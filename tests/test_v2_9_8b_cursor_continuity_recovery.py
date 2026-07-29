from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sqlite3

import pytest

from printer_v1.db import apply_migrations
from printer_v1.discovery.candidate_acquisition import (
    build_acquisition_plan,
    run_candidate_acquisition,
)
from printer_v1.operator_cli.cursor_continuity_recovery import (
    RECOVERY_COMPLETE,
    RECOVERY_INCOMPLETE,
    RECOVERY_NO_NEW,
    CursorRecoveryTransportOwner,
    run_cursor_continuity_recovery,
)
from printer_v1.operator_cli.operational_memory_factory_command import (
    run_cursor_recovery_only,
)
from printer_v1.operator_cli.live_candidate_acquisition_transport import (
    CURSOR_DECODER_VERSION,
    CURSOR_NETWORK,
    LIVE_TAIL_DIRECTION,
    LiveAcquisitionConfiguration,
    TransportResponse,
)
from printer_v1.sources.pump_contracts import OFFICIAL_REPOSITORY_COMMIT
from printer_v1.sources.pumpfun_direct import PUMP_PROGRAM_ID
from printer_v1.sources.pumpfun_origin import PUMP_CREATE_INDEX_ADDRESS


NOW = "2026-07-29T20:00:00+00:00"
HEADS = {
    PUMP_CREATE_INDEX_ADDRESS: (100, "create-head"),
    PUMP_PROGRAM_ID: (101, "migration-head"),
}


def _preflight(path: Path) -> dict:
    return {
        "status": "V2_9_8_OPERATIONAL_PREFLIGHT_READY",
        "database_path": str(path.resolve()),
        "database_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "latest_migration": "049_candidate_acquisition_integration.sql",
        "integrity": "ok",
        "foreign_key_violations": 0,
        "git_provenance": {
            "git_head": "test-head",
            "git_tracked_tree_clean": True,
        },
    }


def _cursor_observation(ordinal: int, address: str, slot: int, signature: str) -> dict:
    return {
        "round_ordinal": ordinal,
        "round_mode": "LIVE_TAIL",
        "source_name": "solana_rpc",
        "request_kind": (
            "pumpfun_create_index_signature_page"
            if address == PUMP_CREATE_INDEX_ADDRESS
            else "pumpfun_migration_signature_page"
        ),
        "source_status": "COMPLETE",
        "failure_reason": None,
        "observed_at": NOW,
        "expires_at": "2026-07-29T21:00:00+00:00",
        "governed_requests_used": 1,
        "transport_operations_used": 1,
        "bytes_used": 1,
        "rows_used": 1,
        "duration_milliseconds": 1,
        "facts": {"seed_cursor": True},
        "cursor_range": {
            "indexed_address": address,
            "contract_pin": OFFICIAL_REPOSITORY_COMMIT,
            "decoder_version": CURSOR_DECODER_VERSION,
            "direction": LIVE_TAIL_DIRECTION,
            "range_mode": "LIVE_TAIL",
            "bootstrap_contract": "EXPLICIT_TIP_BOOTSTRAP",
            "start_slot": None,
            "start_signature": None,
            "end_slot": slot,
            "end_signature": signature,
            "continuity_state": "CONTIGUOUS",
            "cursor_advanced": True,
            "unresolved_reason": None,
            "prior_boundary_verified": False,
        },
    }


def _db(tmp_path: Path, *, established: bool = True) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "recovery.sqlite3"
    apply_migrations(path)
    if established:
        plan = build_acquisition_plan(
            selection_capacity=2,
            execution_id="seed-cursors",
            selection_seed="seed",
            window_start=NOW,
            window_end=NOW,
            cutoff_at=NOW,
            finalized_cutoff_slot=0,
            git_provenance="test-head",
            source_budgets={"solana_rpc": {
                "pumpfun_create_index_signature_page": 1,
                "pumpfun_migration_signature_page": 1,
            }},
            allowed_sources=("solana_rpc",),
        )
        run_candidate_acquisition(
            path,
            plan=plan,
            observations=[
                _cursor_observation(1, PUMP_CREATE_INDEX_ADDRESS, *HEADS[PUMP_CREATE_INDEX_ADDRESS]),
                _cursor_observation(2, PUMP_PROGRAM_ID, *HEADS[PUMP_PROGRAM_ID]),
            ],
        )
    return path


class _RecoveryTransport:
    def __init__(self, rows_by_address: dict[str, list[dict]], *, fail: bool = False) -> None:
        self.rows_by_address = rows_by_address
        self.fail = fail
        self.calls: list[tuple[str, tuple]] = []

    @staticmethod
    def _response(payload, method: str, role: str) -> TransportResponse:
        return TransportResponse(payload, len(repr(payload).encode()), method, role)

    def http_json(self, **kwargs):
        raise AssertionError(kwargs)

    def rpc_json(self, *, rpc_url, method, params, timeout_seconds, byte_ceiling,
                 endpoint_role):
        del rpc_url, timeout_seconds, byte_ceiling
        self.calls.append((method, tuple(params)))
        if self.fail:
            raise OSError("provider unavailable")
        if method == "getTransaction":
            return self._response({"slot": 1}, method, endpoint_role)
        assert method == "getSignaturesForAddress"
        address, options = str(params[0]), dict(params[1])
        rows = self.rows_by_address[address]
        start = 0
        if options.get("before"):
            start = next(
                index + 1 for index, row in enumerate(rows)
                if row["signature"] == options["before"]
            )
        payload = rows[start : start + int(options["limit"])]
        return self._response(payload, method, endpoint_role)


def _rows(address: str, new_count: int) -> list[dict]:
    head_slot, head_signature = HEADS[address]
    prefix = "c" if address == PUMP_CREATE_INDEX_ADDRESS else "m"
    rows = [
        {
            "signature": f"{prefix}-{ordinal:05d}",
            "slot": head_slot + new_count - ordinal,
            "err": None,
            "confirmationStatus": "finalized",
        }
        for ordinal in range(new_count)
    ]
    rows.append({
        "signature": head_signature,
        "slot": head_slot,
        "err": None,
        "confirmationStatus": "finalized",
    })
    return rows


def _owner(transport: _RecoveryTransport) -> CursorRecoveryTransportOwner:
    return CursorRecoveryTransportOwner(
        LiveAcquisitionConfiguration(
            rpc_url="https://example.invalid",
            redacted_rpc_host="example.invalid",
        ),
        transport,
    )


def _run(path: Path, transport: _RecoveryTransport, ordinal: int, **kwargs) -> dict:
    if not kwargs:
        return run_cursor_recovery_only(
            operator_approved=True,
            transport_owner=_owner(transport),
            preflight_override=_preflight(path),
            execution_id=f"recovery-{ordinal}",
            owner_id=f"owner-{ordinal}",
            now=NOW,
            db_path=path,
        )
    return run_cursor_continuity_recovery(
        path,
        operator_approved=True,
        transport_owner=_owner(transport),
        preflight=_preflight(path),
        execution_id=f"recovery-{ordinal}",
        owner_id=f"owner-{ordinal}",
        now=NOW,
        **kwargs,
    )


def _heads(path: Path) -> dict[str, tuple[int, str, int]]:
    connection = sqlite3.connect(path)
    try:
        return {
            row[0]: (row[1], row[2], row[3])
            for row in connection.execute(
                "SELECT indexed_address,boundary_slot,boundary_signature,cursor_version "
                "FROM printer_candidate_acquisition_cursors WHERE direction='FORWARD'"
            )
        }
    finally:
        connection.close()


@pytest.mark.parametrize("new_count", [1, 249])
def test_established_boundary_within_one_page_and_exact_limit(tmp_path, new_count):
    path = _db(tmp_path)
    before = _heads(path)
    transport = _RecoveryTransport({address: _rows(address, new_count) for address in HEADS})
    report = _run(path, transport, 1)
    assert report["status"] == "COMPLETED"
    assert report["first_terminal_cause"] == RECOVERY_COMPLETE
    after = _heads(path)
    assert all(after[address][2] == before[address][2] + 1 for address in HEADS)
    assert all(after[address][1] == _rows(address, new_count)[0]["signature"] for address in HEADS)
    assert report["cursor_advances_committed"] == 2
    assert report["manifest_id"] is None
    assert report["projection_count"] == 0


def test_gap_requires_restart_and_atomic_final_advance(tmp_path):
    path = _db(tmp_path)
    before = _heads(path)
    rows = {address: _rows(address, 1_200) for address in HEADS}
    first_transport = _RecoveryTransport(rows)
    first = _run(path, first_transport, 1)
    assert first["status"] == "BLOCKED"
    assert first["first_terminal_cause"] == RECOVERY_INCOMPLETE
    assert _heads(path) == before
    assert first["foundation_execution_id"] is None
    assert first["cursor_advances_committed"] == 0

    # A separately constructed owner simulates a full process restart.
    second_transport = _RecoveryTransport(rows)
    second = _run(path, second_transport, 2)
    assert second["status"] == "COMPLETED"
    assert second["first_terminal_cause"] == RECOVERY_COMPLETE
    assert all(
        call[1][1].get("before") == rows[str(call[1][0])][999]["signature"]
        for call in second_transport.calls if call[0] == "getSignaturesForAddress"
        and call[1][1].get("before")
    )
    after = _heads(path)
    assert all(after[address][2] == before[address][2] + 1 for address in HEADS)
    assert second["cursor_advances_committed"] == 2
    assert second["runtime_handoff_count"] == 0


@pytest.mark.parametrize("new_count", [499, 600])
def test_exact_two_page_limit_and_gap_beyond_two_pages(tmp_path, new_count):
    path = _db(tmp_path)
    report = _run(
        path,
        _RecoveryTransport({address: _rows(address, new_count) for address in HEADS}),
        1,
    )
    assert report["status"] == "COMPLETED"
    assert report["first_terminal_cause"] == RECOVERY_COMPLETE
    expected_pages = 2 if new_count == 499 else 3
    assert {
        state["recovery_page_ordinal"]
        for state in report["recovery_states"].values()
    } == {expected_pages}


def test_gap_requires_three_separate_process_executions(tmp_path):
    path = _db(tmp_path)
    before = _heads(path)
    rows = {address: _rows(address, 2_200) for address in HEADS}
    first = _run(path, _RecoveryTransport(rows), 1)
    second = _run(path, _RecoveryTransport(rows), 2)
    third = _run(path, _RecoveryTransport(rows), 3)
    assert [first["status"], second["status"], third["status"]] == [
        "BLOCKED", "BLOCKED", "COMPLETED"
    ]
    assert _heads(path) != before
    assert third["recovery_execution_ordinal"] == 3
    assert third["cursor_advances_committed"] == 2


def test_no_new_signatures_is_stable(tmp_path):
    path = _db(tmp_path)
    before = _heads(path)
    rows = {address: _rows(address, 0) for address in HEADS}
    report = _run(path, _RecoveryTransport(rows), 1)
    assert report["status"] == "COMPLETED"
    assert report["first_terminal_cause"] == RECOVERY_NO_NEW
    assert _heads(path) == before
    assert report["cursor_advances_committed"] == 0


def test_fresh_bootstrap_and_provider_failure(tmp_path):
    bootstrap = _db(tmp_path / "bootstrap", established=False)
    rows = {
        PUMP_CREATE_INDEX_ADDRESS: [{
            "signature": "fresh-create", "slot": 500, "err": None,
            "confirmationStatus": "finalized",
        }],
        PUMP_PROGRAM_ID: [{
            "signature": "fresh-migration", "slot": 501, "err": None,
            "confirmationStatus": "finalized",
        }],
    }
    report = _run(bootstrap, _RecoveryTransport(rows), 1)
    assert report["status"] == "COMPLETED"
    assert set(_heads(bootstrap)) == set(HEADS)

    failed = _db(tmp_path / "failure")
    before = _heads(failed)
    report = _run(failed, _RecoveryTransport({}, fail=True), 1)
    assert report["status"] == "BLOCKED"
    assert report["first_terminal_cause"] == "CURSOR_RECOVERY_PROVIDER_UNAVAILABLE"
    assert _heads(failed) == before
    assert report["active_lease_count"] == 0


def test_crash_after_page_commit_resumes_without_head_move(tmp_path):
    path = _db(tmp_path)
    before = _heads(path)
    rows = {address: _rows(address, 1_200) for address in HEADS}
    crashed = _run(
        path, _RecoveryTransport(rows), 1,
        crash_after_work_ordinal=2,
    )
    assert crashed["status"] == "FAILED"
    assert _heads(path) == before
    resumed = _run(path, _RecoveryTransport(rows), 2)
    assert resumed["status"] == "COMPLETED"
    assert resumed["automatic_retry_created"] is False


def test_crash_after_complete_recovery_before_foundation_resumes_atomically(tmp_path):
    path = _db(tmp_path)
    before = _heads(path)
    rows = {address: _rows(address, 10) for address in HEADS}
    crashed = _run(
        path, _RecoveryTransport(rows), 1, crash_before_foundation=True
    )
    assert crashed["status"] == "FAILED"
    assert _heads(path) == before
    replay_transport = _RecoveryTransport({}, fail=True)
    completed = _run(path, replay_transport, 2)
    assert completed["status"] == "COMPLETED"
    assert replay_transport.calls == []
    assert completed["cursor_advances_committed"] == 2


def test_replay_is_zero_source_and_residue_free(tmp_path):
    path = _db(tmp_path)
    rows = {address: _rows(address, 1) for address in HEADS}
    first_transport = _RecoveryTransport(rows)
    first = _run(path, first_transport, 1)
    replay_transport = _RecoveryTransport({}, fail=True)
    replay = _run(path, replay_transport, 1)
    assert replay == first
    assert replay_transport.calls == []
    connection = sqlite3.connect(path)
    try:
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_candidate_acquisition_leases "
            "WHERE lease_state IN ('ACTIVE','STOPPING')"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_scheduler_jobs "
            "WHERE status IN ('PENDING','RUNNING','COOLDOWN')"
        ).fetchone()[0] == 0
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        connection.close()


def test_create_migration_fairness_and_namespace_isolation(tmp_path):
    path = _db(tmp_path)
    rows = {address: _rows(address, 1_200) for address in HEADS}
    transport = _RecoveryTransport(rows)
    report = _run(path, transport, 1)
    signature_addresses = [
        str(params[0]) for method, params in transport.calls
        if method == "getSignaturesForAddress"
    ]
    assert signature_addresses == [
        value for _ in range(4)
        for value in (PUMP_CREATE_INDEX_ADDRESS, PUMP_PROGRAM_ID)
    ]
    assert report["governed_requests_used"] == 8
    assert report["transport_operations_used"] == 10


@pytest.mark.parametrize(
    ("mutator", "cause"),
    [
        (lambda address: [{
            "signature": "", "slot": HEADS[address][0] + 1,
            "err": None, "confirmationStatus": "finalized",
        }], "CURSOR_RECOVERY_MALFORMED_PAGE"),
        (lambda address: [{
            "signature": "skipped-boundary", "slot": HEADS[address][0] - 1,
            "err": None, "confirmationStatus": "finalized",
        }], "CURSOR_RECOVERY_SKIP_ATTEMPT"),
    ],
)
def test_malformed_signature_and_slot_skip_fail_closed(tmp_path, mutator, cause):
    path = _db(tmp_path)
    rows = {address: mutator(address) for address in HEADS}
    report = _run(path, _RecoveryTransport(rows), 1)
    assert report["status"] == "BLOCKED"
    assert report["first_terminal_cause"] == cause
    assert report["cursor_advances_committed"] == 0


def test_unreachable_boundary_and_wrong_namespace_fail_closed(tmp_path):
    path = _db(tmp_path)
    unreachable = _run(
        path,
        _RecoveryTransport({address: [] for address in HEADS}),
        1,
    )
    assert unreachable["status"] == "BLOCKED"
    assert unreachable["first_terminal_cause"] == "CURSOR_PRIOR_BOUNDARY_UNREACHABLE"

    class WrongDirectionOwner(CursorRecoveryTransportOwner):
        def cursor_namespaces(self):
            rows = list(super().cursor_namespaces())
            rows[0] = (*rows[0][:-1], "BACKWARD")
            return tuple(rows)

    with pytest.raises(Exception, match="CURSOR_RECOVERY_NAMESPACE_MISMATCH"):
        run_cursor_continuity_recovery(
            path,
            operator_approved=True,
            transport_owner=WrongDirectionOwner(
                LiveAcquisitionConfiguration(
                    rpc_url="https://example.invalid",
                    redacted_rpc_host="example.invalid",
                ),
                _RecoveryTransport({address: [] for address in HEADS}),
            ),
            preflight=_preflight(path),
            execution_id="wrong-namespace",
            owner_id="wrong-namespace-owner",
            now=NOW,
        )


def test_duplicate_page_fails_closed(tmp_path):
    path = _db(tmp_path)
    rows = {address: _rows(address, 1_200) for address in HEADS}
    first = _run(path, _RecoveryTransport(rows), 1)
    assert first["status"] == "BLOCKED"

    class DuplicateTransport(_RecoveryTransport):
        def rpc_json(self, **kwargs):
            response = super().rpc_json(**kwargs)
            if kwargs["method"] == "getSignaturesForAddress":
                address = str(kwargs["params"][0])
                payload = self.rows_by_address[address][:250]
                return self._response(payload, kwargs["method"], kwargs["endpoint_role"])
            return response

    second = _run(path, DuplicateTransport(rows), 2)
    assert second["status"] == "BLOCKED"
    assert second["first_terminal_cause"] in {
        "CURSOR_RECOVERY_DUPLICATE_PAGE", "CURSOR_RECOVERY_REWIND_ATTEMPT"
    }
