# Qualified Random Active-Token Selection Design

## Status

ADOPTED FOR THIS GATED V2-2 LANE. V2-3 remains paused.

## Audit Finding

The production handoff at commit `88f73e1` ran cooldown gates and then treated
historical category quotas as a hard gate. Those quotas required outcomes such
as A2/A3/A4, decay, D1, and WATCH_ONLY to exist before observation. This forced
future trajectory outcomes into starting-batch composition and could reject an
otherwise clean active pool.

## Adopted Rule

Printer uniformly selects from a bounded pool of clean, actively traded Solana
memecoins, then learns from their natural state transitions over time.

Eligibility remains fail-closed: exact Solana mint/pair identity, governed
source trace, acceptable source status and data quality, TRACK_FAST or
TRACK_NORMAL, existing liquidity/activity acceptance, no infrastructure mint,
no unresolved STNP, deduplication, persistence gate, cooldown, and rotation.
WATCH_ONLY, D1, and inactive candidates remain audit evidence.

Candidates are sorted by exact mint/pair identity, shuffled by one persisted
seed, and sampled without category preference. The same universe and seed must
reproduce the same result. No score, rank, confidence, weight, or bucket
preference is used.

Historical category quotas remain visible as diagnostics. Repeated exact
mint/pair observations provide categorical trajectory coverage for
continuation, failed pump, dumping/decay, death/inactivity, revival,
consolidation, and liquidity removal. Reporting is read-only and creates no
collection, scheduler, memory, retrieval, decision, or financial work.

## Stop Conditions

No eligible active candidate means a rejected selection batch and zero active
handoffs. Unsafe, dirty, stale, untraced, duplicate, unresolved-STNP,
WATCH_ONLY, D1, or inactive candidates cannot be selected.

## Locks

This adoption does not enable scheduler execution, snapshots, memory,
retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL,
wallets, keys, paid APIs, embeddings, or vectors.
