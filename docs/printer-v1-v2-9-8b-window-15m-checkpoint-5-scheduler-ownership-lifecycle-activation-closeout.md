# Printer V1 V2-9.8B WINDOW_15M Checkpoint 5 — Scheduler Ownership and Lifecycle Activation Closeout

## Verdict

`V2_9_8B_WINDOW_15M_CHECKPOINT_5_SCHEDULER_OWNERSHIP_LIFECYCLE_ACTIVATION_PASS`

Checkpoint 5 is complete.

- Baseline: `421e409628a0db443f1c417835a9d5b06bbdc834`
- Audit commit: `601297c338b6ec50d5006ce6302b473496763f6f`
- Final repair commit: `e90e020f0f37960c612c85758cb70ea14096bf60`
- Branch: `agent/v2-9-8b-window-15m-checkpoint-5-scheduler-ownership-lifecycle-activation`
- Linear: `DTW-31`

Checkpoint 6 is not started.

## Audit and blocker result

The current `WINDOW_15M` path was audited from the exact two-token handoff through Central Scheduler enqueue, claim, lifecycle work, support-only 5m handling, terminal close, failure isolation, terminal cleanup, zero-residue verification, and lease release.

The scheduler/lifecycle contracts themselves remained sound. The focused proof exposed one deterministic cross-checkpoint architectural blocker: `printer_v1.discovery.__init__` eagerly installed Checkpoint 3 monkeypatches, and the installer dynamically imported owners that re-entered the discovery package during operational-command imports. This created a deterministic circular import before Checkpoint 5 proof collection.

The blocker was repaired at the canonical owners rather than hidden through import ordering:

- governed direct-provider request identity is created before its linked injected failure;
- existing pair reuse proves canonical token ownership and rejects conflicting non-null `base_token_mint`;
- lawful legacy pair rows with matching canonical `token_id` and NULL optional `base_token_mint` remain accepted;
- campaign request-root membership accepts only the exact root or a hyphen-delimited child;
- the eager package installer and `checkpoint3_guards.py` were removed.

No alternate discovery engine, Source Governor, Scheduler owner, retry path, fallback path, or runtime entry point was added.

## Final implementation manifest

The accepted repair commit changed exactly nine files:

- removed five temporary proof/repair runners;
- removed `src/printer_v1/discovery/checkpoint3_guards.py`;
- removed the eager installer call from `src/printer_v1/discovery/__init__.py`;
- integrated the Checkpoint 3 pair-ownership and request-before-failure contracts into `src/printer_v1/discovery/combined_executor.py`;
- integrated delimiter-bound request-root ownership into `src/printer_v1/discovery/permanent_discovery_availability.py`.

No schema, migration, provider adapter, authoritative database, memory, retrieval, decision, position, trade, audit, or PnL file changed.

## Proof evidence

### Full focused proof

On the unchanged source/test tree later committed as the repair:

- fresh-process import-order proof: `4 passed`;
- Checkpoint 3 contract regressions: `3 passed`;
- static Checkpoint 5 contracts: PASS;
- focused Scheduler/lifecycle suite: `119 passed, 4 deselected, 36 subtests passed`;
- isolated lease replay: `1 passed`;
- diff check: clean;
- exact manifest: PASS.

The static contract proof confirmed:

- top-level factory window remains `WINDOW_15M`;
- all operational lifecycle `fail_job()` calls retain `max_retries=0`;
- approved work scopes remain exactly `DISCOVERY_SELECTION`, `FIRST_15M_HANDOFF`, `WINDOW_LIFECYCLE`, and `TERMINAL_CLEANUP`;
- cleanup still reports zero automatic retries and no resume, restart, successor, or new child work;
- request-before-failure ordering, pair/token ownership, and delimiter-bound request scope are present at their canonical owners;
- the eager guard installer no longer exists.

### Final bounded recheck and push

Before committing and pushing `e90e020f0f37960c612c85758cb70ea14096bf60`, the standalone finalizer established:

- no source or test drift after the full focused proof;
- exact owner-level repair edit: PASS;
- import-order proof: `4 passed`;
- Checkpoint 3 regressions: `3 passed`;
- static contracts: PASS;
- isolated lease replay recheck: `1 passed`;
- diff check: clean;
- exact nine-file manifest: PASS;
- terminal markers:
  - `CHECKPOINT5_IMPORT_ORDER_REPAIR_GREEN_PASS`
  - `CHECKPOINT5_FOCUSED_PROOF_PASS`.

GitHub independently confirms the remote branch points exactly to the repair commit and that the commit contains only the expected nine files. No GitHub Actions workflow or status check is configured for this commit; the bounded disposable local proof is the controlling execution evidence.

## Pre-existing test classifications

Four tests were excluded only after evidence-based classification:

1. One obsolete direct-migration settle-sleep test references the retired `release_write_transaction` symbol and a settle path the current live-tail owner forbids. It was reproduced exactly before exclusion.
2. Two historical E.11 tests use a legacy `graduation_proofs`-only pre-admission fixture without the permanent graduated-supply owner. They fail outside Checkpoint 5's current boundary, which begins with two already memory-admitted token slots.
3. One replay test can exceed its 90-second lease when embedded in the broad combined suite. It passed separately in a fresh process and was not permanently waived.

No production contract was weakened to satisfy stale or superseded fixtures.

## Money-usefulness contribution

Checkpoint 5 protects future paper-only memory growth from duplicated or unowned work, missing Scheduler claims, hidden retries, support-only 5m evidence masquerading as a main outcome, abandoned locks, silent successor runs, and import-time monkeypatch behavior that could prevent the 15m lifecycle from starting deterministically.

This improves the trustworthiness and repeatability of future clean `WINDOW_15M` evidence without creating a trading signal or financial action.

## What this checkpoint improves

- deterministic operational-command imports;
- exact two-token handoff-to-lifecycle identity continuity;
- Central Scheduler enqueue, claim, terminal, and cleanup ownership confidence;
- canonical owner-level Checkpoint 3 invariants without import side effects;
- support-only 5m separation from the main `WINDOW_15M` outcome;
- fail-closed zero-retry lifecycle behavior;
- token-local failure isolation and global safe-stop boundaries;
- terminal cleanup, zero active/locked work, and exact lease release confidence.

## What this checkpoint does not unlock

This checkpoint does not unlock or run:

- providers, RPC, WebSocket, or public Printer runtime;
- authorization creation or consumption;
- authoritative Scheduler/lifecycle execution;
- authoritative database mutation;
- memory generation or retrieval;
- paper BUY/SELL/HOLD decisions;
- paper positions, trade events, paper trade audits, or PnL;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, or `WINDOW_24H`;
- Checkpoint 6.

All Solana-only, Solana-memecoin-only, paper-only, Source Governor, Central Scheduler, no-paid-API, no-scoring/ranking/confidence/weighting, no-wallet, no-private-key, and no-real-funds restrictions remain unchanged.

## Functionality Risks / Setbacks / Efficiency Blockers

- The obsolete settle-sleep concurrency test remains separate maintenance debt and must not be repaired inside this closed checkpoint without a new approved audit/design lane.
- The two superseded legacy pre-admission fixtures remain historical debt; changing their production path here would have crossed the Checkpoint 5 boundary.
- The generic Scheduler remains retry-capable for unrelated historical callers. Future operational code must continue to pass `max_retries=0` explicitly.
- Live provider availability, wall-clock cadence, and authoritative production lease behavior are not proven by fixture-only tests.
- Import-side-effect removal may expose any unknown external caller that relied on the deleted monkeypatch installer, but fresh independent imports and the nearest affected regressions passed on the approved path.
- The proof harness required several corrections before producing a clean final manifest; those runner files were removed from the accepted repair commit and do not remain as production surface.

## Completion boundary

Checkpoint 5 closes only Scheduler ownership, `WINDOW_15M` lifecycle activation readiness, terminal cleanup ownership, and the deterministic import-order blocker described above.

Any Checkpoint 6 work requires its own audit/readiness review, explicit authorization, minimum sufficient proof, and separate closeout. It must not begin automatically.
