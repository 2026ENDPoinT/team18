-- Read-only post-deployment check. Expected: 68 total, 68 populated, 0 empty.
SELECT catalog_id,
       count(*) AS target_course_count,
       count(*) FILTER (WHERE btrim(coalesce(recommendation_reason, '')) <> '') AS populated_reason_count,
       count(*) FILTER (WHERE btrim(coalesce(recommendation_reason, '')) = '') AS empty_reason_count
FROM public.catalog_courses
WHERE catalog_id = 'seoultech-cse-2026-major-v1'
GROUP BY catalog_id;

-- Expected: no rows. The migration itself verifies all 68 IDs/names/codes.
SELECT catalog_id, course_id, course_name
FROM public.catalog_courses
WHERE catalog_id = 'seoultech-cse-2026-major-v1'
  AND (recommendation_reason IS NULL OR btrim(recommendation_reason) = '');

-- Review the stored strings; do not rewrite description_text or historical JSON.
SELECT catalog_id, course_id, course_name, recommendation_reason
FROM public.catalog_courses
WHERE catalog_id = 'seoultech-cse-2026-major-v1'
ORDER BY course_name, course_id;
