# Printer V1 V2-9.7C.0 Money-Usefulness Requirements Readiness Audit

## 1. Executive Verdict

`V2_9_7C_0_MONEY_USEFULNESS_REQUIREMENTS_AUDIT_PASS`

All nineteen canonical V2-9.7C requirements are traceable, each to exactly one
matrix row, with current coverage, gaps, blockers, and later-lane dependencies
made explicit. The proposed binding manipulation-aware and money-usefulness
product laws are assembled and ready for a separate V2-9.7C.0A adoption lane.
The repository is ready for that adoption step and, after it, for V2-9.7C design.

This PASS is an audit result only. It does not adopt any product law, change the
active build order, begin V2-9.7C design, or unlock any runtime, memory,
retrieval, decision, position, trade, audit, PnL, wallet, key, or fund
capability. Those remain locked exactly as before.

The audit's central finding: the **Operational Memory Factory foundation
(requirements 1-9)** is substantially present as proven, reusable machinery that
V2-9.7C can design against without inventing policy. The **Manipulation-Aware
Opportunity and Tradeable-Path layer (requirements 10-19)** is largely genuinely
new, and two of its pillars — market-integrity condition evidence (req 11) and
wallet/participant evidence (req 12) — have **no governed source and no
source-of-truth contract module** in the repository today. V2-9.7C design may
specify policy around those gaps only by holding the evidence explicitly
`UNKNOWN` until a separate approved source-audit lane resolves it. It must not
invent the capability.

## 2. Scope and Preflight

Documentation and static inspection only. No code, tests, schema, migration,
runtime, source, database, or memory action was performed. No website, API, RPC,
adapter, discovery, or source-fetching path was called.

- HEAD: exact `d862139` (`Close V2-9.7B repair program`).
- Tracked tree: clean before this document was created (`git status` zero
  tracked modifications).
- Runtime: no Python process active; no Printer runtime started.
- Locks: no proof or campaign lock; `operator-runs/v2-9-one-proof.lock.json`
  absent; no `.lock.json` under the repository root.
- Persistent DB hash (unchanged, not read for content):
  `97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB`.
- Unrelated untracked artifacts: 165 baselined and left untouched.

### Source stack read

Active Printer V1 stack: `AGENTS.md`, `docs/printer-v1-clean-master-spec.md`,
`docs/printer-v1-post-rc-build-order.md`,
`docs/printer-v1-memory-factory-guide.md`,
`docs/printer-v1-current-state-memory-growth-audit.md`,
`docs/printer-v1-memory-growth-build-order-v2.md`,
`docs/printer-v1-v2-9-final-closeout.md`, the V2-9.7A readiness audit, the
V2-9.7B focused closeout, the V2-9.7B trajectory-checkpoint product-law adoption
closeout, and the V2-9.7B.1-B.5 closeouts. All named closeouts exist under their
stated filenames; none required a git search for an equivalent.

Subordinate Solana Builder stack: see §9 for the per-module existence check. Six
named modules are absent and are recorded as `CURRENT_EVIDENCE_GAP`.

### Prior completed work not reopened

- V2-9.7A readiness audit (`c928aa4`): end-to-end component classification,
  persistent-DB gap, reusable-primitive map.
- V2-9.7B.1 authoritative promotion reporting (`d604926`).
- V2-9.7B.2 timeframe-aware safety labels (`b2af7b1`).
- V2-9.7B.3 tracking lifecycle reconciliation (`0ccdaa5`).
- V2-9.7B.4 heartbeat/lease reliability (`62ae469`).
- V2-9.7B.5 embedded Git provenance (`b3d8761`).
- V2-9.7B trajectory-checkpoint **product-law adoption** (`2d1c10c`): full-
  trajectory memory, phase/reversal, historical checkpoint construction, strict
  anti-look-ahead, realistic action paths, re-entry semantics, observed-peak vs
  capturable-exit separation, and lifecycle-wide conditional 5m — all adopted
  into the clean master spec, factory guide, and build-order-v2. This audit
  treats those as already-adopted law and does not re-adopt them.

## 3. Canonical Traceability Matrix — All 19 Requirements

Exactly one row per requirement. Nested obligations are referenced into §5-§9
and never merged into or substituted for another top-level row. Statuses:
`ALREADY_COMPLETE`, `PARTIALLY_COVERED`, `NEW_REQUIREMENT`,
`CURRENT_EVIDENCE_GAP`, `UNKNOWN_REQUIRES_RESEARCH`, `LATER_LANE_DEPENDENCY`,
`DESIGN_BLOCKER`, `NON_BLOCKING_LIMITATION`.

### R1 — Campaign model
- **Status:** PARTIALLY_COVERED; NEW_REQUIREMENT (campaign layer).
- **Coverage:** Run/cycle/token/pair/main-window/support-window/scheduler-work/
  report identities exist. Run ledger `migrations/028_memory_factory_run_ledger.sql`
  (`printer_memory_factory_runs`, `printer_memory_factory_run_steps`, `run_id`,
  `snapshot_id`); windows in `014`; episodes in `014`; scheduler jobs in `003`.
  Terminal-cause and first-terminal preservation proven in `proof_supervision.py`
  and the factory safe-stop path. `automatic_retries=0`; no successor process.
- **Files:** `migrations/028`, `src/printer_v1/operator_cli/one_command_15m_factory.py`,
  `proof_supervision.py`, `migrations/003`, `004`.
- **Reusable primitives:** run ledger, run steps, terminal-cause recorder,
  zero-retry safe stop.
- **Missing policy:** a campaign identity above the run; explicit two-initially-
  active-token contract; campaign/cycle terminal-state vocabulary; campaign-level
  idempotency identity.
- **Missing evidence/source:** none — identity is internal.
- **Belongs to:** V2-9.7C design (campaign model), V2-9.7D (schema/impl).
- **Impl deps:** operational run-ledger mode (migration 028 constrains
  `db_mode='PROOF_ONLY'`); an operational migration is a later lane.
- **Proof deps:** bounded multi-cycle two-token fixture; no live proof here.
- **Money-usefulness:** turns one proven lifecycle into a repeatable bounded
  producer of diverse lessons.
- **Improves:** repeatability, terminal auditability.
- **Does not unlock:** any campaign write, retrieval, or financial action.
- **Risks:** campaign identity that does not cover cycle/token/pair/window/
  predecessor would allow duplicate or orphaned cycles.

### R2 — Selective continuation
- **Status:** PARTIALLY_COVERED.
- **Coverage:** Exact 15m→1h (`_resolve_current_run_15m_source`,
  `build_1h_continuation_plan`, `_execute_continuation_close`) and 1h→4h
  (`one_token_4h_runtime.plan_current_run_4h`) are proven with exact identity and
  one-time predecessor consumption (Attempt 7: 24/24 then 61/61). Selection is
  categorical and seeded, not scored.
- **Files:** `one_command_15m_factory.py`, `one_token_4h_runtime.py`,
  `snapshots/lifecycle_continuity.py`.
- **Reusable primitives:** exact predecessor continuation, categorical eligibility
  gates.
- **Missing policy:** per-token selective continuation verdict. Today
  `continuous_first_hour` is run-wide and requires exactly one token; every clean
  15m close plans 1h. No per-token "should this token continue" categorical rule.
- **Missing evidence/source:** none new; uses existing evidence.
- **Belongs to:** V2-9.7C design; V2-9.7D impl.
- **Impl deps:** campaign model (R1), fairness (R3).
- **Proof deps:** two-token fixture where only the eligible token continues.
- **Money-usefulness:** spends expensive long-window capacity only where a lesson
  is likely, not on every token.
- **Improves:** capacity discipline, corpus diversity.
- **Does not unlock:** all-timeframe tracking; scores/rankings remain prohibited.
- **Risks:** a continuation rule expressed as a threshold could drift into hidden
  scoring; must stay categorical.

### R3 — Fairness and budgets
- **Status:** PARTIALLY_COVERED; LATER_LANE_DEPENDENCY (fairness proof).
- **Coverage:** Bounded source/scheduler/duration/cycle/token/retry/failure
  ceilings exist; per-token and run-wide budget checks fail closed; zero automatic
  retries; token-local failure isolation. `_FORBIDDEN_DELTA_TABLES` enforced.
- **Files:** `one_command_15m_factory.py` (budget enforcement, `_enforce_budgets_before_step`),
  `proof_supervision.py`, `scheduler` module.
- **Reusable primitives:** budget ceilings, fail-closed stops, no hidden unbounded
  loop.
- **Missing policy:** close-boundary work priority between two tokens; explicit
  no-starvation contract. The factory reads its own ledger `ORDER BY scheduled_for,id`;
  Central Scheduler's `select_next_jobs()` has priority/due-time but is not the
  two-token arbiter here.
- **Belongs to:** V2-9.7C design (fairness contract); V2-9.7D (use/extend scheduler);
  V2-9.7E (no-starvation proof).
- **Proof deps:** two-token deterministic scheduling test; bounded pilot.
- **Money-usefulness:** guarantees the second token's close evidence is not
  starved by the first.
- **Improves:** evidence completeness under contention.
- **Does not unlock:** anything financial.
- **Risks:** tie ordering favouring one token silently drops the other's close
  boundary.

### R4 — Conditional 5m support
- **Status:** PARTIALLY_COVERED.
- **Coverage:** `_capture_same_stream_5m_support` derives a support window from the
  same run's 15m stream, exact-links run/token/pair/lane/parent-window/snapshot,
  persists a `SUPPORT_5M` step, and stays audit/support-only. Lifecycle-wide
  conditional 5m is **adopted as product law** (trajectory-checkpoint lane).
- **Files:** `one_command_15m_factory.py::_capture_same_stream_5m_support`,
  `lane_x8_5m_support_integration.py`, `migrations/013`.
- **Reusable primitives:** exact-linked support window, `SUPPORT_5M` ledger step.
- **Missing policy:** the categorical event triggers. Today capture is
  unconditional whenever continuous 1h is active; there is no event gate.
- **Missing evidence/source:** none new; the design defines trigger categories.
- **Belongs to:** V2-9.7C design (trigger categories + negative no-capture cases).
- **Proof deps:** positive trigger and negative no-capture fixtures.
- **Money-usefulness:** captures pump/dump/wick/trap/exit micro-context only when
  it matters, without cost on quiet windows.
- **Improves:** targeted micro-event evidence.
- **Does not unlock:** 5m as main outcome, continuation trigger, threshold count,
  retrieval, or actions (all permanently barred).
- **Risks:** unconditional capture becomes a hidden mandatory main dependency.

### R5 — Trajectory and checkpoints
- **Status:** PARTIALLY_COVERED (product law ALREADY_ADOPTED; representation not
  implemented).
- **Coverage:** Full-trajectory memory, phase/reversal preservation, historical
  checkpoint construction, strict anti-look-ahead, condition-based (not nominal-
  price) comparison, and observed-peak vs capturable-exit separation are adopted
  law in `clean-master-spec`, `memory-factory-guide`, `build-order-v2`. Snapshot
  ledger already records ordered price/liquidity/volume/txn series; `created_by_phase`
  exists on `printer_memory_windows`.
- **Files:** `docs/printer-v1-clean-master-spec.md`, `memory-factory-guide.md`,
  `build-order-v2.md`; `migrations/006`, `014`.
- **Reusable primitives:** ordered snapshot series, phase column, adopted law.
- **Missing policy:** the concrete categorical phase/reversal vocabulary and the
  derived-trajectory field set the design must specify; unsupported metrics stay
  `UNKNOWN`/`UNPROVEN`.
- **Belongs to:** V2-9.7C design (representation + checkpoint construction).
- **Proof deps:** trajectory-representation and anti-look-ahead fixtures.
- **Money-usefulness:** learns the path, not just open-vs-close.
- **Improves:** realistic checkpoint learning.
- **Does not unlock:** decisions; look-ahead; nominal-price imitation.
- **Risks:** representation that invents unsupported precision.

### R6 — Lifecycle and rotation
- **Status:** PARTIALLY_COVERED.
- **Coverage:** `lane_x3_post_cycle_lifecycle.py`
  (`enter_cooldown_after_window`, `archive_after_memory_window`, `reopen_token`,
  `evaluate_post_cycle_lifecycle`); selection rotation state
  `migrations/026_selection_rotation_state.sql`; V2-9.7B.3 reconciled terminal
  tracking-queue state. Clean/dirty/blocked/failed/cancelled classifications exist.
- **Files:** `lane_x3_post_cycle_lifecycle.py`, `discovery/selection_batch.py`,
  `migrations/026`, V2-9.7B.3 closeout.
- **Reusable primitives:** cooldown/archive/reopen functions, rotation-state table,
  terminal-queue reconciliation.
- **Missing policy:** campaign integration of terminal transitions; candidate
  replacement/rotation across cycles; balanced negative/failed/trap/survival/
  revival example capture.
- **Belongs to:** V2-9.7C design (rotation + replacement policy); V2-9.7D impl.
- **Proof deps:** repeated-cycle fixture; one deterministic terminal transition
  per token; no stale work after terminalization.
- **Money-usefulness:** keeps the corpus fresh and balanced instead of recycling
  the same token.
- **Improves:** diversity, no stale work.
- **Does not unlock:** anything financial.
- **Risks:** revival that reopens without new governed evidence; silent recycle
  inside cooldown.

### R7 — Supervision and recovery
- **Status:** PARTIALLY_COVERED.
- **Coverage:** V2-9.7B.4 hardened heartbeat/lease atomic renewal;
  `proof_supervision.py` preserves first-fault and first-terminal-cause, creates
  no successor, handles operator cancel / budget stop / source failure / host
  interruption / natural completion, and does safe cleanup with report
  availability; `automatic_retries=0`.
- **Files:** `proof_supervision.py`, `migrations/030`,
  `scripts/V2-9-LauncherLogging.ps1`, V2-9.7B.4 closeout.
- **Reusable primitives:** heartbeat/lease, terminal-cause recorder, zero-source
  cleanup, no-restart guarantee.
- **Missing policy:** an operational (persistent-corpus) supervisor; migration 030
  and the launcher are explicitly proof-only.
- **Belongs to:** V2-9.7C design (recovery semantics); V2-9.7D impl.
- **Proof deps:** host-disappearance, cancel, budget, source-failure, natural-
  completion, no-restart tests.
- **Money-usefulness:** a long campaign can fail safely without corrupting the
  corpus or auto-restarting into a bad state.
- **Improves:** long-run reliability.
- **Does not unlock:** anything financial.
- **Risks:** reusing the proof supervisor operationally would carry proof-only
  assumptions.

### R8 — Persistent-corpus safety
- **Status:** PARTIALLY_COVERED; LATER_LANE_DEPENDENCY (operational migration/
  restore).
- **Coverage:** Proof preparation
  (`proof_db_schema_readiness.py`) enforces authoritative-vs-proof isolation,
  byte-identical backup, integrity/FK/runtime-schema checks, and leaves the
  persistent DB unchanged. Persistent DB is at migration 024; 025-030 and their
  tables are absent (per V2-9.7A read-only inspection).
- **Files:** `proof_db_schema_readiness.py`, `migrations/025-030`,
  `data/printer_v1.sqlite3` (not mutated).
- **Reusable primitives:** backup hashing, isolation validator, integrity/FK
  checks.
- **Missing policy:** operational backup/restore, interrupted-copy defense,
  restore rehearsal, row-count/hash reconciliation against the persistent corpus;
  an operational run-ledger mode that does not weaken `db_mode='PROOF_ONLY'`.
- **Belongs to:** V2-9.7D (no migration or DB action in this audit).
- **Proof deps:** migration dry-run on a disposable copy; restore rehearsal.
- **Money-usefulness:** protects the accumulated corpus from loss or partial
  migration.
- **Improves:** corpus durability.
- **Does not unlock:** any DB mutation here.
- **Risks:** migrating the persistent DB without a verified restore.

### R9 — Reporting and report-only replay
- **Status:** PARTIALLY_COVERED.
- **Coverage:** V2-9.7B.1 made authoritative episode promotion the yield source;
  V2-9.7B.2 clarified timeframe-aware safety labels without widening acceptance;
  V2-9.7B.5 embedded immutable Git provenance; `load_report_only()` replays a
  stored report with zero source/evidence deltas. Wallet-level flow authenticity
  correctly reports `TRADING_FLOW_CONTEXT_PARTIAL`/`FLOW_CONTEXT_CAUTION`.
- **Files:** `one_command_15m_factory.py` (`load_report_only`, `_final_report`,
  `_per_token_outcomes`), `e2z_clean_memory_creation.py`, B.1/B.2/B.5 closeouts.
- **Reusable primitives:** report-only replay, authoritative-promotion counts,
  provenance embedding, timeframe-aware safety labels.
- **Missing policy:** operational corpus report (timeframe/continuation yield,
  source efficiency, diversity/concentration, rotation, interruption/shutdown
  state).
- **Belongs to:** V2-9.7C design (report contract); V2-9.7D/E impl + separate
  live report-only replay proof.
- **Money-usefulness:** measures corpus quality by coverage, not raw count.
- **Improves:** honest yield reporting.
- **Does not unlock:** anything financial; wallet authenticity stays PARTIAL/
  CAUTION/UNKNOWN.
- **Risks:** raw row count driving continuation.

### R10 — Transition memory
- **Status:** NEW_REQUIREMENT; CURRENT_EVIDENCE_GAP (categorical vocabulary).
- **Coverage:** Snapshot series can support some transitions (expansion→pullback,
  shakeout→reclaim) from ordered price/liquidity/flow. `printer_episode_outcomes`
  holds `outcome_label`/`action_lesson_label`/`outcome_payload_json`. No fixed
  categorical transition-family vocabulary exists.
- **Files:** `migrations/006`, `014`; adopted trajectory law.
- **Missing policy:** the nine required transition families as approved categorical
  vocabulary; how condition-based comparison (never exact price) records them.
- **Missing evidence:** distribution/insider signals depend on wallet evidence
  (R12) that is absent.
- **Belongs to:** V2-9.7C design; some families gated on R12 later-lane evidence.
- **Money-usefulness:** remembers *how conditions changed*, which is where trade
  timing lives.
- **Does not unlock:** decisions; nominal-price matching stays prohibited.
- **Risks:** inventing transition precision the evidence cannot support.

### R11 — Manipulation-aware opportunity
- **Status:** PARTIALLY_COVERED (principle + some labels); NEW_REQUIREMENT
  (opportunity architecture); CURRENT_EVIDENCE_GAP (integrity/coordination
  evidence).
- **Coverage:** Manipulation-awareness is already anchored: clean-master-spec §
  "price and volume alone are never trusted" (wash-like, thin-liquidity pumps,
  insider-style selling, liquidity removal, pump-dumps); chain-heat labels
  `SOLANA_MEME_MANIPULATED`, `MANIPULATED_TO_ACTIVE`, `DEAD_TO_MANIPULATED`;
  flow labels `MANIPULATED_FLOW`, `WASH_LIKE_FLOW`. Liquidity+Exit engine already
  protects against fake chart profit. **Evidence-quality vs outcome** separation is
  proven (V2-9.4.5). See §5 for the full gap analysis.
- **Files:** clean-master-spec, `migrations/008` (chain heat), `011` (flow),
  `010` (liquidity/exit); `trading_flow/classifier.py`.
- **Missing policy:** the four-way separation as an explicit architecture; the
  manipulation lifecycle; the eight behaviour families; conceptual tradeability
  states; hard-block conditions; the six binding manipulation laws (§13).
- **Missing evidence/source:** market-integrity **condition** evidence
  (coordinated activity, linked/bundled participants, concentrated early ownership,
  suspected insider distribution) has no governed source (§9). Wash-like is a flow
  heuristic, not wallet-proven.
- **Belongs to:** V2-9.7C.0A (law adoption) then V2-9.7C design; integrity/wallet
  evidence is a later source-audit lane.
- **Money-usefulness:** distinguishes a manipulated-but-tradeable opportunity from
  a trap — the core product thesis.
- **Does not unlock:** BUY/SELL/HOLD/WAIT/AVOID/NO_ACTION (all locked); manipulation
  never auto-rejects and never auto-authorizes.
- **Risks:** treating manipulation as automatic rejection (kills the thesis) or as
  license (unsafe); claiming coordination/insider evidence that is not sourced.

### R12 — Wallet and participant evidence
- **Status:** CURRENT_EVIDENCE_GAP; UNKNOWN_REQUIRES_RESEARCH; NON_BLOCKING_LIMITATION
  (for design) / DESIGN_BLOCKER (for later paper-BUY readiness).
- **Coverage:** Holder-concentration category exists in the safety composite
  (`migrations/029`, from GoPlus/RPC holder context). `printer_trading_flow_snapshots`
  has `unique_wallets_*`/`new_wallets_*`/`repeat_wallets_*` columns, but **no
  adapter populates them** (V2-9.4.7 finding) so they are structurally always
  `None`.
- **Files:** `migrations/011`, `029`; `trading_flow/parser.py`; `sources/` (no
  wallet-authenticity adapter).
- **Missing evidence/source:** creator/deployer history, early-buyer concentration,
  related-wallet clusters, bundled accounts, cross-account hidden concentration,
  coordinated timing, early-holder inventory change, genuine-new-participant
  detection. No governed source contributes these; the source-governor evidence
  rules cover only PumpPortal/GeckoTerminal/DexScreener/Solana RPC. The Solana
  Builder transaction-instruction-parsing and core-rpc modules describe on-chain
  parsing capability in principle but no governed Printer request kind produces
  participant-authenticity evidence today.
- **Belongs to:** later source-audit/design lane; not required for V2-9.7C design
  (design labels it UNKNOWN); blocking before any future paper BUY readiness.
- **Money-usefulness:** eventually separates genuine expanding demand from
  coordinated exit liquidity.
- **Does not unlock:** any wallet-authenticity or wash-detection **claim**; wallet
  authenticity must remain UNKNOWN when unproven.
- **Risks:** overstating partial flow as authenticity; adding a paid/wallet source
  without an approved lane.

### R13 — Event-time execution memory
- **Status:** PARTIALLY_COVERED; CURRENT_EVIDENCE_GAP (quantitative execution
  fields).
- **Coverage:** `migrations/023_paper_quote_evidence.sql` records **categorical**
  route availability, slippage context, price-impact context, liquidity context,
  entry/exit realism, freshness, and target match, bound to the exact snapshot
  (entry and exit quote roles). This already distinguishes a chart opportunity from
  a route-available, acceptable-slippage one.
- **Files:** `migrations/023`; `paper_quote/evidence.py`; `context_evidence/window_15m.py`.
- **Missing evidence:** configured position size; position-size-aware price impact;
  numeric slippage/fees; observation/decision/simulated-execution delay; opportunity
  duration; maximum realistically executable size; price change between decision and
  execution; wick-only vs durable classification; failed-route enumeration. The
  Jupiter routing and quote **source-of-truth modules are absent** (§9), so the
  event-time execution contract cannot yet be grounded beyond the categorical labels.
- **Belongs to:** V2-9.7C design (what fields the memory must hold) + later source-
  audit/impl lanes for the quantitative fields.
- **Money-usefulness:** the difference between chart profit and executable profit.
- **Does not unlock:** decisions; no position sizing is activated.
- **Risks:** treating categorical route-available as full executability.

### R14 — Multiple checkpoint decision paths
- **Status:** NEW_REQUIREMENT.
- **Coverage:** Finite predeclared action-path framework and "later outcomes
  evaluate, never rewrite, the checkpoint" are adopted law (trajectory lane).
  `migrations/016_paper_decision_engine.sql` provides a decision table, present but
  **locked** (no writes; `_FORBIDDEN_DELTA_TABLES` enforced).
- **Files:** adopted law; `migrations/016`; forbidden-delta enforcement in
  `one_command_15m_factory.py`.
- **Missing policy:** the predeclared action-path set (BUY/HOLD/SELL/WAIT/AVOID/
  NO_ACTION/fresh-re-entry-review); checkpoint-time-only construction; the four
  good/bad decision-vs-outcome cases; separate-trade-only-after-closed-position.
- **Belongs to:** V2-9.7C design; V2-9.7D+ impl; decision activation is a far
  later, separately gated lane.
- **Money-usefulness:** records disciplined decisions that can be evaluated
  honestly.
- **Does not unlock:** any decision; the schema stays locked.
- **Risks:** post-window invention of an action path; look-ahead into a checkpoint.

### R15 — Contradiction memory
- **Status:** NEW_REQUIREMENT.
- **Coverage:** None. Memory retrieval/similarity schema exists
  (`migrations/015`) but is **locked** and does not represent contradiction.
- **Files:** `migrations/015` (locked).
- **Missing policy:** categorical representation of consistent / mixed-with-clear-
  separator / material-conflict-unresolved / no-comparable-memory / evidence-
  insufficient, and a default to WAIT/AVOID/NO_ACTION under unresolved conflict —
  all without scores, ranks, confidence, or weights.
- **Belongs to:** V2-9.7C design; retrieval activation is far later.
- **Money-usefulness:** refuses to force a trade when the corpus disagrees.
- **Does not unlock:** retrieval or decisions.
- **Risks:** smuggling a similarity score to "resolve" conflict.

### R16 — Balanced corpus coverage
- **Status:** NEW_REQUIREMENT; PARTIALLY_COVERED (counting primitives).
- **Coverage:** `printer_episode_outcomes` indexes `outcome_label`,
  `action_lesson_label`, `window_kind`, token/pair — enough to *count* coverage.
  V2-9.7A/B reporting recommends diversity/concentration reporting.
- **Files:** `migrations/014`; reporting recommendations in V2-9.7A.
- **Missing policy:** coverage sufficiency defined over path families (the ~22
  listed) rather than raw count; concentration risk across token/pair/source/venue/
  outcome/timeframe/regime/manipulation/participant.
- **Belongs to:** V2-9.7C design (corpus-quality contract); later reporting impl.
- **Money-usefulness:** prevents a winner-heavy or concentrated corpus.
- **Does not unlock:** anything financial.
- **Risks:** raw count treated as sufficiency.

### R17 — Recency and market-drift handling
- **Status:** NEW_REQUIREMENT.
- **Coverage:** `market_regime` (`007`) and `chain_heat` (`008`) capture context
  per episode. No categorical current-vs-historical relationship exists; correctly,
  no time-decay weighting exists.
- **Files:** `migrations/007`, `008`.
- **Missing policy:** categorical regime-relationship vocabulary (match/adjacent/
  historical-only/stale-pattern/new-unseen) preserving old memories without treating
  them as current, and explicitly no hidden score or time-decay.
- **Belongs to:** V2-9.7C design.
- **Money-usefulness:** stops stale patterns from silently governing new conditions.
- **Does not unlock:** anything financial.
- **Risks:** a "recency weight" that becomes hidden scoring.

### R18 — Frozen chronological validation
- **Status:** NEW_REQUIREMENT; LATER_LANE_DEPENDENCY.
- **Coverage:** `load_report_only()` is a zero-source replay primitive. No frozen-
  corpus, walk-forward, unseen-episode evaluation architecture exists.
- **Files:** `one_command_15m_factory.py::load_report_only` (primitive only).
- **Missing policy/impl:** the 13-point proof architecture (freeze corpus + rules,
  chronological unseen episodes, no future data, realistic fees/slippage/impact/
  latency/failed-routes, NO_ACTION/baseline comparison, regime/path separation,
  winners/losers/traps/revivals/dead, forward-tracking rejected tokens, no rescue
  edits, repeated walk-forward, drawdown/fragility/concentration/capital-protection
  reporting).
- **Belongs to:** far later proof lanes (beyond V2-9.7C/D); design must name the
  controls so implementation can build them.
- **Money-usefulness:** the only honest test of whether Printer is money-useful.
- **Does not unlock:** anything; requires decisions to exist first.
- **Risks:** proving on the same history used to invent the rules.

### R19 — Optional operator capital policy with permanent safety invariants
- **Status:** NEW_REQUIREMENT; LATER_LANE_DEPENDENCY.
- **Coverage:** Permanent invariants are already anchored in AGENTS.md and the
  clean master spec (Source Governor, Central Scheduler, exact identity,
  auditability, supervision, safe stop, no restart, non-retroactive reporting, no
  dirty memory in retrieval/decisions, Solana-only/paper-only, no live funds, all
  capability locks). No capital-policy schema or config interface exists.
- **Files:** AGENTS.md, clean-master-spec; `migrations/016-018` (locked decision/
  monitor/audit scaffolding).
- **Missing policy:** the optional capital-policy field set; CAPITAL_POLICY_OFF/
  CUSTOM modes (research-only, never disabling permanent invariants); the
  risk-reducing-vs-risk-increasing application-boundary rule; the versioned,
  auditable, non-retroactive config contract; "an active losing position cannot
  rewrite its own rules."
- **Belongs to:** V2-9.7C design (contract shape) + far later impl gated behind
  paper-decision activation.
- **Money-usefulness:** bounds paper risk during future research without weakening
  safety.
- **Does not unlock:** any capital control, position, or PnL; no runnable command.
- **Risks:** an "off" mode that disables a permanent invariant; a config path that
  applies risk-increasing changes to an open position.

**Coverage check:** 19 rows, one per requirement, none omitted, merged, or
substituted.

## 4. Current Reusable-Component Map

| Component | File(s) | Reuse for |
|---|---|---|
| Run ledger + steps | `migrations/028`, `one_command_15m_factory.py` | R1 campaign identity base |
| Exact 15m→1h→4h continuation | `lifecycle_continuity.py`, `one_token_4h_runtime.py` | R2 selective continuation |
| Budget/ceiling enforcement | `one_command_15m_factory.py` | R3 fairness/budgets |
| Exact-linked 5m support | `_capture_same_stream_5m_support`, `lane_x8_5m_support_integration.py` | R4 conditional 5m |
| Ordered snapshot series + phase column | `migrations/006`, `014` | R5 trajectory |
| Cooldown/archive/reopen + rotation state | `lane_x3_post_cycle_lifecycle.py`, `migrations/026` | R6 lifecycle/rotation |
| Heartbeat/lease + terminal cause + no-restart | `proof_supervision.py` (B.4) | R7 supervision |
| Proof isolation + backup hashing | `proof_db_schema_readiness.py` | R8 corpus safety |
| Authoritative promotion + report-only replay + Git provenance | `e2z_clean_memory_creation.py`, `load_report_only`, B.1/B.5 | R9 reporting |
| Episode outcomes + lesson labels | `migrations/014` | R10/R16 outcome + coverage |
| Chain-heat/flow manipulation labels | `migrations/008`, `011` | R11 integrity condition (categorical) |
| Safety composite (holder concentration) | `migrations/029` | R12 partial concentration |
| Paper quote evidence (categorical realism) | `migrations/023` | R13 execution realism |
| Locked decision/retrieval/audit scaffolding | `migrations/015-018` | R14/R15/R19 (locked) |
| Evidence-quality vs outcome separation | V2-9.4.5, `trading_flow`, `chart_volatility` | R11 four-way separation, layer 1/2 |
| Forbidden-delta enforcement | `one_command_15m_factory.py::_FORBIDDEN_DELTA_TABLES` | all: keeps financial locks |

## 5. Manipulation-Aware Opportunity Gap Analysis

**Product direction preserved:** Printer is not an organic-coin detector.
Manipulation is a market condition to understand, not an automatic rejection. Its
role is to determine whether a current opportunity is supported by trustworthy
evidence, realistically tradable, realistically executable, still early enough,
and safely exitable — never to judge whether a token is "fair."

### Four-way separation readiness

| Layer | Status | Evidence today | Gap |
|---|---|---|---|
| 1. Evidence quality (can Printer trust what it captured?) | PARTIALLY_COVERED | Proven: clean/dirty/audit gates; a manipulated token can still be CLEAN_MEMORY (V2-9.4.5) | None material; extend to trajectory |
| 2. Market-integrity condition (what may drive activity?) | CURRENT_EVIDENCE_GAP | Categorical `MANIPULATED_FLOW`, `WASH_LIKE_FLOW`, `SOLANA_MEME_MANIPULATED`; liquidity-inflation via liquidity/exit | Coordinated/linked/bundled/insider/concentration evidence unsourced (R12) |
| 3. Tradeability (could Printer realistically participate?) | PARTIALLY_COVERED | Categorical route/slippage/impact/liquidity/entry-exit realism (`023`) | Position-size-aware impact, duration, delay, max size, wick-vs-durable, bot-speed (R13) |
| 4. Action eligibility (future outcomes) | NEW_REQUIREMENT (LOCKED) | Decision schema exists, locked | Predeclared action-path set; stays locked (R14) |

### Eight manipulation behaviour families — all covered

| # | Behaviour | Readiness | Note |
|---|---|---|---|
| 1 | Coordinated markup | NEW + integrity/wallet gap | early tradable → later exit liquidity; needs transition (R10) + coordination evidence (R12) |
| 2 | Wash-driven attention | PARTIALLY (flow `WASH_LIKE`) | must distinguish artificial vs genuine expansion; volume alone cannot authorize |
| 3 | Liquidity-based price inflation | PARTIALLY (liquidity/exit) | needs position-size-aware entry/exit evidence (R13) |
| 4 | Insider distribution into public demand | CURRENT_EVIDENCE_GAP | concentrated-holder selling evidence unsourced (R12) |
| 5 | Manipulated shakeout | NEW | re-entry needs current reclaim/liquidity/flow/execution (R10/R13) |
| 6 | Fake recovery | NEW | price reclaim while liquidity/exit weakens; future WAIT/AVOID/NO_ACTION |
| 7 | Bot-dominated opportunity | NEW + CURRENT_EVIDENCE_GAP | chart profit visible but entry unproven; NO_ACTION correct; needs bot-speed/duration evidence |
| 8 | Post-manipulation revival | PARTIALLY (reopen primitive) | prior manipulation must not permanently auto-reject; fresh setup review |

### Manipulation lifecycle & tradeability states

The ten-stage lifecycle (quiet preparation → artificial activity → attention
expansion → wider participation → first distribution → shakeout/continuation →
second expansion/failed recovery → heavy distribution → liquidity deterioration →
collapse/survival/revival) has **no production vocabulary today**. V2-9.7C must
define it categorically without inventing unsupported precision. Conceptual
tradeability states (`MANIPULATED_BUT_TRADEABLE`,
`MANIPULATED_AND_EXIT_DETERIORATING`, `MANIPULATED_AND_UNTRADEABLE`) are examples
only — not approved labels.

### Hard-block conditions

The future design must block entry when any material condition is insufficient:
contaminated/mismatched/stale/malformed/untraceable evidence; missing route or
quote; removed/unusable liquidity; impossible/unproven exit; unacceptable
position-size impact; opportunity duration below execution need; source/scheduler
provenance failure; unknown tradeability that cannot fail safely. Several of these
are already enforced as fail-closed gates for memory (evidence contamination,
route/quote absence, provenance failure); the design extends them to future
action eligibility. None is a decision today.

## 6. Tradeable Path and Money-Usefulness Gap Analysis

**Binding distinction preserved:** a memory can have a negative final outcome
while containing several profitable, realistically tradable segments. A complete
15m/1h/4h lifecycle must never be reduced to one pump/consolidation/dump label.

### Two outcome layers

| Layer | Status | Evidence | Gap |
|---|---|---|---|
| 1. Full-window outcome | PARTIALLY_COVERED | `episode_outcome_label` (round trip, dump, pump-and-dump, dead, etc.) | keep as-is |
| 2. Internal trade-opportunity outcome | NEW_REQUIREMENT | none | `opportunity_segments` object; must stay separate from Layer 1 |

Layer 2 (early expansion, valid hold, exit opportunity, shakeout, reclaim, fresh
entry, second expansion, late distribution, correctly-avoided late chase,
unproven capturable exit, final breakdown) has no schema today.

### Twelve tradeable-path contexts — all covered

| # | Context | Status | Primary dependency |
|---|---|---|---|
| 1 | Expansion, pullback, continuation | NEW | R10 transition + R13 execution |
| 2 | Expansion then failed continuation | NEW | R10 + R14 action paths |
| 3 | Fast breakdown then genuine reclaim | NEW + evidence gap | R10 + R13 + liquidity durability |
| 4 | Wick-only peak | PARTIALLY (peak-vs-exit law) | R13 event-time exit liquidity |
| 5 | Price rising while exit deteriorates | PARTIALLY (liquidity/exit) | R12 seller expansion + R13 shrinking size |
| 6 | High volume, weak authenticity | PARTIALLY (flow UNKNOWN) | R12 participant authenticity |
| 7 | Good entry, bad hold | NEW | R14 checkpoint states |
| 8 | Bad entry, profitable outcome | NEW | R14 (no reinforcement of reckless entry) |
| 9 | Correct exit then more upside | PARTIALLY (peak-vs-exit + re-entry law) | R14 fresh re-entry review |
| 10 | Missed entry, no-chase | PARTIALLY (anti-look-ahead law) | R14 WAIT/NO_ACTION |
| 11 | Re-entry churn | PARTIALLY (re-entry law adopted) | R14 + R19 bounded re-entry |
| 12 | Market-context mismatch | PARTIALLY (regime/chain heat) | R17 regime relationship |

### Connected memory objects

| Object | Partial equivalent today | Gap |
|---|---|---|
| `window_outcome` | `printer_episode_outcomes.outcome_label` | keep |
| `ordered_trajectory_phases` | snapshot series + `created_by_phase` | vocabulary (R5) |
| `checkpoint_states` | none | new (R5/R14) |
| `opportunity_segments` | none | new (Layer 2) |
| `eligible_action_paths` | locked decision schema | new + locked (R14) |
| `position_state_transitions` | locked monitor schema (`017`) | new + locked |
| `entry_execution_evidence` | `paper_quote_evidence` entry role | quantitative fields (R13) |
| `exit_execution_evidence` | `paper_quote_evidence` exit role | quantitative fields (R13) |
| `post_exit_reentry_reviews` | re-entry law only | new (R14) |
| `manipulation_and_authenticity_context` | flow/chain-heat labels | integrity + wallet evidence (R11/R12) |
| `unknown_or_unproven_fields` | UNKNOWN labelling convention | formalize |
| `realized_paper_outcomes` | locked audit schema (`018`) | new + locked |

### Money-usefulness diagnostics (must stay separate fields, never a score)

Chart return; executable paper return; fees; slippage; price-impact cost; MAE;
MFE; avoided loss; missed upside; re-entry churn; time in position; observed-peak
vs executable-exit gap; correct/incorrect WAIT; correct/incorrect AVOID. **None**
exists as a diagnostic field today; all are new. They must never combine into a
score, rank, confidence percentage, or weighted decision.

### Anti-hindsight audit

The already-adopted trajectory/checkpoint law prohibits: later outcomes
supporting an earlier checkpoint's action; nominal-price matching; observed peaks
as capturable profit; using the completed path to alter an earlier decision.
**Not yet fully anchored** as explicit prohibitions and required for V2-9.7C:
buying the exact reconstructed bottom; selling every local top; rebuying every
completed-chart pullback; selling the exact ATH without event-time evidence;
post-window invention of an action path. The design must require a finite,
predeclared action-path framework where each checkpoint preserves only
information known at that time, current position state, eligible/blocked actions
with reasons, realistic entry/exit evidence, and uses later outcome for
evaluation only. This gap is a **design-must-anchor item**, addressed by the
proposed money-usefulness law in §13.

## 7. Wallet and Participant Evidence Gap Analysis

| Capability | Status | Source today |
|---|---|---|
| Creator/deployer history | CURRENT_EVIDENCE_GAP | none governed |
| Early-buyer concentration | CURRENT_EVIDENCE_GAP | none (holder concentration ≠ early-buyer) |
| Related-wallet clusters | CURRENT_EVIDENCE_GAP; UNKNOWN_REQUIRES_RESEARCH | none |
| Bundled accounts | CURRENT_EVIDENCE_GAP; UNKNOWN_REQUIRES_RESEARCH | none |
| Cross-account hidden concentration | CURRENT_EVIDENCE_GAP | none |
| Coordinated transaction timing | CURRENT_EVIDENCE_GAP | instruction-parsing module describes parsing in principle; no governed request kind |
| Early-holder inventory change | CURRENT_EVIDENCE_GAP | none |
| Participant expansion / genuine-new-demand | CURRENT_EVIDENCE_GAP | flow counts exist; authenticity does not |
| Holder concentration (coarse) | PARTIALLY_COVERED | safety composite (`029`) |
| Wallet authenticity when unprovable | HONEST UNKNOWN (required) | must remain UNKNOWN |

This whole family is **non-blocking for V2-9.7C design** (the design labels it
UNKNOWN and gates dependent behaviour), but **blocking before any future paper
BUY readiness**. No wallet or paid source may be added without a separate approved
source-audit/design lane.

## 8. Event-Time Execution Evidence Gap Analysis

`CHART OPPORTUNITY` vs `REALISTICALLY EXECUTABLE OPPORTUNITY`:

| Field | Status | Source |
|---|---|---|
| Event-time quote (entry/exit) | PARTIALLY_COVERED | `paper_quote_evidence` (categorical) |
| Route availability | PARTIALLY_COVERED | `route_available_label` |
| Usable liquidity | PARTIALLY_COVERED | `liquidity_context_label` |
| Slippage / price impact (categorical) | PARTIALLY_COVERED | `slippage_context_label`, `price_impact_context_label` |
| Configured position size | CURRENT_EVIDENCE_GAP | none |
| Position-size-aware impact | CURRENT_EVIDENCE_GAP | none |
| Numeric slippage / fees | CURRENT_EVIDENCE_GAP | none |
| Observation / decision / execution delay | CURRENT_EVIDENCE_GAP | none |
| Opportunity duration | CURRENT_EVIDENCE_GAP | derivable from snapshot spacing; not recorded as such |
| Max realistically executable size | CURRENT_EVIDENCE_GAP | none |
| Price change decision→execution | CURRENT_EVIDENCE_GAP | none |
| Wick-only vs durable | CURRENT_EVIDENCE_GAP | peak-vs-exit law only |
| Failed/unavailable routes | PARTIALLY_COVERED | `quote_failure_label` |

The Jupiter routing and quote source-of-truth modules are **absent** (§9), so the
quantitative execution contract cannot be grounded beyond the existing categorical
labels without a source-audit lane.

## 9. Current Evidence and Source Capability Map

Solana Builder module existence (verified read-only):

| Module | Present? |
|---|---|
| README | YES |
| source-governor-evidence-rules | YES |
| solana-core-rpc-reference | YES |
| solana-transaction-instruction-parsing | YES |
| solana-public-rpc-contract | **NO → CURRENT_EVIDENCE_GAP** |
| pump-fun-bonding-curve-protocol | YES |
| pumpswap-amm-protocol | **NO** (narrower `pumpswap-pool-confirmation-contract` present) → CURRENT_EVIDENCE_GAP |
| pumpportal-api-contract | YES |
| goplus-api-contract | **NO → CURRENT_EVIDENCE_GAP** (code adapter exists; contract doc absent) |
| dexscreener-api-contract | YES |
| geckoterminal-api-contract | **NO → CURRENT_EVIDENCE_GAP** (code adapter exists; contract doc absent) |
| jupiter-routing-protocol | **NO → CURRENT_EVIDENCE_GAP** |
| jupiter-quote-api-contract | **NO → CURRENT_EVIDENCE_GAP** |

Capability map (grounded in `source-governor-evidence-rules.md` and repository
schema; no capability inferred from model memory):

| Capability | Authoritative source | Status | Clean-capable? | Blocks |
|---|---|---|---|---|
| Price & trajectory | DexScreener / GeckoTerminal | READY | yes | — |
| Liquidity | DexScreener (approx PumpPortal) | READY | yes | — |
| Transaction activity | DexScreener / GeckoTerminal | READY | yes | — |
| Timeframe price change (15m) | GeckoTerminal candle | READY | yes | — |
| Pool identity & age | DexScreener `pairCreatedAt` (T4) | READY | yes | — |
| Token identity & age | Solana RPC T3 / PumpPortal T2 | READY | yes | — |
| Route & quote | (Jupiter code adapter; **no source-of-truth doc**) | PARTIAL | categorical only | R13, paper readiness |
| Price impact / slippage | paper_quote (categorical) | PARTIAL | categorical only | R13 |
| Event duration | derivable, not recorded | GAP | — | R13 |
| Wallet/participant authenticity | none governed | GAP; UNKNOWN_REQUIRES_RESEARCH | no | R11/R12, paper BUY |
| Creator/deployer history | none | GAP | no | R12 |
| Concentration (coarse) | safety composite | PARTIAL | yes (coarse) | R11/R12 |
| Linked/bundled accounts | none | GAP; UNKNOWN_REQUIRES_RESEARCH | no | R12 |
| Early-holder inventory change | none | GAP | no | R10/R12 |
| Coordination evidence | none governed | GAP | no | R11/R12 |
| Wash-like activity | flow heuristic | PARTIAL | categorical | R11 (not wallet-proven) |
| Distribution evidence | none (needs wallet) | GAP | no | R10/R11 |
| Liquidity withdrawal | DexScreener liquidity delta / A4 | PARTIAL | yes | R10/R11 |
| Wider Solana context | chain heat (DefiLlama) | READY | yes | — |
| Market-regime context | market regime (CoinGecko) | READY | yes | R17 |
| Source provenance | Source Governor traces | READY | yes | — |
| Scheduler provenance | Central Scheduler rows | READY | yes | — |
| Report-only replay | `load_report_only` | READY | yes | — |
| Immutable Git provenance | B.5 embedded HEAD/tree | READY | yes | — |

## 10. Design Blockers

No blocker prevents **this audit** from passing, and none prevents **V2-9.7C
design** from proceeding (design may specify policy while labelling evidence gaps
UNKNOWN). The following are blockers for **later** stages, recorded so the design
does not overreach:

1. Market-integrity **condition** evidence (coordinated/linked/bundled/insider) —
   blocks future manipulation-integrity *claims* and paper BUY, not design.
2. Wallet/participant authenticity — blocks paper BUY readiness (R12).
3. Quantitative event-time execution fields + absent Jupiter source-of-truth —
   block executable-opportunity *measurement* (R13), not the categorical design.
4. Operational persistent-corpus migration/restore — blocks implementation/pilot
   (R8), not design.
5. Frozen chronological validation architecture (R18) — blocks any money-
   usefulness *claim*, which is far downstream.

## 11. Non-Blocking Limitations

- Wallet authenticity remains UNKNOWN and must be reported as PARTIAL/CAUTION.
- Execution realism is categorical, not position-size-quantified.
- Manipulation labels are heuristic (flow/chain-heat), not wallet-proven.
- The persistent DB is six migrations behind proof schema (read-only fact).
- 5m support is currently unconditional; the design adds the trigger gate.

## 12. Later-Lane Dependencies

- **V2-9.7C.0A:** adopt the manipulation-aware + money-usefulness product laws
  (§13). Documentation-only.
- **V2-9.7C:** campaign design; selective continuation; fairness; conditional 5m
  triggers; trajectory/checkpoint/action-path representation; transition/
  contradiction/coverage/recency vocabulary; manipulation lifecycle + four-way
  separation + tradeability states + hard-blocks; two-layer outcomes; connected-
  object shape; capital-policy contract shape; report contract; proof requirements.
- **V2-9.7D:** operational schema/migration, persistent preflight/backup/restore,
  operational supervisor, bounded multi-cycle command, report-only replay impl.
- **V2-9.7E:** two-token pilot; fairness/no-starvation proof; selective
  continuation proof.
- **Later source-audit lane(s):** Jupiter route/quote and wallet/participant
  evidence contracts; the six absent source-of-truth modules.
- **Far-later paper lanes:** decision/action-path activation, capital-policy impl,
  frozen chronological validation (R18), and any BUY/SELL/HOLD, position, trade,
  audit, or PnL — each separately gated.

## 13. Proposed Binding Product Laws for V2-9.7C.0A Adoption

Assembled here for a **separate** adoption lane. Not adopted in this audit.

**Manipulation laws (verbatim intent):**
1. Printer must not automatically exclude a token merely because its activity
   appears manipulated.
2. Manipulation, coordination, artificial activity, concentrated ownership, and
   uncertain participant authenticity are market-context and integrity evidence,
   not automatic action outcomes.
3. A manipulated token may still produce clean memory when the underlying
   observation satisfies clean-evidence requirements.
4. Future approved paper actions may consider manipulated conditions only when
   evidence quality, route availability, liquidity durability, execution realism,
   and exit capability are sufficient.
5. Printer's objective is to distinguish manipulated moves that remain
   realistically tradeable from manipulated moves that trap participants or
   eliminate realistic exit capability.
6. Printer must be fully disciplined about rules, evidence boundaries, timing, and
   exit requirements, and must not claim certainty about future price.

**Money-usefulness / tradeable-path laws (proposed):**
7. Full-window outcome (Layer 1) and internal trade-opportunity outcome (Layer 2)
   are separate and must never be merged; a negative window may contain
   profitable, realistically tradable segments.
8. Chart profit is not executable profit; observed peaks/ATH are chart facts until
   event-time route, liquidity, slippage, impact, duration, and exit evidence
   prove capturability.
9. Money-usefulness diagnostics are separate fields and must never combine into a
   score, rank, confidence percentage, or weighted decision.
10. Anti-hindsight: no checkpoint may use later information; action paths are
    finite and predeclared; later outcomes evaluate but never rewrite a
    checkpoint; no post-window action-path invention; no exact-bottom/exact-top
    reconstruction.
11. The optional operator capital policy is research-only; `CAPITAL_POLICY_OFF`
    may relax operator-selected limits during bounded paper research but may never
    disable any permanent Printer safety invariant; risk-increasing changes apply
    only before a new position or at an approved boundary; an active losing
    position cannot rewrite its own rules.

## 14. Exact Files Recommended for the Later Adoption Step

Adoption (in V2-9.7C.0A, **not** this lane), minimizing duplication:

- **New:** `docs/printer-v1-manipulation-aware-money-usefulness-product-law.md` —
  the single authoritative home for laws 1-11.
- **Update (reference, not duplicate):**
  `docs/printer-v1-memory-growth-build-order-v2.md` — extend the V2-9.7C gate
  (§854-869) to require the manipulation four-way separation, two-outcome layers,
  tradeability hard-blocks, and capital-policy contract.
- **Update (guidance):** `docs/printer-v1-memory-factory-guide.md` — operating
  guidance for the two-layer outcome and manipulation-context capture.
- **Clean master spec:** anchor only the two enduring invariants that must live at
  product-law level — "manipulation is a condition, not an automatic rejection"
  and "chart profit is not executable profit / Layer 1 ≠ Layer 2" — by reference
  to the new law document, since the spec already carries the manipulation-aware
  principle (§ price-and-volume-never-trusted) and can extend it without
  duplication.
- **AGENTS.md:** no change recommended. The existing anchors already preserve the
  V2 source stack, Source Governor/Central Scheduler enforcement, and every
  capability lock; the new laws are safely referenced through the narrower active
  stack.

Do not modify any of these in this audit.

## 15. V2-9.7C Design Acceptance Criteria

The later V2-9.7C design PASSES only if it:
1. Traces every one of the 19 requirements to a design element.
2. Preserves the existing committed V2-9.7C gate (build-order-v2 §854-869):
   trajectory representation, phase/reversal vocabulary, checkpoint construction,
   anti-look-ahead, action-path evaluation, continuous checkpoint review, re-entry
   semantics, peak-vs-exit separation, lifecycle-wide conditional 5m triggers +
   exact parent linkage, 5m non-authority, and minimum sufficient proof.
3. Preserves every manipulation obligation: four-way separation, eight behaviour
   families, the lifecycle, hard-block conditions, and laws 1-6.
4. Preserves the tradeable-path obligations: two separate outcome layers, twelve
   contexts, connected-object shape, and laws 7-11.
5. Distinguishes design-ready policy from later evidence/source gaps and labels
   every gap UNKNOWN/CURRENT_EVIDENCE_GAP rather than inventing capability
   (especially wallet/participant and quantitative execution fields).
6. Defines the optional capital-policy contract with permanent invariants
   non-optional and the risk-reducing/increasing application boundary.
7. Names the frozen chronological validation controls for later proof lanes
   without implementing them.
8. Provides enough state, identity, lifecycle, evidence, reporting, and safe-stop
   detail for V2-9.7D implementation without inventing policy.
9. Keeps all retrieval, decision, position, PnL, command-release, and real-funds
   capabilities locked, with zero campaign deltas.

## 16. Money-Usefulness Contribution

This audit converts a large, ambitious product vision into a disciplined,
traceable readiness map. It prevents the most expensive mistake available at this
stage: designing a manipulation-aware, tradeable-path decision system on top of
evidence Printer does not actually collect — wallet authenticity, coordination,
and quantitative execution. By separating what is proven (the operational-factory
foundation and the evidence-quality-vs-outcome distinction) from what is genuinely
new and what is an unsourced gap, it lets V2-9.7C design the policy that is safe to
design now and defer the rest to explicit source and proof lanes.

## 17. What This Audit Improves

- One canonical, traceable row per requirement, with grounded status.
- A clear boundary between the ready foundation (R1-R9) and the new opportunity
  layer (R10-R19).
- Honest naming of two unsourced pillars (integrity condition, wallet evidence)
  and six absent source-of-truth modules.
- An assembled, adoption-ready law set that does not duplicate existing spec text.
- Acceptance criteria that bind the later design to the committed gate plus the
  new obligations.

## 18. What Remains Locked

Operational memory growth and any campaign write; the operational command; V2-9.8
activation; V2-10 and all 12h/24h work; retrieval activation and retrieval in
decisions; paper decisions and BUY/SELL/HOLD/WAIT/AVOID; positions, trade events,
paper trade audits, and PnL; live trading, execution, signing, wallets, private
keys, and real funds; paid APIs; scoring, ranking, confidence percentages,
weighted logic, embeddings, and vectors; Source Governor / Central Scheduler
bypass; dirty memory in retrieval or decisions; 5m as a main outcome, threshold,
or continuation trigger; any wallet-authenticity claim.

## 19. Proof Required Before Later Completion

- V2-9.7C.0A: static adoption of laws 1-11 (documentation-only).
- V2-9.7C: static design checks (anti-look-ahead, 5m non-authority, lock scans,
  19-requirement trace).
- V2-9.7D: operational schema/migration/restore rehearsed on disposable copies;
  focused integration tests for clean/dirty/blocked, idempotency, interruption
  recovery, terminal failure, and zero retrieval/financial deltas.
- V2-9.7E: bounded two-token pilot; fairness and selective-continuation proof;
  separate zero-source report-only replay.
- Later source-audit lanes: Jupiter route/quote and wallet/participant evidence.
- Far-later: frozen chronological walk-forward validation before any money-
  usefulness claim.

## 20. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Consequence | Control |
|---|---|---|
| Designing manipulation/tradeability on unsourced evidence | False integrity or executability claims | Label integrity/wallet/execution gaps UNKNOWN; gate dependent policy |
| Six absent source-of-truth modules | Ungoverned reliance on Jupiter/GoPlus/Gecko capabilities | Require a source-audit lane before grounding R11/R12/R13 quantitatively |
| Money-usefulness diagnostics collapsing into a score | Violates V1 no-scoring law | Keep every diagnostic a separate field; risky-language scan |
| Manipulation treated as auto-reject or auto-license | Kills the thesis, or unsafe entry | Laws 1-6; manipulation is context, never an action |
| Layer 1 and Layer 2 merged | A profitable-segment lesson lost in a negative label | Law 7; separate connected objects |
| Chart profit read as executable | Fake money-usefulness | Law 8; event-time exit evidence (R13) |
| Capital-policy "off" disabling an invariant | Safety erosion | Law 11; permanent invariants non-optional |
| Frozen validation skipped | Proving on the same history that made the rules | R18 controls named now, enforced later |
| Persistent DB migrated without restore rehearsal | Corpus loss | V2-9.7D backup/hash/restore before any migration |
| Scope creep from this audit into design/adoption | Premature policy or unlock | This lane is audit-only; adoption and design are separate gated lanes |

## 21. Verification Results

Static, risk-based verification only.

- 19 canonical requirements: exactly one matrix row each (§3); none omitted,
  merged, or substituted — verified by enumeration R1-R19.
- Eight manipulation behaviours: all covered (§5).
- Twelve tradeable-path contexts: all covered (§6).
- Two outcome layers: covered and kept separate (§6).
- Four-way separation: covered (§5).
- Chronological-validation requirements: covered (R18, §6, §19).
- Revised optional capital-policy requirements: covered (R19, law 11).
- Permanent safety invariants: enumerated and kept non-optional (§18, law 11).
- Active source-stack consistency: read and cross-referenced; no contradiction
  introduced.
- Source-capability claims grounded in repository documents (§9); no capability
  taken from model memory.
- Missing source capability labelled `CURRENT_EVIDENCE_GAP` /
  `UNKNOWN_REQUIRES_RESEARCH` (§7, §8, §9).
- Solana-only / Solana-memecoin-only / paper-only consistency: preserved.
- No Source Governor or Central Scheduler bypass proposed.
- No dirty-memory authorization; no scoring/ranking/confidence/weighted logic/
  embeddings/vectors introduced.
- No retrieval/decision/BUY/position/trade/audit/PnL/wallet/key/signing/real-funds
  activation language.
- No runnable operational PowerShell command present.
- Only the approved audit document is added (§22).
- Unrelated untracked artifacts untouched (165 baselined).
- `git diff --check`: clean.

## 22. Files Changed

- `docs/printer-v1-v2-9-7c-0-money-usefulness-requirements-readiness-audit.md`
  (this file).

No code, test, schema, migration, database, or active source-law document was
changed.

## 23. Final Verdict and Next Permitted Lane

`V2_9_7C_0_MONEY_USEFULNESS_REQUIREMENTS_AUDIT_PASS`

The nineteen requirements and their nested obligations are traceable; current
coverage, gaps, blockers, and later dependencies are explicit; the proposed
product laws are assembled for a separate adoption lane; and the repository is
ready for **V2-9.7C.0A product-law adoption**.

This PASS authorizes nothing further. It does not adopt product law, change the
active build order, begin V2-9.7C design, or unlock any runtime, memory,
retrieval, decision, position, trade, audit, PnL, wallet, key, signing, live
execution, or real-funds capability.

Next permitted lane: **V2-9.7C.0A — adopt the manipulation-aware and
money-usefulness product laws** (documentation-only), followed by V2-9.7C design.
