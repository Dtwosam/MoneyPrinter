# Printer V1 V2-9.7C Operational Memory Factory Design

## 1. Executive Design Decision

Printer shall implement one bounded, operator-approved campaign that owns this
flow:

```text
discovery -> selection -> tracking -> governed collection
-> conditional WINDOW_5M_MICRO_EVENT support -> WINDOW_15M closeout
-> selective per-token WINDOW_1H -> conditional per-token WINDOW_4H
-> clean/dirty/blocked audit -> cooldown/archive -> replacement/rotation
-> persistent corpus reporting -> report-only replay -> safe stop
```

Initial campaign capacity is exactly two active tokens. Every token starts one
main `WINDOW_15M` lifecycle. Continuation is token-local and categorical;
Printer never tracks every timeframe for every token.

This is a conceptual ownership and behavior contract. It creates no schema,
migration, command, runtime, source call, DB action, memory, retrieval, decision,
position, trade, audit, or PnL capability.

## 2. Scope and Non-Goals

The design binds campaign identities, state machines, budgets, fairness,
continuation, support-only 5m, trajectory, checkpoints, manipulation context,
opportunity segments, lifecycle, persistence, supervision, replay, reporting,
future capital policy, implementation slices, and proof gates.

It does not authorize implementation or an operational command. It does not
invent missing Jupiter, GoPlus, GeckoTerminal, public-RPC, wallet-authenticity,
participant-coordination, or quantitative-execution contracts. Missing facts
remain `CURRENT_EVIDENCE_GAP` or `UNKNOWN_REQUIRES_RESEARCH`.

Source Governor owns every source request. Central Scheduler owns every unit of
scheduled work. No component may create an independent loop or retry path.

## 3. Canonical Requirements Traceability

Each canonical requirement has exactly one row. Section references define the
full contract; the final column records its specific functionality risk,
setback, or efficiency blocker.

| ID | Requirement | Design element | Identities / state | Evidence required | Unknown / missing | Implementation dependency | Bounded proof | Failure / stop | Money-usefulness | Remains locked | Functionality Risks / Setbacks / Efficiency Blockers |
|---|---|---|---|---|---|---|---|---|---|---|---|
| R1 | Campaign model | Campaign aggregate and state machines, sections 4-5 | campaign, run, cycle, token, window, scheduler, report | exact identities and immutable policy/Git provenance | operational schema absent | V2-9.7D storage/orchestrator | bounded two-token multi-cycle fixture | identity mismatch or terminal ambiguity stops campaign | makes every lesson attributable | runtime and command | duplicate ownership or hidden successor |
| R2 | Selective continuation | categorical gates, section 7 | token plus predecessor window | clean/eligible close, continuity, learning need, budgets | quantitative execution may be missing | V2-9.7D gate implementation | only eligible token continues | dirty, stale, mismatch, unsupported, or exhausted stops token | spends long-window budget selectively | all-timeframe tracking | continuation becomes hidden ranking |
| R3 | Fairness and budgets | two-token scheduler, section 6 | token-local queues and campaign ceilings | scheduler work, source use, close deadlines | production ceiling values require committed config | V2-9.7D bounded config | no-starvation and close-boundary fixtures | any ceiling breach enters review stop | protects complete windows and source efficiency | unbounded operation | one token monopolizes close work |
| R4 | Conditional 5m support | support trigger contract, section 8 | support window and containing main window | exact trigger snapshots and provenance | unsupported trigger semantics stay unknown | V2-9.7D conditional capture | positive capture and negative no-capture | missing linkage cancels support only; parent remains governed | explains traps and exit realism | 5m authority | unconditional capture drains budget |
| R5 | Trajectory and checkpoints | fixed vocabularies, section 9 | ordered snapshots, phases, checkpoints | checkpoint-time evidence and gap visibility | unsupported phase remains unknown | V2-9.7D representation | anti-look-ahead and gap fixtures | future leakage blocks episode use | preserves realistic paths | decision activation | over-segmentation invents precision |
| R6 | Lifecycle and rotation | terminal disposition and replacement, section 17 | tracking lifecycle, cooldown/archive/revival | terminal main outcome and queue cleanup | replacement quality depends on discovery | B.3 reuse plus V2-9.7D rotation | two-token replacement fixture | stale work or duplicate lifecycle stops campaign | improves corpus diversity | silent recycle | repeated pairs dominate corpus |
| R7 | Supervision and recovery | lease, first cause, cancellation, section 17 | campaign lease, child/run, terminal event | confirmed renewal and durable first fault | resume remains unsupported | B.4 reuse plus operational supervisor | natural completion, fault, cancellation | unconfirmed renewal stops child; no restart | avoids ambiguous partial evidence | auto restart and resume | launcher fault could hide child state |
| R8 | Persistent-corpus safety | target, backup/restore, section 18 | DB target, backup, restore rehearsal | byte hash, integrity, FK, counts, reconciliation | migration not yet implemented | V2-9.7D migration prerequisite | disposable restore rehearsal | failed copy/reconcile blocks persistent start | protects accumulated corpus | DB mutation now | partial backup could look valid |
| R9 | Reporting and report-only replay | report contract, section 19 | report/replay identity | stored terminal report and authoritative rows | operational replay absent | B.1/B.5 reuse plus V2-9.7D replay | zero-source replay | missing/changed identity blocks replay | makes yield auditable | source work on replay | report drift could hide truth |
| R10 | Transition memory | transition vocabulary, sections 9-10 | ordered phase transitions | consecutive governed observations | distribution intent may be unknown | V2-9.7D derivation | transition ordering fixtures | unsupported transition is UNKNOWN | learns how conditions change | intent claims | endpoint-only labels miss path |
| R11 | Manipulation-aware memory | four dimensions and lifecycle, section 10 | integrity and tradeability context | governed categorical observations | coordination/authenticity often unknown | later source audits plus design fields | all eight behavior fixtures | missing mandatory evidence blocks dependent claim | separates tradeable manipulation from traps | action authorization | manipulation becomes auto-license/reject |
| R12 | Wallet and participant evidence | honest gap model, section 12 | token/pair/checkpoint authenticity context | governed wallet-level source | no current governed authenticity source | later Wallet and Participant Evidence Source Audit | UNKNOWN-preservation fixtures | unproven fields remain UNKNOWN | prevents false organic-flow lessons | authenticity claim | partial flow overstated as identity |
| R13 | Event-time execution memory | chart/executable split, section 13 | opportunity segment and execution evidence | route, quote, liquidity, latency, costs | quantitative provider contracts absent | Jupiter/GoPlus/GeckoTerminal/RPC work before V2-9.7D reliance | gap and future-evidence fixtures | no capturability claim without required evidence | prevents fake chart profit | execution and profit claims | categorical labels read as quantitative |
| R14 | Multiple checkpoint decision paths | finite path model, section 14 | checkpoint plus predeclared paths | checkpoint-time evidence only | decisions remain locked | later decision lane after corpus gates | path immutability fixtures | undeclared or hindsight path invalidates evaluation | compares process, not lucky outcome | actions and positions | profitable bad process appears good |
| R15 | Contradiction memory | categorical contradiction states, section 14 | comparable-memory set | exact comparable conditions and evidence | unseen conditions remain unseen | later retrieval/decision design | mixed/conflict/unseen fixtures | unresolved conflict defaults conservative later | preserves uncertainty honestly | retrieval and action | conflict collapsed into confidence |
| R16 | Balanced corpus coverage | coverage/concentration model, section 15 | corpus report dimensions | clean and negative outcomes plus selection history | small corpus limits inference | V2-9.7D reporting and V2-9.7E pilot | diversity/concentration fixtures | hidden concentration blocks closeout | avoids winner-only learning | quotas as scores | raw row growth masks bias |
| R17 | Recency and market-drift handling | categorical relationships, section 15 | episode time and regime relation | timestamps and regime context | future drift thresholds not proven | later corpus-quality review | same/recent/shifted/unseen fixtures | missing time/regime becomes unknown | avoids stale comparisons | numeric weighting | recency becomes hidden score |
| R18 | Frozen chronological validation | later validation contract, section 16 | frozen corpus/rules and unseen episodes | chronological evidence, realistic costs, baselines | no proof run in this lane | far-later validation lane | repeated walk-forward periods | rule rescue or leakage fails proof | tests capital protection and realistic profit | proof execution now | tuning to failures invalidates result |
| R19 | Optional operator capital policy | versioned optional contract, section 16 | policy/version/effective boundary | validated change and governed linkage | no schema or decision integration | later approved policy lane | risk-reducing/increasing scenarios | invalid or unsafe change rejected | controls paper exposure without weakening safety | financial activation | OFF mistaken for safety bypass |

## 4. Identity and Ownership Model

Conceptual fields and owners:

| Identity | Required fields | Owner |
|---|---|---|
| Campaign | `campaign_id`, policy version, configuration identity, DB target identity, launch Git provenance | operational campaign supervisor |
| Run | `run_id`, `campaign_id`, immutable launch config, first terminal cause | existing/future run ledger |
| Cycle | `cycle_id`, `campaign_id`, ordinal, start/end boundary, two token slots | campaign orchestrator |
| Token target | `token_id`, exact mint, `pair_id`, exact pair, slot, tracking lifecycle identity | selection/tracking handoff |
| Main window | window identity, kind, root 15m lifecycle, predecessor identity, open/close anchors | memory-window pipeline |
| Support window | support identity, root 15m, containing main window, trigger snapshots | support-5m pipeline |
| Scheduler work | scheduler-work identity, token/pair/window, priority, deadline | Central Scheduler |
| Source evidence | request/response provenance, source, target, freshness, scheduler work | Source Governor |
| Report/replay | report identity, run/campaign/cycle, immutable launch provenance, replay-of identity | reporting boundary |

Identity equality requires campaign, run, cycle where applicable, exact mint,
exact pair, lifecycle, window kind, predecessor, and scheduler/source provenance.
No symbol, nominal price, or nearby timestamp may substitute for identity.

Git provenance reuses B.5 exactly: `git_head`, tracked-tree cleanliness, staged,
unstaged and untracked indicators, and capture time. Replay never recomputes it.

## 5. State Machines and Terminal Semantics

Fixed campaign states: `DRAFT`, `PREFLIGHT`, `RUNNING`, `STOP_REQUESTED`,
`TERMINAL_COMPLETED`, `TERMINAL_STOPPED`, `TERMINAL_BLOCKED`, `TERMINAL_FAILED`.

Fixed cycle states: `PLANNED`, `DISCOVERING`, `SELECTING`, `TRACKING`, `CLOSING`,
`AUDITING`, `ROTATING`, `TERMINAL_COMPLETED`, `TERMINAL_STOPPED`,
`TERMINAL_BLOCKED`, `TERMINAL_FAILED`.

Fixed token states: `SELECTED`, `WINDOW_15M_ACTIVE`, `WINDOW_15M_CLOSED`,
`WINDOW_1H_CONTINUING`, `WINDOW_1H_CLOSED`, `WINDOW_4H_CONTINUING`,
`WINDOW_4H_CLOSED`, `COOLDOWN`, `ARCHIVED`, `MANUAL_REVIEW`, `FAILED`.

Fixed window states: `PLANNED`, `COLLECTING`, `CLOSE_PENDING`, `AUDITING`,
`CLEAN_PROMOTED`, `DIRTY`, `BLOCKED`, `NO_PROMOTION`,
`ALREADY_EXISTS_IDEMPOTENT`, `CANCELLED`.

Fixed scheduler states reuse existing scheduler vocabulary; no work may remain
active after its owning token or campaign terminalizes. Fixed report states are
`REPORT_PENDING`, `REPORT_TERMINAL`, `REPLAY_VERIFIED`, `REPLAY_BLOCKED`.

The first terminal cause is immutable. Cancellation is idempotent and reaches
the same cleanup path as natural completion or failure. Repeated terminalization
creates no duplicate lifecycle event, successor, retry, replacement run, or
automatic restart. A new campaign always requires a new operator-approved
launch identity.

## 6. Two-Token Scheduler, Fairness, and Budgets

Exactly two active token slots exist. Replacement fills a vacant slot only
after its prior target is terminal and reconciled. It never increases capacity.

Scheduler order is categorical:

1. imminent main-window close work, earliest deadline first;
2. overdue evidence-gap or safe-stop work;
3. token that received less service in the current fairness round;
4. older scheduler-work identity;
5. stable token-slot order only as a final tie-breaker.

Close-boundary work may preempt ordinary collection, but repeated preemption
must not starve the other token. Each fairness round must offer both eligible
tokens service before either receives a second non-close unit. Token-local
failure terminalizes only that token unless shared integrity, DB, lease, or
budget safety is compromised; shared failure safely stops the campaign.

The immutable configuration contains finite ceilings for source requests by
registered kind, scheduler work, per-token work, cycles, duration, storage
growth, retries, and failures. Source and ordinary scheduler retries are zero.
Only an already-approved primitive may use its existing fixed retry ceiling
(for example B.4 confirmed transient Windows replacement errors); it may not be
expanded by campaign policy. Hitting a ceiling prevents new work, preserves the
first cause, completes possible safe cleanup/reporting, and enters
`TERMINAL_BLOCKED` or `TERMINAL_STOPPED` for operator review.

## 7. Selective Continuation Contract

Every selected token starts `WINDOW_15M`. The 15m close must reconcile B.1
promotion status, B.2 effective safety context, evidence completeness,
freshness, exact identity, source provenance, and lifecycle state.

Fixed 15m-to-1h verdicts:

- `CONTINUE_TO_WINDOW_1H`: main evidence is eligible, exact predecessor
  continuity exists, a declared coverage/transition learning need exists, and
  token/campaign/source/scheduler/storage budgets remain available.
- `STOP_AFTER_WINDOW_15M`: valid close but no declared learning need or budget
  allocation; enter lifecycle disposition normally.
- `BLOCK_CONTINUATION`: dirty, blocked, stale, mismatched, unsupported,
  untraceable, missing mandatory evidence, safety blocked/unknown where
  mandatory, exhausted ceiling, cancellation, or identity conflict.

Fixed 1h-to-4h verdicts mirror these as `CONTINUE_TO_WINDOW_4H`,
`STOP_AFTER_WINDOW_1H`, and `BLOCK_CONTINUATION`. A 4h continuation additionally
requires the exact 1h predecessor and a declared 4h transition, survival,
collapse, revival, distribution, or liquidity-deterioration learning need.

Continuation is evaluated independently per token. `WINDOW_5M_MICRO_EVENT`, raw
row count, price performance, symbol, nominal price, manipulation label alone,
or another token's verdict can never trigger it. No score, rank, probability,
confidence, numeric weighting, or hidden priority total is permitted.

Selective proof scenarios must include: only token A continues to 1h; only
token B continues to 4h; both stop cleanly at 15m; one blocks while the other
continues; and shared budget exhaustion stops both safely.

## 8. Conditional WINDOW_5M_MICRO_EVENT Contract

Approved trigger families are fixed:

- `FAST_COORDINATED_PUMP`
- `FAST_DUMP_OR_COLLAPSE`
- `WICK_OR_LATE_BUY_TRAP`
- `EXIT_REALISM_CHANGE`
- `LIQUIDITY_SHOCK`
- `FAST_BREAKDOWN_OR_RECLAIM`

Positive capture examples: a governed snapshot pair shows a fast expansion; a
wick appears and reverses; liquidity or route realism deteriorates abruptly; a
fast dump occurs; or a breakdown/reclaim transition needs support explanation.

Negative no-capture examples: ordinary movement inside expected cadence; a
single unsupported label; missing exact linkage; stale/mismatched snapshots;
budget exhaustion; no meaningful transition; or a trigger inferred only from a
later main-window outcome.

Capture may occur inside an ongoing 15m, 1h, or 4h lifecycle, but each support
object must exact-link campaign, run, cycle, token, mint, pair, root 15m
lifecycle, containing main window, triggering snapshots, source provenance, and
scheduler work. Its evidence cutoff is the trigger time.

5m never replaces a main window, independently triggers continuation, counts
toward main clean-memory thresholds, selects lifecycle disposition, activates
retrieval/decisions, or authorizes financial behavior. Missing or failed support
does not silently dirty an otherwise complete main window unless the main
window's own mandatory evidence is missing.

## 9. Trajectory, Transition, and Checkpoint Model

Fixed trajectory-phase vocabulary:

`OPENING_STATE`, `QUIET_PREPARATION`, `INITIAL_EXPANSION`, `PULLBACK`,
`CONTINUATION`, `CONSOLIDATION`, `BREAKDOWN`, `RECLAIM`, `SECOND_EXPANSION`,
`DISTRIBUTION`, `LIQUIDITY_DETERIORATION`, `COLLAPSE`, `SURVIVAL`, `REVIVAL`,
`FINAL_OUTCOME`, `EVIDENCE_GAP`, `UNKNOWN_PHASE`.

Fixed reversal vocabulary:

`NO_CONFIRMED_REVERSAL`, `BREAKDOWN_TO_RECLAIM`,
`EXPANSION_TO_DISTRIBUTION`, `COLLAPSE_TO_REVIVAL`, `REVERSAL_UNKNOWN`.

Consolidation, breakdown, reclaim, distribution, liquidity deterioration,
survival, collapse, and revival use the phase names above; unsupported meaning
is `UNKNOWN_PHASE`, never a newly invented runtime label.

The trajectory stores ordered snapshot identities, observed times, gaps,
phases, reversals, source provenance, and containing window. Scheduled
checkpoints are bounded cadence/deadline points. Event checkpoints are bounded
approved trigger-family points. Both contain only evidence observed by their
cutoff and finite predeclared paths.

Later evidence may evaluate an earlier checkpoint but never rewrite its state,
eligible paths, evidence cutoff, or unknowns. Comparison is categorical and
condition-based, never nominal-price matching. `observed_peak` is a chart fact;
`realistically_capturable_exit` stays unknown until event-time execution
evidence supports it. Gaps crossing a claimed phase, reversal, entry, or exit
remain visible and block that dependent claim.

## 10. Manipulation-Aware Opportunity Architecture

Printer is not an organic-coin detector. Four independent categorical
dimensions are always stored:

- evidence quality: existing clean/partial/dirty/do-not-train contract;
- market-integrity condition: `NO_MANIPULATION_EVIDENCE`,
  `MANIPULATION_CONTEXT_PRESENT`, `MANIPULATION_CONTEXT_MIXED`,
  `MARKET_INTEGRITY_UNKNOWN`;
- tradeability: `MANIPULATED_REALISTICALLY_TRADEABLE`,
  `MANIPULATED_EXIT_QUALITY_DETERIORATING`,
  `MANIPULATED_REALISTICALLY_UNTRADEABLE`, `TRADEABILITY_UNKNOWN`;
- action eligibility: `ACTION_ELIGIBILITY_LOCKED`,
  `ACTION_ELIGIBILITY_BLOCKED`, `ACTION_ELIGIBILITY_UNKNOWN` in this program.

Fixed manipulation lifecycle vocabulary:

`QUIET_PREPARATION_OR_ACCUMULATION`, `ARTIFICIAL_ACTIVITY`,
`ATTENTION_EXPANSION`, `WIDER_PARTICIPATION`,
`INITIAL_DISTRIBUTION_PRESSURE`, `SHAKEOUT_OR_CONTINUATION`,
`SECOND_EXPANSION_OR_FAILED_RECOVERY`, `HEAVY_DISTRIBUTION`,
`LIQUIDITY_DETERIORATION`, `COLLAPSE_SURVIVAL_OR_REVIVAL`.

The eight required behavior families are represented exactly:

1. fast coordinated pump;
2. wash-like or artificial flow;
3. concentrated early ownership or suspected insider distribution;
4. liquidity add, pull, lock, or unlock behavior;
5. dev, creator, pool, or holder pressure where governed evidence supports it;
6. trap, wick, late-buy, or exit-failure behavior;
7. dead-to-active, manipulated-to-active, or revival behavior;
8. participant-authenticity uncertainty.

Manipulation never automatically authorizes or rejects an action. Wallet,
participant, coordination, route, and execution-dependent behavior remains
`UNKNOWN_REQUIRES_RESEARCH`, `CURRENT_EVIDENCE_GAP`, or blocked when its
governed evidence is absent.

## 11. Tradeable Path and Money-Usefulness Architecture

Two outcome layers remain separate:

- `full_window_outcome`: what happened over the complete main window;
- `internal_trade_opportunity_outcome`: what happened within each bounded,
  ordered opportunity segment.

A negative main window may contain zero, one, or several segments without
rewriting the full-window outcome. Connected conceptual objects are: window
outcome, ordered phases, checkpoint states, opportunity segments, finite
eligible paths, later-locked position-state transitions, entry evidence, exit
evidence, post-exit re-entry reviews, manipulation/authenticity context,
unknown/unproven fields, and later realized paper outcomes.

The twelve fixed tradeable-path contexts are:

1. expansion, pullback, continuation;
2. expansion then failed continuation;
3. fast breakdown then genuine reclaim;
4. wick-only peak;
5. price rising while exit deteriorates;
6. high volume with weak authenticity;
7. good entry with bad hold;
8. bad entry with profitable outcome;
9. correct exit then more upside;
10. missed entry with no-chase;
11. re-entry churn;
12. market-context mismatch.

These are memory-design contexts, not decisions. They create no position or
action and cannot claim profit without realistic event-time evidence.

## 12. Wallet and Participant Gap Handling

The following fields exist conceptually but default to `UNKNOWN` unless a later
governed source contract proves them: creator/deployer history, early-buyer
concentration, related-wallet clusters, bundled accounts, hidden cross-account
concentration, coordinated timing, early-holder inventory changes, genuine
participant expansion, and probable distribution.

Current flow, holder, transaction, or concentration labels may remain partial
context but cannot prove identity, common control, coordination, intent, or
authenticity. A later Wallet and Participant Evidence Source Audit is mandatory
before paper-decision readiness.

## 13. Event-Time Execution Memory

`CHART_OPPORTUNITY` and `REALISTICALLY_EXECUTABLE_OPPORTUNITY` are distinct.

| Evidence field | Current classification | Design treatment |
|---|---|---|
| configured paper position size | future Printer-configured | locked policy input |
| quote/route availability and freshness | provider-dependent future evidence | `CURRENT_EVIDENCE_GAP` pending Jupiter contract |
| usable liquidity | current categorical plus future provider detail | categorical only until contracts support more |
| position-size impact, slippage, fees | provider-dependent future evidence | `CURRENT_EVIDENCE_GAP` |
| observation/decision/simulated-execution delay | Printer-derived future evidence | derive from immutable timestamps later |
| opportunity duration | Printer-derived future evidence | derive from ordered snapshots later |
| failed routes | provider-dependent future evidence | `CURRENT_EVIDENCE_GAP` |
| maximum realistically executable size | provider plus derived future evidence | `UNKNOWN_REQUIRES_RESEARCH` |
| partial/complete exit capability | provider plus derived future evidence | `UNKNOWN_REQUIRES_RESEARCH` |
| wick-only versus durable | Printer-derived future evidence | categorical trajectory derivation |
| decision-to-execution price movement | provider plus Printer-derived future evidence | gap until both sides exist |

Jupiter route/quote, GoPlus, GeckoTerminal, and public-RPC contract work remains
a pre-V2-9.7D dependency wherever implementation would rely on those fields.
Current categorical evidence must never be presented as quantitative execution
proof.

## 14. Multiple Paths and Contradiction Memory

Each future checkpoint has one authoritative paper path and a finite,
predeclared alternative set drawn from `ENTRY_REVIEW`, `HOLD_REVIEW`,
`EXIT_REVIEW`, `WAIT_REVIEW`, `AVOID_REVIEW`, `NO_ACTION_REVIEW`, and
`FRESH_REENTRY_REVIEW`. They are evaluation states only. No path executes here.

Later evaluation distinguishes good process/bad outcome, bad process/profitable
outcome, correct exit/more upside, missed entry/no-chase, and re-entry churn.
Re-entry requires the prior path to be closed, a new checkpoint, fresh evidence,
and a new comparison; it may not reuse completed-chart knowledge.

Fixed contradiction states:

- `COMPARABLE_MEMORIES_CONSISTENT`
- `MIXED_OUTCOMES_CLEAR_SEPARATOR`
- `UNRESOLVED_MATERIAL_CONFLICT`
- `NO_COMPARABLE_MEMORY`
- `INSUFFICIENT_EVIDENCE`
- `UNSEEN_CONDITION`

Unresolved conflict, insufficient evidence, no comparable memory, or unseen
condition must default conservatively in any later approved decision lane. No
score, probability, or confidence may conceal contradiction.

## 15. Corpus Coverage, Concentration, Recency, and Drift

Coverage reporting separates winners, losers, traps, dead tokens, revivals,
real and failed reclaims, fake recoveries, coordinated markup, distribution,
liquidity deterioration/removal, wick-only peaks, tradeable/untradeable
manipulation, good/bad entry-hold-exit processes, negative windows with useful
segments, and different Solana/market regimes.

Concentration is reported independently by token, pair, source, venue,
timeframe, outcome, trajectory family, manipulation family, and market regime.
Selection/rejection/ignore history remains visible so winner-only or
survivorship bias cannot hide behind promoted-row counts.

Fixed recency/drift relationships are `SAME_REGIME_RECENT`,
`SAME_REGIME_OLDER`, `REGIME_SHIFTED`, `MARKET_STRUCTURE_SHIFTED`,
`RECENCY_UNKNOWN`, and `UNSEEN_REGIME`. They are categorical diagnostics only;
no numeric decay, weight, score, or ranking is permitted.

## 16. Frozen Chronological Validation and Optional Capital Policy

### Frozen Validation Contract

A later proof must freeze the eligible reference corpus and comparison/action
rules; evaluate chronologically unseen episodes; exclude future checkpoint data;
keep evaluation episodes outside the usable corpus until closeout; include
realistic costs, latency, impact, and failed routes; compare against `NO_ACTION`
and simple approved baselines; split results by regime and path family; and
include selected, rejected, ignored, winning, losing, trap, revival, and dead
cases where required.

Repeated walk-forward periods must report drawdown, fragility, concentration,
capital protection, and profit. Rules may not change to rescue a failed period.
Any leakage, corpus contamination, or rescue tuning fails the proof. This lane
does not implement or run validation.

### Optional Operator Capital Policy

The future policy may support view, validate, preview, enable/disable optional
operator limits, field-level change, history, and restoration for paper-only
position, exposure, loss, re-entry, impact, averaging, partial-exit, and
campaign-stop preferences.

Every change must be schema-validated, versioned, auditable, non-retroactive,
linked to governed decisions, and applied at a safe boundary. Risk-reducing
changes may take effect at the next safe checkpoint without increasing any
exposure. Risk-increasing changes take effect no earlier than the next campaign
boundary with no active token/window governed by the prior policy. Neither may
rewrite an open path.

`CAPITAL_POLICY_OFF` disables only operator-selected paper limits. It never
disables Source Governor, Central Scheduler, clean-evidence rules, safety gates,
paper-only mode, capability locks, no-live-funds, no-dirty-memory decisions, or
the prohibitions on scoring and hidden weighting.

Required scenarios include a risk-reducing loss-limit change at a safe
checkpoint, a risk-increasing exposure change deferred to a new campaign,
invalid restoration rejection, and `CAPITAL_POLICY_OFF` preserving every
permanent invariant.

## 17. Lifecycle, Supervision, Recovery, and Rotation

B.3 terminal mapping is reused: valid terminal main outcomes enter explicit
`COOLDOWN` or operator-selected `ARCHIVED`; incomplete, cancelled, blocked, or
failed lifecycles enter `MANUAL_REVIEW` / `SKIPPED` and `DO_NOT_TRAIN`. Each
run/token/pair gets one idempotent lifecycle event. All associated active queue,
scheduler, and pending support work is terminalized.

Cooldown records the pair-specific no-reselection boundary. Archive is explicit
and does not imply permanent rejection. Revival requires fresh governed
evidence, expiry/eligibility under lifecycle policy, and a new selection review.
Replacement selection begins only after terminal reconciliation and fills one
vacant slot. It cannot silently recycle the same token/pair during cooldown.

B.4 semantics are reused: exact lease ownership, monotonic heartbeat/expiry,
same-directory atomic replacement, only the already-approved bounded transient
Windows retry, first-fault fallback persistence, immutable first terminal cause,
child stop after unconfirmed renewal, cleanup, no successor, and no restart.
Ordinary logger failure cannot erase a confirmed renewal.

There is no automatic resume. Interruption leaves a terminal, auditable state.
A later operator-approved campaign may start only after preflight and recovery
review; it is a new identity, not a successor.

## 18. Persistent-Corpus Safety Design

The authoritative operational target is the explicitly configured persistent
corpus DB identity; proof DBs and V2-9 proof-launcher copies are prohibited.
V2-9.7D must define any required migration before persistent operation and must
not mutate the persistent DB merely to test the migration.

Before first persistent campaign use:

1. close all writers and confirm exclusive target ownership;
2. create a same-volume temporary copy with interrupted-copy defense;
3. verify source and copy byte counts and cryptographic hashes;
4. atomically publish the backup only after verification;
5. rehearse restore on a disposable copy;
6. run integrity, foreign-key, migration, table/row-count, and hash
   reconciliation;
7. block launch on any mismatch.

Backup, restore rehearsal, and migration each have distinct artifact identities.
Cleanup never deletes the last verified backup. Storage-ceiling or write failure
stops new collection, preserves first cause, reconciles terminal state, and
reports partial evidence as non-clean.

## 19. Reporting and Report-Only Replay Contract

Reports keep diagnostics separate:

- B.1 authoritative promotion outcomes: `CLEAN_PROMOTED`,
  `DIRTY_OR_BLOCKED`, `ALREADY_EXISTS_IDEMPOTENT`, `NO_PROMOTION`;
- B.2 effective safety: `SAFETY_CONTEXT_ACCEPTABLE`,
  `SAFETY_CONTEXT_BLOCKED`, `SAFETY_CONTEXT_UNKNOWN`, with raw labels retained;
- dirty/blocked reasons and source candidate status;
- timeframe and continuation yield;
- source efficiency, scheduler work/fairness, and token/source concentration;
- trajectory, manipulation-family, and opportunity-segment coverage;
- wallet/authenticity `UNKNOWN` and event-time execution gaps;
- rotation, cooldown, archive, replacement, interruption, terminal cause, and
  shutdown;
- policy version and immutable B.5 Git provenance;
- chart return versus executable return, fees, slippage, impact, maximum
  adverse/favorable excursion, avoided loss, missed upside, re-entry churn,
  time in position, peak-to-executable-exit gap, and later-locked correct/
  incorrect WAIT or AVOID outcomes.

No diagnostic may be combined into a score, rank, confidence, weighting,
embedding, or vector.

Report-only replay accepts an exact report/replay identity, reads committed run
configuration and authoritative stored rows, performs zero discovery/source/
scheduler/memory work, writes nothing, never recaptures Git provenance, and
returns either byte/semantic-equivalent diagnostics or `REPLAY_BLOCKED` with a
reason. It never repairs lifecycle or creates a promotion.

## 20. Abstract V2-9.7D Command Contract

The future command accepts conceptual inputs for immutable configuration
identity, explicit persistent DB target identity, policy version, two-token
capacity, finite campaign/cycle/duration/source/scheduler/storage/failure
ceilings, report directory identity, and either campaign or report-only mode.

Preflight verifies clean tracked Git provenance, exact DB ownership, no active
lease, committed migration state, verified backup/restore prerequisites,
Source Governor/Central Scheduler availability, writable bounded report paths,
and all lock states. Campaign behavior follows sections 4-19. Cancellation is
idempotent. Terminal behavior preserves first cause, stops children, reconciles
token-local work, writes the final report, releases the lease, and creates no
successor. Report-only mode is zero-source and read-only.

This is not command-line syntax and is not runnable. The exact operational
command remains locked until V2-9.8A.

## 21. V2-9.7D Implementation Slices

1. Complete required Jupiter, GoPlus, GeckoTerminal, and public-RPC contract
   prerequisites before implementing fields that rely on them.
2. Add the minimal campaign/config/report persistence and migration with
   isolated migration/restore tests only.
3. Implement identity/state validation and two-token scheduler fairness.
4. Implement token-local selective continuation and conditional 5m capture.
5. Implement fixed trajectory/checkpoint/manipulation/opportunity objects with
   UNKNOWN preservation and anti-look-ahead checks.
6. Integrate B.1-B.5, lifecycle rotation, operational lease, first-fault stop,
   backup/restore preflight, final reporting, and zero-source replay.
7. Add the abstract command surface only after all lower slices pass; do not run
   an operational campaign in V2-9.7D.

Each slice remains narrow, uses isolated DBs, and preserves all capability locks.

## 22. V2-9.7E Two-Token Pilot Requirements

The pilot starts exactly two active tokens and proves exact identity isolation,
no starvation, close-boundary priority, token-local failure isolation, selective
15m-to-1h and 1h-to-4h behavior, positive/negative 5m capture, authoritative
promotion reporting, safety clarity, terminal lifecycle reconciliation,
rotation/replacement, immutable provenance, bounded lease behavior, safe stop,
backup/restore readiness, and zero-source report-only replay.

It must report all ceilings and deltas; prove no stale queue/scheduler/lease/temp
artifact; prove no successor or restart; preserve wallet/execution gaps; and
show zero retrieval, decision, position, trade, audit, PnL, wallet, signing, and
real-funds deltas. Scaling to three tokens is prohibited in V2-9.7E.

## 23. Rollback and Stop Conditions

Stop or block on identity mismatch, foreign/malformed/expired lease, unconfirmed
heartbeat, dirty/stale/missing mandatory evidence, safety block, source or
scheduler bypass, future-data leakage, unsupported phase/coordination/execution
claim, DB/backup/restore mismatch, storage/budget/failure ceiling, stale terminal
work, report/replay disagreement, attempted automatic restart, 5m authority,
all-timeframe tracking, score-like logic, or any locked capability activation.

Rollback means disabling the unactivated implementation path, preserving
artifacts and the last verified backup, and returning to operator review. It
never rewrites historical evidence or silently retries.

## 24. Money-Usefulness Contribution

The design directs scarce source and scheduler capacity toward complete,
diverse, chronologically honest lessons. It separates chart movement from
executable opportunity, full-window outcome from internal segments, and
manipulation context from evidence quality and action eligibility. This improves
future capital-protection research without claiming profitability.

## 25. What This Design Improves

- Converts proven one-token primitives into one bounded two-token campaign
  contract.
- Fixes the exact identity, state, continuation, fairness, 5m, trajectory,
  manipulation, opportunity, persistence, replay, and stop semantics needed by
  V2-9.7D.
- Preserves negative outcomes, uncertainty, contradiction, and concentration
  visibility instead of optimizing raw clean-row count.
- Makes future implementation and pilot acceptance auditable before activation.

## 26. What Remains Locked

Implementation; V2-9.7D execution; runtime and operational memory growth;
source/API/RPC/provider/MCP calls; persistent DB mutation; retrieval; BUY, SELL,
HOLD, WAIT, AVOID, or NO_ACTION activation; paper positions; trade events;
paper-trade audits; PnL; operational command release; MCP installation or
connection; custom MCP; wallets; private keys; signing; execution; real funds;
paid APIs; scoring; ranking; confidence percentages; weighted logic;
embeddings; vectors; 12h/24h; V2-10 and later lanes.

## 27. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Failure effect | Required control |
|---|---|---|
| Two-token fairness is only nominal | starvation and dirty close boundaries | fairness rounds plus deadline priority and pilot evidence |
| Selective gate drifts into ranking | prohibited hidden score | fixed categorical verdicts and reasons |
| 5m becomes mandatory/main | budget drain and false authority | trigger whitelist, negative fixtures, main-threshold exclusion |
| Trajectory labels overstate gaps | hindsight precision | fixed vocabulary, gap-visible blocking |
| Manipulation becomes action | unsafe auto-license or blanket rejection | four independent dimensions |
| Wallet context is overstated | false participant authenticity | UNKNOWN default and later source audit |
| Chart return becomes profit | fake money-usefulness | event-time evidence contract and gap labels |
| Re-entry uses completed chart | hindsight churn | new checkpoint and fresh evidence |
| Corpus grows concentrated | weak generalization | multidimensional coverage/concentration reports |
| Backup appears valid when partial | corpus loss | byte/hash verification and restore rehearsal |
| Replay touches sources or writes | audit path mutates evidence | zero-source, read-only replay contract |
| Lease/log fault obscures stop | ambiguous partial campaign | B.4 first-cause and fail-closed child stop |
| Capital policy disables safety | permanent invariant breach | OFF limitation and effective-boundary rules |
| Provider facts are invented | false executability/safety | pre-V2-9.7D contract dependencies |
| Implementation starts from this doc | lane violation | separate V2-9.7D authorization required |
