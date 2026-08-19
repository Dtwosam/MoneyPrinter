# Printer V1 V2-9.8B Cycle-2 Historical Direct-Proof + Diagnostic Durability Corrective Closeout

Date: 2026-08-19

## Authority and baseline

This closeout is governed by the active Printer V1 source stack and `CURRENT_HANDOFF.md`. It closes only the approved V2-9.8B corrective work on draft PR #191.

- executable base: `f40210f439d3e8366369e7c919dc9dd011868cb3`
- branch: `agent/v2-9-8b-cycle2-historical-proof-carrier-provenance-repair`
- PR: `#191`, draft, unmerged
- last production-code/cleanup HEAD before this closeout document: `35d064c0f5a11a6f091bd9e27c777197516087c2`

No campaign authorization was created or reused. Printer was not run.

## Defects closed

### 1. Historical graduated direct-proof carrier truncation

The consumed Cycle-2 failure was caused by historical `PUMPSWAP_GRADUATED_CONFIRMED` candidates losing immutable direct-Pump/PumpSwap graduation proof after current market refresh, then reaching source-specific admission without the proof required by the existing direct-Pump authority contract.

The repair preserves the original graduated-supply owner byte-for-byte as `_graduated_supply_front_door_base.py` and uses the public wrapper to rejoin immutable registry proof only for exact historical direct candidates. It does not relabel `MARKET_PRESENT_POOL`, fabricate origin evidence, add source calls, or weaken any gate.

### 2. Graduated-supply diagnostic durability

Typed `GraduatedSupplyError` already carried bounded categorical context, but terminalization persisted only the category. The repair preserves the original Scheduler implementation as `_scheduler_base.py` and uses the public Scheduler compatibility adapter to override only `fail_job`.

For the unique matching RUNNING `PRE_ADMISSION_DISCOVERY_SELECTION` job, a typed graduated-supply failure can stage an allowlisted, bounded diagnostic envelope. `fail_job` durably stores that envelope in `printer_scheduler_jobs.last_error` while the Scheduler observer and pre-admission attempt continue to use the unchanged categorical terminal cause.

Durable diagnostic keys are limited to:

- `failure_code`
- `stage`
- `mint`
- `pool`
- `admission_authority`
- `nomination_source`

No traceback, provider body, arbitrary exception message, credentials, wallet material, or uncontrolled attributes are persisted.

## Proof

The corrected RED proof reached the intended behavioral seam and failed only because `last_error` still contained the categorical string rather than the bounded JSON diagnostic envelope: `1 failed, 2 passed`.

Final GREEN proof on the repaired branch:

- changed production modules compile successfully;
- Cycle-2 diagnostic + historical-carrier regressions: `7 passed in 4.57s`;
- bounded existing Scheduler compatibility suite: `25 passed in 18.02s`;
- `git diff --check`: clean.

The final compatibility run was GitHub Actions run `32295818364` on the temporary proof PR.

Temporary proof PR `#195` was closed without merge after evidence capture. The temporary workflow was removed from the product branch, and the disposable proof-base branch was reset to the pre-proof commit.

## Unchanged locks

No Migration 059. No new provider or paid API. No Source Governor bypass. No Central Scheduler bypass. No retries or endpoint rotation were added. The `$3,000` liquidity floor, freeze depth 4, neutral deterministic selection, Cycle-1/Cycle-2 disjointness, two-slot Cycle-2 contract, Solana-only / memecoin-only / paper-only scope, and `WINDOW_5M_MICRO_EVENT` support-only law remain unchanged.

Retrieval, BUY/SELL/HOLD, positions, trade events, audits, PnL, 12h and 24h remain locked.

## Verdict

`V2_9_8B_CYCLE2_HISTORICAL_DIRECT_PROOF_AND_DIAGNOSTIC_DURABILITY_IMPLEMENTATION_CLOSEOUT_PASS`

This PASS closes implementation and bounded proof only. It does not merge PR #191, authorize a new campaign, or make any consumed authorization reusable.

## Exact next permitted action

Independent review / operator adoption review of draft PR #191 against the exact branch head and this closeout.

If PR #191 is lawfully adopted, the exact adopted executable commit must enter a fresh post-repair two-cycle/four-token readiness lane before any later authorization-preparation lane.