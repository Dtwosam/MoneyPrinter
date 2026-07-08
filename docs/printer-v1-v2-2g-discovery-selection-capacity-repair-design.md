# Printer V1 — V2-2G Discovery/Selection Capacity Repair Design

**Status:** DESIGN_COMPLETE_WITH_BLOCKERS

**Date:** 2026-07-08

**Lane:** V2-2G — Discovery/Selection Capacity Repair Design

**Type:** Design/specification only. No implementation.

---

## 1. Lane Boundary

`V2-2G` is a design-only repair lane inside V2-2. It does not close V2-2 and it does
not open V2-3.

**Explicit boundary statements:**

- V2-2G is design-only. It produces a specification, not code.
- V2-2 is not being closed by this document. V2-2's status remains
  `COMPLETE_WITH_BLOCKERS` per the V2-2E closeout and the V2-2 live capacity audit.
- V2-3 is paused until this repair sequence (V2-2G design → V2-2H implementation →
  V2-2I bounded proof) is complete or the operator explicitly accepts the current
  state as sufficient.
- No implementation, runtime execution, source fetching, DB mutation, memory
  generation, retrieval activation, or paper-trading capability is unlocked by this
  document.
- No migrations are created or applied.
- No code files are edited.
- No tests are run.

**Allowed in this lane:**

- Design/specification documentation.
- Static repo inspection (read-only).
- Blocker mapping.
- Target-standard definition.
- Implementation plan for a later `V2-2H`.
- Proof plan for a later `V2-2I`.

**Not allowed in this lane:**

- Implementation.
- Migrations.
- Source fetching.
- Live discovery.
- DB mutation.
- Runtime execution.
- Scheduler execution.
- Memory generation.
- Retrieval activation.
- Paper decisions.
- BUY/SELL/HOLD.
- Paper positions.
- Trades.
- Paper trade audits.
- PnL.
- Paid APIs.
- Live wallet/private keys/real funds.
- Embeddings/vectors.
- Scoring/ranking/confidence/weighted token logic.

---

## 2. Source Stack Read

Active source stack read for this lane:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-assistant-active-build-order-anchor.md`
- `docs/printer-v1-v2-2a-discovery-selection-pipeline-audit.md`
- `docs/printer-v1-v2-2b-memory-diet-buckets-quotas-reasons-design.md`
- `docs/printer-v1-v2-2d-stnp-classification-preflight.md`
- `docs/printer-v1-v2-2d-bounded-discovery-selection-proof.md`
- `docs/printer-v1-v2-2e-discovery-selection-foundation-closeout.md`
- `docs/printer-v1-v2-2-live-discovery-selection-capacity-audit.md`

Static repo inspection performed (read-only):

- `src/printer_v1/operator_cli/commands.py` (candidate cap enforcement, lines 1356-1357)
- `src/printer_v1/operator_cli/lane_x6_discovery_selection_repair.py` (`_DEFAULT_MAX_CANDIDATES = 20`)
- `src/printer_v1/sources/registry.py` (Source Governor registry — full read)
- `src/printer_v1/sources/dexscreener.py`, `geckoterminal.py`, `pumpportal.py`, `pumpswap.py`
- `migrations/025_selection_batch.sql`
- `src/printer_v1/discovery/selection_batch.py`

**Current V2 anchor:**

- Commit: `122c15b Adopt V2 memory growth build order`
- Tag: `printer-v1-memory-growth-build-order-v2-adoption`

**Current V2-2 live audit anchor:**

- Commit: `01cba36 Add V2-2 live discovery selection capacity audit`

---

## 3. Why V2-2 Needs Repair

The live audit (`01cba36`) measured Printer's real governed discovery path with one
operator-approved source request against GeckoTerminal's new-pool channel. The numbers:

| Metric | Result |
|--------|-------:|
| Candidates discovered/inspected | 20 |
| Candidates persisted | 3 |
| Candidates rejected before persistence | 17 |
| Rejection reason for 9 of the 17 | `max_candidates_reached` (cap, not quality) |
| Candidates considered for selection | 3 |
| Candidates selected | 2 |
| Candidates quota-rejected | 1 |
| Final quota result | PASS |
| Source/channel sampled | GeckoTerminal `GECKOTERMINAL_NEW_POOL` only |
| Final selected batch composition | 2× B5 (CONSOLIDATION) — nothing else |

**Why this is not close to perfect:**

1. **The system saw 20 candidates and kept 3.** Nine of the 17 rejections were purely
   an artifact of a hardcoded 1-3 candidate cap (`commands.py:1356-1357`), not a
   quality judgment. Printer discarded real, otherwise-trackable Solana candidates
   because of an arbitrary command-level limit, not because those candidates were bad
   learning examples.
2. **Only one source and one channel were sampled.** GeckoTerminal's new-pool channel
   is a narrow slice of the Solana memecoin universe. DexScreener, PumpPortal launch
   streams, PumpPortal migration streams, and PumpSwap post-migration confirmation
   were never sampled. A single-channel intake cannot claim broad discovery.
3. **All 20 candidates were missing the fields needed for fast-event differentiation** —
   `token_created_at`, `pair_created_at`, `token_age_seconds`, `pair_age_seconds`,
   `price_change_5m`, `price_change_15m`, `price_change_1h`, `price_change_24h`, and
   `volume_15m` were all 100% absent. Without these fields, A2 (WICK_ONLY_PUMP) and A3
   (LATE_BUY_TRAP) cannot be derived from real data, and no A4 (FAILED_PUMP) branch
   exists in `assign_bucket()` at all. Only A1 is currently reachable from live data.
4. **The final selected batch was two consolidation candidates and nothing else.**
   A memory diet of `{B5, B5}` teaches Printer almost nothing about fast pumps, traps,
   dead tokens, revivals, migrations, or liquidity dynamics. It is safe (no bias toward
   winners) but it is not learning-useful at scale.

**Why weak discovery/selection specifically hurts learning value:**

- **Old tokens like BONK, WIF, WEN dominate when data is clean but stale.** These
  tokens have massive historical liquidity and easy-to-parse market data, so a naive
  discovery/selection system will over-sample them simply because their data is
  reliable, not because they teach anything about current Solana memecoin launch
  behavior. A corpus dominated by BONK/WIF/WEN teaches "old, established token
  behavior," which is a different (and less useful) lesson than "what a fresh
  memecoin launch looks like in its first hours and days."
- **Very low-volume tokens are trivially easy to discover but teach little unless
  explicitly used as negative/dead-token examples.** If selection does not
  categorically route them to LOW_ACTIVITY/DEAD_TOKEN/WATCH_ONLY buckets, they either
  get excluded entirely (wasted discovery effort) or accidentally treated as normal
  learning examples (diluted corpus).
- **One-source candidates cannot prove Printer sees the real market.** If GeckoTerminal
  new-pool is the only channel sampled, Printer's "discovery" is really "GeckoTerminal's
  new-pool discovery," which is a narrower and potentially biased subset (e.g.,
  GeckoTerminal's indexing lag, coverage gaps, or channel-specific filtering).
- **One-bucket batches (all B5) cannot fulfill the V2-2B quota design's intent.** The
  V2-2B quotas exist specifically to force diversity — dead tokens, traps, decay,
  liquidity events. A batch that only clears quota because it happens to contain two
  neutral consolidation tokens is technically valid but represents the narrowest
  possible passing case, not a healthy corpus.
- **Tokens with clean data but weak current learning value crowd out tokens with dirty
  data but high learning value.** A fresh 2-hour-old token with a wick-only pump and
  incomplete field data teaches more about trap avoidance than a perfectly clean but
  6-month-old, quiet BONK snapshot. If selection cannot reach fresh tokens because the
  discovery cap stops at 3, or cannot classify wick-only patterns because
  `price_change_5m` is missing, that high-value lesson never enters the corpus.

---

## 4. Definition of "Near-Perfect" for V1

This section defines a measurable, achievable standard. It does not require
impossible perfection (e.g., 100% Solana memecoin universe coverage, real-time
completeness, or zero missing fields under all conditions).

Printer's discovery/selection is **near-perfect for V1** when all of the following are
true and provable through an auditable bounded proof:

| Standard | Definition |
|----------|-----------|
| Candidate universe is measured | Every discovery run reports `candidates_seen_total`, not just persisted count |
| Source/channel coverage is reported | Every run reports which sources/channels were sampled and which were not, with reasons |
| Token age coverage is reported | Every run reports the age-bucket distribution of the candidate pool (Section 6) |
| Activity coverage is reported | Every run reports the activity-bucket distribution of the candidate pool (Section 7) |
| Candidate cap is configurable and bounded | Cap is a parameter with a safe validated range, not hardcoded at 3 |
| Discovery can include any launch age | Discovery eligibility does not filter by token age; broad intake is the discovery-layer default |
| Selection prioritizes recently launched active tokens | Selection priority policy (Section 11) actively prefers 0-24h through 14-28d active tokens |
| Selected batch is not forced from tiny biased intake | Selection batch size and diversity scale with a realistic candidate pool, not a 3-candidate ceiling |
| Field completeness is sufficient for A1/A2/A3/A4 | `price_change_5m`, `token_age_seconds` (or equivalents) are present for a meaningful share of candidates, enabling real A2/A3 differentiation; A4 has a defined derivation path |
| Same-response duplicate/STNP handling is safe | Within-response mint/pair duplicates are detected and resolved before persistence, not just across historical DB rows |
| Rejects are visible | Every rejected candidate — pre-persistence and at selection — carries a specific, auditable reason |
| No hidden scoring/ranking/confidence/BUY probability exists | All bucket, age, and activity classification remains categorical; static/risky-language scans confirm this |
| Lock preservation remains proven | Every proof run shows zero deltas on memory windows, retrieval matches, paper decisions, paper positions, trade events, paper trade audits |

This standard is achievable without paid APIs, without bypassing Source Governor or
Central Scheduler, and without introducing any scoring/ranking/confidence logic. It is
a coverage-and-visibility standard, not a prediction-accuracy standard.

---

## 5. Discovery vs Selection

### 5.1 Discovery Eligibility — Broad

Discovery eligibility must not filter by launch age. Printer must be able to discover
and record (subject to Source Governor budget and validation) candidates across the
full age spectrum:

- Fresh launches (seconds to minutes old)
- 0-24h tokens
- 1-7d tokens
- 7-14d tokens
- 14-28d tokens
- 28d+ older tokens
- Legacy tokens (BONK, WIF, WEN, and similar long-established Solana memecoins)
- Dead tokens
- Revival tokens
- Migration tokens
- Low-volume tokens
- High-activity tokens

Discovery's job is to see broadly and record what it sees, categorically labeled, with
every candidate's fate (persisted, rejected-pre-persistence, capped-out) visible in the
run report. Discovery does not decide what is "useful" — that judgment belongs to
selection.

### 5.2 Selection Priority — Narrower and More Useful

Selection is the layer that decides what enters a bounded memory-growth batch. Selection
should prioritize:

- Recently launched active tokens (0-24h, 1-7d, 7-14d, 14-28d bands — Section 6).
- Tokens with usable liquidity (categorical liquidity threshold, not a score).
- Tokens with meaningful volume/transaction activity (categorical activity threshold —
  Section 7).
- Tokens showing price/liquidity/volume behavior useful for memory learning (fast
  pumps, wick-only reversals, late-buy traps, failed pumps, decay, consolidation,
  liquidity shifts).
- Migration/revival behavior where useful (D2/D3 buckets from V2-2B).
- Failure/trap/dead-token examples where useful (A2/A3/A4/D1 buckets from V2-2B).

Selection should not simply mirror the discovery pool. It applies the V2-2B/V2-2C
quota rules, and it applies the new age/activity priority rules defined in this
document (Section 11), before a candidate enters a bounded batch.

### 5.3 Older/Legacy Token Role

Older/legacy tokens (BONK, WIF, WEN, and similar) may still be discovered and
classified. They must not dominate selection only because their data is clean and
easy to parse. Their intended memory-diet role is:

- **Baseline/reference case** — establishing what "normal, established, high-liquidity
  token behavior" looks like, as a comparison point.
- **Revival case** — when an older token shows a genuine new activity spike after
  dormancy (D2 REVIVAL bucket).
- **Liquidity/volume comparison case** — providing a stable reference point against
  which fresh-launch liquidity/volume patterns can be contrasted in future memory
  review (not scored, just categorically distinct).
- **Older active-token case** — when an older token is currently showing meaningful
  activity, it is still a valid B-group (normal-activity) or A-group (fast-event)
  candidate, just capped in quantity (Section 11).
- **Market-structure example** — teaching what deep, mature liquidity structure looks
  like versus shallow, fresh-launch liquidity.

### 5.4 Very Low-Volume Token Role

Tokens with very low 24h volume (informal reference threshold: **under approximately
$200 in 24h volume**) should remain discoverable. Selection should usually classify
them into one of:

- `LOW_ACTIVITY`
- `DEAD_TOKEN`
- `WATCH_ONLY`
- `NEGATIVE_LEARNING`
- `UNREALISTIC_EXIT`
- `NO_REAL_MARKET_DEPTH`

...unless the candidate shows meaningful new activity (a fresh volume/liquidity spike,
a revival signal, or migration event), in which case it is re-evaluated under the
activity-bucket rules in Section 7 rather than being locked into a low-activity label.

These categorical labels map onto existing V2-2B buckets (D1 DEAD_TOKEN, existing
WATCH_ONLY lane, existing E2 UNREALISTIC_EXIT) plus two new labels this design
introduces for V2-2H: `NEGATIVE_LEARNING` (a general tag for confirmed-poor-outcome
tokens usable for AVOID-style counterfactual memory) and `NO_REAL_MARKET_DEPTH` (a tag
for tokens whose liquidity is too thin to represent a realistic paper-exit scenario,
distinct from D1 dead-token in that the token may still show nominal transaction
activity without any real depth).

---

## 6. Required Age Buckets

| Bucket ID | Definition | Discovery eligibility | Selection priority | Memory-learning role | Cap/quota guidance | Reporting requirement |
|-----------|-----------|----------------------|--------------------|-----------------------|--------------------|-----------------------|
| `AGE_0_24H` | Token/pair first seen 0-24 hours before discovery moment | Always eligible | **Highest** priority tier | Fresh-launch behavior, initial pump/trap/wick patterns, earliest liquidity formation | No hard cap; primary supply source for Group A fast-event buckets | Report count and % of candidate pool |
| `AGE_1_7D` | First seen 1-7 days before discovery moment | Always eligible | **High** priority tier | Early follow-through, first-week survival/decay, early migration signals | No hard cap; primary supply source for Group A/B buckets | Report count and % of candidate pool |
| `AGE_7_14D` | First seen 7-14 days before discovery moment | Always eligible | **High** priority tier | Continuation vs. decay, mid-life liquidity trend, early revival signals | No hard cap; supply source for Group B/C buckets | Report count and % of candidate pool |
| `AGE_14_28D` | First seen 14-28 days before discovery moment | Always eligible | **Medium-high** priority tier (still within the "recent" window) | Late-cycle survival, established-but-still-recent behavior, migration confirmation | No hard cap; supply source for Group B/C/D buckets | Report count and % of candidate pool |
| `AGE_28D_PLUS` | First seen more than 28 days before discovery moment | Always eligible | **Low** priority tier unless showing D2 REVIVAL or D3 MIGRATION signal | Baseline/reference, revival, liquidity/volume comparison, older active-token, market-structure examples (Section 5.3) | Soft cap: no more than 2 per batch of 6+ items unless serving REVIVAL/MIGRATION/baseline role explicitly | Report count, % of pool, and how many were selected under which role label |
| `AGE_UNKNOWN` | `token_created_at`/`pair_created_at` absent or unparseable | Always eligible (discovery must not reject on missing age field) | **Deprioritized but not excluded** — treated as lowest-confidence age tier, ranked below `AGE_28D_PLUS` for priority purposes, never above it | Still usable if activity bucket is strong (Section 7); age-unknown tokens with high observable activity can still enter selection under activity-based rules | No hard cap, but selection must log an explicit `AGE_UNKNOWN_ACTIVITY_OVERRIDE` reason if selected primarily on activity signal | Report count and % of pool; this becomes the primary metric proving whether the missing-field repair (Section 9) is working |

**Design note:** "Recently launched" for V1 spans `AGE_0_24H` through `AGE_14_28D` —
the present moment back through roughly 2-4 weeks. This matches the operator's stated
standard. The highest memory-learning priority sits inside this window, conditional on
the token showing meaningful observable activity per Section 7. Age alone is not
sufficient for selection priority — a fresh but completely dead token is still
`ACTIVITY_DEAD` and routes to Section 5.4's low-activity classification regardless of
age.

---

## 7. Required Activity Buckets

All activity-bucket classification is categorical threshold-based. No scores, ranks,
confidence percentages, or weighted sums are used.

| Bucket ID | Definition | Observable-data thresholds (categorical) |
|-----------|-----------|-------------------------------------------|
| `ACTIVITY_HIGH` | Strong current market activity | `liquidity_usd >= $5,000` AND (`volume_5m >= $1,000` OR `txns_5m >= 10`) — matches existing V2-2C fast-tier gate |
| `ACTIVITY_MEDIUM` | Meaningful but not fast-tier activity | `liquidity_usd >= $1,000` AND `volume_24h > $200` AND NOT `ACTIVITY_HIGH` |
| `ACTIVITY_LOW` | Present but weak activity | `volume_24h` between approximately $10 and $200, OR liquidity between $500 and $1,000 with minimal transaction count |
| `ACTIVITY_DEAD` | Effectively no activity | `volume_5m <= 0` AND `txns_5m <= 0` AND `volume_1h <= 0` AND `txns_1h <= 0` AND `volume_24h <= $10` AND `txns_24h <= 2` — matches existing V2-2C `is_near_dead` gate |
| `ACTIVITY_REVIVING` | Was previously dead/low/archived, now showing a new activity signal | Prior lifecycle state was `ARCHIVED`/`COOLDOWN`/`ACTIVITY_DEAD`, AND current payload shows `volume_5m > 0` OR `txns_5m > 0` OR a liquidity increase versus the last known snapshot |
| `ACTIVITY_UNKNOWN` | Insufficient fields to classify | Core fields (`volume_24h`, `liquidity_usd`, `txns_5m`) are missing or null |

**Inputs considered (categorical, not weighted):**

- 24h volume
- 1h volume
- 15m volume (where available — currently 100% missing per live audit; see Section 9)
- 5m volume
- Transaction counts (5m, 1h, 24h)
- Buy/sell counts where available (not currently normalized; flagged as future field)
- Liquidity (current level and, where sequential snapshots exist, liquidity movement)
- Price movement (5m/15m/1h/24h price change — currently 100% missing; see Section 9)
- Liquidity movement (rising/falling/removed — existing C1/C2/C3 buckets)
- Volume/liquidity relationship (categorical ratio band, e.g., "volume exceeds
  liquidity" vs. "volume is a small fraction of liquidity" — no numeric ratio score
  stored, only a categorical label)
- Route/quote availability (reserved for future paper-exit-realism checks via the
  `jupiter_quote` source, restricted to `paper_quote_realism` request kind — not used
  for activity classification in V2-2G/V2-2H; explicitly deferred)

**Special handling:**

| Case | Handling |
|------|----------|
| Under $200 24h volume | Routes to `ACTIVITY_LOW` or `ACTIVITY_DEAD` per thresholds above; never routes to `ACTIVITY_HIGH`/`ACTIVITY_MEDIUM` regardless of other fields, unless a `ACTIVITY_REVIVING` override applies |
| Low liquidity (below $500) | Existing V2-2C `C3 LIQUIDITY_REMOVED` bucket takes precedence in bucket assignment; activity bucket is set to `ACTIVITY_LOW` or `ACTIVITY_DEAD` as a secondary classification alongside the primary bucket |
| No recent transactions (5m/1h both zero) but nonzero 24h volume | Classified `ACTIVITY_LOW`, not `ACTIVITY_DEAD` — distinguishes "quiet right now" from "confirmed dead" |
| Sudden revived activity | `ACTIVITY_REVIVING` takes precedence over `ACTIVITY_LOW`/`ACTIVITY_DEAD` when the lifecycle-state + new-signal condition is met; this is the primary feed for D2 REVIVAL bucket candidates |
| Fresh launch with low 24h history but strong 5m/15m activity | `ACTIVITY_HIGH` is reachable purely from 5m/liquidity fields — the 24h window is not required to be populated for a fresh token to qualify, since a token minutes old cannot have 24 hours of history. This is a required design point: activity classification must not penalize freshness by demanding a full 24h window. |

---

## 8. Repair Area A: Candidate Cap and Discovery Capacity

**Current state:** `commands.py:1356-1357` hard-validates `max_candidates` to the
range 1-3. `lane_x6_discovery_selection_repair.py` already supports a configurable
`_DEFAULT_MAX_CANDIDATES = 20` in its own selection-repair path, proving a wider cap is
technically already used elsewhere in the codebase — the operator discovery command is
the narrow point.

**Design for V2-2H implementation:**

- Replace the hardcoded 1-3 range with a **bounded, configurable** `max_candidates`
  parameter. Suggested safe validated range: 1-50, with a documented default (e.g.,
  10) that is higher than 3 but still conservative.
- Add a **bounded, configurable** `max_source_requests` parameter, separate from
  `max_candidates`. Currently one invocation means one request; this must become an
  explicit, capped parameter (e.g., 1-10 requests per invocation) so multi-channel
  sampling (Repair Area B) is possible within one bounded run.
- Add a **bounded max runtime** parameter (wall-clock budget for the whole discovery
  invocation, not just the per-request transport timeout). This prevents an
  unbounded-duration run even if source responses are slow.
- Preserve **source budget limits** — rate limits per source remain governed by
  `src/printer_v1/sources/registry.py` (`default_rate_limit_per_minute` per source).
  The new `max_source_requests` cap must never be set higher than what the governed
  rate limit allows within the bounded runtime window.
- Preserve **`--operator-approved` flag** requirement — no cap increase removes the
  operator-approval gate.
- Preserve **proof DB default** for any experimental/expanded-cap testing. Any run
  using a cap above the previously-validated 1-3 range should default to writing to a
  proof DB copy until the operator explicitly approves a wider cap against the live DB.
- **No unbounded discovery** — every parameter (`max_candidates`, `max_source_requests`,
  max runtime) must have a hard validated ceiling. None may be left uncapped.
- **Separation of counted stages** — the run report must separately count and report:
  - `candidates_seen_total` (every row returned by the source response)
  - `candidates_normalized_total` (rows that passed field parsing/normalization)
  - `candidates_persisted_total` (rows written to `printer_discovery_candidates`)
  - `candidates_rejected_pre_persistence` (rows normalized but not persisted, with
    per-row reason — e.g., `max_candidates_reached`, `watch_only_not_eligible`,
    `stale_source_data`, `chain_not_solana`)
  - `candidates_considered_for_selection` (rows handed to the V2-2C selection module)
  - `candidates_selected` (rows that passed all selection gates and quota)
  - `candidates_rejected_by_selection` (rows considered but not selected, with reason)

This six-stage separation already exists conceptually in the V2-2D proof script and the
live capacity audit report; V2-2H's job is to make it a first-class, always-reported
part of the operator command output, not just a one-off proof artifact.

---

## 9. Repair Area B: Multi-Source/Channel Coverage

**Current state:** Only GeckoTerminal's `GECKOTERMINAL_NEW_POOL` request kind has been
exercised in the live audit. `src/printer_v1/sources/registry.py` already defines a
much wider governed surface.

**Governed sources currently registered (from `registry.py`, read-only inspection):**

| Source | Allowed request kinds | Priority class | Current live-audit usage |
|--------|----------------------|-----------------|---------------------------|
| `dexscreener` | `token_discovery`, `pair_market_snapshot`, `token_market_snapshot`, `boosted_token_reference` | `token_level` | Historically used for other discovery rows in the DB; not sampled in the live capacity audit |
| `geckoterminal` | `geckoterminal_new_pool_discovery`, `geckoterminal_trending_pool_reference` | `discovery` | Only `geckoterminal_new_pool_discovery` sampled |
| `pumpportal` | `pumpfun_launch_stream`, `pumpfun_migration_stream` | `discovery` | Not sampled |
| `pumpswap` | `pumpswap_pool_confirmation`, `pumpswap_migration_pool_reference`, `pumpswap_liquidity_reference` | `discovery`, read-only confirmation only | Not sampled |
| `solana_rpc` | `onchain_reference`, `mint_account_reference`, `pool_reference`, `holder_concentration_reference` | `token_level` | Not sampled; free/user-supplied RPC only |
| `helius_free` | `onchain_reference`, `mint_account_reference`, `pool_reference` | `token_level` | Not sampled; free-tier optional |
| `jupiter_quote` | `paper_quote_realism` | `paper_realism`, restricted to paper simulation only | Not sampled; reserved for future paper-exit-realism, never execution |

**Design for V2-2H implementation:**

- Extend the discovery command to accept a **list of (source, request_kind) pairs** to
  sample within one bounded run, each counted separately against
  `max_source_requests`.
- Minimum multi-channel target for V2-2H/V2-2I: at least
  `geckoterminal_new_pool_discovery` **plus** `geckoterminal_trending_pool_reference`
  **plus** `dexscreener` `token_discovery` in the same bounded run, to break the
  single-channel dependency.
- `pumpportal` launch/migration streams and `pumpswap` migration confirmation are
  **future/not-ready** for V2-2H unless a governed adapter call for these already
  exists and is proven safe in a static/unit-test context first. This document marks
  them explicitly as: **future — requires adapter readiness confirmation before
  inclusion in a live bounded run.**
- `solana_rpc`/`helius_free` are marked **future/not ready for discovery use** — their
  registered purpose is onchain reference (mint account, pool reference, holder
  concentration), not primary discovery. They may support Repair Area C's field
  derivation (Section 10) in a later lane, but are out of scope for V2-2H discovery
  itself.
- `jupiter_quote` is explicitly **out of scope for V2-2G/V2-2H discovery or selection.**
  It is reserved for a future paper quote/exit-realism lane and is restricted by its
  own registry `restriction: paper_simulation_only` field. It must never be used for
  execution and must not influence discovery/selection classification.
- **No new paid APIs are introduced.** Every source above is already `dependency_type`
  free_public, free_or_user_supplied, or free_tier_optional in the existing registry.
  This design adds no new registry entries.
- **No Source Governor bypass.** Every additional source/channel call in V2-2H must go
  through `execute_source_request_with_governor()` (the same governed path used in the
  live audit), with `printer_source_requests`/`printer_source_responses`/
  `printer_source_failures` trace rows recorded exactly as today.
- **Coverage reporting requirement:** every run report must state, for each governed
  source/channel in the registry, one of: `SAMPLED (count)`, `NOT_SAMPLED_THIS_RUN`, or
  `NOT_READY (reason)`. This directly answers the live audit's "source/channel blind
  spots" finding with an explicit, auditable per-source status rather than silence.

---

## 10. Repair Area C: Missing Normalized Fields

The live audit found 100% missing rates for 9 fields across all 20 sampled candidates.
This section specifies capture/derivation/fallback for each.

| Field | Source field if available | Derived calculation if available | Fallback if unavailable | Blocks A2/A3/A4? | Appears in report metrics? |
|-------|---------------------------|-----------------------------------|--------------------------|-------------------|------------------------------|
| `token_created_at` | GeckoTerminal pool/token attributes may expose a `pool_created_at`/`base_token` creation timestamp not currently parsed by the adapter; DexScreener `pairCreatedAt` field is a known available field on DexScreener pair responses | If token-level creation timestamp is unavailable but pair-level is, use `pair_created_at` as a proxy with an explicit `derived_from_pair` flag | `null`; candidate routes to `AGE_UNKNOWN` | Blocks A3 only indirectly (A3 depends on `token_age_seconds`, derived from this field) | Yes — missing-field % must be reported per run |
| `pair_created_at` | DexScreener `pairCreatedAt` (documented public field, not currently parsed); GeckoTerminal pool attributes | None beyond direct capture | `null`; candidate routes to `AGE_UNKNOWN` | No direct A2/A3/A4 dependency, but feeds `pair_age_seconds` | Yes |
| `token_age_seconds` | Derived: `discovery_moment - token_created_at` | Derived only; not a raw source field | If `token_created_at` is null, fallback to `pair_age_seconds` if available; else `null` and candidate routes to `AGE_UNKNOWN` | **Yes — required for A3 LATE_BUY_TRAP** (`token_age_seconds >= 3600 AND price_change_1h < 0` in existing `assign_bucket()`) | Yes |
| `pair_age_seconds` | Derived: `discovery_moment - pair_created_at` | Derived only | If `pair_created_at` is null, `null`; candidate routes to `AGE_UNKNOWN` | No direct block, but needed for STNP migration/pair-drift timing analysis | Yes |
| `price_change_5m` | DexScreener `priceChange.m5` (documented field, not currently parsed on this path); GeckoTerminal pool attributes may expose short-window price change | None reliable; must be sourced, not derived, for a 5-minute window | `null`; candidate cannot qualify for A2 via price-change path (bucket assignment falls to A1 default) | **Yes — required for A2 WICK_ONLY_PUMP** (`price_change_5m <= -20.0 AND volume_5m >= 1000`) | Yes |
| `price_change_15m` | Not a standard DexScreener/GeckoTerminal top-level field in most public responses; may require aggregation from sequential snapshots | Derived from two sequential normalized payloads for the same pair, if a prior snapshot exists (`(price_now - price_15m_ago) / price_15m_ago`) | `null` if no prior snapshot exists; does not block any current bucket rule (no bucket currently keys on `price_change_15m` directly) | No current bucket dependency, but supports `volume_15m`-adjacent short-window activity classification | Yes |
| `price_change_1h` | DexScreener `priceChange.h1` (documented field, not currently parsed on this path); GeckoTerminal pool attributes | None reliable beyond direct capture | `null`; candidate cannot qualify for A3 via the `price_change_1h < 0` clause, and cannot qualify for existing C1/C2 liquidity-trend rules that also key on `price_change_1h` | **Yes — required for A3 LATE_BUY_TRAP**, and for existing C1/C2 rules | Yes |
| `price_change_24h` | DexScreener `priceChange.h24` (documented field, not currently parsed on this path) | None reliable beyond direct capture | `null`; no current bucket rule keys directly on this field, but it supports future B-group volume/price correlation labels | No current direct block | Yes |
| `volume_15m` | Not a standard top-level DexScreener/GeckoTerminal field; would require either a dedicated request kind or derivation from sequential 5m snapshots | Derived by summing three sequential `volume_5m` snapshots if available; otherwise unavailable | `null`; no current bucket rule keys directly on `volume_15m` | No current direct block | Yes |

**General repair principle:** for fields with a plausible direct source field
(`price_change_5m`, `price_change_1h`, `price_change_24h`, `pair_created_at`), the
V2-2H implementation should extend the relevant adapter's parser
(`src/printer_v1/discovery/parser.py` plus the source-specific adapter files) to
capture and pass through the field from the raw source payload into
`normalized_candidate_payload_json`. For fields with no reliable direct source field
(`price_change_15m`, `volume_15m`, and `token_age_seconds`/`pair_age_seconds` when the
creation timestamp itself is unavailable), the repair uses a documented derivation
formula against sequential snapshots or timestamps, with an explicit `null` fallback
and an explicit `AGE_UNKNOWN`/`ACTIVITY_UNKNOWN` routing rather than silently
defaulting to zero (the current behavior, which incorrectly makes every missing field
look identical to "confirmed zero activity").

**Critical correction to current behavior:** today, `assign_bucket()`'s `_f()` helper
converts a missing field to `0.0`, which is indistinguishable from a field that is
genuinely zero. This means a token with unknown `price_change_5m` and a token with a
confirmed flat `price_change_5m = 0.0` are currently treated identically. V2-2H should
introduce an explicit "field known and zero" vs. "field unknown" distinction at the
normalization layer (e.g., a companion `*_is_known` boolean or a sentinel that is
checked before falling back to 0.0), so that `AGE_UNKNOWN`/`ACTIVITY_UNKNOWN` routing
is honest rather than silently masked as a normal zero value.

---

## 11. Repair Area D: A1/A2/A3/A4 Fast-Event Differentiation

All rules remain categorical threshold gates. No scoring, ranking, confidence, BUY
probability, or weighted decision logic. All rules are based on **current observable
market behavior**, not token popularity, name recognition, or historical reputation.

| Bucket | Existing rule (from `selection_batch.py`) | V2-2H repair status |
|--------|--------------------------------------------|----------------------|
| A1 `FAST_PUMP_FOLLOW` | `liquidity_usd >= $5,000 AND (volume_5m >= $1,000 OR txns_5m >= 10)`, and none of A2/A3 conditions are met | Already implemented and reachable from live data; remains the default fast-tier bucket when A2/A3 fields are unavailable |
| A2 `WICK_ONLY_PUMP` | `price_change_5m <= -20.0 AND volume_5m >= $1,000` (evaluated only within the A-tier gate) | Currently unreachable from live data because `price_change_5m` is 100% missing. Repaired once Section 10's `price_change_5m` capture lands. No rule change needed — only the missing-field repair is required. |
| A3 `LATE_BUY_TRAP` | `token_age_seconds >= 3600 AND price_change_1h < 0` (evaluated only within the A-tier gate) | Currently unreachable because both `token_age_seconds` and `price_change_1h` are 100% missing. Repaired once Section 10's `token_age_seconds` and `price_change_1h` capture lands. No rule change needed. |
| A4 `FAILED_PUMP` | **No return branch exists in current `assign_bucket()`.** This is a genuine implementation gap, not just a missing-field gap. | **New categorical rule required for V2-2H:** A4 should fire when a candidate previously qualified as A1/A2/A3 in an earlier discovery cycle for the same token/pair (i.e., a prior `printer_discovery_candidates` row exists with an A-tier bucket) AND the current normalized payload shows the token has fallen out of the A-tier gate (`liquidity_usd < $5,000` OR (`volume_5m < $1,000` AND `txns_5m < 10`)) AND liquidity has not been fully removed (excludes C3). Categorically: **"was fast-tier, is no longer fast-tier, and did not die."** This requires access to the token's prior discovery-candidate history at bucket-assignment time, which the current `assign_bucket()` function signature does not accept (it only takes the current candidate dict). V2-2H must extend the function signature (or add a wrapping function) to accept optional prior-candidate context. |

**Design constraint carried forward:** none of A1/A2/A3/A4 may be expressed as a
probability, a "likely a pump" label, or any BUY-adjacent signal. They remain
descriptive market-behavior categories used purely for memory-diet classification.

---

## 12. Repair Area E: Recently Launched Active-Token Priority

**Policy name:** `RECENT_ACTIVE_PRIORITY`

This is a **categorical priority tier system**, not a score. It determines the order in
which selection considers candidates for batch inclusion, and it determines quota
caps — it never determines inclusion by numeric comparison of two candidates' "quality."

### Priority tiers (highest to lowest)

1. **Tier 1 — Recent + High/Medium activity:** `AGE_0_24H` through `AGE_14_28D` AND
   `ACTIVITY_HIGH` or `ACTIVITY_MEDIUM`. These candidates are considered first for
   Group A/B/C bucket slots.
2. **Tier 2 — Recent + Reviving activity:** `AGE_0_24H` through `AGE_14_28D` AND
   `ACTIVITY_REVIVING`. Considered next; feeds D2 REVIVAL bucket.
3. **Tier 3 — Older + High/Medium/Reviving activity:** `AGE_28D_PLUS` AND
   (`ACTIVITY_HIGH`, `ACTIVITY_MEDIUM`, or `ACTIVITY_REVIVING`). Eligible but
   quota-capped per Section 6 (soft cap of 2 per batch of 6+ unless serving an
   explicit baseline/revival/migration role).
4. **Tier 4 — Any age + Low/Dead activity:** Routed to the low-activity/dead-token
   classification path (Section 5.4) rather than competing on age priority; these fill
   the mandatory D1/low-activity quota slots (V2-2B Section 5), not the "active token"
   slots.
5. **Tier 5 — `AGE_UNKNOWN` + `ACTIVITY_UNKNOWN`:** Lowest priority; only selected if
   no better-classified candidate is available to fill a required quota slot, and
   always flagged with an explicit `UNKNOWN_FIELDS_FALLBACK_SELECTION` reason.

### Policy requirements

- **Prioritize 0-24h, 1-7d, 7-14d, and 14-28d active tokens.** Tier 1/2 candidates are
  drawn from selection first when filling Group A/B/C/D2 slots.
- **Avoid old tokens dominating just because data is clean.** Tier 3 is explicitly
  capped (Section 6's `AGE_28D_PLUS` soft cap), regardless of how clean or complete
  their data is. A clean BONK snapshot does not outrank an incomplete fresh-launch
  snapshot for priority purposes — it is simply a different tier with its own cap.
- **Preserve some older/dead/revival/low-volume tokens for learning.** The V2-2B quota
  rules (D1 dead-token minimum, WATCH_ONLY minimum) remain in force and are not
  overridden by the recency policy. Recency priority governs which candidates are
  *preferred* within an otherwise-eligible pool, not which quota slots must be filled.
- **Cap old-token/reference examples.** Enforced via the `AGE_28D_PLUS` soft cap
  (Section 6).
- **Cap dead/low-volume examples.** Enforced via the existing V2-2B/V2-2C bucket
  quota max percentages (e.g., D1 max 20% of batch per the V2-2B consolidated bucket
  table).
- **Report when recent active candidates are unavailable.** If Tier 1/2 candidates are
  insufficient to fill available Group A/B/C/D2 slots, the run report must explicitly
  state `RECENT_ACTIVE_CANDIDATES_INSUFFICIENT` with the count found versus the count
  needed, rather than silently falling back to Tier 3+ without disclosure.
- **Avoid forcing a bad recent token into selection just because it is recent.** A
  Tier 1 candidate that is `ACTIVITY_DEAD` does not get artificially promoted — it
  still routes through the low-activity/dead-token classification (Section 5.4) and
  fills a D1/low-activity quota slot, not an "active recent token" slot. Recency alone
  never overrides the activity-bucket classification.

---

## 13. Repair Area F: Within-Response Duplicate/STNP Handling

**Current state (from live audit):** two of the 20 source candidates in the single
GeckoTerminal response shared one mint across different pair addresses. Only one was
eligible for persistence (the other stayed WATCH_ONLY), so no unresolved STNP case
entered the V2-2C batch in that run — but the audit flagged this as a **structural
risk**, not a proven-safe path, because the one-shot persistence selector compares
against the pre-run DB state, not a set updated after each accepted candidate within
the same response.

**Design for V2-2H implementation:**

- **Duplicate `token_mint` within one source response:** before persistence, group all
  normalized candidates in the current response batch by `token_mint`. If more than one
  row shares a mint, apply the existing V2-2B same-token/new-pair classification rules
  (Section 7 of `printer-v1-v2-2b-memory-diet-buckets-quotas-reasons-design.md`)
  **within the response**, before any row from that mint group is persisted. This
  closes the gap where the current selector only checks against historical DB state.
- **Duplicate `pair_address` within one source response:** if the same `pair_address`
  appears twice in one response (a source data anomaly), reject the second occurrence
  outright with `rejection_reason = PAIR_DUPLICATE` — this is not an STNP case, it is a
  malformed/duplicate source row.
- **Same mint/new pair in same response:** classify using the same five STNP
  categories from V2-2B (`MIGRATION`, `REVIVAL`, `PAIR_DRIFT`, `DUPLICATE_RECYCLE`,
  `DISTINCT_EVIDENCE`), applied at within-response persistence time rather than only at
  later selection time. If the within-response evidence is insufficient to classify
  confidently (e.g., no creation timestamp to establish which pair is older), the pair
  is marked `UNRESOLVED` and **neither** row from that mint group is persisted in the
  same run — consistent with the existing V2-2D preflight precedent of blocking
  UNRESOLVED STNP cases from entering any batch.
- **Migration vs revival vs duplicate recycle vs unresolved STNP:** the classification
  logic is identical to the existing `classify_same_token_new_pair()` design in
  `selection_batch.py`; V2-2H's job is to invoke it earlier — at within-response
  persistence time — not to redesign the classification rules themselves.
- **Reject/flag behavior:** every within-response duplicate/STNP event must produce a
  visible, reportable row (not a silent skip). The run report must include a
  `within_response_stnp_events` count and list, separate from the standard
  pre-persistence rejection count, so this specific risk category remains auditable
  across runs.
- **Reason fields:** reuse the existing `same_token_new_pair`,
  `same_token_new_pair_classification`, and `rejection_reason` fields already defined
  in `migrations/025_selection_batch.sql` and `selection_batch.py` — no new schema is
  required for this repair, only earlier invocation in the discovery pipeline.

---

## 14. Repair Area G: Migration 025 Readiness

**Current state (from live audit):** the copied current DB did not contain migration
025 even though V2-2C selection code depends on `printer_selection_batches` and
`printer_selection_batch_items`. The live audit applied migration 025 to the proof DB
only, as an ad hoc step, to make the run possible.

**Design for V2-2H implementation:**

- **Schema readiness check:** before any selection-batch operation runs (whether in a
  proof context or, later, a real operator command), the implementation must query
  `sqlite_master` (or equivalent) to confirm both `printer_selection_batches` and
  `printer_selection_batch_items` exist with the expected columns.
- **Migration applied check:** if the tables are absent, the command must **fail fast**
  with a clear, actionable error message (e.g., `"migration 025_selection_batch.sql
  has not been applied to this database; run the migration before selection can
  proceed"`) rather than silently creating the schema ad hoc inside a proof script.
- **Fail-fast behavior:** no operator-facing command path should auto-apply a missing
  migration as a side effect of a discovery or selection run. Migration application
  remains a distinct, explicit, operator-controlled step (via the existing
  `src/printer_v1/db/migrate.py` `apply_migrations()` path).
- **No ad hoc proof-only setup in the final operator path:** the pattern used in the
  V2-2D and live-capacity-audit proof scripts (copy DB, apply migration inline, then
  run) is acceptable for **isolated proof scripts** but must not be the production
  behavior of any real operator command in V2-2H. The real command must assume the
  live DB either already has the migration applied (verified via the readiness check)
  or refuses to run.

---

## 15. Repair Area H: Sustained Source Budgeting

**Current state:** the live audit measured exactly one source request with 0.758s
duration and 0% failure rate — a single data point. Sustained, multi-request behavior
remains unproven.

**Design for future V2-2I proof to measure:**

| Metric | What it proves |
|--------|-----------------|
| Source requests attempted | Total governed calls made across the bounded run |
| Responses received | Successful response count |
| Failures | Failed request count, broken down by failure type |
| Failure rate | `failures / attempted`, tracked per source |
| Backoff behavior | Whether `retry_after_seconds` and `max_retries` (from `registry.py`) are honored when a failure occurs mid-run |
| Candidates per request | Discovery yield efficiency per governed call |
| Persisted candidates per request | Persistence yield efficiency per governed call |
| Source/channel distribution | Confirms multi-channel sampling (Repair Area B) actually occurred, not just was configured |
| Time per request | Per-source latency, useful for detecting a slow/degraded source before it exhausts the runtime budget |
| Stop conditions | Confirms the bounded run stopped for an expected reason (max candidates reached, max requests reached, max runtime reached) and not an unexpected crash or hang |
| Rate-limit safety | Confirms the run never exceeded `default_rate_limit_per_minute` for any sampled source |
| Free-source budget safety | Confirms no paid-tier fallback or dependency was triggered for any source marked `requires_paid_plan=False` in the registry |

This is a **measurement design**, not an implementation change — it specifies what the
V2-2I bounded proof must capture and report. The underlying governed request mechanism
(`execute_source_request_with_governor()`) already exists; V2-2H's job is to exercise
it across more requests/channels within one bounded run so V2-2I has something
sustained to measure.

---

## 16. Candidate-Universe Coverage Metrics

The following metrics must appear in every future V2-2H/V2-2I run report. Where a
metric cannot be measured (e.g., no defensible total Solana daily launch universe
figure exists locally, as the live audit already found), the report must say
`NOT_MEASURED` explicitly rather than omitting the field or guessing a number.

| Metric | Source |
|--------|--------|
| `candidate_pool_total` | Total candidates in the current run's universe (all sources/channels combined) |
| `candidates_seen_total` | Every row returned by any governed source response before any filtering |
| `candidates_normalized_total` | Rows that passed field parsing/normalization |
| `candidates_persisted_total` | Rows written to `printer_discovery_candidates` |
| `candidates_rejected_pre_persistence` | Rows normalized but not persisted, with reason breakdown |
| `candidates_considered_for_selection` | Rows handed to the V2-2C selection module |
| `candidates_selected` | Rows that passed all selection gates and quota |
| `candidates_rejected_by_selection` | Rows considered but not selected, with reason breakdown |
| `candidates_by_source` | Per-source breakdown (dexscreener, geckoterminal, pumpportal, pumpswap, etc.) |
| `candidates_by_source_channel` | Per-channel breakdown (e.g., `GECKOTERMINAL_NEW_POOL`, `GECKOTERMINAL_TRENDING_POOL`, `DEXSCREENER_SEARCH`) |
| `candidates_by_asset_class` | Per-asset-class breakdown (existing V2-2C `derive_asset_class()` labels) |
| `candidates_by_bucket` | Per-primary-bucket breakdown (existing V2-2C 20-bucket taxonomy) |
| `candidates_by_age_bucket` | Per-age-bucket breakdown (Section 6 of this document) |
| `candidates_by_activity_bucket` | Per-activity-bucket breakdown (Section 7 of this document) |
| `candidates_by_liquidity_bucket` | Categorical liquidity band breakdown (reusing existing thresholds: under $500, $500-$5,000, $5,000-$25,000, $25,000-$100,000, $100,000+) |
| `candidates_by_volume_bucket` | Categorical 24h volume band breakdown (under $200, $200-$1,000, $1,000-$10,000, above $10,000) |
| `candidates_by_tracking_lane` | Per-lane breakdown (TRACK_FAST, TRACK_NORMAL, WATCH_ONLY) |
| `selected_by_source` / `selected_by_channel` / `selected_by_class` / `selected_by_bucket` / `selected_by_age_bucket` / `selected_by_activity_bucket` | Same breakdowns restricted to the final selected batch, to prove diversity was actually achieved, not just available |
| `rejected_by_reason` | Full rejection-reason breakdown across both pre-persistence and selection-stage rejections |
| `low_volume_candidates_count` | Count of candidates in `ACTIVITY_LOW` |
| `under_200_24h_volume_count` | Count of candidates with `volume_24h < $200` |
| `recent_active_candidates_count` | Count of Tier 1/2 candidates (Section 12) |
| `old_active_candidates_count` | Count of Tier 3 candidates (Section 12) |
| `legacy_reference_candidates_count` | Count of `AGE_28D_PLUS` candidates explicitly selected under a baseline/reference role (Section 5.3) |
| `dead_low_activity_candidates_count` | Count of `ACTIVITY_DEAD` + `ACTIVITY_LOW` candidates |
| `revival_candidates_count` | Count of `ACTIVITY_REVIVING` candidates |
| `estimated_total_daily_solana_memecoin_universe` | `NOT_MEASURED` unless a locally available, defensible source exists — the live audit already confirmed no such source currently exists in this repo |
| `coverage_percent` | `NOT_MEASURED` (depends on the metric above); report the literal string `NOT_MEASURED` rather than a computed guess |

---

## 17. Fair Selection Rules

"Fair consideration" and "not equally likely" are not in tension — this section
defines exactly how they coexist without becoming a scoring system.

- **Every valid candidate should be considered.** No candidate is discarded from the
  selection-consideration pool without a recorded reason. "Considered" means it enters
  the gate/bucket/tier pipeline (Sections 5-12); it does not mean every candidate has
  an equal chance of being selected.
- **Selection should prioritize observable activity and memory-learning value, not
  popularity or age alone.** The Tier 1-5 system (Section 12) and the activity buckets
  (Section 7) are the only inputs to priority ordering. Neither is a numeric score —
  they are ordered categorical tiers, and a candidate's tier is fully determined by
  which categorical thresholds it crosses, not by a computed value.
- **Memory diet should avoid all-winner/all-dead/all-consolidation/all-old-token
  bias.** This is enforced by the existing V2-2B/V2-2C quota system (Group A cap,
  D1 minimum, decay-bucket minimum, WATCH_ONLY minimum) combined with the new
  age-tier caps (Section 6, Section 12) — quotas and tiers work together, not as
  competing systems.
- **Recent active tokens should be prioritized**, per Section 12's Tier 1/2
  precedence, without excluding older/dead/low-volume tokens from their designated
  quota roles.
- **Older/dead/low-volume examples should be included only in controlled amounts** —
  enforced by the `AGE_28D_PLUS` soft cap and the existing bucket max-percentage
  quotas.
- **Selection remains categorical and auditable.** Every classification (age bucket,
  activity bucket, priority tier, primary bucket, asset class, selection reason,
  rejection reason) is a fixed categorical label from a documented, finite set. None of
  these labels is derived from a weighted formula, a normalized score, or a confidence
  percentage.
- **No trading prediction or alpha scoring.** None of the age/activity/tier
  classifications may be interpreted as, or renamed into, a BUY signal, an alpha
  score, or an entry-timing recommendation. They describe observed market state for
  memory-diet purposes only.

---

## 18. Memory-Diet Target for Future V2-2I Proof

The following is the target balanced mix for a future V2-2I bounded proof batch. This
is a **target**, not a guarantee — if the sampled candidate pool cannot supply a given
bucket, the report must say `ABSENT` or `NOT_MEASURED` for that bucket rather than
forcing a low-quality candidate into it.

| Target category | Bucket(s) | Presence expectation |
|-------------------|-----------|------------------------|
| Recent active tokens | Tier 1/2 candidates across A/B/C groups | Should be the largest single category if discovery breadth (Repair Area B) succeeds |
| Fast pump follow-through | A1 | Present if any Tier 1/2 candidate qualifies; capped per V2-2B (max 2) |
| Wick-only pump | A2 | Present only if `price_change_5m` capture (Repair Area C) succeeds and a qualifying candidate exists; otherwise `ABSENT` with explicit reason `PRICE_CHANGE_5M_UNAVAILABLE` |
| Late-buy trap | A3 | Present only if `token_age_seconds`/`price_change_1h` capture succeeds; otherwise `ABSENT` with explicit reason |
| Failed pump | A4 | Present only if the new A4 derivation rule (Section 11) is implemented and a qualifying candidate with prior A-tier history exists; otherwise `ABSENT` |
| Consolidation | B5 | May be present but must not be the only populated bucket (this was the live audit's core finding) |
| Transaction spike | B3 | Present if any candidate meets the existing gate |
| Volume decay | B2/B4 | Present if any candidate meets the existing gate |
| Liquidity rising/falling/removed | C1/C2/C3 | Present if source payloads show liquidity movement; C3 is safety-sensitive per V2-2B and requires explicit reason if selected |
| Dead/low-activity token | D1 / `ACTIVITY_DEAD` / `ACTIVITY_LOW` labels | Required minimum per existing V2-2B quota (at least 1 in batch of 6+) |
| Revival token | D2 / `ACTIVITY_REVIVING` | Present if any candidate qualifies; capped at 1 per batch per V2-2B |
| Migration token | D3 | Present if a within-response or cross-run STNP case resolves to `MIGRATION`; capped at 1 per batch per V2-2B |
| Older active/reference token | `AGE_28D_PLUS` + `ACTIVITY_HIGH`/`ACTIVITY_MEDIUM` | Present in controlled amount (soft cap 2) per Section 6 |
| Low-volume negative-learning example | `NEGATIVE_LEARNING` / `NO_REAL_MARKET_DEPTH` labels (Section 5.4) | Present if under-$200-volume candidates exist in the pool; this label set is new for V2-2H |
| Realistic/unrealistic exit candidate | E1/E2 | Present only where safe data exists (per existing V2-2B Group E rule, capped at 2); otherwise `ABSENT` |

---

## 19. V2-2H Implementation Handoff

**V2-2H — Discovery/Selection Capacity Repair Implementation** should implement, if
this design is accepted:

1. Configurable, bounded candidate cap replacing the hardcoded 1-3 range
   (`commands.py:1356-1357`), per Repair Area A.
2. Configurable, bounded source-request cap and bounded max-runtime parameter, per
   Repair Area A.
3. Age-bucket derivation (`AGE_0_24H` through `AGE_UNKNOWN`), per Section 6.
4. Activity-bucket derivation (`ACTIVITY_HIGH` through `ACTIVITY_UNKNOWN`), per
   Section 7.
5. Recent-active priority tier categories (Tier 1-5), per Section 12/Repair Area E.
6. Low-volume/dead-token handling (`LOW_ACTIVITY`, `DEAD_TOKEN`, `WATCH_ONLY`,
   `NEGATIVE_LEARNING`, `UNREALISTIC_EXIT`, `NO_REAL_MARKET_DEPTH` labels), per
   Section 5.4.
7. Improved field normalization for `price_change_5m`, `price_change_1h`,
   `price_change_24h`, `pair_created_at` (direct capture where available), plus
   `token_age_seconds`, `pair_age_seconds`, `price_change_15m`, `volume_15m`, and
   `token_created_at` (derived where possible), plus explicit known-vs-unknown field
   tracking, per Repair Area C.
8. A1/A2/A3/A4 categorical rules — repairing the missing-field blockers for A2/A3 and
   adding the new A4 derivation rule, per Repair Area D.
9. Within-response dedup/STNP handling at persistence time, per Repair Area F.
10. Schema readiness check for selection-batch tables with fail-fast behavior, per
    Repair Area G.
11. Expanded candidate-universe reporting implementing every metric in Section 16.
12. Multi-source/channel sampling extension for at least the two additional
    GeckoTerminal/DexScreener channels identified as immediately safe in Repair Area B,
    with explicit `NOT_READY` marking for PumpPortal/PumpSwap/Solana RPC until adapter
    readiness is separately confirmed.

**V2-2H must not:**

- Run a live proof against the production DB without explicit operator approval and a
  proof-DB-first default.
- Introduce any new paid API dependency.
- Bypass Source Governor or Central Scheduler.
- Introduce scoring, ranking, confidence, or weighted logic anywhere in the
  age/activity/tier/bucket system.
- Unlock memory generation, retrieval, paper decisions, or any financial capability.

---

## 20. V2-2I Proof Handoff

**V2-2I — Discovery/Selection Capacity Repair Bounded Proof** (later lane, not run now)
should prove, using an isolated proof DB:

1. A larger bounded candidate cap than 3 (e.g., 10-20) actually persists more
   candidates from a single governed run, with the six-stage count separation from
   Repair Area A fully reported.
2. More than one source/channel sampled in a single bounded run, if the corresponding
   adapters are confirmed safe (at minimum, GeckoTerminal new-pool + GeckoTerminal
   trending + DexScreener token_discovery).
3. Measurably improved field completeness for `price_change_5m`, `price_change_1h`,
   `token_age_seconds` versus the live audit's 100%-missing baseline.
4. Age/activity distribution reporting populated with real (non-zero) counts across at
   least 3 of the 6 age buckets and at least 3 of the 6 activity buckets.
5. Recent active candidate selection — the selected batch includes at least one Tier 1
   or Tier 2 candidate (Section 12), not just consolidation/dead-token examples.
6. Low-volume/dead-token classification correctly routing under-$200-volume candidates
   to the appropriate label set (Section 5.4).
7. A1/A2/A3/A4 differentiation — at minimum, a real A2 or A3 classification appearing
   in the candidate pool (not necessarily selected, but classifiable), proving the
   missing-field repair worked.
8. Within-response duplicate/STNP handling — either a real within-response duplicate
   case handled correctly, or an explicit statement that no such case occurred in the
   sampled run (absence of the bug trigger is not the same as proof the handling
   works; a synthetic/fixture-based unit test in V2-2H should independently prove the
   handling logic before V2-2I attempts to observe it live).
9. Selection quota behavior — confirms `validate_batch_quota()` continues to pass
   correctly against a more diverse candidate pool.
10. Zero downstream lock deltas — `printer_memory_windows`, `printer_paper_decisions`,
    `printer_paper_positions`, `printer_paper_trade_audits`, and any retrieval-match
    table must show delta zero, exactly as in every prior V2-2 proof.

---

## 21. Money-Usefulness Contribution

This repair sequence advances Printer's long-term money-usefulness goal without making
any profit claim:

- **Wider intake** means Printer's corpus is built from a realistic cross-section of
  the Solana memecoin market, not an artifact of a 3-candidate cap and a single
  GeckoTerminal channel.
- **Less biased memory diet** follows directly from age/activity-tier priority
  combined with the existing V2-2B/V2-2C quota system — the corpus will contain
  genuine diversity across fast pumps, traps, dead tokens, revivals, and consolidation,
  rather than being dominated by whatever the narrowest safe intake happened to
  surface (as the live audit's `{B5, B5}` result demonstrated).
- **Better current-market learning** comes from prioritizing 0-24h through 14-28d
  active tokens — this is precisely the population that teaches Printer what *current*
  Solana memecoin launch behavior looks like, rather than what a handful of
  long-established tokens looked like years ago.
- **Stronger recent active-token learning** is the direct output of Repair Area E's
  tier system.
- **Better fast-event learning** comes from Repair Area C (missing-field capture) and
  Repair Area D (A2/A3/A4 rules), which together unlock the trap/wick/failure examples
  that a corpus needs to teach realistic capital-protection lessons, not just pump
  recognition.
- **Better dead/low-volume/revival learning** comes from Section 5.4's explicit
  low-activity classification set and the `ACTIVITY_REVIVING` bucket, ensuring these
  categories are captured intentionally rather than either excluded or silently mixed
  into normal-activity buckets.
- **Better rejection visibility** comes from Repair Area A's six-stage count
  separation and Repair Area F's within-response STNP reporting — every candidate's
  fate is auditable, closing the "17 rejected, mostly for a cap reason" opacity the
  live audit surfaced.
- **Better source coverage reporting** comes from Repair Area B's per-source
  `SAMPLED`/`NOT_SAMPLED_THIS_RUN`/`NOT_READY` status, replacing the current silent
  single-channel default with an explicit, auditable coverage statement.
- **Stronger future memory growth** follows because V2-3/V2-4's one-command Memory
  Factory automation will only be as good as the candidate pool it draws from — this
  repair sequence is the prerequisite for that automation producing a genuinely
  balanced corpus rather than automating a narrow, biased intake at scale.

No claim is made that any of this produces or predicts trading profit. This is a
learning-corpus-quality repair, not a trading-signal improvement.

---

## 22. What This Still Does Not Unlock

V2-2G does not unlock:

- V2-3 — One-Command Memory Factory Automation Design (paused pending this repair
  sequence's completion or explicit operator acceptance).
- Implementation of any kind (V2-2G is design-only; implementation is V2-2H).
- Source fetching.
- Memory generation.
- Retrieval.
- Paper decisions.
- BUY/SELL/HOLD.
- Paper positions.
- Trades.
- Paper trade audits.
- PnL.
- Live trading, wallet/private keys, real funds.
- Paid APIs.
- Scoring/ranking/confidence/weighted token logic.
- Embeddings/vectors.

---

## 23. Functionality Risks / Setbacks / Efficiency Blockers

| Problem | Why it matters | Failure mode | Required mitigation | Stop condition |
|---------|----------------|--------------|----------------------|-----------------|
| Source budget exhaustion | Expanded cap + multi-channel sampling increases governed-call volume | Rate-limit violations, degraded source trust | Hard `max_source_requests` cap tied to each source's `default_rate_limit_per_minute` (Repair Area A/H) | Any single-run request count exceeds a source's governed rate limit |
| Rate limits | GeckoTerminal (30/min), PumpPortal (30/min), PumpSwap (20/min) are conservative | Source Governor rejects requests mid-run | Respect existing `registry.py` limits; do not raise them in V2-2H | Governor rejection observed in proof run |
| Missing fields despite repair | Some source APIs may genuinely not expose `price_change_5m`/`token_age_seconds` even after parser extension | A2/A3 remain unreachable even after repair | Explicit `null`/`AGE_UNKNOWN`/`ACTIVITY_UNKNOWN` fallback (Repair Area C) prevents silent masking; report continues to show real completeness % | Missing-field % stays at or near 100% after V2-2H despite parser changes — must be documented, not hidden |
| Source inconsistency | DexScreener/GeckoTerminal field names and availability can differ or change | Parser breaks or silently drops fields | Field-level fallback and known-vs-unknown tracking (Repair Area C) | Parser exception on a previously-working field |
| False A2/A3/A4 classification | New A4 rule depends on prior-candidate history lookup; a data gap could misclassify | A token wrongly labeled FAILED_PUMP when it simply wasn't re-discovered | A4 rule requires an actual prior A-tier `printer_discovery_candidates` row for the same token/pair, not an inferred one | A4 assigned with no verifiable prior A-tier history |
| Over-broad candidate intake | Raising the cap too high in one run could strain source budget or overwhelm review | Runtime/report becomes unwieldy; budget risk | Bounded, validated cap range (Repair Area A); proof-DB-first default for expanded caps | Cap set above validated ceiling or proof-DB default skipped without operator approval |
| Over-focusing on fresh launches | Tier 1/2 priority could overcorrect and starve Group C/D older-reference examples | Corpus loses market-structure comparison value | `AGE_28D_PLUS` soft cap is a floor as well as a ceiling in practice — quota system still requires D1/decay examples regardless of recency priority | Batch has zero older-reference/baseline examples across many consecutive runs |
| Over-focusing on old clean tokens | The original failure mode this design repairs | Corpus dominated by BONK/WIF/WEN-style tokens | Tier system + `AGE_28D_PLUS` soft cap (Section 6/12) | Batch is dominated by `AGE_28D_PLUS` tokens despite Tier 1/2 candidates being available |
| Low-volume noise | Broad discovery eligibility means many near-worthless candidates enter the pool | Report/storage clutter; selection overhead | Explicit low-activity routing (Section 5.4) keeps these candidates classified and capped, not filtered out entirely (they still have learning value) but also not allowed to dominate | Low-volume candidates exceed their bucket's max-percentage cap in a selected batch |
| Selection becoming too slow | More candidates + more buckets + more tiers increases per-run computation | Bounded-run runtime budget exceeded | Bounded max-runtime parameter (Repair Area A) caps total run duration regardless of candidate count | Run exceeds configured max runtime |
| Storage growth | More persisted candidates means more DB rows over time | DB size grows faster than before | Not addressed by this design; flagged as an open item for a future lane (out of scope for V2-2G/H/I) | N/A — informational risk only |
| Scheduler overload | More persisted candidates could create more tracking-queue/scheduler follow-up rows | Central Scheduler job backlog | Cap increases in V2-2H must be evaluated against existing scheduler job-creation behavior before the cap is raised in a live run | Scheduler job count grows disproportionately to candidate cap increase |
| Source Governor bypass risk | New multi-channel sampling code must not introduce a shortcut around the governed path | Untracked/unrecorded source calls | Every new source/channel call in V2-2H must use `execute_source_request_with_governor()`, no exceptions | Any source call without a `printer_source_requests`/`printer_source_responses` trace row |
| Central Scheduler bypass risk | Design does not intend to touch scheduler behavior, but expanded discovery volume increases job-creation surface | Scheduler jobs created outside the governed tracking-queue-to-scheduler path | No change to scheduler integration in V2-2G/V2-2H scope; any scheduler-adjacent change requires separate review | Direct scheduler job creation bypassing tracking-queue sync |
| Duplicate/STNP leakage | Within-response dedup is a genuinely new code path (Repair Area F) | Two rows for the same mint both persisted without classification | Explicit within-response grouping and classification before persistence, with UNRESOLVED blocking both rows | Two persisted candidates share a `token_mint` without an STNP classification |
| Migration readiness failure | Migration 025 was found absent from the copied live DB during the live audit | Selection code fails or requires ad hoc setup at runtime | Fail-fast schema readiness check (Repair Area G) | Selection command runs against a DB missing required tables without an explicit, actionable error |
| Report hiding reject reasons | A repaired system with more candidates could make reject-reason reporting more overwhelming and tempt future implementers to summarize/hide detail | Operator loses audit trail | Every rejection (pre-persistence and selection-stage) must retain a specific reason string; summarization for readability must not remove the underlying per-candidate detail from the raw report/artifact | Rejection reasons aggregated into a vague count with no per-candidate detail available |
| Accidental unlock of memory/retrieval/paper paths | Any implementation touching discovery/selection code carries some risk of accidentally wiring into memory/retrieval/paper code | Lock violation | V2-2H must be scoped strictly to discovery/selection files; any accidental import or call into memory-window, retrieval, or paper-decision modules is a stop condition | Any memory/retrieval/paper module imported or called from V2-2H discovery/selection code |

---

## 24. Readiness Verdict

**`V2-2G Discovery/Selection Capacity Repair Design: DESIGN_COMPLETE_WITH_BLOCKERS`**

The design is complete: it defines discovery eligibility, selection priority, age
buckets, activity buckets, and eight concrete repair areas (A-H), grounded in the real
live-audit numbers and the actual current codebase (candidate cap location, source
registry contents, existing bucket-assignment code). It remains
`_WITH_BLOCKERS` because implementation (V2-2H) has not happened yet — every repair
area in this document is a specification, not a working system.

---

## 25. Next Recommended Lane

**Next recommended lane: `V2-2H — Discovery/Selection Capacity Repair Implementation`**

V2-2H is implementation, not design. It should proceed **only if the operator accepts
this design document**. V2-2H must:

- Implement Repair Areas A-G against the real codebase (`commands.py`, `parser.py`,
  the source adapter files, `selection_batch.py`).
- Preserve every lock listed in Section 22.
- Default to proof-DB-only execution for any expanded-cap or multi-channel testing
  until the operator explicitly approves a live-DB run.
- Produce a full unit test suite proving each repair area's categorical rules (no
  scores, no ranks) before any bounded live proof is attempted.
- Hand off to `V2-2I — Discovery/Selection Capacity Repair Bounded Proof` only after
  V2-2H's test suite passes.

V2-3 remains paused until V2-2H and V2-2I are complete, or until the operator
explicitly accepts the current V2-2 state as sufficient to proceed.
