# V2-9.8B Post-Conversion-Repair WINDOW_15M Re-Proof Closeout

Date: 2026-08-04

Lane: `V2-9.8B — Post-Conversion-Repair WINDOW_15M Re-Proof`

## Verdict

`V2_9_8B_POST_CONVERSION_REPAIR_WINDOW_15M_REPROOF_BLOCKED`

Exact first terminal cause:

`OPERATIONAL_CAMPAIGN_FAILED:CampaignSixUnitError`

Underlying accounting block:

`SIX_UNIT_STAGE_EVIDENCE_DUPLICATE_STAGE_ID:…|MINT_MARKET_BATCH|1`

This was the single authorized canonical attempt on the post-conversion-repair HEAD.
It terminalized before lifecycle activation and before clean-memory creation.
Wrapper child exit code **1** records `CHILD_EXITED_NONZERO`. Zero retries, resumes,
restarts or successors were created.

## Verified baseline

| Item | Value |
|---|---|
| Branch | `agent/v2-9-8b-post-rollover-2-exact-public-composition-scheduler-claim-coverage-audit` |
| Full HEAD | `0a41702738d3780a6515659f1f88af4df4816d26` |
| Subject | `Add governed PumpSwap account batch confirmation` |
| Tracked tree before auth | clean |
| Untracked preserved | `operator-runs/v2-9-8b-authoritative-mig050/` |
| `/private/tmp/mp-preclaim` | present; untouched |

## Pre-run checks (non-mutating)

| Check | Result |
|---|---|
| Migration head | `051_permanent_discovery_availability.sql` (count 51) |
| `PRAGMA integrity_check` | `ok` |
| `PRAGMA foreign_key_check` | 0 violations |
| Active campaigns / runs | 0 / 0 |
| Active supervision leases | 0 (all TERMINAL, released) |
| Scheduler locked/pending/running jobs | 0 |
| SQLite journal/WAL/SHM | absent |
| Relevant Printer processes | none |
| Required env | `PRINTER_SOLANA_RPC_URL` present (value not printed) |
| Prior auth reusable | **no** — `V2_9_8B_WINDOW_15M_AUTH_20260804T141128Z` already has application marker |

No readiness artifact was created.

## Authorization

| Item | Value |
|---|---|
| Authorization ID | `V2_9_8B_WINDOW_15M_AUTH_20260804T160827Z` |
| Authorization SHA-256 | `e6db0582702dcc195ddd85c757dd430efd17b62964ef1767aca3f5a6704389cb` |
| Type | `V2_9_8B_POST_CONVERSION_REPAIR_WINDOW_15M_REPROOF_ONE_USE_AUTHORIZATION` |
| Bound HEAD | `0a41702738d3780a6515659f1f88af4df4816d26` |
| Bound branch | exact required branch |
| Bound DB SHA-256 (pre-run) | `2a6184dc157431655e4b4bf757db78d368c27e317a35b6c2e75b864444494a56` |
| Package path | `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260804T160827Z/` |
| Invocation count | **exactly 1** |
| Retry/rerun/resume/restart/successor | `0 / 0 / 0 / 0 / 0` |
| Readiness artifact | not created |
| Prior auth reused | **no** |

Authorization was consumed at wrapper start:

* consumed_at: `2026-08-04T16:08:47.132369+00:00`
* marker SHA-256: `080ec1c5fdfe1b4835593d5bf4e5559c2857732f3bd6dc898b8a7e5598db95c7`
* manifest SHA-256: `133c3366ea96fbfb2ab80581cc7c11ea5caa3cb9ee85df66590d3ea6a351eee9`

## Exact invocation

```powershell
./scripts/Start-PrinterV1-Window15M-OneShot.ps1 \
  -AuthorizationFile 'operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260804T160827Z/final_authorization.json' \
  -AuthorizationSha256 'e6db0582702dcc195ddd85c757dd430efd17b62964ef1767aca3f5a6704389cb' \
  -OperatorApproved
```

| Item | Value |
|---|---|
| Wrapper start/end | `2026-08-04T16:08:47.132401+00:00` / `2026-08-04T16:10:16.211147+00:00` |
| Wrapper terminal | `CHILD_EXITED_NONZERO` |
| Child exit code | `1` |
| Wrapper terminal SHA-256 | `38ff22cf91897a5f44f6faf6a4d63d6e85410fb63caafba66b817fcea0ea4139` |
| Child stderr SHA-256 | `0ba674175ee04e5146a46011ba5fbe0b6f357bfc8304d38eaa3a4ea21c56cd0c` |
| Child stdout | empty (0 bytes) |

## Attempt identity and terminal truth

| Item | Value |
|---|---|
| Execution | `20260804T160847Z-866d78b18463` |
| Campaign | `20260804T160847Z-866d78b18463-campaign` |
| Run | `20260804T160847Z-866d78b18463-campaign-run` |
| Cycle | `20260804T160847Z-866d78b18463-cycle` |
| Campaign/run state | `TERMINAL_FAILED` |
| First terminal cause | `OPERATIONAL_CAMPAIGN_FAILED:CampaignSixUnitError` |
| Accounting status | `SIX_UNIT_ACCOUNTING_BLOCKED` |
| Lifecycle started | **false / not recorded as started** |
| Campaign windows | **0** |
| Scheduler calls | **0** |
| Factory run | not created |
| Report written | **false** (`report_written` blocked by accounting) |
| Terminal-summary SHA-256 | `2e5824af40487e6f625227a5854029c56001e0806cb26b92aae40511bc48d102` |

### Classification of terminal

| Category | Applies? |
|---|---|
| Candidate-local migration rejection | not the first terminal (migration page ran; no tx-reject stage sealed) |
| Source unavailability | secondary: 4× `geckoterminal_rate_limited` on mint reconciliation, not first terminal |
| Contract blocker | no |
| Identity conflict | no |
| Liquidity shortage | incomplete — funnel stopped by accounting before honest shortage certificate |
| Holder/safety shortage | holder never invoked |
| Operation/stage exhaustion | no flat exhaustion claimed |
| Duration exhaustion | no |
| Governed-universe exhaustion | **no** (must not claim; work remained) |
| **Six-unit stage-evidence collision** | **YES — exact first terminal** |

The exact block reason is a **duplicate sealed stage id** for `MINT_MARKET_BATCH|1` after that stage id had already been sealed once with 7 transport operations. Multi-round permanent market batching / protocol-resume market re-entry reuses stage sequence `1`, which the six-unit owner rejects as `SIX_UNIT_STAGE_EVIDENCE_DUPLICATE_STAGE_ID`.

This is an **accounting composition defect** exposed by the live multi-round market path; it is **not** market shortage and **not** provider total outage.

## Chronological source and stage accounting

### Governed source requests in attempt window (17)

| Kind | Count | Notes |
|---|---:|---|
| `dexscreener_fresh_profiles` | 1 | COMPLETE |
| `restored_pump_migration_signature_page` | 1 | COMPLETE (`normalized_rows=0` on page) |
| `geckoterminal_new_pool_discovery` | 1 | COMPLETE |
| `candidate_market_batch` | 14 | Dex mint batch + Gecko mint-pool reconciliation rounds |
| `pumpswap_pool_account_batch` | **0** | protocol account-batch confirmation never reached a sealed request |

### Source failures (4)

All four are `candidate_market_batch` / `geckoterminal_rate_limited` (IDs 199–202). Candidate-local, not the immutable first terminal.

### Sealed six-unit stages before block (4)

| Stage | Sequence | Transports | Status |
|---|---:|---:|---|
| LOCATOR | 1 | 2 | COMPLETED |
| DIRECT_MIGRATION | 1 | 1 | COMPLETED |
| FRESH_POOL_NOMINATION | 1 | 1 | COMPLETED |
| MINT_MARKET_BATCH | 1 | 7 | COMPLETED |

Owner transport operation count at block: **11**.  
Failure occurs when a later market stage attempts to seal **`MINT_MARKET_BATCH|1` again**.

### Partial transport evidence (from partial six-unit)

Dex fresh profiles + token pairs, Pump signature page, Gecko new pools, and multiple mint-market batch transports completed before the accounting exception. Full campaign report was not written.

## Protocol-confirmation outcomes

| Metric | Value |
|---|---:|
| `pumpswap_pool_account_batch` requests | 0 |
| Protocol-confirmed identities via account batch | 0 |
| Holder attempts | 0 |
| FULLY_ELIGIBLE reserve rows (this campaign) | 0 |

Protocol account-batch confirmation did not execute a governed batch in this attempt before terminalization.

## Discovery / eligibility funnel (durable residue)

| Metric | Value |
|---|---:|
| BROAD_NOMINATED (this campaign) | 81 |
| MARKET_READY (this campaign) | **1** |
| FULLY_ELIGIBLE | **0** |
| Selected / alternates | none |
| Lifecycle handoff | none |

Single market-ready identity observed:

* mint `12u9FULaUfHD8uHHe98Fz5gdhg8qeX6DyV93B3Dtpump`
* pool `ECobcS1MSzzAnnzz89xjwRSEYsHAChB7DMbd3G25gwgc`
* reason `EXACT_POOL_CURRENT_AND_LIQUIDITY_FLOOR_PASS`

Authoritative exact-market projection counts after attempt (global, not only this campaign):

| State | Count |
|---|---:|
| CONTRACT_BLOCKED | 90 |
| EXACT_POOL_NO_MATCH | 22 |
| BELOW_LIQUIDITY_FLOOR | 18 |
| CURRENT_POOL_CONFIRMED | 1 |

No honest exhaustion certificate was sealed because reporting blocked on six-unit accounting.

## Lifecycle and memory result

| Item | Value |
|---|---|
| Lifecycle started | **no** |
| Authoritative WINDOW_15M identity | **none** |
| Window completion | **none** |
| Clean memory rows created | **none** |
| Memory audit | **not run** |
| Memory windows count | **162** (unchanged from prior baseline counts) |
| Memory audit reports | **5** (unchanged) |
| Paper decisions / positions / trades / trade audits | **2 / 0 / 0 / 0** (unchanged) |
| Retrieval queries / matches | **10 / 0** (unchanged vs prior closeout baseline family) |

Memory result: **BLOCKED / not PASS**.

## Database and cleanup proof

| Check | Result |
|---|---|
| Post-attempt DB SHA-256 | `9ffe930d75c282b2097c0ed7a1f344594eaca9770c3c4410a2ed879e4d44b74d` |
| `PRAGMA integrity_check` | `ok` |
| `PRAGMA foreign_key_check` | 0 |
| Active campaigns after | 0 |
| Locked scheduler jobs after | 0 |
| Cleanup completed | **true** (`2026-08-04T16:10:16.165779+00:00`) |
| Lease released | **true** |
| Active owned work after | **0** |
| Automatic retries / restart / resume / successor | **0 / 0 / 0 / 0** |
| New child work allowed | **false** |

Pre-campaign backup preserved under execution root:

`/Users/Dtwo1/PrinterOperations/v2-9-8/20260804T160847Z-866d78b18463/`

## Forbidden-capability deltas

All financial/capability locks remain inactive and unchanged in count:

* retrieval / paper decisions / BUY·SELL·HOLD / positions / trades / audits / PnL: no new activity
* no wallets, keys, live execution, paid APIs, scoring, ranking, confidence, weighting
* no automatic retry/rerun/resume/restart/successor

## Exact verdict

`V2_9_8B_POST_CONVERSION_REPAIR_WINDOW_15M_REPROOF_BLOCKED`

Memory PASS is forbidden: no two-token handoff, no completed `WINDOW_15M`, no clean-memory rows, no memory audit PASS.

## Remaining blockers and narrowest next action

### Proven blocker from this attempt

1. **Six-unit stage sequencing for multi-round `MINT_MARKET_BATCH`**  
   Stage evidence seals hard-code `MINT_MARKET_BATCH|1`. A second market-batch round (permanent multi-round marketing and/or protocol-resume market re-entry) attempts to reseal the same stage id and aborts the campaign with `CampaignSixUnitError` after real source work has already occurred.

### Secondary observations (not first terminal)

2. Only **one** market-ready identity was established before abort.  
3. GeckoTerminal mint reconciliation hit **rate limits** (4 failures) — candidate-local, did not set the immutable first terminal.  
4. Governed PumpSwap account-batch confirmation (`pumpswap_pool_account_batch`) did not run in this attempt.  
5. Holder/safety and fully eligible depth were never reached.

### Narrowest next lane (documentation only — not authorized here)

A repair lane limited to **six-unit stage-id sequencing for permanent multi-round market batches** (unique `stage_sequence` per mint-market batch round / resume), without raising budgets, relaxing Pump exactly-one, or lowering the $3,000 floor. After that repair, a **fresh** one-use authorization and one new HEAD-bound attempt would be required.

No second command, recovery, or re-authorization is performed by this closeout.

## Functionality risks / setbacks / efficiency blockers

* Multi-round market progress can be erased at reporting time by stage-id collision even when providers succeeded.
* Protocol account-batch confirmation cannot prove itself if the campaign dies in market accounting first.
* Gecko rate limits remain an efficiency drag on mint reconciliation under fixed no-retry pacing.

## Capability-lock audit

Retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, wallets, signing and live execution remain locked. This lane did not implement code, did not retry, and did not create a successor authorization.

## Final classification

`V2_9_8B_POST_CONVERSION_REPAIR_WINDOW_15M_REPROOF_BLOCKED`

Memory result: **BLOCKED / not PASS**.
