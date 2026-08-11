from __future__ import annotations

from pathlib import Path
import json
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from printer_v1.operator_cli.campaign_authority_adapters import (
    CampaignAuthorityAdapterError,
    load_authoritative_window_safety,
)


CAMPAIGN = "campaign"
RUN = "campaign-run"
AUTH_RUN = "factory-run"
CYCLE = "cycle"
SLOT = "slot-cycle-1"
WINDOW = "cw:campaign:campaign-run:cycle:slot-cycle-1:WINDOW_1H:171"
MINT = "E9jov4Pnr2F518gmcb5Br2U6fQFbMP92h3FxZSMzpump"
PAIR = "FSfTzEkr8gDvPuv7JBvH7Zj7Saw2ZTMN7AMtSYf2SJs4"
LIFECYCLE_END = "2026-08-11T15:41:15+00:00"
CLOSING_AT = "2026-08-11T15:41:20+00:00"
EVIDENCE_AT = "2026-08-11T15:41:19+00:00"


def _fixture_db(
    path: Path,
    *,
    closing_at: str = CLOSING_AT,
    evidence_at: str = EVIDENCE_AT,
    trace_at: str = EVIDENCE_AT,
    snapshot_token_id: int = 41,
    snapshot_pair_id: int = 45,
    response_request_id: int = 1,
) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE printer_memory_factory_campaigns (
                campaign_id TEXT PRIMARY KEY
            );
            CREATE TABLE printer_memory_factory_campaign_runs (
                campaign_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                authoritative_run_id TEXT
            );
            CREATE TABLE printer_memory_factory_campaign_cycles (
                campaign_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                cycle_id TEXT NOT NULL
            );
            CREATE TABLE printer_memory_factory_campaign_token_slots (
                campaign_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                cycle_id TEXT NOT NULL,
                token_slot_id TEXT NOT NULL,
                token_identity TEXT,
                mint_identity TEXT,
                pair_identity TEXT,
                lifecycle_identity TEXT
            );
            CREATE TABLE printer_memory_factory_campaign_windows (
                campaign_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                cycle_id TEXT NOT NULL,
                token_slot_id TEXT NOT NULL,
                window_id TEXT NOT NULL,
                window_kind TEXT NOT NULL,
                window_state TEXT NOT NULL,
                token_row_id INTEGER NOT NULL,
                pair_row_id INTEGER NOT NULL,
                memory_window_row_id INTEGER,
                checkpoint_cutoff TEXT,
                support_only INTEGER NOT NULL
            );
            CREATE TABLE printer_memory_windows (
                id INTEGER PRIMARY KEY,
                token_id INTEGER NOT NULL,
                pair_id INTEGER NOT NULL,
                window_kind TEXT NOT NULL,
                window_end_at TEXT,
                snapshot_end_id INTEGER,
                supporting_context_json TEXT
            );
            CREATE TABLE printer_token_snapshots (
                id INTEGER PRIMARY KEY,
                token_id INTEGER NOT NULL,
                pair_id INTEGER NOT NULL,
                captured_at TEXT NOT NULL
            );
            CREATE TABLE printer_safety_evidence_composites (
                id INTEGER PRIMARY KEY,
                token_id INTEGER NOT NULL,
                pair_id INTEGER NOT NULL,
                snapshot_id INTEGER NOT NULL,
                memory_window_id INTEGER,
                token_mint TEXT NOT NULL,
                pair_address TEXT NOT NULL,
                evidence_captured_at TEXT NOT NULL,
                target_status TEXT NOT NULL,
                freshness_label TEXT NOT NULL,
                provenance_complete INTEGER NOT NULL,
                blockers_json TEXT,
                conflicts_json TEXT,
                safety_context_label TEXT,
                safety_contract_label TEXT,
                safety_action_label TEXT
            );
            CREATE TABLE printer_safety_evidence_contributions (
                id INTEGER PRIMARY KEY,
                composite_id INTEGER NOT NULL,
                source_name TEXT NOT NULL,
                evidence_category TEXT NOT NULL,
                source_request_id INTEGER,
                source_response_id INTEGER,
                source_failure_id INTEGER,
                captured_at TEXT NOT NULL,
                freshness_label TEXT NOT NULL,
                token_mint TEXT NOT NULL,
                pair_address TEXT NOT NULL,
                fields_supplied_json TEXT,
                source_status TEXT NOT NULL,
                data_quality_label TEXT NOT NULL,
                target_status TEXT NOT NULL,
                rejection_reason TEXT
            );
            CREATE TABLE printer_source_requests (
                id INTEGER PRIMARY KEY,
                source_name TEXT NOT NULL
            );
            CREATE TABLE printer_source_responses (
                id INTEGER PRIMARY KEY,
                source_name TEXT NOT NULL,
                source_request_id INTEGER NOT NULL
            );
            CREATE TABLE printer_source_failures (
                id INTEGER PRIMARY KEY,
                source_name TEXT NOT NULL
            );
            """
        )
        conn.execute("INSERT INTO printer_memory_factory_campaigns VALUES (?)", (CAMPAIGN,))
        conn.execute(
            "INSERT INTO printer_memory_factory_campaign_runs VALUES (?,?,?)",
            (CAMPAIGN, RUN, AUTH_RUN),
        )
        conn.execute(
            "INSERT INTO printer_memory_factory_campaign_cycles VALUES (?,?,?)",
            (CAMPAIGN, RUN, CYCLE),
        )
        conn.execute(
            "INSERT INTO printer_memory_factory_campaign_token_slots VALUES (?,?,?,?,?,?,?,?)",
            (CAMPAIGN, RUN, CYCLE, SLOT, "token-41", MINT, PAIR, "lifecycle-41"),
        )
        conn.execute(
            "INSERT INTO printer_memory_factory_campaign_windows VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                CAMPAIGN,
                RUN,
                CYCLE,
                SLOT,
                WINDOW,
                "WINDOW_1H",
                "CLEAN_PROMOTED",
                41,
                45,
                175,
                LIFECYCLE_END,
                0,
            ),
        )
        conn.execute(
            "INSERT INTO printer_memory_windows VALUES (?,?,?,?,?,?,?)",
            (
                175,
                41,
                45,
                "WINDOW_1H",
                LIFECYCLE_END,
                900,
                json.dumps(
                    {"memory_build_evidence_overlays": {"safety_composite_id": 13}},
                    sort_keys=True,
                ),
            ),
        )
        conn.execute(
            "INSERT INTO printer_token_snapshots VALUES (?,?,?,?)",
            (900, snapshot_token_id, snapshot_pair_id, closing_at),
        )
        conn.execute(
            "INSERT INTO printer_safety_evidence_composites VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                13,
                41,
                45,
                900,
                None,
                MINT,
                PAIR,
                evidence_at,
                "TARGET_MATCH",
                "SAFETY_EVIDENCE_FRESH",
                1,
                "[]",
                "[]",
                "SAFETY_CLEAN",
                "SAFETY_CLEAN",
                "PAPER_ONLY_CONTEXT",
            ),
        )
        conn.execute("INSERT INTO printer_source_requests VALUES (?,?)", (1, "goplus"))
        conn.execute(
            "INSERT INTO printer_source_responses VALUES (?,?,?)",
            (2, "goplus", response_request_id),
        )
        conn.execute(
            "INSERT INTO printer_safety_evidence_contributions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                1,
                13,
                "goplus",
                "TOKEN_SAFETY",
                1,
                2,
                None,
                trace_at,
                "SAFETY_EVIDENCE_FRESH",
                MINT,
                PAIR,
                "{}",
                "COMPLETE",
                "CLEAN_DATA",
                "TARGET_MATCH",
                None,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _load(path: Path, *, cutoff: str = LIFECYCLE_END) -> dict[str, object]:
    with patch(
        "printer_v1.operator_cli.campaign_authority_adapters.composite_row_is_acceptable",
        return_value=True,
    ):
        return load_authoritative_window_safety(
            path,
            campaign_id=CAMPAIGN,
            run_id=RUN,
            cycle_id=CYCLE,
            token_slot_id=SLOT,
            window_id=WINDOW,
            memory_window_close_cutoff=cutoff,
        )


class ThirdStandardFourHourSafetyCutoffRepairProof(unittest.TestCase):
    def _db(self, **kwargs: object) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        tmp = tempfile.TemporaryDirectory()
        path = Path(tmp.name) / "proof.sqlite3"
        _fixture_db(path, **kwargs)
        return tmp, path

    def test_real_shaped_close_uses_exact_closing_snapshot_as_evidence_cutoff(self) -> None:
        tmp, path = self._db()
        try:
            report = _load(path)
            self.assertTrue(report["gate_accepted"])
            self.assertEqual(report["reasons"], [])
            self.assertEqual(report["lifecycle_deadline"], LIFECYCLE_END)
            self.assertEqual(report["evidence_cutoff"], CLOSING_AT)
            self.assertEqual(report["evidence_cutoff_source"], "EXACT_CLOSING_SNAPSHOT")
        finally:
            tmp.cleanup()

    def test_caller_still_must_supply_exact_lifecycle_deadline(self) -> None:
        tmp, path = self._db()
        try:
            with self.assertRaises(CampaignAuthorityAdapterError):
                _load(path, cutoff="2026-08-11T15:41:16+00:00")
        finally:
            tmp.cleanup()

    def test_evidence_after_exact_closing_snapshot_still_fails_closed(self) -> None:
        tmp, path = self._db(
            evidence_at="2026-08-11T15:41:21+00:00",
            trace_at="2026-08-11T15:41:21+00:00",
        )
        try:
            report = _load(path)
            self.assertFalse(report["gate_accepted"])
            self.assertIn("safety_evidence_stale_or_post_cutoff", report["reasons"])
            self.assertIn("safety_source_trace_mismatch", report["reasons"])
        finally:
            tmp.cleanup()

    def test_stale_evidence_over_1800_seconds_still_fails_closed(self) -> None:
        tmp, path = self._db(
            closing_at="2026-08-11T16:11:20+00:00",
            evidence_at="2026-08-11T15:41:19+00:00",
            trace_at="2026-08-11T15:41:19+00:00",
        )
        try:
            report = _load(path)
            self.assertFalse(report["gate_accepted"])
            self.assertIn("safety_evidence_stale_or_post_cutoff", report["reasons"])
            self.assertIn("safety_source_trace_mismatch", report["reasons"])
        finally:
            tmp.cleanup()

    def test_wrong_exact_closing_snapshot_identity_fails_closed(self) -> None:
        tmp, path = self._db(snapshot_token_id=99)
        try:
            report = _load(path)
            self.assertFalse(report["gate_accepted"])
            self.assertIn("closing_snapshot_target_identity_mismatch", report["reasons"])
        finally:
            tmp.cleanup()

    def test_source_response_request_mismatch_still_fails_closed(self) -> None:
        tmp, path = self._db(response_request_id=99)
        try:
            report = _load(path)
            self.assertFalse(report["gate_accepted"])
            self.assertIn("safety_source_trace_mismatch", report["reasons"])
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
