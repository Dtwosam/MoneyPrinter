# Printer V1 V2-9.8B WINDOW_15M Source-Specific Candidate Temporal Contract Design

## Verdict

`V2_9_8B_WINDOW_15M_SOURCE_SPECIFIC_TEMPORAL_CONTRACT_DESIGN_COMPLETE`

This is a design-only closeout. It defines the repair required after the consumed
`WINDOW_15M` execution failed because source-specific candidates were passed to
older Pump-only temporal consumers.

No production code, test, database, authorization package, application marker,
failed-run artifact, provider, discovery, Scheduler, campaign, lifecycle, or
memory path is changed or executed by this design.

## 1. Baseline and incident identity

| Item | Value |
| --- | --- |
| Baseline branch | `agent/v2-9-8b-window-15m-fresh-authorization-after-historical-evidence-repair` |
| Baseline full HEAD | `40b6f27dcd3d3e4bf88d12d8b10c6fd22f5139d5` |
| Design branch | `agent/v2-9-8b-window-15m-source-specific-temporal-contract-design` |
| Consumed authorization | `V2_9_8B_WINDOW_15M_AUTH_20260806T103951Z` |
| Failed execution | `20260806T105403Z-cde8a9b58daf` |
| Wrapper terminal | `CHILD_EXITED_NONZERO` |
| Campaign terminal | `TERMINAL_FAILED` |
| First terminal cause | `AttributeError:'SourceSpecificCandidateAdmission' object has no attribute 'block_time'` |
| Authorization disposition | `CONSUMED_CHILD_EXITED_NONZERO` — permanently non-reusable |

The failed run completed cleanup, released its lease, left zero active locked
Scheduler work, and terminalized its campaign/run/cycle/supervision state.

The authoritative database was lawfully mutated by the consumed attempt and must
not be restored or replaced:

| Field | Post-failure identity |
| --- | --- |
| path | `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3` |
| size | `68718592` |
| SHA-256 | `d4f9e145fffb4010294c5ecfe6027770a11f9d090dd6701a0abb4dce7d83c0d7` |
| inode | `1230526` |
| mtime_ns | `1786013653208178741` |

The run made 11 governed source calls, recorded 8 source responses and 3 source
failures, inserted its terminal campaign control rows, and added bounded discovery
and exact-market evidence. Those rows are preserved as failed-run evidence.

## 2. Controlling source-stack decisions

This design remains inside the active Printer V1 source stack and preserves:

- active bounded `WINDOW_15M` memory growth only;
- Solana-only, Solana-memecoin-only, paper-only V1;
- multi-source candidate admission;
- exact Pump/PumpSwap evidence only when Pump-specific facts are claimed;
- exact present-pool admission for lawful unknown-origin/non-Pump market nominees;
- age as context, never candidate-selection eligibility;
- Source Governor and Central Scheduler ownership;
- no score, rank, confidence, weight, quota, preference, or source bias;
- no retrieval, paper decision, BUY/SELL/HOLD, position, trade, audit, or PnL unlock;
- `WINDOW_5M_MICRO_EVENT` support-only;
- no `WINDOW_1H`, `4H`, `12H`, or `24H` expansion.

## 3. Root cause

### 3.1 Correct new carrier

The source-specific admission repair introduced:

`SourceSpecificCandidateAdmission`

It correctly distinguishes:

- `DIRECT_PUMP_PUMPSWAP`; and
- `MARKET_PRESENT_POOL`.

A direct candidate may carry an exact Pump graduation/migration time through its
`origin_proof`. A market nominee proves a current exact Solana mint+pool market
observation but does not claim a Pump create, migration, or graduation time.

Therefore the source-specific carrier correctly did **not** expose one universal
`block_time` property.

### 3.2 Stale Pump-only consumers

Two production consumers still assume every admitted candidate is a
`FixtureOriginProof`:

1. `_full_pilot_graduation_diagnostics` emits:

   `origin_block_time_epoch = int(proof.block_time)`

2. `_evaluate_holder_eligibility` calls:

   `schedule_maturation(... observed_at=str(proof.block_time), ...)`

Static call order proves the diagnostics call is the earliest reachable stale
access in the permanent operational path: it runs immediately after
`_graduated_admission` and before the holder funnel. The terminal JSON does not
contain a Python stack trace, but the code order makes this the likely immediate
fault site. The holder funnel contains a second guaranteed failure if only the
reporting access is repaired.

### 3.3 Related reporting drift

The old diagnostics owner also remains semantically Pump-only:

- helper name says `graduation`;
- `eligibility_rule` says `GRADUATION_ONLY`;
- market-present-pool candidates can be admitted by `_graduated_admission` but
  reported as not selectable;
- `graduated_candidate_count` excludes lawful market nominees;
- market candidates would be forced into `origin_block_time_epoch`.

This is contract drift from the adopted source-specific admission model.

### 3.4 Paths that are not defective

The following are not to be generalized in this repair:

- `run_snapshot_readiness` obtains only direct Pump acquisition
  `FixtureOriginProof` objects and lawfully calls Pump-origin snapshot maturity;
- `snapshot_maturity.evaluate_snapshot_maturity` is explicitly a finalized Pump
  origin contract and remains unchanged;
- `CombinedPumpfunCampaignExecutor` uses the validated
  `memory_activation_set` retained-evidence path for permanent source-specific
  activation and does not require a universal candidate `block_time`;
- `OriginLifecycleCampaignDriver` does not dereference candidate `block_time`.

## 4. Design decision: explicit temporal authority

### 4.1 No universal `block_time`

Do not add any compatibility property named `block_time` to
`SourceSpecificCandidateAdmission`.

Do not return `0`, current time, evaluation time, file time, request time, or
expiry-derived time as a fake Pump origin time.

### 4.2 Temporal authority vocabulary

Add an explicit categorical authority contract:

```text
DIRECT_PUMP_GRADUATION_TIME
RETAINED_MARKET_OBSERVATION_TIME
```

Recommended typed carrier:

```python
@dataclass(frozen=True)
class CandidateTemporalContext:
    temporal_authority: CandidateTemporalAuthority
    admission_observed_at_utc: str
    pump_origin_block_time_epoch: int | None
```

`SourceSpecificCandidateAdmission` owns exactly one validated
`temporal_context`.

### 4.3 Direct Pump/PumpSwap construction

For `DIRECT_PUMP_PUMPSWAP`:

- require the existing exact direct Pump evidence;
- require `origin_proof.block_time` to be a positive integer;
- set `temporal_authority = DIRECT_PUMP_GRADUATION_TIME`;
- set `pump_origin_block_time_epoch` to that exact integer;
- convert that epoch to one timezone-aware UTC ISO timestamp and store it as
  `admission_observed_at_utc`;
- preserve the meaning as Pump migration/graduation time, never Pump create time
  unless the existing direct carrier explicitly proves create-native origin.

Invalid or missing direct time blocks source-specific admission with a typed
error before reporting, holder transport, or lifecycle work.

### 4.4 Market-present-pool construction

For `MARKET_PRESENT_POOL`:

- set `temporal_authority = RETAINED_MARKET_OBSERVATION_TIME`;
- set `pump_origin_block_time_epoch = None`;
- source `admission_observed_at_utc` only from the exact current market evidence
  already carried by the eligible-reserve candidate:
  - top-level `liquidity_observed_at`; or
  - nested `liquidity.liquidity_observed_at`;
- validate that the timestamp is non-empty, parseable, timezone-aware, and
  normalizable to UTC;
- retain the existing exact mint, exact pool, source request/response, freshness,
  and evidence-expiry contracts;
- do not infer Pump origin, migration, graduation, or token birth time.

The permanent-discovery owner already emits `liquidity_observed_at` for exact
market evidence. The admission owner consumes that field; it must not invent a
new fallback.

Missing or malformed market observation time blocks with a typed error such as:

```text
MARKET_CANDIDATE_OBSERVATION_TIME_MISSING
MARKET_CANDIDATE_OBSERVATION_TIME_INVALID
```

The block occurs before holder transport.

### 4.5 Legacy direct carrier compatibility

The shared holder funnel still serves direct `FixtureOriginProof` callers.
Introduce one narrow temporal resolver used by the holder owner:

```text
SourceSpecificCandidateAdmission
  -> temporal_context.admission_observed_at_utc

FixtureOriginProof
  -> exact positive block_time converted to timezone-aware UTC ISO
```

Unsupported candidate objects fail closed. The resolver does not use duck-typed
`getattr(..., "block_time", default)` fallbacks.

## 5. Holder maturation contract

`holder_reliability_budget_control.schedule_maturation` remains the durable
maturation owner.

The caller must supply a truthful source-specific ISO observation time:

| Candidate authority | `schedule_maturation.observed_at` |
| --- | --- |
| Direct Pump/PumpSwap | exact UTC conversion of direct graduation/migration block time |
| Market present pool | exact retained current market-observation timestamp |
| Legacy direct Pump proof | exact UTC conversion of its positive block time |

Requirements:

- temporal resolution occurs before `schedule_maturation` and before holder I/O;
- a missing/invalid temporal contract blocks the candidate without source calls;
- no slot ordinal changes authority;
- the current `MATURATION_THRESHOLD_SECONDS = None` policy remains unchanged;
- this repair does not introduce a new waiting period or age gate;
- if maturation is enabled later, the persisted source-honest timestamp is
  already parseable and meaningful.

The current raw integer-string call is removed. Even for legacy direct proofs,
`observed_at` becomes timezone-aware ISO rather than `str(epoch)`.

## 6. Source-honest admission reporting

Replace or refactor `_full_pilot_graduation_diagnostics` into a candidate-admission
report owner that supports both contracts.

The outer `full_pilot_admission` field may remain for compatibility, but its
contents must be source-honest.

### 6.1 Per-candidate record

Each record includes:

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

Market nominee:

```text
admission_authority = MARKET_PRESENT_POOL
admission_state = CANDIDATE_PRESENT_POOL_ELIGIBLE
selectable = true
pump_origin_claimed = false
pump_origin_block_time_epoch = null
admission_observed_at_utc = exact retained market observation
```

Market candidates must not be labelled Pump-origin, Pump-migrated,
Pump-graduated, `LATEST_GRADUATED`, or registry-backed unless separately proven.

### 6.2 Aggregate record

For the permanent source-specific path:

```text
eligibility_rule = SOURCE_SPECIFIC_PRESENT_POOL_OR_DIRECT_PUMP
candidate_admitted_count = all lawfully admitted candidates
market_present_pool_count = MARKET_PRESENT_POOL candidates
direct_pump_pumpswap_count = DIRECT_PUMP_PUMPSWAP candidates
```

Legacy non-permanent direct-Pump reporting may retain:

```text
eligibility_rule = GRADUATION_ONLY
```

Do not keep one misleading `graduated_candidate_count` as the sole count for a
mixed source-specific universe.

Age remains context only. For market candidates, Pump-origin age is explicitly:

```text
UNKNOWN_NOT_CLAIMED
```

## 7. Snapshot-maturity decision

Do not modify or broaden `snapshot_maturity.evaluate_snapshot_maturity`.

It remains a Pump-origin-specific owner used by the separate
`SNAPSHOT_READINESS` mode, whose candidate universe is direct Pump acquisition
`FixtureOriginProof` objects.

For the permanent source-specific `FULL_PILOT` path:

- market nominees never enter Pump-origin snapshot maturity;
- no neutral 900-second market maturity gate is introduced;
- retained market freshness and evidence expiry remain the applicable market-time
  contracts;
- direct candidates retain their existing direct temporal evidence;
- age remains context and never selection eligibility.

A focused test must prove that a market candidate cannot be passed to
`evaluate_snapshot_maturity` through the permanent operational path.

## 8. Mixed two-slot behavior

Temporal authority is candidate-local and independent of selection order.

| Composition | Required behavior |
| --- | --- |
| market + market | each uses its own exact retained market observation time; no Pump time required or synthesized |
| direct + direct | each uses its own exact direct graduation/migration time |
| market + direct | market uses retained market time; direct uses direct Pump time; neither inherits the other's authority |

No source quota, preference, rank, score, confidence, weighting, or slot-derived
provenance is introduced.

## 9. Downstream lifecycle boundary

The repair must perform a static scan of every production `.block_time` consumer.
Each occurrence must be classified as either:

1. direct-Pump-only and structurally unreachable by
   `SourceSpecificCandidateAdmission`; or
2. source-specific and repaired to use the explicit temporal contract.

Expected source-specific repairs are limited to:

- candidate admission diagnostics; and
- shared holder maturation input.

The exact retained-evidence `memory_activation_set` remains the authority passed
to `CombinedPumpfunCampaignExecutor`. No conversion of a market candidate into a
fake `FixtureOriginProof` is permitted.

## 10. Failed-run evidence and database preservation

Implementation must preserve:

- consumed authorization package;
- external manifest, marker, terminal, stdout, and stderr files;
- failed campaign/run/cycle/supervision rows;
- source requests `1940–1950`;
- source responses `1730–1737`;
- source failures `210–212`;
- 76 added discovery-reserve-layer rows;
- 40 added exact-market-state rows;
- all other lawful failed-attempt mutations.

Do not restore the pre-run DB, delete terminal rows, rewrite evidence, clean the
consumed application directory, or reuse the authorization.

## 11. Expected implementation boundary

Production changes should be limited to:

- `src/printer_v1/operator_cli/graduated_supply_front_door.py`
  - explicit temporal authority/context on `SourceSpecificCandidateAdmission`;
  - source-specific timestamp construction and validation;
- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
  - source-specific holder maturation timestamp resolution;
  - source-honest admission reporting;
- focused tests;
- implementation and closeout documentation.

`src/printer_v1/scheduler/snapshot_maturity.py` should remain unchanged unless
implementation inspection proves a direct-only assertion is required. A new
market maturity state or neutral age gate is not approved.

No DB migration is expected or justified.

Do not change:

- provider adapters or transports;
- Source Governor;
- Central Scheduler;
- candidate discovery, selection order, or capacity;
- liquidity floor or freshness;
- holder policy or operation ceilings;
- retained evidence roles;
- authorization/manifest/marker framework;
- lifecycle cadence or window policy;
- memory promotion, retrieval, or financial capability code.

## 12. Focused proof contract

Use disposable databases, fixture transports, and deterministic clocks only.
No provider or authoritative DB write is allowed.

Minimum proof:

1. failed-run-shaped market candidate constructs a valid
   `RETAINED_MARKET_OBSERVATION_TIME` context;
2. market candidate missing observation time blocks before holder transport;
3. malformed or naive market timestamp blocks;
4. market candidate never exposes or requires `.block_time`;
5. direct candidate constructs exact `DIRECT_PUMP_GRADUATION_TIME` context;
6. missing/non-positive direct block time blocks;
7. shared holder funnel passes market observation time to `schedule_maturation`;
8. shared holder funnel converts direct epoch to UTC ISO;
9. market/market, direct/direct, and mixed pairs retain independent temporal
   authority in frozen order;
10. admission reporting marks both lawful states selectable;
11. market reporting has `pump_origin_claimed=false` and null Pump block time;
12. direct reporting preserves exact Pump block time;
13. permanent market candidates never call Pump snapshot maturity;
14. direct `SNAPSHOT_READINESS` maturity behavior remains unchanged;
15. memory activation still uses exact retained request/response/transport
   authority and creates no new source rows;
16. no generic source-specific `proof.block_time` dereference remains;
17. existing source-specific admission, exact-member, orientation, retained
   evidence, holder, and mixed-slot tests remain green;
18. `SELECTED_MINT_NOT_IN_REGISTRY` remains absent;
19. no retrieval or financial capability delta exists.

Use minimum sufficient risk-based verification. Do not run the full repository
suite unless the repair becomes unexpectedly cross-cutting.

## 13. Money-usefulness contribution

The repair allows lawful current Solana market candidates to reach bounded
memory observation without fabricating Pump history. It keeps direct Pump
candidates anchored to their real graduation time while anchoring market nominees
to the exact time Printer actually observed their current market. That improves
usable candidate coverage while preserving truthful historical context for later
memory comparison.

## 14. What the repair improves

- closes the immediate `AttributeError`;
- prevents the same defect from recurring in the holder funnel;
- removes Pump-only temporal assumptions from mixed candidate reporting;
- makes holder scheduling timestamps parseable and source-honest;
- preserves exact multi-source admission without inventing lineage;
- keeps direct Pump snapshot maturity intact;
- supports market/market, direct/direct, and mixed two-slot campaigns.

## 15. What remains locked

This design and its implementation do not unlock:

- another authorization or run;
- automatic retry, rerun, resume, restart, or successor;
- `WINDOW_1H`, `4H`, `12H`, or `24H`;
- retrieval or dirty-memory use;
- paper decisions or BUY/SELL/HOLD;
- positions, trades, audits, or PnL;
- wallets, private keys, signing, real funds, or live execution;
- paid APIs;
- scoring, ranking, confidence, weighting, embeddings, or vectors.

## 16. Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Required control |
| --- | --- |
| Fake Pump origin time added for compatibility | No universal `block_time`; market Pump epoch must be null |
| Market timestamp silently falls back to current time | Consume only the exact existing market-observation field; typed block otherwise |
| Holder maturation changes behavior | Preserve `MATURATION_THRESHOLD_SECONDS=None`; change only truthful input representation |
| Direct snapshot readiness regresses | Keep direct-only snapshot maturity unchanged and run nearest tests |
| Reporting remains Pump-biased | Add explicit admission authority/state/counts and source-honest fields |
| Mixed slots share one authority | Candidate-local immutable temporal context; mixed fixture proof |
| Repair hides failed evidence | Preserve DB and all consumed-run artifacts byte-for-byte |
| Scope expands into discovery/lifecycle redesign | Limit production changes to carrier construction and two temporal consumers |

## 17. Exact next step

Implement this design from the design commit on a new repair branch, run focused
disposable proof, produce an implementation closeout, and stop.

Do not create a fresh authorization or execute another campaign until the repair
commit is independently inspected and a later explicit authorization lane binds
the then-current code and database identity.
