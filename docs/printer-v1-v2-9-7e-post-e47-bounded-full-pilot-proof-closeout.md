# Printer V1 — V2-9.7E Post-E.47 Fresh Bounded Two-Token Full-Pilot Proof Closeout

**Verdict: `V2_9_7E_POST_E47_FULL_PILOT_PASS`.**

Exactly one fresh, operator-authorized canonical `FULL_PILOT` was executed after
the E.47 lifecycle and clean-memory repairs. The run obtained its own fresh
isolated attempt DB, admitted two graduated tokens with exact-pool and holder
evidence, completed two real uncompressed `WINDOW_15M` lifecycles, preserved
truthful adverse outcomes while refusing dirty training memory, produced one
authoritative terminal closure across campaign / run / cycle / factory run /
supervision / work / Scheduler jobs, wrote a campaign terminal report, executed a
deterministic zero-source report replay, released the proof lock, and left zero
active or orphaned campaign work.

This is a proof lane only. No code or policy was changed before, during, or after
the attempt. V2-9.7F was not started. V2-9.8 was not activated.

| Field | Value |
|---|---|
| **Baseline / live HEAD** | `7df7ac0c1587e8b1d5a8af6464b5fbc4ad461fbe` |
| **Mode** | `FULL_PILOT` (canonical, single attempt) |
| **Executor** | macOS / zsh; committed Python entry point only |
| **Entry point** | `scripts/v2_9_7e_14_two_token_operational_pilot.py` |
| **Execution id** | `e47-full-20260725-7df7ac0` |
| **Wall clock** | **1320.4 s** (`2026-07-25T19:55:35.341571Z` → `20:17:35.739407Z`) |
| **First terminal cause** | `COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED` |
| **Lifecycle** | started = true; factory run `COMPLETED` |
| **Attempts consumed** | 1 |

---

## 1. Preflight (before any live source request or DB mutation)

| Condition | Result |
|---|---|
| Exact HEAD `7df7ac0…` | **PASS** |
| Tracked tree clean | **PASS** (`git status --porcelain --untracked-files=no` empty) |
| No active Printer process / campaign lease / unfinished attempt | **PASS** (prior E.46 lock expired and unused; fresh paths only) |
| `PRINTER_HELIUS_API_KEY` / `SOLANA_TRACKER_API_KEY` / `PRINTER_SOLANA_RPC_URL` present | **PASS** (presence only; values never printed) |
| Required imports + runtime deps (`websockets>=12.0`, package path) | **PASS** (Python 3.12.13, websockets 16.1.1, `printer_v1` from this repo) |
| Focused E.47 tests | **PASS** — `tests/test_v2_9_7e_47_lifecycle_and_clean_memory_repair.py` → **39 passed, 30 subtests** |
| Canonical command / ceilings / cleanup / report / zero-source replay owners | **PASS** (unchanged committed surface) |
| Fresh identities, isolated DB, backup/restore evidence | **PASS** |
| Old-laptop archive not used as execution DB or active code | **PASS** (prior registry used only as bootstrap **source** via committed `bootstrap_from_prior_registry`) |

Ceilings (unchanged):

| Ceiling | Value |
|---|---:|
| Source / operation | 45 |
| Failures | 20 |
| Scheduler work | 400 |
| Duration envelope | 15300 s |
| Token capacity | 2 |

Dependency + readiness preflight (zero external requests, zero DB writes before
authorization): both `READY`; `secret_material_recorded = false`.

---

## 2. Exact invocation

Committed Mac-compatible entry point (no PowerShell, no parallel runner):

```text
.venv/bin/python scripts/v2_9_7e_14_two_token_operational_pilot.py \
  --operator-approved \
  --persistent-source-db /Users/Dtwo1/PrinterPilot/E47FULL/e47-full-20260725-7df7ac0/canonical-graduated-registry.sqlite3 \
  --target-db .../attempt.sqlite3 \
  --backup-db .../attempt.backup.sqlite3 \
  --restore-rehearsal-db .../attempt.restore-rehearsal.sqlite3 \
  --report-dir .../reports \
  --lock-path .../one-proof.lock \
  --stdout-log .../executor-stdout.txt \
  --stderr-log .../executor-stderr.txt \
  --execution-id e47-full-20260725-7df7ac0 \
  --selection-seed e47-full-20260725-7df7ac0 \
  --git-provenance-json <capture at HEAD 7df7ac0, clean tree> \
  --evaluated-at 2026-07-25T19:55:34.962448+00:00 \
  --cycle-cutoff 2026-07-25T19:55:34.962448+00:00
```

Artifact root (outside the repository; not committed):

`/Users/Dtwo1/PrinterPilot/E47FULL/e47-full-20260725-7df7ac0/`

| Identity | Value |
|---|---|
| Campaign | `e47-full-20260725-7df7ac0-campaign` |
| Campaign run | `e47-full-20260725-7df7ac0-campaign-run` |
| Cycle | `e47-full-20260725-7df7ac0-cycle` |
| Configuration | `e47-full-20260725-7df7ac0-configuration` |
| Report | `e47-full-20260725-7df7ac0-report` |
| Factory run | `483014bd-65ea-4e1c-87d6-dd8fa289d73b` |
| Candidate export | `pilot-export:e47-full-20260725-7df7ac0:attempt.sqlite3` (14 rows) |
| Export provenance hash | `78dd97caf9764745c60d0251794bb561008ab90443b87223cbc829f783db922b` |

Target prep: `PILOT_TARGET_READY`;
`target_hash == backup_hash == 2db277ee2f0e9533d691dcd8d5ca1ecd2e9051daeae3692779e35afe630a397a`;
restore rehearsal OK; persistent registry unchanged
(`64bc49d9060aa38a88c502986256c86548636bba44d72ce1c74559e63c3b4eb6`, 14 rows).

Final attempt DB SHA-256:
`362c87da87c971a998595b5c778e9ef9a0eaddc2f09f6586df423f83ead03c3d`.

---

## 3. Minimum proof checklist

| Requirement | Result | Evidence |
|---|---|---|
| Exactly two valid token/pair identities | **PASS** | tokens=2, pairs=2; mints `22dMBw…pump` / `Gr5fbV…pump`; PumpSwap pools `FFrrAn…` / `BjxoCm…` |
| Approved graduated exact-pool supply + `$3,000+` front door | **PASS** | `graduated_admitted=2`, `eligibility_rule=GRADUATION_ONLY`; both selectable |
| Exact-target holder evidence (approved contract) | **PASS** | 4 holder attempts; GoPlus + Solana RPC (+ Helius Free backup after one public RPC 429); exact-target labels recorded |
| Two real `WINDOW_15M` lifecycle closes | **PASS** | both `WINDOW_CLOSED`; durations **905.8 s** and **911.7 s**; 8 snapshots + close per token (18 run steps `SUCCEEDED`) |
| Correct selective continuation | **PASS** | no `WINDOW_1H` / `WINDOW_4H`; both 15m closed `DEAD` / dirty → no continuation required or started |
| Optional support-only 5m non-authority | **PASS** | `window_5m_support_role=SUPPORT_ONLY_NOT_MAIN_EVIDENCE`; micro-event gate `MICRO_EVENT_SUPPORT_EVIDENCE` |
| Truthful clean/dirty/blocked + outcome separation | **PASS** | both `DIRTY_MEMORY` / `MISSING_CRITICAL_DATA` / `do_not_train=1` for mandatory safety absence; outcomes kept as **`DEAD`** with `HELD_TO_15M_DEAD` (−80.84% and −92.17%) |
| Known outcomes not erased because dirty | **PASS** | outcome_label=`DEAD` (not `OUTCOME_UNKNOWN`); held labels preserved |
| One authoritative terminal closure | **PASS** | campaign/run/cycle `TERMINAL_COMPLETED`; factory `COMPLETED`; supervision `TERMINAL` / `COMPLETED`; first cause immutable |
| Discovery work / Scheduler parity | **PASS** | 8/8 work `SUCCEEDED`; 8/8 `DISCOVERY_REFRESH` jobs `SUCCEEDED`; **0** `PENDING`/`RUNNING`/`COOLDOWN` |
| No PENDING/RUNNING/COOLDOWN/locked/orphaned work after close | **PASS** | `active_jobs=0`, `active_work_rows=0`, `pending_or_running_run_steps=0`, `clean_terminal=true` |
| Campaign terminal report | **PASS** | 1 row + 1 artifact; hash `3ebf1a874cc698a5bc9d3606015a09c960e76fa9b7008537a7c6a3d238aa382d` |
| Deterministic zero-source report replay | **PASS** | `replay_deterministic=true`, `new_source_calls=0`, `new_scheduler_work=0`, `database_writes=0`, `duplicate_reports_created=0`, `artifact_matches=true` |
| Proof lock + lease release | **PASS** | `one_proof_lock_released=true`; lock file absent |
| No restart / successor | **PASS** | both false |
| SQLite integrity + FK | **PASS** | `integrity_check=ok`; `foreign_key_check` empty; 42 migrations |
| Source / Scheduler / memory / lock deltas | **PASS** (see §4) |
| Zero retrieval / decision / position / trade / audit / PnL | **PASS** | all forbidden tables 0; report `downstream_unlocks` all false |
| No secret values in logs/reports/artifacts/Git | **PASS** | presence flags only; `secret_material_recorded=false` |

**Honest non-claims (not failures of the pilot path):**

- No `CLEAN_MEMORY` row was created. Both windows are dirty solely because
  mandatory exact-target safety evidence is absent
  (`NO_VALID_EXACT_TARGET_SAFETY_EVIDENCE` / `SAFETY_UNKNOWN`). Safety gates were
  **not** weakened.
- No positive/continuation-class outcome appeared in live market supply this run
  (both tokens collapsed). Negative separation is proved; positive separation is
  structurally intact but not market-exercised here.
- `WINDOW_1H` / `WINDOW_4H` continuation remains live-unexercised (correctly not
  forced when ineligible).

---

## 4. Source, Scheduler, memory, and locked-capability deltas

### Source requests (48 total; responses 45; durable failures 3)

| Source | Request kind | Count |
|---|---|---:|
| pumpportal | `pumpfun_migration_stream` | 3 |
| pumpswap | `pumpswap_signature_pool_resolution` | 4 |
| dexscreener | `dexscreener_fresh_profiles` | 1 |
| dexscreener | `pair_market_snapshot` | 24 |
| goplus | `safety_reference` | 4 |
| solana_rpc | `holder_concentration_reference` | 2 |
| solana_rpc | `pumpfun_origin_transaction_reference` | 2 |
| helius_free | `holder_concentration_reference` | 2 |
| coingecko | `broad_market_context` | 2 |
| jupiter_quote | `paper_quote_realism` | 4 |

Governed failures (honest, no retry expansion):  
`pumpportal_no_valid_solana_events` ×1; `solana_rpc_rate_limited` ×2.

Holder campaign ledger: `operation_ceiling=45`, `governed_requests=18`,
`underlying_transport_operations=19`, zero-transport ops tracked separately.
Ceiling not breached.

### Scheduler / work

| Class | Terminal |
|---|---|
| Discovery work | 8 `SUCCEEDED` |
| Discovery jobs | 8 `SUCCEEDED` |
| Track snapshots | 16 `SUCCEEDED` |
| Window closes | 2 `SUCCEEDED` |
| Track-normal first-15m placeholders | 2 `CANCELLED` (lawful) |
| Active after stop | **0** |

### Memory

| Metric | Value |
|---|---|
| `WINDOW_15M` closed | 2 |
| Clean memory | 0 |
| Dirty memory / do_not_train | 2 / 2 |
| Outcomes | `DEAD` + `DEAD` (truthful) |
| Held results | `HELD_TO_15M_DEAD` (−80.84% / −92.17%) |
| Closing liquidity | $4,424.85 / $1,485.39 |
| Micro-event support rows | 2 (support-only) |
| Paper quote evidence | 4 (allowed; not a unlock) |

### Forbidden / locked capabilities

| Table / capability | Delta |
|---|---:|
| retrieval queries / matches | 0 / 0 |
| paper decisions / decision audits | 0 / 0 |
| paper positions / trade events / trade audits / paper audits | 0 |
| BUY/SELL/HOLD / PnL / wallet / signing / live execution | none |

### Persistent corpus

Canonical graduated registry remained **14 rows**, SHA-256 unchanged. Attempt
registry grew to **18** (live confirmations isolated to the attempt DB only).

---

## 5. E.47 live confirmation map

| E.47 blocker | Offline | Live this run |
|---|---|---|
| BL-47-01 ownership graph terminal | fixed offline | **Live PASS** — `TERMINAL_COMPLETED` ×3 |
| BL-47-02 discovery job parity | fixed offline | **Live PASS** — 8/8 jobs `SUCCEEDED`, 0 `PENDING` |
| BL-47-03 active-work accounting | fixed offline | **Live PASS** — `active_jobs=0`, `clean_terminal=true` |
| BL-47-04 natural stop ≠ incomplete 4h | fixed offline | **Live PASS** — `COMPLETED` / `COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED` (not `SAFE_STOP_4H_TERMINAL_INCOMPLETE`) |
| BL-47-05 campaign report + replay | fixed offline | **Live PASS** — 1 report + zero-source replay |
| BL-47-06 dependency preflight before state | fixed offline | **Live PASS** — `READY` before mutation |
| BL-47-07/08/09 memory/outcome contract | fixed offline | **Live PASS** for adverse path — outcomes kept; dirty only for real safety absence |

---

## 6. Money-usefulness contribution

This is the first live end-to-end confirmation that the post-E.47 machine can:

1. Admit two real graduated PumpSwap markets under the $3k exact-pool front door
   and holder contract.
2. Run two uncompressed 15-minute windows without compression, retry, or budget
   expansion.
3. Capture **truthful collapse memory** (−80.8% and −92.2%) as `DEAD` while
   correctly refusing it as training material when mandatory safety evidence is
   missing.
4. Close the entire ownership graph cleanly so operators can trust terminal
   reports, zero-source replay, and “no orphan work” without manual cleanup.

That is operational learning infrastructure: honest negative outcomes + clean
terminal accounting. It does **not** claim paper profit, clean training memory,
or trade readiness.

---

## 7. What this proof improves

- Resolves the E.46 live terminal/cleanup blockers on the lifecycle-started path.
- Proves discovery work ↔ Scheduler parity under live load.
- Proves campaign terminal report + deterministic report-only replay live.
- Proves natural no-continuation close reports `COMPLETED` with separate dirty
  memory acceptance rather than a false 4h incomplete stop.
- Proves known adverse outcomes survive dirty classification.
- Confirms the Mac/zsh Python entry point is a valid durable executor for the
  canonical pilot (no PowerShell requirement).

---

## 8. What it still does not unlock

- Retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL
- Live trading, wallets, private keys, signing, real funds
- Paid APIs, scoring/ranking/confidence/weighted logic, embeddings/vectors
- Dirty-memory training use
- Automatic restart/successor
- V2-9.7F activation closeout
- V2-9.8 operator activation
- Live `CLEAN_MEMORY` promotion (still blocked by missing exact-target safety
  evidence on this market sample)
- Live `WINDOW_1H` / `WINDOW_4H` continuation (not eligible this cycle)

---

## 9. Functionality Risks / Setbacks / Efficiency Blockers

- **Functionality risk:** both windows lacked valid exact-target safety evidence.
  Until safety coverage is reliable on live collapses, clean adverse memory will
  remain rare even when outcomes are clear. This is a gate, not a bypass
  candidate.
- **Functionality risk:** public Solana RPC returned HTTP 429 on holder lookups;
  Helius Free backup supplied the needed exact-target holder row for one mint.
  Order and fail-closed backup behavior held; primary public RPC remains fragile.
- **Setback:** one PumpPortal migration round returned
  `pumpportal_no_valid_solana_events` (governed round outcome). Supply still
  produced two graduated admits from the mixed path; BL-43-01 sparse migration
  supply remains a standing market condition.
- **Setback:** early DNS/`getaddrinfo` latency delayed discovery start by a few
  minutes on this host; heartbeat lease kept the proof lock alive.
- **Observation:** positive / moderate-continuation clean-memory path was not
  market-exercised this run (both tokens died). Structural repair for that path
  remains offline-proved from E.47; live clean positive memory is still open.
- **Efficiency blocker:** none introduced. ~22 minutes wall clock for two real
  15m windows is the intended uncompressed cost.
- **BL-47-05 residual:** full 6B campaign-object graph for
  `persist_final_campaign_report` remains deferred; this path uses the committed
  `campaign_persistence` terminal-report owner.

---

## 10. Readiness decision

**V2-9.7E pilot proof resolved** for the post-E.47 bounded two-token full-pilot
path: one fresh live attempt completed with authoritative terminal closure,
discovery parity, campaign report + zero-source replay, truthful dirty+DEAD
memory separation, released lock, integrity OK, and zero locked-capability
deltas.

Remaining open work is **not** a re-block of this pilot path:

- live `CLEAN_MEMORY` still depends on complete mandatory safety evidence;
- 1h/4h continuation remains live-unexercised until a cycle qualifies;
- BL-47-05 6B object graph remains deferred;
- BL-43-01 sparse migration supply remains a market condition.

**V2-9.7F was not started.**  
**V2-9.8 was not activated.**

Exact next roadmap step: operator review of this closeout, then
**V2-9.7F — Activation closeout** only when the operator explicitly authorizes it.

---

## 11. Files changed (this lane)

| File | Role |
|---|---|
| `docs/printer-v1-v2-9-7e-post-e47-bounded-full-pilot-proof-closeout.md` | this closeout |
| `docs/printer-v1-v2-9-7e-pilot-blocker-register.md` | minimal live-proof update |

No production code, migrations, tests, policies, or source contracts were
modified. Databases, backups, locks, and logs remain outside Git.
