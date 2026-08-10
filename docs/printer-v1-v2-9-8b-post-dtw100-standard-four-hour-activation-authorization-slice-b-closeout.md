# Printer V1 Post-DTW100 Standard Four-Hour Activation — Authorization Slice B Closeout

## Verdict

`V2_9_8B_POST_DTW100_STANDARD_FOUR_HOUR_ACTIVATION_AUTHORIZATION_SLICE_B_PASS`

Slice B is complete. The standard first-four-hour operational path now has a distinct one-use authorization, Git-provenance manifest, application-marker, wrapper, child-command, and child-terminal authority boundary. This closeout does **not** authorize or run a real campaign. Factory/runtime handoff remains blocked pending Slice C.

## Exact implementation boundary

Baseline RED head: `b19b122dc13cbf4bbc802bca3a0223dce7256f32`.

Candidate and independently proven production head: `7eff7fa8b721358be847a48bb1b85f468722888c`.

The candidate contains two intentional commits after the RED head:

1. a test-fixture-only correction making the fixture `.venv/` ignored before its Git trust boundary is sealed;
2. `Implement standard four-hour one-shot authorization boundary` — four production files only.

Production files changed:

- `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py`
- `src/printer_v1/operator_cli/operational_memory_factory_command.py`
- `src/printer_v1/operator_cli/standard_four_hour_one_shot_wrapper.py`
- `src/printer_v1/operator_cli/window_15m_child_terminal.py`

No schema or migration was added.

## What was built

- Dedicated standard-four-hour authorization profile:
  - mode `standard-four-hour-run`;
  - dedicated authorization package root/kind;
  - dedicated manifest schema;
  - explicit historical-authorization roots.
- Ordinary `run` remains the default authorization profile and cannot consume the standard profile.
- Standard and ordinary manifests/markers fail closed on cross-mode use.
- Standard final authorization document validates exact temporal, Git, authoritative-DB, one-use, campaign-policy, and prior-authorization bindings.
- Standard one-shot wrapper:
  - consumes exactly once by create-once application directory/marker semantics;
  - permits no automatic retry, manual rerun, resume, restart, or successor;
  - launches only `standard-four-hour-run --operator-approved`;
  - reuses the hardened interpreter/filesystem/application primitives rather than creating a parallel trust model.
- Child terminal evidence is now exact-mode/schema bound for both ordinary `run` and `standard-four-hour-run`.
- Public command resolves the standard authorization profile only for the standard mode and accepts the child-terminal binding for that wrapper-bound mode.
- Slice B deliberately leaves the standard command blocked before factory execution. That runtime/factory authority is Slice C.

## Proof completed

RED proof:

- 7 new Slice B tests;
- 6 intended RED failures and 1 ordinary-profile control already green;
- ordinary wrapper trust regressions: 11/11 PASS;
- 12h/24h locks PASS;
- no fixture/import/runner defect after the fixture correction.

GREEN/candidate proof:

- Slice B authorization/wrapper contract: 7/7 PASS;
- activation-foundation tests PASS;
- ordinary wrapper self-contained regressions PASS;
- cross-mode separation PASS;
- 12h/24h locks PASS;
- compile and diff checks PASS.

Because the manifest change generalized historical authorization roots, the existing focused historical-authorization evidence contract was added as a risk-based regression and PASSed on the exact candidate.

Independent exact-head proof:

- exact SHA `7eff7fa8b721358be847a48bb1b85f468722888c` checked out cleanly;
- standard authorization/wrapper contract PASS;
- existing historical-authorization evidence contract PASS;
- activation foundation PASS;
- ordinary wrapper regressions PASS;
- exact ordinary/standard mode separation PASS;
- 12h/24h real collection remains disabled;
- `git diff --check` and clean tracked-tree checks PASS.

All disposable PRs were closed unmerged.

## Money-usefulness contribution

This slice makes a later real first-four-hour campaign operationally trustworthy: an operator can authorize one exact standard lifecycle attempt without accidentally reusing the ordinary 15m authority, the historical proof-only 4h path, or a stale prior authorization. That reduces the chance that a long collection produces ambiguous or non-auditable corpus evidence.

## What this improves

- Distinct standard-4h launch authority instead of a flag on the old proof path.
- One-use consumption and no-rerun semantics at the wrapper boundary.
- Exact Git/DB/package provenance for the future long campaign.
- Cross-mode fail-closed behavior between ordinary 15m and standard 4h operations.
- Structured terminal evidence for a standard wrapper child even when the child blocks before runtime.

## What remains locked

- Standard-four-hour factory execution remains blocked pending Slice C.
- No real source fetching or campaign runtime was performed.
- No fresh real authorization was created.
- No operator-host authoritative DB was read or mutated in this slice.
- 12h/24h remain locked.
- Retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, paper-trade audits, and PnL remain locked.
- No wallet, private key, signing, real funds, live execution, paid API, scoring/ranking/confidence/weighted logic, embeddings, or vectors were introduced.

## Next required slice

`Standard Four-Hour Activation Slice C — two-slot first-hour barrier and factory/runtime handoff`.

Slice C must preserve the design law that standard 4h composition occurs once after both owned campaign slots have reached their terminal first-hour verdicts, then composes the exact `0/1/2` eligible subset under explicit `STANDARD_CAMPAIGN` authority. It must not reuse `four_hour_proof_mode` as production authority.

## Functionality Risks / Setbacks / Efficiency Blockers

- The authorization trust surface is broader because historical evidence can now exist under ordinary and standard authorization roots. Control: roots are explicit, trust still comes only from the current authorization's declared prior IDs, and one ID appearing untracked across multiple roots fails closed.
- The standard wrapper reuses private hardened helpers from the ordinary wrapper. This minimizes duplicated security logic but creates coupling; future ordinary-wrapper refactors must retain directly affected standard-wrapper regressions.
- A consumed standard authorization can still end before factory/runtime work begins. This is intentional one-use safety, not permission to rerun; terminal evidence must remain durable.
- Slice B does not prove campaign runtime. Activation remains incomplete until Slice C and the final exact-head activation proof/closeout pass.
