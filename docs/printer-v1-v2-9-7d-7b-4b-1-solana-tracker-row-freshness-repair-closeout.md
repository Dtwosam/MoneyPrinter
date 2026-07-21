# V2-9.7D.7B.4B.1 Solana Tracker Row-Level Freshness Repair Closeout

**Status:** PASS
**Lane:** V2-9.7D.7B.4B.1
**Boundary:** narrow production normalizer repair + focused synthetic tests + closeout only
**Date:** 2026-07-21

## Verdict

`V2_9_7D_7B_4B_1_SOLANA_TRACKER_ROW_FRESHNESS_REPAIR_PASS`

## Todo / Checklist

- [x] Verify exact HEAD `27d67e26d97411e0439fe0406212b934dfc828cc`.
- [x] Leave uncommitted 7B.6 proof files untouched (no reset/stash/commit).
- [x] Read adopted Tracker contract and 7B.3B / 7B.4B closeouts.
- [x] Repair `normalize_tracker_list` for row-level stale/future skip.
- [x] Align minimum fixture/test expectations.
- [x] Add focused 4B.1 synthetic proof suite (15 cases).
- [x] Run focused tests only (no network / no live 7B.6).
- [x] Write this closeout and commit repair-lane files only.

## Starting HEAD

`27d67e26d97411e0439fe0406212b934dfc828cc`

## Live-Proof Defect Evidence (7B.6, read-only)

From the blocked authorized 7B.6 rerun (evidence only; not re-run here):

| Fact | Result |
|---|---|
| Free-key authentication | Works (`SOLANA_TRACKER_API_KEY` present; HTTP 200) |
| Adopted endpoints | `/tokens/trending/1h`, `/top-performers/1h` returned HTTP 200 |
| Production normalizer | Raised whole-body `STALE_OR_UNKNOWN` on first stale/future pumpfun pool |
| Combined stage | Not started because individual Tracker probe failed |

Attempt history context:

1. First 7B.6 attempt: `BLOCKED_AUTH` (missing free key).
2. Authorized 7B.6 rerun: auth PASS; normalize FAIL `STALE_OR_UNKNOWN`.

Those 7B.6 proof files remain uncommitted and were not modified by this repair lane:

- `tests/proof_v2_9_7d_7b_6_bounded_live_source.py`
- `docs/printer-v1-v2-9-7d-7b-6-bounded-live-source-proof-closeout.md`

## Root Cause

Adopted Solana Tracker contract authority:

`docs/solana-builder-source-of-truth/solana-tracker-secondary-discovery-contract.md`

Required handling:

| Condition | Required result |
|---|---|
| missing/stale/future `lastUpdated` or receipt | `STALE_OR_UNKNOWN`; **reject row** |
| empty well-formed array after filtering | factual empty provider list |
| non-array / over-limit / body schema failure | response-level failure |

Production `normalize_tracker_list` previously did:

```text
if age < -5 or age > 180s:
    raise SecondaryDiscoveryError("STALE_OR_UNKNOWN", "stale_or_future_pool")
```

That converted a **row-level** freshness rejection into a **response-level** abort. On a live 1h trending/top list, any single stale or future pumpfun pool aborted the entire body, including otherwise valid rows. Fixture tests had encoded the raise-whole-body behavior, so the defect was not caught until live 7B.6.

Receipt-level staleness (`evaluated_at - receipt_time > 180s`) was already correct as a response-level failure and remains unchanged.

## Exact Behavioral Repair

File: `src/printer_v1/sources/secondary_discovery.py`

Function: `normalize_tracker_list`

Change only the per-pool freshness branch:

- **Before:** raise whole-body `STALE_OR_UNKNOWN` on first stale/future pumpfun pool.
- **After:** `continue` (row contributes nothing); remaining rows still evaluate.

Preserved unchanged:

- 180-second threshold (`TRACKER_STALE_AFTER_SECONDS = 180`)
- receipt-level `STALE_OR_UNKNOWN` / `stale_receipt` response failure
- body not array → `MALFORMED_RESPONSE`
- body length > 100 → `SCHEMA_OR_LIMIT_DRIFT`
- malformed token/pool objects → response/row failures as before
- missing mint / missing pool identity → `AMBIGUOUS_IDENTITY`
- non-`pumpfun` market and mint/pool mismatch → skip (no contribution)
- exact identity, provenance collapse, deterministic `(mint, pool)` sort
- rank/score/risk/promoted/order stripping via identity-only observations
- Source Governor request kinds and Scheduler work type ownership
- zero ordinary retries / zero endpoint rotation / no provider fallback

All-stale or all-future parseable pumpfun rows now return `()` (deterministic empty), matching factual empty contribution, not an exception.

## Row-Level Versus Response-Level Failure Boundary

| Failure class | Level | Behavior after repair |
|---|---|---|
| Pool `lastUpdated` stale (>180s) | **Row** | Skip pool; no candidate contribution |
| Pool `lastUpdated` materially future (age < -5s) | **Row** | Skip pool; no candidate contribution |
| All parseable pumpfun pools stale/future | **Row aggregate** | Empty tuple `()`; no exception |
| Receipt older than 180s | **Response** | Raise `STALE_OR_UNKNOWN` / `stale_receipt` |
| Body not a list | **Response** | Raise `MALFORMED_RESPONSE` |
| Body length > 100 | **Response** | Raise `SCHEMA_OR_LIMIT_DRIFT` |
| Malformed token/pool structure | **Response** | Raise `MALFORMED_RESPONSE` (unchanged) |
| Missing mint / missing required pool identity fields | **Response** | Raise `AMBIGUOUS_IDENTITY` (unchanged) |
| Auth missing/invalid (lane) | **Response** | `BLOCKED_AUTH` via auth config / lane |
| HTTP 429 / rate limit (lane) | **Response** | `BLOCKED_QUOTA` via transport classification |

No row-level diagnostic channel existed on `normalize_tracker_list` return type; contribution remains observation presence only (empty = no contribution). Response-level failures still surface as exceptions or lane `ProviderFailure` entries.

## Focused Tests

New suite:

`tests/test_v2_9_7d_7b_4b_1_solana_tracker_row_freshness.py`

| # | Proof | Result |
|---|---|---|
| 1 | One valid row normalizes | PASS |
| 2 | One stale row → no contribution | PASS |
| 3 | One future-dated row → no contribution | PASS |
| 4 | Mixed valid/stale/future → only valid preserved | PASS |
| 5 | Stale/future before valid do not abort parsing | PASS |
| 6 | Stale/future after valid do not remove valid output | PASS |
| 7 | All stale/future → empty result, no whole-body exception | PASS |
| 8 | Invalid top-level schema / ceiling / stale receipt remain response-level | PASS |
| 9 | Auth and transport failures remain response-level | PASS |
| 10 | Malformed identity handling unchanged | PASS |
| 11 | Rank/score/risk/promoted/order stripping intact | PASS |
| 12 | Identical fixtures → deterministic output | PASS |
| 13 | Pagination/observation ceilings enforced; threshold still 180s | PASS |
| 14 | GeckoTerminal behavior unchanged | PASS |
| 15 | Source Governor + Scheduler ownership still pass | PASS |

Aligned existing tests:

- `tests/test_v2_9_7d_7b_4b_secondary_discovery_adapters.py` — stale case expects row skip / all-stale empty
- `tests/test_secondary_discovery_contract_fixtures.py` — contract mirror uses row-level skip; all-stale empty

## Tests / Checks Run

```text
pytest tests/test_v2_9_7d_7b_4b_1_solana_tracker_row_freshness.py
      tests/test_v2_9_7d_7b_4b_secondary_discovery_adapters.py
      tests/test_secondary_discovery_contract_fixtures.py
→ 32 passed
```

- No network tests
- No live 7B.6 re-proof
- `git diff --check` on repair paths
- Staged `git diff --check` at commit time

## Money-Usefulness Contribution

This repair restores the contract-faithful ability for Solana Tracker free REST 1h lists to yield **partial valid pumpfun membership** even when some pool rows are outside the 180-second freshness window. That unblocks the path for a future operator-authorized 7B.6 live proof to pass Tracker normalize without accepting stale authority or widening discovery authority.

## What Remains Unproved

- Live 7B.6 re-proof after this repair (not authorized in this lane)
- Combined live-input multi-provider executor on live captures
- Live create-decode yield under busy Pump Program RPC
- Live PumpSwap confirmation path
- Activation review, command publication, pilot
- Retrieval, paper decisions, BUY/SELL/HOLD, positions, PnL

## Remaining Locks

Unchanged V1 locks remain:

- Solana-only / memecoin-only / paper-only
- no live wallet, private keys, funds, live execution
- no paid API dependency
- no scoring/ranking/confidence/weighted systems
- no engine bypass of Source Governor or Central Scheduler
- no dirty memory for decisions
- no BUY/SELL/HOLD unlock
- provider `pumpfun` labels remain unverified origin
- 180-second Tracker freshness threshold not widened
- no stale row acceptance as authority

## Functionality Risks / Setbacks / Efficiency Blockers

- Empty-after-filter is factual emptiness, not market absence; operators must not treat empty as “no pumpfun market exists.”
- Mixed-age 1h lists may yield sparse valid rows; selection ceilings may still hit `INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL` for non-freshness reasons.
- Receipt clock skew still fails the whole response (by design).
- Malformed identity inside a mixed body still raises response-level (unchanged); only freshness is row-skip.
- Future live 7B.6 may still surface other schema drift not covered by this narrow repair.
- 7B.6 harness/closeout remain uncommitted evidence from the blocked run; they are not part of this repair commit.

## Files Changed (this lane)

- `src/printer_v1/sources/secondary_discovery.py`
- `tests/test_v2_9_7d_7b_4b_1_solana_tracker_row_freshness.py` (new)
- `tests/test_v2_9_7d_7b_4b_secondary_discovery_adapters.py`
- `tests/test_secondary_discovery_contract_fixtures.py`
- `docs/printer-v1-v2-9-7d-7b-4b-1-solana-tracker-row-freshness-repair-closeout.md` (new)

## Files Explicitly Not Committed / Not Modified for Commit

- `tests/proof_v2_9_7d_7b_6_bounded_live_source.py` (remains uncommitted)
- `docs/printer-v1-v2-9-7d-7b-6-bounded-live-source-proof-closeout.md` (remains uncommitted)

## Stop Boundary

V2-9.7D.7B.4B.1 stops at this repair closeout. No live proof, activation review, command publication, pilot, or next discovery lane was started.
