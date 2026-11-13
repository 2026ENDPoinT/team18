"""Stage 2 browser QA; real API/SQLite and parser, deterministic external providers.

Start this script and Next dev on :15102 with API origin http://127.0.0.1:18083.
Inherits review_fixes_ui_server's disposable storage and external-network block.
"""
import review_fixes_ui_server as server
from services.gemini import GeminiError
from services.project_experience_schemas import DocumentExperience

state = {'partial': True, 'failure': False}


def project(schema, prompt, doc):
    server.counters['project_fixture'] += 1
    if state['failure']:
        raise GeminiError('gemini_timeout', '프로젝트 분석 응답 시간 초과')
    specifications = [
        ('React', '행사 신청 화면과 입력 검증을 구현했어요', 'personal'),
        ('Docker', '배포 환경을 구성했어요', 'team'),
        ('SQL', '신청 데이터를 조회했어요', 'personal'),
        ('Python', '통계를 정리했어요', 'personal'),
    ]
    text = doc['extracted_text']
    items = [dict(skill_name=skill, category='other', activity=activity, contribution_scope=scope,
                  evidence_text=next(line for line in text.splitlines() if skill in line))
             for skill, activity, scope in specifications]
    if state['partial']:
        items.append(dict(skill_name='Rust', category='other', activity='검증되지 않은 항목',
                          contribution_scope='unknown', evidence_text='문서에 없는 근거'))
    return DocumentExperience(document_id=doc['document_id'], extraction_revision=doc['extraction_revision'], experiences=items)


server.gemini_projects._generate = project


@server.app.post('/api/explore-fixture')
def fixture(body: dict):
    state.update({key: bool(value) for key, value in body.items() if key in state})
    return state


if __name__ == '__main__':
    import uvicorn
    try:
        uvicorn.run(server.app, host='127.0.0.1', port=18083)
    finally:
        server.temporary.cleanup()
