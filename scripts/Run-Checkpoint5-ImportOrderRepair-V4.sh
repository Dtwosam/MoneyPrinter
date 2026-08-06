#!/usr/bin/env bash
set -euo pipefail

BRANCH="agent/v2-9-8b-window-15m-checkpoint-5-scheduler-ownership-lifecycle-activation"
V3_RUNNER="scripts/Run-Checkpoint5-ImportOrderRepair-V3.sh"
V4_RUNNER="scripts/Run-Checkpoint5-ImportOrderRepair-V4.sh"

ROOT="$(git rev-parse --show-toplevel)"
TMP_SCRIPT="$(mktemp "${TMPDIR:-/tmp}/checkpoint5-repair-v4.XXXXXX.sh")"
cleanup() {
  rm -f "$TMP_SCRIPT"
}
trap cleanup EXIT

git -C "$ROOT" fetch origin "$BRANCH"
git -C "$ROOT" show "origin/$BRANCH:$V3_RUNNER" > "$TMP_SCRIPT"

python3 - "$TMP_SCRIPT" "$V4_RUNNER" <<'PY_V4_FIX'
from pathlib import Path
import sys

path = Path(sys.argv[1])
v4_runner = sys.argv[2]
text = path.read_text(encoding="utf-8")


def replace_exact(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one exact match, found {count}")
    text = text.replace(old, new, 1)


replace_exact(
    '  "$LEGACY_ISOLATION_TEST" <<\'PY\'\n',
    '  "$LEGACY_ISOLATION_TEST" <<\'PY_V3_WRAPPER\'\n',
    "use unique outer V3 heredoc delimiter",
)

replace_exact(
    'path.write_text(text, encoding="utf-8")\n'
    'PY\n\n'
    'chmod +x "$TMP_SCRIPT"\n'
    'bash "$TMP_SCRIPT"\n',
    'path.write_text(text, encoding="utf-8")\n'
    'PY_V3_WRAPPER\n\n'
    'chmod +x "$TMP_SCRIPT"\n'
    'bash "$TMP_SCRIPT"\n',
    "close unique outer V3 heredoc delimiter",
)

runner_removal = '''v3_runner = Path({this_runner!r})
if not v3_runner.is_file():
    raise SystemExit("V3 repair runner is unexpectedly missing")
v3_runner.unlink()

for path in Path("src").rglob("*.py"):
'''
runner_removal_replacement = f'''v3_runner = Path({{this_runner!r}})
if not v3_runner.is_file():
    raise SystemExit("V3 repair runner is unexpectedly missing")
v3_runner.unlink()

v4_runner = Path({v4_runner!r})
if not v4_runner.is_file():
    raise SystemExit("V4 repair runner is unexpectedly missing")
v4_runner.unlink()

for path in Path("src").rglob("*.py"):
'''
replace_exact(
    runner_removal,
    runner_removal_replacement,
    "remove V4 temporary runner",
)

replace_exact(
    '    "D {this_runner}",\n'
    '}}\n'
    "'''\n",
    '    "D {this_runner}",\n'
    f'    "D {v4_runner}",\n'
    '}}\n'
    "'''\n",
    "extend final manifest for V4 runner",
)

path.write_text(text, encoding="utf-8")
PY_V4_FIX

bash -n "$TMP_SCRIPT"
echo "CHECKPOINT5_V3_HEREDOC_REPAIR_SYNTAX_PASS"
chmod +x "$TMP_SCRIPT"
bash "$TMP_SCRIPT"
