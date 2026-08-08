# Printer V1 Post-DTW83 Pilot-Input Activation-Route Audit Closeout

## Verdict

`V2_9_8B_POST_DTW83_PILOT_INPUT_ACTIVATION_READINESS_AUDIT_PASS_ROUTE_CONTRACT_DRIFT_CONFIRMED`

## Controlling attempt

- Authorization: `V2_9_8B_WINDOW_15M_AUTH_20260808T171829Z` — permanently consumed.
- Execution: `20260808T172123Z-fc51627f6c8d`.
- Authorized Git: `agent/v2-9-8b-post-dtw82-window15m-authorization-preparation` at `3da34d21d27ddfad1e62f901f4d87c01d90b62d5`.
- Terminal: `CAMPAIGN_PRE_LIFECYCLE` / `PilotInputReadinessError:READINESS_GATE_UNMET: PILOT_INPUT_BLOCKED_ACTIVATION`.
- `lifecycle_started=null`; no retry, rerun, resume, restart, or successor.
- Cleanup completed; lease released; Scheduler runtime calls `0`.

## Audit finding

The blocker is a producer/consumer activation-route vocabulary drift at the MEMORY_OBSERVATION pilot-input boundary.

At the exact authorized HEAD:

1. `memory_observation_activation.AdmissionAuthority` defines the current source-specific activation authorities as `MARKET_PRESENT_POOL` and `DIRECT_PUMP_PUMPSWAP`.
2. `graduated_supply_front_door.SourceSpecificCandidateAdmission.origin_route` returns the carried `origin_proof.origin_route` for a direct candidate, otherwise it returns `admission_authority.value` for a market-present candidate.
3. `_source_specific_admission_for()` validates `MARKET_PRESENT_POOL` candidates from DexScreener/GeckoTerminal present-pool evidence without consulting the migration registry and returns them without a Pump origin proof.
4. `authoritative_live_operational_campaign` projects the source-specific authority into the memory-activation candidate and ultimately into `ReadinessCandidate.activation_route`.
5. `pilot_input_readiness.evaluate_readiness_gates()` still uses the legacy-only allowlist `{"GRADUATION_NATIVE", "PUMP_CREATE"}` for both readiness purposes. After discovery, selection, market and MEMORY_OBSERVATION gates pass, any selected candidate carrying `MARKET_PRESENT_POOL` or `DIRECT_PUMP_PUMPSWAP` therefore returns `PILOT_INPUT_BLOCKED_ACTIVATION`.

The live evidence is consistent with that exact path. The attempt produced fresh exact-pool PumpSwap market candidates and MEMORY_OBSERVATION_ELIGIBLE rows. Selected candidates included `ACBAYroh2xzPgu3XhLnRrzXKewYX416DqzBfTTUVpump` and `FC6WBsiqnoq5KqjcXA5mawtshXkTDFPjY3DevsNppump`, sourced through `FRESH_AGGREGATOR_PROTOCOL_CONFIRMED` present-pool evidence. The gate therefore reached activation-route validation rather than failing discovery, selection, market or memory-observation eligibility first.

## Not the root cause

- Holder budget state is not the blocker. `MEMORY_OBSERVATION` readiness explicitly treats holder eligibility as context only. `FC6...` carried `SOURCE_NOT_EVALUATED_BUDGET_BOUND`, but this does not lawfully block memory-observation readiness.
- The candidate-local Pump migration rejection on source failure `224` did not kill the shared channel and was not the terminal readiness reason.
- GeckoTerminal rate-limit failures `225` and `226` reduced source availability but did not prevent formation of the selected exact-market pair and are not the direct activation terminal.
- The user-approved no-redundant-registry-confirmation law remains preserved; no repair may reintroduce a post-discovery registry membership gate.

## Authoritative post-attempt state

- DB SHA-256: `3614c99cf4b2d501b6a46ed92ebc784e297261fcf443e316c181f5941d95c603`.
- Size: `70045696`.
- Inode: `1230526`.
- mtime_ns: `1786209702000684860`.
- Integrity: `ok`; foreign-key violations: `0`.
- 15 source requests, 12 responses, 3 failures.
- Source/Scheduler/lifecycle accounting closed terminally.
- `printer_memory_windows` delta `0`; `printer_scheduler_jobs` delta `0`; no retrieval, paper-decision, position, trade, audit or PnL capability was activated.

## Money-usefulness contribution

This audit prevents another scarce live authorization from being spent on a deterministic wiring mismatch. It confirms that useful exact-market candidates were being produced and that the failure was at the activation contract boundary rather than candidate-market usefulness itself.

## What this improves / does not unlock

The audit identifies the exact repair target: align MEMORY_OBSERVATION pilot-input route validation with the canonical source-specific `AdmissionAuthority` contract while preserving legacy FUTURE_ACTION behavior where still required.

It unlocks no implementation, runtime, new authorization, WINDOW_1H+, retrieval, decision, BUY/SELL/HOLD, position, trade, audit, PnL, wallet, signing, live execution, real funds, paid API, scoring/ranking/confidence, embeddings or vectors.

## Required next proof path

A separate design lane must specify the narrow consumer-contract repair. Implementation, if approved later, must use focused deterministic tests only before a bounded proof and closeout. No new real ordinary WINDOW_15M authorization may be prepared until repair proof, closeout, and authoritative DB/operational rereadiness pass.

## Functionality Risks / Setbacks / Efficiency Blockers

- Blindly adding strings to `LAWFUL_ROUTES` could collapse source-specific authority semantics; the design must use the canonical authority model deliberately.
- FUTURE_ACTION legacy route behavior must not be weakened while fixing MEMORY_OBSERVATION.
- Holder gating must remain non-blocking only for MEMORY_OBSERVATION and remain unchanged for future-action eligibility.
- Unknown route values must continue to fail closed.
- The consumed authorization remains permanently non-reusable.
