# Printer V1 V2-9.8B PR #191 GraduatedSupplyError Compatibility Corrective Design

Date: 2026-08-19

## Authority and scope

This bounded corrective follows the independent PR #191 adoption review finding:

`GRADUATED_SUPPLY_PUBLIC_EXCEPTION_BASE_COMPATIBILITY_BREAK`

Approved executable base remains:

`f40210f439d3e8366369e7c919dc9dd011868cb3`

The corrective stays inside draft PR #191. It does not run Printer, call providers, create/reuse an authorization, add a migration, change discovery/market gates, change Scheduler policy, or unlock any protected capability.

## Compatibility requirement

`src/printer_v1/operator_cli/graduated_supply_front_door.py` is a compatibility adapter over the byte-preserved original owner in `_graduated_supply_front_door_base.py`.

The adapter must satisfy both contracts at once:

1. preserved/re-exported base functions that still raise the original `_base.GraduatedSupplyError` remain catchable through the public `GraduatedSupplyError` import;
2. corrective Cycle-2 failures still carry typed categorical code plus bounded context and still expose the categorical dynamic class name used by the existing live terminal classifier.

## Design decision

The independent review initially suggested making the new public typed class inherit `_base.GraduatedSupplyError`. Before production implementation, that was refined because subclassing alone is insufficient: an instance of the base superclass is not catchable by an `except` clause naming only its subclass.

The compatibility-safe design is therefore:

- public `GraduatedSupplyError` is the exact preserved `_base.GraduatedSupplyError` object;
- private `_TypedGraduatedSupplyError` inherits the public/base class and owns `.code`, `.stage`, `.mint`, `.pool`, `.admission_authority`, `.nomination_source`, and bounded `.detail`;
- dynamic categorical error classes inherit `_TypedGraduatedSupplyError`;
- `_typed_error(...)` continues to create/stage only those typed corrective failures;
- `build_graduated_supply(...)` re-raises `_TypedGraduatedSupplyError` unchanged, but converts an ordinary preserved `_base.GraduatedSupplyError` into the typed corrective form before it crosses the authoritative Cycle-2 boundary;
- re-exported preserved functions remain unchanged and may still raise the original public/base exception directly.

This preserves old public catches while retaining the PR #191 diagnostic behavior.

## Focused TDD proof

RED contract:

- assert public `GraduatedSupplyError is _base.GraduatedSupplyError`;
- invoke a preserved base helper that raises the original exception and prove it is catchable through the public type.

Expected pre-fix RED: the identity assertion fails while the four existing historical-carrier tests remain green.

GREEN proof after the minimal production change:

- new compatibility regression passes;
- all existing Cycle-2 historical-carrier and diagnostic-durability tests remain green;
- existing Scheduler compatibility suite remains green;
- the four production modules compile;
- `git diff --check` remains clean.

## Unchanged locks

No Migration 059. No new source/provider. No retry or endpoint rotation. No scoring/ranking/confidence/weights. No liquidity-floor, freeze-depth, selection, disjointness, lifecycle, Source Governor, Central Scheduler, memory, retrieval, decision, position, trade, audit, PnL, 5m, 12h, or 24h policy change.

Solana-only, Solana-memecoin-only, paper-only remain permanent.

## Stop condition

After GREEN focused proof, remove all temporary proof scaffolding, close the temporary proof PR without merge, record corrective closeout, and leave PR #191 draft/unmerged for independent re-review / operator adoption review.