# Flow Evidence Fixture Contract

This is a pre-Lane-7 Post-RC fixture contract.

It is not Lane 7. It is not source adapter implementation. It is not live data collection. It is not a migration. It does not call external APIs, mutate the persistent DB, create source rows, create token snapshots, create context rows, build memory, run retrieval, create paper decisions, unlock BUY, create paper positions, create paper trade events, or create PnL.

## Current Blocker Summary

Current state:

- `flow_direction_label: FLOW_UNKNOWN` remains a clean-memory blocker.
- `flow_pressure_label: PRESSURE_UNKNOWN` remains a clean-memory blocker.
- `clean_memory_count` remains `0`.
- Clean eligible memory count remains `0`.
- Lane 7 remains blocked.
- Retrieval remains blocked.
- Paper decisions remain blocked.
- BUY remains locked.
- Paper positions remain `0`.
- Paper trade events remain `0`.
- PnL remains unavailable.

The current implementation can derive some activity from stored transaction and volume totals, but full flow direction and pressure require side-aware evidence such as buy/sell transaction counts and buy/sell volume. This contract defines fixture-only evidence states for that future evidence without implementing any source adapter or live collection.

## Flow Evidence Contract

These are candidate fields for future flow evidence. They are not a migration and are not runtime wiring. No single future source is assumed to provide all fields.

| Candidate field | Purpose | Notes |
|---|---|---|
| `token_id` | Link flow evidence to tracked token | Required for target linkage. |
| `pair_id` | Link flow evidence to tracked pair | Required for pair-scoped flow. |
| `snapshot_id` | Link flow evidence to token snapshot | Required for evidence-window clean eligibility. |
| `memory_window_id` | Link to memory window | Nullable until a window exists. |
| `evidence_window_id` | Link to evidence-window abstraction | Nullable if not used. |
| `flow_evidence_role` | Categorize evidence | Candidate value: `TOKEN_PAIR_FLOW_CONTEXT`. |
| `source_name` | Governed source name | Candidate source only; must be Source Governor routed later. |
| `source_status` | Source result status | Existing labels: `COMPLETE`, `PARTIAL`, `FAILED`, `STALE`, `CONFLICTING`. |
| `data_quality_label` | Normalized data quality | Existing labels: `CLEAN_DATA`, `ACCEPTABLE_PARTIAL_DATA`, `DIRTY_DATA`, `STALE_DATA`, `MISSING_CRITICAL_DATA`, `CONFLICTING_DATA`, `DO_NOT_TRAIN`. |
| `target_status` | Whether evidence targets intended token/pair/snapshot/window | Candidate values: `TARGET_MATCH`, `TARGET_MISMATCH`, `TARGET_UNKNOWN`. |
| `evidence_captured_at` | Evidence capture timestamp | Missing timestamp remains unknown. |
| `freshness_label` | Evidence freshness | Candidate values: `FLOW_EVIDENCE_FRESH`, `FLOW_EVIDENCE_ACCEPTABLE`, `FLOW_EVIDENCE_STALE`, `FLOW_EVIDENCE_UNKNOWN`. |
| `buy_tx_count` | Side-aware buy count | Nullable if source does not provide side split. |
| `sell_tx_count` | Side-aware sell count | Nullable if source does not provide side split. |
| `buy_volume_usd` | Side-aware buy volume | Nullable if source does not provide side split. |
| `sell_volume_usd` | Side-aware sell volume | Nullable if source does not provide side split. |
| `net_flow_direction_label` | Normalized flow direction | Existing-compatible labels should map to `FLOW_ACCUMULATION`, `FLOW_DISTRIBUTION`, `FLOW_CHOPPY`, or `FLOW_UNKNOWN`. |
| `flow_pressure_label` | Normalized pressure | Existing-compatible labels should map to `PRESSURE_STRONG_INFLOW`, `PRESSURE_MODERATE_INFLOW`, `PRESSURE_BALANCED`, `PRESSURE_MODERATE_OUTFLOW`, `PRESSURE_STRONG_OUTFLOW`, or `PRESSURE_UNKNOWN`. |
| `flow_activity_label` | Activity / thinness context | Existing-compatible activity can map to `VOLUME_*` and `TX_ACTIVITY_*` labels. |
| `flow_window_label` | Time bucket represented by the evidence | Candidate values: `FLOW_WINDOW_5M`, `FLOW_WINDOW_15M`, `FLOW_WINDOW_1H`, `FLOW_WINDOW_4H`, `FLOW_WINDOW_24H`. |
| `source_request_id` | Source Governor request trace | Required for future clean eligibility. |
| `source_response_id` | Source Governor response trace | Required when source succeeds. |
| `source_failure_id` | Source Governor failure trace | Required when source fails. |
| `paper_only_context` | Explicitly marks evidence as paper-only context | Must be true. |
| `created_at` | Local record timestamp | Not a meaningful clean-evidence differentiator by itself. |

Existing runtime-compatible labels should be preferred:

- Direction: `FLOW_ACCUMULATION`, `FLOW_DISTRIBUTION`, `FLOW_ROTATION`, `FLOW_EXHAUSTION`, `FLOW_CHOPPY`, `FLOW_WASH_LIKE`, `FLOW_UNKNOWN`
- Pressure: `PRESSURE_STRONG_INFLOW`, `PRESSURE_MODERATE_INFLOW`, `PRESSURE_BALANCED`, `PRESSURE_MODERATE_OUTFLOW`, `PRESSURE_STRONG_OUTFLOW`, `PRESSURE_UNKNOWN`
- Quality: `TRADING_FLOW_CONTEXT_CLEAN`, `TRADING_FLOW_CONTEXT_PARTIAL`, `TRADING_FLOW_CONTEXT_STALE`, `TRADING_FLOW_CONTEXT_CONFLICTING`, `TRADING_FLOW_CONTEXT_UNKNOWN`, `TRADING_FLOW_CONTEXT_DO_NOT_USE_FOR_MEMORY`
- Gate: `FLOW_CONTEXT_ACCEPTABLE`, `FLOW_CONTEXT_CAUTION`, `FLOW_CONTEXT_AUDIT_ONLY`, `FLOW_CONTEXT_DO_NOT_TRAIN`

No score, ranking, confidence percentage, weighted flow system, or BUY signal is part of this contract.

## Fixture States

| Fixture state | Expected direction | Expected pressure | Expected gate |
|---|---|---|---|
| Known buy-dominant flow | `FLOW_ACCUMULATION` | `PRESSURE_STRONG_INFLOW` or `PRESSURE_MODERATE_INFLOW` | May satisfy only the flow portion when clean and source-governed. |
| Known sell-dominant flow | `FLOW_DISTRIBUTION` | `PRESSURE_STRONG_OUTFLOW` or `PRESSURE_MODERATE_OUTFLOW` | May satisfy only the flow portion when clean and source-governed. |
| Balanced/neutral flow | `FLOW_CHOPPY` or balanced equivalent | `PRESSURE_BALANCED` | Known flow context, not a trade signal. |
| Low-activity flow | `FLOW_EXHAUSTION` or cautionary flow label | Often `PRESSURE_BALANCED` or weak context | Known but cautionary; does not unlock clean memory alone. |
| Missing flow evidence | `FLOW_UNKNOWN` | `PRESSURE_UNKNOWN` | Blocks clean eligibility. |
| Stale flow evidence | Existing labels may remain visible for audit | Existing labels may remain visible for audit | Audit-only. |
| Failed source flow evidence | `FLOW_UNKNOWN` | `PRESSURE_UNKNOWN` | Audit-only. |
| Target mismatch | `FLOW_UNKNOWN` or previous label only for audit | `PRESSURE_UNKNOWN` or previous label only for audit | Blocks clean eligibility. |
| Missing Source Governor trace | `FLOW_UNKNOWN` or previous label only for audit | `PRESSURE_UNKNOWN` or previous label only for audit | Blocks clean eligibility. |
| Non-paper-context evidence | Do-not-train flow context | Do-not-train flow context | Invalid for V1 memory. |

## Label Mapping

Fixture labels are categorical:

- Buy-dominant flow maps to `FLOW_ACCUMULATION` and inflow pressure when buy counts and/or buy volume clearly dominate.
- Sell-dominant flow maps to `FLOW_DISTRIBUTION` and outflow pressure when sell counts and/or sell volume clearly dominate.
- Balanced flow maps to `FLOW_CHOPPY` or a balanced equivalent and `PRESSURE_BALANCED`.
- Low-activity flow maps to cautionary activity such as weak/dead volume or weak/dead transactions and must not be treated as broad market proof.
- Missing, stale, failed, mismatched, untraceable, or non-paper-context evidence maps to unknown, audit-only, or do-not-train flow context.

There is no numeric flow score, no ranking, no confidence percentage, and no weighted flow decision system.

## Blocking Rules

- Missing flow evidence remains `FLOW_UNKNOWN` / `PRESSURE_UNKNOWN`.
- Stale flow evidence remains audit-only.
- Failed source evidence remains audit-only.
- Target mismatch blocks clean eligibility.
- Missing source trace blocks clean eligibility.
- Non-paper-context evidence is invalid.
- Low-activity flow may be known but cautionary.
- Flow evidence alone cannot make memory clean.
- Side-aware flow cannot override safety, entry/exit realism, market regime, chain heat, snapshot coverage, or source quality.

## Source Governor Requirements

Future flow evidence must:

- Have a source request trace.
- Have a source response or source failure trace.
- Preserve failed, stale, missing, malformed, and partial evidence honestly.
- Link to token, pair, snapshot, and window where applicable.
- Block clean eligibility when source trace is missing.
- Never be created directly by the memory engine.
- Never be created directly by the paper decision engine.
- Never be fetched through a private source loop.

## Central Scheduler Requirements

Future flow evidence collection must:

- Be scheduled.
- Be bounded.
- Be operator-approved during manual proof.
- Avoid continuous loops.
- Avoid source spam.
- Avoid runtime expansion before roadmap approval.
- Respect token-level snapshot priority over broad context engines.
- Never directly unlock paper decisions, BUY, positions, trade events, or PnL.

## Clean-Memory Gate Preservation

Flow evidence alone cannot make memory clean.

Flow evidence only helps resolve:

- `flow_direction_label: FLOW_UNKNOWN`
- `flow_pressure_label: PRESSURE_UNKNOWN`

These blockers can still prevent clean memory:

- `SAFETY_UNKNOWN`
- `ENTRY_UNKNOWN`
- `EXIT_UNKNOWN`
- `UNKNOWN` market regime
- `SOLANA_UNKNOWN` chain heat
- stale source evidence
- failed source evidence
- target mismatch
- incomplete memory-window evidence

Dirty, stale, failed, mismatched, audit-only, or do-not-train flow evidence cannot enter retrieval. Flow evidence alone cannot create paper decisions, BUY, paper positions, paper trade events, or PnL.

## Fixture-Only Test Plan

Fixture-only tests should prove:

- Buy-dominant fixture maps to buy-dominant direction label.
- Sell-dominant fixture maps to sell-dominant direction label.
- Balanced fixture maps to balanced direction label.
- Low-activity fixture maps to caution/low-pressure style label and does not unlock clean memory alone.
- Missing fixture remains `FLOW_UNKNOWN`.
- Stale fixture remains audit-only.
- Failed source fixture remains audit-only.
- Target mismatch blocks clean eligibility.
- Missing source trace blocks clean eligibility.
- Non-paper-context evidence is invalid.
- No score, ranking, confidence, or weighted fields are present.
- No wallet, private-key, signature, signing, transaction, or live-execution fields are present.
- Flow evidence alone does not unlock clean memory.
- Flow evidence alone does not unlock retrieval.
- Flow evidence alone does not create paper decisions.
- Flow evidence alone does not create positions, trade events, or PnL.

## Non-Goals

This task does not:

- Add an adapter.
- Call a live API.
- Collect live source data.
- Mutate the DB.
- Add a migration.
- Build or rebuild memory.
- Run retrieval.
- Create a paper decision.
- Unlock BUY.
- Create positions.
- Create trade events.
- Create PnL.
- Activate Lane 7.

## Recommended Next Safe Task

Recommended next safe task:

- `Flow Evidence Storage Schema Design`

Why:

- Flow direction and pressure now have fixture semantics.
- The next safe step is to compare those semantics against `printer_trading_flow_snapshots` and decide whether existing storage can preserve side-aware buy/sell counts, buy/sell volume, source trace, target status, freshness, and paper-only context.
- No source adapter, live fetch, DB mutation, retrieval, paper decision, BUY, position, trade event, or PnL is needed for that task.

Lane 7 remains blocked until clean eligible memory exists.
