# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 Blocked-Proof Repair Design

## Status

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_BLOCKED_PROOF_REPAIR_DESIGN_APPROVED_FOR_OFFLINE_IMPLEMENTATION_ONLY`

This design follows the completed blocker audit. It authorizes only offline proof-harness/test implementation. It does **not** authorize a second controlling proof attempt, source fetching, runtime, or any capability unlock.

## Baseline

- blocked closeout: `V2_9_8B_WINDOW_15M_CHECKPOINT_8_CONTROLLING_PROOF_BLOCKED_NO_RERUN`
- blocker audit: `V2_9_8B_WINDOW_15M_CHECKPOINT_8_BLOCKER_AUDIT_CONFIRMED_THREE_PROOF_CONTRACT_DEFECTS`
- audit commit: `0d3ad289d33f647d2ce24a96d9adc1611fb2e29a`

## Design objective

Repair the **proof-only** fixture/harness contracts exposed by the consumed attempt, and strengthen pre-proof verification so any later authorization can rely on route-through-real-consumer evidence rather than generic fixture declarations.

Production source validators, Source Governor, Central Scheduler, lifecycle owners, memory owners and paper-trading locks remain unchanged.

## Decision 1 — retire the generic one-object response model

The current `_Checkpoint8DeterministicFixture` may remain as a narrow base/counter helper, but it must no longer be the semantic implementation for every DI port.

The future fixture composition must materialize **port-specific objects** whose callable/method surface exactly matches the production consumer.

Required top-level fixture ports:

1. Pump-origin RPC transport
   - interface: `json_rpc(method, params, timeout_seconds, byte_ceiling)`
   - returns the bare JSON-RPC `result` value, matching `PumpRpcTransport`.

2. Restored direct-Pump migration transport
   - interface: callable `transport(SourceAdapterContext) -> Mapping[str, Any]`
   - returns the complete Solana JSON-RPC envelope plus deterministic measurement metadata, matching `DirectPumpMigrationAdapter`.

3. Secondary HTTP transport
   - interface: `json_get(...)`
   - returns decoded provider body.

Graduated-supply and lifecycle routes must likewise be implemented against their real consuming factory/adapter ports rather than generic `execute()` placeholders.

Every object remains explicitly fixture-marked and provider fallback remains false.

## Decision 2 — separate candidate identity from route-specific event evidence

A single candidate catalog may provide two deterministic Solana memecoin mints, but it must keep these identities distinct:

- `mint`
- `creator`
- `bonding_curve`
- `associated_bonding_curve`
- `pumpswap_pool`
- Pump create signature/slot/block time
- Pump migrate signature/slot/block time

`bonding_curve` and `pumpswap_pool` must never share one ambiguous `pool` field.

The same mint may be proven by different source events, but each route must receive its own lawful event:

### Pump-origin route

Use an exact finalized Pump create/create_v2 transaction accepted by the pinned Pump-origin decoder.

### Restored migration route

Use an exact finalized Pump migrate transaction accepted by `decode_supported_pump_migration_transaction()`:

- exact `PUMP_MIGRATE_DISCRIMINATOR`;
- exact pinned account-role cardinality/order;
- correct Pump program/fixed authorities/program IDs;
- mint/bonding-curve relationship;
- exact PumpSwap pool relationship;
- positive finalized slot/block time;
- exact requested migration signature.

The migration signature page returns the two deterministic migrate signatures. Each transaction lookup returns the matching migrate transaction inside a full JSON-RPC envelope.

No production decoder is relaxed.

## Decision 3 — direct-migration response contract

For `restored_pump_migration_signature_page`, the proof transport returns a mapping equivalent to the live `_rpc_post()` boundary:

```text
{
  jsonrpc: "2.0",
  id: 1,
  result: [finalized signature rows],
  response_bytes: deterministic-positive-int,
  transport_operations_used: 1
}
```

For `restored_pump_migration_transaction`, it returns the same envelope shape with `result` equal to the exact migrate transaction.

Unsupported request kinds fail explicitly; they must never return a generic READY object.

## Decision 4 — terminal identity is extracted from authoritative existing fields

Do not change the production public campaign solely for the proof harness.

Introduce one proof-harness helper, conceptually:

`extract_checkpoint8_terminal_identity(terminal) -> (campaign_id, run_id)`

It must support both real public terminal families.

### Lifecycle terminal

Accept the canonical top-level/report identity already returned by the successful lifecycle path.

### Honest pre-lifecycle terminal

Require:

- top-level `campaign_id`;
- exact campaign-run identity from authoritative existing nested fields.

Allowed pre-lifecycle run-id sources, in priority-neutral exact-correspondence form:

- `cleanup.run_id`
- `reconciliation.active_work.scope.run_id`
- `reconciliation.discovery_parity.scope.run_id`
- durable exhaustion certificate `report.exhaustion_certificate.run_id` when present

All non-empty observed identities must agree. Conflicting identities fail closed.

Do not invent, synthesize or derive a run ID from string patterns.

The helper must also verify any available nested campaign IDs agree with the top-level campaign ID.

## Decision 5 — terminal tests use production-shaped fixtures

Replace the execution-entry fake that always puts `run_id` in `report` with two explicit terminal fixtures:

1. production-shaped lifecycle PASS terminal;
2. production-shaped pre-lifecycle `HONEST_BLOCKED` terminal.

Tests must prove:

- exact identity extraction for each;
- conflicting nested identities fail closed;
- missing run identity fails closed;
- replay receives the exact extracted campaign/run identity;
- one-shot sentinel ordering remains unchanged.

## Decision 6 — mandatory 20-route real-consumer compatibility matrix

Before any future proof authorization, every canonical fixture label must be exercised through its **actual consumer contract**.

Create a proof-only compatibility registry keyed by the existing 20 labels. Each entry identifies:

- canonical label;
- DI route;
- consumer/probe owner;
- exact invocation shape;
- expected raw fixture response shape;
- expected normalized/accepted identity;
- whether the DI seam is intentionally shared with another label.

Each probe must call the real parser/adapter/normalizer/factory boundary offline. A label does not pass merely because its fixture builder exists.

### High-risk required probes

At minimum the matrix must explicitly prove:

- Pump-origin signature page + create transaction;
- restored migration signature page + exact migrate transaction through `DirectPumpMigrationAdapter`;
- PumpSwap graduation verifier/pool confirmation/account batch through their adopted owners;
- DexScreener and GeckoTerminal discovery/reconciliation through adopted normalizers;
- lifecycle exact-pair snapshots through the exact snapshot adapter factory ports;
- CoinGecko/GoPlus/Jupiter/holder context factories through the ordinary preclose consumers.

### Matrix invariants

Success requires:

- exact 20 labels, no missing/extra labels;
- every probe executed at least once;
- no probe returns the fixture object itself;
- no generic READY placeholder accepted as evidence;
- no network/provider fallback;
- intentional shared route identity preserved;
- candidate mint/pool/quote identities exact;
- no production mutation beyond disposable test DBs where a real normalizer requires persistence.

## Decision 7 — operation counting remains route-real

Fixture transport operation count must increase only when a real fixture transport/adapter operation occurs. Composition materialization itself remains zero operations.

Shared objects must not double-count one physical fixture operation merely because multiple labels map to the same DI seam.

## Decision 8 — implementation scope

Preferred implementation scope:

- `scripts/v2_9_8b_checkpoint8_controlling_public_composition_proof.py`
- new/updated Checkpoint 8 proof-only tests
- optionally one proof-only helper module if the 20-route compatibility registry becomes too large for the harness

Do not modify production source normalizers, Scheduler, Source Governor, lifecycle/memory owners or paper capability code unless a separate audit proves an independent production defect.

## RED/GREEN implementation sequence

### Slice A — migration fixture RED

REDs must prove current baseline fails because:

- migration transport callable does not return a mapping envelope;
- signature-page normalization does not complete;
- migration transaction is create-shaped rather than migrate-shaped.

GREEN only after both signature-page and transaction normalization succeed through `DirectPumpMigrationAdapter` with the expected two mints.

### Slice B — terminal identity RED

REDs reproduce the current pre-lifecycle `CHECKPOINT8_TERMINAL_IDENTITY_MISSING` shape using a production-shaped terminal fixture.

GREEN after exact-correspondence extraction works for both real terminal families and conflict/missing negatives remain fail-closed.

### Slice C — 20-route compatibility RED

The registry test initially fails for any route without an actual consumer probe. Implement probes/fixture contracts until all 20 pass.

This slice is offline only. It must not call the public campaign coordinator.

### Slice D — full focused verification

Minimum sufficient gate:

- both proof scripts `py_compile`;
- all Checkpoint 8 focused tests;
- affected direct-migration/source-normalizer tests;
- affected terminal/pre-lifecycle reporting tests;
- static proof that compatibility tests contain no network/provider call path;
- `git diff --check`.

Do not run broad unrelated suites unless these changes touch a broader production owner.

## Future proof authorization boundary

Implementation success does **not** restore the consumed Checkpoint 8 entitlement.

After offline implementation/proof, write a repair closeout stating exactly what was repaired and what remains unproven. A future controlling attempt requires a **new explicit operator-approved proof lane/authorization** with a fresh proof ID and fresh disposable targets.

No automation may silently create that authorization.

## Money-usefulness contribution

This design improves the trustworthiness of the evidence needed for automated `WINDOW_15M` memory growth. It makes source fixtures prove what the real Printer owners would actually accept, reducing the chance of spending another bounded proof on test-only semantics while preserving strict Solana source validation.

## What this design improves

- separates event identity from market/pool identity;
- aligns each fixture with the real consuming port;
- covers honest blocked terminals as first-class public outcomes;
- upgrades readiness from registry coverage to real-consumer compatibility;
- keeps production safety rules intact.

## What remains locked

Even after implementation, the following remain locked until separately authorized:

- any second controlling proof;
- runtime/source fetching;
- memory generation outside offline test fixtures;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions, trade events, audits and PnL;
- `WINDOW_1H+` activation.

`WINDOW_5M_MICRO_EVENT` remains support-only.

## Proof/test needed before design completion can advance to repair closeout

The design is complete when this document is committed. Implementation may then proceed only through the RED/GREEN offline sequence above. No runtime proof is part of design completion.

## Functionality Risks / Setbacks / Efficiency Blockers

- The 20-route matrix may expose additional latent fixture mismatches. Those are expected audit findings, not permission to weaken consumers.
- Reusing one generic fixture object would reduce code volume but recreate the semantic ambiguity that caused the consumed attempt to fail.
- Building an exact migrate transaction is more work than returning a mocked token row, but bypassing the pinned decoder would defeat the purpose of the public-composition proof.
- A production terminal API cleanup could simplify the harness, but bundling it here would broaden scope without necessity.
- No future proof should be scheduled until all offline route probes are GREEN and a separate authorization is created.

## Stop condition

Design complete. Proceed only to offline TDD implementation. Do not run Printer runtime or another controlling proof.
