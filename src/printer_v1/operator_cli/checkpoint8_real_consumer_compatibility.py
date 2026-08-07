"""Offline real-consumer compatibility probes for Checkpoint 8 fixtures.

This module is proof-only verification. It performs no network access, campaign
execution, scheduler work, memory generation, or production database mutation.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Mapping, Sequence

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.operator_cli.abstract_campaign_command import (
    CENTRAL_SCHEDULER_OWNER,
    SOURCE_GOVERNOR_OWNER,
    OwnerPort,
)
from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    LivePumpOriginAdapter,
    LiveSecondaryDiscoveryAdapter,
)
from printer_v1.operator_cli.window_15m_concrete_composition import (
    COMPOSITION_MATRIX,
    ordinary_window_15m_builder_identities,
)
from printer_v1.operator_cli import window_15m_disposable_public_composition_proof as proof
from printer_v1.sources.contracts import (
    GOVERNOR_ONLY_EXECUTION_PATH,
    SourceAdapterContext,
    SourceRequestRecord,
    build_governed_source_request,
    build_governor_decision,
)
from printer_v1.sources.direct_pump_migration import (
    SIGNATURE_PAGE_REQUEST_KIND,
    TRANSACTION_REQUEST_KIND,
    build_direct_pump_migration_adapter,
)
from printer_v1.sources.pumpswap import build_pumpswap_adapter
from printer_v1.sources.pumpswap_pool_account_batch import (
    build_pumpswap_pool_account_batch_adapter,
)
from printer_v1.sources.dexscreener import build_dexscreener_adapter
from printer_v1.sources.geckoterminal import build_geckoterminal_adapter


_GOV = OwnerPort(SOURCE_GOVERNOR_OWNER, True)
_SCH = OwnerPort(CENTRAL_SCHEDULER_OWNER, True)


def _context(
    source_name: str,
    request_kind: str,
    *,
    payload: Mapping[str, Any] | None = None,
    ordinal: int = 1,
) -> SourceAdapterContext:
    request = build_governed_source_request(
        source_name,
        request_kind,
        request_key=f"checkpoint8-real-consumer:{ordinal}:{source_name}:{request_kind}",
        payload=payload,
    )
    decision = build_governor_decision(request)
    if not decision.allowed:
        raise RuntimeError(
            f"CHECKPOINT8_REAL_CONSUMER_GOVERNOR_REJECTED:{source_name}:{request_kind}:{decision.reason}"
        )
    record = SourceRequestRecord(
        id=int(ordinal),
        source_name=source_name,
        request_kind=request_kind,
        requested_at=request.requested_at,
        request_key=request.request_key,
        tracking_priority=request.tracking_priority,
        source_status=SourceStatus.COMPLETE,
        data_quality_label=DataQualityLabel.CLEAN_DATA,
    )
    return SourceAdapterContext(
        request=request,
        request_record=record,
        decision=decision,
        governor_approved=True,
        execution_path=GOVERNOR_ONLY_EXECUTION_PATH,
    )


def _is_generic_ready(value: Any) -> bool:
    return isinstance(value, Mapping) and value.get("status") == "READY" and "fixture_route" in value


def _operation_count(value: Any) -> int:
    return int(getattr(value, "operation_count", 0) or 0)


def _accepted_source_result(result: Any) -> bool:
    return (
        getattr(result, "failure_type", None) in (None, "")
        and getattr(result, "source_status", None)
        in {SourceStatus.COMPLETE, SourceStatus.PARTIAL, SourceStatus.STALE}
    )


def _probe_row(
    *,
    spec: Any,
    output: Any,
    before: int,
    accepted: bool,
    observed: Any = None,
    detail: str | None = None,
) -> dict[str, Any]:
    after = _operation_count(output)
    return {
        "label": spec.label,
        "owner": spec.owner,
        "source_name": spec.source_name,
        "request_kind": spec.request_kind,
        "consumer_executed": after > before,
        "accepted": bool(accepted),
        "operation_count_delta": max(0, after - before),
        "returned_fixture_self": observed is output,
        "generic_ready_placeholder": _is_generic_ready(observed),
        "detail": detail,
    }


def run_checkpoint8_real_consumer_compatibility(runtime: Any) -> dict[str, Any]:
    """Exercise all 20 canonical fixture labels through real consumer boundaries."""
    materialized = proof.materialize_disposable_public_composition_execution(runtime)
    expected = tuple(ordinary_window_15m_builder_identities())
    specs = {spec.label: spec for spec in COMPOSITION_MATRIX}
    outputs = materialized.outputs_by_label
    rows: list[dict[str, Any]] = []

    # Derive the two candidate identities through the real Pump-origin consumer.
    pump_output = outputs["pump_origin_solana_rpc_transport"]
    before = _operation_count(pump_output)
    acquisition = LivePumpOriginAdapter(pump_output).acquire(
        source_governor=_GOV,
        central_scheduler=_SCH,
    )
    origins = tuple(acquisition.origin_proofs)
    rows.append(
        _probe_row(
            spec=specs["pump_origin_solana_rpc_transport"],
            output=pump_output,
            before=before,
            accepted=len(origins) == 2 and len({item.mint for item in origins}) == 2,
            observed=origins,
            detail=f"origins={len(origins)}",
        )
    )
    mints = [item.mint for item in origins]

    # Derive PumpSwap identities through the real restored-migration adapter.
    migration_output = outputs["direct_pump_finalized_migration_transport"]
    before = _operation_count(migration_output)
    migration_adapter = build_direct_pump_migration_adapter(
        enabled=True,
        transport=migration_output,
    )
    page = migration_adapter.execute(
        _context("solana_rpc", SIGNATURE_PAGE_REQUEST_KIND, ordinal=2)
    )
    migration_tokens: list[Mapping[str, Any]] = []
    if _accepted_source_result(page):
        for ordinal, item in enumerate(page.normalized_payload.get("signatures") or (), start=3):
            result = migration_adapter.execute(
                _context(
                    "solana_rpc",
                    TRANSACTION_REQUEST_KIND,
                    payload={"signature": str(item.get("signature") or "")},
                    ordinal=ordinal,
                )
            )
            if _accepted_source_result(result):
                migration_tokens.extend(
                    item
                    for item in (result.normalized_payload.get("tokens") or ())
                    if isinstance(item, Mapping)
                )
    migration_by_mint = {str(item.get("mint") or ""): item for item in migration_tokens}
    rows.append(
        _probe_row(
            spec=specs["direct_pump_finalized_migration_transport"],
            output=migration_output,
            before=before,
            accepted=(
                _accepted_source_result(page)
                and len(migration_by_mint) == 2
                and set(migration_by_mint) == set(mints)
            ),
            observed=page,
            detail=f"migration_tokens={len(migration_by_mint)}",
        )
    )

    first_mint = mints[0] if mints else ""
    first_migration = migration_by_mint.get(first_mint, {})
    first_pool = str(first_migration.get("pool_address") or "")
    first_signature = str(first_migration.get("migration_signature") or "")

    # Shared PumpSwap verifier seam: prove both confirmation labels independently.
    verifier = outputs["exact_pump_pumpswap_graduation_verifier_transport"]
    for ordinal, label in enumerate(
        (
            "exact_pump_pumpswap_graduation_verifier_transport",
            "pumpswap_migration_pool_confirmation",
        ),
        start=20,
    ):
        before = _operation_count(verifier)
        observed: Any = None
        accepted = False
        detail = None
        try:
            transport = verifier(first_signature, first_mint)
            adapter = build_pumpswap_adapter(enabled=True, fixture_transport=transport)
            observed = adapter.execute(
                _context(
                    "pumpswap",
                    "pumpswap_onchain_pool_confirmation",
                    payload={"expected_mint": first_mint, "pool_address": first_pool},
                    ordinal=ordinal,
                )
            )
            accepted = _accepted_source_result(observed)
        except Exception as exc:  # matrix reports, caller asserts readiness
            detail = f"{type(exc).__name__}:{exc}"
        rows.append(
            _probe_row(
                spec=specs[label],
                output=verifier,
                before=before,
                accepted=accepted,
                observed=observed,
                detail=detail,
            )
        )

    # Shared verifier seam also owns the account-batch label in C8 DI mapping.
    label = "pumpswap_account_batch_transport"
    before = _operation_count(verifier)
    observed = None
    accepted = False
    detail = None
    try:
        adapter = build_pumpswap_pool_account_batch_adapter(
            enabled=True,
            transport=verifier,
        )
        observed = adapter.execute(
            _context(
                "solana_rpc",
                "pumpswap_pool_account_batch",
                payload={
                    "addresses": [first_pool],
                    "address_to_candidates": {
                        first_pool: [{"mint": first_mint, "pool": first_pool, "venue": "pumpswap"}]
                    },
                },
                ordinal=30,
            )
        )
        accepted = _accepted_source_result(observed)
    except Exception as exc:
        detail = f"{type(exc).__name__}:{exc}"
    rows.append(
        _probe_row(
            spec=specs[label],
            output=verifier,
            before=before,
            accepted=accepted,
            observed=observed,
            detail=detail,
        )
    )

    # Secondary HTTP is consumed by the real operational secondary adapter.
    secondary = outputs["secondary_discovery_http_transport"]
    before = _operation_count(secondary)
    observed = None
    accepted = False
    detail = None
    try:
        observed = LiveSecondaryDiscoveryAdapter(secondary).enrich(
            source_governor=_GOV,
            central_scheduler=_SCH,
            receipt_time="2026-08-07T12:00:00+00:00",
            active_pools=[first_pool] if first_pool else (),
        )
        accepted = int(getattr(observed, "failures", 0) or 0) == 0
    except Exception as exc:
        detail = f"{type(exc).__name__}:{exc}"
    rows.append(
        _probe_row(
            spec=specs["secondary_discovery_http_transport"],
            output=secondary,
            before=before,
            accepted=accepted,
            observed=observed,
            detail=detail,
        )
    )

    def probe_adapter_label(
        label: str,
        *,
        source_name: str,
        request_kind: str,
        payload: Mapping[str, Any],
        adapter_builder: Any,
        factory_args: Sequence[Any] | None = None,
        factory_kwargs: Mapping[str, Any] | None = None,
        ordinal: int,
    ) -> None:
        output = outputs[label]
        before = _operation_count(output)
        observed = None
        accepted = False
        detail = None
        try:
            if factory_args is not None or factory_kwargs is not None:
                transport = output(*(factory_args or ()), **dict(factory_kwargs or {}))
            else:
                transport = output
            adapter = adapter_builder(transport)
            observed = adapter.execute(
                _context(
                    source_name,
                    request_kind,
                    payload=payload,
                    ordinal=ordinal,
                )
            )
            accepted = _accepted_source_result(observed)
        except Exception as exc:
            detail = f"{type(exc).__name__}:{exc}"
        rows.append(
            _probe_row(
                spec=specs[label],
                output=output,
                before=before,
                accepted=accepted,
                observed=observed,
                detail=detail,
            )
        )

    # DexScreener direct locator and shared batch factory labels.
    probe_adapter_label(
        "dexscreener_fresh_profiles_discovery",
        source_name="dexscreener",
        request_kind="dexscreener_fresh_profiles",
        payload={},
        adapter_builder=lambda transport: build_dexscreener_adapter(
            enabled=True, fixture_transport=transport
        ),
        ordinal=40,
    )
    for ordinal, label in enumerate(
        ("dexscreener_mint_batch_discovery", "unknown_liquidity_backup_gecko_to_dex"),
        start=41,
    ):
        probe_adapter_label(
            label,
            source_name="dexscreener",
            request_kind="candidate_market_batch",
            payload={"token_mints": list(mints)},
            adapter_builder=lambda transport: build_dexscreener_adapter(
                enabled=True, fixture_transport=transport
            ),
            factory_args=(list(mints),),
            ordinal=ordinal,
        )

    # GeckoTerminal direct nomination and shared exact-mint reconciliation factory.
    probe_adapter_label(
        "geckoterminal_fresh_nomination",
        source_name="geckoterminal",
        request_kind="geckoterminal_new_pool_discovery",
        payload={},
        adapter_builder=lambda transport: build_geckoterminal_adapter(
            enabled=True, fixture_transport=transport
        ),
        ordinal=50,
    )
    for ordinal, label in enumerate(
        ("geckoterminal_token_pools_discovery", "unknown_liquidity_backup_dex_to_gecko"),
        start=51,
    ):
        probe_adapter_label(
            label,
            source_name="geckoterminal",
            request_kind="candidate_market_batch",
            payload={"token_mint": first_mint},
            adapter_builder=lambda transport: build_geckoterminal_adapter(
                enabled=True, fixture_transport=transport
            ),
            factory_args=(first_mint,),
            ordinal=ordinal,
        )

    # Lifecycle snapshot/context seams return adapter objects directly.
    lifecycle_specs = (
        ("lifecycle_exact_pair_dexscreener_primary", "dexscreener", "pair_market_snapshot", {"token_mint": first_mint, "pool_address": first_pool}),
        ("lifecycle_exact_pair_geckoterminal_fallback", "geckoterminal", "pair_market_snapshot", {"token_mint": first_mint, "pool_address": first_pool}),
        ("preclose_coingecko_market_chain", "coingecko", "broad_market_context", {}),
        ("preclose_goplus_safety", "goplus", "safety_reference", {"token_mint": first_mint}),
        ("preclose_jupiter_entry_quote", "jupiter_quote", "paper_quote_realism", {"input_mint": "So11111111111111111111111111111111111111112", "output_mint": first_mint}),
        ("preclose_jupiter_exit_quote", "jupiter_quote", "paper_quote_realism", {"input_mint": first_mint, "output_mint": "So11111111111111111111111111111111111111112"}),
        ("preclose_solana_rpc_holder_primary", "solana_rpc", "holder_concentration_reference", {"token_mint": first_mint}),
        ("preclose_helius_holder_backup", "helius_free", "holder_concentration_reference", {"token_mint": first_mint}),
    )
    for ordinal, (label, source_name, consumer_kind, payload) in enumerate(lifecycle_specs, start=60):
        output = outputs[label]
        before = _operation_count(output)
        observed = None
        accepted = False
        detail = None
        try:
            adapter = output(
                token_mint=first_mint,
                pool_address=first_pool,
                input_mint=payload.get("input_mint"),
                output_mint=payload.get("output_mint"),
                timeout_seconds=1.0,
            )
            observed = adapter.execute(
                _context(
                    source_name,
                    consumer_kind,
                    payload=payload,
                    ordinal=ordinal,
                )
            )
            accepted = _accepted_source_result(observed)
        except Exception as exc:
            detail = f"{type(exc).__name__}:{exc}"
        rows.append(
            _probe_row(
                spec=specs[label],
                output=output,
                before=before,
                accepted=accepted,
                observed=observed,
                detail=detail,
            )
        )

    by_label = {row["label"]: row for row in rows}
    ordered = [by_label[label] for label in expected if label in by_label]
    ready = (
        len(ordered) == 20
        and all(row["accepted"] and row["consumer_executed"] for row in ordered)
        and not any(row["returned_fixture_self"] for row in ordered)
        and not any(row["generic_ready_placeholder"] for row in ordered)
    )
    return {
        "ready": ready,
        "labels": expected,
        "probes": ordered,
        "provider_fallback_used": False,
        "generic_ready_placeholder_count": sum(
            1 for row in ordered if row["generic_ready_placeholder"]
        ),
        "returned_fixture_self_count": sum(
            1 for row in ordered if row["returned_fixture_self"]
        ),
        "fixture_transport_operation_count": sum(
            int(getattr(value, "operation_count", 0) or 0)
            for value in {id(item): item for item in outputs.values()}.values()
        ),
    }
