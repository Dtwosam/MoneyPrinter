# V2-9.7D.6B.1 Ownership and Schema Reconciliation Closeout

## Result

V2-9.7D.6B.1 adds a campaign-rooted persistence graph on top of migration 031
and a narrow transactional state writer. Verification used disposable database
files only. The operational target was not opened or migrated.

## Money-Usefulness Contribution

The graph makes later campaign evidence attributable to one exact campaign,
run, cycle, token slot, token, mint, pair, lifecycle, window, and scheduler work
identity. This prevents promotion, safety, continuation, manipulation, and
opportunity evidence from being mixed across tokens or reconstructed with
hindsight. It improves the trustworthiness of later memory-yield reporting; it
does not create memory or authorize a financial action.

## What 6B.1 Improves

- Migration 031 remains the campaign root and now owns run, cycle, exactly-two-
  slot, window, scheduler-work, immutable object, and report-object links.
- String campaign identities are stored beside exact integer token, pair,
  memory-window, scheduler-job, source-provenance, episode, safety-composite,
  lifecycle-event, and proof-supervision foreign keys where applicable.
- Composite foreign keys and validation triggers reject cross-campaign,
  cross-cycle, cross-token, cross-pair, support/main, and predecessor mistakes.
- 4A-5C payloads use sorted, compact, finite canonical JSON and SHA-256 identity;
  their rows and report links are immutable.
- Transactional compare-and-update transitions preserve expected state,
  immutable first terminal cause, terminal time, and idempotent repeated
  terminalization. Campaign/run transitions reuse the committed 3A map.
- B.1 promotion, B.2 safety, B.3 lifecycle, B.4 supervision, and B.5 launch
  provenance remain semantic owners. This lane stores references only.

## What Remains Locked

Backup/restore, B.1/B.2 adapters, lifecycle reconciliation and rotation,
operational lease/runtime, source collection, memory generation, final report
assembly, replay, retrieval, decisions, BUY/SELL/HOLD, positions, trades,
audits, PnL, wallets, signing, and live execution remain locked. No operational
campaign command is available.

## Proof Completed

- all migrations apply cleanly to an isolated current-schema database;
- campaign/run/cycle/two-slot/window/work foreign keys survive close and reopen;
- exact token/mint/pair and existing integer-row mappings are enforced;
- a cycle requires slot ordinals 1 and 2, atomically, before it can advance;
- valid state transitions compare-and-update transactionally;
- repeated identical terminalization is idempotent, while later cause/state
  changes fail closed;
- token/pair and predecessor mismatches roll back without partial cycle rows;
- canonical object evaluation is deterministic and immutable;
- pre-existing token, pair, and memory-window rows remain unchanged;
- foreign-key checks pass after reopen; and
- retrieval and financial capability tables remain at zero rows.

## Functionality Risks / Setbacks / Efficiency Blockers

- Migration 028 remains proof-only. The campaign-run row therefore carries an
  optional exact authoritative-run foreign key rather than duplicating or
  relaxing the proof ledger. B.1/B.3 adapters remain required in later lanes.
- Migration 030 remains proof supervision. Its optional reference is evidence
  linkage only and is not an operational lease.
- Existing source-failure rows do not carry a source-request foreign key. This
  schema can require the campaign work's request identity but cannot infer a
  stronger relationship that the authoritative source schema does not store.
- An incomplete cycle may transiently exist with fewer than two slots inside a
  rolled-back transaction. The public writer creates both slots atomically, and
  the database blocks leaving `PLANNED` unless exactly two rows exist.
- Full normalized persistence of every 4A-5C field was intentionally avoided.
  Queryable ownership fields are indexed; object details remain canonical JSON
  to limit schema breadth and prevent parallel semantic ownership.

## Scope Confirmation

No persistent target, backup, source, scheduler runtime, lifecycle action,
memory row, command surface, replay, or locked-capability row was created or
modified. V2-9.7D.6B.2 and later Slice 6 lanes were not started.
