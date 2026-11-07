export class ApiError extends Error {
  constructor(message, status) { super(message); this.name = 'ApiError'; this.status = status; }
}

export async function apiRequest(path, options = {}) {
  let response;
  try {
    response = await fetch(`/api${path}`, { ...options, headers: { Accept: 'application/json', ...options.headers } });
  } catch {
    throw new ApiError('서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.', 0);
  }
  if (!response.ok) throw new ApiError('요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.', response.status);
  try { return await response.json(); } catch { throw new ApiError('서버 응답을 확인할 수 없습니다.', response.status); }
}
