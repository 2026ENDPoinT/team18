"""Persisted, owner-scoped roadmap generation; GET and progress never call AI."""
from datetime import datetime, timezone
import json
from fastapi import APIRouter, Depends

from api.dependencies import owned_context, parse_body, require_origin, respond
from api.domain import Problem, json_value
from api.schemas import EmptyRequest, openapi_body, validate_body
from repositories.roadmaps import RoadmapRepository, metadata, run_payload
from repositories.postgres import StorageConflict
from services.project_experience import current_comparison, digest
from services.activity_recommendations import capture_profile
from repositories.experience_analysis import decode
from services.roadmap_generation import capture_basis
from services.roadmap_schemas import GenerationRequest, ProgressRequest


router = APIRouter(prefix='/api/roadmap-inputs/{rid:roadmap_id}', tags=['roadmaps'])


def read_basis(ctx, rid, expected=None, *, serialize=False):
    db, repo, owner = ctx
    postgres = getattr(db, 'backend', 'sqlite') == 'postgres'
    for attempt in range(3):
        try:
            db.execute('BEGIN ISOLATION LEVEL REPEATABLE READ' if postgres else 'BEGIN IMMEDIATE')
            row = repo.plan(rid, owner['owner_id'], lock=True)
            if not row:
                raise Problem(404, 'not_found', '계획을 찾을 수 없습니다.')
            if expected is not None and row['input_revision'] != expected:
                raise Problem(409, 'revision_conflict', '입력이 변경되었습니다. 최신 내용을 불러와 주세요.')
            if postgres and serialize:
                # Advance the MVCC tuple without changing any input/revision/timestamp.
                # A waiting generator must retry its RR snapshot and see the committed lease/cache.
                db.execute('UPDATE roadmap_inputs SET updated_at=updated_at WHERE request_id=?', (rid,))
            return capture_basis(db, row)
        except StorageConflict:
            db.execute('ROLLBACK')
            if attempt == 2:
                raise Problem(409, 'revision_conflict', '입력이 동시에 변경되었습니다. 최신 내용을 다시 불러와 주세요.') from None


def timestamp(value):
    return value if isinstance(value, datetime) else datetime.fromisoformat(value)


def expire_runs(ctx, rid):
    # Expiration writes use the same short parent lock as workers. Starting this
    # before the repeatable-read snapshot avoids a serialization failure when a
    # worker has just committed a task update.
    db, repo, owner = ctx
    repo.begin()
    if not repo.plan(rid, owner['owner_id'], lock=True):
        raise Problem(404, 'not_found', '계획을 찾을 수 없습니다.')
    RoadmapRepository(db).expire(rid)
    db.commit()


@router.post('/roadmap', dependencies=[Depends(require_origin)], openapi_extra=openapi_body(GenerationRequest))
def generate(rid: str, ctx=Depends(owned_context), body=Depends(parse_body)):
    request = validate_body(GenerationRequest, body)
    db = ctx[0]
    basis = read_basis(ctx, rid, request.expected_input_revision, serialize=True)
    if not (basis['profile']['career_goal'] or '').strip():
        raise Problem(422, 'goal_required', '진로 목표를 먼저 입력해 주세요.')
    from services.roadmap_batch import _valid_bundle, new_work, start, run as execute_run
    store = RoadmapRepository(db)
    store.expire(rid)
    active = store.active(rid)
    if active:
        response = metadata(active, basis)
        db.commit()
        if not request.background:
            raise Problem(409, 'generation_in_progress', '결과를 저장 중입니다. 잠시 후 저장 결과를 다시 조회해 주세요.')
        return respond(202, response)
    run = store.get(rid, request.retry_run_id) if request.retry_run_id else None
    if run and run['status'] == 'failed' and run['basis_hash'] == digest(basis):
        # Recompute cheap server-only sections; never revive legacy generated tasks.
        store.retry(rid, run['run_id'], basis, new_work())
        run = store.get(rid, run['run_id'])
    else:
        run = None
    if not run and not request.refresh and not request.retry_run_id:
        cached = store.reusable(rid, digest(basis))
        work = decode(cached['basis_json']).get('_generation_work') if cached else None
        if work and work.get('version') == 2 and work.get('verified'):
            result = run_payload(store, cached, basis)
            activity = result.get('activity_recommendations', {})
            row = ctx[1].plan(rid, ctx[2]['owner_id'])
            comparison = json.loads(json.dumps(current_comparison(db, row), ensure_ascii=False, default=json_value))
            try:
                fresh = timestamp(activity['valid_until']) > datetime.now(timezone.utc)
            except (KeyError, TypeError, ValueError):
                fresh = False
            if fresh:
                from api.routes.activities import current_recommendations
                from services.activity_reasons import cache_key, reason_input
                profile, _ = capture_profile(db, row)
                current_activity = current_recommendations(db, profile)
                fresh = (activity.get('activity_reason_basis') == cache_key(rid, reason_input(profile, current_activity['activities']))
                         and bool(activity.get('activity_reason_basis')))
            if (_valid_bundle(result) and fresh and activity.get('activity_basis') == capture_profile(db, row)[1]
                    and digest(result['skill_comparison']) == digest(comparison)):
                db.commit()
                return respond(200, {**result, 'reused': True})
    if not run:
        run = store.create(rid, basis, lease_minutes=10)
        store.update_work(rid, run['run_id'], basis, new_work())
        run = store.get(rid, run['run_id'])
    response = metadata(run, basis)
    db.commit()
    if request.background:
        start(rid, ctx[2], run['run_id'])
        return respond(202, response)
    execute_run(rid, ctx[2], run['run_id'], propagate=True)
    current = read_basis(ctx, rid)
    result = run_payload(store, store.get(rid, run['run_id']), current)
    db.commit()
    return respond(201, {**result, 'reused': False})


@router.get('/roadmap')
def latest(rid: str, ctx=Depends(owned_context)):
    expire_runs(ctx, rid)
    current = read_basis(ctx, rid)
    store = RoadmapRepository(ctx[0])
    history = store.history(rid)
    run = next((r for r in history if r['status'] in ('success', 'partial')), None) or next(iter(history), None)
    result = run_payload(store, run, current) if run else {
        'status': 'not_started', 'limited_guidance_available': current['generation_mode'] == 'limited_guidance',
        'input_revision': current['input_revision'], 'current_input_revision': current['input_revision']}
    result['generation_pending'] = any(
        item['status'] == 'generating' and not metadata(item, current)['generation_expired']
        for item in history)
    if history and decode(history[0]['basis_json']).get('_generation_work'):
        result['latest_generation'] = metadata(history[0], current)
    ctx[0].commit()
    return respond(200, result)


@router.get('/roadmaps')
def history(rid: str, ctx=Depends(owned_context)):
    current = read_basis(ctx, rid)
    result = {'runs': [metadata(r, current) for r in RoadmapRepository(ctx[0]).history(rid)], 'input_revision': current['input_revision']}
    ctx[0].commit()
    return respond(200, result)


@router.post('/roadmaps/{run_id:roadmap_id}/course-reasons', dependencies=[Depends(require_origin)], openapi_extra=openapi_body(EmptyRequest))
def course_reasons(rid: str, run_id: str, ctx=Depends(owned_context), body=Depends(parse_body)):
    validate_body(EmptyRequest, body)
    current = read_basis(ctx, rid)
    store = RoadmapRepository(ctx[0])
    run = store.get(rid, run_id)
    if not run:
        raise Problem(404, 'not_found', '저장된 수강 후보를 찾을 수 없습니다.')
    if metadata(run, current)['details_restricted']:
        raise Problem(409, 'evidence_unavailable', '문서 근거가 변경되어 추천 이유를 확인할 수 없습니다.')
    if run['status'] not in ('success', 'partial'):
        raise Problem(409, 'roadmap_not_ready', '수강 후보 생성이 완료된 뒤 추천 이유를 확인해 주세요.')
    from services.roadmap_batch import _fallback_course_reasons
    saved = run_payload(store, run, current)
    if 'recommended_courses' not in saved:
        raise Problem(409, 'roadmap_not_ready', '결과 저장 확인이 끝난 뒤 추천 이유를 확인해 주세요.')
    # Existing explanations are immutable history. Legacy runs use saved ranking
    # evidence if they predate the bundled explanations; no provider is involved.
    result = ({'reasons': saved['course_reasons'], 'source': saved.get('course_reasons_source', 'saved_result')}
              if 'course_reasons' in saved else
              _fallback_course_reasons(saved['recommended_courses'], run['catalog_id']))
    ctx[0].commit()
    return respond(200, {**result, 'run_id': run_id,
                         'provider': 'gemini' if result['source'] == 'gemini' else 'server',
                         'reason_version': saved.get('course_reasons_version', 'catalog-evidence-v1')})


@router.get('/roadmaps/{run_id:roadmap_id}')
def detail(rid: str, run_id: str, ctx=Depends(owned_context)):
    expire_runs(ctx, rid)
    current = read_basis(ctx, rid)
    store = RoadmapRepository(ctx[0])
    run = store.get(rid, run_id)
    if not run:
        raise Problem(404, 'not_found', '로드맵 실행 이력을 찾을 수 없습니다.')
    result = run_payload(store, run, current)
    ctx[0].commit()
    return respond(200, result)


@router.patch('/roadmaps/{run_id:roadmap_id}/tasks/{task_id}', dependencies=[Depends(require_origin)], openapi_extra=openapi_body(ProgressRequest))
def progress(rid: str, run_id: str, task_id: str, ctx=Depends(owned_context), body=Depends(parse_body)):
    request = validate_body(ProgressRequest, body)
    current = read_basis(ctx, rid, serialize=True)
    store = RoadmapRepository(ctx[0])
    run = store.get(rid, run_id)
    if not run:
        raise Problem(404, 'not_found', '로드맵 실행 이력을 찾을 수 없습니다.')
    if metadata(run, current)['details_restricted']:
        raise Problem(409, 'evidence_unavailable', '문서 기준이 변경된 결과는 상세 조회 및 진행 체크를 할 수 없습니다.')
    tasks = store.progress(run_id) if run['status'] in ('success', 'partial') else {}
    if task_id not in tasks:
        raise Problem(404, 'not_found', '실행 항목을 찾을 수 없습니다.')
    if not store.update_progress(run_id, task_id, request.is_completed, request.expected_progress_version):
        raise Problem(409, 'progress_conflict', '다른 화면에서 진행 상태를 변경했습니다. 저장 상태를 다시 불러와 주세요.')
    result = run_payload(store, run, current)
    ctx[0].commit()
    return respond(200, result)
