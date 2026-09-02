# Printer V1 — V2-9.8B Sep-2 Surviving Pre-Lifecycle Wait Reconciliation / Zero-State Closeout

Status: **CLOSED PASS**

Verdict:

`V2_9_8B_SEP2_SURVIVING_PRE_LIFECYCLE_WAIT_RECONCILIATION_ZERO_STATE_PASS`

Classification:

`HISTORICAL_ORPHANED_ACTIVE_WAIT_RESIDUE`

This lane reconciled one known historical Cycle-2 pre-lifecycle refresh wait
left `WAITING` after consumed authorization
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260902T122136Z_59fdefe7`. It did not repair
production code, change schema, run Printer, call providers, prepare or apply
an authorization, or drain any other historical row.

The prior cleanup-ordering defect is already repaired. This closeout is
historical-residue reconciliation only.

## Identity

- branch: `assistant/v2-9-8b-later-cycle-mint-market-replay-repair`
- start HEAD: `6f8a1b6ac7f00fda1f7dca38c7532473b03f1ada`
- closeout documentation commit: `3e4aa14c2f08f2dec741ca9bbe80111b5534d166`
- end HEAD: the live source-stack HEAD after this closeout package; bind `git rev-parse HEAD` from `CURRENT_HANDOFF.md`
- consumed authorization
  `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260902T122136Z_59fdefe7` remains
  `CONSUMED / CHILD_EXITED_NONZERO / PERMANENTLY NON-REUSABLE`
- campaign: `20260902T123958Z-5a3e78f1a7b8-campaign`
- campaign run: `20260902T123958Z-5a3e78f1a7b8-campaign-run`
- proposed Cycle 2: `20260902T123958Z-5a3e78f1a7b8-cycle-2` (never admitted)
- factory run: `7b492361-03ee-4ec2-8b54-89a41612cf8e`
- wait:
  `prelifecycle-refresh-wait:20260902T123958Z-5a3e78f1a7b8-campaign:20260902T123958Z-5a3e78f1a7b8-campaign-run:20260902T123958Z-5a3e78f1a7b8-cycle-2:1`
- refresh Scheduler job: `3548` (`DISCOVERY_REFRESH`)
- Cycle-2 pre-admission attempt:
  `pre-admission:20260902T123958Z-5a3e78f1a7b8-campaign:20260902T123958Z-5a3e78f1a7b8-campaign-run:7b492361-03ee-4ec2-8b54-89a41612cf8e:c0002`

## Authoritative DB

Path: `data/printer_v1.sqlite3`

- SHA-256 before: `cd6b1d4ac7171f4096d06c9b09a035a0cf622899806b9a58cc990a2936ad6659`
- SHA-256 after: `fb52d8fae2d22c70f6c2c7de7ddf4a18c7d89f01450f12e6c60093ee85e17cff`

The post-reconciliation SHA is the new DB identity for subsequent readiness
work. The old SHA must not be reused as current identity.

## Ownership audit

Exactly one `WAITING`/`CLAIMED` refresh wait existed. It belonged to the
consumed failed Sep-2 campaign/run. Parent execution authority was already
terminal:

- campaign `TERMINAL_FAILED` /
  `OPERATIONAL_CAMPAIGN_FAILED:FourTokenFactoryAdapterError`
- campaign run `TERMINAL_FAILED` / same cause
- Cycle 1 `TERMINAL_STOPPED` / `SAFE_STOP_PREFLIGHT_FAILED`
- no persisted Cycle-2 campaign-cycle row
- factory run `SAFE_STOPPED` / `SAFE_STOP_PREFLIGHT_FAILED`
- campaign supervision `TERMINAL` / `FAILED`; lease released; lock file absent
- no live Printer process
- no active campaign/proof supervision
- no `RUNNING` refresh work for this wait
- job `3548` already `CANCELLED`, unlocked, `started_at` null
- Cycle-2 attempt already `CANCELLED` /
  `PARENT_CAMPAIGN_INTERRUPTED:SAFE_STOP_PREFLIGHT_FAILED`
- attempt job `3493` already `CANCELLED`, unlocked

The wait could not lawfully resume. No other active wait in that campaign/run
created ambiguous ownership. Classification is
`HISTORICAL_ORPHANED_ACTIVE_WAIT_RESIDUE`, not a new committed-code defect.

## Canonical owner and terminal cause

Invoked once, after disposable-copy proof, on the authoritative DB:

`printer_v1.operator_cli.pre_lifecycle_persistent_refresh_owner.abandon_scoped_refresh_waits`

Scope:

- `campaign_id` = Sep-2 campaign
- `run_id` = Sep-2 campaign run
- `cycle_id` = proposed Cycle 2

Truthful terminal cause, from current parent-interrupt cleanup law and the
already-persisted Cycle-2 attempt first-terminal cause:

`PARENT_CAMPAIGN_INTERRUPTED:SAFE_STOP_PREFLIGHT_FAILED`

No raw SQL `UPDATE`/`DELETE` was used as the cleanup mechanism. No second
cleanup implementation was constructed. One authoritative invocation. No retry.

## Wait / graph outcomes

| Object | Before | After |
|---|---|---|
| known wait | `WAITING`, no first-terminal cause | `CANCELLED` / `PARENT_CAMPAIGN_INTERRUPTED:SAFE_STOP_PREFLIGHT_FAILED` at `2026-09-02T22:14:34.168733+00:00` |
| matching refresh work | none | none; no row invented |
| job `3548` | `CANCELLED`, unlocked | unchanged |
| Cycle-2 attempt | `CANCELLED` / same cause | unchanged; first-terminal cause preserved |
| campaign / run / Cycle 1 / factory / supervision | already terminal | unchanged |
| restart / successor / new campaign | absent | still absent |

## Official zero-state

Official projection owner:

`project_four_token_proof_zero_state`

Refresh waits counted with `wait_state IN ('WAITING','CLAIMED')`.

Before: every required domain `0` except
`active_pre_lifecycle_discovery_refresh_waits = 1`.

After: every required domain `0`.

Campaign-scoped `campaign_active_work_report` for the Sep-2 campaign/run/factory
went from `clean_terminal = false` to `clean_terminal = true`. No other official
zero-state domain was non-zero.

## Integrity and isolation

- `PRAGMA integrity_check` = `ok`
- `PRAGMA foreign_key_check` = zero rows
- every user table fingerprint unchanged except
  `printer_pre_lifecycle_discovery_refresh_waits`
- source-request count unchanged (`4688`)
- no authorization/application-marker change
- no schema change
- no production-code change

Disposable-copy proof passed the same checks before the authoritative write.

## Confirmations

- no Printer execution
- no providers / RPC / WebSockets
- no Central Scheduler runtime
- no authorization created, applied, or consumed
- consumed `59fdefe7` still permanently non-reusable
- no candidate acquisition
- no retry / rerun / resume / restart / successor
- 476 / 118 / 444 preserved; retries `0`; endpoint rotation `false`
- 4/2/2 preserved
- `+600 / +1200 / +1800 / +2400` preserved
- all V1 locks preserved

## Exact next permitted action

```text
FRESH POST-RECONCILIATION EXACT-HEAD / EXACT-DB NEXT-BOUNDED-CAMPAIGN READINESS / GOVERNANCE AUDIT
```

That next lane must bind the final post-reconciliation Git HEAD and the new
authoritative DB SHA-256
`fb52d8fae2d22c70f6c2c7de7ddf4a18c7d89f01450f12e6c60093ee85e17cff`.

It does **not** authorize authorization preparation, `apply_authorization_once`,
application-marker creation, Printer execution, provider/RPC/WebSocket calls,
Central Scheduler runtime, retrieval, BUY/SELL/HOLD, positions, trades, audits,
PnL, or `WINDOW_12H` / `WINDOW_24H`.
