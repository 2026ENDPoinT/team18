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
from services.course_reasons import VERSION as REASONS_VERSION, reason_input, generate_course_reasons, validate_course_reasons
from services.project_experience import current_comparison, digest, model_basis
from services.roadmap_generation import capture_basis, model_input, validate_result
from services.ai_guard import guarded_call
from services.gemini import GeminiError
from services.limited_roadmap import limited_roadmap
from course_groups import grouped_courses

logger = logging.getLogger(__name__)
TASKS = ('comparison', 'courses', 'activities', 'roadmap')
executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix='roadmap-run')


def new_work():
    return {'version': 1, 'states': {key: 'pending' for key in TASKS}, 'results': {}, 'verified': False, 'error': None}


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
            raise Problem(502, 'course_reasons_unavailable', '검증된 수강 추천 근거를 찾을 수 없습니다.')
        reasons.append({'course_id': course['course_id'], 'personalization_reason': reason,
                        'evidence_ids': []})
    return {'reasons': reasons, 'source': 'catalog_evidence_fallback'}


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
    value = current_comparison(db, row)
    if not _comparison_available(value):
        raise Problem(422, 'comparison_unavailable', '직무 또는 프로젝트 분석의 검증된 근거를 확인하지 못했습니다.')
    # PostgreSQL returns timestamps/decimals as native Python values; the
    # durable JSON snapshot and later comparison must use the same encoding.
    return json.loads(json.dumps(value, ensure_ascii=False, default=json_value))


def _prepare_job(rid, owner, run_id):
    """Job analysis is a prerequisite only when no current verified snapshot exists."""
    with closing(connect()) as db:
        repo, row, store, run = _locked(db, rid, owner, run_id)
        if run['status'] != 'generating':
            raise Problem(409, 'generation_expired', '생성 시간이 만료되었습니다.')
        before = current_comparison(db, row)
        previous = before['job_analysis']
        needs_job = (not previous.get('snapshot_id') or previous.get('previous_analysis_version')
                     or previous.get('status') != 'success')
        if not needs_job:
            db.commit()
            return
        original_basis, work = _parts(run)
        project_hash = digest(before['project_analysis'])
        work['states']['comparison'] = 'running'
        store.update_work(rid, run_id, original_basis, work)
        db.commit()
        from api.routes.job_skill_analysis import job_skill_analysis
        response = job_skill_analysis(rid, (db, repo, owner), {'refresh': bool(previous.get('snapshot_id'))})
        jobs = json.loads(response.body)
        if jobs.get('status') != 'success' or jobs.get('refresh_error') or not jobs.get('snapshot_id'):
            raise Problem(502, 'job_analysis_failed', '직무 분석을 완료하지 못했습니다.')
        repo, row, store, run = _locked(db, rid, owner, run_id)
        if run['status'] != 'generating' or _date(run['lease_until']) <= datetime.now(timezone.utc):
            raise Problem(409, 'generation_expired', '생성 시간이 만료되었습니다.')
        if row['input_revision'] != run['input_revision'] or digest(current_comparison(db, row)['project_analysis']) != project_hash:
            raise Problem(409, 'revision_conflict', '분석 중 입력이 변경되었습니다.')
        current = capture_basis(db, row)
        # Only the job-derived fields may have changed during the prerequisite.
        for key in ('profile', 'catalog', 'courses', 'review_status', 'course_selection_revision',
                    'reviewed_at', 'outside_completed_courses', 'document_basis', 'project_documents'):
            if digest(current[key]) != digest(original_basis[key]):
                raise Problem(409, 'revision_conflict', '분석 중 입력이 변경되었습니다.')
        _, work = _parts(run)
        store.update_work(rid, run_id, current, work, update_hash=True)
        db.commit()


def _execute(task, rid, owner, basis):
    with closing(connect()) as db:
        repo = Repository(db)
        row = repo.plan(rid, owner['owner_id'])
        if not row or row['input_revision'] != basis['input_revision']:
            raise Problem(409, 'revision_conflict', '분석 중 입력이 변경되었습니다.')
        if task == 'comparison':
            return _comparison(db, row)
        if task == 'courses':
            if not basis['catalog']:
                raise Problem(422, 'catalog_unavailable', '사용할 과목 목록이 없습니다.')
            ranked = rank_courses(basis['profile'], basis['courses'], basis['review_status'], basis['skills'])
            if basis['generation_mode'] == 'limited_guidance':
                return ranked
            originals = {course['course_id']: course for course in basis['courses']}
            return [{**course, 'source': basis['catalog'],
                     'description_text': originals[course['course_id']].get('description_text') or None}
                    for course in ranked]
        if task == 'activities':
            from api.routes.activities import activities
            response = json.loads(activities(rid, (db, repo, owner)).body)
            if not _activity_available(response):
                raise Problem(503, 'activity_source_unavailable', '검증 가능한 활동 자료를 확인하지 못했습니다.')
            return response
        if task == 'roadmap':
            from api.routes.roadmaps import generate_roadmap
            if basis['generation_mode'] == 'limited_guidance':
                return limited_roadmap(basis)
            return guarded_call((db, repo, owner), 'roadmap', digest(basis),
                                lambda: validate_result(generate_roadmap(model_input(basis)), basis))
        raise ValueError('unknown task')


def _execute_reasons(rid, owner, run_id, basis, courses):
    candidates = grouped_courses(courses, basis['profile']['catalog_id'])
    data = reason_input(basis, candidates)
    if not data['courses']:
        return {'reasons': []}
    cache_key = digest([REASONS_VERSION, rid, run_id, model_basis(), data])
    with closing(connect()) as db:
        try:
            result = guarded_call((db, Repository(db), owner), 'course_reasons', cache_key,
                                  lambda: generate_course_reasons(data), cache=True)
        except GeminiError as error:
            if error.code != 'gemini_call_failed':
                raise
            # Preserve the already verified course list and roadmap. Never claim
            # that these deterministic explanations were generated by Gemini.
            logger.warning('roadmap_course_reasons_fallback %s',
                           json.dumps({'run_id': run_id, 'cause': error.code}))
            return _fallback_course_reasons(courses, basis['profile']['catalog_id'])
        return validate_course_reasons(data, result)


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
    comparison, activities = result.get('skill_comparison', {}), result.get('activity_recommendations', {})
    sources = activities.get('sources')
    return (isinstance(steps, list) and bool(steps) and all(isinstance(step, dict) and step.get('step_id')
                and isinstance(step.get('tasks'), list) and step['tasks']
                and all(isinstance(task, dict) and task.get('task_id') for task in step['tasks']) for step in steps)
            and isinstance(courses, list) and all(isinstance(course, dict) and course.get('course_id') for course in courses)
            and _valid_reasons(courses, result.get('course_reasons'), result.get('catalog_id'))
            and _comparison_available(comparison)
            and _activity_available(activities))


def _finish(rid, owner, run_id):
    with closing(connect()) as db:
        repo, row, store, run = _locked(db, rid, owner, run_id)
        basis, work = _parts(run)
        if run['status'] != 'generating' or _date(run['lease_until']) <= datetime.now(timezone.utc):
            raise Problem(409, 'generation_expired', '생성 시간이 만료되었습니다.')
        current = capture_basis(db, row)
        results = work['results']
        if digest(current) != run['basis_hash'] or digest(_comparison(db, row)) != digest(results['comparison']):
            raise Problem(409, 'revision_conflict', '분석 중 입력이나 근거가 변경되었습니다.')
        if capture_profile(db, row)[1] != results['activities'].get('activity_basis'):
            raise Problem(409, 'revision_conflict', '활동 추천 근거가 변경되었습니다.')
        if _date(results['activities']['valid_until']) <= datetime.now(timezone.utc):
            raise Problem(409, 'activity_snapshot_expired', '활동 추천을 다시 확인해야 합니다.')
        if results['roadmap']['recommended_courses'] != results['courses']:
            raise Problem(500, 'course_mismatch', '수강 후보 검증에 실패했습니다.')
        result = {**results['roadmap'], 'skill_comparison': results['comparison'],
                  'activity_recommendations': results['activities'], 'course_reasons': results['course_reasons']['reasons'],
                  'catalog_id': basis['profile']['catalog_id']}
        fallback = results['course_reasons'].get('source') == 'catalog_evidence_fallback'
        if (fallback or results['activities']['status'] == 'partial'
                or results['comparison']['status'] == 'partial'):
            result['status'] = 'partial'
        if fallback:
            result['course_reasons_source'] = 'catalog_evidence_fallback'
            result['limitations'] = [*result.get('limitations', []),
                'Gemini 수강 이유 생성이 실패하여 교육과정의 확인된 근거를 바탕으로 작성한 기본 설명을 제공합니다.']
        if not _valid_bundle(result) or any(work['states'][key] != 'success' for key in TASKS[:-1]):
            raise Problem(500, 'invalid_result', '로드맵 결과를 확인하지 못했습니다.')
        store.finish(rid, run_id, result)
        db.commit()
    # A separate connection verifies the committed result, including task rows.
    with closing(connect()) as db:
        repo, row, store, run = _locked(db, rid, owner, run_id)
        current = capture_basis(db, row)
        saved = run_payload(store, run, current, include_unverified=True)
        basis, work = _parts(run)
        if (run['status'] not in ('success', 'partial') or digest(current) != run['basis_hash']
                or not _valid_bundle(saved) or saved['run_id'] != run_id
                or digest(saved['skill_comparison']) != digest(results['comparison'])
                or digest(saved['activity_recommendations']) != digest(results['activities'])):
            raise Problem(500, 'storage_verification_failed', '저장된 결과를 확인하지 못했습니다.')
        work['states']['roadmap'] = 'success'
        work['verified'] = True
        work['results'] = {}  # The verified snapshot is in result_json, not duplicated.
        store.update_work(rid, run_id, basis, work)
        db.commit()


def run(rid, owner, run_id):
    task = 'comparison'
    pool = None
    try:
        _prepare_job(rid, owner, run_id)
        with closing(connect()) as db:
            run_row = RoadmapRepository(db).get(rid, run_id)
            basis, work = _parts(run_row)
        pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix='roadmap-task')
        pending = {}
        failures = []
        results = dict(work['results'])
        for key in TASKS:
            if key in work['results'] and (key != 'activities' or
                    _date(work['results'][key]['valid_until']) > datetime.now(timezone.utc)):
                continue
            task = key
            _save(rid, owner, run_id, lambda w, k=key: w['states'].__setitem__(k, 'running'))
            pending[pool.submit(_execute, key, rid, owner, basis)] = key
        deadline = _date(run_row['lease_until'])
        while True:
            # Course prose uses the existing AI guard, which allows only one AI
            # operation per owner. Rank in parallel, then explain as soon as the
            # roadmap AI has released its lease; comparison/activity can continue.
            if ('courses' in results and 'course_reasons' not in results and
                    'course_reasons' not in pending.values() and
                    (not results['courses'] or 'roadmap' not in pending.values())):
                task = 'courses'
                _save(rid, owner, run_id, lambda w: w['states'].__setitem__('courses', 'running'))
                pending[pool.submit(_execute_reasons, rid, owner, run_id, basis, results['courses'])] = 'course_reasons'
            if not pending:
                break
            seconds = (deadline - datetime.now(timezone.utc)).total_seconds()
            if seconds <= 0:
                task = next(iter(pending.values()))
                if task == 'course_reasons': task = 'courses'
                raise Problem(504, 'generation_expired', '생성 시간이 만료되었습니다.')
            done, _ = wait(pending, timeout=seconds, return_when=FIRST_COMPLETED)
            if not done:
                task = next(iter(pending.values()))
                if task == 'course_reasons': task = 'courses'
                raise Problem(504, 'generation_expired', '생성 시간이 만료되었습니다.')
            for future in done:
                name = pending.pop(future)
                task = 'courses' if name == 'course_reasons' else name
                try:
                    value = future.result()
                    if name == 'course_reasons' and (not isinstance(value, dict) or
                            not _valid_reasons(results['courses'], value.get('reasons'), basis['profile']['catalog_id'])):
                        raise Problem(502, 'course_reasons_invalid', '수강 추천 이유를 확인하지 못했습니다.')
                except Exception as error:
                    failures.append((task, error))
                    _log(rid, run_id, task, error)
                    def record_failure(w, key=task, exc=error):
                        w['states'][key] = 'failed'
                        w['error'] = {'task': key, 'code': _code(exc)}
                    _save(rid, owner, run_id, record_failure)
                    # Do not repeatedly resubmit a failed reason request in this run.
                    if name == 'course_reasons':
                        results['course_reasons'] = None
                    continue
                results[name] = value
                def record(w, key=name, data=value):
                    w['results'][key] = data
                    # Course explanations and the verified final save are part of
                    # their respective task, not lazy work after the page opens.
                    if key == 'course_reasons':
                        w['states']['courses'] = 'success'
                    else:
                        w['states'][key] = 'running' if key in ('courses', 'roadmap') else 'success'
                _save(rid, owner, run_id, record)
        if failures:
            task, error = failures[0]
            raise error
        # A slow model call can outlast the activity snapshot's validity window.
        with closing(connect()) as db:
            _, work = _parts(RoadmapRepository(db).get(rid, run_id))
        if _date(work['results']['activities']['valid_until']) <= datetime.now(timezone.utc):
            task = 'activities'
            _save(rid, owner, run_id, lambda w: w['states'].__setitem__('activities', 'running'))
            activities = _execute('activities', rid, owner, basis)
            def refresh_activity(w):
                w['results']['activities'] = activities
                w['states']['activities'] = 'success'
            _save(rid, owner, run_id, refresh_activity)
        task = 'roadmap'
        _finish(rid, owner, run_id)
    except Exception as error:
        if getattr(error, 'code', None) == 'activity_snapshot_expired':
            task = 'activities'
        _fail(rid, owner, run_id, task, error)
    finally:
        if pool:
            pool.shutdown(wait=False, cancel_futures=True)


def start(rid, owner, run_id):
    executor.submit(run, rid, dict(owner), run_id)
