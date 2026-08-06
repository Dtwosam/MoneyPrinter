# Printer V1 V2-9.8B WINDOW_15M Source-Specific Candidate Temporal Contract Repair Closeout

## Verdict

`V2_9_8B_WINDOW_15M_SOURCE_SPECIFIC_TEMPORAL_CONTRACT_REPAIR_PASS`

This is implementation, focused disposable proof, and closeout only.

- No authorization was created, renewed, edited, moved, or reused.
- No real Printer campaign was executed.
- No provider, discovery, Source Governor, Central Scheduler, factory, lifecycle,
  or memory runtime was invoked.
- The authoritative database identity is unchanged before and after this repair.
- Consumed authorization `V2_9_8B_WINDOW_15M_AUTH_20260806T103951Z` and failed
  execution `20260806T105403Z-cde8a9b58daf` evidence remain preserved.

## Baseline and branch

| Item | Value |
| --- | --- |
| Required baseline branch | `agent/v2-9-8b-window-15m-source-specific-temporal-contract-design` |
| Required full starting HEAD | `caf86d885265b0f5ec8d1cb1581c9d4af1ded8d0` |
| Repair branch | `agent/v2-9-8b-window-15m-source-specific-temporal-contract-repair` |
| Final full HEAD | `03cd69f3de0efad6b87afa56af5f2ced0bd0a34a` |
| Design controlling document | `docs/printer-v1-v2-9-8b-window-15m-source-specific-temporal-contract-design.md` |
| Consumed authorization | `V2_9_8B_WINDOW_15M_AUTH_20260806T103951Z` |
| Failed execution | `20260806T105403Z-cde8a9b58daf` |
| First terminal cause | `AttributeError:'SourceSpecificCandidateAdmission' object has no attribute 'block_time'` |
| Commit subject | `Repair source-specific candidate temporal contract` |

Starting tracked tree and index were clean. Existing untracked operational
evidence packages (Migration-050 and prior/current authorization packages)
were preserved and were not staged.

## Exact files changed

Production:

- `src/printer_v1/operator_cli/graduated_supply_front_door.py`
- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`

Focused proof:

- `tests/test_v2_9_8b_window_15m_source_specific_temporal_contract_repair.py` (new)
- `tests/test_v2_9_8b_window_15m_source_specific_admission_retained_evidence_repair.py`
  (fixture only: market supply candidates now carry `liquidity_observed_at`)

Documentation:

- `docs/printer-v1-v2-9-8b-window-15m-source-specific-temporal-contract-repair-closeout.md`

Not modified:

- `src/printer_v1/scheduler/snapshot_maturity.py`
- providers, Source Governor, Central Scheduler, discovery ownership
- authorization/manifest/marker code
- DB schema / migrations
- selection ordering, capacity, `$3,000` floor, evidence freshness

## Root cause

`SourceSpecificCandidateAdmission` correctly supports:

- `DIRECT_PUMP_PUMPSWAP`
- `MARKET_PRESENT_POOL`

Market nominees do not prove a Pump origin or graduation timestamp and therefore
correctly do **not** expose a universal `block_time`.

Two stale Pump-only consumers still assumed every admitted candidate was a
`FixtureOriginProof`:

1. `_full_pilot_graduation_diagnostics` → `int(proof.block_time)`
2. `_evaluate_holder_eligibility` → `schedule_maturation(... observed_at=str(proof.block_time))`

The permanent source-specific path admitted market nominees, then hit the first
stale access during full-pilot admission reporting, producing:

```text
AttributeError: 'SourceSpecificCandidateAdmission' object has no attribute 'block_time'
```

The holder funnel contained the same guaranteed failure if only reporting were
repaired.

## Explicit temporal authority model

```text
CandidateTemporalAuthority
  DIRECT_PUMP_GRADUATION_TIME
  RETAINED_MARKET_OBSERVATION_TIME

CandidateTemporalContext
  temporal_authority
  admission_observed_at_utc
  pump_origin_block_time_epoch
```

`SourceSpecificCandidateAdmission` owns exactly one validated
`temporal_context`.

No universal `block_time` property was added.

No duck-typed defaults such as `getattr(candidate, "block_time", 0)` were added.

No origin time is synthesized from zero, current time, evaluation time, evidence
expiry, source request time, DB/file timestamps, or slot ordinal.

## Direct Pump/PumpSwap construction

For `DIRECT_PUMP_PUMPSWAP`:

- existing exact direct Pump evidence requirements remain;
- positive integer direct graduation/migration block time is required;
- authority = `DIRECT_PUMP_GRADUATION_TIME`;
- `pump_origin_block_time_epoch` = exact epoch;
- `admission_observed_at_utc` = timezone-aware UTC ISO conversion of that epoch;
- graduation/migration meaning is preserved (not relabelled as Pump create time).

Stable blockers:

```text
DIRECT_CANDIDATE_GRADUATION_TIME_MISSING
DIRECT_CANDIDATE_GRADUATION_TIME_INVALID
```

Missing, zero, negative, boolean, or non-integer values fail closed before
reporting, holder transport, or lifecycle work.

## Market present-pool construction

For `MARKET_PRESENT_POOL`:

- authority = `RETAINED_MARKET_OBSERVATION_TIME`;
- `pump_origin_block_time_epoch` = `None`;
- timestamp sourced only from:
  - top-level `liquidity_observed_at`; or
  - nested `liquidity.liquidity_observed_at`;
- value must be non-empty, parseable, and timezone-aware;
- normalized to UTC ISO;
- exact mint, pool, freshness, request/response, and evidence-expiry ownership
  remain unchanged;
- no Pump origin, migration, graduation, or registry claim is made.

Stable blockers:

```text
MARKET_CANDIDATE_OBSERVATION_TIME_MISSING
MARKET_CANDIDATE_OBSERVATION_TIME_INVALID
```

No fallback to now, evaluated_at, request time, or expiry.

## Holder maturation resolution

Shared resolver on the authoritative campaign owner:

```text
SourceSpecificCandidateAdmission
  → temporal_context.admission_observed_at_utc

FixtureOriginProof
  → exact positive block_time converted to UTC ISO

unsupported
  → UNSUPPORTED_CANDIDATE_TEMPORAL_AUTHORITY (fail closed)
```

Replaces:

```python
observed_at=str(proof.block_time)
```

Resolution occurs before `schedule_maturation` and before holder transport.

Preserved:

```text
MATURATION_THRESHOLD_SECONDS = None
```

No wait, maturity gate, age gate, request, retry, or Scheduler operation was
added.

## Reporting changes

Outer key remains `full_pilot_admission` for compatibility. Contents are now
source-honest.

Per-candidate fields:

```text
mint_identity
admission_authority
admission_state
selectable
temporal_authority
admission_observed_at_utc
pump_origin_claimed
pump_origin_block_time_epoch
market_identity
token_age_context
```

Direct candidate:

```text
admission_authority = DIRECT_PUMP_PUMPSWAP
admission_state = GRADUATION_ELIGIBLE
selectable = true
pump_origin_claimed = true
pump_origin_block_time_epoch = exact value
```

Market candidate:

```text
admission_authority = MARKET_PRESENT_POOL
admission_state = CANDIDATE_PRESENT_POOL_ELIGIBLE
selectable = true
pump_origin_claimed = false
pump_origin_block_time_epoch = null
admission_observed_at_utc = exact retained market timestamp
token_age_context = UNKNOWN_NOT_CLAIMED
```

Permanent source-specific aggregates:

```text
eligibility_rule = SOURCE_SPECIFIC_PRESENT_POOL_OR_DIRECT_PUMP
candidate_admitted_count
market_present_pool_count
direct_pump_pumpswap_count
```

Legacy non-permanent direct-Pump reporting retains:

```text
eligibility_rule = GRADUATION_ONLY
```

Market nominees are never labelled Pump-origin, Pump-migrated, Pump-graduated,
`LATEST_GRADUATED`, or registry-backed. Age remains context, not eligibility.

## Snapshot-maturity preservation

`evaluate_snapshot_maturity` is unchanged.

`run_snapshot_readiness` remains direct-Pump-only and continues using exact
`FixtureOriginProof.block_time`.

The permanent source-specific operational path never passes market nominees to
Pump-origin snapshot maturity.

No neutral 900-second market maturity gate was introduced.

## Static `.block_time` consumer classification

Production `proof.block_time` occurrences after repair:

| Location | Classification |
| --- | --- |
| `authoritative_live_operational_campaign.py` holder resolver (`FixtureOriginProof` branch only) | Reachable by legacy direct proofs only; guarded by `isinstance(proof, FixtureOriginProof)` |
| `authoritative_live_operational_campaign.py` legacy diagnostics branch | Direct-Pump-only reporting path for non-source-specific proofs |
| `authoritative_live_operational_campaign.py` `run_snapshot_readiness` `pump_block_time=proof.block_time` | Structurally direct-Pump-only (`SNAPSHOT_READINESS`) |
| `combined_executor.py` graduation-native observation payload | FixtureOriginProof graduation-native path; permanent source-specific activation uses frozen `memory_activation_set` and does not convert market nominees into fake `FixtureOriginProof` objects |

Reachable source-specific repairs completed:

- source-specific admission reporting;
- shared holder maturation.

No market nominee is converted into a fake `FixtureOriginProof`.

The frozen retained-evidence `memory_activation_set` remains the source-specific
activation authority.

## Focused test commands and exact results

```bash
.venv/bin/pytest \
  tests/test_v2_9_8b_window_15m_source_specific_temporal_contract_repair.py \
  tests/test_v2_9_8b_window_15m_source_specific_admission_retained_evidence_repair.py \
  tests/test_v2_9_8b_window_15m_exact_market_member_binding_repair.py \
  tests/test_v2_9_8b_window_15m_dexscreener_orientation_binding_repair.py \
  tests/test_v2_9_8b_window_15m_retained_evidence_exactness_repair.py \
  tests/test_v2_9_7e_36_38_snapshot_maturity_boundary.py \
  tests/test_v2_9_7e_22_holder_reliability_budget_repair.py \
  tests/test_v2_9_7e_45_holder_reserve_funnel.py \
  -q
```

Primary temporal suite:

```text
tests/test_v2_9_8b_window_15m_source_specific_temporal_contract_repair.py
34 passed
```

Combined focused suite (commands above):

```text
123 passed, 5 subtests passed
```

Also verified:

- Python compilation of both changed production modules: OK
- `git diff --check`: clean
- `SELECTED_MINT_NOT_IN_REGISTRY` remains absent from production front-door code
- no `confidence_score` / `rank_weight` / `source_preference` / `weighted_score`
  added in changed production files

### Unrelated pre-existing failures (recorded, not expanded)

These fail on the design HEAD without this repair and are outside the temporal
contract scope:

1. `tests/test_v2_9_8b_2_holder_budget_supervision_repair.py::HolderBudgetArithmeticTests::test_historical_whole_table_base_work_is_rejected_with_exact_values`
   - `KeyError: 'base_operations'`
2. Several `tests/test_v2_9_7e_11_authoritative_live_operational_campaign.py` natural-lifecycle proofs
   - `AttributeError: 'NoneType' object has no attribute 'holder_reserve_candidates'`
   - Reproduced on design HEAD with unrepaired production files

## DB identity before and after

| Field | Before | After |
| --- | --- | --- |
| path | `data/printer_v1.sqlite3` | same |
| size | `68718592` | `68718592` |
| SHA-256 | `d4f9e145fffb4010294c5ecfe6027770a11f9d090dd6701a0abb4dce7d83c0d7` | same |
| inode | `1230526` | `1230526` |
| mtime_ns | `1786013653208178741` | `1786013653208178741` |
| integrity | `ok` | `ok` |
| foreign-key violations | `0` | `0` |
| WAL/SHM/journal | absent | absent |

Exact DB identity is unchanged. No restore or mutation was performed.

## Failed evidence preservation

Preserved:

- consumed authorization package `V2_9_8B_WINDOW_15M_AUTH_20260806T103951Z`
- external application manifest, marker, terminal, stdout, and stderr
- terminal campaign/run/cycle/supervision rows
- source requests `1940–1950`
- source responses `1730–1737`
- source failures `210–212`
- failed-attempt reserve and exact-market evidence
- all previous authorization packages and staging evidence

No failed evidence was deleted or rewritten. The consumed authorization was never
reused, edited, moved, or regenerated.

## Zero runtime / provider work

Confirmed for this lane:

- no public one-shot wrapper execution;
- no real operational command;
- no authorization create/consume;
- no application marker create;
- no provider contact;
- no discovery run;
- no Scheduler or campaign runtime start;
- no lifecycle windows or memory generation;
- no authoritative DB mutation or restore;
- no retrieval or financial path unlock.

## Money-usefulness contribution

Lawful current Solana market candidates can now reach bounded memory observation
without fabricating Pump history. Direct Pump candidates remain anchored to their
real graduation time. Market nominees are anchored to the exact time Printer
observed their current market. That improves usable candidate coverage while
preserving truthful historical context for later memory comparison.

## What the repair improves

- closes the immediate `AttributeError` on market nominees;
- prevents the same defect in the holder funnel;
- removes Pump-only temporal assumptions from mixed candidate reporting;
- makes holder scheduling timestamps parseable and source-honest;
- preserves exact multi-source admission without inventing lineage;
- keeps direct Pump snapshot maturity intact;
- supports market/market, direct/direct, and mixed two-slot temporal independence.

## What remains locked

- another authorization or run;
- automatic retry, rerun, resume, restart, or successor;
- `WINDOW_1H`, `4H`, `12H`, or `24H`;
- retrieval or dirty-memory use;
- paper decisions or BUY/SELL/HOLD;
- positions, trades, audits, or PnL;
- wallets, private keys, signing, real funds, or live execution;
- paid APIs;
- scoring, ranking, confidence, weighting, embeddings, or vectors.

## Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Control applied |
| --- | --- |
| Fake Pump origin time for market nominees | No universal `block_time`; market Pump epoch is null |
| Silent current-time fallback for market observation | Only retained market observation fields; typed missing/invalid blockers |
| Holder maturation behavior change | `MATURATION_THRESHOLD_SECONDS=None` preserved; only truthful ISO input |
| Direct snapshot readiness regression | `snapshot_maturity.py` unchanged; nearest maturity tests green |
| Pump-biased reporting remains | Explicit admission authority/state/counts and source-honest fields |
| Mixed slots share one authority | Candidate-local immutable temporal context; mixed fixture proof |
| Repair hides failed evidence | DB identity and consumed-run artifacts preserved byte-for-byte |
| Scope expands into discovery/lifecycle redesign | Production changes limited to carrier construction and two temporal consumers |

## Exact next step

Stop after this implementation, focused disposable proof, and closeout.

A later explicit lane may inspect this repair commit and prepare **one** fresh
authorization bound to the repaired code and the then-current DB identity.

Do **not** create another authorization in this lane.
