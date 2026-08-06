#!/usr/bin/env bash
set -euo pipefail

cp .ci/window15m_checkpoint2/write_tests.py /tmp/checkpoint2_write_tests.py
cp .ci/window15m_checkpoint2/apply_repair.py /tmp/checkpoint2_apply_repair.py
cp .ci/window15m_checkpoint2/write_closeout.py /tmp/checkpoint2_write_closeout.py

git fetch --no-tags origin "$BASE_SHA"
git checkout --detach "$BASE_SHA"
test "$(git rev-parse HEAD)" = "$BASE_SHA"
test -z "$(git status --porcelain)"

python -m pip install --upgrade pip
python -m pip install -e . pytest

# Some nearest historical tests expect a disposable repository-default DB.
mkdir -p data
python - <<'PY'
from pathlib import Path
from printer_v1.db import apply_migrations
apply_migrations(Path("data/printer_v1.sqlite3"))
PY

python /tmp/checkpoint2_write_tests.py

red_nodes=(
  "tests/test_v2_9_8b_window_15m_checkpoint_2_preflight_initialization.py::test_authorized_database_drift_blocks_before_any_campaign_write"
  "tests/test_v2_9_8b_window_15m_checkpoint_2_preflight_initialization.py::test_cycle_insert_failure_rolls_back_entire_initialization_graph"
  "tests/test_v2_9_8b_window_15m_checkpoint_2_preflight_initialization.py::test_authorized_database_is_revalidated_while_first_write_lock_is_held"
  "tests/test_v2_9_8b_window_15m_checkpoint_2_preflight_initialization.py::test_initialization_records_all_exact_insert_and_update_identities"
  "tests/test_v2_9_8b_window_15m_checkpoint_2_preflight_initialization.py::test_supervision_connection_failure_removes_only_newly_created_lock"
)

for index in "${!red_nodes[@]}"; do
  node="${red_nodes[$index]}"
  log="/tmp/checkpoint2-red-$((index + 1)).log"
  set +e
  python -m pytest "$node" -q >"$log" 2>&1
  code=$?
  set -e
  cat "$log"
  test "$code" -ne 0
  test "$(grep -c 'FAILED' "$log")" -ge 1
done

# Confirm one unrelated stale historical node against the untouched baseline.
# Its fixture supplies only migration 031, while the current migration owner
# correctly requires a contiguous 001..NNN catalogue before SQLite execution.
preexisting_node="tests/test_v2_9_7d_2a_campaign_persistence.py::CampaignPersistenceTests::test_failed_migration_leaves_no_partial_campaign_schema"
set +e
python -m pytest "$preexisting_node" -q > /tmp/checkpoint2-preexisting.log 2>&1
preexisting_code=$?
set -e
cat /tmp/checkpoint2-preexisting.log
test "$preexisting_code" -ne 0
grep -q "invalid canonical migration catalogue" /tmp/checkpoint2-preexisting.log
grep -q "missing ordinals \[1\]" /tmp/checkpoint2-preexisting.log
grep -q "out-of-range ordinals \[31\]" /tmp/checkpoint2-preexisting.log

python /tmp/checkpoint2_apply_repair.py

set -o pipefail
python -m pytest \
  tests/test_v2_9_8b_window_15m_checkpoint_2_preflight_initialization.py \
  -q | tee /tmp/checkpoint2-focused.log

mapfile -t nearest_tests < <(
  find tests -maxdepth 1 -type f -name 'test_*.py' | sort | grep -E \
    '(operational_memory_factory|campaign_persistence|campaign_ownership|campaign_supervision|operational_campaign_recovery|git_provenance_authorization|pre_authorization_migration|operational_database_target_binding|window_15m_concrete_composition)'
)
test "${#nearest_tests[@]}" -gt 0
printf '%s\n' "${nearest_tests[@]}" | tee /tmp/checkpoint2-nearest-files.log
python -m pytest "${nearest_tests[@]}" -q \
  --deselect "$preexisting_node" | tee /tmp/checkpoint2-nearest.log

python -m py_compile \
  src/printer_v1/operator_cli/campaign_persistence.py \
  src/printer_v1/operator_cli/operational_memory_factory_command.py \
  src/printer_v1/operator_cli/campaign_supervision.py

git diff --check
! git diff --name-only | grep -E '(^|/)(migrations|scripts)/'
! git diff --unified=0 | grep '^+' | grep -E \
  'urlopen\(|requests\.(get|post)|httpx\.|Start-PrinterV1|OperatorApproved'

export FOCUSED_TEST_SUMMARY="$(tail -n 1 /tmp/checkpoint2-focused.log)"
export NEAREST_TEST_SUMMARY="$(tail -n 1 /tmp/checkpoint2-nearest.log)"
export NEAREST_TEST_FILES="$(cat /tmp/checkpoint2-nearest-files.log)"
export PREEXISTING_TEST_SUMMARY="$(tail -n 1 /tmp/checkpoint2-preexisting.log)"
python /tmp/checkpoint2_write_closeout.py

git config user.name "ChatGPT Checkpoint CI"
git config user.email "actions@users.noreply.github.com"
git checkout -B "$STAGED_BRANCH"
git add \
  src/printer_v1/operator_cli/campaign_persistence.py \
  src/printer_v1/operator_cli/operational_memory_factory_command.py \
  src/printer_v1/operator_cli/campaign_supervision.py \
  tests/test_v2_9_8b_window_15m_checkpoint_2_preflight_initialization.py \
  docs/printer-v1-v2-9-8b-window-15m-checkpoint-2-preflight-initialization-closeout.md

git diff --cached --check
test "$(git diff --cached --name-only | wc -l | tr -d ' ')" = "5"
git commit -m "Harden WINDOW_15M preflight initialization"
git push --force origin "$STAGED_BRANCH"
git rev-parse HEAD
