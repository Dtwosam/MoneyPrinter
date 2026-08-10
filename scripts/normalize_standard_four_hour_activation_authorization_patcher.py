from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
old = '''    start_index = text.find(start)\n    if start_index < 0:\n        raise RuntimeError(f"start anchor missing in {path}: {start!r}")\n    end_index = text.find(end, start_index + len(start))\n    if end_index < 0:\n        raise RuntimeError(f"end anchor missing in {path}: {end!r}")\n'''
new = '''    start_index = text.find(start)\n    if start_index < 0 and start.endswith("(\\n"):\n        start_index = text.find(start[:-1])\n    if start_index < 0:\n        raise RuntimeError(f"start anchor missing in {path}: {start!r}")\n    end_index = text.find(end, start_index + 1)\n    if end_index < 0 and end.endswith("(\\n"):\n        end_index = text.find(end[:-1], start_index + 1)\n    if end_index < 0:\n        raise RuntimeError(f"end anchor missing in {path}: {end!r}")\n'''
if old not in text:
    raise RuntimeError("disposable Slice B patcher helper anchor missing")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
