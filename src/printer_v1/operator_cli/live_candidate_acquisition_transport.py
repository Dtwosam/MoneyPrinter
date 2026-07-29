"""Canonical bounded live transport owner for acquisition-only N2/N7 modes.

This module constructs source operations only.  The acquisition integration
owner remains responsible for Scheduler jobs, Source Governor admission,
persistence, budgets, leases, cancellation, and terminal cleanup.  Network
transports are one-shot, finite, close their response, and never retry, rotate,
reconnect, or create successor work.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import base64
import hashlib
import json
import os
from types import MappingProxyType
from typing import Any, Callable, Mapping, Protocol, Sequence
from urllib import error as url_error
from urllib import parse as url_parse
from urllib import request as url_request

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.discovery.pump_migration_observation import (
    CANDIDATE_MINT,
    MIGRATION_SIGNATURE,
    NO_PUMP_GRADUATION_CLAIM,
    PUMP_ACTIVE_BONDING_CURVE,
    PUMP_BONDING_CURVE,
    PUMP_GRADUATION_CLAIMED,
    PUMP_LINEAGE_CONFLICT,
    PUMPSWAP_POOL,
    classify_candidate_lineage_branch,
    plan_candidate_migration_locator,
    validate_candidate_migration_locator,
)
from printer_v1.operator_cli.candidate_acquisition_integration import (
    PHASE_ENRICHMENT,
    AcquisitionSourceOperation,
    CursorHead,
    CursorNamespace,
)
from printer_v1.sources.contracts import NormalizedSourceResult, SourceAdapterContext
from printer_v1.sources.dexscreener import (
    DEXSCREENER_TOKEN_PROFILES_URL,
    DEXSCREENER_TOKENS_BATCH_URL_TEMPLATE,
    _SOLANA_INFRASTRUCTURE_MINTS,
    normalize_dexscreener_fixture_result,
)
from printer_v1.sources.geckoterminal import (
    GECKOTERMINAL_NEW_POOLS_URL,
    normalize_geckoterminal_payload,
)
from printer_v1.sources.goplus import (
    GOPLUS_SOLANA_TOKEN_SECURITY_URL,
    normalize_goplus_payload,
)
from printer_v1.sources.pump_contracts import (
    OFFICIAL_REPOSITORY_COMMIT,
    PUMP_IDL_SHA256,
    PUMPSWAP_IDL_SHA256,
    SYSTEM_PROGRAM_ID,
    TOKEN_2022_PROGRAM_ID,
    TOKEN_PROGRAM_ID,
    WSOL_MINT,
    decode_pump_bonding_curve_account,
    decode_pumpswap_pool_account,
    decode_supported_pump_creation_transaction,
    decode_supported_pump_migration_transaction,
    verify_pinned_pump_migration,
)
from printer_v1.sources.pumpfun_direct import PUMP_PROGRAM_ID
from printer_v1.sources.registry import SOURCE_REGISTRY
from printer_v1.sources.pumpfun_origin import PUMP_CREATE_INDEX_ADDRESS
from printer_v1.sources.pumpswap import PUMPSWAP_AMM_PROGRAM_ID
from printer_v1.sources.solana_rpc_holder import normalize_solana_rpc_holder_response
from printer_v1.sources.solana_rpc_token_age import (
    _decode_spl_token_base_mint_state,
    _decode_token_2022_mint_state,
)


RPC_ENVIRONMENT_NAME = "PRINTER_SOLANA_RPC_URL"
DEFAULT_TIMEOUT_SECONDS = 10.0
PER_RESPONSE_BYTE_CEILING = 1 * 1024 * 1024
# DexScreener's public tokens endpoint resolves up to 30 comma-separated
# addresses in one request. Nomination is bounded by this real transport limit
# (and by the owner's row/byte ceilings), never pre-truncated to the cohort M,
# so no aggregator freezes a partial cohort ahead of the Pump nominations.
DEXSCREENER_BATCH_ADDRESS_LIMIT = 30
DEXSCREENER_HEADERS = MappingProxyType({"Accept": "application/json", "User-Agent": "PrinterV1/0.1"})
GECKOTERMINAL_HEADERS = MappingProxyType({"Accept": "application/json;version=20230203", "User-Agent": "PrinterV1/0.1"})
PUBLIC_HEADERS = MappingProxyType({"Accept": "application/json", "User-Agent": "PrinterV1/0.1"})
RPC_HEADERS = MappingProxyType({"Accept": "application/json", "Content-Type": "application/json", "User-Agent": "PrinterV1/0.1"})
MINT_ACCOUNT_EVIDENCE_VERSION = "candidate-mint-account-v2"
INFRASTRUCTURE_MINTS = _SOLANA_INFRASTRUCTURE_MINTS
CURSOR_NETWORK = "solana-mainnet"
CURSOR_DECODER_VERSION = "canonical-live-acquisition-v1"
LIVE_TAIL_DIRECTION = "FORWARD"


class LiveAcquisitionConfigurationError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class LiveAcquisitionTransportError(RuntimeError):
    def __init__(self, code: str, endpoint_role: str, *, bytes_used: int = 0,
                 operation_kind: str = "ATTEMPTED_TRANSPORT") -> None:
        self.code = code
        self.endpoint_role = endpoint_role
        self.bytes_used = int(bytes_used)
        self.operation_kind = operation_kind
        super().__init__(f"{code}:{endpoint_role}")


class LiveAcquisitionValidationError(RuntimeError):
    """Post-response parsing/contract failure with no new transport attempt."""

    def __init__(self, code: str, endpoint_role: str) -> None:
        self.code = code
        self.endpoint_role = endpoint_role
        super().__init__(f"{code}:{endpoint_role}")


@dataclass(frozen=True)
class LiveAcquisitionConfiguration:
    rpc_url: str = field(repr=False)
    redacted_rpc_host: str
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    per_response_byte_ceiling: int = PER_RESPONSE_BYTE_CEILING
    goplus_enabled: bool = True
    global_pump_observer_enabled: bool = True


@dataclass(frozen=True)
class TransportResponse:
    payload: Any
    bytes_used: int
    operation_kind: str
    endpoint_role: str


def _batch_account_associations(
    requested_mints: Sequence[str], values: Sequence[Any]
) -> list[tuple[str, int | None, str | None, Any, str, str | None]]:
    """Bind every requested mint to one exact response slot.

    Solana's getMultipleAccounts result is positional. Frozen transports may
    additionally wrap entries as {"address": ..., "account": ...}; in that
    test-only/address-asserted shape, response order may differ and association
    is recovered by exact address while retaining the returned slot.
    """
    addressed = any(
        isinstance(value, Mapping) and "address" in value and "account" in value
        for value in values
    )
    if not addressed:
        return [
            (
                mint,
                slot if slot < len(values) else None,
                None,
                values[slot] if slot < len(values) else None,
                "POSITIONAL_RPC_CONTRACT",
                None if slot < len(values) else "MINT_ACCOUNT_MISSING",
            )
            for slot, mint in enumerate(requested_mints)
        ]

    by_address: dict[str, tuple[int, Any]] = {}
    duplicate_addresses: set[str] = set()
    for slot, value in enumerate(values):
        if not isinstance(value, Mapping) or "address" not in value or "account" not in value:
            continue
        address = str(value.get("address") or "")
        if not address or address in by_address:
            duplicate_addresses.add(address)
            continue
        by_address[address] = (slot, value.get("account"))
    output: list[tuple[str, int | None, str | None, Any, str, str | None]] = []
    for mint in requested_mints:
        matched = by_address.get(mint)
        if matched is None or mint in duplicate_addresses:
            output.append((
                mint, None, None, None, "EXPLICIT_RESPONSE_ADDRESS",
                "MINT_TARGET_MISMATCH",
            ))
            continue
        slot, account = matched
        output.append((mint, slot, mint, account, "EXPLICIT_RESPONSE_ADDRESS", None))
    return output


def _batch_pool_account_associations(
    requested_pools: Sequence[str], values: Sequence[Any]
) -> dict[str, tuple[int | None, str | None, Any, str, str | None]]:
    """Bind exact pool targets using the RPC positional contract or fixtures."""
    associated = _batch_account_associations(requested_pools, values)
    output: dict[str, tuple[int | None, str | None, Any, str, str | None]] = {}
    for target, slot, response_address, account, mode, failure in associated:
        translated = (
            "POOL_TARGET_MISMATCH" if failure == "MINT_TARGET_MISMATCH"
            else "POOL_ACCOUNT_MISSING" if failure == "MINT_ACCOUNT_MISSING"
            else failure
        )
        output[target] = (slot, response_address, account, mode, translated)
    return output


def _strict_base64_account_data(account: Any) -> bytes | None:
    if not isinstance(account, Mapping):
        return None
    data = account.get("data")
    if (
        not isinstance(data, (list, tuple))
        or len(data) < 2
        or not isinstance(data[0], str)
        or data[1] != "base64"
    ):
        return None
    try:
        return base64.b64decode(data[0], validate=True)
    except (ValueError, TypeError):
        return None


def _mint_account_observation(
    *,
    requested_mint: str,
    response_slot: int | None,
    response_address: str | None,
    account: Any,
    association_mode: str,
    association_failure: str | None,
) -> dict[str, Any]:
    """Create one exact-target, categorical chain-mint observation."""
    owner = str(account.get("owner") or "") if isinstance(account, Mapping) else ""
    raw = _strict_base64_account_data(account)
    reason = association_failure
    account_presence = "PRESENT" if isinstance(account, Mapping) else "MISSING"
    owner_status = "NOT_REACHED"
    layout_status = "NOT_REACHED"
    program_status = "FAIL"
    mint_valid = False

    if reason is None and requested_mint in INFRASTRUCTURE_MINTS:
        reason = "INFRASTRUCTURE_MINT_EXCLUDED"
    elif reason is None and not isinstance(account, Mapping):
        reason = "MINT_ACCOUNT_MISSING"
    elif reason is None and raw is None:
        owner_status = "PASS" if owner in {TOKEN_PROGRAM_ID, TOKEN_2022_PROGRAM_ID} else "FAIL"
        program_status = "PASS" if owner_status == "PASS" else "FAIL"
        layout_status = "FAIL"
        reason = "MINT_ACCOUNT_DATA_MALFORMED"
    elif reason is None and owner == TOKEN_PROGRAM_ID:
        owner_status = "PASS"
        program_status = "PASS"
        mint_valid = len(raw) == 82 and _decode_spl_token_base_mint_state(raw)[0]
        layout_status = "PASS" if mint_valid else "FAIL"
        if not mint_valid:
            reason = "MINT_ACCOUNT_DATA_MALFORMED"
    elif reason is None and owner == TOKEN_2022_PROGRAM_ID:
        owner_status = "PASS"
        program_status = "PASS"
        # The adopted Token-2022 contract is a 166-byte minimum followed by a
        # structurally valid TLV walk. Extensions do not make a mint invalid.
        mint_valid = len(raw) >= 166 and _decode_token_2022_mint_state(raw)[0]
        layout_status = "PASS" if mint_valid else "FAIL"
        if not mint_valid:
            reason = "MINT_ACCOUNT_DATA_MALFORMED"
    elif reason is None:
        owner_status = "FAIL"
        layout_status = "NOT_ADOPTED"
        looks_like_mint = (
            (len(raw) == 82 and _decode_spl_token_base_mint_state(raw)[0])
            or (len(raw) >= 166 and _decode_token_2022_mint_state(raw)[0])
        )
        reason = (
            "MINT_UNSUPPORTED_TOKEN_PROGRAM"
            if looks_like_mint else "MINT_WRONG_PROGRAM_OWNER"
        )

    authority_safe = bool(
        mint_valid
        and raw is not None
        and raw[0:4] == b"\0" * 4
        and raw[46:50] == b"\0" * 4
    )
    return {
        "mint": requested_mint,
        "base_mint": requested_mint,
        "token_program_id": owner or None,
        "lineage_claim": "UNKNOWN_ORIGIN",
        "facts": {
            "mint_account_evidence_version": MINT_ACCOUNT_EVIDENCE_VERSION,
            "mint_request_target": requested_mint,
            "mint_response_slot": response_slot,
            "mint_response_address": response_address,
            "mint_response_association": association_mode,
            "mint_account_presence": account_presence,
            "mint_owner_status": owner_status,
            "mint_layout_status": layout_status,
            "mint_failure_reason": reason,
            "mint_status": "PASS" if reason is None and mint_valid else "FAIL",
            "token_program_status": program_status,
            "safety_status": "PASS" if authority_safe else "FAIL",
        },
    }


class CandidateAcquisitionOneShotTransport(Protocol):
    def http_json(self, *, url: str, headers: Mapping[str, str], timeout_seconds: float,
                  byte_ceiling: int, endpoint_role: str) -> TransportResponse: ...
    def rpc_json(self, *, rpc_url: str, method: str, params: Sequence[Any],
                 timeout_seconds: float, byte_ceiling: int,
                 endpoint_role: str) -> TransportResponse: ...


class UrllibCandidateAcquisitionOneShotTransport:
    """One socket/response per call, finite read, no retry or endpoint rotation."""

    @staticmethod
    def _read(request: url_request.Request, *, timeout_seconds: float,
              byte_ceiling: int, endpoint_role: str,
              operation_kind: str) -> tuple[Any, int]:
        try:
            with url_request.urlopen(request, timeout=timeout_seconds) as response:
                raw = response.read(byte_ceiling + 1)
        except url_error.HTTPError as exc:
            code = int(exc.code)
            try:
                raw = exc.read(byte_ceiling + 1)
            except OSError:
                raw = b""
            finally:
                exc.close()
            category = "SOURCE_AUTH_UNAVAILABLE" if code in {401, 403} else (
                "SOURCE_BUDGET_OR_RATE_LIMIT" if code == 429 else "SOURCE_PROVIDER_FAILURE"
            )
            if len(raw) > byte_ceiling:
                category = "RESPONSE_BYTE_CEILING"
            raise LiveAcquisitionTransportError(
                category, endpoint_role, bytes_used=len(raw),
                operation_kind=operation_kind,
            ) from None
        except (url_error.URLError, TimeoutError, OSError) as exc:
            reason = getattr(exc, "reason", None)
            category = "SOURCE_TIMEOUT" if (
                isinstance(exc, TimeoutError) or isinstance(reason, TimeoutError)
            ) else "SOURCE_TRANSPORT_FAILURE"
            raise LiveAcquisitionTransportError(
                category, endpoint_role, operation_kind=operation_kind
            ) from None
        if len(raw) > byte_ceiling:
            raise LiveAcquisitionTransportError(
                "RESPONSE_BYTE_CEILING", endpoint_role, bytes_used=len(raw),
                operation_kind=operation_kind,
            )
        try:
            return json.loads(raw.decode("utf-8")), len(raw)
        except (ValueError, UnicodeDecodeError):
            raise LiveAcquisitionTransportError(
                "SOURCE_MALFORMED", endpoint_role, bytes_used=len(raw),
                operation_kind=operation_kind,
            ) from None

    def http_json(self, *, url: str, headers: Mapping[str, str], timeout_seconds: float,
                  byte_ceiling: int, endpoint_role: str) -> TransportResponse:
        request = url_request.Request(url, headers=dict(headers), method="GET")
        payload, size = self._read(request, timeout_seconds=timeout_seconds,
                                   byte_ceiling=byte_ceiling, endpoint_role=endpoint_role,
                                   operation_kind="HTTP_GET")
        return TransportResponse(payload, size, "HTTP_GET", endpoint_role)

    def rpc_json(self, *, rpc_url: str, method: str, params: Sequence[Any],
                 timeout_seconds: float, byte_ceiling: int,
                 endpoint_role: str) -> TransportResponse:
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                           "params": list(params)}, separators=(",", ":")).encode()
        request = url_request.Request(rpc_url, data=body, headers=dict(RPC_HEADERS), method="POST")
        envelope, size = self._read(request, timeout_seconds=timeout_seconds,
                                    byte_ceiling=byte_ceiling, endpoint_role=endpoint_role,
                                    operation_kind=method)
        if not isinstance(envelope, Mapping) or envelope.get("error") is not None or "result" not in envelope:
            raise LiveAcquisitionTransportError(
                "SOURCE_RPC_ERROR", endpoint_role, bytes_used=size,
                operation_kind=method,
            )
        return TransportResponse(envelope["result"], size, method, endpoint_role)


def load_live_acquisition_configuration(
    environment: Mapping[str, str] | None = None,
) -> LiveAcquisitionConfiguration:
    env = os.environ if environment is None else environment
    raw = str(env.get(RPC_ENVIRONMENT_NAME) or "").strip()
    if not raw:
        raise LiveAcquisitionConfigurationError("ACQUISITION_SOLANA_RPC_URL_REQUIRED")
    try:
        parsed = url_parse.urlsplit(raw)
        port = parsed.port
    except ValueError:
        raise LiveAcquisitionConfigurationError("ACQUISITION_SOLANA_RPC_URL_MALFORMED") from None
    if not parsed.scheme or not parsed.hostname:
        raise LiveAcquisitionConfigurationError("ACQUISITION_SOLANA_RPC_URL_MALFORMED")
    if parsed.scheme.lower() != "https":
        raise LiveAcquisitionConfigurationError("ACQUISITION_SOLANA_RPC_HTTPS_REQUIRED")
    if parsed.username is not None or parsed.password is not None:
        raise LiveAcquisitionConfigurationError("ACQUISITION_SOLANA_RPC_URL_MALFORMED")
    if parsed.fragment or (port is not None and port != 443):
        raise LiveAcquisitionConfigurationError("ACQUISITION_SOLANA_RPC_URL_UNSUPPORTED")
    return LiveAcquisitionConfiguration(rpc_url=raw, redacted_rpc_host=parsed.hostname)


class _OperationAdapter:
    def __init__(self, source_name: str, request_kind: str,
                 execute: Callable[[SourceAdapterContext], NormalizedSourceResult]) -> None:
        self.source_name = source_name
        self.request_kind = request_kind
        self._execute = execute
        self.call_count = 0

    def execute(self, context: SourceAdapterContext) -> NormalizedSourceResult:
        if not context.governor_approved or context.request.source_name != self.source_name \
                or context.request.request_kind != self.request_kind:
            raise PermissionError("LIVE_ACQUISITION_GOVERNOR_CONTEXT_REQUIRED")
        self.call_count += 1
        return self._execute(context)


def _failure(source: str, kind: str, exc: Exception,
             details: Sequence[Mapping[str, Any]] = ()) -> NormalizedSourceResult:
    code = (
        exc.code
        if isinstance(
            exc, (LiveAcquisitionTransportError, LiveAcquisitionValidationError)
        )
        else "SOURCE_TRANSPORT_FAILURE"
    )
    operation_details = [dict(item) for item in details]
    if isinstance(exc, LiveAcquisitionTransportError):
        operation_details.append({"operation_kind": exc.operation_kind,
            "operation_state": "FAILED", "redacted_endpoint_role": exc.endpoint_role,
            "bytes_used": exc.bytes_used})
    return NormalizedSourceResult(
        source_name=source, request_kind=kind, source_status=SourceStatus.FAILED,
        data_quality_label=DataQualityLabel.MISSING_CRITICAL_DATA,
        failure_type=code, failure_message=code,
        normalized_payload=MappingProxyType({
            "underlying_operation_count": len(operation_details),
            "underlying_operations": operation_details,
            "response_bytes": sum(int(item["bytes_used"]) for item in operation_details),
            "declared_operation_ceiling": True,
        }),
    )


def _operation_detail(response: TransportResponse) -> dict[str, Any]:
    return {"operation_kind": response.operation_kind, "operation_state": "COMPLETE",
            "redacted_endpoint_role": response.endpoint_role,
            "bytes_used": response.bytes_used}


def _decorate(result: NormalizedSourceResult, responses: Sequence[TransportResponse],
              extra: Mapping[str, Any] | None = None) -> NormalizedSourceResult:
    payload = dict(result.normalized_payload or {})
    payload.update(extra or {})
    payload["underlying_operation_count"] = len(responses)
    payload["underlying_operations"] = [_operation_detail(item) for item in responses]
    payload["response_bytes"] = sum(item.bytes_used for item in responses)
    return NormalizedSourceResult(
        source_name=result.source_name, request_kind=result.request_kind,
        source_status=result.source_status, data_quality_label=result.data_quality_label,
        normalized_payload=MappingProxyType(payload), status_code=result.status_code,
        failure_type=result.failure_type, failure_message=result.failure_message,
        retry_after_at=result.retry_after_at, received_at=result.received_at,
    )


def _signature_page_request_options(
    *,
    range_mode: str,
    head_signature: str | None,
    previous_page_signature: str | None,
    limit: int,
) -> dict[str, Any]:
    """Build exclusive Solana signature bounds without changing owner identity."""
    options: dict[str, Any] = {
        "limit": int(limit),
        "commitment": "finalized",
    }
    if range_mode == "LIVE_TAIL":
        if head_signature:
            options["until"] = head_signature
        if previous_page_signature:
            options["before"] = previous_page_signature
        return options
    if range_mode == "BACKFILL":
        boundary = previous_page_signature or head_signature
        if not boundary:
            raise LiveAcquisitionConfigurationError(
                "CURSOR_BACKFILL_HEAD_REQUIRED"
            )
        options["before"] = boundary
        return options
    raise LiveAcquisitionConfigurationError("CURSOR_RANGE_MODE_UNSUPPORTED")


class LiveCandidateAcquisitionTransportOwner:
    """Repository-owned finite operation plan shared by N2 and N7."""

    decoupled_candidate_migration_plan = True

    def __init__(self, configuration: LiveAcquisitionConfiguration, *,
                 transport: CandidateAcquisitionOneShotTransport | None = None) -> None:
        self.configuration = configuration
        self.transport = transport or UrllibCandidateAcquisitionOneShotTransport()
        if not callable(getattr(self.transport, "http_json", None)) or not callable(
            getattr(self.transport, "rpc_json", None)
        ):
            raise LiveAcquisitionConfigurationError("ACQUISITION_REQUIRED_TRANSPORT_UNRESOLVED")

    def cursor_namespaces(
        self, *, mode: str, policy: Mapping[str, Any], execution_id: str
    ) -> Sequence[CursorNamespace]:
        del mode, policy, execution_id
        namespaces: tuple[CursorNamespace, ...] = ((
            CURSOR_NETWORK, PUMP_CREATE_INDEX_ADDRESS,
            OFFICIAL_REPOSITORY_COMMIT, CURSOR_DECODER_VERSION,
            LIVE_TAIL_DIRECTION,
        ),)
        if self.configuration.global_pump_observer_enabled:
            namespaces += ((
                CURSOR_NETWORK, PUMP_PROGRAM_ID,
                OFFICIAL_REPOSITORY_COMMIT, CURSOR_DECODER_VERSION,
                LIVE_TAIL_DIRECTION,
            ),)
        return namespaces

    def operations(
        self, *, mode: str, policy: Mapping[str, Any], execution_id: str,
        cursor_heads: Mapping[CursorNamespace, CursorHead | None] | None = None,
    ) -> Sequence[AcquisitionSourceOperation]:
        del mode, execution_id
        namespaces = tuple(
            self.cursor_namespaces(mode="", policy=policy, execution_id="")
        )
        supplied_heads = dict(cursor_heads or {})
        for namespace, head in supplied_heads.items():
            if head is None:
                continue
            if tuple(str(head.get(key) or "") for key in (
                "network", "indexed_address", "contract_pin", "decoder_version",
                "direction",
            )) != namespace:
                raise LiveAcquisitionConfigurationError(
                    "CURSOR_NAMESPACE_MISMATCH"
                )
        heads = {namespace: supplied_heads.get(namespace) for namespace in namespaces}
        cap = int(policy["candidate_limit"])
        timeout = self.configuration.timeout_seconds
        byte_cap = self.configuration.per_response_byte_ceiling
        transport = self.transport
        state: dict[str, Any] = {
            "origins": {}, "migrations": {}, "mint_safety": {},
            "pair_results": {},
            "curve_accounts": {}, "pumpswap_present_pools": {},
            "generic_present_pools": {}, "branch_decisions": {},
            "migration_locators": {}, "candidate_migration_failures": {},
            "create_rows": [], "migration_rows": [],
            "create_exhausted": False, "migration_exhausted": False,
        }

        def remember_pairs(source: str, result: NormalizedSourceResult) -> None:
            state["pair_results"][source] = result

        def _pair_identity(pair: Mapping[str, Any]) -> tuple[str, str]:
            # Aggregator normalizers differ: DexScreener emits token_mint/
            # pair_address; GeckoTerminal emits baseToken.address/pairAddress.
            mint = str(
                pair.get("candidate_mint")
                or pair.get("token_mint")
                or (pair.get("baseToken") or {}).get("address")
                or ""
            )
            pool = str(pair.get("pair_address") or pair.get("pairAddress") or "")
            return mint, pool

        def _pair_orientation(pair: Mapping[str, Any]) -> tuple[str, str, str]:
            base = str(
                pair.get("base_mint")
                or pair.get("baseMint")
                or (pair.get("baseToken") or {}).get("address")
                or pair.get("token_mint")
                or ""
            )
            quote = str(
                pair.get("quote_mint")
                or pair.get("quoteMint")
                or (pair.get("quoteToken") or {}).get("address")
                or ""
            )
            venue = str(
                pair.get("dex_id") or pair.get("dexId") or pair.get("dex") or ""
            )
            return base, quote, venue

        def source_best_pairs(source: str) -> dict[str, dict[str, Any]]:
            """One best (deterministic) pair per mint that a single source nominated."""
            result = state["pair_results"].get(source)
            best: dict[str, dict[str, Any]] = {}
            for pair in (getattr(result, "normalized_payload", None) or {}).get("pairs") or []:
                if not isinstance(pair, Mapping):
                    continue
                mint, pool = _pair_identity(pair)
                if not (mint and pool):
                    continue
                if mint not in best or pool < _pair_identity(best[mint])[1]:
                    best[mint] = dict(pair)
            return best

        def aggregator_pairs() -> dict[str, dict[str, Any]]:
            """Deduplicated best pair per mint across every aggregator nomination."""
            merged: dict[str, dict[str, Any]] = {}
            for source in sorted(state["pair_results"]):
                for mint, pair in source_best_pairs(source).items():
                    if mint not in merged or _pair_identity(pair)[1] < _pair_identity(merged[mint])[1]:
                        merged[mint] = pair
            return merged

        def cohort_mints() -> list[str]:
            """The deterministic source-neutral cohort bounded by acquisition capacity M.

            The cohort is the M lexicographically-smallest identities of the
            complete nomination union (aggregator pairs plus direct Pump create
            and migration identities). It is a pure function of the nominated
            identity set, so provider execution order cannot change membership,
            and it is never a source quota, preference, score, or rank.
            """
            universe = (
                set(aggregator_pairs())
                | set(state["origins"])
                | set(state["migrations"])
            )
            return sorted(universe)[:cap]

        def nomination_result(
            result: NormalizedSourceResult, responses: Sequence[TransportResponse],
        ) -> NormalizedSourceResult:
            if result.source_status != SourceStatus.COMPLETE:
                return _decorate(result, responses, {"declared_operation_ceiling": True})
            empty = NormalizedSourceResult(
                source_name=result.source_name,
                request_kind="candidate_nomination",
                source_status=result.source_status,
                data_quality_label=result.data_quality_label,
                normalized_payload=MappingProxyType({"candidate_observations": []}),
                status_code=result.status_code,
            )
            return _decorate(empty, responses, {"declared_operation_ceiling": True})

        def market_materialization(source: str) -> NormalizedSourceResult:
            result = state["pair_results"].get(source)
            if not isinstance(result, NormalizedSourceResult):
                return _failure(source, "candidate_market_batch", RuntimeError("SOURCE_UNAVAILABLE"))
            # Nomination emission: every mint this aggregator nominated, one best
            # pair each, uncapped. The integration owner selects the M-bounded
            # cohort from the complete cross-source nomination union; the transport
            # never pre-truncates one aggregator ahead of the Pump nominations.
            pairs = [source_best_pairs(source)[mint] for mint in sorted(source_best_pairs(source))]
            materialized = NormalizedSourceResult(
                source_name=source,
                request_kind="candidate_market_batch",
                source_status=result.source_status,
                data_quality_label=result.data_quality_label,
                normalized_payload=MappingProxyType({"pairs": pairs}),
                status_code=result.status_code,
                failure_type=result.failure_type,
                failure_message=result.failure_message,
                retry_after_at=result.retry_after_at,
                received_at=result.received_at,
            )
            return _decorate(materialized, ())

        def dex(_context: SourceAdapterContext) -> NormalizedSourceResult:
            responses: list[TransportResponse] = []
            try:
                profiles = transport.http_json(url=DEXSCREENER_TOKEN_PROFILES_URL,
                    headers=DEXSCREENER_HEADERS, timeout_seconds=timeout,
                    byte_ceiling=byte_cap, endpoint_role="DEXSCREENER_PROFILES")
                responses.append(profiles)
                if not isinstance(profiles.payload, list):
                    raise LiveAcquisitionValidationError(
                        "SOURCE_MALFORMED", "DEXSCREENER_PROFILES"
                    )
                mints: list[str] = []
                for item in profiles.payload:
                    if isinstance(item, Mapping) and item.get("chainId") == "solana":
                        mint = str(item.get("tokenAddress") or "")
                        if mint and mint not in mints:
                            mints.append(mint)
                        if len(mints) >= DEXSCREENER_BATCH_ADDRESS_LIMIT:
                            break
                if not mints:
                    raw: Any = []
                else:
                    batch = transport.http_json(
                        url=DEXSCREENER_TOKENS_BATCH_URL_TEMPLATE.format(addresses=",".join(mints)),
                        headers=DEXSCREENER_HEADERS, timeout_seconds=timeout,
                        byte_ceiling=byte_cap, endpoint_role="DEXSCREENER_MARKET_BATCH")
                    responses.append(batch); raw = batch.payload
                result = normalize_dexscreener_fixture_result(
                    {"pairs": raw}, request_kind="candidate_nomination",
                    requested_token_mints=mints,
                )
                # Bind each returned pair back to the explicitly requested
                # profile mint.  DexScreener's token batch may return a target
                # on either side of the pair; retaining that target is what
                # lets the pool gate reject a quote-side reversal precisely
                # instead of silently nominating the unrelated base asset.
                bound_pairs: list[dict[str, Any]] = []
                requested = set(mints)
                for pair in (result.normalized_payload or {}).get("pairs") or []:
                    if not isinstance(pair, Mapping):
                        continue
                    item = dict(pair)
                    base, quote, _venue = _pair_orientation(item)
                    target = base if base in requested else quote if quote in requested else ""
                    if not target:
                        continue
                    item["candidate_mint"] = target
                    item["candidate_pair_orientation_status"] = (
                        "PASS" if target == base else "FAIL"
                    )
                    item["candidate_pair_orientation_reason"] = (
                        None if target == base else "BASE_QUOTE_ORIENTATION_MISMATCH"
                    )
                    bound_pairs.append(item)
                result = NormalizedSourceResult(
                    source_name=result.source_name,
                    request_kind=result.request_kind,
                    source_status=result.source_status,
                    data_quality_label=result.data_quality_label,
                    normalized_payload=MappingProxyType({"pairs": bound_pairs}),
                    status_code=result.status_code,
                    failure_type=result.failure_type,
                    failure_message=result.failure_message,
                    retry_after_at=result.retry_after_at,
                    received_at=result.received_at,
                )
                remember_pairs("dexscreener", result)
                return nomination_result(result, responses)
            except Exception as exc:
                return _failure("dexscreener", "candidate_nomination", exc, [_operation_detail(x) for x in responses])

        def gecko(_context: SourceAdapterContext) -> NormalizedSourceResult:
            responses: list[TransportResponse] = []
            try:
                response = transport.http_json(url=GECKOTERMINAL_NEW_POOLS_URL,
                    headers=GECKOTERMINAL_HEADERS, timeout_seconds=timeout,
                    byte_ceiling=byte_cap, endpoint_role="GECKOTERMINAL_NEW_POOLS")
                responses.append(response)
                result = normalize_geckoterminal_payload(
                    response.payload if isinstance(response.payload, Mapping) else {},
                    request_kind="candidate_nomination")
                remember_pairs("geckoterminal", result)
                return nomination_result(result, responses)
            except Exception as exc:
                return _failure("geckoterminal", "candidate_nomination", exc, [_operation_detail(x) for x in responses])

        def complete(kind: str, observations: Sequence[Mapping[str, Any]],
                     responses: Sequence[TransportResponse], *,
                     cursor_range: Mapping[str, Any] | None = None,
                     extra: Mapping[str, Any] | None = None) -> NormalizedSourceResult:
            result = NormalizedSourceResult(
                source_name="solana_rpc", request_kind=kind,
                source_status=SourceStatus.COMPLETE,
                data_quality_label=DataQualityLabel.CLEAN_DATA,
                normalized_payload=MappingProxyType({"candidate_observations": list(observations)}),
            )
            return _decorate(result, responses, {
                "declared_operation_ceiling": True,
                **({"cursor_range": dict(cursor_range)} if cursor_range else {}),
                **dict(extra or {}),
            })

        def rpc_call(method: str, params: Sequence[Any], role: str) -> TransportResponse:
            return transport.rpc_json(rpc_url=self.configuration.rpc_url, method=method,
                params=params, timeout_seconds=timeout, byte_ceiling=byte_cap,
                endpoint_role=role)

        def rpc_failure(kind: str, exc: Exception,
                        responses: Sequence[TransportResponse]) -> NormalizedSourceResult:
            return _failure("solana_rpc", kind, exc, [_operation_detail(x) for x in responses])

        def live_cursor(namespace: CursorNamespace) -> dict[str, Any]:
            head = heads[namespace]
            start_slot = None if head is None else int(head["boundary_slot"])
            start_signature = (
                None if head is None else str(head["boundary_signature"])
            )
            return {
                "indexed_address": namespace[1],
                "contract_pin": namespace[2],
                "decoder_version": namespace[3],
                "direction": namespace[4],
                "range_mode": "LIVE_TAIL",
                "rpc_order": "NEWEST_TO_OLDEST",
                "rpc_before_exclusive": True,
                "rpc_until_exclusive": True,
                "bootstrap_contract": (
                    "EXPLICIT_TIP_BOOTSTRAP" if head is None else "ESTABLISHED_HEAD"
                ),
                "start_slot": start_slot,
                "start_signature": start_signature,
                "end_slot": start_slot,
                "end_signature": start_signature,
                "continuity_state": "UNKNOWN",
                "cursor_advanced": False,
                "unresolved_reason": "NOT_EXECUTED",
                "prior_boundary_verified": False,
            }

        create_cursor = live_cursor(namespaces[0])
        migration_cursor = (
            live_cursor(namespaces[1]) if len(namespaces) > 1 else None
        )

        def signature_page(
            kind: str, *, indexed_address: str, page_index: int, page_limit: int,
            transaction_limit: int, cursor: dict[str, Any], role_prefix: str,
            rows_key: str, exhausted_key: str,
        ) -> NormalizedSourceResult:
            responses: list[TransportResponse] = []
            try:
                rows: list[Mapping[str, Any]] = state[rows_key]
                if state[exhausted_key]:
                    return complete(kind, (), (), cursor_range=cursor)
                established = cursor.get("bootstrap_contract") == "ESTABLISHED_HEAD"
                if page_index == 0 and established:
                    prior_signature = str(cursor["start_signature"])
                    verification = rpc_call(
                        "getTransaction",
                        [prior_signature, {
                            "encoding": "json", "commitment": "finalized",
                            "maxSupportedTransactionVersion": 0,
                        }],
                        f"{role_prefix}_PRIOR_BOUNDARY",
                    )
                    responses.append(verification)
                    if not isinstance(verification.payload, Mapping):
                        raise LiveAcquisitionValidationError(
                            "CURSOR_PRIOR_BOUNDARY_UNREACHABLE",
                            f"{role_prefix}_PRIOR_BOUNDARY",
                        )
                    cursor["prior_boundary_verified"] = True
                remaining = max(transaction_limit - len(rows), 1)
                pages_remaining = max(page_limit - page_index, 1)
                page_size = max(1, (remaining + pages_remaining - 1) // pages_remaining)
                previous_signature = (
                    str(rows[-1].get("signature") or "") if rows else None
                )
                options = _signature_page_request_options(
                    range_mode="LIVE_TAIL",
                    head_signature=(
                        str(cursor["start_signature"]) if established else None
                    ),
                    previous_page_signature=previous_signature,
                    limit=page_size,
                )
                response = rpc_call(
                    "getSignaturesForAddress", [indexed_address, options],
                    f"{role_prefix}_SIGNATURE_PAGE_{page_index + 1}",
                )
                responses.append(response)
                if not isinstance(response.payload, list) or any(
                    not isinstance(item, Mapping) for item in response.payload
                ):
                    raise LiveAcquisitionValidationError(
                        "SOURCE_MALFORMED", response.endpoint_role
                    )
                page_rows = list(response.payload)
                prior_signatures = {
                    str(row.get("signature")) for row in rows
                    if row.get("signature")
                }
                previous_slot = (
                    int(rows[-1]["slot"]) if rows else None
                )
                for row in page_rows:
                    signature = row.get("signature")
                    slot = row.get("slot")
                    if (
                        not isinstance(signature, str)
                        or not signature
                        or type(slot) is not int
                        or slot < 0
                    ):
                        raise LiveAcquisitionValidationError(
                            "SOURCE_MALFORMED", response.endpoint_role
                        )
                    if signature in prior_signatures:
                        raise LiveAcquisitionValidationError(
                            "CURSOR_DUPLICATE_SIGNATURE", response.endpoint_role
                        )
                    if previous_slot is not None and slot > previous_slot:
                        raise LiveAcquisitionValidationError(
                            "CURSOR_PAGE_ORDER_INVALID", response.endpoint_role
                        )
                    if established and slot < int(cursor["start_slot"]):
                        raise LiveAcquisitionValidationError(
                            "CURSOR_PRIOR_BOUNDARY_UNREACHABLE",
                            response.endpoint_role,
                        )
                    prior_signatures.add(signature)
                    previous_slot = slot
                rows.extend(page_rows)
                if not established:
                    # Bootstrap anchors the current tip only. It makes no claim
                    # that older history was consumed; BACKFILL owns that range.
                    state[exhausted_key] = True
                else:
                    state[exhausted_key] = len(page_rows) < page_size
                eligible_rows = [
                    row for row in rows
                    if row.get("err") is None
                    and str(row.get("confirmationStatus") or "") == "finalized"
                    and row.get("signature")
                ]
                terminal_page = state[exhausted_key] or page_index + 1 == page_limit
                page_ceiling_gap = (
                    established
                    and page_index + 1 == page_limit
                    and not state[exhausted_key]
                )
                continuity = (
                    "GAPPED" if page_ceiling_gap
                    else "CONTIGUOUS" if terminal_page else "UNKNOWN"
                )
                newest = rows[0] if rows else None
                end_slot = (
                    int(newest["slot"]) if newest is not None
                    else cursor.get("start_slot")
                )
                end_signature = (
                    str(newest["signature"]) if newest is not None
                    else cursor.get("start_signature")
                )
                advanced = bool(
                    continuity == "CONTIGUOUS"
                    and end_signature
                    and (
                        cursor.get("start_signature") is None
                        or end_signature != cursor.get("start_signature")
                    )
                )
                cursor.update({
                    "end_slot": end_slot,
                    "end_signature": end_signature,
                    "continuity_state": continuity,
                    "cursor_advanced": advanced,
                    "unresolved_reason": (
                        "BOOTSTRAP_EMPTY_NO_HEAD"
                        if continuity == "CONTIGUOUS" and end_signature is None
                        else None if continuity == "CONTIGUOUS"
                        else "LIVE_TAIL_PAGE_CEILING_BEFORE_BOUNDARY"
                        if continuity == "GAPPED"
                        else "NEXT_DECLARED_PAGE_PENDING"
                    ),
                })
                page_summary = {
                    "summary_version": "candidate-signature-page-summary-v1",
                    "network": CURSOR_NETWORK,
                    "indexed_address": indexed_address,
                    "locator_kind": (
                        "GLOBAL_PUMP_PROGRAM"
                        if indexed_address == PUMP_PROGRAM_ID
                        else "PUMP_CREATE_INDEX"
                    ),
                    "contract_pin": OFFICIAL_REPOSITORY_COMMIT,
                    "decoder_version": CURSOR_DECODER_VERSION,
                    "commitment": "finalized",
                    "page_ordinal": page_index + 1,
                    "requested_limit": page_size,
                    "returned_count": len(page_rows),
                    "eligible_count": len([
                        row for row in page_rows
                        if row.get("err") is None
                        and str(row.get("confirmationStatus") or "") == "finalized"
                    ]),
                    "failed_or_unfinalized_count": len(page_rows) - len([
                        row for row in page_rows
                        if row.get("err") is None
                        and str(row.get("confirmationStatus") or "") == "finalized"
                    ]),
                    "first_slot": (
                        int(page_rows[0]["slot"]) if page_rows else None
                    ),
                    "last_slot": (
                        int(page_rows[-1]["slot"]) if page_rows else None
                    ),
                    "first_signature": (
                        str(page_rows[0]["signature"]) if page_rows else None
                    ),
                    "last_signature": (
                        str(page_rows[-1]["signature"]) if page_rows else None
                    ),
                    "page_hash": hashlib.sha256(
                        json.dumps(
                            page_rows, sort_keys=True, separators=(",", ":")
                        ).encode("utf-8")
                    ).hexdigest(),
                    "continuity_state": continuity,
                    "positive_matching_signatures": [],
                    "raw_signature_rows_persisted": False,
                }
                return complete(
                    kind, (), responses, cursor_range=cursor,
                    extra={"page_summary": page_summary},
                )
            except Exception as exc:
                cursor.update({"continuity_state": "GAPPED", "cursor_advanced": False,
                               "unresolved_reason": getattr(exc, "code", "SOURCE_FAILURE")})
                return rpc_failure(kind, exc, responses)

        def indexed_transaction(
            kind: str, *, transaction_index: int, rows_key: str,
            cursor: dict[str, Any],
            decoder: Callable[[Mapping[str, Any] | None], Mapping[str, Any]],
            role_prefix: str,
        ) -> NormalizedSourceResult:
            responses: list[TransportResponse] = []
            try:
                eligible_rows = [
                    row for row in state[rows_key]
                    if row.get("err") is None
                    and str(row.get("confirmationStatus") or "") == "finalized"
                    and row.get("signature")
                ]
                if transaction_index >= len(eligible_rows):
                    return complete(kind, (), (), cursor_range=cursor)
                signature = str(eligible_rows[transaction_index]["signature"])
                response = rpc_call(
                    "getTransaction",
                    [signature, {"encoding": "json", "commitment": "finalized",
                                 "maxSupportedTransactionVersion": 0}],
                    f"{role_prefix}_TRANSACTION_{transaction_index + 1}",
                )
                responses.append(response)
                if not isinstance(response.payload, Mapping):
                    raise LiveAcquisitionValidationError(
                        "PUMP_TRANSACTION_NULL_OR_PRUNED",
                        response.endpoint_role,
                    )
                decoded = dict(decoder(
                    response.payload
                ))
                if not decoded.get("supported"):
                    raise LiveAcquisitionValidationError(
                        "UNSUPPORTED_PUMP_CONTRACT", response.endpoint_role
                    )
                mint = str(decoded["mint"])
                observations: list[dict[str, Any]] = []
                if kind == "pumpfun_create_index_transaction":
                    state["origins"][mint] = {**decoded, "signature": signature}
                    observations.append({
                        "mint": mint, "base_mint": mint,
                        "lineage_claim": "PUMP_ORIGIN_CONFIRMED",
                        "facts": {"pump_origin_signature": signature,
                                  "pump_origin_contract_hash": PUMP_IDL_SHA256},
                    })
                else:
                    state["migrations"][mint] = {
                        **decoded, "signature": signature, "tx_result": response.payload,
                    }
                    observations.append({
                        "mint": mint,
                        "base_mint": mint,
                        "lineage_claim": "UNKNOWN_ORIGIN",
                        "facts": {
                            "pump_migration_branch": PUMP_GRADUATION_CLAIMED,
                            "pump_migration_branch_reason": (
                                "OPTIONAL_GLOBAL_EXACT_MIGRATE_LOCATOR"
                            ),
                            "global_pump_observer_locator_only": True,
                            "global_pump_observer_admission_authority": "NONE",
                            "candidate_migration_locator_kind": MIGRATION_SIGNATURE,
                            "candidate_migration_locator_target": signature,
                            "candidate_migration_locator_mint": mint,
                            "candidate_migration_locator_pool": decoded["pool_address"],
                            "candidate_migration_locator_curve": decoded["accounts"][3],
                            "candidate_migration_raw_transaction_persisted": False,
                        },
                    })
                return complete(kind, observations, responses, cursor_range=cursor)
            except Exception as exc:
                return rpc_failure(kind, exc, responses)

        def mint_batch(_context: SourceAdapterContext) -> NormalizedSourceResult:
            responses: list[TransportResponse] = []
            try:
                mints = cohort_mints()
                if not mints:
                    return complete("candidate_mint_account_batch", (), ())
                response = rpc_call("getMultipleAccounts", [mints, {"encoding": "base64",
                    "commitment": "finalized"}], "CANDIDATE_MINT_ACCOUNT_BATCH")
                responses.append(response)
                values = (response.payload or {}).get("value") if isinstance(response.payload, Mapping) else None
                if not isinstance(values, list) or len(values) != len(mints):
                    raise LiveAcquisitionValidationError(
                        "SOURCE_MALFORMED", response.endpoint_role
                    )
                observations = [
                    _mint_account_observation(
                        requested_mint=mint,
                        response_slot=slot,
                        response_address=response_address,
                        account=account,
                        association_mode=association_mode,
                        association_failure=association_failure,
                    )
                    for (
                        mint, slot, response_address, account, association_mode,
                        association_failure,
                    ) in _batch_account_associations(mints, values)
                ]
                for observation in observations:
                    state["mint_safety"][str(observation["mint"])] = (
                        observation["facts"]["safety_status"] == "PASS"
                    )
                return complete("candidate_mint_account_batch", observations, responses)
            except Exception as exc:
                return rpc_failure("candidate_mint_account_batch", exc, responses)

        def pool_batch(_context: SourceAdapterContext) -> NormalizedSourceResult:
            responses: list[TransportResponse] = []
            try:
                cohort = set(cohort_mints())
                aggregated = aggregator_pairs()
                target_contexts: dict[str, list[dict[str, Any]]] = {}

                def add_target(pool: str, context: Mapping[str, Any]) -> None:
                    if pool:
                        target_contexts.setdefault(pool, []).append(dict(context))

                for mint in sorted(cohort):
                    pair = aggregated.get(mint)
                    if pair is not None:
                        _base, _quote, _venue = _pair_orientation(pair)
                        add_target(_pair_identity(pair)[1], {
                            "mint": mint,
                            "kind": "AGGREGATOR_PRESENT_POOL",
                            "base_mint": _base,
                            "quote_mint": _quote,
                            "venue": _venue,
                        })
                    origin = state["origins"].get(mint)
                    # A migrated mint's current pool is the exact joined
                    # PumpSwap pool.  Its historical bonding curve remains
                    # lineage evidence and must not compete as a second
                    # present-pool identity.
                    if origin is not None and mint not in state["migrations"]:
                        add_target(str(origin.get("bonding_curve") or ""), {
                            "mint": mint,
                            "kind": "PUMP_BONDING_CURVE",
                            "origin": origin,
                        })
                pools = sorted(target_contexts)[: cap * 2]
                if not pools:
                    return complete("pumpswap_pool_account_batch", (), ())
                response = rpc_call("getMultipleAccounts", [pools, {"encoding": "base64",
                    "commitment": "finalized"}], "PUMPSWAP_POOL_ACCOUNT_BATCH")
                responses.append(response)
                values = (response.payload or {}).get("value") if isinstance(response.payload, Mapping) else None
                if not isinstance(values, list) or len(values) != len(pools):
                    raise LiveAcquisitionValidationError(
                        "SOURCE_MALFORMED", response.endpoint_role
                    )
                associations = _batch_pool_account_associations(pools, values)
                account_infos = {
                    pool: associations[pool][2]
                    for pool in pools
                }

                # A generic present-pool relationship is accepted only when the
                # provider supplied exact base/quote orientation and the exact
                # on-chain owner is itself an executable program.  This proves a
                # present program-owned pool role without guessing a program
                # layout or promoting the provider venue label to authority.
                generic_owner_ids = sorted({
                    str(account.get("owner") or "")
                    for pool, account in account_infos.items()
                    if isinstance(account, Mapping)
                    and str(account.get("owner") or "")
                    not in {
                        "", PUMP_PROGRAM_ID, PUMPSWAP_AMM_PROGRAM_ID,
                        TOKEN_PROGRAM_ID, TOKEN_2022_PROGRAM_ID,
                        SYSTEM_PROGRAM_ID,
                    }
                })
                owner_programs: dict[str, Any] = {}
                if generic_owner_ids:
                    owner_response = rpc_call(
                        "getMultipleAccounts",
                        [generic_owner_ids, {"encoding": "base64", "commitment": "finalized"}],
                        "POOL_OWNER_PROGRAM_ACCOUNT_BATCH",
                    )
                    responses.append(owner_response)
                    owner_values = (
                        (owner_response.payload or {}).get("value")
                        if isinstance(owner_response.payload, Mapping) else None
                    )
                    if not isinstance(owner_values, list) or len(owner_values) != len(generic_owner_ids):
                        raise LiveAcquisitionValidationError(
                            "SOURCE_MALFORMED", owner_response.endpoint_role
                        )
                    owner_programs = dict(zip(generic_owner_ids, owner_values, strict=True))

                observations: list[dict[str, Any]] = []
                for pool in pools:
                    response_slot, response_address, account, association_mode, association_failure = (
                        associations[pool]
                    )
                    owner = (
                        str(account.get("owner") or "")
                        if isinstance(account, Mapping) else ""
                    )
                    association_facts = {
                        "pool_evidence_target": pool,
                        "pool_response_slot": response_slot,
                        "pool_response_address": response_address,
                        "pool_response_association": association_mode,
                    }
                    contexts = target_contexts[pool]
                    if association_failure is not None:
                        for context in contexts:
                            observations.append({
                                "mint": str(context["mint"]),
                                "lineage_claim": "UNKNOWN_ORIGIN",
                                "facts": {
                                    "pool_status": "FAIL",
                                    "pool_failure_reason": association_failure,
                                    "pool_evidence_target": pool,
                                    "pool_response_slot": response_slot,
                                    "pool_response_address": response_address,
                                    "pool_response_association": association_mode,
                                },
                            })
                        continue
                    if len({str(item["mint"]) for item in contexts}) > 1:
                        for context in contexts:
                            observations.append({
                                "mint": str(context["mint"]),
                                "lineage_claim": "UNKNOWN_ORIGIN",
                                "facts": {
                                    "pool_status": "FAIL",
                                    "pool_failure_reason": "POOL_TARGET_MINT_CONFLICT",
                                    **association_facts,
                                },
                            })
                        continue
                    mint = str(contexts[0]["mint"])
                    bonding_context = next(
                        (item for item in contexts if item["kind"] == "PUMP_BONDING_CURVE"),
                        None,
                    )
                    aggregator_context = next(
                        (item for item in contexts if item["kind"] == "AGGREGATOR_PRESENT_POOL"),
                        None,
                    )

                    if bonding_context is not None:
                        origin = bonding_context["origin"]
                        decoded_curve = decode_pump_bonding_curve_account(
                            account if isinstance(account, Mapping) else None,
                            bonding_curve_address=pool,
                            expected_mint=mint,
                        )
                        if decoded_curve.get("decoded"):
                            state["curve_accounts"][mint] = dict(decoded_curve)
                            if decoded_curve.get("complete") is True:
                                continue
                            observations.append({
                                "mint": mint, "pool": pool,
                                "pool_program_id": PUMP_PROGRAM_ID,
                                "base_mint": mint,
                                "quote_mint": decoded_curve.get("quote_mint"),
                                "venue_label": "PUMP_BONDING_CURVE",
                                "lineage_claim": "PUMP_ORIGIN_CONFIRMED",
                                "facts": {
                                    "pool_status": "PASS",
                                    "pool_role": "PUMP_BONDING_CURVE",
                                    "pool_role_status": "PASS",
                                    **association_facts,
                                    "pump_origin_signature": origin.get("signature"),
                                    "pump_origin_contract_hash": PUMP_IDL_SHA256,
                                    "pump_bonding_curve_address": pool,
                                    "pump_bonding_curve_account_hash": decoded_curve.get("account_hash"),
                                    "pump_bonding_curve_contract_hash": decoded_curve.get("contract_hash"),
                                    "pump_bonding_curve_complete": decoded_curve.get("complete"),
                                },
                            })
                            continue

                    decoded_pool = decode_pumpswap_pool_account(
                        account if isinstance(account, Mapping) else None,
                        pool_address=pool,
                    )
                    if (
                        decoded_pool.get("decoded")
                        and decoded_pool.get("base_mint") == mint
                        and decoded_pool.get("quote_mint") == WSOL_MINT
                    ):
                        state["pumpswap_present_pools"][mint] = {
                            "pool": pool,
                            "decoded": dict(decoded_pool),
                        }
                        observations.append({
                            "mint": mint, "pool": pool,
                            "pool_program_id": PUMPSWAP_AMM_PROGRAM_ID,
                            "base_mint": str(decoded_pool["base_mint"]),
                            "quote_mint": str(decoded_pool["quote_mint"]),
                            "venue_label": "PUMPSWAP",
                            "lineage_claim": "UNKNOWN_ORIGIN",
                            "facts": {
                                "pool_status": "PASS",
                                "pool_role": "PUMPSWAP_AMM_POOL",
                                "pool_role_status": "PASS",
                                **association_facts,
                            },
                        })
                        continue

                    base = str((aggregator_context or {}).get("base_mint") or "")
                    quote = str((aggregator_context or {}).get("quote_mint") or "")
                    owner_account = owner_programs.get(owner)
                    owner_executable = bool(
                        isinstance(owner_account, Mapping)
                        and owner_account.get("executable") is True
                    )
                    generic_pass = bool(
                        aggregator_context is not None
                        and base == mint
                        and quote in {WSOL_MINT, "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"}
                        and owner_executable
                    )
                    failure_reason = (
                        None if generic_pass
                        else "BASE_QUOTE_ORIENTATION_MISMATCH"
                        if aggregator_context is not None and (base != mint or not quote)
                        else "POOL_PROGRAM_NOT_EXECUTABLE"
                        if owner and not owner_executable
                        else "UNSUPPORTED_POOL_ROLE_OR_PROGRAM"
                    )
                    if generic_pass:
                        state["generic_present_pools"][mint] = {
                            "pool": pool,
                            "pool_program_id": owner,
                            "base_mint": base,
                            "quote_mint": quote,
                        }
                    observations.append({
                        "mint": mint,
                        **({
                            "pool": pool,
                            "pool_program_id": owner,
                            "base_mint": base,
                            "quote_mint": quote,
                            "venue_label": str((aggregator_context or {}).get("venue") or "GENERIC_POOL"),
                        } if generic_pass else {}),
                        "lineage_claim": (
                            "NON_PUMP_POOL_CONFIRMED" if generic_pass else "UNKNOWN_ORIGIN"
                        ),
                        "facts": {
                            "pool_status": "PASS" if generic_pass else "FAIL",
                            "pool_role": "GENERIC_AMM_POOL" if generic_pass else "UNSUPPORTED_POOL_ROLE",
                            "pool_role_status": "PASS" if generic_pass else "FAIL",
                            **association_facts,
                            "pool_owner_program": owner or None,
                            "pool_owner_program_executable": owner_executable,
                            "pool_observed_base_mint": base or None,
                            "pool_observed_quote_mint": quote or None,
                            "pool_failure_reason": failure_reason,
                        },
                    })
                return complete("pumpswap_pool_account_batch", observations, responses)
            except Exception as exc:
                return rpc_failure("pumpswap_pool_account_batch", exc, responses)

        def branch_for_mint(mint: str) -> dict[str, Any]:
            prior = state["branch_decisions"].get(mint)
            if isinstance(prior, Mapping):
                return dict(prior)
            origin = state["origins"].get(mint)
            curve = state["curve_accounts"].get(mint)
            migration = state["migrations"].get(mint)
            pumpswap = state["pumpswap_present_pools"].get(mint)
            generic = state["generic_present_pools"].get(mint)
            decision = classify_candidate_lineage_branch(
                candidate_mint=mint,
                exact_pump_origin=origin,
                verified_bonding_curve=curve,
                exact_migration_signature=(
                    str(migration.get("signature") or "") if migration else None
                ),
                proposed_pumpswap_pool=(
                    str(pumpswap.get("pool") or "") if pumpswap else None
                ),
                current_pool_conflict=bool(
                    pumpswap
                    and generic
                    and str(pumpswap.get("pool")) != str(generic.get("pool"))
                ),
            )
            state["branch_decisions"][mint] = dict(decision)
            return dict(decision)

        def graduation_claim_mints() -> list[str]:
            return [
                mint for mint in cohort_mints()
                if branch_for_mint(mint)["branch"] in {
                    PUMP_GRADUATION_CLAIMED, PUMP_LINEAGE_CONFLICT,
                }
            ]

        def candidate_failure_observation(
            *,
            mint: str,
            branch: str,
            family: str,
            reason: str,
            locator: Mapping[str, Any] | None = None,
        ) -> dict[str, Any]:
            state["candidate_migration_failures"][mint] = {
                "family": family, "reason": reason,
            }
            return {
                "mint": mint,
                "base_mint": mint,
                "lineage_claim": "UNKNOWN_ORIGIN",
                "facts": {
                    "pump_migration_branch": branch,
                    "pump_migration_failure_family": family,
                    "pump_migration_failure_reason": reason,
                    "candidate_migration_fallback_allowed": False,
                    **({
                        "candidate_migration_locator_kind": locator["locator_kind"],
                        "candidate_migration_locator_target": locator["locator_target"],
                        "candidate_migration_finalized_cutoff_slot": (
                            locator["finalized_cutoff_slot"]
                        ),
                    } if locator else {}),
                },
            }

        def candidate_failure_result(
            kind: str,
            *,
            mint: str,
            branch: str,
            family: str,
            reason: str,
            responses: Sequence[TransportResponse],
            locator: Mapping[str, Any] | None = None,
            source_failed: bool = False,
            extra: Mapping[str, Any] | None = None,
            failure_exception: Exception | None = None,
        ) -> NormalizedSourceResult:
            observation = candidate_failure_observation(
                mint=mint, branch=branch, family=family, reason=reason,
                locator=locator,
            )
            if not source_failed:
                return complete(
                    kind, (observation,), responses, extra=extra,
                )
            details = [_operation_detail(item) for item in responses]
            if (
                isinstance(failure_exception, LiveAcquisitionTransportError)
                and not responses
            ):
                details.append({
                    "operation_kind": failure_exception.operation_kind,
                    "operation_state": "FAILED",
                    "redacted_endpoint_role": failure_exception.endpoint_role,
                    "bytes_used": failure_exception.bytes_used,
                })
            result = NormalizedSourceResult(
                source_name="solana_rpc",
                request_kind=kind,
                source_status=SourceStatus.FAILED,
                data_quality_label=DataQualityLabel.MISSING_CRITICAL_DATA,
                failure_type=reason,
                failure_message=reason,
                normalized_payload=MappingProxyType({
                    "candidate_observations": [observation],
                    "underlying_operation_count": len(details),
                    "underlying_operations": details,
                    "response_bytes": sum(
                        int(item["bytes_used"]) for item in details
                    ),
                    "declared_operation_ceiling": True,
                    **dict(extra or {}),
                }),
            )
            return result

        def _candidate_provider_reason(exc: Exception, *, pool: bool = False) -> str:
            code = str(getattr(exc, "code", "") or "")
            if code in {"SOURCE_MALFORMED"}:
                return (
                    "CANDIDATE_POOL_RESPONSE_MALFORMED"
                    if pool else "CANDIDATE_MIGRATION_PAGE_MALFORMED"
                )
            return (
                "CANDIDATE_POOL_PROVIDER_UNAVAILABLE"
                if pool else "CANDIDATE_MIGRATION_PROVIDER_UNAVAILABLE"
            )

        def candidate_migration_lookup(
            _context: SourceAdapterContext, *, candidate_index: int,
        ) -> NormalizedSourceResult:
            kind = "candidate_pump_migration_signature_lookup"
            responses: list[TransportResponse] = []
            mints = graduation_claim_mints()
            if candidate_index >= len(mints):
                return complete(kind, (), ())
            mint = mints[candidate_index]
            decision = branch_for_mint(mint)
            branch = str(decision["branch"])
            if branch in {
                NO_PUMP_GRADUATION_CLAIM, PUMP_ACTIVE_BONDING_CURVE,
            }:
                return complete(kind, (), (), extra={
                    "candidate_branch": decision,
                    "candidate_mint": mint,
                    "underlying_operation_count": 0,
                })
            if branch == PUMP_LINEAGE_CONFLICT:
                return candidate_failure_result(
                    kind, mint=mint, branch=branch,
                    family="IDENTITY_MERGE_FAILURE",
                    reason=str(decision["reason"]), responses=(),
                )
            origin = state["origins"].get(mint) or {}
            migration = state["migrations"].get(mint) or {}
            pumpswap = state["pumpswap_present_pools"].get(mint) or {}
            curve = state["curve_accounts"].get(mint) or {}
            locator = plan_candidate_migration_locator(
                candidate_mint=mint,
                branch=branch,
                finalized_cutoff_slot=0,
                exact_migration_signature=str(
                    migration.get("signature") or ""
                ) or None,
                exact_pumpswap_pool=str(pumpswap.get("pool") or "") or None,
                exact_verified_bonding_curve=str(
                    curve.get("bonding_curve_address")
                    or origin.get("bonding_curve")
                    or ""
                ) or None,
            )
            assert locator is not None
            state["migration_locators"][mint] = dict(locator)
            if locator["locator_kind"] == MIGRATION_SIGNATURE:
                state["migration_locators"][mint]["selected_signature"] = str(
                    locator["locator_target"]
                )
                return complete(kind, (), (), extra={
                    "candidate_branch": decision,
                    "locator_summary": {
                        **locator,
                        "selected_matching_signatures": [
                            str(locator["locator_target"])
                        ],
                        "raw_signature_rows_persisted": False,
                    },
                })
            try:
                response = rpc_call(
                    "getSignaturesForAddress",
                    [str(locator["locator_target"]), {
                        "limit": 1, "commitment": "finalized",
                    }],
                    f"CANDIDATE_MIGRATION_{locator['locator_kind']}_{candidate_index + 1}",
                )
                responses.append(response)
                page = response.payload
                if not isinstance(page, list) or any(
                    not isinstance(row, Mapping) for row in page
                ):
                    raise LiveAcquisitionValidationError(
                        "SOURCE_MALFORMED", response.endpoint_role
                    )
                page_hash = hashlib.sha256(
                    json.dumps(page, sort_keys=True, separators=(",", ":")).encode(
                        "utf-8"
                    )
                ).hexdigest()
                summary = {
                    **locator,
                    "summary_version": "candidate-migration-page-summary-v1",
                    "commitment": "finalized",
                    "requested_limit": 1,
                    "returned_count": len(page),
                    "page_hash": page_hash,
                    "first_slot": (
                        int(page[0]["slot"])
                        if page and type(page[0].get("slot")) is int else None
                    ),
                    "last_slot": (
                        int(page[-1]["slot"])
                        if page and type(page[-1].get("slot")) is int else None
                    ),
                    "raw_signature_rows_persisted": False,
                }
                if not page:
                    return candidate_failure_result(
                        kind, mint=mint, branch=branch,
                        family="COVERAGE_FAILURE",
                        reason="CANDIDATE_MIGRATION_HISTORY_UNAVAILABLE",
                        responses=responses, locator=locator,
                        extra={"page_summary": summary},
                    )
                eligible = [
                    row for row in page
                    if isinstance(row.get("signature"), str)
                    and row.get("signature")
                    and row.get("err") is None
                    and str(row.get("confirmationStatus") or "") == "finalized"
                ]
                if len(eligible) != 1:
                    return candidate_failure_result(
                        kind, mint=mint, branch=branch,
                        family="COVERAGE_FAILURE",
                        reason="CANDIDATE_MIGRATION_NOT_FOUND_WITHIN_BOUND",
                        responses=responses, locator=locator,
                        extra={"page_summary": summary},
                    )
                signature = str(eligible[0]["signature"])
                state["migration_locators"][mint]["selected_signature"] = signature
                summary["selected_matching_signatures"] = [signature]
                return complete(
                    kind, (), responses,
                    extra={"candidate_branch": decision, "page_summary": summary},
                )
            except Exception as exc:
                reason = _candidate_provider_reason(exc)
                family = (
                    "STALE_OR_INCOMPLETE_EVIDENCE"
                    if reason == "CANDIDATE_MIGRATION_PAGE_MALFORMED"
                    else "SOURCE_PROVIDER_FAILURE"
                )
                return candidate_failure_result(
                    kind, mint=mint, branch=branch, family=family,
                    reason=reason, responses=responses, locator=locator,
                    source_failed=True, failure_exception=exc,
                )

        def candidate_migration_transaction(
            _context: SourceAdapterContext, *, candidate_index: int,
        ) -> NormalizedSourceResult:
            kind = "candidate_pump_migration_transaction"
            responses: list[TransportResponse] = []
            mints = graduation_claim_mints()
            if candidate_index >= len(mints):
                return complete(kind, (), ())
            mint = mints[candidate_index]
            decision = branch_for_mint(mint)
            branch = str(decision["branch"])
            locator = state["migration_locators"].get(mint)
            if branch != PUMP_GRADUATION_CLAIMED or not isinstance(locator, Mapping):
                return complete(kind, (), ())
            if mint in state["candidate_migration_failures"]:
                return complete(kind, (), ())
            signature = str(locator.get("selected_signature") or "")
            if not signature:
                return candidate_failure_result(
                    kind, mint=mint, branch=branch,
                    family="STALE_OR_INCOMPLETE_EVIDENCE",
                    reason="CANDIDATE_MIGRATION_SIGNATURE_MISSING",
                    responses=(), locator=locator,
                )
            try:
                response = rpc_call(
                    "getTransaction",
                    [signature, {
                        "encoding": "json", "commitment": "finalized",
                        "maxSupportedTransactionVersion": 0,
                    }],
                    f"CANDIDATE_MIGRATION_TRANSACTION_{candidate_index + 1}",
                )
                responses.append(response)
                if not isinstance(response.payload, Mapping):
                    return candidate_failure_result(
                        kind, mint=mint, branch=branch,
                        family="STALE_OR_INCOMPLETE_EVIDENCE",
                        reason="CANDIDATE_MIGRATION_TRANSACTION_NULL_OR_PRUNED",
                        responses=responses, locator=locator,
                    )
                decoded = dict(
                    decode_supported_pump_migration_transaction(response.payload)
                )
                if not decoded.get("supported"):
                    raw_reason = str(decoded.get("reason") or "")
                    family = (
                        "UNSUPPORTED_CONTRACT"
                        if raw_reason in {
                            "unsupported_transaction_version",
                            "migrate_account_layout_mismatch",
                            "migrate_fixed_account_mismatch",
                        }
                        else "ADMISSION_FAILURE"
                    )
                    reason = {
                        "unsupported_transaction_version": (
                            "CANDIDATE_MIGRATION_UNSUPPORTED_VERSION"
                        ),
                        "migrate_account_layout_mismatch": (
                            "CANDIDATE_MIGRATION_LAYOUT_UNSUPPORTED"
                        ),
                        "migrate_fixed_account_mismatch": (
                            "CANDIDATE_MIGRATION_FIXED_ACCOUNT_MISMATCH"
                        ),
                        "exactly_one_migrate_instruction_required": (
                            "CANDIDATE_MIGRATION_AMBIGUOUS"
                        ),
                        "transaction_failed_or_meta_missing": (
                            "CANDIDATE_MIGRATION_TRANSACTION_FAILED"
                        ),
                        "finalized_slot_or_block_time_missing": (
                            "CANDIDATE_MIGRATION_FINALITY_EVIDENCE_MISSING"
                        ),
                    }.get(raw_reason, "CANDIDATE_MIGRATION_CONTRACT_UNSUPPORTED")
                    return candidate_failure_result(
                        kind, mint=mint, branch=branch, family=family,
                        reason=reason, responses=responses, locator=locator,
                    )
                locator_valid, locator_reason = validate_candidate_migration_locator(
                    locator=locator, decoded_migration=decoded
                )
                if not locator_valid:
                    return candidate_failure_result(
                        kind, mint=mint, branch=branch,
                        family="ADMISSION_FAILURE", reason=locator_reason,
                        responses=responses, locator=locator,
                    )
                state["migrations"][mint] = {
                    **decoded,
                    "signature": signature,
                    "tx_result": response.payload,
                    "locator": dict(locator),
                    "candidate_verified": True,
                }
                return complete(kind, (), responses, extra={
                    "positive_migration_match": {
                        "candidate_mint": mint,
                        "signature": signature,
                        "slot": int(decoded["slot"]),
                        "block_time": int(decoded["block_time"]),
                        "bonding_curve": str(decoded["accounts"][3]),
                        "pool": str(decoded["pool_address"]),
                        "creator": str(decoded["creator"]),
                        "locator_kind": locator["locator_kind"],
                        "locator_target": locator["locator_target"],
                        "pump_contract_hash": PUMP_IDL_SHA256,
                        "raw_transaction_persisted": False,
                    },
                })
            except Exception as exc:
                return candidate_failure_result(
                    kind, mint=mint, branch=branch,
                    family="SOURCE_PROVIDER_FAILURE",
                    reason="CANDIDATE_MIGRATION_PROVIDER_UNAVAILABLE",
                    responses=responses, locator=locator, source_failed=True,
                    failure_exception=exc,
                )

        def candidate_pumpswap_pool_verification(
            _context: SourceAdapterContext,
        ) -> NormalizedSourceResult:
            kind = "candidate_pumpswap_pool_verification"
            responses: list[TransportResponse] = []
            overflow_observations = [
                candidate_failure_observation(
                    mint=mint, branch=PUMP_GRADUATION_CLAIMED,
                    family="BUDGET_EXHAUSTION",
                    reason="CANDIDATE_MIGRATION_PREDECLARED_BUDGET_EXHAUSTED",
                )
                for mint in graduation_claim_mints()
                if mint not in state["migration_locators"]
                and mint not in state["candidate_migration_failures"]
            ]
            candidates = [
                (mint, item)
                for mint, item in sorted(state["migrations"].items())
                if mint in set(cohort_mints())
                and item.get("candidate_verified") is True
                and mint not in state["candidate_migration_failures"]
            ]
            if not candidates:
                return complete(kind, overflow_observations, ())
            pools = [str(item["pool_address"]) for _mint, item in candidates]
            if len(set(pools)) != len(pools):
                observations = [
                    candidate_failure_observation(
                        mint=mint, branch=PUMP_GRADUATION_CLAIMED,
                        family="IDENTITY_MERGE_FAILURE",
                        reason="CANDIDATE_MIGRATION_POOL_IDENTITY_CONFLICT",
                        locator=item.get("locator"),
                    )
                    for mint, item in candidates
                ]
                return complete(kind, observations, ())
            try:
                response = rpc_call(
                    "getMultipleAccounts",
                    [pools, {"encoding": "base64", "commitment": "finalized"}],
                    "CANDIDATE_PUMPSWAP_POOL_VERIFICATION",
                )
                responses.append(response)
                values = (
                    (response.payload or {}).get("value")
                    if isinstance(response.payload, Mapping) else None
                )
                if not isinstance(values, list) or len(values) != len(pools):
                    raise LiveAcquisitionValidationError(
                        "SOURCE_MALFORMED", response.endpoint_role
                    )
                associations = _batch_pool_account_associations(pools, values)
                account_infos = {
                    pool: associations[pool][2] for pool in pools
                }
                observations: list[dict[str, Any]] = list(overflow_observations)
                positives: list[dict[str, Any]] = []
                for mint, item in candidates:
                    pool = str(item["pool_address"])
                    _slot, response_address, account, association, failure = (
                        associations[pool]
                    )
                    if failure is not None:
                        observations.append(candidate_failure_observation(
                            mint=mint, branch=PUMP_GRADUATION_CLAIMED,
                            family="STALE_OR_INCOMPLETE_EVIDENCE",
                            reason=failure, locator=item.get("locator"),
                        ))
                        continue
                    verified = verify_pinned_pump_migration(
                        item["tx_result"], account_infos,
                        expected_mint=mint, finalized=True,
                    )
                    if not verified.get("verified"):
                        raw_reason = str(verified.get("reason") or "")
                        family = (
                            "UNSUPPORTED_CONTRACT"
                            if raw_reason in {
                                "unsupported_pool_account_length",
                                "pool_data_encoding_unsupported",
                                "pool_data_undecodable",
                            }
                            else "ADMISSION_FAILURE"
                        )
                        reason = (
                            "PUMPSWAP_LAYOUT_UNSUPPORTED"
                            if family == "UNSUPPORTED_CONTRACT"
                            else f"CANDIDATE_PUMPSWAP_JOIN_{raw_reason.upper()}"
                        )
                        observations.append(candidate_failure_observation(
                            mint=mint, branch=PUMP_GRADUATION_CLAIMED,
                            family=family, reason=reason,
                            locator=item.get("locator"),
                        ))
                        continue
                    pool_facts = dict(verified["pool"])
                    origin = state["origins"].get(mint) or {}
                    facts = {
                        "pool_status": "PASS",
                        "pool_role": "PUMPSWAP_AMM_POOL",
                        "pool_role_status": "PASS",
                        "pool_evidence_target": pool,
                        "pool_response_address": response_address,
                        "pool_response_association": association,
                        "pump_migration_branch": PUMP_GRADUATION_CLAIMED,
                        "pump_origin_signature": origin.get("signature"),
                        "pump_origin_contract_hash": PUMP_IDL_SHA256,
                        "pump_migration_signature": item["signature"],
                        "pump_migration_contract_hash": PUMP_IDL_SHA256,
                        "pump_migration_slot": verified["migration_slot"],
                        "pump_migration_block_time": verified["migration_block_time"],
                        "pump_migration_bonding_curve": item["accounts"][3],
                        "pump_migration_pool": pool,
                        "pump_migration_creator": verified["creator"],
                        "pumpswap_account_hash": pool_facts["account_hash"],
                        "pumpswap_contract_hash": PUMPSWAP_IDL_SHA256,
                        "pumpswap_index": int(pool_facts["index"]),
                        "pumpswap_base_mint": pool_facts["base_mint"],
                        "pumpswap_quote_mint": pool_facts["quote_mint"],
                        "pumpswap_lp_mint": pool_facts["lp_mint"],
                        "pumpswap_base_vault": pool_facts["pool_base_token_account"],
                        "pumpswap_quote_vault": pool_facts["pool_quote_token_account"],
                        "candidate_migration_locator_kind": item["locator"]["locator_kind"],
                        "candidate_migration_locator_target": item["locator"]["locator_target"],
                        "candidate_migration_fallback_allowed": False,
                    }
                    observations.append({
                        "mint": mint,
                        "pool": pool,
                        "pool_program_id": PUMPSWAP_AMM_PROGRAM_ID,
                        "base_mint": mint,
                        "quote_mint": WSOL_MINT,
                        "token_program_id": TOKEN_PROGRAM_ID,
                        "venue_label": "PUMPSWAP",
                        "lineage_claim": "PUMP_GRADUATION_CONFIRMED",
                        "facts": facts,
                    })
                    positives.append({
                        "candidate_mint": mint,
                        "signature": item["signature"],
                        "pool": pool,
                        "pool_account_hash": pool_facts["account_hash"],
                        "evidence_hash": hashlib.sha256(
                            json.dumps(
                                facts, sort_keys=True, separators=(",", ":")
                            ).encode("utf-8")
                        ).hexdigest(),
                    })
                return complete(
                    kind, observations, responses,
                    extra={"positive_joined_evidence": positives},
                )
            except Exception as exc:
                reason = _candidate_provider_reason(exc, pool=True)
                family = (
                    "STALE_OR_INCOMPLETE_EVIDENCE"
                    if reason == "CANDIDATE_POOL_RESPONSE_MALFORMED"
                    else "SOURCE_PROVIDER_FAILURE"
                )
                observations = [
                    candidate_failure_observation(
                        mint=mint, branch=PUMP_GRADUATION_CLAIMED,
                        family=family, reason=reason,
                        locator=item.get("locator"),
                    )
                    for mint, item in candidates
                ]
                result = NormalizedSourceResult(
                    source_name="solana_rpc", request_kind=kind,
                    source_status=SourceStatus.FAILED,
                    data_quality_label=DataQualityLabel.MISSING_CRITICAL_DATA,
                    failure_type=reason, failure_message=reason,
                    normalized_payload=MappingProxyType({
                        "candidate_observations": observations,
                        "underlying_operation_count": (
                            len(responses)
                            + int(isinstance(exc, LiveAcquisitionTransportError))
                        ),
                        "underlying_operations": [
                            *[_operation_detail(item) for item in responses],
                            *([{
                                "operation_kind": exc.operation_kind,
                                "operation_state": "FAILED",
                                "redacted_endpoint_role": exc.endpoint_role,
                                "bytes_used": exc.bytes_used,
                            }] if isinstance(
                                exc, LiveAcquisitionTransportError
                            ) else []),
                        ],
                        "response_bytes": (
                            sum(item.bytes_used for item in responses)
                            + (
                                exc.bytes_used
                                if isinstance(
                                    exc, LiveAcquisitionTransportError
                                ) else 0
                            )
                        ),
                        "declared_operation_ceiling": True,
                    }),
                )
                return result

        def target_mints() -> list[str]:
            # Candidate-specific enrichment addresses only cohort identities.
            return cohort_mints()

        def holder_reference(
            _context: SourceAdapterContext, *, candidate_index: int,
        ) -> NormalizedSourceResult:
            responses: list[TransportResponse] = []
            try:
                mints = target_mints()
                if candidate_index >= len(mints):
                    return complete("holder_concentration_reference", (), ())
                mint = mints[candidate_index]
                largest = rpc_call(
                    "getTokenLargestAccounts", [mint, {"commitment": "finalized"}],
                    f"HOLDER_LARGEST_ACCOUNTS_{candidate_index + 1}",
                )
                responses.append(largest)
                supply = rpc_call(
                    "getTokenSupply", [mint, {"commitment": "finalized"}],
                    f"HOLDER_TOKEN_SUPPLY_{candidate_index + 1}",
                )
                responses.append(supply)
                result = normalize_solana_rpc_holder_response({
                    "token_mint": mint,
                    # The one-shot RPC transport returns the JSON-RPC result;
                    # the adopted holder normalizer consumes the full envelope.
                    "largest_accounts_result": {"result": largest.payload},
                    "token_supply_result": {"result": supply.payload},
                    "underlying_operation_count": 2,
                }, request_kind="holder_concentration_reference")
                label = str(
                    (result.normalized_payload or {}).get("holder_concentration_label") or ""
                )
                observation = {
                    "mint": mint, "base_mint": mint,
                    "lineage_claim": "UNKNOWN_ORIGIN",
                    "facts": {"holder_status": (
                        "PASS" if label == "HOLDER_CONCENTRATION_HEALTHY" else "FAIL"
                    )},
                }
                return complete("holder_concentration_reference", (observation,), responses)
            except Exception as exc:
                return rpc_failure("holder_concentration_reference", exc, responses)

        def goplus_reference(
            _context: SourceAdapterContext, *, candidate_index: int,
        ) -> NormalizedSourceResult:
            responses: list[TransportResponse] = []
            try:
                mints = target_mints()
                if candidate_index >= len(mints):
                    result = NormalizedSourceResult(
                        source_name="goplus", request_kind="safety_reference",
                        source_status=SourceStatus.COMPLETE,
                        data_quality_label=DataQualityLabel.CLEAN_DATA,
                        normalized_payload=MappingProxyType({"candidate_observations": []}),
                    )
                    return _decorate(result, (), {"declared_operation_ceiling": True})
                mint = mints[candidate_index]
                response = transport.http_json(
                    url=GOPLUS_SOLANA_TOKEN_SECURITY_URL.format(token_mint=mint),
                    headers=PUBLIC_HEADERS, timeout_seconds=timeout,
                    byte_ceiling=byte_cap,
                    endpoint_role=f"GOPLUS_SAFETY_REFERENCE_{candidate_index + 1}",
                )
                responses.append(response)
                payload = dict(response.payload) if isinstance(response.payload, Mapping) else {}
                payload["_requested_token_mint"] = mint
                result = normalize_goplus_payload(payload, request_kind="safety_reference")
                data = dict(result.normalized_payload or {})
                explicit_risk = any(
                    str(data.get(key, "")) in {"1", "true", "True"}
                    for key in ("mintable", "freezable")
                )
                observation = {
                    "mint": mint, "base_mint": mint,
                    "lineage_claim": "UNKNOWN_ORIGIN",
                    # GoPlus absence is optional/unknown; only an explicit
                    # adopted risk fact may turn the categorical gate FAIL.
                    "facts": ({"safety_status": "FAIL"} if explicit_risk else {}),
                }
                result = NormalizedSourceResult(source_name="goplus", request_kind="safety_reference",
                    source_status=SourceStatus.COMPLETE, data_quality_label=DataQualityLabel.CLEAN_DATA,
                    normalized_payload=MappingProxyType({"candidate_observations": [observation]}))
                return _decorate(result, responses, {"declared_operation_ceiling": True})
            except Exception as exc:
                return _failure("goplus", "safety_reference", exc,
                                [_operation_detail(x) for x in responses])

        source_budgets = policy["source_budgets"]["solana_rpc"]
        create_page_count = int(source_budgets["pumpfun_create_index_signature_page"])
        migration_page_count = (
            int(source_budgets["pumpfun_migration_signature_page"])
            if self.configuration.global_pump_observer_enabled else 0
        )
        selection_capacity = int(policy["selection_capacity"])
        # Create discovery remains bounded to N. The optional global observer
        # decodes at most one locator and has no candidate-gating authority.
        create_transaction_count = min(
            int(source_budgets["pumpfun_create_index_transaction"]),
            int(policy["selection_capacity"]),
        )
        global_transaction_count = (
            min(
                int(source_budgets["pumpfun_migration_transaction"]),
                selection_capacity,
            )
            if migration_page_count else 0
        )
        solana_minute = int(
            SOURCE_REGISTRY["solana_rpc"].default_rate_limit_per_minute
        )
        holder_count = cap if selection_capacity == 2 else selection_capacity
        fixed_without_candidate_slots = (
            create_page_count
            + create_transaction_count
            + migration_page_count
            + global_transaction_count
            + 3  # mint batch, present-pool probe, exact PumpSwap verification
            + holder_count
        )
        candidate_verification_count = min(
            cap,
            max(1, selection_capacity - 1),
            max(0, (solana_minute - fixed_without_candidate_slots) // 2),
        )
        if candidate_verification_count < 1:
            raise LiveAcquisitionConfigurationError(
                "CANDIDATE_MIGRATION_VERIFICATION_HEADROOM_UNAVAILABLE"
            )
        operations = [
            AcquisitionSourceOperation("dexscreener", "candidate_nomination",
                _OperationAdapter("dexscreener", "candidate_nomination", dex), required=False,
                expected_transport_operations=2),
            AcquisitionSourceOperation("geckoterminal", "candidate_nomination",
                _OperationAdapter("geckoterminal", "candidate_nomination", gecko), required=False),
            AcquisitionSourceOperation(
                "dexscreener", "candidate_market_batch",
                _OperationAdapter(
                    "dexscreener", "candidate_market_batch",
                    lambda c: market_materialization("dexscreener"),
                ),
                required=False, expected_transport_operations=0,
            ),
            AcquisitionSourceOperation(
                "geckoterminal", "candidate_market_batch",
                _OperationAdapter(
                    "geckoterminal", "candidate_market_batch",
                    lambda c: market_materialization("geckoterminal"),
                ),
                required=False, expected_transport_operations=0,
            ),
        ]
        operations.extend(
            AcquisitionSourceOperation(
                "solana_rpc", "pumpfun_create_index_signature_page",
                _OperationAdapter(
                    "solana_rpc", "pumpfun_create_index_signature_page",
                    lambda c, page_index=page_index: signature_page(
                        "pumpfun_create_index_signature_page",
                        indexed_address=PUMP_CREATE_INDEX_ADDRESS,
                        page_index=page_index, page_limit=create_page_count,
                        transaction_limit=create_transaction_count, cursor=create_cursor,
                        role_prefix="PUMP_CREATE", rows_key="create_rows",
                        exhausted_key="create_exhausted",
                    ),
                ),
                required=page_index + 1 == create_page_count,
                round_mode="LIVE_TAIL",
                expected_transport_operations=(
                    2 if page_index == 0 and heads[namespaces[0]] is not None else 1
                ),
                cursor_range=create_cursor,
            )
            for page_index in range(create_page_count)
        )
        operations.extend(
            AcquisitionSourceOperation(
                "solana_rpc", "pumpfun_create_index_transaction",
                _OperationAdapter(
                    "solana_rpc", "pumpfun_create_index_transaction",
                    lambda c, transaction_index=transaction_index: indexed_transaction(
                        "pumpfun_create_index_transaction",
                        transaction_index=transaction_index, rows_key="create_rows",
                        cursor=create_cursor,
                        decoder=decode_supported_pump_creation_transaction,
                        role_prefix="PUMP_CREATE",
                    ),
                ),
                round_mode="LIVE_TAIL", expected_transport_operations=1,
                cursor_range=create_cursor,
            )
            for transaction_index in range(create_transaction_count)
        )
        if migration_page_count:
            operations.extend(
                AcquisitionSourceOperation(
                    "solana_rpc", "pumpfun_migration_signature_page",
                    _OperationAdapter(
                        "solana_rpc", "pumpfun_migration_signature_page",
                        lambda c, page_index=page_index: signature_page(
                            "pumpfun_migration_signature_page",
                            indexed_address=PUMP_PROGRAM_ID,
                            page_index=page_index, page_limit=migration_page_count,
                            transaction_limit=global_transaction_count,
                            cursor=migration_cursor,
                            role_prefix="PUMP_MIGRATION", rows_key="migration_rows",
                            exhausted_key="migration_exhausted",
                        ),
                    ),
                    required=False,
                    round_mode="LIVE_TAIL",
                    expected_transport_operations=(
                        2 if page_index == 0 and heads[namespaces[1]] is not None else 1
                    ),
                    cursor_range=migration_cursor,
                    observation_scope="GLOBAL_OPTIONAL",
                )
                for page_index in range(migration_page_count)
            )
            operations.extend(
                AcquisitionSourceOperation(
                    "solana_rpc", "pumpfun_migration_transaction",
                    _OperationAdapter(
                        "solana_rpc", "pumpfun_migration_transaction",
                        lambda c, transaction_index=transaction_index: indexed_transaction(
                            "pumpfun_migration_transaction",
                            transaction_index=transaction_index, rows_key="migration_rows",
                            cursor=migration_cursor,
                            decoder=decode_supported_pump_migration_transaction,
                            role_prefix="PUMP_MIGRATION",
                        ),
                    ),
                    required=False,
                    round_mode="LIVE_TAIL", expected_transport_operations=1,
                    cursor_range=migration_cursor,
                    observation_scope="GLOBAL_OPTIONAL",
                )
                for transaction_index in range(global_transaction_count)
            )
        operations.extend((
            AcquisitionSourceOperation(
                "solana_rpc", "candidate_mint_account_batch",
                _OperationAdapter("solana_rpc", "candidate_mint_account_batch", mint_batch),
                phase=PHASE_ENRICHMENT,
            ),
            AcquisitionSourceOperation(
                "solana_rpc", "pumpswap_pool_account_batch",
                _OperationAdapter("solana_rpc", "pumpswap_pool_account_batch", pool_batch),
                phase=PHASE_ENRICHMENT, expected_transport_operations=2,
            ),
        ))
        operations.extend(
            AcquisitionSourceOperation(
                "solana_rpc", "candidate_pump_migration_signature_lookup",
                _OperationAdapter(
                    "solana_rpc", "candidate_pump_migration_signature_lookup",
                    lambda c, candidate_index=candidate_index: candidate_migration_lookup(
                        c, candidate_index=candidate_index
                    ),
                ),
                required=False, phase=PHASE_ENRICHMENT,
                expected_transport_operations=1,
            )
            for candidate_index in range(candidate_verification_count)
        )
        operations.extend(
            AcquisitionSourceOperation(
                "solana_rpc", "candidate_pump_migration_transaction",
                _OperationAdapter(
                    "solana_rpc", "candidate_pump_migration_transaction",
                    lambda c, candidate_index=candidate_index: candidate_migration_transaction(
                        c, candidate_index=candidate_index
                    ),
                ),
                required=False, phase=PHASE_ENRICHMENT,
                expected_transport_operations=1,
            )
            for candidate_index in range(candidate_verification_count)
        )
        operations.append(
            AcquisitionSourceOperation(
                "solana_rpc", "candidate_pumpswap_pool_verification",
                _OperationAdapter(
                    "solana_rpc", "candidate_pumpswap_pool_verification",
                    candidate_pumpswap_pool_verification,
                ),
                required=False, phase=PHASE_ENRICHMENT,
                expected_transport_operations=1,
            )
        )
        operations.extend(
            AcquisitionSourceOperation(
                "solana_rpc", "holder_concentration_reference",
                _OperationAdapter(
                    "solana_rpc", "holder_concentration_reference",
                    lambda c, candidate_index=candidate_index: holder_reference(
                        c, candidate_index=candidate_index
                    ),
                ),
                expected_transport_operations=2, phase=PHASE_ENRICHMENT,
            )
            # Candidate-specific enrichment covers the acquisition cohort (bounded
            # by M and the governed Solana minute), not the selection capacity N,
            # so more than N cohort candidates can be admitted and the
            # capacity-neutral reserve can exceed N.
            for candidate_index in range(holder_count)
        )
        if self.configuration.goplus_enabled:
            remaining_jobs = max(
                0, int(policy["scheduler_job_ceiling"]) - len(operations)
            )
            goplus_count = min(cap, remaining_jobs)
            operations.extend(
                AcquisitionSourceOperation(
                    "goplus", "safety_reference",
                    _OperationAdapter(
                        "goplus", "safety_reference",
                        lambda c, candidate_index=candidate_index: goplus_reference(
                            c, candidate_index=candidate_index
                        ),
                    ),
                    required=False, phase=PHASE_ENRICHMENT,
                )
                for candidate_index in range(goplus_count)
            )
        return tuple(operations)


def build_live_candidate_acquisition_transport_owner(
    *, environment: Mapping[str, str] | None = None,
    transport: CandidateAcquisitionOneShotTransport | None = None,
) -> LiveCandidateAcquisitionTransportOwner:
    return LiveCandidateAcquisitionTransportOwner(
        load_live_acquisition_configuration(environment), transport=transport)


__all__ = ["RPC_ENVIRONMENT_NAME", "LiveAcquisitionConfigurationError",
           "LiveAcquisitionConfiguration", "TransportResponse",
           "CandidateAcquisitionOneShotTransport",
           "UrllibCandidateAcquisitionOneShotTransport",
           "LiveCandidateAcquisitionTransportOwner",
           "load_live_acquisition_configuration",
           "build_live_candidate_acquisition_transport_owner"]
