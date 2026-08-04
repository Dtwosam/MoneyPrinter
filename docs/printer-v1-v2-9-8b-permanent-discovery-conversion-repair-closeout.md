# V2-9.8B Permanent Discovery Conversion Repair Closeout

Date: 2026-08-04

Lane: `V2-9.8B — Permanent Discovery Conversion Repair`

Baseline: `c0098ccb275239e9208dee31fe1d0722c5c5dc03`  
(`Complete permanent discovery conversion evidence supplement`)

Plan: `docs/superpowers/plans/2026-08-04-permanent-discovery-conversion-repair.md`

## Verdict

`V2_9_8B_PERMANENT_DISCOVERY_CONVERSION_REPAIR_PASS`

All three proven defects from the conversion evidence supplement are repaired with focused offline proof. No authorization was created and no live `WINDOW_15M` attempt was run.

## Defect-to-proof matrix

| Defect | Production owner | Exact code change | Focused proof | Verdict | Remaining limitation |
|---|---|---|---|---|---|
| **D1** Candidate-local Pump migrate validation escalated to shared `SOURCE_AVAILABILITY_FAILURE` | `pump_contracts.decode_supported_pump_migration_transaction`; `direct_pump_migration._failure` / normalize; `eligible_token_supply` governed-failure aggregation | Bounded `migration_rejection_digest` on exactly-one (and related) rejects; payload marks `MIGRATION_EVIDENCE_REJECTED` + `candidate_local_validation`; aggregator skips `direct_pump_migration_rejected_*` for provider_failures / `channels_unavailable` | `test_exactly_one_reject_builds_digest`; `test_transport_complete_reject_is_not_shared_source_failure` | **PASS** | Raw full transaction bodies still not persisted (digest only). True transport failures still mark the channel unavailable. |
| **D2** Global stage cursor advanced to protocol and blocked further market batches while capacity remained | `StageBudget` in `permanent_discovery_availability.py`; permanent loop in `eligible_token_supply.py` | Seal-gated budget: stages consume independently while unsealed; residual flows only after `seal`; `advance` seals earlier stages for compat; migration protocol charged once without sealing market; multi-round market batches allowed | `test_seal_allows_protocol_and_market_without_rewind`; `test_second_market_batch_after_protocol_ops`; updated lawful-unexplored composition test | **PASS** | Flat ceiling remains 30; when market reservation is truly spent, further market work stops honestly. |
| **D3** Solitary market-ready could not enter holder/safety | `AuthoritativeLiveOperationalCampaignOwner` pre-holder gate | Permanent mode: skip only when `graduated_candidates < 1`; legacy path retains `< 2` | `test_permanent_holder_gate_allows_single_market_ready`; campaign composition still requires four fully eligible before selection ready | **PASS** | Selection/handoff still require four fully eligible (permanent) or two (legacy). Holder capacity can still honestly block. |

## Additional repairs delivered

| Item | Change | Proof |
|---|---|---|
| Protocol queue | `process_protocol_confirmation_queue` spends protocol capacity on protocol-due identities; unsupported venues → `UNSUPPORTED_VENUE`; Pump-family without account transport remain due fail-closed; Meteora never activated | `test_protocol_due_identities_receive_bounded_work` |
| Terminal precedence | Candidate-local migrate rejects excluded from shared source shortage; false budget exhaustion suppressed when stage/flat capacity remains with executable work | conversion + composition tests |
| Diagnostics | `stage_capacity` snapshot, sealed/unsealed stages, pending queues, migration rejections, protocol outcomes, market-ready depth | snapshot unit test + supply diagnostics |

## Hard locks preserved

- Ceiling **30**; reservations **3/2/6/7/8/4**
- `exactly_one_migrate_instruction_required` unchanged
- $3,000 floor unchanged
- No retries/successors/paid sources/ranking/scores
- No Source Governor or Scheduler bypass
- No retrieval/decisions/BUY/SELL/HOLD/positions/trades/audits/PnL
- No live providers or campaign during implementation
- No schema migration required

## Verification

```text
.venv/bin/pytest \
  tests/test_v2_9_8b_permanent_discovery_conversion_repair.py \
  tests/test_v2_9_8b_permanent_discovery_availability.py \
  tests/test_v2_9_8b_21_eligible_token_supply_architecture.py \
  tests/test_v2_9_7e_42_direct_migration_discovery.py \
  tests/test_v2_9_7e_45_holder_reserve_funnel.py \
  tests/test_v2_9_8b_2_holder_budget_supervision_repair.py \
  -q
→ 112 passed

python -m compileall (changed modules) → OK
git diff --check → OK
```

No disposable DB migration was required (existing 051 projections suffice).

## Remaining blockers (out of this lane)

1. **Live re-proof** still requires a new operator authorization and one-shot `WINDOW_15M` attempt on the repaired HEAD — not authorized here.
2. **Protocol account batch transport** for fresh Pump-family nominations is counted/attempted offline-safe; production on-chain account confirmation still depends on governed Solana account batching when a transport is composed into a future live path.
3. **Fully eligible depth of four** remains a market + holder evidence problem; repair only restores lawful conversion flow so depth can be accumulated without false terminals.
4. Untracked Migration-050 package and `/private/tmp/mp-preclaim` remain preserved and untouched.

## Money-usefulness

The conversion path no longer dies on healthy transport that fails a local migrate proof, no longer freezes market rounds behind a protocol cursor, and no longer skips holder evaluation for a single market-ready survivor. That is the minimum path back toward a lawful four-candidate freeze and eventual clean memory — without weakening contracts.

## Final classification

`V2_9_8B_PERMANENT_DISCOVERY_CONVERSION_REPAIR_PASS`
