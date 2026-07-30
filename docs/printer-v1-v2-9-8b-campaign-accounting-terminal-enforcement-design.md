# Printer V1 V2-9.8B Campaign Accounting and Terminal Enforcement Design

Date: 2026-07-30

Lane: `V2-9.8B Campaign Accounting and Terminal Enforcement Completion`

Status: `FINAL_DESIGN_FOR_IMPLEMENTATION`

Supersedes, for this surface, the verifiable-real-path design's treatment of
DexScreener exact-pair accounting, campaign-owner authority, terminal
enforcement, and post-handoff lifecycle proofs.

## D1 — DexScreener exact-pair identity on every outcome (B1/B2)

`build_dexscreener_smoke_transport` is the single exact-pair snapshot transport
(used by `build_dexscreener_pair_snapshot_transport` /
`build_dexscreener_token_transport`). One outbound GET = exactly one
`TransportOperationIdentity`, attached via `measured_payload_fields([identity])`
to **every** return payload:

| Outcome | `result` | bytes / rows |
|---|---|---|
| success (object with `pairs`) | `OK` | measured / pair count |
| byte ceiling exceeded | `BYTE_CEILING` | measured / 0 |
| exact-pair row ceiling exceeded | `ROW_CEILING` | measured / pair count |
| non-object body (malformed) | `MALFORMED` | measured / 0 |
| HTTP 429 | `RATE_LIMITED` | 0 / 0 |
| HTTP 5xx | `HTTP_SERVER_ERROR` | 0 / 0 |
| HTTP 4xx | `HTTP_CLIENT_ERROR` | 0 / 0 |
| JSON/Unicode decode failure | `DECODE_FAILURE` | 0 / 0 |
| OSError / TimeoutError | `TRANSPORT_FAILURE` | 0 / 0 |

A single helper `_pair_identity(result, response_bytes, normalized_rows)`
builds the identity; each branch returns `MappingProxyType(payload +
measured_payload_fields([identity]))`. `transport_operations_used` is therefore
always `1`. Error branches that never read a body report `0` bytes/rows — an
attempt still counts as one transport operation. The multi-hop fresh-profiles
transport already preserves prior identities on later-hop failure; a
regression test pins that behavior.

## D2 — `ACCOUNTING_BLOCKED` immediate safe stop (B3)

In `run_direct_migration_discovery`, when `accounting_block_reason` is set the
candidate-mix export is skipped entirely: `candidate_mix=[]`,
`latest_graduated_count=0`, `persisted_graduated_count=0`,
`total_persisted_graduated=0`, plus:

- `campaign_safe_stop=True`
- `registry_candidates_withheld=<count of persisted rows not exported>`

The registry table itself is not mutated (no writes), but no existing candidate
is handed forward. A blocked attempt therefore cannot feed selection or
activation.

## D3 — Top-level campaign six-unit owner as sole authority (B4/B5/B6)

`CampaignSixUnitOwner` gains:

- `ingest_stage_evidence(evidence)` — validates a durable stage evidence block
  (reusing `reconstruct_six_unit_totals_from_evidence`'s structural checks:
  malformed / duplicate / negative fail closed), rehydrates each transport
  identity onto the owner's ledger (dedup enforced), and adds the non-transport
  counters (local validations, scheduler work, lifecycle reservations).
- module function `aggregate_campaign_six_unit_owner(*, campaign_id, run_id,
  cycle_id, started_at, stage_evidences)` — builds one owner from an ordered
  sequence of stage evidence blocks. This is the **single top-level ledger**
  that reconciles every active stage (direct Pump, PumpSwap, DexScreener,
  holder/safety, local validations, Scheduler work, response bytes, normalized
  rows, lifecycle reservations). Omitted/malformed stage accounting raises
  `CampaignSixUnitError` (fail closed).

Stage results still *expose* evidence; they are no longer an *authority*. The
coordinator aggregates them into the owner and the owner emits the one
authoritative `durable_evidence()` / `six_unit_totals()` used for the report.

## D4 — Terminal enforcement (B7/B8/B9)

`build_campaign_terminal_report(..., require_six_unit_evidence: bool = False)`:

When `require_six_unit_evidence=True` (the top-level coordinator path):

1. missing / non-`Mapping` evidence → `TerminalClosureError`
   (`SIX_UNIT_EVIDENCE_MISSING`) — **no** synthetic empty substitution;
2. malformed / duplicate / negative evidence → `TerminalClosureError`
   (propagated from `reconstruct_six_unit_totals_from_evidence`);
3. `six_unit_evidence_match` (report totals vs independent evidence rebuild)
   `False` → `TerminalClosureError` (`SIX_UNIT_EVIDENCE_MISMATCH`).

Legacy callers (`require_six_unit_evidence=False`, the default) keep the prior
lenient behavior so existing terminals are unaffected, but the match flag is
always computed and stored.

`write_campaign_terminal_report(..., require_six_unit_evidence: bool = False)`
re-validates the same three conditions on the assembled report **before**
persistence when required, so an omitted/malformed/mismatched evidence report
can never be persisted or reported as successful completion.

`empty_six_unit_evidence()` remains legal only for a genuinely no-work terminal
(all six units zero) — it is never used to cover an attempted campaign's real
work.

## D5 — Coordinator wiring (B4/B5/B6, real path)

`_run_operational_campaign`:

- constructs a top-level `CampaignSixUnitOwner(campaign_id, run_id, cycle_id)`;
- after the run, aggregates the discovery/lifecycle stage evidence into it via
  `aggregate_campaign_six_unit_owner` (malformed stage evidence → fail-closed
  terminalization);
- passes the owner's `six_unit_totals()` / `durable_evidence()` and
  `require_six_unit_evidence=True` to `build_campaign_terminal_report` /
  `write_campaign_terminal_report`.

No PumpPortal, candidate-acquisition, or cursor authority is introduced (the
composition source-text guard remains satisfied).

## D6 — Post-handoff failure injection + compensation (B10/B11/B12)

`OriginToLifecycleCampaignDriver.run` and `materialize_origin_activated_batch`
accept `post_handoff_fault: str | None`, injecting a `PostHandoffInjectedFault`
at exactly one of the five post-handoff stages, **after** the executor's
successful atomic initial handoff:

1. `LIFECYCLE_SELECTION_BATCH_CREATION` — after the batch row insert, before items
2. `EXECUTOR_JOB_CANCELLATION` — inside `_cancel_executor_first_15m_jobs`
3. `LIFECYCLE_JOB_REPLANNING` — at the handoff to the lifecycle runner
4. `LIFECYCLE_OBJECT_MATERIALIZATION` — inside the lifecycle runner (shim)
5. `POST_ACTIVATION_STATE_TRANSITION` — at the driver's post-activation cycle
   transition after the runner returns

On any injected fault the driver runs a compensating teardown
(`_compensate_post_handoff_teardown`) scoped to the cycle/campaign identities
that removes every newly active or orphan row: token slots, tracking-queue
rows, scheduler jobs (executor `window15m:*` and factory jobs), leases,
selection batches, batch items, discovery selected-item links, and lifecycle
objects (run steps, snapshots). It returns a `FAILED` `OriginLifecycleResult`
with `first_terminal_cause = POST_HANDOFF_<STAGE>` and
`lifecycle_started=False`. Proof asserts zero rows across all target tables on
a fresh disposable migration-049 database per injection.

Replay (`replay_campaign_terminal_report`) is asserted to open the DB read-only
and create zero source calls, Scheduler work, or writes.

## Preserved locks

Solana memecoin-only, paper-only; direct stateless one-page Pump live tail;
complete 25-role validation; canonical deterministic two-token selector;
exactly two active tokens; `WINDOW_15M` only; 5m support-only; migration head
049; Source Governor + Central Scheduler; no automatic retry/restart/successor;
no providers/RPC/WebSockets during proof; no authoritative DB mutation; no
N2/N7/cursor/recovery/backfill; no retrieval, decisions, BUY/SELL/HOLD,
positions, trades, audits, PnL; no wallets/keys/signing/funding/paid APIs,
scoring, ranking, confidence, weighting, embeddings, or live execution. No
ceiling is raised.

## Implementation modules

| Module | Change |
|---|---|
| `sources/dexscreener.py` | exact-pair identity on every outcome (D1) |
| `discovery/direct_migration_discovery.py` | `ACCOUNTING_BLOCKED` safe stop (D2) |
| `sources/campaign_six_unit_accounting.py` | `ingest_stage_evidence` + `aggregate_campaign_six_unit_owner` (D3) |
| `operator_cli/unified_terminal_closure.py` | `require_six_unit_evidence` enforcement in build + write (D4) |
| `operator_cli/operational_memory_factory_command.py` | top-level owner aggregation + enforcement wiring (D5) |
| `operator_cli/origin_lifecycle_campaign.py` | post-handoff injection + compensating teardown (D6) |
| `tests/test_v2_9_8b_campaign_accounting_terminal_enforcement.py` | frozen offline proofs |
| docs | audit / design / closeout; anchor update |
