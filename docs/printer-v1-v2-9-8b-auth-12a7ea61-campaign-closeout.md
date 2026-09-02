# Printer V1 — V2-9.8B Authorization 12a7ea61 Campaign Closeout

Status: **CLOSED PASS**

Evidence-audit verdict:

`V2_9_8B_AUTH_12A7EA61_POST_APPLICATION_EVIDENCE_AUDIT_PASS`

Closeout verdict:

`V2_9_8B_AUTH_12A7EA61_CAMPAIGN_CLOSEOUT_PASS`

Scope-propagation repair live-proof verdict:

`CAMPAIGN_SOURCE_REQUEST_SCOPE_PROPAGATION_REPAIR_LIVE_PROOF_PASS`

Primary later-cycle classification:

`COMMITTED_CODE_DEFECT`

Subtype:

`LATER_CYCLE_COOPERATIVE_MINT_MARKET_BATCH_DUPLICATE_TRANSPORT_IDENTITY`

This closeout is documentation/governance only. It does not repair production
code, reuse the consumed authorization, run Printer, or prepare another
authorization.

## Exact execution identity

- authorization: `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260901T203521Z_12a7ea61`
- authorization SHA-256: `b8112ab756e46c60bac82d486a0de113113cb3b266690f2850f2d6c7698a96f3`
- authorization state: `CONSUMED / CHILD_EXITED_ZERO / PERMANENTLY NON-REUSABLE`
- authorized branch: `assistant/v2-9-8b-campaign-source-request-scope-propagation-repair`
- authorized / actual execution HEAD: `91c757c542d8098ecf7b244769061f333dcfc21f`
- wrapper execution: `20260901T205859Z-89a1f9b9b2bd`
- campaign: `20260901T205859Z-89a1f9b9b2bd-campaign`
- run: `20260901T205859Z-89a1f9b9b2bd-campaign-run`
- Cycle 1: `20260901T205859Z-89a1f9b9b2bd-cycle`
- proposed Cycle 2: `20260901T205859Z-89a1f9b9b2bd-cycle-2` (never admitted)
- supervision: `20260901T205859Z-89a1f9b9b2bd-supervision`
- factory run: `29230b78-9849-4d92-befa-04725a2ab0d7`
- child PID: `92314`
- child result: `CHILD_EXITED_ZERO`
- process exit: `0`
- campaign terminal status: `OPERATIONAL_CAMPAIGN_TERMINAL`
- wrapper `success`: `true`
- wrapper `terminal_category`: `OPERATIONAL_COMMAND_COMPLETE`
- retries / reruns / resumes / restarts / successors: all `0`
- source calls reported by child terminal: `15`
- scheduler runtime calls: `751`

The authorization is permanently consumed. It must not be retried, rerun,
resumed, restarted, reused, or treated as successor authority. It must enter
every future prior-authorization non-reuse trust root.

## Application / authorization evidence

Marker path:

`/Users/Dtwo1/PrinterOperations/v2-9-8/four-token-standard-four-hour-one-shot-applications/V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260901T203521Z_12a7ea61/application-marker.json`

Independently verified:

- marker exists; SHA-256 `fb1181a4a281b84a80ea94bdd73c5f0ba57557b74ed7df3d335bc6d0c9cd516b`;
- authorization SHA-256 matches the frozen package;
- exactly one application; `allowed_invocation_count = 1`;
- marker consumed at `2026-09-01T20:58:56.789413+00:00`;
- wrapper terminal valid; child terminal valid; child stderr empty;
- repository HEAD binding `91c757c542d8098ecf7b244769061f333dcfc21f`;
- retry/rerun/resume/restart/successor all forbidden and all observed `0`.

The marker was not modified.

## Report path / SHA

Path:

`/Users/Dtwo1/PrinterOperations/v2-9-8/20260901T205859Z-89a1f9b9b2bd/reports/20260901T205859Z-89a1f9b9b2bd-report.campaign-report.json`

Fresh SHA-256:

`353df134ec73c9f36919ca1379e0f3f0042303b52304e209502786b6da776b12`

Matches the child-terminal `terminal_report_sha256` and the expected closeout
SHA.

## Post-campaign authoritative DB

Path: `data/printer_v1.sqlite3`

Fresh identity, byte-identical to the child-terminal `database_identity_after`:

- SHA-256: `a3172e04f99ef410ba66eb4e2928b5b4edbdd7dfad4d713fcd1605fa3b702a8c`
- size: `154796032`
- inode: `1230526`
- mtime_ns: `1788310792540112946`
- migration count/head: `62` / `062_pre_admission_attempt_evidence.sql`
- integrity: `ok`
- foreign-key violations: `0`
- journal mode: `delete`
- sidecars: none

Pre-run DB SHA-256 was `ca4c678b6164ad2aad36ed6140a06d96dc409d1cd3b64c40b17bce78a42b01dc`.
Campaign writes were authorized. Do not restore the pre-run database.

This post-campaign identity is the historical baseline from this closeout
forward.

## Post-run durable zero-state / quiescence

Canonical ownership domains are zero. Child-terminal
`active_owned_work_after = 0` matches durable DB state.

Verified:

- campaign / run / Cycle 1: `TERMINAL_COMPLETED`;
- supervision: `TERMINAL`, lease released, cleanup complete;
- lease lock file absent;
- campaign and candidate-acquisition leases released/terminal;
- no PENDING/RUNNING scheduler jobs, factory runs/steps, discovery work, or
  pre-admission attempts;
- Cycle 2 pre-admission attempt is historical `FAILED`, not active;
- no operational Printer processes;
- no SQLite sidecars.

Historical terminal rows, including Cycle 1 `MANUAL_REVIEW` slots and the
failed Cycle 2 pre-admission attempt, remain historical residue and must not
be mutated to manufacture a cleaner report.

## Wrapper success versus campaign-contract success

### Wrapper success

The one-shot wrapper completed normally. The child exited `0`. Cleanup and
lease release completed. `success = true` and
`terminal_category = OPERATIONAL_COMMAND_COMPLETE` are correct under the
existing operational-terminal contract: later-cycle supply failure is handled
as a bounded campaign terminal, not a child crash.

### Campaign-contract success

The intended Standard-4H envelope is two cycles, exactly two concurrent slots,
and up to four distinct through-4h identities.

Observed:

- two cycles were attempted;
- Cycle 1 was admitted (2 tokens);
- Cycle 2 was not admitted;
- distinct admitted identities: `2`;
- the campaign never achieved four through-4h identities;
- Cycle 1 completed `WINDOW_15M -> WINDOW_1H -> WINDOW_4H` for both tokens;
- later-cycle supply did **not** legitimately exhaust the market; it aborted on
  a duplicate-transport accounting exception while Cycle 2 was still discovering.

`success = true` is wrapper-correct. It is not campaign-contract completion of
the 4-token envelope.

## Cycle 1 reconstruction

Cycle ID: `20260901T205859Z-89a1f9b9b2bd-cycle` (ordinal 1).

Admission: yes. Terminal: `COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED`.

Freeze-ready:

- freeze-ready depth: `6` (`complete_count = 6`, `input_count = 6`);
- `4 freeze-ready -> 2 selected + 2 report-only alternates` was satisfied
  (depth 6 exceeds the minimum of 4);
- 36 candidates observed; 6 `ELIGIBLE_FRESH`; 28 `EXCLUDED`; 2 `REMOVED`.

Selected pair:

1. mint `44HivRciwQyZwzjL5DduNyb14Pq6cmnKNm5uz9c4fLAM` / pool
   `2fsFaaJwVf9KZLu7qCdXsH32rYY3FAdCcznANcG845PM` / token `109` / pair `113`
   / slot `slot-...-cycle-1`;
2. mint `44XweXSCVwtMQ2twmXWQdRPwS1QrPGV2aj76YPLNpump` / pool
   `G2qxhNpdtDtLcuTrwaCZrcq97i6KgxMYLiJtNUVRcwTf` / token `110` / pair `114`
   / slot `slot-...-cycle-2`.

Report-only alternates:

1. `3D62gTtHREVwyjTC2izpXLdcwgKjtVvsQEuv1FHtpump` /
   `4zMPdsJ4dw3EqF7tNzXvz2kpBrQpPZh1jwDJA15742yu`;
2. `3cRRwsW47pxYF2pbLKjGJhp1u2nBajfJLgTqeCaBpump` /
   `EwF6y6gENgRkFZPHKp3WUH4UknniYtsTbSbQF8Xv5xAN`.

Additional freeze-ready (not selected, not alternates):

- `KxHGHaXXb1rtkUvZ4SNG5Xv1n1fNWJv4nWEBndppump`;
- `CdWvQiREpPJkRUFPpBirV8ZMipMkevpMmFRhuvEpump`.

Provenance: `FRESH_AGGREGATOR_PROTOCOL_CONFIRMED`. Liquidity was exact and
above the $3,000 floor. Cycle 1 source requests `4275`–`4289` were current-run
rooted (`v2-9-8b-window15m-20260901T205859Z-89a1f9b9b2bd-...`). Campaign source
request scope reconciliation status `OK`;
`request_scope_version = PRINTER_V1_CAMPAIGN_SOURCE_REQUEST_SCOPE_V1`.

Lifecycle per selected token:

| Token | 15m campaign window | 15m memory | 1h campaign window | 1h memory | 4h campaign window | 4h memory |
| --- | --- | --- | --- | --- | --- | --- |
| 109 | `CLEAN_PROMOTED` / episode 115 `DUMP` | window `PARTIAL_MEMORY`; episode `CLEAN_MEMORY` | `CLEAN_PROMOTED` / episode 117 `DEAD_TOKEN` | window `PARTIAL_MEMORY`; episode `CLEAN_MEMORY` | `NO_PROMOTION` / no episode | window `PARTIAL_MEMORY` |
| 110 | `CLEAN_PROMOTED` / episode 116 `CONSOLIDATION` | window `PARTIAL_MEMORY`; episode `CLEAN_MEMORY` | `CLEAN_PROMOTED` / episode 118 `DEAD_TOKEN` | window `PARTIAL_MEMORY`; episode `CLEAN_MEMORY` | `NO_PROMOTION` / no episode | window `PARTIAL_MEMORY` |

Coverage: 15m 16/16, 1h 24/24, 4h 61/61, all `CADENCE_POLICY_PASS` /
`COVERAGE_PASS`. Standard 4h progression attempt
`HANDOFF_COMMITTED` with both tokens `HANDOFF_CREATED`. Continuation to 4h was
legitimate. 4h closed `NO_PROMOTION` after full collection; that is the
intended stop, not ineligibility.

Support-only `WINDOW_5M_MICRO_EVENT` rows 260 and 261 closed
`SUPPORT_EVIDENCE`. No 12h/24h windows.

## Cycle 2 reconstruction

Cycle 2 was attempted and not admitted.

- attempt ID: `pre-admission:...:c0002`
- proposed cycle ID: `20260901T205859Z-89a1f9b9b2bd-cycle-2`
- proposed ordinal: `2`
- scheduler job: `3262` `PRE_ADMISSION_DISCOVERY_SELECTION`
- created: `2026-09-01T21:04:00.707033+00:00`
- terminal: `2026-09-01T21:16:54.634773+00:00` (callback instant; wall-clock
  work continued through request `4349` at `21:16:59Z`)
- attempt state: `FAILED`
- first terminal cause: `LATER_CYCLE_SUPPLY_EXCEPTION_CAMPAIGNSIXUNITERROR`
- selected count: `0`
- frozen pair items: `0`
- consumed cycle ID: none
- no Cycle 2 campaign/run/cycle/slot rows exist

Cooperative claims 1–10 yielded `ACQUISITION_QUANTUM_YIELDED` through:

`AUXILIARY_FRESH_INTAKE` → `AUXILIARY_LIQUIDITY_BACKUP` (including one
GeckoTerminal `geckoterminal_rate_limited` on request `4309` / failure `398`)
→ `AUXILIARY_PROTOCOL_CONFIRMATION` → `DIRECT_MIGRATION` → `MARKET_DISCOVERY`.

Cycle 2 governed requests `4300`–`4313`, `4348`, `4349` were current-run
rooted under
`v2-9-8b-window15m-20260901T205859Z-89a1f9b9b2bd:c0002-...`.
`CampaignSourceRequestScope` was built for Cycle 2. The previous missing-scope
terminal did not recur.

Two fresh/disjoint candidates were **not** admitted. Discovery was still in
`MARKET_DISCOVERY` when accounting failed.

## Exact `CampaignSixUnitError` cause chain

Stdout/report/job error persist only the class-name wrapper
`LATER_CYCLE_SUPPLY_EXCEPTION_CAMPAIGNSIXUNITERROR`. No traceback was printed.
The nested message was reconstructed from durable Cycle 2 source responses plus
the production ingest path.

### Outer wrapper

File: `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`

- catch: `except Exception as supply_exc` in `_one_shot` later-cycle callback;
- identifier: `_safe_supply_exception_identifier`;
- because `CampaignSixUnitError` is a `RuntimeError` without `.code`, the
  identifier becomes `LATER_CYCLE_SUPPLY_EXCEPTION_` + class name.

This wrapping is a secondary representation loss. It is not the root failure.

### Producer

Later-cycle `production_later_supply` → `build_later_cycle_graduated_supply` →
permanent MARKET_DISCOVERY cooperative quantum →
`run_dexscreener_batch_market_resolution` → cycle-2 `stage_evidence_sink`.

### Durable collision

Request `4348` (`...:c0002-mint-batch-r1`) and request `4349`
(`...:c0002-mint-batch-r2`) have byte-identical response SHA-256
`3d8f40876c29fa01fff1fe4ed2e2c3c2436b95ae0a87583d28a1aaef3b78d3a5`
and the same transport identity:

```text
stage=MINT_MARKET_BATCH
source_name=dexscreener_pair
governed_request_kind=candidate_market_batch
method_or_endpoint=GET /tokens/v1/solana/{mints}
within_request_ordinal=1
target_category=due_mints
target_identity=AQi9C9ak1TKTse3kSFKANybEhZmaVpTab1ukhsEhpump
```

Claim 10 sealed `MINT_MARKET_BATCH|1` into the in-process Cycle 2 six-unit
owner and yielded. Claim 11 re-issued the same due mint as `MINT_MARKET_BATCH|2`.
Canonical transport identity keys exclude stage sequence and request id, so
the second ingest collides.

### Ingest raise

File: `src/printer_v1/sources/campaign_six_unit_accounting.py`

- class: `CampaignSixUnitOwner`
- function: `ingest_stage_evidence` / `_ingest_stage_evidence_impl`
- `candidate_ledger.extend(stage_ledger)` raises `MeasuredTransportError("DUPLICATE_TRANSPORT_IDENTITY")`
- wrapped as `CampaignSixUnitError("SIX_UNIT_STAGE_EVIDENCE_DUPLICATE_TRANSPORT:DUPLICATE_TRANSPORT_IDENTITY")`

The six-unit duplicate detector behaved according to contract. The producer
violated uniqueness by repeating the same due-mint transport across cooperative
MARKET_DISCOVERY quantums. Cooperative resume rehydrates evaluated mints from
fresh MOE inventory only; market-batched-but-not-yet-MOE mints are forgotten.

## Classification

Primary:

`COMMITTED_CODE_DEFECT` /
`LATER_CYCLE_COOPERATIVE_MINT_MARKET_BATCH_DUPLICATE_TRANSPORT_IDENTITY`

Producer → path → divergence → consequence is proven above.

Not used:

- `EXPECTED_OPERATIONAL_BLOCKER__NO_CODE_CHANGE` — Cycle 2 was still discovering;
  it did not reach honest `NO_PAIR` / `DURATION_EXHAUSTION` / freeze-ready
  shortage.
- `PROVIDER_OR_SOURCE_LIMITATION__NO_CODE_CHANGE` — GeckoTerminal rate-limit on
  `4309` is a real Cycle 2 fact, not the terminal cause. DexScreener mint-batch
  `4348`/`4349` both completed.
- `TERMINAL_OR_ACCOUNTING_REPRESENTATION_DEFECT` — secondary wrapping loss
  exists, but operational behavior also violated the uniqueness contract.
- `INSUFFICIENT_EVIDENCE_TO_CLASSIFY` — durable identical payloads prove the
  collision.

`CampaignSixUnitError` is a fail-closed accounting exception wrapping the real
root: later-cycle cooperative market-batch identity replay. It is not an
expected later-cycle supply block.

No production code was changed in this closeout. The next lane is design /
specification, not another campaign.

## Scope-propagation repair live proof

`CAMPAIGN_SOURCE_REQUEST_SCOPE_REQUIRED` is absent from stdout, report, child
terminal, and this campaign's source-request keys.

Cycle 1 freeze-ready reconciliation used authentic
`CampaignSourceRequestScope` (`status = OK`, 15 durable requests, zero
mismatches, current-run root
`v2-9-8b-window15m-20260901T205859Z-89a1f9b9b2bd`). Cycle 2 later-cycle supply
also built a scope and rooted 12 requests under `:c0002`. No Source Governor
bypass occurred. Governed requests remained current-run rooted.

Verdict:

`CAMPAIGN_SOURCE_REQUEST_SCOPE_PROPAGATION_REPAIR_LIVE_PROOF_PASS`

This does not imply broader later-cycle perfection.

## Memory usefulness

New durable memory for this campaign's identities, not for retrieval or
decisions:

- token snapshots: 101 per selected token (15m 16 + 1h 24 + 4h 61);
- safety / liquidity / trading-flow / chart snapshots: 1 each per token;
- market-regime snapshots during the run: 6;
- Solana chain-heat snapshots during the run: 6;
- micro-events: 2 (`WINDOW_5M_MICRO_EVENT` support-only);
- episodes: 115–118 with fingerprints 79–82;
- 4h windows 264–265: closed, no episode/fingerprint.

Clean / dirty / ineligible:

- campaign 15m and 1h windows: `CLEAN_PROMOTED`;
- episode rows 115–118: `CLEAN_MEMORY` / `CLEAN_DATA` / `do_not_train = 0`;
- memory-window rows 258–265: `PARTIAL_MEMORY` / `CLEAN_DATA`;
- 4h: `NO_PROMOTION` / not created as clean episodes;
- 5m: `SUPPORT_EVIDENCE` only;
- no dirty-memory promotion into retrieval.

Report `clean_memory_outcome_pass = false` because 4h windows lack
episode/fingerprint linkage. That matches 4h `NO_PROMOTION`. Retrieval remains
locked. No this-campaign retrieval queries, paper decisions, positions, trades,
audits, or PnL.

## Source Governor / Central Scheduler

No bypass. Cycle 1 used 15 governed source requests. Cycle 2 used 12 additional
governed requests under the later-cycle scope. Scheduler job `3262` failed
closed with `max_retries = 0`. Wrapper retries remain 0. `retry_count = 1` on
job 3262 is the fail-job increment, not a relaunch.

## Permanent V1 locks preserved

Solana-only; Solana memecoin-only; paper-only. No live wallet, private keys,
signing, real funds, or live execution. No paid API dependency. No
scoring/ranking/confidence/weighted logic. No embeddings/vectors. No retrieval
activation. No BUY/SELL/HOLD. No positions/trades/audits/PnL. No Source
Governor or Central Scheduler bypass. `WINDOW_5M_MICRO_EVENT` support-only.
`WINDOW_12H` / `WINDOW_24H` locked.

## Next permitted lane

```text
LATER-CYCLE COOPERATIVE MINT-MARKET-BATCH DUPLICATE TRANSPORT IDENTITY — DESIGN / SPECIFICATION ONLY
```

Follow:

```text
audit/readiness -> design/specification -> implementation if approved -> bounded proof/test -> closeout
```

This closeout is the audit. Do not implement yet. Do not run Printer. Do not
prepare or apply another authorization. Do not retry/rerun/resume/restart
`12a7ea61`.

`V2_9_8B_AUTH_12A7EA61_CAMPAIGN_CLOSEOUT_PASS`
