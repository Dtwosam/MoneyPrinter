from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

BASE = "48a4ef5005b5b8e45f40e96d0137deb033a2a0a9"
PRODUCTION = Path("src/printer_v1/operator_cli/campaign_supervision.py")
CLOSEOUT = Path(
    "docs/printer-v1-v2-9-8b-post-consumption-interrupted-four-token-"
    "lease-failure-cleanup-production-implementation-closeout.md"
)


def run(*args: str, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str((Path.cwd() / "src").resolve())
    result = subprocess.run(
        args,
        text=True,
        env=env,
        capture_output=capture,
    )
    if check and result.returncode != 0:
        if capture:
            print(result.stdout)
            print(result.stderr, file=sys.stderr)
        raise SystemExit(result.returncode)
    return result


def pytest(*tests: str, require_failure: bool = False) -> str:
    result = run(sys.executable, "-m", "pytest", "-q", *tests, check=False, capture=True)
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if require_failure:
        if result.returncode == 0:
            raise SystemExit("STOP: reviewed RED regression unexpectedly passed")
    elif result.returncode != 0:
        raise SystemExit(result.returncode)
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    return lines[-1] if lines else f"pytest_rc={result.returncode}"


def main() -> None:
    # Ephemeral branch may contain CI-only files, but product code must still be
    # byte-identical to the reviewed 48a4ef5 baseline before this repair.
    unchanged = run(
        "git", "diff", "--quiet", BASE, "--",
        str(PRODUCTION),
        "src/printer_v1/operator_cli/four_token_factory_adapter.py",
        "tests/test_v2_9_8b_interrupted_four_token_followup_repair.py",
        check=False,
    )
    if unchanged.returncode != 0:
        raise SystemExit("STOP: product baseline drift before second follow-up")

    import printer_v1.operator_cli.campaign_supervision as cs
    import printer_v1.operator_cli.four_token_factory_adapter as fa

    root = (Path.cwd() / "src").resolve()
    for module in (cs, fa):
        origin = Path(module.__file__).resolve()
        print(f"IMPORT={origin}")
        if not origin.is_relative_to(root):
            raise SystemExit(f"STOP: wrong import origin: {origin}")
    print("IMPORT_ORIGIN=PASS")

    red = pytest(
        "tests/test_v2_9_8b_20_sqlite_heartbeat_concurrency.py::"
        "TestProductionLockPatternAndRepair::"
        "test_many_heartbeats_under_concurrent_operational_writers",
        require_failure=True,
    )
    print(f"RED_EVIDENCE={red}")

    text = PRODUCTION.read_text(encoding="utf-8")
    start_marker = "    def _renewal_block_preflight(planned_block: float) -> None:\n"
    end_marker = "\n    def _failure_return(exc: BaseException) -> dict[str, Any]:\n"
    start = text.find(start_marker)
    if start < 0:
        raise SystemExit("STOP: renewal preflight start marker missing")
    end = text.find(end_marker, start)
    if end < 0:
        raise SystemExit("STOP: renewal preflight end marker missing")
    if text.find(start_marker, start + len(start_marker)) >= 0:
        raise SystemExit("STOP: multiple renewal preflight blocks found")

    replacement = '''    def _renewal_block_preflight(planned_block: float) -> None:
        planned = float(planned_block)
        remaining_deadline = renewal_deadline - time.monotonic()
        if (
            planned < LEASE_CONTENTION_MIN_BLOCK_SECONDS
            or remaining_deadline < LEASE_CONTENTION_MIN_BLOCK_SECONDS
            or planned > remaining_deadline
        ):
            raise sqlite3.OperationalError("database is locked")
        if previous_expiry_iso is None:
            raise CampaignSupervisionError(
                "lease renewal preflight has no prior expiry"
            )

        # The ledger re-read is itself a blocking action. Reserve enough
        # deadline and lease lifetime for the next requested block, then give
        # this re-read at most the existing 2s SQLite busy ceiling.
        prior_remaining_lease = (
            _parse(previous_expiry_iso) - _renewal_now()
        ).total_seconds()
        if prior_remaining_lease <= 0:
            raise CampaignSupervisionError(
                "operational campaign lease is expired"
            )
        preflight_timeout = min(
            SQLITE_BUSY_TIMEOUT_SECONDS,
            remaining_deadline - planned,
            prior_remaining_lease
            - LEASE_CONTENTION_REMAINING_SAFETY_SECONDS
            - planned,
        )
        if preflight_timeout < LEASE_CONTENTION_MIN_BLOCK_SECONDS:
            raise sqlite3.OperationalError("database is locked")

        preflight = _connect(
            db_path,
            read_only=True,
            busy_timeout_seconds=preflight_timeout,
        )
        try:
            current = _load_exact(
                preflight,
                supervision_id=supervision_id,
                campaign_id=campaign_id,
                configuration_id=configuration_id,
                run_id=run_id,
                owner_id=owner_id,
            )
            if str(current["supervision_state"]) != "ACTIVE":
                raise CampaignSupervisionError(
                    "campaign supervision is not renewable"
                )

            # The bounded re-read may itself have waited. Recompute all safety
            # predicates before the next BEGIN/sleep is permitted.
            remaining_deadline = renewal_deadline - time.monotonic()
            if (
                remaining_deadline < LEASE_CONTENTION_MIN_BLOCK_SECONDS
                or planned > remaining_deadline
            ):
                raise sqlite3.OperationalError("database is locked")
            remaining_lease = (
                _parse(str(current["lease_expires_at"])) - _renewal_now()
            ).total_seconds()
            if remaining_lease <= 0:
                raise CampaignSupervisionError(
                    "operational campaign lease is expired"
                )
            if (
                remaining_lease <= LEASE_CONTENTION_REMAINING_SAFETY_SECONDS
                or remaining_lease - planned
                <= LEASE_CONTENTION_REMAINING_SAFETY_SECONDS
            ):
                raise sqlite3.OperationalError("database is locked")
        finally:
            preflight.close()
'''
    PRODUCTION.write_text(text[:start] + replacement + text[end:], encoding="utf-8")
    run("git", "diff", "--check")

    isolated = pytest(
        "tests/test_v2_9_8b_20_sqlite_heartbeat_concurrency.py::"
        "TestProductionLockPatternAndRepair::"
        "test_many_heartbeats_under_concurrent_operational_writers"
    )
    print(f"ISOLATED_GREEN={isolated}")

    focused = pytest(
        "tests/test_v2_9_8b_lease_renewal_sqlite_contention_bound.py",
        "tests/test_v2_9_8b_interrupted_cycle2_parent_interrupt_cleanup.py",
        "tests/test_v2_9_8b_interrupted_four_token_followup_repair.py",
        "tests/test_v2_9_8b_20_sqlite_heartbeat_concurrency.py::TestProductionLockPatternAndRepair",
        "tests/test_v2_9_8b_four_token_gate_g_two_phase_terminal.py",
        "tests/test_v2_9_8b_shared_terminal_pre_lifecycle_zero_attempt.py",
        "tests/test_v2_9_8b_pre_admission_terminal_cleanup_repair.py",
    )
    print(f"FOCUSED_GREEN={focused}")

    run(
        sys.executable, "-m", "py_compile",
        str(PRODUCTION),
        "src/printer_v1/operator_cli/four_token_factory_adapter.py",
    )
    run("git", "diff", "--check")

    changed_product = run(
        "git", "diff", "--name-only", BASE, "--",
        "src", "tests", "migrations",
        capture=True,
    ).stdout.strip().splitlines()
    if changed_product != [str(PRODUCTION)]:
        raise SystemExit(f"STOP: unexpected product/test changes: {changed_product}")

    if not CLOSEOUT.is_file():
        raise SystemExit("STOP: production closeout missing")
    addition = f'''\n\n## Second follow-up repair — bounded preflight-read contention\n\nBaseline: `{BASE}`.\n\nThe corrected proof exposed one regression introduced by the first follow-up: the per-block safety re-read used a zero-timeout auxiliary SQLite reader and could convert a legitimate short concurrent writer commit into immediate `SQLITE_LOCK_CONTENTION`.\n\nThe second follow-up preserves the approved 15.0s hard renewal deadline, 15.0s remaining-lease safety margin, outer/inner caps, DB-first/file-second renewal authority, and fail-closed ownership/expiry checks. The auxiliary ledger re-read now receives only a bounded timeout that fits the same fixed deadline and the most recently proven lease expiry while reserving time for the next requested block. After the read returns, deadline and lease-safety predicates are recomputed before the next `BEGIN IMMEDIATE` or sleep may start. No global SQLite timeout, journal mode, Source Governor, Scheduler, recovery, or capability behavior changed.\n\nIsolated former regression: `{isolated}`.\n\nCorrected focused proof: `{focused}`.\n\n`py_compile` and `git diff --check`: PASS.\n\nThe CI runner contained no authoritative consumed-run database or live residue and performed no provider or Scheduler runtime work. The preceding operator-local corrected proof established the authoritative DB remained `c90376b9e26d0f2953a8d9b2fd5fee01d80ac4984510113e595fd1ccc3d9033d` with Cycle-2 attempt RUNNING, Scheduler job 2808 PENDING, supervision ACTIVE, and lease present. This repair does not authorize residue reconciliation.\n\nVerdict:\n\n`V2_9_8B_POST_CONSUMPTION_INTERRUPTED_FOUR_TOKEN_LEASE_FAILURE_CLEANUP_SECOND_FOLLOWUP_REPAIR_PASS`\n'''
    CLOSEOUT.write_text(CLOSEOUT.read_text(encoding="utf-8") + addition, encoding="utf-8")
    run("git", "diff", "--check")

    with Path("/tmp/second-followup-product.patch").open("w", encoding="utf-8") as handle:
        patch = run(
            "git", "diff", BASE, "--", str(CLOSEOUT), str(PRODUCTION),
            capture=True,
        ).stdout
        handle.write(patch)
    if not Path("/tmp/second-followup-product.patch").stat().st_size:
        raise SystemExit("STOP: empty product patch")
    print("SECOND_FOLLOWUP_PROOF=PASS")


if __name__ == "__main__":
    main()
