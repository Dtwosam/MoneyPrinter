# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 Blocker Audit

## Verdict

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_BLOCKER_AUDIT_CONFIRMED_THREE_PROOF_CONTRACT_DEFECTS`

This is an audit-only follow-up to the consumed Checkpoint 8 controlling attempt. It authorizes no repair, runtime, source fetching, memory generation, replay, or second proof attempt.

## Governing state

The controlling attempt remains closed as:

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_CONTROLLING_PROOF_BLOCKED_NO_RERUN`

Controlling evidence:

- approved proof HEAD: `e263f5f3c6539b983314f7e66ea720ed4ec2e935`
- proof ID: `C8_CONTROLLING_E263F5F3_20260807`
- Actions run: `31180769946`
- artifact ID: `8994671067`
- primary terminal: `HONEST_BLOCKED / SOURCE_AVAILABILITY_FAILURE`
- durable source failure: `direct_pump_rpc_malformed` / `Solana RPC payload is not an object`
- secondary harness failure: `CHECKPOINT8_TERMINAL_IDENTITY_MISSING`

No rerun is authorized.

## Root cause 1 — migration fixture callable returns the wrong transport shape

The actual ordinary V2-9.8B restored migration path is **not** the older Pump-origin `PumpRpcTransport` contract that returns the JSON-RPC `result` value.

The restored owner is `printer_v1.sources.direct_pump_migration.DirectPumpMigrationAdapter`.

Its transport contract is:

- one callable accepting `SourceAdapterContext`;
- returns a `Mapping[str, Any]` representing the complete Solana JSON-RPC response envelope;
- the normalizer requires the envelope to be an object;
- it then requires `result` to be present;
- for `restored_pump_migration_signature_page`, `result` must be a finalized signature list.

The ordinary discovery owner `run_direct_migration_discovery()` calls `coerce_migration_transport()`. Because the Checkpoint 8 fixture object is callable, it is accepted directly and passed to `DirectPumpMigrationAdapter`.

Checkpoint 8 maps:

`direct_pump_finalized_migration_transport -> top_level.migration_transport`

But `_Checkpoint8DeterministicFixture.__call__()` increments its counter and returns `self`. Therefore the actual direct-migration adapter receives a fixture object rather than a mapping. Its production normalizer correctly fails with:

`direct_pump_rpc_malformed: Solana RPC payload is not an object`

This exactly matches the durable source-failure row from the controlling proof.

### Why pre-proof verification missed it

The fixture-response semantics tests proved payload behavior only for:

- `top_level.pump_transport.json_rpc(...)`, and
- `top_level.secondary_transport.json_get(...)`.

The 20-label readiness summary merely proved that each canonical label had a declared payload-contract string. It did **not** execute `top_level.migration_transport` through the real `DirectPumpMigrationAdapter` / SourceAdapterContext interface.

The test therefore proved registry coverage, not actual route-specific normalization compatibility.

## Root cause 2 — migration candidate transaction is the wrong protocol event

Even if the first response were wrapped in a correct JSON-RPC envelope, the existing Checkpoint 8 candidate records would still fail on the next migration transaction lookup.

`_checkpoint8_candidate_records()` builds each candidate using `_checkpoint8_create_transaction()`. That helper constructs an exact Pump **create** instruction and is appropriate for the historical Pump-origin acquisition route.

The restored migration route instead calls `decode_supported_pump_migration_transaction()`, whose pinned contract requires an exact Pump **migrate** instruction/account layout (`PUMP_MIGRATE_DISCRIMINATOR`) and the associated PumpSwap migration relationships.

Therefore the same create transaction cannot lawfully serve both:

- `pump_origin_solana_rpc_transport`, and
- `direct_pump_finalized_migration_transport`.

This is a latent second fixture defect that the controlling attempt did not reach because root cause 1 failed first.

### Required architectural correction

The future fixture design must use route-specific response objects. Shared candidate identity is acceptable, but the source event proving that identity must match the exact owner:

- Pump-origin route → finalized Pump create transaction;
- restored migration route → finalized Pump migrate transaction + correct JSON-RPC envelope.

No decoder, admission, or production source contract should be weakened to accommodate the fixture.

## Root cause 3 — harness terminal identity extraction modeled only the success fake shape

The public `run_operational_campaign()` legitimately has two terminal paths:

1. lifecycle-success/terminal path; and
2. honest pre-lifecycle terminal path.

The failed controlling attempt took the second path through `_finalize_returned_pre_lifecycle_result()`.

That real returned terminal contains:

- top-level `campaign_id`;
- no top-level `run_id`;
- a persisted report descriptor under `report` containing `campaign_id`, report identity/path/hash and accounting values, but **not** `run_id`;
- authoritative campaign-run identity under `cleanup.run_id` and independently under `reconciliation.active_work.scope.run_id` (and the exhaustion certificate).

The Checkpoint 8 harness extracted:

- `campaign_id = terminal.campaign_id OR report.campaign_id`;
- `run_id = report.run_id OR terminal.run_id`.

Because neither of those two run-id fields exists on the honest pre-lifecycle terminal, the harness raised `CHECKPOINT8_TERMINAL_IDENTITY_MISSING` after the public campaign call had already completed.

### Why pre-proof verification missed it

The execution-entry test fake `_terminal()` injected:

```text
report = {campaign_id: campaign-c8, run_id: run-c8}
```

That fake modeled the harness's desired shape rather than both real public terminal shapes. The tests therefore proved sentinel/call ordering against a synthetic success-like terminal, but did not prove terminal-identity extraction against a real pre-lifecycle `HONEST_BLOCKED` result.

## Production-path assessment

No evidence supports weakening or changing these production contracts as part of the blocker repair:

- `DirectPumpMigrationAdapter` correctly requires a JSON-RPC envelope and correctly failed closed on a non-object fixture response.
- `decode_supported_pump_migration_transaction()` correctly distinguishes migrate from create evidence.
- the public campaign correctly terminalized `HONEST_BLOCKED`, persisted failure evidence, cleaned up, released its lease, and left zero downstream residue.

The defects are in the Checkpoint 8 proof fixture/harness and its pre-proof verification coverage.

A separate design review may decide whether adding a top-level `run_id` to the production pre-lifecycle terminal is independently desirable, but it is **not required** to repair the proof harness because authoritative run identity already exists in the returned terminal and durable report graph.

## Verification gap exposed by the attempt

The current phrase “all routes have explicit payload contracts” is too weak for one-shot proof readiness.

Before any future proof authorization, offline verification must exercise **every canonical route through its actual consuming adapter/factory/normalizer interface**, not merely assert labels or call generic fixture methods.

At minimum the route matrix must prove:

- exact input call shape;
- exact raw response shape;
- real normalizer acceptance;
- expected target/candidate identity;
- zero provider fallback;
- shared-seam identity where intentional;
- no route returns `self`, a generic READY placeholder, or a payload valid only for a different owner.

The matrix must include both normal/success and fail-closed contract checks for the high-risk restored-migration and terminal-identity paths.

## Money-usefulness contribution

This audit prevents a future one-shot attempt from being spent on a fixture that is structurally valid only at the DI registry level but semantically invalid at the ordinary source owners. It improves the reliability of the evidence that will eventually support automated `WINDOW_15M` clean-memory production, without weakening real source validation.

## What this audit improves

- pins the exact first source-contract mismatch;
- discovers the next latent migration-transaction mismatch before another run;
- pins the exact terminal-return identity mismatch;
- identifies the missing verification layer: route-through-real-consumer compatibility.

## What this audit does not unlock

This audit unlocks no implementation and no new proof attempt. It does not unlock:

- source fetching;
- runtime campaigns;
- memory generation;
- a second Checkpoint 8 proof;
- `WINDOW_1H+`;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions, trade events, audits, or PnL.

`WINDOW_5M_MICRO_EVENT` remains support-only.

## Required design before implementation

A separate repair-design lane should specify, without executing runtime:

1. a route-specific direct-migration fixture transport that returns the exact JSON-RPC envelope expected by `DirectPumpMigrationAdapter`;
2. a canonical deterministic Pump migrate transaction fixture, separate from the create transaction fixture;
3. terminal-identity extraction that accepts both real lifecycle and honest pre-lifecycle public terminal shapes without inventing identity;
4. an offline 20-route consumer-compatibility matrix through actual adapters/normalizers;
5. explicit proof that production source/terminal owners remain unchanged unless a separate production-contract reason is independently established;
6. the authorization model for any future proof attempt, which must be separate from the consumed Checkpoint 8 entitlement.

## Minimum proof required after any later implementation

Before any new controlling-proof authorization:

- new REDs must fail on all three defects at the current blocked baseline;
- implementation must make those REDs GREEN;
- the complete focused C8 gate must remain GREEN;
- actual direct-migration signature-page and migration-transaction normalization must pass offline using the ordinary adapters;
- both lifecycle-success and pre-lifecycle terminal identity extraction must pass against production-shaped terminal fixtures;
- all 20 canonical routes must pass their real-consumer compatibility checks;
- no runtime, network, provider, memory, or proof attempt may occur during this verification.

## Functionality Risks / Setbacks / Efficiency Blockers

- Fixing only the JSON-RPC envelope would expose the latent create-vs-migrate transaction defect next.
- Fixing only the two observed paths without a real-consumer 20-route matrix risks spending a future proof on another generic fixture mismatch.
- Changing production normalizers to accept weaker fixture shapes would reduce source safety and is not justified by this audit.
- Changing the public production terminal contract solely for the harness would broaden scope unnecessarily; the harness can consume existing authoritative identity.
- The consumed one-shot entitlement remains non-reusable regardless of repair success.

## Stop condition

Audit complete. Do not implement or rerun. The next lawful step is a separate design/specification lane for the proof-only repairs and offline consumer-compatibility gate.
