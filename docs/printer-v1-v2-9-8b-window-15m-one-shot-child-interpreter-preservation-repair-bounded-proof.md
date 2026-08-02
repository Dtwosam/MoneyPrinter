# Printer V1 V2-9.8B WINDOW_15M One-Shot Child Interpreter Preservation Repair Bounded Proof

Date: 2026-08-02

Linear tracking issue: `DTW-5`

Lane:
`V2-9.8B WINDOW_15M One-Shot Child Interpreter Preservation Repair Bounded Proof`

Lane type: disposable bootstrap/import proof only.

## 1. Verdict

`V2_9_8B_WINDOW_15M_ONE_SHOT_CHILD_INTERPRETER_PRESERVATION_REPAIR_BOUNDED_PROOF_PASS`

The repaired canonical wrapper preserves the lexical repository virtual-
environment interpreter in the child command, rejects unsafe interpreter
boundaries before marker creation, retains exactly one production child-launch
site with `shell=False`, and leaves all historical repository evidence,
external application evidence, and authoritative database bytes unchanged.

This proof did not run the production wrapper, create or apply an
authorization, import or execute the operational command, contact a provider,
start Source Governor or Central Scheduler, run a campaign, open SQLite,
generate memory, activate retrieval, or create a paper/financial artifact.

## 2. Exact baseline

The requested remote branch was fetched successfully and the local branch was
already checked out and up to date.

| Item | Exact value |
| --- | --- |
| Branch | `agent/v2-9-8b-window-15m-one-shot-child-interpreter-preservation-repair-bounded-proof` |
| Starting HEAD | `f0274db6d16749c50d7875d1ce9a8325012fd5b0` |
| Required HEAD | `f0274db6d16749c50d7875d1ce9a8325012fd5b0` |
| Remote branch HEAD after fetch | `f0274db6d16749c50d7875d1ce9a8325012fd5b0` |
| Tracked worktree | clean (`git diff --quiet` exit `0`) |
| Index | clean (`git diff --cached --quiet` exit `0`) |
| Untracked status | exactly the two retained `operator-runs/` roots below |
| Consumed authorization | `V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z`; historical and non-reusable |

Exact untracked roots:

- `operator-runs/v2-9-8b-authoritative-mig050/`
- `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z/`

No tracked or staged change existed before proof work.

## 3. Proof environment

| Item | Value |
| --- | --- |
| Proof completion timestamp | `2026-08-02T13:58:53Z` |
| Host | macOS `26.5` build `25F71`, `arm64` |
| Repository | `/Users/Dtwo1/Developer/MoneyPrinter` |
| Python | `3.12.13` |
| pytest | `9.1.1` |
| Lexical interpreter | `/Users/Dtwo1/Developer/MoneyPrinter/.venv/bin/python` |
| Resolved base target | `/opt/homebrew/Cellar/python@3.12/3.12.13_4/Frameworks/Python.framework/Versions/3.12/bin/python3.12` |
| `sys.prefix` | `/Users/Dtwo1/Developer/MoneyPrinter/.venv` |
| `sys.base_prefix` | `/opt/homebrew/opt/python@3.12/Frameworks/Python.framework/Versions/3.12` |
| Venv active | `true` |

The repository `.venv` and `.venv/bin` are real directories;
`.venv/pyvenv.cfg` is a regular file. The lexical entrypoint is the normal
symlink chain `.venv/bin/python -> python3.12 ->` the Homebrew base target.

## 4. Pre-proof evidence identities

All identities below were obtained with filesystem stat and SHA-256 file
hashing only. No SQLite connection or SQLite command was used.

### 4.1 Authoritative database

| Field | Pre-proof value |
| --- | --- |
| Path | `data/printer_v1.sqlite3` |
| Type / mode | regular file / `0644` |
| Size | `65671168` bytes |
| SHA-256 | `56ca1218442db1a571ba715794ba91b70c3bfeba242f21855275c026d4c8eed5` |
| `mtime_ns` | `1785617072867102156` |
| `printer_v1.sqlite3-journal` | absent |
| `printer_v1.sqlite3-wal` | absent |
| `printer_v1.sqlite3-shm` | absent |

### 4.2 Retained Migration-050 evidence root

Root:
`operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f`

File count: `12`. Symlinks: `0`. All files were regular mode `0644`.

| Relative file | Bytes | SHA-256 |
| --- | ---: | --- |
| `application_started.json` | 50133 | `8678ecb14feb1f04a315303ac5afd92639541900a267b8951adc7fad75050e8a` |
| `application_stderr.txt` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `application_stdout.txt` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `backup_restore_preflight.json` | 13836 | `569bea4e6d9aeacb6f612b4ec7ea85f43a73bfdc5cbde1693ecb8191aeb98083` |
| `closeout_inputs.json` | 2384 | `c10a76ba5729a2e4af42a9f3a4219571e0f959c2ba3d1214cfa1aa96a072e11f` |
| `disposable-restore/printer_v1-rehearsal.sqlite3` | 65654784 | `e13c40892f0c14d4c07960e00218569a536c50c0fc27815049284c3dd2aff5c2` |
| `final_authorization.json` | 6589 | `eb5388f3fac82b0c628a6b3e1e2893702fe221755838f971c6900f4e24e2b835` |
| `post_migration_proof.json` | 103903 | `fd7509280b2541eb3afa6010bdfdb44f6769219cd8a345224cfa26c6854f3c94` |
| `preauthorization_evidence.json` | 36274 | `4250b0e6a85bad41e50712ef21e5b11aab633c54e0246fc72aff037f7437119c` |
| `preflight.json` | 18590 | `3e3897da82a2012c1eb63aa8ea883a83a8c64fae49a86b2ff6192c8f82c88383` |
| `rollback_rehearsal.json` | 16244 | `997695a5aa4f4ffe6b8dd09970c93692d1a935491cf104b9a63a9c38440af149` |
| `verified-backup/printer_v1-pre050.sqlite3` | 65654784 | `e13c40892f0c14d4c07960e00218569a536c50c0fc27815049284c3dd2aff5c2` |

The SHA-256 of the sorted `shasum` identity listing was
`08e6f40b2e472d0bd8c6e8e1adaaac27a8b1af59d93571daa6cfb18f31dacb7a`.

### 4.3 Retained authorization evidence root

Root:
`operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z`

File count: `1`. Symlinks: `0`.

| Relative file | Bytes | Mode | SHA-256 |
| --- | ---: | ---: | --- |
| `final_authorization.json` | 8019 | `0444` | `af63b05423c4baa7f577cc18b252ab96a2c4cd0200d534375164887727d55c60` |

The SHA-256 of the sorted `shasum` identity listing was
`3bcfbfda544613822b76844f73e70fa1a54d6d790132180f53354f593d1c676d`.

### 4.4 Consumed external application evidence

Directory:
`/Users/Dtwo1/PrinterOperations/v2-9-8/window-15m-one-shot-applications/V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z`

File count: `5`. All files were regular, read-only mode `0444`.

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `application-marker.json` | 881 | `c32d25577010e391ad103ec0f709955d3a13bd12b877ef7dddbee375d20e54ef` |
| `child-stderr.txt` | 204 | `1eb9c38e1513b3dd8e7861f5674cf09cbed2d340b0059f54c56edb6eca651dc1` |
| `child-stdout.txt` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `git-provenance-manifest.json` | 4769 | `8c8ff8916f260349de0d5ee2b3d8440bbfbf7c1dd1ad82ead0f94fe6df6e7ddb` |
| `wrapper-terminal.json` | 1774 | `ff3370d2890b3b95ac640f4e3b543009893de4dd8ddc6569d2b34ceac82f7a17` |

The complete external application parent contained only that five-file
application plus the already-existing empty historical staging directory:

`/Users/Dtwo1/PrinterOperations/v2-9-8/window-15m-one-shot-applications/.staging/V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z-8c6effa328cd4a6fa05b5e2e016a273d`

The SHA-256 of the complete parent's sorted file-hash listing was
`f1a12143425ab418b14bbd0e60dfacd5268b99a13e6c637590160dbfe034f96f`.

## 5. Commands and exit results

### 5.1 Fetch, switch, and baseline

```text
git fetch origin agent/v2-9-8b-window-15m-one-shot-child-interpreter-preservation-repair-bounded-proof
git checkout agent/v2-9-8b-window-15m-one-shot-child-interpreter-preservation-repair-bounded-proof
git rev-parse HEAD
git rev-parse origin/agent/v2-9-8b-window-15m-one-shot-child-interpreter-preservation-repair-bounded-proof
git status --short --branch
```

Exit result: `0`. Local and remote HEAD were both the required
`f0274db6d16749c50d7875d1ce9a8325012fd5b0`. The tracked worktree and index
were clean and only the two expected evidence roots were untracked.

### 5.2 Compilation

The two required files were compiled with `py_compile.compile(...,
doraise=True)` into a temporary directory that was removed immediately:

```text
.venv/bin/python -c 'import py_compile, tempfile; t=tempfile.TemporaryDirectory(); py_compile.compile("src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py", cfile=t.name+"/window_15m_one_shot_wrapper.pyc", doraise=True); py_compile.compile("tests/test_v2_9_8b_window_15m_one_shot_wrapper.py", cfile=t.name+"/test_v2_9_8b_window_15m_one_shot_wrapper.pyc", doraise=True); t.cleanup(); print("COMPILE_OK: 2 files")'
```

Exit result: `0`; output: `COMPILE_OK: 2 files`.

### 5.3 Focused wrapper tests

```text
.venv/bin/python -m pytest \
  tests/test_v2_9_8b_window_15m_one_shot_wrapper.py \
  -q
```

Exit result: `0`; `44 passed in 2.65s`; no skip was reported.

### 5.4 Nearest provenance guard

```text
.venv/bin/python -m pytest \
  tests/test_v2_9_8b_window_15m_git_provenance_authorization_manifest.py \
  -q
```

Exit result: `0`; `48 passed in 2.74s`.

No broad or full suite was run.

## 6. Independent real subprocess probe

One independent parent Python process called `subprocess.run` with:

- command sequence `[/Users/Dtwo1/Developer/MoneyPrinter/.venv/bin/python,
  -c, <harmless probe>]`;
- `cwd=/Users/Dtwo1/Developer/MoneyPrinter`;
- `capture_output=True`, `text=True`;
- `timeout=30`;
- `shell=False`.

The child imported only `json`, `sys`, and `importlib.util`. It used
`find_spec`; it did not import or execute
`printer_v1.operator_cli.operational_memory_factory_command`.

Subprocess exit code: `0`.

Exact canonical JSON output:

```json
{"importlib.util.find_spec(\"printer_v1\") is not None":true,"importlib.util.find_spec(\"printer_v1.operator_cli.operational_memory_factory_command\") is not None":true,"sys.base_prefix":"/opt/homebrew/opt/python@3.12/Frameworks/Python.framework/Versions/3.12","sys.executable":"/Users/Dtwo1/Developer/MoneyPrinter/.venv/bin/python","sys.prefix":"/Users/Dtwo1/Developer/MoneyPrinter/.venv","sys.prefix != sys.base_prefix":true}
```

Assertions passed: the lexical path was used, the repository `.venv` was the
active prefix, prefix differed from base prefix, and both module specifications
were non-null.

## 7. Independent lexical-command proof

The existing `Fixture` and its injected `fake_launcher` were loaded from the
focused test module. The disposable fixture constructed a real symlink chain
and `apply_authorization_once` was called only against the fixture repository,
fixture evidence, and fixture application root. No real production child ran.

Exit result: `0`.

| Assertion | Result |
| --- | --- |
| Launch calls | exactly `1` |
| `child_command[0]` | lexical disposable `repo/.venv/bin/python` |
| Lexical path differs from resolved base target | `true` |
| Resolved base target anywhere in child command | `false` |
| Remaining arguments | exactly `-m printer_v1.operator_cli.operational_memory_factory_command run --operator-approved` |
| Terminal `child_command[0]` equals the lexical path | `true` |
| Automatic retries | `0` |
| Manual reruns | `0` |
| Resumes | `0` |
| Restarts | `0` |
| Successors | `0` |

The disposable paths were removed by the fixture after the proof.

## 8. Fail-closed boundary proof

All required negative cases ran on macOS and passed without skips inside the
44-test focused file:

| Required boundary | Focused evidence |
| --- | --- |
| Direct resolved/base-interpreter override | `test_30_direct_base_interpreter_blocks_before_marker` |
| Missing `pyvenv.cfg` | `test_35_missing_pyvenv_cfg_blocks` |
| Symlinked `pyvenv.cfg` | `test_36_symlinked_pyvenv_cfg_blocks` |
| Symlinked `.venv` | `test_37_symlinked_venv_directory_blocks` |
| Symlinked executable directory | `test_38_symlinked_executable_directory_blocks` |
| Broken entrypoint target | `test_39_broken_target_blocks` |
| Non-regular entrypoint target | `test_40_non_regular_target_blocks` |
| Non-executable entrypoint | `test_41_non_executable_entrypoint_blocks` |
| Missing entrypoint | `test_42_missing_entrypoint_blocks` |

`test_30` directly asserts zero launcher calls, no canonical application
directory, and no staging root for the base-interpreter substitution. Static
ordering independently confirms `_select_child_python` is called before the
first `staging_dir` construction/mkdir, before `canonical_dir.mkdir`, before
marker construction/write, and before `child_attempted` can become true.
Therefore every selector rejection above is a pre-marker failure with:

- staging artifacts: `0`;
- canonical applications: `0`;
- markers: `0`;
- child attempts: `0`.

## 9. Static safety inspection

AST and source inspection returned:

```json
{"forbidden_domain_imports":[],"production_popen_line":392,"production_popen_shell_false":true,"selector_resolve_or_realpath_call_lines":[],"subprocess_popen_calls":1}
```

Findings:

- exactly one `subprocess.Popen` call remains in the production wrapper;
- the production call explicitly retains `shell=False`;
- `child_python` is assigned from `_select_child_python`, and the first element
  of `child_command` is that `child_python` value;
- `_select_child_python` returns `str(lexical)` from `expanduser` plus
  `abspath`; no `resolve()` or `realpath()` call exists inside the selector;
- remaining `resolve()`/`realpath()` calls protect the repository,
  authorization path, application root, staged/published manifest path, marker
  path, child binding paths, and terminal evidence paths;
- imports are limited to Python standard-library modules and
  `git_provenance_authorization_manifest`;
- no provider, Source Governor runtime, Scheduler, SQLite, campaign, memory,
  retrieval, decision, position, trade, audit, PnL, or financial import was
  added;
- `git diff --check` exited `0`.

## 10. Staging proof

The same focused run proved the future-only disposable staging contract:

| Required behavior | Evidence / result |
| --- | --- |
| Empty staging removal | `test_31_future_empty_staging_is_removed` passed; production uses non-recursive `Path.rmdir()` only |
| Non-empty staging preservation | `test_32_non_empty_staging_is_not_recursively_deleted` passed; directory and residual file remained |
| Cleanup failure and attempts | the non-empty `rmdir` failure remained non-fatal; exactly one injected child and zero one-attempt successor counters |
| Recursive deletion | absent |
| Historical target | never used by a disposable fixture; the historical external parent was byte-identical pre/post proof |

The consumed external application's historical empty staging directory was not
removed or changed.

## 11. Post-proof reconciliation

Before creating this report, the complete pre-proof file identity listing and
the complete external/evidence tree listing were regenerated with the same
commands and compared byte-for-byte in memory.

| Reconciliation | Result |
| --- | --- |
| Full repository evidence and consumed-application identity listing | byte-equal pre/post |
| Complete external application-parent tree listing and file-hash listing | byte-equal pre/post |
| Migration evidence file count / identity digest | `12` / unchanged `08e6f40b...acb7a` |
| Authorization evidence file count / identity digest | `1` / unchanged `3bcfbfda...676d` |
| Consumed application file count / parent identity digest | `5` / unchanged `f1a12143...f96f` |
| Authoritative DB size | unchanged `65671168` |
| Authoritative DB SHA-256 | unchanged `56ca1218442db1a571ba715794ba91b70c3bfeba242f21855275c026d4c8eed5` |
| Authoritative DB `mtime_ns` | unchanged `1785617072867102156` |
| SQLite journal/WAL/SHM sidecars | absent before and after |
| Branch / HEAD | unchanged required branch / `f0274db6d16749c50d7875d1ce9a8325012fd5b0` |
| Tracked worktree / index before report | clean / clean |
| Untracked status before report | exactly the two retained evidence roots |

No new manifest, marker, authorization, readiness result, provider, Scheduler,
campaign, memory, retrieval, decision, position, trade, audit, or PnL artifact
was created. All proof fixtures were disposable and removed. This report is the
only intended repository change before commit.

## 12. Windows portability limitation

The Mac bounded proof does not establish universal Windows symlink-test
portability. Windows environments without symlink permission may fail during
disposable fixture setup. This does not invalidate the Mac repair proof, but it
remains an independent-closeout risk and is not hidden or repaired in this
proof lane.

## 13. Money-usefulness contribution

This proof shows that a future fresh one-shot authorization can retain the
approved repository venv identity through child bootstrap instead of being
consumed by the already-proven base-interpreter import failure. That protects a
scarce authorized attempt and lets a later separately approved run reach its
real governed preflight. It does not show that providers will succeed, eligible
tokens will exist, a `WINDOW_15M` will complete, clean memory will be created,
or profit will result.

## 14. What this proof improves

- independently confirms lexical child-interpreter preservation;
- confirms real venv prefix and repository module discovery at an OS subprocess
  boundary;
- confirms dangerous venv/path/file-type substitutions fail before
  authorization consumption;
- confirms one child, no retry/successor, and unchanged operational arguments;
- confirms future staging cleanup is non-recursive and evidence-preserving;
- confirms security-sensitive repository/evidence canonicalization remains;
- confirms historical evidence and authoritative DB identity did not drift.

## 15. What remains locked

- reuse, retry, rerun, resume, restart, or successor use of
  `V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z`;
- any new manifest, marker, readiness result, authorization, or application;
- the published PowerShell wrapper command;
- provider/source access;
- Source Governor and Central Scheduler runtime;
- discovery or campaign execution;
- authoritative SQLite access or mutation;
- memory generation or retrieval;
- paper decisions and BUY/SELL/HOLD;
- positions, trade events, paper audits, and PnL;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, and `WINDOW_24H`;
- wallets, private keys, real funds, live execution, paid APIs;
- scoring, ranking, confidence percentages, weighted logic, embeddings, and
  vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only. Printer remains Solana-only,
Solana-memecoin-only, and paper-only.

## 16. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Proof disposition |
| --- | --- |
| Mac proof does not establish universal Windows symlink fixture portability | Open independent-closeout risk; record honestly, do not repair here |
| Bootstrap/module-spec success could be mistaken for campaign readiness | Explicitly blocked; no operational command import or runtime occurred |
| Repair changes exact wrapper bytes and HEAD | Existing consumed authorization remains unusable; future work still needs independent closeout, fresh readiness, and fresh authorization |
| A later operational blocker may exist beyond import | Open; this proof establishes only child-interpreter/bootstrap correctness |
| Lexical containment relies on venv ancestor and metadata checks rather than base-target containment | Mitigated by non-symlink `.venv`/executable-directory checks, regular non-symlink `pyvenv.cfg`, target-type/executable checks, and real subprocess proof |
| Staging cleanup can fail | Non-fatal and bounded; non-empty evidence remains and no second child or counter change occurs |
| Historical staging residue remains | Preserved intentionally as consumed-application incident evidence |
| Full suite was not run | Intentional risk-based boundary; the required 44-test file and nearest 48-test guard both passed |

## 17. Roadmap verdict

| Decision | Result |
| --- | --- |
| Implementation baseline accepted | `true` |
| Compilation PASS | `true` |
| Focused tests PASS | `44 + 48` |
| Independent real subprocess PASS | `true` |
| Independent lexical-command PASS | `true` |
| Fail-closed boundary PASS | `true` |
| Static safety PASS | `true` |
| Staging behavior PASS | `true` |
| Historical evidence unchanged | `true` |
| Authoritative DB unchanged/unopened | `true` |
| Repair bounded proof PASS | `true` |
| Readiness or authorization issued | `false` |
| Wrapper/campaign execution authorized | `false` |

## 18. Exact next lane

`V2-9.8B WINDOW_15M One-Shot Child Interpreter Preservation Repair Independent Closeout`

Stop after this bounded-proof commit. Do not begin closeout, readiness,
authorization, or another `WINDOW_15M` command in this lane.
