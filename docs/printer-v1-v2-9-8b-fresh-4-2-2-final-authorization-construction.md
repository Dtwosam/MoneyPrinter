# Printer V1 V2-9.8B Fresh 4/2/2 Final Authorization Construction

Date: 2026-08-21

Status: `PRECOMMITTED_FOR_EXACT_HEAD_CONSTRUCTION`

Required readiness verdict:

`V2_9_8B_FRESH_4_2_2_AUTHORIZATION_READINESS_AUDIT_PASS`

## 1. Decision and scope

The fresh 4/2/2 authorization readiness gates pass at starting commit
`6d0c1d30de452af49f6a036852a5ce7148b908e3` on branch
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
- `pre_authorization_migration_ledger_guard` owns immutable database identity
  and repository-ledger agreement;
- the existing create-once/read-only file primitives own publication.

No second document constructor, hand-written final JSON schema or product-code
change is permitted.

## 2. Exact-head transaction

The provenance contract requires the authorization's branch and HEAD to equal
live Git state. This document and `CURRENT_HANDOFF.md` are therefore committed
before construction. The resulting commit is the exact authorization-bound
HEAD. No later commit may be added to this branch after publication.

Because the final ID and temporal window do not exist until after that commit,
the final artifact path, SHA-256, byte size, issue time and expiry are recorded
in the create-once package and the construction response. They are not written
back into tracked files and cannot move the bound HEAD.

If any post-commit construction or validation step fails before immutable
publication, no authorization package or byte may survive.

## 3. Revalidated construction gates

### 3.1 Repository and database

- exact starting branch: PASS
- exact starting HEAD: PASS
- tracked tree and index clean: PASS
- authoritative path: `data/printer_v1.sqlite3`
- SHA-256:
  `87dac0d15ee32940f7dda30d0704dc252ff540c9d6f1ff6a3857e8f598c9f2fa`
- size: `113664000`
- migration count/head:
  `59 / 059_pair_ready_parent_terminal_cancellation_transition.sql`
- canonical migration catalogue/ledger digest agreement: PASS
- `PRAGMA integrity_check`: `ok`
- foreign-key violations: `0`
- SQLite sidecars: `0`

The operational provenance profile deliberately keeps
`MIGRATION_058_20260818T082552Z` as the canonical current schema-transition
evidence package. The authorization's authoritative-database binding separately
pins the exact live Migration-59 ledger and file identity. These facts are
compatible: Migration 059 is a bounded transition-trigger repair and does not
replace the profile's declared Migration-058 package root.

### 3.2 Runtime and strict zero state

The production operational zero-state gate passed read-only with:

- live Printer runtime processes: `0`
- active campaigns: `0`
- active campaign runs: `0`
- active campaign cycles: `0`
- active campaign Scheduler work: `0`
- active campaign supervision: `0`
- active proof supervision: `0`
- active discovery work: `0`
- active factory runs: `0`
- active factory steps: `0`
- active pre-admission attempts: `0`
- active pre-lifecycle refresh work: `0`
- active Scheduler jobs: `0`

All 12 canonical ownership domains are exactly zero.

### 3.3 Exact 4/2/2 policy

- configured through-4h tokens: `4`
- configured active cycles: `2`
- tokens per cycle: `2`
- total cycle-admission ceiling: `2`
- shared discovery requests: `4`
- lifecycle requests per token: `118`
- lifecycle request outer ceiling: `476`
- lifecycle Scheduler outer ceiling: `420`
- minimum cycle-admission spacing: `300` seconds
- pre-lifecycle acquisition duration: `2400` seconds
- post-supply lifecycle duration: `18000` seconds
- automatic retries: `0`
- endpoint rotation: `false`
- root main window: `WINDOW_15M`
- locked windows: `WINDOW_12H`, `WINDOW_24H`

The 5-minute window remains support-only. Exact identity, depth-4 discovery,
evidence-quality, freshness, safety, continuity and the `$3000` graduated-market
floor remain unchanged runtime admission gates and are not widened by this
authorization.

## 4. Prior authorization non-reuse

Exactly 39 existing authorization package identities were enumerated across the
four profile-approved roots. They are unique and must be copied, sorted, into
the new document's `prior_authorizations_non_reusable` trust root.

The latest prior identity is:

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260820T213930Z_e80f3b5c`

Fresh readback proves:

- immutable authorization SHA-256:
  `545b8f05153b1ef32f5ad925766a3152f268658ac5544fcd6f54e070bfab656b`
- application marker: present
- consumed at: `2026-08-20T21:49:46.752577+00:00`
- allowed invocation count: `1`
- child start attempted: `true`
- child exit code: `1`
- automatic retries/manual reruns/restarts/resumes/successors: all `0`
- current production validation: fails closed as `AUTHORIZATION_EXPIRED`

It is historical-only and cannot be reused, reinterpreted or continued.

## 5. Construction contract

After this exact-head commit, the constructor must:

1. re-check branch, HEAD, tracked cleanliness, database identity, ledger health,
   sidecar absence, runtime absence and all 12 zero-state domains;
2. generate one fresh safe authorization identity;
3. use the existing canonical document constructor with a 12-hour validity
   interval and all 39 historical identities declared non-reusable;
4. validate the in-memory document before any package exists;
5. publish exactly one `final_authorization.json` through exclusive create-once
   semantics, make it read-only and independently re-read and validate it;
6. prove the matching application namespace remains absent; and
7. stop without creating a manifest, marker, child or runtime work.

## 6. Failure semantics

- Pre-publication failure: remove any unpublished staging residue; no final
  authorization package survives.
- Package identity collision: fail closed; do not overwrite or choose a second
  authorization in the same construction attempt.
- Validation/readback/immutability failure: construction is BLOCKED and no
  application is permitted.
- Database, Git, zero-state or process drift: stop before publication.
- Any surviving final package is never consumed by this lane.

## 7. Functionality Risks / Setbacks / Efficiency Blockers

- The production profile's current migration evidence root remains Migration
  058 while the database ledger is at 059. The distinction is intentional and
  must remain explicit during independent review.
- The final artifact cannot be recorded in a later tracked closeout without
  invalidating its exact-HEAD binding. Review must derive package facts directly.
- Existing operator evidence is intentionally untracked and must not be staged,
  rewritten, deleted or repurposed.

## 8. Exact next permitted lane

After exactly one package is immutably published and validated:

`V2-9.8B Fresh 4/2/2 Final Authorization Independent Review`

Independent review is required before any future application decision. This
construction decision does not authorize application or execution.

## 9. Preserved locks

Printer remains Solana-only, Solana-memecoin-only and paper-only. Retrieval,
BUY/SELL/HOLD, positions, trade events, paper audits, PnL, live execution,
wallet/private-key/signing logic, paid APIs, scoring/ranking/confidence/weighted
logic, embeddings/vectors and 12h/24h collection remain locked.
