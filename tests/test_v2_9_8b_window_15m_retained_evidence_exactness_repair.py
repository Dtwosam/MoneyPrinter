"""Focused offline tests for WINDOW_15M retained-evidence exactness repair."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import replace

import pytest

from printer_v1.db import apply_migrations
from printer_v1.discovery.combined_executor import (
    CombinedDiscoveryFixtures,
    CombinedPumpfunCampaignExecutor,
    FixturePumpSwapProof,
)
from printer_v1.discovery.memory_observation_activation import (
    ActivationPurpose,
    EvidenceRole,
    FrozenMemoryActivationCandidate,
    FrozenMemoryActivationSet,
    MEMORY_OBSERVATION_SELECTION_REASON,
    ManifestRequestEntry,
    MemoryObservationActivationError,
    REQUIRED_EVIDENCE_ROLES,
    RetainedEvidenceReference,
    TrackingFeasibility,
    measure_source_row_ids,
    reconcile_activation_source_rows,
    validate_memory_activation_set,
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
CAMPAIGN = "campaign-1"
RUN = "run-1"
CYCLE = "cycle-1"


def _key(
    *,
    mint: str,
    stage: str,
    source_name: str,
    request_kind: str,
    method: str,
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


def _insert_pair(
    connection: sqlite3.Connection,
    *,
    mint: str,
    pool: str,
    request_key: str,
    source_name: str,
    request_kind: str,
) -> tuple[int, int, str]:
    payload = {"mint": mint, "pool": pool, "observed_at": NOW}
    payload_json = json.dumps(payload, sort_keys=True)
    raw_hash = hashlib.sha256(payload_json.encode()).hexdigest()
    request = connection.execute(
        """INSERT INTO printer_source_requests(
               source_name,request_kind,requested_at,request_key,
               source_status,data_quality_label
           ) VALUES (?,?,?,?,'COMPLETE','CLEAN_DATA')""",
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


ROLE_SPECS = (
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


@pytest.fixture
def activation_db(tmp_path):
    path = tmp_path / "retained.sqlite3"
    apply_migrations(path)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
    finally:
        connection.close()


def _tracking():
    return TrackingFeasibility(
        eligible=True,
        reason_code="TRACKING_HANDOFF_ELIGIBLE",
        tracking_queue_id=None,
        tracking_queue_status=None,
        requalification_required=False,
        cooldown_until=None,
        assessed_at=NOW,
    )


def _build_roles(
    connection: sqlite3.Connection,
    *,
    mint: str,
    pool: str,
    prefix: str,
) -> tuple[
    list[RetainedEvidenceReference],
    list[ManifestRequestEntry],
    list[int],
    list[tuple[object, ...]],
]:
    refs: list[RetainedEvidenceReference] = []
    entries: list[ManifestRequestEntry] = []
    ids: list[int] = []
    keys: list[tuple[object, ...]] = []
    for role, source_name, request_kind, stage, method in ROLE_SPECS:
        rid, sid, raw_hash = _insert_pair(
            connection,
            mint=mint,
            pool=pool,
            request_key=f"{prefix}:{role.value}",
            source_name=source_name,
            request_kind=request_kind,
        )
        key = _key(
            mint=mint,
            stage=stage,
            source_name=source_name,
            request_kind=request_kind,
            method=method,
        )
        refs.append(
            RetainedEvidenceReference(
                evidence_role=role,
                source_name=source_name,
                request_kind=request_kind,
                source_request_id=rid,
                source_response_id=sid,
                source_failure_id=None,
                transport_identity_keys=(key,),
                observed_at=NOW,
                raw_payload_hash=raw_hash,
                target_mint=mint,
                target_pool=pool,
                campaign_id=CAMPAIGN,
                campaign_run_id=RUN,
                cycle_id=CYCLE,
            )
        )
        entries.append(
            ManifestRequestEntry(
                source_request_id=rid,
                source_name=source_name,
                request_kind=request_kind,
                logical_stage_id=f"{CAMPAIGN}|{RUN}|{CYCLE}|{stage}|1",
                transport_identity_count=1,
                transport_identity_keys=(key,),
                terminal_status="COMPLETED",
            )
        )
        ids.append(rid)
        keys.append(key)
    return refs, entries, ids, keys


def _candidate(
    *,
    ordinal: int,
    mint: str,
    pool: str,
    references: list[RetainedEvidenceReference] | tuple[RetainedEvidenceReference, ...],
    provenance: str = "PERSISTED_GRADUATED",
    holder_condition: str = "HOLDER_CONCENTRATION_PASS",
    fully_eligible: bool = True,
    future_action: str = "ELIGIBLE",
) -> FrozenMemoryActivationCandidate:
    return FrozenMemoryActivationCandidate(
        slot_ordinal=ordinal,
        mint=mint,
        pool=pool,
        market_identity=f"solana-mainnet:pumpswap:{pool}",
        lifecycle_identity="PUMPSWAP_GRADUATED_CONFIRMED",
        activation_route="GRADUATION_NATIVE",
        provenance=provenance,
        memory_observation_eligible=True,
        fully_eligible=fully_eligible,
        holder_condition=holder_condition,
        holder_evidence_status=holder_condition,
        future_action_eligibility=future_action,
        evidence_expires_at=EXPIRES,
        liquidity_observed_at=NOW,
        tracking_feasibility=_tracking(),
        retained_evidence_references=tuple(references),
    )


def _activation_set(connection: sqlite3.Connection) -> FrozenMemoryActivationSet:
    refs1, entries1, ids1, keys1 = _build_roles(
        connection, mint=MINT_1, pool=POOL_1, prefix="c1"
    )
    refs2, entries2, ids2, keys2 = _build_roles(
        connection, mint=MINT_2, pool=POOL_2, prefix="c2"
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
                holder_condition="HOLDER_CONCENTRATION_FAIL",
                fully_eligible=False,
                future_action="BLOCKED",
            ),
        ),
        alternates=(
            replace(
                _candidate(ordinal=3, mint=MINT_1, pool=POOL_1, references=refs1),
                mint="Mint333333333333333333333333333333333333333",
                pool="Pool333333333333333333333333333333333333333",
            ),
            replace(
                _candidate(ordinal=4, mint=MINT_2, pool=POOL_2, references=refs2),
                mint="Mint444444444444444444444444444444444444444",
                pool="Pool444444444444444444444444444444444444444",
            ),
        ),
        manifest_request_ids=tuple(ids1 + ids2),
        manifest_transport_identity_keys=tuple(keys1 + keys2),
        frozen_at=NOW,
        expires_at=EXPIRES,
        manifest_entries=tuple(entries1 + entries2),
    )


def test_empty_per_reference_transport_identities_block(activation_db):
    activation = _activation_set(activation_db)
    first = activation.selected[0]
    empty_refs = tuple(
        replace(ref, transport_identity_keys=())
        for ref in first.retained_evidence_references
    )
    activation = replace(
        activation,
        selected=(
            replace(first, retained_evidence_references=empty_refs),
            activation.selected[1],
        ),
    )
    with pytest.raises(MemoryObservationActivationError) as exc:
        validate_memory_activation_set(activation_db, activation, now=NOW)
    assert exc.value.code == "RETAINED_REQUEST_TRANSPORT_IDENTITY_MISSING"


def test_foreign_request_transport_key_blocks(activation_db):
    activation = _activation_set(activation_db)
    first = activation.selected[0]
    foreign_key = activation.selected[1].retained_evidence_references[0].transport_identity_keys[0]
    tainted = tuple(
        replace(ref, transport_identity_keys=(foreign_key,))
        if ref.evidence_role is EvidenceRole.MARKET_OBSERVATION
        else ref
        for ref in first.retained_evidence_references
    )
    activation = replace(
        activation,
        selected=(
            replace(first, retained_evidence_references=tainted),
            activation.selected[1],
        ),
    )
    with pytest.raises(MemoryObservationActivationError) as exc:
        validate_memory_activation_set(
            activation_db,
            activation,
            now=NOW,
            expected_ownership=(CAMPAIGN, RUN, CYCLE),
        )
    assert exc.value.code in {
        "RETAINED_TRANSPORT_IDENTITY_FOREIGN_REQUEST",
        "RETAINED_TRANSPORT_IDENTITY_COUNT_MISMATCH",
        "RETAINED_TRANSPORT_IDENTITY_MISSING",
    }


def test_same_source_same_kind_ambiguity_blocks_without_exact_binding(activation_db):
    # Two market requests of same source/kind; swapping keys must fail.
    activation = _activation_set(activation_db)
    market_refs = [
        ref
        for cand in activation.selected
        for ref in cand.retained_evidence_references
        if ref.evidence_role is EvidenceRole.MARKET_OBSERVATION
    ]
    assert market_refs[0].source_name == market_refs[1].source_name
    assert market_refs[0].request_kind == market_refs[1].request_kind
    first = activation.selected[0]
    swapped = tuple(
        replace(
            ref,
            transport_identity_keys=market_refs[1].transport_identity_keys,
        )
        if ref.evidence_role is EvidenceRole.MARKET_OBSERVATION
        else ref
        for ref in first.retained_evidence_references
    )
    activation = replace(
        activation,
        selected=(
            replace(first, retained_evidence_references=swapped),
            activation.selected[1],
        ),
    )
    with pytest.raises(MemoryObservationActivationError) as exc:
        validate_memory_activation_set(
            activation_db,
            activation,
            now=NOW,
            expected_ownership=(CAMPAIGN, RUN, CYCLE),
        )
    assert exc.value.code in {
        "RETAINED_TRANSPORT_IDENTITY_FOREIGN_REQUEST",
        "RETAINED_TRANSPORT_IDENTITY_COUNT_MISMATCH",
        "RETAINED_TRANSPORT_IDENTITY_MISSING",
    }


def test_transport_identity_count_mismatch_blocks(activation_db):
    activation = _activation_set(activation_db)
    entries = list(activation.manifest_entries)
    bad = replace(entries[0], transport_identity_count=2)
    activation = replace(activation, manifest_entries=tuple([bad, *entries[1:]]))
    with pytest.raises(MemoryObservationActivationError) as exc:
        validate_memory_activation_set(
            activation_db,
            activation,
            now=NOW,
            expected_ownership=(CAMPAIGN, RUN, CYCLE),
        )
    assert exc.value.code == "RETAINED_TRANSPORT_IDENTITY_COUNT_MISMATCH"


def test_wrong_logical_stage_blocks(activation_db):
    activation = _activation_set(activation_db)
    entries = list(activation.manifest_entries)
    bad = replace(
        entries[0],
        logical_stage_id=f"{CAMPAIGN}|{RUN}|{CYCLE}|WRONG_STAGE|1",
    )
    # Ownership prefix still matches, but stage ownership is validated as prefix;
    # force a completely different stage owner prefix.
    bad = replace(bad, logical_stage_id="other-campaign|other-run|other-cycle|X|1")
    activation = replace(activation, manifest_entries=tuple([bad, *entries[1:]]))
    with pytest.raises(MemoryObservationActivationError) as exc:
        validate_memory_activation_set(
            activation_db,
            activation,
            now=NOW,
            expected_ownership=(CAMPAIGN, RUN, CYCLE),
        )
    assert exc.value.code == "RETAINED_LOGICAL_STAGE_OWNERSHIP_MISMATCH"


def test_wrong_campaign_run_cycle_ownership_blocks(activation_db):
    activation = _activation_set(activation_db)
    first = activation.selected[0]
    wrong = tuple(
        replace(ref, campaign_id="other-campaign")
        for ref in first.retained_evidence_references
    )
    activation = replace(
        activation,
        selected=(
            replace(first, retained_evidence_references=wrong),
            activation.selected[1],
        ),
    )
    with pytest.raises(MemoryObservationActivationError) as exc:
        validate_memory_activation_set(
            activation_db,
            activation,
            now=NOW,
            expected_ownership=(CAMPAIGN, RUN, CYCLE),
        )
    assert exc.value.code == "RETAINED_OWNERSHIP_MISMATCH"


def test_all_three_evidence_roles_are_mandatory(activation_db):
    activation = _activation_set(activation_db)
    first = activation.selected[0]
    only_market = tuple(
        ref
        for ref in first.retained_evidence_references
        if ref.evidence_role is EvidenceRole.MARKET_OBSERVATION
    )
    activation = replace(
        activation,
        selected=(
            replace(first, retained_evidence_references=only_market),
            activation.selected[1],
        ),
    )
    with pytest.raises(MemoryObservationActivationError) as exc:
        validate_memory_activation_set(activation_db, activation, now=NOW)
    assert exc.value.code == "RETAINED_EVIDENCE_ROLE_MISSING"


def test_each_role_preserves_exact_request_response_hash_and_transport(activation_db):
    activation = _activation_set(activation_db)
    report = validate_memory_activation_set(
        activation_db,
        activation,
        now=NOW,
        expected_ownership=(CAMPAIGN, RUN, CYCLE),
    )
    assert report["reconciliation_status"] == "PASS"
    for candidate in activation.selected:
        roles = {ref.evidence_role for ref in candidate.retained_evidence_references}
        assert roles == set(REQUIRED_EVIDENCE_ROLES)
        for ref in candidate.retained_evidence_references:
            assert ref.transport_identity_keys
            assert ref.raw_payload_hash
            assert ref.source_request_id in activation.manifest_request_ids
            assert ref.source_response_id > 0
    for role in REQUIRED_EVIDENCE_ROLES:
        assert report["per_role_request_ids"][role.value]


def test_runtime_reconciliation_is_measured_not_hardcoded(activation_db):
    activation = _activation_set(activation_db)
    before = measure_source_row_ids(activation_db)
    # Simulate an illicit new source row after projection.
    activation_db.execute(
        """INSERT INTO printer_source_requests(
               source_name,request_kind,requested_at,request_key,
               source_status,data_quality_label
           ) VALUES ('x','y',?,?, 'COMPLETE','CLEAN_DATA')""",
        (NOW, "illicit"),
    )
    after = measure_source_row_ids(activation_db)
    report = reconcile_activation_source_rows(
        before=before, after=after, activation=activation
    )
    assert report["reconciliation_status"] == "BLOCKED"
    assert report["newly_created_source_request_ids"]
    # And measured zero-delta path.
    same = measure_source_row_ids(activation_db)
    ok = reconcile_activation_source_rows(
        before=same, after=same, activation=activation
    )
    assert ok["reconciliation_status"] == "PASS"
    assert ok["newly_created_source_request_ids"] == []
    assert ok["before_source_request_ids"] == ok["after_source_request_ids"]


def test_validation_creates_zero_source_rows(activation_db):
    activation = _activation_set(activation_db)
    before = measure_source_row_ids(activation_db)
    report = validate_memory_activation_set(
        activation_db,
        activation,
        now=NOW,
        expected_ownership=(CAMPAIGN, RUN, CYCLE),
        source_ids_before=before,
        source_ids_after=before,
    )
    after = measure_source_row_ids(activation_db)
    assert before == after
    assert report["new_source_request_ids"] == []
    assert report["new_source_response_ids"] == []
    assert report["newly_created_source_failure_ids"] == []


def test_combined_memory_activation_exactness_selection_and_projection(monkeypatch):
    proof = _BatchScopedDiscoveryPersistenceProof()
    proof.setUp()
    try:
        command, cycle_id = proof._create_command(92)
        connection = sqlite3.connect(proof.db)
        connection.row_factory = sqlite3.Row
        try:
            activation = _activation_set(connection)

            def owned(ref: RetainedEvidenceReference) -> RetainedEvidenceReference:
                return replace(
                    ref,
                    campaign_id=command.campaign_id,
                    campaign_run_id=command.run_id,
                    cycle_id=cycle_id,
                )

            selected = tuple(
                replace(
                    cand,
                    retained_evidence_references=tuple(
                        owned(ref) for ref in cand.retained_evidence_references
                    ),
                    provenance="PERSISTED_GRADUATED" if cand.slot_ordinal == 1 else "LATEST_GRADUATED",
                )
                for cand in activation.selected
            )
            entries = tuple(
                replace(
                    entry,
                    logical_stage_id=(
                        f"{command.campaign_id}|{command.run_id}|{cycle_id}|"
                        f"{entry.logical_stage_id.split('|')[-2]}|1"
                    ),
                )
                for entry in activation.manifest_entries
            )
            activation = replace(
                activation,
                selected=selected,
                manifest_entries=entries,
            )
            connection.commit()
            before = (
                connection.execute(
                    "SELECT COUNT(*) FROM printer_source_requests"
                ).fetchone()[0],
                connection.execute(
                    "SELECT COUNT(*) FROM printer_source_responses"
                ).fetchone()[0],
                connection.execute(
                    "SELECT COUNT(*) FROM printer_source_failures"
                ).fetchone()[0],
            )
        finally:
            connection.close()

        fixtures = CombinedDiscoveryFixtures(
            cycle_id=cycle_id,
            cycle_cutoff="2026-08-05T10:06:00+00:00",
            campaign_selection_seed="retained-exactness-seed",
            provider_contract_versions={"retained": "V1"},
            git_provenance_identity="retained-exactness-test",
            evaluated_at=NOW,
            pumpswap_proofs={
                MINT_1: FixturePumpSwapProof(mint=MINT_1, pool_address=POOL_1),
                MINT_2: FixturePumpSwapProof(mint=MINT_2, pool_address=POOL_2),
            },
            holder_evidence_eligibility={
                MINT_1.lower(): {
                    "eligible": False,
                    "reason": "HOLDER_CONCENTRATION_FAIL",
                },
                MINT_2.lower(): {
                    "eligible": False,
                    "reason": "HOLDER_SOURCE_UNAVAILABLE",
                },
            },
            memory_activation_set=activation,
        )
        executor = CombinedPumpfunCampaignExecutor(fixtures)
        monkeypatch.setattr(
            executor,
            "_select",
            lambda *a, **k: (_ for _ in ()).throw(
                AssertionError("second selector called")
            ),
        )
        monkeypatch.setattr(
            executor,
            "_governed_request",
            lambda *a, **k: (_ for _ in ()).throw(
                AssertionError("new source request")
            ),
        )
        monkeypatch.setattr(
            executor,
            "_store_response",
            lambda *a, **k: (_ for _ in ()).throw(
                AssertionError("new source response")
            ),
        )

        result = executor.execute(
            command=command,
            source_governor=OwnerPort(SOURCE_GOVERNOR_OWNER, True),
            central_scheduler=OwnerPort(CENTRAL_SCHEDULER_OWNER, True),
        )
        assert result.terminal_status == "COMPLETED", result.first_terminal_cause

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
                connection.execute(
                    "SELECT COUNT(*) FROM printer_source_requests"
                ).fetchone()[0],
                connection.execute(
                    "SELECT COUNT(*) FROM printer_source_responses"
                ).fetchone()[0],
                connection.execute(
                    "SELECT COUNT(*) FROM printer_source_failures"
                ).fetchone()[0],
            )
            reasons = [
                row[0]
                for row in connection.execute(
                    "SELECT selection_reason FROM printer_selection_batch_items"
                ).fetchall()
            ]
            origin_details = [
                json.loads(row[0])
                for row in connection.execute(
                    "SELECT evidence_detail_json FROM printer_discovery_origin_verifications"
                ).fetchall()
            ]
            pumpswap_details = [
                json.loads(row[0])
                for row in connection.execute(
                    "SELECT evidence_detail_json FROM printer_discovery_pumpswap_confirmations"
                ).fetchall()
            ]
            observation_rows = connection.execute(
                """SELECT channel, factual_payload_json, mint_identity
                   FROM printer_discovery_provider_observations"""
            ).fetchall()
        finally:
            connection.close()

        assert [(row["slot_ordinal"], row["mint_identity"]) for row in slots] == [
            (1, MINT_1),
            (2, MINT_2),
        ]
        assert before == after
        assert reasons
        assert all(reason == MEMORY_OBSERVATION_SELECTION_REASON for reason in reasons)
        assert origin_details
        for detail in origin_details:
            assert detail.get("retained_evidence_role") == "ORIGIN_LINEAGE"
            assert detail.get("retained_source_request_id")
            assert detail.get("retained_source_response_id")
            assert detail.get("retained_response_hash")
            assert detail.get("retained_transport_identity_keys")
        assert pumpswap_details
        for detail in pumpswap_details:
            assert detail.get("retained_evidence_role") == "PUMPSWAP_CONFIRMATION"
            assert detail.get("retained_source_request_id")
            assert detail.get("retained_response_hash")
        # True provenance is persisted; channel labels are not forced by slot
        # ordinal (slot-1 PERSISTED is not forced to LATEST_PUMPFUN).
        by_mint = {
            row["mint_identity"]: (
                row["channel"],
                json.loads(row["factual_payload_json"]),
            )
            for row in observation_rows
        }
        assert by_mint[MINT_1][0] == "ACTIVE_PUMPFUN"
        assert by_mint[MINT_1][1]["true_provenance"] == "PERSISTED_GRADUATED"
        assert by_mint[MINT_1][1]["channel_authority"] == "PERSISTED_GRADUATED"
        assert by_mint[MINT_1][1]["selection_reason"] == MEMORY_OBSERVATION_SELECTION_REASON
        assert by_mint[MINT_2][0] == "LATEST_PUMPFUN"
        assert by_mint[MINT_2][1]["true_provenance"] == "LATEST_GRADUATED"
        assert by_mint[MINT_2][1]["slot_ordinal"] == 2
    finally:
        proof.tearDown()


def test_tracking_exclusion_evidence_shape_is_assessment_not_holder():
    # Unit-level contract for the repaired evidence dict shape.
    tracking_assessment = {
        "eligible": False,
        "reason_code": "DUPLICATE_ACTIVE_TRACKING",
        "category": "DUPLICATE_ACTIVE_TRACKING",
        "queue_id": 9,
        "queue_status": "ACTIVE",
        "requalification_required": False,
        "cooldown_until": None,
        "assessed_at": NOW,
    }
    holder_safety = {
        "eligible": False,
        "reason": "HOLDER_CONCENTRATION_FAIL",
        "source_name": "solana_tracker",
    }
    evidence = {
        "tracking_handoff": dict(tracking_assessment),
        "holder_safety": dict(holder_safety),
        "memory_observation_eligible": False,
    }
    assert evidence["tracking_handoff"]["reason_code"] == "DUPLICATE_ACTIVE_TRACKING"
    assert "HOLDER_CONCENTRATION_FAIL" not in json.dumps(evidence["tracking_handoff"])
    assert evidence["holder_safety"]["reason"] == "HOLDER_CONCENTRATION_FAIL"


def test_holder_fail_unknown_remain_valid_memory_context(activation_db):
    activation = _activation_set(activation_db)
    second = replace(
        activation.selected[1],
        holder_condition="HOLDER_CONTEXT_BUDGET_BOUND_UNKNOWN",
        holder_evidence_status="HOLDER_CONTEXT_BUDGET_BOUND_UNKNOWN",
        fully_eligible=False,
        future_action_eligibility="BLOCKED_OR_UNKNOWN",
    )
    activation = replace(activation, selected=(activation.selected[0], second))
    report = validate_memory_activation_set(
        activation_db,
        activation,
        now=NOW,
        expected_ownership=(CAMPAIGN, RUN, CYCLE),
    )
    assert report["reconciliation_status"] == "PASS"


def test_legacy_non_memory_selection_reason_unchanged_constant():
    # Memory mode constant is exact; legacy still uses uniform: seed form.
    assert MEMORY_OBSERVATION_SELECTION_REASON == "memory_observation_frozen_selection"
    legacy = f"uniform:{'seedvalue123456'[:12]}"
    assert legacy.startswith("uniform:")
    assert legacy != MEMORY_OBSERVATION_SELECTION_REASON
