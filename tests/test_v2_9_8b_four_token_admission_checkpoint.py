from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sqlite3
from types import SimpleNamespace

from printer_v1.operator_cli.four_token_admission_checkpoint import (
    CHECKPOINT_RUNTIME_SECONDS,
    FOUR_TOKEN_ADMISSION_CHECKPOINT_MODE,
    TERMINAL_CAUSE,
    exact_admission_checkpoint_policy,
)
from printer_v1.operator_cli.four_token_admission_checkpoint_one_shot_wrapper import (
    AUTHORIZED_COMMAND_MODE,
    build_child_command,
    fixture_authorization_document,
    validate_four_token_admission_checkpoint_authorization_document,
)
from printer_v1.operator_cli.four_token_factory_adapter import (
    validate_four_token_admission_checkpoint,
)
from printer_v1.operator_cli.one_command_15m_factory import (
    _later_cycle_admission_deadline,
    _resolve_four_token_no_accounting_shared_terminal,
)
from printer_v1.operator_cli.window_15m_child_terminal import CHILD_TERMINAL_MODE_SCHEMAS


def test_checkpoint_authority_is_exact_and_continuations_are_locked() -> None:
    policy = exact_admission_checkpoint_policy()
    assert FOUR_TOKEN_ADMISSION_CHECKPOINT_MODE == AUTHORIZED_COMMAND_MODE
    assert CHECKPOINT_RUNTIME_SECONDS == 900
    assert policy["configured_tokens"] == 4
    assert policy["configured_active_cycles"] == 2
    assert policy["tokens_per_cycle"] == 2
    assert policy["minimum_cycle_admission_spacing_seconds"] == 300
    assert policy["later_cycle_pre_admission_deadline_seconds_after_cycle_one"] == 600
    assert policy["cycle1_interleaving_window"] == "WINDOW_15M"
    assert policy["cycle2_lifecycle_planning_allowed"] is False
    assert policy["continuation_windows_activated"] is False
    assert policy["locked_windows"] == [
        "WINDOW_1H", "WINDOW_4H", "WINDOW_12H", "WINDOW_24H"
    ]
    assert FOUR_TOKEN_ADMISSION_CHECKPOINT_MODE in CHILD_TERMINAL_MODE_SCHEMAS
    assert build_child_command("python")[-2:] == [
        FOUR_TOKEN_ADMISSION_CHECKPOINT_MODE, "--operator-approved"
    ]


def test_checkpoint_authorization_document_binds_reduced_policy() -> None:
    now = datetime.now(timezone.utc)
    document = fixture_authorization_document(
        branch="assistant/test",
        head="a" * 40,
        database={
            "path": "/tmp/test.sqlite3",
            "sha256": "b" * 64,
            "size": 1,
            "inode": 2,
            "mtime_ns": 3,
            "migration_count": 62,
            "migration_head": "062_pre_admission_attempt_evidence.sql",
        },
        authorization_id="V2_9_8B_FOUR_TOKEN_ADMISSION_CHECKPOINT_AUTH_TESTONLY",
        migration_execution_id="MIGRATION_062_TESTONLY",
        authorized_at=now.isoformat(),
        expires_at=(now + timedelta(minutes=10)).isoformat(),
    )
    validated = validate_four_token_admission_checkpoint_authorization_document(document)
    assert validated["authorized_command"]["mode"] == FOUR_TOKEN_ADMISSION_CHECKPOINT_MODE
    assert validated["operational_policy"] == exact_admission_checkpoint_policy()


def _shape_db() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(
        """
        CREATE TABLE printer_memory_factory_campaign_cycles(
          cycle_id TEXT, campaign_id TEXT, run_id TEXT, cycle_ordinal INTEGER,
          created_at TEXT, cycle_state TEXT, first_terminal_cause TEXT
        );
        CREATE TABLE printer_memory_factory_campaign_token_slots(
          cycle_id TEXT, campaign_id TEXT, run_id TEXT, slot_ordinal INTEGER,
          token_row_id INTEGER, mint_identity TEXT, pair_row_id INTEGER,
          pair_identity TEXT, tracking_queue_id INTEGER
        );
        CREATE TABLE printer_pre_admission_discovery_attempts(
          attempt_id TEXT, campaign_id TEXT, campaign_run_id TEXT,
          authoritative_factory_run_id TEXT, proposed_cycle_ordinal INTEGER,
          attempt_state TEXT, consumed_cycle_id TEXT, consumed_at TEXT
        );
        CREATE TABLE printer_pre_admission_discovery_attempt_items(
          attempt_id TEXT, slot_ordinal INTEGER, token_row_id INTEGER,
          mint_identity TEXT, pair_row_id INTEGER, pair_identity TEXT
        );
        CREATE TABLE printer_memory_factory_campaign_windows(
          campaign_id TEXT, run_id TEXT, cycle_id TEXT
        );
        CREATE TABLE printer_memory_factory_campaign_scheduler_work(
          campaign_id TEXT, run_id TEXT, cycle_id TEXT
        );
        """
    )
    start = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)
    second = start + timedelta(seconds=360)
    for cycle_id, ordinal, instant in (("c1", 1, start), ("c2", 2, second)):
        c.execute(
            "INSERT INTO printer_memory_factory_campaign_cycles VALUES (?,?,?,?,?,?,?)",
            (cycle_id, "camp", "run", ordinal, instant.isoformat(),
             "TERMINAL_STOPPED", TERMINAL_CAUSE),
        )
    for cycle_id, base in (("c1", 0), ("c2", 2)):
        for slot in (1, 2):
            n = base + slot
            c.execute(
                "INSERT INTO printer_memory_factory_campaign_token_slots "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (cycle_id, "camp", "run", slot, n, f"mint-{n}",
                 100+n, f"pair-{n}", 200+n),
            )
    c.execute(
        "INSERT INTO printer_pre_admission_discovery_attempts VALUES (?,?,?,?,?,?,?,?)",
        ("attempt-2", "camp", "run", "factory", 2, "CONSUMED",
         "c2", second.isoformat()),
    )
    for slot, n in ((1, 3), (2, 4)):
        c.execute(
            "INSERT INTO printer_pre_admission_discovery_attempt_items VALUES "
            "(?,?,?,?,?,?)",
            ("attempt-2", slot, n, f"mint-{n}", 100+n, f"pair-{n}"),
        )
    return c


def test_durable_checkpoint_shape_proves_exact_four_slots_and_consumed_cycle2() -> None:
    c = _shape_db()
    evidence = validate_four_token_admission_checkpoint(
        c, campaign_id="camp", campaign_run_id="run", factory_run_id="factory"
    )
    assert evidence["admission_checkpoint_pass"] is True
    assert evidence["cycle_ids"] == ["c1", "c2"]
    assert evidence["slot_count"] == 4
    assert evidence["cycle_spacing_seconds"] == 360
    assert evidence["cycle2_attempt_state"] == "CONSUMED"
    assert evidence["cycle2_lifecycle_windows"] == 0
    assert evidence["cycle2_lifecycle_work"] == 0


def test_two_cycle_checkpoint_is_valid_no_accounting_shared_terminal() -> None:
    c = sqlite3.connect(":memory:")
    status, cause = _resolve_four_token_no_accounting_shared_terminal(
        c,
        campaign_id="camp",
        campaign_run_id="run",
        factory_run_id="factory",
        phase_a=(
            {"cycle_state": "TERMINAL_STOPPED", "first_terminal_cause": TERMINAL_CAUSE},
            {"cycle_state": "TERMINAL_STOPPED", "first_terminal_cause": TERMINAL_CAUSE},
        ),
    )
    assert status == "SAFE_STOPPED"
    assert cause == TERMINAL_CAUSE


def test_cycle2_deadline_is_anchored_to_atomic_cycle1_slot_admission() -> None:
    connection = sqlite3.connect(":memory:")
    connection.executescript(
        """
        CREATE TABLE printer_memory_factory_campaign_cycles(
          cycle_id TEXT, campaign_id TEXT, run_id TEXT, cycle_ordinal INTEGER,
          created_at TEXT
        );
        CREATE TABLE printer_memory_factory_campaign_token_slots(
          cycle_id TEXT, campaign_id TEXT, run_id TEXT, slot_ordinal INTEGER,
          created_at TEXT
        );
        """
    )
    setup = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)
    admitted = setup + timedelta(minutes=12)
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_cycles VALUES (?,?,?,?,?)",
        ("c1", "camp", "run", 1, setup.isoformat()),
    )
    for ordinal in (1, 2):
        connection.execute(
            "INSERT INTO printer_memory_factory_campaign_token_slots "
            "VALUES (?,?,?,?,?)",
            ("c1", "camp", "run", ordinal, admitted.isoformat()),
        )
    deadline = _later_cycle_admission_deadline(
        connection,
        binding=SimpleNamespace(campaign_id="camp", campaign_run_id="run"),
        first_cycle_id="c1",
        seconds_after_first_cycle=600,
    )
    assert deadline == admitted + timedelta(minutes=10)
    assert deadline != setup + timedelta(minutes=10)
