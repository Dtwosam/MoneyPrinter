# Printer V1 V2-9.8B Measured Operation Budget Architecture Reset

Date: 2026-07-30

Lane: `V2-9.8B Measured Operation Budget Architecture Reset`

Verdict:
`V2_9_8B_MEASURED_OPERATION_BUDGET_ARCHITECTURE_RESET_PASS`

## Scope and baseline

This is a documentation-and-design-only reset. It defines a bounded accounting
architecture for later operator review; it changes no runtime, test, source
contract, configuration, budget, migration, active source-authority document or
database row.

- Branch: `master`
- Clean design baseline:
  `18908ab393069d4cd50668792e32d7f2ba9106e0`
- Baseline commit:
  `Document source compatibility operation-budget blocker`
- Authoritative database: `data/printer_v1.sqlite3`
- Required authoritative database SHA-256:
  `e748ba505cb8c7d67b8feb3a09b97719a0f3560e41dfb9242570cff3157962e6`
- Migration head remains `049`.
- No provider, RPC, WebSocket, source probe, Memory Factory, tracking, window or
  memory operation was run for this design.

## Exact current-budget root cause

The current `45`-unit admission ledger is not a transport-operation ledger. It
adds unlike quantities:

- governed source-request rows;
- actual HTTP/RPC calls hidden inside some governed requests;
- nine local zero-transport validations; and
- six not-yet-attempted snapshot reservations.

Those quantities are not interchangeable. In particular:

- one DexScreener fresh-profile governed request performs two HTTP calls;
- one PumpSwap verification can perform one transaction lookup plus three
  `getMultipleAccounts` batches;
- one Solana or Helius holder governed request performs two RPC calls; and
- a reservation is capacity, not an attempted call.

The active worst case therefore cannot be represented by incrementing one
request counter. The earlier blocker correctly showed `71` mixed units. Under
the corrected unit model, that same pre-lifecycle plan is:

```text
46 actual candidate-supply transports
+ 10 actual holder transports for two candidates
= 56 actual pre-lifecycle transports

9 local validations                         separate unit, not 9 transports
6 readiness transports                      protected capacity, not attempted
                                            until the readiness calls occur
```

The root cause is the unit model, not excessive evidence collection. Raising one
mixed counter would retain the defect.

## Immutable budget units

| Unit | Exact definition | Counting rule |
|---|---|---|
| `SOURCE_TRANSPORT_OPERATION` | One actual outbound HTTP request or JSON-RPC method call to one resolved endpoint. | Count immediately before the transport is attempted. A failed, timed-out, rate-limited or malformed-response attempt still counts. Parsing, decoding and validation do not count. A governed request may contain more than one. |
| `LOCAL_VALIDATION_STEP` | One predeclared deterministic validation, decode, normalization, identity check or policy check that performs no source I/O. | Count only in its local-work manifest. It never decrements source capacity. The existing nine pre-activation checks remain nine local steps, not nine transports. |
| `SCHEDULER_WORK_ITEM` | One durable Scheduler-owned work item or lifecycle run step created or claimed under its stable identity. | Count once at durable creation/claim according to the Scheduler contract. It may cause zero, one or several transports. Source attempts never infer or fabricate Scheduler rows. |
| `SOURCE_RESPONSE_BYTES` | Raw response bytes actually read for one transport operation, before JSON decoding or normalization. | Record per transport identity, including partial and failed reads. Enforce both per-operation and stage byte envelopes before persistence can authorize continuation. |
| `NORMALIZED_SOURCE_ROWS` | Distinct normalized source entities emitted from governed evidence, such as migration observations, confirmations, pair rows or holder facts. | Count after normalization and before downstream persistence. It is independent of raw byte count, source-request rows and domain rows such as snapshots. |
| `LIFECYCLE_RESERVED_TRANSPORT_OPERATION` | Capacity withheld for a named future lifecycle transport identity. | Reservation reduces capacity available to earlier stages but is not reported as attempted. On the actual attempt it is atomically converted to `SOURCE_TRANSPORT_OPERATION`. Unused reservation is released only by the deterministic rules below. |

Every transport identity must contain:

- campaign, run, cycle and stage identity;
- source name and resolved endpoint-owner identity;
- governed request identity;
- HTTP endpoint or RPC method;
- within-request ordinal;
- target category and exact mint/pair where applicable;
- reserved identity, when converted from a lifecycle reservation;
- attempted-at time, bytes read and normalized-row count;
- categorical completion or failure result.

Missing, duplicate, undeclared or over-envelope identities fail closed before
candidate continuation or lifecycle continuation.

## Stage dependency graph

```text
zero-I/O preflight and nine local validations
  -> one stateless Pump migration signature page
  -> at most twelve migration transaction lookups
  -> at most five exact Pump/PumpSwap verifications
  -> one DexScreener fresh-profile bundle (two HTTP calls)
  -> bounded exact-pair evaluation
  -> two-candidate holder/safety evidence
  -> choose exactly one command branch
       A. readiness-only: two GeckoTerminal readiness bundles -> report/replay
       B. ordinary run: atomic two-token handoff
            -> 32 mandatory WINDOW_15M observations
            -> protected close context and entry/exit quotes
            -> window close/audit
            -> report/replay
```

The readiness-only branch and ordinary lifecycle branch are mutually exclusive.
They must never be summed into one campaign maximum. Pre-activation holder
evidence and close-time holder evidence are not mutually exclusive: they occur
at different freshness boundaries and can coexist in an ordinary campaign.

## Exact candidate-supply arithmetic

Let:

- `n` be attempted Pump migration transaction lookups, `0 <= n <= 12`;
- `m` be attempted exact Pump/PumpSwap candidate verifications,
  `0 <= m <= 5`; and
- `p` be attempted DexScreener exact-pair calls.

The current permitted candidate walk has:

```text
p <= 28 - n - m
```

This retains the current one-page, one-round and thirty-governed-request supply
breadth. It does not create a second page, retry, recovery, backfill or expanded
search. The fresh-profile bundle consumes one governed request but two
transports.

| Candidate-supply stage | Governed requests | Actual transports | Maximum read bytes | Bounded normalized/domain rows |
|---|---:|---:|---:|---|
| Direct Pump nomination | `1 + n` | `1 + n`, max `13` | `13 * 1,048,576 = 13,631,488` | At most 12 migration observations |
| Exact Pump/PumpSwap verification | `m`, max `5` | `4m`, max `20` | `20 * 1,048,576 = 20,971,520` | At most 5 exact confirmations |
| DexScreener fresh profiles | `1` | `2` | `2 * 2,000,000 = 4,000,000` | At most 30 nominated mint identities; returned pair-array rows lack an independent current numeric ceiling |
| DexScreener exact pairs | `p`, standalone max `28` | `p` | `p * 512,000` | At most one admitted exact-pair outcome per attempted target; raw returned pair-array rows lack an independent current numeric ceiling |

At the full direct worst case, `n = 12`, `m = 5`, and `p = 11`:

```text
Pump signature page                              1
Pump migration transaction lookups              12
five verifications * four RPC calls             20
DexScreener fresh-profile HTTP calls              2
DexScreener exact-pair HTTP calls                11
                                                  --
candidate-supply transport maximum               46

candidate-supply governed-request maximum         30
candidate-supply maximum response bytes   44,235,008
```

The standalone DexScreener stage ceiling is 30 transports (`2 + 28`), but it
cannot coexist with all 33 direct transports. The candidate-supply aggregate
ceiling of 46 and the deterministic `p` formula preserve that exclusivity.

## Holder, readiness and lifecycle arithmetic

### Two-candidate holder/safety evidence

For each candidate the legitimate coexisting worst case is:

```text
GoPlus safety/holder reference                    1
primary Solana holder methods                     2
conditional Helius holder methods                 2
                                                   -
per-candidate transport maximum                   5
```

The Helius branch is attempted only after an eligible transient primary failure,
but the primary attempt and backup attempt coexist in the worst case. For two
candidates this stage is 6 governed requests, 10 transports, 5,120,000 maximum
read bytes and at most six persisted attempt records resolving to at most two
candidate holder facts.

### Readiness-only branch

Each candidate has one GeckoTerminal exact-pool base request and at most two
15-minute completion requests. For exactly two candidates:

```text
2 * (1 base + 2 completion) = 6 transports
```

This is six governed requests, 3,072,000 maximum read bytes and at most two
persisted readiness snapshots. Verified inactivity may cause fewer calls, but
success is not assumed to reduce the declared maximum.

### Ordinary two-token `WINDOW_15M` observations

`TRACK_FAST` requires 16 observations per token, including the close
observation. Each observation always permits one DexScreener primary and, only
after an eligible transient primary failure, one GeckoTerminal fallback:

```text
2 tokens * 16 observations * (1 primary + 1 fallback)
= 64 transport operations
```

The two attempts can coexist, but they can create at most one snapshot for that
observation. The stage maximum is 64 governed requests, 32,768,000 read bytes
and 32 persisted token snapshots.

The lifecycle Scheduler envelope is 34 durable work items:

- 32 observation/close run steps; and
- at most one discovery/handoff allowance per token.

Close-time context calls execute inside the close work item and do not create
extra Scheduler rows merely because they create source transports.

### Mandatory pre-close context and Jupiter quotes

For each token, the legitimate coexisting worst case is:

```text
CoinGecko market/chain context                    1
GoPlus safety                                     1
Jupiter ENTRY quote                               1
Jupiter EXIT quote                                1
primary Solana holder methods                     2
conditional Helius holder methods                 2
                                                   -
per-token pre-close transport maximum             8
```

For two tokens this stage is 12 governed requests, 16 transports, 8,192,000
maximum read bytes and at most twelve persisted source attempt records bound
into two close-context bundles.

### Terminal report and replay

Terminal report assembly and replay are DB/artifact reads only:

```text
source transports       0
source response bytes   0
normalized source rows  0
new source-request rows 0
```

Replay must reproduce canonical report bytes without creating a Scheduler job,
source request, response, failure, reservation conversion or retry.

## Full campaign maxima

### Ordinary two-token 15-minute campaign

```text
candidate supply                              46
two-candidate holder/safety                   10
mandatory 15m observations                    64
mandatory pre-close context/quotes            16
                                               --
full ordinary transport maximum              136

maximum governed source requests             112
maximum response bytes                90,315,008
maximum lifecycle Scheduler work items         34
maximum persisted lifecycle snapshots          32
```

The 112 governed requests are `30 + 6 + 64 + 12`; they are reported for
lineage, not used as a substitute for 136 transports.

### Mutually exclusive readiness-only campaign

```text
candidate supply                              46
two-candidate holder/safety                   10
two readiness bundles                          6
                                               --
readiness-only transport maximum              62

maximum governed source requests              42
maximum response bytes                52,427,008
maximum persisted readiness snapshots          2
```

The readiness six is not added to the ordinary 136.

## Maximum transport operations by source

The full ordinary coexisting worst case is:

| Transport owner/source | Candidate supply | Holder admission | 15m observations | Pre-close | Full maximum |
|---|---:|---:|---:|---:|---:|
| One resolved Solana endpoint owner, including Pump/PumpSwap RPC | 33 | 4 | 0 | 4 | 41 |
| DexScreener | 13 | 0 | 32 | 0 | 45 |
| GeckoTerminal conditional snapshot fallback | 0 | 0 | 32 | 0 | 32 |
| GoPlus | 0 | 2 | 0 | 2 | 4 |
| Helius fixed free backup | 0 | 4 | 0 | 4 | 8 |
| CoinGecko | 0 | 0 | 0 | 2 | 2 |
| Jupiter keyless quote | 0 | 0 | 0 | 4 | 4 |
| **Total** | **46** | **10** | **64** | **16** | **136** |

Pump and PumpSwap logical evidence must share the same resolved Solana endpoint
and pacing owner. They cannot each claim an independent 30/minute allowance.

## Provider pacing implications

Spacing is the committed conservative whole-second interval
`ceil(60 / registry_rate_per_minute)`.

| Source/endpoint owner | Registry ceiling | Minimum spacing | Full ordinary maximum | Minimum adjacent-start span |
|---|---:|---:|---:|---:|
| Resolved Solana endpoint | 30/min | 2 s | 41 | 80 s |
| DexScreener | 60/min | 1 s | 45 | 44 s |
| GeckoTerminal | 10/min | 6 s | 32 | 186 s |
| GoPlus | 20/min | 3 s | 4 | 9 s |
| Helius free backup | 30/min | 2 s | 8 | 14 s |
| CoinGecko | 20/min | 3 s | 2 | 3 s |
| Jupiter quote | 30/min | 2 s | 4 | 6 s |

The span is `(operations - 1) * spacing` when calls are adjacent and is not a
promise that the campaign may burst. Lifecycle cadence naturally distributes
DexScreener and GeckoTerminal calls across 15 minutes. The candidate stage's 33
resolved-Solana calls alone requires at least 64 seconds between its first and
last adjacent start. A later implementation must pace by the single resolved
endpoint owner across logical Pump, PumpSwap and holder consumers.

Pacing wait is neither a transport operation nor a Scheduler work item. It
cannot hold a database write lock and cannot trigger retry, rotation or a second
page.

## Mutually exclusive and coexisting branches

| Branches | Relationship | Accounting consequence |
|---|---|---|
| Dex fresh profiles: profiles HTTP + token-batch HTTP | Coexisting | Always declare two transports when the bundle is attempted. |
| PumpSwap verification: transaction + up to three account batches | Coexisting | Declare four transports per candidate; fewer account batches reduce actual use only. |
| Dex snapshot primary + GeckoTerminal fallback | Conditional but coexisting after eligible primary failure | Count both attempts; persist at most one snapshot. |
| Solana holder primary + Helius backup | Conditional but coexisting after eligible primary failure | Count all primary methods and all attempted backup methods. |
| GoPlus holder-known vs RPC holder branch | Mutually exclusive after the GoPlus result | Worst case uses GoPlus plus primary RPC plus eligible backup; do not add another success-only branch. |
| Verified-inactivity readiness vs two completion requests | Conditional | Declare the two completion reservations; convert only calls actually attempted. |
| Readiness-only vs ordinary 15m lifecycle | Mutually exclusive command modes | Use emergency stop 62 or 136, never 142. |
| Candidate direct maximum vs Dex exact-pair standalone maximum | Constrained coexistence | Enforce `p <= 28 - n - m` and candidate-supply aggregate 46. |
| Pre-activation holder evidence vs close-time holder evidence | Coexisting freshness boundaries | Count both in an ordinary campaign. |

## Replacement policy options

| Evaluation | One corrected campaign-wide transport ceiling | Stage ceilings + protected lifecycle reservations | Stage ceilings + protected reservations + smaller emergency stop |
|---|---|---|---|
| Fail-closed safety | Medium: a stage can consume capacity intended for a later stage. | High at stage boundaries. | Highest: stage faults and cross-stage accounting faults both stop. |
| Accounting clarity | Better than the current mixed unit, but weak attribution. | Strong stage attribution. | Strong stage attribution plus an independent campaign invariant. |
| Provider-rate compatibility | Weak: no source-specific burst control. | Strong when stage plans include source pacing. | Strong, with aggregate endpoint pacing and campaign anomaly stop. |
| Two-token feasibility | Numerically possible at 136, but earlier work can starve lifecycle. | Feasible because 80 ordinary lifecycle transports are protected. | Feasible, protected, and bounded by the exact coexisting maximum. |
| Source-starvation risk | High. | Low. | Low. |
| Implementation complexity | Lowest. | Moderate. | Moderately higher due to one aggregate reconciliation. |
| Replay determinism | One total is reproducible but poorly diagnostic. | Deterministic by stable stage identities. | Deterministic by stage and campaign identity. |
| Operator understandability | Superficially simple, operationally ambiguous. | Clear. | Clearest: each stage explains its ceiling and the campaign total detects drift. |

The selected architecture is the third option.

## Selected exact budget architecture

### Hard stage ceilings

| Stage | Transport ceiling | Response-byte ceiling | Additional invariant |
|---|---:|---:|---|
| Direct Pump nomination | 13 | 13,631,488 | One signature page; at most 12 transaction lookups |
| Pump/PumpSwap exact verification | 20 | 20,971,520 | At most five candidates; at most four transports each |
| DexScreener discovery/enrichment | 30 standalone | 18,336,000 standalone | Two fresh-profile transports plus at most 28 exact pairs |
| Aggregate candidate supply | 46 | 44,235,008 | `p <= 28 - n - m`; no unused-capacity search expansion |
| Two-candidate holder/safety | 10 | 5,120,000 | At most five transports per candidate |
| Readiness-only reservation | 6 | 3,072,000 | Mutually exclusive with lifecycle reservation |
| Two-token 15m observations | 64 | 32,768,000 | 32 primaries plus at most 32 eligible fallbacks |
| Mandatory pre-close context/quotes | 16 | 8,192,000 | Eight transports per token |
| Terminal report/replay | 0 | 0 | Zero-source deterministic replay |

### Campaign emergency stops

- Ordinary two-token campaign:
  `136 SOURCE_TRANSPORT_OPERATION` and
  `90,315,008 SOURCE_RESPONSE_BYTES`.
- Readiness-only campaign:
  `62 SOURCE_TRANSPORT_OPERATION` and
  `52,427,008 SOURCE_RESPONSE_BYTES`.
- The nine existing pre-activation validations have a separate
  `9 LOCAL_VALIDATION_STEP` envelope.
- The ordinary lifecycle has a separate `34 SCHEDULER_WORK_ITEM` envelope.
- Governed request, source request/response/failure row and domain-row totals
  remain separately reported and reconciled.

The ordinary emergency stop is smaller than the sum of every standalone stage
maximum (`153`) because direct-source depth and the Dex standalone maximum
cannot coexist, and readiness-only work cannot coexist with ordinary lifecycle
work.

### Reservation and release rules

1. Before candidate transport, an ordinary campaign protects 80 lifecycle
   transports: 64 observation transports and 16 close-context transports.
2. A readiness-only command instead protects exactly six readiness transports
   and protects no lifecycle transports.
3. A reservation becomes attempted only in the same atomic ledger transition
   that precedes its transport call.
4. Candidate supply cannot consume holder, readiness, observation or pre-close
   reservations.
5. Unused nomination/verification capacity may reduce `n` or `m`; exact-pair
   permits are computed once by `p <= 28 - n - m`. This is the only
   pre-lifecycle release rule.
6. That release cannot authorize a second signature page, another discovery
   round, retry, recovery, backfill, source rotation or broader candidate set.
7. Unused holder or lifecycle capacity releases only to terminal unused
   capacity. It cannot flow backward into discovery.
8. If two exact eligible candidates are unavailable, all lifecycle reservations
   are closed as unused and the campaign terminalizes honestly.
9. Any stage breach or campaign emergency-stop projection fails before the next
   transport; no later success can repair an overage.

### Why the numbers are sufficient but not excessive

- `13` is exactly one signature page plus twelve permitted transaction reads.
- `20` is exactly five verifications at the legitimate Solana maximum of one
  transaction plus three 100-account batches.
- DexScreener's standalone `30` preserves the current permitted candidate walk,
  while aggregate `46` prevents that standalone maximum from being added to the
  full direct maximum.
- Holder `10` is exactly the requested two-candidate path including both
  two-method primary and two-method eligible backup.
- Readiness `6` is exactly two fixed three-request bundles.
- Lifecycle `64` is exactly 32 mandatory observations with one bounded
  conditional fallback each.
- Pre-close `16` retains all context, safety, holder and entry/exit quote
  evidence for both tokens.
- Emergency `136` is the exact ordinary coexisting maximum, not a target and
  not a profit- or candidate-yield-driven allowance.

## Row-accounting requirements

The current code has bounded domain output for migration observations,
confirmations, holder facts and snapshots, but does not independently cap every
raw/normalized pair array returned inside the DexScreener byte envelope. A later
implementation must not pretend byte bounds are row bounds.

Before implementation can pass:

- every source adapter must declare whether its normalized entity count has a
  numeric ceiling;
- DexScreener fresh-profile and exact-pair normalization must receive explicit
  deterministic row ceilings or fail closed as
  `NORMALIZED_ROW_CEILING_UNDECLARED`;
- truncation must not silently convert incomplete evidence into a clean exact
  pair;
- request, response, failure, operation, normalized-row and domain-row counts
  must reconcile independently; and
- report/replay must reproduce all totals with zero new source rows.

Known bounded domain maxima are 12 migration observations, 5 exact
confirmations, 2 resolved pre-activation holder facts, 2 readiness snapshots in
readiness mode, and 32 lifecycle snapshots in ordinary mode.

## Source breadth disposition

The existing source breadth is the minimum evidence breadth of the proven
restored factory and must not be weakened to fit the old mixed number.

| Evidence removed | Resulting gate | Money-usefulness impact |
|---|---|---|
| Exact Pump migration | Origin/graduation becomes unsupported or `UNKNOWN`; candidate blocks. | Memory could attribute the wrong launch/graduation history. |
| Exact PumpSwap identity/account join | Canonical pool and quote identity become `UNKNOWN`; candidate blocks. | Entry/exit and liquidity facts could target the wrong pool. |
| DexScreener exact pair | Current price/liquidity/tradeability becomes `UNKNOWN`; candidate or snapshot blocks. | Paper outcomes lose realistic market identity and exit context. |
| Holder/safety evidence | Concentration/risk remains `UNKNOWN` or explicit risk blocks. | Unsafe or untradeable setups could enter memory. |
| GeckoTerminal bounded fallback/readiness evidence | Eligible primary failure yields missing snapshot/readiness evidence. | Clean-window continuity and fast-failure resilience decrease. |
| CoinGecko close context | Mandatory broad context is missing and the window dirties or blocks. | Historical comparison loses the market regime context it requires. |
| Jupiter entry/exit quotes | Paper-realism evidence dirties or blocks. | A chart move could be mistaken for realistically enterable/exitable paper profit. |

Removing any of these would either violate the proven path or increase honest
safe-stops. The budget model must represent the evidence plan; the evidence plan
must not be cut merely to satisfy the former `45`.

## Compatibility with the five pending repairs

This design allows one later cohesive implementation to address all open
defects without changing its arithmetic:

1. **Measured operation accounting:** introduce stable per-transport identities,
   reservation conversion, exact byte/row reconciliation and independent
   governed-request/Scheduler counters.
2. **All 25 Pump migration roles:** validate the complete pinned ordered role,
   PDA/ATA, fixed-address, signer and writable contract. Validation remains local
   work and does not consume a transport.
3. **One resolved Solana endpoint owner:** resolve once, inject the immutable
   result into Pump, PumpSwap and primary holder paths, and aggregate all 41
   possible ordinary operations under one pacing owner.
4. **Typed prohibited-capability enforcement:** add explicit wallet, private
   key, signing, funding, paid, metered-stream, submission, execution-endpoint
   and credential-category fields plus recursive serialized-profile validation.
   These are local validation steps, not source operations.
5. **Active documentation alignment:** update current-authority sections only
   with the cohesive implementation so they accurately name direct stateless
   Pump/PumpSwap as the bounded ordinary locator and PumpPortal as deferred.

This lane implements none of those changes.

## Money-usefulness contribution

The design protects the usefulness of future paper memory by reserving capacity
for the evidence that determines exact identity, realistic liquidity, holder
risk, close context and entry/exit realism. It prevents candidate acquisition
from starving a two-token lifecycle and prevents a false clean-memory claim
based on request rows that concealed multiple real calls.

It creates no decision, position, trade, audit, profit or PnL capability.

## What remains locked

- implementation of this design;
- provider, RPC, WebSocket or source-contract probes;
- Memory Factory campaign execution;
- cursor, continuity, recovery, backfill, N2 or N7;
- a second source page, retry, restart or successor;
- PumpPortal ordinary authority;
- active capacity above exactly two;
- 5-minute main-outcome use; it remains support-only;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H` and `WINDOW_24H` production work;
- clean-memory creation and retrieval;
- paper decisions, BUY, SELL or HOLD;
- positions, trade events, paper audits and PnL;
- wallet, private key, signing, funding, transaction submission or live
  execution;
- paid APIs, scoring, ranking, confidence, weighting, embeddings or vectors.

## Proof required before implementation

A later explicitly authorized cohesive implementation lane must first repeat the
Python Builder Guide's source-grounded blocker classification and then prove,
without provider I/O:

1. exact operation identities for 1 page, 12 transactions, five four-operation
   verifications and the two-call DexScreener bundle;
2. one-, two- and three-account-batch PumpSwap cases, including a supported
   256-account transaction;
3. primary-plus-fallback coexistence for DexScreener/GeckoTerminal and
   Solana/Helius without double snapshots or holder facts;
4. stage reservation isolation, deterministic release and both 62/136 emergency
   stops;
5. exact per-source pacing through one resolved Solana owner without write-lock
   sleep;
6. per-operation bytes, declared normalized-row ceilings and independent
   persisted-row reconciliation;
7. all 25 pinned Pump migrate roles and relationships;
8. typed prohibited-capability rejection over every serialized active profile
   field;
9. active-document alignment without rewriting historical closeouts;
10. zero automatic retry, second page, recovery, backfill, restart or successor;
11. zero-source canonical terminal replay; and
12. unchanged authoritative database, migration head 049 and all financial
    locks.

The bounded proof must use disposable migration-049 databases and frozen
transports. A live proof remains a separate future operator authorization.

## Functionality Risks / Setbacks / Efficiency Blockers

- Current ledgers do not persist every underlying transport identity, byte count
  and normalized-row count required by this design.
- DexScreener normalized pair arrays have byte bounds but no independent current
  numeric row ceiling.
- The current 64 MiB storage ceiling is not proof that the 90,315,008-byte
  response-read maximum can be durably represented; response bytes, serialized
  persistence and artifact storage must be measured separately.
- Pump/PumpSwap and primary holder calls can still diverge in endpoint ownership
  until the single-owner repair lands.
- Existing request ceilings and lifecycle projections reason in governed
  requests and can undercount eligible fallbacks and two-method holder work.
- Provider pacing can consume meaningful wall time; source waits must not hold
  SQLite write locks or cause cadence gaps.
- Making every standalone stage maximum additive would expand candidate search;
  the aggregate 46 constraint and deterministic `p` formula are mandatory.
- A complete implementation spans accounting, source contracts, endpoint
  injection, preflight, reporting and documentation. Partial adoption would
  leave contradictory authorities.

## Exact next permitted task

The exact next permitted task is operator review of this design only.

This design verdict does not authorize implementation, source execution, a live
probe, a Memory Factory campaign, a retry, recovery, successor or any retrieval
or financial capability.
