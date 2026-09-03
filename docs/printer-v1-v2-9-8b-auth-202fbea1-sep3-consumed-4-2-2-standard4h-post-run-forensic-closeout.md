# Printer V1 — V2-9.8B Sep-3 Consumed 4/2/2 Standard-4H Post-Run Forensic Closeout

Status: **CLOSED PASS as forensic evidence collection**

Lane:

`V2-9.8B SEP-3 CONSUMED 4/2/2 STANDARD-4H BUDGET SAFE-STOP READ-ONLY FORENSIC CLOSEOUT`

Forensic verdict:

`V2_9_8B_SEP3_CONSUMED_4_2_2_STANDARD4H_POST_RUN_FORENSIC_CLOSEOUT_PASS`

That `PASS` means the forensic audit is complete and trustworthy. It does **not**
mean the Standard-4H campaign succeeded.

Canonical campaign result:

`CAMPAIGN_FAILED`

Canonical campaign state: `TERMINAL_FAILED`. Factory run status: `SAFE_STOPPED`.
First terminal cause on campaign, campaign-run, Cycle 1, factory run, and
supervision: `SAFE_STOP_BUDGET_CEILING_EXCEEDED`.

Primary classification:

`PROVEN_COMMITTED_BUDGET_ENFORCEMENT_DEFECT`

Subtype:

`FOUR_TOKEN_STD4H_PER_TOKEN_CEILING_STILL_SELECTIVE_1H_CONTINUOUS_50`

The wrapper `child_exit_code = 0` / child `success = true` is **not** campaign
proof. The child treated a budget safe-stop as an operational command complete.

This closeout is documentation/governance only. It does not repair production
code, modify tests, mutate the authoritative DB, reuse the consumed
authorization, rerun Printer, create an application marker, or prepare another
authorization.

---

## Exact execution identity

- authorization: `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260903T121923Z_202fbea1`
- frozen authorization SHA-256: `02153f8a96b13f5096cd0e695c78649f16e2f11105894f91a86517d486493c5d`
- authorization state: `CONSUMED / CHILD_EXITED_ZERO / PERMANENTLY NON-REUSABLE`
- authorized / actual execution HEAD: `26d7b91bb5f115ad816b3cd632b5036d07b82b0e`
- authorized branch: `assistant/v2-9-8b-later-cycle-mint-market-replay-repair`
- wrapper execution: `20260903T124259Z-a9b0fb4b2622`
- campaign: `20260903T124259Z-a9b0fb4b2622-campaign`
- campaign-run: `20260903T124259Z-a9b0fb4b2622-campaign-run`
- Cycle 1: `20260903T124259Z-a9b0fb4b2622-cycle`
- proposed Cycle 2: `20260903T124259Z-a9b0fb4b2622-cycle-2` (attempted; **never admitted**)
- supervision: `20260903T124259Z-a9b0fb4b2622-supervision`
- factory run: `7a8bc1ec-a4bf-459c-873b-c4ec80bd75b5`
- configuration: `20260903T124259Z-a9b0fb4b2622-configuration`
- child PID: `24172`
- child result: `CHILD_EXITED_ZERO`
- process exit: `0`
- wrapper `success`: `true`
- wrapper `terminal_classification`: `CHILD_EXITED_ZERO`
- child `status` / `terminal_category`: `OPERATIONAL_CAMPAIGN_TERMINAL` / `OPERATIONAL_COMMAND_COMPLETE`
- retries / reruns / resumes / restarts / successors: all `0`
- child-terminal `source_calls`: `17`
- child-terminal `scheduler_runtime_calls`: `298`
- child-terminal `lifecycle_started`: `true`
- child-terminal `cleanup_complete`: `true`
- child-terminal `lease_released`: `true`
- child-terminal `active_owned_work_after`: `0`
- child-terminal `first_terminal_cause`: `SAFE_STOP_BUDGET_CEILING_EXCEEDED`

The authorization is permanently consumed. It must not be retried, rerun,
resumed, restarted, reused, or treated as successor authority. It must enter
every future prior-authorization non-reuse trust root. That future complete
root is **60 IDs** (the previous 59 plus this consumed ID).

---

## 1. Immutable application evidence

Independently hashed during this forensic; artifacts were not modified.

| Artifact | Path | SHA-256 |
|---|---|---|
| Frozen authorization | `operator-runs/v2-9-8b-four-token-standard-four-hour-final-authorization/V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260903T121923Z_202fbea1/final_authorization.json` | `02153f8a96b13f5096cd0e695c78649f16e2f11105894f91a86517d486493c5d` |
| Application marker | `/Users/Dtwo1/PrinterOperations/v2-9-8/four-token-standard-four-hour-one-shot-applications/V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260903T121923Z_202fbea1/application-marker.json` | `107e1744bd405b4987f6052ef09566febc8cafa8ae2941c403423c06d99c3a38` |
| Git provenance manifest | same application directory `git-provenance-manifest.json` | `4aadd27df22e22e7159d8bb61566e7379fa0589c43480ac2cfac0cd1826f7032` |
| Wrapper terminal | same application directory `wrapper-terminal.json` | `27c538af2debfae2277290fa6cb82b9acec485713563b892060fc1590a44c1c6` |
| Child terminal | same application directory `child-terminal.json` | `6def0b5a1fe545178b922ff9ce772ed786bc0fb44b2de3bbfe23a52a523829da` |
| Campaign report | `/Users/Dtwo1/PrinterOperations/v2-9-8/20260903T124259Z-a9b0fb4b2622/reports/20260903T124259Z-a9b0fb4b2622-report.campaign-report.json` | `ac0c499d93c007d2855ab567247011fcbbf15cacdc1dd5c0ca21abf0e89733ff` |
| Terminal summary | `/Users/Dtwo1/PrinterOperations/v2-9-8/20260903T124259Z-a9b0fb4b2622/terminal-summary.json` | `5d0373ef33872e28de5231c5f5f94d577b361fbdd2659e99ee573d59970475eb` |
| Authoritative DB | `data/printer_v1.sqlite3` | `575984caa484b12f4bb5fca0a06cdf7865adeb03b5f16874406fb0c1a73daa6e` |

Proved:

- authorization SHA, marker SHA, child-terminal SHA, campaign-report SHA, and
  post-run DB SHA all match the operator-supplied expected values;
- repository HEAD at forensic time equals authorized HEAD `26d7b91b...`;
- marker exists, `allowed_invocation_count = 1`, consumed at
  `2026-09-03T12:42:56.015021+00:00`;
- package / marker / manifest identities agree (authorization SHA, HEAD,
  manifest SHA `4aadd27d...`);
- wrapper records `automatic_retries = 0`, `manual_reruns = 0`, `resumes = 0`,
  `restarts = 0`, `successors = 0`;
- marker forbids retry/rerun/resume/restart/successor;
- exactly one application directory; wrapper staging is empty;
- no second application, no second marker, no second wrapper execution;
- authorization is permanently non-reusable.

Frozen operational policy on the package: `476 / 118 / 444`, shared discovery
`4`, retries `0`, endpoint rotation `false`, 4/2/2, `WINDOW_12H` / `WINDOW_24H`
locked. Prior non-reuse trust root on this package is 59 IDs, including
consumed `59fdefe7`, consumed `12a7ea61`, consumed `ab6c68fe`, and stale
`b6d7ab46`.

---

## 2. Campaign acceptance truth

Report these outcomes separately. Do not collapse them into wrapper
`success = true`.

```text
wrapper/application outcome
  CHILD_EXITED_ZERO
  marker_consumed = true
  applied exactly once
  retries/reruns/resumes/restarts/successors = 0
  cleanup_complete = true
  lease_released = true

campaign execution outcome
  campaign_state = TERMINAL_FAILED
  campaign-run state = TERMINAL_FAILED
  factory-run status = SAFE_STOPPED
  Cycle-1 state = TERMINAL_FAILED
  Cycle-2 = NOT ADMITTED
    pre-admission attempt_state = NO_PAIR
    first_terminal_cause = DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE
  first_terminal_cause (campaign/run/cycle-1/factory/supervision)
    = SAFE_STOP_BUDGET_CEILING_EXCEEDED
  campaign_acceptance.pass = false
  campaign_acceptance.verdict = BLOCKED_UNSAFE
  operational_lifecycle_pass = false

memory-quality outcome
  Cycle-1 WINDOW_15M campaign windows: CLEAN_PROMOTED
  durable memory-window owner: PARTIAL_MEMORY (not CLEAN_MEMORY)
  episode owner: CLEAN_MEMORY / WINDOW_15M_CLEAN_MEMORY
  report quality_results: PARTIAL_MEMORY + CLEAN_EPISODE_ALLOWED
  WINDOW_1H / WINDOW_4H: no durable memory rows
  WINDOW_5M_MICRO_EVENT: SUPPORT_EVIDENCE (support-only)
  retrieval / decisions / positions / trades / PnL remain locked (0 deltas)

Standard-4H objective outcome
  intended 4/2/2 through-4h campaign DID NOT complete
  2 tokens admitted, not 4
  Cycle 2 not admitted
  15m completed; 1h started then cancelled; 4h never started

cleanup/zero-state outcome
  supervision TERMINAL / FAILED
  cleanup_completed_at and lease_released_at present
  official zero-state projection: all required domains 0
  PRAGMA integrity_check = ok
  PRAGMA foreign_key_check = empty
```

Failing campaign-acceptance checks (report, not inferred):

- `mandatory_stage_statuses_completed`
- `owner_action_local_equal_non_vacuous`
- `all_lifecycle_scheduler_jobs_succeeded`
- `runtime_terminal_completed`
- `persisted_slot_dispositions_exact`
- `cadence_coverage_and_close_complete`

---

## 3. Exact 4/2/2 progression

- cycles admitted: **1**
- Cycle 2 actually admitted: **no**
- distinct tokens admitted: **2**
- four concurrent through-4h tokens: **no**
- third cycle: **no**
- fifth token: **no**
- Cycle-1 freeze shape: 4 candidates observed in admission (`2` selected + `2`
  report-only alternates)

Admitted tokens:

| Slot | Mint | Pair | Lane | Token state |
|---|---|---|---|---|
| `slot-...-cycle-1` ordinal 1 | `B33yWXo4uNSmZDkNMNCNi95DRAChEB2LVFpD1LqGpump` | `2HV2bsPoa2AKrKQD6DwmfyaChYqQyY4xpUgB299CGTJp` | `TRACK_FAST` | `MANUAL_REVIEW` |
| `slot-...-cycle-2` ordinal 2 | `J1yoS599NNaynhMw1EUMrHdCASg2fqjthViKEe9epump` | `HjZp9D7CSnoGj1wD1wgewtRJ33GcyxpzCiAbsmTPe7Nj` | `TRACK_NORMAL` | `MANUAL_REVIEW` |

Report-only alternates (not admitted):

- `CLd4sKq53pWpjqwaUG3EBnqFMf8242GnZqvPyyqepump`
- `NEW37tshbEuVKPZ6et9SDoMpumEy1PfQpX55Vcr8fUL`

Campaign-window progression (persisted `printer_memory_factory_campaign_windows`):

| Token | WINDOW_15M | WINDOW_1H | WINDOW_4H |
|---|---|---|---|
| FAST `B33y...pump` | `CLEAN_PROMOTED` (`15M_CLEAN_PROMOTED`) | `CANCELLED` (`SAFE_STOP_BUDGET_CEILING_EXCEEDED`) | `NOT_STARTED` |
| NORMAL `J1yo...pump` | `CLEAN_PROMOTED` (`15M_CLEAN_PROMOTED`) | `CANCELLED` (`SAFE_STOP_BUDGET_CEILING_EXCEEDED`) | `NOT_STARTED` |

`WINDOW_1H` was **STARTED** (snapshots collected) then **CANCELLED**. It is not
`CLOSED` and not `CLEAN_PROMOTED`. FAST completed 23 `CONTINUATION_SNAPSHOT`
steps (cadence 24 observations = 23 snapshots + close). NORMAL completed 12
`CONTINUATION_SNAPSHOT` steps (cadence 13 observations = 12 snapshots + close).
Neither 1h close finished.

`WINDOW_5M_MICRO_EVENT` (support-only; no campaign-window rows): two durable
memory-window rows `274` / `275`, both `WINDOW_CLOSED`, quality
`SUPPORT_EVIDENCE`. Factory `SUPPORT_5M` steps both `SUCCEEDED`.

`WINDOW_12H` / `WINDOW_24H` remain locked. Standard-4h progression attempt
`TERMINAL_FAILED` with both tokens still `WAITING_FOR_PREDECESSOR`; no 4h
successor window.

---

## 4. Exact budget that fired

First persisted factory step with `SAFE_STOP_BUDGET_CEILING_EXCEEDED`:

| Field | Value |
|---|---|
| factory step ID | `2110` |
| step key | `t1_continuation_close_context` |
| step kind | `CONTINUATION_CLOSE_CONTEXT` |
| Scheduler job ID | `3744` |
| cycle | Cycle 1 `20260903T124259Z-a9b0fb4b2622-cycle` |
| token | `B33yWXo4uNSmZDkNMNCNi95DRAChEB2LVFpD1LqGpump` (`TRACK_FAST`, slot 1) |
| window/stage | `WINDOW_1H` close / CONTEXT |
| scheduled timestamp | `2026-09-03T13:43:48.018503+00:00` |
| started | `2026-09-03T13:44:00.582563+00:00` |
| failed | `2026-09-03T13:44:00.591182+00:00` |
| result payload | `{"budget_detail": null, "budget_scope": "CUMULATIVE_LIFECYCLE", "global_stop": "SAFE_STOP_BUDGET_CEILING_EXCEEDED", "ok": false}` |
| `source_request_id` | `null` (rejected before a new request) |

Committed enforcement owner:

`one_command_15m_factory._enforce_budgets_before_step`

Call site: factory loop after Scheduler claim, before reservation/request
(`one_command_15m_factory.py` around the `_projected_requests_for_step` /
`_enforce_budgets_before_step` pair).

This step is **not** a `LONG_CONTINUATION_*` 4h step. It takes the pre-4h
branch:

1. `run_ceiling = _request_ceiling_for_run_config(config)` → **476** because
   `four_token_proof = true` (the repaired outer selector).
2. `token_ceiling = _CONTINUOUS_MAX_REQUESTS_PER_TOKEN` because
   `continuous_first_hour = true` → **50**.
3. `_run_request_count + projected > 476` was **false**.
4. `_token_request_count(t1) + projected > 50` was **true**.

Replay against the live post-run DB with the same owners raised
`_GlobalStop(SAFE_STOP_BUDGET_CEILING_EXCEEDED, scope=CUMULATIVE_LIFECYCLE)`
again.

`budget_scope = CUMULATIVE_LIFECYCLE` is the label used for **both** the outer
run check and the per-token check. `budget_detail` is null because those two
raise sites pass no detail. The arithmetic, not the label, identifies which
counter fired.

Wrapper `source_calls = 17` and `scheduler_runtime_calls = 298` are **not**
this counter. `17` is campaign/pre-lifecycle observer accounting.
`298` is the wrapper runtime-call observer, not
`lifecycle_scheduler_outer_ceiling`.

---

## 5. Every plausible ceiling

Live committed constants at authorized HEAD, and observed counts at rejection
(post-run counts equal rejection-time counts: zero factory requests after the
failed step started).

| Ceiling | Authorized / committed value | Observed | Fired? |
|---|---|---|---|
| Standard-4H outer request (`lifecycle_request_outer_ceiling`) | **476** | factory `_run_request_count` **82** | **no** (`82 + 0 <= 476`) |
| Per-token Standard-4H (`lifecycle_requests_per_token`) | **118** | t1 **51**, t2 **31** | **no** (51 < 118) |
| Scheduler outer (`lifecycle_scheduler_outer_ceiling`) | **444** | `_run_step_job_count` **74** | **no** |
| Shared discovery | **4** | discovery work Cycle 1 succeeded; not the stop | **no** |
| Selective-1h run (`_SELECTIVE_1H_MAX_REQUESTS_RUN`) | **102** | 82 | **no** (selector did not apply 102; 82 < 102 anyway) |
| Selective-1h / continuous **per-token** (`_SELECTIVE_1H_MAX_REQUESTS_PER_TOKEN` = `_CONTINUOUS_MAX_REQUESTS_PER_TOKEN`) | **50** | t1 **51**, projected **0** | **yes** (`51 + 0 > 50`) |
| V2-5 15m per-token (`_MAX_GOVERNED_REQUESTS_PER_TOKEN`) | **22** | not selected (`continuous_first_hour` true) | **no** |
| V2-5 15m run (`_MAX_GOVERNED_REQUESTS_RUN`) | **68** | not selected | **no** |
| Continuous run (`_CONTINUOUS_MAX_REQUESTS_RUN`) | **52** | not selected (`four_token_proof` uses 476) | **no** |
| 4h phase / standard subset | n/a for this step kind | not entered | **no** |

Which counter fired: **t1 per-token governed-request count**.

Value: **51**.

Ceiling applied: **50** (`_CONTINUOUS_MAX_REQUESTS_PER_TOKEN`).

Why that ceiling was selected for `four_token_proof`: `_enforce_budgets_before_step`
special-cases `four_token_proof` only for the **run** ceiling (476). The
**per-token** ceiling still follows `continuous_first_hour` and therefore the
selective-1h/continuous 15m+1h envelope of 50. It never reads
`lifecycle_requests_per_token = 118`.

Projected requests for `CONTINUATION_CLOSE_CONTEXT` are **0**
(`LIFECYCLE_RESERVED_OPERATIONS_BY_STEP_KIND["CONTINUATION_CLOSE_CONTEXT"] = 0`).
The step was rejected because t1 had **already** exceeded 50, not because this
step itself needed more requests.

---

## 6. Old 102-ceiling regression check

The Aug-31 four-token Standard-4H stop inherited the standalone selective-1h
**run** ceiling `102`. That **run-ceiling selector** was later repaired:

```text
_request_ceiling_for_run_config(four_token_proof=True)
  -> scaled_standard_four_hour_capacity_contract(4)["lifecycle_request_outer_ceiling"]
  -> 476
```

This Sep-3 run:

```text
DID NOT trip the legacy selective-1h run ceiling 102.
DID trip the equivalent nested leftover selective-1h / continuous per-token ceiling 50.
```

Proof:

- factory config had `four_token_proof = true`, `selective_1h_continuation = true`,
  `continuous_first_hour = true`, `standard_four_hour_campaign = true`;
- `_request_ceiling_for_run_config(config) = 476`;
- `_run_request_count = 82` (`82 <= 102` and `82 <= 476`);
- hard_ceilings JSON still *records* `selective_1h_governed_requests_run = 102`,
  but that recorded constant is not the live run selector for this config;
- the live per-token selector is still `_CONTINUOUS_MAX_REQUESTS_PER_TOKEN = 50`,
  which is the same constant as `_SELECTIVE_1H_MAX_REQUESTS_PER_TOKEN`.

So the exact 102 **run** regression did not recur. An equivalent stale
selective-1h **per-token** ceiling did, and that is the proven committed-code
defect.

---

## 7. Per-token 118 audit

Factory-governed requests (`printer_source_requests.request_key LIKE '{factory_run_id}:%'`),
attributed by `_token_prefix`:

| Token | Prefix | Governed requests | vs 50 | vs 118 |
|---|---|---|---|---|
| FAST `B33y...pump` | `t1` | **51** | exceeded | well under |
| NORMAL `J1yo...pump` | `t2` | **31** | under | under |
| Factory run total | | **82** | n/a | n/a vs 476 |

No token reached the authorized Standard-4H per-token ceiling **118**.

The next operation rejected was `t1_continuation_close_context` (step `2110`,
job `3744`). It issued no request.

Current committed design treats a per-token ceiling breach as a **run-wide**
`_GlobalStop`, not `TOKEN_LOCAL_TERMINAL_FAILURE`. Remaining peer 1h close
steps were cancelled. That matches current factory law for `_enforce_budgets_before_step`.
The defect is the **wrong numeric ceiling** (50 instead of 118), not the
global-versus-token-local choice by itself. With 118, `51 + 0` would have been
allowed and the 1h close would have continued.

t1 51-request composition (durable request keys):

- 15 × 15m `SNAPSHOT`
- 1 × `t1_window_close_evidence`
- 5 × `t1_window_close_pre_close_critical`
- 23 × 1h snapshot steps plus 3 extra fallbacks on snapshots 20/21/22 = 26
- 2 × `t1_continuation_close_evidence` (DexScreener primary + GeckoTerminal fallback)
- 2 × `t1_continuation_close_pre_close_critical`

The 50th→51st request was `t1_continuation_close_evidence:geckoterminal_fallback`
at `2026-09-03T13:43:58.204192+00:00`, which **succeeded**. The following
CONTEXT step was then rejected.

---

## 8. Scheduler 444 audit

- `_scheduler_ceiling_for_run_config` for this config: **444** (four-token
  scaled contract; `four_token_proof` selector).
- `_run_step_job_count` (`job_name LIKE 'v2_4_{factory_run_id}_%'`): **74**.
- Job states: 69 `SUCCEEDED`, 4 `CANCELLED`, 1 `FAILED` (job `3744`).
- Discovery/handoff allowance for `four_token_proof` insert-time check is `0`,
  so insert would fire only at `>= 444`. 74 < 444.
- Wrapper `scheduler_runtime_calls = 298` is a different observer and is not
  this counter.

Scheduler budget was **not** the stop.

Job `3744` shows `retry_count = 1` with `last_error = SAFE_STOP_BUDGET_CEILING_EXCEEDED`.
That is the fail-job counter on the one claimed execution (`fail_job(..., max_retries=0)`),
not a campaign automatic retry. Wrapper `automatic_retries = 0`.

---

## 9. Source-request accounting

Factory lifecycle governed requests (the counter that fired):

- total: **82**
- all `source_status = COMPLETE`, `data_quality_label = CLEAN_DATA`
- by source: dexscreener 61, solana_rpc 6, geckoterminal 5, goplus 4,
  jupiter_quote 4, coingecko 2
- by kind: `pair_market_snapshot` 66, `safety_reference` 4,
  `mint_account_reference` 4, `paper_quote_realism` 4,
  `broad_market_context` 2, `holder_concentration_reference` 2
- per-token: t1 51, t2 31
- factory requests after failed-step start: **0**
- no successful governed factory request occurred past the ceiling that fired
  for the rejected CONTEXT step (that step has `source_request_id = null`)

Campaign/time-window source rows `2026-09-03T12:42:00Z`–`13:45:00Z`: **111**
`COMPLETE` (includes pre-lifecycle discovery keys
`v2-9-8b-window15m-20260903T124259Z-a9b0fb4b2622...` and Cycle-2
`:c0002-` keys). Child/wrapper `source_calls = 17` /
`campaign_source_calls = 17` count that campaign observer scope, not the 82
factory-lifecycle keys.

Shared discovery: Cycle-1 discovery-work rows all `SUCCEEDED`. Cycle-2
discovery ran as a pre-admission attempt and did not admit a cycle.

Retries: wrapper automatic retries `0`. Endpoint rotation policy `false`.
Exact-pair GeckoTerminal fallbacks did occur on some 1h snapshots and on
`t1_continuation_close_evidence`; those extra keys are what pushed t1 from
the 50 envelope to 51.

Duplicate/replayed factory keys: `t1_continuation_snapshot_20/21/22` each have
2 requests; `t2_continuation_snapshot_11` has 2; `t1_continuation_close_evidence`
has 2.

---

## 10. Memory actually produced

Do not treat campaign-window `CLEAN_PROMOTED` as `CLEAN_MEMORY`.

### WINDOW_15M

Two durable rows:

| id | token | snapshots | window_status | memory_status | memory_quality_label | data_quality | do_not_train |
|---|---|---|---|---|---|---|---|
| 272 | 113 FAST | 16/16 | `WINDOW_CLOSED` | `PARTIAL_MEMORY` | `PARTIAL_MEMORY` | `CLEAN_DATA` | 0 |
| 273 | 114 NORMAL | 9/9 | `WINDOW_CLOSED` | `PARTIAL_MEMORY` | `PARTIAL_MEMORY` | `CLEAN_DATA` | 0 |

Campaign windows for those rows: `CLEAN_PROMOTED`.

Episodes:

| id | window | episode_kind | episode_status | episode memory_status | memory_quality_label |
|---|---|---|---|---|---|
| 123 | 272 | `WINDOW_15M_CLEAN_MEMORY` | `COMPLETE` | `CLEAN_MEMORY` | `CLEAN_MEMORY` |
| 124 | 273 | `WINDOW_15M_CLEAN_MEMORY` | `COMPLETE` | `CLEAN_MEMORY` | `CLEAN_MEMORY` |

Fingerprints: `87` and `88`, both `STATIC_CONDITION_SUMMARY`, `CLEAN_MEMORY`,
`CLEAN_DATA`, `do_not_train = 0`.

Outcome label on both 15m windows: `SLOW_BLEED`.

### WINDOW_1H

No durable `printer_memory_windows` rows. Campaign windows exist and are
`CANCELLED`. No 1h episode/fingerprint.

### WINDOW_4H

No campaign windows. No memory rows. Progression tokens remain
`WAITING_FOR_PREDECESSOR`.

### WINDOW_5M_MICRO_EVENT (support-only)

| id | token | window_status | memory_status | memory_quality_label | data_quality | do_not_train |
|---|---|---|---|---|---|---|
| 274 | 113 | `WINDOW_CLOSED` | `PARTIAL_MEMORY` | `SUPPORT_EVIDENCE` | `CLEAN_DATA` | 0 |
| 275 | 114 | `WINDOW_CLOSED` | `PARTIAL_MEMORY` | `SUPPORT_EVIDENCE` | `CLEAN_DATA` | 0 |

No 5m campaign-window rows. No 5m episodes.

Retrieval / paper decisions / positions / trades / audits / PnL created during
the campaign window: **0**. Locks remain closed.

---

## 11. Cancellation and cleanup

After step `2110` failed:

Cancelled remaining factory steps (all `error_or_skip_reason = SAFE_STOP_BUDGET_CEILING_EXCEEDED`,
`started_at = null`, finished `2026-09-03T13:44:00.600065+00:00`):

- `2111` `t1_continuation_close_audit` job `3745`
- `2126` `t2_continuation_close_evidence` job `3759`
- `2127` `t2_continuation_close_context` job `3760`
- `2128` `t2_continuation_close_audit` job `3761`

Cycle 1, campaign-run, campaign, factory run, and supervision terminalized on
the same cause. Standard-4h progression attempt terminalized
`FACTORY_TERMINAL_OWNERSHIP` / `SAFE_STOP_BUDGET_CEILING_EXCEEDED`.

Supervision: `TERMINAL` / `FAILED`; `cleanup_completed_at` and
`lease_released_at` both `2026-09-03T13:44:00.654614+00:00`.

Active work after closeout: factory steps pending/running `0`; scheduler
pending/running/cooldown `0`; campaign scheduler work pending/running/cooldown
`0`; pre-lifecycle waits waiting/claimed `0`; refresh work running `0`.

No factory governed request after the stop boundary.

Cycle-2 pre-admission did **not** remain `WAITING`. The Cycle-2 refresh wait
is `FAILED` with
`PRE_LIFECYCLE_REFRESH_INTERNAL_INVARIANT:SIX_UNIT_STAGE_EVIDENCE_DUPLICATE_TRANSPORT:DUPLICATE_TRANSPORT_IDENTITY`
at `2026-09-03T13:01:19.459529+00:00`, before the later budget stop. That is a
secondary later-cycle finding; it is not the campaign first-terminal cause.

---

## 12. Post-run official zero-state

Official owner: `project_four_token_proof_zero_state` (same domain queries as
`assert_four_token_standard_four_hour_zero_state`).

Read-only URI open of `data/printer_v1.sqlite3`. All required domains:

```text
active_campaigns                                    0
active_campaign_runs                                0
active_campaign_cycles                              0
active_campaign_scheduler_work                      0
campaign_supervision                                0
proof_supervision                                   0
active_discovery_work                               0
active_factory_runs                                 0
active_factory_steps                                0
pre_admission_discovery_attempts                    0
active_pre_lifecycle_discovery_refresh_work         0
active_pre_lifecycle_discovery_refresh_waits        0
active_scheduler_jobs                               0
```

`PRAGMA integrity_check;` → `ok`

`PRAGMA foreign_key_check;` → empty

DB SHA-256 before forensic:

`575984caa484b12f4bb5fca0a06cdf7865adeb03b5f16874406fb0c1a73daa6e`

DB SHA-256 after forensic:

`575984caa484b12f4bb5fca0a06cdf7865adeb03b5f16874406fb0c1a73daa6e`

No identity drift. The forensic did not mutate the authoritative DB.

---

## 13. Classification

Exactly one primary classification:

```text
PROVEN_COMMITTED_BUDGET_ENFORCEMENT_DEFECT
```

A safe stop itself is not a defect. This stop applied the **wrong ceiling**.

Exact code + persisted evidence:

- committed `_enforce_budgets_before_step` still sets
  `token_ceiling = _CONTINUOUS_MAX_REQUESTS_PER_TOKEN` (50) for
  `four_token_proof` / `continuous_first_hour`;
- authorized / scaled contract per-token ceiling is 118;
- persisted t1 count 51, projected 0, `51 + 0 > 50`;
- replay of the same function against the same DB raises the same stop;
- 51 < 118, 82 < 476, 74 < 444, 82 < 102.

Secondary finding, not the primary classification: Cycle 2 was not admitted
(`NO_PAIR` / `DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE`), and the Cycle-2
pre-lifecycle refresh wait failed closed on
`DUPLICATE_TRANSPORT_IDENTITY`. That later-cycle class is historically
associated with the mint-market replay repair. It did not leave an active wait.
It is out of scope for the budget-stop primary class.

---

## 14. Overall campaign verdict

```text
Cycle 1 admitted?                         YES
Cycle 2 admitted?                         NO
4 tokens admitted?                        NO (2)
15m completed?                            YES (both CLEAN_PROMOTED campaign windows)
1h completed?                             NO (STARTED then CANCELLED)
4h completed?                             NO (NOT_STARTED)
4 freeze-ready?                           Cycle-1 freeze: 2 selected + 2 report-only
2 selected + 2 report-only?               YES for Cycle 1; Cycle 2 never freeze-admitted
intended Standard-4H campaign completed?  NO
```

Forensic evidence-collection verdict:

`V2_9_8B_SEP3_CONSUMED_4_2_2_STANDARD4H_POST_RUN_FORENSIC_CLOSEOUT_PASS`

Canonical campaign result:

`CAMPAIGN_FAILED`

---

## 15. No repair in this lane

No production code, tests, DB, marker, or authorization package was modified.

Next sequence, because a committed-code defect is proven:

```text
forensic closeout
-> repair readiness/audit
-> design
-> implementation
-> bounded proof
-> independent review
-> fresh readiness
```

The repair-readiness/audit must bind the live HEAD after this closeout
documentation commit exists, and DB SHA-256
`575984caa484b12f4bb5fca0a06cdf7865adeb03b5f16874406fb0c1a73daa6e`.

Exact next permitted lane:

```text
FOUR-TOKEN STANDARD-4H PER-TOKEN REQUEST-CEILING WIRING REPAIR READINESS / AUDIT ONLY
```

That lane may inspect whether `_enforce_budgets_before_step` must use
`lifecycle_requests_per_token = 118` for `four_token_proof` instead of
`_CONTINUOUS_MAX_REQUESTS_PER_TOKEN = 50`. It may also record the Cycle-2
duplicate-transport refresh failure as a secondary residual. It must not
implement, rerun Printer, apply an authorization, or create a successor.

Do not treat this consumed authorization as reusable. Future complete
`prior_authorizations_non_reusable` trust roots must include
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260903T121923Z_202fbea1` in addition to the
previous 59 IDs.

Permanent V1 locks remain unchanged.
