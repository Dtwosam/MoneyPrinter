# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — DTW-67 Final Independent Readiness Review

Date: 2026-08-08

Linear: `DTW-67`

Implementation baseline:

`274988b9350d15921914ebfcde7989c49dfa5096`

## Verdict

`DTW67_INDEPENDENT_READINESS_PASS_FRESH_ONE_SHOT_C8_AUTHORIZATION_MAY_BE_REQUESTED`

The independent-inspector repair sequence is now ready for a fresh bounded Checkpoint 8 authorization request.

This review does **not** authorize or execute a proof. The previous one-shot authorization remains consumed. A new proof may run only after the operator explicitly authorizes exactly one fresh bounded Checkpoint 8 controlling proof.

## Evidence reviewed

### Structural reconstruction

DTW-55/56 findings and design are satisfied by the committed durable path:

- campaign-run and factory-run identities remain separate;
- factory run resolves only through the exact campaign-run `authoritative_run_id` bridge;
- campaign-owned WINDOW_15M rows own the memory graph;
- truthful PARTIAL_MEMORY window-layer rows are separated from CLEAN_MEMORY episode/fingerprint evidence;
- fingerprints are joined by `episode_id` and validated by payload identity, not synthetic SHA columns;
- factory-run steps are corroborative and queried only with the resolved factory UUID;
- campaign Scheduler-work joins exactly to Scheduler jobs without owner-name heuristics;
- governed source accounting is reconstructed from canonical identity sets plus persisted source request/response links;
- terminal report hash and artifact bytes are independently verified.

### Canonical terminal identity

PASS.

Durable reconstruction requires canonical terminal:

`report_json.full_run_terminal_evidence.identity`

with non-empty campaign, campaign-run, configuration, cycle, factory-run, supervision, and execution identities.

Missing identity fails closed. Present-but-wrong reconstructed fields fail mismatch. Outer report identity is supplemental parity only and cannot backfill the canonical carrier. Terminal execution identity is taken from the canonical nested report identity and is not replay-backfilled.

### Canonical REPORT_ONLY request identity

PASS.

When `reconstructed_identity` is supplied, durable validation now requires:

`report_only.requested_identity`

with non-empty exact:

- `campaign_id`;
- public campaign `run_id`.

It also requires:

- `status=REPLAYED`;
- `mode=REPORT_ONLY`.

Missing canonical carrier/field fails `REPORT_REPLAY_REQUESTED_IDENTITY_MISSING`. Present-but-wrong campaign/run/status/mode fails `REPORT_REPLAY_IDENTITY_MISMATCH`.

The old top-level replay campaign/run fallback remains only when `reconstructed_identity is None`, preserving direct-helper compatibility without becoming an end-to-end acceptance path.

### Canonical replay full-run identity

PASS.

Durable validation requires replay:

`full_run_terminal_evidence.identity`

with non-empty exact campaign, campaign-run, configuration, cycle, factory-run, supervision, and execution identities. Missing values fail closed and mismatches fail at the replay identity boundary.

### Replay proof/fixture identity

PASS.

Durable validation requires:

`full_run_terminal_evidence.authorization_and_invocation.proof_expectation`

with non-empty exact:

- `proof_id`;
- `fixture_composition_manifest_sha256`.

Missing values fail closed. Wrong proof/manifest identity preserves the existing manifest mismatch boundary.

### End-to-end durable wiring

PASS.

`inspect_checkpoint8_frozen_proof_directory` derives the durable DB projection first and passes:

`reconstructed_identity=projections.get("identity")`

to report/replay identity validation.

Therefore legacy direct-validator fallbacks are not reachable as substitutes in the real frozen-proof acceptance path.

### Memory, Scheduler, source accounting, cleanup, and frozen safety

PASS for the approved successful-C8 shape.

The current path still requires:

- exactly two terminal campaign-owned WINDOW_15M lifecycles;
- exactly two distinct selected mints;
- exact memory-window -> clean episode -> fingerprint chains;
- exactly 18 factory steps;
- exact 28-row campaign Scheduler-work composition with joined terminal/unlocked Scheduler jobs;
- exact lifecycle factory UUID correspondence;
- exact discovery Scheduler correspondence;
- non-vacuous governed source-accounting identity equality;
- persisted request/response/source-link integrity;
- one terminal supervision row with completed cleanup and released lease;
- zero active/locked current work;
- no retry/rerun/resume/restart/successor allowance;
- campaign and acceptance PASS;
- zero network attempts;
- non-zero fixture transport operations;
- zero-work REPORT_ONLY replay;
- zero protected-capability deltas;
- zero WINDOW_1H/WINDOW_4H/WINDOW_12H/WINDOW_24H counts;
- canonical migration ledger, SQLite integrity/FK PASS, and read-only DB byte stability.

Legacy graph/governance validator fallbacks remain only compatibility behavior for isolated direct tests. The durable DB reconstruction supplies the canonical `fingerprint_present`, `source_accounting_exact`, and `scheduler_correspondence_exact` fields before those validators are called, so legacy synthetic fingerprint/owner representations cannot satisfy the real end-to-end reconstruction.

## Verification evidence

### DTW-57 durable reconstruction RED

- accepted RED head: `3c6217bdd9f2abcd2f06eb7cffb80efd7ec91100`;
- run `31236371982`;
- job `93049497860`;
- 11 behavioral failures, no setup/SQLite integrity errors.

### DTW-58 durable reconstruction GREEN

- commit `7f6bcbd574257ba19ec20a0c35217685a2ffce91`;
- run `31237237210`;
- job `93051907381`;
- `23 passed in 16.80s`;
- consumed DTW-54 artifact passed repaired inspector read-only.

### DTW-61 required-identity-presence RED

- accepted RED head `e2121a495ec757897caeda5570e7b6697b591385`;
- run `31237928211`;
- job `93053856735`;
- `19 failed, 2 passed in 24.90s`;
- no setup/collection/SyntaxError/SQLite integrity errors.

### DTW-62 required-identity-presence GREEN

- commit `092a738c2226766aac078036f79ab7d9a901a58e`;
- run `31238096105`;
- job `93054290080`;
- `44 passed in 29.19s`;
- consumed DTW-54 artifact passed repaired inspector read-only.

### DTW-65 canonical requested-identity RED

- accepted RED head `2884a59ad54e2eb391e190da8cf03bff112078b1`;
- run `31238425975`;
- job `93055135265`;
- `5 failed, 3 passed in 6.03s`;
- no setup/collection/SyntaxError/SQLite integrity errors.

### DTW-66 canonical requested-identity GREEN

- commit `274988b9350d15921914ebfcde7989c49dfa5096`;
- run `31238544304`;
- job `93055437697`;
- `52 passed in 39.88s`;
- implementation delta exactly one inspector script;
- consumed DTW-54 artifact `9014056017` returned `CHECKPOINT8_INDEPENDENT_INSPECTION_PASS` read-only;
- post-verification scope recheck PASS.

The consumed historical artifact remains validation evidence only. Its read-only PASS does not retroactively close Checkpoint 8 and is not a substitute for a fresh controlling proof.

## Money-usefulness contribution

The repaired inspector can now independently prove that clean memory, Scheduler/source accounting, terminal report, replay, and proof fixture all belong to the same bounded campaign/run identity. That makes the later memory evidence materially more trustworthy for future paper-only comparison while preserving the rule that no decision can rely on dirty or ambiguously identified memory.

## What this lane improves

DTW-67 completes independent readiness for the Checkpoint 8 inspector after repairing all known structural and fail-open identity gaps found by DTW-55, DTW-59, and DTW-63.

## What this lane still does not unlock

This readiness PASS does not unlock:

- Checkpoint 8 itself;
- a proof without fresh operator authorization;
- automatic WINDOW_15M activation;
- WINDOW_1H or longer windows;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions;
- trade events;
- paper trade audits;
- PnL;
- wallet/private-key/real-fund/live execution.

## Next proof/test needed

The next lawful step is **not** implementation. It is an operator decision whether to authorize exactly one fresh bounded Checkpoint 8 controlling proof against a frozen immutable approved head derived from this readiness state.

If authorized, the proof lane must:

1. freeze the exact approved immutable proof head;
2. allow exactly one fresh controlling C8 attempt;
3. preserve the disposable DB/fixture/no-network boundary;
4. run the controlling campaign once;
5. run the repaired independent inspection against the newly frozen proof evidence;
6. forbid retry/restart/resume/successor/rerun under the same authorization;
7. close out the result before any downstream capability decision.

A campaign PASS without independent-inspection PASS is not Checkpoint 8 PASS.

## Functionality Risks / Setbacks / Efficiency Blockers

- Historical artifact success must not be mistaken for fresh proof closure.
- The next authorization must be one-shot and explicit; the consumed DTW-54 authorization cannot be reused.
- Do not widen the next proof into WINDOW_1H+, retrieval, decisions, positions, trades, or PnL.
- Do not alter campaign/runtime/source/memory behavior merely to make the inspector pass.
- If the next fresh proof exposes a new independent discrepancy, stop at the discrepancy and return to the audit/design/implementation/proof/closeout pattern rather than retrying.

## Stop condition

DTW-67 stops at independent readiness PASS.

A fresh one-shot Checkpoint 8 authorization **may now be requested from the operator**. No proof is authorized or executed by this document.
