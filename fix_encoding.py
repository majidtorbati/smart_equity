from pathlib import Path

path = Path(r".\app\ui\main_window.py")

text = path.read_text(encoding="utf-8-sig")

text = text.replace("â€”", "—")

path.write_text(text, encoding="utf-8-sig")

print("Dash encoding fixed.")