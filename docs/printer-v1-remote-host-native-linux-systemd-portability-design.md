# Printer V1 — Native Linux / systemd One-Shot Portability Design

Status: **DESIGN COMPLETE — OPERATOR REVIEW REQUIRED BEFORE IMPLEMENTATION**

Design verdict:

`REMOTE_HOST_NATIVE_LINUX_SYSTEMD_PORTABILITY_DESIGN_PASS__OPERATOR_REVIEW_NEXT`

## 1. Authority and scope

This is a design/specification artifact only. It is subordinate to the active Printer V1 source stack:

1. `AGENTS.md`
2. `docs/printer-v1-clean-master-spec.md`
3. `docs/printer-v1-post-rc-build-order.md`
4. `docs/printer-v1-memory-factory-guide.md`
5. `docs/printer-v1-current-state-memory-growth-audit.md`
6. `docs/printer-v1-memory-growth-build-order-v2.md`

It implements the design step required by:

`readiness/audit -> design/specification -> implementation if approved -> bounded proof/test -> migration/cutover closeout`

This document authorizes no implementation, server provisioning, DB transfer, authorization creation/application, Printer execution, provider/RPC/WebSocket activity, Central Scheduler execution, or capability advancement.

## 2. Exact design baseline

Repository branch:

`agent/v2-9-8b-aug25-a2z-repair-application`

Design baseline HEAD:

`82c5de6be28d7869fb4b31cd5eda09eb237d2f6c`

Authoritative DB:

`data/printer_v1.sqlite3`

Authoritative DB SHA-256 carried from the closed campaign/readiness audit:

`f4e54b3a2dc9f4dbd41b6f05bb5288f25ca15dc71b7e66de1e05ef7c213e34b1`

Consumed authorization:

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260827T122355Z_8e43eae7`

Authorization SHA-256:

`9711e77a5b169edc1e1bf7ee20560450662a373fb41aa05a9ff70e5f6dc3768a`

That authorization remains permanently consumed and may never become remote-host authority.

## 3. Design goals

The remote-host portability slice must make one already-authorized Printer one-shot safely runnable under native Linux/systemd without creating a second operational engine.

The design must preserve:

- the existing four-token standard-four-hour wrapper as the only operational application boundary;
- the existing operational Memory Factory command as the child runtime;
- Source Governor as the exclusive source-call authority;
- Central Scheduler as the exclusive work-scheduling authority;
- exact one-shot authorization/manifest/application-marker semantics;
- exact two-concurrent-slot / two-cycle / up-to-four-distinct-token capacity semantics;
- the existing `WINDOW_15M -> hard-gated WINDOW_1H -> hard-gated WINDOW_4H -> stop` lifecycle;
- support-only `WINDOW_5M_MICRO_EVENT`;
- locked `WINDOW_12H` and `WINDOW_24H`;
- zero automatic retry, resume, restart, or successor;
- the authoritative DB's existing SQLite DELETE/FULL/normal semantics unless separately redesigned later.

## 4. Canonical owner map

Every portability requirement is assigned to the narrowest existing owner.

| Requirement | Canonical owner | Design disposition |
| --- | --- | --- |
| operational one-shot application boundary | `src/printer_v1/operator_cli/four_token_standard_four_hour_one_shot_wrapper.py` | Extend only this wrapper with a stable Linux-facing CLI/supervision surface; do not create another runner |
| shared create-once / directory durability primitives | `src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py` | Make directory durability fail closed and reusable by the four-token wrapper |
| child terminal publication | `src/printer_v1/operator_cli/window_15m_child_terminal.py` | Reuse the same durable publication primitive; preserve create-once sibling binding |
| operational child runtime | `src/printer_v1/operator_cli/operational_memory_factory_command.py` | Keep existing four-token mode and cancellation probe; no new campaign policy |
| persisted cooperative cancellation / cleanup | `src/printer_v1/operator_cli/campaign_supervision.py` | Reuse `request_campaign_cancellation` and canonical cleanup; no second stop engine |
| terminal reconciliation | `src/printer_v1/operator_cli/unified_terminal_closure.py` and existing terminal owners | Preserve current first-cause, zero-active-work, lease-release and no-restart rules |
| exact DB binding | `src/printer_v1/operator_cli/operational_database_target_binding.py` | Keep exact path/SHA/size/inode/mtime/migration binding; issue fresh remote auth only after final remote identity exists |
| zero-state process gate | `src/printer_v1/operator_cli/four_token_proof_zero_state_gate.py` plus current recovery process inventory | Preserve fail-closed process inventory; prove POSIX `ps` behavior on Linux |
| backup/restore safety | `src/printer_v1/operator_cli/operational_backup_restore_preflight.py` | Preserve quiescent sidecar, exact-copy, integrity/FK/migration rehearsal rules; add only portability checks proven necessary |
| runtime dependency boundary | `pyproject.toml` plus `unified_terminal_closure.assert_runtime_dependency_preflight` | Pin one tested Linux runtime set before proof; never copy the Mac venv |
| host/service policy | systemd deployment artifact owned by this portability slice | Supervise the wrapper only; no provider helper, scheduler helper, daemon, timer, watchdog, or auto restart |

## 5. Canonical Linux entrypoint

### 5.1 Product boundary

The Linux service must invoke the **four-token standard-four-hour one-shot wrapper**, never the child operational command directly.

The child already fails closed when wrapper provenance/marker bindings are absent. The remote design preserves that defense.

The implementation may expose a stable console entry such as a wrapper-owned CLI, but that CLI must do no independent discovery, source fetching, scheduling, campaign selection, continuation policy, or DB orchestration. Its only runtime job is to validate the one-shot application inputs, supervise the single child, and publish wrapper terminal truth.

### 5.2 Invocation contract

One service start corresponds to exactly one wrapper invocation and exactly one allowed child invocation.

The unit receives one run-specific authorization-artifact path through an external runtime configuration surface outside Git. The reusable unit must not hard-code an authorization ID or a consumed application path.

Manual service start is the operator action. No boot target, timer, cron, watchdog, or service dependency may start Printer automatically.

The wrapper remains foreground until the child has exited and the wrapper has validated/published terminal evidence, or until systemd's bounded emergency escalation is reached.

## 6. systemd service contract

The initial native Linux design uses a foreground service with:

- `Type=exec`;
- `Restart=no`;
- `RemainAfterExit=no`;
- no timer unit;
- no watchdog relaunch;
- no `WantedBy=` auto-enable path in the initial unit;
- one dedicated unprivileged service user and group;
- a stable durable `HOME` so existing `~/PrinterOperations/...` artifact semantics remain valid;
- a fixed `WorkingDirectory` at the final remote repository checkout;
- `UMask=0077`;
- stdout/stderr may go to journald, while child/wrapper terminal artifacts remain the authoritative terminal evidence;
- no secret or provider credential on the command line;
- no `ExecStartPre`/`ExecStopPost` helper that contacts providers, runs Scheduler work, mutates the DB, consumes authorization, retries a campaign, or performs orphan recovery.

`Type=exec` is intentionally separate from Printer's product-level "one-shot" meaning. The campaign is one-shot because the wrapper/authorization contract permits one bounded invocation, not because systemd uses `Type=oneshot`.

## 7. Signal and safe-stop contract

### 7.1 Existing safe-stop truth

The existing runtime already has a cooperative stop path:

1. supervision cancellation persists `STOPPING` / stop-request state;
2. the running campaign's cancellation probe observes that state;
3. new child work is blocked;
4. the main coordinator owns Scheduler cancellation, window/cycle terminalization, first-terminal-cause preservation, cleanup, zero-active-work verification, lease release, reporting, and child terminal publication.

The Linux design must use this path instead of terminating the child directly on the first stop request.

### 7.2 systemd signal behavior

The service design requires `KillMode=mixed` semantics:

- the initial stop signal is delivered to the wrapper main process only;
- the wrapper records the signal in process-local state; the signal handler itself performs no SQLite/file/network work;
- normal wrapper control flow requests the existing cooperative campaign cancellation exactly once after an exact active campaign supervision can be established;
- the child remains alive long enough to observe cancellation and run canonical terminal cleanup;
- the wrapper remains alive while waiting for the child terminal artifact;
- only after the bounded systemd stop grace expires may systemd forcibly kill remaining processes in the service cgroup.

The implementation must not use `KillMode=control-group` for the initial SIGTERM because that would signal the child at the same instant and could bypass cooperative cleanup.

### 7.3 Exact cancellation identity

The convenience `cooperative_stop()` path currently resolves the latest supervision row. The systemd implementation must not rely on a merely historical "latest" row.

A remote stop request may be issued only when the wrapper can prove one exact current active/STOPPING supervision belongs to the child invocation under the zero-state one-shot boundary. If that exact ownership cannot be proved, the wrapper fails closed and does not mutate another campaign's supervision.

The narrow implementation may expose an exact-active-supervision cancellation helper around the existing `request_campaign_cancellation` owner. It must not create a second cancellation model or change campaign policy.

### 7.4 Signal timing cases

- **Before application-marker consumption:** no child execution is authorized by that signal event; no automatic retry follows.
- **After marker consumption but before supervision exists:** authorization is already consumed. The wrapper may boundedly wait for the child to either publish terminal truth or establish the uniquely attributable supervision; it must never treat the authorization as reusable.
- **During pre-lifecycle or lifecycle work:** request existing cooperative cancellation once; child performs canonical terminalization.
- **After terminal evidence exists:** do not rewrite terminal truth and do not create a successor.
- **Repeated SIGTERM/SIGINT:** idempotent stop intent only; no repeated campaign creation/cancellation semantics.
- **Forced systemd escalation:** authorization remains consumed. No restart or automatic orphan recovery is allowed. Subsequent work is read-only terminal/orphan audit under a later explicit operator action.

The exact `TimeoutStopSec` must be a finite constant selected by the implementation and accepted only after bounded Linux proof demonstrates it exceeds the worst observed cooperative terminalization envelope with margin. No unbounded stop timeout is allowed.

## 8. Durable publication contract

### 8.1 Proven defect

The shared `_fsync_directory()` currently swallows directory-open and directory-fsync errors. File writers fsync their file descriptor, but selected create/replace boundaries do not yet prove durable parent-directory publication.

Remote operation must treat directory durability as a correctness condition, not best effort.

### 8.2 Required fail-closed primitive

The shared one-shot filesystem owner must provide a directory-sync primitive that:

- opens the exact parent directory without following an unexpected symlink;
- uses directory semantics supported by the approved Linux profile;
- calls `fsync` on the directory;
- raises a bounded explicit error on open/fsync failure;
- never converts an unconfirmed durability result into success.

### 8.3 Mandatory remote durability boundaries

Before a remote campaign may be authorized/proven, parent-directory durability must be established after at least:

1. creation of the per-application directory when newly created;
2. canonical provenance-manifest publication after atomic replace;
3. application-marker create-once publication;
4. child-terminal create-once publication;
5. wrapper-terminal create-once publication;
6. verified pre-campaign backup publication before campaign mutation.

Existing terminal-report/summary and lease-lock publishers must be included in the Linux proof audit. They are repaired only if bounded crash/durability review proves the existing owner does not meet the required publication contract; this design does not authorize a broad persistence refactor.

### 8.4 Consumption rule on durability failure

If the application-marker file was created but its parent-directory durability cannot be confirmed, the authorization is treated as **consumed with durability unconfirmed**. The marker must not be deleted to manufacture a retry. The run stops fail closed and requires operator review.

If child/wrapper terminal publication cannot be durably confirmed, the authorization remains consumed and no rerun is permitted. Missing terminal durability becomes an audit/recovery condition, not restart authority.

## 9. Positive local-filesystem preflight

### 9.1 Requirement

Rejecting only UNC/network-looking paths is not enough on Linux. Before application-marker consumption, remote preflight must positively establish that all authoritative write roots use the approved local filesystem profile.

The check covers at minimum:

- authoritative DB and DB parent;
- application/authorization marker root;
- operational artifact root;
- backup/restore/reports root when on a distinct mount.

### 9.2 Initial supported profile

The first remote proof profile is conservative: **local ext4 only**.

Any other filesystem type is blocked until a later bounded portability review proves its SQLite locking, atomic rename/link, file fsync and directory fsync behavior. This includes XFS until separately proven; support is not inferred merely because it is local.

NFS/NFS4, CIFS/SMB, SSHFS/FUSE remote filesystems, 9p, Ceph/Gluster-style network filesystems, and unknown/virtual filesystem types are blocked for authoritative DB/artifact roots.

### 9.3 Evidence source

On Linux, the preflight should resolve the actual mount owning each path from a kernel-provided mount view such as `/proc/self/mountinfo`, together with real-path/stat identity. `st_dev` alone is not sufficient evidence of filesystem type.

Unknown or unparsable mount evidence fails closed before marker consumption.

## 10. Linux runtime reproducibility

The Mac-created `.venv` must never be copied to Linux.

The future implementation/proof must create a fresh repo-local Linux `.venv` and record one exact tested runtime set including:

- Python 3.11 exact patch version;
- `sys.executable` and package resolution from the final checkout;
- SQLite library version;
- OpenSSL/runtime TLS version;
- exact installed `websockets` version satisfying the current contract;
- exact installed `certifi` version;
- Git version;
- procps/`ps` implementation and command behavior.

`pyproject.toml` version ranges remain source requirements, but a remote deployment is not reproducible until the implementation lane creates an exact install/verification record for the tested set.

No new paid dependency is permitted.

## 11. Linux process-inventory proof

The existing POSIX liveness inventory uses one bounded `ps -axo pid=,command=` call and fails closed on inspection failure.

The implementation must not replace it merely because the host changed. The bounded Linux proof must demonstrate:

- expected output parsing on the selected distro/procps version;
- wrapper and child identities are detected correctly;
- the wrapper's own PID/PPID exclusions remain correct;
- inability to run/parse `ps` blocks rather than silently passes;
- no process-killing or polling loop is introduced into the zero-state gate.

Only a failed bounded proof justifies a narrow code repair.

## 12. Service account, permissions and credentials

The remote host design requires:

- dedicated unprivileged service account/group;
- service-owned final checkout/runtime paths required for operation, with source/config areas not broadly writable at runtime;
- DB/artifact/application directories writable only as needed by the service account;
- `UMask=0077` and private operational artifacts by default;
- no shared Mac/VPS writable volume;
- provider credentials, if an already-approved free source needs them, supplied outside Git with restrictive permissions;
- no credentials in `ExecStart`, shell history, committed files, authorization manifest, application marker, or terminal artifact;
- no infrastructure change that makes an optional provider credential a new mandatory paid dependency.

A run-specific environment file may carry non-secret one-shot paths/identities. Secret-bearing values require a root/service-readable protected file or systemd credential mechanism and must not be logged.

## 13. Disk, evidence and log controls

Before marker consumption, preflight must establish enough durable local free space for:

- the current DB and its normal SQLite temporary/journal needs;
- one verified pre-campaign backup;
- one disposable restore rehearsal;
- the existing bounded campaign storage ceiling;
- terminal/report/log margin.

The implementation must derive the threshold from current DB size plus the existing storage ceiling rather than using raw row counts as a readiness signal. If the derived requirement cannot be met, execution blocks before marker consumption.

Journald is diagnostic only. Canonical wrapper/child/report artifacts remain the authoritative run evidence. Host log retention must be bounded and must not delete active/current campaign evidence needed by the current reconciliation contract.

## 14. Time synchronization

Remote authorization temporal-validity checks depend on a trustworthy clock.

Before a fresh remote authorization is prepared or applied:

- system time synchronization must be active;
- the clock must not be materially unsynchronized according to the selected host time service;
- failure to establish time-sync readiness blocks authorization preparation/application.

No time service is embedded inside Printer.

## 15. SQLite invariants

The initial remote profile preserves the accepted authoritative SQLite state:

- journal mode `DELETE`;
- synchronous `FULL`;
- locking mode `normal`;
- no WAL/SHM/journal sidecars at cutover transfer boundary;
- one authoritative writer host only.

Infrastructure work must not silently switch WAL mode, introduce a network filesystem, or create concurrent Mac/VPS writers.

The existing backup/restore preflight remains the owner of exact-copy, integrity, foreign-key and migration rehearsal behavior.

## 16. Sole-authoritative-host cutover design

Migration/cutover remains a later lane. Its required sequence is:

1. implementation and bounded Linux/systemd proof pass first;
2. operator explicitly approves migration/cutover;
3. stop and fence Mac authoritative Printer execution;
4. prove no in-flight campaign, no active operational ownership and no transient SQLite sidecars;
5. perform an offline copy of the authoritative DB plus the required reconciliation/provenance evidence;
6. verify remote SHA-256, size, SQLite integrity, foreign keys and migration ledger;
7. establish final remote repo checkout, runtime, service user/group, durable HOME, permissions, local ext4 mount identity and artifact paths;
8. prove Mac remains permanently fenced from authoritative writes;
9. capture the **final remote** DB path/SHA/size/inode/mtime and exact Git branch/HEAD;
10. only then prepare a fresh remote one-shot authorization against those exact identities;
11. independently review that authorization;
12. require a separate explicit operator start action.

Copying DB bytes does not transfer authorization. No current or historical Mac authorization becomes VPS authority.

## 17. Bounded Linux/systemd proof matrix

Implementation cannot close without minimum sufficient proof covering:

| Proof | Required result |
| --- | --- |
| fresh Linux venv/runtime | exact interpreter/package/dependency set resolves from final checkout |
| local filesystem positive check | approved ext4 roots pass; remote/unknown filesystem fixtures block pre-consumption |
| directory fsync success | manifest/marker/terminal/backup publication returns only after parent durability is confirmed |
| directory fsync fault injection | publication blocks; marker-created case remains consumed; no retry/restart |
| `ps` process inventory | wrapper/child detection and fail-closed parser behavior proven on Linux |
| systemd manual start | exactly one wrapper and one authorized child; no direct child launch |
| pre-marker SIGTERM | no campaign execution, no automatic retry |
| post-marker/pre-supervision SIGTERM | consumed authority remains consumed; no successor; bounded terminal handling |
| active pre-lifecycle SIGTERM | exactly one cooperative stop request; canonical cleanup; zero active work |
| active lifecycle SIGTERM | same safe-stop/lease-release/terminal-report contract |
| repeated signals | idempotent stop intent; no second campaign/retry/resume/restart |
| forced stop timeout | remaining cgroup processes die only after grace; service does not restart; authorization remains consumed; orphan recovery is not automatic |
| service failure/reboot | no automatic restart or boot relaunch |
| SQLite mode | DELETE/FULL/normal preserved; no unintended WAL |
| owner boundaries | no Source Governor/Central Scheduler bypass; no new source/scheduler loop |
| capability locks | no retrieval/financial/12h/24h activation; 5m remains support-only |

Proof uses disposable/frozen targets wherever mutation is required. No authoritative DB transfer or live campaign is part of the implementation proof unless a later explicit proof authorization says so.

## 18. Minimum future implementation scope

If the operator approves implementation, the first implementation slice is limited to the smallest files necessary to satisfy this design. Expected scope:

- `src/printer_v1/operator_cli/four_token_standard_four_hour_one_shot_wrapper.py`
  - stable wrapper-owned Linux CLI;
  - foreground systemd signal supervision;
  - exact active-supervision cooperative-stop bridge;
- `src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py`
  - fail-closed directory durability primitive and durable create/replace helper behavior;
- `src/printer_v1/operator_cli/window_15m_child_terminal.py`
  - durable parent publication for child terminal;
- one narrow local-filesystem preflight owner, preferably reused by wrapper/database preflight rather than duplicated;
- `pyproject.toml` only if a console entry is required;
- focused unit/fixture tests for these exact boundaries;
- a systemd unit/template artifact only as required by the approved implementation.

No business logic, discovery policy, selection policy, Source Governor adapter, Central Scheduler policy, DB schema/migration, window/capacity rule, authorization schema, retrieval path or financial path is in scope unless a bounded implementation proof exposes a specific blocker and a new design review approves it.

## 19. Implementation acceptance gates

A future implementation may advance to Linux proof only when:

1. the service entrypoint is the canonical four-token one-shot wrapper;
2. direct child launch remains fail closed;
3. first systemd stop signal cannot bypass cooperative cleanup;
4. exact active supervision is proven before external cancellation mutation;
5. directory durability errors fail closed;
6. positive ext4 preflight exists and rejects unknown/remote filesystems;
7. one exact Linux runtime set is recorded;
8. no auto-start/restart/timer/watchdog path exists;
9. no Source Governor/Central Scheduler bypass exists;
10. one-shot/capacity/window/financial locks are unchanged.

## 20. Stop conditions

Stop implementation/proof immediately if any proposed change:

- introduces a second factory runner, Scheduler, Source Governor or discovery loop;
- changes four-token capacity or timeframe policy;
- sends initial systemd SIGTERM directly to the child alongside the wrapper;
- treats a marker-created durability failure as reusable authorization;
- permits unknown/network filesystem use for authoritative SQLite;
- requires copying the Mac venv;
- silently switches SQLite to WAL;
- allows boot/timer/watchdog/automatic restart;
- performs migration/cutover before bounded Linux proof;
- creates a remote authorization before final remote DB/Git/filesystem identity;
- activates retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, 12h or 24h;
- uses dirty memory for retrieval or decisions.

## 21. Money-usefulness contribution

This infrastructure design does not claim profit and does not change trading behavior. Its value is reliability: a remote host can later collect the same bounded, auditable paper-only memory without Mac sleep dependence, while preserving one-shot authorization, evidence durability, safe stop, source/scheduler ownership and sole-writer DB truth.

That improves the reliability of future memory growth without converting infrastructure convenience into capability readiness.

## 22. Design closeout and next permitted action

Design verdict:

`REMOTE_HOST_NATIVE_LINUX_SYSTEMD_PORTABILITY_DESIGN_PASS__OPERATOR_REVIEW_NEXT`

The design is complete enough for an implementation-scope review. It does not authorize implementation by itself.

Exact next permitted action:

`REMOTE HOST DESIGN / SPECIFICATION — OPERATOR REVIEW / IMPLEMENTATION APPROVAL GATE`

Allowed next:

- review this design against the active authority stack;
- accept it, reject it, or narrow it;
- if accepted, explicitly authorize the bounded implementation slice described above.

Not allowed next without that explicit approval:

- code/test/systemd implementation;
- server provisioning;
- DB migration/transfer;
- authorization preparation/application;
- Printer execution;
- providers/RPC/WebSocket;
- Central Scheduler runtime;
- authoritative DB mutation;
- capability advancement.

All permanent V1 locks remain unchanged.