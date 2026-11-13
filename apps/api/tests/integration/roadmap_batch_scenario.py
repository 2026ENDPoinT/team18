"""Exercise the real API and SQLite transactions with controlled provider/catalog results."""
from contextlib import closing
import os
import threading
import time
import unittest
import uuid
from unittest.mock import patch

from roadmap_scenario import RoadmapAPI, fake_roadmap, fake_extraction, job_result
from config import DB_BACKEND
from repositories.experience_analysis import AnalysisRepository, decode
from repositories.plans import connect
from repositories.postgres import StorageUnavailable
from repositories.roadmaps import RoadmapRepository
from services import roadmap_batch
from api.domain import Problem

for name in ('GUEST_HOURLY_UNITS', 'GUEST_DAILY_UNITS', 'USER_HOURLY_UNITS', 'USER_DAILY_UNITS', 'GLOBAL_DAILY_UNITS'):
    os.environ['ROADMAP_AI_' + name] = '100000'
os.environ['ROADMAP_AI_COOLDOWN_SECONDS'] = '0'

class BatchAPI(RoadmapAPI):
    def setUp(self):
        super().setUp()
        source = {'status': 'success', 'kind': 'competition', 'collected': 0}
        for path in ('api.routes.activities.load_catalog', 'api.routes.activities.load_contestkorea_catalog'):
            mock = patch(path, return_value=([], source))
            mock.start(); self.addCleanup(mock.stop)
        model = patch('services.gemini_roadmap.generate_roadmap', side_effect=AssertionError('Unexpected roadmap AI'))
        self.model = model.start(); self.addCleanup(model.stop)
        reasons = patch('google.genai.Client', side_effect=AssertionError('Unexpected reason AI'))
        self.reasons = reasons.start(); self.addCleanup(reasons.stop)
        for path in ('services.gemini_roadmap._generate', 'services.gemini_jobs._generate'):
            blocked = patch(path, side_effect=AssertionError('Unexpected Gemini transport'))
            spy = blocked.start()
            self.addCleanup(blocked.stop)
            self.addCleanup(spy.assert_not_called)

    def start_batch(self, **kwargs):
        response = self.client.post(self.base + '/roadmap', json={
            'expected_input_revision': self.revision(), 'background': True, **kwargs})
        self.assertIn(response.status_code, (200, 202), response.text)
        return response.json()

    def detail(self, run_id):
        response = self.client.get(f'{self.base}/roadmaps/{run_id}')
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def until(self, predicate, timeout=10):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            value = predicate()
            if value:
                return value
            time.sleep(.02)
        self.fail('Timed out waiting for real server work')

    def terminal(self, run_id):
        return self.until(lambda: (data if (data := self.detail(run_id)).get('generation_complete') or data['status'] == 'failed' else None))

    def test_batch_completion_order_and_reentry(self):
        self.jobs()
        original = roadmap_batch._execute
        for slow in ('comparison', 'courses', 'activities'):
            with self.subTest(slowest=slow):
                gate, entered = threading.Event(), threading.Event()
                def controlled(task, *args):
                    if task == slow:
                        entered.set()
                        if not gate.wait(8): raise RuntimeError('test gate timed out')
                    return original(task, *args)
                with patch.object(roadmap_batch, '_execute', side_effect=controlled):
                    try:
                        created = self.start_batch(refresh=True)
                        run_id = created['run_id']
                        self.assertTrue(entered.wait(5))
                        def others_finished():
                            data = self.detail(run_id)
                            states = data['generation_tasks']
                            return data if all(states[k] == 'success' for k in ('comparison', 'courses', 'activities') if k != slow) else None
                        pending = self.until(others_finished)
                        self.assertEqual(pending['status'], 'generating')
                        self.assertEqual(pending['generation_tasks'][slow], 'running')
                        self.assertFalse(pending['generation_complete'])
                        self.assertNotIn('roadmap', pending)
                        # Another page/reload and duplicate click recover the same durable run.
                        latest = self.client.get(self.base + '/roadmap').json()
                        self.assertEqual(latest['latest_generation']['run_id'], run_id)
                        self.assertEqual(self.start_batch(refresh=True)['run_id'], run_id)
                    finally:
                        gate.set()
                    result = self.terminal(run_id)
                    self.assertTrue(result['generation_complete'], result)
                    self.assertTrue(all(state == 'success' for state in result['generation_tasks'].values()))
                    self.assertEqual(result['activity_recommendations']['activities'], [])
                    self.assertEqual(result['roadmap'], [])
                    self.assertEqual(len(result['course_reasons']), len(result['recommended_courses']))
                    self.assertEqual(result['run_id'], run_id)
        self.model.assert_not_called()

    def test_batch_keeps_verified_items_when_project_analysis_is_partial(self):
        self.doc()
        with patch('services.project_experience.extract_project_experiences', side_effect=fake_extraction):
            analyzed = self.analyze()
        self.assertTrue(analyzed['experiences'])
        with closing(connect()) as db:
            row = db.execute('SELECT * FROM project_experience_analyses WHERE request_id=?',
                             (self.rid,)).fetchone()
            result = decode(row['result_json'])
            result.update(status='partial', errors=[{'code': 'activity_not_in_evidence'}])
            db.execute('UPDATE project_experience_analyses SET result_json=? WHERE analysis_id=?',
                       (AnalysisRepository(db).encode(result), row['analysis_id']))
        self.jobs()
        completed = self.terminal(self.start_batch()['run_id'])
        self.assertTrue(completed['generation_complete'], completed)
        self.assertEqual(completed['status'], 'partial')
        self.assertEqual(completed['skill_comparison']['project_analysis']['status'], 'partial')
        self.assertTrue(completed['skill_comparison']['project_analysis']['experiences'])

    def test_batch_cached_result_requires_fresh_activity_snapshot(self):
        self.jobs()
        first = self.terminal(self.start_batch()['run_id'])
        self.assertTrue(first['generation_complete'])
        self.assertEqual(self.start_batch()['run_id'], first['run_id'])
        with closing(connect()) as db:
            store = RoadmapRepository(db)
            saved = decode(store.get(self.rid, first['run_id'])['result_json'])
            saved['activity_recommendations']['valid_until'] = '2020-01-01T00:00:00+00:00'
            db.execute('UPDATE roadmap_runs SET result_json=? WHERE run_id=?', (store.encode(saved), first['run_id']))
        second = self.start_batch()
        self.assertNotEqual(second['run_id'], first['run_id'])
        self.assertTrue(self.terminal(second['run_id'])['generation_complete'])

    def test_batch_unverified_commit_is_neither_exposed_nor_reused(self):
        self.jobs()
        finished = self.terminal(self.start_batch()['run_id'])
        run_id = finished['run_id']
        with closing(connect()) as db:
            store = RoadmapRepository(db)
            basis = decode(store.get(self.rid, run_id)['basis_json'])
            basis['_generation_work']['verified'] = False
            basis['_generation_work']['states']['roadmap'] = 'running'
            db.execute('UPDATE roadmap_runs SET basis_json=? WHERE run_id=?', (store.encode(basis), run_id))
            self.assertIsNone(store.reusable(self.rid, finished['basis_hash']))
        unverified = self.detail(run_id)
        self.assertFalse(unverified['generation_complete'])
        self.assertNotIn('roadmap', unverified)
        self.assertEqual(self.client.post(f'{self.base}/roadmaps/{run_id}/course-reasons', json={}).status_code, 409)
        self.assertEqual(self.start_batch(refresh=True)['run_id'], run_id)
        duplicate = self.make(refresh=True)
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(duplicate.json()['error'], 'generation_in_progress')

    def test_batch_storage_failure_and_retry(self):
        self.jobs()
        original = RoadmapRepository.finish
        calls = []
        def fail_first(store, *args):
            calls.append(1)
            if len(calls) == 1: raise StorageUnavailable('postgresql://secret PASSWORD document', 'sqlstate_08006')
            return original(store, *args)
        with patch.object(RoadmapRepository, 'finish', fail_first), self.assertLogs('services.roadmap_batch', level='ERROR') as logs:
            run_id = self.start_batch()['run_id']
            failed = self.terminal(run_id)
            self.assertEqual(failed['status'], 'failed')
            self.assertEqual(failed['generation_tasks']['roadmap'], 'failed')
            self.assertNotIn('roadmap', failed)
            self.assertEqual(self.start_batch(refresh=True, retry_run_id=run_id)['run_id'], run_id)
            result = self.terminal(run_id)
        self.assertTrue(result['generation_complete'], result)
        self.model.assert_not_called()
        self.reasons.assert_not_called()
        self.assertIn('sqlstate_08006', ''.join(logs.output))
        self.assertNotIn('PASSWORD', ''.join(logs.output))
        self.assertNotIn('document', ''.join(logs.output))
        with closing(connect()) as db:
            saved = RoadmapRepository(db).get(self.rid, run_id)
            self.assertEqual(decode(saved['result_json'])['activity_recommendations']['activities'], [])

    @unittest.skipUnless(DB_BACKEND == 'postgres', 'requires disposable real PostgreSQL')
    def test_batch_postgres_real_write_failure(self):
        self.jobs()
        # Only this synthetic run is rejected, and the trigger is removed afterward.
        with closing(connect()) as db:
            db.execute("""CREATE FUNCTION public.test_roadmap_write_failure() RETURNS trigger AS $$
                BEGIN RAISE EXCEPTION 'PRIVATE_DATABASE_MESSAGE'; END; $$ LANGUAGE plpgsql""")
            db.execute(f"""CREATE TRIGGER test_roadmap_write_failure BEFORE UPDATE OF result_json ON roadmap_runs
                FOR EACH ROW WHEN (NEW.request_id = '{self.rid}' AND NEW.result_json IS NOT NULL)
                EXECUTE FUNCTION public.test_roadmap_write_failure()""")
        try:
            with self.assertLogs('services.roadmap_batch', level='ERROR') as logs:
                run_id = self.start_batch()['run_id']
                failed = self.terminal(run_id)
            self.assertEqual(failed['status'], 'failed')
            self.assertEqual(failed['generation_tasks']['roadmap'], 'failed')
            self.assertIn('sqlstate_P0001', ''.join(logs.output))
            self.assertNotIn('PRIVATE_DATABASE_MESSAGE', ''.join(logs.output))
            with closing(connect()) as db:
                db.execute('DROP TRIGGER test_roadmap_write_failure ON roadmap_runs')
            self.assertEqual(self.start_batch(refresh=True, retry_run_id=run_id)['run_id'], run_id)
            self.assertTrue(self.terminal(run_id)['generation_complete'])
            self.model.assert_not_called()
        finally:
            with closing(connect()) as db:
                db.execute('DROP TRIGGER IF EXISTS test_roadmap_write_failure ON roadmap_runs')
                db.execute('DROP FUNCTION IF EXISTS public.test_roadmap_write_failure()')

    @unittest.skipUnless(DB_BACKEND == 'postgres', 'requires disposable real PostgreSQL')
    def test_batch_reads_saved_postgres_activity_candidates(self):
        from repositories.dacon import load_catalog as load_dacon
        from repositories.contestkorea import load_catalog as load_contestkorea
        self.jobs()
        event = {'id': 'synthetic-batch-event', 'kind': 'competition', 'source': 'contestkorea',
                 'title': '데이터 분석 공모전', 'category': '학문•과학•IT', 'target': '대학생',
                 'period': '상시 접수', 'host': '테스트', 'url': 'https://example.test/activity'}
        with closing(connect()) as db:
            store = RoadmapRepository(db)
            db.execute("""INSERT INTO activity_candidates(source,original_id,payload,state,first_seen_at,last_seen_at,last_success_at,next_check_at,check_status)
                VALUES ('contestkorea','synthetic-batch-event',?,'active',now(),now(),now(),now(),'success')""", (store.encode(event),))
            db.execute("""INSERT INTO dacon_collection_runs(id,collection_date,mode,status,started_at,finished_at,collected_count)
                VALUES (?,CURRENT_DATE,'manual','success',now(),now(),0)""", (str(uuid.uuid4()),))
        try:
            with patch('api.routes.activities.load_catalog', load_dacon), patch('api.routes.activities.load_contestkorea_catalog', load_contestkorea):
                result = self.terminal(self.start_batch()['run_id'])
            self.assertTrue(result['generation_complete'], result)
            self.assertEqual([item['id'] for item in result['activity_recommendations']['activities']], ['synthetic-batch-event'])
        finally:
            with closing(connect()) as db:
                db.execute("DELETE FROM activity_candidates WHERE source='contestkorea' AND original_id='synthetic-batch-event'")

    def test_batch_expired_run_cannot_complete_after_timeout(self):
        self.jobs()
        gate, entered = threading.Event(), threading.Event()
        original = roadmap_batch._execute
        def delayed(task, *args):
            if task == 'comparison':
                entered.set(); gate.wait(8)
            return original(task, *args)
        with patch.object(roadmap_batch, '_execute', side_effect=delayed):
            try:
                run_id = self.start_batch()['run_id']
                self.assertTrue(entered.wait(5))
                with closing(connect()) as db:
                    db.execute('UPDATE roadmap_runs SET lease_until=? WHERE run_id=?', ('2020-01-01T00:00:00+00:00', run_id))
                expired = self.detail(run_id)
                self.assertEqual(expired['status'], 'failed')
                self.assertTrue(expired['generation_expired'])
                self.assertFalse(expired['generation_complete'])
            finally:
                gate.set()
            time.sleep(.1)
            self.assertEqual(self.detail(run_id)['status'], 'failed')

    def assert_no_generation_ai(self):
        self.model.assert_not_called()
        self.reasons.assert_not_called()

    def test_batch_zero_gemini_with_and_without_saved_jobs(self):
        from contextlib import ExitStack
        with ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ, GEMINI_API_KEY='', GOOGLE_API_KEY=''))
            jobs = stack.enter_context(patch('api.routes.job_skill_analysis.job_skill_analysis', side_effect=AssertionError('Automatic job analysis')))
            transport = stack.enter_context(patch('services.gemini_jobs._generate', side_effect=AssertionError('Gemini transport')))
            for background in (False, True):
                response = self.client.post(self.base + '/roadmap', json={'expected_input_revision': self.revision(), 'background': background, 'refresh': True})
                self.assertIn(response.status_code, (201, 202), response.text)
                result = self.terminal(response.json()['run_id'])
                self.assertTrue(result['generation_complete'], result)
                self.assertEqual(result['status'], 'partial')
                self.assertEqual(result['generation_tasks']['comparison'], 'unavailable')
                self.assertEqual(result['skill_comparison']['job_analysis']['status'], 'not_started')
                self.assertTrue(result['recommended_courses'])
                self.assertEqual(result['roadmap'], [])
            jobs.assert_not_called(); transport.assert_not_called()
        self.jobs()  # Explicit user analysis is still supported.
        with patch('api.routes.job_skill_analysis.job_skill_analysis', side_effect=AssertionError('Automatic analysis')) as jobs, \
             patch('services.gemini_jobs._generate', side_effect=AssertionError('Gemini transport')) as transport:
            for background in (False, True):
                response = self.client.post(self.base + '/roadmap', json={'expected_input_revision': self.revision(), 'background': background, 'refresh': True})
                result = self.terminal(response.json()['run_id'])
                self.assertEqual(result['status'], 'success', result)
                self.assertEqual(result['roadmap'], [])
                self.assertEqual(result['model_name'], 'server-assembled-v1')
                for suffix in ('/roadmap', '/roadmaps', '/roadmaps/' + result['run_id']):
                    self.assertEqual(self.client.get(self.base + suffix).status_code, 200)
                reasons = self.client.post(f'{self.base}/roadmaps/{result["run_id"]}/course-reasons', json={}).json()
                self.assertEqual(reasons['reasons'], result['course_reasons'])
            jobs.assert_not_called(); transport.assert_not_called()
        self.assert_no_generation_ai()

    def test_batch_failed_sections_preserve_other_results(self):
        self.jobs()
        original = roadmap_batch._execute
        for broken in ('comparison', 'courses', 'activities'):
            with self.subTest(section=broken):
                def fail_section(task, *args):
                    if task == broken:
                        raise Problem(503, 'source_unavailable', 'synthetic failure')
                    return original(task, *args)
                with patch.object(roadmap_batch, '_execute', side_effect=fail_section):
                    result = self.terminal(self.start_batch(refresh=True)['run_id'])
                self.assertTrue(result['generation_complete'], result)
                self.assertEqual(result['status'], 'partial')
                self.assertEqual(result['component_status'][broken], 'failed')
                self.assertEqual(result['generation_tasks']['roadmap'], 'success')
                if broken != 'courses': self.assertTrue(result['recommended_courses'])
                if broken != 'comparison': self.assertTrue(result['skill_comparison']['job_analysis']['snapshot_id'])
        self.assert_no_generation_ai()

    def test_batch_no_catalog_is_unavailable_not_failed(self):
        self.client.patch(self.base, json={'expected_input_revision': self.revision(), 'changes': {'catalog_id': None}})
        result = self.terminal(self.start_batch()['run_id'])
        self.assertTrue(result['generation_complete'], result)
        self.assertEqual(result['component_status']['courses'], 'unavailable')
        self.assertEqual(result['recommended_courses'], [])
        self.assertEqual(result['course_reasons'], [])

    def test_batch_empty_success_and_failed_activity_source_are_distinct(self):
        self.jobs()
        empty = self.terminal(self.start_batch()['run_id'])
        self.assertEqual(empty['component_status']['activities'], 'success')
        self.assertEqual(empty['activity_recommendations']['activities'], [])
        with patch('api.routes.activities.load_catalog', return_value=([], {'status': 'error', 'collected': 0, 'kind': 'competition', 'error_code': 'source_failed'})):
            partial = self.terminal(self.start_batch(refresh=True)['run_id'])
        self.assertTrue(partial['generation_complete'], partial)
        self.assertEqual(partial['component_status']['activities'], 'partial')
        self.assertTrue(any(s['status'] == 'error' for s in partial['activity_recommendations']['sources']))
        with patch('api.routes.activities.load_catalog', side_effect=RuntimeError('source failed')):
            failed = self.terminal(self.start_batch(refresh=True)['run_id'])
        self.assertEqual(failed['component_status']['activities'], 'failed')
        self.assertEqual(failed['activity_recommendations']['status'], 'error')
        self.assertTrue(failed['recommended_courses'])

    def test_batch_reanalysis_preserves_input_versions_and_legacy_progress(self):
        from repositories.plans import Repository
        from services.roadmap_generation import capture_basis, model_input, validate_result
        self.jobs()
        with closing(connect()) as db:
            repo = Repository(db); repo.begin()
            basis = capture_basis(db, db.execute('SELECT * FROM roadmap_inputs WHERE request_id=?', (self.rid,)).fetchone())
            legacy = validate_result(fake_roadmap(model_input(basis)), basis)
            store = RoadmapRepository(db)
            old = store.create(self.rid, basis)
            store.finish(self.rid, old['run_id'], legacy)
            store.update_progress(old['run_id'], 'task-1', True, 0)
            db.commit()
            original = store.get(self.rid, old['run_id'])
        for _ in range(2):
            restored = self.detail(old['run_id'])
            self.assertTrue(restored['roadmap'])
            self.assertEqual(restored['progress']['completed'], 1)
        first = self.terminal(self.start_batch(refresh=True)['run_id'])
        self.client.patch(self.base, json={'expected_input_revision': self.revision(), 'changes': {'career_goal': 'SQL 데이터 분석'}})
        second = self.terminal(self.start_batch(refresh=True)['run_id'])
        self.assertGreater(second['input_revision'], first['input_revision'])
        self.assertNotEqual(second['run_id'], first['run_id'])
        self.assertEqual(len(self.client.get(self.base + '/roadmaps').json()['runs']), 3)
        with closing(connect()) as db:
            self.assertEqual(RoadmapRepository(db).get(self.rid, old['run_id']), original)
        self.assertEqual(self.detail(old['run_id'])['progress']['completed'], 1)
        self.assert_no_generation_ai()

    def test_batch_storage_integrity_failure_is_not_success(self):
        original = RoadmapRepository.finish
        def corrupt(store, rid, run_id, result):
            return original(store, rid, run_id, {**result, 'career_goal': 'corrupted'})
        with patch.object(RoadmapRepository, 'finish', corrupt):
            failed = self.terminal(self.start_batch()['run_id'])
        self.assertEqual(failed['status'], 'failed')
        self.assertFalse(failed['generation_complete'])
        self.assertEqual(failed['error_code'], 'storage_verification_failed')
        self.assertNotIn('recommended_courses', failed)

    def test_batch_sync_storage_failure_returns_http_error(self):
        with patch.object(RoadmapRepository, 'finish', side_effect=StorageUnavailable('synthetic', 'sqlstate_08006')):
            response = self.make()
        self.assertEqual(response.status_code, 503, response.text)
        latest = self.client.get(self.base + '/roadmap').json()
        self.assertEqual(latest['status'], 'failed')
        self.assertFalse(latest['generation_complete'])

    def test_batch_revision_race_never_commits_stale_success(self):
        original = roadmap_batch._execute
        def change(task, *args):
            value = original(task, *args)
            if task == 'courses':
                with closing(connect()) as db:
                    db.execute('UPDATE roadmap_inputs SET input_revision=input_revision+1 WHERE request_id=?', (self.rid,))
            return value
        with patch.object(roadmap_batch, '_execute', side_effect=change):
            failed = self.terminal(self.start_batch()['run_id'])
        self.assertEqual(failed['status'], 'failed')
        self.assertFalse(failed['generation_complete'])
        self.assertEqual(failed['error_code'], 'revision_conflict')


    def test_batch_old_job_snapshot_is_reused_without_automatic_upgrade(self):
        from services import project_experience as experience
        legacy = job_result()
        legacy.pop('analysis_version')
        legacy.update(career_goal='데이터 분석 분야', target_role='데이터 분석가')
        with patch.object(experience, 'JOB_VERSION', 'job-skills-v1'), \
             patch('api.routes.job_skill_analysis.analyze_job_skills', return_value=legacy):
            old = self.client.post(self.base + '/job-skill-analysis', json={}).json()
        with patch('api.routes.job_skill_analysis.job_skill_analysis', side_effect=AssertionError('Automatic analysis')) as ai:
            result = self.terminal(self.start_batch()['run_id'])
            self.assertTrue(result['generation_complete'], result)
            self.assertEqual(result['status'], 'partial')
            self.assertEqual(result['skill_comparison']['job_analysis']['snapshot_id'], old['snapshot_id'])
            self.assertTrue(result['skill_comparison']['job_analysis']['previous_analysis_version'])
            ai.assert_not_called()
        upgraded, calls = self.jobs()
        self.assertEqual(calls, 1)
        self.assertNotEqual(upgraded['snapshot_id'], old['snapshot_id'])
        with closing(connect()) as db:
            self.assertIn(old['snapshot_id'], [row['snapshot_id'] for row in AnalysisRepository(db).job_history(self.rid)])
        self.assertEqual(self.detail(result['run_id'])['skill_comparison']['job_analysis']['snapshot_id'], old['snapshot_id'])


if __name__ == '__main__':
    suite = unittest.TestSuite(BatchAPI(name) for name in unittest.defaultTestLoader.getTestCaseNames(BatchAPI) if name.startswith('test_batch_'))
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
