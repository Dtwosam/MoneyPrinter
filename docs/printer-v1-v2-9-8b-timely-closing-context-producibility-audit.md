# Printer V1 V2-9.8B Timely Closing-Context Producibility Audit

**Audit kind:** documentation-only, read-only

**Starting and inspected HEAD:** `0b9b0d687eece3084fef9406392371bfabd4d38b`

**Active lane:** `V2-9.8B Lane 2 — Multi-Token Evidence-Deadline Scheduling`

**Audit verdict:** `V2_9_8B_TIMELY_CLOSING_CONTEXT_PRODUCIBILITY_GAP_PROVEN`

**Implementation status:** no implementation is accepted or repaired by this audit

## 1. Executive verdict

The remaining gap is proven.

The current Scheduler-owned phase order is:

```text
CLOSE_EVIDENCE
-> Scheduler reselection
-> CLOSE_CONTEXT
-> Scheduler reselection
-> CLOSE_AUDIT
```

`CLOSE_EVIDENCE` creates and persists the exact closing snapshot. Only after
that phase succeeds may `CLOSE_CONTEXT` run. Current `CLOSE_CONTEXT` does both
of the following:

1. it makes new governed source calls through the existing close collector;
2. after every selected call completes, it persists and binds those results to
   the already-known closing `snapshot_id`.

It is therefore not merely a resolver of already-existing timely evidence.
For newly fetched context, the real source observation and composite evaluation
times occur after the closing snapshot has been persisted. The current resolver
correctly refuses to treat those later timestamps as earlier main-window truth.

The resulting clean-producibility verdicts are:

| Window family | Overall verdict | Exact reason |
| --- | --- | --- |
| `WINDOW_15M` | `NOT_PRODUCIBLE` | Zero allowance requires exact closing safety, holder where needed, ENTRY quote and EXIT quote no later than `window_end_at`. The active producer first calls those sources after the closing snapshot whose capture establishes that boundary. No active pre-capture producer supplies results for later exact binding. |
| `WINDOW_1H` | `NOT_PRODUCIBLE` | The +60s contract belongs only to forced-closing-snapshot freshness. The sole current 1h close-context producer creates safety/holder context after that snapshot. It has no authority to use the snapshot allowance for those observations, and the 1h binding helper does not independently prove the lawful cutoff. |
| `WINDOW_4H` | `PRODUCIBLE_ONLY_IF_PREEXISTING_TIMELY_CONTEXT_EXISTS` | The current post-capture producer can lawfully create the exact snapshot, safety composite, conditional holder contribution and EXIT quote only if they complete inside the existing +60s boundary. Market and chain remain cut off at `window_end_at`; the active factory has no independent scheduled refresh owner that guarantees a timely row before close. |

The proven primary root cause is a **phase-order design conflict** combined with
a **missing timely producer boundary**. The historical owner intentionally
separated observation from binding: it collected governed context before the
closing snapshot, then persisted and bound the already-observed results after
the snapshot id became known. The current phase split moved the source calls,
not only their binding, to after capture.

The timing-correction and phase-split fixtures do **not** prove real producer
capability. They prove resolver boundaries, snapshot timestamp immutability,
phase dependencies, and Scheduler selection. The tests that demonstrate timely
15m or 4h context manually insert source/evidence rows at chosen timestamps.

## 2. Scope, authority, and method

This audit used the requested active source stack and only the nearest relevant
current implementation and tests. It did not preload unrelated historical
documents. In particular it inspected:

- `AGENTS.md`;
- `docs/printer-v1-clean-master-spec.md`;
- `docs/printer-v1-post-rc-build-order.md`;
- `docs/printer-v1-memory-factory-guide.md`;
- `docs/printer-v1-current-state-memory-growth-audit.md`;
- `docs/printer-v1-memory-growth-build-order-v2.md`;
- `CURRENT_HANDOFF.md`;
- `docs/printer-v1-python-builder-guide.md`;
- the accepted post-capture amendment in
  `docs/printer-v1-v2-9-8b-multi-token-evidence-deadline-scheduling-design.md`;
- the V2-9.4.6 and V2-9.4.8 closeouts;
- current close phase, factory, shared context, safety, holder, quote, market,
  chain, cadence, 1h and 4h owners; and
- the nearest phase, timing, identity and cutoff tests.

The audit is static. It made no provider call, campaign run, database mutation,
runtime invocation, or disposable fixture mutation. Static repository evidence
is sufficient to establish the ordering conflict.

The Python Builder Guide classification is source-grounded:

- primary: `DESIGN_GAP` / phase-order design conflict;
- accompanying: `MISSING_APPROVED_IMPLEMENTATION_BOUNDARY` / missing timely
  producer;
- additional: test-only producer-coverage gap;
- additional 1h enforcement finding: committed code does not validate the
  safety composite against the 1h logical cutoff before binding it as the
  first-hour overlay.

No source/provider scarcity was observed or inferred.

## 3. Time facts that must remain distinct

The current code has at least six distinct times. None can stand in for another:

| Time | Current owner | Meaning |
| --- | --- | --- |
| Scheduler execution time | Scheduler job/step `started_at` and `finished_at` | When a worker claimed and finished a phase. |
| Source request start | `SourceRequest.requested_at` | When `build_governed_source_request` built the request, immediately before Source Governor recording/execution. |
| Source request completion | `NormalizedSourceResult.received_at`, persisted as source response `received_at`, or failure `failed_at` | When the adapter result/failure was actually available. |
| Evidence observation/evaluation | Broad context `captured_at`; safety contribution `captured_at`; quote `evidence_captured_at`; composite `evidence_captured_at`/evaluation time | When the relevant fact was observed or evaluated. |
| Snapshot capture | `printer_token_snapshots.captured_at` | The exact-pair source response time used by E2M snapshot persistence. |
| Logical window end | `printer_memory_windows.window_end_at` | The immutable main-window evidence boundary. It is not changed by later phase execution. |
| Persistence/binding time | the later database insert/update transaction | When an already-observed fact was stored and associated with exact identities. This may lawfully be later than observation, but cannot change observation time. |

`execute_source_request_with_governor` records and commits the request before
adapter I/O, then records the response/failure after the adapter returns.
`_persist_preclose_context` runs only after the selected collector calls have
finished. Thus a late response cannot become timely because its database row is
later bound to an exact snapshot.

## 4. Exact current flow

### 4.1 Planning and ownership

`_close_phase_plan` creates three Scheduler-owned steps for every active close
family:

| Window | Evidence step | Context step | Audit step |
| --- | --- | --- | --- |
| 15m | `WINDOW_CLOSE_EVIDENCE` | `WINDOW_CLOSE_CONTEXT` | `WINDOW_CLOSE_AUDIT` |
| 1h | `CONTINUATION_CLOSE_EVIDENCE` | `CONTINUATION_CLOSE_CONTEXT` | `CONTINUATION_CLOSE_AUDIT` |
| 4h | `LONG_CONTINUATION_CLOSE_EVIDENCE` | `LONG_CONTINUATION_CLOSE_CONTEXT` | `LONG_CONTINUATION_CLOSE_AUDIT` |

All three are projected at the same logical close time, but dependency
resolution requires evidence success before context is claimable and context
success before audit is claimable. Scheduler reselection between phases
preserves the accepted category/fairness rules.

### 4.2 `CLOSE_EVIDENCE`

`_execute_close_evidence_phase`:

1. calls `_execute_snapshot`;
2. builds a governed DexScreener exact-pair request at actual execution time;
3. records the request through Source Governor;
4. executes the source adapter, with only the already-approved governed Gecko
   fallback on an eligible transient failure;
5. persists the snapshot through E2M with `captured_at` derived from the exact
   source response `received_at`;
6. obtains `snapshot_id` only from that persistence result;
7. durably attaches that exact id to the current-run ledger; and
8. returns the stored snapshot `captured_at` as `evidence_captured_at`.

No safety, quote, holder, market, or chain call occurs in this phase.

### 4.3 `CLOSE_CONTEXT`

`_execute_close_context_phase` first resolves the successful exact evidence
predecessor. The closing `snapshot_id` is therefore already known and the
snapshot already exists before any context source request begins.

It then calls `_collect_preclose_context`, despite that historical function
name and docstring, with this current family-specific selection:

| Window | New calls made by current context phase, in collection order |
| --- | --- |
| 15m | CoinGecko market/chain; GoPlus safety; optional core Solana RPC safety; Jupiter ENTRY; Jupiter EXIT; conditional holder primary; optional single approved holder backup |
| 1h | GoPlus safety; optional core Solana RPC safety; conditional holder primary; optional single approved holder backup |
| 4h | CoinGecko market/chain; GoPlus safety; optional core Solana RPC safety; Jupiter EXIT; conditional holder primary; optional single approved holder backup |

Every call uses `execute_source_request_with_governor`. There is no Source
Governor bypass, private loop, timestamp override, or retry expansion.

After collection returns, `_persist_preclose_context`:

- persists market and chain with the broad response's real `received_at`;
- persists GoPlus safety from its source response and exact source trace;
- persists a safety composite against the closing snapshot with
  `evaluated_at=_iso()` at the real later persistence/evaluation instant;
- persists conditional holder evidence as a real contribution to that
  composite; and
- persists Jupiter evidence using the normalized quote/source result's real
  evidence/response time.

This phase therefore does **both B and C** from the accepted amendment: it makes
new governed post-capture calls and persists their later truth. It does not
perform A as a separate producer action. The later audit resolver may find an
older row already in the database, but the context executor itself does not
schedule or acquire such a timely row in advance.

Consequences:

- all new 15m context observations and the composite evaluation necessarily
  occur after the closing snapshot/window cutoff;
- all new 1h safety/holder observations necessarily occur after the closing
  snapshot, which is at or after the logical 1h deadline;
- new 4h safety/holder/EXIT evidence may remain lawful only if its actual times
  are no later than `window_end_at + 60s`;
- all new 4h market/chain observations remain late when after
  `window_end_at`, even if they finish inside +60s; and
- serial market/safety/RPC/quote/holder latency consumes the same 60-second 4h
  interval before the later composite is evaluated.

### 4.4 `CLOSE_AUDIT`

`_execute_close_audit_phase` is source-free. It consumes the exact evidence and
context predecessor results and never fetches or recaptures.

- 15m closes the memory window, calls the shared context resolver without
  `tracking_lane`, applies the exact context/quality gate, audits, then attempts
  the clean-memory pipeline.
- 1h closes the continuation window, binds the persisted safety composite as a
  first-hour overlay, derives the outcome from the exact current-run snapshot
  path, audits, then attempts the clean-memory pipeline.
- 4h closes through the existing 4h owner, calls the shared 4h resolver with
  exact run/lane identity, derives outcome, and runs 4h quality gates.

The shared 15m/4h resolver is read-only. It correctly selects only rows inside
each class cutoff and reports exact late/absent blockers. It is not a producer.

## 5. Historical pre-phase flow

The historical path is still visible in the legacy executors and is explicitly
documented by the V2-9.4.8 closeout.

### 5.1 15m historical ordering

```text
collect governed pre-close context
-> capture/persist exact closing snapshot
-> attach snapshot to current-run ledger
-> persist and bind already-observed context to snapshot_id
-> close window
-> resolve/audit
```

This was intentional, not incidental. Source results did not need a snapshot id
at acquisition time. The closing snapshot id became known later, and the
already-observed response was then persisted with exact target/snapshot
identity while retaining its original observation time.

15m evidence classes dependent on this ordering were:

- market regime and Solana chain heat from the shared CoinGecko response;
- GoPlus/core-RPC safety and conditional holder evidence;
- the safety composite;
- ENTRY quote; and
- EXIT quote.

Trading-flow and chart evidence did not depend on pre-close context. They were
derived later from the exact admitted snapshot set.

### 5.2 1h historical ordering

The historical `_execute_continuation_close` collected its safety-only bundle
before the final 1h snapshot, then captured the snapshot, persisted/bound the
safety composite, closed the window, and attached the overlay. Safety and the
conditional holder contribution depended on that ordering.

### 5.3 4h historical ordering

The historical `_execute_long_4h_step` collected:

- market/chain and ENTRY quote before the opening 4h snapshot; and
- market/chain, safety/conditional holder and EXIT quote before the closing 4h
  snapshot.

It then bound each already-observed bundle after the corresponding snapshot id
became known. The current non-close 4h opening path still uses the first of
those patterns. The split close path no longer uses the second.

## 6. Per-window / per-evidence producer matrix

Verdicts in this section use only the required vocabulary. A class marked not
currently consumed is still given a verdict; `UNKNOWN_INSUFFICIENT_EVIDENCE`
means the current 1h close has neither a complete class-specific producer nor a
class-specific CLEAN gate from which producibility can be proven.

### 6.1 `WINDOW_15M`

| Evidence class | Scheduler | Executor / Source Governor | Required for current CLEAN gate | May an earlier row satisfy? | Current lawful producibility |
| --- | --- | --- | --- | --- | --- |
| Closing snapshot | Central Scheduler `WINDOW_CLOSE_EVIDENCE` | `_execute_snapshot`; governed DexScreener, optional governed Gecko fallback | Yes: exact ledger bounds, fields, trace, cadence | Only the exact evidence-step snapshot | `PRODUCIBLE` when captured at the zero-allowance boundary and all existing cadence/quality gates pass |
| Safety composite | Context phase scheduled after evidence | `_collect_preclose_context` + `_persist_preclose_context`; governed GoPlus/core RPC | Yes | Only an exact closing-snapshot-bound timely row; no active owner creates one before this close | `NOT_PRODUCIBLE` |
| Holder evidence | Conditional part of context safety plan | Governed Solana RPC, optional single governed Helius fallback | Conditional: required when the composite needs holder resolution | Only as an exact timely contribution to an acceptable composite | `NOT_PRODUCIBLE` when applicable |
| ENTRY quote | Context phase after evidence | Governed Jupiter; bound by current 15m resolver to the closing snapshot | Yes in the current 15m liquidity section | Exact timely row for the closing snapshot only; no active advance owner | `NOT_PRODUCIBLE` |
| EXIT quote | Context phase after evidence | Governed Jupiter; exact closing snapshot | Yes | Exact timely row for the closing snapshot only; no active advance owner | `NOT_PRODUCIBLE` |
| Market regime | Context phase after evidence | Governed CoinGecko; shared row | Yes | Yes, any provenance-clean row already captured no later than end and still valid | `PRODUCIBLE_ONLY_IF_PREEXISTING_TIMELY_CONTEXT_EXISTS` |
| Solana chain heat | Context phase after evidence | Same governed CoinGecko response; shared row | Yes | Yes, under the same timing/provenance/freshness rules | `PRODUCIBLE_ONLY_IF_PREEXISTING_TIMELY_CONTEXT_EXISTS` |
| Trading flow | No separate source job | Shared resolver derives from exact current-run snapshots | Yes | Exact admitted snapshot set is the evidence | `PRODUCIBLE` if snapshot set and fields are clean |
| Chart / volatility | No separate source job | Shared resolver derives from exact current-run snapshots | Yes | Exact admitted snapshot set is the evidence | `PRODUCIBLE` if snapshot set and fields are clean |
| **Overall** | — | — | Every shared section must support clean memory | Safety and quotes cannot be supplied by the current ordering | **`NOT_PRODUCIBLE`** |

15m contract preserved exactly:

```text
closing_evidence_allowance_seconds = 0
closing_evidence_cutoff_at = window_end_at
```

No widening is proposed or permitted.

### 6.2 `WINDOW_1H`

| Evidence class | Scheduler | Executor / Source Governor | Required by current 1h close | May an earlier row satisfy? | Current lawful producibility |
| --- | --- | --- | --- | --- | --- |
| Closing snapshot | Central Scheduler `CONTINUATION_CLOSE_EVIDENCE` | `_execute_snapshot`; governed exact-pair source path | Yes | Exact evidence-step snapshot | `PRODUCIBLE` at the fixed deadline through +60s under the existing forced-snapshot freshness bands |
| Safety composite | Context phase after evidence | Governed GoPlus/core RPC, then real-time composite evaluation | Operationally mandatory: audit refuses missing persisted context and binds this overlay | Only an exact timely contribution later bound to the closing snapshot; no active advance owner exists | `NOT_PRODUCIBLE` |
| Holder evidence | Conditional part of safety collection | Governed Solana RPC / optional single Helius fallback | Conditional within the required composite | Only as a timely composite contribution | `NOT_PRODUCIBLE` when applicable |
| ENTRY quote | No 1h close producer | Not requested by the current 1h context phase | No explicit current 1h closing-quote gate was found | The current 1h audit does not resolve one | `UNKNOWN_INSUFFICIENT_EVIDENCE` |
| EXIT quote | No 1h close producer | Not requested by the current 1h context phase | No explicit current 1h closing-quote gate was found | The current 1h audit does not resolve one | `UNKNOWN_INSUFFICIENT_EVIDENCE` |
| Market regime | No active 1h close producer | Not requested or resolved by the current 1h audit | Required as episode context by the master spec, but no exact 1h class gate exists here | Not attached by the current 1h close | `UNKNOWN_INSUFFICIENT_EVIDENCE` |
| Solana chain heat | No active 1h close producer | Not requested or resolved by the current 1h audit | Same master-spec/current-gate mismatch as market | Not attached by the current 1h close | `UNKNOWN_INSUFFICIENT_EVIDENCE` |
| Trading flow | Central Scheduler snapshot path | Outcome is derived from exact current-run snapshots | Snapshot path is used for outcome; no explicit 1h flow CLEAN section is evaluated | Snapshot inputs exist, but class-level clean proof is absent | `UNKNOWN_INSUFFICIENT_EVIDENCE` |
| Chart / volatility | Central Scheduler snapshot path | No explicit 1h chart/volatility close resolver | Required as episode context by the master spec, but no explicit 1h class gate exists | Snapshot inputs exist, but class-level clean proof is absent | `UNKNOWN_INSUFFICIENT_EVIDENCE` |
| **Overall** | — | — | At minimum the mandatory safety overlay must be lawful | It is first produced after the logical cutoff | **`NOT_PRODUCIBLE`** |

The +60s 1h rule applies only to the forced closing snapshot. No inspected
authority applies it to safety, holder, quote, market, chain, flow, or chart
observations. The current `attach_first_hour_safety_overlay` verifies exact
window/token/pair/mint/pair-address/snapshot identity, but it does not compare
the composite or contribution timestamps with `window_end_at`. Identity is not
time authority. A path that can label/promote a 1h object while binding a late
composite does not prove a lawfully CLEAN 1h object.

### 6.3 `WINDOW_4H`

| Evidence class | Scheduler | Executor / Source Governor | Required for current CLEAN gate | May an earlier row satisfy? | Current lawful producibility |
| --- | --- | --- | --- | --- | --- |
| Closing snapshot | Central Scheduler `LONG_CONTINUATION_CLOSE_EVIDENCE` | `_execute_snapshot`; governed exact-pair source path | Yes | Exact evidence-step snapshot | `PRODUCIBLE` when actual capture is no later than end +60s and all cadence gates pass |
| Safety composite | Context phase after evidence | Governed GoPlus/core RPC, conditional holder, later composite evaluation | Yes, exact closing snapshot | A valid exact row may be resolved; current new row may also qualify inside +60s | `PRODUCIBLE` only when every required observation and composite evaluation truthfully completes by end +60s |
| Holder evidence | Conditional part of safety collection | Governed Solana RPC / optional single Helius fallback | Conditional within safety composite | Yes, only as an exact contribution inside the safety cutoff | `PRODUCIBLE` when applicable and completed by end +60s |
| ENTRY quote | Scheduler-owned 4h opening snapshot step | Existing opening path collects governed Jupiter before opening capture and binds afterward | Yes, exact opening snapshot/original boundary | Yes, the opening-bound row is the intended authority | `PRODUCIBLE` |
| EXIT quote | Context phase after closing evidence | Governed Jupiter, exact closing snapshot | Yes | Existing exact row or current new row inside +60s | `PRODUCIBLE` only when observed by end +60s |
| Market regime | Context phase after closing evidence | Governed CoinGecko, but newly observed after end | Yes | Yes, a provenance-clean row already captured at/before end and within the 3h freshness contract | `PRODUCIBLE_ONLY_IF_PREEXISTING_TIMELY_CONTEXT_EXISTS` |
| Solana chain heat | Context phase after closing evidence | Same governed CoinGecko response, newly observed after end | Yes | Yes, under the same boundary/provenance/3h freshness contract | `PRODUCIBLE_ONLY_IF_PREEXISTING_TIMELY_CONTEXT_EXISTS` |
| Trading flow | No separate context call | Shared resolver derives from exact admitted current-run snapshots, including lawful closing snapshot | Yes | Exact snapshot set | `PRODUCIBLE` if the snapshot set and fields pass |
| Chart / volatility | No separate context call | Shared resolver derives from exact admitted current-run snapshots | Yes | Exact snapshot set | `PRODUCIBLE` if the snapshot set and fields pass |
| **Overall** | — | — | Every shared section must support clean memory | Timely broad rows are not guaranteed by the active lifecycle | **`PRODUCIBLE_ONLY_IF_PREEXISTING_TIMELY_CONTEXT_EXISTS`** |

The +60s 4h allowance scope is confirmed and remains narrow:

- exact closing snapshot;
- exact closing safety composite, including required contributions; and
- exact closing EXIT quote.

It does not extend market, chain, ENTRY quote, or unrelated evidence. A 4h
source timeout or serial response that completes after +60s is truthful source
latency and produces late/unknown support, not a code permission to widen or
backdate.

## 7. Timestamp and binding matrix

| Evidence | Request start | Completion / observation | Persistence | When `snapshot_id` is known | Exact binding moment | Lawful cutoff |
| --- | --- | --- | --- | --- | --- | --- |
| Closing snapshot | Exact-pair `SourceRequest.requested_at` in evidence phase | Exact-pair result/response `received_at`; becomes snapshot `captured_at` | E2M immediately after governed response | At E2M insert/reuse result | Ledger attachment in evidence phase | 15m: end; 1h: snapshot freshness only through +60; 4h: through +60 |
| Market regime | CoinGecko request construction in context collector | Broad response `received_at`, copied to context `captured_at` | After the full selected context bundle returns | Current split: already known before request; historical: unknown during request | Persisted shared row carries source provenance and close target metadata; resolver later selects it | All families: `<= window_end_at` |
| Solana chain heat | Same CoinGecko request | Same real response time | Same later persistence transaction | Same as market | Same as market | All families: `<= window_end_at` |
| GoPlus safety row | GoPlus request construction | Response `received_at` | After bundle collection, through GoPlus normalizer | Current: known before call; historical: known only afterward | Inserted with exact token/pair/closing snapshot | 15m/1h: end; 4h: end +60 |
| Core RPC safety contribution | RPC request construction | Response `received_at` or failure `failed_at` | Composite persistence after collection | Same | Exact composite contribution to closing snapshot | Inherits safety cutoff |
| Holder contribution | Conditional request after GoPlus result (and after selected quote calls in the current collector order) | Primary/backup response time or failure time | Composite persistence after collection | Same | Exact contribution inside closing-snapshot composite | Inherits safety cutoff; no independent allowance |
| Safety composite | No independent source request | `evaluated_at=_iso()` during `_persist_preclose_context`; underlying source times retained | Composite insert | Known before current evaluation; historical binding after snapshot | Exact closing `snapshot_id`; 1h overlay/window binding occurs later in audit | Evaluation and every contribution must satisfy class cutoff when the evaluation incorporates the fresh observations |
| ENTRY quote | Jupiter request construction | Normalized quote/source result evidence time, falling back to real `received_at` | After bundle collection | Current 15m: known before call; historical 15m/4h opening: unknown during call | 15m current resolver expects close snapshot; 4h expects opening snapshot | Original entry boundary; never inherits closing +60 |
| EXIT quote | Jupiter request construction | Normalized quote/source result evidence time / `received_at` | After bundle collection | Current: known before call; historical: unknown during call | Exact closing snapshot | 15m/1h: end; 4h: end +60 |
| Trading flow | No separate call | Actual admitted snapshot `captured_at` values; deterministic derivation later | Stored in supporting context/audit outputs | Snapshot set known by audit | Exact current-run ledger set and end snapshot | Same family snapshot-set boundary |
| Chart / volatility | No separate call | Same actual snapshot set; deterministic derivation later | Stored in supporting context/audit outputs | Snapshot set known by audit | Exact current-run ledger set | Same family snapshot-set boundary |

Persistence after a cutoff is not itself disqualifying when the observation was
already timely. The historical flow relied on that lawful distinction. The
current problem is that acquisition/observation, not merely persistence, was
moved after capture.

## 8. CLEAN-producibility findings

### 8.1 Why 15m is not producible

The shared resolver's strict behavior is correct. It expects exact closing
safety and both current 15m quotes at or before the same zero-allowance boundary
as the closing snapshot. In the current split:

```text
snapshot captured/persisted at window_end_at
-> context source request starts
-> response observed after window_end_at
-> evidence persisted and bound to snapshot
-> resolver rejects late row
```

An already-persisted market/chain row can be reused because those are shared
context rows. Exact snapshot-bound safety and quote rows cannot be produced for
this new closing snapshot by the current lifecycle before the snapshot exists.
The repository contains no active advance acquisition/bind-later owner replacing
the historical path.

### 8.2 Why 1h is not producible

The fixed 1h logical end is the 15m close plus 2700 seconds. The forced snapshot
may be freshness-clean through +60 seconds, but newly observed safety does not
inherit that allowance. Current safety collection starts only after the
snapshot. Even a snapshot captured exactly at the deadline makes the first new
safety observation later than the deadline.

The current overlay binder's lack of a cutoff check can allow identity-valid
late evidence to be attached. That is an enforcement gap, not proof of lawful
producer capability. The audit also found no complete current 1h class-specific
producer/gate for market, chain, quote, flow and chart context, so those classes
cannot be positively certified by this audit.

### 8.3 Why 4h is only conditionally producible

The accepted V2-9.4.6 allowance makes post-capture closing safety and EXIT
acquisition possible in principle, provided all real observation/evaluation
times fit inside +60 seconds. The code uses those real timestamps, so a fast
lawful execution can pass and a slow one must fail honestly.

Broad context is different. Current context execution starts after the closing
snapshot, so its new market/chain response is after `window_end_at` and cannot
count. The only active-factory 4h broad producer outside close is the opening
collection. Market and chain rows have a three-hour freshness contract while
the 1h-to-4h continuation itself spans three hours; because the broad call
precedes the opening snapshot, that opening row is not a dependable timely,
fresh closing row. Although generic market/chain refresh enqueue helpers exist,
the active one-command lifecycle does not enqueue or execute them as an
independent periodic owner. Therefore overall CLEAN depends on an already
persisted, timely, provenance-clean and still-fresh broad row.

## 9. Fixture versus real-producer audit

| Test surface | What it actually does | Classification | Producer capability proven? |
| --- | --- | --- | --- |
| `test_v2_9_4_8_15m_close_ledger_ordering.py::test_observation_one_second_after_15m_end_cannot_satisfy_main_evidence` | Manually inserts source request/response, safety and quote rows at end +1s, then invokes resolver | Resolver proof | No |
| `...::test_timely_context_resolved_after_capture_remains_admissible` | Manually inserts safety, ENTRY and EXIT rows at exactly `window_end_at`, already bound to the fixture closing snapshot | Resolver proof | No |
| `...::test_later_worse_safety_does_not_rewrite_timely_window_truth` | Manually seeds one timely and one later safety row | Resolver proof | No |
| `test_v2_9_4_6_exact_closing_boundary.py` +60 tests | Helpers manually create broad rows, snapshots, safety and quote rows at chosen timestamps, including end or end + allowance | Resolver/boundary proof | No |
| `test_v2_9_8b_lane2_close_phase_split.py` selection/dependency tests | Creates phase rows and synthetic snapshots; exercises exact predecessor and priority logic | Scheduler proof | No |
| `...::test_evidence_executor_captures_only_and_context_cannot_rewrite_capture_time` | Monkeypatches snapshot execution to return a preinserted snapshot and forbids context in evidence | Scheduler/evidence-phase separation proof | No |
| `...::test_partial_context_preserves_durable_evidence_timestamp` | Monkeypatches collector and persistence with synthetic dictionaries; verifies snapshot timestamp is unchanged | Insufficient for producibility | No |
| `test_v2_9_8b_first_hour_safety_provenance_repair.py` ordering assertion | Statically checks the legacy `_execute_continuation_close` text orders collection before snapshot | Historical producer-order proof, not current phase-path proof | No |
| `test_v2_9_8b_post_dtw100_checkpoint4_1h_close_boundary.py` | Supplies synthetic snapshot `captured_at` values at deadline, +61 and +240 to the cadence evaluator | Scheduler/snapshot freshness proof | No context producer proof |

The manually seeded rows are valid for proving that a resolver accepts or
rejects a timestamp. They bypass the real ordering that this audit was asked to
test. No inspected test runs the real governed current context producer after a
real evidence-phase snapshot and demonstrates that every required evidence
timestamp remains inside the applicable cutoff.

## 10. Proven root cause and failure classification

| Finding | Classification | Evidence-based conclusion |
| --- | --- | --- |
| New 15m/1h context acquisition begins only after closing snapshot | **Phase-order design conflict** | Zero/no-context-late authority makes the order structurally incompatible with newly fetched required context. |
| No active pre-capture acquisition/later-binding owner replaces the historical close path | **Missing producer** | `_collect_preclose_context` and `_persist_preclose_context` already separate the operations, but current phase execution invokes both after evidence. |
| Active factory does not enqueue independent market/chain refresh jobs | **Missing producer** | Job kinds and enqueue helpers exist; no production call site in the active factory uses them. |
| 1h overlay binder verifies identity but not the logical evidence cutoff | **Code defect / enforcement gap** | A late exact composite may be bound even though +60 applies only to the snapshot. This does not make evidence lawful. |
| Timing and phase fixtures seed rows or monkeypatch the collector/persister | **Test-only coverage gap** | They prove resolver/Scheduler contracts, not real production acquisition order. |
| 4h safety/quote may finish after +60 because selected sources execute serially | **Truthful source latency** | A late real result must remain late support. The repository supplies no latency guarantee. |
| Provider returns failure, partial, stale, or no holder/quote evidence | **Source/provider limitation or evidence genuinely unavailable**, case-specific | Existing fail-closed handling is correct; scarcity is not a code defect. |

The root cause is not the strict resolver, not Source Governor, not the Central
Scheduler, and not the zero-second 15m rule. It is the current placement of the
only real acquisition owner after a cutoff that its required evidence must
satisfy, plus the absence of another active timely owner.

## 11. Feasible existing-owner design surfaces

This section assesses feasibility only. It does not choose or specify a repair.

| Existing surface | Proven capability relevant to a later design | Constraint that remains |
| --- | --- | --- |
| `_collect_preclose_context` | Already owns all current governed market/chain, safety, holder and Jupiter calls; supports class-specific `include` sets; no independent loop | Any later use must remain Scheduler-led, bounded, Source-Governed and truthful about observation time |
| `_persist_preclose_context` | Already binds previously obtained responses to an exact snapshot id after that id exists | Must retain real source/composite timestamps; binding cannot backdate |
| Historical 15m/1h/4h ordering | Repository proof that pre-capture acquisition plus post-capture exact binding is technically possible with existing owners | A later design must reconcile that fact with the accepted three-phase Scheduler architecture; this audit does not select how |
| Existing exact snapshot evidence phase | Provides the authoritative close snapshot and ledger identity | Must not absorb unrelated slow context in a way that defeats accepted fairness/deadline protection without a separately approved design |
| Existing market/chain recorder and enqueue helpers | Can persist shared governed context and express Scheduler jobs | They are not wired into the active factory; generic existence is not current production capability |
| Existing shared resolver | Can reuse an already-persisted timely row and reject later replacements | It remains read-only and must not fetch, retry, or manufacture evidence |
| Existing 4h opening owner | Lawfully acquires ENTRY and broad opening context before the opening snapshot and binds afterward | Opening broad context is not a dependable fresh closing context after the three-hour continuation |
| Existing cadence/continuation snapshot owners | Produce exact snapshot sets from which flow/chart can be derived | They do not produce safety, quotes, market, or chain evidence |

The following possible later directions are therefore technically feasible for
design analysis, without being selected here:

- reuse of already-scheduled timely safety/quote evidence when exact identity,
  observation time and later binding can be proven;
- governed pre-close acquisition with later exact binding;
- a narrowly bounded Scheduler-owned evidence acquisition surface containing
  only genuinely close-critical classes;
- keeping slow/support context as truthful post-capture support; and
- activating an existing shared-context owner only if its scheduling,
  freshness, budget and active-factory ownership can be proven.

No feasibility finding authorizes implementation.

## 12. Explicit non-solutions

The following are rejected and remain prohibited:

- no timestamp backdating;
- no 15m allowance widening;
- no broad market/chain context widening;
- no treating the 1h forced-snapshot +60s rule as a context allowance;
- no generalizing the 4h +60s exception beyond exact closing snapshot, safety
  composite/contributions and EXIT quote;
- no Central Scheduler bypass or private producer loop;
- no Source Governor bypass;
- no snapshot-id substitution or nearby-snapshot evidence;
- no automatic retry or provider expansion;
- no fixture-seeded timestamp treated as production proof;
- no clean promotion from late, missing, partial, stale, mismatched or
  unsupported required evidence; and
- no reverting the accepted category/fairness or last-actual-capture deadline
  authorities merely to recover the historical monolithic close.

## 13. Functionality risks / setbacks / efficiency blockers

- **15m yield blocker:** the normal current split cannot pass the shared CLEAN
  context gate even when every provider returns valid data, because required
  safety/quote observation times are structurally late.
- **1h false-clean risk:** the first-hour path may bind an identity-correct but
  temporally unlawful safety composite unless the effective authority later
  rejects it. A successful row/promotion is not proof of lawful evidence time.
- **4h yield variability:** serial market, safety, RPC, quote and holder calls
  consume the narrow closing interval; only safety/holder/EXIT have +60s
  authority, while the first broad call cannot count when post-end.
- **Shared-context dependence:** a coincidentally fresh pre-existing market or
  chain row can make a fixture/database pass without proving that this campaign
  produced or scheduled it.
- **Test confidence blocker:** current green boundary tests can conceal the
  producer gap because they choose evidence timestamps directly.
- **Resource-priority constraint:** any later design must preserve AGENTS
  category order and cannot let close context monopolize the worker or source
  budget ahead of open monitoring or token snapshots.

## 14. Exact next permitted action

Because this audit proves the gap, the exact next permitted action is **one
documentation-only design/specification for timely closing-context production
within the accepted Scheduler-owned phase architecture and existing governed
owners**.

That design may compare the feasible surfaces in Section 11 and define a
bounded proof plan. It may not implement code, edit tests, run providers, run a
campaign, mutate the authoritative database, widen a cutoff, add a retry, or
start observability/saturation or Lane 3.

If independent review does not accept this audit, the permitted action is
operator review or a corrected documentation-only audit—not implementation.

## 15. What remains locked

This audit does not unlock or authorize:

- acceptance of the current phase-split or timing-correction implementation;
- observability/saturation implementation;
- Lane 3, Lane 4, Cycle 3, or new campaign progression;
- a live campaign, provider/source call, recovery, retry, cursor action, N2 or
  N7;
- 12h/24h production work or independent 5m main memory;
- a new scheduler, source adapter, provider, retry policy, schema, migration, or
  configuration change;
- retrieval activation;
- paper decisions;
- BUY, SELL, or HOLD;
- paper positions, trade events, paper audits, or PnL;
- live trading, wallets, private keys, signing, transactions, or real funds;
- paid APIs;
- scoring, ranking, confidence percentages, or weighted logic; or
- embeddings or vectors.

Printer remains Solana-only, memecoin-only, paper-trading only, Source-Governed,
Central-Scheduler-led, clean-memory-gated, and fail-closed.

## 16. Static evidence index

The conclusions above are anchored to these current-HEAD owners:

| Repository evidence | Audit use |
| --- | --- |
| `docs/printer-v1-v2-9-8b-multi-token-evidence-deadline-scheduling-design.md`, Section 20 | Accepted per-family and per-class timing authority; meaning of `CLOSE_CONTEXT`; anti-look-ahead law |
| `docs/printer-v1-v2-9-4-8-15m-close-ordering-closeout.md`, ordering sections | Historical pre-close acquisition, later binding, ledger attachment, zero 15m allowance |
| `docs/printer-v1-v2-9-4-6-exact-closing-boundary-closeout.md` | Narrow 4h +60s exact-closing authority and exact blocker semantics |
| `src/printer_v1/operator_cli/close_phases.py` | Exact evidence/context/audit dependency resolution and source-free predecessor lookup |
| `src/printer_v1/operator_cli/one_command_15m_factory.py::_close_phase_plan` | Three Scheduler-owned phase projection |
| `...::_execute_close_evidence_phase` and `...::_execute_snapshot` | Exact governed closing capture, E2M persistence and ledger attachment |
| `...::_execute_close_context_phase` | Family-specific post-capture source acquisition plus persistence |
| `...::_collect_preclose_context` | Actual source call order, Source Governor owner, conditional holder behavior |
| `...::_persist_preclose_context` | Real response/evaluation timestamps and later snapshot binding |
| `...::_execute_close`, `...::_execute_continuation_close`, `...::_execute_long_4h_step` | Historical pre-capture acquisition/later-binding behavior and current 4h opening behavior |
| `src/printer_v1/context_evidence/window_15m.py` | Read-only 15m/4h resolver, exact identity, class cutoffs, shared section CLEAN gate, snapshot-derived flow/chart |
| `src/printer_v1/operator_cli/first_hour_safety_binding.py` | Source-free 1h exact identity binding and absent cutoff validation |
| `src/printer_v1/operator_cli/lane_e2o_1h_window_close.py` | Fixed 1h logical deadline and forced-snapshot lateness facts |
| `src/printer_v1/snapshots/cadence_policy.py` | Existing 1h/4h forced-snapshot freshness bands |
| `src/printer_v1/sources/contracts.py` and `.../governed_execution.py` | Request/response time creation and Source Governor execution ordering |
| `src/printer_v1/operator_cli/e2m_snapshot_persistence.py` | Snapshot `captured_at` from source response `received_at` |
| `src/printer_v1/safety/composite.py` | Underlying contribution times and composite evaluation/persistence |
| `src/printer_v1/paper_quote/jupiter_fixture.py` | Quote evidence time from actual normalized payload/response truth |
| `src/printer_v1/market_regime/lookup.py` and `src/printer_v1/chain_heat/lookup.py` | Three-hour broad-context freshness contract |
| nearest tests listed in Section 9 | Resolver, scheduler, identity and fixture-versus-producer classification |

## 17. Audit closeout

**Pass/fail status:** `FAIL — PRODUCIBILITY GAP PROVEN`.

This is a successful audit result, not an implementation PASS. It proves why
the current unaccepted implementation cannot yet demonstrate lawful CLEAN
production and narrows the next work to design only. No repair is claimed.
