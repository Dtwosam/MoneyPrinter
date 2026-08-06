#!/usr/bin/env bash
set -euo pipefail

BRANCH="agent/v2-9-8b-window-15m-checkpoint-5-scheduler-ownership-lifecycle-activation"
RED_COMMIT="b4635540a5b24c381a8d5dd71c87c2ee523d9fd7"
BASELINE="421e409628a0db443f1c417835a9d5b06bbdc834"
SCRIPT_PATH="scripts/Run-Checkpoint5-ImportOrderRepair.sh"

ROOT="$(git rev-parse --show-toplevel)"
PYTHON="$ROOT/.venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
  echo "Missing project interpreter: $PYTHON" >&2
  exit 1
fi

git -C "$ROOT" fetch origin "$BRANCH"
REMOTE_HEAD="$(git -C "$ROOT" rev-parse "origin/$BRANCH")"

git -C "$ROOT" merge-base --is-ancestor "$RED_COMMIT" "$REMOTE_HEAD"

TMP="$(mktemp -d "${TMPDIR:-/tmp}/printer-checkpoint5-repair.XXXXXX")"
cleanup() {
  git -C "$ROOT" worktree remove --force "$TMP" >/dev/null 2>&1 || true
  rm -rf "$TMP"
}
trap cleanup EXIT

git -C "$ROOT" worktree add --detach "$TMP" "$REMOTE_HEAD"
cd "$TMP"

export PYTHONPATH="$PWD/src:$PWD/tests${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONDONTWRITEBYTECODE=1

ACTUAL_HEAD="$(git rev-parse HEAD)"
if [[ "$ACTUAL_HEAD" != "$REMOTE_HEAD" ]]; then
  echo "Detached repair head mismatch" >&2
  exit 1
fi

"$PYTHON" - <<'PY'
from pathlib import Path


def replace_exact(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one exact match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")


combined = Path("src/printer_v1/discovery/combined_executor.py")

old_direct = '''        if "direct" in fixtures.provider_failures_injected:
            fail_id = self._store_failure(
                connection,
                usage,
                source_name="solana_rpc",
                request_kind="pumpfun_create_event_subscription",
                failure_type=fixtures.provider_failures_injected["direct"],
                now=now,
            )
            req = self._governed_request(
                connection,
                usage,
                source_name="solana_rpc",
                request_kind="pumpfun_create_event_subscription",
                now=now,
            )
'''
new_direct = '''        if "direct" in fixtures.provider_failures_injected:
            # Checkpoint 3: persist the governed request identity before the
            # linked provider failure so request/failure causality is durable.
            req = self._governed_request(
                connection,
                usage,
                source_name="solana_rpc",
                request_kind="pumpfun_create_event_subscription",
                now=now,
            )
            fail_id = self._store_failure(
                connection,
                usage,
                source_name="solana_rpc",
                request_kind="pumpfun_create_event_subscription",
                failure_type=fixtures.provider_failures_injected["direct"],
                now=now,
            )
'''
replace_exact(
    combined,
    old_direct,
    new_direct,
    "direct request-before-failure repair",
)

old_handoff = '''        fixtures = self.fixtures
        mint = candidate.mint
        pool = candidate.market_identity.rsplit(":", 1)[-1]
        token_row = connection.execute(
'''
new_handoff = '''        fixtures = self.fixtures
        mint = candidate.mint
        pool = candidate.market_identity.rsplit(":", 1)[-1]

        # Checkpoint 3: an existing pair address may be reused only when its
        # canonical token owner is this mint. A nullable legacy base-token field
        # is accepted only when canonical token_id ownership still matches.
        existing_pair_owner = connection.execute(
            "SELECT token_id, base_token_mint "
            "FROM printer_pairs WHERE pair_address = ?",
            (pool,),
        ).fetchone()
        if existing_pair_owner is not None:
            existing_token_owner = connection.execute(
                "SELECT id FROM printer_tokens WHERE token_mint = ?",
                (mint,),
            ).fetchone()
            base_token_mint = existing_pair_owner["base_token_mint"]
            if (
                existing_token_owner is None
                or int(existing_pair_owner["token_id"])
                != int(existing_token_owner["id"])
                or (
                    base_token_mint is not None
                    and str(base_token_mint) != mint
                )
            ):
                raise CombinedDiscoveryError("PAIR_TOKEN_IDENTITY_MISMATCH")

        token_row = connection.execute(
'''
replace_exact(
    combined,
    old_handoff,
    new_handoff,
    "pair/token ownership repair",
)

permanent = Path(
    "src/printer_v1/discovery/permanent_discovery_availability.py"
)
replace_exact(
    permanent,
    '    return key == root or key.startswith(f"{root}")\n',
    '    return key == root or key.startswith(f"{root}-")\n',
    "delimiter-bound request scope repair",
)

package_init = Path("src/printer_v1/discovery/__init__.py")
old_install = '''from printer_v1.discovery.checkpoint3_guards import install_checkpoint3_guards


# Package-local, idempotent installation of the three deterministic Checkpoint 3
# repairs. Direct submodule imports execute this package initializer first.
install_checkpoint3_guards()


'''
replace_exact(
    package_init,
    old_install,
    "",
    "remove eager Checkpoint 3 installer",
)

guards = Path("src/printer_v1/discovery/checkpoint3_guards.py")
if not guards.is_file():
    raise SystemExit("Checkpoint 3 guard installer is unexpectedly missing")
guards.unlink()

runner = Path("scripts/Run-Checkpoint5-ImportOrderRepair.sh")
if not runner.is_file():
    raise SystemExit("repair runner is unexpectedly missing")
runner.unlink()

for path in Path("src").rglob("*.py"):
    if "checkpoint3_guards" in path.read_text(encoding="utf-8"):
        raise SystemExit(f"stale checkpoint3_guards reference: {path}")

print("CHECKPOINT5_EXACT_REPAIR_EDIT_PASS")
PY

echo "=== IMPORT-ORDER GREEN PROOF ==="
"$PYTHON" -m pytest \
  -p no:cacheprovider \
  tests/test_v2_9_8b_checkpoint5_import_order_repair.py \
  -q

echo "=== CHECKPOINT 3 CONTRACT REGRESSIONS ==="
"$PYTHON" -m pytest \
  -p no:cacheprovider \
  tests/test_v2_9_8b_window_15m_checkpoint_3_discovery_selection_accounting.py \
  -q

echo "=== CHECKPOINT 5 STATIC CONTRACTS ==="
"$PYTHON" - <<'PY'
import ast
from pathlib import Path

FILES = (
    "src/printer_v1/operator_cli/origin_lifecycle_campaign.py",
    "src/printer_v1/operator_cli/one_command_15m_factory.py",
    "src/printer_v1/operator_cli/campaign_ownership.py",
    "src/printer_v1/operator_cli/campaign_full_run_accounting.py",
    "src/printer_v1/operator_cli/campaign_active_work.py",
    "src/printer_v1/operator_cli/campaign_supervision.py",
    "src/printer_v1/operator_cli/unified_terminal_closure.py",
    "src/printer_v1/scheduler/scheduler.py",
    "src/printer_v1/sources/campaign_six_unit_accounting.py",
    "src/printer_v1/sources/measured_transport.py",
    "src/printer_v1/discovery/combined_executor.py",
    "src/printer_v1/discovery/permanent_discovery_availability.py",
)

sources = {}
for filename in FILES:
    source = Path(filename).read_text(encoding="utf-8")
    compile(source, filename, "exec")
    sources[filename] = source

factory_name = "src/printer_v1/operator_cli/one_command_15m_factory.py"
factory_source = sources[factory_name]
factory_tree = ast.parse(factory_source, filename=factory_name)

window_values = []
for node in factory_tree.body:
    if not isinstance(node, ast.Assign):
        continue
    if any(
        isinstance(target, ast.Name) and target.id == "WINDOW_KIND"
        for target in node.targets
    ) and isinstance(node.value, ast.Constant):
        window_values.append(node.value.value)
assert window_values == ["WINDOW_15M"], window_values

fail_calls = []
for node in ast.walk(factory_tree):
    if not isinstance(node, ast.Call):
        continue
    if (
        isinstance(node.func, ast.Name) and node.func.id == "fail_job"
    ) or (
        isinstance(node.func, ast.Attribute) and node.func.attr == "fail_job"
    ):
        fail_calls.append(node)
assert fail_calls
for call in fail_calls:
    keywords = [item for item in call.keywords if item.arg == "max_retries"]
    assert len(keywords) == 1
    value = keywords[0].value
    assert (
        isinstance(value, ast.Constant)
        and type(value.value) is int
        and value.value == 0
    )

ownership_name = "src/printer_v1/operator_cli/campaign_ownership.py"
ownership_tree = ast.parse(sources[ownership_name], filename=ownership_name)
work_scopes = None
for node in ownership_tree.body:
    if not isinstance(node, ast.Assign):
        continue
    if any(
        isinstance(target, ast.Name) and target.id == "WORK_SCOPES"
        for target in node.targets
    ) and isinstance(node.value, (ast.Tuple, ast.List)):
        work_scopes = tuple(
            item.value for item in node.value.elts
            if isinstance(item, ast.Constant)
        )
assert work_scopes == (
    "DISCOVERY_SELECTION",
    "FIRST_15M_HANDOFF",
    "WINDOW_LIFECYCLE",
    "TERMINAL_CLEANUP",
), work_scopes

supervision = sources[
    "src/printer_v1/operator_cli/campaign_supervision.py"
]
for required in (
    '"automatic_retries": 0',
    '"resume_created": False',
    '"successor_created": False',
    '"restart_created": False',
    '"new_child_work_allowed": False',
    '"lease_released": True',
    '"active_owned_work_after": active_after',
):
    assert required in supervision, required

combined = sources["src/printer_v1/discovery/combined_executor.py"]
request_position = combined.index(
    'req = self._governed_request(',
    combined.index('if "direct" in fixtures.provider_failures_injected:'),
)
failure_position = combined.index(
    'fail_id = self._store_failure(',
    combined.index('if "direct" in fixtures.provider_failures_injected:'),
)
assert request_position < failure_position
assert "PAIR_TOKEN_IDENTITY_MISMATCH" in combined

permanent = sources[
    "src/printer_v1/discovery/permanent_discovery_availability.py"
]
assert 'key.startswith(f"{root}-")' in permanent
assert 'key.startswith(f"{root}")' not in permanent

assert not Path("src/printer_v1/discovery/checkpoint3_guards.py").exists()
assert "checkpoint3_guards" not in Path(
    "src/printer_v1/discovery/__init__.py"
).read_text(encoding="utf-8")

print(
    "CHECKPOINT5_SYNTAX_STATIC_CONTRACTS_PASS:"
    f"fail_job_calls={len(fail_calls)}:"
    f"work_scopes={len(work_scopes)}"
)
PY

echo "=== FOCUSED SCHEDULER AND LIFECYCLE TESTS ==="
"$PYTHON" -m pytest \
  -p no:cacheprovider \
  tests/test_v2_9_8b_full_run_wiring_integration.py \
  tests/test_v2_9_8b_full_run_accounting_semantics_correction.py \
  tests/test_v2_9_8b_full_run_accounting_terminal_evidence.py \
  tests/test_v2_9_8b_terminal_safety_accounting_finalization.py \
  tests/test_v2_9_8b_20_sqlite_heartbeat_concurrency.py \
  tests/test_v2_9_8b_18_heartbeat_terminalization_repair.py \
  tests/test_v2_9_7e_47_lifecycle_and_clean_memory_repair.py \
  tests/test_v2_9_7e_11_authoritative_live_operational_campaign.py::NaturalOperationalLifecycleProofTests::test_natural_two_token_operational_campaign_full_proof \
  tests/test_v2_9_7e_11_authoritative_live_operational_campaign.py::NaturalOperationalLifecycleProofTests::test_token_local_failure_isolates_and_does_not_corrupt_peer \
  -q

echo "=== DIFF CHECK ==="
git diff --check "$BASELINE"..HEAD
git diff --check

echo "=== INTENDED CHANGE MANIFEST ==="
git status --short --untracked-files=all

"$PYTHON" - <<'PY'
from pathlib import Path
import subprocess

expected = {
    "D src/printer_v1/discovery/checkpoint3_guards.py",
    "M src/printer_v1/discovery/__init__.py",
    "M src/printer_v1/discovery/combined_executor.py",
    "M src/printer_v1/discovery/permanent_discovery_availability.py",
    "D scripts/Run-Checkpoint5-ImportOrderRepair.sh",
}
completed = subprocess.run(
    ["git", "status", "--short", "--untracked-files=all"],
    capture_output=True,
    text=True,
    check=True,
)
actual = {line.rstrip() for line in completed.stdout.splitlines() if line.strip()}
if actual != expected:
    raise SystemExit(
        "unexpected repair manifest\n"
        f"expected={sorted(expected)}\nactual={sorted(actual)}"
    )
print("CHECKPOINT5_INTENDED_CHANGE_MANIFEST_PASS")
PY

git add -A
git commit -m "Repair Checkpoint 5 import order"
FINAL_SHA="$(git rev-parse HEAD)"

git push origin "HEAD:refs/heads/$BRANCH"

echo "=== FINAL REPAIR COMMIT ==="
echo "$FINAL_SHA"
echo "CHECKPOINT5_IMPORT_ORDER_REPAIR_GREEN_PASS"
echo "CHECKPOINT5_FOCUSED_PROOF_PASS"
