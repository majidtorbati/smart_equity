# ARCHITECTURE — FINAL

GUI: PySide6
DB: SQLite
Import: pandas/openpyxl
Reports: reportlab / python-pptx / openpyxl
Analysis: metrics, HHI, anomaly, behavior, market maker, registry reconciliation, FIFO
AI: `app/ai/assistant.py`
Runtime paths: `app/core/runtime.py`

Portable rule:
- read-only bundled resources are under PyInstaller resource root
- writable DB/config/assets/exports are under runtime root beside the EXE

AI provider order is deterministic and fail-safe.
