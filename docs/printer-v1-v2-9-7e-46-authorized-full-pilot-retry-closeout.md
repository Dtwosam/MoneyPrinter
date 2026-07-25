# Printer V1 — V2-9.7E.46 Authorized Full-Pilot Retry Closeout

**Verdict: `V2_9_7E_46_BLOCKED_LIFECYCLE_EVIDENCE`.**

Exactly one separately authorized canonical `FULL_PILOT` was executed from a
durable detached PowerShell executor at real, uncompressed timing. It obtained its
own **fresh** `PILOT_INPUT_READY` bundle (the expired E.46B.1 bundle was not
loaded or reused), performed atomic two-token activation, and ran two genuine
`WINDOW_15M` lifecycles to completion at canonical duration with support-only 5m
evidence, honest memory auditing, a real deterministic report-only replay, a
released proof lock, `integrity_check == ok`, zero foreign-key violations and
**zero** rows in every committed forbidden table.

A PASS is nevertheless **not** claimed, because two required terminal/cleanup
conditions failed on recorded evidence and are preserved unrepaired:
the campaign/run/cycle ownership graph was **not** terminally reconciled, and
**8 scheduler jobs remain `PENDING`** after close. Both are probable code defects
on the *lifecycle-started* path. Per the task's stop conditions they were not
repaired, and no code was modified after execution to make the result pass.

- **Baseline HEAD:** `26e0b224318f0d2625ab74b8d6776b225cb2d7e2`
- **Live execution HEAD:** `26e0b224318f0d2625ab74b8d6776b225cb2d7e2` (identical;
  re-verified inside the executor immediately before invocation; the tracked tree
  was clean before, during and after)
- **Live date:** 2026-07-25
- **Mode:** `FULL_PILOT` (canonical, single)
- **Attempts consumed:** 1 sustained lifecycle attempt

---

## 1. Mandatory preflight

All conditions were verified before any authorization or launch.

| Condition | Result | Evidence |
|---|---|---|
| Exact HEAD | **PASS** | `26e0b224318f0d2625ab74b8d6776b225cb2d7e2` |
| Tracked tree clean | **PASS** | `git status --porcelain --untracked-files=no` empty (untracked proof artifacts only) |
| No active Printer process | **PASS** | sole `python.exe` was the unrelated Google Cloud SDK proxy (PID 15044) |
| No proof lock / campaign lease / scheduler work / lifecycle run | **PASS** | canonical persistent registry holds only `printer_schema_migrations` (41) and `printer_pumpswap_graduated_candidate_registry` (10); no supervision, campaign, scheduler or lifecycle row exists |
| Stable non-hotspot internet | **PASS** | 5/5 TCP:443 handshakes each to `api.dexscreener.com`, `mainnet.helius-rpc.com`, `api.mainnet-beta.solana.com`, `pumpportal.fun`; Wi-Fi (Realtek 8852CE) up at 144.4 Mbps |
| Laptop connected to power | **PASS** | `Win32_Battery.BatteryStatus = 2` (AC), charge 100% |
| Sleep / hibernation will not interrupt | **PASS** | `STANDBYIDLE` = 0 on AC **and** DC; `HIBERNATEIDLE` = 0 on AC; executor additionally held `ES_CONTINUOUS \| ES_SYSTEM_REQUIRED` for the whole window and released it at exit |
| Lid behaviour will not interrupt | **PASS (by operator commitment)** | host is a convertible (`ChassisTypes = 31`); active scheme lid-close action is **2 = Hibernate on AC and DC**. The operator was asked and chose **"leave lid open — no host change"**. No persistent power policy was modified. See §12. |
| No pending Windows restart | **PASS** | CBS `RebootPending` = False; Windows Update agent `RebootRequired` = False. `PendingFileRenameOperations` holds 32 entries, all Microsoft Office ClickToRun update leftovers — not a servicing reboot |
| Adequate disk space | **PASS** | 225.35 GB free on `C:` |
| `PRINTER_HELIUS_API_KEY` present | **PASS (presence only)** | present in process and User scope; never printed, logged or persisted. Runner preflight reported `secret_material_recorded = false` |
| Exact Python imports `printer_v1` from this repository | **PASS on the executed interpreter** | see §2 — the first interpreter choice was corrected before any lifecycle ran |
| All paths fresh and mutually distinct | **PASS** | fresh isolated directory outside the repository; target, backup, rehearsal, report dir, lock, supervision stdout/stderr and executor stdout/stderr are eight distinct paths, none pre-existing |

An additional zero-source rehearsal was run because E.46 `attempt-1` had died on
PowerShell argument quoting: passing the provenance JSON raw reproduced that exact
failure (`Expecting property name enclosed in double quotes`), while
backslash-escaping the inner quotes round-tripped intact. Windows PowerShell 5.1
strips inner double quotes when passing a string to a native executable; escaping
them is an invocation fix and changes no committed contract.

---

## 2. Interpreter blocker on the first launch (no attempt consumed)

The first launch (`e46-full-20260725-26e0b22`, launcher PID **32784**) terminated
after **5.7 s** with:

```
RuntimeError: build_pumpportal_live_transport requires the 'websockets' package;
add websockets to project dependencies before using live transport
```

**Classification: executor-environment / interpreter-selection blocker — not a code
defect, not a provider or network failure.** `websockets>=12.0` **is** a declared
dependency in `pyproject.toml`; the `.venv` interpreter selected in preflight simply
did not have it installed. The preflight condition "the exact Python executable
imports `printer_v1`" was satisfied literally by that interpreter, which is why the
incomplete environment was not caught earlier. This is an operator/preflight error,
not a defect in Printer V1.

Exact state that launch left behind, preserved untouched as evidence:

| Evidence | Value |
|---|---|
| Source requests | **0** — no provider was contacted |
| Failure point | building the PumpPortal migration transport, **before** `run_operational` |
| Supervision | `STARTING` — never terminal; no `terminal_status`, no `first_stop_reason` |
| Campaign / run / cycle | `RUNNING` / `RUNNING` / `PLANNED` (launch metadata only; finalize never ran) |
| Discovery, liquidity, holder, readiness bundle, lifecycle | none |
| Memory, retrieval, decision, position, trade, audit, PnL rows | 0 |
| Proof lock | left on disk, lease expired `01:06:46Z` |
| `integrity_check` / `foreign_key_check` | `ok` / 0 |
| Canonical persistent registry | unmutated |

This is structurally the same class as the E.46 `attempt-1` PowerShell-JSON failure,
which that closeout recorded as "an invocation/preflight issue" that "did not consume
an attempt" — with the one difference that an isolated attempt DB and lock were
created here, so the identity and paths were burned and could not be reused.

Because the task authorized exactly one attempt with no retry or successor, the
decision was **escalated to the operator rather than assumed**. The operator chose
one corrected launch with a wholly fresh identity. The corrected interpreter was
verified first with **zero external requests**: Python 3.12.10, `websockets` 16.1,
`printer_v1` resolved from `src\printer_v1`, migration transport constructible, and
`assert_readiness_source_contract_preflight()` returning `READY` /
`external_requests: 0` / `secret_material_recorded: false`.

No retry, restart or successor was created **after any governed terminal result**.

---

## 3. Durable execution

The full pilot was not run inside Claude's command executor or any short-lived
sandbox process. A temporary launcher outside the repository was launched detached.

| Property | Value |
|---|---|
| Launch mechanism | `Start-Process powershell.exe -PassThru -WindowStyle Hidden` (detached, not a piped child) |
| Launcher location | temporary, outside the repository, in the session scratchpad |
| Arguments | `-NoProfile -NonInteractive -ExecutionPolicy Bypass -File <launcher-b.ps1>` |
| Retained child PID | **32188** (`powershell.exe`); canonical child `python.exe` **28484** |
| stdout / stderr | redirected to fresh external `executor-stdout.txt` / `executor-stderr.txt` (stderr ended empty) |
| Executor timeout | **none** |
| Timing | canonical real timing; no compression |
| Fixture adapters | none (`_FORBIDDEN_PRODUCTION_TIMING_KEYS` guard intact) |
| Retry / restart / successor | none |
| Monitoring | by retained PID and by terminal artifacts (`executor-done.marker`, `terminal-result.json`) |

Process lifetime:

- `DURABLE_EXECUTOR_START_UTC` = `2026-07-25T01:09:49.4350323Z`
- `DURABLE_EXECUTOR_END_UTC` = `2026-07-25T01:32:01.0339090Z`
- Executor lifetime **22 min 11.6 s**; canonical runner wall time **1326.8 s**;
  `PYTHON_EXIT_CODE = 0`; marker `EXIT=0`

The executor terminated because the canonical runner finished — nothing killed it.

**Exact committed canonical invocation.** The committed entry point
`scripts/v2_9_7e_14_two_token_operational_pilot.py` was used verbatim; no parallel
runner was reconstructed or invented. The script's `mode` is the runner default
`FULL_PILOT`. Every argument is a documented flag of that committed surface:

```
--operator-approved
--persistent-source-db operator-runs\v2-9-7e-46\canonical-graduated-registry.sqlite3
--target-db / --backup-db / --restore-rehearsal-db / --report-dir / --lock-path
--stdout-log / --stderr-log
--execution-id e46-full-20260725-26e0b22-b
--selection-seed e46-full-20260725-26e0b22-b
--git-provenance-json <committed git_provenance capture>
--evaluated-at / --cycle-cutoff
```

---

## 4. Fresh identities and artifact paths

No E.46 / E.46A / E.46B / E.46B.1 identity was reused.

- authorization / execution `e46-full-20260725-26e0b22-b`
- campaign `e46-full-20260725-26e0b22-b-campaign`
- run (campaign) `e46-full-20260725-26e0b22-b-campaign-run`
- cycle `e46-full-20260725-26e0b22-b-cycle`
- configuration `e46-full-20260725-26e0b22-b-configuration`
- report `e46-full-20260725-26e0b22-b-report`
- selection seed `e46-full-20260725-26e0b22-b`
- factory run (lifecycle) `496ec5f5-de50-4d71-a3d2-3f534221ae6b`
- immutable export `pilot-export:e46-full-20260725-26e0b22-b:attempt.sqlite3`,
  10 rows, provenance hash `c81b6d8d1f8f132e3f8cc7c329a10c2034f43f32a80e5d6d070924596e997c0c`

Artifacts (isolated, outside the repository, never entering any persistent corpus):
`C:\Users\dtwof\PrinterPilot\E46FULL\e46-full-20260725-26e0b22-b\` —
`attempt.sqlite3`, `attempt.backup.sqlite3`, `reports\`, `provenance.json`,
`executor-preflight.json`, `executor-stdout.txt`, `executor-stderr.txt`,
`terminal-result.json`, `executor-done.marker`, `durable-executor.pid`,
`launcher-start.json`.

Target preparation: `PILOT_TARGET_READY`; target and backup byte-identical
(`target_hash == backup_hash == f3ff2d900cb20bd325a0a2deb733432547de78bc198644d7b1bb567b9503c439`);
restore rehearsal passed on a disposable copy that was then removed; no active
lease; `persistent_unchanged = true`.

Final attempt-DB SHA-256:
`a29db0d9f3049b31a266ee6d28ed98708cfc896e6519954a57162cd80fa28ef3`.
All evidence in this closeout was read from a **disposable copy** opened `mode=ro`;
the retained E.46B.1 proof DB was also only copied, and its SHA-256 is still
`d74e7dd5827f4798dc3c2800d0ff4e25247ac3907d9c36bbfc31c4e075287eae` — unmutated.

---

## 5. Complete discovery, liquidity, holder and rejection ledger

### 5.1 Discovery

Bounded direct-migration discovery ran **3** PumpPortal rounds at canonical timing
(`-supply-migration-r0/r1/r2`). Round r1 returned
`pumpportal_no_valid_solana_events` — a governed round outcome, not a retry.
Four confirmed-LATEST PumpSwap signature→pool resolutions followed, taking the
attempt registry from **10 → 14** rows.

All eight discovery work rows reached a terminal `SUCCEEDED` state:
`DISCOVERY_PUMPFUN_LATEST` (`DIRECT_COMPLETE`), `DISCOVERY_IDENTITY_MERGE`
(`MERGE_COMPLETE`), `DISCOVERY_ORIGIN_VERIFICATION` (`ORIGIN_COMPLETE`),
`DISCOVERY_PUMPSWAP_CONFIRMATION` (`PUMPSWAP_COMPLETE`),
`DISCOVERY_FIXED_ELIGIBILITY_GATES` (`GATES_COMPLETE`),
`DISCOVERY_UNIFORM_SELECTION` (`SELECTION_COMPLETE`),
`DISCOVERY_TRACKING_HANDOFF_SLOT_1/2` (`HANDOFF_COMPLETE`).

Newly confirmed graduations this cycle:

| Mint | Exact PumpSwap pool | Graduation block time |
|---|---|---:|
| `ESMUESNFtbiWREn2V1JPHg2LkrTS4MUrMvLDZRVVpump` | `J2YJMXPmrrCuRCv4Sdum7NG8LCMkCoDP9JCR3qNt328X` | 1784941859 |
| `zqoFGzHQKLGaH7J1c11XnWSYh3hosrruXL962dDpump` | `5rkVVrdaTPS3m2Nd1FLTC23MR6pEXHcouH7uMwb2ANdF` | 1784941920 |
| `5AybvnVxNVwkH46oAoWkBgkPjxAG4SCSmCzD3aDYpump` | `HN1wVGp3AaPKz8ebW1TiiADUPykmtrd4ZKScN1U6H5ZF` | 1784942093 |
| `haDVMmfTseSnFRiwnjcYDx9kYond3HfqcPaGNmkpump` | `F58ku7fQksa1ABiwiKEfUoiCBp8STJY48AcqqB2BLkN4` | 1784942156 |

### 5.2 Exact-pool liquidity front door and rejection ledger

Six governed exact-pool DexScreener liquidity requests over the combined
(LATEST ∪ PERSISTED) seeded-uniform pool. The `$3,000` floor was never weakened.

| # | Mint | Exact PumpSwap pool | Fresh liquidity | Result |
|---|---|---|---:|---|
| 1 | `5AybvnVxNVwkH46oAoWkBgkPjxAG4SCSmCzD3aDYpump` | `HN1wVGp3AaPKz8ebW1TiiADUPykmtrd4ZKScN1U6H5ZF` | **$219,346.86** | Eligible → **SELECTED** |
| 2 | `haDVMmfTseSnFRiwnjcYDx9kYond3HfqcPaGNmkpump` | — | — | **Source failure** (`dexscreener_malformed_fixture`, `MISSING_CRITICAL_DATA`) — fail-closed |
| 3 | `zqoFGzHQKLGaH7J1c11XnWSYh3hosrruXL962dDpump` | `5rkVVrdaTPS3m2Nd1FLTC23MR6pEXHcouH7uMwb2ANdF` | **$292,516.70** | Eligible → **SELECTED** |
| 4 | `Gds9MSe4H8SMcPwd5sqMx1n8ak1nkQRCWnQftKyHpump` | `HSoMcpnQLnC6h4HvXVfhKZqqYhGPRrvYegCdDBv3sSMJ` | $30.76 | Rejected below `$3,000` |
| 5 | `4yxNHzN7E9iPBiYVKWrbo5r4CSVkiAxVm1PNaw6gpump` | `AeaiCGUsEs6BUat3c8PCyokKypi11asoZah9asjr5nSJ` | $1,788.63 | Rejected below `$3,000` |
| 6 | `23NGxdJi5ovKCTtW3FktqxznV4JFpeEoJxXBpWNypump` | `BArrguk94BQu1F6bEJqs7ZsnebiBH5ZeFdPScptf8EvX` | $1.62 | Rejected below `$3,000` |

Admission summary: `candidate_universe` 2, **`candidate_cap` 3**,
`graduated_admitted` 2, `graduated_available` 2, eligibility rule
`GRADUATION_ONLY`, `latest_vs_non_latest` = `{LATEST_GRADUATED: 2,
NON_LATEST_GRADUATED: 0}`, `staged_pending_discovery_this_cycle` 0, and
`channel_counts.PUMPSWAP_CONFIRMED` 2 with every enrichment channel 0.
Blocked channels (`GECKO_TRENDING_TOP`, `PUMPPORTAL_MIGRATION_FEED`,
`SOLANA_TRACKER_TRENDING_TOP`) all recorded `SKIPPED_BLOCKED_CONTRACT`.

`candidate_cap = 3` is the **first live confirmation** of the E.46B.2 repair —
E.46B.1 ran the same shape at `candidate_cap = 2`.

### 5.3 Holder evidence funnel

Both candidates used exactly the committed fixed order GoPlus → public Solana RPC →
Helius Free backup. No rotation, racing or retry. Six durable
`printer_holder_evidence_attempts` rows:

| Candidate | GoPlus (PRIMARY) | Public RPC (PRIMARY) | Helius Free (BACKUP) | Holder result |
|---|---|---|---|---|
| `5Aybvn…pump` | complete, `HOLDER_CONCENTRATION_UNKNOWN` (safety context) | `solana_rpc_rate_limited` (HTTP 429) | complete | `HOLDER_CONCENTRATION_HEALTHY`, eligible |
| `zqoFGzH…pump` | complete, `HOLDER_CONCENTRATION_UNKNOWN` (safety context) | `solana_rpc_rate_limited` (HTTP 429) | complete | `HOLDER_CONCENTRATION_HEALTHY`, eligible |

Both holder verdicts are `VALID_EXACT_TARGET_HOLDER_EVIDENCE` from `helius_free`.
The public-RPC 429s were recorded as transport/rate failures, **not** target
mismatches — correct failure precedence. Two `printer_holder_maturation_work` rows
are `COMPLETED` with `maturation_threshold_state = UNPROVEN_DISABLED`.

---

## 6. `PILOT_INPUT_READY` evidence and provenance composition

One immutable row in `printer_pilot_input_readiness_bundle`, created fresh by this
execution. **The expired E.46B.1 bundle was not loaded or reused.**

| Field | Value |
|---|---|
| `readiness_id` | `e46-full-20260725-26e0b22-b-campaign-run:e46-full-20260725-26e0b22-b-cycle:pilot-input` |
| `readiness_state` | `PILOT_INPUT_READY` |
| Slot A mint / pool | `5AybvnVxNVwkH46oAoWkBgkPjxAG4SCSmCzD3aDYpump` / `HN1wVGp3AaPKz8ebW1TiiADUPykmtrd4ZKScN1U6H5ZF` |
| Slot A liquidity / route | `$219,346.86` / `GRADUATION_NATIVE` |
| Slot B mint / pool | `zqoFGzHQKLGaH7J1c11XnWSYh3hosrruXL962dDpump` / `5rkVVrdaTPS3m2Nd1FLTC23MR6pEXHcouH7uMwb2ANdF` |
| Slot B liquidity / route | `$292,516.70` / `GRADUATION_NATIVE` |
| Provenance | `{"latest": "LATEST_GRADUATED", "persisted": "LATEST_GRADUATED"}` |
| Selection seed | `e46-full-20260725-26e0b22-b` |
| Git provenance identity | `26e0b224318f0d2625ab74b8d6776b225cb2d7e2` |
| Configuration hash | `e4b8529eb90d41af1651ac1711bbeae2fb0675b041b66959a118bd13d1c120c1` |
| Bundle hash | `b08415062156e7885e01e43e40aff3c4f26ad063551d532be1a850e9e6a71549` |
| Created / expires | `2026-07-25T01:09:53.731115Z` / `2026-07-25T01:19:53.731115Z` |

**Provenance composition: `LATEST_GRADUATED` + `LATEST_GRADUATED`** — a lawful
composition, recorded truthfully per token. Neither token was relabelled to satisfy
a partition slot. As in E.46B.1, every `$3,000+`-capable candidate this cycle was
LATEST and every PERSISTED reserve was far below the floor ($1.62–$1,788.63), so
the pre-E.46B mandatory mixed quota would have blocked on supply that genuinely
existed.

As in E.46B.1, `created_at` and both `*_liquidity_observed_at` carry the campaign
evaluation **reference** time supplied at launch, not the instant the provider
answered; actual freshness is proven by the durable governed response receipts at
`01:16:23Z`.

---

## 7. Atomic activation, windows, continuation and 5m support

**Atomic two-token activation:** two `printer_memory_factory_campaign_token_slots`
rows created together at `01:09:53.731115Z`, selection batch
`origin-activated:e46-full-20260725-26e0b22-b-cycle`, `selected_token_count = 2`,
`eligible_pool_size = 2`, two `printer_tracking_queue` rows on `TRACK_NORMAL`.
Exact two-or-none behaviour held.

**Factory run** `496ec5f5-de50-4d71-a3d2-3f534221ae6b`: `window_kind = WINDOW_15M`,
started `01:16:33.253372Z`, finished `01:31:45.929263Z`,
`run_status = SAFE_STOPPED`, `stop_reason = SAFE_STOP_4H_TERMINAL_INCOMPLETE`,
`db_mode = PROOF_ONLY`, `snapshot_mode = FIRST_15M_CYCLE`.

### Windows started and completed

| Window | Token | Opened | Closed | Duration | Snapshots | Result |
|---|---|---|---|---:|---:|---|
| `WINDOW_15M` #1 | `5Aybvn…pump` | `01:16:33.793Z` | `01:31:41.077Z` | **907 s** | 9 | closed, `DIRTY_MEMORY` |
| `WINDOW_15M` #2 | `zqoFGzH…pump` | `01:16:34.276Z` | `01:31:45.753Z` | **911 s** | 9 | closed, `DIRTY_MEMORY` |

Both windows ran the full canonical ~900 s with no compression. 18 run steps
(16 `SNAPSHOT` + 2 `WINDOW_CLOSE`) all `SUCCEEDED`.

**`WINDOW_1H`: not started. `WINDOW_4H`: not started.** Zero rows in
`printer_memory_factory_campaign_windows`. Both 15m windows closed
`DIRTY_MEMORY` / `DO_NOT_TRAIN`, so the natural disposition did not qualify for
selective continuation and **continuation was correctly not forced**. The 4h phase
therefore never started, which is exactly what `SAFE_STOP_4H_TERMINAL_INCOMPLETE`
records (`_four_hour_terminal_validation`: `phase_state = NOT_STARTED`, no source
failure, no budget breach → `SAFE_STOPPED`).

**Support-only 5m evidence:** two `printer_micro_events` rows were lawfully
created, each `window_5m_support_role = SUPPORT_ONLY_NOT_MAIN_EVIDENCE`:

| Pair | Mint | `micro_event_state_label` | Memory gate | Liquidity | Data quality |
|---|---|---|---|---:|---|
| 1 | `5Aybvn…pump` | `MICRO_EVENT_UNKNOWN` | `MICRO_EVENT_SUPPORT_EVIDENCE` | $1,337.59 (`LIQUIDITY_DANGEROUS`) | `MISSING_CRITICAL_DATA` / `PARTIAL` |
| 2 | `zqoFGzH…pump` | `NO_MICRO_EVENT` | `MICRO_EVENT_IGNORE` | $324,448.66 (`LIQUIDITY_DEEP`) | `MISSING_CRITICAL_DATA` / `PARTIAL` |

Neither became main outcome evidence, replaced 15m, or triggered continuation.

---

## 8. Memory quality and outcome results

Both windows were audited by `lane_e2q` and closed **`DIRTY_MEMORY`**,
`data_quality_label = MISSING_CRITICAL_DATA`, `do_not_train = 1`,
`outcome_label = OUTCOME_UNKNOWN`, rejection reason
`window data_quality_label is dirty: 'MISSING_CRITICAL_DATA'`. Zero clean memory
was created and zero promotion occurred. No memory was fabricated and no
provider-evidence gap was mislabelled.

Per-context data quality was identical in shape for both windows —
`chart_volatility`, `liquidity_exit` and `trading_flow` were `CLEAN_DATA` /
`COMPLETE`; `chain_heat`, `market`, `micro_event` and `safety` were
`MISSING_CRITICAL_DATA` / `PARTIAL` (all `CONTEXT_FRESH`,
`CONTEXT_TARGET_MATCH`, no blocking freshness reason). Both windows recorded
`source_coverage_pending_fields = ["liquidity_lock_or_burn_label",
"known_risk_flag_label"]`.

The two windows are materially different and both dispositions are honest:

**Window 1 — `5Aybvn…pump`: a genuine rug/fast pump-dump, correctly refused.**
`price_change_percent −99.986%`, `trend_structure_label TREND_PARABOLIC_DOWN`,
`volatility_label VOLATILITY_EXTREME`, `candle_path_label PATH_ROUND_TRIP`
(`round_trip_percent 100.0`), `held_to_15m_result_label HELD_TO_15M_DEAD`,
`micro_event_state_label FAST_PUMP_DUMP`, `rug_risk_label RUG_RISK_HIGH`,
`safety_status_label SAFETY_BLOCKED_FOR_15M_MEMORY`. Exact-pool liquidity
collapsed from **$219,346.86 at admission to $1,337.59 by window close**.
`clean_memory_context_ready = false`; remaining blockers
`raw_safety_context_label=SAFETY_UNKNOWN`, `raw_safety_action_label=UNKNOWN`,
`SAFETY_COMPOSITE_HOLDER_CONCENTRATION_LABEL`,
`NO_VALID_EXACT_TARGET_SAFETY_EVIDENCE`. This is the machine correctly declining
to learn from a token that rugged inside its first 15 minutes.

**Window 2 — `zqoFGzH…pump`: near-clean, blocked on one label.**
`clean_memory_context_ready = **true**`, `evidence_blockers = []`,
`safety_status_label SAFETY_ACCEPTABLE_FOR_15M_MEMORY_ONLY`,
`rug_risk_label RUG_RISK_ACCEPTABLE_FOR_15M`,
`liquidity_state_label LIQUIDITY_CONTEXT_ACCEPTABLE`, `trend_structure_label
TREND_UP`, `micro_event_state_label FAST_MICRO_PUMP`. Its single remaining
blocker was `held_to_15m_result_label = HELD_TO_15M_UNKNOWN`, and the window-level
`MISSING_CRITICAL_DATA` still forced `DIRTY_MEMORY`.

Both windows recorded `downstream_unlocks` all **false**: `retrieval`,
`paper_decisions`, `buy_sell_hold`, `positions`, `trades`, `audits`, `pnl`.

---

## 9. Source and operation accounting

**Every governed source request counted once.** 52 durable
`printer_source_requests` rows, ids contiguous `1..52`, 52 distinct ids.
50 distinct non-null `request_key` values plus 2 rows with a `NULL` key
(`solana_rpc` / `pumpfun_origin_transaction_reference`, ids 21–22) — there are **no
duplicate request identities**.

**Responses plus failures reconcile to requests exactly:**
**46 responses + 6 failures = 52 requests**; 0 requests with neither, 0 with both.

| Source | Request kind | Count |
|---|---|---:|
| dexscreener | `dexscreener_fresh_profiles` (locator) | 1 |
| dexscreener | `pair_market_snapshot` | 24 |
| pumpportal | `pumpfun_migration_stream` | 3 |
| pumpswap | `pumpswap_signature_pool_resolution` | 4 |
| goplus | `safety_reference` | 4 |
| solana_rpc | `holder_concentration_reference` | 4 |
| solana_rpc | `pumpfun_origin_transaction_reference` | 2 |
| helius_free | `holder_concentration_reference` | 4 |
| coingecko | `broad_market_context` | 2 |
| jupiter_quote | `paper_quote_realism` | 4 |
| **Total** | | **52** |

The six failures: `pumpportal_no_valid_solana_events` ×1,
`dexscreener_malformed_fixture` ×1, `solana_rpc_rate_limited` (HTTP 429) ×4.
No paid API, arbitrary RPC, endpoint rotation, provider racing or hidden retry.
Jupiter quotes were used for paper exit-realism evidence only, as permitted.

### Campaign governed-request count equals distinct durable request identities

`printer_holder_campaign_operation_ledgers` records
**`governed_requests = 20`**, computed at the pre-lifecycle campaign boundary.
The durable pre-lifecycle request identities are exactly ids **1–20**
(locator 1 + migration 3 + PumpSwap verification 4 + front-door snapshots 6 +
holder funnel 6 = 20). Ids 21–52 belong to the lifecycle stage, keyed under the
factory `run_id`.

**Difference = 0.** This is the live confirmation demanded by E.46B.2 §9;
E.46B.1 recorded 22 against 21 (`+1`).

| Field | Value |
|---|---|
| Operation ceiling | 45 |
| Governed requests | 20 |
| Underlying transport operations | 22 |
| Zero-transport operations | 9 (tracked in a separate ledger column, never represented as a source request) |
| Reserved snapshot operations | 2 |
| Reserved snapshot-completion operations | 4 |
| Deadline | `2026-07-25T05:24:53.731115Z` (evaluated + 15,300 s envelope) |

Operation ceilings and reservations remained intact and were never approached.

---

## 10. Replay, terminal metadata, cleanup and integrity

**Deterministic report-only replay — genuinely executed.** Unlike E.46B.1 (where
`replay_deterministic` was a structural constant on a pre-lifecycle path), this run
had `lifecycle_started = true`, so the runner invoked `pilot_report_only_replay`
against the real factory run and compared two loads:
`replay_deterministic = true`, `replay_new_source_calls = **0**`.

**Integrity:** `PRAGMA integrity_check` → **`ok`**; `PRAGMA foreign_key_check` →
**0 violations**; 41 schema migrations applied; 84 tables.

**Supervision and cleanup:** `execution_status = TERMINAL`,
`terminal_status = GOVERNED_SAFE_STOP`,
`first_stop_reason = SAFE_STOP_4H_TERMINAL_INCOMPLETE`,
started `01:09:59.270741Z`, finished `01:32:00.604342Z`,
`one_proof_lock_released = true` (lock file absent),
`pending_or_running_run_steps = 0`, `running_jobs_after_stop = 0`,
`restart_created = false`, `successor_created = false`, restore-rehearsal DB
removed. Exactly one supervision row exists.

**Persistent corpus untouched:** the canonical graduated registry still holds
**10** rows (SHA-256
`44d9395bc886eadbf1c0152ff16ffe8d4ed28bb67c8c548bcd9697354fa82f43`); the four new
confirmations stayed isolated in the attempt database.

### 10.1 FAILED — campaign/run/cycle not terminally reconciled

Required: "campaign/run/cycle and all started windows terminally reconciled."

| Record | State | `first_terminal_cause` | `terminal_at` |
|---|---|---|---|
| campaign `…-b-campaign` | **`RUNNING`** | `null` | `null` |
| run `…-b-campaign-run` | **`RUNNING`** | `null` | `null` |
| cycle `…-b-cycle` | **`PLANNED`** | `null` | `null` |

The runner reported `terminal_metadata_reconciliation: {"reconciled": false}`.
`_reconcile_pre_lifecycle_terminal_metadata` runs only when
`lifecycle_started` is false (`two_token_operational_pilot_runner.py:844`), on the
stated assumption that "A started lifecycle owns its own terminal reconciliation."
The recorded evidence shows the started lifecycle did **not** reconcile the
campaign-level ownership graph: supervision is `TERMINAL` / `GOVERNED_SAFE_STOP`
with zero active work, while `RUNNING/RUNNING/PLANNED` metadata survives. This is
the exact failure mode E.46B item 9 exists to prevent, on the one path item 9 does
not cover. The started `WINDOW_15M` windows themselves *are* closed and audited.

### 10.2 FAILED — 8 scheduler jobs still `PENDING` after close

Required: "zero pending/running jobs and run steps after close."

Run steps are clean (18/18 `SUCCEEDED`, 0 pending/running). Scheduler jobs are not:

| Status | Count | Jobs |
|---|---:|---|
| `SUCCEEDED` | 18 | snapshot / window-close work |
| `CANCELLED` | 2 | `TRACK_NORMAL_FIRST_15M` `window15m:` jobs for both tokens |
| **`PENDING`** | **8** | `DISCOVERY_REFRESH`: `DISCOVERY_PUMPFUN_LATEST`, `DISCOVERY_IDENTITY_MERGE`, `DISCOVERY_ORIGIN_VERIFICATION`, `DISCOVERY_PUMPSWAP_CONFIRMATION`, `DISCOVERY_FIXED_ELIGIBILITY_GATES`, `DISCOVERY_UNIFORM_SELECTION`, `DISCOVERY_TRACKING_HANDOFF_SLOT_1`, `DISCOVERY_TRACKING_HANDOFF_SLOT_2` |

All eight were scheduled at `01:09:53.731115Z` and carry no `last_error`. Their
corresponding `printer_discovery_work` rows all reached terminal `SUCCEEDED` with
explicit terminal causes (§5.1) — so the **work** completed while the **jobs** were
never transitioned out of `PENDING`. The runner's
`running_jobs_after_stop = 0` is accurate but counts only `RUNNING`, so it does not
observe this. No job was left `RUNNING`, and nothing was executing at close.

**Neither defect was repaired.** No production code was modified during or after
this task.

---

## 11. Forbidden-delta proof

The runner's authoritative `forbidden_deltas` — the committed
`_FORBIDDEN_DELTA_TABLES` set — was **all zero**:

| Table | Rows |
|---|---:|
| `printer_memory_retrieval_queries` | 0 |
| `printer_memory_retrieval_matches` | 0 |
| `printer_paper_decisions` | 0 |
| `printer_paper_decision_audits` | 0 |
| `printer_paper_positions` | 0 |
| `printer_paper_trade_events` | 0 |
| `printer_paper_trade_audits` | 0 |
| `printer_paper_audit_reports` | 0 |
| **Total forbidden rows** | **0** |

Independently verified by scanning all 84 tables. No PnL or profit table exists in
the schema. No BUY/SELL/HOLD decision was produced (zero decision rows), and both
windows recorded `downstream_unlocks` all false. No retrieval, decision, position,
trade, paper audit or PnL capability was activated.

`printer_paper_quote_evidence` holds 4 rows and is **not** forbidden: it is a
counted evidence table written by the 15m window close for entry/exit realism, and
`AGENTS.md` explicitly permits the Jupiter quote API for paper simulation. It
unlocked nothing.

No wallet, private key, transaction signing, live trading or fund movement was
introduced. No policy, gate, source endpoint, retry ceiling, lifecycle duration,
liquidity floor, holder gate, continuation law or memory-quality rule was weakened.

---

## 12. Money-usefulness contribution

This is the first time the canonical machine has been driven end-to-end from live
graduated discovery through admission, atomic activation and two completed real
15-minute memory windows in one governed execution. It produced two concrete,
honest results rather than a manufactured one: a token that **rugged −99.99% inside
its own first window** (liquidity $219,346.86 → $1,337.59) was captured, labelled
`DIRTY_MEMORY` / `DO_NOT_TRAIN` and refused as training material; and a second,
genuinely healthy token reached `clean_memory_context_ready = true` with acceptable
safety and rug labels, blocked from clean memory only by
`held_to_15m_result_label = HELD_TO_15M_UNKNOWN` and the window-level
`MISSING_CRITICAL_DATA`. That second window is the closest the program has come to
real clean memory, and it names the exact remaining gap.

It also confirmed E.46B.2 live: charged accounting reconciles to zero difference and
the restored `candidate_cap = 3` held. No profit, trade quality or clean-memory
claim is made — zero clean memory was created.

---

## 13. Functionality Risks / Setbacks / Efficiency Blockers

- **Probable code defect (preserved, not repaired):** campaign/run/cycle terminal
  reconciliation does not happen on the `lifecycle_started` path (§10.1). Any
  future lifecycle proof will leave `RUNNING/RUNNING/PLANNED` metadata behind.
- **Probable code defect (preserved, not repaired):** 8 `DISCOVERY_REFRESH`
  scheduler jobs remain `PENDING` after close although their discovery work rows are
  terminal (§10.2). `running_jobs_after_stop` cannot detect this because it counts
  only `RUNNING`.
- **Functionality risk:** `WINDOW_1H` and `WINDOW_4H` continuation, and the
  `COMPLETED` 4h terminal path, remain **live-unproven**. This cycle legitimately
  did not qualify, so continuation was correctly not forced — but the continuation
  code has still never executed live.
- **Setback:** four of seven window contexts (`chain_heat`, `market`,
  `micro_event`, `safety`) were `MISSING_CRITICAL_DATA` / `PARTIAL` for **both**
  tokens, which alone forces `DIRTY_MEMORY` regardless of market behaviour. Both
  windows also reported the same
  `source_coverage_pending_fields = ["liquidity_lock_or_burn_label",
  "known_risk_flag_label"]`. Until that context coverage improves, clean memory may
  be unreachable even for a healthy token — window 2 is direct evidence of this.
- **Setback:** no campaign report row and an empty `reports\` directory. Zero rows
  in `printer_memory_factory_campaign_reports`; a report artifact appears not to be
  written on a `SAFE_STOPPED` pre-4h-terminal run. Reported as observed; not
  investigated, as this lane is execution and closeout only.
- **Operational setback:** one authorized launch was lost to an interpreter that
  lacked a **declared** dependency (§2). Future preflight must verify the executing
  interpreter satisfies the declared dependency set, not merely that it imports
  `printer_v1`. The corrected launcher now asserts this in-executor before invoking.
- **Environment risk (accepted by the operator):** lid-close remains **Hibernate**
  on AC and DC. Idle sleep cannot fire and the executor held a wake lock, but a lid
  close would still have killed the run. Mitigated by operator commitment, not by
  configuration; no persistent power policy was changed.
- **Observation:** the public Solana RPC rate-limited **all four** holder lookups
  again; every holder verdict came from the Helius Free backup. The committed fixed
  order held, but primary-RPC holder reliability remains weak, as in
  E.20–E.24 and E.46B.1.
- **Efficiency blocker:** none introduced. The run cost 22 minutes of real wall
  clock for two completed 15m windows, which is the intended uncompressed cost.

---

## 14. Verdict

**`V2_9_7E_46_BLOCKED_LIFECYCLE_EVIDENCE`.**

Earned live: fresh graduated discovery, exact PumpSwap confirmation, exact-pool
liquidity checks, partition-flexible selection, holder evidence, a fresh immutable
`PILOT_INPUT_READY` bundle, atomic two-token activation, two completed canonical
`WINDOW_15M` lifecycles, lawful support-only 5m evidence, honest memory auditing,
a genuinely executed deterministic zero-source replay, exact source accounting
reconciling to zero difference, released proof lock, `integrity_check == ok`, zero
FK violations, zero forbidden rows, and no restart or successor.

Not earned: the canonical lifecycle terminated `SAFE_STOPPED` /
`SAFE_STOP_4H_TERMINAL_INCOMPLETE` rather than `COMPLETED` — honest, because the
natural disposition did not qualify for continuation and continuation was not
forced — and two required terminal/cleanup conditions failed on recorded evidence:
the campaign/run/cycle graph was not terminally reconciled (§10.1) and 8 scheduler
jobs remain `PENDING` after close (§10.2). A PASS may not be inferred from
readiness or from a partial lifecycle, so none is claimed.

## 15. Roadmap and operator state

**V2-9.7E remains active and blocked**, with exact unresolved first causes:

1. `SAFE_STOP_4H_TERMINAL_INCOMPLETE` — continuation never qualified because both
   15m windows closed `DIRTY_MEMORY` under `MISSING_CRITICAL_DATA` context coverage.
2. Missing terminal reconciliation of campaign/run/cycle on the lifecycle-started
   path.
3. 8 `DISCOVERY_REFRESH` scheduler jobs left `PENDING` after a governed terminal.

**V2-9.7F is NOT ready and was not started.** It should not be considered until at
least items 2 and 3 are repaired under their own narrow, source-grounded repair
lane with focused proof, and a subsequent authorized pilot demonstrates a
terminally reconciled governed close.

No retry, restart or successor was created after the governed terminal, and no code
was modified after execution to make the result pass. All permanent Printer V1
locks remain in force: Solana memecoin only, paper only, no wallets, private keys,
funds or live execution, no paid APIs, no scoring/ranking/confidence/weighted logic,
no Source Governor or Central Scheduler bypass, no dirty memory used for retrieval
or decisions, and no BUY/SELL/HOLD, positions, trade events, paper audits or PnL
unlock.
