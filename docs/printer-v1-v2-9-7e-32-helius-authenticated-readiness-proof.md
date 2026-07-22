# Printer V1 V2-9.7E.32 Helius-Authenticated Bounded Readiness Proof

## Verdict

`V2_9_7E_32_FAIL`

This is a **controlled, authorization-preserving non-execution**, not a source,
eligible-pool, snapshot or system defect. The consolidated readiness-source
contract preflight is now `READY` with the operator-owned Helius Free key
present, so the E.31 `V2_9_7E_31_BLOCKED_SOURCE_RELIABILITY` blocker is
**resolved**. The single authorized bounded live readiness cycle was, however,
**not started**: the PASS criteria (exactly two holder-eligible candidates and
two complete snapshot bundles) can only be produced by the multi-owner live
orchestration used in E.25–E.29, which was never committed as a runnable
single entry point. On being shown that state, the operator elected to stop and
record the READY preflight rather than reconstruct that uncommitted harness in
this lane. The single non-renewable live authorization is therefore
**preserved (unconsumed)** and zero external requests were made.

## Baseline and authorization

- Exact baseline: `deac94849fa0accf09b11acf807997e7d3d34c67`
- Baseline message: `Close post-liquidity-repair readiness proof blocker`
- Entry HEAD: exact baseline; tracked tree: clean (no staged/unstaged tracked
  changes; unrelated pre-existing untracked workspace files were preserved and
  excluded).
- Authorization: exactly one bounded live readiness cycle. **Not consumed** — no
  live source operation was transmitted (zero external requests).
- No production, test, schema or migration change was made in this lane.

## Preflight results (all zero-source; no live request)

| Preflight item | Result |
|---|---|
| Exact HEAD `deac948…` and clean tracked tree | PASS |
| No active runtime, proof, campaign or lease | PASS — no `python*` process; no lock/lease/pid file under `C:\Users\dtwof\PrinterPilot` |
| `PRINTER_HELIUS_API_KEY` available (not printed/persisted) | PASS — presence-only boolean check; value never read into any artifact |
| **Consolidated source-contract preflight** | **READY** |
| New isolated E.32 DB/report directory | Not created — the live cycle was not started, so nothing needed to be persisted (no `C:\Users\dtwof\PrinterPilot\E32`) |
| Ceiling / candidate cap / snapshot reservation | 45 / 3 / 6 — match |
| Worst-case total | 43 / 45 — match |
| Integrity / FKs / forbidden baselines | Not applicable — no isolated DB was created (no live cycle) |
| `secret_material_recorded` | false (no secret handled, printed or recorded) |

Consolidated readiness-source-contract preflight
(`build_readiness_source_contract_preflight`, deterministic and secret-free):

```json
{
  "status": "READY",
  "issues": [],
  "helius_secret_present": true,
  "secret_material_recorded": false,
  "external_requests": 0,
  "budget": {
    "operation_ceiling": 45,
    "candidate_cap": 3,
    "derived_candidate_cap": 3,
    "snapshot_reservation": 6,
    "contract_snapshot_reservation": 6,
    "pump_worst_case_operations": 13,
    "zero_transport_operations": 9,
    "holder_worst_case_operations": 15,
    "worst_case_total": 43
  },
  "provenance": {
    "primary_source": "geckoterminal",
    "supplemental_15m_source": "geckoterminal",
    "exact_window_seconds": 900
  }
}
```

Preflight report SHA-256 (canonical JSON of the full report):
`a908824534ef27f4427b59b9e497f2e72b0a26210c68e0791af3562ef5362885`.

The budget matches the task ceiling exactly: operation ceiling 45, candidate cap
3 (derived), snapshot reservation 6, and worst case `43/45`
(Pump 13 + combined zero-transport gates 9 + 3×5 holder 15 + snapshot 6). Every
source contract, request kind, rate limit, pacing and no-retry/rotation field
reports no drift, and the only E.31 issue —
`SOURCE_AUTH_DRIFT:helius_free:secret_missing` — is gone because the Helius
secret is now present.

## Why the cycle was not started

E.31 blocked at preflight because the Helius Free credential was absent. That is
now resolved: the deterministic preflight is `READY` and the Helius secret
resolves in this environment (presence confirmed by a boolean check only). The
remaining obstacle to a PASS is not a source, pool or snapshot fault — it is that
the **committed** code exposes no single runnable readiness path that produces
two complete snapshot bundles:

1. `AuthoritativeLiveOperationalCampaignOwner.run_readiness_only` is the only
   committed readiness-only entry point. It reaches finalized Pump acquisition,
   deterministic selection, the atomic two-or-none activation and a disposable
   dry-run handoff, then stops. It does **not** invoke the E.24 Helius
   holder-eligibility funnel nor the E.26/E.30 GeckoTerminal snapshot-bundle
   owner (`execute_readiness_snapshot_bundle`). Verified: its source contains no
   snapshot-bundle collection. It therefore cannot satisfy the E.32 PASS
   criteria on its own.
2. `AuthoritativeLiveOperationalCampaignOwner.run_operational` does perform live
   acquisition and holder eligibility, but then hands off to the full lifecycle
   driver (`self._driver.run(...)`), which schedules 15m/1h/4h lifecycle
   windows — explicitly forbidden by this lane.
3. The E.25/E.27/E.29 live cycles that produced holder eligibility **and** the
   readiness snapshot bundle stitched these committed pieces together in an
   operator harness held under `C:\Users\dtwof\PrinterPilot\E2*`. No such
   harness is committed to the repository, and none exists on disk today.

Reproducing the E.29-shape cycle therefore requires authoring a substantial new
orchestration harness (Pump acquisition → GoPlus/`solana_rpc`/authenticated
Helius holder eligibility → per-candidate GeckoTerminal base + OHLCV + trades
snapshot bundle → cleanup/replay/integrity). A subtly incorrect reconstruction
would either consume the single non-renewable live authorization on a broken run
or emit a misleading verdict. Presented with this, the operator chose to stop
and record the READY preflight, preserving the authorization for the separately
authorized full pilot decision.

Among the fixed E.32 verdict values none names a controlled pre-runtime stop
with a passing preflight: it is not a PASS (no two bundles were produced), and it
is not `BLOCKED_INSUFFICIENT_ELIGIBLE_POOL`, `BLOCKED_SOURCE_RELIABILITY` or
`BLOCKED_SNAPSHOT_READINESS`, because none of those runtime stop conditions was
reached — no live request was made. `V2_9_7E_32_FAIL` is used as the residual
value, qualified throughout as a deliberate authorization-preserving
non-execution rather than a defect.

## Isolation and secret handling

- No new isolated E.32 database or report directory was created; the live cycle
  was not started, so nothing needed to be persisted. Historical readiness
  databases (E.15/E.20/E.23/E.25/E.27/E.29) were not opened, mutated or treated
  as current evidence.
- The Helius key was checked for presence only. Its value was never printed,
  copied into arguments, resolved into a process that transmits it, persisted in
  evidence, or included in this closeout. `secret_material_recorded` is false and
  no secret bytes exist in this document.

## What this proves and does not prove

- Proven: with the Helius Free key configured, the committed consolidated
  readiness-source contract preflight passes `READY` with zero external calls,
  the E.30 budget/ceiling arithmetic is internally consistent (`43/45`), and the
  E.31 missing-credential block is resolved.
- Not proven: live liquidity/holder/snapshot readiness after the E.30 repair.
  That still requires the authorized cycle to actually run through the
  acquisition → holder-eligibility → snapshot-bundle path.

## To unblock (next lane)

Either (a) promote the E.25/E.29 orchestration into a committed, disposable
readiness-only entry point that stops after two snapshot bundles (no lifecycle,
memory, retrieval or financial work) and separately re-authorize one bounded
live cycle against it; or (b) explicitly authorize this lane to reconstruct and
run that harness once. No production contract change is required for the
preflight itself — it is already `READY`.

## Money-usefulness contribution

The lane confirms — with zero external calls and no secret handling — that the
E.30 liquidity/budget repair and the source-contract preflight are healthy at
this baseline and that the E.31 credential gap is closed, while preserving the
single non-renewable live authorization rather than spending it on a
reconstructed harness whose correctness was not first established. It reduces the
remaining work to one well-scoped step: expose (or authorize reconstruction of)
a committed readiness-only snapshot-bundle entry point.

## What remains locked

All Printer V1 Solana-memecoin-only, paper-only, free/public-source, governance,
two-or-none, clean-memory, support-only-5m, and financial/retrieval locks remain
unchanged. No lifecycle, memory, corpus, retrieval, decision or financial
capability was touched. No provider was contacted; no pilot was run; the
authorization is preserved.

## Functionality Risks / Setbacks / Efficiency Blockers

- **Blocker (primary):** no committed single-entrypoint readiness path produces
  two snapshot bundles; the E.25/E.29 orchestration lives only in uncommitted
  operator harnesses.
- **Setback:** the post-liquidity-repair live readiness proof is again deferred,
  now for a tooling/entry-point reason rather than the E.31 credential reason.
- **Risk:** none introduced — no external request, no mutation, no secret
  handling; the single-use authorization is intact.

## Readiness

**NOT READY** to consider the separately authorized full V2-9.7E two-token
pilot: a `V2_9_7E_32_READINESS_PASS` is a prerequisite and was not achieved. The
bounded readiness proof should be re-attempted under a fresh single-use
authorization once a committed readiness-only snapshot-bundle entry point exists
(or reconstruction is explicitly authorized). V2-9.7F, V2-9.8, the operational
memory-growth command, and retrieval/decision/financial capabilities remain
locked and were not started.
