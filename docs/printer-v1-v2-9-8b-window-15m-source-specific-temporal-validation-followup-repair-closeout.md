# Printer V1 V2-9.8B WINDOW_15M Source-Specific Temporal Validation Follow-up Repair Closeout

## Verdict

`V2_9_8B_WINDOW_15M_SOURCE_SPECIFIC_TEMPORAL_VALIDATION_FOLLOWUP_REPAIR_PASS`

This is a focused implementation, disposable proof, and documentation
correction only.

- No authorization was created, renewed, edited, moved, or reused.
- No Printer campaign, provider, discovery, Source Governor, Central Scheduler,
  lifecycle, or memory runtime was invoked.
- The approved temporal architecture is preserved.
- The authoritative database identity is unchanged before and after this repair.

## Baseline and branch

| Item | Value |
| --- | --- |
| Required baseline branch | `agent/v2-9-8b-window-15m-source-specific-temporal-contract-repair` |
| Required full starting HEAD | `1f1869dec15fe3d87456bec3748aa87dd9ce47c6` |
| Atomic temporal implementation commit | `65eae92177c443b19fbffa126480a61e5fbcfc09` |
| Follow-up branch | `agent/v2-9-8b-window-15m-source-specific-temporal-validation-followup-repair` |
| Commit subject | `Harden source-specific temporal validation` |

The live final branch tip is reported externally after push. This closeout does
not embed a self-referential `Final full HEAD` for the commit being created.

## Exact validation defect

`_require_positive_graduation_epoch` accepted non-integer values by coercing
with `int(raw)` after only rejecting booleans explicitly. That allowed:

- floats such as `1.0` and `1.5` (truncation / silent cast);
- digit strings such as `"1700000000"`;
- other `int()`-coercible types.

Oversized integers that cannot be converted by
`datetime.fromtimestamp(..., tz=timezone.utc)` were also not proven convertible
before return, so raw conversion exceptions could escape later.

## Exact repair

### A. Production validation

In `src/printer_v1/operator_cli/graduated_supply_front_door.py`,
`_require_positive_graduation_epoch` now:

1. treats missing / blank string as
   `DIRECT_CANDIDATE_GRADUATION_TIME_MISSING:<mint>`;
2. requires `type(raw) is int` and `raw > 0` — no `int(raw)` coercion;
3. proves convertibility with `datetime.fromtimestamp(raw, tz=timezone.utc)`;
4. maps `OverflowError`, `OSError`, and `ValueError` to
   `DIRECT_CANDIDATE_GRADUATION_TIME_INVALID:<mint>`;
5. returns the exact integer epoch unchanged.

Booleans, floats (including `1.0`), strings, Decimal, null, zero, negative,
inf/nan, and non-convertible oversized integers fail closed. No raw Python
conversion exception escapes source-specific admission.

The legacy `FixtureOriginProof` holder resolver continues to use the same
validator and still converts valid integer block times to UTC ISO, raising
stable `LiveOperationalError` codes for invalid values.

### B. Closeout identity correction

`docs/printer-v1-v2-9-8b-window-15m-source-specific-temporal-contract-repair-closeout.md`
no longer uses a self-referential `Final full HEAD` field. It now records:

```text
Atomic implementation commit:
65eae92177c443b19fbffa126480a61e5fbcfc09

Focused follow-up baseline:
1f1869dec15fe3d87456bec3748aa87dd9ce47c6
```

and states that the live final branch tip must be resolved externally after the
final commit.

### Unchanged (preserved)

- temporal authority enum / model;
- market-observation timestamp sourcing;
- admission authorities;
- holder maturation policy (`MATURATION_THRESHOLD_SECONDS = None`);
- snapshot maturity;
- source freshness;
- providers, Source Governor, Central Scheduler, selection;
- database schema;
- authorization / marker code;
- no universal `block_time` property;
- no timestamp fallback.

## Files changed

- `src/printer_v1/operator_cli/graduated_supply_front_door.py`
- `tests/test_v2_9_8b_window_15m_source_specific_temporal_contract_repair.py`
- `docs/printer-v1-v2-9-8b-window-15m-source-specific-temporal-contract-repair-closeout.md`
- `docs/printer-v1-v2-9-8b-window-15m-source-specific-temporal-validation-followup-repair-closeout.md`

## Tests and results

Commands:

```bash
.venv/bin/pytest \
  tests/test_v2_9_8b_window_15m_source_specific_temporal_contract_repair.py \
  tests/test_v2_9_8b_window_15m_source_specific_admission_retained_evidence_repair.py \
  -q

python3 -m py_compile \
  src/printer_v1/operator_cli/graduated_supply_front_door.py

git diff --check
```

Focused proof covers:

1. `1.5` fails;
2. `1.0` fails;
3. `"1700000000"` fails;
4. ±infinity fail;
5. NaN fails;
6. oversized integer `10**100` → typed invalid-time blocker;
7. valid positive integer remains exact;
8. no truncation/rounding (adjacent float rejected);
9. invalid direct time blocks before holder transport;
10. legacy direct holder resolver returns stable typed blocker for oversized /
    non-integer time;
11. market temporal behavior unchanged;
12. mixed market/direct behavior unchanged.

Exact results for this lane:

```text
tests/test_v2_9_8b_window_15m_source_specific_temporal_contract_repair.py
tests/test_v2_9_8b_window_15m_source_specific_admission_retained_evidence_repair.py
63 passed

python3 -m py_compile graduated_supply_front_door.py → OK
git diff --check → clean
DB identity unchanged
```

## DB identity before and after

| Field | Before | After |
| --- | --- | --- |
| path | `data/printer_v1.sqlite3` | same |
| size | `68718592` | `68718592` |
| SHA-256 | `d4f9e145fffb4010294c5ecfe6027770a11f9d090dd6701a0abb4dce7d83c0d7` | same |
| inode | `1230526` | `1230526` |
| mtime_ns | `1786013653208178741` | `1786013653208178741` |

No restore or mutation.

## Evidence preservation

Preserved unchanged:

- consumed authorization `V2_9_8B_WINDOW_15M_AUTH_20260806T103951Z`;
- failed execution `20260806T105403Z-cde8a9b58daf` artifacts;
- prior authorization packages and Migration-050 staging evidence;
- authoritative DB identity above.

## Remaining locks

- another authorization or run;
- automatic retry / resume / successor;
- `WINDOW_1H` / `4H` / `12H` / `24H`;
- retrieval, dirty memory, paper decisions, BUY/SELL/HOLD;
- positions, trades, audits, PnL;
- wallets, signing, real funds, paid APIs;
- scoring, ranking, confidence, weighting.

## Exact next step

Stop after this focused validation follow-up and closeout.

A later explicit lane may inspect the hardened temporal contract and prepare
**one** fresh authorization bound to the then-current repaired code tip and DB
identity. Do not create another authorization in this lane.
