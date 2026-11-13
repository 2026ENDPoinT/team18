import { authClient } from './auth';
// Keep service configuration and storage diagnostics out of student-facing messages.
// Codes and structured diagnostics remain on ApiError for conflict handling.
export function studentMessage(code, fallback) {
 const messages = {
  auth_unavailable: '지금은 로그인 상태를 확인할 수 없습니다. 잠시 후 다시 시도해 주세요.',
  feature_unavailable: '현재 문서 기능을 이용할 수 없습니다.',
  gemini_not_configured: '현재 분석 서비스를 이용할 수 없습니다. 잠시 후 다시 시도해 주세요.',
  gemini_auth_failed: '현재 분석 서비스를 이용할 수 없습니다. 잠시 후 다시 시도해 주세요.',
  evidence_unavailable: '문서가 변경되어 경험을 다시 확인해야 합니다. 최신 내용을 불러와 주세요.',
  ocr_disabled: '현재 이미지 글자를 읽을 수 없습니다. 텍스트가 포함된 문서를 이용하거나 문서 없이 계속해 주세요.',
  ocr_credentials_missing: '현재 이미지 글자를 읽을 수 없습니다. 잠시 후 다시 시도하거나 텍스트 문서를 등록해 주세요.',
  ocr_credentials_invalid: '현재 이미지 글자를 읽을 수 없습니다. 잠시 후 다시 시도하거나 텍스트 문서를 등록해 주세요.',
  ocr_auth_error: '현재 이미지 글자를 읽을 수 없습니다. 잠시 후 다시 시도하거나 텍스트 문서를 등록해 주세요.',
  ocr_timeout: '이미지 읽기 시간이 초과되었습니다. 읽힌 내용을 확인하거나 텍스트 문서를 등록해 주세요.',
  ocr_uncertain: '이미지 읽기 결과를 확인하지 못했습니다. 읽힌 내용을 확인하거나 텍스트 문서를 등록해 주세요.',
  ocr_api_error: '이미지를 읽지 못했습니다. 읽힌 내용을 확인하거나 텍스트 문서를 등록해 주세요.',
  ocr_storage_error: '문서 읽기 결과를 확인하지 못했습니다. 잠시 후 다시 확인해 주세요.',
 };
 if (messages[code]) return messages[code];
 if (['revision_conflict', 'validation_error', 'not_found'].includes(code) && fallback?.includes('버전')) return '내용이 변경되었거나 확인할 수 없습니다. 최신 내용을 불러와 다시 시도해 주세요.';
 return fallback;
}
export class ApiError extends Error {
  constructor(message, status, code, details = {}) {
    super(studentMessage(code, message)); this.name = 'ApiError'; this.status = status; this.code = code;
    this.runId = details.run_id; this.detailCode = details.detail_code; this.fieldPath = details.field_path;
  }
}
export async function apiRequest(path, options = {}) {
  let response;
  const { expectedUserId, ...fetchOptions } = options;
  const { data, error } = await authClient().auth.getSession();
  if (error || (expectedUserId && data.session?.user?.id !== expectedUserId)) throw new ApiError('인증 세션을 확인할 수 없습니다. 다시 로그인해 주세요.', 401);
  try {
    response = await fetch(`/api${path}`, { ...fetchOptions, cache: 'no-store', headers: { Accept: 'application/json', ...(fetchOptions.body && !(fetchOptions.body instanceof FormData) ? { 'Content-Type': 'application/json' } : {}), ...fetchOptions.headers, ...(data.session ? { Authorization: `Bearer ${data.session.access_token}` } : {}) } });
  } catch { throw new ApiError('서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.', 0); }
  let result;
  try { result = await response.json(); } catch { throw new ApiError('서버 응답을 확인할 수 없습니다.', response.status); }
  if (!response.ok) throw new ApiError(result.message || '요청을 처리하지 못했습니다.', response.status, result.error, result);
  return result;
}
