# Printer V1 V2-9.8B Post-DTW100 Standard Four-Hour Lifecycle Current-State Audit

## Verdict

`V2_9_8B_POST_DTW100_STANDARD_FOUR_HOUR_LIFECYCLE_AUDIT_BLOCKED_CAMPAIGN_INTEGRATION_POLICY_AND_TWO_TOKEN_CAPACITY_DESIGN_REQUIRED`

The operator's proposed direction is learning-useful and aligned with Printer's end goal:

> every otherwise-valid token already activated into the bounded main lifecycle should normally be observed through the full first four hours, with 15m, 1h, and 4h as evidence checkpoints rather than behavior/outcome qualification gates.

However, current Printer cannot adopt that rule by simply removing the `WINDOW_1H -> WINDOW_4H` learning-need gate. The existing 4h path is a proven **proof-oriented long-window subsystem** whose real collection remains disabled and whose operational shape assumes one 4h continuing token (including the historical compressed two-token proof where only one token continues).

A separate design/source-stack amendment plus bounded implementation/proof is required before standard 1h->4h continuation can be adopted.

No new one-token 4h feasibility proof is required. V2-9 already proved a genuine one-token 15m -> 1h -> 4h clean-memory lifecycle. The missing work is generalized campaign integration and bounded two-token operational readiness.

## Baseline and scope

- Baseline: `7c793dca805bccf79a8bbadaed2fb57e426c6b93` — Checkpoint-6 exact-closeout PASS.
- Branch: `agent/v2-9-8b-post-dtw100-standard-four-hour-current-state-audit`.
- Type: read-only/static current-state audit.

Inspected current source-stack policy, continuation policy, cadence contract, one-token 4h runtime, one-command factory 4h gates/budgets, E2Q 4h support, campaign state law, and V2-9 final proof closeout.

No source fetching, Scheduler/runtime execution, authorization creation, authoritative DB mutation, memory generation, 4h activation, retrieval, paper decisions, financial capability, wallet, signing, or execution occurred.

## 1. Learning-policy direction

The policy reason for standard 1h->4h continuation is the same sampling-bias problem already repaired for 15m->1h.

If continuation after 1h depends on an outcome or learning-need label, Printer can systematically miss tokens that appear quiet or unremarkable at the 1h checkpoint but materially change during hours 1-4 through collapse, revival, delayed expansion, distribution, liquidity deterioration, survival, or failed recovery.

The target policy should therefore become:

```text
validly activated bounded token
-> 15m checkpoint
-> standard continuation if hard operational gates remain valid
-> 1h checkpoint
-> standard continuation if hard operational gates remain valid
-> 4h checkpoint
-> stop automatic continuation here
-> any 4h -> 12h work remains separately selective/locked
```

This is an observation policy, not a bullish filter, score, ranking, confidence signal, BUY rule, or profitability claim.

## 2. Current source-stack policy conflicts with that target

### Memory Factory Guide

The current guide still says:

- `WINDOW_1H` opens/continues only when useful/eligible;
- `LONG_WINDOW_CANDIDATE` is for longer lifecycle learning after useful early evidence and is not for every token;
- `WINDOW_4H` should start after 1h memory is clean and capacity is stable;
- selective continuation must be preserved and not every token should receive every timeframe.

Those statements are binding current policy until explicitly amended. They cannot be silently overridden by code.

### Assistant active build-order anchor

The current anchor correctly records the standard first-hour amendment, then explicitly states:

`Selectivity begins after 1h. WINDOW_1H -> WINDOW_4H and later approved transitions remain selective.`

It also keeps 4h activation locked behind an explicit lane.

Therefore standard four-hour observation requires a source-stack amendment before implementation.

## 3. Current continuation policy is still learning-need-gated

`src/printer_v1/scheduler/token_local_continuation.py` currently treats:

- `WINDOW_15M -> WINDOW_1H` as standard after hard gates;
- `WINDOW_1H -> WINDOW_4H` as selective.

For 1h->4h:

- no learning need -> `STOP_AFTER_WINDOW_1H` / `no_unresolved_learning_need`;
- unsupported/non-applicable learning need -> block;
- allowed learning need + token budget -> `CONTINUE_TO_WINDOW_4H`.

Current allowed 4h learning needs are transition, survival, collapse, revival, distribution, and liquidity deterioration.

Future implementation should remove only the **behavior/learning-need qualification** from this transition. Identity, clean predecessor, evidence, freshness, governed provenance, safety, continuity, campaign health, cancellation/terminal, and bounded resource gates remain mandatory.

## 4. Four-hour cadence exists but real collection is explicitly disabled

`src/printer_v1/snapshots/cadence_policy.py` already defines strict 4h contracts.

| Lane | Target gap | Dirty above | Block above | Physical continuation | Minimum snapshots | Real collection |
|---|---:|---:|---:|---:|---:|---|
| `TRACK_FAST` | 180s | 225s | 360s | 10,800s | 61 | disabled |
| `TRACK_NORMAL` | 360s | 450s | 720s | 10,800s | 31 | disabled |

Both require full anchored duration and a forced closing snapshot. Missing evidence is never interpolated.

The cadence contract therefore does not need reinvention, but `enabled_for_real_collection=False` is an explicit activation lock. Changing it must happen only after campaign integration and capacity design/proof are ready; it must not be flipped first.

## 5. Existing 4h runtime is proof-oriented, not generalized campaign-owned operation

`src/printer_v1/operator_cli/one_token_4h_runtime.py` identifies itself as the current-run **one-token** `WINDOW_1H -> WINDOW_4H` runtime boundary and states that real collection remains disabled.

It already provides useful owners to reuse:

- current-run exact 1h predecessor resolution;
- fixed 10,800-second 4h deadline;
- policy-derived snapshot plan;
- zero automatic retries;
- no endpoint rotation;
- continuity evaluation;
- cadence evaluation;
- exact 4h physical-window creation;
- E2Q -> Lane Q -> E2Z clean-memory path.

But `plan_current_run_4h(...)` requires `explicit_proof_mode=True`. Without it, it returns:

`WINDOW_4H real collection remains disabled`

Normal mode requires exactly one selected token. Its historical compressed two-token proof mode accepts two selected tokens but requires exactly **one** current 1h continuation identity. That proves the old one-continuer/two-token scenario, not both active tokens receiving 4h.

## 6. One-command 4h entry is still proof-gated

The one-command factory exposes internal `continuous_four_hour` / `four_hour_proof_mode` behavior.

Current preflight requires:

- 4h uses the same-run first-hour path;
- `continuous_four_hour` without explicit `four_hour_proof_mode` is blocked;
- the campaign-owned first-hour path is explicitly prevented from enabling 4h because 4h remains a separate locked lane.

After a successful `CONTINUATION_CLOSE`, only the old `continuous_four_hour` proof path calls `plan_current_run_4h(...)`.

Therefore the newly repaired campaign-owned standard-first-hour path does not currently own a production 1h->4h handoff.

## 7. Campaign ownership exists structurally but is not integrated into the 4h proof runtime

`campaign_ownership.py` already has the required token state vocabulary:

```text
WINDOW_1H_CLOSED
-> WINDOW_4H_CONTINUING
-> WINDOW_4H_CLOSED
```

The campaign-window table is generic and can represent `WINDOW_4H`.

However, the current `one_token_4h_runtime.py` planner creates generic Scheduler jobs and factory run steps directly. It does not create/advance an exact campaign `WINDOW_4H`, does not advance the owning campaign token slot to `WINDOW_4H_CONTINUING`, and does not project the long-window jobs through the stage-scoped campaign Scheduler-work ownership path that was hardened for the first-hour lifecycle.

This is a campaign-integration gap, not a reason to create new state tables.

The future implementation should reuse the current campaign ownership graph and the already-proven stage-scoped Scheduler projection pattern.

## 8. Two-token capacity/fairness is not yet designed for both tokens through 4h

The existing 4h budget functions were derived for one 4h continuing token. The current two-token lifecycle adjustment adds the peer token's 15m allowance; it does not reserve a full peer 1h + 4h lifecycle.

The old compressed two-token proof is therefore materially smaller than the proposed standard-four-hour campaign.

Using today's policy ceilings only as an audit planning calculation, both tokens running the complete current 15m + 1h + 4h shape would require approximately:

| Lane pair | Run request ceiling to design around* | Scheduler-row ceiling to design around* |
|---|---:|---:|
| FAST + FAST | 230 | 210 |
| FAST + NORMAL | 182 | 162 |
| NORMAL + NORMAL | 134 | 114 |

`*` Derived from the currently committed per-phase policy ceilings and one handoff per token. These are audit planning numbers, **not adopted operational ceilings**. The design must rederive them against actual Source Governor reservation semantics, context requests, holder fallback limits, campaign Scheduler projections, and exact mixed-lane accounting before implementation.

The current proof path also does not prove a fairness round where two simultaneous long-window tokens receive service without one starving the other's close work.

## 9. Four-hour quality/memory machinery already exists

Do not rebuild these owners.

Current E2Q code already accepts a structurally genuine `WINDOW_4H` and requires:

- 10,800-second anchored continuation;
- exact governed snapshot anchors;
- current-run continuity metadata;
- exact token/pair targeting.

Lane Q already has the 4h duration/cadence contract, and `run_4h_quality_gates(...)` already composes E2Q -> Lane Q -> E2Z.

V2-9 Attempt 7 proved the full one-token chain can create an exact clean `WINDOW_4H_CLEAN_MEMORY` episode.

There is a documentation-comment drift inside E2Q: its top docstring still says 4h is not enabled, while its actual constants/validators admit genuine 4h. This should be corrected in the later implementation/design-adoption scope if that file is otherwise touched, but it is not itself the core blocker.

## 10. V2-9 already answered the 4h feasibility question

`V2_9_FINAL_CLOSEOUT_PASS` established one exact TRACK_FAST token through:

- 15m: 16/16 snapshots;
- 1h: 24/24 snapshots;
- 4h: 61/61 snapshots;
- exact 1h->4h continuity;
- fixed 10,800-second deadline;
- E2Q/Lane Q/Lane K/E2Z completion;
- one clean `WINDOW_4H_CLEAN_MEMORY` episode;
- budget/supervision/proof-DB isolation safety.

The same closeout explicitly says generalized 4h production/operational campaigns remain locked and that one-token evidence does not prove generalized 4h campaign readiness.

Therefore repeating another one-token 4h proof now would waste time/credits and would not resolve the current blockers.

## 11. Required design/source-stack amendment

The next lane should design and adopt this bounded policy:

### Standard observation rule

Every otherwise-valid token that reaches a genuine clean/eligible first-hour predecessor continues to the 4h checkpoint without an outcome or learning-need qualification.

`NO_PUMP`, `CONSOLIDATION`, direction, profitability, trajectory class, manipulation label, and 5m support evidence have no authority to stop or authorize 1h->4h.

### Hard gates retained

Continuation still fails closed on:

- exact campaign/run/cycle/token/mint/pair/lifecycle identity;
- genuine closed 1h predecessor and exact clean-memory object where required by current policy;
- evidence completeness/quality/freshness;
- governed provenance;
- safety context;
- exact 1h->4h continuity;
- campaign/DB/lease/integrity health;
- token/campaign/Source Governor/Scheduler/storage ceilings;
- cancellation or terminal state.

Dirty or blocked 1h evidence never becomes clean merely because observation policy is standard.

### Campaign integration required

Design must specify:

1. exact `WINDOW_1H_CLOSED -> WINDOW_4H_CONTINUING` handoff;
2. exact campaign `WINDOW_4H` identity with 1h predecessor linkage;
3. stage-scoped campaign Scheduler-work rows for every 4h snapshot/close job;
4. two-token fairness and close-deadline priority;
5. two-token Source Governor and Scheduler ceilings for FAST/FAST, FAST/NORMAL, NORMAL/NORMAL;
6. lifecycle reservation accounting for all 4h transport operations;
7. token-local failure and shared-stop behavior;
8. `WINDOW_4H` close/memory construction using existing 4h owners;
9. exact campaign 4h terminal reconciliation (`CLEAN_PROMOTED`/`DIRTY`/`NO_PROMOTION`/`BLOCKED`/`CANCELLED` plus token `WINDOW_4H_CLOSED`/failure state);
10. report/active-work proof that no 4h Scheduler work remains after close;
11. explicit real-collection activation boundary only after implementation proof passes.

### Automatic continuation stops at 4h

This amendment must **not** turn 4h into automatic 12h continuation.

`WINDOW_12H` and `WINDOW_24H` remain locked/selective until later explicit audit/design/proof lanes.

`WINDOW_5M_MICRO_EVENT` remains support-only throughout.

## Money-usefulness contribution

Standard first-four-hour observation reduces behavior-conditioned sampling bias and allows Printer to learn delayed collapse, revival, distribution, survival, and liquidity deterioration even when the 1h checkpoint itself appears unremarkable.

The campaign-integration requirements protect that learning value from fake completeness: two tokens must remain fairly serviced, exact identities must stay intact, deadlines must close cleanly, and dirty/failed evidence must remain dirty/failed.

This improves future memory usefulness; it does not prove profit or authorize a paper action.

## What this audit improves

- distinguishes policy standardization from runtime productionization;
- prevents a premature learning-need-only code patch;
- identifies reusable 4h cadence/continuity/memory owners;
- identifies the missing campaign/Scheduler ownership layer;
- identifies the real two-token capacity/fairness expansion;
- avoids wasting another one-token 4h feasibility proof;
- defines a bounded path to the user's desired first-four-hour memory policy.

## What remains locked

- no 4h implementation or real-collection activation in this audit;
- no live 4h or first-hour run;
- no fresh authorization/wrapper;
- no source fetching or operational Scheduler runtime;
- no authoritative DB mutation or operational memory generation;
- no 12h/24h;
- no retrieval;
- no paper decisions;
- no BUY/SELL/HOLD;
- no positions, trade events, paper-trade audits, or PnL;
- no wallet/private keys/signing/real funds/live execution;
- no paid APIs;
- no scoring/ranking/confidence/weighted logic;
- no embeddings/vectors.

## Proof required after later implementation

Minimum bounded offline proof must show:

- both otherwise-valid token slots continue from genuine 1h to 4h without learning-need qualification;
- quiet/no-pump/consolidation and transition outcomes have equal observation authority;
- hard identity/evidence/safety/continuity/budget failures still block;
- exact campaign `WINDOW_4H` and token-slot states stay synchronized;
- all long Scheduler jobs have exact campaign projections;
- two-token fairness and close priority hold;
- derived mixed-lane Source Governor/Scheduler ceilings are not exceeded;
- token-local failure does not terminalize the peer;
- shared stop cleans both safely;
- real 4h quality path reuses E2Q/Lane Q/E2Z and clean-object atomicity;
- no `WINDOW_12H` work is created;
- 5m has no main-outcome/continuation authority;
- retrieval/decision/financial deltas remain zero;
- Checkpoints 1-6 and directly affected long-window regressions remain green.

A later explicitly approved bounded operational proof should only be considered after the design, source-stack amendment, implementation, focused proof, and closeout pass. It must not reuse an old authorization.

## Functionality Risks / Setbacks / Efficiency Blockers

- **Premature policy-only patch:** removing `learning_need` now would produce continuation verdicts without a campaign-owned two-token 4h runtime.
- **Capacity expansion:** two full 4h continuations materially increase source/Scheduler work versus the historical one-continuer proof shape.
- **Deadline fairness:** two simultaneous 4h closes must not starve each other under long-window work.
- **Proof-mode leakage:** `explicit_proof_mode` / `four_hour_proof_mode` must not be converted into production authority by a shortcut.
- **State drift:** the 1h CP1-6 repairs show why campaign window/token/Scheduler truth must be wired before activation.
- **Report drift:** historical V2-9 reporting under-counted clean promotion; generalized 4h reporting must use authoritative clean-object truth.
- **Timeframe-confusing labels:** older safety/E2Q wording may still say 15m-only/4h-disabled despite real 4h proof capability; source-stack/code comments should be reconciled during the approved design/implementation scope.
- **One-token evidence:** V2-9 proves feasibility, not two-token operational fairness/capacity.
- **Scope creep to 12h:** standard four-hour observation must stop at 4h until a later explicit lane.

## Next permitted lane

`V2-9.8B Post-DTW100 Standard Four-Hour Lifecycle Policy and Campaign-Integration Design`

That lane should amend the source-stack policy and specify the exact campaign/Scheduler/budget design before any code change. No live proof or authorization is permitted during design.
