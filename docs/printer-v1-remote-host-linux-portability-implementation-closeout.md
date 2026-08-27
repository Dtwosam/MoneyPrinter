# Printer V1 — Remote Host Linux Portability Implementation Closeout

Date: 2026-08-27

Lane: `REMOTE HOST NATIVE LINUX / SYSTEMD PORTABILITY — BOUNDED IMPLEMENTATION`

Verdict:

`REMOTE_HOST_LINUX_PORTABILITY_IMPLEMENTATION_PASS__NATIVE_HOST_RUNTIME_SETUP_NEXT`

## 1. Authority and scope

This closeout is subordinate to the active Printer V1 source stack:

1. `AGENTS.md`
2. `docs/printer-v1-clean-master-spec.md`
3. `docs/printer-v1-post-rc-build-order.md`
4. `docs/printer-v1-memory-factory-guide.md`
5. `docs/printer-v1-current-state-memory-growth-audit.md`
6. `docs/printer-v1-memory-growth-build-order-v2.md`

The governing design is:

`docs/printer-v1-remote-host-native-linux-systemd-portability-design.md`

The operator explicitly approved the narrow implementation slice after design review. This closeout covers implementation plus bounded offline proof only. It does not claim native Linux/systemd lifecycle proof, migration/cutover, authorization preparation/application, Printer execution, provider/RPC/WebSocket activity, Central Scheduler runtime, authoritative DB mutation, retrieval, decisions, positions, trades, PnL, 12h, or 24h capability.

## 2. Exact implementation baseline

Approved implementation starting commit:

`fd558c9e8a691ee1963509d7488aef05908f93c7`

Implementation branch:

`agent/remote-host-linux-portability-implementation`

Implementation code/test HEAD before this documentation commit:

`a6705249699f39357a6c2f2f21d3d23de30826f0`

Authoritative DB remains:

`data/printer_v1.sqlite3`

Carried authoritative DB SHA-256:

`f4e54b3a2dc9f4dbd41b6f05bb5288f25ca15dc71b7e66de1e05ef7c213e34b1`

No authoritative DB mutation or transfer occurred in this lane.

The previously consumed Mac authorization remains permanently non-reusable and creates no remote-host authority.

## 3. Implemented portability surface

The implementation remains infrastructure-only and keeps the four-token standard-four-hour one-shot wrapper as the sole operational application boundary.

Implemented files are limited to:

- `deploy/systemd/printer-v1-four-token-standard-four-hour.service`
- `src/printer_v1/operator_cli/four_token_standard_four_hour_linux_service.py`
- `src/printer_v1/operator_cli/linux_remote_host_portability.py`
- narrow durability changes in `operational_backup_restore_preflight.py`, `window_15m_child_terminal.py`, and `window_15m_one_shot_wrapper.py`
- remote-host-focused unit/fixture tests.

No business logic, discovery policy, source adapter policy, Source Governor policy, Central Scheduler policy, schema/migration, capacity/window rule, authorization schema, retrieval path, or financial path was changed.

## 4. Wrapper-owned Linux service boundary

The native service invokes:

`printer_v1.operator_cli.four_token_standard_four_hour_linux_service`

That module enters the existing four-token one-shot wrapper once. It does not invoke `operational_memory_factory_command` directly as the systemd child boundary.

The systemd artifact remains manual and non-restarting:

- `Type=exec`
- `Restart=no`
- `RemainAfterExit=no`
- `KillMode=mixed`
- `KillSignal=SIGTERM`
- `FinalKillSignal=SIGKILL`
- `SendSIGKILL=yes`
- candidate `TimeoutStopSec=300s`
- `UMask=0077`
- dedicated `printer-v1` user/group
- no `[Install]` / `WantedBy=` auto-enable path
- no timer, watchdog, `ExecStartPre`, or `ExecStopPost` operational helper.

`TimeoutStopSec=300s` remains a candidate value only. Native proof must demonstrate that the worst observed cooperative terminalization envelope fits within it with margin before it can be accepted.

## 5. Signal and cooperative-stop implementation

SIGTERM/SIGINT handlers are installed before host preflight and perform process-local state changes only.

The first normal stop request does not call `terminate()`, `kill()`, or `send_signal()` on the operational child. Foreground supervision instead:

1. records stop intent;
2. resolves exactly one current `ACTIVE`/`STOPPING` campaign supervision attributable to this child start;
3. invokes the existing `request_campaign_cancellation` owner at most once;
4. leaves the child alive for canonical cancellation, terminalization, cleanup, zero-active-work verification, lease release, and reporting;
5. relies on systemd forced cgroup escalation only after the finite grace period.

Ambiguous or uninspectable supervision fails closed and cannot mutate a merely historical latest campaign.

## 6. Linux filesystem, durability, disk, and time readiness

The first supported authoritative filesystem remains local `ext4` only, resolved from `/proc/self/mountinfo`. Unknown, remote, virtual, or other filesystem types fail before authorization consumption.

Linux directory durability is fail-closed. Create-once/application publication, child terminal publication, wrapper terminal publication through the shared helper, and verified backup publication do not report success when parent-directory durability is unconfirmed. A marker-created durability failure remains consumed and cannot manufacture retry authority.

The service now also enforces the design-required free-space and clock-readiness gates before one-shot authorization application.

Disk reserve is derived only from current DB size and the existing campaign storage-growth ceiling:

`3 * current_db_size + storage_growth_ceiling + max(current_db_size, storage_growth_ceiling)`

The three DB-sized reserves cover normal SQLite temporary/journal headroom, one verified backup, and one disposable restore rehearsal. The final term is terminal/report/log margin. Every declared authoritative write root must independently expose at least that free-space reserve.

The storage-growth input is the existing operational owner `STORAGE_BYTE_CEILING`; no new campaign budget or capacity was invented.

System time readiness uses one bounded read-only `timedatectl show --property=NTPSynchronized --value` probe and requires exact synchronized evidence. It does not configure or start a time service.

## 7. Linux process inventory

The existing bounded POSIX process-inventory owner remains the single `ps` owner. The Linux adapter validates the same one-pass output before the historical parser consumes it.

Expected command:

`ps -axo pid=,command=`

Malformed non-empty output, command failure, or parse uncertainty blocks. No polling, signal, kill, or recovery loop was introduced.

## 8. Bounded offline proof

Fresh implementation closeout evidence was run in a disposable Linux execution environment without providers, Scheduler runtime, Printer campaigns, or authoritative DB mutation.

The bounded portability harness executed 30 tests across the exact changed boundaries and committed remote-host test contracts:

- host disk-space and time-sync readiness;
- service pre-authorization ordering and stop interruption;
- ext4 mount parsing/positive gating;
- directory fsync and symlink rejection;
- exact supervision resolution;
- exactly-once cooperative cancellation;
- no direct child signal path;
- bounded Linux `ps` parsing/failure behavior;
- service entrypoint/wrapper injection and terminal classification;
- systemd safety-policy assertions;
- shared create-once directory durability;
- child-terminal directory durability;
- verified-backup directory durability.

Result:

`30 passed / 0 failed`

This was a bounded offline harness assembled from the branch implementation bodies and committed remote-host tests. It is not represented as a full repository regression suite or as native Python 3.11/systemd lifecycle proof.

The service unit was also checked with `systemd-analyze 257`. With its required executable/environment/working-path layout supplied in a disposable host stub, `systemd-analyze verify` exited `0`.

## 9. What is not yet proven

Native-host proof remains mandatory. In particular, this closeout does not prove:

- a fresh repo-local Python 3.11 venv on the selected host;
- the exact Python patch, SQLite, OpenSSL, `websockets`, `certifi`, Git, and procps versions for that host;
- real ext4 mount identity for final remote DB/artifact roots;
- dedicated service-account ownership/permissions on the final host;
- actual synchronized-clock state on the final host;
- actual disk reserve on the final host;
- real `systemctl start/stop` behavior;
- pre-marker, post-marker/pre-supervision, active pre-lifecycle, or active lifecycle SIGTERM through systemd;
- repeated-signal idempotence through systemd;
- forced `TimeoutStopSec` escalation and no-restart behavior;
- reboot/no-boot-relaunch behavior;
- final acceptance of the 300-second stop grace;
- final-host SQLite `DELETE/FULL/normal` evidence;
- Mac/VPS authoritative-writer fencing;
- authoritative DB migration/cutover;
- any fresh remote authorization or Printer campaign.

## 10. Exact next permitted action

`REMOTE HOST NATIVE LINUX/SYSTEMD PROOF — HOST/RUNTIME ESTABLISHMENT`

The next action is to prepare the native proof environment only far enough to establish the required host/runtime evidence:

1. selected Linux host with native systemd;
2. positively proven local ext4 roots;
3. dedicated unprivileged `printer-v1` account/group and durable HOME;
4. final candidate repository checkout for proof;
5. fresh repo-local Python 3.11 venv — never copy the Mac venv;
6. exact runtime/dependency record: Python patch, SQLite, OpenSSL, `websockets`, `certifi`, Git, procps;
7. service-path ownership/permissions, disk-space readiness, and time-sync readiness;
8. static unit verification against that real layout.

After those prerequisites are recorded, continue the bounded native systemd proof matrix on disposable/frozen targets. Any proof that would run the operational Printer child, contact providers/RPC/WebSocket, or mutate a campaign target requires its own explicit proof authority before execution.

Do not transfer the authoritative DB, prepare/apply a remote production authorization, or run an authoritative Printer campaign during host/runtime establishment.

## 11. Migration/cutover remains later

Migration/cutover remains blocked until native Linux/systemd proof passes and the operator separately approves cutover.

The later cutover must still fence Mac authoritative writes first, prove quiescence/no SQLite sidecars, copy the DB offline, verify SHA/integrity/FK/migrations remotely, establish final remote Git/DB/filesystem identity, and only then prepare a fresh remote one-shot authorization followed by an independent review and separate explicit start action.

## 12. Permanent V1 locks

All permanent locks remain unchanged:

- Solana-only;
- Solana memecoin-only;
- paper-trading only;
- no live wallet/private keys/signing/real funds/live execution;
- no paid API dependency;
- no scoring/ranking/confidence percentages/weighted decision logic;
- no embeddings/vectors;
- no Source Governor or Central Scheduler bypass;
- no dirty-memory retrieval/decisions;
- retrieval, BUY/SELL/HOLD, positions, trades, audits, and PnL remain locked;
- `WINDOW_5M_MICRO_EVENT` remains support-only;
- `WINDOW_12H` and `WINDOW_24H` remain locked.
