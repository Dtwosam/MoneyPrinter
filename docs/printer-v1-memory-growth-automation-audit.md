# Printer V1 Memory Growth Automation Audit

## Meta

**Lane:** Lane W — Memory Growth Automation Audit
**Status:** AUDIT-ONLY. Not an active build order. Not a runtime document.
**Date:** 2026-07-03

---

### This document explicitly does NOT:

- update `AGENTS.md`
- create a new active source-of-truth build order
- unlock runtime expansion by itself
- unlock source fetching by itself
- unlock retrieval activation
- unlock paper decisions
- unlock BUY, SELL, or HOLD
- unlock paper positions
- unlock PnL
- activate any memory factory behavior
- change any V1 hard rules

---

## 1. Current Anchor and Completed Proof State

### Confirmed Lane U / U2 Closeout (prior to Lane V)

Tag: `printer-v1-lane-u-u2-memory-factory-closeout`

Proved:
- Real `WINDOW_15M` windows created from governed DexScreener snapshots.
- Coverage and gap audits persisted per window by Lane U2.
- Coverage-blocked windows downgraded to `DIRTY_MEMORY / MISSING_CRITICAL_DATA`.
- E2Y same-pair group selection: when pair A has 6 coverage-pass windows and pair B has 1, E2Y selects pair A's group (6 ≥ 5) and runs the gate on that group only.
- E2Z created 6 clean memory episodes for the qualifying group.
- A second replay was idempotent — no duplicate episodes.
- Financial, retrieval, and paper-trading locks remained zero throughout.

Proof DB result (isolated rehearsal):

```
printer_episodes: 6 (CLEAN_MEMORY / CLEAN_DATA / COMPLETE / WINDOW_15M_CLEAN_MEMORY)
printer_memory_retrieval_queries: 0
printer_memory_retrieval_matches: 0
printer_paper_decisions: 0
printer_paper_positions: 0
printer_paper_trade_events: 0
printer_paper_trade_audits: 0
```

### Lane V Closeout

Tag: `printer-v1-lane-v-clean-memory-retrieval-report`

Proved:
- Read-only audit report over `printer_episodes`.
- Reads only `CLEAN_MEMORY / CLEAN_DATA / do_not_train=0 / episode_status=COMPLETE / window_kind != WINDOW_5M_MICRO_EVENT`.
- No DB writes. No retrieval activation. No paper decisions.
- No scoring, ranking, or confidence fields.
- Correct categorical labels: SAME_PAIR, SAME_TOKEN, SAME_WINDOW_KIND, RECENT_CLEAN_MEMORY, CONFLICTING_OUTCOME_LABELS, INSUFFICIENT_CLEAN_MEMORY.
- CLI: `printer-run-lane-v-clean-memory-report`.
- 110 tests / 110 passed.

### Current Working Tree

`data/` is untracked (proof DB artifacts). Nothing committed since Lane V tag.

---

## 2. Discovery Reliability Audit

### What discovery modules/commands exist?

**Core module:** `src/printer_v1/discovery/` — `discovery.py`, `classifier.py`, `parser.py`, `contracts.py`

**CLI command:** `printer-discover-candidates-once`

**Discovery processing path:**
```
process_discovery_payload(source_name, payload)
→ validate_discovery_payload()
→ normalize_candidates()
→ classify_discovery_candidate()
→ upsert_discovered_token() / upsert_discovered_pair()
→ enqueue_tracking_item() with chosen lifecycle state
→ enqueue_discovery_followup_jobs()
```

### Which sources feed discovery?

| Source | Purpose | Enabled |
|---|---|---|
| `dexscreener` | Token/pair discovery, market snapshots, boosted tokens | Registered; transport disabled-by-default |
| `geckoterminal` | Solana pool discovery, trending pools | Registered; not live-connected |
| `pumpportal` | Pump.fun launch and migration stream | Registered; stream transport not implemented |
| `pumpswap` | Post-migration pool read-only confirmation | Registered; confirmation-only |
| `coingecko` | Broad market context | Registered; broad context only |
| `alternative_me` | Fear/Greed index | Registered; broad context only |
| `defillama` | Solana TVL/DEX context | Registered; broad context only |
| `goplus` | Token safety reference | Registered; where available |
| `solana_rpc` | Onchain reference | Registered; public RPC |
| `helius_free` | Onchain reference (free tier) | Registered; optional |
| `jupiter_quote` | Paper quote realism only | Registered; paper-sim only |

**All sources:** `requires_paid_plan=False`. No paid API dependency exists.

### Are sources disabled-by-default or real-enabled?

The source registry (`src/printer_v1/sources/registry.py`) defines sources with rate limits and allowed request kinds, but **no live HTTP client exists in the codebase**. Source calls require an `_adapter` parameter (see `e2j_first_15m_cycle.py`, `e2i_source_transport.py`). Without an adapter, all source calls produce no output — controlled simulation mode. This is intentional: live collection requires explicit adapter injection.

**Verdict: Disabled-by-default. Real transport requires adapter injection and operator approval.**

### Are all source calls forced through Source Governor?

Yes. `src/printer_v1/sources/governor.py` provides `SourceRequestDecision` with `allowed: bool`. The governor enforces:
- Source name must be in `SOURCE_REGISTRY`.
- Request kind must be in `source.allowed_request_kinds`.
- `requires_paid_plan=False` must hold.
- Priority class ordering: `paper_realism > token_level > protection > discovery > broad_context`.

No engine is known to create its own API loop or bypass the governor. The architecture review (`docs/printer-v1-post-lane10-architecture-review.md`) confirms: "No engine may call external sources directly or create an independent API loop."

### Does discovery cover active Solana memecoin tokens well enough?

**What is covered (by design/classification):**
- DexScreener token/pair discovery: new pairs, boosted tokens, latest tokens, top boosted
- GeckoTerminal: new pools, trending pools
- PumpPortal: new Pump.fun launches, migrations
- PumpSwap: post-migration pool confirmation
- Channel labels include: DEXSCREENER_LATEST_BOOSTED, DEXSCREENER_TOP_BOOSTED, PUMPFUN_NEW_TOKEN, PUMPFUN_MIGRATION, PUMPSWAP_GRADUATED, GECKOTERMINAL_NEW_POOL, GECKOTERMINAL_TRENDING_POOL

**What is NOT actively collected yet:**
- Sudden volume or liquidity spikes on existing WATCH_ONLY tokens (no scheduled refresh wired in Lane U)
- Pump.fun trending/movers/mayhem surface (channel labels defined but data collection path not wired)
- Dead/revival detection (lifecycle events defined but no automated check)
- Dumps, revivals, micro-pumps are not yet reliably discovered at runtime

**Verdict: Discovery framework is well-designed and Solana memecoin-focused. Real collection capability depends on adapter injection and operator scheduling of `printer-discover-candidates-once`. No autonomous discovery loop exists yet.**

### Does discovery stay Solana-only?

Yes. `PRINTER_CHAIN = "solana"` enforced in `contracts/rules.py`. Non-Solana chains are rejected as `UNSUPPORTED_CHAIN`. All sources are Solana-focused or chain-agnostic context-only.

### Does discovery avoid becoming alpha/trade signal?

Yes. Discovery classifies using liquidity and volume thresholds (memory-learning value), not price-action predictions or BUY probability. Channel labels are audit-only metadata and do not become selection criteria.

### Does discovery write only allowed lifecycle/intake states?

Yes. The `DiscoveryOutputAction` enum allows: IGNORE, WATCH_ONLY, TRACK_NORMAL, TRACK_FAST, INSTANT_REJECT_MEMORY_ONLY. These map to `TokenLifecycleState` values that write to `printer_tracking_queue`.

### What is still manual/operator-approved?

**Everything.** No autonomous discovery loop exists. `printer-discover-candidates-once` is a one-shot operator command. Discovery candidates must be reviewed by the operator before tracking begins. Token lists for Lane U are operator-supplied JSON files.

---

## 3. Token Selection Reliability Audit

### How are discovered tokens selected for tracking?

The `classify_discovery_candidate()` function in `src/printer_v1/discovery/classifier.py` applies hard liquidity and volume thresholds:

| Lane | Condition |
|---|---|
| `TRACK_FAST` | `liquidity_usd >= $5,000` AND (`volume_5m >= $1,000` OR `txns_5m >= 10`) |
| `TRACK_NORMAL` | `liquidity_usd >= $1,000` (and basic market fields present) |
| `WATCH_ONLY` | Has price_usd and liquidity_usd but below TRACK_NORMAL threshold |
| `INSTANT_REJECT_MEMORY_ONLY` | Missing critical fields or unsupported chain |

**Channel override:** PumpSwap graduated tokens and similar migration channels apply a lower TRACK_FAST liquidity floor (graduation itself is evidence of real activity).

### Does selection include winners, losers, traps, dead tokens, etc.?

**By design, yes.** The classifier selects based on data completeness and minimum activity thresholds, not on whether the token will go up. A token that pumps and dumps, gets wash-traded, or has suspicious volume would still qualify for TRACK_FAST if the raw liquidity and activity numbers are present. This is by design — Printer needs memories of traps, rug pulls, and dead tokens, not just winners.

### Does it avoid winner-only bias?

**By policy, yes.** The Memory Factory Guide explicitly requires memories of: pumps, dumps, fake pumps, fast pump-dumps, wick pumps, late-buy traps, consolidations, dead tokens, revivals, liquidity decay, and fake liquidity. The thresholds ensure memory-learning value rather than predicted win probability.

**Risk:** In practice, DexScreener boosted/trending surfaces inherently over-represent active tokens. Dead tokens and revivals require WATCH_ONLY monitoring and re-promotion, which is not yet automated. This creates a **potential survivorship bias risk** if only active new tokens are ever discovered and tracked.

### Are selection reasons logged/auditable?

Yes. `priority_reason` is written to `printer_tracking_queue` for each enqueued item. Lifecycle events are recorded in `printer_token_lifecycle_events`. Discovery candidate records include `discovery_label` and `source_channel`.

### Is selection deterministic enough to debug?

Yes for single-token runs. Multi-token selection ordering is not yet tested.

---

## 4. Deduplication, Cooldown, and Rotation Audit

### Does Printer know when a token/mint was already discovered?

Yes. `upsert_discovered_token()` uses `INSERT OR IGNORE` on `token_mint`. The discovery engine then assigns `EXISTING_TOKEN_NEW_PAIR` or `EXISTING_TOKEN_EXISTING_PAIR` labels.

### Does Printer know when a pair was already discovered?

Yes. `upsert_discovered_pair()` uses `INSERT OR IGNORE` on `pair_address`.

### Does Printer distinguish same token across different pairs?

Yes. Both token_id and pair_id are tracked separately. E2Y now correctly groups candidates by `(token_id, pair_id)` to select the best same-pair window group (proven in Lane U2).

### Does Printer avoid selecting the same stale set of tokens over and over?

**Partially.** `has_active_tracking_duplicate()` prevents duplicate queue entries for `(token_id, pair_id, tracking_lane)`. But once a run is complete and the token remains ACTIVE, nothing automatically rotates it out. Lane U currently loops the same single token from the token_list indefinitely within a bounded run.

**Gap: No automatic cooldown trigger after a 15m window cycle completes.** The lifecycle event `ARCHIVE_AFTER_MEMORY_WINDOW` exists and `LifecycleEvent.ENTER_COOLDOWN` exists, but Lane U does not call these after completing a window cycle. The token stays in the same state and would be re-selected on the next run.

### Are there cooldown rules after tracking?

**Defined but not wired in Lane U.** `QueueStatus.COOLDOWN`, `LifecycleEvent.ENTER_COOLDOWN`, and `set_queue_status()` exist. No automated trigger fires after a clean memory is produced.

### Are there archive rules?

**Defined but not triggered automatically.** `archive_tracking_item()` and `LifecycleEvent.ARCHIVE_AFTER_MEMORY_WINDOW`, `ARCHIVE_STALE_TOKEN`, `ARCHIVE_UNUSABLE_LIQUIDITY` all exist. No automatic archive fires after a memory cycle.

### Are there reopen/revival rules?

**Defined.** `should_reopen_token()` in `lifecycle/state_machine.py` returns True when `revival_detected=True` or `manual_review=True`. `LifecycleEvent.REOPEN_REVIVED_TOKEN` and `MANUAL_REVIEW` exist. Revival detection requires operator input or external triggering — not yet automated.

### Can old dirty/audit-only memory coexist without blocking new distinct evidence?

**Yes.** E2Y group selection now correctly selects the best same-pair group. Coverage-blocked windows become `DIRTY_MEMORY / MISSING_CRITICAL_DATA`. A new clean cycle on the same token produces fresh distinct episodes.

### Can the tracking queue rotate fresh candidates without starving active tokens?

**Not yet.** Lane U is single-token only (enforced by `_load_and_validate_token_list`: exactly 1 TRACK_FAST approved token). Rotation across multiple candidates requires multi-token support, which is not yet implemented at the runner level.

### Deduplication summary

| Level | Implemented |
|---|---|
| Token mint | Yes (upsert by mint) |
| Pair address | Yes (upsert by pair_address) |
| Same token, new pair | Yes (EXISTING_TOKEN_NEW_PAIR) |
| Queue dedup (active) | Yes (has_active_tracking_duplicate) |
| Post-cycle cooldown | Defined but not wired |
| Post-cycle archive | Defined but not wired |
| Revival re-entry | Defined but manual |
| Multi-token rotation | Not implemented |

---

## 5. Multi-Token Tracking Readiness Audit

### Can the current runner safely support `max_active_tokens > 1`?

**No.** This is the most significant gap found in this audit.

The `run_memory_factory_cycle()` function declares `max_active_tokens: int` with a hard cap of 10 and `max_new_tokens` with a hard cap of 50. These parameters look like multi-token support. **However**, the function passes `token_list_path` to `build_e2j_first_15m_cycle_payload()`, which calls `_load_and_validate_token_list()`. That function enforces **exactly 1 TRACK_FAST approved token**:

```python
if len(track_fast_approved) > 1:
    return (
        False,
        f"expected 1 TRACK_FAST approved token, found {len(track_fast_approved)}",
        tokens,
        "",
    )
```

The loop in `run_memory_factory_cycle()` iterates snapshot/window-close cycles on **the same single token** for the full bounded duration. The `max_active_tokens` parameter is validated but does not cause the runner to actually iterate multiple tokens.

**Verdict: `max_active_tokens > 1` is declared but not functional. The underlying E2J/E2I/E2T pipeline enforces single-token operation.**

### Does it actually rotate snapshots across multiple active tokens?

No. All snapshot calls in the loop operate on the single token from the token_list.

### Does each token get enough snapshots for its own 15m window?

For the single token: yes, proven. For multiple tokens: not implemented.

### Can TRACK_FAST and TRACK_NORMAL run together without causing snapshot gaps?

Not tested. No multi-lane concurrent runner exists.

### Is there starvation protection?

Not applicable yet — single-token only.

### Does Lane U2 audit coverage/gaps per token/pair correctly when multiple tokens are active?

**Yes in isolation.** Lane U2 (`persist_coverage_for_windows`) processes windows by window_id list. E2Y now groups candidates by `(token_id, pair_id)`. If multiple tokens were in the DB, each would be evaluated independently. The logic is correct. The gap is at the runner level, not the audit level.

### Does E2Y group candidates per token/pair correctly?

**Yes.** E2Y `_select_best_pair_group()` groups candidates by `(token_id, pair_id)` and selects the best group. This is proven with 6+1 split across two pair_ids.

### Does E2Z create clean episodes without mixing tokens/pairs?

**Yes.** E2Z records `token_id` and `pair_id` on each episode. The group selection guarantees all episodes in one run share the same `(token_id, pair_id)`.

---

## 6. Scheduler Readiness Audit

### Which scheduler job kinds currently exist?

From `src/printer_v1/scheduler/contracts.py`:

| JobKind | Priority | Purpose |
|---|---|---|
| OPEN_PAPER_TRADE_MONITOR | 1 | Paper position monitoring (locked) |
| ACTIVE_EXIT_RISK_TOKEN | 2 | Exit risk monitoring (locked) |
| TRACK_FAST_MICRO_EVENT | 3 | 5m support snapshot |
| TRACK_FAST_FIRST_15M | 4 | Primary 15m snapshot/window-close |
| TRACK_NORMAL_FIRST_15M | 5 | TRACK_NORMAL snapshot/window-close |
| MEMORY_WINDOW_CLOSE | 6 | Window-close trigger |
| TRACKED_TOKEN_SAFETY_LIQUIDITY_REFRESH | 7 | Safety/liquidity refresh |
| DISCOVERY_REFRESH | 8 | Discovery candidate refresh (WATCH_ONLY) |
| MARKET_REGIME_CONTEXT | 9 | Broad market context |
| SOLANA_CHAIN_HEAT_CONTEXT | 10 | Solana chain context |
| BACKUP_SOURCE_CHECK | 11 | Backup source verification |

Token-level snapshot jobs (TRACK_FAST_FIRST_15M, TRACK_FAST_MICRO_EVENT) are correctly prioritized above broad context (MARKET_REGIME_CONTEXT, SOLANA_CHAIN_HEAT_CONTEXT).

### Are snapshot jobs Central Scheduler-led?

Yes. `scheduler.py` manages job enqueue, lock acquisition (`LockResult.ACQUIRED / ALREADY_LOCKED`), and job status transitions. Lane U calls E2J → E2T → E2M through the scheduler, not directly.

### Does any engine create its own timing/API loop?

No live API loops exist in the codebase. The bounded loop in `run_memory_factory_cycle()` uses `time.monotonic()` and `time.sleep()` (via `snapshot_interval_seconds`), but this is an operator-controlled bounded run, not an autonomous daemon.

### Are job locks, duplicate prevention, retries, cooldowns, next-check time, and starvation protection implemented?

| Feature | Status |
|---|---|
| Job locks (ACQUIRED/ALREADY_LOCKED) | Implemented |
| Duplicate active job prevention (DUPLICATE_ACTIVE_JOB) | Implemented |
| Retries (max_retries per source) | Defined in source registry |
| Cooldowns (QueueStatus.COOLDOWN) | Defined |
| Next-check time (next_check_at) | Implemented in queue |
| Starvation protection across multiple tokens | Not implemented (single token) |

### What breaks if 2, 3, 5, or 10 active tokens are tracked?

**All break.** The `_load_and_validate_token_list` gate rejects token lists with more than 1 TRACK_FAST token before any cycle begins. The scheduler priority ordering is correct in theory, but no multi-token runner exists to exercise it.

---

## 7. Source Governor and Source Budget Audit

### Which sources are currently registered?

11 sources (see Section 2). All `requires_paid_plan=False`.

### Which are live-capable, disabled, fixture-only, or governed?

| Source | Capability | Notes |
|---|---|---|
| dexscreener | Governed (adapter required) | Main discovery + snapshot source |
| geckoterminal | Governed (not connected) | Pool discovery, not wired |
| pumpportal | Governed (stream not implemented) | Launch/migration stream |
| pumpswap | Governed (read-only confirmation only) | Post-migration confirmation |
| alternative_me | Governed (broad context) | Fear/Greed |
| coingecko | Governed (broad context) | Market context |
| defillama | Governed (broad context) | Chain/liquidity context |
| goplus | Governed (where available) | Safety reference |
| solana_rpc | Governed (public RPC) | Onchain reference |
| helius_free | Governed (free tier optional) | Onchain reference |
| jupiter_quote | Paper simulation only | Quote realism |

**No source is "live-enabled" by default.** All require explicit adapter injection and operator approval to collect live data.

### Are source request/response/failure rows recorded?

Yes. Tables `printer_source_requests`, `printer_source_responses`, and `printer_source_failures` exist. Lane U reports delta counts for all three: `source_requests_created`, `source_responses_created`, `source_failures_created`.

### Safe free-source budget estimates

Based on source registry rate limits (per-minute caps) and 15m window behavior (one DexScreener call per snapshot):

| Configuration | DexScreener calls/15m | Estimated in budget? |
|---|---|---|
| 1 TRACK_FAST token (90s interval) | ~10 snapshots | Safely within 60/min cap |
| 2 TRACK_FAST tokens (90s each, alternating) | ~20 snapshots | Still within cap |
| 3 TRACK_FAST tokens | ~30 snapshots | Approaching rate limit |
| 5 TRACK_FAST tokens | ~50 snapshots | At or near DexScreener limit |
| 10 TRACK_FAST tokens | ~100 snapshots | Over DexScreener 60/min cap |

**Risk: At 5–10 active tokens, DexScreener rate limits (60/min) are at risk without staggered scheduling. GeckoTerminal (30/min) would be even more constrained.**

### Are budgets configurable?

Rate limits are hardcoded per-source in the source registry. No per-run configurable budget exists yet. Stop gates are handled by `LockResult.RESOURCE_LIMITED` in the scheduler, but this is not yet tied to a source budget counter.

### What stop condition should trigger if source failures or rate limits rise?

**Currently: LANE_U_STATUS_STOPPED when a snapshot E2J call returns non-EXECUTED status.** No automatic source-failure rate monitor or rate-limit backoff exists at the runner level. The source registry defines `retry_after_seconds` and `max_retries` per source, but these are contract definitions, not enforced backoff logic in the current runner.

**Gap: No automated rate-limit stop gate in the runner. A surge of failures would stop the run but would not implement progressive backoff.**

---

## 8. Current One-Command Automation Readiness

### Assessed command

```powershell
printer-run-memory-factory-cycle --operator-approved --duration 6h --max-new-tokens 50 --max-active-tokens 10 --max-track-fast 3 --max-track-normal 7 --windows WINDOW_5M_MICRO_EVENT,WINDOW_15M
```

### Verdict: NOT_READY

### Exact blockers

| Blocker | Severity | Detail |
|---|---|---|
| `--max-track-fast` does not exist | **Hard blocker** | Lane U has no `--max-track-fast` CLI arg. TRACK_FAST count is implicit (exactly 1 in token_list). |
| `--max-track-normal` does not exist | **Hard blocker** | No TRACK_NORMAL runner is wired into Lane U. |
| `--windows WINDOW_5M_MICRO_EVENT,WINDOW_15M` is wrong syntax | **Hard blocker** | Lane U uses `--window-kind WINDOW_15M` + `--support-window-kind WINDOW_5M_MICRO_EVENT` separately. |
| Multi-token operation not implemented | **Hard blocker** | `_load_and_validate_token_list` enforces exactly 1 TRACK_FAST token. `max_active_tokens=10` is validated but unused. |
| No autonomous discovery feeding token selection | **Hard blocker** | Lane U requires a manually supplied `token_list_path`. `--max-new-tokens 50` would be ignored. |
| No post-cycle cooldown/rotation | **Medium blocker** | The runner would loop the same 1 token for the full 6 hours, not discover and rotate 50 new tokens. |
| No rate-limit backoff at 10 active tokens | **Medium blocker** | DexScreener 60/min would be exceeded with 10 concurrent TRACK_FAST tokens at 90s intervals. |

---

## 9. Timeframe Growth Readiness

### 5m support-only (`WINDOW_5M_MICRO_EVENT`)

**Status: Partially implemented.**

- `e2v_5m_micro_event_evidence.py` exists — 5m micro-event evidence capture.
- `e2w_5m_linkage_report.py` exists — linkage between 5m and 15m.
- `printer-report-e2w-5m-linkage` CLI exists.
- Lane U recognizes `support_window_kind="WINDOW_5M_MICRO_EVENT"` and refuses to promote it to main window.
- `WINDOW_5M_MICRO_EVENT` episodes are excluded from Lane V's clean memory retrieval.

**What is missing:** Real 5m capture integration into Lane U's bounded loop. The runner captures 15m snapshots only. A separate `TRACK_FAST_MICRO_EVENT` job kind exists in the scheduler but is not wired into Lane U's per-cycle loop.

**Next proof required:** 5m support capture integrated into a bounded 15m run, with 5m episodes stored as support-only and correctly excluded from E2Y/E2Z clean memory creation.

### 15m main memory (`WINDOW_15M`)

**Status: Fully implemented and proven.**

- Lane U bounded runner working.
- E2J → E2T → E2O → E2Q → Lane Q → Lane U2 → Lane K → E2X → E2Y → E2Z proven.
- 6 clean episodes created from real 15m windows in isolated rehearsal.
- Coverage/gap audit per window.
- E2Y same-pair group selection proven.
- Lane V audit reporting proven.

**Next proof required:** Multi-token 15m run (2 tokens → separate episode groups, no mixing).

### 1h activation (`WINDOW_1H`)

**Status: Documentation-only.**

- `lane_h_1h_bounded_memory_factory.py` exists as a factory review/planning module.
- Real `WINDOW_1H` collection is blocked in Lane U: `_DISABLED_COLLECTION_WINDOW_KINDS = {"WINDOW_1H", "WINDOW_4H", "WINDOW_12H", "WINDOW_24H"}`.
- No 1h proof DB exists.

**Blocker:** 15m memory must be stable across multiple tokens first. 1h requires 1h of sustained snapshot collection from a single token — much more exposure to source failures, rate limits, and data quality issues.

**Next proof required:** 1h readiness review (sources, scheduler capacity, snapshot gap tolerance), then a controlled 1h proof run with a single token.

### 4h activation (`WINDOW_4H`)

**Status: Documentation-only.**

- `lane_i_4h_staged_memory_factory.py` exists as a planning/staging module.
- Blocked in Lane U (same as 1h).

**Next proof required:** 1h proven first. Then 4h readiness review + 4h proof run.

### 12h activation (`WINDOW_12H`)

**Status: Documentation-only.**

- `lane_i_12h_staged_memory_factory.py` exists.
- Blocked in Lane U. Requires `allow_long_bounded_run=True` even when implemented.

**Next proof required:** 4h proven first.

### 24h activation (`WINDOW_24H`)

**Status: Documentation-only.**

- `lane_i_24h_staged_memory_factory.py` exists.
- Blocked in Lane U. Requires `allow_long_bounded_run=True`.

**Next proof required:** 12h proven first.

### Summary

| Timeframe | Status |
|---|---|
| WINDOW_5M_MICRO_EVENT (support) | Partially implemented — capture not wired into bounded loop |
| WINDOW_15M (main) | **Fully implemented and proven** |
| WINDOW_1H | Documentation-only. Blocked. |
| WINDOW_4H | Documentation-only. Blocked. |
| WINDOW_12H | Documentation-only. Blocked. |
| WINDOW_24H | Documentation-only. Blocked. |

---

## 10. Memory Growth Risk Audit

| Risk | Severity | Current mitigation | Gap |
|---|---|---|---|
| Duplicate token recycling | Medium | `has_active_tracking_duplicate` prevents queue duplicates | No post-cycle cooldown wired |
| Pair switching (same token, different pair) | Medium | E2Y groups by (token_id, pair_id); episodes store pair_id | Old pair's dirty memory stays separate; no explicit block |
| Source rate limits | High (at scale) | Source registry defines caps; LockResult.RESOURCE_LIMITED | No automated rate-limit backoff in runner |
| Stale data | Medium | `stale_after_seconds` defined per source; E2X checks data quality | Stale data becomes DIRTY_MEMORY; not forced clean |
| Snapshot gaps | Medium | Lane U2 coverage/gap audit per window | COVERAGE_BLOCKED windows downgraded to dirty |
| Dirty memory pollution | Low | E2Y/E2Z gates block dirty episodes; Lane K requires coverage pass | Dirty episodes stay in DB but cannot become retrievable |
| Winner-only dataset | Medium | Thresholds select any qualifying token, not winners only | DexScreener trending/boosted surfaces over-represent active tokens |
| Survivorship bias | Medium | Policy requires losers, traps, dead tokens | No automated dead/revival token monitoring yet |
| Unrealistic profit labeling | Low | PnL/positions locked; paper profit not calculated until separate unlock | N/A — locked |
| 5m becoming main outcome memory | Low | WINDOW_5M_MICRO_EVENT excluded from E2Y/E2Z and Lane V | Correct |
| Long-window fake data | Low | 1h/4h/12h/24h collection blocked in Lane U | Real longer-window data requires separate unlock per timeframe |
| Accidental retrieval activation | Low | Lane V hard_locks include no_retrieval_activation=True | No write path to retrieval tables in current runner |
| Accidental paper decision creation | Low | Paper decision count monitored as delta in Lane U | No paper decision code path active |
| Accidental BUY/position/PnL unlock | Low | All locked; separate unlock gates required | Verified: 0 in proof DB |

---

## 11. Recommended Next Build-Order Shape

**This is a recommendation only. No lane below is active until the operator explicitly adopts it.**

### Priority order reasoning

The single biggest gap is **multi-token 15m readiness**. The proven 15m path works for 1 token. Expanding to 2–3 tokens is the next step that unlocks real memory diversity (multiple tokens, multiple market conditions, losers as well as winners).

Before drafting a new build order, the operator should confirm:
1. Whether the existing single-token proof is considered stable enough to expand.
2. Whether discovery automation (autonomous candidate finding) should precede or follow multi-token tracking.

### Proposed lanes for the future build order

The following lanes should be evaluated in roughly this order:

**Lane X1 — Multi-Token 15m Readiness Review**
- Review what needs to change in `_load_and_validate_token_list` to accept 2–3 tokens.
- Design snapshot rotation strategy across multiple tokens.
- Design post-cycle cooldown/archive wiring.
- Documentation only. No implementation yet.

**Lane X2 — 2-Token Controlled 15m Proof**
- Modify token list validator to accept 2 TRACK_FAST tokens.
- Run Lane U with 2 tokens for 1h–4h.
- Verify each token gets its own distinct episode group.
- Verify no mixing of (token_id, pair_id) across episodes.
- Verify idempotent replay still works.

**Lane X3 — Post-Cycle Cooldown and Token Rotation**
- Wire `ENTER_COOLDOWN` / `ARCHIVE_AFTER_MEMORY_WINDOW` after a window cycle completes.
- Implement automatic rotation to next available WATCH_ONLY or QUEUED candidate.
- Prevent same token being re-selected before cooldown expires.

**Lane X4 — 3-Token and 5-Token Controlled 15m Proof**
- Expand to 3 tokens, then 5 tokens.
- Verify source budget stays within DexScreener 60/min cap.
- Add source budget counter and runner-level stop gate.

**Lane X5 — Discovery Automation Review**
- Review whether `printer-discover-candidates-once` can be called from within the bounded runner to find new candidates automatically.
- Determine whether autonomous discovery is safe under existing source governance.
- Documentation and review only; no autonomous loop without explicit operator approval.

**Lane X6 — 5m Support Evidence Integration**
- Wire `TRACK_FAST_MICRO_EVENT` job into the bounded 15m loop as a support-only capture.
- Verify 5m episodes never contaminate E2Y/E2Z selection.
- Verify `support_only_excluded_count` stays accurate in Lane V.

**Lane X7 — 1h Activation Readiness**
- After 15m is stable across 3–5 tokens: 1h readiness review.
- Source budget analysis for 1h sustained snapshot collection.
- Proof run with 1 token × 1 window.

**Lanes X8–X10 — 4h, 12h, 24h** (staged, each after prior is proven)

### The one-command vision (not yet ready)

```powershell
printer-run-memory-factory-cycle \
  --operator-approved \
  --duration 6h \
  --max-new-tokens 50 \
  --max-active-tokens 10 \
  --max-track-fast 3 \
  --max-track-normal 7 \
  --windows WINDOW_5M_MICRO_EVENT,WINDOW_15M
```

This requires at minimum: Lanes X1–X4 plus discovery automation (X5) and 5m support (X6) to all complete. Estimated: 6+ implementation lanes.

---

## 12. Checks Run

The following safe read-only checks were performed for this audit:

| Check | Result |
|---|---|
| `git status` | Clean (only `?? data/`) |
| `src/printer_v1/discovery/` module existence | Confirmed |
| `src/printer_v1/sources/registry.py` — 11 sources | Confirmed |
| `src/printer_v1/scheduler/contracts.py` — 11 job kinds | Confirmed |
| `src/printer_v1/lifecycle/contracts.py` — lifecycle states and events | Confirmed |
| `src/printer_v1/lifecycle/tracking_queue.py` — dedup and cooldown logic | Confirmed |
| `src/printer_v1/discovery/classifier.py` — selection thresholds | Confirmed |
| `src/printer_v1/operator_cli/e2i_source_transport.py` — `_load_and_validate_token_list` | Confirmed: exactly 1 TRACK_FAST enforced |
| `src/printer_v1/operator_cli/lane_u_memory_factory_runner.py` — multi-token params | Confirmed: params declared but single-token at E2J level |
| `pyproject.toml` — 43 registered CLI commands | Confirmed |
| `docs/printer-v1-lane-u-u2-memory-factory-closeout.md` — proof DB summary | Confirmed |
| Source file existence checks for all referenced modules | Confirmed |

No DB writes were performed. No source calls were made. No migrations were run.

---

## 13. Confirmation of No Runtime Changes

This audit document is the only artifact created by Lane W.

**No code was written or modified.**
**No migrations were created or applied.**
**No source calls were made.**
**No memory was mutated.**
**No retrieval was activated.**
**No paper decisions were created.**
**No BUY/SELL/HOLD was unlocked.**
**No positions were opened.**
**No PnL was calculated.**
**`data/` was not touched.**

---

## Audit Verdict Summary

| Area | Verdict |
|---|---|
| Current anchor | Lane V tag confirmed; 6 clean episodes proven |
| Discovery | Framework solid; all sources governed; collection manual-only |
| Token selection | Memory-value based, not BUY-probability based; auditable |
| Deduplication | Token/pair level dedup works; post-cycle cooldown not wired |
| Multi-token tracking | **NOT READY** — enforced single-token at E2J/E2I level |
| Scheduler | Job kinds and priority correct; multi-token not exercised |
| Source Governor | All sources governed; rate limits defined; no runtime backoff |
| One-command automation | **NOT_READY** — see Section 8 for exact blockers |
| 15m memory | **Fully implemented and proven** |
| 1h/4h/12h/24h | Documentation-only; blocked until 15m multi-token proven |
| 5m support | Partially implemented; not wired into bounded loop |
| Memory growth risks | Documented; most mitigated; winner-bias and post-cycle rotation are key gaps |
| Recommended next lane | Lane X1 — Multi-Token 15m Readiness Review |
