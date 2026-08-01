# Printer V1 V2-9.8B Post-Migration Authoritative WINDOW_15M Campaign Final Authorization

Date: 2026-08-01

Lane:
`V2-9.8B Post-Migration Authoritative WINDOW_15M Campaign Final Authorization`

Review type: independent final go/no-go inspection and documentation only.

## 1. Verdict

`V2_9_8B_POST_MIGRATION_AUTHORITATIVE_WINDOW_15M_CAMPAIGN_FINAL_AUTHORIZATION_PASS`

Exactly one future invocation of the ordinary two-token `WINDOW_15M` campaign is
authorized, subject to every pre-run gate and stop condition in this document.

This final authorization does not itself run providers, discovery, Central
Scheduler runtime, the campaign, memory generation, report replay, retrieval,
paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.

The authorization is consumed by the first attempted ordinary campaign
invocation, even if the command blocks or terminates before producing clean
memory. No automatic retry, manual rerun, resume, restart, successor, or second
invocation is authorized.

## 2. Controlling source stack and roadmap alignment

This review uses the active Printer V1 source stack:

- `AGENTS.md`;
- `docs/printer-v1-clean-master-spec.md`;
- `docs/printer-v1-post-rc-build-order.md`;
- `docs/printer-v1-memory-factory-guide.md`;
- `docs/printer-v1-current-state-memory-growth-audit.md`;
- `docs/printer-v1-memory-growth-build-order-v2.md`.

The active memory-growth build order permits a readiness PASS to advance only to
an approved design/specification or final-authorization step. The existing
campaign design, repaired C1-C15 implementation, proof chain, migration 050
application, migration closeout, and post-migration readiness audit are already
complete. Repeating design or implementation would add scope without improving
safety.

This authorization therefore advances only to one bounded ordinary execution.
It does not skip the required immediate terminal evidence capture and independent
post-run closeout.

## 3. Controlling identities

| Item | Value |
| --- | --- |
| Repository | `Dtwosam/MoneyPrinter` |
| Final-authorization branch | `agent/v2-9-8b-post-migration-window-15m-final-authorization` |
| Final-authorization baseline | `a545d8839934306401c741fbe3f8c622655d7617` |
| Readiness audit commit | `a545d8839934306401c741fbe3f8c622655d7617` |
| Readiness verdict | `V2_9_8B_POST_MIGRATION_AUTHORITATIVE_WINDOW_15M_CAMPAIGN_READINESS_AUDIT_PASS` |
| C1-C15 repair commit | `e97fa898938f90e3d2c4aaf32c262db7367bffaa` |
| C1-C15 verdict | `V2_9_8B_C1_C15_FINAL_INDEPENDENT_CONFORMANCE_REVIEW_PASS` |
| Migration-application closeout commit | `fcef6ff55affaec6cc95326105300b6ffe2b59fe` |
| Migration count and tip | `50 / 050_campaign_scheduler_ownership_scope.sql` |
| Migration 050 Git blob SHA | `3a5bf6de05deb202316b6689a2d7f4206359e6e9` |
| Authoritative database | `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3` |
| Authorized pre-run DB SHA-256 | `56ca1218442db1a571ba715794ba91b70c3bfeba242f21855275c026d4c8eed5` |
| Authorized pre-run DB size | `65671168` bytes |
| Authorized pre-run DB `mtime_ns` | `1785617072867102156` |
| Migration execution ID | `V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f` |
| Verified pre-050 backup SHA-256 | `e13c40892f0c14d4c07960e00218569a536c50c0fc27815049284c3dd2aff5c2` |
| Readiness evidence SHA-256 | `7a3db962b2d99e83d7732da746a3fa5fb73ea4d03434c4a6be9305ae5a1dd5f5` |

The campaign must run from the exact final-authorization commit created by this
document. No later source, migration, test, launcher, or configuration-contract
change may be included without a new readiness and authorization review.

## 4. Accepted readiness basis

The post-migration readiness audit established:

- exact canonical migration ledger `50/050`;
- integrity exactly `ok`;
- zero foreign-key violations;
- complete stage-scoped Scheduler ownership columns, constraints, indexes, and
  triggers;
- zero duplicate non-null Scheduler-job ownership;
- zero active campaigns, campaign runs, campaign supervision, campaign Scheduler
  work, Scheduler jobs, discovery work, factory steps, and proof supervision;
- zero locked Scheduler jobs;
- all historical leases terminal, cleaned, released, and without lock files;
- exact protected baseline counts;
- complete migration authorization, backup, application, proof, and closeout
  continuity;
- valid redacted source configuration;
- zero-I/O source preflight status `READY` with zero issues;
- Source Governor and Central Scheduler ownership with no bypass;
- ordinary route fixed to two tokens and `WINDOW_15M`;
- zero automatic retries;
- longer windows locked;
- authoritative database unchanged throughout the audit.

The first readiness helper's `TOKEN_CAPACITY` marker failure was a
non-controlling collector ownership error. The corrected collector inspected the
actual contract and passed without any database or runtime action.

## 5. Accepted C1-C15 basis

The final independent conformance review accepted C1-C15 after the focused
repair at `e97fa898938f90e3d2c4aaf32c262db7367bffaa`.

The accepted chain covers:

- one coordinator-created accounting owner;
- complete campaign/run/cycle/configuration/factory identity;
- real governed source success and failure accounting;
- canonical transport and normalized-row identity;
- lifecycle reservation accounting;
- named validation-family evidence;
- stage-scoped Scheduler ownership and transitions;
- owner/action-local manifest equality;
- campaign-window ownership before terminal slot reconciliation;
- exact cadence, snapshots, and close operations;
- unlawful clean-episode prevention;
- durable authorization, invocation, cleanup, release, factory configuration,
  ownership, and accounting evidence;
- one authorization, one supervision invocation, one factory binding, durable
  cleanup, released lease, zero residue, and no retry/restart/resume/successor;
- exact read-only report replay reconstruction;
- real terminal status and first-terminal-cause preservation.

A campaign terminal outcome is accepted only when this evidence chain remains
complete and the canonical acceptance gate passes. A command finishing is not by
itself a Campaign PASS.

## 6. Exact authorized route

The only authorized launcher invocation is:

```powershell
pwsh -NoProfile -File scripts/Start-PrinterV1-MemoryFactory.ps1 `
  -Mode run `
  -OperatorApproved
```

On macOS/zsh the same command may be entered on one line:

```bash
pwsh -NoProfile -File scripts/Start-PrinterV1-MemoryFactory.ps1 -Mode run -OperatorApproved
```

The launcher must resolve the repository `.venv/bin/python` and invoke:

```text
python -m printer_v1.operator_cli.operational_memory_factory_command run --operator-approved
```

No other mode is authorized. In particular, this authorization excludes:

- `preflight-only` as a substitute for the authorized run;
- `discovery-only`;
- `selective-1h-preflight`;
- `selective-1h-proof`;
- `status` during the live run;
- `cooperative-stop` unless the authorized command itself requires the existing
  safe-stop path;
- `recover-orphan` unless a later independent recovery lane explicitly approves
  it after an abnormal terminal state;
- `report-only` until after terminal closeout and only in a later approved
  read-only review.

## 7. Exact campaign policy

The authorized ordinary policy is:

| Control | Authorized value |
| --- | --- |
| Public mode | `run` |
| Token capacity | exactly `2` |
| Main window | `WINDOW_15M` |
| Main-window duration | `900` seconds |
| Bounded command duration | `1200` seconds |
| Discovery request ceiling | `2` |
| Governed 15m request ceiling | `65` |
| Governed requests per token | `21` |
| Scheduler-row ceiling | `51` |
| Admission-operation ceiling | `45` |
| Storage ceiling | `64 MiB` |
| Failure ceiling | `20` |
| Automatic retries | `0` |
| Selective-1h continuation | `false` |
| Locked windows | `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, `WINDOW_24H` |
| Source owner | `SOURCE_GOVERNOR` |
| Scheduler owner | `CENTRAL_SCHEDULER` |

`WINDOW_5M_MICRO_EVENT` remains support-only and cannot become a main outcome
memory, unlock retrieval, support paper decisions, create positions, or affect
PnL by itself.

## 8. Mandatory fresh pre-run gates

Immediately before the one authorized command, the execution wrapper or operator
must fail closed unless every condition below remains true:

1. current branch is exactly the final-authorization branch;
2. current HEAD is exactly this final-authorization commit;
3. tracked worktree and index are clean;
4. no protected untracked file exists under `src/`, `migrations/`, or `tests/`;
5. migration directory contains exactly 50 canonical SQL files with tip 050;
6. migration 050 blob SHA remains exact;
7. authoritative DB path remains exact;
8. authoritative DB SHA-256, size, and `mtime_ns` remain equal to the authorized
   pre-run identity;
9. authoritative ledger is exact canonical `50/050`;
10. integrity is exactly `ok` and foreign-key violations are zero;
11. stage-scoped ownership schema, indexes, triggers, and constraints remain
    exact;
12. no migration replacement or guard residue exists;
13. no SQLite `-wal`, `-shm`, or `-journal` sidecar exists;
14. no Printer operational process is running;
15. exclusive writer reservation is available;
16. all active campaign, supervision, Scheduler, discovery, factory, and proof
    counts are zero;
17. locked Scheduler jobs are zero;
18. all historical leases remain terminal, released, and without live lock
    files;
19. protected baseline counts still equal the readiness baseline;
20. migration application package and verified backup remain intact;
21. no rollback record exists for the accepted migration application;
22. zero-I/O source preflight remains `READY` with zero issues;
23. Solana RPC configuration remains valid HTTPS and non-placeholder;
24. no secret material is written to authorization or terminal output;
25. Source Governor and Central Scheduler contracts remain exact;
26. ordinary `run` policy constants remain exact;
27. selective-1h continuation remains false;
28. all retrieval and financial capability switches remain false;
29. no prior application marker exists for this campaign authorization;
30. operator approval is explicit in the exact command.

Any mismatch consumes no permission to improvise. Stop and return a precise
blocked result. Do not edit source, repair the DB, switch modes, or run a partial
campaign inside the execution lane.

## 9. One-attempt and no-rerun law

The authorized execution must create an immutable application-started marker
before runtime work begins.

After that marker exists:

- the authorization is consumed;
- the command must never be invoked a second time under this authorization;
- automatic retry is forbidden;
- manual retry is forbidden;
- resume is forbidden;
- automatic restart is forbidden;
- successor creation is forbidden;
- changing providers or endpoints to obtain a different result is forbidden;
- extending the run beyond the authorized duration is forbidden;
- converting a blocked or dirty result into a new attempt is forbidden.

A new attempt after any terminal result requires a new post-run audit, explicit
roadmap decision, fresh readiness evidence, and fresh final authorization.

## 10. Honest terminal outcomes

Authorization does not guarantee:

- provider availability;
- two eligible candidates;
- two completed clean windows;
- clean memory generation;
- favorable token behavior;
- a profitable market opportunity;
- any retrieval or paper decision.

The campaign may honestly terminate because of source failure, rate limit,
insufficient eligible supply, validation failure, dirty evidence, cancellation,
lease uncertainty, or another real first terminal cause.

Such a result is evidence, not permission to rerun. A clean execution can still
produce dirty or no memory. A clean memory can still describe an unfavorable
market outcome. No terminal status may be rewritten into a favorable result.

## 11. Required terminal evidence

The one authorized execution must preserve and report, at minimum:

- exact Git and command provenance;
- authorization and invocation marker identities;
- campaign, configuration, run, cycle, token-slot, and factory identities;
- exact selected mint and pair identities;
- source request, response, and failure accounting;
- governed operation and budget accounting;
- stage-scoped Scheduler ownership rows and terminal transitions;
- lifecycle reservation and cadence evidence;
- window ownership and exact 15m snapshot evidence;
- clean/dirty episode insertion decisions;
- terminal status and first terminal cause;
- durable cleanup completion timestamp;
- durable lease release timestamp;
- absent lease-lock file;
- zero active/orphan residue;
- zero retry, restart, resume, and successor state;
- protected capability-table deltas;
- canonical final report and report hash;
- action-local/owner accounting equality;
- report-only replay eligibility, without running replay in the execution lane.

## 12. Immediate post-run handling

After the command reaches a terminal state:

1. do not run any second application command;
2. preserve stdout, stderr, exit code, campaign report, terminal summary, marker
   files, database identity, and artifact hashes;
3. inspect active residue read-only;
4. confirm cleanup and lease release;
5. record protected table deltas;
6. record the exact authoritative post-run DB hash, size, and `mtime_ns`;
7. copy only the immutable evidence summary requested by the next review;
8. enter the independent post-run closeout/audit lane;
9. do not run report-only replay until that later lane explicitly approves it;
10. do not delete the migration package, verified backup, campaign artifacts, or
    application marker.

If terminal cleanup is incomplete or the lease cannot be proven released, stop.
Do not use `recover-orphan` without a separate recovery authorization.

## 13. Rollback and recovery boundary

This authorization does not pre-authorize database rollback, orphan recovery,
manual row edits, campaign deletion, report rewriting, or artifact replacement.

If the command fails before runtime work and proves zero mutation, the result is
still terminal for this authorization.

If runtime work begins and terminal cleanup is incomplete, preserve the state and
move to an independent recovery audit. The recovery audit must decide whether the
existing exact orphan-recovery path is safe. It may not silently rerun the
campaign.

The pre-050 migration backup is not a campaign rollback tool. Restoring it would
remove accepted migration 050 and is forbidden outside a new schema-recovery
lane.

## 14. Protected baseline

The following readiness counts are pinned as the pre-run comparison baseline:

| Table | Count |
| --- | ---: |
| `printer_memory_windows` | 162 |
| `printer_episodes` | 59 |
| `printer_memory_retrieval_queries` | 10 |
| `printer_memory_retrieval_matches` | 0 |
| `printer_paper_decisions` | 2 |
| `printer_paper_decision_audits` | 0 |
| `printer_paper_positions` | 0 |
| `printer_paper_trade_events` | 0 |
| `printer_paper_trade_audits` | 0 |
| `printer_paper_audit_reports` | 1 |
| `printer_paper_quote_evidence` | 32 |
| `printer_scheduler_jobs` | 1365 |
| `printer_source_requests` | 1748 |
| `printer_source_responses` | 1609 |
| `printer_source_failures` | 139 |

Source and Scheduler counts are expected to change only through the governed
campaign path. Retrieval, decision, position, trade, audit, and PnL capability
surfaces must show zero unauthorized activation. Historical nonzero retrieval,
decision, audit-report, and quote-evidence rows remain historical records and are
not activation.

## 15. Capability locks

This authorization keeps all of the following locked:

- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, and `WINDOW_24H`;
- retrieval and retrieval-match activation;
- dirty-memory retrieval or training;
- paper decisions;
- BUY, SELL, and HOLD;
- paper positions;
- trade events;
- paper trade audits;
- PnL;
- wallets, private keys, signing, real funds, and live execution;
- paid APIs;
- scoring, ranking, confidence, weighting, embeddings, and vectors;
- provider rotation and automatic retry;
- any Source Governor bypass;
- any Central Scheduler bypass;
- V2-10.

The command may generate only the memory evidence allowed by the ordinary
`WINDOW_15M` campaign contract. It cannot use that memory for retrieval or a
paper decision.

## 16. Authorization matrix

| Gate | Result |
| --- | --- |
| Active build-order alignment | PASS |
| Existing design/proof chain | PASS; no repeat required |
| C1-C15 conformance | PASS |
| Migration 050 applied and closed | PASS |
| Post-migration readiness | PASS |
| Authoritative DB health | PASS |
| Stage-scoped ownership schema | PASS |
| Zero active/locked residue | PASS |
| Source configuration structure | PASS |
| Source/Scheduler owner contracts | PASS |
| Ordinary two-token `WINDOW_15M` policy | PASS |
| One attempt / no retry law | REQUIRED |
| Selective-1h mode | NOT AUTHORIZED |
| Retrieval and financial capabilities | LOCKED |
| Campaign executed in this lane | NO |
| Final authorization | PASS |

## 17. Money-usefulness contribution

This authorization permits one bounded attempt to grow trustworthy paper-only
memory after the accounting, terminal-evidence, and Scheduler-ownership repairs.

Its money-usefulness contribution is improved learning evidence: exact source
provenance, stage ownership, lifecycle timing, validation, closeout, and honest
clean/dirty outcomes. It makes no profit claim, creates no signal, and cannot move
money.

## 18. What this lane improves

- converts the post-migration readiness PASS into one exact executable boundary;
- prevents mode drift into discovery-only or selective-1h paths;
- binds the repaired C1-C15 chain to the authoritative 50/050 schema;
- preserves one-attempt/no-rerun safety;
- defines exact pre-run gates and terminal evidence requirements;
- prevents provider failure or dirty memory from becoming a retry loop;
- preserves all retrieval and financial locks;
- separates execution from post-run closeout and recovery.

## 19. What this lane still does not unlock

This PASS does not itself unlock or prove:

- successful provider responses;
- successful candidate discovery or selection;
- clean `WINDOW_15M` memory;
- favorable outcomes or profitability;
- `WINDOW_1H` or later windows;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions, trades, audits, or PnL;
- any live-wallet or real-funds capability.

The campaign remains unexecuted until the operator enters the next bounded
execution lane.

## 20. Proof required after execution

The next action is incomplete until an independent closeout establishes:

1. the command ran once from the exact authorized commit;
2. no second invocation, retry, restart, resume, or successor occurred;
3. the exact ordinary `run` policy was used;
4. source and Scheduler operations stayed within ceilings and owners;
5. stage-scoped ownership evidence is complete and non-contradictory;
6. terminal status and first terminal cause are truthful;
7. cleanup and lease release are durable;
8. no active/orphan residue remains;
9. protected capability deltas remain locked;
10. canonical report acceptance passes or an exact blocker is recorded;
11. database and artifact identities are preserved;
12. no later window, retrieval, decision, or financial path ran.

## 21. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Consequence | Required control |
| --- | --- | --- |
| Provider unavailability or rate limiting | Campaign may terminate before useful memory | Honest first terminal cause; zero retry/rotation |
| Insufficient eligible two-token supply | No complete campaign memory | Accept bounded terminal result; no rerun |
| Dirty or incomplete evidence | Memory cannot be promoted cleanly | Preserve dirty classification and exact blocker |
| Separate selective-1h modes exist in the launcher | Operator could run the wrong capability | Exact launcher mode pinned to `run` only |
| Source config can drift after authorization | Wrong endpoint or placeholder could be used | Fresh zero-I/O preflight and exact DB/config gates |
| DB changes after readiness | Authorization could target a different state | Exact pre-hash, size, mtime, ledger, and baseline equality |
| Existing historical nonzero paper/retrieval rows | Could be mistaken for activation | Compare exact baselines and require zero unauthorized deltas |
| Terminal cleanup uncertainty | Active residue could poison later runs | Durable cleanup/release and absent lock required |
| One failed attempt encourages rerun | Repeated mutation and source spend | Immutable application marker; new lane required |
| Campaign produces clean memory but unfavorable market behavior | Operator may treat clean as profitable | Keep evidence quality separate from outcome favorability |
| Pre-050 backup is misused as campaign rollback | Accepted schema would be lost | Forbid migration backup restoration in campaign lane |
| Final auth commit changes code accidentally | Runtime would differ from reviewed route | Verify commit contains documentation only and recheck code hashes |

## 22. Exact next permitted lane

`V2-9.8B Post-Migration Authoritative WINDOW_15M Campaign Bounded Execution and Immediate Terminal Evidence Capture`

Type: one operator-approved ordinary `run` invocation followed by immediate
evidence preservation and stop.

Allowed:

- the exact launcher command in Section 6;
- governed source fetching through Source Governor;
- Central Scheduler-owned work;
- one two-token `WINDOW_15M` campaign;
- authoritative DB writes required by that campaign;
- allowed `WINDOW_15M` memory generation;
- terminal cleanup and immutable evidence capture.

Not allowed:

- a second invocation or rerun;
- discovery-only or selective-1h modes;
- provider rotation or automatic retry;
- manual DB repair;
- report-only replay during execution;
- `WINDOW_1H` or later windows;
- retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL;
- wallets, signing, private keys, real funds, or live execution.
