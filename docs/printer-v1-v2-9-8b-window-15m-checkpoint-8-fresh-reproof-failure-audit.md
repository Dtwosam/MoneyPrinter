# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 Fresh Re-proof Failure Audit

## Verdict

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_FRESH_REPROOF_BLOCKED_PROOF_FIXTURE_FACTORY_ARGUMENT_ORDER_DEFECT_NO_RERUN`

The single explicitly authorized fresh Checkpoint 8 re-proof was consumed and failed safely. No rerun is authorized.

## Controlling evidence

- authorized proof HEAD: `319e842d9b7e6b2e89f4609924341e02017795df`
- proof ID: `C8_REPROOF_AFTER_OFFLINE_REPAIR_20260807`
- Actions run: `31187598614`
- job: `92896002714`
- artifact ID: `8997400153`
- artifact digest: `sha256:230f1a461612c4210596da6567c5e19dc97f0792a305df393e8ffb5a155b49f5`
- harness exit code: `1`
- independent inspector: not reached because the harness failed first
- exact exception: `CHECKPOINT8_PUMPSWAP_FIXTURE_TARGET_MISSING`

The atomic sentinel records attempt ordinal 1, the exact approved HEAD, and the fresh proof ID. This entitlement is consumed permanently.

## Root cause

The production discovery contract is unambiguous:

`direct_migration_discovery._governed_verify()` calls:

`verifier_transport_factory(mint, signature)`

The Checkpoint 8 proof fixture factory instead handles two positional arguments as:

`expected_mint = args[1]`

That interprets the migration signature as the mint and cannot find a fixture candidate, raising `CHECKPOINT8_PUMPSWAP_FIXTURE_TARGET_MISSING` before PumpSwap verification can begin.

The offline real-consumer compatibility helper masked this defect by calling the same fixture factory in the reversed order:

`verifier(first_signature, first_mint)`

Therefore the previous compatibility GREEN result proved compatibility with the helper's reversed call shape, not with the actual production discovery call shape.

## Classification

`PROOF_FIXTURE_CONTRACT_DEFECT`

This is not evidence of a production discovery defect. Production consistently passes `(mint, signature)`. The faulty interpretation exists in the proof-only fixture seam, and the proof-only compatibility probe duplicated the wrong order.

A narrow offline repair is justified under the Python Builder Guide because the failure is deterministic, source-grounded, reproduced by the exact controlling stack trace, and correctable without changing production behavior, provider contracts, Source Governor, Central Scheduler, budgets, persistence law, or capability locks.

## Frozen artifact safety review

Read-only inspection of the uploaded disposable DB established:

- `PRAGMA integrity_check = ok`;
- `PRAGMA foreign_key_check` violations = `0`;
- canonical migration ledger count = `52`;
- governed source requests = `3`;
- governed source responses = `3`;
- governed source failures = `0`;
- discovery work rows = `0`;
- scheduler jobs = `0`;
- memory windows = `0`;
- episodes = `0`;
- memory fingerprints = `0`;
- retrieval queries/matches = `0`;
- paper decisions/positions/trade events/trade audits = `0`.

The terminal artifact records `TERMINAL_FAILED`, cleanup complete, lease released, zero active/orphan work, no restart, no resume, and no successor. The failure occurred in the first `DIRECT_MIGRATION` stage after three fixture transport operations.

The frozen controlling proof summary was not created because the harness failed before freeze. Therefore no independent-inspection PASS may be inferred, and no explicit frozen network-attempt count exists. The harness log contains no network-tripwire exception; the observed failure is the proof-fixture target mismatch above.

## Approved repair boundary

Allowed next work is offline only:

1. design the exact proof-fixture and compatibility-probe argument-order repair;
2. change only the proof harness and directly affected proof-only compatibility coverage if required;
3. add a regression that exercises the canonical `(mint, signature)` factory contract;
4. run minimum sufficient offline tests, compile/static checks, and the focused C8 suite;
5. close the repair and decide fresh re-proof readiness.

Not allowed:

- another proof attempt;
- public campaign runtime;
- provider/network execution;
- authoritative DB mutation;
- memory generation;
- `WINDOW_1H+` activation;
- retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL;
- retry/rerun/resume/restart/successor of the consumed attempt.

## Money-usefulness contribution

The audit prevents a false conclusion that the production migration path is broken and prevents repeated proof attempts from being used as debugging. Repairing the exact fixture-to-production contract improves the reliability of the eventual `WINDOW_15M` clean-memory proof without weakening any market-evidence or financial safety rule.

## Functionality Risks / Setbacks / Efficiency Blockers

- The prior 20-route compatibility gate was insufficient because its helper duplicated the fixture's wrong positional order.
- A one-line fixture change without a production-shaped regression could recreate the same blind spot later.
- The consumed attempt cannot be reused after repair; any later controlling proof requires a new explicit operator authorization.
- Offline GREEN evidence still cannot establish Checkpoint 8 completion.

## Stop condition

Audit complete. Do not rerun the proof. Proceed only to the narrow offline repair design.
