# Printer V1 V2-9.8B Operational Factory Active-Path Restoration Closeout

Date: 2026-07-29

## Verdict

`V2_9_8B_OPERATIONAL_FACTORY_ACTIVE_PATH_RESTORATION_PASS`

The proven two-token operational Memory Factory is restored as the active
command path on the current migration-049 codebase. Candidate-acquisition N2,
N7, global Pump cursor, recovery and migration-observation admission no longer
sit in the public operational prerequisite chain.

The complete candidate-acquisition implementation, migrations, tables, tests,
closeouts and blocked live-proof evidence remain intact and importable as a
deferred/experimental subsystem.

No provider, RPC, WebSocket, N2, N7, recovery, campaign, tracking lifecycle,
snapshot, window or memory operation ran against the authoritative database.

## Exact baseline, branch and selected checkpoint

| Item | Exact value |
| --- | --- |
| Required starting HEAD | `a898327613b294e2ef252cb5e307e359bc0b4ced` |
| Starting tracked tree | clean |
| Restoration branch | `restore/proven-operational-factory` |
| Selected last-good implementation checkpoint | `7c38f13816169c69697ed19893b7e12802d9b1b7` |
| Selected subject | `Repair complete selective 1h blocker path` |
| First candidate-foundation critical-path commit | `219ad8125a75f52686bfbf5953be0fa4cdca4712` |
| First critical-path subject | `Adopt Pump candidate acquisition foundation` |
| Current schema head retained | `049_candidate_acquisition_integration.sql` |

`7416bc762744a56907d59f30d842d5fced0c9260` was not selected as the
implementation checkpoint because it is a read-only feasibility audit with no
code delta. Its history remains useful evidence. `7c38f13` is the latest actual
operational code checkpoint before the adoption commit.

## History decision

The exact post-E.47 commit and rejection map is recorded in:

`docs/printer-v1-v2-9-8b-operational-factory-active-path-restoration.md`.

The restoration retains:

- post-E.47 live two-token lifecycle, report, replay and cleanup behavior;
- E.48 holder-condition / memory-quality separation;
- V2-9.7F readiness and V2-9.8A operator-gate safeguards;
- the public operational command and fixed two-token 15m policy;
- first-operation failure handling and action-local accounting;
- holder-operation budgets and supervision contention repairs;
- honest blocked-supply reporting;
- exact graduated-market floor and eligible-supply intake;
- operational DB-mode and migration-ledger compatibility;
- batch-scoped discovery persistence;
- heartbeat evidence, lease, lock and terminalization protections;
- SQLite operational concurrency contracts;
- deterministic report-only replay;
- atomic two-slot tracking handoff and duplicate prevention;
- liquidity-evidence and continuation-reporting truth; and
- selective-1h implementation as separately gated, inactive-by-default code.

The restoration excludes from the active prerequisite path, but does not delete:

- candidate-acquisition foundation and its generic N mechanics;
- public N2/N7 operational CLI modes;
- live candidate-acquisition transport construction;
- global Pump cursor/backfill authority;
- cursor recovery as factory authority;
- migration-observation admission dependency;
- optional-global operation accounting; and
- all blocked N2 proof attempts as automatic retry or successor authority.

No independent post-foundation operational-factory safety or reporting repair
was found outside that acquisition/cursor/migration-observation subsystem.

## Restored command and dependency path

The registered command remains:

```text
printer-run-v2-9-8-memory-factory
-> printer_v1.operator_cli.operational_memory_factory_command:main
-> mode `run`
-> run_operational_campaign
-> _NORMAL_CAMPAIGN_POLICY
-> _run_operational_campaign
-> AuthoritativeLiveOperationalCampaignOwner.run_operational
```

The PowerShell wrapper remains:

`scripts/Start-PrinterV1-MemoryFactory.ps1`

No command was executed by this lane.

Ordinary `run` remains:

- operator-approved;
- exact DB/preflight gated;
- exactly two active tokens;
- `WINDOW_15M` only;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H` and `WINDOW_24H` locked;
- Source-Governed;
- Central-Scheduler-led;
- zero automatic retry;
- no automatic restart or successor; and
- terminal-report and zero-source-replay capable.

The public operational module no longer eagerly imports candidate-acquisition,
live candidate transport or cursor-recovery modules. Its public CLI no longer
advertises `acquisition-only-n2`, `acquisition-only-n7` or
`cursor-recovery-n2`.

Its preflight/status contract now reports:

```text
active_intake_path=PROVEN_TWO_TOKEN_OPERATIONAL_DISCOVERY_SELECTION
candidate_acquisition.state=DEFERRED_EXPERIMENTAL_NOT_OPERATIONAL_AUTHORITY
candidate_acquisition.operational_prerequisite=false
candidate_acquisition.public_operational_modes=false
candidate_acquisition.cursor_authority=false
active_token_capacity=2
```

A lazy, unregistered offline regression seam retains the historical
candidate-acquisition integration proof capability. It is not in
`pyproject.toml`, is not dispatched by `main`, and does not become another
operational runner, scheduler, source loop or DB authority.

## Current-schema offline proof

Proof database:

- disposable temporary SQLite database;
- all canonical migrations applied;
- migration count `49`;
- latest migration `049_candidate_acquisition_integration.sql`;
- frozen transports only;
- temporary test DB treated as the canonical persistent target only inside the
  fixture boundary;
- no provider or network call.

Exact proof result:

| Evidence | Result |
| --- | --- |
| run status | `COMPLETED` |
| activated slots | `2` |
| distinct mint identities | `2` |
| distinct pair identities | `2` |
| recorded exact selection-to-tracking handoffs | `2` |
| selected rows with non-empty categorical reason/lane | `2 / 2` |
| completed `WINDOW_15M` closes | `2` |
| clean 15m episodes | `2` |
| dirty 15m episodes in clean fixture | `0` |
| 1h close steps | `0` |
| 4h close steps | `0` |
| 12h/24h activation | `0` |
| 5m main-memory promotions | `0` |
| candidate-acquisition table-row delta | `0` |
| candidate cursor/recovery delta | `0` |
| pending/running run steps | `0` |
| active/locked Scheduler jobs after stop | `0` |
| running jobs after stop | `0` |
| SQLite integrity | `ok` |
| foreign-key violations | `0` |

The clean fixture recorded 30 governed source-request rows and 28 Scheduler job
rows across their distinct request/work responsibilities. The directly
affected Source Governor, Scheduler, discovery-work parity, transport-operation
and terminal-accounting regressions passed. No request or job residue remained.

The proof retained two independent mint/pair identities from discovery through
selection, token slots, tracking queue, snapshots, window close and report.

The adjacent E.47/E.48 regressions also passed the dirty, blocked,
`DO_NOT_TRAIN`, adverse-outcome and evidence-quality separation cases. No gate
was weakened to make the clean fixture pass.

## Replay, cleanup and locked deltas

Two consecutive `load_report_only` calls returned identical content. Replay
reported:

- new source calls: `0`;
- new evidence rows: `0`; and
- database bytes before/after replay: identical.

Locked-capability deltas in the exact proof:

| Surface | Delta |
| --- | ---: |
| memory retrieval queries | 0 |
| memory retrieval matches | 0 |
| paper decisions | 0 |
| paper positions | 0 |
| paper trade events | 0 |
| paper trade audits | 0 |
| paper audit reports | 0 |

BUY, SELL, HOLD, PnL, wallets, private keys, signing, real funds and live
execution remained absent.

## Deferred candidate-acquisition proof

The deferred subsystem remains importable:

- `printer_v1.discovery.candidate_acquisition`;
- `printer_v1.operator_cli.candidate_acquisition_integration`;
- `printer_v1.operator_cli.live_candidate_acquisition_transport`; and
- `printer_v1.operator_cli.cursor_continuity_recovery`.

Its current-schema offline regressions passed:

- foundation: `25 passed`;
- post-foundation integration: `116 passed`;
- cursor continuity/recovery: `16 passed`.

These tests use frozen inputs and disposable databases. They do not reactivate
the subsystem or make its state operational authority.

## Authoritative database proof

Authoritative database:

`data/printer_v1.sqlite3`

| Check | Result |
| --- | --- |
| SHA-256 before | `e748ba505cb8c7d67b8feb3a09b97719a0f3560e41dfb9242570cff3157962e6` |
| SHA-256 after | `e748ba505cb8c7d67b8feb3a09b97719a0f3560e41dfb9242570cff3157962e6` |
| byte hash unchanged | PASS |
| migration count | 49 |
| latest migration | `049_candidate_acquisition_integration.sql` |
| journal mode | `delete` |
| integrity | `ok` |
| foreign-key violations | 0 |
| `-journal` / `-wal` / `-shm` residue | none |

No backup was restored over the authoritative database.

## Files changed

- `AGENTS.md`
- `docs/printer-v1-assistant-active-build-order-anchor.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-v2-9-8b-operational-factory-active-path-restoration.md`
- `docs/printer-v1-v2-9-8b-operational-factory-active-path-restoration-closeout.md`
- `src/printer_v1/operator_cli/operational_memory_factory_command.py`
- `tests/test_v2_9_7e_11_authoritative_live_operational_campaign.py`
- `tests/test_v2_9_8b_candidate_acquisition_post_foundation_integration.py`
- `tests/test_v2_9_8b_operational_factory_active_path_restoration.py`

No migration, database, provider adapter, Scheduler owner, Source Governor
owner, memory-quality gate, retrieval surface or financial surface changed.

## Tests and checks run

- restoration proof: `5 passed`;
- broad affected operational suite: `151 passed, 45 subtests passed`;
- deferred foundation suite: `25 passed`;
- deferred post-foundation integration suite: `116 passed`;
- deferred cursor continuity/recovery suite: `16 passed`;
- Python compilation of changed Python/test modules: PASS;
- current authoritative DB read-only migration/integrity/FK/journal check: PASS;
- authoritative DB SHA-256 before/after: PASS;
- SQLite sidecar residue scan: PASS;
- `git diff --check`: PASS before closeout, repeated at final audit;
- active-pointer and accidental-unlock scan: PASS at final audit.

No broad unrelated repository suite was run.

## Money-usefulness contribution

The restoration returns Printer to a path already proved to collect two genuine
15m token histories while keeping selection reasons, token/pair identity,
evidence quality, realistic liquidity/holder protections, negative outcomes,
terminal accounting and replay auditable.

It removes a blocked experimental intake prerequisite that prevented the proven
factory from being treated as operationally available. It does not claim
profit, increase capacity, loosen evidence or turn candidate supply into alpha.

## What remains locked

- authoritative operational campaign execution;
- providers, RPC, WebSockets and live source work;
- candidate-acquisition N2 or N7;
- global Pump cursor/backfill and recovery;
- automatic retry, restart or successor;
- runtime capacity above two;
- restoration-proof 1h/4h/12h/24h activation;
- retrieval and dirty-memory training;
- paper decisions and BUY/SELL/HOLD;
- positions, trade events, paper audits and PnL;
- wallets, private keys, signing, real funds and live execution;
- paid APIs;
- scoring, ranking, confidence percentages and weighted logic;
- embeddings and vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only.

## Functionality Risks / Setbacks / Efficiency Blockers

| Type | Risk / setback / blocker | Treatment |
| --- | --- | --- |
| operational risk | the proven intake still depends on free/public source availability and may honestly find fewer than two eligible tokens | preserve exact two-or-none activation and blocked-supply reporting; never patch a manual token list |
| contract risk | the historical PumpPortal free/keyless locator contract may drift before any future live operation | require a separate current contract/preflight review before live use; this restoration performed no provider call |
| evidence risk | exact holder, liquidity, pair, freshness, safety or tradeability facts may be absent in real supply | keep UNKNOWN/dirty/blocked outcomes; do not weaken gates |
| yield setback | a restored active path can still produce dirty or zero clean memory when sources are incomplete | report honestly; clean yield is not forced |
| efficiency blocker | exactly two active tokens limits growth rate | capacity two is intentional and remains locked |
| deferred-code risk | the retained candidate subsystem can drift while inactive | keep import/offline regression coverage; no public operational dispatch |
| documentation risk | historical candidate closeouts contain former "next task" language | active anchors explicitly mark that history deferred and superseded |
| proof limitation | the exact restoration proof is frozen/offline | PASS authorizes review only, not a live campaign |

## Exact next permitted task

```text
Operator review of branch restore/proven-operational-factory,
commit "Restore proven operational factory active path",
the restoration design, this closeout, and the offline proof evidence.
```

No merge into `master`, tag, live campaign, provider/RPC run, N2, N7, recovery,
cursor reset, retry, memory operation, retrieval or financial capability is
authorized by this PASS.
