'use client';
import './courses.css';
import { courseYears, termSections } from './courseCatalog.mjs';

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

export function SelectedCoursesSummary({ data }) {
 const years = courseYears(data.selected_courses);
 return <>
  <p><strong>{data.selection_summary.count}개 과목</strong></p>
  <div className="course-year-grid">{years.map(group => <SelectedYearTable key={group.year || 'unknown'} {...group}/>)}</div>
 </>;
}
