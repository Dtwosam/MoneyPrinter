# Permanent Discovery Conversion Repair Implementation Plan

> **For agentic workers:** Execute inline in this session. Checkbox tracking below.

**Goal:** Repair D1 (migrate validation ≠ shared source failure), D2 (stage cursor stranding market batches), and D3 (solitary market-ready cannot enter holder/safety), plus protocol queue processing, correct terminals, and sealed diagnostics.

**Architecture:** Keep `run_persistent_eligible_token_supply` as the permanent funnel owner. Replace global stage rewind with seal-gated `StageBudget`. Treat `direct_pump_migration_rejected_*` as candidate-local. Process protocol-due identities under protocol capacity. Open holder evaluation for ≥1 market-ready survivor under permanent mode while still requiring four fully eligible before selection.

**Tech Stack:** Python 3.12, pytest, SQLite disposable fixtures, existing Source Governor / Pump / Dex / Gecko owners.

## Global Constraints

- Flat ceiling remains **30**; reservations **3/2/6/7/8/4**.
- Never relax `exactly_one_migrate_instruction_required`.
- Never lower $3,000 floor or weaken holder/safety/STNP/cooldown/identity rules.
- No retries, successors, paid sources, ranking, scores, or live provider runs.
- No migration unless static inspection proves schema gap (none expected).

## Owner classification

| Owner | Change |
|---|---|
| `sources/pump_contracts.py` decode | CODE_DEFECT (missing rejection digest) |
| `sources/direct_pump_migration.py` failure payload | CODE_DEFECT (no digest) |
| `discovery/direct_migration_discovery.py` | ALREADY_CORRECT (skips rejected_* from source_failures) |
| `discovery/eligible_token_supply.py` failure aggregation | CODE_DEFECT (counts all failures as shared) |
| `discovery/permanent_discovery_availability.py` StageBudget | CODE_DEFECT (global rewind) |
| permanent market loop protocol charge timing | CODE_DEFECT |
| protocol queue processing | CODE_DEFECT (queue not processed) |
| campaign `<2` pre-holder gate | CODE_DEFECT |
| selection/handoff | ALREADY_CORRECT |

---

### Task 1: Rejection digests + candidate-local classification

**Files:** `pump_contracts.py`, `direct_pump_migration.py`, `eligible_token_supply.py`

- [x] Decode builds bounded digest (signature, instruction counts, migrate match count, mint identities, reason)
- [x] Failure payload carries `migration_rejection_digest` + outcome `MIGRATION_EVIDENCE_REJECTED`
- [x] Eligible supply excludes `direct_pump_migration_rejected_*` from provider_failures / channels_unavailable
- [x] True transport failures still mark channel unavailable

### Task 2: Seal-gated StageBudget + multi-round market

**Files:** `permanent_discovery_availability.py`, `eligible_token_supply.py`

- [x] StageBudget: `seal`, seal-gated `available`, no rewind exception for unsealed peer stages
- [x] `advance(stage)` seals all earlier stages (compat with existing tests)
- [x] Permanent loop: charge migration to protocol without sealing market; multiple market batches; seal stages when work exhausted
- [x] No budget-exhaustion terminal from stage-order exceptions while capacity remains

### Task 3: Protocol-confirmation queue

**Files:** `permanent_discovery_availability.py`, `eligible_token_supply.py`

- [x] Fresh supported nominations enter PROTOCOL_CONFIRMATION_DUE queue
- [x] Process bounded protocol work under protocol capacity (mark outcomes; unsupported venues stay blocked)
- [x] Do not activate Meteora or auto-accept pump-fun alternate pools

### Task 4: Incremental holder/safety

**Files:** `authoritative_live_operational_campaign.py`

- [x] Permanent mode: remove hard skip when `len(graduated_candidates) < 2`
- [x] Run holder when ≥1 market-ready; target 4 fully eligible
- [x] Selection still requires four fully eligible before ready handoff

### Task 5: Terminals + diagnostics + tests + closeout

- [x] Terminal precedence ignores candidate-local migrate rejects
- [x] Diagnostics: stage used/remaining, queues, rejections, holder, reserves
- [x] Focused tests for all 15 proof points
- [x] Closeout + single commit

