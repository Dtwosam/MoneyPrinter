# Printer V1 V2-9.8B Post-DTW100 Standard Four-Hour Activation Final Public Wiring Audit

## Verdict

`V2_9_8B_POST_DTW100_STANDARD_FOUR_HOUR_ACTIVATION_FINAL_PUBLIC_WIRING_BLOCKED_IMPLEMENTATION_REQUIRED`

Audit baseline: `7308b477593771c7f8b9f4a4281e3d279fabc901`.

Slices A, B and C are independently proven, but the public standard-four-hour one-shot path is still intentionally disconnected. No real run or authorization is permitted yet.

## Read-Only Findings

1. `standard-four-hour-run` is registered and wrapper-bound, and the standard authorization profile is validated, but `main()` still raises the temporary activation blocker before running a campaign.
2. `_run_operational_campaign()` routes every policy with `selective_1h_continuation=True` through the historical selective-1h preflight. Standard 4h therefore does not yet have its own policy-shaped preflight.
3. The same condition drops `validated_authorization_runtime_facts()` for standard 4h, so the standard one-use authorization would not reach the authoritative database-target binding owner.
4. `_create_campaign_command()` still persists the ordinary policy version and `continuous_four_hour=False` even when the selected policy is `STANDARD_FOUR_HOUR_POLICY`.
5. The live owner is still invoked with `fifteen_minute_only=True`. That correctly preserves production-persistent mode, but the owner currently translates it to `continuous_first_hour=False` and `continuous_four_hour=False`; the standard factory authority cannot be reached.
6. Lifecycle kwargs do not currently carry `standard_four_hour_campaign=True` into the factory.
7. The terminal summary still reports `continuous_four_hour=False` unconditionally.
8. The dedicated standard one-shot wrapper is otherwise present and exact: distinct schema/profile, `standard-four-hour-run`, one invocation, no retry/rerun/resume/restart/successor, 230/210 outer lifecycle ceilings, and only 12h/24h locked.

## Money-Usefulness Contribution

This audit prevents a false activation claim. The 4h factory/barrier can now make useful clean long-memory continuations, but the money-useful product path is incomplete until the public authorized coordinator carries the same policy, authorization, budget, and terminal truth end to end.

## What This Improves

- Identifies the exact remaining disconnect after Slice C.
- Prevents bypassing the temporary public guard without fixing the underlying policy propagation.
- Preserves the hardened one-use authorization and authoritative DB binding as mandatory runtime owners.

## What This Still Does Not Unlock

No source call, operator DB mutation, real standard-4h run, fresh authorization, 12h/24h, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.

## Proof Needed Before Completion

A narrow TDD implementation must prove:

- standard preflight reports standard policy/ceilings and only 12h/24h locks;
- validated standard authorization runtime facts reach DB-target validation;
- public `standard-four-hour-run` calls the canonical persistent campaign owner exactly once;
- production-persistent mode remains true while first-hour and standard-four-hour continuation are enabled;
- the factory receives `standard_four_hour_campaign=True` and never receives `four_hour_proof_mode=True`;
- ordinary 15m and historical selective-1h paths remain unchanged;
- terminal output truthfully reports standard 4h policy;
- direct/unwrapped standard run remains fail-closed;
- no 12h/24h or financial capability is unlocked.

## Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Control |
|---|---|
| Removing only the public blocker creates a fake activation | Require end-to-end policy/authorization propagation before removing it |
| Setting `fifteen_minute_only=False` accidentally re-enters proof authority | Keep production-persistent mode and add explicit standard campaign authority instead |
| Standard mode loses one-use DB binding because it also uses selective 1h | Route authorization by policy identity, not the generic selective boolean |
| Persisted configuration/report says 15m-only while runtime executes 4h | Derive policy version/continuous-4h/locks from the selected immutable policy |
| Broad owner refactor risks regressions | Add one narrow explicit standard flag; preserve ordinary defaults |

## Next Lane

Design and implement the final public standard-four-hour wiring slice, then independently prove its exact committed head. Operational rereadiness remains mandatory afterward.
