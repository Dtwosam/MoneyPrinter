# Printer V1 V2-9.8B Pre-Admission Discovery-Attempt Ownership Closeout

Date: 2026-08-13

## Verdict

`V2_9_8B_PRE_ADMISSION_DISCOVERY_ATTEMPT_OWNERSHIP_PASS_READY_FOR_FACTORY_LOOP_INTEGRATION_REVIEW`

This closeout establishes the prerequisite ownership seam only. It does not
integrate the canonical factory loop, run a four-token proof, or authorize any
operational activity.

## Starting authority

- Branch: `agent/v2-9-8b-four-token-bounded-capacity-proof-integration-implementation`
- Starting HEAD: `e17f5b13dc3386b4dcd9f6184717905f2ebc4c1a`
- The untracked operator authorization directory remained untouched:
  `operator-runs/v2-9-8b-standard-four-hour-final-authorization/`.

## TDD commit ledger

| Task | Gate | Commit |
| --- | --- | --- |
| 1 | RED schema/job-kind contract | `0eab774ef64f12b7bf62b9131f2bc4a5b8bd7951` |
| 1 | GREEN migration 055/job-kind | `25cebd3e8e5b6b4b778377b199427611b8890981` |
| 2 | RED attempt persistence | `32199659605d16af4c172f52bf0f888ef5c6b583` |
| 2 | GREEN persistence/state owner | `886b6ecab14fff96576c751b8f99c33b3562414a` |
| 3 | RED Scheduler ownership | `3b127f2c4f20af84392b3b5d82b897290a0d8a7d` |
| 3 | GREEN atomic job/attempt and active work | `70fe73780ad9657baaf535f4af736560257dd9f8` |
| 4 | RED shared gate/selection authority | `e4e79ac404288bbe6861fced8042fbbdee9eee76` |
| 4 | GREEN shared existing authority | `9b7fcefa3140dcced09c5edc7adab29ec7a5b32f` |
| 5 | RED one-shot callback | `806a3686c4f4cbe43f0401bbb05379f70e659684` |
| 5 | GREEN callback binding | `24d124c67545797f88bdb7f7477574f90168b007` |
| 6 | RED atomic cycle consumption | `6aca8a35a2424d2cc7504f49acd71a3daa283965` |
| 6 | GREEN atomic cycle 2/attempt transaction | `185e9cbec2a5543e3d65c7445da206e8d325eaed` |
| 5 hardening | RED terminal Scheduler parity | `d50c5b53551597b8362c67668ed73e62f797078a` |
| 5 hardening | GREEN terminal Scheduler parity | `4b785ab8d23c191bda9ec9f1ab2501ac150d3f50` |
| 7 | RED frozen-pair materialization | `4fed52740da8b4a852c1f3d268d01026491a3117` |
| 7 | GREEN source-free materialization | `2f1ff83d0013091bd39c0a6f8d82e84ee7cac598` |
| 5 hardening | RED failure terminalization/no retry | `9124ae87225992a4d0883ba80ab934b332d7b669` |
| 5 hardening | GREEN failure terminalization/no retry | `f9fcc9339ae9946b87a8dd005b47d13c38e9e6e3` |

## Task results

### Task 1 — schema ownership

Migration `055_pre_admission_discovery_attempt_ownership.sql` is additive. It
does not relax or rebuild migrations 034, 050, or 054. It adds:

- one campaign/run/configuration/authoritative-factory-rooted attempt table;
- one immutable exact-two selected-item table;
- one immutable provider-reaching source-lineage junction;
- proposed cycle ordinal fixed to `2`;
- one opportunity per campaign/run/authoritative factory/proposed ordinal;
- no pre-consumption cycle foreign key;
- a consumed-cycle foreign key that is populated only with `CONSUMED`;
- strict state, terminal-cause, timestamp, and source-linkage checks.

`PRE_ADMISSION_DISCOVERY_SELECTION` is a dedicated Scheduler `JobKind` placed
immediately after `DISCOVERY_REFRESH` in the existing priority order.

### Tasks 2 and 3 — persistence and Scheduler ownership

The attempt state law is:

```text
PLANNED -> RUNNING | BLOCKED | CANCELLED
RUNNING -> PAIR_READY | NO_PAIR | BLOCKED | FAILED | CANCELLED
PAIR_READY -> CONSUMED
```

Attempt creation and the one Scheduler job are committed in one transaction.
`RUNNING` requires the exact canonical Scheduler claim and lock owner. Active
work reporting includes only active attempts/jobs and excludes terminal work.
Every terminal callback outcome also drives the dedicated job terminal; supply
failure is `FAILED` with `max_retries=0`, and blocked/unwired work is cancelled.

### Task 4 — gate and selection parity

The existing combined executor and the pre-admission callback both call the
same owner-local gate and deterministic uniform-selection primitives. The
existing holder evidence result remains an input to that same gate carrier.
No predicate, score, rank, confidence, weight, budget ceiling, or selection
policy was copied or introduced.

### Task 5 — one-shot callback

The callback binds the exact campaign, campaign run, authoritative factory,
configuration, proposed cycle-2 identity, Source Governor owner, Central
Scheduler owner, and authoritative `MultiCycleAdmissionHealth` value. It
creates one deterministic attempt ID and executes the injected existing
eligible-supply owner once. Repeated invocation returns the durable terminal
attempt and cannot execute a second supply call or create a successor.

Provider-reaching source facts are linked to the attempt. The result is exactly
zero or two selected items. Pair-ready, no-pair, blocked, failed, and cancelled
states cannot reopen. The callback creates no cycle-2 row or lifecycle job.

### Task 6 — atomic admission/consumption

`admit_two_token_cycle_from_attempt(...)` owns one fresh `BEGIN IMMEDIATE`:

1. reload exact unconsumed `PAIR_READY` attempt and frozen pair;
2. reload canonical campaign/session/admission authority;
3. re-evaluate current admission health and historical identity non-reuse;
4. delegate to the existing exact-two cycle/slot creator;
5. create exactly ordinal-2 cycle slots `t1_c0002_slot` and
   `t2_c0002_slot`;
6. bind `consumed_cycle_id` and transition to `CONSUMED` before the same commit.

Any defer, health change, identity conflict, persistence fault, or ownership
mismatch rolls back both cycle creation and consumption. The frozen attempt is
not rerun.

### Task 7 — source-free cycle-rooted materialization

The consumed pair is checked byte-for-byte against its cycle-2 slots and its
immutable source linkage. Frozen channel labels are retained because they are
selection authority, not reconstructed later. Materialization writes normal
cycle-rooted discovery batch/work/merged-candidate/selection junctions through
the same selection batch/item persistence primitive used by the existing
combined executor.

The selected-item links point to `t1_c0002_slot` and `t2_c0002_slot` with
`LINKED_ONLY` state. Materialization performs:

- zero discovery source requests;
- zero selector calls;
- zero target substitution;
- zero tracking-queue creation;
- zero first-15m Scheduler enqueue;
- zero lifecycle activation.

Lifecycle scheduling remains after this prerequisite boundary and is not part
of this batch.

## Focused verification

The integrated prerequisite command covered:

- all seven new `test_v2_9_8b_pre_admission_*` files;
- existing combined discovery execution;
- existing multi-cycle session coordination;
- Phase-3 Scheduler priority/resource behavior;
- campaign Scheduler ownership schema;
- four-token controller readiness;
- canonical factory wiring contract;
- later-cycle callback lock contract;
- same-owner discovery seam;
- four-token proof-integration contract.

Result: `139 passed, 22 subtests passed`.

All touched production Python modules passed `py_compile`. `git diff --check`
passed.

## Operational and capability locks

The authoritative operational database was opened with SQLite `mode=ro` and
`PRAGMA query_only=ON`.

- migration count: `54`;
- applied head: `054_pre_lifecycle_discovery_refresh_wait.sql`;
- migration 055 applied: `False`;
- SHA-256 before/after inspection:
  `07035fba786aba1d141789e5c069fc5de5bfb6185b711500ce8fa901f5358bfd`.

No provider/source modules or provider ceilings changed. The operational
`TOKEN_CAPACITY` remains exactly `2`. No authoritative DB mutation, live source
fetch, real Scheduler runtime, callback execution against operational state,
proof authorization/run, four-token runtime, factory-loop wake integration,
12h/24h work, retrieval, decision, position, trade, audit, or PnL capability
was performed or unlocked.

## Functionality Risks / Setbacks / Efficiency Blockers

- Migration 055 intentionally remains unapplied to the authoritative DB; an
  independently authorized migration lane is still required before operational
  use.
- The production factory loop is intentionally not wired to this callback,
  admission transaction, or materializer. That is the next review boundary.
- The callback remains fail-closed until the existing eligible-supply owner and
  exact operational DB/configuration bindings are supplied by that later
  integration.
- Frozen materialization deliberately stops at `LINKED_ONLY`; lifecycle work
  must not be scheduled until the factory-loop integration is separately
  designed, reviewed, and tested.
- Verification was risk-focused as directed; no broad regression suite or live
  proof was run.

## Next permitted task

Independent review of this prerequisite closeout, followed only if accepted by
the canonical factory-loop integration review. Do not begin discovery reruns,
cycle-2 operational persistence, or a four-token proof from this closeout.
