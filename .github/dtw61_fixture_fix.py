from pathlib import Path

base_path = Path("tests/test_v2_9_8b_window_15m_checkpoint8_dtw57_durable_reconstruction_red.py")
text = base_path.read_text(encoding="utf-8")

old = "def _insert_base_graph(connection: sqlite3.Connection, artifact_root: Path) -> dict:\n"
new = """def _insert_base_graph(
    connection: sqlite3.Connection,
    artifact_root: Path,
    *,
    terminal_identity_omit_field: str | None = None,
) -> dict:
"""
assert old in text
text = text.replace(old, new, 1)

anchor = """    full_run_terminal_evidence = {
        "identity": identity,
        "authorization_and_invocation": authorization_and_invocation,
        "full_run_accounting": full_run_accounting,
        "campaign_acceptance_verdict": "CAMPAIGN_PASS",
        "campaign_pass": True,
    }
"""
replacement = anchor + """    terminal_full_run_terminal_evidence = {
        **full_run_terminal_evidence,
        "identity": dict(identity),
    }
    if terminal_identity_omit_field is not None:
        assert terminal_identity_omit_field in terminal_full_run_terminal_evidence["identity"]
        terminal_full_run_terminal_evidence["identity"].pop(terminal_identity_omit_field)
"""
assert anchor in text
text = text.replace(anchor, replacement, 1)
text = text.replace(
    '        "full_run_terminal_evidence": full_run_terminal_evidence,\n',
    '        "full_run_terminal_evidence": terminal_full_run_terminal_evidence,\n',
    1,
)

old = "def _build_fixture(tmp_path: Path) -> tuple[Path, Path, dict]:\n"
new = """def _build_fixture(
    tmp_path: Path,
    *,
    terminal_identity_omit_field: str | None = None,
) -> tuple[Path, Path, dict]:
"""
assert old in text
text = text.replace(old, new, 1)
old = "        details = _insert_base_graph(connection, artifact_root)\n"
new = """        details = _insert_base_graph(
            connection,
            artifact_root,
            terminal_identity_omit_field=terminal_identity_omit_field,
        )
"""
assert old in text
text = text.replace(old, new, 1)
compile(text, str(base_path), "exec")
base_path.write_text(text, encoding="utf-8")

red_path = Path("tests/test_v2_9_8b_window_15m_checkpoint8_dtw61_required_identity_presence_red.py")
text = red_path.read_text(encoding="utf-8")
old = """    proof_dir, db_path, _summary = BASE._build_fixture(tmp_path)
    _rewrite_terminal_report_without_identity_field(proof_dir, db_path, field)
"""
new = """    proof_dir, _db_path, _summary = BASE._build_fixture(
        tmp_path,
        terminal_identity_omit_field=field,
    )
"""
assert old in text
text = text.replace(old, new, 1)
compile(text, str(red_path), "exec")
red_path.write_text(text, encoding="utf-8")
