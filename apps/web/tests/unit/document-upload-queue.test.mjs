import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readQueue, persistQueue, reconcileQueue } from '../../src/features/intake/documentUploadQueue.mjs';
const key = '10000000-0000-4000-8000-000000000001';
const row = { key, name: 'project.txt', size: 3, file: new Blob(['abc']), status: 'uploading' };
const memory = () => { const values = new Map(); return { getItem: key => values.get(key), setItem: (key, value) => values.set(key, value) }; };

test('reload never resurrects a File; missing server upload is interrupted', () => {
 const storage = memory(); persistQueue('plan', [row], storage);
 const restored = readQueue('plan', storage);
 assert.equal(restored[0].file, undefined);
 assert.equal(restored[0].status, 'checking');
 assert.equal(reconcileQueue(restored, { documents: [], uploads: [] })[0].status, 'interrupted');
 assert.deepEqual(readQueue('other-plan', storage), []);
});
test('server identity restores success and real progress, never filename guessing', () => {
 const restored = [{ ...row, file: undefined, status: 'checking' }];
 assert.deepEqual(reconcileQueue(restored, { documents: [{ upload_id: key, document_id: 'doc' }], uploads: [] }), []);
 assert.equal(reconcileQueue(restored, { documents: [{ original_filename: row.name }], uploads: [] })[0].status, 'interrupted');
 const uploads = [{ upload_id: key, original_filename: row.name, status: 'uploading' }];
 assert.equal(reconcileQueue(restored, { documents: [], uploads })[0].status, 'server_uploading');
 assert.equal(reconcileQueue([], { documents: [], uploads })[0].status, 'server_uploading');
 assert.equal(reconcileQueue(restored, { documents: [], uploads: [{ ...uploads[0], status: 'interrupted' }] })[0].status, 'interrupted');
});
test('local queue bytes stay usable; a failed known upload frees capacity', () => {
 assert.equal(reconcileQueue([row], { documents: [], uploads: [] })[0].file, row.file);
 assert.equal(reconcileQueue([row], { documents: [], uploads: [{ upload_id: key, status: 'interrupted' }] })[0].status, 'failed');
 const storage = memory(); persistQueue('plan', [{ ...row, attempted: true, status: 'failed' }], storage);
 assert.equal(reconcileQueue(readQueue('plan', storage), { documents: [], uploads: [] })[0].status, 'interrupted');
});
