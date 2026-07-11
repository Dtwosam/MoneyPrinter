# Printer V1 V2-2AH Observed Live Launch Live Proof

**Lane:** V2-2AH - OBSERVED_LIVE_LAUNCH Live Proof
**Type:** Bounded live proof, isolated proof DB only
**Verdict:** `LIVE_PROOF_INCONCLUSIVE_NO_EVENTS`
**Date:** 2026-07-10

V2-3, V2-4, runtime/scheduler, memory generation, retrieval, paper decisions,
BUY/SELL/HOLD, paper positions, trades, audits, and PnL remain paused.

This lane ran exactly one bounded live PumpPortal `pumpfun_launch_stream` call
through the existing Source Governor execution path against an isolated proof
DB. It did not change source code or tests.

---

## 1. Source Stack Read

| Document | Role |
|---|---|
| `AGENTS.md` | Highest local build rules and active anchors |
| `docs/printer-v1-clean-master-spec.md` | V1 master safety/specification rules |
| `docs/printer-v1-memory-growth-build-order-v2.md` | Active V2 memory-growth roadmap |
| `docs/printer-v1-v2-2af-pumpportal-launch-timestamp-evidence-design-update.md` | OBSERVED_LIVE_LAUNCH design update |
| `docs/printer-v1-v2-2ag-observed-live-launch-tier-implementation.md` | Implementation closeout for observed-live tier |
| `docs/printer-v1-v2-2ag-1-observed-live-launch-tier-verification.md` | Independent verification of observed-live implementation |
| `docs/printer-v1-v2-2ae-pumpportal-live-event-diagnostics.md` | Prior live event diagnostics and payload-shape evidence |

The source stack preserves all V1 restrictions: Solana-only, paper-only, no
wallet/private keys, no real funds, no live execution, no paid APIs, no
scoring/ranking/confidence/weighted logic, no retrieval activation, no paper
decisions, no BUY/SELL/HOLD, no positions, no trades, no audits, and no PnL.

---

## 2. Active Dependency And Preflight Result

| Check | Result |
|---|---|
| `websockets` import | PASS |
| `websockets` version | `15.0.1` |
| `pumpfun_launch_stream` status | `READY` |
| `pumpfun_migration_stream` status | `NOT_READY` |
| PumpPortal `enabled_by_default` | `False` |
| PumpPortal `supports_network_execution` | `True` |
| PumpPortal `fixture_transport_only` | `False` |

The live proof used only the launch stream. The migration stream and PumpSwap
were not called.

---

## 3. Proof Setup

| Item | Value |
|---|---|
| Persistent DB path | `data/printer_v1.sqlite3` |
| Proof DB path | `data/printer_v1_v2_2ah_observed_live_launch_live_proof.sqlite3` |
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

Execution path used:

```text
build_pumpportal_live_transport(max_events=5, duration_seconds=30.0, connect_timeout_seconds=10.0)
-> build_pumpportal_adapter(enabled=True, fixture_transport=capturing_transport)
-> build_governed_source_request("pumpportal", "pumpfun_launch_stream", ...)
-> execute_source_request_with_governor(proof_db, request, adapter)
-> normalize_candidates("pumpportal", normalized_payload)
```

No broad discovery, scheduler/runtime, memory generation, retrieval, paper
decision, BUY/SELL/HOLD, position, trade, audit, or PnL command was run.

---

## 4. Persistent DB Hash And Counts

Persistent DB hash:

| Stage | SHA-256 |
|---|---|
| Before | `97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB` |
| After | `97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB` |

Persistent DB hash unchanged: yes.

Persistent DB row counts:

| Table | Before | After | Delta |
|---|---:|---:|---:|
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
| `printer_paper_audit_reports` | 1 | 1 | 0 |
| `printer_scheduler_jobs` | 989 | 989 | 0 |
| `printer_discovery_candidates` | 15 | 15 | 0 |
| `printer_tracking_queue` | 15 | 15 | 0 |

The persistent DB was not mutated.

---

## 5. Source Governor Proof DB Rows

Proof DB row deltas:

| Table | Before | After | Delta |
|---|---:|---:|---:|
| `printer_source_requests` | 1118 | 1119 | +1 |
| `printer_source_responses` | 1071 | 1071 | 0 |
| `printer_source_failures` | 47 | 48 | +1 |
| `printer_token_snapshots` | 1012 | 1012 | 0 |
| `printer_memory_windows` | 156 | 156 | 0 |
| `printer_memory_retrieval_queries` | 10 | 10 | 0 |
| `printer_memory_retrieval_matches` | 0 | 0 | 0 |
| `printer_paper_decisions` | 2 | 2 | 0 |
| `printer_paper_positions` | 0 | 0 | 0 |
| `printer_paper_trade_events` | 0 | 0 | 0 |
| `printer_paper_trade_audits` | 0 | 0 | 0 |
| `printer_paper_audit_reports` | 1 | 1 | 0 |
| `printer_scheduler_jobs` | 989 | 989 | 0 |
| `printer_discovery_candidates` | 15 | 15 | 0 |
| `printer_tracking_queue` | 15 | 15 | 0 |

Recorded proof DB IDs:

| Item | Value |
|---|---:|
| Source request ID | 1119 |
| Source response ID | none |
| Source failure ID | 48 |

Source result:

| Field | Value |
|---|---|
| `source_status` | `FAILED` |
| `data_quality_label` | `MISSING_CRITICAL_DATA` |
| `failure_type` | `pumpportal_no_valid_solana_events` |
| `failure_message` | `PumpPortal payload contained no valid Solana events` |

The failure was recorded honestly in the proof DB. No clean source response was
fabricated.

---

## 6. Live Event Result

| Metric | Count |
|---|---:|
| Raw message count | 0 |
| Decoded dict count | 0 |
| Mint-bearing event count | 0 |
| Normalized candidate count | 0 |
| `OBSERVED_LIVE_LAUNCH` count | 0 |
| `T2` count | 0 |
| Candidates with `token_created_at is not None` | 0 |
| Candidates with `token_age_seconds is not None` | 0 |
| A3 candidate count | 0 |

No raw messages arrived in the bounded 30-second proof window. Because no
mint-bearing launch event arrived, the required pass condition could not be
evaluated.

This result is not a parser failure and not an observed-live tier failure. It
is an inconclusive live sample with zero events.

---

## 7. Token-Age Safety Result

The proof did not observe any `OBSERVED_LIVE_LAUNCH` candidates, so the
positive pass condition was not reached.

Safety checks from the live output:

| Check | Result |
|---|---|
| Any candidate with `token_created_at is not None` | No |
| Any candidate with `token_age_seconds is not None` | No |
| Any A3 candidate | No |
| Any memory row created | No |
| Any retrieval row created | No |
| Any paper decision row created | No |
| Any paper position/trade/audit/PnL row created | No |

The lane therefore preserved token-age and financial locks, but did not prove
the positive observed-live mapping against real events.

---

## 8. Tests And Checks Run

Focused tests:

| Command | Result |
|---|---|
| `python -m pytest tests/test_v2_2ag_observed_live_launch_tier.py -q` | Passed: 30 passed |
| `python -m pytest tests/test_v2_2x2_t2_token_age_evidence.py -q` | Passed: 82 passed |
| `python -m pytest tests/test_v2_2ab_pumpportal_live_transport.py -q` | Passed: 43 passed |

Notes:

- Pytest emitted the existing local `gltest.config.yaml` notice.
- Pytest emitted the existing cache warning about `.pytest_cache`.
- The PumpPortal transport suite also emitted a local artifact cleanup warning
  before passing.

Git checks are recorded in the final task response after this document is
created.

---

## 9. Safety Confirmations

- Exactly one bounded live PumpPortal `pumpfun_launch_stream` call was run.
- The call used `subscribeNewToken`.
- Bounds were max 5 messages, max 30 seconds, and 10 second connect timeout.
- No reconnect loop was used.
- No retry loop was used.
- No background worker was started.
- No scheduler job was created.
- Source Governor wrote one request row and one failure row to the isolated
  proof DB only.
- No source rows were added to the persistent DB.
- No raw events were persisted to the persistent DB.
- No discovery candidates were created in the persistent DB.
- No token snapshots were created.
- No memory windows were created.
- No retrieval rows were created.
- No paper decisions were created.
- No paper positions, trade events, audits, or PnL rows were created.
- `pumpfun_migration_stream` remained `NOT_READY` and was not called.
- PumpSwap was not touched.
- No BUY/SELL/HOLD was unlocked.
- No wallet/private-key/signing/live-execution path was touched.
- No paid API dependency was added.
- No scoring/ranking/confidence/weighted logic was added.
- No embeddings/vectors were added.

---

## 10. Remaining Blockers

| Blocker | Status | Impact |
|---|---|---|
| No raw PumpPortal messages arrived in this proof window | CONFIRMED | Positive observed-live mapping could not be evaluated |
| No mint-bearing event arrived | CONFIRMED | `OBSERVED_LIVE_LAUNCH` count remained 0 |
| T2 explicit timestamp proof still absent | CARRY-FORWARD | No real event in this run provided timestamp evidence |
| V2-3 remains paused | CONFIRMED | This proof does not unlock V2-3 |

---

## 11. Exact Next Recommended Lane

`V2-2AH.1 - OBSERVED_LIVE_LAUNCH Retry-Or-Window Policy Decision`

Recommended scope:

1. Decide whether a single no-event window is acceptable as an inconclusive
   live proof or whether one future bounded retry is allowed.
2. If a retry is allowed, keep the same limits:
   - isolated proof DB only
   - one PumpPortal `pumpfun_launch_stream` call
   - max 5 messages
   - max 30 seconds
   - no reconnect
   - no retry loop inside the command
   - no scheduler/runtime
3. Do not move to V2-3 until the operator accepts the remaining V2-2 evidence
   state.

Alternative if the operator does not want another live window:

`V2-2AI - Token-Age Evidence Carry-Forward Closeout`

This would document that OBSERVED_LIVE_LAUNCH is fixture-verified but not live
proven in V2-2AH, and that token age remains a carry-forward evidence blocker.

---

## 12. Final Verdict

```text
VERDICT: LIVE_PROOF_INCONCLUSIVE_NO_EVENTS
LIVE_CALL_RAN: YES
SOURCE_GOVERNOR_PATH: execute_source_request_with_governor
PROOF_DB_ONLY: YES
RAW_MESSAGE_COUNT: 0
MINT_BEARING_EVENT_COUNT: 0
NORMALIZED_CANDIDATE_COUNT: 0
OBSERVED_LIVE_LAUNCH_COUNT: 0
T2_COUNT: 0
TOKEN_CREATED_AT_NON_NULL_COUNT: 0
TOKEN_AGE_SECONDS_NON_NULL_COUNT: 0
A3_UNLOCKED: NO
PERSISTENT_DB_UNCHANGED: YES
V2_3_STATUS: PAUSED
```
