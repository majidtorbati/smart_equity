@echo off
setlocal
REM ============================================================
REM SmartEquity — Final Portable Build (Windows)
REM Python 3.12 x64 فقط برای ساخت لازم است؛ روی PC مقصد Python لازم نیست.
REM خروجی: dist\SmartEquity\SmartEquity.exe + کل پوشه قابل حمل
REM ============================================================

cd /d "%~dp0"

echo [1/5] Checking Python 3.12...
py -3.12 --version
if errorlevel 1 (
    echo.
    echo *** Python 3.12 x64 was not found. ***
    pause
    exit /b 1
)

if not exist "build_venv\Scripts\python.exe" (
    echo [2/5] Creating build virtual environment...
    py -3.12 -m venv build_venv
    if errorlevel 1 exit /b 1
) else (
    echo [2/5] Reusing build virtual environment...
)

call "build_venv\Scripts\activate.bat"
if errorlevel 1 exit /b 1

python -m pip install --upgrade pip
if errorlevel 1 exit /b 1

python -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

echo [3/5] Running test suite...
python -m pytest tests -v
if errorlevel 1 (
    echo.
    echo *** TESTS FAILED — build stopped. ***
    pause
    exit /b 1
)

echo [4/5] Cleaning previous PyInstaller output...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

python -m PyInstaller build.spec --noconfirm --clean
if errorlevel 1 (
    echo.
    echo *** PyInstaller build FAILED. ***
    pause
    exit /b 1
)

if not exist "dist\SmartEquity\SmartEquity.exe" (
    echo.
    echo *** EXE was not created. ***
    pause
    exit /b 1
)

echo [5/5] Writing portable package information...
> "dist\SmartEquity\PORTABLE_README.txt" echo SmartEquity Transaction Intelligence - Portable
>>"dist\SmartEquity\PORTABLE_README.txt" echo.
>>"dist\SmartEquity\PORTABLE_README.txt" echo Run SmartEquity.exe. Do not move only the EXE; copy the entire SmartEquity folder.
>>"dist\SmartEquity\PORTABLE_README.txt" echo Data, settings and exported reports are stored beside the EXE.
>>"dist\SmartEquity\PORTABLE_README.txt" echo On first run, choose the shareholder registry first, then the daily buy/sell Excel file.
>>"dist\SmartEquity\PORTABLE_README.txt" echo AI priority: local Ollama, local OpenAI-compatible endpoint, OpenAI internet API, built-in analysis.

for /f "delims=" %%A in ('powershell -NoProfile -Command "(Get-Item 'dist\SmartEquity\SmartEquity.exe').Length"') do set EXESIZE=%%A

echo.
echo ============================================================
echo BUILD SUCCESSFUL
 echo Portable folder: %CD%\dist\SmartEquity\
echo EXE size: %EXESIZE% bytes
echo Copy the ENTIRE SmartEquity folder to USB/another Windows PC.
echo ============================================================
pause
endlocal
