# Printer V1 V2-9.7C Operational Memory Factory Design Closeout

## 1. Verdict

`V2_9_7C_OPERATIONAL_MEMORY_FACTORY_DESIGN_PASS`

The bounded two-token Operational Memory Factory campaign is fully specified at
the design level. V2-9.7D can prepare implementation in a separate lane without
inventing campaign, evidence, trajectory, manipulation, opportunity, policy,
reporting, replay, persistence, or safe-stop semantics.

PASS does not authorize implementation, runtime, operational memory growth,
source calls, DB mutation, retrieval, decisions, positions, PnL, command
release, MCP connection, wallets, signing, execution, or real funds.

## 2. Preflight and Scope

- Starting HEAD: exact `5c77651c778e1b093d4e2a33012c8e2c49d1b905`.
- Tracked tree: clean before editing.
- Windows denied process command-line inspection; the limitation is recorded
  honestly under the permitted design-only fallback.
- Visible process state showed PowerShell processes and no Python process.
- No readable proof, campaign, or runtime lock was found.
- Unrelated untracked artifacts remained untouched.
- Scope remained static design and documentation only.

No tests, runtime, APIs, RPC, providers, MCP, source adapters, discovery,
scheduler, memory generation, proof, or database command ran.

## 3. Design Adopted

The design binds this full flow:

```text
discovery -> selection -> tracking -> governed collection
-> conditional WINDOW_5M_MICRO_EVENT support -> WINDOW_15M closeout
-> selective per-token WINDOW_1H -> conditional per-token WINDOW_4H
-> clean/dirty/blocked audit -> cooldown/archive -> replacement/rotation
-> persistent corpus reporting -> report-only replay -> safe stop
```

Initial active capacity is exactly two tokens. Every token begins at 15m, and
no rule tracks every timeframe for every token.

## 4. Canonical Requirements

The design contains exactly one canonical traceability row for each of R1-R19.
Each row records its design element, identities/state, evidence, unknowns,
implementation dependency, bounded proof, failure/stop behavior,
money-usefulness contribution, locks, and Functionality Risks / Setbacks /
Efficiency Blockers.

Coverage includes campaign model; selective continuation; fairness/budgets;
conditional 5m; trajectory/checkpoints; lifecycle/rotation;
supervision/recovery; persistent-corpus safety; reporting/replay; transitions;
manipulation; wallet/participant gaps; event-time execution; finite checkpoint
paths; contradiction; balanced coverage; recency/drift; frozen chronological
validation; and optional capital policy with permanent invariants.

## 5. Identity, State, and Fairness Decisions

The design fixes campaign, run, cycle, exact mint/token, exact pair, lifecycle,
main/support window, predecessor, scheduler work, source provenance, policy, Git,
report, and replay identities. It defines terminal campaign/cycle/token/window/
report states, immutable first terminal cause, idempotent cancellation/cleanup,
and no-successor/no-automatic-restart behavior.

Two-token fairness uses close-boundary deadline priority, fairness rounds,
token-local failure isolation, finite ceilings, zero ordinary automatic retries,
and review stop at any failed requirement or ceiling.

## 6. Continuation and 5m Decisions

Continuation uses fixed categorical verdicts and exact predecessor continuity.
Dirty, blocked, stale, mismatched, unsupported, untraceable, missing mandatory,
or budget-exhausted evidence blocks continuation. Scores, ranks,
probabilities, confidence, and weighting are prohibited.

The six fixed 5m trigger families include positive capture and negative
no-capture scenarios across 15m/1h/4h lifecycles. Every support object exact-links
its campaign/run/cycle/token/pair/root-15m/containing-window/snapshots/source/
scheduler identities. 5m remains support-only and non-authoritative.

## 7. Trajectory, Manipulation, and Opportunity Decisions

Fixed categorical vocabularies cover ordered phases, reversals, consolidation,
breakdown, reclaim, distribution, liquidity deterioration, survival, collapse,
revival, gaps, and unknown states. Scheduled/event checkpoints use only
checkpoint-time evidence; later outcomes evaluate but never rewrite them.

The four dimensions remain separate: evidence quality, market-integrity
condition, tradeability, and action eligibility. All eight binding manipulation
behaviors and the complete manipulation lifecycle are represented.
Manipulation never automatically authorizes or rejects an action.

Full-window outcome remains separate from internal trade-opportunity outcome.
All twelve tradeable-path contexts are represented as design contexts, not
activated actions.

## 8. Evidence Gaps and Dependencies

Wallet/participant authenticity, coordination, related-wallet clusters,
bundling, hidden concentration, and probable distribution remain `UNKNOWN` when
unproven. A Wallet and Participant Evidence Source Audit remains required before
paper-decision readiness.

Chart opportunity remains separate from realistically executable opportunity.
Provider-dependent quantitative execution fields remain
`CURRENT_EVIDENCE_GAP` or `UNKNOWN_REQUIRES_RESEARCH`. Jupiter route/quote,
GoPlus, GeckoTerminal, and public-RPC contract work remains required before
V2-9.7D implementation relies on those fields.

## 9. Lifecycle, Persistence, Supervision, and Replay

The design reuses B.1 authoritative promotion reporting, B.2 timeframe-neutral
safety reporting, B.3 terminal lifecycle reconciliation, B.4 bounded lease and
first-fault safe-stop behavior, and B.5 immutable launch Git provenance.

It specifies cooldown/archive/replacement/revival, stale-work cleanup,
persistent target ownership, proof isolation, migration prerequisite,
byte/hash-verified backup, interrupted-copy defense, disposable restore
rehearsal, integrity/FK/count/hash reconciliation, zero-source report-only
replay, immutable report identity, and no automatic resume/restart.

No database action occurred in this lane.

## 10. Reporting and Future Proof

Reporting keeps promotions, dirty/blocked reasons, idempotent outcomes,
timeframe/continuation yield, source efficiency, fairness, concentration,
trajectory/manipulation/opportunity coverage, wallet/execution gaps, rotation,
terminal causes, provenance, chart/executable returns, costs, excursions,
avoided loss, missed upside, churn, time in position, and later-locked
WAIT/AVOID diagnostics separate. No combined score-like system is permitted.

The later frozen-validation contract freezes corpus and rules, prevents
look-ahead, uses unseen episodes and realistic costs, compares approved
baselines, repeats walk-forward periods, and prohibits rescue tuning.

## 11. Optional Capital Policy

The future optional paper policy is versioned, validated, auditable,
non-retroactive, decision-linked, and safe-boundary applied. Risk-reducing
changes may apply at the next safe checkpoint without increasing exposure;
risk-increasing changes wait for a new campaign boundary. `CAPITAL_POLICY_OFF`
cannot disable permanent Printer invariants.

## 12. Abstract Command Boundary

Inputs, configuration identity, DB target requirements, preflight, bounded
behavior, report paths, cancellation, terminal behavior, report-only replay,
and safe stop are specified conceptually. No runnable PowerShell command,
operational syntax, activation sentence, or start placeholder was provided.
The exact operational command remains locked until V2-9.8A.

## 13. Static Verification

- Exactly 19 canonical traceability rows: PASS.
- All eight manipulation behaviors: PASS.
- All twelve tradeable-path contexts: PASS.
- Four-way separation and two outcome layers: PASS.
- Positive/negative conditional-5m scenarios: PASS.
- Two-token fairness/no-starvation and selective-continuation scenarios: PASS.
- Trajectory/checkpoint/anti-look-ahead scenarios: PASS.
- Contradiction and unseen-condition scenarios: PASS.
- Risk-reducing/risk-increasing capital-policy scenarios: PASS.
- Backup/restore/interruption/replay/safe-stop scenarios: PASS.
- Wallet/execution gaps and provider dependencies remain explicit: PASS.
- No invented capability or Governor/Scheduler bypass: PASS.
- No score/rank/confidence/weighting/embedding/vector system: PASS.
- No runnable operational command or capability activation: PASS.
- Exactly three approved documentation files changed: PASS.
- Unrelated untracked artifacts untouched: PASS.
- `git diff --check`: PASS.

## 14. Money-Usefulness Contribution

The design makes future corpus growth selective, diverse, path-aware,
manipulation-aware, execution-honest, chronologically valid, and safely
reproducible. It improves the quality of future capital-protection and realistic
paper-profit research without proving profitability or activating decisions.

## 15. What This Design Improves

- Gives V2-9.7D one complete implementation contract.
- Prevents all-timeframe tracking, hidden score logic, hindsight paths, fake
  chart profit, wallet-authenticity overclaim, and unsafe restart.
- Makes persistent corpus safety, report-only replay, and two-token fairness
  first-class requirements.

## 16. What Remains Locked

V2-9.7D implementation and execution; runtime; operational memory growth;
source/API/RPC/provider/MCP calls; DB mutation; retrieval; all action activation;
positions; trade events; audits; PnL; operational command release; wallets;
private keys; signing; execution; real funds; paid APIs; scoring; ranking;
confidence percentages; weighted logic; embeddings; vectors; 12h/24h; V2-10.

## 17. Functionality Risks / Setbacks / Efficiency Blockers

The principal later risks are fairness drift, categorical gates becoming hidden
ranking, unconditional 5m, trajectory overclaim, manipulation-as-action,
wallet/execution evidence invention, concentrated corpus growth, partial backup,
mutating replay, ambiguous supervision, capital-policy safety bypass, and
implementing provider-dependent fields before their contracts. The design gives
each an explicit stop rule and proof requirement; none is resolved by design
alone.

## 18. Exact Files Changed

- `docs/printer-v1-v2-9-7c-operational-memory-factory-design.md`
- `docs/printer-v1-v2-9-7c-operational-memory-factory-design-closeout.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`

## 19. Next Permitted Lane

`V2-9.7D - Bounded Implementation`

It must be separately authorized. This closeout does not begin implementation.
