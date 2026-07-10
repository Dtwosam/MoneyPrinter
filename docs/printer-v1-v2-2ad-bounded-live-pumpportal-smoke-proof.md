# V2-2AD Bounded Live PumpPortal Smoke Proof

Status: SMOKE PROOF ONLY

Proof verdict: `LIVE_SMOKE_INCONCLUSIVE_NO_EVENTS`

This lane ran one bounded operator-approved public PumpPortal launch-stream
smoke call through the existing Source Governor path against an isolated proof
DB. It did not run broad discovery, scheduler/runtime, memory generation,
retrieval, paper decisions, BUY/SELL/HOLD, paper positions, trade events, paper
trade audits, or PnL.

V2-3 remains paused.

## Source Stack Read

Required documents checked:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-v2-2aa-minimal-pumpportal-launch-transport-design.md`
- `docs/printer-v1-v2-2ab-minimal-pumpportal-live-transport-implementation-proof.md`
- `docs/printer-v1-v2-2ab-1-pumpportal-transport-verification.md`
- `docs/printer-v1-v2-2ac-pumpportal-websockets-dependency-gate.md`

Anchors confirmed:

- V2-2AA: `447e3fc`
- V2-2AB: `45dfb2c`
- V2-2AB.1: `fbf59de`
- V2-2AC: `622fd5f`

## Dependency Preflight

`pyproject.toml` declares:

```toml
dependencies = ["websockets>=12.0"]
```

The non-escalated Python environment could import `websockets 15.0.1`.
The live-call environment initially could not import `websockets`, so the first
attempt stopped before any live call with:

```text
RuntimeError: build_pumpportal_live_transport requires the 'websockets' package
```

Per the lane preflight, `python -m pip install -e .` was run. It installed:

- `printer-v1 0.0.0`
- `websockets 16.1`

The escalated/live-call environment then imported `websockets 16.1`
successfully.

## Proof Setup

| Item | Value |
| --- | --- |
| Proof DB path | `data/printer_v1_v2_2ad_pumpportal_live_smoke.sqlite3` |
| Persistent DB path | `data/printer_v1.sqlite3` |
| DB mode | isolated proof DB copied from persistent DB |
| Source | `pumpportal` |
| Request kind | `pumpfun_launch_stream` |
| Subscription | `subscribeNewToken` |
| Max events | 5 |
| Max duration | 30 seconds |
| Connect timeout | 10 seconds |
| Reconnects | 0 |
| Retry loop | none |
| Background worker | none |
| Scheduler job | none |
| Operator approval | explicit for V2-2AD |
| Source Governor path | `execute_source_request_with_governor()` |

Run timestamps:

- Started: `2026-07-10T08:09:35.309923+00:00`
- Ended: `2026-07-10T08:09:45.794432+00:00`

The smoke call completed in about 10.5 seconds.

## Live Call Result

The live call ran once, through Source Governor, against the proof DB only.

Result:

- Source status: `FAILED`
- Data quality label: `MISSING_CRITICAL_DATA`
- Failure type: `pumpportal_no_valid_solana_events`
- Failure message: `PumpPortal payload contained no valid Solana events`
- Response row: none
- Failure row: recorded
- Valid normalized token/event count: 0
- Usable launch timestamp count: 0

Interpretation:

The transport was importable and callable, and the governed proof path recorded
the attempt. The bounded live stream produced no valid Solana launch events
during this smoke window, so the correct result is inconclusive rather than a
pass. No success or T2 token-age proof is claimed.

## Source Governor Proof DB Rows

Proof DB row deltas:

| Table | Before | After | Delta |
| --- | ---: | ---: | ---: |
| `printer_source_requests` | 1118 | 1119 | +1 |
| `printer_source_responses` | 1071 | 1071 | 0 |
| `printer_source_failures` | 47 | 48 | +1 |

Recorded row IDs:

- Source request row ID: `1119`
- Source response row ID: none
- Source failure row ID: `48`

This satisfies the failure branch of the smoke proof: a governed source request
row exists, and the failed/no-valid-events result is visible as a source failure
row in the isolated proof DB.

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

- Exactly one bounded live PumpPortal `pumpfun_launch_stream` call was attempted.
- The call used `subscribeNewToken`.
- The call used max 5 events, max 30 seconds, and 10 second connect timeout.
- No reconnect loop was used.
- No retry loop was used.
- No background worker was started.
- No scheduler job was created.
- Proof writes were limited to source request/failure rows in the isolated proof
  DB.
- The persistent DB hash and all inspected persistent row counts were unchanged.
- `pumpfun_migration_stream` remains `NOT_READY`.
- `enabled_by_default` remains `False`.
- `supports_network_execution` remains `True`.
- `fixture_transport_only` remains `False`.
- No memory, retrieval, paper-decision, paper-position, trade, audit, or PnL
  path was activated.
- No BUY/SELL/HOLD was unlocked.
- No wallet, private key, signing, transaction, real-fund, paid API,
  scoring/ranking/confidence/weighted, embedding, or vector path was added.

## Tests and Checks Run

Focused tests:

| Command | Result |
| --- | --- |
| `python -m pytest tests/test_v2_2ab_pumpportal_live_transport.py -q` | PASS: 43 passed, 1 warning |
| `python -m pytest tests/test_post_rc_pumpportal_discovery_adapter.py -q` | PASS: 41 passed, 1 warning |
| `python -m pytest tests/test_v2_2x2_t2_token_age_evidence.py -q` | PASS: 82 passed, 1 warning |

Warnings:

- Pytest cache warnings about `.pytest_cache` path creation were emitted.
- Local `gltest` default configuration messages were emitted.

Git checks:

- `git diff --check`
- `git status --short`
- `git diff --stat`
- `git diff --name-only`

## Remaining Blockers

| Blocker | Status |
| --- | --- |
| Live stream produced no valid Solana launch events in the bounded window | BLOCKER for live T2 proof |
| No response row was recorded because normalization failed on no valid events | Honest failure branch, not a pass |
| No usable launch timestamp was observed | T2 token-age evidence not proven in this lane |
| `pumpfun_migration_stream` remains `NOT_READY` | Intentional |
| V2-3 remains paused | Intentional |

## Next Recommended Lane

`V2-2AE - PumpPortal Live Event Capture Reattempt or Event-Level Diagnostics`

Recommended scope:

- Keep the same proof-DB-only, Source-Governor-only constraints.
- Do not broaden into discovery automation.
- Reattempt only if the operator approves another bounded live call, or first
  add diagnostics that preserve raw empty/no-event failure visibility without
  creating discovery candidates.
- Continue to keep memory, retrieval, paper decisions, BUY/SELL/HOLD, positions,
  trades, audits, and PnL locked.

## Final Verdict

`LIVE_SMOKE_INCONCLUSIVE_NO_EVENTS`

The V2-2AD lane proved that the dependency gate can be satisfied, the bounded
live transport can be invoked through Source Governor, the failure/no-event
branch is recorded in the isolated proof DB, and the persistent DB remains
unchanged. It did not prove usable PumpPortal launch-event capture because the
bounded live window yielded zero valid normalized Solana launch events.

V2-3 remains paused.
