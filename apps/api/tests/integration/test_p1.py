import concurrent.futures
import http.client
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import threading
import sys
import unittest

TEMP = tempfile.TemporaryDirectory()
os.environ['ROADMAP_DB_PATH'] = str(Path(TEMP.name) / 'test.sqlite3')
os.environ['ROADMAP_INSECURE_LOCAL_COOKIE'] = '1'
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'app'))
spec = importlib.util.spec_from_file_location('roadmap_api', Path(__file__).resolve().parents[2] / 'app' / 'main.py')
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        api.migrate()
        cls.server = api.ThreadingHTTPServer(('127.0.0.1', 0), api.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        TEMP.cleanup()

    def request(self, method, path, data=None, cookie=None, origin='http://localhost:3000'):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=10)
        headers = {'Origin': origin}
        if cookie: headers['Cookie'] = cookie
        if data is not None: headers['Content-Type'] = 'application/json'
        conn.request(method, '/api' + path, body=json.dumps(data) if data is not None else None, headers=headers)
        resp = conn.getresponse()
        body = json.loads(resp.read())
        result = (resp.status, body, resp.getheader('Set-Cookie'))
        conn.close()
        return result

    def create(self):
        status, body, cookie = self.request('POST', '/roadmap-inputs')
        self.assertEqual(status, 201)
        self.assertIn('HttpOnly', cookie)
        self.assertIn('SameSite=Strict', cookie)
        return body['request_id'], cookie.split(';')[0]

    def patch(self, rid, cookie, revision, changes):
        return self.request('PATCH', '/roadmap-inputs/' + rid, {'expected_input_revision': revision, 'changes': changes}, cookie)

    def test_session_persistence_conflict_and_validation(self):
        rid, cookie = self.create()
        other_id, other_cookie = self.create()
        self.assertEqual(self.request('GET', '/roadmap-inputs/' + rid, cookie=other_cookie)[0], 404)
        self.assertEqual(self.patch(rid, other_cookie, 0, {'career_goal':'x'})[0], 404)
        self.assertEqual(self.request('GET', '/roadmap-inputs/' + rid)[0], 401)
        self.assertEqual(self.request('POST', '/roadmap-inputs', origin='http://evil.test')[0], 403)
        self.assertEqual(self.request('GET', '/roadmap-inputs/resume', cookie=cookie)[1]['request']['request_id'], rid)
        self.assertEqual(self.request('GET', '/roadmap-inputs/resume')[1], {'found': False, 'request': None})
        for changes in ({'career_goal':'  '}, {'career_goal':'x','gpa':0}, {'career_goal':'x','gpa':4.4,'gpa_scale':4.3}, {'career_goal':'x','earned_credits':-1}, {'career_goal':'x','year_level':5}, {'career_goal':'x','university_id':'unknown'}):
            self.assertEqual(self.patch(rid, cookie, 0, changes)[0], 422, changes)
        status, result, _ = self.patch(rid, cookie, 0, {'career_goal':'개발', 'earned_credits':0, 'gpa':0, 'gpa_scale':4.5})
        self.assertEqual(status, 200)
        self.assertEqual(result['input_revision'], 1)
        self.assertEqual(result['input']['earned_credits'], 0)
        self.assertEqual(result['input']['gpa'], 0)
        self.assertIsNone(result['input']['year_level'])
        self.assertEqual(self.patch(rid, cookie, 0, {'career_goal':'충돌'})[0], 409)
        self.assertEqual(self.patch(rid, cookie, 1, {'career_goal':'개발'})[1]['input_revision'], 1)
        api.migrate()  # reopening the same DB does not wipe existing data
        self.assertEqual(self.request('GET', '/roadmap-inputs/' + rid, cookie=cookie)[1]['input']['career_goal'], '개발')
        self.assertNotEqual(rid, other_id)

    def test_secure_cookie_and_expiration(self):
        previous = api.SECURE_COOKIE
        try:
            api.SECURE_COOKIE = True
            status, body, cookie = self.request('POST', '/roadmap-inputs')
            self.assertEqual(status, 201)
            self.assertIn('; Secure', cookie)
        finally:
            api.SECURE_COOKIE = previous
        token_cookie = cookie.split(';')[0]
        with api.closing(api.connect()) as db:
            db.execute("UPDATE session_owners SET expires_at='2000-01-01T00:00:00+00:00' WHERE token_digest=?", (api.sha256(token_cookie.split('=', 1)[1].encode()).hexdigest(),))
        self.assertEqual(self.request('GET', '/roadmap-inputs/' + body['request_id'], cookie=token_cookie)[0], 401)
        self.assertFalse(self.request('GET', '/roadmap-inputs/resume', cookie=token_cookie)[1]['found'])

    def test_relations_and_atomic_versions(self):
        with api.closing(api.connect()) as db:
            db.execute("INSERT INTO universities VALUES('u1','학교1',1),('u2','학교2',1)")
            db.execute("INSERT INTO departments VALUES('d1','u1','학과1',1),('d2','u2','학과2',1)")
            db.execute("INSERT INTO course_catalogs VALUES('c1','d1',NULL,'버전','범위','unknown','출처',NULL,'2026-01-01',NULL,1)")
        rid, cookie = self.create()
        self.assertEqual(self.patch(rid,cookie,0,{'career_goal':'목표','university_id':'u1','department_id':'d2'})[0],422)
        self.assertEqual(self.patch(rid,cookie,0,{'career_goal':'목표','university_id':'u2','department_id':'d2','catalog_id':'c1'})[0],422)
        result=self.patch(rid,cookie,0,{'career_goal':'목표','university_id':'u1','department_id':'d1','catalog_id':'c1'})[1]
        self.assertEqual((result['input_revision'],result['selection_revision'],result['review_status']),(1,1,'unconfirmed'))
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda goal:self.patch(rid,cookie,1,{'career_goal':goal})[0], ['목표1','목표2']))
        self.assertEqual(sorted(results),[200,409])
        result=self.request('GET','/roadmap-inputs/'+rid,cookie=cookie)[1]
        self.assertEqual(result['selection_revision'],1)


if __name__ == '__main__': unittest.main()
