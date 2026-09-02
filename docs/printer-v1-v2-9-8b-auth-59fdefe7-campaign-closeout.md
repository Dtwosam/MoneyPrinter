# Printer V1 — V2-9.8B Authorization 59fdefe7 Campaign Closeout

Status: **CLOSED BLOCKED**

Evidence-audit verdict:

`V2_9_8B_AUTH_59FDEFE7_POST_APPLICATION_EVIDENCE_AUDIT_PASS`

Closeout verdict:

`V2_9_8B_AUTH_59FDEFE7_CAMPAIGN_CLOSEOUT_BLOCKED`

Blocker:

`UNDRAINED_CURRENT_ATTEMPT_PRE_LIFECYCLE_REFRESH_WAIT`

Primary classification:

`COMMITTED_CODE_DEFECT`

Subtype:

`PRE_LIFECYCLE_TERMINAL_CLEANUP_ORDERING_OR_OWNERSHIP_DEFECT`

This closeout is documentation/governance only. It does not repair production
code, drain the remaining wait, reuse the consumed authorization, run Printer,
restore the pre-run database, modify the application marker, or prepare another
authorization.

## Exact execution identity

- authorization: `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260902T122136Z_59fdefe7`
- frozen authorization SHA-256: `fcfa2d6cd0dfdb8f19c8482ace1b4c4c4b1b84b8283862ee8c4e90be74787b19`
- authorization state: `CONSUMED / CHILD_EXITED_NONZERO / PERMANENTLY NON-REUSABLE`
- authorized branch: `assistant/v2-9-8b-later-cycle-mint-market-replay-repair`
- authorized / actual execution HEAD: `83a6ef964e7289ca17c9c1a600758ffdb5e9f752`
- wrapper execution: `20260902T123958Z-5a3e78f1a7b8`
- campaign: `20260902T123958Z-5a3e78f1a7b8-campaign`
- run: `20260902T123958Z-5a3e78f1a7b8-campaign-run`
- Cycle 1: `20260902T123958Z-5a3e78f1a7b8-cycle`
- proposed Cycle 2: `20260902T123958Z-5a3e78f1a7b8-cycle-2` (never admitted as a campaign cycle row)
- supervision: `20260902T123958Z-5a3e78f1a7b8-supervision`
- factory run: `7b492361-03ee-4ec2-8b54-89a41612cf8e`
- configuration: `20260902T123958Z-5a3e78f1a7b8-configuration`
- child PID: `11233`
- child result: `CHILD_EXITED_NONZERO`
- process exit: `1`
- wrapper `success`: `false`
- wrapper `terminal_classification`: `CHILD_EXITED_NONZERO`
- child `status` / `terminal_category`: `OPERATIONAL_COMMAND_BLOCKED`
- retries / reruns / resumes / restarts / successors: all `0`
- child-terminal source calls: `157`
- child-terminal scheduler runtime calls: `0` (reconstruction-hardcoded; not live observer proof)
- child-terminal database_writes: `6` (mutation-recorder campaign-identity count, not all SQLite writes)
- child-terminal `lifecycle_started`: `null` (reconstruction label; durable lifecycle did start)
- child-terminal `failure_phase`: `CAMPAIGN_PRE_LIFECYCLE` (reconstruction label; see ordering)
- child-terminal `terminal_truth_status`: `RECONSTRUCTED`
- child-terminal `secondary_terminal_truth_error`: `null`
- child-terminal `terminal_report_path`: `null`
- factory `final_report_json`: `null`
- reports directory: empty

The authorization is permanently consumed. It must not be retried, rerun,
resumed, restarted, reused, or treated as successor authority. It must enter
every future prior-authorization non-reuse trust root. That future complete
root is 59 IDs.

## Application / authorization evidence

Marker path:

`/Users/Dtwo1/PrinterOperations/v2-9-8/four-token-standard-four-hour-one-shot-applications/V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260902T122136Z_59fdefe7/application-marker.json`

Independently verified and not modified:

- marker exists; SHA-256 `55fc36e3ee5fd7407c4066ea6d915f531c20ba927126d038dd18cf295e262404`;
- authorization SHA-256 matches the frozen package
  `fcfa2d6cd0dfdb8f19c8482ace1b4c4c4b1b84b8283862ee8c4e90be74787b19`;
- wrapper manifest SHA-256 `006b18a73e3887a55958f9a12aa577c299adc5464e96cd40c1c9400f59c22362`;
- child-terminal SHA-256 `0839682e2705f0a2b3dd379218cc00cad81cd539e7ba837b09bc8d600cc6639b`;
- child-stderr SHA-256 `b55f44c53d59c064d0ef29d39ed4196db2e4cd103534034307fac0b62beba1e2`;
- wrapper-terminal SHA-256 `f36138c2576da0613c42c7cf584d2722d1301e4dfe5b487e0159da70a6630969`;
- exactly one application; `allowed_invocation_count = 1`;
- marker consumed at `2026-09-02T12:39:55.336149+00:00`;
- repository HEAD binding `83a6ef964e7289ca17c9c1a600758ffdb5e9f752`;
- retry/rerun/resume/restart/successor all forbidden and all observed `0`.

Pre-application wrapper zero-state gate: `zero_state_ready = true`, every
canonical domain `0`, integrity `ok`, FK `0`, migration `62` /
`062_pre_admission_attempt_evidence.sql`, printer processes `0`, sidecars
none.

## Report path / SHA

No campaign report was written.

- `terminal_report_path = null`
- `terminal_report_sha256 = null`
- `reports/` is empty
- terminal-summary
  `/Users/Dtwo1/PrinterOperations/v2-9-8/20260902T123958Z-5a3e78f1a7b8/terminal-summary.json`
  SHA-256 `d9b3929e3bca6f43e667d35b651e64d91bda8328a9947fac7768094e61f9df09`
- terminal-summary `report_written = false`
- terminal-summary `report_block_reason = SIX_UNIT_EVIDENCE_MISSING`
- terminal-summary `accounting_status = SIX_UNIT_ACCOUNTING_BLOCKED`
- accounting block reason:
  `OPERATIONAL_STAGE_FAILED_BEFORE_ACCOUNTING_COMPLETION`

`terminal_report_path = null` because shared-terminal Phase B raised before the
factory persisted `final_report_json` and before the six-unit report owner
could write a campaign report. The exception path reconstructed terminal truth
instead of emitting the normal report artifact.

## Post-campaign authoritative DB

Path: `data/printer_v1.sqlite3`

Fresh identity, byte-identical to the child-terminal `database_identity_after`:

- SHA-256: `cd6b1d4ac7171f4096d06c9b09a035a0cf622899806b9a58cc990a2936ad6659`
- size: `158408704`
- inode: `1230526`
- mtime_ns: `1788358651758295845`
- migration count/head: `62` / `062_pre_admission_attempt_evidence.sql`
- integrity: `ok`
- foreign-key violations: `0`
- journal mode: `delete`
- sidecars: none

Pre-run DB SHA-256 was
`a3172e04f99ef410ba66eb4e2928b5b4edbdd7dfad4d713fcd1605fa3b702a8c`
(size `154796032`, mtime_ns `1788310792540112946`). Campaign writes were
authorized. Do not restore the pre-run database.

This post-campaign identity is the historical baseline from this closeout
forward, including the undrained wait identified below.

## Raise site

Child-stderr is not a Python traceback. It is the reconstructed JSON exception
envelope printed by `operational_memory_factory_command.main()` after the
factory exception escaped. That is why
`terminal_truth_status = RECONSTRUCTED`.

Exact raise:

- file: `src/printer_v1/operator_cli/four_token_factory_adapter.py`
- function: `finalize_four_token_shared_terminal`
- lines: `1655-1658`
- message: `shared terminal requires zero active or orphan campaign work`
- caller: `src/printer_v1/operator_cli/one_command_15m_factory.py` Phase B
  (`phase_b = finalize_four_token_shared_terminal(...)`)
- consulted function: `campaign_active_work_report` in
  `src/printer_v1/operator_cli/campaign_active_work.py`

The `otherwise_clean` predicate requires all of:

- `active_jobs == 0`
- `active_work_rows == 0`
- `terminal_work_with_active_job == 0`
- `pending_or_running_run_steps == 0`
- `active_pre_lifecycle_refresh_waits == 0`
- `active_pre_admission_attempts == 0`

A false `otherwise_clean` raises at lines `1656-1658` before the shared
terminalizer runs.

## Exact offending durable state

Table: `printer_pre_lifecycle_discovery_refresh_waits`

Primary key:

`prelifecycle-refresh-wait:20260902T123958Z-5a3e78f1a7b8-campaign:20260902T123958Z-5a3e78f1a7b8-campaign-run:20260902T123958Z-5a3e78f1a7b8-cycle-2:1`

At failure time and still now:

- `wait_state = WAITING`
- `refresh_ordinal = 1`
- `campaign_id` / `run_id` = this attempt
- `cycle_id = 20260902T123958Z-5a3e78f1a7b8-cycle-2` (proposed Cycle 2; no
  admitted `printer_memory_factory_campaign_cycles` row)
- `supervision_id = 20260902T123958Z-5a3e78f1a7b8-supervision`
- `scheduler_job_id = 3548`
- `scheduled_for = 2026-09-02T12:54:59.121086+00:00`
- `acquisition_deadline_at = 2026-09-02T13:24:59.121086+00:00`
- `created_at = 2026-09-02T13:00:00.953733+00:00`
- `updated_at = 2026-09-02T13:00:00.953733+00:00`
- `terminal_at = null`
- `first_terminal_cause = null`

Linked Scheduler job `3548`:

- `job_kind = DISCOVERY_REFRESH`
- `job_name = PRE_LIFECYCLE_DISCOVERY_REFRESH:...cycle-2:1`
- created `2026-09-02 13:00:00`
- cancelled later during outer reconstruction cleanup at
  `2026-09-02T14:17:31.757486+00:00`
- current status: `CANCELLED`, unlocked

Canonical accounting treats the wait as active because
`wait_state IN ('WAITING','CLAIMED')`, independent of job status. After outer
cleanup the job is terminal and the wait row is not: that is orphan wait
ownership.

This wait was created by this authorized attempt. It did not exist at
pre-application zero-state. The only other wait row in the database is
historical `FAILED` residue from campaign
`20260817T101114Z-6941aae86dd4-campaign` and is not this offender.

`finalize_four_token_shared_terminal` calls `campaign_active_work_report` with
`campaign_id` and `run_id` but no `cycle_id`. The wait matches on campaign/run
even though its `cycle_id` is the unadmitted proposed Cycle 2.

Linked Cycle-2 pre-admission attempt (terminalized during Phase B start, before
the raise):

- `attempt_id = pre-admission:...:c0002`
- `proposed_cycle_ordinal = 2`
- `proposed_cycle_id = 20260902T123958Z-5a3e78f1a7b8-cycle-2`
- `scheduler_job_id = 3493` (`PRE_ADMISSION_DISCOVERY_SELECTION`)
- current `attempt_state = CANCELLED`
- `first_terminal_cause = PARENT_CAMPAIGN_INTERRUPTED:SAFE_STOP_PREFLIGHT_FAILED`
- `terminal_at = 2026-09-02T14:17:31.732819+00:00`
- `consumed_cycle_id = null`

Parent-interrupt cleanup owns the attempt and job `3493` only. It does not
read, cancel, or terminalize `printer_pre_lifecycle_discovery_refresh_waits`
or wait job `3548`. Unified terminal closure has no wait-table producer.

## Exact shared-terminal active-work report

No in-memory snapshot was persisted at the raise instant. Two durable reports
bound it.

Outer reconstruction `reconcile_campaign_terminal` report in
`terminal-summary.json`, after attempt cancel and during/after job `3548`
cancel:

- `active_jobs = 0`
- `active_work_rows = 0`
- `terminal_work_with_active_job = 0`
- `pending_or_running_run_steps = 0`
- `active_pre_admission_attempts = 0`
- `active_pre_lifecycle_refresh_waits = 1`
- `clean_terminal = false`
- attributable jobs: factory steps `220`, discovery `8`, campaign scheduler
  work `230`, wait jobs `1`, refresh work `0`, pre-admission jobs `0`
- jobs_by_status: `SUCCEEDED 124`, `CANCELLED 105`, `FAILED 2`

Job `3548` `finished_at` is `14:17:31.757486`, after cycle terminal
`14:17:31.694004`, attempt cancel `14:17:31.732819`, and campaign terminal
`14:17:31.742503`. At the raise instant job `3548` was therefore still
non-terminal, so `active_jobs` was also likely `1` in addition to
`active_pre_lifecycle_refresh_waits = 1`. Either count makes
`otherwise_clean` false. The wait row is the count that remains nonzero.

Fresh post-audit `campaign_active_work_report` on the authoritative DB, scoped
to this factory/campaign/run, still returns
`active_pre_lifecycle_refresh_waits = 1` and `clean_terminal = false`.

## Original operational cause versus shared-terminal raise

The shared-terminal exception is a **secondary failure during attempted safe
stop**. It is not the original operational initiator.

Original lifecycle-stop facts, preserved on token-local rows:

1. Cycle 1 token 111 / pair 115 `WINDOW_4H` snapshot `t111_p115_4h_snapshot_012`
   failed at `2026-09-02T14:17:12.082579+00:00` with
   `dexscreener_transport_failure`. Source failure `402`: DexScreener
   `pair_market_snapshot` `<urlopen error timed out>`. Fallback source failure
   `403`: GeckoTerminal `<urlopen error [Errno 65] No route to host>`.
2. Cycle 1 token 112 / pair 116 `WINDOW_4H` snapshot `t112_p116_4h_snapshot_012`
   failed at `2026-09-02T14:17:25.090643+00:00` with
   `dexscreener_transport_failure`. Source failure `404`: DexScreener
   `<urlopen error [Errno 65] No route to host>`. Fallback `405`: GeckoTerminal
   same `No route to host`.

Slot rows preserve `FAILED` / `dexscreener_transport_failure`. Window rows
preserve `WINDOW_4H` `BLOCKED` / `dexscreener_transport_failure`. Remaining 4H
steps were `TOKEN_LOCAL_CANCELLED_AFTER_FAILURE`.

The factory outer handler then mapped the escaped orchestration exception to
generic `SAFE_STOP_PREFLIGHT_FAILED` (`STOP_PREFLIGHT`). Phase A wrote that
generic cause onto the Cycle 1 row. Phase B then raised the shared-terminal
adapter error because the Cycle-2 wait was still `WAITING`. The command
exception envelope replaced first-cause text with
`FourTokenFactoryAdapterError:shared terminal requires zero active or orphan campaign work`.
Outer initialized-failure cleanup wrote campaign/run/supervision first cause
`OPERATIONAL_CAMPAIGN_FAILED:FourTokenFactoryAdapterError`.

Cause preservation:

| Surface | First cause | Preserved? |
|---|---|---|
| Cycle 1 slots / `WINDOW_4H` windows / failed factory steps | `dexscreener_transport_failure` | yes |
| Cycle 1 row | `SAFE_STOP_PREFLIGHT_FAILED` | generic factory mapping |
| Cycle-2 pre-admission attempt | `PARENT_CAMPAIGN_INTERRUPTED:SAFE_STOP_PREFLIGHT_FAILED` | derived from cycle cause |
| Campaign / run / supervision | `OPERATIONAL_CAMPAIGN_FAILED:FourTokenFactoryAdapterError` | secondary overwrite |
| Child terminal / wrapper | `FourTokenFactoryAdapterError:shared terminal requires zero active or orphan campaign work` | reconstructed exception |

## Cleanup ordering reconstruction

```text
application-marker consume
  -> child four-token-standard-four-hour-run
  -> campaign/run/cycle-1/supervision/configuration insert (12:39:59)
  -> Cycle 1 discovery/selection; two tokens admitted (12:40:17)
  -> WINDOW_15M collection; both CLEAN_PROMOTED (12:56:09)
  -> Cycle 2 pre-admission attempt created RUNNING (12:44:59) during Cycle 1
  -> Cycle 2 locator / new-pools / liquidity-backup / protocol / mint-batch-r1
  -> Cycle 2 pre-lifecycle refresh wait + job 3548 inserted WAITING (13:00:00)
  -> WINDOW_1H collection; both CLEAN_PROMOTED (~13:41)
  -> WINDOW_4H collection starts
  -> snapshot 012 DexScreener/GeckoTerminal transport failures (14:17:10-14:17:25)
  -> both slots FAILED; remaining 4H steps TOKEN_LOCAL_CANCELLED_AFTER_FAILURE
  -> factory except maps to SAFE_STOP_PREFLIGHT_FAILED
  -> Phase A: Cycle 1 TERMINAL_STOPPED at 14:17:31.694
  -> Phase B start: parent-interrupt CANCELLED attempt + job 3493 at 14:17:31.732
  -> Phase B: campaign_active_work_report sees WAITING wait (and likely PENDING job 3548)
  -> raise at four_token_factory_adapter.py:1656
  -> factory final_report_json never written; campaign report never written
  -> command main reconstructs JSON envelope (RECONSTRUCTED)
  -> outer cleanup: campaign/run/supervision TERMINAL_FAILED at 14:17:31.742
  -> outer reconcile cancels job 3548 at 14:17:31.757; wait row remains WAITING
```

`lifecycle_started = null` and `failure_phase = CAMPAIGN_PRE_LIFECYCLE` are
reconstruction labels. Child-terminal envelope construction treats missing
`lifecycle_started` / missing `factory_run_id` as pre-lifecycle. Durable
windows, snapshots, and factory steps prove Cycle 1 lifecycle started and
reached `WINDOW_4H`.

`scheduler_runtime_calls = 0` is hardcoded in the reconstruction envelope. It
is not proof that no Scheduler jobs existed. Durable evidence created 232
Scheduler jobs for this attempt (`printer_scheduler_jobs` `3444 -> 3676`).

`database_writes = 6` is the mutation-recorder campaign-identity count
(campaign, run, cycle, configuration inserts plus campaign/run updates), not
the full table delta. Net inserts include 157 source requests, 232 Scheduler
jobs, 222 factory steps, 230 campaign scheduler-work rows, 2 tokens, 2 pairs,
2 slots, 6 campaign windows, and the Cycle-2 wait.

## Pre-application zero-state versus this attempt

Wrapper zero-state passed with every canonical domain `0`. The offending wait
did not exist then. It was created at `13:00:00` by this attempt.

The official zero-state gate still does not count
`printer_pre_lifecycle_discovery_refresh_waits`. It only counts
`printer_pre_lifecycle_discovery_refresh_work` rows in `RUNNING`. That is why
the wait can remain `WAITING` while official domains read zero. This is not
pre-existing residue hidden from preflight at application time. It is
current-attempt residue that the official gate does not project.

## Post-run official zero-state versus remaining active wait

Official `project_four_token_proof_zero_state` domains are all `0`:

- active campaigns / runs / cycles / campaign scheduler work = 0
- campaign supervision ACTIVE/STOPPING = 0
- proof supervision = 0
- active discovery work = 0
- active factory runs / steps = 0
- non-terminal pre-admission attempts = 0
- active pre-lifecycle refresh **work** = 0
- active Scheduler jobs = 0

Also verified:

- locked Scheduler jobs = 0
- live Printer process = 0
- DB holders (`lsof`) = 0
- campaign lease lock absent
- sidecars none
- candidate-acquisition leases for this execution: none
- tracking queues `104` / `105`: `COOLDOWN`

Canonical campaign-scoped active-work report is **not** clean:

- `active_pre_lifecycle_refresh_waits = 1`
- `clean_terminal = false`

Closeout is BLOCKED because that wait remains `WAITING`. This lane does not
manually terminalize it.

## Cycle 1 actual result

Cycle 1 was created, selected, and admitted. Two concurrent slots. Lifecycle
started.

Selected identities:

1. mint `5EHz51kdjgqmq7SH287DihsKZ2GkjziWLUpfpdrVpump` / pool
   `Bc41Ped2cpQyzFvFUzsTN9Rkq3Ggcsav4JjGyYfLWdvr` / token `111` / pair `115`
   / slot `slot-...-cycle-1` / tracking `104`
2. mint `Gffw364rz4r93aYum3BHynoi5iw1gsq2m4P2Py6gpump` / pool
   `9Ngg8wNFYCDo7vakY6kW65jcANh28xnparXgpwBH8AkQ` / token `112` / pair `116`
   / slot `slot-...-cycle-2` / tracking `105`

No durable report-only alternates. Selection batches:

- discovery batch selected count `2`, rejected `0`, candidate pool `0`
- origin-activated batch candidate pool `2`, selected `2`, rejected `0`

Window results:

| Slot | WINDOW_15M | WINDOW_1H | WINDOW_4H |
|---|---|---|---|
| cycle-1 | CLEAN_PROMOTED / memory `266` PARTIAL_MEMORY coverage pass | CLEAN_PROMOTED / memory `270` PARTIAL_MEMORY coverage pass | BLOCKED `dexscreener_transport_failure`; no memory window |
| cycle-2 | CLEAN_PROMOTED / memory `267` PARTIAL_MEMORY coverage pass | CLEAN_PROMOTED / memory `271` PARTIAL_MEMORY coverage pass | BLOCKED `dexscreener_transport_failure`; no memory window |

This is not a four-token campaign success and not a through-4h success.

Factory run: `SAFE_STOPPED` / `SAFE_STOP_PREFLIGHT_FAILED` /
`finished_at = 2026-09-02T14:17:31.753529+00:00` / `final_report_json` null.

Factory steps: `SUCCEEDED 118`, `CANCELLED 102`, `FAILED 2`.
Campaign scheduler work: `SUCCEEDED 124`, `CANCELLED 104`, `FAILED 2`.

## Cycle 2 actual result

Cycle 2 was attempted and never admitted.

- no `printer_memory_factory_campaign_cycles` row with ordinal `2`
- one pre-admission attempt `c0002`, now `CANCELLED` /
  `PARENT_CAMPAIGN_INTERRUPTED:SAFE_STOP_PREFLIGHT_FAILED`
- 11 Cycle-2-keyed source requests (`:c0002-`), including locator, new-pools,
  GeckoTerminal liquidity backups, PumpSwap protocol, migration live-tail, and
  one DexScreener `mint-batch-r1`
- one pre-lifecycle refresh wait remaining `WAITING`

No Cycle-2 slots, windows, or admitted identities.

## Source Governor / Scheduler / six-unit

Source Governor remained sole source authority. All 157 requests
(`4532`-`4688`) are this-execution keyed. 150 responses (`4133`-`4282`). 7
failures (`399`-`405`).

Sources: DexScreener `111`, GeckoTerminal `16`, `solana_rpc` `14`, GoPlus `6`,
Jupiter quote `6` (paper-quote realism only), CoinGecko `4`. No paid Birdeye,
no endpoint rotation, no unauthorized provider class.

157 is inside the authorized operational-policy
`lifecycle_request_outer_ceiling = 476`. Early GeckoTerminal rate-limits were
non-terminal `STALE_DATA`. The campaign-stopping transport failures are the
four `WINDOW_4H` snapshot-012 DexScreener/GeckoTerminal network errors.

Central Scheduler remained sole scheduling authority. Durable Scheduler jobs
were created and later cancelled/succeeded/failed in `printer_scheduler_jobs`.
Zero remaining PENDING/RUNNING/COOLDOWN/locked jobs. Child-terminal
`scheduler_runtime_calls = 0` is reconstruction-hardcoded and is not used as
proof that the Scheduler owner was bypassed.

Six-unit accounting is blocked
`OPERATIONAL_STAGE_FAILED_BEFORE_ACCOUNTING_COMPLETION` after 12 sealed
completed stages. That is a consequence of the later shared-terminal exception,
not an independent source-accounting defect.

## Duplicate-transport repair applicability

The later-cycle cooperative mint-market-batch duplicate-transport repair was
not the terminal cause and is not implicated as weakened.

Cycle 2 reached one DexScreener `c0002-mint-batch-r1` request and then entered
the refresh wait. There is no durable `DUPLICATE_TRANSPORT_IDENTITY` exception,
no second mint-batch identity collision on this run, and no Cycle-2 admission
abort on that producer. The producer repair remains closed PASS in ancestry at
`041e2550ec2ec090e45eec2d8de45f6a0c1e84f0`. This campaign died later, on
undrained wait ownership during shared terminal.

## Classification

Primary: `COMMITTED_CODE_DEFECT`.

Subtype: `PRE_LIFECYCLE_TERMINAL_CLEANUP_ORDERING_OR_OWNERSHIP_DEFECT`.

Proven, not assumed: shared terminal was attempted while current-attempt
Cycle-2 pre-lifecycle refresh wait `WAITING` (and at raise time its
`DISCOVERY_REFRESH` job) had not been lawfully drained. Parent-interrupt
cleanup terminalizes the attempt/job `3493` only. Phase A drains admitted
Cycle-1 scheduler-work only. Outer cleanup later cancelled job `3548` and still
left the wait row `WAITING`. Shared terminal requires zero waits. Official
zero-state does not count waits.

Distinct original operational initiator, not the primary child-exit
classification: `PROVIDER_LIMITATION` / network
(`dexscreener_transport_failure` plus GeckoTerminal `No route to host` on
`WINDOW_4H` snapshot 012). If shared terminal had drained the wait, this run
could have closed as a bounded provider-blocked Cycle-1 through-1h campaign
with Cycle 2 unadmitted. The committed cleanup defect turned that stop into
`CHILD_EXITED_NONZERO` and left orphan wait residue.

Code change is justified. It is not authorized in this lane.

## Permanent locks

Unchanged: Solana-only; Solana memecoin-only; paper-trading only. No live
wallet/private keys/signing/real funds/live execution. No paid API dependency.
No scoring/ranking/confidence/weighted logic. No embeddings/vectors unless
explicitly approved. No Source Governor or Central Scheduler bypass. No
dirty-memory retrieval/decisions. Retrieval and all financial capability remain
locked. `WINDOW_5M_MICRO_EVENT` remains support-only. `WINDOW_12H` and
`WINDOW_24H` remain locked. No automatic retry/rerun/resume/restart.

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260902T122136Z_59fdefe7` is
`CONSUMED / CHILD_EXITED_NONZERO / PERMANENTLY NON-REUSABLE`.

Never retry, rerun, resume, restart, or create a successor from this
authorization. Do not remove or recreate the application marker.

## Exact next permitted lane

```text
PRE-LIFECYCLE TERMINAL CLEANUP ORDERING OR OWNERSHIP DEFECT — AUDIT / READINESS THEN DESIGN / SPECIFICATION ONLY
```

Follow:

```text
audit/readiness -> design/specification -> implementation if approved -> bounded proof/test -> closeout
```

This closeout is the campaign evidence audit. It is not the defect
audit/design. Do not implement yet. Do not drain the remaining wait in this
lane. Do not run Printer. Do not prepare or apply another authorization. Do not
retry/rerun/resume/restart `59fdefe7`.

The subsequent audit/design must cover at least:

1. draining later-cycle pre-lifecycle refresh waits before shared terminal;
2. parent-interrupt cleanup ownership of wait rows and wait jobs, not only the
   pre-admission attempt;
3. official zero-state projection of `WAITING` / `CLAIMED` waits;
4. the live residue row identified above, without unauthorized manual cleanup
   in this closeout.

`V2_9_8B_AUTH_59FDEFE7_CAMPAIGN_CLOSEOUT_BLOCKED`
