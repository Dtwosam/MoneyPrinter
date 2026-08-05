# V2-9.8B WINDOW_15M Authorization and Proof-Retention Integration Repair Closeout

## Verdict

`V2_9_8B_WINDOW_15M_AUTHORIZATION_RETENTION_INTEGRATION_REPAIR_PASS`

Both approved repairs and their focused negative-path tests pass. This closeout
does not authorize the continuous proof, provider contact, discovery runtime,
Central Scheduler runtime, memory generation, authoritative-database mutation,
retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL,
wallets, signing, funding, or live execution.

## Baseline and branch

- Required baseline branch:
  `agent/v2-9-8b-window-15m-safe-stop-holder-accounting-repair`
- Required baseline HEAD:
  `e59b56674dd0bfa131ca5b4b25b5c47056c6c2e0`
- Repair branch:
  `agent/v2-9-8b-window-15m-authorization-retention-integration-repair`
- Baseline branch, exact HEAD, ancestry, clean tracked state, inactive database,
  and authoritative database identity were verified before branch creation.

## Files changed

- `src/printer_v1/operator_cli/operational_database_target_binding.py`
- `src/printer_v1/operator_cli/operational_memory_factory_command.py`
- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
- `src/printer_v1/operator_cli/one_command_15m_factory.py`
- `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py`
- `src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py`
- `src/printer_v1/operator_cli/continuous_proof_evidence_retention.py`
- `tests/support/window_15m_authorization_fixtures.py`
- `tests/test_v2_9_8b_window_15m_authorization_retention_integration_repair.py`
- `tests/test_v2_9_8b_window_15m_safe_stop_holder_accounting_repair.py`
- `tests/test_v2_9_8b_window_15m_git_provenance_authorization_manifest.py`
- `tests/test_v2_9_8b_window_15m_one_shot_wrapper.py`
- `tests/test_v2_9_8b_window_15m_final_integrated_continuous_proof.py`
- `tests/test_v2_9_8b_exact_public_composition_900_logical_seconds.py`
- `tests/test_v2_9_8b_exact_offline_public_composition_lifecycle_entry_harness.py`
- `tests/test_v2_9_8b_token_slot_id_exact_public_composition.py`
- `tests/test_v2_9_8b_end_to_end_pre_lifecycle_failure_propagation.py`
- `tests/test_v2_9_8b_post_rollover_2_pre_lifecycle_factory_run_identity_and_terminal_contract_repair.py`
- `tests/test_v2_9_8b_token_slot_id_projection_repair.py`
- this closeout

## Repair A — independent authorization validation

PASS.

Ordinary operational `run` mode now requires the existing fully validated
Git-provenance authorization object before binding construction. Its real
authorization ID, manifest SHA-256, application-marker SHA-256, consumption
state, current invocation count, allowed invocation count, and five reuse flags
are projected from the validated manifest/application-marker boundary. The
authorization document's independently pinned database path, pre-mutation
SHA-256, and migration count/head are carried through pre-marker and post-marker
validation, compared between those stages, and required to agree with the
read-only operational preflight before campaign artifacts are created. The
previous execution-ID authorization fallback, generated authorization-hash
fallback, and authorization-hash-as-application-marker fallback are removed.

The existing campaign configuration owner now persists one versioned
`operational_database_target_expectation` before campaign execution. It binds
the authorized pre-mutation SHA-256, authorization and marker identities,
migration count/head, execution/campaign/run/cycle/configuration identities,
durable DB-target identity, actual consumption/invocation facts, and exact
retry/rerun/resume/restart/successor prohibitions.

Both the authoritative operational owner and lifecycle factory independently
load this expectation from the durable configuration row by exact ownership.
They validate the immutable binding against that loaded evidence rather than
reconstructing expected values from the binding. Missing or incomplete durable
expectations fail closed. Binding version is exact, and direct
operational-persistent callers without durable expectation cannot validate.

Focused tests prove forged authorization identity, manifest hash, application
marker, consumption state, invocation count, reuse permission, target kind,
ownership, and binding version fail categorically. The public factory terminal
preserves the exact authorization mismatch reason.

## Repair B — failure-safe proof retention

PASS for implementation and focused tests. Proof NOT RUN.

`FailureSafeProofRetention` is the single post-child retention owner. On entry
it creates the external retained directory and immediately copies raw child
stdout, raw child stderr, and the wrapper terminal when present. It then supports
terminal parsing/preservation and incremental campaign/diagnostic artifact
registration. Finalization runs on success or failure, records categorical
absence for every unavailable mandatory artifact, hashes and rereads every
present retained file, completes `artifact-hashes.json`, and records the
external retained-directory identity.

The first proof failure remains primary. Retention failures are attached as
secondary notes when an earlier exception exists. Missing evidence never becomes
an empty success artifact.

The future continuous-proof harness establishes this owner immediately after the
single child returns, checks a nonzero child result only after raw retention has
started, parses through the retention owner, registers later proof/report/
diagnostic artifacts, and uses guaranteed unittest cleanup before disposable
temporary teardown. Successful completion finalizes the same owner exactly once.

Focused tests prove retained packages after child-terminal parse failure, child
nonzero result, missing campaign report, missing holder diagnostics, slot-count
assertion failure, zero-window lifecycle blocker, unexpected post-child
exception, and success. Every blocked case proves surviving raw streams/wrapper,
`artifact-hashes.json`, categorical absence, reread hash equality, and original
first-failure preservation.

## Authoritative database identity

The authoritative database remained inactive and unchanged.

| Property | Before | After |
|---|---:|---:|
| Path | `data/printer_v1.sqlite3` | same |
| Device | `16777233` | same |
| Inode | `1230526` | same |
| Size | `68067328` bytes | same |
| mtime | `1785925095` | same |
| SHA-256 | `ecf0557cf213b44b51f840983e5472a53777f609dee650580d1844e7b01ac2bb` | same |
| WAL/SHM/journal sidecars | none | none |
| Active Printer/database process | none | none |

No authoritative database connection or mutation was used by the repair tests.

## Tests and checks

- New focused authorization integration tests: `20 passed`.
- New focused failure-retention tests: `8 passed`.
- Existing safe-stop/holder-accounting repair suite: `31 passed`.
- Git-provenance authorization, one-shot wrapper, and exact public-composition
  regressions: `103 passed`.
- Directly affected final-readiness regressions: `22 passed`.
- Continuous-proof harness: `1 test collected`; proof test NOT RUN.
- Python compilation for all changed Python modules and tests: PASS.
- `git diff --check`: PASS.
- Continuous proof, provider calls, discovery runtime, Scheduler runtime, and
  memory generation: NOT RUN.

One intentionally broader diagnostic selection exposed one unrelated historical
assertion in
`test_v2_9_8b_post_rollover_2_pre_lifecycle_factory_run_identity_and_terminal_contract_repair.py`:
it expects `UNKNOWN_ON_EXCEPTION`, while the current baseline terminal owner
returns `UNKNOWN_NOT_ATTRIBUTABLE`. This lane did not change that owner or weaken
the assertion; the required and directly affected focused suites are green.

## What was not touched

- Holder identity generation and holder budget arithmetic.
- Freeze depth, candidate selection, Source Governor, or Central Scheduler.
- Memory promotion, fingerprints, retrieval, paper decisions, financial tables,
  or capability locks.
- Database migrations or authoritative database contents.
- Provider contracts, endpoints, budgets, retries, or runtime scheduling.

## Money-usefulness contribution

The repair prevents a forged or self-confirming authorization binding from
reaching memory-growth lifecycle work and ensures a failed one-shot proof retains
enough trustworthy evidence for diagnosis without spending another
authorization. This protects corpus provenance and bounded operational evidence
without adding a signal, score, decision, position, or financial action.

## Functionality Risks / Setbacks / Efficiency Blockers

### Functionality risks

- The proof harness finalizer depends on mandatory artifact names remaining
  synchronized with future report producers; new mandatory evidence must be
  added to both surfaces.
- Test-only public-composition fixtures explicitly bypass strict holder-stage
  sealing because holder accounting is covered by its focused suite; they must
  never be treated as authorization/proof fixtures.
- A malformed durable configuration fails closed as expectation missing or
  incomplete; operators must preserve the configuration artifact for review.

### Setbacks

- No continuous proof was run, so this lane does not establish end-to-end live
  artifact availability.
- The historical consumed authorization remains unusable and was not recreated.
- The unrelated terminal-status assertion remains repository maintenance debt
  outside this lane.

### Efficiency blockers

- Complete retention copies and rereads every present mandatory artifact before
  teardown, intentionally adding bounded I/O.
- Any future marker/configuration contract change requires synchronized wrapper,
  validator, configuration-owner, and focused-test updates.

## Remaining locks

All V1/V2 locks remain in force: Solana memecoin-only, paper-only, no wallet,
private key, signing, funds, live execution, paid API, scoring, ranking,
confidence, weighting, embeddings/vectors, Source Governor bypass, Central
Scheduler bypass, retrieval, paper decisions, BUY/SELL/HOLD, positions, trade
events, paper audits, PnL, production 1h/4h/12h/24h activation, automatic retry,
rerun, resume, restart, recovery, or successor.

## Next recommended phase

One independent read-only implementation review of this repair and closeout.
PASS does not authorize the continuous proof. Any later proof still requires a
fresh exact-HEAD authorization and separate operator approval under the active
build order.
