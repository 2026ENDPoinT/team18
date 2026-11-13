import { resultHref } from './resultPresentation.mjs';

// Resume uses saved progress only and never starts an analysis or creates a plan.
export async function loadResumeResources(apiRequest, plan) {
 const base = `/roadmap-inputs/${encodeURIComponent(plan.request_id)}`;
 const paths = {
  documents: `${base}/documents`, experience: `${base}/project-experience-analysis`,
  skills: `${base}/skill-comparison`, roadmap: `${base}/roadmap`,
  courses: plan.input.catalog_id ? `${base}/courses?catalog_id=${encodeURIComponent(plan.input.catalog_id)}&page_size=1` : null,
 };
 const entries = Object.entries(paths);
 const results = await Promise.allSettled(entries.map(([, path]) => path ? apiRequest(path) : Promise.resolve(null)));
 return Object.fromEntries(entries.map(([key], i) => [key, results[i].status === 'fulfilled' ? { data: results[i].value } : { error: results[i].reason?.message || '조회 실패' }]));
}

export function resumeDestination(plan, resources) {
 if (!plan.input.career_goal?.trim()) return '/input/basic';
 if (resources.roadmap?.data?.roadmap) return resultHref('roadmap');
 if (resources.skills?.data?.job_analysis?.snapshot_id) return resultHref('skills');
 if (resources.experience?.data?.experiences?.length || ['confirmed', 'partial'].includes(plan.review_status)) return '/input/review';
 if (resources.courses?.data?.selection_summary?.count > 0) return '/input/courses';
 if (resources.documents?.data?.documents?.length) return resources.documents.data.analysis_eligible ? '/input/courses' : '/input/documents';
 if (Object.values(resources).some(resource => resource.error)) throw new Error('저장된 진행 상태를 확인하지 못했습니다. 다시 시도해 주세요.');
 return '/input/documents';
}
