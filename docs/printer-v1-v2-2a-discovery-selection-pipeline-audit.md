# Printer V1 V2-2A Discovery / Selection Pipeline Audit

Status: AUDIT ONLY

V2-2A is a read-only audit lane. It does not run discovery, fetch sources,
mutate a database, create memory, activate retrieval, create paper decisions,
unlock BUY/SELL/HOLD, open paper positions, create trade events, create paper
trade audits, create PnL, add scoring/ranking/confidence/weighted logic, add
embeddings/vectors, or introduce live-wallet/live-execution behavior.

## Source Stack Read

This audit used `docs/printer-v1-memory-growth-build-order-v2.md` as the active
memory-growth build order, alongside the higher-authority and supporting source
stack:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-assistant-active-build-order-anchor.md`

Important boundary: `docs/printer-v1-memory-growth-build-order-v2.md` is the
active memory-growth build order, not the sole source of truth.

## Lane Boundary Confirmation

Current lane: `V2-2A - Audit current discovery/selection pipeline`.

Allowed work in this lane:

- Static inspection.
- Read-only DB inspection.
- Existing artifact review.
- Audit documentation.

Forbidden work in this lane:

- Discovery runs.
- Source fetching.
- DB mutation.
- Memory generation.
- Runtime or scheduler execution.
- Retrieval activation.
- Paper decisions.
- BUY/SELL/HOLD.
- Paper positions, trade events, paper trade audits, or PnL.
- Scoring/ranking/confidence/weighted logic.
- Embeddings/vectors.
- Live wallet/private keys/real funds/live execution.
- Paid APIs.

## Files, Docs, Code, Tests, and Artifacts Inspected

Documents inspected:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-assistant-active-build-order-anchor.md`
- `docs/printer-v1-lane-x7-bounded-discovery-to-tracking-review.md`
- `docs/printer-v1-lane-x10-5-discovery-selection-explainability-audit.md`
- `docs/printer-v1-lane-x10-6-discovery-selection-traceability-repair.md`
- `docs/printer-v1-lane-x10-7-manual-discovery-15m-proof-report.md`

Code inspected:

- `src/printer_v1/discovery/contracts.py`
- `src/printer_v1/discovery/parser.py`
- `src/printer_v1/discovery/classifier.py`
- `src/printer_v1/discovery/discovery.py`
- `src/printer_v1/lifecycle/contracts.py`
- `src/printer_v1/lifecycle/tracking_queue.py`
- `src/printer_v1/operator_cli/commands.py`
- `src/printer_v1/operator_cli/lane_x6_discovery_selection_repair.py`
- `src/printer_v1/operator_cli/lane_x10_6_selection_traceability.py`

Migrations inspected:

- `migrations/003_scheduler_resource_governor.sql`
- `migrations/004_token_lifecycle_tracking_queue.sql`
- `migrations/005_discovery_engine.sql`
- `migrations/024_discovery_source_channel.sql`

Tests inspected:

- `tests/test_phase4_token_lifecycle_tracking_queue.py`
- `tests/test_phase5_discovery_engine.py`
- `tests/test_post_lane10_lane_x6_discovery_selection_repair.py`
- `tests/test_post_lane10_lane_x10_6_discovery_selection_traceability.py`

Artifacts inspected:

- `operator-runs/manual-x10-9-fresh/x6-selection.20260707-215733.json`
- `operator-runs/manual-x10-9-fresh/x10-6-selection-batch.20260707-215733.json`
- `operator-runs/lane-x14-attempt-3-auto-pick-fresh-track-fast/x14_attempt3_track_fast_candidates_20260708-123214.json`

## Read-Only DB Inspection Results

Persistent DB inspected read-only:

- Path: `data/printer_v1.sqlite3`
- Access mode: SQLite URI `mode=ro`
- Safety setting: `PRAGMA query_only = ON`
- Query type: `SELECT` only

Observed counts:

| Table | Count |
| --- | ---: |
| `printer_tokens` | 17 |
| `printer_pairs` | 21 |
| `printer_discovery_candidates` | 15 |
| `printer_tracking_queue` | 15 |
| `printer_token_lifecycle_events` | 15 |
| `printer_source_requests` | 1118 |
| `printer_source_responses` | 1071 |
| `printer_source_failures` | 47 |
| `printer_scheduler_jobs` | 989 |
| `printer_memory_windows` | 156 |
| `printer_memory_retrieval_matches` | 0 |
| `printer_paper_decisions` | 2 |
| `printer_paper_positions` | 0 |
| `printer_paper_trade_events` | 0 |
| `printer_paper_trade_audits` | 0 |

Discovery candidate distribution:

| Field | Value | Count |
| --- | --- | ---: |
| `discovery_action` | `TRACK_FAST` | 6 |
| `discovery_action` | `TRACK_NORMAL` | 8 |
| `discovery_action` | `WATCH_ONLY` | 1 |
| `source_name` | `dexscreener` | 9 |
| `source_name` | `geckoterminal` | 6 |
| `source_channel` | `DEXSCREENER_SEARCH` | 1 |
| `source_channel` | `GECKOTERMINAL_NEW_POOL` | 3 |
| `source_channel` | `GECKOTERMINAL_TRENDING_POOL` | 3 |
| `source_channel` | NULL | 8 |

Tracking queue distribution:

| Tracking lane | Queue status | Count |
| --- | --- | ---: |
| `TRACK_FAST` | `QUEUED` | 6 |
| `TRACK_NORMAL` | `QUEUED` | 8 |
| `WATCH_ONLY` | `QUEUED` | 1 |

Dedup and pair-state observations:

- Duplicate token mints: 0.
- Duplicate pair addresses: 0.
- Discovery candidates missing `source_response_id`: 0.
- Tokens with more than one pair:
  - token_id 7, mint `DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263`: 3 pairs.
  - token_id 12, mint `yMJPZbnhoHib3ib8n8PfiVcp9yauk1vnaGKLx7epump`: 2 pairs.
  - token_id 13, mint `9cRCn9rGT8V2imeM2BaKs13yhMEais3ruM3rPvTGpump`: 2 pairs.

Locked-state observations:

- Retrieval matches remain 0.
- Paper positions remain 0.
- Paper trade events remain 0.
- Paper trade audits remain 0.
- The DB contains two historical paper decision rows, but this audit did not run
  or create paper decisions.

## Current Discovery / Selection Pipeline Map

Current pipeline shape:

1. Operator-approved controlled discovery command:
   - `printer-discover-candidates-once`
   - Requires `--operator-approved`.
   - Requires Solana chain.
   - Caps `--max-candidates` at 1 to 3.
   - Supports governed source names including DexScreener and GeckoTerminal.

2. Source request/response/failure recording:
   - Discovery calls the governed source execution path.
   - Source trace rows are recorded before discovery candidates are processed.
   - Persistent discovery rows in the current DB all have `source_response_id`.

3. Payload validation and normalization:
   - `src/printer_v1/discovery/parser.py` validates source, Solana chain,
     token mint, pair address, captured timestamp, stale/conflicting payloads,
     and basic market fields.
   - Normalized fields include price, liquidity, volume, transaction windows,
     FDV/market cap where available, source name, token mint, pair address, and
     source-captured timestamp.

4. Candidate classification:
   - `src/printer_v1/discovery/classifier.py` assigns categorical outputs:
     `TRACK_FAST`, `TRACK_NORMAL`, `WATCH_ONLY`, `IGNORE`, or `INSTANT_REJECT`.
   - Classifier rules are threshold/gate based, not score based.
   - TRACK_FAST requires stronger liquidity and recent activity than
     TRACK_NORMAL.
   - WATCH_ONLY captures weak, partial, low-activity, dead, or incomplete
     candidates rather than discarding every non-fast token.

5. Token/pair upsert:
   - Tokens dedup by unique `token_mint`.
   - Pairs dedup by unique `pair_address`.
   - Same-token/new-pair cases can exist because one token may have multiple
     pair rows.

6. Discovery candidate persistence:
   - `printer_discovery_candidates` stores source trace, token/pair ids,
     source name, discovery label/action, source/data quality labels, raw and
     normalized payload JSON, lifecycle state, tracking lane, priority reason,
     and source channel fields where available.

7. Lifecycle and tracking handoff:
   - A lifecycle event is recorded.
   - `printer_tracking_queue` receives eligible candidates.
   - A scheduler follow-up job is created through tracking queue scheduler sync.

8. Later selection repair/reporting layers:
   - Lane X6 reads recent candidate state, dedups mints/pairs, filters
     cooldown/archive state, assigns memory-diet labels, and emits an
     auditable selection report.
   - Lane X10.6 adds event-kind tags, context tags, source trace references,
     manual override requirements, pair-drift acknowledgment, and batch-balance
     advisory output.
   - These later layers are currently report/artifact oriented; no durable
     `selection_batch` table was found in the inspected schema.

## Current Selection Reason Map

Base discovery reason fields:

| Layer | Reason field | Persistence |
| --- | --- | --- |
| Discovery classifier | `reason` / classifier reason | Stored into `priority_reason` after action/source composition. |
| Discovery candidate | `priority_reason` | Stored in `printer_discovery_candidates`. |
| Tracking queue | `priority_reason` | Stored in `printer_tracking_queue`. |
| Source channel | `source_channel`, `source_channel_reason` | Stored after migration 024 where provided. |
| X6 selection repair | `memory_diet_label`, `selection_reason` | Emitted in report/artifact, not found as a durable DB table. |
| X10.6 traceability | `event_kind`, `context_tags`, `inclusion_reason`, `rejection_reason`, `source_trace` | Emitted in report/artifact, not found as a durable DB table. |

Current strengths:

- Discovery-level selection reasons are auditable in DB.
- Source response linkage is present for current discovery rows.
- X6 and X10.6 define richer memory-value reasons without using scores/ranks.

Current gaps:

- X6 and X10.6 reason artifacts are not durably integrated into a shared
  selection-batch table.
- X10.6 can produce an empty batch if candidate-list input is not supplied,
  even when X6 produced selected candidates.
- The handoff from discovery DB rows to X6/X10.6 to Memory Factory token lists
  remains too manual for V2-2 completion.

## Current Token / Pair Dedup Map

Implemented safeguards:

- `printer_tokens.token_mint` is unique.
- `printer_pairs.pair_address` is unique.
- Active tracking queue duplicates are blocked for the same
  token_id/pair_id/tracking_lane in active statuses.
- X6 has explicit mint dedup and pair dedup.
- X6 reports same-token/new-pair cases with
  `same_token_new_pair_detected_explicitly`.
- X10.6 requires manual override for pair drift and no-discovery-origin cases.

Current DB observations:

- No duplicate token mints.
- No duplicate pair addresses.
- Three tokens currently have multiple pair rows.

Risk:

- Same-token/new-pair behavior is detected in X6/X10.6 but is not yet expressed
  as a single durable Memory Factory selection contract. V2-2B should decide
  whether a same-token/new-pair candidate is a revival, migration, pair drift,
  duplicate recycle, or separate memory-diet item before it enters a bounded
  memory cycle.

## Tracking Queue Handoff Map

Current handoff:

- `TRACK_FAST` discovery action maps to tracking lane `TRACK_FAST`.
- `TRACK_NORMAL` discovery action maps to tracking lane `TRACK_NORMAL`.
- `WATCH_ONLY` discovery action maps to tracking lane `WATCH_ONLY`.
- `INSTANT_REJECT` and `IGNORE` do not become active tracking items.

Queue behavior:

- Active queue statuses: `QUEUED`, `ACTIVE`, `PAUSED`, `COOLDOWN`.
- Terminal/excluded statuses include `ARCHIVED` and `SKIPPED`.
- Due-order priority is `PAPER_MONITORING`, `TRACK_FAST`, `TRACK_NORMAL`,
  `WATCH_ONLY`, then `COOLDOWN`.
- Scheduler job mapping exists for tracking lanes:
  - `TRACK_FAST` -> `TRACK_FAST_FIRST_15M`
  - `TRACK_NORMAL` -> `TRACK_NORMAL_FIRST_15M`
  - `WATCH_ONLY` -> `DISCOVERY_REFRESH`
  - `COOLDOWN` -> `BACKUP_SOURCE_CHECK`

Readiness finding:

- The handoff is structurally present.
- Multi-token memory-diet selection is not yet governed by durable bucket quotas
  or persisted batch reasons.
- WATCH_ONLY, cooldown, archive, and reopen exist as lifecycle concepts, but
  V2-2B must define how they feed a balanced Memory Factory diet.

## Memory-Diet Coverage Table

| Memory-diet target | Current support found | Gap for V2-2 completion |
| --- | --- | --- |
| Winners | TRACK_FAST and HOT_PAIR-like labels can capture fast/liquid candidates. | Must avoid winner-only batches and persist why a winner was selected. |
| Losers | X6/X10.6 can label dump/decay style candidates from payload fields. | Need bucket quotas and proof that losers are intentionally sampled. |
| Traps | X6 has `FAKE_PUMP`, `WICK_ONLY`, and `LATE_BUY_TRAP`; X10.6 has context tags. | Need durable selection reason storage and tests for trap inclusion. |
| Dead tokens | Classifier can WATCH_ONLY dead/low activity; X6 has `DEAD_TOKEN`. | Need design for whether/when dead tokens enter memory growth versus remain watch-only. |
| Failed pumps | X6 has fake pump and high-activity/no-follow-through style labels. | Need exact quota/reason language and proof data fields are sufficient. |
| Wick-only pumps | X6 and X10.6 labels exist. | Need durable bucket and non-duplicate evidence rules. |
| Late-buy traps | X6 and X10.6 labels exist. | Need explicit sampling requirement so fast movers do not become BUY-like selection. |
| Revivals | Lifecycle supports reopen; X6 has `REVIVAL`. | Need revival sampling and archive/cooldown re-entry rules. |
| Liquidity rising/falling/removed | Liquidity fields exist in normalized payloads; X6 has `LIQUIDITY_DECAY`. | Need quota and exact rise/fall/removed reason taxonomy. |
| Volume rising/decaying | Volume windows are normalized. | Need stable bucket rules for rising vs decaying volume. |
| Transaction spikes/decay | Transaction windows are normalized. | Need side-aware and decay labels where available; avoid treating unknown as clean. |
| Consolidation | Not clearly represented as a first-class bucket. | Needs V2-2B bucket design if desired for baseline memory. |
| Migration behavior | X10.6 has `MIGRATION_EVENT`; source channels include PumpSwap/PumpPortal labels. | Persistent DB currently shows DexScreener/GeckoTerminal discovery rows, not PumpPortal/PumpSwap rows. |
| Suspicious safety behavior | X10.6 has safety-risk context tags. | Need safety evidence linkage before using as memory-diet reason. |
| Realistic/unrealistic exit evidence | Quote/liquidity evidence exists elsewhere in the system, not directly in discovery selection. | Need selection design to preserve exit-realism learning targets without creating paper decisions. |

## Source Governor / Central Scheduler Boundary Findings

Source Governor findings:

- Controlled discovery command uses the governed source execution path.
- Source request/response/failure tables are populated in the persistent DB.
- Current discovery rows have source response linkage.
- No direct source fetch was run during this audit.

Central Scheduler findings:

- Tracking queue to scheduler integration exists.
- Scheduler job kinds and priorities exist.
- Persistent DB contains scheduler jobs.
- This audit did not run scheduler/runtime commands.

Boundary risk:

- The base discovery-to-tracking pipeline is governed.
- The later memory-diet selection reports are not yet a durable scheduler/source
  contract. V2-2B should specify exactly how future Memory Factory selection
  uses persisted discovery candidates without source-governor bypass or ad hoc
  token-list construction.

## Bias Risks

Winner-only bias:

- TRACK_FAST candidates are easier to route into early Memory Factory proofs.
- X5-era proofs relied on fast tokens and manual lists.
- V2-2B needs explicit non-winner memory-diet buckets.

Trending-token bias:

- Current DB discovery rows come from DexScreener and GeckoTerminal, including
  trending/new-pool channels.
- There is no durable quota preventing trending rows from dominating.

Dead-token under-sampling:

- WATCH_ONLY exists and the DB has one WATCH_ONLY row, but it is not yet clear
  how WATCH_ONLY becomes memory-growth evidence without manual override.

Revival under-sampling:

- Lifecycle supports reopen/revival, but current durable selection handoff does
  not prove revival quota or reason persistence.

Failed-pump under-sampling:

- X6/X10.6 labels exist, but they are not persisted into a selection batch table.

Duplicate token/pair recycling:

- Same-token/new-pair cases exist in the DB.
- X6 detects them, but V2-2B must define when they are migration/revival versus
  duplicate recycling.

Weak selection reasons:

- Base `priority_reason` is useful but broad.
- Richer X6/X10.6 explanations are artifact-only.

Hidden score/rank/confidence-like logic:

- Static inspection found categorical thresholds and labels, not scoring/ranking
  systems in the discovery/selection components reviewed.
- V2-2B should keep this explicit.

## Gaps and Blockers

- No durable selection-batch table was found for X6/X10.6 memory-diet output.
- No active V2 memory-diet quota policy exists yet.
- WATCH_ONLY, TRACK_NORMAL, cooldown, archive, and reopen behavior exist as
  lifecycle tools but need Memory Factory selection semantics.
- Same-token/new-pair behavior is real in the DB and needs explicit selection
  rules.
- X10.6 traceability can produce strong artifacts, but only when fed a candidate
  list; its integration with DB-backed X6 selection remains too manual.
- Current discovery rows are source-governed, but memory-diet selection is not
  yet a complete end-to-end durable pipeline.
- The current system can identify useful learning candidates, but it cannot yet
  prove balanced memory intake automatically.

## Money-Usefulness Contribution

V2-2A improves the money-usefulness roadmap by identifying whether Printer is
collecting only attractive fast movers or whether it can deliberately learn from
the full range of Solana memecoin outcomes.

The audit shows Printer already has enough structure to describe candidates,
dedup token/pair rows, and route tracking lanes. The missing piece is a durable,
auditable memory-diet selection contract that intentionally samples winners,
losers, traps, dead tokens, revivals, and exit-realism failures without turning
selection into a BUY predictor.

## What V2-2A Improves

V2-2A does not change runtime behavior. It improves the build process by making
the current discovery/selection state explicit:

- Base discovery persistence is present.
- Source trace linkage is present.
- Tracking queue handoff is present.
- Dedup logic exists.
- Same-token/new-pair detection exists.
- Memory-diet labels exist in report code.
- Durable selection-batch persistence and quota design remain missing.

## What V2-2A Still Does Not Unlock

V2-2A does not unlock:

- Discovery automation.
- Source fetching.
- Memory generation.
- Clean-memory creation.
- Retrieval.
- Paper decisions.
- BUY/SELL/HOLD.
- Paper positions.
- Trade events.
- Paper trade audits.
- PnL.
- 5m as a main memory window.
- 1h/4h/12h/24h activation.
- Live trading, wallet/private keys, real funds, or transaction execution.

## Proof/Test Needed Before V2-2 Completion

Before V2-2 can be considered complete, future work should prove:

- A memory-diet bucket taxonomy exists and is documentation-backed.
- Selection can produce a balanced candidate batch without scores/ranks.
- Every selected and rejected candidate has a durable reason.
- WATCH_ONLY, TRACK_NORMAL, TRACK_FAST, cooldown, archive, and reopen behavior
  have clear Memory Factory selection semantics.
- Same-token/new-pair behavior is explicitly classified as migration, revival,
  pair drift, duplicate recycling, or distinct evidence.
- Discovery source trace links remain visible through candidate selection.
- Token/pair dedup prevents indistinguishable duplicates without blocking
  meaningful same-token/new-pair learning.
- Selection does not create retrieval rows, paper decisions, positions, trade
  events, audits, or PnL.
- Selection does not introduce scoring/ranking/confidence/weighted logic.
- Selection can support a balanced memory diet in isolated tests.

## Functionality Risks / Setbacks / Efficiency Blockers

Functionality risks:

- Rich selection reasoning is not yet durable enough for a repeatable Memory
  Factory.
- Manual artifact handoffs can drift from DB-backed discovery candidates.
- Same-token/new-pair cases may be incorrectly recycled or over-sampled without
  a formal bucket policy.

Setbacks:

- WATCH_ONLY and TRACK_NORMAL are structurally present but not yet clearly tied
  to balanced memory production.
- Existing artifacts show selection tooling can be run without populated
  candidate input, creating empty-but-valid outputs that do not move the system
  toward memory growth.

Efficiency blockers:

- Manual token-list construction remains a bottleneck.
- No durable selection batch means later proof reports must reconstruct why a
  token entered a memory cycle.
- Without quotas, fast/trending candidates can consume attention before dead,
  failed, or revival examples are collected.

## Next Recommended Lane

Next recommended lane: `V2-2B - Design memory-diet buckets/quotas/reasons`.

V2-2B should remain design-only unless explicitly scoped otherwise. It should
define the exact bucket taxonomy, quota expectations, selection reasons,
same-token/new-pair handling, WATCH_ONLY/TRACK_NORMAL/TRACK_FAST semantics,
cooldown/archive/reopen behavior, and proof requirements for a balanced
15-minute Memory Factory selection pipeline.
