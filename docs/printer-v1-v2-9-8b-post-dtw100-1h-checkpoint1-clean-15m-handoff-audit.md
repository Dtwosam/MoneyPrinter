# Printer V1 V2-9.8B Post-DTW100 WINDOW_1H Checkpoint 1 — Clean 15m → 1h Handoff Audit

## Verdict

`V2_9_8B_POST_DTW100_1H_CHECKPOINT_1_AUDIT_BLOCKED_STRICT_ATOMIC_HANDOFF_REPAIR_REQUIRED`

Checkpoint 1 starts only after a token has a successfully closed, canonical clean `WINDOW_15M` object. Discovery, selection, initial 15m collection, 15m close, and clean 15m promotion are intentionally not re-audited here.

The current repository already contains reusable, correct foundations for most of the handoff: canonical B.1 clean-promotion authority, B.2 safety authority, exact token/pair/lifecycle/predecessor identity, standard first-hour continuation policy, exact `WINDOW_1H` successor identity, fixed 45-minute continuation planning, and Central Scheduler 1h job kinds.

One current integration defect blocks Checkpoint 1 completion: successor-window persistence and token-slot lifecycle advancement are not one strict atomic ownership operation. `operational_selective_1h.evaluate_selective_1h_for_cycle()` creates a `WINDOW_1H` ownership row and then attempts token-slot transitions while catching and ignoring `CampaignOwnershipError`. Therefore a successor window and immutable continuation decision can exist even if the token slot never reaches `WINDOW_1H_CONTINUING`.

That defect must be repaired before Checkpoint 2.

## Baseline

- Repository: `Dtwosam/MoneyPrinter`
- Verified baseline: `6a031b75f3dfefda6c0f4b95fd3f1d5d8f528cdc`
- Baseline branch was identical to that SHA before this checkpoint branch was created.
- Checkpoint branch: `agent/v2-9-8b-post-dtw100-1h-checkpoint1-clean-15m-handoff`

No source fetching, Scheduler runtime, authoritative DB mutation, authorization creation, wrapper execution, memory generation, retrieval, paper decision, position, trade, audit, PnL, wallet, key, signing, or real-fund action occurred in this audit.

## Starting boundary

The checkpoint assumes each continuing token already has:

- exact campaign/run/cycle/token-slot identity;
- exact token/mint/pair/lifecycle identity;
- closed `WINDOW_15M` memory-window row;
- `CLEAN_DATA`;
- canonical E2Z clean episode plus canonical fingerprint;
- authoritative B.1 clean-promotion status;
- acceptable exact-target B.2 safety facts;
- continuous predecessor evidence;
- a succeeded current-run 15m close step.

A token that does not satisfy those conditions is outside the successful-start boundary and must fail closed rather than be repaired by the handoff.

## What is already healthy and reusable

### Canonical clean predecessor authority

The current operational harness uses E2Z to construct the canonical clean object rather than manufacturing an episode-only predecessor. B.1 then consumes the authoritative clean promotion. This was restored and proved in the immediately preceding first-hour harness/reporting lane.

### Standard first-hour continuation policy

`WINDOW_15M -> WINDOW_1H` no longer requires an outcome or learning-need qualification. Otherwise-valid clean predecessors receive `CONTINUE_TO_WINDOW_1H`; quiet outcomes such as `CONSOLIDATION` and `NO_PUMP` are already covered by the focused operational tests.

### Exact successor linkage

For a continuing token, the operational owner derives a deterministic `WINDOW_1H` campaign-window identity and persists:

- the same campaign/run/cycle;
- the same token slot;
- the same token row and pair row;
- the original root 15m lifecycle identity;
- the exact predecessor 15m campaign-window identity.

This is the correct reuse model; no second token/pair/lifecycle is created.

### Continuous first-hour time plan

The existing lifecycle-continuity owner plans the continuation from the exact 15m close and closing snapshot. The deadline is `15m close + 2700s`, not a new 1h clock. The current 1h cadence policy is enabled for real collection and defines the remaining 45-minute phase.

### Scheduler reuse

The existing factory scheduler maps `CONTINUATION_SNAPSHOT` to the existing 1h FAST/NORMAL job kinds and `CONTINUATION_CLOSE` to the shared memory-window-close job kind. No separate scheduler is required.

## Blocking defect

### Current behavior

On the first authoritative continuation evaluation, `evaluate_selective_1h_for_cycle()`:

1. persists immutable continuation objects;
2. persists the successor `WINDOW_1H` campaign window;
3. attempts token-slot transitions:
   - `SELECTED -> WINDOW_15M_ACTIVE`
   - `WINDOW_15M_ACTIVE -> WINDOW_15M_CLOSED`
   - `WINDOW_15M_CLOSED -> WINDOW_1H_CONTINUING`
4. catches `CampaignOwnershipError` around those transitions and continues.

`persist_window()` and `transition_state()` each own their own connection transaction scope. The successor-window insert can therefore commit independently before a later state transition fails.

### Consequence

The current code can represent an impossible mixed state such as:

- immutable decision = `CONTINUE_TO_WINDOW_1H`;
- `WINDOW_1H` ownership row exists;
- report counts a continuation;
- token slot is still `SELECTED`, `WINDOW_15M_ACTIVE`, `WINDOW_15M_CLOSED`, or another conflicting state.

Because transition errors are swallowed, that inconsistency is not necessarily surfaced to the caller.

### Test gap

The restored 32-test operational first-hour harness proves continuation verdicts, exact clean authority, safety blocking, idempotency, and successor-window counts, but it does not assert that a successful handoff leaves every continuing token in `WINDOW_1H_CONTINUING`. A repository search likewise finds `WINDOW_1H_CONTINUING` in the ownership/state implementation and design documentation, not in the current first-hour proof assertions.

## Required repair shape

The repair must stay inside the existing ownership architecture. It must not create a parallel 1h persistence system.

Required properties:

1. Preflight the token-slot lifecycle state before any new continuation object/window side effect.
2. Accept only the legitimate pre-handoff prefix states needed for current compatibility: `SELECTED`, `WINDOW_15M_ACTIVE`, or `WINDOW_15M_CLOSED`.
3. Reject terminal, 1h-already-active, future-stage, or otherwise conflicting state before successor persistence.
4. Create the `WINDOW_1H` ownership row and advance the token slot through the required prefix transitions to `WINDOW_1H_CONTINUING` as one canonical ownership transaction.
5. Preserve exact campaign/run/cycle/token/pair/root-lifecycle/predecessor identities.
6. Read back and verify both the successor-window identity and final token state before returning success.
7. Do not swallow ownership/state errors.
8. Preserve first-evaluation idempotency rules; replay must not create a second window or second continuation object.
9. Do not change B.1, B.2, E2Q, E2Z, continuation eligibility, cadence, Scheduler policy, Source Governor, or any downstream capability lock.

## Minimum focused proof

The repair proof must demonstrate at least:

- two canonical clean 15m predecessors produce two exact `WINDOW_1H` successors and both slots end at `WINDOW_1H_CONTINUING`;
- predecessor/root lifecycle/token/pair identities are unchanged;
- `CONSOLIDATION` and `NO_PUMP` still continue when otherwise valid;
- a conflicting token-slot state fails before creating a 1h successor or immutable continuation object;
- repeated evaluation remains idempotent;
- the existing first-hour operational harness remains green;
- no retrieval/paper/financial rows are created.

## Money-usefulness contribution

A trustworthy 1h corpus requires the same token lifecycle to continue without ambiguous ownership. This repair prevents Printer from recording a nominal first-hour continuation whose lifecycle state says something different, protecting later trajectory interpretation and clean-memory attribution.

## What this checkpoint improves

When closed, Checkpoint 1 will establish one exact, fail-closed handoff from a canonical clean 15m memory into the 1h continuation lifecycle while reusing the proven shared ownership, continuity, cadence, Scheduler, and clean-memory architecture.

## What this checkpoint still does not unlock

- no real first-hour run;
- no one-use first-hour authorization;
- no wrapper execution;
- no provider/RPC call;
- no authoritative DB mutation;
- no proof that the remaining 45-minute runtime itself is healthy — that is Checkpoints 2-4;
- no 4h activation;
- no retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.

## Functionality Risks / Setbacks / Efficiency Blockers

- An overly broad state refactor could destabilize already-proven 15m ownership; repair must be narrow.
- Merely removing `try/except` is insufficient because the successor window may already have committed before the transition error.
- Copying 15m ownership code into a new 1h subsystem would create drift; the repair must live in/reuse the canonical campaign-ownership boundary.
- A successful handoff proof does not prove 45-minute collection or 1h closeout; later checkpoints remain mandatory.

## Next action

Design the narrow canonical-owner atomic handoff repair. No Checkpoint-2 work may begin until repair implementation, focused proof, and Checkpoint-1 closeout pass.
