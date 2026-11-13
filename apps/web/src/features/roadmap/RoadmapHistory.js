'use client';
import { useRef, useState } from 'react';
import { apiRequest } from '../../lib/api/client';
import { RoadmapSteps } from './RoadmapPanels';

export default function RoadmapHistory({ planId }) {
 const [history, setHistory] = useState(null), [result, setResult] = useState(null);
 const [loading, setLoading] = useState(false), [message, setMessage] = useState('');
 const sequence = useRef(0);
 async function read(runId) {
  const ticket = ++sequence.current;
  setLoading(true); setMessage(''); setResult(null);
  try {
   const data = await apiRequest(`/roadmap-inputs/${encodeURIComponent(planId)}/roadmaps${runId ? `/${encodeURIComponent(runId)}` : ''}`);
   if (ticket !== sequence.current) return;
   if (runId) setResult(data); else setHistory(data.runs);
  } catch (error) { if (ticket === sequence.current) setMessage(error.message); }
  finally { if (ticket === sequence.current) setLoading(false); }
 }
 return <details className="roadmap-history" onToggle={event => { if (event.currentTarget.open && !history && !loading) read(); }}>
  <summary>과거 결과 조회</summary>
  {loading && <p role="status">저장한 결과를 불러오는 중이에요…</p>}
  {message && <p role="alert">{message} <button onClick={() => read()}>다시 조회</button></p>}
  {history?.length === 0 && <p>저장한 과거 결과가 없어요.</p>}
  {history?.length > 0 && <ul className="history-runs">{history.map((run, index) => <li key={run.run_id}><button onClick={() => read(run.run_id)} disabled={loading}>{new Date(run.created_at).toLocaleString('ko-KR', { timeZone: 'Asia/Seoul' })} · {history.length - index}번째 결과</button></li>)}</ul>}
  {result?.details_restricted ? <p role="status">근거가 변경되어 이 과거 결과의 상세 조회가 제한되었어요.</p> : result?.roadmap ? <div className="history-result"><p className="notice">과거에 저장한 작업과 완료 기록입니다.</p><RoadmapSteps result={result} saving/></div> : result && <p role="status">이 결과에는 완료된 로드맵이 없어요.</p>}
 </details>;
}
