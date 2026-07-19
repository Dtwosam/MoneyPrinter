# V2-9.7D.6B.7 Zero-Source Read-Only Replay Closeout

## Scope

This lane adds deterministic verification of one completed terminal campaign
report. Replay uses only persisted campaign facts and opens SQLite through URI
`mode=ro` with `PRAGMA query_only=ON`. It creates no replay row and exposes no
command, source, scheduler, runtime, lifecycle, retrieval, or financial path.

## Money-Usefulness Contribution

Read-only replay makes terminal campaign evidence independently checkable
without contaminating the corpus, spending source budget, scheduling work, or
reconstructing favorable outcomes with hindsight. This improves confidence in
whether stored clean/dirty outcomes, safety context, lifecycle cleanup, and
opportunity gaps are the facts that originally produced the report.

## What 6B.7 Improves

- Exact campaign, configuration, report, run, hash, and immutable object-link
  isolation is enforced.
- Canonical report bytes and stored B.5 launch provenance are validated before
  deterministic diagnostics are recomputed through the 6B.6 assembler.
- Unknowns, evidence gaps, and independent full-window/opportunity outcomes are
  returned unchanged from authoritative stored facts.
- Every result records zero source calls, scheduler work, memory writes, and DB
  writes plus before/after database SHA-256, all-table counts, and
  `total_changes=0`.
- Blocked replay returns exact in-memory reasons and never persists a replay
  status.

## Remaining Locks

Source fetching, scheduler/runtime execution, lifecycle execution, memory
creation, persistent-target migration, retrieval, decisions, positions,
trades, audits, PnL, and all live financial capabilities remain locked. Replay
does not repair incomplete historical reports and does not recapture Git state.

## Proof Completed

- A valid report verifies deterministically on repeated replay.
- Malformed expected hashes, mismatched hashes, noncanonical payloads, and
  campaign/configuration/report mismatches block with exact reasons.
- Stored provenance mismatch and missing immutable object links block.
- Visible unknowns/gaps and independent 5C outcome layers remain unchanged.
- Git capture, the legacy report loader, and the replay persistence writer are
  guarded as unavailable entry points in focused proof.
- Disposable database bytes, all-table row counts, and `total_changes` remain
  unchanged; no replay or locked-capability row is created.

## Functionality Risks / Setbacks / Efficiency Blockers

- Replay intentionally blocks reports that predate the complete 6B.6 envelope
  or lack exact 4A-5C object links; it does not infer missing facts.
- Whole-file hashing assumes a quiescent terminal database. External writers
  cause a hash mismatch and fail closed rather than yielding a verified replay.
- Recomputing B.1-B.5 diagnostics and counting every table favors audit rigor
  over speed. This lane is a bounded terminal verification path, not runtime.

## Stop Boundary

V2-9.7D.6B.7 ends here. V2-9.7D.6B.8 integration proof is not started.
