'use client';
import Link from 'next/link';
import ActivityRecommendations from './ActivityRecommendations';
import { courseReason, relatedRoles, resultHref, roadmapDetailHref } from './resultPresentation.mjs';
import { recommendedCourseCards } from './coursePresentation.mjs';

function ResourceMessage({ resource, loading, error, retry }) {
 if (!resource || resource.phase === 'loading') return <p role="status">{loading}</p>;
 if (resource.phase === 'error') return <div><p role="alert">{error}</p><button onClick={retry}>다시 조회</button></div>;
 return null;
}

export default function ResultOverview({ resources, reload }) {
 const { plan: profile, roadmap, comparison, courses: selection } = resources;
 const plan = profile?.data, input = plan?.input, result = roadmap?.data;
 const ready = profile?.phase === 'ready', courseReady = roadmap?.phase === 'ready' && selection?.phase === 'ready';
 const courses = recommendedCourseCards(result, selection?.data?.selected_courses);
 const roles = relatedRoles(comparison?.data);
 const hasRun = Boolean(result?.roadmap) && !result.details_restricted;
 return <div className="result-overview">
  <section className="result-card result-basic" aria-labelledby="result-basic-title">
   <div className="result-card-heading"><h2 id="result-basic-title">기본 정보</h2><Link className="summary-link" href="/input/basic" aria-label="기본 정보 수정">수정 →</Link></div>
   <ResourceMessage resource={profile} loading="기본 정보를 불러오는 중이에요…" error="기본 정보를 불러오지 못했어요." retry={reload}/>
   {ready && <dl className="result-basic-fields">
    <div><dt>희망 직무</dt><dd>{input.target_role || '아직 정하지 않았어요'}</dd></div>
    <div className="result-basic-goal"><dt>목표·관심 분야</dt><dd>{input.career_goal || '목표·관심 분야를 입력해 주세요.'}</dd></div>
   </dl>}
  </section>
  <section className="result-card result-course-summary" aria-labelledby="result-course-title">
   <h2 id="result-course-title">이수 추천과목</h2>
   <ResourceMessage resource={roadmap?.phase === 'ready' ? selection : roadmap} loading="수강 추천을 불러오는 중이에요…" error="수강 추천을 불러오지 못했어요." retry={reload}/>
   {courseReady && <>
    {result?.details_restricted ? <p role="status">근거가 변경되어 이 결과를 확인할 수 없어요.</p>
     : result?.status === 'failed' ? <p role="alert">로드맵 생성을 완료하지 못했어요. 상세 화면에서 다시 생성해 주세요.</p>
     : !hasRun ? <p role="status">{result?.generation_pending || result?.status === 'generating' ? '요청한 로드맵을 생성하고 있어요.' : '아직 수강 추천이 없어요.'}</p>
     : <>
      {result.is_stale && <p className="summary-note" role="status">이전 입력 기준의 추천이에요. 현재 이수한 과목은 제외했어요.</p>}
      {courses.length ? <ul className="result-brief-list">{courses.slice(0, 3).map(course => <li key={course.course_id} data-recommended-course={course.course_id}><h3>{course.course_name}</h3><p title={courseReason(course)}>{courseReason(course)}</p></li>)}</ul>
       : <p role="status">{result.course_status === 'catalog_unavailable' ? '추천에 사용할 과목 목록이 없어요.' : result.course_status === 'evidence_unavailable' ? '수강 추천에 필요한 직무 근거가 없어요.' : '현재 조건에 맞는 추천 과목이 없어요.'}</p>}
     </>}
    <Link className="summary-link" href={hasRun ? resultHref('courses') : roadmapDetailHref}>{hasRun ? `전체 ${courses.length}과목·추천 근거 보기 →` : '로드맵 생성하러 가기 →'}</Link>
    {hasRun && !courses.length && <Link className="summary-link" href="/input/courses">과목 목록·이수 선택 확인 →</Link>}
   </>}
  </section>
  <section className="result-card result-role-summary" aria-labelledby="result-role-title">
   <h2 id="result-role-title">관련 직무</h2>
   <ResourceMessage resource={comparison} loading="관련 직무를 불러오는 중이에요…" error="관련 직무를 불러오지 못했어요." retry={reload}/>
   {comparison?.phase === 'ready' && <>
    {roles.length ? <ul className="result-brief-list">{roles.map(role => <li key={role}><h3>{role}</h3></li>)}</ul> : <p role={comparison.data?.job_analysis?.status === 'error' ? 'alert' : 'status'}>{comparison.data?.job_analysis?.status === 'error' ? '직무 분석을 완료하지 못했어요.' : comparison.data?.job_analysis?.status === 'not_started' ? '아직 직무 분석이 없어요.' : '확인된 관련 직무가 없어요.'}</p>}
    <Link className="summary-link" href={resultHref('skills')}>{roles.length ? '직무 역량 비교 보기 →' : '직무 분석하러 가기 →'}</Link>
   </>}
  </section>
  <section className="result-card result-activity-summary" aria-labelledby="result-activity-title">
   <h2 id="result-activity-title">추천 공모전·대외활동</h2>
   <ActivityRecommendations active compact inputRevision={plan?.input_revision}/>
  </section>
  <div className="result-overview-actions"><Link className="button" href={roadmapDetailHref}>실행 작업·완료 기록 보기 →</Link></div>
 </div>;
}
