# Printer V1 V2-9.8B WINDOW_15M Exact Pre-Holder Transport-Identity Repair Design

## Verdict

`V2_9_8B_WINDOW_15M_PRE_HOLDER_TRANSPORT_IDENTITY_REPAIR_DESIGN_COMPLETE`

This is design-only. No production code, tests, database rows, authorization
packages, application evidence, provider calls, discovery, Scheduler work,
lifecycle work, or memory work were changed or executed.

## Baseline

| Item | Value |
| --- | --- |
| Audit branch | `agent/v2-9-8b-window-15m-pre-holder-transport-identity-mismatch-audit` |
| Audit commit | `ad2c62c34f93ae205e8bab02c4953a3bf924efb4` |
| Design branch | `agent/v2-9-8b-window-15m-pre-holder-transport-identity-repair-design` |
| Controlling audit | `docs/printer-v1-v2-9-8b-window-15m-pre-holder-transport-identity-mismatch-audit.md` |
| Failed execution | `20260806T131312Z-829382105482` |
| Consumed authorization | `V2_9_8B_WINDOW_15M_AUTH_20260806T131011Z` |

## Design objective

Make pre-holder source accounting fully identity-bearing and require exact parity
across three independently produced transport identity sets:

```text
M = C = A
```

Where:

- `M` = exact transport identities carried by the source-request manifest;
- `C` = exact transport identities aggregated by the campaign six-unit owner;
- `A` = exact transport identities observed at action-local measurement time.

The repair must not lower a count to match an incomplete identity set and must not
fabricate identities from requests, responses, members, provider calls, or stage
counts.

## Root cause being repaired

Request ownership currently reconciles at the request-ID layer (`D = S = M`),
but request coverage may carry `transport_identity_count` without a complete
`transport_identity_keys` list. `build_pre_holder_budget_snapshot` then compares
the summed manifest count with the campaign identity count rather than comparing
an exact manifest identity set with campaign and action-local identity sets.

The failed attempt reached:

```text
manifest_transport_count = 9
campaign_identity_count = 5
```

The terminal did not preserve enough identity-level evidence to name the four
missing or extra identities. The design therefore repairs evidence completeness
and diagnostics, not the numerical result by assumption.

## Canonical ownership

### Canonical transport identity key

`printer_v1.sources.measured_transport` remains the canonical owner of transport
identity shape.

Add or expose one public helper equivalent to:

```python
canonical_transport_identity_key(identity) -> tuple[object, ...]
```

The key must be derived from the exact existing identity fields:

- stage;
- source name;
- governed request kind;
- method or endpoint;
- within-request ordinal;
- target category;
- target identity.

Existing private or duplicated key builders in holder, source-manifest, and
activation code must delegate to this canonical helper. Do not introduce a
second identity shape.

### Per-request coverage owner

Each governed source stage owns the exact measured-ledger delta produced by one
source request. It must attach both:

- `transport_identity_count` derived from that delta;
- `transport_identity_keys` derived from the same delta.

No caller may independently set the count and key list.

### Manifest owner

`printer_v1.discovery.permanent_discovery_availability` remains the owner of the
campaign source-request manifest and source-request reconciliation.

It must validate identity completeness for every coverage entry before the
manifest can be `OK`.

### Pre-holder parity owner

`build_pre_holder_budget_snapshot` remains the holder-budget boundary, but its
input contract becomes exact-identity-bearing. It owns the final `M = C = A`
parity check before any holder transport can begin.

## Exact per-request coverage contract

Every normalized coverage entry must contain:

```text
source_request_id
source_name
request_kind
logical_stage_id
terminal_status
transport_identity_count
transport_identity_keys
normalized_member_count
```

Rules:

1. `transport_identity_keys` must be a list or tuple, never missing or null.
2. Every key must normalize through the canonical measured-transport key helper.
3. `transport_identity_count == len(transport_identity_keys)`.
4. A positive count with no keys blocks.
5. A zero count requires an empty key list.
6. Duplicate keys within one request block.
7. One canonical transport key may belong to exactly one request and logical
   stage in the manifest; cross-request or cross-stage duplicates block.
8. A provider failure may lawfully have zero transports only when the measured
   delta is genuinely empty and the coverage terminal remains `BLOCKED` or
   `FAILED` as appropriate.
9. Counts never derive from normalized-member count, request count, response
   count, batch size, provider-call assumptions, or hard-coded constants.

## Source producer repairs

Audit and update every production source-request coverage producer so count and
keys come from the same measured-ledger delta:

- DexScreener fresh-profile locator;
- direct Pump migration page requests;
- direct Pump transaction requests;
- PumpSwap graduation verification requests;
- GeckoTerminal fresh nomination;
- DexScreener mint-market batches;
- GeckoTerminal reconciliation fallback;
- PumpSwap protocol-confirmation batches;
- liquidity backup requests;
- any final-refresh source coverage;
- any other production source surface collected by
  `collect_stage_source_request_coverage`.

The known concrete gap is the GeckoTerminal reconciliation fallback, which
currently records `gt_transport_count` without attaching exact keys. It must
capture the pre-request ledger length and derive its key delta exactly as the
primary market batch does.

No provider, source order, request budget, stage reservation, candidate order,
or retry behavior changes.

## Manifest validation and evidence

`_normalize_stage_coverage_entry` must fail closed rather than silently accepting
or dropping identity-incomplete coverage.

Use stable categories equivalent to:

```text
SOURCE_REQUEST_TRANSPORT_IDENTITIES_MISSING
SOURCE_REQUEST_TRANSPORT_IDENTITY_COUNT_MISMATCH
SOURCE_REQUEST_TRANSPORT_IDENTITY_MALFORMED
SOURCE_REQUEST_DUPLICATE_TRANSPORT_IDENTITY
CAMPAIGN_DUPLICATE_TRANSPORT_IDENTITY_OWNERSHIP
```

The manifest must return or retain:

```text
transport_identity_count_total
transport_identity_keys
transport_identity_owners
transport_identity_completeness_status
transport_identity_blockers
```

`transport_identity_owners` binds each canonical key to:

- source request ID;
- logical stage ID;
- source name;
- request kind.

The existing request-ID invariant remains unchanged:

```text
D = S = M_requests
```

Transport identity completeness is an additional required invariant. It must not
replace or weaken request-ID reconciliation.

## Exact pre-holder parity

`build_pre_holder_budget_snapshot` must construct:

```text
M = canonical manifest identity keys
C = canonical campaign-owner identity keys
A = canonical action-local identity keys
```

Require:

```text
len(M) = manifest declared transport total
len(C) = campaign measured transport count
len(A) = action-local measured transport count
set(M) = set(C) = set(A)
```

Also require no duplicates in any input sequence before set conversion.

Return the exact sorted canonical key set on PASS as the snapshot’s measured
transport identity keys.

Do not:

- replace manifest count `9` with campaign count `5`;
- infer missing keys from request IDs or response rows;
- mirror campaign evidence into action-local evidence;
- treat equal counts as proof of equal identities;
- discard extra keys silently.

## Failure categories

Use stable pre-holder categories:

```text
PRE_HOLDER_MANIFEST_TRANSPORT_IDENTITIES_MISSING
PRE_HOLDER_MANIFEST_TRANSPORT_IDENTITY_COUNT_MISMATCH
PRE_HOLDER_MANIFEST_TRANSPORT_IDENTITY_MALFORMED
PRE_HOLDER_DUPLICATE_MANIFEST_TRANSPORT_IDENTITY
PRE_HOLDER_MANIFEST_CAMPAIGN_IDENTITY_MISMATCH
PRE_HOLDER_CAMPAIGN_ACTION_IDENTITY_MISMATCH
PRE_HOLDER_MANIFEST_ACTION_IDENTITY_MISMATCH
MULTIPLE_PRE_HOLDER_TRANSPORT_IDENTITY_DEFECTS
```

Preserve `HolderBudgetError` as the fail-closed exception owner.

The previous generic code may remain readable for historical evidence, but new
failures must identify the exact relation that failed.

## Bounded diagnostic contract

For every failed relation, retain structured evidence and emit deterministic,
bounded terminal detail containing:

- manifest, campaign, and action-local counts;
- exact mismatch category or ordered categories;
- first 20 sorted canonical keys per set difference;
- truncation indicator;
- for manifest-owned keys, request ID and logical stage;
- duplicate ownership pairs when applicable.

Required structured differences:

```text
M_minus_C
C_minus_M
M_minus_A
A_minus_M
C_minus_A
A_minus_C
```

Do not emit provider payloads, URLs, request headers, response bodies, secrets,
or unbounded identity lists.

The terminal summary and failure reporting must preserve this detail rather than
reducing it to counts only.

## Source-request manifest integration

The source-request reconciliation object must expose identity completeness before
`build_pre_holder_budget_snapshot` is called.

When identity completeness fails:

- source-request request-ID evidence remains preserved;
- the campaign blocks before holder I/O;
- the exact manifest blocker is surfaced;
- no count or key is normalized away;
- no stage is re-run.

When request-ID and transport-identity contracts both pass, the pre-holder parity
owner independently compares manifest, campaign, and action-local keys.

## Compatibility and historical evidence

- Historical manifest evidence remains readable; do not rewrite it.
- New permanent operational runs require the identity-bearing contract.
- Explicit legacy fixture callers may use a narrowly marked compatibility path
  only when they do not claim permanent operational readiness.
- The consumed authorization and failed application evidence remain immutable.
- No DB migration is expected or approved for this repair.

## Minimum focused proof

Use disposable migrated databases, fixture transports, and deterministic
identities only.

Prove at minimum:

1. reproduce a synthetic `manifest_count=9`, `campaign_count=5` mismatch without
   provider I/O;
2. positive manifest count with missing keys blocks;
3. count/key-length mismatch blocks;
4. malformed canonical key blocks;
5. duplicate key within one request blocks;
6. duplicate key across requests or stages blocks with both owners;
7. lawful blocked zero-transport request with `count=0`, `keys=[]` remains valid;
8. GeckoTerminal fallback coverage carries exact measured keys;
9. every other production coverage producer has count/key parity;
10. exact `M = C = A` passes and preserves the exact key set;
11. equal counts with unequal keys block;
12. each of the six set differences is retained correctly;
13. bounded terminal detail includes category, counts, keys, request IDs, stages,
    and truncation without payloads or secrets;
14. request-ID `D = S = M_requests` behavior remains unchanged;
15. ordinary provider failures remain distinguishable from identity defects;
16. source-request scope and temporal tests remain green;
17. no holder, Scheduler, lifecycle, memory, retrieval, or financial work runs;
18. authoritative DB and failed evidence remain byte-identical.

Run only the new focused tests and the nearest:

- source-request manifest/reconciliation tests;
- campaign six-unit accounting tests;
- pre-holder budget snapshot tests;
- permanent discovery composition tests;
- source-scope tests;
- source-specific temporal tests.

Do not run the full repository suite unless the change becomes unexpectedly
cross-cutting.

## Money-usefulness contribution

Exact transport identity parity ensures campaign source cost, provenance, and
budget truth are tied to real measured operations before holder eligibility and
memory formation. It prevents count-only evidence from silently overstating or
understating work and makes future safe-stops diagnosable without another paid or
bounded live attempt.

## What this lane improves

- exact identity-bearing source manifests;
- one canonical transport identity shape;
- no positive count without keys;
- exact `M = C = A` pre-holder parity;
- request/stage-local mismatch evidence;
- safer repeated campaigns on one authoritative DB.

## What this lane does not unlock

- no authorization or campaign run;
- no holder collection;
- no Scheduler or lifecycle work;
- no `WINDOW_15M` proof by itself;
- no 1h/4h/12h/24h activation;
- no retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL;
- no wallets, keys, signing, real funds, paid APIs, scoring, ranking,
  confidence, weighting, embeddings, or vectors.

## Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Control |
| --- | --- |
| Producer count/key drift | Derive both from one ledger delta helper |
| Different modules normalize keys differently | One canonical helper in measured-transport owner |
| Historical fixtures lack keys | Narrow non-operational compatibility only |
| Equal counts hide identity mismatch | Exact set comparison required |
| Duplicate identity charged twice | Cross-request/stage ownership uniqueness |
| Terminal becomes too large | First 20 sorted keys per difference plus truncation |
| Fix fabricates missing evidence | Forbidden; block rather than infer |
| Scope expands into holder or provider policy | Accounting/coverage/pre-holder files only |

## Exact next lane

Implement this design with focused disposable proof and a closeout report.

Do not create a new authorization or run Printer in the implementation lane.
