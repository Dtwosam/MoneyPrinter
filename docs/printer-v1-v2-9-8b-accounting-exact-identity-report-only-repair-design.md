# Printer V1 V2-9.8B Accounting and Exact-Identity Report-Only Repair Design

Date: 2026-07-30

Design baseline:
`d07b9690359a854c7d7e0969eb68b2bda219c2de`

Forensic source:
`docs/printer-v1-v2-9-8b-first-authoritative-15m-forensic-audit.md`

Design verdict:
`V2_9_8B_FIRST_AUTHORITATIVE_15M_ACCOUNTING_EXACT_IDENTITY_REPORT_ONLY_REPAIR_DESIGN_PASS`

Implementation status:
`NOT_STARTED`

## 1. Boundary

This lane is design/specification only.

Allowed:

- static source inspection;
- existing artifact and read-only forensic evidence review;
- accounting ownership design;
- exact-identity report-only design;
- focused implementation and proof plan;
- documentation.

Not allowed:

- source-code implementation;
- migration or authoritative database mutation;
- report backfill or repair of the July 31 attempt;
- provider/RPC/WebSocket calls;
- discovery, recovery, cursor, N2, N7, or backfill execution;
- another campaign attempt;
- memory generation;
- `WINDOW_1H` or longer-window activation;
- retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, paper-trade
  audits, or PnL.

The permanent first-attempt marker remains valid and continues to prohibit a
rerun of execution `20260731T002406Z-7612696c7295`.

## 2. Defects Being Designed

### 2.1 Missing complete stage-evidence handoff

The public coordinator created one `CampaignSixUnitOwner` before operational
work and passed `campaign_units.ingest_stage_evidence` as the one-way sink.

The authoritative operational owner emitted eligible-supply evidence only after
its supply call returned. The bounded `SOURCE_VISIBILITY_SHORTAGE` raised before
that return boundary, so the completed discovery/liquidity stage did not hand its
full evidence to the campaign owner.

Durable attempt facts were:

```text
campaign source operations: 30
retained stage evidence: 1 stage / 4 transport operations
report_written: false
report_block_reason: SIX_UNIT_EVIDENCE_MISSING
```

### 2.2 Global latest-report selection

Public `report-only` selected the globally newest terminal report:

```sql
WHERE report_state='REPORT_TERMINAL'
ORDER BY created_at DESC, report_id DESC
LIMIT 1
```

Because the July 31 attempt correctly wrote no terminal report, `report-only`
replayed an unrelated July 28 report with 14 source calls.

The replay was zero-source and no-write, but semantically stale for the intended
attempt.

## 3. Design Goals

The repair must:

1. preserve one campaign accounting authority;
2. guarantee one immutable evidence handoff for every started governed stage;
3. seal and ingest bounded-shortage evidence before the terminal exception is
   re-raised;
4. reconcile the campaign owner's identities with exact action-local governed
   source-operation truth;
5. prevent missing evidence from becoming synthetic or reconstructed evidence;
6. make `report-only` target one exact attempt identity;
7. return an explicit blocked replay when that attempt has no terminal report;
8. prohibit fallback to another campaign;
9. preserve zero-source, zero-Scheduler, and zero-write replay;
10. keep all existing V1 locks intact.

## 4. Ownership Model

### 4.1 Single campaign owner remains authoritative

`CampaignSixUnitOwner` remains the only campaign-wide accounting authority.

Stage owners may measure and expose immutable evidence blocks. They may not:

- derive the final campaign totals independently;
- write a second campaign report;
- select a replacement evidence source;
- reconcile another campaign's rows;
- convert database rows into synthetic stage evidence.

The public coordinator remains responsible for:

- creating the owner before the first accounted operation;
- passing the same one-way ingestion sink through the active operational graph;
- closing the owner only after all started stages have terminalized;
- comparing the owner against exact action-local operation truth;
- authorizing report build only when accounting is complete.

### 4.2 Stage owners remain measurement owners only

Each governed stage owns its local measured transport ledger until that stage is
sealed. It then hands one immutable evidence block to the campaign sink.

The eligible-supply/discovery owner must receive the same sink directly. The
upper live-operational composition layer must not wait for a successful return
before forwarding evidence that belongs to the supply stage.

## 5. Stage Evidence Lifecycle

Every stage follows this state machine:

```text
UNSTARTED
-> OPEN
-> SEALED_COMPLETED | SEALED_BLOCKED | SEALED_FAILED
-> INGESTED
```

Rules:

- A stage becomes `OPEN` immediately before its first governed operation or
  counted local validation.
- An unstarted stage emits no evidence block.
- `PRE_OPERATION_NO_WORK` remains the only legal all-zero evidence path.
- Every started stage seals exactly once.
- Every sealed stage is handed to the campaign sink exactly once.
- The handoff occurs before a bounded terminal exception leaves the stage owner.
- Repeated sealing, repeated ingestion, stage-ID reuse, mixed campaign identity,
  and duplicate transport identity fail closed.

The stage evidence contract must retain the existing six-unit evidence fields
and add explicit stage metadata:

```text
stage_id
stage_kind
stage_sequence
stage_terminal_status
stage_first_terminal_cause
sealed_at
campaign_id
run_id
cycle_id
transport_operations
local_validations
scheduler_work_items
lifecycle_reservations
```

`stage_terminal_status` is categorical only:

- `COMPLETED`
- `BLOCKED`
- `FAILED`

It does not change whether the measured operations count.

## 6. Ingest-Before-Raise Contract

The eligible-supply path must use one fail-closed ordering:

```text
finish/persist exact bounded source work
-> seal complete stage evidence
-> call the campaign evidence sink
-> confirm ingestion succeeded
-> persist/retain terminal shortage classification
-> raise the original bounded terminal exception
```

For the July 31-shaped case, the evidence handed to the owner must represent all
30 unique governed source operations, not only the four direct-Pump operations.

The implementation must prefer a `try/except/finally` or equivalent scoped-stage
owner that guarantees sealing for:

- normal success;
- true bounded source-visibility shortage;
- operation-budget exhaustion;
- duration exhaustion;
- malformed/partial provider evidence;
- transport failure;
- unexpected exception after one or more governed operations.

The original market/source terminal cause remains separate from any accounting
handoff failure.

If sink ingestion fails:

- preserve the original first terminal cause;
- mark accounting blocked with the exact ingestion failure;
- preserve the sealed stage evidence for diagnostics;
- write no canonical terminal report;
- create no retry, restart, resume, or successor.

## 7. Campaign Accounting Completion Gate

Before report construction, the coordinator must require all of the following:

1. every started stage is sealed;
2. every sealed stage is ingested exactly once;
3. no stage remains `OPEN`;
4. campaign/run/cycle identity matches across owner and every stage;
5. no duplicate transport identity exists across stages;
6. no negative counter exists;
7. the campaign owner is not accounting-blocked;
8. owner transport identities match exact action-local governed operation truth;
9. owner `SOURCE_TRANSPORT_OPERATION` total matches the action-local source-call
   count for the same run;
10. independent reconstruction from durable evidence matches report totals.

The exact action-local source-operation ledger is a verification source, not a
replacement accounting authority. It may prove equality or expose a mismatch.
It must never be used to manufacture missing stage evidence.

Mismatch behavior:

```text
SIX_UNIT_ACCOUNTING_BLOCKED
report_written: false
report_block_reason: CAMPAIGN_STAGE_OPERATION_RECONCILIATION_MISMATCH
```

The blocked summary must include only factual diagnostics:

- owner transport count;
- action-local source-operation count;
- sealed stage count;
- ingested stage count;
- open stage IDs;
- missing stage IDs where determinable;
- duplicate or identity mismatch reason;
- first terminal cause;
- restart/successor false.

## 8. Honest Shortage Reporting

A bounded shortage with complete accounting is reportable.

The canonical terminal report may truthfully record:

- terminal outcome `SOURCE_VISIBILITY_SHORTAGE`;
- required capacity and eligible capacity;
- exact candidate/rejection facts supported by durable evidence;
- exhaustion certificate identity;
- complete six-unit evidence and independently reconstructed totals;
- zero downstream unlocks;
- no restart or successor.

A negative or blocked market outcome does not make the report dirty. Missing or
mismatched accounting does.

The July 31 historical attempt remains `BLOCKED_UNSAFE`; the repair must not
backfill or reclassify that attempt.

## 9. Exact-Identity Report-Only Contract

### 9.1 Identity inputs

Public `report-only` must support exact identity inputs:

```text
--campaign-id <campaign_id>
--run-id <run_id>
```

Both are required together when either is supplied.

With no explicit identity, `report-only` must resolve the newest supervision
record first and use that supervision's exact campaign/run/configuration
identity. It must not choose the newest report row first.

### 9.2 Exact report query

After identity resolution, report selection must be restricted to the exact
attempt:

```sql
WHERE r.report_state='REPORT_TERMINAL'
  AND r.campaign_id=?
  AND c.campaign_id=?
  AND requested_run_id matches configuration/report identity
```

The row identity, configuration identity, and parsed report JSON identity must
all agree with the requested campaign/run pair.

Any mismatch is `REPLAY_BLOCKED`.

### 9.3 No cross-campaign fallback

The following behavior is prohibited:

- global latest terminal report fallback;
- older report fallback;
- discovery-only report substitution for a campaign request;
- nearest timestamp matching;
- partial string/prefix identity matching;
- report reconstruction from unrelated rows.

## 10. Missing Exact Report Behavior

When the exact attempt is terminal but has no terminal report row,
`report-only` returns a zero-source blocked projection instead of raising an
ambiguous error or replaying history.

Required shape:

```json
{
  "mode": "REPORT_ONLY",
  "status": "REPLAY_BLOCKED",
  "requested_identity": {
    "campaign_id": "...",
    "run_id": "..."
  },
  "report_rows": 0,
  "fallback_used": false,
  "block_reason": "EXACT_TERMINAL_REPORT_MISSING",
  "terminal_summary": {
    "status": "OPERATIONAL_CAMPAIGN_TERMINAL_FAILURE",
    "first_terminal_cause": "...",
    "accounting_status": "...",
    "report_written": false,
    "report_block_reason": "...",
    "summary_path": "...",
    "summary_sha256": "..."
  },
  "source_calls": 0,
  "scheduler_runtime_calls": 0,
  "database_writes": 0
}
```

The blocked projection may read the deterministic terminal-summary artifact
for the exact execution identity. It must validate the summary's
campaign/run/configuration identity before returning it.

If the exact summary is missing or mismatched, return:

```text
REPLAY_BLOCKED
block_reason: EXACT_TERMINAL_SUMMARY_MISSING_OR_MISMATCHED
```

It must not fabricate six-unit totals or candidate outcomes.

## 11. Artifact and Database Boundary

No migration is approved by this design.

The implementation should first use existing:

- campaign configuration identity;
- campaign/run/cycle/supervision rows;
- terminal report rows;
- deterministic execution artifact directory;
- terminal-summary JSON;
- action-local governed operation accounting.

If implementation inspection proves that exact identity cannot be enforced
without schema change, implementation must stop and return a schema-design
blocker. It must not add a migration opportunistically.

The historical July 31 report table remains unchanged. No canonical report row
may be inserted for that attempt.

## 12. Likely Implementation Surface

Likely files, subject to exact implementation audit:

- `src/printer_v1/operator_cli/operational_memory_factory_command.py`;
- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`;
- the canonical eligible-supply owner containing
  `run_persistent_eligible_token_supply`;
- `src/printer_v1/sources/campaign_six_unit_accounting.py`;
- directly affected accounting, terminalization, eligible-supply, and
  report-only tests.

Not in scope:

- alternate runners;
- new source loops;
- Scheduler redesign;
- source budget increases;
- candidate-acquisition N2/N7;
- migrations unless a later dedicated design approves one;
- historical report mutation.

## 13. Focused Proof Plan

All runtime proof uses frozen transports and fresh disposable migration-049
databases.

### 13.1 Stage handoff tests

Prove:

- successful stage seals and ingests once;
- bounded shortage seals and ingests before raise;
- operation-budget exhaustion seals and ingests before raise;
- malformed/partial provider result still accounts for every attempted
  transport;
- unexpected failure after partial work seals a `FAILED` stage;
- sink failure preserves the original first cause and blocks reporting;
- duplicate stage ID, duplicate transport identity, identity mismatch, missing
  evidence, and negative counters fail closed.

### 13.2 July 31-shaped accounting proof

Use frozen evidence shaped like the forensic attempt:

```text
30 governed source operations
2 required eligible candidates
1 eligible candidate
15 provider failures
12 malformed/partial liquidity outcomes
SOURCE_VISIBILITY_SHORTAGE
```

Require:

- all 30 unique transport identities reach the single campaign owner;
- owner source-operation total equals action-local source-call total;
- stage evidence is complete before shortage raises;
- one canonical honest blocked report is written;
- independent six-unit reconstruction matches stored totals;
- no synthetic zero evidence;
- no lifecycle, memory, retrieval, decision, position, trade, audit, or PnL
  delta;
- no retry/restart/successor.

### 13.3 Exact-identity report-only tests

Prove:

- explicit exact campaign/run replays only that report;
- no-argument mode resolves latest supervision identity first;
- exact current report missing returns `REPLAY_BLOCKED`;
- exact blocked summary is returned only when identity matches;
- missing/mismatched summary returns `REPLAY_BLOCKED` without fallback;
- an older globally latest report is never returned for the requested attempt;
- report-row/configuration/report-JSON identity mismatch blocks replay;
- unknown campaign/run blocks replay;
- discovery-only output is not substituted for a campaign request;
- successful replay creates zero new reports, source calls, Scheduler calls, or
  database writes;
- blocked replay also creates zero source calls, Scheduler calls, or writes.

### 13.4 Regression boundary

Run only minimum sufficient verification:

- changed accounting tests;
- changed eligible-supply/operational-owner tests;
- changed public command/report-only tests;
- nearest initialized-failure and terminal-report regressions;
- one normal two-token ordinary `WINDOW_15M` disposable-DB success regression;
- Python compilation and `git diff --check`.

Do not run a broad repository suite during the narrow implementation prompt.
Reserve the broader directly affected suite for implementation closeout or
pre-proof review.

## 14. Acceptance Gate

Implementation may pass only when:

1. every started stage hands complete immutable evidence before returning or
   raising;
2. the single owner reconciles exactly to action-local governed operations;
3. a July 31-shaped shortage produces a complete honest blocked report;
4. missing evidence still prevents report creation;
5. `report-only` is exact-identity bound;
6. no cross-campaign fallback exists;
7. exact missing report returns deterministic `REPLAY_BLOCKED`;
8. all replay paths remain zero-source, zero-Scheduler, and zero-write;
9. normal two-token 15m behavior remains unchanged;
10. all V1 locks and the permanent no-rerun marker remain preserved.

## 15. Stop Conditions

Stop implementation and return BLOCKED if:

- a second campaign accounting authority is required;
- source-operation rows would be converted into synthetic missing stage
  evidence;
- the July 31 report would be backfilled or mutated;
- a schema migration appears necessary without a dedicated schema design;
- exact report identity cannot be proven;
- report-only still needs global latest fallback;
- a provider call or authoritative DB proof is proposed;
- another campaign or recovery action is proposed;
- tests require weakening evidence, identity, or no-rerun rules.

## 16. Money-Usefulness Contribution

This repair lets Printer preserve honest negative learning about source
visibility and market eligibility without losing the accounting chain that
makes the evidence trustworthy. It prevents an operator from seeing a valid but
unrelated historical report and mistaking it for the current campaign.

That improves future capital-protection learning while still refusing to turn
incomplete evidence into clean memory or a paper decision.

## 17. What This Design Improves

- closes the exact ingest-before-shortage gap;
- preserves one accounting authority;
- reconciles stage evidence to action-local operations;
- permits honest source-visibility shortage reports when evidence is complete;
- binds report-only to exact campaign/run identity;
- replaces stale fallback with deterministic blocked replay;
- defines focused proof without broad scope expansion.

## 18. What This Design Still Does Not Unlock

This design does not unlock:

- implementation;
- repair or backfill of the historical attempt;
- another campaign;
- provider/RPC calls;
- memory generation;
- clean-memory promotion;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, or `WINDOW_24H`;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions, trades, audits, or PnL;
- live wallets, private keys, signing, real funds, or live execution;
- paid APIs, scoring, ranking, confidence, weighting, embeddings, or vectors.

## 19. Functionality Risks / Setbacks / Efficiency Blockers

- A stage-level `finally` path can accidentally replace the original terminal
  exception; the implementation must preserve first-cause precedence.
- Sealing too early can omit later operations; sealing too late recreates the
  July 31 defect.
- Emitting evidence from both the supply owner and upper operational owner can
  double-ingest the same stage; ownership must be singular.
- Action-local DB accounting can expose mismatch but must not become a second
  evidence generator.
- Exact artifact lookup must never scan for a nearest timestamp or prefix.
- No-argument report-only semantics can remain ambiguous unless latest
  supervision identity is resolved before report selection.
- Existing historical reports use older report shapes; compatibility must not
  weaken exact identity validation for current reports.
- A narrow repair touching accounting and terminal replay is cross-cutting
  enough to require nearest affected regressions, but not a full suite during
  implementation.

## 20. Design Closeout and Next Task

Design verdict:

```text
V2_9_8B_FIRST_AUTHORITATIVE_15M_ACCOUNTING_EXACT_IDENTITY_REPORT_ONLY_REPAIR_DESIGN_PASS
```

Exact next permitted task:

```text
V2-9.8B First Authoritative WINDOW_15M Accounting and Exact-Identity Report-Only Repair Implementation
```

That lane may implement only the approved accounting handoff, completion gate,
and exact-identity report-only behavior with focused disposable-DB tests. It may
not mutate the authoritative database, contact providers, repair the historical
report, run another campaign, or unlock any later capability.

This design supersedes older next-task pointers that still name campaign
readiness, campaign execution, closeout, or forensic audit as the current next
step.
