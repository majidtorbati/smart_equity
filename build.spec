# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec — SmartEquity Portable Build.
این فایل باید روی خودِ ویندوز با دستور زیر اجرا شود (نه از لینوکس):
    pyinstaller build.spec
خروجی در dist/SmartEquity/ ساخته می‌شود که کاملاً پرتابل است.
"""
import sys
import pathlib
from PyInstaller.utils.hooks import collect_all

numpy_datas, numpy_binaries, numpy_hiddenimports = collect_all('numpy')

block_cipher = None
ROOT = pathlib.Path(SPECPATH).resolve()

a = Analysis(
    ['app/main.py'],
    pathex=[str(ROOT)],
    binaries=numpy_binaries,
    datas=numpy_datas + [
        ('assets/Vazirmatn-Regular.ttf', 'assets'),
        ('assets/Vazirmatn-Bold.ttf', 'assets'),
        ('assets/BNazanin.ttf', 'assets'),
        ('assets/BTitrBd.ttf', 'assets'),
        ('app/data/schema.sql', 'app/data'),
        ('config/settings.json', 'config'),
    ],
    hiddenimports=[
        'openpyxl.cell._writer',
        'PySide6.QtCharts',
        'arabic_reshaper',
        'bidi.algorithm',
        'matplotlib.backends.backend_agg',
        'pptx',
        'PIL',
        'numpy._core._exceptions',
        *numpy_hiddenimports,
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'IPython', 'notebook'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SmartEquity',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,   # بدون کنسول سیاه؛ فقط GUI
    icon=None,       # در صورت داشتن آیکون: 'assets/icon.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='SmartEquity',
)

