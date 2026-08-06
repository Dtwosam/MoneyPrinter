from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


test_path = Path(
    "tests/test_v2_9_8b_window_15m_checkpoint_2_preflight_initialization.py"
)
text = test_path.read_text(encoding="utf-8")
anchor = "\ndef test_cycle_insert_failure_rolls_back_entire_initialization_graph(tmp_path: Path):\n"
wal_test = r'''

def test_wal_logical_drift_blocks_when_main_file_sha_is_unchanged(tmp_path: Path):
    db = _migrated_db(tmp_path)
    setup = sqlite3.connect(db)
    try:
        assert setup.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
    finally:
        setup.close()
    assert not Path(f"{db}-wal").exists()
    assert not Path(f"{db}-shm").exists()

    preflight = _preflight(db)
    writer = sqlite3.connect(db)
    try:
        writer.execute("CREATE TABLE checkpoint2_wal_drift(value INTEGER)")
        writer.commit()
        assert _sha256(db) == preflight["database_sha256"]
        assert Path(f"{db}-wal").is_file()
        assert Path(f"{db}-shm").is_file()

        _clear_action_context()
        with pytest.raises(
            Exception,
            match="AUTHORIZED_DATABASE_RUNTIME_STATE_CHANGED_BEFORE_FIRST_WRITE",
        ):
            _create(db, tmp_path, preflight=preflight)
    finally:
        writer.close()

    assert _graph_counts(db) == {
        "campaigns": 0,
        "configurations": 0,
        "runs": 0,
        "cycles": 0,
    }
    assert command._ACTION_RUN_CONTEXT["campaign_id"] is None
    assert command._ACTION_RUN_CONTEXT["run_id"] is None
    assert command._ACTION_RUN_CONTEXT["cycle_id"] is None
'''
text = replace_once(text, anchor, wal_test + anchor, "WAL test insertion")
test_path.write_text(text, encoding="utf-8")


persistence = Path("src/printer_v1/operator_cli/campaign_persistence.py")
text = persistence.read_text(encoding="utf-8")
old = '''        connection.execute("BEGIN IMMEDIATE")\n        if _sha256_file(path) != expected_sha:\n'''
new = '''        connection.execute("BEGIN IMMEDIATE")\n        journal_mode_row = connection.execute("PRAGMA journal_mode").fetchone()\n        journal_mode = (\n            str(journal_mode_row[0]).strip().lower()\n            if journal_mode_row is not None\n            else ""\n        )\n        runtime_sidecars = tuple(\n            str(candidate)\n            for candidate in (\n                Path(f"{path}-wal"),\n                Path(f"{path}-shm"),\n                Path(f"{path}-journal"),\n            )\n            if candidate.exists()\n        )\n        if journal_mode != "delete" or runtime_sidecars:\n            raise CampaignPersistenceError(\n                "AUTHORIZED_DATABASE_RUNTIME_STATE_CHANGED_BEFORE_FIRST_WRITE:"\n                f"journal_mode={journal_mode or 'unknown'}:"\n                f"sidecars={','.join(runtime_sidecars) or 'none'}"\n            )\n        if _sha256_file(path) != expected_sha:\n'''
text = replace_once(text, old, new, "first-write runtime-state repair")
persistence.write_text(text, encoding="utf-8")


closeout = Path(
    "docs/printer-v1-v2-9-8b-window-15m-checkpoint-2-preflight-initialization-closeout.md"
)
text = closeout.read_text(encoding="utf-8")
text = replace_once(
    text,
    "Three deterministic initialization defects and one exact-write-evidence defect",
    "Four deterministic initialization defects and one exact-write-evidence defect",
    "closeout finding count",
)
text = replace_once(
    text,
    "4. `INITIALIZATION_MUTATION_IDENTITY_INCOMPLETENESS`\n   - The action-local recorder identified campaign/configuration/run inserts but omitted cycle insertion and campaign/run state updates, understating authoritative initialization writes.\n\nNo defect was found",
    "4. `INITIALIZATION_MUTATION_IDENTITY_INCOMPLETENESS`\n   - The action-local recorder identified campaign/configuration/run inserts but omitted cycle insertion and campaign/run state updates, understating authoritative initialization writes.\n5. `AUTHORIZED_DATABASE_RUNTIME_STATE_CHANGED_BEFORE_FIRST_WRITE`\n   - In SQLite WAL mode, a committed logical mutation can remain only in `-wal` while the main database file SHA-256 remains unchanged. The first-write owner previously accepted that unauthorized logical drift.\n\nNo defect was found",
    "closeout WAL finding",
)
text = replace_once(
    text,
    "- It acquires one `BEGIN IMMEDIATE` lock, then revalidates:\n  - exact resolved authorized database path;",
    "- It acquires one `BEGIN IMMEDIATE` lock, then revalidates:\n  - exact rollback-journal mode (`DELETE`) and zero runtime `-wal`/`-shm`/`-journal` sidecars;\n  - exact resolved authorized database path;",
    "closeout WAL repair",
)
text = replace_once(
    text,
    "Five distinct RED gates were observed before implementation:",
    "Six distinct RED gates were observed before implementation:",
    "closeout RED count",
)
text = replace_once(
    text,
    "5. a database connection failure left a newly created supervision lock.\n\nFocused Checkpoint 2 tests:",
    "5. a database connection failure left a newly created supervision lock;\n6. WAL-backed logical drift was accepted while the authorized main-file SHA-256 remained unchanged.\n\nFocused Checkpoint 2 tests:",
    "closeout WAL RED item",
)
text = replace_once(
    text,
    "- authorization-to-first-write database continuity;",
    "- authorization-to-first-write database continuity, including WAL/journal runtime state;",
    "closeout improvement",
)
text = replace_once(
    text,
    "- SHA-256 revalidation under the first write lock adds bounded local file-read time before four small initialization inserts; it performs no provider or network work.",
    "- SHA-256 plus journal-mode/sidecar revalidation under the first write lock adds bounded local checks before four small initialization inserts; it performs no provider or network work.\n- Ordinary operational initialization now requires SQLite `DELETE` journal mode; WAL, MEMORY, OFF, TRUNCATE, and PERSIST modes fail closed rather than weakening raw-file authorization identity.",
    "closeout WAL risk",
)
closeout.write_text(text, encoding="utf-8")

print("Checkpoint 2 WAL gate and repair applied")
