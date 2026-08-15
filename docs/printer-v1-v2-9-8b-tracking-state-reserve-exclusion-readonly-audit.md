# Printer V1 V2-9.8B Tracking-State / Reserve-Exclusion Read-Only Audit

Date: 2026-08-16

Baseline: `4e47afb5feacb37279b92176abfe68c2e7dfa13e`

Branch: `agent/v2-9-8b-tracking-state-reserve-exclusion-readonly-audit`

Execution under reconciliation: `20260815T194831Z-6d09a756e8d1` ·
campaign `20260815T194831Z-6d09a756e8d1-campaign` ·
factory run `9296ffff-7e71-46d2-8e63-dd7b755780c9` · proposed cycle ordinal `2`

Type: audit-only. No code, no repair, no design, no authorization.

## 1. Verdict

```text
V2_9_8B_TRACKING_STATE_RESERVE_EXCLUSION_READONLY_AUDIT_PASS_EXCLUSIONS_EXPECTED_POLICY_WITH_PROVEN_HISTORICAL_RESIDUE
```

Python Builder Guide §13.3 primary classification for the ten reserve
exclusions and the seven Cycle-2 tracking dispositions:

```text
EXPECTED_OPERATIONAL_BLOCKER__NO_CODE_CHANGE
```

**No committed-code defect is claimed anywhere in this document.** Every
exclusion examined matches the approved design table verbatim. One durable
state — two campaign token slots left `SELECTED` by a `TERMINAL_FAILED`
campaign from 2026-07-27 — is inconsistent with what the current committed
closure owner would produce, and is classified as historical residue whose
origin is not determinable from committed code:

```text
UNKNOWN_REQUIRES_RESEARCH  (origin of the 2026-07-27 slot/queue residue only)
```

**The Cycle-2 capacity blocker is now fully understood and was reproduced
deterministically, read-only and zero-source, from committed code plus durable
state (§6).**

## 2. Read-only discipline and DB preservation

| Property | Before | After |
| --- | --- | --- |
| sha256 | `09684edd29a013a80748a03a7d3932f2dde1804c91ea58a02c4f76fb67863645` | `09684edd29a013a80748a03a7d3932f2dde1804c91ea58a02c4f76fb67863645` |
| size | `96612352` | `96612352` |
| inode | `1230526` | `1230526` |
| mtime | `1786824238.9008493` | `1786824238.9008493` |
| `-wal` sidecar | absent | absent |
| `-shm` sidecar | absent | absent |
| `-journal` sidecar | absent | absent |

- **DB SHA before == after**, byte-for-byte. It also equals the SHA recorded by
  the preceding Cycle-2 reconciliation and by the binding-repair closeout, so
  the authoritative corpus has not drifted across three lanes.
- Every connection opened with `file:…?mode=ro` **and** `PRAGMA query_only=ON`
  (verified `1`); `journal_mode` observed as `delete`.
- `PRAGMA integrity_check` = `ok`; `PRAGMA foreign_key_check` = `0` rows.
- Migration ledger `56`, head `056_four_token_pre_lifecycle_terminal_provenance.sql`.
- Zero writes, zero sidecars created, zero source/provider/RPC calls, no
  Scheduler, no Source Governor, no runtime, no tracking or reserve mutation.
- Tracked tree clean; the four pre-existing untracked `operator-runs/…` residue
  directories were listed only and left untouched.

## 3. The reserve is the whole reserve

`printer_eligible_token_reserve` contains **exactly ten rows** — the ten under
audit. There is no eleventh row and no `ELIGIBLE_FRESH` or `ELIGIBLE_STALE` row:

| eligibility_status | liquidity_status | count |
| --- | --- | --- |
| `EXCLUDED` | `LIQUIDITY_PROVEN` | 2 |
| `REMOVED` | `LIQUIDITY_PROVEN` | 8 |

Consequence proven at §5.3: at Cycle-2 the durable reserve contributed
**zero** rows to `prior_reserve`, so no reserve row could be re-marked, and the
certificate's `eligible_reserve_count = 2` came entirely from that run's own
fresh evaluation, not from the durable reserve.

## 4. Row-by-row evidence table

`Cycle-2 tracking` and `Cycle-2 liquidity` are this run's actual outcomes,
reproduced from committed code (§6.1) and read from the certificate's
`candidate_liquidity_lineage` (50 entries). `liquidity_usd` / `liquidity_status`
are the **last-successful historical** values frozen at `last_validated_at` —
see §5.2.

| # | mint (pool) | status | exclusion_reason | hist. liquidity_usd @ last_validated_at | last_campaign_id | updated_at | Cycle-2 tracking category | Cycle-2 liquidity outcome |
|---|---|---|---|---|---|---|---|---|
| 1 | `2C3CURT1…ByDR7A` (`AR4eDzUG…orV59`) | `EXCLUDED` | `TERMINAL_TRACKING_STATE` | 6 846.53 @ 2026-08-02 | `20260802T215214Z-…-campaign` | 2026-08-03 | `TERMINAL_TRACKING_STATE` (ineligible) | **not evaluated** — zero-source precheck |
| 2 | `Av2cD8GQ…wkdt2` (`REUdyzJN…hhJXo`) | `EXCLUDED` | `TERMINAL_TRACKING_STATE` | 4 818.32 @ 2026-08-02 | `20260802T215214Z-…-campaign` | 2026-08-03 | `TERMINAL_TRACKING_STATE` (ineligible) | **not evaluated** — zero-source precheck |
| 3 | `ApPLzZri…uTMpump` (`2JzNMKCn…gxXV`) | `REMOVED` | `LIQUIDITY_BELOW_SELECTION_FLOOR` | 16 020.66 @ 2026-07-28 | `20260728T224158Z-…-campaign` | 2026-07-31 | `FRESH_TRACKING_IDENTITY` (**eligible**) | `LIQUIDITY_NO_EXACT_PAIR` · req 2823 · `COMPLETE` |
| 4 | `F9fAYJUD…2ppump` (`BY3Y3zni…AQz3`) | `REMOVED` | `LIQUIDITY_BELOW_SELECTION_FLOOR` | 12 220.99 @ 2026-07-27 | `…-discovery-only` | 2026-07-27 | `FRESH_TRACKING_IDENTITY` (**eligible**) | `LIQUIDITY_NO_EXACT_PAIR` · req 2824 · `COMPLETE` |
| 5 | `2XzK878G…Xuwpump` (`4XCJeuDX…nizG`) | `REMOVED` | `LIQUIDITY_BELOW_SELECTION_FLOOR` | 9 867.12 @ 2026-07-28 | `20260728T224158Z-…-campaign` | 2026-07-31 | `COOLDOWN_REQUALIFICATION_REQUIRED` (**eligible**) | `LIQUIDITY_NO_EXACT_PAIR` · req 2823 · `COMPLETE` |
| 6 | `5o2WFRY9…6apump` (`9hT4XDxy…hXYZ`) | `REMOVED` | `LIQUIDITY_UNPROVEN` | 9 532.85 @ 2026-07-28 | `NULL` | 2026-07-28 | `FRESH_TRACKING_IDENTITY` (**eligible**) | `LIQUIDITY_NO_EXACT_PAIR` · req 2823 · `COMPLETE` |
| 7 | `2RL5JTQL…f9pump` (`E4fjibQD…TAtG`) | `REMOVED` | `LIQUIDITY_UNPROVEN` | 6 978.41 @ 2026-07-28 | `NULL` | 2026-07-28 | `FRESH_TRACKING_IDENTITY` (**eligible**) | `LIQUIDITY_NO_EXACT_PAIR` · req 2823 · `COMPLETE` |
| 8 | `3zh9CTwP…BVpump` (`BNiVaqvJ…Rsbj`) | `REMOVED` | `LIQUIDITY_BELOW_SELECTION_FLOOR` | 3 472.53 @ 2026-07-27 | `NULL` | 2026-07-28 | `COOLDOWN_REQUALIFICATION_REQUIRED` (**eligible**) | `LIQUIDITY_NO_EXACT_PAIR` · req 2823 · `COMPLETE` |
| 9 | `AkYnWBir…ZVpump` (`CodGcGQQ…FsTJ`) | `REMOVED` | `LIQUIDITY_BELOW_SELECTION_FLOOR` | 3 260.44 @ 2026-07-28 | `20260728T224158Z-…-campaign` | 2026-07-31 | `COOLDOWN_REQUALIFICATION_REQUIRED` (**eligible**) | `BELOW_3000_FLOOR` · req 2823 · `COMPLETE` |
| 10 | `12u9FULa…Dtpump` (`ECobcS1M…gwgc`) | `REMOVED` | `LIQUIDITY_NO_EXACT_PAIR` | 3 192.31 @ 2026-08-04 | `20260804T164755Z-…-campaign` | 2026-08-09 | `COOLDOWN_REQUALIFICATION_REQUIRED` (**eligible**) | `LIQUIDITY_NO_EXACT_PAIR` · req 2823 · `COMPLETE` |

Three facts follow directly from the table:

1. **All ten rows are stale relative to Cycle-2.** The newest `updated_at` is
   2026-08-09, six days before the 2026-08-15 execution. **No reserve row was
   written by the Cycle-2 execution at all.**
2. **Eight of ten were tracking-ELIGIBLE at Cycle-2** (4 `FRESH`, 4
   `COOLDOWN_REQUALIFICATION_REQUIRED`). Only rows 1 and 2 were withheld by
   tracking state.
3. **All eight tracking-eligible rows were re-evaluated at the liquidity stage
   in Cycle-2 with `COMPLETE` source responses** and failed on **current**
   market evidence (7 × exact pool absent, 1 × below the $3 000 floor). They
   were not withheld by their reserve status.

## 5. Status-transition and ownership map

### 5.1 Who can assign each status

| Status | Sole assigning owner | Trigger | Zero-source? |
| --- | --- | --- | --- |
| `ELIGIBLE_FRESH` | `eligible_token_supply.upsert_eligible_reserve` (line 1639) | candidate passed the current round's full evaluation | no |
| `ELIGIBLE_STALE` | `eligible_token_supply.mark_reserve_status` (line 1076) | every prior `FRESH`/`STALE` row at loop start, forcing revalidation | yes |
| `EXCLUDED` | `eligible_token_supply.mark_reserve_status` (line 1150) | tracking precheck says ineligible **and** the mint is in `prior_reserve` | yes |
| `REMOVED` | `eligible_token_supply.mark_reserve_status` (line 1675) | prior reserve mint fails current evaluation (`prior is not None`) | no |

```text
                (inventory walk, every run)
                          |
        ┌─────────────────┴──────────────────┐
        v                                    v
 tracking precheck (zero-source)      liquidity / market stage
        |                                    |
   ineligible + in prior_reserve         fails evaluation + in prior_reserve
        |                                    |
        v                                    v
    EXCLUDED  <──────── mark_reserve_status ────────>  REMOVED
        \                                              /
         \______ upsert_eligible_reserve(ELIGIBLE_FRESH) ______/
                 (re-observed from inventory AND passes)
```

### 5.2 The liquidity columns are historical, not current

`mark_reserve_status` (lines 267-282) updates **only** `eligibility_status`,
`exclusion_reason` and `updated_at`. It never rewrites `liquidity_usd` or
`liquidity_status`. A row therefore keeps the last-successful `LIQUIDITY_PROVEN`
value it earned, even while being removed for a *current* liquidity failure.
The supply owner states this explicitly at lines 1665-1672, tagging the carried
values `"evidence_role": "HISTORICAL_LAST_SUCCESSFUL_ONLY"` and
`"admitted_as_current": False`.

This is why row 3 reads `LIQUIDITY_PROVEN`, `$16,020.66`, `REMOVED`,
`LIQUIDITY_BELOW_SELECTION_FLOOR` simultaneously. It is not a contradiction and
not a defect — but it is the single most misreadable surface in this subsystem
(§10).

### 5.3 EXCLUDED / REMOVED does not gate re-evaluation

`load_eligible_reserve(statuses=(ELIGIBLE_FRESH, ELIGIBLE_STALE))` (line 1071)
never loads an `EXCLUDED` or `REMOVED` row. Those rows therefore never enter
`prior_reserve`, never enter `prior_by_mint`, never receive
`historical_reserve_evidence`, and never count toward `eligible_reserve_count`.

They are nevertheless **re-walked in full every run**, because the candidate
universe is the graduated registry inventory
(`export_graduated_candidates`, line 1057), not the reserve. This is proven
empirically: all ten reserve mints are present in the 48-mint inventory, and the
Cycle-2 certificate lineage contains all ten — two rejected at the zero-source
precheck, eight carried all the way through governed liquidity work.

**The reserve is a cache of last evaluation, not an authority over supply.** An
`EXCLUDED`/`REMOVED` status cannot starve the candidate pool.

### 5.4 Lawful reopen paths that already exist (none executed)

| Blocked category | Self-healing? | Committed lawful path |
| --- | --- | --- |
| reserve `EXCLUDED` / `REMOVED` | **yes** | re-observed from inventory + passes → `upsert_eligible_reserve(ELIGIBLE_FRESH)` overwrites the status. No operator action required. |
| tracking `COOLDOWN` | **yes** | `_effective_cooldown_expiry` + `TRACKING_COOLDOWN_SECONDS` (1800 s) → `COOLDOWN_REQUALIFICATION_REQUIRED`, `eligible = True`, claimable via `claim_tracking_item(fresh_evidence_requalification=True)` → `REOPEN_REVIVED_TOKEN`. |
| tracking `SKIPPED` / `ARCHIVED` | **no** | `lane_x3_post_cycle_lifecycle.reopen_token()`, exposed as an operator CLI command. It appends a **`WATCH_ONLY`/`QUEUED`** row, so it does **not** clear a `TRACK_NORMAL` terminal. This is deliberate — see §5.5. |
| tracking `QUEUED` orphaned by a dead campaign | **no** | `unified_terminal_closure` would set it `SKIPPED` — but only for a campaign whose closure actually runs. |

### 5.5 The terminal behaviour is the approved design, verbatim

`docs/printer-v1-v2-9-8b-selective-1h-tracking-handoff-design.md` (lines 25-51)
specifies the exact table the code implements:

| Latest exact status | Category | Behaviour |
| --- | --- | --- |
| no row | `FRESH_TRACKING_IDENTITY` | eligible |
| `QUEUED` / `ACTIVE` / `PAUSED` | `DUPLICATE_ACTIVE_TRACKING` | exclude; fail closed; do not enqueue |
| `COOLDOWN` | `COOLDOWN_REOPEN_REQUIRED` | exclude; fail closed |
| `SKIPPED` / `ARCHIVED` | `TERMINAL_TRACKING_STATE` | exclude; **"fail closed; no implicit reopen"** |

and states that `reopen_token()` "appends a `WATCH_ONLY` / `QUEUED` row" and
that "discovery must not … silently promote it into the selective-1h
`TRACK_NORMAL` handoff."

The lane mismatch is therefore **intentional policy, not an oversight**. No
defect is claimed.

## 6. Reconciling the Cycle-2 dispositions against the ten rows

### 6.1 Exact zero-source reproduction

Replaying `_handoff_assessment`'s committed rules over the 48-mint
`PUMPSWAP_GRADUATED_CONFIRMED` inventory, at the certificate instant
`2026-08-15T19:53:32Z`, reproduces the certificate's counters **exactly**:

| Category | Reproduced | Certificate `rejection_reasons` |
| --- | --- | --- |
| `FRESH_TRACKING_IDENTITY` | 37 | — (eligible) |
| `COOLDOWN_REQUALIFICATION_REQUIRED` | 4 | — (eligible) |
| `TERMINAL_TRACKING_STATE` | **5** | **5** ✔ |
| `DUPLICATE_ACTIVE_TRACKING` | **2** | **2** ✔ |

### 6.2 Only two of the seven are reserve rows

| # | mint | category | latest `TRACK_NORMAL` queue row | in reserve? |
| --- | --- | --- | --- | --- |
| 1 | `3BTSRa1Y…H7tQpump` | `TERMINAL_TRACKING_STATE` | id 18 `SKIPPED` · `campaign_terminal:LEASE_RENEWAL_UNCONFIRMED_HISTORICAL_SUBTYPE_UNKNOWN` | no |
| 2 | `DqLouq9H…D31pump` | `TERMINAL_TRACKING_STATE` | id 19 `SKIPPED` · `campaign_terminal:LEASE_RENEWAL_UNCONFIRMED_HISTORICAL_SUBTYPE_UNKNOWN` | no |
| 3 | `5iRB5xMp…jpkpump` | `TERMINAL_TRACKING_STATE` | id 22 `SKIPPED` · `campaign_terminal:LEASE_RENEWAL_SQLITE_LOCKED` | no |
| 4 | `2C3CURT1…ByDR7A` | `TERMINAL_TRACKING_STATE` | id 32 `SKIPPED` · `campaign_terminal:OPERATIONAL_CAMPAIGN_FAILED:KeyError` | **yes (row 1)** |
| 5 | `Av2cD8GQ…wkdt2` | `TERMINAL_TRACKING_STATE` | id 33 `SKIPPED` · `campaign_terminal:OPERATIONAL_CAMPAIGN_FAILED:KeyError` | **yes (row 2)** |
| 6 | `UUdfUfhk…jPPpump` | `DUPLICATE_ACTIVE_TRACKING` | id 16 `QUEUED` · `combined_discovery_handoff` · `last_checked_at = NULL` | no |
| 7 | `7tKKxaDc…ZxGpump` | `DUPLICATE_ACTIVE_TRACKING` | id 17 `QUEUED` · `combined_discovery_handoff` · `last_checked_at = NULL` | no |

**Five of the seven tracking-ineligible mints are not reserve rows at all.** The
ten reserve rows and the seven dispositions are two largely disjoint sets whose
only overlap is rows 1 and 2.

### 6.3 Every terminal state traces to an infrastructure failure

All 28 tokens whose latest `TRACK_NORMAL` row is `SKIPPED` carry a
`campaign_terminal:` or `factory_terminal:` reason — lease loss, SQLite lock,
budget ceiling, operator interrupt, preflight failure, adapter error, or an
uncaught `KeyError`. **Not one** is an ordinary lifecycle completion; a clean
15m completion routes to `COOLDOWN` (`owned_window_terminal:…` /
`factory_terminal:COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED:CLEAN`), which
expires and self-heals.

`SKIPPED` is, in this corpus, exclusively a **failure-residue** state. Rows 1
and 2 had healthy `COOLDOWN` rows (ids 30, 31) from a clean 2026-07-31 result
before a crashed 2026-08-02 campaign appended the `SKIPPED` rows that now bind
them permanently.

Five of the 48 inventory mints (10.4 %) are currently permanently
tracking-terminal by this mechanism.

### 6.4 The two `DUPLICATE_ACTIVE_TRACKING` rows are incomplete-closure residue

Queue rows 16 and 17 are `QUEUED` since 2026-07-27 00:21:51 with
`last_checked_at = NULL` and `next_check_at` already in the past. They **are**
linked to campaign token slots:

| slot | campaign | `token_state` | `first_terminal_cause` | queue id |
| --- | --- | --- | --- | --- |
| `slot-20260727T001520Z-…-cycle-1` | `20260727T001520Z-…-campaign` | `SELECTED` | `NULL` | 16 |
| `slot-20260727T001520Z-…-cycle-2` | `20260727T001520Z-…-campaign` | `SELECTED` | `NULL` | 17 |

The owning campaign is `TERMINAL_FAILED`, yet its slots never left `SELECTED`.
These are the **only two non-terminal token slots in the entire database** (all
other slots are `COOLDOWN`/`ARCHIVED`/`MANUAL_REVIEW`/`FAILED`, across 52
campaigns).

`unified_terminal_closure` (lines 444-500) is the committed owner that would
have set both slots `MANUAL_REVIEW` and both queue rows `SKIPPED`
(its `UPDATE … WHERE id=? AND queue_status='QUEUED'` matches exactly this
shape). It evidently did not run for that campaign. Whether the 2026-07-27
campaign predates this closure behaviour or the closure failed cannot be
determined from committed code, so the **origin** stays
`UNKNOWN_REQUIRES_RESEARCH`. The **state** is definitively residue: it is not
what the current committed closure contract would produce.

### 6.5 Why `TRACKING_STATE_CAPACITY_BLOCKED` was nevertheless correct

`_apply_permanent_shortage_precedence` (lines 135-155) checks, in order:
liquidity source unavailable → stale/rate-limited → malformed/partial →
provider failures with unavailable channels → budget → duration →
lawful-work-remaining → **any tracking disposition ineligible for evidence** →
otherwise the computed shortage.

Cycle-2 recorded `provider_failures = 0`, `channels_unavailable = []`, budget
17/30 remaining, duration unexhausted, and no lawful unexplored work. The 37
`LIQUIDITY_EXACT_PAIR_UNAVAILABLE_OR_MISMATCH` outcomes are candidate-local
market absences, correctly **not** counted as source failures. The rule that
fired was therefore the tracking clause — driven by the seven dispositions in
§6.2, of which all seven are residue-derived.

The classification is correct, and this audit strengthens rather than weakens
it: the tracking clause fired on genuinely internal state, exactly as the
conservative precedence intends.

### 6.6 Correction to the reconciliation's corroborating remark

`docs/printer-v1-v2-9-8b-cycle2-authoritative-exhaustion-certificate-reconciliation.md`
§4 offered as corroboration: *"Liquidity-proven supply existed and was withheld
by eligibility/tracking state."*

That is **refuted for eight of the ten rows**. Those eight were tracking-eligible,
were re-walked, received governed liquidity work with `COMPLETE`/`CLEAN_DATA`
responses, and failed on current market evidence. Their `LIQUIDITY_PROVEN`
columns are 12-19-day-old historical values (§5.2), not current supply.

It holds only for rows 1 and 2, and even there the liquidity figures are
historical rather than current.

The reconciliation's **verdict, classification and defect findings are
unaffected** — only this one corroborating sentence is corrected. The Cycle-2
shortage classification remains `TRACKING_STATE_CAPACITY_BLOCKED`.

## 7. Expected policy vs stale/residual vs proven defect

| Finding | Classification | Evidence |
| --- | --- | --- |
| 8 `REMOVED` rows withheld on current liquidity | **expected current policy** | design §6 rules 4 and 6; certificate lineage shows current `COMPLETE` evaluations |
| 2 `EXCLUDED` rows withheld on tracking terminal | **expected current policy** | handoff design table: `SKIPPED` → exclude, no implicit reopen |
| Reserve rows never gate re-evaluation | **expected current policy, working** | all 10 present in the 48-mint inventory and in the Cycle-2 lineage |
| `LIQUIDITY_PROVEN` + high `liquidity_usd` beside `EXCLUDED`/`REMOVED` | **expected policy, high misread risk** | `mark_reserve_status` by construction; `HISTORICAL_LAST_SUCCESSFUL_ONLY` tag at lines 1665-1672 |
| 5 inventory mints permanently `TERMINAL_TRACKING_STATE`, all from infrastructure failures | **historical residue under intentional policy** | every `SKIPPED` reason is a `campaign_terminal:`/`factory_terminal:` failure; "no implicit reopen" is the approved rule |
| `reopen_token()` cannot clear a `TRACK_NORMAL` terminal | **intentional design, not a defect** | handoff design lines 41-51 state this explicitly |
| 2 slots `SELECTED` + 2 queue rows `QUEUED` under a `TERMINAL_FAILED` campaign | **residue; origin `UNKNOWN_REQUIRES_RESEARCH`** | only 2 non-terminal slots in 52 campaigns; inconsistent with `unified_terminal_closure` |
| Any committed-code defect | **none proven** | — |

## 8. Is the Cycle-2 capacity blocker understood?

**Yes — completely, and reproducibly without any source call.**

```text
48 inventory mints walked
  ├─ 7 rejected at the zero-source tracking precheck
  │     ├─ 5 TERMINAL_TRACKING_STATE   (all infrastructure-failure residue)
  │     └─ 2 DUPLICATE_ACTIVE_TRACKING (orphan slots of a TERMINAL_FAILED campaign)
  └─ 41 rejected at the governed liquidity stage
        ├─ 37 LIQUIDITY_NO_EXACT_PAIR  (recorded pool absent from current market data)
        └─  4 LIQUIDITY_BELOW_SELECTION_FLOOR
  + 2 eligible found by fresh discovery (2 fresh_market_checks)
  = 50 unique tokens observed · eligible_count 2 · required capacity 4 → BLOCKED
```

Two distinct, separable constraints are now named:

1. **Governing (classification):** 7 residue-derived tracking dispositions
   triggered the conservative precedence clause. Numerically small.
2. **Binding (supply):** 41 of 48 inventory mints failed **current** market
   evidence, dominated by 37 exact-pool absences. This — not the reserve
   exclusions — is what actually left the run two tokens short.

Even if all 7 tracking dispositions were cleared, those 7 mints would still have
had to pass the same liquidity stage that rejected 41 of their peers. Clearing
tracking residue alone is **not** demonstrated to unblock a four-token proof.

## 9. Money-usefulness contribution

The previous lane left an open, plausible, and expensive hypothesis: that
Printer was sitting on ten liquidity-proven tokens it was refusing to use. Acting
on that would have meant clearing exclusions and spending a scarce one-shot
authorization to re-run against supply that does not currently exist.

This audit closes that hypothesis at zero authorization and zero source cost. It
proves eight of the ten are unusable on **current** market evidence, that the
reserve never gated them anyway, and that the real supply constraint is 37
graduated candidates whose recorded PumpSwap pools no longer resolve in current
market data. Printer only grows clean memory from tokens it can actually observe;
knowing the shortage is market-visibility rather than self-inflicted eligibility
is what stops the next authorization from being wasted a second time.

## 10. What this improves

- Each of the ten exclusions has a named owner, trigger, timestamp and current
  evaluation outcome.
- The certificate's `5 TERMINAL_TRACKING_STATE` and `2 DUPLICATE_ACTIVE_TRACKING`
  are reproduced exactly, offline, and attributed to specific queue rows.
- The reserve is established as a non-authoritative cache: exclusion cannot
  starve supply, and re-admission is automatic on a passing re-evaluation.
- The historical-vs-current semantics of `liquidity_usd` / `liquidity_status`
  are pinned to the code that creates them, retiring the misreading they invite.
- The governing classification is separated from the binding constraint, so the
  next lane targets exact-pool visibility rather than eligibility bookkeeping.
- Two durable residue items are located precisely: 5 permanently terminal
  inventory mints, and the only 2 non-terminal token slots in the corpus.
- The reconciliation's one over-broad corroborating sentence is corrected without
  disturbing its verdict.

## 11. What remains locked

Unchanged and still locked: authorization creation and consumption (including
authorization #7), four-token proof execution or rerun, campaign start,
six-token proof and capacity widening, `WINDOW_1H` / `WINDOW_12H` /
`WINDOW_24H` activation, discovery and source fetching, runtime, DB writes,
cleanup, migrations, memory generation, tracking-state mutation, reserve-status
mutation, retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events,
paper audits, PnL, wallets, private keys, real funds, live execution, paid APIs,
scoring/ranking/confidence/weighted logic, embeddings and vectors. Solana
memecoin-only and paper-only remain in force.

No repair was designed or implemented in this lane. No exclusion was cleared, no
queue row was touched, no reserve row was modified.

## 12. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Consequence | Control / status |
| --- | --- | --- |
| Reading `LIQUIDITY_PROVEN` + `$16,020` as current supply | Exactly the misdiagnosis this lane corrects; invites clearing exclusions and burning an authorization | §5.2 pins the historical semantics; any future surface presenting reserve liquidity must label it last-successful |
| Terminal `SKIPPED` accumulation | Monotonic: 5 of 48 inventory mints (10.4 %) are already permanently unreachable, and every campaign crash adds more. Over time this shrinks the four-token universe | Intentional under "no implicit reopen"; the only remedy is an operator action that currently targets a different lane |
| 2 orphan `SELECTED` slots + `QUEUED` rows | Hold `DUPLICATE_ACTIVE_TRACKING` indefinitely and are the only non-terminal slots in the corpus | Located precisely; origin undetermined; **not** to be cleaned without its own approved lane |
| Treating tracking residue as the binding constraint | Clearing all 7 dispositions would still leave 41/48 failing on liquidity; a rerun would very likely reproduce a below-capacity terminal | §8 separates governing from binding constraint |
| 37 × `LIQUIDITY_NO_EXACT_PAIR` | The dominant real blocker: recorded PumpSwap pools no longer resolve in current market data. Could be pool migration, aggregator coverage, or stale registry identities — **not established here** | Named as the exact next lane (§13) |
| Registry inventory frozen at 48 | If graduated candidates are not being added, the universe cannot grow regardless of eligibility | Out of scope; observed only |
| `_effective_cooldown_expiry` derives expiry from `last_checked_at` when `next_check_at` precedes it | 4 of the reserve rows are eligible only via this derived path; a change to `TRACKING_COOLDOWN_SECONDS` would silently move them | Behaviour is committed and was applied consistently; noted for future coverage |
| Audit stopped at read-only | No fix is delivered; the blocker persists until a later approved lane | Deliberate — this lane is audit-only and forbids repair |
| Over-reading this audit as clearance to re-run | The four-token proof would still block | No authorization is justified; §11 keeps it locked |

## 13. Exact recommended next lane

```text
V2-9.8B Exact-Pool Market-Visibility Read-Only Audit
(LIQUIDITY_NO_EXACT_PAIR across 37 of 48 graduated inventory candidates)
```

Read-only. It should establish, from committed code, durable rows and existing
artifacts, why the recorded `pumpswap_pool` identity for 37 of 48
`PUMPSWAP_GRADUATED_CONFIRMED` candidates did not resolve to an exact pair in
current market data: registry identities stale or wrong, pools migrated or
drained, aggregator coverage gaps, or a batch request/response matching defect.
It must not fetch sources, mutate the DB, or create an authorization.

Two smaller lanes are queued behind it and must **not** be started now:

1. a read-only residue lane for the 2 orphan `SELECTED` slots / `QUEUED` rows
   under the `TERMINAL_FAILED` 2026-07-27 campaign, to determine the origin and
   whether a bounded closure is warranted;
2. a policy review of whether an approved, non-implicit re-admission path should
   exist for `TRACK_NORMAL` lanes left `SKIPPED` purely by infrastructure
   failure — a design question, not a defect.

No authorization may be created and the four-token proof must not be rerun until
the market-visibility lane closes.
