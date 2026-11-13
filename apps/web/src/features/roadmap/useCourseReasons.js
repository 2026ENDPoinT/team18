'use client';
import { useEffect, useRef, useState } from 'react';
import { apiRequest } from '../../lib/api/client';
import { resolvePlanId } from '../../lib/api/session';

export default function useCourseReasons(result, requestId, active) {
 const requests = useRef(new Map());
 const [state, setState] = useState({ key: '', phase: 'idle', reasons: {} });
 const [attempt, setAttempt] = useState(0);
 const runId = result?.run_id;
 const key = requestId && runId ? `${requestId}:${runId}` : '';
 const eligible = active && key && !result?.details_restricted && result?.recommended_courses?.length > 0;
 useEffect(() => {
  if (!eligible) return;
  let disposed = false;
  if (!requests.current.has(key)) {
   setState({ key, phase: 'loading', reasons: {} });
   requests.current.set(key, (async () => {
    try {
     if (await resolvePlanId() !== requestId) throw new Error('계획이 변경되었습니다. 최신 내용을 확인해 주세요.');
     const data = await apiRequest(`/roadmap-inputs/${encodeURIComponent(requestId)}/roadmaps/${encodeURIComponent(runId)}/course-reasons`, {
      method: 'POST', body: JSON.stringify({}),
     });
     if (await resolvePlanId() !== requestId || data.run_id !== runId || !Array.isArray(data.reasons)) throw new Error('추천 이유를 확인하지 못했습니다. 다시 시도해 주세요.');
     return { key, phase: 'ready', reasons: Object.fromEntries(data.reasons.map(item => [item.course_id, item.personalization_reason])) };
    } catch (error) {
     return { key, phase: 'error', reasons: {}, message: error.message };
    }
   })());
  }
  requests.current.get(key).then(next => { if (!disposed) setState(next); });
  return () => { disposed = true; };
 }, [eligible, key, requestId, runId, attempt]);
 return {
  ...(state.key === key ? state : { phase: 'loading', reasons: {} }),
  retry: () => { requests.current.delete(key); setAttempt(value => value + 1); },
 };
}
