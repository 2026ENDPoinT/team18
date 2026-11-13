import test from 'node:test';
import assert from 'node:assert/strict';
import { loadCourseCatalog, courseYear, termSections, filterCourses, withPendingSelections } from '../../src/features/intake/courseCatalog.mjs';

const rows = Array.from({ length: 125 }, (_, i) => ({ course_id:`course-${i}`, course_name:`과목 ${i}`, course_code:`CS${i}`, recommended_year:i%4+1, recommended_term:i%2+1, credits:3, category:'전공선택', is_completed:false }));
function response(courses, page=1, total=courses.length) { return { catalog_id:'catalog', catalog_version:'2026', selection_revision:3, input_revision:7, courses, total, page, page_size:20, out_of_scope_completed_courses:[] }; }

test('collects every server page including a partial final page; never truncates at requested size', async () => {
 const pages=[];
 const result=await loadCourseCatalog(async path=>{
  const page=Number(new URL(path,'https://test').searchParams.get('page')); pages.push(page);
  return response(rows.slice((page-1)*20,page*20),page,rows.length);
 },'request','catalog');
 assert.deepEqual(pages,[1,2,3,4,5,6,7]); assert.deepEqual(result.courses,rows);
 assert.equal((await loadCourseCatalog(async()=>response([]),'r','catalog')).courses.length,0);
});

test('rejects a changing snapshot, duplicate IDs, failed pages, and clamped pagination', async () => {
 for(const mutation of [result=>({...result,selection_revision:4}),result=>({...result,input_revision:8}),result=>({...result,total:126}),result=>({...result,page:1}),result=>({...result,courses:[rows[0]]})]) {
  let calls=0;
  await assert.rejects(loadCourseCatalog(async()=>++calls===1?response(rows.slice(0,20),1,125):mutation(response(rows.slice(20,40),2,125)),'r','catalog'));
 }
 let calls=0;
 await assert.rejects(loadCourseCatalog(async()=>{if(++calls===2)throw Error('offline');return response(rows.slice(0,20),1,125);},'r','catalog'),/offline/);
});

test('missing years/terms remain visible; Korean name ordering stays within each term', () => {
 const courses=[{...rows[0],course_name:'자료구조 (Data Structure)',recommended_term:'1학기'},
  {...rows[1],course_name:'가상현실',recommended_term:'1학기'},
  {...rows[2],recommended_year:null,recommended_term:null},
  {...rows[3],recommended_year:2,recommended_term:null}];
 assert.equal(courseYear(courses[2]),null); assert.equal(courseYear(courses[3]),2);
 const sections=termSections(courses);
 assert.deepEqual(sections[0].courses.map(c=>c.course_name),['가상현실','자료구조 (Data Structure)']);
 assert.equal(sections[2].courses.length,2);
 assert.equal(sections.reduce((n,s)=>n+s.courses.length,0),courses.length);
});

test('pending toggles preserve bilingual IDs and whole-catalog totals through filters', () => {
 const courses=[{...rows[0],course_name:'자료구조 (Data Structure)',course_code:'100 / 200',member_course_ids:['course-0','legacy-en']}, {...rows[1],credits:null}];
 const data=withPendingSelections(response(courses),new Map([['course-0',true],['course-1',true]]));
 assert.deepEqual(data.selection_summary,{count:2,known_credits:3,unknown_credits_count:1});
 for (const search of ['Data Structure','data structure','200']) {
  assert.deepEqual(filterCourses(data.courses,{search,category:'',only:true}).map(c=>c.course_id),['course-0']);
 }
 assert.equal(filterCourses(data.courses,{search:'no matches',category:'',only:true}).length,0);
 assert.equal(data.selection_summary.count,2); assert.deepEqual(data.courses[0].member_course_ids,['course-0','legacy-en']);
 assert.equal(courses[0].is_completed,false);
});
