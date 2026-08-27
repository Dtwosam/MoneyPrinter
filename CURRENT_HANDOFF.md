# CURRENT_HANDOFF — Printer V1

## Current lane

`REMOTE HOST DESIGN / SPECIFICATION — NATIVE LINUX / SYSTEMD ONE-SHOT PORTABILITY`

Design/specification only. Infrastructure support only. The active Printer memory-growth capability ordering is unchanged.

## Latest completed work

Remote-host readiness / portability audit is closed PASS.

Readiness closeout verdict:

`REMOTE_HOST_READINESS_CLOSEOUT_PASS__REMOTE_HOST_DESIGN_SPECIFICATION_NEXT`

Readiness-review verdict:

`REMOTE_HOST_READINESS_ACCEPTED__ADVANCE_TO_REMOTE_HOST_DESIGN_SPECIFICATION`

Closeout document:

`docs/printer-v1-remote-host-readiness-audit-closeout.md`

## Repository / data baseline

Repository:

`/Users/Dtwo1/Developer/MoneyPrinter`

Branch:

`agent/v2-9-8b-aug25-a2z-repair-application`

Audited pre-closeout HEAD:

`dc945c203ad5e158d62bed60d8b471cda6efaa17`

The current repository HEAD is the documentation commit containing this handoff. Resolve it from the repository with `git rev-parse HEAD`; do not create a second self-referential documentation commit merely to embed its own SHA.

Authoritative DB:

`data/printer_v1.sqlite3`

Authoritative DB SHA-256:

`f4e54b3a2dc9f4dbd41b6f05bb5288f25ca15dc71b7e66de1e05ef7c213e34b1`

Do not restore the pre-campaign DB.

## Consumed authorization

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260827T122355Z_8e43eae7`

SHA-256:

`9711e77a5b169edc1e1bf7ee20560450662a373fb41aa05a9ff70e5f6dc3768a`

Permanently consumed. No retry, rerun, resume, restart, reuse, inheritance, or successor.

## Remote-host readiness outcome

Readiness passed for design only. Direct VPS deployment remains blocked.

Accepted design inputs include:

- missing supported wrapper-owned Linux/systemd entrypoint;
- unresolved Linux/systemd signal safe-stop contract;
- directory-durability gap at authorization-consumption / selected terminal publication boundaries;
- missing positive POSIX local-filesystem suitability guard/proof;
- Linux runtime/dependency reproducibility and `ps` behavior needing bounded proof;
- sole authoritative host/writer requirement;
- exact remote authorization binding after final remote DB identity;
- `Restart=no` / no timer / no watchdog / no reboot relaunch;
- current SQLite DELETE/FULL/normal semantics preserved unless separately redesigned.

Mac-specific venvs, PowerShell helpers, `caffeinate`, historical Mac paths, and other non-runtime operator tooling are not automatically product defects and must not trigger a broad cleanup.

## Exact next permitted action

`REMOTE HOST DESIGN / SPECIFICATION — NATIVE LINUX / SYSTEMD ONE-SHOT PORTABILITY`

Design only:

- define the canonical wrapper-owned Linux entrypoint;
- define systemd one-shot supervision and no-restart semantics;
- define signal safe-stop behavior;
- define parent-directory durability requirements;
- define positive local-filesystem preflight;
- define pinned/tested Linux runtime inputs and bounded proof matrix;
- define sole-host offline cutover invariants and permanent Mac writer fencing;
- define minimum permissions, credentials, disk, logs, and retention controls.

Assign every requirement to the narrowest existing canonical owner before proposing code.

Do not implement yet.
Do not provision a server.
Do not transfer the DB.
Do not create or apply an authorization.
Do not run Printer.
Do not contact providers/RPC/WebSocket.
Do not run Central Scheduler.
Do not mutate the authoritative DB.
Do not activate retrieval or any financial capability.

## Permanent locks

Solana-only; Solana memecoin-only; paper-trading only. No live wallet, private keys, signing, real funds, or live execution. No paid API dependency. No scoring, ranking, confidence percentages, weighted decision logic, embeddings, or vectors. No Source Governor or Central Scheduler bypass. No dirty memory for retrieval or decisions. Retrieval, BUY/SELL/HOLD, positions, trades, audits, and PnL remain locked. `WINDOW_5M_MICRO_EVENT` remains support-only. 12h/24h remain locked.

The active authority stack wins any conflict with this handoff.
