# Printer V1 V2-9.8B WINDOW_15M Invocation-Scoped Source-Request Repair Design

## Verdict

`V2_9_8B_WINDOW_15M_SOURCE_REQUEST_SCOPE_REPAIR_DESIGN_COMPLETE`

This is design-only. No production code, tests, database rows, authorization
packages, application evidence, provider calls, discovery, Scheduler work,
lifecycle work, or memory work were changed or executed.

## Baseline

| Item | Value |
| --- | --- |
| Audit branch | `agent/v2-9-8b-window-15m-source-request-scope-contamination-audit` |
| Audit commit | `95890633670a1818251948e462ab19accca75aed` |
| Design branch | `agent/v2-9-8b-window-15m-source-request-scope-repair-design` |
| Controlling audit | `docs/printer-v1-v2-9-8b-window-15m-source-request-scope-contamination-audit.md` |
| Failed execution | `20260806T120233Z-5eb0d3b5f0eb` |
| Consumed authorization | `V2_9_8B_WINDOW_15M_AUTH_20260806T115911Z` |

## Design objective

Make durable source-request ownership invocation-local without weakening the
three-set reconciliation invariant:

`D = S = M`

The repair must preserve prefix lookup as a detector of stage-reporting omissions,
but the prefix must be unique to one campaign invocation so historical rows can
never enter the current durable set.

The repair also makes every reconciliation failure category and bounded request-ID
difference visible in terminal evidence.

## Root cause being repaired

The permanent operational path currently inherits the legacy static prefixes:

```text
discovery_request_key_prefix = v2-9-7e-44
front_door_request_key_prefix = v2-9-7e-44
```

The durable loader performs a persistent-DB prefix scan. Earlier campaigns using
the same prefix therefore contaminate the current `D` set.

This is a request-scope ownership defect. It is not a provider, temporal,
Scheduler, selection, lifecycle, or memory-policy defect.

## Canonical ownership

### Scope construction owner

`AuthoritativeLiveOperationalCampaignOwner.run_operational` is the canonical
composition owner because it already owns the exact:

- execution identity (`selection_seed`);
- campaign ID;
- campaign-run ID;
- cycle ID;
- permanent operational-mode decision.

It must construct one immutable invocation scope before candidate-supply source
work begins.

### Scope validation and reconciliation owner

`printer_v1.discovery.permanent_discovery_availability` remains the canonical
source-accounting and reconciliation owner. It must own:

- typed scope validation;
- pre-existing-prefix collision inspection;
- durable prefix lookup;
- exact mismatch categorization;
- bounded terminal-detail formatting.

### Child-stage behavior

Existing discovery, locator, market, backup, protocol, and reconciliation stages
remain the source-request producers. They receive the canonical root through the
existing composition path and continue adding stage-specific suffixes.

No provider, request order, budget, selection, or stage reservation changes.

## Typed invocation-scope contract

Add an immutable contract equivalent to:

```python
@dataclass(frozen=True)
class CampaignSourceRequestScope:
    scope_version: str
    request_key_root: str
    execution_id: str
    campaign_id: str
    run_id: str
    cycle_id: str
```

Required scope version:

`PRINTER_V1_CAMPAIGN_SOURCE_REQUEST_SCOPE_V1`

### Canonical root

Construct deterministically from the exact execution ID:

```text
v2-9-8b-window15m-<execution_id>
```

The execution ID is already unique per public action and bound to the campaign,
run, cycle, configuration, authorization, and DB target through the operational
command.

The typed contract still carries campaign/run/cycle identities so validation can
prove the scope was constructed for the current invocation rather than merely
receiving an arbitrary unique string.

### Validation

Require:

- exact supported scope version;
- non-empty execution/campaign/run/cycle identities;
- root exactly equal to the canonical derivation;
- printable ASCII root with no whitespace or path separators;
- bounded root length;
- root must not equal or begin with the legacy static `v2-9-7e-44` root;
- scope identities must equal the active command identities.

Invalid scope blocks before source work with a typed error.

## Operational composition

In permanent operational mode, `run_operational` must:

1. construct the typed scope from the current invocation identities;
2. validate it;
3. pass the same canonical root as both the discovery and front-door request-key
   root through `build_graduated_supply`;
4. store the typed scope in supply diagnostics;
5. pass only that exact root to pre-holder reconciliation.

The two existing prefix parameters may remain for compatibility with historical
non-operational tests and explicit callers, but permanent operational mode must
never use their legacy defaults.

## Permanent-mode fail-closed rule

`build_graduated_supply` must fail before source work when:

- `permanent_availability=True` and no typed scope is supplied;
- supplied discovery/front-door roots differ from the typed root;
- either root is the legacy default;
- scope identities do not match campaign/run/cycle/execution inputs.

Suggested typed blockers:

```text
CAMPAIGN_SOURCE_REQUEST_SCOPE_REQUIRED
CAMPAIGN_SOURCE_REQUEST_SCOPE_INVALID
CAMPAIGN_SOURCE_REQUEST_SCOPE_IDENTITY_MISMATCH
CAMPAIGN_SOURCE_REQUEST_SCOPE_PREFIX_MISMATCH
LEGACY_STATIC_REQUEST_SCOPE_BLOCKED_OPERATIONALLY
```

Legacy non-permanent fixture paths may retain explicit historical defaults only
when they do not claim permanent operational ownership.

## Pre-source collision gate

Before the first provider request for the supply invocation, inspect the
authoritative DB for:

```sql
SELECT id, request_key
FROM printer_source_requests
WHERE request_key = ? OR request_key LIKE ?
ORDER BY id
```

using the new root and `<root>%`.

Expected count before source work: `0`.

Any existing row blocks before provider I/O:

```text
CAMPAIGN_SOURCE_REQUEST_SCOPE_ALREADY_EXISTS
```

The blocker must include a bounded count and bounded existing request-ID list.

Do not delete, rename, or reuse existing rows. A collision is evidence of identity
reuse or an incomplete prior invocation and requires inspection.

## Child request-key derivation

All source-producing stages must derive keys from the canonical root, preserving
existing deterministic stage suffixes and sequences.

Covered stages include:

- DexScreener fresh-profile locator;
- direct Pump finalized live-tail discovery;
- PumpSwap migration/protocol verification;
- GeckoTerminal nomination;
- DexScreener market batching;
- GeckoTerminal exact-pool reconciliation;
- bounded unknown-liquidity backup;
- residual protocol confirmation.

No request may use a static stage-global key in permanent operational mode.

## Durable-set construction

Keep the existing two-part durable proof:

1. current stage-reported IDs must exist in `printer_source_requests`;
2. invocation-root lookup discovers any durable current request omitted by stage
   reporting.

The resulting `D` set must contain only rows whose `request_key` belongs to the
exact current root.

Add explicit returned evidence:

```text
request_scope_version
request_key_root
prefix_lookup_request_ids
known_stage_request_ids_proven_durable
out_of_scope_stage_request_ids
```

If a current stage reports an ID whose durable request key is outside the scope,
block with:

`CURRENT_STAGE_REQUEST_OUTSIDE_CAMPAIGN_SCOPE`

Do not silently drop it.

## Exact mismatch categories

Every blocked reconciliation branch must assign one stable categorical detail.

Required categories:

```text
DURABLE_REQUEST_NOT_STAGE_REPORTED
DURABLE_REQUEST_NOT_MANIFESTED
STAGE_REQUEST_NOT_DURABLE
STAGE_REQUEST_NOT_MANIFESTED
MANIFEST_REQUEST_NOT_DURABLE
DUPLICATE_COVERAGE_REQUEST_ID
DUPLICATE_DURABLE_REQUEST_ID
STAGE_OWNERSHIP_GAP
STAGE_ACCOUNTING_BLOCKER
CURRENT_STAGE_REQUEST_OUTSIDE_CAMPAIGN_SCOPE
```

When more than one relation fails, return:

`MULTIPLE_SOURCE_REQUEST_RECONCILIATION_DEFECTS`

with an ordered list of the individual categories.

## Bounded terminal detail

Before raising the existing outer error code, construct deterministic compact
detail equivalent to:

```text
DURABLE_REQUEST_NOT_STAGE_REPORTED:count=11:ids=1940,1941,...
```

Rules:

- report exact total count;
- include at most the first 20 sorted IDs per category;
- include a truncation flag when more exist;
- never print source payloads, URLs, headers, secrets, or response bodies;
- preserve the outer error code
  `CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH` for compatibility.

Also retain the complete structured differences in the in-memory reconciliation
object used by terminal reporting and focused tests.

No DB schema change is required.

## Post-repair behavior for the failed pattern

With a new invocation root:

- historical requests `1940`–`1950` remain preserved but are outside the new root;
- current requests form `D`, `S`, and `M` independently;
- ordinary provider failures remain represented as current durable requests with
  `BLOCKED` terminal coverage rather than becoming attribution mismatches;
- holder work begins only if the exact current three-set invariant passes.

The consumed run itself is not replayed or repaired in place.

## Expected production files

Implementation should normally be limited to:

- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
- `src/printer_v1/operator_cli/graduated_supply_front_door.py`
- `src/printer_v1/discovery/permanent_discovery_availability.py`
- nearest focused tests
- repair closeout documentation

`operational_memory_factory_command.py` should not need behavioral changes because
it already supplies the exact invocation identities. If static inspection proves
a narrow composition update is required there, document why and keep it limited
to typed scope propagation.

No provider adapter, Source Governor, Central Scheduler, selection, lifecycle,
memory, DB schema, authorization, wrapper, or launcher changes are expected.

## Focused proof design

Use disposable databases, fixture transports, deterministic identities, and no
real providers.

Prove at minimum:

1. permanent operational composition creates the exact canonical root;
2. both discovery and front-door children use that root;
3. legacy static defaults are rejected in permanent mode;
4. missing typed scope is rejected before provider work;
5. mismatched campaign/run/cycle/execution identity is rejected;
6. pre-existing root collision blocks before provider work;
7. campaign A and campaign B on the same DB use disjoint roots and disjoint `D`
   sets;
8. historical `v2-9-7e-44%` rows do not enter either new `D` set;
9. all current request IDs appear exactly once in `D`, `S`, and `M` on PASS;
10. a current durable request intentionally omitted from stage reporting is found
    by the unique prefix and classified
    `DURABLE_REQUEST_NOT_STAGE_REPORTED`;
11. a current durable request omitted from coverage is classified
    `DURABLE_REQUEST_NOT_MANIFESTED`;
12. a stage-only non-durable ID is classified `STAGE_REQUEST_NOT_DURABLE`;
13. duplicate coverage and stage ownership gaps retain fail-closed behavior;
14. ordinary provider failure rows reconcile when stage coverage is complete;
15. exact categories and bounded IDs appear in the raised terminal detail;
16. no holder provider call occurs on reconciliation failure;
17. no Scheduler, lifecycle, window, memory, retrieval, or financial work occurs;
18. existing source-specific temporal and mixed-slot tests remain green.

## Minimum verification

Run only:

- new invocation-scope tests;
- nearest permanent-discovery reconciliation tests;
- nearest campaign pre-holder accounting tests;
- source-specific temporal tests;
- Python compilation of changed modules;
- `git diff --check`;
- static search confirming permanent operational mode cannot use
  `v2-9-7e-44`;
- authoritative DB identity before/after unchanged;
- no provider/runtime execution.

Do not run a broad repository suite unless the implementation becomes
unexpectedly cross-cutting.

## Money-usefulness contribution

Invocation-local source ownership ensures that memory candidates are supported by
the source evidence actually gathered for their campaign. It prevents historical
requests from distorting current budget truth, blocking valid source evidence, or
being mistaken for current observations.

## What the design improves

- removes historical request contamination from persistent operational runs;
- preserves exact omission detection through prefix lookup;
- prevents scope reuse before any provider cost or DB mutation;
- makes source-accounting safe-stops diagnosable from terminal evidence;
- keeps provider failures separate from accounting ownership failures;
- supports repeated bounded campaigns on one authoritative DB safely.

## What the design does not unlock

- a new authorization or campaign run;
- automatic retry, resume, restart, or successor;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, or `WINDOW_24H`;
- retrieval or dirty-memory use;
- paper decisions or BUY/SELL/HOLD;
- positions, trades, audits, or PnL;
- wallets, signing, real funds, paid APIs;
- scoring, ranking, confidence, weighting, embeddings, or vectors.

## Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Design control |
| --- | --- |
| New root collides with prior partial work | Pre-source collision gate |
| Removing prefix lookup hides omitted stages | Prefix lookup retained, root made invocation-local |
| Child stages drift to different roots | One typed scope, exact root-equality validation |
| Legacy tests depend on static defaults | Permit only explicit non-permanent legacy paths |
| Terminal detail becomes unbounded | Sorted IDs capped at 20 with exact count |
| Provider failures are misclassified | Complete blocked-stage coverage still reconciles |
| Scope expands into providers or Scheduler | File and behavior boundaries frozen |
| Failed evidence is rewritten | Authoritative DB and application evidence remain immutable |

## Exact next lane

Implement the typed invocation-scoped request-key contract, collision gate,
exact reconciliation categories, bounded terminal detail, focused disposable
proof, and closeout.

Stop before any authorization or real campaign execution.