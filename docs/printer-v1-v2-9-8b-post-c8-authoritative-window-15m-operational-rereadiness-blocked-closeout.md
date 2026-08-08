# Printer V1 V2-9.8B Post-C8 Authoritative WINDOW_15M Operational Re-Readiness Audit — BLOCKED Closeout

Date: 2026-08-08

Linear: `DTW-70`

## Verdict

`V2_9_8B_POST_C8_AUTHORITATIVE_WINDOW_15M_OPERATIONAL_REREADINESS_BLOCKED_LOCAL_LINEAGE_AND_STAGING_RECONCILIATION_REQUIRED`

This audit is complete and truthfully BLOCKED. The authoritative database side passes the requested fresh read-only checks, but the local operational checkout is still on a pre-Checkpoint-8 lineage and the one-shot application root contains unclassified historical staging residue. No authorization or runtime is permitted from this state.

## Fresh Mac evidence

Current local repository:

- branch `agent/v2-9-8b-window-15m-fresh-authorization-after-source-request-scope-enforcement`;
- HEAD `7defc2945c42053d9c770ebc66248d27c63ff4a3`;
- tracked/index clean;
- only operator-evidence paths reported untracked.

GitHub ancestry verification establishes that the current DTW-70 audit head `89fbb1773b2b7daba49f7c84533ad75da208c3a8` is 214 commits ahead of local HEAD and local HEAD is its merge base. Therefore the local checkout does not contain the completed Checkpoint 1-8 hardening sequence or the post-C8 reconciliation/audit documentation.

## Authoritative DB — fresh PASS

Path: `data/printer_v1.sqlite3`

Fresh identity:

- size `69328896`;
- inode `1230526`;
- SHA-256 `7380f9b4c172c218e6c9ab1fed996a06fcdeb90ff67f2b414d805f280403d54e`;
- WAL absent;
- SHM absent;
- journal absent.

Fresh SQLite checks:

- `PRAGMA integrity_check = ok`;
- foreign-key violations `0`;
- applied migration count `52`;
- canonical migration count `52`;
- latest applied/canonical `052_memory_observation_eligibility_layers.sql`;
- exact ordered migration validation `matches=true`, `issues=[]`.

The DB is byte-identical to the retained post-2026-08-06 historical baseline. This is now a fresh 2026-08-08 attestation rather than merely historical context.

## Operational residue — fresh PASS for observed state surfaces

Fresh grouped states show no non-terminal rows on the reported operational surfaces:

- campaign runs: 12 `TERMINAL_COMPLETED`, 20 `TERMINAL_FAILED`;
- campaign cycles: same terminal split;
- supervision: 32 `TERMINAL`;
- campaign windows: 2 `CANCELLED`;
- discovery work: 78 `SUCCEEDED`, 2 `FAILED`;
- campaign Scheduler work: 8 `SUCCEEDED`, 2 `CANCELLED`;
- Scheduler jobs: 1316 `SUCCEEDED`, 14 `FAILED`, 45 `CANCELLED`.

No active Scheduler state is visible in the fresh capture. `printer_memory_factory_runs` was present with 7 rows but the generic capture did not find a recognized state-column name, so exact factory-run terminal-state grouping remains a narrow follow-up check after lineage alignment; it is not evidence of active work by itself.

## Authorization evidence

Fourteen repository authorization packages were visible. The latest package remains `V2_9_8B_WINDOW_15M_AUTH_20260806T131011Z`, whose corresponding external application marker and wrapper terminal are present and therefore consumed/non-reusable.

`V2_9_8B_WINDOW_15M_AUTH_20260806T005252Z` has no canonical application marker and was previously classified `BLOCKED_UNCONSUMED_SUPERSEDED`; it remains non-reusable.

No package may be treated as reusable merely because `final_authorization.json` exists.

## Historical staging residue — reconciliation required

The external application staging root contains:

- `V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z-8c6effa328cd4a6fa05b5e2e016a273d`;
- `V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z-bae5318756834afa8218bc1874e712fd`;
- `V2_9_8B_WINDOW_15M_AUTH_20260804T214901Z-c1b4d8360ddb485dbbeadfb0f5773c46`;
- `V2_9_8B_WINDOW_15M_AUTH_20260806T005252Z-3778d27807ff40edac6e9ac961b78ea9`;
- `V2_9_8B_WINDOW_15M_AUTH_20260806T005252Z-f47145e2df5b41bea6e44475c8c464ba`;
- `index-restoration-premarker`;
- `sim-preauth`.

These entries must not be deleted merely to make readiness pass. The next lane must classify them read-only as historical consumed residue, historical pre-marker/unconsumed residue, or test/simulation residue, preserve evidence, and prove none can act as current execution authority.

## Static code-contract status

The static PASS from the DTW-70 audit remains valid on the remote post-C8 lineage:

- canonical migration catalogue owner;
- exact one-shot authorization law;
- pre-marker temporal/DB/source/composition guards;
- create-once marker consumption boundary;
- exactly one child;
- no retry/rerun/resume/restart/successor;
- normal `WINDOW_15M`, selective 1h false;
- Source Governor and Central Scheduler ownership;
- longer-window and downstream capability locks.

The blocker is therefore operational lineage/evidence state, not a newly proven code defect.

## Money-usefulness contribution

The audit prevents a future one-shot authorization from binding stale pre-hardening code even though the authoritative DB itself is healthy. It also prevents historical staging residue from being silently erased or misclassified. This improves the reliability of future paper-only clean-memory collection without unlocking financial behavior.

## What remains locked

No authorization creation/consumption, wrapper application, provider/RPC/source fetching, Scheduler runtime, campaign, DB mutation, memory generation, `WINDOW_1H+`, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL is permitted.

## Exact next lane

`V2-9.8B Post-C8 Local Operational Lineage and One-Shot Staging Reconciliation`

Required order:

1. audit/classify target lineage and staging evidence;
2. design a non-destructive local Git alignment plan;
3. align to the exact post-C8 operational audit branch only if untracked-evidence collision checks pass;
4. bounded read-only proof that DB bytes are unchanged, local HEAD equals the approved target, tracked tree is clean, and staging evidence is fully classified;
5. closeout;
6. then repeat only the minimum DTW-70 readiness checks needed to obtain a final PASS.

No provider or Printer runtime belongs in that lane.

## Functionality Risks / Setbacks / Efficiency Blockers

- The local checkout is 214 commits behind the current audit head; authorizing from it would bypass the completed Checkpoint hardening chain.
- Untracked operator evidence must be preserved across Git alignment and must not be overwritten by a checkout.
- External `.staging` residue is historical evidence until classified; blanket cleanup is forbidden.
- The authoritative DB is healthy and must remain byte-identical during lineage alignment.
- Broad regression tests are unnecessary for this environment-alignment blocker.

## Stop condition

DTW-70 stops BLOCKED here. Do not create a fresh authorization. Proceed only to the non-runtime lineage/staging reconciliation lane.