from pathlib import Path

p = Path("audit_readonly.py")
s = p.read_text(encoding="utf-8")

s = s.replace(
    'print("Minimum transactions/day:", f"{r[\'min_tx_day\']:,}")',
    'print("Minimum transactions/day:", r["min_tx_day"])'
)
s = s.replace(
    'print("Maximum transactions/day:", f"{r[\'max_tx_day\']:,}")',
    'print("Maximum transactions/day:", r["max_tx_day"])'
)
s = s.replace(
    'print("Average transactions/day:", f"{r[\'avg_tx_day\']:,.2f}")',
    'print("Average transactions/day:", r["avg_tx_day"])'
)

p.write_text(s, encoding="utf-8")
print("AUDIT_FIXED")
