from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from datetime import timedelta
from unittest.mock import patch

import pytest

from printer_v1.operator_cli.one_command_15m_factory import (
    run_one_command_15m_factory,
)
from printer_v1.operator_cli.operational_database_target_binding import (
    AUTHORIZED_DISPOSABLE_OPERATIONAL_PROOF,
    PRODUCTION_AUTHORITATIVE,
    OperationalDatabaseTargetBinding,
    validate_operational_database_target_binding,
)
from printer_v1.sources.goplus import build_goplus_token_safety_transport
from printer_v1.sources.measured_transport import MeasuredTransportLedger
from printer_v1.sources.solana_rpc_holder import build_solana_rpc_holder_transport
from printer_v1.operator_cli.holder_reliability_budget_control import (
    _measure_holder_transport_count,
)
from printer_v1.operator_cli.continuous_proof_evidence_retention import (
    ContinuousProofEvidenceError,
    MANDATORY_RETAINED_ARTIFACTS,
    capture_public_command_main,
    parse_final_child_terminal,
    retain_required_artifacts,
    terminal_truth_projection,
    write_proof_diagnostic_artifacts,
)
from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    AuthoritativeLiveOperationalCampaignOwner,
)
import printer_v1.operator_cli.holder_reliability_budget_control as holder_budget
import test_v2_9_8b_holder_partial_accounting_repair as holder_fixtures


def _binding(path: Path, *, target_kind: str = PRODUCTION_AUTHORITATIVE, **changes):
    values = {
        "binding_version": "OPERATIONAL_DATABASE_TARGET_BINDING_V1",
        "target_kind": target_kind,
        "resolved_db_path": str(path.resolve()),
        "authorized_pre_mutation_sha256": "a" * 64,
        "migration_count": 52,
        "migration_head": "052_memory_observation_eligibility_layers.sql",
        "db_target_identity": f"sha256:{'a' * 64}",
        "authorization_id": "authorization-1",
        "authorization_marker_sha256": "b" * 64,
        "application_marker_sha256": "c" * 64,
        "execution_id": "execution-1",
        "campaign_id": "campaign-1",
        "campaign_run_id": "run-1",
        "cycle_id": "cycle-1",
        "configuration_id": "configuration-1",
        "authorization_consumed_once": True,
        "invocation_count": 1,
        "allowed_invocation_count": 1,
        "automatic_retry_allowed": False,
        "manual_rerun_allowed": False,
        "resume_allowed": False,
        "restart_allowed": False,
        "successor_allowed": False,
    }
    values.update(changes)
    return OperationalDatabaseTargetBinding(**values)


def _expected(path: Path, *, disposable: bool = False) -> dict:
    expected = {
        "authorized_pre_mutation_sha256": "a" * 64,
        "migration_count": 52,
        "migration_head": "052_memory_observation_eligibility_layers.sql",
        "durable_db_target_identity": f"sha256:{'a' * 64}",
        "authorization_id": "authorization-1",
        "authorization_marker_sha256": "b" * 64,
        "application_marker_sha256": "c" * 64,
        "execution_id": "execution-1",
        "campaign_id": "campaign-1",
        "campaign_run_id": "run-1",
        "cycle_id": "cycle-1",
        "configuration_id": "configuration-1",
        "authorization_consumed_once": True,
        "invocation_count": 1,
        "automatic_retry_allowed": False,
        "manual_rerun_allowed": False,
        "resume_allowed": False,
        "restart_allowed": False,
        "successor_allowed": False,
        "disposable_proof_identity": None,
    }
    if disposable:
        expected["fixture_authorization"] = {
            "resolved_db_path": str(path.resolve()),
            "authorized_pre_mutation_sha256": "a" * 64,
            "authorization_id": "authorization-1",
            "authorization_marker_sha256": "b" * 64,
            "application_marker_sha256": "c" * 64,
            "execution_id": "execution-1",
            "campaign_id": "campaign-1",
            "campaign_run_id": "run-1",
            "cycle_id": "cycle-1",
            "configuration_id": "configuration-1",
            "migration_count": 52,
            "migration_head": "052_memory_observation_eligibility_layers.sql",
            "allowed_invocation_count": 1,
            "automatic_retry_allowed": False,
            "manual_rerun_allowed": False,
            "resume_allowed": False,
            "restart_allowed": False,
            "successor_allowed": False,
        }
    return expected


def test_operational_persistent_factory_requires_database_target_binding(
    tmp_path: Path,
) -> None:
    database = tmp_path / "fixture.sqlite3"
    backup = tmp_path / "fixture.backup.sqlite3"
    database.write_bytes(b"fixture")
    backup.write_bytes(b"backup")

    result = run_one_command_15m_factory(
        database,
        backup,
        operator_approved=True,
        proof_mode=False,
        operational_persistent_mode=True,
        total_duration_seconds=901.0,
    )

    assert result["run_status"] == "SAFE_STOPPED"
    assert "OPERATIONAL_DB_BINDING_MISSING" in result["blocked_reasons"]


def test_production_binding_accepts_only_canonical_database(tmp_path: Path) -> None:
    canonical = tmp_path / "printer_v1.sqlite3"
    expected = _expected(canonical)
    assert validate_operational_database_target_binding(
        _binding(canonical),
        actual_db_path=canonical,
        canonical_authoritative_db_path=canonical,
        expected=expected,
    ) is None

    other = tmp_path / "other.sqlite3"
    assert validate_operational_database_target_binding(
        _binding(other),
        actual_db_path=other,
        canonical_authoritative_db_path=canonical,
        expected=expected,
    ) == "OPERATIONAL_DB_BINDING_PRODUCTION_PATH_MISMATCH"


def test_disposable_binding_requires_exact_fixture_authorization(tmp_path: Path) -> None:
    canonical = tmp_path / "printer_v1.sqlite3"
    disposable = tmp_path / "proof.sqlite3"
    expected = _expected(disposable, disposable=True)
    binding = _binding(
        disposable, target_kind=AUTHORIZED_DISPOSABLE_OPERATIONAL_PROOF
    )
    assert validate_operational_database_target_binding(
        binding,
        actual_db_path=disposable,
        canonical_authoritative_db_path=canonical,
        expected=expected,
    ) is None

    expected["fixture_authorization"]["resolved_db_path"] = str(
        (tmp_path / "wrong.sqlite3").resolve()
    )
    assert validate_operational_database_target_binding(
        binding,
        actual_db_path=disposable,
        canonical_authoritative_db_path=canonical,
        expected=expected,
    ) == "OPERATIONAL_DB_BINDING_AUTHORIZATION_MISMATCH"


@pytest.mark.parametrize(
    ("binding_change", "expected_change", "reason"),
    [
        ({"target_kind": "OTHER"}, {}, "OPERATIONAL_DB_BINDING_KIND_INVALID"),
        ({"authorized_pre_mutation_sha256": "d" * 64}, {}, "OPERATIONAL_DB_BINDING_BASELINE_SHA_MISMATCH"),
        ({"migration_count": 51}, {}, "OPERATIONAL_DB_BINDING_MIGRATION_MISMATCH"),
        ({"migration_head": "051.sql"}, {}, "OPERATIONAL_DB_BINDING_MIGRATION_MISMATCH"),
        ({"authorization_marker_sha256": "d" * 64}, {}, "OPERATIONAL_DB_BINDING_AUTHORIZATION_MISMATCH"),
        ({"application_marker_sha256": "d" * 64}, {}, "OPERATIONAL_DB_BINDING_APPLICATION_MARKER_MISMATCH"),
        ({"campaign_id": "other-campaign"}, {}, "OPERATIONAL_DB_BINDING_OWNERSHIP_MISMATCH"),
        ({"campaign_run_id": "other-run"}, {}, "OPERATIONAL_DB_BINDING_OWNERSHIP_MISMATCH"),
        ({"cycle_id": "other-cycle"}, {}, "OPERATIONAL_DB_BINDING_OWNERSHIP_MISMATCH"),
        ({"configuration_id": "other-configuration"}, {}, "OPERATIONAL_DB_BINDING_OWNERSHIP_MISMATCH"),
        ({}, {"authorization_consumed_once": False}, "OPERATIONAL_DB_BINDING_REUSE_OR_HISTORY_MISMATCH"),
        ({}, {"invocation_count": 2}, "OPERATIONAL_DB_BINDING_REUSE_OR_HISTORY_MISMATCH"),
    ],
)
def test_binding_mismatches_return_exact_categories(
    tmp_path: Path,
    binding_change: dict,
    expected_change: dict,
    reason: str,
) -> None:
    canonical = tmp_path / "printer_v1.sqlite3"
    expected = _expected(canonical)
    expected.update(expected_change)
    binding = _binding(canonical, **binding_change)
    assert validate_operational_database_target_binding(
        binding,
        actual_db_path=canonical,
        canonical_authoritative_db_path=canonical,
        expected=expected,
    ) == reason


def test_actual_path_mismatch_is_categorical(tmp_path: Path) -> None:
    canonical = tmp_path / "printer_v1.sqlite3"
    assert validate_operational_database_target_binding(
        _binding(canonical),
        actual_db_path=tmp_path / "wrong.sqlite3",
        canonical_authoritative_db_path=canonical,
        expected=_expected(canonical),
    ) == "OPERATIONAL_DB_BINDING_PATH_MISMATCH"


def test_post_mutation_sha_is_not_compared_to_authorized_baseline(
    tmp_path: Path,
) -> None:
    canonical = tmp_path / "printer_v1.sqlite3"
    expected = _expected(canonical)
    expected["current_database_sha256"] = "f" * 64
    assert validate_operational_database_target_binding(
        _binding(canonical),
        actual_db_path=canonical,
        canonical_authoritative_db_path=canonical,
        expected=expected,
    ) is None


def test_direct_binding_without_durable_expectation_reaches_factory_terminal(
    tmp_path: Path,
) -> None:
    database = tmp_path / "fixture.sqlite3"
    backup = tmp_path / "fixture.backup.sqlite3"
    database.write_bytes(b"fixture")
    backup.write_bytes(b"backup")
    result = run_one_command_15m_factory(
        database,
        backup,
        operator_approved=True,
        proof_mode=False,
        operational_persistent_mode=True,
        operational_database_target_binding=_binding(
            database,
            target_kind=AUTHORIZED_DISPOSABLE_OPERATIONAL_PROOF,
            authorized_pre_mutation_sha256="d" * 64,
        ),
        total_duration_seconds=901.0,
    )
    assert "OPERATIONAL_DB_BINDING_EXPECTATION_MISSING" in result["blocked_reasons"]


def test_goplus_transport_emits_one_exact_holder_identity() -> None:
    mint = "Mint111111111111111111111111111111111111111"
    observed = []
    ledger = MeasuredTransportLedger(on_transport_recorded=observed.append)
    with patch(
        "printer_v1.sources.goplus._load_public_json",
        return_value={"code": 1, "result": {mint: {"holders": []}}},
    ):
        payload = build_goplus_token_safety_transport(
            mint, measured_transport_ledger=ledger
        )(None)

    identities = payload["transport_operation_identities"]
    assert len(identities) == len(ledger.transports) == len(observed) == 1
    assert identities[0] == observed[0].as_dict()
    assert identities[0]["stage"] == "HOLDER_SAFETY"
    assert identities[0]["source_name"] == "goplus"
    assert identities[0]["governed_request_kind"] == "safety_reference"
    assert identities[0]["within_request_ordinal"] == 1
    assert identities[0]["target_category"] == "TOKEN_MINT"
    assert identities[0]["target_identity"] == mint


def test_solana_holder_success_emits_two_exact_rpc_identities() -> None:
    mint = "Mint111111111111111111111111111111111111111"
    ledger = MeasuredTransportLedger()
    responses = [
        {"result": {"context": {"slot": 1}, "value": []}},
        {"result": {"context": {"slot": 2}, "value": {"amount": "1"}}},
    ]
    with patch("printer_v1.sources.solana_rpc_holder._rpc_post", side_effect=responses):
        payload = build_solana_rpc_holder_transport(
            mint, measured_transport_ledger=ledger
        )(None)

    identities = payload["transport_operation_identities"]
    assert [item["method_or_endpoint"] for item in identities] == [
        "getTokenLargestAccounts",
        "getTokenSupply",
    ]
    assert [item["within_request_ordinal"] for item in identities] == [1, 2]
    assert len(ledger.transports) == 2


def test_solana_holder_first_rpc_failure_emits_only_attempted_identity() -> None:
    mint = "Mint111111111111111111111111111111111111111"
    ledger = MeasuredTransportLedger()
    with patch(
        "printer_v1.sources.solana_rpc_holder._rpc_post",
        return_value={
            "fixture_status": "failure",
            "failure_type": "solana_rpc_transport_failure",
            "failure_message": "offline fixture",
            "rpc_method": "getTokenLargestAccounts",
        },
    ) as rpc:
        payload = build_solana_rpc_holder_transport(
            mint, measured_transport_ledger=ledger
        )(None)

    assert rpc.call_count == 1
    assert len(payload["transport_operation_identities"]) == 1
    assert len(ledger.transports) == 1


def _measured_execution(payload: dict, *, source="goplus", kind="safety_reference"):
    return SimpleNamespace(
        normalized_result=SimpleNamespace(
            source_name=source,
            request_kind=kind,
            normalized_payload=payload,
        )
    )


def test_numeric_holder_count_without_identities_blocks_active_accounting() -> None:
    count, complete, reason = _measure_holder_transport_count(
        _measured_execution({"token_mint": "Mint111", "underlying_operation_count": 1}),
        require_exact_identities=True,
    )
    assert (count, complete, reason) == (
        0,
        False,
        "HOLDER_TRANSPORT_IDENTITIES_MISSING",
    )


def test_duplicate_holder_identity_blocks_active_accounting() -> None:
    identity = {
        "stage": "HOLDER_SAFETY",
        "source_name": "goplus",
        "endpoint_owner": "api.gopluslabs.io",
        "governed_request_kind": "safety_reference",
        "method_or_endpoint": "GET_TOKEN_SECURITY",
        "within_request_ordinal": 1,
        "target_category": "TOKEN_MINT",
        "target_identity": "Mint111",
        "response_bytes": 1,
        "normalized_rows": 1,
        "result": "COMPLETED",
    }
    count, complete, reason = _measure_holder_transport_count(
        _measured_execution(
            {
                "token_mint": "Mint111",
                "transport_operation_identities": [identity, dict(identity)],
                "transport_operations_used": 2,
            }
        ),
        require_exact_identities=True,
    )
    assert (count, complete, reason) == (
        0,
        False,
        "HOLDER_TRANSPORT_IDENTITY_DUPLICATE",
    )


def test_holder_identity_correspondence_mismatch_blocks() -> None:
    identity = {
        "stage": "HOLDER_SAFETY",
        "source_name": "solana_rpc",
        "endpoint_owner": "api.mainnet-beta.solana.com",
        "governed_request_kind": "holder_concentration_reference",
        "method_or_endpoint": "getTokenLargestAccounts",
        "within_request_ordinal": 1,
        "target_category": "TOKEN_MINT",
        "target_identity": "OtherMint",
        "response_bytes": 1,
        "normalized_rows": 1,
        "result": "COMPLETED",
    }
    count, complete, reason = _measure_holder_transport_count(
        _measured_execution(
            {
                "token_mint": "Mint111",
                "transport_operation_identities": [identity],
                "transport_operations_used": 1,
            },
            source="solana_rpc",
            kind="holder_concentration_reference",
        ),
        require_exact_identities=True,
    )
    assert (count, complete, reason) == (
        0,
        False,
        "HOLDER_TRANSPORT_IDENTITY_CORRESPONDENCE_MISMATCH",
    )


def test_real_child_streams_are_preserved_and_metadata_is_separate(tmp_path: Path) -> None:
    stdout = tmp_path / "child-stdout.txt"
    stderr = tmp_path / "child-stderr.txt"
    metadata = tmp_path / "child-launcher-metadata.json"

    def child(_arguments):
        print("real child stdout")
        print("real child stderr", file=__import__("sys").stderr)
        print('{"status":"BLOCKED","blocked_reasons":["EXACT"]}')
        return 7

    rc = capture_public_command_main(
        child,
        ["run", "--operator-approved"],
        stdout_path=stdout,
        stderr_path=stderr,
        launcher_metadata_path=metadata,
    )
    assert rc == 7
    assert "real child stdout" in stdout.read_text()
    assert "real child stderr" in stderr.read_text()
    assert "child_returncode" not in stdout.read_text()
    assert '"return_code": 7' in metadata.read_text()


def test_child_terminal_parsing_retains_blockers_and_orchestration_error() -> None:
    terminal = parse_final_child_terminal(
        'log line\n{"status":"BLOCKED","blocked_reasons":["A"],'
        '"orchestration_error":{"code":"B"}}\n'
    )
    projection = terminal_truth_projection(terminal)
    assert projection["blocked_reasons"] == ["A"]
    assert projection["orchestration_error"] == {"code": "B"}


def test_unparseable_child_terminal_blocks_with_raw_streams_untouched(tmp_path: Path) -> None:
    raw = "not terminal json\n"
    stdout = tmp_path / "child-stdout.txt"
    stderr = tmp_path / "child-stderr.txt"
    stdout.write_text(raw)
    stderr.write_text("raw stderr\n")
    with pytest.raises(ContinuousProofEvidenceError, match="CHILD_TERMINAL_JSON_UNPARSEABLE"):
        parse_final_child_terminal(stdout.read_text())
    assert stdout.read_text() == raw
    assert stderr.read_text() == "raw stderr\n"


def test_all_mandatory_artifacts_copy_hash_and_reread_before_cleanup(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    paths = {}
    for index, name in enumerate(MANDATORY_RETAINED_ARTIFACTS, start=1):
        path = source / name
        path.write_bytes(f"artifact-{index}".encode())
        paths[name] = path
    retained = tmp_path / "retained"
    result = retain_required_artifacts(paths, retained_directory=retained)
    assert result["status"] == "COMPLETE"
    assert (retained / "artifact-hashes.json").is_file()
    for name in MANDATORY_RETAINED_ARTIFACTS:
        assert (retained / name).read_bytes() == Path(paths[name]).read_bytes()
        assert result["artifacts"][name]["sha256"]


def test_missing_mandatory_artifact_records_absence_and_blocks(tmp_path: Path) -> None:
    retained = tmp_path / "retained"
    with pytest.raises(ContinuousProofEvidenceError, match="MANDATORY_ARTIFACT_MISSING"):
        retain_required_artifacts({}, retained_directory=retained)
    record = __import__("json").loads(
        (retained / "artifact-hashes.json").read_text()
    )
    assert record["status"] == "BLOCKED"
    assert "child-stdout.txt" in record["absent_artifacts"]


def test_holder_and_freeze_diagnostics_are_retained_without_reconstruction(
    tmp_path: Path,
) -> None:
    diagnostics = {
        "holder_context": {
            "pre_holder_request_ids": [1],
            "pre_holder_transport_identity_keys": [["pre", 1]],
            "evaluated_candidate_mints": ["mint-a"],
            "unattempted_candidate_mints": ["mint-b"],
            "holder_attempt_budget_trace": [{"allowed": True}],
            "source_request_ids": [2],
            "transport_identities": [{"target_identity": "mint-a"}],
            "holder_stage_terminal_status": "COMPLETED",
            "source_outcomes": ["COMPLETE"],
            "ledger_before_holder": {"charged_operations": 1},
            "ledger_after_holder": {"charged_operations": 2},
            "budget_exhaustion_reason": None,
        },
        "pre_holder_budget_snapshot": {"governed_request_ids": [1]},
        "campaign_source_request_reconciliation": {"status": "OK"},
        "campaign_six_unit_evidence": {"transport_operations": [{"id": 1}]},
        "action_local_six_unit_evidence": {"transport_operations": [{"id": 1}]},
        "selected_and_alternate_identities": {
            "ordered_candidate_universe": ["a", "b", "c", "d"],
            "selected_identities": ["a", "b"],
            "alternate_identities": ["c", "d"],
            "selection_seed": "seed",
            "freeze_authority": "campaign-owner",
            "handoff_slots": ["slot-1", "slot-2"],
            "lifecycle_target_identities": ["a", "b"],
        },
    }
    paths = write_proof_diagnostic_artifacts(
        diagnostics, output_directory=tmp_path
    )
    assert set(paths) == {
        "holder-context.json",
        "pre-holder-budget-snapshot.json",
        "campaign-source-request-reconciliation.json",
        "campaign-six-unit-evidence.json",
        "action-local-six-unit-evidence.json",
        "selected-and-alternate-identities.json",
    }
    assert __import__("json").loads(
        paths["selected-and-alternate-identities.json"].read_text()
    )["ordered_candidate_universe"] == ["a", "b", "c", "d"]


def test_holder_identities_fan_out_once_reach_payload_and_seal_one_stage(
    tmp_path: Path,
) -> None:
    connection = holder_fixtures._db(tmp_path)
    observed = []
    sealed_ledgers = []

    def seal(ledger, status, cause):
        sealed_ledgers.append((ledger, status, cause))
        return {"stage_id": "campaign|run|cycle|HOLDER_SAFETY|1"}

    raw = {
        "code": 1,
        "result": {
            holder_fixtures.MINT_A: holder_fixtures._goplus_payload(
                holder_fixtures.MINT_A,
                holders=[{"percent": "3"} for _ in range(10)],
            )
        },
    }
    owner = AuthoritativeLiveOperationalCampaignOwner()
    ledger = holder_budget.build_ledger(
        pump_operations=0,
        deadline_at=holder_fixtures.NOW + timedelta(minutes=30),
    )
    proof = SimpleNamespace(
        mint=holder_fixtures.MINT_A,
        bonding_curve=holder_fixtures._POOLS[0],
        block_time=0,
    )
    with patch("printer_v1.sources.goplus._load_public_json", return_value=raw):
        result = owner._evaluate_holder_eligibility(
            connection,
            command=SimpleNamespace(run_id="run", campaign_id="campaign"),
            cycle_id="cycle",
            bounded_candidates=(proof,),
            evaluated=holder_fixtures.NOW,
            deadline=holder_fixtures.NOW + timedelta(minutes=30),
            ledger=ledger,
            timeout_seconds=1.0,
            context_factories=None,
            request_pacer=holder_fixtures._pacer(),
            eligible_target=1,
            holder_transport_identity_observer=observed.append,
            holder_stage_evidence_sealer=seal,
        )
    connection.close()

    assert len(sealed_ledgers) == 1
    assert result.holder_stage_id.endswith("|HOLDER_SAFETY|1")
    assert result.holder_stage_terminal_status == "COMPLETED"
    assert len(result.transport_identities) == result.measured_transport_count == 1
    assert [item.as_dict() for item in observed] == list(result.transport_identities)
    assert [item.as_dict() for item in sealed_ledgers[0][0].transports] == list(
        result.transport_identities
    )
