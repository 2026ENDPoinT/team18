'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { resultTabs, resultHref } from './resultPresentation.mjs';
import JobSkillAnalysis from './JobSkillAnalysis';
import ActivityRecommendations from './ActivityRecommendations';
import { Preparation, RoadmapSteps, CourseCandidates, NextTask } from './RoadmapPanels';
import { Heading } from '../../components/layout/Shell';
import { apiRequest } from '../../lib/api/client';
import { resolvePlanId } from '../../lib/api/session';
import { roadmapErrorMessage } from './roadmapErrors.mjs';

const tabs = resultTabs.map(tab => tab.label);
export default function Result() {
 const router = useRouter(), searchParams = useSearchParams();
 const selected = Math.max(0, resultTabs.findIndex(tab => tab.key === searchParams.get('tab')));
 const [plan, setPlan] = useState(null);
 const [result, setResult] = useState(null), [history, setHistory] = useState([]);
 const [phase, setPhase] = useState('loading'), [message, setMessage] = useState('');
 const [saving, setSaving] = useState(false), [skillResult, setSkillResult] = useState(null);
 const [activityResult, setActivityResult] = useState(null);
 const toggleLock = useRef(false);
 const epoch = useRef(0), selectedRun = useRef(''), generating = useRef(false);
 const load = useCallback(async (runId = selectedRun.current) => {
  const ticket = ++epoch.current;
  try {
   const id = await resolvePlanId();
   if (!id) throw new Error('계획이 없습니다. 기본 정보를 먼저 입력해 주세요.');
   const base = `/roadmap-inputs/${encodeURIComponent(id)}`;
   const [input, data, runs] = await Promise.all([
    apiRequest(base), apiRequest(runId ? `${base}/roadmaps/${encodeURIComponent(runId)}` : `${base}/roadmap`), apiRequest(`${base}/roadmaps`),
   ]);
   if (ticket !== epoch.current) return;
   setPlan(input); setResult(data); setHistory(runs.runs || []); setPhase('ready');
  } catch (error) {
   if (ticket !== epoch.current) return;
   setResult(null); setPlan(null); setHistory([]); setMessage(error.message); setPhase('error');
  }
 }, []);
 useEffect(() => { load(); return () => { epoch.current++; }; }, [load]);
 useEffect(() => {
  const refresh = () => { if (phase !== 'generating' && !saving) load(); };
  window.addEventListener('focus', refresh);
  return () => window.removeEventListener('focus', refresh);
 }, [load, phase, saving]);
 const pending = history.some(r => r.status === 'generating' && !r.generation_expired);
 useEffect(() => {
  if (!pending || phase === 'generating') return;
  const timer = setInterval(() => load(), 5000);
  return () => clearInterval(timer);
 }, [pending, phase, load]);
 const onPlanChange=useCallback(input=>{
  epoch.current++;setPlan(input);setSkillResult(null);setActivityResult(null);
  setResult(previous=>previous?.run_id?{...previous,is_stale:true,current_input_revision:input.input_revision}:previous);
 },[]);
 const onSkillResult = useCallback(data => { setSkillResult(data); if (data && !generating.current) load(); }, [load]);
 function changeTab(index) { router.push(resultHref(resultTabs[index].key), { scroll: false }); if (phase !== 'generating' && !saving) load(); }
 function onKeyDown(e) {
  let next;
  if (e.key === 'ArrowRight') next = (selected + 1) % tabs.length;
  else if (e.key === 'ArrowLeft') next = (selected + tabs.length - 1) % tabs.length;
  else if (e.key === 'Home') next = 0;
  else if (e.key === 'End') next = tabs.length - 1;
  else return;
  e.preventDefault(); changeTab(next); document.getElementById(`tab-${next}`)?.focus();
 }
 async function generate(refresh) {
  if (!plan || generating.current) return;
  generating.current = true; ++epoch.current; setPhase('generating'); setMessage('');
  try {
   const data = await apiRequest(`/roadmap-inputs/${plan.request_id}/roadmap`, {
    method: 'POST', body: JSON.stringify({ expected_input_revision: plan.input_revision, refresh }),
   });
   selectedRun.current = ''; setResult(data); router.push(resultHref('roadmap'), { scroll: false });
   await load('');
  } catch (error) { setMessage(roadmapErrorMessage(error)); await load(); }
  finally { generating.current = false; }
 }
 async function toggle(task) {
  if (toggleLock.current) return;
  toggleLock.current = true;
  ++epoch.current; setSaving(true); setMessage('');
  try {
   const data = await apiRequest(`/roadmap-inputs/${plan.request_id}/roadmaps/${result.run_id}/tasks/${encodeURIComponent(task.task_id)}`, {
    method: 'PATCH', body: JSON.stringify({ is_completed: !task.is_completed, expected_progress_version: task.progress_version }),
   });
   setResult(data);
  } catch (error) { setMessage(error.message); await load(result.run_id); }
  finally { toggleLock.current = false; setSaving(false); }
 }
 const usable = result?.roadmap && !result.details_restricted;
 const busy = phase === 'generating' || phase === 'loading' || saving;
 const displayed = selected === 4 ? activityResult : selected === 1 ? skillResult : result;
 const displayedGoal = plan?.input?.career_goal || displayed?.career_goal;
 return <>
  <div className="result-head"><Heading number="06" title="로드맵 결과" helpId={`result-${resultTabs[selected].key}`} description="입력 기준에 따른 결과 화면입니다."/><Link href="/input/basic" className="button">입력 수정</Link></div>
  <div className="result-summary result-goal"><div><span>진로 목표</span><strong>{displayedGoal || '입력 확인 중'}</strong></div></div>
  <div className="result-tabs" role="tablist" aria-label="결과 구성" onKeyDown={onKeyDown}>{tabs.map((tab, i) => <button key={tab} role="tab" id={`tab-${i}`} aria-controls="result-panel" aria-selected={selected === i} tabIndex={selected === i ? 0 : -1} onClick={() => changeTab(i)}>{tab}</button>)}</div>
  <section id="result-panel" role="tabpanel" aria-labelledby={`tab-${selected}`} className="empty-state skill-panel">
   <JobSkillAnalysis active={selected === 1} onResult={onSkillResult} plan={plan} onPlanChange={onPlanChange}/>
   <ActivityRecommendations active={selected === 4} inputRevision={plan?.input_revision} onResult={setActivityResult}/>
   {selected !== 1 && selected !== 4 && <>
    {usable && (selected === 0 || selected === 2) && <NextTask result={result} saving={busy} onToggle={toggle}/>}
    <div className="doc-actions roadmap-controls"><button className="primary" onClick={() => generate(false)} disabled={busy || pending || !plan}>{result?.limited_guidance_available ? '제한 안내 로드맵 생성' : '로드맵 생성'}</button>
     {history.some(r => ['success', 'partial'].includes(r.status)) && <button onClick={() => generate(true)} disabled={busy || pending || !plan}>현재 입력으로 다시 분석</button>}
     <button onClick={() => load()} disabled={busy}>저장 결과 새로고침</button>
    </div>
    {phase === 'loading' && <p role="status">저장된 결과를 불러오고 있습니다…</p>}
    {phase === 'generating' && <p role="status">확인된 경험과 과목 정보를 바탕으로 로드맵을 생성하고 있습니다…</p>}
    {message && <p role="alert">{message}</p>}
    {(result?.limited_guidance_available || result?.status === 'needs_job_analysis') && <div className="notice">검증된 직무 분석이 없어 진로 목표·교육과정 기준의 수강 후보와 제한 안내를 제공합니다. 기술별 준비 상태는 판단하지 않습니다. <button onClick={() => changeTab(1)}>직무 역량 비교에서 분석하기</button></div>}
    {pending && phase !== 'generating' && <p role="status">진행 중인 생성 요청이 있습니다. 저장 결과를 확인하고 있습니다.</p>}
    {result?.generation_expired && <p role="status">이전 생성 요청의 유효 시간이 지났습니다. 다시 생성할 수 있습니다.</p>}
    {history.length > 0 && <label className="field">결과 이력<select aria-label="결과 이력" value={selectedRun.current} disabled={busy} onChange={e => { selectedRun.current = e.target.value; load(e.target.value); }}>
     <option value="">최신 유효 결과 우선</option>{history.map(r => <option key={r.run_id} value={r.run_id}>{new Date(r.created_at).toLocaleString('ko-KR')} · {r.status === 'failed' ? '생성 실패' : r.status === 'generating' ? '생성 중' : r.is_stale ? '이전 기준' : '현재 기준'}{r.details_restricted ? ' · 상세 제한' : ''}</option>)}
    </select></label>}
    {result?.is_stale && <p className="notice" role="status">이 결과는 이전 입력·분석 기준입니다. 현재 입력으로 다시 분석하면 새 이력이 생성되며 완료 체크는 옮겨지지 않습니다.</p>}
    {result?.details_restricted && <p className="notice">문서 삭제·재추출 등으로 근거가 변경되어 과거 결과의 상세 내용과 완료 체크 접근을 제한했습니다.</p>}
    {result?.status === 'failed' && <p role="status">{roadmapErrorMessage(result)}</p>}
    {usable ? selected === 0 ? <Preparation result={result}/> : selected === 2 ? <RoadmapSteps result={result} saving={busy} onToggle={toggle}/> : <CourseCandidates result={result}/> : !result?.details_restricted && <p>아직 표시할 로드맵 결과가 없습니다. 분석 근거를 확인한 후 로드맵을 생성해 주세요.</p>}
   </>}
  </section>
  <footer className="footer"><span className="field-help">완료 체크는 실행 기록이며 기술 숙련도나 취업 준비 점수가 아닙니다.</span><Link className="button" href="/input/review">경험 확인·수정</Link></footer>
 </>;
}
