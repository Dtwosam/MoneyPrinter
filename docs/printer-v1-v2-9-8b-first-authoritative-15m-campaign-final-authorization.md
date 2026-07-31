# Printer V1 V2-9.8B First Authoritative WINDOW_15M Campaign Final Authorization

Date: 2026-07-30

Reviewed launch commit:
`b5761b6501ad757eecdfc8cfabce6828d5a899bd`

Verdict:
`V2_9_8B_FIRST_AUTHORITATIVE_15M_CAMPAIGN_FINAL_AUTHORIZATION_PASS`

## Boundary

This review is read-only and documentation-only. It did not run the campaign,
contact providers/RPC, fetch sources, create the one-attempt marker, mutate the
authoritative database, generate memory, start a 1h or longer window, activate
retrieval, or create any paper/financial capability.

## Evidence Reviewed

- exact clean and synchronized local/remote Git commit
  `b5761b6501ad757eecdfc8cfabce6828d5a899bd`;
- canonical public command registration;
- committed policy: two tokens, `WINDOW_15M`, 1h/4h/12h/24h locked, zero retries;
- authoritative DB target and external artifact root;
- absent one-attempt marker;
- absent SQLite WAL/SHM/journal sidecars;
- present and loadable operator secrets file without exposing values;
- valid approved HTTPS Solana RPC configuration with redacted identity;
- optional Helius backup present;
- zero-source `preflight-only` PASS;
- migration count 49 and head `049_candidate_acquisition_integration.sql`;
- database integrity `ok` and zero foreign-key violations;
- zero active campaigns, runs, supervision, discovery work, Scheduler jobs/locks,
  factory steps, and proof supervision;
- preserved retrieval/financial baselines;
- authoritative DB SHA-256 unchanged before/after:
  `e748ba505cb8c7d67b8feb3a09b97719a0f3560e41dfb9242570cff3157962e6`;
- final repository remained clean;
- campaign invoked: no; attempt marker created: no; providers contacted: no;
  intentional DB writes: no.

## Authorization

Exactly one first authoritative ordinary `WINDOW_15M` campaign attempt is
authorized from the reviewed launch commit only.

The attempt must:

- run from repository root on clean synchronized `master` at the exact commit;
- load the approved operator environment without printing secret values;
- rerun a fresh zero-source preflight immediately before launch;
- stop before launch if any preflight or identity check fails;
- create the permanent external one-attempt marker immediately before invoking
  the campaign command;
- invoke the canonical foreground `run --operator-approved` command exactly once;
- capture stdout/stderr, exit code, marker, DB hashes, execution directory,
  terminal report, status, report-only replay, post-terminal preflight, and final
  Git state outside the repository;
- never retry, restart, launch a successor, run discovery-only, recover, reset a
  cursor, or start selective 1h work;
- proceed next only to evidence review and campaign closeout.

## Exact Launch Baseline

The campaign must launch from:

```text
b5761b6501ad757eecdfc8cfabce6828d5a899bd
```

This authorization document is intentionally held on a separate branch before
campaign execution. Merging it first would change `master` and invalidate the
reviewed launch commit.

## One-Attempt Marker

Exact path:

```text
$HOME/PrinterOperations/v2-9-8/first-authoritative-window-15m-attempt.json
```

If that path exists before launch, the campaign is not authorized to run.

## Factual Outcomes

The single attempt may close only as:

- `V2_9_8B_FIRST_AUTHORITATIVE_15M_CAMPAIGN_PASS`;
- `V2_9_8B_FIRST_AUTHORITATIVE_15M_CAMPAIGN_BLOCKED`; or
- `V2_9_8B_FIRST_AUTHORITATIVE_15M_CAMPAIGN_BLOCKED_UNSAFE`.

No outcome authorizes a rerun.

## Money-Usefulness Contribution

This authorization permits one bounded opportunity to add durable 15m
paper-only learning while preserving prior evidence, honest shortages, dirty and
blocked reasons, and every retrieval/financial lock.

## What This Improves

- pins one exact launch commit;
- proves current operator/environment readiness without source calls;
- establishes a permanent no-rerun marker;
- requires complete terminal evidence and separate closeout.

## What Remains Locked

All further campaigns, 1h/4h/12h/24h work, V2-10, retrieval, paper decisions,
BUY/SELL/HOLD, positions, trades, audits, PnL, wallets, private keys, signing,
real funds, paid APIs, scoring, ranking, confidence, weighting, embeddings, and
vectors remain locked.

## Functionality Risks / Setbacks / Efficiency Blockers

- providers may fail or two eligible tokens may not be found;
- local environment can drift between review and launch;
- operator interruption can produce ambiguous state;
- any temptation to retry after an honest block would violate this authorization;
- the campaign exit code alone is insufficient; closeout must inspect durable
  evidence and preservation.

## Exact Next Permitted Task

```text
Execute exactly one first authoritative WINDOW_15M campaign attempt from the
reviewed launch commit, then stop for evidence review and closeout.
```
