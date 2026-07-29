# Printer V1 V2-9.8B Pump Migration Observation Decoupling Design

Date: 2026-07-29

Depends on:
`docs/printer-v1-v2-9-8b-pump-migration-observation-decoupling-audit.md`

Classification: `DESIGN_GAP`

Design verdict: `V2_9_8B_PUMP_MIGRATION_OBSERVATION_DECOUPLING_DESIGN_PASS`

## 1. Objective and invariants

Separate four evidence channels under one canonical acquisition owner:

1. multi-source candidate nomination;
2. candidate-specific exact Pump migration verification;
3. optional global Pump migration observation; and
4. generic/non-Pump exact-present-pool admission.

The global Pump-program cursor is no longer a universal prerequisite. The
design changes no current cursor, recovery bound, provider budget, capacity,
schema, database, or active runtime.

Permanent invariants:

- Solana-only and Solana-memecoin-only;
- paper-only, with no wallet, key, signing, transaction submission, funds, or
  live execution;
- active Memory Factory capacity exactly two;
- `M=2N` and existing exact-N mechanics unchanged;
- no score, rank, confidence, weighting, quota, or source preference;
- every source operation is Source-Governed and Scheduler-led;
- no guessed migration, pool, quote, program, instruction, PDA, or identity;
- no PumpSwap-presence-only graduation claim;
- no cursor reset, silent checkpoint adoption, or recovery-bound increase;
- no dirty/partial evidence promoted into admission; and
- all memory, retrieval, decision, BUY/SELL/HOLD, position, trade, audit, PnL,
  and other financial locks remain unchanged.

## 2. Canonical architecture

```text
multi-source nomination
-> bounded deterministic cohort M=2N
-> determine candidate lineage branch from exact claims/facts

Pump graduation claimed:
  -> bounded candidate-specific migration locator
  -> finalized exact Pump migrate verification
  -> exact PumpSwap Pool verification
  -> PUMP_GRADUATION_CONFIRMED only if both join exactly

Exact active Pump bonding curve:
  -> exact Pump origin + curve PDA/account proof
  -> PUMP_ORIGIN_CONFIRMED only while complete=false
  -> no global migration prerequisite

No Pump graduation claim:
  -> exact generic/current-pool verification
  -> UNKNOWN_ORIGIN or NON_PUMP_POOL_CONFIRMED
  -> global Pump migration continuity does not block admission

optional global Pump observation:
  -> additional nomination and bounded coverage evidence only
  -> exact hits enter the same candidate-specific verifier
  -> never substitutes for exact candidate migration verification
  -> never universally blocks unrelated candidate branches
```

Candidate-specific proof does not fully replace global discovery. It answers
`does this exact candidate have a supported exact migration?` Global observation
answers `what bounded portion of global activity did Printer observe, and did it
locate additional candidates?` Neither answer can be promoted into the other.

## 3. Final authority model

| Channel | Canonical fact owner | What it proves | What it cannot prove |
| --- | --- | --- | --- |
| nomination | source-specific normalizer under acquisition owner | exact candidate mint and only provider-supported nomination/market facts | Pump lineage, graduation, canonical pool, admission |
| lineage branch selection | candidate-acquisition integration owner, pure categorical logic | which evidence contract applies | source truth, eligibility, preference |
| candidate migration verification | approved Solana RPC transport plus pinned Pump decoder | exact successful finalized `migrate` for one candidate | global continuity, safety, profitability |
| PumpSwap Pool verification | approved Solana RPC plus pinned PumpSwap verifier | exact canonical Pool state and identity | migration without joined `migrate` evidence |
| optional global observation | same acquisition owner, separate optional work/coverage namespace | bounded global coverage and migration locators | candidate proof, absence outside range, universal gate |
| generic/current pool | provider orientation plus exact RPC account owner/executable-program proof | exact supported current pool relationship | Pump origin or graduation |
| certificate/reserve/manifest | candidate-acquisition foundation only | categorical admission and runtime-neutral exact-N result | runtime handoff or financial action |

The existing global observer remains an optional coverage channel and a
diagnostic/audit-only continuity surface. It is retired from active universal
candidate gating. `Optional` does not mean its evidence may be mislabeled: when
run, every request, gap, failure, and positive observation remains governed and
durable.

## 4. Branch determination

Branch determination occurs only after the complete nomination union is
canonicalized and thinned deterministically to cohort `M`. It uses categorical
exact facts, never provider count or market magnitude.

### 4.1 `PUMP_GRADUATION_CLAIMED`

This branch applies when any of the following is present:

- an approved locator explicitly claims a Pump migration for the exact mint;
- optional global observation decodes an exact Pump `migrate` candidate;
- exact Pump origin plus a completed bonding curve requires post-curve proof;
- exact Pump origin is joined to a proposed current PumpSwap graduation pool;
  or
- a stored exact Pump graduation fact is being requalified under the same pins.

It requires exact Pump origin under the existing lineage contract, exact Pump
`migrate`, and exact canonical PumpSwap Pool evidence. A failure cannot fall
back to `UNKNOWN_ORIGIN` or generic pool admission.

PumpSwap program ownership or Pool presence alone does not select this branch.

### 4.2 `PUMP_ACTIVE_BONDING_CURVE`

This branch requires exact Pump creation, derived curve PDA, Pump ownership,
pinned curve discriminator/prefix, decoded quote, and `complete=false`. It does
not require migration verification or global migration continuity.

If the curve is complete, the candidate must use the Pump graduation branch and
fail closed until that branch passes.

### 4.3 `NO_PUMP_GRADUATION_CLAIM`

This branch applies when no exact Pump claim conflicts with it. It requires an
exact current pool/pair, exact provider base/quote orientation, exact candidate
mint, allowed quote, exact pool account owner, and executable owner program.

- independently established non-Pump origin may yield
  `NON_PUMP_POOL_CONFIRMED`;
- unknown origin yields `UNKNOWN_ORIGIN`;
- exact PumpSwap Pool presence without exact Pump migration remains
  `UNKNOWN_ORIGIN`, never graduation.

Global Pump observer state is not an input to this branch's pass/fail result.

### 4.4 Conflicts

Conflicting lineage, two current pools, reversed orientation, candidate/pool
mismatch, or a failed explicit Pump claim remains categorical failure. Source
majority and generic fallback cannot resolve a conflict.

## 5. Candidate-specific migration locator contract

The verifier accepts one exact candidate mint and zero or more already-known
locators. Locator precedence is:

1. exact migration signature;
2. exact proposed PumpSwap pool;
3. exact verified Pump bonding curve; and
4. exact candidate mint.

The most specific available locator is used first. A broader locator is not an
automatic retry after an identity, contract, or parser failure. A later
implementation must freeze whether multiple locator forms may be attempted
inside one predeclared budget; unused budget never creates an unplanned attempt.

### 5.1 Direct signature

Call finalized `getTransaction(signature)` with JSON encoding and
`maxSupportedTransactionVersion=0`. The signature is locator evidence until all
transaction and Pool checks pass.

### 5.2 Pool-address lookup

Use bounded finalized `getSignaturesForAddress(exact_pool)`. Each inspected
transaction must decode to the exact Pump `migrate`, and decoded account 9 must
equal the requested pool. A Pool account by itself is never accepted as the
migration transaction.

### 5.3 Bonding-curve lookup

Use bounded finalized `getSignaturesForAddress(exact_verified_curve)`. The curve
must first equal the Pump PDA derived from the candidate mint. The decoded
`migrate` account 3 must equal that same curve.

### 5.4 Mint lookup

Use bounded finalized `getSignaturesForAddress(candidate_mint)`. The decoded
`migrate` account 2 must equal that exact mint.

### 5.5 Bounded negative result

Every lookup has fixed page, row, transaction, byte, duration, request, and
operation ceilings set by a later implementation lane without increasing the
current global budgets. A full bounded page with no exact match is
`CANDIDATE_MIGRATION_NOT_FOUND_WITHIN_BOUND`, not `not migrated`. Empty or
pruned history is `CANDIDATE_MIGRATION_HISTORY_UNAVAILABLE`. A required Pump
graduation branch fails closed; unrelated branches are unaffected.

Candidate-specific lookup has no universal high-water cursor. Its identity is:

```text
network | candidate mint | locator kind | locator address/signature
| Pump pin | PumpSwap pin | decoder version | finalized cutoff
```

## 6. Exact Pump migration proof

For one located signature, all of the following are mandatory:

1. finalized `getTransaction`, successful `meta.err == null`;
2. legacy or version 0 only, with static plus loaded writable plus loaded
   readonly account resolution;
3. exactly one compiled instruction owned by the pinned Pump Program with
   discriminator `9beae792ec9ea21e`;
4. exactly 25 resolved instruction accounts;
5. exact fixed programs/accounts at positions 6, 7, 8, 14, 19, 20, 23, and 24;
6. expected candidate mint at account 2;
7. expected derived bonding curve at account 3;
8. exact candidate pool at account 9 when pool was the locator;
9. exact Pump pool-authority creator at account 10;
10. non-null slot and block time retained as migration-only evidence; and
11. no second supported migrate instruction or conflicting signature/slot.

Unknown version/layout, missing loaded addresses, log-only attribution, failed
transaction, null/pruned result, ambiguity, or mismatch creates no Pump claim.

## 7. Exact PumpSwap join

The Pool address comes only from decoded migrate account 9. Read the exact Pool
account at finalized commitment and verify:

- owner equals the pinned PumpSwap program;
- Pool discriminator equals `f19a6d0411b16dbc`;
- full adopted prefix and allowed length/extension rule decode;
- canonical index is zero;
- Pool creator equals migrate account 10;
- base mint equals migrate account 2 and the candidate mint;
- quote mint is wrapped SOL under this migration pin;
- Pump bonding curve and pool-authority PDAs match the candidate;
- Pool PDA and bump match index/creator/base/quote;
- LP mint matches both the derived PDA and migrate account 15; and
- base and quote vaults match Pool state, derived ATAs, and migrate accounts 17
  and 18.

The joined positive fact binds:

```text
candidate mint
<-> migration signature / slot / block time
<-> exact Pump migrate instruction and contract hash
<-> exact Pool address
<-> exact PumpSwap account hash and contract hash
<-> exact base / quote / creator / index / PDA / LP / vault identities
```

`PUMP_GRADUATION_CONFIRMED` is allowed only after this join and the existing
exact Pump origin requirement pass. No source observation, global cursor state,
or venue label can fill a missing join field.

## 8. Optional global Pump observation

### 8.1 Status

The existing program-wide observer is:

- retained as optional coverage and candidate-discovery input;
- diagnostic/audit-only when its range is incomplete; and
- retired from active candidate gating for every unrelated branch.

Its Scheduler operation must be `required=false`. Its cursor range must attach
only to global observer coverage records, not to generic pool, mint, holder,
safety, market, or candidate-specific verification observations.

### 8.2 Existing gap

The old global migration cursor and recovery ledger stay byte-preserved. Reports
must expose at least:

```text
observer_status = OPTIONAL_OBSERVER_GAPPED
authoritative_head_slot = 435985595
frozen_tip_slot = 435999023
last_recovery_continuation_slot = 435998983
signatures_inspected = 11000
pages_inspected = 44
exact_prior_boundary_reached = false
terminal_reason = CURSOR_RECOVERY_LANE_BOUND_EXHAUSTED
admission_authority = NONE
```

This is a derived report view, not a cursor mutation or new checkpoint.

### 8.3 Future observation

No future global scan is authorized here. If separately implemented, a bounded
global observer may:

- append exact compact coverage summaries;
- emit a migration signature/mint/pool locator when it decodes an exact pinned
  transaction; and
- hand that exact locator to the candidate-specific verifier.

It may not be required for a nomination group to succeed, borrow candidate
verification budget, claim absence beyond its range, or advance past an
unsupported/unavailable observation.

## 9. Narrower global and live locators

No narrower global finalized HTTP locator is adopted. PumpSwap-program history,
withdraw-authority history, event-authority history, or another fixed account
may be considered only after official source research proves exact identity,
migration specificity, and bounded viability. This design contains no guessed
address or fallback.

A future bounded Pump-program `logsSubscribe` session may be used only as
non-authoritative live discovery:

```text
bounded Scheduler-owned subscription
-> collect signature locator within fixed time/slot cutoff
-> unsubscribe/terminalize
-> finalized getTransaction over HTTP
-> exact candidate migrate decode
-> exact PumpSwap Pool join
```

Processed/confirmed notification, log text, program invocation, or disconnect
state never establishes graduation. Missed logs do not create a gap that blocks
candidate-specific or generic admission. Subscription, HTTP verification, and
cleanup are separately counted transport operations under one governed plan.

## 10. Source Governor and Scheduler ownership

The existing public operational command remains the sole public runner. The
`CandidateAcquisitionIntegrationOwner` remains the finite orchestration owner.
No adapter-owned loop or independent cursor runner is added.

### 10.1 Central Scheduler

Central Scheduler owns every `DISCOVERY_REFRESH` work item, including start,
lease, deadline, cancellation, terminal state, and future eligibility. The
logical sequence is:

1. bounded multi-source nomination;
2. deterministic cohort formation;
3. pure branch classification;
4. candidate-specific work only for cohort candidates whose branch requires it;
5. exact current-pool and other categorical enrichment;
6. optional global observer work only if separately predeclared; and
7. foundation and safe stop.

Execution order is resource accounting, never candidate or source preference.
There are zero automatic retries, reconnects, restarts, successors, or endpoint
rotations.

### 10.2 Source Governor

All Solana RPC work remains under source `solana_rpc`. A later implementation
must distinguish request kinds by evidence authority, for example:

| Request kind | Meaning | Candidate-gating authority |
| --- | --- | --- |
| `candidate_pump_migration_signature_lookup` | bounded exact mint/curve/pool signature page | only its exact candidate |
| `candidate_pump_migration_transaction` | finalized exact located transaction | only its exact candidate |
| `candidate_pumpswap_pool_verification` | finalized exact Pool/related account read | only its exact candidate |
| `pumpfun_migration_signature_page` | optional program-wide observer page | none by itself |
| `pumpfun_migration_transaction` | optional global locator decode | locator only until candidate verifier joins it |
| future `pumpfun_migration_logs_locator` | bounded lossy live subscription | locator only |

Names are design identities for the later implementation. Registry changes are
not authorized here. Each underlying HTTP/WebSocket method, connection,
subscribe/unsubscribe, byte count, timeout, and failure is counted separately.

The Governor persists requests before transport and responses/failures after.
Evidence from one request kind cannot be relabeled as another. Optional global
failure cannot overwrite a clean candidate-specific fact.

## 11. Failure taxonomy and precedence

### 11.1 Candidate-specific reasons

| Family | Exact reason examples |
| --- | --- |
| `UNSUPPORTED_CONTRACT` | `CANDIDATE_MIGRATION_UNSUPPORTED_VERSION`, `CANDIDATE_MIGRATION_LAYOUT_UNSUPPORTED`, `PUMPSWAP_LAYOUT_UNSUPPORTED` |
| `SOURCE_PROVIDER_FAILURE` | `CANDIDATE_MIGRATION_PROVIDER_UNAVAILABLE`, `CANDIDATE_POOL_PROVIDER_UNAVAILABLE` |
| `BUDGET_EXHAUSTION` | request/operation/byte/duration ceiling reached before planned work |
| `COVERAGE_FAILURE` | `CANDIDATE_MIGRATION_NOT_FOUND_WITHIN_BOUND`, `CANDIDATE_MIGRATION_HISTORY_UNAVAILABLE` |
| `STALE_OR_INCOMPLETE_EVIDENCE` | null/pruned transaction, missing signature, Pool account unavailable, missing required origin proof |
| `IDENTITY_MERGE_FAILURE` | candidate mint/curve/pool facts conflict across exact observations |
| `ADMISSION_FAILURE` | transaction mint mismatch, pool mismatch, noncanonical index, wrong quote, PDA/LP/vault mismatch, failed explicit Pump branch |

Existing foundation precedence remains:

```text
unsupported contract
-> provider failure
-> budget
-> coverage
-> stale/incomplete
-> identity conflict
-> admission
-> true complete-coverage shortage
```

An exact mismatch requires an actual conflicting returned identity. Provider
failure, empty history, or bounded exhaustion is not a mismatch and never means
`NON_PUMP_POOL_CONFIRMED`.

### 11.2 Optional global reasons

Global outcomes remain separate diagnostics:

- `GLOBAL_PUMP_OBSERVER_CONTIGUOUS`;
- `GLOBAL_PUMP_OBSERVER_GAPPED`;
- `GLOBAL_PUMP_OBSERVER_UNKNOWN`;
- `GLOBAL_PUMP_OBSERVER_BLOCKED_CONTRACT`;
- `GLOBAL_PUMP_OBSERVER_PROVIDER_UNAVAILABLE`; and
- `GLOBAL_PUMP_OBSERVER_NOT_RUN`.

Only a positive exact decoded candidate locator can enter candidate work. No
global terminal category is a universal acquisition terminal cause.

## 12. Restart, pruning, missing history, and provider unavailability

### 12.1 Candidate-specific work

- Before a work-row commit, no evidence or candidate state advances. A later
  explicitly authorized run may repeat the bounded request.
- After a compact work-row commit, replay validates exact candidate, locator,
  cutoff, pin, decoder, page hash, request/response IDs, and continuation before
  reuse.
- There is no automatic process restart or successor.
- A persisted positive finalized migration/Pool proof may be re-used only under
  identical contract pins and exact hashes; requalification still rechecks any
  current evidence required by the foundation.
- A negative bounded lookup is never cached as permanent non-migration.
- Null/pruned transaction or empty address history is missing history, not
  absence. A required Pump claim fails; unrelated candidates continue.
- Provider 403/429/timeout/RPC error/malformed response terminalizes that exact
  governed work. There is no hidden retry or endpoint rotation.

### 12.2 Optional global observation

- The old recovery chain is frozen and never auto-resumed.
- A future separately authorized observer execution uses its own immutable
  cutoff and cannot silently continue or replace the old chain.
- Gapped/unknown/pruned state remains visible and cannot advance a cursor.
- Global provider unavailability is diagnostic and never blocks the nomination
  group, candidate-specific proof already obtained, or generic admission.

### 12.3 Foundation transaction

Candidate observations, exact branch results, certificates, reserve/manifest,
and any permitted candidate-specific evidence links commit atomically under the
existing foundation owner. Optional global coverage is not a prerequisite in
that transaction. Failure before the foundation leaves no partial admission or
cursor movement.

## 13. Storage policy

The design forbids another program-wide raw-signature ledger.

For every signature page, authoritative storage retains only:

- exact request/response IDs and response hash;
- network, indexed address, locator kind, contract pins, decoder version,
  commitment, and immutable cutoff;
- page ordinal, requested limit, returned count, first/last slot and exact
  continuation needed for bounded replay;
- canonical page hash and response byte count;
- categorical failed/unsupported/eligible counts;
- exact matching migration signature(s) actually selected for finalized decode;
  and
- exact failure/coverage category.

It does not persist the full array of unrelated program-wide signature rows in
`normalized_payload_json`, work JSON, report JSON, or candidate facts. The raw
transport body is hashed during bounded processing and discarded after the
governed response/compact evidence is committed. Secrets and full endpoint URLs
remain absent.

For a positive candidate proof, persist the exact normalized migrate identity,
signature, slot, block time, contract hashes, Pool account hash, and joined
mint/pool/base/quote/PDA/LP/vault facts. Raw transaction/account bodies are not
duplicated across observation, certificate, and report tables; link by governed
request/response and content hashes.

Existing 11,000-signature recovery evidence is immutable historical data and is
not deleted or rewritten by this policy.

The later implementation must first prove that migrations 048/049 can represent
the compact work/evidence links without a schema change. If they cannot, it must
stop `BLOCKED` and return to a separately authorized schema design; this design
does not authorize migration 050 or any database change.

## 14. Admission independence

The acquisition-level required-source gate is recalculated by branch:

- nomination group: at least one approved nomination source completes;
- Pump graduation branch: its candidate-specific migration and Pool proof are
  required for that candidate only;
- Pump active-curve branch: exact origin/curve evidence is required for that
  candidate only;
- generic/unknown branch: exact current-pool evidence is required for that
  candidate only; and
- optional global observer: never required for acquisition success.

A failed candidate does not contaminate another candidate's branch. Foundation
may still complete when at least N candidates pass all their own categorical
gates. If fewer than N pass, the existing failure precedence distinguishes
provider/budget/coverage/evidence failure from true complete-coverage shortage.

## 15. Minimum implementation scope

A later separately explicit implementation lane is limited to:

1. make the program-wide migration operations optional and detach their cursor
   range from unrelated candidate/pool observations;
2. add pure lineage-branch classification after deterministic cohort formation;
3. add bounded candidate-specific mint/curve/pool/signature locator planning;
4. reuse the pinned migration and PumpSwap verification kernels without
   loosening them;
5. add exact Source Governor request-kind and operation accounting for the new
   candidate-specific channel;
6. preserve compact normalized storage and zero-source report replay;
7. preserve existing global cursor/recovery rows byte-for-byte; and
8. add focused offline fixtures and directly affected regressions.

Likely canonical files are limited to the existing live acquisition transport
owner, acquisition integration owner, strict Pump contract module only if an
adapter boundary is missing, source registry/contracts, and focused tests. The
foundation admission rules should change only where required to consume the
decoupled branch evidence. No new runner or parallel source loop is allowed.

Not in minimum scope:

- schema/migration or DB mutation;
- cursor reset/advance/recovery continuation;
- source-budget increase;
- provider/RPC/WebSocket/live proof;
- N2, N7, campaign, tracking, lifecycle, snapshot, window, or memory work;
- a new global locator contract;
- PumpPortal, paid RPC, DEXTools, wallet, or secret creation; or
- any retrieval or financial capability.

## 16. Required offline proof before live work

All proof uses frozen transports and disposable databases only. Required matrix:

1. aggregator-only `UNKNOWN_ORIGIN` exact generic pool passes while global
   observer is `GAPPED`, `UNKNOWN`, provider-unavailable, blocked-contract, and
   `NOT_RUN`;
2. independently known non-Pump pool passes as `NON_PUMP_POOL_CONFIRMED` with
   the same optional-global outcomes;
3. exact Pump active bonding curve passes without migration work;
4. Pump graduation passes from each locator type: signature, pool, curve, mint;
5. exact migrate and Pool proofs join on signature/mint/pool/creator/index/quote/
   PDA/LP/vault and fail one field at a time;
6. PumpSwap Pool presence alone never yields graduation;
7. failed explicit Pump claim cannot downgrade to unknown/generic;
8. no-match bounded scan, empty/pruned history, null transaction, provider
   failure, malformed page, unsupported version/layout, ambiguity, and budget
   exhaustion retain their exact categories;
9. optional global positive hit still passes through candidate verifier;
10. optional global failure never enters universal required failures;
11. crash before/after compact page commit, exact replay, duplicate page,
    continuation mismatch, and no automatic restart;
12. compact storage contains page hashes/summaries and positive matches but no
    program-wide raw-signature arrays;
13. Source Governor/Scheduler jobs, request/response/failure links, underlying
    operations, bytes, rows, leases, terminal states, and replay reconcile;
14. live-shaped N2 mechanics produce an exact two-item runtime-neutral manifest
    from eligible branch-mixed candidates with handoff zero;
15. N7 mechanics remain runtime-neutral, projection zero, and legacy adapter
    rejection unchanged;
16. current active capacity remains exactly two, current budgets are not raised,
    existing cursor/recovery fixtures remain byte-identical, and protected
    memory/retrieval/financial deltas are zero; and
17. static no-wallet/no-paid/no-score/no-rank/no-confidence/no-weight/no-vector/
    no-financial scans pass.

No live work may be proposed until this offline proof and its closeout pass from
a clean committed checkpoint and a later explicit authorization is supplied.

## 17. Money-usefulness contribution

This architecture improves candidate supply without weakening evidence quality:

- exact non-Pump and unknown-origin pools are no longer rejected because an
  unrelated high-volume global Pump history is incomplete;
- Pump graduation remains stronger, not weaker, because every claim is bound to
  an exact candidate transaction and canonical Pool state;
- optional global observation can still discover migrations and measure coverage
  without consuming correctness authority it does not have;
- missing/pruned history stays honest instead of becoming false lineage; and
- compact evidence prevents observation bookkeeping from consuming database
  space needed for money-useful clean market memory.

This creates no profit claim, memory, retrieval, decision, position, or PnL.

## 18. Functionality Risks / Setbacks / Efficiency Blockers

1. Candidate-specific address history can still be large or pruned; the design
   improves scope but does not guarantee yield.
2. Dynamic two-stage planning after cohort formation must remain inside one
   finite Scheduler/Governor owner and cannot become an adapter loop.
3. Existing 048/049 storage may not cleanly express compact candidate lookup
   replay without a schema change; implementation must stop rather than improvise.
4. Removing the global universal gate reduces global completeness pressure.
   Reports must show `OPTIONAL_OBSERVER_GAPPED` prominently so coverage is not
   mistaken for complete.
5. Logs can improve freshness only as a lossy locator and may be unavailable on
   public infrastructure.
6. Contract drift in Pump/Pool layout, quote policy, or transaction versions
   blocks the affected Pump branch until refreshed; it cannot fall back.
7. Candidate-specific operations may compete with holder/pool work under the
   fixed Solana budget. The later implementation must freeze exact arithmetic
   and stop if N2 headroom is insufficient.
8. The old 47 MB evidence growth is not recoverable in this lane. The compact
   policy only prevents repetition.

## 19. Design pass basis and stop boundary

The design passes because it specifies branch authority, exact locator and
verification contracts, the Pump/PumpSwap join, optional global status,
historical-gap treatment, narrower-locator disposition, live-log boundary,
Source Governor/Scheduler ownership, failures, restart/pruning/provider
behavior, compact storage, admission independence, minimum implementation, and
offline proof without guessing a source fact or loosening a V1 lock.

Stop here. No implementation, source execution, cursor action, database action,
N2, N7, or campaign is authorized by this document.
