from __future__ import annotations

from datetime import datetime, timezone
import json
import sqlite3

from printer_v1.db import apply_migrations
from printer_v1.operator_cli import one_command_15m_factory as factory
from printer_v1.operator_cli import one_token_4h_runtime
from printer_v1.operator_cli import standard_4h_progression


NOW = datetime(2026, 9, 4, 20, 50, tzinfo=timezone.utc)
CAMPAIGN_ID = "validator-campaign"
CAMPAIGN_RUN_ID = "validator-run"
FACTORY_RUN_ID = "validator-factory"
CYCLE_1 = "validator-cycle-1"
CYCLE_2 = "validator-cycle-2"


def _provenance() -> dict[str, object]:
    return {
        "git_head": "f" * 40,
        "git_tracked_tree_clean": True,
        "git_staged_changes_present": False,
        "git_unstaged_changes_present": False,
        "git_untracked_present": True,
        "git_provenance_captured_at": NOW.isoformat(),
    }


def _seed(tmp_path):
    db = tmp_path / "multicycle-validator.sqlite3"
    apply_migrations(db)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    config = {
        "campaign_id": CAMPAIGN_ID,
        "campaign_run_id": CAMPAIGN_RUN_ID,
        "cycle_id": CYCLE_1,
        "configuration_id": "validator-config",
        "four_token_proof": True,
        "standard_four_hour_campaign": True,
        "continuous_four_hour": True,
        "git_provenance": _provenance(),
    }
    conn.execute(
        "INSERT INTO printer_memory_factory_campaigns("
        "campaign_id,campaign_state,db_mode,db_target_identity,policy_version) "
        "VALUES (?,?,?,?,?)",
        (
            CAMPAIGN_ID,
            "RUNNING",
            "OPERATIONAL_PERSISTENT",
            "db-validator",
            "policy-validator",
        ),
    )
    conn.execute(
        "INSERT INTO printer_memory_factory_runs("
        "run_id,run_status,window_kind,db_mode,config_hash,config_json,"
        "started_at,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (
            FACTORY_RUN_ID,
            "RUNNING",
            "WINDOW_15M",
            "OPERATIONAL_PERSISTENT",
            "a" * 64,
            json.dumps(config, sort_keys=True),
            NOW.isoformat(),
            NOW.isoformat(),
            NOW.isoformat(),
        ),
    )
    conn.execute(
        "INSERT INTO printer_memory_factory_campaign_runs("
        "run_id,campaign_id,run_ordinal,run_state,authoritative_run_id,"
        "created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
        (
            CAMPAIGN_RUN_ID,
            CAMPAIGN_ID,
            1,
            "RUNNING",
            FACTORY_RUN_ID,
            NOW.isoformat(),
            NOW.isoformat(),
        ),
    )
    for ordinal, cycle_id in enumerate((CYCLE_1, CYCLE_2), start=1):
        conn.execute(
            "INSERT INTO printer_memory_factory_campaign_cycles("
            "cycle_id,campaign_id,run_id,cycle_ordinal,cycle_state,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (
                cycle_id,
                CAMPAIGN_ID,
                CAMPAIGN_RUN_ID,
                ordinal,
                "PLANNED",
                NOW.isoformat(),
                NOW.isoformat(),
            ),
        )
    conn.commit()
    return db, conn, config


def _validation(*, complete: bool, cycle_id: str) -> dict[str, object]:
    return {
        "enabled": True,
        "complete": complete,
        "reasons": [] if complete else [f"{cycle_id}:incomplete"],
        "per_token": [],
        "eligible_window_details": [],
        "expected_continuation_count": 0,
        "progression_attempt_id": f"attempt:{cycle_id}",
        "aggregate_state": "HANDOFF_COMMITTED" if complete else "RUNNING",
        "requires_review": not complete,
        "active_owned_four_hour_work": 0 if complete else 1,
        "nonterminal_owned_four_hour_windows": 0 if complete else 1,
        "window_count": 0,
    }


def test_final_report_requires_standard_4h_terminal_truth_for_both_cycles(
    tmp_path, monkeypatch
) -> None:
    _db, conn, config = _seed(tmp_path)
    calls: list[str] = []

    def validate(_connection, **kwargs):
        cycle_id = str(kwargs["cycle_id"])
        calls.append(cycle_id)
        return _validation(complete=(cycle_id == CYCLE_1), cycle_id=cycle_id)

    monkeypatch.setattr(
        factory, "_standard_campaign_four_hour_terminal_validation", validate
    )

    report = factory._final_report(
        conn,
        run_id=FACTORY_RUN_ID,
        config=config,
        discovery={"selection_handoff_report": {}},
        before=factory._counts(conn),
        stop_reason=factory.STOP_COMPLETED,
        started_at=NOW.isoformat(),
    )

    assert calls == [CYCLE_1, CYCLE_2]
    validation = report["standard_four_hour_terminal_validation"]
    assert validation["complete"] is False
    assert validation["per_cycle"][CYCLE_1]["complete"] is True
    assert validation["per_cycle"][CYCLE_2]["complete"] is False
    assert report["run_status"] == "SAFE_STOPPED"
    assert report["stop_reason"] == factory.STOP_TERMINAL_4H
    conn.close()


def test_cycle_validator_ignores_peer_cycle_long_continuation_steps(
    tmp_path, monkeypatch
) -> None:
    _db, conn, _config = _seed(tmp_path)

    conn.execute(
        "INSERT INTO printer_tokens(id,token_mint,chain) VALUES (3,'mint-3','solana')"
    )
    conn.execute(
        "INSERT INTO printer_pairs(id,token_id,pair_address,base_token_mint) "
        "VALUES (103,3,'pool-3','mint-3')"
    )
    # This is peer Cycle-2 work in the shared factory-run ledger. The Cycle-1
    # validator must not count it as Cycle-1 expected/actual long work.
    conn.execute(
        "INSERT INTO printer_memory_factory_run_steps("
        "run_id,step_key,step_kind,step_status,token_id,pair_id,token_mint,"
        "pair_address,tracking_lane,scheduled_for,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            FACTORY_RUN_ID,
            "t1_c0002_4h_snapshot_01",
            "LONG_CONTINUATION_SNAPSHOT",
            "SUCCEEDED",
            3,
            103,
            "mint-3",
            "pool-3",
            "TRACK_NORMAL",
            NOW.isoformat(),
            NOW.isoformat(),
            NOW.isoformat(),
        ),
    )
    conn.commit()

    monkeypatch.setattr(
        standard_4h_progression,
        "derive_standard_4h_progression_status",
        lambda *args, **kwargs: {
            "enabled": True,
            "complete": True,
            "aggregate_state": "HANDOFF_COMMITTED",
            "per_token": [],
            "progression_attempt_id": "cycle1-attempt",
            "requires_review": False,
        },
    )
    monkeypatch.setattr(
        one_token_4h_runtime,
        "load_standard_four_hour_eligibility_manifests",
        lambda *args, **kwargs: {},
    )

    result = factory._standard_campaign_four_hour_terminal_validation(
        conn,
        factory_run_id=FACTORY_RUN_ID,
        campaign_id=CAMPAIGN_ID,
        run_id=CAMPAIGN_RUN_ID,
        cycle_id=CYCLE_1,
    )

    assert result["complete"] is True, result
    assert result["reasons"] == []
    conn.close()
