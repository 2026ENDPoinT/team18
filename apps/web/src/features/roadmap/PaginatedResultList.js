'use client';
import { useEffect, useId, useRef, useState } from 'react';

export default function PaginatedResultList({ items, label, children }) {
 const [pageSize, setPageSize] = useState(5);
 const [requestedPage, setPage] = useState(1);
 const listId = useId(), start = useRef(null), range = useRef(null);
 const pageCount = Math.max(1, Math.ceil(items.length / pageSize));
 const page = Math.min(requestedPage, pageCount);
 const offset = (page - 1) * pageSize;
 const firstPage = Math.max(1, Math.min(page - 2, pageCount - 4));
 const pages = Array.from({ length: Math.min(5, pageCount) }, (_, i) => firstPage + i);
 useEffect(() => { setPage(current => Math.min(current, pageCount)); }, [pageCount]);

 function changePage(next) {
  setPage(next);
  range.current?.focus({ preventScroll: true });
  start.current?.scrollIntoView({ block: 'start' });
 }

 if (!items.length) return null;
 return <div className="paginated-results" ref={start}>
  <div className="result-list-toolbar">
   <p ref={range} tabIndex={-1} role="status" aria-atomic="true">전체 {items.length}개 중 {offset + 1}–{Math.min(offset + pageSize, items.length)}개 · {page} / {pageCount}페이지</p>
   <label>표시 개수 <select aria-label={`${label} 표시 개수`} aria-controls={listId} value={pageSize} onChange={event => { setPageSize(Number(event.target.value)); setPage(1); }}>
    <option value={5}>5개씩 보기</option><option value={10}>10개씩 보기</option>
   </select></label>
  </div>
  <ul id={listId} className="skill-list" aria-label={`${label} 목록`}>{items.slice(offset, offset + pageSize).map(children)}</ul>
  <nav className="result-list-pagination" aria-label={`${label} 페이지 이동`}>
   <button type="button" aria-label={`${label} 이전 페이지`} aria-controls={listId} disabled={page === 1} onClick={() => changePage(page - 1)}>← 이전</button>
   <div className="result-list-pages">{pages.map(number => <button type="button" key={number} aria-label={`${label} ${number}페이지`} aria-controls={listId} aria-current={page === number ? 'page' : undefined} onClick={() => changePage(number)}>{number}</button>)}</div>
   <button type="button" aria-label={`${label} 다음 페이지`} aria-controls={listId} disabled={page === pageCount} onClick={() => changePage(page + 1)}>다음 →</button>
  </nav>
 </div>;
}
