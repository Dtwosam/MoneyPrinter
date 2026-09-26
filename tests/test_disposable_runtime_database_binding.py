"""Development proof identity cannot become operational authorization."""
from dataclasses import replace

import pytest

from printer_v1.operator_cli import operational_database_target_binding as binding_module
from tests.test_v2_9_8b_four_token_factory_wake_ordering import _prepare


@pytest.fixture
def proof_scope(tmp_path):
    db, _, binding = _prepare(tmp_path)
    expected = binding_module.build_disposable_public_composition_proof_expectation(binding)
    return db, binding, expected, tmp_path / "authoritative.sqlite3"


def _validate(scope, binding=None, expected=None, canonical=None):
    db, original, expectation, authoritative = scope
    return binding_module.validate_campaign_runtime_database_binding(
        original if binding is None else binding,
        actual_db_path=db,
        canonical_authoritative_db_path=authoritative if canonical is None else canonical,
        expected=expectation if expected is None else expected,
    )


def test_exact_disposable_runtime_scope_is_accepted(proof_scope):
    assert _validate(proof_scope) is None


@pytest.mark.parametrize("field,value", [
    ("campaign_id", "other"), ("cycle_id", "other"),
    ("campaign_run_id", "other"), ("execution_id", "other"),
    ("fixture_composition_manifest_sha256", "0" * 64),
    ("configuration_id", "other"), ("db_target_identity", "sha256:" + "0" * 64),
    ("provider_execution_allowed", True), ("resume_allowed", True),
    ("binding_schema_version", "UNKNOWN"), ("proof_schema_version", "UNKNOWN"),
])
def test_disposable_scope_tampering_fails_closed(proof_scope, field, value):
    assert _validate(proof_scope, binding=replace(proof_scope[1], **{field: value})) is not None


def test_disposable_scope_rejects_canonical_database(proof_scope):
    assert _validate(proof_scope, canonical=proof_scope[0]) == "DISPOSABLE_PROOF_CANONICAL_DB_FORBIDDEN"


def test_disposable_scope_requires_durable_expectation(proof_scope):
    assert _validate(proof_scope, expected={}) is not None


def test_development_scope_does_not_satisfy_operational_invocation(proof_scope):
    db, binding, expected, canonical = proof_scope
    assert binding_module.validate_bound_operational_invocation(
        binding, actual_db_path=db, canonical_authoritative_db_path=canonical,
        durable_expectation=expected,
    ) is not None


def test_missing_binding_stays_blocked(proof_scope):
    db, _, expected, canonical = proof_scope
    assert binding_module.validate_campaign_runtime_database_binding(
        None, actual_db_path=db, canonical_authoritative_db_path=canonical,
        expected=expected,
    ) == "OPERATIONAL_DB_BINDING_MISSING"


@pytest.mark.parametrize("facts", [
    {"authorization_consumed_once": True},
    {"application_marker_sha256": "0" * 64},
    {"target_kind": "AUTHORITATIVE_OPERATIONAL"},
])
def test_operational_facts_cannot_be_smuggled_into_proof(proof_scope, facts):
    assert _validate(proof_scope, expected={**proof_scope[2], **facts}) is not None


def test_proof_rejects_other_database_path(proof_scope, tmp_path):
    _, binding, expected, canonical = proof_scope
    assert binding_module.validate_campaign_runtime_database_binding(
        binding, actual_db_path=tmp_path / "other.sqlite3",
        canonical_authoritative_db_path=canonical, expected=expected,
    ) == "DISPOSABLE_PROOF_DB_PATH_MISMATCH"
