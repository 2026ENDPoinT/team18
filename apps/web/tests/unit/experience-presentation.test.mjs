import assert from 'node:assert/strict';
import test from 'node:test';
import { experiencePresentation } from '../../src/features/roadmap/experiencePresentation.mjs';
const original={skill_name:'React',activity:'팀 신청 화면 구현',contribution_scope:'team',role:'프런트엔드'};
test('latest corrected activity, skill and personal scope replace the card presentation only',()=>{
 const correction={skill_name:'TypeScript',activity:'입력 검증을 구현했어요',contribution_scope:'personal'};
 const item={...original,user_answer:{status:'corrected',correction}};
 assert.deepEqual(experiencePresentation(item),correction);
 assert.equal(item.activity,original.activity);
 assert.equal(item.contribution_scope,'team');
});
test('unmodified and other answers preserve analyzed activity and team scope',()=>{
 for(const status of [undefined,'confirmed','unknown','no_experience']){
  const item={...original,user_answer:status?{status,correction:{activity:'stale'}}:null};
  assert.equal(experiencePresentation(item),item);
 }
});
