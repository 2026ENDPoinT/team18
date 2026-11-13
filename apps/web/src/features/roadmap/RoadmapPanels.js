import Link from 'next/link';
import { courseLearning } from './resultPresentation.mjs';
import { recommendedCourseCards } from './coursePresentation.mjs';

function CourseTitle({ name }) {
 const translated = name?.match(/^(.*?)\s*(\([A-Za-z][^가-힣]*\))$/);
 if (!translated || !/[가-힣]/.test(translated[1])) return <h3>{name}</h3>;
 return <h3>{translated[1].trimEnd()}<span className="course-title-english"> {translated[2]}</span></h3>;
}

export function CourseCandidates({ result, selectedCourses, courseReasons }) {
 const catalog = result.basis.catalog;
 const cards = recommendedCourseCards(result, selectedCourses);
 return <><h2>수강 후보</h2><p>저장된 경험·이수 선택 기준으로 추천한 수강 후보입니다.</p>
  {result.course_status === 'evidence_unavailable' ? <p className="notice">검증된 직무 근거가 없어 수강 후보 추천을 보류했습니다. 직무 역량 비교에서 분석 내용을 확인해 주세요.</p> : result.course_status === 'catalog_unavailable' ? <p className="notice">과목 목록을 사용할 수 없어 수강 후보를 생성하지 않았습니다.</p> : <>
   {catalog?.source_url?.startsWith('https://') && <p><a href={catalog.source_url} target="_blank" rel="noopener noreferrer">과목 목록 출처 ↗</a></p>}
   {result.basis.review_status === 'unconfirmed' && <p className="notice">이수 선택 확인 전의 잠정 후보입니다. 미이수로 확정하지 않습니다. <Link href="/input/courses">이수 선택 확인 →</Link></p>}
   {result.basis.review_status === 'partial' && <p className="notice">현재 목록에 누락된 과목이 있습니다. 이수 선택 확인은 현재 목록 안에 한정됩니다.</p>}
   {cards.length === 0 && <p>현재 근거와 미선택 과목에서 추천할 후보를 찾지 못했습니다.</p>}
   {cards.length > 0 && cards.length < 5 && <p className="notice">이수 및 대체과목을 제외하면 추천 가능한 고유 과목이 {cards.length}개입니다.</p>}
  </>}
  {cards.length > 0 && courseReasons?.phase === 'error' && <div className="notice"><p role="alert">추천 이유를 불러오지 못했어요. {courseReasons.message}</p><button type="button" onClick={courseReasons.retry}>추천 이유 다시 불러오기</button></div>}
  <ul className="skill-list course-candidates-list">{cards.map(course => <li className="skill-card" key={course.course_id}>
   <div className="course-candidate-heading"><CourseTitle name={course.course_name}/>{course.recommendation_label && <span className="badge">{course.recommendation_label}</span>}</div>
   <div className="recommendation-reason" aria-busy={courseReasons?.phase === 'loading'}><p><b>목표와의 연결</b> {courseReasons?.reasons[course.course_id] || (courseReasons?.phase === 'error' ? '추천 이유를 아직 불러오지 못했어요.' : '목표와 학습 내용을 연결한 추천 이유를 작성하고 있어요…')}</p></div>
   <p className="course-candidate-meta">{course.credits == null ? '학점 미제공' : `${course.credits}학점`}{course.recommended_year ? ` · 교육과정 권장 ${course.recommended_year}학년` : ''}{course.recommended_term ? ` ${course.recommended_term}` : ''}</p>
   <details className="course-learning"><summary>과목에서 배우는 내용<span className="course-learning-arrow" aria-hidden="true">›</span></summary><p>{courseLearning(course)}</p></details>
  </li>)}</ul>
  <p className="field-help">목록 밖에서 보존한 과거 이수 선택 {result.basis.outside_completed_courses.length}개. 현재 수강 후보에는 포함하지 않습니다.</p>
 </>;
}
