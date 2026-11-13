"""Saved legacy and new results share a protected, persisted Gemini reason cache."""
from contextlib import closing
from unittest.mock import patch

from roadmap_scenario import RoadmapAPI
from repositories.plans import connect
from services.course_reasons import CourseReasons
from services.gemini import GeminiError


def provider(schema, instruction, data, **kwargs):
    return CourseReasons(reasons=[{'course_id': c['course_id'],
        'personalization_reason': '데이터 분석 목표와 연결할 과목명 기반 후보입니다. 실제 학습 내용을 확인해 주세요.',
        'evidence_ids': [c['evidence'][0]['id']] if c['evidence'] else []} for c in data['courses']])


case = RoadmapAPI()
case.setUp()
try:
    # Includes runs created before the reason feature, without job analysis.
    saved = case.make().json()
    path = f'{case.base}/roadmaps/{saved["run_id"]}/course-reasons'
    original = case.client.get(case.base + '/roadmap').json()
    with patch('services.course_reasons._generate', side_effect=provider) as ai:
        first = case.client.post(path, json={})
        assert first.status_code == 200, first.text
        assert first.json()['provider'] == 'gemini'
        assert [r['course_id'] for r in first.json()['reasons']] == [c['course_id'] for c in saved['recommended_courses']]
        again = case.client.post(path, json={})
        assert again.json() == first.json() and ai.call_count == 1
        # GET remains read-only and the existing roadmap/task snapshot is untouched.
        assert case.client.get(case.base + '/roadmap').json() == original
        assert ai.call_count == 1
        assert case.client.post(path, json={'courses': []}).status_code == 422
        assert case.client.post(path, json={}, headers={'Origin': 'https://unrelated.example'}).status_code == 403
        other = RoadmapAPI(); other.setUp()
        try:
            assert other.client.post(path, json={}).status_code == 404
            assert other.client.post(f'{other.base}/roadmaps/{saved["run_id"]}/course-reasons', json={}).status_code == 404
        finally:
            other.tearDown()
        assert ai.call_count == 1
    # A new saved goal/result must receive its own explanation.
    response = case.client.patch(case.base, json={'expected_input_revision': case.revision(), 'changes': {'career_goal': 'SQL 분석을 배우고 싶어요.'}})
    assert response.status_code == 200
    newer = case.make().json()
    next_path = f'{case.base}/roadmaps/{newer["run_id"]}/course-reasons'
    with patch('services.course_reasons._generate', side_effect=GeminiError('gemini_timeout', '추천 이유 요청 시간 초과')) as ai:
        failed = case.client.post(next_path, json={})
        assert failed.status_code == 502 and failed.json()['error'] == 'gemini_timeout', failed.text
        assert ai.call_count == 1
    with patch('services.course_reasons._generate', side_effect=provider) as ai:
        assert case.client.post(next_path, json={}).status_code == 200
        assert ai.call_count == 1
    # Changed input during the provider call cannot be returned as current.
    response = case.client.patch(case.base, json={'expected_input_revision': case.revision(), 'changes': {'career_goal': '행사 신청 흐름 분석'}})
    assert response.status_code == 200
    latest = case.make().json()
    latest_path = f'{case.base}/roadmaps/{latest["run_id"]}/course-reasons'
    def changing_provider(*args, **kwargs):
        with closing(connect()) as db:
            db.execute('UPDATE roadmap_inputs SET input_revision=input_revision+1 WHERE request_id=?', (case.rid,))
            db.commit()
        return provider(*args, **kwargs)
    with patch('services.course_reasons._generate', side_effect=changing_provider):
        assert case.client.post(latest_path, json={}).status_code == 409
    # Existing document restrictions are enforced even for a cached explanation.
    case.doc('새 프로젝트 문서입니다.')
    with patch('services.course_reasons._generate') as ai:
        assert case.client.post(path, json={}).status_code == 409
        ai.assert_not_called()
    print('PASS: generated reasons, persisted cache, saved-run preservation, ownership/origin, new goal, failure/retry, in-flight changes, evidence restriction')
finally:
    case.tearDown()
