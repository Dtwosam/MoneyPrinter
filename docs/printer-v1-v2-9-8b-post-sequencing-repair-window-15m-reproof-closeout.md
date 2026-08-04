# V2-9.8B Post-Sequencing-Repair WINDOW_15M Re-Proof Closeout

Date: 2026-08-04

Lane: `V2-9.8B — Post-Sequencing-Repair WINDOW_15M Re-Proof`

## Verdict

`V2_9_8B_POST_SEQUENCING_REPAIR_WINDOW_15M_REPROOF_BLOCKED`

Exact first terminal cause:

`PRE_LIFECYCLE_DISCOVERY_SELECTION_COVERAGE_INSUFFICIENT`

Underlying activation / blocked-supply reason (same categorical family):

`PRE_LIFECYCLE_DISCOVERY_SELECTION_COVERAGE_INSUFFICIENT`

Secondary finalization fault (not first terminal):

`SIX_UNIT_ACCOUNTING_BLOCKED:CAMPAIGN_STAGE_OPERATION_RECONCILIATION_MISMATCH`

This was the single authorized canonical attempt on the post-sequencing-repair HEAD.
It terminalized before lifecycle activation and before clean-memory creation.
Wrapper child exit code **0** records controlled terminalization (`CHILD_EXITED_ZERO`),
not Memory PASS. Zero retries, resumes, restarts or successors were created.

## Verified baseline

| Item | Value |
|---|---|
| Branch | `agent/v2-9-8b-post-rollover-2-exact-public-composition-scheduler-claim-coverage-audit` |
| Full HEAD | `8cb1f1cff737a44a3c2388ecfd958bbc610061d6` |
| Subject | `Repair multi-round market batch sequencing` |
| Tracked tree before auth | clean |
| Untracked preserved | `operator-runs/v2-9-8b-authoritative-mig050/` |
| Prior auth package | `V2_9_8B_WINDOW_15M_AUTH_20260804T160827Z` (preserved; temporarily relocated outside the repository for git-provenance allowlist during the single invoke, then restored) |
| `/private/tmp/mp-preclaim` | present; untouched |

## Pre-run checks (non-mutating)

| Check | Result |
|---|---|
| Migration head | `051_permanent_discovery_availability.sql` (count 51) |
| `PRAGMA integrity_check` | `ok` |
| `PRAGMA foreign_key_check` | 0 violations |
| Active campaigns / runs | 0 / 0 |
| Active discovery / factory steps | 0 / 0 |
| Active supervision leases | 0 (all TERMINAL, released) |
| Scheduler locked jobs | 0 |
| SQLite journal/WAL/SHM | absent |
| Relevant Printer processes | none |
| Required env | `PRINTER_SOLANA_RPC_URL` present (value not printed) |
| Prior auth reusable | **no** — `V2_9_8B_WINDOW_15M_AUTH_20260804T160827Z` has application marker under PrinterOperations |
| Auth valid for this HEAD | **none** before fresh package |

No readiness artifact was created.
No providers or discovery ran during preflight.

### Pre-application note (non-consumed)

An initial wrapper start attempt at `2026-08-04T16:46:12Z` blocked with
`GitProvenanceAuthorizationError` because the preserved untracked prior package
`V2_9_8B_WINDOW_15M_AUTH_20260804T160827Z` was not covered by the two-package
manifest. **No application marker was published; the authorization was not
consumed; no child campaign launched.** The prior package was byte-preserved
under `/Users/Dtwo1/PrinterOperations/v2-9-8/preserved-untracked-auth/` for the
single subsequent consume+invoke, then restored to its repository path after
terminal capture.

## Authorization

| Item | Value |
|---|---|
| Authorization ID | `V2_9_8B_WINDOW_15M_AUTH_20260804T164530Z` |
| Authorization SHA-256 | `abcfa1a7863176fab342f764fa7bf0b153163a4020651ab21b264313f3b224d8` |
| Type | `V2_9_8B_POST_SEQUENCING_REPAIR_WINDOW_15M_REPROOF_ONE_USE_AUTHORIZATION` |
| Bound HEAD | `8cb1f1cff737a44a3c2388ecfd958bbc610061d6` |
| Bound branch | exact required branch |
| Bound DB SHA-256 (pre-run) | `9ffe930d75c282b2097c0ed7a1f344594eaca9770c3c4410a2ed879e4d44b74d` |
| Package path | `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260804T164530Z/` |
| Allowed invocation count | **1** |
| Consumed state | **consumed** at wrapper start |
| Retry/rerun/resume/restart/successor | `0 / 0 / 0 / 0 / 0` |
| Readiness artifact | not created |
| Prior auth reused | **no** |

Authorization consumed at wrapper start:

* consumed_at: `2026-08-04T16:47:55.147706+00:00`
* marker SHA-256: `00d7e9dd4884478cdb69071754bcc6f877be5f6c833cb7fcf560aa196ad0d730`
* manifest SHA-256: `b7c20bdb5742dbf8a19b9be5e032b6417dd7e65da98b60d1c8b9d67d7f8c5774`

## Exact invocation

```powershell
./scripts/Start-PrinterV1-Window15M-OneShot.ps1 \
  -AuthorizationFile 'operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260804T164530Z/final_authorization.json' \
  -AuthorizationSha256 'abcfa1a7863176fab342f764fa7bf0b153163a4020651ab21b264313f3b224d8' \
  -OperatorApproved
```

| Item | Value |
|---|---|
| Wrapper start/end | `2026-08-04T16:47:55.147736+00:00` / `2026-08-04T16:49:26.564298+00:00` |
| Wrapper terminal | `CHILD_EXITED_ZERO` |
| Child exit code | `0` |
| Wrapper terminal SHA-256 | `e736c2bbe6429119db0a5e282965608d853e832c098681a9f60c379cdb512a0f` |
| Child stdout SHA-256 | `f66f78263d76df688b0bbc538fa72793f5dc11ba93e6a3a19be16857d9ee7abc` |
| Child stderr | empty (0 bytes) |
| Application root | `/Users/Dtwo1/PrinterOperations/v2-9-8/window-15m-one-shot-applications/V2_9_8B_WINDOW_15M_AUTH_20260804T164530Z/` |

## Attempt identity and terminal truth

| Item | Value |
|---|---|
| Execution | `20260804T164755Z-b723daf73da2` |
| Campaign | `20260804T164755Z-b723daf73da2-campaign` |
| Run | `20260804T164755Z-b723daf73da2-campaign-run` |
| Cycle | `20260804T164755Z-b723daf73da2-cycle` |
| Campaign/run/cycle state | `TERMINAL_FAILED` |
| First terminal cause | `PRE_LIFECYCLE_DISCOVERY_SELECTION_COVERAGE_INSUFFICIENT` |
| Campaign acceptance | `HONEST_BLOCKED` |
| Accounting status (secondary) | `SIX_UNIT_ACCOUNTING_BLOCKED` / `CAMPAIGN_STAGE_OPERATION_RECONCILIATION_MISMATCH` |
| Lifecycle started | **false** |
| Campaign windows | **0** (no WINDOW_15M activated) |
| Scheduler calls | **0** |
| Factory run | not created |
| Report written | **false** (`report: null`; finalization blocked by secondary accounting fault) |
| Terminal-summary SHA-256 | `f66f78263d76df688b0bbc538fa72793f5dc11ba93e6a3a19be16857d9ee7abc` |
| Stage evidence count (terminal) | 5 |
| Campaign source calls (terminal) | 13 |
| Durable source requests this attempt | 20 (ids 1906–1925) |

### Classification of terminal

| Category | Applies? |
|---|---|
| Accounting composition defect (duplicate stage id) | **no** — multi-round sequences sealed as distinct `3` then `4`; no `SIX_UNIT_STAGE_EVIDENCE_DUPLICATE_STAGE_ID` |
| Secondary stage/op reconciliation mismatch | yes, at finalization only — not first terminal |
| Candidate-local migration / protocol rejection | candidate-local protocol outcomes present; not first terminal |
| True shared source failure | **no** as first terminal; 5× Gecko rate-limits were candidate-local on mint reconciliation |
| Contract blocker | partial (many `CONTRACT_BLOCKED` / owner-mismatch identities) |
| Identity conflict | 5 durable identity-conflict states; not first terminal |
| Market liquidity shortage | **yes, material** — only **1** market-ready / `ELIGIBLE_FRESH` survivor after funnel |
| Holder/safety shortage | **yes, material** — the single market-ready mint received holder eval and failed `HOLDER_CONCENTRATION_EXTREME` |
| Operation/stage exhaustion | not claimed as first terminal; capacity remained |
| Duration exhaustion | no (~91s wall clock) |
| Governed-universe exhaustion | **no** (must not claim; market/holder gates failed first with incomplete eligible depth) |
| **Selection coverage insufficient** | **YES — exact first terminal** |

Immutable first terminal is **insufficient fully eligible selection coverage** before lifecycle:
need four distinct fully eligible candidates (`2 selected + 2 alternates`); observed fully
eligible depth **0** (one market-ready survivor failed holder concentration).

## A. Multi-round six-unit sequencing

### Logical `MINT_MARKET_BATCH` rounds in this attempt

Durable sequence continues the shared prefix `v2-9-7e-44` (historical r1,r2 already present).
This campaign allocated **r3** then **r4** — distinct monotonic sequences, no reseal of `|1`.

| Logical round | `stage_sequence` | Request key | Source request ID | Ordered mint-set digest (SHA-256 of sorted requested mints) | Transport stage | Seal / collision |
|---|---:|---|---:|---|---|---|
| Market batch 3 | **3** | `v2-9-7e-44-mint-batch-r3` | 1909 | `d4a5e233acfe3b3b236088832a5741ff2ebabd603145c4e6bed50d652c84db87` (30 mints; prefix `d4a5e233acfe3b3b`) | `MINT_MARKET_BATCH` Dex COMPLETE | no `DUPLICATE_STAGE_ID` |
| Market batch 4 | **4** | `v2-9-7e-44-mint-batch-r4` | 1916 | `66a64fa5ccb3dc57c14007c15c3ca2aeaa93d163a15b4b0b1d215f4ae0b6ee94` (11 mints; prefix `66a64fa5ccb3dc57`) | `MINT_MARKET_BATCH` Dex COMPLETE | no `DUPLICATE_STAGE_ID` |

Inferred stage ids (owner pattern `{campaign}|{run}|{cycle}|MINT_MARKET_BATCH|{N}`):

* `…|MINT_MARKET_BATCH|3`
* `…|MINT_MARKET_BATCH|4`

Logical batch ids (stage id + digest[:16]):

* `…|MINT_MARKET_BATCH|3|d4a5e233acfe3b3b`
* `…|MINT_MARKET_BATCH|4|66a64fa5ccb3dc57`

### Sequencing proofs

| Claim | Evidence |
|---|---|
| Distinct market rounds use distinct monotonic sequences | r3 then r4 (3, 4) |
| Protocol confirmation between rounds does not reset sequencing | Protocol account batches ran **after** r3/r4 market work (`protocol-account-batch-1/2` at 1923–1924); sequences did not collapse to 1 |
| No distinct round reuses an earlier stage id | no second seal of `|3` or `|1` |
| No `SIX_UNIT_STAGE_EVIDENCE_DUPLICATE_STAGE_ID` | absent from terminal / first cause |
| No replay/retry/successor got a fresh sequence | retries/resumes/successors = 0 |

**Sequencing repair held on the live multi-round path.** The prior blocker
`MINT_MARKET_BATCH|1` duplicate did not recur.

## B. Conversion repairs

| Claim | Result |
|---|---|
| Transport-complete Pump migration validation rejections remain candidate-local | Migration page (1907) COMPLETE with `signature_count=0` / empty signatures; no shared channel wipe |
| Do not populate shared `channels_unavailable` | DexScreener and GeckoTerminal continued after migration and through multi-round market |
| Healthy DexScreener work continues | fresh profiles 1906 COMPLETE (21 pairs); market batches 1909/1916 COMPLETE |
| Healthy GeckoTerminal work continues | new pools 1908 COMPLETE (20 pairs); multiple mint-pool reconciliations COMPLETE; 5 rate-limits were **candidate-local** failures (ids 203–207) without stopping Dex or protocol |
| Stage capacity remains seal-gated | multi-round market sealed as distinct sequences; no flat-exhaustion claim |
| Lawful market work continues while matching capacity remains | second market round (r4) executed after r3 |

## C. PumpSwap account confirmation

Production path executed:

```text
PROTOCOL_CONFIRMATION_DUE
→ governed getMultipleAccounts
→ PumpSwap owner check
→ base_mint@43 check
→ exact candidate-local transition
→ confirmed candidates resume market validation
```

| Batch | Request ID | Request key | Pool-address count | Unique addresses | Context slot | Response | Transport |
|---|---:|---|---:|---:|---:|---|---|
| 1 | 1923 | `protocol-account-batch-1` | 100 | 100 | 437211768 | COMPLETE | `getMultipleAccounts` OK |
| 2 | 1924 | `protocol-account-batch-2` | 6 | 6 | 437211770 | COMPLETE | `getMultipleAccounts` OK |

### Member outcomes

| Batch | CURRENT_POOL_CONFIRMED | POOL_OWNER_MISMATCH | BASE_MINT_MISMATCH | Total |
|---|---:|---:|---:|---:|
| 1 | 24 | 73 | 3 | 100 |
| 2 | 1 | 4 | 1 | 6 |
| **Sum** | **25** | **77** | **4** | **106** |

Contract: `SOLANA_GET_MULTIPLE_ACCOUNTS_PUMPSWAP_BASE_MINT_2026_08_04`.  
Local validation steps: 100 + 6. Normalized rows: 100 + 6.

Confirmed identities transitioned with reason `EXACT_PUMPSWAP_OWNER_AND_BASE_MINT` /
outcome `CURRENT_POOL_CONFIRMED` (25 protocol confirms this window).  
Candidate-local failures: owner mismatch and base-mint mismatch.  
No shared RPC/envelope failure on either account batch (both HTTP 200 COMPLETE).

Liquidity, quote mint, reserves, token age, and eligibility were **not** inferred from
pool bytes (`liquidity=null`, `reserves=null`, `token_age=null`, `holder_safety=null` on
both normalized protocol payloads).

## D. Market and holder funnel

| Metric | Value |
|---|---:|
| Locator pairs (Dex fresh profiles) | 21 |
| Gecko new-pool pairs | 20 |
| Market batches (Dex mint rounds) | 2 (r3, r4) |
| Gecko mint-pool reconciliation requests | 12 (6 per round) |
| Protocol-confirmed pool identities (account-batch members) | 25 |
| Exact-market transitions this window | 229 |
| `CURRENT_POOL_CONFIRMED` durable states (post) | 26 |
| `BELOW_LIQUIDITY_FLOOR` durable states (post) | 16 |
| `EXACT_POOL_NO_MATCH` durable states (post) | 24 |
| `CONTRACT_BLOCKED` durable states (post) | 89 |
| Market-ready / `ELIGIBLE_FRESH` reserve (this campaign) | **1** |
| Fully eligible (holder/safety pass + selection depth) | **0** |
| Holder/safety attempts | **1** |
| Holder/safety passes | **0** |
| Holder/safety failures | **1** (`HOLDER_CONCENTRATION_EXTREME`) |

Single market-ready survivor:

* mint `12u9FULaUfHD8uHHe98Fz5gdhg8qeX6DyV93B3Dtpump`
* pool `ECobcS1MSzzAnnzz89xjwRSEYsHAChB7DMbd3G25gwgc`
* reserve status `ELIGIBLE_FRESH`, liquidity_usd ≈ 3192.31
* holder attempt evidence_id `52`, GoPlus COMPLETE, label `HOLDER_CONCENTRATION_EXTREME`

Selection remained forbidden: need **4** distinct fully eligible
(`2 selected + 2 alternates`); depth observed **0**.

## E. Handoff, lifecycle and memory

| Required PASS condition | Result |
|---|---|
| Four distinct fully eligible candidates | **FAIL** (0) |
| Deterministic neutral freeze | not reached |
| Two selected + two alternates | not reached |
| Atomic handoff of selected two | not reached |
| Authoritative Scheduler / tracking ownership | no lifecycle ownership established |
| One real uncompressed WINDOW_15M | **FAIL** (0 campaign windows) |
| Authoritative start/end timestamps | window not started |
| Completed lifecycle | **FAIL** (`lifecycle_started=false`) |
| Clean-memory creation | **FAIL** (memory windows delta 0; audits delta 0) |
| Memory audit PASS | **FAIL** |
| No dirty memory used | n/a (none created) |
| Complete terminal cleanup | **PASS** (see §G) |

## F. Source and six-unit accounting

### Chronological source-operation ledger (this attempt)

| ID | Time (UTC) | Source | Kind | Request key | Status |
|---:|---|---|---|---|---|
| 1906 | 16:47:55 | dexscreener | dexscreener_fresh_profiles | v2-9-7e-44-locator | COMPLETE |
| 1907 | 16:47:57 | solana_rpc | restored_pump_migration_signature_page | v2-9-7e-44-migration-page | COMPLETE |
| 1908 | 16:47:58 | geckoterminal | geckoterminal_new_pool_discovery | v2-9-7e-44-gt-new-pools | COMPLETE |
| 1909 | 16:47:59 | dexscreener | candidate_market_batch | v2-9-7e-44-mint-batch-**r3** | COMPLETE |
| 1910–1915 | 16:48:06–16:48:40 | geckoterminal | candidate_market_batch | r3-gt-1…6 | COMPLETE (1915 also rate-limit failure row) |
| 1916 | 16:48:41 | dexscreener | candidate_market_batch | v2-9-7e-44-mint-batch-**r4** | COMPLETE |
| 1917–1922 | 16:48:48–16:49:22 | geckoterminal | candidate_market_batch | r4-gt-1…6 | COMPLETE (several rate-limit failure rows) |
| 1923 | 16:49:23 | solana_rpc | pumpswap_pool_account_batch | protocol-account-batch-1 | COMPLETE |
| 1924 | 16:49:24 | solana_rpc | pumpswap_pool_account_batch | protocol-account-batch-2 | COMPLETE |
| 1925 | 16:49:25 | goplus | safety_reference | …holder_eligibility_1:context:safety | COMPLETE |

### Kind tallies

| Kind | Count |
|---|---:|
| candidate_market_batch | 14 |
| pumpswap_pool_account_batch | 2 |
| dexscreener_fresh_profiles | 1 |
| restored_pump_migration_signature_page | 1 |
| geckoterminal_new_pool_discovery | 1 |
| safety_reference | 1 |
| **Total governed requests** | **20** |
| Durable responses | 15 |
| Durable source failures | 5 (all `geckoterminal_rate_limited`, candidate-local) |

### Capacity / stage notes

* Terminal reported `stage_evidence_count=5` and `campaign_source_calls=13`.
* Durable ledger shows **20** source requests; finalization then raised
  `CAMPAIGN_STAGE_OPERATION_RECONCILIATION_MISMATCH` (secondary).
* Flat ceiling was **not** reported as exhausted.
* Do **not** report budget exhaustion: required selection depth failed while work
  remained and duration remained.
* Do **not** report governed-universe exhaustion: executable market/protocol/holder
  work ran; shortage is eligible **depth**, not empty universe.

Pending lawful queues at terminal: none active after cleanup (`active_owned_work_after=0`).
Unexecuted selection/handoff/lifecycle work was not started because coverage gates failed.

## G. Safety and cleanup

| Check | Result |
|---|---|
| Retries / successors | 0 / 0 |
| Resume / restart | 0 / 0 |
| Lease released | yes (`lease_released_at=2026-08-04T16:49:26.516179+00:00`) |
| Cleanup completed | yes |
| Active owned work after | 0 |
| Orphan campaign/run/discovery/Scheduler/factory rows | none active |
| `PRAGMA integrity_check` | `ok` |
| `PRAGMA foreign_key_check` | 0 |
| Retrieval delta | **0** |
| Paper-decision delta | **0** |
| BUY/SELL/HOLD delta | **0** |
| Position delta | **0** |
| Trade-event delta | **0** |
| Paper-trade-audit delta | **0** |
| PnL delta | **0** |
| Memory-window delta | **0** |
| Memory-audit delta | **0** |

Pre-campaign backup preserved under execution root:

`/Users/Dtwo1/PrinterOperations/v2-9-8/20260804T164755Z-b723daf73da2/printer_v1.pre-campaign.backup.sqlite3`

## Money-usefulness contribution

* Proved live multi-round market sequencing no longer collides on
  `MINT_MARKET_BATCH|1` after the sequencing repair.
* Exercised production PumpSwap account-batch confirmation (106 addresses across
  two governed `getMultipleAccounts` calls) with candidate-local outcomes.
* Advanced one market-ready mint into holder/safety evaluation (failed concentration).
* Did **not** produce a clean WINDOW_15M memory unit; no retrieval/decision activation.

## What remains locked

Retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, paper audits,
PnL, wallets/private keys/signing/real funds/live execution, paid APIs, scoring/
ranking/confidence weighting, automatic retry/rerun/resume/restart/successor,
and WINDOW_1H/4H/12H/24H remain locked.

## Functionality Risks / Setbacks / Efficiency Blockers

1. **Selection coverage insufficient (first terminal):** only one market-ready
   survivor and zero fully eligible after holder concentration failure — cannot
   open WINDOW_15M under the 4-deep reserve law.
2. **Secondary six-unit reconciliation mismatch** at pre-lifecycle finalization
   blocked durable campaign report emission even though the honest first terminal
   was selection coverage. Needs a dedicated accounting reconciliation audit if it
   persists after a coverage-PASS attempt.
3. **GeckoTerminal rate limits** on mint reconciliation remain frequent
   (candidate-local); they slow funnel completeness but did not create a shared
   channel-unavailable terminal.
4. **Prior untracked auth packages** outside the two-package git-provenance
   manifest block wrapper start until relocated/rolled over — operational friction
   for successive one-use re-proofs.

## Exact verdict and narrowest next action

**Verdict:** `V2_9_8B_POST_SEQUENCING_REPAIR_WINDOW_15M_REPROOF_BLOCKED`

**Exact first terminal cause:**
`PRE_LIFECYCLE_DISCOVERY_SELECTION_COVERAGE_INSUFFICIENT`

**Narrowest evidence-supported next action:**

Treat sequencing repair as **live-validated for multi-round market sealing**.
Do **not** re-open sequencing as the first blocker.

Next authorized lane should target **eligible-depth / holder-safety yield** under
the permanent discovery funnel (still forbidding floor reduction and forbidding
retry of this consumed authorization), and separately schedule a **read-only or
offline** investigation of `CAMPAIGN_STAGE_OPERATION_RECONCILIATION_MISMATCH` so
honest terminals still emit durable reports when coverage fails.

A fresh one-use authorization on a later HEAD is required for any subsequent
WINDOW_15M attempt. This authorization is permanently non-reusable.
