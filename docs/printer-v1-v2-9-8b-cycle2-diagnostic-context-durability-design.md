# Printer V1 V2-9.8B Cycle-2 Diagnostic Context Durability Design

Date: 2026-08-19

## Authority and baseline

This corrective is governed by the active Printer V1 source stack and the completed fresh Cycle-2 A-to-Z audit. It extends open draft PR #191 only.

- approved executable base: `f40210f439d3e8366369e7c919dc9dd011868cb3`
- implementation branch before this corrective: `agent/v2-9-8b-cycle2-historical-proof-carrier-provenance-repair`
- implementation HEAD before this corrective: `581a6e4ea1b534b0da3599bb92380799dfa1acff`
- PR: `#191`, draft, unmerged

No campaign authorization is created or reused by this lane. Printer is not run.

## Audit finding

The fresh A-to-Z Cycle-2 audit found no new functional defect from later-cycle fresh discovery through exact identity, source-specific admission, market/protocol confirmation, freeze depth 4, neutral two-token selection, Cycle-1 disjointness, atomic admission, 15m activation, and lawful 15m -> 1h -> 4h continuation.

One diagnostic durability defect remains. PR #191's typed `GraduatedSupplyError` already owns a stable categorical code plus bounded context:

- `stage`
- `mint`
- `pool`
- `admission_authority`
- `nomination_source`

The outer Cycle-2 pre-admission catcher currently persists only the categorical `failure_cause`. The bounded context is therefore lost after terminalization.

## Design decision

Do not add Migration 059. Do not overload `printer_pre_admission_discovery_attempts.first_terminal_cause`; it remains the stable categorical terminal identifier. Do not replace the Scheduler observer's `first_terminal_cause` with JSON or arbitrary exception text.

Preserve the exact existing Scheduler implementation byte-for-byte as `src/printer_v1/scheduler/_scheduler_base.py`, then make `src/printer_v1/scheduler/scheduler.py` a compatibility adapter that re-exports the existing surface and overrides only `fail_job`.

The adapter owns one job-keyed, in-process diagnostic handoff:

1. A typed graduated-supply error, while the exact operational DB is bound, identifies a unique RUNNING `PRE_ADMISSION_DISCOVERY_SELECTION` Scheduler job. Zero or multiple matches produce no diagnostic side effect.
2. It stages only an allowlisted sanitized envelope for that exact job id.
3. The existing outer owner later calls `fail_job(error=<categorical cause>, max_retries=0)` as before.
4. The adapter consumes diagnostic context only when the staged failure code matches the categorical error suffix for the same job id.
5. `printer_scheduler_jobs.last_error` receives canonical bounded JSON for that typed Cycle-2 failure.
6. The Scheduler observer continues to receive the original categorical `error` as `first_terminal_cause`.
7. `printer_pre_admission_discovery_attempts.first_terminal_cause` remains unchanged because the outer owner continues to terminalize it with the categorical cause before `fail_job`.
8. Without staged matching diagnostics, `fail_job` behaves exactly as before and writes the ordinary error string to `last_error`.

The durable JSON allowlist is exactly:

- `failure_code`
- `stage`
- `mint`
- `pool`
- `admission_authority`
- `nomination_source`

Every value is bounded. No provider body, traceback, arbitrary exception message, credentials, wallet material, or uncontrolled exception attributes are persisted.

## Safety and ownership locks

This corrective adds no provider/source request, retry, endpoint rotation, score, rank, confidence, selector, liquidity rule, freeze rule, lifecycle path, financial capability, or scheduler bypass.

Unchanged:

- Solana-only / Solana-memecoin-only / paper-only
- Source Governor ownership
- Central Scheduler ownership
- `$3,000` liquidity floor
- freeze minimum depth 4
- neutral deterministic selection
- two Cycle-2 slots and Cycle-1 disjointness
- retries `0`
- endpoint rotation `false`
- `WINDOW_5M_MICRO_EVENT` support-only
- 12h/24h, retrieval, BUY/SELL/HOLD, positions, trade events, audits, and PnL locked

Diagnostic staging is non-authoritative. Failure to stage diagnostics must never make an otherwise valid candidate fail or alter the original failure category.

## Focused proof

RED then GREEN proof is limited to:

1. typed Cycle-2 supply error stages bounded context for the exact RUNNING pre-admission Scheduler job;
2. `fail_job(..., max_retries=0)` leaves job `FAILED`, preserves the categorical Scheduler observer terminal cause, and durably stores the canonical context envelope in `last_error`;
3. unrelated/generic failure with no staged context retains the historical plain-string `last_error` behavior;
4. mismatched staged code is not consumed as another failure's diagnostics;
5. existing four PR #191 historical-carrier regressions remain green;
6. compile changed production modules and run `git diff --check` in the proof environment.

No broad regression suite is required for this bounded diagnostic-only corrective unless focused proof exposes wider coupling.

## Stop condition

After focused GREEN proof and closeout/handoff update, leave PR #191 draft and unmerged. The next permitted lane is independent review/adoption of PR #191, followed by fresh post-repair readiness on the exact adopted executable commit. Only a later explicit authorization lane may create a new one-shot 4/2/2 campaign authorization.
