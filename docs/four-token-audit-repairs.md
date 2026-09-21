# Four-token audit repairs — 2026-09-21

The post-audit user request authorizes engineering repairs, using disposable state
and offline adapters only. No operational or historical state is changed.

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

This closes the misleading clean-memory coverage claim, but does **not** close
the full acquisition-to-report proof gap. Candidate/selection and later-cycle
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

## Smallest remaining complete-proof design

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
variants and require truthful blockage. This composed proof remains pending;
the current repair does not claim it exists.

## Safety

For this repair task: authoritative DB writes = 0; operational Printer launches =
0; provider/RPC/WebSocket attempts = 0; operational Scheduler executions = 0;
operational authorizations created = 0; operational authorizations consumed = 0;
historical campaigns retried/resumed/restarted = 0. Tests use disposable SQLite
and offline fixtures under the development network guard. Historical incident
evidence and the earlier recorded provider attempt are not rewritten by these
task-local counters.
