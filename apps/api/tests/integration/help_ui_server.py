"""Fictional student examples captured from the real web UI and real API/SQLite.

External auth/AI/job/activity responses are fixtures. External networking is blocked.
Run with Next on :15102 pointing to :18083. Never loads production credentials/data.
"""
from contextlib import closing
import explore_ui_server as explore
from repositories.plans import connect
from scripts.seed_dev import U, D, C1, C2
from services import activity_reasons

server = explore.server
explore.state['partial'] = False
with closing(connect()) as db:
    db.execute('UPDATE universities SET university_name=? WHERE university_id=?', ('한빛대학교 (예시)', U))
    db.execute('UPDATE departments SET department_name=? WHERE department_id=?', ('컴퓨터공학과', D))
    db.execute('UPDATE course_catalogs SET version_label=?,source_name=? WHERE catalog_id=?',
               ('2026학년도 전공 과목', '가상 학생 도움말용 교육과정', C1))
    db.execute('UPDATE course_catalogs SET is_selectable=0 WHERE catalog_id=?', (C2,))
    db.execute('UPDATE catalog_courses SET description_text=?,description_page_start=12,description_page_end=12 WHERE catalog_id=? AND course_id=?',
               ('관계형 데이터베이스의 구조와 SQL을 활용한 데이터 조회 및 집계를 학습한다.', C1, server.roadmap_scenario.DB_COURSE))
    db.execute('UPDATE catalog_courses SET recommendation_reason=? WHERE catalog_id=? AND course_id=?',
               ('SQL로 데이터를 조회하고 집계하는 방법을 익혀 데이터 분석에 필요한 기초를 다질 수 있습니다.', C1, server.roadmap_scenario.DB_COURSE))
    for name, description, reason in [
        ('소프트웨어 설계', '요구사항을 정리하고 소프트웨어의 구조와 구성 요소를 설계한다.',
         '분석 결과를 제공하는 서비스를 구상할 때 필요한 요구사항 정리와 소프트웨어 구조 설계를 연습할 수 있습니다.'),
        ('운영체제', '프로세스와 메모리 관리, 파일 시스템의 동작 원리를 학습한다.',
         '데이터 처리 프로그램이 실행되는 환경을 이해하는 데 필요한 프로세스·메모리·파일 관리의 기초를 학습합니다.'),
        ('프로젝트 실습', '문제를 정의하고 팀 프로젝트의 구현 결과를 검증하여 문서로 정리한다.',
         '관심 있는 데이터 문제를 프로젝트로 구체화하고, 구현 결과와 본인이 맡은 역할을 정리하는 연습을 할 수 있습니다.'),
    ]:
        db.execute('UPDATE catalog_courses SET description_text=?,recommendation_reason=? WHERE catalog_id=? AND course_name=?',
                   (description, reason, C1, name))
    db.execute('INSERT INTO catalog_course_keywords(catalog_id,course_id,keyword,keyword_role,evidence_text,evidence_page_start,evidence_page_end) VALUES(?,?,?,?,?,?,?)',
               (C1, server.roadmap_scenario.DB_COURSE, 'SQL', 'learning', 'SQL을 활용한 데이터 조회 및 집계를 학습한다.', 12, 12))
    db.commit()


def activities(db, *, include_event_context=False):
    server.counters['provider_fixture'] += 1
    return [dict(id='minseo-data-example', kind='competition', title='대학생 공공데이터 분석 아이디어 공모전 (예시)',
                 category='데이터 분석', host='한빛 데이터 연구회 (예시)', target='대학생',
                 description_text='공공데이터를 분석하고 지역 생활의 문제를 해결할 아이디어를 제안하는 활동입니다.',
                 period='2026.11.01 ~ 2026.12.20', url='https://www.contestkorea.com/sub/view.php?str_no=example')], dict(
                     source='contestkorea',kind='competition',status='success')


server.activities.load_contestkorea_catalog = activities


def activity_reason_response(schema, instruction, data, **kwargs):
    """Mock only AI output; real evidence validation and saved reasons still run."""
    server.counters['activity_reason_fixture'] = server.counters.get('activity_reason_fixture', 0) + 1
    reasons = []
    for activity in data['activities']:
        evidence = next(item for item in activity['evidence'] if item['kind'] == 'detail')
        references = [{'evidence_id': evidence['id'], 'quote': evidence['text']}]
        reasons.append({'activity_id': activity['activity_id'], 'sentences': [
            {'perspective': 'career', 'basis': 'inference',
             'text': '공공데이터로 지역 생활의 문제를 살펴보는 활동을 통해 데이터 분석가라는 진로에 필요한 문제 정의와 분석 방향 설정을 연습해 볼 수 있습니다.',
             'evidence': references, 'experience_ids': []},
            {'perspective': 'expected', 'basis': 'inference',
             'text': '관심 있는 문제와 관련된 데이터를 찾아보고 분석 결과를 해결 아이디어로 정리하는 경험으로 확장할 수 있습니다.',
             'evidence': references, 'experience_ids': []},
        ]})
    return schema(reasons=reasons)


activity_reasons._generate = activity_reason_response

if __name__ == '__main__':
    import uvicorn
    try:
        uvicorn.run(server.app, host='127.0.0.1', port=18083)
    finally:
        server.temporary.cleanup()
