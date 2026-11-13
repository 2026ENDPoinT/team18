import test from 'node:test';
import assert from 'node:assert/strict';
import { activityReason, activityReasonLabel, activityReasonNote } from '../../src/features/roadmap/activityReason.mjs';

test('validated Gemini paragraphs retain their existing presentation', () => {
 const text = '저장된 개인화 문장입니다. 다음 문장입니다.';
 const item = { personalization_reason: text, reason_source: 'gemini', reason_status: 'generated', reason_evidence_level: 'verified_detail' };
 assert.equal(activityReason(item), text);
 assert.equal(activityReasonLabel(item), '내 진로에 도움이 되는 이유');
 assert.equal(activityReasonNote(item), '');
 assert.equal(activityReason({ ...item, reason_status: undefined }), text);
 assert.match(activityReasonNote({ ...item, reason_evidence_level: 'metadata_inference' }), /제목·분야/);
});

test('server fallback has useful text and a separate non-AI label', () => {
 const text = '소프트웨어 관련 활동으로, 백엔드 개발을 준비하며 아이디어를 탐색해 볼 수 있습니다.';
 const item = { personalization_reason: text, reason_source: 'fallback', reason_status: 'generation_failed', reason_evidence_level: 'metadata_inference' };
 assert.equal(activityReason(item), text);
 assert.equal(activityReasonLabel(item), '활동 참여 안내');
 assert.match(activityReasonNote(item), /AI 설명을 생성하지 못해 기본 안내/);
 assert.match(activityReasonNote({ ...item, reason_status: 'not_generated' }), /AI 생성 전/);
 assert.match(activityReasonNote({ ...item, reason_evidence_level: 'insufficient_information' }), /정보가 적어/);
});

test('legacy prose is not presented as a generated reason or an empty card', () => {
 for (const reason_source of [undefined, 'fallback', 'rule_evidence']) {
  const item = { title: '데이터 분석 대회', personalization_reason: '공고 제목에 데이터 분석 대회라고 안내되어 있습니다.', reason_source,
   reasons: ['unsupported old text'], evidence: [{ posting_field: 'title', posting_quote: '데이터 분석 대회', matched_term: '데이터' }] };
  assert.equal(activityReasonLabel(item), '활동 참여 안내');
  assert.ok(activityReason(item).length > 30);
  assert.doesNotMatch(activityReason(item), /공고 제목|원문|unsupported|제공하지 않습니다/);
 }
 assert.equal(activityReasonLabel({ reason_source: 'gemini', personalization_reason: ' ' }), '활동 참여 안내');
});
