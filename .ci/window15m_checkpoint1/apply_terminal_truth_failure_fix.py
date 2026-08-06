from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


module = Path("src/printer_v1/operator_cli/window_15m_child_terminal.py")
text = module.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''        "terminal_report_path",\n        "terminal_report_sha256",\n''',
    '''        "terminal_report_path",\n        "terminal_report_sha256",\n        "terminal_truth_status",\n        "secondary_terminal_truth_error",\n''',
    "child terminal truth fields",
)
text = replace_once(
    text,
    '''COUNT_FIELDS = ("source_calls", "scheduler_runtime_calls", "database_writes")\n''',
    '''COUNT_FIELDS = ("source_calls", "scheduler_runtime_calls", "database_writes")\nTERMINAL_TRUTH_STATUSES = frozenset(\n    {\n        "NOT_APPLICABLE_SUCCESS",\n        "RECONSTRUCTED",\n        "PROVEN_ZERO_NO_CAMPAIGN_ACTION_IDENTITY",\n        "RECONSTRUCTION_FAILED",\n        "UNAVAILABLE",\n    }\n)\n''',
    "child terminal truth statuses",
)
text = replace_once(
    text,
    '''    payload = {\n        "schema_version": CHILD_TERMINAL_SCHEMA_VERSION,\n''',
    '''    terminal_truth_status = _safe_identifier(\n        _find_key(source, "terminal_truth_status")\n    )\n    if terminal_truth_status is None:\n        if success:\n            terminal_truth_status = "NOT_APPLICABLE_SUCCESS"\n        elif isinstance(source.get("action_local_terminal_truth"), Mapping):\n            terminal_truth_status = "RECONSTRUCTED"\n        elif (\n            _find_key(source, "database_mutation_status")\n            == "PROVEN_ZERO_NO_CAMPAIGN_ACTION_IDENTITY"\n        ):\n            terminal_truth_status = "PROVEN_ZERO_NO_CAMPAIGN_ACTION_IDENTITY"\n        else:\n            terminal_truth_status = "UNAVAILABLE"\n    secondary_terminal_truth_error = _safe_text(\n        _find_key(source, "secondary_terminal_truth_error")\n    )\n    payload = {\n        "schema_version": CHILD_TERMINAL_SCHEMA_VERSION,\n''',
    "child terminal truth derivation",
)
text = replace_once(
    text,
    '''        "terminal_report_path": report_path,\n        "terminal_report_sha256": report_sha,\n''',
    '''        "terminal_report_path": report_path,\n        "terminal_report_sha256": report_sha,\n        "terminal_truth_status": terminal_truth_status,\n        "secondary_terminal_truth_error": secondary_terminal_truth_error,\n''',
    "child terminal truth payload",
)
text = replace_once(
    text,
    '''    if report_sha is not None and report_path is None:\n        raise ChildTerminalError("child terminal report SHA-256 lacks a report path")\n    return dict(payload)\n''',
    '''    if report_sha is not None and report_path is None:\n        raise ChildTerminalError("child terminal report SHA-256 lacks a report path")\n    truth_status = payload.get("terminal_truth_status")\n    if truth_status not in TERMINAL_TRUTH_STATUSES:\n        raise ChildTerminalError("child terminal truth status is invalid")\n    secondary_truth_error = payload.get("secondary_terminal_truth_error")\n    _validate_safe_terminal_text(\n        secondary_truth_error,\n        field="secondary_terminal_truth_error",\n        required=truth_status == "RECONSTRUCTION_FAILED",\n    )\n    if truth_status != "RECONSTRUCTION_FAILED" and secondary_truth_error is not None:\n        raise ChildTerminalError(\n            "child terminal secondary truth error lacks reconstruction failure"\n        )\n    if payload["success"] and truth_status != "NOT_APPLICABLE_SUCCESS":\n        raise ChildTerminalError("child terminal success truth status is invalid")\n    return dict(payload)\n''',
    "child terminal truth reader validation",
)
text = replace_once(
    text,
    '''    "CHILD_TERMINAL_SCHEMA_VERSION",\n''',
    '''    "CHILD_TERMINAL_SCHEMA_VERSION",\n    "TERMINAL_TRUTH_STATUSES",\n''',
    "child terminal truth statuses export",
)
module.write_text(text, encoding="utf-8")

command = Path("src/printer_v1/operator_cli/operational_memory_factory_command.py")
text = command.read_text(encoding="utf-8")
old = '''        if args.mode in campaign_modes and (\n            action_run_id is not None or action_campaign_id is not None\n        ):\n            mutation_recorder = _ACTION_RUN_CONTEXT.get("mutation_recorder")\n            inserted_ids = None\n            updated_ids = None\n            auth_write_count = None\n            if mutation_recorder is not None:\n                inserted_ids = mutation_recorder.inserted_row_ids()\n                updated_ids = mutation_recorder.updated_row_ids()\n                auth_write_count = mutation_recorder.authoritative_write_count()\n            truth = build_action_local_terminal_truth(\n                AUTHORITATIVE_DB,\n                baseline=baseline,\n                execution_id=(\n                    str(action_execution_id) if action_execution_id else None\n                ),\n                campaign_id=(\n                    str(action_campaign_id) if action_campaign_id else None\n                ),\n                run_id=str(action_run_id) if action_run_id else None,\n                cycle_id=str(action_cycle_id) if action_cycle_id else None,\n                first_terminal_cause=f"{type(exc).__name__}:{exc}",\n                owner_emitted_inserted_row_ids=inserted_ids,\n                owner_emitted_updated_row_ids=updated_ids,\n                authoritative_write_count=auth_write_count,\n            )\n            envelope = merge_action_local_into_exception_envelope(\n                {\n                    "status": "OPERATIONAL_COMMAND_BLOCKED",\n                    "error_type": type(exc).__name__,\n                    "error_message": str(exc),\n                    "mode": args.mode,\n                    "action_run_id": action_run_id,\n                    "scheduler_runtime_calls": 0,\n                    "restart_created": False,\n                    "successor_created": False,\n                },\n                truth,\n            )\n'''
new = '''        if args.mode in campaign_modes and (\n            action_run_id is not None or action_campaign_id is not None\n        ):\n            try:\n                mutation_recorder = _ACTION_RUN_CONTEXT.get("mutation_recorder")\n                inserted_ids = None\n                updated_ids = None\n                auth_write_count = None\n                if mutation_recorder is not None:\n                    inserted_ids = mutation_recorder.inserted_row_ids()\n                    updated_ids = mutation_recorder.updated_row_ids()\n                    auth_write_count = mutation_recorder.authoritative_write_count()\n                truth = build_action_local_terminal_truth(\n                    AUTHORITATIVE_DB,\n                    baseline=baseline,\n                    execution_id=(\n                        str(action_execution_id) if action_execution_id else None\n                    ),\n                    campaign_id=(\n                        str(action_campaign_id) if action_campaign_id else None\n                    ),\n                    run_id=str(action_run_id) if action_run_id else None,\n                    cycle_id=str(action_cycle_id) if action_cycle_id else None,\n                    first_terminal_cause=f"{type(exc).__name__}:{exc}",\n                    owner_emitted_inserted_row_ids=inserted_ids,\n                    owner_emitted_updated_row_ids=updated_ids,\n                    authoritative_write_count=auth_write_count,\n                )\n                envelope = merge_action_local_into_exception_envelope(\n                    {\n                        "status": "OPERATIONAL_COMMAND_BLOCKED",\n                        "error_type": type(exc).__name__,\n                        "error_message": str(exc),\n                        "mode": args.mode,\n                        "action_run_id": action_run_id,\n                        "scheduler_runtime_calls": 0,\n                        "restart_created": False,\n                        "successor_created": False,\n                        "terminal_truth_status": "RECONSTRUCTED",\n                        "secondary_terminal_truth_error": None,\n                    },\n                    truth,\n                )\n            except Exception as truth_exc:\n                # Preserve the original campaign failure as the controlling cause.\n                # A secondary terminal-truth reconstruction failure must not erase\n                # it or prevent the child-owned terminal artifact from being written.\n                envelope = {\n                    "status": "OPERATIONAL_COMMAND_BLOCKED",\n                    "error_type": type(exc).__name__,\n                    "error_message": str(exc),\n                    "mode": args.mode,\n                    "execution_id": action_execution_id,\n                    "campaign_id": action_campaign_id,\n                    "action_run_id": action_run_id,\n                    "cycle_id": action_cycle_id,\n                    "campaign_source_calls": None,\n                    "source_calls": None,\n                    "scheduler_runtime_calls": 0,\n                    "database_writes": None,\n                    "database_mutation_known": False,\n                    "database_mutation_status": (\n                        "UNKNOWN_TERMINAL_TRUTH_RECONSTRUCTION_FAILED"\n                    ),\n                    "restart_created": False,\n                    "successor_created": False,\n                    "terminal_truth_status": "RECONSTRUCTION_FAILED",\n                    "secondary_terminal_truth_error": (\n                        f"{type(truth_exc).__name__}:{truth_exc}"\n                    ),\n                }\n'''
text = replace_once(text, old, new, "terminal truth reconstruction fallback")
text = replace_once(
    text,
    '''                "restart_created": False,\n                "successor_created": False,\n            }\n        else:\n''',
    '''                "restart_created": False,\n                "successor_created": False,\n                "terminal_truth_status": (\n                    "PROVEN_ZERO_NO_CAMPAIGN_ACTION_IDENTITY"\n                ),\n                "secondary_terminal_truth_error": None,\n            }\n        else:\n''',
    "no campaign identity truth status",
)
text = replace_once(
    text,
    '''                "restart_created": False,\n                "successor_created": False,\n            }\n        if args.mode == "run" and child_terminal_binding is not None:\n''',
    '''                "restart_created": False,\n                "successor_created": False,\n                "terminal_truth_status": (\n                    "PROVEN_ZERO_NO_CAMPAIGN_ACTION_IDENTITY"\n                ),\n                "secondary_terminal_truth_error": None,\n            }\n        if args.mode == "run" and child_terminal_binding is not None:\n''',
    "auxiliary failure truth status",
)
command.write_text(text, encoding="utf-8")

wrapper_test = Path("tests/test_v2_9_8b_window_15m_one_shot_wrapper.py")
text = wrapper_test.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''                "terminal_report_path": None,\n                "terminal_report_sha256": None,\n''',
    '''                "terminal_report_path": None,\n                "terminal_report_sha256": None,\n                "terminal_truth_status": "RECONSTRUCTED",\n                "secondary_terminal_truth_error": None,\n''',
    "manual wrapper terminal truth fields",
)
wrapper_test.write_text(text, encoding="utf-8")
print("terminal-truth reconstruction failure preservation repaired")
