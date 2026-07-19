# V2-9.7D.6B.3 Promotion/Safety Integration Closeout

## Result

V2-9.7D.6B.3 adds read-only campaign adapters for B.1 authoritative promotion
outcomes and B.2 effective/raw safety context. All verification used disposable
databases. No schema or persistent target was changed.

## Money-Usefulness Contribution

The adapters prevent later continuation logic from treating a clean-looking
window, a support event, or a manipulation claim as authoritative promotion or
safety evidence. They bind each fact to one campaign, run, cycle, token slot,
main window, close step, episode, checkpoint, and safety composite. This makes
selective continuation evidence auditable without enabling memory generation,
decisions, or financial activity.

## What 6B.3 Improves

- B.1 lookup exact-links the campaign graph to the migration-028 authoritative
  run, one expected close-step kind, one integer memory-window row, and an
  eligible episode.
- B.1 outcome classification delegates to the committed authoritative
  promotion functions and preserves clean-created, already-exists-idempotent,
  dirty/blocked, and no-promotion outcomes.
- Promotion is never inferred from memory quality. A 5m support window is
  rejected, and 5A-5C object payloads are not queried as promotion authority.
- B.2 lookup requires a `CHECKPOINT_5A` object exact-linked to the graph and its
  persisted safety-composite foreign key.
- B.2 preserves the full raw composite, source contribution traces, gate
  result, and timeframe-neutral effective report for 15m, 1h, and 4h.
- Target, memory-window, cutoff, freshness, request/response/failure trace, and
  token/mint/pair mismatches fail closed as blocked or unknown.
- Manipulation-context objects cannot supply or override B.2 safety authority.
- The 4A bridge accepts only marked B.1/B.2 reports with identical ownership
  identities and exposes the narrow evidence/safety fields already consumed by
  the committed continuation policy.
- Every adapter connection uses SQLite URI `mode=ro` and `query_only=ON`.

## What Remains Locked

B.3 lifecycle reconciliation/rotation, operational lease/runtime, final report
assembly, replay, source calls, scheduler execution, memory generation,
retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, wallets,
signing, and live execution remain locked. 6B.4 was not started.

## Proof Completed

- B.1 clean-created and already-exists-idempotent outcomes preserve exact
  episode and close-step identities;
- dirty/blocked and no-promotion remain non-promoted;
- campaign/run/cycle/token-slot/window mismatches fail closed;
- 5m support and 5A object claims cannot create promotion;
- B.2 accepts valid exact composites for 15m, 1h, and 4h;
- raw `SAFETY_UNKNOWN` and the legacy raw contract remain distinct from the
  authoritative effective acceptable result;
- source contribution request/response traces are retained;
- missing, stale, post-cutoff, and target-mismatched evidence is unknown or
  blocked;
- a manipulation object cannot replace a missing checkpoint safety composite;
- 4A continues only when its B.1/B.2 adapter facts are authoritative and
  identity-aligned;
- repeated reads are deterministic, database bytes remain unchanged, and
  locked-capability tables remain at zero rows.

## Functionality Risks / Setbacks / Efficiency Blockers

- B.1 still depends on migration 028's proof-only run ledger and embedded
  close-step `result_json` for created-versus-idempotent status. The adapter
  preserves that authority but does not remove its fragility.
- B.2 safety composites are checkpoint-linked through immutable 5A object rows.
  A missing link returns unknown even when another recent token-level composite
  exists; no latest-row guessing is allowed.
- The current safety schema has no stored `safety_action_label` column. The
  adapter preserves all stored raw fields and reports a null raw action label
  rather than synthesizing one.
- The 30-minute committed B.2 freshness contract is applied at the immutable
  checkpoint cutoff for every main timeframe. Longer-window refresh policy
  remains an operational integration concern.
- These adapters return evidence to callers but do not persist campaign report
  facts. Final immutable report assembly remains a later Slice 6 lane.

## Scope Confirmation

No migration, database write, source call, runtime action, lifecycle event,
lease, report, replay, retrieval row, decision, position, trade, audit, or PnL
was created. The persistent target and unrelated artifacts were untouched.
