from __future__ import annotations

import os
from pathlib import Path

focused = os.environ.get("FOCUSED_TEST_SUMMARY", "NOT_RECORDED")
nearest = os.environ.get("NEAREST_TEST_SUMMARY", "NOT_RECORDED")
nearest_files = os.environ.get("NEAREST_TEST_FILES", "NOT_RECORDED")

path = Path(
    "docs/printer-v1-v2-9-8b-window-15m-checkpoint-2-preflight-initialization-closeout.md"
)
path.write_text(f'''# Printer V1 V2-9.8B WINDOW_15M Checkpoint 2 Preflight and Initialization Closeout

## Verdict

`V2_9_8B_WINDOW_15M_CHECKPOINT_2_PREFLIGHT_INITIALIZATION_PASS`

Checkpoint 2 audited the ordinary public child from validated wrapper bindings through zero-source readiness, authorization-bound database validation, the first durable campaign graph, supervision acquisition, and heartbeat start ordering. Three deterministic initialization defects and one exact-write-evidence defect were confirmed with disposable migrated databases and repaired without running Printer or contacting providers.

## Baseline and branch

- baseline: `0deba3c06d72499899b9c21bf9e71c89d5c8057c`
- checkpoint branch: `agent/v2-9-8b-window-15m-checkpoint-2-preflight-initialization`
- Linear tracker: `DTW-28`

## Production path inspected

```text
validated wrapper/child bindings
-> build_activation_preflight
-> DB path and sidecar gate
-> Git provenance
-> source-contract / concrete-composition / dependency / budget checks
-> read-only migration / integrity / FK / active-state / locked-capability checks
-> authorization-bound DB comparison
-> action-local baseline
-> artifact and backup/restore rehearsal
-> first durable campaign graph
-> supervision lease acquisition
-> heartbeat start
```

## Zero-source audit result

The preflight owners were already correctly ordered and required no production change:

- Git-provenance authorization manifest validation is read-only and exact-schema;
- pre-authorization migration-ledger review remains an earlier additional gate;
- concrete composition constructs production dependencies without invoking transports;
- source-contract, runtime-dependency, and holder-budget preflights run before campaign identity;
- database migration, integrity, foreign-key, active-residue, and locked-capability checks are read-only;
- a preflight exception creates no campaign graph, artifact root, lease, heartbeat, source request, Scheduler work, lifecycle, or memory row.

## Confirmed findings

1. `AUTHORIZED_DATABASE_CHANGED_BEFORE_FIRST_WRITE`
   - Authorization and operational preflight compared the database earlier, but the exact bytes were not revalidated under the first write lock. A mutation in the preflight-to-write gap could receive campaign rows tied to stale authorization evidence.
2. `OPERATIONAL_CAMPAIGN_INITIALIZATION_FAILED`
   - Campaign/configuration, run, and cycle/RUNNING transitions committed in three transactions. A cycle insert failure left a partial durable campaign/configuration/run graph while action-local campaign identity had not yet been published.
3. `SUPERVISION_LOCK_ORPHAN_ON_DATABASE_CONNECT_FAILURE`
   - Supervision created its lease file before opening SQLite, but database connection happened outside the cleanup scope. A missing/unopenable database could leave a new orphan lock.
4. `INITIALIZATION_MUTATION_IDENTITY_INCOMPLETENESS`
   - The action-local recorder identified campaign/configuration/run inserts but omitted cycle insertion and campaign/run state updates, understating authoritative initialization writes.

No defect was found in the authorization manifest validator, migration-ledger guard, concrete-composition registry, dependency preflight, holder-budget preflight, recovery policy, provider policy, Scheduler ownership, or memory policy in this checkpoint.

## Repair

- Added `create_operational_campaign_graph` as the single operational first-write owner.
- It acquires one `BEGIN IMMEDIATE` lock, then revalidates:
  - exact resolved authorized database path;
  - exact authorization-bound pre-mutation SHA-256;
  - exact canonical migration ledger, authorized count, and authorized head.
- Only after those checks does the same transaction create:
  - campaign;
  - immutable configuration;
  - campaign run;
  - initial cycle;
  - campaign `DRAFT -> RUNNING` transition;
  - run `DRAFT -> RUNNING` transition.
- Any failure rolls the full graph back. Action-local campaign/run/cycle identities are published only after the transaction commits.
- Historical `create_campaign` and `create_campaign_run` APIs remain unchanged for their existing callers.
- Exact mutation evidence is emitted after commit: four insert identities and two update identities.
- Supervision database connection now sits inside the scope that owns cleanup of the newly created lease file. A pre-existing/foreign lease is still never removed.

## Test-first proof

Five distinct RED gates were observed before implementation:

1. stale authorized database bytes were accepted by the first write;
2. injected cycle insertion failure left partial campaign rows;
3. database revalidation was not performed while the first write lock was held;
4. initialization recorded only three of six exact writes;
5. a database connection failure left a newly created supervision lock.

Focused Checkpoint 2 tests:

```text
{focused}
```

Nearest selected preflight, authorization, migration, persistence, ownership, supervision, recovery, database-binding, concrete-composition, and public-command tests:

```text
{nearest}
```

Selected nearest files:

```text
{nearest_files}
```

Additional verification:

- changed-module Python compilation: PASS;
- `git diff --check`: PASS;
- no migration or script change: PASS;
- no provider/runtime command added: PASS;
- clean one-commit checkpoint generation from the Checkpoint 1 baseline: required before final acceptance.

## Runtime and evidence boundary

- no authorization was created, modified, reused, rebound, or consumed;
- no wrapper application or public operational command was run;
- no provider was contacted;
- no discovery, holder, Scheduler, campaign, lifecycle, or memory runtime ran;
- all database tests used disposable migrated SQLite files;
- the authoritative Mac database and historical authorization/application evidence were not accessed or mutated.

## Money-usefulness contribution

A future authorized `WINDOW_15M` run can no longer attach new campaign ownership to database bytes different from those authorized, and an initialization fault cannot strand a partial campaign graph or orphan lease before useful collection begins. Exact write identities also make consumed-run diagnosis and terminal accounting more reliable.

## What improves

- authorization-to-first-write database continuity;
- atomic campaign/configuration/run/cycle initialization;
- exact rollback on initialization failure;
- exact action-local initialization write accounting;
- supervision lock cleanup when SQLite cannot be opened;
- precise separation between zero-source preflight blocks and post-initialization failures.

## What remains locked

Provider execution, live `WINDOW_15M`, selective 1h, 4h/12h/24h, retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, wallets, real funds, paid APIs, scoring, ranking, confidence, weighting, embeddings, and vectors.

## Functionality Risks / Setbacks / Efficiency Blockers

- SHA-256 revalidation under the first write lock adds bounded local file-read time before four small initialization inserts; it performs no provider or network work.
- SQLite protects the transaction boundary, but the lease file remains a local-filesystem coordination primitive rather than a distributed lock.
- Failure after the graph commits but before supervision acquisition is now an initialized failure and must continue through the existing terminalization coordinator; later checkpoints will test deeper cleanup boundaries.
- Exact mutation recording remains best-effort reporting and is not allowed to control persistence success.
- Historical campaign creation APIs are intentionally retained; this checkpoint changes only the ordinary operational initialization route.

## Exact next step

Begin Checkpoint 3 only after independent inspection confirms this checkpoint's clean commit, proof evidence, branch ancestry, and closeout. Do not create an authorization or run Printer.
''', encoding="utf-8")
print(path)
