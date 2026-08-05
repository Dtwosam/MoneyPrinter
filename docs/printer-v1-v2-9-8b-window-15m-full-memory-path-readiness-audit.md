# Printer V1 — Full Read-Only WINDOW_15M Memory-Path Audit

**Date:** 2026-08-05  
**Repository:** `Dtwosam/MoneyPrinter`  
**Branch:** `agent/v2-9-8b-window-15m-authorization-retention-integration-repair`  
**HEAD:** `3f4a7ad4ea653fec7ece4e6a469643898260cd87`  
**Mode:** static/read-only audit only

No proof, authorization, provider call, discovery run, Scheduler runtime, memory generation, test execution, or database command was performed.

## Verdict

`V2_9_8B_WINDOW_15M_FULL_MEMORY_PATH_READINESS_AUDIT_BLOCKED`

`NOT_READY_FOR_NEW_WINDOW_15M_AUTHORIZATION`

The repaired authorization/database-binding and failure-retention boundaries pass static review. Five committed integration defects remain between memory-observation selection and clean-memory completion.

## Audited path

```text
wrapper and authorization
→ activation preflight
→ authorization-bound DB target
→ measured graduated supply
→ campaign source-request reconciliation
→ bounded holder context
→ MEMORY_OBSERVATION_ELIGIBLE conversion
→ four-candidate neutral freeze
→ two selected + two alternates
→ readiness bundle
→ combined activation executor
→ atomic handoff
→ Central Scheduler
→ WINDOW_15M snapshots and close
→ context and E2Q
→ Lane K / E2Z
→ clean episode and fingerprint
→ terminal acceptance, cleanup and replay
```

## Static-pass areas

- Validated authorization is now independently anchored to real manifest, marker, consumption, invocation, database and migration facts.
- Durable database expectation is loaded independently by campaign and lifecycle owners.
- Failure-safe artifact retention starts before later success assertions.
- Supply correctly separates `MEMORY_OBSERVATION_ELIGIBLE` from holder-dependent `FULLY_ELIGIBLE`.
- Freeze requires four fresh unique observation candidates and produces a neutral 2+2 set.
- Holder transport identities and holder-stage sealing are exact on the strict operational path.
- The factory binds exact ownership, uses Central Scheduler, attaches the closing snapshot to the current-run ledger, requires a 900-second evidence span, runs E2Q and scopes Lane K to the current window.
- Normal operational mode remains `WINDOW_15M` only; 5m remains support-only and longer windows remain locked.
- Retrieval, decisions, trading, positions, audits, PnL, wallets, funds, paid APIs, scoring and vectors remain locked.

# Authorization blockers

## A. Legacy activation re-applies holder eligibility

The new memory policy allows holder-pass, holder-fail, source-unavailable and budget-bound-unknown candidates into memory observation when the market/protocol/tracking/freshness gates pass.

After freeze, the selected proofs and the complete holder-facts map enter `CombinedPumpfunCampaignExecutor`. That executor adds `HOLDER_EVIDENCE_INELIGIBLE` whenever holder `eligible` is not true and rejects that candidate at `EVIDENCE_QUALITY`.

A candidate can therefore pass the memory freeze and then be rejected by the older future-action holder gate.

**Required repair:** add a memory-observation activation mode in which holder evidence remains context, `FULLY_ELIGIBLE` remains false unless actually passed, and holder failure/unknown does not block memory activation.

## B. A second selection authority runs after freeze

`freeze_eligible_reserve()` is intended to be the sole post-filter selection authority.

The selected pair is later processed by the combined executor’s own gate and `_categorical_two_slot()` selection logic. Historical latest/non-latest/provider-channel rules can reorder the selected pair. Graduation-native observations are also assigned the legacy `LATEST_PUMPFUN` channel even when truthful reserve provenance is persisted.

**Required repair:** preserve the exact frozen selected order into slot ordinals. Do not run a second selector, category quota or provider-channel ordering step. Any selected-candidate failure must block the atomic pair; no silent substitution or reselection.

## C. Retained facts are replayed as new source requests after reconciliation

Campaign-wide source-request reconciliation completes before readiness.

The combined executor then receives already measured selected observations and creates new `printer_source_requests` and `printer_source_responses` rows from those retained proof objects. No new transport occurs and no matching `TransportOperationIdentity` is created.

Those rows are created after the reconciled request manifest and represent retained facts as if they were new successful source responses.

**Required repair:** consume retained source evidence by exact original request/response/transport reference, or use an explicit approved zero-transport evidence-reuse contract. Do not create a new source response without a new source operation. The final campaign manifest must include every durable request exactly once.

## D. Current tracking eligibility is not enforced at freeze input

The holder-stage flow performs a current tracking-handoff assessment and can report cooldown, requalification-required or tracking ineligibility.

Observation conversion nevertheless sets `memory_observation_eligible=True` without requiring that current tracking-handoff result. The legacy executor later rechecks tracking and may reject the already frozen candidate.

**Required repair:** apply one current exact tracking-feasibility gate before freeze. Persist categorical deferral/exclusion. Revalidate atomically at handoff; a state change blocks the pair and must not trigger reselection.

## E. Clean episode and fingerprint creation are not atomic

Lane K first calls `create_clean_memory_from_window()`, which commits a `CLEAN_MEMORY` episode using its own database connection.

It then opens another connection to create the fingerprint. If fingerprint creation fails, the factory later marks the close step failed, but the already committed clean episode remains durable without its required fingerprint.

**Required repair:** create or verify the episode and its exact fingerprint in one transaction under one owner. A fingerprint fault must roll back both new objects. Validate exact episode/window/token/pair correspondence before commit.

# Significant follow-up debt

## Readiness role names

The neutral selected pair is still written through `latest` and `persisted` compatibility fields. True provenance is stored separately, so this is not the first blocker, but the reporting should expose explicit ordered slot-1/slot-2 identities and label the old columns positional-only.

## Liquidity timestamp

`liquidity_observed_at` in readiness uses front-door report generation time rather than the selected candidate’s exact retained market-observation timestamp. Use the actual evidence timestamp.

## Lane K zero-clean behavior

Zero clean memories remains valid for reusable Lane K. Do not weaken that module. The operational campaign must continue to apply its separate current-run clean-memory acceptance gate.

## Fingerprint UNKNOWN labels

Exact episode/window/token/pair identity must never be unknown. Non-identity context labels may remain categorical `UNKNOWN` only when the clean context contracts permit it.

# Correct next section

`V2-9.8B — WINDOW_15M Memory-to-Activation and Clean-Object Integrity Repair`

Required order:

1. this audit/readiness closeout;
2. design/specification;
3. bounded implementation;
4. focused offline verification only;
5. independent read-only review and closeout.

No proof or new 15-minute authorization belongs in this section.

# Minimum focused verification after repair

1. Holder-failed, unavailable and budget-bound-unknown candidates remain memory-activatable when memory gates pass.
2. They remain `FULLY_ELIGIBLE=false` and future-action blocked/unknown.
3. Frozen selected order reaches slot ordinals unchanged.
4. No post-freeze selector or category rule changes the set or order.
5. Failure of one selected candidate blocks the entire pair.
6. No automatic alternate substitution.
7. Current tracking-ineligible candidates cannot enter freeze.
8. Post-freeze tracking change blocks atomically without reselection.
9. Retained evidence creates no false new transport-shaped request/response.
10. Every durable request belongs to the final manifest exactly once.
11. Request and transport counts stay separate and exact.
12. Original request/response/transport provenance reaches activation and snapshots.
13. Episode and fingerprint commit atomically.
14. Forced fingerprint failure leaves zero new clean episode and fingerprint.
15. Existing complete episode+fingerprint replay is idempotent.
16. Episode/window/token/pair mismatch blocks.
17. Lane K remains scoped to the current window.
18. Normal operational mode remains 15-minute only.
19. Source Governor, Central Scheduler and all capability locks remain unchanged.

# Money-usefulness

The repair is necessary so Printer can learn from manipulated or concentrated Solana memecoin conditions without mistaking holder concentration for an organic-token filter, while preserving one neutral selection authority, truthful source provenance and complete clean-memory objects.

# Still locked

No authorization, providers, runtime, memory generation, longer windows, retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, wallets, keys, signing, funds or live execution.

## Final verdict

`V2_9_8B_WINDOW_15M_FULL_MEMORY_PATH_READINESS_AUDIT_BLOCKED`

A new `WINDOW_15M` authorization must wait until the five defects are repaired, focused-tested and independently reviewed.
