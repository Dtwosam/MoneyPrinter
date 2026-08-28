"""V2-9.7E.11 authoritative live operational campaign owner.

Single internal, dependency-injected composition owner that joins bounded
read-only *live* free-public source adapters to the existing authoritative
domain owners (finalized Pump origin acquisition, combined discovery gates,
deterministic uniform selection, atomic two-or-none activation, the E.8
origin→lifecycle handoff and the proven memory lifecycle). It has no public CLI
and performs no wallet, signing, funds, paid API, retry, rotation, reconnect,
successor or restart work.

Design: ``docs/printer-v1-v2-9-7e-11-authoritative-live-operational-campaign-design.md``.

The live adapters convert raw transport responses into the *existing* governed
operation carriers and delegate every admission, decode, cursor, continuity,
gate, selection and activation decision to the existing owners. No admission,
ordering, decode, discovery, lifecycle, continuation or support-only 5m policy
logic is duplicated here.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
import json
import sqlite3
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence

from printer_v1.discovery.combined_executor import (
    GRADUATED_LIFECYCLE,
    PUMPSWAP_PROGRAM_ID,
    CombinedDiscoveryError,
    CombinedDiscoveryFixtures,
    CombinedPumpfunCampaignExecutor,
    FixtureOriginProof,
    FixtureSourceFact,
    _candidate_categories,
    _non_latest_categories,
    DiscoverySelectionCandidate,
    apply_existing_discovery_gate_and_selection,
)
from printer_v1.operator_cli.abstract_campaign_command import (
    AbstractCampaignCommand,
    CENTRAL_SCHEDULER_OWNER,
    OwnerPort,
    SOURCE_GOVERNOR_OWNER,
)
from printer_v1.operator_cli.multi_cycle_campaign_coordinator import (
    MultiCycleAdmissionHealth,
)
from printer_v1.operator_cli.origin_lifecycle_campaign import (
    ActivationResult,
    OriginLifecycleResult,
    OriginToLifecycleCampaignDriver,
    materialize_origin_activated_batch,
)
from printer_v1.discovery.pre_lifecycle_temporal_acquisition import (
    PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS,
    acquisition_deadline_at as pre_lifecycle_acquisition_deadline_at,
)
from printer_v1.scheduler.scheduler import ACTIVE_STATUS_VALUES, cancel_job
from printer_v1.scheduler.snapshot_maturity import (
    SNAPSHOT_MATURITY_SECONDS,
    SnapshotMaturityState,
    evaluate_snapshot_maturity,
)
from printer_v1.scheduler.support_only_5m_capture import SupportTriggerFamily
from printer_v1.sources.pumpfun_origin import (
    CREATE_INDEX_PAGE_SIZE,
    PUMP_CREATE_INDEX_ADDRESS,
    SIGNATURE_PAGE_REQUEST,
    TRANSACTION_REQUEST,
    AccountingSnapshot,
    AcquisitionCycleResult,
    FinalizedOriginCursor,
    FixtureOperation,
    OriginRegistryError,
    PumpContractError,
    SignatureReference,
    _Accounting,
    load_due_staged_origins,
    record_confirmed_origin,
    run_acquisition_from_source,
)
from printer_v1.sources import secondary_discovery as _sd


CONTRACT_VERSION = "V2-9.7E.11"

# V2-9.7E.33 canonical operational modes of the single committed runner. These
# are the ONLY entry points; there is no parallel runner or disposable harness.
#   ACTIVATION_ONLY    -> live origin + atomic two-or-none activation, then stop
#                         (``run_readiness_only``; no snapshot bundles).
#   SNAPSHOT_READINESS -> preflight, live origin, holder eligibility, exactly two
#                         complete snapshot bundles or an honest blocker, report,
#                         replay, cleanup, stop (``run_snapshot_readiness``). It
#                         never reaches lifecycle windows, memory, retrieval,
#                         decisions or financial paths.
#   PILOT_INPUT_READINESS -> the FULL_PILOT input boundary through immutable
#                         PILOT_INPUT_READY, then stop before lifecycle.
#   FULL_PILOT         -> the full operational natural lifecycle
#                         (``run_operational``).
ACTIVATION_ONLY = "ACTIVATION_ONLY"
SNAPSHOT_READINESS = "SNAPSHOT_READINESS"
PILOT_INPUT_READINESS = "PILOT_INPUT_READINESS"
FULL_PILOT = "FULL_PILOT"
CANONICAL_OPERATIONAL_MODES = frozenset(
    {ACTIVATION_ONLY, SNAPSHOT_READINESS, PILOT_INPUT_READINESS, FULL_PILOT}
)

# Frozen E.11 per-call transport ceilings (readiness boundary).
DEFAULT_CALL_TIMEOUT_SECONDS = 30.0
DEFAULT_RESPONSE_BYTE_CEILING = 1_572_864  # 1.5 MiB
READINESS_STORAGE_BYTE_CEILING = 8 * 1024 * 1024
READINESS_DURATION_CEILING_SECONDS = 360.0
# Ordinary WINDOW_15M source constructors are configured with this existing
# hard timeout. Slice G uses the same bound only for later-cycle quantum
# admission; it does not alter any provider transport or source budget.
LATER_CYCLE_SOURCE_OPERATION_TIMEOUT_SECONDS = 5.0


def _resolve_current_cycle_ordinal_for_historical_disjointness(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    campaign_run_id: str,
    cycle_id: str,
) -> int:
    """Resolve the executing cycle ordinal for historical-disjointness gating.

    Enforcement depends on the authoritative identity of the currently
    executing campaign cycle. Never derive it from COUNT(*) of campaign-cycle
    rows, historical slot count, or history presence. Missing, ambiguous,
    malformed, or invalid current-cycle identity fails closed.
    """
    canonical_campaign_id = str(campaign_id or "").strip()
    canonical_run_id = str(campaign_run_id or "").strip()
    canonical_cycle_id = str(cycle_id or "").strip()
    if not canonical_campaign_id or not canonical_run_id or not canonical_cycle_id:
        raise LiveOperationalError(
            "CURRENT_CYCLE_IDENTITY_INVALID",
            "exact current campaign/run/cycle identity missing",
        )
    row = connection.execute(
        """SELECT cycle_ordinal
           FROM printer_memory_factory_campaign_cycles
           WHERE campaign_id=? AND run_id=? AND cycle_id=?""",
        (canonical_campaign_id, canonical_run_id, canonical_cycle_id),
    ).fetchone()
    if row is None:
        raise LiveOperationalError(
            "CURRENT_CYCLE_IDENTITY_INVALID",
            "exact current cycle row missing",
        )
    raw_ordinal = row[0]
    if type(raw_ordinal) is not int or raw_ordinal < 1:
        raise LiveOperationalError(
            "CURRENT_CYCLE_IDENTITY_INVALID",
            "current cycle_ordinal invalid",
        )
    return raw_ordinal


def _persist_completed_later_cycle_refresh_progress(
    progress_by_cycle: dict[str, dict[str, Any]],
    *,
    progress_key: str,
    progress: Mapping[str, Any],
    refresh_owner: Any,
    completed_source_operations: int,
) -> dict[str, Any]:
    """Commit the cooperative refresh transition before yielding its claim."""
    prior_operations = int(progress.get("source_operations_used") or 0)
    completed_operations = int(completed_source_operations)
    if completed_operations < 0:
        raise LiveOperationalError("LATER_CYCLE_CUMULATIVE_BUDGET_REGRESSION")
    updated = {
        **dict(progress),
        "refresh_owner": refresh_owner,
        "source_operations_used": prior_operations + completed_operations,
        # The refresh owner reports the pre-revalidation reserve depth. Preserve
        # that truthful value until the resumed canonical market traversal owns
        # and persists a new one.
        "reserve_depth": int(progress.get("reserve_depth") or 0),
        "waiting_for_refresh": False,
        "cooperative_phase": "MARKET_DISCOVERY",
    }
    progress_by_cycle[progress_key] = updated
    return updated


def _next_later_cycle_quantum_kind(
    progress_by_cycle: Mapping[str, Mapping[str, Any]],
) -> Any:
    """Select the exact next cooperative unit from persisted production state."""
    from printer_v1.discovery.eligible_token_supply import AcquisitionQuantumKind

    if not progress_by_cycle:
        return AcquisitionQuantumKind.AUXILIARY_FRESH_INTAKE
    waiting = next(
        (
            item
            for item in progress_by_cycle.values()
            if bool(item.get("waiting_for_refresh"))
        ),
        None,
    )
    if waiting is not None:
        refresh_offset = (
            max(1, int(waiting.get("refresh_ordinal") or 1)) - 1
        ) % 3
        return (
            AcquisitionQuantumKind.PERSISTED_REFRESH
            if refresh_offset == 0
            else AcquisitionQuantumKind.PERSISTED_REFRESH_DEXSCREENER
            if refresh_offset == 1
            else AcquisitionQuantumKind.PERSISTED_REFRESH_GECKOTERMINAL
        )
    phase = str(next(iter(progress_by_cycle.values())).get("cooperative_phase") or "")
    return AcquisitionQuantumKind(
        phase or AcquisitionQuantumKind.MARKET_DISCOVERY.value
    )

# Secondary per-cycle request ceilings (frozen design).
GECKO_TRENDING_MAX = 1
GECKO_ACTIVE_MAX = 1
DEXSCREENER_MAX = 2
TRACKER_MAX = 2
HOLDER_ELIGIBILITY_CANDIDATE_MAX = 8


class LiveOperationalError(RuntimeError):
    """Fail-closed live operational composition fault."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(code if not detail else f"{code}: {detail}")


class LiveTransportError(RuntimeError):
    """Bounded one-shot transport fault (timeout, HTTP, oversize, malformed)."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(code if not detail else f"{code}: {detail}")


def _bind_later_cycle_accounting_owner(
    *,
    campaign_id: str,
    run_id: str,
    proposed_cycle_id: str,
    cycle_cutoff: str,
    evaluated_at: str,
    request_key_prefix: str,
    initial_temporal_refresh_owner: Any | None,
    accounting_stage_evidence_sink_for_cycle: Callable[
        ..., Callable[[Mapping[str, Any]], None]
    ],
) -> tuple[
    Callable[[Mapping[str, Any]], None],
    Any | None,
]:
    """Register canonical later-cycle accounting and rebind its refresh sink."""
    canonical_campaign_id = str(campaign_id or "").strip()
    canonical_run_id = str(run_id or "").strip()
    canonical_cycle_id = str(proposed_cycle_id or "").strip()
    if not canonical_campaign_id or not canonical_run_id or not canonical_cycle_id:
        raise LiveOperationalError("LATER_CYCLE_ACCOUNTING_IDENTITY_INVALID")
    if initial_temporal_refresh_owner is not None:
        if (
            str(getattr(initial_temporal_refresh_owner, "campaign_id", ""))
            != canonical_campaign_id
            or str(getattr(initial_temporal_refresh_owner, "run_id", ""))
            != canonical_run_id
            or str(getattr(initial_temporal_refresh_owner, "cycle_id", ""))
            == canonical_cycle_id
        ):
            raise LiveOperationalError("LATER_CYCLE_ACCOUNTING_IDENTITY_INVALID")

    stage_evidence_sink = accounting_stage_evidence_sink_for_cycle(
        campaign_id=canonical_campaign_id,
        run_id=canonical_run_id,
        cycle_id=canonical_cycle_id,
    )
    if not callable(stage_evidence_sink):
        raise LiveOperationalError("LATER_CYCLE_ACCOUNTING_SINK_INVALID")

    rebound = None
    if initial_temporal_refresh_owner is not None:
        rebind = getattr(initial_temporal_refresh_owner, "for_cycle", None)
        if not callable(rebind):
            raise LiveOperationalError("LATER_CYCLE_TEMPORAL_REFRESH_OWNER_INVALID")
        rebound = rebind(
            cycle_id=canonical_cycle_id,
            cycle_cutoff=str(cycle_cutoff),
            evaluated_at=str(evaluated_at),
            request_key_prefix=str(request_key_prefix),
            stage_evidence_sink=stage_evidence_sink,
            cooperative_yield=True,
        )
        if (
            str(getattr(rebound, "campaign_id", "")) != canonical_campaign_id
            or str(getattr(rebound, "run_id", "")) != canonical_run_id
            or str(getattr(rebound, "cycle_id", "")) != canonical_cycle_id
        ):
            raise LiveOperationalError("LATER_CYCLE_ACCOUNTING_REBIND_INVALID")
    return stage_evidence_sink, rebound


# ---------------------------------------------------------------------------
# Transport ports (one-shot; no retry, rotation, reconnect, session)
# ---------------------------------------------------------------------------


class PumpRpcTransport(Protocol):
    """Bounded one-shot Solana JSON-RPC transport."""

    def json_rpc(
        self,
        method: str,
        params: list[Any],
        *,
        timeout_seconds: float,
        byte_ceiling: int,
    ) -> Any:
        """Return the JSON-RPC ``result`` value; raise on any fault."""


class SecondaryHttpTransport(Protocol):
    """Bounded one-shot HTTP GET transport for free-public secondary providers."""

    def json_get(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None,
        headers: Mapping[str, str] | None,
        timeout_seconds: float,
        byte_ceiling: int,
    ) -> Any:
        """Return the decoded JSON body; raise on any fault."""


class OneShotUrllibPumpTransport:
    """Bounded one-shot Solana JSON-RPC transport (stdlib urllib only).

    No retry, reconnect, endpoint rotation, session, wallet or credential. Each
    call opens a single connection, enforces a hard timeout and a response-byte
    ceiling, and returns the JSON-RPC ``result`` value. Used only by the live
    readiness harness; offline proofs inject transport-shaped fakes instead.
    """

    def __init__(self, endpoint: str) -> None:
        self._endpoint = endpoint

    def json_rpc(
        self,
        method: str,
        params: list[Any],
        *,
        timeout_seconds: float,
        byte_ceiling: int,
    ) -> Any:
        import json as _json
        import urllib.error
        import urllib.request

        payload = _json.dumps(
            {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        ).encode("utf-8")
        request = urllib.request.Request(
            self._endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                raw = response.read(byte_ceiling + 1)
        except urllib.error.HTTPError as exc:
            raise LiveTransportError(f"HTTP_{exc.code}", method) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise LiveTransportError("TRANSPORT_UNAVAILABLE", str(exc)) from exc
        if len(raw) > byte_ceiling:
            raise LiveTransportError("RESPONSE_BYTE_CEILING", method)
        try:
            envelope = _json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise LiveTransportError("MALFORMED_RESPONSE", method) from exc
        if not isinstance(envelope, Mapping) or "error" in envelope:
            raise LiveTransportError("RPC_ERROR", method)
        return envelope.get("result")


class OneShotUrllibSecondaryTransport:
    """Bounded one-shot HTTP GET transport for free-public secondary providers."""

    def json_get(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None,
        headers: Mapping[str, str] | None,
        timeout_seconds: float,
        byte_ceiling: int,
    ) -> Any:
        import json as _json
        import urllib.error
        import urllib.parse
        import urllib.request

        full = url
        if params:
            full = url + "?" + urllib.parse.urlencode(dict(params))
        request = urllib.request.Request(
            full, headers=dict(headers or {}), method="GET"
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                raw = response.read(byte_ceiling + 1)
        except urllib.error.HTTPError as exc:
            raise LiveTransportError(f"HTTP_{exc.code}", url) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise LiveTransportError("TRANSPORT_UNAVAILABLE", str(exc)) from exc
        if len(raw) > byte_ceiling:
            raise LiveTransportError("RESPONSE_BYTE_CEILING", url)
        try:
            return _json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise LiveTransportError("MALFORMED_RESPONSE", url) from exc


def _require_owners(source_governor: OwnerPort, central_scheduler: OwnerPort) -> None:
    if (
        source_governor.owner_kind != SOURCE_GOVERNOR_OWNER
        or not source_governor.available
    ):
        raise LiveOperationalError("SOURCE_GOVERNOR_UNAVAILABLE")
    if (
        central_scheduler.owner_kind != CENTRAL_SCHEDULER_OWNER
        or not central_scheduler.available
    ):
        raise LiveOperationalError("CENTRAL_SCHEDULER_UNAVAILABLE")


def _admit_source_request(
    source_governor: OwnerPort,
    central_scheduler: OwnerPort,
    *,
    source_name: str,
    request_kind: str,
) -> None:
    """Explicit per-request Source Governor admission gate.

    Enforced immediately BEFORE any single source transport call so a denied or
    unavailable Governor — or missing Central Scheduler ownership — makes zero
    HTTP calls. First the canonical owner identity/availability is validated
    (raising :class:`LiveOperationalError`). Then, when the injected Source
    Governor exposes an optional ``admit`` decision hook, it is consulted for
    this exact request; a falsy decision fails closed. Plain ``OwnerPort`` owners
    have no hook, so availability is the admission signal and behaviour is
    unchanged for existing callers.
    """
    _require_owners(source_governor, central_scheduler)
    admit = getattr(source_governor, "admit", None)
    if callable(admit):
        approved = admit(source_name=source_name, request_kind=request_kind)
        if not approved:
            raise LiveOperationalError(
                "SECONDARY_REQUEST_DENIED", f"{source_name}:{request_kind}"
            )


# ---------------------------------------------------------------------------
# Bounded live Pump-origin adapter
#
# Implements the shared ``AcquisitionSource`` protocol so the *same* admission,
# ordering, decode, cursor and continuity kernel runs for live and fixture. It
# requests each planned transaction one at a time only when the kernel reaches
# it, so it never prefetches an unknowable number of transaction responses.
# ---------------------------------------------------------------------------


class _LivePumpAcquisitionSource:
    def __init__(
        self,
        transport: PumpRpcTransport,
        *,
        index_address: str,
        timeout_seconds: float,
        byte_ceiling: int,
    ) -> None:
        self._transport = transport
        self._index_address = index_address
        self._timeout = timeout_seconds
        self._byte_ceiling = byte_ceiling
        self.accounting = _Accounting()
        self._before: str | None = None
        self._page_seq = 0
        self._tx_seq = 0

    def next_signature_page(self) -> Mapping[str, Any] | None:
        self._page_seq += 1
        # Governor admission + governed/operation ceilings BEFORE the transport.
        operation = FixtureOperation(
            request_id=f"live-signature-page-{self._page_seq}",
            request_kind=SIGNATURE_PAGE_REQUEST,
            rpc_operation="getSignaturesForAddress",
            response=None,
        )
        self.accounting.consume(operation)
        params: list[Any] = [
            self._index_address,
            {
                "limit": CREATE_INDEX_PAGE_SIZE,
                "commitment": "finalized",
                **({"before": self._before} if self._before else {}),
            },
        ]
        result = self._transport.json_rpc(
            "getSignaturesForAddress",
            params,
            timeout_seconds=self._timeout,
            byte_ceiling=self._byte_ceiling,
        )
        if not isinstance(result, list):
            raise PumpContractError(
                "MALFORMED_TRANSACTION", "signature page result is not a list"
            )
        if result:
            last = result[-1]
            self._before = last.get("signature") if isinstance(last, Mapping) else None
        return {"rows": result}

    def next_transaction(self, reference: SignatureReference) -> Any:
        self._tx_seq += 1
        operation = FixtureOperation(
            request_id=f"live-transaction-{self._tx_seq}",
            request_kind=TRANSACTION_REQUEST,
            rpc_operation="getTransaction",
            response=None,
        )
        self.accounting.consume(operation)
        params: list[Any] = [
            reference.signature,
            {
                "encoding": "json",
                "commitment": "finalized",
                "maxSupportedTransactionVersion": 0,
            },
        ]
        # Live sources fetch on demand and never signal "no more"; a malformed or
        # missing transaction fails closed inside the decode kernel.
        return self._transport.json_rpc(
            "getTransaction",
            params,
            timeout_seconds=self._timeout,
            byte_ceiling=self._byte_ceiling,
        )

    def finalize(self) -> None:
        # Live has no pre-supplied operation list; nothing can be left unconsumed.
        return None


@dataclass(frozen=True)
class LivePumpAcquisition:
    result: AcquisitionCycleResult
    origin_proofs: tuple[FixtureOriginProof, ...]


class LivePumpOriginAdapter:
    """Bounded live finalized Pump-origin acquisition via the shared kernel."""

    def __init__(
        self,
        transport: PumpRpcTransport,
        *,
        timeout_seconds: float = DEFAULT_CALL_TIMEOUT_SECONDS,
        byte_ceiling: int = DEFAULT_RESPONSE_BYTE_CEILING,
    ) -> None:
        self._transport = transport
        self._timeout = timeout_seconds
        self._byte_ceiling = byte_ceiling

    def acquire(
        self,
        *,
        source_governor: OwnerPort,
        central_scheduler: OwnerPort,
        prior_cursor: FinalizedOriginCursor | None = None,
        index_address: str = PUMP_CREATE_INDEX_ADDRESS,
    ) -> LivePumpAcquisition:
        _require_owners(source_governor, central_scheduler)
        source = _LivePumpAcquisitionSource(
            self._transport,
            index_address=index_address,
            timeout_seconds=self._timeout,
            byte_ceiling=self._byte_ceiling,
        )
        result = run_acquisition_from_source(
            source, prior_cursor=prior_cursor, index_address=index_address
        )
        proofs = tuple(
            FixtureOriginProof(
                mint=observation.mint,
                signature=observation.signature,
                slot=observation.slot,
                block_time=observation.block_time,
                bonding_curve=observation.bonding_curve,
                associated_bonding_curve=observation.associated_bonding_curve,
                creator_address=observation.creator_address,
                confirmed=True,
                create_layout=observation.create_layout,
            )
            for observation in result.observations
        )
        return LivePumpAcquisition(result=result, origin_proofs=proofs)


# ---------------------------------------------------------------------------
# Bounded live secondary-provider adapters (existing normalizers only)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LiveSecondaryEnrichment:
    gecko_ops: tuple[FixtureSourceFact, ...] = ()
    tracker_ops: tuple[FixtureSourceFact, ...] = ()
    dexscreener_ops: tuple[FixtureSourceFact, ...] = ()
    requested: int = 0
    failures: int = 0


class LiveSecondaryDiscoveryAdapter:
    """Bounded live GeckoTerminal / DexScreener / (optional) Tracker enrichment.

    Each request is Governor-admitted and Scheduler-owned before transport, and
    every response is converted to the existing factual input shape validated by
    the existing provider normalizers inside the combined executor. Rank, score,
    position and risk labels never enter gates.
    """

    def __init__(
        self,
        transport: SecondaryHttpTransport,
        *,
        timeout_seconds: float = DEFAULT_CALL_TIMEOUT_SECONDS,
        byte_ceiling: int = DEFAULT_RESPONSE_BYTE_CEILING,
        tracker_api_key: str | None = None,
    ) -> None:
        self._transport = transport
        self._timeout = timeout_seconds
        self._byte_ceiling = byte_ceiling
        self._tracker_api_key = tracker_api_key

    def enrich(
        self,
        *,
        source_governor: OwnerPort,
        central_scheduler: OwnerPort,
        receipt_time: str,
        active_pools: Sequence[str] = (),
    ) -> LiveSecondaryEnrichment:
        _require_owners(source_governor, central_scheduler)
        gecko_ops: list[FixtureSourceFact] = []
        dex_ops: list[FixtureSourceFact] = []
        tracker_ops: list[FixtureSourceFact] = []
        requested = 0
        failures = 0

        # 1. GeckoTerminal trending pools (one governed request).
        fact, ok = self._get(
            source_governor=source_governor,
            central_scheduler=central_scheduler,
            source_name=_sd.GECKO_SOURCE_NAME,
            request_kind=_sd.GECKO_TRENDING_REQUEST,
            url=_sd.GECKO_BASE_URL + _sd.GECKO_TRENDING_PATH,
            params=dict(_sd.GECKO_TRENDING_PARAMS),
            headers=None,
            receipt_time=receipt_time,
        )
        requested += 1
        gecko_ops.append(fact)
        failures += 0 if ok else 1

        # 2. One optional exact-pool enrichment when a pool is available.
        for pool in list(active_pools)[:GECKO_ACTIVE_MAX]:
            fact, ok = self._get(
                source_governor=source_governor,
                central_scheduler=central_scheduler,
                source_name=_sd.GECKO_SOURCE_NAME,
                request_kind=_sd.GECKO_ACTIVE_REQUEST,
                url=_sd.GECKO_BASE_URL
                + _sd.GECKO_ACTIVE_PATH_TEMPLATE.format(pool_address=pool),
                params=dict(_sd.GECKO_ACTIVE_PARAMS),
                headers=None,
                receipt_time=receipt_time,
                requested_pool=pool,
            )
            requested += 1
            gecko_ops.append(fact)
            failures += 0 if ok else 1

        # 3. DexScreener active profiles (bounded).
        fact, ok = self._get(
            source_governor=source_governor,
            central_scheduler=central_scheduler,
            source_name=_sd.DEXSCREENER_SOURCE_NAME,
            request_kind=_sd.DEXSCREENER_FRESH_REQUEST,
            url="https://api.dexscreener.com/token-profiles/latest/v1",
            params=None,
            headers=None,
            receipt_time=receipt_time,
        )
        requested += 1
        dex_ops.append(fact)
        failures += 0 if ok else 1

        # 4. Optional free-auth Solana Tracker (only when a free key resolves).
        if self._tracker_api_key:
            fact, ok = self._get(
                source_governor=source_governor,
                central_scheduler=central_scheduler,
                source_name=_sd.TRACKER_SOURCE_NAME,
                request_kind=_sd.TRACKER_TRENDING_REQUEST,
                url=_sd.TRACKER_BASE_URL + _sd.TRACKER_TRENDING_PATH,
                params=None,
                headers={_sd.TRACKER_AUTH_HEADER: self._tracker_api_key},
                receipt_time=receipt_time,
            )
            requested += 1
            tracker_ops.append(fact)
            failures += 0 if ok else 1

        return LiveSecondaryEnrichment(
            gecko_ops=tuple(gecko_ops),
            tracker_ops=tuple(tracker_ops),
            dexscreener_ops=tuple(dex_ops),
            requested=requested,
            failures=failures,
        )

    def _get(
        self,
        *,
        source_governor: OwnerPort,
        central_scheduler: OwnerPort,
        source_name: str,
        request_kind: str,
        url: str,
        params: Mapping[str, Any] | None,
        headers: Mapping[str, str] | None,
        receipt_time: str,
        requested_pool: str | None = None,
    ) -> tuple[FixtureSourceFact, bool]:
        # Explicit Source Governor admission + Central Scheduler ownership BEFORE
        # any transport. A denied or unavailable owner raises here and makes zero
        # HTTP calls; a transport fault below is isolated to this one request.
        _admit_source_request(
            source_governor,
            central_scheduler,
            source_name=source_name,
            request_kind=request_kind,
        )
        try:
            body = self._transport.json_get(
                url,
                params=params,
                headers=headers,
                timeout_seconds=self._timeout,
                byte_ceiling=self._byte_ceiling,
            )
        except LiveTransportError as exc:
            return (
                FixtureSourceFact(
                    request_kind=request_kind,
                    source_name=source_name,
                    body=None,
                    receipt_time=receipt_time,
                    status_code=0,
                    fixture_status="failure",
                    failure_type=exc.code,
                    params=params,
                    requested_pool=requested_pool,
                ),
                False,
            )
        return (
            FixtureSourceFact(
                request_kind=request_kind,
                source_name=source_name,
                body=body,
                receipt_time=receipt_time,
                status_code=200,
                fixture_status="success",
                params=params,
                requested_pool=requested_pool,
            ),
            True,
        )


# ---------------------------------------------------------------------------
# Natural-evidence disposition owner
#
# A pure categorical map from the *existing* 15m memory-window classifier output
# (memory quality + outcome label, whose thresholds live only inside the
# canonical micro-event classifier) to the already-adopted continuation
# learning-need and support-only-5m trigger vocabularies. No score, weight,
# rank, confidence or new threshold is introduced.
# ---------------------------------------------------------------------------


# Adopted outcome_label → support trigger family for a naturally observed
# meaningful transition (a categorical learning need).
_CONTINUATION_OUTCOME_TRIGGERS: Mapping[str, SupportTriggerFamily] = {
    "SHORT_TERM_PUMP": SupportTriggerFamily.FAST_COORDINATED_PUMP,
    "DUMP": SupportTriggerFamily.FAST_DUMP_OR_COLLAPSE,
    "SLOW_BLEED": SupportTriggerFamily.FAST_BREAKDOWN_OR_RECLAIM,
    "DEAD": SupportTriggerFamily.LIQUIDITY_SHOCK,
}
# Ordinary / consolidated movement: no unresolved learning need.
_ORDINARY_OUTCOMES = frozenset({"CONSOLIDATION", "NO_PUMP"})

# Only these memory-quality labels are eligible for clean-memory continuation or
# support-only 5m capture. Any other label — dirty, do-not-train, audit-only,
# stale, incomplete, mismatched, empty or unknown — is ineligible and fails
# closed regardless of the derived outcome label (fail-closed default set).
_ELIGIBLE_MEMORY_QUALITY = frozenset({"CLEAN_MEMORY", "PARTIAL_MEMORY"})


@dataclass(frozen=True)
class NaturalDisposition:
    should_continue: bool
    ordinary_movement: bool
    meaningful_transition_proven: bool
    trigger_family: str | None
    evidence_label: str
    reasons: tuple[str, ...] = ()


class NaturalEvidenceDispositionOwner:
    """Derive continuation/support-only-5m dispositions from governed evidence."""

    def derive_from_labels(
        self, *, memory_quality_label: str | None, outcome_label: str | None
    ) -> NaturalDisposition:
        quality = str(memory_quality_label or "")
        outcome = str(outcome_label or "")
        # Fail closed on any current-run evidence not proven eligible for
        # clean-memory use. Dirty, DO_NOT_TRAIN, audit-only, stale, incomplete,
        # mismatched, empty or unknown memory quality can never drive
        # continuation or support capture — even when the derived outcome maps to
        # a meaningful transition such as SHORT_TERM_PUMP. Memory quality is
        # checked BEFORE the outcome so an eligible outcome never overrides
        # ineligible memory.
        if quality not in _ELIGIBLE_MEMORY_QUALITY:
            return NaturalDisposition(
                should_continue=False,
                ordinary_movement=False,
                meaningful_transition_proven=False,
                trigger_family=None,
                evidence_label="INELIGIBLE_15M_MEMORY_QUALITY",
                reasons=(
                    f"ineligible_memory_quality:{quality or 'NONE'}:"
                    f"{outcome or 'NONE'}",
                ),
            )
        # The canonical 15m classifier collapses dirty / stale / incomplete /
        # unusable evidence to OUTCOME_UNKNOWN (and never emits a categorical
        # outcome for it). A missing or unknown outcome therefore blocks
        # continuation and support capture: it never guesses. A dirty memory
        # quality with no usable outcome is treated the same way.
        if outcome in {"", "OUTCOME_UNKNOWN"}:
            return NaturalDisposition(
                should_continue=False,
                ordinary_movement=False,
                meaningful_transition_proven=False,
                trigger_family=None,
                evidence_label="UNRESOLVED_OR_DIRTY_15M_EVIDENCE",
                reasons=(f"unusable_outcome:{outcome or 'NONE'}:{quality or 'NONE'}",),
            )
        if outcome in _ORDINARY_OUTCOMES:
            return NaturalDisposition(
                should_continue=False,
                ordinary_movement=True,
                meaningful_transition_proven=False,
                trigger_family=None,
                evidence_label="NO_UNRESOLVED_LEARNING_NEED",
            )
        trigger = _CONTINUATION_OUTCOME_TRIGGERS.get(outcome)
        if trigger is None:
            # Unknown / unmapped outcome: fail closed to a terminal stop.
            return NaturalDisposition(
                should_continue=False,
                ordinary_movement=False,
                meaningful_transition_proven=False,
                trigger_family=None,
                evidence_label="UNRESOLVED_OR_UNKNOWN_OUTCOME",
                reasons=(f"unmapped_outcome:{outcome or 'NONE'}",),
            )
        return NaturalDisposition(
            should_continue=True,
            ordinary_movement=False,
            meaningful_transition_proven=True,
            trigger_family=trigger.value,
            evidence_label=f"{outcome}_OBSERVED",
        )

    def derive_from_window(
        self, connection: sqlite3.Connection, window_id: int
    ) -> NaturalDisposition:
        row = connection.execute(
            "SELECT memory_quality_label, outcome_label, window_kind "
            "FROM printer_memory_windows WHERE id=?",
            (int(window_id),),
        ).fetchone()
        if row is None:
            return NaturalDisposition(
                should_continue=False,
                ordinary_movement=False,
                meaningful_transition_proven=False,
                trigger_family=None,
                evidence_label="MISSING_15M_WINDOW",
                reasons=("window_missing",),
            )
        quality = row["memory_quality_label"] if isinstance(row, sqlite3.Row) else row[0]
        outcome = row["outcome_label"] if isinstance(row, sqlite3.Row) else row[1]
        return self.derive_from_labels(
            memory_quality_label=quality, outcome_label=outcome
        )


# Module-level singleton used by the lifecycle factory seam.
_DISPOSITION_OWNER = NaturalEvidenceDispositionOwner()


def derive_natural_disposition(
    connection: sqlite3.Connection, window_id: int
) -> NaturalDisposition:
    """Factory seam entry point: natural disposition for one closed 15m window."""
    return _DISPOSITION_OWNER.derive_from_window(connection, window_id)


# ---------------------------------------------------------------------------
# Authoritative live operational campaign owner
# ---------------------------------------------------------------------------


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _holder_execution_fact(
    execution: Any, *, token_mint: str, source_name: str
) -> dict[str, Any]:
    if execution is None:
        return {
            "eligible": False,
            "reason": "HOLDER_EVIDENCE_UNAVAILABLE",
            "source_name": source_name,
        }
    normalized = execution.normalized_result
    payload = normalized.normalized_payload
    if (
        getattr(execution, "response_record", None) is None
        or getattr(execution, "failure_record", None) is not None
    ):
        subtype = str(getattr(normalized, "failure_type", None) or "missing_response")
        reason = f"HOLDER_EVIDENCE_FAILED:{subtype}"
    elif normalized.source_status.value in {"STALE", "CONFLICTING"}:
        reason = "HOLDER_EVIDENCE_STALE"
    elif (
        normalized.source_status.value != "COMPLETE"
        or normalized.data_quality_label.value != "CLEAN_DATA"
    ):
        reason = "HOLDER_EVIDENCE_MALFORMED_OR_INCOMPLETE"
    else:
        returned_mint = str(payload.get("token_mint") or "")
        if returned_mint.lower() != token_mint.lower():
            return {
                "eligible": False,
                "reason": "HOLDER_EVIDENCE_TARGET_MISMATCH",
                "source_name": source_name,
            }
        if source_name == "goplus":
            from printer_v1.safety.goplus_normalizer import (
                holder_concentration_label_from_goplus,
            )
            label = holder_concentration_label_from_goplus(payload)
        else:
            label = str(
                payload.get("holder_concentration_label")
                or "HOLDER_CONCENTRATION_UNKNOWN"
            )
        if label != "HOLDER_CONCENTRATION_UNKNOWN":
            return {
                "eligible": True,
                "reason": "VALID_EXACT_TARGET_HOLDER_EVIDENCE",
                "source_name": source_name,
                "holder_concentration_label": label,
            }
        reason = "HOLDER_CONCENTRATION_UNKNOWN"
    return {"eligible": False, "reason": reason, "source_name": source_name}


# V2-9.7E.41 graduation-only tracking law admission states.
GRADUATION_ELIGIBLE = "GRADUATED"
GRADUATION_PENDING_DISCOVERY = "PENDING_DISCOVERY"
GRADUATION_AMBIGUOUS_MARKET = "AMBIGUOUS_MARKET"
GRADUATION_FAILED = "GRADUATION_FAILED"
GRADUATION_MARKET_IDENTITY_INVALID = "MARKET_IDENTITY_INVALID"
BLOCKED_INSUFFICIENT_GRADUATED_POOL = "BLOCKED_INSUFFICIENT_GRADUATED_POOL"


def _graduated_supply_terminal_cause(supply: Any | None) -> str:
    """Return a truthful pre-lifecycle cause for an unmet graduated supply.

    Only proven true market-supply exhaustion retains the historical
    insufficient-pool terminal. Source, stale, malformed/visibility, budget,
    duration, or architecture blockers keep their existing categorical shortage
    name and can never be presented as a market conclusion.
    """
    if supply is None:
        return BLOCKED_INSUFFICIENT_GRADUATED_POOL
    diagnostics = dict(getattr(supply, "diagnostics", {}) or {})
    classification = str(diagnostics.get("shortage_classification") or "")
    if classification == "TRACKING_STATE_CAPACITY_BLOCKED":
        return str(
            diagnostics.get("tracking_terminal_cause")
            or "COOLDOWN_REOPEN_REQUIRED"
        )
    if not classification or classification == "TRUE_MARKET_SUPPLY_SHORTAGE":
        return BLOCKED_INSUFFICIENT_GRADUATED_POOL
    return classification


def _project_supply_exhaustion_certificate(supply_diagnostics: Mapping[str, Any]) -> Any | None:
    return supply_diagnostics.get("exhaustion_certificate")


def _classify_graduation(proof: Any, *, graduation: Any) -> str:
    """Classify one confirmed-origin candidate under the graduation-only law.

    A candidate is selection-eligible only when exact PumpSwap graduation confirms
    the exact mint bound to a valid post-graduation PumpSwap market identity
    (owner == adopted program, exactly one pool, base_mint == mint). A bonding-curve
    / unpaired origin with no confirmed graduation is PENDING_DISCOVERY at any age.
    """
    if graduation is None:
        return GRADUATION_PENDING_DISCOVERY
    if getattr(graduation, "ambiguous", False):
        return GRADUATION_AMBIGUOUS_MARKET
    if not getattr(graduation, "confirmed", False):
        return GRADUATION_FAILED
    if (
        getattr(graduation, "program_id", None) != PUMPSWAP_PROGRAM_ID
        or getattr(graduation, "mint", None) != proof.mint
        or not getattr(graduation, "pool_address", None)
    ):
        return GRADUATION_MARKET_IDENTITY_INVALID
    return GRADUATION_ELIGIBLE


def _graduated_admission(
    proofs: Any, *, graduation_proofs: Mapping[str, Any], candidate_cap: int
) -> tuple[tuple[Any, ...], tuple[tuple[Any, str], ...]]:
    """Deduplicate and admit only graduation-confirmed candidates (no age gate).

    Replaces the retired 900-second maturity admission. Age is never eligibility:
    a token confirmed graduated one second ago is admissible, while a bonding-curve
    token of any age is not. Returns the admitted graduated candidates (bounded by
    ``candidate_cap``) and the full ``(proof, graduation_state)`` decisions for
    honest reporting.
    """
    materialized = tuple(proofs)
    deduped = _finalized_holder_candidates(
        materialized, limit=max(len(materialized), 1)
    )
    decisions = tuple(
        (
            proof,
            (
                "CANDIDATE_PRESENT_POOL_ELIGIBLE"
                if getattr(proof, "admission_authority", None) is not None
                and bool(getattr(proof, "present_pool_confirmed", False))
                else _classify_graduation(
                    proof, graduation=graduation_proofs.get(proof.mint)
                )
            ),
        )
        for proof in deduped
    )
    graduated = tuple(
        proof
        for proof, state in decisions
        if state in {GRADUATION_ELIGIBLE, "CANDIDATE_PRESENT_POOL_ELIGIBLE"}
    )[:candidate_cap]
    return graduated, decisions


def _permanent_observation_admission_inputs(supply: Any) -> tuple[Any, ...]:
    """Return the full lawful reserve used by permanent observation freeze."""
    return tuple(supply.holder_reserve_supply)


def _graduated_admission_candidate_cap(
    *,
    permanent_memory_observation: bool,
    ledger: Any,
) -> int:
    """Keep permanent observation supply independent of holder workload budget."""
    if permanent_memory_observation:
        return HOLDER_ELIGIBILITY_CANDIDATE_MAX
    return min(HOLDER_ELIGIBILITY_CANDIDATE_MAX, ledger.candidate_cap())


def _classify_pre_lifecycle_terminal(
    holder_facts: Mapping[str, Mapping[str, Any]], *, reserve_count: int
) -> str:
    """Distinguish a holder-source outage from healthy discovery-coverage exhaustion.

    V2-9.7E.46B item 8: healthy-source exhaustion must be reported as
    ``DISCOVERY_SELECTION_COVERAGE_INSUFFICIENT`` (or capacity-exhausted when the
    approved candidate-search cap stopped coverage early), never casually attributed
    to the market. A transport/auth/rate-limit/stale/collection failure for any
    evaluated candidate is instead ``PRE_LIFECYCLE_HOLDER_EVIDENCE_BLOCKED``.
    """
    from printer_v1.discovery.graduated_liquidity_front_door import (
        HOLDER_SOURCE_UNAVAILABLE_PREFIXES,
    )
    from printer_v1.lifecycle.tracking_queue import (
        HANDOFF_ACTIVE_CONFLICT,
        HANDOFF_COOLDOWN_REOPEN_REQUIRED,
        HANDOFF_TERMINAL_REOPEN_REQUIRED,
        HANDOFF_UNSUPPORTED_STATE,
    )

    tracking_reasons = {
        HANDOFF_ACTIVE_CONFLICT,
        HANDOFF_COOLDOWN_REOPEN_REQUIRED,
        HANDOFF_TERMINAL_REOPEN_REQUIRED,
        HANDOFF_UNSUPPORTED_STATE,
    }
    saw_source_outage = any(
        not fact.get("eligible")
        and str(fact.get("reason") or "").startswith(HOLDER_SOURCE_UNAVAILABLE_PREFIXES)
        for fact in holder_facts.values()
    )
    if saw_source_outage:
        return "PRE_LIFECYCLE_HOLDER_EVIDENCE_BLOCKED"
    for fact in holder_facts.values():
        reason = str(fact.get("reason") or "")
        if reason in tracking_reasons:
            return reason
    if len(holder_facts) < reserve_count:
        return "PRE_LIFECYCLE_DISCOVERY_SELECTION_CAPACITY_EXHAUSTED"
    return "PRE_LIFECYCLE_DISCOVERY_SELECTION_COVERAGE_INSUFFICIENT"


def _finalized_holder_candidates(proofs: Any, *, limit: int) -> tuple[Any, ...]:
    """Apply structural, zero-source finalized-proof gates before holder I/O."""
    eligible = []
    seen: set[tuple[str, str]] = set()
    for proof in proofs:
        source_specific = getattr(proof, "admission_authority", None) is not None
        identity = (
            str(proof.mint).lower(),
            str(
                getattr(proof, "pool_address", "")
                if source_specific
                else proof.bonding_curve
            ),
        )
        if (
            not bool(proof.confirmed)
            or not identity[0]
            or not identity[1]
            or (not source_specific and not str(proof.signature))
            or (not source_specific and int(proof.slot) < 0)
            or identity in seen
        ):
            continue
        seen.add(identity)
        eligible.append(proof)
    if any(getattr(proof, "admission_authority", None) is not None for proof in eligible):
        # Source-specific reserves are already frozen by the neutral selection
        # authority; slot order must not become a provenance signal.
        return tuple(eligible[:limit])
    return tuple(
        sorted(
            eligible,
            key=lambda proof: (
                proof.mint.lower(), proof.bonding_curve, proof.signature, int(proof.slot),
            ),
        )[:limit]
    )


def _holder_eligibility_from_bundle(
    bundle: Mapping[str, Any], *, token_mint: str
) -> dict[str, Any]:
    executions = bundle.get("executions", {})
    goplus = _holder_execution_fact(
        executions.get("safety"), token_mint=token_mint, source_name="goplus"
    )
    facts = [goplus]
    attempted: list[dict[str, Any]] = []
    seen: set[int] = set()
    for key in ("holder_primary", "holder_backup", "holder"):
        execution = executions.get(key)
        if execution is None or id(execution) in seen:
            continue
        seen.add(id(execution))
        normalized_source = str(
            getattr(execution.normalized_result, "source_name", "solana_rpc")
        )
        fact = _holder_execution_fact(
            execution, token_mint=token_mint, source_name=normalized_source
        )
        facts.append(fact)
        attempted.append(fact)
    from printer_v1.sources.helius_holder import resolve_holder_concentration_facts
    resolved = dict(resolve_holder_concentration_facts(tuple(facts)))
    if resolved["reason"] != "HOLDER_EVIDENCE_UNAVAILABLE":
        return resolved
    # Preserve transport/auth/rate-limit/provider failure precedence. Target
    # mismatch is returned only when an actual response supplied a wrong mint.
    return attempted[-1] if attempted else goplus


def _holder_condition_passes(
    fact: Mapping[str, Any] | None,
) -> bool:
    """True only when usable holder evidence carries a favorable condition."""
    holder_fact = dict(fact or {})
    if not bool(holder_fact.get("eligible")):
        return False
    label = str(
        holder_fact.get("holder_condition")
        or holder_fact.get("holder_concentration_label")
        or "HOLDER_CONCENTRATION_UNKNOWN"
    )
    return label in {
        "HOLDER_CONCENTRATION_PASS",
        "HOLDER_CONCENTRATION_HEALTHY",
    }


def _holder_observation_context(
    fact: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Convert truthful holder evidence into memory-only contextual fields."""
    holder_fact = dict(fact or {})
    holder_evidence_usable = bool(holder_fact.get("eligible"))
    holder_actually_eligible = _holder_condition_passes(holder_fact)
    if not holder_fact:
        holder_condition = "UNKNOWN"
        holder_evidence_status = "SOURCE_UNAVAILABLE_OR_INCOMPLETE"
    elif (
        holder_fact.get("holder_evidence_status")
        == "SOURCE_NOT_EVALUATED_BUDGET_BOUND"
    ):
        holder_condition = "UNKNOWN"
        holder_evidence_status = "SOURCE_NOT_EVALUATED_BUDGET_BOUND"
    else:
        holder_condition = str(
            holder_fact.get("holder_condition")
            or holder_fact.get("holder_concentration_label")
            or "HOLDER_CONCENTRATION_UNKNOWN"
        )
        holder_evidence_status = (
            "COMPLETE"
            if holder_evidence_usable
            else str(
                holder_fact.get("holder_evidence_status")
                or holder_fact.get("reason")
                or "SOURCE_UNAVAILABLE_OR_INCOMPLETE"
            )
        )
    return {
        "holder_condition": holder_condition,
        "holder_evidence_status": holder_evidence_status,
        "future_action_eligibility": "BLOCKED_OR_UNKNOWN",
        "fully_eligible": holder_actually_eligible,
    }



def _readiness_admission_authority(activation_candidate: Any | None) -> str | None:
    """Project canonical frozen admission authority without inference."""
    if activation_candidate is None:
        return None
    from printer_v1.discovery.memory_observation_activation import AdmissionAuthority

    raw = getattr(activation_candidate, "admission_authority", None)
    if raw is None:
        raise LiveOperationalError(
            "MEMORY_OBSERVATION_ADMISSION_AUTHORITY_MISSING"
        )
    value = getattr(raw, "value", raw)
    try:
        return AdmissionAuthority(str(value)).value
    except ValueError as exc:
        raise LiveOperationalError(
            "MEMORY_OBSERVATION_ADMISSION_AUTHORITY_UNSUPPORTED",
            str(value),
        ) from exc

def _owned_transport_keys_for_request(
    manifest_entry: Mapping[str, Any],
) -> tuple[tuple[object, ...], ...]:
    """Return exact serialized transport keys owned by one manifest request."""
    raw_keys = manifest_entry.get("transport_identity_keys")
    if raw_keys is None:
        return ()
    keys: list[tuple[object, ...]] = []
    for item in raw_keys:
        if isinstance(item, Mapping):
            from printer_v1.discovery.memory_observation_activation import (
                transport_identity_key_from_mapping,
            )

            keys.append(transport_identity_key_from_mapping(item))
        else:
            keys.append(tuple(item))
    return tuple(keys)


def _resolve_retained_role_pair(
    connection: sqlite3.Connection,
    *,
    mint: str,
    pool: str,
    role_name: str,
    request_id_raw: object,
    response_id_raw: object,
    failure_id_raw: object = None,
) -> tuple[int, int, str, str, str, int | None]:
    """Load one exact retained source request/response pair for a role."""
    from printer_v1.discovery.memory_observation_activation import (
        MemoryObservationActivationError,
    )

    if request_id_raw is None or response_id_raw is None:
        raise MemoryObservationActivationError(
            "RETAINED_EVIDENCE_ROLE_MISSING", f"{mint}:{role_name}"
        )
    request_id = int(request_id_raw)
    response_id = int(response_id_raw)
    request = connection.execute(
        """SELECT source_name,request_kind,requested_at
           FROM printer_source_requests WHERE id=?""",
        (request_id,),
    ).fetchone()
    response = connection.execute(
        """SELECT response_hash FROM printer_source_responses
           WHERE id=? AND source_request_id=?""",
        (response_id, request_id),
    ).fetchone()
    if request is None or response is None:
        raise MemoryObservationActivationError(
            "RETAINED_EVIDENCE_ROW_MISSING",
            f"{role_name}:{request_id}:{response_id}",
        )
    failure_id = None if failure_id_raw is None else int(failure_id_raw)
    return (
        request_id,
        response_id,
        str(request[0]),
        str(request[1]),
        str(response[0]),
        failure_id,
    )


def _role_ids_from_candidate(
    item: Mapping[str, Any],
    liquidity: Mapping[str, Any],
    role: str,
) -> tuple[object, object, object]:
    """Extract request/response/failure IDs for one evidence role from a candidate."""
    role_blob = item.get("retained_evidence") or {}
    if isinstance(role_blob, Mapping):
        role_entry = role_blob.get(role) or {}
        if isinstance(role_entry, Mapping) and role_entry.get("source_request_id") is not None:
            return (
                role_entry.get("source_request_id"),
                role_entry.get("source_response_id"),
                role_entry.get("source_failure_id"),
            )
    if role == "MARKET_OBSERVATION":
        return (
            liquidity.get("source_request_id"),
            liquidity.get("source_response_id"),
            liquidity.get("source_failure_id"),
        )
    if role == "PUMPSWAP_CONFIRMATION":
        pumpswap = item.get("pumpswap_confirmation") or {}
        if not isinstance(pumpswap, Mapping):
            pumpswap = {}
        provenance = item.get("source_provenance") or liquidity.get("source_provenance") or {}
        if not isinstance(provenance, Mapping):
            provenance = {}
        request_id = (
            pumpswap.get("source_request_id")
            or item.get("pumpswap_source_request_id")
            or item.get("protocol_request_id")
            or provenance.get("protocol_request_id")
        )
        if request_id is None and str(provenance.get("stage") or "") in {
            "protocol_confirmation",
            "protocol_confirmation_direct_promotion",
        }:
            request_id = provenance.get("request_id")
        response_id = (
            pumpswap.get("source_response_id")
            or item.get("pumpswap_source_response_id")
            or provenance.get("response_id")
        )
        return (request_id, response_id, pumpswap.get("source_failure_id"))
    if role == "ORIGIN_LINEAGE":
        origin = item.get("origin_lineage") or {}
        if not isinstance(origin, Mapping):
            origin = {}
        return (
            origin.get("source_request_id") or item.get("origin_source_request_id"),
            origin.get("source_response_id") or item.get("origin_source_response_id"),
            origin.get("source_failure_id"),
        )
    return (None, None, None)


def _admission_authority_from_freeze_item(item: Mapping[str, Any]) -> Any:
    """Resolve freeze-item admission authority with fail-closed missing handling.

    Missing, None, empty, or unknown values never infer DIRECT_PUMP_PUMPSWAP.
    """
    from printer_v1.discovery.memory_observation_activation import AdmissionAuthority

    if "admission_authority" not in item:
        raise ValueError("ADMISSION_AUTHORITY_MISSING")
    raw = item.get("admission_authority")
    if raw is None:
        raise ValueError("ADMISSION_AUTHORITY_MISSING")
    text = str(raw).strip()
    if not text:
        raise ValueError("ADMISSION_AUTHORITY_MISSING")
    return AdmissionAuthority(text)


def _memory_observation_activation_route(
    *,
    admission_authority: Any | None,
    carried_route: object = None,
) -> str:
    """Resolve MEMORY_OBSERVATION activation_route to match readiness law.

    MARKET_PRESENT_POOL must carry its exact authority route. Direct Pump keeps
    a lawful legacy carrier (GRADUATION_NATIVE / PUMP_CREATE) when present.
    """
    from printer_v1.discovery.memory_observation_activation import AdmissionAuthority

    carried = str(carried_route or "").strip()
    if admission_authority is None or not str(admission_authority).strip():
        return carried
    try:
        authority = (
            admission_authority
            if isinstance(admission_authority, AdmissionAuthority)
            else AdmissionAuthority(str(admission_authority).strip())
        )
    except ValueError:
        return carried
    if authority is AdmissionAuthority.MARKET_PRESENT_POOL:
        return authority.value
    if carried:
        return carried
    return "PUMP_CREATE"


def _filter_observation_rows_by_retained_role_completeness(
    connection: sqlite3.Connection,
    rows: Sequence[Mapping[str, Any]],
    *,
    now: str,
    request_key_root: str | None = None,
    campaign_id: str | None = None,
    run_id: str | None = None,
    cycle_id: str | None = None,
    campaign_source_request_manifest: Sequence[Mapping[str, Any]] | None = None,
    measured_transport_identity_keys: Sequence[Sequence[object]] | None = None,
    require_current_run_provenance: bool = True,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Exclude role/provenance-incomplete nominees before the neutral freeze.

    Candidate-local role truth and current-run measured provenance are both
    required for freeze eligibility.
    """
    from printer_v1.discovery.memory_observation_activation import (
        RETAINED_EVIDENCE_ROLE_INCOMPLETE_PRE_FREEZE,
        assess_retained_evidence_role_completeness,
        claims_consistent_with_admission_authority,
        qualify_candidate_local_retained_role,
        qualify_candidate_retained_evidence_timing,
        required_evidence_roles_for_admission_authority,
    )

    if require_current_run_provenance and (
        not str(request_key_root or "").strip()
        or not str(campaign_id or "").strip()
        or not str(run_id or "").strip()
        or not str(cycle_id or "").strip()
        or campaign_source_request_manifest is None
    ):
        # Fail closed before freeze when pre-holder measured ownership is absent.
        return [], [
            {
                "mint": None,
                "pool": None,
                "admission_authority": None,
                "required_roles": (),
                "present_roles": (),
                "missing_roles": (),
                "qualification_failures": {
                    "current_run_provenance": (
                        "RETAINED_CURRENT_RUN_PROVENANCE_UNAVAILABLE"
                    )
                },
                "disposition": RETAINED_EVIDENCE_ROLE_INCOMPLETE_PRE_FREEZE,
                "detail": "RETAINED_CURRENT_RUN_PROVENANCE_UNAVAILABLE",
            }
        ]

    complete_rows: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    for raw in rows:
        item = dict(raw)
        mint = str(item.get("mint") or "")
        pool = str(item.get("pool") or item.get("pumpswap_pool") or "")
        try:
            admission_authority = _admission_authority_from_freeze_item(item)
        except ValueError as exc:
            detail = str(exc) or "ADMISSION_AUTHORITY_UNSUPPORTED"
            if detail not in {
                "ADMISSION_AUTHORITY_MISSING",
                "ADMISSION_AUTHORITY_UNSUPPORTED",
            }:
                detail = "ADMISSION_AUTHORITY_UNSUPPORTED"
            exclusions.append(
                {
                    "mint": mint,
                    "pool": pool,
                    "admission_authority": (
                        None
                        if "admission_authority" not in item
                        else item.get("admission_authority")
                    ),
                    "required_roles": (),
                    "present_roles": (),
                    "missing_roles": (),
                    "qualification_failures": {"admission_authority": detail},
                    "disposition": RETAINED_EVIDENCE_ROLE_INCOMPLETE_PRE_FREEZE,
                    "detail": detail,
                }
            )
            continue

        # Claims are optional provenance. When present they must match authority.
        if "claims_pump_origin" in item or "claims_pumpswap_graduation" in item:
            expected_direct = (
                admission_authority.value == "DIRECT_PUMP_PUMPSWAP"
            )
            claims_origin = bool(
                item.get(
                    "claims_pump_origin",
                    expected_direct,
                )
            )
            claims_graduation = bool(
                item.get(
                    "claims_pumpswap_graduation",
                    expected_direct,
                )
            )
            if not claims_consistent_with_admission_authority(
                admission_authority,
                claims_pump_origin=claims_origin,
                claims_pumpswap_graduation=claims_graduation,
            ):
                exclusions.append(
                    {
                        "mint": mint,
                        "pool": pool,
                        "admission_authority": admission_authority.value,
                        "required_roles": [
                            role.value
                            for role in required_evidence_roles_for_admission_authority(
                                admission_authority
                            )
                        ],
                        "present_roles": [],
                        "missing_roles": [],
                        "qualification_failures": {
                            "admission_authority": (
                                "ADMISSION_AUTHORITY_CLAIMS_INCONSISTENT"
                            )
                        },
                        "disposition": RETAINED_EVIDENCE_ROLE_INCOMPLETE_PRE_FREEZE,
                        "detail": "ADMISSION_AUTHORITY_CLAIMS_INCONSISTENT",
                    }
                )
                continue

        liquidity = dict(item.get("liquidity") or {})
        market_req, market_resp, _market_fail = _role_ids_from_candidate(
            item, liquidity, "MARKET_OBSERVATION"
        )
        timing_ok, timing_reason, resolved_observed_at = (
            qualify_candidate_retained_evidence_timing(
                connection,
                item,
                now=now,
                market_request_id=market_req,
                market_response_id=market_resp,
            )
        )
        if not timing_ok:
            exclusions.append(
                {
                    "mint": mint,
                    "pool": pool,
                    "admission_authority": admission_authority.value,
                    "required_roles": [
                        role.value
                        for role in required_evidence_roles_for_admission_authority(
                            admission_authority
                        )
                    ],
                    "present_roles": [],
                    "missing_roles": [],
                    "qualification_failures": {
                        "timing": str(
                            timing_reason or "RETAINED_OBSERVATION_TIME_MISSING"
                        )
                    },
                    "disposition": RETAINED_EVIDENCE_ROLE_INCOMPLETE_PRE_FREEZE,
                    "detail": str(
                        timing_reason or "RETAINED_OBSERVATION_TIME_MISSING"
                    ),
                }
            )
            continue

        qualifying_roles = set()
        qualification_failures: dict[str, str] = {}
        for role in required_evidence_roles_for_admission_authority(admission_authority):
            request_id, response_id, failure_id = _role_ids_from_candidate(
                item, liquidity, role.value
            )
            ok, reason = qualify_candidate_local_retained_role(
                connection,
                role=role,
                mint=mint,
                pool=pool,
                request_id_raw=request_id,
                response_id_raw=response_id,
                failure_id_raw=failure_id,
                admission_authority=admission_authority,
                now=now,
                evidence_expires_at=(
                    None
                    if item.get("evidence_expires_at") is None
                    else str(item.get("evidence_expires_at"))
                ),
                request_key_root=request_key_root,
                campaign_id=campaign_id,
                run_id=run_id,
                cycle_id=cycle_id,
                campaign_source_request_manifest=campaign_source_request_manifest,
                measured_transport_identity_keys=measured_transport_identity_keys,
                require_current_run_provenance=require_current_run_provenance,
            )
            if ok:
                qualifying_roles.add(role)
            else:
                qualification_failures[role.value] = str(
                    reason or "RETAINED_EVIDENCE_ROLE_MISSING"
                )

        assessment = assess_retained_evidence_role_completeness(
            admission_authority=admission_authority,
            qualifying_roles=qualifying_roles,
            mint=mint,
            qualification_failures=qualification_failures,
        )
        if assessment["complete"]:
            # Preserve the resolved authority on the freeze item so activation
            # construction cannot re-default an explicit MARKET_PRESENT nominee.
            item["admission_authority"] = admission_authority.value
            expected_direct = (
                admission_authority.value == "DIRECT_PUMP_PUMPSWAP"
            )
            item["claims_pump_origin"] = expected_direct
            item["claims_pumpswap_graduation"] = expected_direct
            # Compose the proven retained observation time onto the freeze item
            # so selected activation reuses the same established fact.
            if resolved_observed_at:
                item["liquidity_observed_at"] = str(resolved_observed_at)
                liquidity["liquidity_observed_at"] = str(resolved_observed_at)
                item["liquidity"] = liquidity
            complete_rows.append(item)
            continue
        exclusions.append(
            {
                "mint": mint,
                "pool": pool,
                "admission_authority": assessment["admission_authority"],
                "required_roles": list(assessment["required_roles"]),
                "present_roles": list(assessment["present_roles"]),
                "missing_roles": list(assessment["missing_roles"]),
                "qualification_failures": dict(
                    assessment.get("qualification_failures") or {}
                ),
                "disposition": assessment["disposition"],
            }
        )
    return complete_rows, exclusions


def _build_frozen_memory_activation_set(
    connection: sqlite3.Connection,
    *,
    frozen_reserve: Any,
    readiness_id: str,
    selection_seed: str,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    manifest: Sequence[Mapping[str, Any]],
    measured_transport_identity_keys: Sequence[Sequence[object]],
    frozen_at: str,
    expires_at: str,
) -> Any:
    """Project the exact freeze authority into the typed activation contract."""
    from printer_v1.discovery.memory_observation_activation import (
        ActivationPurpose,
        AdmissionAuthority,
        EvidenceRole,
        FrozenMemoryActivationCandidate,
        FrozenMemoryActivationSet,
        ManifestRequestEntry,
        MemoryObservationActivationError,
        RetainedEvidenceReference,
        TrackingFeasibility,
        required_evidence_roles_for_admission_authority,
    )

    manifest_by_id = {
        int(entry["source_request_id"]): dict(entry)
        for entry in manifest
        if entry.get("source_request_id") is not None
    }
    typed_entries: list[Any] = []
    owned_key_union: list[tuple[object, ...]] = []
    for rid in sorted(manifest_by_id):
        entry = manifest_by_id[rid]
        owned_keys = _owned_transport_keys_for_request(entry)
        declared = int(entry.get("transport_identity_count") or 0)
        # Prefer explicit keys; never invent keys from the flat set by
        # source-name / request-kind fallback.
        if owned_keys and declared and declared != len(owned_keys):
            raise MemoryObservationActivationError(
                "RETAINED_TRANSPORT_IDENTITY_COUNT_MISMATCH",
                f"request={rid}:declared={declared}:keys={len(owned_keys)}",
            )
        if not owned_keys and declared == 0 and str(
            entry.get("terminal_status") or "COMPLETED"
        ) == "COMPLETED":
            # Successful request with zero owned identities is a hard block for
            # activation binding; counts alone are never accepted.
            owned_keys = ()
        typed_entries.append(
            ManifestRequestEntry(
                source_request_id=rid,
                source_name=str(entry.get("source_name") or ""),
                request_kind=str(entry.get("request_kind") or ""),
                logical_stage_id=str(entry.get("logical_stage_id") or ""),
                transport_identity_count=(
                    declared if declared or not owned_keys else len(owned_keys)
                ),
                transport_identity_keys=owned_keys,
                terminal_status=str(entry.get("terminal_status") or "COMPLETED"),
            )
        )
        owned_key_union.extend(owned_keys)

    flat_keys = tuple(tuple(key) for key in measured_transport_identity_keys)
    transport_keys = tuple(owned_key_union) if owned_key_union else flat_keys

    def _reference_for_role(
        *,
        role: EvidenceRole,
        mint: str,
        pool: str,
        request_id: int,
        response_id: int,
        source_name: str,
        request_kind: str,
        raw_hash: str,
        failure_id: int | None,
        observed_at: str,
    ) -> Any:
        manifest_entry = manifest_by_id.get(request_id)
        if manifest_entry is None:
            raise MemoryObservationActivationError(
                "RETAINED_REQUEST_NOT_IN_MANIFEST", str(request_id)
            )
        owned_keys = _owned_transport_keys_for_request(manifest_entry)
        declared = int(manifest_entry.get("transport_identity_count") or 0)
        if not owned_keys:
            raise MemoryObservationActivationError(
                "RETAINED_REQUEST_TRANSPORT_IDENTITY_MISSING",
                f"{mint}:{role.value}:request={request_id}",
            )
        if declared and declared != len(owned_keys):
            raise MemoryObservationActivationError(
                "RETAINED_TRANSPORT_IDENTITY_COUNT_MISMATCH",
                f"request={request_id}",
            )
        return RetainedEvidenceReference(
            evidence_role=role,
            source_name=source_name,
            request_kind=request_kind,
            source_request_id=request_id,
            source_response_id=response_id,
            source_failure_id=failure_id,
            transport_identity_keys=owned_keys,
            observed_at=observed_at,
            raw_payload_hash=raw_hash,
            target_mint=mint,
            target_pool=pool,
            campaign_id=campaign_id,
            campaign_run_id=run_id,
            cycle_id=cycle_id,
        )

    def candidate(raw: Mapping[str, Any], ordinal: int, *, soft: bool = False) -> Any:
        from printer_v1.discovery.memory_observation_activation import (
            resolve_retained_observation_time,
        )

        item = dict(raw)
        mint = str(item.get("mint") or "")
        pool = str(item.get("pool") or "")
        liquidity = dict(item.get("liquidity") or {})
        # Preserve the categorical incomplete-market signal before role checks so
        # disposable fixtures that omit market response rows keep their exact
        # blocker code. Missing origin/pumpswap roles still fail closed below.
        # Soft/report-only alternate projection may omit market IDs without
        # terminalizing the selected activation pair.
        market_req, market_resp, _market_fail = _role_ids_from_candidate(
            item, liquidity, EvidenceRole.MARKET_OBSERVATION.value
        )
        if market_req is None or market_resp is None:
            if soft:
                pass
            else:
                raise MemoryObservationActivationError(
                    "RETAINED_EVIDENCE_REFERENCE_INCOMPLETE", mint
                )

        try:
            market_request_id = (
                None if market_req is None else int(market_req)
            )
        except (TypeError, ValueError):
            market_request_id = None
        try:
            market_response_id = (
                None if market_resp is None else int(market_resp)
            )
        except (TypeError, ValueError):
            market_response_id = None
        # Selected activation must not invent frozen_at as observation time.
        # Report-only soft projection may still fall back to frozen_at.
        retained_time = str(
            resolve_retained_observation_time(
                connection,
                item,
                market_request_id=market_request_id,
                market_response_id=market_response_id,
                frozen_at=frozen_at,
                allow_frozen_at_fallback=soft,
            )
            or ""
        )

        try:
            admission_authority = _admission_authority_from_freeze_item(item)
        except ValueError as exc:
            detail = str(exc) or "ADMISSION_AUTHORITY_UNSUPPORTED"
            code = (
                "ADMISSION_AUTHORITY_MISSING"
                if detail == "ADMISSION_AUTHORITY_MISSING"
                else "ADMISSION_AUTHORITY_UNSUPPORTED"
            )
            raise MemoryObservationActivationError(code, mint) from exc
        claims_pump = admission_authority is AdmissionAuthority.DIRECT_PUMP_PUMPSWAP
        required_roles = required_evidence_roles_for_admission_authority(
            admission_authority
        )
        role_refs: list[Any] = []
        for role in required_roles:
            req_raw, resp_raw, fail_raw = _role_ids_from_candidate(
                item, liquidity, role.value
            )
            if soft and (req_raw is None or resp_raw is None):
                continue
            (
                request_id,
                response_id,
                source_name,
                request_kind,
                raw_hash,
                failure_id,
            ) = _resolve_retained_role_pair(
                connection,
                mint=mint,
                pool=pool,
                role_name=role.value,
                request_id_raw=req_raw,
                response_id_raw=resp_raw,
                failure_id_raw=fail_raw,
            )
            observed = resolve_retained_observation_time(
                connection,
                item,
                market_request_id=int(request_id),
                market_response_id=int(response_id),
                frozen_at=frozen_at,
                # Selected MARKET retained_time never invents frozen_at.
                # Soft/report-only and non-market role reference fills may.
                allow_frozen_at_fallback=(
                    soft or role is not EvidenceRole.MARKET_OBSERVATION
                ),
            ) or retained_time
            if not observed and soft:
                observed = frozen_at
            if (
                role is EvidenceRole.MARKET_OBSERVATION
                and observed
                and (soft or observed != str(frozen_at or "").strip())
            ):
                retained_time = observed
            role_refs.append(
                _reference_for_role(
                    role=role,
                    mint=mint,
                    pool=pool,
                    request_id=request_id,
                    response_id=response_id,
                    source_name=source_name,
                    request_kind=request_kind,
                    raw_hash=raw_hash,
                    failure_id=failure_id,
                    observed_at=str(observed or retained_time or frozen_at),
                )
            )
        if not retained_time:
            if soft:
                retained_time = frozen_at
            else:
                raise MemoryObservationActivationError(
                    "RETAINED_OBSERVATION_TIME_MISSING", mint
                )
        holder_condition = str(item.get("holder_condition") or "UNKNOWN")
        tracking_reason = str(item.get("tracking_handoff_reason") or "UNKNOWN")
        if soft and len(role_refs) < len(required_roles):
            tracking_reason = (
                "REPORT_ONLY_ALTERNATE:RETAINED_EVIDENCE_ROLE_MISSING"
            )
        return FrozenMemoryActivationCandidate(
            slot_ordinal=ordinal,
            mint=mint,
            pool=pool,
            market_identity=str(item.get("market_identity") or ""),
            lifecycle_identity=(
                GRADUATED_LIFECYCLE
                if claims_pump
                else "PRESENT_POOL_CONFIRMED"
            ),
            activation_route=_memory_observation_activation_route(
                admission_authority=admission_authority,
                carried_route=item.get("activation_route"),
            ),
            provenance=str(item.get("provenance") or ""),
            memory_observation_eligible=(
                item.get("memory_observation_eligible") is True
            ),
            fully_eligible=bool(item.get("fully_eligible")),
            holder_condition=holder_condition,
            holder_evidence_status=str(
                item.get("holder_evidence_status") or "UNKNOWN"
            ),
            future_action_eligibility=str(
                item.get("future_action_eligibility") or "BLOCKED_OR_UNKNOWN"
            ),
            evidence_expires_at=str(item.get("evidence_expires_at") or ""),
            liquidity_observed_at=str(retained_time),
            tracking_feasibility=TrackingFeasibility(
                eligible=bool(item.get("tracking_handoff_eligible")),
                reason_code=tracking_reason,
                tracking_queue_id=(
                    None
                    if item.get("tracking_queue_id") is None
                    else int(item["tracking_queue_id"])
                ),
                tracking_queue_status=(
                    None
                    if item.get("tracking_queue_status") is None
                    else str(item["tracking_queue_status"])
                ),
                requalification_required=bool(
                    item.get("tracking_requalification_required")
                ),
                cooldown_until=(
                    None
                    if item.get("cooldown_until") is None
                    else str(item["cooldown_until"])
                ),
                assessed_at=str(item.get("tracking_assessed_at") or frozen_at),
            ),
            retained_evidence_references=tuple(role_refs),
            admission_authority=admission_authority,
            claims_pump_origin=claims_pump,
            claims_pumpswap_graduation=claims_pump,
        )

    def report_only_alternate(raw: Mapping[str, Any], ordinal: int) -> Any:
        """Project report/diagnostic alternates without selected activation authority.

        Narrow soft handling only for missing selected-only retained references.
        Do not swallow arbitrary integrity failures or rewrite admission authority.
        """
        report_only_missing_codes = {
            "RETAINED_EVIDENCE_ROLE_MISSING",
            "RETAINED_EVIDENCE_REFERENCE_INCOMPLETE",
            "RETAINED_OBSERVATION_TIME_MISSING",
            "RETAINED_REQUEST_NOT_IN_MANIFEST",
            "RETAINED_REQUEST_TRANSPORT_IDENTITY_MISSING",
        }
        try:
            return candidate(raw, ordinal, soft=True)
        except MemoryObservationActivationError as exc:
            if exc.code not in report_only_missing_codes:
                raise
            item = dict(raw)
            mint = str(item.get("mint") or "")
            pool = str(item.get("pool") or "")
            if not mint or not pool:
                raise MemoryObservationActivationError(
                    "ACTIVATION_MINT_MISSING" if not mint else "ACTIVATION_POOL_MISSING"
                ) from exc
            raw_authority = item.get("admission_authority")
            if raw_authority is None:
                raise MemoryObservationActivationError(
                    "ADMISSION_AUTHORITY_UNSUPPORTED", mint
                ) from exc
            try:
                admission_authority = AdmissionAuthority(str(raw_authority))
            except ValueError as authority_exc:
                raise MemoryObservationActivationError(
                    "ADMISSION_AUTHORITY_UNSUPPORTED",
                    str(raw_authority),
                ) from authority_exc
            claims_pump = (
                admission_authority is AdmissionAuthority.DIRECT_PUMP_PUMPSWAP
            )
            return FrozenMemoryActivationCandidate(
                slot_ordinal=ordinal,
                mint=mint,
                pool=pool,
                market_identity=str(
                    item.get("market_identity")
                    or f"solana-mainnet:pumpswap:{pool}"
                ),
                lifecycle_identity=(
                    GRADUATED_LIFECYCLE
                    if claims_pump
                    else "PRESENT_POOL_CONFIRMED"
                ),
                activation_route=_memory_observation_activation_route(
                    admission_authority=admission_authority,
                    carried_route=item.get("activation_route"),
                ),
                provenance=str(item.get("provenance") or ""),
                memory_observation_eligible=True,
                fully_eligible=False,
                holder_condition=str(item.get("holder_condition") or "UNKNOWN"),
                holder_evidence_status=str(
                    item.get("holder_evidence_status") or "UNKNOWN"
                ),
                future_action_eligibility=str(
                    item.get("future_action_eligibility") or "BLOCKED_OR_UNKNOWN"
                ),
                evidence_expires_at=str(
                    item.get("evidence_expires_at") or expires_at
                ),
                liquidity_observed_at=str(
                    item.get("liquidity_observed_at")
                    or (item.get("liquidity") or {}).get("liquidity_observed_at")
                    or frozen_at
                ),
                tracking_feasibility=TrackingFeasibility(
                    eligible=bool(item.get("tracking_handoff_eligible", True)),
                    reason_code=f"REPORT_ONLY_ALTERNATE:{exc.code}",
                    tracking_queue_id=None,
                    tracking_queue_status=None,
                    requalification_required=False,
                    cooldown_until=None,
                    assessed_at=frozen_at,
                ),
                retained_evidence_references=(),
                admission_authority=admission_authority,
                claims_pump_origin=claims_pump,
                claims_pumpswap_graduation=claims_pump,
            )

    selected = tuple(
        candidate(item, ordinal, soft=False)
        for ordinal, item in enumerate(frozen_reserve.selected, start=1)
    )
    alternates = tuple(
        report_only_alternate(item, ordinal)
        for ordinal, item in enumerate(frozen_reserve.alternates[:2], start=3)
    )
    return FrozenMemoryActivationSet(
        activation_purpose=ActivationPurpose.MEMORY_OBSERVATION,
        readiness_id=readiness_id,
        selection_seed=selection_seed,
        selected=selected,
        alternates=alternates,
        manifest_request_ids=tuple(manifest_by_id),
        manifest_transport_identity_keys=transport_keys,
        frozen_at=frozen_at,
        expires_at=expires_at,
        manifest_entries=tuple(typed_entries),
    )


@dataclass(frozen=True)
class ReadinessResult:
    status: str
    activated_slots: tuple[dict[str, Any], ...]
    pump_accounting: Mapping[str, Any]
    secondary_requested: int
    secondary_failures: int
    cancelled_dry_run_jobs: int
    summary: Mapping[str, Any]
    replay_new_source_calls: int


@dataclass(frozen=True)
class SnapshotReadinessResult:
    """Terminal record of one SNAPSHOT_READINESS boundary execution."""

    status: str
    preflight_status: str
    complete_bundle_count: int
    holder_eligible_count: int
    snapshot_bundles: tuple[Mapping[str, Any], ...]
    pump_accounting: Mapping[str, Any]
    secondary_requested: int
    secondary_failures: int
    report: Mapping[str, Any]
    report_sha256: str | None
    replay_deterministic: bool
    replay_new_source_calls: int
    cancelled_dry_run_jobs: int
    summary: Mapping[str, Any]
    blocked_reasons: tuple[str, ...]
    # Complete holder-stage result surface (IDs, coverage, accounting blocker,
    # governed request count, measured transport count).
    holder_context: Mapping[str, Any] = field(default_factory=dict)


def build_live_geckoterminal_base_adapter_factory(
    *, timeout_seconds: float = DEFAULT_CALL_TIMEOUT_SECONDS
) -> Any:
    """Return the live exact-pool GeckoTerminal base adapter factory.

    This is the committed live wiring the SNAPSHOT_READINESS mode uses for the
    readiness base snapshot. Offline proofs inject a fixture factory of the same
    shape instead; no live call is made in an offline lane.
    """
    from printer_v1.sources.geckoterminal import (
        build_geckoterminal_adapter,
        build_geckoterminal_pair_snapshot_transport,
    )

    def factory(
        *, pair_address: str, token_mint: str, timeout_seconds: float = timeout_seconds
    ) -> Any:
        return build_geckoterminal_adapter(
            enabled=True,
            fixture_transport=build_geckoterminal_pair_snapshot_transport(
                pair_address, token_mint, timeout_seconds=timeout_seconds
            ),
        )

    return factory


def _validate_fifteen_minute_database_target_binding(
    *,
    command: Any,
    cycle_id: str,
    selection_seed: str,
    operational_database_target_binding: Any | None,
    disposable_public_composition_proof_binding: Any | None,
    durable_expectation: Mapping[str, Any] | None,
    canonical_authoritative_db_path: str | Path,
) -> str | None:
    # Production binding has precedence and keeps its existing law unchanged.
    from printer_v1.db.migrate import (
        canonical_migration_count,
        canonical_migration_names,
    )
    from printer_v1.operator_cli.operational_database_target_binding import (
        validate_bound_operational_invocation,
        validate_disposable_public_composition_proof_invocation,
    )

    if operational_database_target_binding is not None:
        return validate_bound_operational_invocation(
            operational_database_target_binding,
            actual_db_path=command.db_path,
            canonical_authoritative_db_path=canonical_authoritative_db_path,
            migration_count=canonical_migration_count(),
            migration_head=canonical_migration_names()[-1],
            execution_id=selection_seed,
            campaign_id=command.campaign_id,
            campaign_run_id=command.run_id,
            cycle_id=cycle_id,
            configuration_id=command.configuration_id,
            durable_db_target_identity=command.db_target_identity,
            durable_expectation=durable_expectation,
        )
    if disposable_public_composition_proof_binding is not None:
        return validate_disposable_public_composition_proof_invocation(
            disposable_public_composition_proof_binding,
            expectation=durable_expectation,
            actual_db_path=command.db_path,
            canonical_authoritative_db_path=canonical_authoritative_db_path,
            execution_id=selection_seed,
            campaign_id=command.campaign_id,
            campaign_run_id=command.run_id,
            cycle_id=cycle_id,
            configuration_id=command.configuration_id,
            durable_db_target_identity=command.db_target_identity,
            fixture_composition_manifest_sha256=str(
                disposable_public_composition_proof_binding
                .fixture_composition_manifest_sha256
            ),
        )
    return validate_bound_operational_invocation(
        None,
        actual_db_path=command.db_path,
        canonical_authoritative_db_path=canonical_authoritative_db_path,
        migration_count=canonical_migration_count(),
        migration_head=canonical_migration_names()[-1],
        execution_id=selection_seed,
        campaign_id=command.campaign_id,
        campaign_run_id=command.run_id,
        cycle_id=cycle_id,
        configuration_id=command.configuration_id,
        durable_db_target_identity=command.db_target_identity,
        durable_expectation=durable_expectation,
    )


def operational_discovery_batch_identity_inputs() -> tuple[dict[str, str], str]:
    """The provider-contract versions and git identity of this campaign's batch.

    They are invocation-independent constants of the live operational owner, so
    the ordinary command can build a pre-lifecycle discovery-batch resolver that
    derives *byte-identical* canonical batch payload to the one the combined
    discovery executor will later derive from ``CombinedDiscoveryFixtures``.
    Both callers read them here so the two can never drift apart.
    """
    return (
        {
            "direct": CONTRACT_VERSION,
            "geckoterminal": _sd.SECONDARY_DISCOVERY_CONTRACT_VERSION,
        },
        f"live-operational:{CONTRACT_VERSION}",
    )


_FRESH_AGGREGATOR_CANONICAL_CHANNEL = "FRESH_AGGREGATOR_PROTOCOL_CONFIRMED"


def _canonical_pre_admission_channel_labels(candidate: Any) -> tuple[str, ...]:
    """Freeze canonical channel semantics without losing provider provenance."""
    authority = getattr(candidate, "admission_authority", None)
    authority_value = str(getattr(authority, "value", authority) or "")
    if authority_value == "MARKET_PRESENT_POOL":
        return (_FRESH_AGGREGATOR_CANONICAL_CHANNEL,)
    labels = tuple(
        sorted(
            {
                str(label)
                for label in getattr(candidate, "channels", ())
                if isinstance(label, str) and label
            }
        )
    )
    if not labels:
        raise LiveOperationalError("LATER_CYCLE_CHANNEL_PROVENANCE_MISSING")
    return labels


class AuthoritativeLiveOperationalCampaignOwner:
    """Sole internal live origin→lifecycle composition entry point (DI-only)."""

    def __init__(
        self,
        *,
        driver: OriginToLifecycleCampaignDriver | None = None,
        later_cycle_candidate_supply: Callable[..., LaterCycleCandidateSupply]
        | None = None,
    ) -> None:
        self._driver = driver or OriginToLifecycleCampaignDriver()
        self._later_cycle_candidate_supply = later_cycle_candidate_supply

    def _build_later_cycle_discovery_callback(
        self,
        *,
        db_path: str | Path | None = None,
        configuration_id: str | None = None,
        candidate_supply: Callable[..., LaterCycleCandidateSupply] | None = None,
    ) -> Callable[..., Any]:
        """Build the private proof-only later-cycle discovery seam.

        The callback remains fail-closed until a later focused TDD contract
        binds its exact inputs to the existing operational discovery/selection
        pipeline. Building it performs no source request, Scheduler work,
        DB mutation, lifecycle work, or controller invocation.
        """

        def _safe_supply_exception_identifier(exc: BaseException) -> str:
            def _normalize(value: object) -> str:
                raw = str(value).upper()
                normalized = "".join(
                    character
                    if (
                        "A" <= character <= "Z"
                        or "0" <= character <= "9"
                        or character == "_"
                    )
                    else "_"
                    for character in raw
                )
                while "__" in normalized:
                    normalized = normalized.replace("__", "_")
                return normalized.strip("_")

            safe_code = (
                exc.code
                if isinstance(
                    exc,
                    (
                        LiveOperationalError,
                        LiveTransportError,
                        PumpContractError,
                        OriginRegistryError,
                    ),
                )
                else None
            )
            if safe_code is not None:
                normalized_code = _normalize(safe_code)
                if normalized_code:
                    return normalized_code[:128]
            class_name = _normalize(exc.__class__.__name__) or "EXCEPTION"
            return f"LATER_CYCLE_SUPPLY_EXCEPTION_{class_name}"[:128]

        yielded_source_operations: dict[str, int] = {}

        def _one_shot(
            *,
            campaign_id: str,
            campaign_run_id: str,
            authoritative_factory_run_id: str,
            cycle_id: str,
            cycle_ordinal: int,
            cycle_cutoff: str,
            evaluated_at: str,
            selection_seed: str,
            source_governor: OwnerPort,
            central_scheduler: OwnerPort,
            admission_health: MultiCycleAdmissionHealth,
        ) -> Any:
            from printer_v1.operator_cli.four_token_proof_integration import (
                LaterCycleCandidateSupply,
                LaterCycleDiscoveryAttemptResult,
            )
            from printer_v1.operator_cli.later_cycle_graduated_supply import (
                classify_later_cycle_failure,
            )
            from printer_v1.db.sqlite_write_contracts import connect_operational
            from printer_v1.operator_cli.pre_admission_discovery_attempt import (
                PreAdmissionAttemptError,
                PreAdmissionAttemptItem,
                PreAdmissionAttemptState,
                attach_frozen_tracking_lane,
                create_scheduled_pre_admission_attempt,
                link_pre_admission_source_evidence,
                load_pre_admission_attempt,
                mark_pre_admission_attempt_running,
                persist_pre_admission_pair,
                pre_admission_persistence_diagnostic_for_exception,
                pre_admission_attempt_lock_owner,
                terminalize_pre_admission_attempt,
            )
            from printer_v1.operator_cli.pre_admission_attempt_evidence import (
                rebuild_exhaustion_certificate_from_attempt_evidence,
                record_later_cycle_supply_evidence,
            )
            from printer_v1.scheduler.scheduler import (
                cancel_job,
                claim_due_job,
                complete_job,
                discard_job_failure_diagnostic,
                fail_job,
                stage_job_failure_diagnostic,
                yield_job,
            )
            from printer_v1.discovery.pre_lifecycle_temporal_acquisition import (
                WAITING_FOR_ELIGIBLE_SUPPLY,
            )
            from printer_v1.discovery.eligible_token_supply import (
                ACQUISITION_QUANTUM_YIELDED,
                persist_exhaustion_certificate,
            )

            if db_path is None or configuration_id is None:
                raise LiveOperationalError("LATER_CYCLE_DISCOVERY_CALLBACK_NOT_WIRED")
            if (
                not isinstance(admission_health, MultiCycleAdmissionHealth)
                or source_governor.owner_kind != SOURCE_GOVERNOR_OWNER
                or not source_governor.available
                or central_scheduler.owner_kind != CENTRAL_SCHEDULER_OWNER
                or not central_scheduler.available
                or type(cycle_ordinal) is not int
                or cycle_ordinal != 2
            ):
                raise LiveOperationalError("LATER_CYCLE_CONTEXT_INVALID")
            try:
                instant = datetime.fromisoformat(evaluated_at.replace("Z", "+00:00"))
                cutoff = datetime.fromisoformat(cycle_cutoff.replace("Z", "+00:00"))
            except (TypeError, ValueError) as exc:
                raise LiveOperationalError("LATER_CYCLE_CONTEXT_INVALID") from exc
            attempt_id = (
                f"pre-admission:{campaign_id}:{campaign_run_id}:"
                f"{authoritative_factory_run_id}:c{cycle_ordinal:04d}"
            )
            connection = connect_operational(db_path)
            attempt = None
            blocked_domain = None
            try:
                try:
                    existing = load_pre_admission_attempt(
                        connection, attempt_id=attempt_id
                    )
                except PreAdmissionAttemptError as exc:
                    if str(exc) != "ATTEMPT_NOT_FOUND":
                        raise
                    existing = None
                if (
                    existing is not None
                    and existing.state is not PreAdmissionAttemptState.RUNNING
                ):
                    return LaterCycleDiscoveryAttemptResult(
                        attempt_id=existing.attempt_id,
                        state=existing.state.value,
                        first_terminal_cause=str(existing.first_terminal_cause or ""),
                        selected_count=(2 if existing.state in {
                            PreAdmissionAttemptState.PAIR_READY,
                            PreAdmissionAttemptState.CONSUMED,
                        } else 0),
                        failure_domain=classify_later_cycle_failure(
                            terminal_cause=str(existing.first_terminal_cause or "")
                        )
                        if existing.state
                        not in {
                            PreAdmissionAttemptState.PAIR_READY,
                            PreAdmissionAttemptState.CONSUMED,
                        }
                        else None,
                    )
                if existing is None:
                    owner = connection.execute(
                        """SELECT 1 FROM printer_memory_factory_campaign_runs
                           WHERE run_id=? AND campaign_id=? AND authoritative_run_id=?""",
                        (campaign_run_id, campaign_id, authoritative_factory_run_id),
                    ).fetchone()
                    if owner is None:
                        raise LiveOperationalError("LATER_CYCLE_CONTEXT_INVALID")
                    attempt = create_scheduled_pre_admission_attempt(
                        connection,
                        attempt_id=attempt_id,
                        campaign_id=campaign_id,
                        campaign_run_id=campaign_run_id,
                        configuration_id=configuration_id,
                        authoritative_factory_run_id=authoritative_factory_run_id,
                        proposed_cycle_ordinal=cycle_ordinal,
                        proposed_cycle_id=cycle_id,
                        cycle_cutoff=cutoff,
                        evaluated_at=instant,
                        selection_seed_identity=selection_seed,
                        scheduled_for=instant,
                        now=instant,
                    )
                else:
                    attempt = existing
                claimed = claim_due_job(
                    connection,
                    job_id=attempt.scheduler_job_id,
                    lock_owner=pre_admission_attempt_lock_owner(attempt_id),
                    now=instant,
                )
                if claimed.value != "ACQUIRED":
                    terminalize_pre_admission_attempt(
                        connection,
                        attempt_id=attempt_id,
                        state=PreAdmissionAttemptState.BLOCKED,
                        cause="PRE_ADMISSION_SCHEDULER_CLAIM_BLOCKED",
                        now=instant,
                    )
                    cancel_job(connection, job_id=attempt.scheduler_job_id, now=instant)
                else:
                    if attempt.state is PreAdmissionAttemptState.PLANNED:
                        mark_pre_admission_attempt_running(
                            connection, attempt_id=attempt_id, now=instant
                        )
                    supply_owner = candidate_supply or self._later_cycle_candidate_supply
                    if supply_owner is None:
                        terminalize_pre_admission_attempt(
                            connection,
                            attempt_id=attempt_id,
                            state=PreAdmissionAttemptState.BLOCKED,
                            cause="LATER_CYCLE_CANDIDATE_SUPPLY_NOT_WIRED",
                            now=instant,
                        )
                        cancel_job(
                            connection, job_id=attempt.scheduler_job_id, now=instant
                        )
                    else:
                        connection.commit()
                        connection.close()

                        try:
                            supply = supply_owner(
                                campaign_id=campaign_id,
                                campaign_run_id=campaign_run_id,
                                authoritative_factory_run_id=authoritative_factory_run_id,
                                proposed_cycle_id=cycle_id,
                                proposed_cycle_ordinal=cycle_ordinal,
                                cycle_cutoff=cutoff,
                                evaluated_at=instant,
                                selection_seed=selection_seed,
                                source_governor=source_governor,
                                central_scheduler=central_scheduler,
                                admission_health=admission_health,
                            )
                        except Exception as supply_exc:
                            failure_cause = _safe_supply_exception_identifier(supply_exc)
                            connection = connect_operational(db_path)
                            current = load_pre_admission_attempt(
                                connection, attempt_id=attempt.attempt_id
                            )
                            job = connection.execute(
                                "SELECT job_kind,status,locked_at,lock_owner "
                                "FROM printer_scheduler_jobs WHERE id=?",
                                (attempt.scheduler_job_id,),
                            ).fetchone()
                            expected_lock_owner = pre_admission_attempt_lock_owner(
                                attempt.attempt_id
                            )
                            if (
                                current.state is not PreAdmissionAttemptState.RUNNING
                                or current.scheduler_job_id != attempt.scheduler_job_id
                                or job is None
                                or str(job["job_kind"])
                                != "PRE_ADMISSION_DISCOVERY_SELECTION"
                                or str(job["status"]) != "RUNNING"
                                or job["locked_at"] is None
                                or str(job["lock_owner"] or "") != expected_lock_owner
                            ):
                                if connection.in_transaction:
                                    connection.rollback()
                                raise LiveOperationalError(
                                    "LATER_CYCLE_PRE_ADMISSION_AUTHORITY_DRIFT"
                                )
                            terminalize_pre_admission_attempt(
                                connection,
                                attempt_id=attempt.attempt_id,
                                state=PreAdmissionAttemptState.FAILED,
                                cause=failure_cause,
                                now=instant,
                            )
                            fail_job(
                                connection,
                                job_id=attempt.scheduler_job_id,
                                error=failure_cause,
                                now=instant,
                                max_retries=0,
                            )
                            connection.commit()
                            final = load_pre_admission_attempt(
                                connection, attempt_id=attempt.attempt_id
                            )
                            return LaterCycleDiscoveryAttemptResult(
                                attempt_id=final.attempt_id,
                                state=final.state.value,
                                first_terminal_cause=str(
                                    final.first_terminal_cause or ""
                                ),
                                selected_count=0,
                                failure_domain=classify_later_cycle_failure(
                                    exception=supply_exc,
                                    terminal_cause=str(
                                        final.first_terminal_cause or failure_cause
                                    ),
                                ),
                            )

                        connection = connect_operational(db_path)
                        current = load_pre_admission_attempt(
                            connection, attempt_id=attempt.attempt_id
                        )
                        job = connection.execute(
                            "SELECT job_kind,status,locked_at,lock_owner "
                            "FROM printer_scheduler_jobs WHERE id=?",
                            (attempt.scheduler_job_id,),
                        ).fetchone()
                        expected_lock_owner = pre_admission_attempt_lock_owner(
                            attempt.attempt_id
                        )
                        if (
                            current.state is not PreAdmissionAttemptState.RUNNING
                            or current.scheduler_job_id != attempt.scheduler_job_id
                            or job is None
                            or str(job["job_kind"])
                            != "PRE_ADMISSION_DISCOVERY_SELECTION"
                            or str(job["status"]) != "RUNNING"
                            or job["locked_at"] is None
                            or str(job["lock_owner"] or "") != expected_lock_owner
                        ):
                            if connection.in_transaction:
                                connection.rollback()
                            raise LiveOperationalError(
                                "LATER_CYCLE_PRE_ADMISSION_AUTHORITY_DRIFT"
                            )

                        if not isinstance(supply, LaterCycleCandidateSupply):
                            raise LiveOperationalError("LATER_CYCLE_SUPPLY_RESULT_INVALID")
                        diagnostics = dict(supply.diagnostics or {})
                        reported_operations = diagnostics.get(
                            "stage_local_source_requests"
                        )
                        if reported_operations is not None:
                            if (
                                isinstance(reported_operations, bool)
                                or not isinstance(reported_operations, int)
                                or reported_operations < yielded_source_operations.get(
                                    attempt_id, 0
                                )
                            ):
                                raise LiveOperationalError(
                                    "LATER_CYCLE_CUMULATIVE_BUDGET_REGRESSION"
                                )
                        if supply.terminal_cause in {
                            WAITING_FOR_ELIGIBLE_SUPPLY,
                            ACQUISITION_QUANTUM_YIELDED,
                        }:
                            if (
                                supply.candidates
                                or diagnostics.get("shortage_classification")
                                or int(diagnostics.get("provider_failures") or 0) != 0
                                or supply.failure_domain is not None
                            ):
                                raise LiveOperationalError(
                                    "LATER_CYCLE_SCHEDULER_YIELD_INVALID"
                                )
                            seen_yield_evidence: set[
                                tuple[int, int | None, int | None]
                            ] = set()
                            for evidence in supply.source_evidence:
                                identity = (
                                    int(evidence.source_request_id),
                                    evidence.source_response_id,
                                    evidence.source_failure_id,
                                )
                                if identity in seen_yield_evidence:
                                    raise LiveOperationalError(
                                        "LATER_CYCLE_SCHEDULER_YIELD_INVALID"
                                    )
                                seen_yield_evidence.add(identity)
                                durable = connection.execute(
                                    """SELECT r.id,
                                              EXISTS(SELECT 1 FROM printer_source_responses s
                                                     WHERE s.id=? AND s.source_request_id=r.id),
                                              EXISTS(SELECT 1 FROM printer_source_failures f
                                                     WHERE f.id=? AND f.source_request_id=r.id)
                                       FROM printer_source_requests r WHERE r.id=?""",
                                    (
                                        evidence.source_response_id,
                                        evidence.source_failure_id,
                                        evidence.source_request_id,
                                    ),
                                ).fetchone()
                                if (
                                    durable is None
                                    or (
                                        evidence.source_response_id is None
                                        and evidence.source_failure_id is None
                                    )
                                    or (
                                        evidence.source_response_id is not None
                                        and evidence.source_failure_id is not None
                                    )
                                    or (
                                        evidence.source_response_id is not None
                                        and not durable[1]
                                    )
                                    or (
                                        evidence.source_failure_id is not None
                                        and not durable[2]
                                    )
                                ):
                                    raise LiveOperationalError(
                                        "LATER_CYCLE_SCHEDULER_YIELD_INVALID"
                                    )
                            record_later_cycle_supply_evidence(
                                connection,
                                attempt_id=attempt_id,
                                supply=supply,
                                observed_at=instant.isoformat(),
                            )
                            yielded_source_operations[attempt_id] = int(
                                reported_operations or 0
                            )
                            yield_job(
                                connection,
                                job_id=attempt.scheduler_job_id,
                                scheduled_for=instant,
                                now=instant,
                            )
                            connection.commit()
                            return LaterCycleDiscoveryAttemptResult(
                                attempt_id=attempt.attempt_id,
                                state=PreAdmissionAttemptState.RUNNING.value,
                                first_terminal_cause="",
                                selected_count=0,
                                failure_domain=None,
                            )
                        reduced_attempt_evidence = record_later_cycle_supply_evidence(
                            connection,
                            attempt_id=attempt_id,
                            supply=supply,
                            observed_at=instant.isoformat(),
                        )
                        certificate = diagnostics.get("exhaustion_certificate")
                        if isinstance(certificate, Mapping):
                            rebuilt_certificate = (
                                rebuild_exhaustion_certificate_from_attempt_evidence(
                                    certificate,
                                    reduced_attempt_evidence,
                                )
                            )
                            certificate_id = str(
                                rebuilt_certificate.get("certificate_id") or ""
                            )
                            if not certificate_id:
                                raise LiveOperationalError(
                                    "LATER_CYCLE_EXHAUSTION_CERTIFICATE_ID_MISSING"
                                )
                            rebuilt_json = json.dumps(
                                rebuilt_certificate, sort_keys=True
                            )
                            existing_certificate = connection.execute(
                                """SELECT campaign_id,execution_id,run_id,cycle_id,
                                          certificate_json
                                     FROM printer_discovery_exhaustion_certificates
                                    WHERE certificate_id=?""",
                                (certificate_id,),
                            ).fetchone()
                            if existing_certificate is None:
                                # Normal cooperative production path: local supply
                                # persistence was deferred, so the attempt-wide
                                # reducer owns the first durable certificate write.
                                persist_exhaustion_certificate(
                                    connection, rebuilt_certificate
                                )
                            else:
                                # Compatibility for an exact preexisting local
                                # certificate (including historical/injected paths).
                                # Never overwrite a different identity or unknown
                                # payload under the same certificate id.
                                expected_identity = tuple(
                                    str(rebuilt_certificate.get(key) or "")
                                    for key in (
                                        "campaign_id",
                                        "execution_id",
                                        "run_id",
                                        "cycle_id",
                                    )
                                )
                                observed_identity = tuple(
                                    str(existing_certificate[index] or "")
                                    for index in range(4)
                                )
                                if observed_identity != expected_identity:
                                    raise LiveOperationalError(
                                        "LATER_CYCLE_EXHAUSTION_CERTIFICATE_IDENTITY_CONFLICT"
                                    )
                                existing_json = str(existing_certificate[4] or "")
                                if existing_json != rebuilt_json:
                                    original_json = json.dumps(
                                        dict(certificate), sort_keys=True
                                    )
                                    if existing_json != original_json:
                                        raise LiveOperationalError(
                                            "LATER_CYCLE_EXHAUSTION_CERTIFICATE_CAS_FAILED"
                                        )
                                    updated = connection.execute(
                                        """UPDATE printer_discovery_exhaustion_certificates
                                              SET certificate_json=?
                                            WHERE certificate_id=? AND certificate_json=?""",
                                        (rebuilt_json, certificate_id, original_json),
                                    )
                                    if updated.rowcount != 1:
                                        raise LiveOperationalError(
                                            "LATER_CYCLE_EXHAUSTION_CERTIFICATE_CAS_FAILED"
                                        )
                            diagnostics["exhaustion_certificate"] = rebuilt_certificate
                            supply = replace(supply, diagnostics=diagnostics)
                        yielded_source_operations.pop(attempt_id, None)
                        for ordinal, evidence in enumerate(supply.source_evidence, start=1):
                            link_pre_admission_source_evidence(
                                connection,
                                attempt_id=attempt_id,
                                link_ordinal=ordinal,
                                logical_stage=evidence.logical_stage,
                                source_request_id=evidence.source_request_id,
                                source_response_id=evidence.source_response_id,
                                source_failure_id=evidence.source_failure_id,
                                now=instant,
                            )
                        market_authority_mints = frozenset(
                            item.mint_identity
                            for item in supply.candidates
                            if item.admission_authority.value
                            == "MARKET_PRESENT_POOL"
                        )
                        gate_candidates = tuple(
                            DiscoverySelectionCandidate(
                                merged_candidate_id=f"pre-admission:{item.mint_identity}",
                                mint=item.mint_identity,
                                market_identity=item.canonical_market_identity,
                                lifecycle=item.lifecycle_identity,
                                channels=set(item.channels),
                                observation_ids=[f"pre-admission:{item.mint_identity}"],
                                conflicts=[],
                                gaps=([] if item.holder_evidence_eligible else [
                                    {"kind": "HOLDER_EVIDENCE_INELIGIBLE"}
                                ]),
                                origin_state=(
                                    "NOT_REQUIRED"
                                    if item.mint_identity in market_authority_mints
                                    else "CONFIRMED"
                                ),
                                pumpswap_state=(
                                    "NOT_REQUIRED"
                                    if item.mint_identity in market_authority_mints
                                    else "CONFIRMED"
                                ),
                            )
                            for item in supply.candidates
                        )
                        selected_outcome = apply_existing_discovery_gate_and_selection(
                            connection,
                            candidates=gate_candidates,
                            discovery_batch_id=attempt_id,
                            evaluated_at=instant,
                            mode="INITIAL",
                            vacant_slot_ordinals=(1, 2),
                            batch_seq=2,
                            cycle_seed=selection_seed,
                            handoffs_used=0,
                            market_authority_mints=market_authority_mints,
                        )
                        by_mint = {item.mint_identity: item for item in supply.candidates}
                        selected = [by_mint[item.mint] for item in selected_outcome.selected]
                        blocked_domain = None
                        if len(selected) == 2:
                            persist_pre_admission_pair(
                                connection,
                                attempt_id=attempt_id,
                                items=tuple(
                                    attach_frozen_tracking_lane(
                                        PreAdmissionAttemptItem(
                                            attempt_id=attempt_id,
                                            slot_ordinal=ordinal,
                                            token_identity=item.token_identity,
                                            token_row_id=item.token_row_id,
                                            mint_identity=item.mint_identity,
                                            pair_identity=item.pair_identity,
                                            pair_row_id=item.pair_row_id,
                                            lifecycle_identity=item.lifecycle_identity,
                                            canonical_market_identity=item.canonical_market_identity,
                                            canonical_pool_identity=item.canonical_pool_identity,
                                            canonical_evidence_json=item.canonical_evidence_json,
                                            canonical_evidence_hash=item.canonical_evidence_hash,
                                            evidence_version=item.evidence_version,
                                            observed_at=item.observed_at,
                                            channel_labels=_canonical_pre_admission_channel_labels(
                                                item
                                            ),
                                        ),
                                        now=instant,
                                        connection=connection,
                                    )
                                    for ordinal, item in enumerate(selected, start=1)
                                ),
                                now=instant,
                            )
                        else:
                            # A supply that carried its shortage classification
                            # is mapped by the single authoritative owner, so a
                            # non-market shortage can never be terminalized as a
                            # market conclusion. Without a classification the
                            # existing cause is preserved exactly.
                            supply_diagnostics = dict(
                                getattr(supply, "diagnostics", {}) or {}
                            )
                            if supply_diagnostics.get("shortage_classification"):
                                blocked_cause = _graduated_supply_terminal_cause(
                                    supply
                                )
                            else:
                                blocked_cause = (
                                    supply.terminal_cause or "NO_EXACT_PAIR"
                                )
                            blocked_domain = classify_later_cycle_failure(
                                shortage_classification=str(
                                    supply_diagnostics.get("shortage_classification")
                                    or ""
                                )
                                or None,
                                terminal_cause=blocked_cause,
                            )
                            if getattr(supply, "failure_domain", None):
                                blocked_domain = str(supply.failure_domain)
                            terminalize_pre_admission_attempt(
                                connection,
                                attempt_id=attempt_id,
                                state=PreAdmissionAttemptState.NO_PAIR,
                                cause=blocked_cause,
                                now=instant,
                            )
                        complete_job(
                            connection,
                            job_id=attempt.scheduler_job_id,
                            now=instant,
                        )
                    connection.commit()
                final = load_pre_admission_attempt(connection, attempt_id=attempt_id)
                return LaterCycleDiscoveryAttemptResult(
                    attempt_id=final.attempt_id,
                    state=final.state.value,
                    first_terminal_cause=str(final.first_terminal_cause or ""),
                    selected_count=(2 if final.state is PreAdmissionAttemptState.PAIR_READY else 0),
                    failure_domain=(
                        None
                        if final.state is PreAdmissionAttemptState.PAIR_READY
                        else blocked_domain
                        or classify_later_cycle_failure(
                            terminal_cause=str(final.first_terminal_cause or "")
                        )
                    ),
                )
            except PreAdmissionAttemptError as exc:
                if attempt is not None:
                    current = load_pre_admission_attempt(
                        connection, attempt_id=attempt.attempt_id
                    )
                    job = connection.execute(
                        "SELECT job_kind,status,locked_at,lock_owner "
                        "FROM printer_scheduler_jobs WHERE id=?",
                        (attempt.scheduler_job_id,),
                    ).fetchone()
                    expected_lock_owner = pre_admission_attempt_lock_owner(
                        attempt.attempt_id
                    )
                    if (
                        current.state is PreAdmissionAttemptState.RUNNING
                        and current.scheduler_job_id == attempt.scheduler_job_id
                        and job is not None
                        and str(job["job_kind"])
                        == "PRE_ADMISSION_DISCOVERY_SELECTION"
                        and str(job["status"]) == "RUNNING"
                        and job["locked_at"] is not None
                        and str(job["lock_owner"] or "") == expected_lock_owner
                    ):
                        failure_code = "LATER_CYCLE_ATTEMPT_PERSISTENCE_FAILED"
                        diagnostic = (
                            exc.diagnostic
                            or pre_admission_persistence_diagnostic_for_exception(exc)
                        )
                        stage_job_failure_diagnostic(
                            job_id=attempt.scheduler_job_id,
                            failure_code=failure_code,
                            context=diagnostic.as_dict(),
                        )
                        try:
                            terminalize_pre_admission_attempt(
                                connection,
                                attempt_id=attempt.attempt_id,
                                state=PreAdmissionAttemptState.FAILED,
                                cause=failure_code,
                                now=instant,
                            )
                            fail_job(
                                connection,
                                job_id=attempt.scheduler_job_id,
                                error=failure_code,
                                now=instant,
                                max_retries=0,
                            )
                            connection.commit()
                        except Exception as secondary:
                            discard_job_failure_diagnostic(
                                job_id=attempt.scheduler_job_id
                            )
                            try:
                                if connection.in_transaction:
                                    connection.rollback()
                            except Exception as rollback_secondary:
                                raise exc from rollback_secondary
                            raise exc from secondary
                        final = load_pre_admission_attempt(
                            connection, attempt_id=attempt.attempt_id
                        )
                        return LaterCycleDiscoveryAttemptResult(
                            attempt_id=final.attempt_id,
                            state=final.state.value,
                            first_terminal_cause=str(final.first_terminal_cause or ""),
                            selected_count=0,
                            failure_domain=classify_later_cycle_failure(
                                exception=exc,
                                terminal_cause=str(final.first_terminal_cause or ""),
                            ),
                        )
                connection.rollback()
                raise LiveOperationalError(str(exc)) from exc
            except Exception as exc:
                if (
                    isinstance(exc, LiveOperationalError)
                    and exc.code == "LATER_CYCLE_PRE_ADMISSION_AUTHORITY_DRIFT"
                ):
                    if connection.in_transaction:
                        connection.rollback()
                    raise
                if attempt is not None:
                    current = load_pre_admission_attempt(
                        connection, attempt_id=attempt.attempt_id
                    )
                    if current.state is PreAdmissionAttemptState.RUNNING:
                        terminalize_pre_admission_attempt(
                            connection,
                            attempt_id=attempt.attempt_id,
                            state=PreAdmissionAttemptState.FAILED,
                            cause="LATER_CYCLE_SUPPLY_FAILED",
                            now=instant,
                        )
                        fail_job(
                            connection,
                            job_id=attempt.scheduler_job_id,
                            error="LATER_CYCLE_SUPPLY_FAILED",
                            now=instant,
                            max_retries=0,
                        )
                        connection.commit()
                        final = load_pre_admission_attempt(
                            connection, attempt_id=attempt.attempt_id
                        )
                        return LaterCycleDiscoveryAttemptResult(
                            attempt_id=final.attempt_id,
                            state=final.state.value,
                            first_terminal_cause=str(final.first_terminal_cause or ""),
                            selected_count=0,
                            failure_domain=classify_later_cycle_failure(
                                exception=exc,
                                terminal_cause=str(final.first_terminal_cause or ""),
                            ),
                        )
                connection.rollback()
                raise
            finally:
                connection.close()

        return _one_shot

    def _build_fixtures(
        self,
        *,
        pump_transport: PumpRpcTransport,
        secondary_transport: SecondaryHttpTransport | None,
        source_governor: OwnerPort,
        central_scheduler: OwnerPort,
        cycle_id: str,
        cycle_cutoff: str,
        selection_seed: str,
        evaluated_at: str,
        prior_cursor: FinalizedOriginCursor | None,
        timeout_seconds: float,
        byte_ceiling: int,
        tracker_api_key: str | None,
        graduation_native_only: bool = False,
    ) -> tuple[CombinedDiscoveryFixtures, LivePumpAcquisition, LiveSecondaryEnrichment]:
        if graduation_native_only:
            acquisition = LivePumpAcquisition(
                result=AcquisitionCycleResult(
                    index_address=PUMP_CREATE_INDEX_ADDRESS,
                    anchor=None,
                    observations=(),
                    rejections=(),
                    cursor=FinalizedOriginCursor(None),
                    accounting=AccountingSnapshot({}, 0),
                ),
                origin_proofs=(),
            )
        else:
            pump = LivePumpOriginAdapter(
                pump_transport,
                timeout_seconds=timeout_seconds,
                byte_ceiling=byte_ceiling,
            )
            acquisition = pump.acquire(
                source_governor=source_governor,
                central_scheduler=central_scheduler,
                prior_cursor=prior_cursor,
            )
        enrichment = LiveSecondaryEnrichment()
        if secondary_transport is not None and not graduation_native_only:
            secondary = LiveSecondaryDiscoveryAdapter(
                secondary_transport,
                timeout_seconds=timeout_seconds,
                byte_ceiling=byte_ceiling,
                tracker_api_key=tracker_api_key,
            )
            enrichment = secondary.enrich(
                source_governor=source_governor,
                central_scheduler=central_scheduler,
                receipt_time=evaluated_at,
                active_pools=[proof.bonding_curve for proof in acquisition.origin_proofs],
            )
        batch_contract_versions, batch_git_identity = (
            operational_discovery_batch_identity_inputs()
        )
        fixtures = CombinedDiscoveryFixtures(
            cycle_id=cycle_id,
            cycle_cutoff=cycle_cutoff,
            campaign_selection_seed=selection_seed,
            provider_contract_versions=batch_contract_versions,
            git_provenance_identity=batch_git_identity,
            evaluated_at=evaluated_at,
            direct_observations=acquisition.origin_proofs,
            gecko_ops=enrichment.gecko_ops,
            tracker_ops=enrichment.tracker_ops,
            dexscreener_ops=enrichment.dexscreener_ops,
        )
        return fixtures, acquisition, enrichment

    def _evaluate_holder_eligibility(
        self,
        connection: sqlite3.Connection,
        *,
        command: AbstractCampaignCommand,
        cycle_id: str,
        bounded_candidates: Sequence[Any],
        evaluated: datetime,
        deadline: datetime,
        ledger: Any,
        timeout_seconds: float,
        context_factories: Any,
        request_pacer: Any,
        partition_by_mint: Mapping[str, str] | None = None,
        tracking_pair_by_mint: Mapping[str, str] | None = None,
        eligible_target: int = 2,
        permanent_memory_observation: bool = False,
        holder_transport_identity_observer: Any | None = None,
        holder_stage_evidence_sealer: Any | None = None,
        campaign_request_key_root: str | None = None,
    ) -> Any:
        """Shared pre-activation holder-eligibility funnel.

        The single committed implementation used by BOTH the full operational
        campaign and the snapshot-readiness boundary. It admits candidates
        against the operation ledger, replays matured evidence, collects the
        governed GoPlus/RPC/Helius holder bundle through the existing owners, and
        derives per-candidate eligibility. It stops after ``eligible_target``
        candidates. No lifecycle, memory, retrieval or financial work occurs.

        Returns a single ``HolderContextResult`` owning holder facts, the ledger,
        durable source request IDs, stage coverage, and accounting-blocker state.
        """
        from printer_v1.operator_cli.one_command_15m_factory import (
            PrecloseContextPartialError,
            _collect_preclose_context,
        )
        from printer_v1.operator_cli.holder_reliability_budget_control import (
            HolderBundlePersistPartialError,
            HolderContextResult,
            complete_maturation,
            holder_attempt_admission,
            persist_bundle_attempts,
            persist_ledger,
            reuse_holder_fact,
            schedule_maturation,
            SequentialRequestPacer,
        )
        from printer_v1.lifecycle.tracking_queue import (
            assess_possible_tracking_claim_by_identity,
        )
        holder_facts: dict[str, Mapping[str, Any]] = {}
        accepted_partitions: set[str] = set()
        required_partitions = set((partition_by_mint or {}).values())
        pacer = request_pacer or SequentialRequestPacer()
        campaign_id = str(getattr(command, "campaign_id", None) or "")
        stage_request_ids: list[int] = []
        stage_coverage: list[Mapping[str, Any]] = []
        stage_governed = 0
        stage_transports = 0
        accounting_blocker = False
        accounting_reasons: list[str] = []
        ledger_before_holder = ledger
        evaluated_candidate_mints: list[str] = []
        unattempted_candidate_mints: list[str] = []
        budget_exhausted = False
        budget_exhaustion_reason: str | None = None
        holder_attempt_budget_trace: list[dict[str, Any]] = []
        from printer_v1.sources.measured_transport import MeasuredTransportLedger
        holder_transport_ledger = MeasuredTransportLedger(
            campaign_id=campaign_id or None,
            run_id=command.run_id,
            cycle_id=cycle_id,
            on_transport_recorded=holder_transport_identity_observer,
        )
        require_exact_holder_identities = holder_stage_evidence_sealer is not None
        campaign_root = str(campaign_request_key_root or "").strip()
        if permanent_memory_observation and not campaign_root:
            raise LiveOperationalError(
                "CAMPAIGN_SOURCE_REQUEST_SCOPE_ROOT_MISSING",
                "holder eligibility",
            )
        persist_ledger(
            connection, run_id=command.run_id, cycle_id=cycle_id,
            ledger=ledger, now=evaluated.isoformat(),
        )
        from printer_v1.db.sqlite_write_contracts import release_write_transaction

        for ordinal, proof in enumerate(bounded_candidates, start=1):
            partition = (partition_by_mint or {}).get(proof.mint.lower())
            if partition is not None and partition in accepted_partitions:
                continue
            # Lane-agnostic possible-claim: do not invent NORMAL. A NORMAL-only
            # conflict must not deny a still-claimable FAST identity. Exact lane
            # is frozen later from truthful classification.
            handoff = assess_possible_tracking_claim_by_identity(
                connection,
                token_mint=proof.mint,
                pair_address=(tracking_pair_by_mint or {}).get(
                    proof.mint.lower(), proof.bonding_curve
                ),
                assessed_at=evaluated,
            )
            handoff_detail = {
                "tracking_handoff_eligible": handoff.eligible,
                "tracking_handoff_reason": handoff.reason_code,
                "tracking_handoff_category": handoff.category,
                "tracking_queue_id": handoff.queue_id,
                "tracking_queue_status": handoff.queue_status,
                "tracking_requalification_required": (
                    handoff.requalification_eligible
                ),
                "cooldown_until": handoff.cooldown_until,
                "historical_cooldown_expiry_derived": (
                    handoff.historical_cooldown_expiry_derived
                ),
                "tracking_assessed_at": evaluated.isoformat(),
            }
            if not handoff.eligible:
                holder_facts[proof.mint.lower()] = {
                    "eligible": False,
                    "reason": handoff.reason_code,
                    "source_name": None,
                    **handoff_detail,
                }
                continue
            attempt_trace: dict[str, Any] | None = None
            if permanent_memory_observation:
                admission_decision = holder_attempt_admission(
                    ledger,
                    now=evaluated,
                    permanent_stage_operations_used=stage_transports,
                )
                attempt_trace = {
                    "mint": proof.mint.lower(),
                    "allowed": admission_decision.allowed,
                    "reason": admission_decision.reason,
                    "available_operations": admission_decision.available_operations,
                    "required_worst_case_operations": (
                        admission_decision.required_worst_case_operations
                    ),
                    "permanent_stage_operations_used": (
                        admission_decision.permanent_stage_operations_used
                    ),
                    "permanent_stage_operations_remaining": (
                        admission_decision.permanent_stage_operations_remaining
                    ),
                    "deadline_expired": admission_decision.deadline_expired,
                    "ledger_before_attempt": ledger.budget_detail(),
                    "attempted": False,
                }
                holder_attempt_budget_trace.append(attempt_trace)
                if not admission_decision.allowed:
                    budget_exhausted = True
                    budget_exhaustion_reason = admission_decision.reason
                    for remaining in bounded_candidates[ordinal - 1 :]:
                        mint_key = remaining.mint.lower()
                        if mint_key in holder_facts:
                            continue
                        unattempted_candidate_mints.append(mint_key)
                        holder_facts[mint_key] = {
                            "eligible": False,
                            "holder_condition": "UNKNOWN",
                            "holder_evidence_status": (
                                "SOURCE_NOT_EVALUATED_BUDGET_BOUND"
                            ),
                            "future_action_eligibility": "BLOCKED_OR_UNKNOWN",
                            "source_name": None,
                            "source_request_ids": [],
                        }
                    attempt_trace["ledger_after_attempt"] = ledger.budget_detail()
                    break
            else:
                ledger.admit_candidate(now=evaluated)
            # Resolve source-honest observation time before maturation and
            # before any holder provider transport.
            observed_at_utc = self._resolve_holder_maturation_observed_at(proof)
            maturation = schedule_maturation(
                connection, run_id=command.run_id, cycle_id=cycle_id,
                mint=proof.mint, observed_at=observed_at_utc,
                now=evaluated.isoformat(), deadline_at=deadline.isoformat(),
            )
            if maturation["work_state"] != "DUE":
                holder_facts[proof.mint.lower()] = {
                    "eligible": False,
                    "reason": f"HOLDER_MATURATION_{maturation['work_state']}",
                    "source_name": None,
                    **handoff_detail,
                }
                if attempt_trace is not None:
                    attempt_trace["ledger_after_attempt"] = ledger.budget_detail()
                continue
            try:
                evaluated_candidate_mints.append(proof.mint.lower())
                reused_fact = reuse_holder_fact(
                    connection, run_id=command.run_id, cycle_id=cycle_id,
                    mint=proof.mint, evaluated_at=evaluated.isoformat(),
                )
                if reused_fact is not None:
                    holder_facts[proof.mint.lower()] = {
                        **dict(reused_fact),
                        **handoff_detail,
                    }
                    ledger = replace(
                        ledger,
                        zero_transport_operations=ledger.zero_transport_operations + 1,
                    )
                    persist_ledger(
                        connection, run_id=command.run_id, cycle_id=cycle_id,
                        ledger=ledger, now=evaluated.isoformat(),
                    )
                    complete_maturation(
                        connection, work_id=str(maturation["work_id"]),
                        cause="EVIDENCE_REUSED", now=evaluated.isoformat(),
                    )
                    if attempt_trace is not None:
                        attempt_trace["attempted"] = True
                        attempt_trace["evidence_reused"] = True
                        attempt_trace["ledger_after_attempt"] = ledger.budget_detail()
                    if reused_fact.get("eligible") and partition is not None:
                        accepted_partitions.add(partition)
                    if (
                        required_partitions and accepted_partitions == required_partitions
                    ) or (
                        not required_partitions
                        and sum(bool(fact.get("eligible")) for fact in holder_facts.values()) >= eligible_target
                    ):
                        break
                    continue
                # V2-9.8B.20: pure ledger/maturation writes must not span holder I/O.
                release_write_transaction(connection)
                bundle = _collect_preclose_context(
                    connection,
                    {
                        "run_id": command.run_id,
                        "step_key": f"holder_eligibility_{ordinal}",
                        "token_mint": proof.mint,
                        "pair_address": proof.bonding_curve,
                    },
                    timeout_seconds=timeout_seconds,
                    adapter_factories=(
                        dict(context_factories)
                        if isinstance(context_factories, Mapping) else None
                    ),
                    include=frozenset({"safety"}),
                    request_pacer=pacer,
                    # Holder-specific fail-closed mode: a later failure must
                    # carry the governed executions that already happened.
                    preserve_partial_executions=True,
                    holder_transport_ledger=holder_transport_ledger,
                    request_key_prefix=(
                        f"{campaign_root}-holder-{ordinal}-context"
                        if campaign_root
                        else None
                    ),
                )
                holder_facts[proof.mint.lower()] = {
                    **_holder_eligibility_from_bundle(
                        bundle, token_mint=proof.mint
                    ),
                    **handoff_detail,
                }
                persist_result = persist_bundle_attempts(
                    connection,
                    run_id=command.run_id,
                    cycle_id=cycle_id,
                    mint=proof.mint,
                    executions=bundle.get("executions", {}),
                    created_at=evaluated.isoformat(),
                    campaign_id=campaign_id or None,
                    candidate_ordinal=ordinal,
                    require_exact_transport_identities=require_exact_holder_identities,
                )
                stage_governed += int(persist_result.governed_request_count)
                stage_transports += int(persist_result.measured_transport_count)
                stage_request_ids.extend(
                    int(rid) for rid in persist_result.source_request_ids
                )
                stage_coverage.extend(
                    dict(entry) for entry in persist_result.source_request_coverage
                )
                if persist_result.accounting_blocker:
                    accounting_blocker = True
                    if persist_result.accounting_blocker_reason:
                        accounting_reasons.append(
                            str(persist_result.accounting_blocker_reason)
                        )
                ledger = replace(
                    ledger,
                    governed_requests=(
                        ledger.governed_requests
                        + int(persist_result.governed_request_count)
                    ),
                    underlying_transport_operations=(
                        ledger.underlying_transport_operations
                        + int(persist_result.measured_transport_count)
                    ),
                )
                persist_ledger(
                    connection, run_id=command.run_id, cycle_id=cycle_id,
                    ledger=ledger, now=evaluated.isoformat(),
                )
                complete_maturation(
                    connection, work_id=str(maturation["work_id"]),
                    cause="EVIDENCE_EVALUATED", now=evaluated.isoformat(),
                )
                if attempt_trace is not None:
                    attempt_trace["attempted"] = True
                    attempt_trace["governed_request_count"] = int(
                        persist_result.governed_request_count
                    )
                    attempt_trace["measured_transport_count"] = int(
                        persist_result.measured_transport_count
                    )
                    attempt_trace["ledger_after_attempt"] = ledger.budget_detail()
                if holder_facts[proof.mint.lower()].get("eligible") and partition is not None:
                    accepted_partitions.add(partition)
                if (
                    required_partitions and accepted_partitions == required_partitions
                ) or (
                    not required_partitions
                    and sum(bool(fact.get("eligible")) for fact in holder_facts.values()) >= eligible_target
                ):
                    break
            except Exception as exc:
                # V2-9.8B: a governed holder request row must never disappear
                # because a later collection or persistence operation raised.
                # Recover every real execution/request identity, mark the
                # attempt BLOCKED, and set a holder accounting blocker. A
                # failure before any governed request exists reports no ID but
                # still blocks. Counts are never fabricated.
                failed_stage = "HOLDER_CONTEXT_COLLECTION"
                partial_result = None
                partial_executions: Mapping[str, Any] = {}
                if isinstance(exc, HolderBundlePersistPartialError):
                    failed_stage = f"HOLDER_PERSIST:{exc.failed_stage}"
                    partial_result = exc.partial
                elif isinstance(exc, PrecloseContextPartialError):
                    failed_stage = f"HOLDER_COLLECTION:{exc.failed_stage}"
                    partial_executions = exc.executions
                if partial_result is None and partial_executions:
                    try:
                        partial_result = persist_bundle_attempts(
                            connection,
                            run_id=command.run_id,
                            cycle_id=cycle_id,
                            mint=proof.mint,
                            executions=partial_executions,
                            created_at=evaluated.isoformat(),
                            campaign_id=campaign_id or None,
                            candidate_ordinal=ordinal,
                            require_exact_transport_identities=require_exact_holder_identities,
                        )
                    except HolderBundlePersistPartialError as persist_exc:
                        partial_result = persist_exc.partial
                    except Exception as persist_exc:  # pragma: no cover
                        accounting_reasons.append(
                            "HOLDER_PARTIAL_PERSIST_UNRECOVERABLE:"
                            f"{type(persist_exc).__name__}"
                        )
                accounting_blocker = True
                accounting_reasons.append(
                    f"HOLDER_PARTIAL_ATTEMPT_{type(exc).__name__}"
                    f":stage={failed_stage}"
                )
                if partial_result is not None:
                    if partial_result.accounting_blocker_reason:
                        accounting_reasons.append(
                            str(partial_result.accounting_blocker_reason)
                        )
                    stage_governed += int(partial_result.governed_request_count)
                    stage_transports += int(
                        partial_result.measured_transport_count
                    )
                    stage_request_ids.extend(
                        int(rid) for rid in partial_result.source_request_ids
                    )
                    for entry in partial_result.source_request_coverage:
                        blocked_entry = dict(entry)
                        # An incomplete attempt is never a completed one.
                        blocked_entry["terminal_status"] = "BLOCKED"
                        stage_coverage.append(blocked_entry)
                    try:
                        ledger = replace(
                            ledger,
                            governed_requests=(
                                ledger.governed_requests
                                + int(partial_result.governed_request_count)
                            ),
                            underlying_transport_operations=(
                                ledger.underlying_transport_operations
                                + int(partial_result.measured_transport_count)
                            ),
                        )
                        persist_ledger(
                            connection, run_id=command.run_id, cycle_id=cycle_id,
                            ledger=ledger, now=evaluated.isoformat(),
                        )
                    except Exception as ledger_exc:  # pragma: no cover
                        accounting_reasons.append(
                            "HOLDER_PARTIAL_LEDGER_UNRECOVERABLE:"
                            f"{type(ledger_exc).__name__}"
                        )
                try:
                    complete_maturation(
                        connection, work_id=str(maturation["work_id"]),
                        cause=f"EVIDENCE_COLLECTION_FAILED:{type(exc).__name__}",
                        now=evaluated.isoformat(),
                    )
                except Exception as maturation_exc:  # pragma: no cover
                    accounting_reasons.append(
                        "HOLDER_PARTIAL_MATURATION_UNRECOVERABLE:"
                        f"{type(maturation_exc).__name__}"
                    )
                holder_facts[proof.mint.lower()] = {
                    "eligible": False,
                    "reason": f"HOLDER_EVIDENCE_COLLECTION_FAILED:{type(exc).__name__}",
                    "source_name": None,
                    **handoff_detail,
                }
                if attempt_trace is not None:
                    attempt_trace["attempted"] = bool(partial_result is not None)
                    attempt_trace["ledger_after_attempt"] = ledger.budget_detail()
        # Preserve order while de-duplicating request IDs that may repeat only
        # if the same durable row is legitimately re-reported (should not).
        deduped_ids: list[int] = []
        seen_ids: set[int] = set()
        for rid in stage_request_ids:
            if rid in seen_ids:
                continue
            seen_ids.add(rid)
            deduped_ids.append(rid)
        holder_stage_status = "BLOCKED" if accounting_blocker else "COMPLETED"
        holder_stage_cause = (
            ";".join(accounting_reasons)
            if accounting_reasons
            else budget_exhaustion_reason
        )
        holder_stage_id = None
        if holder_stage_evidence_sealer is not None:
            sealed = holder_stage_evidence_sealer(
                holder_transport_ledger,
                holder_stage_status,
                holder_stage_cause,
            )
            holder_stage_id = str(sealed.get("stage_id") or "") or None
        return HolderContextResult(
            holder_facts=holder_facts,
            ledger=ledger,
            source_request_ids=tuple(deduped_ids),
            source_request_coverage=tuple(stage_coverage),
            accounting_blocker=accounting_blocker,
            accounting_blocker_reason=(
                ";".join(accounting_reasons) if accounting_reasons else None
            ),
            governed_request_count=stage_governed,
            measured_transport_count=stage_transports,
            evaluated_candidate_mints=tuple(evaluated_candidate_mints),
            unattempted_candidate_mints=tuple(unattempted_candidate_mints),
            budget_exhausted=budget_exhausted,
            budget_exhaustion_reason=budget_exhaustion_reason,
            ledger_before_holder=ledger_before_holder,
            ledger_after_holder=ledger,
            holder_attempt_budget_trace=tuple(holder_attempt_budget_trace),
            transport_identities=tuple(
                identity.as_dict() for identity in holder_transport_ledger.transports
            ),
            holder_stage_id=holder_stage_id,
            holder_stage_terminal_status=holder_stage_status,
            holder_stage_first_terminal_cause=holder_stage_cause,
        )

    def run(self, *, mode: str, **kwargs: Any) -> Any:
        """Single dispatch entry point for the canonical operational modes.

        There is exactly one committed runner; ``mode`` selects the bounded
        behaviour. No parallel runner or temporary harness exists.
        """
        if mode == FULL_PILOT:
            return self.run_operational(**kwargs)
        if mode == ACTIVATION_ONLY:
            return self.run_readiness_only(**kwargs)
        if mode == SNAPSHOT_READINESS:
            return self.run_snapshot_readiness(**kwargs)
        if mode == PILOT_INPUT_READINESS:
            operational_kwargs = dict(kwargs)
            operational_kwargs["stop_before_lifecycle"] = True
            return self.run_operational(**operational_kwargs)
        raise LiveOperationalError("UNKNOWN_OPERATIONAL_MODE", str(mode))

    def run_operational(
        self,
        *,
        command: AbstractCampaignCommand,
        pump_transport: PumpRpcTransport,
        secondary_transport: SecondaryHttpTransport | None = None,
        source_governor: OwnerPort,
        central_scheduler: OwnerPort,
        selection_seed: str,
        cycle_id: str,
        cycle_cutoff: str,
        evaluated_at: str,
        backup_path: str | Path,
        lifecycle_kwargs: Mapping[str, Any],
        prior_cursor: FinalizedOriginCursor | None = None,
        timeout_seconds: float = DEFAULT_CALL_TIMEOUT_SECONDS,
        byte_ceiling: int = DEFAULT_RESPONSE_BYTE_CEILING,
        tracker_api_key: str | None = None,
        graduation_proofs: Mapping[str, Any] | None = None,
        graduated_supply: Any | None = None,
        migration_transport: Any | None = None,
        graduated_supply_kwargs: Mapping[str, Any] | None = None,
        stop_before_lifecycle: bool = False,
        fifteen_minute_only: bool = False,
        standard_four_hour_campaign: bool = False,
        accounting_stage_evidence_sink: (
            Callable[[Mapping[str, Any]], None] | None
        ) = None,
        accounting_stage_evidence_sink_for_cycle: (
            Callable[..., Callable[[Mapping[str, Any]], None]] | None
        ) = None,
        transport_identity_observer: (
            Callable[[Any], None] | None
        ) = None,
        local_validation_identity_observer: (
            Callable[[Any], None] | None
        ) = None,
        pre_holder_accounting_projection: (
            Callable[[], Mapping[str, Any]] | None
        ) = None,
        holder_stage_evidence_sealer: Callable[[Any, str, str | None], Mapping[str, Any]] | None = None,
        operational_database_target_binding: Any | None = None,
        disposable_public_composition_proof_binding: Any | None = None,
        # V2-9.8B Post-DTW98 bounded pre-lifecycle temporal acquisition. The
        # horizon is explicit and separate from ``ceilings.duration_seconds``:
        # it never borrows lifecycle/WINDOW_15M time. ``None`` for the owner
        # preserves the existing immediate-terminalization behaviour exactly.
        pre_lifecycle_acquisition_seconds: int = (
            PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS
        ),
        pre_lifecycle_temporal_refresh_owner: Any | None = None,
        later_cycle_source_operation_timeout_seconds: float = (
            LATER_CYCLE_SOURCE_OPERATION_TIMEOUT_SECONDS
        ),
    ) -> Any:
        """Run one authoritative live two-token operational-natural campaign.

        V2-9.7E.44: when ``graduated_supply`` (a prebuilt
        ``graduated_supply_front_door.GraduatedSupply``) or a live
        ``migration_transport`` is provided, the E.42 direct-migration discovery and
        E.43 ``$3,000`` exact-pool front door supply the candidate universe: only
        floor-passing front-door-selected candidates (one ``LATEST`` + one
        ``PERSISTED``) become graduation proofs and admission carriers. This is the
        canonical FULL_PILOT candidate-supply wiring; it reuses the adopted owners
        verbatim and adds no new gate, score, ranking, selector or provider.
        ``stop_before_lifecycle`` returns the pre-lifecycle readiness bundle
        (admission + holder eligibility + atomic two-slot handoff readiness) without
        invoking the scheduler/lifecycle/memory driver.

        ``graduation_proofs`` carries confirmed PumpSwap graduation evidence
        (mint -> confirmation) supplied by a graduated-discovery channel or an
        operator migration-signature locator. Under the V2-9.7E.41 graduation-only
        law, only mints with exact confirmed graduation are selectable; on a
        cold-start live cycle with no graduation evidence the mapping is empty and
        the campaign blocks with ``BLOCKED_INSUFFICIENT_GRADUATED_POOL``.
        """
        lk = dict(lifecycle_kwargs or {})

        # Four-token proof-only ownership seam. The authoritative operational
        # owner is the sole callback builder; callers may not substitute a
        # parallel discovery owner through lifecycle kwargs.
        if "later_cycle_discovery_callback" in lk:
            raise LiveOperationalError(
                "LATER_CYCLE_DISCOVERY_CALLBACK_OVERRIDE_FORBIDDEN"
            )
        if lk.get("four_token_proof_controller") is not None:
            production_later_supply = self._later_cycle_candidate_supply
            if production_later_supply is None and migration_transport is not None:
                from printer_v1.operator_cli.later_cycle_graduated_supply import (
                    build_later_cycle_graduated_supply,
                )

                later_supply_kwargs = dict(graduated_supply_kwargs or {})
                for locally_owned in (
                    "campaign_id", "execution_id", "run_id", "cycle_id",
                    "campaign_source_request_scope", "discovery_request_key_prefix",
                    "front_door_request_key_prefix", "stage_evidence_sink",
                    "transport_identity_observer", "local_validation_identity_observer",
                    "deadline_at", "temporal_refresh_owner",
                    "cooperative_stage_budget",
                ):
                    later_supply_kwargs.pop(locally_owned, None)

                later_cycle_progress: dict[str, dict[str, Any]] = {}

                def production_later_supply(**context: Any) -> LaterCycleCandidateSupply:
                    evaluated = context["evaluated_at"]
                    progress_key = str(context["proposed_cycle_id"])
                    progress = later_cycle_progress.get(progress_key)
                    from printer_v1.discovery.permanent_discovery_availability import (
                        StageBudget,
                    )

                    cooperative_stage_budget = (
                        progress.get("stage_budget")
                        if progress is not None
                        else StageBudget.permanent_discovery_default()
                    )
                    if not isinstance(cooperative_stage_budget, StageBudget):
                        raise LiveOperationalError(
                            "LATER_CYCLE_STAGE_BUDGET_STATE_INVALID"
                        )
                    later_cycle_refresh_owner = None
                    later_cycle_deadline = None
                    later_cycle_stage_evidence_sink = None
                    if pre_lifecycle_temporal_refresh_owner is not None:
                        from printer_v1.discovery.permanent_discovery_availability import (
                            build_campaign_source_request_scope,
                        )
                        cycle_ordinal = int(context["proposed_cycle_ordinal"])
                        cycle_source_execution_identity = (
                            f"{selection_seed}:c{cycle_ordinal:04d}"
                        )
                        cycle_scope = build_campaign_source_request_scope(
                            execution_id=cycle_source_execution_identity,
                            campaign_id=str(context["campaign_id"]),
                            run_id=str(context["campaign_run_id"]),
                            cycle_id=str(context["proposed_cycle_id"]),
                        )
                        cutoff_value = context["cycle_cutoff"]
                        cutoff_text = (
                            cutoff_value.isoformat()
                            if isinstance(cutoff_value, datetime)
                            else str(cutoff_value)
                        )
                        if progress is not None:
                            later_cycle_refresh_owner = progress["refresh_owner"]
                        elif accounting_stage_evidence_sink_for_cycle is None:
                            if accounting_stage_evidence_sink is not None:
                                raise LiveOperationalError(
                                    "LATER_CYCLE_ACCOUNTING_SINK_RESOLVER_REQUIRED"
                                )
                            later_cycle_refresh_owner = (
                                pre_lifecycle_temporal_refresh_owner.for_cycle(
                                    cycle_id=str(context["proposed_cycle_id"]),
                                    cycle_cutoff=cutoff_text,
                                    evaluated_at=evaluated.isoformat(),
                                    request_key_prefix=cycle_scope.request_key_root,
                                    cooperative_yield=True,
                                )
                            )
                        else:
                            (
                                later_cycle_stage_evidence_sink,
                                later_cycle_refresh_owner,
                            ) = _bind_later_cycle_accounting_owner(
                                campaign_id=str(context["campaign_id"]),
                                run_id=str(context["campaign_run_id"]),
                                proposed_cycle_id=str(context["proposed_cycle_id"]),
                                cycle_cutoff=cutoff_text,
                                evaluated_at=evaluated.isoformat(),
                                request_key_prefix=cycle_scope.request_key_root,
                                initial_temporal_refresh_owner=(
                                    pre_lifecycle_temporal_refresh_owner
                                ),
                                accounting_stage_evidence_sink_for_cycle=(
                                    accounting_stage_evidence_sink_for_cycle
                                ),
                            )
                        later_cycle_deadline = (
                            later_cycle_refresh_owner.acquisition_deadline_at
                        )
                    elif accounting_stage_evidence_sink_for_cycle is not None:
                        (
                            later_cycle_stage_evidence_sink,
                            later_cycle_refresh_owner,
                        ) = _bind_later_cycle_accounting_owner(
                            campaign_id=str(context["campaign_id"]),
                            run_id=str(context["campaign_run_id"]),
                            proposed_cycle_id=str(context["proposed_cycle_id"]),
                            cycle_cutoff=str(context["cycle_cutoff"]),
                            evaluated_at=evaluated.isoformat(),
                            request_key_prefix="not-used-without-temporal-owner",
                            initial_temporal_refresh_owner=None,
                            accounting_stage_evidence_sink_for_cycle=(
                                accounting_stage_evidence_sink_for_cycle
                            ),
                        )

                    if later_cycle_stage_evidence_sink is not None:
                        later_supply_kwargs["stage_evidence_sink"] = (
                            later_cycle_stage_evidence_sink
                        )
                    if transport_identity_observer is not None:
                        later_supply_kwargs["transport_identity_observer"] = (
                            transport_identity_observer
                        )
                    if local_validation_identity_observer is not None:
                        later_supply_kwargs["local_validation_identity_observer"] = (
                            local_validation_identity_observer
                        )

                    def holder_evidence_owner(supply: Any) -> Mapping[str, Mapping[str, Any]]:
                        from printer_v1.db.sqlite_write_contracts import (
                            connect_operational,
                            release_write_transaction,
                        )
                        from printer_v1.operator_cli.holder_reliability_budget_control import (
                            build_ledger,
                        )
                        from printer_v1.operator_cli.later_cycle_graduated_supply import (
                            selected_slot_holder_candidates,
                        )

                        source_operations = int(
                            supply.diagnostics.get("stage_local_source_requests")
                            or 0
                        )
                        deadline = evaluated + timedelta(
                            seconds=command.ceilings.duration_seconds
                        )
                        holder_targets = selected_slot_holder_candidates(supply)
                        holder_connection = connect_operational(command.db_path)
                        try:
                            release_write_transaction(holder_connection)
                            holder_result = self._evaluate_holder_eligibility(
                                holder_connection,
                                command=command,
                                cycle_id=str(context["proposed_cycle_id"]),
                                bounded_candidates=holder_targets,
                                evaluated=evaluated,
                                deadline=deadline,
                                ledger=build_ledger(
                                    pump_operations=0,
                                    additional_governed_operations=source_operations,
                                    deadline_at=deadline,
                                ),
                                timeout_seconds=timeout_seconds,
                                context_factories=lk.get("context_adapter_factories"),
                                request_pacer=None,
                                partition_by_mint=None,
                                tracking_pair_by_mint={
                                    item.mint.lower(): getattr(
                                        item, "pool_address", None
                                    )
                                    or getattr(item, "bonding_curve", "")
                                    for item in holder_targets
                                },
                                eligible_target=2,
                                permanent_memory_observation=True,
                                holder_transport_identity_observer=(
                                    transport_identity_observer
                                ),
                                holder_stage_evidence_sealer=None,
                                campaign_request_key_root=str(
                                    supply.diagnostics.get("request_key_root") or ""
                                ),
                            )
                            holder_connection.commit()
                            if holder_result.accounting_blocker:
                                raise LiveOperationalError(
                                    "LATER_CYCLE_HOLDER_ACCOUNTING_BLOCKED",
                                    str(holder_result.accounting_blocker_reason or ""),
                                )
                            return dict(holder_result.holder_facts)
                        finally:
                            holder_connection.close()

                    prior_operations = int(
                        (progress or {}).get("source_operations_used") or 0
                    )
                    if (
                        progress is not None
                        and bool(progress.get("waiting_for_refresh"))
                        and later_cycle_refresh_owner is not None
                    ):
                        from printer_v1.discovery.eligible_token_supply import (
                            DEFAULT_DISCOVERY_OPERATION_BUDGET,
                        )
                        from printer_v1.discovery.pre_lifecycle_temporal_acquisition import (
                            REFRESH_COMPLETED,
                            WAITING_FOR_ELIGIBLE_SUPPLY,
                        )
                        from printer_v1.operator_cli.later_cycle_graduated_supply import (
                            classify_later_cycle_failure,
                        )

                        operation_budget = int(
                            later_supply_kwargs.get("discovery_operation_budget")
                            or DEFAULT_DISCOVERY_OPERATION_BUDGET
                        )
                        outcome = later_cycle_refresh_owner.request_temporal_refresh(
                            reserve_depth=int(progress.get("reserve_depth") or 0),
                            required_capacity=4,
                            universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
                            source_operations_remaining=max(
                                0, operation_budget - prior_operations
                            ),
                            provider_terminal_failure=False,
                            now=evaluated.isoformat(),
                            cooperative_stage_budget=cooperative_stage_budget,
                        )
                        from printer_v1.discovery.permanent_discovery_availability import (
                            build_campaign_source_request_scope,
                        )
                        from printer_v1.operator_cli.later_cycle_graduated_supply import (
                            _source_lineage,
                        )
                        from printer_v1.db.sqlite_write_contracts import connect_operational

                        refresh_scope = build_campaign_source_request_scope(
                            execution_id=(
                                f"{selection_seed}:c"
                                f"{int(context['proposed_cycle_ordinal']):04d}"
                            ),
                            campaign_id=str(context["campaign_id"]),
                            run_id=str(context["campaign_run_id"]),
                            cycle_id=str(context["proposed_cycle_id"]),
                        )
                        refresh_lineage_connection = connect_operational(command.db_path)
                        try:
                            refresh_lineage = _source_lineage(
                                refresh_lineage_connection,
                                request_key_root=refresh_scope.request_key_root,
                                required=False,
                            )
                        finally:
                            refresh_lineage_connection.close()
                        if outcome.status == WAITING_FOR_ELIGIBLE_SUPPLY:
                            completed_partial_operations = int(
                                outcome.source_operations
                            )
                            if completed_partial_operations:
                                progress["source_operations_used"] = (
                                    prior_operations
                                    + completed_partial_operations
                                )
                                prior_operations = int(
                                    progress["source_operations_used"]
                                )
                            progress["next_governed_request_worst_case_seconds"] = (
                                outcome.next_governed_request_worst_case_seconds
                            )
                            return LaterCycleCandidateSupply(
                                (),
                                refresh_lineage,
                                WAITING_FOR_ELIGIBLE_SUPPLY,
                                {
                                    "stage_local_source_requests": prior_operations,
                                    "provider_failures": 0,
                                    "shortage_classification": None,
                                    "scheduler_yield": outcome.to_dict(),
                                },
                                None,
                            )
                        if outcome.status != REFRESH_COMPLETED:
                            terminal = str(outcome.status)
                            later_cycle_progress.pop(progress_key, None)
                            return LaterCycleCandidateSupply(
                                (),
                                refresh_lineage,
                                terminal,
                                {
                                    "stage_local_source_requests": prior_operations
                                    + int(outcome.source_operations),
                                    "provider_failures": int(outcome.provider_failures),
                                    "shortage_classification": terminal,
                                },
                                classify_later_cycle_failure(
                                    terminal_cause=terminal,
                                    shortage_classification=terminal,
                                ),
                            )
                        updated_progress = (
                            _persist_completed_later_cycle_refresh_progress(
                                later_cycle_progress,
                                progress_key=progress_key,
                                progress=progress,
                                refresh_owner=later_cycle_refresh_owner,
                                completed_source_operations=int(
                                    outcome.source_operations
                                ),
                            )
                        )
                        prior_operations = int(
                            updated_progress["source_operations_used"]
                        )
                        # The claimed DISCOVERY_REFRESH opportunity is this
                        # Scheduler claim's single acquisition quantum. Persist
                        # its cumulative accounting and return before any market
                        # batch can start under the same claim.
                        return LaterCycleCandidateSupply(
                            (),
                            refresh_lineage,
                            "ACQUISITION_QUANTUM_YIELDED",
                            {
                                "stage_local_source_requests": prior_operations,
                                "provider_failures": 0,
                                "shortage_classification": None,
                                "eligible_reserve_count": int(
                                    progress.get("reserve_depth") or 0
                                ),
                                "completed_refresh": outcome.to_dict(),
                            },
                            None,
                        )

                    result = build_later_cycle_graduated_supply(
                        command.db_path,
                        campaign_id=str(context["campaign_id"]),
                        campaign_run_id=str(context["campaign_run_id"]),
                        authoritative_factory_run_id=str(
                            context["authoritative_factory_run_id"]
                        ),
                        proposed_cycle_id=str(context["proposed_cycle_id"]),
                        proposed_cycle_ordinal=int(context["proposed_cycle_ordinal"]),
                        evaluated_at=evaluated,
                        # The canonical execution identity of this command owns
                        # the later-cycle source scope and exhaustion
                        # certificate. The later-cycle selection seed carried in
                        # ``context`` is selection input only.
                        execution_id=selection_seed,
                        selection_seed=str(context["selection_seed"]),
                        migration_transport=migration_transport,
                        graduated_supply_kwargs={
                            **later_supply_kwargs,
                            "persist_terminal_certificate": False,
                        },
                        holder_evidence_owner=holder_evidence_owner,
                        deadline_at=later_cycle_deadline,
                        temporal_refresh_owner=later_cycle_refresh_owner,
                        cooperative_resume=progress is not None,
                        prior_source_operations_used=prior_operations,
                        cooperative_quantum=True,
                        cooperative_phase=str(
                            (progress or {}).get("cooperative_phase")
                            or "AUXILIARY_FRESH_INTAKE"
                        ),
                        cooperative_stage_budget=cooperative_stage_budget,
                        # Slice B: the direct lane's categorical mode for this
                        # claim. A new attempt always starts at the live tail.
                        cooperative_direct_mode=str(
                            (progress or {}).get("direct_acquisition_mode")
                            or "LIVE_TAIL"
                        ),
                    )
                    if result.terminal_cause in {
                        "WAITING_FOR_ELIGIBLE_SUPPLY",
                        "ACQUISITION_QUANTUM_YIELDED",
                    }:
                        diagnostics = dict(result.diagnostics or {})
                        next_phase = str(
                            diagnostics.get("next_cooperative_phase")
                            or "MARKET_DISCOVERY"
                        )
                        next_request_bound = (
                            (
                                diagnostics.get("direct_migration_discovery")
                                or {}
                            ).get("next_governed_request_worst_case_seconds")
                        )
                        if next_request_bound is None:
                            next_request_bound = (
                                diagnostics.get("scheduler_yield") or {}
                            ).get("next_governed_request_worst_case_seconds")
                        if next_phase == "DIRECT_MIGRATION" and next_request_bound is None:
                            from printer_v1.discovery.eligible_token_supply import (
                                AcquisitionQuantumKind,
                                acquisition_governed_request_bound,
                            )

                            next_request_bound = acquisition_governed_request_bound(
                                AcquisitionQuantumKind.DIRECT_MIGRATION,
                                request_kind="DIRECT_PUMP_SIGNATURE_PAGE",
                                checkpoint_reserve_seconds=5.0,
                            ).worst_case_seconds
                        later_cycle_progress[progress_key] = {
                            "refresh_owner": later_cycle_refresh_owner,
                            "stage_budget": cooperative_stage_budget,
                            "source_operations_used": int(
                                diagnostics.get("stage_local_source_requests") or 0
                            ),
                            "reserve_depth": int(
                                diagnostics.get("eligible_reserve_count") or 0
                            ),
                            "waiting_for_refresh": (
                                result.terminal_cause
                                == "WAITING_FOR_ELIGIBLE_SUPPLY"
                            ),
                            "refresh_ordinal": int(
                                (
                                    diagnostics.get("scheduler_yield") or {}
                                ).get("refresh_ordinal")
                                or 0
                            ),
                            "cooperative_phase": next_phase,
                            # Slice B attempt-local direct acquisition facts.
                            "direct_acquisition_mode": str(
                                diagnostics.get("next_direct_acquisition_mode")
                                or "LIVE_TAIL"
                            ),
                            "direct_live_tail_completed": bool(
                                (progress or {}).get("direct_live_tail_completed")
                                or diagnostics.get("direct_live_tail_completed")
                            ),
                            "direct_backfill_completed": bool(
                                (progress or {}).get("direct_backfill_completed")
                                or diagnostics.get("direct_backfill_completed")
                            ),
                            "next_governed_request_worst_case_seconds": next_request_bound,
                        }
                    else:
                        later_cycle_progress.pop(progress_key, None)
                    return result

            lk["later_cycle_discovery_callback"] = (
                self._build_later_cycle_discovery_callback(
                    db_path=command.db_path,
                    configuration_id=command.configuration_id,
                    candidate_supply=production_later_supply,
                )
            )
            from printer_v1.discovery.eligible_token_supply import (
                acquisition_quantum_bound,
            )

            def next_later_cycle_quantum_seconds() -> float:
                if later_cycle_progress:
                    progress = next(iter(later_cycle_progress.values()))
                    next_request_bound = progress.get(
                        "next_governed_request_worst_case_seconds"
                    )
                    if next_request_bound is not None:
                        value = float(next_request_bound)
                        if value <= 0:
                            raise LiveOperationalError(
                                "LATER_CYCLE_NEXT_REQUEST_BOUND_INVALID"
                            )
                        return value
                kind = _next_later_cycle_quantum_kind(later_cycle_progress)
                return acquisition_quantum_bound(kind).worst_case_seconds

            # Resolve on every factory boundary so deadline protection uses the
            # actual next state-machine unit, never a global guessed duration.
            lk["later_cycle_acquisition_quantum_seconds"] = (
                next_later_cycle_quantum_seconds
            )
            if "four_token_health_projector" in lk:
                raise LiveOperationalError(
                    "FOUR_TOKEN_HEALTH_PROJECTOR_OVERRIDE_FORBIDDEN"
                )
            from printer_v1.operator_cli.authoritative_admission_health import (
                project_authoritative_admission_health,
            )
            from printer_v1.operator_cli.multi_cycle_campaign_coordinator import (
                MultiCycleCampaignBinding,
            )
            from printer_v1.operator_cli.operational_database_target_binding import (
                load_durable_operational_database_target_expectation,
            )
            from printer_v1.operator_cli.proof_db_schema_readiness import (
                CANONICAL_PERSISTENT_DB,
            )
            from printer_v1.operator_cli.source_free_discovery_capacity import (
                build_source_free_discovery_attempt_manifest,
            )

            durable_health_expectation = (
                load_durable_operational_database_target_expectation(
                    command.db_path,
                    campaign_id=command.campaign_id,
                    campaign_run_id=command.run_id,
                    cycle_id=cycle_id,
                    configuration_id=command.configuration_id,
                )
            )
            health_binding = MultiCycleCampaignBinding(
                campaign_id=command.campaign_id,
                campaign_run_id=command.run_id,
                configuration_id=command.configuration_id,
                authoritative_factory_run_id=str(lk.get("factory_run_id") or ""),
            )
            health_manifest = build_source_free_discovery_attempt_manifest()

            def four_token_health_projector(
                connection: sqlite3.Connection, instant: datetime
            ) -> Any:
                return project_authoritative_admission_health(
                    connection,
                    db_path=command.db_path,
                    binding=health_binding,
                    first_cycle_id=cycle_id,
                    operational_db_binding=operational_database_target_binding,
                    operational_db_expected=durable_health_expectation,
                    canonical_authoritative_db_path=CANONICAL_PERSISTENT_DB,
                    supervision_id=command.supervision_id,
                    supervision_owner_id=command.owner_id,
                    discovery_manifest=health_manifest,
                    now=instant,
                )

            lk["four_token_health_projector"] = four_token_health_projector

        if standard_four_hour_campaign and not fifteen_minute_only:
            raise LiveOperationalError(
                "STANDARD_FOUR_HOUR_REQUIRES_OPERATIONAL_PERSISTENT_MODE",
                "standard four-hour campaign requires fifteen_minute_only persistent authority",
            )
        if standard_four_hour_campaign:
            lk["standard_four_hour_campaign"] = True
        if fifteen_minute_only:
            from printer_v1.operator_cli.operational_database_target_binding import (
                load_durable_operational_database_target_expectation,
            )
            from printer_v1.operator_cli.proof_db_schema_readiness import (
                CANONICAL_PERSISTENT_DB,
            )
            durable_expectation = load_durable_operational_database_target_expectation(
                command.db_path,
                campaign_id=command.campaign_id,
                campaign_run_id=command.run_id,
                cycle_id=cycle_id,
                configuration_id=command.configuration_id,
            )
            binding_reason = _validate_fifteen_minute_database_target_binding(
                command=command,
                cycle_id=cycle_id,
                selection_seed=selection_seed,
                operational_database_target_binding=(
                    operational_database_target_binding
                ),
                disposable_public_composition_proof_binding=(
                    disposable_public_composition_proof_binding
                ),
                durable_expectation=durable_expectation,
                canonical_authoritative_db_path=CANONICAL_PERSISTENT_DB,
            )
            if binding_reason is not None:
                raise LiveOperationalError(
                    binding_reason, "database target binding"
                )
        # Structural exclusion at the live owner boundary: fixture proof plans and
        # predeclared dispositions can never enter operational mode.
        for forbidden in (
            "compressed_two_token_proof_plan",
            "operational_natural_disposition",
        ):
            if forbidden in lk:
                raise LiveOperationalError(
                    "FIXTURE_PLAN_REJECTED_OPERATIONALLY", forbidden
                )
        if not standard_four_hour_campaign:
            lk["operational_natural_disposition"] = True

        from printer_v1.operator_cli.durable_external_operation_log import (
            DurablePumpRpcTransport,
        )
        pump_transport = DurablePumpRpcTransport(
            pump_transport, db_path=command.db_path, run_id=command.run_id,
            cycle_id=cycle_id,
        )
        fixtures, acquisition, enrichment = self._build_fixtures(
            pump_transport=pump_transport,
            secondary_transport=secondary_transport,
            source_governor=source_governor,
            central_scheduler=central_scheduler,
            cycle_id=cycle_id,
            cycle_cutoff=cycle_cutoff,
            selection_seed=selection_seed,
            evaluated_at=evaluated_at,
            prior_cursor=prior_cursor,
            timeout_seconds=timeout_seconds,
            byte_ceiling=byte_ceiling,
            tracker_api_key=tracker_api_key,
            graduation_native_only=(
                migration_transport is not None or graduated_supply is not None
            ),
        )
        # V2-9.7E.44: wire E.42 direct-migration discovery + E.43 $3K front door
        # into the FULL_PILOT candidate supply. When a prebuilt supply or a live
        # migration transport is provided, discovery+front-door produce the eligible
        # mixed pair; only floor-passing front-door-selected candidates become
        # graduation proofs and admission-universe carriers. Reuses the adopted
        # owners verbatim (no new gate, score, ranking, selector or provider).
        supply = graduated_supply
        # Prebuilt permanent supplies must already carry validated current-run
        # CampaignSourceRequestScope and pre-holder reconciliation. Do not
        # reconstruct either authority here — the pre-freeze gate fail-closes.
        if supply is None and migration_transport is not None:
            from printer_v1.discovery.permanent_discovery_availability import (
                build_campaign_source_request_scope,
                validate_campaign_source_request_scope,
            )
            from printer_v1.operator_cli.graduated_supply_front_door import (
                build_graduated_supply,
            )
            supply_kwargs = dict(graduated_supply_kwargs or {})
            # The V2-9.8B operational path applies exact tracking feasibility
            # before exact-pool market work. Other front-door consumers retain
            # their explicit default until they opt into this campaign contract.
            supply_kwargs.setdefault("tracking_precheck", True)
            # Bind existing exhaustion-certificate ownership to the canonical
            # operational action. selection_seed is the execution identity used
            # by the outer V2-9.8B command.
            supply_kwargs.update({
                "campaign_id": command.campaign_id,
                "execution_id": selection_seed,
                "run_id": command.run_id,
                "cycle_id": cycle_id,
            })
            # Permanent operational mode owns one typed request-key root for
            # every discovery and front-door stage. Construct it only from the
            # exact invocation identities (never wall-clock, UUID, DB, or
            # provider output).
            if bool(supply_kwargs.get("permanent_availability")):
                scope = build_campaign_source_request_scope(
                    execution_id=selection_seed,
                    campaign_id=command.campaign_id,
                    run_id=command.run_id,
                    cycle_id=cycle_id,
                )
                try:
                    scope = validate_campaign_source_request_scope(
                        scope,
                        execution_id=selection_seed,
                        campaign_id=command.campaign_id,
                        run_id=command.run_id,
                        cycle_id=cycle_id,
                    )
                except ValueError as exc:
                    raise LiveOperationalError(str(exc), "campaign source request scope") from exc
                supply_kwargs["campaign_source_request_scope"] = scope
                supply_kwargs["discovery_request_key_prefix"] = (
                    scope.request_key_root
                )
                supply_kwargs["front_door_request_key_prefix"] = (
                    scope.request_key_root
                )
            # Stages emit sealed evidence into the campaign owner as each stage
            # terminalizes. Do not re-ingest discovery evidence after return
            # (prevents double ingestion and captures shortage-path stages).
            if accounting_stage_evidence_sink is not None:
                supply_kwargs["stage_evidence_sink"] = accounting_stage_evidence_sink
            # Action-local transport identities are observed at measurement time
            # (MeasuredTransportLedger.record_transport), not from sealed stages.
            if transport_identity_observer is not None:
                supply_kwargs["transport_identity_observer"] = (
                    transport_identity_observer
                )
            if local_validation_identity_observer is not None:
                supply_kwargs["local_validation_identity_observer"] = (
                    local_validation_identity_observer
                )
            # V2-9.8B Post-DTW98: bind the *acquisition* horizon at the supply
            # boundary. The audit proved the eligible-supply loop previously ran
            # with no deadline at all because the lifecycle deadline was only
            # computed after supply returned. This horizon is its own bounded
            # envelope, not a share of the post-supply lifecycle duration.
            if pre_lifecycle_temporal_refresh_owner is not None:
                supply_kwargs["deadline_at"] = pre_lifecycle_acquisition_deadline_at(
                    evaluated_at,
                    acquisition_duration_seconds=int(
                        pre_lifecycle_acquisition_seconds
                    ),
                )
                supply_kwargs["temporal_refresh_owner"] = (
                    pre_lifecycle_temporal_refresh_owner
                )
            supply = build_graduated_supply(
                command.db_path,
                cycle_seed=selection_seed,
                migration_transport=migration_transport,
                now=evaluated_at,
                **supply_kwargs,
            )
        graduated_supply_proofs: tuple[Any, ...] = ()
        if supply is not None:
            # Prebuilt supplies that perform no source work intentionally emit
            # no stage evidence here. Live migration-backed supplies already
            # sealed child stages through the sink above.
            merged_proofs = dict(graduation_proofs or {})
            merged_proofs.update(dict(supply.graduation_proofs))
            graduation_proofs = merged_proofs
            graduated_supply_proofs = tuple(
                getattr(supply, "holder_reserve_supply", ())
                or supply.graduated_supply
            )
        # V2-9.7E.41: bind confirmed graduation evidence into the discovery
        # fixtures so the executor's PumpSwap confirmation and the graduation-only
        # gate operate on it. Empty on a cold-start cycle with no graduated supply.
        fixtures = replace(
            fixtures, pumpswap_proofs=dict(graduation_proofs or {})
        )
        from printer_v1.operator_cli.holder_reliability_budget_control import (
            build_ledger,
            persist_ledger,
        )
        evaluated = datetime.fromisoformat(evaluated_at.replace("Z", "+00:00"))
        deadline = evaluated + timedelta(seconds=command.ceilings.duration_seconds)
        evaluated_epoch = int(evaluated.timestamp())
        # V2-9.7E.46B.2 accounting contract: campaign governed_requests equals the
        # DISTINCT durable governed source requests attributable to the campaign.
        # Each stage total must therefore be disjoint from every other stage's.
        #   discovery.source_requests   — every campaign request up to and including
        #                                 the end of discovery (locator + migration +
        #                                 PumpSwap verification). The canonical runner
        #                                 always prepares a FRESH attempt target, so
        #                                 this whole-table count contains nothing but
        #                                 this campaign's own rows.
        #   front_door.liquidity_requests — ONLY the exact pair_market_snapshot request
        #                                 identities that invocation created.
        # Before E.46B.2 the front-door total was a whole-table
        # `WHERE source_name='dexscreener'` count, which re-counted the discovery
        # fresh-profile locator and charged it twice (E.46B.1: 9 + 7 + 6 = 22 against
        # 21 distinct durable rows). Do not reintroduce a whole-table total here.
        # V2-9.8B.2: every stage total must be invocation-local. Discovery must
        # not whole-table-count the persistent operational DB. Prefer the supply
        # composition's stage-local sum (locator + discovery + front door).
        supply_source_operations = 0
        if supply is not None:
            stage_local = supply.diagnostics.get("stage_local_source_requests")
            if stage_local is not None:
                supply_source_operations = int(stage_local)
            else:
                supply_source_operations = int(
                    supply.discovery_report.get("source_operation_ledger", {}).get(
                        "source_requests", 0
                    )
                ) + int(
                    supply.front_door_report.get("source_operation_ledger", {}).get(
                        "liquidity_requests", 0
                    )
                ) + int(supply.diagnostics.get("locator_source_requests") or 0)
        ledger = build_ledger(
            pump_operations=acquisition.result.accounting.underlying_rpc_operations,
            additional_governed_operations=(
                enrichment.requested + supply_source_operations
            ),
            deadline_at=deadline,
        )
        from printer_v1.db.sqlite_write_contracts import (
            connect_operational,
            release_write_transaction,
        )

        connection = connect_operational(command.db_path)
        frozen_eligible_reserve = None
        memory_activation_set = None
        memory_activation_contract_blocker = None
        try:
            # V2-9.7E.41 pending-discovery population: stage every confirmed
            # origin from this cycle into the durable prospective-origin registry
            # as PENDING DISCOVERY evidence (retaining exact Pump origin, mint
            # identity, signature/block time and provenance). Staged origins are
            # bonding-curve / unpaired launches; under the graduation-only law they
            # are NEVER exported as selectable pilot candidates. This reuses the
            # existing registry owner; it adds no source call, no rank/order, and
            # no provider. The 900s age reload is retired.
            staged_now = 0
            for observation in acquisition.result.observations:
                try:
                    if record_confirmed_origin(
                        connection, observation, now=evaluated.isoformat()
                    ):
                        staged_now += 1
                except OriginRegistryError:
                    # A conflicting confirmed origin never blocks the campaign;
                    # the candidate is simply not restaged.
                    pass
            connection.commit()

            # V2-9.7E.41 graduation-only admission (supersedes the 900s maturity
            # gate). The candidate universe is the bounded confirmed origins from
            # this cycle. Eligibility is graduation, not age: only candidates with
            # exact PumpSwap graduation (owner == adopted program, exactly one
            # pool, base_mint == mint) bound to a valid post-graduation market
            # identity may reach holder, market-readiness and lifecycle work.
            # Bonding-curve / unpaired origins of any age remain discovery-only.
            permanent_mode = bool(
                supply is not None
                and bool(supply.diagnostics.get("permanent_availability"))
            )
            candidate_cap = _graduated_admission_candidate_cap(
                permanent_memory_observation=permanent_mode,
                ledger=ledger,
            )
            admission_inputs = (
                _permanent_observation_admission_inputs(supply)
                if permanent_mode and supply is not None
                else tuple(acquisition.origin_proofs)
                + graduated_supply_proofs
            )
            graduated_candidates, graduation_decisions = _graduated_admission(
                admission_inputs,
                graduation_proofs=dict(fixtures.pumpswap_proofs),
                candidate_cap=candidate_cap,
            )
            admission = self._full_pilot_graduation_diagnostics(
                graduation_decisions=graduation_decisions,
                acquisition=acquisition,
                enrichment=enrichment,
                fixtures=fixtures,
                staged_now=staged_now,
                admitted=len(graduated_candidates),
                candidate_cap=candidate_cap,
            )

            # Permanent conversion: a solitary market-ready survivor must still
            # receive holder/safety evaluation. Legacy (non-permanent) path keeps
            # the two-candidate pre-holder gate.
            if len(graduated_candidates) < 1 or (
                not permanent_mode and len(graduated_candidates) < 2
            ):
                # No holder, snapshot, lifecycle or memory work occurs. Persist
                # the ledger and close honestly with the graduation-only terminal
                # before any activation. Ungraduated origins remain staged as
                # pending discovery evidence.
                persist_ledger(
                    connection, run_id=command.run_id, cycle_id=cycle_id,
                    ledger=ledger, now=evaluated.isoformat(),
                )
                connection.commit()
                # V2-9.8B.4 reporting package only: preserve front-door candidate
                # outcomes and durable ledger totals for the terminal report. No
                # network I/O, no second source-accounting owner, no activation.
                front_door_candidates = []
                if supply is not None:
                    front_door_candidates = list(
                        (supply.front_door_report or {}).get("candidates") or []
                    )
                supply_diag = (
                    dict(supply.diagnostics) if supply is not None else {}
                )
                supply_terminal_cause = _graduated_supply_terminal_cause(supply)
                pre_lifecycle_admission = {
                    "required_token_capacity": 2,
                    (
                        "candidate_count"
                        if permanent_mode
                        else "graduated_candidate_count"
                    ): len(graduated_candidates),
                    "holder_eligible_count": 0,
                    "terminal_classification": supply_terminal_cause,
                    "shortage_classification": supply_diag.get(
                        "shortage_classification"
                    ),
                    "provider_failures": supply_diag.get(
                        "provider_failures", 0
                    ),
                    "pre_source_tracking_exclusions": supply_diag.get(
                        "pre_source_tracking_exclusions", 0
                    ),
                    "candidates": front_door_candidates,
                    "campaign_source_calls": int(ledger.governed_requests),
                    "campaign_scheduler_calls": 0,
                }
                terminal_reporting = {
                    "campaign_source_calls": int(ledger.governed_requests),
                    "campaign_scheduler_calls": 0,
                    "required_token_capacity": 2,
                    "blocked_supply_reason": supply_terminal_cause,
                    "candidates": front_door_candidates,
                    # V2-9.8B.21: honest exhaustion evidence when present.
                    "exhaustion_certificate": supply_diag.get(
                        "exhaustion_certificate"
                    ),
                    "shortage_classification": supply_diag.get(
                        "shortage_classification"
                    ),
                    "discovery_rounds": supply_diag.get("discovery_rounds"),
                    "eligible_reserve_count": supply_diag.get(
                        "eligible_reserve_count"
                    ),
                    "pre_lifecycle_admission": pre_lifecycle_admission,
                }
                return OriginLifecycleResult(
                    activation=ActivationResult(
                        terminal_status=supply_terminal_cause,
                        first_terminal_cause=supply_terminal_cause,
                        activated_slots=(),
                        selection_batch_id=None,
                    ),
                    lifecycle={
                        # Campaign identity only. Do not place campaign-run ID in
                        # run_id/factory_run_id; coordinator retains factory UUID
                        # solely after genuine lifecycle entry.
                        "campaign_run_id": command.run_id,
                        "run_status": "NOT_STARTED",
                        "stop_reason": supply_terminal_cause,
                        "first_terminal_cause": supply_terminal_cause,
                        "lifecycle_started": False,
                        "forbidden_deltas": {},
                        "pending_or_running_run_steps": 0,
                        "running_jobs_after_stop": 0,
                        "full_pilot_admission": admission,
                        "stopped_before_lifecycle": bool(stop_before_lifecycle),
                        "graduated_supply_diagnostics": (
                            dict(supply.diagnostics) if supply is not None else {}
                        ),
                        "front_door_candidates": front_door_candidates,
                        "blocked_supply_reason": supply_terminal_cause,
                        "pre_lifecycle_admission": pre_lifecycle_admission,
                        "terminal_reporting": terminal_reporting,
                    },
                    lifecycle_started=False,
                )

            # V2-9.7E.46B: provenance is recorded truthfully per candidate but is
            # NOT a compulsory pair quota. Provenance is used only to label the two
            # selected tokens honestly; selection itself walks one combined pool.
            provenance_by_mint = {}
            if supply is not None:
                provenance_by_mint = {
                    mint.lower(): str(candidate.get("provenance") or "")
                    for mint, candidate in dict(
                        getattr(supply, "holder_reserve_candidates", {})
                    ).items()
                }
            # Combined-pool holder funnel: partition gating disabled so any lawful
            # two-token composition (LATEST+LATEST, LATEST+PERSISTED,
            # PERSISTED+PERSISTED) is reachable. The funnel continues past holder
            # failures and stops after any two eligible candidates.
            # V2-9.8B.20: holder pacing/source I/O must not inherit an open write.
            if permanent_mode and pre_holder_accounting_projection is not None:
                from printer_v1.discovery.permanent_discovery_availability import (
                    assemble_and_reconcile_campaign_source_requests,
                    format_source_request_reconciliation_detail,
                )
                from printer_v1.operator_cli.holder_reliability_budget_control import (
                    build_ledger_from_exact_counts,
                    build_pre_holder_budget_snapshot,
                )

                prefixes = []
                scope_root = supply.diagnostics.get("request_key_root")
                if scope_root:
                    prefixes.append(str(scope_root))
                for key in (
                    "discovery_request_key_prefix",
                    "front_door_request_key_prefix",
                    "request_key_prefix",
                ):
                    value = supply.diagnostics.get(key)
                    if value and str(value) not in prefixes:
                        prefixes.append(str(value))
                pre_holder_reconciliation = (
                    assemble_and_reconcile_campaign_source_requests(
                        connection,
                        diagnostics=supply.diagnostics,
                        request_key_prefixes=prefixes,
                        request_key_root=(
                            str(scope_root) if scope_root else None
                        ),
                        campaign_source_request_scope=supply.diagnostics.get(
                            "campaign_source_request_scope"
                        ),
                    )
                )
                if pre_holder_reconciliation.get("status") != "OK":
                    detail = str(
                        pre_holder_reconciliation.get("terminal_detail")
                        or format_source_request_reconciliation_detail(
                            pre_holder_reconciliation
                        )
                        or pre_holder_reconciliation.get("categorical_detail")
                        or pre_holder_reconciliation.get("blocker")
                        or "PRE_HOLDER_RECONCILIATION_BLOCKED"
                    )
                    raise LiveOperationalError(
                        "CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH",
                        detail,
                    )
                projection = dict(pre_holder_accounting_projection())
                pre_holder_snapshot = build_pre_holder_budget_snapshot(
                    campaign_id=command.campaign_id,
                    governed_request_ids=tuple(
                        pre_holder_reconciliation.get(
                            "durable_campaign_request_ids"
                        )
                        or ()
                    ),
                    request_manifest=tuple(
                        pre_holder_reconciliation.get(
                            "campaign_source_request_manifest"
                        )
                        or ()
                    ),
                    campaign_transport_identities=tuple(
                        projection.get("campaign_transport_identities") or ()
                    ),
                    action_local_transport_identities=tuple(
                        projection.get("action_local_transport_identities") or ()
                    ),
                )
                ledger = build_ledger_from_exact_counts(
                    governed_request_count=(
                        pre_holder_snapshot.governed_request_count
                    ),
                    underlying_transport_operations=(
                        pre_holder_snapshot.measured_transport_count
                    ),
                    deadline_at=deadline,
                )
                supply.diagnostics["pre_holder_source_request_reconciliation"] = (
                    pre_holder_reconciliation
                )
                supply.diagnostics["pre_holder_budget_snapshot"] = {
                    "governed_request_ids": list(
                        pre_holder_snapshot.governed_request_ids
                    ),
                    "measured_transport_identity_keys": [
                        list(key)
                        for key in pre_holder_snapshot.measured_transport_identity_keys
                    ],
                    "governed_request_count": (
                        pre_holder_snapshot.governed_request_count
                    ),
                    "measured_transport_count": (
                        pre_holder_snapshot.measured_transport_count
                    ),
                    "zero_transport_operations": (
                        pre_holder_snapshot.zero_transport_operations
                    ),
                    "reserved_snapshot_operations": (
                        pre_holder_snapshot.reserved_snapshot_operations
                    ),
                    "reserved_snapshot_completion_operations": (
                        pre_holder_snapshot.reserved_snapshot_completion_operations
                    ),
                }
            release_write_transaction(connection)
            holder_transport_before = int(ledger.underlying_transport_operations)
            from printer_v1.operator_cli.later_cycle_graduated_supply import (
                selected_slot_holder_candidates,
            )

            selected_holder_targets = (
                selected_slot_holder_candidates(supply)
                if supply is not None
                else ()
            )
            holder_result = self._evaluate_holder_eligibility(
                connection,
                command=command,
                cycle_id=cycle_id,
                bounded_candidates=(
                    selected_holder_targets or graduated_candidates
                ),
                evaluated=evaluated,
                deadline=deadline,
                ledger=ledger,
                timeout_seconds=timeout_seconds,
                context_factories=lk.get("context_adapter_factories"),
                request_pacer=lk.pop("holder_request_pacer", None),
                partition_by_mint=None,
                tracking_pair_by_mint={
                    mint.lower(): proof.pool_address
                    for mint, proof in fixtures.pumpswap_proofs.items()
                },
                eligible_target=(
                    4
                    if supply is not None
                    and bool(supply.diagnostics.get("permanent_availability"))
                    else 2
                ),
                permanent_memory_observation=bool(
                    supply is not None
                    and bool(supply.diagnostics.get("permanent_availability"))
                ),
                holder_transport_identity_observer=transport_identity_observer,
                holder_stage_evidence_sealer=holder_stage_evidence_sealer,
                campaign_request_key_root=(
                    str(supply.diagnostics.get("request_key_root") or "").strip()
                    if supply is not None
                    else None
                ),
            )
            holder_facts = dict(holder_result.holder_facts)
            ledger = holder_result.ledger
            holder_transport_used = (
                int(ledger.underlying_transport_operations)
                - holder_transport_before
            )
            if (
                supply is not None
                and bool(supply.diagnostics.get("permanent_availability"))
            ):
                if holder_transport_used > 8:
                    raise LiveOperationalError(
                        "PERMANENT_DISCOVERY_HOLDER_SAFETY_RESERVATION_EXCEEDED",
                        str(holder_transport_used),
                    )
                stage_used = dict(
                    supply.diagnostics.get("stage_operations_used") or {}
                )
                stage_used["holder_safety"] = holder_transport_used
                supply.diagnostics["stage_operations_used"] = stage_used
            if (
                supply is not None
                and bool(supply.diagnostics.get("permanent_availability"))
            ):
                from printer_v1.discovery.permanent_discovery_availability import (
                    CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH,
                    FULLY_ELIGIBLE,
                    MEMORY_OBSERVATION_ELIGIBLE,
                    NETWORK,
                    assemble_and_reconcile_campaign_source_requests,
                    freeze_eligible_reserve_for_campaign,
                    upsert_reserve_layer,
                )

                # Memory observation is independent of holder pass/fail.
                # Holder concentration and unavailable evidence remain context.
                observation_rows = []
                tracking_exclusions: list[dict[str, Any]] = []
                from printer_v1.lifecycle.tracking_queue import (
                    assess_possible_tracking_claim_by_identity,
                )
                for proof in graduated_candidates:
                    mint_key = proof.mint.lower()
                    fact = holder_facts.get(mint_key, {})
                    item = dict(supply.holder_reserve_candidates.get(mint_key, {}))
                    if not item and not getattr(proof, "mint", None):
                        continue
                    expiry = item.get("evidence_expires_at")
                    if not expiry:
                        # No alternate can exist without an explicit current
                        # evidence boundary. Selected candidates remain governed
                        # by the same rule; this never fabricates freshness.
                        continue
                    holder_context = _holder_observation_context(fact)
                    exact_pool = str(
                        item.get("pool")
                        or item.get("pumpswap_pool")
                        or proof.bonding_curve
                    )
                    # Lane unknown pre-freeze: dual-lane possible-claim only.
                    # Exact FAST/NORMAL is frozen later from classification.
                    tracking_assessment = assess_possible_tracking_claim_by_identity(
                        connection,
                        token_mint=proof.mint,
                        pair_address=exact_pool,
                        assessed_at=evaluated,
                    )
                    tracking_eligible = bool(tracking_assessment.eligible)
                    tracking_requalification_required = bool(
                        tracking_assessment.requalification_eligible
                    )
                    if not tracking_eligible or tracking_requalification_required:
                        tracking_reason = str(
                            tracking_assessment.reason_code
                            or "TRACKING_HANDOFF_INELIGIBLE"
                        )
                        tracking_assessment_evidence = {
                            "eligible": tracking_eligible,
                            "reason_code": tracking_reason,
                            "category": str(
                                getattr(tracking_assessment, "category", None)
                                or tracking_reason
                            ),
                            "queue_id": tracking_assessment.queue_id,
                            "queue_status": tracking_assessment.queue_status,
                            "requalification_required": (
                                tracking_requalification_required
                            ),
                            "cooldown_until": tracking_assessment.cooldown_until,
                            "assessed_at": evaluated.isoformat(),
                        }
                        exclusion = {
                            "mint": proof.mint,
                            "pool": exact_pool,
                            "reason": tracking_reason,
                            "tracking_handoff_eligible": tracking_eligible,
                            "tracking_requalification_required": (
                                tracking_requalification_required
                            ),
                            "tracking_handoff": dict(tracking_assessment_evidence),
                            "holder_safety": dict(fact),
                        }
                        tracking_exclusions.append(exclusion)
                        upsert_reserve_layer(
                            connection,
                            network=NETWORK,
                            mint=exclusion["mint"],
                            pool=exclusion["pool"],
                            layer=MEMORY_OBSERVATION_ELIGIBLE,
                            reserve_state="EXCLUDED",
                            reason=tracking_reason,
                            observed_at=evaluated.isoformat(),
                            next_lawful_action_at=(
                                tracking_assessment.cooldown_until
                            ),
                            evidence_expires_at=str(expiry),
                            source_provenance={"market": item.get("provenance")},
                            evidence={
                                "tracking_handoff": dict(
                                    tracking_assessment_evidence
                                ),
                                "holder_safety": dict(fact),
                                "memory_observation_eligible": False,
                            },
                            campaign_id=command.campaign_id,
                        )
                        continue
                    holder_actually_eligible = bool(
                        holder_context["fully_eligible"]
                    ) and not bool(holder_result.accounting_blocker)
                    holder_condition = str(holder_context["holder_condition"])
                    holder_evidence_status = str(
                        holder_context["holder_evidence_status"]
                    )
                    future_action = str(
                        holder_context["future_action_eligibility"]
                    )
                    observation = {
                        **item,
                        "mint": proof.mint,
                        "pool": str(
                            item.get("pool")
                            or item.get("pumpswap_pool")
                            or proof.bonding_curve
                        ),
                        "memory_observation_eligible": True,
                        # fully_eligible reflects actual holder pass only; it is
                        # never a memory admission input.
                        "fully_eligible": holder_actually_eligible,
                        "evidence_expires_at": expiry,
                        "holder_safety": dict(fact),
                        "holder_condition": holder_condition,
                        "holder_evidence_status": holder_evidence_status,
                        "future_action_eligibility": future_action,
                        "liquidity_observed_at": str(
                            item.get("liquidity_observed_at")
                            or (item.get("liquidity") or {}).get(
                                "liquidity_observed_at"
                            )
                            or ""
                        ),
                        "activation_route": _memory_observation_activation_route(
                            admission_authority=item.get("admission_authority"),
                            carried_route=(
                                item.get("activation_route")
                                or getattr(proof, "origin_route", None)
                            ),
                        ),
                        "tracking_handoff_eligible": tracking_eligible,
                        "tracking_handoff_reason": str(
                            tracking_assessment.reason_code or "ELIGIBLE"
                        ),
                        "tracking_queue_id": tracking_assessment.queue_id,
                        "tracking_queue_status": (
                            tracking_assessment.queue_status
                        ),
                        "tracking_requalification_required": False,
                        "cooldown_until": tracking_assessment.cooldown_until,
                        "tracking_assessed_at": evaluated.isoformat(),
                    }
                    observation_rows.append(observation)
                    upsert_reserve_layer(
                        connection,
                        network=NETWORK,
                        mint=observation["mint"],
                        pool=observation["pool"],
                        layer=MEMORY_OBSERVATION_ELIGIBLE,
                        reserve_state="ACTIVE",
                        reason="IDENTITY_POOL_LIQUIDITY_MEMORY_OBSERVATION_PASS",
                        observed_at=evaluated.isoformat(),
                        next_lawful_action_at=None,
                        evidence_expires_at=str(expiry),
                        source_provenance={
                            "market": item.get("provenance"),
                            "holder_source": fact.get("source_name"),
                        },
                        evidence={
                            "liquidity": dict(item.get("liquidity") or {}),
                            "holder_safety": dict(fact),
                            "holder_condition": holder_condition,
                            "holder_evidence_status": holder_evidence_status,
                            "future_action_eligibility": future_action,
                            "memory_observation_eligible": True,
                        },
                        campaign_id=command.campaign_id,
                    )
                    # FULLY_ELIGIBLE retained only for future action-specific
                    # policy when holder actually passes. Never for memory path.
                    if holder_actually_eligible:
                        upsert_reserve_layer(
                            connection,
                            network=NETWORK,
                            mint=observation["mint"],
                            pool=observation["pool"],
                            layer=FULLY_ELIGIBLE,
                            reserve_state="ACTIVE",
                            reason="IDENTITY_MARKET_HOLDER_SAFETY_PASS",
                            observed_at=evaluated.isoformat(),
                            next_lawful_action_at=None,
                            evidence_expires_at=str(expiry),
                            source_provenance={
                                "market": item.get("provenance"),
                                "holder_source": fact.get("source_name"),
                            },
                            evidence={
                                "liquidity": dict(item.get("liquidity") or {}),
                                "holder_safety": dict(fact),
                            },
                            campaign_id=command.campaign_id,
                        )
                supply.diagnostics["memory_observation_tracking_exclusions"] = (
                    tracking_exclusions
                )
                # Retained-evidence role completeness is binary eligibility before
                # the neutral seeded freeze. Incomplete DIRECT_PUMP / MARKET
                # nominees must never reach select-then-reject activation build.
                #
                # Current-run provenance authority is ONLY the already-produced
                # pre-holder reconciliation plus the validated
                # CampaignSourceRequestScope. Never reassemble / reconstruct
                # either after holder evaluation.
                from printer_v1.discovery.memory_observation_activation import (
                    RETAINED_EVIDENCE_ROLE_INCOMPLETE_PRE_FREEZE,
                )
                from printer_v1.discovery.permanent_discovery_availability import (
                    validate_campaign_source_request_scope,
                )

                pre_holder_recon = dict(
                    supply.diagnostics.get(
                        "pre_holder_source_request_reconciliation"
                    )
                    or {}
                )
                pre_holder_snapshot = dict(
                    supply.diagnostics.get("pre_holder_budget_snapshot") or {}
                )
                provenance_unavailable_detail = None
                validated_scope = None
                try:
                    validated_scope = validate_campaign_source_request_scope(
                        supply.diagnostics.get("campaign_source_request_scope"),
                        execution_id=selection_seed,
                        campaign_id=command.campaign_id,
                        run_id=command.run_id,
                        cycle_id=cycle_id,
                    )
                except ValueError as exc:
                    provenance_unavailable_detail = (
                        str(exc).strip()
                        or "RETAINED_CURRENT_RUN_PROVENANCE_UNAVAILABLE"
                    )
                if provenance_unavailable_detail is None:
                    if (
                        not pre_holder_recon
                        or str(pre_holder_recon.get("status") or "") != "OK"
                        or not pre_holder_recon.get(
                            "campaign_source_request_manifest"
                        )
                    ):
                        provenance_unavailable_detail = (
                            "RETAINED_CURRENT_RUN_PROVENANCE_UNAVAILABLE"
                        )
                if provenance_unavailable_detail is not None:
                    role_complete_observation_rows = []
                    retained_role_pre_freeze_exclusions = [
                        {
                            "mint": None,
                            "pool": None,
                            "admission_authority": None,
                            "required_roles": (),
                            "present_roles": (),
                            "missing_roles": (),
                            "qualification_failures": {
                                "current_run_provenance": (
                                    "RETAINED_CURRENT_RUN_PROVENANCE_UNAVAILABLE"
                                )
                            },
                            "disposition": (
                                RETAINED_EVIDENCE_ROLE_INCOMPLETE_PRE_FREEZE
                            ),
                            "detail": "RETAINED_CURRENT_RUN_PROVENANCE_UNAVAILABLE",
                            "scope_validation_detail": (
                                None
                                if provenance_unavailable_detail
                                == "RETAINED_CURRENT_RUN_PROVENANCE_UNAVAILABLE"
                                else provenance_unavailable_detail
                            ),
                        }
                    ]
                else:
                    assert validated_scope is not None
                    measured_keys = list(
                        pre_holder_snapshot.get(
                            "measured_transport_identity_keys"
                        )
                        or ()
                    )
                    if not measured_keys:
                        measured_keys = [
                            list(key)
                            for entry in (
                                pre_holder_recon.get(
                                    "campaign_source_request_manifest"
                                )
                                or ()
                            )
                            for key in (
                                entry.get("transport_identity_keys") or ()
                            )
                        ]
                    (
                        role_complete_observation_rows,
                        retained_role_pre_freeze_exclusions,
                    ) = _filter_observation_rows_by_retained_role_completeness(
                        connection,
                        observation_rows,
                        now=evaluated.isoformat(),
                        request_key_root=str(validated_scope.request_key_root),
                        campaign_id=str(validated_scope.campaign_id),
                        run_id=str(validated_scope.run_id),
                        cycle_id=str(validated_scope.cycle_id),
                        campaign_source_request_manifest=list(
                            pre_holder_recon.get(
                                "campaign_source_request_manifest"
                            )
                            or ()
                        ),
                        measured_transport_identity_keys=measured_keys,
                        require_current_run_provenance=True,
                    )
                supply.diagnostics["retained_evidence_role_pre_freeze"] = {
                    "input_count": len(observation_rows),
                    "complete_count": len(role_complete_observation_rows),
                    "excluded_count": len(retained_role_pre_freeze_exclusions),
                    "exclusions": retained_role_pre_freeze_exclusions,
                    "current_run_provenance_available": (
                        provenance_unavailable_detail is None
                    ),
                }
                # Post-filter freeze depth is the sole admission authority.
                # Never use raw observation_rows count for coverage decisions.
                # Historical-disjointness enforcement depends on the authoritative
                # CURRENT cycle ordinal. Real production persists Cycle 1 before
                # freeze, so COUNT(*) of campaign-cycle rows is not a prior-cycle
                # proxy and must not decide enforcement.
                current_cycle_ordinal = (
                    _resolve_current_cycle_ordinal_for_historical_disjointness(
                        connection,
                        campaign_id=str(command.campaign_id),
                        campaign_run_id=str(command.run_id),
                        cycle_id=str(cycle_id),
                    )
                )
                frozen_eligible_reserve = freeze_eligible_reserve_for_campaign(
                    connection,
                    role_complete_observation_rows,
                    cycle_seed=selection_seed,
                    at=datetime.now(timezone.utc).isoformat(),
                    campaign_id=str(command.campaign_id),
                    campaign_run_id=str(command.run_id),
                    enforce_campaign_historical_disjointness=(
                        current_cycle_ordinal > 1
                    ),
                )
                freeze_authority = dict(
                    frozen_eligible_reserve.selection_authority or {}
                )
                supply.diagnostics["observation_reserve"] = freeze_authority
                supply.diagnostics["freeze_depth_enforcement"] = {
                    "enforced": True,
                    "selected_count": len(frozen_eligible_reserve.selected),
                    "alternate_count": len(frozen_eligible_reserve.alternates[:2]),
                    **freeze_authority,
                }
                if freeze_authority.get("coverage_blocker"):
                    supply.diagnostics["freeze_depth_enforcement"][
                        "terminal"
                    ] = "PRE_LIFECYCLE_DISCOVERY_SELECTION_COVERAGE_INSUFFICIENT"
                    supply.diagnostics["freeze_depth_enforcement"][
                        "durable_report_required"
                    ] = True
                else:
                    for reserve_state, items in (
                        ("SELECTED", frozen_eligible_reserve.selected),
                        ("ALTERNATE", frozen_eligible_reserve.alternates[:2]),
                    ):
                        for item in items:
                            connection.execute(
                                """UPDATE printer_discovery_reserve_layers
                                   SET reserve_state=?,updated_at=?
                                   WHERE network=? AND mint_identity=?
                                     AND pool_address=? AND reserve_layer=?""",
                                (
                                    reserve_state,
                                    evaluated.isoformat(),
                                    NETWORK,
                                    str(item.get("mint") or ""),
                                    str(item.get("pool") or ""),
                                    MEMORY_OBSERVATION_ELIGIBLE,
                                ),
                            )
                # Campaign-wide source-request reconciliation before readiness.
                # Holder stage result is the sole owner of holder IDs/coverage;
                # never invent IDs and never fall back to ledger.request_ids.
                supply.diagnostics["holder_context"] = (
                    holder_result.as_holder_context_diagnostics()
                )
                supply.diagnostics["holder_source_request_ids"] = list(
                    holder_result.source_request_ids
                )
                supply.diagnostics["holder_source_request_coverage"] = [
                    dict(entry)
                    for entry in holder_result.source_request_coverage
                ]
                # Prefer stage-reported durable IDs + explicit discovery request
                # key prefixes. Do not scrape the whole DB by campaign/run id
                # alone — that can pull unrelated holder/other rows and false
                # reconciliation mismatches. Permanent operational mode uses the
                # typed invocation root only.
                prefixes = []
                scope_root = supply.diagnostics.get("request_key_root")
                if scope_root:
                    prefixes.append(str(scope_root))
                for key in (
                    "discovery_request_key_prefix",
                    "front_door_request_key_prefix",
                    "request_key_prefix",
                ):
                    value = supply.diagnostics.get(key)
                    if value and str(value) not in prefixes:
                        prefixes.append(str(value))
                recon = assemble_and_reconcile_campaign_source_requests(
                    connection,
                    diagnostics=supply.diagnostics,
                    request_key_prefixes=prefixes,
                    request_key_root=(
                        str(scope_root) if scope_root else None
                    ),
                    campaign_source_request_scope=supply.diagnostics.get(
                        "campaign_source_request_scope"
                    ),
                )
                supply.diagnostics[
                    "campaign_source_request_reconciliation"
                ] = recon
                supply.diagnostics["durable_campaign_request_ids"] = list(
                    recon.get("durable_campaign_request_ids") or ()
                )
                supply.diagnostics["campaign_source_request_manifest"] = list(
                    recon.get("campaign_source_request_manifest") or ()
                )
                supply.diagnostics["campaign_source_request_count"] = int(
                    recon.get("campaign_source_request_count") or 0
                )
                supply.diagnostics["campaign_transport_operation_count"] = int(
                    recon.get("campaign_transport_operation_count") or 0
                )
                # Diagnostic comparison only — not the authoritative count.
                supply.diagnostics["holder_ledger_governed_requests"] = int(
                    ledger.governed_requests
                )
                if (
                    recon.get("status") == "OK"
                    and frozen_eligible_reserve is not None
                    and len(frozen_eligible_reserve.selected) == 2
                ):
                    candidate_expiries = [
                        datetime.fromisoformat(
                            str(item["evidence_expires_at"]).replace(
                                "Z", "+00:00"
                            )
                        )
                        for item in frozen_eligible_reserve.selected
                    ]
                    activation_expiry = min(
                        min(candidate_expiries),
                        evaluated + timedelta(minutes=10),
                    ).isoformat()
                    try:
                        memory_activation_set = _build_frozen_memory_activation_set(
                            connection,
                            frozen_reserve=frozen_eligible_reserve,
                            readiness_id=(
                                f"{command.run_id}:{cycle_id}:pilot-input"
                            ),
                            selection_seed=selection_seed,
                            campaign_id=str(command.campaign_id),
                            run_id=str(command.run_id),
                            cycle_id=cycle_id,
                            manifest=(
                                recon.get("campaign_source_request_manifest")
                                or recon.get("manifest")
                                or ()
                            ),
                            measured_transport_identity_keys=(
                                (
                                    supply.diagnostics.get(
                                        "pre_holder_budget_snapshot"
                                    )
                                    or {}
                                ).get("measured_transport_identity_keys")
                                or ()
                            ),
                            frozen_at=frozen_eligible_reserve.frozen_at,
                            expires_at=activation_expiry,
                        )
                    except Exception as exc:
                        from printer_v1.discovery.memory_observation_activation import (
                            MemoryObservationActivationError,
                        )

                        if not isinstance(exc, MemoryObservationActivationError):
                            raise
                        memory_activation_contract_blocker = exc.code
                        supply.diagnostics["memory_activation_contract"] = {
                            "status": "BLOCKED",
                            "first_blocker": exc.code,
                            "detail": exc.detail,
                        }
                        memory_activation_set = None
                    if memory_activation_set is not None:
                        supply.diagnostics["memory_activation_contract"] = {
                            "activation_purpose": "MEMORY_OBSERVATION",
                            "readiness_id": memory_activation_set.readiness_id,
                            "ordered_selected_candidates": [
                                {
                                    "slot_ordinal": item.slot_ordinal,
                                    "mint": item.mint,
                                    "pool": item.pool,
                                }
                                for item in memory_activation_set.selected
                            ],
                            "report_only_alternates": [
                                {"mint": item.mint, "pool": item.pool}
                                for item in memory_activation_set.alternates
                            ],
                            "evidence_reuse_kind": (
                                "RETAINED_GOVERNED_EVIDENCE_REFERENCE"
                            ),
                        }
            connection.commit()
        finally:
            connection.close()

        readiness_bundle = None
        selection_terminal = None
        eligible_alternates: list[dict[str, Any]] = []
        if supply is not None and provenance_by_mint:
            # Deterministic combined order: honour the seeded combined reserve order
            # (front door) so which two eligible tokens are chosen is fair and
            # replayable, never provider/recency/liquidity biased.
            admitted_by_mint = {p.mint.lower(): p for p in graduated_candidates}
            if frozen_eligible_reserve is not None:
                reserve_order = [
                    str(item.get("mint") or "").lower()
                    for item in frozen_eligible_reserve.selected
                    if str(item.get("mint") or "").lower() in admitted_by_mint
                ]
                eligible_alternates = [
                    dict(item) for item in frozen_eligible_reserve.alternates[:2]
                ]
            else:
                reserve_order = [
                    p.mint.lower()
                    for p in getattr(supply, "holder_reserve_supply", ())
                    if p.mint.lower() in admitted_by_mint
                ]
                for mint in sorted(admitted_by_mint):
                    if mint not in reserve_order:
                        reserve_order.append(mint)
            chosen: list[Any] = []
            seen: set[str] = set()
            # Freeze-depth admission from post-filter freeze authority only.
            depth_blocker = bool(
                (supply.diagnostics.get("observation_reserve") or {}).get(
                    "coverage_blocker"
                )
            )
            recon_status = (
                supply.diagnostics.get("campaign_source_request_reconciliation")
                or {}
            )
            recon_blocker = str(recon_status.get("status") or "OK") != "OK"
            if recon_blocker:
                depth_blocker = True  # block readiness/handoff on reconcile failure
            for mint in reserve_order:
                # Memory freeze already chose from MEMORY_OBSERVATION_ELIGIBLE.
                # Do not re-gate selection on holder pass; holder is context only.
                if depth_blocker:
                    break
                if mint not in seen and mint in admitted_by_mint:
                    if frozen_eligible_reserve is not None:
                        # Only freeze-selected mints may enter the two-slot handoff.
                        selected_mints = {
                            str(item.get("mint") or "").lower()
                            for item in frozen_eligible_reserve.selected
                        }
                        if mint in selected_mints or not selected_mints:
                            if mint in selected_mints:
                                chosen.append(admitted_by_mint[mint])
                                seen.add(mint)
                    else:
                        # Non-permanent path: never invent holder-safe admission
                        # for memory; require explicit memory observation flag
                        # when present on reserve candidates.
                        reserve_item = dict(
                            supply.holder_reserve_candidates.get(mint) or {}
                        )
                        if reserve_item.get("memory_observation_eligible") is True:
                            chosen.append(admitted_by_mint[mint])
                            seen.add(mint)
                if len(chosen) == 2:
                    break

            if (
                len(chosen) == 2
                and not depth_blocker
                and not recon_blocker
                and (
                    frozen_eligible_reserve is None
                    or memory_activation_set is not None
                )
            ):
                graduated_candidates = tuple(chosen)
                selection_terminal = "PILOT_INPUT_READY"
                from printer_v1.operator_cli.pilot_input_readiness import (
                    READINESS_PURPOSE_MEMORY_OBSERVATION,
                    ReadinessCandidate,
                    build_pilot_input_ready_bundle,
                )

                def readiness_candidate(proof: Any) -> ReadinessCandidate:
                    item = dict(supply.holder_reserve_candidates[proof.mint.lower()])
                    liquidity = dict(item.get("liquidity") or {})
                    fact = dict(holder_facts.get(proof.mint.lower()) or {})
                    activation_candidate = next(
                        (
                            value
                            for value in (
                                memory_activation_set.selected
                                if memory_activation_set is not None
                                else ()
                            )
                            if value.mint.lower() == proof.mint.lower()
                        ),
                        None,
                    )
                    # Record actual holder eligibility; never force True for
                    # legacy gates. Memory path already admitted without it.
                    actual_holder = _holder_condition_passes(fact)
                    holder_label = str(
                        fact.get("holder_concentration_label")
                        or item.get("holder_condition")
                        or "HOLDER_CONCENTRATION_UNKNOWN"
                    )
                    resolved_admission_authority = (
                        _readiness_admission_authority(activation_candidate)
                    )
                    return ReadinessCandidate(
                        mint=proof.mint,
                        pool=str(item["pool"]),
                        market_identity=str(item["market_identity"]),
                        liquidity_usd=float(liquidity["liquidity_usd"]),
                        liquidity_observed_at=str(
                            (
                                activation_candidate.liquidity_observed_at
                                if activation_candidate is not None
                                else item.get("liquidity_observed_at")
                                or liquidity.get("liquidity_observed_at")
                                or evaluated_at
                            )
                        ),
                        activation_route=_memory_observation_activation_route(
                            admission_authority=resolved_admission_authority,
                            carried_route=(
                                getattr(
                                    activation_candidate,
                                    "activation_route",
                                    None,
                                )
                                if activation_candidate is not None
                                else None
                            )
                            or item.get("activation_route")
                            or getattr(proof, "origin_route", None),
                        ),
                        holder_eligible=actual_holder,
                        # True provenance per token; a LATEST token is never
                        # relabelled PERSISTED (or vice versa).
                        provenance=provenance_by_mint.get(proof.mint.lower(), ""),
                        memory_observation_eligible=True,
                        holder_condition=holder_label,
                        future_action_eligibility=str(
                            item.get("future_action_eligibility")
                            or "BLOCKED_OR_UNKNOWN"
                        ),
                        admission_authority=resolved_admission_authority,
                        slot_ordinal=(
                            None
                            if activation_candidate is None
                            else activation_candidate.slot_ordinal
                        ),
                        tracking_eligible=(
                            None
                            if activation_candidate is None
                            else activation_candidate.tracking_feasibility.eligible
                        ),
                        tracking_reason=(
                            None
                            if activation_candidate is None
                            else activation_candidate.tracking_feasibility.reason_code
                        ),
                        tracking_requalification_required=(
                            False
                            if activation_candidate is None
                            else activation_candidate.tracking_feasibility.requalification_required
                        ),
                        retained_source_request_ids=(
                            ()
                            if activation_candidate is None
                            else tuple(
                                reference.source_request_id
                                for reference in activation_candidate.retained_evidence_references
                            )
                        ),
                        retained_source_response_ids=(
                            ()
                            if activation_candidate is None
                            else tuple(
                                reference.source_response_id
                                for reference in activation_candidate.retained_evidence_references
                            )
                        ),
                    )

                readiness_connection = sqlite3.connect(Path(command.db_path))
                readiness_connection.execute("PRAGMA foreign_keys = ON")
                try:
                    recon = (
                        supply.diagnostics.get(
                            "campaign_source_request_reconciliation"
                        )
                        or {}
                    )
                    readiness_bundle = build_pilot_input_ready_bundle(
                        readiness_connection,
                        readiness_id=f"{command.run_id}:{cycle_id}:pilot-input",
                        latest=readiness_candidate(chosen[0]),
                        persisted=readiness_candidate(chosen[1]),
                        holder_evidence={
                            mint: dict(fact) for mint, fact in holder_facts.items()
                        },
                        source_ledger={
                            "operation_ceiling": ledger.operation_ceiling,
                            # Diagnostic comparison only.
                            "holder_ledger_governed_requests": ledger.governed_requests,
                            "campaign_source_request_count": int(
                                recon.get("campaign_source_request_count")
                                or supply.diagnostics.get(
                                    "campaign_source_request_count"
                                )
                                or 0
                            ),
                            "campaign_transport_operation_count": int(
                                recon.get("campaign_transport_operation_count")
                                or supply.diagnostics.get(
                                    "campaign_transport_operation_count"
                                )
                                or 0
                            ),
                            "campaign_source_request_reconciliation": recon.get(
                                "campaign_source_request_reconciliation"
                            )
                            or recon,
                            "durable_campaign_request_ids": list(
                                recon.get("durable_campaign_request_ids") or ()
                            ),
                            "campaign_source_request_manifest": list(
                                recon.get("campaign_source_request_manifest") or ()
                            ),
                            "underlying_transport_operations": (
                                ledger.underlying_transport_operations
                            ),
                            "zero_transport_operations": ledger.zero_transport_operations,
                        },
                        selection_seed=selection_seed,
                        git_provenance_identity=str(
                            command.launch_git_provenance.get("git_head") or ""
                        ),
                        configuration_hash=command.configuration_hash,
                        expires_at=(evaluated + timedelta(minutes=10)).isoformat(),
                        now=evaluated.isoformat(),
                        readiness_purpose=READINESS_PURPOSE_MEMORY_OBSERVATION,
                    )
                finally:
                    readiness_connection.close()
            else:
                # Fewer than two memory-observation freeze selections, freeze
                # depth coverage blocker, or source-request reconciliation
                # mismatch. Classify the terminal honestly.
                graduated_candidates = ()
                if memory_activation_contract_blocker:
                    selection_terminal = memory_activation_contract_blocker
                    eligible_alternates = [
                        dict(item)
                        for item in (
                            frozen_eligible_reserve.alternates[:2]
                            if frozen_eligible_reserve is not None
                            else ()
                        )
                    ]
                elif recon_blocker:
                    selection_terminal = (
                        "CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH"
                    )
                    eligible_alternates = []
                elif depth_blocker:
                    selection_terminal = (
                        "PRE_LIFECYCLE_DISCOVERY_SELECTION_COVERAGE_INSUFFICIENT"
                    )
                    eligible_alternates = []
                else:
                    selection_terminal = _classify_pre_lifecycle_terminal(
                        holder_facts, reserve_count=len(admitted_by_mint)
                    )

        front_door_candidates = (
            list((supply.front_door_report or {}).get("candidates") or [])
            if supply is not None else []
        )
        admission_candidates: list[dict[str, Any]] = []
        for candidate in front_door_candidates:
            item = dict(candidate)
            mint_key = str(item.get("mint") or "").lower()
            holder = dict(holder_facts.get(mint_key) or {})
            tracking = dict(item.get("tracking_handoff") or {})
            # Keep tracking assessment under tracking_handoff and holder facts
            # under holder_safety. Never store holder concentration under
            # tracking_handoff.
            if holder:
                # Only adopt tracking-assessment fields if the holder fact
                # payload actually carries them from an identity assessment.
                for key in (
                    "category",
                    "tracking_queue_id",
                    "tracking_queue_status",
                    "queue_id",
                    "queue_status",
                    "requalification_required",
                    "cooldown_until",
                    "historical_cooldown_expiry_derived",
                    "reason_code",
                    "eligible",
                    "assessed_at",
                ):
                    if key in holder and holder.get(key) is not None:
                        tracking.setdefault(key, holder.get(key))
            item["tracking_handoff"] = {
                key: value for key, value in tracking.items() if value is not None
            }
            item["holder_safety"] = holder
            item["holder_eligibility"] = holder
            item["excluded_before_market_source"] = bool(
                item.get("excluded_before_market_source")
            )
            item["fresh_requalification_required"] = bool(
                tracking.get("requalification_required")
            )
            item["fresh_requalification_completed"] = False
            admission_candidates.append(item)

        supply_diagnostics = (
            dict(supply.diagnostics) if supply is not None else {}
        )
        pre_lifecycle_admission = {
            "required_token_capacity": 2,
            (
                "candidate_count"
                if permanent_mode
                else "graduated_candidate_count"
            ): len(graduated_candidates),
            "holder_eligible_count": sum(
                1 for fact in holder_facts.values() if fact.get("eligible")
            ),
            "terminal_classification": selection_terminal,
            "shortage_classification": supply_diagnostics.get(
                "shortage_classification"
            ),
            "exhaustion_certificate": _project_supply_exhaustion_certificate(supply_diagnostics),
            "provider_failures": supply_diagnostics.get("provider_failures", 0),
            "pre_source_tracking_exclusions": supply_diagnostics.get(
                "pre_source_tracking_exclusions", 0
            ),
            "retained_evidence_role_pre_freeze": dict(
                supply_diagnostics.get("retained_evidence_role_pre_freeze") or {}
            ),
            "memory_activation_contract": dict(
                supply_diagnostics.get("memory_activation_contract") or {}
            ),
            "candidates": admission_candidates,
            "campaign_source_calls": int(
                (supply_diagnostics.get("campaign_source_request_count"))
                if supply_diagnostics.get("campaign_source_request_count") is not None
                else ledger.governed_requests
            ),
            "campaign_source_request_count": int(
                supply_diagnostics.get("campaign_source_request_count")
                or 0
            ),
            "campaign_transport_operation_count": int(
                supply_diagnostics.get("campaign_transport_operation_count")
                or 0
            ),
            "holder_ledger_governed_requests": int(ledger.governed_requests),
            "durable_campaign_request_ids": list(
                supply_diagnostics.get("durable_campaign_request_ids") or ()
            ),
            "campaign_source_request_manifest": list(
                supply_diagnostics.get("campaign_source_request_manifest") or ()
            ),
            "campaign_source_request_reconciliation": dict(
                supply_diagnostics.get("campaign_source_request_reconciliation")
                or {}
            ),
            "campaign_scheduler_calls": 0,
            "selected_identities": [proof.mint for proof in graduated_candidates],
            "ordered_selected_slots": [
                {
                    "slot_ordinal": ordinal,
                    "mint": proof.mint,
                    "pool": str(
                        (
                            supply.holder_reserve_candidates.get(
                                proof.mint.lower(), {}
                            ).get("pool")
                            or getattr(
                                fixtures.pumpswap_proofs.get(proof.mint),
                                "pool_address",
                                None,
                            )
                            or proof.bonding_curve
                        )
                    ),
                }
                for ordinal, proof in enumerate(graduated_candidates, start=1)
            ],
            "alternate_identities": [
                str(item.get("mint") or "") for item in eligible_alternates
            ],
        }

        # V2-9.7E.44/46B bounded pre-lifecycle boundary: return atomic two-slot
        # readiness (admission + holder eligibility + handoff readiness) without
        # invoking the scheduler/lifecycle/memory driver. No tracking is enqueued.
        if stop_before_lifecycle or (
            supply is not None and provenance_by_mint and readiness_bundle is None
        ):
            holder_eligible = sum(
                1 for fact in holder_facts.values() if fact.get("eligible")
            )
            # Permanent-discovery memory path: atomic readiness is freeze/selection
            # depth, not holder pass. Holder remains context only.
            depth_blocker = bool(
                (
                    (supply.diagnostics if supply is not None else {}).get(
                        "observation_reserve"
                    )
                    or {}
                ).get("coverage_blocker")
            )
            if supply is not None and bool(
                supply.diagnostics.get("permanent_availability")
            ):
                atomic_ready = (
                    readiness_bundle is not None and len(graduated_candidates) >= 2
                )
            else:
                atomic_ready = len(graduated_candidates) >= 2 and holder_eligible >= 2
            if depth_blocker and selection_terminal is None:
                selection_terminal = (
                    "PRE_LIFECYCLE_DISCOVERY_SELECTION_COVERAGE_INSUFFICIENT"
                )
            terminal = (
                "PILOT_INPUT_READY"
                if readiness_bundle is not None
                else (
                    selection_terminal
                    if selection_terminal is not None
                    else (
                        "PRE_LIFECYCLE_ATOMIC_TWO_SLOT_READY"
                        if atomic_ready and not provenance_by_mint
                        else "PRE_LIFECYCLE_DISCOVERY_SELECTION_COVERAGE_INSUFFICIENT"
                    )
                )
            )
            return OriginLifecycleResult(
                activation=ActivationResult(
                    terminal_status=terminal,
                    first_terminal_cause=terminal,
                    activated_slots=(),
                    selection_batch_id=None,
                ),
                lifecycle={
                    # Campaign identity only. No factory-run identity on
                    # pre-lifecycle returns (post-rollover-2 identity contract).
                    "campaign_run_id": command.run_id,
                    "run_status": "NOT_STARTED",
                    "stop_reason": terminal,
                    "first_terminal_cause": terminal,
                    "lifecycle_started": False,
                    "stopped_before_lifecycle": True,
                    "pilot_input_readiness": readiness_bundle,
                    "atomic_two_slot_ready": atomic_ready,
                    (
                        "candidate_count"
                        if permanent_mode
                        else "graduated_candidate_count"
                    ): len(graduated_candidates),
                    "holder_eligible_count": holder_eligible,
                    "holder_facts": holder_facts,
                    "eligible_alternates": eligible_alternates,
                    "handoff_readiness": (
                        dict(supply.handoff_readiness) if supply is not None else {}
                    ),
                    "forbidden_deltas": {},
                    "pending_or_running_run_steps": 0,
                    "running_jobs_after_stop": 0,
                    "full_pilot_admission": admission,
                    (
                        "candidate_supply_diagnostics"
                        if permanent_mode
                        else "graduated_supply_diagnostics"
                    ): (
                        dict(supply.diagnostics) if supply is not None else {}
                    ),
                    "pre_lifecycle_admission": pre_lifecycle_admission,
                    "terminal_reporting": {
                        "campaign_source_calls": int(ledger.governed_requests),
                        "campaign_scheduler_calls": 0,
                        "required_token_capacity": 2,
                        "blocked_supply_reason": terminal,
                        "exhaustion_certificate": _project_supply_exhaustion_certificate(supply_diagnostics),
                        "shortage_classification": supply_diagnostics.get(
                            "shortage_classification"
                        ),
                        "candidates": admission_candidates,
                        "selected_identities": [
                            proof.mint for proof in graduated_candidates
                        ],
                        "ordered_selected_slots": [
                            {
                                "slot_ordinal": ordinal,
                                "mint": proof.mint,
                            }
                            for ordinal, proof in enumerate(
                                graduated_candidates, start=1
                            )
                        ],
                        "alternate_identities": [
                            str(item.get("mint") or "")
                            for item in eligible_alternates
                        ],
                        "pre_lifecycle_admission": pre_lifecycle_admission,
                    },
                },
                lifecycle_started=False,
            )

        fixtures = replace(
            fixtures,
            direct_observations=graduated_candidates,
            holder_evidence_eligibility=holder_facts,
            memory_activation_set=memory_activation_set,
        )
        result = self._driver.run(
            command=command,
            fixtures=fixtures,
            backup_path=backup_path,
            source_governor=source_governor,
            central_scheduler=central_scheduler,
            selection_seed=selection_seed,
            proof_mode=not fifteen_minute_only,
            continuous_first_hour=(
                not fifteen_minute_only or standard_four_hour_campaign
            ),
            continuous_four_hour=(
                not fifteen_minute_only or standard_four_hour_campaign
            ),
            four_hour_proof_mode=(
                not fifteen_minute_only and not standard_four_hour_campaign
            ),
            operational_persistent_mode=fifteen_minute_only,
            operational_database_target_binding=(
                operational_database_target_binding
            ),
            disposable_public_composition_proof_binding=(
                disposable_public_composition_proof_binding
            ),
            lifecycle_kwargs=lk,
        )
        if (
            supply is not None
            and bool(supply.diagnostics.get("permanent_availability"))
        ):
            stage_used = dict(
                supply.diagnostics.get("stage_operations_used") or {}
            )
            stage_used["final_refresh_handoff"] = len(
                result.activation.activated_slots
            )
            supply.diagnostics["stage_operations_used"] = stage_used
        try:
            result.lifecycle.setdefault("full_pilot_admission", admission)
            result.lifecycle.setdefault("pilot_input_readiness", readiness_bundle)
            result.lifecycle.setdefault(
                "pre_lifecycle_admission", pre_lifecycle_admission
            )
        except (AttributeError, TypeError):  # pragma: no cover - defensive
            pass
        return result

    @staticmethod
    def _resolve_holder_maturation_observed_at(proof: Any) -> str:
        """Resolve a source-honest ISO observation time for holder maturation.

        SourceSpecificCandidateAdmission uses its validated temporal context.
        Legacy FixtureOriginProof converts its exact positive block_time to UTC
        ISO. Unsupported carriers fail closed before schedule_maturation or
        holder transport. No duck-typed block_time default is used.
        """
        from printer_v1.operator_cli.graduated_supply_front_door import (
            GraduatedSupplyError,
            SourceSpecificCandidateAdmission,
            _epoch_to_utc_iso,
            _require_positive_graduation_epoch,
        )

        if isinstance(proof, SourceSpecificCandidateAdmission):
            return str(proof.temporal_context.admission_observed_at_utc)
        if isinstance(proof, FixtureOriginProof):
            try:
                epoch = _require_positive_graduation_epoch(
                    proof.block_time, mint=str(proof.mint)
                )
            except GraduatedSupplyError as exc:
                message = str(exc)
                code = message.split(":", 1)[0]
                raise LiveOperationalError(code, str(proof.mint)) from exc
            return _epoch_to_utc_iso(epoch)
        raise LiveOperationalError(
            "UNSUPPORTED_CANDIDATE_TEMPORAL_AUTHORITY",
            type(proof).__name__,
        )

    @staticmethod
    def _full_pilot_graduation_diagnostics(
        *,
        graduation_decisions: Sequence[tuple[Any, str]],
        acquisition: Any,
        enrichment: Any,
        fixtures: Any,
        staged_now: int,
        admitted: int | None = None,
        candidate_cap: int | None = None,
    ) -> dict[str, Any]:
        """Honest candidate-admission diagnostics for the report.

        Outer key remains ``full_pilot_admission`` for compatibility. Contents
        distinguish source authority honestly: direct Pump/PumpSwap candidates
        keep graduation temporal evidence; market present-pool candidates report
        retained market observation time with no Pump-origin claim. Age is
        context, never eligibility.
        """
        from printer_v1.discovery.memory_observation_activation import (
            AdmissionAuthority,
        )
        from printer_v1.operator_cli.graduated_supply_front_door import (
            CandidateTemporalAuthority,
            SourceSpecificCandidateAdmission,
        )

        graduation_proofs = dict(getattr(fixtures, "pumpswap_proofs", {}) or {})
        records: list[dict[str, Any]] = []
        state_counts: dict[str, int] = {
            GRADUATION_ELIGIBLE: 0,
            GRADUATION_PENDING_DISCOVERY: 0,
            GRADUATION_AMBIGUOUS_MARKET: 0,
            GRADUATION_FAILED: 0,
            GRADUATION_MARKET_IDENTITY_INVALID: 0,
            "CANDIDATE_PRESENT_POOL_ELIGIBLE": 0,
            "GRADUATION_ELIGIBLE": 0,
        }
        latest_graduated = 0
        non_latest_graduated = 0
        market_present_pool_count = 0
        direct_pump_pumpswap_count = 0
        source_specific_universe = False

        for proof, state in graduation_decisions:
            if isinstance(proof, SourceSpecificCandidateAdmission):
                source_specific_universe = True
                temporal = proof.temporal_context
                authority = proof.admission_authority
                is_market = authority is AdmissionAuthority.MARKET_PRESENT_POOL
                is_direct = authority is AdmissionAuthority.DIRECT_PUMP_PUMPSWAP
                if is_market:
                    market_present_pool_count += 1
                    admission_state = "CANDIDATE_PRESENT_POOL_ELIGIBLE"
                    pump_origin_claimed = False
                    token_age_context = "UNKNOWN_NOT_CLAIMED"
                elif is_direct:
                    direct_pump_pumpswap_count += 1
                    admission_state = "GRADUATION_ELIGIBLE"
                    pump_origin_claimed = True
                    token_age_context = "AGE_IS_CONTEXT_NOT_ELIGIBILITY"
                    latest_graduated += 1
                else:
                    admission_state = state
                    pump_origin_claimed = False
                    token_age_context = "AGE_IS_CONTEXT_NOT_ELIGIBILITY"
                state_counts[admission_state] = (
                    state_counts.get(admission_state, 0) + 1
                )
                records.append(
                    {
                        "mint_identity": proof.mint.lower(),
                        "admission_authority": authority.value,
                        "admission_state": admission_state,
                        "selectable": True,
                        "temporal_authority": temporal.temporal_authority.value,
                        "admission_observed_at_utc": (
                            temporal.admission_observed_at_utc
                        ),
                        "pump_origin_claimed": pump_origin_claimed,
                        "pump_origin_block_time_epoch": (
                            temporal.pump_origin_block_time_epoch
                        ),
                        "market_identity": proof.market_identity,
                        "token_age_context": token_age_context,
                        # Compatibility aliases (source-honest values).
                        "graduation_state": admission_state,
                        "origin_block_time_epoch": (
                            temporal.pump_origin_block_time_epoch
                        ),
                        "post_graduation_age_context": (
                            "UNKNOWN_NOT_CLAIMED"
                            if is_market
                            else "UNKNOWN_NOT_FETCHED_AT_ADMISSION"
                        ),
                    }
                )
                continue

            state_counts[state] = state_counts.get(state, 0) + 1
            graduation = graduation_proofs.get(proof.mint)
            market_identity = (
                f"solana-mainnet:pumpswap:{graduation.pool_address}"
                if state == GRADUATION_ELIGIBLE and graduation is not None
                else None
            )
            if state == GRADUATION_ELIGIBLE:
                # A direct-origin graduated candidate is a newly-graduated latest
                # token; secondary-discovered graduated tokens are non-latest.
                latest_graduated += 1
                direct_pump_pumpswap_count += 1
            epoch = (
                int(proof.block_time)
                if isinstance(proof, FixtureOriginProof)
                else None
            )
            records.append(
                {
                    "mint_identity": proof.mint.lower(),
                    "admission_authority": "DIRECT_PUMP_PUMPSWAP",
                    "admission_state": state,
                    "selectable": state == GRADUATION_ELIGIBLE,
                    "temporal_authority": (
                        CandidateTemporalAuthority.DIRECT_PUMP_GRADUATION_TIME.value
                        if epoch is not None and epoch > 0
                        else None
                    ),
                    "admission_observed_at_utc": (
                        datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()
                        if epoch is not None and epoch > 0
                        else None
                    ),
                    "pump_origin_claimed": True,
                    "pump_origin_block_time_epoch": epoch,
                    "market_identity": market_identity,
                    "token_age_context": "AGE_IS_CONTEXT_NOT_ELIGIBILITY",
                    "graduation_state": state,
                    "origin_block_time_epoch": epoch,
                    "post_graduation_age_context": (
                        "UNKNOWN_NOT_FETCHED_AT_ADMISSION"
                    ),
                }
            )

        graduated_count = (
            state_counts.get(GRADUATION_ELIGIBLE, 0)
            + state_counts.get("GRADUATION_ELIGIBLE", 0)
        )
        candidate_admitted_count = (
            market_present_pool_count + direct_pump_pumpswap_count
            if source_specific_universe
            else graduated_count
        )
        if admitted is not None and not source_specific_universe:
            graduated_admitted = admitted
        elif admitted is not None:
            graduated_admitted = admitted
        else:
            graduated_admitted = candidate_admitted_count
        blocked_channels = {
            "GECKO_TRENDING_TOP": "SKIPPED_BLOCKED_CONTRACT",
            "SOLANA_TRACKER_TRENDING_TOP": "SKIPPED_BLOCKED_CONTRACT",
            "PUMPPORTAL_MIGRATION_FEED": "SKIPPED_BLOCKED_CONTRACT",
        }
        if source_specific_universe:
            return {
                "eligibility_rule": (
                    "SOURCE_SPECIFIC_PRESENT_POOL_OR_DIRECT_PUMP"
                ),
                "candidate_universe": len(graduation_decisions),
                "candidate_admitted_count": (
                    admitted
                    if admitted is not None
                    else candidate_admitted_count
                ),
                "market_present_pool_count": market_present_pool_count,
                "direct_pump_pumpswap_count": direct_pump_pumpswap_count,
                # Compatibility counts: include lawful market nominees.
                "graduated_candidate_count": (
                    admitted
                    if admitted is not None
                    else candidate_admitted_count
                ),
                "graduated_available": candidate_admitted_count,
                "graduated_admitted": graduated_admitted,
                "candidate_cap": candidate_cap,
                "graduation_state_counts": state_counts,
                "latest_vs_non_latest": {
                    "LATEST_GRADUATED": latest_graduated,
                    "NON_LATEST_GRADUATED": non_latest_graduated,
                    "MARKET_PRESENT_POOL": market_present_pool_count,
                },
                "candidates": tuple(records),
                "channel_counts": {
                    "LATEST_PUMPFUN_PENDING_DISCOVERY": len(
                        acquisition.origin_proofs
                    ),
                    "GECKO_TRENDING_ENRICH": len(enrichment.gecko_ops),
                    "TRACKER_ENRICH": len(enrichment.tracker_ops),
                    "DEXSCREENER_ENRICH": len(enrichment.dexscreener_ops),
                    "PUMPSWAP_CONFIRMED": direct_pump_pumpswap_count,
                    "MARKET_PRESENT_POOL": market_present_pool_count,
                },
                "blocked_channels": blocked_channels,
                "staged_pending_discovery_this_cycle": staged_now,
                "note": (
                    "Source-specific admission: direct Pump/PumpSwap candidates "
                    "use exact graduation time; market present-pool nominees use "
                    "retained market observation time. Age is context only. "
                    "Market nominees make no Pump origin, migration, or "
                    "graduation claim."
                ),
            }
        return {
            "eligibility_rule": "GRADUATION_ONLY",
            "candidate_universe": len(graduation_decisions),
            "graduated_candidate_count": graduated_count,
            "graduated_available": graduated_count,
            "graduated_admitted": graduated_admitted,
            "candidate_cap": candidate_cap,
            "graduation_state_counts": state_counts,
            "latest_vs_non_latest": {
                "LATEST_GRADUATED": latest_graduated,
                "NON_LATEST_GRADUATED": non_latest_graduated,
            },
            "candidates": tuple(records),
            "channel_counts": {
                "LATEST_PUMPFUN_PENDING_DISCOVERY": len(acquisition.origin_proofs),
                "GECKO_TRENDING_ENRICH": len(enrichment.gecko_ops),
                "TRACKER_ENRICH": len(enrichment.tracker_ops),
                "DEXSCREENER_ENRICH": len(enrichment.dexscreener_ops),
                "PUMPSWAP_CONFIRMED": graduated_count,
            },
            "blocked_channels": blocked_channels,
            "staged_pending_discovery_this_cycle": staged_now,
            "note": (
                "Graduation is mandatory eligibility; age is context only. Direct "
                "LATEST_PUMPFUN creates are pending discovery (bonding-curve / "
                "unpaired) and are never selectable without confirmed PumpSwap "
                "graduation and an exact post-graduation market identity."
            ),
        }

    def run_readiness_only(
        self,
        *,
        command: AbstractCampaignCommand,
        pump_transport: PumpRpcTransport,
        secondary_transport: SecondaryHttpTransport | None = None,
        source_governor: OwnerPort,
        central_scheduler: OwnerPort,
        selection_seed: str,
        cycle_id: str,
        cycle_cutoff: str,
        evaluated_at: str,
        prior_cursor: FinalizedOriginCursor | None = None,
        timeout_seconds: float = DEFAULT_CALL_TIMEOUT_SECONDS,
        byte_ceiling: int = DEFAULT_RESPONSE_BYTE_CEILING,
        tracker_api_key: str | None = None,
        graduation_proofs: Mapping[str, Any] | None = None,
    ) -> ReadinessResult:
        """Reach live origin, secondary enrichment, merge/gates and a disposable
        dry-run atomic handoff — then stop before any lifecycle window.

        It never starts 15m, 1h, 4h, support-only 5m or promotion work.
        V2-9.7E.41: activation is selection, so it obeys the graduation-only law —
        only mints with confirmed PumpSwap graduation in ``graduation_proofs`` can
        reach the dry-run handoff.
        """
        from printer_v1.operator_cli.durable_external_operation_log import (
            DurablePumpRpcTransport,
        )
        pump_transport = DurablePumpRpcTransport(
            pump_transport, db_path=command.db_path, run_id=command.run_id,
            cycle_id=cycle_id,
        )
        fixtures, acquisition, enrichment = self._build_fixtures(
            pump_transport=pump_transport,
            secondary_transport=secondary_transport,
            source_governor=source_governor,
            central_scheduler=central_scheduler,
            cycle_id=cycle_id,
            cycle_cutoff=cycle_cutoff,
            selection_seed=selection_seed,
            evaluated_at=evaluated_at,
            prior_cursor=prior_cursor,
            timeout_seconds=timeout_seconds,
            byte_ceiling=byte_ceiling,
            tracker_api_key=tracker_api_key,
        )

        fixtures = replace(
            fixtures, pumpswap_proofs=dict(graduation_proofs or {})
        )

        executor = CombinedPumpfunCampaignExecutor(fixtures)
        # Fail closed by default: readiness starts NOT_READY and is only raised to
        # READY at the very end after every fixed gate below is individually
        # proven. Zero, one, failed, partial, mismatched or non-atomic activation
        # can never reach READY.
        blocked_reasons: list[str] = []
        gate_failure_code: str | None = None
        try:
            activation = executor.execute(
                command=command,
                source_governor=source_governor,
                central_scheduler=central_scheduler,
            )
            terminal_status = activation.terminal_status
        except CombinedDiscoveryError as exc:
            terminal_status = "FAILED"
            gate_failure_code = exc.code

        connection = sqlite3.connect(Path(command.db_path))
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        cancelled = 0
        activated: list[dict[str, Any]] = []
        try:
            slots = [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT s.slot_ordinal, s.mint_identity, s.pair_identity,
                           s.token_state
                    FROM printer_memory_factory_campaign_token_slots AS s
                    WHERE s.cycle_id = ? AND s.token_state = 'SELECTED'
                    ORDER BY s.slot_ordinal
                    """,
                    (cycle_id,),
                ).fetchall()
            ]
            activated = slots
            # Disposable dry-run: terminally cancel the executor's own first-15m
            # handoff jobs. No factory lifecycle windows are ever scheduled.
            for slot in slots:
                pool = str(slot["pair_identity"]).rsplit(":", 1)[-1]
                job_name = f"window15m:{slot['mint_identity']}:{pool}"
                placeholders = ",".join("?" * len(ACTIVE_STATUS_VALUES))
                for (job_id,) in connection.execute(
                    f"SELECT id FROM printer_scheduler_jobs "
                    f"WHERE job_name = ? AND status IN ({placeholders})",
                    (job_name, *ACTIVE_STATUS_VALUES),
                ).fetchall():
                    cancel_job(connection, job_id=int(job_id))
                    cancelled += 1
            connection.commit()
            # Zero-source replay: re-read the persisted readiness state; it must
            # be identical and must consume no additional source call.
            replay_slots = [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT s.slot_ordinal, s.mint_identity
                    FROM printer_memory_factory_campaign_token_slots AS s
                    WHERE s.cycle_id = ? AND s.token_state = 'SELECTED'
                    ORDER BY s.slot_ordinal
                    """,
                    (cycle_id,),
                ).fetchall()
            ]
            active_lifecycle_jobs = connection.execute(
                "SELECT COUNT(*) FROM printer_scheduler_jobs "
                "WHERE job_name LIKE 'window15m:%' AND status IN "
                "('PENDING','RUNNING','COOLDOWN')"
            ).fetchone()[0]
        finally:
            connection.close()

        # Fixed readiness gates — every one must hold to become READY.
        origin_mints = {proof.mint for proof in acquisition.origin_proofs}
        activated_mints = [str(slot["mint_identity"]) for slot in activated]
        selected_states = {str(slot["token_state"]) for slot in activated}
        slot_ordinals = sorted(int(slot["slot_ordinal"]) for slot in activated)
        replay_identical = [str(slot["mint_identity"]) for slot in replay_slots] == \
            activated_mints
        gates = {
            "activation_gates_complete": (
                gate_failure_code is None and terminal_status == "COMPLETED"
            ),
            "finalized_origin_accepted": len(acquisition.origin_proofs) >= 2,
            "exactly_two_atomic_slots": (
                len(activated) == 2 and len(set(slot_ordinals)) == 2
            ),
            "all_slots_selected": selected_states == {"SELECTED"} and bool(activated),
            "activated_identities_match_selected": (
                len(activated_mints) == 2
                and set(activated_mints) <= origin_mints
                and len(set(activated_mints)) == 2
            ),
            "disposable_handoff_succeeded": (
                len(activated) == 2 and cancelled == len(activated)
            ),
            "zero_lifecycle_windows_scheduled": int(active_lifecycle_jobs) == 0,
            "replay_identical": replay_identical,
        }
        for gate_name, ok in gates.items():
            if not ok:
                blocked_reasons.append(gate_name)
        if gate_failure_code is not None:
            blocked_reasons.append(f"activation:{gate_failure_code}")

        if not blocked_reasons:
            status = "READY"
        elif gate_failure_code is not None:
            status = f"BLOCKED:{gate_failure_code}"
        elif int(active_lifecycle_jobs) != 0:
            status = "BLOCKED:LIFECYCLE_JOBS_NOT_CLEAN"
        else:
            status = "NOT_READY"

        summary = {
            "contract_version": CONTRACT_VERSION,
            "cycle_id": cycle_id,
            "terminal_status": terminal_status,
            "origins_confirmed": len(acquisition.origin_proofs),
            "pump_pages_used": acquisition.result.pages_used,
            "pump_decode_attempts": acquisition.result.decode_attempts,
            "pump_underlying_rpc": acquisition.result.accounting.underlying_rpc_operations,
            "secondary_requested": enrichment.requested,
            "secondary_failures": enrichment.failures,
            "activated_slot_count": len(activated),
            "cancelled_dry_run_jobs": cancelled,
            "active_lifecycle_jobs_after_cleanup": int(active_lifecycle_jobs),
            "lifecycle_started": False,
            "replayed_slot_count": len(replay_slots),
            "readiness_gates": gates,
            "blocked_reasons": tuple(blocked_reasons),
        }
        return ReadinessResult(
            status=status,
            activated_slots=tuple(activated),
            pump_accounting={
                "governed_requests": dict(
                    acquisition.result.accounting.governed_requests
                ),
                "underlying_rpc": acquisition.result.accounting.underlying_rpc_operations,
            },
            secondary_requested=enrichment.requested,
            secondary_failures=enrichment.failures,
            cancelled_dry_run_jobs=cancelled,
            summary=summary,
            replay_new_source_calls=0,
        )

    def run_snapshot_readiness(
        self,
        *,
        command: AbstractCampaignCommand,
        pump_transport: PumpRpcTransport,
        secondary_transport: SecondaryHttpTransport | None = None,
        source_governor: OwnerPort,
        central_scheduler: OwnerPort,
        selection_seed: str,
        cycle_id: str,
        cycle_cutoff: str,
        evaluated_at: str,
        prior_cursor: FinalizedOriginCursor | None = None,
        timeout_seconds: float = DEFAULT_CALL_TIMEOUT_SECONDS,
        byte_ceiling: int = DEFAULT_RESPONSE_BYTE_CEILING,
        tracker_api_key: str | None = None,
        context_adapter_factories: Mapping[str, Any] | None = None,
        holder_request_pacer: Any | None = None,
        snapshot_request_pacer: Any | None = None,
        geckoterminal_base_adapter_factory: Any | None = None,
        geckoterminal_transports: Mapping[str, Any] | None = None,
        secret_present: bool | None = None,
        preflight_runtime_overrides: Mapping[str, Any] | None = None,
        preflight_budget_overrides: Mapping[str, Any] | None = None,
        cancellation_requested: bool = False,
    ) -> SnapshotReadinessResult:
        """Execute the SNAPSHOT_READINESS boundary and stop.

        Flow: preflight -> live Pump acquisition -> holder eligibility -> exactly
        two complete snapshot bundles or an honest blocker -> report, replay,
        cleanup, stop. It NEVER reaches lifecycle windows, memory, retrieval,
        decision or financial paths: the lifecycle driver is never invoked and no
        memory window or run step is written.

        The single non-renewable authorization is preserved on every fail-closed
        path: preflight and single-use refusal both stop before any transport.
        """
        from printer_v1.operator_cli.bounded_readiness_report import (
            build_bounded_readiness_report,
            canonical_report_bytes,
            canonical_report_sha256,
        )
        from printer_v1.operator_cli.holder_reliability_budget_control import (
            SequentialRequestPacer,
            build_ledger,
        )
        from printer_v1.operator_cli.readiness_source_contract_preflight import (
            READINESS_CANDIDATE_CAP,
            build_readiness_source_contract_preflight,
        )
        from printer_v1.operator_cli.snapshot_readiness_owner import (
            execute_readiness_snapshot_bundle,
        )
        from printer_v1.scheduler.snapshot_maturity import (
            SnapshotMaturityState,
            evaluate_snapshot_maturity,
        )

        def _blocked(
            status: str,
            reasons: Sequence[str],
            *,
            preflight_status: str,
            report: Mapping[str, Any] | None = None,
            report_sha256: str | None = None,
            replay_deterministic: bool = False,
            replay_new_source_calls: int = 0,
            complete: int = 0,
            eligible: int = 0,
            bundles: Sequence[Mapping[str, Any]] = (),
            cancelled: int = 0,
            pump_accounting: Mapping[str, Any] | None = None,
            secondary_requested: int = 0,
            secondary_failures: int = 0,
            extra_summary: Mapping[str, Any] | None = None,
        ) -> SnapshotReadinessResult:
            summary = {
                "contract_version": CONTRACT_VERSION,
                "mode": SNAPSHOT_READINESS,
                "cycle_id": cycle_id,
                "preflight_status": preflight_status,
                "complete_bundle_count": complete,
                "holder_eligible_count": eligible,
                "cancelled_dry_run_jobs": cancelled,
                "lifecycle_started": False,
                "memory_windows": 0,
                "run_steps": 0,
                "blocked_reasons": tuple(reasons),
                **(dict(extra_summary) if extra_summary else {}),
            }
            return SnapshotReadinessResult(
                status=status,
                preflight_status=preflight_status,
                complete_bundle_count=complete,
                holder_eligible_count=eligible,
                snapshot_bundles=tuple(bundles),
                pump_accounting=dict(pump_accounting or {}),
                secondary_requested=secondary_requested,
                secondary_failures=secondary_failures,
                report=dict(report or {}),
                report_sha256=report_sha256,
                replay_deterministic=replay_deterministic,
                replay_new_source_calls=replay_new_source_calls,
                cancelled_dry_run_jobs=cancelled,
                summary=summary,
                blocked_reasons=tuple(reasons),
            )

        # 1. Consolidated offline preflight (zero transport). A blocked preflight
        # (missing secret or contract/budget drift) stops BEFORE any live call and
        # before the single authorization can be consumed.
        preflight = build_readiness_source_contract_preflight(
            secret_present=secret_present,
            runtime_overrides=preflight_runtime_overrides,
            budget_overrides=preflight_budget_overrides,
        )
        if preflight["status"] != "READY":
            return _blocked(
                "BLOCKED_PREFLIGHT",
                [f"preflight:{issue}" for issue in preflight["issues"]],
                preflight_status=preflight["status"],
            )

        # 2. Single-use refusal: a committed operation ledger for this identity is
        # the authorization marker. A second execution against the same run/cycle
        # is refused before any transport (no rerun, retry or restart).
        marker_connection = sqlite3.connect(Path(command.db_path))
        try:
            already = marker_connection.execute(
                "SELECT COUNT(*) FROM printer_holder_campaign_operation_ledgers "
                "WHERE run_id=? AND cycle_id=?",
                (command.run_id, cycle_id),
            ).fetchone()[0]
        finally:
            marker_connection.close()
        if int(already):
            return _blocked(
                "REFUSED_SECOND_EXECUTION",
                ["snapshot_readiness_already_executed"],
                preflight_status=preflight["status"],
            )

        # 3. Live Pump acquisition + bounded governed secondary enrichment. A
        # source/transport fault fails closed here (raises) with no retry.
        from printer_v1.operator_cli.durable_external_operation_log import (
            DurablePumpRpcTransport,
        )
        durable_pump = DurablePumpRpcTransport(
            pump_transport, db_path=command.db_path, run_id=command.run_id,
            cycle_id=cycle_id,
        )
        _fixtures, acquisition, enrichment = self._build_fixtures(
            pump_transport=durable_pump,
            secondary_transport=secondary_transport,
            source_governor=source_governor,
            central_scheduler=central_scheduler,
            cycle_id=cycle_id,
            cycle_cutoff=cycle_cutoff,
            selection_seed=selection_seed,
            evaluated_at=evaluated_at,
            prior_cursor=prior_cursor,
            timeout_seconds=timeout_seconds,
            byte_ceiling=byte_ceiling,
            tracker_api_key=tracker_api_key,
        )
        pump_accounting = {
            "governed_requests": dict(
                acquisition.result.accounting.governed_requests
            ),
            "underlying_rpc": acquisition.result.accounting.underlying_rpc_operations,
        }

        # 4. Operation ledger + bounded holder candidates (candidate cap derived).
        evaluated = datetime.fromisoformat(evaluated_at.replace("Z", "+00:00"))
        deadline = evaluated + timedelta(seconds=command.ceilings.duration_seconds)
        ledger = build_ledger(
            pump_operations=acquisition.result.accounting.underlying_rpc_operations,
            additional_governed_operations=enrichment.requested,
            deadline_at=deadline,
        )
        bounded_candidates = _finalized_holder_candidates(
            acquisition.origin_proofs,
            limit=min(
                HOLDER_ELIGIBILITY_CANDIDATE_MAX,
                READINESS_CANDIDATE_CAP,
                ledger.candidate_cap(),
            ),
        )
        maturity_decisions = tuple(
            (
                proof,
                evaluate_snapshot_maturity(
                    pump_block_time=proof.block_time,
                    evaluated_at=evaluated,
                    cancelled=cancellation_requested,
                ),
            )
            for proof in bounded_candidates
        )
        mature_candidates = tuple(
            proof
            for proof, decision in maturity_decisions
            if decision.state is SnapshotMaturityState.DUE
        )
        maturity_records = tuple(
            {
                "mint_identity": proof.mint.lower(),
                "state": decision.state.value,
                "origin_block_time_utc": (
                    decision.origin_block_time_utc.isoformat()
                    if decision.origin_block_time_utc is not None else None
                ),
                "due_at_utc": (
                    decision.due_at_utc.isoformat()
                    if decision.due_at_utc is not None else None
                ),
                "evaluated_at_utc": decision.evaluated_at_utc.isoformat(),
            }
            for proof, decision in maturity_decisions
        )
        maturity_state_counts = {
            state.value: sum(
                decision.state is state for _proof, decision in maturity_decisions
            )
            for state in SnapshotMaturityState
        }

        base_factory = (
            geckoterminal_base_adapter_factory
            or build_live_geckoterminal_base_adapter_factory(
                timeout_seconds=timeout_seconds
            )
        )
        snapshot_pacer = snapshot_request_pacer or SequentialRequestPacer()

        bundle_results: list[dict[str, Any]] = []
        complete_bundles = 0
        holder_eligible = 0
        connection = sqlite3.connect(Path(command.db_path))
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            # 5. Holder eligibility (shared committed funnel). Snapshot maturity
            # is Scheduler-owned and precedes holder I/O. A pool smaller than
            # the two-bundle goal persists the ledger with zero holder calls.
            holder_result = self._evaluate_holder_eligibility(
                connection,
                command=command,
                cycle_id=cycle_id,
                bounded_candidates=(
                    mature_candidates if len(mature_candidates) >= 2 else ()
                ),
                evaluated=evaluated,
                deadline=deadline,
                ledger=ledger,
                timeout_seconds=timeout_seconds,
                context_factories=context_adapter_factories,
                request_pacer=holder_request_pacer,
            )
            holder_facts = dict(holder_result.holder_facts)
            ledger = holder_result.ledger
            # V2-9.8B: readiness inspects the COMPLETE holder result, not only
            # holder facts. Incomplete holder accounting fails closed before any
            # readiness snapshot bundle is attempted.
            holder_accounting_blocker = bool(holder_result.accounting_blocker)
            holder_context = holder_result.as_holder_context_diagnostics()
            eligible_candidates = [
                proof for proof in bounded_candidates
                if bool(holder_facts.get(proof.mint.lower(), {}).get("eligible"))
            ]
            holder_eligible = len(eligible_candidates)
            snapshot_candidates = (
                [] if holder_accounting_blocker else eligible_candidates
            )

            # 6. Exactly two complete snapshot bundles or an honest blocker. The
            # bundle is attempted only for holder-eligible candidates; it stops
            # after two complete bundles.
            for ordinal, proof in enumerate(snapshot_candidates, start=1):
                if complete_bundles >= 2:
                    break
                step = {
                    "run_id": command.run_id,
                    "step_key": f"readiness_snapshot_{ordinal}",
                    "token_mint": proof.mint,
                    "pair_address": proof.bonding_curve,
                    "tracking_lane": "TRACK_FAST",
                }
                bundle = execute_readiness_snapshot_bundle(
                    connection,
                    step,
                    geckoterminal_base_adapter_factory=base_factory,
                    timeout_seconds=timeout_seconds,
                    geckoterminal_transports=geckoterminal_transports,
                    evaluated_at=evaluated,
                    request_pacer=snapshot_pacer,
                )
                redacted = {
                    "ok": bool(bundle.get("ok")),
                    "operations_attempted": int(bundle.get("operations_attempted") or 0),
                    "blocked_reasons": tuple(bundle.get("blocked_reasons") or ()),
                    "snapshot_id": bundle.get("snapshot_id"),
                }
                bundle_results.append(redacted)
                if redacted["ok"]:
                    complete_bundles += 1
            connection.commit()

            # 7. Disposable cleanup: terminally cancel any first-15m handoff jobs
            # that any owner may have staged. In snapshot-readiness none should
            # exist because selection/activation is never run.
            cancelled = 0
            for (job_id,) in connection.execute(
                "SELECT id FROM printer_scheduler_jobs "
                "WHERE job_name LIKE 'window15m:%' AND status IN "
                "('PENDING','RUNNING','COOLDOWN')"
            ).fetchall():
                cancel_job(connection, job_id=int(job_id))
                cancelled += 1
            connection.commit()

            active_lifecycle_jobs = int(connection.execute(
                "SELECT COUNT(*) FROM printer_scheduler_jobs "
                "WHERE job_name LIKE 'window15m:%' AND status IN "
                "('PENDING','RUNNING','COOLDOWN')"
            ).fetchone()[0])
            memory_windows = int(connection.execute(
                "SELECT COUNT(*) FROM printer_memory_windows"
            ).fetchone()[0])
            run_steps = int(connection.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_run_steps"
            ).fetchone()[0])
        finally:
            connection.close()

        # 8. Deterministic DB-only report + zero-source replay (report built
        # twice; canonical bytes must be identical and consume no source call).
        report_a = build_bounded_readiness_report(
            command.db_path, run_id=command.run_id, cycle_id=cycle_id
        )
        report_b = build_bounded_readiness_report(
            command.db_path, run_id=command.run_id, cycle_id=cycle_id
        )
        replay_deterministic = (
            canonical_report_bytes(report_a) == canonical_report_bytes(report_b)
        )
        replay_new_source_calls = int(report_a.get("source_requests_made_by_replay", 0))
        report_sha256 = canonical_report_sha256(report_a)
        forbidden = report_a.get("forbidden_capability_counts", {})
        readiness_snapshots = report_a.get("readiness_snapshots", [])

        # 9. Fixed readiness gates — every one must hold to become READY.
        gates = {
            "preflight_ready": preflight["status"] == "READY",
            "holder_accounting_complete": not holder_accounting_blocker,
            "two_mature_candidates": len(mature_candidates) >= 2,
            "exactly_two_complete_bundles": complete_bundles == 2,
            "two_holder_eligible_candidates": holder_eligible >= 2,
            "two_persisted_readiness_snapshots": len(readiness_snapshots) == 2,
            "no_lifecycle_windows": active_lifecycle_jobs == 0,
            "no_memory_windows": memory_windows == 0,
            "no_run_steps": run_steps == 0,
            "replay_deterministic": replay_deterministic,
            "replay_zero_source_calls": replay_new_source_calls == 0,
            "integrity_ok": report_a.get("integrity") == "ok",
            "zero_foreign_key_violations": int(report_a.get("foreign_key_violations", 1)) == 0,
            "zero_forbidden_capability_rows": all(
                int(value) == 0 for value in forbidden.values()
            ),
        }
        blocked_reasons = [name for name, ok in gates.items() if not ok]

        if not blocked_reasons:
            status = "READY"
        elif holder_accounting_blocker:
            # Typed holder accounting terminal. It dominates other blockers:
            # the holder request/transport accounting itself is not trustworthy.
            status = "BLOCKED_HOLDER_ACCOUNTING"
        elif cancellation_requested:
            status = "CANCELLED"
        elif (
            len(mature_candidates) < 2
            and len(mature_candidates) < len(bounded_candidates)
        ):
            status = "BLOCKED_INSUFFICIENT_MATURE_POOL"
        elif holder_eligible < 2:
            status = "BLOCKED_INSUFFICIENT_ELIGIBLE_POOL"
        elif complete_bundles < 2:
            status = "BLOCKED_SNAPSHOT_READINESS"
        else:
            status = "NOT_READY"

        summary = {
            "contract_version": CONTRACT_VERSION,
            "mode": SNAPSHOT_READINESS,
            "cycle_id": cycle_id,
            "preflight_status": preflight["status"],
            "origins_confirmed": len(acquisition.origin_proofs),
            "pump_underlying_rpc": acquisition.result.accounting.underlying_rpc_operations,
            "secondary_requested": enrichment.requested,
            "secondary_failures": enrichment.failures,
            "snapshot_maturity": {
                "threshold_seconds": 900,
                "mature_candidate_count": len(mature_candidates),
                "state_counts": maturity_state_counts,
                "candidates": maturity_records,
            },
            "holder_eligible_count": holder_eligible,
            "holder_context": holder_context,
            "holder_accounting_blocker": holder_accounting_blocker,
            "holder_accounting_blocker_reason": holder_context.get(
                "accounting_blocker_reason"
            ),
            "holder_source_request_ids": list(
                holder_context.get("source_request_ids") or ()
            ),
            "holder_source_request_coverage": [
                dict(entry)
                for entry in (holder_context.get("source_request_coverage") or ())
            ],
            "holder_governed_request_count": int(
                holder_context.get("governed_request_count") or 0
            ),
            "holder_measured_transport_count": int(
                holder_context.get("measured_transport_count") or 0
            ),
            "complete_bundle_count": complete_bundles,
            "persisted_readiness_snapshots": len(readiness_snapshots),
            "cancelled_dry_run_jobs": cancelled,
            "active_lifecycle_jobs_after_cleanup": active_lifecycle_jobs,
            "memory_windows": memory_windows,
            "run_steps": run_steps,
            "lifecycle_started": False,
            "report_sha256": report_sha256,
            "replay_deterministic": replay_deterministic,
            "replay_new_source_calls": replay_new_source_calls,
            "budget": {
                "operation_ceiling": ledger.operation_ceiling,
                "candidate_cap": READINESS_CANDIDATE_CAP,
                "reserved_snapshot_operations": ledger.reserved_snapshot_operations,
                "reserved_snapshot_completion_operations": (
                    ledger.reserved_snapshot_completion_operations
                ),
                "charged_operations": ledger.charged_operations,
            },
            "readiness_gates": gates,
            "blocked_reasons": tuple(blocked_reasons),
        }
        return SnapshotReadinessResult(
            status=status,
            preflight_status=preflight["status"],
            complete_bundle_count=complete_bundles,
            holder_eligible_count=holder_eligible,
            snapshot_bundles=tuple(bundle_results),
            pump_accounting=pump_accounting,
            secondary_requested=enrichment.requested,
            secondary_failures=enrichment.failures,
            report=report_a,
            report_sha256=report_sha256,
            replay_deterministic=replay_deterministic,
            replay_new_source_calls=replay_new_source_calls,
            cancelled_dry_run_jobs=cancelled,
            summary=summary,
            blocked_reasons=tuple(blocked_reasons),
            holder_context=holder_context,
        )
