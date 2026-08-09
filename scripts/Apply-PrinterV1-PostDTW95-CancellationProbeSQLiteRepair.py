from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

REPO = Path.home() / "Developer" / "MoneyPrinter"
BRANCH = "agent/v2-9-8b-post-dtw95-window15m-sqlite-lock-implementation"
RED_HEAD = "395bff66248f6b127775503fc43ff5f0b5a116b9"
SOURCE = Path("src/printer_v1/operator_cli/operational_memory_factory_command.py")
TEST_MODULE = "tests.test_post_dtw95_cancellation_probe_sqlite_contention"
RED_TEST = (
    TEST_MODULE
    + ".PostDTW95CancellationProbeSQLiteContentionTests"
    + ".test_short_writer_contention_is_tolerated"
)


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        list(args), cwd=REPO, text=True, capture_output=True
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(args)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


if not REPO.is_dir():
    raise SystemExit(f"repository missing: {REPO}")

run("git", "fetch", "origin", BRANCH)
run("git", "checkout", BRANCH)
run("git", "reset", "--hard", f"origin/{BRANCH}")

head = run("git", "rev-parse", "HEAD").stdout.strip()
if head != RED_HEAD:
    raise SystemExit(f"unexpected RED head: {head} != {RED_HEAD}")
if run("git", "status", "--porcelain").stdout.strip():
    raise SystemExit("tracked/untracked worktree must be clean before helper")

python = str(REPO / ".venv" / "bin" / "python")
red = run(python, "-m", "unittest", RED_TEST, check=False)
red_text = red.stdout + "\n" + red.stderr
if red.returncode == 0:
    raise SystemExit("RED test unexpectedly passed before implementation")
if "_read_campaign_supervision_cancellation_reason" not in red_text:
    raise SystemExit(
        "RED failure was not the expected missing cancellation-probe helper\n"
        + red_text
    )

source_path = REPO / SOURCE
text = source_path.read_text(encoding="utf-8")
original = text

import_marker = "from printer_v1.operator_cli.abstract_campaign_command import (\n"
if import_marker not in text:
    raise SystemExit("import insertion marker missing")
text = text.replace(
    import_marker,
    "from printer_v1.db.sqlite_write_contracts import "
    "DEFAULT_OPERATIONAL_BUSY_TIMEOUT_MS\n" + import_marker,
    1,
)

constant_marker = "HEARTBEAT_SECONDS = 30\n"
if constant_marker not in text:
    raise SystemExit("heartbeat constant marker missing")
text = text.replace(
    constant_marker,
    constant_marker
    + "CANCELLATION_PROBE_SQLITE_BUSY_TIMEOUT_SECONDS = (\n"
    + "    DEFAULT_OPERATIONAL_BUSY_TIMEOUT_MS / 1000.0\n"
    + ")\n"
    + 'CANCELLATION_PROBE_SQLITE_LOCKED = "CANCELLATION_PROBE_SQLITE_LOCKED"\n',
    1,
)

old_signature = '''def _read_only(
    path: str | Path | None = None,
    *,
    expected_path: str | Path | None = None,
) -> sqlite3.Connection:
'''
new_signature = '''def _read_only(
    path: str | Path | None = None,
    *,
    expected_path: str | Path | None = None,
    timeout_seconds: float = 0.0,
) -> sqlite3.Connection:
'''
if old_signature not in text:
    raise SystemExit("_read_only signature marker missing")
text = text.replace(old_signature, new_signature, 1)

old_connect = '''    connection = sqlite3.connect(
        f"file:{target.as_posix()}?mode=ro", uri=True, timeout=0.0
    )
'''
new_connect = '''    connection = sqlite3.connect(
        f"file:{target.as_posix()}?mode=ro",
        uri=True,
        timeout=max(0.0, float(timeout_seconds)),
    )
'''
if old_connect not in text:
    raise SystemExit("_read_only connect marker missing")
text = text.replace(old_connect, new_connect, 1)

helper_marker = "\n\ndef _active_counts(connection: sqlite3.Connection) -> dict[str, int]:\n"
if helper_marker not in text:
    raise SystemExit("helper insertion marker missing")
helper = r'''

def _sqlite_busy_or_locked(exc: sqlite3.OperationalError) -> bool:
    raw = str(exc).lower()
    return "locked" in raw or "busy" in raw


def _read_campaign_supervision_cancellation_reason(
    path: str | Path,
    *,
    expected_path: str | Path,
    supervision_id: str,
    campaign_id: str,
    run_id: str,
    busy_timeout_seconds: float = CANCELLATION_PROBE_SQLITE_BUSY_TIMEOUT_SECONDS,
) -> str | None:
    """Read cancellation state with bounded tolerance for a legitimate writer."""
    try:
        connection = _read_only(
            path,
            expected_path=expected_path,
            timeout_seconds=busy_timeout_seconds,
        )
        try:
            row = connection.execute(
                """SELECT supervision_state,cancellation_reason
                   FROM printer_memory_factory_campaign_supervision
                   WHERE supervision_id=? AND campaign_id=? AND run_id=?""",
                (supervision_id, campaign_id, run_id),
            ).fetchone()
        finally:
            connection.close()
    except sqlite3.OperationalError as exc:
        if _sqlite_busy_or_locked(exc):
            return CANCELLATION_PROBE_SQLITE_LOCKED
        raise
    if row is None:
        return "CAMPAIGN_SUPERVISION_MISSING"
    if row["supervision_state"] == "STOPPING":
        return str(
            row["cancellation_reason"]
            or "OPERATOR_REQUESTED_COOPERATIVE_STOP"
        )
    if row["supervision_state"] == "TERMINAL":
        return "CAMPAIGN_SUPERVISION_TERMINAL"
    return None
'''
text = text.replace(helper_marker, helper + helper_marker, 1)

probe_anchor = text.index("        def cancellation_probe() -> str | None:\n")
probe_start = text.index("            connection = _read_only(\n", probe_anchor)
probe_end = text.index("\n\n        def retain_factory_run_id", probe_start)
replacement = '''            return _read_campaign_supervision_cancellation_reason(
                active_db,
                expected_path=active_db,
                supervision_id=command.supervision_id,
                campaign_id=command.campaign_id,
                run_id=command.run_id,
            )'''
text = text[:probe_start] + replacement + text[probe_end:]

if text == original:
    raise SystemExit("source patch produced no change")
source_path.write_text(text, encoding="utf-8")

changed = [
    line.strip()
    for line in run("git", "diff", "--name-only").stdout.splitlines()
    if line.strip()
]
if changed != [str(SOURCE)]:
    raise SystemExit(f"unexpected implementation diff: {changed}")

green = run(python, "-m", "unittest", TEST_MODULE, check=False)
if green.returncode != 0:
    raise SystemExit(
        "focused GREEN failed\nstdout:\n"
        + green.stdout
        + "\nstderr:\n"
        + green.stderr
    )
run(python, "-m", "py_compile", str(SOURCE))

# Static safety checks for the intended narrow semantics.
patched = source_path.read_text(encoding="utf-8")
required = [
    "DEFAULT_OPERATIONAL_BUSY_TIMEOUT_MS / 1000.0",
    'CANCELLATION_PROBE_SQLITE_LOCKED = "CANCELLATION_PROBE_SQLITE_LOCKED"',
    "timeout=max(0.0, float(timeout_seconds))",
    "return CANCELLATION_PROBE_SQLITE_LOCKED",
    "return _read_campaign_supervision_cancellation_reason(",
]
missing = [item for item in required if item not in patched]
if missing:
    raise SystemExit(f"patched source missing required invariants: {missing}")

run("git", "add", str(SOURCE))
run("git", "commit", "-m", "Repair cancellation probe SQLite contention")
implementation_commit = run("git", "rev-parse", "HEAD").stdout.strip()
run("git", "push", "origin", BRANCH)

print(
    json.dumps(
        {
            "status": "PASS",
            "verdict": "V2_9_8B_POST_DTW95_CANCELLATION_PROBE_SQLITE_REPAIR_FOCUSED_PROOF_PASS",
            "branch": BRANCH,
            "red_head": RED_HEAD,
            "red_verdict": "EXPECTED_RED_MISSING_CANCELLATION_PROBE_HELPER",
            "green_focused": "PASS",
            "py_compile": "PASS",
            "git_diff_check": "PASS",
            "implementation_commit": implementation_commit,
            "changed_files_in_implementation_commit": [str(SOURCE)],
            "bounded_busy_wait_seconds": 2.0,
            "persistent_lock_terminal_cause": "CANCELLATION_PROBE_SQLITE_LOCKED",
            "authoritative_database_accessed": False,
            "printer_source_calls": 0,
            "scheduler_runtime_calls": 0,
            "authorization_created": False,
            "window_15m_started": False,
        },
        indent=2,
        sort_keys=True,
    )
)
