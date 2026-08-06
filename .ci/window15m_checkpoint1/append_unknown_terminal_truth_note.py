from pathlib import Path

path = Path(
    "docs/printer-v1-v2-9-8b-window-15m-checkpoint-1-terminal-propagation-closeout.md"
)
text = path.read_text(encoding="utf-8")
text = text.replace(
    "One reachable reporting defect and four related trust-boundary defects were confirmed and repaired.",
    "One reachable reporting defect and five related trust-boundary defects were confirmed and repaired.",
    1,
)
needle = '''5. If action-local terminal-truth reconstruction raised while handling the original campaign exception, that secondary failure escaped the exception handler and prevented `child-terminal.json` from being written, returning diagnosis to stderr-only evidence.\n\nNo wrapper authorization-consumption'''
replacement = '''5. If action-local terminal-truth reconstruction raised while handling the original campaign exception, that secondary failure escaped the exception handler and prevented `child-terminal.json` from being written, returning diagnosis to stderr-only evidence.\n6. The first reconstruction-failure fallback still coerced unavailable lifecycle, active-work, Scheduler, and phase facts into `False`, `{}`, `0`, and `CAMPAIGN_PRE_LIFECYCLE`, creating false certainty after the truth owner had failed.\n\nNo wrapper authorization-consumption'''
if needle not in text:
    raise SystemExit("sixth finding insertion anchor missing")
text = text.replace(needle, replacement, 1)
needle = '''- If terminal-truth reconstruction itself fails, the original campaign exception remains the first cause; the secondary reconstruction error is bounded separately, mutation/source/write truth becomes explicitly unknown rather than fabricated, and the child terminal is still written.\n- Wrapper enforces'''
replacement = '''- If terminal-truth reconstruction itself fails, the original campaign exception remains the first cause; the secondary reconstruction error is bounded separately, mutation/source/write truth becomes explicitly unknown rather than fabricated, and the child terminal is still written.\n- Reconstruction failure now preserves lifecycle, active-work, Scheduler, cleanup, lease, database-identity, and phase facts as explicitly unknown unless independently proven; the phase is classified `CAMPAIGN_PHASE_UNKNOWN_TERMINAL_TRUTH_RECONSTRUCTION_FAILED` rather than guessed.\n- Wrapper enforces'''
if needle not in text:
    raise SystemExit("sixth repair insertion anchor missing")
text = text.replace(needle, replacement, 1)
text = text.replace(
    "Five distinct RED gates were observed before their repairs:",
    "Six distinct RED gates were observed before their repairs:",
    1,
)
needle = '''5. a secondary action-local terminal-truth reconstruction exception erased the structured child artifact and allowed the original campaign cause to escape back to stderr-only evidence.\n\n- focused terminal/wrapper tests:'''
replacement = '''5. a secondary action-local terminal-truth reconstruction exception erased the structured child artifact and allowed the original campaign cause to escape back to stderr-only evidence;\n6. reconstruction failure fabricated unavailable lifecycle, active-work, Scheduler, and campaign-phase facts instead of preserving them as unknown.\n\n- focused terminal/wrapper tests:'''
if needle not in text:
    raise SystemExit("sixth RED gate insertion anchor missing")
text = text.replace(needle, replacement, 1)
text = text.replace(
    "- explicit `RECONSTRUCTION_FAILED` evidence without fabricated source/write/cleanup counts;",
    "- explicit `RECONSTRUCTION_FAILED` evidence without fabricated source, write, lifecycle, active-work, Scheduler, cleanup, lease, database-identity, or phase facts;",
    1,
)
needle = '''- A child killed before handled shutdown may not produce an envelope; the wrapper reports terminal-invalid while preserving stdout/stderr and exit code.\n'''
replacement = '''- A child killed before handled shutdown may not produce an envelope; the wrapper reports terminal-invalid while preserving stdout/stderr and exit code.\n- When action-local reconstruction fails, several operational facts remain intentionally `null`; later checkpoints must inspect their durable owners rather than treating unknown as zero.\n'''
if needle not in text:
    raise SystemExit("sixth risk insertion anchor missing")
text = text.replace(needle, replacement, 1)
path.write_text(text, encoding="utf-8")
print("unknown terminal-truth closeout note appended")
