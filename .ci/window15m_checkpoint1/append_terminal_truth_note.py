from pathlib import Path

path = Path(
    "docs/printer-v1-v2-9-8b-window-15m-checkpoint-1-terminal-propagation-closeout.md"
)
text = path.read_text(encoding="utf-8")
text = text.replace(
    "One reachable reporting defect and three related trust-boundary defects were confirmed and repaired.",
    "One reachable reporting defect and four related trust-boundary defects were confirmed and repaired.",
    1,
)
needle = '''4. The initial child binding used the marker's current hash rather than requiring the exact marker SHA already validated and supplied by the wrapper.\n\nNo wrapper authorization-consumption'''
replacement = '''4. The initial child binding used the marker's current hash rather than requiring the exact marker SHA already validated and supplied by the wrapper.\n5. If action-local terminal-truth reconstruction raised while handling the original campaign exception, that secondary failure escaped the exception handler and prevented `child-terminal.json` from being written, returning diagnosis to stderr-only evidence.\n\nNo wrapper authorization-consumption'''
if needle not in text:
    raise SystemExit("confirmed finding insertion anchor missing")
text = text.replace(needle, replacement, 1)
needle = '''- Child writes failure evidence only after the public command has completed its own terminalization/cleanup path and the action-local truth envelope has been built.\n- Wrapper enforces'''
replacement = '''- Child writes failure evidence only after the public command has completed its own terminalization/cleanup path and the action-local truth envelope has been built.\n- If terminal-truth reconstruction itself fails, the original campaign exception remains the first cause; the secondary reconstruction error is bounded separately, mutation/source/write truth becomes explicitly unknown rather than fabricated, and the child terminal is still written.\n- Wrapper enforces'''
if needle not in text:
    raise SystemExit("repair insertion anchor missing")
text = text.replace(needle, replacement, 1)
text = text.replace(
    "Four distinct RED gates were observed before their repairs:",
    "Five distinct RED gates were observed before their repairs:",
    1,
)
needle = '''4. marker drift after wrapper validation was not rejected by the child binding.\n\n- focused terminal/wrapper tests:'''
replacement = '''4. marker drift after wrapper validation was not rejected by the child binding;\n5. a secondary action-local terminal-truth reconstruction exception erased the structured child artifact and allowed the original campaign cause to escape back to stderr-only evidence.\n\n- focused terminal/wrapper tests:'''
if needle not in text:
    raise SystemExit("RED gate insertion anchor missing")
text = text.replace(needle, replacement, 1)
needle = '''- exact binding to wrapper-validated marker bytes;\n- strict envelope allowlisting'''
replacement = '''- exact binding to wrapper-validated marker bytes;\n- preservation of the original campaign cause when secondary terminal-truth reconstruction fails;\n- explicit `RECONSTRUCTION_FAILED` evidence without fabricated source/write/cleanup counts;\n- strict envelope allowlisting'''
if needle not in text:
    raise SystemExit("improvement insertion anchor missing")
text = text.replace(needle, replacement, 1)
path.write_text(text, encoding="utf-8")
print("terminal-truth reconstruction note appended")
