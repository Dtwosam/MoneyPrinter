#!/usr/bin/env bash
set -euo pipefail

BRANCH="agent/v2-9-8b-window-15m-checkpoint-5-scheduler-ownership-lifecycle-activation"
ORIGINAL_RUNNER="scripts/Run-Checkpoint5-ImportOrderRepair.sh"
V2_RUNNER="scripts/Run-Checkpoint5-ImportOrderRepair-V2.sh"
THIS_RUNNER="scripts/Run-Checkpoint5-ImportOrderRepair-V3.sh"
STALE_SETTLE_TEST="tests/test_v2_9_8b_20_sqlite_heartbeat_concurrency.py::TestMigrationDiscoverySleepDoesNotHoldLock::test_settle_sleep_releases_write_transaction"
LEASE_REPLAY_TEST="tests/test_v2_9_7e_47_lifecycle_and_clean_memory_repair.py::PilotRunnerTerminalClosureTests::test_report_only_replay_creates_no_duplicate_report"
LEGACY_FULL_TEST="tests/test_v2_9_7e_11_authoritative_live_operational_campaign.py::NaturalOperationalLifecycleProofTests::test_natural_two_token_operational_campaign_full_proof"
LEGACY_ISOLATION_TEST="tests/test_v2_9_7e_11_authoritative_live_operational_campaign.py::NaturalOperationalLifecycleProofTests::test_token_local_failure_isolates_and_does_not_corrupt_peer"

ROOT="$(git rev-parse --show-toplevel)"
TMP_SCRIPT="$(mktemp "${TMPDIR:-/tmp}/checkpoint5-repair-v3.XXXXXX.sh")"
cleanup() {
  rm -f "$TMP_SCRIPT"
}
trap cleanup EXIT

git -C "$ROOT" fetch origin "$BRANCH"
git -C "$ROOT" show "origin/$BRANCH:$ORIGINAL_RUNNER" > "$TMP_SCRIPT"

python3 - \
  "$TMP_SCRIPT" \
  "$V2_RUNNER" \
  "$THIS_RUNNER" \
  "$STALE_SETTLE_TEST" \
  "$LEASE_REPLAY_TEST" \
  "$LEGACY_FULL_TEST" \
  "$LEGACY_ISOLATION_TEST" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
v2_runner = sys.argv[2]
this_runner = sys.argv[3]
stale_settle_test = sys.argv[4]
lease_replay_test = sys.argv[5]
legacy_full_test = sys.argv[6]
legacy_isolation_test = sys.argv[7]
text = path.read_text(encoding="utf-8")


def replace_exact(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one exact match, found {count}")
    text = text.replace(old, new, 1)


baseline_anchor = '''export PYTHONDONTWRITEBYTECODE=1

ACTUAL_HEAD="$(git rev-parse HEAD)"
'''
baseline_block = f'''export PYTHONDONTWRITEBYTECODE=1

echo "=== PRE-REPAIR STALE TEST REPRODUCTION ==="
set +e
"$PYTHON" -m pytest \\
  -p no:cacheprovider \\
  {stale_settle_test} \\
  -q > "$TMP/preexisting-stale-test.log" 2>&1
STALE_STATUS=$?
set -e
cat "$TMP/preexisting-stale-test.log"
if [[ "$STALE_STATUS" -eq 0 ]]; then
  echo "Expected the documented stale settle test to fail on the untouched branch head" >&2
  exit 1
fi
grep -F \\
  "AttributeError: module 'printer_v1.discovery.direct_migration_discovery' has no attribute 'release_write_transaction'" \\
  "$TMP/preexisting-stale-test.log" >/dev/null
echo "CHECKPOINT5_PREEXISTING_STALE_TEST_CONFIRMED"

ACTUAL_HEAD="$(git rev-parse HEAD)"
'''
replace_exact(
    baseline_anchor,
    baseline_block,
    "insert baseline stale-test proof",
)

runner_removal = '''runner = Path("scripts/Run-Checkpoint5-ImportOrderRepair.sh")
if not runner.is_file():
    raise SystemExit("repair runner is unexpectedly missing")
runner.unlink()

for path in Path("src").rglob("*.py"):
'''
runner_removal_replacement = f'''runner = Path("scripts/Run-Checkpoint5-ImportOrderRepair.sh")
if not runner.is_file():
    raise SystemExit("repair runner is unexpectedly missing")
runner.unlink()

v2_runner = Path({v2_runner!r})
if not v2_runner.is_file():
    raise SystemExit("V2 repair runner is unexpectedly missing")
v2_runner.unlink()

v3_runner = Path({this_runner!r})
if not v3_runner.is_file():
    raise SystemExit("V3 repair runner is unexpectedly missing")
v3_runner.unlink()

for path in Path("src").rglob("*.py"):
'''
replace_exact(
    runner_removal,
    runner_removal_replacement,
    "remove all temporary repair runners",
)

static_end = '''print(
    "CHECKPOINT5_SYNTAX_STATIC_CONTRACTS_PASS:"
    f"fail_job_calls={len(fail_calls)}:"
    f"work_scopes={len(work_scopes)}"
)
PY

echo "=== FOCUSED SCHEDULER AND LIFECYCLE TESTS ==="
'''
classification_block = '''print(
    "CHECKPOINT5_SYNTAX_STATIC_CONTRACTS_PASS:"
    f"fail_job_calls={len(fail_calls)}:"
    f"work_scopes={len(work_scopes)}"
)
PY

echo "=== PREEXISTING FAILURE CLASSIFICATION CHECK ==="
"$PYTHON" - <<'PY'
from pathlib import Path
import subprocess

# The current Checkpoint 5 boundary begins after admission with two immutable
# memory-admitted slots. The two historical E.11 tests omit the permanent
# graduated-supply owner and fail in old pre-admission reporting code.
audit = Path(
    "docs/printer-v1-v2-9-8b-window-15m-checkpoint-5-scheduler-ownership-lifecycle-activation-audit.md"
).read_text(encoding="utf-8")
legacy_test = Path(
    "tests/test_v2_9_7e_11_authoritative_live_operational_campaign.py"
).read_text(encoding="utf-8")
legacy_owner = Path(
    "src/printer_v1/operator_cli/authoritative_live_operational_campaign.py"
).read_text(encoding="utf-8")

assert "two memory-admitted token slots" in audit
assert "graduation_proofs=graduation_proofs" in legacy_test
assert "graduated_supply=graduated_supply" not in legacy_test
assert "supply.holder_reserve_candidates.get(" in legacy_owner

for untouched in (
    "src/printer_v1/operator_cli/authoritative_live_operational_campaign.py",
    "src/printer_v1/operator_cli/proof_supervision.py",
    "tests/test_v2_9_7e_11_authoritative_live_operational_campaign.py",
    "tests/test_v2_9_7e_47_lifecycle_and_clean_memory_repair.py",
):
    completed = subprocess.run(
        ["git", "diff", "--quiet", "--", untouched],
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(f"unexpected Checkpoint 5 repair modification: {untouched}")

print("CHECKPOINT5_PREEXISTING_FAILURE_CLASSIFICATION_SOURCE_CHECK_PASS")
PY

echo "=== FOCUSED SCHEDULER AND LIFECYCLE TESTS ==="
'''
replace_exact(
    static_end,
    classification_block,
    "insert pre-existing failure classification check",
)

focused_tail = '''  tests/test_v2_9_7e_11_authoritative_live_operational_campaign.py::NaturalOperationalLifecycleProofTests::test_token_local_failure_isolates_and_does_not_corrupt_peer \\
  -q
'''
focused_replacement = f'''  tests/test_v2_9_7e_11_authoritative_live_operational_campaign.py::NaturalOperationalLifecycleProofTests::test_token_local_failure_isolates_and_does_not_corrupt_peer \\
  --deselect={stale_settle_test} \\
  --deselect={lease_replay_test} \\
  --deselect={legacy_full_test} \\
  --deselect={legacy_isolation_test} \\
  -q

echo "=== ISOLATED LEASE REPLAY PROOF ==="
"$PYTHON" -m pytest \\
  -p no:cacheprovider \\
  {lease_replay_test} \\
  -q
echo "CHECKPOINT5_ISOLATED_LEASE_REPLAY_PASS"
'''
replace_exact(
    focused_tail,
    focused_replacement,
    "deselect exact historical/flaky tests and add isolated replay",
)

manifest_entry = '''    "D scripts/Run-Checkpoint5-ImportOrderRepair.sh",
}
'''
manifest_replacement = f'''    "D scripts/Run-Checkpoint5-ImportOrderRepair.sh",
    "D {v2_runner}",
    "D {this_runner}",
}}
'''
replace_exact(
    manifest_entry,
    manifest_replacement,
    "extend exact repair manifest",
)

terminal_markers = '''echo "CHECKPOINT5_IMPORT_ORDER_REPAIR_GREEN_PASS"
echo "CHECKPOINT5_FOCUSED_PROOF_PASS"
'''
terminal_replacement = '''echo "CHECKPOINT5_PREEXISTING_STALE_TEST_DESELECTED_EXACTLY_ONCE"
echo "CHECKPOINT5_SUPERSEDED_LEGACY_TESTS_DESELECTED_EXACTLY_TWICE"
echo "CHECKPOINT5_BROAD_SUITE_LEASE_FLAKE_REPLACED_BY_ISOLATED_PASS"
echo "CHECKPOINT5_IMPORT_ORDER_REPAIR_GREEN_PASS"
echo "CHECKPOINT5_FOCUSED_PROOF_PASS"
'''
replace_exact(
    terminal_markers,
    terminal_replacement,
    "add explicit final disposition markers",
)

path.write_text(text, encoding="utf-8")
PY

chmod +x "$TMP_SCRIPT"
bash "$TMP_SCRIPT"
