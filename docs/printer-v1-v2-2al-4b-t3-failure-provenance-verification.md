# Printer V1 V2-2AL.4B T3 Failure-Provenance Verification

Status: VERIFICATION ONLY
Lane: V2-2AL.4B - Independent T3 Failure-Provenance Verification
Executor/model: Codex, standard/balanced mode
Anchor: `af78265 Add V2-2AL.4 T3 retry readiness review`
Resolved target commit: `11c6cf1 Repair V2-2AL T3 failure provenance`
Verdict: `VERIFICATION_PARTIAL_WITH_BLOCKER`

V2-3, V2-4, runtime/scheduler, memory generation, retrieval, paper decisions,
BUY/SELL/HOLD, positions, trades, audits, and PnL remain paused.

This verification did not run live RPC, discovery, source fetching, runtime,
scheduler, memory generation, retrieval, paper decisions, or paper-trading
work. It did not change code, tests, migrations, or persistent DB rows. It used
one isolated temporary DB fixture check to verify the governed failure path.

The staged/native 15m blocker remains `PARTIAL - DEFERRED, NOT RESOLVED`.
A3 remains locked. V2-3 remains paused.

## Source Stack Read

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-v2-2al-4-t3-page-cap-provenance-readiness-review.md`
- `docs/printer-v1-v2-2al-4a-t3-failure-provenance-repair.md`

## Commit Resolution

Git history for:

- `src/printer_v1/sources/solana_rpc_token_age.py`
- `tests/test_v2_2ak_t3_solana_rpc_token_age.py`
- `docs/printer-v1-v2-2al-4a-t3-failure-provenance-repair.md`

resolved the V2-2AL.4A implementation commit to:

`11c6cf1 Repair V2-2AL T3 failure provenance`

Commit scope:

- added `docs/printer-v1-v2-2al-4a-t3-failure-provenance-repair.md`
- modified `src/printer_v1/sources/solana_rpc_token_age.py`
- modified `tests/test_v2_2ak_t3_solana_rpc_token_age.py`

No unrelated production file was included in the resolved commit scope.

## Files Inspected

- `src/printer_v1/sources/solana_rpc_token_age.py`
- `src/printer_v1/sources/governed_execution.py`
- `src/printer_v1/sources/recording.py`
- `src/printer_v1/sources/contracts.py`
- `migrations/001_database_foundation.sql`
- `tests/test_v2_2ak_t3_solana_rpc_token_age.py`

## Eight-Field Normalization Verification

Result: `PASS_AT_NORMALIZER_LEVEL`

The repair adds `_T3_FAIL_PROVENANCE_FIELDS` with exactly these eight fields:

- `t3_requested_mint`
- `t3_rpc_host_redacted`
- `t3_rpc_methods_attempted`
- `t3_request_ids`
- `t3_pages_fetched`
- `t3_tx_calls_attempted`
- `t3_block_time_calls_attempted`
- `t3_failure_stage`

Static inspection and focused tests confirm `_extract_failure_provenance()`
copies only those eight fields from failure payloads into
`NormalizedSourceResult.normalized_payload` when they are present.

Bare legacy failure payloads still normalize safely with an empty normalized
payload.

## Actual-Call Accuracy Verification

Result: `PASS_AT_FIXTURE_AND_STATIC_LEVEL`

The V2-2AL.4A tests cover:

- account-validation failure with only `getAccountInfo`
- page-cap exhaustion with three signature pages
- transaction-inspection failure with attempted transaction calls
- block-time fallback failure with one `getBlockTime` call
- budget-exhaustion fixture with method count matching request-ID count

Static inspection confirms the live pipeline tracks:

- `request_ids`
- `methods_attempted`
- `pages_fetched`
- `tx_calls`
- `block_time_calls`

The counters remain bounded by the existing caps:

- `_T3_MAX_REQUESTS_PER_TOKEN = 8`
- `_T3_MAX_SIGNATURE_PAGES = 3`
- `_T3_MAX_TRANSACTION_CALLS = 3`
- `_T3_MAX_BLOCK_TIME_CALLS = 1`
- `_T3_RPC_TIMEOUT_SECONDS = 10.0`

No retry loop, page-cap increase, endpoint rotation, or paid/archive dependency
was added by this repair.

## Redaction Verification

Result: `PASS`

The existing `redacted_rpc_host()` helper returns hostname only. Focused tests
verify a URL with path and query string such as
`https://api.mainnet-beta.solana.com/v1?apikey=secret` produces:

`api.mainnet-beta.solana.com`

The failure provenance field `t3_rpc_host_redacted` is therefore safe to carry
as host-only audit context, with no scheme, path, query string, API key,
credential, or token.

## Fail-Closed / A3 Verification

Result: `PASS`

Failure provenance remains fail-closed:

- no `token_created_at`
- no `token_age_seconds`
- no `token_age_evidence_tier`
- no `t3_accepted_signature`
- no `t3_accepted_slot`
- no accepted block-time success field used as evidence
- no `t3_instruction_type`
- no `t3_token_program`
- no derived token creation or derived age success field

Focused tests confirm failure provenance does not unlock A3. A3 remains gated on
real `token_age_seconds`, and failure provenance does not provide it.

## Governed Persistence Verification

Result: `BLOCKER`

An isolated temporary DB fixture check was run through
`execute_source_request_with_governor()` using:

- `build_solana_rpc_token_age_adapter(enabled=True, fixture_transport=...)`
- `fixture_t3_failure_transport(..., failure_provenance=...)`
- source: `solana_rpc`
- request kind: `mint_creation_time_reference`
- no live RPC
- no persistent DB mutation

The governed execution result preserved all eight fields in:

`GovernedSourceExecutionResult.normalized_result.normalized_payload`

However, the persisted `printer_source_failures` row did not preserve those
fields. The table schema from `migrations/001_database_foundation.sql` contains:

- `id`
- `source_name`
- `request_kind`
- `failed_at`
- `failure_type`
- `failure_message`
- `source_status`
- `data_quality_label`
- `retry_after_at`
- `created_at`

There is no `normalized_payload_json`, `failure_payload_json`, or equivalent
provenance column. `record_source_failure()` also accepts and writes only
failure type/message, status, quality, timestamps, and retry metadata.

Therefore the repair satisfies direct normalizer output but does not yet satisfy
the requirement that failure provenance survive the governed failure/audit
persistence path.

## Backward Compatibility Verification

Result: `PASS`

- Bare legacy failure payloads still normalize with no T3 failure provenance.
- Success-path T3 evidence remains unchanged and still carries the original 15
  success provenance fields.
- T2 tests pass.
- `OBSERVED_LIVE_LAUNCH` tests pass.

## Success-Path Regression Verification

Result: `PASS`

The success path still produces:

- `token_created_at`
- `token_age_seconds`
- `token_age_evidence_tier = "T3"`
- all 15 success-path `t3_*` provenance fields

The failure-provenance repair did not modify the T3 success acceptance contract.

## Tests / Checks Run

- `python -m pytest tests/test_v2_2ak_t3_solana_rpc_token_age.py -q`
  - Result: `132 passed`
  - Warning: pytest cache warning / artifacts cleanup warning only
- `python -m pytest tests/test_v2_2x2_t2_token_age_evidence.py tests/test_v2_2ag_observed_live_launch_tier.py -q`
  - Result: `112 passed`
  - Warning: pytest cache warning only
- isolated temporary DB fixture check for governed failure persistence
- `git diff --check`
- `git status --short`
- `git diff --stat`
- `git diff --name-only`

## Safety Confirmations

- No live RPC was run.
- No discovery or source fetching was run.
- No persistent DB was mutated.
- No code, tests, or migrations were changed in this verification lane.
- No page-cap change was made.
- No endpoint rotation was added.
- No paid/archive RPC dependency was added.
- No A3 work was done.
- No memory, retrieval, paper decision, BUY/SELL/HOLD, position, trade, audit,
  or PnL path was touched.
- No wallet, private key, signing, live execution, scoring, ranking,
  confidence, weighted logic, embedding, or vector path was added.

## Remaining Blocker

The remaining blocker is persistence, not normalization.

The eight failure-provenance fields survive direct normalization and the
governed execution result, but they do not persist into the governed
`printer_source_failures` audit row. AL.5 should not run until that persistence
gap is repaired or explicitly waived by the operator.

## Verdict

`VERIFICATION_PARTIAL_WITH_BLOCKER`

V2-2AL.4A repaired the normalizer-level T3 failure provenance and preserved
fail-closed behavior. It did not fully satisfy the persistence-path requirement.

## Exact Next Lane

`V2-2AL.4C - T3 Failure-Provenance Persistence Repair`

After that repair is implemented and independently verified, the approved AL.5
mint remains:

`6LsqJCJ1p98UG3HYx1UuPgqNjTzAcYFdw4nSzfPzpump`

No live retry was performed in this lane.
