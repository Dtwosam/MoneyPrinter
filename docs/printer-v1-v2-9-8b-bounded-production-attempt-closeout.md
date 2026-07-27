# Printer V1 V2-9.8B.9 — One Authorized Bounded Production Attempt Closeout

## Verdict

```text
V2_9_8B_9_BOUNDED_PRODUCTION_ATTEMPT_FAIL
```

This lane authorized and executed **exactly one** canonical public production
run. The repaired discovery path productively filled graduated supply and
selected two market-eligible tokens, then failed with a durable first cause of
`OPERATIONAL_CAMPAIGN_FAILED:IntegrityError` before `WINDOW_15M` lifecycle
collection started. That is an implementation / integrity / supervision-path
failure under the lane outcome rules—not a market-supply block and not a pure
source outage.

No retry, rerun, restart, successor, code repair, tag, or push was performed.
V2-9.8B is **not** complete.

---

## 1. Baseline and authorization

| Item | Value |
|---|---|
| Repository | `/Users/Dtwo1/Developer/MoneyPrinter` |
| Expected HEAD | `267766c` |
| Resolved HEAD | `267766c963f29608203ae89397bd785a24d23ac2` |
| HEAD message | `Review V2-9.8B discovery repair production readiness` |
| Tracked tree pre-run | clean |
| Authorization | This prompt only — one `run --operator-approved` |

Must-read stack used: `AGENTS.md`, clean master / post-RC / memory-factory /
memory-growth v2 anchors, discovery productivity closeout, discovery-repair
production readiness review (`V2_9_8B_8_DISCOVERY_REPAIR_PRODUCTION_READY`),
blocked-supply reporting closeout.

### Pre-run gate (immediately before execution)

| Check | Result |
|---|---|
| `preflight-only` | `V2_9_8_OPERATIONAL_PREFLIGHT_READY` |
| Migration count | 43 (`043_graduated_market_floor_state.sql`) |
| Integrity | ok |
| Foreign-key violations | 0 |
| Active-work counts | all 0 |
| Active lease | none (prior campaign terminal/released) |
| Tracked Git tree | clean |
| `OPERATIONAL_GRADUATED_SUPPLY_KWARGS` | exact E.46B contract in force |
| Source ceiling | 45 |
| `status` | prior campaign terminal `BLOCKED_INSUFFICIENT_GRADUATED_POOL` |

Gate decision: **proceed with one run**.

---

## 2. Exact execution evidence

### Identities

| Identity | Value |
|---|---|
| Execution ID | `20260727T001520Z-d513e21260b5` |
| Campaign ID | `20260727T001520Z-d513e21260b5-campaign` |
| Configuration ID | `20260727T001520Z-d513e21260b5-configuration` |
| Run ID | `20260727T001520Z-d513e21260b5-campaign-run` |
| Cycle ID | `20260727T001520Z-d513e21260b5-cycle` |
| Supervision ID | `20260727T001520Z-d513e21260b5-supervision` |
| Report ID | `20260727T001520Z-d513e21260b5-report` |
| Artifact root | `/Users/Dtwo1/PrinterOperations/v2-9-8/20260727T001520Z-d513e21260b5/` |

### Timing and terminal cause

| Field | Value |
|---|---|
| Start (UTC wall) | `2026-07-27T00:15:20Z` |
| Process return (UTC wall) | `2026-07-27T00:22:24Z` |
| Approx. wall duration | ~424 s |
| Campaign created_at | `2026-07-27T00:15:20.913110+00:00` |
| Final terminal_at (after same-execution closeout) | `2026-07-27T00:24:13.429887+00:00` |
| First terminal cause | **`OPERATIONAL_CAMPAIGN_FAILED:IntegrityError`** |
| Lifecycle started | **false** |
| `WINDOW_15M` windows created | **0** |
| Restart created | false |
| Successor created | false |

### Command shape (unchanged code/config)

```text
python -m printer_v1.operator_cli.operational_memory_factory_command run --operator-approved
```

Preserved production kwargs (shared constant):

```text
collection_rounds=3
max_candidates=5
settle_seconds=6.0
reverify_on_transient=True
reverify_settle_seconds=6.0
front_door_max_candidates=6
run_locator=True
```

Policy: `WINDOW_15M` only, token capacity 2, long windows locked, 5m support-only.

### Public process surface vs durable fault

The public command stdout/stderr surface collapsed to:

```json
{
  "status": "OPERATIONAL_COMMAND_BLOCKED",
  "error_type": "IntegrityError",
  "source_calls": 0,
  "restart_created": false,
  "successor_created": false
}
```

That surface under-reports campaign source activity. Durable evidence is
authoritative:

- holder operation ledger: `governed_requests=18`, `underlying_transport_operations=19`, ceiling `45`
- terminal report after same-execution closeout: `campaign_source_calls=18`
- `printer_source_requests` in the execution window: 20 COMPLETE rows by kind
  (see funnel)

Initial automatic terminalization attempted during the process wrote
`terminal-summary.json` with:

- first cause `OPERATIONAL_CAMPAIGN_FAILED:IntegrityError`
- closure errors: `cleanup:OperationalError:database is locked` and
  `report:TerminalClosureError:... database is locked`
- reconciliation records skipped (`CampaignOwnershipError`) while still RUNNING

Per lane rules, **no rerun**. The existing canonical same-execution owners were
allowed to finish **this** execution only:

1. `cleanup_campaign_supervision` → `cleanup_completed=true`, `lease_released=true`
2. `reconcile_campaign_terminal` → campaign/run/cycle `TERMINAL_FAILED`
3. `write_campaign_terminal_report` → report hash
   `707dd25543c2b15c6982e104dc9e4a4ebfe75de0bccc77d0184cd793e196b781`

The hardcoded V2-9.8B.1 `recover-orphan` path targets a different historical
execution identity and was **not** used.

---

## 3. Discovery funnel

### Migration rounds (configured = 3)

| Round request key | Source | Status |
|---|---|---|
| `v2-9-7e-44-migration-r0` | pumpportal / `pumpfun_migration_stream` | COMPLETE |
| `v2-9-7e-44-migration-r1` | pumpportal / `pumpfun_migration_stream` | COMPLETE |
| `v2-9-7e-44-migration-r2` | pumpportal / `pumpfun_migration_stream` | COMPLETE |

Configured collection rounds: **3**. Completed migration stream requests: **3**.

### PumpSwap confirmations and newly persisted graduated candidates

PumpSwap `pumpswap_signature_pool_resolution` requests this run: **4** (all COMPLETE).

Newly first-observed graduated registry mints this run:

| Mint | Role after market floor |
|---|---|
| `4G5y3xjDB5F8QCcAuCkqMXiWjCjuuRPnUoqm9y9bpump` | below floor `$0.74` |
| `UUdfUfhkqWEQK9wqADgQTQSbE4qpNkNaeCZdjPPpump` | proven `$23,959.78` → **selected** |
| `7tKKxaDcb7w1J9aLz5mFkSypxJjQKHaDfAEYZZxGpump` | proven `$8,132.78` → **selected** |
| `EgjSyM3uYPW6kSxKHqFPW68qE2hE5n3mqCguNQBApump` | below floor `$2.41` |

Prior registry rows re-enriched this run (not newly graduated this cycle):

| Mint | Floor result |
|---|---|
| `CrR3AB6W9v2RV9btV9Egqsdij3jXNUSJba9dqKAqpump` | below floor `$1,693.44` |
| `4hi84NkokbcM6G1LFQ9wB7HgjGrFxh4qXwAc16chpump` | below floor `$8.16` |

Registry size after run: **6** graduated confirmed mints.

### Locator

| Item | Value |
|---|---|
| Locator request | 1 × dexscreener `dexscreener_fresh_profiles` (`v2-9-7e-44-locator`) COMPLETE |
| Locator-only graduation | none observed as graduated authority (locator remains rediscovery-only) |

### Market floor / DexScreener / cooldown

| Item | Value |
|---|---|
| DexScreener pair_market_snapshot | **6** COMPLETE |
| Below-floor cooldown skips | **0** (table was empty pre-run; first post-043 market pass populated state) |
| Market-eligible (LIQUIDITY_PROVEN ≥ $3,000) | **2** |
| Below-floor with 1h cooldown recorded | **4** (`cooldown_until=2026-07-27T01:15:20.912977+00:00`) |

### Holder funnel

Holder ledger (authoritative campaign total):

```text
operation_ceiling = 45
governed_requests = 18
underlying_transport_operations = 19
zero_transport_operations = 9
reserved_snapshot_operations = 2
reserved_snapshot_completion_operations = 4
```

Holder/safety source activity observed in window:

- goplus safety_reference × 2 COMPLETE
- solana_rpc holder_concentration_reference × 1 COMPLETE (and one HTTP **429**
  failure recorded, then backup path)
- helius_free holder_concentration_reference × 1 COMPLETE
- solana_rpc pumpfun_origin_transaction_reference × 2 COMPLETE

### Selected tokens (exactly 2)

| Slot | Mint | Pool | Liquidity | Token/pair rows | Token state |
|---:|---|---|---:|---|---|
| 1 | `UUdfUfhkqWEQK9wqADgQTQSbE4qpNkNaeCZdjPPpump` | `7PZL3Fo1bHSkKiSymZsRHjhX4swn1n9WHvupQ4qQcnFR` | $23,959.78 | token 18 / pair 22 | SELECTED |
| 2 | `7tKKxaDcb7w1J9aLz5mFkSypxJjQKHaDfAEYZZxGpump` | `GocsVH4qcQfPsHqgCDiZPWRmq1Q1FBZn2Qv7BVKbgEix` | $8,132.78 | token 19 / pair 23 | SELECTED |

Supporting durable readiness:

- `printer_pilot_input_readiness_bundle` row present (`PILOT_INPUT_READY`)
- both selected tokens labeled provenance `LATEST_GRADUATED` in the bundle
- selection batches assembled (`selected_count=2`)
- discovery work graph succeeded through both tracking handoffs
  (`DISCOVERY_TRACKING_HANDOFF_SLOT_1/2` → `HANDOFF_COMPLETE`)
- tracking queue rows 16 and 17 `QUEUED` for TRACK_NORMAL

### Discovery work summary

8 discovery work rows for this campaign, all `SUCCEEDED`:

```text
DISCOVERY_PUMPFUN_LATEST
DISCOVERY_IDENTITY_MERGE
DISCOVERY_ORIGIN_VERIFICATION
DISCOVERY_PUMPSWAP_CONFIRMATION
DISCOVERY_FIXED_ELIGIBILITY_GATES
DISCOVERY_UNIFORM_SELECTION
DISCOVERY_TRACKING_HANDOFF_SLOT_1
DISCOVERY_TRACKING_HANDOFF_SLOT_2
```

---

## 4. Source-budget accounting

### By stage (window `2026-07-27 00:15:20` … `00:22:30`)

| Source | Kind | Count |
|---|---|---:|
| pumpportal | pumpfun_migration_stream | 3 |
| pumpswap | pumpswap_signature_pool_resolution | 4 |
| dexscreener | dexscreener_fresh_profiles | 1 |
| dexscreener | pair_market_snapshot | 6 |
| goplus | safety_reference | 2 |
| solana_rpc | holder_concentration_reference | 1 |
| helius_free | holder_concentration_reference | 1 |
| solana_rpc | pumpfun_origin_transaction_reference | 2 |
| **Total request rows** |  | **20** |

### Versus ceiling 45

| Metric | Value |
|---|---:|
| Admission ceiling | 45 |
| Governed requests (ledger / report) | 18 |
| Underlying transport operations | 19 |
| Headroom remaining (45 − 18 governed) | 27 |
| Ceiling breach | **no** |

Multi-round discovery used previously idle budget productively (prior blocked run
used only 4 governed ops).

One holder Solana RPC 429 occurred; it did not terminalize the campaign as a
source block. First durable terminal cause remained IntegrityError after
selection/handoff.

---

## 5. Selected tokens or blocker

**Selected tokens:** two (see §3).

**Blocker / first fault after selection:**
`OPERATIONAL_CAMPAIGN_FAILED:IntegrityError` during the post-selection /
lifecycle-entry path. No `WINDOW_15M` campaign windows were created. No token
snapshots for the selected mints were produced.

This is **not** `BLOCKED_INSUFFICIENT_GRADUATED_POOL`. Discovery repair achieved
the two-token market-eligible selection that the prior production run lacked.

---

## 6. 15m memory outcome

| Item | Result |
|---|---|
| Lifecycle started | false |
| Campaign windows | 0 |
| `WINDOW_15M` snapshots for selected tokens | none |
| Clean memory created this attempt | **absent** |
| Dirty memory created this attempt | **absent** |
| 1h/4h/12h/24h | not enabled |

Memory growth did not occur on this attempt.

---

## 7. Terminal safety

### After same-execution canonical closeout

| Check | Result |
|---|---|
| Campaign state | `TERMINAL_FAILED` |
| Run state | `TERMINAL_FAILED` |
| Cycle state | `TERMINAL_FAILED` |
| Supervision | `TERMINAL` / `FAILED` |
| First cause preserved | `OPERATIONAL_CAMPAIGN_FAILED:IntegrityError` |
| Cleanup completed | yes (`2026-07-27T00:24:13.429887+00:00`) |
| Lease released | yes (same timestamp) |
| Non-terminal campaigns/runs/cycles/supervision | **0** |
| Active campaign scheduler work | 0 |
| Restart / successor | false / false |
| SQLite integrity | **ok** |
| Foreign-key violations | **0** |

### Post-close public modes

| Mode | source_calls | scheduler_runtime_calls | database_writes | Notes |
|---|---:|---:|---:|---|
| `status` | 0 | 0 | 0 | shows this campaign terminal FAILED |
| `report-only` | 0 | 0 | 0 | replays this campaign report; `campaign_source_calls=18` |

Downstream unlocks in report: all **false** (retrieval, decisions, positions,
trades, audits, buy/sell/hold, PnL).

### Historical locked capability counts (unchanged class)

```text
printer_memory_retrieval_queries = 10
printer_memory_retrieval_matches = 0
printer_paper_decisions = 2
printer_paper_positions = 0
printer_paper_trade_events = 0
printer_paper_trade_audits = 0
printer_paper_audit_reports = 1
```

No new retrieval activation or financial unlock.

---

## 8. Money-usefulness contribution

What this attempt proved in the live operational path:

1. **Discovery productivity repair works under production kwargs** — three
   migration rounds completed; four new graduated confirmations; six market
   enrichments; two exact-pool ≥ $3,000 eligible tokens selected.
2. **Idle budget was spent on real confirmations** (18 governed vs prior 4), still
   under ceiling 45.
3. **Floor-state durability activated** — four below-floor mints now carry 1h
   cooldowns so future campaigns can skip re-taxing dead pools.
4. **Honest failure boundary held** — IntegrityError did not invent memory,
   positions, or BUY; no restart/successor was created.

What it did **not** deliver:

- any `WINDOW_15M` collection or clean memory growth
- a clean successful governed terminal of a full memory-factory lifecycle

---

## 9. What remains locked

- Retrieval activation
- Paper decisions / BUY / SELL / HOLD
- Paper positions, trades, audits, PnL
- Live wallets, private keys, signing, real funds
- Paid APIs
- Scoring / ranking / confidence / weighted logic
- Embeddings / vectors
- Automatic retry / restart / successor
- Raising admission ceiling 45
- Lowering `$3,000` or two-token requirements
- 1h / 4h / 12h / 24h production windows
- Claim that V2-9.8B is complete

---

## 10. Functionality Risks / Setbacks / Efficiency Blockers

| Item | Classification | Notes |
|---|---|---|
| Post-selection `IntegrityError` before lifecycle | **Primary blocker** | First durable cause; blocks clean lifecycle terminal despite successful two-token selection |
| Heartbeat vs main terminalization DB lock | Residual setback | Initial cleanup/report failed with `database is locked`; required same-execution owner re-entry after process exit |
| Public exception surface reports `source_calls: 0` | Reporting residual | Under-states real campaign source use; ledger/report totals remain authoritative |
| Holder Solana RPC 429 | Transient source friction | Recovered via backup path; not the first terminal cause |
| Floor cooldown empty on first post-043 run | Expected | All six market calls spent; cooldown now populated for next authorized attempt only after IntegrityError repair |
| Both selected tokens `LATEST_GRADUATED` | Observation | Readiness bundle still formed; not proven as the IntegrityError root without a dedicated audit |
| Generic `recover-orphan` still identity-hardcoded to older orphan | Efficiency blocker for operators | Same-execution closeout used supervision/reconciliation/report owners instead |

---

## 11. Outcome classification rationale

| Candidate verdict | Why not / why |
|---|---|
| `..._PASS` | No clean successful governed lifecycle terminal; IntegrityError first cause |
| `..._BLOCKED_MARKET_SUPPLY` | Two market-eligible tokens **were** selected |
| `..._BLOCKED_SOURCE` | Sources largely completed; 429 was not the first terminal cause |
| **`..._FAIL`** | **IntegrityError + incomplete automatic terminalization path** |

---

## 12. Exact next lane recommendation

```text
V2-9.8B.10 — Post-Selection Lifecycle IntegrityError Audit and Repair
```

Recommended scope (documentation/audit first, then minimal repair only if
operator-approved):

1. Reproduce the exact IntegrityError site on the post-selection /
   pilot-input-ready → lifecycle-entry path using the retained execution
   evidence (`20260727T001520Z-d513e21260b5`) without a new production campaign.
2. Repair only the confirmed integrity / lifecycle-entry defect.
3. Harden terminalization so heartbeat contention cannot leave RUNNING state when
   the main process has already faulted (if still open after audit).
4. Improve failure surface honesty so campaign source totals are not reported as
   zero when the durable ledger is non-zero.
5. **Do not** authorize another production run until that repair is closed PASS
   and a fresh readiness gate says so.

Do **not** mark V2-9.8B complete. Do **not** unlock retrieval or financial
capabilities.

---

## 13. Stop conditions honored

- Exactly one production `run`
- No retry / rerun after failure
- Only same-execution canonical closeout owners used after orphan residue
- No code or configuration edits
- No broad test suite
- No tag
- No push
- Closeout document only committed
- Database / locks / logs / external operation artifacts **not** committed
- V2-9.8B complete claim **not** made

---

## 14. Files / commit

| Item | Value |
|---|---|
| Closeout document | `docs/printer-v1-v2-9-8b-bounded-production-attempt-closeout.md` |
| Commit message | `Close V2-9.8B bounded production attempt` |
| Code changes | none |
| DB/runtime artifacts committed | none |
