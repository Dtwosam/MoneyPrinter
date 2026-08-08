# Printer V1 V2-9.8B Post-C8 Authorized WINDOW_15M — Pre-Marker Schema Block Closeout

Date: 2026-08-08

Linear: `DTW-73`

## Verdict

`V2_9_8B_POST_C8_AUTHORIZED_WINDOW_15M_ONE_SHOT_BLOCKED_UNCONSUMED_PRE_MARKER_AUTHORIZATION_SCHEMA_MISMATCH`

The single approved wrapper invocation did not reach authorization consumption or Printer runtime. It failed inside the canonical pre-marker Git-provenance authorization validation because the DTW-72 package's `authoritative_database` object contained extra fields beyond the exact seven-field contract.

## Attempt identity

- authorization ID `V2_9_8B_WINDOW_15M_AUTH_20260808T122000Z`;
- authorization SHA-256 `a0d297ab2cb1d76bd34914366170a1b2c843fef27d6e0e617f9f54b9ae0aa57b`;
- authorized branch `agent/v2-9-8b-post-c8-window15m-authorization-preparation`;
- authorized HEAD `15978c6c54eab0243db8fe07237b6ec354e532a1`;
- wrapper status `WINDOW_15M_ONE_SHOT_WRAPPER_BLOCKED`;
- error type `GitProvenanceAuthorizationError`;
- error message `authoritative_database must contain the exact required fields`;
- automatic retries/manual reruns/resumes/restarts/successors all `0`.

## Exact root cause

At the authorized HEAD, `pre_authorization_migration_ledger_guard.py` defines exactly seven package binding fields:

1. `path`
2. `sha256`
3. `size`
4. `inode`
5. `mtime_ns`
6. `migration_count`
7. `migration_head`

The canonical Git-provenance validator explicitly requires `set(authoritative_database) == set(PACKAGE_BINDING_FIELDS)`.

The DTW-72 package included those seven values but also reporting/health fields such as `integrity`, `foreign_key_violations`, sidecar booleans, `opened_mode`, and `mutated_by_authorization_lane`. Those extras made the package schema invalid even though the required seven values were truthful.

This defect originated in the authorization-construction/review process. The wrapper itself enforced the intended fail-closed contract correctly.

## Consumption and runtime classification

`window_15m_one_shot_wrapper.apply_authorization_once()` states that authorization consumption occurs only after successful create-once write of `application-marker.json`. A failure before marker creation is `UNCONSUMED_PRE_MARKER_BLOCKED`.

The failing exact-field validation is executed by the pre-marker validator after staging-manifest construction but before canonical application promotion and before marker creation. The wrapper output reported no secondary staging-cleanup or canonical-cleanup blocker.

Therefore:

- authorization marker creation: not reached;
- authorization consumption: not reached;
- child launch: not reached;
- provider/source fetching: not reached;
- Central Scheduler runtime: not reached;
- authoritative DB mutation: not reached;
- memory generation: not reached;
- `WINDOW_15M` lifecycle: not started;
- `WINDOW_1H+`, retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits and PnL: not reached.

The package is technically unconsumed under wrapper semantics, but it must not be invoked again because the operator explicitly prohibited retry/rerun/resume/restart/successor and the package is known invalid.

## Review-process gap

The DTW-72 independent review confirmed that all required DB binding values were present and matched the reviewed authoritative DB, but it did not enforce exact key-set equality. It also built the manifest in memory without running the canonical pre-marker validator over that exact package before runtime authorization was declared ready.

That review gap allowed an invalid package to receive a PASS verdict.

## Money-usefulness contribution

The fail-closed wrapper prevented an invalid authorization envelope from consuming a scarce real operational attempt or mutating the clean memory corpus. The blocker exposes a narrow control-plane defect before any market collection began.

## What this improves

This closeout establishes the exact failed contract and separates package/review construction from Printer runtime. The next repair can target only authorization schema conformance and review coverage rather than reopening discovery, Scheduler, source, holder, or memory logic.

## What remains locked

No new authorization, wrapper invocation, provider/source call, Scheduler/Printer runtime, DB mutation, memory generation, longer window, retrieval, paper decision, BUY/SELL/HOLD, position, trade, paper-trade audit, or PnL action is authorized by this closeout.

No reuse or rerun of `V2_9_8B_WINDOW_15M_AUTH_20260808T122000Z` is allowed.

## Proof/test needed before completion of the repair sequence

The next lane must first audit the authorization-construction and review path. Any later repair must prove, with minimum sufficient focused checks, that a candidate authorization using the exact seven-field DB binding passes the same canonical pre-marker validation that the real wrapper invokes, without creating a marker, launching runtime, or touching the authoritative DB.

## Functionality Risks / Setbacks / Efficiency Blockers

- The invalid package must remain preserved as evidence and must not be edited in place.
- A second package must not be created under the exhausted DTW-72 approval; any later fresh package requires a new explicit operator authorization gate after repair readiness PASS.
- The wrapper must not be weakened to accept extra database fields; the package/review path must conform to the existing exact contract.
- No broad regression suite is justified yet; this is a narrow authorization-envelope/review defect.

## Stop condition

Close DTW-73 BLOCKED at the pre-marker schema mismatch. Proceed only to an audit/readiness lane for the authorization-construction/review defect. Do not rerun the wrapper.