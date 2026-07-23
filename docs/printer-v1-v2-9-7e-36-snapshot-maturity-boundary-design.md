# Printer V1 V2-9.7E.36 Snapshot Maturity Boundary Design

## Frozen implementation contract

This design closes the E.35 `DESIGN_GAP` through the existing canonical
`SNAPSHOT_READINESS` owner only.

- The authoritative maturity fact is the finalized Pump `create` transaction's
  integer Unix `block_time`. The authoritative comparison clock is the
  readiness execution's injected, timezone-aware `evaluated_at`, normalized to
  UTC. GeckoTerminal `pair_created_at` remains pair context and is not a
  pre-request maturity authority.
- Central Scheduler owns the pure maturity policy. Its only categorical states
  are `IMMATURE`, `DUE`, `INVALID_ORIGIN_TIME`, and `CANCELLED`.
- The due boundary is exactly `block_time + 900 seconds`. Immediately before
  that instant is `IMMATURE`; at and after it is `DUE`. Integer epochs are
  converted with `datetime.fromtimestamp(..., tz=timezone.utc)`. Boolean,
  non-integer, non-positive, naive-clock, and otherwise invalid values fail
  closed as `INVALID_ORIGIN_TIME` or a contract error.
- The canonical readiness runner applies this zero-source policy after bounded
  Pump acquisition and structural candidate admission, and before holder or
  snapshot work. Immature, invalid, and cancelled candidates cause zero holder
  and zero snapshot provider calls.
- Holder-first ordering is not necessary. If fewer than two candidates are
  `DUE`, the runner persists the existing single-use operation ledger, performs
  no holder or snapshot calls, cleans up, reports
  `BLOCKED_INSUFFICIENT_MATURE_POOL` (or `CANCELLED`), and stops.
- If at least two candidates are `DUE`, those candidates enter the unchanged
  holder funnel in deterministic identity order. Holder-eligible candidates
  then enter the unchanged readiness snapshot owner. There is no retry, rerun,
  sleep, hidden waiting, endpoint rotation, successor, source substitution, or
  additional acquisition.
- Maturity permits one readiness attempt only. It never asserts provider
  publication, interval continuity, evidence freshness, snapshot completeness,
  or readiness. Missing, skipped, partial, stale, malformed, mismatched, or
  unpublished exact-15m GeckoTerminal evidence remains blocking under the
  existing snapshot contract.
- The operation ceiling remains `45`, the derived candidate cap remains `3`,
  the snapshot reservation remains `6`, and the durable authorization remains
  single-use. Unused reservation cannot become more candidates or calls.
- The readiness mode continues to bypass lifecycle and memory owners entirely.
  Retrieval, decisions, BUY/SELL/HOLD, positions, trade events, paper audits,
  PnL, wallets, signing, funds, and live execution remain unreachable.

## Python Builder Guide work gate

- Baseline: `9922c22771b93df26102a24b7ad92559b4160ad3`; pre-existing untracked
  operator artifacts are outside the sprint and remain untouched.
- Active work: V2-9.7E.36-38 design, narrow implementation, offline proof, and
  closeout only.
- Primary classification: `MISSING_APPROVED_IMPLEMENTATION_BOUNDARY`, following
  E.35's completed `DESIGN_GAP` audit and this frozen design.
- Canonical owners changed: Central Scheduler maturity policy and the canonical
  readiness runner's pre-holder admission boundary.
- Expected production files: one scheduler policy module and the existing
  authoritative readiness runner. No provider, holder, snapshot, migration,
  database, lifecycle, memory, retrieval, decision, or financial owner changes.
- Database boundary: isolated migrated fixture databases only; no authoritative
  or live database mutation.
- Minimum proof: exact boundary/UTC unit cases plus canonical two-bundle,
  insufficient-mature, evidence-failure, single-use, cancellation/cleanup,
  deterministic replay, integrity/foreign-key, budget, and zero-forbidden-delta
  cases; then only directly affected readiness regressions.
- Stop condition: the first relevant failure, any need to alter a provider
  contract/schema/budget, any source or Scheduler bypass, or any lifecycle,
  memory, retrieval, decision, or financial reachability.

## Compatibility decision

The design is compatible with the adopted Pump, GeckoTerminal, Source Governor,
Central Scheduler, E.33 canonical runner, E.22 holder, and E.26 snapshot
contracts. It deliberately does not enable the dormant holder-maturation
threshold, because that threshold owns a different pre-activation concern and
does not establish snapshot maturity.
