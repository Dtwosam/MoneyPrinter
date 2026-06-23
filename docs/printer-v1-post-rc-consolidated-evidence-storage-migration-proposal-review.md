# Consolidated Evidence Storage Migration Proposal Review

This is a consolidated pre-Lane-7 Post-RC review task.

It is not Lane 7. It is not a migration implementation. It is not source adapter implementation. It is not live data collection. It is not a paper decision task.

No migration file is added by this review. No database is mutated.

## Current State Summary

Current state:

- Clean memory remains `0`.
- Clean eligible memory remains `0`.
- Lane 7 remains blocked.
- Retrieval remains blocked.
- Paper decisions remain blocked.
- BUY remains locked.
- Paper positions remain `0`.
- Paper trade events remain `0`.
- PnL remains unavailable.

Evidence fixture/storage designs now exist for:

- paper quote evidence
- Solana safety evidence
- flow evidence
- market regime evidence

This review asks whether those designs are ready to become future migrations, in what order, and what must stay blocked. It does not add or apply migrations.

## Proposed Evidence Tables Under Review

| Proposed table | Blocker addressed | Evidence role | Source Governor linkage | Scheduler boundary | Clean-memory gate behavior | Migration needed before adapter work | Fixture/schema readiness | Risks or field changes needed |
|---|---|---|---|---|---|---|---|---|
| `printer_solana_safety_evidence` | `safety_status_label: SAFETY_UNKNOWN` | Token/pair safety, authority, holder distribution, known risk, liquidity lock/burn, token-program evidence | Must link to `source_request_id`; successful evidence needs `source_response_id`; failures need `source_failure_id` | Future collection should run through `TRACKED_TOKEN_SAFETY_LIQUIDITY_REFRESH` or approved equivalent | Can satisfy only the safety portion when fresh, target-matched, source-governed, paper-only, and not high-risk | Yes, likely before a Solana RPC/GoPlus-style adapter, because authority/distribution/target/freshness/source trace need durable audit fields | Ready for migration proposal | Align boolean naming with existing `printer_safety_rug_snapshots`; decide whether to extend existing table or create a dedicated evidence table |
| `printer_flow_evidence` | `flow_direction_label: FLOW_UNKNOWN`, `flow_pressure_label: PRESSURE_UNKNOWN` | Side-aware buy/sell counts, buy/sell volume, pressure, activity, flow-window context | Must link to request/response/failure trace for clean eligibility | Future collection should be scheduled, bounded, and lower priority than token snapshots and safety/liquidity refreshes | Can satisfy only flow direction/pressure portions; low-activity and missing side-aware data remain caution/audit-only | Not necessarily before adapter work if existing `printer_trading_flow_snapshots` plus raw payload can already preserve side-aware fields | Needs design revision before migration | Existing `printer_trading_flow_snapshots` already has buys/sells and buy/sell volume; prefer an extension/linkage review before creating a parallel table |
| `printer_paper_quote_evidence` | `entry_realism_label: ENTRY_UNKNOWN`, `exit_realism_label: EXIT_UNKNOWN` | Paper-only route, route plan, slippage, price impact, quote freshness, no-route/failure evidence | Must link to governed quote request/response/failure; failed/no-route evidence remains visible | Future collection must be bounded and scheduler-controlled; manual proof requires operator approval | Can satisfy only entry/exit realism portions; quote evidence alone cannot make memory clean | Yes before a Jupiter quote adapter, because quote evidence needs durable route/no-route/failure and source trace audit | Ready for migration proposal, after safety | Rename `paper_only` to `paper_only_context` for cross-table consistency unless there is a strong reason to keep shorter naming; keep quote fields paper-only and non-execution |
| `printer_market_regime_evidence` | `market_regime_label: UNKNOWN` | Broad market context: risk-on/off, neutral, volatile, trend, volatility, broad liquidity | Must link to governed broad-market source trace for clean eligibility | Future collection should use `MARKET_REGIME_CONTEXT`, be bounded, and stay below token-level priorities | Can satisfy only market-regime context; broad context cannot become a direct trade signal | Defer until source path is defined; existing `printer_market_regime_snapshots` may be enough with smaller linkage additions | Ready as design, but not first migration | Because this is broad context and existing table is already present, avoid creating a parallel table until source path and linkage gaps are proven |

## Cross-Table Consistency Review

### Token, Pair, And Snapshot Linkage

Recommended consistency:

- `token_id` should be required for token-specific evidence.
- `pair_id` should be required for pair-scoped evidence: quote, flow, pair liquidity/safety, and pair-specific market evidence.
- `snapshot_id` should be required when evidence is attached to an evidence window or memory-window audit.
- Broad market context may allow nullable `token_id` and `pair_id` only when `market_scope_label` is broad.
- Safety evidence may allow nullable `pair_id` only for token-level authority/distribution evidence; pair/liquidity lock evidence should require `pair_id`.

Before migration, each table should document whether it is token-level, pair-level, snapshot-level, memory-window-level, or broad context.

### Memory Window And Evidence Window Usage

Recommended consistency:

- Use `memory_window_id` when the evidence is attached to a concrete memory window.
- Keep `evidence_window_id` nullable until the separate evidence-window abstraction is implemented.
- Do not use `created_at`, job id, or retry id as evidence identity.
- Evidence-window clean eligibility should require snapshot/window linkage, not just token/pair linkage.

### Source Trace Fields

Recommended consistency:

- Use `source_request_id`, `source_response_id`, and `source_failure_id` across all proposed evidence tables.
- Successful clean-eligible evidence should require `source_request_id` and `source_response_id`.
- Failed evidence should require `source_request_id` and `source_failure_id`.
- Missing source trace must remain audit-only even if payload fields look complete.
- Future migration proposals should consider foreign keys to `printer_source_requests`, `printer_source_responses`, and `printer_source_failures`, following existing source trace conventions.

### Source Status And Data Quality

Recommended consistency:

- Keep existing `source_status` vocabulary: `COMPLETE`, `PARTIAL`, `FAILED`, `STALE`, `CONFLICTING`.
- Keep existing `data_quality_label` vocabulary: `CLEAN_DATA`, `ACCEPTABLE_PARTIAL_DATA`, `DIRTY_DATA`, `STALE_DATA`, `MISSING_CRITICAL_DATA`, `CONFLICTING_DATA`, `DO_NOT_TRAIN`.
- Do not create source-specific quality labels where existing common labels are enough.

### Target Status

Recommended consistency:

- Use `target_status` consistently with values such as `TARGET_MATCH`, `TARGET_MISMATCH`, and `TARGET_UNKNOWN`.
- `TARGET_MISMATCH` must block clean eligibility.
- Future reports should show whether the mismatch is token, pair, snapshot, memory window, time window, or source payload mismatch.

### Freshness Label

Recommended consistency:

- Use domain-specific freshness labels only where useful: `SAFETY_EVIDENCE_FRESH`, `FLOW_EVIDENCE_FRESH`, `MARKET_EVIDENCE_FRESH`, `QUOTE_FRESH`.
- All domains must include fresh, acceptable if allowed, stale, and unknown states.
- Stale evidence must be audit-only.

### Paper-Only Context

Recommended consistency:

- Prefer `paper_only_context` across all proposed evidence tables.
- The quote design currently uses `paper_only`; migration proposal should rename it to `paper_only_context` unless compatibility requires otherwise.
- `paper_only_context` must be required and true for V1 clean eligibility.

### Created At

Recommended consistency:

- `created_at` remains a storage timestamp only.
- `created_at` is not evidence freshness.
- `created_at` is not a meaningful evidence differentiator.

### Nullable Broad-Context Fields

Recommended consistency:

- Only broad context tables should allow nullable `token_id` and `pair_id`.
- Broad market/chain context must carry an explicit scope label.
- Broad context cannot override token-level evidence and cannot become a direct trade signal.

## Migration Priority Order

Recommended safest future migration order:

1. `printer_solana_safety_evidence`
   Safety is a hard protection gate and the current blocker cannot be solved from liquidity alone. A migration proposal here gives future source work a durable place for authority, holder distribution, risk flags, target status, freshness, and source trace.

2. `printer_paper_quote_evidence`
   Entry/exit realism has already been designed and is needed before any paper-profit realism claim. This should follow safety because quote realism cannot compensate for unknown or unsafe token evidence.

3. Flow linkage revision before `printer_flow_evidence`
   Do not immediately create `printer_flow_evidence`. First review whether the existing `printer_trading_flow_snapshots` table can be extended or linked with source trace/target/freshness/window metadata. It already stores side-aware flow fields.

4. Market regime linkage revision before `printer_market_regime_evidence`
   Do not immediately create `printer_market_regime_evidence`. First decide whether existing `printer_market_regime_snapshots` can be extended with source trace and evidence-window linkage. Market regime is broad context and must not become a direct trade signal.

Do not implement all migrations at once. The first future migration should be one narrow safety evidence migration proposal after operator approval.

## Migration Readiness Verdict

| Proposed table | Verdict | Reason |
|---|---|---|
| `printer_solana_safety_evidence` | `READY_FOR_MIGRATION_PROPOSAL` | Fixture and storage semantics are concrete, safety is a hard blocker, and existing table may not be enough for source trace/window targeting/paper-only audit without extension. |
| `printer_paper_quote_evidence` | `READY_FOR_MIGRATION_PROPOSAL` | Fixture and storage semantics are concrete; needs naming consistency before SQL, especially `paper_only_context`; should follow safety. |
| `printer_flow_evidence` | `NEEDS_DESIGN_REVISION` | Existing `printer_trading_flow_snapshots` already contains side-aware fields. Review extension/linkage before creating a parallel evidence table. |
| `printer_market_regime_evidence` | `DEFER_UNTIL_SOURCE_PATH_DEFINED` | Existing `printer_market_regime_snapshots` already stores broad market context. Defer a parallel evidence table until governed source path and table gaps are proven. |

## Clean-Memory Gate Preservation

Storage tables alone cannot create clean memory.

Source rows alone cannot unlock retrieval.

Evidence must be:

- fresh or acceptable by approved rules
- target-matched
- source-governed
- scheduler-compatible
- paper-only
- tied to snapshot/window evidence where required
- audited

All other critical blockers still apply. Fixing one evidence table never bypasses:

- complete memory-window coverage
- source quality
- safety
- entry realism
- exit realism
- flow direction/pressure
- market regime
- Solana chain heat
- dirty/audit-only memory blocking

Dirty, stale, failed, mismatched, ungoverned, non-paper, or audit-only evidence remains blocked from retrieval and decisions.

No paper decision, BUY, paper position, paper trade event, or PnL may come from storage alone.

## Not Allowed In Future Migrations

Future migrations must not add:

- score fields
- rank fields
- rating fields
- confidence fields
- weighted decision fields
- numeric decision score fields
- wallet fields
- private key fields
- signature fields
- signing fields
- transaction-building fields
- transaction-sending fields
- live execution fields
- BUY unlock fields
- PnL unlock fields
- direct retrieval-ready shortcut fields
- fields that let dirty/audit-only evidence become decision support

Any future migration must preserve Source Governor and Central Scheduler boundaries.

## Recommended Next Concrete Task

Recommended next safe task:

- `Solana Safety Evidence Migration Proposal`

Task scope:

- Draft one migration proposal document for `printer_solana_safety_evidence` or a minimal extension of `printer_safety_rug_snapshots`.
- Do not create the migration file yet.
- Compare dedicated-table vs extension approach.
- Specify exact fields, constraints, indexes, source trace links, freshness labels, target status, and paper-only guard.
- Keep retrieval, paper decisions, BUY, positions, trade events, and PnL blocked.

Do not recommend Lane 7 until clean eligible memory exists.

## Non-Goals

This task does not:

- Add a migration file.
- Apply migrations.
- Mutate the DB.
- Add an adapter.
- Fetch live data.
- Call external APIs.
- Collect source data.
- Create source request, response, or failure rows.
- Create token snapshots.
- Create context rows.
- Build memory windows.
- Rebuild memory.
- Run retrieval.
- Create paper decisions.
- Unlock BUY.
- Create paper positions.
- Create paper trade events.
- Create PnL.
- Activate Lane 7.
