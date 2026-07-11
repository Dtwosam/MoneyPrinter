# Printer V1 V2-2AL Bounded Live T3 Token-Age Proof

Status: BOUNDED LIVE PROOF
Lane: V2-2AL - Bounded Live T3 Solana RPC Token-Age Proof
Executor/model: Codex, standard/balanced mode
Anchor: `d910909 Add V2-2AK.3 T3 readiness repair verification`
Verdict: `LIVE_T3_PROOF_FAIL`

V2-3, V2-4, runtime/scheduler, memory generation, retrieval, paper decisions,
BUY/SELL/HOLD, positions, trades, audits, and PnL remain paused.

This lane performed exactly one operator-approved, bounded, read-only Solana
RPC proof attempt through the existing Source Governor boundary against an
isolated proof DB only. It did not change code, change tests, run discovery,
activate runtime, create memory, activate retrieval, create paper decisions,
unlock A3, unlock V2-3, or touch any paper-trading/financial path.

The staged/native 15m blocker remains `PARTIAL - DEFERRED, NOT RESOLVED`.

## Source Stack Read

- `AGENTS.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-v2-2aj-t3-solana-rpc-token-age-evidence-design.md`
- `docs/printer-v1-v2-2ak-2-t3-live-proof-readiness-repair.md`
- `docs/printer-v1-v2-2ak-3-t3-readiness-repair-verification.md`

## Preflight

| Item | Result |
| --- | --- |
| Mint selection source | Existing local V2/X artifact; no discovery was run |
| Mint source document | `docs/printer-v1-lane-x10-7-manual-discovery-15m-proof-report.md` |
| Mint used | `pumpgrWRAztPTe9HpqUUj23hWDcz1qvkbMRiDM6wint` |
| Endpoint type | Public/free Solana RPC |
| RPC host shown | `api.mainnet-beta.solana.com` |
| `websockets` relevance | Irrelevant; this lane used read-only Solana JSON-RPC, not PumpPortal |
| Proof DB | `data/printer_v1_v2_2al_t3_live_proof.sqlite3` |
| Persistent DB | `data/printer_v1.sqlite3` |
| Persistent DB hash before | `97db9a15cc464d86137cbbb0dd0a4ef1880e9f4e231fb41e8b22ca09fb177fbb` |
| Persistent DB hash after | `97db9a15cc464d86137cbbb0dd0a4ef1880e9f4e231fb41e8b22ca09fb177fbb` |
| Persistent DB unchanged | Yes |

The isolated proof DB was copied from `data/printer_v1.sqlite3` before the
proof. The copy hash matched the persistent DB hash before the live call.

## Live Proof Limits

The proof used the V2-2AK T3 adapter and live transport with the designed caps:

- Source Governor path only.
- Explicit live transport injection.
- One token only.
- Max 8 RPC operations.
- Max 3 signature pages.
- Max 3 `getTransaction` calls.
- Max 1 `getBlockTime` call.
- 10-second timeout per call.
- Zero retries.
- No endpoint rotation.

The live attempt reached the public Solana RPC endpoint and failed closed during
mint account validation.

## Proof Result

| Field | Result |
| --- | --- |
| Source status | `FAILED` |
| Data quality | `MISSING_CRITICAL_DATA` |
| Failure type | `solana_rpc_token_age_not_a_mint` |
| Failure message | `Token-2022 mint-state decode failed: Token-2022 AccountType byte 0 is not Mint (expected 1)` |
| `token_created_at` | Not populated |
| `token_age_seconds` | Not populated |
| `token_age_evidence_tier` | Not populated |
| T3 provenance fields | Not populated because the success path did not complete |

The result is a live proof failure, not a successful T3 evidence proof. The
adapter did the correct safety behavior: it rejected the mint before attempting
signature-history or transaction evidence and did not fabricate token age from
pair age, `captured_at`, migration time, first trade, or
`OBSERVED_LIVE_LAUNCH`.

## Operation Count

The normalized failure payload does not expose `t3_rpc_methods_attempted`
because those fields are emitted only on successful T3 evidence. From the
failure point, the live transport reached the first mint-account validation
step and failed there.

| Operation view | Count |
| --- | --- |
| Inferred live RPC operations before failure | 1 (`getAccountInfo`) |
| Exposed successful `t3_rpc_methods_attempted` count | 0 |
| Signature pages | 0 |
| `getTransaction` calls | 0 |
| `getBlockTime` calls | 0 |

This stayed inside the lane caps.

## Source Governor Proof DB Rows

| Table | Delta after live call |
| --- | --- |
| `printer_source_requests` | `+1` |
| `printer_source_responses` | `+0` |
| `printer_source_failures` | `+1` |

Proof DB row identifiers:

- `source_request_id`: `1119`
- `source_response_id`: `null`
- `source_failure_id`: `48`

The failure was recorded in the isolated proof DB only.

## Persistent DB No-Change Verification

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

Persistent DB hash before and after matched exactly. Persistent DB mutation:
none.

## Proof DB Downstream Lock Verification

The isolated proof DB recorded only the Source Governor request/failure rows.
It created no downstream rows:

| Table | Delta |
| --- | ---: |
| `printer_token_snapshots` | 0 |
| `printer_memory_windows` | 0 |
| `printer_memory_retrieval_queries` | 0 |
| `printer_memory_retrieval_matches` | 0 |
| `printer_paper_decisions` | 0 |
| `printer_paper_positions` | 0 |
| `printer_paper_trade_events` | 0 |
| `printer_paper_trade_audits` | 0 |

## Safety Confirmations

- Exactly one approved mint was attempted.
- No discovery command was run to find a token.
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
  - Result: `114 passed`
  - Note: emitted the pre-existing pytest cache warning for `.pytest_cache`
    path creation; tests still passed.

## Blockers

- The selected approved artifact mint did not produce valid T3 evidence because
  the live mint-account validation failed the Token-2022 AccountType mint check.
- No valid `token_created_at`, `token_age_seconds`, `token_age_evidence_tier =
  "T3"`, or successful `t3_*` provenance bundle was produced.
- The adapter currently does not expose partial RPC method provenance on failure
  payloads, so the exact attempted RPC method list is inferred from the failure
  point rather than normalized into `t3_rpc_methods_attempted`.
- A3 remains locked.
- The staged/native 15m blocker remains `PARTIAL - DEFERRED, NOT RESOLVED`.
- V2-3 remains paused.

## Verdict

`LIVE_T3_PROOF_FAIL`

The live Source Governor path and public read-only Solana RPC endpoint were
reachable, and the failure was recorded safely in the isolated proof DB. The
proof did not satisfy the V2-2AL goal because no successful T3 token-age
evidence was produced.

## Exact Next Lane

`V2-2AL.1 - Approved T3 Mint Selection Preflight and Bounded Retry`

The next lane should remain inside V2-2 and should not unlock A3 or V2-3. It
should choose an operator-approved mint from existing local artifacts, verify
that the selected mint is suitable for T3 proof without running discovery, then
perform at most one new bounded Source-Governor T3 proof if the operator
approves the retry.
