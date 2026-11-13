"""Deterministic, server-validated guidance when Gemini returns an invalid roadmap.

This is a conservative fallback, not an AI-generated learning plan. It uses only
the verified job comparison and the student's explicit experience answers.
Unknown experience remains a verification task; course candidates remain
server-ranked, not invented by the fallback.
"""
from services.roadmap_generation import model_input, validate_result


def verified_roadmap_fallback(basis):
    included = model_input(basis)['skills']
    if not included:
        raise ValueError('No verified job skills for an evidence-based fallback')

    items = []
    for index, skill in enumerate(included[:5], 1):
        name = skill['skill_name']
        status = skill['student_status']
        action_type = skill['allowed_action_type']
        sid = f'fallback-step-{index}'
        tid = f'fallback-task-{index}'

        if action_type == 'verify_experience':
            # Merely appearing in a job posting does not establish an
            # individual's ability or lack of experience.
            title = f'{name} 수행 경험 확인'
            purpose = '현재 자료에서 직접 수행 여부가 확인되지 않은 경험을 검토합니다.'
            reason = '채용공고에서 기술 근거가 확인되었지만 본인이 수행했는지는 아직 확인되지 않았습니다.'
            tasks = [{
                'task_id': tid, 'task_type': 'verify_experience',
                'title': f'{name} 사용 기록 검토',
                'action': f'기존 프로젝트와 코드 기록에서 {name}을 직접 사용한 경험이 있는지 확인하고, 수행 주체와 근거 유무를 기록한다.',
                'completion_criteria': '경험 있음, 경험 없음, 판단 보류 중 확인한 상태와 관련 기록을 남김',
                'deliverable': f'{name} 경험 확인 기록',
            }]
        elif action_type == 'learn':
            title = f'{name} 기초 학습과 직접 실습'
            purpose = '사용자가 경험이 없다고 밝힌 기술의 학습 시작점을 검토합니다.'
            reason = '사용자가 직접 수행 경험이 없다고 답해 개인 실습 후보로 제시합니다.'
            tasks = [
                {
                    'task_id': tid + '-practice', 'task_type': 'practice',
                    'title': f'{name} 기초 실습',
                    'action': f'{name}의 기본 사용법을 공식 문서에서 찾아 작은 개인 실습을 수행하고 실행 결과를 기록한다.',
                    'completion_criteria': '사용한 설명 자료, 실습 과정, 실제 실행 결과를 저장함',
                    'deliverable': f'{name} 기초 실습 기록',
                },
                {
                    'task_id': tid + '-validate', 'task_type': 'validate',
                    'title': f'{name} 실습 결과 확인',
                    'action': f'{name} 개인 실습에서 예상한 결과와 실제 결과를 비교하여 확인한 점과 남은 질문을 기록한다.',
                    'completion_criteria': '예상 결과와 관찰 결과, 차이를 정리함',
                    'deliverable': f'{name} 결과 비교 메모',
                },
            ]
        elif action_type == 'deepen':
            title = f'{name} 기존 경험 검토와 확장'
            purpose = '본인이 수행했다고 확인한 경험을 바탕으로 재현성과 적용 범위를 검토합니다.'
            reason = '본인 수행은 확인되었으나 이 사실만으로 기술 숙련도가 보장되지는 않습니다.'
            tasks = [
                {
                    'task_id': tid + '-apply', 'task_type': 'apply',
                    'title': f'{name} 작업 재현',
                    'action': f'본인이 직접 수행한 {name} 관련 작업을 재현하거나 동일한 범위의 작은 예제를 작성한다.',
                    'completion_criteria': '작업 재현 과정과 관찰 가능한 결과를 기록함',
                    'deliverable': f'{name} 재현 결과',
                },
                {
                    'task_id': tid + '-document', 'task_type': 'document',
                    'title': f'{name} 본인 기여 기록',
                    'action': f'{name} 관련 본인 역할과 직접 수행한 범위, 확인 가능한 결과를 구분하여 정리한다.',
                    'completion_criteria': '본인 역할, 수행 내용, 결과 근거를 구분하여 기록함',
                    'deliverable': f'{name} 기여 기록',
                },
            ]
        else:
            raise ValueError('Unsupported allowed_action_type')

        items.append({
            'step_id': sid,
            'order': index,
            'title': title,
            'purpose': purpose,
            'reason': reason,
            'skill_targets': [{
                'skill_name': name,
                'student_status': status,
                'action_type': action_type,
            }],
            # Do not fabricate a relationship between a course and a skill.
            # The verified source-grounded course list remains separately shown.
            'related_course_ids': [],
            'depends_on': [],
            'evidence_refs': [skill['comparison_ref']],
            'limitations': '검증된 현재 자료에 한정한 안내입니다. 순서는 선수 관계나 학습 기간을 의미하지 않습니다.',
            'tasks': tasks,
        })

    # Pass the same strict server checks as normal Gemini output. In particular,
    # experience status, evidence refs and forbidden skill expansion are checked.
    result = validate_result({'recommended_courses': [], 'roadmap': items}, basis)
    result['status'] = 'partial'
    result['generation_mode'] = 'verified_evidence_fallback'
    result['roadmap_source'] = 'server_verified_evidence'
    result['limitations'] = [*result['limitations'],
        'AI 실행 로드맵 응답이 검증을 통과하지 못해, 확인된 직무 근거와 사용자 답변만으로 구성한 안내를 표시합니다.',
        '경험 미확인 기술은 학습 부족으로 단정하지 않고 경험 확인 단계로만 제안합니다.']
    for step in result['roadmap']:
        step['recommendation_kind'] = 'guidance'
    return result
