from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import socket
import sqlite3

import pytest

from printer_v1.operator_cli.proof_db_schema_readiness import CANONICAL_PERSISTENT_DB


ROOT = Path(__file__).resolve().parents[1]
HARNESS_PATH = ROOT / "scripts" / "v2_9_8b_checkpoint8_controlling_public_composition_proof.py"
INSPECTOR_PATH = ROOT / "scripts" / "v2_9_8b_checkpoint8_independent_inspection.py"


def _load_script(path: Path, module_name: str):
    assert path.is_file(), f"missing required C8 proof script: {path.name}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_network_tripwire_blocks_create_connection_and_counts_attempt() -> None:
    harness = _load_script(HARNESS_PATH, "checkpoint8_controlling_harness_tripwire_create")
    tripwire = harness.Checkpoint8NetworkTripwire()
    with tripwire:
        with pytest.raises(
            harness.Checkpoint8NetworkTripwireError,
            match="CHECKPOINT8_EXTERNAL_NETWORK_ATTEMPT_FORBIDDEN",
        ):
            socket.create_connection(("203.0.113.1", 443), timeout=0.01)
    assert tripwire.attempt_count == 1
    assert len(tripwire.attempts) == 1


def test_network_tripwire_blocks_connect_ex_and_restores_socket_hooks() -> None:
    harness = _load_script(HARNESS_PATH, "checkpoint8_controlling_harness_tripwire_restore")
    original_create_connection = socket.create_connection
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    tripwire = harness.Checkpoint8NetworkTripwire()
    with tripwire:
        assert socket.create_connection is not original_create_connection
        assert socket.socket.connect is not original_connect
        assert socket.socket.connect_ex is not original_connect_ex
        candidate = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            with pytest.raises(
                harness.Checkpoint8NetworkTripwireError,
                match="CHECKPOINT8_EXTERNAL_NETWORK_ATTEMPT_FORBIDDEN",
            ):
                candidate.connect_ex(("198.51.100.1", 443))
        finally:
            candidate.close()

    assert socket.create_connection is original_create_connection
    assert socket.socket.connect is original_connect
    assert socket.socket.connect_ex is original_connect_ex
    assert tripwire.attempt_count == 1


def test_controlling_attempt_sentinel_is_atomic_one_shot(tmp_path: Path) -> None:
    harness = _load_script(HARNESS_PATH, "checkpoint8_controlling_harness_sentinel")
    proof_root = tmp_path / "proof-root"
    proof_root.mkdir()

    sentinel = harness.claim_controlling_attempt_sentinel(
        proof_root,
        proof_id="checkpoint8-proof-1",
        git_head="a" * 40,
    )
    assert sentinel.is_file()
    before = sentinel.read_bytes()
    payload = json.loads(before)
    assert payload["proof_id"] == "checkpoint8-proof-1"
    assert payload["git_head"] == "a" * 40
    assert payload["attempt_ordinal"] == 1

    with pytest.raises(
        harness.Checkpoint8ControllingProofError,
        match="CONTROLLING_ATTEMPT_ALREADY_CONSUMED",
    ):
        harness.claim_controlling_attempt_sentinel(
            proof_root,
            proof_id="checkpoint8-proof-1",
            git_head="a" * 40,
        )
    assert sentinel.read_bytes() == before


def test_controlling_harness_exposes_no_reuse_or_force_cli() -> None:
    source = HARNESS_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "--force",
        "--retry",
        "--rerun",
        "--resume",
        "--restart",
        "--successor",
    ):
        assert forbidden not in source


def test_independent_inspector_refuses_canonical_production_db() -> None:
    inspector = _load_script(INSPECTOR_PATH, "checkpoint8_independent_inspector_canonical")
    with pytest.raises(
        inspector.Checkpoint8IndependentInspectionError,
        match="CANONICAL_PRODUCTION_DB_FORBIDDEN",
    ):
        inspector.validate_independent_proof_db_target(
            CANONICAL_PERSISTENT_DB,
            canonical_db_path=CANONICAL_PERSISTENT_DB,
        )


def test_independent_inspector_opens_disposable_db_read_only(tmp_path: Path) -> None:
    inspector = _load_script(INSPECTOR_PATH, "checkpoint8_independent_inspector_ro")
    db_path = tmp_path / "proof.sqlite3"
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("CREATE TABLE evidence(id INTEGER PRIMARY KEY, value TEXT)")
        connection.execute("INSERT INTO evidence(value) VALUES ('frozen')")
        connection.commit()
    finally:
        connection.close()

    reader = inspector.open_independent_read_only_db(
        db_path,
        canonical_db_path=CANONICAL_PERSISTENT_DB,
    )
    try:
        assert reader.execute("SELECT value FROM evidence").fetchone()[0] == "frozen"
        with pytest.raises(sqlite3.OperationalError):
            reader.execute("INSERT INTO evidence(value) VALUES ('mutation')")
    finally:
        reader.close()


def test_independent_inspector_has_no_operational_campaign_or_report_replay_call() -> None:
    source = INSPECTOR_PATH.read_text(encoding="utf-8")
    assert "run_operational_campaign(" not in source
    assert "report_only(" not in source


def test_proof_safety_scripts_are_import_safe_and_have_main_guards() -> None:
    harness = _load_script(HARNESS_PATH, "checkpoint8_controlling_harness_import_safe")
    inspector = _load_script(INSPECTOR_PATH, "checkpoint8_independent_inspector_import_safe")
    assert callable(harness.main)
    assert callable(inspector.main)
    assert 'if __name__ == "__main__":' in HARNESS_PATH.read_text(encoding="utf-8")
    assert 'if __name__ == "__main__":' in INSPECTOR_PATH.read_text(encoding="utf-8")
