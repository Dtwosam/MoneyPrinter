# Printer V1 V2-9.8B WINDOW_15M One-Shot Application Failure Audit

Date: 2026-08-02

Lane:
`V2-9.8B WINDOW_15M One-Shot Application Failure Audit`

Lane type: independent audit only.

## 1. Verdict

`V2_9_8B_WINDOW_15M_ONE_SHOT_APPLICATION_FAILURE_AUDIT_PASS`

The one-shot wrapper application is preserved and internally consistent. It
consumed exactly one authorization, attempted exactly one child launch, and
recorded child exit code `1` with no retry, rerun, resume, restart, or
successor.

The exact failure is independently verified:

```text
/opt/homebrew/opt/python@3.12/bin/python3.12: Error while finding module specification for 'printer_v1.operator_cli.operational_memory_factory_command' (ModuleNotFoundError: No module named 'printer_v1')
```

The root cause is a committed wrapper defect. The wrapper applies
`Path.resolve()` to the intended `.venv/bin/python` child entrypoint. On this
repository, that entrypoint is a symlink chain whose resolved target is the
Homebrew base interpreter. Executing the resolved target discards the lexical
virtual-environment entrypoint needed to discover `.venv/pyvenv.cfg` and the
venv-only editable `src` path. Printer V1's operational module therefore never
imported.

No provider/source, Source Governor, Central Scheduler, campaign, database,
memory, retrieval, decision, position, trade, audit, or PnL runtime began.

This PASS audits the failure truthfully. It does not make the failed application
successful, restore the consumed authorization, implement a repair, authorize
another application, or issue readiness.

## 2. Audit baseline and scope

| Item | Value |
| --- | --- |
| Audit branch | `agent/v2-9-8b-window-15m-one-shot-application-failure-audit` |
| Starting HEAD | `9c785ffe4222ff9adc24fd663d9a4daecc7f9965` |
| Required starting commit | `9c785ffe4222ff9adc24fd663d9a4daecc7f9965` |
| Starting tracked worktree/index | clean |
| Preserved current migration root | `operator-runs/v2-9-8b-authoritative-mig050/` |
| Preserved current authorization root | `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z/` |
| Audit method | read-only filesystem, Git, JSON, hash, size, mode, symlink, and timestamp inspection |

No wrapper, operational command, test suite, provider, Scheduler, campaign, or
SQLite command was run. The authoritative database and the retained SQLite
evidence files were hashed as regular files and were not opened through SQLite.

## 3. Exact application identity

| Field | Value |
| --- | --- |
| Authorization ID | `V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z` |
| Application directory | `/Users/Dtwo1/PrinterOperations/v2-9-8/window-15m-one-shot-applications/V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z` |
| Wrapper execution ID | `V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z` |
| Wrapper schema | `PRINTER_V1_WINDOW_15M_ONE_SHOT_WRAPPER_V1` |
| Manifest schema | `PRINTER_V1_GIT_PROVENANCE_MANIFEST_V1` |
| Marker schema | `PRINTER_V1_APPLICATION_MARKER_V1` |
| Application artifact count | `5` |
| Additional file inside application directory | none |

All five application artifacts are regular, read-only `0444` files and remain
byte-exact:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `application-marker.json` | 881 | `c32d25577010e391ad103ec0f709955d3a13bd12b877ef7dddbee375d20e54ef` |
| `child-stderr.txt` | 204 | `1eb9c38e1513b3dd8e7861f5674cf09cbed2d340b0059f54c56edb6eca651dc1` |
| `child-stdout.txt` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `git-provenance-manifest.json` | 4769 | `8c8ff8916f260349de0d5ee2b3d8440bbfbf7c1dd1ad82ead0f94fe6df6e7ddb` |
| `wrapper-terminal.json` | 1774 | `ff3370d2890b3b95ac640f4e3b543009893de4dd8ddc6569d2b34ceac82f7a17` |

One authorization-specific staging directory also remains at:

```text
/Users/Dtwo1/PrinterOperations/v2-9-8/window-15m-one-shot-applications/.staging/V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z-8c6effa328cd4a6fa05b5e2e016a273d
```

It is an empty directory with zero entries. It is not a second application,
manifest, marker, terminal, or child-attempt artifact. It was preserved and not
removed by this audit.

## 4. Authorization, manifest, marker, Git, and migration binding

| Binding | Verified value |
| --- | --- |
| Authorization file | `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z/final_authorization.json` |
| Authorization bytes | 8019 |
| Authorization mode | read-only `0444` |
| Authorization SHA-256 | `af63b05423c4baa7f577cc18b252ab96a2c4cd0200d534375164887727d55c60` |
| Authorized branch | `agent/v2-9-8b-window-15m-fresh-exact-head-final-authorization` |
| Authorized HEAD | `00f827c8c6c179534ab4e26e710c359e6d0ada22` |
| Authorized command | ordinary `run`, operator-approved |
| Allowed invocation count | `1` |
| Migration execution ID | `V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f` |
| Manifest SHA-256 | `8c8ff8916f260349de0d5ee2b3d8440bbfbf7c1dd1ad82ead0f94fe6df6e7ddb` |
| Manifest file records | `13` (`12` migration plus `1` authorization) |
| Allowed-file-set SHA-256 | `dfbe833853eeb3c00c9cdc964d2df68da585685a5fdf5264bb8d60afa8b4bd7f` |
| Marker authorization SHA-256 | `af63b05423c4baa7f577cc18b252ab96a2c4cd0200d534375164887727d55c60` |
| Marker manifest SHA-256 | `8c8ff8916f260349de0d5ee2b3d8440bbfbf7c1dd1ad82ead0f94fe6df6e7ddb` |
| Marker allowed-file-set SHA-256 | `dfbe833853eeb3c00c9cdc964d2df68da585685a5fdf5264bb8d60afa8b4bd7f` |
| Marker branch/HEAD | exact authorized branch/HEAD |

Every one of the manifest's 13 repository file records matches the current
regular file's size and SHA-256. The authorization, manifest, marker, wrapper
terminal, authorized branch, authorized HEAD, and Migration-050 identity form
one consistent binding chain.

The accepted launch-chain files also remain exact:

| File | SHA-256 |
| --- | --- |
| `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py` | `e899ecc14b62b3b46e6344ee2e3358ec5a09b6c523bdcbc821a8d3a70d9854c1` |
| `src/printer_v1/operator_cli/operational_memory_factory_command.py` | `16c8bb80569a870c21a13cc9f3a7ba724042dbb5fbab86f8ca080293b4c6587b` |
| `src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py` | `77e35c14860e3aae02f570e18773a8c7edb2f76e71d3772adb0ec58ef57d37c6` |
| `scripts/Start-PrinterV1-Window15M-OneShot.ps1` | `524c6332d0952b3959a8136140bc9e1a98acd54f486d88d70910dd537a496d4f` |
| `tests/test_v2_9_8b_window_15m_one_shot_wrapper.py` | `87a1b970ac6dac4bee8b43cc392b5c4e54feb1f06e606b1cc34c1ea29699780b` |

## 5. Authorization consumption and non-reuse

| Field | Result |
| --- | --- |
| Marker created | `true` |
| Consumed at | `2026-08-02T11:34:17.389120+00:00` |
| Allowed invocation count | `1` |
| One child start attempted | `true` |
| Authorization consumed by failed attempt | `true` |
| Reusable | `false` |
| Retry/rerun/resume/restart/successor allowed | all `false` |

Consumption occurred when the create-once marker was written, before the child
launch. The authorization's honest terminal law explicitly states that a
blocked attempt consumes the authorization. The canonical application directory
now exists, and the wrapper rejects an authorization whose canonical
application directory already exists. The authorization therefore cannot be
reused, resumed, restarted, rerun, or applied through a successor.

## 6. Exact child attempt and safety counters

The wrapper terminal records exactly this child command:

```text
/opt/homebrew/Cellar/python@3.12/3.12.13_4/Frameworks/Python.framework/Versions/3.12/bin/python3.12 -m printer_v1.operator_cli.operational_memory_factory_command run --operator-approved
```

| Counter / outcome | Verified value |
| --- | ---: |
| Child launch attempts | 1 |
| Child PID | 69314 |
| Child exit code | 1 |
| Child terminal classification | `CHILD_EXITED_NONZERO` |
| Child stdout bytes | 0 |
| Child stderr bytes | 204 |
| Automatic retries | 0 |
| Manual reruns | 0 |
| Resumes | 0 |
| Restarts | 0 |
| Successors | 0 |
| Parent environment mutations | 0 |
| Operational-module imports completed | 0 |
| Provider/source calls | 0 |
| Source Governor runtime starts | 0 |
| Central Scheduler runtime starts | 0 |
| Campaigns started | 0 |
| Authoritative DB opens or writes | 0 |
| Memory windows or memories generated | 0 |
| Retrieval operations | 0 |
| Decisions / BUY / SELL / HOLD | 0 |
| Positions / trade events / audits / PnL | 0 |

The zero operational counters are established at the earliest boundary: Python
failed while finding the requested module specification. It never imported the
operational module, so none of that module's top-level imports or runtime call
paths could execute. Empty stdout, the single exact stderr error, unchanged DB
identity, and absent sidecars independently agree with that boundary.

## 7. Verified root cause

Blocker classification:

`COMMITTED_CODE_DEFECT`

Evidence chain:

1. The PowerShell launcher constructs and invokes the lexical repository
   interpreter at `.venv/bin/python`.
2. `.venv/bin/python` exists and is a symlink to `python3.12`;
   `.venv/bin/python3.12` is a symlink to
   `/opt/homebrew/opt/python@3.12/bin/python3.12`.
3. The canonical filesystem target of that symlink chain is exactly:

   ```text
   /opt/homebrew/Cellar/python@3.12/3.12.13_4/Frameworks/Python.framework/Versions/3.12/bin/python3.12
   ```

4. The wrapper constructs the child executable with:

   ```python
   str(Path(python_executable or (root / ".venv/bin/python")).resolve())
   ```

5. The terminal artifact records the child executable as the same canonical
   Homebrew base-interpreter target, proving the `.resolve()` result was used.
6. `.venv/pyvenv.cfg` identifies the repository venv and its base executable.
   The venv has `include-system-site-packages = false`.
7. The project uses `src/printer_v1`; there is no repository-root
   `printer_v1` package.
8. The venv contains
   `.venv/lib/python3.12/site-packages/__editable__.printer_v1-0.0.0.pth`, whose
   only entry is `/Users/Dtwo1/Developer/MoneyPrinter/src`.
9. The resolved base interpreter did not activate the repository venv and did
   not load that venv-only editable path. Its exact error was
   `ModuleNotFoundError: No module named 'printer_v1'`.

The defect is not a missing interpreter, missing project package, provider
failure, source-contract outcome, or operator-path error. The wrapper itself
successfully imported through the lexical venv launcher; the identity was lost
only when the wrapper dereferenced the child executable before `Popen`.

The defect is also narrower than general path canonicalization. Canonicalizing
repository, authorization, manifest, marker, and application artifact paths is
part of the security boundary. The proven fault is specifically dereferencing
the executable entrypoint where the symlink's lexical location carries virtual-
environment activation identity.

## 8. Authoritative database state

| Field | Verified value |
| --- | --- |
| Path | `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3` |
| Type | regular file |
| Size | 65671168 |
| SHA-256 | `56ca1218442db1a571ba715794ba91b70c3bfeba242f21855275c026d4c8eed5` |
| `mtime_ns` | `1785617072867102156` |
| WAL | absent |
| SHM | absent |
| Journal | absent |

Size, SHA-256, and nanosecond modification timestamp exactly match the fresh
authorization binding and pre-application audit. No SQLite connection was used
to establish this result.

## 9. Retained Migration-050 evidence

Retained execution ID:

`V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f`

All twelve retained files remain regular, untracked current evidence with their
authorized sizes and SHA-256 values. The manifest independently enumerates the
same twelve identities and all twelve current files match it. The retained
package still establishes:

- Migration 050 invoked exactly once;
- migration count advanced from `49` to `50`;
- migration tip advanced from `049_candidate_acquisition_integration.sql` to
  `050_campaign_scheduler_ownership_scope.sql`;
- post-migration SHA-256 is
  `56ca1218442db1a571ba715794ba91b70c3bfeba242f21855275c026d4c8eed5`;
- integrity check was `ok` and foreign-key violation count was `0`;
- rollback was not entered;
- providers, RPC, WebSockets, Scheduler runtime, discovery, memory generation,
  retrieval, and financial runtime were not part of the migration application.

Migration 050 must not be invoked again.

## 10. Repository evidence namespace

| Set | Count |
| --- | ---: |
| Tracked historical `operator-runs/` files | 18 |
| Visible current files | 11 |
| Ignored current files | 2 |
| Current manifest evidence | 13 |
| Complete filesystem inventory | 31 |

Verified set relationships:

- complete inventory equals tracked history union current manifest evidence;
- tracked history and current evidence are disjoint;
- current evidence equals visible current union ignored current;
- no tracked file exists inside either current evidence package;
- no symlink or other non-regular file exists in the evidence namespace;
- tracked worktree and index remained clean during the audit;
- the only untracked status roots are the two explicitly preserved roots.

The external empty staging directory is outside the repository evidence
namespace and contains no evidence file.

## 11. Money-usefulness contribution

This audit prevents the failed attempt from being misclassified as provider,
eligibility, Scheduler, campaign, or memory behavior. That distinction protects
future paper-only learning efficiency: the next scarce authorization should not
be spent until the child can retain the approved interpreter environment and
reach the operational bootstrap boundary.

The audit creates no market evidence, memory, decision, trade, PnL, or profit
claim.

## 12. What this audit improves

- establishes the five exact immutable application artifact identities;
- proves one child launch and the exact nonzero terminal outcome;
- proves authorization consumption and permanent non-reuse;
- distinguishes a wrapper bootstrap defect from an operational or external
  outcome;
- identifies the exact identity-losing expression and the venv metadata it
  bypassed;
- confirms the operational module did not import and no protected runtime
  began;
- confirms the authoritative database and retained Migration-050 package did
  not drift;
- confirms the repository evidence namespace still reconciles exactly;
- defines a narrow repair and proof boundary without implementing it.

## 13. What remains locked

- any retry, rerun, resume, restart, or successor for this authorization;
- repair design and implementation beyond the next separately approved lane;
- a new manifest, marker, application, readiness decision, or authorization;
- provider/source access;
- Source Governor and Central Scheduler runtime;
- campaign execution;
- authoritative SQLite access or mutation;
- memory generation and retrieval;
- paper decisions and BUY/SELL/HOLD;
- positions, trade events, paper audits, and PnL;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, and `WINDOW_24H`;
- wallets, private keys, real funds, live execution, and paid APIs;
- scoring, ranking, confidence, weighting, embeddings, and vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only. Printer remains Solana-only,
Solana memecoin-only, and paper-only.

## 14. Minimum repair boundary and proof required

The minimum repair boundary is the canonical wrapper's child-executable
construction. The repair design must preserve virtual-environment entrypoint
identity while retaining all existing one-shot, exact-binding, environment
isolation, `shell=False`, create-once, no-retry, and terminal-evidence laws.

The evidence does not justify changes to the PowerShell launcher's venv choice,
the manifest/marker validator, the operational command, provider owners,
Scheduler owners, database code, campaign code, or capability locks.

Before any future authoritative application, the later approved implementation
and proof sequence must establish at minimum:

1. a focused regression test with a real symlinked venv-style executable proves
   command construction does not replace the lexical venv entrypoint with its
   base-interpreter target;
2. a real disposable subprocess proof, not only an injected process-launcher
   double, proves the child sees the intended venv identity and the repository
   editable `src` path;
3. a harmless disposable bootstrap probe proves the requested `printer_v1`
   module specification is discoverable without invoking the operational
   command, providers, Scheduler, campaign, or SQLite;
4. existing manifest/marker validation, one-attempt consumption,
   environment-binding isolation, nonzero child terminalization, and all five
   zero retry/rerun/resume/restart/successor counters remain covered;
5. the repair does not relax canonicalization of security-sensitive repository
   or evidence paths merely to preserve executable identity;
6. application/staging artifact behavior is specified, including the observed
   empty staging directory, without modifying historical evidence;
7. only focused static and disposable checks run; no broad suite or live
   operational proof is needed for the design lane;
8. after implementation, bounded disposable proof, and independent closeout,
   a fresh authoritative readiness audit and a fresh exact-HEAD authorization
   are required before any new ordinary attempt.

The consumed authorization and its manifest, marker, terminal, stdout, stderr,
or application directory may not be reused as proof of a repaired execution.

## 15. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Audit disposition |
| --- | --- |
| `.resolve()` conflates executable canonical target with venv entrypoint identity | Proven root cause; repair design must separate these concerns |
| Existing process-launcher-double tests can validate command shape without exercising OS venv detection | Minimum repair proof requires one real disposable subprocess boundary |
| Authorization was consumed before the child bootstrap failed | Correct one-shot law; authorization is permanently non-reusable |
| No operational behavior was exercised | Future application may reveal a later independent blocker after bootstrap is repaired |
| Repair changes wrapper bytes and exact HEAD | Fresh readiness, independent review, and fresh authorization are required later |
| Empty staging directory remains | Zero-file cleanup/efficiency residue; preserve now and specify behavior in repair design |
| Broad path-canonicalization weakening would damage evidence security | Repair must be executable-specific and retain evidence path validation |
| A successful import probe could be mistaken for campaign readiness | Prohibited; it proves bootstrap only |
| Retained Migration-050 evidence includes ignored SQLite files | Exact inventory includes and hashes both; do not open, delete, or omit them |

## 16. Roadmap decision

| Decision | Result |
| --- | --- |
| Failure evidence accepted | `true` |
| Audit PASS | `true` |
| Application successful | `false` |
| Authorization consumed | `true` |
| Authorization reusable | `false` |
| Wrapper defect proven | `true` |
| Repair implemented | `false` |
| New application authorized | `false` |
| Readiness issued | `false` |
| Campaign authorized | `false` |

## 17. Exact next lane

`V2-9.8B WINDOW_15M One-Shot Child Interpreter Preservation Repair Design`

Stop after this audit commit. Do not begin repair design in this lane.
