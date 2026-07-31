# Printer V1 V2-9.8B Accounting and Exact-Identity Report-Only Repair Closeout

Date: 2026-07-31

Lane: `V2-9.8B First Authoritative WINDOW_15M Accounting and Exact-Identity Report-Only Repair`

Branch:
`codex/v2-9-8b-accounting-report-only-repair`

Reviewed HEAD:
`0118a37e32929501c45f97ea9353b799b29fef7b`

Design baseline:
`e71e543d197154eba427b41e2e01574a59f527f5`

Implementation commits:

| Commit | Summary |
| --- | --- |
| `b168c57` | Repair 15m accounting and exact report replay |
| `fd35b41` | Close accounting and exact replay review gaps |
| `0118a37` | Add independent transport verification and real coordinator proofs |

Implementation verdict:
`V2_9_8B_FIRST_AUTHORITATIVE_15M_ACCOUNTING_EXACT_IDENTITY_REPORT_ONLY_REPAIR_IMPLEMENTATION_PASS`

Operator-review verdict:
`V2_9_8B_FIRST_AUTHORITATIVE_15M_ACCOUNTING_EXACT_IDENTITY_REPORT_ONLY_REPAIR_OPERATOR_REVIEW_PASS`

Closeout verdict:
`V2_9_8B_FIRST_AUTHORITATIVE_15M_ACCOUNTING_EXACT_IDENTITY_REPORT_ONLY_REPAIR_CLOSEOUT_PASS`

## 1. Boundary

This closeout is documentation-only. It records the completed repair, the
operator-review PASS, and the exact next permitted roadmap lane.

It does not:

- modify runtime code or tests;
- mutate the authoritative database;
- backfill or reclassify the July 31 attempt;
- call providers, RPC, or WebSockets;
- run a campaign, recovery, N2, N7, cursor reset, or memory generation;
- unlock retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits,
  or PnL.

The permanent no-rerun marker for execution
`20260731T002406Z-7612696c7295` remains valid.

## 2. What Was Closed

### Independent pre-seal transport observer

`MeasuredTransportLedger.on_transport_recorded` fires after each accepted
transport is recorded and before stage sealing. The public coordinator supplies
one verification-only observer that appends exact action-local transport
identities. This is not a second campaign accounting authority and does not
reconstruct missing stage evidence from SQLite rows.

### Exact owner / action-local identity reconciliation

Pre-lifecycle completion requires exact identity-set equality both directions
between the single `CampaignSixUnitOwner` and independently observed
action-local transport identities. Count-only surfaces remain blocked with
`ACTION_LOCAL_TRANSPORT_IDENTITY_DESIGN_BLOCKED`. Mismatch fails closed with
accounting blocked and no synthetic evidence manufacture.

### Exception-safe stage sealing

Direct migration, locator, and each exact-liquidity round seal and ingest
exactly once on a `try/except/finally` path before a bounded or unexpected
exception escapes. First-cause precedence is preserved when sink ingestion
fails after a market/source terminal cause.

### Exact-identity report-only behavior

Public `report-only` resolves exact campaign/run identity and does not fall
back to the globally newest terminal report. Missing exact report with valid
exact summary returns `EXACT_TERMINAL_REPORT_MISSING`. Missing or mismatched
summary returns `EXACT_TERMINAL_SUMMARY_MISSING_OR_MISMATCHED`. Replay remains
zero-source, zero-Scheduler, and zero-write.

### Genuine disposable 30-operation shortage proof

A disposable coordinator path exercises the real operational stage graph,
campaign evidence sink, independent measurement observer, completion gate, and
canonical report builder/writer. It requires 30 independently observed
transport identities, exact owner equality, terminal
`SOURCE_VISIBILITY_SHORTAGE`, one report row and artifact, reconstructable
totals, and zero lifecycle/memory/retrieval/decision/position/trade/audit/PnL
deltas.

### Genuine two-token `WINDOW_15M` regression

A frozen disposable ordinary two-token operational coordinator path reaches and
closes two `WINDOW_15M` windows (`fifteen_minute_only=True`) without providers
or the authoritative database.

## 3. Proof Evidence

| Check | Result |
| --- | --- |
| Focused repair suite | 31 passed |
| Combined focused affected suites | 103 passed |
| Authoritative DB SHA-256 before | `f36f3b3fd7c389018323c219b3ce9421e2006769de3db860593ce4b31415a511` |
| Authoritative DB SHA-256 after | `f36f3b3fd7c389018323c219b3ce9421e2006769de3db860593ce4b31415a511` (unchanged) |
| Schema migration | none |
| Providers / authoritative campaign | not run |

## 4. Money-Usefulness Contribution

Printer can now preserve honest negative learning about source-visibility
shortage only when stage evidence is complete and independently reconcilable.
Operators can no longer mistake sealed-stage self-comparison for independent
verification, and cannot treat an unrelated historical terminal report as the
current attempt.

The historical July 31 attempt remains
`V2_9_8B_FIRST_AUTHORITATIVE_15M_CAMPAIGN_BLOCKED_UNSAFE` and is not backfilled.

## 5. What Remains Locked

- clean-memory creation and retrieval activation
- paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL
- live wallets, private keys, signing, real funds, live execution
- paid APIs, scoring, ranking, confidence, weighting, embeddings/vectors
- `WINDOW_1H` / longer production activation
- historical July 31 report backfill or reclassification
- campaign rerun of the permanent no-rerun marker attempt
- candidate-acquisition N2/N7, cursor recovery, automatic retry/restart/successor
- another authoritative campaign without a fresh readiness/design/authorization
  sequence

## 6. Functionality Risks / Setbacks / Efficiency Blockers

- Stages that measure transports without the coordinator observer under-count
  action-local identities and fail closed at the completion gate.
- Fixture transports that omit declared identities still fail closed under exact
  equality.
- Holder/lifecycle stages after lifecycle start are not forced into the
  pre-lifecycle identity gate; later lanes may need explicit sealed stages if
  full-run equality is required.
- Cross-cutting accounting and report-only changes used focused suites only; the
  broader repository suite was intentionally not expanded.

## 7. Exact Next Permitted Lane

```text
V2-9.8B Post-Accounting-Repair Authoritative WINDOW_15M Campaign Readiness Audit
```

Type: audit/readiness only.

Allowed:

- static inspection of the repaired ordinary command, accounting, and exact-
  identity report-only surface;
- read-only inspection of the authoritative database identity, migration head,
  integrity expectations, permanent no-rerun marker, and residual campaign state;
- verification that the exact non-placeholder operator command and environment-
  variable names remain valid after the repair;
- readiness documentation and a factual PASS/BLOCKED verdict.

Not allowed:

- providers, RPC, WebSockets, or source fetching;
- authoritative database mutation;
- campaign, recovery, N2, N7, cursor reset, or memory generation;
- July 31 report repair or reclassification;
- retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL;
- V2-10 or longer-window activation.

A readiness PASS may authorize only the next approved design/specification or
final-authorization step. It does not directly authorize campaign execution.
