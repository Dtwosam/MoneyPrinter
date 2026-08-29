from pathlib import Path
import re
import subprocess

BASELINE = "096d179983f7fe5481879fd898c3202dad479dd6"

head_parent = subprocess.check_output(["git", "rev-parse", "HEAD^^"], text=True).strip()
if head_parent != BASELINE:
    raise SystemExit(f"unexpected governance baseline ancestor: {head_parent}")

agents = Path("AGENTS.md")
text = agents.read_text(encoding="utf-8")
pattern = re.compile(
    r"### Current V2-9\.8B post-reconciliation governance state — 2026-08-29\n.*?(?=Any future approved remote-host implementation)",
    re.S,
)
replacement = """### Current V2-9.8B post-reconciliation governance state — 2026-08-29

The interrupted consumed four-token execution has completed production repair,
exact-residue recovery, separately approved authoritative reconciliation, and
post-reconciliation readiness review.

Authoritative DB identity remains:

`a7ad83d5f368192da7a4e7522870e3956e6f42f70b51748ff642f2c2c53683f8`

Fresh local read-only evidence reports `RECOVERED`, integrity/FKs `ok / 0`,
migration `62 / 062_pre_admission_attempt_evidence.sql`, zero active Scheduler
jobs, zero active pre-admission attempts, zero active factory runs, no campaign
lease, no Printer/Governor/Central Scheduler process, and no SQLite sidecars.
A final post-implementation local re-hash returned the same authoritative DB
SHA above.

The consumed authorization
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260828T211924Z_5fcb1bf5`
remains permanently consumed and non-reusable. Its exact diagnostic historical
disposition is now `CONSUMED_CHILD_EXITED_NONZERO`; this records the original
wrapper/child result and does not grant reuse authority. Any future authorization
must explicitly carry this exact ID in its approved
`prior_authorizations_non_reusable` trust root.

Post-reconciliation readiness verdict:

`V2_9_8B_POST_RECONCILIATION_NEXT_BOUNDED_CAMPAIGN_READINESS_PASS`

The exact current permitted lane is:

`FRESH EXACT-HEAD / EXACT-DB ONE-SHOT STANDARD-4H AUTHORIZATION PREPARATION + INDEPENDENT REVIEW`

That lane may prepare and independently review one brand-new authorization
package only. The package must bind the then-current reviewed Git HEAD and exact
authoritative DB SHA, preserve migration-062 provenance and all historical
non-reuse trust, and remain unusable until its own independent review and later
separate operator execution approval. This lane does **not** authorize applying
or consuming an authorization, Printer execution, provider/RPC/WebSocket calls,
Central Scheduler runtime, another campaign, retry/resume/restart of the
consumed campaign, remote/VPS work, retrieval, paper decisions, positions,
trades, audits, PnL, or longer-window activation.

Governing readiness closeout:

`docs/printer-v1-v2-9-8b-post-reconciliation-next-bounded-campaign-readiness-closeout.md`

"""
new_text, count = pattern.subn(replacement, text, count=1)
if count != 1:
    raise SystemExit(f"AGENTS current-lane replacement count={count}")
agents.write_text(new_text, encoding="utf-8")

Path("CURRENT_HANDOFF.md").write_text("""# CURRENT_HANDOFF — Printer V1

## Current lane

`FRESH EXACT-HEAD / EXACT-DB ONE-SHOT STANDARD-4H AUTHORIZATION PREPARATION + INDEPENDENT REVIEW`

This lane may prepare and independently review one brand-new authorization package only. It does not authorize authorization application/consumption, Printer execution, providers/RPC/WebSocket, Central Scheduler runtime, another campaign, or remote/VPS work.

## Current repository state

Readiness governance branch:

`governance/v2-9-8b-post-reconciliation-readiness-closeout`

Latest reviewed provenance implementation:

`784d4afd1e2cb479e6773e588b5d62ebea53f71e`

Independent implementation closeout:

`096d179983f7fe5481879fd898c3202dad479dd6`

## Authoritative database

Path: `data/printer_v1.sqlite3`

Exact SHA-256, re-confirmed locally after the code-only provenance repair:

`a7ad83d5f368192da7a4e7522870e3956e6f42f70b51748ff642f2c2c53683f8`

Read-only readiness evidence reports `RECOVERED`, integrity `ok`, FK violations `0`, migration count `62`, tip `062_pre_admission_attempt_evidence.sql`, zero active Scheduler jobs, zero active pre-admission attempts, zero active factory runs, no campaign lease, zero Printer/Governor/Central Scheduler processes, and no SQLite WAL/SHM/journal sidecars.

## Latest completed work

Post-reconciliation next-bounded-campaign readiness closed PASS.

Consumed authorization `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260828T211924Z_5fcb1bf5` remains permanently consumed/non-reusable and now has exact diagnostic historical disposition `CONSUMED_CHILD_EXITED_NONZERO`.

Implementation proof: RED `2 failed, 3 passed`; GREEN `35 passed, 8 subtests passed`, plus `py_compile` and `git diff --check` PASS. Independent implementation review PASS.

Readiness closeout:

`docs/printer-v1-v2-9-8b-post-reconciliation-next-bounded-campaign-readiness-closeout.md`

## Exact next permitted action

Prepare a brand-new exact-HEAD/exact-DB one-shot Standard-4H authorization package and then independently review it.

The package must bind its exact reviewed Git HEAD and authoritative DB SHA `a7ad83d5f368192da7a4e7522870e3956e6f42f70b51748ff642f2c2c53683f8`; preserve migration-062 evidence identity; explicitly include all required historical non-reusable authorization IDs including `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260828T211924Z_5fcb1bf5`; preserve one-shot/non-retry semantics, Source Governor and Central Scheduler authority; and keep retrieval and financial capability locked.

Preparation/review does not authorize execution. A later separately explicit operator approval is required before any new authorization may be consumed.

## Permanent locks

Solana-only; Solana memecoin-only; paper-trading only. No live wallet/private keys/signing/real funds/live execution. No paid API dependency. No scoring/ranking/confidence/weighted decision logic. No embeddings/vectors unless explicitly approved. No Source Governor or Central Scheduler bypass. No dirty-memory retrieval/decisions. Retrieval and all financial capability remain locked. `WINDOW_5M_MICRO_EVENT` remains support-only. `WINDOW_12H` and `WINDOW_24H` remain locked. Remote/VPS work remains paused at `agent/remote-host-linux-portability-implementation`, HEAD `f61419f2db37fc5eb220c20fafeaf15501218033`.
""", encoding="utf-8")

Path("docs/printer-v1-v2-9-8b-post-reconciliation-next-bounded-campaign-readiness-closeout.md").write_text("""# Printer V1 V2-9.8B — Post-Reconciliation Next-Bounded-Campaign Readiness Closeout

Date: 2026-08-29

Lane: **READ-ONLY READINESS / GOVERNANCE CLOSEOUT**

## Reviewed chain

Governance baseline: `aca6218f72e3b97fef3d0a93c98c15dbbc91819a`

Aug28 consumed-authorization disposition design: `dc4d5cafe5f142bd959ab5b3bf6d681d8f00776d`

Implementation: `784d4afd1e2cb479e6773e588b5d62ebea53f71e`

Independent implementation closeout: `096d179983f7fe5481879fd898c3202dad479dd6`

## Authoritative read-only evidence

Operator-executed local readiness checks reported authoritative DB SHA `a7ad83d5f368192da7a4e7522870e3956e6f42f70b51748ff642f2c2c53683f8`; recovered shape `RECOVERED`; integrity/FKs `ok / 0`; migration `62 / 062_pre_admission_attempt_evidence.sql`; zero active Scheduler jobs, pre-admission attempts, and factory runs; no campaign lease; zero Printer/Governor/Central Scheduler processes; and no SQLite WAL/SHM/journal sidecars.

Consumed marker SHA remained `9099e5f31949bd9dc219dbe58a301e095df1600cd5698b705841ee33bfd0c76a`, all retry/rerun/resume/restart/successor flags remained false, and migration-062 provenance remained `MIGRATION_062_20260828T182504Z / fa617f77f288705e7e8a4d3676f78feee041f098292a59d431a60e66624bcd02`.

After the code-only historical-disposition implementation and independent review, the operator re-hashed the authoritative DB and reported the same exact SHA. No authoritative operational mutation occurred in the provenance lane.

Historical capability rows remain locked historical state; this readiness closeout does not activate retrieval or financial capability.

## Historical authorization provenance

Consumed authorization `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260828T211924Z_5fcb1bf5` remains permanently non-reusable. Its exact diagnostic disposition is `CONSUMED_CHILD_EXITED_NONZERO`. Any new authorization must explicitly include this exact ID in `prior_authorizations_non_reusable`; directory discovery alone cannot grant trust or reuse authority.

## Proof incorporated

RED-before-GREEN provenance proof: RED `2 failed, 3 passed`; GREEN `35 passed, 8 subtests passed`; `py_compile` PASS; `git diff --check` PASS; independent implementation review PASS.

Older handoff-transition test failures were adjudicated as stale governance/synthetic-fixture debt and are not production regressions.

## Verdict

`V2_9_8B_POST_RECONCILIATION_NEXT_BOUNDED_CAMPAIGN_READINESS_PASS`

## Next permitted lane

`FRESH EXACT-HEAD / EXACT-DB ONE-SHOT STANDARD-4H AUTHORIZATION PREPARATION + INDEPENDENT REVIEW`

That lane may create and review a new one-shot authorization package only. It does not authorize applying/consuming it or running a campaign. Separate explicit operator approval remains required before execution.
""", encoding="utf-8")
