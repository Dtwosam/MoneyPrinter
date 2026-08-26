# Printer V1 / V2-9.8B — Aug-25 Four-Token A-to-Z Repair Closeout

Verdict:

`V2_9_8B_AUG25_A_TO_Z_REPAIR_CLOSEOUT_PASS_READY_FOR_POST_COMMIT_REREADINESS`

Implementation commit:

`87a49f04b0f7d35bbb878f2745f159675ec70a38`

Parent:

`d9c73432f9155c39d75c692867d5c7e73b5c83a1`

Branch:

`agent/v2-9-8b-aug25-a2z-repair-application`

## Closed repair

The Aug-25 four-token Standard-4H 4/2/2 A→Z operational path is repaired on the
exact seven production files:

- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
- `src/printer_v1/operator_cli/campaign_full_run_accounting.py`
- `src/printer_v1/operator_cli/campaign_ownership.py`
- `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py`
- `src/printer_v1/operator_cli/one_command_15m_factory.py`
- `src/printer_v1/operator_cli/operational_memory_factory_command.py`
- `src/printer_v1/operator_cli/pre_admission_discovery_attempt.py`

Exact defect areas closed:

- lawful typed `TIMELY_ACQUISITION_NOT_PRODUCIBLE` preclose skip is
  terminal-acceptable; untyped/unsafe skip and failed jobs remain fail-closed;
- cooperative Scheduler yield may mirror campaign `scheduler_work`
  `RUNNING -> PENDING` only after the bound Central Scheduler job is already
  released `PENDING`;
- Cycle-2 frozen tracking lane may supplement missing classifier fields from
  already-linked exact-pair `COMPLETE` DexScreener/GeckoTerminal responses;
  this is projection-only and creates no source request;
- `owned_proof_cycle_id` is initialized before the outer exception owner and
  before any Scheduler claim;
- `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260825T134723Z_4563a9dd` is registered
  `CONSUMED_CHILD_EXITED_ZERO`.

Source Governor remains the only external-source owner. Central Scheduler
remains the only scheduled-work owner. No retry, resume, restart, or successor
path was introduced.

## Original failure reproof

The original Aug-25 failure groups remain closed and were not reopened:

- A = 12/12 PASS
- C = 5/5 PASS
- D = 5/5 PASS
- E = 3/3 PASS
- F = 8/8 PASS
- G = 5/5 PASS

Focused genuine-checkout repair: 14/14 PASS

Accounting correspondence: 8/8 PASS

Full wiring: 10/10 PASS

Lawful preclose acceptance: 2/2 PASS

Canonical Standard-4H: 23/23 PASS

Bounded offline operational 4/2/2 A→Z: 1/1 PASS

Final overlay genuine-checkout rereadiness:

`V2_9_8B_AUG25_A_TO_Z_REPAIR_REREADINESS_PASS`

## Intended tests and proofs committed with the repair

New:

- `tests/support/four_token_historical_authorization_portable.py` —
  portable historical-authorization fixture for provenance proofs
- `tests/test_v2_9_8b_aug25_consumed_authorization_historical_disposition.py` —
  exact `...4563a9dd` `CONSUMED_CHILD_EXITED_ZERO` fail-closed enumeration
- `tests/test_v2_9_8b_cycle2_frozen_lane_evidence_carrier_conformance.py` —
  Cycle-2 linked-market projection; different-pool and thin-carrier fail closed
- `tests/test_v2_9_8b_exception_terminal_compatibility_conformance.py` —
  heartbeat optional `failure_event` and `owned_proof_cycle_id` lifetime
- `tests/test_v2_9_8b_lawful_preclose_terminal_acceptance.py` —
  typed preclose skip vs untyped skip
- `tests/test_v2_9_8b_scheduler_yield_ownership_projection_conformance.py` —
  cooperative yield only after canonical PENDING release

Modified to keep the same production repairs honest:

- provenance: `07d92adf`, latest-consumed, and handoff suites now include
  `...4563a9dd` in the future non-reuse root
- Cycle-2 linked market: callback-consume materialize integration
- Cycle-2 isolation clock: cycle2 materialization fault isolation
- terminal accounting / preclose correspondence: campaign accounting,
  cycle-accounting adapter, factory terminal, full-run wiring, timely
  preclose, post-rollover-2 exception envelope
- Standard-4H / offline 4/2/2 live-derived ceilings rather than stale
  literals
- Migration-061 honesty: pair-ready current-head catalogue, historical
  four-token reconciliation through exact 001–055 prefix
- source-compatibility import path and WINDOW_15M wrapper isolation from
  the live authoritative database

`tests/__init__.py` remains untracked and excluded. Historical
`operator-runs/**` remains untracked and excluded.

## Governance preserved

- Source Governor: every live request still requires `_require_owners` /
  `_admit_source_request`. The frozen-lane helper reads already-linked
  responses only.
- Central Scheduler: pre-admission still uses `enqueue_job`. Cooperative
  yield cannot invent PENDING while the canonical job is running, locked, or
  started.
- Migration-061: ledger head remains
  `061_standard_4h_progression_fault_preservation.sql`; current package
  identity `MIGRATION_061_20260823T200709Z` is unchanged.
- Terminal accounting: required correspondence remains complete; shared
  terminal cleanup remains once; first terminal cause remains immutable.

## Immutable runtime evidence

Authoritative DB SHA remained:

`2fe2106be9ab9a7959b644aff883cece9e59e9894352eb02cd08fa24d32cb5ab`

`PRAGMA integrity_check` = `ok`

`PRAGMA foreign_key_check` = zero rows

No `-wal` / `-shm` / `-journal`.

Consumed Aug-25 authorization package remained unchanged:

- ID: `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260825T134723Z_4563a9dd`
- SHA-256: `f5cb7678127716eeb8b15edfd8f637a7f18267815a74562de75f1ca7f42d51f0`
- size: `4470`
- mode: `0444`
- disposition: `CONSUMED_CHILD_EXITED_ZERO`

No runtime call, provider call, Solana RPC, PumpPortal WebSocket, DB write,
migration, authorization creation, retry, rerun, resume, restart, or successor
occurred during implementation closeout.

## Authorization boundary

`AUTHORIZATION_PREPARATION_NOT_PERMITTED`

This closeout does not create a replacement authorization and does not reuse
`...4563a9dd` or `...07d92adf`. Transitions A and B remain encoded and do not
apply until a later post-commit rereadiness creates an exact checkpoint HEAD.

## Permanent locks

All Printer V1 permanent locks remain unchanged: Solana-only, Solana
memecoin-only, paper-only, no live wallet/private keys/signing/real funds/live
execution, no paid API dependency, no scoring/ranking/confidence/weighted
logic, no embeddings/vectors, Source Governor mandatory, Central Scheduler
mandatory, dirty memory excluded, 5m support-only, Cycle 3 locked, 12h/24h
locked, retrieval locked, BUY/SELL/HOLD locked, positions/trades/paper audits/
PnL locked, and no automatic retry/rerun/resume/restart/successor.

## Exact next permitted action

```text
POST-COMMIT EXACT-HEAD / WORKTREE / DB REREADINESS ONLY
```

No fresh authorization may be prepared until that separate rereadiness gate
passes and creates the exact checkpoint HEAD to which any future authorization
must bind.
