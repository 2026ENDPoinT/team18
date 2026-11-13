"""Real API/DB/SDK adapter with a controlled Gemini transport, never live credentials."""
from contextlib import closing
import json
import os
import threading
import time
import unittest
from unittest.mock import Mock, patch

from roadmap_scenario import RoadmapAPI, C, U, DB_COURSE, fake_extraction
from repositories.plans import connect
from repositories.roadmaps import RoadmapRepository
from repositories.postgres import StorageUnavailable

DESCRIPTION = 'SQL을 이용한 데이터 조회와 집계, 데이터 저장 및 관리 개념을 학습한다.'
SECOND = 'reason-test-query'


class ReasonAPI(RoadmapAPI):
    def setUp(self):
        super().setUp()
        env = patch.dict(os.environ, {'GEMINI_API_KEY': 'synthetic-key', 'GEMINI_MODEL': 'test-reasons-model',
            'ROADMAP_AI_COOLDOWN_SECONDS': '0', **{'ROADMAP_AI_' + key: '100000' for key in (
                'GUEST_HOURLY_UNITS', 'GUEST_DAILY_UNITS', 'USER_HOURLY_UNITS', 'USER_DAILY_UNITS', 'GLOBAL_DAILY_UNITS')}})
        env.start(); self.addCleanup(env.stop)
        self.sdk = Mock()
        self.sdk.models.generate_content.side_effect = self.reply
        sdk = patch('google.genai.Client', return_value=self.sdk)
        sdk.start(); self.addCleanup(sdk.stop)
        for path in ('services.gemini_roadmap.generate_roadmap', 'services.gemini_roadmap._generate',
                     'api.routes.job_skill_analysis.analyze_job_skills', 'services.project_experience.extract_project_experiences'):
            blocked = patch(path, side_effect=AssertionError('Unexpected analysis or execution roadmap AI'))
            spy = blocked.start(); self.addCleanup(blocked.stop); self.addCleanup(spy.assert_not_called)
        with closing(connect()) as db:
            db.execute('INSERT INTO courses(course_id,university_id,canonical_name) VALUES(?,?,?) ON CONFLICT DO NOTHING', (SECOND, U, 'SQL 활용'))
            db.execute('INSERT INTO catalog_courses(catalog_id,course_id,course_name) VALUES(?,?,?) ON CONFLICT DO NOTHING', (C, SECOND, 'SQL 활용'))
            for cid in (DB_COURSE, SECOND):
                db.execute('UPDATE catalog_courses SET description_text=? WHERE catalog_id=? AND course_id=?', (DESCRIPTION, C, cid))
                db.execute('INSERT INTO catalog_course_keywords(catalog_id,course_id,keyword,keyword_role,evidence_text) VALUES(?,?,?,?,?) ON CONFLICT DO NOTHING', (C, cid, 'SQL', 'learning', DESCRIPTION))
            db.commit()

    def reply(self, **kwargs):
        data = json.loads(kwargs['contents'])
        # Contract fixture, not a claim of live model quality.
        first = f"{data['target_role']}라는 희망 직무와 {data['career_goal']} 목표에 데이터 조회·집계 학습을 연결할 수 있습니다."
        experiences = data['project_experiences']
        second = (f"확인한 {experiences[0]['activity']} 경험을 데이터 저장·관리를 활용하는 방향으로 확장하는 데 도움이 됩니다."
                  if experiences else '데이터 저장·관리 개념을 학습할 후보로 살펴볼 수 있습니다.')
        return Mock(text=json.dumps({'reasons': [{'course_id': c['course_id'],
            'personalization_reason': first + ' ' + second, 'evidence_ids': [c['evidence'][0]['id']]}
            for c in data['courses']]}, ensure_ascii=False))

    def saved(self, refresh=False):
        response = self.make(refresh)
        self.assertIn(response.status_code, (200, 201), response.text)
        return response.json()

    def payloads(self):
        return [json.loads(call.kwargs['contents']) for call in self.sdk.models.generate_content.call_args_list]

    def change_goal(self, goal, role):
        response = self.client.patch(self.base, json={'expected_input_revision': self.revision(),
            'changes': {'career_goal': goal, 'target_role': role}})
        self.assertEqual(response.status_code, 200, response.text)

    def test_reasons_batch_cache_refresh_completed_and_immutable_history(self):
        first = self.saved()
        self.assertEqual(first['course_reasons_source'], 'gemini')
        self.assertEqual(len(first['recommended_courses']), 2)
        self.assertEqual(self.sdk.models.generate_content.call_count, 1)
        self.assertEqual(len(self.payloads()[0]['courses']), 2)
        self.assertEqual(first['roadmap'], [])
        path = f'{self.base}/roadmaps/{first["run_id"]}'
        with closing(connect()) as db:
            before = RoadmapRepository(db).get(self.rid, first['run_id'])
        self.sdk.models.generate_content.side_effect = TimeoutError('provider now unavailable')
        for _ in range(3):
            self.assertEqual(self.client.get(path).json()['course_reasons'], first['course_reasons'])
            self.assertEqual(self.client.get(self.base + '/roadmap').json()['course_reasons'], first['course_reasons'])
            self.assertEqual(self.client.post(path + '/course-reasons', json={}).json()['provider'], 'gemini')
        self.saved(); self.saved(refresh=True)
        self.assertEqual(self.sdk.models.generate_content.call_count, 1)
        self.sdk.models.generate_content.side_effect = self.reply
        self.complete_course()
        changed = self.saved(refresh=True)
        self.assertNotIn(DB_COURSE, [c['course_id'] for c in changed['recommended_courses']])
        self.assertIn(DB_COURSE, [c['course_id'] for c in self.payloads()[-1]['completed_courses']])
        self.assertEqual(self.sdk.models.generate_content.call_count, 2)
        with closing(connect()) as db:
            self.assertEqual(RoadmapRepository(db).get(self.rid, first['run_id']), before)

    def test_reasons_three_users_receive_different_grounded_context(self):
        reasons, owners = [], set()
        for role, goal in [('데이터 분석가', '고객 구매 데이터 분석'), ('백엔드 개발자', '주문 데이터 관리'), ('데이터 엔지니어', '데이터 집계 파이프라인')]:
            other = ReasonAPI(); other.setUp()
            try:
                other.change_goal(goal, role)
                result = other.saved()
                reason = next(r['personalization_reason'] for r in result['course_reasons'] if r['course_id'] == DB_COURSE)
                reasons.append(reason)
                self.assertIn(role, reason)
                self.assertIn(goal, other.payloads()[-1]['career_goal'])
                self.assertEqual(other.payloads()[-1]['courses'][0]['evidence'][0]['text'], DESCRIPTION)
                self.assertEqual(other.sdk.models.generate_content.call_count, 1)
                with closing(connect()) as db:
                    owners.add(db.execute('SELECT owner_id FROM roadmap_inputs WHERE request_id=?', (other.rid,)).fetchone()['owner_id'])
            finally:
                other.doCleanups()
        self.assertEqual(len(set(reasons)), 3)
        self.assertEqual(len(owners), 3)

    def test_reasons_two_users_same_goal_different_projects(self):
        reasons = []
        for project in ('제가 Python으로 전처리 코드를 작성했습니다.', '제가 React로 화면을 개발했습니다.'):
            other = ReasonAPI(); other.setUp()
            try:
                other.doc(project)
                with patch('services.project_experience.extract_project_experiences', side_effect=fake_extraction):
                    item = other.analyze()['experiences'][0]
                other.answer(item, 'confirmed')
                result = other.saved()
                reasons.append(next(r['personalization_reason'] for r in result['course_reasons'] if r['course_id'] == DB_COURSE))
                self.assertEqual(other.payloads()[-1]['career_goal'], '데이터 분석 분야')
            finally:
                other.doCleanups()
        self.assertNotEqual(*reasons)

    def test_reasons_concurrent_generation_shares_one_batch(self):
        entered, release = threading.Event(), threading.Event()
        def held(**kwargs):
            entered.set()
            if not release.wait(8):
                raise TimeoutError()
            return self.reply(**kwargs)
        self.sdk.models.generate_content.side_effect = held
        body = {'expected_input_revision': self.revision(), 'background': True, 'refresh': True}
        try:
            started = self.client.post(self.base + '/roadmap', json=body)
            self.assertEqual(started.status_code, 202, started.text)
            run_id = started.json()['run_id']
            self.assertTrue(entered.wait(5))
            for _ in range(3):
                duplicate = self.client.post(self.base + '/roadmap', json=body)
                self.assertEqual(duplicate.json()['run_id'], run_id)
            self.assertEqual(self.sdk.models.generate_content.call_count, 1)
        finally:
            release.set()
        for _ in range(100):
            result = self.client.get(f'{self.base}/roadmaps/{run_id}').json()
            if result.get('generation_complete'):
                break
            time.sleep(.02)
        self.assertTrue(result.get('generation_complete'), result)
        self.assertEqual(result['course_reasons_source'], 'gemini')

    def test_reasons_same_goal_different_confirmed_and_corrected_experience(self):
        self.doc()
        with patch('services.project_experience.extract_project_experiences', side_effect=fake_extraction):
            item = self.analyze()['experiences'][0]
        self.answer(item, 'confirmed')
        first = self.saved()
        self.assertEqual(self.payloads()[-1]['project_experiences'][0]['skill_name'], 'Python')
        # Experiences remain available even without any job analysis snapshot.
        self.assertFalse(self.payloads()[-1]['skill_comparison'])
        self.answer(item, 'corrected', {'skill_name': 'Excel', 'activity': 'Excel로 판매 집계표 작성', 'contribution_scope': 'personal'})
        second = self.saved()
        self.assertNotEqual(first['course_reasons'], second['course_reasons'])
        self.assertEqual(self.payloads()[-1]['project_experiences'][0]['skill_name'], 'Excel')
        self.assertEqual(self.sdk.models.generate_content.call_count, 2)
        self.jobs(); self.sql_answer('no_experience')
        self.saved()
        self.assertEqual(next(s for s in self.payloads()[-1]['skill_comparison'] if s['skill_name'] == 'SQL')['student_status'], 'no_experience')

    def test_reasons_provider_errors_preserve_candidates_and_cache_fallback(self):
        from google.genai.errors import ServerError, ClientError
        failures = [ServerError(503, {'error': {'message': 'synthetic'}}),
                    ClientError(429, {'error': {'message': 'synthetic'}}), TimeoutError(),
                    Mock(text='not json'), Mock(text=json.dumps({'reasons': []}))]
        for i, failure in enumerate(failures):
            with self.subTest(failure=i):
                self.change_goal(f'분석 목표 {i}', '데이터 분석가')
                self.sdk.models.generate_content.side_effect = failure if isinstance(failure, Exception) else None
                self.sdk.models.generate_content.return_value = failure
                before = self.sdk.models.generate_content.call_count
                result = self.saved()
                self.assertEqual(len(result['recommended_courses']), 2)
                self.assertTrue(result['generation_complete'])
                self.assertEqual(result['course_reasons_source'], 'catalog_evidence_fallback')
                self.assertIsNotNone(result['course_reasons_error'])
                self.assertEqual(result['course_reasons'][0]['personalization_reason'], result['recommended_courses'][0]['reason'])
                self.saved(refresh=True)
                self.assertEqual(self.sdk.models.generate_content.call_count, before + 1)

    def test_reasons_budget_limit_keeps_catalog_candidates(self):
        with patch.dict(os.environ, {'ROADMAP_AI_GLOBAL_DAILY_UNITS': '0'}):
            result = self.saved()
        self.assertEqual(result['course_reasons_error'], 'ai_budget_exceeded')
        self.assertEqual(len(result['recommended_courses']), 2)
        self.sdk.models.generate_content.assert_not_called()

    def test_reasons_cache_and_result_storage_errors_are_not_ai_fallback(self):
        for path in ('services.ai_guard.guarded_call', 'repositories.roadmaps.RoadmapRepository.finish'):
            with self.subTest(path=path), patch(path, side_effect=StorageUnavailable('synthetic', 'sqlstate_08006')):
                response = self.make(refresh=True)
            self.assertEqual(response.status_code, 503, response.text)
            latest = self.client.get(self.base + '/roadmap').json()
            self.assertEqual(latest['latest_generation']['status'], 'failed')
            self.assertEqual(latest['latest_generation']['generation_error']['code'], 'sqlstate_08006')
        calls = self.sdk.models.generate_content.call_count
        self.assertEqual(self.saved(refresh=True)['course_reasons_source'], 'gemini')
        self.assertEqual(self.sdk.models.generate_content.call_count, calls, 'committed reason cache survives a result-save failure')

    def test_reasons_corrupt_cache_is_rejected_without_repeat_provider_call(self):
        self.saved()
        with closing(connect()) as db:
            owner = db.execute('SELECT owner_id FROM roadmap_inputs WHERE request_id=?', (self.rid,)).fetchone()['owner_id']
            invalid = {'source': 'gemini', 'reasons': [{'course_id': 'foreign', 'personalization_reason': 'fake', 'evidence_ids': []}]}
            db.execute("UPDATE ai_requests SET result_json=? WHERE owner_id=? AND operation='course_reasons'", (RoadmapRepository(db).encode(invalid), owner))
            db.commit()
        result = self.saved(refresh=True)
        self.assertEqual(result['course_reasons_source'], 'catalog_evidence_fallback')
        self.assertEqual(len(result['recommended_courses']), 2)
        self.assertEqual(self.sdk.models.generate_content.call_count, 1)


if __name__ == '__main__':
    suite = unittest.TestSuite(ReasonAPI(name) for name in unittest.defaultTestLoader.getTestCaseNames(ReasonAPI) if name.startswith('test_reasons_'))
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
