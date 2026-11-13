import test from 'node:test';
import assert from 'node:assert/strict';
import { loadDashboardResources, dashboardCards, resumeDestination } from '../../src/features/roadmap/dashboardData.mjs';
import { courseLearning } from '../../src/features/roadmap/resultPresentation.mjs';
const plan = { request_id: 'one', input: { career_goal:'데이터 분석', catalog_id:'catalog' } };
test('a failed card stays an error while independent saved values survive; GET only', async () => {
 const calls = [];
 const resources = await loadDashboardResources(async (path, options) => {
  calls.push([path, options]);
  if (path.endsWith('/documents')) throw Error('문서 일시 실패');
  if (path.endsWith('/project-experience-analysis')) return { analyzed_documents:1, verified_experiences:1, experiences:[{ activity:'원래 활동', skill_name:'React', contribution_scope:'team', user_answer:{ status:'corrected', correction:{ activity:'수정한 수행', skill_name:'TypeScript', contribution_scope:'personal' } } }] };
  if (path.includes('/courses?')) return { selection_summary:{count:0,known_credits:0,unknown_credits_count:0}, selected_courses:[] };
  if (path === '/reference') return { universities:[], departments:[] };
  return {};
 }, plan);
 const cards = dashboardCards(plan, resources);
 assert.equal(cards.length,8);
 assert.equal(cards.find(card=>card.key==='documents').error,'문서 일시 실패');
 assert.ok(cards.find(card=>card.key==='experience').lines.includes('수정한 수행'));
 assert.ok(cards.find(card=>card.key==='courses').lines.includes('선택 0과목'));
 assert.ok(!cards.find(card=>card.key==='basic').lines.join(' ').includes('학년'));
 assert.ok(calls.every(([,options])=>options===undefined));
});
test('no goal or catalog skips unavailable lookups; current owner/plan paths only', async()=>{
 const calls=[];
 await loadDashboardResources(async path=>{calls.push(path);return {};},{request_id:'two',input:{career_goal:''}});
 assert.ok(!calls.some(path=>path.includes('/activities')||path.includes('/courses?')));
 assert.ok(calls.every(path=>path==='/reference'||path.startsWith('/roadmap-inputs/two/')));
});
test('roadmap card opens the summary and describes saved recommendations',()=>{
 const resources={roadmap:{data:{roadmap:[{tasks:[{title:'removed task',is_completed:false}]}],recommended_courses:[{course_id:'one',course_name:'데이터베이스'}]}}};
 const card=dashboardCards(plan,resources).find(card=>card.key==='roadmap');
 assert.equal(card.href,'/result?tab=roadmap');
 assert.equal(card.lines[0],'저장된 수강 후보 1개');
 assert.ok(!card.lines.join(' ').includes('removed task'));
 assert.equal(card.action,'로드맵 요약 보기');
});
test('course descriptions never infer learning from a title or prerequisite alone',()=>{
 assert.equal(courseLearning({course_name:'SQL',course_evidence:'SQL',keyword_evidence:[{keyword_role:'prerequisite',evidence_text:'Python 사전 지식'}]}),'공식 학습 내용이 제공되지 않았습니다.');
 assert.equal(courseLearning({keyword_evidence:[{keyword_role:'learning',evidence_text:'관계형 질의 학습'}]}),'관계형 질의 학습');
});
test('resume uses saved progress and errors do not silently create a new plan',()=>{
 assert.equal(resumeDestination({input:{}},{}),'/input/basic');
 assert.equal(resumeDestination(plan,{}),'/input/documents');
 assert.equal(resumeDestination(plan,{documents:{error:'failed'}}),'/dashboard');
 assert.equal(resumeDestination(plan,{documents:{data:{documents:[{extraction_status:'failed'}],analysis_eligible:false}}}),'/input/documents');
 assert.equal(resumeDestination(plan,{documents:{data:{documents:[{extraction_status:'ready'}],analysis_eligible:true}}}),'/input/courses');
 assert.equal(resumeDestination(plan,{roadmap:{data:{roadmap:[{}]}}}),'/result?tab=roadmap');
 assert.equal(resumeDestination({...plan,review_status:'confirmed'},{}),'/input/review');
});
test('representative experience favors confirmed personal work and never claims denied work',()=>{
 const item=(activity,contribution_scope,status)=>({activity,skill_name:'SQL',contribution_scope,user_answer:status?{status}:null});
 const resources={experience:{data:{analyzed_documents:1,verified_experiences:3,experiences:[item('팀 활동','team'),item('아닌 활동','personal','no_experience'),item('확인한 내 활동','personal','confirmed')]}}};
 assert.equal(dashboardCards(plan,resources).find(card=>card.key==='experience').lines[0],'확인한 내 활동');
 resources.experience.data.experiences=[item('아닌 활동','personal','no_experience')];
 const text=dashboardCards(plan,resources).find(card=>card.key==='experience').lines.join(' ');
 assert.ok(text.includes('모두에 경험 없다고')); assert.ok(!text.includes('아닌 활동'));
});
