'use client';
import Link from 'next/link';
import { PageTitle } from '../../components/layout/Shell';
import { useCallback, useEffect, useRef, useState } from 'react';
import { apiRequest } from '../../lib/api/client';
import { resolvePlanId } from '../../lib/api/session';
import { loadDashboardResources, dashboardCards } from '../../features/roadmap/dashboardData.mjs';

export default function Dashboard() {
 const [state, setState] = useState({ phase: 'loading' });
 const epoch = useRef(0);
 const load = useCallback(async () => {
  const ticket = ++epoch.current;
  setState({ phase: 'loading' });
  try {
   const id = await resolvePlanId();
   if (ticket !== epoch.current) return;
   if (!id) { setState({ phase: 'empty' }); return; }
   const path = `/roadmap-inputs/${encodeURIComponent(id)}`;
   const plan = await apiRequest(path);
   const resources = await loadDashboardResources(apiRequest, plan);
   const current = await apiRequest(path);
   if (ticket !== epoch.current) return;
   if (await resolvePlanId() !== id || current.input_revision !== plan.input_revision || current.activity_basis !== plan.activity_basis) {
    throw new Error('조회 중 계획이 변경되었습니다. 최신 내용을 다시 불러와 주세요.');
   }
   setState({ phase: 'ready', cards: dashboardCards(plan, resources) });
  } catch (error) { if (ticket === epoch.current) setState({ phase: 'error', message: error.message }); }
 }, []);
 useEffect(() => {
  load();
  const refresh = () => { if (document.visibilityState === 'visible') load(); };
  window.addEventListener('focus', refresh);
  window.addEventListener('pageshow', refresh);
  return () => { epoch.current++; window.removeEventListener('focus', refresh); window.removeEventListener('pageshow', refresh); };
 }, [load]);
 return <>
  <div className="eyebrow">MY CAREER</div><PageTitle title="대시보드"/>
  <p className="description">현재 계획에 저장한 내용입니다. 카드를 눌러 확인하거나 이어서 수정하세요.</p>
  {state.phase === 'loading' && <p className="notice" role="status">현재 계획을 불러오는 중입니다…</p>}
  {state.phase === 'error' && <div className="notice" role="alert">{state.message} <button onClick={load}>다시 불러오기</button> <Link href="/">계정 확인</Link></div>}
  {state.phase === 'empty' && <div className="empty-state"><strong>아직 작성한 계획이 없어요</strong><p>관심 분야부터 입력하고 나에게 맞는 활동을 찾아보세요.</p><Link className="button primary" href="/">계획 시작하기</Link></div>}
  {state.phase === 'ready' && <>
   <div className="dashboard-toolbar"><button onClick={load}>최신 내용 불러오기</button></div>
   <div className="dashboard-grid">{state.cards.map(card => <Link key={card.key} href={card.href} className="dashboard-card" aria-labelledby={`dashboard-${card.key}`}>
    <h2 id={`dashboard-${card.key}`}>{card.title}<span aria-hidden="true">↗</span></h2>
    <div className="dashboard-card-content">{card.error ? <p className="dashboard-error">불러오지 못했습니다. {card.error}</p> : card.lines.filter(Boolean).map((line, index) => <p key={index}>{line}</p>)}</div>
    <span className="dashboard-card-action">{card.error ? '상세 화면에서 다시 확인' : card.action} →</span>
   </Link>)}</div>
  </>}
 </>;
}
