# V2-9.7E.19 Holder-Evidence Eligibility and Clean-Memory Repair — Design

**Status:** DESIGN GATE PASSED

**Design verdict:** `PASS`

## Scope and baseline

This lane implements only the operator-approved E.19 repair at commit
`77e7630e711ba39c1969519158646f2c3f820fde`. It preserves Solana-only,
memecoin-only, paper-only operation and every retrieval, decision, position,
PnL, wallet, paid-source, score, rank, confidence, weighting, embedding and
live-execution lock. No provider contact or pilot rerun is part of this lane.

No schema migration is required. Existing source-request/response/failure,
discovery-candidate, Scheduler-job, snapshot-provenance and run-report storage
is sufficient.

## M1 — pre-activation holder-evidence eligibility

Holder concentration remains mandatory in the safety composite. E.19 does not
reinterpret unavailable evidence as safe and does not weaken memory quality.

The operational live owner evaluates a fixed, bounded, deterministic set of at
most eight finalized Pump-origin candidates before combined-discovery
activation. Candidates are ordered by exact mint, bonding-curve identity,
signature and slot; the first eight are evaluated. For each candidate it calls
the existing governed pre-close safety collection owner with a candidate-local
request key. That owner remains the sole source-law implementation:

1. one governed GoPlus token-safety request;
2. Solana RPC holder evidence only when GoPlus holder concentration is unknown;
3. exactly one already-authorized, governed, distinct-endpoint backup only for
   the existing eligible transient-primary failure;
4. no retry, backoff, endpoint rotation, new provider or raised ceiling.

A candidate is holder-evidence eligible only when one response from that path
is `COMPLETE`, `CLEAN_DATA`, non-stale, non-malformed, exact-target for the mint,
and has a holder-concentration label other than
`HOLDER_CONCENTRATION_UNKNOWN`. GoPlus evidence and Solana-RPC evidence retain
their own source identity; they are never blended or reattributed.

Unavailable, failed, stale, malformed, target-mismatched or unknown holder
evidence makes only that candidate ineligible. A factual reason and source are
persisted in its evidence gaps. The candidate is not labelled unsafe merely
because evidence is unavailable.

The existing fixed eligibility-gate order consumes this fact before the
existing deterministic uniform selection and atomic handoff. Selection remains
scoreless and rankless. The result is exactly two eligible active slots or no
activation. Fewer than two produces the existing
`INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL` terminal block and no first-15m lifecycle
job. Candidate replacement means only selection from the already bounded,
already evaluated set; it performs no new source call.

Readiness-only behavior is unchanged: E.19 governs operational activation, not
the disposable E.11 source/readiness diagnostic.

## M2 — verified inactivity normalization

The exact-pair snapshot persistence boundary may convert a missing 5m/15m
activity field to numeric zero only after all of these facts are proven:

- the governed source response is `COMPLETE` and `CLEAN_DATA`;
- normalized JSON is valid and the exact Solana mint and expected pair match;
- `price_usd` and `liquidity_usd` are finite and strictly positive;
- wider activity `volume_1h` and `txns_1h` are finite, non-negative and both
  zero, positively proving inactivity across the containing wider window;
- no stale, malformed, failed or target-mismatch condition is present.

Only missing `volume_5m`, `volume_15m`, `txns_5m`, `txns_15m`,
`price_change_5m` and `price_change_15m` are filled. Existing values are never
changed. Snapshot provenance records `SNAPSHOT_VERIFIED_INACTIVE`, its exact
predicate and the fields converted. If any predicate fails, fields remain
missing so existing quality logic remains dirty/fail-closed.

## M3 — operational-natural terminal completion

Explicit compressed/proof-mode 4h behavior remains unchanged. A qualifying
operational-natural token still follows 15m → 1h → 4h and must satisfy the
existing complete 4h terminal audit.

An operational-natural run whose 4h phase is `NOT_STARTED` is `COMPLETED` only
when all of the following hold:

- exactly two distinct selected tokens have succeeded terminal `WINDOW_CLOSE`
  steps with attached `WINDOW_15M` rows;
- both windows are `CLEAN_MEMORY` with `CLEAN_DATA`, are complete, and are not
  `do_not_train`;
- both close results contain a factual `STOP_AFTER_15M` continuation disposition
  with zero planned jobs;
- the two-close barrier has resolved, no 1h/4h continuation step exists, no
  pending/running run step or job exists, budgets are not exceeded and no
  authoritative source/run failure is present.

Dirty, partial, missing or ambiguous closes cannot produce completion. They
remain honest safe stops with zero false clean yield.

## O1 — exact campaign discovery-job cleanup

At terminalization the factory cancels only Scheduler jobs satisfying all of:

- `job_kind = DISCOVERY_REFRESH`;
- status is `PENDING` or `RUNNING`;
- ownership is proven by a `printer_discovery_work` row for the exact discovery
  handoff `run_id`, with campaign identity already bound by the campaign/run
  source tables.

Cleanup uses the canonical Scheduler cancellation owner, is idempotent, reports
the cancelled count, and preserves unrelated discovery and non-discovery jobs.
It does not broaden cleanup to `COOLDOWN` or infer ownership from a loose name
prefix.

## Frozen budgets, ordering and writes

- Holder candidate bound: eight.
- Per candidate: one GoPlus; RPC only when needed; at most one existing backup.
- No ceiling increase; existing Source Governor and Scheduler owners remain
  authoritative.
- Candidate ordering and selection remain deterministic and scoreless.
- New writes are limited to existing governed source audit rows, candidate
  evidence-gap JSON, snapshot provenance, Scheduler cancellation state and
  final-report cleanup facts.
- No migration, new source, retry, rotation, background loop or independent API
  owner.

## Required offline proof

Focused tests must prove valid/missing/mismatched/stale/failed holder evidence,
bounded deterministic replacement and fewer-than-two blocking; verified
inactive conversion plus all negative predicates and active-market invariance;
operational two-clean-stop completion, dirty-stop refusal and unchanged
qualifying/proof-mode continuation; exact idempotent discovery cleanup; source
budgets, isolation, atomic two-or-none activation and all permanent locks.

## Design gate conclusion

The design changes candidate eligibility, truthful absence semantics and
terminal cleanup only. It neither weakens holder safety nor invents market
evidence, and it keeps source and Scheduler ownership intact. Production
implementation may proceed.
