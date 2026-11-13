'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import PageHelp from '../help/PageHelp';
import { helpForPath } from '../help/examples.mjs';

export function Logo() {
 return <span className="stepup-logo" aria-hidden="true"><svg viewBox="0 0 48 48" width="35" height="35"><path fill="currentColor" d="M3 36a2 2 0 0 1 2-2h10v10H3v-8Zm13-7a2 2 0 0 1 2-2h10v17H16V29Zm13-8a2 2 0 0 1 2-2h10v25H29V21Z"/><path d="M31 17V3.5a1 1 0 0 1 1.5-.87l10.5 5.8a1 1 0 0 1 0 1.75L32 16" fill="currentColor" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/></svg></span>;
}
const menu = [
 ['/input/basic', '◉', '기본 정보'],
 ['/input/documents', '▤', '경험 · 문서'],
 ['/input/courses', '▧', '이수 과목'],
 ['/input/review', '✧', '역량 탐색'],
 ['/result', '↗', '로드맵 결과'],
];
const sidebarStorageKey = 'stepup-sidebar-collapsed';
export function Shell({ children }) {
 const pathname = usePathname();
 const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
 useEffect(() => {
  try { setSidebarCollapsed(localStorage.getItem(sidebarStorageKey) === 'true'); } catch {}
 }, []);
 function toggleSidebar() {
  const collapsed = !sidebarCollapsed;
  setSidebarCollapsed(collapsed);
  try { localStorage.setItem(sidebarStorageKey, String(collapsed)); } catch {}
 }
 const home = pathname === '/';
 const current = pathname.startsWith('/input/') ? 'input' : pathname === '/result' ? 'result' : 'home';
 return <>
  <a className="skip-link" href="#main-content">본문으로 이동</a>
  <header className="global-bar"><Link href="/" className="global-brand"><Logo/>스텝업</Link><nav className="global-nav" aria-label="진행 메뉴">{[['home','/','시작'],['input','/input/basic','입력·검토'],['result','/result','내 로드맵']].map(([id,href,label])=><Link key={id} href={href} className={current===id?'active':''} aria-current={current===id?'page':undefined}>{label}</Link>)}</nav><Link href="/" className="account-link">계정 · 로그인</Link></header>
  <div className={home?'home-shell':'stepup-app'} data-sidebar-collapsed={sidebarCollapsed}>
   {!home&&<aside className="stepup-side">
    <div className="side-toolbar"><div className="nav-heading">역량 체크하기</div><button type="button" className="sidebar-toggle" onClick={toggleSidebar} aria-expanded={!sidebarCollapsed} aria-controls="primary-sidebar-nav" aria-label={sidebarCollapsed?'메뉴 펼치기':'메뉴 접기'} title={sidebarCollapsed?'메뉴 펼치기':'메뉴 접기'}>
     <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false"><rect x="3" y="4" width="18" height="16" rx="3"/><path d="M9 4v16"/><path d={sidebarCollapsed?'m13 9 3 3-3 3':'m16 9-3 3 3 3'}/></svg>
     <span className="sidebar-toggle-label">{sidebarCollapsed?'메뉴 펼치기':'메뉴 접기'}</span>
    </button></div>
    <nav id="primary-sidebar-nav" className="side-nav" aria-label="주 메뉴">{menu.map(([href,icon,label])=><div key={href}><Link href={href} className={pathname===href?'active':''} aria-label={label} title={sidebarCollapsed?label:undefined} aria-current={pathname===href?'page':undefined}><span className="side-nav-icon" aria-hidden="true">{icon}</span><span className="side-nav-label">{label}</span></Link></div>)}</nav>
   </aside>}
   <main id="main-content" className={home?'home-content':'service-content'}>{children}</main>
  </div>
 </>;
}
export function Stepper({ current, blockForward = false }) {
  const steps = [['기본 정보','/input/basic'],['프로젝트 문서','/input/documents'],['이수 과목','/input/courses'],['분석 내용 확인','/input/review']];
  return <nav className="stepper" aria-label="입력 단계">{steps.map(([label, href], i) => <span className="step-wrap" key={href}>{blockForward && i > current ? <span aria-disabled="true">{i + 1}. {label}</span> : <Link className={i === current ? 'current' : ''} aria-current={i === current ? 'step' : undefined} href={href}>{i + 1}. {label}</Link>}{i < 3 && <span aria-hidden="true">›</span>}</span>)}</nav>;
}
export function PageTitle({ title, helpId }) {
 const pathname = usePathname();
 return <div className="page-title-row"><h1 className="page-title">{title}</h1><PageHelp exampleId={helpId || helpForPath[pathname]}/></div>;
}
export function Heading({ number, title, description, helpId }) { return <><div className="eyebrow">{String(Number(number)-1).padStart(2,'0')} / 05</div><PageTitle title={title} helpId={helpId}/><p className="description">{description}</p></>; }
export function Footer({ previous, next, nextLabel, note }) { return <footer className="footer"><div><Link className="button" href={previous}>이전</Link>{note && <div className="footer-note">{note}</div>}</div>{next && <Link className="button primary" href={next}>{nextLabel}</Link>}</footer>; }
