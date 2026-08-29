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
text = text.replace(
    "def _seed(path: Path, lease_path: Path) -> None:\n",
    "def _seed(\n    path: Path,\n    lease_path: Path,\n    *,\n    supervision_lease_path: str | None = None,\n) -> None:\n",
    1,
)
old = '''                str(recovery.LEASE_LOCK_PATH),\n                NOW.isoformat(),\n                NOW.isoformat(),\n'''
new = '''                str(supervision_lease_path or recovery.LEASE_LOCK_PATH),\n                NOW.isoformat(),\n                NOW.isoformat(),\n'''
if old not in text:
    raise SystemExit("fixture lease path marker not found")
text = text.replace(old, new, 1)

marker = "\ndef test_production_entry_point_remains_bound_to_live_database_sha"
head, separator, _tail = text.partition(marker)
if not separator:
    raise SystemExit("production hard-binding test marker not found")
replacement = r'''

def test_production_entry_point_remains_bound_to_live_database_sha(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_reconcile(**kwargs):
        captured.update(kwargs)
        return {"status": "NOT_EXECUTED_PROOF"}

    monkeypatch.setattr(recovery, "_reconcile", fake_reconcile)
    result = recovery.reconcile_exact_interrupted_four_token_residue(
        operator_approved=True,
        db_path="/tmp/not-opened.sqlite3",
        repository_root="/tmp/not-opened-repo",
        expected_git_head="proof-head",
        process_probe=lambda: False,
        now=NOW,
    )
    assert result == {"status": "NOT_EXECUTED_PROOF"}
    assert captured["expected_db_sha256"] == recovery.EXPECTED_DB_SHA256
    assert captured["marker_path"] == recovery.APPLICATION_MARKER_PATH
    assert captured["expected_marker_sha256"] == recovery.EXPECTED_APPLICATION_MARKER_SHA256
    assert captured["lease_path"] == recovery.LEASE_LOCK_PATH
    assert captured["lease_lock_path_override"] is None


def test_recovered_lease_path_identity_drift_fails_closed(tmp_path: Path) -> None:
    db = tmp_path / "bad-lease-identity.sqlite3"
    lease = tmp_path / "campaign.lease.lock"
    marker_path = tmp_path / "application-marker.json"
    _seed(
        db,
        lease,
        supervision_lease_path="/tmp/not-the-consumed-execution.lock",
    )
    marker_sha = _marker(marker_path)
    with pytest.raises(recovery.InterruptedFourTokenResidueRecoveryError):
        recovery._reconcile(
            operator_approved=True,
            db_path=db,
            repository_root=tmp_path,
            expected_git_head="proof-head",
            expected_db_sha256=recovery._sha256(db),
            marker_path=marker_path,
            expected_marker_sha256=marker_sha,
            lease_path=lease,
            process_probe=lambda: False,
            git_head_probe=lambda _root: "proof-head",
            lease_lock_path_override=lease,
            now=NOW,
        )
'''
test.write_text(head + replacement, encoding="utf-8")
