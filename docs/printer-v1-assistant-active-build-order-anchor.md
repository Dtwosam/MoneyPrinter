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

## Current durable state — 2026-08-27

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

- authorization: `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260827T122355Z_8e43eae7`;
- authorization SHA-256: `9711e77a5b169edc1e1bf7ee20560450662a373fb41aa05a9ff70e5f6dc3768a`;
- permanently consumed; no retry, rerun, resume, restart, reuse, inheritance, or successor;
- authoritative post-campaign DB SHA-256: `f4e54b3a2dc9f4dbd41b6f05bb5288f25ca15dc71b7e66de1e05ef7c213e34b1`;
- campaign classification: `EXPECTED_OPERATIONAL_BLOCKER__NO_CODE_CHANGE`;
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
REMOTE HOST DESIGN / SPECIFICATION — OPERATOR REVIEW / IMPLEMENTATION APPROVAL GATE
```

Allowed now:

- review the native Linux/systemd portability design against the active authority stack;
- accept, reject, or narrow the design;
- if accepted, explicitly authorize the narrow implementation slice.

Do not implement yet.
Do not provision a server.
Do not transfer the DB.
Do not create or apply an authorization.
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
