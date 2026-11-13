"""Opt-in, real Gemini with synthetic A–E inputs and an in-memory budget/cache.

No production database, user documents, crawler, ranking or roadmap history is used.
At most four provider requests (one per A–D profile), with SDK retries disabled.
"""
import json
import os
from pathlib import Path
import sqlite3

import pytest

from services.activity_reasons import attach_reasons


@pytest.mark.skipif(os.environ.get('GEMINI_LIVE_TEST') != '1' or not os.environ.get('GEMINI_API_KEY'),
                    reason='Real Gemini requires GEMINI_LIVE_TEST=1 and GEMINI_API_KEY; mocked tests are separate')
def test_activity_reasons_real_gemini(monkeypatch, tmp_path):
    for setting in ('GUEST_HOURLY_UNITS', 'GUEST_DAILY_UNITS', 'GLOBAL_DAILY_UNITS'):
        monkeypatch.setenv('ROADMAP_AI_' + setting, '4')
    monkeypatch.setenv('ROADMAP_AI_COOLDOWN_SECONDS', '0')
    cases = json.loads((Path(__file__).parents[1] / 'fixtures/activity_reason_cases.json').read_text())
    db = sqlite3.connect(':memory:', isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute('''CREATE TABLE ai_requests(request_id TEXT PRIMARY KEY, owner_id TEXT, operation TEXT,
        basis_hash TEXT, units INTEGER, status TEXT, created_at TEXT, lease_until TEXT, result_json TEXT)''')
    ctx = (db, None, {'owner_id': 'synthetic-live-test', 'is_anonymous': True})
    actual = []
    try:
        for case in cases:
            args = (ctx, case['case'], case['profile'], {'activities': [case['item']]})
            first = attach_reasons(*args, generate=True)
            item = first['activities'][0]
            expected = 'fallback' if case['case'] == 'E' else 'gemini'
            assert item['reason_source'] == expected, first.get('activity_reasons_error') or item['reason_status']
            assert attach_reasons(*args)['activities'] == first['activities']
            assert attach_reasons(*args, generate=True)['activities'] == first['activities']
            actual.append({'case': case['case'], 'source': item['reason_source'],
                           'text': item['personalization_reason'], 'evidence': item['reason_evidence']})
        assert db.execute('SELECT COUNT(*), SUM(units) FROM ai_requests').fetchone()[:] == (4, 4)
        report = tmp_path / 'actual-gemini-activity-reasons.json'
        report.write_text(json.dumps(actual, ensure_ascii=False, indent=2))
        print('Real Gemini synthetic-input output:', report)
        print(json.dumps(actual, ensure_ascii=False, indent=2))
    finally:
        db.close()
