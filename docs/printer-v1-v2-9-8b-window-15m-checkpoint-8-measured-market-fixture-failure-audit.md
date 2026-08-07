# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — Measured Market Fixture Failure Audit

Date: 2026-08-07

Consumed proof:
- authorized HEAD: `aa0499bb60783b789b6f3bf436735ab2f4b7a3e8`
- Actions run: `31194214360`
- proof ID: `C8_REPROOF_AFTER_POLICY_OVERLAY_REPAIR_20260807`
- artifact: `checkpoint8-post-policy-overlay-reproof-aa0499bb`
- artifact ID: `9000089457`
- artifact SHA-256: `7a79a5a4e903ca5ce87ad457c409bc25f066904e6fa000d0664917ba50230a4d`

## Verdict

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_MEASURED_MARKET_FIXTURE_IDENTITY_DEFECT_CONFIRMED`

The one-shot authorization is consumed. The proof must not be rerun, resumed, restarted, or succeeded by another attempt without a new explicit authorization.

## Frozen evidence

The post-policy-overlay proof reached the canonical permanent DexScreener fresh-profile locator. The disposable database contains exactly one governed `dexscreener_fresh_profiles` request and one clean response with two normalized Solana PumpSwap pairs.

The normalized payload also contains:
- `transport_operations_used = 1`
- `transport_operation_identities = []`

Canonical `record_payload_transports()` therefore raises `TRANSPORT_IDENTITIES_MISSING`. The locator correctly blocks measured accounting, but its stage has started. Six-unit sealing then fails closed with:

`SIX_UNIT_STAGE_EVIDENCE_MALFORMED:EMPTY_STARTED_STAGE_EVIDENCE`

The independent success inspector was not invoked.

## Same-class fixture audit

The defect is not production discovery behavior. It is a C8 fixture metadata defect on permanent market-source ports whose canonical consumers explicitly rehydrate measured transport identities from normalized payloads.

Four C8 fixture seams require the same measured-payload contract:

1. DexScreener fresh-profile locator — stage `DEXSCREENER_DISCOVERY`.
2. DexScreener mint-batch resolution — stage `MINT_MARKET_BATCH`.
3. GeckoTerminal fresh nomination — stage `FRESH_POOL_NOMINATION`.
4. GeckoTerminal mint reconciliation fallback — stage `MINT_MARKET_BATCH`.

The current C8 Dex/Gecko payload helpers claim one transport operation but do not serialize the corresponding identity for these routes. Repairing only the first failing route would leave the same defect latent in later permanent-market stages.

## Production assessment

No production source, discovery, Scheduler, Source Governor, accounting, selection, lifecycle, or memory owner is shown defective by this evidence. Their fail-closed behavior is correct.

## Money-usefulness contribution

Fixing this proof seam allows Checkpoint 8 to test the real permanent market-source pipeline with trustworthy per-call accounting instead of dying on synthetic fixture metadata.

## What this lane improves

It restores C8 fixture fidelity for measured market-source operations while preserving the canonical production owners and their fail-closed accounting rules.

## What remains locked

Checkpoint 8 is incomplete. No new controlling proof, `WINDOW_1H+`, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL are unlocked.

## Proof/test needed before completion

Offline repair must prove each of the four measured market fixture seams exposes exactly one valid transport identity through the real adapter normalization boundary, plus the focused Checkpoint 8 suite must remain green. A later controlling proof still requires a new explicit authorization.

## Functionality Risks / Setbacks / Efficiency Blockers

- A later independent seam may still appear because Checkpoint 8 has not yet completed end to end.
- Identity metadata must describe only actual fixture transport work; no synthetic extra operations may be invented.
- Repair must stay proof-fixture-only and must not weaken canonical accounting to tolerate missing identities.
