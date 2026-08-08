# Printer V1 V2-9.8B Post-C8 Local Operational Lineage and One-Shot Staging Reconciliation — Phase 1 Audit

Date: 2026-08-08

Linear: `DTW-71`

## Verdict

`V2_9_8B_POST_C8_LOCAL_OPERATIONAL_LINEAGE_STAGING_PHASE1_PASS_ALIGNMENT_ALLOWED`

Phase 1 is complete. The local Mac worktree may proceed to the approved non-destructive branch alignment defined by the DTW-71 design. No authorization, provider/source call, Printer/Scheduler runtime, authoritative DB mutation, memory generation, longer window, retrieval, decision, position, trade, audit, or PnL action is authorized by this PASS.

## Immutable target

Remote immutable target branch:

`agent/v2-9-8b-post-c8-operational-window15m-rereadiness-target`

Exact target HEAD:

`cd0a422d84a0076dd03ba34f1a764fc8795f6aaf`

Fresh fetch reproduced that exact SHA.

Local pre-alignment state:

- branch `agent/v2-9-8b-window-15m-fresh-authorization-after-source-request-scope-enforcement`;
- HEAD `7defc2945c42053d9c770ebc66248d27c63ff4a3`;
- ancestry to target PASS;
- tracked/index state clean;
- untracked file count `15`;
- target tracked-file count `1573`;
- exact untracked-vs-target collision count `0`.

The old local branch pointer must remain unchanged. No reset/clean/stash/force checkout is permitted.

## Authoritative DB identity — unchanged

Fresh pre-alignment identity:

- path `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3`;
- SHA-256 `7380f9b4c172c218e6c9ab1fed996a06fcdeb90ff67f2b414d805f280403d54e`;
- size `69328896`;
- inode `1230526`;
- WAL `false`;
- SHM `false`;
- journal `false`.

Factory-run truth:

- `COMPLETED = 3`;
- `SAFE_STOPPED = 4`;
- no active factory-run state observed.

The earlier DTW-70 fresh capture already established exact 52/52 migration-ledger equality, integrity `ok`, foreign-key violations `0`, and terminal-only campaign/run/cycle/supervision/discovery/Scheduler states. Phase 1 did not mutate SQLite.

## One-shot staging classification

Seven external staging directories were inspected read-only.

### Historical consumed staging residue

1. `V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z-8c6effa328cd4a6fa05b5e2e016a273d`
   - canonical application marker present;
   - wrapper terminal present;
   - marker invocation count `1`;
   - no retry/rerun/resume/restart/successor;
   - classification `HISTORICAL_CONSUMED_STAGING_RESIDUE`.

2. `V2_9_8B_WINDOW_15M_AUTH_20260804T214901Z-c1b4d8360ddb485dbbeadfb0f5773c46`
   - canonical application marker present;
   - wrapper terminal present;
   - marker invocation count `1`;
   - no retry/rerun/resume/restart/successor;
   - classification `HISTORICAL_CONSUMED_STAGING_RESIDUE`.

### Historical unconsumed pre-marker residue

3. `V2_9_8B_WINDOW_15M_AUTH_20260806T005252Z-3778d27807ff40edac6e9ac961b78ea9`
4. `V2_9_8B_WINDOW_15M_AUTH_20260806T005252Z-f47145e2df5b41bea6e44475c8c464ba`
   - no canonical marker;
   - authorization explicitly expired `2026-08-07T00:52:52.316353Z` and was previously classified superseded;
   - classification `HISTORICAL_UNCONSUMED_PREMARKER_RESIDUE`.

5. `V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z-bae5318756834afa8218bc1874e712fd`
   - no canonical application directory, marker, or wrapper terminal;
   - one staging `git-provenance-manifest.json` only;
   - authorization issued `2026-08-03T20:48:00.842758+00:00`;
   - printed `expires_at` was null;
   - current post-C8 temporal owner `authorization_temporal_validity.py` centrally caps validity/age at 86,400 seconds and requires either an explicit expiry or a positive validity span that cannot exceed 86,400 seconds;
   - therefore on 2026-08-08 this package is necessarily rejected as missing-expiry, expired, over-max-age, or over-age before any staging/marker/consumption side effect, regardless of whether the historical document contains an unprinted `validity_seconds` field;
   - classification `HISTORICAL_UNCONSUMED_PREMARKER_RESIDUE`.

This classification does not delete or rewrite the residue and does not make the authorization reusable.

### Test/simulation residue

6. `index-restoration-premarker`
7. `sim-preauth`
   - no authorization identity;
   - no canonical application or marker;
   - no production authority;
   - classification `TEST_OR_SIMULATION_PREMARKER_RESIDUE`.

## Why the August 3 package cannot block alignment

The current temporal validation law is pure pre-consumption validation and enforces:

- timezone-aware `authorized_at`;
- explicit `expires_at` or derivation from `validity_seconds`;
- maximum validity `86400` seconds;
- maximum issue age `86400` seconds;
- expiry and over-age rejection.

Thus the August 3 package is historical evidence only. It cannot become a current one-use authority on August 8 and cannot lawfully survive the current wrapper's pre-marker temporal gate.

## Alignment authorization boundary

Phase 2 may now:

- create a new local branch named exactly `agent/v2-9-8b-post-c8-operational-window15m-rereadiness-audit` from the fetched immutable target branch;
- preserve all untracked `operator-runs/` evidence;
- preserve `~/PrinterOperations` staging/application evidence;
- preserve the authoritative DB byte-for-byte;
- leave the prior local branch pointer unchanged.

Phase 2 must not:

- use `git reset --hard`, `git clean`, stash, force checkout, or delete evidence;
- move the old branch pointer;
- create/consume authorization;
- run providers, Source Governor, Central Scheduler, Printer runtime, or memory generation;
- activate longer windows, retrieval, decisions, positions, trades, audits, or PnL.

## Required bounded post-alignment proof

After the branch switch, require only:

1. exact local branch name;
2. exact HEAD `cd0a422d84a0076dd03ba34f1a764fc8795f6aaf`;
3. tracked/index clean;
4. untracked evidence still present;
5. DB SHA remains `7380f9b4c172c218e6c9ab1fed996a06fcdeb90ff67f2b414d805f280403d54e`;
6. no SQLite sidecars;
7. migration ledger still 52/52, integrity/FK clean;
8. factory and other operational state remains non-active;
9. zero-I/O concrete-composition preflight PASS.

No broad test suite is needed.

## Money-usefulness contribution

Phase 1 proves the real Mac operator checkout can be advanced onto the completed Checkpoint-hardened code without overwriting operator evidence or changing the clean authoritative corpus. It removes the environmental blocker that would otherwise risk burning a future one-use authorization against obsolete code.

## What remains locked

Everything beyond non-destructive local alignment and read-only proof remains locked. In particular: no authorization, provider/source access, runtime, DB mutation, memory generation, WINDOW_1H+, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, paper-trade audits, PnL, wallets/private keys/signing/real funds/live execution, paid APIs, scoring/ranking/confidence/weighting, embeddings, or vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only.

## Functionality Risks / Setbacks / Efficiency Blockers

- Historical staging remains on disk by design; its existence must not be mistaken for current authority.
- The local branch switch must target the immutable `cd0a422...` branch, not a moving development branch.
- Any unexpected local branch-name collision must stop the switch rather than force-update it.
- DB identity must be rechecked immediately after alignment.
- No cleanup of staging or untracked evidence belongs in this lane.

## Stop condition

Phase 1 stops at `PASS_ALIGNMENT_ALLOWED`. Proceed only with the exact non-destructive local alignment and bounded read-only proof.