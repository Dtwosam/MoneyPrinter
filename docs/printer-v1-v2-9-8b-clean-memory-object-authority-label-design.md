# Printer V1 V2-9.8B Clean-Memory Object Authority / Label Design

Status: DESIGN_APPROVED_FOR_IMPLEMENTATION_BY_OPERATOR

Baseline: `cf329a03801ca8af7e9fb5dbe65455f96cb9a2c6`

## Scope

Resolve the proven authority/naming mismatch without changing the successful E2Q -> E2Z object model and without unlocking retrieval.

## B1 — authoritative object contract

- Parent main windows remain `PARTIAL_MEMORY` after a successful E2Q audit. In the live pipeline this means `E2Q_AUDIT_CLEAN_CANDIDATE`, not failed evidence quality.
- E2Z episode + fingerprint is the current `CLEAN_MEMORY` object.
- Do not rewrite successful parent windows to `CLEAN_MEMORY`; E2Z currently requires the candidate-window state.
- `CLEAN_PROMOTED` means an E2Z clean object exists for the lifecycle window; it does not mean the parent row was relabelled clean.
- Legacy window-row `CLEAN_MEMORY` is not current operational authority.

## B2 — code-visible semantics and retrieval lock

- Centralize current object-authority semantics in a small, explicit contract helper so operator/report/retrieval code cannot infer cleanliness from ambiguous labels independently.
- The helper must distinguish `E2Q_CLEAN_CANDIDATE`, `E2Z_CLEAN_OBJECT`, and legacy window-clean state.
- Retrieval remains locked. This package may add a guard/assertion or pure predicate making the intended future eligibility explicit, but it must not activate retrieval or change any retrieval feature flag.
- Any future retrieval lane must explicitly choose episode+fingerprint authority and re-check hard exclusion (`do_not_train`, dirty/conflicting evidence) rather than relying on display labels.

## B3 — 4h U2 coverage persistence

Problem: 4h cadence is evaluated and passes inside supporting context, but the 4h quality path does not persist the normal U2 coverage row/window coverage columns.

Design:
- Reuse the existing Lane U2 coverage persistence owner used by 15m/1h.
- Persist 4h coverage after the 4h window is closed and cadence evidence exists, before E2Z clean-object creation.
- Do not manufacture coverage from absence; use the actual 4h snapshots/cadence policy.
- A genuine 4h cadence failure must retain existing fail-closed behavior.

## Required proof

Focused tests must prove:
1. E2Q success still leaves the parent window `PARTIAL_MEMORY`;
2. E2Z still creates the clean episode/fingerprint;
3. the new authority helper reports candidate vs clean object without label ambiguity;
4. retrieval remains disabled;
5. genuine 4h close persists a U2 coverage row and coverage status using actual snapshot evidence;
6. no 12h/24h or financial capability is activated.

No schema migration unless an existing current table cannot represent the evidence; current evidence says a migration is unnecessary.