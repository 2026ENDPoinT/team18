import test from 'node:test';
import assert from 'node:assert/strict';
import { loadResumeResources, resumeDestination } from '../../src/features/roadmap/resumePlan.mjs';

const plan = { request_id:'one', input:{ career_goal:'데이터 분석', catalog_id:'catalog' } };

test('resume reads only saved progress for the selected plan and preserves individual failures', async () => {
 const calls = [];
 const resources = await loadResumeResources(async (path, options) => {
  calls.push([path, options]);
  if (path.endsWith('/documents')) throw Error('문서 일시 실패');
  return {};
 }, plan);
 assert.equal(resources.documents.error, '문서 일시 실패');
 assert.ok(calls.every(([path, options]) => path.startsWith('/roadmap-inputs/one/') && options === undefined));
 assert.equal(calls.length, 5);
 assert.ok(!calls.some(([path]) => path.includes('/activities') || path === '/reference'));
 const noCatalog = [];
 await loadResumeResources(async path => { noCatalog.push(path); return {}; }, { request_id:'two', input:{ career_goal:'' } });
 assert.equal(noCatalog.length, 4);
 assert.ok(noCatalog.every(path => path.startsWith('/roadmap-inputs/two/') && !path.includes('/courses?')));
});

test('resume follows saved progress and reports lookup errors without opening a removed page or creating a plan', () => {
 assert.equal(resumeDestination({ input:{} }, {}), '/input/basic');
 assert.equal(resumeDestination(plan, {}), '/input/documents');
 assert.throws(() => resumeDestination(plan, { documents:{ error:'failed' } }), /진행 상태를 확인하지 못했습니다/);
 assert.equal(resumeDestination(plan, { documents:{ data:{ documents:[{ extraction_status:'failed' }], analysis_eligible:false } } }), '/input/documents');
 assert.equal(resumeDestination(plan, { documents:{ data:{ documents:[{ extraction_status:'ready' }], analysis_eligible:true } } }), '/input/courses');
 assert.equal(resumeDestination(plan, { courses:{ data:{ selection_summary:{ count:1 } } } }), '/input/courses');
 assert.equal(resumeDestination({ ...plan, review_status:'confirmed' }, {}), '/input/review');
 assert.equal(resumeDestination(plan, { skills:{ data:{ job_analysis:{ snapshot_id:'saved' } } } }), '/result?tab=skills');
 assert.equal(resumeDestination(plan, { roadmap:{ data:{ roadmap:[{}] } } }), '/result?tab=roadmap');
});
