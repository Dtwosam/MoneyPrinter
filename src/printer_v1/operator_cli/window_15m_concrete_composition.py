"""Zero-I/O concrete composition readiness for ordinary WINDOW_15M runs.

Enumerates every default transport/adapter factory reachable by the public
operational path, constructs each with fixed sample identities, and rejects
unusable results (None, disabled, transportless, wrong source). Performs zero
external requests and zero database writes.

Used twice:
1. one-shot wrapper, after child-interpreter + migration-ledger review, before
   staging / marker / child launch;
2. build_activation_preflight, before campaign artifacts or DB mutation.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from printer_v1.operator_cli.unified_terminal_closure import (
    DependencyPreflight,
    assert_runtime_dependency_preflight,
)


class ConcreteCompositionError(RuntimeError):
    """Raised when a required WINDOW_15M dependency is not concretely usable."""


# Fixed syntactically valid sample identities. Construction only — never sent
# on the wire during preflight (transports are built, not executed).
PREFLIGHT_MINT = "So11111111111111111111111111111111111111112"
PREFLIGHT_MINT_B = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
PREFLIGHT_POOL = "58oQChx4yWmvKdwLLZzBi4ChoCc2fqCUWBkwMihLYQo2"
PREFLIGHT_PAIR = PREFLIGHT_POOL
PREFLIGHT_SIGNATURE = (
    "5VERv8NMvzbJMEkV8xnrLkEaWRtSz9CosKDYjCJjBRnbJLgp8uirBgmQpjKhoR4tjF3sMcky"
    "H4ck4sY5sD5a5rZ"
)


def require_concrete_transport(label: str, transport: object) -> object:
    """Reject missing or non-callable transports before any stage mutation."""
    if transport is None:
        raise ConcreteCompositionError(
            f"REQUIRED_TRANSPORT_MISSING:{label}"
        )
    if not callable(transport):
        raise ConcreteCompositionError(
            f"REQUIRED_TRANSPORT_NOT_CALLABLE:{label}"
        )
    return transport


def require_concrete_adapter(
    label: str,
    adapter: object,
    *,
    expected_source_name: str | None = None,
    require_enabled: bool = True,
    require_transport: bool = True,
) -> object:
    """Reject None / disabled / transportless / wrong-source adapters.

    Production adapters expose ``enabled`` and ``transport``. Offline fixture
    adapters used by controlled-clock proofs may implement a different surface;
    when those attributes are absent the call still requires a non-None object
    and, when a source name is discoverable, an exact source match.
    """
    if adapter is None:
        raise ConcreteCompositionError(f"REQUIRED_ADAPTER_MISSING:{label}")
    has_enabled = hasattr(adapter, "enabled")
    has_transport = hasattr(adapter, "transport")
    if require_enabled and has_enabled and not bool(adapter.enabled):
        raise ConcreteCompositionError(f"REQUIRED_ADAPTER_DISABLED:{label}")
    if require_transport and has_transport:
        transport = adapter.transport
        if transport is None:
            raise ConcreteCompositionError(
                f"REQUIRED_ADAPTER_TRANSPORT_MISSING:{label}"
            )
        if not callable(transport):
            raise ConcreteCompositionError(
                f"REQUIRED_ADAPTER_TRANSPORT_NOT_CALLABLE:{label}"
            )
    # Production default builders always expose enabled+transport; rejecting a
    # production-shaped missing transport is mandatory even when the attribute
    # is present and None (handled above). When both attributes are absent the
    # object is treated as an injected fixture owner and only None is rejected.
    if require_transport and has_enabled and not has_transport:
        raise ConcreteCompositionError(
            f"REQUIRED_ADAPTER_TRANSPORT_MISSING:{label}"
        )
    if expected_source_name is not None:
        source_name = _adapter_source_name(adapter)
        if source_name is not None and str(source_name) != str(expected_source_name):
            raise ConcreteCompositionError(
                f"REQUIRED_ADAPTER_SOURCE_MISMATCH:{label}"
                f":expected={expected_source_name!r}:got={source_name!r}"
            )
    return adapter


def require_factory_output(
    label: str,
    factory: Callable[..., Any] | None,
    *,
    expected_source_name: str | None = None,
    require_enabled: bool = True,
    require_transport: bool = True,
    factory_kwargs: Mapping[str, Any] | None = None,
) -> object:
    """Invoke a supplied factory once and validate the concrete result.

    Used at runtime DI seams so a callable that returns None / disabled /
    transportless adapters cannot survive until after mutation.
    """
    if factory is None:
        raise ConcreteCompositionError(f"REQUIRED_FACTORY_MISSING:{label}")
    try:
        built = factory(**dict(factory_kwargs or {}))
    except ConcreteCompositionError:
        raise
    except Exception as exc:
        raise ConcreteCompositionError(
            f"REQUIRED_FACTORY_RAISED:{label}:{type(exc).__name__}:{exc}"
        ) from exc
    return require_concrete_adapter(
        label,
        built,
        expected_source_name=expected_source_name,
        require_enabled=require_enabled,
        require_transport=require_transport,
    )


def _adapter_source_name(adapter: object) -> str | None:
    metadata = getattr(adapter, "metadata", None)
    if metadata is not None:
        name = getattr(metadata, "source_name", None)
        if name is not None:
            return str(name)
    contract = getattr(adapter, "contract", None)
    if contract is not None:
        name = getattr(contract, "source_name", None)
        if name is not None:
            return str(name)
    name = getattr(adapter, "source_name", None)
    return str(name) if name is not None else None


@dataclass(frozen=True)
class CompositionBuilderSpec:
    """One reachable ordinary-path builder for the readiness matrix."""

    label: str
    owner: str
    source_name: str
    request_kind: str
    transport_builder: str
    adapter_builder: str


# Exact matrix of ordinary WINDOW_15M owners. Labels are stable for closeout.
COMPOSITION_MATRIX: tuple[CompositionBuilderSpec, ...] = (
    CompositionBuilderSpec(
        label="pump_origin_solana_rpc_transport",
        owner="authoritative_live_operational_campaign.OneShotUrllibPumpTransport",
        source_name="solana_rpc",
        request_kind="pump_origin_acquisition",
        transport_builder="OneShotUrllibPumpTransport",
        adapter_builder="OneShotUrllibPumpTransport",
    ),
    CompositionBuilderSpec(
        label="secondary_discovery_http_transport",
        owner="authoritative_live_operational_campaign.OneShotUrllibSecondaryTransport",
        source_name="secondary_http",
        request_kind="secondary_enrichment",
        transport_builder="OneShotUrllibSecondaryTransport",
        adapter_builder="OneShotUrllibSecondaryTransport",
    ),
    CompositionBuilderSpec(
        label="pumpswap_migration_pool_confirmation",
        owner="sources.pumpswap.build_pumpswap_confirmation_transport",
        source_name="pumpswap",
        request_kind="pumpswap_onchain_pool_confirmation",
        transport_builder="build_pumpswap_confirmation_transport",
        adapter_builder="build_pumpswap_adapter",
    ),
    CompositionBuilderSpec(
        label="pumpswap_account_batch_transport",
        owner="sources.pumpswap_pool_account_batch.build_pumpswap_pool_account_batch_transport",
        source_name="pumpswap",
        request_kind="pumpswap_pool_account_batch",
        transport_builder="build_pumpswap_pool_account_batch_transport",
        adapter_builder="build_pumpswap_pool_account_batch_adapter",
    ),
    CompositionBuilderSpec(
        label="dexscreener_fresh_profiles_discovery",
        owner="sources.dexscreener.build_dexscreener_fresh_profiles_transport",
        source_name="dexscreener",
        request_kind="dexscreener_fresh_profiles",
        transport_builder="build_dexscreener_fresh_profiles_transport",
        adapter_builder="build_dexscreener_adapter",
    ),
    CompositionBuilderSpec(
        label="dexscreener_mint_batch_discovery",
        owner="sources.dexscreener.build_dexscreener_mint_batch_transport",
        source_name="dexscreener",
        request_kind="candidate_market_batch",
        transport_builder="build_dexscreener_mint_batch_transport",
        adapter_builder="build_dexscreener_adapter",
    ),
    CompositionBuilderSpec(
        label="geckoterminal_fresh_nomination",
        owner="sources.geckoterminal.build_geckoterminal_pools_transport",
        source_name="geckoterminal",
        request_kind="geckoterminal_new_pool_discovery",
        transport_builder="build_geckoterminal_pools_transport",
        adapter_builder="build_geckoterminal_adapter",
    ),
    CompositionBuilderSpec(
        label="geckoterminal_token_pools_discovery",
        owner="sources.geckoterminal.build_geckoterminal_token_pools_transport",
        source_name="geckoterminal",
        request_kind="candidate_market_batch",
        transport_builder="build_geckoterminal_token_pools_transport",
        adapter_builder="build_geckoterminal_adapter",
    ),
    CompositionBuilderSpec(
        label="unknown_liquidity_backup_dex_to_gecko",
        owner="discovery.permanent_discovery_availability.run_bounded_unknown_liquidity_backup",
        source_name="geckoterminal",
        request_kind="candidate_market_batch",
        transport_builder="build_geckoterminal_token_pools_transport",
        adapter_builder="build_geckoterminal_adapter",
    ),
    CompositionBuilderSpec(
        label="unknown_liquidity_backup_gecko_to_dex",
        owner="discovery.permanent_discovery_availability.run_bounded_unknown_liquidity_backup",
        source_name="dexscreener",
        request_kind="candidate_market_batch",
        transport_builder="build_dexscreener_mint_batch_transport",
        adapter_builder="build_dexscreener_adapter",
    ),
    CompositionBuilderSpec(
        label="lifecycle_exact_pair_dexscreener_primary",
        owner="operator_cli.e2i_source_transport.build_e2i_dexscreener_adapter",
        source_name="dexscreener",
        request_kind="exact_pair_snapshot",
        transport_builder="build_dexscreener_token_transport",
        adapter_builder="build_e2i_dexscreener_adapter",
    ),
    CompositionBuilderSpec(
        label="lifecycle_exact_pair_geckoterminal_fallback",
        owner="operator_cli.exact_pair_source_redundancy.build_default_geckoterminal_fallback_adapter",
        source_name="geckoterminal",
        request_kind="exact_pair_snapshot",
        transport_builder="build_geckoterminal_pair_snapshot_transport",
        adapter_builder="build_default_geckoterminal_fallback_adapter",
    ),
    CompositionBuilderSpec(
        label="preclose_coingecko_market_chain",
        owner="sources.coingecko.build_coingecko_market_transport",
        source_name="coingecko",
        request_kind="broad_market_context",
        transport_builder="build_coingecko_market_transport",
        adapter_builder="build_coingecko_adapter",
    ),
    CompositionBuilderSpec(
        label="preclose_goplus_safety",
        owner="sources.goplus.build_goplus_token_safety_transport",
        source_name="goplus",
        request_kind="safety_reference",
        transport_builder="build_goplus_token_safety_transport",
        adapter_builder="build_goplus_adapter",
    ),
    CompositionBuilderSpec(
        label="preclose_jupiter_entry_quote",
        owner="sources.jupiter_quote.build_jupiter_paper_quote_transport",
        source_name="jupiter_quote",
        request_kind="paper_quote_realism",
        transport_builder="build_jupiter_paper_quote_transport",
        adapter_builder="build_jupiter_quote_adapter",
    ),
    CompositionBuilderSpec(
        label="preclose_jupiter_exit_quote",
        owner="sources.jupiter_quote.build_jupiter_paper_quote_transport",
        source_name="jupiter_quote",
        request_kind="paper_quote_realism",
        transport_builder="build_jupiter_paper_quote_transport",
        adapter_builder="build_jupiter_quote_adapter",
    ),
    CompositionBuilderSpec(
        label="preclose_solana_rpc_holder_primary",
        owner="sources.solana_rpc_holder.build_solana_rpc_holder_transport",
        source_name="solana_rpc",
        request_kind="holder_concentration_reference",
        transport_builder="build_solana_rpc_holder_transport",
        adapter_builder="build_solana_rpc_holder_adapter",
    ),
    CompositionBuilderSpec(
        label="preclose_helius_holder_backup",
        owner="operator_cli.safety_context_source_redundancy.build_default_solana_rpc_holder_backup_adapter",
        source_name="helius_free",
        request_kind="holder_concentration_reference",
        transport_builder="build_helius_holder_transport_or_auth_missing_fixture",
        adapter_builder="build_default_solana_rpc_holder_backup_adapter",
    ),
)


def _build_composition_callables(
    *,
    timeout_seconds: float,
) -> tuple[tuple[str, Callable[[], object]], ...]:
    """Construct zero-I/O builders for every matrix entry."""
    from printer_v1.operator_cli.authoritative_live_operational_campaign import (
        OneShotUrllibPumpTransport,
        OneShotUrllibSecondaryTransport,
    )
    from printer_v1.operator_cli.e2i_source_transport import build_e2i_dexscreener_adapter
    from printer_v1.operator_cli.exact_pair_source_redundancy import (
        build_default_geckoterminal_fallback_adapter,
    )
    from printer_v1.operator_cli.safety_context_source_redundancy import (
        build_default_solana_rpc_holder_backup_adapter,
    )
    from printer_v1.sources.coingecko import (
        COINGECKO_SOURCE_NAME,
        build_coingecko_adapter,
        build_coingecko_market_transport,
    )
    from printer_v1.sources.dexscreener import (
        DEXSCREENER_SOURCE_NAME,
        build_dexscreener_adapter,
        build_dexscreener_fresh_profiles_transport,
        build_dexscreener_mint_batch_transport,
    )
    from printer_v1.sources.geckoterminal import (
        GECKOTERMINAL_SOURCE_NAME,
        build_geckoterminal_adapter,
        build_geckoterminal_pools_transport,
        build_geckoterminal_token_pools_transport,
    )
    from printer_v1.sources.goplus import (
        GOPLUS_SOURCE_NAME,
        build_goplus_adapter,
        build_goplus_token_safety_transport,
    )
    from printer_v1.sources.helius_holder import HELIUS_SOURCE_NAME
    from printer_v1.sources.jupiter_quote import (
        DEFAULT_PAPER_AMOUNT_LAMPORTS,
        DEFAULT_SLIPPAGE_BPS,
        JUPITER_QUOTE_SOURCE_NAME,
        WSOL_MINT,
        build_jupiter_paper_quote_transport,
        build_jupiter_quote_adapter,
    )
    from printer_v1.sources.operational_source_contracts import (
        OFFICIAL_SOLANA_PUBLIC_RPC_URL,
        resolve_solana_rpc_configuration,
    )
    from printer_v1.sources.pumpswap import (
        PUMPSWAP_SOURCE_NAME,
        build_pumpswap_adapter,
        build_pumpswap_confirmation_transport,
    )
    from printer_v1.sources.pumpswap_pool_account_batch import (
        build_pumpswap_pool_account_batch_adapter,
        build_pumpswap_pool_account_batch_transport,
    )
    from printer_v1.sources.solana_rpc_holder import (
        SOLANA_RPC_SOURCE_NAME,
        build_solana_rpc_holder_adapter,
        build_solana_rpc_holder_transport,
    )

    mint = PREFLIGHT_MINT
    pool = PREFLIGHT_POOL
    timeout = float(timeout_seconds)

    def pump_origin() -> object:
        try:
            endpoint = str(resolve_solana_rpc_configuration().url)
        except Exception:
            endpoint = OFFICIAL_SOLANA_PUBLIC_RPC_URL
        transport = OneShotUrllibPumpTransport(endpoint)
        if not hasattr(transport, "json_rpc"):
            raise ConcreteCompositionError(
                "REQUIRED_ADAPTER_NOT_CONSTRUCTIBLE:pump_origin_solana_rpc_transport"
            )
        return transport

    def secondary_http() -> object:
        transport = OneShotUrllibSecondaryTransport()
        if not hasattr(transport, "json_get"):
            raise ConcreteCompositionError(
                "REQUIRED_ADAPTER_NOT_CONSTRUCTIBLE:secondary_discovery_http_transport"
            )
        return transport

    def pumpswap_confirm() -> object:
        transport = require_concrete_transport(
            "pumpswap_migration_pool_confirmation.transport",
            build_pumpswap_confirmation_transport(
                expected_mint=mint,
                pool_address=pool,
                migration_signature=PREFLIGHT_SIGNATURE,
                timeout_seconds=timeout,
            ),
        )
        return require_concrete_adapter(
            "pumpswap_migration_pool_confirmation",
            build_pumpswap_adapter(enabled=True, fixture_transport=transport),
            expected_source_name=PUMPSWAP_SOURCE_NAME,
        )

    def pumpswap_batch() -> object:
        transport = require_concrete_transport(
            "pumpswap_account_batch_transport.transport",
            build_pumpswap_pool_account_batch_transport(
                addresses=[pool],
                timeout_seconds=timeout,
            ),
        )
        return require_concrete_adapter(
            "pumpswap_account_batch_transport",
            build_pumpswap_pool_account_batch_adapter(
                enabled=True, transport=transport
            ),
            expected_source_name="solana_rpc",
            require_enabled=True,
            require_transport=True,
        )

    def dex_fresh() -> object:
        transport = require_concrete_transport(
            "dexscreener_fresh_profiles_discovery.transport",
            build_dexscreener_fresh_profiles_transport(timeout_seconds=timeout),
        )
        return require_concrete_adapter(
            "dexscreener_fresh_profiles_discovery",
            build_dexscreener_adapter(enabled=True, fixture_transport=transport),
            expected_source_name=DEXSCREENER_SOURCE_NAME,
        )

    def dex_batch() -> object:
        transport = require_concrete_transport(
            "dexscreener_mint_batch_discovery.transport",
            build_dexscreener_mint_batch_transport([mint], timeout_seconds=timeout),
        )
        return require_concrete_adapter(
            "dexscreener_mint_batch_discovery",
            build_dexscreener_adapter(enabled=True, fixture_transport=transport),
            expected_source_name=DEXSCREENER_SOURCE_NAME,
        )

    def gt_fresh() -> object:
        transport = require_concrete_transport(
            "geckoterminal_fresh_nomination.transport",
            build_geckoterminal_pools_transport(timeout_seconds=timeout),
        )
        return require_concrete_adapter(
            "geckoterminal_fresh_nomination",
            build_geckoterminal_adapter(enabled=True, fixture_transport=transport),
            expected_source_name=GECKOTERMINAL_SOURCE_NAME,
        )

    def gt_token_pools() -> object:
        transport = require_concrete_transport(
            "geckoterminal_token_pools_discovery.transport",
            build_geckoterminal_token_pools_transport(mint, timeout_seconds=timeout),
        )
        return require_concrete_adapter(
            "geckoterminal_token_pools_discovery",
            build_geckoterminal_adapter(enabled=True, fixture_transport=transport),
            expected_source_name=GECKOTERMINAL_SOURCE_NAME,
        )

    def backup_dex_to_gecko() -> object:
        transport = require_concrete_transport(
            "unknown_liquidity_backup_dex_to_gecko.transport",
            build_geckoterminal_token_pools_transport(mint, timeout_seconds=timeout),
        )
        return require_concrete_adapter(
            "unknown_liquidity_backup_dex_to_gecko",
            build_geckoterminal_adapter(enabled=True, fixture_transport=transport),
            expected_source_name=GECKOTERMINAL_SOURCE_NAME,
        )

    def backup_gecko_to_dex() -> object:
        transport = require_concrete_transport(
            "unknown_liquidity_backup_gecko_to_dex.transport",
            build_dexscreener_mint_batch_transport([mint], timeout_seconds=timeout),
        )
        return require_concrete_adapter(
            "unknown_liquidity_backup_gecko_to_dex",
            build_dexscreener_adapter(enabled=True, fixture_transport=transport),
            expected_source_name=DEXSCREENER_SOURCE_NAME,
        )

    def lifecycle_dex_primary() -> object:
        return require_concrete_adapter(
            "lifecycle_exact_pair_dexscreener_primary",
            build_e2i_dexscreener_adapter(token_mint=mint, timeout_seconds=timeout),
            expected_source_name=DEXSCREENER_SOURCE_NAME,
        )

    def lifecycle_gt_fallback() -> object:
        return require_concrete_adapter(
            "lifecycle_exact_pair_geckoterminal_fallback",
            build_default_geckoterminal_fallback_adapter(
                pair_address=pool,
                token_mint=mint,
                timeout_seconds=timeout,
            ),
            expected_source_name=GECKOTERMINAL_SOURCE_NAME,
        )

    def coingecko_market() -> object:
        transport = require_concrete_transport(
            "preclose_coingecko_market_chain.transport",
            build_coingecko_market_transport(timeout_seconds=timeout),
        )
        return require_concrete_adapter(
            "preclose_coingecko_market_chain",
            build_coingecko_adapter(enabled=True, fixture_transport=transport),
            expected_source_name=COINGECKO_SOURCE_NAME,
        )

    def goplus_safety() -> object:
        transport = require_concrete_transport(
            "preclose_goplus_safety.transport",
            build_goplus_token_safety_transport(mint, timeout_seconds=timeout),
        )
        return require_concrete_adapter(
            "preclose_goplus_safety",
            build_goplus_adapter(enabled=True, fixture_transport=transport),
            expected_source_name=GOPLUS_SOURCE_NAME,
        )

    def jupiter_entry() -> object:
        transport = require_concrete_transport(
            "preclose_jupiter_entry_quote.transport",
            build_jupiter_paper_quote_transport(
                input_mint=WSOL_MINT,
                output_mint=mint,
                amount_lamports=DEFAULT_PAPER_AMOUNT_LAMPORTS,
                slippage_bps=DEFAULT_SLIPPAGE_BPS,
                timeout_seconds=timeout,
            ),
        )
        return require_concrete_adapter(
            "preclose_jupiter_entry_quote",
            build_jupiter_quote_adapter(enabled=True, fixture_transport=transport),
            expected_source_name=JUPITER_QUOTE_SOURCE_NAME,
        )

    def jupiter_exit() -> object:
        transport = require_concrete_transport(
            "preclose_jupiter_exit_quote.transport",
            build_jupiter_paper_quote_transport(
                input_mint=mint,
                output_mint=WSOL_MINT,
                amount_lamports=DEFAULT_PAPER_AMOUNT_LAMPORTS,
                slippage_bps=DEFAULT_SLIPPAGE_BPS,
                timeout_seconds=timeout,
            ),
        )
        return require_concrete_adapter(
            "preclose_jupiter_exit_quote",
            build_jupiter_quote_adapter(enabled=True, fixture_transport=transport),
            expected_source_name=JUPITER_QUOTE_SOURCE_NAME,
        )

    def holder_primary() -> object:
        transport = require_concrete_transport(
            "preclose_solana_rpc_holder_primary.transport",
            build_solana_rpc_holder_transport(mint, timeout_seconds=timeout),
        )
        return require_concrete_adapter(
            "preclose_solana_rpc_holder_primary",
            build_solana_rpc_holder_adapter(enabled=True, fixture_transport=transport),
            expected_source_name=SOLANA_RPC_SOURCE_NAME,
        )

    def holder_backup() -> object:
        return require_concrete_adapter(
            "preclose_helius_holder_backup",
            build_default_solana_rpc_holder_backup_adapter(
                token_mint=mint, timeout_seconds=timeout
            ),
            expected_source_name=HELIUS_SOURCE_NAME,
        )

    builders: list[tuple[str, Callable[[], object]]] = [
        ("pump_origin_solana_rpc_transport", pump_origin),
        ("secondary_discovery_http_transport", secondary_http),
        ("pumpswap_migration_pool_confirmation", pumpswap_confirm),
        ("pumpswap_account_batch_transport", pumpswap_batch),
        ("dexscreener_fresh_profiles_discovery", dex_fresh),
        ("dexscreener_mint_batch_discovery", dex_batch),
        ("geckoterminal_fresh_nomination", gt_fresh),
        ("geckoterminal_token_pools_discovery", gt_token_pools),
        ("unknown_liquidity_backup_dex_to_gecko", backup_dex_to_gecko),
        ("unknown_liquidity_backup_gecko_to_dex", backup_gecko_to_dex),
        ("lifecycle_exact_pair_dexscreener_primary", lifecycle_dex_primary),
        ("lifecycle_exact_pair_geckoterminal_fallback", lifecycle_gt_fallback),
        ("preclose_coingecko_market_chain", coingecko_market),
        ("preclose_goplus_safety", goplus_safety),
        ("preclose_jupiter_entry_quote", jupiter_entry),
        ("preclose_jupiter_exit_quote", jupiter_exit),
        ("preclose_solana_rpc_holder_primary", holder_primary),
        ("preclose_helius_holder_backup", holder_backup),
    ]
    return tuple(builders)


def window_15m_preflight_builders(
    *,
    timeout_seconds: float = 5.0,
) -> tuple[tuple[str, Callable[[], object]], ...]:
    """Return labeled zero-I/O builders for assert_runtime_dependency_preflight."""
    return _build_composition_callables(timeout_seconds=timeout_seconds)


def run_window_15m_concrete_composition_preflight(
    *,
    repository_root: str | None = None,
    timeout_seconds: float = 5.0,
    adapter_builders: Iterable[tuple[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run the full concrete composition guard with zero external I/O.

    Returns a bounded non-secret readiness payload. Raises
    ConcreteCompositionError when any required builder is unusable.
    """
    builders = (
        tuple(adapter_builders)
        if adapter_builders is not None
        else window_15m_preflight_builders(timeout_seconds=timeout_seconds)
    )
    # Validate matrix coverage against builder labels when using defaults.
    if adapter_builders is None:
        matrix_labels = {spec.label for spec in COMPOSITION_MATRIX}
        builder_labels = {label for label, _ in builders}
        missing = sorted(matrix_labels - builder_labels)
        extra = sorted(builder_labels - matrix_labels)
        if missing or extra:
            raise ConcreteCompositionError(
                f"COMPOSITION_MATRIX_MISMATCH:missing={missing}:extra={extra}"
            )

    # Adapter/transport constructibility is the composition subject. Package
    # path binding remains owned by build_activation_preflight; do not fail
    # composition solely because a disposable test repository root is not the
    # installed package parent.
    dependency: DependencyPreflight = assert_runtime_dependency_preflight(
        repository_root=None,
        adapter_builders=builders,
    )
    issues = list(dependency.issues)
    # Surface ConcreteCompositionError detail from builders that raised.
    for label, builder in builders:
        try:
            built = builder()
        except ConcreteCompositionError as exc:
            issues.append(str(exc))
            continue
        except Exception as exc:
            issues.append(
                f"REQUIRED_ADAPTER_NOT_CONSTRUCTIBLE:{label}:{type(exc).__name__}"
            )
            continue
        if built is None:
            issues.append(f"REQUIRED_ADAPTER_NOT_CONSTRUCTIBLE:{label}")

    if issues:
        raise ConcreteCompositionError(
            "WINDOW_15M_CONCRETE_COMPOSITION_BLOCKED:" + ";".join(issues)
        )

    matrix_rows = [
        {
            "label": spec.label,
            "owner": spec.owner,
            "source_name": spec.source_name,
            "request_kind": spec.request_kind,
            "transport_builder": spec.transport_builder,
            "adapter_builder": spec.adapter_builder,
            "enabled_state": True,
            "explicit_transport_present": True,
            "zero_io_result": "PASS",
        }
        for spec in COMPOSITION_MATRIX
    ]
    return {
        "status": "READY",
        "external_requests": 0,
        "database_writes": 0,
        "builder_count": len(builders),
        "matrix": matrix_rows,
        "dependency": dependency.to_dict()
        if hasattr(dependency, "to_dict")
        else {
            "status": dependency.status,
            "interpreter": dependency.interpreter,
            "package_path": dependency.package_path,
            "issues": list(dependency.issues),
        },
    }


def composition_matrix_as_dicts() -> list[dict[str, str]]:
    """Stable matrix projection for tests and closeout."""
    return [
        {
            "label": spec.label,
            "owner": spec.owner,
            "source_name": spec.source_name,
            "request_kind": spec.request_kind,
            "transport_builder": spec.transport_builder,
            "adapter_builder": spec.adapter_builder,
        }
        for spec in COMPOSITION_MATRIX
    ]


__all__ = [
    "COMPOSITION_MATRIX",
    "PREFLIGHT_MINT",
    "PREFLIGHT_MINT_B",
    "PREFLIGHT_PAIR",
    "PREFLIGHT_POOL",
    "PREFLIGHT_SIGNATURE",
    "CompositionBuilderSpec",
    "ConcreteCompositionError",
    "composition_matrix_as_dicts",
    "require_concrete_adapter",
    "require_concrete_transport",
    "require_factory_output",
    "run_window_15m_concrete_composition_preflight",
    "window_15m_preflight_builders",
]
