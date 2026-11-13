'use client';
import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Stepper, Heading, PageTitle } from '../../components/layout/Shell';
import { apiRequest } from '../../lib/api/client';
import { resolvePlanId } from '../../lib/api/session';
import { chooseCatalog } from './catalog-selection.mjs';

const fields = ['career_goal', 'target_role', 'university_id', 'department_id', 'catalog_id'];
function formFrom(input) { return Object.fromEntries(fields.map(k => [k, input[k] == null ? '' : String(input[k])])); }
function toChanges(form) { return Object.fromEntries(fields.map(k => [k, form[k] === '' ? (k === 'career_goal' ? '' : null) : form[k]])); }

export default function BasicForm() {
 const router = useRouter();
 const [goalError, setGoalError] = useState(false);
 const [academicExpanded, setAcademicExpanded] = useState(true);
 const goalRef = useRef(null), schoolRef = useRef(null), changeRef = useRef(null);
 const savedCatalogs = useRef(new Map()), saveLock = useRef(false);
 const [catalogState, setCatalogState] = useState({ key: '', status: 'idle', items: [] });
 const [catalogReload, setCatalogReload] = useState(0);
 const [id, setId] = useState(null), [form, setForm] = useState(null), [revision, setRevision] = useState(null);
 const [reference, setReference] = useState(null), [status, setStatus] = useState('loading');
 const [message, setMessage] = useState(''), [dirty, setDirty] = useState(false);

 async function load(requestId) {
  const plan = await apiRequest(`/roadmap-inputs/${encodeURIComponent(requestId)}`);
  setId(requestId);
  savedCatalogs.current.set(plan.input.department_id, plan.input.catalog_id);
  setForm(formFrom(plan.input));
  setAcademicExpanded(!plan.input.university_id || !plan.input.department_id);
  setGoalError(false);
  setCatalogReload(n => n + 1);
  setRevision(plan.input_revision);
  setDirty(false);
  setStatus(plan.input.career_goal?.trim() ? 'saved' : 'ready');
  setMessage('');
 }
 useEffect(() => {
  let active = true;
  (async () => {
   try {
    const ref = await apiRequest('/reference');
    if (!active) return;
    setReference(ref);
    const requestId = await resolvePlanId();
    if (!active) return;
    if (!requestId) { setStatus('empty'); return; }
    await load(requestId);
   } catch (e) { if (active) { setStatus('error'); setMessage(e.message); } }
  })();
  return () => { active = false; };
 }, []);

 const universityId = form?.university_id, departmentId = form?.department_id;
 useEffect(() => {
  if (!departmentId) { setCatalogState({ key: '', status: 'idle', items: [] }); return; }
  let active = true;
  const controller = new AbortController();
  setCatalogState({ key: departmentId, status: 'loading', items: [] });
  (async () => {
   try {
    const result = await apiRequest(`/departments/${encodeURIComponent(departmentId)}/catalogs`, { signal: controller.signal });
    if (!active) return;
    const items = result.catalogs.filter(c => c.department_id === departmentId && c.is_selectable !== false && c.is_selectable !== 0);
    const catalogId = chooseCatalog(items, savedCatalogs.current.get(departmentId));
    setForm(old => old?.department_id === departmentId && old.university_id === universityId ? { ...old, catalog_id: catalogId } : old);
    if (catalogId !== (savedCatalogs.current.get(departmentId) || '')) setDirty(true);
    setCatalogState({ key: departmentId, status: 'ready', items });
   } catch (e) { if (active) setCatalogState({ key: departmentId, status: 'error', items: [], message: e.message }); }
  })();
  return () => { active = false; controller.abort(); };
 }, [universityId, departmentId, catalogReload]);
 const catalogsReady = !departmentId || (catalogState.key === departmentId && catalogState.status === 'ready');

 useEffect(() => {
  function warn(e) { if (dirty) { e.preventDefault(); e.returnValue = ''; } }
  function navigate(e) {
   const link = e.target.closest('a[href]');
   if (!dirty || !link || e.defaultPrevented || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || link.target === '_blank') return;
   const url = new URL(link.href);
   if (url.pathname === location.pathname && url.search === location.search) return;
   if (!window.confirm('저장하지 않은 변경 사항이 있습니다. 다른 화면으로 이동할까요?')) { e.preventDefault(); e.stopPropagation(); }
  }
  window.addEventListener('beforeunload', warn);
  document.addEventListener('click', navigate, true);
  return () => { window.removeEventListener('beforeunload', warn); document.removeEventListener('click', navigate, true); };
 }, [dirty]);

 function collapseAcademic() {
  setAcademicExpanded(false);
  requestAnimationFrame(() => changeRef.current?.focus({ preventScroll: true }));
 }
 function expandAcademic() {
  setAcademicExpanded(true);
  requestAnimationFrame(() => schoolRef.current?.focus({ preventScroll: true }));
 }
 function update(e) {
  const { name, value } = e.target;
  if (name === 'career_goal' && value.trim()) setGoalError(false);
  setForm(old => ({ ...old, [name]: value, ...(name === 'university_id' ? { department_id: '', catalog_id: '' } : name === 'department_id' ? { catalog_id: '' } : {}) }));
  // Disclosure state only changes presentation; selecting a department is still unsaved.
  if (name === 'department_id' && value) collapseAcademic();
  setDirty(true);
  if (status !== 'conflict') { setStatus('ready'); setMessage(''); }
 }
 async function save(destination) {
  if (saveLock.current || !catalogsReady || status === 'conflict' || status === 'loading') return;
  if (!form.career_goal.trim()) {
   setGoalError(true);
   setMessage('');
   setStatus('ready');
   goalRef.current?.scrollIntoView({ block: 'center' });
   goalRef.current?.focus({ preventScroll: true });
   return;
  }
  setGoalError(false);
  saveLock.current = true;
  setStatus('saving');
  setMessage('');
  try {
   const result = await apiRequest(`/roadmap-inputs/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify({ expected_input_revision: revision, changes: toChanges(form) }) });
   savedCatalogs.current.set(result.input.department_id, result.input.catalog_id);
   setForm(formFrom(result.input));
   setRevision(result.input_revision);
   setDirty(false);
   setStatus('saved');
   if (destination) router.push(destination);
  } catch (e) { setStatus(e.status === 409 ? 'conflict' : 'error'); setMessage(e.message); }
  finally { saveLock.current = false; }
 }
 async function reload() {
  if (dirty && !window.confirm('저장하지 않은 변경 사항을 버리고 최신 내용을 불러올까요?')) return;
  setStatus('loading');
  try { await load(id); } catch (e) { setStatus('error'); setMessage(e.message); }
 }

 if (!form) return <><Stepper current={0} blockForward/><Heading number="02" title="기본 정보" description="진로 목표와 학업 정보를 입력하는 화면입니다."/><div className="notice" role="status">{status === 'loading' ? '불러오는 중입니다…' : status === 'empty' ? '계획이 없습니다. 시작 화면에서 새 계획을 만들어 주세요.' : message}</div><Link className="button" href="/">시작 화면</Link></>;
 const universities = reference?.universities || [];
 const departments = (reference?.departments || []).filter(d => d.university_id === universityId);
 const catalogs = catalogState.key === departmentId ? catalogState.items : [];
 const universityName = universities.find(u => u.university_id === universityId)?.university_name;
 const departmentName = departments.find(d => d.department_id === departmentId)?.department_name;
 const academicComplete = Boolean(universityId && departmentId);
 const academicSummary = [universityName, departmentName].filter(Boolean).join(' · ');
 const saveDisabled = status === 'saving' || status === 'loading' || status === 'conflict' || !catalogsReady;
 const catalogLoading = departmentId && (catalogState.key !== departmentId || catalogState.status === 'loading');
 const catalogError = departmentId && catalogState.key === departmentId && catalogState.status === 'error';
 const catalogEmpty = departmentId && catalogsReady && !catalogs.length;
 const saveStatus = status === 'saving' ? '저장 중' : dirty ? '변경사항 있음' : status === 'saved' ? '저장됨' : '';

 return <div className="basic-page">
  <Stepper current={0} blockForward/>
  <div className="eyebrow">01 / 05</div>
  <PageTitle title="기본 정보"/>
  <form noValidate onSubmit={e => { e.preventDefault(); save(); }}>
   <fieldset className="form-fields" disabled={status === 'saving' || status === 'loading'}>
    <section className="academic-bar" aria-label="학교·학과">
     <div className="academic-summary">
      <span className="academic-summary-text" title={academicSummary || undefined}>{academicSummary || '학교·학과'}{!academicComplete && <small> · 선택</small>}</span>
      {academicExpanded ? academicComplete && <button type="button" className="academic-change" aria-expanded="true" aria-controls="academic-fields" onClick={collapseAcademic}>접기</button> : <button ref={changeRef} type="button" className="academic-change" aria-expanded="false" aria-controls="academic-fields" onClick={expandAcademic}>변경</button>}
     </div>
     <div id="academic-fields" hidden={!academicExpanded}>
      <p className="field-help academic-hint">학교·학과를 선택하면 수강할 과목을 제안해요. 선택하지 않아도 진행할 수 있어요.</p>
      <div className="inline-fields">
       <label className="field"><span>학교 <small>선택</small></span>
        <select ref={schoolRef} name="university_id" value={universityId} onChange={update} disabled={!universities.length}>
         <option value="">{universities.length ? '선택해 주세요' : '등록된 학교 없음'}</option>
         {universities.map(x => <option key={x.university_id} value={x.university_id}>{x.university_name}</option>)}
        </select>
       </label>
       <label className="field"><span>학과 <small>선택</small></span>
        <select name="department_id" value={departmentId} onChange={update} disabled={!departments.length}>
         <option value="">{departments.length ? '선택해 주세요' : universityId ? '등록된 학과 없음' : '학교를 먼저 선택해 주세요'}</option>
         {departments.map(x => <option key={x.department_id} value={x.department_id}>{x.department_name}</option>)}
        </select>
       </label>
      </div>
      {catalogs.length > 1 && <label className="field academic-catalog"><span>연결된 과목 목록 <small>변경 가능</small></span><select name="catalog_id" value={form.catalog_id} onChange={update}>{catalogs.map(x => <option key={x.catalog_id} value={x.catalog_id}>{x.version_label}</option>)}</select></label>}
      {!universities.length && <p className="field-help">현재 선택할 수 있는 학교가 없습니다. 목표만 저장해도 진행할 수 있어요.</p>}
     </div>
     {catalogLoading && <p className="field-help academic-feedback" role="status">학과 과목 목록을 연결하는 중입니다…</p>}
     {catalogError && <p className="field-help academic-feedback" role="alert">{catalogState.message} <button type="button" onClick={() => setCatalogReload(n => n + 1)}>목록 다시 불러오기</button></p>}
     {catalogEmpty && <p className="field-help academic-feedback" role="status">등록된 과목 목록이 없습니다. 계속 진행할 수 있습니다.</p>}
    </section>
    <section className="wire-box career-card" aria-labelledby="career-card-title">
     <h2 id="career-card-title">어떤 일을 해보고 싶나요?</h2>
     <label className="field">
      <span id="career-goal-label">목표·관심 분야 <small>· 필수</small></span>
      <textarea ref={goalRef} rows={3} required aria-labelledby="career-goal-label" aria-invalid={goalError || undefined}
       aria-describedby={goalError ? 'career-goal-error career-goal-help' : 'career-goal-help'} name="career_goal"
       value={form.career_goal} onChange={update} maxLength={10000}
       placeholder="예) 동아리에서 웹 서비스를 개발하며 백엔드 구현에 흥미를 느꼈습니다. 앞으로 데이터베이스와 서버 개발 역량을 키워 백엔드 개발자로 성장하고 싶습니다."/>
      {goalError && <span id="career-goal-error" className="field-error-message" role="alert"><span className="field-error-icon" aria-hidden="true">!</span><span>목표·관심 분야를 입력해 주세요.</span></span>}
      <span id="career-goal-help" className="field-help">직무가 정해지지 않았다면 관심 분야와 해보고 싶은 일을 적어 주세요.</span>
     </label>
     <label className="field target-role-field"><span>희망 직무 <small>· 선택</small></span><input name="target_role" value={form.target_role} onChange={update} maxLength={100} placeholder="예) 데이터 분석가"/></label>
    </section>
   </fieldset>
   <footer className="footer basic-footer">
    <Link className="button" href="/">이전</Link>
    <div className="basic-save-actions">
     <span className="basic-save-status" role="status" aria-live="polite" data-state={status === 'saving' ? 'saving' : dirty ? 'dirty' : status}>{saveStatus}</span>
     <div className="right-actions"><button type="submit" disabled={saveDisabled}>저장</button><button type="button" className="primary" onClick={() => save('/input/documents')} disabled={saveDisabled}>저장 후 다음 →</button></div>
    </div>
   </footer>
   {message && (status === 'error' || status === 'conflict') && <div className="basic-save-error" role="alert">
    <span>{message} 입력한 내용은 유지되어 있어요.{status !== 'conflict' && ' 저장 버튼을 눌러 다시 시도해 주세요.'}</span>
    {status === 'conflict' && <button type="button" onClick={reload}>최신 내용 불러오기</button>}
   </div>}
  </form>
  <div className="basic-activity-shortcut"><button type="button" className="basic-activity-link" onClick={() => save('/result?tab=activities')} disabled={saveDisabled}>저장 후 공모전·대외활동 보기 →</button></div>
 </div>;
}
