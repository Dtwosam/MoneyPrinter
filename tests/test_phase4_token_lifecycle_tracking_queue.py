import inspect
import pathlib
import sqlite3
import sys
import tempfile
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.db import apply_migrations
from printer_v1.lifecycle import state_machine, tracking_queue
from printer_v1.lifecycle.contracts import LifecycleEvent, QueueStatus, TokenLifecycleState
from printer_v1.lifecycle.state_machine import (
    can_transition,
    classify_initial_state,
    transition_token_state,
)
from printer_v1.lifecycle.tracking_queue import (
    archive_tracking_item,
    enqueue_tracking_item,
    get_active_tracking_items,
    get_due_tracking_items,
    record_lifecycle_event,
    sync_tracking_state_with_scheduler,
)
from printer_v1.scheduler.contracts import LockResult


REQUIRED_STATES = {
    "DISCOVERED",
    "WATCH_ONLY",
    "TRACK_NORMAL",
    "TRACK_FAST",
    "PAPER_MONITORING",
    "COOLDOWN",
    "ARCHIVED",
    "INSTANT_REJECT_MEMORY_ONLY",
}

REQUIRED_EVENTS = {
    "NEW_DISCOVERY",
    "PROMOTE_TO_TRACK_FAST",
    "PROMOTE_TO_TRACK_NORMAL",
    "DEMOTE_TO_WATCH_ONLY",
    "ENTER_PAPER_MONITORING",
    "ENTER_COOLDOWN",
    "ARCHIVE_STALE_TOKEN",
    "ARCHIVE_UNUSABLE_LIQUIDITY",
    "ARCHIVE_AFTER_MEMORY_WINDOW",
    "REOPEN_REVIVED_TOKEN",
    "INSTANT_REJECT_BAD_DATA",
    "INSTANT_REJECT_UNSUPPORTED_CHAIN",
    "INSTANT_REJECT_UNUSABLE_PAIR",
    "WATCH_ONLY_REFRESH",
    "SOURCE_DATA_STALE",
    "SOURCE_DATA_CONFLICTING",
    "MANUAL_REVIEW",
}

REQUIRED_QUEUE_STATUSES = {
    "QUEUED",
    "ACTIVE",
    "PAUSED",
    "COOLDOWN",
    "ARCHIVED",
    "SKIPPED",
}

FORBIDDEN_FRAGMENTS = {
    "score",
    "confidence",
    "rank",
    "rating",
    "weight",
    "wallet",
    "private_key",
    "signed_tx",
    "live_trade",
}


class Phase4TokenLifecycleTrackingQueueTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.tempdir.name) / "printer.sqlite3"
        apply_migrations(self.db_path)
        self.now = datetime(2026, 6, 19, 12, 0, tzinfo=timezone.utc)
        self.token_id = self.insert_token("mint-a")
        self.pair_id = self.insert_pair(self.token_id, "pair-a")

    def tearDown(self):
        self.tempdir.cleanup()

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def insert_token(self, token_mint):
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO printer_tokens (token_mint, token_status) VALUES (?, ?)",
                (token_mint, TokenLifecycleState.DISCOVERED.value),
            )
            return int(cursor.lastrowid)

    def insert_pair(self, token_id, pair_address):
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO printer_pairs (token_id, pair_address, dex, pool_source)
                VALUES (?, ?, 'test_dex', 'test_pool')
                """,
                (token_id, pair_address),
            )
            return int(cursor.lastrowid)

    def enqueue(self, lane, token_id=None, pair_id=None, next_check_at=None):
        return enqueue_tracking_item(
            self.db_path,
            token_id=token_id or self.token_id,
            pair_id=self.pair_id if pair_id is None else pair_id,
            tracking_lane=lane,
            tracking_action=LifecycleEvent.NEW_DISCOVERY,
            priority_reason=f"{lane.value.lower()}_test",
            next_check_at=next_check_at or self.now,
            source_status=SourceStatus.COMPLETE,
            data_quality_label=DataQualityLabel.CLEAN_DATA,
        )

    def test_scheduler_package_has_dunder_init_not_accidental_init(self):
        self.assertTrue((SRC_PATH / "printer_v1" / "scheduler" / "__init__.py").exists())
        self.assertFalse((SRC_PATH / "printer_v1" / "scheduler" / "init.py").exists())

    def test_lifecycle_files_import_successfully(self):
        self.assertTrue(inspect.ismodule(state_machine))
        self.assertTrue(inspect.ismodule(tracking_queue))

    def test_all_required_lifecycle_states_exist(self):
        self.assertEqual({state.value for state in TokenLifecycleState}, REQUIRED_STATES)

    def test_all_required_lifecycle_events_exist(self):
        self.assertEqual({event.value for event in LifecycleEvent}, REQUIRED_EVENTS)

    def test_all_required_queue_statuses_exist(self):
        self.assertEqual({status.value for status in QueueStatus}, REQUIRED_QUEUE_STATUSES)

    def test_unsupported_chain_becomes_instant_reject_memory_only(self):
        state = classify_initial_state(
            chain="ethereum",
            source_status=SourceStatus.COMPLETE,
            data_quality_label=DataQualityLabel.CLEAN_DATA,
            has_usable_pair=True,
        )
        self.assertEqual(state, TokenLifecycleState.INSTANT_REJECT_MEMORY_ONLY)

    def test_discovered_token_allowed_moves(self):
        for new_state, event in (
            (TokenLifecycleState.WATCH_ONLY, LifecycleEvent.WATCH_ONLY_REFRESH),
            (TokenLifecycleState.TRACK_NORMAL, LifecycleEvent.PROMOTE_TO_TRACK_NORMAL),
            (TokenLifecycleState.TRACK_FAST, LifecycleEvent.PROMOTE_TO_TRACK_FAST),
            (
                TokenLifecycleState.INSTANT_REJECT_MEMORY_ONLY,
                LifecycleEvent.INSTANT_REJECT_BAD_DATA,
            ),
        ):
            self.assertTrue(can_transition(TokenLifecycleState.DISCOVERED, new_state, event))

    def test_watch_only_can_promote_to_tracking(self):
        self.assertTrue(
            can_transition(
                TokenLifecycleState.WATCH_ONLY,
                TokenLifecycleState.TRACK_NORMAL,
                LifecycleEvent.PROMOTE_TO_TRACK_NORMAL,
            )
        )
        self.assertTrue(
            can_transition(
                TokenLifecycleState.WATCH_ONLY,
                TokenLifecycleState.TRACK_FAST,
                LifecycleEvent.PROMOTE_TO_TRACK_FAST,
            )
        )

    def test_track_normal_can_promote_to_track_fast(self):
        transition = transition_token_state(
            TokenLifecycleState.TRACK_NORMAL,
            TokenLifecycleState.TRACK_FAST,
            LifecycleEvent.PROMOTE_TO_TRACK_FAST,
        )
        self.assertTrue(transition.allowed)

    def test_track_fast_can_enter_paper_monitoring_state(self):
        transition = transition_token_state(
            TokenLifecycleState.TRACK_FAST,
            TokenLifecycleState.PAPER_MONITORING,
            LifecycleEvent.ENTER_PAPER_MONITORING,
        )
        self.assertTrue(transition.allowed)

    def test_paper_monitoring_outranks_other_active_tracking_lanes(self):
        lanes = [
            TokenLifecycleState.WATCH_ONLY,
            TokenLifecycleState.TRACK_NORMAL,
            TokenLifecycleState.TRACK_FAST,
            TokenLifecycleState.PAPER_MONITORING,
        ]
        for index, lane in enumerate(lanes):
            token_id = self.insert_token(f"mint-{index}")
            pair_id = self.insert_pair(token_id, f"pair-{index}")
            self.enqueue(lane, token_id=token_id, pair_id=pair_id)
        due = get_due_tracking_items(self.db_path, now=self.now)
        self.assertEqual(due[0]["tracking_lane"], TokenLifecycleState.PAPER_MONITORING.value)

    def test_archived_token_cannot_reopen_without_explicit_reason(self):
        self.assertFalse(
            can_transition(
                TokenLifecycleState.ARCHIVED,
                TokenLifecycleState.TRACK_NORMAL,
                LifecycleEvent.WATCH_ONLY_REFRESH,
            )
        )
        self.assertTrue(
            can_transition(
                TokenLifecycleState.ARCHIVED,
                TokenLifecycleState.TRACK_NORMAL,
                LifecycleEvent.REOPEN_REVIVED_TOKEN,
            )
        )

    def test_instant_reject_cannot_enter_active_tracking_without_manual_review(self):
        self.assertFalse(
            can_transition(
                TokenLifecycleState.INSTANT_REJECT_MEMORY_ONLY,
                TokenLifecycleState.TRACK_NORMAL,
                LifecycleEvent.REOPEN_REVIVED_TOKEN,
            )
        )
        self.assertTrue(
            can_transition(
                TokenLifecycleState.INSTANT_REJECT_MEMORY_ONLY,
                TokenLifecycleState.TRACK_NORMAL,
                LifecycleEvent.MANUAL_REVIEW,
            )
        )

    def test_no_lifecycle_transition_creates_paper_decisions(self):
        transition_token_state(
            TokenLifecycleState.TRACK_FAST,
            TokenLifecycleState.PAPER_MONITORING,
            LifecycleEvent.ENTER_PAPER_MONITORING,
        )
        with self.connect() as connection:
            count = connection.execute("SELECT COUNT(*) FROM printer_paper_decisions").fetchone()[0]
        self.assertEqual(count, 0)

    def test_enqueue_tracking_item_creates_row(self):
        created, queue_id = self.enqueue(TokenLifecycleState.TRACK_NORMAL)
        self.assertTrue(created)
        self.assertIsNotNone(queue_id)

    def test_duplicate_active_tracking_rows_are_prevented(self):
        self.enqueue(TokenLifecycleState.TRACK_NORMAL)
        created, queue_id = self.enqueue(TokenLifecycleState.TRACK_NORMAL)
        self.assertFalse(created)
        self.assertIsNone(queue_id)

    def test_archived_and_instant_reject_excluded_from_active_due_tracking(self):
        _, archived_id = self.enqueue(TokenLifecycleState.TRACK_NORMAL)
        archive_tracking_item(self.db_path, queue_id=archived_id)
        other_token = self.insert_token("mint-reject")
        other_pair = self.insert_pair(other_token, "pair-reject")
        enqueue_tracking_item(
            self.db_path,
            token_id=other_token,
            pair_id=other_pair,
            tracking_lane=TokenLifecycleState.INSTANT_REJECT_MEMORY_ONLY,
            tracking_action=LifecycleEvent.INSTANT_REJECT_BAD_DATA,
            priority_reason="bad_data",
            next_check_at=self.now,
            source_status=SourceStatus.FAILED,
            data_quality_label=DataQualityLabel.MISSING_CRITICAL_DATA,
        )
        active = get_active_tracking_items(self.db_path)
        due = get_due_tracking_items(self.db_path, now=self.now)
        self.assertEqual(active, [])
        self.assertEqual(due, [])

    def test_due_tracking_order_prioritizes_expected_lanes(self):
        lane_order = [
            TokenLifecycleState.WATCH_ONLY,
            TokenLifecycleState.TRACK_NORMAL,
            TokenLifecycleState.TRACK_FAST,
            TokenLifecycleState.PAPER_MONITORING,
        ]
        for index, lane in enumerate(lane_order):
            token_id = self.insert_token(f"order-mint-{index}")
            pair_id = self.insert_pair(token_id, f"order-pair-{index}")
            self.enqueue(lane, token_id=token_id, pair_id=pair_id)
        due = get_due_tracking_items(self.db_path, now=self.now)
        self.assertEqual(
            [row["tracking_lane"] for row in due],
            [
                TokenLifecycleState.PAPER_MONITORING.value,
                TokenLifecycleState.TRACK_FAST.value,
                TokenLifecycleState.TRACK_NORMAL.value,
                TokenLifecycleState.WATCH_ONLY.value,
            ],
        )

    def test_lifecycle_event_history_is_recorded(self):
        event_id = record_lifecycle_event(
            self.db_path,
            token_id=self.token_id,
            pair_id=self.pair_id,
            previous_state=TokenLifecycleState.DISCOVERED,
            new_state=TokenLifecycleState.TRACK_NORMAL,
            lifecycle_event=LifecycleEvent.PROMOTE_TO_TRACK_NORMAL,
            priority_reason="enough_clean_source_data",
            source_status=SourceStatus.COMPLETE,
            data_quality_label=DataQualityLabel.CLEAN_DATA,
            event_payload={"source": "unit_test"},
        )
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM printer_token_lifecycle_events WHERE id = ?",
                (event_id,),
            ).fetchone()
        self.assertEqual(row["new_state"], TokenLifecycleState.TRACK_NORMAL.value)

    def test_scheduler_integration_only_creates_scheduler_rows(self):
        _, queue_id = self.enqueue(TokenLifecycleState.TRACK_FAST)
        result, job_id = sync_tracking_state_with_scheduler(
            self.db_path,
            queue_id=queue_id,
            scheduled_for=self.now + timedelta(minutes=5),
        )
        self.assertEqual(result, LockResult.ACQUIRED)
        with self.connect() as connection:
            job = connection.execute(
                "SELECT * FROM printer_scheduler_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
            paper_count = connection.execute("SELECT COUNT(*) FROM printer_paper_decisions").fetchone()[0]
        self.assertEqual(job["status"], "PENDING")
        self.assertEqual(paper_count, 0)

    def test_no_live_network_calls_or_adapter_execution_exists(self):
        source_text = "\n".join(
            inspect.getsource(obj)
            for module in (state_machine, tracking_queue)
            for _, obj in inspect.getmembers(module, inspect.isfunction)
            if obj.__module__ == module.__name__
        )
        for fragment in (
            "requests.get",
            "requests.post",
            "httpx",
            "aiohttp",
            "urllib.request",
        ):
            self.assertNotIn(fragment, source_text)

    def test_no_forbidden_concept_or_capability_is_introduced(self):
        names = []
        for module in (state_machine, tracking_queue):
            names.extend(name.lower() for name, _ in inspect.getmembers(module))
        joined_names = " ".join(names)
        self.assertFalse(any(fragment in joined_names for fragment in FORBIDDEN_FRAGMENTS))


if __name__ == "__main__":
    unittest.main()
