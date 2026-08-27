# Printer V1 — Remote Host Readiness / Portability Audit Closeout

Status: **CLOSED — PASS TO DESIGN**

Closeout verdict:

`REMOTE_HOST_READINESS_CLOSEOUT_PASS__REMOTE_HOST_DESIGN_SPECIFICATION_NEXT`

Readiness-review verdict:

`REMOTE_HOST_READINESS_ACCEPTED__ADVANCE_TO_REMOTE_HOST_DESIGN_SPECIFICATION`

## 1. Authority and scope

This closeout is documentation-only infrastructure support. It is subordinate to the active Printer V1 source stack:

1. `AGENTS.md`
2. `docs/printer-v1-clean-master-spec.md`
3. `docs/printer-v1-post-rc-build-order.md`
4. `docs/printer-v1-memory-factory-guide.md`
5. `docs/printer-v1-current-state-memory-growth-audit.md`
6. `docs/printer-v1-memory-growth-build-order-v2.md`

`CURRENT_HANDOFF.md` supplies current lane/current commit/latest-completed-work/blockers/next-action state only. Higher authority wins any conflict.

This lane does not advance or reorder the memory-growth capability sequence.

## 2. Exact audited baseline

Repository:

`/Users/Dtwo1/Developer/MoneyPrinter`

Branch:

`agent/v2-9-8b-aug25-a2z-repair-application`

Audited repository HEAD:

`dc945c203ad5e158d62bed60d8b471cda6efaa17`

Authoritative DB:

`data/printer_v1.sqlite3`

Authoritative DB SHA-256:

`f4e54b3a2dc9f4dbd41b6f05bb5288f25ca15dc71b7e66de1e05ef7c213e34b1`

The pre-campaign DB is not authoritative and must not be restored.

Consumed authorization:

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260827T122355Z_8e43eae7`

Authorization SHA-256:

`9711e77a5b169edc1e1bf7ee20560450662a373fb41aa05a9ff70e5f6dc3768a`

It is permanently consumed. It must never be retried, rerun, resumed, restarted, reused, inherited, or treated as successor authority.

## 3. Readiness decision

The independent audit and source-stack review support:

`PASS_TO_DESIGN`

This means the repository has been investigated enough to begin a narrow remote-host design/specification lane.

It does **not** mean the repository is approved for direct Linux/VPS deployment.

Direct deployment remains blocked until the required design, approved implementation where applicable, bounded proof, and migration/cutover closeout are complete.

## 4. Accepted finding classifications

### Proven portability / deployment gaps

- There is no committed stable wrapper-owned Linux/systemd `ExecStart` surface for the current four-token one-shot authority.
- A supported native Linux one-shot entrypoint must be designed around the existing canonical wrapper rather than creating a second runner or scheduler.

### Deployment / supervision safety gap

- Current Linux/systemd termination behavior is not sufficiently specified or proven.
- The next design must define how SIGTERM/SIGINT and other selected termination paths reach existing fail-closed safe-stop/terminalization behavior.
- The design must preserve permanent non-resumability after authorization consumption.
- This finding requires design resolution; it does not pre-decide that a particular Python implementation is the only valid owner.

### Durability defect / requirement

- File fsync alone is not sufficient at every authorization-consumption and selected terminal-publication boundary if the containing directory entry has not been durably committed.
- The next design must identify the exact create/replace boundaries where confirmed parent-directory fsync is mandatory and fail closed when that durability contract cannot be established.

### POSIX filesystem guard gap

- The current Windows-UNC-style network-path guard does not positively establish that a Linux path is on a supported local filesystem.
- The design must assign this requirement to the narrowest suitable owner: runtime preflight, deployment preflight, or both.
- NFS/SMB/FUSE and other remote/virtual filesystems are not approved for the authoritative SQLite corpus without separate evidence proving the required locking, fsync, and atomic-rename semantics.

### Runtime reproducibility requirement

- The intended Linux Python, SQLite, websockets, Git, and process-tool environment is not yet pinned and bounded-proven.
- This is a deployment reproducibility requirement rather than proof that current Mac product behavior is defective.

### Linux proof requirement

- POSIX liveness inventory using `ps -axo pid=,command=` requires bounded Linux/systemd proof.
- No code change is justified unless that proof exposes a real production-path defect.

## 5. Expected host-specific tooling / non-defects

The following are host/operator concerns and are not automatically Printer product defects:

- `Path.home()/PrinterOperations/...` when used under a stable durable service-account HOME;
- the current Mac-created `.venv`, which must not be copied to Linux;
- PowerShell launch helpers, which must not become a Linux/systemd dependency;
- historical review/repair scripts containing Mac-specific operator paths when they are outside the selected remote runtime path;
- `caffeinate` references that are documentation/operator recommendations rather than active runtime dependencies;
- macOS `/var` versus `/private/var` commentary where the implementation already uses portable real-path normalization;
- Python `tempfile` usage where destination-directory permissions/capacity and durability are otherwise valid.

No broad Mac-tool cleanup is authorized by this closeout.

## 6. Authorization and Git/filesystem binding invariants

A future remote operational authorization may exist only after the remote repository, DB, filesystem paths, ownership, and migration state are final.

The remote authorization must bind the actual remote identity required by the canonical authorization contract, including the exact named branch/HEAD and exact DB identity fields.

A Mac authorization cannot become remote execution authority merely because DB bytes or Git content were copied.

The consumed authorization named above remains permanently dead regardless of host migration, crash, signal, reboot, partial launch, artifact failure, or later repository changes.

Do not widen the authorization identity schema merely to encode deployment controls such as UID, GID, permission mode, or `st_dev` unless a later approved design proves that schema change is required.

Required tracked/untracked/ignored operational evidence for future authorization/provenance must be determined from the canonical reconciliation contract at cutover time. Today's incidental directory count is not a permanent transfer contract.

The remote clock must be synchronized before authorization preparation/application so authorization temporal-validity checks remain meaningful.

## 7. SQLite and sole-writer constraints

The VPS must become the sole authoritative operational DB writer before any future approved remote campaign.

There may be no Mac/VPS write overlap, shared-authority mount, bidirectional sync, or other two-host authoritative write model.

The accepted current SQLite state is:

- journal mode: DELETE;
- synchronous: FULL;
- locking mode: normal;
- no active WAL/SHM/journal sidecars at the audited cutover baseline.

Remote-host work must not silently switch the authoritative DB to WAL.

Any future migration/cutover design must require Mac quiescence, absence of transient SQLite sidecars at transfer, offline copy, exact remote verification, and final remote filesystem identity before remote authorization issuance.

The authoritative DB must live on a durable local filesystem with proven SQLite locking, fsync, and atomic-rename behavior.

## 8. Supervision constraints

Native systemd is the minimum next design target.

The design must preserve:

- one bounded one-shot invocation;
- `Restart=no` or an exactly proven equivalent;
- no timer-driven relaunch;
- no watchdog relaunch;
- no reboot restart;
- no retry, resume, or successor after consumed authority;
- an external timeout, if any, that cannot undercut Printer's approved bounded campaign terminalization envelope.

Containers remain out of scope for this infrastructure lane.

## 9. Deployment/security requirements to design

The next design may specify only the minimum controls needed for safe remote operation, including:

- dedicated unprivileged service account;
- stable durable HOME and working directory;
- restrictive umask and artifact ownership;
- safe credential/environment handling without exposing secrets through unit command lines, Git, manifests, journald, or shell history;
- durable disk capacity and explicit evidence/log retention behavior;
- required Git/process/runtime packages;
- outbound networking only through the already-approved Source-Governed path;
- positive local-filesystem suitability checks;
- time synchronization prerequisites.

No optional free-tier source credential may become a new mandatory paid or provider dependency through infrastructure work.

## 10. What remains a design choice

The readiness audit does not pre-authorize a particular implementation for:

- signal forwarding / cooperative stop ownership;
- the exact Linux entrypoint shape beyond wrapper ownership;
- whether filesystem suitability is enforced by Python, host preflight, or both;
- the minimum reproducible dependency-pinning mechanism;
- exact service paths, service username, or distro-specific package commands;
- retention thresholds and disk-capacity margins.

The next lane must assign each requirement to the narrowest existing canonical owner before proposing code.

## 11. No source/provider blocker found

The readiness audit found no source-scarcity or provider-limitation issue that requires product repair.

This closeout does not authorize:

- new providers;
- provider fallbacks;
- paid APIs;
- new endpoints;
- independent API/network loops;
- Source Governor bypass;
- Central Scheduler bypass.

## 12. Migration/cutover invariants carried forward

A later migration/cutover may proceed only after the prior required lanes pass and must preserve at minimum:

1. Mac Printer execution fully stopped before authoritative transfer.
2. No in-flight one-shot may be migrated, resumed, or continued.
3. No SQLite WAL/SHM/journal sidecars at the transfer boundary.
4. VPS becomes the sole authoritative DB writer; Mac may retain archival evidence but not resume authoritative writes.
5. Offline DB/evidence transfer with exact SHA/size/integrity/foreign-key/migration verification as required by the accepted design.
6. Required provenance evidence transferred according to the current canonical reconciliation contract.
7. Final remote service ownership, paths, permissions, filesystem, and runtime established before authorization.
8. Fresh authorization generated only against the final remote exact HEAD and exact DB identity.
9. No Mac/existing/consumed authorization becomes remote authority.
10. Consumed authority remains dead after crash, reboot, signal, partial launch, or terminal-artifact failure.
11. `Restart=no` or exact equivalent; no automatic retry/resume/restart/successor.
12. Source Governor and Central Scheduler remain exclusive authorities.
13. Infrastructure work does not change capacity, campaign behavior, windows, or capability build-order position.

## 13. Permanent capability locks

Nothing in this closeout unlocks or advances:

- 12h/24h operation;
- retrieval;
- paper decisions;
- BUY, SELL, or HOLD;
- paper positions;
- trade events;
- paper audits;
- PnL;
- live execution;
- wallet/private-key/signing logic;
- paid APIs;
- scoring/ranking/confidence/weighted logic;
- embeddings/vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only and cannot independently create main outcome memory, continuation, retrieval, decisions, positions, or PnL.

## 14. Exact next permitted lane

`REMOTE HOST DESIGN / SPECIFICATION — NATIVE LINUX / SYSTEMD ONE-SHOT PORTABILITY`

Minimum justified design scope:

1. canonical wrapper-owned Linux entrypoint;
2. native systemd one-shot supervision with hard no-restart semantics;
3. safe signal/stop contract;
4. authorization-marker and terminal-evidence directory durability contract;
5. positive local-filesystem suitability preflight;
6. tested/pinned Linux runtime and bounded Linux proof matrix;
7. sole-host offline migration/cutover design and permanent Mac writer fencing;
8. minimum permissions, credential, disk, log, and retention controls.

The design lane must not provision a server, transfer the authoritative DB, create/apply an authorization, run Printer, call providers/RPC/WebSocket, execute Scheduler work, mutate the authoritative DB, or implement runtime/code changes.

## 15. Closeout statement

No Printer code, tests, migrations, source adapters, Scheduler behavior, Source Governor behavior, runtime command, systemd unit, server configuration, authorization, or authoritative DB content was changed by the readiness audit itself.

No Printer campaign was run as part of this readiness closeout.

No deployment or migration occurred.

No V1 capability was advanced.

The readiness lane is closed PASS and the only next permitted work is the design/specification lane stated above.
