# Printer V1 V2-9.8B WINDOW_15M Source-Request Scope Enforcement Independent Inspection

## Verdict

`V2_9_8B_WINDOW_15M_SOURCE_REQUEST_SCOPE_ENFORCEMENT_INDEPENDENT_INSPECTION_PASS`

The invocation-scoped source-request ownership repair and its enforcement follow-up are suitable for one later fresh `WINDOW_15M` authorization-preparation lane.

This inspection is read-only and documentation-only. It created no authorization, application marker, provider request, discovery work, Scheduler work, campaign runtime, lifecycle work, memory, database mutation, retrieval, decision, position, trade, audit, or PnL activity.

## Reviewed baseline

| Item | Value |
| --- | --- |
| Repair branch | `agent/v2-9-8b-window-15m-source-request-scope-enforcement-followup-repair` |
| Repair full HEAD | `b577cc92d73ff92c8c1f3d5c73a6c4fa280870e6` |
| Repair commit | `Enforce canonical source request scope at reconciliation` |
| Prior scope repair | `d9b2deb5ea35ae9035702f90343d3818bf6ac536` |
| Controlling follow-up design | `docs/printer-v1-v2-9-8b-window-15m-source-request-scope-enforcement-followup-design.md` |
| Consumed authorization preserved | `V2_9_8B_WINDOW_15M_AUTH_20260806T115911Z` |

GitHub comparison proves the follow-up is one commit after the controlling design and changes only:

- `src/printer_v1/discovery/permanent_discovery_availability.py`;
- `tests/test_v2_9_8b_window_15m_source_request_scope_enforcement_followup.py`;
- the follow-up repair closeout.

No other production module, schema, launcher, wrapper, authorization owner, provider, Scheduler owner, temporal rule, holder policy, selection rule, or financial/retrieval surface changed.

## Independent code findings

### 1. Invalid scoped evidence fails closed

`assemble_and_reconcile_campaign_source_requests` activates scoped enforcement when a typed scope or explicit/diagnostic request root is present.

It now:

- requires a typed scope;
- validates the supported scope version and canonical root;
- rejects explicit-root disagreement;
- rejects diagnostic-root disagreement;
- rejects request-scope-version disagreement;
- rejects any caller prefix that differs from the canonical root;
- does not catch invalid scope and continue unscoped.

Stable scope blockers are raised before set reconciliation.

### 2. Canonical prefix set is exact

Scoped reconciliation uses exactly:

```python
prefixes = [scope.request_key_root]
```

Foreign caller prefixes are rejected rather than merged.

The legacy multi-prefix behavior remains available only when neither a typed scope nor a root is supplied.

### 3. Durable-set filtering is complete

When root enforcement is active, `load_durable_campaign_source_request_ids` applies `request_key_belongs_to_root` to rows obtained through both:

- known-request-ID lookup;
- prefix lookup.

Foreign-root rows therefore cannot enter the durable set `D` through either path.

`load_prefix_lookup_request_ids` applies the same root filter, keeping the reported prefix-lookup set invocation-local.

### 4. Out-of-scope evidence remains diagnosable

A stage-reported durable request under a foreign root:

- remains outside `D`;
- is recorded in `out_of_scope_stage_request_ids`;
- is classified as `CURRENT_STAGE_REQUEST_OUTSIDE_CAMPAIGN_SCOPE`;
- is not mislabelled as non-durable;
- retains bounded terminal detail.

### 5. Public live composition remains correctly bound

The earlier scope repair remains intact:

- the public operational owner constructs the typed scope from the exact execution, campaign, run, and cycle identities;
- discovery and front-door prefixes are forced to one canonical root;
- the pre-provider collision gate remains before permanent supply provider work;
- the pre-holder reconciliation path uses the typed scope and canonical root;
- the outer compatibility blocker remains `CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH` for set defects.

No new provider, request ordering, source budget, stage reservation, Source Governor, Scheduler, selection, liquidity, temporal, holder, lifecycle, or memory behavior was introduced.

## Proof assessment

The committed closeout records:

- `36 passed` for the new follow-up plus original scope tests;
- `125 passed` for the nearest durable, manifest, temporal, retained-evidence, and permanent-discovery suites;
- Python compilation and `git diff --check` passing;
- unchanged authoritative DB identity;
- no provider or runtime execution.

GitHub exposes no CI status for this commit, so this inspection did not independently rerun the local test suite or recalculate the local authoritative DB hash. The reviewed implementation and committed focused tests support the reported PASS verdict.

## Remaining risks and controls

| Risk | Control |
| --- | --- |
| Reuse of an invocation root | Pre-provider durable collision gate |
| Foreign caller prefix | Fail-closed prefix mismatch |
| Invalid typed scope | Fail-closed scope validation |
| Foreign durable stage request | Explicit out-of-scope classification |
| Historical static-prefix contamination | Invocation-local canonical root and row-level filter |
| Missing current stage evidence | Canonical-root prefix lookup remains active |
| Overbroad repair | One production module changed |
| Premature rerun | No authorization in inspection lane |

No remaining source-request-scope enforcement blocker was found on the public `WINDOW_15M` path.

## Money-usefulness contribution

The campaign can now attribute source evidence only to its own invocation. This protects current request-budget truth and prevents historical or foreign requests from contaminating candidate evidence used for later memory observations.

## What remains locked

- no automatic retry, resume, restart, or successor;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, and `WINDOW_24H`;
- retrieval and dirty-memory use;
- paper decisions and BUY/SELL/HOLD;
- paper positions, trade events, audits, and PnL;
- wallets, signing, private keys, real funds, and live execution;
- paid APIs;
- scoring, ranking, confidence, weighting, embeddings, and vectors.

## Exact next lane

One fresh, one-use `WINDOW_15M` authorization may be prepared in a separate explicit lane, bound to:

- the final inspection branch tip created by this document;
- the then-current authoritative DB identity;
- the complete exact historical non-reusable authorization trust root, including `V2_9_8B_WINDOW_15M_AUTH_20260806T115911Z`.

The authorization-preparation lane must remain non-consuming and stop before wrapper execution.
