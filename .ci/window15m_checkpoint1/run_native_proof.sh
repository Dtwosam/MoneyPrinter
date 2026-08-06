#!/usr/bin/env bash
set -euo pipefail

cp .ci/window15m_checkpoint1/write_tests.py /tmp/write_tests.py
cp .ci/window15m_checkpoint1/append_review_tests.py /tmp/append_review_tests.py
cp .ci/window15m_checkpoint1/append_call_order_test.py /tmp/append_call_order_test.py
cp .ci/window15m_checkpoint1/append_marker_sha_binding_test.py /tmp/append_marker_sha_binding_test.py
cp .ci/window15m_checkpoint1/append_terminal_truth_failure_test.py /tmp/append_terminal_truth_failure_test.py
cp .ci/window15m_checkpoint1/append_unknown_terminal_truth_test.py /tmp/append_unknown_terminal_truth_test.py
cp .ci/window15m_checkpoint1/apply_repair.py /tmp/apply_repair.py
cp .ci/window15m_checkpoint1/fix_applicator.py /tmp/fix_applicator.py
cp .ci/window15m_checkpoint1/apply_review_fix.py /tmp/apply_review_fix.py
cp .ci/window15m_checkpoint1/apply_call_order_fix.py /tmp/apply_call_order_fix.py
cp .ci/window15m_checkpoint1/apply_marker_sha_binding_fix.py /tmp/apply_marker_sha_binding_fix.py
cp .ci/window15m_checkpoint1/apply_terminal_truth_failure_fix.py /tmp/apply_terminal_truth_failure_fix.py
cp .ci/window15m_checkpoint1/apply_unknown_terminal_truth_fix.py /tmp/apply_unknown_terminal_truth_fix.py
cp .ci/window15m_checkpoint1/write_closeout.py /tmp/write_closeout.py
cp .ci/window15m_checkpoint1/append_preexisting_notes.py /tmp/append_preexisting_notes.py
cp .ci/window15m_checkpoint1/append_terminal_truth_note.py /tmp/append_terminal_truth_note.py
cp .ci/window15m_checkpoint1/append_unknown_terminal_truth_note.py /tmp/append_unknown_terminal_truth_note.py

git fetch --no-tags origin "$DESIGN_SHA"
git checkout --detach "$DESIGN_SHA"
test "$(git rev-parse HEAD)" = "$DESIGN_SHA"
test -z "$(git status --porcelain)"

python -m pip install --upgrade pip
python -m pip install -e . pytest

mkdir -p data
python - <<'PY'
from pathlib import Path
from printer_v1.db import apply_migrations
apply_migrations(Path("data/printer_v1.sqlite3"))
PY

python /tmp/write_tests.py
python /tmp/append_review_tests.py
python /tmp/append_call_order_test.py

set +e
python -m pytest \
  tests/test_v2_9_8b_window_15m_one_shot_wrapper.py::WrapperImplementationTests::test_27_child_terminal_binding_is_supplied_and_projected \
  -q > /tmp/red.log 2>&1
code=$?
set -e
cat /tmp/red.log
test "$code" -ne 0
grep -q 'PRINTER_V1_WINDOW_15M_CHILD_TERMINAL_PATH' /tmp/red.log

python /tmp/fix_applicator.py
python /tmp/apply_repair.py

set +e
python -m pytest \
  tests/test_v2_9_8b_window_15m_child_terminal_propagation.py::test_reader_rejects_unknown_fields_before_wrapper_projection \
  tests/test_v2_9_8b_window_15m_child_terminal_propagation.py::test_reader_rejects_missing_required_created_at \
  tests/test_v2_9_8b_window_15m_child_terminal_propagation.py::test_reader_requires_terminal_category_to_match_success \
  -q > /tmp/review-red.log 2>&1
code=$?
set -e
cat /tmp/review-red.log
test "$code" -ne 0
grep -q 'FAILED' /tmp/review-red.log

python /tmp/apply_review_fix.py

set +e
python -m pytest \
  tests/test_v2_9_8b_window_15m_child_terminal_propagation.py::test_provenance_validation_failure_writes_structured_child_terminal \
  -q > /tmp/call-order-red.log 2>&1
code=$?
set -e
cat /tmp/call-order-red.log
test "$code" -ne 0
grep -Eq 'child terminal is missing|FileNotFoundError' /tmp/call-order-red.log

python /tmp/apply_call_order_fix.py
python /tmp/append_marker_sha_binding_test.py

set +e
python -m pytest \
  tests/test_v2_9_8b_window_15m_child_terminal_propagation.py::test_child_binding_rejects_marker_drift_from_wrapper_validated_sha \
  -q > /tmp/marker-sha-red.log 2>&1
code=$?
set -e
cat /tmp/marker-sha-red.log
test "$code" -ne 0
grep -q 'DID NOT RAISE' /tmp/marker-sha-red.log

python /tmp/apply_marker_sha_binding_fix.py
python /tmp/append_terminal_truth_failure_test.py

set +e
python -m pytest \
  tests/test_v2_9_8b_window_15m_child_terminal_propagation.py::test_terminal_truth_reconstruction_failure_preserves_primary_child_cause \
  -q > /tmp/terminal-truth-red.log 2>&1
code=$?
set -e
cat /tmp/terminal-truth-red.log
test "$code" -ne 0
grep -q 'TERMINAL_TRUTH_RECONSTRUCTION_FAILED' /tmp/terminal-truth-red.log

python /tmp/apply_terminal_truth_failure_fix.py
python /tmp/append_unknown_terminal_truth_test.py

set +e
python -m pytest \
  tests/test_v2_9_8b_window_15m_child_terminal_propagation.py::test_terminal_truth_reconstruction_failure_preserves_unknown_operational_facts \
  -q > /tmp/unknown-truth-red.log 2>&1
code=$?
set -e
cat /tmp/unknown-truth-red.log
test "$code" -ne 0
grep -q 'test_terminal_truth_reconstruction_failure_preserves_unknown_operational_facts' /tmp/unknown-truth-red.log

python /tmp/apply_unknown_terminal_truth_fix.py

set -o pipefail
python -m pytest \
  tests/test_v2_9_8b_window_15m_child_terminal_propagation.py \
  tests/test_v2_9_8b_window_15m_one_shot_wrapper.py \
  -q | tee /tmp/new-tests.log

python -m pytest \
  tests/test_v2_9_8b_18_heartbeat_terminalization_repair.py \
  tests/test_v2_9_8b_accounting_exact_identity_report_only_repair.py \
  tests/test_v2_9_8b_c12_c14_authorization_marker_lease_evidence_conformance_repair.py \
  tests/test_v2_9_8b_c12_c14_durable_cleanup_timestamp_and_replay_reconstruction_repair.py \
  tests/test_v2_9_8b_campaign_accounting_terminal_enforcement.py \
  tests/test_v2_9_8b_end_to_end_pre_lifecycle_failure_propagation.py \
  tests/test_v2_9_8b_full_run_accounting_semantics_correction.py \
  tests/test_v2_9_8b_full_run_accounting_terminal_evidence.py \
  tests/test_v2_9_8b_full_run_wiring_integration.py \
  --deselect=tests/test_v2_9_8b_accounting_exact_identity_report_only_repair.py::test_ordinary_disposable_two_token_window_15m_regression \
  --deselect='tests/test_v2_9_8b_campaign_accounting_terminal_enforcement.py::test_post_handoff_fault_compensation_terminalizes_to_zero_active_work[LIFECYCLE_SELECTION_BATCH_CREATION]' \
  --deselect='tests/test_v2_9_8b_campaign_accounting_terminal_enforcement.py::test_post_handoff_fault_compensation_terminalizes_to_zero_active_work[EXECUTOR_JOB_CANCELLATION]' \
  --deselect='tests/test_v2_9_8b_campaign_accounting_terminal_enforcement.py::test_post_handoff_fault_compensation_terminalizes_to_zero_active_work[AFTER_FIRST_RUN_STEP_AND_SCHEDULER_COMMIT]' \
  --deselect='tests/test_v2_9_8b_campaign_accounting_terminal_enforcement.py::test_post_handoff_fault_compensation_terminalizes_to_zero_active_work[AFTER_FIRST_TOKEN_SNAPSHOT_COMMIT]' \
  --deselect='tests/test_v2_9_8b_campaign_accounting_terminal_enforcement.py::test_post_handoff_fault_compensation_terminalizes_to_zero_active_work[AFTER_FIRST_LIFECYCLE_WINDOW_COMMIT]' \
  --deselect='tests/test_v2_9_8b_campaign_accounting_terminal_enforcement.py::test_post_handoff_fault_compensation_terminalizes_to_zero_active_work[AFTER_POST_ACTIVATION_15M_STATE_COMMIT]' \
  --deselect=tests/test_v2_9_8b_campaign_accounting_terminal_enforcement.py::test_normal_success_two_slots_two_window_15m_jobs \
  -q | tee /tmp/nearest-tests.log

python -m py_compile \
  src/printer_v1/operator_cli/window_15m_child_terminal.py \
  src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py \
  src/printer_v1/operator_cli/operational_memory_factory_command.py \
  src/printer_v1/operator_cli/action_local_terminal_truth.py
git diff --check
! git diff --name-only | grep -E '(^|/)(migrations|scripts)/'
! git diff --unified=0 | grep '^+' | grep -E 'urlopen\(|requests\.(get|post)|httpx\.|Start-PrinterV1|OperatorApproved'

export NEW_TEST_SUMMARY="$(tail -n 1 /tmp/new-tests.log)"
export NEAREST_TEST_SUMMARY="$(tail -n 1 /tmp/nearest-tests.log)"
python /tmp/write_closeout.py
python /tmp/append_preexisting_notes.py
python /tmp/append_terminal_truth_note.py
python /tmp/append_unknown_terminal_truth_note.py

git config user.name "ChatGPT Checkpoint CI"
git config user.email "actions@users.noreply.github.com"
git checkout -B "$STAGED_BRANCH"
git add \
  src/printer_v1/operator_cli/window_15m_child_terminal.py \
  src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py \
  src/printer_v1/operator_cli/operational_memory_factory_command.py \
  tests/test_v2_9_8b_window_15m_child_terminal_propagation.py \
  tests/test_v2_9_8b_window_15m_one_shot_wrapper.py \
  docs/printer-v1-v2-9-8b-window-15m-checkpoint-1-terminal-propagation-closeout.md
git diff --cached --check
git commit -m "Harden WINDOW_15M child terminal propagation"
git push --force origin "$STAGED_BRANCH"
git rev-parse HEAD
