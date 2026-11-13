import os
from pathlib import Path
import subprocess
import sys
import pytest


@pytest.mark.skipif(not os.environ.get('ROADMAP_TEST_POSTGRES_URL'), reason='isolated PostgreSQL not configured')
def test_roadmap_batch_on_postgres():
    script = Path(__file__).with_name('roadmap_batch_postgres_scenario.py')
    result = subprocess.run([sys.executable, str(script)], cwd=script.parents[2],
                            env=os.environ.copy(), text=True, capture_output=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
