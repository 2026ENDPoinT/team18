from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from services.activity_reasons import (INSTRUCTION, cache_key, evidence_level, fallback_reason,
                                      generate_reasons, reason_input, validate_reasons)
from services.gemini import GeminiError

CASES = json.loads((Path(__file__).parents[1] / 'fixtures/activity_reason_cases.json').read_text())
PROFILE, ITEM = CASES[0]['profile'], CASES[0]['item']


def test_single_batch_keeps_metadata_only_activities_and_allowlisted_inputs(monkeypatch):
    data = reason_input(CASES[1]['profile'], [CASES[1]['item'], {**ITEM, 'private_secret': 'DO NOT SEND'}])
    result = {'reasons': [deepcopy(CASES[1]['response']['reasons'][0]), deepcopy(CASES[0]['response']['reasons'][0])]}
    result['reasons'][1]['sentences'].pop(1)  # This profile has no Python experience.
    provider = Mock(return_value=result)
    monkeypatch.setattr('services.activity_reasons._generate', provider)
    assert len(generate_reasons(data)['reasons']) == 2
    provider.assert_called_once()
    assert provider.call_args.kwargs == {'max_attempts': 1}
    assert len(provider.call_args.args[2]['activities']) == 2
    assert 'DO NOT SEND' not in str(data)
    assert 'LEVEL 2' in INSTRUCTION and '상세 설명 부족만으로' in INSTRUCTION


@pytest.mark.parametrize('case', CASES, ids=lambda c: c['case'])
def test_requested_cases_a_to_e_call_provider(case, monkeypatch):
    data = reason_input(case['profile'], [case['item']])
    provider = Mock(return_value=case['response'])
    monkeypatch.setattr('services.activity_reasons._generate', provider)
    assert generate_reasons(data) == case['response']
    provider.assert_called_once()
    level = 'metadata_inference' if case['case'] in ('B', 'D', 'E') else 'verified_detail'
    assert data['activities'][0]['evidence_level'] == level
    sentences = case['response']['reasons'][0]['sentences']
    assert 100 <= len(' '.join(s['text'] for s in sentences)) <= 200
    assert any(s['experience_ids'] for s in sentences) == (case['case'] in ('A', 'B', 'C'))


@pytest.mark.parametrize('body', ['', ITEM['title'], '누구나 도전할 수 있는 멋진 기회입니다.',
                                  '접수 기간과 참가 대상은 대학생입니다.', '공공데이터를 분석합니다.',
                                  '공공데이터 분석 결과물을 제출하지 않습니다.',
                                  '데이터 분석 과제와 결과물은 추후 공개합니다.'])
def test_missing_outcomes_or_negative_details_do_not_block_metadata_inference(body, monkeypatch):
    case = deepcopy(CASES[4])
    case['item']['description_text'] = body
    provider = Mock(return_value=case['response'])
    monkeypatch.setattr('services.activity_reasons._generate', provider)
    assert generate_reasons(reason_input(case['profile'], [case['item']])) == case['response']
    provider.assert_called_once()


@pytest.mark.parametrize('item', [
    {'id': 'unknown'}, {'id': 'unknown', 'title': '2026년 제1회 공모전', 'category': '기타'},
    {'id': 'unknown', 'host': '한국데이터기관', 'target': '대학생', 'description_text': '참가자를 모집합니다.'},
])
def test_insufficient_information_never_calls_provider(item, monkeypatch):
    provider = Mock()
    monkeypatch.setattr('services.activity_reasons._generate', provider)
    data = reason_input(PROFILE, [item])
    assert evidence_level(data['activities'][0]) == 'insufficient_information'
    assert generate_reasons(data) == {'reasons': []}
    provider.assert_not_called()
    assert '파악하기 어려워' in fallback_reason(item, profile=PROFILE)


@pytest.mark.parametrize('change', ['foreign_id', 'foreign_quote', 'unknown_experience', 'invented_history',
                                   'invented_technology_fact', 'invented_deliverable', 'changed_metadata',
                                   'extra_sentence', 'unlabelled_inference', 'empty', 'no_modality',
                                   'metadata_requirement', 'eligibility', 'prize', 'deadline'])
def test_rejects_invalid_format_or_fabricated_facts(change):
    case = deepcopy(CASES[1])
    result = case['response']
    reason = result['reasons'][0]
    sentence = reason['sentences'][1]
    if change == 'foreign_id': reason['activity_id'] = 'dacon:foreign'
    if change == 'foreign_quote': sentence['evidence'][0]['quote'] = 'TensorFlow로 모델을 구현합니다.'
    if change == 'unknown_experience': sentence['experience_ids'] = ['unknown']
    if change == 'invented_history': sentence['text'] = '기존 TensorFlow 모델 학습 경험을 활용해 새로운 서비스 아이디어를 구체화하는 연습으로 확장할 수 있습니다.'
    if change == 'invented_technology_fact': sentence.update(basis='verified_fact', perspective='expected', experience_ids=[], text='TensorFlow로 모델을 학습하는 소프트웨어 개발 과정에서 새로운 서비스 아이디어를 구체화하는 연습으로 확장할 수 있습니다.')
    if change == 'invented_deliverable': sentence['text'] = '기존 REST API 구현 경험을 활용해 API 설명서와 분석 보고서를 제출하며 새로운 서비스 구조를 설계하는 연습으로 확장할 수 있습니다.'
    if change == 'changed_metadata': reason['host'] = 'invented'
    if change == 'extra_sentence': sentence['text'] += ' 상금도 받습니다.'
    if change == 'unlabelled_inference': sentence.pop('basis')
    if change == 'empty': reason['sentences'] = []
    if change == 'no_modality': sentence['text'] = '기존 REST API 구현 경험을 활용해 서비스 아이디어를 구체화하고 다른 기능과 연결되는 백엔드 구조를 설계합니다.'
    if change == 'metadata_requirement': sentence['text'] = '기존 REST API 구현 경험을 활용해 서비스 아이디어를 구체화하고 필수인 백엔드 구조 설계 과제에 참여할 수 있습니다.'
    if change == 'eligibility': sentence['text'] = '기존 REST API 구현 경험이 있으면 참가 자격을 충족하므로 서비스 아이디어를 구체화하는 연습을 할 수 있습니다.'
    if change == 'prize': sentence['text'] = '기존 REST API 구현 경험을 바탕으로 높은 수상 가능성을 기대하며 서비스 아이디어를 구체화하는 연습을 할 수 있습니다.'
    if change == 'deadline': sentence['text'] = '기존 REST API 구현 경험을 바탕으로 마감 전에 서비스 아이디어를 구체화하고 다른 기능과 연결되는 구조를 연습할 수 있습니다.'
    with pytest.raises(GeminiError):
        validate_reasons(reason_input(case['profile'], [case['item']]), result)


def test_inferred_technology_is_allowed_as_optional_future_direction():
    case = deepcopy(CASES[3])
    case['response']['reasons'][0]['sentences'][1]['text'] = 'Python을 활용해 인공지능 기술을 실제 문제에 적용하는 아이디어를 구상하고, 작은 실험으로 구체화하는 경험을 시도해 볼 수 있습니다.'
    assert validate_reasons(reason_input(case['profile'], [case['item']]), case['response']) == case['response']


def test_two_sentence_user_example_can_use_confirmed_python_with_metadata_only():
    case = deepcopy(CASES[4])
    case['profile'] = deepcopy(PROFILE)
    sentence = case['response']['reasons'][0]['sentences'][1]
    sentence.update(perspective='experience', experience_ids=['p0'], text='기존 Python 데이터 처리 경험을 바탕으로 환경 데이터를 분석하는 아이디어를 구상하고, 분석 결과를 설명하는 경험으로 확장해 볼 수 있습니다.')
    assert validate_reasons(reason_input(case['profile'], [case['item']]), case['response']) == case['response']
    for status in ('unknown', 'no_experience', 'unconfirmed'):
        case['profile']['project_experiences'][0]['user_status'] = status
        with pytest.raises(GeminiError):
            validate_reasons(reason_input(case['profile'], [case['item']]), case['response'])


@pytest.mark.parametrize('text', [
    '기존 Python 분석 경험을 활용해 인공지능 아이디어를 실제 문제에 적용하고 구체적인 기획으로 발전시켜 볼 수 있습니다.',
    '사용해 온 Python으로 인공지능 아이디어를 실제 문제에 적용하고 구체적인 기획으로 발전시켜 볼 수 있습니다.',
])
def test_no_unverified_personal_history_even_with_modal_ending(text):
    case = deepcopy(CASES[3])
    case['response']['reasons'][0]['sentences'][1]['text'] = text
    with pytest.raises(GeminiError):
        validate_reasons(reason_input(case['profile'], [case['item']]), case['response'])


def test_posting_cannot_license_historical_user_claim():
    case = deepcopy(CASES[0])
    case['item']['description_text'] += ' 분석 보고서를 작성합니다.'
    sentence = case['response']['reasons'][0]['sentences'][1]
    sentence['evidence'][0]['quote'] = case['item']['description_text']
    sentence['text'] = '기존 분석 보고서 작성 경험을 환경 데이터 분석에 활용해 볼 수 있습니다.'
    with pytest.raises(GeminiError):
        validate_reasons(reason_input(case['profile'], [case['item']]), case['response'])


def test_cropped_quote_cannot_reverse_negated_source():
    case = deepcopy(CASES[0])
    case['item']['description_text'] += ' 분석 보고서를 제출하지 않습니다.'
    case['response']['reasons'][0]['sentences'][2].update(
        text='분석 보고서를 제출하며 분석한 결과를 전달하는 경험을 쌓을 수 있습니다.',
        evidence=[{'evidence_id': 'description_text', 'quote': '분석 보고서를 제출'}])
    with pytest.raises(GeminiError):
        validate_reasons(reason_input(case['profile'], [case['item']]), case['response'])


def test_exact_multiline_quotes_remain_valid():
    case = deepcopy(CASES[0])
    body = case['item']['description_text'].replace(', ', ',\n')
    case['item']['description_text'] = body
    for sentence in case['response']['reasons'][0]['sentences']:
        sentence['evidence'][0]['quote'] = body
    assert validate_reasons(reason_input(case['profile'], [case['item']]), case['response']) == case['response']


def test_cache_basis_tracks_context_content_and_not_collection_time():
    key = cache_key('plan', reason_input(PROFILE, [ITEM]))
    assert key == cache_key('plan', reason_input(PROFILE, [{**ITEM, 'last_success_at': 'later', 'status': 'open', 'score': 12}]))
    for profile, item in [({**PROFILE, 'career_goal': '환경 데이터 분석'}, ITEM),
                          ({**PROFILE, 'project_experiences': []}, ITEM),
                          ({**PROFILE, 'skill_comparison': [{'skill_name': 'SQL', 'student_status': 'no_experience'}]}, ITEM),
                          (PROFILE, {**ITEM, 'description_text': '다른 분석 과제'}),
                          (PROFILE, {**ITEM, 'host': '다른 주최'})]:
        assert key != cache_key('plan', reason_input(profile, [item]))
    assert key != cache_key('other-plan', reason_input(PROFILE, [ITEM]))


def test_input_only_sends_confirmed_personal_effective_fields():
    verified = {**PROFILE['project_experiences'][0], 'private_document': 'secret'}
    profile = {**PROFILE, 'project_experiences': [verified,
        {**verified, 'user_status': 'unknown'}, {**verified, 'user_status': 'unconfirmed'},
        {**verified, 'contribution_scope': 'team'}, {**verified, 'user_status': 'no_experience'}],
        'skill_comparison': [{'skill_name': 'SQL', 'student_status': 'not_verified', 'reason': 'secret'},
                             {'skill_name': 'Python', 'student_status': 'confirmed_experience', 'reason': 'secret'}]}
    data = reason_input(profile, [ITEM])
    assert len(data['project_experiences']) == len(data['skill_comparison']) == 1
    assert 'secret' not in str(data)


def test_fallback_uses_actual_subject_and_goal_without_claiming_history():
    text = fallback_reason(CASES[1]['item'], 'generation_failed', CASES[1]['profile'])
    assert '소프트웨어' in text and '백엔드 개발자' in text and '볼 수 있습니다' in text
    assert 'REST' not in text
    assert '데이터 분석가' in fallback_reason(ITEM, 'not_generated', PROFILE)


def test_mixed_information_levels_keep_distinct_status_and_source(monkeypatch):
    import sqlite3
    from contextlib import closing
    from services.activity_reasons import attach_reasons
    case = CASES[1]
    provider = Mock(return_value=case['response'])
    monkeypatch.setattr('services.activity_reasons._generate', provider)
    unknown = {'id': 'unknown', 'title': '공모전', 'category': '기타'}
    with closing(sqlite3.connect(':memory:', isolation_level=None)) as db:
        db.row_factory = sqlite3.Row
        db.execute('''CREATE TABLE ai_requests(request_id TEXT PRIMARY KEY, owner_id TEXT, operation TEXT,
            basis_hash TEXT, units INTEGER, status TEXT, created_at TEXT, lease_until TEXT, result_json TEXT)''')
        ctx = db, None, {'owner_id': 'test'}
        args = ctx, 'plan', case['profile'], {'activities': [case['item'], unknown]}
        result = attach_reasons(*args, generate=True)
        first, second = result['activities']
        assert (first['reason_source'], first['reason_evidence_level']) == ('gemini', 'metadata_inference')
        assert (second['reason_source'], second['reason_status']) == ('fallback', 'insufficient_information')
        assert len(provider.call_args.args[2]['activities']) == 1
        assert attach_reasons(*args)['activities'] == result['activities']
        assert attach_reasons(*args, generate=True)['activities'] == result['activities']
        provider.assert_called_once()


def test_prior_submission_experience_does_not_require_a_posting_submission():
    case = deepcopy(CASES[1])
    case['profile']['project_experiences'][0]['activity'] = 'REST API를 구현하고 API 설명서를 제출했습니다.'
    case['response']['reasons'][0]['sentences'][1]['text'] = '기존 REST API 구현과 설명서 제출 경험을 활용해 서비스 아이디어를 구체화하고, 백엔드 구조를 설계하는 연습으로 확장할 수 있습니다.'
    validate_reasons(reason_input(case['profile'], [case['item']]), case['response'])


def test_mentioned_tool_is_not_automatically_mandatory():
    case = deepcopy(CASES[0])
    case['item']['description_text'] = 'Python을 활용한 데이터 분석도 가능합니다.'
    for sentence in case['response']['reasons'][0]['sentences']:
        sentence['evidence'] = [{'evidence_id': 'description_text', 'quote': case['item']['description_text']}]
    case['response']['reasons'][0]['sentences'] = [case['response']['reasons'][0]['sentences'][0], {
        'perspective': 'expected', 'basis': 'inference', 'experience_ids': [],
        'text': '이 대회의 필수 기술인 Python으로 데이터 분석을 진행하며 새로운 주제를 탐색하는 경험을 쌓을 수 있습니다.',
        'evidence': [{'evidence_id': 'description_text', 'quote': case['item']['description_text']}]}]
    with pytest.raises(GeminiError):
        validate_reasons(reason_input(case['profile'], [case['item']]), case['response'])
