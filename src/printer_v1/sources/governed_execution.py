"""Fixture-only governed source execution boundary for Phase 23."""

from __future__ import annotations

from dataclasses import dataclass
from contextvars import ContextVar, Token
from datetime import datetime, timedelta, timezone
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Mapping

if TYPE_CHECKING:
    from printer_v1.sources.pumpportal import PumpPortalAdapter

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.sources.contracts import (
    GOVERNOR_ONLY_EXECUTION_PATH,
    NormalizedSourceResult,
    SourceAdapterContext,
    SourceAdapterContract,
    SourceFailureRecord,
    SourceRequest,
    SourceRequestRecord,
    SourceResponseRecord,
    build_governor_decision,
    build_source_adapter_contract,
    validate_source_adapter_contract,
)
from printer_v1.db.sqlite_write_contracts import release_write_transaction
from printer_v1.sources.recording import (
    record_source_failure,
    record_source_request,
    record_source_response,
)


FIXTURE_SUCCESS = "fixture_success"
FIXTURE_MALFORMED = "fixture_malformed"
FIXTURE_STALE = "fixture_stale"
FIXTURE_FAILURE = "fixture_failure"

_ATTEMPT_OBSERVER: ContextVar[Any | None] = ContextVar(
    "printer_v1_governed_attempt_observer", default=None
)


def set_governed_attempt_observer(observer: Any | None) -> Token:
    """Install an execution-local observer for the real governed attempt boundary."""
    return _ATTEMPT_OBSERVER.set(observer)


def reset_governed_attempt_observer(token: Token) -> None:
    _ATTEMPT_OBSERVER.reset(token)


def _observe_attempt(execution: GovernedSourceExecutionResult) -> None:
    observer = _ATTEMPT_OBSERVER.get()
    if observer is None:
        return
    from printer_v1.sources.measured_transport import merge_transport_payload_metadata

    payload = execution.normalized_result.normalized_payload
    measured = merge_transport_payload_metadata(payload)
    observer(
        {
            "boundary": "GOVERNED_SOURCE_ATTEMPT",
            "request_key": execution.request_record.request_key,
            "source_name": execution.request_record.source_name,
            "request_kind": execution.request_record.request_kind,
            "source_request_id": int(execution.request_record.id),
            "source_response_id": (
                None
                if execution.response_record is None
                else int(execution.response_record.id)
            ),
            "source_failure_id": (
                None
                if execution.failure_record is None
                else int(execution.failure_record.id)
            ),
            "result": (
                "SUCCEEDED"
                if execution.response_record is not None
                else "FAILED"
            ),
            "response_bytes": int(measured["response_bytes"]),
            "normalized_rows": int(measured["normalized_rows"]),
            "transport_operation_identities": [
                dict(item)
                for item in measured["transport_operation_identities"]
                if isinstance(item, Mapping)
            ],
        }
    )


@dataclass(frozen=True)
class GovernedSourceExecutionResult:
    request_record: SourceRequestRecord
    normalized_result: NormalizedSourceResult
    response_record: SourceResponseRecord | None = None
    failure_record: SourceFailureRecord | None = None


class FixtureSourceAdapter:
    """Local test double for future adapters; it has no network implementation."""

    def __init__(
        self,
        contract: SourceAdapterContract,
        *,
        fixture_kind: str = FIXTURE_SUCCESS,
        fixture_payload: Mapping[str, Any] | None = None,
    ) -> None:
        if not validate_source_adapter_contract(contract):
            raise ValueError("source adapter contract violates Phase 23 boundary")
        self.contract = contract
        self.fixture_kind = fixture_kind
        self.fixture_payload = MappingProxyType(dict(fixture_payload or {}))
        self.call_count = 0

    def execute(self, context: SourceAdapterContext) -> NormalizedSourceResult:
        if not context or not context.governor_approved:
            raise PermissionError("source adapter execution requires Source Governor approval")
        if context.execution_path != GOVERNOR_ONLY_EXECUTION_PATH:
            raise PermissionError("source adapter execution requires governed recording path")
        if context.request.source_name != self.contract.source_name:
            raise ValueError("source request does not match adapter contract")
        if context.request.request_kind not in self.contract.allowed_request_kinds:
            raise ValueError("source request kind is not allowed for adapter contract")

        self.call_count += 1
        if self.fixture_kind == FIXTURE_SUCCESS:
            return NormalizedSourceResult(
                source_name=context.request.source_name,
                request_kind=context.request.request_kind,
                source_status=SourceStatus.COMPLETE,
                data_quality_label=DataQualityLabel.CLEAN_DATA,
                normalized_payload=MappingProxyType(dict(self.fixture_payload)),
                status_code=200,
            )
        if self.fixture_kind == FIXTURE_STALE:
            stale_time = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
            return NormalizedSourceResult(
                source_name=context.request.source_name,
                request_kind=context.request.request_kind,
                source_status=SourceStatus.STALE,
                data_quality_label=DataQualityLabel.STALE_DATA,
                normalized_payload=MappingProxyType(dict(self.fixture_payload)),
                status_code=200,
                received_at=stale_time,
            )
        if self.fixture_kind == FIXTURE_MALFORMED:
            return NormalizedSourceResult(
                source_name=context.request.source_name,
                request_kind=context.request.request_kind,
                source_status=SourceStatus.FAILED,
                data_quality_label=DataQualityLabel.MISSING_CRITICAL_DATA,
                normalized_payload=MappingProxyType({}),
                status_code=200,
                failure_type="malformed_fixture",
                failure_message="fixture payload missing required fields",
            )
        if self.fixture_kind == FIXTURE_FAILURE:
            return NormalizedSourceResult(
                source_name=context.request.source_name,
                request_kind=context.request.request_kind,
                source_status=SourceStatus.FAILED,
                data_quality_label=DataQualityLabel.MISSING_CRITICAL_DATA,
                normalized_payload=MappingProxyType({}),
                failure_type="fixture_failure",
                failure_message="fixture source failure",
            )
        raise ValueError(f"Unknown fixture kind: {self.fixture_kind}")


def build_fixture_source_adapter(
    source_name: str,
    *,
    fixture_kind: str = FIXTURE_SUCCESS,
    fixture_payload: Mapping[str, Any] | None = None,
) -> FixtureSourceAdapter:
    contract = build_source_adapter_contract(source_name)
    return FixtureSourceAdapter(
        contract,
        fixture_kind=fixture_kind,
        fixture_payload=fixture_payload,
    )


def execute_source_request_with_governor(
    db_path_or_conn,
    source_request: SourceRequest,
    adapter: FixtureSourceAdapter | PumpPortalAdapter,
    *,
    recent_request_count: int = 0,
    now: datetime | None = None,
) -> GovernedSourceExecutionResult:
    """Record a governed source request, execute the adapter, then record the result.

    V2-9.8B.20 architecture contract: the request row is committed (write lock
    released) *before* ``adapter.execute``. Source I/O, sleeps, or long work
    must never run while a shared SQLite write transaction remains open. The
    response/failure write is a separate short transaction after the adapter
    returns. Source Governor admission remains authoritative.
    """
    decision = build_governor_decision(
        source_request,
        recent_request_count=recent_request_count,
        now=now,
    )
    request_record = record_source_request(db_path_or_conn, source_request, decision)
    # Release any deferred write held by a shared connection before adapter I/O.
    release_write_transaction(db_path_or_conn)

    if not decision.allowed:
        failure_record = record_source_failure(
            db_path_or_conn,
            request_record,
            failure_type=decision.reason,
            failure_message="Source Governor rejected fixture execution",
            source_status=decision.source_status,
            data_quality_label=decision.data_quality_label,
        )
        release_write_transaction(db_path_or_conn)
        result = NormalizedSourceResult(
            source_name=source_request.source_name,
            request_kind=source_request.request_kind,
            source_status=decision.source_status,
            data_quality_label=decision.data_quality_label,
            failure_type=decision.reason,
            failure_message="Source Governor rejected fixture execution",
        )
        execution = GovernedSourceExecutionResult(
            request_record=request_record,
            normalized_result=result,
            failure_record=failure_record,
        )
        _observe_attempt(execution)
        return execution

    context = SourceAdapterContext(
        request=source_request,
        request_record=request_record,
        decision=decision,
        governor_approved=True,
    )
    # Adapter transport / fixture work runs with no open write transaction.
    result = adapter.execute(context)
    if result.source_status in {SourceStatus.COMPLETE, SourceStatus.PARTIAL, SourceStatus.STALE} and not result.failure_type:
        response_record = record_source_response(db_path_or_conn, request_record, result)
        release_write_transaction(db_path_or_conn)
        execution = GovernedSourceExecutionResult(
            request_record=request_record,
            normalized_result=result,
            response_record=response_record,
        )
        _observe_attempt(execution)
        return execution

    failure_record = record_source_failure(
        db_path_or_conn,
        request_record,
        failure_type=result.failure_type or "fixture_failure",
        failure_message=result.failure_message,
        source_status=result.source_status,
        data_quality_label=result.data_quality_label,
        failed_at=result.received_at,
        retry_after_at=result.retry_after_at,
        normalized_payload=result.normalized_payload,
    )
    release_write_transaction(db_path_or_conn)
    execution = GovernedSourceExecutionResult(
        request_record=request_record,
        normalized_result=result,
        failure_record=failure_record,
    )
    _observe_attempt(execution)
    return execution
