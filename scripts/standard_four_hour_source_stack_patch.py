from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one anchor, found {count}")
    return text.replace(old, new, 1)


files = {
    "agents": Path("AGENTS.md"),
    "guide": Path("docs/printer-v1-memory-factory-guide.md"),
    "build": Path("docs/printer-v1-memory-growth-build-order-v2.md"),
    "anchor": Path("docs/printer-v1-assistant-active-build-order-anchor.md"),
}
texts = {name: path.read_text(encoding="utf-8") for name, path in files.items()}

texts["agents"] = replace_once(
    texts["agents"],
'''The post-V2-9 operational Memory Factory program must preserve selective continuation:

- discovery -> selection -> tracking -> governed collection
- conditional WINDOW_5M_MICRO_EVENT support
- main WINDOW_15M closeout
- selective WINDOW_1H continuation
- conditional WINDOW_4H continuation
- clean/dirty/blocked audit
- cooldown/archive
- candidate rotation
- persistent corpus reporting
- safe stop
''',
'''The post-V2-9 operational Memory Factory program must preserve bounded lifecycle continuation:

- discovery -> selection -> tracking -> governed collection
- conditional WINDOW_5M_MICRO_EVENT support
- main WINDOW_15M closeout
- standard hard-gated WINDOW_1H continuation for otherwise-valid activated tokens
- standard hard-gated WINDOW_4H continuation after a genuine eligible first-hour close
- automatic continuation stops at the WINDOW_4H checkpoint
- WINDOW_12H / WINDOW_24H remain selective and locked until later explicit lanes
- clean/dirty/blocked audit
- cooldown/archive
- candidate rotation
- persistent corpus reporting
- safe stop

The post-DTW100 standard-four-hour amendment removes behavior/outcome/learning-need qualification only from 15m->1h and 1h->4h observation. It does not weaken exact identity, evidence quality, freshness, provenance, safety, continuity, campaign health, cancellation, Source Governor, Central Scheduler, or bounded-resource gates. `WINDOW_4H` real collection remains locked until its later explicit activation/rereadiness lane.
''',
    "AGENTS standard-four-hour lifecycle anchor",
)

texts["guide"] = replace_once(
    texts["guide"],
'''-> main WINDOW_15M closeout
-> selective WINDOW_1H continuation
-> conditional WINDOW_4H continuation
-> clean/dirty/blocked audit
''',
'''-> main WINDOW_15M closeout
-> standard hard-gated WINDOW_1H continuation
-> standard hard-gated WINDOW_4H continuation
-> clean/dirty/blocked audit
''',
    "guide workflow",
)
texts["guide"] = replace_once(
    texts["guide"],
'''- first 15m snapshots every 5-10 minutes
- open 15m main memory
- open 1h only if token remains useful/eligible after 15m
- slow down if activity fades
''',
'''- first 15m snapshots every 5-10 minutes
- open 15m main memory
- continue through the first hour and to the 4h checkpoint when hard operational/evidence gates remain valid; outcome or learning-need labels do not qualify continuation
- cadence may slow after the opening period according to the approved Scheduler policy, but observation does not stop merely because activity fades
''',
    "guide TRACK_NORMAL",
)
texts["guide"] = replace_once(
    texts["guide"],
'''- first 15m snapshots every 1-3 minutes if source capacity allows
- open 5m support evidence
- open 15m main memory
- continue to 1h if token survives and data remains useful
- speed up around dumps, liquidity decay, revival, or exit danger
''',
'''- first 15m snapshots every 1-3 minutes if source capacity allows
- open 5m support evidence
- open 15m main memory
- continue through the first hour and to the 4h checkpoint when hard operational/evidence gates remain valid; survival, outcome, or learning-need labels do not qualify continuation
- speed up around dumps, liquidity decay, revival, or exit danger when the approved Scheduler policy allows
''',
    "guide TRACK_FAST",
)
texts["guide"] = replace_once(
    texts["guide"],
'''- only after useful early windows
- eligible for 4h, 12h, or 24h tracking
- not for every token
- prioritize tokens that teach survival, revival, delayed dump, or full-cycle outcomes
''',
'''- applied only after the standard 4h checkpoint for later long-horizon learning
- eligible for future 12h or 24h tracking only in their separately approved selective lanes
- not every token proceeds beyond 4h
- prioritize later-horizon lessons such as survival, revival, delayed dump, or full-cycle outcomes without turning the category into a score or ranking
''',
    "guide long-window candidate",
)
texts["guide"] = replace_once(
    texts["guide"],
'''4h should start after 1h memory is clean and scheduler/source capacity is stable.
''',
'''Under the post-DTW100 standard-four-hour policy, every otherwise-valid activated token with a genuine eligible first-hour predecessor continues to the 4h checkpoint. Outcome and learning-need labels do not qualify that continuation. Real 4h collection still requires the later explicit campaign-integration/rereadiness activation gate; this policy statement alone does not enable runtime.
''',
    "guide 4h role",
)
texts["guide"] = replace_once(
    texts["guide"],
'''Do not activate all timeframes at once. Preserve selective continuation: not every token should receive every timeframe. Continue only when evidence quality, learning value, source budget, and token/pair continuity justify the next window.
''',
'''Do not activate all timeframes at once. The adopted bounded observation lifecycle is standard through the 4h checkpoint for otherwise-valid activated tokens: 15m and 1h outcome/learning-need labels do not decide whether observation continues. Hard evidence-quality, exact-identity, freshness, provenance, safety, continuity, Source Governor, Central Scheduler, cancellation, and bounded-resource gates still apply. Automatic continuation stops at 4h; 12h and 24h remain selective and locked until later explicit lanes.
''',
    "guide activation policy",
)

texts["build"] = replace_once(
    texts["build"],
'''- Preserves selective continuation so source budget is spent on useful tokens,
  not every timeframe for every token.
''',
'''- Preserves bounded continuation under the post-DTW100 amendment: every
  otherwise-valid activated token is observed through the 4h checkpoint, while
  hard evidence/identity/safety/continuity/resource gates remain fail-closed and
  12h/24h continuation remains selective and separately locked.
''',
    "build-order program improvement",
)
texts["build"] = replace_once(
    texts["build"],
'''- Use selective continuation rather than every timeframe for every token.
''',
'''- Use the adopted standard first-four-hour lifecycle for otherwise-valid activated tokens; automatic continuation stops at 4h, and later 12h/24h windows remain selective and separately approved.
''',
    "build-order operational rule",
)

texts["anchor"] = replace_once(
    texts["anchor"],
'''Selectivity begins after 1h. `WINDOW_1H -> WINDOW_4H` and later approved transitions remain selective. `WINDOW_12H` and `WINDOW_24H` remain locked.

Controlling design:

- `docs/printer-v1-v2-9-8b-post-dtw100-first-hour-lifecycle-policy-design.md`
''',
'''The bounded observation lifecycle now extends through the 4h checkpoint. After a genuine eligible first-hour close, every otherwise-valid activated token continues to `WINDOW_4H`; 1h outcome, direction, profitability, trajectory class, manipulation label, and learning-need presence/absence have no authority to qualify that observation. Hard identity, evidence quality, freshness, provenance, safety, continuity, campaign health, cancellation, Source Governor, Central Scheduler, and bounded-resource gates remain fail-closed.

Automatic continuation stops at `WINDOW_4H`. `WINDOW_12H` and `WINDOW_24H` remain selective and locked. `WINDOW_4H` real collection also remains disabled until the separately approved campaign-integration implementation, offline proof, closeout, and later operational rereadiness/activation gate pass.

Controlling designs:

- `docs/printer-v1-v2-9-8b-post-dtw100-first-hour-lifecycle-policy-design.md`
- `docs/printer-v1-v2-9-8b-post-dtw100-standard-four-hour-lifecycle-policy-campaign-integration-design.md`
''',
    "assistant active four-hour policy",
)

for name, path in files.items():
    path.write_text(texts[name], encoding="utf-8")
