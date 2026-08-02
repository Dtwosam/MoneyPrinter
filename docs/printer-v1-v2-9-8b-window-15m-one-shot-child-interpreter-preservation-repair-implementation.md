# Printer V1 V2-9.8B WINDOW_15M One-Shot Child Interpreter Preservation Repair Implementation

Date: 2026-08-02

Lane:
`V2-9.8B WINDOW_15M One-Shot Child Interpreter Preservation Repair Implementation`

Lane type: implementation (test-driven).

## 1. Verdict

`V2_9_8B_WINDOW_15M_ONE_SHOT_CHILD_INTERPRETER_PRESERVATION_REPAIR_IMPLEMENTATION_PASS`

The canonical one-shot wrapper now preserves the lexical repository
virtual-environment interpreter entrypoint when constructing the operational
child command. It no longer replaces that entrypoint with the canonical target
of its symlink chain. Every authorization, Git-provenance, manifest, marker,
one-attempt, environment, and terminal-evidence boundary is unchanged.

## 2. Exact baseline

| Item | Value |
| --- | --- |
| Implementation branch | `agent/v2-9-8b-window-15m-one-shot-child-interpreter-preservation-repair-implementation` |
| Required / actual starting HEAD | `0a8f98920aa5b0966569f567f4cda3c14616a4e8` |
| Design followed | `docs/printer-v1-v2-9-8b-window-15m-one-shot-child-interpreter-preservation-repair-design.md` |
| Design verdict | `V2_9_8B_WINDOW_15M_ONE_SHOT_CHILD_INTERPRETER_PRESERVATION_REPAIR_DESIGN_PASS` |
| Tracked worktree at start | clean |
| Untracked `operator-runs/` evidence | preserved unchanged |
| Consumed authorization (still consumed) | `V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z` |

## 3. Files changed

Exactly the allowed set:

- `src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py`
- `tests/test_v2_9_8b_window_15m_one_shot_wrapper.py`
- `docs/printer-v1-v2-9-8b-window-15m-one-shot-child-interpreter-preservation-repair-implementation.md` (this report)

No launcher, validator, operational command, provider, Scheduler, database,
discovery, memory, retrieval, or trading code was modified. No new import was
added to the wrapper.

## 4. Failing-test evidence before implementation

Focused tests were added first and run against the unmodified wrapper. 14 new
tests were red; the pre-existing 28 tests stayed green (30 passing total because
`test_32` and `test_44` pass trivially against the old wrapper).

The decisive red proof is the lexical-preservation test. Against the old wrapper
`child_command[0]` was the dereferenced base target rather than the lexical
entrypoint:

```text
AssertionError: '.../T/tmp.../venv-base-python'
             != '.../T/tmp.../repo/.venv/bin/python'
```

`.../venv-base-python` is the resolved final target of
`.venv/bin/python -> python3 -> venv-base-python`. This reproduces the exact
historical defect (`Path(...).resolve()` following the venv symlink chain to the
external base interpreter). The `_select_child_python` unit and boundary tests
failed with `AttributeError` because the selector did not yet exist.

## 5. Repair contract implemented

Added one narrow wrapper-owned selector/validator,
`_select_child_python(*, repository_root, override)`, and replaced the previous
`str(Path(python_executable or (root / ".venv/bin/python")).resolve())`
construction with its lexical result. The selector:

- defaults to `sys.executable`; uses the internal `python_executable` override
  only as a test/proof injection boundary;
- normalizes with `os.path.expanduser` + `os.path.abspath` (no symlink
  following) and never uses `resolve()`/`realpath()` to produce
  `child_command[0]`;
- requires lexical containment under the canonical repository `.venv` and an
  immediate parent of exactly `.venv/bin` (POSIX) or `.venv/Scripts` (Windows);
- rejects symlinked `.venv`, `bin`, or `Scripts` ancestors and requires both to
  be real directories;
- requires `.venv/pyvenv.cfg` to exist as a regular, non-symlink file;
- allows the final entrypoint to be a regular file or a normal venv symlink;
- follows the entrypoint only to validate it reaches an existing regular
  executable, and applies the POSIX executable-permission check;
- rejects a directly supplied Homebrew/base interpreter (lexically outside
  `.venv`) before any staging, manifest, or marker artifact is created.

The selection runs immediately after the pre-existing canonical-directory guard
and before `staging_dir.mkdir(...)`, so every rejection is fail-closed with zero
consumption side effects.

## 6. Preserved boundaries

- exactly one `subprocess.Popen` call site (verified: count = 1);
- `shell=False` retained;
- child argument sequence unchanged
  (`-m printer_v1.operator_cli.operational_memory_factory_command run
  --operator-approved`);
- exact four binding variables and their sanitize-then-set behavior unchanged;
- parent-environment mapping immutability unchanged;
- manifest/marker schemas, pre-marker/full-validator agreement, create-once
  consumption, and terminal evidence unchanged;
- repository/authorization/manifest/marker/application-root/evidence path
  canonicalization unchanged (the only abandoned canonicalization is the
  executable entrypoint, as designed);
- zero retry / rerun / resume / restart / successor.

## 7. Staging behavior

For future applications only, after the atomic `os.replace` manifest publication
and directory fsync, the wrapper performs a best-effort non-recursive
`staging_dir.rmdir()`. `rmdir` removes only the now-empty future staging
directory; it refuses a non-empty directory, so no staging evidence is ever
recursively deleted. A residual directory is a benign efficiency residue that
never consumes an authorization, launches a second child, or overwrites the
first terminal cause. The historical incident staging directory lives under a
different application root and is never targeted. Tests prove both the
empty-removal and non-empty-preservation behaviors and that cleanup outcome
never creates a second child or alters one-attempt counters.

## 8. Focused test / proof results

- Focused wrapper file
  `tests/test_v2_9_8b_window_15m_one_shot_wrapper.py`: **44 passed, 0 skipped**.
- Nearest affected guard
  `tests/test_v2_9_8b_window_15m_git_provenance_authorization_manifest.py`:
  **48 passed**.
- Python compilation of both changed Python files: OK.

New focused coverage proves:

- a real venv symlink chain remains lexical in `child_command[0]` and the
  resolved base target is absent from the command and from the terminal
  `child_command`;
- a direct base-interpreter override blocks before marker creation with no
  staging/canonical artifact;
- missing / symlinked `pyvenv.cfg` blocks;
- symlinked `.venv` / `bin` / `Scripts` ancestor blocks;
- broken, non-regular, non-executable, or missing entrypoint blocks;
- the outside-`.venv` override blocks;
- future empty staging is removed; non-empty staging is not recursively deleted;
- no cleanup outcome creates a second child.

Real disposable subprocess proof (`test_44`, executed — not skipped) using the
repository `.venv/bin/python` (lexical, not its resolved target), a harmless
`-c` probe, `shell=False`, and a finite timeout, emits canonical JSON and
asserts:

- `sys.prefix != sys.base_prefix` (`is_venv` true);
- the venv prefix is the repository `.venv`;
- `importlib.util.find_spec("printer_v1")` is not `None`;
- `find_spec("printer_v1.operator_cli.operational_memory_factory_command")` is
  not `None`.

The probe imports/executes no operational command and creates no manifest,
marker, provider call, Scheduler runtime, campaign, SQLite connection, or
memory. `test_43` additionally proves the default (`override=None`) selection
returns the lexical repository `.venv` entrypoint (`sys.executable`), never its
resolved base target.

## 9. Money-usefulness contribution

The repair stops another scarce authorization from being spent before the
approved memory-factory module can even start. It restores a correct
virtual-environment bootstrap so the one-command path can reach its real
governed preflight in a later, separately authorized lane. It makes no claim
that a later run will find eligible tokens, obtain complete source evidence,
create clean memory, or produce profit.

## 10. What improved

- correct, deterministic lexical venv child-executable identity;
- test coverage at the real OS subprocess boundary;
- honest separation of bootstrap readiness from campaign readiness;
- future staging-directory efficiency without touching incident evidence;
- protection against repeating the exact consumed-authorization failure.

## 11. What remains locked

Unchanged from the design: no reuse of
`V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z`; no new readiness/authorization; no
new manifest/marker/wrapper application; no provider, Source Governor, or Central
Scheduler runtime; no discovery/campaign; no authoritative SQLite access or
mutation; no memory generation/retrieval; no paper decisions, positions, trade
events, or PnL; no `WINDOW_1H/4H/12H/24H`; no wallets, keys, real funds, live
execution, or paid APIs; no scoring/ranking/embeddings/vectors.
`WINDOW_5M_MICRO_EVENT` remains support-only. Printer remains Solana-only,
Solana-memecoin-only, and paper-only.

## 12. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Status after implementation |
| --- | --- |
| Lexical containment weaker than canonical containment | Mitigated: non-symlink `.venv`/`bin`/`Scripts` ancestors, regular non-symlink `pyvenv.cfg`, executable-type/permission checks, and a real disposable venv proof all enforced |
| `sys.executable` already outside `.venv` in a broken executor | Fails closed before marker; unit test `test_34`/`test_43` cover default and override |
| Unit doubles hiding OS venv behavior | Addressed by real subprocess proof `test_44` asserting `sys.prefix != sys.base_prefix` and module-spec discovery |
| Broad `.resolve()` removal weakening evidence security | Avoided: only the executable entrypoint abandons canonicalization; all evidence-path canonicalization retained |
| Second production child via a preflight probe | Avoided: exactly one `subprocess.Popen`; the probe lives only in tests |
| Staging cleanup erasing incident evidence | Avoided: future-only non-recursive `rmdir`; historical path never targeted |
| Repaired bytes cannot bind the consumed authorization | Requires fresh readiness and a new exact-HEAD authorization after closeout; consumed authorization stays consumed |
| Import success is not campaign success | Kept honest: no claim of memory creation |

## 13. Exact next lane

`V2-9.8B WINDOW_15M One-Shot Child Interpreter Preservation Repair Bounded Proof`

Stop after this implementation commit. Do not begin bounded proof, readiness,
authorization, or another `WINDOW_15M` command in this lane.
