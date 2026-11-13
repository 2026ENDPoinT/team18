"""Basic form browser QA: real API/SQLite, fictional reference data, no external calls.

Extends the help fixture with a second school, multiple catalogs and an empty
catalog department. Run with Next on :15102 pointing to :18083.
"""
from contextlib import closing
from datetime import date
import help_ui_server as help_fixture
from repositories.plans import connect

server = help_fixture.server
with closing(connect()) as db:
    db.execute('INSERT INTO universities VALUES(?,?,1)', ('basic-other', '다온대학교 (예시)'))
    db.execute('INSERT INTO departments VALUES(?,?,?,1)', ('basic-data', 'basic-other', '데이터사이언스학과'))
    db.execute('INSERT INTO departments VALUES(?,?,?,1)', ('basic-empty', 'basic-other', '융합학과'))
    for cid, year in [('basic-current', date.today().year), ('basic-previous', date.today().year - 1)]:
        db.execute('INSERT INTO course_catalogs VALUES(?,?,?,?,?,?,?,?,?,NULL,1)',
                   (cid, 'basic-data', year, f'{year}학년도 전공 과목', '검증용',
                    'complete', '가상 교육과정', None, '2026-11-14T00:00:00Z'))
    db.commit()

if __name__ == '__main__':
    import uvicorn
    try:
        uvicorn.run(server.app, host='127.0.0.1', port=18083)
    finally:
        server.temporary.cleanup()
