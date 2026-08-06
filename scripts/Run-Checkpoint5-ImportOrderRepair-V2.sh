#!/usr/bin/env bash
set -euo pipefail

BRANCH="agent/v2-9-8b-window-15m-checkpoint-5-scheduler-ownership-lifecycle-activation"
ORIGINAL_RUNNER="scripts/Run-Checkpoint5-ImportOrderRepair.sh"
THIS_RUNNER="scripts/Run-Checkpoint5-ImportOrderRepair-V2.sh"
STALE_TEST="tests/test_v2_9_8b_20_sqlite_heartbeat_concurrency.py::TestMigrationDiscoverySleepDoesNotHoldLock::test_settle_sleep_releases_write_transaction"

ROOT="$(git rev-parse --show-toplevel)"
TMP_SCRIPT="$(mktemp "${TMPDIR:-/tmp}/checkpoint5-repair-v2.XXXXXX.sh")"
cleanup() {
  rm -f "$TMP_SCRIPT"
}
trap cleanup EXIT

git -C "$ROOT" fetch origin "$BRANCH"
git -C "$ROOT" show "origin/$BRANCH:$ORIGINAL_RUNNER" > "$TMP_SCRIPT"

python3 - "$TMP_SCRIPT" "$THIS_RUNNER" "$STALE_TEST" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
this_runner = sys.argv[2]
stale_test = sys.argv[3]
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
  {stale_test} \\
  -q > "$TMP/preexisting-stale-test.log" 2>&1
STALE_STATUS=$?
set -e
cat "$TMP/preexisting-stale-test.log"
if [[ "$STALE_STATUS" -eq 0 ]]; then
  echo "Expected the documented stale test to fail on the untouched branch head" >&2
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

focused_tail = '''  tests/test_v2_9_7e_11_authoritative_live_operational_campaign.py::NaturalOperationalLifecycleProofTests::test_token_local_failure_isolates_and_does_not_corrupt_peer \\
  -q
'''
focused_replacement = f'''  tests/test_v2_9_7e_11_authoritative_live_operational_campaign.py::NaturalOperationalLifecycleProofTests::test_token_local_failure_isolates_and_does_not_corrupt_peer \\
  --deselect={stale_test} \\
  -q
'''
replace_exact(
    focused_tail,
    focused_replacement,
    "deselect only the documented stale test",
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

v2_runner = Path({this_runner!r})
if not v2_runner.is_file():
    raise SystemExit("V2 repair runner is unexpectedly missing")
v2_runner.unlink()

for path in Path("src").rglob("*.py"):
'''
replace_exact(
    runner_removal,
    runner_removal_replacement,
    "remove both temporary repair runners",
)

manifest_entry = '''    "D scripts/Run-Checkpoint5-ImportOrderRepair.sh",
}
'''
manifest_replacement = f'''    "D scripts/Run-Checkpoint5-ImportOrderRepair.sh",
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
echo "CHECKPOINT5_IMPORT_ORDER_REPAIR_GREEN_PASS"
echo "CHECKPOINT5_FOCUSED_PROOF_PASS"
'''
replace_exact(
    terminal_markers,
    terminal_replacement,
    "add explicit stale-test disposition marker",
)

path.write_text(text, encoding="utf-8")
PY

chmod +x "$TMP_SCRIPT"
bash "$TMP_SCRIPT"
