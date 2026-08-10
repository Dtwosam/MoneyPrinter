from __future__ import annotations

from pathlib import Path


ADAPTER = Path("src/printer_v1/operator_cli/campaign_authority_adapters.py")
STANDARD = Path("src/printer_v1/operator_cli/operational_standard_4h.py")


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"expected {label} anchor missing: {old[:160]!r}")
    return text.replace(old, new, 1)


# Modify only load_authoritative_window_safety. Earlier helpers have similar
# signature/cutoff text and must not be touched by this long-window extension.
adapter_text = ADAPTER.read_text(encoding="utf-8")
start = adapter_text.find("def load_authoritative_window_safety(\n")
end = adapter_text.find("\ndef build_4a_authority_facts(\n", start)
if start < 0 or end < 0:
    raise RuntimeError("exact load_authoritative_window_safety function boundary missing")
block = adapter_text[start:end]
block = replace_once(
    block,
    '''    token_slot_id: str,\n    window_id: str,\n) -> dict[str, Any]:\n''',
    '''    token_slot_id: str,\n    window_id: str,\n    memory_window_close_cutoff: str | None = None,\n) -> dict[str, Any]:\n''',
    label="window-safety signature",
)
block = replace_once(
    block,
    '''        cutoff = _time(graph["checkpoint_cutoff"])\n        captured = _time(composite["evidence_captured_at"])\n''',
    '''        if memory_window_close_cutoff is not None:\n            authoritative_window_end = str(window.get("window_end_at") or "")\n            if (\n                not authoritative_window_end\n                or str(memory_window_close_cutoff) != authoritative_window_end\n            ):\n                raise CampaignAuthorityAdapterError(\n                    "memory-window safety cutoff must equal authoritative window_end_at"\n                )\n            cutoff_value = authoritative_window_end\n        else:\n            cutoff_value = str(graph["checkpoint_cutoff"])\n        cutoff = _time(cutoff_value)\n        captured = _time(composite["evidence_captured_at"])\n''',
    label="window-safety cutoff",
)
block = replace_once(
    block,
    '''            "reasons": list(dict.fromkeys(reasons)),\n            "read_only": True,\n        }\n''',
    '''            "reasons": list(dict.fromkeys(reasons)),\n            "evidence_cutoff": cutoff_value,\n            "evidence_cutoff_source": (\n                "MEMORY_WINDOW_END"\n                if memory_window_close_cutoff is not None\n                else "CAMPAIGN_CHECKPOINT"\n            ),\n            "read_only": True,\n        }\n''',
    label="window-safety return",
)
adapter_text = adapter_text[:start] + block + adapter_text[end:]
ADAPTER.write_text(adapter_text, encoding="utf-8")

# Slice C supplies only the exact physical 1h window_end_at to that adapter.
standard_text = STANDARD.read_text(encoding="utf-8")
standard_text = replace_once(
    standard_text,
    '''        """SELECT id,token_id,pair_id,window_kind,window_status,\n                  data_quality_label,do_not_train,supporting_context_json\n           FROM printer_memory_windows WHERE id=?""",\n''',
    '''        """SELECT id,token_id,pair_id,window_kind,window_status,window_end_at,\n                  data_quality_label,do_not_train,supporting_context_json\n           FROM printer_memory_windows WHERE id=?""",\n''',
    label="physical 1h close timestamp",
)
standard_text = replace_once(
    standard_text,
    '''            token_slot_id=slot_id,\n            window_id=window_id,\n        )\n        facts = build_4a_authority_facts(promotion, safety)\n''',
    '''            token_slot_id=slot_id,\n            window_id=window_id,\n            memory_window_close_cutoff=str(physical["window_end_at"]),\n        )\n        facts = build_4a_authority_facts(promotion, safety)\n''',
    label="Slice C exact safety cutoff call",
)
STANDARD.write_text(standard_text, encoding="utf-8")
