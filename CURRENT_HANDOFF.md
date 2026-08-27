# CURRENT_HANDOFF — Printer V1

## Current lane

`REMOTE HOST DESIGN / SPECIFICATION — OPERATOR REVIEW / IMPLEMENTATION APPROVAL GATE`

Design/specification lane only. Infrastructure support only. The active Printer memory-growth capability ordering is unchanged.

## Latest completed work

Native Linux/systemd one-shot portability design is complete.

Design verdict:

`REMOTE_HOST_NATIVE_LINUX_SYSTEMD_PORTABILITY_DESIGN_PASS__OPERATOR_REVIEW_NEXT`

Design document:

`docs/printer-v1-remote-host-native-linux-systemd-portability-design.md`

Prior readiness verdict remains:

`REMOTE_HOST_READINESS_CLOSEOUT_PASS__REMOTE_HOST_DESIGN_SPECIFICATION_NEXT`

Readiness closeout:

`docs/printer-v1-remote-host-readiness-audit-closeout.md`

## Repository / data baseline

Repository:

`/Users/Dtwo1/Developer/MoneyPrinter`

Branch:

`agent/v2-9-8b-aug25-a2z-repair-application`

Design baseline HEAD:

`82c5de6be28d7869fb4b31cd5eda09eb237d2f6c`

The current repository HEAD is the documentation commit containing this handoff/design. Resolve it with `git rev-parse HEAD`; do not create a self-referential follow-up commit merely to embed its own SHA.

Authoritative DB:

`data/printer_v1.sqlite3`

Authoritative DB SHA-256:

`f4e54b3a2dc9f4dbd41b6f05bb5288f25ca15dc71b7e66de1e05ef7c213e34b1`

Do not restore the pre-campaign DB.

## Consumed authorization

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260827T122355Z_8e43eae7`

SHA-256:

`9711e77a5b169edc1e1bf7ee20560450662a373fb41aa05a9ff70e5f6dc3768a`

Permanently consumed. No retry, rerun, resume, restart, reuse, inheritance, or successor. It cannot become remote-host authority.

## Accepted design

The design keeps the existing four-token standard-four-hour one-shot wrapper as the only operational application boundary. It does not create a second Memory Factory runner, Source Governor, Central Scheduler, discovery loop, campaign policy, or authorization model.

Key design commitments:

- native systemd supervises the wrapper, never the child operational command directly;
- foreground service, `Type=exec`, `Restart=no`, no timer/watchdog/boot relaunch;
- first stop signal targets the wrapper only under `KillMode=mixed` semantics;
- wrapper translates stop intent into the existing persisted cooperative-cancellation path after exact active ownership is proven;
- child remains alive to perform canonical Scheduler cancellation, terminalization, cleanup, zero-active-work verification, lease release and terminal reporting;
- forced service escalation is bounded, never creates restart authority, and never makes a consumed authorization reusable;
- parent-directory durability becomes fail-closed at application/manifest/marker/child-terminal/wrapper-terminal/backup publication boundaries;
- marker-created directory-durability failure is consumed-with-durability-unconfirmed, never a retry path;
- first remote filesystem profile is positively proven local ext4 only; remote/unknown filesystems fail closed;
- fresh Linux `.venv` and one exact tested runtime/dependency set are required; Mac `.venv` is never copied;
- existing POSIX `ps -axo pid=,command=` inventory is proven on Linux before any repair is justified;
- SQLite DELETE/FULL/normal semantics and sole-authoritative-writer rule remain unchanged;
- Mac/VPS authoritative write overlap is forbidden;
- final remote Git/DB/filesystem identity must exist before any fresh remote authorization is prepared.

## Exact next permitted action

`REMOTE HOST DESIGN / SPECIFICATION — OPERATOR REVIEW / IMPLEMENTATION APPROVAL GATE`

Allowed now:

- review `docs/printer-v1-remote-host-native-linux-systemd-portability-design.md` against the active authority stack;
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

## Future implementation scope if explicitly approved

Expected narrow scope only:

- wrapper-owned Linux CLI/systemd foreground signal supervision;
- fail-closed directory durability primitives;
- child-terminal durable parent publication;
- positive local-ext4 filesystem preflight;
- exact Linux runtime/dependency verification;
- focused tests and a bounded Linux/systemd proof plan.

No business logic, source adapters, Scheduler policy, Source Governor policy, DB schema/migrations, capacity/window policy, retrieval, or financial capability is approved by this handoff.

## Permanent locks

Solana-only; Solana memecoin-only; paper-trading only. No live wallet, private keys, signing, real funds, or live execution. No paid API dependency. No scoring, ranking, confidence percentages, weighted decision logic, embeddings, or vectors. No Source Governor or Central Scheduler bypass. No dirty memory for retrieval or decisions. Retrieval, BUY/SELL/HOLD, positions, trades, audits, and PnL remain locked. `WINDOW_5M_MICRO_EVENT` remains support-only. 12h/24h remain locked.

The active authority stack wins any conflict with this handoff.