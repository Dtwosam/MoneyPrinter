# Printer V1 — V2-9.7E.46B.2 Source-Accounting Reconciliation Closeout

**Verdict: `V2_9_7E_46B_2_ACCOUNTING_RECONCILIATION_PASS`.**

The E.46B.1 discrepancy (campaign `governed_requests = 22` against `21` distinct
durable `printer_source_requests` rows) was inspected read-only against the retained
proof database. **The suspected duplicated-locator cause is confirmed exactly**, and
every listed alternative was ruled out on evidence. A narrow accounting repair makes
the liquidity front door report only the exact request identities it created, and the
retained proof reconciles to a difference of **zero** under the corrected accounting.

- **Baseline commit:** `4335b65154092850ecd71b23cdcde8807b0dea00`
- **Proof artifact inspected:** `C:\Users\dtwof\PrinterPilot\E46B1\e46b1-readiness-20260724-b68977e\attempt.sqlite3`
  (opened `mode=ro`; SHA-256 `d74e7dd5827f4798dc3c2800d0ff4e25247ac3907d9c36bbfc31c4e075287eae`
  identical before and after — **unmutated**)
- **Date:** 2026-07-25
- No live readiness proof was run. No source call was made. No provider, endpoint,
  retry, ceiling, ordering, selection, floor, holder or readiness semantic changed.

## 1. Inspection evidence (Phase 1)

### 1.1 Exact source-request ledger

All 21 durable rows, each with its outcome and owning stage. Stage attribution comes
from the durable `request_key` namespaces created by the campaign
(`…-supply-*` = discovery, `…-market-liq-*` = front door,
`…-campaign-run:*` = holder funnel):

| id | source | request kind | outcome | owning stage |
|---:|---|---|---|---|
| 1 | dexscreener | `dexscreener_fresh_profiles` | resp#1 | **locator (discovery ns)** |
| 2 | pumpportal | `pumpfun_migration_stream` | resp#2 | discovery |
| 3 | pumpportal | `pumpfun_migration_stream` | FAIL#1 | discovery |
| 4 | pumpportal | `pumpfun_migration_stream` | resp#3 | discovery |
| 5–9 | pumpswap | `pumpswap_signature_pool_resolution` | resp#4–8 | discovery |
| 10 | dexscreener | `pair_market_snapshot` | FAIL#2 | front door |
| 11–15 | dexscreener | `pair_market_snapshot` | resp#9–13 | front door |
| 16 | goplus | `safety_reference` | resp#14 | holder funnel |
| 17 | solana_rpc | `holder_concentration_reference` | FAIL#3 | holder funnel |
| 18 | helius_free | `holder_concentration_reference` | resp#15 | holder funnel |
| 19 | goplus | `safety_reference` | resp#16 | holder funnel |
| 20 | solana_rpc | `holder_concentration_reference` | FAIL#4 | holder funnel |
| 21 | helius_free | `holder_concentration_reference` | resp#17 | holder funnel |

Stage totals: discovery **9** (locator 1 + migration 3 + PumpSwap verify 5),
front door **6**, holder funnel **6**. Every row carried transport (there is no
zero-transport row in this table).

### 1.2 How each figure was calculated

`authoritative_live_operational_campaign.py` builds the campaign ledger base from two
stage reports and then adds the holder funnel's governed requests:

```
supply_source_operations = discovery_report.source_operation_ledger.source_requests
                         + front_door_report.source_operation_ledger.liquidity_requests
ledger = build_ledger(pump_operations=0, additional_governed_operations=…)
governed_requests = base + holder governed requests
```

The two operands were **both whole-table totals**:

- `direct_migration_discovery._ledger_counts` →
  `SELECT COUNT(*) FROM printer_source_requests` (no filter at all).
  Evaluated at the end of discovery (after id 9) = **9**.
- `graduated_liquidity_front_door._dexscreener_ledger` →
  `SELECT COUNT(*) FROM printer_source_requests WHERE source_name='dexscreener'`
  (filtered by source only, not by stage or request kind).
  Evaluated at the end of the front door (after id 15) = **7**.

Therefore:

```
as-run   = discovery(9) + front_door(7) + holder(6) = 22   ← persisted ledger
durable  = 21 distinct rows
corrected= discovery(9) + front_door_own(6) + holder(6) = 21
```

`22` and `21` both reproduce exactly from the durable rows, so the arithmetic is fully
explained.

### 1.3 Hypothesis: **CONFIRMED**

All three proposed steps hold exactly:

1. The locator is included in the discovery report's whole-table total — it is
   executed by `build_graduated_supply` **before** `run_direct_migration_discovery`
   (stage order verified in `graduated_supply_front_door.py`: locator → discovery →
   front door), so it is already on the table when discovery counts.
2. The front-door total also includes that same locator, because the front door
   counted **all** rows where `source_name='dexscreener'`. Enumerated directly:

   | id | request kind | owned by front door? | request key |
   |---:|---|---|---|
   | 1 | `dexscreener_fresh_profiles` | **NO** | `e46b1-readiness-20260724-b68977e-supply-locator` |
   | 10–15 | `pair_market_snapshot` | yes | `e46b1-readiness-20260724-b68977e-market-liq-…` |

   Front-door contamination = exactly **1**.
3. The campaign adds both totals, producing the duplicated `+1`.

**Exact duplicated request identity:** durable row `id = 1`,
`request_key = e46b1-readiness-20260724-b68977e-supply-locator`,
`source_name = dexscreener`, `request_kind = dexscreener_fresh_profiles`.

### 1.4 Alternatives ruled out on evidence

| Alternative cause | Evidence | Ruled out |
|---|---|---|
| Missing durable request row | ids contiguous `1..21`, count 21 | ✔ |
| Approved request never persisted | as-run 22 fully explained as 9+7+6 with no unpersisted remainder; `pump_operations` and `enrichment.requested` contributed 0, and all 21 rows are stage-attributable | ✔ |
| Duplicate durable request identities | 0 duplicate `id`, 0 duplicate `request_key` | ✔ |
| Request lacking a required response/failure | 0 rows with neither; 0 rows with both; responses(17) + failures(4) = 21 exactly | ✔ |
| Zero-transport validation counted as a governed request | `zero_transport_operations = 9` is a fixed validation constant tracked in a separate ledger column; representing it as requests would need 30 rows, not 21 | ✔ |
| Another source or request kind | 0 `UNATTRIBUTED` rows; every row maps to discovery, front door or holder funnel; 0 orphan responses, 0 orphan failures | ✔ |

## 2. Root cause

Stage-local accounting was derived from whole-table totals. The liquidity front door
answered “how many DexScreener requests exist in this database?” when the campaign
contract needed “how many DexScreener requests did *this invocation* make?”. Because
the campaign sums disjoint stage totals, any overlap between them is charged twice —
here, the one fresh-profile locator that discovery had already counted.

This is a `COMMITTED_CODE_DEFECT` in reporting/accounting only. No source call,
eligibility decision, provenance label, selection, floor or holder verdict was ever
affected: the double count existed purely in the charged total.

**It was not cosmetic.** `build_ledger` seeds both `governed_requests` and
`underlying_transport_operations` from the same base, and `candidate_cap()` derives
from charged operations. The extra unit therefore consumed real candidate-search
depth:

| | base | charged | available | candidate cap |
|---|---:|---:|---:|---:|
| As-run (double counted) | 16 | 25 | 14 | **2** |
| Corrected | 15 | 24 | 15 | **3** |

E.46B.1's terminal report shows `candidate_cap: 2`; under corrected accounting the
same cycle would lawfully have supported 3.

## 3. Implementation

Narrow and confined to accounting.

**`src/printer_v1/discovery/graduated_liquidity_front_door.py`**

- `enrich_pool_liquidity(...)` gained an optional `on_request: Callable[[int], None]`,
  invoked with `execution.request_record.id` immediately after the governed execution
  and **before** any status branching — so a failed pair snapshot is charged exactly
  once, identically to a successful one.
- `run_graduated_liquidity_front_door` collects those exact durable identities into
  `stage_request_ids`.
- `_dexscreener_ledger(connection, *, request_ids)` now counts only those identities:
  `liquidity_requests` is the distinct identity count, and responses/failures are
  counted by `source_request_id IN (…)`. The whole-table `WHERE source_name=
  'dexscreener'` form is gone, with a comment recording why it must not return.

**`src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`**

- Comment only. Records the corrected contract at the summation site — each stage
  total must be disjoint, `discovery.source_requests` is the campaign's own rows so
  far (the canonical runner always prepares a fresh attempt target), and
  `front_door.liquidity_requests` is that invocation's own snapshots only.

Unchanged: source calls, providers, endpoints, retries, operation ceiling, request
ordering, discovery, selection, candidate-search depth policy, the `$3,000` floor,
holder evidence, readiness semantics, Source Governor / Central Scheduler ownership,
and lifecycle behaviour.

## 4. Focused tests

New: `tests/test_v2_9_7e_46b_2_source_accounting.py` — **10 passed** (fixtures and
isolated temporary databases only; no network, no persistent-DB mutation).

| Required proof | Test |
|---|---|
| One locator + N snapshots counted as exactly `1 + N` | `test_locator_plus_n_snapshots_is_exactly_one_plus_n` |
| Locator counted once | `test_locator_is_counted_exactly_once` (also pins that the old whole-table form returned `1 + N`) |
| Front door includes only its own `pair_market_snapshot` identities | `test_accounting_uses_only_own_pair_snapshot_identities` |
| Successful and failed snapshots each counted once | `test_successful_and_failed_snapshots_each_counted_once` |
| Unrelated earlier DexScreener rows do not contaminate | `test_unrelated_earlier_dexscreener_rows_do_not_contaminate` (3 earlier locator rows present) |
| No durable row lost or duplicated | `test_no_row_lost_or_duplicated` |
| Campaign accounting equals distinct durable set | `test_campaign_total_equals_distinct_durable_requests` (difference asserted `== 0`) |
| Candidate-cap arithmetic uses the corrected total | `test_candidate_cap_uses_corrected_total` (proves 2 → 3) |
| Selection and readiness outputs unchanged | `test_selection_outputs_unchanged`, `test_below_floor_candidate_still_rejected` |

Directly affected regressions, stop-on-first-failure, all green:

- E.43 front door + E.46B efficient two-token readiness: **41 passed**
- E.42 direct-migration discovery + E.44 full-pilot supply integration + E.45
  fresh-profile locator: **40 passed**
- `py_compile` on changed files: PASS. Changed-module import smoke: PASS.
  `git diff --check`: PASS.

Total: **91 passed**, 0 failed.

## 5. Read-only reconciliation of the retained E.46B.1 proof

Recalculated against the retained attempt database without mutation.

| Field | Value |
|---|---|
| Campaign request count (corrected) | **21** |
| Durable distinct request count | **21** |
| **Difference** | **0** |
| Campaign request count (as-run, defective) | 22 (difference `+1`) |

Requests by source and request kind:

| Source | Request kind | Count |
|---|---|---:|
| dexscreener | `dexscreener_fresh_profiles` | 1 |
| dexscreener | `pair_market_snapshot` | 6 |
| pumpportal | `pumpfun_migration_stream` | 3 |
| pumpswap | `pumpswap_signature_pool_resolution` | 5 |
| goplus | `safety_reference` | 2 |
| solana_rpc | `holder_concentration_reference` | 2 |
| helius_free | `holder_concentration_reference` | 2 |
| **Total** | | **21** |

Responses **17**, failures **4**, `17 + 4 = 21` — every request resolved exactly once.
Zero-transport operations **9**, tracked in a separate ledger column and never
represented as a source request. Corrected
`underlying_transport_operations` = 23 (was 24).

The proof database SHA-256 is identical before and after
(`d74e7dd5…87eae`) — the artifact was read `mode=ro` and **not mutated**. The expired
`PILOT_INPUT_READY` bundle was **not** reused operationally; this reconciliation
validates accounting only.

## 6. Money-usefulness contribution

The repair returns real candidate-search depth that the double count was silently
consuming: the same E.46B.1 cycle moves from `candidate_cap = 2` to `3`. Under the
E.46B combined pool, a deeper cap directly raises the probability that a lawful
two-token input set is found when early candidates fail liquidity or holder evidence —
exactly the failure mode that made E.46B.1 a PASS with no margin (two eligible tokens
out of six pooled, one liquidity request failing outright). It buys that headroom
without touching the `$3,000` floor, the holder gate, the ceiling, or any provider
behaviour. No memory, paper result, trade or profit claim is made.

## 7. What improved

- Each governed request is now charged exactly once; the campaign total equals the
  distinct durable campaign request set, asserted by test.
- Stage-local accounting is identity-based rather than whole-table, so it is immune to
  unrelated rows from other stages or earlier work in the same database.
- A failed pair snapshot is charged identically to a successful one — no accounting
  path depends on outcome.
- The honest E.46B.1 finding is closed with evidence rather than left open.

## 8. What remains locked

All permanent Printer V1 locks are untouched: Solana memecoin only, paper only, no
wallets/private keys/funds/live execution, no paid APIs, no
scoring/ranking/confidence/weighted logic, no Source Governor or Central Scheduler
bypass, no dirty memory for decisions, and no BUY/SELL/HOLD, positions, trade events,
paper audits or PnL unlock. V2-9.7E remains active; V2-9.7F was not started.

## 9. Proof still required later

- The corrected accounting is proven offline and reconciled against a retained
  artifact. Its **live** behaviour is observed only on the next separately authorized
  execution, where campaign `governed_requests` must equal the distinct durable
  request count with difference zero.
- The restored `candidate_cap = 3` has not been exercised live; a future cycle should
  confirm the deeper search actually vets a third candidate when one fails.

## 10. Functionality Risks / Setbacks / Efficiency Blockers

- **Residual finding (reported, not repaired):** `direct_migration_discovery.
  _ledger_counts` still reports `source_requests` as a whole-table
  `SELECT COUNT(*)`. On the canonical path this is correct — `prepare_pilot_target`
  refuses a non-fresh target, so the attempt database contains only this campaign's
  rows — and it is the campaign's intended “requests so far” base. But it would
  overcount on any reused database. It was left unchanged because the proven defect
  was the front door and narrow-scope discipline forbids widening a confirmed repair;
  the fresh-target precondition is now documented at the summation site.
- **Risk:** stage-local accounting depends on the front door observing every request
  it creates. `on_request` fires immediately after governed execution and before any
  branching, so all current paths are covered, but a future code path that executes a
  DexScreener request without the callback would under-count rather than over-count.
- **Setback:** the corrected `candidate_cap = 3` is arithmetic, not new supply. A
  cycle with few `$3,000+` graduates still blocks honestly.
- **Efficiency blocker:** none introduced. The identity-based ledger replaces three
  whole-table scans with two indexed `IN` lookups over a handful of ids.

## 11. Readiness for one separately authorized E.46 full pilot

**Ready.** The E.46B.1 readiness PASS stands — this lane changed no eligibility,
selection or readiness semantics, and the E.42/E.43/E.44/E.46B regressions confirm
behaviour is unchanged. The single honest finding recorded against that proof is now
closed with evidence, and the corrected accounting gives the next attempt one
additional unit of lawful candidate-search depth.

A separately authorized E.46 full-pilot attempt is therefore ready — and only ready.
This lane does not run that pilot, does not consume its authorization, and does not
unlock V2-9.7F. That attempt must obtain its own fresh readiness; the E.46B.1
`PILOT_INPUT_READY` bundle is expired and must not be reused.
