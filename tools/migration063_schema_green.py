from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one match in {path}: {count}\n{old}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


COHERENCE = "src/printer_v1/operator_cli/schema_admission_coherence.py"
SCHEMA = "src/printer_v1/operator_cli/proof_db_schema_readiness.py"
POST = "tests/test_v2_9_8b_post_lane4_schema_gate_coherence.py"
PRE = "tests/test_v2_9_8b_pre_lifecycle_schema_gate_coherence.py"
HANDOFF = "CURRENT_HANDOFF.md"

replace_once(
    COHERENCE,
    "    MIGRATION_062_REQUIRED_INDEXES,\n    MIGRATION_062_REQUIRED_TABLES,\n    MIGRATION_062_REQUIRED_TRIGGERS,\n",
    "    MIGRATION_062_REQUIRED_INDEXES,\n    MIGRATION_062_REQUIRED_TABLES,\n    MIGRATION_062_REQUIRED_TRIGGERS,\n    MIGRATION_063_REQUIRED_INDEXES,\n    MIGRATION_063_REQUIRED_TABLES,\n    MIGRATION_063_REQUIRED_TRIGGERS,\n",
)
replace_once(
    COHERENCE,
    'REQUIRED_MIGRATION_COUNT = 62\nREQUIRED_MIGRATION_HEAD = (\n    "062_pre_admission_attempt_evidence.sql"\n)\n',
    'REQUIRED_MIGRATION_COUNT = 63\nREQUIRED_MIGRATION_HEAD = (\n    "063_four_token_zero_attempt_terminal_provenance.sql"\n)\n',
)
replace_once(
    COHERENCE,
    "    migration_061_objects_ready: bool\n    migration_062_objects_ready: bool\n    partial_application: bool\n",
    "    migration_061_objects_ready: bool\n    migration_062_objects_ready: bool\n    migration_063_objects_ready: bool\n    partial_application: bool\n",
)
replace_once(
    COHERENCE,
    '            "migration_061_objects_ready": self.migration_061_objects_ready,\n            "migration_062_objects_ready": self.migration_062_objects_ready,\n            "partial_application": self.partial_application,\n',
    '            "migration_061_objects_ready": self.migration_061_objects_ready,\n            "migration_062_objects_ready": self.migration_062_objects_ready,\n            "migration_063_objects_ready": self.migration_063_objects_ready,\n            "partial_application": self.partial_application,\n',
)
replace_once(
    COHERENCE,
    "    migration_060_ready = False\n    migration_061_ready = False\n    migration_062_ready = False\n",
    "    migration_060_ready = False\n    migration_061_ready = False\n    migration_062_ready = False\n    migration_063_ready = False\n",
)
replace_once(
    COHERENCE,
    "            migration_062_ready = not _issues_name_hit(object_issues, names_062)\n            if object_issues:\n",
    "            migration_062_ready = not _issues_name_hit(object_issues, names_062)\n            names_063 = (\n                set(MIGRATION_063_REQUIRED_TABLES)\n                | set(MIGRATION_063_REQUIRED_TRIGGERS)\n                | set(MIGRATION_063_REQUIRED_INDEXES)\n            )\n            migration_063_ready = not _issues_name_hit(object_issues, names_063)\n            if object_issues:\n",
)
replace_once(
    COHERENCE,
    "    mixed_objects = len(\n        {migration_060_ready, migration_061_ready, migration_062_ready}\n    ) > 1\n    objects_complete = (\n        migration_060_ready and migration_061_ready and migration_062_ready\n    )\n",
    "    mixed_objects = len(\n        {\n            migration_060_ready, migration_061_ready, migration_062_ready,\n            migration_063_ready,\n        }\n    ) > 1\n    objects_complete = (\n        migration_060_ready and migration_061_ready\n        and migration_062_ready and migration_063_ready\n    )\n",
)
replace_once(
    COHERENCE,
    "        migration_061_objects_ready=migration_061_ready,\n        migration_062_objects_ready=migration_062_ready,\n        partial_application=partial_application,\n",
    "        migration_061_objects_ready=migration_061_ready,\n        migration_062_objects_ready=migration_062_ready,\n        migration_063_objects_ready=migration_063_ready,\n        partial_application=partial_application,\n",
)

replace_once(
    SCHEMA,
    '    "printer_pre_admission_attempt_evidence": {\n        "attempt_id", "event_key", "opportunity_ordinal", "claim_ordinal",\n        "evidence_kind", "mint_identity", "pair_identity",\n        "categorical_reason", "source_request_id", "source_response_id",\n        "source_failure_id", "payload_json", "payload_hash", "observed_at",\n        "created_at",\n    },\n}',
    '    "printer_pre_admission_attempt_evidence": {\n        "attempt_id", "event_key", "opportunity_ordinal", "claim_ordinal",\n        "evidence_kind", "mint_identity", "pair_identity",\n        "categorical_reason", "source_request_id", "source_response_id",\n        "source_failure_id", "payload_json", "payload_hash", "observed_at",\n        "created_at",\n    },\n    "printer_four_token_zero_attempt_terminal_provenance": {\n        "campaign_id", "campaign_run_id", "authoritative_factory_run_id",\n        "cycle_id", "cycle_ordinal", "proposed_cycle_ordinal",\n        "terminal_phase", "first_terminal_cause", "recorded_at",\n    },\n}',
)
replace_once(
    SCHEMA,
    '    "printer_pre_admission_attempt_evidence": {\n        "attempt_id", "event_key", "opportunity_ordinal", "claim_ordinal",\n        "evidence_kind", "payload_json", "payload_hash", "observed_at",\n        "created_at",\n    },\n}',
    '    "printer_pre_admission_attempt_evidence": {\n        "attempt_id", "event_key", "opportunity_ordinal", "claim_ordinal",\n        "evidence_kind", "payload_json", "payload_hash", "observed_at",\n        "created_at",\n    },\n    "printer_four_token_zero_attempt_terminal_provenance": {\n        "campaign_id", "campaign_run_id", "authoritative_factory_run_id",\n        "cycle_id", "cycle_ordinal", "proposed_cycle_ordinal",\n        "terminal_phase", "first_terminal_cause", "recorded_at",\n    },\n}',
)
replace_once(
    SCHEMA,
    '    "printer_pre_admission_attempt_evidence": {\n        ("attempt_id", "event_key"),\n    },\n}',
    '    "printer_pre_admission_attempt_evidence": {\n        ("attempt_id", "event_key"),\n    },\n    "printer_four_token_zero_attempt_terminal_provenance": {\n        (\n            "campaign_id", "campaign_run_id",\n            "authoritative_factory_run_id", "proposed_cycle_ordinal",\n        ),\n    },\n}',
)
replace_once(
    SCHEMA,
    '    "printer_pre_admission_attempt_evidence_failure_match": (\n        "printer_pre_admission_attempt_evidence"\n    ),\n}',
    '    "printer_pre_admission_attempt_evidence_failure_match": (\n        "printer_pre_admission_attempt_evidence"\n    ),\n    "printer_four_token_zero_attempt_terminal_provenance_exact_shape": (\n        "printer_four_token_zero_attempt_terminal_provenance"\n    ),\n    "printer_four_token_zero_attempt_terminal_provenance_immutable_update": (\n        "printer_four_token_zero_attempt_terminal_provenance"\n    ),\n    "printer_four_token_zero_attempt_terminal_provenance_immutable_delete": (\n        "printer_four_token_zero_attempt_terminal_provenance"\n    ),\n    "printer_pre_admission_attempt_forbids_zero_attempt_terminal_provenance": (\n        "printer_pre_admission_discovery_attempts"\n    ),\n    "printer_pre_lifecycle_provenance_forbids_zero_attempt_terminal_provenance": (\n        "printer_four_token_pre_lifecycle_terminal_provenance"\n    ),\n}',
)
replace_once(
    SCHEMA,
    'MIGRATION_062_REQUIRED_INDEXES = frozenset({\n    "idx_pre_admission_attempt_evidence_reduce",\n})\n\nREQUIRED_STEP_FOREIGN_KEYS',
    'MIGRATION_062_REQUIRED_INDEXES = frozenset({\n    "idx_pre_admission_attempt_evidence_reduce",\n})\nMIGRATION_063_REQUIRED_TABLES = frozenset({\n    "printer_four_token_zero_attempt_terminal_provenance",\n})\nMIGRATION_063_REQUIRED_TRIGGERS = frozenset({\n    "printer_four_token_zero_attempt_terminal_provenance_exact_shape",\n    "printer_four_token_zero_attempt_terminal_provenance_immutable_update",\n    "printer_four_token_zero_attempt_terminal_provenance_immutable_delete",\n    "printer_pre_admission_attempt_forbids_zero_attempt_terminal_provenance",\n    "printer_pre_lifecycle_provenance_forbids_zero_attempt_terminal_provenance",\n})\nMIGRATION_063_REQUIRED_INDEXES = frozenset()\n\nREQUIRED_STEP_FOREIGN_KEYS',
)

replace_once(
    POST,
    'MIGRATION_062 = "062_pre_admission_attempt_evidence.sql"\nMIGRATION_060',
    'MIGRATION_062 = "062_pre_admission_attempt_evidence.sql"\nMIGRATION_063 = "063_four_token_zero_attempt_terminal_provenance.sql"\nMIGRATION_060',
)
replace_once(POST, "assert coherence.REQUIRED_MIGRATION_COUNT == 62", "assert coherence.REQUIRED_MIGRATION_COUNT == 63")
replace_once(POST, "assert coherence.REQUIRED_MIGRATION_HEAD == MIGRATION_062", "assert coherence.REQUIRED_MIGRATION_HEAD == MIGRATION_063")
replace_once(POST, 'assert found["REQUIRED_MIGRATION_COUNT"].value == 62', 'assert found["REQUIRED_MIGRATION_COUNT"].value == 63')
replace_once(POST, 'extra = catalog / "063_synthetic_coherence_probe.sql"', 'extra = catalog / "064_synthetic_coherence_probe.sql"')
replace_once(POST, "assert coherence.REQUIRED_MIGRATION_COUNT == 62", "assert coherence.REQUIRED_MIGRATION_COUNT == 63")
replace_once(POST, "assert result.applied_count == 62", "assert result.applied_count == 63")
replace_once(POST, "assert result.applied_head == MIGRATION_062", "assert result.applied_head == MIGRATION_063")
replace_once(
    POST,
    "        migration_061_objects_ready=True,\n        migration_062_objects_ready=True,\n        partial_application=False,\n",
    "        migration_061_objects_ready=True,\n        migration_062_objects_ready=True,\n        migration_063_objects_ready=True,\n        partial_application=False,\n",
)

replace_once(
    PRE,
    'MIGRATION_062_NAME = "062_pre_admission_attempt_evidence.sql"\nMIGRATION_059_NAME',
    'MIGRATION_062_NAME = "062_pre_admission_attempt_evidence.sql"\nMIGRATION_063_NAME = "063_four_token_zero_attempt_terminal_provenance.sql"\nMIGRATION_059_NAME',
)
replace_once(PRE, "def test_zero_state_gate_reexports_helper_pin_62()", "def test_zero_state_gate_reexports_helper_pin_63()")
replace_once(PRE, "assert gate.REQUIRED_MIGRATION_COUNT == 62", "assert gate.REQUIRED_MIGRATION_COUNT == 63")
replace_once(PRE, "assert gate.REQUIRED_MIGRATION_HEAD == MIGRATION_062_NAME", "assert gate.REQUIRED_MIGRATION_HEAD == MIGRATION_063_NAME")
replace_once(PRE, 'assert found["REQUIRED_MIGRATION_COUNT"].value == 62', 'assert found["REQUIRED_MIGRATION_COUNT"].value == 63')
replace_once(PRE, 'assert found["REQUIRED_MIGRATION_HEAD"].value == MIGRATION_062_NAME', 'assert found["REQUIRED_MIGRATION_HEAD"].value == MIGRATION_063_NAME')

new_test = Path("tests/test_v2_9_8b_migration063_schema_contract.py")
new_test.write_text('''"""Migration 063 reviewed schema-admission contract (disposable DBs only)."""\n\nfrom __future__ import annotations\n\nimport sqlite3\nfrom pathlib import Path\n\nfrom printer_v1.db import migrate as migration_runner\nfrom printer_v1.operator_cli import proof_db_schema_readiness as schema\nfrom printer_v1.operator_cli import schema_admission_coherence as coherence\n\nMIGRATION_063 = "063_four_token_zero_attempt_terminal_provenance.sql"\nTABLE = "printer_four_token_zero_attempt_terminal_provenance"\nTRIGGERS = {\n    "printer_four_token_zero_attempt_terminal_provenance_exact_shape",\n    "printer_four_token_zero_attempt_terminal_provenance_immutable_update",\n    "printer_four_token_zero_attempt_terminal_provenance_immutable_delete",\n    "printer_pre_admission_attempt_forbids_zero_attempt_terminal_provenance",\n    "printer_pre_lifecycle_provenance_forbids_zero_attempt_terminal_provenance",\n}\n\n\ndef _full(tmp_path: Path) -> Path:\n    db = tmp_path / "full63.sqlite3"\n    migration_runner.apply_migrations(db)\n    return db\n\n\ndef _through_62(db: Path) -> None:\n    connection = sqlite3.connect(db)\n    try:\n        connection.execute("PRAGMA foreign_keys=ON")\n        connection.execute(\n            "CREATE TABLE IF NOT EXISTS printer_schema_migrations ("\n            "version TEXT PRIMARY KEY, "\n            "applied_at TEXT NOT NULL DEFAULT (datetime('now')))"\n        )\n        for migration in sorted(migration_runner.MIGRATIONS_DIR.glob("*.sql")):\n            if int(migration.name[:3]) > 62:\n                continue\n            connection.executescript(migration.read_text(encoding="utf-8"))\n            connection.execute(\n                "INSERT INTO printer_schema_migrations(version) VALUES (?)",\n                (migration.name,),\n            )\n        connection.commit()\n    finally:\n        connection.close()\n\n\ndef test_reviewed_pin_matches_canonical_63_head() -> None:\n    names = list(migration_runner.canonical_migration_names())\n    assert len(names) == 63\n    assert names[-1] == MIGRATION_063\n    assert coherence.REQUIRED_MIGRATION_COUNT == 63\n    assert coherence.REQUIRED_MIGRATION_HEAD == MIGRATION_063\n\n\ndef test_063_objects_are_registered_in_runtime_schema_contract() -> None:\n    assert schema.MIGRATION_063_REQUIRED_TABLES == frozenset({TABLE})\n    assert schema.MIGRATION_063_REQUIRED_TRIGGERS == frozenset(TRIGGERS)\n    assert schema.MIGRATION_063_REQUIRED_INDEXES == frozenset()\n    assert set(schema.REQUIRED_TABLE_COLUMNS[TABLE]) == {\n        "campaign_id", "campaign_run_id", "authoritative_factory_run_id",\n        "cycle_id", "cycle_ordinal", "proposed_cycle_ordinal",\n        "terminal_phase", "first_terminal_cause", "recorded_at",\n    }\n\n\ndef test_fully_migrated_63_db_is_schema_ready(tmp_path: Path) -> None:\n    db = _full(tmp_path)\n    result = coherence.evaluate_schema_admission_coherence(\n        db_path=db, expected_target=db\n    )\n    assert result.admission_schema_ready is True, result.summary()\n    assert result.migration_063_objects_ready is True\n    assert result.blocker_codes == ()\n\n\ndef test_62_prefix_is_fail_closed_against_63_contract(tmp_path: Path) -> None:\n    db = tmp_path / "through62.sqlite3"\n    _through_62(db)\n    result = coherence.evaluate_schema_admission_coherence(\n        db_path=db, expected_target=db\n    )\n    assert result.admission_schema_ready is False\n    assert result.applied_count == 62\n    assert "migration_count_mismatch" in result.blocker_codes\n    assert "migration_head_mismatch" in result.blocker_codes\n    assert result.migration_063_objects_ready is False\n\n\ndef test_missing_063_table_is_fail_closed(tmp_path: Path) -> None:\n    db = _full(tmp_path)\n    connection = sqlite3.connect(db)\n    try:\n        connection.execute("PRAGMA foreign_keys=OFF")\n        connection.execute(f"DROP TABLE {TABLE}")\n        connection.commit()\n    finally:\n        connection.close()\n    result = coherence.evaluate_schema_admission_coherence(\n        db_path=db, expected_target=db\n    )\n    assert result.admission_schema_ready is False\n    assert result.migration_063_objects_ready is False\n    assert "required_schema_object_missing" in result.blocker_codes\n\n\ndef test_missing_063_trigger_is_fail_closed(tmp_path: Path) -> None:\n    db = _full(tmp_path)\n    trigger = "printer_four_token_zero_attempt_terminal_provenance_exact_shape"\n    connection = sqlite3.connect(db)\n    try:\n        connection.execute(f"DROP TRIGGER {trigger}")\n        connection.commit()\n    finally:\n        connection.close()\n    result = coherence.evaluate_schema_admission_coherence(\n        db_path=db, expected_target=db\n    )\n    assert result.admission_schema_ready is False\n    assert result.migration_063_objects_ready is False\n    assert "required_schema_object_missing" in result.blocker_codes\n''', encoding="utf-8")

replace_once(
    HANDOFF,
    "## Verification\n",
    "A post-repair schema-coherence defect was then proven before any authoritative DB mutation: migration 063 was canonical, but the reviewed schema-admission pin and required-object registry still stopped at 62/062. A fully migrated disposable 63/63 DB therefore failed closed with `schema_expectation_mismatch`. The repair advances only the reviewed schema contract to 63/063 and adds migration-063 table/trigger readiness; migration evidence/provenance remains pinned to 062 until a separately authorized authoritative 063 application is actually completed and evidenced.\n\n## Verification\n",
)
replace_once(
    HANDOFF,
    "Focused repair-family verification must pass with migration 063, the new regression, existing pre-lifecycle provenance tests, terminal integration, adapter, and wake-ordering coverage before any promotion.",
    "Focused repair-family verification passed for the planned-lifecycle repair. The migration-063 schema-coherence RED then proved the stale 62/062 pin on disposable 63/63 state; focused GREEN must prove the explicit 63/063 pin, required migration-063 objects, the zero-state gate, and proof-DB schema readiness before promotion.",
)
