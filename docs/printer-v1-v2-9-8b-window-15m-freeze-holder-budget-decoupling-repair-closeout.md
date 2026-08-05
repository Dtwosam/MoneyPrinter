# Printer V1 — V2-9.8B `WINDOW_15M` Freeze / Holder-Budget Decoupling Repair Closeout

**Date:** 2026-08-05  
**Lane:** `V2-9.8B — WINDOW_15M Memory-Observation Freeze / Holder-Budget Decoupling Repair`  
**Branch:** `agent/v2-9-8b-window-15m-freeze-holder-budget-decoupling-repair`  
**Baseline branch:** `agent/v2-9-8b-window-15m-continuous-supply-evidence-repair`  
**Baseline HEAD:** `4f4bcade3c84771342bb4132cf4cb179d8daf517`  
**Safe implementation checkpoint:** `e43bfabdbd27dea0928ddaadcc2cc6772ee648ea`  
**Closeout commit:** the final branch HEAD reported with the operator return; a Git commit cannot contain its own commit identity.

## Final verdict

`V2_9_8B_WINDOW_15M_FREEZE_HOLDER_BUDGET_DECOUPLING_REPAIR_BLOCKED`

The approved request/transport and observation/holder decoupling repair produced four
observation candidates and reached a two-slot handoff. The required uninterrupted
wrapper-to-memory proof did not reach a `WINDOW_15M` window, clean memory, or a
fingerprint. The exact first terminal category after handoff was:

`SAFE_STOP_PREFLIGHT_FAILED`

No retry, rerun, resume, restart, successor, broad suite, real authorization, provider
contact, or authoritative-database mutation followed.

## Blocker classification

`COMMITTED_CODE_DEFECT` justified the narrow implementation because permanent
production admission passed `ledger.candidate_cap()` into graduated admission even
though holder evidence is contextual for memory observation.

The continuous proof then exposed a later boundary:

- four market/protocol candidates survived;
- two token slots were created;
- final campaign accounting reported 16 governed source calls;
- the campaign six-unit owner still reported the pre-holder 17 transport identities;
- no window was created;
- runtime stopped `SAFE_STOP_PREFLIGHT_FAILED`.

The retained proof summary does not preserve the detailed preflight reason or holder
diagnostics. The request/owner delta strongly indicates that the attempted holder
request/transport was not incorporated into the campaign six-unit owner before
full-run preflight, but this attribution is an inference, not a retained categorical
subreason. A new repair is not authorized by this closeout.

## What was built

- Immutable `PreHolderBudgetSnapshot` projecting existing durable request-manifest,
  campaign-owner transport, and action-local transport evidence.
- Fail-closed rejection for duplicate transports, missing campaign ownership,
  manifest/request mismatch, count-without-identities, and stage/campaign identity
  mismatch.
- `build_ledger_from_exact_counts()` with independent governed-request and measured
  transport counts.
- Legacy `build_ledger()` compatibility only on the explicit equality path.
- Permanent admission separated from `ledger.candidate_cap()`; legacy admission is
  unchanged.
- Non-mutating permanent holder-attempt decisions preserving:
  - operation ceiling 45;
  - zero-transport charge 9;
  - reservations 2 + 4;
  - worst-case pre-attempt requirement 5;
  - permanent holder-stage ceiling 8.
- Incremental holder collection with categorical pre-request budget completion and
  zero requests for unattempted candidates.
- Extended holder result diagnostics for evaluated/unattempted identities, budget
  state, before/after ledgers, request/transport counts, source IDs/coverage, and
  per-attempt budget trace.
- Exact budget-bound unknown holder context and actual-holder-pass-only
  `fully_eligible`.
- Operator design added byte-identically (SHA-256
  `f05df87f2bf6118e99b724e7d785092ca1bc95433b3f76a15c24ebb27a68488c`).

## Request-count versus transport-count reconciliation

### Pre-holder snapshot

The continuous proof reached the exact pre-holder boundary with:

| Fact | Value |
|---|---:|
| Distinct governed request count | 15 |
| Unique measured transport identity count | 17 |
| Zero-transport validation charge | 9 |
| Charged operations | 26 |
| Snapshot reservations | 2 + 4 |
| Available before holder reservation | 13 |
| Holder worst-case admission requirement | 5 |
| Holder-derived candidate cap | 2 (not used for permanent observation admission) |
| Permanent observation admission cap | 8 |
| Actual valid observation universe | 4 |

The exact request-ID and transport-identity arrays were validated in-process but were
not retained by the historical continuous-proof harness. They must not be recreated
from row counts after the fact.

### Holder and terminal accounting

| Fact | Value |
|---|---:|
| Final campaign governed source calls | 16 |
| Campaign six-unit source transports | 17 |
| Final local validations | 19 |
| Final Scheduler work items | 10 |
| Final lifecycle transport reservations | 0 |
| Final normalized source rows | 128 |
| Final source response bytes | 24,934 |

The historical proof harness did not retain `holder_context`,
`holder_attempt_budget_trace`, or the detailed terminal preflight report. Therefore
the exact per-attempt before/after budgets and evaluated/unattempted mint arrays are
not available for a truthful closeout. This is a proof limitation and part of the
BLOCKED verdict; no identities are fabricated.

## Candidate universe and freeze

The disposable ordinary supply contained these four exact market/protocol-qualified
mint/pool identities:

| Mint | Pool |
|---|---|
| `6m2GokQpwZoe2oPQgxKbTmg1doKdqa4iZ2cZbWu2V2ks` | `E3GiKEcFL24tD65Dxatf89usogA58DMWDsEbWdTJrYpY` |
| `7t3DbSJzyd9zyaspC9ocWbdPnGUbWRF9YNMBFy1G69yc` | `VuNbRsyNKvtNEV2RCBhXUiVWKWSGzUVn4n2xzjjURvR` |
| `91CeYJiaYP7MPKCg528sRWZwJKmjsSzJW6UtfRAuCwjT` | `vXyyVjC8GtjfUcMth8DQArXYtArvk5vdnfsmBDkUsoE` |
| `FgqpW3Hvshn6K1j3rugbiEHaG9GJ8CaoRTvB8mqaMF7p` | `8TXonTQyy8thegfJr1V7XTXdQfebPRSPDSu6RYC3WJ6M` |

Scheduler evidence retained the two selected handoff identities:

1. `7t3DbSJzyd9zyaspC9ocWbdPnGUbWRF9YNMBFy1G69yc` /
   `VuNbRsyNKvtNEV2RCBhXUiVWKWSGzUVn4n2xzjjURvR`
2. `6m2GokQpwZoe2oPQgxKbTmg1doKdqa4iZ2cZbWu2V2ks` /
   `E3GiKEcFL24tD65Dxatf89usogA58DMWDsEbWdTJrYpY`

The exact alternate ordering was not retained in the proof summary. The remaining two
identities were the alternate universe, but their ordering is not asserted here.

## Continuous proof

**Proof execution ID:**  
`V2_9_8B_WINDOW_15M_FINAL_INTEGRATED_CONTINUOUS_PROOF_V1`

**Retained execution directory:**  
`/Users/Dtwo1/PrinterOperations/v2-9-8/final-integrated-proofs/V2_9_8B_WINDOW_15M_FINAL_INTEGRATED_CONTINUOUS_PROOF_V1_20260805T155633Z`

| Artifact | SHA-256 |
|---|---|
| `proof_summary.json` | `df58a6f63cc89dbff6ee727f4a4560c48a4018c705b0f20cf79afa39d18deab9` |
| `wrapper_terminal.json` | `1742d605de65a00b387830108c7caa42f60ad8a281ae5c7ccf1e915102d310e0` |

Observed proof facts:

- fixture authorization consumed once;
- one child invocation;
- child exit code 0;
- zero automatic retries;
- zero manual reruns, resumes, restarts, or successors;
- zero external network escapes;
- four-candidate supply reached two token slots;
- zero active Scheduler jobs after cleanup;
- zero `WINDOW_15M` rows;
- zero current-run `CLEAN_MEMORY` episodes;
- zero fingerprints;
- `operational_lifecycle_pass=false`;
- `clean_memory_outcome_pass=false`;
- terminal category `SAFE_STOP_PREFLIGHT_FAILED`.

## Tests and checks

| Command / check | Result |
|---|---|
| New focused repair suite | 20 passed |
| New + nearest holder/accounting/manifest/observation suites | 89 passed |
| Python compilation of changed modules/test | PASS |
| `git diff --check` | PASS |
| Continuous wrapper-to-memory proof | 1 failed: two slots, zero windows; `SAFE_STOP_PREFLIGHT_FAILED` |
| Broad regression | NOT RUN — prohibited after continuous BLOCKED |

## Authoritative database before/after identity

| Fact | Before | After |
|---|---|---|
| Path | `data/printer_v1.sqlite3` | same |
| SHA-256 | `ecf0557cf213b44b51f840983e5472a53777f609dee650580d1844e7b01ac2bb` | identical |
| Migration | `52 / 052_memory_observation_eligibility_layers.sql` | identical |
| Integrity | `ok` | `ok` |
| Foreign-key violations | 0 | 0 |
| SQLite sidecars | none | none |
| Active DB process | none | none |

## Money-usefulness contribution

The safe implementation preserves four valid market/protocol observations even when
holder context cannot be collected for all candidates. It prevents holder-source
budget from falsely deleting memory observations, retains truthful unknown context,
and keeps future action blocked unless a real holder pass exists.

No clean-memory money-usefulness outcome was proven continuously because the lifecycle
did not create a window.

## What improved

- The original holder-derived three-or-less admission truncation no longer controls
  permanent observation admission.
- Governed request and measured transport counts are separate.
- Operation charge uses measured transports plus the fixed zero-transport charge.
- Holder budget exhaustion before a new request is bounded completion rather than an
  exception.
- Unattempted holder candidates create no request and retain exact unknown,
  future-action-blocked context.
- The continuous proof advanced from zero slots to two slots.

## What remains locked / not touched

No migration or schema change. No freeze-owner, Scheduler-owner, Source-Governor,
fingerprint-owner, memory-promotion-owner, provider contract, authoritative DB, real
authorization, or live source was changed.

All hard locks remain:

- Solana-only and Solana-memecoin-only;
- paper-only;
- no wallet, private key, signing, funds, or execution;
- no paid API;
- no score, rank, confidence, weight, embedding, or vector;
- no Source Governor or Central Scheduler bypass;
- 5m support-only;
- no production 1h/4h/12h/24h;
- no retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, paper audits,
  or PnL;
- no retry, recovery, or successor.

## Proof limitations

- The uninterrupted wrapper-to-memory PASS requirement was not met.
- The proof retained summary/wrapper artifacts but not the detailed campaign report,
  pre-holder identity arrays, holder attempt trace, evaluated/unattempted mint arrays,
  or alternate ordering.
- Holder-stage measured identities did not appear in the final campaign six-unit
  owner totals despite one additional governed source call.
- No 900-second window, clean episode, canonical fingerprint, outcome, tracking-lane
  fingerprint linkage, or report-only replay equivalence was reached.
- No broad regression is valid or required after the continuous blocker.

## Functionality Risks / Setbacks / Efficiency Blockers

### Functionality risks

- Holder-stage request/transport evidence may still be absent from the campaign
  six-unit owner at full-run preflight.
- Direct owner callers without the public projection seam retain compatibility and do
  not establish production exact-accounting proof.
- The new permanent path is focused-tested but not continuously proven through memory.

### Setbacks

- Continuous proof stopped after handoff and before the first window.
- Required exact per-holder-attempt closeout evidence was not retained by the existing
  proof harness.

### Efficiency blockers

- The continuous wrapper proof is comparatively expensive and consumes a one-shot
  fixture authorization each run.
- The lane forbids another run after the newly exposed blocker.
- A future lane should first perform a read-only retained-evidence/harness and
  holder-stage campaign-accounting audit before any new implementation or proof.

## Next permitted step

Operator review of this BLOCKED closeout and retained artifacts only.

If the operator later authorizes another lane, the nearest compliant work is a
read-only audit/design of `SAFE_STOP_PREFLIGHT_FAILED`, specifically the missing
retained detailed preflight reason and holder-stage request/transport integration into
the campaign six-unit owner. It must not authorize a rerun, real authorization,
provider contact, authoritative DB mutation, retrieval, or financial capability.

