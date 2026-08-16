from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


path = Path("src/printer_v1/discovery/eligible_token_supply.py")
text = path.read_text()

helper = '''_TEMPORAL_FRESH_SOURCE_CHANNELS = frozenset({
    "direct_pump_finalized_live_tail",
    "dexscreener_fresh_profiles",
    "geckoterminal_fresh_pool_nomination",
})


def _temporal_terminal_source_failure_facts(
    *,
    provider_failures: int,
    channels_unavailable: Sequence[str],
    acquisition_ledger: Any | None,
    last_stop_reason: str | None,
) -> tuple[int, list[str]]:
    """Return only source-failure facts that may control terminal shortage.

    Historical or source-local failures remain certificate provenance, but they
    cannot become the terminal reason while another fresh source channel stayed
    lawful. A shared refresh-stage failure remains terminal. Otherwise all
    three approved fresh-source channels must have been attempted and unavailable
    in the latest completed refresh before source availability may control.
    """
    unavailable = sorted(set(str(x) for x in channels_unavailable))
    if acquisition_ledger is None:
        return int(provider_failures), unavailable
    if last_stop_reason == "SOURCE_AVAILABILITY_FAILURE_DURING_REFRESH":
        return int(provider_failures), unavailable
    completed = [
        item
        for item in getattr(acquisition_ledger, "outcomes", ())
        if str(item.get("status") or "") == REFRESH_COMPLETED
    ]
    if not completed:
        return int(provider_failures), unavailable
    latest = completed[-1]
    attempted = {str(x) for x in latest.get("channels_attempted") or ()}
    latest_unavailable = {
        str(x) for x in latest.get("channels_unavailable") or ()
    }
    all_fresh_unavailable = (
        _TEMPORAL_FRESH_SOURCE_CHANNELS.issubset(attempted)
        and _TEMPORAL_FRESH_SOURCE_CHANNELS.issubset(latest_unavailable)
    )
    if all_fresh_unavailable:
        return int(provider_failures), unavailable
    return 0, []


'''
if "def _temporal_terminal_source_failure_facts(" not in text:
    text = replace_once(
        text,
        "def _apply_permanent_shortage_precedence(\n",
        helper + "def _apply_permanent_shortage_precedence(\n",
        "shortage helper anchor",
    )

old = '''            depth_before = len(campaign_eligible)
            outcome = temporal_refresh_owner.request_temporal_refresh(
'''
new = '''            depth_before = len(campaign_eligible)
            # Settle the prior completed refresh after its newly reachable
            # registry rows have traversed the canonical front door. This keeps
            # per-round reserve transitions honest without a second admission
            # authority.
            if (
                acquisition_ledger.outcomes
                and acquisition_ledger.outcomes[-1].get("status") == REFRESH_COMPLETED
            ):
                acquisition_ledger.outcomes[-1]["reserve_depth_after"] = depth_before
                if acquisition_ledger.reserve_depth_transitions:
                    acquisition_ledger.reserve_depth_transitions[-1][
                        "reserve_depth_after"
                    ] = depth_before
            outcome = temporal_refresh_owner.request_temporal_refresh(
'''
if new.strip() not in text:
    text = replace_once(text, old, new, "prior refresh depth anchor")

old = '''        # Refresh inventory size after discovery (new confirms).
        inventory_rows = export_graduated_candidates(connection)
'''
new = '''        # Settle the final completed refresh after its canonical front-door
        # traversal, before residual post-loop protocol reconciliation.
        if (
            acquisition_ledger is not None
            and acquisition_ledger.outcomes
            and acquisition_ledger.outcomes[-1].get("status") == REFRESH_COMPLETED
        ):
            final_refresh_depth = len(campaign_eligible)
            acquisition_ledger.outcomes[-1]["reserve_depth_after"] = final_refresh_depth
            if acquisition_ledger.reserve_depth_transitions:
                acquisition_ledger.reserve_depth_transitions[-1][
                    "reserve_depth_after"
                ] = final_refresh_depth

        # Refresh inventory size after discovery (new confirms).
        inventory_rows = export_graduated_candidates(connection)
'''
if new.strip() not in text:
    text = replace_once(text, old, new, "final refresh depth anchor")

old = '''            shortage = classify_shortage(
                provider_failures=provider_failures,
                channels_unavailable=sorted(set(channels_unavailable)),
'''
new = '''            terminal_provider_failures, terminal_channels_unavailable = (
                _temporal_terminal_source_failure_facts(
                    provider_failures=provider_failures,
                    channels_unavailable=channels_unavailable,
                    acquisition_ledger=acquisition_ledger,
                    last_stop_reason=last_stop_reason,
                )
            )
            shortage = classify_shortage(
                provider_failures=terminal_provider_failures,
                channels_unavailable=terminal_channels_unavailable,
'''
if new.strip() not in text:
    text = replace_once(text, old, new, "classify shortage anchor")

old = '''                provider_failures=provider_failures,
                channels_unavailable=sorted(set(channels_unavailable)),
                liquidity_source_unavailable=liquidity_outcome_counts.get(LIQUIDITY_SOURCE_UNAVAILABLE, 0),
'''
new = '''                provider_failures=terminal_provider_failures,
                channels_unavailable=terminal_channels_unavailable,
                liquidity_source_unavailable=liquidity_outcome_counts.get(LIQUIDITY_SOURCE_UNAVAILABLE, 0),
'''
if new.strip() not in text:
    text = replace_once(text, old, new, "precedence source-fact anchor")

path.write_text(text)

test_path = Path("tests/test_v2_9_8b_persistent_multisource_refresh.py")
tests = test_path.read_text()
if "test_partial_refresh_source_failure_is_not_terminal_source_exhaustion" not in tests:
    tests += '''


def test_partial_refresh_source_failure_is_not_terminal_source_exhaustion():
    from types import SimpleNamespace
    from printer_v1.discovery.eligible_token_supply import (
        _temporal_terminal_source_failure_facts,
    )

    ledger = SimpleNamespace(outcomes=[{
        "status": "REFRESH_COMPLETED",
        "channels_attempted": [
            composition.PUMP_FRESH_CHANNEL,
            composition.DEXSCREENER_FRESH_CHANNEL,
            composition.GECKOTERMINAL_NOMINATION_CHANNEL,
        ],
        "channels_unavailable": [composition.GECKOTERMINAL_NOMINATION_CHANNEL],
    }])
    failures, unavailable = _temporal_terminal_source_failure_facts(
        provider_failures=1,
        channels_unavailable=[composition.GECKOTERMINAL_NOMINATION_CHANNEL],
        acquisition_ledger=ledger,
        last_stop_reason="DISCOVERY_OPERATION_BUDGET_EXHAUSTED",
    )
    assert failures == 0
    assert unavailable == []


def test_all_fresh_refresh_sources_unavailable_remains_terminal_source_fact():
    from types import SimpleNamespace
    from printer_v1.discovery.eligible_token_supply import (
        _temporal_terminal_source_failure_facts,
    )

    all_fresh = [
        composition.PUMP_FRESH_CHANNEL,
        composition.DEXSCREENER_FRESH_CHANNEL,
        composition.GECKOTERMINAL_NOMINATION_CHANNEL,
    ]
    ledger = SimpleNamespace(outcomes=[{
        "status": "REFRESH_COMPLETED",
        "channels_attempted": all_fresh,
        "channels_unavailable": all_fresh,
    }])
    failures, unavailable = _temporal_terminal_source_failure_facts(
        provider_failures=3,
        channels_unavailable=all_fresh,
        acquisition_ledger=ledger,
        last_stop_reason="ALL_REACHABLE_CANDIDATES_EVALUATED",
    )
    assert failures == 3
    assert unavailable == sorted(all_fresh)
'''
    test_path.write_text(tests)
