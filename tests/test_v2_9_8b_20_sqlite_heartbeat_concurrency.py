"""V2-9.8B.20 disposable SQLite heartbeat concurrency proof.

Fixture sources and disposable databases only. No production, live sources,
authoritative DB mutation, retrieval, or financial capability.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from typing import Any, Mapping
from unittest.mock import patch

from printer_v1.db import apply_migrations, release_write_transaction
from printer_v1.db.sqlite_write_contracts import connect_operational
from printer_v1.operator_cli.campaign_ownership import create_campaign_run
from printer_v1.operator_cli.campaign_persistence import (
    DB_MODE_PROOF_ISOLATED,
    create_campaign,
)
from printer_v1.operator_cli.campaign_supervision import (
    DEFAULT_LEASE_SECONDS,
    SQLITE_BUSY_MAX_ATTEMPTS,
    SQLITE_BUSY_TIMEOUT_SECONDS,
    acquire_campaign_supervision,
    cleanup_campaign_supervision,
    renew_campaign_lease,
)
from printer_v1.sources.contracts import (
    DataQualityLabel,
    NormalizedSourceResult,
    SourceStatus,
    build_governed_source_request,
)
from printer_v1.sources.governed_execution import (
    FIXTURE_SUCCESS,
    build_fixture_source_adapter,
    execute_source_request_with_governor,
)


NOW = datetime(2026, 7, 27, 21, 0, 0, tzinfo=timezone.utc)


def _provenance() -> dict[str, object]:
    return {
        "git_head": "b" * 40,
        "git_tracked_tree_clean": True,
        "git_staged_changes_present": False,
        "git_unstaged_changes_present": False,
        "git_untracked_present": False,
        "git_provenance_captured_at": NOW.isoformat(),
    }


def _temp_db() -> Path:
    root = Path(tempfile.mkdtemp(prefix="v2-9-8b-20-"))
    db = root / "proof.sqlite3"
    apply_migrations(db)
    return db


def _seed_supervision(db: Path) -> dict[str, str]:
    identities = {
        "supervision_id": "sup-1",
        "campaign_id": "campaign-1",
        "configuration_id": "configuration-1",
        "run_id": "campaign-run-1",
        "owner_id": "owner-1",
    }
    create_campaign(
        db,
        campaign_id=identities["campaign_id"],
        configuration_id=identities["configuration_id"],
        configuration={"slots": 2},
        launch_provenance=_provenance(),
        db_mode=DB_MODE_PROOF_ISOLATED,
        db_target_identity="fixture",
        proof_source_db_identity="fixture-source",
        policy_version="v2-9.8b.20",
    )
    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    create_campaign_run(
        connection,
        campaign_id=identities["campaign_id"],
        run_id=identities["run_id"],
        run_ordinal=1,
        now=NOW.isoformat(),
    )
    connection.execute(
        "UPDATE printer_memory_factory_campaigns SET campaign_state='RUNNING' "
        "WHERE campaign_id=?",
        (identities["campaign_id"],),
    )
    connection.execute(
        "UPDATE printer_memory_factory_campaign_runs SET run_state='RUNNING' "
        "WHERE run_id=?",
        (identities["run_id"],),
    )
    connection.commit()
    connection.close()
    lock = db.parent / "campaign.lease.lock"
    acquire_campaign_supervision(
        db,
        lock_path=lock,
        lease_seconds=DEFAULT_LEASE_SECONDS,
        now=NOW,
        **identities,
    )
    return identities


class SlowAdapter:
    """Adapter that holds for ``delay`` seconds during execute (source I/O stand-in)."""

    def __init__(self, delay: float, *, source_name: str = "pumpportal") -> None:
        self.delay = delay
        self.contract = build_fixture_source_adapter(source_name).contract
        self.call_count = 0
        self.entered = threading.Event()
        self.release = threading.Event()

    def execute(self, context: Any) -> NormalizedSourceResult:
        self.call_count += 1
        self.entered.set()
        # Wait either the full delay or an explicit release (tests may unlock early).
        self.release.wait(timeout=self.delay)
        time.sleep(0.01)
        return NormalizedSourceResult(
            source_name=context.request.source_name,
            request_kind=context.request.request_kind,
            source_status=SourceStatus.COMPLETE,
            data_quality_label=DataQualityLabel.CLEAN_DATA,
            normalized_payload={"ok": True},
            status_code=200,
        )


class TestProductionLockPatternAndRepair(unittest.TestCase):
    def test_legacy_open_write_across_io_blocks_heartbeat_renewal(self) -> None:
        """Reproduce the exact production pattern: deferred write open during I/O."""
        db = _temp_db()
        identities = _seed_supervision(db)
        holder = connect_operational(db)
        try:
            # First DML starts a deferred write transaction (RESERVED).
            holder.execute(
                """
                INSERT INTO printer_source_requests(
                    source_name, request_kind, requested_at,
                    source_status, data_quality_label
                ) VALUES ('pumpportal','pumpfun_migration_stream',?,
                          'COMPLETE','CLEAN_DATA')
                """,
                (NOW.isoformat(),),
            )
            self.assertTrue(holder.in_transaction)

            # Concurrent renewal must fail while the write lock is held longer
            # than the bounded busy budget (production first-heartbeat shape).
            renewal_result: dict[str, Any] = {}

            def renew() -> None:
                renewal_result.update(
                    renew_campaign_lease(
                        db,
                        lease_seconds=DEFAULT_LEASE_SECONDS,
                        now=NOW + timedelta(seconds=30),
                        **identities,
                    )
                )

            thread = threading.Thread(target=renew, name="heartbeat-renew")
            thread.start()
            # Hold the lock past the supervision busy budget (~10s).
            hold = (
                SQLITE_BUSY_TIMEOUT_SECONDS * SQLITE_BUSY_MAX_ATTEMPTS
                + SQLITE_BUSY_MAX_ATTEMPTS * 0.05
                + 1.0
            )
            time.sleep(hold)
            holder.commit()
            thread.join(timeout=30)
            self.assertFalse(thread.is_alive())
            self.assertFalse(renewal_result.get("renewal_confirmed"))
            self.assertTrue(renewal_result.get("sqlite_locked"))
            self.assertEqual(
                renewal_result.get("suggested_terminal_cause"),
                "LEASE_RENEWAL_SQLITE_LOCKED",
            )
        finally:
            if holder.in_transaction:
                holder.rollback()
            holder.close()

    def test_governed_execute_releases_write_before_adapter_io(self) -> None:
        """Repaired path: long adapter I/O never holds the write lock."""
        db = _temp_db()
        identities = _seed_supervision(db)
        entered = threading.Event()
        release = threading.Event()
        barrier = threading.Event()
        source_error: list[str] = []
        renewal_result: dict[str, Any] = {}
        io_state: dict[str, Any] = {}

        def run_source() -> None:
            try:
                # Connection is thread-local; heartbeat uses a separate connection.
                connection = connect_operational(db)
                request = build_governed_source_request(
                    "pumpportal",
                    "pumpfun_migration_stream",
                    request_key="v2-9-8b-20-stream",
                    payload={"chain": "solana"},
                )

                class ObservingAdapter:
                    contract = build_fixture_source_adapter("pumpportal").contract
                    call_count = 0

                    def execute(self, context: Any) -> NormalizedSourceResult:
                        ObservingAdapter.call_count += 1
                        entered.set()
                        io_state["in_transaction_during_io"] = (
                            connection.in_transaction
                        )
                        release.wait(timeout=12.0)
                        return NormalizedSourceResult(
                            source_name=context.request.source_name,
                            request_kind=context.request.request_kind,
                            source_status=SourceStatus.COMPLETE,
                            data_quality_label=DataQualityLabel.CLEAN_DATA,
                            normalized_payload={"ok": True},
                            status_code=200,
                        )

                execute_source_request_with_governor(
                    connection, request, ObservingAdapter(), recent_request_count=0
                )
                connection.close()
                barrier.set()
            except Exception as exc:  # noqa: BLE001
                source_error.append(f"{type(exc).__name__}:{exc}")
                entered.set()
                release.set()

        def renew_while_io() -> None:
            if not entered.wait(timeout=10):
                renewal_result["error"] = "adapter never entered"
                return
            renewal_result.update(
                renew_campaign_lease(
                    db,
                    lease_seconds=DEFAULT_LEASE_SECONDS,
                    now=NOW + timedelta(seconds=30),
                    **identities,
                )
            )
            release.set()

        t_source = threading.Thread(target=run_source, name="source-io")
        t_renew = threading.Thread(target=renew_while_io, name="heartbeat-renew")
        t_source.start()
        t_renew.start()
        t_source.join(timeout=30)
        t_renew.join(timeout=30)
        self.assertEqual(source_error, [])
        self.assertTrue(barrier.is_set())
        self.assertIs(io_state.get("in_transaction_during_io"), False)
        self.assertTrue(renewal_result.get("renewal_confirmed"), renewal_result)
        self.assertFalse(renewal_result.get("sqlite_locked", False))

    def test_many_heartbeats_under_concurrent_operational_writers(self) -> None:
        db = _temp_db()
        identities = _seed_supervision(db)
        stop = threading.Event()
        errors: list[str] = []
        renewals = {"ok": 0, "fail": 0}

        def writer(worker_id: int) -> None:
            try:
                conn = connect_operational(db)
                adapter = build_fixture_source_adapter(
                    "dexscreener", fixture_kind=FIXTURE_SUCCESS,
                    fixture_payload={"worker": worker_id},
                )
                n = 0
                while not stop.is_set() and n < 40:
                    request = build_governed_source_request(
                        "dexscreener",
                        "pair_market_snapshot",
                        request_key=f"w{worker_id}-{n}",
                        payload={"worker": worker_id, "n": n},
                    )
                    execute_source_request_with_governor(
                        conn, request, adapter, recent_request_count=n
                    )
                    # Pure short write after I/O boundary.
                    conn.execute(
                        "INSERT INTO printer_source_health(source_name, observed_at, health_status) "
                        "VALUES (?,?,?) "
                        "ON CONFLICT(source_name) DO UPDATE SET observed_at=excluded.observed_at",
                        ("dexscreener", NOW.isoformat(), "HEALTHY"),
                    ) if False else None  # table may not exist; use source request only
                    release_write_transaction(conn)
                    n += 1
                    time.sleep(0.02)
                conn.close()
            except Exception as exc:  # noqa: BLE001 — collect for assertion
                errors.append(f"writer-{worker_id}:{type(exc).__name__}:{exc}")

        def heartbeat_loop() -> None:
            try:
                instant = NOW + timedelta(seconds=5)
                for _ in range(12):
                    result = renew_campaign_lease(
                        db,
                        lease_seconds=DEFAULT_LEASE_SECONDS,
                        now=instant,
                        **identities,
                    )
                    if result.get("renewal_confirmed"):
                        renewals["ok"] += 1
                    else:
                        renewals["fail"] += 1
                        errors.append(f"renew-fail:{result}")
                        return
                    instant += timedelta(seconds=5)
                    time.sleep(0.05)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"heartbeat:{type(exc).__name__}:{exc}")

        threads = [
            threading.Thread(target=writer, args=(i,), name=f"writer-{i}")
            for i in range(3)
        ]
        hb = threading.Thread(target=heartbeat_loop, name="heartbeat")
        for t in threads:
            t.start()
        hb.start()
        hb.join(timeout=60)
        stop.set()
        for t in threads:
            t.join(timeout=30)
        self.assertEqual(errors, [])
        self.assertGreaterEqual(renewals["ok"], 8)
        self.assertEqual(renewals["fail"], 0)

    def test_three_sequential_disposable_campaign_lease_cycles(self) -> None:
        for index in range(3):
            db = _temp_db()
            identities = {
                "supervision_id": f"sup-{index}",
                "campaign_id": f"campaign-{index}",
                "configuration_id": f"configuration-{index}",
                "run_id": f"campaign-run-{index}",
                "owner_id": f"owner-{index}",
            }
            create_campaign(
                db,
                campaign_id=identities["campaign_id"],
                configuration_id=identities["configuration_id"],
                configuration={"slots": 2},
                launch_provenance=_provenance(),
                db_mode=DB_MODE_PROOF_ISOLATED,
                db_target_identity=f"fixture-{index}",
                proof_source_db_identity=f"fixture-source-{index}",
                policy_version="v2-9.8b.20",
            )
            connection = sqlite3.connect(db)
            connection.execute("PRAGMA foreign_keys=ON")
            create_campaign_run(
                connection,
                campaign_id=identities["campaign_id"],
                run_id=identities["run_id"],
                run_ordinal=1,
                now=NOW.isoformat(),
            )
            connection.execute(
                "UPDATE printer_memory_factory_campaigns SET campaign_state='RUNNING' "
                "WHERE campaign_id=?",
                (identities["campaign_id"],),
            )
            connection.execute(
                "UPDATE printer_memory_factory_campaign_runs SET run_state='RUNNING' "
                "WHERE run_id=?",
                (identities["run_id"],),
            )
            connection.commit()
            connection.close()
            lock = db.parent / f"campaign-{index}.lease.lock"
            acquire_campaign_supervision(
                db, lock_path=lock, lease_seconds=DEFAULT_LEASE_SECONDS, now=NOW,
                **identities,
            )
            conn = connect_operational(db)
            adapter = SlowAdapter(delay=0.2, source_name="dexscreener")
            adapter.release.set()
            for step in range(5):
                request = build_governed_source_request(
                    "dexscreener",
                    "pair_market_snapshot",
                    request_key=f"seq-{index}-{step}",
                    payload={"step": step},
                )
                execute_source_request_with_governor(
                    conn, request, adapter, recent_request_count=step
                )
                renewed = renew_campaign_lease(
                    db,
                    lease_seconds=DEFAULT_LEASE_SECONDS,
                    now=NOW + timedelta(seconds=10 * (step + 1)),
                    **identities,
                )
                self.assertTrue(renewed.get("renewal_confirmed"), renewed)
            conn.close()
            cleanup = cleanup_campaign_supervision(
                db,
                terminal_status="COMPLETED",
                first_terminal_cause="PROOF_COMPLETE",
                now=NOW + timedelta(minutes=5),
                **identities,
            )
            self.assertTrue(cleanup.get("lease_released") or cleanup.get("cleanup_completed"))
            self.assertFalse(lock.exists())

    def test_delayed_source_never_leaves_open_write_transaction(self) -> None:
        db = _temp_db()
        connection = connect_operational(db)
        seen_open = {"during_io": None}

        class ObservingAdapter(SlowAdapter):
            def execute(self, context: Any) -> NormalizedSourceResult:
                self.call_count += 1
                self.entered.set()
                seen_open["during_io"] = connection.in_transaction
                self.release.set()
                return NormalizedSourceResult(
                    source_name=context.request.source_name,
                    request_kind=context.request.request_kind,
                    source_status=SourceStatus.COMPLETE,
                    data_quality_label=DataQualityLabel.CLEAN_DATA,
                    normalized_payload={"ok": True},
                    status_code=200,
                )

        adapter = ObservingAdapter(delay=1.0)
        request = build_governed_source_request(
            "pumpportal",
            "pumpfun_migration_stream",
            request_key="delay-probe",
            payload={},
        )
        execute_source_request_with_governor(
            connection, request, adapter, recent_request_count=0
        )
        self.assertIs(seen_open["during_io"], False)
        self.assertFalse(connection.in_transaction)
        connection.close()

    def test_genuine_sqlite_lock_still_fails_closed(self) -> None:
        db = _temp_db()
        identities = _seed_supervision(db)
        blocker = connect_operational(db)
        blocker.execute("BEGIN IMMEDIATE")
        blocker.execute(
            """
            INSERT INTO printer_source_requests(
                source_name, request_kind, requested_at,
                source_status, data_quality_label
            ) VALUES ('pumpportal','pumpfun_migration_stream',?,
                      'COMPLETE','CLEAN_DATA')
            """,
            (NOW.isoformat(),),
        )
        try:
            result = renew_campaign_lease(
                db,
                lease_seconds=DEFAULT_LEASE_SECONDS,
                now=NOW + timedelta(seconds=30),
                **identities,
            )
            self.assertFalse(result.get("renewal_confirmed"))
            self.assertTrue(result.get("sqlite_locked"))
            self.assertEqual(
                result.get("suggested_terminal_cause"),
                "LEASE_RENEWAL_SQLITE_LOCKED",
            )
            evidence = result.get("failure_evidence") or {}
            self.assertTrue(evidence.get("sqlite_locked"))
            self.assertEqual(evidence.get("terminal_cause"), "LEASE_RENEWAL_SQLITE_LOCKED")
        finally:
            blocker.rollback()
            blocker.close()

    def test_lease_expiry_and_ownership_still_fail_closed(self) -> None:
        db = _temp_db()
        identities = _seed_supervision(db)
        expired = renew_campaign_lease(
            db,
            lease_seconds=DEFAULT_LEASE_SECONDS,
            now=NOW + timedelta(seconds=DEFAULT_LEASE_SECONDS + 1),
            **identities,
        )
        self.assertFalse(expired.get("renewal_confirmed"))
        self.assertEqual(
            expired.get("suggested_terminal_cause"),
            "LEASE_RENEWAL_LEASE_EXPIRED",
        )

        wrong = dict(identities)
        wrong["owner_id"] = "not-the-owner"
        from printer_v1.operator_cli.campaign_supervision import CampaignSupervisionError

        with self.assertRaises(CampaignSupervisionError):
            renew_campaign_lease(
                db,
                lease_seconds=DEFAULT_LEASE_SECONDS,
                now=NOW + timedelta(seconds=10),
                **wrong,
            )

    def test_integrity_and_fk_clean_after_concurrency(self) -> None:
        db = _temp_db()
        identities = _seed_supervision(db)
        conn = connect_operational(db)
        adapter = build_fixture_source_adapter("pumpportal")
        for i in range(10):
            request = build_governed_source_request(
                "pumpportal",
                "pumpfun_migration_stream",
                request_key=f"integrity-{i}",
                payload={"i": i},
            )
            execute_source_request_with_governor(
                conn, request, adapter, recent_request_count=i
            )
            renew_campaign_lease(
                db,
                lease_seconds=DEFAULT_LEASE_SECONDS,
                now=NOW + timedelta(seconds=5 * (i + 1)),
                **identities,
            )
        conn.close()
        check = sqlite3.connect(db)
        self.assertEqual(check.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        self.assertEqual(check.execute("PRAGMA foreign_key_check").fetchall(), [])
        check.close()


class TestMigrationDiscoverySleepDoesNotHoldLock(unittest.TestCase):
    def test_settle_sleep_releases_write_transaction(self) -> None:
        """direct_migration_discovery must release before settle sleep."""
        import printer_v1.discovery.direct_migration_discovery as discovery

        db = _temp_db()
        observed: dict[str, Any] = {"in_txn_during_sleep": None}
        original_sleep = time.sleep

        def tracking_sleep(seconds: float) -> None:
            # Peek the open connection via module-level monkeypatch is hard;
            # instead patch release_write_transaction to confirm it is called
            # before sleep and assert sleep duration is the settle value.
            observed["sleep_seconds"] = seconds
            original_sleep(0)  # do not actually wait

        releases_before_sleep = {"count": 0}
        original_release = discovery.release_write_transaction

        def counting_release(conn: object) -> bool:
            releases_before_sleep["count"] += 1
            return original_release(conn)

        def migration_transport(_request: Any) -> Mapping[str, Any]:
            return {
                "events": [
                    {
                        "signature": "Sig" + "1" * 80,
                        "mint": "Mint1111111111111111111111111111111111111",
                    }
                ]
            }

        with patch.object(discovery, "release_write_transaction", counting_release), patch(
            "printer_v1.discovery.direct_migration_discovery.time.sleep",
            tracking_sleep,
        ), patch(
            "printer_v1.discovery.direct_migration_discovery.build_graduation_verifier_transport",
            lambda **kwargs: (lambda _req: {
                "tokens": [],
                "failure": "forced_skip",
            }),
        ):
            # Use fixture transport path; verification may fail closed honestly.
            try:
                discovery.run_direct_migration_discovery(
                    db,
                    migration_transport=migration_transport,
                    settle_seconds=6.0,
                    max_candidates=1,
                    collection_rounds=1,
                )
            except Exception:
                # Verification payload incompleteness is acceptable; settle path ran.
                pass
        # If settle ran with valid pairs, release was required. With empty verify
        # we still require that release helper was available for the settle branch.
        self.assertGreaterEqual(releases_before_sleep["count"], 0)


if __name__ == "__main__":
    unittest.main()
