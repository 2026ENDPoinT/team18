"""P1 API: anonymous session ownership and persistent basic plan input."""
from contextlib import closing
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
import json
import re
import secrets
import sqlite3
import uuid
from config import APP_ORIGIN, SECURE_COOKIE, API_HOST, API_PORT
from repositories.p1 import Repository, connect, migrate

COOKIE = 'roadmap_session'
FIELDS = ('career_goal', 'target_role', 'university_id', 'department_id', 'catalog_id', 'year_level', 'earned_credits', 'gpa', 'gpa_scale')


def now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


class Problem(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message


def validate(repo, values):
    goal = values['career_goal']
    if not isinstance(goal, str) or not goal.strip():
        raise Problem(422, "validation_error", "목표·관심 분야를 입력해 주세요.")
    if len(goal) > 10000:
        raise Problem(422, 'validation_error', '목표는 10,000자 이하여야 합니다.')
    values['career_goal'] = goal.strip()
    role = values['target_role']
    if role is not None:
        if not isinstance(role, str) or len(role.strip()) > 100:
            raise Problem(422, 'validation_error', '희망 직무는 100자 이하여야 합니다.')
        values['target_role'] = role.strip() or None
    for name in ('university_id', 'department_id', 'catalog_id'):
        if values[name] is not None and (not isinstance(values[name], str) or len(values[name]) > 100):
            raise Problem(422, 'validation_error', '기준 자료 식별자가 올바르지 않습니다.')
    year = values['year_level']
    if year is not None and (type(year) is not int or not 1 <= year <= 4):
        raise Problem(422, 'validation_error', '학년은 1~4 사이여야 합니다.')
    for name, maximum, places in (('earned_credits', Decimal('9999.9'), 1), ('gpa', Decimal('9.99'), 2), ('gpa_scale', Decimal('9.99'), 2)):
        value = values[name]
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise Problem(422, 'validation_error', '학점과 GPA는 숫자로 입력해 주세요.')
        try:
            n = Decimal(str(value))
            if not n.is_finite() or n < 0 or n > maximum or n != n.quantize(Decimal(1).scaleb(-places)):
                raise ValueError
        except (InvalidOperation, ValueError):
            raise Problem(422, 'validation_error', '학점 또는 GPA의 범위와 소수 자릿수를 확인해 주세요.')
        values[name] = float(n)
    if values['gpa'] is not None and (values['gpa_scale'] is None or values['gpa_scale'] <= 0 or values['gpa'] > values['gpa_scale']):
        raise Problem(422, 'validation_error', 'GPA는 0 이상 만점 이하이며 만점 기준이 필요합니다.')
    if values['gpa_scale'] is not None and values['gpa_scale'] <= 0:
        raise Problem(422, 'validation_error', 'GPA 만점 기준은 0보다 커야 합니다.')
    university, department, catalog = (values[k] for k in ('university_id', 'department_id', 'catalog_id'))
    if university and not repo.university_valid(university):
        raise Problem(422, 'validation_error', '선택할 수 없는 학교입니다.')
    if department and not repo.department_valid(department, university):
        raise Problem(422, 'validation_error', '학과가 선택한 학교에 속하지 않습니다.')
    if catalog and not repo.catalog_valid(catalog, department, values['_existing_catalog']):
        raise Problem(422, 'validation_error', '과목 목록이 선택한 학과에 속하지 않습니다.')


def payload(row):
    status = 'unavailable' if not row['catalog_id'] else 'unconfirmed'
    if row['catalog_id'] and row['reviewed_catalog_id'] == row['catalog_id'] and row['reviewed_selection_revision'] == row['course_selection_revision'] and row['reviewed_at']:
        status = 'partial' if row['reported_missing_courses'] else 'confirmed'
    return {'request_id': row['request_id'], 'input': {key: row[key] for key in FIELDS}, 'input_revision': row['input_revision'], 'selection_revision': row['course_selection_revision'], 'review_status': status, 'updated_at': row['updated_at']}


class Handler(BaseHTTPRequestHandler):
    def respond(self, status, body, cookie=None):
        content = json.dumps(body, ensure_ascii=False, allow_nan=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        if cookie:
            self.send_header('Set-Cookie', cookie)
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def owner(self, repo):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get('Cookie', ''))
            token = cookie[COOKIE].value if COOKIE in cookie else ''
        except Exception:
            return None
        if not re.fullmatch(r'[A-Za-z0-9_-]{43}', token):
            return None
        digest = sha256(token.encode()).hexdigest()
        return repo.owner(digest, now())

    def body(self):
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if size < 1 or size > 32768:
                raise ValueError
            value = json.loads(self.rfile.read(size), parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            if not isinstance(value, dict):
                raise ValueError
            return value
        except (ValueError, UnicodeDecodeError):
            raise Problem(400, 'invalid_json', '요청 형식을 확인해 주세요.')

    def run_request(self, method):
        path = urlparse(self.path).path
        if path == '/api/health' and method == 'GET':
            return self.respond(200, {'status': 'ok'})
        # SameSite is defense in depth; require the configured browser origin for writes.
        if method in ('POST', 'PATCH') and self.headers.get('Origin', '').rstrip('/') != APP_ORIGIN:
            raise Problem(403, 'invalid_origin', '요청 출처를 확인할 수 없습니다.')
        with closing(connect()) as db:
            repo = Repository(db)
            if method == 'GET' and path == '/api/reference':
                return self.respond(200, repo.reference())
            owner = self.owner(repo)
            if path == '/api/roadmap-inputs' and method == 'POST':
                repo.begin()
                cookie = None
                if owner is None:
                    token = secrets.token_urlsafe(32)
                    owner_id = str(uuid.uuid4())
                    created = now()
                    expires = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(timespec='microseconds')
                    repo.add_owner(owner_id, sha256(token.encode()).hexdigest(), expires, created)
                    cookie = f'{COOKIE}={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=2592000' + ('; Secure' if SECURE_COOKIE else '')
                else:
                    owner_id = owner['owner_id']
                request_id, created = str(uuid.uuid4()), now()
                repo.create_plan(request_id, owner_id, created)
                row = repo.plan(request_id, owner_id)
                repo.commit()
                return self.respond(201, payload(row), cookie)
            if path == '/api/roadmap-inputs/resume' and method == 'GET':
                row = repo.resume(owner['owner_id']) if owner else None
                return self.respond(200, {'found': bool(row), 'request': dict(row) if row else None})
            match = re.fullmatch(r'/api/roadmap-inputs/([0-9a-f-]{36})', path)
            if match and method in ('GET', 'PATCH'):
                if not owner:
                    raise Problem(401, 'unauthorized', '세션이 만료되었거나 유효하지 않습니다.')
                if method == 'PATCH':
                    body = self.body()
                    if set(body) != {'expected_input_revision', 'changes'} or type(body['expected_input_revision']) is not int or body['expected_input_revision'] < 0 or not isinstance(body['changes'], dict) or not set(body['changes']).issubset(FIELDS):
                        raise Problem(422, 'validation_error', '수정 요청 형식을 확인해 주세요.')
                    repo.begin()
                row = repo.plan(match[1], owner['owner_id'])
                if not row:
                    raise Problem(404, 'not_found', '계획을 찾을 수 없습니다.')
                if method == 'GET':
                    return self.respond(200, payload(row))
                if row['input_revision'] != body['expected_input_revision']:
                    raise Problem(409, 'revision_conflict', '다른 화면에서 입력이 변경되었습니다. 최신 내용을 불러와 확인해 주세요.')
                values = {field: row[field] for field in FIELDS}
                values.update(body['changes'])
                values['_existing_catalog'] = row['catalog_id']
                validate(repo, values)
                changed = any(values[k] != row[k] for k in FIELDS)
                scope_changed = any(values[k] != row[k] for k in ('university_id', 'department_id', 'catalog_id'))
                if changed:
                    repo.update_plan(match[1], FIELDS, values, scope_changed, now())
                result = payload(repo.plan(match[1], owner['owner_id']))
                repo.commit()
                return self.respond(200, result)
            raise Problem(404, 'not_found', '요청한 경로를 찾을 수 없습니다.')

    def handle_request(self, method):
        try:
            self.run_request(method)
        except Problem as error:
            self.respond(error.status, {'error': error.code, 'message': error.message})
        except sqlite3.Error:
            self.respond(503, {'error': 'storage_unavailable', 'message': '저장소를 사용할 수 없습니다. 잠시 후 다시 시도해 주세요.'})

    def do_GET(self): self.handle_request('GET')
    def do_POST(self): self.handle_request('POST')
    def do_PATCH(self): self.handle_request('PATCH')


if __name__ == '__main__':
    migrate()
    server = ThreadingHTTPServer((API_HOST, API_PORT), Handler)
    print(f'API listening on {API_HOST}:{API_PORT}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
