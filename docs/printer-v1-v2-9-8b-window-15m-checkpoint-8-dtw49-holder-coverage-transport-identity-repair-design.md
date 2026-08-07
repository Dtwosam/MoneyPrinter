# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — DTW-49 Holder Coverage Transport-Identity Projection Repair Design

Date: 2026-08-07

Audit HEAD: `fa51dab6aef22af89b130be7ec1d1b39ae2a99a6`
Linear: `DTW-49`

Status:

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_DTW49_HOLDER_COVERAGE_TRANSPORT_IDENTITY_PROJECTION_REPAIR_APPROVED_FOR_OFFLINE_IMPLEMENTATION_ONLY`

## Decision

Repair only the holder per-request coverage projection that drops already-proven measured transport identity keys before campaign source-request reconciliation.

Do not alter governed request counts, transport counts, stage ceilings, PumpSwap multi-transport behavior, six-unit validation, Source Governor, Central Scheduler, provider transports, holder admission, memory owners, or capability locks.

## Approved implementation surface

Exactly these two files may change:

1. `src/printer_v1/operator_cli/holder_reliability_budget_control.py`
2. `tests/test_v2_9_8b_window_15m_checkpoint8_real_consumer_compatibility.py`

Any need for a third file stops implementation and returns to audit/design.

## Required production behavior

For every holder execution persisted by `persist_bundle_attempts()`:

1. the per-request `source_request_coverage` entry must contain an explicit `transport_identity_keys` field;
2. keys must be derived only from the same real normalized execution payload already used by holder transport measurement;
3. each key must use the existing canonical measured-transport identity primitive;
4. in exact-identity mode, a successful nonzero transport count requires exactly the same number of canonical keys;
5. keys must remain owned by the exact `source_request_id` and existing holder `logical_stage_id`;
6. target/source/request correspondence validation already enforced by holder measurement remains unchanged;
7. no campaign-wide identity list may be copied blindly into an individual request row;
8. lawful zero-transport coverage must carry an explicit empty key list, not an omitted field;
9. malformed, duplicate, absent, target-mismatched, or count-mismatched exact identities remain fail-closed.

The existing `HolderBundlePersistResult.transport_identities` remains a campaign/stage convenience view; it does not replace exact per-request key ownership.

## Partial/blocked attempts

Do not invent keys for work that was not proven.

If an execution already contains valid measured identity metadata before a later persistence failure, a blocked coverage row may preserve those exact proven keys only if the focused RED demonstrates that this path is affected and the keys can be bound to that exact request without inference.

Otherwise partial/blocked behavior is unchanged in this lane. No speculative broadening is approved.

## Deterministic RED

At the audit/design baseline, add one focused C8 regression using the real DTW-48 GoPlus fixture execution and real `persist_bundle_attempts(..., require_exact_transport_identities=True)` path.

The RED must prove:

- governed GoPlus result is clean and exact-target;
- normalized payload contains exactly one canonical measured holder identity;
- holder persistence returns `transport_identity_count == 1` for that request;
- the resulting coverage row lacks exact transport identity keys or fails exact campaign transport-manifest validation;
- zero network attempts.

Expected RED classification:

`DTW49_HOLDER_COVERAGE_TRANSPORT_IDENTITY_KEYS_DROPPED_RED_CONFIRMED`

No controlling sentinel, campaign runtime, or second C8 proof is allowed for this RED.

## Minimum sufficient GREEN

After the two-file repair, require:

1. changed-file `py_compile` PASS;
2. targeted DTW-49 regression PASS, proving one GoPlus governed request yields:
   - one holder coverage row;
   - `transport_identity_count == 1`;
   - exactly one `transport_identity_key`;
   - canonical equality with the normalized payload identity;
   - exact request/stage ownership;
   - exact transport-manifest validation `OK`;
   - zero network attempts;
3. full C8 real-consumer compatibility file PASS;
4. complete focused `tests/test_v2_9_8b_window_15m_checkpoint8_*.py` PASS;
5. `git diff --check` PASS;
6. exact two-file changed manifest;
7. no provider/network execution and no controlling proof.

No broad repository suite is required for this narrow carrier repair.

## Implementation shape

Prefer a small internal helper in `holder_reliability_budget_control.py` that canonicalizes the execution payload's `transport_operation_identities` into per-request keys without changing measurement policy.

The coverage entry produced by `_persist_one_holder_attempt()` should always expose `transport_identity_keys`, including an explicit empty list for lawful zero transport.

Do not reconstruct keys from counts, source names, endpoints, or campaign ledgers. The payload identity is the evidence source.

## Stop conditions

Stop and return to audit/design if:

- any third file is required;
- a key would need to be inferred rather than carried from measured evidence;
- a budget/ceiling change appears necessary;
- six-unit or reconciliation validation would need weakening;
- Source Governor or Scheduler behavior would need changing;
- focused GREEN reveals a different reconciliation defect;
- provider/network/runtime/authoritative DB access would be required.

## Money-usefulness contribution

This closes the provenance gap between holder execution and campaign reconciliation. A memory-growth system cannot trust holder safety evidence if transport ownership is measurable at execution but disappears from the campaign manifest.

## What this improves

- exact holder per-request transport provenance;
- final campaign request/transport reconciliation fidelity;
- truthful distinction between one governed request and one-or-more underlying transports;
- C8 ability to reach lifecycle without weakening accounting.

## What this still does not unlock

- another Checkpoint 8 controlling proof;
- Checkpoint 8 completion;
- operational `WINDOW_15M` memory growth;
- provider/network access;
- authoritative DB use;
- `WINDOW_1H+`;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions, trades, audits, or PnL.

## Functionality Risks / Setbacks / Efficiency Blockers

1. **Count-only repair:** forbidden; exact key ownership must be carried.
2. **Campaign-wide key leakage:** prevented by deriving keys per exact execution/request.
3. **Legacy zero-transport behavior:** explicit empty keys preserve truth without fabricating work.
4. **Partial failure ambiguity:** remains out of scope unless focused RED proves exact already-measured keys are lost there too.
5. **Later blocker risk:** even a correct repair does not guarantee C8 end-to-end PASS; a future authorized one-shot attempt may expose a new downstream defect.

No new Checkpoint 8 controlling proof is authorized by this design.
