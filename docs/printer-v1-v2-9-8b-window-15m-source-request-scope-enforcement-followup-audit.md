# Printer V1 V2-9.8B WINDOW_15M Source-Request Scope Enforcement Follow-up Audit

## Verdict

`V2_9_8B_WINDOW_15M_SOURCE_REQUEST_SCOPE_ENFORCEMENT_FOLLOWUP_AUDIT_COMPLETE`

Primary classification:

`SCOPED_DURABLE_LOOKUP_ENFORCEMENT_DEFECT`

Secondary classification:

`RECONCILIATION_SCOPE_VALIDATION_DEFECT`

This audit is documentation-only. No production code, tests, authorization, provider, campaign, Scheduler, lifecycle, memory, or database work was executed or changed.

## Baseline

- repair branch: `agent/v2-9-8b-window-15m-source-request-scope-repair`
- repair commit: `d9b2deb5ea35ae9035702f90343d3818bf6ac536`
- controlling design: `docs/printer-v1-v2-9-8b-window-15m-source-request-scope-repair-design.md`
- controlling incident: `V2_9_8B_WINDOW_15M_AUTH_20260806T115911Z`
- failed execution: `20260806T120233Z-5eb0d3b5f0eb`

The main repair correctly adds invocation-local roots, permanent-mode prefix gates, a pre-provider collision check, exact reconciliation categories, and bounded terminal detail. The live public path constructs one root from the fixed-format execution ID and writes it into all three diagnostic prefix fields.

## Confirmed main repair behavior

The reviewed code confirms:

1. `CampaignSourceRequestScope` exists with the approved six fields.
2. canonical root is `v2-9-8b-window15m-<execution_id>`.
3. `run_operational` constructs the scope from execution/campaign/run/cycle identities.
4. permanent `build_graduated_supply` requires and validates the typed scope before supply provider work.
5. discovery and front-door prefixes are forced to the typed root.
6. a pre-existing durable row under that root blocks before supply provider work.
7. current public pre-holder reconciliation passes the typed root and scope.
8. historical static `v2-9-7e-44` rows are excluded on the tested canonical path.
9. terminal reconciliation detail is categorical and bounded.

The unrelated legacy `SimpleNamespace` fixture failures do not prove a live runtime defect. The live path uses `SourceSpecificCandidateAdmission`; the prior live attempt already progressed past temporal admission into pre-holder reconciliation.

## Defect 1 — prefix lookup does not fully enforce the root

`load_durable_campaign_source_request_ids(..., enforce_request_key_root=True)` filters `known_request_ids` by `request_key_root`, but its subsequent prefix loop adds every row matched by every caller-supplied prefix without checking that the row belongs to the canonical root.

Therefore this call can violate its documented invariant:

```python
load_durable_campaign_source_request_ids(
    connection,
    request_key_prefixes=[canonical_root, foreign_root],
    request_key_root=canonical_root,
    enforce_request_key_root=True,
)
```

Rows under `foreign_root` can still enter `D` through the prefix loop.

The current public composition supplies only the canonical root, so the repaired live path is not presently reproducing the historical `v2-9-7e-44` contamination. However, the canonical accounting owner does not actually guarantee its advertised root-enforcement contract. A future diagnostic drift or direct caller can reintroduce cross-invocation contamination.

Required classification:

`SCOPED_DURABLE_LOOKUP_ENFORCEMENT_DEFECT`

## Defect 2 — invalid typed scope is silently downgraded

`assemble_and_reconcile_campaign_source_requests` currently attempts `_coerce_campaign_source_request_scope` and catches `ValueError` by setting `scope_obj = None`.

It can then continue using a separately supplied `request_key_root` or diagnostic root without validating:

- scope version;
- canonical root derivation;
- scope/root equality;
- invocation identity equality.

This does not satisfy the approved design statement that the reconciliation owner owns typed scope validation and fails closed on invalid or contradictory scope evidence.

The public live path validates earlier, so this is not evidence that the last live attempt would still fail. It is a missing defense-in-depth and owner-contract guarantee at the exact reconciliation boundary.

Required classification:

`RECONCILIATION_SCOPE_VALIDATION_DEFECT`

## Why this blocks another authorization

Printer has already consumed two fresh authorizations after reaching progressively later defects. The next authorization should not depend only on the current caller constructing perfect inputs when the canonical reconciliation owner claims to enforce the scope itself.

The minimum safe follow-up is narrow:

- validate typed scope inside reconciliation when a scope/root is present;
- reject scope/root contradiction;
- when root enforcement is enabled, allow only the canonical root for prefix lookup;
- filter every prefix-derived durable row by `request_key_belongs_to_root` as a final defense;
- add exact disposable tests for foreign-prefix contamination and invalid-scope downgrade.

This does not require provider, budget, selection, Scheduler, temporal, holder, lifecycle, schema, authorization, or database changes.

## Money-usefulness contribution

Closing this gap ensures a memory candidate can never inherit durable source ownership from another invocation merely because a caller supplied an extra prefix or malformed scope. Source evidence remains attributable to the exact campaign that paid for and observed it.

## What remains locked

- no authorization or campaign run;
- no provider contact;
- no `WINDOW_1H+` activation;
- no retrieval;
- no paper decisions or BUY/SELL/HOLD;
- no positions, trades, audits, or PnL;
- no wallet, signing, real funds, paid APIs, scoring, ranking, weighting, confidence, embeddings, or vectors.

## Proof required before completion

A focused repair must prove:

1. foreign prefixes cannot add rows to `D` when root enforcement is active;
2. invalid typed scope blocks reconciliation;
3. root/scope contradiction blocks;
4. canonical current-root `D = S = M` still passes;
5. stage-reported foreign-root rows retain their explicit out-of-scope category;
6. public permanent composition remains unchanged;
7. authoritative DB and failed evidence remain unchanged.

## Functionality Risks / Setbacks / Efficiency Blockers

- Risk: over-tightening legacy fixture callers. Control: enforce only when typed scope or explicit root enforcement is active.
- Risk: hiding current-stage foreign IDs. Control: continue classifying them as `CURRENT_STAGE_REQUEST_OUTSIDE_CAMPAIGN_SCOPE`.
- Risk: broad regression work. Control: focused reconciliation and public-composition tests only.
- Risk: another premature live run. Control: no authorization until focused repair and independent inspection pass.

## Exact next lane

`V2-9.8B WINDOW_15M source-request scope enforcement follow-up design and repair`

Stop. Do not create another authorization from `d9b2deb5ea35ae9035702f90343d3818bf6ac536`.
