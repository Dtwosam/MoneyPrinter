# Printer V1 V2-9.8B WINDOW_15M One-Shot Child Interpreter Preservation Repair Independent Closeout

Date: 2026-08-02

Linear tracking issue: `DTW-6`

Lane:
`V2-9.8B WINDOW_15M One-Shot Child Interpreter Preservation Repair Independent Closeout`

Lane type: independent documentation and reconciliation only.

## 1. Verdict

`V2_9_8B_WINDOW_15M_ONE_SHOT_CHILD_INTERPRETER_PRESERVATION_REPAIR_INDEPENDENT_CLOSEOUT_PASS`

The exact historical child-interpreter bootstrap defect is closed for the proven
macOS repository environment.

The audit, design, implementation, and bounded proof form one complete,
consistent, descendant commit chain. The implementation corrected the proven
cause without broadening scope or weakening authorization, Git provenance,
manifest, marker, evidence, one-shot, Source Governor, Central Scheduler,
memory, retrieval, or paper-financial locks. The bounded proof demonstrated the
repaired lexical virtual-environment bootstrap boundary without running the
production wrapper or any Printer campaign/runtime capability.

This PASS closes only the interpreter-preservation repair section. It does not
establish campaign readiness, authorize another application, restore or reuse
the consumed authorization, generate memory, activate retrieval, or unlock any
paper or financial capability.

## 2. Controlling source stack

This closeout is governed by the active Printer V1 source stack:

- `AGENTS.md`;
- `docs/printer-v1-clean-master-spec.md`;
- `docs/printer-v1-post-rc-build-order.md`;
- `docs/printer-v1-memory-factory-guide.md`;
- `docs/printer-v1-current-state-memory-growth-audit.md`;
- `docs/printer-v1-memory-growth-build-order-v2.md`;
- `docs/printer-v1-python-builder-guide.md`;
- the committed failure-audit, repair-design, implementation, and bounded-proof
  reports reviewed below.

`docs/printer-v1-memory-growth-build-order-v2.md` remains the active
memory-growth build order inside this source stack and is not the sole source of
truth.

The required completion pattern remains:

```text
audit/readiness
-> design/specification
-> implementation
-> bounded proof/test
-> independent closeout
```

After this closeout, the next permitted step is a fresh authoritative readiness
audit. Runtime and authorization do not follow directly from this PASS.

## 3. Exact closeout baseline and method

| Item | Exact value |
| --- | --- |
| Closeout branch | `agent/v2-9-8b-window-15m-one-shot-child-interpreter-preservation-repair-independent-closeout` |
| Required starting HEAD | `54547c4b5fb116b15c9d398aac9e3c31fde40be4` |
| Bounded-proof verdict | `V2_9_8B_WINDOW_15M_ONE_SHOT_CHILD_INTERPRETER_PRESERVATION_REPAIR_BOUNDED_PROOF_PASS` |
| Consumed authorization | `V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z` |
| Authorization reusable | `false` |
| Closeout method | committed-document review, remote Git descendant/diff review, static code/test reconciliation, and committed filesystem-identity reconciliation |
| Tests rerun in closeout | none |
| Production wrapper applications | `0` |
| Provider/Scheduler/campaign/SQLite/memory runtime | `0` |

No production or test code was modified in this closeout. No test rerun was
needed because no contradiction was found between the committed implementation,
bounded proof, and repository diffs. No provider, Source Governor, Central
Scheduler, campaign, SQLite, memory, retrieval, decision, position, trade,
audit, or PnL path was entered.

## 4. Exact commit-chain reconciliation

| Lane | Commit | Relationship | Authorized changed files |
| --- | --- | --- | --- |
| Failure audit | `8dced9286a6a6a7a3bb882d4cfcab332ba35851e` | audited the consumed one-shot failure | one failure-audit report |
| Repair design | `0a8f98920aa5b0966569f567f4cda3c14616a4e8` | exactly one commit after failure audit | one design report |
| Repair implementation | `f0274db6d16749c50d7875d1ce9a8325012fd5b0` | exactly one commit after design | wrapper, focused wrapper tests, one implementation report |
| Bounded proof | `54547c4b5fb116b15c9d398aac9e3c31fde40be4` | exactly one commit after implementation | one bounded-proof report |

Remote comparison verified:

- `0a8f98920aa5b0966569f567f4cda3c14616a4e8` is one commit ahead of
  `8dced9286a6a6a7a3bb882d4cfcab332ba35851e` and adds only the approved design
  report;
- `f0274db6d16749c50d7875d1ce9a8325012fd5b0` is one commit ahead of
  `0a8f98920aa5b0966569f567f4cda3c14616a4e8` and changes only the approved
  wrapper, focused test file, and implementation report;
- `54547c4b5fb116b15c9d398aac9e3c31fde40be4` is one commit ahead of
  `f0274db6d16749c50d7875d1ce9a8325012fd5b0` and adds only the approved bounded
  proof report.

No lane skipped its required predecessor. No unrelated production, provider,
Scheduler, database, discovery, memory, retrieval, or paper-trading file entered
the repair chain.

## 5. Historical failure resolution

The failure audit established all of the following:

- authorization `V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z` was consumed exactly
  once when its create-once application marker was written;
- exactly one child launch was attempted;
- the child exited with code `1`;
- the child failed while finding the module specification for
  `printer_v1.operator_cli.operational_memory_factory_command`;
- the exact stderr was a `ModuleNotFoundError` for `printer_v1`;
- the operational module did not import;
- providers, Source Governor, Central Scheduler, campaign, authoritative DB,
  memory, retrieval, decision, position, trade, audit, and PnL runtime did not
  begin;
- retries, reruns, resumes, restarts, and successors were all `0`;
- the consumed authorization cannot be reused, resumed, restarted, rerun, or
  rebound to repaired bytes.

The proven cause was limited to the wrapper constructing `child_command[0]` by
calling `Path.resolve()` on the intended lexical repository
`.venv/bin/python` entrypoint. On the macOS repository, that symlink chain
resolved to the Homebrew base interpreter. Launching the base target discarded
the virtual-environment identity required to discover `.venv/pyvenv.cfg` and
the venv-only editable `src` path.

The repair section resolves that exact cause. It does not rewrite history or
convert the consumed application into a successful application. Historical
terminal and evidence artifacts remain immutable failure evidence.

## 6. Design-to-implementation reconciliation

The selected design required one narrow wrapper-owned interpreter
selector/validator while preserving all unrelated canonicalization and one-shot
laws. The implementation conforms to that design:

- `_select_child_python(*, repository_root, override)` is the sole new
  interpreter-selection owner;
- `sys.executable` is the default interpreter source;
- the existing override remains an internal test/proof injection boundary;
- `expanduser` plus `abspath` produces an absolute normalized lexical path
  without following symlinks;
- `child_command[0]` receives that lexical venv entrypoint directly;
- the resolved base-interpreter target is used only for file validation and is
  never substituted into the child command;
- the interpreter must be lexically under the canonical repository `.venv`;
- its immediate parent must be `.venv/bin` on POSIX or `.venv/Scripts` on
  Windows;
- symlinked `.venv` or executable-directory ancestors are rejected;
- `.venv/pyvenv.cfg` must be a regular non-symlink file;
- the final entrypoint must be a regular file or normal venv symlink whose target
  reaches an existing regular executable;
- POSIX executable permission is checked;
- a direct base/Homebrew interpreter override blocks before staging, manifest,
  marker, or child-attempt creation.

The implementation also preserves:

- repository, authorization, manifest, marker, application-root, and evidence
  path canonicalization;
- one production `subprocess.Popen` call site;
- an argument sequence and `shell=False`;
- the unchanged operational command arguments;
- the exact four manifest/marker environment bindings;
- parent-environment immutability;
- create-once marker and terminal evidence;
- nonzero-child terminal behavior;
- zero retry, rerun, resume, restart, and successor paths;
- no production bootstrap/import probe.

Future staging cleanup is limited to best-effort non-recursive `rmdir` after
atomic manifest publication. It removes only a newly empty future staging
directory, refuses non-empty directories, and never targets the historical
incident staging directory.

## 7. Bounded-proof sufficiency

The bounded proof is sufficient for the exact historical bootstrap defect.

Committed proof results:

| Proof | Result |
| --- | --- |
| Python compilation | two required files compiled successfully |
| Focused wrapper tests | `44 passed in 2.65s` |
| Nearest Git-provenance guard | `48 passed in 2.74s` |
| Broad/full suite | not run, correctly |
| Independent subprocess | exit `0`, finite 30-second timeout, `shell=False` |
| Production wrapper launch | `0` |
| Disposable injected launches | exactly `1` |

The independent harmless subprocess used the lexical repository
`.venv/bin/python`, not its resolved Homebrew target, and proved:

- `sys.executable` was the lexical repository venv entrypoint;
- `sys.prefix` was the repository `.venv`;
- `sys.prefix != sys.base_prefix` was `true`;
- `importlib.util.find_spec("printer_v1")` was non-null;
- `importlib.util.find_spec("printer_v1.operator_cli.operational_memory_factory_command")`
  was non-null;
- the operational command was not imported or executed.

The disposable injected-launch proof established:

- exactly one launch call;
- `child_command[0]` matched the lexical venv path byte-for-byte;
- it differed from the resolved base target;
- the base target appeared nowhere in the child command;
- the remaining operational arguments were unchanged;
- terminal evidence recorded the same lexical path;
- retries, reruns, resumes, restarts, and successors remained `0`.

Focused fail-closed checks covered direct base-interpreter substitution,
missing/symlinked `pyvenv.cfg`, symlinked venv ancestors, broken/missing/
non-regular/non-executable entrypoints, future empty staging cleanup, and
non-empty staging preservation.

The proof demonstrates interpreter-bootstrap correctness and the continued
one-shot safety boundary. It does not demonstrate provider readiness, discovery
productivity, campaign completion, clean memory creation, retrieval quality,
paper-decision quality, or profit.

## 8. Database and evidence invariants

The bounded proof used filesystem stat and file hashing only for authoritative
DB and evidence reconciliation. It did not open SQLite.

### 8.1 Authoritative database

| Field | Verified pre/post value |
| --- | --- |
| Path | `data/printer_v1.sqlite3` |
| Size | `65671168` bytes |
| SHA-256 | `56ca1218442db1a571ba715794ba91b70c3bfeba242f21855275c026d4c8eed5` |
| `mtime_ns` | `1785617072867102156` |
| Journal | absent before and after |
| WAL | absent before and after |
| SHM | absent before and after |

### 8.2 Retained Migration-050 evidence

- file count: `12`;
- symlink count: `0`;
- sorted identity-listing SHA-256:
  `08e6f40b2e472d0bd8c6e8e1adaaac27a8b1af59d93571daa6cfb18f31dacb7a`;
- pre/post identity unchanged.

### 8.3 Retained authorization evidence

- file count: `1`;
- authorization SHA-256:
  `af63b05423c4baa7f577cc18b252ab96a2c4cd0200d534375164887727d55c60`;
- sorted identity-listing SHA-256:
  `3bcfbfda544613822b76844f73e70fa1a54d6d790132180f53354f593d1c676d`;
- pre/post identity unchanged.

### 8.4 Consumed external application

- five immutable application files;
- one preserved historical empty staging directory;
- complete parent sorted file-hash-listing SHA-256:
  `f1a12143425ab418b14bbd0e60dfacd5268b99a13e6c637590160dbfe034f96f`;
- pre/post identity unchanged;
- no historical application or staging evidence changed or was deleted.

The proof created no new real manifest, marker, authorization, campaign,
database, memory, retrieval, decision, position, trade, audit, or PnL artifact.

## 9. One-shot, security, and ownership laws

The repair section preserves the required laws:

- fresh exact branch/HEAD binding remains an authorization requirement;
- tracked-tree and current-evidence reconciliation remain enforced;
- the application root remains external to the repository;
- manifest and marker artifacts remain create-once;
- the consumed historical application continues to block reuse;
- one authorization permits at most one application;
- the wrapper owns at most one child;
- no automatic retry, manual rerun, resume, restart, or successor path was added;
- the child remains an argument sequence with `shell=False`;
- parent environment is not mutated;
- terminal evidence remains immutable and records the first honest outcome;
- Source Governor remains the only external-source owner;
- Central Scheduler remains the only runtime scheduling owner;
- no engine or wrapper bypass was introduced.

No V1 capability or financial lock was weakened.

## 10. Residual risks and limitations

### 10.1 Windows symlink-test portability

The committed Mac proof does not establish universal Windows symlink-test
portability. The disposable fixture creates symlinks, and a Windows environment
without symlink permission may fail during fixture setup.

This limitation does not block closing the exact historical macOS repair because:

- the historical failure occurred on the proven macOS repository environment;
- the implementation includes a Windows `.venv/Scripts` lexical contract;
- the Mac real-subprocess and disposable symlink proofs directly exercise the
  historical defect;
- the limitation concerns the portability of one test fixture, not evidence that
  the macOS repair remains defective.

It remains a documented later focused Windows-compatibility risk. No broad
cross-platform readiness claim is made by this closeout.

### 10.2 Bootstrap success is not campaign success

Module-spec discovery proves only that the intended venv identity is preserved
and the operational module is discoverable. It does not prove:

- provider credentials or availability;
- Source Governor source readiness;
- candidate eligibility or discovery productivity;
- Scheduler/campaign lifecycle completion;
- complete evidence collection;
- clean `WINDOW_15M` memory closeout;
- retrieval usefulness;
- conservative paper-decision quality;
- executable paper entry/exit realism;
- paper profit.

These remain future lane concerns.

## 11. Money-usefulness contribution

The closed repair prevents a scarce future one-shot authorization from being
wasted before Printer can import its approved operational command. It restores
the correct environment boundary required to reach the real governed preflight
in a later separately authorized lane.

That improves learning efficiency and protects operator time and evidence
integrity. It does not itself produce memory, a decision, a position, or profit,
and it makes no guaranteed-profit claim.

## 12. What the repair improves

The closed section improves:

- deterministic lexical venv interpreter identity;
- fail-closed interpreter validation before authorization-consumption side
  effects;
- protection against direct base-interpreter substitution;
- regression coverage for the exact historical failure;
- real OS subprocess proof of venv and editable-package discovery;
- preservation of one-child and no-retry laws;
- future empty-staging cleanup without historical evidence deletion;
- honest separation between bootstrap readiness and campaign readiness.

## 13. What remains locked

This closeout does not unlock:

- reuse of `V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z`;
- a new readiness result or final authorization;
- a new real manifest, marker, or wrapper application;
- provider/source access;
- Source Governor or Central Scheduler runtime;
- discovery or campaign execution;
- authoritative SQLite opening or mutation;
- memory generation or retrieval;
- paper decisions or BUY/SELL/HOLD;
- positions, trade events, paper-trade audits, or PnL;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, or `WINDOW_24H`;
- wallets, private keys, real funds, live execution, or paid APIs;
- scoring, ranking, confidence percentages, weighted logic, embeddings, or
  vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only and cannot independently unlock
retrieval, decisions, positions, trades, audits, or PnL. Printer remains
Solana-only, Solana-memecoin-only, and paper-only.

## 14. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Closeout disposition | Required later action |
| --- | --- | --- |
| Repaired bytes cannot bind the consumed authorization | Preserved as a hard lock | Fresh readiness followed by a new exact-HEAD authorization in separate lanes |
| Mac proof may not run unchanged on Windows without symlink permission | Residual portability limitation; does not block exact Mac repair closeout | Focused Windows fixture/permission compatibility review before broad Windows-proof claims |
| Bootstrap proof could be mistaken for campaign readiness | Explicitly rejected | Fresh authoritative campaign-readiness audit |
| Future provider or candidate-pool blockers may still exist | Unresolved and outside this repair | Readiness must inspect current source, environment, and campaign prerequisites without runtime |
| Another one-shot authorization could be wasted by unrelated blockers | Still possible | Fresh read-only readiness and independent final-authorization review before application |
| Dirty or incomplete memory could later be produced | Not unlocked | Existing memory-quality and clean-closeout gates remain mandatory |
| Profit could be overstated from chart-only outcomes | Not reached or unlocked | Later paper lanes must prove realistic entry, exit, fees, liquidity, and capital protection |
| Broad testing could create noise after a narrow repair | Avoided | Continue risk-based minimum sufficient verification |

## 15. Independent closeout decision

The closeout acceptance conditions are satisfied:

- the failure audit established one exact, evidence-backed code defect;
- the design selected the minimum safe repair;
- implementation matched the design and changed only approved files;
- focused red/green evidence reproduced and corrected the historical symptom;
- the bounded proof independently demonstrated lexical venv bootstrap and module
  discoverability;
- one-shot, environment, evidence, and terminal laws remained intact;
- authoritative DB and retained evidence identities remained unchanged;
- no unauthorized runtime or capability activation occurred;
- residual portability and campaign-readiness limitations are explicitly bounded;
- no campaign, memory, retrieval, paper, or profit readiness is claimed.

Therefore the interpreter-preservation repair section is closed PASS.

## 16. Exact next permitted lane

`V2-9.8B Post-Interpreter-Repair Authoritative WINDOW_15M Campaign Readiness Audit`

Lane type: fresh audit/readiness only.

That lane may inspect current committed code, exact branch/HEAD, environment
presence without exposing secrets, retained evidence, authoritative DB identity
without mutation, and all prerequisites for one future ordinary
`WINDOW_15M` application.

It may not run the production wrapper, contact providers, start Source Governor
or Central Scheduler runtime, run discovery/campaign work, open or mutate the
authoritative DB, generate memory, activate retrieval or paper decisions, create
positions/trades/audits/PnL, issue a final authorization, or reuse the consumed
authorization.

A later final authorization, if readiness passes, must be fresh, independently
reviewed, and bound to the exact then-current branch/HEAD. This closeout is not
that authorization.
