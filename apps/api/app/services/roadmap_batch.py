"""Durable orchestration on the existing roadmap run, with short DB transactions."""
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from contextlib import closing
from datetime import datetime, timezone
import json
import logging
import re

from api.domain import Problem, json_value, now
from repositories.experience_analysis import decode
from repositories.plans import Repository, connect
from repositories.roadmaps import RoadmapRepository, run_payload
from services.activity_recommendations import capture_profile
from services.course_recommendations import rank_courses
from services.project_experience import current_comparison, digest
from services.roadmap_generation import capture_basis, roadmap_context
from course_groups import grouped_courses

logger = logging.getLogger(__name__)
TASKS = ('comparison', 'courses', 'activities', 'roadmap')
TERMINAL = ('success', 'partial', 'failed', 'unavailable')
executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix='roadmap-run')


def new_work():
    return {'version': 2, 'states': {key: 'pending' for key in TASKS}, 'results': {}, 'verified': False, 'error': None}


def _date(value):
    return value if isinstance(value, datetime) else datetime.fromisoformat(value)


def _parts(run):
    data = decode(run['basis_json'])
    return {key: value for key, value in data.items() if key != '_generation_work'}, data['_generation_work']


def _code(error):
    diagnostic = getattr(error, 'diagnostic', None)
    code = diagnostic if isinstance(diagnostic, str) else getattr(error, 'code', None) or type(error).__name__
    return code if isinstance(code, str) and re.fullmatch(r'[A-Za-z0-9_:-]{1,80}', code) else 'unknown_error'


def _comparison_available(value):
    """Reject missing job evidence, but retain individually verified project items."""
    if not isinstance(value, dict) or not isinstance(value.get('comparisons'), list):
        return False
    jobs, project = value.get('job_analysis', {}), value.get('project_analysis', {})
    if (not isinstance(jobs, dict) or not isinstance(project, dict)
            or jobs.get('status') != 'success' or not jobs.get('snapshot_id')
            or jobs.get('previous_analysis_version')):
        return False
    status = project.get('status')
    return (status in ('success', 'no_documents')
            or (status == 'partial' and project.get('verified_experiences', 0) > 0))


def _activity_available(value):
    """Partial collection is usable only with previously verified candidates."""
    if not isinstance(value, dict) or not isinstance(value.get('activities'), list):
        return False
    sources = value.get('sources')
    if not isinstance(sources, list) or not sources or any(
            not isinstance(source, dict) or source.get('status') not in ('success', 'partial', 'error')
            for source in sources):
        return False
    if value.get('status') == 'success':
        return all(source['status'] == 'success' for source in sources)
    if value.get('status') == 'partial':
        return any(source['status'] in ('success', 'partial')
                   and type(source.get('collected')) is int and source['collected'] > 0
                   for source in sources)
    return False


def _fallback_course_reasons(courses, catalog_id):
    """Use existing catalog-grounded ranking explanations, never invented AI text."""
    reasons = []
    for course in grouped_courses(courses, catalog_id):
        reason = course.get('personalization_reason') or course.get('reason')
        if not isinstance(reason, str) or not reason.strip():
            reason = '저장된 추천 근거가 부족하여 실제 학습 내용과 목표의 관련성을 확인해야 합니다.'
        reasons.append({'course_id': course['course_id'], 'personalization_reason': reason,
                        'evidence_ids': []})
    return {'reasons': reasons, 'source': 'catalog_evidence'}


def _log(rid, run_id, task, error):
    # Never serialize exception text: drivers/providers can include credentials or user data.
    logger.error('roadmap_task_failed %s', json.dumps({'run_id': run_id, 'task': task,
        'path': f'/api/roadmap-inputs/{rid}/roadmap', 'cause': _code(error)}))


def _locked(db, rid, owner, run_id):
    repo = Repository(db)
    repo.begin()
    row = repo.plan(rid, owner['owner_id'], lock=True)
    if not row:
        raise Problem(404, 'not_found', '계획을 찾을 수 없습니다.')
    store = RoadmapRepository(db)
    run = store.get(rid, run_id)
    if not run:
        raise Problem(404, 'not_found', '로드맵 실행을 찾을 수 없습니다.')
    return repo, row, store, run


def _save(rid, owner, run_id, change):
    with closing(connect()) as db:
        _, _, store, run = _locked(db, rid, owner, run_id)
        if run['status'] != 'generating' or _date(run['lease_until']) <= datetime.now(timezone.utc):
            raise Problem(409, 'generation_expired', '생성 시간이 만료되었습니다.')
        basis, work = _parts(run)
        change(work)
        store.update_work(rid, run_id, basis, work)
        db.commit()


def _fail(rid, owner, run_id, task, error):
    _log(rid, run_id, task, error)
    try:
        with closing(connect()) as db:
            _, _, store, run = _locked(db, rid, owner, run_id)
            basis, work = _parts(run)
            if work.get('verified') or run['status'] == 'failed':
                db.commit()
                return
            work['states'][task] = 'failed'
            for key in TASKS:
                if key != task and work['states'][key] == 'running':
                    work['states'][key] = 'pending'
            work['error'] = {'task': task, 'code': _code(error)}
            store.update_work(rid, run_id, basis, work)
            # A commit/verification failure may have left an unverified result.
            db.execute('DELETE FROM roadmap_task_progress WHERE run_id=?', (run_id,))
            db.execute("UPDATE roadmap_runs SET status='failed',result_json=NULL,error_code=?,finished_at=? WHERE request_id=? AND run_id=?",
                       (_code(error), now(), rid, run_id))
            db.commit()
    except Exception as failure:
        _log(rid, run_id, 'failure_record', failure)


def _comparison(db, row):
    # Reading a comparison never starts job/project analysis.
    return json.loads(json.dumps(current_comparison(db, row), ensure_ascii=False, default=json_value))


def _prepare_job(rid, owner, run_id):
    """Reuse saved snapshots only; explicit job analysis owns all AI calls."""
    return None


def _component_status(task, value, basis):
    if task == 'courses':
        return 'unavailable' if basis['review_status'] == 'unavailable' else 'success'
    if task == 'comparison':
        jobs = value.get('job_analysis', {})
        if not jobs.get('snapshot_id'):
            return 'unavailable' if jobs.get('status') == 'not_started' else 'failed'
        return ('success' if _comparison_available(value)
                and value['project_analysis'].get('status') != 'partial' else 'partial')
    status = value.get('status')
    return 'failed' if status == 'error' else status


def _unavailable(task, error):
    code = _code(error)
    if task == 'comparison':
        return {'status': 'error', 'comparisons': [], 'job_analysis': {'status': 'error', 'skills': []},
                'project_analysis': {'status': 'error'}, 'error_code': code}
    if task == 'activities':
        return {'status': 'error', 'activities': [], 'sources': [], 'error_code': code}
    return []


def _execute(task, rid, owner, basis):
    with closing(connect()) as db:
        repo = Repository(db)
        row = repo.plan(rid, owner['owner_id'])
        if not row or row['input_revision'] != basis['input_revision']:
            raise Problem(409, 'revision_conflict', '분석 중 입력이 변경되었습니다.')
        if task == 'comparison':
            return _comparison(db, row)
        if task == 'courses':
            ranked = rank_courses(basis['profile'], basis['courses'], basis['review_status'], basis['skills'])
            originals = {course['course_id']: course for course in basis['courses']}
            return [{**course, 'source': basis['catalog'],
                     'description_text': originals[course['course_id']].get('description_text') or None}
                    for course in ranked]
        if task == 'activities':
            from api.routes.activities import activities
            response = json.loads(activities(rid, (db, repo, owner)).body)
            if (not isinstance(response.get('activities'), list) or not isinstance(response.get('sources'), list)
                    or response.get('status') not in ('success', 'partial', 'error')
                    or (response['status'] == 'success' and not _activity_available(response))):
                raise Problem(502, 'activity_source_invalid', '활동 자료의 형식을 확인하지 못했습니다.')
            return response
        raise ValueError('unknown task')


def _execute_reasons(rid, owner, run_id, basis, courses):
    return _fallback_course_reasons(courses, basis['profile']['catalog_id'])


def _valid_reasons(courses, reasons, catalog_id):
    if not isinstance(reasons, list):
        return False
    expected = {course['course_id'] for course in grouped_courses(courses, catalog_id)}
    if any(not isinstance(item, dict) or not isinstance(item.get('course_id'), str)
           or not isinstance(item.get('personalization_reason'), str) or not item['personalization_reason'].strip()
           for item in reasons):
        return False
    ids = [item['course_id'] for item in reasons]
    return len(ids) == len(set(ids)) and set(ids) == expected


def _valid_bundle(result):
    if not isinstance(result, dict):
        return False
    steps, courses = result.get('roadmap'), result.get('recommended_courses')
    comparison, activities = result.get('skill_comparison'), result.get('activity_recommendations')
    if not (isinstance(steps, list) and isinstance(courses, list)
            and all(isinstance(c, dict) and isinstance(c.get('course_id'), str) for c in courses)
            and _valid_reasons(courses, result.get('course_reasons'), result.get('catalog_id'))
            and isinstance(comparison, dict) and isinstance(comparison.get('comparisons'), list)
            and isinstance(comparison.get('job_analysis'), dict)
            and isinstance(comparison.get('project_analysis'), dict)
            and isinstance(activities, dict) and isinstance(activities.get('activities'), list)
            and isinstance(activities.get('sources'), list)):
        return False
    states = result.get('component_status')
    if states is None:  # Legacy completed bundles remain readable/reusable.
        return _comparison_available(comparison) and _activity_available(activities)
    if (steps or not isinstance(states, dict) or set(states) != set(TASKS[:-1])
            or any(state not in TERMINAL for state in states.values())
            or result.get('status') != ('success' if all(v == 'success' for v in states.values()) else 'partial')):
        return False
    if states['comparison'] == 'success' and not _comparison_available(comparison):
        return False
    if states['comparison'] == 'unavailable' and comparison['job_analysis'].get('status') != 'not_started':
        return False
    if states['courses'] in ('failed', 'unavailable') and courses:
        return False
    activity_status = 'failed' if activities.get('status') == 'error' else activities.get('status')
    return (states['activities'] == activity_status
            and (activity_status != 'success' or _activity_available(activities)))


def _finish(rid, owner, run_id):
    with closing(connect()) as db:
        repo, row, store, run = _locked(db, rid, owner, run_id)
        basis, work = _parts(run)
        if run['status'] != 'generating' or _date(run['lease_until']) <= datetime.now(timezone.utc):
            raise Problem(409, 'generation_expired', '생성 시간이 만료되었습니다.')
        current = capture_basis(db, row)
        results = work['results']
        if digest(current) != run['basis_hash']:
            raise Problem(409, 'revision_conflict', '분석 중 입력이나 근거가 변경되었습니다.')
        states = {key: work['states'][key] for key in TASKS[:-1]}
        if states['comparison'] != 'failed' and digest(_comparison(db, row)) != digest(results['comparison']):
            raise Problem(409, 'revision_conflict', '직무 비교 근거가 변경되었습니다.')
        activity = results['activities']
        if activity.get('activity_basis'):
            if capture_profile(db, row)[1] != activity['activity_basis']:
                raise Problem(409, 'revision_conflict', '활동 추천 근거가 변경되었습니다.')
            if _date(activity['valid_until']) <= datetime.now(timezone.utc):
                raise Problem(409, 'activity_snapshot_expired', '활동 추천을 다시 확인해야 합니다.')
        result = {
            'status': 'success' if all(v == 'success' for v in states.values()) else 'partial',
            'generation_mode': 'saved_data', 'roadmap': [],
            'career_goal': basis['profile']['career_goal'], 'target_role': basis['profile']['target_role'],
            'preparation_summary': {'confirmed_skills': [], 'skills_to_verify': [], 'learning_candidates': []},
            'preparation_items': [], 'evidence': basis['evidence'],
            'recommended_courses': results['courses'], 'skill_comparison': results['comparison'],
            'activity_recommendations': activity, 'course_reasons': results['course_reasons']['reasons'],
            'course_reasons_source': 'catalog_evidence', 'component_status': states,
            'component_errors': work.get('errors', {}),
            'catalog_id': basis['profile']['catalog_id'], 'limitations': basis['limitations'],
            **roadmap_context(basis),
        }
        if states['courses'] == 'failed':
            result['course_status'] = 'failed'
        if not _valid_bundle(result):
            raise Problem(500, 'invalid_result', '로드맵 결과를 확인하지 못했습니다.')
        store.finish(rid, run_id, result)
        db.commit()
    # Verify the full committed snapshot on a separate connection before exposing it.
    with closing(connect()) as db:
        repo, row, store, run = _locked(db, rid, owner, run_id)
        current = capture_basis(db, row)
        saved = run_payload(store, run, current, include_unverified=True)
        basis, work = _parts(run)
        if (run['status'] not in ('success', 'partial') or digest(current) != run['basis_hash']
                or not _valid_bundle(saved) or saved['run_id'] != run_id
                or digest(decode(run['result_json'])) != digest(result)
                or digest(saved['skill_comparison']) != digest(results['comparison'])
                or digest(saved['activity_recommendations']) != digest(results['activities'])):
            raise Problem(500, 'storage_verification_failed', '저장된 결과를 확인하지 못했습니다.')
        work['states']['roadmap'] = 'success'
        work['verified'] = True
        work['results'] = {}  # The verified snapshot is in result_json, not duplicated.
        store.update_work(rid, run_id, basis, work)
        db.commit()


def run(rid, owner, run_id, *, propagate=False):
    task = 'roadmap'
    pool = None
    try:
        _prepare_job(rid, owner, run_id)
        with closing(connect()) as db:
            run_row = RoadmapRepository(db).get(rid, run_id)
            basis, work = _parts(run_row)
        pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix='roadmap-task')
        pending = {}
        for key in TASKS[:-1]:
            task = key
            _save(rid, owner, run_id, lambda w, k=key: w['states'].__setitem__(k, 'running'))
            pending[pool.submit(_execute, key, rid, owner, basis)] = key
        deadline = _date(run_row['lease_until'])
        while pending:
            seconds = (deadline - datetime.now(timezone.utc)).total_seconds()
            done, _ = wait(pending, timeout=max(0, seconds), return_when=FIRST_COMPLETED)
            if not done:
                raise Problem(504, 'generation_expired', '생성 시간이 만료되었습니다.')
            for future in done:
                task = pending.pop(future)
                error_code = None
                try:
                    value = future.result()
                    state = _component_status(task, value, basis)
                except Exception as error:
                    if getattr(error, 'code', None) in ('revision_conflict', 'generation_expired'):
                        raise
                    _log(rid, run_id, task, error)
                    value, state, error_code = _unavailable(task, error), 'failed', _code(error)
                    if task == 'comparison':
                        value.update(input_revision=basis['input_revision'],
                                     career_goal=basis['profile']['career_goal'],
                                     target_role=basis['profile']['target_role'])
                reasons = _execute_reasons(rid, owner, run_id, basis, value) if task == 'courses' else None
                def record(w, key=task, data=value, status=state, code=error_code, prose=reasons):
                    w['results'][key] = data
                    w['states'][key] = status
                    if code:
                        w.setdefault('errors', {})[key] = code
                    if prose is not None:
                        w['results']['course_reasons'] = prose
                _save(rid, owner, run_id, record)
        task = 'roadmap'  # Compatibility key: only the final durable save.
        _save(rid, owner, run_id, lambda w: w['states'].__setitem__('roadmap', 'running'))
        _finish(rid, owner, run_id)
    except Exception as error:
        _fail(rid, owner, run_id, task, error)
        if propagate:
            raise
    finally:
        if pool:
            pool.shutdown(wait=False, cancel_futures=True)


def start(rid, owner, run_id):
    executor.submit(run, rid, dict(owner), run_id)
