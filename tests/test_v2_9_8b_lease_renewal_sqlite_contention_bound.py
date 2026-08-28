"""Focused proofs for hard-deadline lease renewal contention (design L1–L9)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
from unittest.mock import patch

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.campaign_ownership import create_campaign_run
from printer_v1.operator_cli.campaign_persistence import (
    DB_MODE_PROOF_ISOLATED,
    create_campaign,
)
from printer_v1.operator_cli import campaign_supervision as supervision
from printer_v1.operator_cli.campaign_supervision import (
    DEFAULT_LEASE_SECONDS,
    LEASE_CONTENTION_WALL_CLOCK_SECONDS,
    acquire_campaign_supervision,
    renew_campaign_lease,
)


NOW = datetime(2026, 8, 28, 22, 0, 0, tzinfo=timezone.utc)


def _provenance() -> dict[str, object]:
    return {
        "git_head": "c" * 40,
        "git_tracked_tree_clean": True,
        "git_staged_changes_present": False,
        "git_unstaged_changes_present": False,
        "git_untracked_present": False,
        "git_provenance_captured_at": NOW.isoformat(),
    }


def _temp_db() -> Path:
    root = Path(tempfile.mkdtemp(prefix="v2-9-8b-lease-contention-"))
    db = root / "proof.sqlite3"
    apply_migrations(db)
    return db


def _seed(db: Path, *, lease_seconds: int = DEFAULT_LEASE_SECONDS) -> dict[str, str]:
    identities = {
        "supervision_id": "sup-lease-1",
        "campaign_id": "campaign-lease-1",
        "configuration_id": "configuration-lease-1",
        "run_id": "campaign-run-lease-1",
        "owner_id": "owner-lease-1",
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
        policy_version="v2-9.8b-lease-contention",
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
    lock = db.parent / "campaign.lease.lock"
    acquire_campaign_supervision(
        db,
        lock_path=lock,
        lease_seconds=lease_seconds,
        now=NOW,
        **identities,
    )
    return identities


def test_l1_l2_brief_contention_clears_and_confirms_db_file_agreement() -> None:
    db = _temp_db()
    identities = _seed(db)
    blocker = sqlite3.connect(db, timeout=0.1)
    blocker.execute("BEGIN IMMEDIATE")
    blocker.execute("CREATE TABLE IF NOT EXISTS _hold(x INTEGER)")
    release = threading.Event()
    done = {}

    def _renew() -> None:
        done["result"] = renew_campaign_lease(
            db,
            lease_seconds=DEFAULT_LEASE_SECONDS,
            now=NOW + timedelta(seconds=30),
            **identities,
        )

    thread = threading.Thread(target=_renew)
    thread.start()
    time.sleep(0.3)
    blocker.rollback()
    blocker.close()
    release.set()
    thread.join(timeout=20)
    assert thread.is_alive() is False
    result = done["result"]
    assert result["renewal_confirmed"] is True
    assert result["db_ledger_advanced"] is True
    assert result["lease_file_synced"] is True
    assert result["contention_outer_attempts"] >= 1
    connection = sqlite3.connect(db)
    row = connection.execute(
        "SELECT heartbeat_at,lease_expires_at,lease_lock_path "
        "FROM printer_memory_factory_campaign_supervision WHERE supervision_id=?",
        (identities["supervision_id"],),
    ).fetchone()
    connection.close()
    payload = supervision._lock_payload(Path(row[2]))
    assert payload["heartbeat_at"] == row[0] == result["heartbeat_at"]
    assert payload["lease_expires_at"] == row[1] == result["lease_expires_at"]


def test_l3_prolonged_contention_fails_within_hard_deadline() -> None:
    db = _temp_db()
    identities = _seed(db)
    blocker = sqlite3.connect(db, timeout=0.1)
    blocker.execute("BEGIN IMMEDIATE")
    blocker.execute("CREATE TABLE IF NOT EXISTS _hold(x INTEGER)")
    started = time.monotonic()
    result = renew_campaign_lease(
        db,
        lease_seconds=DEFAULT_LEASE_SECONDS,
        now=NOW + timedelta(seconds=30),
        **identities,
    )
    elapsed = time.monotonic() - started
    blocker.rollback()
    blocker.close()
    assert result["renewal_confirmed"] is False
    assert result["suggested_terminal_cause"] == "LEASE_RENEWAL_SQLITE_LOCKED"
    assert result["sqlite_locked"] is True
    assert result["db_ledger_advanced"] is False
    assert elapsed <= LEASE_CONTENTION_WALL_CLOCK_SECONDS + 0.250


def test_l4_insufficient_deadline_does_not_start_blocking_wait() -> None:
    db = _temp_db()
    identities = _seed(db)
    with patch.object(supervision, "LEASE_CONTENTION_WALL_CLOCK_SECONDS", 0.0):
        started = time.monotonic()
        result = renew_campaign_lease(
            db,
            lease_seconds=DEFAULT_LEASE_SECONDS,
            now=NOW + timedelta(seconds=30),
            **identities,
        )
        elapsed = time.monotonic() - started
    assert result["renewal_confirmed"] is False
    assert result["suggested_terminal_cause"] == "LEASE_RENEWAL_SQLITE_LOCKED"
    assert elapsed < 1.0


def test_l4_insufficient_lease_safety_fails_without_wait() -> None:
    db = _temp_db()
    identities = _seed(db, lease_seconds=20)
    started = time.monotonic()
    result = renew_campaign_lease(
        db,
        lease_seconds=DEFAULT_LEASE_SECONDS,
        now=NOW + timedelta(seconds=6),
        **identities,
    )
    elapsed = time.monotonic() - started
    assert result["renewal_confirmed"] is False
    assert result["suggested_terminal_cause"] == "LEASE_RENEWAL_SQLITE_LOCKED"
    assert elapsed < 1.0


def test_l5_expired_lease_fails_immediately() -> None:
    db = _temp_db()
    identities = _seed(db)
    result = renew_campaign_lease(
        db,
        lease_seconds=DEFAULT_LEASE_SECONDS,
        now=NOW + timedelta(seconds=DEFAULT_LEASE_SECONDS + 1),
        **identities,
    )
    assert result["renewal_confirmed"] is False
    assert result["suggested_terminal_cause"] == "LEASE_RENEWAL_LEASE_EXPIRED"
    assert result["sqlite_locked"] is False


def test_l6_ownership_mismatch_fails_without_contention_retry() -> None:
    db = _temp_db()
    identities = _seed(db)
    bad = dict(identities)
    bad["owner_id"] = "other-owner"
    try:
        renew_campaign_lease(
            db,
            lease_seconds=DEFAULT_LEASE_SECONDS,
            now=NOW + timedelta(seconds=30),
            **bad,
        )
    except supervision.CampaignSupervisionError as exc:
        assert "ownership mismatch" in str(exc).lower()
    else:
        raise AssertionError("expected ownership mismatch to raise")


def test_l7_db_commit_file_failure_is_unconfirmed_partial() -> None:
    db = _temp_db()
    identities = _seed(db)
    lock = Path(
        sqlite3.connect(db)
        .execute(
            "SELECT lease_lock_path FROM printer_memory_factory_campaign_supervision "
            "WHERE supervision_id=?",
            (identities["supervision_id"],),
        )
        .fetchone()[0]
    )
    before = lock.read_text(encoding="utf-8")
    with patch.object(
        supervision,
        "_replace_lock",
        side_effect=supervision.CampaignSupervisionError(
            "operational lease replacement unconfirmed after 1 attempt(s)"
        ),
    ):
        result = renew_campaign_lease(
            db,
            lease_seconds=DEFAULT_LEASE_SECONDS,
            now=NOW + timedelta(seconds=30),
            **identities,
        )
    assert result["renewal_confirmed"] is False
    assert result["suggested_terminal_cause"] == "LEASE_RENEWAL_UNCONFIRMED"
    assert result["db_ledger_advanced"] is True
    assert result["lease_file_synced"] is False
    connection = sqlite3.connect(db)
    row = connection.execute(
        "SELECT heartbeat_at FROM printer_memory_factory_campaign_supervision "
        "WHERE supervision_id=?",
        (identities["supervision_id"],),
    ).fetchone()
    connection.close()
    assert row[0] == (NOW + timedelta(seconds=30)).isoformat()
    assert lock.read_text(encoding="utf-8") == before


def test_l8_pre_commit_db_failure_leaves_file_untouched() -> None:
    db = _temp_db()
    identities = _seed(db)
    lock = Path(
        sqlite3.connect(db)
        .execute(
            "SELECT lease_lock_path FROM printer_memory_factory_campaign_supervision "
            "WHERE supervision_id=?",
            (identities["supervision_id"],),
        )
        .fetchone()[0]
    )
    before = lock.read_text(encoding="utf-8")
    blocker = sqlite3.connect(db, timeout=0.1)
    blocker.execute("BEGIN IMMEDIATE")
    with patch.object(supervision, "LEASE_CONTENTION_OUTER_MAX_ATTEMPTS", 1), patch.object(
        supervision, "LEASE_CONTENTION_WALL_CLOCK_SECONDS", 2.0
    ), patch.object(supervision, "SQLITE_BUSY_TIMEOUT_SECONDS", 0.05), patch.object(
        supervision, "SQLITE_BUSY_MAX_ATTEMPTS", 1
    ):
        result = renew_campaign_lease(
            db,
            lease_seconds=DEFAULT_LEASE_SECONDS,
            now=NOW + timedelta(seconds=30),
            **identities,
        )
    blocker.rollback()
    blocker.close()
    assert result["renewal_confirmed"] is False
    assert result["db_ledger_advanced"] is False
    after = supervision._lock_payload(lock)
    before_payload = __import__("json").loads(before)
    assert after["heartbeat_at"] == before_payload["heartbeat_at"]
    assert after["lease_expires_at"] == before_payload["lease_expires_at"]


def test_l9_renewal_retries_create_no_duplicate_campaign_or_scheduler_work() -> None:
    db = _temp_db()
    identities = _seed(db)
    before_jobs = sqlite3.connect(db).execute(
        "SELECT COUNT(*) FROM printer_scheduler_jobs"
    ).fetchone()[0]
    renew_campaign_lease(
        db,
        lease_seconds=DEFAULT_LEASE_SECONDS,
        now=NOW + timedelta(seconds=30),
        **identities,
    )
    after_jobs = sqlite3.connect(db).execute(
        "SELECT COUNT(*) FROM printer_scheduler_jobs"
    ).fetchone()[0]
    campaigns = sqlite3.connect(db).execute(
        "SELECT COUNT(*) FROM printer_memory_factory_campaigns"
    ).fetchone()[0]
    assert after_jobs == before_jobs
    assert campaigns == 1
