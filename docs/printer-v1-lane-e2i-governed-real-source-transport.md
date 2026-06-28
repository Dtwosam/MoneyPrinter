# Lane E2I — Governed Real Source Transport Boundary

## What E2I Does

Lane E2I adds the real DexScreener smoke transport required for
`TRACK_FAST_FIRST_15M`. After E2I:

- `check_real_source_transport_available()` in E2H delegates to E2I and returns
  `(True, reason)`.
- `_check_15m_cycle_runtime_available()` in E2G returns `(True, ...)` when the
  handler is registered AND transport is available.
- E2G reports `OPERATOR_RUN_READY` when all gates pass (approval, backup, token
  list, transport).
- The one-shot smoke command `printer-run-e2i-one-shot-governed-source-smoke` is
  available for operator verification.

## What E2I Does NOT Do

E2I does NOT authorize the full 15m cycle. The operator must commit and tag Lane
E2G and then run `printer-run-e2g-first-bounded-15m-operator-run` manually.

- Claude did not run the full 15m cycle.
- No snapshots, context, or memory are created.
- No paper decisions, positions, or PnL are created.
- No BUY/SELL/HOLD decisions.
- No wallet, private keys, signing, or live execution.
- No paid APIs.
- No scoring, ranking, confidence, weighted logic, embeddings, or vectors.

## Transport Architecture

E2I uses the existing `DexScreenerAdapter` from `dexscreener.py`. The adapter
was already implemented but disabled by default. E2I enables it with the real
`build_dexscreener_token_transport(token_mint)` HTTP transport, which uses the
approved token mint as the lookup target:

```python
def build_e2i_dexscreener_adapter(*, token_mint: str, timeout_seconds=5.0) -> DexScreenerAdapter:
    transport = build_dexscreener_token_transport(token_mint, timeout_seconds=timeout_seconds)
    return build_dexscreener_adapter(enabled=True, smoke_transport=transport)
```

Transport is token-specific. Endpoint pattern:
`https://api.dexscreener.com/latest/dex/tokens/{token_mint}`

Generic SOL search (`q=SOL`) is forbidden. The `_GENERIC_SEARCH_FORBIDDEN` flag
and `no_generic_search` hard lock are set to `True` in all payloads.
The approved token mint is extracted from the validated operator token list —
it cannot be overridden externally. `approved_token_mint` and `smoke_target`
are reported in the payload for operator verification.

No new external dependencies. Free/public API only. No authentication required.
No paid tier.

## E2H Delegation

`e2h_runtime_handler.check_real_source_transport_available()` now delegates to
E2I via lazy import:

```python
def check_real_source_transport_available() -> tuple[bool, str]:
    try:
        from printer_v1.operator_cli.e2i_source_transport import (
            check_real_source_transport_available as _e2i_check,
        )
        return _e2i_check()
    except ImportError:
        return (False, _REAL_SOURCE_TRANSPORT_REASON)
```

E2I does NOT import from E2H (no circular dependency).

## One-Shot Smoke Command

The `printer-run-e2i-one-shot-governed-source-smoke` command makes exactly one
governed DexScreener call for operator verification. The command:

1. Validates `--operator-approved` flag
2. Validates backup proof file exists at `--backup-proof-path`
3. Validates DB file exists at `--db-path`
4. Validates token list at `--token-list-path` (1 TRACK_FAST approved token,
   no placeholder mint)
5. Counts before-rows for audit tables
6. Calls Source Governor (`can_request_source`)
7. Calls DexScreener smoke endpoint through governed transport
8. Records source request/response/failure rows
9. Counts after-rows for audit tables
10. Reports full payload including before/after counts

### Required CLI Arguments

```
printer-run-e2i-one-shot-governed-source-smoke
  --token-list-path <PATH>         Operator-approved token list JSON
  --backup-proof-path <PATH>       Path to DB backup file (proof it exists)
  --db-path <PATH>                 Path to printer_v1.sqlite3
  --operator-approved              Explicit operator approval flag
  --format json                    Output format (json recommended)
```

### Permitted Writes

- `printer_source_requests` — one row per governed request
- `printer_source_responses` — one row if source responds successfully
- `printer_source_failures` — one row if Source Governor rejects or transport fails

### Forbidden Writes (Hard Locks)

The following tables must remain at zero new rows:

- `printer_paper_decisions`
- `printer_paper_positions`
- `printer_paper_trade_events`
- `printer_paper_trade_audits`
- `printer_token_snapshots`
- `printer_memory_windows`
- `printer_memories`

## PHASE35_SAFE_JOB_KINDS and Handler Integration

The `TRACK_FAST_FIRST_15M` handler (E2H) is registered in `PHASE35_SAFE_JOB_KINDS`.
The Phase 35/36 bounded runner dispatches `TRACK_FAST_FIRST_15M` jobs to
`execute_track_fast_first_15m_job`. After E2I, the transport gate passes.

The handler's production path (`adapter=None`) returns `executed=True` with
`source_results=[]` because the Phase 35/36 dispatcher does not yet inject a
real adapter. The one-shot smoke command (`build_e2i_one_shot_smoke_payload`) is
the authorized path for making real governed source calls in Lane E2I.

## E2G Gate Flow After E2I

```
E2G build_e2g_operator_run_payload()
  └── _check_15m_cycle_runtime_available()
        └── e2h: is_handler_registered() → True (Lane E2H)
        └── e2h: check_real_source_transport_available()
              └── e2i: check_real_source_transport_available() → (True, reason)
        → returns (True, "TRACK_FAST_FIRST_15M handler registered and real
                   source transport available")
  └── other gates: approval_confirmed, backup_confirmed, backup_proof,
                   token count=1, no running jobs, no locks
  → OPERATOR_RUN_READY (when all gates pass)
```

## Security Constraints

These constraints are permanent and may never be violated:

- No BUY/SELL/HOLD decisions
- No paper decisions, paper positions, or PnL
- No token snapshots created by smoke command
- No memory windows or memories created by smoke command
- No wallet, private keys, signing, or live execution
- No paid APIs (DexScreener public tier only)
- No scoring, ranking, confidence, or weighted logic
- No embeddings or vectors
- Claude did not run the full 15m cycle

## Anchor

- Commit: E2I closes at `printer-v1-post-lane10-lane-e2i-governed-real-source-transport`
- Base: E2H commit `735d1be`, tag `printer-v1-post-lane10-lane-e2h-track-fast-first-15m-runtime-handler`
- This module does NOT authorize real execution. The operator runs
  `printer-run-e2g-first-bounded-15m-operator-run` manually after commit+tag.
