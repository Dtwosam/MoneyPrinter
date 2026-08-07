# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — DTW-50 Holder Request Scope Propagation Repair Design

Date: 2026-08-07

Linear: `DTW-50`

Audit commit: `6120370d8346337e7408695a4ec20e243b99c7ac`

Status:

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_DTW50_HOLDER_REQUEST_SCOPE_PROPAGATION_REPAIR_APPROVED_FOR_OFFLINE_IMPLEMENTATION_ONLY`

## Design decision

Propagate the already-built and already-validated permanent campaign `request_key_root` into holder request construction. Do not reconstruct campaign scope and do not change reconciliation.

### 1. Authoritative holder funnel

Extend `AuthoritativeLiveOperationalCampaignOwner._evaluate_holder_eligibility()` with an optional `campaign_request_key_root` argument.

For permanent memory-observation mode, require a non-empty root before any holder provider call. For each candidate ordinal, derive a deterministic holder-local prefix beneath that root:

`<campaign_request_key_root>-holder-<ordinal>-context`

Pass that prefix to `_collect_preclose_context()`.

`run_operational()` obtains the root only from the validated existing supply diagnostics (`request_key_root`) and passes it to the holder funnel. It must not manufacture a second root.

### 2. Preclose context owner

Extend `one_command_15m_factory._collect_preclose_context()` with optional `request_key_prefix: str | None = None`.

- when omitted: preserve the existing legacy/default prefix `run_id:step_key:context` exactly;
- when supplied: use the explicit non-empty prefix verbatim as the governed request prefix.

All provider ordering, request kinds, budgets, pacing, Source Governor execution and partial-execution behavior remain unchanged.

### 3. Sole holder backup

Extend `safety_context_source_redundancy.execute_solana_rpc_holder_backup()` with optional `request_key_prefix: str | None = None`.

When explicit prefix is supplied by `_collect_preclose_context()`, build the backup request beneath the same prefix as `<prefix>:holder_backup`. Otherwise preserve the legacy `run_id:step_key:context:holder_backup` key exactly.

No backup eligibility, provider, retry, endpoint, budget or evidence law changes.

## Approved implementation surface

Production:

1. `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
2. `src/printer_v1/operator_cli/one_command_15m_factory.py`
3. `src/printer_v1/operator_cli/safety_context_source_redundancy.py`

Proof:

4. `tests/test_v2_9_8b_window_15m_checkpoint8_holder_request_scope.py`

No other file may change in the implementation commit.

## Deterministic RED

The new focused regression at the audit/design baseline must show:

1. the existing holder funnel creates a GoPlus `safety_reference` request whose durable key does not start with the canonical campaign `request_key_root`;
2. strict `assemble_and_reconcile_campaign_source_requests()` therefore returns `CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH` with the holder request outside scope / manifest-not-durable classification.

The RED must be caused by request-key scope propagation, not fixture/network/setup failure.

## GREEN acceptance

The focused regression must prove:

- one permanent holder GoPlus request uses `<root>-holder-1-context:safety` (or the same canonical rooted deterministic pattern);
- a sole eligible backup, when exercised, uses the same rooted holder prefix and remains a separate governed request;
- every rooted holder request is included by the exact existing `CampaignSourceRequestScope` lookup;
- durable request IDs, stage-reported IDs and manifest IDs are equal;
- transport identity completeness remains `OK`;
- governed request count and underlying transport count remain separately truthful;
- default/non-campaign `_collect_preclose_context()` behavior retains the legacy `run_id:step_key:context:*` contract;
- zero network attempts in fixture proof.

Minimum sufficient offline proof:

1. `py_compile` four changed modules/files;
2. dedicated DTW-50 regression;
3. existing C8 real-consumer compatibility;
4. full focused `tests/test_v2_9_8b_window_15m_checkpoint8_*.py` suite;
5. exact four-file implementation manifest;
6. `git diff --check`.

## Money-usefulness contribution

This restores truthful holder evidence to the same durable campaign provenance boundary as discovery and market evidence, which is necessary before clean 15-minute memory can be trusted.

## What remains locked

No controlling C8 proof is authorized by this design. Operational `WINDOW_15M` memory activation, `WINDOW_1H+`, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits and PnL remain locked.

## Functionality Risks / Setbacks / Efficiency Blockers

1. Optional prefix support must not alter ordinary memory-close callers.
2. Holder backup must not retain the old out-of-scope namespace when primary fails.
3. The root must come from the existing validated campaign scope; duplicate derivation is forbidden.
4. Reconciliation and scope membership remain strict and unchanged.
5. A future C8 attempt remains one-shot and separately authorized only after offline closeout and independent readiness review.
