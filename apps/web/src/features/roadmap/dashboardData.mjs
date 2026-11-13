import { experiencePresentation } from './experiencePresentation.mjs';
import { coursePresentation } from './coursePresentation.mjs';
import { orderedSkills } from './jobSkillAnalysis.mjs';
import { roadmapProgress, courseReason, experienceAnswer, resultHref } from './resultPresentation.mjs';

// GET only. A rejected resource stays an error and cannot become a zero count.
export async function loadDashboardResources(apiRequest, plan) {
 const base = `/roadmap-inputs/${encodeURIComponent(plan.request_id)}`;
 const paths = {
  reference: '/reference', documents: `${base}/documents`, experience: `${base}/project-experience-analysis`,
  skills: `${base}/skill-comparison`, roadmap: `${base}/roadmap`,
  courses: plan.input.catalog_id ? `${base}/courses?catalog_id=${encodeURIComponent(plan.input.catalog_id)}&page_size=1` : null,
  activities: plan.input.career_goal?.trim() ? `${base}/activities` : null,
 };
 const entries = Object.entries(paths);
 const results = await Promise.allSettled(entries.map(([, path]) => path ? apiRequest(path) : Promise.resolve(null)));
 return Object.fromEntries(entries.map(([key], i) => [key, results[i].status === 'fulfilled' ? { data: results[i].value } : { error: results[i].reason.message || '조회 실패' }]));
}

export function dashboardCards(plan, resources) {
 const input = plan.input;
 const data = key => resources[key]?.data;
 const error = key => resources[key]?.error;
 const make = (key, title, href, lines, action) => ({ key, title, href, lines, action, error: error(key) });
 const ref = data('reference');
 const school = ref?.universities.find(item => item.university_id === input.university_id)?.university_name;
 const department = ref?.departments.find(item => item.department_id === input.department_id)?.department_name;
 const basic = make('basic', '기본 정보', '/input/basic', [
  [school || (input.university_id ? '학교명 조회 필요' : '학교 미선택'), department || (input.department_id ? '학과명 조회 필요' : '학과 미선택'), input.year_level ? `${input.year_level}학년` : '학년 미입력'].join(' · '),
  input.career_goal || '목표·관심 분야를 입력해 주세요.', `희망 직무: ${input.target_role || '아직 정하지 않았어요'}`,
 ], '기본 정보 확인·수정');
 if (error('reference')) basic.lines.push('학교·학과 이름을 불러오지 못했습니다. 다시 조회해 주세요.');
 const docs = data('documents')?.documents || [];
 const recent = [...docs].sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''))[0];
 const readLabels = { ready: '읽기 완료', pending: '읽는 중', partial: '일부만 읽힘 · 확인 필요', needs_ocr: 'OCR 필요', failed: '읽기 실패 · 재시도 필요' };
 const documents = make('documents', '경험·문서', '/input/documents', [
  `등록 문서 ${docs.length}개 · 읽기 완료 ${docs.filter(doc => doc.extraction_status === 'ready').length}개`,
  ...(recent ? [`최근 파일: ${recent.original_filename}`, readLabels[recent.extraction_status] || '읽기 상태 확인 필요'] : ['등록한 문서가 없습니다. 문서를 올리거나 문서 없이 계속할 수 있어요.']),
 ], '문서와 읽힌 내용 확인');
 const selected = data('courses');
 const courses = make('courses', '이수 과목', '/input/courses', selected ? [
  `선택 ${selected.selection_summary.count}개 · ${selected.selection_summary.known_credits}학점${selected.selection_summary.unknown_credits_count ? ` · 학점 미제공 ${selected.selection_summary.unknown_credits_count}개` : ''}`,
  selected.selected_courses.slice(0, 3).map(course => course.course_name).join(', ') || '선택한 과목이 없습니다. 0개로도 확인할 수 있어요.',
 ] : ['연결된 과목 목록이 없습니다. 기본 정보에서 학교·학과를 확인해 주세요.'], '이수 선택 확인·수정');
 const analysis = data('experience');
 const availableExperiences = (analysis?.experiences || []).filter(item => item.user_answer?.status !== 'no_experience');
 const rankExperience = item => {
  const personal = experiencePresentation(item).contribution_scope === 'personal';
  return personal && ['confirmed', 'corrected'].includes(item.user_answer?.status) ? 0 : personal ? 1 : 2;
 };
 const experience = [...availableExperiences].sort((a, b) => rankExperience(a) - rankExperience(b))[0];
 const shown = experience && experiencePresentation(experience);
 const exploration = make('experience', '역량 탐색', '/input/review', [
  ...(shown ? [shown.activity, `기술 스택: ${shown.skill_name} · ${shown.contribution_scope === 'team' ? '팀 수행' : shown.contribution_scope === 'personal' ? '본인 직접 수행' : '담당 범위 확인 필요'}`, experienceAnswer(experience)] : [analysis?.experiences?.length ? '분석된 항목 모두에 경험 없다고 답했어요. 답변을 확인하거나 수정해 주세요.' : analysis?.status === 'error' ? '경험 분석을 완료하지 못했습니다. 다시 실행해 주세요.' : '아직 확인할 경험 카드가 없습니다. 읽힌 문서로 경험 분석을 실행해 주세요.']),
  ...(analysis ? [`경험 분석 문서 ${analysis.analyzed_documents}개 · 확인 가능한 경험 ${analysis.verified_experiences}개`] : []),
 ], '맡은 일과 기술 확인·수정');
 const comparison = data('skills'), jobs = comparison?.job_analysis;
 const skills = make('skills', '직무 역량 비교', resultHref('skills'), jobs?.snapshot_id ? [
  `분석한 직무: ${jobs.canonical_role || jobs.target_role || '직무 미확인'}`,
  `대표 요구 기술: ${orderedSkills({ ...jobs, comparison }).filter(skill => skill.recommendation_eligible !== false).slice(0, 3).map(skill => skill.name).join(', ') || '확인된 기술 없음'}`,
 ] : [jobs?.status === 'error' ? '직무 분석을 완료하지 못했습니다. 다시 실행해 주세요.' : '현재 진로 정보로 저장된 분석이 없습니다. 직무 분석을 실행해 주세요.'], '직무 분석 확인·실행');
 const run = data('roadmap'), usable = run?.roadmap && !run.details_restricted;
 const progress = roadmapProgress(usable ? run : null);
 const roadmap = make('roadmap', '실행 로드맵', resultHref('roadmap'), usable ? [
  progress.next ? `다음 할 일: ${progress.next.task.title}` : progress.total ? '모든 작업을 완료했어요.' : '저장된 실행 작업이 없습니다.',
  `작업 완료 ${progress.completed} / ${progress.total}개`,
 ] : [run?.details_restricted ? '근거가 변경되어 상세 접근이 제한된 결과입니다.' : '저장된 로드맵이 없습니다. 결과 화면에서 생성해 주세요.'], '지금 할 일 확인');
 const candidate = usable && coursePresentation(run.recommended_courses || []).cards[0];
 const recommendations = make('recommendedCourses', '수강 후보', resultHref('courses'), candidate ? [candidate.course_name, courseReason(candidate)] : [usable ? '현재 근거로 추천된 과목이 없습니다. 과목 목록과 이수 선택을 확인해 주세요.' : '로드맵을 생성하면 실제 추천 과목을 확인할 수 있어요.'], '수강 후보와 학습 내용 확인');
 recommendations.error = error('roadmap');
 if (run?.is_stale) { roadmap.lines.push('이전 입력·분석 기준의 저장 결과'); recommendations.lines.push('이전 입력·분석 기준의 저장 결과'); }
 const activityData = data('activities'), activity = activityData?.activities?.[0];
 const activities = make('activities', '공모전·대외활동', resultHref('activities'), activity ? [activity.title, `접수 마감: ${activity.deadline_label}`, activity.reasons?.[0]] : [input.career_goal?.trim() ? '현재 조회 가능한 공고 중 추천 조건에 맞는 활동이 없습니다.' : '기본 정보에 목표를 저장하면 문서 없이 추천 활동을 볼 수 있어요.'], '추천 활동과 접수 기간 확인');
 if (activityData?.status === 'error') activities.error = '추천 공고를 불러오지 못했습니다. 다시 조회해 주세요.';
 if (activityData?.status === 'partial') activities.lines.push('일부 출처의 조회가 완료되지 않아 확인된 공고만 표시합니다.');
 return [basic, documents, courses, exploration, skills, roadmap, recommendations, activities];
}

export function resumeDestination(plan, resources) {
 if (!plan.input.career_goal?.trim()) return '/input/basic';
 if (resources.roadmap?.data?.roadmap) return resultHref('roadmap');
 if (resources.skills?.data?.job_analysis?.snapshot_id) return resultHref('skills');
 if (resources.experience?.data?.experiences?.length || ['confirmed', 'partial'].includes(plan.review_status)) return '/input/review';
 if (resources.courses?.data?.selection_summary?.count > 0) return '/input/courses';
 if (resources.documents?.data?.documents?.length) return resources.documents.data.analysis_eligible ? '/input/courses' : '/input/documents';
 if (Object.values(resources).some(resource => resource.error)) return '/dashboard';
 return '/input/documents';
}
