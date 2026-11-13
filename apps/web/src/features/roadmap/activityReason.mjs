export function hasGeneratedActivityReason(item) {
 return item.reason_source === 'gemini' &&
  (!item.reason_status || item.reason_status === 'generated') &&
  typeof item.personalization_reason === 'string' && !!item.personalization_reason.trim();
}

export function activityReasonLabel(item) {
 return hasGeneratedActivityReason(item) ? '내 진로에 도움이 되는 이유' : '활동 참여 안내';
}

export function activityReason(item) {
 if (hasGeneratedActivityReason(item)) return item.personalization_reason.trim();
 // Only the versioned server guidance is trusted; legacy ranking prose is not
 // substituted for a generated paragraph.
 if (item.reason_source === 'fallback' && item.reason_evidence_level &&
     typeof item.personalization_reason === 'string' && item.personalization_reason.trim()) {
  return item.personalization_reason.trim();
 }
 return '현재 저장된 공고 정보로 활동의 주제와 관심 진로를 연결해 볼 수 있습니다. 구체적인 개인화 설명은 로드맵을 생성할 때 함께 준비됩니다.';
}

export function activityReasonNote(item) {
 if (hasGeneratedActivityReason(item)) {
  return item.reason_evidence_level === 'metadata_inference'
   ? '제목·분야를 바탕으로 제안한 참여 방향입니다.' : '';
 }
 if (item.reason_evidence_level === 'insufficient_information' || item.reason_status === 'needs_verification') {
  return '활동 정보가 적어 개인화 안내가 제한됩니다.';
 }
 if (item.reason_status === 'generation_failed') {
  return 'AI 설명을 생성하지 못해 기본 안내를 표시합니다.';
 }
 return 'AI 생성 전 기본 안내입니다.';
}
