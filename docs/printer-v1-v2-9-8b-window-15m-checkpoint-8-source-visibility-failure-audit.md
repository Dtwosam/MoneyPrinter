# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — Source-Visibility Failure Audit

Date: 2026-08-07

## Scope

Audit only the single consumed re-proof `C8_REPROOF_AFTER_FIXTURE_ORDER_REPAIR_20260807` from GitHub Actions run `31190804691` and frozen artifact `checkpoint8-next-reproof-75cfb759` (artifact `8998719684`, SHA-256 `317ececd4140040b7232ee2f280ee6e30250989b026ff239133cf33608e483f3`). No rerun, provider execution, production mutation, or downstream capability unlock is authorized by this audit.

## Controlling result

The authorization at `75cfb7595023cd765e8f5f7c5901d00147125344` is consumed.

The harness completed evidence freezing with process exit `0`, but the campaign did **not** pass:

- `campaign_pass = false`
- `campaign_acceptance_verdict = HONEST_BLOCKED`
- `activation_terminal_status = SOURCE_VISIBILITY_SHORTAGE`
- `lifecycle_started = false`
- `network_attempt_count = 0`
- replay was zero-work
- DB integrity `ok`; foreign-key violations `0`
- protected retrieval/decision/position/trade tables remained zero
- `WINDOW_1H/4H/12H/24H` remained zero

The independent inspector then exited `1` with `CURRENT_RUN_IDENTITY_MISSING`. That is a secondary orchestration symptom of running the closeout inspector after a pre-lifecycle honest block; it is not the primary discovery failure.

## Frozen evidence facts

The disposable proof DB contains exactly five governed source requests and five clean responses, with zero source failures:

1. finalized Pump migration signature page — 2 signatures;
2. migration transaction for candidate A — clean exact mint/migration evidence;
3. migration transaction for candidate B — clean exact mint/migration evidence;
4. PumpSwap signature/pool resolution for candidate A — confirmed;
5. PumpSwap signature/pool resolution for candidate B — confirmed.

Despite those successful source responses, the graduated-candidate registry, eligible reserve, discovery-candidate tables, and selection tables remained empty. No DexScreener market request ran. The exhaustion certificate therefore reported zero unique observed tokens and `SOURCE_VISIBILITY_SHORTAGE`.

## Root cause

The defect is in the Checkpoint 8 PumpSwap **proof fixture accounting contract**, not production discovery.

`_checkpoint8_pumpswap_confirmation()` declares:

- `transport_operations_used = 1`
- `response_bytes = 512`
- `normalized_rows = 1`

but declares no `transport_operation_identities`.

The canonical direct-migration owner calls `record_payload_transports()` for each PumpSwap verification response. The measured-transport contract requires declared transport-operation counts to be backed by concrete transport identities. A payload that claims transport operations while carrying no identities fails closed as `TRANSPORT_IDENTITIES_MISSING`.

`run_direct_migration_discovery()` catches that measured-transport failure, sets its accounting block reason, and later clears `pending_persist` before `record_graduated_candidate()`. This exactly explains the frozen state:

- five governed request/response rows exist;
- only the three direct-Solana migration operations entered six-unit transport identity accounting;
- both PumpSwap confirmations were source-clean but accounting-ineligible;
- zero confirmed candidates were persisted;
- no market-resolution round could start.

Production `build_graduation_verifier_transport()` already emits measured identities for its real read-only sequence (`getTransaction` plus the required `getMultipleAccounts` batch). Production discovery therefore does not need modification.

## Secondary proof-fidelity finding

The C8 synthetic migration timestamps are fixed around Unix epoch `1_800_000_000`, which is January 2027 and therefore later than this August 2026 proof. The production graduation verifier rejects migration block times more than 300 seconds in the future. The C8 custom success fixture bypasses that production verifier check.

This timestamp did not cause the consumed failure because persistence was already blocked by missing transport identities, but leaving future-dated success evidence would weaken the next proof. The fixture should use a fixed valid past graduation time or otherwise prove the production future-time invariant without changing production code.

## Independent-inspector gating finding

The harness intentionally freezes honest blocked evidence and returns process code `0`. Therefore a disposable CI runner must not treat harness exit `0` alone as proof success. Before invoking the independent success inspector, a future runner must read the frozen summary and require both:

- `campaign_pass == true`
- `campaign_acceptance_verdict == CAMPAIGN_PASS`

If either is false, the runner should preserve/upload the frozen evidence and stop without invoking the success inspector. This is runner orchestration, not a production capability change.

## Audit verdict

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_SOURCE_VISIBILITY_FAILURE_AUDIT_COMPLETE_PROOF_FIXTURE_REPAIR_REQUIRED`

## Money-usefulness contribution

Restoring exact proof-fixture accounting allows Checkpoint 8 to test the real governed discovery-to-memory path instead of falsely losing two otherwise confirmed candidates before selection. It improves confidence that later paper-only money-useful behavior is based on correctly accounted source evidence.

## Still not unlocked

This audit unlocks no new proof attempt and no `WINDOW_1H+`, retrieval, paper decision, BUY/SELL/HOLD, position, trade, audit, or PnL capability.

## Minimum proof before repair completion

- PumpSwap fixture payload carries production-shaped measured transport identities.
- Direct-migration offline regression proves two source-clean confirmations can pass the pre-persist accounting gate and reach the graduated registry.
- C8 real-consumer/focused tests remain green with zero network attempts.
- Fixture migration times satisfy the production future-time rule.
- No production discovery file changes.

## Functionality Risks / Setbacks / Efficiency Blockers

- Missing transport identities caused a false source-visibility shortage despite clean provider responses.
- Future-dated synthetic migration evidence is a latent proof-fidelity defect.
- Harness exit `0` means evidence freeze completed, not necessarily `CAMPAIGN_PASS`; runner gating must distinguish those states.
- The consumed authorization cannot be reused. Any later controlling re-proof requires a fresh explicit operator authorization after repair closeout/readiness review.
