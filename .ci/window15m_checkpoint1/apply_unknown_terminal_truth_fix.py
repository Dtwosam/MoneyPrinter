from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


command = Path("src/printer_v1/operator_cli/operational_memory_factory_command.py")
text = command.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''                    "campaign_source_calls": None,\n                    "source_calls": None,\n                    "scheduler_runtime_calls": 0,\n                    "database_writes": None,\n                    "database_mutation_known": False,\n''',
    '''                    "campaign_source_calls": None,\n                    "source_calls": None,\n                    "scheduler_runtime_calls": None,\n                    "database_writes": None,\n                    "database_identity_after": None,\n                    "lifecycle_started": None,\n                    "cleanup_complete": None,\n                    "lease_released": None,\n                    "active_locked_work": None,\n                    "failure_phase": (\n                        "CAMPAIGN_PHASE_UNKNOWN_TERMINAL_TRUTH_RECONSTRUCTION_FAILED"\n                    ),\n                    "database_mutation_known": False,\n''',
    "unknown reconstruction fallback facts",
)
command.write_text(text, encoding="utf-8")

module = Path("src/printer_v1/operator_cli/window_15m_child_terminal.py")
text = module.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''    active = _bounded_mapping(_find_key(source, "active_locked_work"))\n    db_identity = _database_identity(_find_key(source, "database_identity_after"))\n''',
    '''    active_raw = _find_key(source, "active_locked_work")\n    active = (\n        _bounded_mapping(active_raw)\n        if isinstance(active_raw, Mapping)\n        else None\n    )\n    lifecycle_raw = _find_key(source, "lifecycle_started")\n    factory_run_id = _find_key(source, "factory_run_id")\n    if type(lifecycle_raw) is bool:\n        lifecycle_started = lifecycle_raw\n    elif factory_run_id not in (None, ""):\n        lifecycle_started = True\n    else:\n        lifecycle_started = None\n    db_identity = _database_identity(_find_key(source, "database_identity_after"))\n''',
    "optional active and lifecycle truth derivation",
)
text = replace_once(
    text,
    '''        "marker_consumed": True,\n        "lifecycle_started": bool(_find_key(source, "lifecycle_started")) or bool(\n            _find_key(source, "factory_run_id")\n        ),\n        "cleanup_complete": _find_key(source, "cleanup_complete"),\n''',
    '''        "marker_consumed": True,\n        "lifecycle_started": lifecycle_started,\n        "cleanup_complete": _find_key(source, "cleanup_complete"),\n''',
    "optional lifecycle payload",
)
text = replace_once(
    text,
    '''def _validate_active_work(value: Any) -> None:\n    if not isinstance(value, Mapping) or len(value) > MAX_MAPPING_ITEMS:\n''',
    '''def _validate_active_work(value: Any) -> None:\n    if value is None:\n        return\n    if not isinstance(value, Mapping) or len(value) > MAX_MAPPING_ITEMS:\n''',
    "optional active work validation",
)
text = replace_once(
    text,
    '''    if type(payload.get("lifecycle_started")) is not bool:\n        raise ChildTerminalError("child terminal lifecycle evidence is invalid")\n''',
    '''    lifecycle_started = payload.get("lifecycle_started")\n    if lifecycle_started is not None and type(lifecycle_started) is not bool:\n        raise ChildTerminalError("child terminal lifecycle evidence is invalid")\n''',
    "optional lifecycle reader validation",
)
module.write_text(text, encoding="utf-8")

wrapper = Path("src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py")
text = wrapper.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''            "child_active_locked_work": (\n                {} if child_terminal is None\n                else child_terminal.get("active_locked_work", {})\n            ),\n''',
    '''            "child_active_locked_work": (\n                None if child_terminal is None\n                else child_terminal.get("active_locked_work")\n            ),\n''',
    "wrapper unknown active work projection",
)
wrapper.write_text(text, encoding="utf-8")
print("unknown operational terminal-truth preservation repaired")
