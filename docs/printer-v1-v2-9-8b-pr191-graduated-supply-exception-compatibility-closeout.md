# Printer V1 V2-9.8B PR #191 GraduatedSupplyError Compatibility Corrective Closeout

Date: 2026-08-19

## Scope

This closeout closes only the bounded compatibility corrective required by the independent PR #191 adoption review.

Finding closed:

`GRADUATED_SUPPLY_PUBLIC_EXCEPTION_BASE_COMPATIBILITY_BREAK`

PR #191 remains draft and unmerged. No Printer runtime, provider call, campaign authorization, retry/resume/restart/successor, lifecycle execution, wallet/signing/funds action, or financial capability was used.

## Design applied

The public exception contract is restored without weakening the typed Cycle-2 diagnostic contract:

- public `GraduatedSupplyError` is exactly `_base.GraduatedSupplyError`;
- private `_TypedGraduatedSupplyError` extends that preserved public/base class and owns the bounded typed metadata;
- dynamic categorical classes extend the private typed class;
- typed corrective errors therefore remain instances of the historical public exception and retain the categorical class-name fallback used by the live terminal classifier;
- preserved/re-exported base functions may still raise the original base object, and callers catching public `GraduatedSupplyError` catch it exactly as before;
- `build_graduated_supply(...)` re-raises already-typed corrective errors and converts ordinary preserved base supply errors at the Cycle-2 boundary.

Production corrective commit:

`642b55795858a8c4243580b1e6730515f9d9c4b6`

Design record:

`docs/printer-v1-v2-9-8b-pr191-graduated-supply-exception-compatibility-design.md`

## TDD evidence

### RED

Temporary proof PR: `#196`

GitHub Actions run: `32297538063`

Result before production change:

- historical-carrier test file: `1 failed, 4 passed`;
- the sole failure was `test_public_graduated_supply_error_preserves_base_catch_contract`;
- failure was exactly the expected identity mismatch between public `GraduatedSupplyError` and `_base.GraduatedSupplyError`.

This is valid RED evidence: the fixture and four pre-existing repair tests passed, while only the missing compatibility behavior failed.

### Narrow GREEN

GitHub Actions run: `32297671884`

After the production corrective:

- historical-carrier/compatibility file: `5 passed in 2.59s`;
- production compile: PASS;
- diff hygiene: PASS.

### Full bounded GREEN

GitHub Actions run: `32297731250`

- Cycle-2 historical carrier + diagnostic durability regressions: `8 passed in 12.27s`;
- existing Scheduler compatibility suite `tests/test_phase3_scheduler_resource_governor.py`: `25 passed in 83.96s`;
- compile of `graduated_supply_front_door.py`, `_graduated_supply_front_door_base.py`, `scheduler.py`, `_scheduler_base.py`: PASS;
- `git diff --check`: clean.

No broad regression suite was required because the focused proof and the existing central-Scheduler compatibility suite exposed no wider coupling.

## Proof scaffold cleanup

Temporary proof PR `#196` was closed without merge.

The temporary workflow `.github/workflows/tmp-pr191-exception-compat-proof.yml` was removed from the product branch at cleanup commit:

`3afe157513fc9a23e0eccc23d3bbc252442b9894`

The disposable proof base remains anchored to the pre-test review/handoff commit and is not an executable/adoption target.

## Lock preservation

Unchanged:

- Solana-only;
- Solana memecoin-only;
- paper-only;
- no paid API;
- no Source Governor bypass;
- no Central Scheduler bypass;
- no scoring/ranking/confidence/weighted logic;
- `$3,000` liquidity floor;
- freeze minimum depth 4;
- neutral deterministic two-token selection;
- Cycle-1/Cycle-2 disjointness;
- source budgets;
- retries `0`;
- endpoint rotation `false`;
- `WINDOW_5M_MICRO_EVENT` support-only;
- 12h/24h, retrieval, BUY/SELL/HOLD, positions, trades, audits, and PnL locked;
- no Migration 059.

All historical four-token authorizations remain consumed, immutable, and non-reusable. No new authorization exists.

## Verdict

`V2_9_8B_PR191_GRADUATED_SUPPLY_PUBLIC_BASE_EXCEPTION_COMPATIBILITY_CORRECTIVE_CLOSEOUT_PASS`

The bounded compatibility defect is repaired and proven without reopening the core Cycle-2 repair or changing any market/safety policy.

## Exact next permitted action

Independent re-review / operator adoption review of draft PR #191 on its exact final branch head after this closeout/handoff documentation successor.

Do not merge PR #191, create/reuse an authorization, or run Printer solely from this closeout.