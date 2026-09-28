"""
Smart Equity Transaction Intelligence — نقطه ورود اصلی برنامه.
اجرا: python app/main.py   (یا از طریق SmartEquity.exe در نسخه پرتابل)
"""
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.ui.main_window import main

if __name__ == "__main__":
    main()
