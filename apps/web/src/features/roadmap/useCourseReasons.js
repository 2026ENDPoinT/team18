'use client';
import { courseReason } from './resultPresentation.mjs';

// The API overlays current DB text on saved results. Rendering never requests AI.
// Explicit catalog text takes precedence over any legacy bundled explanation.
export default function useCourseReasons(result) {
 if (result?.details_restricted) return { phase: 'ready', reasons: {} };
 return { phase: 'ready', reasons: {
  ...Object.fromEntries((result?.recommended_courses || []).map(course => [course.course_id, courseReason(course)])),
  ...Object.fromEntries((result?.course_reasons || []).filter(item => item.personalization_reason?.trim())
   .map(item => [item.course_id, item.personalization_reason])),
  ...Object.fromEntries((result?.recommended_courses || []).filter(course => Object.hasOwn(course, 'recommendation_reason'))
   .map(course => [course.course_id, courseReason(course)])),
 } };
}
