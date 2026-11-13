import test from 'node:test';
import assert from 'node:assert/strict';
import { activityReason } from '../../src/features/roadmap/activityReason.mjs';

test('saved paragraph is used immediately; legacy evidence is deduplicated and grounded', () => {
 const quote = '데이터 분석 경진대회';
 const evidence = { posting_field: 'title', posting_quote: quote, matched_term: '데이터' };
 const item = { title: quote, evidence: [evidence, evidence], reasons: ['unsupported old text'] };
 assert.equal(activityReason({ ...item, personalization_reason: '저장된 개인화 문장입니다. 다음 문장입니다.' }), '저장된 개인화 문장입니다. 다음 문장입니다.');
 assert.equal(activityReason(item).split(quote).length - 1, 1);
 assert.ok(!activityReason(item).includes('unsupported'));
 assert.match(activityReason({ ...item, title: '다른 공고' }), /근거가 부족/);
 assert.match(activityReason({}), /원문/);
});
