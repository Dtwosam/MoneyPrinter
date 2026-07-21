# V2-9.7E.9 Two-Token Continuous Lifecycle Proof Closeout

**Status:** PASS
**Date:** 2026-07-21
**Baseline:** `d3ea14ee8c5f30665c21ec7cddb46f8058fb3daa`
**Boundary:** deterministic fixtures and disposable migration-036 databases only

## Todo / Checklist

- [x] Audit the E.8 single-token proof blocker.
- [x] Freeze the minimum exact-two-token proof design.
- [x] Implement proof-scoped two-token lifecycle ownership and budgets.
- [x] Prove terminal 15m, 1h, 4h, promotion, 5m, cleanup, and replay.
- [x] Run directly affected focused regressions and static checks.
- [x] Preserve every paper-only, source-governance, and financial lock.

## Root cause and impact

`_CONTINUOUS_MAX_SELECTED_TOKENS == 1` was a compressed-proof harness limit,
not a lifecycle-owner requirement or a general production token ceiling. It was
duplicated in factory preflight, first-hour request/Scheduler budgets, and the
one-token 4h planner's selected-count guard. E.8 then copied one activated slot
into a one-item batch and asserted only that 1h/4h report structures existed;
it did not prove a terminal 1h close or any 4h work.

The lifecycle ledger was already token-local. Scheduler order is deterministic
by due time and row identity, first snapshot anchors are independent, and a
token failure cancels only that token. No general production token ceiling was
raised. Ordinary continuous proof remains exactly one token.

The integrated run exposed two additional bounded proof facts:

1. identical deterministic close timestamps collide with global broad-context
   timestamp deduplication; the fixture clock now advances deterministic
   microseconds while retaining the real 900/2700/10800-second boundaries; and
2. explanatory raw GoPlus unknown labels were overriding an already accepted
   timeframe-aware safety result. Raw labels remain visible, but cannot create
   an unknown blocker when the canonical effective safety gate is
   `SAFETY_CONTEXT_ACCEPTABLE`. Unknown or blocked effective safety still fails
   closed.

## Files changed and implementation

- `one_command_15m_factory.py`: adds the exact proof plan, exact-identity
  validation, continuation split, proof-only additive ceilings, per-token
  accounting, and strict terminal proof validator.
- `one_token_4h_runtime.py`: accepts two selected identities only in the
  explicit proof mode and only when exactly one current-run continuation close
  matches the requested token/pair/lane.
- `commands.py`: reconciles explanatory raw safety labels with the canonical
  effective safety gate without discarding observed evidence.
- E.8/E.9 focused tests: deterministic provenance, migration-036 fixtures,
  complete campaign proof, rollback, mismatch, failure isolation, replay, and
  fail-closed safety checks.
- E.9 design/closeout and dated E.8 correction.

No schema, migration, public CLI, live source, real wall-clock runtime, origin
architecture, discovery/reselection path, campaign activation rule, or
financial capability was added.

## Strict terminal evidence

One deterministic origin-to-lifecycle campaign proved:

- two finalized Pump origins and exactly two atomic activated slots;
- exact mint/pair projection with no second discovery or reselection;
- two succeeded audited `WINDOW_15M` closes;
- token A: explicit `VALID_NO_CAPTURE` and `STOP_AFTER_15M`;
- token B: naturally observed synthetic 50% liquidity change, one support-only
  `WINDOW_5M_MICRO_EVENT`, one succeeded terminal `WINDOW_1H`, and one
  succeeded terminal `WINDOW_4H`;
- exactly one eligible authoritative `printer_episodes` promotion attached to
  a main window, zero non-clean episode promotions, and zero episode rows for
  the 5m support window;
- final report persisted once; report-only replay is byte-stable and creates
  zero source/evidence rows;
- zero pending/running run steps, zero active Scheduler jobs, and zero
  retrieval/financial table deltas.

The strict report validator returned `complete=true`, with counts `15m=2`,
`1h=1`, `4h=1`, `clean promotions=1`, `dirty promotions=0`.

## Scheduler, budgets, and identity

The two 15m streams interleave deterministically and both close before the
single continuation chain. The failure fixture proves token A can terminally
fail while token B still reaches its terminal 4h close. Atomic failure during
the second activation rolls back both slots and starts no lifecycle.

Observed governed usage was 75/82 cumulative requests (`t1=13`, `t2=62`, each
within the cumulative per-token ceiling), 36/39 4h-phase requests, 62/67
Scheduler rows, zero automatic retries, zero endpoint rotation, and zero holder
fallback calls. Ceilings are policy-derived maxima, not targets.

## Focused proof

All 255 focused tests passed:

- E.9 exact-two-token proof: 6;
- E.8 origin-to-lifecycle regression: 14;
- factory, one-token 4h, first-hour readiness: 27;
- 5m support-only integration: 110;
- Scheduler fairness, promotion safety, timeframe safety: 23;
- final report, durable supervision, terminal cleanup: 15;
- continuous lifecycle/runtime and long-window cadence/continuity: 60.

Static compilation, Governor/Scheduler ownership scans, and both diff checks
also passed. No broad repository suite and no live provider call were run.

## Money-usefulness contribution

Printer can now prove, without fabricated profit or live-source risk, that one
atomic two-token intake campaign preserves independent evidence, stops one
token conservatively, continues the other through terminal 4h, and promotes
only authoritative clean main memory. This closes the exact proof gap that made
E.8's readiness statement premature while retaining all capital-protection
locks.

## What remains locked

Live pilot and pilot rerun; V2-9.7F/V2-9.8; retrieval; paper decisions;
BUY/SELL/HOLD; positions; trades; audits; PnL; wallet, private keys, signing,
funds, or execution; paid APIs; scoring/ranking/confidence/weighted logic;
embeddings/vectors; Governor or Scheduler bypass; non-finalized/wrong-mint Pump
origin; non-atomic activation; 5m main-outcome authority; automatic successor
or restart.

## Functionality Risks / Setbacks / Efficiency Blockers

1. This is a fixture-only compressed proof seam. It does not expose two-token
   continuous mode through a public or live command.
2. The final per-token yield projection reports each token's latest terminal
   window, so it under-counts the earlier authoritative clean 15m promotion on
   the token that later ends dirty at 4h. The strict proof validator queries the
   authoritative episode join and reports the correct count; the historical
   run-local yield projection remains a reporting limitation.
3. The proof executes every policy-derived fixture snapshot, so focused runs
   are materially heavier than E.8's structural assertion.
4. Provider retention, real latency, and operational throughput remain
   unproved. They require an explicitly authorized live pilot rerun.
5. The 4h owner intentionally permits only one continuation identity; a second
   1h continuation or ambiguous identity fails closed.

## Readiness

**READY for one separately authorized V2-9.7E live pilot rerun.** This means the
offline integrated blocker is closed. It does not authorize or execute that
pilot, and it does not unlock any downstream or financial capability.

## Verdict

`V2_9_7E_9_TWO_TOKEN_CONTINUOUS_LIFECYCLE_PROOF_PASS`
