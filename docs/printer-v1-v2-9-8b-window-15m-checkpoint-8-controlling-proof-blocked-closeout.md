# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 Controlling-Proof Blocked Closeout

## Verdict

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_CONTROLLING_PROOF_BLOCKED_NO_RERUN`

Checkpoint 8 is **not complete**. The single authorized controlling disposable public-composition attempt was consumed and failed. No retry, rerun, resume, restart, or successor proof is authorized inside Checkpoint 8.

## Controlling attempt identity

- approved proof HEAD: `e263f5f3c6539b983314f7e66ea720ed4ec2e935`
- proof ID: `C8_CONTROLLING_E263F5F3_20260807`
- GitHub Actions run: `31180769946`
- job: `92873243015`
- artifact ID: `8994671067`
- artifact name: `checkpoint8-controlling-proof-e263f5f3`
- artifact ZIP SHA-256: `986b3a37cf72f40632012e2999629da241bd4561f82c8c2365a56db34b2d577c`
- sentinel SHA-256: `eb6e4ec7388a9f64d0892905b2ef1030f46e756cde617e18b71780583902469a`
- disposable DB SHA-256 after failure: `0eac46c4a7b0699699d95c87bc4b0cd1de4d0905351205c071c7e5eebfdff18d`
- terminal-summary SHA-256: `a7b15e9456243da6e33129ae6468cf359d56cbabc32c0923d49d59ed1a70157d`

The one-shot sentinel records `attempt_ordinal=1` and the exact approved proof HEAD, so the entitlement was consumed before the public campaign call as designed.

## Primary controlling-proof failure

The ordinary public campaign did not reach discovery/selection or lifecycle. It terminalized honestly as:

- `campaign_acceptance_verdict = HONEST_BLOCKED`
- `first_terminal_cause = SOURCE_AVAILABILITY_FAILURE`
- `activation_terminal_status = SOURCE_AVAILABILITY_FAILURE`
- `run_status = NOT_STARTED`
- `lifecycle_started = false`
- candidates observed: `0`
- candidates validated: `0`
- eligible candidates: `0`
- source operations used: `1`

The durable source failure is exact:

- source: `solana_rpc`
- request kind: `restored_pump_migration_signature_page`
- failure type: `direct_pump_rpc_malformed`
- failure message: `Solana RPC payload is not an object`

This proves the Checkpoint 8 deterministic Pump RPC success fixture was shaped incorrectly for the real ordinary direct-Pump migration path. The pre-proof fixture semantics test accepted a list response for `getSignaturesForAddress`, while the actual governed path expected the adopted Solana JSON-RPC object shape. This is a proof-fixture contract defect, not evidence that the production path should be weakened.

## Secondary harness failure

After the public campaign returned its honest terminal result, the controlling harness raised:

`CHECKPOINT8_TERMINAL_IDENTITY_MISSING`

The harness unit contract expected campaign/run identity directly in the public return dictionary, while the real terminal identity was available in the generated terminal summary/report. Because this happened after the one-shot public call, it is a secondary harness return-shape defect and does not restore the consumed proof entitlement.

`report_only()` did not run and the frozen controlling-proof summary was not produced. Therefore the independent inspector was correctly not run against this failed attempt.

## Safety and residue evidence

Read-only inspection of the disposable proof DB after failure shows:

- canonical migration ledger: 52 applied through `052_memory_observation_eligibility_layers.sql`
- `PRAGMA integrity_check = ok`
- foreign-key violations: `0`
- campaign rows: `1`, terminal failed
- campaign run rows: `1`, terminal failed
- campaign cycle rows: `1`, terminal failed
- supervision rows: `1`, terminal, cleanup completed
- lease released: true
- active discovery work: `0`
- campaign Scheduler work: `0`
- Scheduler jobs: `0`
- automatic retries: `0`
- restart created: false
- resume created: false
- successor created: false

Memory/downstream locks remained intact:

- memory windows: `0`
- episodes: `0`
- memory fingerprints: `0`
- retrieval queries/matches: `0`
- paper decisions: `0`
- paper positions: `0`
- paper trade events: `0`
- paper trade audits: `0`
- PnL unlock: none

No external-network tripwire exception occurred. Because the harness failed before frozen-summary creation, no final frozen network-attempt counter exists for this attempt; the failure evidence is instead the governed fixture-path malformed-response terminal above.

## Money-usefulness contribution

The failed proof is still useful evidence: it prevented Printer from accepting a synthetic fixture contract that did not match the real ordinary governed source path. The one-shot rule did its job by turning that mismatch into a durable blocker rather than allowing repeated attempts until a favorable result appeared.

## What this attempt improved

- proved the exact approved HEAD and one-shot sentinel boundary in a real execution;
- proved fail-closed Source Governor handling for malformed deterministic source evidence;
- proved honest pre-lifecycle terminalization, cleanup, lease release, and zero downstream leakage;
- exposed two concrete pre-proof verification gaps: real Pump JSON-RPC response shape and real public terminal-return identity shape.

## Still locked

Nothing beyond Checkpoint 8 is unlocked. In particular, no retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, audits, PnL, longer windows, live wallet, private keys, real funds, or live execution is authorized.

`WINDOW_5M_MICRO_EVENT` remains support-only.

## Correct next step

Do **not** rerun the controlling proof.

The next lawful work is a new audit/readiness review of the two exposed defects:

1. trace the real `restored_pump_migration_signature_page` request/normalizer contract and compare it with the Checkpoint 8 deterministic fixture response;
2. trace the real `run_operational_campaign()` terminal return contract and compare it with the controlling harness identity extraction.

That follow-up is audit-only until a separate design/repair/proof decision is approved. Any future proof attempt requires an explicit new authorization outside this consumed Checkpoint 8 attempt.

## Functionality Risks / Setbacks / Efficiency Blockers

- Checkpoint 8 cannot close PASS from this attempt because no clean `WINDOW_15M` lifecycle or memory was produced.
- The independent inspector cannot validate a successful frozen proof because the harness never reached freeze/replay.
- Repairing either defect and silently rerunning would violate the one-shot proof law.
- The evidence artifact is retained by GitHub Actions and should remain the controlling failure artifact for this attempt.

## Stop condition

Stop Checkpoint 8 here as blocked. Preserve the artifact and this closeout. Do not perform another controlling proof until a separately approved audit/design/repair path explicitly authorizes a new attempt.
