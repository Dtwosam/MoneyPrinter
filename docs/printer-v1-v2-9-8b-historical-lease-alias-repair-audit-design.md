# Printer V1 V2-9.8B — Historical Disposable Lease Alias Repair Audit & Design

## Verdict

`V2_9_8B_HISTORICAL_DISPOSABLE_LEASE_ALIAS_REPAIR_DESIGN_PASS_READY_FOR_FOCUSED_TDD`

## Baseline

- Prior closeout: `01245f9d699ce01b534135287feaf1790c4a4a6b`
- Verified historical reconciliation implementation ancestor: `c5998516ff1782a2d65bebdac908543de3eafee6`
- Historical execution: `20260814T172224Z-490856f405bf`
- Expected authoritative DB SHA256: `5e830af41d58325d3f9e521f1b95f697b8151113cb783cf05a2a776e204639bc`
- Authoritative DB/artifacts/lease remain unchanged.

The real disposable-copy reproof reached the repaired discovery-batch contract, then blocked before mutation because `_historical_preflight()` requires the SQLite-recorded `lease_lock_path` to equal `artifact_root / "campaign.lease.lock"`. A byte-identical disposable DB necessarily still records the original absolute lease path, while a safe copied artifact root has a different path.

Classification: `DESIGN_GAP` with secondary `PROOF_HARNESS_PATH_COUPLING`.

## Audit conclusion

The blocker is real and fail-closed. The proof must not be unblocked by:

- passing the original artifact root, because canonical cleanup would delete the original lease;
- editing `lease_lock_path` in the disposable DB, because that breaks the pinned byte-identical DB identity and adds an unauthorized setup mutation;
- weakening the authoritative DB SHA contract;
- modifying `HistoricalFourTokenRecoveryContract()` for the proof;
- bypassing `cleanup_campaign_supervision()` or duplicating its terminalization SQL.

Adding only an expected lease-path field to `HistoricalFourTokenRecoveryContract` is insufficient. Even if preflight accepted a relocated path, `cleanup_campaign_supervision()` later reloads `lease_lock_path` from SQLite and calls `_release_lock()` on the recorded original path.

## Design decision

Preserve the historical SQLite row exactly and introduce a narrow **disposable lease alias** path only for the exact historical reconciliation proof.

Normal and authoritative cleanup must continue to release the SQLite-recorded lease path exactly as today.

The disposable mode is not a generic runtime lease override and must not be exposed through discovery, Scheduler, factory, or campaign runtime surfaces.

## Recorded lease identity

Do not hard-code or derive a user-specific absolute Mac path in the contract.

The already-required exact pre-reconciliation DB SHA cryptographically binds the persisted `lease_lock_path` value. Therefore the recorded lease path read from the exact-SHA supervision row is itself the authoritative historical path for this one execution.

Do not persist a replacement path in SQLite.

## Historical recovery API

`reconcile_exact_historical_four_token_execution()` may gain one optional keyword-only parameter:

`disposable_lease_alias: str | Path | None = None`

Default `None` preserves current authoritative behavior.

When supplied, all of the following are mandatory before any DB write:

1. `disposable_lease_alias.resolve() == (artifact_root / "campaign.lease.lock").resolve()`;
2. the SQLite-recorded lease path remains unchanged and is distinct from the alias;
3. the original recorded lease exists;
4. the disposable alias exists;
5. original and alias lease bytes are identical at preflight;
6. both payloads satisfy the existing exact supervision ownership checks;
7. lease expiry/payload facts match the durable supervision row;
8. authoritative DB SHA and all existing historical preflight guards remain unchanged.

Because the DB SHA is checked before these path checks, a caller cannot relocate the persisted lease path without failing the existing authoritative identity gate.

Store the original recorded lease bytes/hash in preflight evidence so post-proof preservation is independently checked.

Without `disposable_lease_alias`, preserve the existing rule that the recorded lease path must equal `artifact_root / "campaign.lease.lock"`.

## Cleanup ownership

Do not create a second terminalization implementation.

Refactor only enough for the existing `cleanup_campaign_supervision()` body to have one internal implementation with an optional private release-path input. Public `cleanup_campaign_supervision()` must continue to call that implementation without an override.

The exact historical recovery path may call the internal implementation with the preflight-validated disposable alias.

The internal alias branch must:

- validate the alias before transactional DB mutation;
- require alias path != recorded path;
- require alias bytes equal the recorded lease bytes before mutation;
- use the existing `_exact_lock()` ownership check on both files;
- perform the same canonical DB cleanup transaction as normal cleanup;
- call the same `_release_lock()` against only the alias;
- persist `lease_released_at` only in the disposable DB;
- prove the original recorded lease still exists and is byte-identical after alias release;
- return explicit evidence such as `lease_release_mode="DISPOSABLE_ALIAS"` and `recorded_lease_preserved=True`.

The public/default path remains `lease_release_mode="RECORDED"` and must be behaviorally unchanged.

## Replay contract

`_historical_already_reconciled()` must remain strict.

Default/authoritative mode continues to require the SQLite-recorded lease to be absent after reconciliation.

Disposable alias mode may report `ALREADY_RECONCILED` only when:

- the exact historical DB terminal state is correct;
- `lease_released_at` is durable;
- the disposable alias is absent;
- the recorded original lease still exists;
- the recorded original lease remains byte-identical to its pre-proof evidence / exact ownership payload;
- all existing batch, queue, factory, provenance and locked-capability checks pass.

A caller cannot obtain disposable replay semantics merely because the recorded lease still exists; the explicit validated alias mode is required.

## Exact DB mutation set

The approved DB mutation set remains exactly the existing ten historical row identities. No lease-path column change is added.

Filesystem mutation in disposable mode is exactly one copied alias deletion. The original historical lease is read-only evidence and must remain unchanged.

## Focused RED/GREEN

Minimum sufficient TDD:

1. exact byte-identical disposable DB + copied artifact root fails under current path-coupled implementation;
2. repaired disposable alias mode reaches reconciliation without changing SQLite `lease_lock_path`;
3. alias is deleted, recorded original lease is preserved byte-for-byte;
4. first invocation still changes exactly ten DB identities;
5. second invocation returns `V2_9_8B_HISTORICAL_FOUR_TOKEN_ALREADY_RECONCILED` with zero writes in alias mode;
6. alias missing before first run fails before DB mutation;
7. alias bytes/payload differing from recorded lease fails before DB mutation;
8. alias pointing at the recorded original path fails before DB mutation;
9. default historical mode still rejects a relocated artifact root without alias;
10. default cleanup still releases its recorded lease and existing operational lease tests remain green;
11. historical discovery-batch repair tests remain green;
12. `py_compile` and `git diff --check` pass.

Use the nearest affected campaign-supervision and historical-reconciliation tests only. No broad suite is required for this narrow proof-path repair.

## Disposable reproof after implementation

Repeat the real Mac-local proof from a byte-identical DB copy and copied historical artifact root using unmodified `HistoricalFourTokenRecoveryContract()` plus only the explicit `disposable_lease_alias` argument.

Required proof remains:

- first call `V2_9_8B_HISTORICAL_FOUR_TOKEN_RECONCILED`;
- exactly ten DB row identities changed;
- copied alias removed;
- original recorded lease unchanged;
- Scheduler/discovery work unchanged;
- windows/steps/Cycle-2 attempts zero;
- migration ledger 55/head 055 and no migration-056 provenance;
- integrity/FK clean;
- locked retrieval/financial hashes unchanged;
- second call `V2_9_8B_HISTORICAL_FOUR_TOKEN_ALREADY_RECONCILED` with zero writes and unchanged post-first-run DB SHA;
- authoritative DB/artifacts/original lease unchanged.

Only after that reproof closes PASS may authoritative historical reconciliation be considered.

## Money-usefulness contribution

This repair makes the exact historical cleanup provable without risking the authoritative evidence set. It restores a trustworthy route toward bounded memory-growth operations but creates no trading or retrieval capability.

## What this improves

- disposable proof isolation;
- preservation of the authoritative lease evidence;
- faithful exercise of the canonical cleanup logic;
- proof of the same ten-row DB terminalization contract without pre-editing the copied DB;
- truthful idempotent replay under explicit proof context.

## What remains locked

No authoritative reconciliation, fresh proof authorization, new four-token proof, six-token widening, longer-window activation, retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events/audits, or PnL is unlocked.

## Functionality Risks / Setbacks / Efficiency Blockers

- A generic public lease override would be too dangerous because it could mark a real supervision row released while preserving its actual lease file. The alias path must stay internal to the exact historical proof path.
- Replay must distinguish authoritative recorded-lease removal from disposable alias removal or it can falsely claim success.
- The original lease must be checked again after alias release; preflight-only equality is insufficient.
- Refactoring campaign supervision cleanup can affect safety-critical ownership logic. Keep the DB mutation body single-sourced and run the nearest operational lease tests.
- Do not add transient SQLite lease-path rewrites even if restored later; they would widen the proof beyond the approved mutation contract.
