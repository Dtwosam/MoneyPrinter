# Paper Quote Evidence Storage Schema Design

This is a pre-Lane-7 Post-RC storage design document.

It is not Lane 7. It is not Jupiter implementation. It is not live quote collection. It is not source adapter work. It is not a migration implementation. It is not a paper decision task.

Implementation status update:

- Migration `023_paper_quote_evidence.sql` now implements isolated paper quote evidence storage.
- Low-level helper `insert_paper_quote_evidence(...)` now inserts caller-provided fixture evidence into caller-provided SQLite DB handles only.
- Tests cover isolated temporary DB migration and helper behavior only.
- There is still no live quote fetching, no Jupiter adapter, no Source Governor adapter wiring, no scheduler/operator command wiring, no audit/retrieval/paper-decision integration, no BUY unlock, no positions, no trade events, and no PnL.
- Lane 7 remains blocked because clean eligible memory still does not exist.

Printer V1 remains Solana-only, Solana memecoin-only, paper-trading only, free/public-source only, no live wallet, no private keys, no real funds, no live execution, no paid API dependency, no scoring, no ranking, no confidence percentages, no weighted decision logic, no dirty-memory retrieval, no BUY unlock, no paper positions, no paper trade events, and no PnL.

## Current State Summary

Current anchors:

- `d54aac9` / `printer-v1-post-rc-paper-quote-evidence-fixture-readiness`
- `9da034c` / `printer-v1-post-rc-jupiter-paper-quote-realism-readiness`
- `594eb42` / `printer-v1-post-rc-missing-context-source-candidate-evaluation`
- `138adff` / `printer-v1-post-rc-fresh-context-validation`
- `0269bcd` / `printer-v1-post-rc-clean-context-blocker-review`
- `5fffa5d` / `printer-v1-post-rc-lane6-longer-window-activation-readiness`

Validated state:

- Lane 6 is complete.
- Fresh context validation is complete.
- Missing source candidates have been evaluated.
- Jupiter paper quote realism readiness has been documented.
- Paper quote fixture readiness has been added.
- Clean memory still does not exist.
- Lane 7 is still blocked.
- Retrieval is still blocked.
- Paper decisions are still blocked.
- Paper positions remain `0`.
- Paper trade events remain `0`.

This storage design exists because future paper quote evidence needs a durable way to be linked to Source Governor records, token snapshots, evidence windows, memory-window audit, and freshness checks.

The design must preserve the current blockers:

- Quote evidence can help only `entry_realism_label` and `exit_realism_label`.
- Quote evidence cannot solve `chain_heat_label`, `market_regime_label`, `safety_status_label`, `flow_direction_label`, or `flow_pressure_label`.
- Quote evidence alone cannot make a memory clean.
- Quote evidence alone cannot unlock retrieval, paper decisions, BUY, paper positions, trade events, or PnL.

Lane 7 remains blocked because clean eligible memory still does not exist.

## Implemented Table Shape

Implemented table name:

- `printer_paper_quote_evidence`

This table is implemented as isolated fixture/evidence storage only. It is not wired to live quote collection, memory rebuilds, retrieval, paper decisions, or scheduler/operator commands.

Candidate future table shape:

```sql
CREATE TABLE printer_paper_quote_evidence (
    id INTEGER PRIMARY KEY,
    token_id INTEGER NOT NULL,
    pair_id INTEGER NOT NULL,
    snapshot_id INTEGER NOT NULL,
    memory_window_id INTEGER,
    evidence_window_id INTEGER,
    quote_direction TEXT NOT NULL,
    quote_purpose TEXT NOT NULL,
    input_mint TEXT NOT NULL,
    output_mint TEXT NOT NULL,
    input_amount_raw TEXT NOT NULL,
    output_amount_raw TEXT,
    route_available INTEGER NOT NULL,
    route_plan_present INTEGER NOT NULL,
    route_count INTEGER,
    slippage_bps INTEGER,
    price_impact_bps INTEGER,
    price_impact_label TEXT,
    quote_captured_at TEXT,
    quote_freshness_label TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_status TEXT NOT NULL,
    data_quality_label TEXT NOT NULL,
    failure_reason TEXT,
    no_route_reason TEXT,
    target_status TEXT NOT NULL,
    paper_only INTEGER NOT NULL,
    source_request_id INTEGER,
    source_response_id INTEGER,
    source_failure_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

Candidate fields and notes:

| Field | Requirement | Design note |
|---|---|---|
| `id` | Required | Internal row id only; not evidence identity by itself |
| `token_id` | Required | Links to `printer_tokens(id)` |
| `pair_id` | Required | Links to `printer_pairs(id)` |
| `snapshot_id` | Required | Links to the token snapshot nearest the quote target |
| `memory_window_id` | Nullable | Links to `printer_memory_windows(id)` when quote targets a memory window |
| `evidence_window_id` | Nullable | Future-compatible alias if evidence windows become a separate concept |
| `quote_direction` | Required | `ENTRY` or `EXIT` only |
| `quote_purpose` | Required | Must be `PAPER_REALISM_ONLY` |
| `input_mint` | Required | Candidate source field; exact source-specific name must be verified later |
| `output_mint` | Required | Candidate source field; exact source-specific name must be verified later |
| `input_amount_raw` | Required | Raw paper quote amount as text to avoid unit/precision mistakes |
| `output_amount_raw` | Nullable | Raw candidate quoted output amount as text; nullable for failure/no-route |
| `route_available` | Required | Integer boolean, `0` or `1` |
| `route_plan_present` | Required | Integer boolean, `0` or `1` |
| `route_count` | Nullable | Candidate route count; source-specific verification needed |
| `slippage_bps` | Nullable | Candidate slippage basis points; not a score |
| `price_impact_bps` | Nullable | Candidate numeric evidence field only; not a decision score |
| `price_impact_label` | Nullable | Categorical label such as acceptable/caution/unknown |
| `quote_captured_at` | Nullable | Required for fresh usable evidence; nullable only for missing/failed cases |
| `quote_freshness_label` | Required | Categorical freshness label |
| `source_name` | Required | Example future value: `jupiter`, if approved later |
| `source_status` | Required | Existing source status vocabulary |
| `data_quality_label` | Required | Existing data quality vocabulary |
| `failure_reason` | Nullable | Required when source failed |
| `no_route_reason` | Nullable | Required when no route is available |
| `target_status` | Required | Targeting status such as `TARGET_MATCH`, `TARGET_MISMATCH`, `TARGET_UNKNOWN` |
| `paper_only` | Required | Integer boolean; must be `1` |
| `source_request_id` | Nullable | Links to `printer_source_requests(id)` where applicable |
| `source_response_id` | Nullable | Links to `printer_source_responses(id)` on successful response |
| `source_failure_id` | Nullable | Links to `printer_source_failures(id)` on failure |
| `created_at` | Required | Storage timestamp, not quote freshness by itself |

Candidate future indexes:

- `idx_paper_quote_evidence_token_pair_snapshot` on `(token_id, pair_id, snapshot_id)`
- `idx_paper_quote_evidence_memory_window` on `(memory_window_id)`
- `idx_paper_quote_evidence_direction` on `(quote_direction)`
- `idx_paper_quote_evidence_source_request` on `(source_request_id)`
- `idx_paper_quote_evidence_source_response` on `(source_response_id)`
- `idx_paper_quote_evidence_source_failure` on `(source_failure_id)`

Do not add these indexes until a migration is separately reviewed and approved.

## Required Constraints

Future migration constraints should enforce:

- `quote_direction` must be `ENTRY` or `EXIT`.
- `quote_purpose` must be `PAPER_REALISM_ONLY`.
- `paper_only` must be true.
- `token_id`, `pair_id`, and `snapshot_id` linkage is required.
- `source_name`, `source_status`, and `data_quality_label` are required.
- Source governance linkage is required where applicable.
- A successful source quote should have `source_request_id` and `source_response_id`.
- A failed quote should have `source_request_id`, `source_failure_id`, and `failure_reason`.
- Stale quote cannot support clean entry/exit realism.
- Failed quote cannot support clean entry/exit realism.
- No-route quote cannot be route-available.
- Target mismatch cannot support clean entry/exit realism.
- Non-paper-only quote is invalid.
- No live execution fields are allowed.
- No wallet fields are allowed.
- No private-key fields are allowed.
- No transaction signature fields are allowed.
- No transaction build/send fields are allowed.
- No score, ranking, confidence, or weighted decision fields are allowed.

Candidate check constraints, for future migration review only:

- `CHECK (quote_direction IN ('ENTRY', 'EXIT'))`
- `CHECK (quote_purpose = 'PAPER_REALISM_ONLY')`
- `CHECK (paper_only = 1)`
- `CHECK (route_available IN (0, 1))`
- `CHECK (route_plan_present IN (0, 1))`
- `CHECK (route_available = 0 OR route_plan_present = 1)`
- `CHECK (source_status IN ('COMPLETE', 'PARTIAL', 'FAILED', 'STALE', 'CONFLICTING'))`
- `CHECK (data_quality_label IN ('CLEAN_DATA', 'ACCEPTABLE_PARTIAL_DATA', 'DIRTY_DATA', 'STALE_DATA', 'MISSING_CRITICAL_DATA', 'CONFLICTING_DATA', 'DO_NOT_TRAIN'))`

Exact constraint syntax should be reviewed in a future migration proposal.

## Label Mapping From Storage

Stored quote evidence could later support categorical labels only.

ENTRY:

| Stored evidence state | Candidate label |
|---|---|
| `quote_direction='ENTRY'`, `paper_only=1`, target match, fresh, source clean, route available, route plan present | `ENTRY_ROUTE_AVAILABLE` |
| `quote_direction='ENTRY'`, target match, fresh enough, no route or no route plan | `ENTRY_ROUTE_UNAVAILABLE` |
| `quote_direction='ENTRY'`, target match, fresh route exists, but price impact/slippage/source caveat needs caution | `ENTRY_REALISM_CAUTION` |
| Missing, stale, failed, mismatched, non-paper-only, or ungoverned entry evidence | `ENTRY_REALISM_UNKNOWN` |

EXIT:

| Stored evidence state | Candidate label |
|---|---|
| `quote_direction='EXIT'`, `paper_only=1`, target match, fresh, source clean, route available, route plan present | `EXIT_ROUTE_AVAILABLE` |
| `quote_direction='EXIT'`, target match, fresh enough, no route or no route plan | `EXIT_ROUTE_UNAVAILABLE` |
| `quote_direction='EXIT'`, target match, fresh route exists, but price impact/slippage/source caveat needs caution | `EXIT_REALISM_CAUTION` |
| Missing, stale, failed, mismatched, non-paper-only, or ungoverned exit evidence | `EXIT_REALISM_UNKNOWN` |

This mapping must not introduce:

- numeric scores
- ranking
- confidence percentages
- weighted logic
- BUY or SELL signals

## Audit Behavior

Future audit should treat stored quote evidence as follows:

| Evidence state | Audit behavior |
|---|---|
| Fresh route available | Can support entry/exit realism label only; cannot make memory clean by itself |
| No route | Record no-route reason; map to unavailable; keep decision/position gates blocked unless clean-memory rules later allow action |
| Stale quote | Audit-only; cannot support clean entry/exit realism |
| Failed quote | Audit-only; source failure remains visible |
| Missing quote | Unknown; does not create dirty fake data, but blocks known entry/exit realism |
| Target mismatch | Dirty/audit-only; cannot support clean eligibility |
| Non-paper-only quote | Invalid for V1; must be blocked |
| Missing source governance linkage | Audit-only; cannot support clean eligibility |

Future audit reports should distinguish:

- `QUOTE_FRESH`
- `QUOTE_STALE`
- `QUOTE_MISSING`
- `QUOTE_FAILED`
- `QUOTE_TARGET_MISMATCH`
- `QUOTE_NOT_PAPER_ONLY`
- `QUOTE_SOURCE_GOVERNANCE_MISSING`

These are proposed audit labels only, not runtime labels added by this task.

## Source Governor Linkage

Future paper quote evidence must link to governed source evidence.

Required linkage:

- `source_request_id` for the governed request.
- `source_response_id` for successful or partial source responses.
- `source_failure_id` for failed source attempts.

Rules:

- Quote evidence without a governed source request trace remains audit-only.
- Quote evidence with a successful route but no `source_response_id` remains audit-only.
- Failed quote evidence must preserve `source_failure_id` and `failure_reason`.
- No source request may be created by the memory engine directly.
- No source request may be created by the paper decision engine directly.
- No quote source may bypass Source Governor.
- Source failures must remain visible and must not be rewritten into clean quote evidence.

## Central Scheduler Linkage

Future paper quote collection must be scheduled, bounded, and operator-approved during manual proof.

Rules:

- Collection must run through Central Scheduler.
- Manual proof must require operator approval.
- Jobs must be bounded.
- No continuous quote loop.
- No source spam.
- No runtime expansion without roadmap approval.
- Token snapshots and memory-window close snapshots remain higher priority.
- Quote collection must not directly unlock clean memory, retrieval, paper decisions, BUY, paper positions, trade events, or PnL.

This document does not add scheduler jobs or runtime behavior.

## Clean-Memory Gate Preservation

Quote evidence alone cannot make memory clean.

Quote evidence only helps entry/exit realism.

Clean memory still requires:

- completed evidence window
- complete snapshot coverage
- clean source quality
- known and acceptable safety context
- known and acceptable market context
- known and acceptable Solana chain context
- known and acceptable flow context
- known and acceptable chart/volatility context
- known and acceptable entry/exit realism where required

Safety, market, chain, and flow blockers still block clean memory.

Dirty or audit-only quote evidence cannot enter retrieval.

No paper decision, BUY, paper position, paper trade event, or PnL can come from quote evidence alone.

## Fixture-Only Test Plan

Fixture-only tests should prove:

- Proposed required fields are present in fixture contract.
- `paper_only` must be true.
- `quote_purpose` must be `PAPER_REALISM_ONLY`.
- `ENTRY` and `EXIT` are the only accepted directions.
- Stale quote maps to audit-only.
- Failed quote maps to audit-only.
- No-route maps to unavailable, not available.
- Target mismatch blocks clean eligibility.
- Missing source governance blocks clean eligibility.
- No live execution, wallet, private-key, signature, or transaction execution fields are present.
- Quote evidence alone does not unlock clean memory.
- Quote evidence alone does not unlock retrieval.
- Quote evidence alone does not create paper decisions.
- Quote evidence alone does not create positions.
- Quote evidence alone does not create trade events.
- Quote evidence alone does not create PnL.

Fixture tests must not:

- Call Jupiter.
- Fetch live data.
- Require environment variables.
- Require API keys.
- Mutate persistent DB.
- Apply migrations.
- Add source adapters.

## Non-Goals

This implemented storage/helper path still does not:

- Implement a Jupiter adapter.
- Call an API.
- Fetch live data.
- Create quote rows in the persistent operator DB.
- Rebuild memory.
- Run retrieval.
- Create paper decisions.
- Create BUY.
- Create positions.
- Create PnL.
- Activate Lane 7.

## Recommended Next Safe Task

Recommended next safe task:

- Flow direction/pressure fixture review from existing governed DexScreener/source payloads, or a quote evidence audit-readiness fixture task that remains isolated and does not call Jupiter.

The quote evidence migration/helper path now exists, but it only reduces the `ENTRY_UNKNOWN` and `EXIT_UNKNOWN` storage blocker. It does not solve safety, market, chain, flow, or clean-memory eligibility by itself.

Alternative safe tasks:

- Solana RPC/token safety readiness plan.
- GoPlus-style token safety source readiness plan.

Do not recommend Lane 7 until clean memory exists.
