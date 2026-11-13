import test from 'node:test';
import assert from 'node:assert/strict';
import { completeResult, pollGeneration } from '../../src/features/roadmap/generationFlow.mjs';

const states = {comparison:'success',courses:'success',activities:'success',roadmap:'success'};
const complete = {run_id:'run-1',status:'partial',generation_complete:true,generation_tasks:states,
 roadmap:[],recommended_courses:[],course_reasons:[],
 skill_comparison:{comparisons:[],job_analysis:{status:'success',snapshot_id:'job-1'}},
 activity_recommendations:{status:'success',activities:[],sources:[{status:'success'}]}};

test('only the verified matching run with every valid result is complete, including legitimate empty lists', () => {
 assert.equal(completeResult(complete, 'run-1'), true);
 assert.equal(completeResult({...complete,recommended_courses:[{course_id:'c'}],course_reasons:[{course_id:'c',personalization_reason:'저장된 추천 이유'}]}, 'run-1'), true);
 for (const value of [{...complete, run_id:'other'}, {...complete, generation_complete:false},
  {...complete,generation_tasks:{...states,activities:'running'}}, {...complete,activity_recommendations:{status:'error'}},
  {...complete,recommended_courses:[{course_id:'c'}],course_reasons:[]},
  {...complete,roadmap:null}, {...complete,is_stale:true}]) assert.equal(completeResult(value,'run-1'),false);
});

test('polling waits for the last task and verified read, even when a different task finishes first', async () => {
 for (const slow of ['comparison','courses','activities']) {
  const updates=[], responses = [
   {run_id:'run-1',status:'generating',generation_complete:false,generation_tasks:{...states,[slow]:'running',roadmap:'running'}},
   {...complete,generation_complete:false,generation_tasks:{...states,roadmap:'running'}}, complete,
  ];
  const result = await pollGeneration({request:async()=>responses.shift(),planId:'plan',runId:'run-1',onState:data=>updates.push(data),delay:async()=>{}});
  assert.equal(result.kind,'complete'); assert.equal(updates.length,3);
 }
});

test('server failure, invalid committed data, and repeated 503s remain distinct', async () => {
 const run = async request => pollGeneration({request,planId:'plan',runId:'run-1',onState:()=>{},delay:async()=>{}});
 assert.equal((await run(async()=>({run_id:'run-1',status:'failed'}))).kind,'failed');
 assert.equal((await run(async()=>({...complete,activity_recommendations:{status:'error'}}))).kind,'invalid');
 let attempts=0;
 assert.equal((await run(async()=>{attempts++;throw Object.assign(new Error('503'),{status:503});})).kind,'unknown');
 assert.equal(attempts,4);
});


test('verified partial results finish without successful optional sections or generated steps', () => {
 for (const status of ['partial', 'failed', 'unavailable']) {
  const value = {...complete, generation_tasks:{...states,comparison:status,activities:status,courses:status},
   skill_comparison:{comparisons:[],job_analysis:{status:'not_started'}},
   activity_recommendations:{status:status === 'partial' ? 'partial' : 'error',activities:[],sources:[]}};
  assert.equal(completeResult(value,'run-1'),true);
  assert.equal(completeResult({...value,generation_complete:false},'run-1'),false);
  assert.equal(completeResult({...value,generation_tasks:{...value.generation_tasks,roadmap:'failed'}},'run-1'),false);
 }
});
