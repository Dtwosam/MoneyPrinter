# Printer V1 V2-9.8B C12-C14 Authorization Marker and Lease-Evidence Conformance Repair

Date: 2026-08-01

Lane: `V2-9.8B C12-C14 Authorization Marker and Lease-Evidence Conformance Repair`

Repository: `MoneyPrinter`
Branch: `agent/v2-9-8b-c12-c14-authorization-marker-lease-evidence-repair`

## Commit boundary

- Required and confirmed starting HEAD: `925bf7b376145ccc283bf4edc7c8da230df26470`.
- Ending HEAD: the single lane commit containing this report; its exact pushed
  commit ID is recorded by `git rev-parse HEAD` in the final handoff. A Git
  commit cannot embed its own resulting object ID.
- The branch and starting HEAD were confirmed before any edit.

## First decision: existing owners are sufficient

Static inspection established that the contract is implementable without a new
table, migration, authorization owner, report owner, runner, Scheduler, or source
path:

| Evidence | Canonical existing owner | Static basis |
| --- | --- | --- |
| Authorization | Immutable `printer_memory_factory_campaign_configurations.configuration_json` created by `create_campaign()` | Configuration is created before accountable work and protected by the existing immutable configuration ownership contract. |
| Invocation | The unique immutable acquisition row in `printer_memory_factory_campaign_supervision` created by `acquire_campaign_supervision()` | The row binds supervision, campaign, configuration, run, owner, lease-lock path, and acquisition time; `(campaign_id, run_id)` is unique and resume is forbidden. |
| Lease release | The actual `cleanup_campaign_supervision()` return plus durable supervision read-back | Unified cleanup terminalizes owned work, releases the exact lock, then persists `lease_released_at`. |
| Canonical replay | Public exact-identity `report_only()` | It opens the disposable SQLite database with URI `mode=ro`, reconstructs durable rows and markers, and performs zero source calls, Scheduler runtime calls, or writes. |

Therefore `V2_9_8B_C12_C14_REPAIR_BLOCKED_DESIGN_AMENDMENT_REQUIRED` does not
apply.

## Files changed

- `src/printer_v1/operator_cli/campaign_persistence.py`
- `src/printer_v1/operator_cli/campaign_supervision.py`
- `src/printer_v1/operator_cli/campaign_full_run_accounting.py`
- `src/printer_v1/operator_cli/operational_memory_factory_command.py`
- `tests/test_v2_9_8b_c12_c14_authorization_marker_lease_evidence_conformance_repair.py`
- `tests/test_v2_9_8b_full_run_accounting_semantics_correction.py`
- `tests/test_v2_9_8b_full_run_accounting_terminal_evidence.py`
- `tests/test_v2_9_8b_full_run_wiring_integration.py`
- `docs/printer-v1-v2-9-8b-c12-c14-authorization-marker-and-lease-evidence-conformance-repair.md`
- `docs/printer-v1-v2-9-8b-post-repair-window-15m-full-run-accounting-and-terminal-evidence-implementation.md`

No schema or migration file changed.

## Canonical marker payloads and hashes

The immutable authorization payload is stored under
`configuration_json.authorization_marker` and contains exactly:

```text
marker_kind
marker_version
marker_id
execution_id
campaign_id
configuration_id
run_id
policy_version
db_target_identity
launch_git_provenance
operator_approved (literal true)
```

The same immutable configuration also stores the separate
`authorization_marker_sha256` canonical payload digest; loading, acceptance,
and replay require it to equal an independent recomputation.

The invocation payload is reconstructed from the exact supervision acquisition
row and contains exactly:

```text
marker_kind
marker_version
marker_id
supervision_id
campaign_id
configuration_id
run_id
owner_id
lease_lock_path
lease_lock_path_identity
acquisition_identity
acquired_at
authorization_marker_id
```

Both digests use UTF-8 bytes of canonical JSON constructed with sorted keys,
compact separators, and `ensure_ascii=True`, followed by SHA-256 (see the
2026-08-01 addendum: the original text incorrectly said `ensure_ascii=False`;
the canonical owner `canonical_campaign_evidence_json()` in
`campaign_persistence.py` uses `ensure_ascii=True`). The authorization digest
hashes the authorization payload; the invocation digest hashes the invocation
payload. `factory_config_hash` and the immutable campaign `configuration_hash`
remain separate fields. The gate explicitly rejects either marker digest when it
equals `factory_config_hash`.

Authorization count is reconstructed by scanning immutable configuration owners
for the exact marker ID and exact canonical payload. Invocation count is derived
only from the exact matching supervision acquisition row. It is not inferred
from a factory-run binding. The gate separately requires one matching
campaign-run/factory-run bind, one campaign supervision history row, and zero
additional history.

## Lease evidence flow

The ordinary coordinator passes the complete mapping returned by
`cleanup_campaign_supervision()` to the full-run finalizer. There is no
acceptance-boundary lease default. The finalizer cross-checks that mapping with
the exact durable supervision row and exact campaign/configuration/run/
supervision/owner identity. PASS requires literal boolean `cleanup_completed is
True` and `lease_released is True`, durable `TERMINAL` supervision, non-null
`cleanup_completed_at` and `lease_released_at`, absence of the exact lease-lock
path, and zero active or locked owned work.

Missing cleanup evidence, omission, `None`, false, a non-boolean value, identity
drift, a remaining lock, or durable/read-back drift blocks. Tests and helpers use
the real acquired supervision and actual cleanup return; they do not manufacture
positive lease truth.

Public exact replay reopens the disposable database read-only, reconstructs both
markers from immutable configuration and supervision acquisition, recomputes
both digests, preserves the factory configuration hash, verifies exact counts,
binding/history correspondence, durable cleanup/release timestamps and lock
absence, and reruns the acceptance gate. Historical V1 or report-carried marker
hashes cannot substitute for persisted evidence.

## C12-C14 completion law

| ID | Required repaired law | Positive evidence | Fail-closed evidence | Status |
| --- | --- | --- | --- | --- |
| C12 | One canonical report carries distinct configuration, authorization, invocation, cleanup, release, and lock evidence | Real disposable coordinator path reaches `CAMPAIGN_PASS` only with actual cleanup and all distinct fields | Missing marker/cleanup, substituted hash, malformed digest, wrong identity, bad count/history/bind, release timestamp or lock evidence blocks | PASS |
| C13 | Authorization is a pre-work immutable payload; invocation is the exact supervision acquisition; lease truth is actual and durable | Exactly one canonical authorization marker, one matching supervision invocation, one matching factory bind, literal cleanup/release truth, durable timestamp, absent lock, zero residue | Authorization/invocation counts 0 or 2, wrong campaign/run/configuration/supervision/owner, duplicate history, factory-bind mismatch, omitted/`None`/false/non-boolean lease truth block | PASS |
| C14 | Public exact replay independently reconstructs persisted marker and lease truth read-only | Exact marker replay returns `REPLAYED`, zero source/Scheduler/write counters, and unchanged disposable DB mtime | Historical/report-only substitutes, missing markers, digest drift, durable mismatch, or failed acceptance gate block | PASS |

## Verification commands and exact results

All test databases were disposable temporary SQLite databases. Transports were
injected or frozen. No provider, RPC, WebSocket, network discovery, operational
campaign, authoritative memory operation, or public runtime campaign ran.

```text
.venv/bin/python -m py_compile src/printer_v1/operator_cli/campaign_full_run_accounting.py src/printer_v1/operator_cli/campaign_persistence.py src/printer_v1/operator_cli/campaign_supervision.py src/printer_v1/operator_cli/operational_memory_factory_command.py tests/test_v2_9_8b_c12_c14_authorization_marker_lease_evidence_conformance_repair.py tests/test_v2_9_8b_full_run_accounting_semantics_correction.py tests/test_v2_9_8b_full_run_accounting_terminal_evidence.py tests/test_v2_9_8b_full_run_wiring_integration.py
Result: exit 0, no output.

.venv/bin/python -m pytest -q tests/test_v2_9_8b_c12_c14_authorization_marker_lease_evidence_conformance_repair.py
Result: 15 passed, 16 subtests passed in 6.83s.

.venv/bin/python -m pytest -q tests/test_v2_9_8b_full_run_accounting_semantics_correction.py tests/test_v2_9_8b_full_run_accounting_terminal_evidence.py tests/test_v2_9_8b_full_run_wiring_integration.py
Result: 47 passed, 6 subtests passed in 10.73s.

.venv/bin/python -m pytest -q tests/test_v2_9_8b_c12_c14_authorization_marker_lease_evidence_conformance_repair.py tests/test_v2_9_8b_full_run_accounting_semantics_correction.py tests/test_v2_9_8b_full_run_accounting_terminal_evidence.py tests/test_v2_9_8b_full_run_wiring_integration.py
Result after final source cleanup: 62 passed, 22 subtests passed in 18.07s.

.venv/bin/python -m pytest -q tests/test_v2_9_7e_46b_2_source_accounting.py tests/test_v2_9_7d_6b_5_operational_lease_safe_stop.py tests/test_v2_9_7d_7a_abstract_command_surface.py
Result: 24 passed, 11 subtests passed in 5.43s.

.venv/bin/python -m pytest -q --disable-warnings tests/test_v2_9_7d_6b_1_campaign_ownership_schema.py tests/test_v2_9_8b_campaign_accounting_terminal_enforcement.py tests/test_v2_9_8b_terminal_safety_accounting_finalization.py tests/test_v2_9_8b_accounting_exact_identity_report_only_repair.py tests/test_v2_4_one_command_15m_factory.py tests/test_v2_9_8b_operational_factory_active_path_restoration.py tests/test_v2_9_8b_post_handoff_terminal_compensation.py tests/test_v2_9_8b_restored_factory_source_compatibility_reset.py
Result: 130 passed in 35.73s.
```

Migration-050 ownership/projection tests were not rerun because no migration,
schema projection, or migration-owned behavior changed. The full repository
suite was not run because focused verification exposed no shared architectural
regression.

## Money-usefulness contribution

This repair prevents incomplete or substituted authorization and lease evidence
from falsely certifying a memory-production run. That improves the trustworthiness
of evidence that may later inform paper-only analysis. It adds no retrieval,
decision, trade, money movement, or profitability capability.

## What improved

- Removed the default-true lease acceptance path.
- Bound authorization to an immutable pre-work configuration payload.
- Bound invocation to the exact supervision acquisition rather than a non-null
  factory-run binding.
- Separated factory configuration, authorization, and invocation hashes.
- Added exact identity/count/history/binding and durable lease read-back checks.
- Made public report-only replay reconstruct both markers and lease release from
  persisted owners read-only.

## What remains locked

`data/printer_v1.sqlite3`; migration 050 application to that database; bounded or
live proof; provider/RPC/WebSocket/source execution; discovery or an operational
campaign; authoritative memory generation or promotion; longer windows;
retrieval; paper decisions; BUY/SELL/HOLD; positions, trades, audits, PnL;
wallets, signing, private keys, funds, paid APIs; scoring, ranking, confidence,
weighting, embeddings, and vectors.

## Proof still required

This lane is implementation plus disposable verification only. A repeat
independent read-only C1-C15 conformance review is still required. This PASS does
not authorize bounded proof or a campaign.

## Functionality Risks / Setbacks / Efficiency Blockers

| Item | Impact | Disposition |
| --- | --- | --- |
| Final commit self-reference | The report cannot contain the object ID of the commit that contains it. | Exact ending HEAD is recorded after commit and push in the final handoff. |
| Existing schema makes exact duplicate supervision acquisition impossible for one campaign/run | The count-two negative is exercised at the acceptance gate rather than by violating the immutable unique owner. | Durable history count and additional-history checks independently reject any extra supervision history. |
| Historical reports lack the new persisted markers | They cannot be upgraded by carrying a hash in report JSON. | Replay fails closed; no compatibility alias was added. |
| Full repository suite not run | Unrelated repository behavior was not surveyed. | The requested focused and nearest affected matrices passed, so scope was not expanded. |

## Verdict

`V2_9_8B_C12_C14_AUTHORIZATION_MARKER_AND_LEASE_EVIDENCE_CONFORMANCE_REPAIR_PASS`

## Addendum (2026-08-01): factual corrections from the repeat review

This addendum is added by the follow-on lane
`V2-9.8B C12-C14 Durable Cleanup Timestamp and Replay Reconstruction Repair`
(starting HEAD `780fabfc815026243bc5ad9ab3e0f13e86ae05d8`). It does not rewrite or
erase this report or either independent review; it records factual corrections
and the residual gaps that the repeat independent read-only C1-C15 review found
after this PASS.

1. Canonicalization statement corrected. The "Canonical marker payloads and
   hashes" section originally stated both marker digests use `ensure_ascii=False`.
   That was inaccurate. The single canonical owner
   `canonical_campaign_evidence_json()` / `campaign_evidence_sha256()` in
   `campaign_persistence.py` serializes with `ensure_ascii=True`. Creation and
   acceptance always used that owner; only the public replay path independently
   recomputed marker digests with a local `ensure_ascii=False` serializer, so a
   valid non-ASCII lease-lock path could hash to different bytes and falsely
   block replay. The follow-on lane removed that replay-local marker
   serialization and routed replay's marker digests through
   `campaign_evidence_sha256()`.

2. Durable `cleanup_completed_at` was not gated at initial acceptance. This
   report's PASS relied on caller-carried `cleanup_completed is True` plus durable
   terminal supervision, `lease_released_at`, and lock absence, but did not
   require a non-empty, parseable, timezone-aware durable `cleanup_completed_at`
   with `lease_released_at` never preceding it. The follow-on lane added that
   gate (and the identical requirement in public replay).

3. Replay did not independently reconstruct `factory_config_hash`. Public replay
   copied the report-carried `factory_config_hash` into the durable
   reconstruction before comparison instead of reading
   `printer_memory_factory_runs.config_hash` for the exact `factory_run_id`. The
   follow-on lane replaced that copy with an independent durable query.

See `docs/printer-v1-v2-9-8b-c12-c14-durable-cleanup-timestamp-and-replay-reconstruction-repair.md`
for the follow-on repair, its completion-law table, and its exact test results.

This PASS authorizes only a repeat independent read-only conformance review.
