# Printer V1 V2-9.8B Post-Repair Two-Cycle Four-Token Authorization Alignment Audit

Date: 2026-08-18

Status: `CLOSED_PASS_WITH_SCOPED_REPAIR_REQUIRED`

Verdict:

`V2_9_8B_POST_REPAIR_TWO_CYCLE_FOUR_TOKEN_AUTHORIZATION_ALIGNMENT_AUDIT_PASS_WITH_SCOPED_REPAIR_REQUIRED`

Operational readiness: `BLOCKED`

## 1. Scope

This is a read-only audit of the repaired V2-9.8B baseline for one bounded operational campaign shaped as exactly two cycles with exactly two fresh token/pair slots per cycle, for four distinct through-4h token slots total.

This audit does not authorize implementation, authorization creation/consumption, provider calls, campaign execution, database mutation, Migration 059, 12h/24h activation, retrieval, decisions, positions, trades, audits or PnL.

Repaired product-code baseline:

`df1aced491d01d1a6d25ae38ca2da4eab72665c6`

Repository baseline inspected for this audit:

`ba1758886523c11c19d5ab37118c84de9a415327`

## 2. Authority findings

The active source stack supports bounded operator-approved memory growth, requires Source Governor and Central Scheduler ownership, keeps 5m support-only, and keeps 12h/24h locked until their later lanes.

The existing standard-four-hour authority is deliberately a two-token standard campaign. It must remain intact and must not be silently widened to four tokens.

The existing multi-cycle policy already defines exact two-token cycles and supports configured through-4h capacities of 2, 4 or 6. For configured capacity 4, the canonical projection is exactly two active cycles and two tokens per cycle. Capacity arithmetic is derived from the standard-four-hour contract rather than independently hard-coded.

The persisted multi-cycle coordinator already preserves one campaign/factory/Scheduler/Source-Governor ownership model, validates pair-atomic two-slot cycle admission, and rejects duplicate historical campaign slot identities. Its source explicitly states that the public operational command was intentionally not wired to multi-cycle activation in that implementation lane.

## 3. Runtime alignment finding

The four-token runtime composition exists, but its exposed authority remains proof-only.

Current public mode:

`four-token-bounded-capacity-proof-run`

Current standard operational mode:

`standard-four-hour-run`

The proof mode derives its four-token ceilings from `scaled_standard_four_hour_capacity_contract(4)` and reuses the standard-four-hour lifecycle arithmetic. The proof-only adapters/controllers also already carry Cycle-2 admission, later-cycle candidate supply, stage-scoped Scheduler ownership and per-cycle accounting seams.

Therefore the runtime repair program must not be reopened broadly. The missing boundary is an explicit approved operational 4/2/2 authority that delegates to the repaired canonical composition without turning the proof command into ordinary corpus-growth authority and without widening the two-token standard mode.

Classification:

`MISSING_APPROVED_OPERATIONAL_MULTI_CYCLE_AUTHORITY_BOUNDARY`

## 4. Migration/provenance finding

The canonical committed migration head is:

`058_direct_pump_migration_cursor.sql`

The four-token pre-consumption zero-state gate is already explicitly pinned to migration count 58 and head `058_direct_pump_migration_cursor.sql`.

However, `FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE` in `git_provenance_authorization_manifest.py` still names Migration 057 as its current migration evidence package and declares only Migrations 050, 055 and 056 as preserved historical migration packages.

That is stale against the repaired 058 database authority.

Classification:

`FOUR_TOKEN_PROVENANCE_CURRENT_MIGRATION_EVIDENCE_STALE_057_VS_058`

The exact host-local Migration-058 operator-evidence package execution identity and complete inventory digest are not established by the committed repository evidence inspected here. They must not be invented in this audit or design. Later implementation/preparation must bind exact real evidence or fail closed.

## 5. What is not reopened

This audit found no basis to reopen the repaired Cycle-2 acquisition/accounting/runtime seams, including fresh later-cycle acquisition, direct Pump/PumpSwap handling, `MARKET_PRESENT_POOL`, Source Governor ownership, Central Scheduler ownership/cadence isolation, 15m -> 1h -> eligible 4h continuation, exact predecessor cutoff, selected-slot holder ownership, terminal reporting or Migration 058 itself.

Source scarcity, provider limitation, honest market/supply exhaustion, missing optional evidence and host-local identity gaps remain distinct from code defects.

## 6. Required design scope

The next design must specify two narrowly coupled repair packages.

First, an operational 4/2/2 authority boundary:

- one operator-approved bounded invocation;
- exactly two cycles;
- exactly two fresh distinct mint/pair slots per cycle;
- exactly four total through-4h token slots;
- Cycle 2 performs fresh lawful governed discovery/selection rather than manual carry-forward;
- reuse the existing canonical campaign/factory/Scheduler/Source-Governor/lifecycle composition;
- preserve `standard-four-hour-run` as the existing two-token authority;
- preserve the existing proof mode as proof-only historical/bounded-proof authority;
- no retry, rerun, resume, restart or successor;
- 5m remains support-only and 12h/24h remain locked.

Second, post-repair migration/provenance alignment:

- Migration 058 becomes current migration evidence for the new operational 4/2/2 authorization profile;
- Migration 057 becomes preserved historical migration evidence rather than current authority;
- Migrations 050, 055, 056 and 057 remain distinct preserved history;
- the exact Migration-058 package identity/inventory must be evidence-bound, never guessed;
- focused stale provenance fixtures/tests must be updated;
- no Migration 059.

## 7. Capacity comparison anchor

For design verification only, the current derived four-token projection should resolve from committed code to:

- configured through-4h tokens: 4;
- configured active cycles: 2;
- tokens per cycle: 2;
- lifecycle requests per token: 117;
- lifecycle request outer ceiling: 472;
- lifecycle Scheduler outer ceiling: 420;
- automatic retries: 0;
- endpoint rotation: false;
- long windows activated: false.

These are comparison anchors, not values to hand-edit. Any later implementation/preparation must derive them from the exact launch checkout and stop on drift.

## 8. Authorization evidence disposition

The current repository handoff states that no fresh standard-four-hour authorization was created or consumed in the preceding preparation lane because host DB identity was unavailable. This audit therefore does not claim a concrete fresh authorization package exists.

Any authorization evidence discovered later on the actual host must be enumerated and classified by exact identity and terminal disposition. No existing two-token standard authorization may be repurposed as four-token authority.

## 9. Acceptance and stop conditions

Audit acceptance is satisfied because the target mismatch is classified, the proof-only/operational boundary is explicit, the 057-versus-058 provenance defect is proven, and the already-repaired runtime areas are not reopened without evidence.

Stop and re-audit if design would require a second Scheduler, a second Source Governor, an independent source loop, widening `standard-four-hour-run` to silently change its two-token contract, changing the proof mode into production authority, Migration 059, 12h/24h, retrieval/financial capability, paid APIs, scoring/ranking/confidence/weights, embeddings/vectors, wallet/private-key/signing/real-fund logic, or fabricated Migration-058 evidence.

## 10. Next permitted lane

`V2-9.8B Post-Repair Two-Cycle Four-Token Operational Authorization Alignment Design`

Type: `DESIGN_SPECIFICATION_ONLY`

No implementation, authorization creation/consumption, campaign execution or provider I/O is authorized by this audit.
