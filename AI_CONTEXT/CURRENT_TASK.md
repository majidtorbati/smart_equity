# CURRENT TASK — FINALIZED

The project now supports a combined initial import workflow:
1. shareholder registry (required first)
2. daily buy/sell transactions

The registry is used as opening ownership input for FIFO and reconciliation.
The project database is preserved on application close; starting a new company/symbol uses the project import button again.

Reports:
- PDF: Persian RTL verified visually.
- PowerPoint: Persian RTL, Tahoma set for Latin/East-Asia/Complex-Script, 16 slides including Registry/FIFO.
- Excel: RTL on all sheets, print setup, freeze panes, filters, numeric formatting, Registry/FIFO and identity reconciliation sheets.

AI routing:
- Ollama local first
- local OpenAI-compatible endpoint second
- OpenAI internet API if `OPENAI_API_KEY` is available
- deterministic SmartEquity built-in analysis as final fallback

No API key is bundled in the project.
