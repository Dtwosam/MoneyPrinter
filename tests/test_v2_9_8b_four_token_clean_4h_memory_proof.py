"""Focused proof that the two-cycle four-token Standard-4H path forms clean memory.

This regression deliberately reuses the established disposable end-to-end factory
proof, then adds the missing success invariant: every one of the four owned
WINDOW_4H physical memories must have exactly one clean episode and one canonical
fingerprint with exact campaign/token/pair/window identity.
"""

from __future__ import annotations

import json
import sqlite3

from tests.test_v2_9_8b_full_four_token_standard4h_audit import (
    test_two_cycle_four_token_real_factory_reaches_shared_terminal_standard4h,
)


def test_two_cycle_four_token_real_factory_forms_exactly_four_clean_4h_memories(
    tmp_path,
    monkeypatch,
) -> None:
    """Require one exact clean 4h object for every admitted cycle/slot target."""
    test_two_cycle_four_token_real_factory_reaches_shared_terminal_standard4h(
        tmp_path,
        monkeypatch,
    )

    db = tmp_path / "wake-order.sqlite3"
    assert db.is_file()

    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    try:
        clean_four_hour = connection.execute(
            """SELECT cw.cycle_id,cw.token_slot_id,slot.slot_ordinal,
                      cw.memory_window_row_id,
                      slot.token_row_id AS expected_token_id,
                      slot.pair_row_id AS expected_pair_id,
                      mw.id AS physical_window_id,
                      mw.window_kind AS source_window_kind,
                      mw.outcome_label AS source_outcome_label,
                      mw.memory_status AS source_memory_status,
                      mw.memory_quality_label AS source_memory_quality_label,
                      mw.data_quality_label AS source_data_quality_label,
                      mw.do_not_train AS source_do_not_train,
                      mw.supporting_context_json AS source_context_json,
                      cw.window_state AS campaign_window_state,
                      e.id AS episode_id,
                      e.token_id AS episode_token_id,
                      e.pair_id AS episode_pair_id,
                      e.window_kind AS episode_window_kind,
                      e.episode_kind,e.memory_status,e.memory_quality_label,
                      e.data_quality_label,e.do_not_train,e.episode_outcome_label,
                      f.id AS fingerprint_id,f.fingerprint_payload_json
                 FROM printer_memory_factory_campaign_windows AS cw
                 JOIN printer_memory_factory_campaign_token_slots AS slot
                   ON slot.campaign_id=cw.campaign_id
                  AND slot.run_id=cw.run_id
                  AND slot.cycle_id=cw.cycle_id
                  AND slot.token_slot_id=cw.token_slot_id
                 JOIN printer_memory_windows AS mw
                   ON mw.id=cw.memory_window_row_id
                 LEFT JOIN printer_episodes AS e
                   ON e.memory_window_id=cw.memory_window_row_id
                  AND e.memory_status='CLEAN_MEMORY'
                 LEFT JOIN printer_memory_fingerprints AS f
                   ON f.episode_id=e.id
                  AND f.fingerprint_kind='STATIC_CONDITION_SUMMARY'
                WHERE cw.window_kind='WINDOW_4H'
                ORDER BY cw.cycle_id,slot.slot_ordinal"""
        ).fetchall()

        diagnostics = [dict(row) for row in clean_four_hour]
        assert len(clean_four_hour) == 4, diagnostics
        assert len(
            {
                (str(row["cycle_id"]), int(row["slot_ordinal"]))
                for row in clean_four_hour
            }
        ) == 4, diagnostics
        assert len(
            {int(row["physical_window_id"]) for row in clean_four_hour}
        ) == 4, diagnostics
        assert all(row["episode_id"] is not None for row in clean_four_hour), diagnostics
        assert all(
            row["fingerprint_id"] is not None for row in clean_four_hour
        ), diagnostics
        assert len({int(row["episode_id"]) for row in clean_four_hour}) == 4, diagnostics
        assert len(
            {int(row["fingerprint_id"]) for row in clean_four_hour}
        ) == 4, diagnostics

        for row in clean_four_hour:
            assert int(row["memory_window_row_id"]) == int(row["physical_window_id"])
            assert int(row["episode_token_id"]) == int(row["expected_token_id"])
            assert int(row["episode_pair_id"]) == int(row["expected_pair_id"])
            assert str(row["source_window_kind"]) == "WINDOW_4H"
            assert str(row["episode_window_kind"]) == "WINDOW_4H"
            assert str(row["episode_kind"]) == "WINDOW_4H_CLEAN_MEMORY"
            assert str(row["memory_status"]) == "CLEAN_MEMORY"
            assert str(row["memory_quality_label"]) == "CLEAN_MEMORY"
            assert str(row["data_quality_label"]) == "CLEAN_DATA"
            assert int(row["do_not_train"]) == 0
            assert str(row["source_outcome_label"] or "") not in {
                "",
                "OUTCOME_UNKNOWN",
            }
            assert str(row["episode_outcome_label"]) == str(
                row["source_outcome_label"]
            )

            payload = json.loads(str(row["fingerprint_payload_json"] or "{}"))
            assert int(payload["episode_id"]) == int(row["episode_id"])
            assert int(payload["window_id"]) == int(row["physical_window_id"])
            assert int(payload["token_id"]) == int(row["expected_token_id"])
            assert int(payload["pair_id"]) == int(row["expected_pair_id"])
            assert str(payload["window_kind"]) == "WINDOW_4H"
            assert str(payload["outcome_label"]) == str(row["episode_outcome_label"])
    finally:
        connection.close()
