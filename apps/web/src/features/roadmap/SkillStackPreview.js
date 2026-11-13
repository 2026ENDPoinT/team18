'use client';
import { useLayoutEffect, useRef, useState } from 'react';

export default function SkillStackPreview({ skills }) {
 const viewport = useRef(null), measure = useRef(null);
 const [visibleCount, setVisibleCount] = useState(skills.length);
 useLayoutEffect(() => {
  let frame, active = true;
  function fit() {
   if (!active) return;
   const container = viewport.current, list = measure.current;
   // On mobile the cards stack naturally, so there is no neighboring height to fill.
   if (!getComputedStyle(container).contain.includes('size')) {
    setVisibleCount(skills.length);
    return;
   }
   const top = list.getBoundingClientRect().top;
   let count = 0;
   for (const row of list.children) {
    if (row.getBoundingClientRect().bottom - top > container.clientHeight) break;
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
  document.fonts.ready.then(() => { if (active) schedule(); });
  return () => { active = false; observer.disconnect(); cancelAnimationFrame(frame); };
 }, [skills]);
 const items = count => skills.slice(0, count).map(skill => <li key={skill.name}><h3>{skill.name}</h3></li>);
 return <div ref={viewport} className="result-skill-preview">
  <ul className="result-brief-list" aria-label="분석된 기술 스택">{items(visibleCount)}</ul>
  <ul ref={measure} className="result-brief-list result-skill-measure" aria-hidden="true">{items(skills.length)}</ul>
 </div>;
}
