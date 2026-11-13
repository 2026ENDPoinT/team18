"""Saved reasons and catalog-only legacy explanations never invoke Gemini."""
from contextlib import closing
from unittest.mock import patch

from roadmap_scenario import RoadmapAPI
from repositories.plans import connect
from repositories.roadmaps import RoadmapRepository
from repositories.experience_analysis import decode

case = RoadmapAPI()
case.setUp()
try:
    with patch('services.course_reasons._generate', side_effect=AssertionError('Unexpected AI')) as ai:
        saved = case.make().json()
        path = f'{case.base}/roadmaps/{saved["run_id"]}/course-reasons'
        original = case.client.get(case.base + '/roadmap').json()
        first = case.client.post(path, json={})
        assert first.status_code == 200, first.text
        assert first.json()['provider'] == 'server'
        assert first.json()['reasons'] == saved['course_reasons']
        assert case.client.post(path, json={}).json() == first.json()
        assert case.client.get(case.base + '/roadmap').json() == original
        assert case.client.post(path, json={'courses': []}).status_code == 422
        assert case.client.post(path, json={}, headers={'Origin': 'https://unrelated.example'}).status_code == 403
        other = RoadmapAPI(); other.setUp()
        try:
            assert other.client.post(path, json={}).status_code == 404
        finally:
            other.doCleanups()
        # Legacy saved results without a bundled reason use saved catalog prose.
        with closing(connect()) as db:
            store = RoadmapRepository(db)
            raw = decode(store.get(case.rid, saved['run_id'])['result_json'])
            raw.pop('course_reasons'); raw.pop('course_reasons_source')
            db.execute('UPDATE roadmap_runs SET result_json=? WHERE run_id=?', (store.encode(raw), saved['run_id']))
        fallback = case.client.post(path, json={}).json()
        assert fallback['source'] == 'catalog_evidence'
        assert fallback['reasons'] == saved['course_reasons']
        case.doc('새 프로젝트 문서입니다.')
        assert case.client.post(path, json={}).status_code == 409
        ai.assert_not_called()
    print('PASS: saved and legacy reasons, no AI, ownership/origin and evidence restrictions')
finally:
    case.doCleanups()
