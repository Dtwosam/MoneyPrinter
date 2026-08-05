# Printer V1 — V2-9.8B `WINDOW_15M` End-to-End Readiness Unified Repair Closeout

**Date:** 2026-08-05
**Lane:** `V2-9.8B — WINDOW_15M End-to-End Operational Readiness Unified Repair`
**Branch:** `agent/v2-9-8b-window-15m-end-to-end-readiness-unified-repair`
**Baseline HEAD:** `7a4152bb90b14317513bb10879ee3861410270c7`
**Design:** `docs/printer-v1-v2-9-8b-window-15m-end-to-end-readiness-unified-repair-design.md`
**Audit:** `docs/printer-v1-window-15m-a-to-z-operational-readiness-audit-2026-08-05.md`

## Final verdict

`V2_9_8B_WINDOW_15M_END_TO_END_READINESS_UNIFIED_REPAIR_PASS`

## Money-usefulness contribution

This repair stops one-use `WINDOW_15M` authorizations from being permanently consumed by deterministic adapter/transport construction defects after campaign mutation. It also makes terminal exception reporting action-local (source requests and DB deltas), confines clean-memory promotion to the current closed window, and separates lifecycle PASS from clean-memory PASS so a truthful operational outcome can be read without conflating accounting success with memory quality.

## B1–B8 / E1–E3 closure matrix

| Item | Status | Proof |
|---|---|---|
| B1 complete composition not validated before mutation | `CLOSED_WITH_PROOF` | `window_15m_concrete_composition.run_window_15m_concrete_composition_preflight` in wrapper (pre-staging) and `build_activation_preflight` (pre-campaign); focused tests for PASS / raise / None |
| B2 Dex→Gecko unknown-liquidity no default transport | `CLOSED_WITH_PROOF` | `run_bounded_unknown_liquidity_backup` defaults to `build_geckoterminal_token_pools_transport`; focused once-call proof |
| B3 Gecko→Dex mirror defect | `CLOSED_WITH_PROOF` | Default `build_dexscreener_mint_batch_transport`; focused once-call proof |
| B4 factory presence without concrete output | `CLOSED_WITH_PROOF` | Shared `require_concrete_adapter` / `require_concrete_transport` / `require_factory_output`; invalid factory blocks before backup write; lifecycle primary/fallback/pre-close seams validate |
| B5 mutation before composition readiness | `CLOSED_WITH_PROOF` | Wrapper blocks before staging/marker/child; child preflight runs concrete composition before artifacts/campaign identity |
| B6 exception source-call incomplete holder ledger | `CLOSED_WITH_PROOF` | `action_local_terminal_truth` + public exception envelope; focused truth test after source request |
| B7 exception mutation not actionable | `CLOSED_WITH_PROOF` | Baseline + table deltas + `database_mutation_status`; envelope no longer hardcodes `UNKNOWN_ON_EXCEPTION` when baseline exists |
| B8 clean-memory global historical scan | `CLOSED_WITH_PROOF` | `run_e2z_pipeline(..., candidate_window_ids=...)`; `_execute_close` passes exact `window_id`; explicit-scope test proves unrelated window not promoted |
| E1 exact 900s public composition proof | `CLOSED_WITH_PROOF` | `tests/test_v2_9_8b_exact_public_composition_900_logical_seconds.py` with `_window_seconds=900.0`, zero network |
| E2 current-run clean episodes/fingerprints | `CLOSED_WITH_PROOF` | Same proof asserts two `CLEAN_MEMORY` episodes and two fingerprint rows; terminal `clean_memory_outcome` |
| E3 independent lifecycle vs clean-memory verdicts | `CLOSED_WITH_PROOF` | Terminal fields `operational_lifecycle_pass`, `clean_memory_outcome_pass`, `clean_memory_outcome` |

## Composition-builder matrix (18)

| label | source | request kind |
|---|---|---|
| pump_origin_solana_rpc_transport | solana_rpc | pump_origin_acquisition |
| secondary_discovery_http_transport | secondary_http | secondary_enrichment |
| pumpswap_migration_pool_confirmation | pumpswap | pumpswap_onchain_pool_confirmation |
| pumpswap_account_batch_transport | solana_rpc | pumpswap_pool_account_batch |
| dexscreener_fresh_profiles_discovery | dexscreener | dexscreener_fresh_profiles |
| dexscreener_mint_batch_discovery | dexscreener | candidate_market_batch |
| geckoterminal_fresh_nomination | geckoterminal | geckoterminal_new_pool_discovery |
| geckoterminal_token_pools_discovery | geckoterminal | candidate_market_batch |
| unknown_liquidity_backup_dex_to_gecko | geckoterminal | candidate_market_batch |
| unknown_liquidity_backup_gecko_to_dex | dexscreener | candidate_market_batch |
| lifecycle_exact_pair_dexscreener_primary | dexscreener | exact_pair_snapshot |
| lifecycle_exact_pair_geckoterminal_fallback | geckoterminal | exact_pair_snapshot |
| preclose_coingecko_market_chain | coingecko | broad_market_context |
| preclose_goplus_safety | goplus | safety_reference |
| preclose_jupiter_entry_quote | jupiter_quote | paper_quote_realism |
| preclose_jupiter_exit_quote | jupiter_quote | paper_quote_realism |
| preclose_solana_rpc_holder_primary | solana_rpc | holder_concentration_reference |
| preclose_helius_holder_backup | helius_free | holder_concentration_reference |

All 18 construct with zero I/O in preflight (`external_requests=0`, `database_writes=0`).

## Files changed

### New

- `src/printer_v1/operator_cli/window_15m_concrete_composition.py`
- `src/printer_v1/operator_cli/action_local_terminal_truth.py`
- `tests/test_v2_9_8b_window_15m_end_to_end_readiness_unified_repair.py`
- `docs/printer-v1-window-15m-a-to-z-operational-readiness-audit-2026-08-05.md`
- `docs/printer-v1-v2-9-8b-window-15m-end-to-end-readiness-unified-repair-design.md`
- `docs/printer-v1-v2-9-8b-window-15m-end-to-end-readiness-unified-repair-closeout.md`

### Modified

- `src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py` — pre-consumption composition + auto-select interpreter match
- `src/printer_v1/operator_cli/operational_memory_factory_command.py` — child preflight composition; action-local baseline; exception truth; clean-memory outcome fields
- `src/printer_v1/discovery/permanent_discovery_availability.py` — both unknown-liquidity defaults + factory validation
- `src/printer_v1/operator_cli/one_command_15m_factory.py` — factory output validation; current-window E2Z scope
- `src/printer_v1/operator_cli/exact_pair_source_redundancy.py` — fallback factory validation
- `src/printer_v1/operator_cli/lane_k_e2z_pipeline_wiring.py` — `candidate_window_ids` scope + fingerprint wiring
- `tests/test_v2_9_8b_exact_public_composition_900_logical_seconds.py` — clean-memory + independent verdict assertions

## Focused test results

Command:

```bash
.venv/bin/python -m pytest \
  tests/test_v2_9_8b_window_15m_end_to_end_readiness_unified_repair.py \
  tests/test_v2_9_8b_exact_public_composition_900_logical_seconds.py \
  -q
```

Result: **13 passed**.

Includes:

- composition matrix PASS zero-I/O
- builder None / raise blocks
- wrapper composition block before staging (auth unconsumed)
- Dex→Gecko and Gecko→Dex backup once
- invalid injected factory no backup write
- action-local exception truth after request
- explicit E2Z scope isolation
- independent verdict helper
- integrated 900 logical-second public composition success

## Integrated positive proof (E1–E3)

`tests/test_v2_9_8b_exact_public_composition_900_logical_seconds.py`

Observed outcomes on controlled-clock disposable Migration-052 DB:

- `OPERATIONAL_CAMPAIGN_TERMINAL` / `COMPLETED` / `campaign_pass=true`
- `operational_lifecycle_pass=true`
- `clean_memory_outcome_pass=true`
- two `WINDOW_15M` windows: `WINDOW_CLOSED`, `PARTIAL_MEMORY`, `CLEAN_DATA`, `do_not_train=0`, evidence span ≥900s
- two current-run `CLEAN_MEMORY` episodes
- two canonical fingerprint rows
- zero unrelated promotion
- zero network (`urllib.request.urlopen` not called)
- report-only replay zero source/writes, byte-stable

Integrated negative (composition):

- wrapper builder failure: no staging/application/marker/child; authorization unconsumed
- required builder None/raise: composition `BLOCKED` before campaign identity

## Authoritative DB identity (read-only)

Before and after all tests (unchanged):

| Fact | Value |
|---|---|
| path | `data/printer_v1.sqlite3` |
| SHA-256 | `ecf0557cf213b44b51f840983e5472a53777f609dee650580d1844e7b01ac2bb` |
| size | `68067328` |
| inode | `1230526` |
| mtime_ns | `1785925095953652677` |
| migration | `52 / 052_memory_observation_eligibility_layers.sql` |
| integrity | `ok` |
| FK violations | `0` |
| sidecars | none |

Incident evidence preserved (consumed auth, failed execution graph) — not deleted or rewritten.

## Source / Scheduler / forbidden capability deltas

This repair introduces **no** live provider calls and **no** authoritative DB writes. Offline proofs use disposable DBs only. Locked capabilities remain false:

- no retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL
- no wallet/signing/funds/live execution
- no paid API, scoring/ranking/confidence, embeddings/vectors
- no `WINDOW_1H`/`4H`/`12H`/`24H` activation; `WINDOW_5M_MICRO_EVENT` support-only
- no Source Governor / Central Scheduler bypass

## What this improves

1. Deterministic composition defects are caught before authorization consumption and before campaign mutation.
2. Both opposite-source unknown-liquidity backups have concrete default transports.
3. Injected factory seams reject `None`/disabled/transportless production adapters before stage writes.
4. Public exception envelopes report action-local source IDs and table deltas when attributable.
5. Operational close promotes only the newly closed window.
6. Terminal reports separate lifecycle PASS from clean-memory PASS with exact IDs.

## What remains locked / live uncertainty

- Live provider availability, rate limits, and market supply remain uncertain by nature.
- Wrapper package expiry remains operator-enforced (not code-enforced) as previously audited.
- No new authorization or live `WINDOW_15M` run is authorized by this closeout.
- Selective 1h and multi-hour windows remain locked.

## Functionality Risks / Setbacks / Efficiency Blockers

| Class | Note |
|---|---|
| Risk | Composition preflight constructs real transport closures (zero execute); if a builder starts requiring network or secrets at construction time, preflight will block until that builder is fixed to be lazy. |
| Risk | Explicit E2Z scope skips global E2Y authority (`NOT_APPLICABLE_EXPLICIT_WINDOW_SCOPE`); backlog/maintenance still uses `candidate_window_ids=None`. |
| Setback | Offline fixture adapters lack `enabled`/`transport`; validators accept non-None fixture owners while still hard-failing production-shaped unusable adapters. |
| Efficiency | Concrete composition re-invokes builders inside preflight for strict validation after `assert_runtime_dependency_preflight` — small fixed cost, zero I/O. |

## What this repair still does not guarantee

- A live market will always supply four eligible candidates.
- Providers will always return clean data.
- Operator will not re-use a consumed authorization (one-use marker still owns that).
- Clean-memory PASS on every future live run (honest dirty outcomes remain valid with lifecycle PASS).

## Test / proof command summary

### Narrow focused + public + wrapper + 900s

```bash
.venv/bin/python -m pytest \
  tests/test_v2_9_8b_window_15m_end_to_end_readiness_unified_repair.py \
  tests/test_v2_9_8a_public_operational_command.py \
  tests/test_v2_9_8b_window_15m_one_shot_wrapper.py \
  tests/test_v2_9_8b_exact_public_composition_900_logical_seconds.py \
  -q
```

Result: **70 passed**.

### Final broad regression (canonical closeout command)

```bash
.venv/bin/python -m pytest \
  tests/test_v2_9_8b_window_15m_end_to_end_readiness_unified_repair.py \
  tests/test_v2_9_8b_exact_public_composition_900_logical_seconds.py \
  tests/test_v2_9_8b_window_15m_one_shot_wrapper.py \
  tests/test_post_lane10_lane_k_e2z_pipeline_wiring.py \
  tests/test_post_rc_lane_e2z_clean_memory_creation.py \
  tests/test_v2_9_8b_token_slot_id_exact_public_composition.py \
  tests/test_v2_9_8b_permanent_discovery_availability.py \
  tests/test_v2_9_8b_pre_authorization_migration_ledger_drift_guard.py \
  -q
```

Result after action-local schema repair: **342 passed, 24 subtests passed**.

### Count reconciliation

| Report | Suite composition | Count |
|---|---|---|
| Initial handoff “183 passed” | wrapper + Lane K + focused unified-repair only (partial closeout subset) | 183 |
| Prior full broad closeout | same 8-file command as above | **340 passed, 24 subtests** |
| Current full broad closeout | same 8-file command + 2 new action-local schema tests | **342 passed, 24 subtests** |

The “183” figure was never the full broad command; it was a narrower intermediate subset. The authoritative broad regression for this lane is the 8-file command above (340 → 342 after the two schema-drift proofs).

## Follow-up: action-local terminal truth schema drift

**Status:** `CLOSED_WITH_PROOF`
**Baseline for this follow-up:** `42781cbbb36727fcc5e892adb1ab9df16a5511cc`

Remotely verified defect: `action_local_terminal_truth.py` selected non-existent columns
`run_status` / `stop_reason` / `cycle_status` / `supervision_status`.

Repair:

- Read only Migration-052 canonical columns:
  - run: `run_state`, `first_terminal_cause`, `terminal_at`
  - cycle: `cycle_state`, `first_terminal_cause`, `terminal_at`
  - supervision: `supervision_state`, `terminal_status`, `first_terminal_cause`,
    `cleanup_completed_at`, `lease_released_at`
- Stable output keys preserve those durable names.
- Original exception remains `first_terminal_cause`.
- Optional state-read faults return `UNKNOWN_NOT_ATTRIBUTABLE` without raising a
  secondary exception or wiping source IDs / table deltas.
- Mutation inventory expanded with pre-lifecycle discovery/campaign/holder tables
  (`printer_discovery_reserve_layers`, `printer_exact_market_states`,
  `printer_source_health`, `printer_source_rate_limits`,
  `printer_external_source_operations`, `printer_discovery_work`,
  `printer_memory_factory_campaign_scheduler_work`, campaign reports/objects,
  holder evidence attempts and maturation work).

Focused proofs:
`ActionLocalTruthTests.test_canonical_campaign_graph_state_columns_and_envelope`
and `test_state_read_failure_is_unknown_not_attributable`.

## Commit

Initial unified repair:

Message: `Repair WINDOW_15M end-to-end readiness`
SHA: `42781cbbb36727fcc5e892adb1ab9df16a5511cc`

Schema-drift follow-up:

Message: `Repair action-local terminal truth schema`

Not pushed. Untracked incident operator-run directories preserved outside the commit.
