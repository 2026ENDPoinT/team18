"""Regression coverage for verified partial evidence and safe catalog fallbacks."""
from services.roadmap_batch import (
    _activity_available, _comparison_available, _valid_bundle
)


def partial_comparison():
    return {
        'job_analysis': {'status': 'success', 'snapshot_id': 'snapshot-1'},
        'project_analysis': {
            'status': 'partial', 'verified_experiences': 3,
            'errors': [{'code': 'activity_not_in_evidence'}],
        },
        'comparisons': [],
    }


def partial_activities():
    return {
        'status': 'partial', 'activities': [],
        'sources': [
            {'status': 'success', 'collected': 0},
            {'status': 'partial', 'collected': 15},
        ],
    }


def test_verified_partial_project_is_usable_but_empty_partial_is_not():
    comparison = partial_comparison()
    assert _comparison_available(comparison)
    comparison['project_analysis']['verified_experiences'] = 0
    assert not _comparison_available(comparison)


def test_verified_partial_activity_source_is_usable():
    assert _activity_available(partial_activities())
    assert _activity_available({'status': 'success', 'activities': [],
                                'sources': [{'status': 'success', 'collected': 0}]})


def test_source_error_with_no_candidates_is_not_silent_success():
    assert not _activity_available({
        'status': 'partial', 'activities': [],
        'sources': [{'status': 'success', 'collected': 0},
                    {'status': 'error', 'collected': 0}],
    })
    assert not _activity_available({
        'status': 'error', 'activities': [], 'sources': [
            {'status': 'error', 'collected': 0},
        ],
    })


def test_bundle_accepts_verified_partial_results_only():
    result = {
        'roadmap': [{'step_id': 'step-1', 'tasks': [{'task_id': 'task-1'}]}],
        'recommended_courses': [{'course_id': 'course-1'}],
        'course_reasons': [{'course_id': 'course-1',
                            'personalization_reason': '원문 학습 내용에 근거한 설명'}],
        'catalog_id': 'synthetic-catalog',
        'skill_comparison': partial_comparison(),
        'activity_recommendations': partial_activities(),
    }
    assert _valid_bundle(result)
    result['activity_recommendations']['sources'][1]['collected'] = 0
    assert not _valid_bundle(result)


def test_partial_bundle_requires_honest_terminal_states_and_intact_reasons():
    from copy import deepcopy
    result = {
        'status': 'partial', 'roadmap': [], 'recommended_courses': [{'course_id': 'c'}],
        'course_reasons': [{'course_id': 'c', 'personalization_reason': '저장된 교육과정 근거'}],
        'component_status': {'comparison': 'unavailable', 'courses': 'success', 'activities': 'failed'},
        'skill_comparison': {'comparisons': [], 'job_analysis': {'status': 'not_started'}, 'project_analysis': {}},
        'activity_recommendations': {'status': 'error', 'activities': [], 'sources': []},
    }
    assert _valid_bundle(result)
    for key, value in [('status', 'success'), ('course_reasons', []),
                       ('recommended_courses', [{'course_name': 'missing ID'}]), ('roadmap', [{}])]:
        assert not _valid_bundle({**result, key: value})
    for key, value in [('comparison', 'success'), ('activities', 'success'), ('courses', 'running')]:
        changed = deepcopy(result)
        changed['component_status'][key] = value
        assert not _valid_bundle(changed)
