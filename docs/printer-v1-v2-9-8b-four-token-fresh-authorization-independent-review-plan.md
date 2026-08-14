# Printer V1 V2-9.8B Fresh Four-Token Authorization Independent Review Plan

Date: 2026-08-14

## Scope

Read-only independent review of `V2_9_8B_FOUR_TOKEN_PROOF_AUTH_20260814T171249Z_0022b4dc` only.

Review against the exact authorized launch state:

- branch: `agent/v2-9-8b-four-token-fresh-authorization-preparation`
- HEAD: `aa5ab488c74b90ba57b1ca8e390bb50507609537`
- authorization SHA-256: `4a8160309d97226bc1f005376e1ae95e0b8212ccd2a4e84b21bdd50b01a7524b`

## Minimum sufficient review

1. exact authorization file/hash/package resolution and document validation;
2. temporal validity and exact four-token 4/2/2 one-shot policy;
3. current migration-055 plus explicit historical authorization/migration evidence can be built in memory;
4. authoritative DB identity remains bound and unchanged;
5. fresh zero-state is ready and no Printer runtime process exists;
6. no application/consumption state exists for the authorization;
7. no manifest or marker is written and Printer is not launched.

## Decision rule

Any drift, expiry, malformed provenance chain, active work/process, DB mismatch, application state, or repository mismatch blocks review. PASS permits only a later separately controlled one-shot application/run step.

## Locks

No source fetching, memory generation, 12h/24h activation, retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, audits, PnL, live wallet, private keys, real funds, or paid API dependency.