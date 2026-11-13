import json
from copy import deepcopy
from unittest.mock import Mock, patch

import pytest

from services.course_reasons import CourseReasons, generate_course_reasons, reason_input, validate_course_reasons
from services.gemini import GeminiError


def fixture():
    basis = {'profile': {'career_goal': '행사 신청 데이터를 분석하고 싶어요.', 'target_role': '데이터 분석가',
                         'email': 'never-send@example.com', 'gpa': 4.0},
             'review_status': 'confirmed', 'project_documents': [{'text': 'PRIVATE PROJECT'}],
             'courses': [{'course_id': 'db', 'description_text': 'SQL 조회와 집계를 학습한다. Python 사전지식이 필요하다.',
                          'keywords': [{'keyword': 'SQL', 'keyword_role': 'learning', 'evidence_text': 'SQL 조회와 집계를 학습한다.'},
                                       {'keyword': 'Python', 'keyword_role': 'prerequisite', 'evidence_text': 'Python 사전지식이 필요하다.'},
                                       {'keyword': 'Fake', 'keyword_role': 'learning', 'evidence_text': '다른 과목의 문장'}]},
                         {'course_id': 'unknown', 'description_text': None},
                         {'course_id': 'not-recommended', 'description_text': 'NOT SENT'}]}
    courses = [{'course_id': 'db', 'course_name': '데이터베이스', 'recommendation_type': 'direct'},
               {'course_id': 'unknown', 'course_name': '기초 수학', 'recommendation_type': 'exploration'}]
    return basis, courses


def output():
    return {'reasons': [
        {'course_id': 'db', 'personalization_reason': '행사 신청 데이터를 분석하려는 목표에 SQL 조회·집계를 연결할 수 있어요. 신청 흐름을 정리하는 데 활용할 학습 후보입니다.', 'evidence_ids': ['e0']},
        {'course_id': 'unknown', 'personalization_reason': '과목명만으로 살펴보는 후보여서 실제 학습 내용과 분석 목표의 연결을 확인해야 해요.', 'evidence_ids': []},
    ]}


def test_minimized_input_preserves_only_own_learning_evidence():
    basis, courses = fixture()
    data = reason_input(basis, courses)
    assert data['career_goal'] == basis['profile']['career_goal']
    assert data['target_role'] == '데이터 분석가'
    assert data['courses'][0]['evidence'] == [{'id': 'e0', 'kind': 'learning_evidence', 'keyword': 'SQL', 'text': 'SQL 조회와 집계를 학습한다.'}]
    assert data['courses'][1]['evidence'] == []
    text = json.dumps(data)
    assert all(value not in text for value in ('PRIVATE PROJECT', 'never-send', 'gpa', 'NOT SENT', 'Python', 'Fake'))


def test_bilingual_sources_are_validated_against_their_own_description():
    basis, courses = fixture()
    courses[0]['member_course_ids'] = ['db', 'db-en']
    basis['courses'][0]['_keyword_sources'] = [
        {'course_id': 'db-en', 'description_text': 'Learn SQL queries.', 'keywords': [
            {'keyword': 'SQL', 'keyword_role': 'learning', 'evidence_text': 'Learn SQL queries.'}]},
        {'course_id': 'foreign', 'description_text': 'Foreign text', 'keywords': []}]
    data = reason_input(basis, courses)
    assert data['courses'][0]['evidence'][0]['text'] == 'Learn SQL queries.'
    assert len(data['courses'][0]['evidence']) == 1
    basis['courses'][0]['_keyword_sources'][0]['description_text'] = 'Unrelated description'
    assert reason_input(basis, courses)['courses'][0]['evidence'] == []


def test_real_sdk_transport_uses_configured_model_and_returns_generated_reason():
    sdk = Mock()
    sdk.models.generate_content.return_value.text = json.dumps(output())
    with patch.dict('os.environ', {'GEMINI_API_KEY': 'test-key', 'GEMINI_MODEL': 'operator-selected-model'}), \
         patch('google.genai.Client', return_value=sdk):
        result = generate_course_reasons(reason_input(*fixture()))
    assert result == output()
    call = sdk.models.generate_content.call_args.kwargs
    assert call['model'] == 'operator-selected-model'
    assert json.loads(call['contents']) == reason_input(*fixture())
    assert call['config'].response_mime_type == 'application/json'
    sdk.close.assert_called_once()


@pytest.mark.parametrize('change', ['missing', 'duplicate', 'foreign', 'foreign_evidence', 'missing_evidence', 'name_only_claim', 'prohibited'])
def test_invalid_provider_output_is_not_cached_or_shown(change):
    raw = deepcopy(output())
    if change == 'missing': raw['reasons'].pop()
    elif change == 'duplicate': raw['reasons'].append(raw['reasons'][0])
    elif change == 'foreign': raw['reasons'][0]['course_id'] = 'not-recommended'
    elif change == 'foreign_evidence': raw['reasons'][0]['evidence_ids'] = ['foreign']
    elif change == 'missing_evidence': raw['reasons'][0]['evidence_ids'] = []
    elif change == 'name_only_claim': raw['reasons'][1]['personalization_reason'] = '이 과목에서는 SQL 프로젝트를 진행해요.'
    elif change == 'prohibited': raw['reasons'][0]['personalization_reason'] = '취업을 위해 반드시 수강하세요.'
    with patch('services.course_reasons._generate', return_value=CourseReasons.model_validate(raw)):
        with pytest.raises(GeminiError): generate_course_reasons(reason_input(*fixture()))


def test_empty_candidates_and_provider_failure_never_fall_back_to_template():
    with patch('services.course_reasons._generate') as model:
        assert generate_course_reasons({'courses': []}) == {'reasons': []}
        model.assert_not_called()
    with patch('services.course_reasons._generate', side_effect=GeminiError('gemini_timeout', 'timeout')) as model:
        with pytest.raises(GeminiError): generate_course_reasons(reason_input(*fixture()))
        assert model.call_count == 1


def test_cached_reasons_are_validated_against_the_same_evidence():
    data, saved = reason_input(*fixture()), output()
    assert validate_course_reasons(data, saved) == saved
    saved['reasons'][0]['evidence_ids'] = ['foreign']
    with pytest.raises(GeminiError): validate_course_reasons(data, saved)
