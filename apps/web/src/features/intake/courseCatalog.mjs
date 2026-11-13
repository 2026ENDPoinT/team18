// Paging is a transport detail. Keep the API's bilingual groups and IDs intact.
export async function loadCourseCatalog(request, requestId, catalogId) {
 const courses = [], ids = new Set();
 let first, page = 1;
 do {
  const query = new URLSearchParams({ catalog_id: catalogId, page: String(page), page_size: '100' });
  const result = await request(`/roadmap-inputs/${encodeURIComponent(requestId)}/courses?${query}`);
  if (!first) first = result;
  if (result.catalog_id !== catalogId || result.selection_revision !== first.selection_revision ||
      result.input_revision !== first.input_revision || result.catalog_version !== first.catalog_version || result.total !== first.total) {
   throw Object.assign(new Error('목록을 불러오는 동안 입력이 변경되었습니다. 최신 상태를 불러와 주세요.'), { status: 409 });
  }
  if (result.page !== page || (courses.length < result.total && !result.courses.length)) {
   throw new Error('전체 과목 목록을 불러오지 못했습니다. 다시 불러와 주세요.');
  }
  for (const course of result.courses) {
   if (ids.has(course.course_id)) throw new Error('과목 목록이 변경되었습니다. 다시 불러와 주세요.');
   ids.add(course.course_id); courses.push(course);
  }
  page += 1;
 } while (courses.length < first.total);
 if (courses.length !== first.total) throw new Error('전체 과목 수를 확인하지 못했습니다. 다시 불러와 주세요.');
 return { ...first, courses };
}

export function withPendingSelections(data, pending) {
 if (!data || !pending.size) return data;
 const courses = data.courses.map(course => pending.has(course.course_id)
  ? { ...course, is_completed: pending.get(course.course_id) } : course);
 const selected = courses.filter(course => course.is_completed);
 return { ...data, courses, selected_courses: selected, review_status: 'unconfirmed',
  selection_summary: { count: selected.length },
  out_of_scope_completed_courses: data.out_of_scope_completed_courses.filter(course => pending.get(course.course_id) !== false),
 };
}
export function courseYear(course) {
 return [1, 2, 3, 4].includes(Number(course.recommended_year)) ? Number(course.recommended_year) : null;
}
export function courseYears(courses) {
 const groups = new Map([1, 2, 3, 4, null].map(year => [year, []]));
 for (const course of courses) groups.get(courseYear(course)).push(course);
 return [...groups].filter(([year, items]) => year !== null || items.length).map(([year, items]) => ({ year, courses: items }));
}
export function courseTerm(course) {
 const term = String(course.recommended_term ?? '').trim();
 return /^(1|2)(학기)?$/.test(term) ? Number(term[0]) : null;
}
export function filterCourses(courses, { search, only }) {
 const query = search.trim().toLocaleLowerCase();
 return courses.filter(course => (!query || `${course.course_name} ${course.course_code || ''}`.toLocaleLowerCase().includes(query)) &&
  (!only || course.is_completed));
}
const courseNameCollator = new Intl.Collator('ko', { numeric: true, sensitivity: 'base' });
export function sortCoursesByName(courses) {
 return [...courses].sort((a, b) => courseNameCollator.compare(a.course_name.trim(), b.course_name.trim()) || a.course_id.localeCompare(b.course_id));
}
export function termSections(courses) {
 return [1, 2, null].map(term => ({ term, title: term ? `${term}학기` : '학기 미지정',
  courses: sortCoursesByName(courses.filter(course => courseTerm(course) === term)),
 }));
}
