import test from 'node:test';
import assert from 'node:assert/strict';
import { recommendedCourseCards } from '../../src/features/roadmap/coursePresentation.mjs';
import { relatedRoles } from '../../src/features/roadmap/resultPresentation.mjs';
import { loadResultResources } from '../../src/features/roadmap/resultData.mjs';

test('recommendations preserve rank/reason, exclude completed reviewed identities and never deduplicate by title', () => {
 const result = { recommended_courses: [
  { course_id: 'old', course_name: '프로그래밍 기초', member_course_ids: ['old', 'old-alias'] },
  { course_id: 'new', course_name: '데이터베이스', personalization_reason: '목표에 필요한 SQL 조회를 연습해요.' },
  { course_id: 'new-alias', course_name: '데이터베이스', member_course_ids: ['new', 'new-alias'] },
  { course_id: 'other', course_name: '데이터베이스' },
 ] };
 const cards = recommendedCourseCards(result, [{ course_id: 'old-alias' }]);
 assert.deepEqual(cards.map(c => c.course_id), ['new', 'other']);
 assert.equal(cards[0].personalization_reason, '목표에 필요한 SQL 조회를 연습해요.');
});

test('only a saved analyzed role is a related job, never skills or search keywords', () => {
 const job = { snapshot_id: 'saved', canonical_role: '데이터 분석가', target_role: '데이터 분석가', skills: [{ name: 'SQL' }, { name: 'React' }], keyword_details: [{ keyword: 'data' }] };
 assert.deepEqual(relatedRoles({ job_analysis: job }), ['데이터 분석가']);
 assert.deepEqual(relatedRoles({ job_analysis: { ...job, canonical_role: '', target_role: '' } }), []);
 assert.deepEqual(relatedRoles({ job_analysis: { status: 'not_started', target_role: 'SQL' } }), []);
});

test('a rejected roadmap remains an error while saved profile and comparison load with GET only', async () => {
 const calls = [], resources = {};
 const request = async (path, options) => {
  calls.push({ path, options });
  if (path.endsWith('/roadmap')) throw Error('로드맵 조회 실패');
  if (path.endsWith('/plan')) return { input: { catalog_id: 'catalog' } };
  return { selected_courses: [] };
 };
 await loadResultResources(request, 'plan', (key, value) => { resources[key] = value; });
 assert.equal(resources.plan.phase, 'ready');
 assert.equal(resources.roadmap.phase, 'error');
 assert.equal(resources.comparison.phase, 'ready');
 assert.equal(resources.courses.phase, 'ready');
 assert.ok(calls.some(c => c.path.endsWith('page_size=1')));
 assert.ok(calls.every(c => !c.options));
});
