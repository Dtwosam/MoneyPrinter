# Printer V1 V2-9.8B Timely Closing-Context Production Design

**Design kind:** documentation-only specification

**Original design starting HEAD:** `536c8e4bedb3a15f500c76a1de5eac21a3c6f9fa`

**Claim-granularity amendment base HEAD:** `d28c040e1ae30946d8e405a5d5d0116eec822ae5`

**Closing-context failure-semantics amendment base HEAD:** `24e7ceed8c7b3fca261a45a00c81cc50a0b2844e`

**Active lane:** `V2-9.8B Lane 2 — Multi-Token Evidence-Deadline Scheduling`

**Design verdict:** `V2_9_8B_CLOSING_CONTEXT_FAILURE_SEMANTICS_DESIGN_AMENDMENT_ACCEPTED_READY_FOR_NARROW_IMPLEMENTATION`

**Runtime status:** the current phase split and current timing corrective implementation remain unaccepted

## 1. Verdict

Repository evidence supports the preferred direction with one necessary
refinement.

Printer shall add one Central-Scheduler-owned logical pre-close critical
acquisition step for each active close family. The step is one persisted,
cooperatively resumable Scheduler job. One claim may execute exactly one
logical source unit and at most one governed provider attempt; it must then
checkpoint and return control to the Central Scheduler before another unit.
The step uses the existing governed source owners early enough to make each
evidence class lawfully producible, persists durable per-unit
request/response/failure truth plus an exact manifest, and never creates or
infers a closing snapshot.

The exact closing snapshot remains an independently claimable,
cadence-sensitive `CLOSE_EVIDENCE` step. After that snapshot exists, the
existing `CLOSE_CONTEXT` phase becomes a binding/resolution phase: it validates
the exact pre-close unit manifest, rehydrates its durable source records, binds
eligible observations to the exact closing snapshot/window, resolves periodic
broad context, and classifies late or failed results honestly. `CLOSE_AUDIT`
then consumes either complete context or an explicit partial/failed/unknown
context result.

The resulting normal execution sequence is:

```text
PRE_CLOSE_CRITICAL unit
-> Central Scheduler reselection
-> PRE_CLOSE_CRITICAL unit
-> Central Scheduler reselection
-> ... until the exact unit manifest is terminal
-> Central Scheduler reselection
-> CLOSE_EVIDENCE
-> Central Scheduler reselection
-> CLOSE_CONTEXT_BIND
-> Central Scheduler reselection
-> CLOSE_AUDIT
```

That is the normal timely path, not a dependency that lets pre-close work hold
capture. If `CLOSE_EVIDENCE` becomes due while units remain, its higher
intra-close phase wins; the snapshot may capture independently and remaining
units later become terminal timely, late, missed, failed or not required.

The dependency model is a fork-join rather than a hard success chain:

```text
PRE_CLOSE_CRITICAL exact terminal unit set --\
                                             -> CLOSE_CONTEXT_BIND -> CLOSE_AUDIT
CLOSE_EVIDENCE exact successful snapshot ----/
```

Provider failure or missing pre-close context must not suppress the closing
snapshot. Exact evidence failure still prevents exact binding and closing
audit under the existing integrity law.

This design requires the three family-level pre-close step kinds and resumable
unit metadata behavior. Beyond the one family-level pre-close row already
designed, it requires no source-unit step kinds or Scheduler rows, new
Scheduler category, worker loop, source adapter, provider, configuration,
table, column, or migration. Section 24 is the controlling claim-granularity
and safe-scheduling amendment.

If the later implementation and bounded proof conform to this specification,
the producer-capability targets are:

| Window family | Target producer verdict | Scope of the claim |
| --- | --- | --- |
| `WINDOW_15M` | `PRODUCIBLE` | Scheduler can lawfully run the real required producer before the zero-allowance cutoff and bind afterward; provider success is not promised. |
| `WINDOW_1H` | `PRODUCIBLE` for the existing mandatory safety-overlay gate | Safety/holder observations are bounded by logical end and never borrow snapshot +60; this does not invent currently absent class gates. |
| `WINDOW_4H` | `PRODUCIBLE` | Broad context has an at/before-end producer path, while only exact snapshot, closing safety composite (including required contributions), and EXIT retain +60. |

These are implementation proof targets, not claims about the current
unaccepted runtime and not a guarantee that public sources will return usable
evidence.

## 2. Proven problem

The accepted producibility audit established:

| Window family | Accepted current verdict |
| --- | --- |
| `WINDOW_15M` | `NOT_PRODUCIBLE` |
| `WINDOW_1H` | `NOT_PRODUCIBLE` |
| `WINDOW_4H` | `PRODUCIBLE_ONLY_IF_PREEXISTING_TIMELY_CONTEXT_EXISTS` |

The current split executes:

```text
CLOSE_EVIDENCE
-> CLOSE_CONTEXT source calls
-> CLOSE_AUDIT
```

That ordering keeps the closing snapshot short and cadence-sensitive, but it
places the only real safety/holder/quote/market/chain acquisition owner after
the exact closing snapshot. The resolver correctly rejects newly observed
15m/1h context after `window_end_at` and newly observed 4h market/chain context
after `window_end_at`.

The historical path proved that the current persistence model can separate
observation and binding:

```text
governed source observation before close
-> exact snapshot capture
-> evidence binding after snapshot_id exists
```

The repair must restore that lawful separation without restoring the old
monolithic worker claim.

## 3. Approaches considered

### 3.1 Chosen: one resumable pre-close phase, one source unit per claim, plus later exact binding

Advantages:

- moves existing calls instead of duplicating them;
- preserves the current source adapters and Source Governor path;
- gives the Central Scheduler a reselection point after every bounded source
  unit and before exact capture;
- retains truthful source times in already-durable source rows;
- obtains exact snapshot identity only from real capture;
- permits complete, partial, failed, late, or missing context truth to reach
  audit; and
- needs no schema migration.

The design below adopts this approach.

### 3.2 Rejected: depend only on periodic/pre-existing rows

Periodic market and chain rows are reusable, but periodic-only context cannot
produce token-specific, exact-closing-snapshot safety and quote evidence. It
would leave 15m and 1h non-producible.

### 3.3 Rejected: move all source calls into `CLOSE_EVIDENCE`

This recreates the historical monolithic claim. Serial provider work would run
before the exact snapshot without a Scheduler reselection point, allowing one
token to delay sibling close evidence and higher-priority cadence work.

### 3.4 Rejected: one new Scheduler step kind per provider/evidence class

Provider-specific step kinds would create a permanent provider-shaped phase
taxonomy and multiply dependency rules. Multiple same-kind Scheduler rows would
avoid provider-specific kinds but would still multiply Scheduler work-item
accounting and row ceilings. The existing Scheduler supports cooperative
`yield_job`, while run-step `result_json` can durably hold a frozen unit
manifest. Section 24 therefore chooses one resumable family-level row whose
individual claims are bounded to one unit. It obtains the reselection boundary
without either provider JobKinds or additional Scheduler rows.

## 4. Exact phase architecture

### 4.1 New step kinds

Add exactly these close-family step kinds:

| Window family | New step kind | Existing later steps retained |
| --- | --- | --- |
| 15m | `WINDOW_CLOSE_PRE_CLOSE_CRITICAL` | `WINDOW_CLOSE_EVIDENCE`, `_CONTEXT`, `_AUDIT` |
| 1h | `CONTINUATION_CLOSE_PRE_CLOSE_CRITICAL` | `CONTINUATION_CLOSE_EVIDENCE`, `_CONTEXT`, `_AUDIT` |
| 4h | `LONG_CONTINUATION_CLOSE_PRE_CLOSE_CRITICAL` | `LONG_CONTINUATION_CLOSE_EVIDENCE`, `_CONTEXT`, `_AUDIT` |

All remain in the existing `MEMORY_WINDOW_CLOSE` AGENTS category. No new
`JobKind`, queue, scheduler, thread, process, or worker is authorized.

Each close owns one row of its family-level pre-close step kind, not one row per
provider. Its frozen `source_unit_manifest` is the resumable representation.
Source units are metadata and claim boundaries, not Scheduler categories.

`CLOSE_CONTEXT` may retain its current step-kind name. Its responsibility
changes from “make new required main-window calls and persist them” to
“join, validate, bind, resolve, classify and report.” Reports should describe
it as `CLOSE_CONTEXT_BIND`; historical database vocabulary need not be renamed.

### 4.2 Per-window lifecycle order

The intended temporal order for one window is:

1. `PRE_CLOSE_CRITICAL` is scheduled before the close boundary.
2. Scheduler claims it for exactly one eligible source unit, durably records
   that unit, yields the job, and reselects globally.
3. Step 2 may repeat only for a different nonterminal unit while pre-close work
   remains the globally selected work. It cannot hold a due evidence claim.
4. `CLOSE_EVIDENCE` independently captures only the exact closing snapshot;
   context waits until both evidence and the unit manifest are terminal.
5. Scheduler reselects globally.
6. `CLOSE_CONTEXT` joins the terminal acquisition manifest with the successful
   evidence result and binds/resolves context.
7. Scheduler reselects globally.
8. `CLOSE_AUDIT` closes and audits with complete or honest incomplete context.

`CLOSE_EVIDENCE` is not success-dependent on `PRE_CLOSE_CRITICAL`. The
pre-close manifest must reach a durable terminal result before context joins
it, but individual unit results may be `TIMELY`, `PARTIAL`, `FAILED`, `LATE`,
`MISSED_CUTOFF`, `UNKNOWN_INTERRUPTED_AFTER_REQUEST`, `NOT_REQUIRED`, or
`CANCELLED_BEFORE_ATTEMPT`. Provider/data outcome is not the same as Scheduler
step integrity.

### 4.3 Intra-category selection order

Typical time separation causes pre-close work to run first. If different
tokens' phases are simultaneously due, the existing cadence protection must
win. Inside `MEMORY_WINDOW_CLOSE`, use this categorical order:

| Order among simultaneously due close work | Phase |
| --- | --- |
| 1 | `CLOSE_EVIDENCE` |
| 2 | `PRE_CLOSE_CRITICAL` |
| 3 | `CLOSE_CONTEXT` |
| 4 | `CLOSE_AUDIT` |

This is deliberately different from the normal per-window temporal sequence.
A token B pre-close call may not delay token A's already-due exact closing
snapshot. The earlier `scheduled_for` and separate pre-close deadline give
pre-close work its lawful opportunity before that collision.

## 5. Evidence-class ownership matrix

Classifications:

- **A — PERIODIC / PREEXISTING CONTEXT:** an existing timely governed row may
  be reused without a close-time source call.
- **B — PRE-CLOSE CRITICAL ACQUISITION:** one bounded governed source attempt
  must start early enough to be capable of meeting the class cutoff.
- **C — EXACT CLOSING SNAPSHOT:** only the cadence-sensitive evidence phase may
  create it.
- **D — POST-CAPTURE BINDING:** source truth already observed is bound or
  derived only after exact snapshot identity exists.
- **E — POST-CLOSE SUPPORT ONLY:** a result outside its class cutoff may be
  retained but cannot support historical CLEAN eligibility.

Each occurrence at one lifecycle stage has exactly one classification. A table
cell lists multiple letters only to show the ordered lifecycle of that evidence
class—for example, periodic reuse (`A`) or fallback acquisition (`B`), followed
by exact post-capture binding (`D`), with an ineligible late result retained
only as support (`E`). The letters are not alternative quality labels and do
not permit one stage to masquerade as another.

| Evidence class | 15m | 1h | 4h | Exact design treatment |
| --- | --- | --- | --- | --- |
| Market regime | A, B, D, E | A, D, E | A, B, D, E | Resolve a valid periodic row first. For 15m/4h only, if absent, move the existing single broad-context call into pre-close acquisition. Bind/persist with real response time. Never admit an observation after `window_end_at`. This lane does not invent a new 1h broad-context requirement or call. |
| Solana chain heat | A, B, D, E | A, D, E | A, B, D, E | Same governed broad response and timing law as market. Existing shared rows remain reusable. |
| Safety | B, D, E | B, D, E | B, D, E | Move the existing GoPlus/core-RPC safety attempt into pre-close acquisition. Bind exact contributions/composite after snapshot. 15m/1h cutoff is end; 4h cutoff remains end +60. |
| Holder evidence | B, D, E when conditional | B, D, E when conditional | B, D, E when conditional | Preserve the current GoPlus-dependent primary and single approved backup rule. Holder inherits safety cutoff and has no independent allowance. |
| ENTRY quote | B, D, E | E / unchanged non-requirement | A/B at existing 4h opening, D, E | Move the current required 15m ENTRY attempt into pre-close acquisition and bind to the exact expected 15m snapshot as the current resolver requires. Preserve the existing 4h opening acquisition/binding. Do not add a new 1h ENTRY requirement in this slice. |
| EXIT quote | B, D, E | E / unchanged non-requirement | B, D, E | Move the current 15m and 4h EXIT attempts into pre-close acquisition. Preserve 15m cutoff at end and 4h cutoff at end +60. Do not add a new 1h EXIT requirement in this slice. |
| Trading flow | C, D | C, D | C, D | No source call. Derive later from the exact admitted current-run snapshot set and real snapshot times. This design does not add a missing 1h class gate. |
| Chart / volatility | C, D | C, D | C, D | Same exact snapshot-set derivation; no later refresh may enter the closed set. This design does not add a missing 1h class gate. |
| Exact closing snapshot | C | C | C | Remains exclusively owned by `CLOSE_EVIDENCE`; no pre-close phase may fabricate, predict, reserve, or preassign its database id or capture time. |

The 1h audit found no current closing-quote or full shared-context CLEAN gate.
This design repairs the proven required 1h safety timing defect without silently
expanding 1h evidence requirements. A future explicit authority must define
any broader 1h gate. Absence of such a gate is not permission to infer context.

## 6. Timing and deadline contract

### 6.1 Frozen time distinctions

```text
source_requested_at
!= source_observed_at / failed_at
!= preclose_bound_at
!= closing_snapshot_captured_at
!= window_end_at
!= Scheduler started_at / finished_at
```

The source response/failure owns observation truth. The context phase owns
binding truth. The exact-pair response owns snapshot capture truth. No phase
copies one timestamp into another field to obtain eligibility.

### 6.2 Existing evidence deadline remains unchanged

The accepted `CLOSE_EVIDENCE` `scheduled_for`, `deadline_at`, last-ACTUAL-capture
basis, forced-close min, clean/dirty/block boundaries, and evaluation formulas
remain byte-for-byte contractually unchanged. This design creates a separate
pre-close scheduling contract; it does not modify evidence arithmetic.

### 6.3 Class cutoffs remain unchanged

| Family/class | Lawful observation cutoff |
| --- | --- |
| 15m snapshot, market, chain, safety, holder, ENTRY, EXIT | `window_end_at` |
| 1h safety and holder | `window_end_at` |
| 1h forced closing snapshot only | existing freshness-clean band through `window_end_at + 60s` |
| 4h market and chain | `window_end_at` |
| 4h ENTRY | existing opening/original boundary |
| 4h closing snapshot, safety composite (including required holder contribution) and EXIT | `window_end_at + 60s` |
| flow/chart | exact lawful snapshot set for that family |

15m remains exactly:

```text
closing_evidence_allowance_seconds = 0
closing_evidence_cutoff_at = window_end_at
```

### 6.4 Separate pre-close fire/deadline formula

Each planned pre-close step receives a frozen unit manifest. Each potentially
required unit `u` receives:

```text
source_unit_identity
acquisition_cutoff_at(u)
bounded_claim_seconds(u)
latest_safe_claim_at(u)
desired_preclose_scheduled_for
earliest_preclose_schedulable_at
contention_cohort_identity
owner-scoped deterministic unit tie ordinal
```

The conservative lead formula is:

```text
bounded_claim_seconds(u)
  = existing hard timeout for u's one governed attempt
    + deterministic maximum Source-pacer wait for u
    + bounded request/result/checkpoint/yield reserve

latest_safe_claim_at(u)
  = acquisition_cutoff_at(u) - bounded_claim_seconds(u)

cohort_required_lead_seconds
  = sum(bounded_claim_seconds(u) for every potentially required unit u
        in the exact contention cohort)
    + unit_count * SCHEDULER_RESELECTION_RESERVE_SECONDS

desired_preclose_scheduled_for
  = earliest acquisition_cutoff in the exact contention cohort
    - cohort_required_lead_seconds
```

The formula is deliberately conservative: all potentially required work is
given a chance before the earliest cutoff, including conditional holder
fallback. The existing 4h +60 exception remains available for truthful actual
results; it is not used to plan routine market/chain delay. Every claim still
checks its unit's real `latest_safe_claim_at` before making a call.

The exact contention cohort contains Scheduler-owned pre-close work whose
reserved single-worker execution intervals overlap and is frozen from exact
campaign/run/cycle/token/slot/window identities at planning time. Its ordinal
uses the accepted token/cycle fairness rotation and stable identity tie-breaks,
never a score, confidence, historical latency estimate, outcome, or permanent
cycle preference.

`SCHEDULER_RESELECTION_RESERVE_SECONDS` is a per-unit Scheduler handoff bound,
not an evidence allowance. The later implementation must define its exact
constant from bounded local checkpoint/yield/reselection operations and prove
it in disposable tests before runtime acceptance.
It may not be derived from historical provider latency. If the implementation
cannot prove a finite bound for configured one-attempt source timeouts, pacing,
and local handoff, it must stop `BLOCKED` rather than invent or learn one.

Scheduling makes timely acquisition possible; it does not guarantee CLEAN.
Higher AGENTS categories, Source Governor denial, provider latency, timeout,
or resource exhaustion may still make evidence late/missing. Actual source
timestamps remain final authority.

`desired_preclose_scheduled_for`, `earliest_preclose_schedulable_at`, and the
fail-closed comparison between them are defined normatively in Section 24.6.
No pre-close acquisition deadline is derived from the accepted
`CLOSE_EVIDENCE` cadence deadline.

### 6.5 Provider response crossing a boundary

- 15m or 1h safety/holder/15m quote observed after `window_end_at` is late and
  cannot support CLEAN, even if the request started earlier.
- 4h market/chain observed after `window_end_at` is late.
- Each single-attempt 4h safety/holder/EXIT unit may remain eligible when its
  real observation time is no later than `window_end_at + 60s` and all other
  gates pass. This is not a retry or broader context allowance.
- A call still running near exact capture can delay the single worker. The
  separate lead-time and hard-timeout contract is intended to prevent normal
  overlap, but a real overrun is reported honestly; it never widens cadence or
  evidence thresholds.

## 7. Acquisition and binding identity contract

### 7.1 Identity known before acquisition

Every `PRE_CLOSE_CRITICAL` unit manifest entry and every yielded claim must be
projected with the exact:

- `campaign_id`;
- campaign `run_id`;
- `cycle_id`;
- `token_slot_id`;
- campaign `window_id`;
- `factory_run_id`;
- Scheduler job/work ids;
- token row id and immutable mint;
- pair row id and pair address;
- tracking lane;
- window family;
- logical `window_end_at` and class cutoffs;
- pre-close/evidence/context/audit step keys;
- close-phase contract version;
- intended closing work identity; and
- exact governed request-key prefix, source-unit identity, fixed attempt
  ordinal `1`, and allowed source request family.

The acquisition envelope shall store those identities plus, per attempted
source:

- source name/request kind;
- source request id;
- source response id or source failure id;
- real `requested_at`, `received_at`, or `failed_at`;
- returned target identity needed by the existing normalizer;
- source/data-quality status; and
- one terminal disposition: timely candidate, late, partial, failed, denied,
  not required, or not attempted.

The source tables remain the normalized-payload/provenance authority. The
envelope references those durable rows; it does not serialize mutable adapter
objects or fabricate evidence rows before snapshot identity exists.

### 7.2 Identity known only after capture

Only successful `CLOSE_EVIDENCE` may provide:

- exact closing `snapshot_id`;
- exact snapshot source request/response/failure ids;
- actual `closing_snapshot_captured_at`;
- successful current-run ledger attachment; and
- exact evidence-phase Scheduler terminal identity.

The memory-window row id may remain unavailable until `CLOSE_AUDIT` creates or
resolves it.

### 7.3 Binding validation

Before any token-specific evidence row is bound, `CLOSE_CONTEXT` must prove:

1. exactly one terminal pre-close step with the expected contract/version,
   exact frozen unit manifest, and intended evidence step;
2. every expected unit has exactly one terminal result or an exact typed
   `NOT_REQUIRED`/unschedulable result, with no duplicate request identity;
3. exactly one successful evidence step with an actual exact snapshot;
4. identical campaign/run/cycle/slot/window/factory-run/stage/work-scope owner;
5. identical token/mint/pair/pair-address/tracking-lane/window family;
6. exact source request/response/failure linkage and request-key prefix;
7. returned source target matches the immutable intended target;
8. each real observation time satisfies its own class cutoff before it is
   marked main-window eligible; and
9. no source record is substituted from another token, pair, cycle, window,
   historical close, or nearby snapshot.

Binding writes the actual closing snapshot id but never rewrites source
observation time. Idempotent replay may return the same exact binding; a
different source or snapshot identity is a conflict and fails closed.

### 7.4 Safety composite timing representation

The current composite uses `evidence_captured_at` as its resolver time. For a
post-capture deterministic composition of frozen pre-close inputs, the later
implementation shall:

- keep every contribution's real `captured_at`;
- set composite `evidence_captured_at` to the latest underlying observation
  actually used by the composite, not to binding time;
- retain the real later `composite_evaluated_at` and `evidence_bound_at` in the
  existing phase/window supporting JSON; and
- prove that evaluation adds no post-cutoff source fact.

If composition performs a new source evaluation after the cutoff, that real
evaluation is late. The timing metadata may not be used to hide it. Existing
JSON surfaces are sufficient; no schema migration is required.

## 8. `WINDOW_15M` behavior

The 15m pre-close manifest contains logical units for market/chain reuse with
at most one fallback call, GoPlus safety, optional core safety, ENTRY, EXIT,
conditional holder primary, and the single approved conditional holder backup.
Independent units do not have a fixed provider order. Only these real
acquisition dependencies apply:

1. holder primary becomes required only after the GoPlus unit truthfully
   reports holder concentration unknown; and
2. holder backup becomes required only after the primary holder unit ends in
   an existing backup-eligible transient failure.

Safety composition happens after capture and therefore imposes no acquisition
order on independent safety/core/quote/market units. Market/chain periodic
resolution and its possible one-call fallback are one bounded logical unit;
that claim never proceeds to a second unit even when no fallback call is made.

All token-specific results remain unbound source records until the exact
snapshot exists. `CLOSE_EVIDENCE` then captures only the closing snapshot.
`CLOSE_CONTEXT` binds eligible safety/holder/ENTRY/EXIT results to that exact
snapshot, persists/resolves market/chain, derives nothing from a later source
refresh, and passes timing truth to audit.

No response observed after `window_end_at` can support CLEAN. A request that
started before the end but completed after it is late. A delayed closing
snapshot receives no allowance; the accepted cadence/evidence owners classify
it without changing the context cutoff.

## 9. `WINDOW_1H` behavior

The 1h pre-close manifest moves the existing required safety-only units earlier:

- GoPlus safety;
- existing core Solana safety where active;
- conditional holder primary; and
- the one approved conditional holder backup.

No new 1h market, chain, ENTRY, or EXIT source call is introduced. Existing
periodic context may remain attached/reported under its existing authority, but
this lane does not define a new 1h CLEAN class gate.

The pre-close safety/holder observations must be no later than the fixed 1h
`window_end_at`. The forced closing snapshot may independently be freshness
clean through +60 seconds. That snapshot allowance never changes the safety or
holder cutoff.

After the 1h window row exists, `attach_first_hour_safety_overlay` must verify:

- exact memory window/token/pair/mint/pair-address/closing snapshot identity;
- composite latest-observation time `<= window_end_at`;
- every required contribution `captured_at <= window_end_at`;
- acceptable source trace, target, freshness and composite policy; and
- exact pre-close and evidence owner linkage.

Failure of any timing check prevents a clean safety overlay and reaches audit
as late/missing/invalid context. It does not erase the closing snapshot.

## 10. `WINDOW_4H` behavior

The 4h pre-close market/chain unit first resolves valid periodic rows. If
either required shared row is absent, that same bounded unit may make the
existing single governed broad-context request before close and later persist
both supported contexts from that one response. It then yields. Market/chain
remain eligible only when observed no later than `window_end_at` and within
existing freshness/provenance rules.

Separate claims of the same resumable pre-close step make the existing
one-attempt closing safety, conditional holder, and EXIT quote requests. They
are not duplicated after capture. Their existing exact-closing allowance
remains `window_end_at + 60s`.
A pre-close request whose response truthfully arrives in that narrow interval
may be bound after the exact snapshot and may qualify; a response after +60s
is support only.

The exact closing snapshot independently retains its existing +60s allowance.
The existing 4h opening ENTRY quote remains unchanged. Market, chain, opening
ENTRY, or unrelated evidence never inherit the 4h closing allowance.

## 11. `CLOSE_CONTEXT` responsibility

For the minimum implementation slice, `CLOSE_CONTEXT` shall perform only:

1. exact evidence-step resolution;
2. exact terminal pre-close unit-manifest/envelope resolution;
3. durable source-row rehydration and provenance validation;
4. class-specific cutoff classification;
5. exact snapshot binding for eligible token-specific evidence;
6. periodic/fallback broad-context resolution and persistence;
7. deterministic safety composition from frozen source observations;
8. late/partial/failed/unknown support classification;
9. an exact context outcome envelope for audit; and
10. Scheduler completion followed by global reselection.

It shall not make the moved main-window source calls. This avoids:

```text
pre-close safety/quote call
+ identical post-close safety/quote call
```

An optional post-close support refresh is not part of the minimum slice. If a
later product requirement authorizes one, it must remain Source-Governed,
separately labeled support, non-retrying, and incapable of historical CLEAN
rescue.

## 12. Failure semantics

### 12.1 Pre-close provider/data outcomes

Provider timeout, rate denial, source failure, partial response, stale result,
target mismatch, or evidence genuinely unavailable is a terminal unit outcome,
not permission to retry and not necessarily a Scheduler integrity failure.
Preserve every created source row and exact unit envelope, yield without
repeating the unit, and allow the exact snapshot phase to proceed
independently.

### 12.2 Evidence failure

If `CLOSE_EVIDENCE` does not produce one valid exact closing snapshot:

- no closed memory window is fabricated;
- no preassigned or nearby snapshot is substituted;
- no token-specific pre-close result is bound as closing evidence;
- dependent binding/audit stops under existing exact-evidence integrity law;
- raw source rows and the pre-close unit manifest remain as unbound diagnostic or
  later-risk truth tied to the failed intended close; and
- those token-specific rows may not be reused by another token/cycle/window.

### 12.3 Context binding/provider outcome after valid capture

A valid snapshot is durable even when context is incomplete. Distinguish:

- `CONTEXT_COMPLETE`: every required binding succeeds;
- `CONTEXT_PARTIAL`: some required source truth is missing/partial/late;
- `CONTEXT_PROVIDER_FAILED`: one-attempt source failure/denial/timeout was
  preserved from pre-close;
- `CONTEXT_BINDING_FAILED`: exact source truth exists but binding/persistence
  failed with a durable typed failure envelope;
- `CONTEXT_UNKNOWN`: required truth cannot be established; and
- `CONTEXT_INTEGRITY_BLOCKED`: owner/target/snapshot/provenance is ambiguous or
  contradictory.

The first five states are valid audit inputs. Only an untrustworthy/missing
failure envelope or a shared database/lease/integrity failure may prevent audit
under existing terminal integrity law.

### 12.4 Isolation

Every failure is token/window-local unless it is an already-defined shared
stop reason such as shared database, lease, integrity, or campaign-budget
failure. A timeout for token A cannot contaminate token B's envelope, consume
token B's binding, or create cross-cycle cancellation.

## 13. Audit-after-context-failure rule

The accepted contract is binding:

```text
timely successful closing capture
+ partial/failed/unknown context
-> durable capture
+ audit receives honest context state
```

`CLOSE_AUDIT` claimability shall therefore require:

1. one exact successful `CLOSE_EVIDENCE` result; and
2. one exact terminal `CLOSE_CONTEXT` result or durable typed context-failure
   envelope with the same owner/target/snapshot identity.

It shall not require `context_quality == COMPLETE`.

Normal provider/data failures should leave the context Scheduler step
operationally `SUCCEEDED` with an incomplete quality outcome: the bounded work
completed and preserved truth. A technical binding failure may leave the step
`FAILED`, but `resolve_close_context` must permit audit only when it can resolve
an exact durable failure envelope and exact successful evidence predecessor.

Audit then creates/resolves the window through existing close owners, records
the exact snapshot, attaches blockers, and applies existing E2Q/Lane Q/E2Z
fail-closed behavior. Missing required evidence cannot promote CLEAN. If exact
context identity itself is ambiguous, audit remains ineligible and the durable
capture is reported as capture-only terminal residue for existing safe-stop
handling.

## 14. Scheduler and fairness treatment

### 14.1 Global category order is unchanged

`PRE_CLOSE_CRITICAL` belongs inside `MEMORY_WINDOW_CLOSE` because it is exact
window-close work, not a generic safety refresh or independent context engine.
It never jumps above:

1. open paper-position monitoring when a future explicit lane lawfully unlocks
   that category;
2. exit-risk token snapshots;
3. `TRACK_FAST` / micro-event token snapshots; or
4. `TRACK_NORMAL` token snapshots.

The active global dispatch remains AGENTS-category-first. Retrieval priority
remains undecided and locked.

### 14.2 Fairness inside close work

After selecting `MEMORY_WINDOW_CLOSE`, use categorical phase order, then the
accepted dispatch fields:

```text
intra_close_phase
-> earliest applicable deadline_at
-> fewer ordinary services first
-> scheduled_for
-> created_at
-> cycle ordinal as tie-break only
-> slot ordinal
-> stable scheduler work / step id
```

No outcome, score, confidence, weighted urgency, profitability, or permanent
cycle preference is permitted. Cycle 1, Cycle 2, and future Cycle 3 propose
eligible work under the same category/phase/deadline/fairness rules.

After every single pre-close unit, evidence capture, context bind, or audit,
the single worker returns to global Scheduler selection. A pre-close executor
may not recursively execute the next unit or next phase.

### 14.3 Missed pre-close slot

If the active pre-close unit reaches `latest_safe_claim_at` before claim, that
unit becomes exact `MISSED_CUTOFF`/not-attempted truth through the Scheduler
owner; it may not start late and pretend to be timely. The resumable step may
yield/terminalize other units without a provider call. Already-due
`CLOSE_EVIDENCE` wins the intra-close collision. A running single source
attempt retains its hard one-attempt timeout; there is no second worker or
unsafe preemption. Any real overrun and resulting capture delay is reported
honestly.

## 15. Budget implications

The intended source-cost delta is zero.

| Family | Existing close-context calls | New disposition |
| --- | --- | --- |
| 15m | current six-request preclose/context reservation | move unchanged to the resumable `WINDOW_CLOSE_PRE_CLOSE_CRITICAL` row and debit it one unit claim at a time; context bind owns zero new provider attempts |
| 1h | current four-request safety reservation | move unchanged to the resumable `CONTINUATION_CLOSE_PRE_CLOSE_CRITICAL` row and debit it one unit claim at a time; context bind owns zero new provider attempts |
| 4h | current long-close context reservation | move the same broad/safety/holder/EXIT attempts to the resumable `LONG_CONTINUATION_CLOSE_PRE_CLOSE_CRITICAL` row; context bind owns zero new provider attempts |

Valid pre-existing market/chain context may avoid the broad request. It does
not create a spare budget that can be spent on retries or new providers.

The later implementation must update measured-transport reservation ownership
atomically with the new step kinds and prove that the exact worst-case current
holder primary/backup operations still fit existing ceilings. It may not raise
run, token, stage, byte, row, or transport ceilings in this slice. If the
current committed ceiling cannot represent the existing worst-case calls after
reassignment, implementation stops `BLOCKED` for a separate budget design.

No automatic retry, endpoint rotation, capacity increase, paid fallback, or
duplicate post-close refresh is authorized.

Finer claims increase claim/yield events, not Scheduler rows or provider
attempts. For identical source outcomes and conditional branches:

```text
old intended governed source attempt count
== new intended governed source attempt count
```

An interrupted unit with any durable exact request row is never called again.
Section 24.8 freezes the crash reconciliation rule.

## 16. Required scenario walkthroughs

### A. 15m normal timely close

1. Scheduler claims the exact token/window pre-close step for one unit at its
   deterministic fire time.
2. Each unit checkpoints and yields; after global reselection, later units may
   run. Safety, required quote and any necessary broad/holder observations
   finish no later than `window_end_at`; source rows and manifest persist real
   times.
3. Evidence independently captures the exact closing snapshot at the lawful
   boundary and attaches it to the run ledger.
4. Context validates both owners, binds frozen observations to the exact
   snapshot, resolves broad context, and emits `CONTEXT_COMPLETE`.
5. Audit runs unchanged quality gates. CLEAN remains possible, never promised.

### B. 15m provider response crosses `window_end_at`

The response retains its real late `received_at`. Context classifies that
evidence late/support-only. It cannot satisfy safety/quote/broad CLEAN input.
The snapshot and audit remain honest; there is no CLEAN rescue or retry.

### C. 15m closing snapshot delayed

The snapshot keeps its actual capture time. Zero allowance remains zero.
Pre-close timing does not widen snapshot or context boundaries. Existing
cadence/evidence owners classify the delayed capture.

### D. Pre-close succeeds but closing snapshot fails

Source rows and the unit manifest remain durable and unbound to a closing
snapshot. No window is fabricated. Context binding and close audit stop for
missing exact evidence. Token-specific observations cannot migrate to another
close.

### E. Snapshot succeeds but context binding fails

The snapshot and ledger attachment remain durable. If exact failure identity is
preserved, context emits `CONTEXT_BINDING_FAILED` and audit runs to record
dirty/do-not-train truth. If binding identity is ambiguous or the failure
envelope itself cannot be trusted, existing integrity law stops audit and
reports capture-only terminal residue.

### F. 1h normal close

The safety/holder units are observed through separate bounded claims before the
fixed logical 1h end. The forced snapshot may occur at the deadline or within
its independent +60s
freshness band. Context binds the frozen safety composite afterward. The 1h
overlay verifies every required contribution against `window_end_at`, not the
later snapshot time. Snapshot +60 is never borrowed by context.

### G. 4h close

Periodic or fallback broad context must be observed no later than
`window_end_at`. Separate single-attempt safety/holder/EXIT units may qualify
only through their existing end +60 cutoff. The exact snapshot independently
uses its existing +60 rule. Later market/chain cannot qualify.

### H. Multiple tokens/cycles close near each other

Pre-close slots are projected from the bounded exact contention cohort and
accepted fairness rotation. Higher AGENTS categories still win. If a closing
snapshot is due while another token's pre-close phase is pending, snapshot
evidence wins inside close work. No cycle receives permanent preference; missed
context is recorded token-locally.

### I. Provider timeout

The one attempt ends with its real failure/timeout time and durable source
failure id. No retry occurs. The exact snapshot remains independently eligible.
Context and audit see missing/failed truth for that token only.

### J. Better post-close evidence

A later safer result, better quote, stronger market regime, or improved chain
context is post-close support/later-lifecycle truth. It cannot replace the
frozen envelope or rescue historical CLEAN eligibility.

## 17. Minimum later implementation map

The smallest likely implementation surfaces are:

| Surface | Minimum change |
| --- | --- |
| `src/printer_v1/operator_cli/close_phases.py` | Add three family-level pre-close step kinds, unit-manifest contract/metadata, exact terminal-manifest resolver, fork-join dependency rules, terminal context failure resolution, and phase-order mapping; add no source-unit kinds |
| `src/printer_v1/operator_cli/one_command_15m_factory.py` | Plan one resumable pre-close row per window; execute exactly one eligible unit per claim; durably checkpoint/yield; reconcile interruption without duplicate calls; make context rehydrate/bind without provider calls; keep evidence snapshot-only and preserve global reselection |
| Scheduler step planning/selection metadata | Use the active unit's acquisition deadline for intra-close selection, count each terminal unit as one ordinary service for fairness, and use existing `yield_job`; do not alter `CLOSE_EVIDENCE` deadline projection |
| `src/printer_v1/sources/measured_transport.py` | Reassign existing close-context reservations to pre-close step kinds, debit the same reservation per terminal unit attempt, and set binding phases to zero provider operations; do not raise ceilings |
| `src/printer_v1/safety/composite.py` | Separate latest underlying observation time from later deterministic evaluation/binding truth using existing row plus JSON reporting semantics |
| `src/printer_v1/operator_cli/first_hour_safety_binding.py` | Enforce exact 1h `window_end_at` against composite and every required contribution; reject borrowing snapshot +60 |
| `src/printer_v1/context_evidence/window_15m.py` | Preserve existing cutoffs; accept only the clarified composite observation semantics; no threshold change |
| nearest Lane-2/15m/1h/4h tests | Replace seeded-only confidence with real producer-order, binding, failure, cutoff and fairness proofs |

An implementation may add a small focused helper module for acquisition
envelope rehydration if keeping it inside the already-large factory would make
identity validation unclear. That would be code organization only, not a new
engine or authority.

Expected shape:

- new Scheduler step kinds: **yes**;
- source-unit step kinds: **no**;
- same pre-close step kind with multiple Scheduler rows: **no**;
- one same-kind resumable row with multiple bounded claims: **yes**;
- reuse existing `CLOSE_EVIDENCE`, `CLOSE_CONTEXT`, `CLOSE_AUDIT`: **yes**;
- new `JobKind` or category: **no**;
- result/ownership metadata changes: **yes**;
- existing Scheduler cooperative yield/reclaim: **yes**;
- persistence behavior changes: **yes, within existing source/evidence/JSON
  surfaces**;
- schema migration: **no**;
- configuration change: **no**;
- runtime/provider execution in the design task: **no**.

If implementation discovers that source rows plus existing result/supporting
JSON cannot retain exact acquisition, evaluation and binding truth, it must
stop `BLOCKED`. This design does not authorize a migration fallback.

## 18. Bounded proof matrix for the later implementation

All proofs are disposable/offline with concrete governed fixture adapters and
temporary databases. No live provider, campaign, authoritative database, or
authorization is permitted.

| Proof | Required setup and assertion |
| --- | --- |
| P1 — real 15m producer order | Run the real pre-close executor, evidence executor and context binder. Prove each source request/response precedes or meets `window_end_at`, snapshot capture occurs separately, and exact binding occurs afterward. Do not manually seed evidence rows. |
| P2 — timestamp retention | Provider fixture emits a known observation time; later binding preserves it while separately recording evaluation/binding time. No copied snapshot/window timestamp. |
| P3 — 15m zero allowance | Real produced result at end passes; end +1s fails. Assert allowance remains `0` and cutoff equals end. |
| P4 — 15m delayed snapshot | Pre-close succeeds; evidence captures late. Existing cadence/evidence classification applies with no cutoff widening. |
| P5 — 1h timing separation | Pre-close safety at/before end plus snapshot at end +60 may bind; safety at end +1 fails even when snapshot itself is freshness-clean. |
| P6 — 1h overlay enforcement | Binder rejects any composite or required contribution after logical end and preserves exact snapshot/window identity. |
| P7 — 4h narrow allowance | Broad row at end passes and end +1 fails; safety/EXIT at end +60 pass and +61 fail; ENTRY and unrelated evidence never inherit +60. |
| P8 — provider timeout/no retry | Real governed fixture times out once. One source failure row exists, no second request exists, snapshot remains independently claimable, context is incomplete. |
| P9 — evidence failure | Pre-close succeeds, snapshot fails. No bound token-specific closing evidence, memory close, or fabricated snapshot/window appears. |
| P10 — binding failure after capture | Exact snapshot remains durable; a typed exact binding-failure envelope makes audit claimable and yields non-CLEAN truth. Ambiguous identity blocks audit. |
| P11 — audit after partial context | Context provider result is partial/failed/unknown; audit executes, records blockers and cannot promote CLEAN. |
| P12 — no duplicate calls | For each family, source request counts equal the existing intended call set after movement; yielding/reclaiming and context binding make zero duplicate provider calls. |
| P13 — multi-token close fairness | Two tokens/cycles with overlapping pre-close slots and closes: no permanent cycle priority, ordinary service remains fair, and due evidence outranks sibling pending pre-close/context/audit. |
| P14 — global category priority | Due TRACK_FAST and TRACK_NORMAL work independently outrank all pre-close/evidence/context/audit close work exactly as accepted. |
| P15 — accepted deadline regression | Existing last-ACTUAL-capture evidence `deadline_at`, forced-close min, and block boundary projections are byte-for-byte unchanged. |
| P16 — identity isolation | Cross-token, pair, cycle, slot, window, run, request-key or snapshot substitution fails closed; no source row is rebound to a foreign close. |
| P17 — preexisting broad reuse | Timely valid shared market/chain rows suppress the fallback broad request; stale/late rows do not, and any fallback retains its real time. |
| P18 — post-close better result | Later clean-looking context remains support only and cannot change the earlier window's eligibility. |
| P19 — 5m lock | No `WINDOW_5M_MICRO_EVENT` pre-close main phase, clean authority or continuation trigger is created. |
| P20 — restart/idempotency | Replaying exact terminal envelope/binding is idempotent; conflicting envelope/source/snapshot identity fails closed without a second call. |

Green resolver tests with manually seeded rows remain useful boundary tests but
are insufficient for P1–P12.

## 19. Explicit non-solutions

This design explicitly forbids:

- timestamp backdating;
- treating request start as response observation;
- 15m allowance widening;
- borrowing the 1h snapshot +60s for safety, holder, market, chain or quotes;
- widening 4h +60 beyond exact snapshot, exact closing safety composite
  (including required holder contributions), and exact closing EXIT;
- broad market/chain observations after `window_end_at` supporting CLEAN;
- putting slow source calls back inside the evidence claim;
- one claimed pre-close job executing two source units or two governed
  provider attempts before Scheduler reselection;
- a hidden in-memory loop advancing across the source-unit manifest;
- a second worker, thread pool, private source loop, or engine-owned scheduler;
- Central Scheduler or Source Governor bypass;
- historical-latency scores, confidence, weights, ranking or probabilistic fire
  times;
- permanent Cycle-1, Cycle-2, token, or source priority;
- automatic retry, endpoint rotation, duplicate post-close call, paid fallback,
  or capacity increase;
- cross-token/cycle/pair/snapshot evidence substitution;
- a schema/config migration hidden inside implementation;
- manually seeded rows as producer proof;
- clean promotion when required context is late, failed, missing, stale,
  partial, mismatched or unsupported;
- making context completeness a prerequisite for preserving a valid snapshot;
  or
- reverting accepted category/fairness or last-ACTUAL-capture deadline work.

## 20. Functionality risks / setbacks / efficiency blockers

- A public provider may still be too slow or unavailable. This yields honest
  late/missing evidence, not a design defect or fabricated CLEAN result.
- A running one-attempt source call cannot be safely preempted by a single
  worker. Claim granularity is therefore exactly one bounded source unit; the
  deterministic lead/hard-timeout contract bounds that hold but does not
  promise provider behavior.
- Pre-close observations taken too early may fail existing freshness gates.
  The implementation proof must demonstrate that deterministic slots are both
  schedulable and fresh; it may not loosen freshness.
- Multiple near-simultaneous tokens enlarge the contention-cohort lead. Higher
  AGENTS work may still cause misses; misses remain honest and token-local.
- Safety composite observation/evaluation semantics must be changed carefully
  without losing the real later evaluation/binding time.
- Current measured long-close reservation and conditional holder worst-case
  accounting must reconcile exactly. A mismatch blocks implementation rather
  than authorizing a ceiling increase.
- The current 1h path still lacks a complete shared per-class context gate.
  This slice repairs only the proven mandatory safety timing defect and does
  not claim a broader 1h architecture repair.

## 21. Locked capabilities

This design does not authorize or unlock:

- the current unaccepted phase-split or timing implementation;
- implementation before independent design acceptance;
- observability/saturation;
- Lane 3, Lane 4, Cycle 3 activation, or new campaign progression;
- live campaign/provider execution, recovery, retry, N2, N7, or cursor work;
- new sources, paid APIs, endpoint rotation, or source capacity;
- schema, migration, or configuration changes;
- `WINDOW_5M_MICRO_EVENT` as main memory or independent close authority;
- 12h/24h production work;
- retrieval activation;
- paper decisions or BUY/SELL/HOLD;
- paper positions, trade events, paper audits, or PnL;
- wallets, private keys, signing, transactions, real funds, or live execution;
- scoring, ranking, confidence percentages, or weighted logic; or
- embeddings or vectors.

Printer remains Solana-only, Solana-memecoin-only, paper-trading-only,
Source-Governed, Central-Scheduler-led, clean-memory-gated, and fail-closed.

## 22. Exact next permitted implementation slice

After independent acceptance of this design, the exact next permitted work is:

```text
V2-9.8B Timely Closing-Context Production —
Bounded Resumable Pre-Close Acquisition and Post-Capture Binding Implementation
```

That slice may modify only the minimum surfaces in Sections 17/24.13 and their
nearest focused tests. It must implement the one-unit-per-claim resumable
contract, fork/join phase contract, move rather than duplicate existing calls,
preserve all timing/category/deadline locks, and run the bounded offline proof
matrix appropriate to the changed surfaces.

It may not start observability/saturation or Lane 3. It may not run a live
campaign or provider. If design acceptance is withheld, the next action is
operator review or a corrected documentation-only design—not implementation.

## 23. Design closeout

**Status:** `AMENDED_PASS_READY_FOR_INDEPENDENT_ACCEPTANCE`.

The chosen architecture makes timely main-window context production possible
without promising provider success, fabricating a snapshot, backdating
evidence, widening a threshold, duplicating calls, bypassing central owners, or
reintroducing the monolithic close claim. No implementation is performed or
accepted by this document.

## 24. Controlling amendment — pre-close claim granularity and safe scheduling

This section amends Sections 1, 3, 4, 6, 7, 8–10, 14–18 and 20 only where they
previously treated `PRE_CLOSE_CRITICAL` as one multi-source claim. All evidence
identity, observation-time, cutoff, binding, audit and capability contracts
outside that claim boundary remain unchanged. If earlier wording can be read
as permitting a source bundle inside one claim, this section controls.

### 24.1 Blocker and amendment verdict

The remaining blocker is proven: a single worker cannot reconsider newly due
`TRACK_FAST` or `TRACK_NORMAL` work while a claimed pre-close executor serially
advances across market/chain, safety, holder and quotes. Moving that bundle
before close would relocate, not remove, Lane-2 contention.

**Amendment verdict:** use one persisted, resumable family-level
`PRE_CLOSE_CRITICAL` run-step/Scheduler-job row per exact window. Freeze its
source-unit manifest in `result_json`. Each Scheduler claim may execute exactly
one selected logical unit and at most one governed provider attempt. It must
durably checkpoint the unit and cooperatively yield the existing job before
another unit can run.

This yields the required execution shape:

```text
Central Scheduler claim PRE_CLOSE_CRITICAL for one exact window
-> execute/checkpoint exactly one bounded source unit
-> yield job and run step
-> global Scheduler reselection
-> possibly claim one later unit
-> ...
-> terminal exact unit manifest

terminal manifest --------------------------\
                                             -> CLOSE_CONTEXT_BIND -> CLOSE_AUDIT
exact successful CLOSE_EVIDENCE snapshot ---/
```

A running provider attempt remains bounded by its existing hard timeout and
cannot be safely preempted inside the call. The mandatory preemption boundary
is before every subsequent logical unit.

### 24.2 Options compared

| Option | Repository fit | Decision |
| --- | --- | --- |
| A. Multiple Scheduler rows using one family-level step kind plus source-unit metadata | `(run_id, step_key)` permits multiple same-kind rows and each could be terminal independently. However this multiplies Scheduler-job/campaign-work rows and the measured `SCHEDULER_WORK_ITEM` unit, requiring new row-ceiling accounting solely to obtain a yield boundary. | Rejected as larger than necessary. |
| B. Small fixed categorical pre-close subphases | Makes source roles look like permanent Scheduler categories, creates extra step kinds/dependency edges, and risks encoding provider order as phase priority. | Rejected. |
| C. One persisted resumable row using the existing Scheduler cooperative-yield boundary plus frozen `result_json` unit state | Existing run-step status/result fields, Scheduler `PENDING`/`RUNNING` and `yield_job`, immutable campaign ownership, and durable source rows can represent each checkpoint without another table or row family. | **Chosen: minimum sufficient.** |

The chosen row keeps the new family-level step kinds already specified:

- `WINDOW_CLOSE_PRE_CLOSE_CRITICAL`;
- `CONTINUATION_CLOSE_PRE_CLOSE_CRITICAL`; and
- `LONG_CONTINUATION_CLOSE_PRE_CLOSE_CRITICAL`.

There is no provider JobKind, no source-unit step kind, and no additional
Scheduler row per source.

### 24.3 Frozen source-unit manifest

The pre-close row's planned `result_json` shall contain an immutable identity
header and a frozen `source_unit_manifest`. Each unit entry contains:

- exact `source_unit_identity` and logical evidence role;
- exact campaign/factory run/cycle/token slot/window/step/work identity;
- token id, immutable mint, pair id and pair address;
- window family and intended evidence/context/audit step keys;
- allowed source name and request kind, or the exact zero-source periodic
  resolution role;
- deterministic request-key prefix and fixed attempt ordinal `1`;
- real dependency unit identities, if any;
- lawful `acquisition_cutoff_at`;
- deterministic `bounded_claim_seconds` and `latest_safe_claim_at`;
- unit state and terminal reason;
- source request/response/failure ids and actual timestamps when present; and
- returned-target/provenance/quality disposition needed by later binding.

The manifest's membership, identities, dependencies, cutoffs and attempt
ordinal are frozen before the step becomes claimable. Only unit state/result
fields may change, and only through the declared state machine:

```text
WAITING_DEPENDENCY or PENDING
-> RUNNING
-> TIMELY | PARTIAL | FAILED | LATE | MISSED_CUTOFF
   | NOT_REQUIRED | DENIED | UNKNOWN_INTERRUPTED_AFTER_REQUEST
```

Terminal states never return to `PENDING`. A contradictory transition or a
source identity outside the manifest is `CONTEXT_INTEGRITY_BLOCKED`, not a new
attempt.

The run-step and campaign-work scalar `source_request_id`/
`source_response_id`/`source_failure_id` fields cannot represent multiple
units and must not be overwritten as a rolling cursor. They may remain null for
the resumable aggregate row. The exact per-unit references live in the
manifest and point to the existing authoritative source tables. Request keys
include exact Scheduler work and unit identity. If later implementation proves
that existing provenance consumers require every unit in those scalar columns,
it must stop `BLOCKED`; this amendment does not authorize a migration.

When every unit is terminal, the Scheduler step may be operationally
`SUCCEEDED` because its bounded work completed even when one or more unit
quality outcomes are failed/late/unknown. That status never means context is
complete. A safely unschedulable whole plan is instead exact `SKIPPED` with its
typed envelope. `CLOSE_CONTEXT_BIND` accepts either trustworthy terminal form;
it does not require every unit quality outcome to be successful.

### 24.4 Maximum work in one claim

One pre-close Scheduler claim may perform only:

1. exact ownership/manifest validation;
2. validation of the one eligible nonterminal unit identity selected and bound
   by the Central Scheduler claim;
3. that unit's bounded local precondition or periodic-context lookup;
4. at most one Source-Governed provider attempt for that unit;
5. persistence/reconciliation of that unit's request/response/failure truth;
6. deterministic eligibility/`NOT_REQUIRED` updates to declared dependent
   units without calling their sources;
7. one atomic manifest checkpoint; and
8. either terminal completion of the whole manifest or cooperative Scheduler
   yield.

It may not execute a second logical unit, make a second governed provider
attempt, compose/bind safety, call context binding, or recursively claim the
next phase. Even a zero-call periodic reuse unit must checkpoint and yield; it
cannot spend its unused call opportunity on another unit.

The maximum worker hold for one claim is therefore:

```text
one deterministic Source-pacer wait
+ one existing adapter hard timeout
+ bounded local validation/request/result/checkpoint/yield work
```

No loop over `source_unit_manifest` is permitted inside a claim.

### 24.5 Logical units and real dependencies

The manifest uses evidence-role units, not provider priority classes:

| Logical unit | Maximum provider work in its claim | Acquisition dependency |
| --- | --- | --- |
| `MARKET_CHAIN` where currently required | Resolve exact timely periodic context; if absent, at most the existing one governed broad request | None |
| `SAFETY_PRIMARY` | One existing GoPlus attempt | None |
| `SAFETY_CORE` where currently active | One existing core Solana RPC attempt | None |
| `ENTRY_QUOTE` where currently required | One existing governed Jupiter ENTRY attempt | None |
| `EXIT_QUOTE` where currently required | One existing governed Jupiter EXIT attempt | None |
| `HOLDER_PRIMARY` when required | One existing governed primary holder attempt | `SAFETY_PRIMARY` must terminally show holder concentration unknown |
| `HOLDER_BACKUP` when authorized | One existing governed fixed backup attempt | `HOLDER_PRIMARY` must terminally show an existing backup-eligible transient failure |

No fixed acquisition order exists among independent market, safety, core,
ENTRY and EXIT units. Safety composite composition occurs after capture and
does not make those acquisitions depend on one another.

Before global comparison, the Central Scheduler's read-only pre-close
projection derives the row's one next unit categorically by:

```text
dependency-ready
-> earliest latest_safe_claim_at
-> owner-scoped deterministic rotation among equal-deadline independent roles
-> stable source_unit_identity tie
```

That projected unit supplies the row's active acquisition deadline to the
global selection key. The resulting claim binds the exact
`source_unit_identity`; the executor may validate and execute that unit only,
not choose another after claim. This remains Central-Scheduler-owned selection,
not an engine-local scheduler.

The rotation is derived only from exact campaign/run/cycle/slot/window identity
and the frozen logical-role set. It is not provider performance, latency,
quality, score, confidence or weight. Consequently no provider is permanently
first across tokens/windows. Bind/composition order remains a separate later
contract.

### 24.6 Safe schedulability and earliest identity boundary

No pre-close row or unit may be owned before its exact ownership graph exists.
Define:

```text
ownership_graph_committed_at
  = the first commit after which exactly one persisted factory run,
    campaign, campaign run, cycle, token slot, token/pair, window family/window,
    and intended pre-close/evidence/context/audit work identity can be resolved

earliest_preclose_schedulable_at
  = the planner's truthful now observed after ownership_graph_committed_at
    and after the frozen pre-close unit manifest is valid
```

Creating the close plan and manifest may be one transaction, but no Scheduler
claim is visible until it commits. The persisted
`earliest_preclose_schedulable_at` is never earlier than that post-commit
planner observation.

The desired lead remains Section 6.4's deterministic conservative result:

```text
desired_preclose_scheduled_for
  = earliest acquisition cutoff in the exact contention cohort
    - sum(all potentially required bounded unit holds)
    - one reselection reserve per unit
```

The hard boundary is:

```text
if desired_preclose_scheduled_for < earliest_preclose_schedulable_at:
    effective scheduled_for = earliest_preclose_schedulable_at
    make no pre-close provider call
    terminalize the pre-close step/job/work as SKIPPED
    result reason = TIMELY_ACQUISITION_NOT_PRODUCIBLE
    preserve desired and earliest times in result_json
```

`SKIPPED` is existing row vocabulary;
`TIMELY_ACQUISITION_NOT_PRODUCIBLE` is a typed result/error reason, not a new
schema enum. `CLOSE_EVIDENCE` remains independently eligible. Later context
and audit receive the exact missing-context reason and cannot promote CLEAN.
No ownership is fabricated, no `scheduled_for` is backdated, and no evidence
cutoff changes.

### 24.7 Acquisition deadline versus evidence deadline

Each unit has both a fire opportunity and an acquisition boundary:

```text
desired_preclose_scheduled_for
  = conservative earliest time the resumable job should first become due

acquisition_cutoff_at(u)
  = existing lawful latest observation time for unit u's evidence class

latest_safe_claim_at(u)
  = acquisition_cutoff_at(u) - bounded_claim_seconds(u)
```

The projected active unit's `latest_safe_claim_at` is the pre-close deadline
used for deadline ordering inside `MEMORY_WINDOW_CLOSE`. It may be stored in
existing step `result_json` and projected by the Central Scheduler selector;
no new column is required.
The campaign work row retains exact plan ownership, while the active-unit
deadline—not an expired earlier unit deadline—governs each later claim.

These remain distinct:

```text
pre-close acquisition_cutoff_at
!= pre-close latest_safe_claim_at
!= accepted CLOSE_EVIDENCE dispatch deadline_at
!= window_end_at identity boundary
!= actual Scheduler claimed_at
```

The accepted last-ACTUAL-capture `CLOSE_EVIDENCE` deadline formula is unchanged
and is never used to derive a pre-close source deadline. A unit not claimed by
its `latest_safe_claim_at` is terminal `MISSED_CUTOFF` without a provider call.
A timely claim cannot make a response timely: the real response/observation
must still satisfy `acquisition_cutoff_at`.

The family cutoffs remain exactly:

- 15m: every required closing context observation `<= window_end_at`; allowance
  remains zero;
- 1h: safety/holder `<= window_end_at`; snapshot-only +60 is not borrowed; and
- 4h: market/chain `<= window_end_at`; only exact closing snapshot, closing
  safety composite including its required contributions, and exact EXIT may
  use the existing +60 allowance.

### 24.8 Checkpoint, yield, interruption and no-duplicate rule

After the selected unit finishes or becomes terminal without a call, the owner
must commit its exact unit envelope before releasing the claim. If units remain:

1. set the run step back to `PENDING` with the checkpointed manifest;
2. cooperatively release the same Scheduler job through the existing yield
   owner with the next truthful due time;
3. synchronize campaign work back to its existing nonterminal state; and
4. return to the outer single-worker Scheduler loop.

The next source unit can run only after a new global Scheduler selection and
claim. Each terminal unit claim counts as one ordinary service for token/cycle
fairness even though the same Scheduler row is reused. The selector reads the
manifest's durable terminal-unit count; yielding must not erase that service
history.

Interruption reconciliation uses the governed persistence order: the source
request row is committed before adapter I/O, and response/failure is committed
after it. For the active unit's exact deterministic request key and attempt
ordinal:

| Durable state after interruption | Lawful reconciliation |
| --- | --- |
| Unit already terminal in manifest | Never call; release/reterminalize the stale claim from existing truth. |
| Exactly one request and exactly one linked response or failure | Rehydrate and checkpoint that result; never call again. |
| Exactly one request and no linked response/failure | Terminalize `UNKNOWN_INTERRUPTED_AFTER_REQUEST`; never retry because provider outcome is unknowable. |
| No request row | The governed adapter cannot have been called because request persistence precedes I/O; after exact stale-lock/owner reconciliation, the same unit may make its one first attempt. |
| Duplicate requests, multiple terminal rows, foreign request key or owner mismatch | `CONTEXT_INTEGRITY_BLOCKED`; no call and no automatic repair. |

This is crash reconciliation for the same already-authorized active run, not a
campaign retry surface. If exact stale-lock ownership cannot be proven, safe
stop remains required. A completed, failed, late, denied, unknown or not-
required unit is never repeated.

### 24.9 Scheduler reselection and fork/join

The global selector remains:

```text
eligible due work
-> AGENTS category
-> phase / active-unit deadline inside category
-> token/cycle ordinary-service fairness
-> deterministic tie
-> Central Scheduler claim
```

Globally:

```text
TRACK_FAST > TRACK_NORMAL > MEMORY_WINDOW_CLOSE
```

Inside `MEMORY_WINDOW_CLOSE`, simultaneously due work remains:

```text
CLOSE_EVIDENCE
-> PRE_CLOSE_CRITICAL active unit
-> CLOSE_CONTEXT_BIND
-> CLOSE_AUDIT
```

After one pre-close unit yields, all categories are reconsidered. A
`TRACK_FAST` or `TRACK_NORMAL` snapshot that became due during the one bounded
attempt therefore wins before another pre-close unit. `CLOSE_CONTEXT_BIND`
joins the exact terminal unit manifest, exact successful snapshot, timely
periodic context, and typed late/failure/unknown envelopes. It makes no new
main-window provider call. The existing audit-after-context-failure decision
remains unchanged.

### 24.10 Multi-token and multi-cycle fairness

- **Two FAST tokens near close:** both expose the same global category. After
  token A receives one pre-close unit service and yields, token B has fewer
  ordinary unit services and wins the next otherwise-equal opportunity. Exact
  deadlines may lawfully order them; token identity is only a deterministic
  tie.
- **FAST plus NORMAL:** due `TRACK_FAST` and then due `TRACK_NORMAL` cadence
  work outrank both tokens' pre-close work. Within close work, lane does not
  create an extra priority; deadline and ordinary-service fairness apply.
- **Cycle 1 plus Cycle 2:** cycle is readiness/tie identity only. Terminal unit
  counts and accepted fairness apply across both; neither cycle is permanently
  first.
- **Future Cycle 3:** if a later lane authorizes it, it enters the same category,
  active-unit deadline and ordinary-service rules. This amendment does not
  activate it or reserve a superior position.
- **Track work becomes due during a unit:** the current one-attempt claim runs
  only to its hard bound, checkpoints and yields. Before another unit, global
  selection occurs and due track work wins.
- **Independent providers:** equal-deadline roles use owner-scoped deterministic
  rotation; no `provider A > provider B` policy exists. Only the two real
  holder dependencies constrain acquisition order.

There is no permanent `Cycle1 > Cycle2`, `Cycle2 > Cycle1`, `token1 > token2`,
or provider ordering.

### 24.11 Required amendment scenarios

**A. Safety unit running when TRACK_FAST becomes due.** The one governed safety
attempt reaches its existing hard bound, its exact result is checkpointed, and
the job yields. The outer Scheduler sees TRACK_FAST before any core/holder/quote
unit and selects it globally.

**B. Two units succeed; third times out.** Each success is already terminal in
the manifest. The third unit persists its real request/failure and becomes
`FAILED`; none of the three can return to pending. Later units may continue one
claim at a time. Context binding sees all exact terminal states.

**C. Process interruption between units.** The preceding unit checkpoint is
durable. Stale-claim reconciliation follows Section 24.8. A terminal unit or
any exact request already made is never called again. Only a unit with no
request row may make its first attempt after exact owner recovery.

**D. Desired start predates identity.** The planner persists truthful desired
and earliest times, schedules nothing in the past, makes no source call, and
terminalizes `SKIPPED / TIMELY_ACQUISITION_NOT_PRODUCIBLE`. Evidence may still
capture; later quality fails closed.

**E. Two tokens have simultaneously due units.** The Central Scheduler first
applies category/active-unit deadline, then fewer terminal unit services,
accepted token/cycle fairness, owner-scoped deterministic tie and stable work
identity. One token yields after one unit, so no permanent preference emerges.

**F. PRE_CLOSE and TRACK_NORMAL are due.** `TRACK_NORMAL` wins because AGENTS
category selection occurs before close phase/deadline/fairness.

**G. 15m response arrives after end.** Its real response time remains late even
if dispatch was timely. The unit terminal state is `LATE`/support-only; zero
allowance and audit blockers remain.

**H. 4h safety/EXIT complete inside +60.** Their exact real observations may
qualify under the existing narrow allowance. A market/chain response after end
remains late and cannot inherit +60.

### 24.12 Request-budget preservation

Unit splitting changes claim count only. Every provider-capable unit maps
one-for-one to an attempt already authorized by the existing close path and
retains the same conditional rules:

```text
new attempts for exact close/outcome branch
  = count(manifest units that actually make their fixed ordinal-1 request)

old intended attempts for the same close/outcome branch
  = count(the same existing governed calls in the former collector)

new attempts == old intended attempts
```

Periodic reuse, `NOT_REQUIRED`, missed, denied, unknown and unschedulable units
make no provider call. Holder backup remains one maximum and only after the
existing eligible primary failure. Reclaiming/yielding never refreshes or
retries a terminal unit. `CLOSE_CONTEXT_BIND` makes zero main-window provider
calls. No reservation, transport, response-byte, row or source ceiling is
raised.

### 24.13 Amended minimum implementation map

The exact later surfaces remain narrow:

| Surface | Amendment-specific minimum |
| --- | --- |
| `src/printer_v1/operator_cli/close_phases.py` | Represent one family-level resumable pre-close phase, validate the frozen unit manifest and terminal set, retain fork/join and audit failure semantics; no source-unit step kinds. |
| `src/printer_v1/operator_cli/one_command_15m_factory.py` | Project safe identity-bound manifests; execute/checkpoint exactly one unit; yield/reclaim the same row; reconcile stale/interrupted requests without duplicates; expose terminal unit service counts to selection. |
| Scheduler planning/selection metadata and existing `yield_job` integration | Use active-unit acquisition deadline, global category ordering and durable per-unit service count; never recurse to the next unit. |
| `src/printer_v1/sources/measured_transport.py` or nearest existing accounting boundary | Move/debit the unchanged reservation one attempt at a time and prove call-count equality; no ceiling increase. |
| `src/printer_v1/safety/composite.py` | Preserve the already-designed post-capture deterministic composition and truthful observation/evaluation separation. |
| `src/printer_v1/operator_cli/first_hour_safety_binding.py` | Preserve exact 1h end enforcement; no snapshot-allowance borrowing. |
| Focused Lane-2/15m/1h/4h tests | Exercise the real resumable executor, Scheduler yield/reselection, crash reconciliation, identity boundary, budgets, cutoffs, binding and audit. |

Implementation shape is frozen as:

- new family-level pre-close step kinds: **yes, the existing design's three**;
- new source-unit step kinds: **no**;
- same step kind with multiple Scheduler rows: **no**;
- one same-kind row with multiple bounded claims: **yes**;
- unit distinction: **existing `result_json`/metadata only**;
- existing Scheduler cooperative yield: **yes**;
- new table/column/index/trigger/migration: **no**.

If exact unit state, stale-claim reconciliation or no-duplicate proof cannot be
represented with the existing step/job/work/source rows and `result_json`, the
implementation must stop `BLOCKED`. This amendment authorizes no migration.

### 24.14 Additional bounded proof requirements

The future implementation proof must add these real-executor tests to Section
18; manually seeded resolver rows are insufficient:

1. one claimed pre-close job executes exactly one logical unit and no more than
   one governed request;
2. the job checkpoints/yields and the Scheduler reselects before a second unit;
3. TRACK_FAST and TRACK_NORMAL becoming due between units win globally;
4. a terminal successful unit cannot execute again on later claims;
5. provider timeout/failure is durable, typed and not retried;
6. old intended request count equals new actual request count for identical
   success, conditional-holder and failure branches;
7. two-token unit service alternation obeys accepted deadline/fairness rules;
8. Cycle 1/Cycle 2 overlap has no permanent cycle preference, with a dormant
   Cycle 3 fixture proving identical future treatment without activation;
9. desired start before earliest exact identity produces
   `SKIPPED / TIMELY_ACQUISITION_NOT_PRODUCIBLE` and zero requests;
10. interruption after terminal checkpoint, after request+response, after
    request-only, and before request follows every Section 24.8 branch with no
    duplicate provider call or timestamp rewrite;
11. real 15m end and end +1 observations preserve zero allowance;
12. 1h safety/holder end +1 fails while the independent forced snapshot +60
    contract remains unchanged;
13. 4h market/chain end +1 fails while exact safety/EXIT +60 and +61 retain
    their existing pass/fail boundary;
14. terminal unit manifest joins only the exact post-capture snapshot and
    preserves real observation versus binding time;
15. successful capture remains durable when units or binding are partial,
    failed, late, unknown or unschedulable;
16. audit receives the exact typed context envelope and cannot promote CLEAN;
    ambiguous/shared integrity still blocks; and
17. accepted last-ACTUAL-capture `CLOSE_EVIDENCE` deadline projection and
    TRACK/global category tests remain byte-for-byte behaviorally unchanged.

### 24.15 Amendment closeout and locks

The pre-close monopoly blocker and the early-identity schedulability blocker
are resolved at design level. Timely acquisition is made possible, never
guaranteed. A public provider may still respond late or fail; Printer records
that truth and does not retry, backdate, widen or substitute.

All Section 19 non-solutions and Section 21 locks remain in force. In
particular, this amendment does not accept the current implementation, start
observability/saturation, start Lane 3, activate Cycle 3, add a worker, create
provider priority, change evidence cutoffs, modify `CLOSE_EVIDENCE` deadline
math, or authorize implementation before independent design acceptance.

**Amended status:**
`V2_9_8B_TIMELY_CLOSING_CONTEXT_PRODUCTION_DESIGN_AMENDED_PASS_READY_FOR_INDEPENDENT_ACCEPTANCE`.

## 25. Controlling amendment — closing-context failure semantics

This section supersedes Sections 1, 4.2, 11–13, 16.E, 18.P10–P11,
24.3, 24.9, 24.12, 24.14–24.15, and any other wording in this document only
where it requires a failed `CLOSE_CONTEXT_BIND` step to preserve
`CLOSE_AUDIT` through `CONTEXT_BINDING_FAILED`. It does not change the
pre-close producer, claim granularity, Scheduler ordering, timing, evidence
cutoffs, or post-capture binding architecture.

### 25.1 Amendment verdict

Static inspection at `24e7ceed8c7b3fca261a45a00c81cc50a0b2844e`
proves that current V1 has no concrete production operation whose exception
means a trustworthy bounded local binding/composition failure while excluding
identity, provenance, invariant, persistence, SQLite, and unclassified
technical failures.

Current V1 shall therefore use this two-outcome contract:

1. a structurally successful `CLOSE_CONTEXT_BIND` may carry complete,
   partial, failed-provider, late, rejected, unavailable, or unknown evidence
   truth; the context step completes operationally, `CLOSE_AUDIT` remains
   claimable, and E2Q decides non-CLEAN quality from that truth; and
2. an exception during `CLOSE_CONTEXT_BIND` is a technical/integrity failure;
   context-local writes roll back, the context step fails closed, and its
   dependent audit is not preserved.

`CONTEXT_BINDING_FAILED` and `ContextBindingCompositionFailure` are removed
from the active required runtime contract. Their names may remain only as
historical design vocabulary. They are unsupported and unreachable until a
future separately approved audit and design identify a real qualifying
production operation and define its exact trust boundary. A fixture or
monkeypatch cannot establish that boundary.

The exact phase architecture remains:

```text
PRE_CLOSE_CRITICAL bounded unit
-> Central Scheduler reselection
-> CLOSE_EVIDENCE
-> Central Scheduler reselection
-> CLOSE_CONTEXT_BIND
-> Central Scheduler reselection
-> CLOSE_AUDIT
```

This verdict corrects a design-to-production semantic mismatch. It does not
claim that the current unaccepted implementation is repaired.

### 25.2 Exact source-inspection evidence

The inspected production call tree is:

```text
_execute_close_context_phase
  -> resolve_close_evidence
  -> resolve_preclose_manifest
  -> _preclose_result_base
  -> _rehydrate_preclose_context_bundle
  -> SAVEPOINT close_context_binding
  -> _persist_preclose_context
       -> market/chain governed-response validation and recorders
       -> GoPlus evidence normalization/guarded insert
       -> safety composite construction/persistence
       -> Jupiter ENTRY/EXIT normalization/guarded insert
       -> holder contribution composition where present
  -> RELEASE or ROLLBACK savepoint
  -> context result/envelope
```

Before `_persist_preclose_context` runs, the exact evidence predecessor,
closing snapshot, pre-close manifest, request identities, source names,
request kinds, response/failure linkage, and returned result shape have been
validated. Failures in those checks are explicit identity/provenance/integrity
failures. The persistence subtree then has these real semantics:

| Evidence class | Truthful degradation path | Exceptions found by source inspection | Conclusion |
| --- | --- | --- | --- |
| Broad market regime | A missing provider response remains a failed/late/unknown pre-close unit and no broad row is fabricated. A real response is normalized and may persist `MARKET_CONTEXT_PARTIAL`, `MARKET_CONTEXT_STALE`, `MARKET_CONTEXT_CONFLICTING`, `MARKET_CONTEXT_UNKNOWN`, or `MARKET_CONTEXT_DO_NOT_USE_FOR_MEMORY`; unsafe qualities force regime `UNKNOWN`. | Missing response id, disallowed source, or disallowed request kind raises `ValueError`; enum/normalization/SQL failures remain technical. | All lawful evidence degradation is a normal result. Exceptions do not prove a trustworthy local composition failure. |
| Solana chain heat | The same governed broad response may persist partial/stale/conflicting/unknown/do-not-use quality; unsafe quality forces chain/activity/liquidity/congestion to explicit unknown labels. No response means no fabricated row and a degraded unit envelope. | Missing/foreign response provenance, invalid enums/normalization, or SQL failure. | Normal return already preserves degraded evidence for audit. |
| GoPlus safety | Provider failure without a response remains an exact source failure execution. A returned mint mismatch becomes `REJECTED_TARGET_MINT_MISMATCH`. Insert-guard rejection returns `inserted=False`, `REJECTED_GUARD_FAILED`, rejection reasons, and no downstream unlocks. Non-clean evidence can be inserted audit-only. | Missing response, wrong source, wrong request kind, or non-object normalized payload raises `ValueError`; SQL failure remains technical. | Source failure and explicit evidence rejection do not require a technical-exception envelope. |
| Safety composite | A source failure is retained as a contribution with request/failure ids, real `failed_at`, source status, quality, and rejection reason. Missing/unsafe fields become blockers or optional unknowns. The composite returns `SAFETY_BLOCKED`, `PARTIAL`, `ACCEPTABLE_PARTIAL_DATA`, conflicts, blockers, and optional unknowns as data. | Invalid evaluation time, exceeded fixed contribution invariant, absence of any truthful observation time, provenance/invariant fault, or SQLite write failure. | Lawful safety/holder degradation is data. The remaining exceptions are invariant or persistence failures. |
| Jupiter ENTRY/EXIT quote | A failed normalized source result retains its failure id and becomes `QUOTE_FAILED`/unknown or unrealistic quote truth. Returned target mismatch and insert-guard failure return explicit non-inserted rejection results; audit later sees missing/blocked quote evidence. | Wrong governed source/request identity raises `ValueError`; malformed/invariant or SQLite failure remains technical. | Provider and quote-quality failure has a normal fail-closed evidence representation. |
| Holder contribution | Primary/backup source failure is an exact terminal pre-close unit and a composite contribution with real failure time and rejection reason. Missing, stale, or conflicting holder truth becomes `HOLDER_CONDITION_UNAVAILABLE`, `HOLDER_CONDITION_STALE`, or `HOLDER_CONDITION_CONFLICTING`/unknown according to existing optionality policy. | Foreign request/response/failure linkage, target/provenance invariant failure, fixed contribution invariant, or SQL failure. | Holder scarcity/failure is normal evidence truth; owner/provenance corruption is technical. |

Returned provider target mismatch is an evidence rejection, not permission to
substitute another target. A mismatch between the persisted close owner and a
request/response/failure row is instead an integrity exception. This
distinction keeps explicit provider evidence rejection auditable without
weakening exact-owner protection.

No production statement raises `ContextBindingCompositionFailure`. At this
baseline its only raise is in
`test_real_context_binding_failure_producer_preserves_snapshot_and_audit`,
where the test replaces `_persist_preclose_context` itself. The positive test
therefore proves consumption of a manually injected semantic marker, not
production classification. The same-boundary generic `ValueError` test proves
the opposite real safety rule: an unclassified persistence/integrity failure
must use ordinary fail-closed cancellation.

### 25.3 Proof that normal degradation reaches audit and memory quality

The current structural path already has the required join:

1. pre-close source units persist exact terminal states such as `FAILED`,
   `DENIED`, `LATE`, `MISSED_CUTOFF`,
   `UNKNOWN_INTERRUPTED_AFTER_REQUEST`, and
   `TIMELY_ACQUISITION_NOT_PRODUCIBLE`, without retry or fabricated evidence;
2. `_rehydrate_preclose_context_bundle` reconstructs exact request,
   response, and failure truth without a provider call;
3. `_persist_preclose_context` either persists audit-only/degraded evidence,
   records an explicit non-inserted rejection result, or lawfully leaves an
   absent row absent;
4. `_execute_close_context_phase` returns `ok=True` with
   `CONTEXT_COMPLETE`, `CONTEXT_PARTIAL`, `CONTEXT_PROVIDER_FAILED`, or
   `CONTEXT_UNKNOWN` when the join itself is structurally trustworthy;
5. a `SUCCEEDED` context step makes the exact audit dependency ready;
6. `_execute_close_audit_phase` passes the same persistence report and context
   envelope to the 15m, 1h, or 4h close/audit owner without another source
   call; and
7. the shared memory-quality path turns unknown context, context freshness
   blockers, missing/blocked safety, and missing/blocked ENTRY/EXIT quote rows
   into `MISSING_OR_UNKNOWN_CONTEXT` and exact evidence blockers. It assigns
   non-CLEAN/audit-only or dirty quality, `do_not_train=1`, and
   `retrieval_ready=False` where required.

Operational `SUCCEEDED` for `CLOSE_CONTEXT_BIND` means that exact resolution,
classification, attachment, and reporting completed. It does not mean every
provider succeeded or that context is CLEAN. The exact unit states,
persistence/rejection results, context labels, and E2Q blockers carry evidence
quality.

The current focused partial-context test confirms the consumer join for
`CONTEXT_PROVIDER_FAILED`, although its monkeypatched producer remains
insufficient as real-producer proof. The production functions above establish
that each named evidence owner has a normal-return degraded representation;
the next implementation proof must exercise those real owners rather than
seed a technical failure envelope.

### 25.4 Final failure taxonomy

| Final category | Included outcomes | Context step/job | Audit | Closing snapshot |
| --- | --- | --- | --- | --- |
| `EVIDENCE_DEGRADED` | Provider timeout/failure/denial, truthful late result, missed/unschedulable attempt, source scarcity, missing optional holder evidence, unsupported field, stale/partial/unknown payload, route unavailable, explicit target-data rejection | `SUCCEEDED` when exact binding/classification completed; quality state is partial/provider-failed/unknown as applicable | Remains claimable; E2Q consumes exact truth and fails CLEAN where required | Remains durable |
| `BIND_STRUCTURALLY_SUCCESSFUL` | Exact owner, exact snapshot, exact manifest, valid provenance, all local writes/reads complete, including explicit non-clean or non-inserted evidence dispositions | `SUCCEEDED` | Remains claimable | Remains durable |
| `TECHNICAL_OR_INTEGRITY_FAILURE` | Owner/snapshot mismatch, cross-token/cycle/window identity, duplicate/foreign provenance, corrupt/unverifiable state, invariant violation, malformed persistence, SQLite/database error, or any unclassified exception | `FAILED` through the ordinary fail-closed terminalizer after context savepoint rollback | Not preserved; normal token-local dependent cancellation remains lawful | Already committed exact capture remains durable |

There is no current fourth category for an audit-preserving technical binding
exception. Source/provider scarcity is not a code defect. Conversely, a
technical exception cannot be relabeled as evidence degradation merely to
keep audit running.

### 25.5 Amended `CLOSE_CONTEXT_BIND -> CLOSE_AUDIT` contract

The only lawful audit-preserving join is:

```text
exact successful CLOSE_EVIDENCE
+ exact terminal PRE_CLOSE manifest
+ structurally successful CLOSE_CONTEXT_BIND
  carrying complete or truthful degraded evidence state
-> exact CLOSE_AUDIT remains claimable
-> E2Q records CLEAN only if every existing gate independently passes
```

The technical failure branch is:

```text
exact successful CLOSE_EVIDENCE
+ technical/integrity exception during CLOSE_CONTEXT_BIND
-> rollback only close-context savepoint writes
-> preserve already committed closing snapshot
-> context step/job FAILED
-> ordinary exact-token dependent cancellation
-> CLOSE_AUDIT not claimable
```

This is not evidence erasure. The durable closing capture, pre-close source
requests/responses/failures, and already committed manifest remain truthful.
Audit is blocked because the system cannot establish a trustworthy completed
context join, not because the capture disappeared.

`resolve_close_context` must therefore accept only the exact operationally
`SUCCEEDED` context predecessor for the active V1 path. Degraded evidence
belongs inside that successful result. A `FAILED` context step, including one
with a manually created `CONTEXT_BINDING_FAILED` payload, must not make audit
dependency-ready.

### 25.6 Exact consequences for the next implementation commit

The next implementation is removal and simplification, not a new producer:

| Surface | Required consequence |
| --- | --- |
| `ContextBindingCompositionFailure` | Remove the declaration. Do not translate any lower-level exception into it. |
| `_execute_close_context_phase` | Remove the special typed catch and `CONTEXT_BINDING_FAILED` result construction. Keep the existing savepoint. On every exception, roll back and release that savepoint, then re-raise to ordinary fail-closed handling. Keep normal degraded return states unchanged. |
| `context_binding_failure_is_exact` | Remove the validator and its now-unused `datetime` import. Exact successful context validation remains required. |
| `_terminalize_typed_context_binding_failure` | Remove the special failed-job terminalizer. Keep the generic token-local failure/cancellation path unchanged. |
| Factory terminalization loop | Remove only the audit-preserving typed branch. All other terminalization, token isolation, category ordering, and cancellation behavior remain unchanged. |
| `resolve_close_context` | Remove consumer acceptance of `FAILED` context steps and the `typed_context_failure` branch. Require the exact context predecessor to be `SUCCEEDED`; validate owner/evidence/pre-close identity as before. |
| `_close_context_result` | Remove `allow_typed_failure`; require `ok=True`. |
| Positive typed-failure test | Remove the test that monkeypatches `_persist_preclose_context` to raise the semantic marker. It encodes an unreachable production contract. Replace its intended quality proof with real normal-return source failure/rejection producer tests. |
| Same-boundary generic `ValueError` test | Retain or mechanically simplify it as proof that persistence/integrity failure rolls back, uses ordinary token-local cancellation, does not preserve audit, and does not affect another token. It must no longer be framed as the negative half of a typed-exception feature. |
| Consumer-only failed-envelope tests | Remove or invert them: a manually seeded failed context envelope must not make audit claimable. Resolver tests for exact `SUCCEEDED` partial/provider-failed/unknown results remain valid. |

No schema, migration, metadata version, provider call, request budget, retry,
deadline, cutoff, Scheduler category, or Source Governor change follows from
this amendment.

### 25.7 Disposition of `24e7cee` and the preceding repair

`24e7cee` is **partially superseded**, not reverted wholesale.

Retain these proven protections from the combined repair history:

- generic `ValueError` is not audit-preserving;
- close-context work remains inside the savepoint and rolls back on failure;
- the already committed exact closing snapshot remains durable;
- strengthened pre-close request/response/failure provenance checks remain;
- ordinary token-local cancellation remains isolated from other tokens; and
- normal provider/source degradation remains truthful and non-retrying.

Remove the unsupported contract introduced to preserve audit after a technical
failure:

- the semantic exception declaration/catch;
- `CONTEXT_BINDING_FAILED` production and validation;
- failed-context consumer acceptance;
- the special audit-preserving terminalizer branch; and
- tests whose positive premise is a directly injected semantic exception.

Thus the next commit supersedes only the unreachable typed-exception surface.
It must not undo the savepoint, snapshot durability, provenance validation, or
generic fail-closed correction.

### 25.8 Bounded proof required for the narrow implementation

The later implementation proof must be producer-level and focused:

1. a governed broad market/chain degraded result or absence completes context
   structurally, reaches audit, and cannot CLEAN;
2. a real GoPlus provider failure and an explicit safety rejection complete
   context structurally, preserve exact source truth, reach audit, and cannot
   CLEAN;
3. safety composite and applicable holder failure/unknown paths persist real
   contribution/failure truth and produce blockers/optional unknowns without a
   technical envelope;
4. real Jupiter ENTRY/EXIT failure or route-unavailable truth reaches audit and
   cannot satisfy the relevant realism gate;
5. the exact closing snapshot remains unchanged for each normal degraded path;
6. a same-boundary generic `ValueError` and a representative SQLite/integrity
   exception roll back partial context writes, fail the context step/job,
   cancel the exact dependent audit, and leave another token unaffected;
7. a manually seeded failed `CONTEXT_BINDING_FAILED` result is rejected by
   dependency resolution;
8. no production declaration, raise, catch, envelope, validator,
   terminalizer, or consumer path for `ContextBindingCompositionFailure` /
   `CONTEXT_BINDING_FAILED` remains;
9. no provider call count, pre-close yield/reselection, category/fairness,
   Source Governor, 15m/1h/4h cutoff, or accepted `CLOSE_EVIDENCE` deadline
   assertion changes; and
10. touched Python compiles, focused tests pass, and `git diff --check` passes.

Fixtures may use controlled governed adapters to induce real normalized source
failure/rejection results. They must not fabricate the removed technical
envelope.

### 25.9 Functionality risks / setbacks / efficiency blockers

- A successful context step with failed provider evidence can be misread as a
  quality success unless operators and tests continue to distinguish
  operational completion from evidence quality. E2Q and the context envelope,
  not step status alone, are authoritative for CLEAN.
- A technical context failure leaves a durable capture without a completed
  memory audit. This is honest capture-only residue and may require existing
  operator reporting/recovery policy; this amendment does not invent recovery.
- The existing positive typed-failure test is strong end-to-end consumer proof
  for an invalid premise. It must not be retained as evidence of production
  capability merely because it reaches E2Q.
- Real producer tests for each normal-return class are required because a
  monkeypatched persistence dictionary proves only the join consumer.

### 25.10 Explicit locks and non-solutions

This amendment does not authorize:

- converting technical exceptions into partial evidence;
- preserving audit after owner, snapshot, provenance, invariant, database, or
  unclassified failure;
- timestamp backdating or evidence cutoff widening;
- any 15m, 1h, or 4h timing-contract change;
- a pre-close, Scheduler, fairness, Source Governor, provider, budget, retry,
  endpoint, schema, migration, or configuration redesign;
- a second worker or an independent source loop;
- observability/saturation, Lane 3, Cycle 3, 12h/24h, retrieval, decisions,
  BUY/SELL/HOLD, positions, trades, paper audits, or PnL; or
- any live campaign, provider call, database mutation, or runtime execution in
  this design task.

### 25.11 Exact next permitted action and design closeout

The exact next permitted action, after independent acceptance, is one narrow
implementation commit that removes the unreachable audit-preserving technical
binding-exception surface while retaining savepoint rollback, durable closing
capture, strengthened provenance, normal degraded evidence flow, and ordinary
fail-closed cancellation.

No closeout, observability/saturation work, Lane 3 work, or capability unlock is
permitted by that implementation.

**Final design verdict:**
`V2_9_8B_CLOSING_CONTEXT_FAILURE_SEMANTICS_DESIGN_AMENDMENT_ACCEPTED_READY_FOR_NARROW_IMPLEMENTATION`.
