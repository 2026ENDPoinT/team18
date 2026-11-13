'use client';
import './courses.css';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Stepper, Heading } from '../../components/layout/Shell';
import { ApiError, apiRequest } from '../../lib/api/client';
import { resolvePlanId } from '../../lib/api/session';
import CourseSelectionDialog from './CourseSelectionDialog';
import { courseYears, filterCourses, loadCourseCatalog, termSections, withPendingSelections } from './courseCatalog.mjs';

function CourseGroupToggle({ label, courses, disabled, toggleMany }) {
 const allSelected = courses.length > 0 && courses.every(course => course.is_completed);
 const selection = allSelected ? 'all' : courses.some(course => course.is_completed) ? 'some' : 'none';
 const action = allSelected ? '전체 해제' : '전체 선택';
 return <button className="course-group-toggle" type="button" data-selection={selection} aria-label={`${label} ${action}`} disabled={disabled || !courses.length} onClick={() => toggleMany(courses.map(course => course.course_id), !allSelected)}>
  <span className="course-group-toggle-icon" aria-hidden="true"><svg width="12" height="12" viewBox="0 0 16 16" fill="none" focusable="false"><path d={selection === 'some' ? 'M4 8h8' : 'm3.5 8 3 3 6-6'} stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/></svg></span>
  <span>{action}</span>
 </button>;
}

function YearTable({ year, courses, visibleIds, disabled, toggle, toggleMany }) {
 const title = year ? `${year}학년` : '학년 미지정';
 const terms = useMemo(() => termSections(courses), [courses]);
 const sections = terms.map(section => ({ ...section, visible: section.courses.filter(course => visibleIds.has(course.course_id)) }));
 const visibleCourses = courses.filter(course => visibleIds.has(course.course_id));
 return <section className="course-year" aria-labelledby={`course-year-${year || 'unknown'}`} data-year={year || 'unknown'}>
  <header className="course-year-heading"><h2 id={`course-year-${year || 'unknown'}`}>{title}</h2><div className="course-year-actions"><span>선택 {courses.filter(c => c.is_completed).length} / 전체 {courses.length}</span><CourseGroupToggle label={title} courses={visibleCourses} disabled={disabled} toggleMany={toggleMany}/></div></header>
  {sections.some(section => section.visible.length) ? <table className="course-year-table" aria-label={`${title} 과목`}><colgroup><col/><col className="course-check-column"/></colgroup>
   {sections.filter(section => section.visible.length).map(section => <tbody key={section.title}>
    <tr className="course-term"><th colSpan={2} scope="colgroup"><div className="course-term-heading"><span>{section.title}</span><div className="course-term-actions"><span>{section.visible.length === section.courses.length ? section.courses.length : `${section.visible.length} / ${section.courses.length}`}과목</span><CourseGroupToggle label={`${title} ${section.title}`} courses={section.visible} disabled={disabled} toggleMany={toggleMany}/></div></div></th></tr>
    {section.visible.map(course => <tr key={course.course_id} className={course.is_completed ? 'is-completed' : ''} data-course-id={course.course_id} onClick={() => { if (!disabled) toggle(course.course_id, !course.is_completed); }}>
     <td><strong className="course-name">{course.course_name}</strong>
     </td>
     <td className="course-check-cell"><button className="course-toggle" type="button" role="switch" aria-label={`${course.course_name} 이미 이수함`} aria-checked={course.is_completed} disabled={disabled} onClick={event => { event.stopPropagation(); toggle(course.course_id, !course.is_completed); }}><span className="course-checkmark" aria-hidden="true">{course.is_completed && <svg width="18" height="18" viewBox="0 0 20 20" fill="none" focusable="false"><path d="m4 10 4 4 8-8" stroke="currentColor" strokeWidth="2.4" strokeLinecap="square" strokeLinejoin="miter"/></svg>}</span></button></td>
    </tr>)}
   </tbody>)}
  </table> : <p className="course-year-empty">{courses.length ? '검색 결과가 없습니다.' : '등록된 과목이 없습니다.'}</p>}
 </section>;
}

export default function Courses() {
 const router = useRouter();
 const [requestId, setRequestId] = useState(null), [catalogId, setCatalogId] = useState(null);
 const [data, setData] = useState(null), [phase, setPhase] = useState('loading'), [message, setMessage] = useState(''), [failure, setFailure] = useState(null);
 const [reviewOpen, setReviewOpen] = useState(false);
 const reviewTrigger = useRef(null);
 const [search, setSearch] = useState(''), [only, setOnly] = useState(false);
 const lock = useRef(false), confirming = useRef(false), missingRef = useRef(false);
 const dataRef = useRef(null), pendingChanges = useRef(new Map()), pendingSave = useRef(null);
 const publish = useCallback((snapshot = dataRef.current, preserveReport = false) => {
  dataRef.current = snapshot;
  setData(withPendingSelections(snapshot, pendingChanges.current));
  if (!preserveReport) missingRef.current = !!snapshot?.reported_missing_courses;
 }, []);

 useEffect(() => {
  let active = true;
  (async () => {
   try {
    const id = await resolvePlanId();
    if (!active) return;
    if (!id) { setPhase('empty'); return; }
    setRequestId(id);
    const plan = await apiRequest(`/roadmap-inputs/${encodeURIComponent(id)}`);
    if (!active) return;
    if (!plan.input.catalog_id) { setPhase('unavailable'); return; }
    setCatalogId(plan.input.catalog_id);
    const result = await loadCourseCatalog(apiRequest, id, plan.input.catalog_id);
    if (active) { publish(result); setPhase('ready'); }
   } catch (error) {
    if (active) { setFailure({ kind: 'load', conflict: error.status === 409 }); setPhase('failed'); setMessage(error.message); }
   }
  })();
  return () => { active = false; };
 }, [publish]);

 async function refresh() {
  if (lock.current || confirming.current) return;
  lock.current = true; setPhase('loading'); setMessage(''); setFailure(null);
  try {
   const plan = await apiRequest(`/roadmap-inputs/${encodeURIComponent(requestId)}`);
   const cid = plan.input.catalog_id;
   if (!cid) { pendingChanges.current.clear(); publish(null); setCatalogId(null); setPhase('unavailable'); return; }
   const latest = await loadCourseCatalog(apiRequest, requestId, cid);
   setCatalogId(cid); pendingChanges.current.clear(); pendingSave.current = null;
   publish(latest); setPhase('ready'); setMessage('최신 선택 상태를 불러왔습니다. 내용을 확인한 뒤 이수 선택 확인을 눌러 주세요.');
  } catch (error) { setFailure({ kind: 'load', conflict: error.status === 409 }); setPhase('failed'); setMessage(error.message); }
  finally { lock.current = false; }
 }

 function savePending() {
  if (lock.current) return pendingSave.current;
  lock.current = true; setPhase('saving'); setFailure(null); setMessage('이수 선택을 저장 중입니다…');
  // One writer owns the revision. New clicks overlay the snapshot and are
  // drained in order, including clicks made while the refreshed GET is pending.
  const operation = (async () => {
   try {
    while (pendingChanges.current.size) {
     const batch = [...pendingChanges.current].slice(0, 100);
     const saved = await apiRequest(`/roadmap-inputs/${encodeURIComponent(requestId)}/course-selections`, {
      method: 'PATCH', body: JSON.stringify({ catalog_id: catalogId, expected_selection_revision: dataRef.current.selection_revision,
       changes: batch.map(([course_id, is_completed]) => ({ course_id, is_completed })) }),
     });
     const latest = await loadCourseCatalog(apiRequest, requestId, catalogId);
     if (latest.selection_revision !== saved.selection_revision || latest.input_revision !== saved.input_revision) throw new ApiError('다른 화면에서 입력이 변경되었습니다.', 409);
     for (const [id, target] of batch) if (pendingChanges.current.get(id) === target) pendingChanges.current.delete(id);
     publish(latest, true);
    }
    if (!confirming.current) { setPhase('ready'); setMessage('이수 선택이 저장되었습니다.'); }
    return true;
   } catch (error) {
    setFailure({ kind: 'toggle', conflict: error.status === 409 }); setPhase('failed');
    setMessage(error.status === 409 ? '다른 화면에서 선택이나 입력이 변경되었습니다. 최신 상태를 불러와 확인해 주세요.' : error.message + ' 다시 저장하거나 최신 상태를 불러와 주세요.');
    return false;
   } finally { lock.current = false; }
  })();
  pendingSave.current = operation;
  return operation;
 }
 function toggle(courseId, target) {
  toggleMany([courseId], target);
 }
 function toggleMany(courseIds, target) {
  if (!['ready', 'saving'].includes(phase) || confirming.current || !dataRef.current || !courseIds.length) return;
  const current = new Map(dataRef.current.courses.map(course => [course.course_id, course.is_completed]));
  let changed = false;
  for (const courseId of courseIds) {
   const selected = pendingChanges.current.has(courseId) ? pendingChanges.current.get(courseId) : current.get(courseId);
   if (selected !== target) { pendingChanges.current.set(courseId, target); changed = true; }
  }
  if (!changed) return;
  publish(dataRef.current, true);
  savePending();
 }
 function openReview() {
  if (!canConfirm || confirming.current) return;
  setReviewOpen(true);
 }
 function closeReview() {
  if (confirming.current) return;
  setReviewOpen(false);
  if (failure?.kind === 'confirm' && !failure.conflict) { setFailure(null); setPhase('ready'); setMessage('선택을 확인한 뒤 다시 진행해 주세요.'); }
 }
 async function confirm() {
  if (!reviewOpen || confirming.current || !dataRef.current || (phase !== 'ready' && !(phase === 'failed' && failure?.kind === 'confirm' && !failure.conflict))) return;
  confirming.current = true; let succeeded = false; setPhase('confirming'); setFailure(null); setMessage('현재 이수 선택을 확인 중입니다…');
  try {
   if (pendingSave.current && !await pendingSave.current) return;
   const latest = dataRef.current;
   await apiRequest(`/roadmap-inputs/${encodeURIComponent(requestId)}/course-selection-review`, { method: 'POST', body: JSON.stringify({ catalog_id: catalogId, expected_selection_revision: latest.selection_revision, expected_input_revision: latest.input_revision, reported_missing_courses: missingRef.current }) });
   succeeded = true; router.push('/input/review');
  } catch (error) {
   setFailure({ kind: 'confirm', conflict: error.status === 409 }); setPhase('failed');
   setMessage(error.status === 409 ? '다른 화면에서 선택이나 입력이 변경되었습니다. 최신 상태를 불러와 확인해 주세요.' : error.message + ' 확인하고 역량 탐색을 다시 눌러 주세요.');
  } finally { if (!succeeded) confirming.current = false; }
 }
 async function continueWithoutCatalog() {
  if (lock.current || phase !== 'unavailable') return;
  lock.current = true; setPhase('loading');
  try {
   const plan = await apiRequest(`/roadmap-inputs/${encodeURIComponent(requestId)}`);
   if (plan.input.catalog_id) {
    const latest = await loadCourseCatalog(apiRequest, requestId, plan.input.catalog_id);
    setCatalogId(plan.input.catalog_id); publish(latest); setPhase('ready'); setMessage('과목 목록 기준이 변경되었습니다. 이수 선택을 확인해 주세요.');
   } else router.push('/input/review');
  } catch (error) { setFailure({ kind: 'load', conflict: error.status === 409 }); setPhase('failed'); setMessage(error.message); }
  finally { lock.current = false; }
 }

 const disabled = !['ready', 'saving'].includes(phase);
 const canConfirm = !!data && (['ready', 'saving'].includes(phase) || (phase === 'failed' && failure?.kind === 'confirm' && !failure.conflict));
 const years = useMemo(() => courseYears(data?.courses || []), [data?.courses]);
 const visible = useMemo(() => data ? filterCourses(data.courses, { search, only }) : [], [data?.courses, search, only]);
 const visibleIds = useMemo(() => new Set(visible.map(course => course.course_id)), [visible]);
 return <div className="course-page"><Stepper current={2} blockForward/><Heading number="04" title="이수 과목" description="학년별 과목을 한눈에 보며 이미 이수한 과목을 체크하세요. 수강 중인 과목은 포함하지 않습니다. 권장 학기와 실제 개설 학기는 다를 수 있어요."/>
  {phase === 'loading' && <div className="notice" role="status">전체 과목 목록을 불러오는 중입니다.</div>}
  {phase === 'empty' && <div className="empty-state"><strong>계획이 없습니다.</strong><p>시작 화면에서 계획을 만들어 주세요.</p><Link className="button" href="/">시작 화면</Link></div>}
  {phase === 'unavailable' && <div className="empty-state"><strong>현재 학교·학과의 과목 목록을 사용할 수 없습니다.</strong><p>이 상태를 이수 과목 0개로 해석하지 않습니다. 기본 정보에서 학교·학과를 확인하거나 과목 목록 없이 계속 진행할 수 있습니다.</p><Link className="button" href="/input/basic">기본 정보 확인</Link></div>}
  {phase === 'failed' && !reviewOpen && <div className="notice" role="alert"><strong>목록 조회 또는 저장을 완료하지 못했습니다.</strong><br/>{message} {failure?.kind === 'toggle' && !failure.conflict && <button onClick={savePending}>다시 저장</button>} {requestId ? <button onClick={refresh}>최신 상태 불러오기</button> : <Link href="/">시작 화면</Link>}</div>}
  {data && <>
   <section className="course-toolbar" aria-label="과목 검색 및 필터">
    <div className="filters"><input aria-label="과목 검색" placeholder="과목 검색" maxLength={100} value={search} onChange={event => setSearch(event.target.value)}/>
     <label className="check-line"><input type="checkbox" checked={only} onChange={event => setOnly(event.target.checked)}/>선택한 과목만 보기</label>
    </div>
    <p className="field-help" role="status">검색 결과 {visible.length}개 · 전체 {data.total}과목</p>
    <p className="field-help course-bulk-help">전체 선택·해제는 현재 검색·필터 결과에 표시된 해당 학년·학기의 과목에만 적용됩니다.</p>
   </section>
   <div className="course-year-grid">{years.map(group => <YearTable key={group.year || 'unknown'} {...group} visibleIds={visibleIds} disabled={disabled} toggle={toggle} toggleMany={toggleMany}/>)}</div>
   <div className="course-confirm-bar" aria-label="이수 선택 확인 영역">
    <div className="course-confirm-row"><div className="course-confirm-summary"><strong aria-live="polite">선택 {data.selection_summary.count}과목</strong>
     <p className="field-help course-save-status" role="status">{phase === 'saving' ? '선택을 저장 중입니다… 계속 체크할 수 있어요.' : phase === 'confirming' ? '선택 확인 중…' : phase === 'failed' ? '저장 상태를 확인해 주세요.' : message || '선택은 자동 저장됩니다. 0개를 선택해도 계속할 수 있어요.'}</p>
    </div><button ref={reviewTrigger} className="primary" aria-haspopup="dialog" aria-expanded={reviewOpen} disabled={!canConfirm} onClick={openReview}>이수 선택 확인</button></div>
   </div>
   {reviewOpen && <CourseSelectionDialog data={data} missing={missingRef.current} phase={phase} failure={failure} message={message} trigger={reviewTrigger} canConfirm={canConfirm && phase !== 'saving'} onConfirm={confirm} onClose={closeReview} onRetrySave={savePending} onRefresh={() => { closeReview(); refresh(); }}/>}
  </>}
  <footer className="footer"><div><Link className="button" href="/input/documents">이전</Link></div>{phase === 'unavailable' && <button className="primary" onClick={continueWithoutCatalog}>수강 제안 없이 계속</button>}</footer>
 </div>;
}
