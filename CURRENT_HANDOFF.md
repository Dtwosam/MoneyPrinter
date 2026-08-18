# CURRENT HANDOFF

Date: 2026-08-18

## Current lane

`V2-9.8B Post-Repair Two-Cycle Four-Token Operational Authorization Alignment Independent Closeout`

Status: `CLOSED_PASS`

Verdict:

`V2_9_8B_POST_REPAIR_TWO_CYCLE_FOUR_TOKEN_OPERATIONAL_AUTHORIZATION_ALIGNMENT_INDEPENDENT_CLOSEOUT_PASS`

## Current code baseline

Approved design baseline:

`babc8a3b2dfd4ddca1307e140a378e0d3279e113`

Repaired operational product-code baseline:

`df1aced491d01d1a6d25ae38ca2da4eab72665c6`

Reviewed implementation commit:

`25daf4fd993fbea4142b16d02820b577fba6e300`

Implementation branch:

`agent/v2-9-8b-post-repair-two-cycle-four-token-operational-authorization-alignment-implementation`

This review adds documentation only. Product source, tests and migrations are
unchanged by it. Master was not modified.

## What the independent review established

Every claim was re-derived from the repository rather than accepted from the
implementation closeout.

- Diff from the design baseline is exactly the approved scope. No migration,
  provider adapter, Source Governor, Central Scheduler, discovery, coordinator,
  factory-runner or selection-algorithm file was changed.
- Three authorities remain distinct. Fourteen adversarial cross-authority reuse
  attempts were executed and all were rejected, in both directions, including
  mode substitution, schema substitution and one-shot policy loosening.
- Reusing the repaired `FourTokenProofController` imports no proof-only
  authorization, application, terminal, retry or execution semantics. The
  controller holds only a capacity policy; `standard_four_hour_campaign=True`
  hard-requires operational-persistent mode and rejects proof modes; and the
  proof acceptance verdict function is test-only, never called from `src/`.
- Capacity is live-derived: reloading the facade against a deliberately
  perturbed canonical contract moved every value and restored cleanly. Derived
  4 / 2 / 2 / 117 / 472 / 420, 300s spacing, zero retries, no rotation, no long
  windows.
- Migration-058 is current for both four-token profiles; 050, 055, 056 and 057
  are preserved history. The 057 identity was reproduced independently, and the
  method was validated by reproducing the two previously-committed 055 and 056
  digests exactly. No fabrication; no weakened validation; the 058 execution
  identity remains preparation-time bound.
- The zero-state gate is one shared implementation with two thin entry points,
  pinned to 58 / `058_direct_pump_migration_cursor.sql`, and it failed closed on
  every probe including a cross-authority document.
- The bounded proof was re-executed independently and audited with raw SQL: all
  20 checks passed, including four distinct mint and exact-pair identities, one
  campaign run, zero source requests, no 12h/24h, one terminal cleanup and no
  third cycle.

## Residual finding (non-blocking)

The authorization-binding policy derives from
`scaled_standard_four_hour_capacity_contract(4)`, but the runtime controller's
structural policy is built from separate literals in
`four_token_proof_integration.py`. They agree exactly today and a focused test
pins the agreement, and reusing that repaired builder was mandated by scope.

The host-local preparation lane should re-derive both on the exact launch
checkout and stop on any disagreement rather than assuming today's agreement.

## Disposition of the pre-existing baseline failures

Investigated against a read-only extracted copy of the design baseline, not
auto-dismissed.

`tests/test_v2_9_8b_window_15m_git_provenance_authorization_manifest.py` fails
31 / passes 17 on both trees, with **identical failing test identities and
identical failure signatures**. Every failing test exercises the ordinary `run`
profile, which this lane did not change, and the file never references the new
4/2/2 authority. The other six affected-set failures reproduce byte-identically
on the baseline with signatures naming Migration-050.

Critically, every one of these is a validator **rejection**, not a wrongful
acceptance — they fail closed, so none can authorize anything unsafely.

Classification: `PRESERVED_SEPARATE_PRE_EXISTING_DEBT`. Zero new relevant
regressions. Not repaired here; they require their own lane.

## Git reconciliation

Local HEAD `25daf4f` is local-only; the origin branch of the same name still
points at the design baseline `babc8a3b`. Local master `19bcd23` is an ancestor
of origin/master `a98e2da` — 21 behind, 0 ahead — a stale pointer, not a
divergence. The implementation commit is on neither local master nor
origin/master.

Classification: `LOCAL_ONLY_VISIBILITY_STATE`, not a product defect. Nothing was
pushed. A later launch lane must bind the actual local launch checkout, because
remote visibility does not currently reflect it.

## Authorization state

Fresh authorization created: `NO`

Authorization consumed: `NO`

Historical authorization reused: `NO`

Campaign started: `NO`

Provider/RPC/WebSocket campaign calls: `0` (the bounded proof and the full new
authority set also pass with outbound network hard-blocked)

Authoritative campaign DB mutation: `0` — identity unchanged: SHA-256
`a77141bce32468a2685007a276dbac91d1ed68671b5036c7bc24f54f60ad46d7`, size
`100794368`, inode `1230526`, mtime_ns `1787043184343686970`, no sidecars.

Migration added: `NO`. Migration head remains `058_direct_pump_migration_cursor.sql`.

Migration 059: `NO`

The eight pre-existing untracked `standard-four-hour-run` authorization packages
remain unconsumed and cannot authorize the 4/2/2 mode.

## Exact next permitted action

`V2-9.8B Post-Repair Two-Cycle Four-Token Operational 4/2/2 Host-Local Authorization Preparation`

Derived from the approved design's sequence: implementation -> bounded
proof/test -> closeout -> host-local authorization preparation -> independent
authorization review -> operator-approved one-use run.

That lane must bind the actual launch checkout and the actual
`data/printer_v1.sqlite3` path, SHA-256, size, inode and mtime_ns. GitHub-only
evidence cannot substitute. It must stop without consuming the authorization.

Do not create or consume the operational authorization in this closeout. Do not
run Printer.

## Locks

5m remains support-only. Migration head remains 058; no 059. 12h/24h, retrieval,
paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, live
wallet/private-key/signing execution, real funds, paid APIs,
scoring/ranking/confidence/weighted logic and embeddings/vectors remain locked.

The active authority stack wins any conflict with this handoff.
