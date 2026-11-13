"""Synthetic API scenarios shared by isolated SQLite and PostgreSQL. AI is mocked."""
from contextlib import closing
import unittest
import uuid
from unittest.mock import patch

from project_experience_scenario import ProjectExperienceAPI, fake_extraction, job_result
from repositories.plans import connect, Repository
from repositories.roadmaps import RoadmapRepository
from services.roadmap_schemas import GeneratedRoadmap

U, D, C, C2 = ('roadmap-test-' + s for s in ('university', 'department', 'catalog', 'outside-catalog'))
DB_COURSE, OTHER_COURSE = 'roadmap-test-database', 'roadmap-test-same-name'

def fake_roadmap(data):
    """Contract fixture adapts to actual server input; never used by production code."""
    skill = next(s for s in data['skills'] if s['skill_name'] == 'SQL')
    status = skill['student_status']
    intent = 'deepen' if status == 'confirmed_experience' else 'learn' if status == 'no_experience' else 'verify_experience'
    courses = [c for c in data['eligible_courses'] if c['course_id'] == DB_COURSE]
    selected = [{'course_id': c['course_id'], 'related_skills': ['SQL'], 'evidence_refs': [skill['comparison_ref']],
                 'course_evidence': c['description_text'] or c['course_name'], 'reason': 'SQL 데이터 조회 개념과 관련된 후보',
                 'personalization_reason': status + ' 상태 반영', 'course_role': 'advanced' if intent == 'deepen' else 'foundation',
                 'recommendation_confidence': 'supported'} for c in courses]
    return GeneratedRoadmap(recommended_courses=selected, roadmap=[{
        'step_id': f'step-{i}', 'order': i, 'title': f'{intent} 활동 {i}', 'purpose': 'SQL 활용 준비',
        'reason': status + ' 상태에 따른 추천 의견', 'skill_targets': [{'skill_name': 'SQL', 'student_status': status, 'action_type': intent}],
        'related_course_ids': [c['course_id'] for c in selected], 'depends_on': [f'step-{i-1}'] if i > 1 else [],
        'evidence_refs': [skill['comparison_ref']], 'limitations': '해외 공고 표본과 현재 확인 자료에 한정',
        'tasks': [{'task_id': f'task-{i}', 'task_type': 'verify_experience' if intent == 'verify_experience' else 'apply',
                   'title': f'{intent} 작업 {i}', 'action': f'SQL 경험 확인 자료 {i}를 정리한다.' if intent == 'verify_experience' else f'{intent} 구체 작업 {i}를 수행한다.',
                   'completion_criteria': '검토 가능한 실행 파일과 결과 기록', 'deliverable': f'결과 기록 {i}'}],
    } for i in range(1, 4)])

class RoadmapAPI(ProjectExperienceAPI):

    def setUp(self):
        super().setUp()
        source = {'status': 'success', 'kind': 'competition', 'collected': 0}
        for path in ('api.routes.activities.load_catalog', 'api.routes.activities.load_contestkorea_catalog'):
            mocked = patch(path, return_value=([], source))
            mocked.start(); self.addCleanup(mocked.stop)
        with closing(connect()) as db:
            db.execute('INSERT INTO universities VALUES(?,?,TRUE) ON CONFLICT DO NOTHING', (U, 'Synthetic'))
            db.execute('INSERT INTO departments VALUES(?,?,?,TRUE) ON CONFLICT DO NOTHING', (D, U, 'Synthetic'))
            for cid in (C, C2):
                db.execute('''INSERT INTO course_catalogs(catalog_id,department_id,version_label,scope_description,
                    completeness_status,source_name,retrieved_at,is_selectable) VALUES(?,?,?,?,?,?,?,TRUE) ON CONFLICT DO NOTHING''',
                    (cid, D, 'test', 'synthetic catalog', 'complete', 'test', '2026-11-09T00:00:00+00:00'))
            for course, cid in ((DB_COURSE, C), (OTHER_COURSE, C2)):
                db.execute('INSERT INTO courses(course_id,university_id,canonical_name) VALUES(?,?,?) ON CONFLICT DO NOTHING', (course, U, '데이터베이스'))
                db.execute('INSERT INTO catalog_courses(catalog_id,course_id,course_name,course_code) VALUES(?,?,?,?) ON CONFLICT DO NOTHING', (cid, course, '데이터베이스', course))
        self.client.patch(self.base, json={'expected_input_revision': self.revision(), 'changes': {'university_id': U, 'department_id': D, 'catalog_id': C}})

    def jobs(self):
        result = job_result()
        # All four fixture skills have equal frequency. Keep SQL in the small
        # representative unknown sample for this SQL-specific contract fixture.
        result['skills'].sort(key=lambda s: (s['name'] != 'SQL', s['name']))
        with patch('api.routes.job_skill_analysis.analyze_job_skills', return_value=result) as model:
            response = self.client.post(self.base + '/job-skill-analysis', json={})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json(), model.call_count

    def make(self, refresh=False):
        return self.client.post(self.base + '/roadmap', json={'expected_input_revision': self.revision(), 'refresh': refresh})

    def generated(self, refresh=False):
        with patch('services.gemini_roadmap.generate_roadmap', side_effect=AssertionError('Unexpected roadmap AI')) as ai:
            response = self.make(refresh)
        self.assertIn(response.status_code, (200, 201), response.text)
        return response.json(), ai.call_count

    def sql_answer(self, status):
        snapshot = self.comparison()['job_analysis']['snapshot_id']
        response = self.client.post(self.base + '/skill-comparison/answers', json={
            'expected_input_revision': self.revision(), 'snapshot_id': snapshot, 'skill_name': 'SQL', 'status': status})
        self.assertEqual(response.status_code, 200, response.text)

    def complete_course(self, course=DB_COURSE, catalog=C):
        plan = self.client.get(self.base).json()
        response = self.client.patch(self.base + '/course-selections', json={'catalog_id': catalog,
            'expected_selection_revision': plan['selection_revision'], 'changes': [{'course_id': course, 'is_completed': True}]})
        self.assertEqual(response.status_code, 200, response.text)

    def review_courses(self, missing=False):
        plan = self.client.get(self.base).json()
        response = self.client.post(self.base + '/course-selection-review', json={'catalog_id': C,
            'expected_selection_revision': plan['selection_revision'], 'expected_input_revision': plan['input_revision'], 'reported_missing_courses': missing})
        self.assertEqual(response.status_code, 200, response.text)


    def test_roadmap_full_basis_invalidation(self):
        self.jobs(); first, _ = self.generated()
        self.review_courses(True)
        second, _ = self.generated()
        self.assertEqual(second['basis']['review_status'], 'partial')
        self.assertNotEqual(first['basis_hash'], second['basis_hash'])
        # Catalog metadata can change without input_revision: still invalidate.
        with closing(connect()) as db:
            db.execute('UPDATE course_catalogs SET scope_description=? WHERE catalog_id=?', (str(uuid.uuid4()), C))
        self.assertTrue(self.client.get(self.base + '/roadmap').json()['is_stale'])
        third, _ = self.generated()
        with patch('api.routes.job_skill_analysis.analyze_job_skills', return_value=self.comparison()['job_analysis']):
            self.client.post(self.base + '/job-skill-analysis', json={'refresh': True})
        self.assertTrue(self.client.get(self.base + '/roadmap').json()['is_stale'])
        fourth, _ = self.generated()
        self.assertNotEqual(third['basis_hash'], fourth['basis_hash'])

    def test_roadmap_deleted_or_reextracted_document_restricts_details(self):
        did = self.doc(); self.jobs(); first, _ = self.generated()
        self.client.post(f'{self.base}/documents/{did}/retry-extraction', json={'expected_input_revision': self.revision()})
        detail = self.client.get(f'{self.base}/roadmaps/{first["run_id"]}').json()
        self.assertTrue(detail['details_restricted']); self.assertNotIn('roadmap', detail); self.assertNotIn('evidence', detail)
        self.assertEqual(self.client.patch(f'{self.base}/roadmaps/{first["run_id"]}/tasks/task-1', json={'is_completed': True, 'expected_progress_version': 0}).json()['error'], 'evidence_unavailable')
        second, _ = self.generated()
        self.client.request('DELETE', f'{self.base}/documents/{did}', json={'expected_input_revision': self.revision()})
        self.assertTrue(self.client.get(f'{self.base}/roadmaps/{second["run_id"]}').json()['details_restricted'])
        history = self.client.get(self.base + '/roadmaps').json()
        self.assertNotIn('evidence_text', str(history)); self.assertNotIn('result_json', str(history))

    def test_roadmap_analysis_completion_invalidates_without_input_change(self):
        self.doc(); self.jobs(); first, _ = self.generated(); revision = self.revision()
        with patch('services.project_experience.extract_project_experiences', side_effect=fake_extraction): self.analyze()
        self.assertEqual(revision, self.revision())
        self.assertTrue(self.client.get(self.base + '/roadmap').json()['is_stale'])
        second, _ = self.generated(); self.assertNotEqual(first['basis_hash'], second['basis_hash'])

    def test_roadmap_outside_completed_preserved(self):
        self.client.patch(self.base, json={'expected_input_revision': self.revision(), 'changes': {'catalog_id': C2}})
        self.complete_course(OTHER_COURSE, C2)
        self.client.patch(self.base, json={'expected_input_revision': self.revision(), 'changes': {'catalog_id': C}})
        self.jobs(); run, _ = self.generated()
        self.assertEqual(run['basis']['outside_completed_courses'][0]['course_id'], OTHER_COURSE)
        self.assertEqual(run['recommended_courses'][0]['course_id'], DB_COURSE)
        with closing(connect()) as db:
            self.assertTrue(db.execute('SELECT is_completed FROM input_course_states WHERE request_id=? AND course_id=?', (self.rid, OTHER_COURSE)).fetchone()['is_completed'])

    def test_roadmap_ownership_and_invalid_task(self):
        self.jobs(); run, _ = self.generated()
        other = self.client.post('/api/roadmap-inputs').json()['request_id']
        self.assertEqual(self.client.get(f'/api/roadmap-inputs/{other}/roadmaps/{run["run_id"]}').status_code, 404)
        task = f'{self.base}/roadmaps/{run["run_id"]}/tasks/task-1'
        self.assertEqual(self.client.patch(task.replace('task-1', 'invented'), json={'is_completed': True, 'expected_progress_version': 0}).status_code, 404)
        headers = self.auth.headers() if hasattr(self, 'auth') else {}
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app, headers={'Origin': 'http://localhost:3000', **headers}) as stranger:
            if not headers: stranger.post('/api/roadmap-inputs')
            for path in ('/roadmap', '/roadmaps', '/roadmaps/' + run['run_id']):
                self.assertEqual(stranger.get(self.base + path).status_code, 404)
            self.assertEqual(stranger.patch(task, json={'is_completed': True, 'expected_progress_version': 0}).status_code, 404)
            self.assertEqual(stranger.post(self.base + '/roadmap', json={'expected_input_revision': self.revision()}).status_code, 404)


    def test_roadmap_expired_lease_recovery(self):
        self.jobs()
        from repositories.roadmaps import RoadmapRepository
        from services.roadmap_generation import capture_basis
        with closing(connect()) as db:
            Repository(db).begin()
            row = db.execute('SELECT * FROM roadmap_inputs WHERE request_id=?', (self.rid,)).fetchone()
            run = RoadmapRepository(db).create(self.rid, capture_basis(db, row))
            db.execute('UPDATE roadmap_runs SET lease_until=? WHERE run_id=?', ('2020-01-01T00:00:00+00:00', run['run_id']))
            db.commit()
        self.assertTrue(self.client.get(self.base + '/roadmap').json()['generation_expired'])
        new, calls = self.generated()
        self.assertEqual(calls, 0); self.assertNotEqual(new['run_id'], run['run_id'])
        old = self.client.get(f'{self.base}/roadmaps/{run["run_id"]}').json()
        self.assertEqual(old['error_code'], 'generation_expired'); self.assertEqual(old['status'], 'failed')


if __name__ == '__main__':
    suite = unittest.TestSuite(RoadmapAPI(name) for name in unittest.defaultTestLoader.getTestCaseNames(RoadmapAPI) if name.startswith('test_roadmap_'))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
