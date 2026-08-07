# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — Pre-Proof Repair Design

## Status

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_PRE_PROOF_REPAIR_DESIGN_APPROVED`

Design baseline:

`b5be2ec7db87796b9c8cce9105bee095a2b81f0b` — pre-proof readiness audit

This design repairs only the three pre-proof blockers. It authorizes no controlling campaign run.

## 1. Preserve two distinct invocation-authority laws

Production/authorized campaigns keep the existing authorization-marker and invocation-marker law unchanged.

C8 uses a separate evidence mode:

`DISPOSABLE_PUBLIC_COMPOSITION_PROOF`

Mode selection must come from the durable configuration-owned `operational_database_target_expectation.target_kind`, never from a caller boolean or report payload.

### Production/authorized mode

Keep all current requirements unchanged:

- exactly one authorization marker;
- exact authorization-marker reconstruction and digest;
- exact supervision invocation marker;
- exact marker/supervision/factory correspondence;
- existing production/authorized DB binding law.

### C8 proof mode

The configuration must contain the dedicated proof expectation and no fabricated authorization facts.

Required proof invocation evidence is reconstructed from durable owners only:

- exact proof expectation/version/kind;
- proof id/schema;
- exact non-production DB path and DB target identity;
- canonical migration count/head;
- execution/campaign/run/cycle/configuration identities;
- exact fixture-composition manifest SHA;
- provider execution false;
- automatic retry/manual rerun/resume/restart/successor false;
- exactly one matching supervision row;
- exactly one matching factory binding;
- zero additional supervision/factory-binding history.

The report may retain the existing `authorization_and_invocation` container for backward compatibility, but it must add an explicit `evidence_mode` and proof-specific fields. In C8 mode:

- `authorization_marker` remains absent/None;
- authorization count is 0;
- no authorization id/SHA/application marker/consumption fact is synthesized;
- proof expectation and proof invocation evidence are recorded separately.

## 2. Mode-specific full-run acceptance

`evaluate_campaign_acceptance_gate()` must branch on the durable evidence mode.

Production mode evaluates the existing authorization checks exactly as today.

C8 proof mode replaces only the authorization-marker-specific checks with proof checks:

- `proof_expectation_exact`;
- `proof_invocation_identity_exact`;
- `proof_supervision_factory_correspondence_exact`;
- `proof_no_authorization_facts`;
- `proof_no_provider_or_reuse_permission`;
- `proof_manifest_exact`.

All non-authorization acceptance checks remain shared and unchanged: two distinct targets, exactly two terminal WINDOW_15M lifecycles, Scheduler ownership/terminality, six-unit equality, cadence completion, quality consistency, cleanup, lease release, zero active/locked work, forbidden-delta locks, no retry/restart/resume/successor, and canonical report completeness.

A C8 proof cannot PASS merely because it is proof mode; it must satisfy every shared full-run requirement plus the proof-specific invocation law.

## 3. Mode-specific evidence hashes and replay

Production report/replay keeps the existing authorization/invocation marker hashes unchanged.

C8 report adds:

- `proof_expectation_sha256`;
- `proof_invocation_evidence_sha256`.

Both hashes use the existing canonical campaign-evidence serialization owner where applicable. C8 does not populate an authorization-marker hash with a placeholder.

The report body hash must cover the selected evidence mode and its mode-specific hashes.

Public `report_only()` independently resolves the durable evidence mode from the configuration and reconstructs the corresponding evidence/hashes from DB owners. It must never trust the report's claimed mode by itself.

Production replay remains contract-equivalent to current behavior.

## 4. Exact disposable artifact-root replay

Extend `_load_exact_terminal_summary()` with an explicit artifact-root input whose default remains production `ARTIFACT_ROOT`.

`report_only()` must pass its resolved `replay_artifact_root` into that helper.

C8 replay must therefore search both the canonical report directory and terminal-summary fallback only inside the bound disposable artifact root.

No fallback to production artifact storage is allowed when an explicit disposable root is supplied.

## 5. Repository-owned controlling proof harness

Add one proof-only harness, not a second operational runner:

`scripts/v2_9_8b_checkpoint8_controlling_public_composition_proof.py`

Its only operational action is exactly one call to the existing public `run_operational_campaign()`.

It must not duplicate Source Governor, Scheduler, discovery, selection, lifecycle, memory, cleanup, reporting or replay orchestration.

### Before the call

The harness must:

1. require exact approved Git HEAD and clean tracked tree;
2. refuse if a fixed controlling-attempt sentinel already exists;
3. create one fresh canonically migrated disposable DB;
4. create one fresh disposable artifact root;
5. record pre-run DB SHA, migration count/head, integrity/FK and protected-capability counts;
6. build the exact canonical 20-label fixture composition using existing fixture/adapter shapes and existing normalizers;
7. validate every fixture builder/output marker and shared-seam identity;
8. install the process-local network tripwire;
9. construct the validated disposable proof plan/runtime;
10. atomically persist the one-shot attempt sentinel immediately before the public coordinator call.

No `--force`, retry, resume, restart or successor option is allowed.

### Deterministic success fixtures

The fixture set must produce exactly two lawful Solana memecoin candidates while preserving real gates.

It may provide deterministic external responses only. It may not inject:

- selection outcome;
- lifecycle disposition;
- memory quality;
- clean-memory episode;
- Scheduler result;
- Source Governor result;
- campaign acceptance result.

Fixture data must be structurally valid for the existing Pump/PumpSwap/DexScreener/GeckoTerminal/preclose/holder/Jupiter/GoPlus/RPC adapters used by the composition. Infrastructure mints remain excluded. Pair/mint identity must remain exact.

Labels that share one existing DI seam must materialize to the same marked fixture object, matching the already-proven execution-binding plan.

## 6. Network tripwire

The controlling harness installs a proof-only low-level network tripwire before invoking `run_operational_campaign()` and restores it afterward.

At minimum it must intercept external AF_INET/AF_INET6 connection creation at the Python socket boundary, including direct `socket.connect`/`connect_ex`/`create_connection` paths. DNS/address-resolution attempts may also be trapped and counted.

Unix-domain/local filesystem behavior required by SQLite must not be blocked.

Any external network attempt:

- increments the independent attempt counter;
- records a redacted attempt class/target;
- fails immediately;
- consumes the controlling attempt; no automatic second campaign is created.

The frozen proof summary records:

- network/provider attempt count;
- fixture transport operation count;
- exact fixture registry manifest SHA.

Success requires network/provider attempt count = 0 and fixture transport operation count > 0.

## 7. One-shot controlling proof sequence

After the sentinel is persisted, the harness:

1. calls `run_operational_campaign(operator_approved=True, disposable_proof=runtime)` exactly once;
2. permits the ordinary natural WINDOW_15M lifecycle to finish;
3. records returned terminal identity/evidence;
4. calls public `report_only()` exactly once with the exact campaign/run, disposable DB and disposable artifact root;
5. records post-run integrity/FK, protected-table deltas, active/locked work and longer-window counts;
6. freezes a controlling proof summary plus hashes;
7. exits without launching any successor.

A failed call or failed acceptance consumes the controlling attempt. The harness must not offer or perform a rerun.

## 8. Independent read-only inspector

Add a separate proof-only inspector:

`scripts/v2_9_8b_checkpoint8_independent_inspection.py`

It accepts only the frozen controlling proof directory and refuses the canonical production DB.

It opens the proof DB read-only and independently recomputes:

- migration ledger/integrity/FK;
- campaign/run/cycle/configuration/factory graph;
- proof expectation and proof invocation evidence;
- exact two terminal WINDOW_15M windows;
- clean-memory episodes/fingerprints for both current-run windows;
- campaign acceptance evidence/hash reconstruction;
- Source Governor/Scheduler ownership evidence;
- cleanup/lease timestamps and lease-file absence;
- zero active/locked/orphan owned work;
- report row/artifact parity;
- frozen `report_only()` result and zero replay work;
- protected capability zero deltas;
- no WINDOW_1H/4H/12H/24H activation;
- no retry/rerun/resume/restart/successor;
- exact fixture manifest and frozen zero-network-attempt evidence.

It writes only a separate inspection artifact; it never mutates the proof DB.

## 9. RED -> GREEN entry contracts before proof

Minimum sufficient deterministic contracts:

1. production full-run authorization acceptance remains unchanged;
2. C8 full-run acceptance succeeds only with exact durable proof expectation/invocation evidence and no auth marker;
3. any authorization/app-marker fact in C8 proof expectation blocks;
4. proof identity/manifest/reuse/provider drift blocks acceptance;
5. proof report hashes use proof-specific hashes and no fake authorization hash;
6. public proof replay reconstructs proof evidence independently and preserves zero-work replay;
7. terminal-summary fallback uses the explicit disposable artifact root and never production root;
8. network tripwire catches an attempted external socket connection and restores hooks afterward;
9. exact success fixture composition covers all canonical labels and materializes with zero live fallback;
10. one-shot sentinel prevents a second public coordinator call;
11. independent inspector refuses canonical DB and uses SQLite read-only mode;
12. existing 41 C8 contracts remain GREEN.

Because this is a pre-live-proof checkpoint and the repair touches full-run acceptance/replay, run the nearest existing full-run-accounting, campaign-report/replay, DB-binding and authoritative-owner regressions in addition to the C8 contracts. Do not broaden unrelated failures automatically.

## 10. Pre-proof entry verdict

Only after all repair contracts and directly affected regressions are GREEN may the lane produce:

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_CONTROLLING_PROOF_ENTRY_READY`

That verdict authorizes exactly one controlling C8 proof attempt. It does not authorize a retry if the attempt fails.

## Money-usefulness contribution

This repair makes the final integration proof truthful: Printer can prove clean-memory usefulness without pretending a no-auth proof was a production authorization, without reading unrelated production artifacts, and without hidden provider fallback.

## What this design improves

- preserves production authorization security while making C8 proof evidence truthful;
- gives report/replay a proof-aware independent evidence law;
- closes disposable artifact-root isolation;
- creates a reproducible one-shot proof harness with an independent network tripwire;
- creates a separate read-only inspection step.

## What remains locked

Until the entry verdict passes, the controlling C8 proof remains locked. All provider/live execution, longer-window proofs, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, wallets, signing, real funds, paid APIs, scoring/ranking/confidence/weighted logic and embeddings/vectors remain locked. `WINDOW_5M_MICRO_EVENT` remains support-only.

## Functionality Risks / Setbacks / Efficiency Blockers

1. A mode check derived from a caller flag instead of durable configuration could bypass production authorization; durable target kind owns dispatch.
2. Reusing authorization-marker field names with fabricated values would violate C8; proof-specific evidence/hashes are mandatory.
3. Changing production acceptance while adding proof mode risks regression; the authorized branch must remain contract-equivalent.
4. Static fixture success that bypasses real Source Governor/Scheduler/lifecycle owners would create a false integration proof.
5. A high-level HTTP-only tripwire may miss RPC/WebSocket fallback; socket-boundary blocking is required.
6. The natural 15m proof is costly and one-shot; deterministic entry verification must be completed first.
