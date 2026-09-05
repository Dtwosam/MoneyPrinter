"""Persistent multi-round Scheduler owner for V2-9.8B pre-lifecycle refreshes."""
from __future__ import annotations
import sqlite3, threading
from datetime import timedelta
from pathlib import Path
from typing import Any, Callable, Mapping

from printer_v1.discovery.pre_lifecycle_refresh_work import (
 active_refresh_work, insert_refresh_work, terminalize_refresh_work,
)
from printer_v1.discovery.pre_lifecycle_temporal_acquisition import (
 ACQUISITION_DEADLINE_EXHAUSTED, ALREADY_PENDING_REFRESH, CANCELLED,
 INTERNAL_INVARIANT, INTERNAL_RUNTIME_ERROR, REFRESH_COMPLETED,
 REFRESH_SOURCE_FAILURE, SOURCE_BUDGET_EXHAUSTED, SUPERVISION_FAILED,
 UNSAFE_SCHEDULER_STATE, WAITING_FOR_ELIGIBLE_SUPPLY,
 PreLifecycleTemporalAcquisitionError, TemporalRefreshOutcome,
 active_refresh_waits, evaluate_wait_eligibility, insert_refresh_wait, iso,
 mark_refresh_wait_claimed, next_refresh_ordinal, parse_iso,
 refresh_opportunity_at, terminalize_refresh_wait,
)
from printer_v1.scheduler.contracts import JobKind, JobStatus, LockResult
from printer_v1.scheduler.resource_governor import next_check_interval_seconds
from printer_v1.scheduler.scheduler import (
 cancel_job, claim_due_job, complete_job, enqueue_job, fail_job, yield_job,
)

REFRESH_WORK_TYPE = "PRE_LIFECYCLE_DISCOVERY_REFRESH"
WAIT_ABORT_SUPERVISION = "SUPERVISION_FAILED"
WAIT_ABORT_CANCELLED = "CANCELLATION_REQUESTED"
FAILURE_DOMAIN_INTERNAL = "INTERNAL"
FAILURE_DOMAIN_SOURCE = "SOURCE"


class PreLifecycleTemporalRefreshError(RuntimeError):
    pass


def _as_refresh_stage_mapping(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise TypeError("refresh stage payload is not a mapping")
    return dict(raw)


def _nonneg_int(value: Any, name: str) -> int:
    if value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"malformed refresh stage field: {name}")
    if value < 0:
        raise ValueError(f"malformed refresh stage field: {name}")
    return value


def classify_refresh_stage_exception(
    exc: BaseException,
) -> tuple[str, str, str]:
    """Return (status, failure_domain, terminal_cause) for one stage exception."""
    from printer_v1.discovery.pre_lifecycle_refresh_composition import (
        PreLifecycleRefreshCompositionError,
    )
    from printer_v1.discovery.pre_lifecycle_refresh_work import (
        PreLifecycleRefreshWorkError,
    )
    from printer_v1.operator_cli.authoritative_live_operational_campaign import (
        LiveOperationalError,
        LiveTransportError,
    )
    from printer_v1.operator_cli.later_cycle_graduated_supply import (
        LaterCycleGraduatedSupplyError,
    )
    from printer_v1.sources.campaign_six_unit_accounting import (
        CampaignSixUnitError,
    )

    if isinstance(exc, LiveTransportError):
        code = str(getattr(exc, "code", "") or type(exc).__name__)
        return (
            REFRESH_SOURCE_FAILURE,
            FAILURE_DOMAIN_SOURCE,
            f"PRE_LIFECYCLE_REFRESH_SOURCE_FAILURE:{code}",
        )
    if isinstance(
        exc,
        (
            CampaignSixUnitError,
            PreLifecycleTemporalRefreshError,
            PreLifecycleTemporalAcquisitionError,
            PreLifecycleRefreshCompositionError,
            PreLifecycleRefreshWorkError,
            LaterCycleGraduatedSupplyError,
            LiveOperationalError,
            TypeError,
            ValueError,
        ),
    ):
        detail = str(exc) or type(exc).__name__
        return (
            INTERNAL_INVARIANT,
            FAILURE_DOMAIN_INTERNAL,
            f"PRE_LIFECYCLE_REFRESH_INTERNAL_INVARIANT:{detail}"[:160],
        )
    return (
        INTERNAL_RUNTIME_ERROR,
        FAILURE_DOMAIN_INTERNAL,
        f"PRE_LIFECYCLE_REFRESH_INTERNAL_RUNTIME:{type(exc).__name__}",
    )


def bounded_interruptible_wait(seconds: float, abort_event: threading.Event | None) -> bool:
    if seconds <= 0:
        return bool(abort_event is not None and abort_event.is_set())
    return bool((abort_event if abort_event is not None else threading.Event()).wait(timeout=seconds))


def _refresh_stage_source_request_coverage(
    stage: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    """Return only exact stage-produced coverage from one refresh quantum."""
    from printer_v1.discovery.permanent_discovery_availability import (
        collect_stage_source_request_coverage,
    )

    reports = stage.get("stage_reports") or {}
    if not isinstance(reports, Mapping):
        raise PreLifecycleTemporalRefreshError(
            "PRE_LIFECYCLE_REFRESH_STAGE_REPORTS_INVALID"
        )
    coverage: list[dict[str, Any]] = []
    for report in reports.values():
        if not isinstance(report, Mapping):
            raise PreLifecycleTemporalRefreshError(
                "PRE_LIFECYCLE_REFRESH_STAGE_REPORT_INVALID"
            )
        coverage.extend(collect_stage_source_request_coverage(report))
    return tuple(dict(item) for item in coverage)


def _refresh_stage_source_request_ids(stage: Mapping[str, Any]) -> tuple[int, ...]:
    """Collect producer-reported IDs independently from coverage manifests."""
    from printer_v1.discovery.permanent_discovery_availability import (
        collect_stage_reported_request_ids,
    )

    reports = stage.get("stage_reports") or {}
    if not isinstance(reports, Mapping):
        raise PreLifecycleTemporalRefreshError(
            "PRE_LIFECYCLE_REFRESH_STAGE_REPORTS_INVALID"
        )
    request_ids: list[int] = []
    for report in reports.values():
        if not isinstance(report, Mapping):
            raise PreLifecycleTemporalRefreshError(
                "PRE_LIFECYCLE_REFRESH_STAGE_REPORT_INVALID"
            )
        request_ids.extend(collect_stage_reported_request_ids(report))
    return tuple(request_ids)


class PreLifecycleTemporalRefreshOwner:
    """One existing authorization may request multiple bounded refresh ordinals."""
    def __init__(self, db_path: str | Path, *, campaign_id: str, run_id: str,
        cycle_id: str, supervision_id: str, source_governor: Any,
        central_scheduler: Any, acquisition_deadline_at: str, work_deadline_at: str,
        refresh_stage: Callable[..., Mapping[str, Any]],
        acquisition_started_at: str | None = None,
        discovery_batch_resolver: Callable[[sqlite3.Connection, str, int], str] | None = None,
        supervision_probe: Callable[[], Mapping[str, Any]] | None = None,
        waiter: Callable[[float], bool] | None = None, clock: Callable[[], str] | None = None,
        publisher: Callable[[Mapping[str, Any]], None] | None = None,
        abort_event: threading.Event | None = None, refresh_interval_seconds: int | None = None,
        cycle_rebinder: Callable[..., "PreLifecycleTemporalRefreshOwner"] | None = None) -> None:
        self.db_path=Path(db_path); self.campaign_id=str(campaign_id); self.run_id=str(run_id)
        self.cycle_id=str(cycle_id); self.supervision_id=str(supervision_id)
        self.source_governor=source_governor; self.central_scheduler=central_scheduler
        self.acquisition_deadline_at=str(acquisition_deadline_at); self.work_deadline_at=str(work_deadline_at)
        self.acquisition_started_at=(
            None if acquisition_started_at is None else str(acquisition_started_at)
        )
        self._refresh_stage=refresh_stage
        self._discovery_batch_resolver=discovery_batch_resolver
        self._supervision_probe=supervision_probe; self._waiter=waiter; self._clock=clock
        self._publisher=publisher; self._abort_event=abort_event
        self._cycle_rebinder=cycle_rebinder
        self._cooperative_yield=False
        self.refresh_interval_seconds=int(next_check_interval_seconds(JobKind.DISCOVERY_REFRESH) if refresh_interval_seconds is None else refresh_interval_seconds)
        self.published_states=[]; self._acquisition_mark=None
    def for_cycle(self, *, cycle_id:str, cycle_cutoff:str, evaluated_at:str,
        request_key_prefix:str,
        stage_evidence_sink: Callable[[Mapping[str, Any]], None] | None = None,
        cooperative_yield: bool = False):
        """Rebuild this bounded owner for a later cycle under canonical authority."""
        if self._cycle_rebinder is None:
            raise PreLifecycleTemporalRefreshError('TEMPORAL_CYCLE_REBINDER_NOT_CONFIGURED')
        rebind_kwargs={
            'cycle_id':str(cycle_id), 'cycle_cutoff':str(cycle_cutoff),
            'evaluated_at':str(evaluated_at),
            'request_key_prefix':str(request_key_prefix),
        }
        if stage_evidence_sink is not None:
            rebind_kwargs['stage_evidence_sink']=stage_evidence_sink
        rebound=self._cycle_rebinder(
            **rebind_kwargs,
        )
        if not isinstance(rebound, type(self)):
            raise PreLifecycleTemporalRefreshError('TEMPORAL_CYCLE_REBINDER_RESULT_INVALID')
        def owner_identity(value):
            return (str(getattr(value,'owner_kind','')), bool(getattr(value,'available',False)))
        if (
            rebound.db_path != self.db_path
            or rebound.campaign_id != self.campaign_id
            or rebound.run_id != self.run_id
            or rebound.supervision_id != self.supervision_id
            or rebound.cycle_id != str(cycle_id)
            or owner_identity(rebound.source_governor) != owner_identity(self.source_governor)
            or owner_identity(rebound.central_scheduler) != owner_identity(self.central_scheduler)
            or rebound.refresh_interval_seconds != self.refresh_interval_seconds
            or rebound.work_deadline_at != self.work_deadline_at
        ):
            raise PreLifecycleTemporalRefreshError('TEMPORAL_CYCLE_REBINDER_AUTHORITY_DRIFT')
        if parse_iso(rebound.acquisition_deadline_at) >= parse_iso(rebound.work_deadline_at):
            raise PreLifecycleTemporalRefreshError('TEMPORAL_CYCLE_REBINDER_DEADLINE_DRIFT')
        if cooperative_yield:
            rebound._waiter=None
            rebound._cooperative_yield=True
        return rebound
    def _connect(self):
        c=sqlite3.connect(self.db_path); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); return c
    def _now(self,fallback): return self._clock() if self._clock is not None else fallback
    def _acquisition_now(self,now):
        return self._acquisition_mark if self._acquisition_mark and parse_iso(self._acquisition_mark)>parse_iso(now) else now
    def _publish(self,state,**evidence):
        payload={"state":state,"campaign_id":self.campaign_id,"run_id":self.run_id,"cycle_id":self.cycle_id,"supervision_id":self.supervision_id,**evidence}
        self.published_states.append(payload)
        if self._publisher is not None: self._publisher(payload)
    def _owners_available(self):
        return all(x is not None and bool(getattr(x,'available',x)) for x in (self.source_governor,self.central_scheduler))
    def _supervision(self):
        if self._supervision_probe is None: return True,False
        s=dict(self._supervision_probe() or {}); cancelled=bool(s.get('cancellation_requested') or s.get('cancellation_requested_at'))
        active=bool(s.get('supervision_active',s.get('supervision_state','ACTIVE')=='ACTIVE' and not s.get('lease_expired',False)))
        return active,cancelled
    def request_temporal_refresh(self, *, reserve_depth:int, required_capacity:int, universe_state:str,
        source_operations_remaining:int, provider_terminal_failure:bool=False, now:str,
        cooperative_stage_budget: Any | None = None) -> TemporalRefreshOutcome:
        c=self._connect()
        try: return self._request(c,reserve_depth=int(reserve_depth),required_capacity=int(required_capacity),universe_state=str(universe_state),source_operations_remaining=int(source_operations_remaining),provider_terminal_failure=bool(provider_terminal_failure),now=str(now),cooperative_stage_budget=cooperative_stage_budget)
        finally: c.close()
    __call__=request_temporal_refresh
    def _request(self,c,*,reserve_depth,required_capacity,universe_state,source_operations_remaining,provider_terminal_failure,now,cooperative_stage_budget=None):
        now=self._acquisition_now(now)
        if not self._owners_available(): return TemporalRefreshOutcome(status=UNSAFE_SCHEDULER_STATE,reserve_depth_before=reserve_depth,reserve_depth_after=reserve_depth,detail='source governor or central scheduler owner unavailable')
        if c.in_transaction: return TemporalRefreshOutcome(status=UNSAFE_SCHEDULER_STATE,reserve_depth_before=reserve_depth,reserve_depth_after=reserve_depth,detail='open sqlite write transaction held at wait boundary')
        active,cancelled=self._supervision()
        pending=active_refresh_waits(c,campaign_id=self.campaign_id,run_id=self.run_id,cycle_id=self.cycle_id)
        resuming=bool(pending)
        resuming_claimed_work=False
        if resuming:
            if len(pending)!=1 or str(pending[0]['wait_state']) not in {'WAITING','CLAIMED'}:
                return TemporalRefreshOutcome(status=UNSAFE_SCHEDULER_STATE,reserve_depth_before=reserve_depth,reserve_depth_after=reserve_depth,detail='pending refresh ownership is ambiguous')
            row=pending[0]
            wait_id=str(row['wait_id']); job_id=int(row['scheduler_job_id'])
            ordinal=int(row['refresh_ordinal']); scheduled=str(row['scheduled_for'])
            resuming_claimed_work=str(row['wait_state'])=='CLAIMED'
            if resuming_claimed_work:
                running_work=active_refresh_work(c,campaign_id=self.campaign_id,run_id=self.run_id,cycle_id=self.cycle_id)
                if len(running_work)!=1 or str(running_work[0]['wait_id'])!=wait_id or int(running_work[0]['scheduler_job_id'])!=job_id or int(running_work[0]['refresh_ordinal'])!=ordinal:
                    return TemporalRefreshOutcome(status=UNSAFE_SCHEDULER_STATE,reserve_depth_before=reserve_depth,reserve_depth_after=reserve_depth,detail='claimed refresh work ownership is ambiguous')
            job_name=f'PRE_LIFECYCLE_DISCOVERY_REFRESH:{self.campaign_id}:{self.run_id}:{self.cycle_id}:{ordinal}'
            due=parse_iso(scheduled)
            waiting=TemporalRefreshOutcome(status=WAITING_FOR_ELIGIBLE_SUPPLY,wait_id=wait_id,scheduler_job_id=job_id,refresh_ordinal=ordinal,scheduled_for=scheduled,reserve_depth_before=reserve_depth,reserve_depth_after=reserve_depth,detail='pre-lifecycle acquisition waiting for a due Scheduler refresh')
            if parse_iso(now)<due:
                return waiting
            woke=now
        else:
            eligibility=evaluate_wait_eligibility(reserve_depth=reserve_depth,required_capacity=required_capacity,universe_state=universe_state,now=now,acquisition_deadline_at=self.acquisition_deadline_at,source_operations_remaining=source_operations_remaining,provider_terminal_failure=provider_terminal_failure,supervision_active=active,cancellation_requested=cancelled,pending_refresh_exists=False)
            if not eligibility.eligible: return TemporalRefreshOutcome(status=eligibility.reason,reserve_depth_before=reserve_depth,reserve_depth_after=reserve_depth,detail='wait eligibility not satisfied')
            ordinal=next_refresh_ordinal(c,campaign_id=self.campaign_id,run_id=self.run_id,cycle_id=self.cycle_id)
            if self.acquisition_started_at is None:
                self.acquisition_started_at=iso(parse_iso(now))
            due=parse_iso(refresh_opportunity_at(self.acquisition_started_at,refresh_ordinal=ordinal,refresh_interval_seconds=self.refresh_interval_seconds))
            if due>=parse_iso(self.acquisition_deadline_at):
                return TemporalRefreshOutcome(status='NO_LAWFUL_REFRESH_WINDOW',reserve_depth_before=reserve_depth,reserve_depth_after=reserve_depth,detail='anchored DISCOVERY_REFRESH opportunity is not strictly before acquisition deadline')
            job_name=f'PRE_LIFECYCLE_DISCOVERY_REFRESH:{self.campaign_id}:{self.run_id}:{self.cycle_id}:{ordinal}'
            result,job_id=enqueue_job(c,job_name=job_name,job_kind=JobKind.DISCOVERY_REFRESH,target_table='printer_discovery_batches',scheduled_for=due)
            if job_id is None: return TemporalRefreshOutcome(status=ALREADY_PENDING_REFRESH if result==LockResult.DUPLICATE_ACTIVE_JOB else UNSAFE_SCHEDULER_STATE,reserve_depth_before=reserve_depth,reserve_depth_after=reserve_depth,detail=f'enqueue refused: {result}')
            wait_id=f'prelifecycle-refresh-wait:{self.campaign_id}:{self.run_id}:{self.cycle_id}:{ordinal}'; scheduled=iso(due)
            insert_refresh_wait(c,wait_id=wait_id,campaign_id=self.campaign_id,run_id=self.run_id,cycle_id=self.cycle_id,supervision_id=self.supervision_id,scheduler_job_id=int(job_id),refresh_ordinal=ordinal,scheduled_for=scheduled,acquisition_deadline_at=self.acquisition_deadline_at,now=now); c.commit()
            self._publish(WAITING_FOR_ELIGIBLE_SUPPLY,wait_id=wait_id,scheduler_job_id=int(job_id),refresh_ordinal=ordinal,scheduled_for=scheduled,eligible_reserve_depth=reserve_depth,required_eligible_capacity=required_capacity,acquisition_deadline_at=self.acquisition_deadline_at)
            waiting=TemporalRefreshOutcome(status=WAITING_FOR_ELIGIBLE_SUPPLY,wait_id=wait_id,scheduler_job_id=int(job_id),refresh_ordinal=ordinal,scheduled_for=scheduled,reserve_depth_before=reserve_depth,reserve_depth_after=reserve_depth,detail='pre-lifecycle acquisition waiting for a due Scheduler refresh')
            if self._waiter is None:
                if parse_iso(now) < due:
                    return waiting
                woke = now
                aborted = False
                self._acquisition_mark = woke
            else:
                aborted=bool(self._waiter(max(0.0,(due-parse_iso(now)).total_seconds()))); woke=self._now(scheduled); self._acquisition_mark=woke
        active,cancelled=self._supervision()
        if (not resuming and aborted) or not active or cancelled:
            cause=WAIT_ABORT_SUPERVISION if not active else WAIT_ABORT_CANCELLED; status=SUPERVISION_FAILED if not active else CANCELLED
            self._abandon(c,wait_id,int(job_id),'CANCELLED',cause,woke)
            return TemporalRefreshOutcome(status=status,wait_id=wait_id,scheduler_job_id=int(job_id),refresh_ordinal=ordinal,scheduled_for=scheduled,reserve_depth_before=reserve_depth,reserve_depth_after=reserve_depth,detail=cause)
        if parse_iso(woke)>=parse_iso(self.acquisition_deadline_at):
            self._abandon(c,wait_id,int(job_id),'CANCELLED','PRE_LIFECYCLE_ACQUISITION_DEADLINE_EXHAUSTED',woke)
            return TemporalRefreshOutcome(status=ACQUISITION_DEADLINE_EXHAUSTED,wait_id=wait_id,scheduler_job_id=int(job_id),refresh_ordinal=ordinal,scheduled_for=scheduled,reserve_depth_before=reserve_depth,reserve_depth_after=reserve_depth,detail='acquisition deadline reached before refresh due')
        lock_owner=f'pre-lifecycle-refresh:{wait_id}'
        claim=claim_due_job(c,job_id=int(job_id),lock_owner=lock_owner,now=parse_iso(woke))
        if claim!=LockResult.ACQUIRED:
            self._abandon(c,wait_id,int(job_id),'FAILED',f'PRE_LIFECYCLE_REFRESH_CLAIM_{claim.value}',woke)
            return TemporalRefreshOutcome(status=UNSAFE_SCHEDULER_STATE,wait_id=wait_id,scheduler_job_id=int(job_id),refresh_ordinal=ordinal,scheduled_for=scheduled,reserve_depth_before=reserve_depth,reserve_depth_after=reserve_depth,detail=f'claim not acquired: {claim}')
        self._require_claim(c,int(job_id),job_name,lock_owner)
        if not resuming_claimed_work:
            mark_refresh_wait_claimed(c,wait_id=wait_id,now=woke); c.commit()
        refresh_work_id=f'prelifecycle-refresh-work:{self.campaign_id}:{self.run_id}:{self.cycle_id}:{ordinal}'
        if not resuming_claimed_work:
            try:
                insert_refresh_work(c,refresh_work_id=refresh_work_id,wait_id=wait_id,campaign_id=self.campaign_id,run_id=self.run_id,cycle_id=self.cycle_id,supervision_id=self.supervision_id,scheduler_job_id=int(job_id),refresh_ordinal=ordinal,work_deadline_at=self.work_deadline_at,now=woke); c.commit()
            except Exception as exc:
                fail_job(c,job_id=int(job_id),error='PRE_LIFECYCLE_REFRESH_WORK_OWNERSHIP_FAILED',max_retries=0)
                terminalize_refresh_wait(c,wait_id=wait_id,wait_state='FAILED',first_terminal_cause='PRE_LIFECYCLE_REFRESH_WORK_OWNERSHIP_FAILED',now=woke); c.commit()
                return TemporalRefreshOutcome(status=UNSAFE_SCHEDULER_STATE,wait_id=wait_id,scheduler_job_id=int(job_id),refresh_ordinal=ordinal,scheduled_for=scheduled,claimed=True,reserve_depth_before=reserve_depth,reserve_depth_after=reserve_depth,detail=f'refresh work ownership failed: {type(exc).__name__}')
        try:
            raw_stage=self._refresh_stage(c,campaign_id=self.campaign_id,run_id=self.run_id,cycle_id=self.cycle_id,refresh_work_id=refresh_work_id,discovery_work_id=refresh_work_id,scheduler_job_id=int(job_id),refresh_ordinal=ordinal,source_operations_remaining=source_operations_remaining,now=woke,cooperative_yield=self._cooperative_yield,cooperative_stage_budget=cooperative_stage_budget)
        except Exception as exc:
            status,domain,cause=classify_refresh_stage_exception(exc)
            from printer_v1.discovery.pre_lifecycle_refresh_composition import (
                PreLifecycleRefreshCompositionError,
            )
            partial=(
                exc.partial_stage
                if isinstance(exc,PreLifecycleRefreshCompositionError)
                else None
            )
            ops=0; failures=0; unavailable=(); attempted=(); skipped=()
            source_request_ids=(); coverage=()
            if isinstance(partial,Mapping):
                try:
                    stage=_as_refresh_stage_mapping(partial)
                    ops=_nonneg_int(stage.get('source_operations'),'source_operations')
                    failures=_nonneg_int(stage.get('provider_failures'),'provider_failures')
                    unavailable=tuple(str(x) for x in stage.get('channels_unavailable',()))
                    attempted=tuple(str(x) for x in stage.get('channels_attempted',()))
                    skipped=tuple(dict(x) for x in stage.get('channels_skipped',()) if isinstance(x,Mapping))
                    source_request_ids=_refresh_stage_source_request_ids(stage)
                    coverage=_refresh_stage_source_request_coverage(stage)
                except Exception:
                    ops=0; failures=0; unavailable=(); attempted=(); skipped=()
                    source_request_ids=(); coverage=()
            if domain==FAILURE_DOMAIN_SOURCE:
                failures=max(1,failures)
            self._terminalize(c,wait_id,refresh_work_id,int(job_id),False,cause,woke)
            return TemporalRefreshOutcome(status=status,wait_id=wait_id,scheduler_job_id=int(job_id),refresh_ordinal=ordinal,scheduled_for=scheduled,claimed=True,source_operations=ops,provider_failures=failures,channels_unavailable=unavailable,channels_attempted=attempted,channels_skipped=skipped,source_request_ids=source_request_ids,source_request_coverage=coverage,reserve_depth_before=reserve_depth,reserve_depth_after=reserve_depth,detail=f'refresh stage failed: {type(exc).__name__}',failure_domain=domain)
        ops=0; failures=0
        try:
            stage=_as_refresh_stage_mapping(raw_stage)
            ops=_nonneg_int(stage.get('source_operations'),'source_operations')
            failures=_nonneg_int(stage.get('provider_failures'),'provider_failures')
            unavailable=tuple(str(x) for x in stage.get('channels_unavailable',()))
            source_request_ids=_refresh_stage_source_request_ids(stage)
            coverage=_refresh_stage_source_request_coverage(stage)
            for key,expected in (('campaign_id',self.campaign_id),('run_id',self.run_id),('cycle_id',self.cycle_id)):
                if key in stage and str(stage[key])!=str(expected):
                    raise PreLifecycleTemporalRefreshError(f'PRE_LIFECYCLE_REFRESH_STAGE_IDENTITY_MISMATCH:{key}')
        except Exception as exc:
            status,domain,cause=classify_refresh_stage_exception(exc)
            if domain==FAILURE_DOMAIN_SOURCE:
                status,domain,cause=INTERNAL_INVARIANT,FAILURE_DOMAIN_INTERNAL,f'PRE_LIFECYCLE_REFRESH_INTERNAL_INVARIANT:{type(exc).__name__}'
            self._terminalize(c,wait_id,refresh_work_id,int(job_id),False,cause,woke)
            return TemporalRefreshOutcome(status=status,wait_id=wait_id,scheduler_job_id=int(job_id),refresh_ordinal=ordinal,scheduled_for=scheduled,claimed=True,source_operations=ops,provider_failures=failures,reserve_depth_before=reserve_depth,reserve_depth_after=reserve_depth,detail=f'refresh stage local accounting failed: {type(exc).__name__}',failure_domain=domain)
        if ops>source_operations_remaining:
            self._terminalize(c,wait_id,refresh_work_id,int(job_id),False,'PRE_LIFECYCLE_REFRESH_BUDGET_OVERRUN',woke)
            return TemporalRefreshOutcome(status=SOURCE_BUDGET_EXHAUSTED,wait_id=wait_id,scheduler_job_id=int(job_id),refresh_ordinal=ordinal,scheduled_for=scheduled,claimed=True,source_operations=source_operations_remaining,reserve_depth_before=reserve_depth,reserve_depth_after=reserve_depth,detail='refresh stage exceeded cumulative discovery budget')
        if bool(stage.get('cooperative_incomplete')):
            next_bound=stage.get('next_governed_request_worst_case_seconds')
            if next_bound is None or float(next_bound)<=0:
                self._terminalize(c,wait_id,refresh_work_id,int(job_id),False,'PRE_LIFECYCLE_REFRESH_NEXT_REQUEST_BOUND_MISSING',woke)
                return TemporalRefreshOutcome(status=INTERNAL_INVARIANT,wait_id=wait_id,scheduler_job_id=int(job_id),refresh_ordinal=ordinal,scheduled_for=scheduled,claimed=True,source_operations=ops,reserve_depth_before=reserve_depth,reserve_depth_after=reserve_depth,detail='cooperative refresh did not declare its next governed-request bound',failure_domain=FAILURE_DOMAIN_INTERNAL)
            yield_job(c,job_id=int(job_id),scheduled_for=parse_iso(woke),now=parse_iso(woke)); c.commit()
            return TemporalRefreshOutcome(status=WAITING_FOR_ELIGIBLE_SUPPLY,wait_id=wait_id,scheduler_job_id=int(job_id),refresh_ordinal=ordinal,scheduled_for=scheduled,claimed=True,source_operations=ops,provider_failures=failures,channels_unavailable=unavailable,channels_attempted=tuple(str(x) for x in stage.get('channels_attempted',())),channels_skipped=tuple(dict(x) for x in stage.get('channels_skipped',()) if isinstance(x,Mapping)),source_request_ids=source_request_ids,source_request_coverage=coverage,reserve_depth_before=reserve_depth,reserve_depth_after=reserve_depth,detail='cooperative refresh yielded after one governed request',next_governed_request_kind=(None if stage.get('next_governed_request_kind') is None else str(stage.get('next_governed_request_kind'))),next_governed_request_worst_case_seconds=float(next_bound))
        self._terminalize(c,wait_id,refresh_work_id,int(job_id),True,'PRE_LIFECYCLE_REFRESH_COMPLETED',woke)
        self._publish(REFRESH_COMPLETED,wait_id=wait_id,scheduler_job_id=int(job_id),refresh_ordinal=ordinal,source_operations=ops)
        return TemporalRefreshOutcome(status=REFRESH_COMPLETED,wait_id=wait_id,scheduler_job_id=int(job_id),refresh_ordinal=ordinal,scheduled_for=scheduled,claimed=True,source_operations=ops,provider_failures=failures,channels_unavailable=unavailable,channels_attempted=tuple(str(x) for x in stage.get('channels_attempted',())),channels_skipped=tuple(dict(x) for x in stage.get('channels_skipped',()) if isinstance(x,Mapping)),source_request_ids=source_request_ids,source_request_coverage=coverage,newly_observed_exact_identities=tuple(dict(x) for x in stage.get('newly_observed_exact_identities',()) if isinstance(x,Mapping)),promoted_observation_eligible=tuple(dict(x) for x in stage.get('promoted_observation_eligible',())),reserve_depth_before=reserve_depth,reserve_depth_after=reserve_depth,detail='bounded Source-Governed refresh stage completed')
    def _require_claim(self,c,job_id,job_name,lock_owner):
        r=c.execute('SELECT id,job_name,job_kind,status,lock_owner FROM printer_scheduler_jobs WHERE id=?',(job_id,)).fetchone()
        if r is None or int(r['id'])!=job_id or str(r['job_name'])!=job_name or str(r['job_kind'])!=JobKind.DISCOVERY_REFRESH.value or str(r['status'])!=JobStatus.RUNNING.value or str(r['lock_owner'] or '')!=lock_owner:
            raise PreLifecycleTemporalRefreshError('PRE_LIFECYCLE_REFRESH_CLAIMED_IDENTITY_MISMATCH')
    def cancel_pending_wait(self,*,wait_id,scheduler_job_id,cause,now):
        c=self._connect()
        try: self._abandon(c,wait_id,int(scheduler_job_id),'CANCELLED',cause,now)
        finally: c.close()
    def _abandon(self,c,wait_id,job_id,state,cause,now):
        cancel_job(c,job_id=job_id); terminalize_refresh_wait(c,wait_id=wait_id,wait_state=state,first_terminal_cause=cause,now=now); c.commit(); self._publish(state,wait_id=wait_id,scheduler_job_id=job_id,first_terminal_cause=cause)
    def _terminalize(self,c,wait_id,refresh_work_id,job_id,succeeded,cause,now):
        terminalize_refresh_work(c,refresh_work_id=refresh_work_id,work_state='SUCCEEDED' if succeeded else 'FAILED',first_terminal_cause=cause,now=now)
        if succeeded: complete_job(c,job_id=job_id)
        else: fail_job(c,job_id=job_id,error=cause,max_retries=0)
        terminalize_refresh_wait(c,wait_id=wait_id,wait_state='SUCCEEDED' if succeeded else 'FAILED',first_terminal_cause=cause,now=now); c.commit()


def abandon_scoped_refresh_waits(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    run_id: str,
    cause: str,
    now: str,
    cycle_id: str | None = None,
) -> tuple[str, ...]:
    """Terminalize WAITING/CLAIMED waits for one campaign/run (optional cycle).

    Cancels still-active matching Scheduler jobs and RUNNING refresh work.
    Already-terminal jobs/waits are left unchanged. Does not invent a second
    wait owner.
    """
    from printer_v1.discovery.pre_lifecycle_temporal_acquisition import (
        WAIT_TABLE,
        wait_table_exists,
    )
    from printer_v1.scheduler.scheduler import cancel_job as _cancel_job

    if not wait_table_exists(connection):
        return ()
    cause_text = str(cause or "").strip()
    if not cause_text:
        raise PreLifecycleTemporalRefreshError("MISSING_REFRESH_WAIT_ABANDON_CAUSE")
    clauses = ["campaign_id=?", "run_id=?", "wait_state IN ('WAITING','CLAIMED')"]
    params: list[Any] = [str(campaign_id), str(run_id)]
    if cycle_id:
        clauses.append("cycle_id=?")
        params.append(str(cycle_id))
    previous = connection.row_factory
    connection.row_factory = sqlite3.Row
    try:
        rows = list(
            connection.execute(
                f"SELECT wait_id,cycle_id,scheduler_job_id FROM {WAIT_TABLE} "
                f"WHERE {' AND '.join(clauses)} ORDER BY refresh_ordinal,wait_id",
                tuple(params),
            ).fetchall()
        )
    finally:
        connection.row_factory = previous
    abandoned: list[str] = []
    for row in rows:
        wait_id = str(row["wait_id"])
        job_id = int(row["scheduler_job_id"])
        job = connection.execute(
            "SELECT status,locked_at,lock_owner FROM printer_scheduler_jobs WHERE id=?",
            (job_id,),
        ).fetchone()
        if job is not None:
            status = str(job[0] if not isinstance(job, sqlite3.Row) else job["status"])
            locked_at = job[1] if not isinstance(job, sqlite3.Row) else job["locked_at"]
            lock_owner = job[2] if not isinstance(job, sqlite3.Row) else job["lock_owner"]
            if status in {"PENDING", "RUNNING", "COOLDOWN"} or locked_at is not None or lock_owner:
                _cancel_job(connection, job_id=job_id)
        for work in active_refresh_work(
            connection,
            campaign_id=str(campaign_id),
            run_id=str(run_id),
            cycle_id=str(row["cycle_id"]),
        ):
            if str(work.get("wait_id") or "") != wait_id:
                continue
            if str(work.get("work_state") or "") != "RUNNING":
                continue
            terminalize_refresh_work(
                connection,
                refresh_work_id=str(work["refresh_work_id"]),
                work_state="FAILED",
                first_terminal_cause=cause_text,
                now=now,
            )
        terminalize_refresh_wait(
            connection,
            wait_id=wait_id,
            wait_state="CANCELLED",
            first_terminal_cause=cause_text,
            now=now,
        )
        abandoned.append(wait_id)
    return tuple(abandoned)


__all__=['PreLifecycleTemporalRefreshError','PreLifecycleTemporalRefreshOwner','REFRESH_WORK_TYPE','abandon_scoped_refresh_waits','bounded_interruptible_wait','classify_refresh_stage_exception']
