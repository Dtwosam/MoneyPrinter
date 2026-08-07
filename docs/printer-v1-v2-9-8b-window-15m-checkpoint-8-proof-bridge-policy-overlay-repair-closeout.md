# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — Proof-Bridge Policy Overlay Repair Closeout

Date: 2026-08-07

## Verdict

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_PROOF_BRIDGE_POLICY_OVERLAY_OFFLINE_REPAIR_PASS_NO_REPROOF_AUTHORIZATION`

## Evidence lineage

- Consumed failed proof HEAD: `6792fca5bf8a437e5e73c55d4e3ea837d2c06c7b`
- Consumed Actions run: `31192953880`
- Frozen artifact SHA-256: `fe2a81451851bc60f79cca5923f38d240f9003f7e7c7b34b904f8e208e5e5c6c`
- Audit commit: `16ffc7100199efd2881ca9e1e434e847dac814f6`
- Design commit: `2b85d4c8b3b77498fb6dde45a9c60300616f35aa`
- Implementation commit: `cd7762d8f39544ac8d3693e8bbf4029b00c08928`
- Offline verification Actions run: `31193563004`

## Implemented repair

The disposable C8 owner bridge now preserves the canonical `OPERATIONAL_GRADUATED_SUPPLY_KWARGS` policy and overlays only deterministic fixture dependency kwargs.

A fail-closed collision guard rejects any disposable fixture attempt to replace an operational policy key.

The repair therefore keeps `permanent_availability=True`, `run_locator=True`, `run_geckoterminal_nomination=True`, and the rest of the canonical operational supply policy while retaining the existing C8 fixture transports.

No `src/printer_v1/discovery/*` file changed.

## Verification

Actions run `31193563004` passed:

- changed production command compile: PASS;
- focused compatibility test compile: PASS;
- C8 real-consumer compatibility: 5/5 PASS;
- full focused `tests/test_v2_9_8b_window_15m_checkpoint8_*.py`: 96/96 PASS;
- `git diff --check`: PASS;
- narrow-diff guard: PASS;
- discovery-module change count: zero.

The new regression proves the disposable bridge retains every canonical operational graduated-supply policy value, preserves the fixture dependency objects, and fails closed if a fixture tries to override `permanent_availability`.

## Money-usefulness contribution

Checkpoint 8 can now test the actual permanent operational candidate-supply path intended to feed clean `WINDOW_15M` memories. This makes a later pass evidence about Printer's real operational composition rather than a proof-only legacy route.

## What this lane improved

- restored operational-policy parity under the disposable proof capability;
- prevented accidental fallback into non-permanent exact-pair source behavior;
- preserved deterministic zero-provider fixture injection;
- added a fail-closed policy-collision guard.

## What remains locked

Checkpoint 8 itself remains incomplete until a later newly authorized controlling re-proof passes and independent read-only inspection passes.

No `WINDOW_1H+`, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL are unlocked.

## Proof/test needed before Checkpoint 8 completion

A later explicit operator authorization must permit exactly one fresh ordinary `WINDOW_15M` controlling re-proof on the post-closeout readiness HEAD. The runner must preserve frozen evidence and invoke independent success inspection only after the frozen summary proves both `campaign_pass == true` and `campaign_acceptance_verdict == CAMPAIGN_PASS`.

## Functionality Risks / Setbacks / Efficiency Blockers

- A later one-shot proof may expose a different downstream seam; such a result must be preserved, not retried.
- The consumed run `31192953880` remains historical failed evidence and cannot be reused.
- Offline verification does not itself complete Checkpoint 8 or authorize runtime proof.

## Stop condition

DTW-44 implementation and offline verification are complete. Stop before any new controlling proof and make a separate readiness/authorization decision.