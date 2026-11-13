import test from 'node:test';
import assert from 'node:assert/strict';
import { activityReason, activityReasonLabel } from '../../src/features/roadmap/activityReason.mjs';

test('only a saved Gemini paragraph is shown as a personalized reason', () => {
 const text = '저장된 개인화 문장입니다. 다음 문장입니다.';
 const item = { personalization_reason: text, reason_source: 'gemini', reason_status: 'generated' };
 assert.equal(activityReason(item), text);
 assert.equal(activityReasonLabel(item), '내 진로에 도움이 되는 이유');
 assert.equal(activityReason({ ...item, reason_status: undefined }), text);
});

test('fallback, unlabelled and legacy title prose never masquerade as Gemini', () => {
 for (const reason_source of [undefined, 'fallback', 'rule_evidence']) {
  const item = { title: '데이터 분석 대회', personalization_reason: '공고 제목에 데이터 분석 대회라고 안내되어 있습니다.', reason_source,
   reasons: ['unsupported old text'], evidence: [{ posting_field: 'title', posting_quote: '데이터 분석 대회', matched_term: '데이터' }] };
  assert.equal(activityReasonLabel(item), '추천 근거 확인 필요');
  assert.match(activityReason(item), /근거가 부족/);
  assert.doesNotMatch(activityReason(item), /공고 제목|원문|unsupported/);
 }
 assert.match(activityReason({ reason_status: 'generation_failed' }), /AI 개인화 추천 이유를 생성하지 못했습니다/);
 assert.match(activityReason({ reason_status: 'not_generated' }), /아직/);
 assert.equal(activityReasonLabel({ reason_source: 'gemini', personalization_reason: ' ' }), '추천 근거 확인 필요');
});
