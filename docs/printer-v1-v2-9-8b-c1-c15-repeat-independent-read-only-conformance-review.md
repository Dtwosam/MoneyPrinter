# Printer V1 V2-9.8B C1-C15 Repeat Independent Read-Only Conformance Review

Date: 2026-08-01

Lane:
`V2-9.8B C1-C15 Repeat Independent Read-Only Conformance Review`

Reviewed repair branch:
`agent/v2-9-8b-c12-c14-authorization-marker-lease-evidence-repair`

Reviewed repair commit:
`780496423926f70d9904196bfe391327e09b8370`

Repair baseline:
`925bf7b376145ccc283bf4edc7c8da230df26470`

Review type: static/read-only inspection of the one-commit repair diff, repaired implementation report, source boundaries, public replay path, and focused test sources. No production code was changed, no tests or runtime command were executed, no source/provider/RPC/WebSocket path was contacted, and no database was opened or mutated.

## Verdict

`CONFORMANCE_REVIEW_BLOCKED`

Block classification:

`BLOCKED_C12_C14_DURABLE_CLEANUP_AND_REPLAY_RECONSTRUCTION_GAPS`

The focused repair correctly removes the previously confirmed default-true lease path, creates distinct authorization and invocation evidence, and derives invocation identity from campaign-supervision acquisition rather than factory binding. However, three completion-law gaps remain. Bounded proof is not authorized.

## Review method

The review checked the repaired commit against:

- the active Printer V1 source stack;
- the approved full-run accounting and terminal-evidence design;
- the final C1-C15 conformance map;
- the first independent review and its required C12-C14 repair;
- the repaired source and test files at commit `780496423926f70d9904196bfe391327e09b8370`.

Every requirement remains governed by:

```text
design requirement
-> real execution boundary
-> single-owner evidence
-> independent action-local evidence
-> canonical report field
-> acceptance-gate check
-> negative fail-closed test
```

## Confirmed repairs

The repeat review confirms that:

1. `_apply_full_run_campaign_acceptance()` no longer has a default-true lease argument. Omitted cleanup evidence reaches a fail-closed report/gate path.
2. The immutable campaign configuration now owns a dedicated authorization-marker payload and digest created before accountable work.
3. The exact campaign-supervision acquisition row now supplies the invocation-marker identity and invocation count.
4. Authorization-marker, invocation-marker, campaign configuration, and factory configuration fields are separated.
5. The ordinary coordinator passes the real `cleanup_campaign_supervision()` result into finalization.
6. Initial acceptance cross-checks cleanup identity, literal boolean cleanup/release truth, durable terminal supervision, release timestamp, lock absence, active work, locked work, retry/restart/resume/successor state, and marker/binding counts.
7. The public `report_only()` path opens SQLite in `mode=ro` and performs no source calls, Scheduler runtime calls, or writes.

These repairs resolve the three findings recorded in the first independent review. They do not by themselves complete C12-C14 because of the findings below.

## Blocking finding F1: initial acceptance does not require durable `cleanup_completed_at`

`load_cleanup_lease_evidence()` reads and returns both:

- `durable_cleanup_completed_at`;
- `lease_released_at`.

The report carries the complete nested cleanup evidence. The acceptance gate explicitly requires:

- cleanup evidence presence and identity equality;
- `cleanup_completed is True` from the supplied cleanup mapping;
- durable terminal supervision;
- non-empty `lease_released_at`;
- absent lease lock.

It does not require non-empty durable `cleanup_completed_at`.

Therefore a report can reach Campaign PASS when:

- the caller supplies `cleanup_completed=True`;
- the durable supervision row is terminal;
- `lease_released_at` exists and the lock is absent;
- but the durable `cleanup_completed_at` value is missing.

The public replay path later requires durable `cleanup_completed_at`, so this state would produce an initial Campaign PASS followed by replay block. That violates the one canonical report/gate law and the requirement that PASS depend on actual durable cleanup completion—not caller-carried truth alone.

The focused test module tests missing release timestamp and remaining lock, but has no negative test for missing durable `cleanup_completed_at`.

Required repair:

- expose `durable_cleanup_completed_at` as an explicit terminal-safety field;
- require it to be a non-empty valid durable timestamp in the acceptance gate;
- require exact agreement with the cleanup completion identity/timing contract where applicable;
- add a negative test proving a null/missing durable cleanup timestamp cannot reach PASS;
- preserve the same requirement in public replay.

## Blocking finding F2: marker hashing uses two different canonical JSON contracts

The canonical campaign-evidence helper in `campaign_persistence.py` serializes with:

```python
ensure_ascii=True
```

Both authorization and invocation marker digests are created through that helper.

The public `report_only()` path independently recomputes marker hashes using a local serializer with:

```python
ensure_ascii=False
```

The currently tested marker fixture is ASCII-only, so the mismatch is hidden. The invocation marker includes `lease_lock_path`, and the existing path contract does not restrict valid paths to ASCII. A valid non-ASCII user/home/artifact path therefore produces different bytes and a false replay block even though initial acceptance used the canonical owner correctly.

The repair report also states that both marker digests use `ensure_ascii=False`, which does not match the implementation owner.

This violates C14 exact replay because report generation and replay do not share one canonical byte contract.

Required repair:

- remove the replay-local marker serialization rule;
- recompute both marker digests through `campaign_evidence_sha256()` or the exact same canonical owner used at creation;
- add a focused valid non-ASCII lease-path marker test proving initial acceptance and read-only replay agree;
- correct the repair report’s canonicalization statement.

## Blocking finding F3: replay does not independently reconstruct `factory_config_hash`

During initial report construction, `factory_config_hash` is read from the exact `printer_memory_factory_runs` row.

During public replay, `load_authorization_invocation_evidence()` initially returns `factory_config_hash=None`. The replay path then assigns:

```python
durable_markers["factory_config_hash"] = full_identity.get("factory_config_hash")
```

That copies the report-carried value into the supposedly durable reconstruction before comparing `durable_markers` with report marker evidence. It does not load and compare the factory-run row’s real `config_hash`.

As a result, replay independently verifies marker digests and factory binding identity, but it does not independently verify the separate factory configuration hash that the report claims. A changed report value can satisfy this portion of durable reconstruction if the report/body hashes are regenerated, because the replay comparison reuses the report value.

This violates:

- C12, because one canonical report field is not backed by its claimed durable owner during replay;
- C14, because exact report-only reconstruction must read the factory configuration hash from the factory-run owner rather than copy it from report JSON.

Required repair:

- query `printer_memory_factory_runs.config_hash` for the exact `factory_run_id` during replay;
- require it to equal `full_run.identity.factory_config_hash` and the marker evidence’s separate factory-config field;
- block on missing factory row, missing config hash, wrong factory identity, or hash mismatch;
- add a negative test that mutates only the report-carried factory config hash, recomputes report hashes, and proves replay still blocks from durable mismatch.

## C1-C15 repeat-review status

| ID | Status | Result |
| --- | --- | --- |
| C1 | SUPPORTED | One coordinator-created owner and action-local ledger remain continuous through finalization. |
| C2 | SUPPORTED | Complete immutable campaign/run/cycle/configuration/factory identity remains preallocated before lifecycle work. |
| C3 | SUPPORTED | Governed success/failure attempts remain observed at the execution boundary. |
| C4 | SUPPORTED | Canonical transport bytes and normalized rows remain identity-bearing and reconciled. |
| C5 | SUPPORTED | Lifecycle reservations remain observed from the shared authoritative policy/boundary. |
| C6 | SUPPORTED | Required named validation families remain execution-boundary evidence and gate inputs. |
| C7 | SUPPORTED | Stage-scoped Scheduler ownership and transition evidence remain complete. |
| C8 | SUPPORTED | Full-manifest equality remains unscoped and non-vacuous. |
| C9 | SUPPORTED | Campaign-window registration precedes terminal slot reconciliation and no default cooldown is used. |
| C10 | SUPPORTED | Exact cadence, snapshots, coverage, and two succeeded closes remain gated. |
| C11 | SUPPORTED | Unlawful clean-episode insertion remains prevented before insertion. |
| C12 | BLOCKED | The initial gate does not require durable `cleanup_completed_at`, and replay does not durably reconstruct factory config hash. |
| C13 | BLOCKED | Actual cleanup mapping is now mandatory, but durable cleanup completion timestamp is not mandatory at initial PASS. |
| C14 | BLOCKED | Replay marker canonicalization differs from creation, and factory config hash is copied from report JSON instead of reconstructed. |
| C15 | SUPPORTED | Real stage terminal status and first-cause handling remain intact. |

`SUPPORTED` is not a lane PASS while any mandatory C item is blocked.

## Test-evidence review

The repair report records:

- compilation exit 0;
- 15 focused tests plus 16 subtests;
- 62 combined C12-C14/C1-C15 tests plus 22 subtests;
- 24 supervision/abstract/source-accounting tests plus 11 subtests;
- 130 nearest affected compatibility tests.

This repeat review did not rerun those commands. Static inspection found that the focused matrix lacks:

- null/missing durable `cleanup_completed_at` at initial acceptance;
- a valid non-ASCII invocation-marker path exercising creation and replay canonicalization;
- report-carried factory config hash tampering with independently recomputed report hashes.

No broad repository suite is needed for the narrow repair.

## Money-usefulness contribution

The repeat review prevents a report from being accepted before durable cleanup completion is fully proven and prevents replay from silently trusting a report-carried factory configuration field. It also avoids a platform/path-dependent false replay failure. These controls improve trust in future memory evidence but unlock no retrieval, decision, trade, money movement, or profit capability.

## What remains locked

- application of migration 050 to `data/printer_v1.sqlite3`;
- bounded or live campaign proof;
- provider/source/RPC/WebSocket execution;
- authoritative memory generation or promotion;
- WINDOW_1H/4H/12H/24H;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions, trades, audits, or PnL;
- wallets, keys, signing, real funds, or live execution;
- paid APIs;
- scoring, ranking, confidence, weighting, embeddings, or vectors.

## Minimum repair and proof

The next repair must be limited to:

1. mandatory durable `cleanup_completed_at` in initial acceptance and replay;
2. one shared marker canonicalization helper for creation, acceptance, and replay;
3. durable factory-run `config_hash` reconstruction during report-only replay;
4. focused negative/positive tests for those three surfaces;
5. factual correction of the repair report.

Minimum focused tests:

- null durable `cleanup_completed_at` blocks initial Campaign PASS;
- valid durable cleanup and release timestamps pass;
- valid non-ASCII lease-lock path yields identical invocation digest at creation and replay;
- replay blocks when report-carried factory config hash differs from the exact factory-run row, even after report hashes are recomputed;
- exact read-only replay still returns zero source calls, Scheduler actions, and writes.

Do not run a broad suite unless focused failures expose a shared architectural regression.

## Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Effect | Required control |
| --- | --- | --- |
| Caller cleanup truth exceeds durable cleanup truth | Initial report may PASS before durable cleanup completion is proven | Gate explicit durable `cleanup_completed_at` |
| Creation/replay canonical JSON drift | Valid path-dependent marker evidence can fail replay | Use one shared canonical hash helper |
| Report-carried factory hash reused as durable evidence | Replay can miss factory-config field tampering | Query exact factory-run row during replay |
| Repair scope expands into unrelated accounting | Increases regression risk | Limit changes to C12-C14 report/gate/replay and focused tests |

## Exact next permitted task

`V2-9.8B C12-C14 Durable Cleanup Timestamp and Replay Reconstruction Repair`

After that focused repair passes, repeat the independent read-only C1-C15 conformance review again.

Bounded proof remains prohibited until the review returns `CONFORMANCE_REVIEW_PASS`.
