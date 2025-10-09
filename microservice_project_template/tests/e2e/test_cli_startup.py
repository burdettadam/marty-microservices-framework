from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.e2e
def test_cli_serve_runs_and_stops(tmp_path) -> None:
    env = os.environ.copy()
    env.setdefault("APP_GRPC_HOST", "127.0.0.1")
    env.setdefault("APP_GRPC_PORT", "50555")
    env.setdefault("APP_METRICS_PORT", "9100")

    start = time.monotonic()
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "microservice_template.main",
            "serve",
            "--shutdown-after",
            "1.0",
        ],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        check=False,
        text=True,
    )

    duration = time.monotonic() - start
    assert completed.returncode == 0, completed.stderr
    assert duration < 5
