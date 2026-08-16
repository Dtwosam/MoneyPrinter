# V2-9.8B Persistent Fresh Acquisition Implementation Plan

Starting design commit: `c9fb16b8f214e4e527f574e7c7dcbeb5cf351455`

1. Add migration 057 for additive per-refresh work ownership; keep legacy `printer_discovery_work` unchanged.
2. Add persistence helpers for refresh-work create/terminalize/read.
3. RED tests: two refresh ordinals in one cycle; active-work cleanup sees refresh work.
4. Update temporal refresh owner to create one refresh-work row after exact Scheduler claim and allow later ordinals.
5. Extend acquisition horizon from 900s to 2400s; preserve canonical 600s Scheduler cadence and cumulative budget.
6. Refactor production refresh composition to reuse existing Pump, DexScreener, GeckoTerminal, liquidity-backup and protocol-confirmation owners with ordinal-only categorical rotation.
7. RED/GREEN tests for multi-source continuation, candidate-local failure isolation, no budget reset, capacity stop, dedup and lawful terminal exhaustion.
8. Run focused tests, then one fixture-only disposable proof with >=2 refresh ordinals and no external provider calls.
9. Run broad regression only at closeout because Scheduler ownership + schema changed. Document unrelated pre-existing failures without expanding scope automatically.
10. Write closeout. Do not run live discovery, mutate the authoritative DB, create authorization, or rerun four-token proof.
