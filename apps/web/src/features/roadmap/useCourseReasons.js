'use client';
import { courseReason } from './resultPresentation.mjs';

// Reasons are part of the persisted result. Mounts, refreshes and tab/card
// interactions only render that snapshot, including legacy catalog fallbacks.
export default function useCourseReasons(result) {
 if (result?.details_restricted) return { phase: 'ready', reasons: {} };
 return { phase: 'ready', reasons: {
  ...Object.fromEntries((result?.recommended_courses || []).map(course => [course.course_id, courseReason(course)])),
  ...Object.fromEntries((result?.course_reasons || []).filter(item => item.personalization_reason?.trim())
   .map(item => [item.course_id, item.personalization_reason])),
 } };
}
