# Printer V1 V2-9.8B WINDOW_15M Source-Request Scope Enforcement Follow-up Design

## Verdict

`V2_9_8B_WINDOW_15M_SOURCE_REQUEST_SCOPE_ENFORCEMENT_FOLLOWUP_DESIGN_COMPLETE`

Design-only. No production code, tests, authorization, provider, runtime, or database work was changed or executed.

## Baseline

- audit branch: `agent/v2-9-8b-window-15m-source-request-scope-enforcement-followup-audit`
- audit commit: `7a1d452cf22535daa640072204064b77df47214c`
- repair being tightened: `d9b2deb5ea35ae9035702f90343d3818bf6ac536`
- controlling audit: `docs/printer-v1-v2-9-8b-window-15m-source-request-scope-enforcement-followup-audit.md`

## Objective

Make the canonical reconciliation owner enforce the same typed invocation scope already required by the permanent operational composition.

Preserve:

`D = S = M`

while guaranteeing that every member of `D` belongs to the one canonical `request_key_root` whenever scoped enforcement is active.

## Production scope

Expected production change:

- `src/printer_v1/discovery/permanent_discovery_availability.py`

Modify another production module only if focused proof demonstrates the public caller does not pass enough identity to validate the scope. Do not change providers, campaign composition, source budgets, Scheduler, selection, temporal rules, holder policy, lifecycle, schema, authorization, or locked capabilities.

## 1. Strict scoped-reconciliation entry contract

When either `campaign_source_request_scope` or `request_key_root` is supplied to `assemble_and_reconcile_campaign_source_requests`, scoped enforcement becomes active.

Require a valid typed scope. Do not silently catch and downgrade an invalid scope.

Validation must prove:

- supported scope version;
- canonical root derived from scope execution ID;
- non-empty scope identities;
- explicit `request_key_root`, when supplied, equals the typed scope root;
- diagnostic `request_key_root`, when supplied, equals the typed scope root;
- every supplied request-key prefix equals the typed scope root.

Use stable blockers:

- `CAMPAIGN_SOURCE_REQUEST_SCOPE_REQUIRED`
- `CAMPAIGN_SOURCE_REQUEST_SCOPE_INVALID`
- `CAMPAIGN_SOURCE_REQUEST_SCOPE_PREFIX_MISMATCH`

The function may either raise a narrow typed `ValueError` before reconciliation or return a deterministic blocked reconciliation object. Use one approach consistently with nearest callers and preserve the public outer `CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH` behavior for set-reconciliation failures.

Legacy unscoped fixture callers remain supported only when no typed scope and no explicit root are supplied.

## 2. Canonical prefix set

Under scoped enforcement, the prefix lookup set must be exactly:

```python
[scope.request_key_root]
```

Do not merge arbitrary caller prefixes into it.

A foreign supplied prefix is a contract error, not an additional discovery source.

For unscoped legacy callers, preserve existing multi-prefix behavior.

## 3. Final row-level root filter

Even with the canonical prefix set, `load_durable_campaign_source_request_ids` must apply `request_key_belongs_to_root(request_key, request_key_root)` to every row added through:

- known request-ID lookup;
- prefix lookup.

When `enforce_request_key_root=True`, no code path may add a foreign-root row to `D`.

This is a final defense, not a replacement for scope/prefix validation.

## 4. Prefix lookup evidence

`load_prefix_lookup_request_ids` must support scoped enforcement or receive only the canonical root.

The returned `prefix_lookup_request_ids` must contain only current-root rows.

Do not silently include and later discard foreign rows.

## 5. Out-of-scope stage IDs

Preserve the existing behavior:

- a stage-reported durable row under another root does not enter `D`;
- it is reported in `out_of_scope_stage_request_ids`;
- category remains `CURRENT_STAGE_REQUEST_OUTSIDE_CAMPAIGN_SCOPE`;
- terminal detail remains bounded and source-payload-free.

Do not relabel a foreign durable row as non-durable.

## 6. Public path unchanged

The public permanent path must continue to:

- construct the typed scope from execution/campaign/run/cycle identities;
- force discovery and front-door prefixes to the canonical root;
- perform the pre-provider collision gate;
- pass the scope and root into pre-holder reconciliation;
- expose exact bounded reconciliation detail.

No new provider call, ordering, request, retry, or budget is allowed.

## 7. Focused proof

Use disposable migrated databases and fixture transports only.

Prove at minimum:

1. `enforce_request_key_root=True` with `[canonical_root, foreign_root]` cannot add foreign rows to `D`.
2. a foreign supplied prefix is rejected in scoped reconciliation.
3. invalid scope version blocks.
4. malformed canonical root blocks.
5. explicit root different from scope root blocks.
6. diagnostic root different from scope root blocks.
7. current-root known IDs plus current-root prefix IDs reconcile normally.
8. stage-reported foreign durable IDs remain `CURRENT_STAGE_REQUEST_OUTSIDE_CAMPAIGN_SCOPE`.
9. unscoped legacy multi-prefix callers retain prior behavior.
10. public permanent composition tests remain green.
11. source-specific temporal tests remain green.
12. authoritative DB identity and failed evidence remain unchanged.

## Money-usefulness contribution

The final ownership boundary becomes self-enforcing: a campaign can only use source requests generated under its own invocation root, even if a caller accidentally supplies extra prefixes or malformed scope evidence.

## What remains locked

No authorization, runtime, `WINDOW_1H+`, retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, wallets, signing, real funds, paid APIs, scoring, ranking, confidence, weighting, embeddings, or vectors.

## Functionality Risks / Setbacks / Efficiency Blockers

- Legacy fixture compatibility: preserve unscoped behavior only when no scoped inputs exist.
- Double classification: keep foreign durable stage IDs out-of-scope, not non-durable.
- Excessive scope: one accounting module plus focused tests and closeout.
- Premature live proof: no authorization until implementation and independent inspection pass.

## Completion sequence

1. focused implementation;
2. disposable proof;
3. closeout;
4. independent inspection;
5. one later fresh authorization preparation lane.
