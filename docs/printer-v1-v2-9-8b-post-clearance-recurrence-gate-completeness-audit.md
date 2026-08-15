# Printer V1 V2-9.8B Post-Clearance Recurrence / Zero-State Gate Completeness Audit

Date: 2026-08-15

## Verdict

`V2_9_8B_POST_CLEARANCE_RECURRENCE_GATE_AUDIT_BLOCKED:pre_lifecycle_zero_attempt_provenance_requires_migration_056_absent_from_authoritative_db`

## Boundary

Read-only audit. No DB mutation, no Printer/Scheduler/runtime start, no source
fetch, no memory generation, no campaign, no migration, no
retrieval/decisions/trading activation. No design or patch work in this lane.

## Lane identity

- Baseline / starting HEAD: `11668703419c687247916551d3ecbd506bbc397c`
  (`Record post-authoritative zero-state clearance PASS`)
- Branch: `agent/v2-9-8b-post-clearance-recurrence-gate-audit`
- Final code HEAD: `11668703419c687247916551d3ecbd506bbc397c` — unchanged;
  documentation-only commit.
- Audited from a detached temporary worktree. The user's working repository
  (HEAD `8fbfb088…`) and untracked operator evidence were not altered.
- Authoritative DB observed at sha
  `9d0addd9e2b4859a33d07810cee26ec0893ada3ae884bde740719a4ec20e3b39`,
  migrations `55`, head `055_pre_admission_discovery_attempt_ownership.sql`.

---

## Question 1 — Early Cycle-1 failure

**Classification: `BLOCKER_TO_NEXT_BOUNDED_OPERATION`**

### The repair exists in code

Since the earlier audit, `finalize_four_token_shared_terminal()` gained a third
admitted shape (`four_token_factory_adapter.py:1029`):

```python
elif len(attempt_rows) == 0:
    ...
    admitted_shape = "ONE_CYCLE_PRE_LIFECYCLE_ZERO_ATTEMPT"
```

It requires exactly one row in
`printer_four_token_pre_lifecycle_terminal_provenance` with
`cycle_ordinal = 1`, `proposed_cycle_ordinal = 2`,
`terminal_phase = 'CAMPAIGN_PRE_LIFECYCLE'`, a matching non-empty cycle cause,
and zero windows. So the shape gap identified previously **is** addressed at the
source level.

### But it is inert on the authoritative schema

That provenance table is created by
`migrations/056_four_token_pre_lifecycle_terminal_provenance.sql`. The
authoritative database is at **migration 55, head 055**, and the table is
**absent** (verified directly against `sqlite_master`).

`_validate_pre_lifecycle_zero_attempt_provenance_shape()`
(`four_token_factory_adapter.py:652`) fails closed when the table is missing:

```python
if not _table_exists(
    connection, "printer_four_token_pre_lifecycle_terminal_provenance"
):
    raise FourTokenFactoryAdapterError(
        "pre-lifecycle zero-attempt provenance table is missing"
    )
```

This validator is invoked **early inside** `reconcile_four_token_cycle_terminal()`
(line 789) — after the two-slot check but **before** any scheduler-work
processing, slot transition, or cycle terminalization write.

The factory supplies the triggering argument on exactly the early-failure path
(`one_command_15m_factory.py:7965`):

```python
terminal_phase=(
    "CAMPAIGN_PRE_LIFECYCLE"
    if (str(admitted[0]) == str(cycle_id)
        and not four_token_cycle_one_opening_completed)
    else None
),
```

### Consequence

On the current authoritative DB, a fresh four-token operation that fails in
Cycle 1 before opening completes would pass `terminal_phase =
"CAMPAIGN_PRE_LIFECYCLE"`, hit the missing-table raise inside Phase A, and abort
**before terminalizing anything** — leaving campaign, campaign run, Cycle 1,
supervision, and factory run non-terminal. That is precisely the stranding this
programme has just spent multiple lanes clearing.

### The contradiction that makes this a blocker

The four-token zero-state gate pins the schema that disables the repair
(`four_token_proof_zero_state_gate.py:41`):

```python
REQUIRED_MIGRATION_COUNT = 55
REQUIRED_MIGRATION_HEAD = "055_pre_admission_discovery_attempt_ownership.sql"
```

and fails closed on any mismatch (lines 330, 334). So today:

- at migration 55, the gate admits the proof but the pre-lifecycle repair cannot
  function;
- at migration 56, the repair functions but the gate refuses the proof.

There is no schema at which both hold. Answer to the question as posed: **yes,
an early Cycle-1 failure can still strand ownership.**

### Test evidence

`tests/test_v2_9_8b_shared_terminal_pre_lifecycle_zero_attempt.py:25` pins
`MIGRATION_056 = Path("migrations/056_four_token_pre_lifecycle_terminal_provenance.sql")`
and applies it before exercising the new shape. The repair is only ever proven
on a 56-migration schema — never on the 55-migration schema the authoritative
database and the zero-state gate both require.

---

## Question 2 — Tracking-queue blind spot

**Classification: `NON_BLOCKING_KNOWN_LIMITATION`**

### The blind spot is real and currently occupied

`project_four_token_proof_zero_state()` contains **zero** references to
`printer_tracking_queue` (grep count `0` against
`four_token_proof_zero_state_gate.py`). Its eleven domains cover campaigns,
runs, cycles, campaign scheduler work, campaign and proof supervision, discovery
work, factory runs and steps, pre-admission attempts, and scheduler jobs — not
the tracking queue.

Measured on the authoritative DB right now, with all eleven domains at `0`:

| `queue_status` | rows |
| --- | --- |
| `SKIPPED` | 27 |
| **`QUEUED`** | **17** |
| `COOLDOWN` | 15 |

So the answer to the first half is demonstrably **yes**: 17 non-terminal
`QUEUED` rows coexist with an all-zero eleven-domain projection.

### No mandatory gate catches it

`bounded_readiness_report.py:84` is the only readiness-style owner that inspects
the queue:

```sql
SELECT COUNT(*) FROM printer_tracking_queue
 WHERE queue_status IN ('PENDING','ACTIVE','TRACK_FAST','TRACK_NORMAL')
```

That filter does **not** include `QUEUED`, and returns `0` against the current
database despite the 17 `QUEUED` rows. It is also not invoked from any four-token
gate — grep across `four_token_proof_one_shot_wrapper.py`,
`four_token_proof_zero_state_gate.py`, and `four_token_proof_controller.py`
returns no reference. Answer to the second half: **no mandatory readiness gate
already catches it.**

### Why this is nevertheless not a blocker

The residue is inert with respect to bounded-operation ownership:

- all 17 `QUEUED` rows are **historical**, ids 1–17, created between
  `2026-06-21` and `2026-07-27`; none was created on or after `2026-08-14`;
- they have therefore coexisted with every prior authorized operation on this
  database without blocking one;
- they hold no Scheduler ownership — active or locked Scheduler jobs globally
  are `0`;
- they claim no campaign, run, cycle, supervision, or lease;
- the two queue rows that *were* part of the reconciled execution (58, 59) are
  correctly `SKIPPED`, so the reconciliation itself left no queue residue.

The zero-state contract exists to prove no live *ownership* blocks a bounded
proof. A backlog row in `QUEUED` is not ownership. This is a genuine gate
completeness gap worth recording and eventually closing, but it does not by
itself block the next bounded operation.

---

## Money-usefulness contribution

Prevents the next one-use four-token authorization from being consumed on a
recurrence of the exact stranding just cleared at significant cost. Establishing
that the Cycle-1 repair is inert at migration 55 **before** authorizing anything
is far cheaper than discovering it from a second consumed proof, and it converts
an assumed-closed risk into a precise, testable schema contradiction.

## What remains locked

Four-token proof execution, fresh authorization creation, reuse of any consumed
authorization, six-token proof and capacity widening, 12h/24h activation, source
fetching and discovery, memory generation, Scheduler work creation, campaign
start, retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, paper
audits, PnL, wallets, private keys, signing, live execution, real funds, paid
APIs, scoring/ranking/confidence/weighted logic, embeddings, and vectors.

## Minimum next step (Question 1 is a blocker)

A separate design lane must resolve the schema contradiction between the
zero-state gate's pinned 55/055 requirement and the pre-lifecycle repair's
dependency on the migration-056 provenance table. The decision is whether to
advance the authoritative schema to 56 and re-pin the gate, or to make the
pre-lifecycle provenance path degrade safely when the table is absent. That
decision, its bounded migration/proof evidence, and a fresh readiness review must
all close before any new four-token authorization is prepared.

Question 2 needs no immediate action, but the tracking-queue vocabulary gap
(`QUEUED` covered by neither the zero-state gate nor the
`bounded_readiness_report` filter) should be folded into that same design lane so
the gate's domain list and the queue's real state vocabulary are reconciled once.

No design or patch work was performed in this lane.
