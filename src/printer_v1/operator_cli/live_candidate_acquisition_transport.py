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
import json
import os
from types import MappingProxyType
from typing import Any, Callable, Mapping, Protocol, Sequence
from urllib import error as url_error
from urllib import parse as url_parse
from urllib import request as url_request

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
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
    TOKEN_2022_PROGRAM_ID,
    TOKEN_PROGRAM_ID,
    WSOL_MINT,
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


@dataclass(frozen=True)
class LiveAcquisitionConfiguration:
    rpc_url: str = field(repr=False)
    redacted_rpc_host: str
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    per_response_byte_ceiling: int = PER_RESPONSE_BYTE_CEILING
    goplus_enabled: bool = True


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
    code = exc.code if isinstance(exc, LiveAcquisitionTransportError) else "SOURCE_TRANSPORT_FAILURE"
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
        return (
            (
                CURSOR_NETWORK, PUMP_CREATE_INDEX_ADDRESS,
                OFFICIAL_REPOSITORY_COMMIT, CURSOR_DECODER_VERSION,
                LIVE_TAIL_DIRECTION,
            ),
            (
                CURSOR_NETWORK, PUMP_PROGRAM_ID,
                OFFICIAL_REPOSITORY_COMMIT, CURSOR_DECODER_VERSION,
                LIVE_TAIL_DIRECTION,
            ),
        )

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
            "create_rows": [], "migration_rows": [],
            "create_exhausted": False, "migration_exhausted": False,
        }

        def remember_pairs(source: str, result: NormalizedSourceResult) -> None:
            state["pair_results"][source] = result

        def _pair_identity(pair: Mapping[str, Any]) -> tuple[str, str]:
            # Aggregator normalizers differ: DexScreener emits token_mint/
            # pair_address; GeckoTerminal emits baseToken.address/pairAddress.
            mint = str(
                pair.get("token_mint")
                or (pair.get("baseToken") or {}).get("address")
                or ""
            )
            pool = str(pair.get("pair_address") or pair.get("pairAddress") or "")
            return mint, pool

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
                    raise LiveAcquisitionTransportError("SOURCE_MALFORMED", "DEXSCREENER_PROFILES")
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
                result = normalize_dexscreener_fixture_result({"pairs": raw}, request_kind="candidate_nomination")
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
                     cursor_range: Mapping[str, Any] | None = None) -> NormalizedSourceResult:
            result = NormalizedSourceResult(
                source_name="solana_rpc", request_kind=kind,
                source_status=SourceStatus.COMPLETE,
                data_quality_label=DataQualityLabel.CLEAN_DATA,
                normalized_payload=MappingProxyType({"candidate_observations": list(observations)}),
            )
            return _decorate(result, responses, {
                "declared_operation_ceiling": True,
                **({"cursor_range": dict(cursor_range)} if cursor_range else {}),
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
        migration_cursor = live_cursor(namespaces[1])

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
                        raise LiveAcquisitionTransportError(
                            "CURSOR_PRIOR_BOUNDARY_UNREACHABLE",
                            f"{role_prefix}_PRIOR_BOUNDARY",
                            operation_kind="getTransaction",
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
                    raise LiveAcquisitionTransportError("SOURCE_MALFORMED", response.endpoint_role)
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
                        raise LiveAcquisitionTransportError(
                            "SOURCE_MALFORMED", response.endpoint_role
                        )
                    if signature in prior_signatures:
                        raise LiveAcquisitionTransportError(
                            "CURSOR_DUPLICATE_SIGNATURE", response.endpoint_role
                        )
                    if previous_slot is not None and slot > previous_slot:
                        raise LiveAcquisitionTransportError(
                            "CURSOR_PAGE_ORDER_INVALID", response.endpoint_role
                        )
                    if established and slot < int(cursor["start_slot"]):
                        raise LiveAcquisitionTransportError(
                            "CURSOR_PRIOR_BOUNDARY_UNREACHABLE",
                            response.endpoint_role,
                            operation_kind="getSignaturesForAddress",
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
                return complete(kind, (), responses, cursor_range=cursor)
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
                decoded = dict(decoder(
                    response.payload if isinstance(response.payload, Mapping) else None
                ))
                if not decoded.get("supported"):
                    raise LiveAcquisitionTransportError(
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
                    raise LiveAcquisitionTransportError("SOURCE_MALFORMED", response.endpoint_role)
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
                migrations = [
                    state["migrations"][mint]
                    for mint in sorted(state["migrations"]) if mint in cohort
                ]
                aggregated = aggregator_pairs()
                target_mints = {
                    _pair_identity(aggregated[mint])[1]: mint
                    for mint in cohort
                    if mint in aggregated and _pair_identity(aggregated[mint])[1]
                }
                target_mints.update({str(item["pool_address"]): str(item["mint"])
                                     for item in migrations})
                pools = sorted(target_mints)[: cap * 2]
                if not pools:
                    return complete(
                        "pumpswap_pool_account_batch", (), (), cursor_range=migration_cursor
                    )
                response = rpc_call("getMultipleAccounts", [pools, {"encoding": "base64",
                    "commitment": "finalized"}], "PUMPSWAP_POOL_ACCOUNT_BATCH")
                responses.append(response)
                values = (response.payload or {}).get("value") if isinstance(response.payload, Mapping) else None
                if not isinstance(values, list) or len(values) != len(pools):
                    raise LiveAcquisitionTransportError("SOURCE_MALFORMED", response.endpoint_role)
                account_infos = dict(zip(pools, values, strict=True)); observations = []
                migration_pools = {str(item["pool_address"]) for item in migrations}
                for pool in pools:
                    if pool in migration_pools:
                        continue
                    account = account_infos.get(pool)
                    decoded_pool = decode_pumpswap_pool_account(
                        account if isinstance(account, Mapping) else None,
                        pool_address=pool,
                    )
                    facts = {
                        "pool_status": "PASS"
                    } if (
                        decoded_pool.get("decoded")
                        and decoded_pool.get("base_mint") == target_mints[pool]
                        and decoded_pool.get("quote_mint") == WSOL_MINT
                    ) else {}
                    observations.append({"mint": target_mints[pool], "pool": pool,
                        "pool_program_id": (
                            str(account.get("owner") or "") if isinstance(account, Mapping) else None
                        ), "base_mint": target_mints[pool],
                        "quote_mint": decoded_pool.get("quote_mint"),
                        "lineage_claim": "UNKNOWN_ORIGIN", "facts": facts})
                for item in migrations:
                    mint = str(item["mint"]); pool = str(item["pool_address"])
                    verified = verify_pinned_pump_migration(item["tx_result"], account_infos,
                                                            expected_mint=mint, finalized=True)
                    if not verified.get("verified"):
                        continue
                    origin = state["origins"].get(mint)
                    observations.append({"mint": mint, "pool": pool,
                        "pool_program_id": PUMPSWAP_AMM_PROGRAM_ID, "base_mint": mint,
                        "quote_mint": WSOL_MINT, "token_program_id": TOKEN_PROGRAM_ID,
                        "venue_label": "PUMPSWAP", "lineage_claim": "PUMP_GRADUATION_CONFIRMED",
                        "facts": {"pool_status": "PASS",
                            "pump_origin_signature": (origin or {}).get("signature"),
                            "pump_origin_contract_hash": PUMP_IDL_SHA256,
                            "pump_migration_signature": item["signature"],
                            "pump_migration_contract_hash": PUMP_IDL_SHA256,
                            "pumpswap_account_hash": str(verified["pool"].get("contract_hash")),
                            "pumpswap_contract_hash": PUMPSWAP_IDL_SHA256,
                            "pumpswap_index": int(verified["pool"]["index"])}})
                return complete("pumpswap_pool_account_batch", observations, responses)
            except Exception as exc:
                return rpc_failure("pumpswap_pool_account_batch", exc, responses)

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
        migration_page_count = int(source_budgets["pumpfun_migration_signature_page"])
        # The operation plan never exceeds either per-kind policy budgets or
        # the Source Governor's 30 Solana requests/minute. It resolves at most
        # N create and N migrate transactions.
        transaction_count = min(
            int(source_budgets["pumpfun_create_index_transaction"]),
            int(source_budgets["pumpfun_migration_transaction"]),
            int(policy["selection_capacity"]),
        )
        # Candidate-specific holder enrichment is a Solana request per cohort
        # candidate. It covers the acquisition cohort M (never the smaller
        # selection capacity N), but the whole Solana plan must still fit one
        # governed minute (30 requests). When M plus the fixed create/migration/
        # mint/pool Solana cost would exceed the minute, the holder fan-out is
        # bounded to the exact governed headroom, never above M and never
        # silently below what a distinct N-item manifest needs.
        fixed_solana_requests = (
            create_page_count + migration_page_count + 2 * transaction_count + 2
        )
        solana_minute = int(
            SOURCE_REGISTRY["solana_rpc"].default_rate_limit_per_minute
        )
        enrichment_count = min(cap, max(0, solana_minute - fixed_solana_requests))
        if enrichment_count < int(policy["selection_capacity"]):
            raise LiveAcquisitionConfigurationError(
                "ACQUISITION_ENRICHMENT_HEADROOM_BELOW_SELECTION"
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
                        transaction_limit=transaction_count, cursor=create_cursor,
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
            for transaction_index in range(transaction_count)
        )
        operations.extend(
            AcquisitionSourceOperation(
                "solana_rpc", "pumpfun_migration_signature_page",
                _OperationAdapter(
                    "solana_rpc", "pumpfun_migration_signature_page",
                    lambda c, page_index=page_index: signature_page(
                        "pumpfun_migration_signature_page",
                        indexed_address=PUMP_PROGRAM_ID,
                        page_index=page_index, page_limit=migration_page_count,
                        transaction_limit=transaction_count, cursor=migration_cursor,
                        role_prefix="PUMP_MIGRATION", rows_key="migration_rows",
                        exhausted_key="migration_exhausted",
                    ),
                ),
                required=page_index + 1 == migration_page_count,
                round_mode="LIVE_TAIL",
                expected_transport_operations=(
                    2 if page_index == 0 and heads[namespaces[1]] is not None else 1
                ),
                cursor_range=migration_cursor,
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
                round_mode="LIVE_TAIL", expected_transport_operations=1,
                cursor_range=migration_cursor,
            )
            for transaction_index in range(transaction_count)
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
                round_mode="LIVE_TAIL", cursor_range=migration_cursor,
                phase=PHASE_ENRICHMENT,
            ),
        ))
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
            for candidate_index in range(enrichment_count)
        )
        if self.configuration.goplus_enabled:
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
                for candidate_index in range(enrichment_count)
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
