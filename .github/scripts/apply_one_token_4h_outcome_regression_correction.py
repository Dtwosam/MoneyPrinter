from pathlib import Path

path = Path('tests/test_v2_8_1_one_token_4h_runtime.py')
text = path.read_text()

old_import = '''from printer_v1.operator_cli.one_token_4h_runtime import (\n'''
new_import = '''from printer_v1.operator_cli import one_command_15m_factory as factory\nfrom printer_v1.operator_cli.one_token_4h_runtime import (\n'''
if text.count(old_import) != 1:
    raise SystemExit(f'import marker count={text.count(old_import)}')
text = text.replace(old_import, new_import, 1)

old = '''        self.conn.commit()\n        quality = run_4h_quality_gates(str(self.db), int(result["window_id"]))\n        self.assertEqual(quality["lane_k_status"], "LANE_K_COMPLETED")\n'''
new = '''        self.conn.commit()\n        outcome_owner = getattr(factory, "_derive_and_persist_four_hour_outcome", None)\n        self.assertIsNotNone(\n            outcome_owner,\n            "canonical full-path WINDOW_4H outcome owner is missing",\n        )\n        outcome = outcome_owner(\n            self.conn,\n            run_id=run_id,\n            token_id=token_id,\n            pair_id=pair_id,\n            window_id=int(result["window_id"]),\n            current_close_snapshot_id=int(closing_id),\n        )\n        self.conn.commit()\n        self.assertNotEqual(outcome["outcome_label"], "OUTCOME_UNKNOWN")\n        quality = run_4h_quality_gates(str(self.db), int(result["window_id"]))\n        self.assertEqual(quality["lane_k_status"], "LANE_K_COMPLETED")\n'''
if text.count(old) != 1:
    raise SystemExit(f'quality marker count={text.count(old)}')
text = text.replace(old, new, 1)
path.write_text(text)
