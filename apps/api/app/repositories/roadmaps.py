"""Caller must authorize/lock the parent plan before all reads and writes."""
import uuid
from datetime import datetime, timedelta, timezone

from api.domain import now
from repositories.experience_analysis import AnalysisRepository, decode
from services.project_experience import digest
from services.roadmap_validation import error_metadata
from course_groups import grouped_roadmap


class RoadmapRepository(AnalysisRepository):
    def get(self, rid, run_id):
        row = self.db.execute('SELECT * FROM roadmap_runs WHERE request_id=? AND run_id=?', (rid, run_id)).fetchone()
        return dict(row) if row else None

    def history(self, rid):
        return [dict(r) for r in self.db.execute('SELECT * FROM roadmap_runs WHERE request_id=? ORDER BY created_at DESC,run_id DESC', (rid,))]

    def reusable(self, rid, basis_hash):
        rows = self.db.execute("""SELECT * FROM roadmap_runs WHERE request_id=? AND basis_hash=?
            AND status IN ('success','partial') ORDER BY created_at DESC,run_id DESC""", (rid, basis_hash))
        for row in rows:
            run = dict(row)
            work = decode(run['basis_json']).get('_generation_work')
            if not work or work.get('verified'):
                return run
        return None

    def active(self, rid):
        row = self.db.execute("SELECT * FROM roadmap_runs WHERE request_id=? AND status='generating'", (rid,)).fetchone()
        if row:
            return dict(row)
        for run in self.history(rid):
            work = decode(run['basis_json']).get('_generation_work')
            if run['status'] in ('success', 'partial') and work and not work.get('verified'):
                return run
        return None

    def expire(self, rid):
        self.db.execute("""UPDATE roadmap_runs SET status='failed',error_code='generation_expired',finished_at=?
            WHERE request_id=? AND status='generating' AND lease_until<?""", (now(), rid, now()))
        for run in self.history(rid):
            work = decode(run['basis_json']).get('_generation_work')
            lease = run['lease_until'] if isinstance(run['lease_until'], datetime) else datetime.fromisoformat(run['lease_until'])
            if work and not work.get('verified') and run['status'] in ('success', 'partial') and lease < datetime.now(timezone.utc):
                self.db.execute('DELETE FROM roadmap_task_progress WHERE run_id=?', (run['run_id'],))
                self.db.execute("UPDATE roadmap_runs SET status='failed',result_json=NULL,error_code='generation_expired',finished_at=? WHERE run_id=?",
                                (now(), run['run_id']))

    def create(self, rid, basis, *, lease_minutes=3):
        run_id, created = str(uuid.uuid4()), now()
        lease = (datetime.now(timezone.utc) + timedelta(minutes=lease_minutes)).isoformat()
        self.db.execute('''INSERT INTO roadmap_runs(run_id,request_id,input_revision,basis_hash,catalog_id,
            basis_json,status,model_name,rules_version,created_at,lease_until) VALUES(?,?,?,?,?,?,'generating',?,?,?,?)''',
            (run_id, rid, basis['input_revision'], digest(basis), basis['profile']['catalog_id'], self.encode(basis),
             basis['model_name'], basis['rules_version'], created, lease))
        return self.get(rid, run_id)

    def update_work(self, rid, run_id, basis, work, *, update_hash=False):
        stored = {**basis, '_generation_work': work}
        self.db.execute('UPDATE roadmap_runs SET basis_json=?,basis_hash=? WHERE request_id=? AND run_id=?',
                        (self.encode(stored), digest(basis) if update_hash else self.get(rid, run_id)['basis_hash'], rid, run_id))

    def retry(self, rid, run_id, basis, work):
        lease = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
        self.db.execute("""UPDATE roadmap_runs SET status='generating',error_code=NULL,finished_at=NULL,
            lease_until=?,basis_json=? WHERE request_id=? AND run_id=? AND status='failed'""",
            (lease, self.encode({**basis, '_generation_work': work}), rid, run_id))

    def fail(self, rid, run_id, code):
        self.db.execute("""UPDATE roadmap_runs SET status='failed',error_code=?,finished_at=?
            WHERE request_id=? AND run_id=? AND status='generating'""", (code, now(), rid, run_id))

    def finish(self, rid, run_id, result):
        self.db.execute("""UPDATE roadmap_runs SET status=?,result_json=?,finished_at=?
            WHERE request_id=? AND run_id=? AND status='generating'""", (result['status'], self.encode(result), now(), rid, run_id))
        for step in result['roadmap']:
            for task in step['tasks']:
                self.db.execute('INSERT INTO roadmap_task_progress(run_id,task_id,is_completed,updated_at) VALUES(?,?,FALSE,?)',
                                (run_id, task['task_id'], now()))
        return self.get(rid, run_id)

    def progress(self, run_id):
        return {r['task_id']: dict(r) for r in self.db.execute('SELECT * FROM roadmap_task_progress WHERE run_id=?', (run_id,))}

    def update_progress(self, run_id, task_id, completed, version):
        return self.db.execute('''UPDATE roadmap_task_progress SET is_completed=?,progress_version=progress_version+1,updated_at=?
            WHERE run_id=? AND task_id=? AND progress_version=?''', (completed, now(), run_id, task_id, version)).rowcount


def metadata(run, current):
    basis = decode(run['basis_json'])
    restricted = basis['document_basis'] != current['document_basis']
    lease = run['lease_until'] if isinstance(run['lease_until'], datetime) else datetime.fromisoformat(run['lease_until'])
    work = basis.get('_generation_work')
    expired = (run['status'] == 'generating' and lease < datetime.now(timezone.utc)) or run['error_code'] == 'generation_expired'
    states = dict(work['states']) if work else None
    if states and expired:
        states = {key: 'failed' if value == 'running' else value for key, value in states.items()}
    return {k: run[k] for k in ('run_id', 'request_id', 'input_revision', 'catalog_id', 'basis_hash', 'status', 'model_name',
                                'rules_version', 'created_at', 'finished_at', 'error_code')} | {
        **error_metadata(run['error_code']),
        'is_stale': run['basis_hash'] != digest(current), 'current_input_revision': current['input_revision'],
        'details_restricted': restricted,
        'limited_guidance_available': current.get('generation_mode') == 'limited_guidance',
        'restriction_reason': 'document_basis_changed' if restricted else None,
        'generation_expired': expired,
        **({'generation_tasks': states, 'generation_complete': bool(work.get('verified')),
            'generation_error': work.get('error'), 'lease_until': lease.isoformat()} if work else {}),
    }


def run_payload(store, run, current, *, include_unverified=False):
    meta = metadata(run, current)
    work = decode(run['basis_json']).get('_generation_work')
    if (meta['details_restricted'] or run['status'] not in ('success', 'partial') or
            (work and not work.get('verified') and not include_unverified)):
        return meta
    result = grouped_roadmap(decode(run['result_json']), run['catalog_id'])
    progress = store.progress(run['run_id'])
    for step in result['roadmap']:
        for task in step['tasks']:
            saved = progress[task['task_id']]
            task.update(is_completed=bool(saved['is_completed']), progress_version=saved['progress_version'], updated_at=saved['updated_at'])
    return {**result, **meta, 'progress': {'completed': sum(bool(p['is_completed']) for p in progress.values()), 'total': len(progress)}}
