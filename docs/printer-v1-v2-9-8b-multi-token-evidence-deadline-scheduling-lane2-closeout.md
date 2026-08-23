# V2-9.8B Lane 2 — Multi-Token Evidence-Deadline Scheduling Closeout

**Document status:** `CLOSEOUT`

**Date:** 2026-08-23

**Starting implementation/proof HEAD reviewed:** `ae4d5d55abc9486372115a9fb21d976b46f67a54`

**Verdict:** `V2_9_8B_MULTI_TOKEN_EVIDENCE_DEADLINE_SCHEDULING_LANE2_CLOSEOUT_PASS_READY_FOR_LANE3_READINESS_AUDIT`

## Scope

This independent closeout covers Lane 2 only: multi-token evidence-deadline
scheduling, resumable timely pre-close acquisition, closing-phase sequencing,
and final closing-context failure semantics. It performs no runtime operation,
provider call, authoritative database mutation, Lane-3 work, or Cycle-3
activation.

## Accepted architecture and contracts

- Selection remains `eligible due work -> canonical AGENTS/JOB_PRIORITY_ORDER
  category -> phase/deadline inside the winning category -> token/cycle
  fairness -> deterministic tie -> Central Scheduler claim`.
- The canonical active ordering remains `TRACK_FAST > TRACK_NORMAL >
  MEMORY_WINDOW_CLOSE`; cycle ordinal is never permanent priority.
- Each `PRE_CLOSE_CRITICAL` claim performs at most one governed provider
  attempt, durably checkpoints, yields, and returns to global Scheduler
  reselection. Source Governor remains source authority; no bypass worker or
  private source loop exists.
- Closing remains `PRE_CLOSE_CRITICAL -> reselection -> CLOSE_EVIDENCE ->
  reselection -> CLOSE_CONTEXT_BIND -> reselection -> CLOSE_AUDIT`.
- Ordinary `CLOSE_EVIDENCE` deadline is last truthful ACTUAL capture plus
  `dirty_above_gap_seconds`; forced close uses the earlier of that deadline and
  window end plus `closing_clean_late_seconds`. The separate hard block is last
  ACTUAL capture plus `max_clean_snapshot_gap_seconds`. Missing ACTUAL truth is
  `UNKNOWN`; no deadline or CLEAN result is synthesized.
- Evidence-time contracts remain frozen: 15m allowance is zero; 1h +60 applies
  only to forced closing-snapshot freshness; 4h +60 applies only to the exact
  closing snapshot, exact closing safety composite and required contributions,
  and exact closing EXIT quote. Market/chain remain bounded by window end and
  ENTRY retains its original boundary. No backdating or historical CLEAN
  rescue is possible.

## Implementation and proof commits

| Commit | Accepted role |
| --- | --- |
| `2724549c4ec23c59dd5f1086a8f2037435bafe3e` | AGENTS-category Scheduler selection and fairness |
| `64c64435b5509f1836123379f654372f6d8b38bd` | Last-ACTUAL-capture deadline projection |
| `25cbc7b2f56918250aa66e48a052da96c3644f85` | Deadline cadence-provenance correction |
| `7d24bcbb7fdd781f4ac628662d89a65c1621bbd6` | Scheduler-owned close phase split |
| `0b9b0d687eece3084fef9406392371bfabd4d38b` | Frozen post-capture evidence boundaries |
| `514af10ec489860476c970c3669ecf20c274d77e` | Resumable one-unit timely pre-close acquisition and binding |
| `b7e0fdbdaf664510e09df1f26be52e712f371f19` | Removal of unsupported audit-preserving typed technical failure machinery |
| `ae4d5d55abc9486372115a9fb21d976b46f67a54` | Producer-level bounded proof of final closing-context semantics |

The governing audit/design chain is preserved in
`printer-v1-v2-9-8b-multi-token-evidence-deadline-scheduling-design.md`,
`printer-v1-v2-9-8b-timely-closing-context-producibility-audit.md`, and
`printer-v1-v2-9-8b-timely-closing-context-production-design.md`.

## Final failure semantics

A structurally successful `CLOSE_CONTEXT_BIND` may carry complete, partial,
provider-failed, explicitly rejected, unavailable, late, or unknown evidence.
It succeeds operationally, keeps exact `CLOSE_AUDIT` claimable, and leaves CLEAN
eligibility to E2Q.

Identity/provenance mismatch, invariant violation, corrupt or unverifiable
persistence, generic technical `ValueError`, SQLite/database failure, and any
unclassified technical exception roll back context-savepoint writes, preserve
the already-durable exact closing snapshot, fail the context step/job through
ordinary token-local cancellation, and do not preserve dependent
`CLOSE_AUDIT`. No active runtime dependency remains on
`ContextBindingCompositionFailure`, `CONTEXT_BINDING_FAILED`, an exact-failure
validator, a special terminalizer, or failed-context audit acceptance.

## Bounded verification

- Focused Lane-2 regressions: **76 passed** across the close-phase, timely
  pre-close, Scheduler category/fairness, and last-ACTUAL deadline modules.
- Producer proof covers broad market/chain degradation; GoPlus failure and
  explicit rejection; safety composite and holder failure/unknown; Jupiter
  ENTRY/EXIT failure or unavailable route; durable closing snapshots; E2Q
  non-CLEAN outcomes; generic `ValueError`; representative
  `sqlite3.IntegrityError`; historical failed-envelope rejection; provider call
  counts; yielding/reselection; category/fairness; and cutoff/deadline
  preservation.
- The 20 Lane-2-touched production Python files compile from source.
- Removed-symbol production scan: zero matches.
- `git diff --check`: PASS; tracked tree clean before closeout documentation.

No broad full-project suite, live provider run, or authoritative DB mutation
was necessary.

## Known non-blocking residue / baseline debt

- Public-provider failure, lateness, route unavailability, and source scarcity
  can still make a window non-CLEAN. That is expected fail-closed evidence
  truth, not a Lane-2 defect.
- The existing 1h path does not yet define a complete shared per-class context
  gate beyond the Lane-2 mandatory safety/holder timing repair. Any expansion
  requires later explicit authority; Lane 2 does not infer it.
- A technical context failure truthfully leaves a durable capture without a
  completed close audit. Existing reporting/recovery policy owns that
  capture-only residue; Lane 2 does not invent audit preservation or recovery.
- Observability/saturation expansion and Cycle 3 remain locked for later
  explicitly approved work.

## Locks preserved

Printer remains Solana-only, Solana-memecoin-only, paper-only,
Source-Governed, Central-Scheduler-led, and clean-memory-gated. Retrieval,
BUY/SELL/HOLD, paper positions, trade events, paper audits, PnL, live execution,
wallet/private-key/signing logic, paid APIs, scoring/ranking/confidence/weighted
logic, embeddings/vectors, 12h/24h production, independent 5m main memory, and
Cycle 3 remain locked.

## Next permitted lane

Lane 2 is **CLOSED PASS** with no remaining Lane-2 blocker. The next permitted
action is only:

```text
LANE 3:
Post-1H Standard-4H Progression + Fault Preservation
AUDIT/READINESS ONLY.
```

This closeout does not authorize Lane-3 design or implementation.
