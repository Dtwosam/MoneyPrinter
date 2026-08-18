# Printer V1 V2-9.8B Four-Token 4/2/2 Freeze-Input Versus Two-Slot Truncation Repair Design

Date: 2026-08-18

Status: `CLOSED_PASS`

Verdict:

`V2_9_8B_FOUR_TOKEN_4_2_2_FREEZE_INPUT_VERSUS_TWO_SLOT_TRUNCATION_REPAIR_DESIGN_PASS`

## 1. Authority and scope

This design follows the active Printer V1 source stack and the V2 completion pattern:

`audit/readiness -> design/specification -> implementation -> bounded proof/test -> closeout`.

It repairs one proven V2-9.8B integration defect. It does not reopen discovery-provider law, Source Governor, Central Scheduler, holder policy, continuation, migrations, authorization, retrieval, financial capability, or long-window policy.

Design baseline: `2c8caf0b72136cc6eefbb114d4804175abc2097b`.

The consumed authorization `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260818T205144Z` is permanent historical evidence and is never reusable.

## 2. Incident and proven root cause

The consumed operational 4/2/2 attempt ended before lifecycle with:

`PRE_LIFECYCLE_DISCOVERY_SELECTION_COVERAGE_INSUFFICIENT`.

Forensic reconstruction proved this was not honest market scarcity. Printer had already produced eight lawful `MARKET_READY` / `MEMORY_OBSERVATION_ELIGIBLE` PumpSwap candidates with exact pool identity and liquidity at or above the $3,000 floor.

The defect is an integration ordering error:

1. The permanent front door owns a full lawful reserve in `GraduatedSupply.holder_reserve_supply` / `holder_reserve_candidates`.
2. The front door also owns a two-slot immediate handoff carrier in `GraduatedSupply.graduated_supply`.
3. `authoritative_live_operational_campaign.py` currently uses `tuple(supply.graduated_supply)` as permanent-mode `_graduated_admission()` input.
4. Permanent admission then sees only the two already-selected slot candidates even though its observation candidate cap is eight.
5. `freeze_eligible_reserve()` correctly requires post-filter depth >= 4 so it can produce exactly two selected plus two alternates.
6. The freeze therefore receives 2 rather than the eight lawful reserve candidates, truthfully blocks `2 < 4`, and lifecycle never starts.

The freeze-depth rule is correct. The input carrier is wrong.

## 3. Canonical owner analysis

`GraduatedSupply` already exposes the two required semantic domains:

- `holder_reserve_supply`: the full bounded lawful reserve before the two-slot handoff;
- `holder_reserve_candidates`: evidence mappings for that reserve;
- `graduated_supply`: the front-door two-slot selected handoff set.

No new list, selector, ranker, scoring owner, or persisted schema is required.

The permanent campaign's canonical pre-freeze admission input must be the existing `holder_reserve_supply`. The front-door `graduated_supply` remains valid as an immediate two-slot carrier for places that genuinely need the front-door pair; it must not be reused as the full memory-observation universe.

## 4. Designed data flow

### Before

```text
full lawful reserve (up to 8)
-> front-door two-slot selection
-> graduated_supply (2)
-> permanent graduated admission
-> observation rows (2)
-> freeze requires 4
-> coverage block
```

### After

```text
full lawful reserve (up to 8)
-> holder_reserve_supply
-> permanent graduated admission
-> tracking/evidence filtering
-> full MEMORY_OBSERVATION_ELIGIBLE observation rows
-> freeze_eligible_reserve
-> exactly 2 selected + exactly 2 alternates
-> only freeze-selected 2 may enter Cycle 1 active slots
```

Two-slot truncation therefore occurs at the existing post-freeze active-slot handoff, not before freeze.

## 5. Exact repair boundary

Primary product change:

- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`

For permanent memory-observation mode only, change `_graduated_admission()` input from `supply.graduated_supply` to the existing full `supply.holder_reserve_supply`.

No product change is designed in `graduated_supply_front_door.py` because it already exposes both carriers correctly.

No change is designed to:

- `freeze_eligible_reserve()`;
- `MINIMUM_FREEZE_DEPTH`;
- selection authority;
- provider/source adapters;
- Source Governor;
- Central Scheduler;
- Pump/PumpSwap protocol confirmation;
- later-cycle discovery;
- database schema or migrations;
- authorization/provenance code;
- lifecycle continuation.

If implementation inspection proves the semantic split is not stable on the current baseline, stop rather than inventing a new carrier.

## 6. Invariants preserved

- Freeze minimum depth remains 4.
- Successful freeze remains exactly 2 selected + 2 alternates.
- Exactly 2 selected candidates enter Cycle 1 slots.
- Alternates remain non-active reserve evidence.
- Operational shape remains 4 total through-4h tokens / 2 cycles / 2 tokens per cycle.
- Cycle 2 still requires fresh governed later-cycle discovery and distinct mint/pair identities; Cycle-1 alternates do not become Cycle-2 supply by carry-forward.
- $3,000 liquidity floor unchanged.
- Exact mint/pair and current protocol confirmation unchanged.
- Tracking-state exclusions unchanged.
- Holder UNKNOWN/unavailable remains context-only for memory observation.
- `FULLY_ELIGIBLE` remains distinct future-action evidence and is not a memory gate.
- Deterministic categorical neutral freeze/selection remains unchanged.
- Source Governor and Central Scheduler remain sole owners.
- Request ceilings, zero retries, no endpoint rotation, and 300s minimum cycle spacing remain unchanged.
- 5m remains support-only; 12h/24h remain locked.

## 7. Holder workload semantics

The existing permanent path already bounds holder work through `selected_slot_holder_candidates(supply)`. This repair must not replace that bounded holder target with the full reserve.

Therefore the intended behavior is lawful and asymmetric:

- full reserve participates in memory-observation admission and tracking/freshness checks;
- holder I/O stays limited to the existing selected-slot subset;
- candidates without holder evidence may still remain `MEMORY_OBSERVATION_ELIGIBLE` when all memory gates pass;
- holder pass may create `FULLY_ELIGIBLE`, but holder failure/UNKNOWN does not delete otherwise lawful observation candidates.

## 8. Authority separation and non-regression

`standard-four-hour-run` remains the existing two-token operational authority.

`four-token-bounded-capacity-proof-run` remains proof-only.

`four-token-standard-four-hour-run` remains exact operational 4/2/2 authority.

The repair changes a shared permanent observation seam only where the existing permanent-mode data carrier is semantically wrong. Tests must prove the ordinary two-token and proof authority meanings do not widen or merge.

## 9. Focused TDD requirements

Implementation must begin with a failing focused test that reproduces the defect before production code changes.

Minimum positive/negative cases:

1. Eight lawful reserve candidates with `graduated_supply` length 2: permanent admission/freeze receives the full reserve and does not truncate to 2.
2. Exactly four lawful observation candidates: freeze succeeds with 2 selected + 2 alternates.
3. Exactly three lawful observation candidates: freeze still truthfully coverage-blocks.
4. Holder work over only two candidates does not shrink the observation universe.
5. Holder timeout/UNKNOWN does not remove a candidate that otherwise passes memory-observation law.
6. Below-$3k, unsupported/wrong-pool, duplicate identity, and tracking-state exclusions remain excluded by their existing owners.
7. Exactly two freeze-selected candidates may become Cycle-1 active slots; alternates do not.
8. Cycle-2 fresh/disjoint identity law remains unchanged.
9. Existing two-token operational authority and four-token proof-only authority remain unchanged.
10. No 12h/24h and no retry/rerun/resume/restart/successor behavior is introduced.

## 10. Bounded disposable proof

After implementation, run a no-network/disposable proof with frozen fixtures that reproduces the incident shape:

- at least eight lawful observation-ready reserve candidates;
- front-door immediate pair remains two;
- permanent admission sees the full reserve;
- freeze receives at least four post-filter rows;
- freeze returns exactly two selected and two alternates;
- exactly two Cycle-1 slots are activated;
- holder workload stays bounded;
- later Cycle-2 supply remains fresh and disjoint;
- zero real provider calls;
- zero authoritative DB mutation;
- no authorization or child launch;
- no 12h/24h.

Also prove the negative case with only three lawful candidates still blocks coverage. A green positive proof must not be achieved by lowering the freeze threshold.

## 11. Persistence, rollback, and stop condition

No migration or schema change is required. Failed-attempt rows from the consumed campaign remain preserved; no backup restore or cleanup deletion is permitted.

Rollback is the single campaign-seam change plus its focused tests. Stop implementation if satisfying the test requires changing provider law, freeze depth, holder-as-memory-gate semantics, Scheduler/Source Governor ownership, later-cycle fresh-discovery law, migrations, or authorization rules.

## 12. Secondary non-causal findings

The forensic audit also observed reporting gaps involving campaign-level six-unit totals and missing pre-lifecycle provenance on this command path. They did not cause the freeze failure and are classified `NON_CAUSAL_REPORTING_EVIDENCE_GAPS`. They are excluded from this repair.

## 13. Money-usefulness contribution

This repair allows Printer to use the lawful fresh candidate depth it already paid to discover, so the memory factory can reach actual observation/lifecycle work without weakening market/safety gates. It improves learning yield while preserving honest blocking when fewer than four lawful observation candidates truly exist.

It does not guarantee profitable tokens, activate decisions, or create financial capability.

## 14. Implementation disposition

`IMPLEMENTATION_REQUIRED`

Exact next permitted lane:

`V2-9.8B Four-Token 4/2/2 Freeze-Input Versus Two-Slot Truncation Repair Implementation`

Implementation must use focused TDD and a disposable proof only. No live provider work, authoritative DB mutation, authorization creation, or Printer launch is permitted.