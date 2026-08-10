# Printer V1 — Post-DTW100 Standard Four-Hour Rereadiness Historical-Evidence Provenance Audit

## Verdict

`V2_9_8B_POST_DTW100_STANDARD_FOUR_HOUR_REREADINESS_HISTORICAL_EVIDENCE_PROVENANCE_AUDIT_PASS`

The post-staging-repair host rereadiness blocker is a pre-authorization audit-path mismatch, not a production Git-provenance defect and not unexplained repository drift.

## Baseline

- Branch: `agent/v2-9-8b-post-dtw100-standard-four-hour-rereadiness-after-staging-repair`
- Baseline HEAD: `75abb21dfce462a744d0422f7413a47b393857aa`
- Authoritative DB trust anchor remains `6ce0e27332427243cffd055c41de58408f46dbcd84d43a764bf1764915a176fb`, size `76435456`.
- Ordinary wrapper staging residue was already quarantined with preservation and zero DB/runtime/source/authorization mutation.

## Audit finding

The host inventory found exactly 26 visible untracked repository files and zero SQLite runtime sidecars. Every path is retained Printer evidence under `operator-runs/`:

1. 10 files from the retained authoritative migration-050 package `V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f`.
2. 16 historical ordinary WINDOW_15M `final_authorization.json` files, including the DTW100 authorization.

There were no mystery temporary files, unrelated user files, symlinks, or other untracked classes in the captured inventory.

## Exact cause

`build_standard_four_hour_preflight()` delegates to `build_activation_preflight()`. Before a standard-four-hour authorization exists, `git_provenance_authorization=None`, so `build_activation_preflight()` correctly applies raw operational Git provenance. Raw operational provenance permits only the exact authoritative SQLite sidecars and rejects any other untracked path.

During an actual authorized standard-four-hour run, this is different by design: the one-shot wrapper builds and validates a manifest, the standard Git authorization profile enumerates the retained migration package plus explicitly approved historical authorization evidence, and the resulting `ValidatedGitProvenanceAuthorization.allowed_untracked_paths` is supplied to `build_standard_four_hour_preflight()`.

Therefore the current blocker exists only because the pre-authorization rereadiness helper asks the production launch-time Git gate a question that cannot yet be answered with manifest authority.

## Decision

Do **not**:

- delete, move, quarantine, ignore, or broadly allow the 26 retained evidence files;
- weaken `_capture_operational_git_provenance()`;
- add `operator-runs/` to a generic Git allowlist or `.gitignore` bypass;
- fabricate a `ValidatedGitProvenanceAuthorization` before authorization exists;
- change the authorized standard-four-hour production path.

The repair belongs only to the read-only rereadiness helper. It must validate the exact retained-evidence inventory itself, then run the same non-Git readiness owners directly and read-only.

## Money-usefulness contribution

This removes a false pre-authorization blocker without weakening the launch trust boundary, allowing Printer to progress toward the first real standard 15m→1h→4h memory-growth campaign while preserving historical evidence needed to trust that run.

## What this improves

- Makes pre-authorization rereadiness compatible with required retained evidence.
- Preserves exact launch-time manifest/Git provenance enforcement.
- Keeps migration and historical authorization evidence available for the future one-use standard-four-hour manifest.

## Still locked

This audit does not create an authorization, start runtime, fetch sources, mutate the authoritative DB, generate memory, activate retrieval, create paper decisions, unlock BUY/SELL/HOLD, create positions, or unlock WINDOW_12H/WINDOW_24H.

## Proof required before closeout

1. Helper-only implementation; no production module change.
2. Exact 26-path evidence inventory with exact hashes/sizes must be enforced fail-closed.
3. Any extra/missing/changed untracked path must block.
4. Non-Git readiness owners must remain zero-source/read-only.
5. Authoritative DB fingerprint, process/handle/lease/staging state must remain unchanged before/after.
6. Static exact-head proof before host execution.
7. Fresh host rereadiness PASS before any authorization creation.

## Functionality Risks / Setbacks / Efficiency Blockers

- Retained evidence may drift or a new historical authorization file may appear; the helper must block rather than silently broaden trust.
- Duplicating broad production preflight logic would risk future drift; the helper should call existing canonical non-Git owners directly and keep its local composition narrow.
- A fabricated authorization object would blur audit and execution authority and is prohibited.
