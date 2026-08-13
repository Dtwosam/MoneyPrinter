from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import sqlite3

import pytest

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.pre_admission_discovery_attempt import (
    PreAdmissionAttemptError,
    PreAdmissionAttemptItem,
    PreAdmissionAttemptState,
    create_pre_admission_attempt,
    link_pre_admission_source_evidence,
    load_pre_admission_attempt,
    load_pre_admission_pair,
    mark_pre_admission_attempt_running,
    persist_pre_admission_pair,
    terminalize_pre_admission_attempt,
)


NOW = datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def connection(tmp_path):
    path = tmp_path / "attempt-persistence.sqlite3"
    apply_migrations(path)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute(
        "INSERT INTO printer_memory_factory_campaigns("
        "campaign_id,campaign_state,db_mode,db_target_identity,policy_version) "
        "VALUES ('campaign-1','RUNNING','OPERATIONAL_PERSISTENT','db-1','policy-1')"
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_configurations("
        "configuration_id,campaign_id,configuration_hash,configuration_json,"
        "launch_provenance_json) VALUES (?,?,?,?,?)",
        ("configuration-1", "campaign-1", "a" * 64, "{}", "{}"),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_runs("
        "run_id,run_status,window_kind,db_mode,config_hash,config_json,started_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (
            "factory-1", "RUNNING", "WINDOW_15M", "OPERATIONAL_PERSISTENT",
            "a" * 64, "{}", NOW.isoformat(),
        ),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_runs("
        "run_id,campaign_id,run_ordinal,run_state,authoritative_run_id,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (
            "campaign-run-1", "campaign-1", 1, "RUNNING", "factory-1",
            NOW.isoformat(), NOW.isoformat(),
        ),
    )
    connection.execute(
        "INSERT INTO printer_scheduler_jobs("
        "job_name,job_kind,target_table,priority,status,scheduled_for) "
        "VALUES (?,?,?,?,?,?)",
        (
            "pre-admission:attempt-1", "PRE_ADMISSION_DISCOVERY_SELECTION",
            "printer_pre_admission_discovery_attempts", 13, "PENDING",
            NOW.isoformat(),
        ),
    )
    connection.commit()
    try:
        yield connection
    finally:
        connection.close()


def _create(connection, *, attempt_id="attempt-1", factory_run_id="factory-1"):
    return create_pre_admission_attempt(
        connection,
        attempt_id=attempt_id,
        campaign_id="campaign-1",
        campaign_run_id="campaign-run-1",
        configuration_id="configuration-1",
        authoritative_factory_run_id=factory_run_id,
        proposed_cycle_ordinal=2,
        proposed_cycle_id="cycle-2",
        scheduler_job_id=1,
        cycle_cutoff=NOW,
        evaluated_at=NOW,
        selection_seed_identity="seed-2",
        now=NOW,
    )


def _item(slot: int) -> PreAdmissionAttemptItem:
    return PreAdmissionAttemptItem(
        attempt_id="attempt-1",
        slot_ordinal=slot,
        token_identity=f"solana-mainnet:mint-{slot}",
        token_row_id=slot,
        mint_identity=f"mint-{slot}",
        pair_identity=f"pair-{slot}",
        pair_row_id=slot,
        lifecycle_identity=f"lifecycle-{slot}",
        canonical_market_identity=f"solana-mainnet:dex:pool-{slot}",
        canonical_pool_identity=f"pool-{slot}",
        canonical_evidence_json='{"quality":"exact"}',
        canonical_evidence_hash=str(slot) * 64,
        evidence_version="v1",
        observed_at=NOW,
        channel_labels=("LATEST_PUMPFUN" if slot == 1 else "TOP_PUMPFUN",),
    )


def _seed_items(connection) -> None:
    for slot in (1, 2):
        connection.execute(
            "INSERT INTO printer_tokens(id,token_mint,chain) VALUES (?,?, 'solana')",
            (slot, f"mint-{slot}"),
        )
        connection.execute(
            "INSERT INTO printer_pairs(id,token_id,pair_address) VALUES (?,?,?)",
            (slot, slot, f"pair-{slot}"),
        )
    connection.commit()


def _claim_attempt_job(connection) -> None:
    connection.execute(
        "UPDATE printer_scheduler_jobs SET status='RUNNING',"
        "lock_owner='pre-admission-discovery:attempt-1',locked_at=? WHERE id=1",
        (NOW.isoformat(),),
    )


def test_create_is_immutable_owner_bound_and_one_shot(connection) -> None:
    created = _create(connection)
    assert created.state is PreAdmissionAttemptState.PLANNED
    assert created.authoritative_factory_run_id == "factory-1"
    with pytest.raises(PreAdmissionAttemptError, match="ATTEMPT_ALREADY_EXISTS"):
        _create(connection)
    with pytest.raises(PreAdmissionAttemptError, match="OWNERSHIP_MISMATCH"):
        _create(connection, attempt_id="attempt-wrong", factory_run_id="other-factory")


def test_state_machine_rejects_invalid_transition_rewrite_and_reopen(connection) -> None:
    _create(connection)
    with pytest.raises(PreAdmissionAttemptError, match="INVALID_ATTEMPT_TRANSITION"):
        terminalize_pre_admission_attempt(
            connection,
            attempt_id="attempt-1",
            state=PreAdmissionAttemptState.NO_PAIR,
            cause="NO_EXACT_PAIR",
            now=NOW,
        )
    _claim_attempt_job(connection)
    mark_pre_admission_attempt_running(connection, attempt_id="attempt-1", now=NOW)
    terminalize_pre_admission_attempt(
        connection,
        attempt_id="attempt-1",
        state=PreAdmissionAttemptState.NO_PAIR,
        cause="NO_EXACT_PAIR",
        now=NOW,
    )
    with pytest.raises(PreAdmissionAttemptError, match="INVALID_ATTEMPT_TRANSITION"):
        mark_pre_admission_attempt_running(connection, attempt_id="attempt-1", now=NOW)
    with pytest.raises(PreAdmissionAttemptError, match="INVALID_ATTEMPT_TRANSITION"):
        terminalize_pre_admission_attempt(
            connection,
            attempt_id="attempt-1",
            state=PreAdmissionAttemptState.FAILED,
            cause="REWRITE",
            now=NOW,
        )


def test_pair_is_atomic_exact_two_distinct_and_immutable(connection) -> None:
    _seed_items(connection)
    _create(connection)
    _claim_attempt_job(connection)
    mark_pre_admission_attempt_running(connection, attempt_id="attempt-1", now=NOW)
    with pytest.raises(PreAdmissionAttemptError, match="EXACT_TWO_ITEMS_REQUIRED"):
        persist_pre_admission_pair(
            connection, attempt_id="attempt-1", items=(_item(1),), now=NOW
        )
    assert connection.execute(
        "SELECT COUNT(*) FROM printer_pre_admission_discovery_attempt_items"
    ).fetchone()[0] == 0
    duplicate = replace(
        _item(2), token_identity=_item(1).token_identity, mint_identity=_item(1).mint_identity
    )
    with pytest.raises(PreAdmissionAttemptError, match="PAIR_IDENTITIES_NOT_DISTINCT"):
        persist_pre_admission_pair(
            connection, attempt_id="attempt-1", items=(_item(1), duplicate), now=NOW
        )
    persisted = persist_pre_admission_pair(
        connection, attempt_id="attempt-1", items=(_item(1), _item(2)), now=NOW
    )
    assert persisted.state is PreAdmissionAttemptState.PAIR_READY
    pair = load_pre_admission_pair(connection, attempt_id="attempt-1")
    assert tuple(item.slot_ordinal for item in pair) == (1, 2)
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        connection.execute(
            "UPDATE printer_pre_admission_discovery_attempt_items "
            "SET lifecycle_identity='changed' WHERE attempt_id='attempt-1'"
        )


def test_source_links_require_exact_canonical_request_lineage(connection) -> None:
    _create(connection)
    request_id = connection.execute(
        "INSERT INTO printer_source_requests("
        "source_name,request_kind,requested_at,source_status,data_quality_label) "
        "VALUES ('dexscreener','kind',?,'COMPLETE','CLEAN_DATA')",
        (NOW.isoformat(),),
    ).lastrowid
    response_id = connection.execute(
        "INSERT INTO printer_source_responses("
        "source_request_id,source_name,received_at,source_status,data_quality_label) "
        "VALUES (?,'dexscreener',?,'COMPLETE','CLEAN_DATA')",
        (request_id, NOW.isoformat()),
    ).lastrowid
    failure_id = connection.execute(
        "INSERT INTO printer_source_failures("
        "source_name,request_kind,failed_at,failure_type,source_status,"
        "data_quality_label,source_request_id) "
        "VALUES ('dexscreener','kind',?,'provider_error','FAILED','DIRTY_DATA',?)",
        (NOW.isoformat(), request_id),
    ).lastrowid
    connection.commit()
    with pytest.raises(PreAdmissionAttemptError, match="AMBIGUOUS_SOURCE_EVIDENCE"):
        link_pre_admission_source_evidence(
            connection,
            attempt_id="attempt-1",
            link_ordinal=1,
            logical_stage="DISCOVERY",
            source_request_id=request_id,
            source_response_id=response_id,
            source_failure_id=failure_id,
            now=NOW,
        )
    link_pre_admission_source_evidence(
        connection,
        attempt_id="attempt-1",
        link_ordinal=1,
        logical_stage="DISCOVERY",
        source_request_id=request_id,
        source_response_id=response_id,
        now=NOW,
    )
    assert load_pre_admission_attempt(connection, attempt_id="attempt-1").attempt_id == "attempt-1"
