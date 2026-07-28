# Printer V1 V2-9.8B — Operational Selective WINDOW_1H Operator Readiness Closeout

## Final verdict

```text
V2_9_8B_OPERATIONAL_SELECTIVE_1H_OPERATOR_READY
```

This manual review confirms readiness for a separately authorized, exactly-one
bounded operational selective `WINDOW_1H` proof.

It does not authorize or run that proof and does not unlock 4h, retrieval,
paper decisions, positions, trades, audits, or PnL.

## Baseline

- Implementation HEAD before this closeout:
  `098048c3371196e6535b44bbad84d6cd55583ff6`
- Branch: `master`
- Canonical wrapper:
  `scripts/Start-PrinterV1-MemoryFactory.ps1`
- Canonical proof mode:
  `selective-1h-proof`
- Normal `run` remains 15m-only with
  `selective_1h_continuation=False`.

## Command readiness

The canonical command surface provides:

- `selective-1h-preflight`
- `selective-1h-proof`

The proof mode:

- requires explicit operator approval;
- reuses the existing operational campaign owner;
- sets `selective_1h_continuation=True`;
- keeps `continuous_four_hour=False`;
- supports zero, one, or two categorical continuations;
- creates exactly one campaign and one cycle;
- creates no automatic retry, restart, resume, or successor.

No parallel runner exists.

## Migration 047 readiness and application

Migration:

`047_campaign_oneshot_linkage_binds.sql`

Before authoritative application, the repository-owned backup and disposable
restore rehearsal passed:

- source DB integrity: `ok`
- source foreign-key violations: `0`
- source migration count before application: `46`
- disposable restore migration count: `47`
- disposable restore latest migration:
  `047_campaign_oneshot_linkage_binds.sql`
- disposable restore runtime schema: ready
- critical row counts unchanged
- authoritative source unchanged during rehearsal

Migration 047 was then applied separately to the authoritative database.

Post-application state:

- migration count: `47`
- latest migration:
  `047_campaign_oneshot_linkage_binds.sql`
- integrity: `ok`
- foreign-key violations: `0`
- critical row counts unchanged
- authoritative DB SHA-256:
  `a241247a756e5dc3880fa42408b2cb73d580fd11767bb591136d8be7c2cafff7`

## Rollback anchor

Verified migration-046 backup:

`/Users/Dtwo1/PrinterV1OperatorReadiness/selective-1h-20260728T165835Z/printer_v1.pre-migration-047.backup.sqlite3`

SHA-256:

`1a8190ef0fa4b9226cf3fe25f4403998fadedc6a88ffad0f3faf0e1e410e9166`

Migration application receipt:

`/Users/Dtwo1/PrinterV1OperatorReadiness/selective-1h-20260728T165835Z/migration-047-application-receipt.json`

The rollback backup must remain preserved through the proof and its closeout.

## Post-migration selective 1h preflight

Final status:

```text
V2_9_8B_SELECTIVE_1H_PREFLIGHT_READY
```

Verified:

- exact clean Git provenance;
- canonical migration count `47`;
- migration 047 applied;
- database integrity `ok`;
- zero foreign-key violations;
- dependency preflight READY;
- Source Governor budget preflight READY;
- selective 1h budget preflight READY;
- selective 1h implementation available;
- zero active or orphan campaign work;
- zero source calls;
- zero Scheduler runtime calls;
- zero database writes.

Active counts were zero for:

- campaign runs;
- campaign supervision;
- campaigns;
- discovery work;
- factory run steps;
- locked Scheduler jobs;
- proof supervision;
- Scheduler jobs.

## Fixed proof policy and ceilings

| Item | Rule |
|---|---:|
| Starting tokens | maximum 2 |
| Campaigns | exactly 1 |
| Cycles | exactly 1 |
| Main 15m phase | 900 seconds |
| Selective continuation | 2700 seconds |
| Total duration ceiling | 3900 seconds |
| Discovery requests | 2 |
| Governed requests total | 92 |
| Governed requests per token | 45 |
| Scheduler rows | 82 |
| Reserved mandatory close steps | 4 |
| Automatic retries | 0 |
| Restart | false |
| Successor | false |

Only tokens receiving categorical `CONTINUE` may enter `WINDOW_1H`.

Continuation must use the authoritative clean 15m episode. A raw partial
window cannot authorize it.

## Host-awake and supervision requirements

The proof must run while the Mac remains awake.

Recommended guard:

```text
caffeinate
```

The existing supervision lease remains authoritative. Host sleep or lease
expiry must terminate fail-closed with no automatic restart or successor.

## Proof acceptance criteria

The separately authorized proof must establish:

1. exactly one campaign and one cycle;
2. no more than two starting tokens;
3. categorical zero, one, or two continuation behavior;
4. authoritative clean 15m episode lineage;
5. exact campaign, factory, and window linkage;
6. Scheduler-owned and Source-Governed work;
7. genuine `WINDOW_1H` elapsed time and cadence;
8. E2Q audit and E2Z promotion only when clean and eligible;
9. dirty, blocked, gapped, or pair-drift outcomes remain unpromoted;
10. mandatory close work is not starved;
11. zero active or orphan residue at terminal close;
12. no retry, restart, resume, or successor;
13. report-only replay makes zero source calls, zero Scheduler calls, and zero writes;
14. retrieval and paper/financial deltas remain zero.

## Money-usefulness contribution

Selective 1h continuation can create longer-horizon survival, collapse,
continuation, and transition evidence without spending the full 1h budget on
every token.

Clean 1h memory remains evidence only. It is not a profitability prediction or
BUY signal.

## What this improves

- campaign/factory identity linkage;
- campaign-window lineage;
- selective token-local 1h continuation;
- genuine period-aware 1h close and promotion;
- bounded Source Governor and Scheduler capacity;
- rollback and preflight safety.

## What remains locked

- normal production 1h;
- `WINDOW_4H`, `WINDOW_12H`, and `WINDOW_24H`;
- retrieval and similarity activation;
- paper decisions and BUY/SELL/HOLD;
- positions, trades, audits, and PnL;
- wallets, private keys, signing, and real funds;
- paid APIs;
- scoring, ranking, confidence, and weighted logic;
- embeddings and vectors;
- automatic retries, restarts, resumes, and successors.

## Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Mitigation |
|---|---|
| Host sleeps | Run under `caffeinate`; fail closed |
| Both tokens continue | Fixed 92-request and 82-job ceilings |
| Close work is starved | Four reserved mandatory close steps |
| Partial window used as authority | Require authoritative clean 15m episode |
| Pair or continuity drift | Fail closed without clean promotion |
| Migration rollback needed | Preserve the verified backup and receipt |
| Repeated proof invocation | Exactly one separately authorized command; no automatic successor |

## Exact next permitted action

A separately authorized, exactly-one bounded operational selective
`WINDOW_1H` proof may now run using the canonical proof command.

This closeout does not authorize 4h or any downstream capability.

## Hard-boundary confirmation

During operator readiness:

- migration 047 was applied only after successful disposable rehearsal;
- no source request was made;
- no Scheduler or campaign runtime ran;
- no memory was generated;
- no operational 15m, 1h, or 4h proof ran;
- no retrieval or financial capability was activated.
