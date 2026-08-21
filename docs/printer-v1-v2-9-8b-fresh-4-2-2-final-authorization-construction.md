# Printer V1 V2-9.8B Fresh 4/2/2 Final Authorization Construction

Date: 2026-08-21

Status: `PRECOMMITTED_FOR_EXACT_HEAD_CONSTRUCTION`

Required readiness verdict:

`V2_9_8B_FRESH_4_2_2_AUTHORIZATION_READINESS_RECHECK_PASS`

Expected construction verdict after successful create-once publication:

`V2_9_8B_FRESH_4_2_2_FINAL_AUTHORIZATION_CONSTRUCTION_PASS`

## 1. Decision and scope

The fresh 4/2/2 authorization readiness recheck passes at starting commit
`e2918849afe858a94e80058899d6e93d50211d2a` on branch
`agent/v2-9-8b-pair-ready-parent-terminal-cancellation-repair`.

This decision permits exactly one create-once final authorization package for
the existing `four-token-standard-four-hour-run` authority. It permits no
application marker, wrapper application, child process, Printer/provider/RPC/
WebSocket call, Source Governor or Central Scheduler runtime, campaign, cycle,
authoritative business-data mutation, authorization consumption, retry, rerun,
restart, resume or successor.

The existing production owner remains authoritative:

- `four_token_standard_four_hour_one_shot_wrapper.fixture_authorization_document()`
  owns the exact document shape and policy;
- `validate_four_token_standard_four_hour_authorization_document()` owns the
  production schema/policy validation;
- `pre_authorization_migration_ledger_guard.inspect_authoritative_database()`
  owns immutable database identity measurement;
- the existing create-once/read-only file primitives own publication.

No second document constructor, hand-written final JSON schema, or product-code
change is permitted.

## 2. Exact-head transaction

The provenance contract requires the authorization's branch and HEAD to equal
live Git state. This document and `CURRENT_HANDOFF.md` are therefore committed
before construction. The resulting commit is the exact authorization-bound
HEAD. The authorization JSON will bind that construction commit, not the
readiness HEAD `e2918849afe858a94e80058899d6e93d50211d2a`.

No later tracked commit may be added to this branch after authorization
publication. No guessed future commit SHA is recorded here.

Selected authorization identity for this lane:

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260821T153458Z_512f2436`

Issue/expiry timestamps and the final artifact SHA-256/byte size are recorded
in the create-once package and construction response only. They are not written
back into tracked files after the exact HEAD has been bound.

If any post-commit construction or validation step fails before immutable
publication, no authorization package or byte may survive.

## 3. Revalidated construction gates

### 3.1 Repository and database

- exact starting branch: PASS
- exact readiness HEAD `e2918849afe858a94e80058899d6e93d50211d2a`: PASS
- tracked tree and index clean: PASS
- ancestral design/implementation/proof/closeout commits: PASS
- authoritative path: `data/printer_v1.sqlite3`
- SHA-256:
  `87dac0d15ee32940f7dda30d0704dc252ff540c9d6f1ff6a3857e8f598c9f2fa`
- size: `113664000`
- inode: `1230526`
- mtime_ns: `1787310849512684366`
- migration count/head:
  `59 / 059_pair_ready_parent_terminal_cancellation_transition.sql`
- `PRAGMA integrity_check`: `ok`
- foreign-key violations: `0`
- SQLite sidecars: `0`
- open runtime handles: `none`

### 3.2 Current Migration-059 / provenance

Current four-token profile migration evidence:

- root: `operator-runs/v2-9-8b-migration-059-application`
- kind: `MIGRATION_059_EVIDENCE`
- execution: `MIGRATION_059_20260821T095456Z`
- exact execution directory present; five regular files; no symlink/non-regular
  member; no unexplained sibling

Historical provenance remains:

- Migration 058: `MIGRATION_058_20260818T082552Z` / `11` /
  `d6dc1431a3a99a8c2f521a3033948d11bbdd4e7151ddabc1127c7fb3b9138fa8`
- PAIR_READY: `RECONCILIATION_20260821T110736Z` / `5` /
  `94cb775d8f1a0d095669c3a1285b8484d7bfbae62c50bf327669516d942285d7`
- production enumeration: `Hm=40` / `Hr=12`
- trust law: `F = T ∪ M ∪ Ha ∪ Hm ∪ Hr` and `C == M`
- no wildcard or directory-discovery trust

### 3.3 Runtime and strict zero state

All 12 canonical ownership domains are exactly zero. No active or unconsumed
pre-admission authority and no active campaign/factory/Scheduler/discovery/
supervision residue remain.

### 3.4 Exact 4/2/2 operational policy

Derived from the canonical production contract:

- configured through-4h tokens: `4`
- configured active cycles: `2`
- tokens per cycle: `2`
- Cycle2: fresh and disjoint
- token-slot identity: `slot-<exact-cycle-id>-1/2`
- minimum freeze depth: `4`
- exact-pool floor: `$3,000`
- minimum cycle spacing: `300` seconds
- acquisition: `2400` seconds
- lifecycle: `18000` seconds
- requests per token: `118`
- governed total: `476`
- shared discovery: `4`
- Scheduler ceiling: `420`
- storage: `67,108,864` bytes
- automatic retries: `0`
- endpoint rotation: `false`
- main lifecycle: `WINDOW_15M -> WINDOW_1H -> WINDOW_4H`
- `WINDOW_5M_MICRO_EVENT`: support-only
- `WINDOW_12H` / `WINDOW_24H`: locked
- allowed invocation count: `1`
- manual rerun / resume / restart / successor: all `false`
- operator approval: required
- wrapper route: required

Stale `117` / `472` / `236` expectations are rejected.

## 4. Prior authorization non-reuse

Exactly 40 existing authorization package identities were enumerated across the
profile-approved historical roots and must be copied, sorted, into the new
document's `prior_authorizations_non_reusable` trust root.

That complete set includes the superseded unconsumed authorization:

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260821T124505Z_8cf7ee5d`

Fresh readback of that superseded package proves:

- immutable SHA-256:
  `644a7b16c7055334e59ab5aa4e820f712b055f8fa4e902d3b9810389fe2724b7`
- unconsumed; marker absent; manifest absent; application absent
- authorized HEAD: `e639fb0f43338f231165b8873849f452e0a5c146`
- diagnostic disposition: `BLOCKED_UNCONSUMED_SUPERSEDED`
- reusable: `false`

It cannot authorize the repaired Migration-059 profile or the construction
HEAD created by this record.

## 5. Construction contract

After this exact-head commit, the constructor must:

1. re-check branch, `AUTHORIZED_HEAD`, tracked cleanliness, database identity,
   Migration-059 evidence, `Hm/Hr`, zero-state, and superseded-auth invariance;
2. use the selected authorization identity above;
3. use the existing canonical document constructor with a 12-hour validity
   interval (`43200` seconds) and all 40 historical identities declared
   non-reusable;
4. bind `migration_execution_id = MIGRATION_059_20260821T095456Z`;
5. validate the in-memory document before any package exists;
6. publish exactly one `final_authorization.json` through exclusive create-once
   semantics, make it mode `0444`, and independently re-read/validate it;
7. run only a non-consuming pre-marker provenance proof;
8. stop without creating a manifest, marker, child, or runtime work; and
9. leave tracked files unchanged after publication so the bound HEAD remains
   exact.

## 6. Failure semantics

- Pre-publication failure: remove any unpublished staging residue; no final
  authorization package survives.
- Package identity collision: fail closed; do not overwrite or choose a second
  authorization in the same construction attempt.
- Validation/readback/immutability failure: construction is BLOCKED and no
  application is permitted.
- Database, Git, zero-state, or process drift: stop before publication.
- Any surviving final package is never consumed by this lane.

## 7. Functionality Risks / Setbacks / Efficiency Blockers

- Exact-HEAD preservation forbids any tracked amend/commit after publication;
  review must derive package facts directly from the untracked artifact.
- The selected authorization ID is reserved for this lane only; collision with
  an unexpected sibling fails closed.
- Existing operator evidence is intentionally untracked and must not be staged,
  rewritten, deleted, or repurposed.

## 8. Exact next permitted lane

After exactly one package is immutably published and validated:

`V2-9.8B Fresh 4/2/2 Final Authorization Independent Review`

Independent review is required before any future application decision. This
construction decision does not authorize application or execution.

## 9. Preserved locks

Printer remains Solana-only, Solana-memecoin-only and paper-only. Retrieval,
BUY/SELL/HOLD, positions, trade events, paper audits, PnL, live execution,
wallet/private-key/signing logic, paid APIs, scoring/ranking/confidence/weighted
logic, embeddings/vectors and 12h/24h collection remain locked. Source Governor
and Central Scheduler bypass remain forbidden.
