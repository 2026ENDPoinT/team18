"""Catalog-authored course explanations; no provider or AI cache is involved."""
from course_groups import canonical_id
from repositories.courses import CourseRepository

VERSION = 'catalog-fixed-reasons-v1'
SOURCE = 'catalog_fixed'
MISSING_REASON = '추천 근거 확인 필요'


def attach_course_reasons(db, catalog_id, courses):
    """Overlay display fields without changing order, identities or evidence.

    A reviewed bilingual group always uses its canonical Korean member, even for
    a legacy English-only result. Missing representatives never borrow another
    member's prose. The run's catalog ID, not the current profile, owns the lookup.
    """
    ids = [canonical_id(catalog_id, course['course_id']) for course in courses]
    stored = CourseRepository(db).recommendation_reasons(catalog_id, ids)
    result = []
    for course, cid in zip(courses, ids):
        value = stored.get(cid)
        present = isinstance(value, str) and bool(value.strip())
        reason = value if present else MISSING_REASON
        result.append({**course, 'recommendation_reason': value if present else None,
                       'reason': reason, 'personalization_reason': reason,
                       'reason_source': SOURCE if present else 'safe_fallback',
                       'reason_provider': 'database' if present else 'server',
                       'reason_version': VERSION})
    return result


def course_reasons_payload(courses):
    """Keep the existing reasons/personalization_reason/evidence_ids contract."""
    sources = {course['reason_source'] for course in courses}
    source = ('catalog_fixed_with_fallback' if len(sources) > 1 else
              next(iter(sources), SOURCE))
    return {'reasons': [{'course_id': course['course_id'],
                         'personalization_reason': course['personalization_reason'],
                         # Fixed editorial prose does not cite generated evidence IDs.
                         'evidence_ids': []} for course in courses],
            'source': source, 'provider': 'server' if source == 'safe_fallback' else 'database',
            'reason_version': VERSION}


def present_course_reasons(db, catalog_id, result):
    """Read projection only: historical result_json/basis_json stay immutable."""
    courses = attach_course_reasons(db, catalog_id, result['recommended_courses'])
    reasons = course_reasons_payload(courses)
    return {**result, 'recommended_courses': courses, 'course_reasons': reasons['reasons'],
            'course_reasons_source': reasons['source'], 'course_reasons_provider': reasons['provider'],
            'course_reasons_version': VERSION, 'course_reasons_error': None}


def experience_input(experiences):
    """Send effective, verified observations without document text or identifiers."""
    result = []
    fields = ('skill_name', 'activity', 'role', 'output', 'contribution_scope')
    for item in experiences:
        if not item.get('evidence_verified'):
            continue
        user = item.get('user_answer') or {}
        status = user.get('status')
        effective = user.get('correction') if status == 'corrected' else item
        if not effective:
            continue
        selected = ('skill_name',) if status in ('no_experience', 'unknown') else fields
        result.append({**{key: effective.get(key) for key in selected}, 'user_status': status or 'unconfirmed'})
    return result
