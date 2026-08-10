# Printer V1 V2-9.8B Post-DTW100 Standard Four-Hour Eligible-Subset Handoff / Planning Repair Closeout

## Verdict

`V2_9_8B_POST_DTW100_STANDARD_FOUR_HOUR_ELIGIBLE_SUBSET_HANDOFF_PLANNING_REPAIR_PASS`

The standard four-hour campaign composition now preserves the exact two owned campaign slots while allowing the explicit `0/1/2` eligible subset required by token-local 1h->4h hard gates. An ineligible peer no longer suppresses an otherwise-valid token's four-hour continuation.

This closeout authorizes no real `WINDOW_4H` collection, operational activation, source call, Scheduler runtime, authorization creation, authoritative DB mutation, 12h/24h work, retrieval, paper decision, BUY/SELL/HOLD, position, trade, audit, PnL, wallet, signing, execution, real funds, paid API, scoring, ranking, confidence, weighted logic, embeddings or vectors.

## Baseline and implementation

- Approved design baseline: `706129d8e76fb7f65f63064a02d3aead23a1afcc`
- RED test commit: `d14e5e557e4a9f69366c41bdd4a45b25a5caea90`
- Production implementation commit: `74e7d45d27d8a03bce305bd76aea004d43274b4d`
- Production subject: `Repair standard four-hour eligible subset composition`

Production changed exactly:

- `src/printer_v1/operator_cli/campaign_ownership.py`
- `src/printer_v1/operator_cli/one_token_4h_runtime.py`
- `src/printer_v1/operator_cli/one_command_15m_factory.py`

The test contract was already committed at the RED boundary:

- `tests/test_v2_9_8b_post_dtw100_standard_four_hour_eligible_subset.py`

No schema migration was added.

## Implemented contract

### Eligible subset

The campaign still requires the exact two owned candidate/slot identities. `eligible_token_slot_ids` now declares which of those slots may receive `WINDOW_4H` ownership:

- zero eligible -> no four-hour successor or long work;
- one eligible -> only that exact slot receives the four-hour successor and owned long work;
- two eligible -> historical all-valid two-token behavior remains compatible;
- duplicate, foreign, drifting, partial or conflicting subset state fails closed.

Ineligible slots receive no fabricated four-hour window and are not advanced to `WINDOW_4H_CONTINUING`.

### Durable eligibility manifest

Each exact successful first-hour `CONTINUATION_CLOSE` carries the versioned `standard_four_hour_eligibility` record under contract:

`STANDARD_4H_ELIGIBILITY_V1`

It binds campaign, campaign run, cycle, token slot, token, pair, eligibility and categorical verdict. Exact replay is allowed; conflicting or partial manifest truth fails closed.

### Policy-derived lifecycle budget

`standard_campaign_lifecycle_budget(tracking_lanes, continuing_mask)` preserves both tokens' already-consumed discovery/15m/1h prefix and adds the 4h suffix only for eligible slots.

| Lane shape / eligible subset | Requests | Scheduler rows |
|---|---:|---:|
| FAST+FAST / none | 92 | 82 |
| FAST+FAST / one FAST | 161 | 146 |
| FAST+FAST / both | 230 | 210 |
| FAST+NORMAL / none | 74 | 64 |
| FAST+NORMAL / FAST only | 143 | 128 |
| FAST+NORMAL / NORMAL only | 113 | 98 |
| FAST+NORMAL / both | 182 | 162 |
| NORMAL+NORMAL / none | 56 | 46 |
| NORMAL+NORMAL / one NORMAL | 95 | 80 |
| NORMAL+NORMAL / both | 134 | 114 |

The historical `standard_two_token_lifecycle_budget(...)` remains a compatibility wrapper for both eligible.

### Atomic planning and ownership

The standard composer persists the eligibility manifest, B1 successor ownership, eligible-token long run steps and exact stage-scoped Central Scheduler projection under one caller-owned transaction. A projection or composition failure rolls back the fresh manifest, windows, token-state changes, long steps, Scheduler jobs and campaign ownership together.

Zero eligible is a valid no-op composition rather than a campaign error.

### Terminal reconciliation

The standard terminal validator now derives expected four-hour cardinality from the durable two-slot eligibility manifest:

- zero eligible + zero four-hour work can complete;
- one eligible requires exactly that slot's terminal four-hour path;
- two eligible preserves the established two-window validation;
- missing/extra windows or long work relative to the manifest fail closed;
- historical no-manifest behavior retains its prior fallback boundary rather than silently legitimizing a partial new standard plan.

## Verification

### RED proof

Disposable PR #152 was closed unmerged. The exact RED head ran 72 directly affected tests. The eight new eligible-subset tests failed only because the approved production subset API and generalized budget owner did not yet exist. Existing directly affected tests stayed green; compile, capability locks and diff hygiene passed.

### Disposable GREEN proof

Disposable PR #153 was closed unmerged. The approved three-file patch ran the same focused suite:

`72 / 72 PASS`

It also proved exact three-production-file scope, compilation, `git diff --check`, and that real 4h/12h/24h collection remained disabled.

### Independent exact-head proof

Disposable PR #154 was closed unmerged. Its runner checked out exact production SHA:

`74e7d45d27d8a03bce305bd76aea004d43274b4d`

Result:

`72 / 72 PASS`

The independent proof additionally asserted:

- `STANDARD_4H_ELIGIBILITY_V1` contract identity;
- every exact subset budget value above;
- `continuation_count` matches each eligible mask;
- subset budget `real_collection_enabled` remains false;
- FAST/NORMAL `WINDOW_4H`, `WINDOW_12H` and `WINDOW_24H` real collection remains false;
- tracked tree remained read-only and clean during proof.

## Money-usefulness contribution

The repair prevents Printer from discarding a valid token's first-four-hour observation merely because its peer independently fails a hard continuation gate. It therefore improves the completeness and honesty of long-horizon memory collection without weakening safety or turning continuation into a score/rank.

It proves no profitability and creates no live market evidence.

## What this lane improves

- exact token-local standard 1h->4h composition;
- honest `0/1/2` continuation cardinality;
- durable expected-subset evidence;
- exact policy-derived resource accounting for partial continuation;
- atomic rollback and replay safety;
- terminal reconciliation for zero-, one- and two-token continuation.

## What remains locked

Real four-hour collection is still deliberately disabled. The public operational command, one-shot wrapper/authorization contract, Git-manifest mode binding, operational duration/resource envelope and factory activation seam remain separate activation-envelope work. `WINDOW_12H`/`WINDOW_24H`, retrieval and every financial capability remain locked.

## Functionality Risks / Setbacks / Efficiency Blockers

- The current public operational surface is still 15m/legacy-proof shaped and must not gain four-hour authority through a hidden proof flag.
- The later authorization envelope must distinguish pre-lifecycle acquisition accounting from post-supply lifecycle ceilings.
- A future operational mode must preserve the durable eligible-subset manifest rather than infer expected cardinality from observed windows.
- GitHub proof does not establish current operator-host DB bytes, process quiescence, leases or sidecars; those require fresh host read-only verification before any later authorization.

## Next permitted task

Repeat the **Standard Four-Hour Operational Rereadiness Audit** from this closeout head.

That rereadiness may determine whether a separate standard-four-hour activation-integration design lane can begin. It must not itself enable real four-hour collection or create an authorization.
