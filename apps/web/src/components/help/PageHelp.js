'use client';
import { useEffect, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { helpExamples } from './examples.mjs';

function ExampleDialog({ example, imageId, trigger, close }) {
 const dialog = useRef(null), closeButton = useRef(null), titleId = useId();
 const [zoom, setZoom] = useState(false), [phase, setPhase] = useState('loading'), [retry, setRetry] = useState(0);
 useEffect(() => {
  const element = dialog.current, originalOverflow = document.body.style.overflow;
  element.showModal(); document.body.style.overflow = 'hidden'; closeButton.current.focus();
  return () => { element.close(); document.body.style.overflow = originalOverflow; trigger.current?.focus(); };
 }, [trigger]);
 function containFocus(event) {
  if (event.key !== 'Tab') return;
  const elements = [...dialog.current.querySelectorAll('button:not(:disabled),a[href],[tabindex="0"]')];
  const first = elements[0], last = elements.at(-1);
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
 }
 return createPortal(<dialog ref={dialog} className="help-dialog" aria-labelledby={titleId} onKeyDown={containFocus} onCancel={event => { event.preventDefault(); close(); }} onClick={event => { if (event.target === event.currentTarget) close(); }}>
  <div className="help-dialog-content">
   <div className="help-dialog-heading"><h2 id={titleId}>{example.title} 예시</h2><button ref={closeButton} type="button" onClick={close} aria-label="도움말 닫기">닫기</button></div>
   <p>{example.description}</p><p className="field-help">가상 학생 ‘민서’의 예시입니다. 학교·문서·추천 내용은 사용 방법을 보여주기 위한 가상 자료예요.</p>
   <div className="help-tools"><button type="button" aria-pressed={zoom} onClick={() => setZoom(value => !value)}>{zoom ? '이미지 맞춤' : '이미지 확대'}</button><span className="field-help">확대한 이미지는 좌우·위아래로 움직여 볼 수 있어요.</span></div>
   {phase === 'loading' && <p role="status">예시 이미지를 불러오는 중입니다…</p>}
   {phase === 'error' && <p role="alert">이미지를 불러오지 못했습니다. <button type="button" onClick={() => { setPhase('loading'); setRetry(value => value + 1); }}>이미지 다시 불러오기</button></p>}
   <div className={`help-image-view${zoom ? ' is-enlarged' : ''}`} tabIndex={0} role="region" aria-label="예시 이미지 둘러보기">
    <img key={retry} src={`/help/${imageId}.png${retry ? `?retry=${retry}` : ''}`} alt={example.alt} onLoad={() => setPhase('ready')} onError={() => setPhase('error')}/>
   </div>
  </div>
 </dialog>, document.body);
}

export default function PageHelp({ exampleId }) {
 const trigger = useRef(null), [open, setOpen] = useState(false);
 const example = helpExamples[exampleId];
 if (!example) return null;
 return <><button ref={trigger} type="button" className="page-help-button" aria-label={`${example.title} 예시 보기`} title={`${example.title} 예시 보기`} aria-haspopup="dialog" aria-expanded={open} onClick={() => setOpen(true)}>?</button>
  {open && <ExampleDialog example={example} imageId={exampleId} trigger={trigger} close={() => setOpen(false)}/>}
 </>;
}
