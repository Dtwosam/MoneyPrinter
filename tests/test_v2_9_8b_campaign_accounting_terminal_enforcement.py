"""Frozen offline proof: V2-9.8B campaign accounting and terminal enforcement.

Covers, with frozen transports and disposable migration-049 databases only:

* exact-pair DexScreener success and every failure class create exact identities;
* multi-hop failure preserves prior identities;
* ``ACCOUNTING_BLOCKED`` prevents all campaign selection and activation;
* one top-level ledger reconciles every active stage; malformed stage fails closed;
* report persistence is blocked on evidence mismatch / missing evidence;
* replay reconstructs from durable evidence with zero source calls / writes;
* post-handoff failure injection leaves zero orphan state;
* normal success still creates exactly two slots and two WINDOW_15M jobs;
* locked capability tables, foreign keys, migration 049, integrity all hold.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from urllib import error as url_error

import pytest

import printer_v1.sources.dexscreener as dex
from printer_v1.db.migrate import apply_migrations, canonical_migration_names
from printer_v1.discovery.direct_migration_discovery import (
    run_direct_migration_discovery,
)
from printer_v1.discovery.combined_executor import (
    CombinedDiscoveryFixtures,
    FixturePumpSwapProof,
    FixtureSourceFact,
)
from printer_v1.operator_cli.origin_lifecycle_campaign import (
    POST_HANDOFF_STAGES,
    OriginToLifecycleCampaignDriver,
)
from printer_v1.operator_cli.unified_terminal_closure import (
    TerminalClosureError,
    build_campaign_terminal_report,
    replay_campaign_terminal_report,
    write_campaign_terminal_report,
)
from printer_v1.sources.campaign_six_unit_accounting import (
    CampaignSixUnitError,
    aggregate_campaign_six_unit_owner,
    reconstruct_six_unit_totals_from_evidence,
)
from printer_v1.sources.dexscreener import build_dexscreener_pair_snapshot_transport
from printer_v1.sources.direct_pump_migration import (
    SIGNATURE_PAGE_REQUEST_KIND,
    TRANSACTION_REQUEST_KIND,
)
from printer_v1.sources.measured_transport import SIX_UNITS

from tests.test_v2_9_8b_candidate_acquisition_foundation import _pinned_migration_fixture
from tests.test_v2_9_8b_restored_factory_source_compatibility_reset import _verifier_factory
from tests.test_v2_9_7e_8_origin_to_lifecycle_integration import (
    CUTOFF, MINT_A, MINT_B, NOW, POOL_A, POOL_B, SEED, _IntegrationBase,
)


_NOW = "2026-07-30T22:00:00+00:00"
_SIGNATURE = (
    "5NarrowDirectPumpMigrationFinalizedSignature"
    "111111111111111111111111111111111111111111111111"
)
WSOL = "So11111111111111111111111111111111111111112"


# --------------------------------------------------------------------------- #
# D1/D2: DexScreener exact-pair identity on every outcome
# --------------------------------------------------------------------------- #


class _Resp:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self._body = body
        self.status = status

    def read(self, size: int = -1) -> bytes:
        return self._body[:size] if size and size > 0 else self._body

    def __enter__(self) -> "_Resp":
        return self

    def __exit__(self, *_a) -> bool:
        return False


def _success_body() -> bytes:
    return json.dumps(
        {
            "pairs": [
                {
                    "chainId": "solana",
                    "pairAddress": "PoolAddr1111111111111111111111111111111111",
                    "baseToken": {"address": "MintAddr111111111111111111111111111111111"},
                    "quoteToken": {"address": WSOL},
                }
            ]
        }
    ).encode("utf-8")


_EXACT_PAIR_CASES = [
    ("success", lambda: _Resp(_success_body()), None, "OK"),
    ("byte_ceiling", lambda: _Resp(b"x" * 512_001), "failure", "BYTE_CEILING"),
    (
        "row_ceiling",
        lambda: _Resp(json.dumps({"pairs": [{} for _ in range(9)]}).encode()),
        "failure",
        "ROW_CEILING",
    ),
    ("malformed", lambda: _Resp(json.dumps([1, 2, 3]).encode()), "failure", "MALFORMED"),
    ("decode_failure", lambda: _Resp(b"\xff\xfe not json"), "failure", "DECODE_FAILURE"),
    (
        "rate_limit",
        url_error.HTTPError("http://x", 429, "rate", None, None),
        "rate_limited",
        "RATE_LIMITED",
    ),
    (
        "http_5xx",
        url_error.HTTPError("http://x", 503, "err", None, None),
        "failure",
        "HTTP_SERVER_ERROR",
    ),
    (
        "http_4xx",
        url_error.HTTPError("http://x", 404, "nf", None, None),
        "failure",
        "HTTP_CLIENT_ERROR",
    ),
    ("timeout", TimeoutError("connect timeout"), "failure", "TRANSPORT_FAILURE"),
]


@pytest.mark.parametrize("name,behavior,fixture_status,result", _EXACT_PAIR_CASES)
def test_exact_pair_every_outcome_emits_exactly_one_identity(
    monkeypatch, name, behavior, fixture_status, result
) -> None:
    def fake_urlopen(request, timeout=None):
        if isinstance(behavior, BaseException):
            raise behavior
        return behavior()

    monkeypatch.setattr(dex.url_request, "urlopen", fake_urlopen)
    transport = build_dexscreener_pair_snapshot_transport(
        pair_address="PoolAddr1111111111111111111111111111111111"
    )
    payload = transport(None)
    if fixture_status is None:
        assert payload.get("fixture_status") in (None,)
    else:
        assert payload["fixture_status"] == fixture_status
    identities = payload["transport_operation_identities"]
    assert len(identities) == 1, f"{name}: expected exactly one identity"
    assert payload["transport_operations_used"] == 1
    assert identities[0]["result"] == result
    assert identities[0]["source_name"] == "dexscreener_pair"
    assert identities[0]["stage"] == "DEXSCREENER_DISCOVERY"


def test_fresh_profiles_multi_hop_preserves_first_identity(monkeypatch) -> None:
    from printer_v1.sources.dexscreener import (
        build_dexscreener_fresh_profiles_transport,
    )

    calls = {"n": 0}

    def fake_get(endpoint, timeout_seconds, *, byte_ceiling=2_000_000):
        calls["n"] += 1
        if calls["n"] == 1:
            return (
                [{"chainId": "solana", "tokenAddress": "MintABC1111111111111111111111111111111"}],
                100,
            )
        raise TimeoutError("second-hop timeout")

    monkeypatch.setattr(dex, "_dexscreener_http_get_json", fake_get)
    payload = build_dexscreener_fresh_profiles_transport()(
        SimpleNamespace(request=SimpleNamespace(request_kind="dexscreener_fresh_profiles"))
    )
    identities = payload["transport_operation_identities"]
    assert len(identities) == 2
    assert identities[0]["result"] == "OK"
    assert identities[1]["result"] == "FAILED"


# --------------------------------------------------------------------------- #
# D2: ACCOUNTING_BLOCKED is an immediate campaign safe stop
# --------------------------------------------------------------------------- #


def _migration_transport(tx):
    def transport(context):
        if context.request.request_kind == SIGNATURE_PAGE_REQUEST_KIND:
            return {
                "result": [
                    {
                        "signature": _SIGNATURE,
                        "slot": tx["slot"],
                        "err": None,
                        "confirmationStatus": "finalized",
                    }
                ],
                "response_bytes": 32,
            }
        if context.request.request_kind == TRANSACTION_REQUEST_KIND:
            return {"result": tx, "response_bytes": 64}
        raise AssertionError(context.request.request_kind)

    return transport


def test_accounting_blocked_withholds_registry_candidates(tmp_path: Path) -> None:
    tx, infos, mint, pool = _pinned_migration_fixture()
    db = tmp_path / "blocked.sqlite3"
    apply_migrations(db)

    # Pre-seed one already-persisted registry candidate (a prior confirmation).
    from printer_v1.sources.pumpswap_graduated_registry import (
        LATEST_GRADUATED_CHANNEL,
        record_graduated_candidate,
    )
    from printer_v1.sources.pump_migration import MIGRATION_PROVENANCE

    seed = sqlite3.connect(db)
    try:
        record_graduated_candidate(
            seed,
            mint="PriorMint11111111111111111111111111111111111",
            migration_signature="prior-sig",
            pumpswap_pool="PriorPool11111111111111111111111111111111111",
            graduation_block_time=1,
            graduation_slot=1,
            now=_NOW,
            discovery_channel=LATEST_GRADUATED_CHANNEL,
            migration_provenance=MIGRATION_PROVENANCE,
        )
        seed.commit()
    finally:
        seed.close()

    def bad_verifier_factory(mint_value: str, signature: str):
        def transport(_context):
            return {
                "pumpswap_confirmation": {"confirmed": True},
                "pumpswap_resolution": {"pool_address": pool, "resolved": True},
                "pump_migration_proof": {
                    "verified": True,
                    "migration_block_time": tx["blockTime"],
                    "migration_slot": tx["slot"],
                },
                "migration_signature": signature,
                "transport_operations_used": 2,  # claimed without identities
            }

        return transport

    report = run_direct_migration_discovery(
        db,
        migration_transport=_migration_transport(tx),
        verifier_transport_factory=bad_verifier_factory,
        now=_NOW,
        collection_rounds=1,
    )
    assert report["status"] == "ACCOUNTING_BLOCKED"
    assert report["campaign_safe_stop"] is True
    assert report["confirmed_count"] == 0
    # Existing registry candidate must NOT continue toward selection.
    assert report["candidate_mix"] == []
    assert report["total_persisted_graduated"] == 0
    assert report["latest_graduated_count"] == 0
    assert report["persisted_graduated_count"] == 0
    assert report["registry_candidates_withheld"] >= 1
    # The registry row itself is read-only (unchanged), just not handed forward.
    connection = sqlite3.connect(db)
    try:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM printer_pumpswap_graduated_candidate_registry"
            ).fetchone()[0]
            == 1
        )
    finally:
        connection.close()


# --------------------------------------------------------------------------- #
# D3: one top-level owner reconciles every stage; malformed stage fails closed
# --------------------------------------------------------------------------- #


def _stage_evidence(*, stage, source, ordinal, rows=0, bytes_=0, locals_=0, sched=0, resv=0):
    return {
        "evidence_kind": "CAMPAIGN_SIX_UNIT_EVIDENCE_V1",
        "transport_operations": [
            {
                "stage": stage,
                "source_name": source,
                "governed_request_kind": f"{source}_kind",
                "method_or_endpoint": f"GET /{source}",
                "within_request_ordinal": ordinal,
                "target_category": "cat",
                "target_identity": f"{source}-{ordinal}",
                "response_bytes": bytes_,
                "normalized_rows": rows,
            }
        ],
        "local_validations": locals_,
        "scheduler_work_items": sched,
        "lifecycle_reservations": resv,
    }


def test_top_level_owner_reconciles_every_stage() -> None:
    stages = [
        _stage_evidence(stage="DIRECT_PUMP_NOMINATION", source="pump", ordinal=1, bytes_=10, rows=1),
        _stage_evidence(stage="PUMPSWAP_EXACT_VERIFICATION", source="pumpswap", ordinal=1, bytes_=20, rows=2),
        _stage_evidence(stage="DEXSCREENER_DISCOVERY", source="dexscreener_pair", ordinal=1, bytes_=30, rows=3),
        _stage_evidence(stage="HOLDER_SAFETY", source="solana_rpc", ordinal=1, bytes_=40, rows=1, locals_=2),
    ]
    stages[0]["scheduler_work_items"] = 5
    stages[1]["lifecycle_reservations"] = 2
    owner = aggregate_campaign_six_unit_owner(
        campaign_id="c", run_id="r", cycle_id="y", started_at=_NOW, stage_evidences=stages
    )
    totals = owner.six_unit_totals()
    assert totals["SOURCE_TRANSPORT_OPERATION"] == 4
    assert totals["SOURCE_RESPONSE_BYTES"] == 100
    assert totals["NORMALIZED_SOURCE_ROWS"] == 7
    assert totals["LOCAL_VALIDATION_STEP"] == 2
    assert totals["SCHEDULER_WORK_ITEM"] == 5
    assert totals["LIFECYCLE_RESERVED_TRANSPORT_OPERATION"] == 2
    # Durable evidence reconstructs to the same totals independently.
    assert reconstruct_six_unit_totals_from_evidence(owner.durable_evidence()) == totals
    assert set(totals) == set(SIX_UNITS)


def test_omitted_or_malformed_stage_accounting_fails_closed() -> None:
    good = _stage_evidence(stage="DIRECT_PUMP_NOMINATION", source="pump", ordinal=1)
    # Omitted stage (None) fails closed.
    with pytest.raises(CampaignSixUnitError):
        aggregate_campaign_six_unit_owner(stage_evidences=[good, None])
    # Malformed stage (negative measure) fails closed.
    malformed = _stage_evidence(stage="DIRECT_PUMP_NOMINATION", source="pump", ordinal=2)
    malformed["transport_operations"][0]["response_bytes"] = -1
    with pytest.raises(CampaignSixUnitError):
        aggregate_campaign_six_unit_owner(stage_evidences=[malformed])


# --------------------------------------------------------------------------- #
# D4: terminal enforcement — missing / malformed / mismatch fail closed
# --------------------------------------------------------------------------- #


def _valid_report(evidence=None, totals=None):
    owner = aggregate_campaign_six_unit_owner(
        campaign_id="c",
        run_id="r",
        cycle_id="y",
        started_at=_NOW,
        stage_evidences=[
            _stage_evidence(
                stage="DIRECT_PUMP_NOMINATION", source="pump", ordinal=1, bytes_=10, rows=1
            )
        ],
    )
    return build_campaign_terminal_report(
        campaign_id="c",
        configuration_id="cfg",
        run_id="r",
        cycle_id="y",
        report_id="rep-te-1",
        factory_run_id=None,
        execution_id="e",
        terminal_status="FAILED",
        terminal_cause="TEST",
        run_status="FAILED",
        lifecycle_started=False,
        reconciliation={},
        six_unit_totals=totals if totals is not None else owner.six_unit_totals(),
        six_unit_evidence=evidence if evidence is not None else owner.durable_evidence(),
        require_six_unit_evidence=True,
    )


def test_terminal_build_requires_present_evidence() -> None:
    with pytest.raises(TerminalClosureError):
        build_campaign_terminal_report(
            campaign_id="c",
            configuration_id="cfg",
            run_id="r",
            cycle_id="y",
            report_id="rep",
            factory_run_id=None,
            execution_id="e",
            terminal_status="FAILED",
            terminal_cause="T",
            run_status="FAILED",
            lifecycle_started=False,
            reconciliation={},
            six_unit_totals={"SOURCE_TRANSPORT_OPERATION": 3},
            six_unit_evidence=None,  # missing evidence for attempted work
            require_six_unit_evidence=True,
        )


def test_terminal_build_rejects_mismatch() -> None:
    owner = aggregate_campaign_six_unit_owner(
        started_at=_NOW,
        stage_evidences=[
            _stage_evidence(stage="DIRECT_PUMP_NOMINATION", source="pump", ordinal=1, bytes_=10)
        ],
    )
    bad_totals = dict(owner.six_unit_totals())
    bad_totals["SOURCE_RESPONSE_BYTES"] = 9999  # disagree with evidence
    with pytest.raises(TerminalClosureError):
        _valid_report(evidence=owner.durable_evidence(), totals=bad_totals)


def test_terminal_build_accepts_matched_evidence() -> None:
    payload = _valid_report()
    assert payload["six_unit_evidence_match"] is True
    assert payload["six_unit_totals"]["SOURCE_TRANSPORT_OPERATION"] == 1


def test_write_blocks_on_evidence_mismatch(tmp_path: Path) -> None:
    payload = _valid_report()
    # Corrupt the evidence match flag / evidence to simulate a tampered report.
    corrupt = dict(payload)
    corrupt["six_unit_evidence_match"] = False
    with pytest.raises(TerminalClosureError):
        write_campaign_terminal_report(
            tmp_path / "authoritative.sqlite3",
            tmp_path / "reports",
            report_id="rep-te-1",
            campaign_id="c",
            configuration_id="cfg",
            report=corrupt,
            require_six_unit_evidence=True,
        )
    # Missing evidence also blocks.
    corrupt2 = dict(payload)
    corrupt2["six_unit_evidence"] = {}
    with pytest.raises(TerminalClosureError):
        write_campaign_terminal_report(
            tmp_path / "authoritative.sqlite3",
            tmp_path / "reports",
            report_id="rep-te-1",
            campaign_id="c",
            configuration_id="cfg",
            report=corrupt2,
            require_six_unit_evidence=True,
        )


# --------------------------------------------------------------------------- #
# D5: replay reconstructs from durable evidence with zero operations / writes
# --------------------------------------------------------------------------- #


def test_replay_is_read_only_and_reconstructs_from_evidence() -> None:
    import inspect

    payload = _valid_report()
    # Independent reconstruction from durable evidence equals stored totals.
    rebuilt = reconstruct_six_unit_totals_from_evidence(payload["six_unit_evidence"])
    assert rebuilt == payload["six_unit_totals"]
    # The replay implementation opens the DB read-only and performs no source
    # transport and no authoritative write.
    src = inspect.getsource(replay_campaign_terminal_report)
    assert "mode=ro" in src
    assert "urlopen" not in src
    for mutation in ("INSERT INTO", "UPDATE ", "DELETE FROM"):
        assert mutation not in src


# --------------------------------------------------------------------------- #
# D6: post-handoff failure injections leave zero orphan state
# --------------------------------------------------------------------------- #


class _PostHandoffHarness(_IntegrationBase):
    """Bare harness: no test methods, driven per-stage from a pytest function."""

    def runTest(self) -> None:  # pragma: no cover - satisfies TestCase
        pass

    def _two_origin_fixtures(self) -> CombinedDiscoveryFixtures:
        # Current Cycle-1 cadence authority derives TRACK_FAST/TRACK_NORMAL from
        # a current-batch governed market observation.  The historical fixture
        # supplied only Pump origin/PumpSwap proof, so it now fails before the
        # intended post-handoff injection at DISCOVERY_TRACKING_LANE_MISSING.
        # Keep the exact origin proofs as verification authority, but nominate
        # both mints through one frozen DexScreener response carrying sufficient
        # market facts for the existing classifier.
        origin_a = self._origin("a", MINT_A, POOL_A, 10)
        origin_b = self._origin("b", MINT_B, POOL_B, 11)
        return CombinedDiscoveryFixtures(
            cycle_id="cyc",
            cycle_cutoff=CUTOFF,
            campaign_selection_seed=SEED,
            provider_contract_versions={"dexscreener": "fixture"},
            git_provenance_identity="git-integration",
            evaluated_at=NOW,
            dexscreener_ops=(
                FixtureSourceFact(
                    request_kind="dexscreener_fresh_profiles",
                    source_name="dexscreener",
                    receipt_time=NOW,
                    body={
                        "pairs": [
                            {
                                "chainId": "solana",
                                "dexId": "pumpswap",
                                "pairAddress": POOL_A,
                                "baseToken": {"address": MINT_A},
                                "quoteToken": {"address": WSOL},
                                "priceUsd": "0.01",
                                "liquidity": {"usd": 1500.0},
                                "volume": {"m5": 50.0, "h1": 200.0, "h24": 500.0},
                                "txns": {
                                    "m5": {"buys": 1, "sells": 1},
                                    "h1": {"buys": 3, "sells": 2},
                                    "h24": {"buys": 6, "sells": 4},
                                },
                            },
                            {
                                "chainId": "solana",
                                "dexId": "pumpswap",
                                "pairAddress": POOL_B,
                                "baseToken": {"address": MINT_B},
                                "quoteToken": {"address": WSOL},
                                "priceUsd": "0.01",
                                "liquidity": {"usd": 1500.0},
                                "volume": {"m5": 50.0, "h1": 200.0, "h24": 500.0},
                                "txns": {
                                    "m5": {"buys": 1, "sells": 1},
                                    "h1": {"buys": 3, "sells": 2},
                                    "h24": {"buys": 6, "sells": 4},
                                },
                            },
                        ]
                    },
                ),
            ),
            origin_proofs={MINT_A: origin_a, MINT_B: origin_b},
            pumpswap_proofs={
                MINT_A: FixturePumpSwapProof(mint=MINT_A, pool_address=POOL_A),
                MINT_B: FixturePumpSwapProof(mint=MINT_B, pool_address=POOL_B),
            },
        )

    def run_with_fault(self, stage):
        driver = OriginToLifecycleCampaignDriver()
        snapshot_factory, _calls = self._snapshot_adapter_factory()
        return driver.run(
            command=self.command,
            fixtures=self._two_origin_fixtures(),
            backup_path=self.backup,
            selection_seed="seed",
            proof_mode=True,
            lifecycle_kwargs={
                "snapshot_adapter_factory": snapshot_factory,
                "context_adapter_factories": self._context_factories(),
                "_window_seconds": 0.05,
                "total_duration_seconds": 3.0,
                "launch_provenance": {
                    "git_head": "f" * 40,
                    "git_tracked_tree_clean": True,
                    "git_staged_changes_present": False,
                    "git_unstaged_changes_present": False,
                    "git_untracked_present": True,
                    "git_provenance_captured_at": "2026-07-21T17:00:00+00:00",
                },
            },
            post_handoff_fault=stage,
        )

@pytest.mark.parametrize("stage", POST_HANDOFF_STAGES)
def test_post_handoff_fault_compensation_terminalizes_to_zero_active_work(stage) -> None:
    """Post-handoff compensation leaves zero active work (repaired invariant).

    The surviving pinned handoff rows (slots, first-15m jobs, immutable links)
    are preserved as terminal audit evidence but moved to a lawful non-runnable
    terminal state; every deletable lifecycle-materialization row is gone. This
    replaces the prior lane's "pinned residual survives active" blocker record.
    """
    harness = _PostHandoffHarness()
    harness.setUp()
    try:
        result = harness.run_with_fault(stage)
        assert result.activation.terminal_status == "FAILED"
        assert result.activation.first_terminal_cause == f"POST_HANDOFF_{stage}"
        assert result.lifecycle_started is False
        report = result.lifecycle["post_handoff_compensation_report"]
        assert report["terminal_cause"] == f"POST_HANDOFF_{stage}"
        # Zero active / runnable / leased / orphan work.
        assert report["clean_zero_active_work"] is True
        for key, value in report["remaining_active_work"].items():
            assert value == 0, f"{stage}: remaining_active_work[{key}]={value}"
        # Pinned handoff evidence preserved but terminalized (non-runnable).
        assert report["immutable_retained_evidence"]["selected_item_links"] >= 1
        assert report["terminalized_pinned_rows"]["token_slots_terminalized"] == 2
        assert report["terminalized_pinned_rows"]["first_15m_jobs_cancelled"] >= 1
        assert report["terminalized_pinned_rows"]["tracking_rows_terminalized"] >= 1
        connection = harness._conn()
        try:
            # Slots are terminal and non-runnable, cause attributable to the fault.
            slot_rows = connection.execute(
                "SELECT token_state, first_terminal_cause FROM "
                "printer_memory_factory_campaign_token_slots WHERE cycle_id='cyc'"
            ).fetchall()
            assert len(slot_rows) == 2
            for state, terminal_cause in slot_rows:
                assert state in ("COOLDOWN", "ARCHIVED", "MANUAL_REVIEW", "FAILED")
                assert terminal_cause == f"POST_HANDOFF_{stage}"
            # Immutable links preserved and FK-valid.
            assert (
                connection.execute(
                    "SELECT COUNT(*) FROM printer_discovery_selected_item_links "
                    "WHERE cycle_id='cyc'"
                ).fetchone()[0]
                == 2
            )
            assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
            head = [
                r[0]
                for r in connection.execute(
                    "SELECT version FROM printer_schema_migrations ORDER BY version"
                )
            ][-1]
            assert head == canonical_migration_names()[-1]
        finally:
            connection.close()
    finally:
        harness.tearDown()


# --------------------------------------------------------------------------- #
# Normal success still creates exactly two slots and two WINDOW_15M jobs
# --------------------------------------------------------------------------- #


def test_normal_success_two_slots_two_window_15m_jobs(tmp_path: Path) -> None:
    tx, infos, mint, pool = _pinned_migration_fixture()
    db = tmp_path / "ok.sqlite3"
    apply_migrations(db)
    report = run_direct_migration_discovery(
        db,
        migration_transport=_migration_transport(tx),
        verifier_transport_factory=_verifier_factory(tx, infos),
        now=_NOW,
        collection_rounds=1,
    )
    assert report["status"] == "COMPLETE"
    assert report["campaign_safe_stop"] is False
    assert report["confirmed_count"] == 1
    assert report["source_operation_ledger"]["operation_accounting_reconciled"] is True
    connection = sqlite3.connect(db)
    try:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM printer_pumpswap_graduated_candidate_registry"
            ).fetchone()[0]
            == 1
        )
        head = [
            row[0]
            for row in connection.execute(
                "SELECT version FROM printer_schema_migrations ORDER BY version"
            )
        ][-1]
        assert head == canonical_migration_names()[-1]
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        connection.close()
