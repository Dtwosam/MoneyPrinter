from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sqlite3

import pytest

from printer_v1.operator_cli.one_command_15m_factory import (
    run_one_command_15m_factory,
)
from printer_v1.operator_cli.git_provenance_authorization_manifest import (
    ValidatedGitProvenanceAuthorization,
)
from printer_v1.operator_cli.operational_database_target_binding import (
    AUTHORIZED_DISPOSABLE_OPERATIONAL_PROOF,
    PRODUCTION_AUTHORITATIVE,
    OperationalDatabaseTargetBinding,
    build_durable_operational_database_target_expectation,
    load_durable_operational_database_target_expectation,
    validate_authorized_database_preflight,
    validated_authorization_runtime_facts,
    validate_bound_operational_invocation,
)
from printer_v1.operator_cli.continuous_proof_evidence_retention import (
    FailureSafeProofRetention,
    MANDATORY_RETAINED_ARTIFACTS,
)


def _binding(path: Path, *, target_kind: str = PRODUCTION_AUTHORITATIVE):
    return OperationalDatabaseTargetBinding(
        binding_version="OPERATIONAL_DATABASE_TARGET_BINDING_V1",
        target_kind=target_kind,
        resolved_db_path=str(path.resolve()),
        authorized_pre_mutation_sha256="a" * 64,
        migration_count=52,
        migration_head="052_memory_observation_eligibility_layers.sql",
        db_target_identity=f"sha256:{'a' * 64}",
        authorization_id="authorization-real",
        authorization_marker_sha256="b" * 64,
        application_marker_sha256="c" * 64,
        execution_id="execution-real",
        campaign_id="campaign-real",
        campaign_run_id="run-real",
        cycle_id="cycle-real",
        configuration_id="configuration-real",
        authorization_consumed_once=True,
        invocation_count=1,
        allowed_invocation_count=1,
        automatic_retry_allowed=False,
        manual_rerun_allowed=False,
        resume_allowed=False,
        restart_allowed=False,
        successor_allowed=False,
    )


def _expectation(path: Path, *, target_kind: str = PRODUCTION_AUTHORITATIVE):
    return build_durable_operational_database_target_expectation(
        target_kind=target_kind,
        resolved_db_path=path,
        authorized_pre_mutation_sha256="a" * 64,
        migration_count=52,
        migration_head="052_memory_observation_eligibility_layers.sql",
        durable_db_target_identity=f"sha256:{'a' * 64}",
        authorization_id="authorization-real",
        manifest_sha256="b" * 64,
        application_marker_sha256="c" * 64,
        execution_id="execution-real",
        campaign_id="campaign-real",
        campaign_run_id="run-real",
        cycle_id="cycle-real",
        configuration_id="configuration-real",
        authorization_consumed_once=True,
        invocation_count=1,
        allowed_invocation_count=1,
        automatic_retry_allowed=False,
        manual_rerun_allowed=False,
        resume_allowed=False,
        restart_allowed=False,
        successor_allowed=False,
    )


def _validate(binding, canonical: Path, expectation):
    return validate_bound_operational_invocation(
        binding,
        actual_db_path=Path(binding.resolved_db_path),
        canonical_authoritative_db_path=canonical,
        durable_expectation=expectation,
    )


def test_forged_binding_is_not_its_own_validation_authority(tmp_path: Path) -> None:
    canonical = tmp_path / "printer_v1.sqlite3"
    forged = replace(
        _binding(canonical),
        authorization_id="forged-authorization",
        authorization_marker_sha256="d" * 64,
        application_marker_sha256="e" * 64,
    )

    assert _validate(forged, canonical, _expectation(canonical)) == (
        "OPERATIONAL_DB_BINDING_AUTHORIZATION_MISMATCH"
    )


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("authorization_id", "wrong", "OPERATIONAL_DB_BINDING_AUTHORIZATION_MISMATCH"),
        ("authorization_marker_sha256", "d" * 64, "OPERATIONAL_DB_BINDING_AUTHORIZATION_MISMATCH"),
        ("application_marker_sha256", "e" * 64, "OPERATIONAL_DB_BINDING_APPLICATION_MARKER_MISMATCH"),
        ("binding_version", "OPERATIONAL_DATABASE_TARGET_BINDING_V0", "OPERATIONAL_DB_BINDING_VERSION_UNSUPPORTED"),
    ],
)
def test_independent_expectation_rejects_forged_authorization_fields(
    tmp_path: Path, field: str, value: str, reason: str
) -> None:
    canonical = tmp_path / "printer_v1.sqlite3"
    assert _validate(
        replace(_binding(canonical), **{field: value}),
        canonical,
        _expectation(canonical),
    ) == reason


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("authorization_consumed_once", False),
        ("invocation_count", 2),
        ("allowed_invocation_count", 2),
        ("automatic_retry_allowed", True),
        ("manual_rerun_allowed", True),
        ("resume_allowed", True),
        ("restart_allowed", True),
        ("successor_allowed", True),
    ],
)
def test_actual_consumption_and_reuse_facts_fail_closed(
    tmp_path: Path, field: str, value: object
) -> None:
    canonical = tmp_path / "printer_v1.sqlite3"
    expectation = dict(_expectation(canonical))
    expectation[field] = value

    assert _validate(_binding(canonical), canonical, expectation) == (
        "OPERATIONAL_DB_BINDING_REUSE_OR_HISTORY_MISMATCH"
    )
    assert _validate(
        replace(_binding(canonical), **{field: value}),
        canonical,
        _expectation(canonical),
    ) == "OPERATIONAL_DB_BINDING_REUSE_OR_HISTORY_MISMATCH"


@pytest.mark.parametrize(
    "target_kind",
    [PRODUCTION_AUTHORITATIVE, AUTHORIZED_DISPOSABLE_OPERATIONAL_PROOF],
)
def test_production_and_disposable_paths_require_independent_expectation(
    tmp_path: Path, target_kind: str
) -> None:
    canonical = tmp_path / "printer_v1.sqlite3"
    actual = canonical if target_kind == PRODUCTION_AUTHORITATIVE else tmp_path / "proof.sqlite3"
    binding = _binding(actual, target_kind=target_kind)

    assert validate_bound_operational_invocation(
        binding,
        actual_db_path=actual,
        canonical_authoritative_db_path=canonical,
        durable_expectation=None,
    ) == "OPERATIONAL_DB_BINDING_EXPECTATION_MISSING"
    assert _validate(binding, canonical, _expectation(actual, target_kind=target_kind)) is None


def _authorization(**changes):
    values = {
        "allowed_untracked_paths": (),
        "authorization_id": "authorization-real",
        "manifest_sha256": "b" * 64,
        "marker_sha256": "c" * 64,
        "allowed_file_set_sha256": "d" * 64,
        "file_count": 0,
        "authorization_consumed_once": True,
        "invocation_count": 1,
        "allowed_invocation_count": 1,
        "automatic_retry_allowed": False,
        "manual_rerun_allowed": False,
        "resume_allowed": False,
        "restart_allowed": False,
        "successor_allowed": False,
        "authoritative_database": {
            "path": "/tmp/authorization-real.sqlite3",
            "sha256": "a" * 64,
            "size": 1,
            "inode": 1,
            "mtime_ns": 1,
            "migration_count": 52,
            "migration_head": "052_memory_observation_eligibility_layers.sql",
        },
    }
    values.update(changes)
    return ValidatedGitProvenanceAuthorization(**values)


def test_missing_validated_authorization_blocks_before_binding_construction() -> None:
    with pytest.raises(ValueError, match="VALIDATED_AUTHORIZATION_REQUIRED"):
        validated_authorization_runtime_facts(None)


def test_missing_application_marker_blocks_before_binding_construction() -> None:
    with pytest.raises(ValueError, match="APPLICATION_MARKER_REQUIRED"):
        validated_authorization_runtime_facts(_authorization(marker_sha256=""))


def test_authorized_database_baseline_is_not_derived_from_preflight(
    tmp_path: Path,
) -> None:
    database = tmp_path / "authorized.sqlite3"
    authorization = _authorization(
        authoritative_database={
            **_authorization().authoritative_database,
            "path": str(database),
        }
    )
    facts = validated_authorization_runtime_facts(authorization)

    with pytest.raises(ValueError, match="AUTHORIZED_DATABASE_SHA256_MISMATCH"):
        validate_authorized_database_preflight(
            facts,
            actual_db_path=database,
            preflight={
                "database_sha256": "f" * 64,
                "migration_count": 52,
                "latest_migration": "052_memory_observation_eligibility_layers.sql",
            },
        )


def _persist_expectation(database: Path, expectation: dict) -> None:
    connection = sqlite3.connect(database)
    try:
        connection.execute(
            """CREATE TABLE printer_memory_factory_campaign_configurations(
                   configuration_id TEXT PRIMARY KEY,
                   campaign_id TEXT NOT NULL,
                   configuration_json TEXT NOT NULL
               )"""
        )
        connection.execute(
            """INSERT INTO printer_memory_factory_campaign_configurations(
                   configuration_id,campaign_id,configuration_json
               ) VALUES (?,?,?)""",
            (
                "configuration-real",
                "campaign-real",
                json.dumps(
                    {"operational_database_target_expectation": expectation},
                    sort_keys=True,
                ),
            ),
        )
        connection.commit()
    finally:
        connection.close()


def test_durable_expectation_is_loaded_by_exact_ownership(tmp_path: Path) -> None:
    database = tmp_path / "proof.sqlite3"
    expectation = _expectation(
        database, target_kind=AUTHORIZED_DISPOSABLE_OPERATIONAL_PROOF
    )
    _persist_expectation(database, expectation)

    loaded = load_durable_operational_database_target_expectation(
        database,
        campaign_id="campaign-real",
        campaign_run_id="run-real",
        cycle_id="cycle-real",
        configuration_id="configuration-real",
    )

    assert loaded == expectation
    assert load_durable_operational_database_target_expectation(
        database,
        campaign_id="campaign-real",
        campaign_run_id="wrong-run",
        cycle_id="cycle-real",
        configuration_id="configuration-real",
    ) is None


def test_wrong_authorization_reason_reaches_public_terminal_envelope(
    tmp_path: Path,
) -> None:
    database = tmp_path / "proof.sqlite3"
    backup = tmp_path / "proof.backup.sqlite3"
    expectation = _expectation(
        database, target_kind=AUTHORIZED_DISPOSABLE_OPERATIONAL_PROOF
    )
    _persist_expectation(database, expectation)
    backup.write_bytes(b"backup")
    forged = replace(
        _binding(database, target_kind=AUTHORIZED_DISPOSABLE_OPERATIONAL_PROOF),
        authorization_id="forged-authorization",
    )

    result = run_one_command_15m_factory(
        database,
        backup,
        operator_approved=True,
        proof_mode=False,
        operational_persistent_mode=True,
        operational_database_target_binding=forged,
        campaign_id="campaign-real",
        campaign_run_id="run-real",
        cycle_id="cycle-real",
        configuration_id="configuration-real",
        total_duration_seconds=901.0,
    )

    assert "OPERATIONAL_DB_BINDING_AUTHORIZATION_MISMATCH" in result["blocked_reasons"]


class OriginalProofFailure(RuntimeError):
    pass


def _initial_retention_sources(tmp_path: Path, *, stdout: str = '{"status":"BLOCKED"}\n'):
    staging = tmp_path / "child"
    staging.mkdir()
    sources = {
        "child-stdout.txt": staging / "child-stdout.txt",
        "child-stderr.txt": staging / "child-stderr.txt",
        "wrapper-terminal.json": staging / "wrapper-terminal.json",
    }
    sources["child-stdout.txt"].write_text(stdout, encoding="utf-8")
    sources["child-stderr.txt"].write_text("child diagnostic\n", encoding="utf-8")
    sources["wrapper-terminal.json"].write_text(
        '{"status":"CHILD_COMPLETED"}\n', encoding="utf-8"
    )
    return sources


def _assert_trustworthy_blocked_package(retained: Path, expected_failure: str) -> None:
    assert retained.is_dir()
    assert (retained / "child-stdout.txt").read_bytes()
    assert (retained / "child-stderr.txt").read_bytes()
    assert (retained / "wrapper-terminal.json").read_bytes()
    manifest = json.loads((retained / "artifact-hashes.json").read_text())
    assert manifest["status"] == "BLOCKED"
    assert manifest["first_failure"] == expected_failure
    assert manifest["absent_artifacts"]
    for name, record in manifest["artifacts"].items():
        if record["status"] != "PRESENT":
            continue
        payload = (retained / name).read_bytes()
        import hashlib

        assert record["sha256"] == hashlib.sha256(payload).hexdigest()
        assert record["size"] == len(payload)


@pytest.mark.parametrize(
    ("scenario", "message"),
    [
        ("child_nonzero", "CHILD_NONZERO_RETURN:7"),
        ("missing_campaign_report", "CAMPAIGN_REPORT_ABSENT"),
        ("missing_holder_diagnostics", "HOLDER_DIAGNOSTICS_ABSENT"),
        ("slot_assertion", "expected two token slots"),
        ("zero_window_blocker", "ZERO_WINDOW_LIFECYCLE_BLOCKER"),
        ("unexpected", "UNEXPECTED_AFTER_CHILD"),
    ],
)
def test_retention_finalizes_before_each_post_child_failure(
    tmp_path: Path, scenario: str, message: str
) -> None:
    retained = tmp_path / "retained"
    sources = _initial_retention_sources(tmp_path)

    with pytest.raises((OriginalProofFailure, AssertionError), match=message):
        with FailureSafeProofRetention(
            retained_directory=retained,
            initial_artifact_sources=sources,
        ) as retention:
            retention.parse_and_preserve_child_terminal()
            if scenario == "child_nonzero":
                raise OriginalProofFailure(message)
            if scenario == "missing_campaign_report":
                retention.record_absence(
                    "campaign-terminal-report.json", "CAMPAIGN_REPORT_ABSENT"
                )
                raise OriginalProofFailure(message)
            if scenario == "missing_holder_diagnostics":
                retention.record_absence(
                    "holder-context.json", "HOLDER_DIAGNOSTICS_ABSENT"
                )
                raise OriginalProofFailure(message)
            if scenario == "slot_assertion":
                raise AssertionError(message)
            if scenario == "zero_window_blocker":
                raise OriginalProofFailure(message)
            raise OriginalProofFailure(message)

    _assert_trustworthy_blocked_package(retained, message)


def test_retention_survives_child_terminal_parse_failure(tmp_path: Path) -> None:
    retained = tmp_path / "retained"
    sources = _initial_retention_sources(tmp_path, stdout="not-json\n")

    with pytest.raises(RuntimeError, match="CHILD_TERMINAL_JSON_UNPARSEABLE"):
        with FailureSafeProofRetention(
            retained_directory=retained,
            initial_artifact_sources=sources,
        ) as retention:
            retention.parse_and_preserve_child_terminal()

    _assert_trustworthy_blocked_package(
        retained, "CHILD_TERMINAL_JSON_UNPARSEABLE"
    )


def test_retention_completes_for_successful_execution(tmp_path: Path) -> None:
    retained = tmp_path / "retained"
    sources = _initial_retention_sources(tmp_path)
    remaining = tmp_path / "remaining"
    remaining.mkdir()
    for name in MANDATORY_RETAINED_ARTIFACTS:
        if name in sources or name == "child-terminal.json":
            continue
        path = remaining / name
        path.write_text(json.dumps({"artifact": name}) + "\n", encoding="utf-8")
        sources[name] = path

    with FailureSafeProofRetention(
        retained_directory=retained,
        initial_artifact_sources={
            name: path
            for name, path in sources.items()
            if name in {
                "child-stdout.txt",
                "child-stderr.txt",
                "wrapper-terminal.json",
            }
        },
    ) as retention:
        retention.parse_and_preserve_child_terminal()
        retention.add_artifacts(sources)

    manifest = json.loads((retained / "artifact-hashes.json").read_text())
    assert manifest["status"] == "COMPLETE"
    assert manifest["first_failure"] is None
    assert manifest["absent_artifacts"] == []
    assert set(manifest["artifacts"]) == set(MANDATORY_RETAINED_ARTIFACTS)
