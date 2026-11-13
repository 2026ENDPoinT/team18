'use client';
import { useEffect, useId, useRef } from 'react';
import { createPortal } from 'react-dom';
import { SelectedCoursesSummary } from './CourseSelectionSummary';

export default function CourseSelectionDialog({ data, missing, phase, failure, message, trigger, canConfirm, onConfirm, onClose, onRetrySave, onRefresh }) {
 const dialog = useRef(null), heading = useRef(null), titleId = useId(), descriptionId = useId();
 const submitting = phase === 'confirming';
 useEffect(() => {
  const element = dialog.current, overflow = document.body.style.overflow;
  element.showModal(); document.body.style.overflow = 'hidden'; heading.current.focus();
  return () => { element.close(); document.body.style.overflow = overflow; trigger.current?.focus(); };
 }, [trigger]);
 function containFocus(event) {
  if (event.key !== 'Tab') return;
  const elements = [...dialog.current.querySelectorAll('button:not(:disabled),a[href],[tabindex="0"]')];
  const first = elements[0], last = elements.at(-1);
  if (event.shiftKey && (document.activeElement === first || document.activeElement === heading.current)) { event.preventDefault(); last?.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
 }
 return createPortal(<dialog ref={dialog} className="course-review-dialog" aria-labelledby={titleId} aria-describedby={descriptionId} onKeyDown={containFocus} onCancel={event => { event.preventDefault(); onClose(); }} onClick={event => { if (event.target === event.currentTarget) onClose(); }}>
  <div className="course-review-dialog-content">
   <header className="course-review-dialog-heading"><h2 ref={heading} tabIndex={-1} id={titleId}>이수 과목 확인</h2><button type="button" disabled={submitting} onClick={onClose} aria-label="이수 과목 확인 닫기">닫기</button></header>
   <p id={descriptionId}>선택한 과목을 확인한 뒤 역량 탐색으로 이동하세요.</p>
   <div className="course-review-dialog-body" tabIndex={0} role="region" aria-label="선택한 이수 과목 둘러보기">
    <SelectedCoursesSummary data={data} byYear/>
    {missing && <p className="notice">목록에 없는 이수 과목 신고가 포함됩니다.</p>}
   </div>
   {phase === 'failed' && <div className="notice" role="alert">{message}<div className="doc-actions">{failure?.kind === 'toggle' && !failure.conflict && <button type="button" onClick={onRetrySave}>다시 저장</button>}<button type="button" onClick={onRefresh}>최신 상태 불러오기</button></div></div>}
   <footer className="course-review-dialog-footer"><p className="field-help" role="status">{phase === 'saving' ? '마지막 선택을 저장 중입니다. 저장이 끝나면 계속할 수 있어요.' : submitting ? '이수 선택을 확인하고 있습니다…' : phase === 'failed' ? '저장 상태를 확인해 주세요.' : '선택을 바꾸려면 선택 수정을 눌러 주세요.'}</p><div><button type="button" disabled={submitting} onClick={onClose}>선택 수정</button><button type="button" className="primary" disabled={!canConfirm} onClick={onConfirm}>확인하고 역량 탐색</button></div></footer>
  </div>
 </dialog>, document.body);
}
