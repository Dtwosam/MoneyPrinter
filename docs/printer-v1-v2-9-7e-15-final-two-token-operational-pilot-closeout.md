# V2-9.7E.15 Final Authorized Two-Token Operational Pilot — Closeout

**Status:** LIVE PILOT EXECUTED — HONEST BLOCK (clean governed safe-stop; mandatory clean-memory evidence unobtainable live)

**Verdict:** `V2_9_7E_15_BLOCKED_SOURCE_OR_EVIDENCE`

---

# Live pilot execution — 2026-07-22

## Exact baseline and authorization

- Commit: `fe64c36c9faf6c6d320a91483269585ac1b144d3`
- Message: `Provision isolated two-token pilot source`
- HEAD verified equal to the authorized baseline; clean tracked tree and index;
  no stash; E.11–E.16 artifacts present; no active campaign/runner/process/lease;
  no stale E15 target/backup/restore/lock/log/report/execution.

The operator authorized exactly one live real-wall-clock execution of the
committed two-token pilot runner. **That authorization was consumed by this
run.** No production code was modified. No standalone reachability or readiness
cycle was performed — the pilot was the only live source use.

## Full path manifest (all approved, absolute, mutually distinct, outside repo)

| Artifact | Path |
|---|---|
| Persistent source DB | `C:\Users\dtwof\PrinterPilot\E15\source\printer-v1-e15-source.sqlite3` |
| Pilot target DB | `C:\Users\dtwof\PrinterPilot\E15\printer-v1-e15-pilot.sqlite3` |
| Pre-run backup file | `C:\Users\dtwof\PrinterPilot\E15\backups\printer-v1-e15-pre-run-backup.sqlite3` |
| Restore-rehearsal DB | `C:\Users\dtwof\PrinterPilot\E15\restore\printer-v1-e15-restore-rehearsal.sqlite3` |
| Report directory | `C:\Users\dtwof\PrinterPilot\E15\reports` |
| Lock file | `C:\Users\dtwof\PrinterPilot\E15\locks\pilot.lock` |
| Standard-output log | `C:\Users\dtwof\PrinterPilot\E15\logs\pilot.stdout.log` |
| Standard-error log | `C:\Users\dtwof\PrinterPilot\E15\logs\pilot.stderr.log` |

Launched via the committed unregistered runner
`scripts/v2_9_7e_14_two_token_operational_pilot.py` (execution id
`v2-9-7e-15-final-pilot`) with real, uncompressed production timing.

## Source identity before and after

- Before: size **2,183,168** bytes; SHA-256
  `770fb92c0f3c5444aae6f559d8e474b2e62483191da8d3e9aeb74e6c3f562f20`; head
  `036_pumpfun_finalized_origin_registry.sql`; ledger 36/36; `integrity_check`
  `ok`; 0 foreign-key errors; all operational/retrieval/financial tables empty;
  no active lease. Distinct from the authoritative corpus.
- After: SHA-256 **unchanged** (`770fb92c…`). The runner treated the source as
  logically read-only and only copied it into the isolated target; it never
  migrated, mutated, leased, supervised, or executed against it.

## Backup and restore evidence

- Byte-identical pre-run backup written (`target_hash == backup_hash ==
  770FB92C…`), `proof_backup_byte_identical = true`, `persistent_unchanged =
  true`.
- Disposable restore rehearsal ran and passed (`restore_rehearsal_ok = true`)
  and the rehearsal copy was removed. `prepare` returned `PILOT_TARGET_READY`
  with `no_active_lease = true`.

## Start / end time and duration

- Start (UTC): `2026-07-22T14:28:42Z`
- End (UTC): `2026-07-22T14:44:43Z`
- Real duration: **≈16m01s**. The campaign terminated at the two 15m closes
  because **no natural continuation formed** (see below); it did not need the
  full ~4.25 h envelope.

## Source and operation accounting

- Total governed source requests: **41**; responses **34**; failures **7**.
  Finalized Pump-origin discovery via free-public Solana RPC succeeded and
  yielded ≥2 finalized supported origins; per-token 15m snapshot lanes
  (DexScreener) succeeded. The 7 failures were the isolated secondary/context
  lanes (see risks), which are `ALLOWED_FIXTURE_ONLY` and fail live; they were
  isolated and never weakened a gate.
- Every external operation was Source-Governor-admitted before transport and
  Central-Scheduler-owned (committed E.11 owner path). Status inspection was
  local and zero-source throughout (`source_calls: 0`, `scheduler_calls: 0`).

## Gate and activation results

- Finalized Pump origins: ≥2 observed; deterministic seeded selection.
- **Exactly two-or-none atomic activation:** 2 slots `SELECTED` (ordinals 1, 2).
- Selected identities exactly equal activated identities; no token/pair identity
  mixing (redacted): slot 1 mint `id:5655ee1af66c` / pair `id:be133f108498`;
  slot 2 mint `id:b1312c39e885` / pair `id:f319c3eda40d`.

## Per-token lifecycle

- Both tokens received independent, real 15m streams (16 snapshot steps total
  SUCCEEDED across the two tokens; the executor's 2 first-15m handoff jobs were
  CANCELLED by design and superseded by the factory's own scheduling).
- **Both terminal 15m closes SUCCEEDED**; 2 `WINDOW_15M` memory windows created;
  2 `MEMORY_WINDOW_CLOSE` jobs SUCCEEDED.
- Token-local isolation held: all run steps SUCCEEDED; no starvation; no
  cross-token mixing; no shared fault.

## Natural continuation and support-only 5m evidence

- **Two-terminal-15m-close barrier** released only after both tokens had terminal
  15m close evidence, then evaluated each token from its **own** governed window.
- Both tokens' 15m windows classified **`DIRTY_MEMORY` / `OUTCOME_UNKNOWN`**.
  Per the committed fail-closed natural-evidence disposition, ineligible
  (dirty/unknown) memory can drive **no** continuation and **no** support
  capture. Both dispositions were therefore, identically and order-independently:
  `continuation_plan = STOP_AFTER_15M` (`enqueue_ok = false`) and
  `support_5m = VALID_NO_CAPTURE`.
- 15m→1h continuation: **none** (naturally absent — not manufactured).
- 1h→4h continuation: **none** (naturally absent — not manufactured).
- Support-only 5m: **0** capture windows; the only observed case was the valid
  **no-capture** result on both tokens. The eligible-capture case did **not**
  occur naturally and is reported as absent, not manufactured. No support-only
  5m episode, continuation, retrieval or financial authority was created.

## Memory and promotion evidence

- Both 15m windows: `DIRTY_MEMORY` / `OUTCOME_UNKNOWN`.
- Episodes built: **0**; dirty or `DO_NOT_TRAIN` promotions: **0**; eligible
  clean promotions: **0**. The clean-memory and no-dirty-promotion locks held:
  the dirty windows were honestly classified and correctly **not** promoted.
- No favorable, negative, or neutral clean memory was promoted, because no clean
  memory was produced this run.

## Fairness and identity isolation

- Exactly two tokens throughout; no expansion beyond two; no starvation; no
  token/pair identity mixing; token-local jobs isolated; no shared fault; the
  barrier produced identical, close-order-independent dispositions.

## Report, replay, integrity and cleanup

- Terminal report produced **exactly once** (`status: PILOT_TERMINAL`).
- Report-only replay **deterministic** and **zero-source** (`replay_deterministic
  = true`, `replay_new_source_calls = 0`).
- `PRAGMA integrity_check` → `ok`; `PRAGMA foreign_key_check` → **0** errors.
- Run-step cleanup clean: all 18 run steps SUCCEEDED; `pending_or_running_run_steps
  = 0`; `running_jobs_after_stop = 0`; 0 run-step-linked scheduler jobs remain
  pending/running.
- One-proof lock **released** (`one_proof_lock_released = true`; lock file absent
  after). Supervision execution is `TERMINAL` with terminal status
  `GOVERNED_SAFE_STOP` and immutable first cause `SAFE_STOP_4H_TERMINAL_INCOMPLETE`.
- No automatic restart or successor (`restart_created = false`,
  `successor_created = false`).
- Source hash **unchanged**; backup byte-identical; persistent source unchanged.
- **Minor observation (non-blocking):** 10 `DISCOVERY_REFRESH` scheduler rows
  remain `PENDING` in the isolated disposable target. They are **not** linked to
  any run step, are not lifecycle/campaign work, and are inert (the execution is
  terminal, the lock is released, no process exists, the target is disposable).
  The runner's run-scoped cleanup contract (run steps and run-linked jobs) is
  satisfied; these discovery-cadence rows are documented as a cleanup nuance, not
  stale run work.

## Prohibited-capability deltas

All zero. Retrieval queries/matches, paper decisions, paper positions, paper
trade events, paper trade audits, and paper audit reports: **0** rows each, and
the runner's `forbidden_deltas` are all 0. No wallet, key, signing, funds, live
execution, paid API, scoring, ranking, embedding, retrieval, decision,
BUY/SELL/HOLD, position, trade, audit, or PnL occurred.

## Exact blocker

The pilot ran the committed owner exactly once, cleanly and safely, to a
`GOVERNED_SAFE_STOP`. It did **not** reach a COMPLETED PASS because the **active
V2-9.7E pilot gate requires a completed 4h terminal** (one clean natural
selective continuation surviving to 4h), and that required evidence was
**naturally absent**: both live tokens' 15m memory was `DIRTY_MEMORY`, so no
clean promotion and no eligible continuation could form. The root cause is that
the mandatory clean-memory context evidence — token safety (GoPlus), broad market
context (CoinGecko), and paper-quote realism (Jupiter), and part of the secondary
enrichment (GeckoTerminal) — is `ALLOWED_FIXTURE_ONLY` under the committed Source
Governor evidence rules and therefore fails in live mode, producing dirty 15m
memory. This is an **evidence** limitation, not a lifecycle or safety fault: the
lifecycle, barrier, fail-closed dirty rejection, supervision, report, replay and
cleanup all behaved correctly. Hence `V2_9_7E_15_BLOCKED_SOURCE_OR_EVIDENCE`.

## Money-usefulness contribution

This is the first end-to-end **live** exercise of the two-token operational
pathway: real finalized Pump-origin discovery → exact two-or-none activation →
two real 15m streams → both terminal 15m closes → the two-terminal-close barrier →
fail-closed natural disposition on dirty evidence → clean governed safe-stop with
deterministic zero-source replay and complete run cleanup, all with zero
retrieval/financial surface and an unmutated source. It proves the intake,
activation, barrier and safety machinery are trustworthy on live data, and it
pinpoints the single remaining gap to clean-memory growth: promoting the
fixture-only context/safety/quote source adapters to governed production-network
use.

## What the pilot improves

- Confirms live: governed discovery, exact two-or-none activation,
  identity-preserving handoff, two real 15m streams, the two-terminal-15m-close
  barrier, order-independent per-token dispositions, and — critically — the
  fail-closed rejection of dirty/`OUTCOME_UNKNOWN` memory (no continuation, no
  support capture, no promotion).
- Confirms live: durable lease/heartbeat, one execution, one campaign
  invocation, cooperative-stop wiring, immutable terminal cause, report-once,
  deterministic zero-source replay, clean run cleanup, no restart/successor,
  integrity/FK clean, and an unmutated source.

## What remains locked

All Printer V1 Solana-memecoin-only, paper-only, free/public-source, governance,
two-or-none, clean-memory, support-only-5m, and financial/retrieval locks remain
unchanged. No operator command was published; no CLI was registered; retrieval
and financial capabilities remain locked.

## Proof still required before V2-9.7F

1. Promote the mandatory clean-memory context/safety/quote source adapters
   (GoPlus token security, CoinGecko/market context, Jupiter paper-quote realism,
   and the GeckoTerminal secondary lanes) from `ALLOWED_FIXTURE_ONLY` to governed
   production-network use, each with its own committed adapter and proof lane, so
   a live 15m window can classify **clean** rather than dirty.
2. A subsequent authorized live pilot in which at least one token produces clean
   15m memory and a naturally derived selective 1h→4h continuation with a
   conditional support-only 5m capture and exactly one eligible clean promotion —
   or an honest block — under a fresh authorization.

## Functionality Risks / Setbacks / Efficiency Blockers

- **Setback (primary):** a live operational pilot cannot currently produce clean
  promotable memory or a natural continuation, because the mandatory
  clean-memory context/safety/quote adapters are fixture-only and fail live,
  making every 15m window dirty. The pilot therefore always safe-stops as
  `SAFE_STOP_4H_TERMINAL_INCOMPLETE`.
- **Risk (design observation, not patched here):** the committed `run_operational`
  runs in `four_hour_proof_mode`, so a live operational pilot can only reach a
  COMPLETED PASS if the market naturally yields a clean continuation surviving to
  4h — which the operator must not manufacture. Whether an operational (non-proof)
  pilot should treat "both tokens cleanly stop after 15m" as a valid COMPLETED
  outcome is an E.11-owner design question for a future lane; no production code
  was changed here.
- **Cleanup nuance:** 10 unlinked `DISCOVERY_REFRESH` rows remained `PENDING` in
  the disposable target after terminal closeout (inert; not run work).
- **Efficiency blocker:** none in the runner; the run terminated in ~16 minutes
  because no continuation formed.

## Readiness for V2-9.7F

**NOT READY for V2-9.7F.** The live pilot executed cleanly and safely but did not
satisfy the active pilot gate: the mandatory clean-memory evidence was
unobtainable live (fixture-only context/safety/quote adapters), so no clean
promotion or natural continuation occurred. V2-9.7F must not begin. V2-9.8, the
operational memory-growth command, and retrieval/decision/financial capabilities
remain locked and were not started.

---

# Historical section — prior E.15 preflight block (2026-07-22, before source provisioning)

**Status at the time:** BLOCKED AT PREFLIGHT — NO EXTERNAL REQUEST MADE

**Verdict at the time:** `V2_9_7E_15_BLOCKED_PREFLIGHT`

This earlier attempt (from baseline `bdd7625…`, before the E.16 source
provisioning) blocked at preflight because the committed runner requires an
explicit non-authoritative source database and none had yet been provided or
configured — only the target/backup/report paths were supplied, and the sole
persistent database was the authoritative corpus, which may not be used or
guessed. The single pilot authorization was preserved, no external request was
made, and no target was created. E.16 then provisioned the isolated source and
the full execution-path contract, enabling the live execution recorded above.

Key points preserved from that attempt:

- The runner's `PilotPaths.persistent_source_db` is required and validated as an
  existing file; `--persistent-source-db` is `required=True`; no default or
  configured non-authoritative source existed.
- The only persistent database was `CANONICAL_PERSISTENT_DB`
  (`…\MoneyPrinter\data\printer_v1.sqlite3`) — the authoritative corpus, forbidden
  as source or target.
- Per the Source database rule, the lane stopped before any external use with
  `V2_9_7E_15_BLOCKED_PREFLIGHT`, reporting the exact missing source-path
  requirement; production code was unchanged and the authorization stayed
  unconsumed.
