# Printer V1 — Cycle-2 Pre-Lifecycle Admission / Liveness and Wait-Ownership Audit

Status: **CLOSED PASS**

Audit/readiness verdict:

`V2_9_8B_CYCLE2_PRE_LIFECYCLE_ADMISSION_LIVENESS_WAIT_OWNERSHIP_AUDIT_PASS`

This lane is documentation-only. It does not implement a repair, drain the
surviving `WAITING` row, rerun Printer, prepare an authorization, or mutate
the authoritative database.

Governing prior closeout:

`docs/printer-v1-v2-9-8b-auth-59fdefe7-campaign-closeout.md`

Consumed authorization
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260902T122136Z_59fdefe7` remains
`CONSUMED / CHILD_EXITED_NONZERO / PERMANENTLY NON-REUSABLE`.

## Identity

- branch: `assistant/v2-9-8b-later-cycle-mint-market-replay-repair`
- audited starting HEAD: `758d604fe91726ac6ac0b30f62dada6cc2c6ce8b`
- campaign: `20260902T123958Z-5a3e78f1a7b8-campaign`
- Cycle 2 attempt: `pre-admission:...:c0002`
- proposed Cycle 2: `20260902T123958Z-5a3e78f1a7b8-cycle-2` (never admitted)
- wait:
  `prelifecycle-refresh-wait:...:cycle-2:1`
- wait job: `3548` (`DISCOVERY_REFRESH`, `started_at` null, later `CANCELLED`)
- authoritative DB SHA-256 (unchanged):
  `cd6b1d4ac7171f4096d06c9b09a035a0cf622899806b9a58cc990a2936ad6659`

## Verdicts in one place

| Question | Finding |
|---|---|
| Did the 40-minute deadline exist? | Yes. Absolute, attempt-wide, `evaluated_at + 2400s`. |
| Was it reset/extended? | No durable reset. Wait row and attempt `evaluated_at` stayed original. |
| Did it expire without firing? | Yes. Expired `13:24:59Z`. Owner was never re-entered after wait insert. |
| Freeze-ready ever `>= 4`? | No. Zero Cycle-2 merged candidates. Zero frozen attempt items. |
| Network loss explain Cycle-2 non-admission? | No. Cycle-2 went silent at `12:59:55Z`; 4H transport failures began `14:17:10Z`. |
| Would 2400s still have been violated without the 4H network failure? | Yes. |

## A. The 40-minute deadline existed

Exact source stack:

1. `four_token_operational_composition.PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS = 2400`
2. `exact_operational_policy()["pre_lifecycle_acquisition_duration_seconds"]`
3. frozen authorization `59fdefe7` operational policy field `2400`
4. campaign configuration JSON `pre_lifecycle_acquisition_duration_seconds: 2400`
5. `operational_memory_factory_command._build_pre_lifecycle_temporal_refresh_owner`
   passes `policy.pre_lifecycle_acquisition_duration_seconds`
6. `compose_owner` sets
   `acquisition_deadline_at = acquisition_deadline_at(owner_evaluated_at, 2400)`
   and `acquisition_started_at = owner_evaluated_at`
7. later-cycle `for_cycle(..., evaluated_at=..., cooperative_yield=True)`
8. wait insert copies `self.acquisition_deadline_at` into
   `printer_pre_lifecycle_discovery_refresh_waits.acquisition_deadline_at`

Scope: **attempt-wide / owner-instance-wide**, not campaign-wide. Cycle 1
campaign-start `now` was `12:39:59.030485Z`. Cycle 2 attempt
`evaluated_at` / `cycle_cutoff` is `12:44:59.121086Z` (the 300-second
admission-spacing boundary). Deadline:

`12:44:59.121086Z + 2400s = 13:24:59.121086Z`

That exact value is on the wait row. Refresh ordinal 1 is anchored at
`acquisition_started_at + 600s = 12:54:59.121086Z` (`JobKind.DISCOVERY_REFRESH`
interval is 600s). Job `3548.scheduled_for` matches that due time.

`work_deadline_at` is a separate shared envelope:
initial evaluated_at + 2400 + 18000. Rebind forbids
`acquisition_deadline_at >= work_deadline_at` but does **not** require the
rebound acquisition deadline to equal the previous one.

## B. Deadline was not reset

Durable evidence:

- attempt `evaluated_at` remained `12:44:59.121086Z`
- wait `acquisition_deadline_at` remained `13:24:59.121086Z`
- no second wait row, no second attempt, no second refresh ordinal

In-memory later-cycle progress, when present, reuses
`progress["refresh_owner"]` and therefore the original deadline. A fresh
`for_cycle(evaluated_at=now)` on a call without progress *could* compute
`now+2400`, but after wait insert there is no durable sign of such a rebind:
no new wait, no claim, no new source requests, no updated attempt
`evaluated_at`.

Hypothesis “deadline was reset to `now+2400` on cooperative resume” is
**not proven**. The 77-minute overstay is an **enforcement** failure of the
original absolute deadline.

## C. Deadline expired and did not fire

`PreLifecycleTemporalRefreshOwner._request` enforces the deadline only inside
that function:

1. New wait eligibility: `now >= deadline` → `ACQUISITION_DEADLINE_EXHAUSTED`
   (does not apply when a pending wait already exists).
2. New wait due-time: `due >= deadline` → `NO_LAWFUL_REFRESH_WINDOW`.
3. After waiter / on resume once `now >= due`:
   `woke >= deadline` → `_abandon(..., PRE_LIFECYCLE_ACQUISITION_DEADLINE_EXHAUSTED)`.

Cooperative later-cycle rebind sets `_waiter = None`. On first insert:

```text
insert WAITING wait + enqueue job
if self._waiter is None: return waiting   # no claim, no deadline check
```

This campaign inserted the wait at `13:00:00.953733Z` when due was already
`12:54:59Z` (five minutes past). Cooperative mode returned `WAITING` without
claiming job `3548`. `started_at` is still null.

Resume path:

```text
if pending wait and now < due: return waiting   # no deadline check
woke = now
if woke >= deadline: abandon DEADLINE_EXHAUSTED
else claim job
```

After `13:00:00Z`, `now >= due`, so the next `_request` would have claimed or
deadline-exhausted. **That next `_request` never happened.**

There is no Scheduler consumer that terminalizes a due `DISCOVERY_REFRESH`
wait by itself. Deadline checking does not run after the waiter in this
campaign because there was no waiter. Repeated refresh scheduling cannot
extend the durable deadline; the owner simply never ran again.

Waiter vs remaining budget (non-cooperative, not this run): waiter is
`(due - now)` seconds, not `min(due-now, remaining-to-deadline)`. Overshoot is
handled only after wake. Cooperative mode does not wait at all.

## Why Cycle 2 was never re-entered after the wait

`_run_four_token_admission_boundary` calls `later_cycle_callback` only when
disposition is `CYCLE_ADMISSION`, and then only if
`_later_cycle_acquisition_deadline_conflict` is false:

`now + later_cycle_acquisition_quantum_seconds >= next_due_lifecycle_work`

After `waiting_for_refresh` with `refresh_ordinal=1`,
`_next_later_cycle_quantum_kind` returns `PERSISTED_REFRESH`.
Worst-case seconds = `7 * 5.0 + 4 * 20.0 = 115s`.

At wait insert `13:00:00.953733Z` the next Cycle-1 1H snapshot was
`t1_continuation_snapshot_03` scheduled `13:01:28.610521Z` (87.7s later).
`13:00:00 + 115s = 13:01:55 >= 13:01:28` →
`LIFECYCLE_DEADLINE_PROTECTS_CADENCE`. Callback skipped.

1H snapshot pairs remain ~2 minutes apart. After each pair finishes, remaining
time to the next due snapshot is ~90s, still less than 115s. The conflict
stays true through 1H and 4H. Durable proof: attempt evidence has **no event
after `12:59:55.211873Z`** until parent-interrupt cancel at `14:17:31.732819Z`.

The factory loop therefore treated Cycle-2 acquisition as parked while Cycle 1
lifecycle occupied the process. The 2400s deadline is not a factory-loop wake
bound.

## D–E. Freeze-ready depth never reached 4

Required rule remains `4 freeze-ready -> 2 selected + 2 report-only`.

Cycle 2 durable inventory:

- discovery batches for Cycle 2: **0**
- merged candidates with `cycle_id=...-cycle-2`: **0**
- frozen attempt items: **0**
- Cycle-2 exhaustion certificate: **none**
- two eligible-reserve rows last-validated at mint-batch time
  `12:57:55.615798Z` by this campaign, both `ELIGIBLE_STALE`:
  `12u9FULaUfHD8uHHe98Fz5gdhg8qeX6DyV93B3Dtpump`,
  `CrR3AB6W9v2RV9btV9Egqsdij3jXNUSJba9dqKAqpump`

`ELIGIBLE_STALE` is not freeze-ready. Retained rows do not count until
revalidation. No Cycle-2 candidate identities were frozen. Freeze-ready depth
never durably reached 4. Selection/admission therefore never had a lawful pair.

That is **not** proven honest market scarcity. Cycle 2 stopped after 11
cooperative source requests and entered a refresh wait whose job was never
claimed. The refresh that exists to revalidate retained rows and look for new
freeze-ready identities did not run. Labeling this `SOURCE_SCARCITY` would
hide the liveness defect.

Provider note during Cycle 2 itself: one GeckoTerminal rate-limit
(`source_failure 401`, request `4567`) at `12:46:10Z`. Cycle 2 continued
through protocol/migration and later mint-batch-r1. That rate-limit is not
the terminal cause.

## F. Cycle 1 versus Cycle 2

| Stage | Cycle 1 | Cycle 2 |
|---|---|---|
| Owner construction | campaign-start `12:39:59Z` | later-cycle `for_cycle` at `12:44:59Z`, `cooperative_yield=True` |
| Deadline | not used as Cycle-1 wait | attempt-start + 2400s = `13:24:59Z` |
| Discovery batch | created; 8 discovery work rows succeeded | none |
| Freeze-ready | exhaustion cert `eligible_reserve_count=6` (`>=4`) | never certified; 0 merged |
| Selection | 2 selected, 0 alternates | never |
| Admission | yes, two slots | no |
| Source path | opening discovery then lifecycle snapshots | 12 cooperative claims interleaved with Cycle 1 |
| Waiter | N/A | `_waiter=None` |
| After insufficient depth | N/A | insert wait and park |

Disjointness is required for Cycle 2 and does not by itself explain zero
merged candidates: the two STALE reserve mints are not the Cycle-1 admitted
identities.

## G. Historical Cycle-2 comparison

Successful Cycle-2 admissions exist (`CONSUMED` / `EXACT_PAIR_FROZEN`) with
attempt durations ~11–13 minutes, finishing before a parked wait was needed.

The only prior wait row (Aug-17 `6941aae86dd4`) was **claimed at due time**
and `FAILED` `PRE_LIFECYCLE_REFRESH_STAGE_FAILED` 10 minutes after insert,
still before its `10:56:15Z` deadline. That wait did not overstay 2400s.

Aug-27 `22f4d5da4137` Cycle 2 terminalized `NO_PAIR` /
`DURATION_EXHAUSTION` after ~56 minutes and wrote an exhaustion certificate.
That is a different terminal owner (attempt terminalized, no surviving
`WAITING` row).

This 77-minute `WAITING` row with an unclaimed due job is **new** relative to
the durable wait table. It is not how prior successful Cycle-2 admissions
behaved.

## Exact Cycle-2 chronology

Acquisition start `T0 = 2026-09-02T12:44:59.121086Z`.
Expected expiry `T0+2400s = 13:24:59.121086Z`.

| UTC | Elapsed | Claim | Phase / action | Deadline | Freeze-ready | Why not admitted |
|---|---|---|---|---|---|---|
| 12:44:59 | 0s | 1 | AUXILIARY_FRESH_INTAKE; req 4558–4559 | 13:24:59 | unknown, not 4 | cooperative yield |
| 12:45:09–12:46:04 | 10–65s | 2–7 | AUXILIARY_LIQUIDITY_BACKUP; req 4560–4567; 4567 GT rate-limit | 13:24:59 | not 4 | yield |
| 12:46:49 | 110s | 8 | AUXILIARY_PROTOCOL_CONFIRMATION; req 4570 | 13:24:59 | not 4 | yield |
| 12:46:57 | 118s | 9 | DIRECT_MIGRATION; req 4571 | 13:24:59 | not 4 | yield |
| 12:46:57–12:57:55 | 11 min gap | — | Cycle 1 `WINDOW_15M` close (`12:56:09Z`) | 13:24:59 | — | factory doing Cycle 1 |
| 12:57:55 | 776s | 10 | MARKET_DISCOVERY mint-batch-r1 req 4606; two reserve rows STALE | 13:24:59 | not 4 | yield |
| 12:58:03 | 784s | 11 | MARKET_DISCOVERY yield, still 11 requests | 13:24:59 | not 4 | yield |
| 12:59:55 | 896s | 12 | `WAITING_FOR_ELIGIBLE_SUPPLY` | 13:24:59 | not 4 | wait entered |
| 13:00:00 | 902s | — | wait row + job 3548 inserted; due already 12:54:59; waiter None; return | 13:24:59 | not 4 | parked |
| 13:01:28 | 989s | — | next Cycle-1 1H snapshot due; 115s quantum conflicts (87s remain) | 13:24:59 | — | callback skipped |
| **13:24:59** | **2400s** | **—** | **deadline expires; owner not in `_request`; wait still WAITING; job PENDING unclaimed** | **expired** | **not 4** | **enforcement not invoked** |
| 13:24:59–14:17:10 | 2400–5531s | — | Cycle 1 1H then 4H snapshots | expired | not 4 | still parked |
| 14:17:10–14:17:25 | ~5531s | — | Cycle 1 4H DexScreener/GT transport failures | expired | — | unrelated later |
| 14:17:31.732 | 5552s | — | parent-interrupt CANCELLED attempt + job 3493 | expired | — | wait row not touched |
| 14:17:31.757 | 5552s | — | outer reconcile CANCELLED job 3548 | expired | — | wait row still WAITING |

## Network-outage separation

Cycle 1 `WINDOW_4H` snapshot-012 transport/no-route failures start
`14:17:10.673126Z`. Cycle 2’s last acquisition action is `12:59:55.211873Z`.
No Cycle-2 source request after that. Laptop/network loss can explain the
later Cycle-1 4H failures. It does not explain Cycle-2 non-admission or the
missed `13:24:59Z` deadline.

**Would Cycle 2 still have violated 2400s if the Cycle-1 network failure never
happened?** Yes. The deadline was already missed at `13:24:59Z` while Cycle 1
1H snapshots were succeeding. Absent the 4H network failure, Cycle 1 would
have continued 4H collection and Cycle 2 would have remained parked longer.

## Wait-row ownership contract

Creator: `PreLifecycleTemporalRefreshOwner._request` → `insert_refresh_wait`
plus `enqueue_job(DISCOVERY_REFRESH)`.

Terminal owner: same module, `_abandon` / `_terminalize` →
`terminalize_refresh_wait` to `SUCCEEDED` / `FAILED` / `CANCELLED`.
`cancel_pending_wait` exists on the owner.

Who should terminalize:

| Event | Lawful owner | This run |
|---|---|---|
| Deadline reached | `_request` resume/wake `_abandon` | never invoked |
| Successful refresh | `_terminalize` SUCCEEDED | never claimed |
| Refresh stage failure | `_terminalize` FAILED | n/a |
| Supervision/cancel | `_abandon` CANCELLED | n/a (no waiter, no re-entry) |
| Parent safe-stop / campaign failure | missing | attempt+job 3493 cancelled; wait row left `WAITING`; job 3548 cancelled later without `terminalize_refresh_wait` |

`reconcile_parent_interrupted_open_pre_admission_attempts` owns the
pre-admission attempt and job `3493` only. Unified terminal closure has no
wait-table producer. Outer `reconcile_campaign_terminal` cancelled job `3548`
and left the wait row `WAITING`. That confirms
`PRE_LIFECYCLE_TERMINAL_CLEANUP_ORDERING_OR_OWNERSHIP_DEFECT`.

## Official zero-state gap

Official `project_four_token_proof_zero_state` counts
`printer_pre_lifecycle_discovery_refresh_work` rows in `RUNNING` only.
It does not count `printer_pre_lifecycle_discovery_refresh_waits`.

`campaign_active_work_report` does count `WAITING`/`CLAIMED` waits and is why
shared terminal raised.

This is not an intentional “waits are historical residue” contract:
`WAITING` is defined as active ownership, and shared terminal already requires
zero waits. The official gate omitted the wait table after DTW98 wait
persistence. Classification: same ownership-family committed gap, not a third
unrelated product. Design must decide whether official zero-state projects
active waits. No implementation here.

## Classifications

### Cycle-2 admission / liveness

`COMMITTED_CODE_DEFECT`

Subtype:

`LATER_CYCLE_PRE_LIFECYCLE_ACQUISITION_DEADLINE_ENFORCEMENT_DEFECT`

The suggested `...PROPAGATION_OR_ENFORCEMENT...` name is half-right.
Propagation of the original absolute deadline is proven intact. Enforcement
is proven broken: cooperative insert returns without claim/deadline check
when due is already past, and the factory loop never re-enters `_request`
while Cycle-1 lifecycle work makes a 115s persisted-refresh quantum miss the
next snapshot due time.

Not `SOURCE_SCARCITY`, not `EXPECTED_DURATION_EXHAUSTION` (the exhaustion
owner never ran), not `PROVIDER_LIMITATION` for Cycle-2 non-admission.

### Refresh-wait cleanup

Confirmed:

`COMMITTED_CODE_DEFECT` /
`PRE_LIFECYCLE_TERMINAL_CLEANUP_ORDERING_OR_OWNERSHIP_DEFECT`

### Zero-state coverage

`COMMITTED_CODE_DEFECT` /
`OFFICIAL_ZERO_STATE_OMITS_ACTIVE_PRE_LIFECYCLE_REFRESH_WAITS`

Same family as wait ownership, not a separate product lane.

## Code seams for the later design

1. `pre_lifecycle_persistent_refresh_owner.py` `_request`: cooperative
   `waiter is None` return after insert; resume deadline check only if
   re-entered; insert allowed when due is already past.
2. `one_command_15m_factory.py` `_later_cycle_acquisition_deadline_conflict`
   + `_run_four_token_admission_boundary`: 115s persisted-refresh quantum vs
   Cycle-1 snapshot cadence; acquisition deadline is not a wake bound.
3. `authoritative_live_operational_campaign.py` later-cycle progress
   `waiting_for_refresh` short path: never reached after `13:00:00Z`.
4. `reconcile_parent_interrupted_open_pre_admission_attempts`: no wait-row
   consumer.
5. `four_token_proof_zero_state_gate.py`: no wait-table domain.

Code change is justified. This lane does not implement it.

## Exact next permitted lane

```text
LATER-CYCLE PRE-LIFECYCLE DEADLINE ENFORCEMENT AND WAIT OWNERSHIP — DESIGN / SPECIFICATION ONLY
```

Follow:

```text
audit/readiness -> design/specification -> implementation if approved -> bounded proof/test -> closeout
```

This document is the audit/readiness. Do not implement. Do not drain the
surviving wait. Do not prepare another authorization. Do not rerun
`59fdefe7`.

`V2_9_8B_CYCLE2_PRE_LIFECYCLE_ADMISSION_LIVENESS_WAIT_OWNERSHIP_AUDIT_PASS`
