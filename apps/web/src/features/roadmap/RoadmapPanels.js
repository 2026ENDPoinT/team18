import Link from 'next/link';
import { roadmapProgress, courseLearning, courseReason } from './resultPresentation.mjs';
import { experiencePresentation } from './experiencePresentation.mjs';
import { coursePresentation, relatedCourseNames } from './coursePresentation.mjs';

const statusLabels = { confirmed_experience: '확인된 경험', document_supported: '문서 근거 · 본인 확인 필요', needs_confirmation: '확인 필요', not_verified: '자료 부족 · 확인 필요', no_experience: '사용자가 경험 없음으로 응답' };

function Evidence({ refs, result }) {
 if (!refs.length) return null;
 return <details><summary>추천 연결 근거</summary><ul>{refs.map(ref => {
  const item = result.evidence[ref];
  if (!item) return null;
  return <li key={ref}>{item.skill_name} · {item.kind === 'comparison' ? `${statusLabels[item.student_status]}: ${item.reason}` : item.kind === 'job' ? '검증된 채용공고 근거' : '프로젝트 문서 근거'}
   {item.kind === 'comparison' && <span> · 공고 근거 {item.job_refs.length}건 · 프로젝트 근거 {item.project_refs.length}건</span>}
   {item.kind === 'project' && <p>{experiencePresentation(item).activity} · {item.user_answer?.status === 'confirmed' ? '본인 수행 확인' : item.user_answer?.status === 'corrected' ? '사용자 수정 답변' : item.user_answer?.status === 'no_experience' ? '경험 없음 응답' : '본인 확인 필요'}</p>}
   {item.match_source === 'user_correction' && <p className="field-help">이 기술 연결은 사용자 수정 답변에 근거합니다. 아래 원문이 수정한 기술을 검증한다는 뜻은 아닙니다.</p>}
   {item.source_url?.startsWith('https://') && <> · <a href={item.source_url} target="_blank" rel="noopener noreferrer">공고 원문 ↗</a></>}
   {item.recommendation_eligible === false && <span> · 맥락 언급으로 핵심 추천에서 제외</span>}
   {item.evidence_text && <blockquote>{item.evidence_text}</blockquote>}
  </li>;
 })}</ul></details>;
}

export function NextTask({ result, saving, onToggle }) {
 const { next, completed, total } = roadmapProgress(result);
 return <section className="next-task" aria-labelledby="next-task-title">
  <div className="eyebrow">MY NEXT STEP</div><h2 id="next-task-title">지금 할 일</h2>
  {result.is_stale && <p className="notice">이전 입력·분석 기준으로 저장된 작업입니다.</p>}
  {next ? <>
   <h3>{next.task.title}</h3><p>{next.task.action}</p>
   <dl><div><dt>나에게 추천하는 이유</dt><dd>{next.step.reason}</dd></div>
    <div><dt>완료할 결과물</dt><dd>{next.task.deliverable || '저장된 결과물 안내가 없습니다.'}</dd></div>
    <div><dt>완료 기준</dt><dd>{next.task.completion_criteria}</dd></div></dl>
   <button className="primary" disabled={saving} onClick={() => onToggle(next.task)}>이 작업 완료로 표시</button>
  </> : <p>{total ? '모든 작업을 완료했어요. 저장한 실행 기록을 아래에서 확인하세요.' : '저장된 실행 작업이 없습니다.'}</p>}
  <p className="field-help" role="status">작업 완료 {completed} / {total}개</p>
 </section>;
}

function ConfirmationQuestions({ items }) {
 if (!items.length) return null;
 return <section className="confirmation-questions" aria-label="확인할 질문"><h3>확인할 질문</h3>
  <p>아직 확인하지 않은 경험을 먼저 정리해 주세요.</p><ul>{items.map(item => <li key={item.skill_name}><strong>{item.skill_name}을 직접 수행한 경험이 있나요?</strong><p>{item.reason}</p></li>)}</ul>
  <Link href="/input/review" className="button">내 프로젝트 경험 확인</Link>{' '}<Link href="/result?tab=skills" className="button">기술별 경험 여부 답하기</Link>
 </section>;
}
const unconfirmed = result => (result.preparation_items || []).filter(item => ['document_supported', 'needs_confirmation', 'not_verified'].includes(item.student_status));

export function Preparation({ result }) {
 const summary = result.preparation_summary;
 return <>
  <h2>준비 상태</h2><p>{result.career_goal}{result.target_role ? ` · ${result.target_role}` : ''}</p>
  <div className="columns">{[['confirmed_skills', '확인된 수행 경험'], ['skills_to_verify', '추가 확인이 필요한 기술'], ['learning_candidates', '추가 학습을 검토할 기술']].map(([key, title]) => <div className="wire-box" key={key}><h3>{title}</h3><p>{summary[key].join(', ') || '현재 확인된 항목 없음'}</p></div>)}</div>
  <p>분석된 해외 채용공고 {result.basis.job_summary.analyzed_jobs || 0}개 · 프로젝트 분석 {result.basis.project_documents.filter(d => ['success', 'partial'].includes(d.status)).length}개</p>
  <ConfirmationQuestions items={unconfirmed(result)}/>
  <ul className="skill-list">{result.preparation_items.filter(item => !unconfirmed(result).includes(item)).map(item => {
   return <li className="skill-card" key={item.skill_name}><h3>{item.skill_name} <span className="badge">{statusLabels[item.student_status]}</span></h3><p>{item.reason}</p>
    {item.job_requirement?.priority_reason && <p className="field-help">{item.job_requirement.priority_reason}</p>}
    {item.job_requirement?.single_job_notice && <p className="notice">{item.job_requirement.single_job_notice}</p>}
    <Evidence refs={[item.comparison_ref, ...item.job_refs, ...item.project_refs]} result={result}/></li>;
  })}</ul>
  <Link href="/input/review">경험 확인 답변 수정 →</Link>
 </>;
}

export function RoadmapSteps({ result, saving, onToggle }) {
 const byId = Object.fromEntries(result.roadmap.map(step => [step.step_id, step]));
 const { byId: courses } = coursePresentation(result.recommended_courses);
 return <><h2>실행 로드맵</h2><p role="status">작업 완료 {result.progress.completed} / {result.progress.total}개</p>
  <progress aria-label="사용자가 체크한 작업 완료 비율" max={result.progress.total} value={result.progress.completed}/>
  <p className="field-help">순서는 추천 활동 간의 학습 흐름입니다. 학교 공식 선수과목이나 수강 학기를 뜻하지 않습니다.</p>
  <ConfirmationQuestions items={unconfirmed(result)}/>
  <ol className="skill-list">{result.roadmap.map(step => <li className="skill-card" key={step.step_id}>
   <h3>{step.order}단계 · {step.title}</h3><p><b>목적</b> {step.purpose}</p><p><b>추천 이유</b> {step.reason}</p>
   <p>{step.related_skills.map(name => <span className="badge" key={name}>{name}</span>)}</p>
   {step.related_course_ids.length > 0 && <p>관련 수강 후보: {relatedCourseNames(step.related_course_ids, courses).join(', ')}</p>}
   <p className="field-help">선행 활동: {step.depends_on.length ? step.depends_on.map(id => `${byId[id].order}단계 ${byId[id].title}`).join(', ') : '없음'}</p>
   <ul className="roadmap-tasks">{step.tasks.map(task => <li key={task.task_id}>
    <label className="roadmap-task-label"><input type="checkbox" checked={task.is_completed} disabled={saving} onChange={() => onToggle(task)}/><b>{task.title}</b></label>
    <p>{task.action}</p><p><b>완료 기준</b> {task.completion_criteria}</p><p><b>완료할 결과물</b> {task.deliverable}</p>
   </li>)}</ul><Evidence refs={step.evidence_refs} result={result}/>
  </li>)}</ol></>;
}

export function CourseCandidates({ result }) {
 const catalog = result.basis.catalog;
 const { cards } = coursePresentation(result.recommended_courses);
 return <><h2>수강 후보</h2><p>이 로드맵 실행의 경험·이수 선택 기준으로 생성한 개인화 후보입니다.</p>
  {result.course_status === 'evidence_unavailable' ? <p className="notice">검증된 직무 근거가 없어 수강 후보 추천을 보류했습니다. 직무 분석 후 로드맵을 다시 생성해 주세요.</p> : result.course_status === 'catalog_unavailable' ? <p className="notice">과목 목록을 사용할 수 없어 수강 후보를 생성하지 않았습니다.</p> : <>
   {catalog.source_url?.startsWith('https://') && <p><a href={catalog.source_url} target="_blank" rel="noopener noreferrer">과목 목록 출처 ↗</a></p>}
   {result.basis.review_status === 'unconfirmed' && <p className="notice">이수 선택 확인 전의 잠정 후보입니다. 미이수로 확정하지 않습니다. <Link href="/input/courses">이수 선택 확인 →</Link></p>}
   {result.basis.review_status === 'partial' && <p className="notice">현재 목록에 누락된 과목이 있습니다. 이수 선택 확인은 현재 목록 안에 한정됩니다.</p>}
   {result.recommended_courses.length === 0 && <p>현재 근거와 미선택 과목에서 추천할 후보를 찾지 못했습니다.</p>}
   {result.recommended_courses.length > 0 && result.recommended_courses.length < 5 && <p className="notice">이수 및 대체과목을 제외하면 추천 가능한 고유 과목이 {result.recommended_courses.length}개입니다.</p>}
  </>}
  <ul className="skill-list">{cards.map(course => <li className="skill-card" key={course.course_id}>
   <h3>{course.course_name} <span className="badge">{course.recommendation_label || course.course_code || '코드 미제공'}</span></h3>
   <div className="recommendation-reason"><p><b>공식 교육과정에서 확인한 학습 내용</b></p><p>{courseLearning(course)}</p><p><b>목표와의 연결</b> {courseReason(course)}</p></div>
   <p>{course.credits == null ? '학점 미제공' : `${course.credits}학점`}{course.recommended_year ? ` · 교육과정 권장 ${course.recommended_year}학년` : ''}{course.recommended_term ? ` ${course.recommended_term}` : ''}</p>
   {(course.keyword_evidence || []).some(item => item.keyword_role === 'prerequisite') && <p><b>수강 전 확인:</b> {(course.keyword_evidence || []).filter(item => item.keyword_role === 'prerequisite').map(item => item.keyword).join(', ')}</p>}
   <details><summary>공식 근거와 출처 쪽수</summary><p>{course.course_evidence}{course.evidence_page_start ? ` · ${course.evidence_page_start}쪽${course.evidence_page_end && course.evidence_page_end !== course.evidence_page_start ? `–${course.evidence_page_end}쪽` : ''}` : ''}</p>{(course.keyword_evidence || []).map((item, i) => <p key={i}>{item.keyword} · {({learning:'학습', prerequisite:'사전지식', tool:'도구', example:'예시', context:'배경'})[item.keyword_role]}: {item.evidence_text}{item.evidence_page_start ? ` · ${item.evidence_page_start}쪽` : ''}</p>)}<p>{course.availability_notice}</p><Evidence refs={course.evidence_refs} result={result}/></details>
  </li>)}</ul>
  <p className="field-help">목록 밖에서 보존한 과거 이수 선택 {result.basis.outside_completed_courses.length}개. 현재 수강 후보에는 포함하지 않습니다.</p>
 </>;
}
