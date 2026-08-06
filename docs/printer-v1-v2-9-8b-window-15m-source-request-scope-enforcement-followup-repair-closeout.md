# Printer V1 V2-9.8B WINDOW_15M Source-Request Scope Enforcement Follow-up Repair Closeout

## Verdict

`V2_9_8B_WINDOW_15M_SOURCE_REQUEST_SCOPE_ENFORCEMENT_FOLLOWUP_REPAIR_PASS`

Focused implementation, disposable proof, and closeout only. No authorization
was created. No Printer process was run. No provider or runtime execution
occurred.

## Baseline and repair branch

| Item | Value |
| --- | --- |
| Design branch / required HEAD | `agent/v2-9-8b-window-15m-source-request-scope-enforcement-followup-design` / `4d8be11774ea95b9d11c52ea807210fcead0f6d1` |
| Repair branch | `agent/v2-9-8b-window-15m-source-request-scope-enforcement-followup-repair` |
| Controlling design | `docs/printer-v1-v2-9-8b-window-15m-source-request-scope-enforcement-followup-design.md` |
| Controlling audit | `docs/printer-v1-v2-9-8b-window-15m-source-request-scope-enforcement-followup-audit.md` |
| Prior scope repair | `d9b2deb5ea35ae9035702f90343d3818bf6ac536` |
| Consumed authorization (preserved) | `V2_9_8B_WINDOW_15M_AUTH_20260806T115911Z` |

Baseline gates:

- exact design branch and HEAD;
- clean tracked tree/index (untracked authorization evidence only);
- no active Printer process, campaign, Scheduler, factory, lease, or lock;
- failed-run and authorization evidence preserved;
- no provider or runtime execution.

## Exact files changed

Production:

- `src/printer_v1/discovery/permanent_discovery_availability.py`

Tests:

- `tests/test_v2_9_8b_window_15m_source_request_scope_enforcement_followup.py` (new)

Closeout:

- `docs/printer-v1-v2-9-8b-window-15m-source-request-scope-enforcement-followup-repair-closeout.md`

No other production modules required change. Public composition, collision gate,
providers, budgets, Scheduler, selection, temporal/holder policy, schema, and
authorization framework are unchanged.

## Both defects

### Defect A — silent invalid-scope downgrade

`assemble_and_reconcile_campaign_source_requests` caught invalid scope coercion
and continued with `scope_obj = None`, allowing scoped inputs to fall through to
weaker multi-prefix / unscoped durable construction.

### Defect B — foreign-prefix merge into `D`

Under enforcement, caller prefixes were merged with the root, and prefix-lookup
rows were added to `D` without a final `request_key_belongs_to_root` filter. A
foreign prefix could therefore enlarge `D`.

## Exact enforcement behavior

### Scoped activation

Scoped enforcement is active when any of the following is present:

- `campaign_source_request_scope` argument or diagnostic;
- `request_key_root` argument;
- diagnostic `request_key_root`.

### Fail-closed validation (before set reconciliation)

Raises stable typed `ValueError` (not swallowed):

| Condition | Blocker |
| --- | --- |
| Scoped but no typed scope | `CAMPAIGN_SOURCE_REQUEST_SCOPE_REQUIRED` |
| Invalid version / root / identities | `CAMPAIGN_SOURCE_REQUEST_SCOPE_INVALID` |
| Explicit root ≠ scope root | `CAMPAIGN_SOURCE_REQUEST_SCOPE_PREFIX_MISMATCH` |
| Diagnostic root ≠ scope root | `CAMPAIGN_SOURCE_REQUEST_SCOPE_PREFIX_MISMATCH` |
| Any supplied prefix ≠ scope root | `CAMPAIGN_SOURCE_REQUEST_SCOPE_PREFIX_MISMATCH` |

Valid scope is obtained only via `validate_campaign_source_request_scope`
(supported version, canonical root derivation, non-empty identities, token
shape).

### Canonical prefix set

Under scoped enforcement:

```python
prefixes = [scope.request_key_root]
```

Foreign prefixes are contract errors, not discovery sources.

### Row-level final filter

When `enforce_request_key_root=True`, `load_durable_campaign_source_request_ids`
applies `request_key_belongs_to_root` to rows from **both**:

- known-request-ID lookup;
- prefix lookup.

`load_prefix_lookup_request_ids` applies the same filter when enforced, so
`prefix_lookup_request_ids` contains only current-root rows.

### Out-of-scope classification preserved

A stage-reported durable row under another root:

- stays outside `D`;
- appears in `out_of_scope_stage_request_ids`;
- retains category `CURRENT_STAGE_REQUEST_OUTSIDE_CAMPAIGN_SCOPE`;
- is not relabelled non-durable;
- retains bounded terminal detail.

### Unscoped legacy path

When neither typed scope nor root is supplied, multi-prefix behavior is unchanged.

### Public outer recon blocker

Set-reconciliation failures still use
`CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH`. Scope-contract failures raise
the stable scope `ValueError` before set reconciliation.

## Focused test results

```text
.venv/bin/python -m pytest \
  tests/test_v2_9_8b_window_15m_source_request_scope_enforcement_followup.py \
  tests/test_v2_9_8b_window_15m_source_request_scope_repair.py -q
→ 36 passed

.venv/bin/python -m pytest \
  tests/test_v2_9_8b_durable_id_and_stage_blocker_repair.py \
  tests/test_v2_9_8b_campaign_manifest_evidence_repair.py \
  tests/test_v2_9_8b_window_15m_source_specific_temporal_contract_repair.py \
  tests/test_v2_9_8b_window_15m_source_specific_admission_retained_evidence_repair.py \
  tests/test_v2_9_8b_permanent_discovery_availability.py -q
→ 125 passed

Python compilation of changed module: OK
git diff --check: OK
```

Proof coverage:

1. `[canonical_root, foreign_root]` with enforce cannot add foreign row to `D`;
2. foreign supplied prefix blocks scoped reconciliation;
3. invalid scope version blocks;
4. malformed canonical root blocks;
5. explicit root ≠ scope blocks;
6. diagnostic root ≠ scope blocks;
7. current-root known + prefix IDs reconcile with `D = S = M`;
8. foreign durable stage IDs remain out-of-scope (not non-durable);
9. unscoped multi-prefix behavior unchanged;
10–11. public permanent-composition and temporal/mixed-candidate tests green;
12. no provider/runtime work; authoritative DB identity unchanged.

No unrelated pre-existing failures were widened in this lane.

## DB identity before / after

| Field | Before | After |
| --- | --- | --- |
| size | `69046272` | `69046272` |
| SHA-256 | `0b4b2b40c817bfd09a796686a898ef1c788d438b412ef6aa789ce6596c2c7b80` | same |
| inode | `1230526` | `1230526` |
| mtime_ns | `1786017804315875344` | `1786017804315875344` |
| integrity | `ok` | `ok` |
| foreign-key violations | `0` | `0` |
| WAL/SHM/journal | none | none |

## Evidence preservation

Preserved and not reused, edited, moved, deleted, or regenerated:

- authorization `V2_9_8B_WINDOW_15M_AUTH_20260806T115911Z`;
- application marker, manifest, terminal, stdout, stderr under
  `$HOME/PrinterOperations/v2-9-8/window-15m-one-shot-applications/V2_9_8B_WINDOW_15M_AUTH_20260806T115911Z`;
- source requests `1951–1968`, responses `1738–1748`, failures `213–219`;
- all prior failed-run and authorization rows on the authoritative DB.

## Zero runtime / provider confirmation

- no wrapper or operational command;
- no authorization created or consumed;
- no application marker created;
- no provider contact;
- no discovery/Scheduler/campaign/lifecycle/memory runtime;
- no active Printer process during the lane.

## Money-usefulness contribution

The final durable-ownership boundary is self-enforcing: even if a caller
accidentally supplies extra prefixes or malformed scope evidence, a campaign can
only attribute durable source requests under its own invocation root. That keeps
current budget truth free of foreign-run contamination on a shared authoritative
DB.

## What improves

- invalid typed scope can no longer silently degrade to unscoped reconciliation;
- foreign prefixes cannot enlarge `D` under scoped enforcement;
- prefix-lookup evidence is root-clean under enforcement;
- out-of-scope stage classification remains explicit and diagnosable.

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
| Legacy fixture breakage | Unscoped path retained when no scope/root supplied |
| Foreign durable mislabelled non-durable | Out-of-scope classification preserved |
| Scope expands beyond accounting | Single production module + focused tests |
| Premature live proof | No authorization in this lane |

## Exact next step

A later **explicit** independent inspection lane must review this follow-up repair
on the repair branch tip before any fresh authorization preparation.

Do **not** create another authorization in this lane.

Stop after implementation, focused disposable proof, and closeout.
