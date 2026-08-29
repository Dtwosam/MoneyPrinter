from __future__ import annotations

from pathlib import Path

module = Path("src/printer_v1/operator_cli/interrupted_four_token_704f53472011_residue_reconciliation.py")
text = module.read_text(encoding="utf-8")
old = '''        and str(supervision["first_terminal_cause"] or "") == TERMINAL_CAUSE\n        and supervision["cleanup_completed_at"] is not None\n'''
new = '''        and str(supervision["first_terminal_cause"] or "") == TERMINAL_CAUSE\n        and str(supervision["lease_lock_path"]) == str(LEASE_LOCK_PATH)\n        and supervision["cleanup_completed_at"] is not None\n'''
if old not in text:
    raise SystemExit("module recovered lease-path marker not found")
module.write_text(text.replace(old, new, 1), encoding="utf-8")

test = Path("tests/test_v2_9_8b_interrupted_four_token_704f53472011_residue_reconciliation.py")
text = test.read_text(encoding="utf-8")
old = '''    monkeypatch.setattr(recovery, "LEASE_LOCK_PATH", Path(residue["lease"]))\n    monkeypatch.setattr(recovery, "_default_git_head_probe", lambda _root: "proof-head")\n    with pytest.raises(recovery.InterruptedFourTokenResidueRecoveryError, match="database SHA"):\n'''
new = '''    monkeypatch.setattr(recovery, "LEASE_LOCK_PATH", Path(residue["lease"]))\n    monkeypatch.setattr(recovery, "_default_git_head_probe", lambda _root: "proof-head")\n    connection = _open(Path(residue["db"]))\n    try:\n        connection.execute(\n            "UPDATE printer_memory_factory_campaign_supervision SET lease_lock_path=? "\n            "WHERE supervision_id=?",\n            (str(residue["lease"]), recovery.SUPERVISION_ID),\n        )\n        connection.commit()\n    finally:\n        connection.close()\n    with pytest.raises(recovery.InterruptedFourTokenResidueRecoveryError, match="database SHA"):\n'''
if old not in text:
    raise SystemExit("production hard-binding test marker not found")
text = text.replace(old, new, 1)
text += '''\n\ndef test_recovered_lease_path_identity_drift_fails_closed(residue) -> None:\n    _apply_fixture(residue)\n    db = Path(residue["db"])\n    connection = _open(db)\n    try:\n        connection.execute(\n            "UPDATE printer_memory_factory_campaign_supervision SET lease_lock_path=? "\n            "WHERE supervision_id=?",\n            ("/tmp/not-the-consumed-execution.lock", recovery.SUPERVISION_ID),\n        )\n        connection.commit()\n    finally:\n        connection.close()\n    with pytest.raises(recovery.InterruptedFourTokenResidueRecoveryError):\n        recovery._reconcile(\n            operator_approved=True,\n            db_path=db,\n            repository_root=db.parent,\n            expected_git_head="proof-head",\n            expected_db_sha256=recovery._sha256(db),\n            marker_path=Path(residue["marker"]),\n            expected_marker_sha256=str(residue["marker_sha"]),\n            lease_path=Path(residue["lease"]),\n            process_probe=lambda: False,\n            git_head_probe=lambda _root: "proof-head",\n            lease_lock_path_override=Path(residue["lease"]),\n            now=NOW,\n        )\n'''
test.write_text(text, encoding="utf-8")
