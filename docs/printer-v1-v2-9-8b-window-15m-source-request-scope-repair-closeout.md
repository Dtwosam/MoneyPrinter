# Printer V1 V2-9.8B WINDOW_15M Invocation-Scoped Source-Request Repair Closeout

## Verdict

`V2_9_8B_WINDOW_15M_SOURCE_REQUEST_SCOPE_REPAIR_PASS`

Implementation, focused disposable proof, and closeout only. No authorization was
created. No real campaign was run. No provider or runtime execution occurred.

## Baseline and repair branch

| Item | Value |
| --- | --- |
| Design branch / required HEAD | `agent/v2-9-8b-window-15m-source-request-scope-repair-design` / `1598f9f370745e52153e8a8e34aa75128226ca28` |
| Repair branch | `agent/v2-9-8b-window-15m-source-request-scope-repair` |
| Controlling design | `docs/printer-v1-v2-9-8b-window-15m-source-request-scope-repair-design.md` |
| Controlling audit | `docs/printer-v1-v2-9-8b-window-15m-source-request-scope-contamination-audit.md` |
| Consumed authorization (preserved) | `V2_9_8B_WINDOW_15M_AUTH_20260806T115911Z` |
| Failed execution (preserved) | `20260806T120233Z-5eb0d3b5f0eb` |
| First terminal cause | `CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH` |

Baseline gates before repair:

- exact design branch and HEAD verified;
- tracked tree/index clean (only untracked authorization/application evidence);
- no Printer campaign/discovery/Scheduler/factory process;
- no active lease/lock residue (historical leases are terminal);
- authoritative DB identity matched the post-failure identity below.

## Exact files changed

Production:

- `src/printer_v1/discovery/permanent_discovery_availability.py`
- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
- `src/printer_v1/operator_cli/graduated_supply_front_door.py`

Focused tests:

- `tests/test_v2_9_8b_window_15m_source_request_scope_repair.py` (new)
- `tests/test_v2_9_8b_durable_id_and_stage_blocker_repair.py` (category assertion update)
- `tests/test_v2_9_8b_window_15m_source_specific_temporal_contract_repair.py` (typed scope fixture for permanent path)
- `tests/test_v2_9_8b_window_15m_source_specific_admission_retained_evidence_repair.py` (typed scope fixture for permanent path)

Closeout:

- `docs/printer-v1-v2-9-8b-window-15m-source-request-scope-repair-closeout.md`

No DB migration. No provider, Source Governor ownership, Scheduler, selection,
liquidity floor, temporal rule, holder policy, retrieval, or financial changes.

## Root cause

Permanent operational composition inherited the legacy static request-key roots:

```text
discovery_request_key_prefix = v2-9-7e-44
front_door_request_key_prefix = v2-9-7e-44
```

Durable reconciliation then performed a persistent-DB prefix scan under that
shared root, so earlier campaigns contaminated the current `D` set and produced
`CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH` even when current stage
accounting was otherwise coherent.

This is a request-scope ownership defect, not a provider, temporal, Scheduler,
selection, lifecycle, or memory-policy defect.

## Typed scope contract

Immutable owner contract in `permanent_discovery_availability`:

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

- `scope_version = PRINTER_V1_CAMPAIGN_SOURCE_REQUEST_SCOPE_V1`
- canonical root = `v2-9-8b-window15m-<execution_id>`
- validation: exact version; non-empty identities; exact root derivation;
  printable ASCII; no whitespace/path separators; bounded length; root must not
  equal or begin with `v2-9-7e-44`; optional exact match to active command
  identities.

## Canonical ownership

`AuthoritativeLiveOperationalCampaignOwner.run_operational` constructs the scope
from:

- `selection_seed` (execution identity);
- `command.campaign_id`;
- `command.run_id`;
- `cycle_id`.

When `permanent_availability` is true, it passes the same root as both:

- `discovery_request_key_prefix`
- `front_door_request_key_prefix`

plus `campaign_source_request_scope`, into `build_graduated_supply`.

The root is never constructed from wall-clock time, random UUID, DB state, or
provider output.

`build_graduated_supply` stores the typed scope and root in supply diagnostics.

## Collision gate

Before the first permanent supply provider request,
`inspect_preexisting_source_request_scope_collision` runs:

```sql
SELECT id, request_key
FROM printer_source_requests
WHERE request_key = ? OR request_key LIKE ?
ORDER BY id
```

Expected count: zero. Any existing row blocks with
`CAMPAIGN_SOURCE_REQUEST_SCOPE_ALREADY_EXISTS` including exact count and at most
the first 20 sorted IDs. Colliding rows are never deleted, renamed, or reused.

## Permanent-mode blockers

Before source work:

| Code | Meaning |
| --- | --- |
| `CAMPAIGN_SOURCE_REQUEST_SCOPE_REQUIRED` | permanent mode without typed scope |
| `CAMPAIGN_SOURCE_REQUEST_SCOPE_INVALID` | version/root/token invalid |
| `CAMPAIGN_SOURCE_REQUEST_SCOPE_IDENTITY_MISMATCH` | campaign/run/cycle/execution disagree |
| `CAMPAIGN_SOURCE_REQUEST_SCOPE_PREFIX_MISMATCH` | discovery/front-door root ≠ typed root |
| `LEGACY_STATIC_REQUEST_SCOPE_BLOCKED_OPERATIONALLY` | `v2-9-7e-44` prefix/root in permanent mode |
| `CAMPAIGN_SOURCE_REQUEST_SCOPE_ALREADY_EXISTS` | pre-existing durable rows under root |

Explicit non-permanent fixture callers may still use historical defaults.

## Child-stage scope propagation

All permanent operational source stages continue to derive keys from the supplied
root with existing stage suffixes, sequence rules, budgets, and ordering:

- DexScreener locator
- direct Pump live-tail discovery
- PumpSwap verification
- GeckoTerminal nomination
- DexScreener market batches
- GeckoTerminal reconciliation
- liquidity backup
- protocol confirmation

No budget, reservation, ordering, provider, or Governor changes.

## Reconciliation categories

Invariant preserved: `D = S = M`.

Prefix lookup retained under the invocation-local root.

Returned scope evidence:

- `request_scope_version`
- `request_key_root`
- `prefix_lookup_request_ids`
- `known_stage_request_ids_proven_durable`
- `out_of_scope_stage_request_ids`

Exact categories:

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
MULTIPLE_SOURCE_REQUEST_RECONCILIATION_DEFECTS
```

A stage-reported durable request whose `request_key` is outside the current root
blocks with `CURRENT_STAGE_REQUEST_OUTSIDE_CAMPAIGN_SCOPE` and is not silently
discarded.

## Terminal-detail behavior

Outer compatibility code retained:

`CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH`

Bounded deterministic detail (via `terminal_detail` /
`format_source_request_reconciliation_detail`):

```text
DURABLE_REQUEST_NOT_STAGE_REPORTED:count=11:ids=1940,1941,...:truncated=0
```

Rules:

- exact count;
- first 20 sorted IDs maximum;
- truncation indicator;
- no payloads, URLs, headers, bodies, or secrets;
- complete structured set differences retained on the reconciliation object.

Pre-holder raise path now surfaces `terminal_detail` rather than a bare category
token alone.

## Focused test commands and results

```text
.venv/bin/python -m pytest tests/test_v2_9_8b_window_15m_source_request_scope_repair.py -q
→ 26 passed

.venv/bin/python -m pytest \
  tests/test_v2_9_8b_durable_id_and_stage_blocker_repair.py \
  tests/test_v2_9_8b_campaign_manifest_evidence_repair.py \
  tests/test_v2_9_8b_window_15m_source_specific_temporal_contract_repair.py \
  tests/test_v2_9_8b_permanent_discovery_availability.py -q
→ 112 passed

Combined earlier nearest suite including admission retained-evidence:
→ 151 passed
```

Python compilation of changed modules: `OK`  
`git diff --check`: `OK`  
Static permanent-mode legacy-block proof: `OK`  
Zero provider/runtime processes: `OK`

### Focused proofs covered

1. permanent composition constructs canonical root;
2. discovery and front-door use the same root;
3. missing typed scope blocks before provider I/O;
4. legacy static prefixes block in permanent mode;
5. identity mismatch blocks;
6. pre-existing root collision blocks before provider I/O;
7. campaign A/B disjoint roots and `D` sets;
8. historical `v2-9-7e-44%` rows do not enter a new `D` set;
9. PASS has each current request once in `D`, `S`, `M`;
10. durable current request omitted from stage reporting detected by prefix lookup;
11. durable omitted from coverage categorized;
12. stage-only non-durable categorized;
13. duplicate coverage / ownership-gap fail-closed;
14. ordinary provider failures reconcile when coverage complete;
15. terminal detail has category, count, bounded IDs;
16. invalid scope causes zero provider work;
17. source-specific temporal / mixed-candidate tests remain green;
18. no retrieval/financial capability unlock tokens.

### Unrelated pre-existing failures (not widened)

The following older campaign/holder fixture modules still fail for reasons
outside this repair (primarily missing source-specific temporal authority on
legacy SimpleNamespace fixture proofs / empty recon because holder path never
reaches full readiness). They were not part of the required proof set and were
not expanded into this lane:

- `tests/test_v2_9_8b_holder_manifest_composition_repair.py` (subset)
- `tests/test_v2_9_8b_holder_partial_accounting_repair.py` (subset)
- `tests/test_v2_9_8b_remaining_runtime_blocker_repair.py` (subset)

Example first cause observed:
`UNSUPPORTED_CANDIDATE_TEMPORAL_AUTHORITY: SimpleNamespace`.

## DB identity before / after

| Field | Before | After |
| --- | --- | --- |
| path | `data/printer_v1.sqlite3` | same |
| size | `69046272` | `69046272` |
| SHA-256 | `0b4b2b40c817bfd09a796686a898ef1c788d438b412ef6aa789ce6596c2c7b80` | same |
| inode | `1230526` | `1230526` |
| mtime_ns | `1786017804315875344` | `1786017804315875344` |
| integrity | `ok` | `ok` |
| foreign-key violations | `0` | `0` |
| WAL/SHM/journal | none | none |

Authoritative DB identity is unchanged. No restore or mutation was performed.

## Failed evidence preservation

Preserved and not reused, edited, moved, deleted, or regenerated:

- authorization `V2_9_8B_WINDOW_15M_AUTH_20260806T115911Z`
  (`operator-runs/.../final_authorization.json`);
- application evidence under
  `$HOME/PrinterOperations/v2-9-8/window-15m-one-shot-applications/V2_9_8B_WINDOW_15M_AUTH_20260806T115911Z`
  (marker, manifest, terminal, stdout, stderr);
- terminal campaign/run/cycle/supervision rows in the authoritative DB;
- source requests `1951–1968`, responses `1738–1748`, failures `213–219`;
- all prior failed-run and authorization evidence on the authoritative DB.

## Zero runtime / provider confirmation

- no wrapper or operational command run;
- no authorization created or consumed;
- no application marker created;
- no provider contact;
- no discovery/Scheduler/campaign/lifecycle/memory runtime started;
- no active Printer process observed during the lane.

## Money-usefulness contribution

Invocation-local source ownership ensures memory candidates are supported only by
source evidence gathered for their own campaign. Historical request contamination
can no longer distort current budget truth, block valid current evidence, or be
mistaken for current observations on a shared authoritative DB.

## What improves

- historical request contamination removed from permanent operational runs;
- omission detection retained via unique-root prefix lookup;
- scope reuse blocked before any provider cost or DB mutation;
- source-accounting safe-stops diagnosable from terminal detail;
- ordinary provider failures remain separable from ownership failures;
- repeated bounded campaigns on one authoritative DB become ownership-safe.

## What remains locked

- no new authorization or campaign run;
- no automatic retry/resume/restart/successor;
- `WINDOW_1H` / `WINDOW_4H` / `WINDOW_12H` / `WINDOW_24H`;
- retrieval / dirty-memory use;
- paper decisions / BUY/SELL/HOLD;
- positions, trades, audits, PnL;
- wallets, signing, real funds, paid APIs;
- scoring, ranking, confidence, weighting, embeddings, vectors.

## Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Control |
| --- | --- |
| New root collides with prior partial work | Pre-source collision gate |
| Removing prefix lookup hides omitted stages | Prefix lookup retained, root invocation-local |
| Child stages drift to different roots | One typed scope + exact root equality |
| Legacy tests depend on static defaults | Non-permanent fixture defaults retained |
| Terminal detail unbounded | Sorted IDs capped at 20 with exact count |
| Provider failures misclassified as ownership | Complete blocked-stage coverage still reconciles |
| Scope expands into providers/Scheduler | File and behavior boundaries frozen |
| Failed evidence rewritten | Authoritative DB and application evidence immutable |

## Exact next step

A later **explicit** lane must independently inspect this repair on the repair
branch tip before preparing **one** fresh authorization.

Do **not** create another authorization in this lane.

Stop after implementation, focused disposable proof, and closeout.
