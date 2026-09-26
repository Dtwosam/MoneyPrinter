# Four-token audit repairs — 2026-09-21

The post-audit user request authorizes engineering repairs, using disposable state
and offline adapters only. No operational or historical state is changed.

Final repair result (2026-09-26): all reproduced blockers below are repaired. The
fresh raw public-composition regression passed, including canonical acceptance
and immutable replay. Remaining coverage limits are stated at the end.

## F-01 — P1: lane-specific acceptance

The final gate required an aggregate 16 non-close snapshots, rejecting valid FAST
and mixed lanes. The replacement reads the authoritative frozen-lane cadence:
8 NORMAL or 15 FAST non-close snapshots per token. Expected, planned and actual
counts must each match; require complete coverage, zero missing observations and
one succeeded close. The selected and cadence lanes must agree. A missing snapshot
on one token cannot be hidden by an extra snapshot on another.

The initial regression reproduced 20 failures and nine passes before repair.
Focused cadence plus durable finalizer tests passed (51 tests, six subtests).
Related accounting, SQLite attribution and lease-contention verification passed
(123 tests, six subtests). Durable tests seed terminal evidence and do not claim
natural acquisition or memory-production coverage. Diff review confirmed the
change is confined to acceptance; no cadence, budget or execution policy changed.

## F-03 — P3: standalone reader-contention regression

The heartbeat reader-contention test now uses the package-qualified sibling
import. Default `python -m pytest` no longer depends on adding `tests` to
PYTHONPATH. The actual disposable held-reader COMMIT regression passes as part
of the 123-test verification above. This changes no heartbeat runtime behavior.

## F-02 — P3: misleading integration scope and bypassed producers

The legacy case is now explicitly labeled orchestration coverage. A separate
natural-memory case removes injected clean promotion, safety persistence,
Scheduler projection, support capture, opening planning and healthy admission
results. It uses the real admission-health projector and real lease renewals on
a deterministic clock. All lease readers share that clock. Its first-hour
continuation uses the production 2,700-second span following 15 minutes, instead
of the old fixture's extra 3,600 seconds that synthetic promotion had concealed.

The natural-memory case passed in 321.33 seconds: four distinct tokens across
two cycles, real 15m/1h/4h memory producers, four clean 4H episode/fingerprint
pairs, exact lane/provenance assertions, one consumed later-cycle attempt,
terminal campaign/factory, released supervision lease and zero active/locked
Scheduler or owned work. Locked decision/trading and 12H/24H surfaces stay empty.

This intermediate test closed the misleading clean-memory coverage claim, but
did not close the full acquisition-to-report proof gap. Candidate/selection and later-cycle
source evidence are still prevalidated fixtures. Nomination, holder acquisition,
complete six-unit accounting and canonical report acceptance have focused tests,
but are not all composed in this case. No passing memory result is represented
as full operational readiness. Historical lock-holder attribution stays NOT PROVEN.

## F-04 — P1: campaign identity absent when 4H quality reads it

The natural-memory integration produced four physical 4H closes with complete
cadence and clean candidate data, but no clean 4H episodes. Lane-Q blocked each
with `CAMPAIGN_WINDOW_BINDING_MISSING`; strict campaign completion then rejected
the missing promoted memory. The legacy fixture concealed this by promoting
memory itself.

Both `_audit_4h_close_from_evidence` and `_execute_long_4h_step` committed the
physical row and ran independent quality readers before linking the physical row
to the owned campaign window. Those readers need that exact link to determine
the frozen lane. The repair binds through the existing one-shot ownership writer
immediately after physical prerequisites commit, before the independent reader.
It requires the exact job-owned window to be CLOSE_PENDING. Token, pair and kind
must match; an existing different binding fails. Standalone windows retain their
existing path. No success state, clean label or episode is created by this bind.

The normal quality pipeline and terminal reconciliation remain responsible for
promotion and success. A crash after binding leaves committed physical evidence
and a nonterminal window; it does not manufacture a completed close or permit an
operational retry. The binding transaction ends before quality readers run.

Focused regressions verify separate-connection visibility, no premature success,
same-binding idempotence, wrong-token rejection and CLOSE_PENDING enforcement.
Related close/terminal fixtures were stale: they referenced retired unsplit close
steps, counted context/audit work as observations, or lacked columns now read by
the production accounting reader. Updating these fixtures yielded 25 passing
focused tests. The larger natural-memory integration also passed as recorded
above. Diff review checked both close entry points, exact job/window ownership,
transaction completion before independent readers, terminal ordering and
unchanged standalone behavior.

Final related verification: 28 close/orchestration tests passed; the natural
case passed separately; 12 binding/wake-order tests passed; standalone SQLite
attribution passed 46 tests. Compile and whitespace checks passed. The test
reader used for the durability assertion is explicitly closed.

## Raw public-composition proof design

Extend the existing disposable public-composition proof boundary, rather than
reimplementing the coordinator. Use its approved offline runtime-builder registry
to supply raw origin, market, protocol-account and holder responses for four fixed
identities, plus deterministic clock/renewal adapters. Bind every authorization
test helper to the temporary DB before use. Preserve the production coordinator's
stage observers, cycle owner registry and action-local ledger from acquisition
through lifecycle finalization; never reconstruct missing measurements afterward.

Reuse this natural-memory lifecycle and terminal assertion set. Require the
canonical finalizer to accept both registered cycle owners, reconcile all six
measured units, persist CAMPAIGN_PASS and replay the immutable report without new
writes. Remove one required source/holder/accounting fact in focused negative
variants and require truthful blockage. The following sections record the
implementation and defects exposed by composing this path.

## Safety

For this repair task: authoritative DB writes = 0; operational Printer launches =
0; provider/RPC/WebSocket attempts = 0; operational Scheduler executions = 0;
operational authorizations created = 0; operational authorizations consumed = 0;
historical campaigns retried/resumed/restarted = 0. Tests use disposable SQLite
and offline fixtures under the development network guard. Historical incident
evidence and the earlier recorded provider attempt are not rewritten by these
task-local counters.

## Public-composition capability boundary

Reusing the existing raw four-identity C8 fixture exposed two development
composition gaps: its materializer omitted the already-implemented protocol
account-batch transport, and admission/4H runtime checks only accepted operational
DB bindings despite the public Standard-4H entry accepting disposable proofs.
The fixture also supplied conflicting venue labels across providers; that
identity conflict was correctly rejected and is not a production defect.

Design: forward the existing marked account-batch transport through the supply
facade to Source Governor. For runtime DB checks only, accept the existing typed
disposable capability against the independently persisted configuration
expectation. Preserve exact path, target, campaign/run/root-cycle/configuration,
manifest, version and non-reuse/provider prohibitions. Canonical authoritative
paths remain forbidden. Operational invocation and authorization validators stay
separate and unchanged. Shared Cycle-2 scope still requires the existing exact
admitted-cycle loader. No operational authority is synthesized for development.

The new binding regression was red (12 failed, one passed); 19 focused binding
and materialization checks passed after implementation. The final binding
regression also covers schema versions, another DB path and forbidden authority facts.

## F-05 — P1: cooperative discovery drops prior stage reports

The raw public proof exposed a production handoff defect after Cycle-2 nomination.
Fresh pools were protocol-confirmed and measured coverage survived each Scheduler
yield, but the separate stage-reported request list did not. The freeze reader
therefore saw durable and manifest IDs 19–22 with an empty stage-reported set and
correctly blocked with `DURABLE_REQUEST_NOT_STAGE_REPORTED`. The acquisition
subsequently ended as NO_PAIR/DURATION_EXHAUSTION despite available fresh evidence.

The repair carries explicit prior stage reports alongside, independently of,
measured coverage through the existing supply facade and attempt-local progress.
The existing reconciliation still checks both against durable request scope and
transport identities. No IDs are inferred from coverage or reconstructed from
SQLite; no source is repeated and no budget is increased. Reports are carried
only within the same owned cooperative attempt, not across operational reruns.

A disposable zero-work resumed-quantum regression verifies successful reconciliation
with both records present, and blockage when either record is missing. The raw
proof now reaches Cycle-2 admission with two fresh candidates. Related discovery,
replay, freeze and post-holder regressions passed (33 tests; legacy post-holder
fixtures require `PYTHONPATH=src:tests`). Subsequent terminal defects are
recorded below.

## F-06 — P1: terminal cycle accounting runs before stage sealing

The raw four-token run produced all 12 clean episodes and terminal zero-state,
but correctly failed acceptance. Per-cycle owner reconciliation ran before the
finalizer sealed the lifecycle stages, and lifecycle sealing covered only the
primary cycle. Both registered owners therefore lacked mandatory slot stages at
the point of comparison. The finalizer now seals each admitted cycle using its
exact owned factory-step IDs, ingests through the explicit registry-owned mutable
cycle owner, refreshes the read-only campaign projection, then reconciles each
cycle and the aggregate. Stage evidence still comes from durable execution-time
measurements; missing measurements cannot be manufactured by this boundary.

## F-07 — P1: pre-close yields overwrite validation occurrence history

A pre-close Scheduler job executes several separately claimed source units. Each
claim emitted the same three validation identities, then overwrote the prior
claim's durable validation list. The action-local ledger correctly detected the
repeated identities, while the owner could see only the final claim's records.
The repair retains every previously committed occurrence and appends new
occurrences with the next ordinal within the same job. The observer receives only
the current claim's records. Foreign, reordered or duplicate prior identities
fail closed; no deduplication or retrospective evidence reconstruction is used.
This is an occurrence identity correction grounded in actual Scheduler claims,
not a change to source-request or token identity. Focused history and pre-close
acquisition regressions passed (32 tests).

The same terminal trace exposed missing Cycle-2 discovery/selection accounting:
only Cycle 1 emitted `DISCOVERY_SELECTION_SCHEDULER`. The existing lifecycle
observer now forwards the second cycle's actual consumed-pair handoff to its exact
registered owner. Capture requires one consumed attempt, its succeeded Scheduler
job and two exact slots; it performs no new work and cannot manufacture absent
selection evidence. Three focused handoff tests pass. The bounded two-cycle reader
fixtures now seed explicit selection batch and consumed-attempt provenance, rather
than expecting terminal slots alone to prove selection; all 23 fixture tests pass.

## F-08 — P1: measured discovery/holder transports lose cycle ownership

After slot sealing and validation-history repair, reservation, Scheduler and
validation identity sets matched. Transport sets still differed: generic discovery
stage names did not encode a cycle, so action-local per-cycle slicing dropped
those measured calls. Cycle-2 holder calls were observed but their sealer was
explicitly disabled, leaving two calls without owner evidence.

The measurement callback now carries explicit cycle provenance alongside the
unchanged canonical transport identity. Registered-cycle validation occurs at
capture; cycle-bearing stage identities cannot contradict this provenance.
Per-cycle comparison includes these explicitly attributed records. A duplicate
within one cycle remains an error; identical lawful request shapes in separate
cycles retain separate occurrences and the existing aggregate multiset rules.
The Cycle-2 holder boundary uses the existing strict sealer, resolved to its exact
registered cycle owner. No source request is repeated or reconstructed.

Focused capture/partition/duplicate and existing per-cycle ownership regressions
passed (15 tests). The next raw proof confirmed exact per-cycle six-unit
equality, then exposed F-09.

## F-09 — P1: four-hour report reader rejects lawful terminal disposition

The fully measured raw proof reconciled both cycles and all six units, yet its
terminal reader rejected all four slots as `token_slot_not_window_4h_closed:COOLDOWN`.
Unified terminal closure legitimately moves a completed slot from
`WINDOW_4H_CLOSED` into `COOLDOWN`; archival can subsequently move it to `ARCHIVED`.
The cycle accounting reader already recognizes those later terminal states, but
the four-hour validator it calls accepted only the intermediate closed state.

The validator now accepts those two terminal dispositions while retaining every
exact eligible-subset, window, physical memory, clean-object, cadence and Scheduler
ownership check. No state is changed or promoted by this reader. Two focused
positive regressions failed before repair; both pass afterward, and missing-close
negative cases still fail. The related eligible-subset group passed 12 tests.
Reading the failed disposable proof with the repaired reader yields both cycles
complete and `TERMINAL_SUCCESS`, without changing its immutable failed report.
The next fresh raw proof established canonical acceptance, then exposed the
artifact mutation described in F-10.

## Focused verification for the raw-proof extension

On 2026-09-26, the final focused groups passed:

- 68 tests: cooperative stage-report handoff; disposable runtime binding;
  multi-cycle accounting handoffs; pre-close validation history; bounded terminal
  accounting; disposable factory preflight; raw fixture materialization.
- 27 tests: cycle-scoped capacity/accounting, cycle adapter and later-cycle
  accounting failure domain. Two stale fixtures were repaired: exact queue
  ownership is now supplied, and the over-capacity case exceeds the current
  derived ceiling rather than an obsolete literal. Production budgets did not change.
- 12 tests: lawful post-four-hour terminal disposition and exact eligible-subset
  validation, including missing owned-close rejection and honest dirty outcomes.

Diff review checked runtime capability separation, exact per-cycle mutable owner
resolution, observation at the consumed selection boundary, independent prior
coverage/report handoff, append-only validation occurrence history, duplicate
rejection, and post-close disposition without memory promotion. Compilation and
`git diff --check` passed. These checks do not exercise providers or authoritative
operational state.

## Repair locations and regressions

| Finding | Production boundary | Smallest regression |
| --- | --- | --- |
| F-05 | `discovery/eligible_token_supply.py::run_persistent_eligible_token_supply`, `operator_cli/authoritative_live_operational_campaign.py::production_later_supply` | `tests/test_cooperative_stage_report_handoff.py` |
| F-06 | `operator_cli/campaign_full_run_accounting.py::finalize_full_run_ownership_and_report`; `operator_cli/one_command_15m_factory.py::_observe_consumed_cycle_selection` | `tests/test_multi_cycle_accounting_handoffs.py`, raw public completion |
| F-07 | `operator_cli/one_command_15m_factory.py::_prior_preclose_validation_records` and the factory validation observer | `tests/test_preclose_validation_history.py` |
| F-08 | `sources/campaign_six_unit_accounting.py::CampaignActionLocalLedger`, public command transport observer/holder sealer, later-cycle acquisition callback | `tests/test_multi_cycle_accounting_handoffs.py`, raw public completion |
| F-09 | `operator_cli/one_command_15m_factory.py::_standard_campaign_four_hour_terminal_validation` | `tests/test_four_hour_terminal_disposition.py` |

Production paths above are relative to `src/printer_v1/`. F-05 requires cooperative
acquisition spanning multiple Scheduler claims. F-06/F-08 require two admitted
cycles and canonical terminal accounting. F-07 requires multiple pre-close source
claims for one job. F-09 requires reporting after shared terminal disposition.
Each defect can block truthful completion/report acceptance while leaving real
source or memory evidence present. Earlier tests supplied completed evidence,
synthetic promotions, or intermediate close states and therefore skipped the
failing handoff; the raw proof composes those boundaries without such substitutions.

## F-10 — P2: report replay appends to terminal attribution evidence

The raw proof reached canonical `CAMPAIGN_PASS`, all 12 clean objects and exact
per-cycle accounting, then failed its final artifact-byte comparison. The
report-only reader in `operator_cli/unified_terminal_closure.py::replay_campaign_terminal_report`
used `connect_attributed`; a still-registered terminal campaign timeline appended
new read events to `sqlite-writer-attribution.json`. SQLite and the canonical report
were unchanged, but the promised immutable replay mutated a diagnostic artifact.
Earlier replay tests checked DB writes and report rows without an active timeline.

Only this immutable replay connection now uses plain SQLite `mode=ro`. Operational
readers retain attribution, and replay does not disable or replace the process-wide
timeline. The existing bounded report-only test now activates attribution and
checks exact diagnostic bytes plus unchanged active-timeline identity. It failed
before the repair and passes after it. This is a bounded evidence/replay defect,
not a repair to or inference about the historical lock holder.

## Scope of the composed proof

`tests/test_four_token_public_offline_completion.py` uses the existing marked raw
transport registry, a lawful empty finalized-migration page, market nomination,
consistent PumpSwap venue identities, and real governed protocol-account/holder
validation. Two candidates are available initially; two distinct candidates
arrive before Cycle-2 admission. Time and lease-renewal scheduling are deterministic;
real lifecycle, quality, persistence, accounting and report owners run unchanged.
The test supplies no clean-memory promotion or terminal success result. A temporary
local Git clone contains the exact tracked development source for real preflight.

The proof covers this complete offline nomination branch and the canonical
accounting contract. It does not prove every provider/migration branch, every
crash or SQLite concurrency interleaving, or operational readiness. Historical
lock-holder attribution remains NOT PROVEN, and historical missing accounting
stays missing. There is no new permission to launch, retry, resume or clean up an
operational campaign.


## Final composed verification — 2026-09-26

`.venv/bin/python -m pytest -q tests/test_four_token_public_offline_completion.py`
passed: **1 passed in 535.91 seconds**. This fresh disposable run includes every
repair above and verifies:

- four distinct tokens, two admitted cycles and one consumed later-cycle attempt;
- 12 CLEAN_MEMORY episodes, four each at 15m/1h/4h, with one canonical fingerprint each;
- canonical CAMPAIGN_PASS, complete terminal accounting and exact six-unit equality
  for both cycles;
- terminal supervision, released lease and zero active/locked owned work;
- no 12H/24H, retrieval, decision, position or trade records;
- REPORT_ONLY_COMPLETE with zero source calls, Scheduler runtime calls or DB writes,
  plus byte-identical DB and every artifact before/after replay.

After the replay repair, the terminal-accounting and SQLite-attribution group
passed **69 tests** (23 terminal tests overlap the earlier 68-test group).
The earlier 27- and 12-test groups remain passing; no runtime source changed
outside replay afterward. Final compilation, whitespace checks and actual diff
review passed. The test runs under the development network guard. All seven
safety counters recorded above remain zero. These results close the reproduced
engineering blockers; they do not erase the scope limits or historical unknowns.
