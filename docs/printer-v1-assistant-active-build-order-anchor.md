# Printer V1 Assistant Active Build Order Anchor

## Purpose and authority

This document aligns ChatGPT, Codex, Claude, Grok, and future assistants before Printer V1 / Moneygoals work.

It is an assistant-alignment anchor only. It does not replace the active authority stack:

1. `AGENTS.md`
2. `docs/printer-v1-clean-master-spec.md`
3. `docs/printer-v1-post-rc-build-order.md`
4. `docs/printer-v1-memory-factory-guide.md`
5. `docs/printer-v1-current-state-memory-growth-audit.md`
6. `docs/printer-v1-memory-growth-build-order-v2.md`

Inside that stack, `docs/printer-v1-memory-growth-build-order-v2.md` is the active memory-growth build order, not the sole source of truth.

Use `CURRENT_HANDOFF.md` only for the current lane, current commit, latest completed work, blockers, and next permitted action. If it conflicts with the authority stack, the authority stack wins.

Historical roadmaps, old lane documents, old chats, previous handoffs, and older current-looking pointers are historical evidence only unless explicitly re-adopted.

## Current durable state — 2026-09-03 Cycle-2 duplicate-transport audit

Active capability family:

- `V2-9.8B — Active Bounded Memory Growth Operations`

Current adopted operational envelope remains:

- policy family: `V2-9.8B-FOUR-TOKEN-STANDARD-4H-OPERATIONAL-V1`;
- two cycles;
- exactly two token slots per cycle, ordinals `(1, 2)`;
- up to four concurrent through-4h lifecycle tokens as two overlapping
  two-slot cycles;
- Cycle 2 may overlap Cycle 1 through `WINDOW_15M`, `WINDOW_1H`, and
  `WINDOW_4H`;
- no third cycle; no fifth token; compiled 6-token / 3-cycle max unused;
- standard lifecycle: `WINDOW_15M -> hard-gated WINDOW_1H -> hard-gated WINDOW_4H -> stop`;
- `WINDOW_5M_MICRO_EVENT` remains support-only;
- `WINDOW_12H` and `WINDOW_24H` remain locked;
- candidate-acquisition foundation / N2 / N7 / global Pump cursor/recovery remain preserved but deferred and are not an operational prerequisite.

Latest completed campaign:

- authorization: `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260903T121923Z_202fbea1`;
- authorization SHA-256: `02153f8a96b13f5096cd0e695c78649f16e2f11105894f91a86517d486493c5d`;
- authorized execution HEAD: `26d7b91bb5f115ad816b3cd632b5036d07b82b0e`;
- permanently consumed `CONSUMED / CHILD_EXITED_ZERO / PERMANENTLY NON-REUSABLE`;
- no retry, rerun, resume, restart, reuse, inheritance, or successor;
- post-run authoritative DB SHA-256:
  `575984caa484b12f4bb5fca0a06cdf7865adeb03b5f16874406fb0c1a73daa6e`;
- campaign result `CAMPAIGN_FAILED`;
- primary classification
  `PROVEN_COMMITTED_BUDGET_ENFORCEMENT_DEFECT` /
  `FOUR_TOKEN_STD4H_PER_TOKEN_CEILING_STILL_SELECTIVE_1H_CONTINUOUS_50`;
- forensic closeout
  `V2_9_8B_SEP3_CONSUMED_4_2_2_STANDARD4H_POST_RUN_FORENSIC_CLOSEOUT_PASS`;
- per-token ceiling wiring repair readiness/audit
  `V2_9_8B_FOUR_TOKEN_STANDARD4H_PER_TOKEN_REQUEST_CEILING_WIRING_REPAIR_READINESS_AUDIT_PASS`;
- Cycle-2 duplicate-transport / NO-PAIR blocker audit
  `V2_9_8B_SEP3_CYCLE2_DUPLICATE_TRANSPORT_NO_PAIR_BLOCKER_AUDIT_PASS`;
- Cycle-2 primary classification `NEW_NARROW_REFRESH_REENTRY_DEFECT`;
- Cycle-2 repair classification `NARROW_REPAIR_FEASIBLE`;
- official zero-state domains are all `0`;
- retrieval, financial capabilities, 12h, and 24h remain locked.

## Remote-host infrastructure state

Remote-host readiness / portability audit is closed PASS:

`REMOTE_HOST_READINESS_CLOSEOUT_PASS__REMOTE_HOST_DESIGN_SPECIFICATION_NEXT`

Native Linux/systemd one-shot portability design is complete:

`REMOTE_HOST_NATIVE_LINUX_SYSTEMD_PORTABILITY_DESIGN_PASS__OPERATOR_REVIEW_NEXT`

Current governing design:

`docs/printer-v1-remote-host-native-linux-systemd-portability-design.md`

The remote-host work is infrastructure support only. It does not reorder or advance the memory-growth capability sequence.

## Exact current next permitted action

The exact current lane is:

```text
SEP-3 CYCLE-2 DUPLICATE-TRANSPORT ACQUISITION REPAIR — DESIGN / SPECIFICATION
```

The independent four-token per-token `50 -> 118` design remains open:

```text
FOUR-TOKEN STANDARD-4H PER-TOKEN REQUEST-CEILING WIRING REPAIR — DESIGN / SPECIFICATION
```

The Sep-3 consumed 4/2/2 Standard-4H forensic closeout is closed PASS:

`V2_9_8B_SEP3_CONSUMED_4_2_2_STANDARD4H_POST_RUN_FORENSIC_CLOSEOUT_PASS`

Campaign result: `CAMPAIGN_FAILED`. Consumed authorization
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260903T121923Z_202fbea1` is permanently
non-reusable.

The Sep-3 Cycle-2 duplicate-transport / NO-PAIR blocker audit is closed PASS:

`V2_9_8B_SEP3_CYCLE2_DUPLICATE_TRANSPORT_NO_PAIR_BLOCKER_AUDIT_PASS`

Primary classification: `NEW_NARROW_REFRESH_REENTRY_DEFECT`

Repair classification: `NARROW_REPAIR_FEASIBLE`

Governing audit:

`docs/printer-v1-v2-9-8b-sep3-cycle2-duplicate-transport-no-pair-blocker-audit.md`

The per-token request-ceiling wiring repair readiness/audit remains closed PASS:

`V2_9_8B_FOUR_TOKEN_STANDARD4H_PER_TOKEN_REQUEST_CEILING_WIRING_REPAIR_READINESS_AUDIT_PASS`

Classification: `NARROW_POLICY_WIRING_REPAIR_FEASIBLE`

Governing audit:

`docs/printer-v1-v2-9-8b-four-token-standard4h-per-token-request-ceiling-wiring-repair-audit.md`

The next-bounded 4/2/2 Standard-4H authorization-boundary / package design
remains historically closed PASS:

`V2_9_8B_NEXT_BOUNDED_4_2_2_STANDARD_4H_AUTHORIZATION_BOUNDARY_PACKAGE_DESIGN_PASS`

Classification: `EXISTING_OWNER_ALREADY_SUFFICIENT`

Governing design:

`docs/printer-v1-v2-9-8b-next-bounded-4-2-2-standard-4h-authorization-boundary-package-design.md`

Do not implement either repair automatically. Do not prepare or apply an
authorization. Do not run Printer.

Post-reconciliation exact-HEAD / exact-DB next-bounded-campaign readiness /
governance remains historically closed PASS:

`V2_9_8B_POST_RECONCILIATION_FRESH_EXACT_HEAD_EXACT_DB_NEXT_BOUNDED_CAMPAIGN_READINESS_GOVERNANCE_PASS`

Governing readiness:

`docs/printer-v1-v2-9-8b-post-reconciliation-next-bounded-campaign-readiness-governance.md`

The Sep-2 surviving pre-lifecycle wait reconciliation / zero-state lane remains
historically closed PASS:

`V2_9_8B_SEP2_SURVIVING_PRE_LIFECYCLE_WAIT_RECONCILIATION_ZERO_STATE_PASS`

Governing closeout:

`docs/printer-v1-v2-9-8b-sep2-surviving-pre-lifecycle-wait-reconciliation-zero-state-closeout.md`

The four-concurrent 4/2/2 terminal-transaction and production-owner proof
hardening lane remains historically closed PASS:

`V2_9_8B_FOUR_CONCURRENT_4_2_2_TERMINAL_TRANSACTION_AND_PRODUCTION_OWNER_PROOF_HARDENING_PASS`

The consumed Sep-2 authorization
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260902T122136Z_59fdefe7` is
`CONSUMED / CHILD_EXITED_NONZERO / PERMANENTLY NON-REUSABLE`. Consumed
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260901T203521Z_12a7ea61` remains
`CONSUMED / CHILD_EXITED_ZERO / PERMANENTLY NON-REUSABLE`. Consumed
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260901T181024Z_ab6c68fe` remains
`CONSUMED / CHILD_EXITED_NONZERO / PERMANENTLY NON-REUSABLE`. Source-stack
wording permits four concurrent through-4h tokens as two overlapping two-slot
cycles. Use `CURRENT_HANDOFF.md` for the live HEAD after this documentation
commit. Later Cycle-2 design must bind that live HEAD and DB SHA-256
`575984caa484b12f4bb5fca0a06cdf7865adeb03b5f16874406fb0c1a73daa6e`.

Allowed now:

- Cycle-2 duplicate-transport acquisition repair design / specification only;
- the independent four-token `50 -> 118` design remains open and is not this
  Cycle-2 repair;
- do not implement either design in this handoff;
- do not apply or consume an authorization in this handoff;
- do not run Printer.

Do not begin implementation automatically.
Do not begin package preparation automatically.
Do not redo the existing canonical authorization owners.
Do not reuse consumed `202fbea1`, `59fdefe7`, `12a7ea61`, or `ab6c68fe`.
Do not retry, rerun, resume, restart, or create a successor from those runs.
Do not create an application marker.
Do not call `apply_authorization_once`.
Do not run Printer.
Do not contact providers/RPC/WebSocket.
Do not run Central Scheduler.
Do not mutate the authoritative DB.
Do not activate retrieval or any financial capability.

## Remote-host design locks

Any future approved implementation must preserve:

- the existing four-token standard-four-hour one-shot wrapper as the operational application boundary;
- systemd supervising the wrapper, not the child operational command directly;
- `Restart=no`, no timer, no watchdog relaunch, no reboot relaunch;
- cooperative safe-stop through existing campaign supervision / cancellation owners;
- consumed authorization permanently dead even after signal, crash, or durability failure;
- exact remote authorization issued only after final remote exact HEAD + exact DB + filesystem identity exist;
- one sole authoritative operational DB writer/host;
- no Mac/VPS authoritative-write overlap;
- fail-closed parent-directory durability at required one-shot publication boundaries;
- positively proven local filesystem suitability before marker consumption;
- fresh Linux runtime/venv and exact tested dependency/runtime evidence;
- Source Governor and Central Scheduler remaining authoritative;
- existing SQLite DELETE/FULL/normal semantics unless separately redesigned and approved.

## Required assistant behavior

Before proposing any change, shortcut, repair, next step, workflow, proof, or new lane:

- check it against the active authority stack, active build order, and `CURRENT_HANDOFF.md`;
- reject or correct anything that skips sequencing, weakens evidence/safety rules, or drifts from V1;
- distinguish proven product defects from source scarcity, provider limitations, honest market blocks, missing evidence, documentation assumptions, and infrastructure requirements;
- preserve `audit/readiness -> design/specification -> implementation if approved -> bounded proof/test -> closeout` for each major capability;
- use minimum sufficient risk-based verification;
- do not request broad regression suites unless change risk or lane closeout requires them.

## Permanent restrictions

Printer V1 remains:

- Solana-only;
- Solana memecoin-only;
- paper-trading only;
- no live wallet, private keys, signing, real funds, or live execution;
- no paid API dependency;
- no scoring, ranking, confidence percentages, or weighted decision logic;
- no embeddings or vectors unless explicitly approved later;
- no Source Governor bypass;
- no Central Scheduler bypass;
- no dirty memory used for retrieval or decisions;
- no retrieval before its explicit approved lane;
- no BUY/SELL/HOLD before its explicit approved lane;
- no paper positions, trade events, paper audits, or PnL before their explicit approved lanes;
- no 12h/24h activation.

`WINDOW_5M_MICRO_EVENT` remains support-only and cannot independently create main outcome memory, continuation, retrieval, decisions, positions, or PnL.

## Final anchor rule

Assistants must use the current repository evidence and `CURRENT_HANDOFF.md` for time-sensitive state, while preserving the authority stack above. Do not revive any older next-lane pointer merely because it remains in a historical document.

<!-- V2_9_8B_REMOTE_HOST_PAUSE_MEMORY_GROWTH_RETURN_CURRENT_STATE_START -->
## V2-9.8B Remote-Host Pause / Memory-Growth Return — Current Authority

Operator decision: remote-host / VPS work is paused while Printer continues the
local Mac V2-9.8B bounded memory-growth path.

Completed remote-host work remains preserved separately on
`agent/remote-host-linux-portability-implementation` at `f61419f2db37fc5eb220c20fafeaf15501218033`. It is not discarded, merged into this
lane, or treated as current operational authority.

This block supersedes older current-looking remote-host lane pointers in this
document for current-lane selection only. Historical remote-host evidence
remains valid evidence.

Current preserved campaign/data baseline:

- branch before this synchronization: `agent/v2-9-8b-aug25-a2z-repair-application`
- pre-synchronization HEAD: `fd558c9e8a691ee1963509d7488aef05908f93c7`
- authoritative DB: `data/printer_v1.sqlite3`
- authoritative DB SHA-256: `f4e54b3a2dc9f4dbd41b6f05bb5288f25ca15dc71b7e66de1e05ef7c213e34b1`
- consumed authorization:
  `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260827T122355Z_8e43eae7`
- that authorization remains permanently non-reusable
- latest campaign classification remains
  `EXPECTED_OPERATIONAL_BLOCKER__NO_CODE_CHANGE`
- retrieval, financial capability, `WINDOW_12H`, and `WINDOW_24H` remain locked
- `WINDOW_5M_MICRO_EVENT` remains support-only

The exact current permitted lane is:

`POST-CAMPAIGN FRESH NEXT-BOUNDED-CAMPAIGN READINESS / GOVERNANCE ONLY`

This lane is read-only readiness/governance. It may establish exact final Git
identity, authoritative DB identity/health, tracked-tree cleanliness, runtime
quiescence, evidence continuity, and permanent-lock continuity.

It does not create or apply an authorization. It does not run Printer, contact
providers/RPC/WebSocket, run Central Scheduler, mutate the authoritative DB,
activate retrieval, activate financial capability, or unlock longer windows.

Only after a fresh exact-HEAD/exact-DB readiness PASS may the next separate lane
be considered:

`FRESH EXACT-HEAD / EXACT-DB ONE-SHOT AUTHORIZATION PREPARATION / INDEPENDENT REVIEW`

Separate operator approval remains required before any later one-shot execution.

Permanent V1 locks remain unchanged.
<!-- V2_9_8B_REMOTE_HOST_PAUSE_MEMORY_GROWTH_RETURN_CURRENT_STATE_END -->

<!-- V2_9_8B_POST_MIGRATION_062_READINESS_CURRENT_STATE_START -->
## V2-9.8B Post-Migration 062 Fresh Next-Bounded-Campaign Readiness — Current Authority

This block supersedes older current-looking migration, post-campaign,
remote-host, and next-bounded-campaign readiness pointers for current-lane
selection. Historical text remains evidence only.

- migration application verdict:
  `V2_9_8B_MIGRATION_062_CONTROLLED_APPLICATION_PASS`
- migration-application synchronization commit:
  `52bf15365bbf500ffe61f1b49a4d9ca38d1c3363`
- authoritative DB SHA-256:
  `dececa7ce402856978675c66ecbdfd23b88ed97e3ff23f282a2588a436c93836`
- migration state: `62 / 062_pre_admission_attempt_evidence.sql`
- reviewed product-code repair:
  `91ec3131318f5bff4d3c6dfed12b09c5b6747827`
- consumed authorization
  `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260827T122355Z_8e43eae7`
  remains permanently non-reusable
- readiness verdict:
  `V2_9_8B_POST_MIGRATION_FRESH_NEXT_BOUNDED_CAMPAIGN_READINESS_GOVERNANCE_PASS`
- historical `NO_PAIR / DURATION_EXHAUSTION` classification remains
  `EXPECTED_OPERATIONAL_BLOCKER__NO_CODE_CHANGE`
- no campaign, authorization, provider/RPC/WebSocket, Source Governor, Central
  Scheduler, retrieval, financial, or remote-host action occurred in readiness

Governing closeout:

`docs/printer-v1-v2-9-8b-post-migration-062-fresh-next-bounded-campaign-readiness-governance-closeout.md`

The exact current permitted lane is:

`FRESH EXACT-HEAD / EXACT-DB ONE-SHOT AUTHORIZATION PREPARATION / INDEPENDENT REVIEW`

Any fresh authorization must bind the final committed readiness HEAD and the
exact DB SHA above. Preparation/review does not execute Printer, and later
consumption/execution requires separate explicit operator approval. All
permanent V1 locks remain unchanged.
<!-- V2_9_8B_POST_MIGRATION_062_READINESS_CURRENT_STATE_END -->
