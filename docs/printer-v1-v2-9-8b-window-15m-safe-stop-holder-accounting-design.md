# Printer V1 — V2-9.8B `WINDOW_15M` Safe-Stop / Holder-Accounting Repair Design

**Date:** 2026-08-05  
**Lane:** `V2-9.8B — WINDOW_15M Safe-Stop Preflight and Holder-Accounting Design`  
**Type:** Design/specification only  
**Baseline branch:** `agent/v2-9-8b-window-15m-freeze-holder-budget-decoupling-repair`  
**Baseline HEAD:** `a1bcc7d8ed8f5e93c9c5f2cfd5432eeb06f087f1`  
**Required audit:** `docs/printer-v1-v2-9-8b-window-15m-safe-stop-holder-accounting-audit.md`

## 1. Design verdict

`V2_9_8B_WINDOW_15M_SAFE_STOP_HOLDER_ACCOUNTING_DESIGN_PASS`

This design approves one future implementation lane containing three inseparable
repair units:

1. **authorization-bound operational database target binding;**
2. **exact holder-stage six-unit identity integration;**
3. **complete continuous-proof terminal evidence retention.**

The design does not authorize implementation, tests, proof execution, provider
contact, a real authorization, or authoritative database mutation.

## 2. Design goals

The successor implementation must allow one exact wrapper-authorized disposable
Migration-052 database to exercise the real operational-persistent `WINDOW_15M`
lifecycle without weakening the production authoritative-database rule.

It must also ensure every attempted holder transport is represented by exact existing
`TransportOperationIdentity` evidence in both:

- the campaign six-unit owner; and
- the independent action-local ledger.

Finally, the proof harness must retain enough child and campaign evidence to diagnose
the first terminal cause without rerunning.

## 3. Non-negotiable invariants

The implementation must preserve:

- Solana-only;
- Solana memecoin-only;
- paper-only;
- no wallet, private key, signing, funds, or execution;
- no paid API;
- no score, rank, confidence, weight, embedding, or vector;
- no Source Governor bypass;
- no Central Scheduler bypass;
- `WINDOW_5M_MICRO_EVENT` support-only;
- first operational target `WINDOW_15M`;
- no production 1h/4h/12h/24h activation;
- no retrieval;
- no paper decisions;
- no BUY/SELL/HOLD;
- no positions, trade events, paper audits, or PnL;
- operation ceiling `45`;
- zero-transport validation charge `9`;
- snapshot reservations `2 + 4`;
- holder pre-attempt requirement `5`;
- permanent holder-stage ceiling `8`;
- holder context independent of memory-observation admission;
- `FULLY_ELIGIBLE` only after a real holder pass;
- exact two selected plus two alternates at freeze depth;
- no retry, resume, restart, or successor.

No ceiling or gate may be weakened to make the proof pass.

## 4. Architecture overview

```text
one-shot wrapper authorization
-> public operational activation preflight
-> immutable OperationalDatabaseTargetBinding
-> campaign identity and exact DB target binding
-> governed discovery / permanent observation supply
-> immutable pre-holder accounting snapshot
-> budget-bounded holder collection
   -> exact holder TransportOperationIdentity records
   -> action-local observer at measurement time
   -> one sealed HOLDER_SAFETY campaign stage
-> request / six-unit / action-local reconciliation
-> two-slot handoff
-> lifecycle factory validates the same DB binding
-> two logical 900-second WINDOW_15M lifecycles
-> terminal report
-> complete retained proof package and hash manifest
```

There remains one Source Governor, one Central Scheduler, one campaign six-unit owner,
one action-local observer, one lifecycle factory, and one terminal report.

## 5. Repair Unit A — Authorization-bound operational DB target

### 5.1 Problem

The public coordinator and lifecycle factory currently resolve the operational DB
independently.

The proof can rebind the public coordinator to an exact disposable DB, but the
lifecycle factory still compares the path against its production canonical constant.
That prevents the authorized disposable proof from exercising production semantics.

Simply passing a raw path is unsafe. It would allow arbitrary callers to weaken the
authoritative corpus restriction.

### 5.2 New immutable contract

Introduce one immutable contract in a shared operator module, for example:

`src/printer_v1/operator_cli/operational_database_target_binding.py`

Recommended shape:

```python
@dataclass(frozen=True)
class OperationalDatabaseTargetBinding:
    binding_version: str
    target_kind: str
    resolved_db_path: str
    authorized_pre_mutation_sha256: str
    migration_count: int
    migration_head: str
    db_target_identity: str
    authorization_id: str
    authorization_marker_sha256: str
    application_marker_sha256: str
    execution_id: str
    campaign_id: str
    campaign_run_id: str
    cycle_id: str
    configuration_id: str
```

Allowed `target_kind` values:

- `PRODUCTION_AUTHORITATIVE`
- `AUTHORIZED_DISPOSABLE_OPERATIONAL_PROOF`

No third value is allowed.

### 5.3 Binding authority

Only the public operational coordinator may construct the binding, after:

- activation preflight passes;
- the one-shot authorization package is validated where applicable;
- the exact DB path and pre-mutation SHA-256 are known;
- migration ledger count/head are validated;
- campaign, run, cycle, configuration, and execution IDs exist;
- authorization and application markers are available.

The binding is passed unchanged:

```text
public coordinator
-> authoritative operational owner
-> origin/lifecycle driver
-> run_one_command_15m_factory
```

No downstream layer may replace or partially rebuild it.

### 5.4 Production validation

For `PRODUCTION_AUTHORITATIVE`, the lifecycle factory must prove:

- actual resolved DB path equals binding path;
- binding path equals the canonical production DB;
- binding IDs equal lifecycle ownership context;
- binding DB target identity equals the durable campaign target identity;
- binding authorization marker matches the durable campaign configuration;
- migration ledger count/head remain canonical;
- no disposable-proof marker is present.

Failure returns a categorical DB-binding preflight reason before factory mutation.

### 5.5 Disposable operational-proof validation

For `AUTHORIZED_DISPOSABLE_OPERATIONAL_PROOF`, the lifecycle factory must prove:

- actual resolved DB path equals binding path;
- binding path is not the canonical production DB;
- the exact one-shot authorization names that same path and baseline SHA-256;
- authorization marker and application marker hashes match;
- authorization ID and execution ID match the current invocation;
- campaign/run/cycle/configuration IDs match the lifecycle ownership context;
- the durable campaign configuration stores the same baseline DB target identity;
- migration count/head are canonical;
- the invocation is single-use and has no retry/restart/resume/successor permission.

The lifecycle runs with production behavior:

- `proof_mode=False`;
- `operational_persistent_mode=True`.

The disposable classification comes from the validated binding, not from relaxing
operational mode.

### 5.6 Pre-mutation SHA rule

The authorized SHA-256 describes the exact database before campaign-owned mutation.

After campaign identity, discovery, reserve, and handoff rows are written, the current
file SHA will legitimately differ.

Therefore the lifecycle factory must not require the current mutable file hash to equal
the original authorization hash.

It must instead prove:

- the binding baseline SHA equals the authorization document;
- the same baseline identity is durably bound to the campaign configuration;
- current path and campaign ownership are exact;
- migration head remains valid;
- all action-local mutations are attributable to this invocation.

This preserves authorization without making legitimate owned writes impossible.

### 5.7 Fail-closed behavior

The factory returns distinct categorical reasons:

- `OPERATIONAL_DB_BINDING_MISSING`
- `OPERATIONAL_DB_BINDING_KIND_INVALID`
- `OPERATIONAL_DB_BINDING_PATH_MISMATCH`
- `OPERATIONAL_DB_BINDING_PRODUCTION_PATH_MISMATCH`
- `OPERATIONAL_DB_BINDING_AUTHORIZATION_MISMATCH`
- `OPERATIONAL_DB_BINDING_APPLICATION_MARKER_MISMATCH`
- `OPERATIONAL_DB_BINDING_BASELINE_SHA_MISMATCH`
- `OPERATIONAL_DB_BINDING_MIGRATION_MISMATCH`
- `OPERATIONAL_DB_BINDING_OWNERSHIP_MISMATCH`
- `OPERATIONAL_DB_BINDING_REUSE_OR_HISTORY_MISMATCH`

The public terminal envelope must preserve the exact reason.

### 5.8 Direct callers

Any operational-persistent direct caller without a valid binding must safe-stop.

Tests may construct fixture bindings only through a dedicated test helper that still
passes the same validator. Production code must not expose a permissive path-only
constructor.

## 6. Repair Unit B — Exact holder-stage six-unit integration

### 6.1 Problem

Holder collection currently proves durable request IDs and numeric transport counts,
but campaign six-unit accounting requires exact identity records.

Counts must not be converted into identities after the fact.

### 6.2 Existing identity authority

Reuse:

`printer_v1.sources.measured_transport.TransportOperationIdentity`

Do not create a competing holder-specific identity class.

Every actual outbound holder operation must have one identity created at the transport
boundary.

### 6.3 Exact holder transport identities

#### GoPlus

One attempted HTTP request emits one identity:

- stage: `HOLDER_SAFETY`
- source name: `goplus`
- endpoint owner: existing GoPlus transport owner
- governed request kind: `safety_reference`
- method/endpoint: exact approved HTTP endpoint category
- ordinal: `1`
- target category: `TOKEN_MINT`
- target identity: exact mint
- measured response bytes
- normalized holder row count
- terminal result

#### Solana RPC primary or backup

Each JSON-RPC call emits one identity.

A successful normal holder request emits:

1. `getTokenLargestAccounts`
2. `getTokenSupply`

A failure after the first RPC emits only the first identity.

A failure on the second RPC emits both attempted identities.

Primary and backup endpoint owners remain distinct. No provider rotation or additional
backup is introduced.

### 6.4 Measurement-time fan-out

Create one holder-stage `MeasuredTransportLedger` with:

`on_transport_recorded = public action-local transport observer`

Data flow:

```text
real holder HTTP/RPC transport
-> build exact TransportOperationIdentity
-> holder MeasuredTransportLedger.record_transport()
   -> action-local observer receives the identity
-> normalized payload retains the identical serialized identity
-> holder persistence validates request/identity correspondence
```

The action-local observer remains verification-only.

### 6.5 Holder persistence contract

Extend `HolderBundlePersistResult` and `HolderContextResult` with:

```text
transport_identities
holder_stage_id
holder_stage_terminal_status
holder_stage_first_terminal_cause
```

For the permanent operational path:

- `transport_identity_count` must equal the number of exact identities;
- payload count and identities must agree;
- request kind/source/target must agree;
- identity ordinals must be unique;
- response-byte and normalized-row values must be non-negative;
- duplicate identity keys block;
- numeric `underlying_operation_count` without exact identities blocks campaign
  acceptance.

Legacy paths may retain numeric compatibility only where they do not claim campaign
six-unit acceptance. The active V2-9.8B path requires exact identities.

### 6.6 Holder stage ownership

Seal exactly one campaign stage after holder evaluation:

- stage kind: `HOLDER_SAFETY`;
- stage identity: built by existing `build_campaign_stage_id`;
- stage sequence: assigned by the public campaign accounting owner as the next
  available sequence after currently ingested pre-lifecycle stages;
- campaign/run/cycle identities: exact current ownership context.

The holder code must not invent its own campaign owner or sequence authority.

### 6.7 Holder stage terminal semantics

| Condition | Stage result |
|---|---|
| One or more attempted requests, exact accounting complete | `COMPLETED` |
| Source failure/rate limit with exact attempted identities | `COMPLETED` source outcome; holder context may be unknown/failed |
| Attempted request with missing/duplicate/contradictory identity | `BLOCKED` |
| Persistence fault after real attempt, partial exact identities retained | `BLOCKED`, preserving real identities |
| No request can start because of clean budget exhaustion | `COMPLETED` with evidence phase `PRE_OPERATION_NO_WORK` |
| No request can start because deadline expired | `COMPLETED` with evidence phase `PRE_OPERATION_NO_WORK` and deadline reason |

`PRE_OPERATION_NO_WORK` must use the existing all-zero sealed-stage contract and create
no source row or fake transport.

### 6.8 Existing campaign sink

Reuse the current accounting stage evidence sink.

The holder stage is sealed once and ingested once into the same
`CampaignSixUnitOwner`.

Do not directly increment campaign transport counters.

### 6.9 Conditional acceptance rule

Full-run acceptance must require:

- when holder durable request IDs exist: exactly one sealed `HOLDER_SAFETY` stage and
  exact request/identity reconciliation;
- when no holder request exists: exact `PRE_OPERATION_NO_WORK` evidence or an explicit
  approved omitted-stage state;
- campaign owner and action-local transport identity sets are equal and non-vacuous
  after holder work;
- no holder request is represented only by a count.

`HOLDER_SAFETY` is conditionally mandatory. It does not become a source-availability
gate for memory observation.

### 6.10 Holder context law remains unchanged

- holder pass is not required for `MEMORY_OBSERVATION_ELIGIBLE`;
- source unavailable, concentrated, or budget-unattempted remains truthful context;
- only a real holder pass creates `FULLY_ELIGIBLE`;
- future action remains `BLOCKED_OR_UNKNOWN`;
- missing accounting blocks handoff;
- clean source failure with exact accounting does not erase an otherwise valid market
  observation.

## 7. Repair Unit C — Continuous-proof terminal evidence retention

### 7.1 Problem

The current custom child launcher overwrites stdout with only the integer return code.
The proof summary omits the detailed public terminal result.

A one-shot proof must retain enough evidence to explain a blocker without another run.

### 7.2 Required raw artifacts

Retain before disposable teardown:

- `child-stdout.txt`
- `child-stderr.txt`
- `child-terminal.json`
- `wrapper-terminal.json`
- `campaign-terminal-report.json`
- `proof-summary.json`
- `holder-context.json`
- `pre-holder-budget-snapshot.json`
- `campaign-source-request-reconciliation.json`
- `campaign-six-unit-evidence.json`
- `action-local-six-unit-evidence.json`
- `selected-and-alternate-identities.json`
- `artifact-hashes.json`

Where a source artifact does not exist, record a categorical absence in the proof
summary. Do not invent an empty success object.

### 7.3 Child output capture

The in-process proof launcher must capture the real output of
`public_command.main()` using isolated stdout/stderr capture.

It must not replace the captured output.

It may write a separate launcher metadata file containing:

- return code;
- PID;
- invocation arguments;
- start/end timestamps.

### 7.4 Terminal parsing

Parse the final JSON terminal envelope from child stdout.

Retain at minimum:

- status;
- execution ID;
- campaign ID;
- run status;
- first terminal cause;
- `blocked_reasons`;
- `orchestration_error`;
- fault details;
- campaign acceptance verdict;
- operational lifecycle pass;
- clean-memory outcome pass;
- report path/identity.

If parsing fails:

- retain raw stdout/stderr;
- record `CHILD_TERMINAL_JSON_UNPARSEABLE`;
- fail the proof.

### 7.5 Holder diagnostics

The terminal/campaign report must retain:

- pre-holder exact request IDs;
- pre-holder exact transport identity keys;
- holder evaluated mints;
- holder unattempted mints;
- holder attempt budget trace;
- exact holder request IDs;
- exact holder transport identities;
- holder stage status;
- holder source outcomes;
- before/after operation ledgers;
- budget exhaustion state and reason.

### 7.6 Freeze and handoff diagnostics

Retain the exact ordered:

- four-candidate observation universe;
- two selected identities;
- two alternate identities;
- selection seed;
- freeze authority;
- handoff slots;
- lifecycle factory target IDs.

### 7.7 Copy and hash order

Before temporary directory cleanup:

1. flush and close database/report handles;
2. copy every required artifact into the retained directory;
3. hash every retained file;
4. write `artifact-hashes.json`;
5. re-read and verify copied bytes;
6. only then allow temporary cleanup.

A missing required artifact makes the proof BLOCKED.

## 8. Data flow after repair

```text
validated wrapper package
-> validated public DB target
-> immutable DB binding
-> campaign configuration stores baseline DB target identity
-> governed discovery stages seal exact evidence
-> pre-holder snapshot reconciles request and identity sets
-> holder transport creates exact identity at each outbound call
-> holder stage ledger records identity
-> action-local observer receives identity immediately
-> holder persistence binds identity to real Source Governor request
-> HOLDER_SAFETY stage seals once into campaign owner
-> campaign request manifest and six-unit evidence reconcile
-> freeze and handoff
-> lifecycle factory validates immutable DB binding
-> WINDOW_15M Scheduler work
-> terminal acceptance
-> complete retained proof package
```

## 9. Likely implementation files

Expected narrow source scope:

- `src/printer_v1/operator_cli/operational_database_target_binding.py` — new
- `src/printer_v1/operator_cli/operational_memory_factory_command.py`
- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
- `src/printer_v1/operator_cli/origin_lifecycle_campaign.py`
- `src/printer_v1/operator_cli/one_command_15m_factory.py`
- `src/printer_v1/operator_cli/holder_reliability_budget_control.py`
- `src/printer_v1/sources/solana_rpc_holder.py`
- existing GoPlus transport module
- `src/printer_v1/sources/campaign_six_unit_accounting.py` only if a minimal
  conditional-stage helper is required
- focused tests
- continuous proof harness
- implementation closeout doc

No migration is expected.

A schema change is not authorized by this design. If implementation proves an exact
required durable fact cannot be represented in existing campaign configuration,
report JSON, holder attempt, source request, or six-unit evidence surfaces, stop
BLOCKED for separate schema design.

## 10. Focused verification design

### 10.1 Operational DB binding tests

1. Exact production binding accepts canonical production target.
2. Production binding rejects a non-canonical path.
3. Exact authorized disposable binding accepts the approved disposable path.
4. Arbitrary disposable path is rejected.
5. Missing binding is rejected.
6. Binding path drift is rejected.
7. Baseline SHA/authorization mismatch is rejected.
8. Application marker mismatch is rejected.
9. Migration count/head drift is rejected.
10. Campaign/run/cycle/configuration drift is rejected.
11. Reused authorization/history is rejected.
12. Legitimate campaign-owned writes after baseline authorization do not require the
    current file SHA to equal the baseline SHA.
13. The exact categorical reason survives into the public terminal envelope.

### 10.2 Holder identity tests

14. GoPlus success emits exactly one identity.
15. GoPlus failure emits exactly one attempted identity.
16. Solana RPC success emits two ordered identities.
17. Solana RPC first-call failure emits one identity.
18. Solana RPC second-call failure emits two identities.
19. Backup RPC identities use the backup endpoint owner and do not duplicate primary.
20. Identity count and numeric count mismatch blocks.
21. Missing identities with positive count blocks.
22. Duplicate identity keys block.
23. Target mint mismatch blocks.
24. Exact holder identities reach the action-local observer once each.
25. One `HOLDER_SAFETY` stage seals the same identity set into the campaign owner.
26. Campaign and action-local identity sets reconcile exactly after holder work.
27. Durable holder request IDs reconcile to exact stage identities.
28. Clean budget exhaustion creates zero requests and valid no-work evidence.
29. Complete source failure remains holder context rather than fake accounting failure.
30. Only real holder pass creates `FULLY_ELIGIBLE`.
31. Four observation rows still freeze to two selected plus two alternates.

### 10.3 Proof retention tests

32. Child raw stdout and stderr are preserved.
33. Static `blocked_reasons` are retained.
34. `orchestration_error` is retained.
35. Parsed child terminal JSON is retained.
36. Campaign report is copied before teardown.
37. Holder context and attempt trace are retained.
38. Exact ordered selected and alternate identities are retained.
39. Campaign/action-local exact identity arrays are retained.
40. Every retained file is hashed and byte-verified.
41. Missing required artifact makes proof BLOCKED.
42. Authorization remains single-use with zero retry/restart/resume/successor.

## 11. Verification order for the future implementation lane

Use risk-based minimum sufficient verification:

1. changed focused tests;
2. nearest DB-binding, holder accounting, campaign six-unit, wrapper, and terminal
   contract tests;
3. Python compilation for changed modules;
4. `git diff --check`;
5. static no-unlock/no-bypass review;
6. directly affected regression set;
7. broad suite only at pre-proof validation because this is a cross-cutting
   DB-isolation/accounting/proof-boundary repair;
8. one separately authorized continuous disposable proof.

Do not run the continuous proof before the broad pre-proof gate passes.

## 12. Continuous proof acceptance

The later proof must show:

- one authorization;
- one child invocation;
- zero retry/resume/restart/successor;
- zero network escapes beyond frozen approved transports;
- exact authorized disposable DB binding;
- authoritative production DB byte-identical before/after;
- four observation candidates;
- two selected plus two ordered alternates;
- exactly two token slots;
- exact holder stage request/transport reconciliation;
- campaign and action-local six-unit equality including holder identities;
- two logical `WINDOW_15M` lifecycles;
- at least `900` seconds per window;
- two current-run terminal windows;
- two clean episodes;
- two canonical fingerprints;
- zero active/orphan work;
- released lease;
- zero forbidden capability deltas;
- report-only replay equivalence;
- complete retained artifacts and hash manifest.

Any safe stop remains a valid honest result, but it is not a PASS.

## 13. Error and stop semantics

The first terminal cause must never be overwritten.

Secondary cleanup, reporting, or evidence-retention faults are appended separately.

Stop before handoff when:

- holder request identity evidence is missing or contradictory;
- campaign and action-local holder identities disagree;
- DB binding is missing or mismatched;
- authorization/marker/migration/ownership binding disagrees.

Continue memory observation with truthful holder context when:

- holder source returns a complete failure/rate-limit result with exact accounting;
- holder evidence is concentrated;
- budget is exhausted before another request starts;
- a candidate remains unattempted because of clean bounded exhaustion.

## 14. Rollback boundary

The implementation must remain one narrow branch.

If a focused test shows the required binding cannot be represented without weakening
production DB strictness, stop BLOCKED.

If exact holder identities cannot be produced at the real transport boundary without
inventing fields, stop BLOCKED.

If a schema migration appears necessary, stop BLOCKED.

If the repair changes selection, freeze depth, source ceilings, provider order,
Scheduler ownership, memory quality, retrieval, decisions, or financial capability,
stop BLOCKED.

## 15. Money-usefulness contribution

This repair makes memory growth trustworthy rather than merely runnable.

- Exact DB authorization prevents learning into the wrong corpus.
- Exact holder transport identities prevent hidden source work and false accounting
  equality.
- Complete proof retention prevents repeated expensive runs and makes blockers
  auditable.
- Holder context remains separate from memory observation, preserving useful losing,
  risky, concentrated, and unavailable-source trajectories for later clean learning.

## 16. What this lane improves

- Enables a lawful disposable proof of production operational semantics.
- Preserves strict production DB targeting.
- Completes holder request-to-transport-to-campaign accounting.
- Preserves independent action-local verification.
- Makes the next one-shot proof self-diagnosing.
- Protects the four-candidate observation universe and two-plus-two freeze.

## 17. What this lane still does not unlock

- no implementation by this design itself;
- no proof rerun;
- no real authorization;
- no provider contact;
- no authoritative DB mutation;
- no production memory-growth campaign;
- no 1h/4h/12h/24h activation;
- no retrieval;
- no decisions;
- no BUY/SELL/HOLD;
- no positions, trade events, audits, or PnL;
- no wallet, keys, signing, funds, or live execution.

## 18. Functionality Risks / Setbacks / Efficiency Blockers

### Functionality risks

- A loose DB-binding constructor could become an arbitrary path bypass.
- Comparing a post-mutation DB hash to the baseline authorization hash could make every
  lawful run fail.
- Building identities after the transport returns could create self-reported or
  fabricated evidence.
- Recording the same holder identity through both payload parsing and observer callback
  could double-count.
- A mandatory holder stage without no-work semantics could block lawful budget
  exhaustion.
- Treating holder failure as memory ineligibility would regress the adopted
  holder-context separation.

### Setbacks

- The prior proof authorization is already consumed.
- The historical exact preflight subreason cannot be recovered from existing retained
  summary evidence.
- The next proof must validate three repaired boundaries together.
- Full-run accounting tests will need new exact identity fixtures rather than numeric
  holder counts.

### Efficiency blockers

- Cross-cutting DB binding and accounting changes require a broad pre-proof suite.
- The proof remains one-shot and comparatively expensive.
- Exact response-byte and normalized-row measurement must come from transport owners,
  not a cheap reconstructed count.
- Artifact retention must complete before temporary cleanup, increasing proof package
  size but reducing rerun risk.

## 19. Implementation authorization boundary

This design PASS authorizes only preparation of a separate implementation prompt or
operator-approved implementation lane.

It does not authorize code changes, tests, a proof, an authorization package, source
contact, Scheduler runtime, or database mutation.
