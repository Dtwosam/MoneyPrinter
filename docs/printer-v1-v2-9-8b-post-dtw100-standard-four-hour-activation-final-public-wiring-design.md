# Printer V1 V2-9.8B Post-DTW100 Standard Four-Hour Activation Final Public Wiring Design

## Verdict

`V2_9_8B_POST_DTW100_STANDARD_FOUR_HOUR_ACTIVATION_FINAL_PUBLIC_WIRING_DESIGN_PASS`

Design baseline: `4ecedf7cc88ba09c80f90ed5a6f4ca7ca75ef21b`.

## Design Decision

Finish activation by threading the already-approved `STANDARD_FOUR_HOUR_POLICY` through the existing one-shot public coordinator and live operational owner. Do not create another runner, proof path, source owner, Scheduler owner, or DB owner.

### 1. Immutable policy identity

Add `policy_version` to `_OperationalCampaignPolicy`.

- ordinary run keeps `V2-9.8-15M-OPERATIONAL-V1`;
- historical selective-1h proof keeps its current policy identity;
- standard run uses `V2-9.8-STANDARD-4H-OPERATIONAL-V1`.

Campaign configuration, authorization marker, command policy version, lifecycle configuration and terminal projection must derive from the selected policy rather than hard-coded ordinary values.

### 2. Standard read-only preflight

Add `build_standard_four_hour_preflight()` as a read-only overlay on the existing operational preflight. It performs no source call or write and reports:

- mode `standard-four-hour-preflight`;
- token capacity 2;
- root `WINDOW_15M`;
- continuous first hour = true;
- standard continuous 4h = true;
- only `WINDOW_12H` / `WINDOW_24H` locked;
- maximum outer lifecycle ceiling 230 governed requests / 210 Scheduler rows;
- 114 governed requests per token outer ceiling;
- no retries/restart/resume/successor.

This preflight does not create or consume a final authorization.

### 3. Authorization/DB binding

Policy identity, not the generic `selective_1h_continuation` boolean, decides whether external authorization runtime facts are required.

- ordinary one-shot run: existing authorization behavior unchanged;
- historical selective-1h proof: existing no-external-authorization behavior unchanged;
- standard-four-hour run: validated standard authorization is mandatory and its runtime facts must reach `validate_authorized_database_preflight()` and `build_operational_database_target_binding()`.

### 4. Production-persistent live owner

Keep `fifteen_minute_only=True` for ordinary and standard production operation because that flag currently selects `proof_mode=False`, `four_hour_proof_mode=False` and `operational_persistent_mode=True`.

Add one explicit `standard_four_hour_campaign: bool = False` owner argument. When true:

- require `fifteen_minute_only=True`;
- driver `continuous_first_hour=True`;
- driver `continuous_four_hour=True`;
- driver `four_hour_proof_mode=False`;
- driver `operational_persistent_mode=True`;
- lifecycle kwargs must carry `standard_four_hour_campaign=True` to the already-proven factory barrier.

Ordinary defaults remain unchanged.

### 5. Public command dispatch

Add `run_standard_four_hour_campaign()` as a narrow wrapper around `_run_operational_campaign(policy=STANDARD_FOUR_HOUR_POLICY, ...)`.

`main()` may remove the temporary standard-run blocker only when it dispatches the wrapper-bound, profile-validated standard mode to this function. Direct/unwrapped standard invocation continues to fail before any campaign action identity.

### 6. Terminal truth

Successful/blocked standard terminal payloads must report selected-policy truth, including `continuous_four_hour=True`, standard policy version and only 12h/24h locks. No terminal path may claim 4h was disabled for a standard run.

## Production Scope

Expected production files:

- `src/printer_v1/operator_cli/operational_memory_factory_command.py`
- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`

No schema or migration is planned.

## Minimum Sufficient TDD Proof

RED/GREEN coverage must prove:

1. standard preflight policy/ceilings/locks;
2. standard run requires validated external authorization and DB binding;
3. main standard mode dispatches only through wrapper-bound standard authority;
4. live owner remains production-persistent while enabling first-hour + standard 4h;
5. factory lifecycle kwargs contain `standard_four_hour_campaign=True` and never `four_hour_proof_mode=True`;
6. standard command/config/terminal policy version and `continuous_four_hour` are truthful;
7. ordinary run remains 15m-only;
8. historical selective-1h behavior remains unchanged;
9. 12h/24h and retrieval/financial locks remain unchanged.

After GREEN, independently prove the exact committed head. No live source/runtime or operator DB proof is part of this implementation slice.

## Money-Usefulness Contribution

This completes the actual authorized path to collect standard 4h memory, so the proven long-window factory can become operationally reachable without losing one-use authorization, persistent DB identity, Scheduler ownership, or fail-closed hard gates.

## What This Improves

- Public one-command continuity from authorization to 15m -> 1h -> 4h.
- Policy truth in durable configuration and terminal evidence.
- Standard authorization-to-authoritative-DB binding.
- Removal of the final intentional activation disconnect.

## What This Still Does Not Unlock

No real campaign until a later fresh operational rereadiness PASS and one-use authorization review. No 12h/24h, retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, wallet, signing, execution, or real funds.

## Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Control |
|---|---|
| Standard mode accidentally becomes proof mode | Keep persistent flag true and four-hour proof flag false |
| Generic selective boolean drops production authorization | Branch on standard policy identity before historical selective path |
| Public guard removed before complete wiring | TDD requires dispatch/config/owner/factory propagation before removal |
| Ordinary 15m behavior drifts | Default standard flag false + nearest ordinary regressions |
| 4h run claims wrong ceilings/locks | Standard preflight/config/terminal all derive from immutable policy |
