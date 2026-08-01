# Printer V1 V2-9.8B C1-C15 Final Independent Read-Only Conformance Review

Date: 2026-08-01

Lane:
`V2-9.8B C1-C15 Final Independent Read-Only Conformance Review`

Reviewed repair branch:
`agent/v2-9-8b-c12-c14-durable-cleanup-replay-reconstruction-repair`

Reviewed repair commit:
`e97fa898938f90e3d2c4aaf32c262db7367bffaa`

Repair baseline:
`780fabfc815026243bc5ad9ab3e0f13e86ae05d8`

Review type: independent static/read-only inspection of the one-commit focused repair, repaired implementation reports, the exact acceptance and report-only replay boundaries, and the new focused test source. No production source was changed by this review, no tests or runtime command were executed, no provider/RPC/WebSocket/source path was contacted, and no database was opened or mutated.

## Verdict

`CONFORMANCE_REVIEW_PASS`

Completion classification:

`V2_9_8B_C1_C15_FINAL_INDEPENDENT_CONFORMANCE_REVIEW_PASS`

The three blockers from the prior repeat review are repaired without a schema migration, parallel evidence owner, report owner, runner, Scheduler, or source path. C1-C15 are now supported by the approved design-to-boundary-to-owner-to-report-to-gate-to-negative-test chain.

This PASS does not authorize a campaign or bounded proof directly. The active build order requires the next audit-only lane:

`V2-9.8B Post-Accounting-Repair Authoritative WINDOW_15M Campaign Readiness Audit`

## Review method

The review checked commit `e97fa898938f90e3d2c4aaf32c262db7367bffaa` against:

- the active Printer V1 source stack;
- the V2-9.8B full-run accounting and terminal-evidence design;
- the final C1-C15 conformance map;
- the first independent blocked review;
- the repeat independent blocked review;
- the two focused C12-C14 repair reports;
- the changed implementation and focused-test files.

The completion law remains:

```text
design requirement
-> real execution boundary
-> single-owner evidence
-> independent action-local evidence
-> canonical report field
-> acceptance-gate check
-> negative fail-closed test
```

## Commit boundary and scope

The repair is exactly one commit ahead of the repeat-review baseline:

- base: `780fabfc815026243bc5ad9ab3e0f13e86ae05d8`;
- head: `e97fa898938f90e3d2c4aaf32c262db7367bffaa`;
- commit message: `Repair durable cleanup and replay reconstruction`.

Changed files are lane-scoped:

- `src/printer_v1/operator_cli/campaign_full_run_accounting.py`;
- `src/printer_v1/operator_cli/campaign_supervision.py`;
- `src/printer_v1/operator_cli/operational_memory_factory_command.py`;
- `tests/test_v2_9_8b_c12_c14_durable_cleanup_timestamp_and_replay_reconstruction_repair.py`;
- `tests/test_v2_9_8b_full_run_wiring_integration.py`;
- `docs/printer-v1-v2-9-8b-c12-c14-durable-cleanup-timestamp-and-replay-reconstruction-repair.md`;
- `docs/printer-v1-v2-9-8b-c12-c14-authorization-marker-and-lease-evidence-conformance-repair.md`.

No schema or migration file changed. Neither independent review was rewritten or erased.

## Prior finding F1 — durable cleanup completion timestamp

Status: `RESOLVED`

The repair adds one shared timestamp contract:

- `parse_durable_timestamp()` accepts only non-empty, parseable, timezone-aware ISO-8601 values;
- `durable_cleanup_release_timestamps_valid()` requires both durable timestamps and rejects release before cleanup completion.

The exact flow is now:

1. `cleanup_campaign_supervision()` persists terminal supervision and `cleanup_completed_at`.
2. It releases the exact lease lock.
3. It persists `lease_released_at`.
4. It reopens the database read-only and returns the exact durable timestamps from the supervision row.
5. `load_cleanup_lease_evidence()` independently reads the exact supervision row.
6. The canonical full-run report carries `durable_cleanup_completed_at` and `lease_released_at`.
7. Initial acceptance requires presence, timezone-aware validity, chronological ordering, terminal supervision, exact cleanup identity, literal cleanup/release truth, absent lock, and zero residue.
8. Public replay reads the same durable row and applies the same shared timestamp helper before rerunning the same acceptance gate.

A caller-carried timestamp is not used as the durable owner. The durable supervision row owns the acceptance and replay timestamps.

Focused negative evidence covers:

- null report-carried durable cleanup timestamp at the gate;
- malformed durable cleanup timestamp;
- timezone-naive durable cleanup timestamp;
- lease release before cleanup completion.

Focused positive evidence covers valid durable cleanup and release timestamps reaching Campaign PASS.

## Prior finding F2 — marker canonicalization drift

Status: `RESOLVED`

The authoritative marker canonicalization owner remains unchanged:

- `canonical_campaign_evidence_json()`;
- `campaign_evidence_sha256()`;
- sorted keys;
- compact separators;
- `ensure_ascii=True`.

Creation and acceptance already used that owner. Public `report_only()` now also uses `campaign_evidence_sha256()` for authorization and invocation markers instead of a replay-local `ensure_ascii=False` serializer.

The focused non-ASCII lease-lock proof uses the real supervision acquisition row, reconstructs the invocation payload through `build_invocation_marker_payload()`, confirms the old local serializer would produce a different digest, and proves:

- creation digest equals acceptance digest;
- acceptance digest equals replay digest;
- public report-only returns `REPLAYED`;
- source, Scheduler-runtime, and write counters remain zero;
- the disposable database mtime remains unchanged.

The predecessor report's inaccurate canonicalization statement was corrected factually without rewriting either independent review.

## Prior finding F3 — factory configuration reconstruction

Status: `RESOLVED`

Public replay no longer copies `full_identity.factory_config_hash` into its durable reconstruction.

It now queries:

```sql
SELECT run_id, config_hash
FROM printer_memory_factory_runs
WHERE run_id = ?
```

using the exact report-carried factory-run identity, then requires:

- exactly one returned row;
- exact run identity;
- non-empty durable `config_hash`;
- equality with the report identity's `factory_config_hash`;
- equality with the separate marker/report `factory_config_hash` field;
- inequality with the authorization and invocation marker digests.

Only after those validations does replay place the durable value into the reconstructed marker evidence for exact comparison.

Focused negative evidence covers:

- report-carried factory config hash tampering with the report-body hash recomputed;
- missing factory-run row;
- empty durable factory config hash.

These cases block from durable reconstruction rather than from a stale report hash.

## C1-C15 final status

| ID | Status | Final review result |
| --- | --- | --- |
| C1 | PASS | One coordinator-created accounting owner and one independent action-local ledger remain continuous through finalization. |
| C2 | PASS | Complete immutable campaign/run/cycle/configuration/factory identity remains allocated before lifecycle work. |
| C3 | PASS | Governed success and failure attempts remain observed at the real execution boundary. |
| C4 | PASS | Canonical transport bytes and normalized rows remain identity-bearing and reconciled. |
| C5 | PASS | Lifecycle reservations remain observed from the shared authoritative policy and real reservation boundary. |
| C6 | PASS | Required named validation families remain execution-boundary evidence and gate inputs. |
| C7 | PASS | Stage-scoped Scheduler ownership and transition evidence remain complete and exact. |
| C8 | PASS | Full-manifest owner/action-local equality remains unscoped and non-vacuous. |
| C9 | PASS | Campaign-window ownership precedes terminal slot reconciliation; no default cooldown is accepted. |
| C10 | PASS | Exact cadence, snapshot coverage, and two succeeded close operations remain gated. |
| C11 | PASS | Unlawful clean-episode insertion remains prevented before insertion. |
| C12 | PASS | The canonical report is backed by durable authorization, invocation, cleanup, release, factory configuration, ownership, and accounting evidence. |
| C13 | PASS | Exactly one authorization, one supervision invocation, one factory binding, actual durable cleanup, released lease, zero residue, and zero retry/restart/resume/successor state are mandatory. |
| C14 | PASS | Public exact report-only replay independently reconstructs markers, factory config, cleanup, windows, Scheduler ownership, totals, hashes, and acceptance read-only with zero work. |
| C15 | PASS | Real stage terminal statuses and first-terminal-cause handling remain preserved and fail closed. |

Overall C1-C15 verdict: `PASS`.

## Test-evidence review

The repair report records:

- changed-file compilation: exit 0;
- new focused module: 10 passed;
- combined C12-C14/accounting/wiring/report-only/supervision matrix: 163 passed plus 33 subtests;
- nearest supervision/factory/ownership matrix: 72 passed.

Static inspection confirms the focused module exercises the required repaired surfaces through disposable databases and real existing owners rather than report-only mocks.

This independent review did not rerun tests. The reported unrelated stale-discovery-module failure was confirmed by the executor on the starting HEAD and is outside this lane; it does not weaken the focused proof or justify expanding scope.

## Money-usefulness contribution

This conformance PASS improves the trustworthiness of future authoritative `WINDOW_15M` memory evidence. It prevents false Campaign PASS before durable cleanup completion, prevents platform/path-dependent marker replay failure, and prevents replay from trusting a report-carried factory configuration value.

It creates no profit claim and unlocks no retrieval, paper decision, position, trade, or money movement.

## What improved

- Durable cleanup completion is mandatory at initial acceptance and replay.
- Cleanup and lease timestamps share one parse/order contract.
- Marker creation, acceptance, and replay share one canonical hash owner.
- Factory configuration is independently reconstructed from its durable factory-run owner.
- C1-C15 full-run accounting and terminal evidence now have a complete static conformance chain.

## What remains locked

- campaign execution and bounded proof until the next readiness lane approves it;
- provider/source/RPC/WebSocket execution;
- authoritative DB mutation;
- historical July 31 campaign repair;
- authoritative memory generation or promotion;
- `WINDOW_1H`, 4h, 12h, or 24h activation;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions, trade events, paper trade audits, or PnL;
- wallets, signing, private keys, real funds, or live execution;
- paid APIs;
- scoring, ranking, confidence, weighting, embeddings, or vectors.

## Proof still required

The active build order requires the next audit-only readiness lane before any final authorization or bounded campaign execution:

`V2-9.8B Post-Accounting-Repair Authoritative WINDOW_15M Campaign Readiness Audit`

That audit must inspect the authoritative state read-only and determine whether a later design/specification or final-authorization step is safe. It may not run providers, mutate the authoritative database, execute a campaign, generate memory, or unlock retrieval or financial capabilities.

## Functionality Risks / Setbacks / Efficiency Blockers

| Item | Effect | Required control |
| --- | --- | --- |
| This review is static and does not independently rerun the executor's tests | Test-command results are report evidence rather than independently executed proof | Preserve the focused test record and require readiness audit before runtime authorization |
| Null `cleanup_completed_at` is schema-unreachable on a valid terminal row | The null negative is proven directly at the gate rather than through an ordinary valid end-to-end row | Keep both schema invariant and explicit gate check |
| Corrupt factory-row negatives require disposable DB copies | Normal schema ownership prevents ordinary mutation of valid evidence | Keep corruption tests disposable and never weaken production invariants |
| Report-only lock-path verification depends on the durable path being inspectable on the replay host | Cross-host artifact relocation can cause an honest replay block | Readiness audit must confirm the intended same-host authoritative replay and artifact identity assumptions |
| Historical reports lack the repaired evidence contract | They must not be silently upgraded | Continue fail-closed historical replay behavior |
| Broad regression suite was not run | Unrelated repository behavior was not surveyed | Risk-based verification is sufficient unless readiness audit exposes a shared architectural concern |

## Exact next permitted task

`V2-9.8B Post-Accounting-Repair Authoritative WINDOW_15M Campaign Readiness Audit`

Allowed next work is audit-only:

- static inspection;
- read-only authoritative DB inspection;
- existing artifact review;
- readiness documentation.

Not allowed in that audit:

- providers, RPC, WebSockets, or source fetching;
- authoritative DB writes or migration application;
- campaign execution or bounded proof;
- memory generation or promotion;
- retrieval or paper decisions;
- BUY/SELL/HOLD, positions, trades, audits, or PnL.

A readiness PASS may authorize only the next approved design/specification or final-authorization step. It does not itself authorize a campaign.
