# Printer V1 V2-9.7E.35 Post-E.34 Snapshot Readiness Blocker Audit

## Verdict

`V2_9_7E_35_MISSING_APPROVED_MATURITY_BOUNDARY`

E.34 was not proved to be a one-off outcome caused only by two unusually young
candidates. Across the read-only E.25, E.29, and E.34 live-proof databases, all
six observed exact pairs were only about 170 to 243 seconds old when their base
evidence was requested. The committed readiness path takes a bounded view of
recent finalized Pump creates, applies no age gate, completes holder evidence
immediately, and then attempts snapshot readiness immediately. No approved
categorical boundary coordinates candidate maturity with the requirement for a
completed exact 15-minute candle.

This is a design gap, not a demonstrated committed-code defect. The committed
code matches its present contracts and fails closed when completed exact-15m
evidence is absent. Its downstream snapshot owner can build two complete bundles
when valid completed evidence is supplied, but the live acquisition-to-snapshot
path does not establish that suitably mature candidates will realistically be
available in one bounded execution. No code change or another live execution is
justified by this audit.

## Scope and static baseline

- Audited HEAD: `0ae4571b806c55d271e99d392ccf5ce71412783d`.
- Branch: `master`.
- Tracked tree and index before the audit: clean.
- E.35 is audit-only and does not change the active V2 build order.
- Provider calls, canonical readiness executions, full-pilot executions,
  authorization consumption, retries, waits, endpoint rotation, and new-source
  use during E.35: zero.
- Python, tests, contracts, budgets, candidate caps, reservations, thresholds,
  and databases were not changed.
- The E.34 database was opened read-only with SQLite immutable/query-only
  controls. Its SHA-256 after inspection was
  `49A9C2DDCAD9728DA9FEF1183F072E2ECC5932CF486062696078E29AAA91BA03`.

## Exact committed call path

```text
AuthoritativeLiveOperationalCampaignOwner.run(mode=SNAPSHOT_READINESS)
  -> run_snapshot_readiness
  -> offline readiness source/configuration/budget preflight
  -> operation-ledger single-use refusal check
  -> DurablePumpRpcTransport
  -> LivePumpOriginAdapter.acquire
  -> run_acquisition_from_source
     -> up to 3 latest finalized create-index pages, 16 rows per page
     -> bounded finalized decode queue, at most 10 transactions
     -> FixtureOriginProof(block_time, mint, bonding_curve, signature, slot)
  -> bounded secondary enrichment
  -> _finalized_holder_candidates, at most derived cap 3
  -> _evaluate_holder_eligibility
     -> schedule_maturation
     -> GoPlus/public RPC/Helius evidence as governed
  -> eligible candidates, in deterministic identity order
  -> execute_readiness_snapshot_bundle immediately
     -> GeckoTerminal exact-pool base
     -> exact 15m OHLCV
     -> exact-window trades
     -> strict all-or-nothing persistence
  -> terminal report
  -> zero-source report replay
  -> disposable cleanup
  -> stop
```

The readiness dispatcher never calls the lifecycle driver or memory owners.
Retrieval, decisions, positions, trade events, audits, PnL, wallets, signing,
and live execution remain unreachable.

## Candidate age and acquisition findings

### Age is known before snapshot work

Every admitted origin proof contains the finalized Pump create transaction's
integer epoch `block_time`. This is available before holder work and before any
snapshot request. The exact-pool base response later supplies
`pair_created_at`, which is valid pair-age evidence for the resolved pair but is
not used by candidate admission.

Neither `cycle_cutoff` nor `evaluated_at` is a maturity gate. The structural
candidate filter checks confirmation, mint, bonding curve, signature, slot, and
deduplication only. Its final ordering is by identity fields, not age.

### Why E.34 admitted two approximately four-minute-old pairs

The direct Pump origin owner reads at most the latest 48 finalized create-index
signatures and decodes at most 10 admitted transactions. A prior cursor, when
present, admits only rows newer than that cursor; it does not create an older
candidate lane. Candidate selection then takes up to three structurally valid
proofs without an age condition. Both holder-eligible E.34 candidates therefore
went directly to snapshot readiness.

Read-only exact-pair ages at the base request were:

| Proof | Candidate 1 | Candidate 2 |
|---|---:|---:|
| E.25 | 172.656 seconds | 181.453 seconds |
| E.29 | 182.422 seconds | 170.425 seconds |
| E.34 | 243.013 seconds | 241.033 seconds |

The six observations do not prove that every bounded acquisition must return a
young pool. Low create throughput could make the latest bounded set span more
than 15 minutes. They do prove that E.34's outcome was not isolated and that the
currently observed live candidate diet repeatedly favors very fresh pools.

### Existing maturation is not snapshot maturity

The committed holder control declares:

```text
MATURATION_THRESHOLD_SECONDS = None
MATURATION_THRESHOLD_STATE = UNPROVEN_DISABLED
```

Accordingly, both E.34 candidates were immediately `DUE` and then
`COMPLETED/EVIDENCE_EVALUATED`. That mechanism controls pre-activation holder
evidence only. Its approved E.22 boundary intentionally leaves the threshold
disabled because no evidence-backed categorical threshold was frozen. It does
not wait for completed candles and does not govern snapshot admission.

Focused holder tests can monkeypatch a 30-second threshold to exercise pacing
and deadline behavior. That is test evidence for the generic control, not an
approved production threshold or a snapshot-maturity contract. The production
integration also passes `str(proof.block_time)`, while the enabled parsing path
expects an ISO datetime. Turning on the dormant constant would therefore not be
a valid repair. It would apply the wrong owner/purpose and expose an integration
shape that has never been approved for this use.

No Scheduler-owned snapshot-maturation row, queue, or categorical state applies
to `SNAPSHOT_READINESS`. Adding one would be a new approved implementation
boundary only after its design is accepted; it is not a configuration switch
that an operator can safely enable today.

## Source-contract comparison

| Boundary | Committed contract | Audit finding |
|---|---|---|
| Direct Pump origin | Latest bounded finalized create evidence through Source Governor/Central Scheduler owners | Provides trustworthy create time, but no mature-candidate guarantee |
| PumpPortal | Current contract is blocked for automatic Printer use because of key/wallet/funding prerequisites | Cannot be used as an alternative age or candidate path |
| GeckoTerminal base | Exact resolved pool with pair creation time, price, and liquidity | Can confirm pair age only after candidate admission |
| GeckoTerminal OHLCV | Exact 900-second candle; start plus interval must be complete at evaluation time | Correctly rejects absent or incomplete evidence |
| GeckoTerminal trades | Exact target and exact readiness window | Supporting completeness remains strict; provider latency/rate limiting can still block |
| Source Governor | Fixed owners, operation ceilings, no retry/rotation, fail closed | Must remain unchanged; it does not choose candidate age |

The provider response has no authoritative generic `completed` flag that can
replace interval validation. Pair age is necessary but not sufficient: skipped
intervals, publication/cache latency, or source reliability can still leave a
mature pair without acceptable exact-15m evidence.

## Can one bounded execution succeed?

The downstream path is structurally capable in isolation. The committed E.33
and E.26 focused fixtures prove that exact-pool base, a prior completed 15m
candle, exact-window trades, and strict persistence can produce complete
readiness bundles, and that missing evidence blocks rather than being invented.

The live end-to-end path is only conditionally capable. It can succeed if its
latest bounded Pump set happens to contain enough holder-eligible pools with
published completed exact-15m evidence. It has no committed mechanism that
makes that condition realistic or repeatable:

- selection cannot deliberately include older pools;
- the prior cursor favors newer, not older, creates;
- holder maturation is disabled and has a different purpose;
- snapshot work begins immediately after holder eligibility;
- the bounded execution deadline cannot mature a roughly four-minute-old pool
  into a reliably published exact-15m candle;
- hidden waiting, retry, rerun, budget expansion, and source substitution are
  prohibited.

Therefore the code can consume valid completed evidence, but the committed live
candidate-supply path has not proved that it can reliably reach that evidence
within one authorized execution. This is a repeatable structural coordination
mismatch, not proof of a parser, persistence, or strictness defect.

## Python Builder Guide blocker investigation

**BLOCKER CLASSIFICATION:** `DESIGN_GAP`

**Evidence:** Six read-only live observations over three proof cycles show
approximately 2.8-to-4.1-minute-old exact pairs. The committed path has the Pump
create time before snapshot work, but `_finalized_holder_candidates` does not
use it, production holder maturation is `UNPROVEN_DISABLED`, and no
snapshot-maturity owner exists.

**Official-source behavior:** A newly created pool need not yet expose a
completed exact 15-minute candle. GeckoTerminal completeness must be established
from the returned exact interval and evaluation time; age alone does not promise
publication or continuity.

**Printer-contract behavior:** The snapshot contract correctly requires
completed exact-15m evidence and fails closed. The acquisition contract
correctly performs bounded newest-create intake. Neither contract defines the
coordination boundary needed between those two valid behaviors.

**Root cause:** The approved design does not specify how readiness mode obtains
or admits sufficiently mature candidates while preserving bounded acquisition,
Scheduler ownership, fixed budget, single-use authorization, no retry, and no
hidden wait.

**Code change justified:** `NO`. There is no approved maturity policy to
implement, and the current code conforms to its committed contracts. A direct
code change would invent policy, ownership, timing, and candidate-pool behavior.

**Minimum safe response:** Keep the strict evidence gate and every existing
budget/cap/reservation unchanged; perform no new run; and, only if separately
authorized, define a design-only categorical snapshot-maturity boundary before
implementation or proof work.

**Focused proof needed:** See “Proof required before another live
authorization.”

**Untouched scope:** Provider behavior, source contracts, acquisition,
maturation, holder logic, snapshot logic, scheduler, lifecycle, memory,
retrieval, decisions, and financial capabilities.

**Authorization status:** The E.34 single-use operation-ledger marker remains
present and consumed. E.35 creates no authorization and consumes none.

**Next roadmap action:** Remain inside V2-9.7E. The operator may separately
authorize a design checkpoint for the missing maturity boundary. This audit
does not advance to a new roadmap lane.

### `snapshot_reason` query failure

The local E.34 closeout wrapper queried a nonexistent
`printer_token_snapshots.snapshot_reason` column during its final convenience
count. The committed schema has no such column. Canonical readiness identity is
stored at
`normalized_snapshot_payload_json.snapshot_readiness_contract.label`, and the
committed bounded report queries that JSON label correctly.

This is strictly `TEST_HARNESS_DEFECT`, owned by the one-off inline E.34 shell
proof wrapper. It is not owned by the canonical runner, snapshot owner,
persistence owner, report owner, focused tests, or migration schema. It occurred
after the terminal proof and did not change the zero-snapshot result. No product
repair, DB migration, or rerun is warranted.

## Minimum safe response

Do not configure or patch the dormant holder threshold, relax completed-candle
evidence, widen acquisition, add a source, wait inside the proof, retry, or issue
another authorization. Preserve E.34 as consumed.

Any future design proposal must define, without scores or ranking:

- the authoritative categorical age fact and clock;
- how Pump finalized `block_time` and Gecko exact `pair_created_at` relate;
- Scheduler ownership and finite maturity/deadline states;
- zero provider calls while a candidate is not due;
- whether mature candidates come from an already observed persistent pool or a
  separately bounded staged flow;
- behavior when fewer than two mature holder-eligible candidates exist;
- production integer-epoch compatibility;
- the rule that maturity only admits work and never substitutes for completed
  exact-15m source evidence;
- unchanged operation ceiling `45`, candidate cap `3`, snapshot reservation
  `6`, single-use authorization, and cleanup guarantees.

## Proof required before another live authorization

Another live readiness execution must not be recommended until a separately
approved boundary has all of the following non-network proof:

1. A frozen design and contract for categorical snapshot maturity, including
   owner, clocks, deadlines, persistence, cancellation, and replay.
2. End-to-end canonical fixtures tying Pump origin time to candidate admission,
   rather than supplying an unrelated old Gecko fixture.
3. Proof that young candidates make zero snapshot calls and cannot consume the
   snapshot reservation.
4. Proof that an eligible mature candidate pool can supply two complete bundles
   through the committed candidate owner without a new source, retry, rerun,
   hidden waiting, or budget expansion.
5. Strict refusal for missing, skipped, partial, stale, or unpublished exact-15m
   intervals even when age eligibility passes.
6. Deadline, cancellation, single-use refusal, terminal-report replay, cleanup,
   integrity, and foreign-key proof.
7. Production-shape proof for integer Pump epoch times and timezone handling.
8. Unchanged ceilings and zero lifecycle, memory, retrieval, decision,
   position, trade, audit, PnL, wallet, signing, and live-execution deltas.

These are readiness conditions for deciding whether a separately authorized run
could be useful. They are not authorization to design, implement, or execute it.

## Read-only proof state and zero-activity verification

- E.34 authorization marker rows: `1`; second use remains refused by the
  committed pre-transport check.
- E.35 authorization rows: none; no E.35 run/cycle identity or marker was
  created.
- E.34 active scheduler jobs after cleanup: `0`.
- E.34 active tracking rows: `0`.
- E.34 readiness snapshots: `0`.
- E.34 memory windows and run steps: `0`.
- E.34 retrieval queries and matches: `0`.
- E.34 decisions, positions, trade events, and trade audits: `0`.
- E.34 database integrity: `ok`; foreign-key violations: `0`.
- Latest E.34 durable source-request timestamp remains
  `2026-07-23T11:08:28.033641Z`.
- E.35 source, transport, runtime, lifecycle, memory, retrieval, decision, and
  financial activity: zero.

## Money-usefulness contribution

This audit protects source credits and operator time from being spent on a
single-use proof whose candidate supply is repeatedly too young for its strict
evidence goal. It preserves the honest completed-candle rule, so Printer cannot
manufacture readiness, train on partial evidence, or later claim paper
profitability from an unrealistic data path.

## What this audit improves

- Separates downstream snapshot capability from live candidate-supply
  capability.
- Converts “two young candidates” into a bounded cross-proof evidence set
  without claiming statistical certainty.
- Identifies the exact available age facts and the point where they are ignored.
- Distinguishes holder-evidence maturation from snapshot maturity.
- Prevents a test-only threshold or a one-off SQL error from becoming an
  unjustified product repair lane.
- States the minimum evidence needed before scarce live authorization can be
  considered again.

## What remains locked

Operational memory growth, lifecycle creation, snapshot-threshold relaxation,
clean-memory creation, retrieval, decisions, BUY/SELL/HOLD, positions, trade
events, paper audits, PnL, wallets, private keys, signing, real funds, live
execution, paid APIs, scoring, ranking, confidence percentages, weighted logic,
embeddings, and vectors remain locked.

## Functionality Risks / Setbacks / Efficiency Blockers

| Item | Effect | Required handling |
|---|---|---|
| Recent-create candidate diet | Repeatedly supplies pools far short of completed-15m readiness | Do not spend another authorization until a boundary is designed and proved |
| Age is necessary, not sufficient | A mature pool can still lack published continuous exact evidence | Keep completed-candle and exact-window checks authoritative |
| No approved snapshot-maturity owner | Any immediate code patch would invent policy and timing | Separate design approval before implementation |
| Dormant holder threshold has a different purpose | Enabling it could couple unrelated controls and mishandle epoch input | Do not use it as a snapshot repair |
| Latest-set/cursor semantics | Natural mature candidates depend on chance low throughput | Prove a committed mature-candidate supply mechanism offline |
| Provider reliability | Rate limits, skipped intervals, latency, or missing fields can still block | Classify as source reliability when reached; do not auto-create a code lane |
| Single-use proof cost | An immature candidate can consume scarce governed work | Require pre-snapshot categorical admission and zero-call refusal proof |
| Small live evidence set | Six observations show repetition but not a universal distribution | Avoid probabilistic claims; require structural proof, not extrapolation |

## Closeout

E.35 closes as
`V2_9_7E_35_MISSING_APPROVED_MATURITY_BOUNDARY`. It authorizes no provider
call, implementation, configuration change, rerun, full pilot, or later
capability. Stop after committing this audit.
