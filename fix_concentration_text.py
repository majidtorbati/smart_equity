from pathlib import Path

p = Path("app/ui/main_window.py")
lines = p.read_text(encoding="utf-8").splitlines(True)

count = 0

for i, line in enumerate(lines):
    if "self.buyer_concentration_box = QGroupBox(" in line:
        lines[i + 1] = (
            '            "\u062a\u0645\u0631\u06a9\u0632 \u062e\u0631\u06cc\u062f\u0627\u0631\u0627\u0646 \u2014 Top 1 / 5 / 10"\n'
        )
        count += 1

    elif "self.buyer_concentration_layout.addWidget(" in line:
        lines[i + 1] = (
            '            QLabel("\u062e\u0644\u0627\u0635\u0647 \u062a\u0645\u0631\u06a9\u0632 \u062e\u0631\u06cc\u062f\u0627\u0631\u0627\u0646")\n'
        )
        count += 1

    elif "self.seller_concentration_box = QGroupBox(" in line:
        lines[i + 1] = (
            '            "\u062a\u0645\u0631\u06a9\u0632 \u0641\u0631\u0648\u0634\u0646\u062f\u06af\u0627\u0646 \u2014 Top 1 / 5 / 10"\n'
        )
        count += 1

    elif "self.seller_concentration_layout.addWidget(" in line:
        lines[i + 1] = (
            '            QLabel("\u062e\u0644\u0627\u0635\u0647 \u062a\u0645\u0631\u06a9\u0632 \u0641\u0631\u0648\u0634\u0646\u062f\u06af\u0627\u0646")\n'
        )
        count += 1

p.write_text("".join(lines), encoding="utf-8")

print(f"OK - repaired {count} concentration texts")