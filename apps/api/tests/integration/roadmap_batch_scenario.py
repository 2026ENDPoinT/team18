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
from repositories.experience_analysis import decode
from repositories.plans import connect
from repositories.postgres import StorageUnavailable
from repositories.roadmaps import RoadmapRepository
from services import roadmap_batch
from services.gemini import GeminiError

for name in ('GUEST_HOURLY_UNITS', 'GUEST_DAILY_UNITS', 'USER_HOURLY_UNITS', 'USER_DAILY_UNITS', 'GLOBAL_DAILY_UNITS'):
    os.environ['ROADMAP_AI_' + name] = '100000'
os.environ['ROADMAP_AI_COOLDOWN_SECONDS'] = '0'


def fake_reasons(data):
    return {'reasons': [{'course_id': course['course_id'], 'personalization_reason': '과목명과 목표의 연결을 확인해 볼 후보입니다.',
                         'evidence_ids': [course['evidence'][0]['id']] if course['evidence'] else []}
                        for course in data['courses']]}


class BatchAPI(RoadmapAPI):
    def setUp(self):
        super().setUp()
        source = {'status': 'success', 'kind': 'competition', 'collected': 0}
        for path in ('api.routes.activities.load_catalog', 'api.routes.activities.load_contestkorea_catalog'):
            mock = patch(path, return_value=([], source))
            mock.start(); self.addCleanup(mock.stop)
        model = patch('api.routes.roadmaps.generate_roadmap', side_effect=fake_roadmap)
        self.model = model.start(); self.addCleanup(model.stop)
        reasons = patch('services.roadmap_batch.generate_course_reasons', side_effect=fake_reasons)
        self.reasons = reasons.start(); self.addCleanup(reasons.stop)

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
                    self.assertTrue(result['roadmap'])
                    self.assertEqual(len(result['course_reasons']), len(result['recommended_courses']))
                    self.assertEqual(result['run_id'], run_id)
        self.assertEqual(self.model.call_count, 3)

    def test_batch_no_courses_and_automatic_job_analysis(self):
        self.complete_course()
        with patch('api.routes.job_skill_analysis.analyze_job_skills', return_value=job_result()) as jobs:
            result = self.terminal(self.start_batch()['run_id'])
        self.assertTrue(result['generation_complete'], result)
        self.assertEqual(result['recommended_courses'], [])
        self.assertEqual(result['activity_recommendations']['activities'], [])
        self.assertEqual(jobs.call_count, 1)
        self.assertEqual(self.reasons.call_count, 0)

    def test_batch_reason_failure_blocks_and_retry_reuses_ranked_courses_and_roadmap(self):
        self.jobs()
        self.reasons.side_effect = [GeminiError('gemini_timeout', 'synthetic timeout'), fake_reasons({
            'courses': [{'course_id': 'roadmap-test-database', 'evidence': []}]})]
        run_id = self.start_batch()['run_id']
        failed = self.terminal(run_id)
        self.assertEqual(failed['status'], 'failed')
        self.assertEqual(failed['generation_tasks']['courses'], 'failed')
        self.assertNotIn('roadmap', failed)
        self.assertEqual(self.start_batch(refresh=True, retry_run_id=run_id)['run_id'], run_id)
        done = self.terminal(run_id)
        self.assertTrue(done['generation_complete'], done)
        self.assertEqual(done['course_reasons'][0]['course_id'], done['recommended_courses'][0]['course_id'])
        self.assertEqual(self.model.call_count, 1)
        self.assertEqual(self.reasons.call_count, 2)

    def test_batch_course_reasons_wait_for_roadmap_ai_guard(self):
        self.jobs()
        gate, entered = threading.Event(), threading.Event()
        def slow_roadmap(data):
            entered.set()
            if not gate.wait(8): raise RuntimeError('test gate timed out')
            return fake_roadmap(data)
        self.model.side_effect = slow_roadmap
        try:
            run_id = self.start_batch()['run_id']
            self.assertTrue(entered.wait(5))
            pending = self.until(lambda: (data if (data := self.detail(run_id))['generation_tasks']['activities'] == 'success'
                                            and data['generation_tasks']['comparison'] == 'success' else None))
            self.assertEqual(pending['generation_tasks']['courses'], 'running')
            self.assertFalse(pending['generation_complete'])
            self.assertEqual(self.reasons.call_count, 0)
        finally:
            gate.set()
        self.assertTrue(self.terminal(run_id)['generation_complete'])
        self.assertEqual(self.reasons.call_count, 1)

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
        self.assertEqual(self.start_batch(refresh=True)['run_id'], run_id)
        duplicate = self.make(refresh=True)
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(duplicate.json()['error'], 'generation_in_progress')

    def test_batch_failed_activity_and_retry_reuses_success(self):
        self.jobs()
        original = roadmap_batch._execute
        counts = {key: 0 for key in roadmap_batch.TASKS}
        def fail_once(task, *args):
            counts[task] += 1
            if task == 'activities' and counts[task] == 1:
                raise RuntimeError('PRIVATE_CONTENT_DO_NOT_LOG')
            return original(task, *args)
        with patch.object(roadmap_batch, '_execute', side_effect=fail_once):
            run_id = self.start_batch()['run_id']
            failed = self.terminal(run_id)
            self.assertEqual(failed['status'], 'failed')
            self.assertFalse(failed['generation_complete'])
            self.assertEqual(failed['generation_tasks']['activities'], 'failed')
            self.assertNotIn('roadmap', failed)
            self.assertEqual(self.start_batch(refresh=True, retry_run_id=run_id)['run_id'], run_id)
            done = self.terminal(run_id)
        self.assertTrue(done['generation_complete'], done)
        self.assertEqual(counts, {'comparison': 1, 'courses': 1, 'activities': 2, 'roadmap': 1})

    def test_batch_empty_activity_from_failed_source_is_not_success(self):
        self.jobs()
        for status in ('error', 'partial'):
            with self.subTest(source_status=status), patch('api.routes.activities.load_catalog', return_value=([], {'status': status, 'error_code': 'snapshot_unavailable'})):
                result = self.terminal(self.start_batch(refresh=True)['run_id'])
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(result['generation_tasks']['activities'], 'failed')
            self.assertNotIn('activity_recommendations', result)

    def test_batch_retry_invalidates_stale_saved_outputs_even_when_revision_is_unchanged(self):
        self.doc('제가 React 화면을 구현했습니다.')
        with patch('services.project_experience.extract_project_experiences', side_effect=fake_extraction):
            self.analyze()
        self.jobs()
        original = roadmap_batch._execute
        counts = {key: 0 for key in roadmap_batch.TASKS}
        def fail_once(task, *args):
            counts[task] += 1
            if task == 'courses' and counts[task] == 1:
                raise RuntimeError('synthetic course failure')
            return original(task, *args)
        with patch.object(roadmap_batch, '_execute', side_effect=fail_once):
            run_id = self.start_batch()['run_id']
            self.assertEqual(self.terminal(run_id)['status'], 'failed')
            revision = self.revision()
            # Emulate stale intermediate snapshots without changing the plan revision.
            with closing(connect()) as db:
                store = RoadmapRepository(db)
                saved = decode(store.get(self.rid, run_id)['basis_json'])
                saved['_generation_work']['results']['comparison']['project_analysis']['verified_experiences'] = 999
                saved['_generation_work']['results']['activities']['activity_basis'] = 'stale-basis'
                db.execute('UPDATE roadmap_runs SET basis_json=? WHERE run_id=?', (store.encode(saved), run_id))
            self.assertEqual(self.revision(), revision)
            self.assertEqual(self.start_batch(refresh=True, retry_run_id=run_id)['run_id'], run_id)
            result = self.terminal(run_id)
        self.assertTrue(result['generation_complete'], result)
        self.assertEqual(counts, {'comparison': 2, 'courses': 2, 'activities': 2, 'roadmap': 1})

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
        self.assertEqual(self.model.call_count, 1)
        self.assertEqual(self.reasons.call_count, 1)
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
            self.assertEqual(self.model.call_count, 1)
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


if __name__ == '__main__':
    suite = unittest.TestSuite(BatchAPI(name) for name in unittest.defaultTestLoader.getTestCaseNames(BatchAPI) if name.startswith('test_batch_'))
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
