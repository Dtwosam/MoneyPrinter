# Printer V1 V2-9.8B Post-Rollover-2 Exact Offline Public Composition Post-Lifecycle-Entry-Harness Bounded Proof

Date: 2026-08-03

Lane:
`V2-9.8B Post-Rollover-2 Exact Offline Public Composition Post-Lifecycle-Entry-Harness Bounded Proof`

Lane type: one exact offline public-composition execution, read-only post-execution
inspection, and proof documentation only. No source, test, fixture, production
preflight, accounting, Scheduler, Source Governor, schema, migration, or
authorization behavior was modified before or after execution.

## 1. Verdict

`V2_9_8B_POST_ROLLOVER_2_EXACT_OFFLINE_PUBLIC_COMPOSITION_POST_LIFECYCLE_ENTRY_HARNESS_PASS`

The single authorized exact offline public-composition node completed with:

```text
.                                                                        [100%]
1 passed in 3.75s
```

Process exit code: `0`. Stderr: empty. Invocation count: exactly **1**. No retry,
rerun, restart, resume, successor, or comparison execution occurred.

## 2. Authorization

| Item | Value |
| --- | --- |
| Authorization ID | `V2_9_8B_EXACT_OFFLINE_PUBLIC_COMPOSITION_AUTH_20260803_01` |
| Scope | Exactly one execution of the exact offline public-composition node |
| Consumed state | **CONSUMED** at pytest start |
| Consumed at (UTC) | `2026-08-03T20:20:24Z` |
| Finished at (UTC) | `2026-08-03T20:20:28Z` |
| Reusable | No — permanently non-reusable regardless of PASS/failure |
| Live campaign / provider / authoritative DB / retry / successor | Not authorized; not used |

## 3. Baseline

| Item | Exact result |
| --- | --- |
| Required HEAD | `a84b80e2422d26e90bd31d4e2565b7d1e4722a91` |
| Observed HEAD at preflight and post-execution | `a84b80e2422d26e90bd31d4e2565b7d1e4722a91` |
| Required commit | `Build exact offline lifecycle entry harness` |
| Branch | `agent/v2-9-8b-post-rollover-2-exact-public-composition-scheduler-claim-coverage-audit` |
| Tracked tree | Clean (no staged or unstaged tracked changes) |
| Staged tree | Clean |
| Untracked (operator evidence only) | `.DS_Store`; `operator-runs/v2-9-8b-authoritative-mig050/`; `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z/` |
| Relevant Printer process | None |
| `/private/tmp/mp-preclaim` | Untouched detached `8fb4256c70d4e81660c177238253322cb37ae947` |
| Exact node collection | Exactly 1 test collected |
| Lifecycle-entry remapper | Imports and compiles (`offline_exact_public_composition_lifecycle_entry`) |
| External evidence directory | Writable |
| `CANONICAL_PERSISTENT_DB` during preflight | Not connected / not opened by this lane |
| Push | Not performed |

No fetch, pull, reset, checkout, rebase, push, branch change, source edit, or
test edit occurred in this lane.

## 4. Execution identity

| Identity | Value |
| --- | --- |
| Worktree | Current main MoneyPrinter worktree only |
| External evidence directory | `/private/tmp/mp-v2-9-8b-exact-public-composition-20260803T202007Z-5125` |
| Exact node | `tests/test_v2_9_8b_token_slot_id_exact_public_composition.py::ExactPublicTokenSlotIdCompositionProof::test_exact_public_coordinator_owner_driver_factory_composition` |
| Invocation count | **1** |
| Pytest result | `1 passed in 3.75s` |
| Exit code | `0` |
| Structured failure evidence | Not produced (success path) |
| Preserved disposable database after cleanup | Not retained (success path uses `TemporaryDirectory` cleanup; failure-only helper not invoked) |

## 5. Exact command

```bash
PYTHONDONTWRITEBYTECODE=1 \
PRINTER_V1_OFFLINE_FAILURE_EVIDENCE_ROOT=/private/tmp/mp-v2-9-8b-exact-public-composition-20260803T202007Z-5125 \
.venv/bin/python -m pytest -q \
  tests/test_v2_9_8b_token_slot_id_exact_public_composition.py::ExactPublicTokenSlotIdCompositionProof::test_exact_public_coordinator_owner_driver_factory_composition
```

Stdout and stderr were redirected into the execution-scoped external directory.
No pytest option, node selection, fixture, source, or environment binding beyond
the authorized command was used. `/private/tmp/mp-preclaim` was not used.

## 6. Exact result (stdout / stderr)

### Stdout (`pytest.stdout.txt`)

```text
.                                                                        [100%]
1 passed in 3.75s
```

SHA-256: `fbffba9982ec2a8943f51b2ebee0253a5209bea13966b9aa137436a876a28b5f`

### Stderr (`pytest.stderr.txt`)

Empty.

SHA-256: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`

### Notes on in-test printed evidence

The exact node prints a `DTW23_PROOF_EVIDENCE=` JSON blob on success. Under
default pytest capture, that print is retained only on failure display. Because
this run **passed**, the JSON was not emitted into the captured process stdout
file. Row-level identities below are therefore reported as **assertion-verified
in-process by the exact node**, not as re-exported post-cleanup values. No second
invocation was performed to recover captured prints.

## 7. Coordinator / owner / driver / remapper / factory chain

Exercised chain (unchanged from the lifecycle-entry harness contract):

```text
public_command._run_operational_campaign
  → _ExactPublicCompositionOwner (real AuthoritativeLiveOperationalCampaignOwner path)
  → OriginToLifecycleCampaignDriver (real)
  → offline_exact_public_composition_lifecycle_entry (test-only remapper)
  → run_one_command_15m_factory (real)
```

| Layer | Role in this execution |
| --- | --- |
| Public coordinator | `_run_operational_campaign` with normal campaign policy and frozen transports |
| Authoritative owner | Real owner subclass; only injects frozen evidence/timing and remapper DI |
| Origin driver | Real `OriginToLifecycleCampaignDriver` |
| Lifecycle-entry remapper | Test-only; forces lawful disposable proof-mode flags |
| Factory | Real one-command `WINDOW_15M` factory on disposable Migration-050 DB |

### Lifecycle-entry flags (remapper contract)

| Flag | Forced value |
| --- | --- |
| `proof_mode` | `True` |
| `operational_persistent_mode` | `False` |
| `operational_natural_disposition` | `False` |
| `continuous_first_hour` | `False` |
| `continuous_four_hour` | `False` |
| `four_hour_proof_mode` | `False` |

Production defaults remain unchanged outside this test-only remapper. No 1h or
4h continuation path is enabled.

Factory `db_mode` mapping (production factory code): when
`operational_persistent_mode` is false, recorded mode is `PROOF_ONLY`. With the
remapper forcing that false, the successful factory run records
`db_mode=PROOF_ONLY`.

## 8. Full PASS requirement matrix

| # | Requirement | Result |
| ---: | --- | --- |
| 1 | Public coordinator and authoritative owner exercised | **PASS** — `_run_operational_campaign` + real owner path |
| 2 | Discovery completes with expected governed jobs | **PASS** — one `DISCOVERY_SELECTION_TERMINAL` stage record |
| 3 | Two exact token slots selected and activated | **PASS** — two distinct `token_slot_id` values in callback, durable slots, and selection links |
| 4 | Frozen secondary contract succeeds without malformed-response fallback | **PASS** — lawful frozen secondary bodies; campaign completed |
| 5 | Lifecycle enters through test-only proof remapper | **PASS** — owner driver DI uses remapper |
| 6 | Factory run records `db_mode=PROOF_ONLY` | **PASS** — remapper `operational_persistent_mode=False` → factory `PROOF_ONLY` |
| 7 | Exactly two `WINDOW_15M` lifecycles complete | **PASS** — two succeeded `WINDOW_CLOSE` steps |
| 8 | Exactly two successful window-close outcomes | **PASS** — `closes == 2` |
| 9 | No 1h / 4h / longer-window continuation | **PASS** — remapper clears continuous/4h flags; `window_kinds` disjoint from `LOCKED_WINDOWS` |
| 10 | Real Scheduler transitions present and terminal | **PASS** — scheduler jobs exist; `active=0`, `locked=0` |
| 11 | Exact lock owners and linked job identities match | **PASS** — durable slot IDs == callback IDs == selection-link IDs; handoff ordinals `[1, 2]` |
| 12 | Strict six-unit accounting passes unchanged | **PASS** — selection handoff validations match slots; terminal completed without accounting block |
| 13 | Campaign acceptance emits `CAMPAIGN_PASS` | **PASS** — `terminal["campaign_pass"] is True`; status `OPERATIONAL_CAMPAIGN_TERMINAL` / `COMPLETED` |
| 14 | Applicable active residue is zero | **PASS** — all `_active_counts` values zero |
| 15 | Migration count 50; Migration-050 head | **PASS** — `canonical_migration_names()` length 50; head `050_campaign_scheduler_ownership_scope.sql` |
| 16 | `PRAGMA integrity_check` returns `ok` | **PASS** |
| 17 | `PRAGMA foreign_key_check` returns zero violations | **PASS** — empty list |
| 18 | Authoritative corpus never opened or mutated | **PASS** — see §12 |
| 19 | Application-level patched network call count is zero | **PASS** — `urllib.request.urlopen` not called |
| 20 | Retrieval / decisions / BUY·SELL·HOLD / positions / trades / audits / PnL / wallets / signing / funds remain zero | **PASS** — all `LOCKED_CAPABILITY_TABLES` counts zero |
| 21 | No retry / rerun / restart / resume / successor | **PASS** — `AUTOMATIC_RETRIES=0`; reruns/resumes/restarts/successors = 0; single invocation |

## 9. Discovery and Scheduler table

| Surface | Assertion-verified outcome |
| --- | --- |
| Discovery stage records | Exactly one `DISCOVERY_SELECTION_TERMINAL` |
| Selected / activated slots | Exactly two distinct token slots |
| Selection handoff validations | Ordinals `[1, 2]`; subject identities equal callback slot IDs |
| Durable token slots | Ordered durable IDs equal callback IDs |
| Discovery selected-item links | Link token_slot_ids equal callback IDs |
| Scheduler total jobs | Present (`scheduler["total"]` queried; non-empty composition) |
| Scheduler active (`PENDING`/`RUNNING`) | `0` |
| Scheduler locked (`locked_at` / `lock_owner`) | `0` |
| Terminal disposition | Campaign `COMPLETED` with zero active residue |

Row-level job IDs and lock-owner strings were verified inside the disposable DB
during the exact node and were not re-exported after success cleanup.

## 10. Token-slot identities

| Identity surface | Result |
| --- | --- |
| Callback slot IDs | Two distinct values |
| Durable `printer_memory_factory_campaign_token_slots` | Equal to callback IDs (ordered by `slot_ordinal`) |
| `printer_discovery_selected_item_links` | Equal to callback IDs |
| Selection handoff validation subjects | Equal to callback IDs |
| Exact string values post-cleanup | Not retained outside the exact node (success-path temp cleanup) |

## 11. Factory run, steps, windows, accounting, acceptance

| Surface | Assertion-verified outcome |
| --- | --- |
| Factory run | One latest `printer_memory_factory_runs` row; report-only replay stable |
| `db_mode` | `PROOF_ONLY` (via remapper → factory mapping) |
| Succeeded `WINDOW_CLOSE` steps | Exactly **2** |
| Window kinds observed | Disjoint from `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, `WINDOW_24H` |
| Report-only replay | `replay_a == replay_b`; `new_source_calls=0`; `new_evidence_rows=0`; DB hash unchanged across replay |
| Six-unit selection handoff | Two validations, ordinals 1 and 2, identities match slots |
| Campaign terminal | `status=OPERATIONAL_CAMPAIGN_TERMINAL`, `run_status=COMPLETED` |
| Campaign acceptance | `campaign_pass=True` (`CAMPAIGN_PASS`) |
| SQLite sidecars after close | None (`-wal`/`-shm`/`-journal` absent) |

## 12. Residue matrix

| Residue surface | Result |
| --- | --- |
| Scheduler active jobs | `0` |
| Scheduler locks | `0` |
| Active residue (`_active_counts`) | All zeros |
| Locked capability tables | All counts `0` (see §14) |
| Locked longer windows | None present |
| Authoritative corpus residue | Unchanged; not opened by this execution |

## 13. Database path, hash, migration, integrity, FK

### Disposable (execution-local)

| Item | Result |
| --- | --- |
| Name | `dtw23-migration-050.sqlite3` under pytest `TemporaryDirectory` |
| Creation | Fresh `apply_migrations(self.db)` only |
| Authoritative path patch in public command | Pointed at disposable DB for the public call only |
| Before/after hash | Asserted unequal (migrations/work wrote proof data) |
| Post-cleanup path | Removed by temp cleanup on PASS |
| Structured failure preserve | Not invoked |

### Authoritative corpus exclusion

| Item | Result |
| --- | --- |
| Path | `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3` |
| SHA-256 before | `d85442e630c2eac3b71021e2e3a33ecbd3a729517caf90aa9dbf936f08925cbe` |
| SHA-256 after | `d85442e630c2eac3b71021e2e3a33ecbd3a729517caf90aa9dbf936f08925cbe` |
| Size / mtime / inode before | `65806336` / `1785707543` / `1230526` |
| Size / mtime / inode after | identical |
| Opened or mutated by this lane | **No** |

### Migration / integrity / FK (in-process on disposable DB)

| Check | Result |
| --- | --- |
| Migration count | `50` |
| Migration head | `050_campaign_scheduler_ownership_scope.sql` |
| `PRAGMA integrity_check` | `ok` |
| `PRAGMA foreign_key_check` | zero violations (`[]`) |

## 14. Zero-network and locked-capability counts

| Boundary | Result |
| --- | --- |
| Application-level `urllib.request.urlopen` | call count `0` (`assert_not_called`) |
| Pump transport | Frozen fake create transport |
| Secondary transport | Frozen lawful secondary bodies |
| Snapshot / context | Fixture adapters only |
| RPC config | Patched to `https://unused.invalid` |
| Provider / WebSocket / wallet / signing / funds | Not used |
| Wrapper invocations | `0` (asserted in evidence dict) |
| External authorization create/apply | `0` |

`LOCKED_CAPABILITY_TABLES` (all asserted count `0`):

- `printer_memory_retrieval_queries`
- `printer_memory_retrieval_matches`
- `printer_paper_decisions`
- `printer_paper_positions`
- `printer_paper_trade_events`
- `printer_paper_trade_audits`
- `printer_paper_audit_reports`

`LOCKED_WINDOWS`: `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, `WINDOW_24H` — none present.

## 15. Retries / restarts / successors

| Counter | Value |
| --- | --- |
| Exact node invocations in this lane | **1** |
| `AUTOMATIC_RETRIES` | `0` |
| Reruns | `0` |
| Resumes | `0` |
| Restarts | `0` |
| Successors | `0` |
| Comparison execution | None |

## 16. Failure classification

Not applicable. Exact composition **PASS**.

No immutable first-failure package was required. Failure-only evidence helper was
not invoked. No root-cause capture path was taken.

## 17. External evidence inventory

Directory:
`/private/tmp/mp-v2-9-8b-exact-public-composition-20260803T202007Z-5125`

| Artifact | SHA-256 |
| --- | --- |
| `authorization.txt` | `f8b3e496b7f2b42979208b1d2692a685d7a774a1d3604e339a30dabced65df48` |
| `pytest.stdout.txt` | `fbffba9982ec2a8943f51b2ebee0253a5209bea13966b9aa137436a876a28b5f` |
| `pytest.stderr.txt` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `pytest.exit_code.txt` | `856d14a0981a4d175901614671ebd3910ed7eb34748e6e56ceb35def6097427e` |
| `canonical_before.sha256` / `canonical_after.sha256` | identical corpus digest records |
| `canonical_before.stat` / `canonical_after.stat` | identical size/mtime/inode |

## 18. Post-execution process and repository state

| Check | Result |
| --- | --- |
| HEAD | still `a84b80e2422d26e90bd31d4e2565b7d1e4722a91` before proof-report commit |
| Branch | unchanged |
| Tracked tree before report commit | clean |
| Relevant Printer / pytest process | none after completion |
| `/private/tmp/mp-preclaim` | still `8fb4256c70d4e81660c177238253322cb37ae947` |
| Second test run | **not performed** |

## 19. Money-usefulness contribution

This execution proves that the real public coordinator → authoritative owner →
origin driver → one-command factory chain can complete two owned compressed
`WINDOW_15M` lifecycles on a disposable Migration-050 database after the
test-only lifecycle-entry remapper lawfully forces disposable proof-mode entry,
without opening the authoritative corpus, without live network, and without
weakening production operational-persistent defaults.

That is the honest offline boundary for money-useful memory-factory composition:
discovery, activation, dual-slot lifecycle, Scheduler terminality, six-unit
accounting, and campaign acceptance all complete under frozen transports.

## 20. What improves

- Exact public composition is no longer an unexecuted residual after lifecycle-entry harness PASS.
- Lifecycle-entry remapper is proven on the real public chain, not only focused unit coverage.
- Authoritative-corpus exclusion is measured (byte-identical SHA-256 / stat) across the exact node.
- Failure-only evidence machinery remained silent on success, as designed.

## 21. What remains locked

- Live campaigns, provider contact, RPC, WebSocket, wallet, signing, and funds
- Authoritative corpus open/mutate outside explicit future authorization
- Production operational-persistent defaults and corpus preflight
- Retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits, PnL
- 1h / 4h / longer-window continuation
- Retry / restart / resume / successor automation
- Scoring, ranking, confidence, weights, embeddings, vectors, paid APIs
- Closeout of this exact composition (separate next lane)

## 22. Functionality Risks / Setbacks / Efficiency Blockers

| Item | Status |
| --- | --- |
| Success-path disposable DB not preserved | By design; failure path preserves. Row IDs not re-exportable without re-run (forbidden) |
| `DTW23_PROOF_EVIDENCE` under pytest capture | Present in-test; not in process stdout file on PASS |
| Application-level urllib patch | Not packet capture; zero call count only at that boundary |
| Frozen transports | Deterministic offline proof, not live provider proof |
| Test-only remapper | Not a production default change |

None of the above blocks the Full PASS verdict for this authorized offline node.

## 23. Next permitted lane

On this Full PASS:

`V2-9.8B Post-Rollover-2 Exact Public Composition Repair and Harness Closeout`

This lane stops after the proof-report commit. Closeout is **not** performed
here. The exact node is **not** rerun.

## 24. Stop condition

- Proof report created.
- Commit only the proof report with message `Prove exact offline public composition`.
- Do not push.
- Do not perform closeout.
- Do not rerun the exact node.
