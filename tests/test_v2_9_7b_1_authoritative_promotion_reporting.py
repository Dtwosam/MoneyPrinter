"""Focused V2-9.7B.1 authoritative promotion reporting checks."""

import json
import sqlite3
import unittest

from printer_v1.operator_cli.one_command_15m_factory import (
    ALREADY_EXISTS_IDEMPOTENT,
    CLEAN_PROMOTED,
    DIRTY_OR_BLOCKED,
    NO_PROMOTION,
    _authoritative_promotions_for_run,
    _memory_yield_report,
    _per_token_outcomes,
)


def _step(token_id, pair_id, window_id, e2z_status, *, close_status="SUCCEEDED"):
    pipeline = {"e2z_window_results": []}
    if e2z_status:
        pipeline["e2z_window_results"].append(
            {"window_id": window_id, "e2z_status": e2z_status}
        )
    return {
        "token_id": token_id,
        "token_mint": f"mint-{token_id}",
        "pair_id": pair_id,
        "pair_address": f"pair-{pair_id}",
        "tracking_lane": "TRACK_FAST",
        "step_kind": "WINDOW_CLOSE",
        "step_status": close_status,
        "snapshot_id": 1000 + token_id,
        "memory_window_id": window_id,
        "result_json": json.dumps({"memory_pipeline": pipeline}),
    }


def _window(window_id, token_id, pair_id, quality):
    return {
        "id": window_id,
        "token_id": token_id,
        "pair_id": pair_id,
        "window_kind": "WINDOW_15M",
        "window_status": "WINDOW_CLOSED",
        "memory_status": "PARTIAL_MEMORY",
        "memory_quality_label": quality,
        "snapshot_end_id": 2000 + token_id,
        "closed_at": "2026-07-17T00:15:00+00:00",
    }


def _episode(episode_id, window_id, token_id, pair_id):
    return {
        "id": episode_id,
        "memory_window_id": window_id,
        "token_id": token_id,
        "pair_id": pair_id,
        "window_kind": "WINDOW_15M",
    }


class AuthoritativePromotionReportingTests(unittest.TestCase):
    def test_two_token_clean_created_and_idempotent_are_isolated_and_counted_once(self):
        windows = {
            101: _window(101, 1, 11, "PARTIAL_MEMORY"),
            202: _window(202, 2, 22, "PARTIAL_MEMORY"),
        }
        steps = [
            _step(1, 11, 101, "E2Z_MEMORY_CREATED"),
            _step(2, 22, 202, "E2Z_ALREADY_EXISTS"),
        ]
        promotions = {
            101: _episode(501, 101, 1, 11),
            202: _episode(502, 202, 2, 22),
        }

        outcomes = _per_token_outcomes(steps, windows, promotions)
        by_token = {item["token_id"]: item for item in outcomes}
        self.assertEqual(by_token[1]["promotion_status"], CLEAN_PROMOTED)
        self.assertEqual(
            by_token[2]["promotion_status"], ALREADY_EXISTS_IDEMPOTENT
        )
        self.assertEqual(by_token[1]["authoritative_episode_id"], 501)
        self.assertEqual(by_token[2]["authoritative_episode_id"], 502)
        self.assertEqual(by_token[1]["memory_quality_label"], "PARTIAL_MEMORY")
        self.assertEqual(by_token[2]["memory_quality_label"], "PARTIAL_MEMORY")

        run_yield, memory = _memory_yield_report(
            outcomes, list(windows.values())
        )
        self.assertEqual(run_yield["clean"], 2)
        self.assertEqual(run_yield["clean_promoted"], 1)
        self.assertEqual(run_yield["already_exists_idempotent"], 1)
        self.assertEqual(memory["clean"], 2)
        self.assertEqual(
            memory["source_window_candidates"]["blocked_or_partial"], 2
        )

    def test_dirty_blocked_and_unpromoted_partial_remain_non_clean(self):
        windows = {
            101: _window(101, 1, 11, "DIRTY_MEMORY"),
            202: _window(202, 2, 22, "PARTIAL_MEMORY"),
        }
        outcomes = _per_token_outcomes(
            [
                _step(1, 11, 101, "LANE_Q_BLOCKED"),
                _step(2, 22, 202, None),
            ],
            windows,
            {},
        )
        self.assertEqual(outcomes[0]["promotion_status"], DIRTY_OR_BLOCKED)
        self.assertEqual(outcomes[1]["promotion_status"], NO_PROMOTION)
        run_yield, memory = _memory_yield_report(
            outcomes, list(windows.values())
        )
        self.assertEqual(run_yield["clean"], 0)
        self.assertEqual(run_yield["dirty_or_blocked"], 1)
        self.assertEqual(run_yield["no_promotion"], 1)
        self.assertEqual(memory["clean"], 0)

    def test_authoritative_query_is_read_only_eligible_and_deduplicated(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE printer_memory_factory_run_steps (
                run_id TEXT, memory_window_id INTEGER
            );
            CREATE TABLE printer_episodes (
                id INTEGER, memory_window_id INTEGER, token_id INTEGER,
                pair_id INTEGER, episode_status TEXT, memory_status TEXT,
                data_quality_label TEXT, do_not_train INTEGER,
                memory_quality_label TEXT, window_kind TEXT
            );
            INSERT INTO printer_memory_factory_run_steps VALUES ('run-a', 101);
            INSERT INTO printer_memory_factory_run_steps VALUES ('run-a', 202);
            INSERT INTO printer_memory_factory_run_steps VALUES ('run-b', 303);
            INSERT INTO printer_episodes VALUES
              (1,101,1,11,'COMPLETE','CLEAN_MEMORY','CLEAN_DATA',0,'CLEAN_MEMORY','WINDOW_15M'),
              (2,101,1,11,'COMPLETE','CLEAN_MEMORY','CLEAN_DATA',0,'CLEAN_MEMORY','WINDOW_15M'),
              (3,202,2,22,'COMPLETE','DIRTY_MEMORY','DIRTY_DATA',1,'DIRTY_MEMORY','WINDOW_15M'),
              (4,303,3,33,'COMPLETE','CLEAN_MEMORY','CLEAN_DATA',0,'CLEAN_MEMORY','WINDOW_15M');
            """
        )
        before_changes = conn.total_changes
        before_rows = conn.execute(
            "SELECT COUNT(*) FROM printer_episodes"
        ).fetchone()[0]
        promotions = _authoritative_promotions_for_run(conn, "run-a")
        after_rows = conn.execute(
            "SELECT COUNT(*) FROM printer_episodes"
        ).fetchone()[0]
        self.assertEqual(set(promotions), {101})
        self.assertEqual(promotions[101]["id"], 1)
        self.assertEqual(conn.total_changes, before_changes)
        self.assertEqual(after_rows, before_rows)
        conn.close()


if __name__ == "__main__":
    unittest.main()