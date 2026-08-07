# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 Controlling-Proof Entry Readiness Closeout

## Verdict

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_CONTROLLING_PROOF_ENTRY_READY`

Checkpoint 8 pre-proof hardening is complete and exactly one controlling disposable public-composition proof attempt is authorized from the exact approved HEAD recorded by this closeout commit. This verdict does **not** mean Checkpoint 8 itself is complete; the controlling proof, independent inspection of its frozen evidence, and final C8 closeout still remain.

## Governing source stack

This closeout remains subordinate to the active Printer V1 stack:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`

## Completed readiness evidence

- Public-composition audit/design and pre-proof repair design are complete.
- Production authorization law remains unchanged; disposable proof evidence is separate and durable.
- Exact canonical 20-label fixture composition is prepared with zero provider fallback.
- Deterministic fixture response semantics cover exactly two distinct non-infrastructure Solana candidates.
- Process-local external-network tripwire and atomic one-shot sentinel are proven.
- Exact one public `run_operational_campaign()` call and exact one `report_only()` call are wired behind the sentinel and tripwire.
- Frozen proof-summary boundary and SHA-256 evidence sealing are wired.
- Independent inspector is read-only, refuses the canonical production DB, recomputes frozen-summary integrity, migration/integrity/FK safety, graph/governance projections, frozen safety, report/replay identity, and fixture-manifest identity, and writes only a separate exclusive inspection artifact.
- Independent inspector contains no controlling-harness, campaign-runner, or report-replay dependency.

## Focused proof of readiness

Temporary GitHub verification PR: `#21` — closed without merge.

Controlling CI run:

- workflow run: `31180352004`
- job: `92871876502`
- Python: `3.11.15`
- harness `py_compile`: PASS
- inspector `py_compile`: PASS
- focused C8 pytest gate: **87 passed in 30.52s**

The tested commit was `26a97fac505a528a617581b1b68972088cb6bd7e`. Post-test cleanup commit `3df5a46429080866b390e3393004b8783fa271f1` removed only `.github/workflows/checkpoint8-independent-inspector-ci.yml`; no production, harness, inspector, or test file changed after the GREEN run.

## Money-usefulness contribution

This readiness gate makes the first real disposable `WINDOW_15M` public-composition proof trustworthy enough to use as evidence for later memory-factory automation work. It improves confidence that the eventual clean-memory result comes through the ordinary governed composition rather than a hidden provider, bypass, retry, or synthetic acceptance shortcut.

## What this improves

- proves one-shot execution boundaries before the proof attempt;
- proves deterministic offline source-response coverage before spending the attempt;
- proves frozen-evidence and independent-read-only inspection boundaries;
- preserves Source Governor, Central Scheduler, cleanup, memory-quality, replay, and downstream-lock requirements as inspection targets.

## Still locked

This closeout unlocks only the single Checkpoint 8 controlling proof attempt. It does **not** unlock:

- another attempt if the controlling proof fails;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, or `WINDOW_24H` activation;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions;
- trade events or trade audits;
- PnL;
- any live wallet, private key, real funds, or live execution.

`WINDOW_5M_MICRO_EVENT` remains support-only.

## Required proof before Checkpoint 8 completion

Exactly one fresh controlling proof must now run with:

- one fresh canonically migrated disposable DB;
- one fresh disposable artifact root;
- exact canonical 20-label fixture composition;
- zero external-network/provider attempts;
- exactly one public campaign call;
- normal uncompressed `WINDOW_15M` behavior;
- exactly two clean terminal current-run 15m windows;
- `CLEAN_MEMORY` episodes with fingerprints;
- `CAMPAIGN_PASS`;
- cleanup, lease release, and zero residue;
- one zero-work report-only replay;
- zero downstream capability deltas;
- no longer-window activation;
- no retry/rerun/resume/restart/successor.

If the controlling run succeeds, the frozen proof directory must then pass the independent inspector. Only then may the final Checkpoint 8 closeout be written.

## Functionality Risks / Setbacks / Efficiency Blockers

- The controlling attempt is one-shot. Any failure consumes the attempt and must be treated as evidence, not automatically retried.
- The independent inspector is intentionally strict. If the real proof DB/artifacts do not persist enough evidence to prove required ownership, graph, cleanup, or identity facts independently, inspection must fail closed.
- No known focused-test blocker remains at entry readiness.

## Stop condition

Stop after issuing this readiness verdict. Do not run any second proof attempt and do not advance to later capabilities unless the single controlling proof and its independent inspection both pass and Checkpoint 8 is formally closed.
