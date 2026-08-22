# Printer V1 V2-9.8B Timely Closing-Context Production Design

**Design kind:** documentation-only specification

**Starting and inspected HEAD:** `536c8e4bedb3a15f500c76a1de5eac21a3c6f9fa`

**Active lane:** `V2-9.8B Lane 2 — Multi-Token Evidence-Deadline Scheduling`

**Design verdict:** `V2_9_8B_TIMELY_CLOSING_CONTEXT_PRODUCTION_DESIGN_PASS_READY_FOR_NARROW_IMPLEMENTATION`

**Runtime status:** the current phase split and current timing corrective implementation remain unaccepted

## 1. Verdict

Repository evidence supports the preferred direction with one necessary
refinement.

Printer shall add one Central-Scheduler-owned pre-close critical acquisition
step for each active close family. That step shall use the existing governed
collector to make the already-budgeted source attempts early enough to be
capable of satisfying each evidence class's lawful cutoff. It shall persist
only durable source request/response/failure truth plus an exact acquisition
envelope. It shall not create or infer a closing snapshot.

The exact closing snapshot remains an independently claimable,
cadence-sensitive `CLOSE_EVIDENCE` step. After that snapshot exists, the
existing `CLOSE_CONTEXT` phase becomes a binding/resolution phase: it validates
the exact pre-close envelope, rehydrates its durable source records, binds
eligible observations to the exact closing snapshot/window, resolves periodic
broad context, and classifies late or failed results honestly. `CLOSE_AUDIT`
then consumes either complete context or an explicit partial/failed/unknown
context result.

The resulting normal execution sequence is:

```text
PRE_CLOSE_CRITICAL
-> Central Scheduler reselection
-> CLOSE_EVIDENCE
-> Central Scheduler reselection
-> CLOSE_CONTEXT_BIND
-> Central Scheduler reselection
-> CLOSE_AUDIT
```

The dependency model is a fork-join rather than a hard success chain:

```text
PRE_CLOSE_CRITICAL terminal result ---------\
                                             -> CLOSE_CONTEXT_BIND -> CLOSE_AUDIT
CLOSE_EVIDENCE exact successful snapshot ---/
```

Provider failure or missing pre-close context must not suppress the closing
snapshot. Exact evidence failure still prevents exact binding and closing
audit under the existing integrity law.

This design requires new step kinds and metadata behavior, but no new Scheduler
category, worker loop, source adapter, provider, configuration, table, column,
or migration.

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

### 3.1 Chosen: one pre-close acquisition phase plus later exact binding

Advantages:

- moves existing calls instead of duplicating them;
- preserves the current source adapters and Source Governor path;
- gives the Central Scheduler a reselection point before exact capture;
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

### 3.4 Rejected: one Scheduler phase per provider/evidence class

Per-source micro-phases would multiply Scheduler rows, dependency edges,
partial-result states, source reservations, and exact-owner joins. The current
collector already owns one bounded bundle and can produce a durable per-source
envelope. The extra complexity is not required for this repair.

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

`CLOSE_CONTEXT` may retain its current step-kind name. Its responsibility
changes from “make new required main-window calls and persist them” to
“join, validate, bind, resolve, classify and report.” Reports should describe
it as `CLOSE_CONTEXT_BIND`; historical database vocabulary need not be renamed.

### 4.2 Per-window lifecycle order

The intended temporal order for one window is:

1. `PRE_CLOSE_CRITICAL` is scheduled and claimed before the close boundary.
2. Scheduler reselects globally.
3. `CLOSE_EVIDENCE` captures only the exact closing snapshot.
4. Scheduler reselects globally.
5. `CLOSE_CONTEXT` joins the terminal acquisition result with the successful
   evidence result and binds/resolves context.
6. Scheduler reselects globally.
7. `CLOSE_AUDIT` closes and audits with complete or honest incomplete context.

`CLOSE_EVIDENCE` is not success-dependent on `PRE_CLOSE_CRITICAL`. The
pre-close step must reach a durable terminal result before context joins it,
but that terminal result may be `TIMELY`, `PARTIAL`, `FAILED`, `LATE`,
`MISSED_CUTOFF`, or `CANCELLED_BEFORE_ATTEMPT`. Provider/data outcome is not
the same as Scheduler step integrity.

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

Each planned pre-close step receives:

```text
class_cutoff_at
preclose_handoff_at
preclose_scheduled_for
preclose_deadline_at
bounded_attempt_seconds
contention_cohort_identity
contention_ordinal
```

The formula is:

```text
latest_preclose_handoff_at
  = min(
      unchanged CLOSE_EVIDENCE scheduled_for,
      unchanged CLOSE_EVIDENCE deadline_at,
      earliest lawful cutoff among source observations in this step
    )
    - CLOSE_EVIDENCE_RESELECTION_RESERVE_SECONDS

preclose_handoff_at
  = latest_preclose_handoff_at

bounded_attempt_seconds(step)
  = sum(existing one-attempt adapter hard timeouts for the step's
        worst-case moved call plan, including conditional holder fallback)
    + sum(existing deterministic source-pacer waits)
    + bounded local result-envelope reserve

preclose_scheduled_for(step_j)
  = preclose_handoff_at
    - sum(bounded_attempt_seconds(step_k)
          for step_k at-or-after j in the exact contention cohort)

preclose_deadline_at(step_j)
  = preclose_scheduled_for(step_j) + bounded_attempt_seconds(step_j)
```

For every current 15m/1h/4h close this plans the whole bundle to hand control
back before the unchanged exact-snapshot dispatch point. For 4h, the planned
handoff therefore remains at or before the logical end even though exact
closing safety/holder and EXIT observations have a narrow lawful +60-second
outer cutoff. That exception remains available to classify a real already-
running attempt and later snapshot truthfully; it is not used to plan routine
delay or to move market/chain past the end.

The exact contention cohort contains Scheduler-owned pre-close work whose
reserved single-worker execution intervals overlap and is frozen from exact
campaign/run/cycle/token/slot/window identities at planning time. Its ordinal
uses the accepted token/cycle fairness rotation and stable identity tie-breaks,
never a score, confidence, historical latency estimate, outcome, or permanent
cycle preference.

`CLOSE_EVIDENCE_RESELECTION_RESERVE_SECONDS` is a Scheduler handoff bound, not
an evidence allowance. The later implementation must define its exact constant
from bounded local claim/finalize/reselection operations and prove it in
disposable tests before runtime acceptance.
It may not be derived from historical provider latency. If the implementation
cannot prove a finite bound for configured one-attempt source timeouts, pacing,
and local handoff, it must stop `BLOCKED` rather than invent or learn one.

Scheduling makes timely acquisition possible; it does not guarantee CLEAN.
Higher AGENTS categories, Source Governor denial, provider latency, timeout,
or resource exhaustion may still make evidence late/missing. Actual source
timestamps remain final authority.

### 6.5 Provider response crossing a boundary

- 15m or 1h safety/holder/15m quote observed after `window_end_at` is late and
  cannot support CLEAN, even if the request started earlier.
- 4h market/chain observed after `window_end_at` is late.
- The same single 4h safety/holder/EXIT attempt may remain eligible when its
  real observation time is no later than `window_end_at + 60s` and all other
  gates pass. This is not a retry or broader context allowance.
- A call still running near exact capture can delay the single worker. The
  separate lead-time and hard-timeout contract is intended to prevent normal
  overlap, but a real overrun is reported honestly; it never widens cadence or
  evidence thresholds.

## 7. Acquisition and binding identity contract

### 7.1 Identity known before acquisition

`PRE_CLOSE_CRITICAL` must be projected with the exact:

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
- exact governed request-key prefix and allowed source request families.

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

1. exactly one terminal pre-close step with the expected contract/version and
   intended evidence step;
2. exactly one successful evidence step with an actual exact snapshot;
3. identical campaign/run/cycle/slot/window/factory-run/stage/work-scope owner;
4. identical token/mint/pair/pair-address/tracking-lane/window family;
5. exact source request/response/failure linkage and request-key prefix;
6. returned source target matches the immutable intended target;
7. each real observation time satisfies its own class cutoff before it is
   marked main-window eligible; and
8. no source record is substituted from another token, pair, cycle, window,
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

The 15m pre-close step uses this order:

1. resolve an already-persisted, provenance-clean, fresh market/chain row at or
   before the intended end;
2. only if broad context is absent, perform the already-budgeted single
   governed broad-context call;
3. perform the existing governed GoPlus/core safety attempts;
4. perform the existing governed ENTRY and EXIT quote attempts; and
5. perform conditional holder primary/approved backup exactly as today.

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

The 1h pre-close step moves the existing required safety-only bundle earlier:

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

The 4h pre-close step first resolves valid periodic market/chain rows. If
either required shared row is absent, it uses the existing single governed
broad-context request before close and later persists both supported contexts
from that one response. Market/chain remain eligible only when observed no
later than `window_end_at` and within existing freshness/provenance rules.

The same pre-close step also makes the existing one-attempt closing safety,
conditional holder, and EXIT quote requests. It does not duplicate them after
capture. Their existing exact-closing allowance remains `window_end_at + 60s`.
A pre-close request whose response truthfully arrives in that narrow interval
may be bound after the exact snapshot and may qualify; a response after +60s
is support only.

The exact closing snapshot independently retains its existing +60s allowance.
The existing 4h opening ENTRY quote remains unchanged. Market, chain, opening
ENTRY, or unrelated evidence never inherit the 4h closing allowance.

## 11. `CLOSE_CONTEXT` responsibility

For the minimum implementation slice, `CLOSE_CONTEXT` shall perform only:

1. exact evidence-step resolution;
2. exact terminal pre-close-envelope resolution;
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
target mismatch, or evidence genuinely unavailable is a terminal acquisition
outcome, not permission to retry and not necessarily a Scheduler integrity
failure. Preserve every created source row and the exact envelope, then allow
the exact snapshot phase to proceed independently.

### 12.2 Evidence failure

If `CLOSE_EVIDENCE` does not produce one valid exact closing snapshot:

- no closed memory window is fabricated;
- no preassigned or nearby snapshot is substituted;
- no token-specific pre-close result is bound as closing evidence;
- dependent binding/audit stops under existing exact-evidence integrity law;
- raw source rows and the pre-close envelope remain as unbound diagnostic or
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

After every pre-close source bundle, evidence capture, context bind, or audit,
the single worker returns to global Scheduler selection. No phase recursively
executes the next phase.

### 14.3 Missed pre-close slot

If a pre-close job is still pending at its deadline, it becomes an exact
`MISSED_CUTOFF`/not-attempted terminal envelope through the Scheduler owner;
it may not start late and pretend to be timely. Already-due `CLOSE_EVIDENCE`
wins the intra-close collision. A running source attempt retains its hard
one-attempt timeout; there is no second worker or unsafe preemption. Any real
overrun and resulting capture delay is reported honestly.

## 15. Budget implications

The intended source-cost delta is zero.

| Family | Existing close-context calls | New disposition |
| --- | --- | --- |
| 15m | current six-unit preclose/context reservation | move to `WINDOW_CLOSE_PRE_CLOSE_CRITICAL`; context bind owns zero new provider attempts |
| 1h | current four-unit safety reservation | move to `CONTINUATION_CLOSE_PRE_CLOSE_CRITICAL`; context bind owns zero new provider attempts |
| 4h | current long-close context reservation | move the same broad/safety/holder/EXIT attempts to `LONG_CONTINUATION_CLOSE_PRE_CLOSE_CRITICAL`; context bind owns zero new provider attempts |

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

## 16. Required scenario walkthroughs

### A. 15m normal timely close

1. Scheduler claims the exact token/window pre-close step at its deterministic
   fire time.
2. Safety, required quote and any necessary broad/holder observations finish
   no later than `window_end_at`; source rows and envelope persist real times.
3. Scheduler reselects.
4. Evidence captures the exact closing snapshot at the lawful boundary and
   attaches it to the run ledger.
5. Context validates both owners, binds frozen observations to the exact
   snapshot, resolves broad context, and emits `CONTEXT_COMPLETE`.
6. Audit runs unchanged quality gates. CLEAN remains possible, never promised.

### B. 15m provider response crosses `window_end_at`

The response retains its real late `received_at`. Context classifies that
evidence late/support-only. It cannot satisfy safety/quote/broad CLEAN input.
The snapshot and audit remain honest; there is no CLEAN rescue or retry.

### C. 15m closing snapshot delayed

The snapshot keeps its actual capture time. Zero allowance remains zero.
Pre-close timing does not widen snapshot or context boundaries. Existing
cadence/evidence owners classify the delayed capture.

### D. Pre-close succeeds but closing snapshot fails

Source rows and envelope remain durable and unbound to a closing snapshot. No
window is fabricated. Context binding and close audit stop for missing exact
evidence. Token-specific observations cannot migrate to another close.

### E. Snapshot succeeds but context binding fails

The snapshot and ledger attachment remain durable. If exact failure identity is
preserved, context emits `CONTEXT_BINDING_FAILED` and audit runs to record
dirty/do-not-train truth. If binding identity is ambiguous or the failure
envelope itself cannot be trusted, existing integrity law stops audit and
reports capture-only terminal residue.

### F. 1h normal close

The safety/holder bundle is observed before the fixed logical 1h end. The
forced snapshot may occur at the deadline or within its independent +60s
freshness band. Context binds the frozen safety composite afterward. The 1h
overlay verifies every required contribution against `window_end_at`, not the
later snapshot time. Snapshot +60 is never borrowed by context.

### G. 4h close

Periodic or fallback broad context must be observed no later than
`window_end_at`. The single safety/holder/EXIT attempt may qualify only through
its existing end +60 cutoff. The exact snapshot independently uses its existing
+60 rule. Later market/chain cannot qualify.

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
| `src/printer_v1/operator_cli/close_phases.py` | Add three pre-close step kinds, contract version/metadata, exact pre-close resolver, fork-join dependency rules, terminal context failure resolution, and phase-order mapping |
| `src/printer_v1/operator_cli/one_command_15m_factory.py` | Plan deterministic pre-close slots; execute the existing governed collector there; persist acquisition envelopes; make context rehydrate/bind without duplicate calls; keep evidence snapshot-only; preserve global reselection |
| `src/printer_v1/sources/measured_transport.py` | Reassign existing close-context reservations to pre-close step kinds and set binding phases to zero provider operations; do not raise ceilings |
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
- reuse existing `CLOSE_EVIDENCE`, `CLOSE_CONTEXT`, `CLOSE_AUDIT`: **yes**;
- new `JobKind` or category: **no**;
- result/ownership metadata changes: **yes**;
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
| P12 — no duplicate calls | For each family, source request counts equal the existing bounded bundle after movement; context binding makes zero duplicate provider calls. |
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
  worker. The deterministic lead/hard-timeout contract reduces planned
  collisions but does not promise provider behavior.
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
Pre-Close Acquisition and Post-Capture Binding Implementation
```

That slice may modify only the minimum surfaces in Section 17 and their nearest
focused tests. It must implement the fork-join phase contract, move rather than
duplicate existing calls, preserve all timing/category/deadline locks, and run
the bounded offline proof matrix appropriate to the changed surfaces.

It may not start observability/saturation or Lane 3. It may not run a live
campaign or provider. If design acceptance is withheld, the next action is
operator review or a corrected documentation-only design—not implementation.

## 23. Design closeout

**Status:** `PASS_READY_FOR_NARROW_IMPLEMENTATION_AFTER_INDEPENDENT_ACCEPTANCE`.

The chosen architecture makes timely main-window context production possible
without promising provider success, fabricating a snapshot, backdating
evidence, widening a threshold, duplicating calls, bypassing central owners, or
reintroducing the monolithic close claim. No implementation is performed or
accepted by this document.
