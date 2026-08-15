# Printer V1 V2-9.8B Cycle-2 Authoritative Exhaustion-Certificate Reconciliation

Date: 2026-08-15

Baseline: `3687bb5b4ba692de9f342da40305125f50e0277c`

Execution: `20260815T194831Z-6d09a756e8d1` ·
campaign `20260815T194831Z-6d09a756e8d1-campaign` ·
factory run `9296ffff-7e71-46d2-8e63-dd7b755780c9`

## 1. Exact verdict

```text
V2_9_8B_CYCLE2_AUTHORITATIVE_EXHAUSTION_CERTIFICATE_RECONCILIATION_CERTIFICATE_VALID_REPORTING_CONTRACT_VIOLATED
```

The Cycle-2 exhaustion certificate **exists, is valid, and satisfies honest
exhaustion**. The persisted classification is **not** a market-supply
conclusion, and the committed reporting path **lost it**, presenting a generic
market-flavoured terminal instead.

### Exact shortage classification

```text
TRACKING_STATE_CAPACITY_BLOCKED
```

### Python Builder Guide primary classification

```text
PRINTER_BINDING
```

Not `EXPECTED_OPERATIONAL_BLOCKER__NO_CODE_CHANGE`: committed behaviour violated
an approved certificate/reporting contract that the code itself states in its own
docstring. The defect category is **evidence loss / contract drift in the Cycle-2
supply reporting path**, binding on the active Printer design.

## 2. Read-only discipline

- audit worktree at the baseline; user checkout untouched
  (`agent/v2-9-8b-post-repair-zero-state-residue-audit` @ `8fbfb088`)
- real DB read by absolute path only, `mode=ro` + `PRAGMA query_only=ON` (verified `1`)
- **DB SHA before == after** = `09684edd29a013a80748a03a7d3932f2dde1804c91ea58a02c4f76fb67863645`
  — reconciles exactly with the recorded post-execution SHA; no drift
- size `96612352`, inode `1230526`, ledger `56` / head `056_…`
- sidecars before: none · after: none — **zero audit-created sidecars**
- `integrity_check = ok`, `foreign_key_check = 0`
- no Printer process, no DB holder, no lease, before and after
- zero source/Scheduler/runtime activity; no writes; `git diff --check` PASS

## 3. Certificate evidence table

| # | question | answer |
| --- | --- | --- |
| 1 | certificate exists for the failed Cycle-2 attempt? | **YES** — `exh-9296ffff-7e71-46d2-8e63-dd7b755780c9:20260815T194831Z-6d09a756e8d1-campaign-run:c0002`, created `2026-08-15T19:53:32.356663+00:00`, version `V2_9_8B_LIQUIDITY_EVIDENCE_EXHAUSTION_V2` |
| 2 | bound to exact identity? | **campaign/run/cycle exact** — campaign `…-campaign`, run `…-campaign-run`, cycle `…-cycle-2`. The `execution_id` column carries the **composite adapter key** `9296ffff…:…-campaign-run:c0002`, not the canonical execution id `20260815T194831Z-6d09a756e8d1` (all 11 earlier certificates use canonical execution ids) |
| 3 | shortage_classification | **`TRACKING_STATE_CAPACITY_BLOCKED`** |
| 4 | required / reserve | `required_eligible_capacity = 4`, `eligible_reserve_count = 2`, `eligible_count = 2` |
| 5 | unique tokens / rounds | `unique_tokens_observed = 50`, `discovery_rounds = 2`, `tokens_already_known_from_inventory = 48`, `pools_confirmed = 48`, `fresh_market_checks = 2`, `rejected_count = 48` |
| 6 | rejection reason counts | `LIQUIDITY_NO_EXACT_PAIR` **37**, `TERMINAL_TRACKING_STATE` **5**, `LIQUIDITY_BELOW_SELECTION_FLOOR` **4**, `DUPLICATE_ACTIVE_TRACKING` **2**. Liquidity outcomes: `LIQUIDITY_EXACT_PAIR_UNAVAILABLE_OR_MISMATCH` 37, `LIQUIDITY_EXACT_BELOW_FLOOR` 4 |
| 7 | channels attempted / unavailable | **5 attempted** — `dexscreener_fresh_profiles_locator`, `direct_pump_finalized_live_tail`, `exact_pump_pumpswap_graduation_verify`, `dexscreener_mint_market_batch`, `geckoterminal_fresh_pool_nomination`. **`channels_unavailable = []`** |
| 8 | provider/source failures + lineage | certificate: `provider_failures = 0`, `liquidity_stage_provider_failures = 0`. Host DB shows 7 failures in the run: 2 × `direct_pump_migration_rejected_…` (candidate-local by contract, must never mark a channel unavailable), 4 × `geckoterminal_rate_limited` (`STALE`, discovery stage), 1 × `dexscreener_exact_pair_row_ceiling` at 19:56:28 (after certificate). Cycle-2 liquidity requests `2815`, `2823`, `2824` all `COMPLETE` / `CLEAN_DATA` |
| 9 | source operations | `source_operations_used = 13`, **`source_operations_remaining = 17`** — budget **not** exhausted |
| 10 | duration | `duration_used_seconds = 0.0`, `duration_remaining_seconds = null` — duration **not** exhausted |
| 11 | lawful unexplored work remaining? | **NO** — `unexplored_work_prevented_by_hard_ceiling = false`; `stale_evidence_exclusions = 0`; `cooldown_skips = 0`; `duplicate_observations_removed = 0` |
| 12 | last_reason_discovery_could_not_continue | **`ALL_REACHABLE_CANDIDATES_EVALUATED`** |
| 13 | HONEST_EXHAUSTION? | **SATISFIED** — see §5 |
| 14 | certificate agrees with host terminal artifact? | **NO** — see §6 |
| 15 | generic closeout accurate? | **NO** — see §7 |
| 16 | reporting path lost evidence? | **YES** — see §6 |

## 4. Why `TRACKING_STATE_CAPACITY_BLOCKED` is the correct classification

`eligible_token_supply._apply_permanent_shortage_precedence` applies a fixed
precedence. Source-availability, stale-evidence, visibility, budget, duration and
architecture-false-shortage conditions all rank above it and **none applied**
(`provider_failures 0`, `channels_unavailable []`, `stale_evidence_exclusions 0`,
budget and duration both unexhausted). The rule that fired is:

```python
if any(not bool(x.get("eligible_for_evidence")) for x in tracking_dispositions.values()):
    return TRACKING_STATE_CAPACITY_BLOCKED
```

Seven observed candidates carried tracking dispositions ineligible for evidence
(`TERMINAL_TRACKING_STATE` 5 + `DUPLICATE_ACTIVE_TRACKING` 2). The precedence is
deliberately conservative: when the operator's own tracking state contributed, the
system must not present a market conclusion. The classification is therefore
**correct under the committed contract**, even though liquidity reasons dominate
the raw counts (41 of 48).

Corroborating durable state: `printer_eligible_token_reserve` holds 10
`PERSISTED_GRADUATED` rows with `LIQUIDITY_PROVEN` and liquidity well above the
3000 floor (e.g. `$16,020.66`, `$6,846.53`, `$4,818.32`, `$3,260.44`) whose
`eligibility_status` is `EXCLUDED` or `REMOVED`. Liquidity-proven supply existed
and was withheld by eligibility/tracking state — exactly what the classification
asserts.

## 5. HONEST_EXHAUSTION verdict

```text
HONEST_EXHAUSTION: SATISFIED
```

All five conditions hold: discovery reached
`ALL_REACHABLE_CANDIDATES_EVALUATED`; no hard ceiling suppressed lawful work
(`unexplored_work_prevented_by_hard_ceiling = false`); operation budget was not
exhausted (17 of 30 remaining); duration was not exhausted; and no channel was
unavailable with zero counted provider failures at the liquidity stage. The
attempt did not stop early or hide a reachable candidate.

## 6. Certificate vs host terminal artifact — evidence lost

The DB persisted the certificate correctly and completely. The host artifacts did
not carry it.

| surface | certificate content |
| --- | --- |
| `printer_discovery_exhaustion_certificates` | **complete**, classification present |
| `terminal-summary.json` → `report.exhaustion_certificate` | **`null`** |
| `terminal-summary.json` → `report.shortage_classification` | **`null`** |
| `terminal-summary.json` occurrences of `TRACKING_STATE_CAPACITY_BLOCKED` | **0** |
| `terminal-summary.json` occurrences of `BLOCKED_INSUFFICIENT_ELIGIBLE_CANDIDATE_POOL` | **3** |
| `terminal-summary.json` `blocked_supply_reason` / `eligible_candidates` / `candidates_observed` / `candidates_validated` | all **`null`** |
| `terminal-summary.json` `required_token_capacity` / `token_capacity` | `2` / `2` — not the certificate's required `4` |
| `child-terminal.json` | **zero** certificate or classification content |
| `printer_pre_admission_discovery_attempts` (ordinal 2) | `NO_PAIR`, `first_terminal_cause = BLOCKED_INSUFFICIENT_ELIGIBLE_CANDIDATE_POOL` — generic, not the classification |
| campaign / run / Cycle 1 terminal cause | `BLOCKED_INSUFFICIENT_ELIGIBLE_CANDIDATE_POOL` |

The committed contract is explicit. `authoritative_live_operational_campaign.py`
(≈ line 850) documents:

> *"Only proven true market-supply exhaustion retains the historical
> insufficient-pool terminal. Source, stale, malformed/visibility, budget,
> duration, or architecture blockers keep their existing categorical shortage
> name and **can never be presented as a market conclusion**."*

and implements:

```python
if classification == "TRACKING_STATE_CAPACITY_BLOCKED":
    return str(diagnostics.get("tracking_terminal_cause") or "COOLDOWN_REOPEN_REQUIRED")
```

The observed run nonetheless surfaced an insufficient-pool market terminal, with
`tracking_terminal_cause` and `COOLDOWN_REOPEN_REQUIRED` appearing **0 times**
anywhere in the host artifacts. **Answer to Q16: yes — the Cycle-2
adapter/reporting path lost required certificate and classification evidence
despite correct DB persistence.**

## 7. Was "external supply" the correct characterisation?

**No.**

The authoritative-root execution closeout stated the blocker was *"external
supply, not the machinery"* and recorded
`BLOCKED_INSUFFICIENT_ELIGIBLE_CANDIDATE_POOL`. The durable certificate shows the
governing classification is `TRACKING_STATE_CAPACITY_BLOCKED` — an **internal
tracking-state capacity condition**, with liquidity-proven reserve tokens present
but withheld by eligibility state. The generic closeout **did not accurately
represent the underlying classification**, and that mischaracterisation is
corrected here.

## 8. Is another proof authorization currently justified?

**No.**

A further authorization consumed against this state would very likely reproduce
the same certificate: the reserve still holds `EXCLUDED`/`REMOVED`
liquidity-proven entries, the tracking-state condition is unchanged, and the
reporting path would again present a market conclusion while discarding the
classification — leaving the next operator with the same false diagnosis that
cost this reconciliation.

The reporting/evidence-propagation defect should be repaired, and the
tracking-state exclusions understood, before any authorization is created.

## 9. Money-usefulness contribution

Converts a false "external market supply" conclusion into the exact, durable
classification, at zero authorization cost and with no DB mutation. It prevents
spending a scarce one-use proof against a condition that is internal and
addressable, and it identifies a reporting defect that would otherwise keep
mislabelling every future shortage as a market outcome.

## 10. What improves

- The Cycle-2 certificate is located, validated and fully transcribed.
- `TRACKING_STATE_CAPACITY_BLOCKED` is established as the governing shortage.
- `HONEST_EXHAUSTION` is proven, so the attempt itself is exonerated.
- The certificate/reporting contract violation is pinned to a named surface with
  the code's own contract quoted against the observed behaviour.
- The prior closeout's "external supply" characterisation is corrected on the
  record.
- The composite `execution_id` binding inconsistency is documented.

## 11. What remains locked

Authorization creation and consumption, four-token proof execution, campaign
start, six-token proof and capacity widening, WINDOW_1H rerun, WINDOW_12H /
WINDOW_24H, retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events,
paper audits, PnL, wallets, private keys, real funds, live execution, paid APIs,
scoring/ranking/confidence, embeddings and vectors. Solana memecoin-only and
paper-only remain in force. No repair was implemented in this lane.

## 12. Functionality Risks / Setbacks / Efficiency Blockers

- The reporting defect is **diagnosis-corrupting**: every shortage currently
  surfaces as an insufficient-pool market conclusion regardless of the true
  classification. Any operator reading only host artifacts will reach the wrong
  decision, as happened here.
- `report.exhaustion_certificate` and `report.shortage_classification` are `null`
  while the certificate exists in the DB, so host-artifact-only audits cannot
  detect the divergence — it is only visible by reading the authoritative DB.
- The composite `execution_id` breaks the convention used by the 11 prior
  certificates. A canonical-execution-id query returns **zero rows**, which is
  how the preceding audit missed it. Any future tooling keyed on execution id
  will silently miss Cycle-2 certificates.
- `terminal-summary.json` reports `required_token_capacity: 2` while the
  certificate requires `4`; the four-token requirement is not represented in the
  host artifact.
- The certificate `created_at` (`19:53:32.356663`) precedes the source requests it
  cites (`19:53:38`–`19:53:45`), indicating the timestamp is captured at attempt
  start and persisted at completion. Not a fault, but it defeats naive
  chronological correlation.
- Four geckoterminal rate-limit `STALE` failures occurred in the run window and
  are not represented in the certificate's counters. They fell outside the
  liquidity stage, so precedence was unaffected here — but under a different
  ordering they would have selected `STALE_EVIDENCE_SHORTAGE`, so the boundary
  deserves explicit test coverage.
- The tracking-state exclusions themselves are not yet explained: this lane
  establishes *that* reserve entries are `EXCLUDED`/`REMOVED`, not *why*.

## 13. Exact next permitted lane

`V2-9.8B Cycle-2 Exhaustion-Certificate Reporting Contract Repair Design` —
design-only, no code change in that lane either. It must:

1. specify propagation of `exhaustion_certificate`, `shortage_classification`,
   and `last_reason_discovery_could_not_continue` into `terminal-summary.json`,
   `child-terminal.json`, and the pre-admission attempt terminal cause;
2. specify that `TRACKING_STATE_CAPACITY_BLOCKED` must surface
   `tracking_terminal_cause` / `COOLDOWN_REOPEN_REQUIRED` and never
   `BLOCKED_INSUFFICIENT_ELIGIBLE_CANDIDATE_POOL`, per the existing docstring
   contract;
3. decide whether the certificate `execution_id` must carry the canonical
   execution id alongside the composite adapter key;
4. define the focused RED tests, including the stale/rate-limited precedence
   boundary.

A separate lane should then investigate why liquidity-proven reserve entries are
`EXCLUDED`/`REMOVED`. No authorization may be created until both close.
