# Printer V1 V2-9.8B Source-Free Discovery Capacity Authority Closeout

## Verdict

`V2_9_8B_SOURCE_FREE_DISCOVERY_CAPACITY_AUTHORITY_CLOSEOUT_PASS_READY_TO_RESUME_ADMISSION_HEALTH_PROJECTION`

The source-free discovery-capacity prerequisite is complete.

It now provides owner-backed, read-only authority for the two fields that previously blocked the 12-field `MultiCycleAdmissionHealth` projection:

- `provider_budgets_available`
- `discovery_capacity_available`

No later-cycle discovery, callback, cycle-2 persistence, factory wake integration, runtime, authorization, or source execution is unlocked by this closeout.

## Baseline and implementation chain

Closeout baseline:

`a2d5f5de5bb33ebe9e447725d2ba27ab6783ef7d`

Key prerequisite seams now closed:

1. source-free exact-two-token discovery-attempt manifest;
2. Solana-only manifest validation repair;
3. provider-reaching attempt detail using the existing 60-second accounting law;
4. source-failure lineage-boundary audit;
5. scoped current-window failure evidence-frontier repair;
6. provider package-capacity and exact recheck-boundary composition.

## What is now authoritative

### Exact attempt manifest

The source-free manifest remains pure and immutable. It derives request requirements from existing execution owners and machine-readable constants rather than operation-budget prose.

Current provider governed request totals for one exact two-token later-cycle discovery action are:

- DexScreener: 1
- GeckoTerminal: 2
- GoPlus: 1
- Helius Free: 1
- Solana RPC: 14

Tracker remains configuration-bound and is included only when the existing free configuration proves it enabled.

### Provider-reaching attempt accounting

Current consumed provider attempts use the same shared law as `count_recent_source_requests(...)`.

Positive attempt timestamp authority remains only:

`printer_source_requests.requested_at`

Provider-reaching evidence includes:

- response-backed attempts;
- attributable provider/adapter/network failures.

Pure Governor/pre-adapter failures remain excluded.

### Historical failure evidence frontier

Historical unlinked failure rows are not rewritten.

`printer_source_failures.created_at` may be used only as negative historical-exclusion evidence, in exact canonical SQLite UTC `YYYY-MM-DD HH:MM:SS` form.

- strict `created_at < cutoff` may prove a row cannot affect the current 60-second window;
- equality, newer evidence, malformed evidence, or otherwise unclassifiable evidence remains fail-closed;
- `created_at`, `failed_at`, retry metadata, and pacer state never become provider-attempt or package-ready timing authority.

### Provider package capacity

For every required provider:

```text
C = current consumed provider-reaching attempts
R = manifest required governed requests
L = SOURCE_REGISTRY rate ceiling
```

Package capacity is available only when:

```text
C + R <= L
```

If `R > L`, the provider is blocked with no future package-ready boundary.

If current consumption is the only blocker:

```text
needed_expirations = C + R - L
```

Attempts are ordered by:

```text
(requested_at, source_request_id)
```

The provider boundary is derived from the attempt at `needed_expirations - 1`.

Because the existing 60-second window is inclusive, an attempt at `T` still counts at exactly `T + 60s`.

Earliest lawful expiry is:

```text
T + 60 seconds + datetime.resolution
```

For multiple blocked providers, composed `recheck_at` is the latest authoritative provider boundary required for the whole package.

If any blocked provider lacks an authoritative boundary, composed `recheck_at = None`.

A package-ready timestamp is reevaluation evidence only, never a reservation.

## Read-only operational readiness evidence

The immediately preceding Step D operational DB projection reported:

- inspection time: `2026-08-13T14:03:54.434604+00:00`;
- all current consumed attempt counts were zero;
- DexScreener `0 / 1 / 60` => fits;
- GeckoTerminal `0 / 2 / 10` => fits;
- GoPlus `0 / 1 / 20` => fits;
- Helius Free `0 / 1 / 30` => fits;
- Solana RPC `0 / 14 / 30` => fits;
- `manifest_valid=True`;
- `provider_budgets_available=True`;
- `discovery_capacity_available=True`;
- `recheck_at=None`;
- SQLite `total_changes=0`;
- database SHA-256 unchanged before/after:
  `07035fba786aba1d141789e5c069fc5de5bfb6185b711500ce8fa901f5358bfd`.

These live-DB values remain point-in-time evidence only. Any later projection must reread current provider consumption.

## Verification

Focused Step D verification reported:

`59 passed`

The final focused set covered:

- package-fit law;
- `R > L` no-boundary behavior;
- exact inclusive 60-second expiry;
- needed-expiration indexing;
- multi-provider whole-package boundary;
- intervening consumption requiring fresh projection;
- manifest validity independent from provider availability;
- ambiguous evidence fail-closed behavior;
- absence of retry/pacer timing authority;
- zero operational activity.

No broad suite was required for this prerequisite closeout.

## Money-usefulness contribution

This prerequisite allows Printer to determine, before attempting later-cycle discovery, whether one additional exact two-token discovery package can fit inside the existing free-provider budgets without guessing, polling, or weakening Source Governor protections.

That directly supports safe growth from the current through-4h two-token cycle shape toward the four-token proof corpus while avoiding wasted attempts and provider-budget collapse.

## What the prerequisite improves

- exact owner-derived two-token discovery package shape;
- deterministic provider-budget readiness;
- current-window accounting that is not permanently poisoned by old unlinked rows;
- exact, evidence-backed future reevaluation boundaries when current provider consumption blocks admission;
- separation of provider availability from discovery-action validity;
- no copied rate limits or prose-derived budgets.

## What it still does not unlock

This closeout does not unlock:

- later-cycle discovery callback execution;
- source fetching;
- Scheduler admission work;
- cycle-2 persistence;
- one-loop factory wake integration;
- memory generation;
- four-token runtime/proof authorization;
- 12h/24h;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions, trades, audits, or PnL.

`TOKEN_CAPACITY` remains 2.

## Functionality Risks / Setbacks / Efficiency Blockers

- `package_ready_at` is not a reservation; intervening consumption can invalidate it.
- Current-window ambiguous provider evidence intentionally removes synthetic recheck authority.
- The low-level bare-`SourceRequest` failure-recording surface can still create an unlinked row; any current-window occurrence will safely block capacity until evidence becomes classifiable.
- Provider capacity is only one of twelve admission-health truths. Source budget, Scheduler, close reserve, lease, DB, supervision, lifecycle priority, cancellation, and protected-work capacity remain separate authorities.
- The later callback must still run every actual request through fresh Source Governor and Central Scheduler ownership.

## Correct next lane

Resume Step 1 of:

`docs/printer-v1-v2-9-8b-admission-health-and-wake-disposition-design.md`

Specifically:

**TDD the authoritative 12-field `MultiCycleAdmissionHealth` read-only projection.**

The two fields that previously blocked that lane now have concrete source-free authority:

- `provider_budgets_available` from the completed provider package-capacity projection;
- `discovery_capacity_available` from the validated exact-two-token manifest/action-shape projection.

Do not proceed to admission disposition/rearm, callback invocation, cycle-2 persistence, or factory-loop integration until the 12-field projection itself passes focused implementation and closeout.
