"""Finite, restart-safe FORWARD cursor recovery for V2-9.8B.

This module is recovery-only.  It never nominates or enriches candidates during
an incomplete scan and never changes the normal N2/N7 source budgets.  Every
external request remains Central-Scheduler-led and Source-Governed through the
existing candidate-acquisition integration persistence owners.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import json
from pathlib import Path
from types import MappingProxyType
import time
from typing import Any, Mapping, Sequence

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.discovery.candidate_acquisition import (
    build_acquisition_plan,
    run_candidate_acquisition,
)
from printer_v1.operator_cli.candidate_acquisition_integration import (
    ACTIVE_CAPACITY,
    LEASE_SECONDS,
    MODE_N2,
    AcquisitionSourceOperation,
    CandidateAcquisitionIntegrationError,
    CursorHead,
    CursorNamespace,
    RELIABILITY_STATUS,
    _acquire_lease,
    _canonical,
    _connect,
    _counts,
    _load_exact_cursor_heads,
    _parse,
    _persist_integration_report,
    _persist_work,
    _preflight_hash,
    _release_lease,
    _sha,
    _source_status,
    _terminalize_unleased_integration,
    renew_candidate_acquisition_lease,
    replay_candidate_acquisition_integration_report,
)
from printer_v1.operator_cli.live_candidate_acquisition_transport import (
    CURSOR_DECODER_VERSION,
    CURSOR_NETWORK,
    LIVE_TAIL_DIRECTION,
    CandidateAcquisitionOneShotTransport,
    LiveAcquisitionConfiguration,
    LiveAcquisitionTransportError,
    TransportResponse,
    UrllibCandidateAcquisitionOneShotTransport,
    load_live_acquisition_configuration,
)
from printer_v1.scheduler.contracts import JobKind, LockResult
from printer_v1.scheduler.scheduler import (
    claim_due_job,
    complete_job,
    enqueue_job,
    fail_job,
)
from printer_v1.sources.budget_accounting import count_recent_source_requests
from printer_v1.sources.contracts import (
    NormalizedSourceResult,
    SourceAdapterContext,
    SourceRequest,
    build_governed_source_request,
)
from printer_v1.sources.governed_execution import execute_source_request_with_governor
from printer_v1.sources.pump_contracts import OFFICIAL_REPOSITORY_COMMIT
from printer_v1.sources.pumpfun_direct import PUMP_PROGRAM_ID
from printer_v1.sources.pumpfun_origin import PUMP_CREATE_INDEX_ADDRESS


CLI_MODE_CURSOR_RECOVERY_N2 = "cursor-recovery-n2"
RECOVERY_CONTRACT_VERSION = "cursor-continuity-recovery-v1"
RECOVERY_PAGES_PER_NAMESPACE = 4
RECOVERY_SIGNATURES_PER_PAGE = 250
RECOVERY_GOVERNED_REQUEST_CEILING = 8
RECOVERY_TRANSPORT_OPERATION_CEILING = 10
RECOVERY_DURATION_SECONDS = 120
RECOVERY_MAX_EXECUTIONS = 12

RECOVERY_INCOMPLETE = "CURSOR_RECOVERY_INCOMPLETE_BOUNDED_BUDGET"
RECOVERY_COMPLETE = "CURSOR_RECOVERY_EXACT_BOUNDARY_REACHED"
RECOVERY_NO_NEW = "CURSOR_RECOVERY_NO_NEW_SIGNATURES"
RECOVERY_PRIOR_UNREACHABLE = "CURSOR_PRIOR_BOUNDARY_UNREACHABLE"
RECOVERY_PROVIDER_UNAVAILABLE = "CURSOR_RECOVERY_PROVIDER_UNAVAILABLE"
RECOVERY_MALFORMED = "CURSOR_RECOVERY_MALFORMED_PAGE"
RECOVERY_DUPLICATE = "CURSOR_RECOVERY_DUPLICATE_PAGE"
RECOVERY_NAMESPACE_MISMATCH = "CURSOR_RECOVERY_NAMESPACE_MISMATCH"
RECOVERY_SKIP = "CURSOR_RECOVERY_SKIP_ATTEMPT"
RECOVERY_REWIND = "CURSOR_RECOVERY_REWIND_ATTEMPT"
RECOVERY_BOUND_EXHAUSTED = "CURSOR_RECOVERY_LANE_BOUND_EXHAUSTED"


def _namespace_dict(namespace: CursorNamespace) -> dict[str, str]:
    return {
        "network": namespace[0],
        "indexed_address": namespace[1],
        "contract_pin": namespace[2],
        "decoder_version": namespace[3],
        "direction": namespace[4],
    }


def _recovery_identity(
    namespaces: Sequence[CursorNamespace],
    heads: Mapping[CursorNamespace, CursorHead | None],
) -> str:
    payload = []
    for namespace in sorted(namespaces):
        head = heads.get(namespace)
        payload.append({
            **_namespace_dict(namespace),
            "boundary_slot": None if head is None else head["boundary_slot"],
            "boundary_signature": None if head is None else head["boundary_signature"],
            "cursor_version": None if head is None else head["cursor_version"],
        })
    return "carec-" + _sha({
        "contract": RECOVERY_CONTRACT_VERSION,
        "heads": payload,
    })[:32]


def _page_hash(payload: Mapping[str, Any]) -> str:
    fields = (
        "network", "indexed_address", "contract_pin", "decoder_version",
        "direction", "range_mode", "recovery_contract_version", "recovery_id",
        "authoritative_start_slot", "authoritative_start_signature",
        "authoritative_cursor_version", "recovery_tip_slot",
        "recovery_tip_signature", "boundary_reached", "no_new_signatures",
        "terminal_category", "recovery_page_ordinal",
        "input_continuation_slot", "input_continuation_signature",
        "output_continuation_slot", "output_continuation_signature",
        "page_rows", "page_committed",
    )
    material = {key: payload.get(key) for key in fields}
    return _sha(material)


def _initial_state(
    namespace: CursorNamespace,
    head: CursorHead | None,
    *,
    recovery_id: str,
) -> dict[str, Any]:
    return {
        **_namespace_dict(namespace),
        "range_mode": "LIVE_TAIL_RECOVERY",
        "recovery_contract_version": RECOVERY_CONTRACT_VERSION,
        "recovery_id": recovery_id,
        "authoritative_start_slot": None if head is None else int(head["boundary_slot"]),
        "authoritative_start_signature": (
            None if head is None else str(head["boundary_signature"])
        ),
        "authoritative_cursor_version": (
            None if head is None else int(head["cursor_version"])
        ),
        "recovery_tip_slot": None,
        "recovery_tip_signature": None,
        "continuation_slot": None,
        "continuation_signature": None,
        "boundary_reached": False,
        "no_new_signatures": False,
        "recovery_page_ordinal": 0,
        "seen_signatures": [],
        "terminal_category": RECOVERY_INCOMPLETE,
    }


def _validate_page_artifact(
    state: dict[str, Any], artifact: Mapping[str, Any]
) -> None:
    if artifact.get("recovery_id") != state["recovery_id"]:
        raise CandidateAcquisitionIntegrationError(RECOVERY_NAMESPACE_MISMATCH)
    for key in ("network", "indexed_address", "contract_pin", "decoder_version", "direction"):
        if artifact.get(key) != state[key]:
            raise CandidateAcquisitionIntegrationError(RECOVERY_NAMESPACE_MISMATCH, key)
    if artifact.get("direction") != "FORWARD":
        raise CandidateAcquisitionIntegrationError(RECOVERY_NAMESPACE_MISMATCH, "direction")
    if artifact.get("authoritative_start_slot") != state["authoritative_start_slot"] or (
        artifact.get("authoritative_start_signature")
        != state["authoritative_start_signature"]
    ) or artifact.get("authoritative_cursor_version") != state["authoritative_cursor_version"]:
        raise CandidateAcquisitionIntegrationError(RECOVERY_NAMESPACE_MISMATCH, "head")
    if artifact.get("input_continuation_signature") != state["continuation_signature"]:
        raise CandidateAcquisitionIntegrationError(RECOVERY_SKIP, "continuation_signature")
    if artifact.get("input_continuation_slot") != state["continuation_slot"]:
        raise CandidateAcquisitionIntegrationError(RECOVERY_SKIP, "continuation_slot")
    if _page_hash(artifact) != artifact.get("page_hash"):
        raise CandidateAcquisitionIntegrationError(RECOVERY_MALFORMED, "page_hash")
    rows = artifact.get("page_rows")
    if not isinstance(rows, list):
        raise CandidateAcquisitionIntegrationError(RECOVERY_MALFORMED, "page_rows")
    known = set(str(item) for item in state["seen_signatures"])
    previous_slot = state["continuation_slot"]
    for row in rows:
        if not isinstance(row, Mapping):
            raise CandidateAcquisitionIntegrationError(RECOVERY_MALFORMED, "row")
        signature, slot = row.get("signature"), row.get("slot")
        if not isinstance(signature, str) or not signature or type(slot) is not int or slot < 0:
            raise CandidateAcquisitionIntegrationError(RECOVERY_MALFORMED, "identity")
        if signature in known:
            raise CandidateAcquisitionIntegrationError(RECOVERY_DUPLICATE, signature)
        if previous_slot is not None and slot > int(previous_slot):
            raise CandidateAcquisitionIntegrationError(RECOVERY_REWIND, signature)
        known.add(signature)
        previous_slot = slot
    if rows:
        if artifact.get("output_continuation_signature") != rows[-1]["signature"] or (
            artifact.get("output_continuation_slot") != rows[-1]["slot"]
        ):
            raise CandidateAcquisitionIntegrationError(RECOVERY_SKIP, "page_end")
    state["seen_signatures"] = sorted(known)
    state["continuation_signature"] = artifact.get("output_continuation_signature")
    state["continuation_slot"] = artifact.get("output_continuation_slot")
    state["recovery_tip_signature"] = artifact.get("recovery_tip_signature")
    state["recovery_tip_slot"] = artifact.get("recovery_tip_slot")
    state["recovery_page_ordinal"] = int(artifact.get("recovery_page_ordinal") or 0)
    state["boundary_reached"] = bool(artifact.get("boundary_reached"))
    state["no_new_signatures"] = bool(artifact.get("no_new_signatures"))
    state["terminal_category"] = str(artifact.get("terminal_category") or RECOVERY_INCOMPLETE)


def _load_recovery_chain(
    db_path: str | Path,
    *,
    namespaces: Sequence[CursorNamespace],
    heads: Mapping[CursorNamespace, CursorHead | None],
    recovery_id: str,
) -> tuple[dict[CursorNamespace, dict[str, Any]], int]:
    states = {
        namespace: _initial_state(namespace, heads.get(namespace), recovery_id=recovery_id)
        for namespace in namespaces
    }
    connection = _connect(db_path)
    try:
        execution_count = int(connection.execute(
            """SELECT COUNT(*) FROM printer_candidate_acquisition_integrations
               WHERE json_extract(policy_json,'$.cursor_recovery_only')=1
                 AND json_extract(policy_json,'$.recovery_id')=?""",
            (recovery_id,),
        ).fetchone()[0])
        rows = connection.execute(
            """SELECT w.cursor_range_json
               FROM printer_candidate_acquisition_work w
               JOIN printer_candidate_acquisition_integrations i
                 ON i.integration_id=w.integration_id
               WHERE json_extract(i.policy_json,'$.cursor_recovery_only')=1
                 AND json_extract(i.policy_json,'$.recovery_id')=?
                 AND w.cursor_range_json IS NOT NULL
               ORDER BY i.started_at,i.integration_id,w.work_ordinal""",
            (recovery_id,),
        ).fetchall()
    finally:
        connection.close()
    for row in rows:
        artifact = json.loads(str(row["cursor_range_json"]))
        if not bool(artifact.get("page_committed")):
            continue
        namespace = tuple(str(artifact.get(key) or "") for key in (
            "network", "indexed_address", "contract_pin", "decoder_version", "direction",
        ))
        if namespace not in states:
            raise CandidateAcquisitionIntegrationError(RECOVERY_NAMESPACE_MISMATCH)
        _validate_page_artifact(states[namespace], artifact)
    return states, execution_count


class _RecoveryAdapter:
    def __init__(self, request_kind: str, execute: Any) -> None:
        self.source_name = "solana_rpc"
        self.request_kind = request_kind
        self._execute = execute

    def execute(self, context: SourceAdapterContext) -> NormalizedSourceResult:
        if not context.governor_approved or context.request.source_name != "solana_rpc" or (
            context.request.request_kind != self.request_kind
        ):
            raise PermissionError("CURSOR_RECOVERY_GOVERNOR_CONTEXT_REQUIRED")
        return self._execute()


@dataclass
class CursorRecoveryTransportOwner:
    configuration: LiveAcquisitionConfiguration
    transport: CandidateAcquisitionOneShotTransport

    def cursor_namespaces(self) -> tuple[CursorNamespace, CursorNamespace]:
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

    def _rpc(self, method: str, params: Sequence[Any], role: str) -> TransportResponse:
        try:
            return self.transport.rpc_json(
                rpc_url=self.configuration.rpc_url,
                method=method,
                params=params,
                timeout_seconds=self.configuration.timeout_seconds,
                byte_ceiling=self.configuration.per_response_byte_ceiling,
                endpoint_role=role,
            )
        except LiveAcquisitionTransportError:
            raise
        except Exception:
            raise LiveAcquisitionTransportError(
                RECOVERY_PROVIDER_UNAVAILABLE,
                role,
                operation_kind=method,
            ) from None

    def operations(
        self,
        *,
        states: Mapping[CursorNamespace, dict[str, Any]],
    ) -> tuple[AcquisitionSourceOperation, ...]:
        operations: list[AcquisitionSourceOperation] = []
        namespaces = self.cursor_namespaces()
        for local_page in range(1, RECOVERY_PAGES_PER_NAMESPACE + 1):
            for namespace_index, namespace in enumerate(namespaces):
                state = states[namespace]
                request_kind = (
                    "pumpfun_create_index_signature_page"
                    if namespace_index == 0 else "pumpfun_migration_signature_page"
                )
                prefix = "PUMP_CREATE_RECOVERY" if namespace_index == 0 else "PUMP_MIGRATION_RECOVERY"

                def execute_page(
                    *, state: dict[str, Any] = state,
                    namespace: CursorNamespace = namespace,
                    local_page: int = local_page,
                    request_kind: str = request_kind,
                    prefix: str = prefix,
                ) -> NormalizedSourceResult:
                    responses: list[TransportResponse] = []
                    if state["boundary_reached"]:
                        state["page_committed"] = False
                        payload = {**state, "page_committed": False,
                                   "underlying_operation_count": 0,
                                   "underlying_operations": [], "response_bytes": 0,
                                   "declared_operation_ceiling": True}
                        return NormalizedSourceResult(
                            source_name="solana_rpc", request_kind=request_kind,
                            source_status=SourceStatus.COMPLETE,
                            data_quality_label=DataQualityLabel.CLEAN_DATA,
                            normalized_payload=MappingProxyType(payload),
                        )
                    try:
                        input_continuation_signature = state["continuation_signature"]
                        input_continuation_slot = state["continuation_slot"]
                        if local_page == 1 and state["authoritative_start_signature"]:
                            verification = self._rpc(
                                "getTransaction",
                                [state["authoritative_start_signature"], {
                                    "encoding": "json", "commitment": "finalized",
                                    "maxSupportedTransactionVersion": 0,
                                }],
                                prefix + "_PRIOR_BOUNDARY",
                            )
                            responses.append(verification)
                            if not isinstance(verification.payload, Mapping):
                                raise LiveAcquisitionTransportError(
                                    RECOVERY_PRIOR_UNREACHABLE,
                                    verification.endpoint_role,
                                    operation_kind="getTransaction",
                                )
                        options: dict[str, Any] = {
                            "limit": RECOVERY_SIGNATURES_PER_PAGE,
                            "commitment": "finalized",
                        }
                        if input_continuation_signature:
                            options["before"] = input_continuation_signature
                        response = self._rpc(
                            "getSignaturesForAddress",
                            [namespace[1], options],
                            f"{prefix}_PAGE_{state['recovery_page_ordinal'] + 1}",
                        )
                        responses.append(response)
                        if not isinstance(response.payload, list) or any(
                            not isinstance(item, Mapping) for item in response.payload
                        ):
                            raise LiveAcquisitionTransportError(
                                RECOVERY_MALFORMED, response.endpoint_role,
                                operation_kind="getSignaturesForAddress",
                            )
                        raw_rows = [dict(item) for item in response.payload]
                        if not raw_rows:
                            if state["authoritative_start_signature"] is None:
                                state["boundary_reached"] = True
                                state["no_new_signatures"] = True
                                state["terminal_category"] = RECOVERY_NO_NEW
                                page_rows: list[dict[str, Any]] = []
                            else:
                                raise LiveAcquisitionTransportError(
                                    RECOVERY_PRIOR_UNREACHABLE, response.endpoint_role,
                                    operation_kind="getSignaturesForAddress",
                                )
                        else:
                            known = set(str(item) for item in state["seen_signatures"])
                            previous_slot = state["continuation_slot"]
                            page_rows = []
                            boundary_found = False
                            for raw in raw_rows:
                                signature, slot = raw.get("signature"), raw.get("slot")
                                if (
                                    not isinstance(signature, str) or not signature
                                    or type(slot) is not int or slot < 0
                                ):
                                    raise LiveAcquisitionTransportError(
                                        RECOVERY_MALFORMED, response.endpoint_role,
                                        operation_kind="getSignaturesForAddress",
                                    )
                                if signature in known:
                                    raise LiveAcquisitionTransportError(
                                        RECOVERY_DUPLICATE, response.endpoint_role,
                                        operation_kind="getSignaturesForAddress",
                                    )
                                if previous_slot is not None and slot > int(previous_slot):
                                    raise LiveAcquisitionTransportError(
                                        RECOVERY_REWIND, response.endpoint_role,
                                        operation_kind="getSignaturesForAddress",
                                    )
                                if (
                                    state["authoritative_start_slot"] is not None
                                    and slot < int(state["authoritative_start_slot"])
                                    and signature != state["authoritative_start_signature"]
                                ):
                                    raise LiveAcquisitionTransportError(
                                        RECOVERY_SKIP, response.endpoint_role,
                                        operation_kind="getSignaturesForAddress",
                                    )
                                row = {
                                    "signature": signature,
                                    "slot": slot,
                                    "err": raw.get("err"),
                                    "confirmationStatus": raw.get("confirmationStatus"),
                                }
                                page_rows.append(row)
                                known.add(signature)
                                previous_slot = slot
                                if signature == state["authoritative_start_signature"]:
                                    boundary_found = True
                                    break
                            if state["recovery_tip_signature"] is None:
                                state["recovery_tip_signature"] = page_rows[0]["signature"]
                                state["recovery_tip_slot"] = page_rows[0]["slot"]
                            state["seen_signatures"] = sorted(known)
                            state["continuation_signature"] = page_rows[-1]["signature"]
                            state["continuation_slot"] = page_rows[-1]["slot"]
                            state["boundary_reached"] = boundary_found or (
                                state["authoritative_start_signature"] is None
                            )
                            if state["authoritative_start_signature"] is None:
                                state["terminal_category"] = RECOVERY_COMPLETE
                            elif boundary_found:
                                state["no_new_signatures"] = len(page_rows) == 1 and (
                                    page_rows[0]["signature"]
                                    == state["authoritative_start_signature"]
                                )
                                state["terminal_category"] = (
                                    RECOVERY_NO_NEW if state["no_new_signatures"]
                                    else RECOVERY_COMPLETE
                                )
                            else:
                                state["terminal_category"] = RECOVERY_INCOMPLETE
                        state["recovery_page_ordinal"] += 1
                        artifact = {
                            key: state[key] for key in (
                                "network", "indexed_address", "contract_pin",
                                "decoder_version", "direction", "range_mode",
                                "recovery_contract_version", "recovery_id",
                                "authoritative_start_slot", "authoritative_start_signature",
                                "authoritative_cursor_version", "recovery_tip_slot",
                                "recovery_tip_signature", "boundary_reached",
                                "no_new_signatures", "terminal_category",
                            )
                        }
                        artifact.update({
                            "recovery_page_ordinal": state["recovery_page_ordinal"],
                            "input_continuation_slot": input_continuation_slot,
                            "input_continuation_signature": input_continuation_signature,
                            "output_continuation_slot": state["continuation_slot"],
                            "output_continuation_signature": state["continuation_signature"],
                            "page_rows": page_rows,
                            "page_committed": True,
                        })
                        # Input continuation is the exclusive bound used for this
                        # request, captured before state mutation.
                        artifact["page_hash"] = _page_hash(artifact)
                        state.update(artifact)
                        details = [{
                            "operation_kind": item.operation_kind,
                            "operation_state": "COMPLETE",
                            "redacted_endpoint_role": item.endpoint_role,
                            "bytes_used": item.bytes_used,
                        } for item in responses]
                        payload = {**artifact,
                                   "underlying_operation_count": len(details),
                                   "underlying_operations": details,
                                   "response_bytes": sum(item["bytes_used"] for item in details),
                                   "declared_operation_ceiling": True}
                        return NormalizedSourceResult(
                            source_name="solana_rpc", request_kind=request_kind,
                            source_status=SourceStatus.COMPLETE,
                            data_quality_label=DataQualityLabel.CLEAN_DATA,
                            normalized_payload=MappingProxyType(payload),
                        )
                    except Exception as exc:
                        code = getattr(exc, "code", RECOVERY_PROVIDER_UNAVAILABLE)
                        if code not in {
                            RECOVERY_PRIOR_UNREACHABLE, RECOVERY_MALFORMED,
                            RECOVERY_DUPLICATE, RECOVERY_SKIP, RECOVERY_REWIND,
                        }:
                            code = RECOVERY_PROVIDER_UNAVAILABLE
                        details = [{
                            "operation_kind": item.operation_kind,
                            "operation_state": "COMPLETE",
                            "redacted_endpoint_role": item.endpoint_role,
                            "bytes_used": item.bytes_used,
                        } for item in responses]
                        if isinstance(exc, LiveAcquisitionTransportError) and not any(
                            item["operation_kind"] == exc.operation_kind
                            and item["redacted_endpoint_role"] == exc.endpoint_role
                            for item in details
                        ):
                            details.append({
                                "operation_kind": exc.operation_kind,
                                "operation_state": "FAILED",
                                "redacted_endpoint_role": exc.endpoint_role,
                                "bytes_used": exc.bytes_used,
                            })
                        state["terminal_category"] = code
                        state["page_committed"] = False
                        return NormalizedSourceResult(
                            source_name="solana_rpc", request_kind=request_kind,
                            source_status=SourceStatus.FAILED,
                            data_quality_label=DataQualityLabel.MISSING_CRITICAL_DATA,
                            failure_type=code, failure_message=code,
                            normalized_payload=MappingProxyType({
                                **state,
                                "underlying_operation_count": len(details),
                                "underlying_operations": details,
                                "response_bytes": sum(item["bytes_used"] for item in details),
                                "declared_operation_ceiling": True,
                            }),
                        )

                # First local page may verify the exact prior transaction and
                # fetch one signature page. Later pages fetch exactly one page.
                operations.append(AcquisitionSourceOperation(
                    "solana_rpc", request_kind,
                    _RecoveryAdapter(request_kind, execute_page),
                    required=True,
                    round_mode="LIVE_TAIL",
                    expected_transport_operations=(
                        2 if local_page == 1 and state["authoritative_start_signature"] else 1
                    ),
                    cursor_range=state,
                ))
        return tuple(operations)


def build_live_cursor_recovery_transport_owner(
    *,
    environment: Mapping[str, str] | None = None,
    transport: CandidateAcquisitionOneShotTransport | None = None,
) -> CursorRecoveryTransportOwner:
    return CursorRecoveryTransportOwner(
        load_live_acquisition_configuration(environment),
        transport or UrllibCandidateAcquisitionOneShotTransport(),
    )


def _terminalize_recovery_scheduler_residue(
    db_path: str | Path, *, execution_id: str, cause: str, now: str
) -> int:
    connection = _connect(db_path)
    try:
        rows = connection.execute(
            """SELECT id FROM printer_scheduler_jobs
               WHERE job_name LIKE ? AND status IN ('PENDING','RUNNING','COOLDOWN')
               ORDER BY id""",
            (f"cursor-recovery:{execution_id}:%",),
        ).fetchall()
    finally:
        connection.close()
    for row in rows:
        fail_job(db_path, job_id=int(row["id"]), error=cause,
                 now=_parse(now), max_retries=0)
    return len(rows)


def _complete_recovery_foundation(
    db_path: str | Path,
    *,
    execution_id: str,
    now: str,
    preflight: Mapping[str, Any],
    states: Mapping[CursorNamespace, Mapping[str, Any]],
) -> dict[str, Any]:
    observations: list[dict[str, Any]] = []
    source_budgets = {"solana_rpc": {
        "pumpfun_create_index_signature_page": 1,
        "pumpfun_migration_signature_page": 1,
    }}
    for ordinal, (namespace, state) in enumerate(sorted(states.items()), 1):
        start_slot = state["authoritative_start_slot"]
        start_signature = state["authoritative_start_signature"]
        end_slot = state["recovery_tip_slot"]
        end_signature = state["recovery_tip_signature"]
        advanced = bool(end_signature and end_signature != start_signature)
        observations.append({
            "round_ordinal": ordinal,
            "round_mode": "LIVE_TAIL",
            "source_name": "solana_rpc",
            "request_kind": (
                "pumpfun_create_index_signature_page"
                if namespace[1] == PUMP_CREATE_INDEX_ADDRESS
                else "pumpfun_migration_signature_page"
            ),
            "source_status": "COMPLETE",
            "failure_reason": None,
            "observed_at": now,
            "expires_at": (_parse(now) + timedelta(seconds=180)).isoformat(),
            "governed_requests_used": 0,
            "transport_operations_used": 0,
            "bytes_used": 0,
            "rows_used": 1,
            "duration_milliseconds": 0,
            "facts": {
                "cursor_recovery_only": True,
                "recovery_id": state["recovery_id"],
                "recovery_page_count": state["recovery_page_ordinal"],
                "recovery_signature_count": len(state["seen_signatures"]),
            },
            "cursor_range": {
                "indexed_address": namespace[1],
                "contract_pin": namespace[2],
                "decoder_version": namespace[3],
                "direction": namespace[4],
                "range_mode": "LIVE_TAIL",
                "bootstrap_contract": (
                    "EXPLICIT_TIP_BOOTSTRAP" if start_signature is None
                    else "ESTABLISHED_HEAD"
                ),
                "start_slot": start_slot,
                "start_signature": start_signature,
                "end_slot": end_slot,
                "end_signature": end_signature,
                "continuity_state": "CONTIGUOUS",
                "cursor_advanced": advanced,
                "unresolved_reason": None,
                "prior_boundary_verified": start_signature is not None,
            },
        })
    plan = build_acquisition_plan(
        selection_capacity=2,
        execution_id=execution_id,
        selection_seed=f"CURSOR_RECOVERY:{execution_id}",
        window_start=now,
        window_end=now,
        cutoff_at=now,
        finalized_cutoff_slot=0,
        git_provenance=str(
            (preflight.get("git_provenance") or {}).get("git_head")
            or preflight.get("git_provenance")
        ),
        source_budgets=source_budgets,
        allowed_sources=("solana_rpc",),
    )
    return run_candidate_acquisition(db_path, plan=plan, observations=observations)


def run_cursor_continuity_recovery(
    db_path: str | Path,
    *,
    operator_approved: bool,
    transport_owner: CursorRecoveryTransportOwner,
    preflight: Mapping[str, Any],
    execution_id: str,
    owner_id: str,
    now: str,
    lease_seconds: int = RECOVERY_DURATION_SECONDS + 30,
    crash_after_work_ordinal: int | None = None,
    crash_before_foundation: bool = False,
) -> dict[str, Any]:
    if not operator_approved:
        raise CandidateAcquisitionIntegrationError("EXPLICIT_OPERATOR_APPROVAL_REQUIRED")
    preflight_hash = _preflight_hash(preflight, db_path)
    namespaces = transport_owner.cursor_namespaces()
    expected_namespaces = (
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
    if namespaces != expected_namespaces:
        raise CandidateAcquisitionIntegrationError(RECOVERY_NAMESPACE_MISMATCH)
    # Read-only preview is used only to derive the deterministic recovery ID for
    # the immutable authorization row. Heads are reloaded under the lease below.
    preview_heads = _load_exact_cursor_heads(db_path, namespaces=namespaces)
    recovery_id = _recovery_identity(namespaces, preview_heads)
    policy = {
        "selection_capacity": 2,
        "candidate_limit": 0,
        "cursor_recovery_only": True,
        "recovery_id": recovery_id,
        "recovery_contract_version": RECOVERY_CONTRACT_VERSION,
        "pages_per_namespace": RECOVERY_PAGES_PER_NAMESPACE,
        "signatures_per_page": RECOVERY_SIGNATURES_PER_PAGE,
        "governed_request_ceiling": RECOVERY_GOVERNED_REQUEST_CEILING,
        "transport_operation_ceiling": RECOVERY_TRANSPORT_OPERATION_CEILING,
        "duration_seconds": RECOVERY_DURATION_SECONDS,
        "max_manual_executions": RECOVERY_MAX_EXECUTIONS,
        "automatic_retries": 0,
        "source_budgets": {"solana_rpc": {
            "pumpfun_create_index_signature_page": RECOVERY_PAGES_PER_NAMESPACE,
            "pumpfun_migration_signature_page": RECOVERY_PAGES_PER_NAMESPACE,
        }},
    }
    integration_id = f"cain-{_sha((execution_id, MODE_N2))[:32]}"
    connection = _connect(db_path)
    try:
        prior = connection.execute(
            "SELECT 1 FROM printer_candidate_acquisition_integration_reports WHERE execution_id=?",
            (execution_id,),
        ).fetchone()
        if prior is not None:
            return replay_candidate_acquisition_integration_report(
                db_path, execution_id=execution_id
            )
        before = _counts(connection)
        with connection:
            connection.execute(
                """INSERT INTO printer_candidate_acquisition_integrations(
                       integration_id,execution_id,mode,selection_capacity,owner_id,
                       authorization_confirmed,preflight_hash,policy_json,
                       integration_state,started_at,created_at,updated_at
                   ) VALUES (?,?,?,?,?,?,?,?,'AUTHORIZED',?,?,?)""",
                (integration_id, execution_id, MODE_N2, 2, owner_id, 1,
                 preflight_hash, _canonical(policy), now, now, now),
            )
    finally:
        connection.close()

    lease_id: str | None = None
    scheduler_jobs = governed_requests = transport_operations = bytes_used = rows_used = 0
    foundation: dict[str, Any] | None = None
    terminal_status = "BLOCKED"
    first_cause = RECOVERY_INCOMPLETE
    failure_detail: str | None = None
    states: dict[CursorNamespace, dict[str, Any]] = {}
    execution_count = 0
    started = time.monotonic()
    try:
        lease_id = _acquire_lease(
            db_path, integration_id=integration_id, execution_id=execution_id,
            owner_id=owner_id, mode=MODE_N2, now=now, lease_seconds=lease_seconds,
        )
        heads = _load_exact_cursor_heads(db_path, namespaces=namespaces)
        if _recovery_identity(namespaces, heads) != recovery_id:
            raise CandidateAcquisitionIntegrationError(RECOVERY_NAMESPACE_MISMATCH, "head_changed")
        states, execution_count = _load_recovery_chain(
            db_path, namespaces=namespaces, heads=heads, recovery_id=recovery_id
        )
        if execution_count > RECOVERY_MAX_EXECUTIONS:
            raise CandidateAcquisitionIntegrationError(RECOVERY_BOUND_EXHAUSTED)
        operations = (
            () if all(state["boundary_reached"] for state in states.values())
            else transport_owner.operations(states=states)
        )
        for ordinal, operation in enumerate(operations, 1):
            renew_candidate_acquisition_lease(
                db_path, lease_id=lease_id, integration_id=integration_id,
                execution_id=execution_id, owner_id=owner_id, now=now,
                lease_seconds=lease_seconds,
            )
            if time.monotonic() - started > RECOVERY_DURATION_SECONDS:
                raise CandidateAcquisitionIntegrationError("DURATION_CEILING")
            if governed_requests + 1 > RECOVERY_GOVERNED_REQUEST_CEILING:
                raise CandidateAcquisitionIntegrationError("GOVERNED_REQUEST_CEILING")
            request: SourceRequest = build_governed_source_request(
                "solana_rpc", operation.request_kind,
                request_key=f"{execution_id}:{ordinal}", tracking_priority=0,
                payload={"cursor_recovery_only": True, "recovery_id": recovery_id},
                now=_parse(now),
            )
            lock, job_id = enqueue_job(
                db_path,
                job_name=f"cursor-recovery:{execution_id}:{ordinal}",
                job_kind=JobKind.DISCOVERY_REFRESH,
                target_table="printer_candidate_acquisition_integrations",
                target_id=ordinal,
                scheduled_for=_parse(now),
                source_name="solana_rpc",
                source_request_kind=operation.request_kind,
                recent_request_count=count_recent_source_requests(
                    db_path, "solana_rpc", now=_parse(now)
                ),
            )
            if lock is not LockResult.ACQUIRED or job_id is None:
                raise CandidateAcquisitionIntegrationError("SCHEDULER_ENQUEUE_BLOCKED")
            scheduler_jobs += 1
            if claim_due_job(db_path, job_id=job_id, lock_owner=owner_id,
                             now=_parse(now)) is not LockResult.ACQUIRED:
                raise CandidateAcquisitionIntegrationError("SCHEDULER_CLAIM_BLOCKED")
            op_started = time.monotonic()
            source_execution = execute_source_request_with_governor(
                db_path, request, operation.adapter,
                recent_request_count=count_recent_source_requests(
                    db_path, "solana_rpc", now=_parse(now)
                ),
                now=_parse(now),
            )
            renew_candidate_acquisition_lease(
                db_path, lease_id=lease_id, integration_id=integration_id,
                execution_id=execution_id, owner_id=owner_id, now=now,
                lease_seconds=lease_seconds,
            )
            elapsed_ms = int((time.monotonic() - op_started) * 1000)
            normalized = source_execution.normalized_result
            payload = dict(normalized.normalized_payload or {})
            actual_operations = int(payload.get("underlying_operation_count") or 0)
            details = payload.get("underlying_operations") or []
            encoded_size = int(payload.get("response_bytes") or 0)
            if actual_operations > int(operation.expected_transport_operations) or (
                actual_operations != len(details)
            ) or sum(int(item.get("bytes_used") or 0) for item in details) != encoded_size:
                fail_job(db_path, job_id=job_id, error="OPERATION_ACCOUNTING_MISMATCH",
                         now=_parse(now), max_retries=0)
                raise CandidateAcquisitionIntegrationError("OPERATION_ACCOUNTING_MISMATCH")
            if transport_operations + actual_operations > RECOVERY_TRANSPORT_OPERATION_CEILING:
                fail_job(db_path, job_id=job_id, error="TRANSPORT_OPERATION_CEILING",
                         now=_parse(now), max_retries=0)
                raise CandidateAcquisitionIntegrationError("TRANSPORT_OPERATION_CEILING")
            healthy = _source_status(normalized) == "COMPLETE"
            if healthy:
                complete_job(db_path, job_id=job_id, now=_parse(now))
                work_state, work_cause = "SUCCEEDED", "SOURCE_OPERATION_COMPLETE"
            else:
                raw_cause = str(normalized.failure_type or "")
                work_cause = (
                    raw_cause if raw_cause in {
                        RECOVERY_PRIOR_UNREACHABLE, RECOVERY_MALFORMED,
                        RECOVERY_DUPLICATE, RECOVERY_SKIP, RECOVERY_REWIND,
                    } else RECOVERY_PROVIDER_UNAVAILABLE
                )
                fail_job(db_path, job_id=job_id, error=work_cause,
                         now=_parse(now), max_retries=0)
                work_state = "FAILED"
            _persist_work(
                db_path, integration_id=integration_id, execution_id=execution_id,
                ordinal=ordinal, operation=operation, job_id=job_id,
                source_execution=source_execution, state=work_state,
                transport_operations=actual_operations, bytes_used=encoded_size,
                rows_used=len(payload.get("page_rows") or ()),
                duration_milliseconds=elapsed_ms, cause=work_cause, now=now,
                underlying_operations=details,
            )
            governed_requests += 1
            transport_operations += actual_operations
            bytes_used += encoded_size
            rows_used += len(payload.get("page_rows") or ())
            if crash_after_work_ordinal == ordinal:
                raise RuntimeError("INJECTED_CRASH_AFTER_RECOVERY_STATE_COMMIT")
            if not healthy:
                raise CandidateAcquisitionIntegrationError(work_cause)

        if all(state["boundary_reached"] for state in states.values()):
            if crash_before_foundation:
                raise RuntimeError("INJECTED_CRASH_BEFORE_FINAL_HEAD_COMMIT")
            foundation = _complete_recovery_foundation(
                db_path, execution_id=execution_id, now=now,
                preflight=preflight, states=states,
            )
            # Recovery foundation intentionally has zero candidates and no
            # manifest. Success is the exact atomic cursor reconciliation.
            if foundation.get("manifest_id") is not None or int(
                foundation.get("certificate_count") or 0
            ) != 0:
                raise CandidateAcquisitionIntegrationError("RECOVERY_FOUNDATION_SCOPE_VIOLATION")
            first_cause = (
                RECOVERY_NO_NEW
                if all(state["no_new_signatures"] for state in states.values())
                else RECOVERY_COMPLETE
            )
            terminal_status = "COMPLETED"
        else:
            first_cause = RECOVERY_INCOMPLETE
            if execution_count >= RECOVERY_MAX_EXECUTIONS:
                first_cause = RECOVERY_BOUND_EXHAUSTED
            terminal_status = "BLOCKED"
    except CandidateAcquisitionIntegrationError as exc:
        first_cause = exc.code
        failure_detail = exc.detail or str(exc)
        terminal_status = "BLOCKED"
    except Exception as exc:
        first_cause = "CURSOR_RECOVERY_EXCEPTION"
        failure_detail = f"{type(exc).__name__}:{exc}"
        terminal_status = "FAILED"

    scheduler_residue_terminalized = _terminalize_recovery_scheduler_residue(
        db_path, execution_id=execution_id, cause=first_cause, now=now
    )
    connection = _connect(db_path)
    try:
        with connection:
            connection.execute(
                """UPDATE printer_candidate_acquisition_integrations SET
                       foundation_execution_id=?,manifest_id=NULL,projection_count=0,
                       scheduler_jobs_created=?,governed_requests_used=?,
                       transport_operations_used=?,bytes_used=?,rows_used=?,updated_at=?
                   WHERE integration_id=?""",
                (execution_id if foundation is not None else None, scheduler_jobs,
                 governed_requests, transport_operations, bytes_used, rows_used,
                 now, integration_id),
            )
        after = _counts(connection)
        integrity = tuple(str(row[0]) for row in connection.execute("PRAGMA integrity_check"))
        fk = connection.execute("PRAGMA foreign_key_check").fetchall()
    finally:
        connection.close()
    deltas = {table: after[table] - before[table] for table in before}
    if any(deltas.values()):
        terminal_status, first_cause = "FAILED", "FORBIDDEN_TABLE_DELTA"
    if integrity != ("ok",) or fk:
        terminal_status, first_cause = "FAILED", "DATABASE_INTEGRITY_FAILURE"
    cleanup = (
        _release_lease(
            db_path, lease_id=lease_id, integration_id=integration_id,
            terminal_status=terminal_status, first_terminal_cause=first_cause, now=now,
        ) if lease_id is not None else _terminalize_unleased_integration(
            db_path, integration_id=integration_id, terminal_status=terminal_status,
            first_terminal_cause=first_cause, now=now,
        )
    )
    connection = _connect(db_path)
    try:
        active_leases = int(connection.execute(
            "SELECT COUNT(*) FROM printer_candidate_acquisition_leases "
            "WHERE lease_state IN ('ACTIVE','STOPPING')"
        ).fetchone()[0])
        cursor_advances = int(connection.execute(
            "SELECT COUNT(*) FROM printer_candidate_acquisition_cursors "
            "WHERE last_execution_id=?", (execution_id,)
        ).fetchone()[0])
    finally:
        connection.close()
    state_report = {
        namespace[1]: {
            key: value for key, value in state.items()
            if not key.startswith("_") and key != "seen_signatures"
        } | {"seen_signature_count": len(state.get("seen_signatures") or ())}
        for namespace, state in sorted(states.items())
    }
    report = {
        "mode": "CURSOR_RECOVERY_N2",
        "integration_id": integration_id,
        "execution_id": execution_id,
        "recovery_id": recovery_id,
        "recovery_execution_ordinal": execution_count,
        "status": terminal_status,
        "first_terminal_cause": first_cause,
        "failure_detail": failure_detail,
        "policy": policy,
        "scheduler_owner": "Central Scheduler",
        "source_governor_owner": "Source Governor",
        "scheduler_jobs_created": scheduler_jobs,
        "governed_requests_used": governed_requests,
        "transport_operations_used": transport_operations,
        "bytes_used": bytes_used,
        "rows_used": rows_used,
        "recovery_states": state_report,
        "foundation_execution_id": execution_id if foundation is not None else None,
        "foundation_report": foundation,
        "manifest_id": None,
        "projection_count": 0,
        "runtime_handoff_count": 0,
        "cursor_advances_committed": cursor_advances,
        "candidate_admission_during_incomplete_recovery": False,
        "automatic_retry_created": False,
        "restart_created": False,
        "successor_created": False,
        "active_capacity_lock": ACTIVE_CAPACITY,
        "scheduler_residue_terminalized": scheduler_residue_terminalized,
        "lease_cleanup": cleanup,
        "active_lease_count": active_leases,
        "forbidden_table_deltas": deltas,
        "integrity": "ok" if integrity == ("ok",) else list(integrity),
        "foreign_key_violations": len(fk),
        "reliability_claim_status": RELIABILITY_STATUS,
    }
    return _persist_integration_report(
        db_path, integration_id=integration_id, execution_id=execution_id,
        mode=MODE_N2, manifest_id=None, report=report, now=now,
    )


__all__ = [
    "CLI_MODE_CURSOR_RECOVERY_N2",
    "RECOVERY_PAGES_PER_NAMESPACE",
    "RECOVERY_SIGNATURES_PER_PAGE",
    "RECOVERY_GOVERNED_REQUEST_CEILING",
    "RECOVERY_TRANSPORT_OPERATION_CEILING",
    "RECOVERY_DURATION_SECONDS",
    "RECOVERY_MAX_EXECUTIONS",
    "CursorRecoveryTransportOwner",
    "build_live_cursor_recovery_transport_owner",
    "run_cursor_continuity_recovery",
]
