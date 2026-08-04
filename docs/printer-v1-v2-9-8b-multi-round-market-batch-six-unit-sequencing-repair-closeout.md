# V2-9.8B Multi-Round Market-Batch Six-Unit Sequencing Repair Closeout

Date: 2026-08-04

Lane: `V2-9.8B — Multi-Round Market-Batch Six-Unit Sequencing Repair`

Baseline: `6bfafe04ccfd2fd574ab08509f67c7951bbc7fca`  
(`Close post-conversion-repair 15m re-proof`)

Plan: `docs/superpowers/plans/2026-08-04-multi-round-market-batch-six-unit-sequencing-repair.md`

## Verdict

`V2_9_8B_MULTI_ROUND_MARKET_BATCH_SIX_UNIT_SEQUENCING_REPAIR_PASS`

Distinct logical mint-market batches now seal as `MINT_MARKET_BATCH|1`, `|2`, `|3`
without resetting after protocol work. Duplicate sealing of the same logical
batch still fails with existing six-unit duplicate-stage protection. No
authorization or live attempt was created.

## Exact root cause

`run_dexscreener_batch_market_resolution` hard-coded:

```text
stage_kind = MINT_MARKET_BATCH
stage_sequence = 1
```

when sealing six-unit stage evidence. The permanent multi-round path (and
protocol-resume market re-entry) called this function for each genuinely new
market round, so the second round attempted to reseal
`…|MINT_MARKET_BATCH|1` and the campaign owner raised:

```text
SIX_UNIT_STAGE_EVIDENCE_DUPLICATE_STAGE_ID:…|MINT_MARKET_BATCH|1
```

The six-unit **duplicate-stage protection was correct**. The permanent market
batch sealer was not allocating a durable monotonic sequence.

## Owner classification

| Owner | Classification | Action |
|---|---|---|
| Logical mint-market batch creation (`run_dexscreener_batch_market_resolution`) | `CODE_DEFECT` | Accept and seal with allocated `stage_sequence` |
| `stage_sequence` allocation | `MISSING_DURABLE_IDENTITY` | Allocate at request-key creation from durable `printer_source_requests.request_key` history |
| Six-unit stage identity (`build_campaign_stage_id`) | `ALREADY_CORRECT` | Unchanged |
| Stage evidence sealing / duplicate detection | `ALREADY_CORRECT` | Unchanged — still rejects duplicate stage_id |
| Market resume after protocol confirmation | `CODE_DEFECT` | Continues monotonic sequence (`protocol-resume-mbN`) |
| Campaign/run/cycle six-unit owner | `ALREADY_CORRECT` | Unchanged |

## Production changes

### Files

| File | Change |
|---|---|
| `src/printer_v1/discovery/permanent_discovery_availability.py` | Helpers for sequence parse/allocate/request-key/logical identity; sealer uses `stage_sequence` parameter (reconstructed from request key when omitted) |
| `src/printer_v1/discovery/eligible_token_supply.py` | Permanent rounds and protocol-resume allocate durable sequence before batch execution and pass it through |
| `tests/test_v2_9_8b_multi_round_market_batch_six_unit_sequencing.py` | Focused proofs |

### Logical identity and sequence rules

1. **Allocation point:** when a new logical market batch is created — before the governed request — via `next_mint_market_batch_stage_sequence(connection, request_key_prefix=…)`, which scans durable `printer_source_requests.request_key` values matching the prefix and returns `max(parsed)+1` (or 1).
2. **Durable request key embeds sequence:**
   - rounds: `{prefix}-mint-batch-r{N}`
   - protocol resume: `{prefix}-protocol-resume-mb{N}`
3. **Six-unit stage id:** `{campaign}|{run}|{cycle}|MINT_MARKET_BATCH|{N}`
4. **Content digest:** SHA-256 of sorted mint set verifies membership; **not** sole identity (same mint set in round 2 still has sequence 2).
5. **Logical batch id:** `{stage_id}|{digest[:16]}` attached to sealed evidence metadata.

### Replay / resume / duplicate behavior

| Case | Behavior |
|---|---|
| First distinct batch | sequence 1 |
| Second / third distinct batch | sequence 2 / 3 |
| Protocol work between rounds | does not reset counter (next allocate continues) |
| Replay same sequence + same stage_id | existing `DUPLICATE_STAGE_ID` (or equivalent owner fail) — **no new sequence** |
| Request-key reconstruction without explicit arg | `parse_mint_market_batch_stage_sequence` restores N from key |
| Duplicate seal cannot allocate 2 for batch 1 | proven |

## Source Governor and six-unit reconciliation

- Each logical batch still creates governed `candidate_market_batch` request(s) under the durable request key.
- Sealed evidence carries `stage_sequence`, `logical_batch_identity`, `request_key`, and `source_request_ids`.
- Transport identities remain exactly-once at the owner ledger; tests use unique ordinals per outbound call.
- No Source Governor ownership change; no budget or reservation change.

## Tests

```text
.venv/bin/pytest \
  tests/test_v2_9_8b_multi_round_market_batch_six_unit_sequencing.py \
  tests/test_v2_9_8b_permanent_discovery_availability.py \
  tests/test_v2_9_8b_permanent_discovery_conversion_repair.py \
  tests/test_v2_9_8b_21_eligible_token_supply_architecture.py \
  tests/test_v2_9_8b_full_run_accounting_semantics_correction.py \
  tests/test_v2_9_8b_accounting_exact_identity_report_only_repair.py \
  -k 'not ordinary_disposable_two_token_window_15m_regression' -q
→ 126 passed, 1 deselected, 6 subtests passed

compileall changed modules → OK
git diff --check → OK
```

Deselected regression asserts migration head still starts with `050` while the ledger head is now `051` — pre-existing head-pin staleness, unrelated to sequencing.

### Distinct-round proof

- Unit: three seals → sequences `[1,2,3]`
- Permanent multi-round supply path: market stage sequences start at 1 and continue monotonically (≥2 rounds)

### Duplicate/replay proof

- Second seal of sequence 1 raises `DUPLICATE_STAGE_ID`
- Owner retains exactly one ingested `MINT_MARKET_BATCH|1`

## Money-usefulness contribution

The live re-proof died after real source work because multi-round market progress could not be accounted. Distinct-round sequencing restores the ability for the permanent funnel to complete second and later market batches and protocol-resume market validation without a false accounting terminal — a prerequisite for any clean `WINDOW_15M` memory attempt.

## What remains locked

- Flat ceiling 30; reservations 3/2/6/7/8/4
- Pump exactly-one migration rule; PumpSwap confirmation law; $3,000 floor
- Six-unit duplicate-stage protection (strength retained)
- No retries/successors; no retrieval/decisions/BUY·SELL·HOLD/positions/trades/audits/PnL
- No new authorization or live attempt in this lane

## Functionality Risks / Setbacks / Efficiency Blockers

- Sequence allocation depends on request_key prefix hygiene; callers must keep a stable `front_door_request_key_prefix` per cycle.
- Unfinished batches that wrote a request key but never sealed still advance the durable max sequence (honest gap; does not invent a free reseal).
- Live re-proof still requires a **fresh** one-use authorization on this repaired HEAD.

## Final classification

`V2_9_8B_MULTI_ROUND_MARKET_BATCH_SIX_UNIT_SEQUENCING_REPAIR_PASS`
