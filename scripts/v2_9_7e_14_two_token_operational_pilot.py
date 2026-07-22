"""V2-9.7E.14 unregistered pilot-only operational runner script.

Operator-run entry point that drives exactly ONE bounded two-token live
operational pilot through the committed E.11 owner and the E.14 pilot runner,
under real, uncompressed lifecycle timing. It is NOT registered in
``pyproject.toml`` and is NOT the future V2-9.8 public PowerShell command.

Running this script performs a live operational pilot and consumes the single
operator pilot authorization. E.14 does not authorize running it; it exists so a
later, separately authorized pilot lane has a committed, reviewed entry point.

Usage (operator-run, all paths explicit and disposable/isolated):

    python scripts/v2_9_7e_14_two_token_operational_pilot.py \
        --operator-approved \
        --persistent-source-db PATH \
        --target-db PATH --backup-db PATH --restore-rehearsal-db PATH \
        --report-dir DIR --lock-path PATH \
        --stdout-log PATH --stderr-log PATH \
        --execution-id ID --git-provenance-json JSON
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from typing import Iterable

from printer_v1.operator_cli.two_token_operational_pilot_runner import (
    PilotPaths,
    PilotRunnerError,
    run_two_token_operational_pilot,
)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run one bounded two-token live operational pilot (unregistered)."
    )
    parser.add_argument("--operator-approved", action="store_true")
    parser.add_argument("--persistent-source-db", required=True)
    parser.add_argument("--target-db", required=True)
    parser.add_argument("--backup-db", required=True)
    parser.add_argument("--restore-rehearsal-db", required=True)
    parser.add_argument("--report-dir", required=True)
    parser.add_argument("--lock-path", required=True)
    parser.add_argument("--stdout-log", required=True)
    parser.add_argument("--stderr-log", required=True)
    parser.add_argument("--execution-id", required=True)
    parser.add_argument("--selection-seed", default="v2-9-7e-14-pilot-seed")
    parser.add_argument("--git-provenance-json", required=True)
    parser.add_argument("--cycle-cutoff", default=None)
    parser.add_argument("--evaluated-at", default=None)
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        if not args.operator_approved:
            raise PilotRunnerError("--operator-approved is required")
        provenance = json.loads(args.git_provenance_json)
        paths = PilotPaths.of(
            persistent_source_db=args.persistent_source_db,
            target_db=args.target_db,
            backup_db=args.backup_db,
            restore_rehearsal_db=args.restore_rehearsal_db,
            report_dir=args.report_dir,
            one_proof_lock_path=args.lock_path,
            stdout_log_path=args.stdout_log,
            stderr_log_path=args.stderr_log,
        )
        now = _iso_now()
        report = run_two_token_operational_pilot(
            paths,
            execution_id=args.execution_id,
            launch_provenance=provenance,
            selection_seed=args.selection_seed,
            cycle_cutoff=args.cycle_cutoff or now,
            evaluated_at=args.evaluated_at or now,
            now=now,
        )
        # Redacted terminal summary only: no mints, pools, or raw payloads.
        print(json.dumps(report, indent=2, sort_keys=True, default=str))
        return 0 if report.get("run_status") != "FAILED" else 1
    except Exception as exc:  # noqa: BLE001 - fail closed with a redacted reason
        print(
            json.dumps(
                {
                    "status": "PILOT_BLOCKED",
                    "error": f"{type(exc).__name__}: {exc}",
                    "source_calls": 0,
                    "restart_created": False,
                    "successor_created": False,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 1


if __name__ == "__main__":  # pragma: no cover - operator-run only
    raise SystemExit(main())
