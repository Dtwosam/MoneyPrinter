from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"expected close-cutoff anchor missing in {path}: {old[:140]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


ADAPTER = "src/printer_v1/operator_cli/campaign_authority_adapters.py"
STANDARD = "src/printer_v1/operator_cli/operational_standard_4h.py"

# Existing callers retain the campaign checkpoint cutoff. Long-window callers may
# instead ask the adapter to evaluate the exact evidence retained by the closed
# physical memory window at that window's own immutable close boundary. The
# override is accepted only when it equals authoritative window_end_at exactly.
replace_once(
    ADAPTER,
    '''    token_slot_id: str,\n    window_id: str,\n) -> dict[str, Any]:\n    """Load the exact safety composite retained by one memory-window context.\n''',
    '''    token_slot_id: str,\n    window_id: str,\n    memory_window_close_cutoff: str | None = None,\n) -> dict[str, Any]:\n    """Load the exact safety composite retained by one memory-window context.\n''',
)
replace_once(
    ADAPTER,
    '''        cutoff = _time(graph["checkpoint_cutoff"])\n        captured = _time(composite["evidence_captured_at"])\n''',
    '''        if memory_window_close_cutoff is not None:\n            authoritative_window_end = str(window.get("window_end_at") or "")\n            if (\n                not authoritative_window_end\n                or str(memory_window_close_cutoff) != authoritative_window_end\n            ):\n                raise CampaignAuthorityAdapterError(\n                    "memory-window safety cutoff must equal authoritative window_end_at"\n                )\n            cutoff_value = authoritative_window_end\n        else:\n            cutoff_value = str(graph["checkpoint_cutoff"])\n        cutoff = _time(cutoff_value)\n        captured = _time(composite["evidence_captured_at"])\n''',
)
replace_once(
    ADAPTER,
    '''            "reasons": list(dict.fromkeys(reasons)),\n            "read_only": True,\n        }\n\n\ndef build_4a_authority_facts(\n''',
    '''            "reasons": list(dict.fromkeys(reasons)),\n            "evidence_cutoff": cutoff_value,\n            "evidence_cutoff_source": (\n                "MEMORY_WINDOW_END"\n                if memory_window_close_cutoff is not None\n                else "CAMPAIGN_CHECKPOINT"\n            ),\n            "read_only": True,\n        }\n\n\ndef build_4a_authority_facts(\n''',
)

# Slice C supplies only the exact physical 1h window end to that adapter.
replace_once(
    STANDARD,
    '''        """SELECT id,token_id,pair_id,window_kind,window_status,\n                  data_quality_label,do_not_train,supporting_context_json\n           FROM printer_memory_windows WHERE id=?""",\n''',
    '''        """SELECT id,token_id,pair_id,window_kind,window_status,window_end_at,\n                  data_quality_label,do_not_train,supporting_context_json\n           FROM printer_memory_windows WHERE id=?""",\n''',
)
replace_once(
    STANDARD,
    '''            token_slot_id=slot_id,\n            window_id=window_id,\n        )\n        facts = build_4a_authority_facts(promotion, safety)\n''',
    '''            token_slot_id=slot_id,\n            window_id=window_id,\n            memory_window_close_cutoff=str(physical["window_end_at"]),\n        )\n        facts = build_4a_authority_facts(promotion, safety)\n''',
)
