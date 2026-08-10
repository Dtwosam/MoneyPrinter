# Printer V1 — Standard Four-Hour Consumed Preflight Runtime Closeout

## Verdict

`V2_9_8B_STANDARD_FOUR_HOUR_CONSUMED_PREFLIGHT_RUNTIME_CLOSEOUT_BLOCKED_COMMITTED_CODE_DEFECT`

The first separately operator-started standard 15m→1h→4h operational attempt is permanently consumed and must not be rerun.

The attempt safely stopped before either `WINDOW_15M` lifecycle stage could start because the committed production composition passes a legacy `operational_natural_disposition=True` flag into the standard-four-hour factory path while that same factory explicitly rejects the legacy disposition for a standard-four-hour campaign.

This is a deterministic committed-code composition defect. It is not a provider outage, holder-budget shortage, Git drift, DB corruption, authorization defect, or reason to increase any budget or weaken any safety gate.

## Exact attempt identity

- baseline branch: `agent/v2-9-8b-post-dtw100-standard-four-hour-rereadiness-after-staging-repair`
- launch HEAD: `3b558d2af77ac469dd0d6c2f04e3993515988b2e`
- authorization: `V2_9_8B_STANDARD_4H_AUTH_20260810T220717Z`
- authorization SHA-256: `f8d321ed164463f289997d4d6de8c0069a767df738706eb8ec8fb337718ca76e`
- execution: `20260810T221625Z-20e56a0c7f56`
- campaign: `20260810T221625Z-20e56a0c7f56-campaign`
- run: `20260810T221625Z-20e56a0c7f56-campaign-run`
- wrapper marker consumed: true
- wrapper child exit: `0`
- child terminal valid: true
- first terminal cause: `SAFE_STOP_PREFLIGHT_FAILED`
- automatic retries / manual reruns / resumes / restarts / successors: `0 / 0 / 0 / 0 / 0`

## Runtime evidence

The run reached governed pre-lifecycle work and then stopped at the lifecycle/factory preflight boundary.

Observed before the stop:

- governed discovery/protocol/holder work completed and was durably attributable;
- campaign source calls: `14`;
- measured transport operations: `15`;
- source-operation failures: `0`;
- exact discovery selection/handoff completed for two token slots;
- first-15m handoff Scheduler jobs `1496` and `1497` were created, then cancelled by the terminal owner;
- no current-run `WINDOW_15M` physical memory window was created;
- no clean episode or fingerprint was created;
- campaign acceptance correctly remained `BLOCKED_UNSAFE`.

The holder stage ended with `HOLDER_CONTEXT_BUDGET_EXHAUSTED`. That is not the root defect: the adopted holder-budget contract treats this as bounded completion and allows otherwise-valid memory-observation candidates to proceed with holder context unknown/blocked for future action. The production holder loop and freeze path preserve that law.

## Static root-cause trace

### 1. Live owner injects the legacy disposition

`src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`:

- marks `standard_four_hour_campaign=True` in lifecycle kwargs;
- rejects caller-supplied fixture/legacy disposition keys;
- then unconditionally sets `lk["operational_natural_disposition"] = True` for operational execution;
- invokes the origin→lifecycle driver with standard-four-hour mode and those lifecycle kwargs.

### 2. Driver forwards lifecycle options unchanged

`src/printer_v1/operator_cli/origin_lifecycle_campaign.py` copies `lifecycle_kwargs` into `lifecycle_options` and forwards them to `run_one_command_15m_factory(...)` together with the standard-four-hour booleans.

### 3. Factory preflight contains contradictory laws

`src/printer_v1/operator_cli/one_command_15m_factory.py` requires for a standard-four-hour campaign:

- operational persistent mode;
- two token slots;
- standard first-hour continuation;
- continuous four-hour observation;
- `four_hour_proof_mode=False`;
- no `operational_natural_disposition` historical disposition.

But the same preflight's `continuous_first_hour` branch sees the forced `operational_natural_disposition=True` and applies the legacy operational-natural rule requiring terminal 4h proof mode (`four_hour_proof_mode=True`).

Therefore the committed path is internally unsatisfiable: standard-four-hour requires proof mode false while inherited operational-natural logic requires it true, and standard-four-hour separately rejects the legacy disposition itself.

The factory returns `SAFE_STOP_PREFLIGHT_FAILED` before creating a factory run or either `WINDOW_15M` stage.

## Blocker classification

**BLOCKER CLASSIFICATION:** `COMMITTED_CODE_DEFECT`

**EVIDENCE:** consumed one-shot terminal evidence, exact DB attempt rows, exact Scheduler terminalization, zero current-run windows, and the static call-chain contradiction above.

**OFFICIAL-SOURCE COMPARISON:** no external protocol/provider behavior caused this stop; all relevant source transports completed without source-operation failure before lifecycle entry.

**PRINTER-CONTRACT COMPARISON:** the active standard-four-hour policy requires the production standard path, not historical proof dispositions. The current live owner incorrectly injects a legacy disposition into that path.

**ROOT CAUSE:** standard-four-hour composition was added on top of a live-owner default that still unconditionally asserts `operational_natural_disposition=True`; the factory correctly rejects the resulting contradictory configuration.

**CODE CHANGE JUSTIFIED:** YES, but only after the next repair audit/design gate.

**MINIMUM SAFE RESPONSE:** remove the standard-four-hour path's inheritance of historical operational-natural disposition semantics without weakening ordinary operational-natural behavior, one-shot authority, Source Governor, Central Scheduler, holder context law, or any lifecycle gate.

**FOCUSED PROOF:** offline standard-four-hour composition must reach factory-run creation and both first-15m lifecycle stage plans with the exact production configuration, while ordinary legacy/natural fixtures remain unchanged and invalid mixed dispositions still fail closed.

**UNTOUCHED SCOPE:** source contracts, holder budgets, discovery selection law, 5m support-only law, 12h/24h locks, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, wallet/signing/funds, paid APIs, scoring/ranking/confidence/weights, embeddings/vectors.

**AUTHORIZATION STATUS:** permanently consumed; no reuse, retry, resume, restart, or successor.

**NEXT ROADMAP-COMPLIANT STEP:** read-only repair-scope audit → design/specification → minimal implementation → focused offline proof → closeout → fresh operational rereadiness → fresh one-use authorization → independent authorization review → only then consider one new bounded operational proof.

## Terminal safety / cleanup

Post-attempt forensic inspection established:

- authoritative DB integrity: `ok`;
- foreign-key violations: `0`;
- no active-status operational rows detected;
- campaign supervision terminalized;
- cleanup completed;
- lease released;
- both handoff Scheduler jobs cancelled by owner;
- zero retry/restart/resume/successor behavior;
- no current-run memory window/episode/fingerprint;
- no retrieval or paper-financial capability unlock.

The failed attempt is therefore closed as a safe consumed preflight stop, not an ambiguous active run.

## Money-usefulness contribution

This closeout prevents another scarce one-shot authorization from being spent on the same deterministic wiring contradiction. Fixing the composition boundary is necessary before Printer can collect trustworthy continuous 15m→1h→4h memory; it does not make any token more tradeable or authorize financial action.

## What this lane improves

- identifies the exact deterministic blocker rather than blaming holder budget or providers;
- preserves the holder-decoupling law and existing safety ceilings;
- proves the consumed attempt left no active operational residue;
- narrows the repair to one composition/configuration boundary.

## What this lane still does not unlock

- no rerun or successor authorization;
- no new live/provider run;
- no 12h/24h collection;
- no retrieval;
- no paper decisions;
- no BUY/SELL/HOLD;
- no positions/trades/audits/PnL;
- no wallet/private key/signing/real funds/live execution;
- no paid APIs;
- no scoring/ranking/confidence/weighted decision logic;
- no embeddings/vectors.

## Proof/test required before future completion

Before another authorization can be considered:

1. audit the exact configuration ownership and affected callers;
2. specify the minimum standard-four-hour exception to legacy disposition injection;
3. implement only the approved boundary;
4. prove standard-four-hour factory preflight passes with production-shaped offline inputs;
5. prove ordinary operational-natural behavior and invalid mixed configurations remain fail-closed;
6. prove no holder/source/Scheduler/capability-law weakening;
7. close the repair and rerun separate operational rereadiness;
8. prepare and independently review a completely fresh one-use authorization.

## Functionality Risks / Setbacks / Efficiency Blockers

- A broad removal of `operational_natural_disposition` could regress historical ordinary operational behavior; repair must be mode-scoped.
- Treating holder budget exhaustion as the cause would create unnecessary budget growth and violate the adopted memory/holder decoupling design.
- Fixing only the error label instead of the contradictory configuration would hide the defect rather than repair it.
- A new live proof before offline reproduction and closeout would risk consuming another authorization on deterministic code.
- Current report acceptance failures such as missing factory binding and missing `WINDOW_15M` stages are downstream consequences of the preflight stop and must not be patched independently unless the post-repair proof shows a separate defect.
