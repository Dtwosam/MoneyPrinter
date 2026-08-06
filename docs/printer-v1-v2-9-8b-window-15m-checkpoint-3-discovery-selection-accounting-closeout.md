# Printer V1 V2-9.8B WINDOW_15M Checkpoint 3 — Discovery, Selection, and Source-Scope Accounting Closeout

## Verdict

`V2_9_8B_WINDOW_15M_CHECKPOINT_3_DISCOVERY_SELECTION_SOURCE_SCOPE_ACCOUNTING_PASS`

Checkpoint 3 is complete on the exact baseline `dceb63274d4633486c5cfecafbbd9470a09f8bee` and branch `agent/v2-9-8b-window-15m-checkpoint-3-discovery-selection-accounting`.

Checkpoint 4 is not started.

## Audit result

The ordinary WINDOW_15M discovery/selection path was inspected through the active Printer V1 source stack.

Three deterministic defects were confirmed:

1. an existing pair row could be reused by `pair_address` without proving canonical token ownership for the selected mint;
2. the direct-provider injected-failure path persisted a failure before its governed request identity;
3. campaign request-root membership accepted adjacent sibling prefixes such as `<root>shadow`.

The Scheduler claim-at-work-start contract was already present and required no repair.

The source-specific graduation path already validates carried exact authority without a second generic migration-registry lookup. Exact mint/pool identity and PumpSwap evidence remain required; no registry-removal change was made.

## Design and implementation

The approved implementation preserves existing owners and adds no second discovery engine, selector, Source Governor, Scheduler owner, retry path, or runtime entry point.

A package-local idempotent installer applies only the three RED-proven contracts to the existing module objects and `CombinedPumpfunCampaignExecutor` class:

- governed request identity is persisted before the linked direct-provider failure;
- existing pair rows fail closed when their canonical `token_id` belongs to another mint, or when a present `base_token_mint` conflicts with the candidate mint;
- lawful legacy pair rows with the correct canonical `token_id` and a NULL optional `base_token_mint` remain accepted;
- request-root membership accepts only the exact root or a hyphen-delimited child.

The repair is integrated explicitly from `printer_v1.discovery.__init__`.

## RED evidence

At commit `e4d7fac36c14a3a42669f5fc097d38fbf1b4dc11`, the focused test file produced three intended failures:

- prefix collision returned `True` instead of `False`;
- direct failure observed zero governed request rows at failure persistence time;
- foreign pair reuse returned the generic handoff failure instead of `PAIR_TOKEN_IDENTITY_MISMATCH`.

This established the required deterministic RED state before production repair.

## Bounded proof

The final disposable proof ran at repair head `115634e2c4953f202fff837b009d8489134ac1b5` in a detached temporary worktree.

Fresh evidence:

- exact proof head matched `115634e2c4953f202fff837b009d8489134ac1b5`;
- syntax and import guard: `CHECKPOINT3_SYNTAX_IMPORT_GUARDS_PASS`;
- focused tests: `34 passed, 3 subtests passed`;
- `git diff --check dceb63274d4633486c5cfecafbbd9470a09f8bee..HEAD`: clean;
- disposable worktree status: clean;
- terminal marker: `CHECKPOINT3_BOUNDED_GREEN_PROOF_PASS`.

The focused set covered:

- all three Checkpoint 3 contracts;
- atomic initial two-slot handoff and rollback;
- graduation-native activation;
- isolated combined discovery, including replacement preservation.

The first GREEN attempt correctly exposed one regression: valid legacy pair rows with matching canonical `token_id` but NULL `base_token_mint` were rejected. The existing replacement test served as RED evidence. The minimal nullable-field correction was committed and the complete focused proof then passed.

No broad suite was requested because the change is narrow and the directly affected contracts and regressions passed.

## Money-usefulness contribution

Checkpoint 3 improves the reliability of future paper-only money-useful observation by ensuring that:

- a selected market cannot silently inherit another token's pair identity;
- source failures remain accountable to an actual governed request;
- campaign source accounting cannot absorb adjacent request-key namespaces.

This strengthens the evidence chain that later memory comparison will depend on without introducing trading behavior.

## What this improves

- exact token/pair binding at handoff;
- request-before-failure provenance ordering;
- campaign source-scope isolation;
- deterministic fail-closed accounting;
- legacy pair compatibility where canonical token ownership is still exact.

## What this does not unlock

This checkpoint does not unlock or run:

- Printer runtime or provider fetching;
- authorization consumption or authoritative database mutation;
- memory generation or retrieval;
- paper BUY/SELL/HOLD decisions;
- paper positions, trade events, paper trade audits, or PnL;
- WINDOW_1H, 4h, 12h, or 24h activation;
- Checkpoint 4.

All Solana-only, Solana-memecoin-only, paper-only, Source Governor, Central Scheduler, no-paid-API, no-scoring/ranking/confidence/weighting, no-wallet, and no-real-funds restrictions remain unchanged.

## Functionality Risks / Setbacks / Efficiency Blockers

- The connected GitHub contents surface could not safely apply a unified hunk patch to the two large owner files. A package-local explicit installer was used instead; its idempotence and import activation are covered by the proof.
- A large-file façade approach was tested only as an unaccepted commit object, rejected after GitHub reported more than 18,000 changed lines, and the branch was restored before the accepted implementation. No façade files remain in the final tree.
- Legacy `base_token_mint` may be NULL. Canonical `token_id` ownership is therefore the required identity authority; a non-NULL conflicting denormalized mint still fails closed.
- No live or authoritative proof was appropriate or permitted for this checkpoint.

## Completion boundary

Checkpoint 3 closes only the discovery, selection, and source-scope accounting contracts described above. Any next checkpoint requires its own audit/readiness review and explicit authorization.