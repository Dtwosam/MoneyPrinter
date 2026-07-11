# Printer V1 V2-2AL.3 Bounded Live T3 Proof Retry

Status: BOUNDED LIVE PROOF RETRY
Lane: V2-2AL.3 - Bounded Live T3 Proof Retry
Executor/model: Codex, standard/balanced mode
Anchor: `5a4309e Add V2-2AL.2 Token-2022 layout verification`
Verdict: `LIVE_T3_RETRY_FAIL`

V2-3, V2-4, runtime/scheduler, memory generation, retrieval, paper decisions,
BUY/SELL/HOLD, positions, trades, audits, and PnL remain paused.

This lane performed exactly one operator-approved, bounded, read-only Solana RPC
retry through the existing Source Governor boundary against an isolated proof DB
only. It did not change code, change tests, run discovery, activate runtime,
create memory, activate retrieval, create paper decisions, unlock A3, unlock
V2-3, or touch any paper-trading or financial path.

The staged/native 15m blocker remains `PARTIAL - DEFERRED, NOT RESOLVED`.

## Source Stack Read

- `AGENTS.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-v2-2al-bounded-live-t3-token-age-proof.md`
- `docs/printer-v1-v2-2al-1-token-2022-extension-layout-repair.md`
- `docs/printer-v1-v2-2al-2-token-2022-layout-repair-verification.md`

## Proof Setup

| Item | Result |
| --- | --- |
| Approved mint | `pumpgrWRAztPTe9HpqUUj23hWDcz1qvkbMRiDM6wint` |
| Mint selection | Reused the previously approved V2-2AL mint; no discovery/search was run |
| Endpoint type | Public/free read-only Solana RPC |
| RPC host shown | `api.mainnet-beta.solana.com` |
| Source path | Existing Source Governor execution path with explicit live transport injection |
| Proof DB | `data/printer_v1_v2_2al3_t3_live_retry.sqlite3` |
| Persistent DB | `data/printer_v1.sqlite3` |
| Started at | `2026-07-11T23:00:59.327407+00:00` |
| Ended at | `2026-07-11T23:01:03.174402+00:00` |

The proof DB was copied from the persistent DB before the retry. The copied proof
DB hash matched the persistent DB hash before the live call, and migrations were
applied only to the proof DB copy.

## Persistent DB No-Change Proof

| Item | Value |
| --- | --- |
| Persistent DB hash before | `97db9a15cc464d86137cbbb0dd0a4ef1880e9f4e231fb41e8b22ca09fb177fbb` |
| Persistent DB hash after | `97db9a15cc464d86137cbbb0dd0a4ef1880e9f4e231fb41e8b22ca09fb177fbb` |
| Persistent DB unchanged | Yes |
| PnL tables detected | None |

Persistent row counts stayed unchanged:

| Table | Before | After | Delta |
| --- | ---: | ---: | ---: |
| `printer_source_requests` | 1118 | 1118 | 0 |
| `printer_source_responses` | 1071 | 1071 | 0 |
| `printer_source_failures` | 47 | 47 | 0 |
| `printer_token_snapshots` | 1012 | 1012 | 0 |
| `printer_memory_windows` | 156 | 156 | 0 |
| `printer_memory_retrieval_queries` | 10 | 10 | 0 |
| `printer_memory_retrieval_matches` | 0 | 0 | 0 |
| `printer_paper_decisions` | 2 | 2 | 0 |
| `printer_paper_positions` | 0 | 0 | 0 |
| `printer_paper_trade_events` | 0 | 0 | 0 |
| `printer_paper_trade_audits` | 0 | 0 | 0 |

## Live Retry Limits

The retry used the existing V2-2AK/V2-2AL T3 adapter limits:

- Source Governor path only.
- Explicit live transport injection.
- One mint only.
- One proof attempt only.
- Max 8 RPC operations.
- Max 3 signature pages.
- Max 3 `getTransaction` calls.
- Max 1 `getBlockTime` call.
- 10-second timeout per call.
- Zero retries.
- No endpoint rotation.

## Retry Result

| Field | Result |
| --- | --- |
| Source status | `FAILED` |
| Data quality | `MISSING_CRITICAL_DATA` |
| Failure type | `solana_rpc_token_age_page_cap_exhausted` |
| Failure message | `Signature page cap (3) exhausted before reaching mint history start` |
| `token_created_at` | Not populated |
| `token_age_seconds` | Not populated |
| `token_age_evidence_tier` | Not populated |
| T3 provenance fields | Not populated because the success path did not complete |

The result is a bounded live proof retry failure, not a successful T3 evidence
proof. The adapter failed closed and did not substitute pair age, `captured_at`,
migration time, first trade time, or `OBSERVED_LIVE_LAUNCH`.

## Corrected Mint Decoder Result

Result: `PASS_FOR_PREVIOUS_FAILURE_CAUSE`

The retry no longer failed with the prior Token-2022 byte-82 AccountType error.
It progressed past mint-account validation into signature-history inspection.
This confirms the V2-2AL.1 Token-2022 layout repair addressed the previous
failure cause for this mint.

## Initialization Transaction Result

Result: `NOT_PROVEN`

The proof did not reach the mint history start within the approved 3-page cap,
so it did not inspect a matching successful `initializeMint` or
`initializeMint2` transaction. No exact mint-target initialization transaction
was accepted, and no block time was accepted.

## Operation Count and Methods

The normalized failure payload does not expose partial `t3_rpc_methods_attempted`
because `t3_*` provenance fields are emitted only on successful T3 evidence.
From the bounded failure point, the inferred methods attempted were:

| Method | Inferred count | Basis |
| --- | ---: | --- |
| `getAccountInfo` | 1 | Mint validation succeeded before signature-history inspection |
| `getSignaturesForAddress` | 3 | Failure reported 3-page cap exhaustion |
| `getTransaction` | 0 | No initialization candidate was reached |
| `getBlockTime` | 0 | No transaction with null block time was accepted |

Total inferred RPC operations: 4, within the max-8 operation cap.

## T3 Evidence and Provenance Result

| Required pass field | Result |
| --- | --- |
| `token_created_at` | Missing |
| `token_age_seconds >= 0` | Missing |
| `token_age_evidence_tier = "T3"` | Missing |
| `t3_requested_mint` | Missing |
| `t3_rpc_host_redacted` | Missing |
| `t3_rpc_methods_attempted` | Missing |
| `t3_request_ids` | Missing |
| `t3_pages_fetched` | Missing |
| `t3_signatures_inspected` | Missing |
| `t3_accepted_signature` | Missing |
| `t3_accepted_slot` | Missing |
| `t3_block_time_raw` | Missing |
| `t3_block_time_source` | Missing |
| `t3_instruction_type` | Missing |
| `t3_token_program` | Missing |
| `t3_derived_token_created_at` | Missing |
| `t3_derived_token_age_seconds` | Missing |
| `t3_captured_at` | Missing |

All 15 `t3_*` provenance fields remain absent because the governed request did
not produce accepted T3 evidence. This is fail-closed behavior.

## Proof DB Row Deltas

Only Source Governor trace rows changed in the isolated proof DB:

| Table | Delta |
| --- | ---: |
| `printer_source_requests` | +1 |
| `printer_source_responses` | 0 |
| `printer_source_failures` | +1 |
| `printer_token_snapshots` | 0 |
| `printer_memory_windows` | 0 |
| `printer_memory_retrieval_queries` | 0 |
| `printer_memory_retrieval_matches` | 0 |
| `printer_paper_decisions` | 0 |
| `printer_paper_positions` | 0 |
| `printer_paper_trade_events` | 0 |
| `printer_paper_trade_audits` | 0 |

Proof DB Source Governor rows:

- `source_request_id`: `1119`
- `source_response_id`: `null`
- `source_failure_id`: `48`

## Safety Confirmations

- Exactly one approved mint was retried.
- No discovery command was run.
- No broad source activation occurred.
- No scheduler/runtime command was run.
- No memory window was generated.
- No retrieval was activated.
- No paper decision was created.
- No BUY/SELL/HOLD path was unlocked.
- No paper position, trade event, audit, or PnL row was created.
- No wallet, private key, signing, transaction build/send, real-fund, paid API,
  scoring, ranking, confidence, weighted, embedding, or vector logic was used.
- A3 remains locked.
- V2-3 remains paused.

## Tests / Checks Run

- `python -m pytest tests/test_v2_2ak_t3_solana_rpc_token_age.py -q`
- `git diff --check`
- `git status --short`
- `git diff --stat`
- `git diff --name-only`

## Blockers

- The approved mint now passes the repaired mint-account validation step, but
  its signature history did not reach the mint initialization point within the
  approved 3-page cap.
- No successful `initializeMint` or `initializeMint2` transaction was accepted.
- No valid non-future block time was accepted.
- No T3 token-age evidence was produced.
- The adapter still exposes `t3_*` provenance only on success, so failed live
  attempts require operator reports to infer partial method progress from the
  failure stage.
- A3 remains locked.
- The staged/native 15m blocker remains `PARTIAL - DEFERRED, NOT RESOLVED`.
- V2-3 remains paused.

## Verdict

`LIVE_T3_RETRY_FAIL`

The retry proved the Token-2022 byte-82 repair against the prior live mint
failure mode, but it did not prove successful T3 evidence. The live proof now
fails later and honestly at the bounded signature-history page cap.

## Exact Next Lane

`V2-2AM - A3 Readiness Review and Repair Design`

The next lane should not unlock A3. It should review what is required before A3
can safely use token-age evidence, including this T3 page-cap blocker, staged
15m remaining deferred, and the need for successful token-age provenance before
any A3 activation.
