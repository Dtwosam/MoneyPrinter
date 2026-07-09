# Printer V1 — V2-2H Discovery/Selection Repair Implementation Closeout

**Lane:** V2-2H (slices H.1–H.6)
**Status:** IMPLEMENTATION_COMPLETE_WITH_BLOCKERS
**Date:** 2026-07-09
**Commits:** 64799e4 (H.1) → 6587468 (H.2) → e71c6e3 (H.3) → 9c317f5 (H.4) → c429e22 (H.5) → (H.6)

---

## 1. Lane Boundary

V2-2H implemented six bounded slices of discovery/selection repair. Each
slice targeted one specific repair area from the V2-2G design (`0aa1242`)
without crossing into adjacent work.

**V2-3 remains paused.** Automation design does not resume until the V2-2
repair sequence is fully proved in an isolated proof environment (V2-2I).

**No capability was unlocked by V2-2H.** No memory generation, no retrieval
activation, no paper decisions, no financial logic, no live trading.

V2-2I bounded proof is next only if this closeout is accepted by the operator.

---

## 2. Per-Slice Summary

### H.1 — Candidate Cap / Stage Reporting / Schema Readiness
**Commit:** 64799e4

- `max_candidates` widened from hard-coded 1–3 to configurable 1–50; default raised to 10.
- Added `candidate_stage_report` separating seen / normalized / persisted / rejected counts.
- All `candidate_stage_report` values are `int` or `"NOT_MEASURED"` (H.1 invariant; enforced through H.6).
- Added selection-batch schema readiness check.

### H.2 — Age / Activity / Recent-Active Priority
**Commit:** 6587468

- Added age buckets: VERY_NEW, NEW, ESTABLISHED, OLD, UNKNOWN_AGE.
- Added activity buckets: HIGH, MEDIUM, LOW, MINIMAL, DEAD, UNKNOWN_ACTIVITY.
- Added recent-active tiers: RECENT_HIGH, RECENT_MEDIUM, RECENT_LOW, STALE.
- Added `age_activity_report` as a separate top-level key (not nested in `candidate_stage_report`).

### H.3 — Field Normalization / A1–A4 Helpers / Field Completeness
**Commit:** e71c6e3

- Added `_parse_created_at()` and `_safe_age_seconds()` to `parser.py`.
- `normalize_candidate()` now extracts and derives: `pair_created_at`, `token_created_at`,
  `pair_age_seconds`, `token_age_seconds`, `price_change_5m`, `price_change_15m`,
  `price_change_1h`, `price_change_24h`.
- `NORMALIZED_FIELDS` extended with all 8 new fields.
- `geckoterminal.py` adapter updated to extract `price_change_percentage` sub-fields.
- A2 gate: explicit `_pc5m_known` guard (replaces accident-of-`_f()` zero comparison).
- A3 gate: explicit `_tok_age_known` and `_pc1h_known` guards.
- `derive_failed_pump_bucket()` helper implemented (A4; not wired into `assign_bucket()` main path — see deferred).
- `build_field_completeness_report()` added; `field_completeness_report` added to payload.

### H.4 — Within-Response Duplicate / STNP Handling
**Commit:** 9c317f5

- `filter_within_response_duplicates()` added to `selection_batch.py`.
- Duplicate `pair_address` within one response → `REJECTION_PAIR_DUPLICATE_WITHIN_RESPONSE`.
- Duplicate `token_mint` within one response → STNP event:
  - Migration channel (`PUMPFUN_MIGRATION`, `PUMPSWAP_GRADUATED`, `PUMPSWAP_MIGRATION_POOL_REFERENCE`)
    → `STNP_MIGRATION` → routed through V2-2C `classify_same_token_new_pair()`.
  - All other channels → `REJECTION_STNP_WITHIN_RESPONSE_UNRESOLVED` (conservative; blocks persistence).
- Applied in `commands.py` before `_select_discovery_candidates`.
- `within_response_integrity_report` added as a separate top-level key.

### H.5 — Bounded Multi-Request / Source-Budget Plumbing
**Commit:** c429e22

- `max_source_requests` parameter added (range 1–10, default 1).
- `_SOURCE_REQUEST_PLAN_CATALOG` maps each source to ordered `(request_kind, status)` pairs.
  - GeckoTerminal: 2 READY (new_pool_discovery, trending_pool_reference).
  - DexScreener: 1 READY (token_discovery).
  - PumpPortal: 2 NOT_READY (WebSocket streams; fixture-only).
  - PumpSwap: 2 NOT_READY (fixture-only confirmation; no live path).
- `_build_source_request_plan()`, `_get_transport_for_index()`, `_execute_plan_item()` helpers added.
- Plan loop executes each READY item through Source Governor; NOT_READY items reported but skipped.
- Per-response H.4 filter runs before aggregation.
- Cross-response dedup pass added after aggregation (same conservative STNP treatment).
- `_aggregate_wr_reports()` merges per-response within-response reports.
- `source_budget_report` added to payload with full per-channel seen/persisted metrics.
- `--max-source-requests` CLI argument added to `main_discover_candidates_once`.

### H.6 — Per-Candidate Attribution Repair / Closeout
**This commit**

- H.5 blocker: `process_discovery_payload()` overwrote all candidates' `source_channel`
  with the primary request's channel, collapsing multi-channel attribution.
- Fix: stamp each normalized candidate with `source_response_id` during the plan loop.
- Persistence replaced with a grouping step: `accepted` candidates are grouped by
  `(source_channel, source_channel_reason, source_response_id)` before calling
  `process_discovery_payload()` once per group with the correct per-group channel params.
- Per-request `candidates_persisted` count updated per group for accurate `source_budget_report`.
- No schema change required. No changes to `process_discovery_payload()` internals.

---

## 3. What V2-2H Improved

| Area | Before V2-2H | After V2-2H |
|---|---|---|
| Candidate intake cap | Hard-stuck at 1–3 | Configurable 1–50 (default 10) |
| Stage visibility | Single count | Seen / normalized / persisted / rejected separated |
| Age/activity signal | None | Age buckets + activity buckets + recent-active tiers |
| Fast-event fields | Missing (100% gap in live audit) | Captured and derived where available |
| A2 gate logic | Accidentally correct via `_f()`=0.0 | Explicit `price_change_5m is not None` guard |
| A3 gate logic | Accidentally correct via `_f()`=0.0 | Explicit `token_age_seconds is not None` guard |
| Failed pump helper | Missing | `derive_failed_pump_bucket()` available |
| Within-response dups | Silent persistence | Filtered before selection |
| Within-response STNP | Silent persistence | Blocked or migrated through V2-2C gates |
| Source request count | Always 1 | Configurable 1–10 via plan catalog |
| Source budget reporting | None | `source_budget_report` with per-channel metrics |
| Multi-channel attribution | All persisted under primary channel | Each candidate persists with its actual channel |

---

## 4. What Remains Deferred

**A4 main-path integration:** `derive_failed_pump_bucket()` exists as a helper but is not
wired into `assign_bucket()`. `assign_bucket()` is a pure function of a single candidate;
A4 requires prior candidate context. Integration requires a call site where prior context
is available. This is deferred to a future slice.

**REVIVAL / DISTINCT_EVIDENCE STNP classification:** Within-response and cross-response STNP
classification for these labels requires querying the DB for prior token history. This external
context is not available in the current per-response filter path. Conservative unresolved
treatment applies.

**PumpPortal / PumpSwap live WebSocket plumbing:** Both sources are NOT_READY in the plan
catalog. Live fixture transport and WebSocket connection management are required to make them
executable. Deferred to a separate mini-lane.

**Full sustained live source-budget proof:** No live proof was run under V2-2H. All tests
use fixture transports.

**V2-2I bounded proof:** Required next step. Must validate V2-2H implementation on an
isolated proof DB against real source data.

**V2-2J closeout:** Follows V2-2I proof.

**V2-3 automation design:** Paused. Does not resume until V2-2 repair is proved.

---

## 5. Money-Usefulness Contribution

V2-2H does not unlock trading or live execution. It improves the quality and diversity of
what enters the discovery pipeline, which is the foundation of everything downstream.

**Wider candidate intake:** The cap increase from 3→10 (configurable to 50) means the system
no longer silently discards most of what sources return. A wider intake is necessary before
any statistical argument about source coverage can be meaningful.

**Less old-token-only bias:** Age buckets and the A3 gate correction mean the system can
now distinguish fresh tokens from established ones without guessing from zero-valued fields.
The old code accidentally passed old tokens through A2/A3 because missing fields defaulted to
`0.0` — now missing means missing, not zero.

**Recent-active prioritization:** The recent-active tier system (`RECENT_HIGH`, `RECENT_MEDIUM`,
`RECENT_LOW`, `STALE`) gives the downstream pipeline a principled way to prefer candidates
that showed activity in the current measurement window.

**Low-volume / dead-token classification:** The DEAD and MINIMAL activity buckets expose tokens
that would waste tracking budget. They are visible in `age_activity_report` before persistence.

**Better fast-event differentiation:** `price_change_5m`, `token_age_seconds`, and related
fields now actually exist on candidates instead of being universally None. A2 (wick-reversal)
and A3 (late-buy) gates now work as designed.

**Better source/channel coverage measurement:** The `source_budget_report` tells the operator
exactly which channels were sampled, how many candidates each produced, and how many were
persisted per channel. This is the first step toward evidence-based channel diversification.

**Safer duplicate/STNP handling:** Within-response and cross-response dedup prevents silent
double-persistence of the same token or pair within a single discovery run.

**Stronger future memory diet:** A more diverse, accurately attributed candidate set produces
a better candidate pool for V2-2I proof and eventually for memory factory intake. V2-2H is
necessary groundwork, not sufficient on its own.

---

## 6. What V2-2H Does Not Unlock

V2-2H changes only the discovery pipeline intake and attribution layer. The following remain
completely locked:

- Memory generation
- Retrieval activation
- Paper decisions
- BUY / SELL / HOLD signals
- Paper positions
- Trades
- Paper trade audits
- PnL
- Live trading
- Wallet / private keys / real funds
- Paid APIs
- Scoring / ranking / confidence / weighted token logic
- Embeddings / vectors

---

## 7. V2-2I Proof Requirements

V2-2I must run on an isolated proof DB (not committed to repo) and demonstrate:

1. **Candidate cap:** bounded intake of more than 3 candidates from a real source response.
2. **`max_source_requests`:** at least 2 source requests are executed when `max_source_requests=2`.
3. **Multi-channel sampling:** more than one channel is sampled in the same run (GeckoTerminal
   new_pool + trending, or DexScreener + GeckoTerminal if a second source is wired).
4. **`source_budget_report` populated:** all keys present with non-zero `source_requests_attempted`.
5. **`candidate_stage_report` populated:** `candidates_seen_total` > 0.
6. **`age_activity_report` populated:** at least one non-UNKNOWN bucket count > 0.
7. **`field_completeness_report` populated:** missing-field counts reflect real data quality.
8. **`within_response_integrity_report` populated:** counts correct even if all zeros (clean input).
9. **Per-candidate attribution correct:** persisted rows show the actual channel they came from,
   not all collapsed to the primary channel.
10. **Batch diversity:** selection produces candidates from more than one bucket (where source
    data provides diversity). The old `{B5, B5}` result was evidence of old-only bias.
11. **Downstream locked table deltas remain zero:**
    - `printer_memory_windows`: delta = 0
    - `printer_memory_retrieval_queries`: delta = 0
    - `printer_memory_retrieval_matches`: delta = 0
    - `printer_paper_decisions`: delta = 0
    - `printer_paper_positions`: delta = 0
    - `printer_paper_trade_events`: delta = 0
    - `printer_paper_trade_audits`: delta = 0

---

## 8. Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Severity | Mitigation |
|---|---|---|
| Source budget exhaustion (too many requests per run) | Medium | `max_source_requests` cap enforced; default=1 |
| Rate limits from multi-channel sampling | Medium | Source Governor rate-limiting remains active; plan catalog controls request count |
| Multi-channel attribution regression (H.6 fix) | Low (mitigated) | 21 H.6 tests verify per-channel DB rows; 397 regression tests pass |
| Source/channel NOT_READY (PumpPortal/PumpSwap) | Low | NOT_READY items reported but not executed; no crash |
| Missing fields despite parser repair | Medium | `field_completeness_report` exposes gaps; H.3 fixes known DexScreener/GeckoTerminal paths |
| A4 not fully wired | Low | `derive_failed_pump_bucket()` helper exists; main-path integration deferred explicitly |
| External-context STNP limitations | Low | Conservative unresolved treatment documented; does not cause false persistence |
| Storage growth from wider intake | Low | `max_candidates` cap limits per-run persistence; operator controls the bound |
| Scheduler overload from more discoveries | Low | Tracking queue and scheduler jobs are created as before; intake rate is operator-controlled |
| Report hiding reject reasons | Low | `rejected_candidates` list and `within_response_integrity_report` preserve all reject reasons |
| Accidental memory/retrieval/paper unlock | None | H.1–H.6 code confirmed free of all prohibited paths; all locked table deltas tested to be zero |

---

## 9. Readiness Verdict

**V2-2H Discovery/Selection Capacity Repair Implementation: IMPLEMENTATION_COMPLETE_WITH_BLOCKERS**

Implementation is complete for all six H-slices. Tests pass (418 total across H.1–H.6
and required regression suites). All hard locks preserved.

Blockers before V2-3 can resume:
- V2-2I bounded proof on isolated proof DB must pass.
- Operator must accept V2-2I proof results.

---

## 10. Next Recommended Lane

**V2-2I — Discovery/Selection Capacity Repair Bounded Proof**

Only after operator accepts this H.6 closeout.

V2-2I runs the V2-2H implementation against a real source response on an isolated
proof DB, audits all report fields, and verifies the locked table deltas are zero.
V2-2I does not commit proof DB artifacts to the repository.
