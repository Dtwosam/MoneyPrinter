# Printer V1 — Sep-3 Cycle-2 Duplicate-Transport / NO-PAIR Acquisition Blocker Audit

Status: **CLOSED PASS as readiness/forensic audit only**

Lane:

`SEP-3 CYCLE-2 DUPLICATE-TRANSPORT / NO-PAIR ACQUISITION BLOCKER — READINESS / FORENSIC AUDIT`

Verdict:

`V2_9_8B_SEP3_CYCLE2_DUPLICATE_TRANSPORT_NO_PAIR_BLOCKER_AUDIT_PASS`

This audit does not implement a repair. It does not modify `src/`, tests,
migrations, or the authoritative DB. It does not run Printer. It does not work
the separate four-token `50 -> 118` budget repair.

---

## 1. Baseline

| Item | Value |
|---|---|
| Branch | `assistant/v2-9-8b-later-cycle-mint-market-replay-repair` |
| Audit HEAD | `83d6bc1fb89a03a547b59d5419e74eb6303a4b29` |
| Authorized Sep-3 execution HEAD | `26d7b91bb5f115ad816b3cd632b5036d07b82b0e` (ancestor; no production-code drift) |
| DB | `data/printer_v1.sqlite3` |
| DB SHA-256 | `575984caa484b12f4bb5fca0a06cdf7865adeb03b5f16874406fb0c1a73daa6e` |
| Consumed authorization | `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260903T121923Z_202fbea1` permanently non-reusable |
| Execution | `20260903T124259Z-a9b0fb4b2622` |
| Campaign | `20260903T124259Z-a9b0fb4b2622-campaign` |
| Campaign run | `20260903T124259Z-a9b0fb4b2622-campaign-run` |
| Cycle 1 | `20260903T124259Z-a9b0fb4b2622-cycle` |
| Proposed Cycle 2 | `20260903T124259Z-a9b0fb4b2622-cycle-2` (never admitted) |
| Attempt | `pre-admission:...:7a8bc1ec-a4bf-459c-873b-c4ec80bd75b5:c0002` |
| Factory run | `7a8bc1ec-a4bf-459c-873b-c4ec80bd75b5` |

Historical repair commit still in ancestry: `041e2550ec2ec090e45eec2d8de45f6a0c1e84f0`
(`fix: preserve cooperative mint-market completion state`).

Governing prior evidence:

- `docs/printer-v1-v2-9-8b-auth-202fbea1-sep3-consumed-4-2-2-standard4h-post-run-forensic-closeout.md`
- `docs/printer-v1-v2-9-8b-four-token-standard4h-per-token-request-ceiling-wiring-repair-audit.md`
- `docs/printer-v1-v2-9-8b-auth-12a7ea61-campaign-closeout.md`
- `docs/printer-v1-v2-9-8b-later-cycle-duplicate-transport-repair-closeout.md`

Budget-audit independence `CYCLE2_FINDING_INDEPENDENT` is **preserved**.

---

## 2. Exact Cycle-2 timeline

Acquisition start (attempt created / evaluated):
`2026-09-03T12:47:58.183244Z`

Anchors from that start:

| Opportunity | Due | What actually ran |
|---|---|---|
| initial | `12:47:58Z` | claims 1–9, `12:47:58Z`–`12:49:22Z` |
| +600 refresh | `12:57:58.183244Z` | job `3762` claimed `13:01:19Z` (late because Cycle-1 15m close was occupying the factory), then **FAILED** |
| +1200 | `13:07:58Z` | **not executed** |
| +1800 | `13:17:58Z` | **not executed** |
| deadline +2400 | `13:27:58.183244Z` | **not reached** |

Lawful opportunities executed: **initial + first refresh start**. Remaining +1200 / +1800 / deadline unused.

### Initial cooperative quanta (opportunity 0)

Scheduler job `3718`
`PRE_ADMISSION_DISCOVERY_SELECTION` created `12:48:05Z`, claimed/finished
`13:01:12.854290Z`, `SUCCEEDED`.

| Claim | Time | Source | Kind |
|---|---|---|---|
| 1 | 12:47:58 / 12:48:05 | 4714, 4715 | DexScreener locator; GeckoTerminal new pools |
| 2–7 | 12:48:07–12:49:00 | 4716–4722 | GeckoTerminal `candidate_market_batch` liquidity backups; **4721** `geckoterminal_rate_limited` / `STALE_DATA` |
| 8 | 12:49:07 | 4723 | PumpSwap protocol batch |
| 9 | 12:49:15 / 12:49:22 | **4724** | Pump migration live-tail `getSignaturesForAddress` `before=HEAD` |
| 10 | 13:00:57 / 13:01:04 | **4755** | DexScreener `c0002-mint-batch-r1` (2 due mints, **distinct** from Cycle-1 batches) |
| 11 | 13:01:05 | — | yield |
| 12 | 13:01:12 | 4756 recorded on attempt evidence | `MARKET_DISCOVERY`; disposition `BLOCKED_INSUFFICIENT_ELIGIBLE_CANDIDATE_POOL` |

Attempt terminal:

- `attempt_state = NO_PAIR`
- `first_terminal_cause = DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE`
- `terminal_at = 2026-09-03T13:01:12.854290Z`
- `consumed_cycle_id = null`
- attempt items: **empty** (no Cycle-2 freeze slots)

Observed identities at disposition (not admitted): Cycle-1 pair
`B33y...` / `J1yo...` plus `CLd4...`, `NEW37...`, `GbYw...`.

### First refresh (ordinal 1)

Wait
`prelifecycle-refresh-wait:...:cycle-2:1`

Work
`prelifecycle-refresh-work:...:cycle-2:1`

Job `3762` `DISCOVERY_REFRESH`:

- `scheduled_for = 12:57:58.183244Z` (+600)
- created/started `13:01:19.459529Z` (already due)
- finished `13:01:20.160265Z` `FAILED`
- `last_error = PRE_LIFECYCLE_REFRESH_INTERNAL_INVARIANT:SIX_UNIT_STAGE_EVIDENCE_DUPLICATE_TRANSPORT:DUPLICATE_TRANSPORT_IDENTITY`

Request **4756** at `13:01:19.472304Z`:
`...:c0002-refresh-1-pump-migration-page-live-tail`

Refresh channel rotation for ordinal 1 selects Pump first
(`_FRESH_CHANNEL_ORDER[0] = direct_pump_finalized_live_tail`). Cooperative
refresh runs only that first channel.

Acquisition still had ~26 minutes and two later refresh ordinals when this
duplicate fired. Cycle-1 15m→1h work continued afterward and was **not**
stopped by Cycle-2. No factory `PROOF_DEADLINE`.

---

## 3. Exact duplicate pair

Colliding canonical transport identity:

```text
(
  DIRECT_PUMP_NOMINATION,
  solana_rpc,
  restored_pump_migration_signature_page,
  getSignaturesForAddress,
  1,
  pump_migration_withdraw_authority_page,
  27m9co5M6RLMFdHXzJz6ktUvN9Dm3GAmttmNrqvnEnjN|before=HEAD
)
```

| Field | Original (Cycle-2 initial) | Duplicate (refresh 1) |
|---|---|---|
| source_request_id | **4724** | **4756** |
| source_response_id | **4315** | **4347** |
| source_failure_id | none | none |
| request_key | `...:c0002-migration-page-live-tail` | `...:c0002-refresh-1-pump-migration-page-live-tail` |
| stage | `DIRECT_PUMP_NOMINATION` | same |
| source_name | `solana_rpc` | same |
| governed_request_kind | `restored_pump_migration_signature_page` | same |
| method | `getSignaturesForAddress` | same |
| within_request_ordinal | 1 | 1 |
| target_category | `pump_migration_withdraw_authority_page` | same |
| target_identity | `27m9co...|before=HEAD` | same |
| response SHA-256 | `1ba6f403db0a1438ade56488d66d4a5cb79d9892d5fcee5bd8f17f2bd67d1337` | **identical** |
| payload | empty signatures, `normalized_rows=0` | **byte-identical** |
| timestamps | `12:49:22.357302Z` | `13:01:19.472304Z` |
| Scheduler | claim 9 / job 3718 lineage | job **3762**, refresh_ordinal **1** |

Payload comparison: **BYTE_IDENTICAL**.

Canonical transport identity: **SAME**.

Governed request keys: **DIFFERENT**.

Cycle-1 request `4690` (`...-migration-page-live-tail`, no `:c0002`) uses the
same canonical tuple but a **different** response hash. Cycle-2 initial `4724`
completed, so Cycle-1 and Cycle-2 six-unit owners are cycle-scoped. The
collision is **inside Cycle 2**: initial live-tail vs refresh-1 live-tail.

Mint-batch comparison (not the colliding pair): Cycle-1 `4699`/`4700` vs
Cycle-2 `4755` have **different** `due_mints` target identities. The Sep-1
mint-batch replay did **not** recur on Sep-3.

---

## 4. Producer path

```text
Scheduler claim job 3762 DISCOVERY_REFRESH
-> PreLifecycleTemporalRefreshOwner.request_temporal_refresh
-> build_pre_lifecycle_refresh_stage.refresh_stage
   (refresh_ordinal=1, cooperative_yield, first rotated channel = Pump)
-> run_direct_migration_discovery(
     request_key_prefix="...:c0002-refresh-1-pump",
     stage_sequence=2,
     collection_rounds=1,
     live-tail before=HEAD
   )
-> Source Governor request 4756 (new request key)
-> measured transport identity before=HEAD
-> seal_campaign_stage_evidence / stage_evidence_sink
-> CampaignSixUnitOwner.extend -> DUPLICATE_TRANSPORT_IDENTITY
-> classify_refresh_stage_exception
   -> PRE_LIFECYCLE_REFRESH_INTERNAL_INVARIANT:...DUPLICATE_TRANSPORT_IDENTITY
```

First incorrect owner: **refresh-stage Pump live-tail producer**
(`pre_lifecycle_refresh_composition.refresh_stage` →
`run_direct_migration_discovery`). It re-issued an already-sealed Cycle-2
`before=HEAD` page. The new request key (`refresh-1-pump-...`) does not change
canonical identity.

Producer class: **REFRESH_OPPORTUNITY_REUSE** (same query after persisted
refresh re-entry). Not mint-market checkpoint rehydration loss.

---

## 5. Sep-1 comparison

Sep-1 `12a7ea61` was cooperative `MARKET_DISCOVERY` resume forgetting a mint
whose DexScreener `MINT_MARKET_BATCH` had already completed, then re-issuing
the same due-mint identity as `r2`.

| Question | Sep-3 |
|---|---|
| Same mint twice in mint-batch? | **No.** Cycle-2 `4755` due-mints are a different set. |
| Same stage? | **No.** This collision is `DIRECT_PUMP_NOMINATION`, not `MINT_MARKET_BATCH`. |
| Same opportunity? | **No.** Initial vs refresh ordinal 1. |
| Same MARKET_DISCOVERY yield seam? | **No.** Refresh owner / Pump channel. |
| Forgotten unevaluated mint? | **No.** Empty HEAD page already sealed. |

```text
SEP1_MECHANISM_PARTIAL_RECURRENCE
```

Same *class*: producer re-issues an identical canonical transport; guard
rejects; request keys differ. Different *stage, channel, and resume surface*.

---

## 6. Historical repair inspection

| Item | Value |
|---|---|
| Implementation commit | `041e2550ec2ec090e45eec2d8de45f6a0c1e84f0` |
| Files | `eligible_token_supply.py`, `tests/test_v2_9_8b_later_cycle_mint_market_replay_repair.py` |
| Helper | `load_completed_cooperative_mint_market_batch_mints` |
| Prevents | MARKET_DISCOVERY cooperative resume putting already-COMPLETE+CLEAN_DATA current-cycle DexScreener round mint-batch mints back into `due_mints` |
| Does not cover | Pump live-tail; refresh composition; `before=HEAD` identity; refresh ordinal |
| Six-unit owner | unchanged, still fail-closed |
| Present in Sep-3 HEAD | **yes** (ancestor of `83d6bc1f` and of execution `26d7b91b`) |

Sep-3 **did** pass through that repaired MARKET_DISCOVERY path: claim 10 issued
`c0002-mint-batch-r1` with a **new** due-mint set and it completed. The mint-
batch repair worked for its stated case.

```text
REPAIR_REACHED_BUT_SCOPE_GAP
```

Not a regression of the mint-batch helper. Not “repair never reached.”

---

## 7. 4/2/2 path-change analysis

Overlapped 4/2/2 uses `PreLifecycleTemporalRefreshOwner` plus
`build_pre_lifecycle_refresh_stage`, which rotates fresh channels by refresh
ordinal and, under cooperative yield, runs **only the first** rotated channel.

Ordinal 1 → Pump live-tail. That path does **not** call
`load_completed_cooperative_mint_market_batch_mints` and does not rehydrate
already-sealed `DIRECT_PUMP_NOMINATION` identities.

Proved answer to the audit question:

> The old repair protected cooperative resume inside one MARKET_DISCOVERY
> opportunity. It did **not** carry equivalent “already fetched this exact
> transport” truth across the persisted refresh/re-entry Pump live-tail.

---

## 8. Request-key vs transport identity

```text
request keys:        DIFFERENT
canonical identity:  SAME
payloads:            BYTE_IDENTICAL
```

The producer lawfully created a **new Source Governor request** under a refresh
prefix, then measured the **same** RPC (`getSignaturesForAddress` on the same
authority from HEAD). That is a disguised replay, not a distinct protocol
transport.

Do **not** add request id, stage sequence, refresh ordinal, or Scheduler job id
to canonical identity. `stage_sequence=2` was already passed into
`run_direct_migration_discovery` and is excluded from the identity key by
contract.

---

## 9. Duplicate-guard verdict

```text
DUPLICATE_GUARD_CORRECT
```

`CampaignSixUnitOwner` / `MeasuredTransportLedger.record_transport` rejected
the second identical key. The same genuine transport occurred twice inside the
Cycle-2 accounting scope. Do not weaken the detector.

A later design may skip re-issuing a completed `before=HEAD` page, or use a
protocol-real cursor if new signatures exist. Empty HEAD (`signatures=[]`) has
no cursor to advance; polling HEAD again is the same query.

---

## 10. NO_PAIR truth

```text
NO_PAIR_FALSE_SHORTAGE_FROM_INTERNAL_FAILURE
```

- Instantaneous disposition at `13:01:12Z` was
  `BLOCKED_INSUFFICIENT_ELIGIBLE_CANDIDATE_POOL` while the +2400 horizon still
  had ~26 minutes and +1200/+1800 unused. Code maps that live-horizon case to
  `DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE`, not true market shortage.
- The first lawful delayed refresh then died on duplicate transport, so later
  ordinals never ran.
- Attempt items empty; Cycle 2 never freeze-admitted.
- This is not proven honest market scarcity.

---

## 11. Provider / source causality

```text
PROVIDER_LIMITATION_PRESENT_BUT_NOT_CAUSAL
```

Present: request `4721` `geckoterminal_rate_limited` / `STALE_DATA` during
initial liquidity-backup quanta (`retry_after` ~2 minutes). Other GeckoTerminal
batches in that sequence completed. Pump HEAD pages returned **empty**
signatures on both calls (no new on-chain migration page). Empty HEAD is not
independently sufficient to classify Cycle-2 no-pair after cutting off remaining
refresh law.

Do not convert the duplicate exception into provider scarcity.

---

## 12. Timing

Approved `+600 / +1200 / +1800 / deadline +2400` still scheduled correctly.
Duplicate occurred on **first refresh**, not initial (initial 4724 succeeded).
No 2400 → factory `PROOF_DEADLINE`. Cycle-1 continued through 1h until the
later unrelated `13:44Z` budget stop.

---

## 13. Budget interaction

```text
BUDGET_DEFECT_NOT_INVOLVED
```

At `13:01:20Z`, factory-governed requests were **39** total / t1 **23**, both
far below the stale per-token 50 and authorized 118. Cycle-2 died ~43 minutes
before the Cycle-1 1h budget stop. `project_lifecycle_budget_reserve` was not
the Cycle-2 terminal owner.

---

## 14. Primary classification

```text
NEW_NARROW_REFRESH_REENTRY_DEFECT
```

Proven chain:

```text
refresh_stage Pump channel
-> re-issue getSignaturesForAddress before=HEAD
-> new request key, same canonical identity as Cycle-2 initial 4724
-> CampaignSixUnitOwner reject DUPLICATE_TRANSPORT_IDENTITY
-> refresh wait/work FAILED
-> remaining acquisition opportunities abandoned
-> attempt remains NO_PAIR / DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE
```

Repair-disposition (historical mint-batch repair): `REPAIR_REACHED_BUT_SCOPE_GAP`.

---

## 15. Minimum repair surface (audit only — do not implement)

Defective functions:

- `pre_lifecycle_refresh_composition.build_pre_lifecycle_refresh_stage`
  / inner `refresh_stage` Pump branch
- `run_direct_migration_discovery` live-tail `before=HEAD` when that exact
  identity is already sealed in the current cycle ledger

Missing state: “this Cycle-2 campaign already completed canonical Pump
live-tail `address|before=HEAD`.” Analogous to completed mint-batch mint
rehydration, but for Pump HEAD pages and **refresh re-entry**, not MARKET_DISCOVERY
resume.

Canonical owners to reuse, not replace:

- Source Governor durable `printer_source_requests` /
  `printer_source_responses` (read-only rehydration)
- `canonical_transport_identity_key` (unchanged)
- `CampaignSixUnitOwner` (unchanged fail-closed)

Expected production files (later design):

- `src/printer_v1/discovery/pre_lifecycle_refresh_composition.py`
- possibly `src/printer_v1/discovery/direct_migration_discovery.py`
- focused tests next to
  `tests/test_v2_9_8b_later_cycle_mint_market_replay_repair.py`

Schema: **not required** if the helper reads existing Source Governor rows
scoped to the Cycle-2 request-key root, same pattern as
`load_completed_cooperative_mint_market_batch_mints`.

Source Governor / Scheduler: **no bypass, no new job kind, no retry, no
rotation, no budget/timing change.**

Prefer producer/checkpoint skip of an already-complete identical HEAD page
over detector relaxation.

---

## 16. Repair feasibility

```text
NARROW_REPAIR_FEASIBLE
```

---

## 17. Exact next lane

```text
SEP-3 CYCLE-2 DUPLICATE-TRANSPORT ACQUISITION REPAIR — DESIGN / SPECIFICATION
```

The independent four-token per-token `50 -> 118` design lane remains open and
is not this repair. Do not implement either automatically. Do not run Printer.
Do not prepare another authorization.

---

## Required repair invariants (later design only)

- same genuine transport cannot be counted twice
- duplicate guard stays strict
- Source Governor remains sole source-request owner
- Central Scheduler remains sole scheduling owner
- no retries / endpoint rotation / request-budget increase / timing change
- no new background worker/thread
- legitimate new mint B must not be suppressed because mint A was processed
- legitimate later refresh must not be suppressed unless existing law says
  that exact work is already satisfied
- no scoring/ranking/confidence

---

## DB / cleanup

Read-only after this audit: SHA-256 unchanged
`575984caa484b12f4bb5fca0a06cdf7865adeb03b5f16874406fb0c1a73daa6e`. Official
zero-state all `0`. Integrity `ok`. FK empty. Cycle-2 wait/work/attempt
terminal, none active. Authorization remains consumed. No
retry/rerun/restart/successor.
