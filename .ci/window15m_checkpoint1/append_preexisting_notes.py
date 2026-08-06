from pathlib import Path

path = Path(
    "docs/printer-v1-v2-9-8b-window-15m-checkpoint-1-terminal-propagation-closeout.md"
)
text = path.read_text(encoding="utf-8")
start = text.index("## Unrelated pre-existing failure\n")
end = text.index("\n## Runtime and evidence boundary\n", start)
replacement = '''## Unrelated pre-existing failures

The following historical tests failed for reasons that predate and are unrelated
to the reporting-only Checkpoint 1 diff. They were documented and excluded by
exact node rather than repaired or used to broaden scope.

1. Broad readiness collection failure:

```text
tests/test_v2_9_8b_window_15m_final_integrated_readiness_repair.py
ImportError: cannot import name '_attach_fingerprint_for_episode'
from printer_v1.operator_cli.lane_k_e2z_pipeline_wiring
```

2. One historical ordinary-regression test omits the now-required operational DB
target binding and blocks with:

```text
OPERATIONAL_DB_BINDING_MISSING: database target binding
```

3. Seven historical campaign-terminal assertions require migration head `050`,
while the active migrated repository head is `052_memory_observation_eligibility_layers.sql`.
The terminal behavior preceding those stale head assertions passed.

Before exact deselection, the neighboring run produced:

```text
141 passed, 22 subtests passed, 8 failed
```

The eight failures were exactly the one missing-binding node and seven stale
migration-head nodes above. All remaining exact terminal-neighbor tests remained
mandatory in the final proof.
'''
path.write_text(text[:start] + replacement + text[end:], encoding="utf-8")
print("pre-existing neighboring test notes appended")
