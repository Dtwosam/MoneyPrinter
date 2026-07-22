# V2-9.7E.19 Holder-Evidence Eligibility and Clean-Memory Repair — Closeout

**Lane verdict:** PASS

**Baseline:** 77e7630e711ba39c1969519158646f2c3f820fde

## What changed

### M1 — holder evidence before operational activation

- The authoritative operational owner now evaluates a deterministic, fixed set
  of at most eight finalized Pump-origin candidates before activation.
- It reuses the existing governed GoPlus → Solana-RPC holder path, including
  only the already-authorized single transient backup. There is no new retry,
  backoff, endpoint rotation, provider or ceiling.
- Complete, clean, exact-target, known holder evidence is eligible. Missing,
  failed, stale, mismatched and unknown evidence is candidate-ineligible with a
  factual persisted evidence-gap reason; it is not relabelled unsafe.
- The existing fixed evidence-quality gate consumes the fact before existing
  deterministic uniform selection. Two eligible candidates activate atomically,
  or fewer than two blocks with no first-15m job.
- Worst-case source work remains within the existing 45-call campaign ceiling:
  at most 24 holder-path calls (8 × GoPlus/primary/one backup), at most 9 Pump
  calls, and at most 5 existing discovery/enrichment calls. No ceiling changed.

### M2 — verified inactivity

- The exact-pair persistence boundary fills missing 5m/15m activity with zero
  only after a complete/clean exact-target response, positive finite price and
  liquidity, and finite factual zero 1h volume and transaction counts.
- Existing active values are invariant. Missing price, liquidity, wider
  evidence, stale/failed/malformed evidence or exact-pair mismatch stays
  missing/fail-closed.
- Converted fields carry explicit SNAPSHOT_VERIFIED_INACTIVE provenance.

### M3 — operational-natural terminal result

- Exactly two distinct, succeeded, attached, complete, clean 15m windows with
  factual STOP_AFTER_15M dispositions may complete an operational-natural run
  when 4h was correctly not started.
- Dirty/partial/incomplete/ambiguous stops cannot complete.
- A started natural continuation still must pass the existing 1h → 4h terminal
  audit. Explicit compressed/proof-mode 4h behavior remains unchanged.

### O1 — campaign discovery cleanup

- Terminal cleanup cancels only pending/running DISCOVERY_REFRESH Scheduler
  jobs joined to the exact discovery batch through printer_discovery_work.
- Unrelated discovery jobs and non-discovery jobs are preserved.
- Repeated cleanup is idempotent and the final report records its exact count.

## Offline proof

- Holder facts: valid, missing, target mismatch, stale, failed and unknown.
- Existing GoPlus-first/RPC-fallback evidence isolation.
- Deterministic in-set replacement; fewer than two eligible candidates produces
  atomic no-activation and no 15m job.
- Verified inactivity conversion, negative predicates and active-value
  invariance.
- Two clean natural stops complete; dirty stops and proof-mode no-4h do not.
- Started 4h failure remains terminally blocked.
- Exact discovery cleanup, unrelated-job preservation and replay idempotence.
- Existing exact-pair persistence, combined-discovery, operational continuation,
  Scheduler terminalization and permanent-lock contracts.

No provider was contacted. No pilot was run or mutated. No migration was added.

## Permanent locks

No retrieval, paper decision, BUY/SELL/HOLD, position, trade event, paper audit,
PnL, wallet, private key, signing, real funds, live execution, paid API,
scoring, ranking, confidence, weighting, embedding or vector capability was
added or unlocked. The 5m window remains support-only.

## Functionality risks / setbacks / efficiency blockers

- Holder eligibility intentionally reduces activation yield when free evidence
  is unavailable; that is an honest block, not a token safety conclusion.
- Eight candidates can consume up to 24 holder-path calls in the full
  GoPlus-unknown/two-RPC-fault case. It stays under the frozen campaign ceiling
  but remains the largest incremental source cost.
- Verified inactivity is deliberately narrow: any wider-window activity keeps
  absent short-window values missing.
- The Windows restricted-token sandbox could not run repository patches or
  temporary-directory tests directly. The approved installed patch executable
  and elevated focused test runs were used; no proof scope was weakened.

## Files

- docs/printer-v1-v2-9-7e-19-holder-evidence-clean-memory-repair-design.md
- docs/printer-v1-v2-9-7e-19-holder-evidence-clean-memory-repair-closeout.md
- src/printer_v1/discovery/combined_executor.py
- src/printer_v1/operator_cli/authoritative_live_operational_campaign.py
- src/printer_v1/operator_cli/e2m_snapshot_persistence.py
- src/printer_v1/operator_cli/one_command_15m_factory.py
- tests/test_v2_9_7d_7b_4d_combined_discovery_executor.py
- tests/test_v2_9_7e_11_authoritative_live_operational_campaign.py
- tests/test_v2_9_7e_19_holder_evidence_clean_memory_repair.py

## Next lane

Stop at E.19. Do not begin E.7F, E.8, provider contact or a live pilot in this
lane. Any next action requires the operator’s explicit active-roadmap choice.
