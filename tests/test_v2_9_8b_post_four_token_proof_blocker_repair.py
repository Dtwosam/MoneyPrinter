"""Focused V2-9.8B post-four-token-proof blocker repair contracts (R1-R4).

Bounded offline only: in-memory SQLite and temp files. No network, no providers,
no authoritative database writes, no authorization, no marker creation, no live
Printer child, no proof execution.

R1 closeout window identity / R2 Scheduler ownership / R3 proof-root
correspondence / R4 child-terminal fidelity.
"""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from printer_v1.operator_cli.campaign_full_run_accounting import (
    OperationalLifecycleOwnershipContext,
    _load_terminal_scheduler_correspondence,
    _resolve_close_boundary_campaign_window,
    _resolve_lifecycle_scheduler_owner_disposition,
)
from printer_v1.operator_cli.window_15m_child_terminal import (
    APPLICATION_MARKER_FILENAME,
    CHILD_TERMINAL_FIELDS,
    CHILD_TERMINAL_FILENAME,
    MAX_CHILD_TERMINAL_BYTES,
    ChildTerminalBinding,
    build_child_terminal_envelope,
    read_child_terminal_envelope,
    write_child_terminal_envelope,
)


CAMPAIGN = "campaign-1"
CAMPAIGN_RUN = "campaign-run-1"
CYCLE = "cycle-1"
FACTORY_RUN = "factory-run-1"


def _context() -> OperationalLifecycleOwnershipContext:
    return OperationalLifecycleOwnershipContext(
        campaign_id=CAMPAIGN,
        campaign_run_id=CAMPAIGN_RUN,
        cycle_id=CYCLE,
        configuration_id="config-1",
        factory_run_id=FACTORY_RUN,
    )


def _canonical_window_id(slot: str) -> str:
    """The deterministic precreated proof-owned root identity."""
    return f"cw:{CAMPAIGN}:{CAMPAIGN_RUN}:{CYCLE}:{slot}:WINDOW_15M:factory-root"


def _legacy_window_id(token_id: int) -> str:
    return f"{CYCLE}:window:{token_id}"


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE printer_scheduler_jobs (
            id INTEGER PRIMARY KEY,
            status TEXT NOT NULL,
            retry_count INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE printer_memory_factory_run_steps (
            id INTEGER PRIMARY KEY,
            run_id TEXT NOT NULL,
            scheduler_job_id INTEGER,
            step_kind TEXT NOT NULL,
            token_id INTEGER NOT NULL,
            pair_id INTEGER NOT NULL,
            step_key TEXT NOT NULL
        );
        CREATE TABLE printer_memory_factory_campaign_windows (
            window_id TEXT PRIMARY KEY,
            campaign_id TEXT NOT NULL,
            run_id TEXT NOT NULL,
            cycle_id TEXT NOT NULL,
            token_slot_id TEXT NOT NULL,
            token_row_id INTEGER NOT NULL,
            pair_row_id INTEGER NOT NULL,
            window_kind TEXT NOT NULL,
            window_state TEXT,
            memory_window_row_id INTEGER
        );
        CREATE TABLE printer_memory_factory_campaign_scheduler_work (
            scheduler_work_id TEXT PRIMARY KEY,
            campaign_id TEXT NOT NULL,
            run_id TEXT NOT NULL,
            cycle_id TEXT NOT NULL,
            factory_run_id TEXT NOT NULL,
            scheduler_job_id INTEGER NOT NULL,
            token_slot_id TEXT,
            window_id TEXT,
            work_state TEXT NOT NULL,
            ownership_contract_version TEXT NOT NULL,
            stage_id TEXT,
            work_scope TEXT NOT NULL,
            target_category TEXT,
            target_identity TEXT
        );
        """
    )
    return conn


def _window(
    conn: sqlite3.Connection,
    window_id: str,
    *,
    slot: str = "slot-1",
    token_row_id: int = 57,
    pair_row_id: int = 61,
    kind: str = "WINDOW_15M",
    state: str = "CLEAN_PROMOTED",
    memory_row_id: int | None = 199,
    cycle_id: str = CYCLE,
) -> None:
    conn.execute(
        """INSERT INTO printer_memory_factory_campaign_windows
           (window_id,campaign_id,run_id,cycle_id,token_slot_id,token_row_id,
            pair_row_id,window_kind,window_state,memory_window_row_id)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (
            window_id, CAMPAIGN, CAMPAIGN_RUN, cycle_id, slot, token_row_id,
            pair_row_id, kind, state, memory_row_id,
        ),
    )


def _step(
    conn: sqlite3.Connection,
    step_id: int,
    *,
    job_id: int,
    step_kind: str,
    token_id: int = 57,
    pair_id: int = 61,
    step_key: str = "t1_snapshot_00",
    status: str = "SUCCEEDED",
) -> None:
    conn.execute(
        "INSERT INTO printer_scheduler_jobs(id,status,retry_count) VALUES (?,?,0)",
        (job_id, status),
    )
    conn.execute(
        """INSERT INTO printer_memory_factory_run_steps
           (id,run_id,scheduler_job_id,step_kind,token_id,pair_id,step_key)
           VALUES (?,?,?,?,?,?,?)""",
        (step_id, FACTORY_RUN, job_id, step_kind, token_id, pair_id, step_key),
    )


def _owner(
    conn: sqlite3.Connection,
    job_id: int,
    *,
    window_id: str,
    stage_id: str = "WINDOW_15M",
    slot: str = "slot-1",
    work_id: str | None = None,
    campaign_id: str = CAMPAIGN,
    run_id: str = CAMPAIGN_RUN,
    cycle_id: str = CYCLE,
    factory_run_id: str = FACTORY_RUN,
    work_scope: str = "WINDOW_LIFECYCLE",
    contract: str = "V2_STAGE_SCOPED",
    target_category: str = "CAMPAIGN_WINDOW",
    target_identity: str | None = None,
    work_state: str = "SUCCEEDED",
) -> None:
    conn.execute(
        """INSERT INTO printer_memory_factory_campaign_scheduler_work
           (scheduler_work_id,campaign_id,run_id,cycle_id,factory_run_id,
            scheduler_job_id,token_slot_id,window_id,work_state,
            ownership_contract_version,stage_id,work_scope,target_category,
            target_identity)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            work_id or f"cw15m:{campaign_id}:{run_id}:{cycle_id}:{slot}:"
            f"{window_id}:{job_id}",
            campaign_id, run_id, cycle_id, factory_run_id, job_id, slot,
            window_id, work_state, contract, stage_id, work_scope,
            target_category,
            window_id if target_identity is None else target_identity,
        ),
    )


# ---------------------------------------------------------------------------
# R1 — closeout window identity
# ---------------------------------------------------------------------------


class R1CloseoutWindowIdentity(unittest.TestCase):
    def _resolve(self, conn, **overrides):
        kwargs = dict(
            context=_context(),
            token_slot_id="slot-1",
            token_id=57,
            pair_id=61,
            memory_row_id=199,
        )
        kwargs.update(overrides)
        return _resolve_close_boundary_campaign_window(conn, **kwargs)

    def test_canonical_precreated_window_is_the_authority(self) -> None:
        conn = _db()
        canonical = _canonical_window_id("slot-1")
        _window(conn, canonical)
        window_id, state, blocked = self._resolve(conn)
        self.assertEqual(window_id, canonical)
        self.assertEqual(state, "CLEAN_PROMOTED")
        self.assertEqual(blocked, [])

    def test_no_replacement_row_is_ever_created(self) -> None:
        conn = _db()
        _window(conn, _canonical_window_id("slot-1"))
        before = conn.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_windows"
        ).fetchone()[0]
        self._resolve(conn)
        after = conn.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_windows"
        ).fetchone()[0]
        self.assertEqual(before, after)

    def test_legacy_non_precreated_shape_keeps_historical_identity(self) -> None:
        conn = _db()
        window_id, state, blocked = self._resolve(conn)
        self.assertEqual(window_id, _legacy_window_id(57))
        self.assertIsNone(state)
        self.assertEqual(blocked, [])

    def test_duplicate_slot_binding_blocks(self) -> None:
        conn = _db()
        _window(conn, _canonical_window_id("slot-1"))
        _window(conn, _legacy_window_id(57), memory_row_id=199)
        _window_id, state, blocked = self._resolve(conn)
        self.assertIsNone(state)
        self.assertEqual(blocked, ["CAMPAIGN_WINDOW_IDENTITY_AMBIGUOUS:57"])

    def test_wrong_slot_token_binding_blocks(self) -> None:
        conn = _db()
        _window(conn, _canonical_window_id("slot-1"), token_row_id=58)
        _window_id, state, blocked = self._resolve(conn)
        self.assertIsNone(state)
        self.assertEqual(blocked, ["CAMPAIGN_WINDOW_IDENTITY_MISMATCH:57"])

    def test_wrong_pair_binding_blocks(self) -> None:
        conn = _db()
        _window(conn, _canonical_window_id("slot-1"), pair_row_id=62)
        _window_id, state, blocked = self._resolve(conn)
        self.assertEqual(blocked, ["CAMPAIGN_WINDOW_IDENTITY_MISMATCH:57"])

    def test_wrong_memory_binding_still_blocks(self) -> None:
        conn = _db()
        _window(conn, _canonical_window_id("slot-1"), memory_row_id=1234)
        _window_id, state, blocked = self._resolve(conn)
        self.assertIsNone(state)
        self.assertEqual(
            blocked, ["WINDOW_NOT_REGISTERED_AT_CLOSE_BOUNDARY:57"]
        )

    def test_unbound_memory_still_blocks(self) -> None:
        conn = _db()
        _window(conn, _canonical_window_id("slot-1"), memory_row_id=None)
        _window_id, _state, blocked = self._resolve(conn)
        self.assertEqual(
            blocked, ["WINDOW_NOT_REGISTERED_AT_CLOSE_BOUNDARY:57"]
        )

    def test_foreign_cycle_window_is_not_authority(self) -> None:
        conn = _db()
        _window(conn, _canonical_window_id("slot-1"), cycle_id="other-cycle")
        window_id, state, blocked = self._resolve(conn)
        self.assertEqual(window_id, _legacy_window_id(57))
        self.assertIsNone(state)
        self.assertEqual(blocked, [])


# ---------------------------------------------------------------------------
# R2 — Scheduler ownership
# ---------------------------------------------------------------------------


class R2SchedulerOwnership(unittest.TestCase):
    def _resolve(self, conn, *, job_id=2060, window_id=None, slot="slot-1"):
        return _resolve_lifecycle_scheduler_owner_disposition(
            conn,
            context=_context(),
            scheduler_job_id=job_id,
            token_slot_id=slot,
            window_id=window_id or _canonical_window_id("slot-1"),
        )

    def test_unowned_legacy_work_is_still_projected(self) -> None:
        conn = _db()
        disposition, reason = self._resolve(conn)
        self.assertEqual(disposition, "PROJECT")
        self.assertIsNone(reason)

    def test_exact_canonical_owner_is_verified_not_reprojected(self) -> None:
        conn = _db()
        canonical = _canonical_window_id("slot-1")
        _owner(conn, 2060, window_id=canonical)
        disposition, reason = self._resolve(conn, window_id=canonical)
        self.assertEqual(disposition, "VERIFIED")
        self.assertIsNone(reason)

    def test_duplicate_owner_fails_closed(self) -> None:
        conn = _db()
        canonical = _canonical_window_id("slot-1")
        _owner(conn, 2060, window_id=canonical)
        _owner(conn, 2060, window_id=canonical, work_id="campaign-work|c|2060")
        disposition, reason = self._resolve(conn, window_id=canonical)
        self.assertEqual(disposition, "BLOCKED")
        self.assertEqual(reason, "SCHEDULER_OWNERSHIP_DUPLICATE:2060")

    def test_each_identity_field_mismatch_fails_closed(self) -> None:
        canonical = _canonical_window_id("slot-1")
        cases = {
            "ownership_contract_version": {"contract": "V1_WINDOW_BOUND"},
            "work_scope": {"work_scope": "TERMINAL_CLEANUP"},
            "campaign_id": {"campaign_id": "other-campaign"},
            "run_id": {"run_id": "other-run"},
            "cycle_id": {"cycle_id": "other-cycle"},
            "factory_run_id": {"factory_run_id": "other-factory-run"},
            "token_slot_id": {"slot": "slot-2"},
            "window_id": {"window_id": _legacy_window_id(57)},
            "target_category": {"target_category": "TRACKING_QUEUE"},
            "target_identity": {"target_identity": "not-the-window"},
        }
        for field, override in cases.items():
            with self.subTest(field=field):
                conn = _db()
                kwargs = {"window_id": canonical}
                kwargs.update(override)
                _owner(conn, 2060, **kwargs)
                disposition, reason = self._resolve(conn, window_id=canonical)
                self.assertEqual(disposition, "BLOCKED")
                self.assertEqual(
                    reason, f"SCHEDULER_OWNERSHIP_CONFLICT:2060:{field}"
                )

    def test_owner_of_a_different_job_does_not_leak(self) -> None:
        conn = _db()
        canonical = _canonical_window_id("slot-1")
        _owner(conn, 2061, window_id=canonical)
        disposition, _reason = self._resolve(conn, job_id=2060)
        self.assertEqual(disposition, "PROJECT")


# ---------------------------------------------------------------------------
# R3 — proof-root correspondence
# ---------------------------------------------------------------------------


class R3ProofRootCorrespondence(unittest.TestCase):
    def test_bare_root_stage_accepted_only_for_threaded_step_identity(self) -> None:
        conn = _db()
        canonical = _canonical_window_id("slot-1")
        _window(conn, canonical)
        _step(conn, 615, job_id=2060, step_kind="SNAPSHOT")
        _owner(conn, 2060, window_id=canonical, stage_id="WINDOW_15M")

        rejected = _load_terminal_scheduler_correspondence(
            conn, context=_context(), standard_four_hour_campaign=False
        )
        self.assertFalse(rejected["correspondence_exact"])
        self.assertEqual(rejected["lineage_mismatch_job_ids"], [2060])

        accepted = _load_terminal_scheduler_correspondence(
            conn,
            context=_context(),
            standard_four_hour_campaign=False,
            proof_root_stage_step_ids=(615,),
        )
        self.assertTrue(accepted["correspondence_exact"])
        self.assertEqual(accepted["lineage_mismatch_job_ids"], [])

    def test_stage_acceptance_is_not_broadened_to_untreaded_steps(self) -> None:
        conn = _db()
        canonical = _canonical_window_id("slot-1")
        _window(conn, canonical)
        _step(conn, 615, job_id=2060, step_kind="SNAPSHOT")
        _owner(conn, 2060, window_id=canonical, stage_id="WINDOW_15M")
        _step(
            conn, 616, job_id=2061, step_kind="SNAPSHOT",
            step_key="t1_snapshot_01",
        )
        _owner(
            conn, 2061, window_id=canonical, stage_id="WINDOW_15M",
            work_id="cw15m:other:2061",
        )
        result = _load_terminal_scheduler_correspondence(
            conn,
            context=_context(),
            standard_four_hour_campaign=False,
            proof_root_stage_step_ids=(615,),
        )
        self.assertFalse(result["correspondence_exact"])
        self.assertEqual(result["lineage_mismatch_job_ids"], [2061])

    def test_ordinary_slot_stage_rules_are_unchanged(self) -> None:
        for stage in ("WINDOW_15M_SLOT_1", f"{CAMPAIGN}|WINDOW_15M_SLOT_1|2"):
            with self.subTest(stage=stage):
                conn = _db()
                canonical = _canonical_window_id("slot-1")
                _window(conn, canonical)
                _step(conn, 615, job_id=2060, step_kind="SNAPSHOT")
                _owner(conn, 2060, window_id=canonical, stage_id=stage)
                result = _load_terminal_scheduler_correspondence(
                    conn, context=_context(), standard_four_hour_campaign=False
                )
                self.assertTrue(result["correspondence_exact"])

    def test_long_window_rules_are_unchanged_with_and_without_the_set(self) -> None:
        for step_ids in (None, (615, 616, 617)):
            with self.subTest(threaded=step_ids is not None):
                conn = _db()
                w15 = _canonical_window_id("slot-1")
                _window(conn, w15)
                _window(conn, "w1h", kind="WINDOW_1H", memory_row_id=None)
                _window(conn, "w4h", kind="WINDOW_4H", memory_row_id=None)
                _step(conn, 615, job_id=2060, step_kind="SNAPSHOT")
                _owner(conn, 2060, window_id=w15, stage_id="WINDOW_15M_SLOT_1")
                _step(
                    conn, 616, job_id=2061, step_kind="CONTINUATION_SNAPSHOT",
                    step_key="t1_cont_00",
                )
                _owner(
                    conn, 2061, window_id="w1h", stage_id="WINDOW_1H",
                    work_id="cw1h:2061",
                )
                _step(
                    conn, 617, job_id=2062,
                    step_kind="LONG_CONTINUATION_SNAPSHOT",
                    step_key="t1_long_00",
                )
                _owner(
                    conn, 2062, window_id="w4h", stage_id="WINDOW_4H",
                    work_id="cw4h:2062",
                )
                result = _load_terminal_scheduler_correspondence(
                    conn,
                    context=_context(),
                    standard_four_hour_campaign=True,
                    proof_root_stage_step_ids=step_ids,
                )
                self.assertTrue(result["correspondence_exact"])
                self.assertEqual(result["lifecycle_job_ids"], [2060, 2061, 2062])

    def test_threaded_set_never_rescues_a_wrong_long_window_stage(self) -> None:
        conn = _db()
        _window(conn, "w1h", kind="WINDOW_1H", memory_row_id=None)
        _step(
            conn, 616, job_id=2061, step_kind="CONTINUATION_SNAPSHOT",
            step_key="t1_cont_00",
        )
        _owner(
            conn, 2061, window_id="w1h", stage_id="WINDOW_15M",
            work_id="cw1h:2061",
        )
        result = _load_terminal_scheduler_correspondence(
            conn,
            context=_context(),
            standard_four_hour_campaign=True,
            proof_root_stage_step_ids=(616,),
        )
        self.assertFalse(result["correspondence_exact"])
        self.assertEqual(result["lineage_mismatch_job_ids"], [2061])


# ---------------------------------------------------------------------------
# R4 — child-terminal fidelity
# ---------------------------------------------------------------------------


PROOF_MODE = "four-token-bounded-capacity-proof-run"


def _proof_shaped_terminal_result(report_path: str) -> dict[str, object]:
    """The R4-repaired four-token result boundary shape (no proof verdict)."""
    return {
        "status": "OPERATIONAL_CAMPAIGN_TERMINAL",
        "execution_id": "20260816T213315Z-5039b5eecb81",
        "campaign_id": "20260816T213315Z-5039b5eecb81-campaign",
        "run_id": "20260816T213315Z-5039b5eecb81-campaign-run",
        "cycle_id": "20260816T213315Z-5039b5eecb81-cycle",
        "supervision_id": "20260816T213315Z-5039b5eecb81-supervision",
        "lifecycle_started": True,
        "cleanup_complete": True,
        "lease_released": True,
        "active_locked_work": {"active_owned_work_after": 0},
        "database_identity_after": {
            "path": "/tmp/printer_v1.sqlite3",
            "exists": True,
            "sha256": "9f08f9022b58b9d9ec917ca485b68af2bd7d32c38a8fce6031156c3e853026e7",
            "size": 96645120,
            "inode": 1230526,
            "mtime_ns": 1786907911431630352,
        },
        "source_calls": 15,
        "scheduler_runtime_calls": 22,
        "terminal_report_path": report_path,
        "run_status": "SAFE_STOPPED",
        "first_terminal_cause": "TERMINAL_TRACKING_STATE",
        "campaign_acceptance_verdict": "BLOCKED_UNSAFE",
        "campaign_pass": False,
    }


class R4ChildTerminalFidelity(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.marker = root / APPLICATION_MARKER_FILENAME
        self.marker.write_text(
            json.dumps({"authorization_id": "V2_9_8B_TEST_AUTH_0001"}),
            encoding="utf-8",
        )
        self.report = root / "campaign-report.json"
        self.report.write_text(json.dumps({"report": True}), encoding="utf-8")
        self.binding = ChildTerminalBinding(
            terminal_path=root / CHILD_TERMINAL_FILENAME,
            marker_path=self.marker,
            authorization_id="V2_9_8B_TEST_AUTH_0001",
            marker_sha256="0" * 64,
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _build(self, source):
        return build_child_terminal_envelope(
            binding=self.binding, source=source, mode=PROOF_MODE,
            exit_code=0, success=True,
        )

    def test_available_truth_is_projected(self) -> None:
        payload = self._build(_proof_shaped_terminal_result(str(self.report)))
        self.assertTrue(payload["lifecycle_started"])
        self.assertEqual(payload["cycle_id"], "20260816T213315Z-5039b5eecb81-cycle")
        self.assertEqual(
            payload["supervision_id"], "20260816T213315Z-5039b5eecb81-supervision"
        )
        self.assertTrue(payload["cleanup_complete"])
        self.assertTrue(payload["lease_released"])
        self.assertEqual(
            payload["active_locked_work"], {"active_owned_work_after": 0}
        )
        self.assertEqual(payload["database_identity_after"]["size"], 96645120)
        self.assertEqual(payload["source_calls"], 15)
        self.assertEqual(payload["scheduler_runtime_calls"], 22)
        self.assertEqual(payload["terminal_report_path"], str(self.report))

    def test_report_hash_is_derived_from_the_real_file(self) -> None:
        import hashlib

        payload = self._build(_proof_shaped_terminal_result(str(self.report)))
        self.assertEqual(
            payload["terminal_report_sha256"],
            hashlib.sha256(self.report.read_bytes()).hexdigest(),
        )

    def test_database_writes_is_never_invented(self) -> None:
        payload = self._build(_proof_shaped_terminal_result(str(self.report)))
        self.assertIsNone(payload["database_writes"])

    def test_schema_allow_list_is_unchanged(self) -> None:
        payload = self._build(_proof_shaped_terminal_result(str(self.report)))
        self.assertEqual(set(payload), set(CHILD_TERMINAL_FIELDS))

    def test_child_exited_zero_is_not_proof_pass(self) -> None:
        source = _proof_shaped_terminal_result(str(self.report))
        payload = self._build(source)
        # Process disposition only; no proof/campaign verdict may be carried.
        self.assertIs(payload["success"], True)
        self.assertEqual(payload["process_exit_code"], 0)
        self.assertEqual(
            payload["terminal_category"], "OPERATIONAL_COMMAND_COMPLETE"
        )
        self.assertNotIn("campaign_acceptance_verdict", payload)
        self.assertNotIn("campaign_pass", payload)
        self.assertNotIn("proof_pass", payload)
        self.assertEqual(source["campaign_acceptance_verdict"], "BLOCKED_UNSAFE")

    def test_success_still_must_agree_with_exit_code(self) -> None:
        from printer_v1.operator_cli.window_15m_child_terminal import (
            ChildTerminalError,
        )

        with self.assertRaises(ChildTerminalError):
            build_child_terminal_envelope(
                binding=self.binding,
                source=_proof_shaped_terminal_result(str(self.report)),
                mode=PROOF_MODE, exit_code=1, success=True,
            )

    def test_envelope_round_trips_within_bounds_and_create_once(self) -> None:
        import hashlib

        marker_sha = hashlib.sha256(self.marker.read_bytes()).hexdigest()
        binding = ChildTerminalBinding(
            terminal_path=self.binding.terminal_path,
            marker_path=self.marker,
            authorization_id="V2_9_8B_TEST_AUTH_0001",
            marker_sha256=marker_sha,
        )
        write_child_terminal_envelope(
            binding=binding,
            source=_proof_shaped_terminal_result(str(self.report)),
            mode=PROOF_MODE, exit_code=0, success=True,
        )
        self.assertLessEqual(
            binding.terminal_path.stat().st_size, MAX_CHILD_TERMINAL_BYTES
        )
        payload = read_child_terminal_envelope(
            binding.terminal_path,
            expected_authorization_id="V2_9_8B_TEST_AUTH_0001",
            expected_marker_path=self.marker,
            expected_marker_sha256=marker_sha,
            expected_exit_code=0,
            expected_mode=PROOF_MODE,
        )
        self.assertEqual(payload["source_calls"], 15)
        from printer_v1.operator_cli.window_15m_child_terminal import (
            ChildTerminalError,
        )

        with self.assertRaises(ChildTerminalError):
            write_child_terminal_envelope(
                binding=binding,
                source=_proof_shaped_terminal_result(str(self.report)),
                mode=PROOF_MODE, exit_code=0, success=True,
            )

    def test_unsafe_terminal_detail_is_still_redacted(self) -> None:
        source = _proof_shaped_terminal_result(str(self.report))
        source["status"] = "leaked api_key material"
        payload = self._build(source)
        self.assertEqual(payload["status"], "[REDACTED_UNSAFE_TERMINAL_DETAIL]")


# ---------------------------------------------------------------------------
# Fixture A — CONSUMED-SHAPE NEGATIVE CONTROL
# ---------------------------------------------------------------------------


class ConsumedShapeNegativeControl(unittest.TestCase):
    """One cycle, two tokens, canonical cw windows, canonical ownership.

    After repair this shape carries no false window/Scheduler/correspondence
    blocker — and it must still FAIL the four-token proof because it holds only
    2 tokens / 1 cycle and no through-4h evidence.
    """

    TOKENS = ((57, 61, "slot-1", 199), (58, 62, "slot-2", 200))

    def _build(self) -> tuple[sqlite3.Connection, tuple[int, ...]]:
        conn = _db()
        step_ids: list[int] = []
        step_id = 615
        job_id = 2060
        for token_id, pair_id, slot, memory_row in self.TOKENS:
            _window(
                conn, _canonical_window_id(slot), slot=slot,
                token_row_id=token_id, pair_row_id=pair_id,
                memory_row_id=memory_row,
            )
        # 16 SNAPSHOT + 2 WINDOW_CLOSE, exactly the consumed proof shape.
        plan = [("SNAPSHOT", index) for index in range(8)] + [("WINDOW_CLOSE", 0)]
        for ordinal, (token_id, pair_id, slot, _memory) in enumerate(
            self.TOKENS, start=1
        ):
            for kind, index in plan:
                _step(
                    conn, step_id, job_id=job_id, step_kind=kind,
                    token_id=token_id, pair_id=pair_id,
                    step_key=f"t{ordinal}_{kind.lower()}_{index:02d}",
                )
                _owner(
                    conn, job_id, window_id=_canonical_window_id(slot),
                    stage_id="WINDOW_15M", slot=slot,
                )
                step_ids.append(step_id)
                step_id += 1
                job_id += 1
        return conn, tuple(step_ids)

    def test_no_false_window_registration_blocker(self) -> None:
        conn, _ = self._build()
        for token_id, pair_id, slot, memory_row in self.TOKENS:
            window_id, state, blocked = _resolve_close_boundary_campaign_window(
                conn, context=_context(), token_slot_id=slot,
                token_id=token_id, pair_id=pair_id, memory_row_id=memory_row,
            )
            self.assertEqual(window_id, _canonical_window_id(slot))
            self.assertEqual(state, "CLEAN_PROMOTED")
            self.assertEqual(blocked, [])

    def test_no_false_scheduler_projection_blocker(self) -> None:
        conn, _ = self._build()
        rows = conn.execute(
            "SELECT scheduler_job_id, token_slot_id, window_id "
            "FROM printer_memory_factory_campaign_scheduler_work "
            "ORDER BY scheduler_job_id"
        ).fetchall()
        self.assertEqual(len(rows), 18)
        for row in rows:
            disposition, reason = _resolve_lifecycle_scheduler_owner_disposition(
                conn, context=_context(),
                scheduler_job_id=int(row["scheduler_job_id"]),
                token_slot_id=str(row["token_slot_id"]),
                window_id=str(row["window_id"]),
            )
            self.assertEqual(disposition, "VERIFIED", msg=reason)
            self.assertIsNone(reason)

    def test_truthful_correspondence_after_repair(self) -> None:
        conn, step_ids = self._build()
        result = _load_terminal_scheduler_correspondence(
            conn, context=_context(), standard_four_hour_campaign=True,
            proof_root_stage_step_ids=step_ids,
        )
        self.assertTrue(result["correspondence_exact"])
        self.assertTrue(result["all_lifecycle_jobs_succeeded"])
        self.assertEqual(result["lineage_mismatch_job_ids"], [])
        self.assertEqual(result["missing_ownership"], [])
        self.assertEqual(result["extra_ownership"], [])
        self.assertEqual(result["expected_lifecycle_scheduler_count"], 18)

    def test_still_fails_the_four_token_proof(self) -> None:
        """Capacity/through-4h evidence is absent; the repair cannot supply it."""
        conn, _ = self._build()
        distinct_tokens = conn.execute(
            "SELECT COUNT(DISTINCT token_id) FROM printer_memory_factory_run_steps"
        ).fetchone()[0]
        distinct_cycles = conn.execute(
            "SELECT COUNT(DISTINCT cycle_id) "
            "FROM printer_memory_factory_campaign_scheduler_work"
        ).fetchone()[0]
        long_windows = conn.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_windows "
            "WHERE window_kind IN ('WINDOW_1H','WINDOW_4H')"
        ).fetchone()[0]
        through_4h_steps = conn.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_run_steps "
            "WHERE step_kind LIKE '%CONTINUATION%'"
        ).fetchone()[0]
        # Four-token proof capacity is 4 tokens across 2 cycles with through-4h
        # evidence. This shape satisfies none of it.
        self.assertEqual(distinct_tokens, 2)
        self.assertLess(distinct_tokens, 4)
        self.assertEqual(distinct_cycles, 1)
        self.assertLess(distinct_cycles, 2)
        self.assertEqual(long_windows, 0)
        self.assertEqual(through_4h_steps, 0)


# ---------------------------------------------------------------------------
# Fixture B — SYNTHETIC SUCCESS-SHAPED ACCOUNTING FIXTURE
# ---------------------------------------------------------------------------


class SyntheticSuccessShapedAccounting(unittest.TestCase):
    """Recognition-only fixture.

    This proves solely that correct ownership / window / stage / evidence is
    recognised by the repaired owners. It is NOT the four-token proof, asserts
    nothing about proof capacity or campaign PASS, and can never stand in for a
    real bounded-capacity proof.
    """

    def _build(self) -> tuple[sqlite3.Connection, tuple[int, ...]]:
        conn = _db()
        _window(conn, _canonical_window_id("slot-1"))
        _step(conn, 615, job_id=2060, step_kind="SNAPSHOT")
        _owner(
            conn, 2060, window_id=_canonical_window_id("slot-1"),
            stage_id="WINDOW_15M",
        )
        _step(
            conn, 616, job_id=2061, step_kind="WINDOW_CLOSE",
            step_key="t1_window_close_00",
        )
        _owner(
            conn, 2061, window_id=_canonical_window_id("slot-1"),
            stage_id="WINDOW_15M",
        )
        return conn, (615, 616)

    def test_correct_window_identity_is_recognised(self) -> None:
        conn, _ = self._build()
        window_id, state, blocked = _resolve_close_boundary_campaign_window(
            conn, context=_context(), token_slot_id="slot-1",
            token_id=57, pair_id=61, memory_row_id=199,
        )
        self.assertEqual(window_id, _canonical_window_id("slot-1"))
        self.assertEqual(state, "CLEAN_PROMOTED")
        self.assertEqual(blocked, [])

    def test_correct_ownership_is_recognised_without_a_second_owner(self) -> None:
        conn, _ = self._build()
        for job_id in (2060, 2061):
            disposition, reason = _resolve_lifecycle_scheduler_owner_disposition(
                conn, context=_context(), scheduler_job_id=job_id,
                token_slot_id="slot-1",
                window_id=_canonical_window_id("slot-1"),
            )
            self.assertEqual(disposition, "VERIFIED")
            self.assertIsNone(reason)
        owner_rows = conn.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_scheduler_work"
        ).fetchone()[0]
        self.assertEqual(owner_rows, 2)

    def test_correct_stage_and_evidence_are_recognised(self) -> None:
        conn, step_ids = self._build()
        result = _load_terminal_scheduler_correspondence(
            conn, context=_context(), standard_four_hour_campaign=False,
            proof_root_stage_step_ids=step_ids,
        )
        self.assertTrue(result["correspondence_exact"])
        self.assertTrue(result["all_lifecycle_jobs_succeeded"])
        self.assertEqual(result["lifecycle_job_ids"], [2060, 2061])
        self.assertEqual(result["lineage_mismatch_job_ids"], [])


# ---------------------------------------------------------------------------
# R4 — terminal-boundary projection wiring
# ---------------------------------------------------------------------------


class R4TerminalBoundaryProjection(unittest.TestCase):
    """The campaign terminal result must carry the truth the child terminal reads."""

    def setUp(self) -> None:
        from printer_v1.operator_cli.operational_memory_factory_command import (
            _child_terminal_truth_projection,
        )

        self._project = _child_terminal_truth_projection
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.db = root / "printer_v1.sqlite3"
        self.db.write_bytes(b"authoritative-bytes")
        self.artifact = root / "campaign-report.json"
        self.artifact.write_text(json.dumps({"report": True}), encoding="utf-8")
        self.cleanup = {
            "cleanup_completed": True,
            "lease_released": True,
            "active_owned_work_after": 0,
        }
        self.report = {
            "campaign_source_calls": 15,
            "artifact_path": str(self.artifact),
        }

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _projection(self, **overrides):
        kwargs = dict(
            cycle_id="cycle-1",
            supervision_id="supervision-1",
            lifecycle_started=True,
            cleanup_result=self.cleanup,
            report=self.report,
            scheduler_runtime_calls=22,
            db_path=self.db,
        )
        kwargs.update(overrides)
        return self._project(**kwargs)

    def test_projection_supplies_every_repaired_field(self) -> None:
        projection = self._projection()
        self.assertEqual(
            set(projection),
            {
                "cycle_id", "supervision_id", "lifecycle_started",
                "cleanup_complete", "lease_released", "active_locked_work",
                "database_identity_after", "source_calls",
                "scheduler_runtime_calls", "terminal_report_path",
            },
        )
        self.assertEqual(projection["cycle_id"], "cycle-1")
        self.assertEqual(projection["supervision_id"], "supervision-1")
        self.assertIs(projection["lifecycle_started"], True)
        self.assertIs(projection["cleanup_complete"], True)
        self.assertIs(projection["lease_released"], True)
        self.assertEqual(
            projection["active_locked_work"], {"active_owned_work_after": 0}
        )
        self.assertEqual(projection["source_calls"], 15)
        self.assertEqual(projection["scheduler_runtime_calls"], 22)
        self.assertEqual(projection["terminal_report_path"], str(self.artifact))

    def test_projection_never_invents_database_writes(self) -> None:
        self.assertNotIn("database_writes", self._projection())

    def test_projection_carries_no_proof_or_campaign_verdict(self) -> None:
        projection = self._projection()
        for forbidden in (
            "campaign_pass", "campaign_acceptance_verdict",
            "operational_lifecycle_pass", "proof_pass", "success",
        ):
            self.assertNotIn(forbidden, projection)

    def test_database_identity_is_a_real_read_only_capture(self) -> None:
        import hashlib

        identity = self._projection()["database_identity_after"]
        self.assertIs(identity["exists"], True)
        self.assertEqual(
            identity["sha256"], hashlib.sha256(self.db.read_bytes()).hexdigest()
        )
        self.assertEqual(identity["size"], len(b"authoritative-bytes"))
        self.assertEqual(self.db.read_bytes(), b"authoritative-bytes")

    def test_untruthful_cleanup_is_never_upgraded(self) -> None:
        projection = self._projection(
            cleanup_result={"cleanup_completed": False, "lease_released": None},
        )
        self.assertIs(projection["cleanup_complete"], False)
        self.assertIs(projection["lease_released"], False)
        self.assertIsNone(projection["active_locked_work"])

    def test_missing_owners_project_none_rather_than_zero(self) -> None:
        projection = self._projection(cleanup_result=None, report=None)
        self.assertIsNone(projection["source_calls"])
        self.assertIsNone(projection["terminal_report_path"])
        self.assertIsNone(projection["active_locked_work"])

    def test_projection_feeds_the_child_terminal_envelope_end_to_end(self) -> None:
        import hashlib

        root = Path(self._tmp.name)
        marker = root / APPLICATION_MARKER_FILENAME
        marker.write_text(
            json.dumps({"authorization_id": "V2_9_8B_TEST_AUTH_0002"}),
            encoding="utf-8",
        )
        binding = ChildTerminalBinding(
            terminal_path=root / CHILD_TERMINAL_FILENAME,
            marker_path=marker,
            authorization_id="V2_9_8B_TEST_AUTH_0002",
            marker_sha256=hashlib.sha256(marker.read_bytes()).hexdigest(),
        )
        terminal = {
            "status": "OPERATIONAL_CAMPAIGN_TERMINAL",
            "execution_id": "exec-1",
            "campaign_id": "campaign-1",
            "run_id": "campaign-run-1",
            **self._projection(),
            "campaign_acceptance_verdict": "BLOCKED_UNSAFE",
            "campaign_pass": False,
        }
        payload = build_child_terminal_envelope(
            binding=binding, source=terminal, mode=PROOF_MODE,
            exit_code=0, success=True,
        )
        for field in (
            "cycle_id", "supervision_id", "lifecycle_started",
            "cleanup_complete", "lease_released", "active_locked_work",
            "database_identity_after", "source_calls",
            "scheduler_runtime_calls", "terminal_report_path",
            "terminal_report_sha256",
        ):
            self.assertIsNotNone(payload[field], msg=field)
        self.assertIsNone(payload["database_writes"])
        self.assertEqual(set(payload), set(CHILD_TERMINAL_FIELDS))
        # Process exited zero, campaign verdict BLOCKED_UNSAFE — no proof PASS.
        self.assertIs(payload["success"], True)
        self.assertNotIn("campaign_acceptance_verdict", payload)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
