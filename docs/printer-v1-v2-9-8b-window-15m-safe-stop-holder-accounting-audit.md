# Printer V1 — V2-9.8B `WINDOW_15M` Safe-Stop / Holder-Accounting Audit

**Date:** 2026-08-05  
**Lane:** `V2-9.8B — WINDOW_15M Safe-Stop Preflight and Holder-Accounting Audit`  
**Type:** Audit/readiness only  
**Baseline branch:** `agent/v2-9-8b-window-15m-freeze-holder-budget-decoupling-repair`  
**Baseline HEAD:** `a1bcc7d8ed8f5e93c9c5f2cfd5432eeb06f087f1`  
**Prior implementation checkpoint:** `e43bfabdbd27dea0928ddaadcc2cc6772ee648ea`  
**Prior closeout verdict:** `V2_9_8B_WINDOW_15M_FREEZE_HOLDER_BUDGET_DECOUPLING_REPAIR_BLOCKED`

## 1. Audit verdict

`V2_9_8B_WINDOW_15M_SAFE_STOP_HOLDER_ACCOUNTING_AUDIT_PASS`

The prior BLOCKED closeout is correct.

The completed holder-budget decoupling repair made a real money-useful improvement:
four valid market/protocol observation candidates survived, the reserve froze to two
selected plus two alternates, and the operational path committed a two-slot handoff.

The continuous proof still did not enter the first `WINDOW_15M` lifecycle. It stopped
after handoff with the generic category:

`SAFE_STOP_PREFLIGHT_FAILED`

Static review identifies two separate defects that must not be collapsed:

1. **Immediate deterministic lifecycle-preflight defect:** the disposable continuous
   proof rebinds the public coordinator to its disposable database, but the downstream
   lifecycle factory independently imports and enforces the production canonical
   database path. The current harness therefore cannot pass operational-persistent
   lifecycle preflight on its disposable database as written.
2. **Later deterministic holder-accounting defect:** governed holder requests and
   numeric measured costs reach durable Source Governor rows and the holder ledger, but
   exact holder `TransportOperationIdentity` records do not reach the campaign six-unit
   owner or the independent action-local ledger.

The first defect is sufficient to explain the observed post-handoff, zero-window stop.
The second defect would still prevent exact full-run accounting acceptance after the
database-target preflight is repaired.

No implementation, test, proof, source call, Scheduler runtime, authorization, or
database mutation was performed in this audit.

## 2. Authority and roadmap alignment

This audit was checked against the active Printer V1 source stack:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`

The lane aligns because:

- V2-9.8B is the active bounded memory-growth operations program.
- A BLOCKED bounded proof must return to audit/readiness and design before another
  implementation or proof.
- `WINDOW_15M` remains the first operational memory target.
- This work strengthens Source Governor, campaign accounting, DB isolation, and proof
  truthfulness.
- It does not unlock retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits,
  PnL, 1h/4h/12h/24h operation, or live execution.

## 3. Scope and evidence reviewed

### Committed source and tests

- `src/printer_v1/operator_cli/operational_memory_factory_command.py`
- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
- `src/printer_v1/operator_cli/origin_lifecycle_campaign.py`
- `src/printer_v1/operator_cli/one_command_15m_factory.py`
- `src/printer_v1/operator_cli/holder_reliability_budget_control.py`
- `src/printer_v1/operator_cli/campaign_full_run_accounting.py`
- `src/printer_v1/sources/campaign_six_unit_accounting.py`
- `src/printer_v1/sources/measured_transport.py`
- `src/printer_v1/sources/solana_rpc_holder.py`
- `tests/test_v2_9_8b_window_15m_freeze_holder_budget_decoupling_repair.py`
- `tests/test_v2_9_8b_window_15m_final_integrated_continuous_proof.py`

### Documentation and reported artifacts

- `docs/printer-v1-v2-9-8b-window-15m-freeze-holder-budget-decoupling-repair-design.md`
- `docs/printer-v1-v2-9-8b-window-15m-freeze-holder-budget-decoupling-repair-closeout.md`
- Reported retained proof directory:
  `/Users/Dtwo1/PrinterOperations/v2-9-8/final-integrated-proofs/V2_9_8B_WINDOW_15M_FINAL_INTEGRATED_CONTINUOUS_PROOF_V1_20260805T155633Z`
- Reported artifact hashes:
  - `proof_summary.json`:
    `df58a6f63cc89dbff6ee727f4a4560c48a4018c705b0f20cf79afa39d18deab9`
  - `wrapper_terminal.json`:
    `1742d605de65a00b387830108c7caa42f60ad8a281ae5c7ccf1e915102d310e0`

### Evidence-access limitation

The retained `/Users/Dtwo1/PrinterOperations/...` directory is outside this review
environment. Its files were not directly opened or independently rehashed here.

Therefore this audit distinguishes:

- facts proven by committed code;
- facts reported by the committed closeout;
- deterministic current-code defects;
- strongest inferences;
- historical details that remain unavailable.

No unavailable value is reconstructed from counts or guessed.

## 4. Proven historical proof facts

The committed closeout reports:

- one fixture authorization consumed once;
- one child invocation;
- child exit code `0`;
- zero automatic retries;
- zero manual reruns, resumes, restarts, or successors;
- zero external network escapes;
- four market/protocol-qualified candidates;
- exactly two token slots;
- zero active Scheduler jobs after cleanup;
- zero `WINDOW_15M` rows;
- zero current-run clean episodes;
- zero fingerprints;
- `operational_lifecycle_pass=false`;
- `clean_memory_outcome_pass=false`;
- terminal category `SAFE_STOP_PREFLIGHT_FAILED`;
- authoritative database identity unchanged.

The exact detailed lifecycle `blocked_reasons`, child terminal payload, orchestration
exception details, holder attempt trace, evaluated/unattempted arrays, and alternate
ordering were not retained in the available proof summary.

## 5. Static `SAFE_STOP_PREFLIGHT_FAILED` audit

`run_one_command_15m_factory()` returns `SAFE_STOP_PREFLIGHT_FAILED` whenever any
static preflight reason is present.

The active continuous proof reaches this factory only after the two-slot handoff.
The public owner calls the lifecycle driver with:

- `proof_mode=False`;
- `operational_persistent_mode=True`;
- `max_selected_tokens=2`;
- `WINDOW_15M`;
- no continuous 1h;
- no 4h;
- no selective 1h;
- a controlled `900`-second logical window;
- `total_duration_seconds=5000`.

### Static reason matrix

| Preflight family | Proof-path disposition | Audit result |
|---|---|---|
| Invalid Git provenance | Public preflight supplies validated launch provenance | Expected satisfied; detailed child reason not retained |
| Missing operator approval | Wrapper invokes `run --operator-approved` | Satisfied |
| Non-proof without operational persistent mode | Factory receives operational persistent mode | Satisfied |
| Proof and operational persistent both enabled | `proof_mode=False` | Satisfied |
| Invalid proof-only fault injection | No post-handoff fault injection | Not applicable |
| Unsupported window kind | `WINDOW_15M` | Satisfied |
| Missing target DB | Disposable DB exists and already contains handoff rows | Satisfied |
| Missing backup | Public coordinator creates backup before owner execution | Expected satisfied |
| Operational persistent DB differs from factory canonical DB | Public command is patched; factory canonical constant is not | **Deterministic failure** |
| Persistent DB used in proof mode | `proof_mode=False` | Not applicable |
| Invalid compressed two-token proof plan | No compressed plan | Not applicable |
| Operational-natural mode lacks persistent operation | Persistent mode enabled | Satisfied |
| Invalid selected-token count | Exactly two | Satisfied |
| Invalid discovery request ceiling | Existing default remains within 1–2 | Satisfied |
| Invalid continuous/4h combination | Continuous and 4h disabled | Not applicable |
| Invalid selective-1h combination | Selective 1h disabled | Not applicable |
| Invalid proof supervision target/state | No factory proof-supervision execution ID | Not applicable |
| Duration does not exceed lifecycle | `5000 > 900` | Satisfied |

### Immediate deterministic defect

The continuous proof patches:

`operational_memory_factory_command.AUTHORITATIVE_DB = disposable_db`

The lifecycle factory does not consume that public coordinator binding. In
operational-persistent mode it independently imports:

`proof_db_schema_readiness.CANONICAL_PERSISTENT_DB`

and rejects the actual path unless it equals that production canonical path.

The disposable proof DB is intentionally not the authoritative production corpus.
Therefore, under the committed code and harness, this check produces:

`operational persistent mode requires the authoritative corpus`

and the factory returns `SAFE_STOP_PREFLIGHT_FAILED` before creating a factory run
window.

This matches the observed boundary:

```text
two-slot handoff
-> lifecycle factory preflight
-> SAFE_STOP_PREFLIGHT_FAILED
-> zero WINDOW_15M rows
```

### Historical attribution limit

The historical proof summary did not retain `blocked_reasons`. The audit therefore
does not rewrite the old proof artifact as categorically proving this exact text.

Classification:

- **Deterministic current-code defect:** proven.
- **Strongest explanation of the historical first stop:** yes.
- **Retained categorical historical subreason:** unavailable.

## 6. Generic exception masking and evidence loss

Inside the lifecycle factory, unexpected orchestration exceptions are also collapsed
to the generic `SAFE_STOP_PREFLIGHT_FAILED` category and attached under an
`orchestration_error` field.

The continuous proof launcher then replaces the child stdout artifact with only:

```json
{"child_returncode": 0}
```

The retained proof summary records row counts and high-level wrapper state, but not the
complete child terminal result.

Consequences:

- a static preflight refusal and an orchestration exception are not distinguishable
  from retained proof evidence;
- the exact first subreason is lost;
- holder diagnostics cannot be independently reconciled;
- a later reviewer cannot prove whether the public command returned a safe stop or
  swallowed a secondary exception;
- rerunning becomes tempting even when a static inspection would suffice.

This is a proof-harness defect, not permission to rerun.

## 7. Holder request and transport ownership audit

### 7.1 Durable Source Governor truth

Holder collection uses the existing governed execution path. Each attempted source
operation creates a real durable `printer_source_requests` row and corresponding
response or failure evidence.

`persist_bundle_attempts()` preserves:

- exact durable source request IDs;
- source name and request kind;
- logical holder-stage coverage;
- terminal source status;
- normalized member count;
- numeric measured transport count;
- holder attempt evidence rows.

### 7.2 Holder operation ledger

`_evaluate_holder_eligibility()` increments the holder
`CampaignOperationLedger` with:

- `governed_request_count`;
- `measured_transport_count`.

It also returns:

- evaluated candidate mints;
- unattempted candidate mints;
- before/after ledgers;
- budget exhaustion state;
- request IDs and coverage;
- per-attempt budget trace.

The budget decoupling repair correctly preserves unknown context for unattempted
candidates and never represents unknown holder evidence as a pass.

### 7.3 Campaign request reconciliation

After holder evaluation, the permanent path adds holder request IDs and coverage to
the campaign diagnostics. The campaign request reconciler can therefore observe the
new durable governed request.

This explains the closeout's final governed request count increasing from `15` to
`16`.

### 7.4 Campaign six-unit owner

The campaign six-unit owner derives transport totals from exact
`TransportOperationIdentity` records ingested through sealed stage evidence.

Before holder collection, the public coordinator projects:

- campaign owner transport identities;
- independent action-local transport identities.

Both contain the same pre-holder set.

Holder evaluation does not call the campaign stage evidence sink with a holder-stage
ledger. Therefore the campaign owner receives no exact holder transport identity.

### 7.5 Independent action-local ledger

The action-local ledger receives transport identities through the public
`_observe_transport_identity()` callback at measurement time.

That callback is wired into the graduated-supply path. It is not wired into the
holder GoPlus/RPC transport builders used by `_collect_preclose_context()` during
holder eligibility.

Therefore the independent action-local ledger also receives no holder transport
identity.

### 7.6 Holder normalized payload limitation

Current holder adapters and proof fixtures expose numeric fields such as:

- `underlying_operation_count=1` for GoPlus;
- `underlying_operation_count=1` or `2` for Solana RPC.

The committed holder persistence layer accepts those numeric counts as measured
budget evidence.

A numeric count is not sufficient to create campaign six-unit identity evidence.
The required identity fields include the exact:

- stage;
- source;
- endpoint owner;
- governed request kind;
- method or endpoint;
- within-request ordinal;
- target category and identity;
- response bytes;
- normalized rows;
- result.

Those values must originate at the actual transport boundary. They must not be
invented later from a row count.

### 7.7 Exact propagation break

The exact break is:

```text
real governed holder execution
-> durable Source Governor request/response/failure
-> numeric holder measured count
-> holder operation ledger and diagnostics
-> campaign request manifest advances
X no exact TransportOperationIdentity fan-out
X no HOLDER_SAFETY sealed campaign stage
X no action-local holder transport observation
```

This is a deterministic committed integration defect.

### 7.8 Historical relationship to the blocker

The closeout reported:

- final campaign governed source calls: `16`;
- campaign six-unit source transports: `17`;
- pre-holder campaign six-unit source transports: `17`.

This is consistent with one holder request whose transport identity never entered the
campaign owner.

However, because the lifecycle factory already has the deterministic disposable-DB
preflight mismatch, missing holder identity propagation is not established as the
first historical cause of `SAFE_STOP_PREFLIGHT_FAILED`.

It remains a real next blocker that must be repaired before a valid full-run
accounting PASS.

## 8. What the previous lane successfully improved

The committed repair correctly:

- separates governed requests from measured transport operations;
- charges measured operations rather than request count;
- preserves the operation ceiling `45`;
- preserves zero-transport charge `9`;
- preserves reservations `2 + 4`;
- preserves the five-operation holder pre-attempt rule;
- preserves the permanent holder-stage ceiling `8`;
- stops additional holder requests cleanly when budget is insufficient;
- preserves all four memory-observation candidates;
- gives unattempted candidates exact unknown, future-action-blocked context;
- allows only actual holder passes to become `FULLY_ELIGIBLE`;
- reaches the two-slot handoff.

These changes should remain. The successor design must not undo or bypass them.

## 9. Root-cause classification

| Finding | Classification | Confidence |
|---|---|---:|
| Two slots and zero windows | Proven historical fact | Exact |
| Generic `SAFE_STOP_PREFLIGHT_FAILED` | Proven historical fact | Exact |
| Disposable DB differs from factory canonical persistent DB | Deterministic current-code defect | Exact |
| That mismatch is sufficient to stop before a window | Deterministic code-path result | Exact |
| It was the exact retained historical subreason | Strongest inference, not retained | High |
| Holder request advanced durable request count | Reported historical fact | High |
| Holder exact identities do not reach campaign owner | Deterministic current-code defect | Exact |
| Holder exact identities do not reach action-local observer | Deterministic current-code defect | Exact |
| Missing holder identity was the first historical stop | Not proven | Unavailable |
| Exact holder attempt trace and alternate order | Not retained in available evidence | Unavailable |

## 10. Readiness decision

A successor implementation lane is justified, but it must contain three coordinated
repairs:

1. authorization-bound operational DB target propagation;
2. exact holder transport identity propagation through existing accounting owners;
3. complete child/proof terminal evidence retention.

Fixing only the DB check would expose the holder-accounting blocker.

Fixing only holder accounting would still leave the disposable proof unable to enter
the lifecycle.

Fixing both without proof retention would make the next one-shot failure difficult to
audit again.

## 11. Minimum proof required after a later implementation

No proof is authorized by this audit.

A later implementation must first pass focused tests proving:

- production canonical DB strictness remains;
- an exact wrapper-authorized disposable DB can exercise production semantics;
- arbitrary DB paths remain rejected;
- campaign/run/cycle/configuration bindings cannot drift;
- holder HTTP/RPC calls emit exact transport identities;
- exact identities reach campaign and action-local owners once each;
- holder request, identity, bytes, rows, and terminal results reconcile;
- clean pre-request budget exhaustion performs zero source work;
- missing identity evidence remains blocking;
- proof artifacts retain all terminal and holder diagnostics.

Only after focused tests, directly affected regressions, compilation, diff checks, and
the required pre-proof broad suite pass may a separately authorized single continuous
proof be considered.

## 12. Money-usefulness contribution

This audit protects money-usefulness by preventing false operational readiness.

A memory factory that reaches two slots but cannot prove its DB target or source
accounting could create apparently clean memories with untrustworthy provenance. This
audit identifies the boundaries that must be exact before Printer can safely grow its
paper-only learning corpus.

It also preserves the useful outcome of the prior repair: holder budget may reduce
context completeness, but it must not erase valid market observations.

## 13. What this lane improves

- Establishes the most likely immediate post-handoff stop.
- Separates the DB-binding defect from the holder-accounting defect.
- Identifies the exact holder identity propagation break.
- Identifies why the proof cannot currently support a categorical subreason.
- Defines the minimum coordinated successor scope.

## 14. What this lane still does not unlock

- no implementation;
- no proof rerun;
- no real authorization;
- no provider contact;
- no authoritative database mutation;
- no new memory window;
- no retrieval;
- no paper decisions;
- no BUY/SELL/HOLD;
- no paper positions;
- no trade events;
- no paper audits;
- no PnL;
- no 1h/4h/12h/24h activation;
- no wallet, private key, signing, funds, or live execution.

## 15. Functionality Risks / Setbacks / Efficiency Blockers

### Functionality risks

- Accepting a disposable DB through a loose parameter could weaken production DB
  isolation.
- Reconstructing holder identities from numeric counts would create fake accounting
  equality.
- Sealing holder evidence twice could double-count transports.
- Adding holder stage evidence without conditional stage rules could reject clean
  zero-request budget exhaustion.
- Treating holder source failure as an accounting failure could incorrectly erase
  useful memory observations.

### Setbacks

- The previous one-shot proof authorization was consumed without reaching a window.
- The retained artifacts are insufficient to prove the exact static subreason.
- No clean memory outcome was produced by the continuous proof.
- Holder-stage exact identity architecture is still incomplete.

### Efficiency blockers

- The continuous proof is expensive and one-shot.
- The current harness discards the most useful child diagnostics.
- Another proof before focused repair would likely expose one blocker at a time.
- The authoritative database cannot be used to diagnose a disposable proof-path
  binding defect.

## 16. Stop condition

Stop after this audit and its paired design.

Do not implement, test, authorize, or rerun until the operator separately approves the
implementation lane.
