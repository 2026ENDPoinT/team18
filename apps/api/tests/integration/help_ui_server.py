"""Fictional student examples captured from the real web UI and real API/SQLite.

External auth/AI/job/activity responses are fixtures. External networking is blocked.
Run with Next on :15102 pointing to :18083. Never loads production credentials/data.
"""
from contextlib import closing
import explore_ui_server as explore
from repositories.plans import connect
from scripts.seed_dev import U, D, C1, C2
from services.roadmap_schemas import GeneratedRoadmap

server = explore.server
with closing(connect()) as db:
    db.execute('UPDATE universities SET university_name=? WHERE university_id=?', ('한빛대학교 (예시)', U))
    db.execute('UPDATE departments SET department_name=? WHERE department_id=?', ('컴퓨터공학과', D))
    db.execute('UPDATE course_catalogs SET version_label=?,source_name=? WHERE catalog_id=?',
               ('2026학년도 전공 과목', '가상 학생 도움말용 교육과정', C1))
    db.execute('UPDATE course_catalogs SET is_selectable=0 WHERE catalog_id=?', (C2,))
    db.execute('UPDATE catalog_courses SET description_text=?,description_page_start=12,description_page_end=12 WHERE catalog_id=? AND course_id=?',
               ('관계형 데이터베이스의 구조와 SQL을 활용한 데이터 조회 및 집계를 학습한다.', C1, server.roadmap_scenario.DB_COURSE))
    db.execute('INSERT INTO catalog_course_keywords(catalog_id,course_id,keyword,keyword_role,evidence_text,evidence_page_start,evidence_page_end) VALUES(?,?,?,?,?,?,?)',
               (C1, server.roadmap_scenario.DB_COURSE, 'SQL', 'learning', 'SQL을 활용한 데이터 조회 및 집계를 학습한다.', 12, 12))
    db.commit()


def roadmap(data):
    server.counters['roadmap_fixture'] += 1
    raw = server.roadmap_scenario.fake_roadmap(data).model_dump()
    skill = next(item for item in data['skills'] if item['skill_name'] == 'SQL')
    for course in raw['recommended_courses']:
        course['reason'] = 'SQL로 데이터를 조회하고 집계하는 학습 내용이 데이터 분석 목표와 연결됩니다.'
        course['personalization_reason'] = '행사 신청 데이터를 분석하려는 목표와 연결해 SQL 조회·집계 내용을 살펴볼 수 있어요.'
    tasks = [
        ('SQL로 맡은 조회 작업 확인하기', '행사 신청 프로젝트에서 SQL을 직접 사용한 경험을 확인하고 담당한 쿼리를 찾아 정리하세요.', '담당한 쿼리와 역할을 적거나, 찾지 못한 경우 확인이 필요하다고 기록하면 완료입니다.', '담당 쿼리와 역할을 적은 경험 확인 메모'),
        ('집계 결과를 설명한 경험 확인하기', 'SQL 집계 결과를 직접 설명한 경험을 확인하고 결과 화면이나 메모를 찾아 정리하세요.', '본인이 설명한 부분과 자료 위치 또는 확인할 질문을 기록하면 완료입니다.', '결과 화면과 본인 설명을 묶은 기록'),
        ('SQL 경험 확인 답변 정리하기', '앞서 찾은 자료로 SQL 경험을 확인하고 본인의 수행 내용과 더 확인할 질문을 정리하세요.', '직접 수행한 일과 팀원이 맡은 일을 구분한 기록이 있으면 완료입니다.', '본인 역할과 팀 역할을 구분한 프로젝트 메모'),
    ]
    for step, (title, action, criteria, artifact) in zip(raw['roadmap'], tasks):
        step.update(title=title, purpose='데이터 분석 목표와 연결되는 본인의 SQL 경험 정리',
                    reason='행사 신청 데이터를 분석하고 싶다는 목표가 있고, 문서에 있는 SQL 경험은 본인 확인이 필요해요.',
                    limitations='현재 확인한 프로젝트 자료를 기준으로 합니다.')
        task = step['tasks'][0]
        if skill['student_status'] not in ('confirmed_experience', 'no_experience'):
            task.update(title=title, action=action, completion_criteria=criteria, deliverable=artifact)
    return GeneratedRoadmap(**raw)


server.roadmaps.generate_roadmap = roadmap


def activities(db, *, include_event_context=False):
    server.counters['provider_fixture'] += 1
    return [dict(id='minseo-data-example', kind='competition', title='대학생 공공데이터 분석 아이디어 공모전 (예시)',
                 category='데이터 분석', host='한빛 데이터 연구회 (예시)', target='대학생',
                 description_text='공공데이터를 분석하고 지역 생활의 문제를 해결할 아이디어를 제안하는 활동입니다.',
                 period='2026.11.01 ~ 2026.12.20', url='https://www.contestkorea.com/sub/view.php?str_no=example')], dict(
                     source='contestkorea',kind='competition',status='success')


server.activities.load_contestkorea_catalog = activities

if __name__ == '__main__':
    import uvicorn
    try:
        uvicorn.run(server.app, host='127.0.0.1', port=18083)
    finally:
        server.temporary.cleanup()
