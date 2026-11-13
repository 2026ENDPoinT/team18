'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import { apiRequest } from '../../lib/api/client';
import { nameKey, pending, readQueue, persistQueue, reconcileQueue } from './documentUploadQueue.mjs';

const duplicateMessage = name => `${name} 파일은 이미 등록되어 있거나 업로드 중이라 업로드하지 않았습니다.`;

// One registration queue per page preserves FileList order across selections and
// drops. OCR keeps running independently; each file has its own failure boundary.
export default function useDocumentUploads(id, data, load, onMessage) {
 const [items, setItems] = useState([]);
 const rows = useRef([]), running = useRef(false), mounted = useRef(true);
 const queueId = useRef(null);
 const current = useRef({ id, data, load, onMessage });
 current.current = { id, data, load, onMessage };
 const update = useCallback(change => {
  rows.current = change(rows.current);
  persistQueue(queueId.current, rows.current);
  if (mounted.current) setItems(rows.current);
 }, []);
 useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
 useEffect(() => {
  if (queueId.current === id) return;
  queueId.current = id;
  update(() => id ? readQueue(id) : []);
 }, [id, update]);
 useEffect(() => {
  update(list => reconcileQueue(list, data));
 }, [data, update]);

 async function drain() {
  if (running.current) return;
  running.current = true;
  try {
   let item;
   while (mounted.current && (item = rows.current.find(row => row.status === 'queued'))) {
    const { id: requestId, load: refresh } = current.current;
    update(list => list.map(row => row.key === item.key ? { ...row, status: 'uploading', attempted: true } : row));
    try {
     let result;
     // OCR completion can change input_revision between GET and POST. Retry
     // only that conflict; never automatically resend an ambiguous network error.
     for (let attempt = 0; attempt < 5; attempt++) {
      const latest = await refresh(requestId);
      if (latest.documents.some(doc => nameKey(doc.original_filename) === nameKey(item.file.name))) {
       throw Object.assign(new Error(duplicateMessage(item.file.name)), { code: 'duplicate_filename' });
      }
      const form = new FormData();
      form.append('file', item.file);
      form.append('expected_input_revision', String(latest.input_revision));
      try {
       if (!mounted.current || current.current.id !== requestId) return;
       result = await apiRequest(`/roadmap-inputs/${encodeURIComponent(requestId)}/documents`, { method: 'POST', body: form, headers: { 'Idempotency-Key': item.key } });
       break;
      } catch (error) {
       if (error.code !== 'revision_conflict' || attempt === 4) throw error;
      }
     }
     update(list => list.map(row => row.key === item.key ? { ...row, status: result.document ? 'uploaded' : 'server_uploading', document: result.document, message: '' } : row));
    } catch (error) {
     update(list => list.map(row => row.key === item.key ? { ...row, status: error.code === 'duplicate_filename' ? 'duplicate' : !error.code || error.status >= 500 ? 'checking' : 'failed', message: error.message } : row));
    }
    try { await refresh(requestId); }
    catch { current.current.onMessage('문서 목록을 동기화하지 못했습니다. 최신 상태 불러오기로 확인해 주세요.'); }
   }
  } finally { running.current = false; }
 }

 function enqueue(files, retryKey) {
  const policy = current.current.data?.upload_policy;
  if (!policy || !current.current.id || !files.length) return;
  const documents = current.current.data.documents;
  const existing = new Set(documents.map(doc => nameKey(doc.original_filename)));
  const waiting = rows.current.filter(item => pending(item) && !documents.some(doc => doc.upload_id === item.key || doc.document_id === item.document?.document_id));
  waiting.forEach(item => existing.add(nameKey(item.name)));
  const serverPending = (current.current.data.uploads || []).filter(item => item.status === 'uploading');
  serverPending.forEach(item => { if (item.original_filename) existing.add(nameKey(item.original_filename)); });
  let count = documents.length + serverPending.length + waiting.filter(item => !serverPending.some(server => server.upload_id === item.key)).length;
  const added = Array.from(files, file => {
   const item = { key: crypto.randomUUID(), name: file.name, size: file.size, file, status: 'queued' };
   if (existing.has(nameKey(file.name))) return { ...item, status: 'duplicate', message: duplicateMessage(file.name) };
   const extension = file.name.includes('.') ? file.name.split('.').at(-1).toLowerCase() : '';
   if (!policy.extensions.includes(extension)) return { ...item, status: 'failed', message: 'PDF, DOCX, UTF-8 TXT·마크다운(.md, .markdown) 파일만 지원합니다.' };
   if (!file.size) return { ...item, status: 'failed', message: '빈 파일은 등록할 수 없습니다.' };
   if (file.size > policy.max_file_bytes) return { ...item, status: 'failed', message: `파일당 최대 ${Math.floor(policy.max_file_bytes / 1024 / 1024)}MB까지 등록할 수 있습니다.` };
   if (count >= policy.max_files) return { ...item, status: 'failed', message: `기존 문서와 업로드 중인 파일을 포함해 최대 ${policy.max_files}개까지 등록할 수 있습니다.` };
   existing.add(nameKey(file.name)); count++;
   return item;
  });
  update(list => [...list.filter(item => item.key !== retryKey && !(['failed','interrupted'].includes(item.status) && added.some(row => row.status === 'queued' && nameKey(row.name) === nameKey(item.name)))), ...added]);
  current.current.onMessage('각 파일의 등록 결과와 읽기 상태를 목록에서 확인해 주세요.');
  void drain();
 }
 return {
  items,
  uploading: items.some(pending),
  enqueue,
  retry: item => { if (item.file) enqueue([item.file], item.key); },
  dismiss: key => update(list => list.filter(item => item.key !== key)),
 };
}
