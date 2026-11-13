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


test('DB text wins over every cached or saved AI field verbatim', () => {
 const text = '본 강좌에서는 데이터베이스의 구성과 운영 방법을 학습한다. ';
 const course = { course_id: 'db', recommendation_reason: text, personalization_reason: 'AI', reason: '추출 문구' };
 const result = { recommended_courses: [course], course_reasons: [{ course_id: 'db', personalization_reason: 'old AI' }] };
 assert.equal(useCourseReasons(result).reasons.db, text);
 assert.equal(useCourseReasons({ recommended_courses: [course] }).reasons.db, text);
});


test('a missing DB explanation cannot revive old AI text', () => {
 const course = { course_id: 'db', recommendation_reason: null, personalization_reason: 'old AI', reason: 'old excerpt' };
 assert.equal(useCourseReasons({ recommended_courses: [course], course_reasons: [{ course_id: 'db', personalization_reason: 'old AI' }] }).reasons.db, '추천 근거 확인 필요');
});
