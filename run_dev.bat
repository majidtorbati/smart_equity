@echo off
REM اجرای برنامه در حالت توسعه (بدون build گرفتن exe) — برای تست سریع روی ویندوز
if not exist build_venv (
    echo Creating virtual environment...
    python -m venv build_venv
)
call build_venv\Scripts\activate.bat
pip install -r requirements.txt -q
python app\main.py
