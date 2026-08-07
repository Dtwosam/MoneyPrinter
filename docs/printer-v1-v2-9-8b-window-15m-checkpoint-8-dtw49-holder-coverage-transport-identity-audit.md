# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — DTW-49 Holder Coverage Transport-Identity Reconciliation Audit

Date: 2026-08-07

Linear: `DTW-49`

Consumed proof:

- proof ID: `C8_REPROOF_AFTER_DTW48_20260807`
- immutable authorization/proof HEAD: `0640de69f462335643be72aed2a0a72617916d55`
- sentinel claimed: true
- frozen result: `HONEST_BLOCKED`
- terminal: `CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH`
- network attempts: zero
- no retry/rerun/resume/restart/successor authorized or performed

Verdict:

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_DTW49_HOLDER_COVERAGE_TRANSPORT_IDENTITY_PROJECTION_AUDIT_CONFIRMED`

## Scope and source-stack boundary

This is audit-only work under the active Printer V1 source stack and the V2-9.8B Checkpoint 8 boundary. It does not authorize implementation, another controlling proof, operational `WINDOW_15M` memory growth, provider/network access, authoritative DB use, `WINDOW_1H+`, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.

## What the consumed proof already proves

The post-DTW48 campaign passed the pre-holder path, executed holder collection, and then stopped before lifecycle at campaign source-request reconciliation. Therefore this is not a clean-memory failure and no lifecycle/clean-memory acceptance object can be used to explain the stop.

The campaign-wide reconciliation intentionally keeps governed request count and underlying transport-operation count separate. Multiple measured transports may lawfully belong to one governed request. The observed request/transport totals must not be forced equal.

## Reconciliation law at the consumed proof HEAD

`assemble_and_reconcile_campaign_source_requests()` requires:

`set(durable request IDs) == set(stage-reported request IDs) == set(stage-produced coverage request IDs)`

and independently validates exact per-request transport-identity ownership when invocation-scoped reconciliation is active.

For every stage-produced coverage row, exact reconciliation requires:

- a durable `source_request_id`;
- non-empty source/request/stage ownership;
- explicit `transport_identity_count`;
- explicit `normalized_member_count`;
- explicit `transport_identity_keys`;
- declared transport count equal to the number of canonical exact keys;
- no duplicate transport identity ownership.

Missing exact keys yields `SOURCE_REQUEST_TRANSPORT_IDENTITIES_MISSING`. A nonzero declared count with zero exact keys also yields `SOURCE_REQUEST_TRANSPORT_IDENTITY_COUNT_MISMATCH`.

## Proven holder projection defect

DTW-48 repaired the C8 GoPlus fixture so one actual governed holder execution now produces one truthful `HOLDER_SAFETY` measured transport identity in the caller-owned holder ledger and normalized payload.

The real holder persistence owner then calls `_persist_one_holder_attempt()` in `holder_reliability_budget_control.py`.

At the consumed proof HEAD, its stage coverage row contains:

- `source_request_id`
- `source_name`
- `request_kind`
- `logical_stage_id`
- `terminal_status`
- `transport_identity_count`
- `normalized_member_count`

but it omits `transport_identity_keys`.

This is not an absence of transport evidence. `persist_bundle_attempts()` separately reads and canonicalizes the same execution payload identities and returns them in `HolderBundlePersistResult.transport_identities`. The identity exists; the per-request campaign coverage projection drops its keys.

For a successful DTW-48 GoPlus holder attempt the resulting coverage row therefore declares `transport_identity_count=1` while exact key ownership is absent. Under the scoped reconciliation law this necessarily blocks exact transport completeness with at least:

- `SOURCE_REQUEST_TRANSPORT_IDENTITIES_MISSING`
- `SOURCE_REQUEST_TRANSPORT_IDENTITY_COUNT_MISMATCH`

before lifecycle handoff.

This statically reproduces the consumed terminal class without changing request counts, transport counts, stage ceilings, six-unit rules, Source Governor, or Scheduler behavior.

## Classification

The proven DTW-49 defect class is:

`CHECKPOINT8_HOLDER_COVERAGE_TRANSPORT_IDENTITY_KEYS_DROPPED_BEFORE_RECONCILIATION`

This is a holder coverage-projection defect in the production accounting carrier, exposed by the truthful DTW-48 fixture repair.

It is not evidence for:

- forcing governed request count to equal transport-operation count;
- reducing PumpSwap multi-transport accounting;
- fabricating transport identities;
- weakening exact reconciliation;
- weakening six-unit accounting;
- raising holder/source budgets;
- changing Source Governor or Central Scheduler ownership;
- changing clean-memory acceptance.

The exact numeric request IDs in the retained local DB are not required to prove this code-path defect: every successful holder coverage row with a nonzero measured identity is malformed for scoped reconciliation at this HEAD because its projection omits the required key field. No claim is made here that no additional frozen-evidence category could coexist; this proven defect alone is sufficient to make the final reconciliation fail closed.

## Required design direction

A design may proceed, but it must remain narrow:

1. preserve exact transport identity keys from the already validated holder execution into the per-request holder coverage row;
2. derive keys only from the real normalized execution payload using the existing canonical measured-transport primitive;
3. keep `transport_identity_count` equal to the exact number of carried canonical keys;
4. fail closed on malformed, duplicate, target-mismatched, or count-mismatched holder identities;
5. preserve partial/blocked attempt truth without inventing keys for unproven work;
6. prove final campaign reconciliation accepts lawful holder rows while still rejecting missing/mismatched identity keys;
7. make no change to budgets, six-unit validation, Source Governor, Scheduler, provider transports, memory owners, or capability locks.

## Money-usefulness contribution

This repair direction preserves truthful holder-source provenance all the way into campaign reconciliation. Clean holder evidence cannot safely support 15-minute memory if its transport ownership is lost between execution and the campaign manifest.

## What this audit improves

- identifies the first proven post-holder reconciliation defect;
- preserves the distinction between governed requests and underlying transports;
- localizes the problem to holder per-request coverage projection;
- prevents a false fix that would distort PumpSwap transport accounting or weaken reconciliation.

## What remains locked

Checkpoint 8 remains open. No new controlling proof is authorized. Operational `WINDOW_15M` memory growth and every later capability remain locked.

## Functionality Risks / Setbacks / Efficiency Blockers

1. The retained local frozen DB is not available to this connected review, so exact holder request IDs are intentionally not asserted.
2. A later repair must preserve exact per-request ownership; copying only a campaign-wide identity list would be insufficient.
3. Partial holder persistence paths may require separate treatment only if focused RED proves they lose already-proven keys; scope must not expand speculatively.
4. A later one-shot proof may reveal another downstream blocker after this reconciliation defect is removed. That would require a new evidence-driven lane, not a rerun.
