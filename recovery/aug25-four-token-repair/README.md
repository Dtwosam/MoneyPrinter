# Aug-25 four-token repair preservation

This branch preserves the verified Printer V1 Aug-25 four-token A-to-Z repair artifacts. It is **not** a production-ready or authorization-ready branch and it does not modify the repository's product code.

## Proven repair

The repair was developed against the byte-verified forensic Aug-25 source capture and preserved locally as repair commit `c92474dc32c8c7af1bc51535e2e976afdddfa3c2` on that forensic baseline.

Bounded closeout verdict: `AUG25_FOUR_TOKEN_A_TO_Z_REPAIR_BOUNDED_PROOF_PASS`.

The production-only patch in this directory contains the seven proven product-code repairs. The full proof patch and closeout are preserved separately in the repair bundle; this branch exists so the repair boundary cannot disappear when the original local-only Aug-25 Git commit is unavailable remotely.

## Hard stop

The forensic archive did not contain the exact original Migration 059-061 SQL bytes, and no reachable GitHub ref/object store contains the exact Aug-25 production blobs or canonical 059-061 migration files. Test-only 059-061 reconstructions passed schema-equivalence and bounded integration proof, but they are **not canonical migration provenance**.

Therefore:

`FRESH_LIVE_AUTHORIZATION_PREPARATION_NOT_AUTHORIZED_FROM_FORENSIC_CAPTURE`

Do not reuse the consumed Aug-25 authorization. Do not create a successor authorization from this preservation branch. Do not apply this patch to a mismatched historical branch merely because it applies textually.

## Next lawful action

Locate the genuine production checkout that still owns the canonical Migration 059-061 provenance. Confirm the active source stack and `CURRENT_HANDOFF.md`, verify the seven product files against the Aug-25 repair preimages or perform a scoped conflict audit, apply the production patch, then rerun the bounded rereadiness checks before any authorization-preparation lane is considered.
