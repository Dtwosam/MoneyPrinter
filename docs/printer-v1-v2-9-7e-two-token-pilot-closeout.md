# V2-9.7E Two-Token Operational Memory Factory Pilot Closeout

**Status:** BLOCKED  
**Lane:** V2-9.7E — Two-Token Operational Memory Factory Pilot  
**Date:** 2026-07-21  
**Baseline HEAD:** `78978ea4222f699dd1d280c39ad4d9594f08d271`

## Verdict

`V2_9_7E_PILOT_BLOCKED`

**Block reason:** `INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL`

The authorized pilot **preflight passed** and **exactly one** discovery campaign
ran under Source Governor and Central Scheduler ownership. Fewer than two
eligible tokens qualified under committed origin, freshness, and gate rules.
Zero slots were activated. Rules were **not** weakened to force yield.

This is **not** successful two-token memory growth.

## Todo / Checklist

- [x] Verify exact HEAD `78978ea4222f699dd1d280c39ad4d9594f08d271`.
- [x] Confirm pilot target absent at start; use only `data/printer_v1_v2_9_7e_pilot.sqlite3`.
- [x] Leave `data/printer_v1.sqlite3` unmodified.
- [x] Preflight: migrations 034, integrity/FK, backup/restore, provenance, locks, free sources.
- [x] Persist `V2_9_7E_PREFLIGHT_PASS`.
- [x] One bounded live discovery + combined selection attempt.
- [x] Persist `INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL` with zero activation.
- [x] Write this closeout.
- [ ] Two-token WINDOW_15M / continuation / 4h / 5m / clean promotion — **not reached**

## Preflight

**Verdict:** `V2_9_7E_PREFLIGHT_PASS`

| Check | Result |
|---|---|
| HEAD exact | `78978ea4222f699dd1d280c39ad4d9594f08d271` |
| Tracked tree clean | yes |
| Foreign Printer process / active lease at start | none observed |
| `SOLANA_TRACKER_API_KEY` | PRESENT (value never printed) |
| Free / read-only / wallet-free sources | confirmed |
| Pilot target created | `data/printer_v1_v2_9_7e_pilot.sqlite3` |
| Migrated through `034` | yes; ledger matches repository |
| Integrity / FK | ok / 0 |
| Backup + disposable restore rehearsal | READY (backup retained under `operator-runs/v2-9-7e-pilot/backups/`) |
| Git provenance | captured; tracked clean; untracked present (local noise only) |
| Two slots / seed / ceilings frozen in config | yes |
| Governor admissions for pilot kinds | all allowed |
| Internal DI entry | lease + `CombinedPumpfunCampaignExecutor` + cleanup |
| Public PowerShell published | no |
| Report dir outside DB | `operator-runs/v2-9-7e-pilot/reports` |
| Locked capability counts on fresh target | all zero |

Evidence file (local, not committed):  
`operator-runs/v2-9-7e-pilot/V2_9_7E_PREFLIGHT.json`

## Pilot execution (exactly one)

| Field | Value |
|---|---|
| Started (post-preflight) UTC | `2026-07-21T14:26:45Z` |
| Finished UTC | `2026-07-21T14:26:51Z` |
| Campaign attempt | one (timestamped campaign id under pilot DB) |
| Rerun / successor / auto-restart | none |
| Source Governor used | true |
| Central Scheduler used | true |

### Live intake (redacted)

| Provider | Result |
|---|---|
| Direct Pump / public RPC | 4 signatures; **zero decoded creates**; gaps `FAILED_TRANSACTION`×4; continuity GAPPED |
| DexScreener | 5 Solana pairs (identity only; no origin authority) |
| GeckoTerminal | 20 trending normalized |
| Solana Tracker | HTTP 200 both; **0** normalized after row-level freshness filter |
| PumpPortal / Pumpdev | zero requests |

RPC ops in capture: 5 (within ceiling). No secret material logged.

### Selection / activation

| Field | Value |
|---|---|
| Terminal status | `FAILED` |
| First terminal cause | **`INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL`** |
| Slot count | **0** |
| Tracking queue | **0** |
| WINDOW_15M jobs | **0** |
| Partial activation | **none** |
| Source calls (executor) | 4 |
| Scheduler work | 9 |
| Successor / restart | false / false |
| Locked financial table deltas | **zero** |

## Why PASS criteria were not met

Authorized PASS required two terminally audited 15m windows, continuation split,
a reconciled 4h path, clean promotion, and 5m trigger/no-capture proofs. Those
stages **require two eligible activated tokens**.

Eligible activation requires **direct finalized Pump origin** among other fixed
gates. This pilot’s live direct page produced **zero successful create decodes**
(all four transaction references failed decode / failed transaction). Secondary
providers alone cannot establish origin. Tracker contributed zero fresh pumpfun
rows after the 180-second row-level filter.

Therefore the committed two-or-none rule correctly activated **none**.

## Safe stop

- No tracking windows executed.
- No memory windows created as main outcomes.
- No 5m support path.
- No replacement attempt.
- No successor campaign; no automatic restart.
- `data/printer_v1.sqlite3` size unchanged (not opened for write by pilot).
- Pilot DB retained locally for audit; **not committed**.

### Cleanup note

Supervision cleanup raised `IntegrityError: campaign cycle requires exactly two
token slots` because the insufficient-pool path leaves zero slots while cleanup
expects a two-slot cycle structure. Discovery first-fault cause remained
`INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL`. This is recorded as a **functionality risk**
for a future narrow repair if cleanup must tolerate insufficient-pool cycles; it
did **not** create partial activation or restart.

### Abstract-command composition note

7A `handle_abstract_command` preflight requires every cycle to already have
exactly two token slots. INITIAL discovery **creates** those slots on handoff.
The pilot therefore composed **lease → CombinedPumpfunCampaignExecutor.execute →
cleanup** under Governor/Scheduler ports (same owners as CommandServices) for
INITIAL discovery. A future repair may align 7A preflight with INITIAL vacant
cycles; that is not required to explain this yield block.

## Production change prohibition

No production code, migrations, schemas, or provider contracts were modified.

Operator-run harness (local, not production package):

- `operator-runs/v2-9-7e-pilot/run_v2_9_7e_pilot.py`

## Money-usefulness contribution

The pilot proved the fail-closed two-or-none gate under live free sources on an
approved isolated target after full preflight: when origin-eligible candidates
are insufficient, Printer **does not** invent two tokens, **does not** partially
activate, and **does not** open tracking windows. That protects corpus honesty
more than raw row growth.

## What remains unproved / next

- Live dual activation of two origin-eligible tokens
- WINDOW_15M dual terminal audits
- Continuation vs non-continuation split
- Terminally reconciled 4h path
- Authoritative clean promotion
- Support-only 5m trigger + no-capture under campaign ownership
- Full lease cleanup path on insufficient-pool cycles (see risk above)

## Remaining locks

All V1 locks remain: no retrieval, decisions, BUY/SELL/HOLD, positions, trades,
PnL, wallets, signing, live execution, paid APIs, scoring, 12h/24h, public
PowerShell command (V2-9.8A), or automatic restart.

## Functionality Risks / Setbacks / Efficiency Blockers

- Live Pump Program create-decode yield can be zero on a bounded signature page
  (this run: four failed transactions).
- Tracker 1h lists can normalize empty under 180s row freshness.
- Secondary identity intake without origin cannot force eligibility.
- 7A preflight vs INITIAL vacant-slot discovery composition friction.
- Supervision cleanup assumes two-slot cycles even on insufficient-pool failure.
- Full PASS bar (15m + 1h/4h + 5m + clean promotion) remains multi-hour and
  yield-dependent after dual activation exists.

## Artifacts (do not commit)

| Artifact | Path |
|---|---|
| Pilot DB | `data/printer_v1_v2_9_7e_pilot.sqlite3` |
| Backup | `operator-runs/v2-9-7e-pilot/backups/` |
| Preflight JSON | `operator-runs/v2-9-7e-pilot/V2_9_7E_PREFLIGHT.json` |
| Pilot result JSON | `operator-runs/v2-9-7e-pilot/V2_9_7E_PILOT_RESULT.json` |
| Harness | `operator-runs/v2-9-7e-pilot/run_v2_9_7e_pilot.py` |

## Stop boundary

V2-9.7E stops at this blocked outcome. No second pilot, no production repair in
this lane, no V2-9.7F activation, no V2-9.8 command publication.
