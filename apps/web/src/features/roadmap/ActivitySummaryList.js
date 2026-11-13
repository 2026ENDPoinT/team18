'use client';
import { useLayoutEffect, useRef, useState } from 'react';
import { activityKindLabel } from './activityLoader.mjs';
import { resultHref } from './resultPresentation.mjs';

function ActivityRow({ item, measure = false }) {
 const url = item.url || item.source_links?.[0]?.url;
 const external = /^https?:\/\//.test(url || '');
 const title = <>{item.title}{external && <span aria-hidden="true"> ↗</span>}</>;
 return <li>
  {measure ? <span className="activity-preview-title">{title}</span> :
   <a href={external ? url : resultHref('activities')} target={external ? '_blank' : undefined} rel={external ? 'noopener noreferrer' : undefined}>{title}</a>}
  <p>{activityKindLabel(item.kind)} · {item.status === 'upcoming' ? '접수 예정' : '접수 중'}</p>
 </li>;
}

export default function ActivitySummaryList({ activities }) {
 const viewport = useRef(null), measure = useRef(null);
 const [visibleCount, setVisibleCount] = useState(0);
 useLayoutEffect(() => {
  let frame, active = true;
  function fit() {
   if (!active || !viewport.current || !measure.current) return;
   const container = viewport.current, list = measure.current;
   const style = getComputedStyle(container);
   // Desktop fills the neighboring cards. On mobile, stacked cards have no
   // shared height, so the CSS maximum bounds the preview instead.
   const limit = style.contain.includes('size') ? container.clientHeight : parseFloat(style.maxHeight);
   if (!Number.isFinite(limit)) return;
   const top = list.getBoundingClientRect().top;
   let count = 0;
   for (const row of list.children) {
    if (row.getBoundingClientRect().bottom - top > limit + 0.1) break;
    count++;
   }
   setVisibleCount(count);
  }
  function schedule() {
   cancelAnimationFrame(frame);
   frame = requestAnimationFrame(fit);
  }
  fit();
  const observer = new ResizeObserver(schedule);
  observer.observe(viewport.current);
  observer.observe(measure.current);
  window.addEventListener('resize', schedule);
  document.fonts?.ready.then(() => { if (active) schedule(); });
  return () => { active = false; observer.disconnect(); window.removeEventListener('resize', schedule); cancelAnimationFrame(frame); };
 }, [activities]);
 return <div ref={viewport} className="result-activity-preview">
  <ul className="result-brief-list" aria-label="추천 공모전·대외활동">{activities.slice(0, visibleCount).map(item =>
   <ActivityRow key={`${item.source}:${item.original_id || item.id}`} item={item}/>)}</ul>
  <ul ref={measure} className="result-brief-list result-activity-measure" aria-hidden="true">{activities.map(item =>
   <ActivityRow key={`${item.source}:${item.original_id || item.id}`} item={item} measure/>)}</ul>
 </div>;
}
