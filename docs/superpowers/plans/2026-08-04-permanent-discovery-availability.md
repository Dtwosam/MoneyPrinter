# Permanent Discovery Availability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend the existing canonical eligible-token-supply path into a permanent mint-first, batch-first, fairly traversed four-candidate funnel that atomically hands two eligible tokens to `WINDOW_15M` without weakening any Printer V1 gate.

**Architecture:** Keep `run_persistent_eligible_token_supply` as the sole active acquisition/reserve owner. Add an append-only exact-market state/history projection and reserve-layer helpers, compose governed DexScreener/GeckoTerminal resolution through existing adapters, preserve direct Pump/PumpSwap as lineage authority, continue holder/safety evaluation to four, and reuse the existing neutral selector and atomic two-slot handoff.

**Tech Stack:** Python 3, SQLite forward-only SQL migrations, stdlib urllib adapters, unittest/pytest, existing Source Governor/Central Scheduler owners.

**Global constraints:** Solana memecoins and paper-only memory collection; no scores/ranks/confidence/weights; no retries/loops/successors; no paid/unapproved provider; no threshold reduction; no retrieval/decision/position/trade/PnL surfaces; total discovery ceiling remains 30; preserve the untracked Migration-050 package and `/private/tmp/mp-preclaim`.

---

### Task 1: Lock the persistence and pure policy contracts

**Files:**
- Create: `migrations/051_permanent_discovery_availability.sql`
- Create: `src/printer_v1/discovery/permanent_discovery_availability.py`
- Create: `tests/test_v2_9_8b_permanent_discovery_availability.py`

- [x] Write failing migration/state-history tests for exact mint+pool preservation, append-only transitions, reserve layers, forward upgrade, integrity and foreign keys.
- [x] Run the focused test and confirm RED for missing migration/module.
- [x] Implement migration 051 and minimal persistence dataclasses/helpers.
- [x] Write failing pure-policy tests for categorical round-robin fairness, immutable stage reservations, 30-mint batch validation, no-match suppression and different-pool pending proof.
- [x] Implement only the policy needed to make those tests GREEN.

### Task 2: Add governed batch and reconciliation adapters

**Files:**
- Modify: `src/printer_v1/sources/dexscreener.py`
- Modify: `src/printer_v1/sources/geckoterminal.py`
- Modify: `src/printer_v1/sources/operational_source_contracts.py`
- Modify: `src/printer_v1/sources/registry.py`
- Modify: `docs/solana-builder-source-of-truth/dexscreener-api-contract.md`
- Modify: `docs/solana-builder-source-of-truth/geckoterminal-api-contract.md`
- Modify: `docs/solana-builder-source-of-truth/pumpswap-pool-confirmation-contract.md`
- Modify: `docs/solana-builder-source-of-truth/solana-core-rpc-reference.md`
- Test: `tests/test_v2_9_8b_permanent_discovery_availability.py`
- Test: `tests/test_dexscreener_fresh_profiles.py`
- Test: `tests/test_post_rc_geckoterminal_discovery_adapter.py`

- [x] Write failing tests for one 30-mint Dex batch, provider-order neutrality, preserved multi-pool identities, Gecko mint-pool fallback and provider-failure/absence separation.
- [x] Run focused tests and confirm RED.
- [x] Add no-retry governed transports/normalization and pin refreshed official contracts.
- [x] Run focused adapter tests to GREEN.

### Task 3: Replace flat traversal with the permanent canonical funnel

**Files:**
- Modify: `src/printer_v1/discovery/eligible_token_supply.py`
- Modify: `src/printer_v1/operator_cli/graduated_supply_front_door.py`
- Test: `tests/test_v2_9_8b_permanent_discovery_availability.py`
- Test: `tests/test_v2_9_8b_21_eligible_token_supply_architecture.py`

- [x] Write failing integration tests for multi-source mint/pool merge, due persisted candidates, same-pool revival, new-pool proof, fair category traversal, no repeat exact polling, protected later capacity and no false shortage with lawful unexplored work.
- [x] Run the focused tests and confirm RED.
- [x] Integrate batch resolution, exact state transitions, reconciliation and all three reserve layers into the existing supply owner.
- [x] Preserve existing local tracking/cooldown/STNP gates and exact `$3,000` floor.
- [x] Emit complete terminal truth and exact per-stage request/transport accounting.
- [x] Run eligible-supply regressions to GREEN.

### Task 4: Freeze four eligible candidates and preserve neutral atomic handoff

**Files:**
- Reuse unchanged: `src/printer_v1/discovery/selection_authority.py`
- Modify: `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
- Modify: `src/printer_v1/operator_cli/graduated_supply_front_door.py`
- Test: `tests/test_v2_9_8b_permanent_discovery_availability.py`
- Test: `tests/test_v2_9_7d_7b_4d_1_atomic_two_slot_handoff.py`
- Test: `tests/test_v2_9_7e_11_authoritative_live_operational_campaign.py`

- [x] Write failing tests showing holder/safety is called only for market-ready survivors until four fully eligible mints exist, stale alternates are rejected, selection remains seeded-uniform and partial handoff rolls back.
- [x] Run focused tests and confirm RED.
- [x] Extend the holder/safety depth and readiness bundle to selected plus alternates while reusing the existing selector and handoff owner.
- [x] Run handoff/campaign regressions to GREEN.

### Task 5: Prove the complete offline boundary and close implementation

**Files:**
- Create: `docs/printer-v1-v2-9-8b-permanent-discovery-availability-closeout.md`
- Modify tests above only as required by proven behavior.

- [x] Run changed tests during development and the directly affected discovery, Source Governor, Scheduler, migration and handoff tests.
- [x] Run migration 000→051 and 050→051 disposable upgrade checks, `PRAGMA integrity_check`, `PRAGMA foreign_key_check`, compilation and `git diff --check`.
- [x] Verify clean cancellation/zero residue and zero retrieval/decision/position/trade/PnL deltas.
- [x] Map every design requirement to implementation owner, proof, verdict and limitation in the closeout.
- [x] Perform the verification-before-completion evidence review and commit `Build permanent discovery availability` only on full PASS.

### Task 6: Execute the separately authorized one-shot `WINDOW_15M` attempt

**Files:**
- Create: one fresh exact-HEAD one-use authorization package under the existing authorization root.
- Create: one concise live closeout document.

- [ ] Confirm the implementation commit is exact HEAD and the tracked tree is clean; create no readiness artifact.
- [ ] Build and validate one fresh authorization bound to that exact HEAD, branch, command and one-attempt law.
- [ ] Invoke the canonical wrapper exactly once. Do not retry, rerun, restart, resume or create a successor regardless of outcome.
- [ ] Preserve complete source/candidate/reserve/lifecycle/memory/cleanup evidence and verify authoritative DB integrity.
- [ ] Classify Memory PASS only when authoritative completed `WINDOW_15M` and clean-memory rows exist.
- [ ] Write the honest live closeout and commit `Close permanent discovery 15m attempt`; do not push.

### Plan self-review

- [x] Every approved design requirement has an implementation task and focused proof.
- [x] Tasks preserve the existing canonical owner boundaries and do not revive deferred cursor runtime.
- [x] RED/GREEN checkpoints precede production changes.
- [x] Verification scope matches the cross-cutting migration/Source Governor/Scheduler risk without invoking unrelated full-repository suites.
- [x] The only live action is the one exact post-commit attempt explicitly authorized by the operator.
