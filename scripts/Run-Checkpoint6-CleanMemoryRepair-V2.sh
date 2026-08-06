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
