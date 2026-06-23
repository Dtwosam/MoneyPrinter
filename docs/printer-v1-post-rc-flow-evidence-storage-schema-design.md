# Flow Evidence Storage Schema Design

This is a pre-Lane-7 Post-RC storage schema design.

It is not Lane 7. It is not a real migration. It is not source adapter implementation. It does not fetch live data, call external APIs, mutate the persistent DB, create source rows, create token snapshots, create context rows, build memory windows, run retrieval, create paper decisions, unlock BUY, create paper positions, create paper trade events, or create PnL.

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

The existing `printer_trading_flow_snapshots` table already has useful side-aware columns such as `buys_5m`, `sells_5m`, `buy_volume_5m`, and `sell_volume_5m`. This proposed design focuses on future evidence storage and auditability: governed source traces, token/pair/snapshot/window targeting, freshness, target match, and paper-only context.

Implementation status update:

- No new flow migration was added.
- Existing governed DexScreener fixture normalization now preserves side-aware buy/sell transaction counts where the stored source payload contains them.
- Existing token snapshot payload JSON can now feed those side-aware fields into `printer_trading_flow_snapshots` when trading-flow context is built from a stored token snapshot.
- Failed, stale, conflicting, unknown, or dirty flow evidence remains audit-only/unknown for direction and pressure.
- Flow labels still do not unlock clean memory, retrieval, paper decisions, BUY, paper positions, paper trade events, or PnL.
- Lane 7 remains blocked until clean eligible memory exists.

## Proposed Future Table Shape

Proposed future table name:

- `printer_flow_evidence`

This is only a proposed design, not a migration.

The current `printer_trading_flow_snapshots` table may already be enough for some flow cases if source trace, target status, freshness, and window linkage can be represented safely elsewhere. A future migration should be considered only if existing storage cannot preserve those audit requirements.

| Candidate field | Suggested requirement | Purpose |
|---|---:|---|
| `id` | Required | Primary key. |
| `token_id` | Required | Links evidence to tracked token. |
| `pair_id` | Required for pair-level flow evidence | Flow is pair/liquidity-market behavior, so pair-scoped flow should require this. |
| `snapshot_id` | Required when attached to an evidence window | Links evidence to the token snapshot used by a memory window. |
| `memory_window_id` | Nullable | Direct link to a memory window when available. |
| `evidence_window_id` | Nullable | Optional future evidence-window link if used separately from memory windows. |
| `flow_evidence_role` | Required | Candidate value: `TOKEN_PAIR_FLOW_CONTEXT`. |
| `source_name` | Required | Governed source name. |
| `source_status` | Required | Existing source status: `COMPLETE`, `PARTIAL`, `FAILED`, `STALE`, or `CONFLICTING`. |
| `data_quality_label` | Required | Existing data quality label. |
| `target_status` | Required | Candidate values: `TARGET_MATCH`, `TARGET_MISMATCH`, `TARGET_UNKNOWN`. |
| `evidence_captured_at` | Required for clean eligibility | Capture timestamp for freshness and window alignment. |
| `freshness_label` | Required | Candidate values: `FLOW_EVIDENCE_FRESH`, `FLOW_EVIDENCE_ACCEPTABLE`, `FLOW_EVIDENCE_STALE`, `FLOW_EVIDENCE_UNKNOWN`. |
| `buy_tx_count` | Nullable | Side-aware buy count. |
| `sell_tx_count` | Nullable | Side-aware sell count. |
| `buy_volume_usd` | Nullable | Side-aware buy volume. |
| `sell_volume_usd` | Nullable | Side-aware sell volume. |
| `net_flow_direction_label` | Required normalized label | Existing-compatible label such as `FLOW_ACCUMULATION`, `FLOW_DISTRIBUTION`, `FLOW_CHOPPY`, `FLOW_EXHAUSTION`, or `FLOW_UNKNOWN`. |
| `flow_pressure_label` | Required normalized label | Existing-compatible pressure label such as `PRESSURE_STRONG_INFLOW`, `PRESSURE_BALANCED`, or `PRESSURE_UNKNOWN`. |
| `flow_activity_label` | Required normalized label | Existing-compatible activity label or future categorical activity label. |
| `flow_window_label` | Required | Candidate values: `FLOW_WINDOW_5M`, `FLOW_WINDOW_15M`, `FLOW_WINDOW_1H`, `FLOW_WINDOW_4H`, `FLOW_WINDOW_24H`. |
| `source_request_id` | Nullable, required for clean eligibility | Link to `printer_source_requests`. |
| `source_response_id` | Nullable | Link to `printer_source_responses` when source succeeds. |
| `source_failure_id` | Nullable | Link to `printer_source_failures` when source fails. |
| `paper_only_context` | Required | Must be true. Non-paper context is invalid for V1. |
| `created_at` | Required | Local row creation timestamp; not a clean-evidence differentiator by itself. |

No single source is assumed to provide all fields. Side-aware fields are candidate fields for future source-governed implementation and must be verified later.

## Required Constraints

Future storage should enforce or audit these constraints:

- `token_id` is required.
- `pair_id` is required for pair-level flow evidence.
- `snapshot_id` is required where evidence is attached to an evidence window.
- `paper_only_context` must be true.
- Source trace is required for clean eligibility.
- If source succeeds, `source_request_id` and `source_response_id` should be present.
- If source fails, `source_request_id` and `source_failure_id` should be present.
- Stale evidence cannot be clean.
- Failed evidence cannot be clean.
- Missing evidence remains `FLOW_UNKNOWN` and `PRESSURE_UNKNOWN`.
- Target mismatch cannot be clean.
- Missing source trace cannot be clean.
- Low-activity flow may be known but cautionary.
- Flow evidence cannot unlock clean memory by itself.
- No live execution fields.
- No wallet, private key, signing, signature, or transaction fields.
- No score, ranking, confidence, weighted, or numeric decision fields.

## Label Mapping From Storage

Stored evidence can later support categorical labels only.

Direction labels should use existing-compatible labels:

| Generic meaning | Existing-compatible label |
|---|---|
| Buy-dominant flow | `FLOW_ACCUMULATION` |
| Sell-dominant flow | `FLOW_DISTRIBUTION` |
| Balanced flow | `FLOW_CHOPPY` or equivalent balanced context |
| Rotation/noisy flow | `FLOW_ROTATION` |
| Low-activity flow | `FLOW_EXHAUSTION` |
| Unknown flow | `FLOW_UNKNOWN` |

Pressure labels should use existing-compatible labels:

| Generic meaning | Existing-compatible label |
|---|---|
| High inflow pressure | `PRESSURE_STRONG_INFLOW` |
| Moderate inflow pressure | `PRESSURE_MODERATE_INFLOW` |
| Balanced pressure | `PRESSURE_BALANCED` |
| Moderate outflow pressure | `PRESSURE_MODERATE_OUTFLOW` |
| High outflow pressure | `PRESSURE_STRONG_OUTFLOW` |
| Unknown pressure | `PRESSURE_UNKNOWN` |

Activity labels should remain categorical, such as:

- `VOLUME_SURGING`
- `VOLUME_ELEVATED`
- `VOLUME_NORMAL`
- `VOLUME_WEAK`
- `VOLUME_DEAD`
- `TX_ACTIVITY_SURGING`
- `TX_ACTIVITY_ELEVATED`
- `TX_ACTIVITY_NORMAL`
- `TX_ACTIVITY_WEAK`
- `TX_ACTIVITY_DEAD`
- `VOLUME_UNKNOWN`
- `TX_ACTIVITY_UNKNOWN`

There is no flow score, ranking, confidence percentage, weighted flow system, or BUY signal in this storage design.

## Audit Behavior

Future audit should treat storage states as follows:

- Buy-dominant flow: known flow context if source trace, target match, freshness, and data quality are acceptable.
- Sell-dominant flow: known flow context if source trace, target match, freshness, and data quality are acceptable.
- Balanced flow: known flow context, not a trade signal.
- Low-activity flow: known but cautionary; may support context only and cannot unlock clean memory alone.
- Missing flow evidence: remains `FLOW_UNKNOWN` / `PRESSURE_UNKNOWN` and blocks clean eligibility.
- Stale flow evidence: audit-only and blocks clean eligibility.
- Failed source flow evidence: audit-only and blocks clean eligibility.
- Target mismatch: audit-only and blocks clean eligibility.
- Missing Source Governor trace: audit-only even if payload appears complete.
- Non-paper-context evidence: invalid for V1 memory.

Audit output should not hide missing side-aware data, stale source evidence, failed source evidence, target mismatch, missing source trace, or low-activity caution.

## Source Governor Linkage

Future flow evidence must link to governed source records:

- `source_request_id` links to the approved source request.
- `source_response_id` links to the normalized response when collection succeeds.
- `source_failure_id` links to the failure when collection fails.

Flow evidence without proper governed source trace must remain audit-only. The memory engine, paper decision engine, retrieval engine, and scheduler job handler must not call external sources directly.

## Central Scheduler Linkage

Future flow evidence collection must be:

- Scheduled.
- Bounded.
- Operator-approved during manual proof.
- Non-continuous.
- Non-spammy.
- Governed by existing scheduler priority.
- Non-runtime-expanding unless a future roadmap task explicitly approves that work.

No runtime expansion, source loop, source spam, paper decision unlock, BUY unlock, paper position, trade event, or PnL may come from flow storage.

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

Dirty, stale, failed, target-mismatched, non-paper-context, audit-only, or do-not-train flow evidence cannot enter retrieval. Flow evidence alone cannot create paper decisions, BUY, paper positions, paper trade events, or PnL.

## Fixture-Only Test Plan

Fixture-only tests should prove:

- Proposed required fields are present.
- `token_id` is required.
- `pair_id` is required for pair-level flow evidence.
- Snapshot linkage is required for evidence-window clean eligibility.
- `paper_only_context` must be true.
- Source trace is required for clean eligibility.
- Stale evidence maps to audit-only.
- Failed evidence maps to audit-only.
- Missing evidence remains `FLOW_UNKNOWN`.
- Target mismatch blocks clean eligibility.
- Missing source trace blocks clean eligibility.
- Low-activity fixture does not unlock clean memory alone.
- No score, ranking, confidence, or weighted fields are present.
- No wallet, private-key, signature, signing, transaction, or live-execution fields are present.
- Flow evidence alone does not unlock clean memory.
- Flow evidence alone does not unlock retrieval.
- Flow evidence alone does not create paper decisions.
- Flow evidence alone does not create positions, trade events, or PnL.

## Non-Goals

This task does not:

- Add a real migration.
- Mutate the DB.
- Add an adapter.
- Call a live API.
- Collect live source data.
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

- `Market Regime Fixture Contract`

Why:

- Safety has fixture and storage design.
- Entry/exit quote evidence has fixture and storage design.
- Flow evidence has fixture and storage design.
- Market regime remains one of the remaining context blockers and should be defined fixture-first without live source integration or decision unlocks.

Lane 7 remains blocked until clean eligible memory exists.
