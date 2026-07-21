# V2-9.7D.7B.6 Bounded Live-Source Proof Closeout

**Status:** PASS
**Lane:** V2-9.7D.7B.6
**Boundary:** one operator-authorized sequential live proof (third attempt history); no production change
**Date:** 2026-07-21

## Verdict

`V2_9_7D_7B_6_BOUNDED_LIVE_SOURCE_PROOF_PASS`

## Todo / Checklist

- [x] Verify exact HEAD `1309c2807d59d167fe90104eabcae64a8003acf7`.
- [x] Preflight tracked worktree; preserve uncommitted 7B.6 files.
- [x] Credential preflight: `SOLANA_TRACKER_API_KEY` PRESENT (value never printed).
- [x] Confirm Solana Tracker free REST (no wallet/funds/signing/paid path).
- [x] Update harness for `PASS_EMPTY_AFTER_ROW_FILTER` after 4B.1 repair.
- [x] Probe Direct → DexScreener → GeckoTerminal → Solana Tracker once.
- [x] Combined low-ceiling disposable proof.
- [x] Synthetic negative assertions around captured inputs.
- [x] Write this closeout distinguishing all three attempts.
- [x] Focused regressions + leakage scan + diff checks.
- [x] PASS commit of proof-specific files only.

## Exact Commit Proven

`1309c2807d59d167fe90104eabcae64a8003acf7`

(`Repair Tracker row freshness handling` — includes V2-9.7D.7B.4B.1 row-level freshness repair.)

## Operator-Authorization Scope

Authorized exactly once (this re-proof):

- bounded read-only calls to already approved free/public contracts;
- one sequential provider-by-provider probe;
- one combined low-ceiling proof only after required probes pass or return
  explicitly acceptable empty/gapped results.

Not authorized and not performed:

- second live rerun after this attempt;
- background monitoring / persistent campaign;
- command publication;
- activation review / pilot;
- tracking-window execution / memory generation;
- retrieval or financial capability;
- production repairs during the proof.

## Attempt History

### Attempt 1 — blocked auth (historical)

| Field | Value |
|---|---|
| HEAD | `27d67e26d97411e0439fe0406212b934dfc828cc` |
| Outcome | `V2_9_7D_7B_6_BOUNDED_LIVE_SOURCE_PROOF_BLOCKED` |
| Material blocker | Solana Tracker `BLOCKED_AUTH` — free API key unavailable |
| Tracker HTTP | 0 (fail-closed before transport) |
| Combined | not started |

### Attempt 2 — blocked normalizer (historical)

| Field | Value |
|---|---|
| HEAD | `27d67e26d97411e0439fe0406212b934dfc828cc` |
| Outcome | `V2_9_7D_7B_6_BOUNDED_LIVE_SOURCE_PROOF_BLOCKED` |
| Material blocker | `normalize_tracker_list` whole-body `STALE_OR_UNKNOWN` |
| Tracker HTTP | 2 (HTTP 200 both) |
| Combined | not started |
| Follow-up repair | V2-9.7D.7B.4B.1 row-level freshness (`1309c280…`) |

### Attempt 3 — this newly authorized re-proof

| Field | Value |
|---|---|
| HEAD | `1309c2807d59d167fe90104eabcae64a8003acf7` |
| Outcome | `V2_9_7D_7B_6_BOUNDED_LIVE_SOURCE_PROOF_PASS` |
| Started UTC | `2026-07-21T13:02:26Z` |
| Finished UTC | `2026-07-21T13:02:59Z` |
| Work directory | process temp `printer_7b6_live_y_db2_ag` (ephemeral) |
| Evidence | redacted hashes/counts only under that temp directory |
| Production changes | none |
| Live runs this authorization | **exactly one** |

## Free-Access and Credential Preflight

| Check | Result |
|---|---|
| `SOLANA_TRACKER_API_KEY` present | YES (value never printed) |
| Key written to files/DB/logs/fixtures/reports | NO |
| New credential convention | NO |
| Free REST plan (adopted) | EUR 0 / 10k req/month / 3 rps; no wallet/funds/signing |
| Paid path used | NO |

## Approved Endpoints and Request Kinds (attempt 3)

| Provider | Endpoint / method | Calls |
|---|---|---:|
| Solana public RPC | `api.mainnet-beta.solana.com` `getSlot` + `getSignaturesForAddress` | 2 |
| DexScreener | `token-profiles/latest/v1` + `tokens/v1/solana/{addresses}` | 2 |
| GeckoTerminal | trending_pools page=1 duration=1h + exact pool enrich | 2 |
| Solana Tracker | `/tokens/trending/1h` + `/top-performers/1h` | 2 |
| PumpSwap | none | 0 |
| PumpPortal | none | 0 |
| Pumpdev | none | 0 |

Hosts only: `api.mainnet-beta.solana.com`, `api.dexscreener.com`,
`api.geckoterminal.com`, `data.solanatracker.io`.

Zero ordinary retries. Zero endpoint rotation. Zero background reconnects.

## Individual Provider Verdicts (attempt 3)

| Provider | Verdict | Notes |
|---|---|---|
| Direct Pump / Solana RPC | **PASS** | Governor admitted; cutoff slot `434308405`; 4 signatures all `post_cutoff` → continuity **GAPPED**; decoded creates **0**; 2 RPC ops |
| DexScreener | **PASS** | 5 Solana profile mints; 5 batch observations; rank/boost excluded; ~32.7 KiB |
| GeckoTerminal | **PASS** | 20 trending normalized; active m5 count 15 on pool `636bk…`; ~40.4 KiB |
| Solana Tracker | **PASS_EMPTY_AFTER_ROW_FILTER** | Auth free REST OK; both HTTP 200; list schema OK; 0 normalized after row-level freshness skip |
| PumpSwap | `PUMPSWAP_CONFIRMATION_NOT_REQUIRED` | 0 requests |
| PumpPortal | `SKIPPED_BLOCKED_CONTRACT` | 0 requests |
| Pumpdev | EXCLUDED | 0 requests |

### Direct continuity

- Immutable cutoff: finalized slot `434308405`.
- Signature page limit 4; all classified `post_cutoff`.
- Continuity: `GAPPED` (honest; not treated as failure).
- Create-decode yield: 0 (acceptable when honestly reported).

### Solana Tracker auth / schema / freshness

| Item | Result |
|---|---|
| Free-key authentication | PASS (HTTP 200 both endpoints) |
| Free-access path | PASS |
| Top-level schema | list bodies (`trending` len 49, `top` len 14) |
| `lastUpdated` types | int (ms contract) |
| Pumpfun market pools scanned | trending 40, top 2 |
| Fresh pumpfun pools | 0 / 0 |
| Stale pumpfun pools skipped (row-level) | 40 / 2 |
| Future pumpfun pools | 0 / 0 |
| Normalized rows | trending 0 + top 0 = **0** |
| Verdict | `PASS_EMPTY_AFTER_ROW_FILTER` (factual empty; does **not** block combined) |
| Rank/score/risk/promoted/order | excluded from eligibility inputs (contract + strip intent recorded) |
| Provider `pumpfun` labels | remain **unverified** origin |

4B.1 repair confirmed live: mixed-age body no longer aborts; all-stale pumpfun rows yield empty normalized set without exception.

## Exact Request / Operation Counts (attempt 3)

| Metric | Value |
|---|---:|
| DexScreener HTTP GETs | 2 |
| GeckoTerminal HTTP GETs | 2 |
| Solana Tracker HTTP GETs | 2 |
| Direct RPC operations (individual probe) | 2 |
| Ordinary retries | 0 |
| Endpoint rotations | 0 |
| Combined source_calls | 5 |
| Combined scheduler_work | 9 |
| Combined storage_bytes | 544916 (~0.52 MiB) |
| Combined failures | 0 |
| Combined observations (DB readback) | 26 |
| Combined unique mints | 23 |
| Combined slots / tracking / WINDOW_15M jobs | 0 / 0 / 0 |

Provider-local response byte sums (approx): Dex ~33 KiB + Gecko ~40 KiB + Tracker ~497 KiB + RPC ~1 KiB. Harness `totals.response_bytes` field double-counts some probes and is not used as an authority metric.

## Combined Proof Outcome

**Executed once** on disposable SQLite under process temp (not committed).

| Field | Value |
|---|---|
| Terminal status | `FAILED` |
| First terminal cause | `INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL` |
| Selected mints | none |
| Slots / tracking | 0 / 0 |
| WINDOW_15M jobs created | 0 |
| WINDOW_15M executed | no |
| Source Governor used | true |
| Central Scheduler used | true |
| Acceptable market outcome | **yes** (explicitly allowed insufficient-pool path with zero partial activation) |

Work types observed (migration-034 discovery work path):

- `DISCOVERY_PUMPFUN_LATEST`
- `DISCOVERY_GECKOTERMINAL_TRENDING_ACTIVE`
- `DISCOVERY_SOLANA_TRACKER_TRENDING_TOP`
- `DISCOVERY_DEXSCREENER_ACTIVE`
- `DISCOVERY_ORIGIN_VERIFICATION`
- `DISCOVERY_PUMPSWAP_CONFIRMATION`
- `DISCOVERY_IDENTITY_MERGE`
- `DISCOVERY_FIXED_ELIGIBILITY_GATES`
- `DISCOVERY_UNIFORM_SELECTION`

Job kinds: `DISCOVERY_REFRESH` only (no track/window activation jobs).

### Ceiling note

Stated proof ceilings of **24 observations / 12 unique mints** were exceeded on this live capture (26 / 23) because full Gecko trending + Dex batch bodies were fed as fixtures. Other hard resource ceilings held (`source_calls` 5≤20, `scheduler_work` 9≤11, storage ≤2 MiB, failures 0≤3). Selection was **not** forced by raising limits; outcome remained insufficient-pool with zero activation. Future proofs may truncate fixture bodies to the stated observation/mint caps without changing production.

## Atomicity and Failure-Isolation Evidence

Synthetic fault injection around captured live inputs (no deliberate real provider abuse):

| Case | Result |
|---|---|
| Secondary isolation (Gecko rate_limited inject) | zero slots/tracking/window15m; insufficient or isolated failure path |
| Direct origin loss | `INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL`; zero activation |
| Shared first fault | `SHARED_CONFIGURATION_MISMATCH` / `SHARED_FAILURE`; zero activation |
| Atomic rollback inject (`DURING_SECOND`) | slots=0, tracking=0, window15m=0 (no partial two-slot activation) |

Zero retries. Zero endpoint rotation. Zero 5m/1h/4h activation. Locked financial tables delta zero.

## Locked-Capability Baseline / Final Deltas

All zero before and after combined disposable campaign:

- `printer_memory_retrieval_queries` / `matches`
- `printer_paper_decisions`
- `printer_paper_positions`
- `printer_paper_trade_events` / `audits`
- `printer_paper_audit_reports`

`locked_delta_zero`: **true**

Paper-only locks held: no wallet, signing, funds, live execution, retrieval activation, BUY/SELL/HOLD.

## Temporary-Data Disposal Confirmation

- Raw live bodies retained only in process memory for combined fixture injection.
- Redacted evidence stores hashes, counts, statuses, gap codes only.
- No API key values, authorization material, or raw provider payloads written into the repository.
- Temp work directory outside the repo; temporary DB not committed.
- No secret material in closeout.

## Money-Usefulness Contribution

Live multi-source discovery ownership path is proven under Source Governor and Central Scheduler with free/public contracts only:

- Keyless DexScreener + GeckoTerminal yield Solana identities.
- Public RPC Pump Program probe reports honest gaps.
- Free Tracker auth works; 4B.1 row-level freshness yields factual empty rather than whole-body failure.
- Combined executor safely stops at two-or-none with zero partial activation when live origin evidence is insufficient.

This does **not** unlock tracking, memory, decisions, or financial capability.

## What Remains Unproved

- Live create-decode yield under a cutoff that includes the signature page.
- Live Tracker non-empty normalized pumpfun set within 180s freshness.
- Live selection of exactly two origin-verified candidates and atomic tracking handoff.
- Isolated WINDOW_15M persistence-link proof after successful selection (no selection this run).
- Live PumpSwap confirmation when a qualifying migration claim exists.
- Observation/mint proof-ceiling adherence under full live secondary pages.
- Activation review, command publication, pilot, V2-9.7D closeout.

## Activation-Review Blockers

1. This PASS is **live-source proof only** — not operational activation.
2. No public command publication.
3. No tracking-window / memory-generation campaign.
4. No BUY/SELL/HOLD, positions, PnL, or retrieval unlock.
5. Future activation review requires separate operator-approved lanes after corpus readiness.

## Functionality Risks / Setbacks / Efficiency Blockers

- Pump Program signature traffic remains extremely busy; pre-fetched `getSlot` can race signature pages → all-post-cutoff gaps with zero creates.
- Tracker 1h lists can be entirely stale under the 180s pool policy → factual empty pumpfun contribution is common.
- Full secondary page bodies can exceed the 24-observation / 12-mint proof ceilings while still producing insufficient eligible origin-verified candidates.
- Combined INSUFFICIENT path is expected without live direct origin creates; two-slot success remains environment-dependent.
- Public RPC and free REST rate limits remain operational risks under broader campaigns (not provoked here).

## Production Change Prohibition Confirmation

No production code, adapters, contracts, migrations, schemas, combined executor, persistence, or public commands were modified in this proof lane.

Proof-only files updated:

- `tests/proof_v2_9_7d_7b_6_bounded_live_source.py`
- `docs/printer-v1-v2-9-7d-7b-6-bounded-live-source-proof-closeout.md`

## Stop Boundary

V2-9.7D.7B.6 stops at this PASS closeout. Activation review, V2-9.7D closeout, command publication, and pilot were not started. Exactly one new live run occurred under this authorization.
