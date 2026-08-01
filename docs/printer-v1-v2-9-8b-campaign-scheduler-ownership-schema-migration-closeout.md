# Printer V1 V2-9.8B Campaign Scheduler Ownership Schema Migration Closeout

Date: 2026-08-01

Lane:
`V2-9.8B Campaign Scheduler Ownership Schema Migration Closeout`

Review type: independent documentation and evidence closeout only.

## 1. Verdict

`V2_9_8B_CAMPAIGN_SCHEDULER_OWNERSHIP_SCHEMA_MIGRATION_CLOSEOUT_PASS`

The bounded disposable proof for migration
`050_campaign_scheduler_ownership_scope.sql` is accepted as one controlling,
execution-specific proof package.

This PASS does not authorize applying migration `050` to the authoritative
database, resuming C1-C15, executing an operational campaign, generating
memory, activating retrieval, or enabling any paper or financial capability.

## 2. Baseline and branch identity

| Item | Reviewed value |
| --- | --- |
| Repository | `Dtwosam/MoneyPrinter` |
| Proof branch | `codex/v2-9-8b-scheduler-ownership-schema-migration-proof` |
| Required and reviewed HEAD | `a61ed4e4b6f43054d3688ffa14891b2fd21d7721` |
| Commit subject | `Correct canonical migration proof evidence` |
| Proof implementation branch | `codex/v2-9-8b-scheduler-ownership-schema-migration` — not merged or modified by this closeout |
| Migration under review | `migrations/050_campaign_scheduler_ownership_scope.sql` |

The remote proof branch resolved exactly to the required HEAD before this
closeout commit. The operator report states the local tracked worktree and index
were clean after the post-commit non-canonical regressions. This closeout did
not run or alter the operator's local checkout.

## 3. Controlling evidence identity

| Field | Controlling value |
| --- | --- |
| Proof execution ID | `V2_9_8B_MIG050_BOUNDED_PROOF_20260801T144740Z_5df7a275` |
| Evidence path | `operator-runs/v2-9-8b-mig050-bounded-proof/V2_9_8B_MIG050_BOUNDED_PROOF_20260801T144740Z_5df7a275/proof_summary.json` |
| Recorded JSON SHA-256 | `a6598c06ae85d4388df4d7e809e67475adcb386cd094639a78e9f358d70cafec` |
| Tracked GitHub blob SHA | `64d03d0cf07f37e3afec3f3ecfb2ca2b88a16a3b` |
| Source SHA-256 | `e13c40892f0c14d4c07960e00218569a536c50c0fc27815049284c3dd2aff5c2` |
| Source size | `65654784` |
| Source mtime_ns | `1785510479935495533` |
| Disposable pre SHA-256 | `e13c40892f0c14d4c07960e00218569a536c50c0fc27815049284c3dd2aff5c2` |
| Disposable post SHA-256 | `4000cbefaafb2a17c205a2129f2be14b30a01ec3bd7216397c0b66a09235f0cf` |
| Ledger before | tip `049_candidate_acquisition_integration.sql`, count `49` |
| Ledger after | tip `050_campaign_scheduler_ownership_scope.sql`, count `50` |
| Ledger delta | `050_campaign_scheduler_ownership_scope.sql` only |
| Historical pre/post count | `0 / 0` |
| Historical pre/post hash | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |
| Reconstruction hash | `1488cc12d4f4266daa81fac0025ce18e911ad444479b4eb49dea78156e78b46d` |
| Proof verdict | `V2_9_8B_CAMPAIGN_SCHEDULER_OWNERSHIP_SCHEMA_MIGRATION_BOUNDED_PROOF_PASS` |

The controlling pointer contains exactly the controlling execution ID. The
execution-specific JSON contains the same ID, evidence path, source identity,
migration timestamps, ledger transition, historical-preservation identity,
reconstruction hash, and verdict recorded by the controlling proof report.

## 4. Independent reconciliation results

| Review item | Result | Evidence conclusion |
| --- | --- | --- |
| `CONTROLLING_EXECUTION` exact pointer | PASS | Points only to `...T144740Z_5df7a275`. |
| Report / JSON controlling identity | PASS | Controlling fields agree and are enforced by `CanonicalEvidenceCrossArtifactEquality`. |
| Execution-specific package | PASS | JSON exists only under its execution-specific directory and the path embeds the controlling ID. |
| Evidence immutability | PASS | Canonical runner fails closed if the execution directory or summary path already exists. |
| Canonical environment gate | PASS | Requires `PRINTER_V2_9_8B_MIG050_CANONICAL_PROOF=1`; direct main mode additionally requires `PRINTER_V2_9_8B_MIG050_CANONICAL_PROOF_MAIN=1`. |
| Default pytest isolation | PASS | Default mode uses synthetic disposable databases and does not copy the authoritative DB, create a canonical execution ID, or write proof evidence. |
| Non-canonical artifact protection | PASS | Synthetic test setup/teardown fingerprints the complete evidence tree and authoritative filesystem identity and fails on change. |
| Superseded attempts retained honestly | PASS | Both earlier executions remain named and marked `SUPERSEDED_HARNESS_OVERWRITE`. |
| Shared summary retired | PASS | Generic `proof_summary.json` is a superseded marker, identifies both overwritten attempts, and points readers to `CONTROLLING_EXECUTION`. |
| Canonical rerun after success | PASS | Controlling report records no canonical rerun; later reported runs were non-canonical only. |
| Authoritative protection | PASS | Recorded before/after SHA-256, size, and mtime_ns are identical; the harness obtains filesystem identity without opening the authoritative path through SQLite. |
| Migration/schema result | PASS | Disposable copy advanced exactly from migration 049 to 050, integrity was `ok`, foreign-key violations were zero, and the approved columns/indexes/triggers were present. |
| Historical preservation | PASS | Authoritative copy contained zero historical ownership rows, producing exact empty-set equality; focused fixtures separately prove non-empty preserved-field equality. |
| V2 scope and replay-local reconstruction | PASS | All four scopes were represented on a separate disposable fixture; reconstruction included only `V2_STAGE_SCOPED` rows, used read-only SQLite mode, made zero source/Scheduler/operational-report calls, and produced a stable hash. |
| Forbidden capability delta | PASS | No provider, RPC, WebSocket, discovery, operational campaign, memory, retrieval, decision, position, trade, audit, PnL, wallet, signing, or execution capability was introduced. |

## 5. Superseded execution treatment

The following attempts are historical evidence only:

- `V2_9_8B_MIG050_BOUNDED_PROOF_20260801T143546Z_f98b72fd`
- `V2_9_8B_MIG050_BOUNDED_PROOF_20260801T143555Z_4f9874ff`

Both are classified `SUPERSEDED_HARNESS_OVERWRITE`. Their existence is not
hidden or rewritten. Neither may be cited as the controlling proof.

The shared path
`operator-runs/v2-9-8b-mig050-bounded-proof/proof_summary.json` is retired and
must not be treated as proof evidence. The only controlling package is selected
through `CONTROLLING_EXECUTION` and lives under the exact execution directory.

## 6. Migration and schema conclusion

The bounded evidence supports these conclusions only:

1. The current pre-050 authoritative filesystem image was suitable for a
   disposable-copy migration proof: ledger tip 049, no duplicate non-null
   Scheduler-job ownership, integrity `ok`, zero foreign-key violations, and
   zero historical Scheduler-ownership rows.
2. Migration `050_campaign_scheduler_ownership_scope.sql` applied once to the
   byte-identical disposable copy and produced exactly one ledger delta.
3. The approved stage-scoped ownership schema, partial unique Scheduler-job
   index, reporting index, and identity/provenance triggers were present after
   migration.
4. Failed synthetic migration cases rolled back without a 050 ledger entry or
   replacement-table residue.
5. The proof did not apply migration `050` to the authoritative database and
   did not connect the new owner to the operational campaign.

The proof is sufficient to close the disposable migration-proof capability.
It is not an authoritative migration application or operational-integration
proof.

## 7. Money-usefulness contribution

This closeout improves future paper-only money usefulness by ensuring discovery,
selection, first-15m handoff, window lifecycle, and terminal-cleanup Scheduler
work can later be attributed without double counting, invented windows, hidden
costs, or historical V1 evidence being silently upgraded into repaired V2
proof.

It improves accounting honesty and capital-protection evidence. It makes no
profit claim and creates no decision or trading signal.

## 8. What this lane improves

- Establishes one controlling migration-proof package after the overwrite defect.
- Makes canonical proof execution explicit and operator-gated.
- Prevents default regression runs from silently repeating the authoritative-copy proof.
- Replaces a mutable shared evidence path with immutable execution-specific evidence.
- Preserves the two superseded attempts as honest history.
- Proves migration 050 behavior on a disposable byte-identical copy without touching authoritative data.
- Proves the schema can represent all four approved Scheduler ownership scopes.
- Preserves exact V1/V2 evidence separation.

## 9. What remains locked

This closeout does not authorize:

- applying migration `050` to `data/printer_v1.sqlite3`;
- changing the supported authoritative schema head from migration `049`;
- resuming, rebuilding, or merging C1-C15 implementation;
- wiring scope-aware ownership into operational terminal closure or campaign runtime;
- running providers, RPC, WebSockets, discovery, tracking, snapshots, windows, campaigns, or memory generation;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, or `WINDOW_24H` activation;
- retrieval or dirty-memory training;
- paper decisions, BUY, SELL, HOLD, positions, trade events, paper audits, or PnL;
- wallets, private keys, signing, real funds, or live execution;
- paid APIs, scoring, ranking, confidence, weighting, embeddings, or vectors.

## 10. Proof or review needed before authoritative application

Before any future authoritative migration application, a separate explicit
operator-approved lane must at minimum:

1. reconcile the application proposal against the active build order and
   supported-schema-head rule;
2. establish the exact accepted baseline and integration history;
3. recheck authoritative filesystem identity and migration readiness without
   opening or mutating the DB before authorization;
4. define backup, restore, WAL/journal-mode, rollback, and stop conditions;
5. apply migration `050` exactly once only if that later lane explicitly permits it;
6. verify migration ledger, schema identity, integrity, foreign keys, historical
   rows, and authoritative post-application identity;
7. keep all runtime, retrieval, decision, and financial capabilities locked.

This closeout itself grants none of that authority.

## 11. Active build-order reconciliation

The migration design amendment contains a local dependency sequence ending in
`resume C1-C15 implementation`. That sequence describes what the schema blocker
would permit after its own implementation/proof/closeout chain, but it is
subordinate to the active Printer V1 source stack.

The higher active memory-growth build order and assistant active anchor still
name the exact next permitted task as:

```text
V2-9.8B Post-Accounting-Repair Authoritative WINDOW_15M Campaign Readiness Audit
```

Therefore this closeout does not move directly into C1-C15 and does not invent
an authoritative migration-application lane. Any later roadmap change requires
an explicit reconciliation/adoption step under the active source stack.

The readiness audit remains audit/readiness-only. It may inspect the repaired
ordinary command and authoritative DB read-only, but it may not run providers,
mutate the DB, execute a campaign, generate memory, or unlock later capabilities.

## 12. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Consequence | Control / disposition |
| --- | --- | --- |
| Shared proof file could be mistaken for current evidence | Wrong execution may be cited | Shared file is an explicit superseded marker; pointer plus execution-specific directory is controlling. |
| Canonical environment variable is accidentally enabled during regression | Unintended authoritative-copy proof repetition | Canonical test is env-gated; ordinary invocations remain non-canonical. Operators must clear the variable outside an explicitly authorized proof. |
| A new execution ID could create another valid-looking package | Multiple competing proofs | This closeout freezes the named controlling execution; another canonical run requires a new explicit lane and review. |
| Empty historical row set gives vacuous preservation evidence | Real historical-row drift may remain unobserved on this source image | Focused synthetic non-empty migration tests remain required supporting evidence; authoritative application must recheck the actual row set at that time. |
| Local migration sequence is mistaken for active-roadmap authority | C1-C15 or migration application could start out of order | Higher active build-order anchor wins; next task remains the readiness audit. |
| Remote closeout cannot inspect operator-local untracked files | Local residue could be missed | Operator's submitted result recorded a clean tracked worktree/index; no local file mutation was performed by this review. Recheck local status before later integration. |
| Evidence SHA-256 is recorded but future content could drift | Closeout identity could become stale | Treat commit `a61ed4...`, GitHub blob SHA, execution path, and recorded SHA-256 as one immutable evidence identity; any change invalidates this closeout. |
| Migration 050 remains unapplied to the supported authoritative schema | C1-C15 schema dependency remains unavailable operationally | Expected and locked; requires later active-roadmap authorization, not a shortcut in closeout. |

Efficiency blocker: none inside this documentation closeout. No canonical proof,
regression suite, provider call, database command, or runtime command was needed
or authorized.

## 13. Checks completed

- Remote branch-to-required-HEAD identity check: PASS before closeout.
- Controlling pointer inspection: PASS.
- Execution-specific JSON content and identity inspection: PASS.
- Proof report / JSON field reconciliation: PASS.
- Shared superseded marker inspection: PASS.
- Canonical/default harness boundary inspection: PASS.
- Immutable-path and evidence-tree guard inspection: PASS.
- Migration/schema/result inspection from controlling evidence: PASS.
- Forbidden capability and unlock scan: PASS.
- Active build-order reconciliation: PASS.

The canonical proof was not rerun. No tests, providers, RPC, WebSockets,
operational command, or database command were executed by this closeout.

## 14. Files changed by closeout

- `docs/printer-v1-v2-9-8b-campaign-scheduler-ownership-schema-migration-closeout.md`

No active build-order pointer was changed because the controlling active anchor
already names the readiness audit. No migration, production code, test harness,
evidence package, operator-run artifact, database, or implementation branch was
changed.

## 15. Exact next permitted lane

```text
V2-9.8B Post-Accounting-Repair Authoritative WINDOW_15M Campaign Readiness Audit
```

This next lane remains audit/readiness-only and does not directly authorize an
authoritative campaign or migration application.
