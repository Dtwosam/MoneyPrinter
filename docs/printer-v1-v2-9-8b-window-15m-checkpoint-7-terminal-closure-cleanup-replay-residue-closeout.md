# Printer V1 V2-9.8B WINDOW_15M Checkpoint 7 — Terminal Closure, Cleanup, Replay, and Residue Closeout

## Verdict

`V2_9_8B_WINDOW_15M_CHECKPOINT_7_TERMINAL_CLOSURE_CLEANUP_REPLAY_RESIDUE_PASS`

Checkpoint 7 is complete through audit, design, fail-first regression proof, implementation, bounded focused proof, and closeout.

- Checkpoint 6 baseline: `b6890b7bf8788c6a2b22b4a72acc26352e776248`
- Checkpoint 7 audit commit: `48f246eda72926ee981004fa5e34ccc1e7e49371`
- Checkpoint 7 design commit: `46bb16889b394e442365104064156cb83cdfbcb8`
- Fail-first contract commit: `b5e44e5562142340d38068348c19b9cad8090415`
- Implementation commit: `276063d3f7c08619eb5d128ee9175d84a700a5a1`
- Branch: `agent/v2-9-8b-window-15m-checkpoint-7-terminal-closure-cleanup-replay-residue`
- Linear: `DTW-33`

No provider/RPC/WebSocket call, Source Governor runtime, Central Scheduler runtime, public campaign execution, authoritative database mutation, memory generation, retrieval, paper decision, BUY/SELL/HOLD, position, trade, paper-trade audit, PnL, live wallet/key/execution, paid API, embedding/vector, longer-window activation, or Checkpoint 8 work occurred in this closeout.

## Four confirmed blockers repaired

### 1. `INITIALIZED_FAILURE_PRECISE_CAUSE_COLLAPSED_TO_EXCEPTION_CLASS`

Initialized operational failures previously collapsed safe categorical owned exception codes into the class fallback `OPERATIONAL_CAMPAIGN_FAILED:<ExceptionClass>`.

Repair:

- existing durable first cause remains authoritative;
- heartbeat cause retains precedence when present;
- otherwise only `.code` from `LiveOperationalError` / `LiveTransportError` is eligible;
- the code must match `^[A-Z][A-Z0-9_]{1,127}$`;
- `.detail`, `str(exc)`, provider bodies, URLs, headers, secrets, and arbitrary attributes are never promoted into durable first cause;
- generic class-only fallback remains when no safe owned categorical code exists.

This improves diagnosis precision without weakening terminal-cause safety.

### 2. `FAILURE_TERMINAL_REPORT_CAN_PERSIST_WITH_UNPROVEN_CLEANUP_OR_LEASE_RELEASE`

The initialized-failure path could reach canonical terminal report publication after cleanup errors, even when durable cleanup closure was not proven.

Repair:

Canonical failure-report publication now requires all of:

- exact `supervision_id`, `campaign_id`, `configuration_id`, `run_id`, and `owner_id` identity;
- `cleanup_completed is True`;
- `lease_released is True`;
- `active_owned_work_after` is an integer equal to `0`.

If those facts are not proven:

- canonical report publication is blocked;
- `report_written=False`;
- `report_block_reason="TERMINAL_CLEANUP_UNPROVEN"`;
- bounded terminal diagnostic evidence remains available;
- no retry, restart, resume, or successor is created.

### 3. `TERMINAL_REPORT_ROW_AND_ARTIFACT_PERSISTENCE_NOT_ATOMIC`

The report owner previously committed the authoritative SQLite report row before writing its required artifact, so an artifact-write failure could leave DB authority without the matching durable artifact.

Repair:

The publication protocol is now artifact-first and fail-closed:

1. validate required six-unit evidence;
2. compute exact canonical JSON and report hash;
3. resolve the canonical artifact path;
4. if an artifact already exists, require exact canonical bytes;
5. if absent, create an exact sibling temporary file;
6. write canonical bytes, `fsync` the temporary file, then atomically `os.replace` it into the final artifact path;
7. only after exact artifact publication, persist the authoritative report row;
8. if DB persistence fails after this invocation created the artifact, attempt compensating artifact deletion;
9. after DB persistence, re-read and require exact artifact bytes before success.

SQLite and the filesystem are not one physical transaction, so this protocol deliberately makes the artifact-only state non-authoritative while preventing a DB-authoritative report from being created before its artifact exists.

### 4. `PUBLIC_REPORT_ONLY_IGNORES_ARTIFACT_MISMATCH`

Lower replay already calculated `artifact_matches`, but public `report_only()` could continue into later acceptance/reconstruction checks instead of failing immediately on artifact mismatch.

Repair:

- public report-only now requires `replay.get("artifact_matches") is True` before later full-run reconstruction;
- mismatch returns `REPLAY_BLOCKED` with `TERMINAL_REPORT_ARTIFACT_MISMATCH`;
- replay remains zero-source, zero-Scheduler-runtime, and zero-write;
- later reconstruction cannot override the artifact-parity block.

## Historical fixture correction

One historical report-only fixture hand-built an artifact that was not actually canonical:

- it used `<report_id>.json` instead of the terminal owner's canonical `<report_id>.campaign-report.json` suffix;
- it added a trailing newline not present in the canonical report bytes.

Checkpoint 7 artifact parity correctly exposed that fixture defect. The fixture was corrected to use the canonical filename and exact bytes so it continues testing its intended historical `FULL_RUN_EVIDENCE_MISSING` behavior instead of accidentally testing artifact mismatch.

No production rule was weakened to preserve the stale fixture.

## Fail-first proof

The exact Checkpoint 7 RED module was first observed against the active fail-first baseline `b5e44e5562142340d38068348c19b9cad8090415`.

Result:

- `4 failed`;
- each failure mapped to one audited blocker;
- no unexpected fifth blocker appeared.

Observed RED behavior:

1. safe `LiveOperationalError.code` collapsed to `OPERATIONAL_CAMPAIGN_FAILED:LiveOperationalError`;
2. cleanup failure still reached canonical report publication;
3. artifact-write failure still allowed the DB persistence seam first;
4. public report-only did not block immediately on lower replay artifact mismatch.

This cleared the implementation gate without source fetching, runtime execution, or authoritative DB mutation.

## Bounded GREEN proof

The controlling implementation proof used disposable worktrees and disposable SQLite/artifact fixtures only.

Pre-repair focused baseline:

- `32 passed`.

Disposable post-repair proof:

- changed-module `py_compile` PASS;
- four Checkpoint 7 contracts: `4 passed`;
- focused existing regressions: `32 passed`;
- atomic artifact protocol static checks PASS (`tempfile.mkstemp`, `os.fsync`, `os.replace`);
- `git diff --check` PASS;
- canonical artifact fixture proof PASS.

Active Checkpoint 7 worktree proof after applying the exact disposable diff:

- four Checkpoint 7 contracts: `4 passed`;
- focused existing regressions: `32 passed`;
- changed-module compilation PASS;
- `git diff --check` PASS;
- implementation commit created and pushed as `276063d3f7c08619eb5d128ee9175d84a700a5a1`;
- `CHECKPOINT7_CHECKPOINT8_NOT_STARTED` confirmed.

The focused regression set covered the changed terminal/report owners and their immediate contracts:

- child-terminal first-cause propagation;
- heartbeat/supervision cleanup and lease behavior;
- full-run terminal report and acceptance behavior;
- durable cleanup timestamp and replay reconstruction behavior;
- exact-identity zero-side-effect report-only behavior;
- a real disposable report-writer path.

A broad repository suite was intentionally not required because unrelated historical fixture/test debt had already been identified and the Checkpoint 7 change was confined to the named terminal/report owners. This follows the repository's risk-based verification policy.

## Exact implementation manifest

The implementation commit changes exactly three files:

- `src/printer_v1/operator_cli/operational_memory_factory_command.py`;
- `src/printer_v1/operator_cli/unified_terminal_closure.py`;
- `tests/test_v2_9_8b_accounting_exact_identity_report_only_repair.py` (canonical historical artifact fixture correction only).

No discovery, source adapter, Scheduler, memory-generation, retrieval, paper-decision, position/trade, or longer-window production owner changed.

## Money-usefulness contribution

Checkpoint 7 makes a terminal campaign result trustworthy enough to be used as a stopping and audit boundary for later memory-growth operations:

- the operator gets the most precise safe categorical failure reason available;
- a canonical failure report cannot claim closure before cleanup, lease release, and zero active owned work are proven;
- DB authority cannot be created before the exact report artifact exists;
- report-only replay cannot accept DB-only evidence when the archived artifact is missing or different.

This improves the reliability of future paper-only learning evidence without activating retrieval or financial decision capability.

## What this checkpoint improves

- safe initialized first-cause precision;
- failure terminal cleanup/lease/residue gating;
- exact terminal report row/artifact publication integrity;
- deterministic artifact-first idempotency and recovery behavior;
- public report-only artifact parity;
- preservation of zero-source / zero-Scheduler-runtime / zero-write replay;
- preservation of no retry/restart/resume/successor terminal behavior.

## What this checkpoint still does not unlock

Checkpoint 7 does not unlock:

- retrieval activation;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions;
- trade events;
- paper-trade audits;
- PnL;
- live wallet, private keys, signing, execution, or real funds;
- paid API dependency;
- scoring/ranking/confidence/weighted systems;
- embeddings/vectors;
- new `WINDOW_1H` proof rerun;
- `WINDOW_4H` / `WINDOW_12H` / `WINDOW_24H` activation;
- Checkpoint 8.

`WINDOW_5M_MICRO_EVENT` remains support-only and cannot independently unlock retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.

## Functionality Risks / Setbacks / Efficiency Blockers

1. SQLite and the filesystem cannot participate in one physical atomic transaction. The artifact-first + compensation protocol is therefore fail-closed rather than physically transactional.
2. A process crash after atomic artifact publication but before DB persistence can leave an artifact-only orphan. That artifact is non-authoritative because no terminal report row exists; exact same-payload publication can complete it idempotently later.
3. Compensating deletion after DB persistence failure is best-effort. If deletion itself fails, the remaining artifact is still non-authoritative without the DB row.
4. Safe initialized-cause extraction must remain deliberately narrow. Expanding it to arbitrary exception text would risk persisting provider or secret-bearing details.
5. Strong artifact parity can expose historical fixtures or artifacts that were not written using canonical filename/byte rules. The correct response is to classify/repair those fixtures or evidence explicitly, not weaken parity.
6. This closeout does not prove the full disposable public composition required by Checkpoint 8; that remains a separate explicitly bounded checkpoint.

## Closeout boundary

Checkpoint 7 is complete.

The next roadmap checkpoint is Checkpoint 8 / `DTW-34` — full disposable public-composition proof and independent closeout — only if separately started. This Checkpoint 7 closeout does not authorize or begin Checkpoint 8.
