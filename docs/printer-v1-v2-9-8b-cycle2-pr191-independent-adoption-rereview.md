# Printer V1 V2-9.8B Cycle-2 PR #191 Independent Adoption Re-Review

Date: 2026-08-19

## Authority and reviewed target

This independent re-review is governed by the active Printer V1 source stack and the current `CURRENT_HANDOFF.md`.

Reviewed PR:

`#191` — `V2-9.8B Cycle-2 historical proof carrier repair`

Reviewed product/executable head:

`bd818df37c9057ee59080d68fe64bcdade8e5e0e`

Approved executable base / merge base:

`f40210f439d3e8366369e7c919dc9dd011868cb3`

Branch:

`agent/v2-9-8b-cycle2-historical-proof-carrier-provenance-repair`

No Printer runtime, provider call, campaign authorization, retry/resume/restart/successor, wallet/signing/funds work, or financial capability occurred during this re-review.

## Structural review

PASS.

- PR #191 is ahead of the approved base and not behind it.
- merge base is exactly `f40210f439d3e8366369e7c919dc9dd011868cb3`.
- no unresolved inline review threads exist.
- the permanent PR diff contains 12 files and no temporary GitHub Actions workflow.
- temporary proof PRs #195 and #196 are closed without merge.
- temporary proof workflows are absent from the product branch.

## Preserved-owner integrity

PASS.

The compatibility adapters preserve the approved owners byte-for-byte:

- approved `graduated_supply_front_door.py` / current `_graduated_supply_front_door_base.py` blob SHA: `049f41ba91ed1c780615abd5e58cee253430ae70`;
- approved `scheduler.py` / current `_scheduler_base.py` blob SHA: `06cb3ad8cee3b446c21039753ba02ebba4242d31`.

The adapters therefore alter only the bounded corrective seams described below rather than silently rewriting unrelated source, market, selection, Scheduler, lifecycle, or memory logic.

## Historical direct-proof repair re-review

PASS.

The current adapter rejoins immutable Pump/PumpSwap graduation proof only for an exact historical registry candidate when:

- the candidate is not already carrying direct proof;
- the candidate is not `MARKET_PRESENT_POOL`;
- the registry contains the mint;
- lifecycle is `PUMPSWAP_GRADUATED_CONFIRMED`;
- the registry pool exactly matches the candidate pool; and
- immutable migration signature/program/time evidence is valid.

Pool mismatch or corrupt/missing immutable proof fails closed. The repair does not fabricate origin evidence, does not relabel a market-present candidate as direct Pump, and does not require same-cycle live-tail rediscovery for a durable historical Pump candidate.

Fresh `MARKET_PRESENT_POOL` behavior remains non-Pump and unchanged.

## Diagnostic durability re-review

PASS.

Typed graduated-supply failures may stage only the bounded allowlisted context:

- `failure_code`
- `stage`
- `mint`
- `pool`
- `admission_authority`
- `nomination_source`

Staging is non-authoritative. It requires exactly one matching RUNNING, locked `PRE_ADMISSION_DISCOVERY_SELECTION` Scheduler job in the bound operational DB; zero or multiple matches produce no diagnostic side effect. Any staging fault is swallowed so diagnostics cannot replace the original supply failure.

`fail_job` still delegates terminalization to the exact preserved Scheduler owner with the original categorical `error`. Only after that does the adapter optionally replace that matching job row's `last_error` with canonical bounded diagnostic JSON. The Scheduler observer's `first_terminal_cause`, pre-admission attempt cause, retry policy, job state, and control semantics remain unchanged.

No evidence was found that this diagnostic-only carrier can affect admission, selection, lifecycle, or financial behavior.

## Prior compatibility blocker

RESOLVED.

The prior independent review correctly identified:

`GRADUATED_SUPPLY_PUBLIC_EXCEPTION_BASE_COMPATIBILITY_BREAK`

The current code now preserves the historical public exception identity exactly:

`GraduatedSupplyError = _base.GraduatedSupplyError`

Typed corrective failures inherit through a private `_TypedGraduatedSupplyError`, and dynamic categorical subclasses inherit that typed class. As a result:

- preserved/re-exported base functions remain catchable through the historical public exception import;
- typed corrective failures remain instances of the public/base exception;
- categorical class-name provenance and bounded typed context remain available; and
- `build_graduated_supply(...)` continues to convert ordinary preserved-base errors while re-raising already-typed corrective errors unchanged.

## Proof evidence

PASS.

TDD compatibility proof:

- RED Actions run `32297538063`: `1 failed, 4 passed`; sole failure was the intended public/base exception identity mismatch.
- narrow GREEN Actions run `32297671884`: `5 passed in 2.59s`; production compile PASS; diff hygiene PASS.
- full bounded GREEN Actions run `32297731250`:
  - Cycle-2 historical-carrier + diagnostic-durability suites: `8 passed in 12.27s`;
  - existing Scheduler compatibility suite: `25 passed in 83.96s`;
  - production-module compile: PASS;
  - `git diff --check`: clean.

The current reviewed product/test blobs are the same blobs exercised by the final GREEN proof; subsequent branch changes before this re-review were documentation/cleanup only.

No broad suite is required for this adoption decision because the bounded proof directly covers the changed production seams and the risk-proportionate Scheduler compatibility surface.

## V1 lock review

PASS.

Unchanged:

- Solana-only;
- Solana memecoin-only;
- paper-only;
- no live wallet/private keys/signing/real funds/live execution;
- no paid API dependency;
- no scoring/ranking/confidence/weighted decision logic;
- no embeddings/vectors;
- no Source Governor bypass;
- no Central Scheduler bypass;
- no dirty-memory retrieval/decision use;
- no retrieval or financial capability unlock;
- no BUY/SELL/HOLD, positions, trade events, paper audits, or PnL unlock;
- `WINDOW_5M_MICRO_EVENT` remains support-only;
- no 12h/24h activation from this PR;
- `$3,000` liquidity floor unchanged;
- freeze depth 4 unchanged;
- neutral deterministic selection unchanged;
- Cycle-1/Cycle-2 disjointness unchanged;
- source budgets unchanged;
- retries remain `0`;
- endpoint rotation remains `false`;
- no Migration 059.

## Re-review verdict

`V2_9_8B_CYCLE2_PR191_INDEPENDENT_REREVIEW_OPERATOR_ADOPTION_PASS`

No remaining blocker was proven in PR #191 at the reviewed product/executable head.

This PASS approves PR #191 for the explicit operator merge/adoption decision only. It does not itself merge the PR, authorize a campaign, run Printer, or make any consumed authorization reusable.

## Exact next permitted action

Explicit operator adoption / merge of PR #191 into its approved base branch.

After lawful adoption, the exact adopted executable commit must enter a fresh post-repair two-cycle/four-token authoritative readiness lane before any new authorization-preparation lane. No campaign authorization may be created from this re-review alone.
