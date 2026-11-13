import { orderedSkills } from './jobSkillAnalysis.mjs';

export const resultTabs = [
 { key: 'roadmap', label: '결과 요약' },
 { key: 'courses', label: '수강 후보' }, { key: 'skills', label: '직무 역량 비교' },
 { key: 'activities', label: '공모전·대외활동' },
];
export const resultHref = key => `/result?tab=${key}`;

// Reuse the saved analysis and the detail view's ordering, without generating data.
export function analyzedSkills(comparison) {
 const job = comparison?.job_analysis;
 if (!job?.snapshot_id) return [];
 return orderedSkills({ ...job, comparison }).filter(skill => typeof skill.name === 'string' && skill.name.trim());
}

export function courseLearning(course) {
 const quotes = (course.keyword_evidence || []).filter(item => item.keyword_role === 'learning').map(item => item.evidence_text).filter(Boolean);
 return [...new Set(quotes)].join(' ') || (course.course_evidence && course.course_evidence !== course.course_name ? course.course_evidence : '공식 학습 내용이 제공되지 않았습니다.');
}
export const courseReason = course => course.personalization_reason || course.reason || '저장된 추천 이유가 없습니다.';
export const experienceAnswer = item => ({ confirmed: '본인 경험으로 확인', corrected: '사용자 수정 답변', unknown: '판단 보류', no_experience: '경험 없다고 답변' })[item.user_answer?.status] || '본인 확인 필요';
