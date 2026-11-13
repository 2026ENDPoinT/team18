'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { courseReason, resultTabs, resultHref } from './resultPresentation.mjs';
import { loadResultResources } from './resultData.mjs';
import { pollGeneration } from './generationFlow.mjs';
import GenerationLoading from './GenerationLoading';
import JobSkillAnalysis from './JobSkillAnalysis';
import ActivityRecommendations from './ActivityRecommendations';
import ResultOverview from './ResultOverview';
import { CourseCandidates } from './RoadmapPanels';
import { PageTitle } from '../../components/layout/Shell';
import { apiRequest } from '../../lib/api/client';
import { resolvePlanId } from '../../lib/api/session';

const storageKey = id => `stepup-roadmap-run:${id}`;
function remember(id, runId) { try { if (runId) localStorage.setItem(storageKey(id), runId); else localStorage.removeItem(storageKey(id)); } catch {} }
function remembered(id) { try { return localStorage.getItem(storageKey(id)); } catch { return null; } }
function failureDetail(data) {
 const code = data?.generation_error?.code || data?.error_code;
 if (['comparison_unavailable', 'job_analysis_failed'].includes(code)) return '직무 또는 프로젝트 분석을 확인해 주세요. 입력과 분석 내용을 확인한 후 다시 시도할 수 있습니다.';
 if (code === 'catalog_unavailable') return '수강 추천에 사용할 과목 목록을 선택해 주세요.';
 if (code === 'activity_source_unavailable') return '저장된 활동 자료를 확인하지 못했습니다. 잠시 후 다시 시도해 주세요.';
 if (code === 'revision_conflict') return '생성 중 입력이나 분석 근거가 변경되었습니다. 최신 입력으로 다시 시도해 주세요.';
 if (code === 'generation_expired') return '생성 시간이 만료되었습니다. 다시 시도해 주세요.';
 return '';
}

export default function Result() {
 const router = useRouter(), searchParams = useSearchParams();
 const selected = Math.max(0, resultTabs.findIndex(tab => tab.key === searchParams.get('tab')));
 const selectedTab = resultTabs[selected].key, nextTab = resultTabs[selected + 1];
 const overview = selectedTab === 'roadmap';
 const tabNavigation = useRef(false), generationLock = useRef(false), epoch = useRef(0), previousRunId = useRef(null);
 const wantsGeneration = useRef(searchParams.get('generate') === '1');
 const [resources, setResources] = useState({});
 const [tracking, setTracking] = useState({ phase: 'checking', tasks: {} });
 const [progressBusy, setProgressBusy] = useState(false), [progressError, setProgressError] = useState('');
 const plan = resources.plan?.data, result = resources.roadmap?.data;
 const load = useCallback(async () => {
  const ticket = ++epoch.current, collected = {};
  const receive = (key, value) => {
   collected[key] = value;
   if (ticket === epoch.current) setResources(previous => ({ ...previous,
    [key]: value.phase === 'loading' ? { ...previous[key], ...value } : value }));
  };
  try {
   const id = await resolvePlanId();
   if (!id) throw new Error('계획이 없습니다. 기본 정보를 먼저 입력해 주세요.');
   await loadResultResources((path, options = {}) => apiRequest(path, { ...options, signal: AbortSignal.timeout(15000) }), id, receive);
  } catch (error) {
   for (const key of ['plan', 'roadmap', 'comparison', 'courses']) receive(key, { phase: 'error', message: error.message });
  }
  return collected;
 }, []);

 const startGeneration = useCallback(async (currentPlan, refresh = false, retryRunId = null) => {
  if (!currentPlan || generationLock.current) return;
  generationLock.current = true;
  const previous = previousRunId.current;
  setTracking({ phase: 'starting', planId: currentPlan.request_id, tasks: {} });
  router.replace(resultHref('roadmap'), { scroll: false });
  const base = `/roadmap-inputs/${encodeURIComponent(currentPlan.request_id)}`;
  try {
   const data = await apiRequest(`${base}/roadmap`, { method: 'POST', signal: AbortSignal.timeout(20000),
    body: JSON.stringify({ expected_input_revision: currentPlan.input_revision, refresh, background: true,
     ...(retryRunId ? { retry_run_id: retryRunId } : {}) }) });
   if (!data.run_id) throw new Error('실행 상태를 확인하지 못했습니다.');
   previousRunId.current = data.run_id;
   remember(currentPlan.request_id, data.run_id);
   setTracking({ phase: 'tracking', planId: currentPlan.request_id, runId: data.run_id, tasks: data.generation_tasks || {} });
  } catch (error) {
   // A lost POST response is ambiguous. Check the durable run before any retry.
   try {
    const latest = await apiRequest(`${base}/roadmap`, { signal: AbortSignal.timeout(15000) });
    const active = latest.latest_generation;
    if (active && (active.run_id !== previous || active.status === 'generating' || (retryRunId && active.run_id === retryRunId))) {
     previousRunId.current = active.run_id;
     remember(currentPlan.request_id, active.run_id);
     setTracking({ phase: 'tracking', planId: currentPlan.request_id, runId: active.run_id, tasks: active.generation_tasks || {} });
    } else setTracking({ phase: error.status >= 400 && error.status < 500 ? 'failed' : 'unknown', planId: currentPlan.request_id, tasks: {}, detail: error.message });
   } catch { setTracking({ phase: 'unknown', planId: currentPlan.request_id, tasks: {}, detail: error.message }); }
  } finally { generationLock.current = false; }
 }, [router]);

 useEffect(() => {
  if (searchParams.get('tab') === 'readiness') router.replace(resultHref('roadmap'), { scroll: false });
 }, [router, searchParams]);

 useEffect(() => {
  let disposed = false;
  (async () => {
   const loaded = await load();
   if (disposed) return;
   const currentPlan = loaded.plan?.data, latest = loaded.roadmap?.data;
   if (!currentPlan || loaded.roadmap?.phase === 'error') {
    setTracking({ phase: 'unknown', planId: currentPlan?.request_id, tasks: {} }); return;
   }
   const generation = latest?.latest_generation;
   previousRunId.current = generation?.run_id || latest?.run_id || null;
   const active = generation && (generation.status === 'generating' || !generation.generation_complete && generation.status !== 'failed');
   if (active || (!wantsGeneration.current && generation)) {
    remember(currentPlan.request_id, generation.run_id);
    setTracking({ phase: 'tracking', planId: currentPlan.request_id, runId: generation.run_id, tasks: generation.generation_tasks || {} });
   } else if (wantsGeneration.current) {
    wantsGeneration.current = false;
    await startGeneration(currentPlan, Boolean(latest?.run_id));
   } else if (remembered(currentPlan.request_id)) {
    setTracking({ phase: 'tracking', planId: currentPlan.request_id, runId: remembered(currentPlan.request_id), tasks: {} });
   } else setTracking({ phase: 'idle', tasks: {} });
  })();
  return () => { disposed = true; epoch.current++; };
 }, [load, startGeneration]);

 useEffect(() => {
  if (tracking.phase !== 'tracking' || !tracking.runId) return;
  let disposed = false;
  const { planId, runId } = tracking;
  (async () => {
   const outcome = await pollGeneration({ request: apiRequest, planId, runId, cancelled: () => disposed,
    onState: data => setTracking(previous => ({ ...previous, tasks: data.generation_tasks || previous.tasks })) });
   if (disposed || outcome.kind === 'cancelled') return;
   if (outcome.kind === 'complete') {
    previousRunId.current = runId;
    remember(planId, null);
    setResources(previous => ({ ...previous, roadmap: { phase: 'ready', data: outcome.data },
     comparison: { phase: 'ready', data: outcome.data.skill_comparison } }));
    setTracking({ phase: 'complete', planId, runId, tasks: outcome.data.generation_tasks });
   } else setTracking(previous => ({ ...previous, phase: outcome.kind,
    tasks: outcome.data?.generation_tasks || previous.tasks, detail: failureDetail(outcome.data) }));
  })();
  return () => { disposed = true; };
 }, [tracking.phase, tracking.planId, tracking.runId]);

 const retry = useCallback(async () => {
  if (tracking.phase === 'unknown') {
   if (tracking.runId) { setTracking(previous => ({ ...previous, phase: 'tracking' })); return; }
   if (!plan) { window.location.reload(); return; }
   setTracking(previous => ({ ...previous, phase: 'checking' }));
   try {
    const latest = await apiRequest(`/roadmap-inputs/${encodeURIComponent(plan.request_id)}/roadmap`, { signal: AbortSignal.timeout(15000) });
    if (latest.latest_generation && (latest.latest_generation.status === 'generating' ||
        !latest.latest_generation.generation_complete && latest.latest_generation.status !== 'failed' ||
        latest.latest_generation.run_id !== previousRunId.current)) {
     const item = latest.latest_generation;
     remember(plan.request_id, item.run_id);
     setTracking({ phase: 'tracking', planId: plan.request_id, runId: item.run_id, tasks: item.generation_tasks || {} });
    } else await startGeneration(plan, Boolean(latest.run_id));
   } catch { setTracking(previous => ({ ...previous, phase: 'unknown' })); }
  } else await startGeneration(plan, true, tracking.runId);
 }, [tracking.phase, tracking.runId, plan, startGeneration]);

 const onPlanChange = useCallback(input => {
  setResources(previous => ({ ...previous, plan: { phase: 'ready', data: input } }));
  load();
 }, [load]);
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
  tab?.focus({ preventScroll: true }); tab?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
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
 }
 async function setTask(task) {
  if (progressBusy || !result?.run_id) return;
  setProgressBusy(true); setProgressError('');
  try {
   const data = await apiRequest(`/roadmap-inputs/${encodeURIComponent(plan.request_id)}/roadmaps/${encodeURIComponent(result.run_id)}/tasks/${encodeURIComponent(task.task_id)}`,
    { method: 'PATCH', body: JSON.stringify({ is_completed: !task.is_completed, expected_progress_version: task.progress_version }) });
   setResources(previous => ({ ...previous, roadmap: { phase: 'ready', data } }));
  } catch (error) { setProgressError(error.message); }
  finally { setProgressBusy(false); }
 }
 if (!['idle', 'complete'].includes(tracking.phase)) return <GenerationLoading state={tracking} onRetry={retry}/>;
 const hasResult = ['success', 'partial'].includes(result?.status) && !!result?.roadmap && !result.details_restricted;
 const activities = result?.activity_recommendations
  ? { phase: 'ready', data: result.activity_recommendations, message: '' }
  : { phase: 'error', data: null, message: '저장된 활동 추천이 없습니다. 로드맵을 다시 생성해 주세요.' };
 const displayedResources = result?.skill_comparison
  ? { ...resources, comparison: { phase: 'ready', data: result.skill_comparison } } : resources;
 const reasons = Object.fromEntries(result?.course_reasons?.map(reason => [reason.course_id, reason.personalization_reason]) ||
  (result?.recommended_courses || []).map(course => [course.course_id, courseReason(course)]));
 return <div className="result-page">
  <div className="result-generation-heading"><PageTitle title="로드맵 결과" helpId={`result-${selectedTab}`}/>
   <button className="primary" disabled={!plan || resources.roadmap?.phase === 'loading'} onClick={() => startGeneration(plan, hasResult)}>{hasResult ? '재분석' : '로드맵 만들기'}</button></div>
  {hasResult && !result.generation_complete && <p className="notice">이전에 저장한 결과입니다. 모든 추천을 함께 저장하려면 재분석을 실행해 주세요.</p>}
  <div className="result-tabs" role="tablist" aria-label="결과 구성" onKeyDown={onKeyDown}>{resultTabs.map((tab, i) => <button key={tab.key} type="button" role="tab" id={`tab-${i}`} data-index={i} aria-controls="result-panel" aria-selected={selected === i} tabIndex={selected === i ? 0 : -1} onClick={() => changeTab(i)}>{tab.label}</button>)}</div>
  <section id="result-panel" role="tabpanel" tabIndex={0} aria-labelledby={`tab-${selected}`} className={overview ? 'result-overview-panel' : 'result-panel skill-panel'}>
   <JobSkillAnalysis active={selectedTab === 'skills'} savedComparison={result?.skill_comparison} savedRunId={result?.run_id} onResult={onSkillResult} plan={plan} onPlanChange={onPlanChange}/>
   {selectedTab === 'activities' && <ActivityRecommendations active resource={activities}/>}
   {overview && <ResultOverview resources={displayedResources} reload={load} activities={activities}/>}
   {overview && <section className="result-roadmap-steps" aria-labelledby="execution-steps-title"><h2 id="execution-steps-title">실행 로드맵</h2>
    {!hasResult && <p>아직 저장된 실행 로드맵이 없습니다. 로드맵을 만들어 주세요.</p>}
    {result?.is_stale && <p className="notice">이전 입력을 기준으로 저장된 로드맵입니다. 재분석으로 최신 결과를 만들 수 있어요.</p>}
    {hasResult && <ol className="execution-steps">{result.roadmap.map(step => <li className="skill-card" key={step.step_id}><h3>{step.title}</h3><p>{step.purpose}</p><p>{step.reason}</p><ul>{step.tasks.map(task => <li key={task.task_id}><label><input type="checkbox" checked={!!task.is_completed} disabled={progressBusy} onChange={() => setTask(task)}/> {task.action}</label><p className="field-help">완료 기준: {task.completion_criteria} · 결과물: {task.deliverable}</p></li>)}</ul></li>)}</ol>}
    {progressError && <p role="alert">{progressError}</p>}</section>}
   {selectedTab === 'courses' && <>
    {result?.course_reasons_source === 'catalog_evidence_fallback' && <p className="notice" role="status">AI 수강 추천 이유를 생성하지 못해, 확인된 교육과정 내용을 바탕으로 작성한 기본 추천 근거를 표시합니다. 실제 개설과 수강 가능 여부는 별도로 확인해 주세요.</p>}
    {resources.roadmap?.phase === 'loading' && <p role="status">저장된 결과를 불러오고 있습니다…</p>}
    {resources.roadmap?.phase === 'error' && <p role="alert">{resources.roadmap.message}</p>}
    {result?.is_stale && <p className="notice" role="status">이 수강 후보는 이전 입력·분석 기준으로 저장된 결과입니다.</p>}
    {result?.details_restricted && <p className="notice">문서 삭제·재추출 등으로 근거가 변경되어 저장된 수강 후보의 상세 내용을 확인할 수 없습니다.</p>}
    {hasResult && resources.courses?.phase === 'ready' ? <CourseCandidates result={result} selectedCourses={resources.courses.data?.selected_courses} courseReasons={{ phase: 'ready', reasons }}/> : !result?.details_restricted && <p>아직 표시할 수강 후보가 없습니다. 로드맵을 만들어 주세요.</p>}
   </>}
  </section>
  {!overview && <nav className="result-pagination" aria-label="로드맵 결과 순서 이동"><span className="field-help">{selected + 1} / {resultTabs.length} · {resultTabs[selected].label}</span>
   <div>{selected > 0 && <button type="button" onClick={() => changeTab(selected - 1, true)}>← 이전: {resultTabs[selected - 1].label}</button>}{nextTab ? <button type="button" className="primary" onClick={() => changeTab(selected + 1, true)}>다음: {nextTab.label} →</button> : <button type="button" className="primary" onClick={() => changeTab(0, true)}>결과 확인 완료 · 실행 로드맵 →</button>}</div></nav>}
 </div>;
}
