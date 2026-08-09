from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

REPO = Path.home() / "Developer" / "MoneyPrinter"
BRANCH = "agent/v2-9-8b-post-dtw94-holder-projection-implementation"
RED_HEAD = "1ccbedd4fcbf24d27df09f06f569aeaf9f7257ae"
SOURCE = REPO / "src/printer_v1/operator_cli/authoritative_live_operational_campaign.py"
FOCUSED_PATTERN = "test_v2_9_8b_post_dtw94_holder_projection.py"
ADJACENT_PATTERN = "test_v2_9_7e_45_pilot_input_readiness.py"


def run(*args: str, check: bool = True, capture: bool = True) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO / "src")
    return subprocess.run(
        list(args),
        cwd=REPO,
        env=env,
        text=True,
        capture_output=capture,
        check=check,
    )


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run("git", *args, check=check)


def unittest(pattern: str) -> subprocess.CompletedProcess[str]:
    return run(
        str(REPO / ".venv/bin/python"),
        "-m",
        "unittest",
        "discover",
        "-s",
        "tests",
        "-p",
        pattern,
        "-v",
        check=False,
    )


def blocked(phase: str, error: str) -> None:
    print(
        json.dumps(
            {
                "status": "BLOCKED",
                "phase": phase,
                "error": error,
                "printer_source_calls": 0,
                "scheduler_runtime_calls": 0,
                "authoritative_database_accessed": False,
                "authorization_created": False,
                "window_15m_started": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    raise SystemExit(3)


if not REPO.is_dir():
    blocked("PRECHECK", f"repository unavailable: {REPO}")
if not (REPO / ".venv/bin/python").is_file():
    blocked("PRECHECK", "repository Python interpreter unavailable")

# Never trample tracked operator work.
if git("diff", "--quiet", "--no-ext-diff", "--", check=False).returncode != 0:
    blocked("PRECHECK", "tracked worktree is not clean")
if git("diff", "--cached", "--quiet", "--no-ext-diff", "--", check=False).returncode != 0:
    blocked("PRECHECK", "tracked index is not clean")

phase = "ALIGN"
try:
    fetched = git("fetch", "origin", BRANCH)
    remote_head = git("rev-parse", "FETCH_HEAD").stdout.strip()
    if remote_head != RED_HEAD:
        blocked(phase, f"remote implementation RED head drifted: {remote_head}")
    git("switch", "-C", BRANCH, "FETCH_HEAD")
    if git("rev-parse", "HEAD").stdout.strip() != RED_HEAD:
        blocked(phase, "local implementation head mismatch")

    phase = "VERIFY_RED"
    red = unittest(FOCUSED_PATTERN)
    red_output = (red.stdout or "") + (red.stderr or "")
    expected_names = (
        "test_concentrated_holder_evidence_is_complete_but_not_future_holder_pass",
        "test_extreme_holder_evidence_is_complete_but_not_future_holder_pass",
    )
    if red.returncode == 0:
        blocked(phase, "focused regression unexpectedly passed before production repair")
    if "FAILED (failures=2)" not in red_output:
        blocked(phase, "RED failure shape was not exactly two assertion failures")
    if any(name not in red_output for name in expected_names):
        blocked(phase, "RED output did not name both adverse-holder regression tests")
    if "ERROR" in red_output:
        blocked(phase, "RED run contained a test error rather than only expected failures")

    phase = "PATCH"
    text = SOURCE.read_text(encoding="utf-8")

    function_anchor = "def _holder_observation_context(\n"
    if text.count(function_anchor) != 1:
        blocked(phase, "holder observation context anchor count mismatch")
    helper = '''def _holder_condition_passes(\n    fact: Mapping[str, Any] | None,\n) -> bool:\n    """True only when usable holder evidence carries a favorable condition."""\n    holder_fact = dict(fact or {})\n    if not bool(holder_fact.get("eligible")):\n        return False\n    label = str(\n        holder_fact.get("holder_condition")\n        or holder_fact.get("holder_concentration_label")\n        or "HOLDER_CONCENTRATION_UNKNOWN"\n    )\n    return label in {\n        "HOLDER_CONCENTRATION_PASS",\n        "HOLDER_CONCENTRATION_HEALTHY",\n    }\n\n\n'''
    text = text.replace(function_anchor, helper + function_anchor, 1)

    old_projection = '    holder_actually_eligible = bool(holder_fact.get("eligible"))'
    new_projection = (
        '    holder_evidence_usable = bool(holder_fact.get("eligible"))\n'
        '    holder_actually_eligible = _holder_condition_passes(holder_fact)'
    )
    if text.count(old_projection) != 1:
        blocked(phase, "holder projection assignment count mismatch")
    text = text.replace(old_projection, new_projection, 1)

    old_status = '''        holder_evidence_status = (\n            "COMPLETE"\n            if holder_actually_eligible\n            else str(\n'''
    new_status = '''        holder_evidence_status = (\n            "COMPLETE"\n            if holder_evidence_usable\n            else str(\n'''
    if text.count(old_status) != 1:
        blocked(phase, "holder evidence completeness projection count mismatch")
    text = text.replace(old_status, new_status, 1)

    old_readiness = '                    actual_holder = bool(fact.get("eligible"))'
    new_readiness = '                    actual_holder = _holder_condition_passes(fact)'
    if text.count(old_readiness) != 1:
        blocked(phase, "memory readiness holder projection count mismatch")
    text = text.replace(old_readiness, new_readiness, 1)

    SOURCE.write_text(text, encoding="utf-8")

    # The activation invariant must remain in place; this repair fixes projection,
    # not the fail-closed consistency check.
    activation_text = (REPO / "src/printer_v1/discovery/memory_observation_activation.py").read_text(
        encoding="utf-8"
    )
    if 'MemoryObservationActivationError("FULLY_ELIGIBLE_WITHOUT_HOLDER_PASS")' not in activation_text:
        raise RuntimeError("activation consistency invariant changed unexpectedly")

    phase = "VERIFY_GREEN_FOCUSED"
    green = unittest(FOCUSED_PATTERN)
    if green.returncode != 0:
        raise RuntimeError((green.stdout or "") + (green.stderr or ""))

    phase = "VERIFY_ADJACENT"
    adjacent_path = REPO / "tests" / ADJACENT_PATTERN
    if not adjacent_path.is_file():
        raise RuntimeError(f"adjacent pilot-input readiness test missing: {ADJACENT_PATTERN}")
    adjacent = unittest(ADJACENT_PATTERN)
    if adjacent.returncode != 0:
        raise RuntimeError((adjacent.stdout or "") + (adjacent.stderr or ""))

    phase = "VERIFY_STATIC"
    compiled = run(
        str(REPO / ".venv/bin/python"),
        "-m",
        "py_compile",
        str(SOURCE.relative_to(REPO)),
        check=False,
    )
    if compiled.returncode != 0:
        raise RuntimeError((compiled.stdout or "") + (compiled.stderr or ""))
    if git("diff", "--check", check=False).returncode != 0:
        raise RuntimeError("git diff --check failed")
    changed = [
        line.strip()
        for line in git("diff", "--name-only").stdout.splitlines()
        if line.strip()
    ]
    expected_changed = [
        "src/printer_v1/operator_cli/authoritative_live_operational_campaign.py"
    ]
    if changed != expected_changed:
        raise RuntimeError(f"unexpected working-tree diff: {changed}")

    phase = "COMMIT"
    git("add", expected_changed[0])
    git("commit", "-m", "Repair holder condition projection semantics")
    commit = git("rev-parse", "HEAD").stdout.strip()
    git("push", "origin", f"HEAD:{BRANCH}")

    print(
        json.dumps(
            {
                "status": "PASS",
                "verdict": "V2_9_8B_POST_DTW94_HOLDER_PROJECTION_IMPLEMENTATION_FOCUSED_PROOF_PASS",
                "branch": BRANCH,
                "red_head": RED_HEAD,
                "red_verdict": "EXPECTED_RED_TWO_ADVERSE_HOLDER_ASSERTIONS",
                "green_focused": "PASS",
                "adjacent_pilot_input_readiness": "PASS",
                "py_compile": "PASS",
                "git_diff_check": "PASS",
                "implementation_commit": commit,
                "changed_files_in_implementation_commit": expected_changed,
                "activation_invariant_preserved": True,
                "printer_source_calls": 0,
                "scheduler_runtime_calls": 0,
                "authoritative_database_accessed": False,
                "authorization_created": False,
                "window_15m_started": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
except SystemExit:
    raise
except Exception as exc:
    # Return the branch to the committed RED state if the production edit has not
    # been committed. Never leave an unverified source mutation behind.
    try:
        if git("diff", "--quiet", "--no-ext-diff", "--", check=False).returncode != 0:
            git("restore", "--source=HEAD", "--", str(SOURCE.relative_to(REPO)), check=False)
    except Exception:
        pass
    blocked(phase, f"{type(exc).__name__}:{exc}")
