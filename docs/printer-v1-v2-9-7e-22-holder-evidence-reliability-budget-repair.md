# V2-9.7E.22 Holder Evidence Reliability and Campaign Budget Repair

**Verdict:** `V2_9_7E_22_HOLDER_RELIABILITY_BUDGET_REPAIR_PASS`

**Baseline:** `0b8d1e916262250b79a4ba7af5b9617fc8800343`,
`Audit holder reliability and campaign budget`.

**Readiness:** READY only for one later, separately authorized bounded live
readiness cycle. This lane did not contact a provider, rerun E.20, or run a
pilot.

## Frozen design

The concise design was frozen before production edits in
`printer-v1-v2-9-7e-22-holder-evidence-reliability-budget-design.md`.
It defines one deterministic pre-activation `mature/reuse/reserve/pace` owner,
one 45-operation ledger, two non-spendable DexScreener snapshot reservations,
strict exact-evidence reuse, durable Scheduler maturation work, fixed
registry-derived pacing, and corrected failure precedence.

The requested `goplus-api-contract.md` is absent. The canonical committed
`goplus-solana-token-security-api-contract.md` was used instead. It provides no
exact provider-index maturity promise, so no threshold was invented.

## Exact implementation

- Finalized Pump proofs now pass structural zero-source gates and duplicate
  elimination before holder work. Ordering remains mint, pool, signature,
  slot; selection remains scoreless and exactly-two-or-none.
- A pre-slot operation ledger durably separates governed requests, underlying
  transports, zero-transport validation/reuse, the fixed campaign deadline,
  and the two reserved snapshot operations. Candidate admission refuses a
  worst-case reservation breach.
- Holder work stops once two candidates are eligible. Candidate replacement is
  only traversal of the already bounded deterministic set.
- Reuse requires exact lowercase mint, fixed holder purpose, exact source and
  endpoint role, original response lineage, capture and receipt times,
  unchanged parser/policy versions, complete/clean exact-target evidence, a
  known holder label, and the source registry TTL. Reuse records a new
  zero-transport lineage row; it never fabricates a provider response.
- Maturation is stored as pre-slot work with `scheduled_for`, deadline,
  cancellation and terminal completion. Waiting consumes zero source calls.
- Holder calls remain synchronous and non-overlapping. A one-shot pacer uses
  committed registry rates: GoPlus is spaced by three seconds and Solana RPC
  by two seconds. It performs one wait at most, with no retry, reconnect,
  recursion, endpoint rotation or automatic restart.
- The path remains one GoPlus call, primary RPC only when needed, and at most
  the existing fixed backup after an eligible transient primary failure.
- Source failures now retain their source-request foreign key. Attempt rows
  retain endpoint role, redacted host, RPC method, finalized commitment,
  context slot when returned, underlying operation count, response/failure
  identity, subtype and Retry-After time.
- The RPC transport now requests explicit `finalized` commitment, reports the
  one- versus two-method transport count, captures response context, and
  preserves HTTP Retry-After evidence when supplied.
- Holder reporting now classifies missing execution and governor/provider/
  transport/rate-limit/parser/no-response failure before examining target
  identity. Genuine parseable-response target mismatch remains blocking.

## Budget arithmetic

The ceiling remains exactly 45. The ledger starts with actual Pump underlying
operations plus any secondary governed requests, adds nine explicit
zero-transport combined-validation operations, and reserves exactly two
DexScreener snapshots. Each new candidate is admitted at a three-governed-call
worst case.

For the E.20 shape:

`floor((45 - 12 Pump - 9 validation - 2 snapshots) / 3) = 7 candidates`.

Seven worst-case candidates yield `12 + 9 + 21 + 2 = 44`, preserving one
unused operation and both snapshot slots. An eighth candidate is refused
before any request. Successful early evidence and exact reuse reduce actual
transport use; they never expand the derived cap.

## Maturation-threshold status

`UNPROVEN_DISABLED`; production threshold is `None`. E.20 showed missing
GoPlus holder data through 277 seconds, and the committed provider contract
does not guarantee an exact indexing age. The Scheduler work contract is fully
implemented and fixture-proven for waiting, due time, deadline refusal,
cancellation and replay, but activation requires later exact contract or
offline fixture evidence.

## Schema impact

Migration `037_holder_reliability_budget_control.sql` adds:

- nullable `printer_source_failures.source_request_id` with a foreign key;
- one pre-slot campaign operation-ledger table;
- one pre-slot maturation-work table; and
- one immutable-attempt/lineage table for holder evidence.

Existing slot/window ownership cannot represent candidates before activation,
so this narrow schema is necessary. It adds no lifecycle, memory, retrieval,
decision, position, trading, PnL, provider or wallet capability.

## Focused proof results

- E.22 repair tests: 6 passed. They cover fake-clock pacing, fixed spacing,
  budget cap/refusal, two-snapshot reservation, production threshold state,
  maturation waiting/deadline/cancellation/replay, exact reuse acceptance,
  mint/source/parser/policy/TTL rejection, request/failure/provenance linkage,
  Retry-After, integrity and foreign keys.
- E.19 holder/cleanup tests: 8 passed. They preserve factual holder outcomes,
  deterministic two-or-none behavior, no ranking, operational completion and
  exact campaign discovery cleanup.
- Fixed holder-backup plus E.22/E.19 focused group: 18 passed; no retry or
  endpoint-rotation behavior appeared.
- Source adapter/recording contract: 11 passed.
- Source Governor and Scheduler resource regressions: 23 passed.
- Authoritative live operational campaign regression: 18 passed.
- Final campaign report/replay: 4 tests and 3 subtests passed, including
  deterministic zero-source replay.
- Solana holder adapter/fixed redundancy regressions: 5 passed.
- Changed Python files compiled; `git diff --check` passed. No live request,
  authoritative-corpus write, E.20 mutation, lifecycle activation or memory
  promotion occurred.

## What improved

The campaign can no longer spend the full intake budget before reserving the
two market snapshots required to judge a future clean 15m outcome. Exact fresh
evidence can remove redundant calls without weakening identity or freshness
rules. Failures are attributable to the request, endpoint role and transport
method, and a 429 is no longer mislabeled as a target mismatch. Fixed pacing
also turns incidental latency into an explicit deterministic rule.

## Money-usefulness contribution

The repair preserves scarce free-source capacity for price, liquidity and
microstructure evidence instead of exhausting it on holder fallbacks. That
raises the chance that a future authorized cycle produces auditable clean
memory while still blocking unsafe or unverifiable candidates and avoiding
paid data.

## What remains locked

No live readiness cycle or pilot is authorized by this PASS. Retrieval, paper
decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, wallets, keys,
signing, real funds, live execution, paid APIs, new providers/endpoints,
scores, ranks, confidence, weighting, embeddings, vectors, V2-9.7F and V2-9.8
remain locked. The 5m window remains support-only.

## Functionality Risks / Setbacks / Efficiency Blockers

- GoPlus provider-index maturity is still unproven; maturation remains
  intentionally disabled instead of guessing a delay.
- Primary public-RPC shared capacity may still return 429 despite pacing.
- PublicNode independence and service guarantees remain unproven; it is only
  the already fixed backup, not evidence of meaningful redundancy.
- Registry TTL proves local receipt freshness, not upstream capture freshness.
- Strict reuse deliberately rejects otherwise similar evidence after any
  source, endpoint-role, parser or policy change.
- Pacing can consume additional campaign duration, but never additional calls.
- The lower budget-derived cap can reduce candidate yield; this is preferable
  to losing the two mandatory snapshot operations.
- A later live cycle may still block honestly with fewer than two eligible
  candidates or insufficient snapshot evidence. It must not auto-rerun.

## Next authorization boundary

One newly and explicitly authorized bounded live readiness cycle may test this
repair with the same 45 ceiling and fixed endpoints. PASS here does not
authorize that cycle automatically, and it does not authorize a full pilot.
