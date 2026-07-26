# Printer V1 — V2-9.7E.48 Holder-Condition / Memory-Quality Separation Closeout

**Verdict: `V2_9_7E_48_HOLDER_CONDITION_MEMORY_QUALITY_SEPARATION_PASS`.**

- Starting commit: `b66a40df195964ff8473ab0af571a3afa784bc47`
- Mode: source-grounded audit, frozen design, narrow repair, bounded offline
  proof and retained-evidence reconciliation
- External source calls: none
- Retained original: read-only/copy-only
- Next lane: `V2-9.7F — Activation Readiness Review` (not started)

## Audit findings and blocker classification

The active source stack supports one consistent rule: memory quality measures
whether an episode is trustworthy enough to learn from; holder condition
describes market-integrity risk. Safety/favourability/profitability must not be
used as proxies for evidence quality.

The Python Builder Guide investigation classified the blocker as
`COMMITTED_CODE_DEFECT`:

1. `safety_memory_policy_summary` made concentrated, extreme and unknown holder
   states hard 15m-memory blockers.
2. safety composites promoted holder-source conflict and holder-only absence
   into blocked/conflicting memory evidence.
3. the shared 15m resolver inherited those blockers and dirtied otherwise
   complete windows.
4. holder percentages and measurement limitations were discarded.
5. a Helius contribution was stored under its real contribution source but
   bound in `field_bindings_json` as `solana_rpc`.

The retained database confirmed the production consequence. Both closed 15m
memories had truthful `DEAD` outcomes, complete main-window evidence and
entry/exit realism. Both were dirty solely because
`holder_concentration_label = HOLDER_CONCENTRATION_EXTREME` was the remaining
hard safety/memory blocker.

## Frozen design

Four concerns remain separate:

| Concern | Meaning | Holder-condition effect |
|---|---|---|
| Evidence quality | identity, cadence/duration, required snapshots, freshness, core source provenance, outcome and entry/exit realism | no holder state independently dirties memory |
| Market integrity | healthy, concentrated, extreme, unknown, unavailable or conflicting condition, with source, percentage and limitations | always retained descriptively |
| Action eligibility | future clean-memory-backed paper-action policy | remains locked; this lane neither allows nor forbids an action from holder condition alone |
| Capability locks | retrieval, BUY/SELL/HOLD, positions, trades, audits and PnL | all remain locked |

`UNKNOWN` is never relabelled healthy. Wrong target, cross-token contamination
and invalid source trace remain evidence-quality/provenance blockers. Stale,
failed or unavailable holder evidence remains a visible limitation but does not
independently dirty otherwise trustworthy episode evidence.

The existing categorical thresholds remain unchanged:

- below 55%: `HOLDER_CONCENTRATION_HEALTHY`
- 55% through below 80%: `HOLDER_CONCENTRATION_CONCENTRATED`
- 80% or more: `HOLDER_CONCENTRATION_EXTREME`

Top-ten measurements retain an explicit limitation: Solana
`getTokenLargestAccounts` returns token accounts, not proven beneficial owners.
Related wallets are not clustered, and pool/vault/burn/program-controlled
accounts are not identified or excluded by the current free-source adapters.

## Implementation

- GoPlus and Solana RPC normalization now preserve the top-ten percentage,
  measurement basis, categorical label, reason and limitations.
- Composite contributions preserve that evidence and bind the holder field to
  the actual contribution source, including `helius_free`.
- Healthy, concentrated, extreme, unknown, unavailable and conflicting holder
  states stay descriptive and cannot independently create a memory blocker.
- Holder target mismatch and invalid trace remain explicit fail-closed
  provenance blockers.
- The 15m shared resolver accepts legacy holder-only blocked/conflicting
  composites while retaining their historical labels and risks.
- operator reporting distinguishes optional holder/context coverage from
  mandatory evidence gaps.
- missing outcome evidence was confirmed as a negative-control defect during
  proof and now remains `OUTCOME_UNKNOWN` with
  `MISSING_REQUIRED_OUTCOME_EVIDENCE`; it cannot be normalized into a clean
  `NO_PUMP` memory.

No source endpoint, threshold, Scheduler path, Source Governor path, cadence,
continuation rule or locked capability was expanded.

## Retained-memory reconciliation

Retained original:
`/Users/Dtwo1/PrinterPilot/E47FULL/e47-full-20260725-7df7ac0/attempt.sqlite3`

- original SHA-256 before and after:
  `362c87da87c971a998595b5c778e9ef9a0eaddc2f09f6586df423f83ead03c3d`
- disposable copy began byte-identical
- no source calls were made

The repaired classifier was applied to each row's recorded snapshot ledger,
recorded context identities, recorded outcome and current exact-target safety
and realism evidence:

| Memory | Before | After on disposable copy | Holder condition |
|---|---|---|---|
| 1 | `DEAD`, `DIRTY_MEMORY`, `MISSING_CRITICAL_DATA`, `do_not_train=1` | `DEAD`, `CLEAN_MEMORY`, `CLEAN_DATA`, `do_not_train=0` | `HOLDER_CONCENTRATION_EXTREME` retained |
| 2 | `DEAD`, `DIRTY_MEMORY`, `MISSING_CRITICAL_DATA`, `do_not_train=1` | `DEAD`, `CLEAN_MEMORY`, `CLEAN_DATA`, `do_not_train=0` | `HOLDER_CONCENTRATION_EXTREME` retained |

Both reconciliations had zero remaining blockers. SQLite
`integrity_check = ok`, `foreign_key_check = 0`. Deltas were zero for retrieval
queries/matches, paper decisions, positions, trade events, decision audits,
trade audits and paper audit reports.

The retained original was not rewritten.

## Focused proof

The lane proof covers:

- all six holder states becoming clean only when the independent evidence
  contract is complete;
- truthful adverse outcome persistence and `do_not_train = 0`;
- percentage, source, basis, reason and limitation persistence;
- Helius source binding;
- explicit token-account/beneficial-owner limitations;
- wrong identity, incomplete duration, missing snapshots, stale core evidence,
  invalid provenance, missing outcome and missing entry/exit realism remaining
  non-clean;
- holder target mismatch and invalid trace remaining fail-closed;
- zero retrieval or financial capability deltas.

Focused adjacent contracts and the E.47 lifecycle/memory regression remain
passing. Changed Python files compile and `git diff --check` is clean.

## Money-usefulness contribution

Printer can now learn the truthful fact that an extreme-concentration token died
without corrupting evidence quality into a safety opinion. The holder condition
remains available for later comparison and risk review, while trustworthy bad
outcomes can enter clean historical memory. This improves the corpus without
claiming the token was safe, favourable, buyable or profitable.

## Functionality Risks / Setbacks / Efficiency Blockers

- Top-ten token-account concentration is not beneficial-owner concentration.
  Pool/vault/burn/program accounts and related-wallet clusters remain unresolved
  by the current free-source evidence.
- Historical retained composites keep their historical Helius binding text;
  new composites bind correctly. The disposable reconciliation does not rewrite
  historical provenance records.
- Holder evidence remains partial wallet-level flow context. It is descriptive,
  not a standalone action signal.
- No live report-only replay was added or run in this offline lane.

## Locks and next lane

Retrieval, paper decisions, BUY/SELL/HOLD, paper positions, trade events, paper
audits, PnL, live execution, wallets/private keys, paid APIs, scoring/ranking,
confidence/weighted logic and vectors/embeddings remain locked.

V2-9.7E.48 is closed PASS. The next recommended lane is
`V2-9.7F — Activation Readiness Review`. It was not started here.
