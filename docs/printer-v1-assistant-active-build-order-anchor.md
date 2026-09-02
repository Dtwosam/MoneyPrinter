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

## Current durable state — 2026-09-02

Active capability family:

- `V2-9.8B — Active Bounded Memory Growth Operations`

Current adopted operational envelope remains:

- policy family: `V2-9.8B-FOUR-TOKEN-STANDARD-4H-OPERATIONAL-V1`;
- two cycles;
- exactly two concurrently active token slots;
- up to four distinct token identities across the full two-cycle campaign;
- concurrent capacity remains exactly `2`;
- no increase to 3 or 4 concurrent tokens is authorized;
- standard lifecycle: `WINDOW_15M -> hard-gated WINDOW_1H -> hard-gated WINDOW_4H -> stop`;
- `WINDOW_5M_MICRO_EVENT` remains support-only;
- `WINDOW_12H` and `WINDOW_24H` remain locked;
- candidate-acquisition foundation / N2 / N7 / global Pump cursor/recovery remain preserved but deferred and are not an operational prerequisite.

Latest completed campaign:

- authorization: `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260901T203521Z_12a7ea61`;
- authorization SHA-256: `b8112ab756e46c60bac82d486a0de113113cb3b266690f2850f2d6c7698a96f3`;
- authorized execution HEAD: `91c757c542d8098ecf7b244769061f333dcfc21f`;
- permanently consumed `CONSUMED / CHILD_EXITED_ZERO / PERMANENTLY NON-REUSABLE`;
- no retry, rerun, resume, restart, reuse, inheritance, or successor;
- authoritative post-campaign DB SHA-256: `a3172e04f99ef410ba66eb4e2928b5b4edbdd7dfad4d713fcd1605fa3b702a8c`;
- campaign classification: `COMMITTED_CODE_DEFECT` / `LATER_CYCLE_COOPERATIVE_MINT_MARKET_BATCH_DUPLICATE_TRANSPORT_IDENTITY`;
- scope-propagation repair live proof: `CAMPAIGN_SOURCE_REQUEST_SCOPE_PROPAGATION_REPAIR_LIVE_PROOF_PASS`;
- later-cycle duplicate-transport authoritative repair: `V2_9_8B_LATER_CYCLE_DUPLICATE_TRANSPORT_AUTHORITATIVE_REPAIR_PASS`;
- no current-campaign active work;
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
POST-REPAIR FRESH EXACT-HEAD / EXACT-DB READINESS / GOVERNANCE
```

The consumed Sep-1/Sep-2 authorization
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260901T203521Z_12a7ea61` is
`CONSUMED / CHILD_EXITED_ZERO / PERMANENTLY NON-REUSABLE`. The earlier consumed
Sep-1 authorization `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260901T181024Z_ab6c68fe`
remains `CONSUMED / CHILD_EXITED_NONZERO / PERMANENTLY NON-REUSABLE`. The
freeze-ready scope-propagation repair is closed PASS and live-proven. The
later-cycle duplicate-transport authoritative repair is closed PASS. Use
`CURRENT_HANDOFF.md` for the live HEAD after that repair closeout
documentation commit.

Allowed now:

- establish fresh exact-HEAD / exact-DB readiness / governance after the
  repair closeout commit exists;
- do not enter that lane automatically;
- do not prepare or apply an authorization in this closeout.

Do not redo the completed authorization-boundary design.
Do not reuse either consumed Sep-1 authorization.
Do not retry, rerun, resume, restart, or create a successor from those runs.
Do not create an application marker.
Do not call `apply_authorization_once`.
Do not prepare another authorization.
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
