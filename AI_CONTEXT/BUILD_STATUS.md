# BUILD STATUS — FINAL

- Python build target: 3.12 x64
- PyInstaller: 6.11.1
- Build mode: one-folder portable
- Build command: `build.bat`
- Final EXE: `dist\SmartEquity\SmartEquity.exe`
- The whole `dist\SmartEquity` folder must be copied to another PC.
- Runtime database/settings/exports are stored beside the EXE, not inside PyInstaller's read-only resource area.
- NumPy is explicitly collected in `build.spec` to prevent the previous `numpy._core._exceptions` runtime error.
- Tests requiring a real imported market database are skipped only when no DB exists; when a DB exists they execute normally.
