"""Real API/history projection with synthetic records and forbidden Gemini calls."""
from contextlib import closing
from copy import deepcopy
import unittest
import uuid
from unittest.mock import patch

from roadmap_scenario import RoadmapAPI, C, C2, U, DB_COURSE, fake_extraction
from repositories.plans import connect
from repositories.roadmaps import RoadmapRepository
from repositories.experience_analysis import decode
from services.course_reasons import MISSING_REASON, VERSION
from services.roadmap_generation import capture_basis
from services.project_experience import digest

TEXT = '본 강좌에서는 데이터베이스의 구성과 운영 방법을 학습한다.'
SECOND = 'reason-test-second'


class FixedReasonAPI(RoadmapAPI):
    def setUp(self):
        super().setUp()
        for path in ('google.genai.Client', 'services.gemini_roadmap.generate_roadmap', 'services.gemini_jobs._generate'):
            blocker = patch(path, side_effect=AssertionError('Unexpected AI'))
            spy = blocker.start(); self.addCleanup(blocker.stop); self.addCleanup(spy.assert_not_called)
        with closing(connect()) as db:
            db.execute('UPDATE catalog_courses SET recommendation_reason=?,description_text=? WHERE catalog_id=? AND course_id=?',
                       (TEXT, 'SQL 데이터 조회를 학습한다.', C, DB_COURSE))
            db.execute('INSERT INTO courses(course_id,university_id,canonical_name) VALUES(?,?,?) ON CONFLICT DO NOTHING', (SECOND, U, '설명 미등록'))
            db.execute('INSERT INTO catalog_courses(catalog_id,course_id,course_name) VALUES(?,?,?) ON CONFLICT DO NOTHING', (C, SECOND, '설명 미등록'))
            db.execute('INSERT INTO catalog_courses(catalog_id,course_id,course_name,recommendation_reason) VALUES(?,?,?,?) ON CONFLICT DO NOTHING',
                       (C2, DB_COURSE, '동일 이름', '다른 교육과정의 문구'))
            db.commit()

    def saved(self, refresh=False):
        response = self.make(refresh)
        self.assertIn(response.status_code, (200, 201), response.text)
        return response.json()

    def assert_fixed(self, result, text=TEXT):
        course = next(c for c in result['recommended_courses'] if c['course_id'] == DB_COURSE)
        self.assertEqual(course['recommendation_reason'], text)
        self.assertEqual(course['reason'], text)
        self.assertEqual(course['personalization_reason'], text)
        self.assertEqual(next(c['personalization_reason'] for c in result['course_reasons'] if c['course_id'] == DB_COURSE), text)
        self.assertEqual(result['course_reasons_version'], VERSION)
        self.assertEqual(result['course_reasons_provider'], 'database')

    def snapshot(self, run_id):
        with closing(connect()) as db:
            return deepcopy(RoadmapRepository(db).get(self.rid, run_id))

    def test_fixed_new_standalone_repeated_reads_and_missing_reason(self):
        saved = self.saved()
        self.assert_fixed(saved)
        self.assertEqual(saved['course_reasons_source'], 'catalog_fixed_with_fallback')
        missing = next(c for c in saved['recommended_courses'] if c['course_id'] == SECOND)
        self.assertEqual(missing['reason'], MISSING_REASON)
        standalone = self.client.post(self.base + '/course-recommendations', json={}).json()
        self.assertEqual([c['course_id'] for c in standalone['courses']], [c['course_id'] for c in saved['recommended_courses']])
        self.assertEqual(next(c['reason'] for c in standalone['courses'] if c['course_id'] == DB_COURSE), TEXT)
        before = self.snapshot(saved['run_id'])
        path = f'{self.base}/roadmaps/{saved["run_id"]}'
        for _ in range(3):
            self.assert_fixed(self.client.get(path).json())
            self.assert_fixed(self.client.get(self.base + '/roadmap').json())
            reasons = self.client.post(path + '/course-reasons', json={}).json()
            self.assertEqual(reasons['reasons'], saved['course_reasons'])
            self.assertEqual(reasons['provider'], 'database')
        self.assertEqual(self.snapshot(saved['run_id']), before)
        with closing(connect()) as db:
            self.assertEqual(db.execute("SELECT count(*) n FROM ai_requests WHERE operation='course_reasons' AND owner_id=(SELECT owner_id FROM roadmap_inputs WHERE request_id=?)", (self.rid,)).fetchone()['n'], 0)

    def test_fixed_legacy_ai_and_cache_never_override_or_rewrite_history(self):
        saved = self.saved()
        path = f'{self.base}/roadmaps/{saved["run_id"]}'
        with closing(connect()) as db:
            store = RoadmapRepository(db)
            raw = decode(store.get(self.rid, saved['run_id'])['result_json'])
            for course in raw['recommended_courses']:
                course.update(reason='잘못된 AI 주장', personalization_reason='잘못된 AI 주장')
                course.pop('recommendation_reason', None)
            raw.update(course_reasons=[{'course_id': c['course_id'], 'personalization_reason': '옛 Gemini 문구', 'evidence_ids': ['old']} for c in raw['recommended_courses']],
                       course_reasons_source='gemini', course_reasons_version='course-goal-reasons-v2')
            # A legacy run with progress must preserve both the task and its completion.
            raw['roadmap'] = [{'step_id': 'legacy-step', 'related_course_ids': [DB_COURSE], 'tasks': [{'task_id': 'legacy-task'}]}]
            db.execute('INSERT INTO roadmap_task_progress(run_id,task_id,is_completed,updated_at) VALUES(?,?,TRUE,?)',
                       (saved['run_id'], 'legacy-task', '2026-11-14T00:00:00+00:00'))
            db.execute('UPDATE roadmap_runs SET result_json=? WHERE run_id=?', (store.encode(raw), saved['run_id']))
            owner = db.execute('SELECT owner_id FROM roadmap_inputs WHERE request_id=?', (self.rid,)).fetchone()['owner_id']
            cache_id = str(uuid.uuid4())
            db.execute('INSERT INTO ai_requests(request_id,owner_id,operation,basis_hash,units,status,created_at,lease_until,result_json) VALUES(?,?,?,?,?,?,?,?,?)',
                       (cache_id, owner, 'course_reasons', 'legacy-key', 1, 'finished', '2026-11-14T00:00:00+00:00', '2026-11-14T00:10:00+00:00', store.encode({'reasons': raw['course_reasons'], 'source': 'gemini'})))
            cache_before = dict(db.execute('SELECT * FROM ai_requests WHERE request_id=?', (cache_id,)).fetchone())
            db.commit()
        before = self.snapshot(saved['run_id'])
        for suffix in ('', '/course-reasons'):
            response = self.client.post(path + suffix, json={}) if suffix else self.client.get(path)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertNotIn('옛 Gemini 문구', str(response.json()))
        result = self.client.get(path).json()
        self.assert_fixed(result)
        self.assertTrue(result['roadmap'][0]['tasks'][0]['is_completed'])
        self.assertEqual(result['progress'], {'completed': 1, 'total': 1})
        self.assertEqual(self.snapshot(saved['run_id']), before)
        with closing(connect()) as db:
            self.assertEqual(dict(db.execute('SELECT * FROM ai_requests WHERE request_id=?', (cache_id,)).fetchone()), cache_before)
        # Missing legacy reason bundle follows the same DB projection.
        with closing(connect()) as db:
            raw.pop('course_reasons')
            db.execute('UPDATE roadmap_runs SET result_json=? WHERE run_id=?', (store.encode(raw), saved['run_id']))
            db.commit()
        self.assert_fixed(self.client.get(path).json())

    def test_fixed_edit_does_not_invalidate_basis_or_regenerate(self):
        saved = self.saved()
        before = self.snapshot(saved['run_id'])
        with closing(connect()) as db:
            row = db.execute('SELECT * FROM roadmap_inputs WHERE request_id=?', (self.rid,)).fetchone()
            basis = digest(capture_basis(db, row))
            db.execute('UPDATE catalog_courses SET recommendation_reason=? WHERE catalog_id=? AND course_id=?', (TEXT + ' 개정 안내.', C, DB_COURSE))
            self.assertEqual(digest(capture_basis(db, row)), basis)
            db.commit()
        result = self.saved()
        self.assertEqual(result['run_id'], saved['run_id'])
        self.assertTrue(result['reused'])
        self.assertFalse(result['is_stale'])
        self.assert_fixed(result, TEXT + ' 개정 안내.')
        self.assertEqual(self.snapshot(saved['run_id']), before)

    def test_fixed_saved_catalog_scope_and_completed_filter(self):
        saved = self.saved()
        self.complete_course()
        newer = self.saved(refresh=True)
        self.assertNotIn(DB_COURSE, [c['course_id'] for c in newer['recommended_courses']])
        self.client.patch(self.base, json={'expected_input_revision': self.revision(), 'changes': {'catalog_id': C2}})
        self.assert_fixed(self.client.get(f'{self.base}/roadmaps/{saved["run_id"]}').json())

    def test_fixed_goal_and_experience_independence_other_analysis_still_works(self):
        first = self.saved()
        self.client.patch(self.base, json={'expected_input_revision': self.revision(), 'changes': {'career_goal': '웹 개발', 'target_role': '개발자'}})
        self.doc()
        with patch('services.project_experience.extract_project_experiences', side_effect=fake_extraction) as extraction:
            item = self.analyze()['experiences'][0]
        extraction.assert_called()
        self.answer(item, 'confirmed')
        self.jobs()
        self.assert_fixed(self.saved())
        self.assertEqual(first['course_reasons'], self.saved()['course_reasons'])


if __name__ == '__main__':
    suite = unittest.TestSuite(FixedReasonAPI(name) for name in unittest.defaultTestLoader.getTestCaseNames(FixedReasonAPI) if name.startswith('test_fixed_'))
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
