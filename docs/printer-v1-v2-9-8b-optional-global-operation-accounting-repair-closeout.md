# Printer V1 V2-9.8B Optional-Global Operation Accounting Repair Closeout

Date: 2026-07-29

Starting HEAD:
`f9bf35ccfa2bc51d807e1bc5c2b22775848a7510`

Required authoritative database SHA-256:
`688aa243efe82d1d034bac2f46181ab929a0874400ed9be3709ac29fd7555275`

Lane:
`V2-9.8B Optional-Global Operation Accounting Repair and Offline Proof`

## Verdict

`V2_9_8B_OPTIONAL_GLOBAL_OPERATION_ACCOUNTING_REPAIR_PASS`

The exact live blocker was reproduced from durable evidence and code, repaired
in the canonical transport and integration owners, and closed by frozen,
disposable, migration-049 offline proofs.

No live provider, RPC, recovery, N2, N7, campaign, cursor action, or
authoritative database mutation occurred.

## Source-grounded blocker classification

```text
BLOCKER CLASSIFICATION: COMMITTED_CODE_DEFECT
PRIMARY ROOT-CAUSE CLASS: non-transport work counted as transport
CODE CHANGE JUSTIFIED: YES
CANONICAL OWNERS:
  canonical live candidate-acquisition transport owner
  candidate-acquisition integration owner
AUTHORIZATION STATUS: offline implementation and proof only
```

The live authorization was consumed by the earlier, already-closed proof. This
repair consumed no new live authorization and made no provider contact.

## Exact persisted two-operation root cause

Evidence inspected:

- execution `20260729T200835Z-acq-2849418f5f07`;
- integration `cain-754abcd6eaa47248a63820d8e8f812c2`;
- optional work kind `pumpfun_migration_transaction`;
- source failure `UNSUPPORTED_PUMP_CONTRACT`.

The persisted source-failure payload contained:

| Ordinal | Operation kind | State | Redacted role | Bytes | What it was |
| ---: | --- | --- | --- | ---: | --- |
| 1 | `getTransaction` | `COMPLETE` | `PUMP_MIGRATION_TRANSACTION_1` | 8,463 | The one real finalized HTTP/RPC attempt and returned response |
| 2 | `ATTEMPTED_TRANSPORT` | `FAILED` | `PUMP_MIGRATION_TRANSACTION_1` | 0 | A fabricated detail created when local Pump decoding rejected the already-returned response |

The code path was exact:

```text
one rpc_call(getTransaction)
-> append one TransportResponse
-> local decode returns supported=false
-> local UNSUPPORTED_PUMP_CONTRACT exception
-> shared failure helper appends a second FAILED transport detail
```

There was no second provider invocation. The declared per-work ceiling of one
was correct. The measured count of two was wrong because local validation was
represented as transport.

### Confirmed and rejected hypotheses

| Hypothesis | Decision | Evidence |
| --- | --- | --- |
| incorrect predeclared operation plan | Rejected | The work legitimately performs at most one `getTransaction` |
| duplicate accounting | Rejected as the primary class | No second real attempt or duplicate response existed; the extra row represented local work |
| non-transport work counted as transport | Confirmed | The local unsupported-contract exception created the zero-byte second detail |
| hidden transport call | Rejected | The call path and frozen call ledger contain one RPC call |
| mixed defect | Rejected as the root-cause class | Failed-work omission was a connected downstream persistence defect, not a second cause of the two-operation count |
| evidence insufficient | Rejected | Durable detail rows, code, and frozen reproduction agree |

The required root-cause classification is therefore:

`non-transport work counted as transport`

## Accounting design implemented

The canonical identity of a transport operation is:

```text
source_name
+ request_kind
+ work_ordinal
+ transport_ordinal
+ ordered operation_kind
```

The redacted endpoint role remains durable actual provenance. Ordered operation
kinds are predeclared before execution and stored in the durable terminal report
for deterministic replay.

The complete boundary is now:

```text
ordered predeclared operation plan
-> actual low-level attempts
-> normalized operation details
-> source response/failure
-> acquisition work
-> durable transport-operation rows
-> count + ordered-identity + byte validation
-> terminal report
-> zero-source replay
```

Changes:

- introduced a distinct local validation exception that never creates a new
  transport-operation detail;
- retained transport failures as exactly one failed attempt with method, role,
  bytes, and terminal state;
- predeclared ordered operation kinds for every acquisition work item;
- rejected equal-count/wrong-kind results as
  `OPERATION_ACCOUNTING_MISMATCH`;
- retained the existing exact-count versus declared-ceiling behavior;
- added a post-observation overall transport-ceiling check without raising any
  ceiling;
- persisted every post-request accounting, byte, row, and response-ceiling
  failure before universal stop;
- added governed response/failure, duration, and operation-plan reconciliation
  fields to the durable report;
- preserved the exact report as the zero-source replay authority.

Frozen adapters that do not represent a low-level network boundary normalize
their already-declared fixture plan into operation details. Canonical
live-shaped proof paths emitted all details directly and reported zero
synthesized work items.

## Failed-work persistence

Once Source Governor has created a source request, a later accounting failure
now persists:

- its Scheduler job;
- source request;
- source response or source failure;
- terminal acquisition work row;
- every observed transport-operation row;
- exact observed bytes;
- exact normalized rows;
- duration;
- exact first terminal cause;
- cumulative integration totals; and
- report/replay totals.

A mismatch no longer raises between Source Governor persistence and work
persistence.

## Optional-source isolation

The implemented precedence is:

```text
accounting or ceiling defect
-> persist observed evidence
-> universal fail-closed stop

exactly accounted optional provider/contract/coverage outcome
-> persist failed or coverage work
-> diagnostic observer status only
-> required=false
-> admission_authority=NONE
-> universal_failure_contribution=false
-> continue unrelated cohort and admission work
```

Optional status cannot conceal an accounting mismatch. Conversely, an honest,
exactly accounted optional source failure does not enter universal required
failures.

Exact optional failure categories proved:

| Outcome | Source/work result | Observer result | Integration behavior |
| --- | --- | --- | --- |
| provider failure | `SOURCE_TRANSPORT_FAILURE`; one failed transport | provider unavailable | continue |
| unsupported Pump contract | `UNSUPPORTED_PUMP_CONTRACT`; one complete transport followed by local rejection | blocked contract | continue |
| malformed returned page | `SOURCE_MALFORMED`; one complete transport followed by local rejection | provider unavailable | continue |
| null/pruned transaction | `PUMP_TRANSACTION_NULL_OR_PRUNED`; one complete transport followed by local rejection | gapped | continue |
| bounded page coverage | successful page work with `GAPPED` continuity | gapped | continue without advancing the optional migration head |
| genuine undeclared operation | `OPERATION_ACCOUNTING_MISMATCH` | cannot hide defect | persist and stop universally |
| equal count but wrong method | `OPERATION_ACCOUNTING_MISMATCH` | cannot hide defect | persist and stop universally |
| predeclared overall ceiling breach | `TRANSPORT_OPERATION_CEILING` | not optionalized | stop before a request |

## Live-shaped unsupported-contract offline result

The frozen one-shot transport reproduced the live shape with exactly:

- one optional `pumpfun_migration_transaction` work item;
- one real `getTransaction`;
- one normalized `COMPLETE` operation detail;
- one source failure `UNSUPPORTED_PUMP_CONTRACT`;
- one failed Scheduler job;
- one failed acquisition work row;
- one durable transport-operation row;
- zero fabricated second operation;
- zero operation-identity mismatches; and
- continuation through the unrelated acquisition funnel.

The disposable fixture transaction was 1,426 bytes. This fixture byte count is
not a claim about the earlier live response; the earlier persisted response
remains exactly 8,463 bytes.

## Exact N2 offline proof

The live-shaped unsupported-contract proof completed:

| Field | Result |
| --- | ---: |
| Scheduler jobs | 23 |
| governed requests | 23 |
| governed responses | 22 |
| governed failures | 1 |
| acquisition work rows | 23 |
| failed work rows | 1 |
| transport operations | 24 |
| operation bytes | 9,213 |
| normalized/work rows | 31 |
| raw unique nominations | 4 |
| deterministic cohort | 4 |
| enrichment identities | 4 |
| out-of-cohort enrichment | 0 |
| identity-reconciled work items | 23 |
| identity mismatches | 0 |
| frozen synthesized live-shaped details | 0 |
| selected certificates/manifest items | 2 |
| legacy projection | 2 |
| runtime handoff | 0 |
| active leases after stop | 0 |
| Scheduler residue | 0 |

Every report total matched the corresponding durable rows and sums. The
optional observer remained:

```text
observer_status=GLOBAL_PUMP_OBSERVER_BLOCKED_CONTRACT
required=false
admission_authority=NONE
universal_failure_contribution=false
```

The persistent historical gap remained represented exactly as:

```text
authoritative head slot: 435985595
frozen tip slot: 435999023
last recovery continuation slot: 435998983
pages inspected: 44
signatures inspected: 11000
exact prior boundary reached: false
terminal reason: CURSOR_RECOVERY_LANE_BOUND_EXHAUSTED
cursor mutation performed: false
```

## Runtime-neutral N7 offline proof

The disposable N7 mechanics completed with:

| Field | Result |
| --- | ---: |
| Scheduler jobs / governed requests | 48 / 48 |
| transport operations | 35 |
| bytes | 17,033 |
| rows | 87 |
| exact manifest items | 7 |
| projection | 0 |
| runtime handoff | 0 |
| lifecycle started | false |
| protected deltas | zero |
| zero-source replay | exact |

The legacy two-token projection continued to reject a seven-item manifest.
This proof does not authorize live N7 or runtime capacity above two.

## Report, replay, compact storage, and schema decision

- Terminal reports are durable JSON rows.
- Every report stores the compact ordered predeclared plan by work ordinal.
- Source response/failure payloads retain normalized actual-operation details.
- Work rows and transport-operation rows retain measured terminal evidence.
- Zero-source replay returned the exact stored report and made zero provider,
  Scheduler, lifecycle, or evidence writes.
- Compact global page summaries, hashes, and positive-match summaries remain;
  no raw program-wide signature arrays were introduced.
- No schema or migration change was required. Migration 049 already provides
  immutable work, operation, and report tables with exact joins.

## Offline proof matrix

| Requirement | Result |
| --- | --- |
| live-shaped unsupported contract | PASS |
| declared/measured ordered identities | PASS |
| failed Scheduler/Governor/work/operations/bytes/rows | PASS |
| optional failure excluded from universal required failures | PASS |
| nomination through exact-two projection with zero handoff | PASS |
| observer diagnostic with `admission_authority=NONE` | PASS |
| undeclared extra operation persists and stops | PASS |
| overall operation ceiling remains fail-closed | PASS |
| provider/unsupported/malformed/null-pruned/coverage outcomes | PASS |
| success paths reconcile | PASS |
| report totals equal durable totals | PASS |
| deterministic zero-source replay | PASS |
| compact storage/no raw program signature arrays | PASS |
| cursor and recovery fixtures unchanged | PASS |
| runtime-neutral exact-seven mechanics | PASS |
| protected tracking/memory/retrieval/financial deltas | PASS |

## Verification

Focused optional-accounting selection:

```text
18 passed, 98 deselected
```

Broad affected integration suite:

```text
116 passed
```

Directly affected regressions:

```text
candidate-acquisition foundation: 25 passed
cursor-continuity recovery: 16 passed
Source Governor + Scheduler: 44 passed
public operational command: 11 passed
```

Distinct executed test total:

```text
212 passed
```

Additional checks:

- Python compilation: PASS;
- fresh disposable migration through 049: PASS;
- SQLite integrity: `ok`;
- foreign-key violations: zero;
- cursor/recovery production and fixture files: no diff;
- `git diff --check`: PASS;
- authoritative database SHA-256:
  `688aa243efe82d1d034bac2f46181ab929a0874400ed9be3709ac29fd7555275`.

## Files changed

- `src/printer_v1/operator_cli/live_candidate_acquisition_transport.py`
- `src/printer_v1/operator_cli/candidate_acquisition_integration.py`
- `tests/test_v2_9_8b_candidate_acquisition_post_foundation_integration.py`
- `docs/printer-v1-v2-9-8b-optional-global-operation-accounting-repair-closeout.md`
- `AGENTS.md`
- `docs/printer-v1-assistant-active-build-order-anchor.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`

## Money-usefulness contribution

The repair prevents optional global coverage from suppressing otherwise
admissible exact-pool candidates, while retaining universal failure for real
accounting defects. That protects corpus growth from both false blockage and
hidden source-cost inflation. It does not claim profitability or unlock any
financial behavior.

## What remained locked and untouched

- Solana-only and Solana-memecoin-only;
- paper-only;
- wallet, private key, signing, transaction submission, and real funds;
- paid sources;
- scores, ranks, confidence, weighting, quotas, embeddings, and vectors;
- Source Governor and Central Scheduler bypass;
- all request, operation, byte, row, duration, and Scheduler ceilings;
- active runtime capacity exactly two;
- authoritative database content;
- migrations and schema;
- cursor reset, rewind, recovery continuation, or historical fabrication;
- live N2, live N7, and operational campaign execution;
- tracking handoff, lifecycle, snapshots, windows, memory, retrieval,
  decisions, BUY/SELL/HOLD, positions, trades, audits, and PnL.

## Functionality Risks / Setbacks / Efficiency Blockers

1. The repaired path has not yet been exercised by a new live provider
   response. Offline proof establishes deterministic implementation behavior,
   not current provider availability or indexing completeness.
2. The optional global historical gap remains real and unresolved. It is
   diagnostic coverage evidence only and cannot prove absence.
3. A provider can still return an honest unsupported, malformed, pruned, or
   incomplete result. The repaired integration continues only because that
   source is optional; candidate-specific graduation evidence remains strict.
4. Frozen generic adapters may normalize their explicit predeclared fixture
   plan. Canonical live-shaped proofs require and achieved zero synthesized
   operation details.
5. No source ceiling was raised. Bounded plans may therefore yield fewer
   observations or candidates under real provider limitations.

## Exact next permitted task

Operator review.

Only if separately and explicitly authorized, the next permitted technical
task is:

```text
one future bounded live N2 proof of the repaired optional-global
operation-accounting boundary
```

This PASS does not authorize an automatic live run, retry, recovery, cursor
action, N7, operational campaign, or later runtime lane.
