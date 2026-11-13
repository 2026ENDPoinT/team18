"""Owner-scoped recommendations; public provider receives no student input."""
from fastapi import APIRouter, Depends
from api.dependencies import owned_context, respond
from api.domain import Problem
from repositories.contestkorea import load_catalog as load_contestkorea_catalog
from services.activity_recommendations import capture_profile, recommend
from services.activity_reasons import attach_reasons
from services.project_experience import digest
from repositories.dacon import load_catalog
from repositories.experience_analysis import decode

router = APIRouter(prefix='/api')


def current_recommendations(db, profile):
    # DB-only snapshot shared by reads and explicit-generation cache validation.
    items, contestkorea_source = load_contestkorea_catalog(db, include_event_context=True)
    dacon_items, dacon_source = load_catalog(db, include_event_context=True)
    return recommend(profile, [*items, *dacon_items], [contestkorea_source, dacon_source])


def restore_generation_failure(db, rid, result):
    """A budget/concurrency rejection has no AI ledger row, but is saved in the run.

    Keep that status on reads of the identical input; never reuse an old failure
    for changed postings, nor treat a failed run's prose as generated content.
    """
    if not any(item.get('reason_status') == 'not_generated' for item in result['activities']):
        return result
    row = db.execute("""SELECT result_json FROM roadmap_runs WHERE request_id=?
        AND status IN ('success','partial') ORDER BY created_at DESC LIMIT 1""", (rid,)).fetchone()
    saved = decode(row['result_json']) if row else None
    activity = saved.get('activity_recommendations', {}) if isinstance(saved, dict) else {}
    if (activity.get('activity_reason_basis') == result['activity_reason_basis']
            and activity.get('activity_reasons_error')):
        return {**result, 'activity_reasons_error': activity['activity_reasons_error'],
                'activities': [{**item, 'reason_status': 'generation_failed'}
                               if item.get('reason_status') == 'not_generated' else item
                               for item in result['activities']]}
    return result


@router.get('/roadmap-inputs/{rid:roadmap_id}/activities')
def activities(rid: str, ctx=Depends(owned_context)):
    db, repo, owner = ctx
    row = repo.plan(rid, owner['owner_id'])
    if not row:
        raise Problem(404, 'not_found', '계획을 찾을 수 없습니다.')
    if not (row['career_goal'] or '').strip():
        raise Problem(422, 'goal_required', '진로 목표를 먼저 입력해 주세요.')
    profile, basis = capture_profile(db, row)
    revision = row['input_revision']
    db.commit()
    # Keep verified event witnesses even when a source has expired or has no
    # career keywords. The event-level decision needs both publishers' evidence.
    result = current_recommendations(db, profile)
    current = repo.plan(rid, owner['owner_id'])
    if not current or current['input_revision'] != revision or digest(capture_profile(db, current)[0]) != digest(profile):
        raise Problem(409, 'revision_conflict', '조회 중 입력이나 경험 근거가 변경되었습니다. 다시 조회해 주세요.')
    result = attach_reasons(ctx, rid, profile, result)
    result = restore_generation_failure(db, rid, result)
    db.commit()
    return respond(200, {**result, 'request_id': rid, 'input_revision': revision, 'activity_basis': basis})
