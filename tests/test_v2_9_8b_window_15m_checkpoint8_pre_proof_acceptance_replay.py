from __future__ import annotations

import inspect

from printer_v1.operator_cli import campaign_full_run_accounting as accounting
from printer_v1.operator_cli import operational_memory_factory_command as command


PROOF_MODE = "DISPOSABLE_PUBLIC_COMPOSITION_PROOF"


def _minimal_report(*, markers: dict) -> dict:
    return {
        "authorization_and_invocation": markers,
        "selection_and_lifecycle": {},
        "full_run_accounting": {"owner_action_local_reconciliation": {}},
        "terminal_safety": {},
        "identity": {},
        "quality_consistency": {"consistent": False},
        "hashes": {},
        "runtime_terminal_status": "FAILED",
    }


def test_production_acceptance_keeps_existing_authorization_checks() -> None:
    result = accounting.evaluate_campaign_acceptance_gate(
        _minimal_report(markers={})
    )
    checks = result["checks"]
    assert "exactly_one_authorization_marker" in checks
    assert "authorization_supervision_binding_correspondence_exact" in checks
    assert "authorization_marker_digest_exact" in checks
    assert "invocation_marker_digest_exact" in checks


def test_c8_proof_evidence_mode_constant_exists() -> None:
    assert accounting.EVIDENCE_MODE_DISPOSABLE_PUBLIC_COMPOSITION_PROOF == PROOF_MODE


def test_c8_has_durable_invocation_authority_loader() -> None:
    loader = accounting.load_invocation_authority_evidence
    signature = inspect.signature(loader)
    assert "connection" in signature.parameters
    assert "context" in signature.parameters
    assert "execution_id" in signature.parameters
    assert "supervision_id" in signature.parameters
    source = inspect.getsource(loader)
    assert "operational_database_target_expectation" in source
    assert "DISPOSABLE_PUBLIC_COMPOSITION_PROOF" in source
    assert "proof_expectation" in source
    assert "proof_invocation_evidence" in source


def test_c8_acceptance_replaces_authorization_checks_with_proof_checks() -> None:
    result = accounting.evaluate_campaign_acceptance_gate(
        _minimal_report(
            markers={
                "evidence_mode": PROOF_MODE,
                "authorization_marker": None,
                "authorization_count": 0,
                "exact_authorization_count": 0,
            }
        )
    )
    checks = result["checks"]
    assert "exactly_one_authorization_marker" not in checks
    assert "authorization_supervision_binding_correspondence_exact" not in checks
    assert "authorization_marker_digest_exact" not in checks
    assert "invocation_marker_digest_exact" not in checks
    assert "proof_expectation_exact" in checks
    assert "proof_invocation_identity_exact" in checks
    assert "proof_supervision_factory_correspondence_exact" in checks
    assert "proof_no_authorization_facts" in checks
    assert "proof_no_provider_or_reuse_permission" in checks
    assert "proof_manifest_exact" in checks


def test_c8_report_and_replay_use_proof_specific_hashes_not_fake_auth_hash() -> None:
    accounting_source = inspect.getsource(accounting)
    replay_source = inspect.getsource(command.report_only)
    assert "proof_expectation_sha256" in accounting_source
    assert "proof_invocation_evidence_sha256" in accounting_source
    assert "proof_expectation_sha256" in replay_source
    assert "proof_invocation_evidence_sha256" in replay_source


def test_terminal_summary_loader_accepts_explicit_artifact_root() -> None:
    signature = inspect.signature(command._load_exact_terminal_summary)
    assert "artifact_root" in signature.parameters
    source = inspect.getsource(command._load_exact_terminal_summary)
    assert "artifact_root" in source


def test_report_only_passes_exact_replay_artifact_root_to_summary_fallback() -> None:
    source = inspect.getsource(command.report_only)
    summary_call = source[source.index("_load_exact_terminal_summary(") :]
    assert "artifact_root=replay_artifact_root" in summary_call
