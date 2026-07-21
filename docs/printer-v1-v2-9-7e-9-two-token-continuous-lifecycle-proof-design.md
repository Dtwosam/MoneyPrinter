# V2-9.7E.9 Two-Token Continuous Lifecycle Proof Design

**Status:** FROZEN FOR IMPLEMENTATION
**Lane:** V2-9.7E.9
**Date:** 2026-07-21
**Boundary:** deterministic fixture proof only; no live pilot

## Todo / Checklist

- [x] Audit the single-token ceiling and the incomplete E.8 assertions.
- [x] Separate production safety from proof-harness constraints.
- [x] Freeze an exact-identity, proof-only two-token disposition contract.
- [x] Implement the minimum proof-scoped changes.
- [x] Prove terminal 15m/1h/4h, promotion, 5m, cleanup, and replay.

## Root-Cause Audit

`_CONTINUOUS_MAX_SELECTED_TOKENS == 1` is an intentional historical
compressed-proof limit in `one_command_15m_factory`, not a general production
token ceiling. It is repeated in three proof assumptions:

1. preflight rejects continuous runs unless `max_selected_tokens == 1`;
2. continuous governed-request and Scheduler-row ceilings reserve capacity for
   one 15m and one 1h lifecycle only; and
3. `one_token_4h_runtime.plan_current_run_4h` requires the factory run's
   `selected_token_count` to equal one.

The lifecycle loop itself has no one-token correctness dependency. Steps carry
exact token/pair identities, token failures cancel only that token's pending
steps, and the Scheduler orders by `(scheduled_for, id)`. Separate opening
snapshots establish token-local clocks. The audit also found that two deterministic closes at an identical timestamp collide in the global broad-context deduplication key; the proof clock therefore advances deterministic microsecond boundaries between operations, matching real execution without changing deadlines.

Shared request and Scheduler counts are
the only capacity constraints; their single-token values are proof budgets,
not evidence that two token identities collide.

E.8 did not prove terminal continuous depth. Its continuation test manually
created a one-item selection batch from one of the two activated slots, enabled
`continuous_first_hour` but not `continuous_four_hour`, and asserted only that
the report contained `continuation_1h` and `continuation_4h` structures. Those
keys exist even when empty. It did not require a succeeded 1h close, a planned
and succeeded 4h close, or a terminal 4h window. The short wall-clock values
also did not exercise the fixed production 4h boundary.

## Frozen Minimum Design

### Scope

Add an explicit compressed two-token proof plan to the existing lifecycle
owner. It is accepted only when all of the following hold:

- `proof_mode`, `continuous_first_hour`, `continuous_four_hour`, and
  `four_hour_proof_mode` are true;
- an injected origin `discovery_runner` is present, so legacy discovery cannot
  run;
- `max_selected_tokens == 2`;
- the plan names exactly two distinct mints: one continuation target and one
  non-continuation target;
- after origin handoff, those names exactly equal the two already-selected
  target mints; and
- the continuation target is the deterministic later target in the factory's
  stable target order, so both 15m closes finish before continuation work is
  introduced.

The plan records fixture evidence dispositions, not market scores or forced
outcomes:

- continuation: `LIQUIDITY_SHOCK_OBSERVED`;
- non-continuation: `NO_UNRESOLVED_LEARNING_NEED`; and
- support-only 5m trigger: one approved trigger family for the continuation
  target.

The non-continuation target receives a recorded valid no-capture/no-
continuation disposition. It creates no 5m window and no successor jobs.

### Ownership and timing

The existing factory remains the sole lifecycle owner. The origin driver still
runs discovery/origin/gates/selection/atomic activation exactly once and
materializes the exact activated identities without reselection. All source
operations remain governed and all lifecycle work remains Scheduler-owned.

Production timing, deadlines, cutoff semantics, cadence policies, and close
functions are unchanged. Focused tests advance a deterministic injected clock
through the real 15m, 1h, and 4h durations; they do not shorten or rewrite
production deadlines.

### Budget boundary

Normal continuous mode stays capped at one proof token. The new mode adds only
the second token's policy-derived 15m request/context and Scheduler allowance
to the existing one-token 15m+1h+4h cumulative ceiling. Per-token ceilings,
4h phase ceilings, zero retry, and zero endpoint rotation remain unchanged.
No general production ceiling is raised.

### 4h owner

The 4h owner remains one-token. In explicit two-token proof mode it may accept
a run with two selected targets only when exactly one succeeded 1h close exists
and it belongs to the requested continuation identity. All long-continuation
steps must remain on that identity. Replay and partial-plan checks remain
fail-closed.

### Strict terminal validation

The final report gains a proof validation that requires:

- exact two-target identity match;
- two succeeded terminal 15m close steps;
- no continuation steps for the non-continuation target;
- exactly one succeeded 1h close for the continuation target;
- exactly one succeeded support-only 5m step for that target and zero 5m rows
  for the other;
- exactly one succeeded terminal 4h close and `WINDOW_4H` successor;
- zero pending/running steps and jobs; and
- all retrieval/financial deltas zero.

An incomplete proof cannot retain `COMPLETED`; it fails closed with a dedicated
safe-stop reason. Tests must assert terminal evidence, not report structure.

### Safety-label consistency

The integrated clean-promotion proof exposed an existing reporting/classification
inconsistency: a canonical `SAFETY_CONTEXT_ACCEPTABLE` effective 15m result was
still downgraded by explanatory raw GoPlus `SAFETY_UNKNOWN` fields. The narrow
repair preserves those raw observed labels in reports but excludes them from
unknown blockers only when the canonical effective safety gate is already
accepted. Blocked or unknown effective safety remains fail-closed. This does not
change provider evidence, gates, or authority.
## Rejected Alternatives

- Raising `_CONTINUOUS_MAX_SELECTED_TOKENS` globally: rejected because it would
  broaden an older production/proof contract without a live-capacity audit.
- Running two separate factory runs: rejected because it would not prove one
  atomic two-slot campaign or one final report.
- Copying one slot into a single-token batch: rejected because that is the E.8
  proof gap.
- Shortening 4h production deadlines: rejected because it changes lifecycle
  semantics merely to make a test faster.
- Retrospective or synthetic market triggers: rejected. Fixtures must carry
  the declared eligible continuation/support evidence before execution.

## Locks

No live source, pilot, wallet, signing, key, fund, execution, paid API,
retrieval, decision, BUY/SELL/HOLD, position, trade, audit, PnL, scoring,
ranking, confidence, weighting, embedding, vector, Governor bypass, Scheduler
bypass, discovery reopening, or origin-authority change is authorized.

## Functionality Risks / Setbacks / Efficiency Blockers

- The proof plan is deliberately fixture-only; it does not activate two-token
  continuous mode for a real command.
- Deterministic tests still execute every policy-derived snapshot and governed
  fixture request, so the focused proof is larger than the E.8 structural test.
- A token-local failure makes the strict integrated proof incomplete even when
  isolation works correctly; that negative case must be asserted separately.
- The 4h owner remains intentionally one-continuation-token and must fail if a
  second 1h continuation appears.
- Live timing, provider retention, and operational throughput remain unproved
  until an explicitly authorized pilot rerun.
