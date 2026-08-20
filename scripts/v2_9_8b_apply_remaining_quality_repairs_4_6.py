from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text()
    if old not in text:
        raise SystemExit(f"patch anchor missing: {path}: {old[:80]!r}")
    if text.count(old) != 1:
        raise SystemExit(f"patch anchor ambiguous: {path}: count={text.count(old)}")
    target.write_text(text.replace(old, new, 1))


quality_reporting = '''"""Read-only quality and memory-authority summaries for Printer V1 reports.

These helpers expose existing evidence. They do not promote memory, unlock
retrieval, change decisions, or infer missing facts.
"""
from __future__ import annotations

import json
from typing import Any, Mapping, Sequence


MEMORY_AUTHORITY_RULE = (
    "PARENT_WINDOW_PROVENANCE_ONLY;"
    "CLEAN_EPISODE_AND_FINGERPRINT_AUTHORITATIVE_WHEN_PROMOTED"
)


def _window_id(window: Mapping[str, Any]) -> int | None:
    try:
        value = window.get("id")
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def build_window_blocker_summary(
    windows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Expose exact persisted remaining blockers for attached memory windows."""
    blocking_reasons: list[str] = []
    per_window: list[dict[str, Any]] = []
    for window in windows:
        raw = window.get("supporting_context_json")
        context_status = "ABSENT"
        context: Mapping[str, Any] = {}
        if isinstance(raw, Mapping):
            context = raw
            context_status = "PARSED"
        elif isinstance(raw, str) and raw.strip():
            try:
                parsed = json.loads(raw)
            except (TypeError, ValueError, json.JSONDecodeError):
                context_status = "MALFORMED"
            else:
                if isinstance(parsed, Mapping):
                    context = parsed
                    context_status = "PARSED"
                else:
                    context_status = "MALFORMED"
        raw_blockers = context.get("remaining_blockers") if context_status == "PARSED" else None
        blockers = (
            [str(item) for item in raw_blockers if str(item).strip()]
            if isinstance(raw_blockers, (list, tuple))
            else []
        )
        for blocker in blockers:
            if blocker not in blocking_reasons:
                blocking_reasons.append(blocker)
        per_window.append(
            {
                "window_id": _window_id(window),
                "window_kind": window.get("window_kind"),
                "memory_status": window.get("memory_status"),
                "memory_quality_label": window.get("memory_quality_label"),
                "data_quality_label": window.get("data_quality_label"),
                "do_not_train": int(window.get("do_not_train") or 0),
                "supporting_context_status": context_status,
                "remaining_blockers": blockers,
            }
        )
    return {
        "has_blockers": bool(blocking_reasons),
        "blocking_reasons": blocking_reasons,
        "per_window": per_window,
    }


def build_memory_authority_summary(
    windows: Sequence[Mapping[str, Any]],
    promotions_by_window_id: Mapping[int, Mapping[str, Any]],
) -> dict[str, Any]:
    """Describe parent-window provenance versus authoritative clean artifacts.

    The parent memory window intentionally remains its persisted status (often
    PARTIAL_MEMORY after a clean E2Q candidate). A clean E2Z episode plus its
    fingerprint is the authoritative clean object. Retrieval remains locked.
    """
    per_window: list[dict[str, Any]] = []
    clean_count = 0
    for window in windows:
        window_id = _window_id(window)
        promotion = (
            promotions_by_window_id.get(window_id)
            if window_id is not None
            else None
        )
        episode_id = promotion.get("id") if promotion else None
        fingerprint_id = promotion.get("fingerprint_id") if promotion else None
        complete_clean = bool(
            promotion
            and episode_id is not None
            and fingerprint_id is not None
            and promotion.get("memory_status") == "CLEAN_MEMORY"
            and promotion.get("memory_quality_label") == "CLEAN_MEMORY"
            and promotion.get("data_quality_label") == "CLEAN_DATA"
            and int(promotion.get("do_not_train") or 0) == 0
        )
        if complete_clean:
            clean_count += 1
        per_window.append(
            {
                "parent_window_id": window_id,
                "window_kind": window.get("window_kind"),
                "parent_memory_status": window.get("memory_status"),
                "parent_memory_quality_label": window.get("memory_quality_label"),
                "parent_status_is_authoritative_clean_object": False,
                "authoritative_clean_artifact": (
                    "EPISODE_AND_FINGERPRINT" if complete_clean else None
                ),
                "episode_id": int(episode_id) if complete_clean else None,
                "fingerprint_id": int(fingerprint_id) if complete_clean else None,
            }
        )
    return {
        "authority_rule": MEMORY_AUTHORITY_RULE,
        "retrieval_status": "LOCKED",
        "retrieval_or_decision_use_enabled": False,
        "authoritative_clean_artifact_count": clean_count,
        "per_window": per_window,
    }
'''
Path("src/printer_v1/operator_cli/quality_reporting.py").write_text(quality_reporting)

# Repair 4: reuse the already-governed exact-pool Gecko trade payload for
# aggregate 15m wallet/flow context without persisting raw addresses.
gecko = "src/printer_v1/sources/geckoterminal_15m.py"
marker = "# ---------------------------------------------------------------------------\n# High-level enrichment functions\n# ---------------------------------------------------------------------------\n"
helper = '''# ---------------------------------------------------------------------------
# Observed exact-pool wallet / split-flow aggregation
# ---------------------------------------------------------------------------

def derive_observed_15m_flow_from_trades(
    trades: list[Any],
    *,
    window_start_unix: float,
    window_end_unix: float,
    completeness: str,
) -> dict[str, Any]:
    """Aggregate only what one complete exact-pool trade window proves.

    ``tx_from_address`` is an observed transaction-from address, not beneficial
    ownership and not historical first-seen/new-wallet evidence. Raw addresses
    are never returned or persisted by this helper.
    """
    empty = {
        "unique_wallets_15m": None,
        "buys_15m": None,
        "sells_15m": None,
        "buy_volume_15m": None,
        "sell_volume_15m": None,
        "wallet_identity_semantics_15m": (
            "OBSERVED_TX_FROM_ADDRESS_NOT_BENEFICIAL_OWNER"
        ),
        "wallet_flow_provenance_15m": {
            "trade_history_completeness": completeness,
            "raw_addresses_persisted": False,
            "new_wallet_history_claimed": False,
            "beneficial_owner_claimed": False,
        },
    }
    if completeness != TRADE_HISTORY_COMPLETE:
        return empty

    observed_addresses: set[str] = set()
    address_coverage_complete = True
    recognized_kind_complete = True
    volume_coverage_complete = True
    buys = 0
    sells = 0
    buy_volume = 0.0
    sell_volume = 0.0
    in_window = 0

    for trade in trades:
        if not isinstance(trade, Mapping):
            continue
        attrs = trade.get("attributes")
        if not isinstance(attrs, Mapping):
            attrs = trade
        ts = _parse_trade_timestamp(attrs.get("block_timestamp"))
        if ts is None or not (window_start_unix <= ts < window_end_unix):
            continue
        in_window += 1
        raw_address = attrs.get("tx_from_address")
        if isinstance(raw_address, str) and raw_address.strip():
            observed_addresses.add(raw_address.strip())
        else:
            address_coverage_complete = False

        kind = str(attrs.get("kind") or "").strip().lower()
        if kind not in {"buy", "sell"}:
            recognized_kind_complete = False
            continue
        if kind == "buy":
            buys += 1
        else:
            sells += 1
        raw_volume = attrs.get("volume_in_usd")
        try:
            volume = float(raw_volume)
        except (TypeError, ValueError):
            volume_coverage_complete = False
            continue
        if volume < 0:
            volume_coverage_complete = False
            continue
        if kind == "buy":
            buy_volume += volume
        else:
            sell_volume += volume

    result = dict(empty)
    result["unique_wallets_15m"] = (
        len(observed_addresses)
        if in_window > 0 and address_coverage_complete
        else None
    )
    if recognized_kind_complete:
        result["buys_15m"] = buys
        result["sells_15m"] = sells
    if recognized_kind_complete and volume_coverage_complete:
        result["buy_volume_15m"] = buy_volume
        result["sell_volume_15m"] = sell_volume
    result["wallet_flow_provenance_15m"] = {
        **result["wallet_flow_provenance_15m"],
        "trades_in_window": in_window,
        "observed_address_count": (
            len(observed_addresses) if address_coverage_complete else None
        ),
        "address_coverage_complete": address_coverage_complete,
        "buy_sell_kind_coverage_complete": recognized_kind_complete,
        "split_volume_coverage_complete": (
            recognized_kind_complete and volume_coverage_complete
        ),
    }
    return result


'''
replace_once(gecko, marker, helper + marker)
old_return = '''    return {
        "txns_15m": count,
        "txns_15m_source_kind": PROVIDER_TRADES_WINDOW,
        "txns_15m_completeness": completeness,
        "txns_15m_provenance": {
'''
new_return = '''    observed_flow = derive_observed_15m_flow_from_trades(
        raw_trades_data,
        window_start_unix=window_start_unix,
        window_end_unix=window_end_unix,
        completeness=completeness,
    )

    return {
        "txns_15m": count,
        "txns_15m_source_kind": PROVIDER_TRADES_WINDOW,
        "txns_15m_completeness": completeness,
        **observed_flow,
        "txns_15m_provenance": {
'''
replace_once(gecko, old_return, new_return)

# Repair 5: keep optional safety UNKNOWN but expose why it remains UNKNOWN.
composite = "src/printer_v1/safety/composite.py"
composite_anchor = '''SAFETY_FIELDS = (
    "mint_authority_status",
    "freeze_authority_status",
    "metadata_mutability_status",
    "supply_sanity_label",
    "holder_concentration_label",
    "liquidity_lock_or_burn_label",
    "known_risk_flag_label",
    "token_program_label",
)
'''
composite_insert = composite_anchor + '''

_OPTIONAL_SAFETY_UNKNOWN_REASON_MAP = {
    "metadata_mutability_status": "METADATA_MUTABILITY_SOURCE_UNAVAILABLE",
    "liquidity_lock_or_burn_label": "EXACT_PAIR_LIQUIDITY_LOCK_OR_BURN_UNPROVEN",
    "known_risk_flag_label": "PROVIDER_RISK_FLAGS_UNAVAILABLE",
    "holder_concentration_label": "HOLDER_CONDITION_UNAVAILABLE",
    "HOLDER_CONDITION_UNAVAILABLE": "HOLDER_CONDITION_UNAVAILABLE",
    "HOLDER_CONDITION_CONFLICTING": "HOLDER_CONDITION_CONFLICTING",
    "HOLDER_CONDITION_STALE": "HOLDER_CONDITION_STALE",
}


def optional_safety_unknown_reasons(optional_unknowns: list[str]) -> dict[str, str]:
    """Map optional UNKNOWN fields to exact evidence-availability reasons."""
    reasons: dict[str, str] = {}
    for raw in optional_unknowns:
        item = str(raw)
        reason = _OPTIONAL_SAFETY_UNKNOWN_REASON_MAP.get(item)
        if reason is None:
            continue
        key = (
            "holder_concentration_label"
            if item.startswith("HOLDER_CONDITION_")
            else item
        )
        reasons[key] = reason
    return reasons
'''
replace_once(composite, composite_anchor, composite_insert)
old_optional = '''    optional_unknowns = list(dict.fromkeys(optional_unknowns))
    contract_label = (
'''
new_optional = '''    optional_unknowns = list(dict.fromkeys(optional_unknowns))
    optional_unknown_reason_map = optional_safety_unknown_reasons(optional_unknowns)
    contract_label = (
'''
replace_once(composite, old_optional, new_optional)
old_result = '''        "optional_unknowns": optional_unknowns,
        "field_bindings": field_bindings,
'''
new_result = '''        "optional_unknowns": optional_unknowns,
        "optional_unknown_reasons": optional_unknown_reason_map,
        "field_bindings": field_bindings,
'''
replace_once(composite, old_result, new_result)

# Repair 6: expose exact window blockers and the already-existing clean-object
# authority distinction in the terminal report. No memory status is mutated.
factory = "src/printer_v1/operator_cli/one_command_15m_factory.py"
old_vars = '''    windows_by_id = {int(w["id"]): w for w in windows}
    promotions_by_window_id = _authoritative_promotions_for_run(conn, run_id)
    dirty_promotion_count = int(conn.execute(
'''
new_vars = '''    windows_by_id = {int(w["id"]): w for w in windows}
    promotions_by_window_id = _authoritative_promotions_for_run(conn, run_id)
    from printer_v1.operator_cli.quality_reporting import (
        build_memory_authority_summary,
        build_window_blocker_summary,
    )
    window_blocker_summary = build_window_blocker_summary(windows)
    memory_authority = build_memory_authority_summary(
        windows, promotions_by_window_id
    )
    dirty_promotion_count = int(conn.execute(
'''
replace_once(factory, old_vars, new_vars)
old_report = '''        "run_local_yield": run_local_yield,
        "historical_report_note": (
'''
new_report = '''        "run_local_yield": run_local_yield,
        "blocking_reasons": window_blocker_summary["blocking_reasons"],
        "window_blocker_summary": window_blocker_summary,
        "memory_authority": memory_authority,
        "historical_report_note": (
'''
replace_once(factory, old_report, new_report)

print("remaining quality repairs 4-6 patch applied")
