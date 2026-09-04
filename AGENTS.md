# Printer V1 Working Rules

## Active authority

Read active rules in this order:

1. `AGENTS.md`
2. `docs/printer-v1-clean-master-spec.md`
3. `docs/printer-v1-build-order.md`
4. `CURRENT_HANDOFF.md`

`CURRENT_HANDOFF.md` is a concise status summary. It never overrides a safety
or capability lock in the first three files. Git history is the archive for
completed work; historical lane documents are not active authority.

## Working workflow

Use the smallest process that preserves evidence and safety:

```text
understand -> build/fix -> focused verification -> actual code review -> done
```

- Normal bug: find the defect, make the smallest fix, add or update a focused
  regression, verify it, and review the diff.
- Normal feature: build the smallest useful vertical slice, verify it, review
  it, then continue only if the next slice is useful.
- Failed operational run: inspect durable terminal evidence and fix a proven
  defect. Write a forensic document only when the evidence or ownership chain
  is genuinely complex.
- Design is required only for an architectural, ambiguous, schema-related, or
  safety-critical change. Ordinary repairs do not need a separate readiness,
  closeout, or bookkeeping lane.
- One meaningful engineering change normally has one commit. Do not create a
  separate documentation-only commit merely to advance process state.

Use focused, risk-based verification. Do not request broad suites unless the
change crosses a shared boundary or a focused failure makes it necessary.

## Non-negotiable V1 safety and capability locks

- Solana-only, Solana-memecoin-only, and paper-trading-only.
- No live wallet, private key, signing, real funds, or live trade execution.
- Free/public sources only; no paid dependency may become a V1 requirement.
- Source Governor is the sole governed source-request owner. Do not bypass it,
  add retries, rotate endpoints, or invent extra request budget outside the
  approved policy.
- Central Scheduler is the sole scheduler owner. Do not bypass it or introduce
  background work outside its ownership model.
- Strict source evidence, data-quality, measured-transport, manifest, and
  duplicate guards fail closed. Never silently deduplicate, discard evidence,
  or change identity just to make a run pass.
- Manipulation is evidence and context, not an automatic action outcome. Keep
  observed outcomes distinct from realistically executable opportunity outcomes;
  never replace this distinction with a score, rank, or hindsight reconstruction.
- Clean memory only: stale, incomplete, dirty, conflicting, or missing-critical
  evidence must not become decision-training memory.
- Capability sequencing stays locked: `WINDOW_5M` is support-only and
  `WINDOW_12H`/`WINDOW_24H` remain locked. Do not unlock capabilities without
  a deliberate approved change to the active authority and code. A future
  paper BUY/SELL/HOLD, position, audit, or PnL capability stays locked until
  its enforced gates are deliberately approved; no document alone enables it.
- No scoring/ranking/confidence points may decide action. V1 decisions remain
  memory-backed and paper-only.

## Operational execution boundary

Operational execution is exceptional, not a normal development check. Before
it, code/preflight must prove the exact repository HEAD and authoritative DB
identity, migration health, DB integrity/FK health where relevant, zero active
work, and explicit operator approval.

One-shot authorization remains mandatory for an operational execution:

- it binds exact HEAD and DB identity;
- application consumes it once;
- every consumed, stale, or otherwise non-reusable authorization remains
  permanently non-reusable and is included by the canonical prior-non-reuse
  validator;
- no retry, rerun, resume, restart, or successor is inferred from a prior run.

Development tests must use disposable state. Do not mutate the authoritative DB
unless the user has authorized that exact operation. Never run Printer, contact
providers/RPC/WebSockets, or run Central Scheduler operationally unless the
user has explicitly authorized that action.

## Documentation

Document an API, protocol, source contract, safety invariant, or user-visible
behavior when it helps future engineering. Keep `CURRENT_HANDOFF.md` short.
Do not require PASS chains, readiness documents, closeouts, state
synchronization, or separate bookkeeping as a condition of ordinary work.
