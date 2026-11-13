import test from 'node:test';
import assert from 'node:assert/strict';
import { recommendedCourseCards } from '../../src/features/roadmap/coursePresentation.mjs';
import { analyzedSkills, courseLearning } from '../../src/features/roadmap/resultPresentation.mjs';
import { loadResultResources } from '../../src/features/roadmap/resultData.mjs';

test('course descriptions never infer learning from a title or prerequisite alone', () => {
 assert.equal(courseLearning({ course_name:'SQL', course_evidence:'SQL', keyword_evidence:[{ keyword_role:'prerequisite', evidence_text:'Python 사전 지식' }] }), '공식 학습 내용이 제공되지 않았습니다.');
 assert.equal(courseLearning({ keyword_evidence:[{ keyword_role:'learning', evidence_text:'관계형 질의 학습' }] }), '관계형 질의 학습');
});

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

test('skill overview uses saved analysis skills, never the role or search keywords', () => {
 const job = { snapshot_id: 'saved', canonical_role: '데이터 분석가', target_role: '데이터 분석가', skills: [{ name: 'SQL' }, { name: 'React' }], keyword_details: [{ keyword: 'data' }] };
 assert.deepEqual(analyzedSkills({ job_analysis: job }), job.skills);
 assert.deepEqual(analyzedSkills({ job_analysis: { ...job, skills: [] } }), []);
 assert.deepEqual(analyzedSkills({ job_analysis: { ...job, snapshot_id: null } }), []);
 assert.deepEqual(analyzedSkills({ job_analysis: { status: 'not_started', target_role: 'SQL' } }), []);
 assert.deepEqual(analyzedSkills({ job_analysis: { ...job, skills: [{name:''},{},...job.skills], analysis_version:'job-skills-v2' }, comparisons:[{skill_name:'React'},{skill_name:'SQL'}] }).map(skill=>skill.name), ['React','SQL']);
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
 assert.equal(resources.activities.phase, 'ready');
 assert.equal(resources.courses.phase, 'ready');
 assert.ok(calls.some(c => c.path.endsWith('page_size=1')));
 assert.ok(calls.every(c => !c.options));
});
