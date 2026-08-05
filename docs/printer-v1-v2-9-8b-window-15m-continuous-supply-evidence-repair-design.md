# Printer V1 — V2-9.8B WINDOW_15M Continuous Graduated-Supply Evidence Repair Design

**Date:** 2026-08-05  
**Lane:** `V2-9.8B — WINDOW_15M Continuous Graduated-Supply Evidence Completion`  
**Branch:** `agent/v2-9-8b-window-15m-continuous-supply-evidence-repair`  
**Baseline:** `c363879023d6f66ef02ec4b14079e8c737020550`

## Design verdict

`V2_9_8B_WINDOW_15M_CONTINUOUS_SUPPLY_EVIDENCE_REPAIR_DESIGN_PASS`

## Phase 1 — Blocker attribution (from blocked continuous proof)

| Fact | Value |
|---|---|
| Terminal cause | `CampaignSixUnitError:SIX_UNIT_STAGE_EVIDENCE_MALFORMED:EMPTY_STARTED_STAGE_EVIDENCE` |
| Campaign identity | created (configuration/run/cycle/supervision rows present) |
| Governed source requests | 5 request/response pairs recorded |
| Graduated floor rows | 4 inserts (`printer_graduated_market_floor_state`) |
| Token slots / windows / episodes | 0 (handoff not reached) |
| Measured transport count at seal | 0 (empty ledger) |
| Seal contract | Correct — do not weaken |

### Root cause

Frozen exact-market / migration callables returned **normalized provider data only**. Production stage sealing requires every started stage to contribute at least one six-unit component via `MeasuredTransportLedger`. Production transports attach identities with `build_transport_identity` + `measured_payload_fields` (or normalizers that emit `transport_operation_identities`). Plain frozen callables omit those fields, so:

1. a governed source request starts the stage (`stage_started=true`);
2. `record_payload_transports` finds zero identities;
3. totals remain all-zero;
4. `seal_campaign_stage_evidence` fails with `EMPTY_STARTED_STAGE_EVIDENCE`.

Responsible frozen surfaces in the blocked proof:

* `frozen_dex_factory` / `frozen_dex_batch_factory` (plain pair dicts);
* `empty_migration_transport` when used as a non-production replacement that does not pass through production measured attachment (and/or subsequent stages started without measured payloads).

## Repair architecture

### Prefer production network freezes

Keep production constructors:

* `build_direct_pump_migration_transport` / normalizer;
* `build_graduation_verifier_transport` / PumpSwap confirmation path;
* `build_dexscreener_*` transports;
* ordinary Gecko / holder / safety / Jupiter constructors as reached.

Freeze **below** those constructors:

| Seam | Module path | Purpose |
|---|---|---|
| Solana JSON-RPC | `direct_pump_migration._rpc_post`, `pump_migration._rpc_post` | signatures, transactions, accounts |
| DexScreener HTTP | `dexscreener._dexscreener_http_get_json` | profiles, mint batch, exact pair |
| Residual HTTPS | `urllib.request.urlopen` | Gecko/Coingecko/GoPlus/Jupiter/Helius empty lawful bodies |

Production transports then emit exact measured identities themselves.

### Explicit measured helper (fallback only)

`tests/support/window_15m_measured_frozen_transports.py` provides:

* `measured_frozen_payload` / `measured_frozen_transport` using `build_transport_identity` + `measured_payload_fields`;
* truthful `response_bytes` from deterministic JSON body;
* truthful `normalized_rows` from frozen list members;
* unique identity per invocation ordinal.

Used only when a low-level seam cannot be frozen safely; never as a post-hoc identity synthesis from `printer_source_requests`.

### Ordinary supply kwargs restored

Continuous proof uses production `OPERATIONAL_GRADUATED_SUPPLY_KWARGS` without forcing:

* `permanent_availability=False`
* `run_geckoterminal_nomination=False`
* `run_locator=False`

Stages that start receive measured frozen bodies. Stages with true pre-operation no-work use existing `PRE_OPERATION_NO_WORK` only when production does not create a governed request.

### Four candidates

Built from four distinct pinned-style migration fixtures (fixture mints from capacity fixture), not as preassembled graduation_proofs and not as the sole authority of pre-seeded graduated registry rows. Production migration + verification + exact-liquidity paths produce four `MEMORY_OBSERVATION_ELIGIBLE` candidates and 2+2 freeze.

## Hard locks preserved

No real authorization, no live network, no authoritative DB mutation, no seal relaxation, no Source Governor / Scheduler bypass, no scoring/ranking/confidence.

## Implementation sequence

1. Measured freeze support module  
2. Focused identity + seal tests  
3. Continuous proof rewrite  
4. Closeout  

## Post-implementation continuous blocker (after EMPTY_STARTED cleared)

With measured freezes and ordinary supply, continuous still fails:

`PRE_LIFECYCLE_DISCOVERY_SELECTION_COVERAGE_INSUFFICIENT`

Root: `CampaignOperationLedger.candidate_cap()` ≈ 3 under ordinary supply charge, while `MINIMUM_FREEZE_DEPTH = 4`. Not a seal relaxation; next lane must reconcile freeze depth with the 45-op holder budget.

See closeout for full matrix and evidence.
