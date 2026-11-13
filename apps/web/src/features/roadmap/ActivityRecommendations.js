'use client';
import { activityKindLabel } from './activityLoader.mjs';
import Link from 'next/link';
import { resultHref } from './resultPresentation.mjs';
import ActivitySummaryList from './ActivitySummaryList';
import { activityReason } from './activityReason.mjs';

export default function ActivityRecommendations({ active, resource, compact = false }) {
 const { phase, data, message, refresh } = resource;
 const failed = data?.sources?.filter(source => source.status !== 'success') || [];
 if (compact) return <div className="activity-summary" aria-busy={phase === 'idle' || phase === 'loading'}>
  {(phase === 'idle' || phase === 'loading') && <p role="status">활동 추천을 불러오는 중이에요…</p>}
  {(phase === 'error' || data?.status === 'error') && <div><p role="alert">활동 추천을 불러오지 못했어요.</p>{refresh && <button onClick={refresh}>다시 조회</button>}</div>}
  {phase === 'ready' && data?.status !== 'error' && <>
   {failed.length > 0 && <p className="summary-note" role="status">일부 출처를 조회하지 못해 확인된 활동만 표시해요.</p>}
   {data.activities.length === 0 ? <p role="status">현재 추천 조건에 맞는 활동이 없어요.</p> : <ActivitySummaryList activities={data.activities}/>}
  </>}
  <Link className="summary-link" href={resultHref('activities')}>활동 상세 보기 →</Link>
 </div>;
 return <div hidden={!active} className="activity-recommendations" aria-busy={phase === 'loading'}>
  <h2>공모전·대외활동 추천</h2>
  <p>저장한 진로 목표를 바탕으로, 한국 시간 기준 접수 중이거나 접수 예정이고 대학생 또는 누구나 참여 대상으로 안내된 공고를 추천합니다. 문서나 직무 분석 없이도 이용할 수 있습니다.</p>
  {refresh && <button disabled={phase === 'idle' || phase === 'loading'} onClick={refresh}>활동 추천 다시 확인</button>}
  {phase === 'loading' && <p role="status">접수 기간과 목표에 맞는 실제 공고를 확인하고 있습니다…</p>}
  {phase === 'error' && <p role="alert">{message}</p>}
  {data?.status === 'error' && <p role="alert">추천 활동을 불러오지 못했습니다. 잠시 후 다시 확인해 주세요.</p>}
  {failed.map(source => <p key={`${source.source || 'contestkorea'}-${source.kind}`} className="notice" role="status">
   {source.source === 'dacon_daker' ? '데이콘·데이커' : '콘테스트코리아'}: {source.error_code === 'last_collection_failed' ? '최근 수집에 실패하여 마지막 성공 자료에서 접수 중이거나 예정인 공고를 표시합니다.' : source.error_code === 'not_configured' ? '현재 이 출처의 추천 활동을 조회할 수 없습니다.' : source.status === 'partial' ? '일부 분야 또는 접수 기간을 확인하지 못해 검증된 공고만 표시합니다.' : '공고를 불러오지 못했습니다.'}
  </p>)}
  {data && data.status !== 'error' && data.activities.length === 0 && <p role="status">{data.status === 'partial' ? '정상 조회된 공고 중 ' : ''}현재 추천 조건에 맞는 공고가 없습니다. 목표 관련성, 접수 기간과 참가 대상을 확인한 공고만 표시합니다.</p>}
  {data && <>
   <ul className="skill-list">{data.activities.map(item => <li key={`${item.source}:${item.original_id || item.id}`} className="skill-card">
    <div className="skill-title"><span className="badge">{activityKindLabel(item.kind)}</span><span className="badge">{item.status === 'upcoming' ? '접수 예정' : '접수 중'}</span><h3>{item.title}</h3></div>
    <div className="recommendation-reason"><h4>관심 분야와 연결되는 활동</h4>
     <p>{activityReason(item)}</p>
    </div>
    <dl className="skill-summary">
     <div><dt>출처</dt><dd>{item.source_label || '콘테스트코리아'}</dd></div>
     <div><dt>분야</dt><dd>{item.category || '정보 없음'}</dd></div>
     <div><dt>주최·주관</dt><dd>{item.host || '정보 없음'}</dd></div>
     <div><dt>참가 대상</dt><dd>{item.target}</dd></div>
     {item.status === 'upcoming' && item.opens_at && <div><dt>접수 시작</dt><dd>{new Date(item.opens_at).toLocaleString('ko-KR', { timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false })} (한국 시간)</dd></div>}
     <div><dt>접수 마감</dt><dd>{item.deadline_label}</dd></div>
     <div><dt>접수 기간 원문</dt><dd>{item.period}</dd></div>
     {item.verified_period && <div><dt>원문에서 확인한 기간</dt><dd>{item.verified_period}</dd></div>}
    </dl>
    {(item.source_links || [{ source: item.source, source_label: item.source_label, url: item.url }]).map(link => <div key={`${link.source}:${link.url}`}>
     <a className="button" href={link.url} target="_blank" rel="noopener noreferrer" aria-label={`${item.title} ${link.source_label} 원문 보기 (새 창)`}>{link.source_label} 원문 보기 <span aria-hidden="true">↗</span></a>
     {link.last_success_at && <p className="field-help">마지막 원문 확인: {new Date(link.last_success_at).toLocaleString('ko-KR', { timeZone: 'Asia/Seoul' })} (한국 시간){link.stale ? ' · 최근 재확인 지연 — 신청 전 원문을 확인해 주세요.' : ''}</p>}
    </div>)}
   </li>)}</ul>
  </>}
 </div>;
}
