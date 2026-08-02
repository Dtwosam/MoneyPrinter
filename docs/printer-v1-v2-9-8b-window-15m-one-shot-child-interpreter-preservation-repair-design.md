# Printer V1 V2-9.8B WINDOW_15M One-Shot Child Interpreter Preservation Repair Design

Date: 2026-08-02

Lane:
`V2-9.8B WINDOW_15M One-Shot Child Interpreter Preservation Repair Design`

Lane type: design/specification only.

## 1. Verdict

`V2_9_8B_WINDOW_15M_ONE_SHOT_CHILD_INTERPRETER_PRESERVATION_REPAIR_DESIGN_PASS`

The minimum safe repair is approved for later implementation.

The canonical one-shot wrapper must preserve the lexical repository virtual-
environment interpreter entrypoint when constructing the operational child
command. It must stop replacing that entrypoint with the canonical target of its
symlink chain.

The repair is deliberately narrow:

- change child-executable selection and validation inside the canonical wrapper;
- add focused regression and disposable bootstrap proof coverage;
- optionally remove only a newly emptied future staging directory with a
  non-recursive best-effort `rmdir`;
- preserve every manifest, marker, authorization, one-attempt, environment,
  terminal-evidence, Source Governor, Scheduler, memory, and financial lock.

This design does not implement the repair, run the wrapper, restore the consumed
authorization, authorize a new run, or generate a `WINDOW_15M` memory.

## 2. Controlling source stack

This design is governed by:

- `AGENTS.md`;
- `docs/printer-v1-clean-master-spec.md`;
- `docs/printer-v1-post-rc-build-order.md`;
- `docs/printer-v1-memory-factory-guide.md`;
- `docs/printer-v1-current-state-memory-growth-audit.md`;
- `docs/printer-v1-memory-growth-build-order-v2.md`;
- `docs/printer-v1-python-builder-guide.md`;
- `docs/printer-v1-v2-9-8b-window-15m-one-shot-application-failure-audit.md`.

`docs/printer-v1-memory-growth-build-order-v2.md` remains the active
memory-growth build order inside this source stack and is not the sole source of
truth.

The active V2 completion pattern remains:

```text
audit/readiness
-> design/specification
-> implementation
-> bounded proof/test
-> independent closeout
```

## 3. Exact baseline and proven failure

| Item | Value |
| --- | --- |
| Design branch | `agent/v2-9-8b-window-15m-one-shot-child-interpreter-preservation-repair-design` |
| Starting HEAD | `8dced9286a6a6a7a3bb882d4cfcab332ba35851e` |
| Failure-audit verdict | `V2_9_8B_WINDOW_15M_ONE_SHOT_APPLICATION_FAILURE_AUDIT_PASS` |
| Consumed authorization | `V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z` |
| Reusable | `false` |
| Child attempts | `1` |
| Child exit code | `1` |
| Retry/rerun/resume/restart/successor | all `0` |
| Protected Printer runtime starts | `0` |

The failed wrapper command contained:

```text
/opt/homebrew/Cellar/python@3.12/3.12.13_4/Frameworks/Python.framework/Versions/3.12/bin/python3.12
```

The approved launcher had entered through:

```text
<repository>/.venv/bin/python
```

The wrapper changed the child identity by applying:

```python
str(Path(python_executable or (root / ".venv/bin/python")).resolve())
```

`Path.resolve()` followed the normal POSIX venv symlink chain to the Homebrew
base executable. The child therefore did not discover the repository
`.venv/pyvenv.cfg` or the venv-only editable `src` path and failed before the
Printer operational module imported.

## 4. Exact defect boundary

The defect boundary is only the canonical wrapper's construction of
`child_command[0]`.

Current owner:

`src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py`

The evidence does not justify changing:

- the PowerShell launcher's selection of the repository venv;
- the authorization document schema;
- the manifest or marker schemas;
- Git-provenance validation;
- the operational command;
- Source Governor;
- Central Scheduler;
- provider adapters;
- discovery, lifecycle, memory, retrieval, or paper-trading owners;
- authoritative database code.

Canonicalization remains required for repository, authorization, manifest,
marker, application-root, and evidence paths. The repair must not generalize
"do not resolve paths" beyond the executable entrypoint whose lexical location
carries virtual-environment identity.

## 5. Selected executable contract

Implementation must add one narrow wrapper-owned selector/validator, named
descriptively such as:

```python
_select_child_python(...)
```

The helper may use a different final name, but it must enforce the following
contract.

### 5.1 Selection

1. Canonicalize the repository root exactly as today.
2. Define the approved lexical venv root as `<canonical-root>/.venv`.
3. When no internal override is supplied, select the running wrapper
   interpreter from `sys.executable`.
4. When the existing internal `python_executable` override is supplied, use it
   only as a test/proof injection boundary.
5. Convert the selected value to an absolute normalized lexical path with
   `expanduser` plus `abspath` or an equivalent operation that removes relative
   components without following symlinks.
6. Never call `Path.resolve()`, `os.path.realpath()`, or an equivalent
   symlink-dereferencing operation to produce the executable value placed in the
   child command.
7. Return/store the lexical absolute path as `child_command[0]`.

Using `sys.executable` follows the active Python Builder Guide's rule to use the
current interpreter when launching the same Python environment. Official Python
venv behavior permits the environment's executable to be a symlink, and venv
identity depends on the environment entrypoint and nearby `pyvenv.cfg`.

### 5.2 Lexical boundary validation

The selected lexical path must fail closed unless all are true:

- it is absolute after non-dereferencing normalization;
- it is lexically contained under `<repository>/.venv`;
- its immediate executable directory is exactly `.venv/bin` on POSIX or
  `.venv/Scripts` on Windows;
- no component from the repository root through the executable's parent is a
  symlink;
- `.venv/pyvenv.cfg` exists, is a regular file, and is not a symlink;
- the final entrypoint itself is either a regular file or a symlink;
- following the final entrypoint only for validation reaches an existing
  regular file;
- the lexical entrypoint is executable under the current platform contract.

A normal POSIX venv is allowed to have:

```text
.venv/bin/python -> python3.x -> external base interpreter
```

The canonical target may therefore live outside `.venv`. That target is
validation evidence only. It must never replace the lexical entrypoint in
`child_command`.

### 5.3 Explicit rejection rules

Fail before marker creation when:

- `sys.executable` is empty or outside the repository venv;
- an override points directly to the base interpreter;
- the candidate uses `..`, an aliased parent, or a symlinked `.venv`/`bin`/
  `Scripts` ancestor;
- `pyvenv.cfg` is absent, a symlink, or non-regular;
- the entrypoint is missing, a directory, FIFO, socket, or other non-executable
  object;
- the final symlink target is missing or non-regular;
- platform executable permission/availability checks fail.

The error must identify a child-interpreter validation blocker without printing
secrets or environment contents.

## 6. Process-launch contract preserved

The production wrapper must still:

- own one and only one child launch;
- use an argument sequence;
- use `shell=False`;
- set `cwd` to the canonical repository root;
- sanitize and add the exact four manifest/marker binding variables;
- avoid mutating the parent environment mapping;
- write create-once stdout/stderr files;
- write immutable terminal evidence;
- record nonzero exit as terminal;
- create no retry, rerun, resume, restart, or successor.

The repair must not add a production preflight/import subprocess. The real
import-only probe belongs only to focused tests, bounded proof, and later
readiness. This preserves the one-wrapper/one-child law.

The existing `child_command` terminal field remains sufficient and should record
the lexical venv path. No terminal schema change is required.

## 7. Empty staging-directory contract

The consumed historical application and its empty staging directory are
immutable incident evidence and must not be changed or deleted.

For future applications only:

1. retain the current staging-manifest write and atomic `os.replace`;
2. after the manifest is published and directory state is synchronized, attempt
   a non-recursive `staging_dir.rmdir()` only when the directory is empty;
3. never use recursive deletion;
4. never delete a staging directory containing a file;
5. failure to remove an empty directory is a non-fatal efficiency residue and
   must not consume another authorization, create a second child, or overwrite
   the first terminal cause.

The implementation tests must prove that no staging evidence file is lost and
that historical application paths are never targeted.

## 8. Files allowed in implementation

Later implementation may change only:

- `src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py`;
- `tests/test_v2_9_8b_window_15m_one_shot_wrapper.py`;
- one implementation report for the approved implementation lane.

A separate bounded-proof report and independent closeout report may be added in
their own later lanes.

Not permitted without a new design finding:

- `scripts/Start-PrinterV1-Window15M-OneShot.ps1`;
- `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py`;
- `src/printer_v1/operator_cli/operational_memory_factory_command.py`;
- database migrations or schemas;
- provider, Scheduler, discovery, memory, retrieval, or paper-trading code.

## 9. Focused implementation tests

The implementation lane must add the minimum focused coverage below while
preserving all existing wrapper tests.

### 9.1 Lexical venv preservation

Create a disposable repository venv-style layout with a real symlink chain:

```text
repo/.venv/bin/python -> python3.x -> disposable executable target
```

Use the existing injected process launcher and assert:

- exactly one launch call;
- `command[0]` equals the lexical absolute
  `repo/.venv/bin/python` path;
- `command[0]` is not the canonical target;
- the rest of the operational command is unchanged;
- `cwd`, `env`, stdout/stderr ownership, and `shell=False` contract remain
  unchanged.

### 9.2 Base-interpreter substitution rejection

Pass the resolved target directly through `python_executable`.

The wrapper must block before manifest publication/marker creation because the
path is lexically outside `<repository>/.venv`.

### 9.3 Boundary and file-type rejection

Focused cases must cover:

- missing `pyvenv.cfg`;
- symlinked `.venv` or executable-parent directory;
- missing/broken executable;
- non-regular final target;
- non-executable lexical entrypoint where the platform supports the check.

### 9.4 Existing one-shot laws

Nearest affected tests must continue proving:

- one child only;
- create-once marker and terminal;
- pre-marker and full-validator agreement;
- wrong authorization hash blocks before marker;
- dirty tracked tree and extra current file block;
- nonzero child is terminal with zero retry;
- start failure consumes without successor;
- exact four binding variables;
- parent environment unchanged;
- direct operational command without bindings remains blocked;
- network and authoritative SQLite remain unused in wrapper tests.

### 9.5 Staging cleanup

Focused tests must prove:

- a successfully published future staging directory is removed only when empty;
- a non-empty staging directory is not recursively deleted;
- cleanup failure does not launch a second child or change one-attempt counters.

## 10. Real disposable bootstrap proof

The bounded proof lane must include one real subprocess boundary in addition to
unit tests.

It must:

1. use the lexical repository `.venv` executable, not its resolved target;
2. run a harmless `-c` probe outside the production wrapper;
3. emit a small canonical JSON object containing:
   - `sys.executable`;
   - `sys.prefix`;
   - `sys.base_prefix`;
   - whether `sys.prefix != sys.base_prefix`;
   - whether `importlib.util.find_spec("printer_v1")` is non-null;
   - whether
     `importlib.util.find_spec("printer_v1.operator_cli.operational_memory_factory_command")`
     is non-null;
4. assert the venv prefix is the repository `.venv`;
5. assert the operational module specification is discoverable without
   importing or executing the operational command;
6. use a finite timeout and `shell=False`;
7. create no manifest, marker, authorization, campaign, database, memory, or
   provider artifact.

A second proof assertion must inspect the repaired wrapper command through the
disposable injected launcher and show its executable string matches the lexical
venv entrypoint byte-for-byte.

## 11. Minimum verification sequence

Implementation verification must remain risk-based:

1. compile the changed wrapper and focused test module;
2. run only the changed/nearest wrapper tests first;
3. run directly affected Git-provenance/operational-command guard tests if not
   already contained in the focused file;
4. run the real disposable import-spec probe once;
5. perform static checks:
   - exactly one `subprocess.Popen` call site in the wrapper;
   - `shell=False` remains present;
   - no `.resolve()`/`realpath()` is used to construct `child_command[0]`;
   - no new provider, Scheduler, SQLite, memory, retrieval, or financial import;
6. run `git diff --check` and exact scope review.

No broad suite, provider smoke test, authoritative wrapper application, or live
campaign belongs in the implementation or bounded bootstrap-proof lanes.

## 12. Implementation acceptance criteria

Implementation may receive PASS only when all are true:

- lexical venv executable identity is preserved in `child_command[0]`;
- direct base-interpreter substitution is rejected;
- venv boundary and file-type checks fail closed before marker creation;
- a real subprocess proves venv prefix and module-spec discovery;
- exactly one wrapper child-launch call site remains;
- `shell=False`, exact environment binding, and parent-environment immutability
  remain;
- existing manifest/marker validation and one-attempt consumption tests pass;
- no historical evidence is modified;
- no source/provider, Scheduler, campaign, SQLite, memory, retrieval, or
  financial capability runs;
- implementation scope stays within the allowed files.

Stop and return BLOCKED if preserving lexical identity requires weakening any
authorization, Git, manifest, marker, evidence, or capability boundary.

## 13. Money-usefulness contribution

The repair prevents another scarce authorization from being spent before the
approved memory-factory module can even start.

That improves paper-only learning efficiency by making the one-command path
capable of reaching its real governed preflight and, in a later separately
authorized lane, the natural `WINDOW_15M` observation boundary.

It does not claim that a later run will find eligible tokens, obtain complete
source evidence, create clean memory, or produce profit.

## 14. What the repair improves

The later repair will improve:

- correct virtual-environment bootstrap;
- deterministic child executable identity;
- test coverage at the real OS subprocess boundary;
- honest distinction between bootstrap readiness and campaign readiness;
- staging-directory efficiency for future applications;
- protection against repeating the exact consumed-authorization failure.

## 15. What remains locked

A repair PASS still does not unlock:

- reuse of `V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z`;
- a new readiness decision or authorization;
- a new manifest, marker, or wrapper application;
- provider/source access;
- Source Governor or Central Scheduler runtime;
- discovery or campaign execution;
- authoritative SQLite access or mutation;
- memory generation or retrieval;
- paper decisions or BUY/SELL/HOLD;
- positions, trade events, paper audits, or PnL;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, or `WINDOW_24H`;
- wallets, private keys, real funds, live execution, paid APIs;
- scoring, ranking, confidence, weighted logic, embeddings, or vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only. Printer remains Solana-only,
Solana memecoin-only, and paper-only.

After implementation, bounded proof and independent closeout must pass before
fresh readiness, a new exact-HEAD authorization, independent authorization
review, and one later ordinary `WINDOW_15M` attempt.

## 16. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Why it matters | Required mitigation | Proof / stop condition |
| --- | --- | --- | --- |
| Lexical containment without canonical target containment appears weaker | Normal POSIX venv targets are outside `.venv` | Trust the lexical venv boundary, non-symlink ancestors, `pyvenv.cfg`, executable type, and real disposable venv proof; use canonical target only for validation | Stop if candidate can enter through a symlinked ancestor or outside lexical `.venv` |
| `sys.executable` may already be outside `.venv` in a broken executor | Repeating the failure would consume authorization | Fail before marker and require a correctly launched wrapper | Stop when default interpreter is outside `.venv` |
| Unit doubles may hide OS venv behavior | Previous tests missed the real defect | Require one real disposable subprocess import-spec proof | Stop if `sys.prefix == sys.base_prefix` or module spec is absent |
| Broad removal of `.resolve()` could weaken evidence security | Canonical evidence paths are a security boundary | Limit change to executable selection only | Stop if repository/evidence path canonicalization changes |
| Adding a pre-marker probe would create a second production child | Violates one-child law | Probe only in tests/proof/readiness | Stop if production wrapper launches more than one process |
| Staging cleanup could erase incident evidence | Application artifacts must remain immutable | Non-recursive future-only `rmdir` after successful move; never touch historical paths | Stop if recursive deletion or historical path targeting appears |
| Repair changes wrapper bytes and exact HEAD | Existing authorization cannot bind repaired code | Require fresh readiness and a new authorization after closeout | Stop any attempt to reuse the consumed authorization |
| Bootstrap repair may expose a later independent operational blocker | Import success is not campaign success | Keep outcomes honest and close each later blocker separately | No claim of memory creation until a later terminal report proves it |

## 17. Roadmap decision

| Decision | Result |
| --- | --- |
| Failure audit accepted | `true` |
| Repair design PASS | `true` |
| Selected repair is wrapper-local | `true` |
| PowerShell launcher change approved | `false` |
| Validator or operational-command change approved | `false` |
| Implementation approved as the next lane | `true` |
| Implementation completed | `false` |
| New readiness or authorization approved | `false` |
| Wrapper rerun or campaign approved | `false` |

## 18. Exact next lane

`V2-9.8B WINDOW_15M One-Shot Child Interpreter Preservation Repair Implementation`

Stop after this design commit. Do not implement the repair in this lane.
