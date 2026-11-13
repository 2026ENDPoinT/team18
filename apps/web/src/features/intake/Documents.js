'use client';
import Link from 'next/link';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Stepper, Heading } from '../../components/layout/Shell';
import { apiRequest, studentMessage } from '../../lib/api/client';
import { resolvePlanId } from '../../lib/api/session';
import useDocumentUploads from './useDocumentUploads';
import { readQueue } from './documentUploadQueue.mjs';
import './documents.css';

const labels={pending:'읽기 중',ready:'읽기 완료 · 분석 포함 가능',partial:'일부만 읽힘 · 확인 필요',needs_ocr:'OCR 필요 · 분석 제외',failed:'읽기 실패 · 분석 제외'};
export default function Documents(){
 const router=useRouter();
 const [id,setId]=useState(null),[data,setData]=useState(null),[phase,setPhase]=useState('loading'),[message,setMessage]=useState(''),[modal,setModal]=useState(null);
 const lock=useRef(false),seq=useRef(0),fileRef=useRef(null),modalRef=useRef(null),modalTrigger=useRef(null),restoreFocus=useRef(false);
 const [dragging,setDragging]=useState(false),dragDepth=useRef(0);
 const load=useCallback(async requestId=>{const version=++seq.current;const ids=readQueue(requestId).map(row=>row.key).join(',');const result=await apiRequest(`/roadmap-inputs/${encodeURIComponent(requestId)}/documents${ids?`?upload_ids=${encodeURIComponent(ids)}`:''}`);if(version===seq.current)setData(result);return result},[]);
 const uploads=useDocumentUploads(id,data,load,setMessage);
 useEffect(()=>{let active=true;(async()=>{try{const requestId=await resolvePlanId();if(!requestId){if(active)setPhase('empty');return}if(active)setId(requestId);await load(requestId);if(active)setPhase('ready')}catch(e){if(active){setPhase(e.code==='feature_unavailable'?'unavailable':'error');setMessage(e.message)}}})();return()=>{active=false;seq.current++}},[load]);
 useEffect(()=>{if(!id||phase!=='ready')return;const timer=setInterval(()=>{if(lock.current||document.visibilityState==='hidden')return;load(id).catch(e=>setMessage(e.message))},3000);return()=>clearInterval(timer)},[id,phase,load]);
 useEffect(()=>{
  function preventFileNavigation(e){if([...e.dataTransfer.types].includes('Files'))e.preventDefault();}
  function resetDrag(){dragDepth.current=0;setDragging(false);}
  window.addEventListener('dragover',preventFileNavigation);
  window.addEventListener('drop',preventFileNavigation);
  window.addEventListener('drop',resetDrag);
  window.addEventListener('dragend',resetDrag);
  return()=>{window.removeEventListener('dragover',preventFileNavigation);window.removeEventListener('drop',preventFileNavigation);window.removeEventListener('drop',resetDrag);window.removeEventListener('dragend',resetDrag);};
 },[]);
 useEffect(()=>{
  if(!modal)return;
  const trigger=modalTrigger.current;
  const dialog=modalRef.current;
  const previousOverflow=document.body.style.overflow;
  document.body.style.overflow='hidden';
  dialog.querySelector('button')?.focus();
  function keydown(e){
   if(e.key==='Escape'){e.preventDefault();setModal(null);return;}
   if(e.key!=='Tab')return;
   const focusable=[...dialog.querySelectorAll('button:not(:disabled),a[href],input:not(:disabled),select:not(:disabled),textarea:not(:disabled),summary,[tabindex="0"]')];
   const first=focusable[0], last=focusable.at(-1);
   if(e.shiftKey&&document.activeElement===first){e.preventDefault();last?.focus();}
   else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus();}
  }
  document.addEventListener('keydown',keydown);
  return()=>{document.removeEventListener('keydown',keydown);document.body.style.overflow=previousOverflow;restoreFocus.current=true;trigger?.focus();if(document.activeElement===trigger)restoreFocus.current=false;};
 },[modal]);
 useEffect(()=>{if(!modal&&phase==='ready'&&restoreFocus.current){modalTrigger.current?.focus();restoreFocus.current=false;}},[modal,phase]);
 async function refresh(){if(lock.current)return;lock.current=true;setPhase('loading');try{await load(id);setMessage('최신 문서 상태를 불러왔습니다.');setPhase('ready')}catch(e){setMessage(e.message);setPhase('error')}finally{lock.current=false}}
 async function action(path,method,body,success){if(lock.current||phase!=='ready')return;lock.current=true;seq.current++;setPhase('working');setMessage('처리 중입니다…');try{await apiRequest(`/roadmap-inputs/${encodeURIComponent(id)}/documents${path}`,{method,body});await load(id);setPhase('ready');setMessage(success);return true}catch(e){setPhase('error');setMessage(e.status===409?'다른 화면에서 입력이 변경되었습니다. 최신 상태를 불러와 확인해 주세요.':e.message);return false}finally{lock.current=false}}
 function upload(e){const files=Array.from(e.target.files||[]);e.target.value='';uploads.enqueue(files);}
 function dragEnter(e){if(![...e.dataTransfer.types].includes('Files'))return;e.preventDefault();dragDepth.current++;if(phase==='ready')setDragging(true);}
 function dragLeave(e){e.preventDefault();dragDepth.current=Math.max(0,dragDepth.current-1);if(!dragDepth.current)setDragging(false);}
 function drop(e){e.preventDefault();dragDepth.current=0;setDragging(false);if(phase==='ready')uploads.enqueue(Array.from(e.dataTransfer.files));}
 async function show(doc,trigger){if(lock.current||phase!=='ready')return;modalTrigger.current=trigger;lock.current=true;setPhase('working');try{const result=await apiRequest(`/roadmap-inputs/${encodeURIComponent(id)}/documents/${doc.document_id}/extractions/${doc.extraction_revision}`);setModal({...result,filename:doc.original_filename});setPhase('ready')}catch(e){setMessage(e.message);setPhase('error')}finally{lock.current=false}}
 async function confirm(){if(!modal||!modal.is_current_revision)return;const ok=await action(`/${modal.document_id}/extractions/${modal.extraction_revision}/confirmation`,'POST',JSON.stringify({expected_input_revision:data.input_revision}),'읽힌 범위를 확인했습니다.');if(ok)setModal(null)}
 async function remove(doc){if(!window.confirm(`“${doc.original_filename}” 문서를 삭제할까요?`))return;await action(`/${doc.document_id}`,'DELETE',JSON.stringify({expected_input_revision:data.input_revision}),'문서를 현재 계획에서 제외했습니다.')}
 async function retry(doc){await action(`/${doc.document_id}/retry-extraction`,'POST',JSON.stringify({expected_input_revision:data.input_revision}),'문서를 다시 읽기 시작했습니다.')}
 async function next(skip=false){if(lock.current||phase!=='ready')return;lock.current=true;setPhase('working');try{const latest=await load(id);if(skip&&(latest.documents.length||(latest.uploads||[]).some(upload=>upload.status==='uploading'))){setMessage('등록 중이거나 등록된 문서를 확인한 뒤 계속해 주세요.');setPhase('ready')}else if(skip||latest.analysis_eligible)router.push('/input/courses');else{setMessage('읽기 완료 또는 읽힌 범위를 확인한 문서가 필요합니다.');setPhase('ready')}}catch(e){setMessage(e.message);setPhase('error')}finally{lock.current=false}}
 const busy=phase!=='ready'||uploads.uploading;
 return <><Stepper current={1} blockForward/><Heading number="03" title="경험·문서" description="프로젝트에서 맡은 역할과 활동이 담긴 문서를 등록하고 읽힌 내용을 확인합니다."/>
 {phase==='loading'&&!data&&<div className="notice" role="status">문서 목록을 불러오는 중입니다.</div>}
 {phase==='empty'&&<div className="empty-state"><strong>계획이 없습니다.</strong><p>시작 화면에서 계획을 만들어 주세요.</p><Link className="button" href="/">시작 화면</Link></div>}
 {phase==='unavailable'&&<><div className="notice" role="status"><strong>프로젝트 문서를 사용할 수 없습니다.</strong><p>{message} 문서 없이 이수 과목 입력과 수강 후보 확인을 계속할 수 있습니다.</p></div><footer className="footer"><Link className="button" href="/input/basic">이전</Link><Link className="button primary" href="/input/courses">문서 없이 다음: 이수 과목</Link></footer></>}
 {phase==='error'&&<div className="notice" role="alert"><strong>문서 상태를 확인하지 못했습니다.</strong><br/>{message} {id?<button onClick={refresh}>최신 상태 불러오기</button>:<Link href="/">시작 화면</Link>}</div>}
 {data&&<>
  <div className="columns documents-columns">
   <section className={`wire-box documents-drop-zone${dragging?' is-dragging':''}`} onDragEnter={dragEnter} onDragLeave={dragLeave} onDragOver={e=>{e.preventDefault();e.dataTransfer.dropEffect=phase==='ready'?'copy':'none';}} onDrop={drop}>
    <h3>프로젝트 문서 등록</h3>
    <div className="upload-box">
     <strong>프로젝트 문서</strong><p>프로젝트 목적·본인 역할·수행 내용이 담긴 문서를 등록해 주세요.</p>
     <label className="upload-file-picker"><input ref={fileRef} type="file" accept={data.upload_policy.extensions.map(extension=>`.${extension}`).join(',')} multiple onChange={upload} disabled={phase!=='ready'} aria-label="프로젝트 문서 선택"/><span className="upload-file-button" aria-hidden="true">파일 선택</span><span aria-hidden="true">여러 파일 선택 가능</span></label>
     <p className="field-help">파일을 이 영역으로 끌어다 놓거나 파일 선택 버튼을 눌러 주세요.</p>
     <p className="field-help">PDF, DOCX, UTF-8 TXT·마크다운(.md, .markdown) · 파일당 최대 {Math.floor(data.upload_policy.max_file_bytes/1024/1024)}MB · 최대 {data.upload_policy.max_files}개</p>
     {!data.documents.length&&!uploads.uploading&&!(data.uploads||[]).some(upload=>upload.status==='uploading')&&<button type="button" disabled={busy} onClick={()=>next(true)}>문서 없이 계속</button>}
    </div>
   </section>
   <section className="wire-box"><h3>등록한 문서</h3>
    <div className={data.documents.length?'table-scroll':'table-scroll documents-empty'}>
     <table><thead><tr><th scope="col" className="document-position">순서</th><th scope="col">파일명</th><th scope="col">읽기 상태</th><th scope="col">관리</th></tr></thead>
      <tbody>
       {data.documents.map(doc=><tr key={doc.document_id} data-document-id={doc.document_id}>
        <td className="document-position">{doc.position}</td><td>{doc.original_filename}</td>
        <td>{doc.extraction_status==='partial'&&doc.partial_confirmed_at?'일부 추출 · 범위 확인됨':labels[doc.extraction_status]}
         {doc.extraction_error_code==='ocr_budget_exceeded'&&<p className="field-help">OCR 사용량 제한 안내: 미국 태평양 시간 기준 다음 달에 다시 시도해 주세요.</p>}
         {doc.retry_available===false&&doc.extraction_status!=='pending'&&<p className="field-help">{studentMessage(doc.retry_reason,doc.retry_message)||'읽지 못한 부분은 원본에서 확인해 주세요.'}</p>}
        </td>
        <td><div className="doc-actions">
         {doc.extraction_status!=='pending'&&<button disabled={phase!=='ready'} onClick={e=>show(doc,e.currentTarget)}>{doc.extraction_status==='partial'?'읽힌 범위 확인':'읽힌 내용'}</button>}
         {doc.extraction_status!=='pending'&&<button disabled={busy||doc.retry_available===false} title={doc.retry_reason?studentMessage(doc.retry_reason,doc.retry_message)||'현재 다시 읽을 수 없습니다.':undefined} onClick={()=>retry(doc)}>다시 읽기</button>}
         <button disabled={busy} onClick={()=>remove(doc)}>삭제</button>
        </div></td>
       </tr>)}
       {!data.documents.length&&<tr><td colSpan="4" className="muted">등록된 문서가 없습니다.</td></tr>}
      </tbody>
     </table>
    </div>
    {uploads.items.length>0&&<><h4>업로드 큐</h4><p className="field-help">등록이 완료된 파일은 위 문서 목록에 표시됩니다.</p><div className="table-scroll document-upload-queue"><table><thead><tr><th scope="col" className="document-position">순서</th><th scope="col">파일명</th><th scope="col">업로드 상태</th><th scope="col">관리</th></tr></thead><tbody>
       {uploads.items.map(item=><tr key={item.key} data-upload-status={item.status}>
        <td className="document-position">—</td><td>{item.name}</td>
        <td><span role="status">{{queued:'업로드 대기 중',uploading:'업로드 중',uploaded:'등록 완료 · 목록 동기화 중',checking:'서버 상태 확인 중',server_uploading:'서버에서 업로드 중',interrupted:'업로드 중단',failed:'업로드 실패',duplicate:'중복 제외'}[item.status]}</span>{item.message&&<p className="field-help document-upload-message">{item.message}</p>}</td>
        <td><div className="doc-actions">
         {item.status==='failed'&&item.file&&<button disabled={phase!=='ready'} onClick={()=>uploads.retry(item)}>다시 업로드</button>}
         {item.status==='interrupted'&&<button disabled={phase!=='ready'} onClick={()=>fileRef.current?.click()}>파일 다시 선택</button>}
         {['failed','duplicate','interrupted'].includes(item.status)&&<button onClick={()=>uploads.dismiss(item.key)}>목록에서 닫기</button>}
        </div></td>
       </tr>)}
      </tbody>
     </table>
    </div></>}
   </section>
  </div>
  <p className="field-help" role="status">{phase==='working'?'처리 중입니다…':message}</p>
  <footer className="footer"><Link className="button" href="/input/basic">이전</Link><div className="documents-footer-actions"><button type="button" disabled={busy} onClick={refresh}>최신 상태 불러오기</button><button className="primary" disabled={!data.analysis_eligible||busy} onClick={()=>next()}>다음: 이수 과목</button></div></footer>
 </>}

 {modal&&<div className="modal-overlay" onClick={e=>{if(e.target===e.currentTarget)setModal(null)}}><section ref={modalRef} role="dialog" aria-modal="true" aria-labelledby="document-modal-title" className="document-modal"><div className="box-heading"><h2 id="document-modal-title">{modal.extraction_status==='partial'?'일부만 읽힌 문서 확인':'읽힌 내용'}</h2><button onClick={()=>setModal(null)}>닫기</button></div><p><strong>{modal.filename}</strong></p>{modal.limitations.length>0&&<div className="notice"><strong>읽기 한계</strong><p>원본과 아래 본문을 비교해 빠진 내용이 있는지 확인해 주세요. 이미지의 글자나 복잡한 표는 일부만 읽힐 수 있어요.</p></div>}<div className="source-text">{modal.extracted_text||'읽힌 본문이 없습니다.'}</div><p className="field-help">확인할 수 있는 내용은 위에 표시된 텍스트 범위입니다. 이미지에서 읽은 글자는 인식 오류가 있을 수 있으니 원본과 확인해 주세요.</p>{modal.extraction_status==='partial'&&modal.is_current_revision&&!modal.partial_confirmed&&<button className="primary" disabled={busy} onClick={confirm}>읽힌 범위를 확인했어요</button>}</section></div>}</>;
}
