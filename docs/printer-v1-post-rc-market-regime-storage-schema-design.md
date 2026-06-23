# Market Regime Storage Schema Design

This is a pre-Lane-7 Post-RC storage design task.

It is not Lane 7. It is not source adapter implementation. It is not live data collection. It is not a real migration. It does not call external APIs, mutate the persistent DB, create source rows, create token snapshots, create context rows, build memory, run retrieval, create paper decisions, unlock BUY, create paper positions, create paper trade events, or create PnL.

## Current Blocker Summary

Current state:

- `market_regime_label: UNKNOWN` remains a clean-memory blocker.
- `clean_memory_count` remains `0`.
- Clean eligible memory count remains `0`.
- Lane 7 remains blocked.
- Retrieval remains blocked.
- Paper decisions remain blocked.
- BUY remains locked.
- Paper positions remain `0`.
- Paper trade events remain `0`.
- PnL remains unavailable.

The market regime fixture contract is documented and tested. This document defines how future market-regime evidence could be stored and audited without applying a migration yet.

The existing `printer_market_regime_snapshots` table already stores broad market context such as BTC/SOL changes, Fear and Greed, Solana TVL context, market labels, source status, data quality, and raw/normalized payload JSON. A future evidence table would only be justified if the current snapshot table cannot cleanly represent evidence-window linkage, explicit source trace IDs, target status, freshness, and paper-only context.

## Proposed Future Table Shape

Proposed future table name:

- `printer_market_regime_evidence`

This is only a proposed design, not a migration.

| Candidate field | Purpose | Notes |
|---|---|---|
| `id` | Primary key | Future migration detail only. |
| `snapshot_id` | Link market evidence to token snapshot | Required where evidence is attached to an evidence window. |
| `token_id` | Optional token target | Nullable only for broad market context. |
| `pair_id` | Optional pair target | Nullable only for broad market context. |
| `memory_window_id` | Link to audited memory window | Nullable until a window exists. |
| `evidence_window_id` | Link to evidence-window abstraction | Nullable if not used. |
| `market_evidence_role` | Evidence role | Candidate value: `BROAD_MARKET_CONTEXT`; token-specific variants require token/pair linkage. |
| `market_scope_label` | Evidence scope | Candidate values: `BROAD_CRYPTO_MARKET`, `SOLANA_MARKET_CONTEXT`, `SOLANA_MEME_MARKET_CONTEXT`, `TOKEN_PAIR_MARKET_CONTEXT`, `UNKNOWN_MARKET_SCOPE`. |
| `source_name` | Governed source name | Candidate source only; no source assumed. |
| `source_status` | Existing source status | `COMPLETE`, `PARTIAL`, `FAILED`, `STALE`, `CONFLICTING`. |
| `data_quality_label` | Existing data quality | `CLEAN_DATA`, `ACCEPTABLE_PARTIAL_DATA`, `DIRTY_DATA`, `STALE_DATA`, `MISSING_CRITICAL_DATA`, `CONFLICTING_DATA`, `DO_NOT_TRAIN`. |
| `target_status` | Evidence target result | Candidate values: `TARGET_MATCH`, `TARGET_MISMATCH`, `TARGET_UNKNOWN`. |
| `evidence_captured_at` | Evidence capture timestamp | Missing timestamp remains unknown. |
| `freshness_label` | Evidence freshness | Candidate values: `MARKET_EVIDENCE_FRESH`, `MARKET_EVIDENCE_ACCEPTABLE`, `MARKET_EVIDENCE_STALE`, `MARKET_EVIDENCE_UNKNOWN`. |
| `market_regime_label` | Existing-compatible regime label | Prefer existing labels: `RISK_ON`, `RISK_OFF`, `NEUTRAL`, `VOLATILE`, `UNKNOWN`, and existing Fear/Greed labels. |
| `market_trend_label` | Categorical trend | Candidate values: `MARKET_TREND_UP`, `MARKET_TREND_DOWN`, `MARKET_TREND_SIDEWAYS`, `MARKET_TREND_UNKNOWN`. |
| `market_volatility_label` | Categorical volatility | Candidate values: `MARKET_VOLATILITY_HIGH`, `MARKET_VOLATILITY_NORMAL`, `MARKET_VOLATILITY_LOW`, `MARKET_VOLATILITY_UNKNOWN`. |
| `market_liquidity_label` | Categorical broad liquidity | Candidate values: `MARKET_LIQUIDITY_HEALTHY`, `MARKET_LIQUIDITY_THIN`, `MARKET_LIQUIDITY_UNKNOWN`. |
| `solana_market_context_label` | Optional Solana broad context | Nullable; not a chain-heat replacement. |
| `meme_market_context_label` | Optional memecoin broad context | Nullable; not token-level evidence. |
| `source_request_id` | Source Governor request trace | Nullable for audit-only historical rows; required for clean eligibility. |
| `source_response_id` | Source Governor response trace | Required for clean eligibility when source succeeds. |
| `source_failure_id` | Source Governor failure trace | Required when source fails. |
| `paper_only_context` | V1 paper-only guard | Must be true for usable V1 evidence. |
| `created_at` | Local creation timestamp | Not a clean-evidence differentiator by itself. |

No source-specific field should be assumed until a future Source Governor-controlled implementation task proves that a free/public source provides it reliably.

## Required Constraints

Future constraints should preserve these rules:

- `snapshot_id` is required where evidence is attached to an evidence window.
- Broad market context may have nullable `token_id` and `pair_id` only when `market_scope_label` is broad, such as `BROAD_CRYPTO_MARKET`, `SOLANA_MARKET_CONTEXT`, or `SOLANA_MEME_MARKET_CONTEXT`.
- Token-specific or pair-specific market evidence requires `token_id` and `pair_id`.
- `paper_only_context` must be true for V1 memory eligibility.
- Source trace is required for clean eligibility: at minimum `source_request_id` plus either `source_response_id` or `source_failure_id` depending on result.
- Clean eligibility requires successful trace: `source_request_id` and `source_response_id` must be present when `source_status` is `COMPLETE` or acceptable `PARTIAL`.
- Stale evidence cannot be clean.
- Failed evidence cannot be clean.
- Missing evidence remains `UNKNOWN`.
- Target mismatch cannot be clean.
- Missing source trace cannot be clean.
- Broad market context cannot become a direct trade signal.
- Market evidence cannot unlock clean memory by itself.
- No live execution fields are allowed.
- No wallet, private key, signature, signing, or transaction fields are allowed.
- No score, ranking, confidence, weighted, or numeric decision fields are allowed.

## Label Mapping From Storage

Stored market evidence could later support categorical labels only.

Existing-compatible regime labels should remain preferred:

- `RISK_ON`
- `RISK_OFF`
- `NEUTRAL`
- `VOLATILE`
- `UNKNOWN`
- Existing Fear and Greed labels where applicable: `EXTREME_FEAR`, `FEAR`, `GREED`, `EXTREME_GREED`, `CHOPPY`

Documentation-level candidate labels may map as follows:

| Candidate label | Existing-compatible storage result |
|---|---|
| `MARKET_REGIME_RISK_ON` | `RISK_ON` |
| `MARKET_REGIME_RISK_OFF` | `RISK_OFF` |
| `MARKET_REGIME_NEUTRAL` | `NEUTRAL` |
| `MARKET_REGIME_VOLATILE` | `VOLATILE` |
| `MARKET_REGIME_UNKNOWN` | `UNKNOWN` |

Trend candidates:

- `MARKET_TREND_UP`
- `MARKET_TREND_DOWN`
- `MARKET_TREND_SIDEWAYS`
- `MARKET_TREND_UNKNOWN`

Volatility candidates:

- `MARKET_VOLATILITY_HIGH`
- `MARKET_VOLATILITY_NORMAL`
- `MARKET_VOLATILITY_LOW`
- `MARKET_VOLATILITY_UNKNOWN`

There is no market score, ranking, confidence percentage, weighted market system, or numeric decision value.

## Audit Behavior

Future audit should treat market-regime evidence as follows:

| Evidence state | Audit behavior |
|---|---|
| Risk-on market regime | Known broad context only; may satisfy the market-regime portion if fresh, governed, target-matched, and paper-only. |
| Risk-off market regime | Known broad context only; not a direct AVOID/SELL signal. |
| Neutral market regime | Known broad context only; not a direct WAIT/NO_ACTION signal. |
| Volatile market regime | Known broad context with caution visibility; not a direct trade signal. |
| Thin/illiquid market regime | Audit-visible broad liquidity context; cannot override token-level liquidity/exit realism. |
| Missing market evidence | `UNKNOWN`; blocks clean eligibility. |
| Stale market evidence | Audit-only; cannot support clean memory. |
| Failed source market evidence | Audit-only or do-not-use; cannot support clean memory. |
| Target mismatch | Conflicting/audit-only; blocks clean eligibility. |
| Missing Source Governor trace | Audit-only; blocks clean eligibility. |
| Non-paper-context evidence | Invalid for V1 memory. |
| Broad market context used as direct trade signal | V1 violation; must block downstream use. |

Market evidence should explain the environment around a memory. It must not trade, rank, score, or override token-level evidence.

## Source Governor Linkage

Future market evidence must link to governed source traces:

- `source_request_id` links to `printer_source_requests`.
- `source_response_id` links to `printer_source_responses` when collection succeeds.
- `source_failure_id` links to `printer_source_failures` when collection fails.

Market evidence without proper governed source trace must remain audit-only.

The memory engine, retrieval engine, and paper decision engine must not call broad-market sources directly. Any future external collection must be recorded through Source Governor first.

## Central Scheduler Linkage

Future market evidence collection must be:

- Scheduled through Central Scheduler.
- Bounded.
- Operator-approved during manual proof.
- Non-continuous.
- Non-spammy.
- Lower priority than token-level snapshots, safety/liquidity refreshes, and memory-window close work.
- Blocked from runtime expansion without roadmap approval.

The likely scheduler kind remains `MARKET_REGIME_CONTEXT` unless a future approved migration/task adds a more specific kind.

## Clean-Memory Gate Preservation

Market evidence alone cannot make memory clean.

Market evidence only helps resolve:

- `market_regime_label: UNKNOWN`

The following blockers still block clean memory when unresolved:

- `chain_heat_label: SOLANA_UNKNOWN`
- `safety_status_label: SAFETY_UNKNOWN`
- `entry_realism_label: ENTRY_UNKNOWN`
- `exit_realism_label: EXIT_UNKNOWN`
- `flow_direction_label: FLOW_UNKNOWN`
- `flow_pressure_label: FLOW_UNKNOWN`

Dirty, stale, failed, mismatched, non-paper, or audit-only market evidence cannot enter retrieval.

No paper decision, BUY, paper position, paper trade event, or PnL can be unlocked by market evidence alone.

## Fixture-Only Test Plan

Fixture-only tests should prove:

- Proposed required fields are present.
- `snapshot_id` linkage is required for evidence-window clean eligibility.
- Broad market scope allows nullable `token_id` and `pair_id` only when scope is broad.
- Token-specific market evidence requires `token_id` and `pair_id` linkage.
- `paper_only_context` must be true.
- Source trace is required for clean eligibility.
- Stale evidence maps to audit-only.
- Failed evidence maps to audit-only.
- Missing evidence remains `UNKNOWN`.
- Target mismatch blocks clean eligibility.
- Missing source trace blocks clean eligibility.
- Broad market context cannot become a direct trade signal.
- No score, ranking, confidence, or weighted fields are present.
- No wallet, private-key, signature, transaction, or live-execution fields are present.
- Market evidence alone does not unlock clean memory.
- Market evidence alone does not unlock retrieval.
- Market evidence alone does not create paper decisions.
- Market evidence alone does not create positions, trade events, or PnL.

## Non-Goals

This task does not:

- Add a real migration.
- Mutate the DB.
- Add an adapter.
- Call a live API.
- Collect live source data.
- Create source request, response, or failure rows.
- Create token snapshots.
- Create context rows.
- Build memory windows.
- Rebuild memory.
- Run retrieval.
- Create a paper decision.
- Unlock BUY.
- Create paper positions.
- Create paper trade events.
- Create PnL.
- Activate Lane 7.

## Recommended Next Safe Task

Recommended next safe task:

- `Market Regime Migration Proposal Review`

Why:

- This document defines the proposed storage semantics and constraints.
- The next safe step is to compare this design against `printer_market_regime_snapshots` and decide whether a minimal future migration is justified.
- That task should still not apply a migration, call sources, mutate the DB, run retrieval, unlock BUY, or start Lane 7.

Alternative safe next task:

- `Solana Chain Heat Fixture Contract`

Lane 7 remains blocked until clean eligible memory exists.
