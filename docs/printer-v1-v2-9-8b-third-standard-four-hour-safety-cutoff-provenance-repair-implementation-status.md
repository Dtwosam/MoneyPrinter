# Printer V1 V2-9.8B — Third Standard Four-Hour Safety Cutoff / Provenance Repair Implementation Status

## Verdict

`V2_9_8B_THIRD_STANDARD_FOUR_HOUR_SAFETY_CUTOFF_PROVENANCE_REPAIR_IMPLEMENTED_PROOF_BLOCKED_TOOLING`

This is **not** an implementation closeout PASS. Production code and the focused regression test are committed, but the canonical repository test command has not yet executed because GitHub Actions is blocked before runner startup by an account billing lock.

## Baseline and branch

- repair-scope audit: `d1f57145ca719223502d6521cb4881532530e1b8`
- design: `19adeed4bf175331dd19bee31a1056bd396db80d`
- implementation plan: `214adee3afc34d6df15cbcf21bfbafa373d90b66`
- implementation branch: `agent/v2-9-8b-third-standard-4h-safety-cutoff-provenance-repair-implementation`
- production repair commit: `0aef38c89320f9ca7a265bda5a8a5503a8c52484`
- temporary-workflow cleanup commit: `7ee27b92860ef23e99bf75ea411f4a7bd6433f75`

## Implemented repair

Only `src/printer_v1/operator_cli/campaign_authority_adapters.py` changed in production.

The memory-window B.2 path now keeps two distinct authorities:

1. `lifecycle_deadline` remains the authoritative `WINDOW_1H.window_end_at` fixed at 15m close + 2700 seconds. The caller must still supply this exact value.
2. `evidence_cutoff` is the `captured_at` timestamp of the exact `snapshot_end_id` already owned by that memory window.

The adapter additionally:

- loads the exact closing snapshot;
- validates its token/pair identity;
- fails closed if the closing snapshot is missing or unparseable;
- fails closed if the observed close precedes the fixed lifecycle deadline;
- keeps the existing 1800-second freshness maximum;
- keeps exact composite snapshot linkage, mint/pair/target checks, source trace checks, source-response/request linkage, failure-source linkage, source status, data quality, and rejection checks unchanged;
- reports `evidence_cutoff_source = EXACT_CLOSING_SNAPSHOT` for this path;
- leaves checkpoint B.2 logic untouched;
- introduces no Scheduler, Source Governor, request-budget, schema, migration, provider, or authorization change.

## Focused regression test added

`tests/test_v2_9_8b_third_standard_four_hour_safety_cutoff_provenance_repair.py`

It covers:

- real-shaped fixed deadline `T`, closing snapshot `T+5s`, fresh evidence `T+4s`;
- caller cutoff mismatch;
- evidence/trace after exact closing snapshot;
- evidence older than 1800 seconds;
- wrong exact closing-snapshot token identity;
- source response/request mismatch.

## Verification evidence available now

### RED semantic reconstruction

Using the exact pre-repair cutoff arithmetic with lifecycle end `15:41:15` and fresh evidence at `15:41:19` produced:

- composite age: `-4.0s`
- trace age: `-4.0s`

This reproduces the third-attempt false post-cutoff rejection.

### GREEN isolated SQLite adapter-slice proof

A local source-exact reconstruction of the changed B.2 memory-window slice, using the same SQL ownership shape as the committed focused test, produced:

- real-shaped `T+5s` close: accepted, no reasons;
- caller cutoff mismatch: raised fail-closed;
- post-close evidence: blocked with stale/post-cutoff + trace mismatch;
- >1800s stale evidence: blocked with stale + trace mismatch;
- wrong closing-snapshot identity: blocked;
- response/request mismatch: blocked.

This is useful semantic evidence, but it is not substituted for executing the committed repository tests.

## Tooling blocker

Temporary GitHub Actions run `31514365590` did not execute any runner step. GitHub annotated it:

`The job was not started because your account is locked due to a billing issue.`

The temporary workflow was removed. No temporary workflow remains in the implementation diff.

## Exact remaining proof

Run on the implementation branch:

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p 'test_v2_9_8b_third_standard_four_hour_safety_cutoff_provenance_repair.py' -v
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p 'test_v2_9_8b_first_hour_safety_provenance_repair.py' -v
```

If both are GREEN, perform a minimal diff/compile review and write the implementation closeout PASS. Do not widen into a broad regression suite unless these focused tests expose coupling.

## Money-usefulness contribution

The repair removes a deterministic false safety block that can waste a one-use standard-four-hour authorization after valid 15m and 1h learning, while preserving protection against stale, future, mismatched, or untraceable evidence.

## What remains locked

No fresh operational rereadiness, authorization, standard-four-hour attempt, 12h/24h, retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, paper-trade audits, PnL, wallet/private keys/signing/real funds/live execution, paid APIs, scoring/ranking/confidence/weighted logic, embeddings, or vectors is unlocked by this status.

## Functionality Risks / Setbacks / Efficiency Blockers

- GitHub-hosted proof is unavailable until the account-level Actions billing lock is resolved.
- The isolated SQLite proof is not a substitute for the committed repository tests.
- No new authorization may be created merely because the implementation exists.

## Next allowed step

Only the exact focused repository proof above, followed by implementation closeout if GREEN.