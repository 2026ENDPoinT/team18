"""DB-only display behavior, including historical and invalid identities."""
from copy import deepcopy
import sqlite3
from unittest.mock import patch

import pytest

from services.course_reasons import (
    MISSING_REASON, VERSION, attach_course_reasons, course_reasons_payload,
    experience_input, present_course_reasons,
)

CATALOG = 'seoultech-cse-2026-major-v1'
KO = 'stcse-2026-ac66832f2c533c700dde1354'
EN = 'stcse-2026-56e5e2a1aedbfd4d2e87404c'
TEXT = '본 강좌에서는 데이터베이스의 구성과 운영 방법을 학습한다. '


@pytest.fixture
def db():
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    db.execute('CREATE TABLE catalog_courses(catalog_id text, course_id text, recommendation_reason text)')
    db.executemany('INSERT INTO catalog_courses VALUES(?,?,?)', [
        (CATALOG, KO, TEXT), (CATALOG, EN, '영문 행의 개별 설명'),
        ('other', KO, '다른 목록의 설명'), (CATALOG, 'blank', ' \n'),
    ])
    yield db
    db.close()


def test_overlay_exact_text_preserves_ranking_and_evidence_without_ai(db):
    courses = [{'course_id': KO, 'reason': 'old AI', 'personalization_reason': 'old AI',
                'course_evidence': '원문', 'keyword_evidence': [{'evidence_text': '원문'}],
                'related_skills': ['SQL'], 'recommendation_type': 'direct'},
               {'course_id': EN, 'course_name': 'Database'}]
    original = deepcopy(courses)
    with patch('google.genai.Client', side_effect=AssertionError('AI forbidden')) as ai:
        output = attach_course_reasons(db, CATALOG, courses)
        ai.assert_not_called()
    assert courses == original
    assert [c['course_id'] for c in output] == [KO, EN]
    assert all(c['reason'] == c['personalization_reason'] == c['recommendation_reason'] == TEXT for c in output)
    for c, before in zip(output, original):
        assert all(c[k] == v for k, v in before.items() if k not in ('reason', 'personalization_reason'))
    assert output[0]['reason_provider'] == 'database'
    assert output[0]['reason_version'] == VERSION


@pytest.mark.parametrize('catalog,cid', [(CATALOG, 'invalid'), (CATALOG, 'blank'), ('unknown', KO), (None, KO), (CATALOG, "' OR 1=1 --")])
def test_unknown_or_empty_uses_safe_notice_never_saved_ai_or_names(db, catalog, cid):
    courses = [{'course_id': cid, 'course_name': '데이터베이스', 'reason': 'old claim',
                'personalization_reason': 'old claim', 'member_course_ids': [KO]}]
    result = attach_course_reasons(db, catalog, courses)
    assert result[0]['recommendation_reason'] is None
    assert result[0]['personalization_reason'] == MISSING_REASON
    assert course_reasons_payload(result)['source'] == 'safe_fallback'


def test_catalog_scope_missing_canonical_and_metadata(db):
    assert attach_course_reasons(db, 'other', [{'course_id': KO}])[0]['reason'] == '다른 목록의 설명'
    mixed = attach_course_reasons(db, CATALOG, [{'course_id': KO}, {'course_id': 'unknown'}])
    assert course_reasons_payload(mixed)['source'] == 'catalog_fixed_with_fallback'
    db.execute('DELETE FROM catalog_courses WHERE course_id=?', (KO,))
    assert attach_course_reasons(db, CATALOG, [{'course_id': EN}])[0]['reason'] == MISSING_REASON
    assert course_reasons_payload([])['reasons'] == []


def test_historical_payload_is_projected_without_mutation_or_cached_prose(db):
    saved = {'recommended_courses': [{'course_id': KO, 'reason': 'AI'}],
             'course_reasons': [{'course_id': KO, 'personalization_reason': 'AI'}],
             'course_reasons_source': 'gemini', 'course_reasons_error': 'timeout', 'roadmap': []}
    before = deepcopy(saved)
    output = present_course_reasons(db, CATALOG, saved)
    assert saved == before
    assert output['course_reasons'][0] == {'course_id': KO, 'personalization_reason': TEXT, 'evidence_ids': []}
    assert output['course_reasons_source'] == 'catalog_fixed'
    assert output['course_reasons_provider'] == 'database'
    assert output['course_reasons_error'] is None


def test_shared_experience_input_preserves_other_ai_features_and_privacy():
    original = {'evidence_verified': True, 'skill_name': 'Python', 'activity': '전처리',
                'contribution_scope': 'personal', 'evidence_text': 'PRIVATE QUOTE', 'document_id': 'PRIVATE ID'}
    corrected = {**original, 'user_answer': {'status': 'corrected', 'correction': {
        'skill_name': 'Excel', 'activity': '집계표 작성', 'contribution_scope': 'personal'}}}
    denied = {**original, 'user_answer': {'status': 'no_experience'}}
    result = experience_input([original, corrected, denied, {**original, 'evidence_verified': False}])
    assert result[1]['skill_name'] == 'Excel'
    assert result[1]['activity'] == '집계표 작성'
    assert result[2] == {'skill_name': 'Python', 'user_status': 'no_experience'}
    assert len(result) == 3
    assert 'PRIVATE' not in str(result)
