from copy import deepcopy
from unittest.mock import Mock

import pytest
from services.activity_reasons import (INSTRUCTION, cache_key, fallback_reason, generate_reasons,
                                      reason_input, validate_reasons)
from services.gemini import GeminiError
from services.activity_recommendations import recommend, KST
from datetime import datetime

BODY = '기후 공공데이터를 분석하고 시각화 결과를 제출합니다.'
ITEM = {'id': 'one', 'source': 'contestkorea', 'title': '기후 공공데이터 AI 활용대회',
        'description_text': BODY, 'host': '공공기관', 'target': '대학생', 'period': '상시 접수'}
PROFILE = {'career_goal': '스포츠 데이터 분석', 'target_role': '데이터 분석가',
           'project_experiences': [{'skill_name': 'Python', 'activity': 'Python으로 전처리',
                                    'contribution_scope': 'personal', 'user_status': 'confirmed'}]}


def output(data):
    sentences = [
        {'perspective': 'career', 'text': '스포츠 분야의 활동은 아니지만, 공고에 명시된 기후 공공데이터 분석으로 데이터 분석 방법을 연습할 수 있습니다.',
         'experience_ids': [], 'evidence': [{'evidence_id': 'description_text', 'quote': BODY}]},
        {'perspective': 'expected', 'text': '분석한 내용을 시각화 결과로 정리해 제출하는 경험을 쌓을 수 있는 활동입니다.',
         'experience_ids': [], 'evidence': [{'evidence_id': 'description_text', 'quote': BODY}]},
    ]
    return {'reasons': [{'activity_id': a['activity_id'], 'sentences': deepcopy(sentences)}
                        for a in data['activities'] if any(e['kind'] == 'detail' for e in a['evidence'])]}


def test_single_batch_and_only_existing_allowlisted_facts(monkeypatch):
    data = reason_input(PROFILE, [ITEM, {**ITEM, 'id': 'two', 'private_secret': 'DO NOT SEND'}])
    generate = Mock(return_value=output(data))
    monkeypatch.setattr('services.activity_reasons._generate', generate)
    assert len(generate_reasons(data)['reasons']) == 2
    generate.assert_called_once()
    assert generate.call_args.kwargs == {'max_attempts': 1}
    assert 'DO NOT SEND' not in str(data)
    assert '스포츠' in INSTRUCTION and '일반어' in INSTRUCTION
    assert '스포츠 분야의 활동은 아니지만' in generate_reasons(data)['reasons'][0]['sentences'][0]['text']


@pytest.mark.parametrize('change', ['foreign_id', 'foreign_quote', 'title_only', 'invented_technology',
                                   'invented_deliverable', 'assumed_experience', 'direct_match', 'changed_metadata', 'extra_sentence'])
def test_rejects_unsupported_claims(change):
    data = reason_input(PROFILE, [ITEM])
    result = output(data)
    reason, = result['reasons']
    sentence = reason['sentences'][1]
    if change == 'foreign_id': reason['activity_id'] = 'dacon:foreign'
    if change == 'foreign_quote': sentence['evidence'][0]['quote'] = 'TensorFlow로 모델을 구현합니다.'
    if change == 'title_only': sentence['evidence'] = [{'evidence_id': 'title', 'quote': ITEM['title']}]
    if change == 'invented_technology': sentence['text'] = 'TensorFlow로 시각화 결과를 정리해 제출하는 경험을 쌓을 수 있습니다.'
    if change == 'invented_deliverable': sentence['text'] = '분석 보고서를 정리해 제출하는 경험을 쌓을 수 있는 활동입니다.'
    if change == 'assumed_experience': sentence.update(perspective='experience', experience_ids=['unknown'])
    if change == 'direct_match': sentence['text'] = '스포츠 데이터 분석 목표에 직접 관련된 결과물을 만들어 제출하는 경험을 쌓을 수 있습니다.'
    if change == 'changed_metadata': reason['host'] = 'invented'
    if change == 'extra_sentence': sentence['text'] += ' 상금도 받습니다.'
    with pytest.raises(GeminiError): validate_reasons(data, result)


def test_confirmed_experience_is_not_a_license_to_invent_activity_requirements():
    data = reason_input(PROFILE, [ITEM])
    result = output(data)
    experience = {'perspective': 'experience', 'text': '확인한 Python 전처리 경험을 데이터 분석에 활용해 볼 수 있습니다.',
                  'experience_ids': ['p0'], 'evidence': [{'evidence_id': 'description_text', 'quote': BODY}]}
    result['reasons'][0]['sentences'].insert(1, experience)
    validate_reasons(data, result)
    result['reasons'][0]['sentences'][2]['text'] = 'Python으로 시각화 결과를 제출하는 경험을 쌓을 수 있는 활동입니다.'
    with pytest.raises(GeminiError): validate_reasons(data, result)
    result['reasons'][0]['sentences'][2] = output(data)['reasons'][0]['sentences'][1]
    for status in ('unknown', 'no_experience', 'unconfirmed'):
        denied = reason_input({**PROFILE, 'project_experiences': [{**PROFILE['project_experiences'][0], 'user_status': status}]}, [ITEM])
        with pytest.raises(GeminiError): validate_reasons(denied, result)


def test_cache_basis_tracks_context_content_and_not_collection_time():
    key = cache_key('plan', reason_input(PROFILE, [ITEM]))
    assert key == cache_key('plan', reason_input(PROFILE, [{**ITEM, 'last_success_at': 'later', 'status': 'open', 'score': 12}]))
    for profile, item in [({**PROFILE, 'career_goal': '환경 데이터 분석'}, ITEM),
                          ({**PROFILE, 'project_experiences': []}, ITEM),
                          ({**PROFILE, 'gap_skills': ['SQL']}, ITEM),
                          (PROFILE, {**ITEM, 'description_text': BODY + ' 분석 보고서를 제출합니다.'}),
                          (PROFILE, {**ITEM, 'host': '다른 주최'})]:
        assert key != cache_key('plan', reason_input(profile, [item]))
    assert key != cache_key('other-plan', reason_input(PROFILE, [ITEM]))


def test_fallback_deduplicates_actual_witness_and_does_not_overstate_keyword():
    ranked = recommend(PROFILE, [ITEM], [{'status': 'success'}], datetime(2026, 11, 14, tzinfo=KST))['activities'][0]
    reason = fallback_reason(ranked)
    assert reason.count(ITEM['title']) == 1
    assert '맞춰' not in reason and '콘테스트코리아:' not in reason
    assert '확인해 주세요' in reason
    corrupted = {**ranked, 'evidence': [{'posting_field': 'description_text', 'posting_quote': '거짓 본문', 'matched_term': '본문'}]}
    assert '거짓' not in fallback_reason(corrupted)


def test_missing_details_are_excluded_without_inventing_facts():
    data = reason_input(PROFILE, [{k: v for k, v in ITEM.items() if k != 'description_text'}])
    assert validate_reasons(data, {'reasons': []}) == {'reasons': []}
    with pytest.raises(GeminiError): validate_reasons(data, output(reason_input(PROFILE, [ITEM])))
