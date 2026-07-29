# Printer V1 V2-9.8B End-to-End Candidate Admission Closeout

Date: 2026-07-29

Starting HEAD: `599179f84e210c050884ebd88398c361a945b9e6`

Live launch HEAD: `d2d2e0617c50be6bcee57045e6fe7e2e918cb1de`

Lane: `V2-9.8B End-to-End Candidate Admission Audit, Repair, and Final Live N2 Proof`

## Verdict

`V2_9_8B_END_TO_END_CANDIDATE_ADMISSION_LIVE_N2_BLOCKED`

The full source-grounded audit classified twelve connected admission defects as
`COMMITTED_CODE_DEFECT`. They were designed and repaired together without a
schema, migration, ceiling, capacity, cursor-policy, Scheduler, Source Governor,
safety, or capability change. All offline admission gates passed.

Exactly one final canonical live N2 then ran. It loaded both established
`FORWARD` cursor heads and blocked before foundation because neither bounded
live-tail page reached its stored boundary before the page ceiling. Both ranges
reported `GAPPED` / `LIVE_TAIL_PAGE_CEILING_BEFORE_BOUNDARY`; zero cursor
advances were proposed or committed, and every persisted cursor row remained
byte-identical to the fresh backup.

This is a terminal, honest evidence-continuity outcome for this run. It did not
expose a new admission implementation defect and does not authorize a patch,
retry, restart, successor, cursor reset, live N7, or campaign. No code was
changed after the live invocation.

## Confirmed and rejected findings

Confirmed systemic defects:

1. DexScreener and GeckoTerminal base/quote/DEX identity loss.
2. lost Dex requested-token correlation for quote-side returns.
3. integration base-mint synthesis and quote omission.
4. Pump bonding curve, PumpSwap Pool, and generic pool role conflation.
5. missing exact pool target/slot/address association evidence.
6. no exact-present generic non-Pump pool branch.
7. unconditional rejection of an exact active Pump bonding curve.
8. pool/base/quote merge pollution by non-pool observations.
9. identity completeness masking precise pool and quote failures.
10. imprecise failure-family precedence.
11. cross-execution observation primary-key collisions.
12. synthetic PumpSwap-only offline fixtures hiding live-shaped paths.

Rejected as systemic defects:

- genuine high holder concentration;
- missing holder provider evidence;
- honest low or missing liquidity;
- zero or missing route/tradeability activity;
- stale or ageless market evidence;
- unsupported mint, pool role/program, or lineage;
- active tracking or cooldown conflict; and
- complete governed coverage yielding fewer than N eligible candidates.

These remain valid categorical fail-closed outcomes. `UNKNOWN_ORIGIN` remains
allowed only through the approved exact-present non-Pump branch and never
asserts Pump lineage.

## Final architecture

The final admission chain preserves exact provider and on-chain relationships:

```text
requested candidate mint
→ exact aggregator pair and base/quote orientation
→ exact RPC pool target association
→ distinct Pump curve / PumpSwap / generic pool role
→ exact pool owner/program relationship
→ exact SPL or Token-2022 mint evidence
→ holder, safety, market, age, liquidity, and tradeability facts
→ atomic tracking/cooldown recheck
→ foundation identity, certificate, reserve, and exact-N manifest
```

Pump bonding curves require the exact creation contract, derived PDA, Pump
owner, complete pinned account prefix, decoded quote, and `complete=false`.
Graduated Pump candidates require the existing exact migration plus canonical
PumpSwap proof. Generic pools require provider orientation, exact pool account
owner, and an exact executable owner-program account. Provider venue labels
remain diagnostic and are never promoted to program authority.

Pool identity merge now consumes only pool-linked observations. Identity
availability and pool/quote validity are separate gates, preserving the first
precise categorical cause. Observation content hashes remain content-based;
primary keys additionally bind execution identity for safe sequential replay.

Foundation remains the sole certificate/reserve/manifest owner. Active runtime
capacity is exactly two and `M=2N` is unchanged.

## Offline proof

Positive live-shaped proof totals:

| Proof | Issued | Admitted | Manifest | Projection | Handoff | Result |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| N2, four-candidate cohort | 4 | 4 | exactly 2 | 2 | 0 | `COMPLETED` |
| N7, seven-candidate cohort | 7 | 7 | exactly 7 | 0 | 0 | `COMPLETED` |

N2 reconciled Scheduler/Governor/transport as `20 / 20 / 23`; N7 reconciled
`44 / 44 / 32`. In both proofs measured transport operations equaled frozen
low-level calls, deterministic replay made no new transport call, active leases
and Scheduler residue were zero, integrity was `ok`, foreign-key violations
were zero, and every protected-table delta was zero. N7 rejected the legacy
two-token projection exactly as required.

The positive matrix covered:

- exact active Pump bonding curve;
- exact graduated PumpSwap Pool;
- exact-present generic non-Pump pool;
- approved unknown-origin behavior;
- classic SPL Token and Token-2022;
- mixed DexScreener, GeckoTerminal, and direct Pump overlap; and
- initial `FORWARD` bootstrap plus a sequential established-cursor execution.

The negative live-shaped matrix preserved the first exact cause for missing
quote, wrong pool role/program, base/quote reversal, pool-target mismatch,
holder failure, liquidity failure, and tradeability failure. Directly affected
foundation/integration regressions also prove unsupported lineage, stale
evidence, active tracking/cooldown conflict, malformed/incomplete provider and
account evidence, mint target mismatch, unsupported token programs, provider
failure, budget exhaustion, and honest N-minus-one shortage.

## Tests and checks

- focused foundation/integration suite: `93 passed`;
- focused plus provider normalizers: `161 passed`;
- broad affected migration/Source Governor/Scheduler/provider/Pump/admission
  suite: `300 passed, 1 deselected, 10 subtests passed`;
- compilation of all changed Python modules and the changed test module: PASS;
- `git diff --check`: PASS;
- fresh disposable migration application and idempotent reapplication: 49
  migrations, latest 049, integrity `ok`, zero foreign-key violations.

The one deselected historical Phase-1 assertion is a confirmed baseline test
defect: clean HEAD hard-codes migration 034 while clean HEAD already contains
migrations 035 through 049. Its surrounding broad suite initially produced
`300 passed, 1 failed, 10 subtests passed`; no production or test rule was
weakened. The current disposable migration-049 proof passed independently.

## Pre-live gate and backup

| Gate | Result |
| --- | --- |
| clean launch HEAD | `d2d2e0617c50be6bcee57045e6fe7e2e918cb1de` |
| authoritative starting DB SHA-256 | `898d9b0fa9e99417a3429c21f5dd02817d80d3b78402c4e35d2c261e9e62f1c9` |
| migration / integrity / foreign keys | 049 / `ok` / zero |
| journal / sidecars | `delete` / none |
| active Printer process / DB handle | none / none |
| active lease / integration / Scheduler work | zero / zero / zero |
| RPC configuration | present; value not printed or persisted |
| canonical preflight | `V2_9_8_OPERATIONAL_PREFLIGHT_READY`; zero source calls/writes |
| active runtime capacity / automatic retries | 2 / 0 |

Fresh backup:

`/private/tmp/printer-v1-end-to-end-admission-live-n2.5GfQT0/printer_v1.pre-n2.backup.sqlite3`

Source and backup were both 17,305,600 bytes and shared SHA-256
`898d9b0fa9e99417a3429c21f5dd02817d80d3b78402c4e35d2c261e9e62f1c9`.
The backup reached migration 049, integrity `ok`, and zero foreign-key
violations.

## Exactly one live N2

The required public command was invoked exactly once:

```bash
.venv/bin/python -m printer_v1.operator_cli.operational_memory_factory_command acquisition-only-n2 --operator-approved
```

| Field | Result |
| --- | --- |
| exit / wall time | 0 / 19.760 seconds |
| execution ID | `20260729T175446Z-acq-222214011e4b` |
| integration ID | `cain-d0cf5b5218027acaabe2b7490bf3dc0f` |
| canonical status | `BLOCKED` |
| first cause / detail | `CURSOR_CONTINUITY_GAPPED` / same |
| established heads loaded / bootstrap | 2 / 0 |
| proposed / committed advances | 0 / 0 |
| raw nominations / enriched identities | 40 / 4 |
| foundation executions / certificates / manifests | 0 / 0 / 0 |
| exact cohort / selected / projection / handoff | 0 / 0 / 0 / 0 |
| Scheduler jobs / governed requests / transport operations | 20 / 20 / 23 |
| work and Scheduler terminal states | 20 `SUCCEEDED` / 20 `SUCCEEDED` |
| source responses / source failures | 20 / 0 |
| retry / restart / successor / N7 | false / false / false / not run |
| lease / Scheduler residue | 0 / 0 |
| integrity / foreign keys | `ok` / zero |
| protected-table delta sum | 0 |

Both cursor namespaces ended at the current live tip without encountering their
stored boundary inside the two-page ceiling. Both exact ranges were persisted
as `GAPPED`, `cursor_advanced=false`, with
`LIVE_TAIL_PAGE_CEILING_BEFORE_BOUNDARY`. All four cursor rows—two historical
`BACKWARD` and two established `FORWARD`—have identical before/after row hashes.

The post-live authoritative DB SHA-256 is
`c8787da63b1f37a21366399444420e392d273d574e0904a06b2395bd83da3bc3`;
size is 17,448,960 bytes. Integrity is `ok`, foreign-key violations are zero,
and no sidecar remains.

Redacted terminal evidence is stored in
`docs/printer-v1-v2-9-8b-end-to-end-candidate-admission-live-n2-redacted.json`.

## Files changed

- `docs/printer-v1-v2-9-8b-end-to-end-candidate-admission-audit.md`
- `docs/printer-v1-v2-9-8b-end-to-end-candidate-admission-design.md`
- `docs/printer-v1-v2-9-8b-end-to-end-candidate-admission-closeout.md`
- `docs/printer-v1-v2-9-8b-end-to-end-candidate-admission-live-n2-redacted.json`
- `src/printer_v1/discovery/candidate_acquisition.py`
- `src/printer_v1/operator_cli/candidate_acquisition_integration.py`
- `src/printer_v1/operator_cli/live_candidate_acquisition_transport.py`
- `src/printer_v1/sources/dexscreener.py`
- `src/printer_v1/sources/geckoterminal.py`
- `src/printer_v1/sources/pump_contracts.py`
- `tests/test_v2_9_8b_candidate_acquisition_post_foundation_integration.py`

## What was not touched

No schema/migration, source ceiling, `M=2N`, active capacity, cursor policy,
Scheduler or Source Governor ownership, cohort rule, mint rule, holder/safety
floor, campaign, tracking handoff, lifecycle, snapshot, window, memory,
retrieval, paper decision, BUY/SELL/HOLD, position, trade, audit, PnL, wallet,
signing, transaction, funds, paid source, score, rank, confidence, weight,
embedding, or vector capability was added or loosened.

There was no live N7, retry, restart, successor, cursor reset, or campaign.

## Risks and remaining concerns

- The repaired admission branches are fully proved offline but were not reached
  by the terminal live run because cursor continuity blocked first.
- Both established forward boundaries fell beyond the fixed two-page live-tail
  ceiling. This run supplies categorical evidence of that condition; it does
  not authorize changing the ceiling or cursor policy.
- Generic pool admission deliberately proves exact provider orientation plus
  current on-chain account owner/executable-program relationship; it does not
  claim an unsupported generic program-specific account layout.
- Holder concentration, liquidity, tradeability, source coverage, and market
  freshness remain variable honest rejection gates in any future authorized
  run.

## Exact next permitted task

Operator review of this terminal BLOCKED closeout and redacted artifact only.

No retry, successor, cursor reset, live N7, operational campaign, tracking,
lifecycle, snapshots, windows, memory, or later runtime lane is authorized. Any
future source-grounded cursor-range investigation or other action requires a
separate explicit operator authorization under the active source stack; this
closeout does not create an automatic repair lane.
