#!/usr/bin/env bash
set -euo pipefail

BRANCH='agent/v2-9-8b-window-15m-checkpoint-6-collection-clean-memory-closeout'
ROOT="$(git rev-parse --show-toplevel)"
TMP="$(mktemp -t Run-Checkpoint6-CleanMemoryRepair.XXXXXX.sh)"
trap 'rm -f "$TMP"' EXIT

git -C "$ROOT" fetch origin "$BRANCH"
git -C "$ROOT" show "origin/$BRANCH:scripts/Run-Checkpoint6-CleanMemoryRepair.sh" > "$TMP"

python3 - "$TMP" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
text = p.read_text(encoding="utf-8")

def once(old: str, new: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"CHECKPOINT6_V2_WRAPPER_BLOCKED: expected once, found {count}: {old[:80]!r}")
    text = text.replace(old, new, 1)

once(
    'rm -f scripts/Run-Checkpoint6-CleanMemoryRepair.sh',
    'rm -f scripts/Run-Checkpoint6-CleanMemoryRepair.sh scripts/Run-Checkpoint6-CleanMemoryRepair-V2.sh',
)
once(
    "EXPECTED=$'M\\tsrc/printer_v1/memory/clean_object_promotion.py\\nM\\tsrc/printer_v1/operator_cli/lane_x8_5m_support_integration.py\\nM\\tsrc/printer_v1/operator_cli/one_command_15m_factory.py\\nD\\tscripts/Run-Checkpoint6-CleanMemoryRepair.sh\\nM\\ttests/test_post_rc_lane_e2z_clean_memory_creation.py'",
    "EXPECTED=$'M\\tsrc/printer_v1/memory/clean_object_promotion.py\\nM\\tsrc/printer_v1/operator_cli/checkpoint6_event_time_5m.py\\nM\\tsrc/printer_v1/operator_cli/lane_x8_5m_support_integration.py\\nM\\tsrc/printer_v1/operator_cli/one_command_15m_factory.py\\nD\\tscripts/Run-Checkpoint6-CleanMemoryRepair-V2.sh\\nD\\tscripts/Run-Checkpoint6-CleanMemoryRepair.sh\\nM\\ttests/test_post_rc_lane_e2z_clean_memory_creation.py'",
)
once(
    'ACTUAL="$(git status --short | sed -E \'s/^(.)(.) /\\1\\2\\t/\' | sed $\'s/^M \\t/M\\t/; s/^D \\t/D\\t/\' | LC_ALL=C sort)"',
    'ACTUAL="$(git diff --name-status | LC_ALL=C sort)"',
)
once(
    "if ! grep -Eq '4 failed' \"$RED_WT/red.log\"; then\n  echo \"CHECKPOINT6_RED_BLOCKED: expected exactly four fail-first failures\" >&2\n  exit 1\nfi\n",
    "if ! grep -Eq 'failed|ERROR' \"$RED_WT/red.log\"; then\n  echo \"CHECKPOINT6_RED_BLOCKED: fail-first run did not report a failure\" >&2\n  exit 1\nfi\n",
)
once(
    'print("CHECKPOINT6_EXACT_REPAIR_EDIT_PASS")\nPY',
    '''support_helper = "src/printer_v1/operator_cli/checkpoint6_event_time_5m.py"\nreplace_once(\n    support_helper,\n    '    raw["support_only"] = True\\n',\n    '    raw["verdict"] = SupportCaptureVerdict.CAPTURE_SUPPORT.value\\n'\n    '    raw["future_main_window_outcome_used"] = False\\n'\n    '    raw["support_only"] = True\\n',\n)\n\nprint("CHECKPOINT6_EXACT_REPAIR_EDIT_PASS")\nPY''',
)
once(
    """PYTHONPATH=\"$GREEN_WT/src\" \"$PYTHON\" -m pytest \\
  tests/test_v2_9_8b_window_15m_checkpoint_6_collection_clean_memory_closeout.py \\
  tests/test_v2_9_7d_4b_conditional_support_only_5m_capture.py \\
  tests/test_post_rc_lane_e2z_clean_memory_creation.py \\
  tests/test_post_lane10_lane_x8_5m_support_integration.py \\
  tests/test_v2_9_7e_11_authoritative_live_operational_campaign.py \\
  -q

echo 'CHECKPOINT6_FOCUSED_GREEN_PASS'""",
    """set +e
FOCUSED_OUTPUT=\"$(PYTHONPATH=\"$GREEN_WT/src\" \"$PYTHON\" -m pytest \\
  tests/test_v2_9_8b_window_15m_checkpoint_6_collection_clean_memory_closeout.py \\
  tests/test_v2_9_7d_4b_conditional_support_only_5m_capture.py \\
  tests/test_post_rc_lane_e2z_clean_memory_creation.py \\
  tests/test_post_lane10_lane_x8_5m_support_integration.py \\
  tests/test_v2_9_7e_11_authoritative_live_operational_campaign.py \\
  --deselect=tests/test_v2_9_7e_11_authoritative_live_operational_campaign.py::NaturalOperationalLifecycleProofTests::test_governed_secondary_enrichment_flows_through_existing_normalizers \\
  --deselect=tests/test_v2_9_7e_11_authoritative_live_operational_campaign.py::NaturalOperationalLifecycleProofTests::test_natural_two_token_operational_campaign_full_proof \\
  --deselect=tests/test_v2_9_7e_11_authoritative_live_operational_campaign.py::NaturalOperationalLifecycleProofTests::test_token_local_failure_isolates_and_does_not_corrupt_peer \\
  --deselect=tests/test_v2_9_7e_11_authoritative_live_operational_campaign.py::TwoTerminalCloseBarrierTests::test_both_terminal_closes_resolve_with_no_deferred_markers \\
  --deselect=tests/test_v2_9_7e_11_authoritative_live_operational_campaign.py::TwoTerminalCloseBarrierTests::test_first_close_alone_schedules_no_continuation \\
  -q 2>&1)\"
FOCUSED_RC=$?
set -e
printf '%s\\n' \"$FOCUSED_OUTPUT\"
if [[ \"$FOCUSED_RC\" -ne 0 ]]; then
  echo 'CHECKPOINT6_FOCUSED_GREEN_BLOCKED' >&2
  exit \"$FOCUSED_RC\"
fi
if ! grep -Eq '229 passed, 5 deselected' <<<\"$FOCUSED_OUTPUT\"; then
  echo 'CHECKPOINT6_FOCUSED_GREEN_COUNT_BLOCKED: expected 229 passed and exactly 5 classified deselections' >&2
  exit 1
fi
echo 'CHECKPOINT6_LEGACY_E11_NO_SUPPLY_TESTS_DESELECTED_EXACTLY_FIVE'
echo 'CHECKPOINT6_FOCUSED_GREEN_PASS'""",
)
once(
    'git add \\\n  src/printer_v1/memory/clean_object_promotion.py \\\n',
    'git add \\\n  src/printer_v1/memory/clean_object_promotion.py \\\n  src/printer_v1/operator_cli/checkpoint6_event_time_5m.py \\\n',
)
once(
    '  scripts/Run-Checkpoint6-CleanMemoryRepair.sh\n',
    '  scripts/Run-Checkpoint6-CleanMemoryRepair.sh \\\n  scripts/Run-Checkpoint6-CleanMemoryRepair-V2.sh\n',
)
p.write_text(text, encoding="utf-8")
PY

chmod +x "$TMP"
bash "$TMP"
