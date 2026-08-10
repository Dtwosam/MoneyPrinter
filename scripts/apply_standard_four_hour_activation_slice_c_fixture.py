from __future__ import annotations

from pathlib import Path

TEST = "tests/test_v2_9_8b_post_dtw100_standard_four_hour_activation_factory_barrier.py"
path = Path(TEST)
text = path.read_text(encoding="utf-8")
old = '''        self.fx, self.candidates = StandardFourHourCampaignPlanningTests()._prepared()\n        self._attach_acceptable_safety(1, self.candidates[0])\n        self._attach_acceptable_safety(2, self.candidates[1])\n        self.fx.connection.commit()\n'''
new = '''        self.fx, self.candidates = StandardFourHourCampaignPlanningTests()._prepared()\n        self._attach_authoritative_clean_fingerprint(self.candidates[0])\n        self._attach_authoritative_clean_fingerprint(self.candidates[1])\n        self._attach_acceptable_safety(1, self.candidates[0])\n        self._attach_acceptable_safety(2, self.candidates[1])\n        self.fx.connection.commit()\n'''
if old not in text:
    raise RuntimeError("Slice C activation setUp anchor missing")
text = text.replace(old, new, 1)
anchor = '''    def tearDown(self) -> None:\n        self.fx.close()\n\n    def _attach_acceptable_safety(self, ordinal: int, candidate: dict[str, object]) -> int:\n'''
replacement = '''    def tearDown(self) -> None:\n        self.fx.close()\n\n    def _attach_authoritative_clean_fingerprint(self, candidate: dict[str, object]) -> int:\n        connection = self.fx.connection\n        memory_window_id = int(candidate["memory_window_1h_id"])\n        token_id = int(candidate["token_row_id"])\n        pair_id = int(candidate["pair_row_id"])\n        rows = connection.execute(\n            """SELECT id FROM printer_episodes\n               WHERE memory_window_id=? AND token_id=? AND pair_id=?\n                 AND episode_status='COMPLETE' AND memory_status='CLEAN_MEMORY'\n                 AND data_quality_label='CLEAN_DATA' AND do_not_train=0\n                 AND window_kind='WINDOW_1H' AND memory_quality_label='CLEAN_MEMORY'\n               ORDER BY id""",\n            (memory_window_id, token_id, pair_id),\n        ).fetchall()\n        self.assertEqual(len(rows), 1)\n        episode_id = int(rows[0][0])\n        payload = {\n            "episode_id": episode_id,\n            "window_id": memory_window_id,\n            "token_id": token_id,\n            "pair_id": pair_id,\n            "window_kind": "WINDOW_1H",\n        }\n        cursor = connection.execute(\n            """INSERT INTO printer_memory_fingerprints(\n                episode_id,fingerprint_kind,fingerprint_payload_json,\n                memory_status,data_quality_label,do_not_train\n            ) VALUES (?,'STATIC_CONDITION_SUMMARY',?,'CLEAN_MEMORY','CLEAN_DATA',0)""",\n            (episode_id, json.dumps(payload, sort_keys=True)),\n        )\n        return int(cursor.lastrowid)\n\n    def _attach_acceptable_safety(self, ordinal: int, candidate: dict[str, object]) -> int:\n'''
if anchor not in text:
    raise RuntimeError("Slice C activation fingerprint helper anchor missing")
path.write_text(text.replace(anchor, replacement, 1), encoding="utf-8")
