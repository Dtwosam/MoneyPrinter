# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — Proof-Bridge Policy Overlay Failure Audit

Date: 2026-08-07

Consumed proof HEAD: `6792fca5bf8a437e5e73c55d4e3ea837d2c06c7b`

Actions run: `31192953880`

Proof ID: `C8_REPROOF_AFTER_SOURCE_VISIBILITY_FIXTURE_ACCOUNTING_REPAIR_20260807`

Frozen artifact: `checkpoint8-source-visibility-reproof-6792fca5`

Artifact ID: `8999582778`

Artifact SHA-256: `fe2a81451851bc60f79cca5923f38d240f9003f7e7c7b34b904f8e208e5e5c6c`

## Verdict

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_PROOF_BRIDGE_POLICY_OVERLAY_DEFECT_CONFIRMED`

The one-shot authorization is consumed. No rerun, resume, restart, or successor is permitted from it.

## Frozen evidence

The repaired direct-migration stage now behaves correctly:

- `DIRECT_MIGRATION` sealed `COMPLETED`;
- 7 measured source transport identities were owned by the stage;
- 2 local `PUMPSWAP_GRADUATION_VERIFIED` validations were sealed;
- 2 graduated candidates were persisted;
- DB integrity was `ok` and foreign-key violations were zero.

The failure occurred afterward in `EXACT_LIQUIDITY`:

- two DexScreener `pair_market_snapshot` governed requests were created;
- both attempted the live transport and were stopped by `CHECKPOINT8_EXTERNAL_NETWORK_ATTEMPT_FORBIDDEN`;
- no measured transport identity entered the liquidity-stage ledger;
- the stage was nevertheless marked started because candidate evaluation began;
- sealing correctly failed closed with `SIX_UNIT_STAGE_EVIDENCE_MALFORMED:EMPTY_STARTED_STAGE_EVIDENCE`.

The independent success inspector was not invoked.

All memory, retrieval, decision, position, trade, audit, PnL, Scheduler-work, lifecycle-window, and factory-run protected surfaces remained at zero.

## Root cause

The disposable proof owner bridge changes the normal operational composition incorrectly.

Normal `WINDOW_15M` execution starts graduated supply with `OPERATIONAL_GRADUATED_SUPPLY_KWARGS`, which includes the permanent operational discovery policy such as `permanent_availability=True` and its governed batch-market path.

When a disposable C8 owner bridge is present, `operational_memory_factory_command.py` currently replaces those canonical policy kwargs with `owner_bridge.graduated_supply_kwargs`, which contains only fixture dependency overrides.

That replacement drops the operational policy. The proof therefore enters the non-permanent exact-pair front-door path, which is not the canonical operational route and has no C8 exact-pair transport injection. The network tripwire then catches the unintended provider attempt.

This is a proof-bridge composition defect, not evidence that production discovery is broken.

## Correct repair boundary

Preserve `OPERATIONAL_GRADUATED_SUPPLY_KWARGS` as the canonical operational policy owner and overlay the disposable proof's fixture dependency kwargs on top.

Do not:

- add a parallel discovery path;
- invent an extra source route solely for the proof;
- weaken Source Governor, Scheduler, accounting, or network-tripwire rules;
- change production discovery modules;
- change source ceilings, floors, selection, ranking, or scoring;
- run another controlling proof in this lane.

## Money-usefulness contribution

This repair makes the controlling proof exercise the same permanent candidate-supply path Printer is intended to use operationally, so later clean-memory evidence is meaningful rather than a proof-only variant.

## What this improves

- restores canonical permanent operational discovery policy under the C8 proof capability;
- keeps the already-proven deterministic fixture transports as dependency overrides only;
- prevents accidental fallback into the legacy exact-pair path;
- preserves fail-closed accounting and network-tripwire behavior.

## What remains locked

Checkpoint 8 is still incomplete. No `WINDOW_1H+`, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL are unlocked.

## Proof/test required before completion

Offline only:

1. targeted regression proving the disposable bridge preserves every canonical `OPERATIONAL_GRADUATED_SUPPLY_KWARGS` value unless an explicit fixture dependency override uses the same key;
2. targeted C8 path regression proving `permanent_availability=True` reaches the graduated-supply call under the disposable bridge;
3. existing focused Checkpoint 8 suite;
4. compile and `git diff --check`.

No public campaign or provider/network execution is authorized in DTW-44.

## Functionality Risks / Setbacks / Efficiency Blockers

- A later authorized proof may expose another downstream seam after permanent supply progresses further.
- The repair must not duplicate operational policy values in the proof harness; the canonical mapping must remain the owner.
- Broad regression is unnecessary here; focused C8 and bridge-policy tests are the minimum sufficient verification.