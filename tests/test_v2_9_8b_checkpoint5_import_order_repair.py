"""Fresh-process import-order proof for the Checkpoint 3 guard repair.

No source, Scheduler runtime, authoritative database, memory, retrieval, or
financial capability is exercised. Each case starts an independent interpreter
so a prior successful import cannot hide a package-initialization cycle.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


@pytest.mark.parametrize(
    "module_name",
    (
        "printer_v1.operator_cli.abstract_campaign_command",
        "printer_v1.operator_cli.authoritative_live_operational_campaign",
        "printer_v1.operator_cli.one_command_15m_factory",
        "printer_v1.discovery.combined_executor",
    ),
)
def test_fresh_process_import_order_is_cycle_free(module_name: str) -> None:
    environment = dict(os.environ)
    existing = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        str(SRC) if not existing else os.pathsep.join((str(SRC), existing))
    )
    completed = subprocess.run(
        [sys.executable, "-c", f"import {module_name}"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, (
        f"fresh import failed for {module_name}\n"
        f"stdout:\n{completed.stdout}\n"
        f"stderr:\n{completed.stderr}"
    )
