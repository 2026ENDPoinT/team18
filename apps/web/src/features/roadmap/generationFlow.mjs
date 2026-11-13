export const generationTasks = [
 ['comparison', '직무 역량 비교'], ['courses', '수강 후보 추천'],
 ['activities', '공모전·대외활동 추천'], ['roadmap', '실행 로드맵 구성 및 결과 저장'],
];

export function completeResult(value, runId) {
 return value?.run_id === runId && value.generation_complete === true &&
  generationTasks.every(([key]) => value.generation_tasks?.[key] === 'success') &&
  ['success', 'partial'].includes(value.status) && !value.is_stale && !value.details_restricted &&
  Array.isArray(value.roadmap) && value.roadmap.length > 0 && value.roadmap.every(step =>
   step?.step_id && Array.isArray(step.tasks) && step.tasks.length > 0 && step.tasks.every(task => task?.task_id)) &&
  Array.isArray(value.recommended_courses) && value.recommended_courses.every(course => course?.course_id) &&
  Array.isArray(value.course_reasons) && value.course_reasons.length === value.recommended_courses.length &&
  new Set(value.course_reasons.map(reason => reason?.course_id)).size === value.course_reasons.length &&
  value.course_reasons.every(reason => typeof reason?.personalization_reason === 'string' && reason.personalization_reason.trim() &&
   value.recommended_courses.some(course => course.course_id === reason.course_id)) &&
  Array.isArray(value.skill_comparison?.comparisons) && value.skill_comparison?.job_analysis?.status === 'success' &&
  Boolean(value.skill_comparison.job_analysis.snapshot_id) &&
  value.activity_recommendations?.status === 'success' &&
  Array.isArray(value.activity_recommendations?.activities) && Array.isArray(value.activity_recommendations?.sources) &&
  value.activity_recommendations.sources.length > 0 && value.activity_recommendations.sources.every(source => source?.status === 'success');
}

// The deadline bounds client polling; it does not declare that the server failed.
export async function pollGeneration({ request, planId, runId, onState, cancelled = () => false,
 delay = ms => new Promise(resolve => setTimeout(resolve, ms)), now = Date.now,
 interval = 2500, maxElapsed = 11 * 60 * 1000, maxErrors = 4 }) {
 const started = now();
 let errors = 0;
 while (!cancelled() && now() - started < maxElapsed) {
  try {
   const data = await request(`/roadmap-inputs/${encodeURIComponent(planId)}/roadmaps/${encodeURIComponent(runId)}`,
    { signal: AbortSignal.timeout(15000) });
   if (cancelled()) return { kind: 'cancelled' };
   if (data.run_id !== runId) return { kind: 'invalid', data };
   errors = 0;
   onState(data);
   if (data.status === 'failed' || data.generation_expired) return { kind: 'failed', data };
   if (data.generation_complete) return { kind: completeResult(data, runId) ? 'complete' : 'invalid', data };
  } catch (error) {
   if (cancelled()) return { kind: 'cancelled' };
   if ([401, 403, 404].includes(error.status)) return { kind: 'unknown', error };
   if (++errors >= maxErrors) return { kind: 'unknown', error };
  }
  await delay(interval);
 }
 return { kind: cancelled() ? 'cancelled' : 'unknown' };
}
