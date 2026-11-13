from copy import deepcopy
import json
from pathlib import Path
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
                          ({**PROFILE, 'skill_comparison': [{'skill_name': 'SQL', 'student_status': 'no_experience'}]}, ITEM),
                          (PROFILE, {**ITEM, 'description_text': BODY + ' 분석 보고서를 제출합니다.'}),
                          (PROFILE, {**ITEM, 'host': '다른 주최'})]:
        assert key != cache_key('plan', reason_input(profile, [item]))
    assert key != cache_key('other-plan', reason_input(PROFILE, [ITEM]))


def test_fallback_does_not_repackage_ranking_keywords_as_personalization():
    ranked = recommend(PROFILE, [ITEM], [{'status': 'success'}], datetime(2026, 11, 14, tzinfo=KST))['activities'][0]
    reason = fallback_reason(ranked)
    assert ITEM['title'] not in reason
    assert '맞춰' not in reason and '콘테스트코리아:' not in reason
    assert '개인화 추천 이유를 제공하지 않습니다' in reason
    corrupted = {**ranked, 'evidence': [{'posting_field': 'description_text', 'posting_quote': '거짓 본문', 'matched_term': '본문'}]}
    assert '거짓' not in fallback_reason(corrupted)


def test_missing_details_are_excluded_without_inventing_facts():
    data = reason_input(PROFILE, [{k: v for k, v in ITEM.items() if k != 'description_text'}])
    assert validate_reasons(data, {'reasons': []}) == {'reasons': []}
    with pytest.raises(GeminiError): validate_reasons(data, output(reason_input(PROFILE, [ITEM])))


CASES = json.loads((Path(__file__).parents[1] / 'fixtures/activity_reason_cases.json').read_text())


@pytest.mark.parametrize('case', CASES, ids=lambda c: c['case'])
def test_requested_cases_a_to_e(case, monkeypatch):
    data = reason_input(case['profile'], [case['item']])
    provider = Mock(return_value=case['response'])
    monkeypatch.setattr('services.activity_reasons._generate', provider)
    generated = generate_reasons(data)
    assert generated == case['response']
    if case['case'] == 'E':
        provider.assert_not_called()
    else:
        provider.assert_called_once()
        sentences = generated['reasons'][0]['sentences']
        assert 100 <= len(' '.join(s['text'] for s in sentences)) <= 200
        assert len(sentences) == (2 if case['case'] == 'D' else 3)
        assert any(s['experience_ids'] for s in sentences) == (case['case'] != 'D')


@pytest.mark.parametrize('body', ['', ITEM['title'], '누구나 도전할 수 있는 멋진 기회입니다.',
                                  '접수 기간과 참가 대상은 대학생입니다.', '공공데이터를 분석합니다.',
                                  '소프트웨어 개발 해커톤 참가자를 모집합니다.'])
def test_empty_vague_or_task_only_details_do_not_call_gemini(body, monkeypatch):
    provider = Mock()
    monkeypatch.setattr('services.activity_reasons._generate', provider)
    assert generate_reasons(reason_input(PROFILE, [{**ITEM, 'description_text': body}])) == {'reasons': []}
    provider.assert_not_called()


def test_input_only_sends_confirmed_personal_effective_fields():
    verified = {**PROFILE['project_experiences'][0], 'private_document': 'secret'}
    profile = {**PROFILE, 'project_experiences': [verified,
        {**verified, 'user_status': 'unknown'}, {**verified, 'user_status': 'unconfirmed'},
        {**verified, 'contribution_scope': 'team'}, {**verified, 'user_status': 'no_experience'}],
        'skill_comparison': [{'skill_name': 'SQL', 'student_status': 'not_verified', 'reason': 'secret'},
                             {'skill_name': 'Python', 'student_status': 'confirmed_experience', 'reason': 'secret'}]}
    data = reason_input(profile, [ITEM])
    assert len(data['project_experiences']) == 1
    assert len(data['skill_comparison']) == 1
    assert 'secret' not in str(data)


@pytest.mark.parametrize('change', ['personal_claim_without_ids', 'posting_as_experience', 'unrelated_experience',
                                   'title_technology', 'wrong_career_method', 'experience_as_requirement'])
def test_rejects_evidence_scope_confusion(change):
    case = deepcopy(CASES[0])
    profile, item, result = case['profile'], case['item'], case['response']
    sentences = result['reasons'][0]['sentences']
    if change == 'personal_claim_without_ids':
        sentences.pop(1)
        sentences[1]['text'] = '기존 Python 분석 경험을 활용해 분석 결과를 설명하는 제출물을 작성할 수 있습니다.'
    if change == 'posting_as_experience':
        sentences[1]['text'] = '기존 분석 보고서 작성 경험을 환경 데이터 분석에 활용할 수 있습니다.'
        item['description_text'] += ' 분석 보고서 작성도 포함합니다.'
        sentences[1]['evidence'][0]['quote'] = item['description_text']
    if change == 'unrelated_experience':
        profile['project_experiences'][0].update(skill_name='React', activity='React로 화면을 개발했습니다.')
        sentences[1]['text'] = '기존 React 화면 개발 경험을 환경 데이터 분석에 적용해 볼 수 있습니다.'
    if change == 'title_technology':
        item['title'] = 'TensorFlow 데이터 분석 대회'
        sentences[2]['text'] = 'TensorFlow로 분석 결과를 설명하는 제출물을 작성하며 결과를 전달하는 경험을 쌓을 수 있습니다.'
        sentences[2]['evidence'].append({'evidence_id': 'title', 'quote': item['title']})
    if change == 'wrong_career_method':
        item['description_text'] = '기후 환경 보호 영상을 제작하고 완성한 영상을 제출합니다.'
        for sentence in sentences: sentence['evidence'][0]['quote'] = item['description_text']
    if change == 'experience_as_requirement':
        sentences[1]['text'] = '기존 Python 데이터 처리 경험을 활용해 Python 분석 보고서를 제출할 수 있습니다.'
    with pytest.raises(GeminiError):
        validate_reasons(reason_input(profile, [item]), result)


def test_provider_can_abstain_without_breaking_schema():
    data = reason_input(PROFILE, [ITEM])
    abstained = {'reasons': [{'activity_id': 'contestkorea:one', 'sentences': []}]}
    assert validate_reasons(data, abstained) == abstained
    invalid = output(data)
    invalid['reasons'][0]['sentences'] = invalid['reasons'][0]['sentences'][:1]
    with pytest.raises(GeminiError): validate_reasons(data, invalid)


@pytest.mark.parametrize('body', ['공공데이터 분석 결과물을 제출하지 않습니다.',
                                  '데이터 분석 과제와 결과물은 추후 공개합니다.'])
def test_negative_or_undecided_details_are_not_tasks(body, monkeypatch):
    provider = Mock()
    monkeypatch.setattr('services.activity_reasons._generate', provider)
    assert generate_reasons(reason_input(PROFILE, [{**ITEM, 'description_text': body}])) == {'reasons': []}
    provider.assert_not_called()


def test_cropped_quote_cannot_reverse_negated_source():
    body = BODY + ' 분석 보고서를 제출하지 않습니다.'
    data = reason_input(PROFILE, [{**ITEM, 'description_text': body}])
    result = output(data)
    result['reasons'][0]['sentences'][1].update(text='분석 보고서를 제출하며 분석한 결과를 전달하는 경험을 쌓을 수 있습니다.',
        evidence=[{'evidence_id': 'description_text', 'quote': '분석 보고서를 제출'}])
    with pytest.raises(GeminiError): validate_reasons(data, result)


def test_exact_multiline_quotes_remain_valid():
    case = deepcopy(CASES[0])
    body = case['item']['description_text'].replace(', ', ',\n')
    case['item']['description_text'] = body
    for sentence in case['response']['reasons'][0]['sentences']:
        sentence['evidence'][0]['quote'] = body
    assert validate_reasons(reason_input(case['profile'], [case['item']]), case['response']) == case['response']
