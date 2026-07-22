"""V2-9.7E.11 bounded live readiness-only cycle harness.

Runs EXACTLY ONE readiness-only cycle of the authoritative live operational
campaign owner against bounded free-public live sources. It reaches live Pump
origin acquisition, bounded secondary enrichment, merge and fixed gates, and a
disposable dry-run atomic handoff, then stops before any 15m/1h/4h/5m/promotion
work. It prints a redacted summary and performs terminal cleanup.

This harness is not a public command and is never imported by production code or
offline tests. It must not be rerun. No wallet, signing, funds, paid API, retry,
rotation, reconnect, successor or restart is involved.

Usage (operator-run, disposable DB is created and removed):

    python scripts/v2_9_7e_11_readiness_cycle.py
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from printer_v1.db.migrate import apply_migrations
from printer_v1.operator_cli.abstract_campaign_command import (
    AbstractCampaignCommand,
    CAMPAIGN_MODE,
    CENTRAL_SCHEDULER_OWNER,
    CampaignCeilings,
    OwnerPort,
    SOURCE_GOVERNOR_OWNER,
)
from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    READINESS_DURATION_CEILING_SECONDS,
    AuthoritativeLiveOperationalCampaignOwner,
    OneShotUrllibPumpTransport,
    OneShotUrllibSecondaryTransport,
)
from printer_v1.operator_cli.campaign_ownership import create_campaign_run
from printer_v1.operator_cli.campaign_persistence import (
    DB_MODE_PROOF_ISOLATED,
    create_campaign,
)

NOW = "2026-07-22T00:00:00+00:00"
CUTOFF = "2026-07-22T00:06:00+00:00"
SEED = "v2-9-7e-11-readiness-seed"
FREE_PUBLIC_SOLANA_RPC = "https://api.mainnet-beta.solana.com"


def _provenance() -> dict[str, object]:
    return {
        "git_head": "0" * 40,
        "git_tracked_tree_clean": True,
        "git_staged_changes_present": False,
        "git_unstaged_changes_present": False,
        "git_untracked_present": True,
        "git_provenance_captured_at": NOW,
    }


def _build_command(root: Path, db: str) -> AbstractCampaignCommand:
    configuration = {
        "token_capacity": 2,
        "ceilings": {
            "campaign_count": 1,
            "cycle_count": 1,
            "duration_seconds": int(READINESS_DURATION_CEILING_SECONDS),
            "source_calls": 45,
            "scheduler_work": 60,
            "storage_bytes": 8 * 1024 * 1024,
            "failures": 20,
        },
        "campaign_selection_seed": SEED,
        "report_directory_identity": "path-sha256:" + "c" * 64,
        "backup_preflight_references": {
            "preflight_status": "READY",
            "source_identity": "sha256:" + "a" * 64,
            "backup_sha256": "b" * 64,
            "required_migration": "032_campaign_ownership_schema.sql",
            "latest_migration": "036_pumpfun_finalized_origin_registry.sql",
        },
    }
    created = create_campaign(
        db,
        campaign_id="camp",
        configuration_id="cfg",
        configuration=configuration,
        launch_provenance=_provenance(),
        db_mode=DB_MODE_PROOF_ISOLATED,
        db_target_identity="iso",
        proof_source_db_identity="src",
        policy_version="v2-9.7e.11",
    )
    connection = sqlite3.connect(db)
    connection.execute("PRAGMA foreign_keys=ON")
    create_campaign_run(
        connection, campaign_id="camp", run_id="run", run_ordinal=1, now=NOW
    )
    with connection:
        connection.execute(
            """
            INSERT INTO printer_memory_factory_campaign_cycles(
                cycle_id, campaign_id, run_id, cycle_ordinal, cycle_state,
                created_at, updated_at
            ) VALUES ('cyc', 'camp', 'run', 1, 'PLANNED', ?, ?)
            """,
            (NOW, NOW),
        )
        connection.execute(
            "UPDATE printer_memory_factory_campaigns SET campaign_state='RUNNING'"
        )
        connection.execute(
            "UPDATE printer_memory_factory_campaign_runs SET run_state='RUNNING'"
        )
    connection.close()
    return AbstractCampaignCommand(
        mode=CAMPAIGN_MODE,
        db_path=db,
        db_target_identity="iso",
        campaign_id="camp",
        configuration_id="cfg",
        configuration_hash=str(created["configuration_hash"]),
        policy_version="v2-9.7e.11",
        token_capacity=2,
        ceilings=CampaignCeilings(
            campaign_count=1,
            cycle_count=1,
            duration_seconds=int(READINESS_DURATION_CEILING_SECONDS),
            source_calls=45,
            scheduler_work=60,
            storage_bytes=8 * 1024 * 1024,
            failures=20,
        ),
        report_directory=root,
        report_directory_identity="path-sha256:" + "c" * 64,
        launch_git_provenance=_provenance(),
        run_id="run",
        report_id="rep",
    )


def main() -> int:
    temp = tempfile.TemporaryDirectory()
    try:
        root = Path(temp.name)
        db = str(root / "readiness.sqlite3")
        apply_migrations(db)
        command = _build_command(root, db)

        owner = AuthoritativeLiveOperationalCampaignOwner()
        readiness = owner.run_readiness_only(
            command=command,
            pump_transport=OneShotUrllibPumpTransport(FREE_PUBLIC_SOLANA_RPC),
            secondary_transport=OneShotUrllibSecondaryTransport(),
            source_governor=OwnerPort(SOURCE_GOVERNOR_OWNER, True),
            central_scheduler=OwnerPort(CENTRAL_SCHEDULER_OWNER, True),
            selection_seed=SEED,
            cycle_id="cyc",
            cycle_cutoff=CUTOFF,
            evaluated_at=NOW,
        )
        # Redacted summary only: no raw payloads, mints, or pool addresses.
        print(json.dumps(readiness.summary, indent=2, sort_keys=True))
        print("readiness_status:", readiness.status)
        print("cancelled_dry_run_jobs:", readiness.cancelled_dry_run_jobs)
        print("replay_new_source_calls:", readiness.replay_new_source_calls)
        return 0
    finally:
        temp.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
