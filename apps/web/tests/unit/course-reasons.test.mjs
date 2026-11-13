import test from 'node:test';
import assert from 'node:assert/strict';
import useCourseReasons from '../../src/features/roadmap/useCourseReasons.js';

test('saved prose renders immediately with catalog fallback for missing items', () => {
 const result = { recommended_courses: [{ course_id: 'db', reason: '기존 근거' }, { course_id: 'c' }],
  course_reasons: [{ course_id: 'db', personalization_reason: '개인화 이유' }] };
 assert.deepEqual(useCourseReasons(result), { phase: 'ready', reasons: { db: '개인화 이유', c: '추천 근거 확인 필요' } });
 assert.deepEqual(useCourseReasons({ ...result, details_restricted: true }), { phase: 'ready', reasons: {} });
 assert.deepEqual(useCourseReasons(null), { phase: 'ready', reasons: {} });
});
