# Printer V1 V2-9.8B Discovery and Selection Full-System Re-Audit

Date: 2026-07-30

Lane: `V2-9.8B Discovery and Selection Full-System Re-Audit and Consolidation`

Status: `REAUDIT_COMPLETE_FOR_FINAL_CONSOLIDATION`

## Baseline

- Branch: `master`
- Required HEAD: `d21d7c82dbd98fc1e86637f871fdb190176fdec8`
- Prior closeout treated as **unaccepted**:
  `V2_9_8B_DISCOVERY_SELECTION_AUTHORITY_CONSOLIDATION_OPERATOR_REVIEW_BLOCKED`
- Authoritative DB SHA-256:
  `e748ba505cb8c7d67b8feb3a09b97719a0f3560e41dfb9242570cff3157962e6`
- Migration head: `049`

## Ordinary public `run` path (re-traced)

```text
preflight (typed prohibitions + resolved Solana endpoint)
  -> direct Pump nomination (1 signature page + <=12 txs)
  -> 25-role migrate validation + PumpSwap verification
  -> graduated registry
  -> DexScreener fresh profiles + exact-pair liquidity
  -> holder/safety funnel (shared Solana endpoint)
  -> cooldown / floor / eligibility
  -> selection_authority.select_two_candidates
  -> atomic two-slot activation + first WINDOW_15M jobs
  -> terminal report (six units)
  -> zero-source report-only replay
  -> safe stop
```

## Reconfirmed BLOCKED findings (operator review)

| # | Gap | Severity | Reconfirmed |
|---|---|---|---|
| 1 | Measured transport identities helper-only | BLOCKER | Yes — ledger unused outside helper module |
| 2 | Response bytes / normalized rows incomplete | BLOCKER | Yes — graduation verifier `response_bytes = 0` |
| 3 | DexScreener row ceilings not at call sites | BLOCKER | Yes — enforce helper never imported by adapters |
| 4 | Six-unit absent from terminal report | BLOCKER | Yes — only `campaign_source_calls` |
| 5 | Replay does not reconstruct six units | BLOCKER | Yes |
| 6 | Valid-but-wrong relationships pass (`withdraw_authority`) | BLOCKER | Yes — random valid pubkey accepted |
| 7 | Activation/lifecycle compensation under-proved | HIGH | Yes — savepoint exists; lane proof insufficient |
| 8 | Dormant latest/persisted product fields | HIGH | Yes — `selected_latest` / `selected_persisted` product |
| 9 | Vacuous composition assert (`or True`) | MED | Yes |
| 10 | Direct-migration count-only reconcile | HIGH | Yes — not full six-unit contract |

## Additional defects found in re-audit

| # | Defect | Severity |
|---|---|---|
| A | Offline verifier claimed transport ops without identities | HIGH |
| B | Direct-Pump failure normalize omitted transport identities | HIGH |
| C | PumpSwap `_rpc_post` did not measure/return response bytes | HIGH |
| D | GraduatedSupply product still exported latest/persisted readiness fields | HIGH |
| E | Shared DexScreener normalizer did not bound multi-row pair arrays | HIGH |
| F | Prior closeout claimed PASS while helper-only surfaces remained | HIGH (process) |

## Active / dormant / deferred owner map (pre-repair)

| Owner | State |
|---|---|
| `selection_authority.select_two_candidates` | Active |
| Direct Pump + graduation verifier | Active |
| `MeasuredTransportLedger` | Dormant helper |
| `select_holder_eligible_pair` | Dormant latest/persisted selector |
| PumpPortal ordinary runtime | Deferred |
| Candidate-acquisition N2/N7/cursors/recovery | Deferred |

## Mandatory classification

```text
BLOCKER CLASSIFICATION:
CONTRACT_DRIFT + DESIGN_GAP + INCOMPLETE_WIRING

CODE CHANGE JUSTIFIED:
YES — full-system consolidation of the ordinary discovery/selection surface.

MINIMUM SAFE RESPONSE:
Wire measured identities, six-unit report/replay, complete role relations,
DexScreener ceilings, neutral two-candidate product, and fail-closed paths
with frozen offline proof only.
```

## Exact next task after re-audit

Final consolidation design → complete implementation → frozen offline proof →
corrected closeout. No live probe. No campaign.
