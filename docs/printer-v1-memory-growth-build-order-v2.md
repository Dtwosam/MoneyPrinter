# Printer V1 Memory Growth Build Order V2

## 1. Adoption Status

Status: proposed until this document and the matching `AGENTS.md` anchor are
committed and tagged by the operator.

After adoption, this document supersedes
`docs/printer-v1-memory-growth-build-order.md` only for Printer V1 memory-growth
work after V2-0. The old memory-growth build order remains preserved as the
historical X1-X14 era roadmap.

Higher authority remains unchanged:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`

This document does not unlock retrieval, paper decisions, BUY, SELL, HOLD,
paper positions, trade events, paper trade audits, PnL, live execution, wallet
logic, private keys, paid APIs, scoring, ranking, confidence percentages,
weighted logic, embeddings, vectors, or dirty-memory decision support.

The V2 target is:

```text
maximum reliable paper-only learning efficiency under V1 restrictions
```

This is a learning-efficiency target, not a guaranteed-profit claim.

## 2. Why V2 Exists

V2 exists because V2-0 found roadmap drift and a hard 1h blocker:

- The active memory-growth build order still pointed around Lane X1 while repo
  history and operator artifacts reached X13/X14.
- X14 Attempt 3C must be classified as `PARTIAL_READY_WITH_BLOCKER`.
- X14 proved bounded 1h collection safety but not clean 1h memory closeout.
- E2Q currently blocks `WINDOW_1H` because it is still limited to `WINDOW_15M`.
- The one-command memory workflow is fragmented across lane-specific commands,
  manual token lists, proof DB scripts, and run artifacts.
- Discovery/selection is partial and needs a memory-diet upgrade before it feeds
  automated memory growth.
- Printer needs clean, useful memory before retrieval or paper decisions.
- Every major capability needs explicit risk/setback handling so the build does
  not create false readiness, fake confidence, biased memory, dirty memory, or
  fake paper profit.

V2 therefore resets the roadmap around deliberate capability slices:

```text
audit/readiness -> design/specification -> implementation -> bounded proof/test -> closeout report
```

No V2 section is complete merely because code exists.

## 3. Current Reset State

| Area | Reset status |
|---|---|
| V2-0 current-state audit | Complete, audit-only |
| X14 Attempt 3C | `PARTIAL_READY_WITH_BLOCKER` |
| 15m memory | Active, but needs one-command stabilization and corpus quality review |
| 1h memory | Structurally partial, audit-blocked at E2Q |
| 4h/12h/24h | Not operationally approved |
| Discovery/selection | Partial, needs memory-diet upgrade |
| One-command Memory Factory | Fragmented, not ready |
| Retrieval | Locked |
| Paper decisions | Locked |
| BUY/SELL/HOLD | Locked |
| Positions/trades/PnL | Locked |
| Live trading/wallet/private keys/real funds | Out of scope for V1 |

Post-V2-9 update:

- V2-9 is closed PASS at commit `51bcfdb`.
- Attempt 7 produced a real, isolated, bounded `WINDOW_4H` clean memory result.
- No further 4h proof is required before operational readiness review.
- V2-9.7A through V2-9.7E are closed through post-E.47 full-pilot PASS and
  E.48 holder-condition / memory-quality separation PASS.
- V2-9.7F activation readiness is closed PASS:
  `V2_9_7F_ACTIVATION_READINESS_PASS`
  (`docs/printer-v1-v2-9-7f-activation-readiness-closeout.md`).
- V2-9.8A is closed `V2_9_8A_OPERATOR_ACTIVATION_GATE_PASS`.
- The next active memory-growth lane is:

```text
V2-9.8B — Active Bounded Memory Growth Operations
```

Known factual anchors from V2-0:

- Live DB has 15m memory growth evidence, including 30 complete clean
  `WINDOW_15M` episodes and 3 clean memory-window/fingerprint rows.
- The corpus is still small.
- The X14 proof DB has one `WINDOW_1H` row, but it was blocked before valid 1h
  memory closeout or promotion.
- Retrieval matches remain 0.
- Paper positions, trade events, paper trade audits, and PnL remain 0.

## 4. Required V2 Completion Pattern

Verification for each step below follows the Risk-Based Verification Policy in
`AGENTS.md` (minimum sufficient verification for the change's risk level).

Every major V2 capability must pass:

1. Audit/readiness review.
2. Design/specification.
3. Implementation if applicable.
4. Bounded proof/test.
5. Closeout report.
6. Functionality-risk mitigation.
7. Money-usefulness contribution check.
8. Lock-preservation check.

Every major lane and sub-lane must state:

- Goal.
- Allowed.
- Not allowed.
- Likely files/docs.
- Likely DB/tables.
- Tests/checks.
- Proof artifacts.
- Acceptance gate.
- Rollback/stop condition.
- Locks preserved.
- Money-usefulness contribution.
- What this lane improves.
- What this lane still does not unlock.
- `Functionality Risks / Setbacks / Efficiency Blockers`.

Common locks preserved by every V2 lane unless a later operator-approved lane
explicitly changes them:

- No live trading.
- No wallet/private keys.
- No real funds.
- No paid APIs.
- No scoring/ranking/confidence/weighted logic.
- No embeddings/vectors unless explicitly approved later.
- No Source Governor bypass.
- No Central Scheduler bypass.
- No dirty memory in retrieval or decisions.
- No retrieval activation until a later clean retrieval lane.
- No paper decisions until a later conservative decision lane.
- No BUY/SELL/HOLD.
- No positions, trade events, paper trade audits, or PnL.

## 5. Active V2 Lane Order

### V2-1 - Adopt/Reset Memory Growth Build Order

Type: documentation/adoption only.

Goal: make V2 the active memory-growth build order and remove roadmap drift.

Allowed: documentation updates to this file and `AGENTS.md`, diff checks, risky
language scans.

Not allowed: code, migrations, tests that run runtime, source fetching, DB
mutation, memory generation, retrieval, paper decisions, BUY/SELL/HOLD,
positions, trades, audits, PnL.

Likely files/docs: `docs/printer-v1-memory-growth-build-order-v2.md`,
`AGENTS.md`, optional adoption notes.

Likely DB/tables: none.

Tests/checks: documentation diff checks, non-ASCII scan, risky unlock language
scan.

Proof artifacts: V2 build-order doc, AGENTS anchor, operator closeout report.

Acceptance gate: active source-of-truth stack clearly says V2 is the current
memory-growth roadmap after V2-0 and old X1-X14 roadmap is historical.

Rollback/stop condition: any requested change requires implementation, DB
mutation, source fetching, runtime, or financial unlock.

Locks preserved: all common locks.

Money-usefulness contribution: gives Printer a clean roadmap toward useful
paper-only learning without pretending the current corpus is enough.

What this lane improves: source-of-truth clarity and lane sequencing.

What this lane still does not unlock: everything runtime, memory, retrieval,
paper, financial, live, and scoring-related.

Sub-lanes:

| Sub-lane | Goal | Allowed | Not allowed | Likely files/docs | Likely DB/tables | Tests/checks | Proof artifacts | Acceptance gate | Stop condition | Money-usefulness contribution |
|---|---|---|---|---|---|---|---|---|---|---|
| V2-1A | Audit V2-0 findings and source stack | Read docs/artifacts | Runtime/DB writes | V2-0 audit | None | Read-only inspection | Findings list | X14 and drift facts preserved | Facts conflict with source stack | Prevents false roadmap confidence |
| V2-1B | Draft V2 build order | Write doc | Code/migrations | V2 doc | None | Diff review | Draft doc | Required lane pattern present | Missing required sections | Creates controlled future path |
| V2-1C | Update AGENTS anchor | Minimal AGENTS edit | Weaken V1 rules | AGENTS | None | Diff review | Anchor | V2 active after adoption | AGENTS loosens locks | Clarifies next work |
| V2-1D | Documentation verification | Safe scans | Tests/runtime | Docs only | None | `git diff`, `rg` scans | Check output | No risky accidental unlock language | Scan exposes unsafe wording | Keeps operator trust |
| V2-1E | Operator review and closeout | Review/commit/tag if later requested | Implementation | Closeout output | None | Git status | Operator report | Next lane V2-2A clear | Operator rejects V2 | Clean handoff |

#### Functionality Risks / Setbacks / Efficiency Blockers

| Problem | Why it matters | How it could reduce memory quality or money-usefulness | Failure mode | Required mitigation | Proof/test needed | Stop condition |
|---|---|---|---|---|---|---|
| V2 is adopted without preserving V2-0 facts | Roadmap starts from fiction | Repeats failed X14 proof attempts | False readiness | Cite V2-0 and X14 blocker | Doc scan for `PARTIAL_READY_WITH_BLOCKER` | X14 described as clean pass |
| AGENTS anchor weakens locks | Higher authority becomes unsafe | Future lanes may unlock financial paths early | Fake profit/live-risk language | Explicit lock preservation | Risky-language scan | Any unlock appears |
| Lane order jumps to implementation | Skips design and proof | Builds brittle command path | Operator confusion | Required A/B/C/D/E pattern | Lane table present | Missing sub-lane pattern |

### V2-2 - Discovery/Selection Foundation

Goal: prove Printer can discover and select useful learning tokens before those
tokens feed automated memory growth.

Allowed: audit, design, and later repair of discovery/selection buckets, gates,
labels, quotas, and selection reasons.

Active handoff policy adopted after the V2-2 Group A and unassisted-handoff
proofs: Printer uniformly selects from a bounded pool of clean, actively
traded Solana memecoins, then learns from their natural state transitions over
time. The pool is sorted by exact mint/pair identity and uniformly sampled by
a persisted reproducible seed. Existing category quotas remain diagnostic
coverage reports only; they are not active-handoff gates. WATCH_ONLY, D1, and
inactive candidates remain audit evidence and cannot enter active selection.
Deduplication, STNP, cooldown, rotation, provenance, source-quality, liquidity,
and activity gates remain mandatory.

Not allowed: score/rank/confidence/weighted decisions, alpha prediction, direct
BUY logic, retrieval activation, paper decisions, positions, PnL.

Likely files/docs: discovery docs, discovery/selection helper modules,
discovery source channel tests, tracking queue tests, proof reports.

Likely DB/tables: `printer_discovery_candidates`, `printer_tracking_queue`,
`printer_tokens`, `printer_pairs`, source trace tables, proof DB only for
bounded proof.

Tests/checks: fixture discovery outputs, selection bucket coverage, duplicate
guards, source-governed trace checks, tracking-queue handoff checks.

Proof artifacts: bounded discovery/selection report showing token categories,
selection reasons, rejects, and tracking handoff.

Acceptance gate: Printer can select a learning-useful token set without using
scores/ranks/confidence and without winner-only bias.

Rollback/stop condition: discovery becomes alpha, selection hides reasons, or
any selected token bypasses Source Governor/tracking queue.

Locks preserved: all common locks.

Money-usefulness contribution: improves the learning set so clean memory covers
market behavior that can later support realistic paper decisions.

What this lane improves: memory-diet quality before automation.

What this lane still does not unlock: memory generation, retrieval, paper
decisions, BUY/SELL/HOLD, positions, PnL.

Required learning targets:

- winners
- losers
- traps
- dead tokens
- fake pumps
- wick-only pumps
- late-buy traps
- revivals
- liquidity rising
- liquidity falling
- liquidity removed
- volume rising
- volume decaying
- transaction spikes
- transaction decay
- consolidation
- hot pair behavior
- migration behavior
- suspicious safety behavior
- realistic exit behavior
- unrealistic exit behavior
- correct avoids
- wrong avoids
- correct waits
- wrong waits

Sub-lanes:

| Sub-lane | Goal | Allowed | Not allowed | Likely files/docs | Likely DB/tables | Tests/checks | Proof artifacts | Acceptance gate | Stop condition | Money-usefulness contribution |
|---|---|---|---|---|---|---|---|---|---|---|
| V2-2A | Audit current discovery/selection pipeline | Static and DB read-only review | Source fetch/DB write | Discovery docs/code/tests | Read-only source/discovery tables | Read-only counts and code scan | Audit report | Current gaps known | Needs implementation to answer | Avoids building on bad token intake |
| V2-2B | Design memory-diet buckets/quotas/reasons | Design doc/tests plan | Scoring/ranking | Design doc | None | Risk scan | Spec | Buckets are auditable | Score-like language appears | Creates balanced learning diet |
| V2-2C | Implement discovery/selection repairs | Minimal code/tests if approved | BUY/paper/retrieval | Discovery/selection modules | Proof/temp DB only | Unit tests | Test report | Reasons persist to reports | Hidden selection logic | Makes intake usable |
| V2-2D | Bounded discovery/selection proof | Operator-approved bounded proof | Memory generation | Proof scripts/reports | Proof DB source/discovery/tracking rows | Proof checks | Selection proof report | Useful tokens selected safely | Source bypass or bad rows | Proves safe front door |
| V2-2E | Closeout report | Documentation | New implementation | Closeout doc | None | Diff checks | Closeout | Next lane ready | Gaps unresolved | Prevents ambiguous handoff |

#### Functionality Risks / Setbacks / Efficiency Blockers

| Problem | Why it matters | How it could reduce memory quality or money-usefulness | Failure mode | Required mitigation | Proof/test needed | Stop condition |
|---|---|---|---|---|---|---|
| Winner-only bias | Active sources over-represent pumps | Corpus cannot teach avoids/traps/dead tokens | False confidence from winners | Seeded uniform active-pool sampling plus trajectory coverage reporting | Selection and trajectory reports | Repeated observations remain concentrated without visibility |
| Trending-token bias | Boosted/trending feeds are not the whole market | Memory misses quiet decay and failed pumps | Biased paper decisions later | Include WATCH_ONLY/revisit lanes | Proof includes non-trending reasons | Trending source dominates without label |
| Dead-token under-sampling | Dead tokens teach capital protection | WAIT/AVOID lessons remain weak | Corpus overstates opportunity | Dead/stale buckets and archive revisit | Dead-token fixtures | Dead bucket always empty |
| Revival under-sampling | Revivals are distinct from new pumps | Misses delayed continuation/failure lessons | Poor lifecycle memory | Revival label/reason | Revival fixture/proof row | Revival indistinguishable from new |
| Failed-pump under-sampling | Failed pumps teach traps | BUY review later overfits to success | Fake optimism | Observe natural exact-pair trajectories and report failed-pump coverage | Trajectory coverage report | Failed-pump transitions remain unobserved |
| Late-buy trap under-sampling | Core memecoin risk | Entry realism lessons stay weak | Fake chart profit | Late-buy trap reason | Fixture/proof | No trap category |
| Same-token/new-pair drift | Pair drift can pollute memory | Token/pair mixing | Dirty memory or false continuity | Pair identity guard | Pair drift tests | Pair drift unhandled |
| Duplicate token/pair selection | Wastes source budget | Repeated same token dominates corpus | Low diversity | Duplicate guard/cooldown | Duplicate tests | Duplicate accepted as new |
| Stale or malformed source data | Bad intake corrupts tracking | Dirty evidence enters memory path | Bad candidates | Source status/data quality gates | Malformed/stale tests | Stale source accepted clean |
| Weak selection reasons | Operator cannot audit why token was tracked | Confusing proof reports | False readiness | Persist reasons to reports | Reason persistence tests | Report loses reasons |
| WATCH_ONLY/manual override confusion | Wrong lane can feed factory | Unsafe or irrelevant tracking | Operator error | Explicit lane gates | WATCH_ONLY tests | WATCH_ONLY becomes TRACK_FAST silently |
| Token set good for one run but bad for learning | One proof can pass but corpus stays weak | Low money-usefulness | Short-term overfitting | Corpus-bucket report | Multi-run bucket analysis | No long-term learning plan |
| Discovery output does not feed tracking safely | Automation chain breaks | Manual patching persists | Fragile workflow | Tracking queue handoff gate | Handoff tests | Manual token-list patch required |
| Buckets become hidden scoring | Violates V1 | Fake confidence/ranking | Score drift | Categorical labels only | Risky-language scan | Numeric ranking appears |

### V2-3 - One-Command Memory Factory Automation Design

Goal: design the PowerShell-started command path before implementation.

Target flow:

```text
operator starts one command
-> discovery/selection
-> tracking queue
-> scheduler jobs
-> Source Governor calls
-> snapshots
-> WINDOW_15M memory windows
-> clean/dirty audit
-> report
-> safe stop
```

Allowed: architecture/design docs, command contract, backup/proof/live DB safety
rules, stop conditions, source budgets, lock checks, report contract.

Not allowed: implementation, live/proof DB mutation, source fetching, runtime,
retrieval, paper decisions, financial rows.

Likely files/docs: command design doc, Memory Factory docs, source/scheduler
boundary references.

Likely DB/tables: none in design; future paths reference source, scheduler,
tracking, snapshot, and memory tables.

Tests/checks: doc checks and static design validation.

Proof artifacts: design closeout report.

Acceptance gate: an implementer can build V2-4 without inventing runtime shape.

Rollback/stop condition: design requires unsupported timeframes or financial
paths.

Locks preserved: all common locks.

Money-usefulness contribution: turns useful discovery into repeatable 15m memory
growth instead of manual one-off proof scripts.

What this lane improves: operator workflow clarity.

What this lane still does not unlock: runtime execution and DB mutation.

Sub-lanes:

| Sub-lane | Goal | Allowed | Not allowed | Likely files/docs | Likely DB/tables | Tests/checks | Proof artifacts | Acceptance gate | Stop condition | Money-usefulness contribution |
|---|---|---|---|---|---|---|---|---|---|---|
| V2-3A | Audit fragmented commands | Static review | Running commands | CLI docs/source | None | `rg` scans | Audit notes | Current command gaps known | Requires runtime | Reduces operator confusion |
| V2-3B | Design orchestration | Design only | Code | Design doc | None | Review checklist | Spec | End-to-end flow specified | Flow bypasses scheduler/governor | Defines usable factory |
| V2-3C | Define DB safety | Design only | DB writes | Design doc | None | Checklist | DB safety spec | Proof/live boundaries clear | Live write ambiguity | Protects data integrity |
| V2-3D | Define stops/budgets/reports | Design only | Runtime | Design doc | None | Checklist | Report spec | Stops and deltas explicit | Hidden failure paths | Makes runs auditable |
| V2-3E | Closeout design report | Docs | Implementation | Closeout doc | None | Diff checks | Closeout | V2-4 ready | Unresolved design hole | Clean handoff |

#### Functionality Risks / Setbacks / Efficiency Blockers

| Problem | Why it matters | How it could reduce memory quality or money-usefulness | Failure mode | Required mitigation | Proof/test needed | Stop condition |
|---|---|---|---|---|---|---|
| Discovery works but does not feed selection | Pipeline breaks early | Manual candidate picking persists | Operator bias | Selection handoff contract | Handoff design review | Manual patching remains required |
| Selection works but does not feed tracking queue | No automated memory cycle | Useful candidates never become evidence | Lost learning | Queue enqueue contract | Queue design checks | Tracking queue ambiguous |
| Tracking queue works but scheduler jobs wrong | Snapshots not collected on time | Coverage gaps | Dirty memory | Scheduler job mapping | Job kind review | Wrong job kind/timing |
| Scheduler jobs work but source budget fails | Runs die under load | Source failures/dirty rows | Low yield | Budget gate/backoff | Budget model | No budget stop |
| Source Governor bypass | Violates architecture | Dirty/untracked source use | Untrusted evidence | All source calls through governor | Static proof in design | Any direct API path |
| Central Scheduler bypass | Unbounded behavior risk | Hard to stop/audit | Runtime drift | Scheduler-led jobs | Static proof in design | Independent loop |
| One token works but multiple fail | Not scalable memory growth | Weak corpus | Token starvation | Rotation design | Multi-token proof plan | No per-token isolation |
| Proof DB works but live unsafe | Operator cannot trust command | Risky live mutation | Data damage | Explicit DB mode behavior | Proof/live safety tests planned | Live path ambiguous |
| Report does not explain result | Operator cannot act | False success/failure | Confusion | Required report fields | Report contract | Missing deltas/blockers |
| Operator cannot tell clean vs dirty | Dirty memory may be trusted | Fake learning | Dirty leakage | Clean/dirty summary | Report design | Dirty rows hidden |
| Unsupported timeframe touched | Scope creep | 1h/4h premature rows | Fake long memory | `WINDOW_15M only` first target | Risk scan | 1h/4h rows possible |
| Retrieval/paper/financial rows created | Violates locks | False money readiness | Financial drift | Hard row-delta locks | Report contract | Any financial delta |

### V2-4 - One-Command 15m Memory Factory Implementation

Goal: implement the first bounded one-command memory growth path for
`WINDOW_15M` only.

Allowed: minimal orchestration implementation, Source Governor and Central
Scheduler boundary tests, report output, bounded proof DB test.

Not allowed: 1h/4h/12h/24h activation, retrieval, paper decisions, BUY/SELL/HOLD,
positions, trades, audits, PnL.

Likely files/docs: operator CLI command, Memory Factory runner, source/scheduler
boundary tests, report docs.

Likely DB/tables: proof DB source requests/responses/failures, tracking queue,
scheduler jobs, token snapshots, memory windows, episodes/fingerprints.

Tests/checks: unit tests, isolated proof DB tests, row-delta lock checks,
source/scheduler boundary checks.

Proof artifacts: bounded proof DB, command JSON, closeout report.

Acceptance gate: one operator command can safely produce or honestly fail
`WINDOW_15M` memory and stop with zero running jobs and no financial/retrieval
unlock.

Rollback/stop condition: live DB touched unintentionally, dirty memory marked
clean, source failures hidden, scheduler jobs remain running.

Locks preserved: all common locks.

Money-usefulness contribution: creates repeatable 15m memory growth from useful
selected tokens.

What this lane improves: actual automation and reporting.

What this lane still does not unlock: longer windows, retrieval, paper decisions,
BUY/SELL/HOLD, positions, PnL.

Sub-lanes:

| Sub-lane | Goal | Allowed | Not allowed | Likely files/docs | Likely DB/tables | Tests/checks | Proof artifacts | Acceptance gate | Stop condition | Money-usefulness contribution |
|---|---|---|---|---|---|---|---|---|---|---|
| V2-4A | Implement/repair orchestration | Code/tests | Unsupported windows | CLI/runner | Temp/proof DB | Unit tests | Test output | Command path exists | Scope creep | Makes factory usable |
| V2-4B | Test boundaries | Tests | Source bypass | Source/scheduler tests | Temp DB | Boundary tests | Test report | Governor/scheduler enforced | Direct calls | Protects evidence trust |
| V2-4C | Report output | Code/tests | Success masking | Report code/docs | Temp DB | Snapshot/report tests | Example report | Deltas/blockers clear | Report hides failures | Operator can act |
| V2-4D | Bounded proof DB test | Proof only | Live mutation | Proof scripts | Proof DB | Row deltas | Proof JSON | Safe stop, honest memory | Live DB mutated | Validates command |
| V2-4E | Closeout report | Docs | Further implementation | Closeout doc | None | Diff checks | Closeout | V2-5 ready or blocked | Proof unresolved | Clean handoff |

#### Functionality Risks / Setbacks / Efficiency Blockers

| Problem | Why it matters | How it could reduce memory quality or money-usefulness | Failure mode | Required mitigation | Proof/test needed | Stop condition |
|---|---|---|---|---|---|---|
| Snapshots created but windows do not close | No memory grows | Source budget wasted | False progress | Window-close gate tests | Proof creates/blocks windows clearly | No close result |
| Windows close but audit fails | Memory not usable | Dirty unknowns | Low yield | Audit report | Clean/dirty tests | Audit missing |
| Dirty memory marked clean | Corrupts corpus | Bad future retrieval/decisions | Fake readiness | Strict clean gates | Dirty fixture tests | Dirty row clean |
| Clean memory fails to persist | Useful evidence lost | Low yield | Silent failure | Persistence tests | DB row checks | No clean row when gates pass |
| Scheduler jobs remain running | Runtime unsafe | Future jobs blocked | Stale locks | Post-run lock checks | Row-delta checks | Running job after stop |
| Source failures hidden | Operator overtrusts data | Dirty corpus | False success | Failure report fields | Failure fixture | Failure not visible |
| Token/pair mixing | Memory contaminated | Wrong lessons | False matching | Evidence identity isolation | Multi-token tests | Mixed token/pair |
| Pair drift not handled | Same token/pair continuity broken | Dirty/fake memory | Bad evidence | Pair drift gate | Drift fixture | Drift clean-promoted |
| Source budget not enforced | Free-source overload | Failed runs | Rate-limit cascade | Budget/backoff gate | Budget tests | Budget ignored |
| Malformed/stale data becomes memory | Bad data trains corpus | Fake memory | Dirty leak | Data-quality gate | Malformed/stale tests | Stale clean |
| Live DB mutation during proof | Irreversible operator risk | Pollutes live state | Data damage | Proof DB requirement | Path tests | Live DB delta |
| Report hides failure behind success | Operator confusion | False readiness | Bad next lane | Explicit blocker fields | Report tests | Success without blockers |

### V2-5 - Multi-Token 15m Conservative Proof

Goal: prove one-command multi-token 15m memory growth from a bounded proof.

Allowed: conservative proof design, bounded proof DB run, per-token reports,
source budget and pair isolation checks.

Not allowed: 1h/4h/12h/24h, retrieval, paper decisions, BUY/SELL/HOLD,
positions, trades, audits, PnL.

Likely files/docs: proof report, runner tests, token-list/proof artifacts.

Likely DB/tables: proof DB source/snapshot/scheduler/memory tables.

Tests/checks: per-token isolation, source budget, scheduler job status, clean
vs dirty yield, report clarity.

Proof artifacts: proof DB, runner JSON, per-token report, closeout doc.

Acceptance gate: multiple selected tokens can create or honestly fail 15m
windows without token/pair contamination and with all locks preserved.

Rollback/stop condition: source budget exhaustion, token starvation, pair drift
unhandled, false clean memory, financial/retrieval deltas.

Locks preserved: all common locks.

Money-usefulness contribution: moves from one-token anecdotes toward a useful
multi-token corpus.

What this lane improves: scale and per-token memory isolation.

What this lane still does not unlock: longer windows, retrieval, paper decisions,
BUY/SELL/HOLD, positions, PnL.

Sub-lanes:

| Sub-lane | Goal | Allowed | Not allowed | Likely files/docs | Likely DB/tables | Tests/checks | Proof artifacts | Acceptance gate | Stop condition | Money-usefulness contribution |
|---|---|---|---|---|---|---|---|---|---|---|
| V2-5A | Audit caps/budget/isolation | Read-only | Proof run | Runner/docs | Read-only DB | Static/DB checks | Audit notes | Proof limits known | Budget unclear | Avoids overload |
| V2-5B | Design conservative proof | Design | Runtime | Proof plan | None | Review | Plan | Stop gates defined | Unsafe proof shape | Sets safe scale |
| V2-5C | Run bounded proof | Operator-approved proof | Live financial rows | Runner/report | Proof DB | Row deltas | Proof output | Safe run complete | Lock/source breach | Tests real scale |
| V2-5D | Inspect yield/reports | Read-only proof inspection | Mutation | Report doc | Proof DB read-only | Counts | Yield report | Per-token result clear | Ambiguous failures | Shows learning value |
| V2-5E | Closeout | Docs | More proof | Closeout | None | Diff checks | Closeout | V2-6 ready/block known | Open blockers | Clean transition |

#### Functionality Risks / Setbacks / Efficiency Blockers

| Problem | Why it matters | How it could reduce memory quality or money-usefulness | Failure mode | Required mitigation | Proof/test needed | Stop condition |
|---|---|---|---|---|---|---|
| Source budget exhaustion | Multi-token can overload free sources | Low yield/dirty rows | Rate limits | Conservative caps/backoff | Source budget deltas | Budget breach |
| One token starves others | Corpus biased | Missing windows | Unbalanced learning | Rotation fairness | Per-token snapshot counts | Starvation detected |
| Pair/token cross-contamination | Invalid memory | Wrong lessons | Dirty corpus | Evidence identity isolation | Per-token tests | Mixed ids |
| Selected tokens too similar | Poor diversity | Weak retrieval later | Overfit corpus | Memory-diet buckets | Bucket report | All same category |
| Trending winners only | False optimism | Bad future BUY review | Winner bias | Selection quotas | Corpus mix report | Winner-only set |
| No dirty/trap/dead/revival coverage | Missing capital-protection lessons | Money-usefulness weak | Avoid blind spots | Bucket quotas | Proof labels | Buckets absent |
| Scheduler pileup | Runtime unsafe | Stale/running jobs | Stop failure | Running job checks | Post-run status | Running jobs after stop |
| Technical pass but useless corpus | Looks successful but not educational | False readiness | Empty learning value | Money-usefulness report | Corpus report | No actionable lessons |
| Clean yield too low without reason | Cannot improve | Operator stuck | Vague failure | Per-token blockers | Blocker report | Unknown blockers |
| Failure reason not actionable | Cannot repair | Repeated failed proofs | Wasted cycles | Structured failures | Report tests | Missing exact reasons |

### V2-6 - 1h Audit Gate Repair

Goal: inspect and repair/generalize E2Q or create a staged 1h audit gate so valid
`WINDOW_1H` evidence is not blocked only because it is not `WINDOW_15M`.

Allowed: audit E2Q, design safe 1h support, minimal code/tests, closeout report.

Not allowed: fake 1h from 15m, 4h/12h/24h activation, retrieval, paper decisions,
BUY/SELL/HOLD, positions, trades, audits, PnL.

Likely files/docs: E2Q audit code, 1h runner tests, E2Q tests, closeout report.

Likely DB/tables: temp/proof DB in tests; no live DB mutation in implementation.

Tests/checks: 15m unchanged, 5m invalid as main, 1h accepted only with real 1h
evidence identity and source-governed coverage.

Proof artifacts: test output and closeout report.

Acceptance gate: E2Q no longer blocks valid 1h solely because it is not 15m, but
still blocks dirty/incomplete/fake 1h.

Rollback/stop condition: 15m behavior breaks, 5m becomes accepted as main,
dirty/incomplete 1h passes clean, or 4h/12h/24h inherit acceptance.

Locks preserved: all common locks.

Money-usefulness contribution: opens the path to continuation/failure memory,
which is needed for more realistic later paper decisions.

What this lane improves: 1h audit boundary correctness.

What this lane still does not unlock: 1h runtime proof, retrieval, paper
decisions, BUY/SELL/HOLD, positions, PnL.

Sub-lanes:

| Sub-lane | Goal | Allowed | Not allowed | Likely files/docs | Likely DB/tables | Tests/checks | Proof artifacts | Acceptance gate | Stop condition | Money-usefulness contribution |
|---|---|---|---|---|---|---|---|---|---|---|
| V2-6A | Audit E2Q and 15m-only assumptions | Static/test review | Code changes | E2Q/tests | None | `rg`, unit review | Audit notes | Hardcoded gates mapped | Unknown 15m assumptions | Prevents blind loosening |
| V2-6B | Design 1h audit support | Design | Implementation | Design notes | None | Review | Spec | Safe 1h criteria set | Criteria vague | Makes repair safe |
| V2-6C | Implement minimal repair | Code/tests | Runtime proof | E2Q/audit tests | Temp DB only | Unit tests | Test output | 1h gate works in fixture | Scope expands | Enables proof path |
| V2-6D | Test 15m unchanged | Tests | Behavior loosen | 15m tests | Temp DB | Regression tests | Test report | 15m still passes/fails same | 15m regression | Protects current corpus |
| V2-6E | Test 5m invalid as main | Tests | 5m promotion | E2Q tests | Temp DB | 5m block tests | Test report | 5m blocked | 5m accepted | Protects support-only rule |
| V2-6F | Test real 1h identity/coverage | Tests | Fake 1h | 1h tests | Temp DB | Coverage/identity tests | Test report | Only real 1h accepted | Fake 1h passes | Keeps memory honest |
| V2-6G | Closeout | Docs | Proof run | Closeout doc | None | Diff checks | Closeout | V2-7 ready | Open audit gaps | Clean handoff |

#### Functionality Risks / Setbacks / Efficiency Blockers

| Problem | Why it matters | How it could reduce memory quality or money-usefulness | Failure mode | Required mitigation | Proof/test needed | Stop condition |
|---|---|---|---|---|---|---|
| Blindly loosening E2Q | Could accept bad windows | Dirty/fake 1h memory | False readiness | Window-kind-specific criteria | Tests per kind | Generic accept-all |
| Breaking valid 15m audit | Existing memory path regresses | 15m growth stops | Lost foundation | Regression tests | Existing 15m tests | 15m fails unexpectedly |
| Allowing 5m as main | Violates core rule | Micro-event becomes fake memory | Bad retrieval later | Explicit 5m block | 5m tests | 5m accepted |
| Fake 1h aggregation from 15m | Not real 1h evidence | False continuation lesson | Fake long memory | Evidence identity checks | Snapshot range/time tests | 15m-only data accepted |
| Incomplete 1h evidence passes clean | Dirty corpus | Bad future decisions | Weak coverage | Coverage thresholds | Dirty/incomplete tests | Incomplete clean |
| Dirty 1h not blocking | Pollutes retrieval later | Fake confidence | Dirty leak | Dirty gates | Dirty fixture | Dirty clean |
| Source coverage too weak | 1h memory unreliable | Low money-usefulness | Sparse evidence | Source-governed coverage | Coverage tests | Weak coverage accepted |
| Missing fingerprint/episode support | 1h row unusable | No retrieval path later | Dead-end rows | Fingerprint/episode review | Fixture tests | No downstream representation |
| 1h accepted but not useful | Technical pass only | Poor money lessons | Low value corpus | Money-usefulness closeout | Closeout report | No outcome/action lesson |

### V2-7 - Bounded 1h Proof Rerun

Goal: rerun a bounded 1h proof only after V2-6 passes.

Allowed: readiness audit, conservative token selection, proof DB setup, bounded
1h proof, read-only inspection, closeout report.

Not allowed: live DB proof without explicit approval, 4h/12h/24h, retrieval,
paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL.

Likely files/docs: proof runbook, runner output, closeout report.

Likely DB/tables: proof DB source/scheduler/snapshot/memory tables.

Tests/checks: window closeout, source failures, pair drift, locks, clean/dirty
outcome, no financial/retrieval deltas.

Proof artifacts: proof DB, runner JSON, post-run DB report, closeout report.

Acceptance gate: 1h proof creates a valid audited 1h memory result or blocks
honestly for evidence-quality reasons other than the old E2Q 15m-only gate.

Rollback/stop condition: repeats X14 E2Q blocker, source failures hidden, pair
drift unresolved, clean memory over-claimed, financial/retrieval deltas.

Locks preserved: all common locks.

Money-usefulness contribution: validates continuation/failure learning over 1h.

What this lane improves: real 1h operational proof.

What this lane still does not unlock: 4h/12h/24h, retrieval, paper decisions,
BUY/SELL/HOLD, positions, PnL.

Sub-lanes:

| Sub-lane | Goal | Allowed | Not allowed | Likely files/docs | Likely DB/tables | Tests/checks | Proof artifacts | Acceptance gate | Stop condition | Money-usefulness contribution |
|---|---|---|---|---|---|---|---|---|---|---|
| V2-7A | Audit readiness after V2-6 | Read-only | Proof before repair | Readiness doc | Read-only DB | Checks | Readiness report | Repair verified | Repair missing | Avoids repeat failure |
| V2-7B | Select conservative token(s) | Selection review | Discovery automation unless approved | Token list/report | Read-only DB | Selection checks | Token list | Fresh/stable token selected | Stale/drift token | Better proof evidence |
| V2-7C | Run proof DB 1h proof | Bounded proof | Live/financial rows | Runner artifacts | Proof DB | Row deltas | Runner JSON | Proof completes/stops safely | Lock/source breach | Tests 1h runtime |
| V2-7D | Inspect closeout | Read-only proof inspection | Mutation | Closeout report | Proof DB read-only | Counts/locks | DB report | Outcome clear | Ambiguous memory | Shows actual learning |
| V2-7E | Closeout | Docs | More runs | Closeout doc | None | Diff checks | Closeout | Next stage known | Unresolved proof | Clean handoff |

#### Functionality Risks / Setbacks / Efficiency Blockers

| Problem | Why it matters | How it could reduce memory quality or money-usefulness | Failure mode | Required mitigation | Proof/test needed | Stop condition |
|---|---|---|---|---|---|---|
| Proof repeats X14 and blocks again | Shows repair incomplete | Wastes source budget | Same blocker | Preflight E2Q tests | Confirm blocker absent | E2Q 15m-only blocker |
| 1h row but no audit result | Unusable memory | Dead-end evidence | False progress | Audit closeout fields | DB report | No audit status |
| Source failures hidden | Bad evidence | Dirty memory trusted | False success | Failure deltas | Source report | Hidden failure |
| Pair drift after longer run | Token/pair mix | Invalid window | Dirty memory | Pair drift detection | Drift report | Drift not blocked |
| Stale evidence | Weak proof | Dirty/false memory | Bad data | Freshness gate | Freshness fields | Stale accepted clean |
| Clean memory over-claimed | False readiness | Bad retrieval later | Fake corpus | Conservative clean gates | Clean/dirty report | Unsupported clean |
| No money-useful continuation/failure lesson | Technical proof only | Weak corpus | Low learning value | Outcome labels/report | Closeout analysis | No lesson reported |
| No clear next step | Operator stuck | Random future lanes | Drift | Closeout recommendation | Closeout review | Next lane unclear |

### V2-8 - 4h Readiness Review

Goal: design 4h activation only after 1h proof.

Allowed: documentation/readiness review, static code/test audit, proof plan.

Not allowed: real 4h run, source fetching, DB mutation, 12h/24h activation,
retrieval, paper decisions, BUY/SELL/HOLD, positions, PnL.

Likely files/docs: 4h staged modules/tests, readiness doc.

Likely DB/tables: none.

Tests/checks: static inspection and documentation verification.

Proof artifacts: readiness report.

Acceptance gate: 4h evidence requirements, source budget, stop conditions, and
proof plan are explicit.

Rollback/stop condition: 4h plan depends on fake aggregation or unbounded run.

Locks preserved: all common locks.

Money-usefulness contribution: prepares medium-term lifecycle memory without
pretending 1h is solved early.

What this lane improves: long-window readiness clarity.

What this lane still does not unlock: real 4h run or financial/retrieval paths.

Sub-lanes:

| Sub-lane | Goal | Allowed | Not allowed | Likely files/docs | Likely DB/tables | Tests/checks | Proof artifacts | Acceptance gate | Stop condition | Money-usefulness contribution |
|---|---|---|---|---|---|---|---|---|---|---|
| V2-8A | Audit 4h structural code/tests | Static review | Runtime | 4h modules/tests | None | `rg`/read | Audit notes | Gaps known | Runtime needed | Avoids fake readiness |
| V2-8B | Design 4h evidence requirements | Design | Code | Readiness doc | None | Review | Spec | Evidence identity clear | Fake aggregation | Defines valid 4h |
| V2-8C | Design source budget/stops | Design | Source calls | Readiness doc | None | Budget review | Stop plan | Safe budget defined | No stop gates | Controls long run |
| V2-8D | Define proof plan | Design | Proof run | Readiness doc | None | Checklist | Proof plan | Operator can review | Unsafe proof | Prepares real proof |
| V2-8E | Closeout | Docs | Implementation | Closeout | None | Diff checks | Closeout | V2-9 ready/block | Gaps unresolved | Clean handoff |

#### Functionality Risks / Setbacks / Efficiency Blockers

| Problem | Why it matters | How it could reduce memory quality or money-usefulness | Failure mode | Required mitigation | Proof/test needed | Stop condition |
|---|---|---|---|---|---|---|
| 4h source budget too expensive | Free sources may fail | Data gaps | Dirty/failed proof | Budget model | Budget plan | Budget impossible |
| Stale data over long windows | Long windows amplify staleness | Fake continuity | Bad memory | Freshness rules | Freshness design | Stale accepted |
| Fake aggregation from shorter windows | Not real 4h evidence | False lifecycle memory | Fake clean | Evidence identity | Design review | Aggregation-only proof |
| No lifecycle value beyond 1h | 4h may not teach more | Wasted complexity | Low usefulness | Learning goals | Readiness report | No distinct 4h goal |
| Operator cannot monitor safely | Long run risky | Runtime drift | Hidden failure | Stop/report plan | Proof plan review | No stop/report |
| Artifact sprawl | Proof hard to audit | Confusion | Drift | Canonical artifacts | Closeout template | No canonical output |
| Starts before 1h solid | Skips dependency | Repeats blockers | Roadmap drift | Dependency gate | V2-7 closeout | 1h not proven |

### V2-9 - Bounded 4h Proof

Goal: run 4h proof only after V2-8 approval.

Allowed: final preflight, proof DB setup, bounded 4h run, closeout inspection,
proof report.

Not allowed: 12h/24h, retrieval, paper decisions, BUY/SELL/HOLD, positions,
trades, audits, PnL.

Likely files/docs: 4h proof report and runner artifacts.

Likely DB/tables: proof DB source/scheduler/snapshot/memory tables.

Tests/checks: source budget, stale handling, scheduler locks, clean/dirty
outcome, row deltas.

Proof artifacts: proof DB, runner output, closeout report.

Acceptance gate: 4h proof creates valid real 4h memory result or blocks
honestly with all locks preserved.

Rollback/stop condition: source budget exhaustion, stale evidence, hidden
scheduler failures, fake clean promotion.

Locks preserved: all common locks.

Money-usefulness contribution: tests medium-term outcomes after 1h is stable.

What this lane improves: real 4h evidence confidence.

What this lane still does not unlock: 12h/24h, retrieval, paper decisions,
BUY/SELL/HOLD, positions, PnL.

Sub-lanes:

| Sub-lane | Goal | Allowed | Not allowed | Likely files/docs | Likely DB/tables | Tests/checks | Proof artifacts | Acceptance gate | Stop condition | Money-usefulness contribution |
|---|---|---|---|---|---|---|---|---|---|---|
| V2-9A | Final preflight | Read-only checks | Run before approval | Proof checklist | Read-only DB | Preflight | Preflight log | Safe to run | Failed preflight | Protects proof |
| V2-9B | Proof DB setup | Backup/proof copy | Live mutation | Artifact dirs | Proof DB | File checks | Backup/proof paths | Isolated DB ready | No backup | Protects live DB |
| V2-9C | Bounded 4h run | Approved proof | Unbounded run | Runner output | Proof DB | Runtime checks | Runner JSON | Stops safely | Runtime/source breach | Produces evidence |
| V2-9D | Closeout inspection | Read-only proof inspection | Mutation | Report | Proof DB read-only | Counts/locks | DB report | Outcome clear | Hidden failures | Shows value |
| V2-9E | Proof report | Docs | More runs | Closeout doc | None | Diff checks | Report | Next step clear | Ambiguous result | Clean handoff |

#### Functionality Risks / Setbacks / Efficiency Blockers

| Problem | Why it matters | How it could reduce memory quality or money-usefulness | Failure mode | Required mitigation | Proof/test needed | Stop condition |
|---|---|---|---|---|---|---|
| Source budget exhaustion | 4h uses more calls | Data gaps | Dirty proof | Hard budgets | Source deltas | Budget breach |
| Stale evidence | Long proof can decay | Fake memory | Bad corpus | Freshness checks | Freshness report | Stale clean |
| Hidden scheduler failures | Runtime unsafe | Missing windows | False success | Job status report | Scheduler counts | Running/failed hidden |
| Long-window dirty memory | Expected sometimes | Low yield | Overclaim | Honest dirty report | Clean/dirty deltas | Dirty hidden |
| Fake clean promotion | Corrupts corpus | Bad future retrieval | False confidence | Strict gates | Dirty fixture/regression | Unsupported clean |
| No lifecycle lesson | Technical pass only | Low usefulness | Weak memory | Outcome labels | Closeout analysis | No lesson |
| Insufficient token diversity | 4h proof too narrow | Overfit | Weak corpus | Token selection criteria | Proof report | All same category |
| Operator interruption risk | Long run fragile | Partial data | Confusion | Safe stop behavior | Stop proof | Cannot stop cleanly |

### V2-9.7 - Operational Memory Factory Activation Program

Goal: prepare and implement the operational Memory Factory only after V2-9 has
closed PASS, without starting operational memory growth during the adoption or
readiness-audit lanes.

Status: V2-9.7A through V2-9.7F and V2-9.8A are closed PASS. V2-9.8A is
`V2_9_8A_OPERATOR_ACTIVATION_GATE_PASS`. The next active memory-growth lane is:

```text
V2-9.8B — Active Bounded Memory Growth Operations
```

At V2-9.7 closeout, the operational command was published but had not yet run.
That historical status is superseded by the later V2-9.8B first authoritative
WINDOW_15M campaign attempt, forensic audit, and accounting/exact-identity
repair documented below. Retrieval and financial capabilities remain locked.

Historical allowed work inside V2-9.7 (now complete): audit, targeted repair of
proven operational blockers, campaign design, bounded implementation, two-token
pilot proof, and activation closeout in the lane order below.

Not allowed before/without V2-9.8A: active memory-growth operations, V2-10,
12h/24h work, retrieval activation, paper decisions, BUY/SELL/HOLD, positions,
trades, paper trade audits, PnL, live execution, wallet/private-key/signing
logic, paid APIs, scoring, ranking, confidence percentages, weighted logic,
embeddings, vectors, unbounded runtime, or automatic restart after terminal
failure.

Final factory target flow:

```text
discovery
-> selection
-> tracking
-> governed collection
-> conditional WINDOW_5M_MICRO_EVENT support
-> main WINDOW_15M closeout
-> selective WINDOW_1H continuation
-> conditional WINDOW_4H continuation
-> clean/dirty/blocked audit
-> cooldown/archive
-> candidate rotation
-> persistent corpus reporting
-> safe stop
```

Selective continuation is mandatory. Printer must not track every timeframe for
every token. Continuation to 1h or 4h must depend on evidence quality, learning
value, source budget, token/pair continuity, and operator-approved campaign
policy.

`WINDOW_5M_MICRO_EVENT` remains support-only. It may be conditionally captured
for early pumps, dumps, wicks, traps, and exit realism, but it must be
exact-linked to the token, pair, run, and main 15m lifecycle; remain
Source-Governed and Scheduler-led; never become a main outcome memory; never
replace 15m; never independently trigger continuation; stay excluded from main
clean-memory thresholds; and never unlock retrieval or financial capabilities.

Known V2-9 carry-forward observations:

- clean-promotion reporting under-count;
- timeframe-confusing safety labels;
- transient heartbeat lock-file contention;
- partial wallet-level flow authenticity;
- missing embedded Git provenance;
- no separate live report-only replay.

Sub-lanes:

| Sub-lane | Goal | Allowed | Not allowed | Likely files/docs | Likely DB/tables | Tests/checks | Proof artifacts | Acceptance gate | Stop condition | Money-usefulness contribution |
|---|---|---|---|---|---|---|---|---|---|---|
| V2-9.7A | Operational Memory Factory Readiness Audit | Static/read-only audit of discovery, selection, tracking, scheduler, Source Governor, continuation gates, cooldown/archive, rotation, reporting, persistent DB safety, and V2-9 carry-forward observations | Code, DB writes, source fetching, runtime, operational command, V2-10, retrieval, paper/financial rows | Active docs, CLI/source/tests, read-only DB/report surfaces | Read-only only | Static inspection, accidental-unlock scan | Readiness audit closeout | Proven blockers and implementation scope are known | Needs mutation or runtime to answer | Prevents operational growth on a false-ready factory |
| V2-9.7B | Repair only proven discovery/operational blockers | Minimal targeted repairs after V2-9.7A proves blockers | Broad refactor, new financial paths, unproven wishlist repairs | Discovery/selection/tracking/scheduler/report modules as proven by A | Temp/proof DB only if tests need it | Focused tests and regressions | Repair closeout | Proven blockers fixed without lock drift | Repair requires retrieval/financial unlock | Makes the factory operationally safe enough to design campaigns |
| V2-9.7C | Multi-timeframe campaign design | Design only for 15m main, selective 1h, conditional 4h, lifecycle-wide conditional 5m support, full-trajectory memory, checkpoint construction, realistic action paths, cooldown/archive, rotation, persistent reporting, stop policy | Runtime/source fetch/DB writes, retrieval/paper/financial activation | Campaign design doc, command contract | None | Static design checks including anti-look-ahead, 5m non-authority, and lock scans | Campaign design closeout | Implementer can build without inventing policy or trajectory semantics | Design implies all-timeframe tracking, auto restart, nominal-price matching, look-ahead, or 5m authority | Turns proven 4h capability into controlled corpus growth policy |
| V2-9.7D | Bounded implementation | Implement the committed operational command and reports | Running operational campaign, proof before approval, retrieval/paper/financial rows | CLI/runner/report/tests | Temp/proof DB for tests only | Targeted tests, no-unlock checks | Implementation closeout | Command exists but is not operated | Command can bypass governor/scheduler or auto-restart | Creates the tool needed for bounded real corpus growth |
| V2-9.7E | Two-token pilot proof | Bounded two-token pilot against approved target with exact report and safe stop | Scaling to 3 tokens, unbounded campaign, V2-10, retrieval/paper/financial rows | Runner artifacts, pilot report | Approved target DB per lane scope | Source/scheduler/memory/lock deltas | Pilot proof closeout | Two-token pilot passes or blocks honestly | Token mixing, dirty clean promotion, unsafe stop | Proves initial operational memory growth can work without fake corpus claims |
| V2-9.7F | Activation closeout | Decide whether V2-9.8A activation gate is ready | Starting operation, issuing command early | Closeout doc | None | Diff checks, unlock scan | Activation closeout | V2-9.8A is ready or explicitly blocked | Pilot unresolved or command unverified | Clean handoff to active bounded operations |

Required V2-9.7C source stack additions:

- `docs/printer-v1-v2-9-7c-0-money-usefulness-requirements-readiness-audit.md`
- `docs/printer-v1-manipulation-aware-money-usefulness-product-law.md`
- `docs/solana-builder-source-of-truth/solana-agent-assistance-policy.md`
- `docs/solana-builder-source-of-truth/official-solana-agent-resources.md`

The official Solana MCP connection is optional and is not required for
V2-9.7C design. A custom Printer MCP remains deferred. Before V2-9.7D
implementation relies on affected evidence, Printer still requires a Jupiter
route-and-quote provider contract, GoPlus and GeckoTerminal provider contracts,
and public-RPC limit consolidation. A wallet and participant evidence source
audit remains required before paper-decision readiness.

V2-9.7C must trace all 19 canonical requirements from the V2-9.7C.0 audit:
campaign model; selective continuation; fairness and budgets; conditional 5m
support; trajectory and checkpoints; cooldown/archive/rotation; recovery and
replay; reporting and supervision; Source-Governed evidence isolation;
transition memory; manipulation-aware opportunity; wallet and participant
evidence; event-time execution memory; multiple checkpoint decision paths;
contradiction memory; balanced corpus coverage; recency and market-drift
handling; frozen chronological validation; and optional operator capital policy
with permanent safety invariants.

V2-9.7C must also preserve the manipulation-aware and money-usefulness product
laws by reference. The design must require:

- four-way separation between evidence quality, market-integrity condition,
  tradeability, and action eligibility
- manipulation lifecycle coverage
- all eight manipulation behaviours named in the law document
- two separate outcome layers: full-window outcome and internal
  trade-opportunity outcome
- all twelve tradeable-path contexts named in the law document
- hard blocks for missing mandatory evidence, unsafe evidence, unsupported
  execution realism, unproven capturability, look-ahead, and any capability lock
- anti-hindsight and checkpoint-time-only evidence boundaries
- chronological-validation controls for later frozen-corpus proof lanes
- optional capital-policy rules that can never disable permanent Printer safety
  invariants

#### Money-Usefulness Contribution

V2-9.7 converts the successful one-token 4h proof into a disciplined operational
program for growing a larger, more diverse, persistent clean-memory corpus. It
keeps the work focused on evidence quality, selective continuation, realistic
entry/exit evidence, negative outcomes, traps, round trips, and dirty/blocked
honesty instead of raw row counts or profit claims.

#### What This Program Improves

- Moves from isolated proof success toward bounded persistent corpus growth.
- Makes discovery, selection, tracking, cooldown/archive, and rotation part of
  the same audited factory path.
- Preserves bounded continuation under the post-DTW100 amendment: every
  otherwise-valid activated token is observed through the 4h checkpoint, while
  hard evidence/identity/safety/continuity/resource gates remain fail-closed and
  12h/24h continuation remains selective and separately locked.
- Carries V2-9 reporting/safety/supervision/provenance observations into the
  next readiness audit instead of burying them.
- Requires persistent corpus reporting before operational activation.

#### What Remains Locked

Operational memory growth, V2-10, 12h/24h, retrieval activation, paper decisions,
BUY/SELL/HOLD, paper positions, trade events, paper trade audits, PnL, live
execution, wallet/private-key/signing logic, paid APIs, scoring, ranking,
confidence percentages, weighted logic, embeddings, vectors, unbounded runtime,
auto-restart after terminal failure, dirty-memory retrieval, and 5m main outcome
memory remain locked.

#### Proof Required

- V2-9.7A read-only readiness audit.
- Focused repairs only for blockers proven in V2-9.7A.
- Static campaign design closeout.
- Bounded implementation tests and no-unlock checks.
- Two-token pilot proof with safe stop and exact deltas.
- Activation closeout before any V2-9.8 operation.

V2-9.7C cannot pass unless its design specifies:

- traceability from every one of the 19 canonical requirements to a concrete
  design element
- full-trajectory memory representation
- phase and reversal representation using approved categorical vocabulary
- historical decision-checkpoint construction
- strict anti-look-ahead boundaries
- realistic action-path evaluation
- continuous scheduled/event checkpoint review
- re-entry and separate-trade semantics
- observed peak versus capturable exit separation
- lifecycle-wide conditional 5m trigger categories
- exact 5m parent linkage to campaign, run, token, pair, root 15m lifecycle,
  containing main window, triggering snapshots, source provenance, and scheduler
  work
- 5m non-authority controls
- four-way separation of evidence quality, market-integrity condition,
  tradeability, and action eligibility
- manipulation lifecycle and all eight manipulation behaviours from
  `docs/printer-v1-manipulation-aware-money-usefulness-product-law.md`
- separate full-window and internal trade-opportunity outcome layers
- all twelve tradeable-path contexts from the law document
- hard-block, anti-hindsight, chronological-validation, and optional
  capital-policy contracts
- minimum sufficient proof requirements

V2-9.7C remains design-only unless the active build order explicitly says
otherwise.

#### Functionality Risks / Setbacks / Efficiency Blockers

| Problem | Why it matters | How it could reduce memory quality or money-usefulness | Failure mode | Required mitigation | Proof/test needed | Stop condition |
|---|---|---|---|---|---|---|
| Starting operations before readiness audit | False operational confidence | Pollutes persistent corpus | Dirty rows or hidden failures | V2-9.7A first | Audit closeout | Runtime requested during A |
| All-timeframe tracking | Wastes source budget | Fewer useful clean memories | Gaps and stale evidence | Selective continuation gates | Campaign tests/report | Every token gets every timeframe |
| 5m support becomes a trigger | Violates support-only rule | Fake early-signal memory | 5m drives continuation or retrieval | Exact 15m linkage and exclusions | 5m exclusion tests | 5m acts as main evidence |
| Trajectory over-segmentation | Invented phases imply false precision | Dirty lessons look clean | Dynamic labels or excessive splits | Approved categorical phase vocabulary | Design scan and fixture plan | Labels invented at runtime |
| False reversal labeling | Misreads noise as learning value | Bad entry/exit lessons | Reversal count/order unreliable | Snapshot coverage and evidence thresholds | Trajectory proof fixtures | Unsupported reversal becomes known |
| Snapshot gaps | Path is incomplete | Fake continuity and fake exits | Hidden gap crosses peak or reversal | Gap-visible trajectory reporting | Cadence/gap tests | Gaps hidden in clean memory |
| Wick-only observed peaks | Chart peak mistaken for tradable exit | Fake profit | Peak counted as capturable | Separate observed peak from capturable exit | Exit-realism fixtures | Perfect-top exit assumed |
| Nominal-price matching | Cross-token prices are meaningless | Bad BUY imitation | Price X causes action | Condition-based comparison only | Static decision-policy scan | Nominal price used alone |
| Future-data leakage | Later outcome justifies earlier action | Look-ahead memory | Recovery/close supports past action | Checkpoint evidence boundary | Anti-look-ahead fixtures | Later facts enter checkpoint |
| Excessive checkpoint frequency | Source budget drain | Fewer complete memories | Every tick becomes checkpoint | Scheduled/event checkpoint limits | Budget/design tests | Unbounded checkpoint loop |
| Re-entry churn | Repeated low-quality trades | Overfit and noisy audits | Re-entry without fresh setup | Closed prior position and new comparison | Re-entry design fixtures | Re-entry skips requirements |
| Unconditional 5m capture | Support evidence becomes mandatory drain | Source budget waste | 5m for every token/window | Conditional trigger categories | Positive/negative capture tests | 5m always captured |
| 5m accidental main outcome | Violates product law | Fake clean threshold | 5m counted as main memory | Main-window filters | 5m exclusion tests | 5m counts toward main clean yield |
| Missing event-time execution evidence | Exit realism unproved | Fake paper profit | Chart opportunity treated as route | Quote/route/liquidity proof | Exit-realism tests | Capturable exit claimed without evidence |
| Unavailable wallet-level authenticity | Flow can be overclaimed | Bad authenticity lesson | Partial/caution flow labels | Flow report checks | Wallet authenticity claimed |
| Discovery/selection bias | Corpus overfits to active winners | Weak avoid/trap/dead lessons | Winner-only corpus | Memory-diet and rotation reports | Diversity report | Concentration hidden |
| Cooldown/archive missing | Same tokens dominate | Low diversity and stale lessons | Repeated same-pair loops | Lifecycle transitions | Rotation proof | No post-window transition |
| Persistent DB safety unclear | Production corpus risk | Hard-to-recover pollution | Wrong DB/path or unbounded writes | Explicit target and backups | Preflight/report checks | DB target ambiguous |
| Report under-count remains | Operator under-trusts or misreads yield | Bad go/no-go decisions | Clean promotion hidden | Repair or explicit reconciliation | Report tests | Episode/window counts conflict without explanation |
| Safety label confusion persists | Timeframe policy unclear | False block or false clean | Wrong safety interpretation | Label/policy repair if proven | Safety report tests | Label contradicts gate |
| Heartbeat contention recurs | Long run may lose supervision | Unclear terminal state | Expired lease | Durable renewal handling | Supervision tests/proof | Lease expires |
| Partial flow overclaim | Flow authenticity overstated | Bad money lessons | Wallet-level claims without data | Explicit partial/caution reporting | Flow report checks | Report claims wallet authenticity |
| Missing Git provenance | Harder audit | Poor reproducibility | Unknown code state | Embed HEAD/status in artifacts | Artifact tests | Provenance absent at operation |
| No live replay | Idempotency less visible | Duplicate-risk uncertainty | Replay assumptions unproved | Replay/report-only plan if safe | Replay checks | Duplicate rows or replay mutation |

### V2-9.8 - Active Bounded Memory Growth Campaigns

Goal: operate bounded, persistent Memory Factory campaigns only after V2-9.7
passes and the operator activates the gate.

Status: V2-9.7F passed (`V2_9_7F_ACTIVATION_READINESS_PASS`). Historical
V2-9.8 program note — not current next-lane authority: active bounded campaigns
remained locked until the later closed V2-9.8A operator activation. This is real
persistent corpus production, not design, fixtures, implementation-only work,
or a one-off proof. Current next-lane authority is the 2026-08-26 source-stack
adoption / post-synchronization fresh next-bounded-campaign authorization
readiness/governance lane.

#### V2-9.8A — Operator Activation Gate — HISTORICAL

Historical V2-9.8A operator-activation instruction — preserved for provenance,
not current execution authority.

Status at the closed V2-9.8A gate: before any then-authorized active bounded
memory-growth campaign, the assistant had to say exactly:

```text
This is the time for us to send a command to PowerShell and start growing
Printer's real quality memory.
```

That may have happened only after V2-9.7 passed. At that closed gate, the
assistant had to provide the exact verified PowerShell command from the
committed implementation. The command had to contain no placeholders; target the
authoritative persistent corpus DB; not use a proof DB or the V2-9 proof
launcher; run bounded automatic cycles; use Source Governor and Central
Scheduler; perform discovery through reporting and safe shutdown; never
automatically restart after terminal failure; and preserve all retrieval and
financial locks.

Current command/launch authority is not created by this historical V2-9.8A text
or by the 2026-08-26 four-token standard-4h source-stack adoption. Any live
operational command may be provided only under a later fresh exact-HEAD
authorization lane after required post-synchronization readiness/governance,
with separate explicit operator approval. No existing or consumed authorization
may be reused.

#### V2-9.8B - Active Bounded Memory Growth Operations

##### Operational Factory Active-Path Restoration (2026-07-29)

The active restoration design is:

`docs/printer-v1-v2-9-8b-operational-factory-active-path-restoration.md`.

The exact selected implementation checkpoint is
`7c38f13816169c69697ed19893b7e12802d9b1b7`. It is the latest code checkpoint
before the candidate-acquisition overhaul entered the active operational
critical path at `219ad8125a75f52686bfbf5953be0fa4cdca4712`.

The active route is the proven two-token operational
discovery/selection/tracking handoff plus the independent later supervision,
provenance, replay, reporting, holder/evidence-quality, persistence,
database-mode, heartbeat and lock repairs. Ordinary `run` remains
`WINDOW_15M` only and supports the current migration ledger through 049.

Candidate-acquisition foundation, N2/N7, live acquisition transport, global
Pump cursor, cursor recovery and migration-observation admission are
deferred/experimental. Their implementation, tables, migrations and evidence
remain preserved and importable, but they are not an operational prerequisite
and their cursors/recovery rows are not active factory authority.

This restoration is offline-only. Historical restoration checkpoint — preserved
for provenance, not current next-lane authority: on restoration PASS, the exact
next permitted task was operator review of the restoration branch and closeout.
It did not authorize the published operational command, a live campaign,
provider/RPC work, N2, N7, recovery, cursor reset, a retry, retrieval or any
financial capability. Current next-lane authority is the 2026-08-26 source-stack
adoption / post-synchronization fresh next-bounded-campaign authorization
readiness/governance lane.

##### Historical Candidate-Acquisition Foundation Adoption (Deferred)

The documentation-only adoption verdict is
`V2_9_8B_CANDIDATE_ACQUISITION_FOUNDATION_ROADMAP_ADOPTION_PASS` at
`docs/printer-v1-v2-9-8b-candidate-acquisition-foundation-roadmap-adoption.md`.
It adopts this factory-wide authority order:

1. direct Pump on-chain activity for exact launch origin;
2. direct Pump migration plus exact PumpSwap evidence for graduation and
   canonical pool identity;
3. DexScreener and GeckoTerminal for direct candidate nomination and their
   supported current market, liquidity, activity, age, and coverage facts;
4. approved Solana RPC providers for exact on-chain transport/verification; and
5. PumpPortal only as an optional governed locator after its authentication,
   wallet, free-versus-metered, and cost contract is resolved.

Aggregator observations never replace exact Pump origin or exact joined
Pump-migration/PumpSwap graduation evidence. Candidate acquisition must be one
Source-Governed, Scheduler-led owner with bounded finalized live-tail and
restart-safe cursor-based historical-backfill modes for missed Pump creation and
migration activity. Unknown or unsupported Pump/PumpSwap instructions, events,
accounts, layouts, quote mints, or PDA relationships fail closed and prevent
cursor advancement past the unresolved observation.

The current PumpPortal-led migration locator and lack of an equivalent direct
on-chain migration cursor are a confirmed design gap. Before implementation,
Printer must refresh and pin the official Pump and PumpSwap program contracts,
including exact repository commit, raw-file hashes, program IDs, supported
instruction/event/account layouts, discriminators, account order, Pool account
discriminator and extension policy, PDA/canonical-index rules, quote-mint rules,
indexing strategy, and immutable fixtures.

This adoption does not activate the operational command, live observation,
backfill, implementation, migration, capacity above two, or another selective-1h
proof. The next permitted sub-lane is the read-only **V2-9.8B Direct
Pump/PumpSwap Contract Refresh and Pin Readiness Audit**.

##### Historical Candidate-Acquisition Foundation Clarification (Deferred)

The combined audit/design/implementation/offline-proof lane is complete and
supersedes the prior exclusive-source interpretation. Candidate discovery is
multi-source: direct Pump/PumpSwap, DexScreener, GeckoTerminal, and optional
free Birdeye Standard new-listing nomination. Pump/PumpSwap proof is mandatory
for Pump-specific origin/graduation/canonical-pool claims, not for every token.
Non-Pump and unknown-origin candidates may use the exact-present-pool branch.
DEXTools remains deferred; PumpPortal foundation implementation is prohibited
under its current API-key/wallet contract. No source preference, quota, score,
rank, confidence, or weighting exists.

The foundation and post-foundation integration are capacity-neutral through
N=16 and transport-free offline-proven. Active Memory Factory capacity remains
exactly two. No operational campaign, selective-1h proof, retrieval, or
financial feature is authorized. The foundation mint-identity admission repair
and durable cursor-to-live-range repair are closed PASS. The subsequent
post-cursor-repair live N2 proof is closed
`V2_9_8B_POST_CURSOR_REPAIR_LIVE_N2_PROOF_BLOCKED` after exactly one execution.
It passed explicit `FORWARD` bootstrap and preserved historical `BACKWARD`
heads, then blocked at foundation on `IDENTITY_MERGE_FAILURE` because exact
quote identity was absent for all four candidates; N7 is `NOT_RUN`. The next
Pump migration observation decoupling implementation/offline proof is closed
`V2_9_8B_PUMP_MIGRATION_OBSERVATION_DECOUPLING_IMPLEMENTATION_PASS`. Its
bounded live N2 proof is closed
`V2_9_8B_BOUNDED_LIVE_N2_PUMP_MIGRATION_DECOUPLING_PROOF_BLOCKED` on
`OPERATION_ACCOUNTING_MISMATCH`. The optional-global operation-accounting
repair and offline proof is closed
`V2_9_8B_OPTIONAL_GLOBAL_OPERATION_ACCOUNTING_REPAIR_PASS`. The separately
authorized repaired-boundary live N2 proof is closed
`V2_9_8B_BOUNDED_LIVE_N2_OPTIONAL_GLOBAL_ACCOUNTING_REPAIR_PROOF_BLOCKED`
on honest `OBSERVATION_ROW_CEILING` budget exhaustion after exact
optional-global accounting. The next permitted task is operator review of that
terminal closeout and redacted evidence. No automatic run, retry, recovery,
successor, cursor reset, N7, or operational campaign is authorized.

Restored active-path rules (historical restoration baseline; current envelope
clarified by the 2026-08-26 four-token standard-4h source-stack adoption):

- begin with 2 active tokens;
- concurrent active capacity remains exactly 2; no increase to 3 or 4
  concurrent tokens is authorized;
- later adopted 4/2/2 means two cycles × two concurrent slots and up to four
  distinct token identities across the campaign, not concurrent capacity four;
- use the proven governed discovery/selection/tracking handoff;
- do not require or consume candidate-acquisition N2, N7, cursor or recovery state;
- retain trustworthy positive and negative outcomes as clean when evidence is
  complete;
- keep incomplete, stale, mismatched, or unsupported evidence dirty or blocked;
- report corpus growth, diversity, dirty reasons, source efficiency,
  concentration, continuation yield, rotation, and safe shutdown;
- continue through formal corpus-quality reviews, not raw row-count targets.

Allowed by this restoration lane: offline implementation, frozen-transport
proof and operator review of a PASS branch.

Not allowed: authoritative campaign execution, providers, RPC, N2, N7, cursor
recovery, automatic retry or restart, proof DB runs as a substitute for
production, V2-9 proof launcher, placeholder commands, unbounded campaigns,
retrieval activation, paper decisions, BUY/SELL/HOLD, positions, trades, paper
trade audits, PnL, live execution, wallet/private-key/signing logic, paid APIs,
scoring, ranking, confidence percentages, weighted logic, embeddings, vectors,
or treating row counts as quality.

Likely files/docs: operational run reports and corpus quality closeouts.

Likely DB/tables: disposable current-schema databases only for this restoration;
the authoritative database remains read-only and byte-identical.

Tests/checks: command verification, preflight DB target check, source/scheduler
trace checks, corpus reports, safe-stop report, no-unlock deltas.

Proof artifacts: operational campaign report, corpus quality report, safe-stop
report, lock-preservation report.

Acceptance gate: the current-schema frozen proof restores exactly two-token
selection/handoff and 15m terminal mechanics with safe shutdown, deterministic
replay, no candidate-acquisition cursor/recovery delta, and zero
retrieval/financial deltas.

Rollback/stop condition: wrong DB target, proof launcher use, placeholder
command, Source Governor or Central Scheduler bypass, auto-restart, hidden dirty
reasons, unsafe shutdown, or any retrieval/financial delta.

#### Money-Usefulness Contribution

V2-9.8 is where Printer begins growing real persistent quality memory from more
than one active token. It is intended to increase the diversity and usefulness of
clean 15m/1h/4h lessons while preserving bad outcomes, traps, failed
continuations, realistic exits, and dirty/blocked reasons.

#### What This Program Improves

- Converts the factory from proof readiness to persistent corpus production.
- Makes corpus growth, diversity, source efficiency, continuation yield, and
  rotation visible to the operator.
- Ensures operational campaigns remain bounded and stop safely.
- Keeps quality reviews in charge instead of raw memory-row targets.

#### What Remains Locked

V2-10, 12h/24h, retrieval activation, paper decisions, BUY/SELL/HOLD, paper
positions, trade events, paper trade audits, PnL, live execution,
wallet/private-key/signing logic, paid APIs, scoring, ranking, confidence
percentages, weighted logic, embeddings, vectors, unbounded runtime, proof
launcher operation, and auto-restart remain locked.

#### Proof Required

- V2-9.7 PASS and activation closeout.
- Exact committed PowerShell command with no placeholders.
- Preflight proving authoritative persistent corpus DB target.
- Bounded operation report from discovery through safe shutdown.
- Corpus quality report and no-unlock deltas.

#### Functionality Risks / Setbacks / Efficiency Blockers

| Problem | Why it matters | How it could reduce memory quality or money-usefulness | Failure mode | Required mitigation | Proof/test needed | Stop condition |
|---|---|---|---|---|---|---|
| Wrong command | Could run proof path or wrong DB | No persistent corpus value | Proof DB or launcher used | Exact committed command | Command verification | Placeholder or proof path |
| Persistent corpus pollution | Harder to undo than proof DB | Bad retrieval later | Dirty called clean | Strict audit gates | Corpus report | Unsupported clean row |
| Raw row-count target | Incentivizes weak memory | Low quality corpus | Many dirty/low-value rows | Formal corpus quality reviews | Quality report | Row count used as success |
| Token concentration | Overfits to few pairs | Weak money lessons | Same token dominates | Rotation/concentration reports | Diversity report | Concentration hidden |
| Continuation overuse | Source waste | Stale/gappy long windows | Every token continues | Selective continuation policy | Continuation yield report | No continuation gate |
| Source inefficiency | Free-source limits | More dirty/blocked windows | Budget exhaustion | Source efficiency reporting | Source deltas | Budget breach |
| Unsafe terminal failure | Could restart or keep writing | Confusing corpus state | Auto-restart | No auto-restart rule | Terminal report | Restart after failure |
| Financial drift | Violates V1 | Unsafe fake profit | Paper/financial rows appear | Lock deltas | No-unlock scan | Any forbidden delta |

### V2-10 - 12h/24h Lifecycle Readiness Review

Goal: design long lifecycle memory only after 4h proof.

Allowed: audit, lifecycle learning goals, source budget/stop design, proof plan,
closeout readiness report.

Not allowed: real 12h/24h run, source fetching, DB mutation, retrieval, paper
decisions, BUY/SELL/HOLD, positions, PnL.

Likely files/docs: 12h/24h staged modules/tests, readiness doc.

Likely DB/tables: none.

Tests/checks: static inspection, documentation review.

Proof artifacts: readiness report.

Acceptance gate: long lifecycle proof can be reviewed safely before any run.

Rollback/stop condition: proof design depends on fake long-window aggregation,
unbounded runtime, or impossible source budget.

Locks preserved: all common locks.

Money-usefulness contribution: prepares dead/revival/lifecycle learning.

What this lane improves: long lifecycle planning.

What this lane still does not unlock: actual long-window proof or financial
paths.

Sub-lanes:

| Sub-lane | Goal | Allowed | Not allowed | Likely files/docs | Likely DB/tables | Tests/checks | Proof artifacts | Acceptance gate | Stop condition | Money-usefulness contribution |
|---|---|---|---|---|---|---|---|---|---|---|
| V2-10A | Audit 12h/24h structure | Static review | Runtime | Long-window modules/tests | None | Read-only scans | Audit notes | Gaps known | Runtime needed | Avoids premature proof |
| V2-10B | Define lifecycle goals | Design | Code | Readiness doc | None | Review | Goals | Dead/revival goals clear | No distinct goals | Improves corpus value |
| V2-10C | Define budgets/stops | Design | Source calls | Readiness doc | None | Budget review | Stop plan | Safe limits | No stop path | Controls long run |
| V2-10D | Define proof plan | Design | Proof run | Readiness doc | None | Checklist | Proof plan | Operator can approve | Unsafe plan | Prepares proof |
| V2-10E | Closeout | Docs | Implementation | Closeout | None | Diff checks | Report | V2-11 ready/block | Gaps unresolved | Clean handoff |

#### Functionality Risks / Setbacks / Efficiency Blockers

| Problem | Why it matters | How it could reduce memory quality or money-usefulness | Failure mode | Required mitigation | Proof/test needed | Stop condition |
|---|---|---|---|---|---|---|
| Too much source usage | Long windows stress free sources | Missing/stale data | Dirty proof | Budget caps | Budget plan | Budget impossible |
| Stale or missing context | Long lifecycle needs context | Fake clean memory | Bad corpus | Freshness rules | Readiness review | Stale accepted |
| Token dies before useful evidence | Common memecoin outcome | Could be useful if labeled | Ambiguous dirty | Dead-token policy | Lifecycle plan | Death not represented |
| Fake lifecycle memory | Violates evidence rules | False lessons | Fake confidence | Evidence identity | Design review | Aggregation-only |
| Poor dead/revival coverage | Misses key lessons | Weak money-usefulness | Bias | Selection buckets | Proof plan | No dead/revival plan |
| No operator-safe stop | Long run risk | Artifact/DB confusion | Unsafe runtime | Stop gates | Stop condition review | Stop unclear |
| Proof too long to review cleanly | Operator fatigue | Hidden failures | Bad closeout | Report template | Closeout plan | Report too vague |

### V2-11 - Bounded 12h/24h Lifecycle Proof

Goal: prove long lifecycle memory only after readiness review.

Allowed: final preflight, proof DB setup, bounded lifecycle run, closeout
inspection, proof report.

Not allowed: retrieval, paper decisions, BUY/SELL/HOLD, positions, trades,
audits, PnL, live trading.

Likely files/docs: lifecycle proof report, runner artifacts.

Likely DB/tables: proof DB source/scheduler/snapshot/memory tables.

Tests/checks: source budget, data gaps, pair drift, clean/dirty outcome, report
clarity, row deltas.

Proof artifacts: proof DB, runner JSON, closeout report.

Acceptance gate: 12h/24h proof creates honest lifecycle memory or blocks
cleanly with clear learning value and locks preserved.

Rollback/stop condition: source budget exhaustion, data gaps hidden, fake clean
promotion, unclear lifecycle lesson.

Locks preserved: all common locks.

Money-usefulness contribution: adds lifecycle outcomes such as delayed death,
revival, and longer hold failure.

What this lane improves: long-horizon learning.

What this lane still does not unlock: retrieval, paper decisions, BUY/SELL/HOLD,
positions, PnL.

Sub-lanes:

| Sub-lane | Goal | Allowed | Not allowed | Likely files/docs | Likely DB/tables | Tests/checks | Proof artifacts | Acceptance gate | Stop condition | Money-usefulness contribution |
|---|---|---|---|---|---|---|---|---|---|---|
| V2-11A | Final preflight | Read-only checks | Proof before approval | Checklist | Read-only DB | Preflight | Log | Safe to run | Failed preflight | Protects proof |
| V2-11B | Proof DB setup | Backup/proof copy | Live mutation | Artifact dirs | Proof DB | File checks | Backup/proof paths | Isolated DB ready | No backup | Protects live DB |
| V2-11C | Bounded lifecycle run | Approved proof | Unbounded runtime | Runner output | Proof DB | Runtime checks | Runner JSON | Stops safely | Runtime/source breach | Creates lifecycle evidence |
| V2-11D | Closeout inspection | Read-only | Mutation | Report | Proof DB read-only | Counts/locks | DB report | Outcome clear | Hidden failures | Interprets learning |
| V2-11E | Proof report | Docs | More runs | Closeout doc | None | Diff checks | Report | Next lane clear | Ambiguous result | Clean handoff |

#### Functionality Risks / Setbacks / Efficiency Blockers

| Problem | Why it matters | How it could reduce memory quality or money-usefulness | Failure mode | Required mitigation | Proof/test needed | Stop condition |
|---|---|---|---|---|---|---|
| Source budget exhaustion | Long proof can overload sources | Gaps/dirty rows | Failed run | Strict budget | Source deltas | Budget breach |
| Data gaps | Long windows are fragile | Dirty memory | Low yield | Gap audit | Coverage report | Gaps hidden |
| Token/pair drift | Pairs can migrate over time | Mixed evidence | Bad memory | Drift gates | Pair report | Drift unhandled |
| Lifecycle memory too dirty | May be expected | Low clean yield | Unclear value | Honest dirty labels | Clean/dirty report | Dirty called clean |
| Fake clean promotion | Corrupts future retrieval | False confidence | Bad corpus | Strict gates | Regression tests | Unsupported clean |
| Data but no learning value | Run succeeds technically | Weak money-usefulness | Empty lessons | Outcome analysis | Closeout report | No learning summary |
| Report too vague | Operator cannot decide next | Drift | Bad planning | Required fields | Report review | Missing blockers |

### V2-11.7 - Extend the Operational Factory to Selective 12h/24h Continuation

Goal: after individual 12h/24h readiness and proof lanes pass, extend the
operational factory so selected tokens can continue into 12h and 24h lifecycle
windows.

Allowed: readiness review, design, targeted implementation, bounded tests, and
proof for selective 12h/24h continuation after V2-10 and V2-11 prove the long
lifecycle path.

Not allowed: activating 12h/24h during V2-9.7 or V2-9.8, tracking every token to
12h/24h, fake aggregation from shorter windows, retrieval activation, paper
decisions, BUY/SELL/HOLD, positions, trades, paper trade audits, PnL, live
execution, wallet/private-key/signing logic, paid APIs, scoring, ranking,
confidence percentages, weighted logic, embeddings, or vectors.

Likely files/docs: long-continuation design, factory continuation policy,
reporting docs, tests.

Likely DB/tables: temp/proof DB for tests and approved bounded proofs; later
persistent DB only after activation.

Tests/checks: long-window evidence identity, stale handling, source budget,
pair drift, selective continuation gates, no-unlock deltas.

Proof artifacts: 12h/24h selective continuation proof report and closeout.

Acceptance gate: operational factory can continue only selected tokens into
12h/24h with honest clean/dirty/blocked outcomes and all locks preserved.

Rollback/stop condition: all-token long continuation, fake long-window evidence,
source budget exhaustion hidden, stale clean promotion, or any retrieval/
financial delta.

Money-usefulness contribution: adds delayed dump, revival, liquidity decay,
longer consolidation, death, and full-cycle outcome lessons only for tokens
whose earlier evidence justifies the longer source spend.

What this lane improves: selective long-horizon learning without turning the
factory into an all-timeframe source drain.

What remains locked: retrieval, paper decisions, BUY/SELL/HOLD, positions,
trades, paper trade audits, PnL, live execution, wallet/private-key/signing
logic, paid APIs, scoring/ranking/confidence/weighted logic, embeddings,
vectors, and unbounded campaigns.

Proof required: V2-10/V2-11 PASS, selective continuation design, focused tests,
bounded proof, corpus reporting, and no-unlock deltas.

#### Functionality Risks / Setbacks / Efficiency Blockers

| Problem | Why it matters | How it could reduce memory quality or money-usefulness | Failure mode | Required mitigation | Proof/test needed | Stop condition |
|---|---|---|---|---|---|---|
| Long-window overuse | 12h/24h are source-expensive | Fewer useful memories overall | Every token continues | Strict selection gates | Continuation report | No selectivity |
| Stale evidence | Long windows amplify decay | Fake clean lifecycle | Stale clean row | Freshness gates | Staleness tests | Stale accepted |
| Token/pair drift | Long lifecycles can migrate | Mixed evidence | Wrong pair memory | Pair identity checks | Drift proof | Pair drift unhandled |
| Fake aggregation | Not real 12h/24h memory | False lifecycle lessons | Short windows reused | Evidence identity | Fixture tests | Aggregation-only proof |
| Operator fatigue | Long campaigns are hard to audit | Hidden failures | Vague closeout | Report contract | Closeout review | Missing report fields |

### V2-11.8 - Extended Bounded Multi-Timeframe Campaigns

Goal: after V2-11.7 passes, operate bounded campaigns that include selective
12h/24h continuation as part of the persistent corpus program.

Allowed: bounded persistent campaigns with selected 15m, 1h, 4h, 12h, and 24h
continuations according to approved policy and source budget.

Not allowed: unbounded daemon operation, all-token all-timeframe tracking,
retrieval activation, paper decisions, BUY/SELL/HOLD, positions, trades, paper
trade audits, PnL, live execution, wallet/private-key/signing logic, paid APIs,
scoring, ranking, confidence percentages, weighted logic, embeddings, vectors,
auto-restart after terminal failure, or raw row-count success targets.

Likely files/docs: extended campaign reports and corpus quality reviews.

Likely DB/tables: authoritative persistent corpus DB after approved gate.

Tests/checks: command verification, source/scheduler traces, long-window budget,
corpus quality, concentration, no-unlock deltas, safe shutdown.

Proof artifacts: extended campaign report, long-window corpus quality report,
lock-preservation report.

Acceptance gate: campaign produces or honestly blocks multi-timeframe corpus
memory with clear source efficiency, continuation yield, diversity, dirty
reasons, and safe shutdown.

Rollback/stop condition: source budget breach, hidden dirty reasons,
continuation concentration, unsafe terminal behavior, or any retrieval/financial
delta.

Money-usefulness contribution: grows richer lifecycle memory for survival,
revival, delayed failure, liquidity decay, and full-day outcomes without turning
that data into live trading or paper actions.

What this lane improves: long-horizon corpus diversity and lifecycle realism.

What remains locked: retrieval, paper decisions, BUY/SELL/HOLD, positions,
trades, paper trade audits, PnL, live execution, wallet/private-key/signing
logic, paid APIs, scoring/ranking/confidence/weighted logic, embeddings,
vectors, and unbounded operation.

Proof required: V2-11.7 PASS, exact verified command, bounded campaign report,
long-window corpus quality review, no-unlock deltas, and safe-stop evidence.

#### Functionality Risks / Setbacks / Efficiency Blockers

| Problem | Why it matters | How it could reduce memory quality or money-usefulness | Failure mode | Required mitigation | Proof/test needed | Stop condition |
|---|---|---|---|---|---|---|
| Campaign too broad | Source budget collapses | Dirty/gappy corpus | Too many continuations | Caps and priority policy | Budget report | Budget breach |
| Long-window concentration | Few survivors dominate | Biased lessons | Same token dominates long corpus | Concentration report | Diversity review | Concentration hidden |
| Dirty long windows hidden | False readiness | Bad retrieval later | Dirty called clean | Strict audit and report | Dirty-reason report | Hidden dirty reason |
| Safe stop weak | Long campaigns may straddle failures | Ambiguous DB state | Running/locked jobs after terminal | Stop contract | Shutdown report | Orphaned jobs/locks |
| Row count mistaken for quality | Incentivizes junk corpus | Weak money-usefulness | Quantity target met | Formal corpus reviews | Quality review | Raw count used as pass |

### V2-12 - Memory Corpus Quality Report

Goal: report clean/dirty yield, memory-diet balance, timeframe distribution,
source failures, stale data, and learning coverage.

Allowed: audit, report design, read-only report implementation, report run,
closeout.

Not allowed: retrieval activation, paper decisions, BUY/SELL/HOLD, positions,
trades, audits, PnL, scoring/ranking/confidence.

Likely files/docs: report command/tests/docs.

Likely DB/tables: read-only `printer_memory_windows`, `printer_episodes`,
`printer_memory_fingerprints`, source trace tables, tracking/discovery tables.

Tests/checks: dirty/audit-only exclusion, 5m support-only exclusion as main
memory, source failure visibility, bucket distribution.

Proof artifacts: corpus quality report.

Acceptance gate: operator can see whether the clean memory corpus is diverse and
useful enough for retrieval review.

Rollback/stop condition: report counts dirty/audit-only/5m support rows as main
clean memory or hides source failures.

Locks preserved: all common locks.

Money-usefulness contribution: prevents retrieval/paper review from being based
on a biased or too-small corpus.

What this lane improves: corpus truthfulness.

What this lane still does not unlock: retrieval or decisions.

Sub-lanes:

| Sub-lane | Goal | Allowed | Not allowed | Likely files/docs | Likely DB/tables | Tests/checks | Proof artifacts | Acceptance gate | Stop condition | Money-usefulness contribution |
|---|---|---|---|---|---|---|---|---|---|---|
| V2-12A | Audit corpus tables/reports | Read-only | DB writes | Report docs/code | Read-only DB | Counts | Audit notes | Corpus sources known | Tables ambiguous | Prevents false corpus claims |
| V2-12B | Design report | Design | Runtime | Report spec | None | Review | Spec | Required fields set | Missing dirty/source fields | Makes corpus inspectable |
| V2-12C | Implement read-only report | Code/tests | DB writes | Report command | Read-only DB in tests | Unit tests | Test output | Read-only enforced | Writes rows | Gives operator tool |
| V2-12D | Run report | Read-only command | Mutation | Report output | Read-only DB | Report checks | Corpus report | Corpus quality visible | Report hides risks | Shows readiness |
| V2-12E | Closeout | Docs | Activation | Closeout | None | Diff checks | Closeout | V2-13 ready/block | Corpus insufficient unclear | Clean handoff |

#### Functionality Risks / Setbacks / Efficiency Blockers

| Problem | Why it matters | How it could reduce memory quality or money-usefulness | Failure mode | Required mitigation | Proof/test needed | Stop condition |
|---|---|---|---|---|---|---|
| Report overstates clean memory | False readiness | Bad retrieval review | Fake corpus | Strict clean filters | Report tests | Count mismatch |
| Dirty/audit-only counted useful | Dirty leakage | Bad decisions later | False support | Exclusion filters | Dirty tests | Dirty included |
| 5m support counted main | Violates support-only | Fake main memory | Bad retrieval | Window-kind filters | 5m tests | 5m main count |
| Corpus biased toward winners | Retrieval overfits | Bad money lessons | False optimism | Bucket report | Diversity checks | Winner-only corpus |
| Missing dead/trap/revival | Weak protection | Poor avoids/waits | Blind spots | Memory-diet fields | Coverage report | Key buckets absent |
| Source failures hidden | Data quality false | Dirty confidence | Hidden failures | Failure section | Failure tests | Failures omitted |
| Timeframe coverage overstated | Long-window false readiness | Premature proofs | Drift | Per-timeframe counts | Count tests | 1h/4h overclaimed |
| Report cannot guide retrieval | No actionable next step | Stalled roadmap | Vague output | Recommendation section | Report review | No verdict |

### V2-13 - Clean Retrieval Reactivation Review

Goal: only review whether clean retrieval can be safely reactivated.

Allowed: audit retrieval tables/reports, design clean-only retrieval boundary,
read-only retrieval preview if safe, dirty/audit/5m exclusion checks, closeout.

Not allowed: paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL.

Likely files/docs: retrieval report docs/tests.

Likely DB/tables: read-only memory/retrieval tables unless later approved.

Tests/checks: clean-only retrieval, dirty/audit-only exclusion, 5m main
exclusion, diversity warning, no writes unless explicitly approved.

Proof artifacts: retrieval readiness report.

Acceptance gate: clean retrieval can be trusted not to inflate support using
dirty, audit-only, duplicated, or over-concentrated memory.

Rollback/stop condition: dirty/audit-only memory enters retrieval or output
creates false confidence.

Locks preserved: paper/financial/common locks.

Money-usefulness contribution: prepares evidence comparison for later
conservative decisions.

What this lane improves: clean memory usability.

What this lane still does not unlock: paper decisions or financial actions.

Sub-lanes:

| Sub-lane | Goal | Allowed | Not allowed | Likely files/docs | Likely DB/tables | Tests/checks | Proof artifacts | Acceptance gate | Stop condition | Money-usefulness contribution |
|---|---|---|---|---|---|---|---|---|---|---|
| V2-13A | Audit retrieval tables/reports | Read-only | Activation | Retrieval docs/code | Read-only DB | Counts/static | Audit notes | Existing state known | Writes required | Prevents blind activation |
| V2-13B | Design clean-only boundary | Design | Code | Retrieval spec | None | Review | Spec | Filters explicit | Dirty path unclear | Protects decisions |
| V2-13C | Read-only preview if safe | Preview | Persistent writes | Preview report | Read-only DB | Preview checks | Preview output | No writes | Preview needs mutation | Tests usefulness |
| V2-13D | Verify exclusions | Tests/review | Paper decisions | Retrieval tests | Temp DB | Exclusion tests | Test output | Dirty/5m excluded | Dirty included | Keeps retrieval clean |
| V2-13E | Closeout review | Docs | Activation | Closeout | None | Diff checks | Report | Decision on activation | Risks unresolved | Clean handoff |

#### Functionality Risks / Setbacks / Efficiency Blockers

| Problem | Why it matters | How it could reduce memory quality or money-usefulness | Failure mode | Required mitigation | Proof/test needed | Stop condition |
|---|---|---|---|---|---|---|
| Dirty memory enters retrieval | Violates V1 | Bad future decisions | Dirty support | Clean filters | Dirty tests | Dirty match |
| Audit-only memory enters retrieval | Untrained evidence used | False support | Weak comparison | Audit-only block | Tests | Audit-only match |
| 5m support as main evidence | Violates support-only | Fake main memory | Bad comparison | Window filter | 5m tests | 5m main match |
| Similar but useless memories | Retrieval not money-useful | Bad explanations | Noise | Corpus quality gate | Preview review | No useful rationale |
| False confidence | Retrieval seems stronger than corpus | Over-trust | Bad paper decisions | Diversity/limits wording | Report review | Confidence/ranking appears |
| Corpus lacks diversity | Results not broad | Biased evidence | Overfit | Diversity labels | Corpus report | Dominant token/pair hidden |
| Output cannot explain relevance | Operator cannot audit | Confusion | Vague match | Explanation template | Preview tests | Missing why |

### V2-14 - WAIT/AVOID/NO_ACTION Paper Decision Readiness

Goal: review conservative paper decisions only after retrieval is safe.

Allowed: audit conservative decision requirements, design WAIT/AVOID/NO_ACTION
policy, test decision-blocking on insufficient memory, run review/proof if
approved, closeout report.

Not allowed: BUY/SELL/HOLD unlock, paper positions, trade events, paper trade
audits, PnL.

Likely files/docs: paper decision readiness docs/tests.

Likely DB/tables: temp/proof DB only if approved; no live financial rows.

Tests/checks: insufficient memory creates conservative outcome only, no BUY,
no positions, no PnL.

Proof artifacts: conservative decision readiness report.

Acceptance gate: conservative decisions are evidence-backed, explainable,
non-position, and still locked away from BUY.

Rollback/stop condition: paper decision rows appear before approval, BUY appears,
or retrieval evidence is weak but decision sounds confident.

Locks preserved: BUY/positions/PnL/live/common locks.

Money-usefulness contribution: tests whether Printer can protect capital with
WAIT/AVOID/NO_ACTION before considering BUY.

What this lane improves: conservative paper decision realism.

What this lane still does not unlock: BUY, SELL, HOLD, positions, PnL.

Sub-lanes:

| Sub-lane | Goal | Allowed | Not allowed | Likely files/docs | Likely DB/tables | Tests/checks | Proof artifacts | Acceptance gate | Stop condition | Money-usefulness contribution |
|---|---|---|---|---|---|---|---|---|---|---|
| V2-14A | Audit conservative requirements | Read-only | Decision writes | Decision docs/code | Read-only DB | Static review | Audit notes | Requirements known | BUY path needed | Protects capital logic |
| V2-14B | Design policy | Design | Implementation | Policy doc | None | Review | Spec | WAIT/AVOID/NO_ACTION clear | BUY language | Defines safe decisions |
| V2-14C | Test insufficient memory blocking | Tests | Paper BUY | Tests | Temp DB | Unit tests | Test output | Insufficient memory blocks | BUY created | Prevents over-action |
| V2-14D | Review/proof if approved | Bounded proof | Positions/PnL | Proof report | Proof DB | Row deltas | Proof output | Conservative only | Financial rows | Tests usefulness |
| V2-14E | Closeout | Docs | Further unlock | Closeout | None | Diff checks | Report | V2-15 maybe ready | Risks unresolved | Clean handoff |

#### Functionality Risks / Setbacks / Efficiency Blockers

| Problem | Why it matters | How it could reduce memory quality or money-usefulness | Failure mode | Required mitigation | Proof/test needed | Stop condition |
|---|---|---|---|---|---|---|
| Conservative decision becomes fake trading signal | WAIT/AVOID can be overread | Operator trust issue | False action | Explicit non-position wording | Risk scan | BUY/position implied |
| Insufficient memory still produces action | Violates memory rule | Bad decision | Over-action | Minimum evidence gate | Blocking tests | Action without memory |
| Weak retrieval sounds confident | Creates false confidence | Bad money lessons | Overclaim | No confidence language | Report scan | Confidence/rank wording |
| No clear WAIT/AVOID explanation | Not useful | Cannot learn from decision | Vague decisions | Explanation template | Output tests | Missing rationale |
| Decision not useful for future money-making | No learning value | Paper review weak | Empty decisions | Outcome/audit plan | Closeout review | No learning connection |
| Decision cannot be audited | Bad records | No feedback loop | Weak evidence | Audit fields | Tests | Missing links |
| Paper decision rows appear before approval | Scope violation | Financial lane drift | DB mutation | Approval gate | Row deltas | Unexpected rows |

### V2-15 - Paper BUY Readiness Review

Goal: review BUY preconditions only after clean retrieval and paper realism are
proven.

Allowed: audit BUY prerequisites, define paper BUY policy boundaries, define
entry/exit/liquidity/quote realism requirements, define proof plan, closeout
review.

Not allowed: automatic BUY unlock, live trading, wallet/private keys, real
funds, positions, trade events, paper trade audits, PnL.

Likely files/docs: BUY readiness policy docs, Lane 9/10 references.

Likely DB/tables: none in review.

Tests/checks: risky language scans, no auto-approval language, no score/rank/
confidence thresholds.

Proof artifacts: BUY readiness review.

Acceptance gate: operator has a future BUY review policy that still requires
explicit approval and clean-memory-backed evidence.

Rollback/stop condition: BUY unlock treated as automatic or paper result treated
as real money readiness.

Locks preserved: live trading, wallet/private keys, real funds, positions, PnL
and all common locks until explicit later approval.

Money-usefulness contribution: defines what would be needed before a future
paper BUY review without crossing the line early.

What this lane improves: future BUY discipline.

What this lane still does not unlock: BUY itself, positions, PnL, live trading.

Sub-lanes:

| Sub-lane | Goal | Allowed | Not allowed | Likely files/docs | Likely DB/tables | Tests/checks | Proof artifacts | Acceptance gate | Stop condition | Money-usefulness contribution |
|---|---|---|---|---|---|---|---|---|---|---|
| V2-15A | Audit BUY prerequisites | Docs/read-only | BUY enablement | Lane 9/10 docs | None | Review | Audit notes | Prereqs known | Requires code | Avoids premature BUY |
| V2-15B | Define paper BUY boundaries | Policy | Unlock | Policy doc | None | Risk scan | Spec | Non-approval clear | BUY allowed | Clarifies future |
| V2-15C | Define realism requirements | Policy | PnL | Policy doc | None | Review | Spec | Entry/exit/liquidity clear | Fake profit path | Protects realism |
| V2-15D | Define proof plan | Design | Proof execution | Review doc | None | Checklist | Plan | Later lane scoped | Automatic approval | Sets safe future |
| V2-15E | Closeout review | Docs | Commit unless asked | Closeout | None | Diff checks | Report | Next step clear | Unsafe language | Clean handoff |

#### Functionality Risks / Setbacks / Efficiency Blockers

| Problem | Why it matters | How it could reduce memory quality or money-usefulness | Failure mode | Required mitigation | Proof/test needed | Stop condition |
|---|---|---|---|---|---|---|
| BUY unlock treated as automatic | Huge scope/safety violation | Fake readiness | Premature action | Explicit non-approval | Risk scan | Auto-BUY language |
| Fake chart profit | Core V1 danger | Bad money lessons | Unrealistic PnL | Entry/exit realism | Policy review | Profit without realism |
| No realistic entry | Paper trade impossible | Fake opportunity | Bad decision | Quote/liquidity gates | Review checklist | Entry unknown |
| No realistic exit | Paper profit fake | Bad PnL | Unrealistic exit | Exit realism gates | Review checklist | Exit unknown |
| Liquidity too weak | Trade not realistic | Fake fill | Bad paper result | Liquidity bucket | Review | Liquidity ignored |
| Slippage/price impact ignored | Profit overstated | Fake money | Bad PnL | Quote realism | Review | Slippage absent |
| Decision not backed by clean memory | Violates rules | Bad action | Overfit | Retrieval prereq | Checklist | Weak memory |
| Overfitting to small corpus | Bad generalization | False money-usefulness | Bias | Corpus thresholds | V2-12 report | Corpus too small |
| Paper equals real money belief | V1 boundary breach | Unsafe expectations | Live drift | Paper-only wording | Risk scan | Live readiness language |

## 6. Explicit Non-Goals

V2 does not unlock:

- Live trading.
- Wallet/private keys.
- Real funds.
- Paid APIs.
- Scoring/ranking/confidence/weighted logic.
- Embeddings/vectors.
- Retrieval.
- Paper decisions.
- BUY/SELL/HOLD.
- Positions.
- Trade events.
- Paper trade audits.
- PnL.
- Operational memory growth before V2-9.8A.

## 7. E2Q Repair Boundary

E2Q is currently `WINDOW_15M` only. X14 Attempt 3C showed that the X12 1h runner
can collect 1h evidence and create a `WINDOW_1H` row in a proof DB, but E2Q
blocked the closeout with:

```text
window_kind must be 'WINDOW_15M'; got 'WINDOW_1H'
```

V2-6 must not blindly loosen E2Q. The repair must:

- Preserve all valid 15m behavior.
- Keep `WINDOW_5M_MICRO_EVENT` invalid as a main outcome window.
- Allow `WINDOW_1H` only with real 1h evidence identity and source-governed
  coverage.
- Keep dirty, stale, incomplete, mismatched, or malformed 1h evidence blocked.
- Avoid fake 1h from 15m rows.
- Avoid automatic acceptance of `WINDOW_4H`, `WINDOW_12H`, or `WINDOW_24H`.
- Avoid retrieval/paper/financial unlocks.

## 8. Discovery/Selection Memory-Diet Boundary

Discovery is not alpha. Selection is for learning usefulness, not prediction.

V2 discovery/selection must use:

- Auditable memory buckets.
- Gates.
- Labels.
- Quotas.
- Selection reasons.
- Source trace and tracking-queue handoff.

V2 discovery/selection must not use:

- Scores.
- Ranks.
- Confidence percentages.
- Weighted decisions.
- BUY probability.

The selection set must avoid winner-only memory and include dead tokens, traps,
failed pumps, revivals, liquidity decay, realistic exit evidence, and
unrealistic exit evidence. Selection reasons must survive into proof reports so
the operator can audit why each token was tracked.

## 9. Automation Boundary

After V2-9, the automation target is a PowerShell-started, bounded operational
command, but the exact command must not be provided until V2-9.8A. The target
factory flow is:

```text
discovery
-> selection
-> tracking
-> governed collection
-> conditional WINDOW_5M_MICRO_EVENT support
-> main WINDOW_15M closeout
-> selective WINDOW_1H continuation
-> conditional WINDOW_4H continuation
-> clean/dirty/blocked audit
-> cooldown/archive
-> candidate rotation
-> persistent corpus reporting
-> safe stop
```

The command must move from discovery to reporting and safe shutdown without
manual token-list patching once V2-9.7 passes.

The first operational activation remains bounded and conservative:

```text
2 active tokens first; 3 active tokens only after the two-token pilot passes
```

`WINDOW_5M_MICRO_EVENT` may remain support-only if already approved, but it must
not become a main memory window, replace 15m, independently trigger
continuation, count toward main clean-memory thresholds, or unlock retrieval,
paper decisions, BUY, positions, or PnL.

The command must:

- Stop safely.
- Produce a clear report.
- Use Source Governor for source calls.
- Use Central Scheduler for jobs.
- Preserve source failure visibility.
- Preserve clean/dirty/blocked audit visibility.
- Use the adopted standard first-four-hour lifecycle for otherwise-valid activated tokens; automatic continuation stops at 4h, and later 12h/24h windows remain selective and separately approved.
- Target the authoritative persistent corpus DB only at V2-9.8A or later.
- Never use the V2-9 proof launcher for operational campaigns.
- Never automatically restart after terminal failure.
- Avoid retrieval/paper/financial rows.
## 10. Money-Usefulness Boundary

The user's end goal is money-useful Printer. In V1, money-usefulness means:

1. Paper-only clean memory first.
2. Paper realism second.
3. Audited decisions third.

Live trading is never V1.

Paper BUY can only come after clean retrieval and conservative paper-decision
readiness, and only through a later explicit operator-approved lane.

Every V2 lane must explain how it improves future money-usefulness without
pretending to guarantee profit. A lane that creates code but does not improve
learning quality, evidence quality, report clarity, or lock safety is not done.

## 11. V2-1 Acceptance Checklist

- [x] V2-0 findings preserved.
- [x] X14 classified as `PARTIAL_READY_WITH_BLOCKER`.
- [x] Old memory-growth build order preserved as historical.
- [x] V2 build order created.
- [x] AGENTS anchor update required.
- [x] Every major capability follows audit/design/implementation/proof/closeout.
- [x] Discovery/Selection Foundation comes before one-command implementation.
- [x] First automation target is `WINDOW_15M only`.
- [x] E2Q repair is placed before any more 1h proof attempts.
- [x] 4h/12h/24h remain later.
- [x] Retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, and
  PnL remain locked.

## 12. Next Recommended Lane

V2-9.7A through V2-9.7F and V2-9.8A are closed. V2-9.8A verdict is
`V2_9_8A_OPERATOR_ACTIVATION_GATE_PASS`. V2-9.8B remains the active
bounded operational Memory Factory lane.

### Current adopted operational envelope (2026-08-26)

Canonical adoption:

`docs/printer-v1-v2-9-8b-four-token-standard-4h-source-stack-adoption.md`

Adopted authority family:

- `V2-9.8B-FOUR-TOKEN-STANDARD-4H-OPERATIONAL-V1`
- public mode family: `four-token-standard-four-hour-run`

Exact capacity semantics:

- two cycles;
- exactly two concurrently active token slots;
- up to four distinct token identities across the full two-cycle campaign;
- "four-token" does **not** mean concurrent capacity four;
- concurrent capacity remains exactly `2`;
- no capacity increase to 3 or 4 concurrent tokens is authorized.

Standard observation lifecycle:

```text
WINDOW_15M
-> hard-gated WINDOW_1H
-> hard-gated WINDOW_4H
-> stop
```

`WINDOW_12H` and `WINDOW_24H` remain locked. `WINDOW_5M_MICRO_EVENT` remains
support-only.

Cycle-2 fresh-slot identity must be campaign-history disjoint from all earlier
admitted cycles. Historical identities may appear in discovery diagnostics but
cannot consume later-cycle fresh slots.

Candidate-acquisition foundation / N2 / N7 / global Pump cursor/recovery remain
preserved but deferred and are not an operational prerequisite unless a later
explicit source-stack lane reactivates them.

Implemented capability ≠ previously exercised capability ≠ authorization to run
now. This adoption creates no authorization and unlocks no campaign.

The exact current next permitted lane is:

```text
POST-REPAIR FRESH NEXT-BOUNDED-CAMPAIGN AUTHORIZATION
READINESS / GOVERNANCE ONLY
```

Historical at the time of the 2026-08-26 source-stack synchronization:
`POST-SYNCHRONIZATION FRESH NEXT-BOUNDED-CAMPAIGN AUTHORIZATION READINESS /
GOVERNANCE ONLY`. That pointer is superseded by the later Cycle-1
historical-disjointness repair closeout and `CURRENT_HANDOFF.md`.

A future operational campaign still requires separate fresh exact-HEAD
authorization, explicit operator approval, exact DB binding, Source Governor,
Central Scheduler, one-shot semantics, consumed-authorization non-reuse, and no
automatic retry/resume/restart/successor. Source scarcity and honest evidence
blockers remain valid terminals. The profile does not promise 4/2/2 success.

Retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, and PnL
remain locked.

Assistant active anchor:
`docs/printer-v1-assistant-active-build-order-anchor.md`

### Historical next-lane pointers (preserved; superseded for current authority)

##### Accounting / exact-identity report-only checkpoint — HISTORICAL

The accounting and exact-identity report-only repair is closed:

- design baseline `e71e543d197154eba427b41e2e01574a59f527f5`
- implementation commits `b168c57`, `fd35b41`, `0118a37`
- closeout:
  `docs/printer-v1-v2-9-8b-accounting-exact-identity-report-only-repair-closeout.md`

At that checkpoint the exact next permitted task was:

```text
V2-9.8B Post-Accounting-Repair Authoritative WINDOW_15M Campaign Readiness Audit
```

That pointer is historical only and is superseded by the 2026-08-26 adoption
above.

##### Post-Authoritative-Readiness Roadmap Review (2026-08-01) — HISTORICAL

Verdict:

`V2_9_8B_WINDOW_15M_POST_AUTHORITATIVE_READINESS_ROADMAP_REVIEW_PASS`

The repeated authoritative readiness audit at `21262837322b31301cbfc495f814d7f84f149774` closed the
current-vs-historical `operator-runs/` reconciliation blocker.

At that 2026-08-01 checkpoint the exact next lane was:

```text
V2-9.8B WINDOW_15M External One-Shot Wrapper Manifest and Application Marker Design
```

That wrapper-design next-lane pointer is historical only. Wrapper/manifest/
marker construction and later standard-4h / four-token operational authority
advanced afterward and are synchronized into the active source stack by the
2026-08-26 adoption above. No historical consumed authorization may be reused.

#### Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Required disposition |
| --- | --- |
| Source-stack adoption is treated as campaign approval | Block; fresh authorization readiness/governance is next |
| Prior run or consumed authorization is treated as current authority | Prohibited; historical-only |
| Four-token is misread as >2 concurrent capacity | Block; concurrent capacity remains exactly 2 |
| Candidate-acquisition N2/N7 is treated as current required next lane | Block; deferred unless later explicit reactivation |
| Automatic retry/resume/restart/successor is assumed | Prohibited |
| Design drifts into runtime or financial work during sync closeout | Stop immediately |
