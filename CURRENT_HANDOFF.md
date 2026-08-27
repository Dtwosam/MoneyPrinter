# CURRENT_HANDOFF — Printer V1

## Current lane

`REMOTE HOST NATIVE LINUX/SYSTEMD PROOF — HOST/RUNTIME ESTABLISHMENT`

Infrastructure support only. The active Printer memory-growth capability ordering is unchanged.

## Latest completed work

The approved native Linux/systemd portability implementation is complete through bounded offline implementation proof.

Implementation verdict:

`REMOTE_HOST_LINUX_PORTABILITY_IMPLEMENTATION_PASS__NATIVE_HOST_RUNTIME_SETUP_NEXT`

Implementation closeout:

`docs/printer-v1-remote-host-linux-portability-implementation-closeout.md`

Closeout commit:

`a728ba3d034ab7e883f67f4ef3a253dddf4c96c8`

Implementation code/test baseline before closeout documentation:

`a6705249699f39357a6c2f2f21d3d23de30826f0`

Governing design remains:

`docs/printer-v1-remote-host-native-linux-systemd-portability-design.md`

Native Linux/systemd lifecycle proof is NOT yet passed.

## Repository / data baseline

Repository:

`/Users/Dtwo1/Developer/MoneyPrinter`

Active implementation/proof branch:

`agent/remote-host-linux-portability-implementation`

Approved implementation starting commit:

`fd558c9e8a691ee1963509d7488aef05908f93c7`

The current repository HEAD is the documentation commit containing this handoff. Resolve it with `git rev-parse HEAD`; do not create a self-referential follow-up commit merely to embed its own SHA.

Authoritative DB:

`data/printer_v1.sqlite3`

Carried authoritative DB SHA-256:

`f4e54b3a2dc9f4dbd41b6f05bb5288f25ca15dc71b7e66de1e05ef7c213e34b1`

No authoritative DB mutation or transfer occurred in the portability implementation lane.

## Consumed authorization

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260827T122355Z_8e43eae7`

SHA-256:

`9711e77a5b169edc1e1bf7ee20560450662a373fb41aa05a9ff70e5f6dc3768a`

Permanently consumed. No retry, rerun, resume, restart, reuse, inheritance, successor, or remote-host authority.

## Implemented remote-host contract

The implementation preserves the existing four-token standard-four-hour one-shot wrapper as the sole application boundary.

Implemented and boundedly verified:

- native foreground Linux service entrypoint owned by the wrapper;
- manual systemd service artifact with `Type=exec`, `Restart=no`, `KillMode=mixed`, no timer/watchdog/boot enable path;
- process-local SIGTERM/SIGINT stop intent with no signal-handler I/O;
- exact ACTIVE/STOPPING supervision resolution before one existing cooperative cancellation request;
- no direct child `terminate()`, `kill()`, or `send_signal()` path;
- positive local-ext4 preflight from `/proc/self/mountinfo`;
- strict Linux `ps -axo pid=,command=` validation around the existing one-pass inventory owner;
- fail-closed Linux parent-directory durability for shared create-once artifacts, child terminal, wrapper terminal through the shared owner, and verified backup publication;
- fail-closed pre-authorization free-space readiness derived from current DB size plus the existing storage-growth ceiling;
- fail-closed `timedatectl` synchronization evidence before authorization application;
- exact service success only for validated `CHILD_EXITED_ZERO` terminal truth.

Bounded offline evidence recorded in the implementation closeout:

`30 passed / 0 failed`

This is bounded offline portability evidence, not a full repository regression suite and not native systemd lifecycle proof.

Static unit verification with `systemd-analyze 257` exits `0` when the required service paths are supplied in a disposable host layout.

## Exact next permitted action

`REMOTE HOST NATIVE LINUX/SYSTEMD PROOF — HOST/RUNTIME ESTABLISHMENT`

Allowed now:

1. select/prepare the native Linux proof host with systemd;
2. positively prove local ext4 for candidate DB/application/artifact roots;
3. create the dedicated unprivileged `printer-v1` account/group and durable HOME;
4. establish the candidate remote repository checkout;
5. create a fresh repo-local Python 3.11 venv — never copy the Mac venv;
6. record the exact Python patch, SQLite, OpenSSL, `websockets`, `certifi`, Git, and procps versions;
7. establish service path ownership/permissions and `UMask=0077` compatibility;
8. prove host disk-space and time-sync readiness;
9. run static systemd unit verification against the actual host layout;
10. prepare the bounded native proof evidence plan on disposable/frozen targets.

Do not yet:

- transfer the authoritative DB;
- create or apply a fresh remote production authorization;
- run an authoritative Printer campaign;
- contact providers/RPC/WebSocket as part of host/runtime establishment;
- run Central Scheduler work;
- mutate the authoritative DB;
- activate retrieval or financial capability;
- claim `TimeoutStopSec=300s` accepted before real cooperative-stop timing proof.

If a later native proof case would run the operational Printer child, contact providers/RPC/WebSocket, or mutate a campaign target, stop and require its own explicit bounded proof authority before execution.

## Native proof still required

Before remote portability can close completely, prove on the actual selected Linux/systemd host:

- exact fresh Python 3.11 runtime/dependency set from the final candidate checkout;
- real ext4 mount identity and fail-closed non-ext4 behavior;
- real service-user ownership and permissions;
- real disk-space and synchronized-clock readiness;
- `ps` behavior with the selected procps version;
- manual systemd start with exactly one wrapper boundary;
- pre-marker SIGTERM with no campaign/retry;
- post-marker/pre-supervision consumed-authority handling;
- active pre-lifecycle and lifecycle SIGTERM through exactly one cooperative stop request;
- repeated signal idempotence;
- forced stop timeout behavior and no automatic restart;
- service failure/reboot with no boot relaunch;
- SQLite `DELETE/FULL/normal` preservation and no unintended WAL;
- owner boundaries and all capability locks;
- cooperative cleanup timing sufficient to accept or revise the candidate `TimeoutStopSec=300s`.

## Migration/cutover remains later

Migration/cutover is blocked until native Linux/systemd proof passes and the operator separately approves cutover.

The later sequence remains: fence Mac authoritative writes -> prove quiescence/no SQLite sidecars -> offline DB copy -> verify remote SHA/integrity/FK/migration ledger -> establish final remote Git/runtime/service-user/ext4 identity -> prove Mac remains fenced -> capture final remote DB path/SHA/size/inode/mtime and exact Git HEAD -> only then prepare a fresh remote one-shot authorization -> independent review -> separate explicit operator start.

Copying DB bytes never transfers authorization.

## Permanent locks

Solana-only; Solana memecoin-only; paper-trading only. No live wallet, private keys, signing, real funds, or live execution. No paid API dependency. No scoring, ranking, confidence percentages, weighted decision logic, embeddings, or vectors. No Source Governor or Central Scheduler bypass. No dirty memory for retrieval or decisions. Retrieval, BUY/SELL/HOLD, positions, trades, audits, and PnL remain locked. `WINDOW_5M_MICRO_EVENT` remains support-only. `WINDOW_12H` and `WINDOW_24H` remain locked.

The active authority stack wins any conflict with this handoff.
