from pathlib import Path

path = Path("/tmp/apply_repair.py")
text = path.read_text(encoding="utf-8")
old = '''    count = text.count(old)\n    if count != 1:\n        raise SystemExit(f"{label}: expected one match, found {count}")\n    return text.replace(old, new, 1)\n'''
new = '''    count = text.count(old)\n    if label == "child success terminal write" and count == 2:\n        head, separator, tail = text.rpartition(old)\n        if not separator:\n            raise SystemExit(f"{label}: final public main match missing")\n        return head + new + tail\n    if count != 1:\n        raise SystemExit(f"{label}: expected one match, found {count}")\n    return text.replace(old, new, 1)\n'''
if text.count(old) != 1:
    raise SystemExit("replace_once implementation anchor mismatch")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
print("applicator narrowed to final public main occurrence")
