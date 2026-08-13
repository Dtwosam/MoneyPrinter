# Printer V1 V2-9.8B Source-Free Discovery Capacity Authority Design

## Verdict

`V2_9_8B_SOURCE_FREE_DISCOVERY_CAPACITY_AUTHORITY_DESIGN_PASS_READY_FOR_TDD_IMPLEMENTATION`

This design is the minimum prerequisite repair required before the authoritative `MultiCycleAdmissionHealth` projection can resume.

The preceding audit proved that ten of the twelve health fields have existing owner-backed authority or a narrow read-only adapter path, but `provider_budgets_available` and `discovery_capacity_available` cannot currently be populated without inventing state. The missing piece is not a new provider policy. The operational path already owns machine-readable request ceilings and request-kind identities, but those facts are scattered across the real execution owners and are not exposed as one source-free capacity contract.

This lane therefore defines one shared, read-only discovery-attempt manifest plus one read-only provider-capacity projection. It does not implement or invoke later-cycle discovery.

## Authority and baseline

Use the active Printer V1 source stack together:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-python-builder-guide.md`
- `docs/printer-v1-v2-9-8b-four-token-bounded-capacity-proof-integration-design.md`
- `docs/printer-v1-v2-9-8b-admission-health-and-wake-disposition-design.md`

Immediate baseline:

- branch: `agent/v2-9-8b-four-token-bounded-capacity-proof-integration-implementation`
- starting HEAD: `11303a048fd2d1554630c7f1d65016fac6206063`
- controller readiness: PASS
- admission-health/wake design: PASS
- authoritative admission-health projection: STOPPED before RED because provider/discovery capacity authority was incomplete

The four-token proof shape remains exactly `4 / 2 / total cycles 2`, with public `TOKEN_CAPACITY == 2`.

## Audit conclusion

The blocker is real, but it is narrower than creating a new provider-budget model.

Existing machine-readable authority already includes:

- `pumpfun_origin.REQUEST_CEILINGS`, including bounded signature-page and transaction-decode requests;
- `secondary_discovery.REQUEST_CEILINGS`, provider/request-kind mappings, and provider cycle ceilings;
- the live operational composition in `authoritative_live_operational_campaign.py`, which determines which optional secondary branches are actually enabled;
- holder-stage aggregate authority in `holder_reliability_budget_control.py`, including `HOLDER_WORST_CASE_GOVERNED_REQUESTS`, `HOLDER_WORST_CASE_TRANSPORT_OPERATIONS`, and the permanent holder-stage ceiling;
- provider rate ceilings in `SOURCE_REGISTRY`;
- the canonical 60-second read-only consumed-attempt window in `sources/budget_accounting.py`;
- exact provider-reaching attempt classification in `count_recent_source_requests(...)`;
- Source Governor request-kind validation;
- Central Scheduler ownership as a separate admission gate.

What is missing is a shared source-free projection of the exact attempt shape and the exact remaining provider capacity for that shape.

`OperationalSourceContract.operation_budget` remains descriptive documentation only. It must not become numeric authority and must not be parsed.

## Design decision 1 - compose the manifest from execution owners, not prose

Add one immutable source-free attempt manifest for exactly one later-cycle two-token discovery/selection action.

The manifest is a projection of the plan already owned by the operational path. It is not a second execution plan and does not execute anything.

Conceptual immutable records:

```text
DiscoveryAttemptRequirement
  stage
  source_name
  request_kind
  governed_request_ceiling
  underlying_transport_ceiling
  condition
  condition_evidence
  rate_limit_owner
  execution_owner

LaterCycleDiscoveryAttemptManifest
  contract_version
  target_count = 2
  candidate_evaluation_ceiling
  requirements
  provider_governed_request_totals
  provider_transport_operation_totals
  optional_paths
  source_free = true
```

Names may change during TDD, but the semantics may not.

Every numeric ceiling in the manifest must be imported or derived from an existing machine-readable owner. No value may be copied from documentation prose.

## Design decision 2 - exact stage authority

### Pump origin acquisition

Authority:

- `src/printer_v1/sources/pumpfun_origin.py`
- `REQUEST_CEILINGS`
- `SIGNATURE_PAGE_REQUEST`
- `TRANSACTION_REQUEST`
- `_OPERATION_CEILINGS`
- the existing acquisition kernel

The current machine-readable maximum is the existing bounded request plan, not `operation_budget` text.

The manifest must derive Pump request ceilings directly from `REQUEST_CEILINGS` and require the same Solana RPC source identity and request kinds used by the acquisition kernel.

No new Pump polling, page size, decode ceiling, or RPC allowance may be defined in this lane.

### Secondary discovery/enrichment

Authority:

- `src/printer_v1/sources/secondary_discovery.py`
- `REQUEST_CEILINGS`
- `REQUEST_TO_SOURCE`
- `REQUEST_TO_WORK_TYPE`
- Gecko/Tracker source identities and rate ceilings
- the actual live composition in `AuthoritativeLiveOperationalCampaignOwner._build_fixtures(...)` and `LiveSecondaryDiscoveryAdapter.enrich(...)`

The manifest must describe only request branches the live operational owner can actually execute.

Current conditionality must remain explicit:

- Gecko trending: enabled when the secondary path is enabled;
- Gecko active-pool enrichment: conditional on an acquired active pool, but its maximum lawful branch must be reserved when that branch can occur;
- DexScreener fresh-profile request: governed exactly as executed by the live adapter;
- Solana Tracker: included only when the existing free-key/configuration path proves it is enabled;
- no paid fallback may appear.

Unused or historical constants must not silently increase the manifest. Tests must compare the manifest against current executable call sites/owner constants rather than assuming every old ceiling is active.

### Holder eligibility

Authority:

- `holder_reliability_budget_control.py`
- `HOLDER_WORST_CASE_GOVERNED_REQUESTS`
- `HOLDER_WORST_CASE_TRANSPORT_OPERATIONS`
- `PERMANENT_HOLDER_STAGE_TRANSPORT_CEILING`
- the existing safety-context collection and holder source-redundancy owners

Current gap:

The holder budget owner exposes exact aggregate worst-case counts but does not export the provider/request-kind split as a pure plan.

Minimum prerequisite helper:

Expose a pure, source-free holder safety request plan from the same safety-context owner used by `_collect_preclose_context(... include={"safety"})`.

That plan must identify the current governed request families and fallback conditions without performing any request. At minimum it must distinguish:

- GoPlus safety evidence;
- primary Solana RPC holder-concentration evidence;
- the one conditional Helius Free holder backup after only an eligible transient primary failure.

The provider/request-kind split must reconcile exactly to the existing aggregate holder budget constants. If it does not, fail closed and stop the implementation lane.

Do not infer the split from prose comments.

## Design decision 3 - manifest conditionality is conservative and configuration-bound

The capacity check happens before source execution, so some branches are not yet factually known.

Rules:

- a branch that can lawfully occur under the current configuration contributes its worst-case requirement;
- a branch may be omitted only when existing configuration proves it cannot execute;
- a conditional fallback that may be required after an eligible failure remains reserved;
- optional paid or prohibited providers remain excluded;
- dynamic candidate success must never be assumed to reduce required capacity before the attempt starts.

This is deliberately conservative. It may defer cycle 2 when an optimistic runtime path could have fit, but it must never admit a cycle whose bounded source package cannot be proven safe.

## Design decision 4 - provider capacity comes from persisted provider-reaching attempts

Provider admission capacity is derived from the existing Source Governor accounting model, not from `retry_after_seconds` and not from documentation prose.

Canonical read-only owner:

`src/printer_v1/sources/budget_accounting.py`

It already defines:

- `DEFAULT_WINDOW_SECONDS = 60`;
- provider-reaching attempts as requests with a response or attributable adapter/network failure;
- exclusion of pure governor rejections;
- read-only counting through `count_recent_source_requests(...)`.

Add the minimum read-only detail projection needed to expose the timestamps/identities of the same counted attempts. The new helper must use the same inclusion/exclusion law as `count_recent_source_requests(...)`; it must not create a second definition of a consumed provider attempt.

Conceptual provider snapshot:

```text
ProviderCapacitySnapshot
  source_name
  window_seconds
  rate_ceiling
  consumed_attempt_times
  consumed_attempt_count
  package_required_attempts
  package_fits_now
  package_ready_at
  evidence_complete
  reason
```

`rate_ceiling` comes from `SOURCE_REGISTRY[source_name].default_rate_limit_per_minute`.

## Design decision 5 - exact package-ready boundary

The read-only provider projection answers whether the entire manifest requirement for that provider can be reserved under the current 60-second rate window.

For a provider with:

```text
limit = L
current provider-reaching attempts in the canonical window = C
required attempts from the manifest = R
```

current capacity is sufficient only when:

```text
C + R <= L
```

If not, the provider's exact next meaningful capacity boundary is derived from the persisted timestamps of the counted attempts and the canonical 60-second window.

The implementation must calculate the earliest timestamp at which enough of the currently counted attempts have aged out for `C + R <= L`, assuming no new consumption.

That timestamp is a **reevaluation boundary**, not a promise that capacity will still be available then. Any intervening lifecycle/source consumption requires a fresh projection.

For multiple blocked providers, the composed discovery-capacity recheck boundary is the latest of the provider package-ready boundaries required for the whole currently known package. Earlier lifecycle/supervision events may still trigger reevaluation under the already-approved wake design.

If timestamp attribution is missing or ambiguous, there is no synthetic boundary: fail closed with `recheck_at = None`.

## Design decision 6 - `retry_after_seconds` is not admission authority

`SourceRequestDecision.retry_after_seconds` remains a generic Source Governor failure hint.

It must not be converted into cycle-2 `recheck_at` because it does not prove when the complete multi-provider two-token package becomes lawful.

The discovery-capacity lane must never use:

- `definition.retry_after_seconds`;
- generic exponential/backoff timing;
- arbitrary sleeps;
- a periodic poll interval

as admission-health authority.

## Design decision 7 - the mutable pacer is not global provider authority

`SequentialRequestPacer` remains an execution-time sequential spacing helper.

Its private `_last_started` state is currently local/mutable and is not durable campaign-wide provider accounting. Therefore it must not become the primary admission-health authority.

If a later callback implementation reuses one pacer instance and needs a pure intra-attempt next-start query, it may add a non-mutating inspection method backed by the existing `next_paced_time(...)` calculation. That is an execution convenience only.

Cross-cycle `provider_budgets_available` must remain based on the durable consumed-attempt accounting described above.

## Design decision 8 - discovery capacity and provider capacity stay separate

The prerequisite produces two distinct truths for the later `MultiCycleAdmissionHealth` projection.

### `provider_budgets_available`

True only when every provider required by the current source-free manifest has sufficient package capacity under its existing rate window.

False when any required provider lacks capacity or when consumed-attempt evidence is ambiguous.

### `discovery_capacity_available`

True only when:

- the source-free manifest is complete and internally consistent;
- it resolves to exactly one bounded two-token discovery action;
- all required request kinds remain valid under the existing Source Governor contracts;
- required source-owner configuration is available;
- the authoritative operational owner can represent this attempt shape without invoking the callback;
- no prohibited/paid source path is required.

It does not duplicate:

- provider rate capacity (`provider_budgets_available`);
- total source-budget envelope (`source_budget_available`);
- Scheduler row capacity (`scheduler_budget_available`);
- lifecycle close/protected reserve.

Those remain separate health fields.

The later callback may still remain unwired while this field is implemented. `discovery_capacity_available` proves the bounded action shape is representable and capacity-checkable; it does not itself execute discovery.

## Design decision 9 - Source Governor remains authoritative at execution time

Passing the read-only capacity projection never pre-approves a future source call.

Every actual request in the later callback must still pass through the existing Source Governor immediately before execution using fresh current accounting.

The manifest is a capacity/readiness contract only. It cannot bypass a later Source Governor denial.

Likewise, Central Scheduler ownership remains mandatory when the callback is later implemented.

## Design decision 10 - no DB or schema mutation is required

This prerequisite is read-side only.

The current source request/response/failure history already carries the provider-attempt evidence required for the 60-second projection.

Do not add a migration merely to cache the manifest or provider-capacity result.

Do not persist a speculative cycle-2 discovery row in this lane.

If TDD proves the current schema cannot unambiguously recover the timestamps of provider-reaching attempts under the existing accounting definition, stop and document the exact schema blocker before proposing a migration.

## Source-free projection result

The implementation may use different class names, but the composed result must carry equivalent evidence:

```text
LaterCycleDiscoveryCapacity
  manifest
  manifest_valid
  provider_snapshots
  provider_budgets_available
  discovery_capacity_available
  recheck_at
  reasons
```

Requirements:

- immutable/read-only output;
- exact reason codes for every false result;
- no healthy default;
- `recheck_at` only from persisted provider-window evidence;
- no source call;
- no Scheduler operation;
- no DB write;
- no callback invocation.

## TDD implementation sequence

### Step A - RED: manifest authority

Add focused tests proving there is no current source-free exact two-token attempt manifest and specifying:

- exact Pump request-kind ceilings from `pumpfun_origin.REQUEST_CEILINGS`;
- exact active secondary request branches from existing owner constants/call sites;
- holder provider/request-kind plan reconciling to the existing `3 governed / 5 transport` worst-case contract;
- optional Tracker exclusion only when configuration proves it disabled;
- conditional holder backup reservation;
- zero transport/source/Scheduler/DB activity.

Commit the valid RED separately.

### Step B - GREEN: source-free manifest only

Implement the minimum pure helpers necessary to compose the manifest from existing owners.

Do not implement provider availability yet if the RED can be closed cleanly without it.

Verify focused parity tests and stop if any request ceiling requires a new invented constant.

### Step C - RED/GREEN: provider capacity detail

Extend `budget_accounting.py` with the minimum read-only attempt-detail projection that shares the exact counted-attempt law with `count_recent_source_requests(...)`.

Prove:

- response-backed attempts count;
- attributable provider/network failures count;
- pure Governor rejections do not count;
- timestamps are exact and deterministic;
- ambiguous schema/evidence fails closed rather than returning zero.

### Step D - RED/GREEN: package capacity and recheck boundary

Compose manifest requirements with provider snapshots.

Prove:

- current package-fit calculation;
- exact package-ready boundary from aged-out consumed attempts;
- multiple blocked providers use the whole-package boundary;
- new intervening consumption changes the next projection;
- no `retry_after_seconds` dependency;
- no pacer mutation;
- no polling/backoff.

### Step E - closeout

Focused closeout only. Do not resume later-cycle discovery.

Closeout verdict must explicitly state whether the prerequisite now provides authoritative inputs for both:

- `provider_budgets_available`;
- `discovery_capacity_available`.

Only after PASS may the project resume Step 1 of `docs/printer-v1-v2-9-8b-admission-health-and-wake-disposition-design.md` and populate all twelve health fields.

## Minimum sufficient verification

Use risk-based verification.

Required focused proof:

1. manifest is source-free and deterministic;
2. manifest imports/derives every numeric ceiling from existing machine-readable owners;
3. Pump parity with `pumpfun_origin.REQUEST_CEILINGS`;
4. secondary parity with active live composition and `secondary_discovery` request contracts;
5. holder request-plan totals reconcile exactly to existing aggregate governed/transport ceilings;
6. no paid/prohibited provider appears;
7. disabled optional providers are omitted only from existing configuration evidence;
8. conditional fallbacks are conservatively reserved;
9. provider snapshot uses the same provider-reaching-attempt definition as `count_recent_source_requests(...)`;
10. pure Governor rejections do not consume provider capacity;
11. package-fit calculation is deterministic;
12. package-ready boundary comes only from persisted timestamps plus the canonical 60-second window;
13. missing/ambiguous timestamp attribution fails closed;
14. `retry_after_seconds` is never used as package rearm authority;
15. `SequentialRequestPacer` is not mutated by read-side projection;
16. zero source requests;
17. zero Scheduler enqueue/claim/cancel;
18. zero DB mutation;
19. zero later-cycle callback invocation;
20. public two-token/runtime behavior is unchanged because the new authority is not wired into runtime in this prerequisite lane.

No broad regression suite is required until the later admission-health implementation closeout or another major integration checkpoint.

## Money-usefulness contribution

This prerequisite does not create a paper decision or simulated PnL. Its contribution is preventing Printer from starting a second discovery package when provider capacity cannot actually support it. That protects already-admitted lifecycle observations and makes future four-token memory growth more trustworthy instead of increasing token count by silently overloading source providers.

## What this improves

- turns scattered runtime request ceilings into one inspectable exact two-token attempt shape;
- gives provider capacity a durable, source-free evidence basis;
- produces lawful provider recheck boundaries without hidden retry policy;
- preserves Source Governor and Central Scheduler authority;
- makes `provider_budgets_available` and `discovery_capacity_available` implementable without healthy defaults;
- avoids parsing prose source contracts or copying provider ceilings.

## What this still does not unlock

This lane does not unlock:

- later-cycle discovery callback execution;
- source fetching;
- Scheduler runtime work;
- cycle-2 admission or persistence;
- Memory Factory wake integration;
- four-token proof authorization or proof execution;
- six-token execution;
- 12h/24h activation;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions;
- trade events/audits;
- PnL.

## Functionality Risks / Setbacks / Efficiency Blockers

### Risk - manifest drifts from execution

Mitigation: every ceiling comes from the same machine-readable constants/helpers used by the real path, with focused parity tests. No prose parsing and no copied numbers.

### Risk - conservative reservation blocks usable capacity

The manifest reserves branches that can lawfully occur even if a particular runtime attempt might not need them.

Mitigation: accept conservative false negatives for the first four-token proof. Do not weaken safety by predicting favorable source outcomes.

### Risk - holder aggregate and provider split disagree

Mitigation: provider/request-kind helper must reconcile to the existing aggregate holder budget contract. Any mismatch blocks implementation rather than changing the aggregate ceiling in this lane.

### Risk - sliding-window timestamp ambiguity

Mitigation: the provider detail helper must share the exact response/failure attribution law of `count_recent_source_requests(...)`. Missing evidence fails closed; it must not be treated as zero usage.

### Risk - Source Governor decision changes after readiness

Mitigation: readiness is never execution authority. Actual requests must still be freshly governed when the callback is later implemented.

### Efficiency blocker - one holder request-plan helper is not currently exported

This is the only expected new owner-local declarative helper beyond provider-attempt detail. Keep it pure and narrow. Do not refactor the whole safety-context subsystem.

## Closeout

Design status:

`V2_9_8B_SOURCE_FREE_DISCOVERY_CAPACITY_AUTHORITY_DESIGN_PASS_READY_FOR_TDD_IMPLEMENTATION`

Correct next lane:

`TDD source-free discovery attempt manifest and provider-capacity authority`

After that prerequisite closes PASS, return to:

`TDD authoritative MultiCycleAdmissionHealth projection`

Do not implement or invoke cycle-2 discovery before both prerequisites pass focused proof.
