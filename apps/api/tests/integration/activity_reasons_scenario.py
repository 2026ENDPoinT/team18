"""API/storage/real Gemini SDK adapter, with controlled transport and isolated DB."""
from contextlib import closing
from copy import deepcopy
import json
import os
from pathlib import Path
import threading
import time
import unittest
from unittest.mock import Mock, patch

from roadmap_scenario import RoadmapAPI, fake_extraction
from repositories.plans import connect
from repositories.roadmaps import RoadmapRepository

BODY = '기후 공공데이터를 분석하고 시각화 결과를 제출합니다.'
ITEM = {'id': 'climate', 'source': 'contestkorea', 'kind': 'competition',
        'title': '기후 공공데이터 AI 활용대회', 'category': '데이터 분석', 'host': '검증용 기관',
        'target': '대학생', 'period': '상시 접수', 'description_text': BODY,
        'url': 'https://example.org/climate'}


class ActivityReasonAPI(RoadmapAPI):
    def setUp(self):
        super().setUp()
        env = patch.dict(os.environ, {'GEMINI_API_KEY': 'synthetic-key', 'GEMINI_MODEL': 'test-activity-model',
            'ROADMAP_AI_COOLDOWN_SECONDS': '0', **{'ROADMAP_AI_' + key: '100000' for key in (
                'GUEST_HOURLY_UNITS', 'GUEST_DAILY_UNITS', 'USER_HOURLY_UNITS', 'USER_DAILY_UNITS', 'GLOBAL_DAILY_UNITS')}})
        env.start(); self.addCleanup(env.stop)
        self.items = [deepcopy(ITEM), {**ITEM, 'id': 'next', 'title': '기후 데이터 분석 아이디어 대회',
                                     'period': '2099.01.01 ~ 2099.02.01', 'url': 'https://example.org/next'},
                      {**ITEM, 'id': 'closed', 'period': '2000.01.01 ~ 2000.02.01'}]
        catalog = patch('api.routes.activities.load_contestkorea_catalog', side_effect=lambda *a, **kw:
                        (deepcopy(self.items), {'source': 'contestkorea', 'kind': 'competition', 'status': 'success', 'collected': len(self.items)}))
        catalog.start(); self.addCleanup(catalog.stop)
        self.sdk = Mock()
        self.sdk.models.generate_content.side_effect = self.reply
        sdk = patch('google.genai.Client', return_value=self.sdk)
        sdk.start(); self.addCleanup(sdk.stop)
        for name in ('services.gemini_roadmap.generate_roadmap', 'services.gemini_roadmap._generate',
                     'api.routes.job_skill_analysis.analyze_job_skills', 'services.project_experience.extract_project_experiences'):
            blocker = patch(name, side_effect=AssertionError('Unexpected analysis or execution roadmap AI'))
            spy = blocker.start(); self.addCleanup(blocker.stop); self.addCleanup(spy.assert_not_called)

    def reply(self, **kwargs):
        data = json.loads(kwargs['contents'])
        assert 'activities' in data  # No per-course or execution-roadmap call.
        reasons = []
        for activity in data['activities']:
            detail = next((e for e in activity['evidence'] if e['kind'] == 'detail'), None)
            subject = next(e['text'] for e in activity['evidence'] if e['id'] == 'title')
            anchor = detail or next(e for e in activity['evidence'] if e['id'] == 'title')
            refs = [{'evidence_id': anchor['id'], 'quote': anchor['text']}]
            sentences = [{'perspective': 'career', 'basis': 'inference', 'text': f"{subject}의 주제로 {data['career_goal']} 목표에 필요한 분석 방법을 연습해 볼 수 있습니다.",
                          'evidence': refs, 'experience_ids': []}]
            personal = [e for e in data['project_experiences'] if e.get('user_status') in ('confirmed', 'corrected') and e.get('contribution_scope') == 'personal']
            if personal:
                e = personal[0]
                activity_text = e['activity'].rstrip('.!?')
                sentences.append({'perspective': 'experience', 'basis': 'inference', 'text': f"확인한 {activity_text} 경험을 분석 과정에 활용해 볼 수 있습니다.",
                                  'evidence': refs, 'experience_ids': [e['id']]})
            sentences.append({'perspective': 'expected', 'basis': 'verified_fact' if detail else 'inference', 'text': ('공고에서 안내한 시각화 결과를 정리해 제출하는 경험을 쌓을 수 있습니다.' if detail else '공공데이터를 살펴보는 아이디어를 구상하고 분석한 내용을 설명하는 경험으로 확장할 수 있습니다.'),
                              'evidence': refs, 'experience_ids': []})
            reasons.append({'activity_id': activity['activity_id'], 'sentences': sentences})
        return Mock(text=json.dumps({'reasons': reasons}, ensure_ascii=False))

    def saved(self, refresh=False):
        response = self.make(refresh)
        self.assertIn(response.status_code, (200, 201), response.text)
        result = response.json()
        self.assertEqual(result['roadmap'], [])
        return result

    def change_goal(self, goal):
        response = self.client.patch(self.base, json={'expected_input_revision': self.revision(),
            'changes': {'career_goal': goal, 'target_role': '데이터 분석가'}})
        self.assertEqual(response.status_code, 200, response.text)

    def payloads(self):
        return [json.loads(c.kwargs['contents']) for c in self.sdk.models.generate_content.call_args_list]

    def test_activity_batch_cache_reads_and_preserved_selection(self):
        before = self.client.get(self.base + '/activities').json()['activities']
        self.sdk.models.generate_content.assert_not_called()
        first = self.saved()
        self.assertTrue(all(i['reason_source'] == 'gemini' for i in first['activity_recommendations']['activities']))
        items = first['activity_recommendations']['activities']
        self.assertEqual(len(items), 2)
        self.assertEqual({i['status'] for i in items}, {'open', 'upcoming'})
        self.assertTrue(all(i['reason_source'] == 'gemini' for i in items), items)
        for original, generated in zip(before, items):
            for key, value in original.items():
                if key not in ('personalization_reason', 'reason_source', 'reason_status', 'reason_evidence'):
                    self.assertEqual(value, generated[key], key)
        self.assertEqual(len(self.payloads()[0]['activities']), 2)
        self.assertEqual(self.sdk.models.generate_content.call_count, 1)
        with closing(connect()) as db:
            stored = RoadmapRepository(db).get(self.rid, first['run_id'])
        for _ in range(3):
            for path in ('/roadmap', f"/roadmaps/{first['run_id']}"):
                self.assertEqual(self.client.get(self.base + path).json()['activity_recommendations']['activities'], items)
            self.assertEqual(self.client.get(self.base + '/activities').json()['activities'], items)
        self.saved(); self.saved(refresh=True)
        self.assertEqual(self.sdk.models.generate_content.call_count, 1)
        self.items[0]['description_text'] += ' 결과 요약을 함께 제출합니다.'
        # A changed posting invalidates a still-fresh run and never returns stale cached prose on GET.
        read = self.client.get(self.base + '/activities').json()
        self.assertTrue(all(i['reason_source'] == 'fallback' for i in read['activities']))
        changed = self.saved()
        self.assertNotEqual(changed['run_id'], first['run_id'])
        self.assertEqual(self.sdk.models.generate_content.call_count, 2)
        with closing(connect()) as db:
            self.assertEqual(RoadmapRepository(db).get(self.rid, first['run_id']), stored)

    def test_activity_distinct_users_goals_and_projects(self):
        outputs = []
        for goal, project in [('스포츠 데이터 분석', '제가 Python으로 전처리 코드를 작성했습니다.'),
                              ('환경 데이터 분석', '제가 Python으로 전처리 코드를 작성했습니다.'),
                              ('스포츠 데이터 분석', '제가 Python으로 시각화 코드를 작성했습니다.')]:
            other = ActivityReasonAPI(); other.setUp()
            try:
                other.change_goal(goal); other.doc(project)
                with patch('services.project_experience.extract_project_experiences', side_effect=fake_extraction):
                    item = other.analyze()['experiences'][0]
                other.answer(item, 'confirmed')
                result = other.saved()['activity_recommendations']['activities'][0]
                self.assertEqual(result['reason_source'], 'gemini', result)
                outputs.append(result['personalization_reason'])
                self.assertIn(goal, outputs[-1])
                self.assertEqual(other.sdk.models.generate_content.call_count, 1)
            finally:
                other.doCleanups()
        self.assertEqual(len(set(outputs)), 3)

    def test_activity_corrections_comparison_and_existing_analysis_preserved(self):
        self.doc()
        with patch('services.project_experience.extract_project_experiences', side_effect=fake_extraction):
            item = self.analyze()['experiences'][0]
        self.answer(item, 'confirmed'); self.jobs(); self.sql_answer('no_experience')
        def analyses():
            with closing(connect()) as db:
                return {table: [dict(row) for row in db.execute(f'SELECT * FROM {table} WHERE request_id=?', (self.rid,)).fetchall()]
                        for table in ('project_experience_analyses', 'job_skill_snapshots')}
        before = analyses()
        first = self.saved()
        self.assertEqual(analyses(), before)
        data = self.payloads()[-1]
        self.assertNotIn('gap_skills', data)
        self.assertTrue(any(c['student_status'] == 'no_experience' for c in data['skill_comparison']))
        self.answer(item, 'corrected', {'skill_name': 'Excel', 'activity': 'Excel로 판매 데이터 분석', 'contribution_scope': 'personal'})
        second = self.saved()
        self.assertTrue(all(i['reason_source'] == 'gemini' for i in second['activity_recommendations']['activities']))
        self.assertEqual(self.payloads()[-1]['project_experiences'][0]['skill_name'], 'Excel')
        self.assertNotEqual(first['activity_recommendations']['activities'][0]['personalization_reason'], second['activity_recommendations']['activities'][0]['personalization_reason'])

    def test_activity_failures_are_not_success_cache_and_explicit_retry_recovers(self):
        from google.genai.errors import ServerError, ClientError
        failures = [ServerError(503, {'error': {'message': 'synthetic'}}),
                    ClientError(429, {'error': {'message': 'synthetic'}}), TimeoutError(),
                    Mock(text='not json'), Mock(text=json.dumps({'reasons': []}))]
        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                self.items[0]['description_text'] += ' 결과를 제출합니다.'
                self.sdk.models.generate_content.side_effect = failure if isinstance(failure, Exception) else lambda **kw: failure
                calls = self.sdk.models.generate_content.call_count
                result = self.saved(refresh=True)
                self.assertTrue(result['recommended_courses'])
                self.assertEqual(result['component_status']['activities'], 'success')
                items = result['activity_recommendations']['activities']
                self.assertEqual(len(items), 2)
                self.assertTrue(all(i['reason_source'] == 'fallback' for i in items))
                for _ in range(3):
                    self.assertEqual(self.client.get(self.base + '/activities').json()['activities'], items)
                    self.assertEqual(self.client.get(self.base + '/roadmap').json()['activity_recommendations']['activities'], items)
                self.assertEqual(self.sdk.models.generate_content.call_count, calls + 1)
                with closing(connect()) as db:
                    ledger = db.execute("SELECT status,result_json FROM ai_requests WHERE operation='activity_reasons' ORDER BY created_at DESC LIMIT 1").fetchone()
                    self.assertEqual(ledger['status'], 'failed')
                    from repositories.experience_analysis import decode
                    self.assertEqual(decode(ledger['result_json'])['source'], 'fallback')
                self.sdk.models.generate_content.side_effect = self.reply
                recovered = self.saved(refresh=True)['activity_recommendations']['activities']
                self.assertTrue(all(i['reason_source'] == 'gemini' for i in recovered))
                self.assertEqual(self.sdk.models.generate_content.call_count, calls + 2)
                self.saved(refresh=True)
                self.assertEqual(self.sdk.models.generate_content.call_count, calls + 2)

    def test_activity_concurrent_generations_share_one_batch(self):
        entered, release = threading.Event(), threading.Event()
        def held(**kwargs):
            entered.set()
            if not release.wait(8): raise TimeoutError()
            return self.reply(**kwargs)
        self.sdk.models.generate_content.side_effect = held
        body = {'expected_input_revision': self.revision(), 'refresh': True, 'background': True}
        try:
            started = self.client.post(self.base + '/roadmap', json=body).json()
            self.assertTrue(entered.wait(5))
            for _ in range(3):
                self.assertEqual(self.client.post(self.base + '/roadmap', json=body).json()['run_id'], started['run_id'])
        finally:
            release.set()
        for _ in range(100):
            result = self.client.get(f"{self.base}/roadmaps/{started['run_id']}").json()
            if result.get('generation_complete'): break
            time.sleep(.02)
        self.assertTrue(result.get('generation_complete'), result)
        self.assertEqual(self.sdk.models.generate_content.call_count, 1)
        self.assertTrue(all(i['reason_source'] == 'gemini' for i in result['activity_recommendations']['activities']))

    def test_activity_metadata_only_calls_gemini_and_survives_reads(self):
        for item in self.items: item.pop('description_text')
        result = self.saved()
        self.assertEqual(len(result['activity_recommendations']['activities']), 2)
        self.assertEqual(self.sdk.models.generate_content.call_count, 1)
        items = result['activity_recommendations']['activities']
        self.assertTrue(all(i['reason_source'] == 'gemini' and i['reason_evidence_level'] == 'metadata_inference' for i in items))
        self.assertEqual(len({i['personalization_reason'] for i in items}), 2)
        self.assertEqual(self.client.get(self.base + '/activities').json()['activities'], items)
        self.saved(refresh=True)
        self.assertEqual(self.sdk.models.generate_content.call_count, 1)

    def test_activity_partial_evidence_and_invalid_cached_response(self):
        self.items[1].pop('description_text')
        first = self.saved()
        items = {i['id']: i for i in first['activity_recommendations']['activities']}
        self.assertEqual(items['climate']['reason_source'], 'gemini')
        self.assertEqual(items['next']['reason_source'], 'gemini')
        self.assertEqual(items['next']['reason_evidence_level'], 'metadata_inference')
        self.assertEqual(len(self.payloads()[0]['activities']), 2)
        with closing(connect()) as db:
            owner = db.execute('SELECT owner_id FROM roadmap_inputs WHERE request_id=?', (self.rid,)).fetchone()['owner_id']
            db.execute("UPDATE ai_requests SET result_json=? WHERE owner_id=? AND operation='activity_reasons'",
                       (json.dumps({'source': 'gemini', 'reasons': [{'activity_id': 'foreign', 'host': 'invented'}]}), owner))
            db.commit()
        read = self.client.get(self.base + '/activities').json()
        self.assertTrue(all(i['reason_source'] == 'fallback' for i in read['activities']))
        self.assertEqual(self.sdk.models.generate_content.call_count, 1)
        result = self.saved(refresh=True)
        self.assertTrue(all(i['reason_source'] == 'gemini' for i in result['activity_recommendations']['activities']))
        self.assertTrue(all(i['host'] == ITEM['host'] for i in result['activity_recommendations']['activities']))
        self.assertEqual(self.sdk.models.generate_content.call_count, 2)

    def test_activity_requested_cases_persist_paragraph_and_evidence(self):
        from repositories.experience_analysis import decode
        from services.project_experience_schemas import DocumentExperience
        cases = json.loads((Path(__file__).parents[1] / 'fixtures/activity_reason_cases.json').read_text())
        outputs = []
        for case in cases:
            with self.subTest(case=case['case']):
                other = ActivityReasonAPI(); other.setUp()
                try:
                    profile = case['profile']
                    other.client.patch(other.base, json={'expected_input_revision': other.revision(),
                        'changes': {k: profile[k] for k in ('career_goal', 'target_role')}}).raise_for_status()
                    other.items = [case['item']]
                    if profile['project_experiences']:
                        exp = profile['project_experiences'][0]
                        other.doc('제가 ' + exp['activity'])
                        def extraction(document):
                            return DocumentExperience(document_id=document['document_id'],
                                extraction_revision=document['extraction_revision'], experiences=[{
                                    'skill_name': exp['skill_name'], 'category': 'other', 'activity': exp['activity'],
                                    'contribution_scope': 'personal', 'evidence_text': document['extracted_text']}])
                        with patch('services.project_experience.extract_project_experiences', side_effect=extraction):
                            experiences = other.analyze()['experiences']
                        self.assertEqual(len(experiences), 1)
                        if experiences[0]['contribution_scope'] == 'personal':
                            other.answer(experiences[0], 'confirmed')
                        else:
                            # A user correction explicitly establishes personal scope;
                            # a generic confirmed answer never upgrades unknown scope.
                            other.answer(experiences[0], 'corrected', {k: exp[k] for k in
                                ('skill_name', 'activity', 'contribution_scope')})
                    other.sdk.models.generate_content.side_effect = lambda **kw: Mock(text=json.dumps(case['response'], ensure_ascii=False))
                    before = other.client.get(other.base + '/activities').json()['activities']
                    saved = other.saved()
                    activity = saved['activity_recommendations']['activities'][0]
                    self.assertEqual(activity['score'], before[0]['score'])
                    self.assertEqual(activity['id'], before[0]['id'])
                    expected_calls = 1
                    self.assertEqual(other.sdk.models.generate_content.call_count, expected_calls)
                    self.assertEqual(activity['reason_source'], 'gemini' if expected_calls else 'fallback')
                    self.assertEqual(activity['reason_status'], 'generated' if expected_calls else 'needs_verification')
                    if expected_calls:
                        self.assertEqual(activity['reason_evidence'], case['response']['reasons'][0]['sentences'])
                        outputs.append(activity['personalization_reason'])
                    with closing(connect()) as db:
                        row = RoadmapRepository(db).get(other.rid, saved['run_id'])
                        self.assertEqual(decode(row['result_json'])['activity_recommendations']['activities'][0], activity)
                        owner = db.execute('SELECT owner_id FROM roadmap_inputs WHERE request_id=?', (other.rid,)).fetchone()['owner_id']
                        cache = db.execute("SELECT result_json, units FROM ai_requests WHERE owner_id=? AND operation='activity_reasons'", (owner,)).fetchall()
                        self.assertEqual(len(cache), expected_calls)
                        if cache:
                            self.assertEqual(cache[0]['units'], 1)
                            self.assertEqual(decode(cache[0]['result_json'])['reasons'], case['response']['reasons'])
                    for _ in range(2):
                        self.assertEqual(other.client.get(other.base + '/activities').json()['activities'][0], activity)
                        self.assertEqual(other.client.get(other.base + '/roadmap').json()['activity_recommendations']['activities'][0], activity)
                    self.assertEqual(other.sdk.models.generate_content.call_count, expected_calls)
                finally:
                    other.doCleanups()
        self.assertEqual(len(set(outputs)), 5)

    def test_activity_one_nonmodal_reason_keeps_other_verified_reasons(self):
        def mixed(**kwargs):
            response = json.loads(self.reply(**kwargs).text)
            first = response['reasons'][0]
            first['sentences'][0]['text'] = first['sentences'][0]['text'].replace('연습해 볼 수 있습니다.', '연습합니다.')
            return Mock(text=json.dumps(response, ensure_ascii=False))

        self.sdk.models.generate_content.side_effect = mixed
        saved = self.saved()['activity_recommendations']
        self.assertEqual(saved['activity_reasons_error'], 'gemini_invalid_response')
        self.assertCountEqual([item['reason_status'] for item in saved['activities']], ['generated', 'generation_failed'])
        for item in saved['activities']:
            self.assertEqual(bool(item['reason_evidence']), item['reason_status'] == 'generated')
        self.assertEqual(self.client.get(self.base + '/activities').json()['activities'], saved['activities'])
        with patch.dict(os.environ, {'ROADMAP_AI_COOLDOWN_SECONDS': '60'}):
            during_cooldown = self.saved(refresh=True)['activity_recommendations']
            self.assertEqual(during_cooldown['activities'], saved['activities'])
        self.assertEqual(self.sdk.models.generate_content.call_count, 1)
        self.sdk.models.generate_content.side_effect = self.reply
        repaired = self.saved(refresh=True)['activity_recommendations']
        self.assertIsNone(repaired['activity_reasons_error'])
        self.assertTrue(all(item['reason_status'] == 'generated' for item in repaired['activities']))
        self.assertEqual(self.sdk.models.generate_content.call_count, 2)

    def test_activity_empty_response_is_failed_and_retryable(self):
        self.items = [deepcopy(ITEM)]
        abstention = {'reasons': [{'activity_id': 'contestkorea:climate', 'sentences': []}]}
        self.sdk.models.generate_content.side_effect = lambda **kw: Mock(text=json.dumps(abstention))
        result = self.saved()['activity_recommendations']['activities'][0]
        self.assertEqual(result['reason_source'], 'fallback')
        self.assertEqual(result['reason_status'], 'generation_failed')
        self.assertEqual(result['reason_evidence'], [])
        self.assertEqual(self.client.get(self.base + '/activities').json()['activities'][0], result)
        self.sdk.models.generate_content.side_effect = self.reply
        self.assertEqual(self.saved(refresh=True)['activity_recommendations']['activities'][0]['reason_source'], 'gemini')
        self.assertEqual(self.sdk.models.generate_content.call_count, 2)

    def test_activity_budget_limit_preserves_candidates_without_provider_call(self):
        with patch.dict(os.environ, {'ROADMAP_AI_GLOBAL_DAILY_UNITS': '0'}):
            result = self.saved()['activity_recommendations']
        self.assertEqual(len(result['activities']), 2)
        self.assertEqual(result['activity_reasons_error'], 'ai_budget_exceeded')
        self.assertTrue(all(a['reason_status'] == 'generation_failed' for a in result['activities']))
        self.assertEqual(self.client.get(self.base + '/activities').json()['activities'], result['activities'])
        self.assertEqual(self.client.get(self.base + '/roadmap').json()['activity_recommendations']['activities'], result['activities'])
        self.sdk.models.generate_content.assert_not_called()


if __name__ == '__main__':
    suite = unittest.TestSuite(ActivityReasonAPI(name) for name in unittest.defaultTestLoader.getTestCaseNames(ActivityReasonAPI) if name.startswith('test_activity_'))
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
