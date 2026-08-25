# Printer V1 / V2-9.8B — Durable-Admission Terminal-Accounting Scope Repair Design

Verdict:

`V2_9_8B_DURABLE_ADMISSION_TERMINAL_ACCOUNTING_SCOPE_REPAIR_DESIGN_PASS_READY_FOR_NARROW_IMPLEMENTATION`

Governing forensic audit:

`docs/printer-v1-v2-9-8b-consumed-07d92adf-forensic-audit.md`

## Objective

Repair the production integration boundary so proposed pre-admission accounting
owners remain valid evidence collectors but are never interpreted as durable
admitted campaign cycles.

Also restore the intended fail-closed exception type by importing
`TerminalClosureError`.

No upstream frozen-lane/source/provider behavior changes.

## Canonical authority split

Two concepts MUST remain separate:

1. **Accounting registration**
   - may begin for a proposed later cycle before admission;
   - captures real pre-admission source/validation evidence;
   - `registered_cycle_ids` is therefore not admission authority.

2. **Durable cycle admission**
   - authoritative source:
     `printer_memory_factory_campaign_cycles`
     for the exact campaign/run;
   - only these rows determine whether Lane-4 single-cycle or exact two-cycle
     terminal accounting applies.

The accounting registry MUST NOT become a second admission ledger.

## Narrow implementation surface

Expected production surface:

- `src/printer_v1/operator_cli/operational_memory_factory_command.py`
- focused tests only

`campaign_full_run_accounting.py` should remain the canonical Lane-4 accounting
owner unless implementation proves a narrowly necessary validation helper
belongs there. No schema/database migration is expected.

`authoritative_live_operational_campaign._bind_later_cycle_accounting_owner()`
must remain capable of binding pre-admission evidence; do not defer evidence
collection until after admission.

## Required behavior

### 1. Import the real fail-closed exception

`operational_memory_factory_command.py` must import
`TerminalClosureError` from `unified_terminal_closure`.

No alias or replacement exception.

### 2. Resolve terminal accounting scope from durable admitted cycles

Before the outer command chooses a single owner versus
`CampaignSixUnitProjection`, it must read the exact admitted cycle rows for the
campaign/run from the authoritative DB.

Allowed durable shapes for this V1 lane:

- exact ordinal `(1,)`
- exact ordinals `(1, 2)`

Any other durable ordinal shape is fail-closed.

### 3. One durable cycle with a provisional Cycle-2 owner

When durable admission is exact `(1,)`:

- use only the admitted Cycle-1 `CampaignSixUnitOwner` as the canonical full-run
  accounting owner;
- use the action-local ledger sliced to that admitted cycle for canonical
  owner/action-local reconciliation;
- do not build or pass a `CampaignSixUnitProjection` to Lane-4;
- do not require a Lane-4 two-cycle `terminal_accounting` mapping;
- preserve the original terminal cause
  `LATER_CYCLE_ATTEMPT_PERSISTENCE_FAILED`;
- preserve the frozen-lane diagnostic separately;
- do not create a synthetic Cycle-2 durable row;
- do not reinterpret the proposed Cycle-2 owner as admitted.

Extra registered owners may be ignored for canonical Lane-4 scope only when
they are provably non-admitted proposed-cycle owners for this exact
campaign/run. An arbitrary unmatched extra owner must still fail closed.

A valid proof for an extra provisional owner is an exact matching
`printer_pre_admission_discovery_attempts.proposed_cycle_id` for the same
campaign/run with:

- no durable cycle row for that proposed ID; and
- `consumed_cycle_id IS NULL`.

The implementation may further require a terminal attempt state if that is
needed to keep the boundary fail-closed.

### 4. Exact two durable cycles

When durable admission is exact `(1, 2)`:

- registered canonical owner IDs must match admitted cycle IDs exactly;
- use the campaign projection;
- retain the existing Lane-4 exact-two-cycle requirements;
- require canonical `terminal_accounting`;
- preserve exact ordinal `(1,2)` semantics;
- preserve peer-stop and primary-fault rules.

This repair must not weaken any existing two-cycle Lane-4 proof.

### 5. Terminal reconciliation sealing

Terminal reconciliation stages used for canonical full-run accounting must be
scoped to durable admitted cycles.

A provisional non-admitted owner may retain pre-admission evidence already
captured, but it must not receive treatment that promotes it into canonical
admitted-cycle terminal accounting.

### 6. Exception/secondary terminalization path

Any post-initialization exception path that currently chooses a campaign
projection solely from:

`len(registered_cycle_ids) > 1`

must use the same durable-admission scope rule.

The repair must not fix only the happy/normal terminal path while leaving the
reconstructed/failure terminal path vulnerable to the same projection error.

## Failure semantics

The upstream reason:

`FROZEN_TRACKING_LANE_UNAVAILABLE`

remains an honest fail-closed application-validation outcome.

The repaired terminal path should preserve:

`LATER_CYCLE_ATTEMPT_PERSISTENCE_FAILED`

as first terminal cause and complete cleanup/terminal truth without inventing
Cycle-2 admission.

If a truly inconsistent accounting/admission relationship occurs, fail closed
with `TerminalClosureError` / existing accounting errors as appropriate. Never
fall through to `NameError`.

## Required production-path proof

Tests must inject the underlying production condition, not the desired final
classification.

Minimum sufficient proof:

1. **Real later-cycle frozen-lane/no-admission regression**
   - drive the actual later-cycle production path to an unavailable frozen
     tracking lane;
   - prove proposed Cycle-2 accounting evidence can be registered;
   - prove Cycle 2 remains non-admitted;
   - prove the outer terminal path does not build canonical two-cycle Lane-4
     accounting;
   - prove original persistence terminal cause is preserved;
   - prove cleanup and terminalization complete;
   - prove no `NameError`.

2. **Unmatched provisional-owner fail-closed case**
   - an extra registry owner with no matching non-consumed pre-admission attempt
     must block rather than be silently ignored.

3. **Genuine two-cycle regression**
   - two admitted ordinals `(1,2)` still select the campaign projection;
   - canonical Lane-4 `terminal_accounting` remains mandatory;
   - registered/admitted identity equality remains enforced.

4. **Exception-path regression**
   - the post-initialization terminalization path uses the same durable scope and
     cannot promote a provisional owner.

5. **TerminalClosureError import/masking regression**
   - intended fail-closed terminal closure produces `TerminalClosureError`, not
     `NameError`.

Nearest existing focused suites should include the shared-terminal
pre-lifecycle integration, Lane-4 bounded proof, campaign accounting terminal
enforcement, multi-cycle projection finalization, and the new repair-specific
tests.

Run changed tests + nearest contract tests + `py_compile` + `git diff --check`.
No broad suite unless the implementation unexpectedly becomes cross-cutting.

## Forbidden implementation shortcuts

Do not:

- remove the Lane-4 `(1,2)` requirement;
- make `CampaignSixUnitProjection` tolerate missing durable ordinals;
- manufacture a Cycle-2 admission row;
- convert the failed attempt to consumed/admitted;
- bypass frozen-lane validation;
- delete provisional evidence;
- infer admission from registry membership;
- create a new DB/schema/accounting ledger;
- add automatic retry/recovery;
- activate Cycle 3/12h/24h/retrieval/trading/PnL.

## Closeout expectation

If implementation and bounded proof pass, closeout must show:

- observed consumed authorization remains historical and non-reusable;
- DB/history from the consumed run is not rewritten;
- honest `FROZEN_TRACKING_LANE_UNAVAILABLE` evidence remains unchanged;
- one-cycle/no-admission terminalization is clean and first-cause preserving;
- exact two-cycle Lane-4 behavior remains unchanged;
- no retry/successor is authorized.

Exact next action after this design is committed:

`NARROW DURABLE-ADMISSION TERMINAL-ACCOUNTING SCOPE REPAIR IMPLEMENTATION ONLY`
