"""Persistent multi-round Scheduler owner for V2-9.8B pre-lifecycle refreshes."""
from __future__ import annotations
import sqlite3, threading
from datetime import timedelta
from pathlib import Path
from typing import Any, Callable, Mapping

from printer_v1.discovery.pre_lifecycle_refresh_work import insert_refresh_work, terminalize_refresh_work
from printer_v1.discovery.pre_lifecycle_temporal_acquisition import (
 ACQUISITION_DEADLINE_EXHAUSTED, ALREADY_PENDING_REFRESH, CANCELLED,
 REFRESH_COMPLETED, REFRESH_SOURCE_FAILURE, SOURCE_BUDGET_EXHAUSTED,
 SUPERVISION_FAILED, UNSAFE_SCHEDULER_STATE, WAITING_FOR_ELIGIBLE_SUPPLY,
 TemporalRefreshOutcome, active_refresh_waits, evaluate_wait_eligibility,
 insert_refresh_wait, iso, mark_refresh_wait_claimed, next_refresh_ordinal,
 parse_iso, refresh_window_fits, terminalize_refresh_wait,
)
from printer_v1.scheduler.contracts import JobKind, JobStatus, LockResult
from printer_v1.scheduler.resource_governor import next_check_interval_seconds
from printer_v1.scheduler.scheduler import cancel_job, claim_due_job, complete_job, enqueue_job, fail_job

REFRESH_WORK_TYPE = "PRE_LIFECYCLE_DISCOVERY_REFRESH"
WAIT_ABORT_SUPERVISION = "SUPERVISION_FAILED"
WAIT_ABORT_CANCELLED = "CANCELLATION_REQUESTED"

class PreLifecycleTemporalRefreshError(RuntimeError): pass

def bounded_interruptible_wait(seconds: float, abort_event: threading.Event | None) -> bool:
    if seconds <= 0:
        return bool(abort_event is not None and abort_event.is_set())
    return bool((abort_event if abort_event is not None else threading.Event()).wait(timeout=seconds))

class PreLifecycleTemporalRefreshOwner:
    """One existing authorization may request multiple bounded refresh ordinals."""
    def __init__(self, db_path: str | Path, *, campaign_id: str, run_id: str,
        cycle_id: str, supervision_id: str, source_governor: Any,
        central_scheduler: Any, acquisition_deadline_at: str, work_deadline_at: str,
        refresh_stage: Callable[..., Mapping[str, Any]],
        discovery_batch_resolver: Callable[[sqlite3.Connection, str, int], str] | None = None,
        supervision_probe: Callable[[], Mapping[str, Any]] | None = None,
        waiter: Callable[[float], bool] | None = None, clock: Callable[[], str] | None = None,
        publisher: Callable[[Mapping[str, Any]], None] | None = None,
        abort_event: threading.Event | None = None, refresh_interval_seconds: int | None = None) -> None:
        self.db_path=Path(db_path); self.campaign_id=str(campaign_id); self.run_id=str(run_id)
        self.cycle_id=str(cycle_id); self.supervision_id=str(supervision_id)
        self.source_governor=source_governor; self.central_scheduler=central_scheduler
        self.acquisition_deadline_at=str(acquisition_deadline_at); self.work_deadline_at=str(work_deadline_at)
        self._refresh_stage=refresh_stage
        self._discovery_batch_resolver=discovery_batch_resolver
        self._supervision_probe=supervision_probe; self._waiter=waiter; self._clock=clock
        self._publisher=publisher; self._abort_event=abort_event
        self.refresh_interval_seconds=int(next_check_interval_seconds(JobKind.DISCOVERY_REFRESH) if refresh_interval_seconds is None else refresh_interval_seconds)
        self.published_states=[]; self._acquisition_mark=None
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
        source_operations_remaining:int, provider_terminal_failure:bool=False, now:str) -> TemporalRefreshOutcome:
        c=self._connect()
        try: return self._request(c,reserve_depth=int(reserve_depth),required_capacity=int(required_capacity),universe_state=str(universe_state),source_operations_remaining=int(source_operations_remaining),provider_terminal_failure=bool(provider_terminal_failure),now=str(now))
        finally: c.close()
    __call__=request_temporal_refresh
    def _request(self,c,*,reserve_depth,required_capacity,universe_state,source_operations_remaining,provider_terminal_failure,now):
        now=self._acquisition_now(now)
        if not self._owners_available(): return TemporalRefreshOutcome(status=UNSAFE_SCHEDULER_STATE,reserve_depth_before=reserve_depth,reserve_depth_after=reserve_depth,detail='source governor or central scheduler owner unavailable')
        if c.in_transaction: return TemporalRefreshOutcome(status=UNSAFE_SCHEDULER_STATE,reserve_depth_before=reserve_depth,reserve_depth_after=reserve_depth,detail='open sqlite write transaction held at wait boundary')
        active,cancelled=self._supervision()
        eligibility=evaluate_wait_eligibility(reserve_depth=reserve_depth,required_capacity=required_capacity,universe_state=universe_state,now=now,acquisition_deadline_at=self.acquisition_deadline_at,source_operations_remaining=source_operations_remaining,provider_terminal_failure=provider_terminal_failure,supervision_active=active,cancellation_requested=cancelled,pending_refresh_exists=bool(active_refresh_waits(c,campaign_id=self.campaign_id,run_id=self.run_id,cycle_id=self.cycle_id)))
        if not eligibility.eligible: return TemporalRefreshOutcome(status=eligibility.reason,reserve_depth_before=reserve_depth,reserve_depth_after=reserve_depth,detail='wait eligibility not satisfied')
        if not refresh_window_fits(now=now,acquisition_deadline_at=self.acquisition_deadline_at,refresh_interval_seconds=self.refresh_interval_seconds):
            return TemporalRefreshOutcome(status='NO_LAWFUL_REFRESH_WINDOW',reserve_depth_before=reserve_depth,reserve_depth_after=reserve_depth,detail='next canonical DISCOVERY_REFRESH interval is not strictly before acquisition deadline')
        due=parse_iso(now)+timedelta(seconds=self.refresh_interval_seconds)
        ordinal=next_refresh_ordinal(c,campaign_id=self.campaign_id,run_id=self.run_id,cycle_id=self.cycle_id)
        job_name=f'PRE_LIFECYCLE_DISCOVERY_REFRESH:{self.campaign_id}:{self.run_id}:{self.cycle_id}:{ordinal}'
        result,job_id=enqueue_job(c,job_name=job_name,job_kind=JobKind.DISCOVERY_REFRESH,target_table='printer_discovery_batches',scheduled_for=due)
        if job_id is None: return TemporalRefreshOutcome(status=ALREADY_PENDING_REFRESH if result==LockResult.DUPLICATE_ACTIVE_JOB else UNSAFE_SCHEDULER_STATE,reserve_depth_before=reserve_depth,reserve_depth_after=reserve_depth,detail=f'enqueue refused: {result}')
        wait_id=f'prelifecycle-refresh-wait:{self.campaign_id}:{self.run_id}:{self.cycle_id}:{ordinal}'; scheduled=iso(due)
        insert_refresh_wait(c,wait_id=wait_id,campaign_id=self.campaign_id,run_id=self.run_id,cycle_id=self.cycle_id,supervision_id=self.supervision_id,scheduler_job_id=int(job_id),refresh_ordinal=ordinal,scheduled_for=scheduled,acquisition_deadline_at=self.acquisition_deadline_at,now=now); c.commit()
        self._publish(WAITING_FOR_ELIGIBLE_SUPPLY,wait_id=wait_id,scheduler_job_id=int(job_id),refresh_ordinal=ordinal,scheduled_for=scheduled,eligible_reserve_depth=reserve_depth,required_eligible_capacity=required_capacity,acquisition_deadline_at=self.acquisition_deadline_at)
        waiting=TemporalRefreshOutcome(status=WAITING_FOR_ELIGIBLE_SUPPLY,wait_id=wait_id,scheduler_job_id=int(job_id),refresh_ordinal=ordinal,scheduled_for=scheduled,reserve_depth_before=reserve_depth,reserve_depth_after=reserve_depth,detail='pre-lifecycle acquisition waiting for a due Scheduler refresh')
        if self._waiter is None: return waiting
        aborted=bool(self._waiter(max(0.0,(due-parse_iso(now)).total_seconds()))); woke=self._now(scheduled); self._acquisition_mark=woke
        active,cancelled=self._supervision()
        if aborted or not active or cancelled:
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
        self._require_claim(c,int(job_id),job_name,lock_owner); mark_refresh_wait_claimed(c,wait_id=wait_id,now=woke); c.commit()
        refresh_work_id=f'prelifecycle-refresh-work:{self.campaign_id}:{self.run_id}:{self.cycle_id}:{ordinal}'
        try:
            insert_refresh_work(c,refresh_work_id=refresh_work_id,wait_id=wait_id,campaign_id=self.campaign_id,run_id=self.run_id,cycle_id=self.cycle_id,supervision_id=self.supervision_id,scheduler_job_id=int(job_id),refresh_ordinal=ordinal,work_deadline_at=self.work_deadline_at,now=woke); c.commit()
        except Exception as exc:
            fail_job(c,job_id=int(job_id),error='PRE_LIFECYCLE_REFRESH_WORK_OWNERSHIP_FAILED',max_retries=0)
            terminalize_refresh_wait(c,wait_id=wait_id,wait_state='FAILED',first_terminal_cause='PRE_LIFECYCLE_REFRESH_WORK_OWNERSHIP_FAILED',now=woke); c.commit()
            return TemporalRefreshOutcome(status=UNSAFE_SCHEDULER_STATE,wait_id=wait_id,scheduler_job_id=int(job_id),refresh_ordinal=ordinal,scheduled_for=scheduled,claimed=True,reserve_depth_before=reserve_depth,reserve_depth_after=reserve_depth,detail=f'refresh work ownership failed: {type(exc).__name__}')
        try:
            stage=dict(self._refresh_stage(c,campaign_id=self.campaign_id,run_id=self.run_id,cycle_id=self.cycle_id,refresh_work_id=refresh_work_id,discovery_work_id=refresh_work_id,scheduler_job_id=int(job_id),refresh_ordinal=ordinal,source_operations_remaining=source_operations_remaining,now=woke) or {})
        except Exception as exc:
            self._terminalize(c,wait_id,refresh_work_id,int(job_id),False,'PRE_LIFECYCLE_REFRESH_STAGE_FAILED',woke)
            return TemporalRefreshOutcome(status=REFRESH_SOURCE_FAILURE,wait_id=wait_id,scheduler_job_id=int(job_id),refresh_ordinal=ordinal,scheduled_for=scheduled,claimed=True,reserve_depth_before=reserve_depth,reserve_depth_after=reserve_depth,detail=f'refresh stage failed: {type(exc).__name__}')
        ops=int(stage.get('source_operations') or 0); failures=int(stage.get('provider_failures') or 0); unavailable=tuple(str(x) for x in stage.get('channels_unavailable',()))
        if ops>source_operations_remaining:
            self._terminalize(c,wait_id,refresh_work_id,int(job_id),False,'PRE_LIFECYCLE_REFRESH_BUDGET_OVERRUN',woke)
            return TemporalRefreshOutcome(status=SOURCE_BUDGET_EXHAUSTED,wait_id=wait_id,scheduler_job_id=int(job_id),refresh_ordinal=ordinal,scheduled_for=scheduled,claimed=True,source_operations=source_operations_remaining,reserve_depth_before=reserve_depth,reserve_depth_after=reserve_depth,detail='refresh stage exceeded cumulative discovery budget')
        self._terminalize(c,wait_id,refresh_work_id,int(job_id),True,'PRE_LIFECYCLE_REFRESH_COMPLETED',woke)
        self._publish(REFRESH_COMPLETED,wait_id=wait_id,scheduler_job_id=int(job_id),refresh_ordinal=ordinal,source_operations=ops)
        return TemporalRefreshOutcome(status=REFRESH_COMPLETED,wait_id=wait_id,scheduler_job_id=int(job_id),refresh_ordinal=ordinal,scheduled_for=scheduled,claimed=True,source_operations=ops,provider_failures=failures,channels_unavailable=unavailable,channels_attempted=tuple(str(x) for x in stage.get('channels_attempted',())),channels_skipped=tuple(dict(x) for x in stage.get('channels_skipped',()) if isinstance(x,Mapping)),newly_observed_exact_identities=tuple(dict(x) for x in stage.get('newly_observed_exact_identities',()) if isinstance(x,Mapping)),promoted_observation_eligible=tuple(dict(x) for x in stage.get('promoted_observation_eligible',())),reserve_depth_before=reserve_depth,reserve_depth_after=reserve_depth,detail='bounded Source-Governed refresh stage completed')
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

__all__=['PreLifecycleTemporalRefreshError','PreLifecycleTemporalRefreshOwner','REFRESH_WORK_TYPE','bounded_interruptible_wait']
