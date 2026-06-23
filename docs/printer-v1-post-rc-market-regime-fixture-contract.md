# Market Regime Fixture Contract

This is a pre-Lane-7 Post-RC fixture contract.

It is not Lane 7. It is not source adapter implementation. It is not live data collection. It is not a migration. It does not call external APIs, mutate the persistent DB, create source rows, create token snapshots, create context rows, build memory, run retrieval, create paper decisions, unlock BUY, create paper positions, create paper trade events, or create PnL.

## Current Blocker Summary

Current validated state:

- Clean memory count remains `0`.
- Clean eligible memory count remains `0`.
- Retrieval remains blocked.
- Paper decisions remain blocked.
- BUY remains locked.
- Paper positions remain `0`.
- Paper trade events remain `0`.
- PnL remains unavailable.
- Lane 7 remains blocked.

The current market blocker is:

- `market_regime_label: UNKNOWN`

Market regime is required memory context, but it is broad context only. It cannot become a direct trade signal, cannot override token-level safety, liquidity, flow, or quote realism, and cannot make memory clean by itself.

The existing runtime-compatible market labels are:

- `EXTREME_FEAR`
- `FEAR`
- `NEUTRAL`
- `GREED`
- `EXTREME_GREED`
- `RISK_ON`
- `RISK_OFF`
- `CHOPPY`
- `VOLATILE`
- `UNKNOWN`

This contract defines fixture-only evidence states for future governed market-regime evidence without adding a source adapter or live collection path.

## Market Regime Evidence Contract

These are candidate fields for future market-regime evidence. They are not a migration and are not runtime wiring. No single future source is assumed to provide all fields.

| Candidate field | Purpose | Notes |
|---|---|---|
| `snapshot_id` | Link broad market context to the token snapshot being reviewed | Required where the evidence supports a specific window snapshot. |
| `token_id` | Optional token target | Nullable because market regime may be broad market context. |
| `pair_id` | Optional pair target | Nullable because market regime may be broad market context. |
| `memory_window_id` | Link to the memory window being audited | Nullable until a window exists. |
| `evidence_window_id` | Link to evidence-window abstraction | Nullable if not used. |
| `market_evidence_role` | Categorize evidence | Candidate value: `BROAD_MARKET_CONTEXT`. |
| `source_name` | Governed source name | Candidate source only; must be Source Governor routed later. |
| `source_status` | Source result status | Existing labels: `COMPLETE`, `PARTIAL`, `FAILED`, `STALE`, `CONFLICTING`. |
| `data_quality_label` | Normalized data quality | Existing labels: `CLEAN_DATA`, `ACCEPTABLE_PARTIAL_DATA`, `DIRTY_DATA`, `STALE_DATA`, `MISSING_CRITICAL_DATA`, `CONFLICTING_DATA`, `DO_NOT_TRAIN`. |
| `target_status` | Whether evidence targets the intended snapshot/window/context | Candidate values: `TARGET_MATCH`, `TARGET_MISMATCH`, `TARGET_UNKNOWN`. |
| `evidence_captured_at` | Evidence capture timestamp | Missing timestamp remains unknown. |
| `freshness_label` | Evidence freshness | Candidate values: `MARKET_EVIDENCE_FRESH`, `MARKET_EVIDENCE_ACCEPTABLE`, `MARKET_EVIDENCE_STALE`, `MARKET_EVIDENCE_UNKNOWN`. |
| `market_scope_label` | Scope of the broad context | Candidate values: `BROAD_CRYPTO_MARKET`, `SOLANA_MARKET_CONTEXT`, `SOLANA_MEME_MARKET_CONTEXT`, `UNKNOWN_MARKET_SCOPE`. |
| `market_regime_label` | Existing-compatible market regime label | Prefer existing labels such as `RISK_ON`, `RISK_OFF`, `NEUTRAL`, `VOLATILE`, `UNKNOWN`. |
| `market_trend_label` | Categorical trend evidence | Candidate values: `MARKET_TREND_UP`, `MARKET_TREND_DOWN`, `MARKET_TREND_SIDEWAYS`, `MARKET_TREND_UNKNOWN`. |
| `market_volatility_label` | Categorical volatility evidence | Candidate values: `MARKET_VOLATILITY_HIGH`, `MARKET_VOLATILITY_NORMAL`, `MARKET_VOLATILITY_LOW`, `MARKET_VOLATILITY_UNKNOWN`. |
| `market_liquidity_label` | Categorical broad liquidity evidence | Candidate values: `MARKET_LIQUIDITY_HEALTHY`, `MARKET_LIQUIDITY_THIN`, `MARKET_LIQUIDITY_UNKNOWN`. |
| `solana_market_context_label` | Optional Solana broad market context | Nullable; not a substitute for chain heat. |
| `meme_market_context_label` | Optional memecoin broad market context | Nullable; not a token-level signal. |
| `source_request_id` | Source Governor request trace | Required for future clean eligibility. |
| `source_response_id` | Source Governor response trace | Required when source succeeds. |
| `source_failure_id` | Source Governor failure trace | Required when source fails. |
| `paper_only_context` | Explicitly marks evidence as paper-only context | Must be true. |
| `created_at` | Local record timestamp | Not a meaningful clean-evidence differentiator by itself. |

Existing runtime-compatible quality labels should be preserved:

- `MARKET_CONTEXT_CLEAN`
- `MARKET_CONTEXT_PARTIAL`
- `MARKET_CONTEXT_STALE`
- `MARKET_CONTEXT_CONFLICTING`
- `MARKET_CONTEXT_UNKNOWN`
- `MARKET_CONTEXT_DO_NOT_USE_FOR_MEMORY`

No market score, ranking, confidence percentage, weighted regime system, numeric decision score, or BUY signal is part of this contract.

## Fixture States

| Fixture state | Expected regime result | Expected quality result | Clean-memory effect |
|---|---|---|---|
| Known risk-on | `RISK_ON` | `MARKET_CONTEXT_CLEAN` when fresh, governed, and target-matched | May satisfy only the market-regime portion. |
| Known risk-off | `RISK_OFF` | `MARKET_CONTEXT_CLEAN` when fresh, governed, and target-matched | Context only; never a direct AVOID/BUY signal. |
| Neutral | `NEUTRAL` or existing neutral-compatible label | `MARKET_CONTEXT_CLEAN` when fresh and governed | Known broad context, not a trade signal. |
| Volatile | `VOLATILE` | `MARKET_CONTEXT_CLEAN` or conservative clean-with-caution if later approved | Known broad context; does not block by itself when evidence is clean. |
| Thin/illiquid broad market | `RISK_OFF` or `CHOPPY` depending on future source contract | `MARKET_CONTEXT_PARTIAL` or cautionary market context | Does not unlock memory alone. |
| Missing | `UNKNOWN` | `MARKET_CONTEXT_UNKNOWN` | Blocks clean eligibility. |
| Stale | Existing label may remain visible for audit | `MARKET_CONTEXT_STALE` | Audit-only. |
| Failed source | `UNKNOWN` | `MARKET_CONTEXT_DO_NOT_USE_FOR_MEMORY` | Audit-only. |
| Target mismatch | `UNKNOWN` or previous label only for audit | `MARKET_CONTEXT_CONFLICTING` | Blocks clean eligibility. |
| Missing source-governor trace | `UNKNOWN` | `MARKET_CONTEXT_UNKNOWN` | Blocks clean eligibility. |
| Non-paper-context | `UNKNOWN` | `MARKET_CONTEXT_DO_NOT_USE_FOR_MEMORY` | Invalid for V1 memory. |

## Label Mapping

Market-regime fixture labels are categorical and existing-compatible:

- Risk-on fixture evidence maps to existing `RISK_ON` when trend, liquidity, source status, data quality, freshness, target status, and source trace are all acceptable.
- Risk-off fixture evidence maps to existing `RISK_OFF` when broad market trend/liquidity context is weak or defensive.
- Neutral fixture evidence maps to existing `NEUTRAL` when broad trend is sideways and volatility is normal.
- Volatile fixture evidence maps to existing `VOLATILE` when volatility context is high.
- Missing, stale, failed, mismatched, untraceable, or non-paper-context evidence maps to `UNKNOWN`, audit-only, conflicting, stale, or do-not-use market context.

Requested generic candidate labels should stay documentation-level until runtime adoption is approved:

- Regime candidates: `MARKET_REGIME_RISK_ON`, `MARKET_REGIME_RISK_OFF`, `MARKET_REGIME_NEUTRAL`, `MARKET_REGIME_VOLATILE`, `MARKET_REGIME_UNKNOWN`
- Trend candidates: `MARKET_TREND_UP`, `MARKET_TREND_DOWN`, `MARKET_TREND_SIDEWAYS`, `MARKET_TREND_UNKNOWN`
- Volatility candidates: `MARKET_VOLATILITY_HIGH`, `MARKET_VOLATILITY_NORMAL`, `MARKET_VOLATILITY_LOW`, `MARKET_VOLATILITY_UNKNOWN`

Runtime storage should prefer the existing market-regime labels unless a future migration explicitly changes the contract.

There is no score, ranking, confidence percentage, weighted system, or buy/sell signal.

## Blocking Rules

- Missing market evidence remains `UNKNOWN`.
- Stale market evidence remains audit-only.
- Failed source evidence remains audit-only.
- Target mismatch blocks clean eligibility.
- Missing Source Governor trace blocks clean eligibility.
- Non-paper-context evidence is invalid for Printer V1 memory.
- Broad market context is not a direct trade signal.
- Market evidence alone cannot make memory clean.
- Market evidence cannot override token-level snapshots, safety, entry realism, exit realism, flow, chain heat, source quality, or memory-window coverage.
- Market regime cannot unlock retrieval, paper decisions, BUY, paper positions, paper trade events, or PnL.

## Source Governor Requirements

Future market-regime evidence must:

- Have a Source Governor request trace.
- Have a Source Governor response or failure trace.
- Preserve failed, stale, missing, malformed, and partial evidence honestly.
- Link to snapshot and memory/evidence window where applicable.
- Mark broad context scope clearly.
- Block clean eligibility when source trace is missing.
- Never be created directly by the memory engine.
- Never be created directly by the paper decision engine.
- Never be fetched through a private source loop.
- Use only free/public sources approved for V1.

## Central Scheduler Requirements

Future market-regime collection must:

- Use `MARKET_REGIME_CONTEXT` or a future approved scheduler job kind.
- Be bounded.
- Be operator-approved during manual proof.
- Avoid continuous loops.
- Avoid source spam.
- Respect resource priority behind token-level snapshots and safety/liquidity refreshes.
- Never directly unlock paper decisions, BUY, positions, trade events, or PnL.

## Clean-Memory Gate Preservation

Market-regime evidence alone cannot make memory clean.

Market-regime evidence only helps resolve:

- `market_regime_label: UNKNOWN`

These blockers can still prevent clean memory:

- `SOLANA_UNKNOWN` chain heat
- `SAFETY_UNKNOWN`
- `ENTRY_UNKNOWN`
- `EXIT_UNKNOWN`
- `FLOW_UNKNOWN`
- `PRESSURE_UNKNOWN`
- stale source evidence
- failed source evidence
- target mismatch
- incomplete memory-window evidence

Dirty, stale, failed, mismatched, audit-only, or do-not-train market context cannot enter retrieval or decisions.

## Fixture-Only Test Plan

Fixture-only tests should prove:

- Risk-on fixture maps to `RISK_ON`.
- Risk-off fixture maps to `RISK_OFF`.
- Neutral fixture maps to `NEUTRAL`.
- Volatile fixture maps to `VOLATILE`.
- Missing fixture remains `UNKNOWN`.
- Stale fixture remains audit-only.
- Failed source fixture remains audit-only.
- Target mismatch blocks clean eligibility.
- Missing Source Governor trace blocks clean eligibility.
- Non-paper-context evidence is invalid.
- No score, ranking, confidence, or weighted fields are present.
- No wallet, private-key, signature, signing, transaction, or live-execution fields are present.
- Market evidence alone does not make memory clean.
- Market evidence alone does not unlock retrieval.
- Market evidence alone does not create paper decisions.
- Market evidence alone does not create positions, trade events, or PnL.

## Non-Goals

This task does not:

- Add a market-regime adapter.
- Fetch live data.
- Call external APIs.
- Add paid dependencies.
- Add a migration.
- Mutate the persistent DB.
- Create source request, response, or failure rows.
- Create token snapshots.
- Create context rows.
- Build memory windows.
- Run retrieval.
- Create paper decisions.
- Unlock BUY.
- Create paper positions.
- Create paper trade events.
- Create PnL.
- Start Lane 7.

## Recommended Next Safe Task

Recommended next safe task:

- `Market Regime Storage Schema Design`

Why:

- This fixture contract defines market-regime evidence semantics.
- The next safe step is to compare these candidate fields against `printer_market_regime_snapshots` and decide whether existing storage is sufficient or whether a minimal future migration proposal is justified.
- No source adapter, live fetch, DB mutation, retrieval, paper decision, BUY, position, trade event, or PnL is needed for that task.

Alternative safe next task:

- `Solana Chain Heat Fixture Contract`

Lane 7 remains blocked until clean eligible memory exists.
