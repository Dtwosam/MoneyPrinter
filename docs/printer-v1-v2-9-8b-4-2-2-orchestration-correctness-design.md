# Printer V1 V2-9.8B 4/2/2 Orchestration Correctness Design

Date: 2026-08-28

Lane: design/specification only

Baseline: `391ff01f5e9da84b48761e641b4483cda14483cd`

Consumed authorization (historical evidence only):
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260827T122355Z_8e43eae7`

The authorization is permanently consumed and cannot be rerun, reused, resumed,
restarted, or succeeded automatically.

## 1. Design verdict

`V2_9_8B_4_2_2_ORCHESTRATION_CORRECTNESS_DESIGN_PASS`

All four audited defects have one safe, bounded, implementation-ready repair
design. The selected design does not weaken memory quality, cadence, exact-pair,
liquidity, safety, Source Governor, Central Scheduler, or full-run accounting
gates.

The main design choice is a durable, Scheduler-owned micro-quantum state machine
for later-cycle acquisition. Alternatives were rejected:

- reducing provider timeouts would change source capability without proving the
  work can complete;
- allowing the current roughly 115-second aggregate operation to cross a
  lifecycle deadline would regress cadence protection;
- an independent worker/source loop would bypass the Central Scheduler ownership
  model and create duplicate-call risk.

## 2. Defect-to-repair map

### 2.1 Defect 1 — 1h campaign-window binding order

**Proven cause.** `_audit_1h_close_from_evidence()` commits the physical
`WINDOW_1H` row and invokes Lane K/E2Z before the owned campaign-window row is
bound. `_bind_owned_continuation_memory_window_at_close()` performs the first
bind only after E2Z returns. Lane Q therefore lawfully returns
`CAMPAIGN_WINDOW_BINDING_MISSING`, and Lane K lawfully dirties the candidate.

**Affected production owners.**

- `src/printer_v1/operator_cli/one_command_15m_factory.py`
  - `_audit_1h_close_from_evidence`
  - `_owned_continuation_window_for_job`
  - `_bind_owned_continuation_memory_window_at_close`
- `src/printer_v1/operator_cli/operational_selective_1h.py`
  - new identity-only `WINDOW_1H` bind helper, parallel to
    `bind_precreated_15m_campaign_window_memory_row`

`cadence_authority.resolve_cadence_authority()` and
`lane_k_e2z_pipeline_wiring.run_e2z_pipeline()` are consumers and must not be
relaxed.

**Repair.** Add `_bind_precreated_1h_campaign_window_before_e2z()` and an
identity-only `bind_precreated_1h_campaign_window_memory_row()` owner. Resolve
the exact campaign window from the close step's Scheduler job, validate the full
campaign/run/cycle/slot/token/pair/window identity and the physical memory row,
CAS-bind `NULL -> memory_window_row_id`, commit, and read the binding back before
E2Z opens its independent database connection. An exact same-id bind is
idempotent; a second id, absent row, ambiguous row, wrong kind, or identity drift
fails closed.

The early bind changes no window state, terminal cause, terminal timestamp,
memory quality, `do_not_train`, promotion, or progression state. The later
terminal reconciler must verify/reuse the same binding and only then perform its
existing quality-derived terminal transition.

**Invariants preserved.** Lane Q still requires exact cadence ownership. Lane K
still dirties every genuine blocker. Non-campaign 1h closes remain outside the
bind path. Existing 15m behavior and final 4h transfer-first/owner behavior are
unchanged.

### 2.2 Defect 2 — Cycle-2 acquisition cannot fit beside TRACK_FAST cadence

**Proven cause.** `_later_cycle_acquisition_deadline_conflict()` correctly
protects the next lifecycle deadline, but the next direct-migration/persisted
refresh unit is declared as one aggregate of seven 5-second calls plus four
20-second verifier calls. Its roughly 115-second bound cannot fit in the usable
space between roughly 117-second TRACK_FAST deadlines. The +600/+1200/+1800
refresh opportunities therefore cannot begin.

**Affected production owners.**

- `src/printer_v1/operator_cli/one_command_15m_factory.py`
  - `_later_cycle_acquisition_deadline_conflict`
  - `_run_four_token_admission_boundary`
  - `_active_later_cycle_refresh_wake_at`
- `src/printer_v1/discovery/eligible_token_supply.py`
  - `AcquisitionQuantumBound`
  - `acquisition_quantum_bound`
  - `run_persistent_eligible_token_supply`
- `src/printer_v1/discovery/direct_migration_discovery.py`
  - split the internals of `run_direct_migration_discovery` into resumable,
    one-transport steps while retaining its public one-shot composition
- `src/printer_v1/discovery/pre_lifecycle_temporal_acquisition.py`
- `src/printer_v1/discovery/pre_lifecycle_refresh_work.py`
- `src/printer_v1/discovery/pre_lifecycle_refresh_composition.py`
- `src/printer_v1/operator_cli/pre_lifecycle_persistent_refresh_owner.py`
- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
  - later-cycle progress/callback ownership

**Repair.** Preserve the current aggregate source budget, calls, channel
rotation, exact verification, and timeouts, but execute them as durable
micro-quanta. One micro-quantum owns at most one outbound HTTP/RPC operation or
one bounded local-only transition. Ordinary source calls retain their 5-second
timeout; exact PumpSwap verification calls retain their 20-second timeout.

Each outbound micro-quantum receives its own deterministic Central Scheduler
`DISCOVERY_REFRESH` child job and Source Governor request key. Its declared
deadline bound is:

```text
provider timeout + 5-second bounded checkpoint/finalization reserve
```

The checkpoint transaction uses a busy timeout no greater than that reserve. A
quantum starts only when its whole bound is strictly before both the next
protected lifecycle deadline and the acquisition horizon. Otherwise it remains
pending and the coordinator yields to lifecycle work. No provider call is held
open across a yield, and no provider work occurs inside a SQLite transaction.

The initial opportunity is ordinal `0`. At attempt creation, the Central
Scheduler durably enqueues ordinals `1`, `2`, and `3` for immutable times
`attempt.evaluated_at + 600s`, `+1200s`, and `+1800s`; they are not derived from
the previous refresh's completion time. If capacity is already met, remaining
opportunities are cancelled with categorical evidence. If it is unmet, each due
opportunity becomes executable through its child quanta. Only one child quantum
per attempt may be `RUNNING` at once.

The existing aggregate operation ceiling is not increased. The sequence of
page, transaction, exact Pump/PumpSwap, pool, market, liquidity, and safety
steps is unchanged; a candidate becomes eligible only after every required
terminal step is present. Each micro-quantum seals its existing six-unit stage
evidence under a deterministic stage sequence derived from
`(opportunity_ordinal, quantum_ordinal)`. Splitting creates no extra source call
and no second accounting authority.

**Invariants preserved.** Lifecycle work always wins. Central Scheduler claims
every executable quantum. Source Governor owns every provider request. Exact
pair, migration, PumpSwap, liquidity, freshness, holder, safety, historical
disjointness, duplicate exclusion, and budget rules remain unchanged.

### 2.3 Defect 3 — terminal acquisition evidence loses observations

**Proven cause.** `run_persistent_eligible_token_supply()` rebuilds
`evaluated_mints`, `all_candidates`, rejection maps, provider-failure sets, and
`discovery_rounds` as action-local variables on each cooperative entry.
`authoritative_live_operational_campaign.py` preserves only limited in-memory
progress. The final call therefore constructs the exhaustion certificate from
an empty final-call view instead of the entire attempt.

**Affected production owners.**

- `src/printer_v1/discovery/eligible_token_supply.py`
  - `run_persistent_eligible_token_supply`
  - `ExhaustionCertificate`
  - `persist_exhaustion_certificate`
- `src/printer_v1/operator_cli/pre_admission_discovery_attempt.py`
  - attempt/source-evidence persistence and terminalization
- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
  - later-cycle callback and final supply diagnostics
- new attempt-evidence reducer module described in section 6

**Repair.** Persist append-only, attempt-owned categorical evidence after every
local gate or terminal source result. The final certificate is built only by a
fresh database reduction over the exact attempt, its fixed opportunities, its
micro-quanta, its immutable source links, and its evidence rows. In-memory
collections may remain caches but are never certificate authority.

The reducer must report at least:

- opportunities scheduled, claimed, completed, failed, and cancelled;
- refresh/discovery rounds actually executed;
- distinct mints and exact mint/pair identities observed;
- retained-inventory and re-observation outcomes;
- duplicate and already-used exclusions;
- exact-pair and PumpSwap confirmation outcomes;
- liquidity and safety/evidence outcomes;
- distinct provider/source failures by `source_failure_id`;
- final candidate rejection reasons and eligible reserve depth;
- remaining/cancelled work and controlling terminal reason.

For certificate compatibility, `unique_tokens_observed` means distinct mint
identities over the full attempt, `provider_failures` means distinct linked
source-failure rows, `discovery_rounds` means distinct opportunity ordinals with
at least one claimed terminal quantum, and `rejected_count` means distinct exact
candidate identities whose final attempt disposition is rejected. The next
certificate version also records observation/re-observation/rejection event
counts so repeated observations are visible rather than silently collapsed.

`NO_PAIR` is legal only after the durable reduction proves fewer than two exact
eligible, historically disjoint candidates and no executable attempt work
remains. `DURATION_EXHAUSTION` is legal only when the immutable acquisition
deadline is reached. Evidence mismatch, missing terminal source lineage, an
unexplained unexecuted opportunity, or active quantum residue produces an
internal/evidence blocker, never a zero-filled `NO_PAIR` certificate.

**Invariants preserved.** Evidence is categorical and provenance-bound; it is
not a score, rank, confidence, weight, or source preference. Raw provider bodies
remain in existing source tables, not duplicated into the attempt ledger.

### 2.4 Defect 4 — full-run accounting aggregation mismatch

**Proven cause.** Some initial discovery/holder transport constructors do not
receive the independent action-local observer, even though owner-side stage
evidence includes those transports. In addition, resumable pre-close claims
observe one reservation per source unit, but each new `result_json` assignment
replaces `lifecycle_reservations` with the current claim, leaving only the last
reservation for final reconstruction.

**Affected production owners.**

- `src/printer_v1/operator_cli/operational_memory_factory_command.py`
  - `_observe_transport_identity`
  - construction of the authoritative live owner and per-cycle observer ports
- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
  - `AuthoritativeLiveOperationalCampaignOwner.run_operational`
  - `_build_fixtures`
  - initial/later-cycle holder and discovery composition calls
- `src/printer_v1/operator_cli/one_command_15m_factory.py`
  - `_bind_preclose_source_unit_for_claim`
  - `_lifecycle_reservation_records_for_step`
  - pre-close checkpoint/yield result persistence
- `src/printer_v1/operator_cli/campaign_full_run_accounting.py`
  - `reservation_identities_for_step`
  - `prepare_full_run_accounting_owner`
  - `finalize_full_run_ownership_and_report`

`CampaignActionLocalLedger` and
`reconcile_full_run_owner_to_action_local()` remain strict and are not made more
permissive.

**Repair.** Every accounting-active transport composition, including initial
discovery and every initial/later-cycle holder path, must require the same
independent `transport_identity_observer` port. The callback fires at the real
`MeasuredTransportLedger.record_transport()` boundary after the canonical
identity exists and independently of stage sealing. It must never be populated
by copying owner evidence or final database counts. An absent observer while
campaign accounting is active is an immediate internal wiring failure.

For resumable pre-close work, bind one pending source unit with CAS, create its
unique reservation identity, merge it into the step's prior persisted
reservation manifest, and commit that cumulative manifest before the provider
attempt. Merge identity is the exact reservation ordinal plus full
run/job/step/token/pair/campaign/cycle/slot/source-unit ownership. An identical
repeat is idempotent; a conflicting ordinal, foreign owner, unexpected unit, or
missing earlier record fails closed. Each later checkpoint carries the complete
ordered manifest, never only the current reservation.

For pre-close steps, final accounting validates the cumulative persisted
records against the immutable source-unit manifest and reconstructs the owner
reservation identities from those records. Static one-reservation projection
must not replace the actual multi-claim set. Other lifecycle step projections
remain unchanged. Exact owner/action-local identity equality in both directions
is still required.

**Invariants preserved.** No call, reservation, byte, row, Scheduler, or stage
ceiling increases. Duplicate action-local observation remains a blocker. Missing
owner or action-local evidence remains a blocker.

## 3. Exact sequencing

### 3.1 1h bind before E2Z

```text
Scheduler claims exact CONTINUATION_CLOSE_AUDIT
-> close/persist physical WINDOW_1H and supporting context
-> E2Q audit produces candidate result
-> resolve Scheduler-owned campaign WINDOW_1H
-> validate campaign/run/cycle/slot/token/pair/window + physical row
-> CAS bind NULL -> memory_window_row_id (same-id repeat allowed)
-> commit physical row + bind
-> durable readback by window_id and memory_window_row_id
-> Lane Q/E2Z
-> classify actual clean/dirty/no-promotion result
-> existing terminal reconciliation reuses exact binding
-> existing standard-4h eligibility/barrier/transfer-first owner
```

No E2Z call is allowed before the durable readback.

### 3.2 Cadence-safe Cycle-2 acquisition

```text
create/claim one pre-admission attempt
-> enqueue opportunity 0 now and fixed refreshes +600/+1200/+1800
-> materialize deterministic child-quantum plan for due opportunity
-> select next PLANNED quantum
-> compare (timeout + 5s finalization) with next lifecycle/acquisition deadline
   -> does not fit: leave PLANNED; yield to lifecycle
   -> fits: Central Scheduler claim child job
-> CAS quantum PLANNED -> RUNNING and commit request identity
-> Source Governor executes at most one provider call
-> short terminal checkpoint links request/response-or-failure and evidence
-> CAS quantum RUNNING -> terminal; seal its exact accounting stage
-> yield to the main coordinator
-> resume from the next durable nonterminal quantum
-> opportunity terminal only when all required quanta terminal or fail closed
```

A transaction page, each transaction lookup, and each PumpSwap verifier RPC is a
separate quantum. Cursor movement or candidate promotion occurs only after the
same contiguous/complete evidence required today; partial work cannot promote.

### 3.3 Attempt evidence and terminal certificate

```text
terminal source/local gate
-> validate attempt/opportunity/quantum/subject owner
-> append deterministic evidence row + immutable source link
-> commit
...
acquisition horizon/terminal condition
-> cancel/terminalize every remaining child and parent Scheduler owner
-> require zero RUNNING quanta and no unexplained due opportunity
-> reduce all durable attempt evidence in one read snapshot
-> validate source request -> exactly one response or failure lineage
-> derive categorical totals, reasons, and evidence-manifest hash
-> insert one deterministic exhaustion certificate
-> CAS attempt RUNNING -> NO_PAIR with exact first terminal cause
-> commit certificate + attempt terminal together
```

If reduction or insertion fails, the transaction rolls back and the attempt is
failed/blocked with the exact internal evidence reason; it is not reported as
market scarcity.

### 3.4 Accounting observation and reservation aggregation

```text
real transport terminal boundary
-> owner stage ledger records canonical TransportOperationIdentity
-> independent action-local observer records the same execution-time identity
-> stage seals normally

pre-close Scheduler claim
-> CAS-bind exact pending source unit
-> derive its unique reservation identity
-> validate + merge with all prior step reservations
-> commit cumulative result_json reservation manifest
-> emit independent action-local reservation observation once
-> execute/reconcile the one unit
-> persist unit result while retaining the full reservation manifest
-> yield or terminalize
-> final accounting independently reconstructs owner set
-> strict owner/action-local equality
```

## 4. State/ownership model

### 4.1 Additive schema contract

Implementation is expected to add, but not apply during implementation review,
`migrations/062_pre_admission_acquisition_quantum_evidence.sql` with two narrow
tables.

`printer_pre_admission_acquisition_quanta` owns one local or provider unit:

- immutable campaign, campaign-run, authoritative factory-run, proposed cycle,
  attempt, opportunity ordinal, refresh-work (nullable for ordinal 0), stage,
  unit ordinal, subject identity, request key, Scheduler job, `not_before`,
  deadline, timeout, and checkpoint-before hash;
- state `PLANNED | RUNNING | SUCCEEDED | FAILED | CANCELLED`;
- nullable exact source request/response/failure IDs and checkpoint-after hash;
- terminal timestamp and immutable first terminal cause;
- unique attempt/opportunity/stage/unit/subject and unique request key/Scheduler
  job;
- one partial unique `RUNNING` quantum per attempt.

`printer_pre_admission_attempt_evidence` is append-only:

- deterministic evidence ID, attempt ID, opportunity ordinal, optional quantum
  ID, categorical evidence kind and outcome/reason;
- optional mint/pair subject identity;
- optional exact source request/response/failure IDs;
- exact provenance owner table/identity, observed time, canonical bounded JSON,
  payload SHA-256, and created time;
- immutable update/delete triggers and source response/failure match triggers.

Allowed evidence kinds are fixed categories such as candidate observed,
inventory re-observed, rejected, duplicate, already used, exact-pair result,
PumpSwap result, liquidity result, safety/evidence result, provider failure, and
opportunity terminal. They contain no score or rank.

Because three future waits are now expected, wait resolution must select the
earliest nonterminal due identity rather than require exactly one `WAITING` row.
The exact legal shape is ordinals 1..3 at their fixed due times, at most one
`CLAIMED` parent work, and at most one `RUNNING` child quantum. A missing,
duplicate, shifted, extra, or multiply-claimed ordinal is unsafe Scheduler state.

Existing owners remain authoritative:

- `printer_pre_admission_discovery_attempts`: one Cycle-2 attempt;
- `printer_pre_lifecycle_discovery_refresh_waits`: fixed opportunity ordinals
  1..3 and parent Scheduler jobs;
- `printer_pre_lifecycle_discovery_refresh_work`: claimed opportunity work;
- `printer_source_requests/responses/failures`: provider truth;
- `printer_memory_factory_campaign_windows`: memory/campaign bind truth;
- `CampaignSixUnitOwner`: accounting authority;
- `CampaignActionLocalLedger`: independent verification only.

No campaign token slot exists while the attempt is still acquiring candidates;
the proposed-cycle/attempt identity is therefore the only lawful pre-admission
owner. Only `PAIR_READY` may freeze two immutable attempt items at slot ordinals
1 and 2, and the existing atomic consumption path then creates the real Cycle-2
campaign slots. A quantum or evidence row must never fabricate a slot identity.

### 4.2 CAS and idempotency

- Memory binding permits `NULL -> exact id` or exact-id readback only.
- A quantum is provider-call eligible only after one successful
  `PLANNED -> RUNNING` CAS under its exact Scheduler claim.
- Deterministic request keys include attempt, opportunity, stage, unit, subject,
  and attempt ordinal. Before calling a provider, existing source rows are
  checked. A terminal exact row is reconciled without a new call; an unterminated
  row is `UNKNOWN_INTERRUPTED_AFTER_REQUEST` and is never automatically retried.
- Evidence insertion accepts an existing deterministic ID only when every field
  and hash is identical; divergence is an integrity blocker.
- Reservation merge is a deterministic ordered set by reservation ordinal;
  identical persistence is idempotent, but duplicate action-local execution
  observation remains an accounting blocker.
- Opportunity due times and quantum identity never change on retry/yield.

### 4.3 Resume and crash behavior

Cooperative resume means re-entry by the same authorized running campaign. It
loads durable attempt/wait/work/quantum/evidence state; it does not rely on
`later_cycle_progress` for truth.

A normal yield leaves the parent opportunity work active and the next child
quantum `PLANNED`. The main coordinator continues lifecycle work and later
re-enters the same exact owner. Completed quanta are never reissued.

A process crash does not authorize restart or reuse. Recovery may read and
terminalize orphaned owners, or reconcile a source request that already has one
exact terminal result, but may not issue a new provider call. An ambiguous
`RUNNING` quantum or unterminated source request blocks the attempt/campaign and
is preserved in terminal evidence.

## 5. Failure behavior

Every repair fails closed:

- absent/ambiguous/mismatched 1h ownership: no E2Z clean promotion, typed bind
  blocker, existing cleanup;
- conflicting memory rebind: integrity failure, never overwrite;
- no safe quantum interval: leave pending and run lifecycle work;
- acquisition deadline reached: cancel pending work, preserve which
  opportunities/quanta did and did not execute;
- Scheduler owner/claim mismatch: no provider call;
- Source Governor denial/provider failure: terminal source evidence retained,
  no gate bypass and no same-quantum retry;
- partial direct-migration chain: no candidate promotion or cursor advance past
  unresolved evidence;
- evidence/source-lineage mismatch: no exhaustion certificate and no `NO_PAIR`
  scarcity claim;
- terminal certificate/attempt CAS conflict: rollback both;
- missing action-local observer: internal accounting blocker before PASS;
- missing/conflicting reservation history: full-run accounting remains blocked;
- owner/action inequality: unchanged accounting failure;
- cancellation/supervision loss: cancel every pending Scheduler child and retain
  first terminal cause.

No failure path forces admission, clean memory, 1h continuation, or 4h
progression.

## 6. Implementation boundary

Expected production changes, and no others without a new audit/design decision:

1. `migrations/062_pre_admission_acquisition_quantum_evidence.sql` — additive
   quantum/evidence ownership only.
2. `src/printer_v1/operator_cli/one_command_15m_factory.py` — pre-E2Z 1h bind,
   per-quantum deadline check, and cumulative pre-close reservations.
3. `src/printer_v1/operator_cli/operational_selective_1h.py` — identity-only,
   idempotent precreated 1h bind owner.
4. `src/printer_v1/discovery/pre_lifecycle_temporal_acquisition.py` — fixed
   opportunity schedule and durable summary reads.
5. `src/printer_v1/discovery/pre_lifecycle_refresh_work.py` — resumable parent
   work/child ownership integration.
6. New `src/printer_v1/discovery/pre_lifecycle_refresh_quantum.py` — quantum
   insert/claim/checkpoint/terminal CAS owner.
7. `src/printer_v1/operator_cli/pre_lifecycle_persistent_refresh_owner.py` —
   materialize/resume fixed opportunities and yield between child quanta.
8. `src/printer_v1/discovery/pre_lifecycle_refresh_composition.py` and
   `src/printer_v1/discovery/direct_migration_discovery.py` — expose one-call
   resumable stages while preserving existing one-shot callers.
9. `src/printer_v1/discovery/eligible_token_supply.py` — durable progress input,
   terminal reducer use, and certificate-version update.
10. `src/printer_v1/operator_cli/pre_admission_discovery_attempt.py` plus new
    `src/printer_v1/operator_cli/pre_admission_attempt_evidence.py` — append-only
    evidence persistence and deterministic certificate reduction.
11. `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py` —
    replace in-memory progress authority, pass observers to every discovery and
    holder composition, and preserve exact attempt diagnostics.
12. `src/printer_v1/operator_cli/operational_memory_factory_command.py` — require
    and wire the independent per-cycle transport observer across all paths.
13. `src/printer_v1/operator_cli/campaign_full_run_accounting.py` — reconstruct
    cumulative pre-close reservations and retain strict equality.

No change is designed for Lane Q, Lane K, cadence thresholds, eligibility
thresholds, exact-pair policy, Source Governor policy, 4h transfer-first owner,
retrieval, decisions, or financial code.

## 7. Bounded verification plan

Implementation requires focused disposable/offline tests only, plus nearest
affected contract regressions. No broad suite is justified unless the approved
implementation expands beyond section 6.

### 7.1 1h bind and progression

1. Production 1h close proves the exact campaign row is bound and committed
   before the mocked/real Lane Q boundary reads it.
2. E2Q-clean + Lane-Q-clean 1h produces the existing clean episode, terminal
   `CLEAN_PROMOTED`, and standard clean 1h -> planned/continuing 4h path.
3. Missing, ambiguous, wrong campaign/run/cycle/slot/token/pair/window-kind, and
   conflicting memory-row bindings fail closed before E2Z.
4. Exact repeated bind is idempotent; later terminal reconciliation neither
   duplicates nor overwrites the bind.
5. Genuine Lane-Q blocker still invokes Lane K dirty/do-not-train behavior.
6. Existing 15m pre-E2Z binding and final 4h transfer-first/owner binding tests
   remain green.

### 7.2 Cadence-compatible acquisition

7. A synthetic TRACK_FAST two-slot 1h timeline runs its lifecycle deadlines
   while a direct-migration opportunity makes progress through 5s/20s child
   quanta.
8. No child starts unless timeout + 5s reserve fits; lifecycle claim/start/capture
   lateness is no worse than the existing protected baseline.
9. Aggregate 115-second direct work spans multiple safe gaps without one
   115-second call and without duplicate provider requests.
10. Opportunity waits are durably scheduled at exact +600/+1200/+1800 and all
    become claimable/executable when capacity remains unmet.
11. A late prior opportunity does not shift a later due time; only one child is
    RUNNING, and due work remains pending rather than disappearing.
12. Cancellation, acquisition deadline, Source Governor denial, provider
    timeout, and Scheduler claim mismatch leave zero unauthorized calls and
    correct terminal child/parent state.
13. Crash boundaries before call, after source request, after source terminal,
    and before/after checkpoint prove no duplicate call, no skipped evidence,
    and fail-closed ambiguity.

### 7.3 Durable terminal evidence

14. Multiple cooperative entries reconstruct nonzero full-attempt unique mints,
    observations, re-observations, refresh rounds, exact-pair outcomes,
    rejections, duplicates/already-used exclusions, and source operations.
15. One provider failure is linked and counted exactly once after later entries;
    it cannot collapse to zero or be double-counted from summary labels.
16. Candidate rejection reasons and liquidity/safety outcomes survive resume and
    appear in the final certificate with the same evidence-manifest hash.
17. Missing source terminal lineage, divergent duplicate evidence, active
    quantum residue, or an unexplained unexecuted opportunity blocks certificate
    creation and cannot terminalize as `NO_PAIR`.
18. Deadline with unmet capacity and complete evidence yields exactly
    `NO_PAIR` plus `DURATION_EXHAUSTION`; true source/market/eligibility terminals
    retain their existing categorical precedence.

### 7.4 Full-run accounting

19. Initial discovery, initial holder, later discovery, and later holder
    transports each reach both the owner stage and the independent action-local
    observer at execution time.
20. Removing any observer edge blocks full-run reconciliation; copying sealed
    owner evidence is not accepted as action-local evidence.
21. A pre-close step with multiple source-unit claims persists all reservation
    identities in deterministic order through every yield and terminal result.
22. Same-id reservation persistence is idempotent; conflicting or foreign
    reservation identity fails closed.
23. Full transport and reservation owner/action-local sets reconcile exactly;
    one missing, extra, duplicate, or mismatched identity still blocks.
24. Multi-cycle projection partitions by campaign/run/cycle/slot and remains
    exact when Cycle-1 lifecycle and Cycle-2 acquisition overlap.

Static implementation checks must include migration catalogue/head coherence,
compile/import checks for changed modules, `git diff --check`, lock-language
scan, and authoritative-DB non-mutation verification. A later bounded proof must
use a disposable DB and fixture transports unless separately authorized.

## 8. Explicit non-goals

This lane does not:

- create, prepare, apply, reuse, resume, or restart an authorization;
- run Printer, Central Scheduler, providers, RPC, or WebSocket;
- change TRACK_FAST/TRACK_NORMAL thresholds or lifecycle priority;
- lower liquidity, exact-pair, Pump/PumpSwap, safety, holder, freshness,
  provenance, or historical-disjointness requirements;
- add paid providers, retries, endpoint rotation, independent loops, capacity,
  scoring, ranking, confidence, weighting, embeddings, or vectors;
- make `WINDOW_5M_MICRO_EVENT` a main outcome window;
- unlock `WINDOW_12H`, `WINDOW_24H`, retrieval, paper decisions,
  BUY/SELL/HOLD, positions, trades, audits, PnL, wallet/private-key/signing,
  real funds, or live execution;
- reclassify or backfill the consumed historical campaign;
- prove four-token/two-cycle completion by design alone.

## 9. Next permitted action

`DESIGN PASS -> EXPLICITLY APPROVED IMPLEMENTATION LANE`

No implementation, migration application, bounded campaign, proof campaign, or
authorization is approved by this design.
