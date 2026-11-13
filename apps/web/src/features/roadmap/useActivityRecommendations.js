'use client';
import { useEffect, useRef, useState } from 'react';
import { apiRequest } from '../../lib/api/client';
import { resolvePlanId } from '../../lib/api/session';
import { createActivityLoader } from './activityLoader.mjs';

// Keep one activity snapshot for the result screen. Time, focus, tab visits and
// unrelated input revisions must not replace it; refresh is an explicit action.
export default function useActivityRecommendations(requestId, active) {
 const snapshot = useRef(null);
 const [state, setState] = useState({ requestId: null, phase: 'idle', data: null, message: '' });
 const [retry, setRetry] = useState(0);
 useEffect(() => {
  if (!active || !requestId) return;
  let disposed = false;
  if (snapshot.current?.requestId !== requestId) {
   snapshot.current = { requestId, loader: createActivityLoader({ apiRequest, resolvePlanId }), promise: null };
  }
  const current = snapshot.current;
  if (!current.promise) {
   setState({ requestId, phase: 'loading', data: null, message: '' });
   current.promise = (async () => {
    try {
     if (await resolvePlanId() !== requestId) throw new Error('계획이 변경되었습니다. 최신 내용을 확인해 주세요.');
     const data = await current.loader({ refresh: true });
     if (await resolvePlanId() !== requestId) throw new Error('계획이 변경되었습니다. 최신 내용을 확인해 주세요.');
     return { requestId, phase: 'ready', data, message: '' };
    } catch (error) {
     return { requestId, phase: 'error', data: null, message: error.message };
    }
   })();
  }
  current.promise.then(next => { if (!disposed) setState(next); });
  return () => { disposed = true; };
 }, [active, requestId, retry]);
 return {
  ...(state.requestId === requestId ? state : { phase: 'idle', data: null, message: '' }),
  refresh: () => { if (snapshot.current?.requestId === requestId) snapshot.current.promise = null; setRetry(value => value + 1); },
 };
}
