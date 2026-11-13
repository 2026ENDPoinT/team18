export function hasGeneratedActivityReason(item) {
 return item.reason_source === 'gemini' &&
  (!item.reason_status || item.reason_status === 'generated') &&
  typeof item.personalization_reason === 'string' && !!item.personalization_reason.trim();
}

export function activityReasonLabel(item) {
 return hasGeneratedActivityReason(item) ? '내 진로에 도움이 되는 이유' : '추천 근거 확인 필요';
}

export function activityReason(item) {
 // The server validates structured sentences before persisting the paragraph.
 // Legacy ranking prose and fallbacks must never look like Gemini explanations.
 if (hasGeneratedActivityReason(item)) return item.personalization_reason.trim();
 if (item.reason_status === 'generation_failed') {
  return 'AI 개인화 추천 이유를 생성하지 못했습니다. 이 활동이 진로에 도움이 되는지는 아직 검증되지 않았습니다.';
 }
 if (item.reason_status === 'not_generated') {
  return '아직 개인화 추천 이유가 생성되지 않았습니다. 로드맵 생성 시 확인된 활동 근거로 설명을 작성합니다.';
 }
 return '상세 과제와 결과물 근거가 부족해 개인화 추천 이유를 제공하지 않습니다.';
}
