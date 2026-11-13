'use client';
import './courses.css';
import { courseYear, sortCoursesByName, termSections } from './courseCatalog.mjs';

function SelectedYearTable({ year, courses }) {
 const title = year ? `${year}학년` : '학년 미지정';
 return <section className="course-year" aria-label={`${title} 이수 선택`} data-selected-year={year || 'unknown'}>
  <header className="course-year-heading"><h3>{title}</h3><span>선택 {courses.length}과목</span></header>
  {courses.length ? <table className="course-year-table course-selected-table" aria-label={`${title} 선택 과목`}>
   {termSections(courses).filter(section => section.courses.length).map(section => <tbody key={section.title}>
    <tr className="course-term"><th scope="colgroup">{section.title}<span>{section.courses.length}과목</span></th></tr>
    {section.courses.map(course => <tr key={course.course_id} data-selected-course-id={course.course_id}><td>
     <strong className="course-name">{course.course_name}</strong>
    </td></tr>)}
   </tbody>)}
  </table> : <p className="course-year-empty">선택한 과목이 없습니다.</p>}
 </section>;
}

export function SelectedCoursesSummary({ data, byYear = false }) {
 const selected = sortCoursesByName(data.selected_courses);
 return <>
  <p><strong>{data.selection_summary.count}개 과목</strong></p>
  {byYear ? <>
   <div className="course-year-grid">{[1, 2, 3, 4].map(year => <SelectedYearTable key={year} year={year} courses={selected.filter(course => courseYear(course) === year)}/>)}</div>
   {selected.some(course => courseYear(course) === null) && <div className="course-unassigned"><SelectedYearTable year={null} courses={selected.filter(course => courseYear(course) === null)}/></div>}
  </> : <ul>{selected.length ? selected.map(course => <li key={course.course_id}>{course.course_name}</li>) : <li>선택한 이수 과목 없음</li>}</ul>}
 </>;
}
