# Printer V1 — V2-9.8B WINDOW_15M Continuous Graduated-Supply Evidence Repair Closeout

**Date:** 2026-08-05  
**Lane:** `V2-9.8B — WINDOW_15M Continuous Graduated-Supply Evidence Completion`  
**Branch:** `agent/v2-9-8b-window-15m-continuous-supply-evidence-repair`  
**Baseline HEAD:** `c363879023d6f66ef02ec4b14079e8c737020550`  
**Baseline branch:** `agent/v2-9-8b-window-15m-final-integrated-readiness-repair`

## Final verdict

`V2_9_8B_WINDOW_15M_CONTINUOUS_SUPPLY_EVIDENCE_REPAIR_BLOCKED`

PASS requires one uninterrupted wrapper→operational child→activation preflight→ordinary discovery→four-candidate reserve→2+2 freeze→atomic handoff→Scheduler→two 900-second windows→Lane K→clean memory proof. Continuous wrapper path still fails before two-slot handoff.

## Exact baseline and final commit

| Fact | Value |
|---|---|
| Baseline HEAD | `c363879023d6f66ef02ec4b14079e8c737020550` |
| Final commit | `4fca7518bf73d64e49b8163c1aef4e38dca372f4` |
| Branch | `agent/v2-9-8b-window-15m-continuous-supply-evidence-repair` |
| Ancestry | Created from baseline; no foreign worktree |

## Failing stage before repair (Phase 1)

| Fact | Value |
|---|---|
| Terminal cause | `CampaignSixUnitError:SIX_UNIT_STAGE_EVIDENCE_MALFORMED:EMPTY_STARTED_STAGE_EVIDENCE` |
| Root cause | Frozen exact-market / residual transports returned provider data without `TransportOperationIdentity` |
| Measured transport count at seal | 0 |
| Seal contract | Correct — not weakened |

## What was repaired (useful progress)

### Frozen production-transport architecture

`tests/support/window_15m_measured_frozen_transports.py`:

* `NetworkFreezeBundle` freezes network seams beneath production constructors:
  * `direct_pump_migration._rpc_post` / `pump_migration._rpc_post`
  * `solana_rpc_holder._rpc_post`
  * `dexscreener._dexscreener_http_get_json`
  * `urllib.request.urlopen` (JSON-RPC POST + residual HTTPS)
* Four unique pinned-style migration cases (fixed withdraw authority; skip fixture mint index 2)
* Lawful GeckoTerminal new_pools bodies (fresh timestamps)
* Lawful DexScreener pair/profile/batch bodies
* Lawful PumpSwap `getMultipleAccounts` envelope (`context` + `value`)
* Lawful holder `getTokenLargestAccounts` / `getTokenSupply`
* Lawful GoPlus mint-keyed token security bodies
* Explicit `measured_frozen_payload` / `measured_frozen_transport` helpers (fallback path)

### Production identity fixes (narrow, non-weakening)

1. **`coerce_migration_transport`** in `direct_migration_discovery.py`  
   Shared WINDOW_15M composition returns a preflight **adapter**; discovery needs the inner **transport** callable. Without unwrap: `PROVIDER_FAILURE` / empty migration.

2. **Local validation identities on DIRECT_MIGRATION seal**  
   Each PumpSwap verification emits a `LocalValidationIdentity` so campaign V2 aggregation does not mix bare integers with identity lists.

3. **CampaignSixUnitOwner.durable_evidence V2 counters**  
   When identity-mode is active for a non-transport unit, the counter is derived from the identity list (matches seal contract; avoids `SIX_UNIT_EVIDENCE_IDENTITY_COUNT_MISMATCH:local_validation_identities`).

### Continuous proof structure

* Actual one-shot wrapper → actual operational child module
* Activation preflight not patched out
* Ordinary `OPERATIONAL_GRADUATED_SUPPLY_KWARGS` restored (locator / permanent_availability / gecko nomination on)
* Production migration constructor path (not `migration_transport=None`, not plain `object()`)
* Controlled clock for 900s lifecycle injection
* Measured context factories for GoPlus / solana_rpc_holder holder-stage costs

### Focused tests

```bash
.venv/bin/python -m pytest \
  tests/test_v2_9_8b_window_15m_continuous_supply_evidence_repair.py -q
```

**Result: 7 passed**

Including: measured identity shape, production dex/migration freezes, plain unmeasured seal still fails `EMPTY_STARTED_STAGE_EVIDENCE`, four unique migration cases, duplicate identity rejection.

## Transport-by-transport frozen evidence matrix (ordinary path)

| Stage / provider | Seam | Measured owner | Status under freeze |
|---|---|---|---|
| DexScreener fresh profiles + mint batch | `_dexscreener_http_get_json` / urlopen | production dexscreener transport | LOCATOR seals (2 ops) |
| Direct Pump live-tail signatures + txs | `_rpc_post` (direct_pump / pump_migration) | production migration normalizer | DIRECT_MIGRATION seals (5+ ops) |
| PumpSwap signature pool resolution | same RPC freezes | production graduation verifier | included in DIRECT_MIGRATION |
| GeckoTerminal new pools | urlopen | production gecko attach | FRESH_POOL_NOMINATION seals |
| PumpSwap pool account batch | urlopen JSON-RPC | production account-batch transport | PROTOCOL_CONFIRMATION seals |
| GoPlus safety | urlopen (or fixture with `underlying_operation_count`) | production / fixture | holder stage |
| Solana RPC holder | `_rpc_post` / fixture | production / fixture | holder stage |

Isolated `build_graduated_supply` under freezes + production adapter:

* **ready=True**, `GRADUATED_SUPPLY_READY`
* 4 graduated registry rows, 4 graduation proofs, 4 holder-reserve carriers, 2+2 selection ready
* Stages sealed: LOCATOR, DIRECT_MIGRATION, FRESH_POOL_NOMINATION, PROTOCOL_CONFIRMATION

## Stage-by-stage six-unit totals (isolated supply, typical)

| Stage | Terminal | Transport ops (approx) |
|---|---|---|
| LOCATOR | COMPLETED | 2 |
| DIRECT_MIGRATION | COMPLETED | 13 (5 migration + 8 pumpswap) |
| FRESH_POOL_NOMINATION | COMPLETED | 1 |
| PROTOCOL_CONFIRMATION | COMPLETED | 1 |
| **Campaign continuous (before handoff)** | BLOCKED | SOURCE_TRANSPORT_OPERATION≈17, LOCAL_VALIDATION_STEP=8 |

## Four-candidate reserve and 2+2 (isolated)

* Four unique Solana memecoin mints from fixture indices 0,1,3,4  
* Four exact PumpSwap pools (canonical PDA)  
* Four production graduation proofs  
* Selection: two selected + two alternates ready (`SELECTION_TWO_TOKEN_READY`) under ordinary authority  
* Continuous path: **does not yet persist two slots** (blocked before handoff)

## Next exact first blocker (continuous wrapper path)

```text
PRE_LIFECYCLE_DISCOVERY_SELECTION_COVERAGE_INSUFFICIENT
```

### Attribution

After supply readiness and holder-context collection:

1. `CampaignOperationLedger.candidate_cap()` under ordinary supply load is **3**  
   (`available_before_reservation // HOLDER_WORST_CASE_TRANSPORT_OPERATIONS`, ceiling 45, worst-case 5).
2. Freeze admission requires **`MINIMUM_FREEZE_DEPTH = 4`** MEMORY_OBSERVATION_ELIGIBLE candidates.
3. Only capped graduated candidates enter holder → observation freeze → coverage blocker.

So ordinary continuous supply + permanent freeze-depth 4 is **budget-incompatible** with the current 45-op holder ledger once ~12 supply source operations are charged.

Earlier continuous blockers that **were** cleared on this branch:

* `EMPTY_STARTED_STAGE_EVIDENCE` (unmeasured freezes)
* `PROVIDER_FAILURE` (adapter-as-transport)
* Gecko empty-stage seal (empty unmeasured failure path)
* Protocol account-batch envelope incomplete
* Stale gecko evidence timestamps
* `SIX_UNIT_EVIDENCE_IDENTITY_COUNT_MISMATCH:local_validation_identities`
* `CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH` / `HOLDER_TRANSPORT_IDENTITY_ABSENT` (holder measured costs)

## Lifecycle and clean-memory evidence

| Requirement | Continuous result |
|---|---|
| Wrapper → child once | Yes |
| Authorization once | Yes |
| Two token slots | **No** (0) |
| Two WINDOW_15M 900s | **No** (0) |
| Two CLEAN_MEMORY + fingerprints | **No** (0) |
| Zero external network escapes | Yes (frozen hosts only) |
| Authoritative DB | Unchanged (never mutated) |

## Tests and proof results

| Suite | Result |
|---|---|
| Focused continuous-supply-evidence repair | **7 passed** |
| Continuous wrapper-to-memory proof | **Failed** — `PRE_LIFECYCLE_DISCOVERY_SELECTION_COVERAGE_INSUFFICIENT` |
| Broad regression | Not run (continuous still blocked; risk-based order) |

## Proof artifact paths and hashes

Retained under `~/PrinterOperations/v2-9-8/final-integrated-proofs/` (disposable-run summaries only; no two-slot success path):

* `V2_9_8B_WINDOW_15M_FINAL_INTEGRATED_CONTINUOUS_PROOF_V1_* / proof_summary.json`
* Typical: `token_slots=0`, `window_count=0`, `clean_episodes=0`

## Authoritative DB before/after identity

Unchanged throughout (no real authorization, no live write to authoritative path). Continuous work uses disposable `repo/data/printer_v1.sqlite3` only.

## Money-usefulness contribution

* Restores the only lawful path to measure ordinary graduated supply under freezes without inventing transports.
* Unblocks stage sealing for migration / exact-liquidity / protocol confirmation.
* Surfaces the **real** next budget/freeze-depth incompatibility instead of empty-ledger false failures.

## What improved

* Production freezes emit real measured identities.
* Adapter/transport composition mismatch fixed at discovery boundary.
* V2 local-validation identity aggregation consistency improved.
* Continuous proof exercises ordinary kwargs and production migration constructor.

## What remains locked

* Solana-only, paper-only, no scoring/ranking/confidence, no live wallet/keys, no Source Governor / Scheduler bypass, no 1h/4h/12h/24h production work, no retrieval / paper decision / BUY-SELL-HOLD, no automatic retry/successor, no real authorization, no live provider calls, no authoritative DB mutation.
* Six-unit seal not weakened; empty started stages still fail closed.

## Proof limitations

* Continuous PASS not achieved; lifecycle / Lane K / clean memory not exercised continuously.
* Holder budget vs four-observation freeze depth not redesigned (out of narrow evidence-repair scope once accounting seal works).
* Snapshot readiness freezes may still need extension after freeze-depth is resolved.

## Functionality Risks / Setbacks / Efficiency Blockers

| Item | Notes |
|---|---|
| **FR** | Ordinary continuous path charges enough source ops that holder `candidate_cap` falls below freeze depth 4. |
| **Setback** | Continuous still blocked after multi-layer freeze repair; cannot authorize. |
| **Efficiency** | Full continuous runs are multi-second; diagnosis used one repro + isolated supply + recon capture (not broad suite loops). |

## Recommended next lane (do not weaken accounting)

1. Reconcile `MINIMUM_FREEZE_DEPTH=4` with `CampaignOperationLedger.candidate_cap` under ordinary supply load **without** inventing transports or lowering seal rules — e.g. charge true measured transports into the holder ledger (not whole request counts), or adjust permanent-path admission ordering so four observation-eligible rows are freezable within the existing 45-op ceiling.
2. Then re-run one continuous proof for 2+2 handoff + 900s + Lane K.
3. Independent read-only review before any real authorization.

## Design document

`docs/printer-v1-v2-9-8b-window-15m-continuous-supply-evidence-repair-design.md`
