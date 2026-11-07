'use client';
import { useState } from 'react';
import Link from 'next/link';
import { Heading } from '../../components/layout/Shell';
const tabs = ['준비 상태','직무 역량 비교','실행 로드맵','수강 후보','공모전·대외활동'];
export default function Result() {
 const [selected, setSelected] = useState(0);
 function onKeyDown(e) { let next; if (e.key === 'ArrowRight') next = (selected + 1) % tabs.length; else if (e.key === 'ArrowLeft') next = (selected + tabs.length - 1) % tabs.length; else if (e.key === 'Home') next = 0; else if (e.key === 'End') next = tabs.length - 1; else return; e.preventDefault(); setSelected(next); document.getElementById(`tab-${next}`)?.focus(); }
 return <><div className="result-head"><Heading number="06" title="로드맵 결과" description="입력 기준과 추천 이유를 함께 확인하는 결과 화면입니다."/><Link href="/input/basic" className="button">입력 수정</Link></div><div className="result-summary"><div><span>진로 목표</span><strong>결과 생성 전</strong></div><div><span>생성 당시 입력 기준</span><strong>표시할 기준 없음</strong></div></div><div className="result-tabs" role="tablist" aria-label="결과 구성" onKeyDown={onKeyDown}>{tabs.map((tab,i)=><button key={tab} role="tab" id={`tab-${i}`} aria-controls="result-panel" aria-selected={selected===i} tabIndex={selected===i?0:-1} onClick={()=>setSelected(i)}>{tab}</button>)}</div><section id="result-panel" role="tabpanel" aria-labelledby={`tab-${selected}`} className="empty-state"><strong>아직 생성된 분석 결과가 없습니다</strong><p>{tabs[selected]} 결과가 생성되면 이곳에서 확인할 수 있습니다.</p><button className="primary" disabled>로드맵 생성</button></section><footer className="footer"><span className="field-help">분석과 결과 생성 기능을 준비 중입니다.</span><Link className="button" href="/input/basic">입력 수정</Link></footer></>;
}
