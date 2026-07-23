# Printer V1 V2-9.7E.36-38 Snapshot Maturity Boundary Closeout

## Verdict

`V2_9_7E_36_38_SNAPSHOT_MATURITY_BOUNDARY_PASS`

This PASS means only that another separately authorized canonical
`SNAPSHOT_READINESS` live proof may be considered. No live proof, two-token
pilot, operational memory growth, or later capability is authorized here.

## Baseline and authorization

- Exact starting commit:
  `9922c22771b93df26102a24b7ad92559b4160ad3`.
- The pre-existing untracked operator artifacts were preserved and excluded.
- Live provider calls: `0`.
- Live authorization created or consumed: `0`.
- `SNAPSHOT_READINESS` executions: `0`.
- `FULL_PILOT` executions: `0`.
- Proof databases: isolated temporary fixture databases only.

## Final frozen design

The authoritative maturity fact is the finalized Pump `create` transaction's
integer Unix `block_time`. The authoritative readiness comparison clock is the
injected timezone-aware `evaluated_at`, normalized to UTC.

Central Scheduler owns four categorical states:

- `IMMATURE`
- `DUE`
- `INVALID_ORIGIN_TIME`
- `CANCELLED`

The exact due boundary is `block_time + 900 seconds`. Immediately before is
`IMMATURE`; exactly at and after is `DUE`. Conversion uses
`datetime.fromtimestamp(epoch, tz=timezone.utc)` and fails closed for invalid
epoch shapes.

The canonical runner applies maturity after structural Pump-origin admission
and before holder or snapshot work. Immature, invalid, and cancelled candidates
make zero holder and snapshot calls. If maturity leaves fewer than two
candidates, the existing single-use ledger is persisted, no holder or snapshot
work occurs, cleanup/report/replay completes, and the run closes honestly.
A naturally undersized pool whose admitted candidates are all mature retains
the established `BLOCKED_INSUFFICIENT_ELIGIBLE_POOL` status; maturity-caused
shortage uses `BLOCKED_INSUFFICIENT_MATURE_POOL`.

At least two mature candidates enter the unchanged holder funnel in
deterministic identity order. Holder-eligible candidates then enter the
unchanged E.26 snapshot owner. Maturity permits only an attempt. Completed,
fresh, exact-pool GeckoTerminal 15m OHLCV and exact-window trade evidence remains
the final all-or-nothing readiness gate.

There is no wait loop, sleep, retry, rerun, endpoint rotation, reconnect,
successor, source substitution, acquisition widening, provider-contract change,
or dormant holder-threshold activation.

The fixed arithmetic remains:

- operation ceiling: `45`;
- candidate cap: `3`;
- snapshot reservation: `6` (`2` base plus `4` exact-15m completion);
- authorization: durable single-use.

## Files and owners changed

- `docs/printer-v1-v2-9-7e-36-snapshot-maturity-boundary-design.md`
  freezes E.36 and the Python Builder work gate.
- `src/printer_v1/scheduler/snapshot_maturity.py`
  adds the pure Central-Scheduler categorical maturity policy.
- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
  applies the policy inside the existing canonical `SNAPSHOT_READINESS`
  boundary before holder I/O, enforces the frozen cap of three, reports
  maturity diagnostics, and preserves cleanup/single-use behavior.
- `tests/test_v2_9_7e_36_38_snapshot_maturity_boundary.py`
  supplies the fixture-only integrated E.38 proof.
- This closeout records the bounded result.

No migration, provider adapter, Source Governor, holder owner, snapshot owner,
report/replay owner, lifecycle owner, memory owner, retrieval owner, decision
owner, or financial owner changed.

## Money-usefulness contribution

The boundary prevents scarce holder and snapshot work from being spent on a
candidate that cannot yet have a completed 15-minute history. It makes the
candidate-supply limitation explicit without manufacturing candle evidence or
weakening exact-window requirements. This improves the realism and source
efficiency of a future readiness proof while preserving honest blocked
outcomes.

## What the boundary improves

- Uses the already-authoritative finalized Pump creation time instead of a new
  source or pair-age substitute.
- Makes integer epoch and UTC behavior explicit and testable.
- Stops immature candidates before holder and snapshot provider work.
- Allows two mature candidates to traverse the exact canonical readiness path.
- Separates maturity admission from provider publication/completeness.
- Preserves established undersized-pool status semantics.
- Enforces and reports the frozen candidate cap of three even when current
  operation use would otherwise make a larger dynamic ledger cap appear.
- Preserves deterministic report-only replay, integrity, foreign keys, cleanup,
  single-use refusal, and zero forbidden deltas.

## Offline proof results

Focused proof:

```text
python -m pytest -q -p no:cacheprovider \
  tests/test_v2_9_7e_36_38_snapshot_maturity_boundary.py -x

16 passed, 5 subtests passed
```

Proved:

- immature candidates produced zero holder attempts and zero snapshot calls;
- exact behavior immediately before, at, and after `block_time + 900`;
- integer Pump epoch conversion and UTC-aware output;
- invalid epoch and naive clock refusal;
- two mature candidates produced two complete readiness bundles through the
  canonical dispatcher;
- fewer than two mature candidates closed without holder work;
- missing, unpublished, skipped, partial, malformed, and stale exact-15m
  evidence still blocked after maturity;
- ceiling `45`, cap `3`, and reservation `6` remained unchanged;
- cancellation stopped before holder/snapshot work and cleanup stayed empty;
- the consumed ledger refused a second execution before transport;
- DB-only replay was deterministic and made zero source calls;
- integrity was `ok` and foreign-key violations were zero;
- lifecycle, memory, retrieval, decision, position, trade, audit, and PnL row
  deltas were zero.

Directly affected regressions:

```text
python -m pytest -q -p no:cacheprovider \
  tests/test_v2_9_7e_33_canonical_readiness_boundary.py \
  tests/test_v2_9_7e_26_snapshot_readiness_contract_repair.py \
  tests/test_v2_9_7e_28_readiness_contract_preflight.py \
  tests/test_v2_9_7e_22_holder_reliability_budget_repair.py -x

44 passed
```

Static verification:

- scoped `git diff --check`: PASS;
- implementation imported and exercised through the focused and regression
  suites: PASS;
- no live transport was configured or called: PASS;
- no authoritative/live database was opened by the proof: PASS.

## What remains locked

Another live readiness execution, the full two-token pilot, operational memory
growth, lifecycle creation, clean-memory creation, retrieval, decisions,
BUY/SELL/HOLD, positions, trade events, paper audits, PnL, wallets, private
keys, signing, real funds, live execution, paid APIs, retries, endpoint
rotation, scoring, ranking, confidence percentages, weighted logic, embeddings,
vectors, 12h/24h, V2-10, and later lanes remain locked.

Maturity does not prove GeckoTerminal indexing, publication, continuity,
freshness, completeness, holder eligibility, safety, tradeability, executable
entry/exit, or profit.

## Functionality Risks / Setbacks / Efficiency Blockers

| Item | Effect | Required handling |
|---|---|---|
| Latest Pump candidate diet can still be immature | A future bounded run may close with no holder/snapshot work | Treat as an honest supply outcome; do not retry, wait, widen, or add a source |
| Age is necessary but insufficient | A due pair may still lack published exact evidence | Keep E.26 completed-candle, freshness, identity, and trade-coverage gates final |
| Exact 900-second attempt may precede provider publication | A boundary-due candidate may still block | Do not add a cache/SLA assumption or hidden delay |
| Holder evidence can still be unavailable | Mature candidates may fail before snapshots | Preserve existing source precedence and honest eligible-pool blocker |
| GeckoTerminal may rate-limit or omit fields | Complete bundles may remain below two | Preserve one attempt, zero retry/rotation, and fixed reservation |
| Maturity diagnostics are returned by the terminal readiness result | DB-only replay remains deterministic for durable evidence but does not invent process-only history | Do not reconstruct missing historical maturity facts as observed |
| Single-use authorization is scarce | An external/provider blocker still consumes one future authorized proof | Require all preflight and operator gates below before any run |

## Exact requirements before another live authorization

Another live authorization may be considered only when all of these are true:

1. This PASS checkpoint is committed with the requested message and the tracked
   sprint tree is clean.
2. The operator separately and explicitly authorizes exactly one canonical
   `SNAPSHOT_READINESS` execution with a new durable run/cycle identity.
3. The authorization is not reused from E.34 and is not a `FULL_PILOT`
   authorization.
4. The exact target database and disposable proof/artifact paths are approved;
   no authoritative corpus mutation is implied.
5. The consolidated current source-contract preflight is `READY` in the exact
   executor process, including required secret presence without disclosure.
6. Source Governor and Central Scheduler owners are available; no provider,
   endpoint, header, pacing, request-kind, or evidence-contract drift is open.
7. The printed budget remains exactly ceiling `45`, cap `3`, reservation `6`,
   zero ordinary retries, and single-use.
8. The committed canonical runner is used directly; no temporary harness,
   hidden wait, rerun, retry, endpoint rotation, source substitution, or
   successor is allowed.
9. The run must stop after readiness report, deterministic zero-source replay,
   cleanup, integrity/foreign-key checks, and zero forbidden deltas regardless
   of READY or blocked outcome.
10. A separate operator decision is required after that proof before the full
    two-token pilot can be considered.

## Stop boundary

E.36-38 stops after one logical PASS commit. It does not issue a live command,
create authorization, run readiness, run the full pilot, tag the repository, or
advance to another lane.
