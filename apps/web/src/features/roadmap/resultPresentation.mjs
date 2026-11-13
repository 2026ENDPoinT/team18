export const resultTabs = [
 { key: 'roadmap', label: '실행 로드맵' },
 { key: 'skills', label: '직무 역량 비교' }, { key: 'courses', label: '수강 후보' },
 { key: 'activities', label: '공모전·대외활동' },
];
export const resultHref = key => `/result?tab=${key}`;
export const roadmapDetailHref = `${resultHref('roadmap')}&view=steps`;

// Only the analyzed role field is a job name. Search keywords and skill names
// cannot be substituted, including before an analysis has been saved.
export function relatedRoles(comparison) {
 const job = comparison?.job_analysis;
 if (!job?.snapshot_id) return [];
 const role = (job.canonical_role || job.target_role || '').trim();
 return role ? [role] : [];
}

// Both the dashboard and the result use persisted task progress, never inferred skill levels.
export function roadmapProgress(result) {
 const steps = [...(result?.roadmap || [])].sort((a, b) => a.order - b.order);
 const tasks = steps.flatMap(step => (step.tasks || []).map(task => ({ step, task })));
 const remaining = tasks.filter(({ task }) => !task.is_completed);
 const ready = remaining.find(({ step }) => (step.depends_on || []).every(id =>
  steps.find(parent => parent.step_id === id)?.tasks.every(task => task.is_completed)));
 return { total: tasks.length, completed: tasks.length - remaining.length, next: ready || remaining[0] || null };
}

export function courseLearning(course) {
 const quotes = (course.keyword_evidence || []).filter(item => item.keyword_role === 'learning').map(item => item.evidence_text).filter(Boolean);
 return [...new Set(quotes)].join(' ') || (course.course_evidence && course.course_evidence !== course.course_name ? course.course_evidence : '공식 학습 내용이 제공되지 않았습니다.');
}
export const courseReason = course => course.personalization_reason || course.reason || '저장된 추천 이유가 없습니다.';
export const experienceAnswer = item => ({ confirmed: '본인 경험으로 확인', corrected: '사용자 수정 답변', unknown: '판단 보류', no_experience: '경험 없다고 답변' })[item.user_answer?.status] || '본인 확인 필요';
