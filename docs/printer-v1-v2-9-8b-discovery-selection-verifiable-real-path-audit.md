# Printer V1 V2-9.8B Discovery and Selection Verifiable Real-Path Audit

Date: 2026-07-30

Lane: `V2-9.8B Discovery and Selection Verifiable Real-Path Completion`

Status: `AUDIT_COMPLETE`

## Baseline

- Branch: `master`
- HEAD: `8434c57d337c91a18d7f1c29c876681f0cf526bb`
- Prior full-system closeout treated as operator-review **BLOCKED**
- Authoritative DB SHA-256:
  `e748ba505cb8c7d67b8feb3a09b97719a0f3560e41dfb9242570cff3157962e6`
- Migration head: `049`

## Required outcome gaps reconfirmed

| # | Requirement | Pre-repair defect |
|---|---|---|
| 1 | Identity for every success/fail HTTP/RPC | DexScreener early HTTP/rate-limit paths omitted identities |
| 2 | Preserve earlier identities on later failure | Partial multi-call paths incomplete on DexScreener step-1 fails |
| 3 | Fail closed before candidate persistence | `record_graduated_candidate` ran before identity totals reconcile |
| 4 | Campaign-wide six-unit owner | No single owner across discovery/Dex/holder/scheduler/bytes/rows/reservations |
| 5 | Durable evidence for independent reconstruction | Only derived totals stored; no evidence block |
| 6 | Report vs reconstruction (not self-compare) | Replay compared six_unit_totals to itself |
| 7 | Real injected activation/lifecycle proofs | Prior suite used source-text inspection for savepoints |
| 8 | Accurate elapsed-duration reporting | Discovery/report lacked wall-clock elapsed |
| 9 | No synthetic/source-text-only runtime proofs | Activation and report equality used inspect/artifact shortcuts |

## Classification

```text
BLOCKER CLASSIFICATION:
INCOMPLETE_WIRING + PROOF_GAP + ACCOUNTING_ORDERING

CODE CHANGE JUSTIFIED: YES
```

## Exact next task after audit

Final design → complete repair → frozen offline proof → corrected closeout.
