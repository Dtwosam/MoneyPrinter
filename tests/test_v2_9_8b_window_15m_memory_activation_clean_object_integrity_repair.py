from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import replace

import pytest

from printer_v1.db import apply_migrations
from printer_v1.discovery.memory_observation_activation import (
    ActivationPurpose,
    EvidenceRole,
    FrozenMemoryActivationCandidate,
    FrozenMemoryActivationSet,
    MemoryObservationActivationError,
    RetainedEvidenceReference,
    TrackingFeasibility,
    validate_memory_activation_set,
)
from printer_v1.discovery.permanent_discovery_availability import (
    freeze_eligible_reserve,
)
from printer_v1.memory.clean_object_promotion import (
    CleanObjectIntegrityError,
    promote_clean_object,
)
from printer_v1.operator_cli.e2z_clean_memory_creation import (
    E2Z_STATUS_CREATED,
    create_clean_memory_from_window,
)
from printer_v1.operator_cli.pilot_input_readiness import (
    READINESS_PURPOSE_MEMORY_OBSERVATION,
    ReadinessCandidate,
    build_pilot_input_ready_bundle,
)
from printer_v1.operator_cli.one_command_15m_factory import (
    _apply_clean_object_integrity_gate,
    _four_hour_terminal_validation,
)
from printer_v1.discovery.combined_executor import (
    CombinedDiscoveryFixtures,
    CombinedPumpfunCampaignExecutor,
    FixturePumpSwapProof,
)
from printer_v1.operator_cli.abstract_campaign_command import (
    CENTRAL_SCHEDULER_OWNER,
    OwnerPort,
    SOURCE_GOVERNOR_OWNER,
)
from test_v2_9_8b_16_batch_scoped_discovery_persistence import (
    BatchScopedDiscoveryPersistenceProof as _BatchScopedDiscoveryPersistenceProof,
)

_BatchScopedDiscoveryPersistenceProof.__test__ = False


NOW = "2026-08-05T10:00:00+00:00"
EXPIRES = "2026-08-05T10:10:00+00:00"
MINT_1 = "Mint111111111111111111111111111111111111111"
MINT_2 = "Mint222222222222222222222222222222222222222"
POOL_1 = "Pool111111111111111111111111111111111111111"
POOL_2 = "Pool222222222222222222222222222222222222222"


def _transport_key(
    mint: str,
    *,
    stage: str = "MARKET_OBSERVATION",
    source_name: str = "dexscreener",
    request_kind: str = "candidate_market_batch",
    method: str = "POST /latest/dex/tokens",
    ordinal: int = 1,
) -> tuple[object, ...]:
    return (
        stage,
        source_name,
        source_name,
        request_kind,
        method,
        ordinal,
        "MINT",
        mint,
        128,
        1,
        "COMPLETE",
        None,
    )


def _insert_source_pair(
    connection: sqlite3.Connection,
    *,
    mint: str,
    pool: str,
    request_key: str,
    source_name: str = "dexscreener",
    request_kind: str = "candidate_market_batch",
) -> tuple[int, int, str]:
    payload = {"mint": mint, "pool": pool, "observed_at": NOW}
    payload_json = json.dumps(payload, sort_keys=True)
    raw_hash = hashlib.sha256(payload_json.encode()).hexdigest()
    request = connection.execute(
        """INSERT INTO printer_source_requests(
               source_name,request_kind,requested_at,request_key,
               source_status,data_quality_label
           ) VALUES (?,?,?,?,
                     'COMPLETE','CLEAN_DATA')""",
        (source_name, request_kind, NOW, request_key),
    )
    response = connection.execute(
        """INSERT INTO printer_source_responses(
               source_request_id,source_name,received_at,status_code,
               source_status,data_quality_label,response_hash,
               normalized_payload_json
           ) VALUES (?,?,?,200,'COMPLETE','CLEAN_DATA',?,?)""",
        (int(request.lastrowid), source_name, NOW, raw_hash, payload_json),
    )
    return int(request.lastrowid), int(response.lastrowid), raw_hash


@pytest.fixture
def activation_db(tmp_path):
    path = tmp_path / "activation.sqlite3"
    apply_migrations(path)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
    finally:
        connection.close()


def _tracking(*, eligible: bool = True, reason: str = "TRACKING_HANDOFF_ELIGIBLE"):
    return TrackingFeasibility(
        eligible=eligible,
        reason_code=reason,
        tracking_queue_id=None,
        tracking_queue_status=None,
        requalification_required=False,
        cooldown_until=None,
        assessed_at=NOW,
    )


def _reference(
    *,
    mint: str,
    pool: str,
    request_id: int,
    response_id: int,
    raw_hash: str,
    role: EvidenceRole = EvidenceRole.MARKET_OBSERVATION,
    source_name: str = "dexscreener",
    request_kind: str = "candidate_market_batch",
    transport_key: tuple[object, ...] | None = None,
) -> RetainedEvidenceReference:
    return RetainedEvidenceReference(
        evidence_role=role,
        source_name=source_name,
        request_kind=request_kind,
        source_request_id=request_id,
        source_response_id=response_id,
        source_failure_id=None,
        transport_identity_keys=(
            (
                transport_key
                if transport_key is not None
                else _transport_key(
                    mint, source_name=source_name, request_kind=request_kind
                )
            ),
        ),
        observed_at=NOW,
        raw_payload_hash=raw_hash,
        target_mint=mint,
        target_pool=pool,
        campaign_id="campaign-1",
        campaign_run_id="run-1",
        cycle_id="cycle-1",
    )


def _three_role_references(
    connection: sqlite3.Connection,
    *,
    mint: str,
    pool: str,
    key_prefix: str,
) -> tuple[tuple[RetainedEvidenceReference, ...], list[int], list[tuple[object, ...]]]:
    role_specs = (
        (
            EvidenceRole.ORIGIN_LINEAGE,
            "solana_rpc",
            "pumpfun_origin_transaction_reference",
            "ORIGIN_LINEAGE",
            "rpc origin",
        ),
        (
            EvidenceRole.PUMPSWAP_CONFIRMATION,
            "solana_rpc",
            "pumpswap_pool_account_batch",
            "PUMPSWAP_CONFIRMATION",
            "getMultipleAccounts",
        ),
        (
            EvidenceRole.MARKET_OBSERVATION,
            "dexscreener",
            "candidate_market_batch",
            "MARKET_OBSERVATION",
            "POST /latest/dex/tokens",
        ),
    )
    refs: list[RetainedEvidenceReference] = []
    request_ids: list[int] = []
    keys: list[tuple[object, ...]] = []
    for role, source_name, request_kind, stage, method in role_specs:
        rid, sid, raw_hash = _insert_source_pair(
            connection,
            mint=mint,
            pool=pool,
            request_key=f"{key_prefix}:{role.value}",
            source_name=source_name,
            request_kind=request_kind,
        )
        key = _transport_key(
            mint,
            stage=stage,
            source_name=source_name,
            request_kind=request_kind,
            method=method,
        )
        refs.append(
            _reference(
                mint=mint,
                pool=pool,
                request_id=rid,
                response_id=sid,
                raw_hash=raw_hash,
                role=role,
                source_name=source_name,
                request_kind=request_kind,
                transport_key=key,
            )
        )
        request_ids.append(rid)
        keys.append(key)
    return tuple(refs), request_ids, keys


def _candidate(
    *,
    ordinal: int,
    mint: str,
    pool: str,
    references: tuple[RetainedEvidenceReference, ...],
    holder_condition: str = "HOLDER_CONCENTRATION_PASS",
    fully_eligible: bool = True,
    future_action: str = "ELIGIBLE",
    tracking: TrackingFeasibility | None = None,
) -> FrozenMemoryActivationCandidate:
    return FrozenMemoryActivationCandidate(
        slot_ordinal=ordinal,
        mint=mint,
        pool=pool,
        market_identity=f"solana-mainnet:pumpswap:{pool}",
        lifecycle_identity="PUMPSWAP_GRADUATED_CONFIRMED",
        activation_route="GRADUATION_NATIVE",
        provenance="PERSISTED_GRADUATED",
        memory_observation_eligible=True,
        fully_eligible=fully_eligible,
        holder_condition=holder_condition,
        holder_evidence_status=holder_condition,
        future_action_eligibility=future_action,
        evidence_expires_at=EXPIRES,
        liquidity_observed_at=NOW,
        tracking_feasibility=tracking or _tracking(),
        retained_evidence_references=references,
    )


def _activation_set(connection: sqlite3.Connection) -> FrozenMemoryActivationSet:
    refs1, ids1, keys1 = _three_role_references(
        connection, mint=MINT_1, pool=POOL_1, key_prefix="campaign-1:run-1:cycle-1:1"
    )
    refs2, ids2, keys2 = _three_role_references(
        connection, mint=MINT_2, pool=POOL_2, key_prefix="campaign-1:run-1:cycle-1:2"
    )
    return FrozenMemoryActivationSet(
        activation_purpose=ActivationPurpose.MEMORY_OBSERVATION,
        readiness_id="ready-1",
        selection_seed="seed-1",
        selected=(
            _candidate(ordinal=1, mint=MINT_1, pool=POOL_1, references=refs1),
            _candidate(
                ordinal=2,
                mint=MINT_2,
                pool=POOL_2,
                references=refs2,
                holder_condition="HOLDER_SOURCE_UNAVAILABLE",
                fully_eligible=False,
                future_action="BLOCKED_OR_UNKNOWN",
            ),
        ),
        alternates=(
            replace(
                _candidate(
                    ordinal=3, mint=MINT_1, pool=POOL_1, references=refs1
                ),
                mint="Mint333333333333333333333333333333333333333",
                pool="Pool333333333333333333333333333333333333333",
            ),
            replace(
                _candidate(
                    ordinal=4, mint=MINT_2, pool=POOL_2, references=refs2
                ),
                mint="Mint444444444444444444444444444444444444444",
                pool="Pool444444444444444444444444444444444444444",
            ),
        ),
        manifest_request_ids=tuple(ids1 + ids2),
        manifest_transport_identity_keys=tuple(keys1 + keys2),
        frozen_at=NOW,
        expires_at=EXPIRES,
    )


@pytest.mark.parametrize(
    ("condition", "fully_eligible", "future_action"),
    [
        ("HOLDER_CONCENTRATION_PASS", True, "ELIGIBLE"),
        ("HOLDER_CONCENTRATION_FAIL", False, "BLOCKED"),
        ("HOLDER_SOURCE_UNAVAILABLE", False, "BLOCKED_OR_UNKNOWN"),
        ("HOLDER_CONTEXT_BUDGET_BOUND_UNKNOWN", False, "BLOCKED_OR_UNKNOWN"),
    ],
)
def test_memory_activation_accepts_holder_context_without_overstating_future_action(
    activation_db, condition, fully_eligible, future_action
):
    activation = _activation_set(activation_db)
    second = replace(
        activation.selected[1],
        holder_condition=condition,
        holder_evidence_status=condition,
        fully_eligible=fully_eligible,
        future_action_eligibility=future_action,
    )
    activation = replace(activation, selected=(activation.selected[0], second))

    report = validate_memory_activation_set(activation_db, activation, now=NOW)

    assert report["reconciliation_status"] == "PASS"
    assert [item.slot_ordinal for item in activation.selected] == [1, 2]
    assert activation.selected[1].fully_eligible is fully_eligible
    assert activation.selected[1].future_action_eligibility == future_action


def test_tracking_ineligible_candidate_is_rejected_before_activation(activation_db):
    activation = _activation_set(activation_db)
    blocked = replace(
        activation.selected[0],
        tracking_feasibility=_tracking(
            eligible=False, reason="ACTIVE_TRACKING_CONFLICT"
        ),
    )
    with pytest.raises(MemoryObservationActivationError) as exc:
        validate_memory_activation_set(
            activation_db,
            replace(activation, selected=(blocked, activation.selected[1])),
            now=NOW,
        )
    assert exc.value.code == "TRACKING_FEASIBILITY_INELIGIBLE"


def test_tracking_ineligible_candidate_cannot_enter_four_candidate_freeze():
    candidates = [
        {
            "mint": f"MintFreeze{ordinal}",
            "pool": f"PoolFreeze{ordinal}",
            "market_identity": f"solana-mainnet:pumpswap:PoolFreeze{ordinal}",
            "memory_observation_eligible": True,
            "tracking_handoff_eligible": ordinal != 4,
            "tracking_requalification_required": False,
            "evidence_expires_at": EXPIRES,
        }
        for ordinal in range(1, 5)
    ]

    frozen = freeze_eligible_reserve(candidates, cycle_seed="seed", at=NOW)

    assert frozen.selected == ()
    assert frozen.selection_authority["tracking_ineligible_count"] == 1
    assert frozen.selection_authority["valid_fresh_unique_observation_depth"] == 3
    assert frozen.selection_authority["coverage_blocker"] is True


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (lambda value: replace(value, manifest_request_ids=value.manifest_request_ids[1:]), "RETAINED_REQUEST_NOT_IN_MANIFEST"),
        (lambda value: replace(value, manifest_transport_identity_keys=()), "RETAINED_TRANSPORT_IDENTITY_MISSING"),
        (
            lambda value: replace(
                value,
                selected=(
                    replace(
                        value.selected[0],
                        pool=POOL_2,
                        market_identity=f"solana-mainnet:pumpswap:{POOL_2}",
                    ),
                    value.selected[1],
                ),
            ),
            "RETAINED_EVIDENCE_TARGET_MISMATCH",
        ),
    ],
)
def test_retained_evidence_mismatch_blocks_exactly(activation_db, mutation, code):
    activation = mutation(_activation_set(activation_db))
    with pytest.raises(MemoryObservationActivationError) as exc:
        validate_memory_activation_set(activation_db, activation, now=NOW)
    assert exc.value.code == code


def test_validation_creates_zero_source_rows(activation_db):
    activation = _activation_set(activation_db)
    before = tuple(
        activation_db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("printer_source_requests", "printer_source_responses")
    )
    report = validate_memory_activation_set(activation_db, activation, now=NOW)
    after = tuple(
        activation_db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("printer_source_requests", "printer_source_responses")
    )
    assert before == after
    assert report["new_source_request_ids"] == []
    assert report["new_source_response_ids"] == []


def test_readiness_reports_exact_order_and_liquidity_timestamp(activation_db):
    exact_first = "2026-08-05T09:59:01+00:00"
    exact_second = "2026-08-05T09:59:02+00:00"

    def readiness(ordinal, mint, pool, observed_at, provenance):
        return ReadinessCandidate(
            mint=mint,
            pool=pool,
            market_identity=f"solana-mainnet:pumpswap:{pool}",
            liquidity_usd=4000.0,
            liquidity_observed_at=observed_at,
            activation_route="GRADUATION_NATIVE",
            holder_eligible=False,
            provenance=provenance,
            memory_observation_eligible=True,
            holder_condition="HOLDER_SOURCE_UNAVAILABLE",
            slot_ordinal=ordinal,
            tracking_eligible=True,
            tracking_reason="TRACKING_HANDOFF_ELIGIBLE",
            retained_source_request_ids=(ordinal,),
            retained_source_response_ids=(ordinal + 10,),
        )

    bundle = build_pilot_input_ready_bundle(
        activation_db,
        readiness_id="ordered-readiness",
        latest=readiness(1, MINT_2, POOL_2, exact_first, "PERSISTED_GRADUATED"),
        persisted=readiness(2, MINT_1, POOL_1, exact_second, "LATEST_GRADUATED"),
        holder_evidence={},
        source_ledger={},
        selection_seed="frozen-seed",
        git_provenance_identity="head",
        configuration_hash="config",
        expires_at=EXPIRES,
        now=NOW,
        readiness_purpose=READINESS_PURPOSE_MEMORY_OBSERVATION,
    )

    assert bundle["legacy_candidate_fields"] == "POSITIONAL_COMPATIBILITY_ONLY"
    assert [item["slot_ordinal"] for item in bundle["ordered_selected_candidates"]] == [1, 2]
    assert [item["mint"] for item in bundle["ordered_selected_candidates"]] == [MINT_2, MINT_1]
    assert [item["liquidity_observed_at"] for item in bundle["ordered_selected_candidates"]] == [exact_first, exact_second]


def _insert_clean_candidate_window(connection: sqlite3.Connection) -> int:
    token = connection.execute(
        """INSERT INTO printer_tokens(
               token_mint,chain,token_status,first_seen_at,last_seen_at,
               created_at,updated_at
           ) VALUES (?,'solana','TRACK_NORMAL',?,?,?,?)""",
        (MINT_1, NOW, NOW, NOW, NOW),
    )
    pair = connection.execute(
        """INSERT INTO printer_pairs(
               token_id,pair_address,base_token_mint,first_seen_at,last_seen_at,
               created_at,updated_at
           ) VALUES (?,?,?,?,?,?,?)""",
        (int(token.lastrowid), POOL_1, MINT_1, NOW, NOW, NOW, NOW),
    )
    context = json.dumps(
        {
            "snapshot_id": 1,
            "e2q_audited": True,
            "e2q_audit_status": "E2Q_AUDIT_CLEAN_CANDIDATE",
            "tracking_lane": "TRACK_NORMAL",
        },
        sort_keys=True,
    )
    window = connection.execute(
        """INSERT INTO printer_memory_windows(
               token_id,pair_id,window_kind,opened_at,closed_at,memory_status,
               data_quality_label,do_not_train,window_status,memory_quality_label,
               supporting_context_json,created_by_phase,created_at,updated_at,
               window_start_at,window_end_at,snapshot_start_id,snapshot_end_id
           ) VALUES (?,?, 'WINDOW_15M',?,?, 'PARTIAL_MEMORY','CLEAN_DATA',0,
                     'WINDOW_CLOSED','PARTIAL_MEMORY',?,'test',?,?,?,?,1,2)""",
        (
            int(token.lastrowid),
            int(pair.lastrowid),
            NOW,
            "2026-08-05T10:15:01+00:00",
            context,
            NOW,
            NOW,
            NOW,
            "2026-08-05T10:15:01+00:00",
        ),
    )
    connection.commit()
    return int(window.lastrowid)


def _count(connection: sqlite3.Connection, table: str) -> int:
    return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def test_episode_and_fingerprint_commit_as_one_exact_object(activation_db):
    window_id = _insert_clean_candidate_window(activation_db)

    result = promote_clean_object(activation_db, window_id=window_id)

    assert result.status == "CREATED"
    assert result.episode_id > 0
    assert result.fingerprint_id > 0
    row = activation_db.execute(
        "SELECT fingerprint_payload_json FROM printer_memory_fingerprints WHERE id=?",
        (result.fingerprint_id,),
    ).fetchone()
    payload = json.loads(row[0])
    assert payload["episode_id"] == result.episode_id
    assert payload["window_id"] == window_id
    assert payload["token_id"] != "UNKNOWN"
    assert payload["pair_id"] != "UNKNOWN"


def test_forced_fingerprint_failure_rolls_back_episode_and_fingerprint(activation_db):
    window_id = _insert_clean_candidate_window(activation_db)

    def fail_writer(*args, **kwargs):
        raise RuntimeError("injected fingerprint failure")

    with pytest.raises(CleanObjectIntegrityError) as exc:
        promote_clean_object(
            activation_db,
            window_id=window_id,
            fingerprint_writer=fail_writer,
        )

    assert exc.value.code == "FINGERPRINT_CREATION_FAILED"
    assert _count(activation_db, "printer_episodes") == 0
    assert _count(activation_db, "printer_memory_fingerprints") == 0


def test_complete_clean_object_replay_is_idempotent(activation_db):
    window_id = _insert_clean_candidate_window(activation_db)
    created = promote_clean_object(activation_db, window_id=window_id)

    replay = promote_clean_object(activation_db, window_id=window_id)

    assert replay.status == "ALREADY_EXISTS"
    assert replay.episode_id == created.episode_id
    assert replay.fingerprint_id == created.fingerprint_id
    assert _count(activation_db, "printer_episodes") == 1
    assert _count(activation_db, "printer_memory_fingerprints") == 1


def test_mismatched_existing_clean_object_blocks_without_rewrite(activation_db):
    window_id = _insert_clean_candidate_window(activation_db)
    created = promote_clean_object(activation_db, window_id=window_id)
    row = activation_db.execute(
        "SELECT fingerprint_payload_json FROM printer_memory_fingerprints WHERE id=?",
        (created.fingerprint_id,),
    ).fetchone()
    payload = json.loads(row[0])
    payload["pair_id"] = int(payload["pair_id"]) + 1
    activation_db.execute(
        "UPDATE printer_memory_fingerprints SET fingerprint_payload_json=? WHERE id=?",
        (json.dumps(payload, sort_keys=True), created.fingerprint_id),
    )
    activation_db.commit()

    with pytest.raises(CleanObjectIntegrityError) as exc:
        promote_clean_object(activation_db, window_id=window_id)

    assert exc.value.code == "FINGERPRINT_IDENTITY_MISMATCH"
    assert _count(activation_db, "printer_episodes") == 1
    assert _count(activation_db, "printer_memory_fingerprints") == 1


def test_existing_clean_episode_without_fingerprint_blocks_without_mutation(activation_db):
    window_id = _insert_clean_candidate_window(activation_db)
    window = activation_db.execute(
        "SELECT token_id,pair_id FROM printer_memory_windows WHERE id=?", (window_id,)
    ).fetchone()
    activation_db.execute(
        """INSERT INTO printer_episodes(
               memory_window_id,token_id,pair_id,episode_kind,episode_status,
               memory_status,data_quality_label,do_not_train,window_kind,
               memory_quality_label,supporting_context_json,created_at,updated_at
           ) VALUES (?,?,?,'WINDOW_15M_CLEAN_MEMORY','COMPLETE','CLEAN_MEMORY',
                     'CLEAN_DATA',0,'WINDOW_15M','CLEAN_MEMORY','{}',?,?)""",
        (window_id, int(window[0]), int(window[1]), NOW, NOW),
    )
    activation_db.commit()

    with pytest.raises(CleanObjectIntegrityError) as exc:
        promote_clean_object(activation_db, window_id=window_id)

    assert exc.value.code == "EXISTING_INCOMPLETE_CLEAN_OBJECT"
    assert _count(activation_db, "printer_episodes") == 1
    assert _count(activation_db, "printer_memory_fingerprints") == 0


def test_e2z_compatibility_boundary_returns_atomic_fingerprint(activation_db):
    window_id = _insert_clean_candidate_window(activation_db)
    db_path = activation_db.execute("PRAGMA database_list").fetchone()[2]

    result = create_clean_memory_from_window(
        db_path,
        window_id,
        operator_approved=True,
        individual_promotion=True,
    )

    assert result["e2z_status"] == E2Z_STATUS_CREATED
    assert result["fingerprint_id"] > 0
    assert result["atomic_status"] == "CREATED"
    assert result["idempotent"] is False
    assert _count(activation_db, "printer_episodes") == 1
    assert _count(activation_db, "printer_memory_fingerprints") == 1


def test_factory_blocks_atomic_integrity_failure_but_not_honest_no_promotion():
    failed = {
        "ok": True,
        "memory_pipeline": {
            "clean_object_integrity_blocked": True,
            "blocked_reasons": [
                "clean_object_integrity:FINGERPRINT_CREATION_FAILED"
            ],
        },
    }
    assert _apply_clean_object_integrity_gate(failed) is False
    assert failed["ok"] is False
    assert (
        failed["blocked_reason"]
        == "clean_object_integrity:FINGERPRINT_CREATION_FAILED"
    )

    honest_dirty = {
        "ok": True,
        "memory_pipeline": {
            "clean_object_integrity_blocked": False,
            "e2z_created_count": 0,
        },
    }
    assert _apply_clean_object_integrity_gate(honest_dirty) is True
    assert honest_dirty["ok"] is True


def test_current_run_terminal_acceptance_requires_complete_clean_objects():
    windows = {
        ordinal: {
            "id": ordinal,
            "window_kind": "WINDOW_15M",
            "window_status": "WINDOW_CLOSED",
            "memory_status": "CLEAN_MEMORY",
            "memory_quality_label": "CLEAN_MEMORY",
            "data_quality_label": "CLEAN_DATA",
            "do_not_train": 0,
        }
        for ordinal in (1, 2)
    }
    steps = [
        {
            "step_kind": "WINDOW_CLOSE",
            "step_status": "SUCCEEDED",
            "token_id": ordinal,
            "memory_window_id": ordinal,
            "result_json": json.dumps(
                {"continuation_plan": {"verdict": "STOP_AFTER_15M", "planned_jobs": 0}}
            ),
        }
        for ordinal in (1, 2)
    ]
    kwargs = {
        "config": {
            "continuous_four_hour": True,
            "operational_natural_disposition": True,
        },
        "steps": steps,
        "windows_by_id": windows,
        "budgets": {"four_hour_phase_usage": {"state": "NOT_STARTED"}},
        "pending_steps": 0,
        "running_jobs": 0,
    }

    blocked = _four_hour_terminal_validation(
        **kwargs, complete_clean_objects_by_window_id={}
    )
    accepted = _four_hour_terminal_validation(
        **kwargs,
        complete_clean_objects_by_window_id={1: {"fingerprint_id": 1}, 2: {"fingerprint_id": 2}},
    )

    assert blocked["memory_acceptance"]["verdict"] == "MEMORY_EVIDENCE_BLOCKED"
    assert "incomplete_clean_object:1" in blocked["reasons"]
    assert accepted["memory_acceptance"]["verdict"] == "CLEAN_MEMORY_ACHIEVED"


@pytest.mark.parametrize("handoff_failure", [None, "DUPLICATE_ACTIVE"])
def test_combined_memory_activation_reuses_evidence_and_frozen_order(
    monkeypatch, handoff_failure
):
    proof = _BatchScopedDiscoveryPersistenceProof()
    proof.setUp()
    try:
        command, cycle_id = proof._create_command(91)
        connection = sqlite3.connect(proof.db)
        connection.row_factory = sqlite3.Row
        try:
            activation = _activation_set(connection)
            connection.commit()
            before = (
                _count(connection, "printer_source_requests"),
                _count(connection, "printer_source_responses"),
            )
        finally:
            connection.close()

        # Rebind the reference ownership to the disposable campaign.
        def owned(reference: RetainedEvidenceReference) -> RetainedEvidenceReference:
            return replace(
                reference,
                campaign_id=command.campaign_id,
                campaign_run_id=command.run_id,
                cycle_id=cycle_id,
            )

        selected = tuple(
            replace(candidate, retained_evidence_references=tuple(
                owned(reference) for reference in candidate.retained_evidence_references
            ))
            for candidate in activation.selected
        )
        activation = replace(activation, selected=selected)
        fixtures = CombinedDiscoveryFixtures(
            cycle_id=cycle_id,
            cycle_cutoff="2026-08-05T10:06:00+00:00",
            campaign_selection_seed="batch-scoped-proof-seed",
            provider_contract_versions={"retained": "V1"},
            git_provenance_identity="retained-evidence-test",
            evaluated_at=NOW,
            pumpswap_proofs={
                MINT_1: FixturePumpSwapProof(mint=MINT_1, pool_address=POOL_1),
                MINT_2: FixturePumpSwapProof(mint=MINT_2, pool_address=POOL_2),
            },
            holder_evidence_eligibility={
                MINT_1.lower(): {"eligible": False, "reason": "HOLDER_CONCENTRATION_FAIL"},
                MINT_2.lower(): {"eligible": False, "reason": "HOLDER_SOURCE_UNAVAILABLE"},
            },
            memory_activation_set=activation,
            force_handoff_failure=handoff_failure,
        )
        executor = CombinedPumpfunCampaignExecutor(fixtures)
        monkeypatch.setattr(executor, "_select", lambda *a, **k: (_ for _ in ()).throw(AssertionError("second selector called")))
        monkeypatch.setattr(executor, "_governed_request", lambda *a, **k: (_ for _ in ()).throw(AssertionError("new source request")))
        monkeypatch.setattr(executor, "_store_response", lambda *a, **k: (_ for _ in ()).throw(AssertionError("new source response")))

        result = executor.execute(
            command=command,
            source_governor=OwnerPort(SOURCE_GOVERNOR_OWNER, True),
            central_scheduler=OwnerPort(CENTRAL_SCHEDULER_OWNER, True),
        )

        assert result.terminal_status == (
            "COMPLETED" if handoff_failure is None else "FAILED"
        )
        connection = sqlite3.connect(proof.db)
        connection.row_factory = sqlite3.Row
        try:
            slots = connection.execute(
                """SELECT slot_ordinal,mint_identity FROM
                          printer_memory_factory_campaign_token_slots
                   WHERE cycle_id=? ORDER BY slot_ordinal""",
                (cycle_id,),
            ).fetchall()
            after = (
                _count(connection, "printer_source_requests"),
                _count(connection, "printer_source_responses"),
            )
            links = connection.execute(
                """SELECT source_request_id,source_response_id
                   FROM printer_discovery_work_source_links
                   ORDER BY source_request_id"""
            ).fetchall()
        finally:
            connection.close()
        assert [(row["slot_ordinal"], row["mint_identity"]) for row in slots] == (
            [(1, MINT_1), (2, MINT_2)]
            if handoff_failure is None
            else []
        )
        assert before == after
        assert {row["source_request_id"] for row in links} == set(
            activation.manifest_request_ids
        )
    finally:
        proof.tearDown()
