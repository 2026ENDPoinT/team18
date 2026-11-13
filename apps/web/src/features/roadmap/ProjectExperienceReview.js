'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { apiRequest } from '../../lib/api/client';
import { resolvePlanId } from '../../lib/api/session';
import { answerLabels, scopeLabels } from './ProjectEvidence';
import { experiencePresentation } from './experiencePresentation.mjs';

const exclusionLabels = { pending: '본문 추출 중', failed: '본문 추출 실패', needs_ocr: 'OCR 필요', partial_unconfirmed: '부분 추출 확인 필요', invalid_extraction: '읽힌 내용 확인 필요', empty_text: '본문이 비어 있음' };

function ExperienceCard({ item, busy, save }) {
 const effective = experiencePresentation(item);
 const [editing, setEditing] = useState(false);
 const [correction, setCorrection] = useState({});
 function edit() { setCorrection({ skill_name: effective.skill_name, activity: effective.activity, contribution_scope: effective.contribution_scope, role: effective.role, output: effective.output }); setEditing(true); }
 const change = (field, value) => setCorrection(old => ({ ...old, [field]: value }));
 return <li className="skill-card">
  <div className="skill-title"><h3>{effective.activity}</h3><span className="badge">{scopeLabels[effective.contribution_scope]}</span><span className="badge">{answerLabels[item.user_confirmation] || '미확인'}</span></div>
  <p>기술 스택: {effective.skill_name}</p>
  <div className="doc-actions experience-actions">
   <button disabled={busy} onClick={() => save(item, 'confirmed')}>맞아요</button>
   <button disabled={busy} onClick={edit}>수정할게요</button>
   <button disabled={busy} onClick={() => save(item, 'unknown')}>잘 모르겠어요</button>
   <button disabled={busy} onClick={() => save(item, 'no_experience')}>이 기술 경험 없어요</button>
  </div>
  {editing && <form className="experience-correction" onSubmit={async e => { e.preventDefault(); if (await save(item, 'corrected', correction)) setEditing(false); }}>
   <p className="field-help">수정한 내용은 사용자 답변으로 별도 저장됩니다. 직접 수행한 경험이면 수행 범위를 개인으로 선택해 주세요.</p>
   <label className="field">기술명<input required maxLength={150} value={correction.skill_name} onChange={e => change('skill_name', e.target.value)}/></label>
   <label className="field">수행 내용<textarea required maxLength={1000} value={correction.activity} onChange={e => change('activity', e.target.value)}/></label>
   <label className="field">수행 범위<select value={correction.contribution_scope} onChange={e => change('contribution_scope', e.target.value)}><option value="personal">본인 직접 수행</option><option value="team">팀 수행</option><option value="unknown">수행 주체 미확인</option></select></label>
   <label className="field">본인 역할 (선택)<input maxLength={500} value={correction.role || ''} onChange={e => change('role', e.target.value || null)}/></label>
   <label className="field">결과물 (선택)<input maxLength={1000} value={correction.output || ''} onChange={e => change('output', e.target.value || null)}/></label>
   <div className="doc-actions"><button className="primary" disabled={busy}>수정 내용 저장</button><button type="button" disabled={busy} onClick={()=>setEditing(false)}>수정 취소</button></div>
  </form>}
 </li>;
}

export default function ProjectExperienceReview() {
 const lock=useRef(false);
 const [conflict,setConflict]=useState(false);
 const [id, setId] = useState(null), [data, setData] = useState(null), [busy, setBusy] = useState(true), [message, setMessage] = useState('');
 const load = useCallback(async () => {
  if(lock.current)return;lock.current=true;
  setBusy(true); setMessage(''); setData(null);setConflict(false);
  try {
   const rid = await resolvePlanId();
   if (!rid) throw new Error('계획이 없습니다. 기본 정보를 먼저 입력해 주세요.');
   const result = await apiRequest(`/roadmap-inputs/${encodeURIComponent(rid)}/project-experience-analysis`);
   if (await resolvePlanId() !== rid) throw new Error('선택한 계획이 변경되었습니다. 다시 불러와 주세요.');
   setId(rid); setData(result);
  } catch (e) { setMessage(e.message); }
  finally { lock.current=false;setBusy(false); }
 }, []);
 useEffect(() => { load(); }, [load]);
 async function mutate(path, body, method) {
  if(lock.current||conflict||!data)return false;lock.current=true;
  setBusy(true); setMessage('');
  try {
   if (await resolvePlanId() !== id) throw new Error('선택한 계획이 변경되었습니다. 다시 불러와 주세요.');
   const result = await apiRequest(`/roadmap-inputs/${encodeURIComponent(id)}${path}`, { method, body: JSON.stringify({ expected_input_revision: data.input_revision, ...body }) });
   if (await resolvePlanId() !== id) throw new Error('선택한 계획이 변경되었습니다. 다시 불러와 주세요.');
   setData(result); return true;
  } catch (e) { setMessage(e.message); if ([401, 404].includes(e.status)) setData(null);setConflict(e.status===409); return false; }
  finally { lock.current=false;setBusy(false); }
 }
 const save = (item, status, correction) => mutate(`/project-experiences/${item.experience_id}/confirmation`, { status, ...(correction ? { correction } : {}) }, 'PATCH');
 return <section className="wire-box" aria-busy={busy}>
  <h3>프로젝트 경험 분석 및 확인</h3>
  <p>‘맞아요’는 해당 설명이 본인의 수행 경험이라는 확인입니다. 팀 전체의 기술 사용과 본인의 직접 수행을 구분해 주세요.</p>
  {busy && <p role="status">문서 분석 또는 확인 내용을 처리하고 있습니다…</p>}
  {message && <p role="alert">{message}</p>}
  <div className="doc-actions"><button className="primary" disabled={busy || conflict || !data || !data.eligible_documents} onClick={() => mutate('/project-experience-analysis', {}, 'POST')}>프로젝트 경험 분석 실행</button><button disabled={busy} onClick={load}>최신 내용 불러오기</button><Link href="/input/documents" className="button">문서 확인</Link></div>
  {data && <>
   <p className="field-help">분석 가능한 문서 {data.eligible_documents}개 · 분석 완료 {data.analyzed_documents}개 · 확인할 경험 {data.verified_experiences}개</p>
   {data.status === 'no_documents' && <p role="status">현재 분석 가능한 문서가 없습니다. 경험이 없다는 의미는 아닙니다. 문서 상태를 확인해 주세요.</p>}
   {data.status === 'not_started' && <p role="status">분석 실행 후 추출된 경험을 확인할 수 있습니다.</p>}
   {!!data.refresh_errors?.length && <p role="alert">재분석을 완료하지 못해 기존 분석 결과와 사용자 답변을 유지했습니다.</p>}
   {data.status === 'error' && <p role="alert">프로젝트 경험 분석을 완료하지 못했습니다. 분석 실행 버튼을 눌러 다시 시도해 주세요. {data.errors.some(e => e.code === 'document_too_long') && '문서가 너무 깁니다. 맡은 일이 담긴 부분을 나누어 등록해 주세요.'}</p>}
   {!!data.excluded_documents.length && <ul>{data.excluded_documents.map(d => <li key={d.document_id}>{d.original_filename}: {exclusionLabels[d.reason] || '본문 확인 필요'}</li>)}</ul>}
   {['success', 'partial'].includes(data.status) && !data.experiences.length && <p>현재 문서에서 검증 가능한 기술 활동을 찾지 못했습니다. 경험 부재로 판단하지 않습니다.</p>}
   <ul className="skill-list">{data.experiences.map(item => <ExperienceCard key={item.experience_id} item={item} busy={busy||conflict} save={save}/>)}</ul>
  </>}
 </section>;
}
