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
import sqlite3
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from printer_v1.discovery.combined_executor import (
    CombinedDiscoveryError,
    CombinedDiscoveryFixtures,
    CombinedPumpfunCampaignExecutor,
    FixtureOriginProof,
    FixtureSourceFact,
)
from printer_v1.operator_cli.abstract_campaign_command import (
    AbstractCampaignCommand,
    CENTRAL_SCHEDULER_OWNER,
    OwnerPort,
    SOURCE_GOVERNOR_OWNER,
)
from printer_v1.operator_cli.origin_lifecycle_campaign import (
    OriginToLifecycleCampaignDriver,
    materialize_origin_activated_batch,
)
from printer_v1.scheduler.scheduler import ACTIVE_STATUS_VALUES, cancel_job
from printer_v1.scheduler.support_only_5m_capture import SupportTriggerFamily
from printer_v1.sources.pumpfun_origin import (
    CREATE_INDEX_PAGE_SIZE,
    PUMP_CREATE_INDEX_ADDRESS,
    SIGNATURE_PAGE_REQUEST,
    TRANSACTION_REQUEST,
    AcquisitionCycleResult,
    FinalizedOriginCursor,
    FixtureOperation,
    PumpContractError,
    SignatureReference,
    _Accounting,
    run_acquisition_from_source,
)
from printer_v1.sources import secondary_discovery as _sd


CONTRACT_VERSION = "V2-9.7E.11"

# Frozen E.11 per-call transport ceilings (readiness boundary).
DEFAULT_CALL_TIMEOUT_SECONDS = 30.0
DEFAULT_RESPONSE_BYTE_CEILING = 1_572_864  # 1.5 MiB
READINESS_STORAGE_BYTE_CEILING = 8 * 1024 * 1024
READINESS_DURATION_CEILING_SECONDS = 360.0

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
            source_name=_sd.DEXSCREENER_SOURCE_NAME
            if hasattr(_sd, "DEXSCREENER_SOURCE_NAME")
            else "dexscreener",
            request_kind="dexscreener_fresh_profiles",
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


def _finalized_holder_candidates(proofs: Any, *, limit: int) -> tuple[Any, ...]:
    """Apply structural, zero-source finalized-proof gates before holder I/O."""
    eligible = []
    seen: set[tuple[str, str]] = set()
    for proof in proofs:
        identity = (str(proof.mint).lower(), str(proof.bonding_curve))
        if (
            not bool(proof.confirmed)
            or not identity[0]
            or not identity[1]
            or not str(proof.signature)
            or int(proof.slot) < 0
            or identity in seen
        ):
            continue
        seen.add(identity)
        eligible.append(proof)
    return tuple(sorted(
        eligible,
        key=lambda proof: (
            proof.mint.lower(), proof.bonding_curve, proof.signature, int(proof.slot),
        ),
    )[:limit])


def _holder_eligibility_from_bundle(
    bundle: Mapping[str, Any], *, token_mint: str
) -> dict[str, Any]:
    executions = bundle.get("executions", {})
    goplus = _holder_execution_fact(
        executions.get("safety"), token_mint=token_mint, source_name="goplus"
    )
    if goplus["eligible"]:
        return goplus
    holder = _holder_execution_fact(
        executions.get("holder"),
        token_mint=token_mint,
        source_name="solana_rpc",
    )
    if holder["eligible"]:
        return holder
    # Preserve the most specific attempted on-chain reason when present.
    return holder if executions.get("holder") is not None else goplus


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


class AuthoritativeLiveOperationalCampaignOwner:
    """Sole internal live origin→lifecycle composition entry point (DI-only)."""

    def __init__(
        self, *, driver: OriginToLifecycleCampaignDriver | None = None
    ) -> None:
        self._driver = driver or OriginToLifecycleCampaignDriver()

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
    ) -> tuple[CombinedDiscoveryFixtures, LivePumpAcquisition, LiveSecondaryEnrichment]:
        pump = LivePumpOriginAdapter(
            pump_transport, timeout_seconds=timeout_seconds, byte_ceiling=byte_ceiling
        )
        acquisition = pump.acquire(
            source_governor=source_governor,
            central_scheduler=central_scheduler,
            prior_cursor=prior_cursor,
        )
        enrichment = LiveSecondaryEnrichment()
        if secondary_transport is not None:
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
        fixtures = CombinedDiscoveryFixtures(
            cycle_id=cycle_id,
            cycle_cutoff=cycle_cutoff,
            campaign_selection_seed=selection_seed,
            provider_contract_versions={"direct": CONTRACT_VERSION},
            git_provenance_identity=f"live-operational:{CONTRACT_VERSION}",
            evaluated_at=evaluated_at,
            direct_observations=acquisition.origin_proofs,
            gecko_ops=enrichment.gecko_ops,
            tracker_ops=enrichment.tracker_ops,
            dexscreener_ops=enrichment.dexscreener_ops,
        )
        return fixtures, acquisition, enrichment

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
    ) -> Any:
        """Run one authoritative live two-token operational-natural campaign."""
        lk = dict(lifecycle_kwargs or {})
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
        lk["operational_natural_disposition"] = True

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
        from printer_v1.operator_cli.holder_reliability_budget_control import (
            build_ledger,
            complete_maturation,
            persist_bundle_attempts,
            persist_ledger,
            reuse_holder_fact,
            schedule_maturation,
            SequentialRequestPacer,
        )
        evaluated = datetime.fromisoformat(evaluated_at.replace("Z", "+00:00"))
        deadline = evaluated + timedelta(seconds=command.ceilings.duration_seconds)
        ledger = build_ledger(
            pump_operations=acquisition.result.accounting.underlying_rpc_operations,
            additional_governed_operations=enrichment.requested,
            deadline_at=deadline,
        )
        bounded_candidates = _finalized_holder_candidates(
            acquisition.origin_proofs,
            limit=min(HOLDER_ELIGIBILITY_CANDIDATE_MAX, ledger.candidate_cap()),
        )
        holder_facts: dict[str, Mapping[str, Any]] = {}
        connection = sqlite3.connect(Path(command.db_path))
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            from printer_v1.operator_cli.one_command_15m_factory import (
                _collect_preclose_context,
            )
            context_factories = lk.get("context_adapter_factories")
            request_pacer = lk.pop("holder_request_pacer", None) or SequentialRequestPacer()
            persist_ledger(
                connection, run_id=command.run_id, cycle_id=cycle_id,
                ledger=ledger, now=evaluated.isoformat(),
            )
            for ordinal, proof in enumerate(bounded_candidates, start=1):
                ledger.admit_candidate(now=evaluated)
                maturation = schedule_maturation(
                    connection, run_id=command.run_id, cycle_id=cycle_id,
                    mint=proof.mint, observed_at=str(proof.block_time),
                    now=evaluated.isoformat(), deadline_at=deadline.isoformat(),
                )
                if maturation["work_state"] != "DUE":
                    holder_facts[proof.mint.lower()] = {
                        "eligible": False,
                        "reason": f"HOLDER_MATURATION_{maturation['work_state']}",
                        "source_name": None,
                    }
                    continue
                try:
                    reused_fact = reuse_holder_fact(
                        connection, run_id=command.run_id, cycle_id=cycle_id,
                        mint=proof.mint, evaluated_at=evaluated.isoformat(),
                    )
                    if reused_fact is not None:
                        holder_facts[proof.mint.lower()] = reused_fact
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
                        if sum(bool(fact.get("eligible")) for fact in holder_facts.values()) == 2:
                            break
                        continue
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
                        request_pacer=request_pacer,
                    )
                    holder_facts[proof.mint.lower()] = (
                        _holder_eligibility_from_bundle(
                            bundle, token_mint=proof.mint
                        )
                    )
                    governed_used, transports_used = persist_bundle_attempts(
                        connection, run_id=command.run_id, cycle_id=cycle_id,
                        mint=proof.mint, executions=bundle.get("executions", {}),
                        created_at=evaluated.isoformat(),
                    )
                    ledger = replace(
                        ledger,
                        governed_requests=ledger.governed_requests + governed_used,
                        underlying_transport_operations=(
                            ledger.underlying_transport_operations + transports_used
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
                    if sum(bool(fact.get("eligible")) for fact in holder_facts.values()) == 2:
                        break
                except Exception as exc:
                    complete_maturation(
                        connection, work_id=str(maturation["work_id"]),
                        cause=f"EVIDENCE_COLLECTION_FAILED:{type(exc).__name__}",
                        now=evaluated.isoformat(),
                    )
                    holder_facts[proof.mint.lower()] = {
                        "eligible": False,
                        "reason": f"HOLDER_EVIDENCE_COLLECTION_FAILED:{type(exc).__name__}",
                        "source_name": None,
                    }
            connection.commit()
        finally:
            connection.close()
        fixtures = replace(
            fixtures,
            direct_observations=bounded_candidates,
            holder_evidence_eligibility=holder_facts,
        )
        return self._driver.run(
            command=command,
            fixtures=fixtures,
            backup_path=backup_path,
            source_governor=source_governor,
            central_scheduler=central_scheduler,
            selection_seed=selection_seed,
            proof_mode=True,
            continuous_first_hour=True,
            continuous_four_hour=True,
            four_hour_proof_mode=True,
            lifecycle_kwargs=lk,
        )

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
    ) -> ReadinessResult:
        """Reach live origin, secondary enrichment, merge/gates and a disposable
        dry-run atomic handoff — then stop before any lifecycle window.

        It never starts 15m, 1h, 4h, support-only 5m or promotion work.
        """
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
