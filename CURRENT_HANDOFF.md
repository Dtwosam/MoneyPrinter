# CURRENT HANDOFF

Date: 2026-08-18

## Current lane

`V2-9.8B Post-Repair Two-Cycle Four-Token Operational Authorization Alignment Implementation`

Status: `CLOSED_PASS`

Verdict:

`V2_9_8B_POST_REPAIR_TWO_CYCLE_FOUR_TOKEN_OPERATIONAL_AUTHORIZATION_ALIGNMENT_IMPLEMENTATION_PASS`

## Current code baseline

Approved design baseline:

`babc8a3b2dfd4ddca1307e140a378e0d3279e113`

Repaired operational product-code baseline:

`df1aced491d01d1a6d25ae38ca2da4eab72665c6`

Implementation branch:

`agent/v2-9-8b-post-repair-two-cycle-four-token-operational-authorization-alignment-implementation`

Master remains untouched at `19bcd23da1608e406e25f675532df193b65d038a`.

## Latest completed work

The already-repaired multi-cycle four-token machinery is now an explicitly
authorized OPERATIONAL command boundary.

New operational mode: `four-token-standard-four-hour-run`.

One bounded invocation; Cycle 1 two fresh governed slots (15m → eligible 1h →
eligible 4h); Cycle 2 two NEW fresh governed slots inside the SAME campaign
invocation; four token slots total; two active cycles; two tokens per cycle.

Existing meanings are unchanged:

- `standard-four-hour-run` remains the two-token operational Standard-4H
  authority;
- `four-token-bounded-capacity-proof-run` remains proof-only.

Implementation is the minimum authority/wiring layer: a neutral 4/2/2
composition facade, a distinct one-shot wrapper, a distinct Git authorization
profile, command registration/routing, and a generalized (not duplicated)
zero-state gate. No new Scheduler, Source Governor, provider loop, Memory Factory
runner, selection algorithm, DB schema, migration or parallel lifecycle owner was
created.

Capacity derives from `scaled_standard_four_hour_capacity_contract(4)` and
matches the expected comparison values exactly: 4 slots / 2 cycles / 2 per cycle
/ 117 requests per token / 472 request outer ceiling / 420 Scheduler rows, with
300s minimum admission spacing, zero retries, no endpoint rotation and no long
windows. Nothing was hard-coded to force those numbers.

## Provenance alignment

CURRENT: Migration 058, for both the repaired four-token proof profile and the
new four-token operational profile.

HISTORICAL: Migrations 050, 055, 056 and 057.

Migration 057 is no longer current four-token schema-transition evidence. Its
historical identity came from real preserved operator evidence
(`MIGRATION_057_20260816T191558Z`, 6 files, inventory SHA-256
`9272f596e7a82c3cfe9d824595be74f34c7203dccab3bd541c187dc236519535`), derived with
the committed enumeration/digest primitives and validated by reproducing the
already-committed Migration-055 and Migration-056 constants exactly. No evidence
was fabricated and no provenance validation was weakened.

Only the Migration-058 package root and kind are committed. The exact execution
identity stays preparation-time bound through the authorization document, so
host-local operator/DB evidence is never hard-coded source truth.

Ordinary and two-token Standard-4H profile semantics are unchanged.

## Verification

Focused new tests: PASS. Touched Standard-4H, four-token proof, multi-cycle,
zero-state, migration/provenance and capability-lock tests: PASS. Compilation and
import checks: PASS.

Bounded offline/disposable proof: PASS. One invocation produced Cycle 1 two fresh
slots, Cycle 2 two new fresh slots, four distinct mint/pair identities, exact per
cycle Scheduler ownership, no 12h/24h planning, one terminal closure and no
successor, retry, rerun, resume or restart — with fake/frozen transports,
deterministic time, a disposable database and zero source calls.

Regression was measured against the untouched baseline rather than asserted.
Baseline: 1037 passed / 89 failed. This lane: 1093 passed / 90 failed. Exactly one
test moved pass-to-fail — a stale `057-as-current` assertion — and it was updated
along with two sibling assertions found by running every affected file in full.
Those affected files now show 182 passed / 3 failed, and those 3 were confirmed
byte-identical failures on the stashed baseline.

The 89 pre-existing baseline failures across roughly 26 files (largest cluster: 31
in `tests/test_v2_9_8b_window_15m_git_provenance_authorization_manifest.py`) are
documented, not repaired. They are outside this lane's approved scope and need
their own lane.

## Authorization state

Fresh authorization created: `NO`

Authorization consumed: `NO`

Historical authorization reused: `NO`

Campaign started: `NO`

Provider/RPC/WebSocket campaign calls: `0`

Authoritative campaign DB mutation: `0` (byte-identical: SHA-256
`a77141bce32468a2685007a276dbac91d1ed68671b5036c7bc24f54f60ad46d7`, size
`100794368`, inode `1230526`, mtime_ns `1787043184343686970`, no sidecars)

Migration added: `NO`. Migration head remains `058_direct_pump_migration_cursor.sql`.

Migration 059: `NO`

## Exact next permitted action

`V2-9.8B Post-Repair Two-Cycle Four-Token Operational Authorization Alignment Independent Closeout`

Do not proceed automatically into independent closeout. Do not prepare or create
the final operational 4/2/2 authorization. Do not run Printer.

The unconsumed two-token Standard-4H authorization from the earlier lane remains
untouched and is not authority for the new operational mode.

## Locks

5m remains support-only. Migration head remains 058; no 059. 12h/24h, retrieval,
paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, live
wallet/private-key/signing execution, real funds, paid APIs,
scoring/ranking/confidence/weighted logic and embeddings/vectors remain locked.

The active authority stack wins any conflict with this handoff.
