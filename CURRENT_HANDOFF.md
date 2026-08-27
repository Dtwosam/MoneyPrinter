# CURRENT_HANDOFF — Printer V1

## Current lane

`REMOTE HOST NATIVE LINUX/SYSTEMD PROOF — HOST/RUNTIME ESTABLISHMENT`

Infrastructure support only. The active Printer memory-growth capability ordering is unchanged.

## Latest completed work

The approved native Linux/systemd portability implementation is closed through bounded offline implementation proof.

Implementation verdict:

`REMOTE_HOST_LINUX_PORTABILITY_IMPLEMENTATION_PASS__NATIVE_HOST_RUNTIME_SETUP_NEXT`

Implementation closeout:

`docs/printer-v1-remote-host-linux-portability-implementation-closeout.md`

Closeout commit:

`a728ba3d034ab7e883f67f4ef3a253dddf4c96c8`

A read-only native-host/runtime proof preflight is now implemented:

`src/printer_v1/operator_cli/linux_remote_host_native_preflight.py`

Proof-support commit before this handoff update:

`3ddba7c52140929d661113106f38c7724827f876`

The preflight requires and records:

- native Linux;
- exact Python 3.11 patch from `<repo>/.venv/bin/python`;
- SQLite and OpenSSL runtime versions;
- exact installed `websockets` and `certifi` versions;
- Git version, exact branch and HEAD;
- procps version plus successful parsing through the existing one-pass `ps -axo pid=,command=` owner;
- dedicated unprivileged `printer-v1` account/group, durable private HOME, and non-broadly-writable repository root;
- positive local-ext4 evidence for candidate sizing/application/artifact roots;
- fail-closed free-space readiness using the existing operational storage ceiling;
- synchronized-clock evidence through bounded `timedatectl` inspection;
- `systemd-analyze` version and static unit verification.

It creates no authorization, starts no Printer child, contacts no provider/RPC/WebSocket, runs no Central Scheduler work, and performs no database write.

Fresh bounded reconstructed remote-host test evidence after adding this proof-support surface:

`33 passed / 0 failed`

This remains bounded offline evidence assembled from the exact changed implementation bodies and committed remote-host tests. It is not a full repository regression suite and is not native Linux/systemd lifecycle proof.

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

Resolve the current documentation HEAD with `git rev-parse HEAD`; do not create a self-referential follow-up commit merely to embed its own SHA.

Authoritative DB:

`data/printer_v1.sqlite3`

Carried authoritative DB SHA-256:

`f4e54b3a2dc9f4dbd41b6f05bb5288f25ca15dc71b7e66de1e05ef7c213e34b1`

No authoritative DB mutation or transfer occurred in the portability implementation or host-proof-support work.

## Consumed authorization

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260827T122355Z_8e43eae7`

SHA-256:

`9711e77a5b169edc1e1bf7ee20560450662a373fb41aa05a9ff70e5f6dc3768a`

Permanently consumed. No retry, rerun, resume, restart, reuse, inheritance, successor, or remote-host authority.

## Implemented remote-host contract

The existing four-token standard-four-hour one-shot wrapper remains the sole application boundary.

Implemented and boundedly verified:

- native foreground Linux service entrypoint owned by the wrapper;
- manual systemd service with `Type=exec`, `Restart=no`, `KillMode=mixed`, no timer/watchdog/boot-enable path;
- process-local SIGTERM/SIGINT stop intent with no signal-handler I/O;
- exact ACTIVE/STOPPING supervision resolution before one existing cooperative cancellation request;
- no direct child `terminate()`, `kill()`, or `send_signal()` path;
- positive local-ext4 preflight from `/proc/self/mountinfo`;
- strict Linux process-output validation around the existing one-pass inventory owner;
- fail-closed Linux parent-directory durability for shared create-once artifacts, child terminal, wrapper terminal through the shared owner, and verified backup publication;
- fail-closed pre-authorization free-space readiness derived from current DB size plus the existing `STORAGE_BYTE_CEILING`;
- fail-closed synchronized-clock evidence before authorization application;
- exact service success only for validated `CHILD_EXITED_ZERO` terminal truth;
- read-only native runtime/service-account/Git/procps/systemd proof evidence collection.

Static unit verification with `systemd-analyze 257` exits `0` when the required service layout is supplied in a disposable host stub. `TimeoutStopSec=300s` remains a candidate until real cooperative-stop timing proof.

## Exact next permitted action

`REMOTE HOST NATIVE LINUX/SYSTEMD PROOF — HOST/RUNTIME ESTABLISHMENT`

On the selected native Linux/systemd proof host, establish only the non-operational proof prerequisites:

1. final candidate checkout at `/opt/printer-v1` on local ext4;
2. dedicated unprivileged `printer-v1` user/group with durable private HOME `/var/lib/printer-v1`;
3. fresh repo-local Python 3.11 venv at `/opt/printer-v1/.venv` — never copy the Mac venv;
4. install the repository's required runtime dependencies into that venv;
5. provide one disposable local sizing file on the candidate ext4 root whose byte size equals the current authoritative DB byte size; the sizing file must not contain authoritative DB contents and is not a DB transfer;
6. establish candidate application/artifact roots under the service HOME;
7. run the read-only native-host preflight below and preserve its JSON output as proof evidence.

Canonical service-HOME-derived roots are:

- application root: `/var/lib/printer-v1/PrinterOperations/v2-9-8/four-token-standard-four-hour-one-shot-applications`
- operational artifact root: `/var/lib/printer-v1/PrinterOperations/v2-9-8`

Example proof command:

```bash
/opt/printer-v1/.venv/bin/python -m printer_v1.operator_cli.linux_remote_host_native_preflight \
  --repository-root /opt/printer-v1 \
  --sizing-db-path /var/lib/printer-v1/proof/printer-v1-sizing.sqlite3 \
  --application-root /var/lib/printer-v1/PrinterOperations/v2-9-8/four-token-standard-four-hour-one-shot-applications \
  --artifact-root /var/lib/printer-v1/PrinterOperations/v2-9-8 \
  --systemd-unit /opt/printer-v1/deploy/systemd/printer-v1-four-token-standard-four-hour.service
```

Expected success status:

`REMOTE_HOST_NATIVE_RUNTIME_PREFLIGHT_READY`

If the tool returns `REMOTE_HOST_NATIVE_RUNTIME_PREFLIGHT_BLOCKED`, treat the reported host/runtime condition as the blocker. Do not bypass it and do not create authorization authority from a blocked host.

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

- the read-only runtime preflight above returns READY on the real host;
- real service-user ownership and permissions;
- real ext4, disk-space, synchronized-clock, Git and procps evidence;
- manual systemd start with exactly one wrapper boundary;
- pre-marker SIGTERM with no campaign/retry;
- post-marker/pre-supervision consumed-authority handling;
- active pre-lifecycle and lifecycle SIGTERM through exactly one cooperative stop request;
- repeated signal idempotence;
- forced stop timeout behavior and no automatic restart;
- service failure/reboot with no boot relaunch;
- SQLite `DELETE/FULL/normal` preservation and no unintended WAL;
- owner boundaries and all capability locks;
- cooperative cleanup timing sufficient to accept or revise candidate `TimeoutStopSec=300s`.

## Migration/cutover remains later

Migration/cutover is blocked until native Linux/systemd proof passes and the operator separately approves cutover.

The later sequence remains: fence Mac authoritative writes -> prove quiescence/no SQLite sidecars -> offline DB copy -> verify remote SHA/integrity/FK/migration ledger -> establish final remote Git/runtime/service-user/ext4 identity -> prove Mac remains fenced -> capture final remote DB path/SHA/size/inode/mtime and exact Git HEAD -> only then prepare a fresh remote one-shot authorization -> independent review -> separate explicit operator start.

Copying DB bytes never transfers authorization.

## Permanent locks

Solana-only; Solana memecoin-only; paper-trading only. No live wallet, private keys, signing, real funds, or live execution. No paid API dependency. No scoring, ranking, confidence percentages, weighted decision logic, embeddings, or vectors. No Source Governor or Central Scheduler bypass. No dirty memory for retrieval or decisions. Retrieval, BUY/SELL/HOLD, positions, trades, audits, and PnL remain locked. `WINDOW_5M_MICRO_EVENT` remains support-only. `WINDOW_12H` and `WINDOW_24H` remain locked.

The active authority stack wins any conflict with this handoff.
