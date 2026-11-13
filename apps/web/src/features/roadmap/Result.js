'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { resultTabs, resultHref, roadmapDetailHref } from './resultPresentation.mjs';
import { loadResultResources } from './resultData.mjs';
import JobSkillAnalysis from './JobSkillAnalysis';
import ActivityRecommendations from './ActivityRecommendations';
import ResultOverview from './ResultOverview';
import RoadmapHistory from './RoadmapHistory';
import { RoadmapSteps, CourseCandidates, NextTask } from './RoadmapPanels';
import { PageTitle } from '../../components/layout/Shell';
import { apiRequest } from '../../lib/api/client';
import { resolvePlanId } from '../../lib/api/session';
import { roadmapErrorMessage } from './roadmapErrors.mjs';

export default function Result() {
 const router = useRouter(), searchParams = useSearchParams();
 const selected = Math.max(0, resultTabs.findIndex(tab => tab.key === searchParams.get('tab')));
 const selectedTab = resultTabs[selected].key, nextTab = resultTabs[selected + 1];
 const overview = selectedTab === 'roadmap' && searchParams.get('view') !== 'steps';
 const tabNavigation = useRef(false);
 const [resources, setResources] = useState({});
 const [message, setMessage] = useState(''), [saving, setSaving] = useState(false), [generating, setGenerating] = useState(false);
 const toggleLock = useRef(false), generationLock = useRef(false), epoch = useRef(0);
 const plan = resources.plan?.data, result = resources.roadmap?.data;
 const phase = resources.roadmap?.phase || 'loading';
 const load = useCallback(async () => {
  const ticket = ++epoch.current;
  const receive = (key, value) => {
   if (ticket === epoch.current) setResources(previous => ({ ...previous,
    [key]: value.phase === 'loading' ? { ...previous[key], ...value } : value,
   }));
  };
  try {
   const id = await resolvePlanId();
   if (!id) throw new Error('계획이 없습니다. 기본 정보를 먼저 입력해 주세요.');
   await loadResultResources(apiRequest, id, receive);
  } catch (error) {
   for (const key of ['plan', 'roadmap', 'comparison', 'courses']) receive(key, { phase: 'error', message: error.message });
  }
 }, []);
 useEffect(() => { load(); return () => { epoch.current++; }; }, [load]);
 useEffect(() => {
  const refresh = () => { if (!generationLock.current && !toggleLock.current) load(); };
  window.addEventListener('focus', refresh);
  return () => window.removeEventListener('focus', refresh);
 }, [load]);
 const pending = result?.generation_pending || (result?.status === 'generating' && !result.generation_expired);
 useEffect(() => {
  if (!pending || generating) return;
  const timer = setInterval(load, 5000);
  return () => clearInterval(timer);
 }, [pending, generating, load]);
 const onPlanChange = useCallback(input => {
  setResources(previous => ({ ...previous, plan: { phase: 'ready', data: input } }));
  load();
 }, [load]);
 // JobSkillAnalysis already reads on a tab visit. Only update the comparison here;
 // navigation must not refetch the roadmap or invoke a generator.
 const onSkillResult = useCallback((data, { changed = false } = {}) => {
  if (data?.comparison) setResources(previous => ({ ...previous, comparison: { phase: 'ready', data: data.comparison } }));
  if (changed) load();
 }, [load]);
 function changeTab(index, fromFooter = false) {
  tabNavigation.current = fromFooter;
  router.push(resultHref(resultTabs[index].key), { scroll: false });
 }
 useEffect(() => {
  if (!tabNavigation.current) return;
  tabNavigation.current = false;
  const tab = document.getElementById(`tab-${selected}`);
  tab?.focus({ preventScroll: true });
  tab?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
 }, [selected]);
 function onKeyDown(e) {
  const current = Number(e.target.dataset.index);
  let next;
  if (e.key === 'ArrowRight') next = (current + 1) % resultTabs.length;
  else if (e.key === 'ArrowLeft') next = (current + resultTabs.length - 1) % resultTabs.length;
  else if (e.key === 'Home') next = 0;
  else if (e.key === 'End') next = resultTabs.length - 1;
  else return;
  e.preventDefault(); changeTab(next);
  document.getElementById(`tab-${next}`)?.focus({ preventScroll: true });
  document.getElementById(`tab-${next}`)?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
 }
 async function generate(refresh) {
  if (!plan || generationLock.current) return;
  generationLock.current = true; ++epoch.current; setGenerating(true); setMessage('');
  try {
   await apiRequest(`/roadmap-inputs/${plan.request_id}/roadmap`, {
    method: 'POST', body: JSON.stringify({ expected_input_revision: plan.input_revision, refresh }),
   });
   router.push(roadmapDetailHref, { scroll: false });
  } catch (error) { setMessage(roadmapErrorMessage(error)); }
  finally { await load(); generationLock.current = false; setGenerating(false); }
 }
 async function toggle(task) {
  if (toggleLock.current || !plan || !result?.run_id) return;
  toggleLock.current = true; ++epoch.current; setSaving(true); setMessage('');
  try {
   const data = await apiRequest(`/roadmap-inputs/${plan.request_id}/roadmaps/${result.run_id}/tasks/${encodeURIComponent(task.task_id)}`, {
    method: 'PATCH', body: JSON.stringify({ is_completed: !task.is_completed, expected_progress_version: task.progress_version }),
   });
   setResources(previous => ({ ...previous, roadmap: { phase: 'ready', data } }));
  } catch (error) { setMessage(error.message); await load(); }
  finally { toggleLock.current = false; setSaving(false); }
 }
 const usable = result?.roadmap && !result.details_restricted;
 const hasResult = ['success', 'partial'].includes(result?.status);
 const busy = generating || phase === 'loading' || saving || !plan;
 return <div className="result-page">
  <PageTitle title="로드맵 결과" helpId={`result-${selectedTab}`}/>
  <div className="result-tabs" role="tablist" aria-label="결과 구성" onKeyDown={onKeyDown}>{resultTabs.map((tab, i) => <button key={tab.key} type="button" role="tab" id={`tab-${i}`} data-index={i} aria-controls="result-panel" aria-selected={selected === i} tabIndex={selected === i ? 0 : -1} onClick={() => changeTab(i)}>{tab.label}</button>)}</div>
  <section id="result-panel" role="tabpanel" tabIndex={0} aria-labelledby={`tab-${selected}`} className={overview ? 'result-overview-panel' : 'result-panel skill-panel'}>
   <JobSkillAnalysis active={selectedTab === 'skills'} onResult={onSkillResult} plan={plan} onPlanChange={onPlanChange}/>
   {selectedTab === 'activities' && <ActivityRecommendations active inputRevision={plan?.input_revision}/>}
   {overview && <ResultOverview resources={resources} reload={load}/>}
   {!overview && (selectedTab === 'roadmap' || selectedTab === 'courses') && <>
    {selectedTab === 'roadmap' && <Link className="summary-link" href={resultHref('roadmap')}>← 로드맵 요약</Link>}
    {usable && selectedTab === 'roadmap' && <NextTask result={result} saving={busy} onToggle={toggle}/>}
    <div className="doc-actions roadmap-controls"><button className="primary" onClick={() => generate(hasResult)} disabled={busy || pending || !plan}>{hasResult ? '현재 입력으로 다시 분석' : result?.limited_guidance_available ? '제한 안내 로드맵 생성' : '로드맵 생성'}</button>
     <button onClick={load} disabled={busy}>저장 결과 새로고침</button>
    </div>
    {phase === 'loading' && <p role="status">저장된 결과를 불러오고 있습니다…</p>}
    {phase === 'error' && <p role="alert">{resources.roadmap.message}</p>}
    {generating && <p role="status">확인된 경험과 과목 정보를 바탕으로 로드맵을 생성하고 있습니다…</p>}
    {message && <p role="alert">{message}</p>}
    {(result?.limited_guidance_available || result?.status === 'needs_job_analysis') && <div className="notice">검증된 직무 분석이 없어 진로 목표·교육과정 기준의 수강 후보와 제한 안내를 제공합니다. 기술별 준비 상태는 판단하지 않습니다. <Link href={resultHref('skills')}>직무 역량 비교에서 분석하기 →</Link></div>}
    {pending && !generating && <p role="status">진행 중인 생성 요청이 있습니다. 저장 결과를 확인하고 있습니다.</p>}
    {result?.generation_expired && <p role="status">이전 생성 요청의 유효 시간이 지났습니다. 다시 생성할 수 있습니다.</p>}
    {result?.is_stale && <p className="notice" role="status">이 결과는 이전 입력·분석 기준입니다. 현재 입력으로 다시 분석하면 최신 결과로 표시되며, 이전 완료 체크는 반영되지 않습니다.</p>}
    {result?.details_restricted && <p className="notice">문서 삭제·재추출 등으로 근거가 변경되어 과거 결과의 상세 내용과 완료 체크 접근을 제한했습니다.</p>}
    {result?.status === 'failed' && <p role="status">{roadmapErrorMessage(result)}</p>}
    {usable ? selectedTab === 'roadmap' ? <RoadmapSteps result={result} saving={busy} onToggle={toggle}/> : resources.courses?.phase === 'ready' ? <CourseCandidates result={result} selectedCourses={resources.courses.data?.selected_courses}/> : <p role={resources.courses?.phase === 'error' ? 'alert' : 'status'}>{resources.courses?.phase === 'error' ? '현재 이수 과목을 확인하지 못했어요. 저장 결과를 다시 조회해 주세요.' : '현재 이수 과목을 확인하고 있어요…'}</p> : phase === 'ready' && !result?.details_restricted && <p>아직 표시할 로드맵 결과가 없습니다. 분석 근거를 확인한 후 로드맵을 생성해 주세요.</p>}
    {selectedTab === 'roadmap' && plan && <RoadmapHistory key={`${plan.request_id}:${result?.run_id || ''}`} planId={plan.request_id}/>}
   </>}
  </section>
  {!overview && <nav className="result-pagination" aria-label="로드맵 결과 순서 이동">
   <span className="field-help">{selected + 1} / {resultTabs.length} · {resultTabs[selected].label}</span>
   <div>{selected > 0 && <button type="button" onClick={() => changeTab(selected - 1, true)}>← 이전: {resultTabs[selected - 1].label}</button>}{nextTab ? <button type="button" className="primary" onClick={() => changeTab(selected + 1, true)}>다음: {nextTab.label} →</button> : <Link className="button primary" href="/dashboard">결과 확인 완료 · 대시보드 →</Link>}</div>
  </nav>}
 </div>;
}
