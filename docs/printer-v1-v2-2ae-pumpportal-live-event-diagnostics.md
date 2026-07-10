# V2-2AE PumpPortal Live Event-Level Diagnostics

Status: DIAGNOSTICS ONLY

Diagnostics verdict: `DIAGNOSTICS_COMPLETE_PAYLOAD_SHAPE_BLOCKER`

This lane ran one bounded live PumpPortal `pumpfun_launch_stream` diagnostic
call through the existing governed adapter path against an isolated proof DB.
It did not run broad discovery, scheduler/runtime, memory generation,
retrieval, paper decisions, BUY/SELL/HOLD, paper positions, trade events, paper
trade audits, or PnL.

V2-3 remains paused.

## Source Stack Read

Required documents checked:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-v2-2ad-bounded-live-pumpportal-smoke-proof.md`
- `docs/printer-v1-v2-2ac-pumpportal-websockets-dependency-gate.md`
- `docs/printer-v1-v2-2ab-minimal-pumpportal-live-transport-implementation-proof.md`

Files inspected:

- `src/printer_v1/sources/pumpportal.py`
- `tests/test_v2_2ab_pumpportal_live_transport.py`
- `tests/test_v2_2x2_t2_token_age_evidence.py`

## Diagnostic Question Answers

1. Did no raw PumpPortal events arrive?

   No. Raw messages did arrive. The diagnostic call received 5 raw WebSocket
   messages.

2. Or did raw events arrive but get rejected by the parser/normalizer?

   Raw messages arrived. One message was a subscription acknowledgement with no
   mint field and was not a token event. Four messages had `mint` fields and
   normalized successfully as PumpPortal launch candidates.

3. If rejected, what fields were missing or mismatched?

   The main blocker is not mint parsing. The blocker is timestamp evidence:
   none of the 5 decoded dict messages contained `tokenCreatedAt`,
   `createdTimestamp`, or `timestamp`. The current T2 token-age contract requires
   one of those fields to set `token_created_at`.

4. What is the smallest safe next lane?

   `V2-2AF - PumpPortal Launch Timestamp Evidence Design Update`.

   The next lane should decide whether PumpPortal launch events can safely use a
   governed receipt/observation timestamp as a lower-tier token-age evidence
   label, or whether T2 must remain unavailable from PumpPortal until the source
   provides explicit launch timestamps. It should be design first; no parser
   rewrite should happen inside this diagnostics lane.

## Diagnostic Setup

| Item | Value |
| --- | --- |
| Proof DB path | `data/printer_v1_v2_2ae_pumpportal_event_diagnostics.sqlite3` |
| Persistent DB path | `data/printer_v1.sqlite3` |
| DB mode | isolated proof DB copied from persistent DB |
| Source | `pumpportal` |
| Request kind | `pumpfun_launch_stream` |
| Subscription | `subscribeNewToken` |
| Max events/messages | 5 |
| Max duration | 30 seconds |
| Connect timeout | 10 seconds |
| Reconnects | 0 |
| Retry loop | none |
| Background worker | none |
| Scheduler job | none |
| Source Governor path | `execute_source_request_with_governor()` |

Run timestamps:

- Started: `2026-07-10T08:21:04.075224+00:00`
- Ended: `2026-07-10T08:21:26.060164+00:00`

## Raw Event Diagnostics

| Metric | Count |
| --- | ---: |
| Raw WebSocket messages received | 5 |
| JSON decoded messages | 5 |
| Dict events/messages | 5 |
| Skipped non-JSON messages | 0 |
| Skipped non-dict messages | 0 |
| Events with `mint` | 4 |
| Events with `tokenMint` | 0 |
| Events with `token_mint` | 0 |
| Events with `tokenCreatedAt` | 0 |
| Events with `createdTimestamp` | 0 |
| Events with `timestamp` | 0 |
| Messages with Solana mint-like string values | 5 |
| Normalized event count | 4 |
| Usable launch timestamp count | 0 |

First payload shapes:

1. Subscription acknowledgement:

   - Type: dict
   - Keys: `message`
   - Has mint: no
   - Has `tokenCreatedAt`: no
   - Has `createdTimestamp`: no
   - Has `timestamp`: no
   - Sample: `{"message": "Successfully subscribed to token creation events."}`

2. Launch-like token event:

   - Type: dict
   - Has mint: yes
   - Has `tokenCreatedAt`: no
   - Has `createdTimestamp`: no
   - Has `timestamp`: no
   - Keys observed:
     `bondingCurveKey`, `initialBuy`, `is_mayhem_mode`, `marketCapSol`, `mint`,
     `name`, `pool`, `signature`, `solAmount`, `symbol`, `traderPublicKey`,
     `txType`, `uri`, `vSolInBondingCurve`, `vTokensInBondingCurve`

3. Second launch-like token event:

   - Type: dict
   - Has mint: yes
   - Has `tokenCreatedAt`: no
   - Has `createdTimestamp`: no
   - Has `timestamp`: no
   - Same general key shape as the first launch-like event.

## Rejection Reason Buckets

| Bucket | Count | Meaning |
| --- | ---: | --- |
| `missing_mint_field` | 1 | Subscription acknowledgement had no token mint |

There were no non-JSON, non-dict, or connection-error buckets.

Important nuance:

The four mint-bearing launch events were not rejected by the normalizer. They
normalized as candidate events. However, they did not provide T2 token-age
evidence because the live payload did not include any accepted timestamp field.

## Source Governor Proof DB Rows

Proof DB row deltas:

| Table | Before | After | Delta |
| --- | ---: | ---: | ---: |
| `printer_source_requests` | 1118 | 1119 | +1 |
| `printer_source_responses` | 1071 | 1072 | +1 |
| `printer_source_failures` | 47 | 47 | 0 |

Recorded row IDs:

- Source request row ID: `1119`
- Source response row ID: `1072`
- Source failure row ID: none

Source result:

- Source status: `COMPLETE`
- Data quality label: `CLEAN_DATA`
- Failure type: none
- Failure message: none
- Normalized event count: 4
- Usable launch timestamp count: 0

## Persistent DB No-Change Result

Persistent DB hash:

| Stage | SHA-256 |
| --- | --- |
| Before | `97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB` |
| After | `97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB` |

Persistent DB hash unchanged: yes.

Persistent DB row deltas:

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
| `printer_scheduler_jobs` | 989 | 989 | 0 |

The persistent DB was not mutated.

## Safety Confirmations

- Exactly one bounded live PumpPortal `pumpfun_launch_stream` diagnostic call
  was run.
- The call used `subscribeNewToken`.
- The call used max 5 messages/events, max 30 seconds, and 10 second connect
  timeout.
- No reconnect loop was used.
- No retry loop was used.
- No background worker was started.
- No scheduler job was created.
- Proof writes were limited to source request/response rows in the isolated
  proof DB.
- No raw events were persisted to the persistent DB.
- No discovery candidates were created.
- No token snapshots were created.
- The persistent DB hash and all inspected persistent row counts were unchanged.
- `pumpfun_migration_stream` was not called.
- PumpSwap was not touched.
- No memory, retrieval, paper-decision, paper-position, trade, audit, or PnL
  path was activated.
- No BUY/SELL/HOLD was unlocked.
- No wallet, private key, signing, transaction, real-fund, paid API,
  scoring/ranking/confidence/weighted, embedding, or vector path was added.

## Tests and Checks Run

Focused tests:

- `python -m pytest tests/test_v2_2ab_pumpportal_live_transport.py -q`
- `python -m pytest tests/test_v2_2x2_t2_token_age_evidence.py -q`

Git checks:

- `git diff --check`
- `git status --short`
- `git diff --stat`
- `git diff --name-only`

## Remaining Blockers

| Blocker | Status |
| --- | --- |
| Live PumpPortal launch events do not include `tokenCreatedAt` in this sample | CONFIRMED |
| Live PumpPortal launch events do not include `createdTimestamp` in this sample | CONFIRMED |
| Live PumpPortal launch events do not include `timestamp` in this sample | CONFIRMED |
| Current T2 token-age path cannot derive `token_created_at` from these live payloads | CONFIRMED |
| V2-3 remains paused | INTENTIONAL |

## Exact Next Recommended Lane

`V2-2AF - PumpPortal Launch Timestamp Evidence Design Update`

Recommended design questions:

1. Should PumpPortal live receipt time be allowed as a lower-tier launch-age
   evidence label, separate from T2?
2. If yes, what label should distinguish it from explicit source timestamp
   evidence?
3. If no, should PumpPortal remain useful for launch discovery while token-age
   evidence stays unavailable until another source confirms creation time?
4. How should reports distinguish "launch event observed live" from "source
   supplied explicit token creation timestamp"?

No parser rewrite, candidate creation, snapshot creation, memory generation,
retrieval, paper decision, BUY/SELL/HOLD, position, trade, audit, or PnL should
be added without a future approved implementation lane.

## Final Conclusion

`DIAGNOSTICS_COMPLETE_PAYLOAD_SHAPE_BLOCKER`

V2-2AE proves that V2-2AD's zero-valid-event result was not simply because no
raw PumpPortal messages could arrive. In this diagnostic run, raw messages did
arrive, four mint-bearing launch events normalized successfully, and the Source
Governor recorded a clean proof-DB response. The remaining blocker is payload
shape: the live events did not include any timestamp field accepted by the
current T2 token-age contract.

V2-3 remains paused.
