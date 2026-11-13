'use client';
import { useEffect, useRef, useState } from 'react';
import { apiRequest } from '../../lib/api/client';
import { resolvePlanId } from '../../lib/api/session';

function values(plan) {
 return { career_goal: plan.input.career_goal || '', target_role: plan.input.target_role || '' };
}

export default function CareerInfoEditor({ plan, disabled, onPlanChange }) {
 const [base, setBase] = useState(null), [draft, setDraft] = useState(null);
 const [phase, setPhase] = useState('ready'), [message, setMessage] = useState('');
 const lock = useRef(false), goal = useRef(null);
 useEffect(() => { setBase(null); setDraft(null); setPhase('ready'); setMessage(''); }, [plan?.request_id]);
 function edit() { setBase(plan); setDraft(values(plan)); setPhase('ready'); setMessage(''); }
 function cancel() { setBase(null); setDraft(null); setPhase('ready'); setMessage(''); }
 async function reload() {
  if (lock.current) return;
  lock.current = true; setPhase('saving');
  try {
   const id = await resolvePlanId();
   if (id !== base.request_id) throw new Error('계획이 변경되었습니다. 화면을 다시 불러와 주세요.');
   const latest = await apiRequest(`/roadmap-inputs/${encodeURIComponent(id)}`);
   setBase(latest); setDraft(values(latest)); onPlanChange(latest, false);
   setPhase('ready'); setMessage('최신 진로 정보를 불러왔습니다. 내용을 확인한 뒤 수정해 주세요.');
  } catch (error) { setPhase('conflict'); setMessage(error.message); }
  finally { lock.current = false; }
 }
 async function save(event) {
  event.preventDefault();
  if (lock.current || disabled || phase === 'conflict') return;
  if (!draft.career_goal.trim()) { setPhase('error'); setMessage('목표·관심 분야를 입력해 주세요.'); goal.current?.focus(); return; }
  const changes = {};
  const updated = { career_goal: draft.career_goal.trim(), target_role: draft.target_role.trim() || null };
  for (const key of Object.keys(updated)) if (updated[key] !== (base.input[key] ?? (key === 'career_goal' ? '' : null))) changes[key] = updated[key];
  if (!Object.keys(changes).length) { cancel(); return; }
  lock.current = true; setPhase('saving'); setMessage('');
  try {
   if (await resolvePlanId() !== base.request_id) throw new Error('계획이 변경되었습니다. 화면을 다시 불러와 주세요.');
   const saved = await apiRequest(`/roadmap-inputs/${encodeURIComponent(base.request_id)}`, {
    method: 'PATCH', body: JSON.stringify({ expected_input_revision: base.input_revision, changes }),
   });
   if (await resolvePlanId() !== base.request_id) throw new Error('계획이 변경되었습니다. 화면을 다시 불러와 주세요.');
   onPlanChange(saved, true); setBase(null); setDraft(null); setPhase('ready'); setMessage('진로 정보를 저장했습니다.');
  } catch (error) {
   setPhase(error.status === 409 ? 'conflict' : 'error');
   setMessage(error.status === 409 ? '다른 화면에서 정보가 변경되었습니다. 최신 정보를 불러온 뒤 다시 수정해 주세요.' : error.message);
  } finally { lock.current = false; }
 }
 const busy = phase === 'saving';
 return <section className="career-editor" aria-labelledby="career-editor-title" aria-busy={busy}>
  <h3 id="career-editor-title">진로 정보 수정</h3>
  {draft ? <form onSubmit={save} noValidate>
   <label className="field">목표·관심 분야 <small>필수</small><textarea ref={goal} required maxLength={10000} value={draft.career_goal} disabled={busy} aria-invalid={phase === 'error' && !draft.career_goal.trim() || undefined} onChange={e=>setDraft(old=>({...old,career_goal:e.target.value}))}/></label>
   <label className="field">희망 직무 <small>선택</small><input maxLength={100} value={draft.target_role} disabled={busy} onChange={e=>setDraft(old=>({...old,target_role:e.target.value}))}/></label>
   <div className="doc-actions"><button className="primary" disabled={busy || disabled || phase === 'conflict'}>저장</button><button type="button" disabled={busy} onClick={cancel}>취소</button></div>
  </form> : plan ? <><dl className="career-values"><div><dt>목표·관심 분야</dt><dd>{plan.input.career_goal || '입력 필요'}</dd></div><div><dt>희망 직무</dt><dd>{plan.input.target_role || '미입력'}</dd></div></dl><button type="button" disabled={disabled} onClick={edit}>수정</button></> : <p role="status">저장한 진로 정보를 불러오는 중입니다.</p>}
  {message && <p role={['error','conflict'].includes(phase) ? 'alert' : 'status'}>{message}</p>}
  {phase === 'conflict' && <button type="button" onClick={reload}>최신 정보 불러오기</button>}
 </section>;
}
