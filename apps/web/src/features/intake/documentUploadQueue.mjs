const prefix = 'stepup:document-uploads:';
export const nameKey = name => name.toLowerCase();
export const pending = item => ['queued', 'uploading', 'uploaded', 'checking', 'server_uploading'].includes(item.status);
export const interruptedMessage = '업로드가 중단되었습니다. 원본 파일을 다시 선택해 주세요.';

export function readQueue(id, storage = globalThis.sessionStorage) {
 try {
  const rows = JSON.parse(storage.getItem(prefix + id) || '[]');
  return Array.isArray(rows) ? rows.filter(row => /^[0-9a-f-]{36}$/.test(row.key) && typeof row.name === 'string')
   .slice(-100).map(row => ({ key: row.key, name: row.name, size: row.size, status: 'checking' })) : [];
 } catch { return []; }
}

export function persistQueue(id, rows, storage = globalThis.sessionStorage) {
 if (!id) return;
 try {
  // Metadata is for reconciliation only. Never serialize a File or pretend
  // these names can be uploaded without the original bytes after a reload.
  storage.setItem(prefix + id, JSON.stringify(rows.filter(row => pending(row) || row.status === 'interrupted' || (row.status === 'failed' && row.attempted))
   .slice(-100).map(({ key, name, size }) => ({ key, name, size }))));
 } catch { /* Storage-disabled browsers still reconcile server reservations. */ }
}

export function reconcileQueue(rows, data) {
 if (!data) return rows;
 const documents = data.documents || [], uploads = data.uploads || [];
 const next = rows.flatMap(item => {
  if (documents.some(doc => doc.upload_id === item.key || (item.document?.document_id && doc.document_id === item.document.document_id))) return [];
  const server = uploads.find(upload => upload.upload_id === item.key);
  if (server?.status === 'removed') return [];
  if (server?.status === 'uploading') return [{ ...item, status: item.status === 'uploading' && item.file ? 'uploading' : 'server_uploading', message: '서버에서 파일을 저장하고 있습니다.' }];
  if (!item.file || server?.status === 'interrupted' || item.status === 'checking' || item.status === 'server_uploading') {
   return [{ ...item, status: item.file ? 'failed' : 'interrupted', message: interruptedMessage }];
  }
  return [item];
 });
 for (const upload of uploads) {
  if (upload.upload_id && upload.status === 'uploading' && !next.some(row => row.key === upload.upload_id)) {
   next.push({ key: upload.upload_id, name: upload.original_filename, status: 'server_uploading', message: '서버에서 파일을 저장하고 있습니다.' });
  }
 }
 return next;
}
