# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 Blocked-Proof Repair Closeout

## Verdict

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_BLOCKED_PROOF_OFFLINE_REPAIR_PASS_NO_REPROOF_AUTHORIZATION`

The proof-only defects exposed by the consumed Checkpoint 8 controlling attempt have been repaired and proven offline. This closeout does **not** authorize a second controlling proof and does not change the prior controlling-attempt verdict:

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_CONTROLLING_PROOF_BLOCKED_NO_RERUN`

## Governing source stack

This work remains subordinate to the active Printer V1 stack:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`

## Repair lineage

- blocker audit: `0d3ad289d33f647d2ce24a96d9adc1611fb2e29a`
- repair design: `e443574a5b9c6fc971897d5ccbf34bb8ebc287e3`
- migration/terminal A-B repair: `5bfcd7b51dcd311c5d1a1aebf4fb8b9e6f79f23a`
- real-consumer fixture-port repair: `9feee2b102b31bb2ae095d3092956fee322036b4`
- temporary-CI cleanup head before this closeout: `93253162aaece974e0cc9d882d7eef68fe658beb`

Temporary verification PR `#23` was closed without merge. All temporary Checkpoint 8 repair workflows were removed after verification.

## What was repaired

### 1. Restored direct-Pump migration fixture contract

The Checkpoint 8 fixture now implements the real `DirectPumpMigrationAdapter` callable contract and returns a complete Solana JSON-RPC envelope rather than a fixture object/bare result.

### 2. Exact Pump migrate evidence

Candidate fixtures now separate:

- mint;
- bonding curve;
- PumpSwap pool;
- Pump create signature/transaction;
- Pump migrate signature/transaction.

The migration route uses an exact pinned Pump migrate instruction/account layout with `PUMP_MIGRATE_DISCRIMINATOR` and the expected PumpSwap relationships. Production decoders were not weakened.

### 3. Public terminal identity extraction

The proof harness now extracts campaign/run identity by exact correspondence across the authoritative fields already returned by both:

- lifecycle terminal results; and
- honest pre-lifecycle terminal results.

Conflicting nested identities fail closed. No run ID is synthesized from naming conventions.

### 4. Port-specific fixture semantics

The previous generic semantic behavior was replaced for the canonical DI ports with route-specific behavior covering:

- Pump-origin RPC;
- direct migration;
- PumpSwap confirmation/account batch;
- secondary discovery;
- DexScreener direct/batch;
- GeckoTerminal nomination/reconciliation;
- lifecycle Dex/Gecko snapshot factories;
- CoinGecko, GoPlus, Jupiter quote, Solana RPC holder, and Helius backup context factories.

Generic READY placeholders are not accepted by the compatibility gate.

### 5. Offline 20-route real-consumer compatibility gate

A new proof-only compatibility owner exercises every canonical label through a real consuming adapter/normalizer/factory boundary and records all 20 probe results.

Success requires:

- exact 20-label registry;
- consumer executed for every label;
- every label accepted;
- operation count delta for every label;
- no returned fixture self;
- no generic READY placeholder;
- no provider fallback;
- zero external-network attempts under the Checkpoint 8 network tripwire.

## RED/GREEN evidence

### A-B RED

Initial blocked-proof repair tests:

- **4 failed** at the blocked baseline;
- failures exactly matched the audited migration-contract and terminal-identity defects.

### A-B GREEN

GitHub Actions offline repair run:

- run: `31183595896`
- job: `92882571374`
- blocker repair tests: **4 passed**
- focused C8 tests at that slice: **91 passed in 18.03s**
- `py_compile`: PASS
- offline no-proof guard: PASS
- `git diff --check`: PASS

The workflow committed `5bfcd7b51dcd311c5d1a1aebf4fb8b9e6f79f23a` only after the GREEN gates.

### 20-route compatibility RED

Initial real-consumer compatibility tests:

- **2 failed** because the compatibility owner was intentionally absent.

### 20-route compatibility GREEN

GitHub Actions run:

- run: `31185418562`
- job: `92888613742`
- real-consumer compatibility tests: **2 passed in 3.53s**
- full focused C8 wildcard gate: **93 passed in 20.57s**
- harness `py_compile`: PASS
- compatibility module `py_compile`: PASS
- offline static guard: PASS
- `git diff --check`: PASS

The workflow committed `9feee2b102b31bb2ae095d3092956fee322036b4` only after all gates passed.

Post-test commits through `93253162aaece974e0cc9d882d7eef68fe658beb` removed only five temporary CI workflow files. No harness, compatibility module, test, production source owner, Scheduler owner, Source Governor owner, lifecycle owner, memory owner, or paper-trading code changed after the 93-test GREEN run.

## Money-usefulness contribution

This repair materially improves the reliability of the first automation target, `WINDOW_15M`, by ensuring that bounded proof fixtures are accepted through the same source/normalizer contracts used by Printer rather than through test-only approximations. It lowers the chance that a future authorized proof is spent on fixture-shape defects while preserving strict source and scheduler safety.

## What this lane improves

- exact restored-migration semantics;
- create-vs-migrate evidence separation;
- honest blocked terminal handling;
- all 20 canonical fixture routes through real consumer boundaries;
- fail-closed generic-placeholder rejection;
- stronger offline proof-readiness evidence.

## What this lane still does not unlock

This closeout does **not** unlock:

- a second Checkpoint 8 controlling proof;
- any reuse of the consumed sentinel/attempt;
- source fetching/runtime outside separately authorized work;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, or `WINDOW_24H`;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions;
- trade events or trade audits;
- PnL;
- live wallet/private keys/real funds/live execution.

`WINDOW_5M_MICRO_EVENT` remains support-only.

## Proof/test needed before any later controlling attempt

The offline repair is complete, but any future controlling attempt requires a **new explicit operator-approved proof lane/authorization**. That future authorization must name:

- the exact approved repair HEAD;
- a new proof ID;
- a fresh disposable DB;
- a fresh artifact root;
- a fresh one-shot sentinel namespace;
- the exact bounded proof acceptance law;
- an explicit statement that the prior C8 controlling attempt remains historical failure evidence and is not being retried/resumed.

Before issuing such authorization, a fresh readiness review should confirm the repair closeout lineage and the 93-test GREEN evidence. No automation or implementation step may silently create the new authorization.

## Functionality Risks / Setbacks / Efficiency Blockers

- A future controlling proof remains unproven because no second proof has been authorized or run.
- The prior failed attempt remains controlling historical evidence for the original C8 authorization.
- The 20-route matrix reduces fixture-contract risk but cannot prove full campaign/lifecycle success without a separately authorized bounded proof.
- Broad unrelated regression suites were intentionally not added; verification remained risk-scoped to Checkpoint 8 and directly affected source contracts.

## Stop condition

Offline repair and closeout are complete. Stop before any new runtime proof. The next lawful step is a separate re-proof readiness/authorization decision, not an automatic rerun of Checkpoint 8.
