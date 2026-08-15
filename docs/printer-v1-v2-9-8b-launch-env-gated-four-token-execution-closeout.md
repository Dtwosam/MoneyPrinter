# Printer V1 V2-9.8B Launch-Environment Repair + Gated Four-Token Execution Closeout

Date: 2026-08-15

## Verdict

`V2_9_8B_LAUNCH_ENV_GATED_FOUR_TOKEN_EXECUTION_BLOCKED_PRE_CONSUMPTION:operational_child_binds_AUTHORITATIVE_DB_repository_relatively_so_an_isolated_launch_checkout_targets_a_non_authoritative_database`

**No authorization was consumed. No application marker was created. The child was
never launched. Nothing was written anywhere.**

## Stage verdicts

| stage | verdict |
| --- | --- |
| **0 — launch `.venv` audit / provision / proof** | **PASS (17/17)** |
| **A — fresh authorization creation** | **PASS** |
| **B — independent review** | **PASS (39/39)** |
| **C — real pre-marker readiness + pre-consumption recheck** | **PASS** |
| **D — one-shot consumption + execution** | **BLOCKED PRE-CONSUMPTION by the wrapper's own free gate** |
| **E — terminal closeout** | **N/A** — nothing consumed, so no terminal state exists |

## Stage 0 — launch environment repair: PASS (17/17)

### Working-`.venv` audit (read-only)

| item | value |
| --- | --- |
| Python | `3.12.13` |
| `sys._base_executable` | `/opt/homebrew/Cellar/python@3.12/3.12.13_4/Frameworks/Python.framework/Versions/3.12/bin/python3.12` |
| `websockets` | `16.1.1` |
| `printer-v1` | `0.0.0`, **editable** |
| editable reference | `__editable__.printer_v1-0.0.0.pth` → `/Users/Dtwo1/Developer/MoneyPrinter/src` |

**Copying the existing `.venv` was ruled out**, exactly as the design warned: it
carries a stale checkout binding through that `.pth`, which would have made the
launch child import `printer_v1` from the user's working repository.

### Provisioning method (the preferred safe path)

1. `python3.12 -m venv <launch_root>/.venv` using the same base interpreter
   `/opt/homebrew/opt/python@3.12/bin/python3.12`;
2. `pip install websockets==16.1.1` — the exact observed version;
3. `pip install -e .` **from the launch checkout itself**.

All package fetching completed before authorization creation. PyPI was used only
for this developer-environment bootstrap; no paid dependency, and this is not
Printer operational source fetching.

### Proof from `<launch_root>/.venv/bin/python`

- `sys.prefix` resolves to `<launch_root>/.venv`
- `printer_v1.__file__` → `<launch_root>/src/printer_v1/__init__.py` — **inside the
  launch checkout, never the user's repository**
- `websockets` `16.1.1`, resolved from the launch venv
- the only `.pth` now reads `<launch_root>/src`; **no `.pth` points at the user's
  working checkout**
- `operational_memory_factory_command` and `four_token_proof_one_shot_wrapper`
  both import from the launch checkout
- `_select_child_python(repository_root=<launch_root>, override=<launch_root>/.venv/bin/python)`
  **PASS**, returning exactly `<launch_root>/.venv/bin/python`
- source configuration validates from the launch environment
- launch branch `agent/v2-9-8b-launch-env-gated-execution`, HEAD
  `4da9be74ef1a78947baedb7a40a212c510795606`, **no tracked file changed**

**The previously proven `.venv` blocker is resolved.**

## Stage A — fresh authorization: PASS

| field | value |
| --- | --- |
| authorization_id | `V2_9_8B_FOUR_TOKEN_PROOF_AUTH_20260815T191342Z_537f61ad` |
| SHA-256 | `ec410f7b337418f9c3da5ee403192888d1eee8ecd8577e450761a556e02f0001` |
| authorized_at / expires_at | `2026-08-15T19:13:42.504961+00:00` / `2026-08-16T07:13:42.504961+00:00` |
| bound branch / HEAD | `agent/v2-9-8b-launch-env-gated-execution` / `4da9be74…` |
| DB binding | `555f9558…`, size 94978048, inode 1230526, 56 / head 056 |
| migration execution | `MIGRATION_056_20260815T164802Z` |
| prior non-reusable | **38**, derived from evidence, no guessing |

Policy equals `exact_proof_policy()`: 4 / 2 / 2, 300 s, `WINDOW_15M` only, long
windows locked, 0 retries. One-shot semantics unchanged. Preconditions re-checked
17/17 immediately before creation.

## Stage B — independent review: PASS (39/39)

Fresh process, nothing trusted from Stage A. Re-derived artifact SHA, schema, TTL,
repository binding, all seven live DB identity fields, migration evidence, exact
proof policy, one-shot policy, the complete prior chain (independently re-derived
and **set-equal**), unconsumed state, the four migration-056 SHAs with 0 tracked,
and the launch `.venv` identity and dependency proof.

All three superseded authorizations — `…_1c9bc205`, `…_e033b252`, `…_a2252a7c` —
are present in the non-reuse chain.

## Stage C — real pre-marker readiness: PASS

`validate_git_provenance_manifest_pre_marker(..., profile=FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE)`
→ **PASS** for `…_537f61ad`. Manifest written outside the repository, sha
`12e113d03df51f9c3575e87cbff5bf47718435cb84053f00405a2961e808f2ef`, 7 files.

live branch/HEAD exact · `tracked_allowlist_overlap` empty · `tracked_current`
empty · migration-056 tracked count **0** · current inventory == 7-file manifest
set · historical authorization reconciliation **PASS** · historical migration
reconciliation **PASS**.

Immediate pre-consumption recheck: `_select_child_python` returned exactly the
launch venv interpreter, and the child import smoke exited `0`, importing
`printer_v1`, `websockets 16.1.1`, and `operational_memory_factory_command` all
from the launch checkout.

## Stage D — BLOCKED PRE-CONSUMPTION

`apply_authorization_once()` was invoked **exactly once** with explicit operator
approval. The wrapper's own free zero-state gate blocked it before consumption:

```
FourTokenProofOneShotWrapperError: authorization blocked before consumption:
  printer_process_state_unavailable: authoritative database file is unavailable
```

### Root cause — deeper than the interpreter

`operational_memory_factory_command.py:201` defines:

```python
AUTHORITATIVE_DB = Path(CANONICAL_PERSISTENT_DB).resolve()
```

which is **repository-relative**. Evaluated from the launch checkout it resolves
to `<launch_root>/data/printer_v1.sqlite3` — a path that does not exist and is
**not** the authoritative database:

```
AUTHORITATIVE_DB resolves to: <launch_root>/data/printer_v1.sqlite3
exists                     : False
is the real authoritative DB: False
```

The wrapper accepts an `authoritative_db_path` override, so its own gate could be
satisfied. **The operational child cannot be.** The child has no equivalent
override and would use its module-level `AUTHORITATIVE_DB`. Supplying the override
to the wrapper alone would therefore consume the authorization and then run the
child against a **non-authoritative, non-existent database** — most likely
creating an empty SQLite inside the launch checkout and producing a meaningless
run, with the one-use authority already spent.

That is precisely the outcome worth avoiding, so the override was not used and no
second invocation was made.

### The structural conflict, now fully mapped

- the **child** requires `repository_root` to be the checkout that owns the real
  `data/printer_v1.sqlite3` — only the user's working repository;
- **authorization provenance** requires live branch/HEAD to equal the bound
  branch/HEAD — only the isolated launch checkout;
- this lane **forbids** moving the user's working branch/HEAD;
- production code and the interpreter/provenance contracts **may not be changed**.

Stage 0 removed the interpreter layer of this conflict and revealed the database
layer beneath it. Both must be resolved together before execution is possible.

## Post-attempt state — nothing written

| check | value |
| --- | --- |
| application directory for `…_537f61ad` | **absent** |
| marker / manifest for the new ID | **0** |
| wrapper `.staging` entries | **0** |
| stray `<launch_root>/data/` | **not created** |
| authoritative DB sha | `555f9558…` unchanged |
| integrity / FK / sidecars | `ok` / `0` / none |
| ledger / head | `56` / `056_…` |
| eleven zero-state domains | all `0` |
| consumed authorizations | still only the two historical (`…101513Z`, `…_0022b4dc`) |
| wrapper invocations | **1** |

No source fetching, discovery, Scheduler, runtime, memory generation, campaign,
retrieval, decision, position, trade, audit, or PnL activity occurred. No
forbidden window or capability was activated. Zero retries, reruns, resumes,
restarts, or successors.

## Stage E — N/A

No marker, no consumption, no child process. There is no execution ID, child PID,
exit code, wrapper or child terminal classification, campaign/factory/cycle
state, POST database SHA, or WINDOW_15M memory outcome to record. Reporting any
of those would be fabrication.

## Money-usefulness contribution

Stage 0 permanently removed the launch-interpreter blocker and produced a
reusable, provably clean launch environment whose `printer_v1` resolves from the
launch checkout. Stages A–C then passed in sequence, so the authorization,
review, and provenance layers are all proven working. The remaining blocker was
caught by the wrapper's own free gate **before** the marker existed, so no scarce
one-use authority was spent on an environment that would have run against the
wrong database.

## What this operation improved

- Proved a launch `.venv` can be provisioned that satisfies the interpreter
  contract without inheriting the working repository's editable binding.
- Established the exact provisioning recipe: same base interpreter,
  `websockets==16.1.1`, `pip install -e .` from the launch checkout.
- Carried a real authorization through creation, a 39-check independent review,
  and the real pre-marker validator at a launch checkout for the first time.
- Identified the final blocker precisely: repository-relative `AUTHORITATIVE_DB`
  binding in the operational child.

## What it still does not unlock

Four-token proof execution, authorization consumption, campaign start, six-token
proof and capacity widening, WINDOW_1H rerun, WINDOW_12H / WINDOW_24H activation,
retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, paper audits,
PnL, wallets, private keys, real funds, live execution, scoring/ranking/confidence,
embeddings, and vectors. Solana memecoin-only and paper-only remain in force.

## Functionality Risks / Setbacks / Efficiency Blockers

- **The database binding and the branch binding are mutually exclusive under the
  current contracts.** Any future execution lane must resolve this explicitly. The
  realistic options are: (a) execute from the user's working repository with its
  branch moved to the bound commit — which needs the user's explicit consent since
  every prior lane forbade it; (b) place the launch checkout so that its
  repository-relative `data/printer_v1.sqlite3` *is* the authoritative database;
  or (c) change production contracts to make the child's authoritative-DB path
  injectable — forbidden here and requiring its own design, repair, and proof.
- Using the wrapper's `authoritative_db_path` override alone is a trap: it
  satisfies the wrapper's gate while leaving the child bound to the wrong
  database, and would burn the authorization to discover that.
- **Five authorizations have now been created without reaching execution.** The
  create/review cycle is the dominant cost. No further authorization should be
  created until the database/branch binding conflict is resolved and proven.
- Authorization `…_537f61ad` expires `2026-08-16T07:13:42Z` and is superseded by
  this closeout commit, which advances HEAD. Preserve it unconsumed; never
  salvage it.
- The launch `.venv` lives under the scratchpad and is machine-local; a future
  lane must reprovision it or relocate the launch root.
- The migration-056 triggers remain unexercised by a live campaign.

## Next lane

Resolve the authoritative-database binding conflict — decide between moving the
user's working branch to the bound commit, siting the launch checkout so it owns
the authoritative database, or making the child's DB path injectable — and prove
the chosen path **before** creating any further authorization.
