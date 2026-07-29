# Printer V1 V2-9.8B Operational Factory Active-Path Restoration

Date: 2026-07-29

## 1. Lane and authority

This document freezes one cohesive restoration lane:

```text
history and dependency review
-> exact last-good operational architecture
-> restoration design
-> implementation
-> current-schema offline proof
-> closeout
```

Required starting HEAD:

`a898327613b294e2ef252cb5e307e359bc0b4ced`

Restoration branch:

`restore/proven-operational-factory`

The lane is offline-only. It does not authorize providers, RPC, N2, N7,
candidate-acquisition recovery, a campaign, tracking against the authoritative
database, snapshots, windows, memory growth, retrieval, or any financial
capability.

The authoritative database is read-only for this lane. Its required starting
SHA-256 is:

`e748ba505cb8c7d67b8feb3a09b97719a0f3560e41dfb9242570cff3157962e6`

All executable proof uses disposable databases on the current migration ledger
through `049_candidate_acquisition_integration.sql`.

## 2. Mandatory Source-Grounded Blocker Investigation

```text
BLOCKER CLASSIFICATION:
MISSING_APPROVED_IMPLEMENTATION_BOUNDARY

EVIDENCE:
The proven public `run` route remains present and still selects the fixed normal
campaign policy. It is exactly two-token, `WINDOW_15M` only, Scheduler-led and
Source-Governed. Candidate acquisition did not replace `_run_operational_campaign`.
However, `operational_memory_factory_command.py`, the sole public operational
module, eagerly imports candidate-acquisition integration, live transport and
cursor-recovery modules and advertises N2, N7 and cursor recovery beside the
operational modes. The active roadmap then made those modes the next operational
prerequisite chain.

OFFICIAL-SOURCE COMPARISON:
No Python or SQLite behavior requires the eager imports or shared CLI modes.
Removing eager imports from the active module is compatible with Python import
semantics. Current-schema support remains append-only; migrations 048 and 049
are retained and applied to disposable proof databases.

PRINTER-CONTRACT COMPARISON:
The Python Builder Guide requires one canonical operational runner, narrow
ownership, no speculative retry, current migration compatibility and no
Source Governor or Central Scheduler bypass. The operator-directed restoration
requires the last proven operational intake to be active without N2, a global
Pump cursor, recovery or migration-observation admission authority. It also
requires the complete later candidate implementation to remain intact but
inactive.

ROOT CAUSE:
The candidate-acquisition adoption introduced a missing separation boundary:
experimental acquisition and cursor modes became eager dependencies and public
modes of the operational factory command even though the proven factory owner
did not consume their manifest, cursor or recovery state.

CODE CHANGE JUSTIFIED: YES

MINIMUM SAFE RESPONSE:
Keep the proven campaign owner and all independent later operational repairs.
Remove candidate-acquisition and cursor-recovery modes and eager imports from
the active public operational command. Retain the deferred implementation,
schema, evidence and direct offline helper seams. Publish explicit active/deferred
status metadata. Do not add another scheduler, source loop, database authority
or campaign runner.

FOCUSED PROOF:
Migration-049 disposable database; exact-two-token frozen operational lifecycle;
selection and tracking handoff audit; candidate-table/cursor/recovery zero
deltas; Scheduler/Governor reconciliation; isolated identities; 15m
clean/dirty/blocked mechanics; terminal cleanup; zero-source replay; locked
capability zero deltas; candidate module import and offline regressions.

UNTOUCHED SCOPE:
Applied migrations; authoritative DB contents; candidate-acquisition foundation,
transport, cursor, recovery and evidence modules; provider contracts; source
budgets; evidence-quality gates; retrieval and financial code.

AUTHORIZATION STATUS:
Offline restoration implementation and disposable proof are authorized.
Live execution and authoritative DB mutation are not.

NEXT ROADMAP-COMPLIANT STEP:
On PASS, operator review of the restoration branch only.
```

## 3. Exact history result

### Selected last-good operational checkpoint

The selected implementation checkpoint is:

`7c38f13816169c69697ed19893b7e12802d9b1b7`

Subject:

`Repair complete selective 1h blocker path`

This is the latest code checkpoint before candidate-acquisition work entered
the active operational dependency order. It contains:

- the live-proven post-E.47 two-token full-pilot architecture;
- E.48 holder-condition / memory-quality separation;
- V2-9.7F activation readiness and V2-9.8A operator-gate protections;
- the public two-token operational command;
- post-activation failure, supervision, reporting, persistence, heartbeat,
  provenance, replay and lock repairs;
- the original governed discovery, selection and atomic two-slot tracking
  handoff;
- the first successful bounded 15m memory-growth result; and
- later selective-1h code and fixes as inactive-by-default, separately gated
  capability.

The restored ordinary `run` mode remains 15m-only. Selective 1h is not invoked
or activated by this lane.

### Rejected candidate checkpoints

| Checkpoint | Disposition | Exact reason |
| --- | --- | --- |
| `7df7ac0` | rejected as too early | E.47 repair was ready but its fresh live two-token proof and later independent safeguards were not yet retained |
| `b66a40d` | rejected as too early | exact post-E.47 live PASS, report replay and clean shutdown were proved, but E.48 and activation/operational hardening were still later |
| `7326b9a` | rejected as too early | holder-condition / memory-quality separation was fixed, but public activation and V2-9.8B operational repairs were absent |
| `6ef7ace` | rejected as too early | activation-readiness review passed, but the durable public operational route was not complete |
| `6945d5d` | rejected as too early | operator gate passed, but subsequent independent runtime hardening and successful 15m operation were not retained |
| `bb00d89` | rejected as too early | first successful bounded 15m memory growth was proved, but selective-1h-adjacent tracking/liquidity/reporting corrections were not yet retained |
| `7416bc7` | rejected as an architecture checkpoint | it is a read-only feasibility audit with no code delta; the latest implementation remains `7c38f13` |
| `219ad81` and later | rejected for the active path | candidate-foundation adoption entered the operational prerequisite chain; later code/evidence remains preserved but deferred |

### First critical-path commit

The first commit where the candidate-acquisition overhaul entered the active
operational critical path is:

`219ad8125a75f52686bfbf5953be0fa4cdca4712`

Subject:

`Adopt Pump candidate acquisition foundation`

That commit was documentation-only, but it inserted the foundation sequence
ahead of another operational campaign and changed the active source and roadmap
authority. `164dcd5` built migration 048 and the foundation. `f50ca45` then
integrated N2/N7 into the public operational command and added migration 049.

## 4. Preserved independent changes

The following post-E.47 changes are preserved because they are independent of
the candidate-acquisition prerequisite and strengthen the selected factory:

| Commit | Preserved reason |
| --- | --- |
| `7326b9a` | separates holder condition from evidence quality without weakening identity, freshness or provenance |
| `db6c2a1`, `6945d5d` | public operational command, fixed two-token policy, operator approval and Scheduler residue controls |
| `963627a` | first-operation failure handling, provenance and manual orphan recovery protections |
| `fb276e4` | holder-operation accounting and supervision contention repair |
| `5e86c30` | honest insufficient-supply and source reporting |
| `c1741c0` | original eligible-pool productivity and exact graduated-market floor |
| `d6d6a75` | current operational DB-mode lifecycle entry and migration compatibility |
| `02445ac` | batch-scoped discovery persistence and deterministic identities |
| `455594e` | heartbeat failure evidence and terminalization |
| `5dde3ae` | canonical migration-ledger and production-command requalification |
| `c942194` | SQLite operational write/heartbeat concurrency contracts |
| `e450468` | eligible-token supply reserve used by the proven intake path |
| `3b08ac4` | bounded discovery-only qualification and audit reporting |
| `67ae2a3`, `098048c` | selective-1h implementation and command remain separately gated; ordinary `run` keeps 1h locked |
| `1edb5e9` | duplicate-tracking prevention and exact two-slot handoff |
| `011f966` | liquidity-evidence reporting truth |
| `043f9ea`, `7c38f13` | continuation eligibility, terminal reporting and tracking reconciliation fixes |

Documentation-only closeouts paired with those commits remain historical
evidence. They are not duplicated or rewritten.

## 5. Deferred and excluded changes

The candidate-acquisition work is not deleted or reverted. The following
changes remain in the current tree, schema and Git history but are excluded from
the restored operational prerequisite chain:

| Commit(s) | Deferred treatment |
| --- | --- |
| `219ad81` | roadmap adoption is superseded for active-path authority by this restoration; preserved as historical evidence |
| `164dcd5` | foundation module, migration 048, source contracts and offline tests remain importable and schema-compatible |
| `f50ca45` | integration module and migration 049 remain; N2/N7 leave the public operational mode list |
| `34100c9`, `a156486`, `50e45a0` | live transport, pipeline and mint-admission repairs remain deferred |
| `2b6e820`, `5af4b45` | durable cursor and recovery code/evidence remain deferred and are not read as operational authority |
| `cf5622f`, `f5e23d5` | migration-observation decoupling and optional-global accounting repairs remain deferred |
| `f68d743`, `4c11347`, `20c1f1b`, `f1def8f`, `599179f`, `01e2315`, `90f80d8`, `f9bf35c`, `a898327` | terminal proof and closeout evidence remains historical; no blocked proof becomes a prerequisite, retry or automatic successor |

There is no later post-foundation operational-factory safety or reporting fix
outside that acquisition/cursor/migration-observation subsystem. Therefore no
independent post-foundation factory fix is lost by deactivating the subsystem.

## 6. Frozen restoration design

### Active path

```text
public operational `run`
-> exact activation preflight and operator approval
-> verified backup / disposable restore rehearsal owner
-> one campaign + one cycle
-> proven mixed governed discovery and eligible-supply front door
-> deterministic selection with persisted reasons
-> atomic exact two-slot tracking handoff
-> Central Scheduler work
-> Source Governor requests and exact operation accounting
-> two isolated token/pair WINDOW_15M lifecycles
-> clean / dirty / blocked audit
-> terminal reconciliation and report
-> deterministic zero-source replay
-> safe stop with no successor
```

The path does not read, reset, advance or interpret:

- `printer_candidate_acquisition_cursors`;
- candidate-acquisition integrations, work, leases, reports or recovery rows;
- global Pump cursor state; or
- migration-observation admission as operational authority.

### Deferred boundary

The candidate-acquisition and cursor-recovery Python modules, migrations 048/049
and offline tests remain in the repository. Direct helper seams may continue to
support historical/offline regression tests, but the sole public operational
CLI no longer imports those modules eagerly or advertises their execution modes.

The public preflight and status surfaces report:

- active intake = proven operational discovery/selection/tracking path;
- candidate acquisition = deferred/experimental;
- operational prerequisite = false;
- cursor authority = false; and
- active capacity = exactly two.

### Current schema

Migration 049 remains the canonical schema head. No applied migration is edited.
The ordinary factory must accept an exact 49-entry ledger, ignore inactive
candidate-acquisition tables, and preserve all their rows byte-for-byte within
the disposable proof.

## 7. Locked capability boundary

This lane does not unlock:

- providers, RPC, WebSockets or live source execution;
- N2, N7, cursor recovery, backfill or automatic retry;
- a campaign against the authoritative database;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H` or `WINDOW_24H`;
- retrieval or dirty-memory training;
- paper decisions or BUY/SELL/HOLD;
- positions, trade events, paper audits or PnL;
- wallets, private keys, signing, real funds or live execution;
- paid APIs, scoring, ranking, confidence, weighting, embeddings or vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only and cannot trigger continuation or
count as a main outcome memory.

## 8. Minimum proof contract

The PASS proof must use frozen transports and disposable migration-049
databases and establish:

1. exact two-token selection, auditable reasons and atomic handoff;
2. zero candidate-acquisition integration, cursor and recovery deltas;
3. reconciled Scheduler/Governor accounting;
4. token/pair isolation;
5. bounded 15m clean/dirty/blocked mechanics;
6. terminal report, zero-source replay and no cleanup residue;
7. integrity `ok`, zero foreign-key violations and migration head 049;
8. zero retrieval and financial deltas;
9. active capacity two, 5m support-only and longer windows inactive; and
10. deferred modules import plus directly affected offline regressions.

Any relevant failure produces:

`V2_9_8B_OPERATIONAL_FACTORY_ACTIVE_PATH_RESTORATION_BLOCKED`

No budget, evidence, identity, freshness, holder, liquidity, tradeability,
clean-memory or safe-stop rule may be weakened to obtain PASS.
