# Printer V1 Assistant Active Build Order Anchor

## 1. Purpose and authority

This document aligns Claude, ChatGPT, Codex, and future assistants before
Printer V1 memory-growth work.

It does not replace:

- `AGENTS.md`;
- `docs/printer-v1-clean-master-spec.md`;
- `docs/printer-v1-post-rc-build-order.md`;
- `docs/printer-v1-memory-factory-guide.md`;
- `docs/printer-v1-current-state-memory-growth-audit.md`; or
- `docs/printer-v1-memory-growth-build-order-v2.md`.

Inside that source stack, the active memory-growth build order remains:

`docs/printer-v1-memory-growth-build-order-v2.md`.

It is not the sole source of truth. Current lane position must also follow later
committed audits, designs, implementations, proofs, closeouts, and explicit
build-order reconciliations.

The current status reconciliation is:

`docs/printer-v1-v2-9-8b-post-migration-closeout-active-build-order-reconciliation.md`.

Verdict:

`V2_9_8B_POST_MIGRATION_CLOSEOUT_ACTIVE_BUILD_ORDER_RECONCILIATION_PASS`.

## 2. Active lane

V2-9 is closed PASS. V2-9.7A through V2-9.7F are closed. V2-9.7F verdict is:

`V2_9_7F_ACTIVATION_READINESS_PASS`.

V2-9.8A is closed:

`V2_9_8A_OPERATOR_ACTIVATION_GATE_PASS`.

The active lane remains:

```text
V2-9.8B — Active Bounded Memory Growth Operations
```

## 3. Completed V2-9.8B sequence relevant to the current lane

### 3.1 First authoritative campaign and accounting repair

The historical first authoritative campaign remains:

`V2_9_8B_FIRST_AUTHORITATIVE_15M_CAMPAIGN_BLOCKED_UNSAFE`.

The permanent no-rerun marker for execution
`20260731T002406Z-7612696c7295` remains valid.

The Accounting and Exact-Identity Report-Only Repair is closed:

- implementation PASS;
- independent operator-review PASS;
- closeout PASS;
- design baseline `e71e543d197154eba427b41e2e01574a59f527f5`;
- implementation commits `b168c57`, `fd35b41`, `0118a37`.

It repaired bounded-shortage stage evidence, independent pre-seal transport
verification, exact owner/action-local identity reconciliation, exception-safe
stage sealing, and exact-identity report-only behavior.

### 3.2 Post-accounting-repair readiness audit

The readiness audit is already complete and must not be repeated:

- audit commit: `84127c62ba6179fcbddb90e61ed09f43d6bed5a4`;
- read-only evidence transcript: `d97a382ca831558173fdfa7c5da570d813e2c954`;
- verdict:
  `V2_9_8B_POST_ACCOUNTING_REPAIR_AUTHORITATIVE_15M_CAMPAIGN_READINESS_AUDIT_PASS`.

That audit statically traced the repaired ordinary route, inspected the
authoritative DB read-only, verified the permanent marker and residual state,
and preserved all runtime and financial locks.

### 3.3 Post-repair attempt and full-run blocker

After the readiness PASS, post-repair campaign design and authorization advanced.
The bounded post-repair attempt was later closed as:

`V2_9_8B_POST_REPAIR_15M_BLOCKED_UNSAFE_FORENSIC_AUDIT_CONFIRMED`.

Two real `WINDOW_15M` lifecycles occurred, but the full-run campaign accounting
and terminal report could not be trusted because complete campaign-wide
Scheduler ownership, all-stage equality, exact window/cycle linkage, complete
quality/episode truth, and non-vacuous terminal evidence were not proven.

The approved response was:

1. full-run accounting and terminal-evidence design;
2. final C1-C15 conformance map;
3. schema design amendment;
4. migration implementation;
5. bounded disposable proof;
6. migration closeout.

### 3.4 Scheduler ownership schema chain

Completed documents and evidence include:

- `docs/printer-v1-v2-9-8b-full-run-accounting-final-conformance-map.md`;
- `docs/printer-v1-v2-9-8b-campaign-scheduler-ownership-schema-design-amendment.md`;
- `docs/printer-v1-v2-9-8b-campaign-scheduler-ownership-schema-migration-implementation.md`;
- `docs/printer-v1-v2-9-8b-campaign-scheduler-ownership-schema-migration-bounded-proof.md`;
- `docs/printer-v1-v2-9-8b-campaign-scheduler-ownership-schema-migration-closeout.md`.

Migration implementation controlling verdict:

`V2_9_8B_CAMPAIGN_SCHEDULER_OWNERSHIP_SCHEMA_MIGRATION_IMPLEMENTATION_PASS`.

Controlling bounded proof verdict:

`V2_9_8B_CAMPAIGN_SCHEDULER_OWNERSHIP_SCHEMA_MIGRATION_BOUNDED_PROOF_PASS`.

Migration closeout verdict:

`V2_9_8B_CAMPAIGN_SCHEDULER_OWNERSHIP_SCHEMA_MIGRATION_CLOSEOUT_PASS`.

Controlling proof execution:

`V2_9_8B_MIG050_BOUNDED_PROOF_20260801T144740Z_5df7a275`.

Closeout commit:

`d0e7298315239cc85ff47155a2922339a9e7a52e`.

Migration `050_campaign_scheduler_ownership_scope.sql` is proven only on a
byte-identical disposable copy. It is not applied to the authoritative database.
The supported authoritative schema head remains migration `049` until a later
explicit operator-approved application lane.

## 4. Current exact next permitted task

On:

`V2_9_8B_POST_MIGRATION_CLOSEOUT_ACTIVE_BUILD_ORDER_RECONCILIATION_PASS`

the exact next permitted task is:

```text
V2-9.8B Post-Repair WINDOW_15M Full-Run Accounting and Terminal-Evidence Implementation (C1-C15)
```

The implementation must start from the accepted schema baseline containing the
migration implementation, controlling proof package, migration closeout, and
this reconciliation. It must not merge or revive earlier false-PASS C1-C15 work
unchanged.

## 5. C1-C15 implementation boundary

Allowed:

- static inspection of the accepted schema baseline and existing implementation;
- implementation of the approved C1-C15 requirements only;
- focused disposable-database tests and nearest affected regressions;
- one campaign-wide `CampaignSixUnitOwner` and one independent action-local
  ledger before first accountable work;
- exact campaign/run/cycle/factory/token/pair/window/Scheduler/source identity;
- complete source-attempt, byte, row, reservation, validation, Scheduler,
  cadence, quality, report, terminal, and replay evidence required by the final
  conformance map;
- implementation documentation and factual PASS/BLOCKED closeout.

Not allowed:

- applying migration `050` to `data/printer_v1.sqlite3`;
- providers, RPC, WebSockets, source fetching, discovery runs, campaigns, or
  operational runtime;
- authoritative DB mutation;
- another post-repair campaign attempt;
- memory generation or promotion against the authoritative corpus;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, or `WINDOW_24H` activation;
- V2-10;
- retrieval or dirty-memory training;
- paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL;
- wallets, private keys, signing, real funds, paid APIs, scoring, ranking,
  confidence, weighting, embeddings, or vectors.

Use minimum sufficient risk-based verification. Run focused tests for the exact
C1-C15 surface and nearest affected ownership/accounting/report/replay
regressions. Reserve broad/full suites for the later major implementation
closeout or pre-proof checkpoint.

## 6. Required C1-C15 completion law

Every requirement must satisfy:

```text
design requirement
-> real execution boundary
-> single owner evidence
-> independent action-local evidence
-> canonical report field
-> acceptance-gate check
-> negative fail-closed test
```

PASS requires all C1-C15 requirements, including:

1. one full-run accounting owner;
2. complete immutable identity before lifecycle work;
3. every attributable source attempt observed exactly once;
4. exact byte and normalized-row equality;
5. real reservation boundaries;
6. real named validation boundaries;
7. complete Scheduler ownership and enqueue/claim/terminal observation;
8. bidirectional full-manifest equality;
9. window registration before slot terminalization;
10. exact cadence, coverage, and two-close completeness;
11. prevention of unlawful clean-episode insertion;
12. one complete canonical report and strict gate;
13. real terminal-safety and exactly-one-invocation evidence;
14. exact public report-only replay with zero source/Scheduler/write effects;
15. truthful stage terminal status and immutable first cause.

Allowed implementation PASS label:

`V2_9_8B_POST_REPAIR_WINDOW_15M_FULL_RUN_ACCOUNTING_AND_TERMINAL_EVIDENCE_IMPLEMENTATION_PASS`.

A PASS still does not authorize an authoritative migration application or
campaign execution. It permits only the next approved independent review/proof
step.

## 7. Operational route and preserved ownership

The restored ordinary route remains conceptually:

```text
public operational `run`
-> operator approval and exact preflight
-> verified backup / disposable restore rehearsal
-> governed discovery and deterministic selection
-> exact two-token tracking handoff
-> Source Governor + Central Scheduler
-> two isolated WINDOW_15M lifecycles
-> clean / dirty / blocked audit
-> terminal report and exact zero-source replay
-> safe stop with no successor
```

The C1-C15 implementation may repair this route only as required by the approved
full-run accounting design. It must not create another Scheduler, source loop,
report owner, replay owner, campaign runner, or database authority.

## 8. Deferred candidate-acquisition state

Candidate-acquisition foundation, N2/N7, live acquisition transport, global
Pump cursors, cursor recovery, migration-observation admission, and
optional-global accounting remain deferred/experimental.

They are not:

- active operational prerequisites;
- active factory intake authorities;
- public operational command modes;
- cursor or recovery authorities for the active factory; or
- permission for a retry, recovery, N7, or successor.

The active operational path must not read, reset, advance, or interpret those
candidate-acquisition cursors or recovery rows.

## 9. Permanent restrictions

Printer V1 remains:

- Solana-only;
- Solana memecoin-only;
- paper-trading only;
- no live wallet, private keys, signing, real funds, or live execution;
- no paid API dependency;
- no scoring, ranking, confidence, or weighted decision logic;
- no embeddings or vectors unless explicitly approved later;
- no Source Governor bypass;
- no Central Scheduler bypass;
- no dirty memory used for retrieval or decisions;
- no retrieval before its explicit approved lane;
- no paper decisions before their explicit approved lane;
- no BUY/SELL/HOLD unlock;
- no paper positions, trade events, paper trade audits, or PnL.

`WINDOW_5M_MICRO_EVENT` remains support-only. It never becomes a main outcome
memory, independently triggers continuation, counts toward main clean-memory
thresholds, or unlocks retrieval or financial behavior.

## 10. Assistant behavior

Assistants must:

- verify the exact baseline and lane before editing;
- read the final C1-C15 conformance map and schema amendment;
- preserve the accepted migration and controlling proof evidence;
- use disposable databases only for implementation tests;
- keep the authoritative database byte-identical;
- preserve Source Governor and Central Scheduler ownership;
- preserve exact token/pair and campaign identity;
- preserve clean, dirty, blocked, and `DO_NOT_TRAIN` separation;
- stop after the requested implementation lane and factual verdict.

Assistants must not:

- repeat the completed post-accounting-repair readiness audit;
- run providers/RPC/WebSockets or any campaign;
- apply migration `050` to the authoritative database;
- loosen evidence, identity, safety, budget, Scheduler, memory, or financial
  gates to make tests pass;
- auto-retry or auto-restart after terminal failure;
- start V2-10 or any later-window/retrieval/decision/financial lane.

## 11. Money-usefulness and remaining risks

The current implementation lane improves future paper-only money usefulness by
making all discovery, handoff, lifecycle, and cleanup work fully attributable,
preventing fake clean episodes, and ensuring terminal reports and replay reflect
the exact campaign rather than partial or vacuous evidence.

It makes no profit claim and unlocks no trading capability.

Main risks:

- C1-C15 is cross-cutting and can accidentally introduce a second owner;
- incomplete source-attempt or Scheduler observation can still produce vacuous
  equality;
- report fields can appear complete while execution-time evidence is missing;
- migration `050` can be mistaken for an authoritative application;
- earlier false-PASS implementation history can be mistaken for accepted code;
- broad test expansion can hide the exact defect and waste resources.

Mitigation: follow the final conformance map column by column, use focused
risk-based tests, fail closed on missing evidence, and preserve the authoritative
DB and all later capability locks.