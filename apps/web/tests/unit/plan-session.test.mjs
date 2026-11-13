import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';

async function setup() {
 const storage = new Map();
 const sessionStorage = { getItem: key => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key) };
 let user = 'user-a', latest = { found: false, request: null }, calls = [], signOutError = null;
 const signOutCalls = [];
 const context = vm.createContext({ sessionStorage });
 const session = new vm.SourceTextModule(await readFile(new URL('../../src/lib/api/session.js', import.meta.url), 'utf8'), { context });
 const auth = new vm.SyntheticModule(['authClient'], function () {
  this.setExport('authClient', () => ({ auth: {
   getSession: async () => ({ data: { session: user ? { user: { id: user } } : null }, error: null }),
   signOut: async options => { signOutCalls.push(options); if (!signOutError) user = null; return { error: signOutError }; },
  } }));
 }, { context });
 const client = new vm.SyntheticModule(['apiRequest'], function () {
  this.setExport('apiRequest', async (path, options) => { calls.push([path, options]); if (latest instanceof Error) throw latest; return latest; });
 }, { context });
 await session.link(specifier => specifier === './auth' ? auth : client);
 await session.evaluate();
 return { ...session.namespace, storage, calls, signOutCalls, setSignOutError: value => { signOutError = value; }, setUser: value => { user = value; }, setLatest: value => { latest = value; } };
}

test('logout ends the current session and clears its selected plan; a failed logout preserves both for retry', async () => {
 const s = await setup();
 await s.selectPlan('saved-plan', 'user-a');
 s.setSignOutError(new Error('offline'));
 await assert.rejects(s.signOutSession(), /offline/);
 assert.equal(await s.resolvePlanId(), 'saved-plan');
 s.setSignOutError(null);
 await s.signOutSession();
 assert.equal(s.storage.size, 0);
 await assert.rejects(s.resolvePlanId(), /다시 로그인/);
 assert.ok(s.signOutCalls.every(options => options.scope === 'local'), 'other device sessions are retained');
});

test('selected plan remains selected even when another plan is the latest', async () => {
 const s = await setup();
 s.setLatest({ found: true, request: { request_id: 'older' } });
 await s.selectPlan('new', 'user-a');
 assert.equal(await s.resolvePlanId(), 'new');
 assert.equal(s.calls.length, 0);
});

test('selection is scoped to the authenticated user and the tab', async () => {
 const s = await setup();
 await s.selectPlan('user-a-plan', 'user-a');
 s.setUser('user-b');
 s.setLatest({ found: true, request: { request_id: 'user-b-plan' } });
 assert.equal(await s.resolvePlanId(), 'user-b-plan');
 assert.equal(s.storage.get('roadmap_request_owner'), 'user-b');
 assert.equal(s.calls[0][1].expectedUserId, 'user-b');
 s.setUser(null);
 await assert.rejects(s.resolvePlanId());
 assert.equal(s.storage.size, 0);
});

test('session change while selecting cannot retain a previous user plan', async () => {
 const s = await setup();
 await s.selectPlan('old', 'user-a');
 s.setUser('user-b');
 await assert.rejects(s.selectPlan('new', 'user-a'));
 assert.equal(s.storage.size, 0);
});

test('missing, failed, and malformed resume responses stay distinct', async () => {
 const s = await setup();
 assert.equal(await s.resolvePlanId(), null);
 s.setLatest(new Error('offline'));
 await assert.rejects(s.resolvePlanId(), /offline/);
 s.setLatest({});
 await assert.rejects(s.resolvePlanId(), /계획 응답/);
 s.setLatest({ found: true, request: null });
 await assert.rejects(s.resolvePlanId(), /계획 응답/);
});

test('authenticated requests use the intended user token and reject account changes', async () => {
 let user = 'user-a';
 const calls = [];
 const context = vm.createContext({ FormData, fetch: async (...args) => { calls.push(args); return { ok: true, json: async () => ({ found: false }) }; } });
 const module = new vm.SourceTextModule(await readFile(new URL('../../src/lib/api/client.js', import.meta.url), 'utf8'), { context });
 const auth = new vm.SyntheticModule(['authClient'], function () {
  this.setExport('authClient', () => ({ auth: { getSession: async () => ({ data: { session: { user: { id: user }, access_token: 'token-a' } }, error: null }) } }));
 }, { context });
 await module.link(() => auth);
 await module.evaluate();
 await module.namespace.apiRequest('/roadmap-inputs/resume', { expectedUserId: 'user-a' });
 assert.equal(calls[0][1].headers.Authorization, 'Bearer token-a');
 assert.equal(calls[0][1].expectedUserId, undefined);
 user = 'user-b';
 await assert.rejects(module.namespace.apiRequest('/roadmap-inputs', { method: 'POST', expectedUserId: 'user-a' }));
 assert.equal(calls.length, 1);
});

test('roadmap API failures retain safe diagnostic metadata for the result screen', async () => {
 const context = vm.createContext({ FormData, fetch: async () => ({ ok: false, status: 502, json: async () => ({
  error: 'gemini_invalid_response', message: '이전 결과는 유지됩니다.',
  run_id: 'failed-run', detail_code: 'course_evidence_mismatch', field_path: '$.recommended_courses[0].course_evidence',
 }) }) });
 const module = new vm.SourceTextModule(await readFile(new URL('../../src/lib/api/client.js', import.meta.url), 'utf8'), { context });
 const auth = new vm.SyntheticModule(['authClient'], function () {
  this.setExport('authClient', () => ({ auth: { getSession: async () => ({ data: { session: null }, error: null }) } }));
 }, { context });
 await module.link(() => auth); await module.evaluate();
 await assert.rejects(module.namespace.apiRequest('/roadmap-inputs/plan/roadmap'), error => {
  assert.equal(error.code, 'gemini_invalid_response');
  assert.equal(error.runId, 'failed-run');
  assert.equal(error.detailCode, 'course_evidence_mismatch');
  assert.equal(error.fieldPath, '$.recommended_courses[0].course_evidence');
  return true;
 });
 const configured = new module.namespace.ApiError('Gemini API 키가 설정되지 않았습니다.', 503, 'gemini_not_configured');
 assert.match(configured.message, /분석 서비스를 이용할 수 없습니다/);
 assert.doesNotMatch(configured.message, /API|키|설정/);
 assert.equal(configured.code, 'gemini_not_configured');
 assert.equal(module.namespace.studentMessage('ocr_credentials_invalid', '서버 인증 설정 오류'), '현재 이미지 글자를 읽을 수 없습니다. 잠시 후 다시 시도하거나 텍스트 문서를 등록해 주세요.');
});
