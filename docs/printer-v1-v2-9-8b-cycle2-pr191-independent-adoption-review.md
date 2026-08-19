# Printer V1 V2-9.8B Cycle-2 PR #191 Independent Adoption Review

Date: 2026-08-19

## Scope and authority

This review is the independent review / operator-adoption gate required by `CURRENT_HANDOFF.md` for draft PR #191. It reviews the exact corrective branch without running Printer, providers, lifecycle work, or any authorization.

Reviewed PR head before this review document: `5c5042ba7a3a3301f17a8eecf2a62d435a6f624b`

Approved executable base: `f40210f439d3e8366369e7c919dc9dd011868cb3`

PR: `#191` — open, draft, unmerged, mergeable at review.

## Review results

### PASS — ancestry and scope

The PR is directly based on the approved executable baseline. The compare merge base is exactly `f40210f439d3e8366369e7c919dc9dd011868cb3`; the reviewed head is ahead and not behind.

The permanent PR diff contains only the historical direct-proof repair, diagnostic-durability repair, focused tests, design/closeout documents, and handoff update. No Migration 059, provider addition, paid API, retry/rotation change, scoring/ranking logic, financial capability, Source Governor bypass, or Central Scheduler bypass is introduced.

### PASS — preserved owner implementations

The adapter split genuinely preserves the pre-repair owners byte-for-byte:

- `f40210f:src/printer_v1/operator_cli/graduated_supply_front_door.py` and reviewed `src/printer_v1/operator_cli/_graduated_supply_front_door_base.py` share Git blob SHA `049f41ba91ed1c780615abd5e58cee253430ae70`.
- `f40210f:src/printer_v1/scheduler/scheduler.py` and reviewed `src/printer_v1/scheduler/_scheduler_base.py` share Git blob SHA `06cb3ad8cee3b446c21039753ba02ebba4242d31`.

### PASS — core Cycle-2 corrective behavior

The historical proof repair remains correctly bounded:

- only exact registry-backed `PUMPSWAP_GRADUATED_CONFIRMED` candidates can be rehydrated;
- exact mint/pool agreement is required;
- immutable migration signature, PumpSwap program binding, and positive graduation time are required;
- no proof is fabricated;
- `MARKET_PRESENT_POOL` remains unchanged and does not acquire Pump provenance;
- the existing source-specific validator remains the final admission authority.

The diagnostic repair remains non-authoritative:

- only an exact matching staged Scheduler job can receive the bounded diagnostic envelope;
- the Scheduler observer and pre-admission attempt retain the categorical terminal cause;
- unmatched/generic failures retain the established plain-string behavior;
- retries and scheduling policy are unchanged.

Existing bounded proof remains valid: 7 corrective tests passed, 25 Scheduler compatibility tests passed, changed production modules compiled, and diff hygiene was clean.

## Blocking finding

Classification: `A — CODE DEFECT`, bounded compatibility regression.

Finding:

`GRADUATED_SUPPLY_PUBLIC_EXCEPTION_BASE_COMPATIBILITY_BREAK`

The public adapter first re-exports the preserved base surface, then defines a new public `GraduatedSupplyError(RuntimeError)`. The preserved base module separately defines `_base.GraduatedSupplyError(RuntimeError)`. These are sibling exception classes rather than a compatible inheritance chain.

Re-exported preserved functions continue to execute in the `_base` module namespace. Therefore a preserved function that raises its original `_base.GraduatedSupplyError` is not catchable by a caller that imports and catches the new public `GraduatedSupplyError`.

This does not invalidate the repaired `build_graduated_supply` Cycle-2 path because that wrapper explicitly converts `_base.GraduatedSupplyError` to the typed public form. It is nevertheless a real public-module compatibility regression and conflicts with the adapter's stated purpose of preserving the existing surface.

### Minimum corrective design

Do not change discovery, sources, market gates, liquidity, freeze, selection, Scheduler policy, retries, lifecycle, or authorization behavior.

The minimum correction is:

1. make public `GraduatedSupplyError` inherit from `_base.GraduatedSupplyError` rather than directly from `RuntimeError`;
2. keep the current typed-code/context behavior on that subclass;
3. add a focused compatibility regression proving the public typed exception remains a subtype of the preserved base exception and that an original preserved base error remains catchable through the public type contract;
4. rerun the existing 7 corrective tests, the 25 Scheduler compatibility tests, production-module compile, and `git diff --check`.

No migration or broader regression suite is justified unless that focused proof exposes wider coupling.

## Adoption verdict

`V2_9_8B_CYCLE2_PR191_INDEPENDENT_ADOPTION_REVIEW_BLOCKED_ONE_BOUNDED_EXCEPTION_COMPATIBILITY_DEFECT`

PR #191 must remain draft and unmerged until the compatibility corrective is implemented and independently re-reviewed.

This review does not authorize Printer, create/reuse an authorization, or permit a 4/2/2 runtime.

## Exact next permitted action

`V2-9.8B PR #191 GraduatedSupplyError Public/Base Compatibility Corrective — design/specification, then implementation only if approved, followed by focused proof and review closeout.`
