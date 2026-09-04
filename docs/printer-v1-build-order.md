# Printer V1 Build Order

## Operating principle

Build the smallest useful, safe piece of the paper-only Solana memecoin memory
machine. Preserve code-enforced safety and evidence contracts; do not add
documentation ceremony around ordinary engineering work.

## Capability order

1. Maintain safety boundaries, schema health, source/data-quality contracts,
   and clean-memory integrity.
2. Maintain governed discovery, validation, selection, and durable evidence
   ownership through Source Governor and Central Scheduler.
3. Maintain paper-only lifecycle, realistic liquidity/exit evidence, episodes,
   memory, and paper-decision auditability.
4. Improve the smallest proven blocker in the active capability path with a
   focused regression and review.
5. Keep `WINDOW_5M` support-only and `WINDOW_12H`/`WINDOW_24H` locked unless a
   deliberate capability decision changes both active authority and code.

## How to choose work

- Prefer a proven defect or the smallest missing part of an existing flow.
- Distinguish code defects from provider scarcity, missing evidence, and honest
  market blocks before changing code.
- Use a short design only when the change is architectural, ambiguous,
  schema-related, or safety-critical.
- Normal work ends after focused verification and actual diff review. Do not
  create a separate readiness or closeout lane for ordinary changes.

## Operational boundary

Development proof is not operational authority. A real operational execution
requires the existing code/preflight checks for exact HEAD/DB binding, DB
health, zero active work, one-shot authorization, and explicit operator
approval. A consumed authorization is permanently non-reusable.
