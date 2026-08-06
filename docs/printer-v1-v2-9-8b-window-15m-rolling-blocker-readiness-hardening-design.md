# Printer V1 V2-9.8B WINDOW_15M Rolling Blocker-Readiness Hardening Design

## Verdict

`V2_9_8B_WINDOW_15M_ROLLING_BLOCKER_READINESS_HARDENING_DESIGN_COMPLETE`

This design adopts the operator-approved rolling audit-and-repair method for the ordinary public `WINDOW_15M` path. It does not create an authorization, run Printer, contact providers, mutate the authoritative database, or unlock any retrieval or financial capability.

## Baseline

- controlling implementation closeout branch: `agent/v2-9-8b-window-15m-pre-holder-transport-identity-repair-closeout-completion`
- controlling closeout commit: `50de72cc06a3f2597b3a56e660e3728128d1e2d1`
- prior repair verdict: `V2_9_8B_WINDOW_15M_PRE_HOLDER_TRANSPORT_IDENTITY_REPAIR_PASS`
- active memory-growth lane: `V2-9.8B — Active Bounded Memory Growth Operations`
- no new authorization is permitted inside this hardening section.

## Active source stack

Use together:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`

Also use the V2-9.7C operational design, all V2-9.8B repair/closeout documents that govern the reached path, and the official Solana Builder Source Stack modules relevant to each checkpoint.

## Goal

Reduce the chance that another one-use authorization is consumed by a deterministic code, composition, accounting, evidence, cleanup, or reporting defect.

The work must also ensure that a future runtime failure is surfaced as a precise structured terminal cause instead of requiring `child-stderr.txt` as the sole source of the campaign blocker.

This is readiness hardening, not a guarantee that live providers, market conditions, eligible tokens, or holder evidence will be available.

## Rolling method

Audit the ordinary public execution path in order. At each boundary:

1. inspect the production call path and controlling contracts;
2. identify a plausible deterministic blocker;
3. prove reachability and contract violation with a disposable fixture or migrated test database;
4. record the narrow design decision;
5. observe a RED regression before production modification;
6. implement the minimum repair;
7. run only the focused risk-based tests needed for that change;
8. independently inspect the resulting diff and behavior;
9. commit a checkpoint closeout;
10. continue from the repaired commit.

No production change is allowed for a merely suspicious pattern. Without a reachable reproduction or a direct contradiction of a controlling contract, record an audit note and continue.

## Checkpoint order

### Checkpoint 0 — Design and plan adoption

Commit this design and the execution plan from the exact controlling baseline.

### Checkpoint 1 — Authorization, wrapper, child launch, terminal propagation

Trace:

```text
one-use authorization package
-> external application validation
-> marker/provenance creation
-> child interpreter and environment preservation
-> child process launch
-> stdout/stderr capture
-> wrapper terminal output
```

Required outcome: exact child terminal evidence is written by a canonical child owner and safely projected into the wrapper terminal. `child-stderr.txt` remains immutable debugging evidence but is not the sole structured source.

### Checkpoint 2 — Child preflight and campaign initialization

Trace argument parsing, mode locks, authoritative DB target, sidecar quiescence, Git provenance authorization, migrations, integrity/FK checks, locked-capability baseline, concrete composition, dependency/source/budget preflight, recovery, campaign/run/cycle creation, supervision, lease, and heartbeat startup.

### Checkpoint 3 — Discovery, selection, source scope, and accounting

Trace Source Governor execution, discovery Scheduler ownership, direct/secondary acquisition, source-request scope, temporal authority, exact request and transport identity reconciliation, selection/two-slot handoff, and safe-stop cleanup.

### Checkpoint 4 — Holder evidence and admission

Trace exact `M = C = A`, holder budget/reservations, pacing, transport attempts, provider-failure separation, persistence, maturation, eligibility, and two-token admission.

### Checkpoint 5 — Scheduler ownership and lifecycle activation

Trace admitted tokens through Central Scheduler work identity, claims, lifecycle creation, support-only `WINDOW_5M_MICRO_EVENT`, main `WINDOW_15M` scheduling, cancellation, lease renewal, and no-restart policy.

### Checkpoint 6 — WINDOW_15M collection and clean-memory closeout

Trace observation freshness/quality, token/pair continuity, window coverage, episode/outcome construction, clean/dirty/blocked gates, fingerprint persistence, anti-look-ahead boundaries, and zero retrieval/financial deltas.

### Checkpoint 7 — Terminal closure, cleanup, replay, and residue

Trace every success and failure exit through campaign/run/cycle/supervision closure, Scheduler/work release, lease/lock release, immutable terminal report, report-only replay, and zero active residue.

### Checkpoint 8 — Full disposable public-composition proof

After every reached segment is audited and all confirmed blockers are repaired, run the real public composition with:

- disposable migrated databases;
- deterministic fixture transports;
- the real Source Governor and Central Scheduler owners;
- the real campaign, lifecycle, memory, cleanup, and terminal-reporting boundaries;
- no provider calls;
- no authoritative DB access or mutation;
- no authorization or application marker.

Prove one complete successful ordinary `WINDOW_15M` clean-memory closeout plus representative fail-closed boundaries, exact terminal propagation, zero active residue, and all lock preservation.

## Finding classifications

Each inspected boundary receives one of:

- `NO_REACHABLE_DEFECT_FOUND`
- `EXPECTED_LIVE_CONDITION`
- `DETERMINISTIC_BLOCKER_CONFIRMED`
- `REPORTING_OR_DIAGNOSTIC_DEFECT_CONFIRMED`
- `CLEANUP_OR_RESIDUE_DEFECT_CONFIRMED`
- `CROSS_CHECKPOINT_ARCHITECTURAL_BLOCKER`

Only the last four defect classifications may trigger implementation.

## Checkpoint artifact contract

Each checkpoint must record:

- baseline and final commit;
- exact production path inspected;
- files and functions inspected;
- confirmed findings and rejected suspicions;
- RED reproduction evidence;
- exact repair, if any;
- focused tests and results;
- no-provider/no-runtime confirmation;
- authoritative DB non-access or exact read-only identity proof where applicable;
- money-usefulness contribution;
- what improved;
- what remains locked;
- `Functionality Risks / Setbacks / Efficiency Blockers`;
- exact next checkpoint.

## Terminal propagation contract

A child terminal envelope must be written by the child process for success and every handled failure after child initialization. The wrapper may project only bounded, source-safe fields, including:

- terminal category and first cause;
- failure phase;
- execution/campaign/run/cycle identities when created;
- marker/application state;
- whether lifecycle work started;
- cleanup state and active residue;
- database identity after the child;
- terminal report path and hash when present.

Do not project secrets, request headers, provider payloads, URLs containing credentials, response bodies, or unbounded lists.

If the child cannot initialize enough to write its envelope, the wrapper must retain a distinct launch/bootstrap classification rather than mislabeling it as a campaign failure.

## Test policy

Use TDD and risk-based minimum sufficient verification. Each confirmed blocker receives its nearest regression and neighboring contract tests. Broad suites are reserved for cross-cutting checkpoint closeout and the final disposable public-composition proof.

All tests must use fixtures and disposable databases. No provider calls, wrapper application, authorization consumption, or authoritative DB mutation.

## Compatibility and evidence preservation

- Historical authorization/application evidence remains immutable.
- Existing terminal files remain readable.
- No historical terminal is rewritten to contain evidence it never recorded.
- Compatibility paths cannot claim current operational readiness.
- No DB migration is assumed; any proposed migration is a cross-checkpoint blocker requiring separate design approval.

## Hard locks

Do not:

- create, modify, reuse, rebind, or consume an authorization;
- run the one-shot wrapper or public operational command;
- contact providers or perform discovery/holder/runtime source work;
- mutate, restore, vacuum, checkpoint, normalize, or replace the authoritative DB;
- change provider order, source budgets, reservations, selection policy, liquidity floors, temporal law, or holder eligibility unless a proven blocker requires a separately explicit design decision;
- bypass Source Governor or Central Scheduler;
- unlock `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, or `WINDOW_24H`;
- make `WINDOW_5M_MICRO_EVENT` a main outcome or independent authority;
- activate retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, trade audits, or PnL;
- add wallets, keys, signing, real funds, live execution, paid APIs, scoring, ranking, confidence, weighting, embeddings, or vectors.

## Money-usefulness contribution

This hardening improves the reliability and auditability of the mechanism that creates clean 15-minute market memory. It protects future learning from incomplete evidence, hidden deterministic failures, false clean promotion, and ambiguous terminal reports. It does not guarantee profit or live market availability.

## What this section improves

- deterministic blocker discovery before another authorization;
- permanent regression coverage for confirmed defects;
- exact public-path composition confidence;
- structured child-to-wrapper terminal propagation;
- cleanup and residue confidence;
- clean-memory closeout reliability.

## What remains locked

Another authorization, provider execution, active memory operation, selective 1h, 4h/12h/24h, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, wallets, real funds, paid APIs, scoring, ranking, confidence, weighting, embeddings, and vectors.

## Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Control | Proof |
|---|---|---|
| Fixing suspicious but lawful behavior | Require reachable RED reproduction or direct contract contradiction | Finding classification and failing test |
| One huge unstable patch | Sequential checkpoint commits | Compare each checkpoint to its baseline |
| Later repair invalidates earlier evidence | Re-run affected nearest tests and document dependency | Checkpoint closeout |
| Fixture composition diverges from public path | Final proof enters through the real public composition | Full disposable proof |
| Hidden provider dependency enters tests | Fixture-only transport and static forbidden-call scan | Test logs and diff scan |
| Child terminal leaks source data or secrets | Bounded allowlisted projection | Source-safety tests |
| Terminal propagation changes campaign semantics | Reporting-only ownership and no retry/restart changes | Behavioral regression tests |
| Broad test expansion wastes time | Risk-based nearest suites per checkpoint | Recorded test rationale |
| Rolling work drifts from V2-9.8B | Source-stack and lock review at every checkpoint | Closeout lock section |

## Exact next step

Write and commit the checkpoint implementation plan, then begin Checkpoint 1 with static inspection and disposable RED tests only.
