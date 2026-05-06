"""_make_bat.py - setup.bat / build_exe.bat 을 CRLF 로 생성"""
from pathlib import Path

HERE = Path(__file__).parent

SETUP = r"""@echo off
setlocal enabledelayedexpansion
title Video Compressor Pro
cd /d "%~dp0"

echo.
echo  ============================================
echo   Video Compressor Pro  v1.0.0
echo   H.265 Video Compression Tool
echo  ============================================
echo.

set "PYTHON="

:: 1. Search common install paths
for %%V in (313 312 311 310 39 38) do (
    if "!PYTHON!"=="" (
        if exist "%USERPROFILE%\AppData\Local\Programs\Python\Python%%V\python.exe" (
            set "PYTHON=%USERPROFILE%\AppData\Local\Programs\Python\Python%%V\python.exe"
        )
    )
)

if "!PYTHON!"=="" (
    for %%V in (313 312 311 310 39 38) do (
        if exist "C:\Python%%V\python.exe" (
            if "!PYTHON!"=="" set "PYTHON=C:\Python%%V\python.exe"
        )
    )
)

:: 2. Check for 'py' launcher
if "!PYTHON!"=="" (
    py -3 --version > nul 2>&1
    if !errorlevel!==0 (
        set "PYTHON=py -3"
    )
)

if "!PYTHON!"=="" (
    echo  [ERROR] Python not found.
    echo  Install from: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo  [OK] Python: !PYTHON!
echo.

:: Execute helper - handle 'py -3' vs 'C:\path\python.exe'
set "RUN_CMD="
if "!PYTHON:~0,2!"=="py" (
    set RUN_CMD=!PYTHON!
) else (
    set RUN_CMD="!PYTHON!"
)

echo  [1/2] Checking ffmpeg...
!RUN_CMD! "%~dp0installer.py"
echo.

echo  [2/2] Starting Video Compressor Pro...
start "" !RUN_CMD! "%~dp0main.py"
endlocal
"""

BUILD = r"""@echo off
setlocal enabledelayedexpansion
title Video Compressor Pro - Build EXE
cd /d "%~dp0"

echo.
echo  ============================================
echo   Video Compressor Pro - Build EXE
echo  ============================================
echo.

set "PYTHON="
for %%V in (313 312 311 310 39 38) do (
    if "!PYTHON!"=="" (
        if exist "%USERPROFILE%\AppData\Local\Programs\Python\Python%%V\python.exe" (
            set "PYTHON=%USERPROFILE%\AppData\Local\Programs\Python\Python%%V\python.exe"
        )
    )
)
if "!PYTHON!"=="" (
    py -3 --version > nul 2>&1
    if !errorlevel!==0 set "PYTHON=py -3"
)

if "!PYTHON!"=="" (
    echo  [ERROR] Python not found.
    pause
    exit /b 1
)

set "RUN_CMD="
if "!PYTHON:~0,2!"=="py" (
    set RUN_CMD=!PYTHON!
) else (
    set RUN_CMD="!PYTHON!"
)

echo  [OK] Python: !PYTHON!
echo.

echo  [1/3] Installing PyInstaller...
!RUN_CMD! -m pip install pyinstaller --quiet --upgrade
if !errorlevel! neq 0 (
    echo  [ERROR] PyInstaller install failed.
    pause & exit /b 1
)
echo  [OK] PyInstaller ready.
echo.

echo  [2/3] Cleaning old build...
if exist "dist\VideoCompressorPro.exe"  del /f /q "dist\VideoCompressorPro.exe"
if exist "build"                        rmdir /s /q "build"
if exist "VideoCompressorPro.spec"      del /f /q "VideoCompressorPro.spec"
echo  [OK] Done.
echo.

echo  [3/3] Building EXE (few minutes)...
echo.

!RUN_CMD! -m PyInstaller ^
    --onefile ^
    --windowed ^
    --icon "assets\icons\app_icon.ico" ^
    --name "VideoCompressorPro" ^
    --add-data "installer.py;." ^
    --add-data "video_compressor.py;." ^
    --add-data "main.py;." ^
    --add-data "assets;assets" ^
    --add-data "README.md;." ^
    --hidden-import tkinter ^
    --hidden-import tkinter.ttk ^
    --hidden-import tkinter.filedialog ^
    --hidden-import tkinter.messagebox ^
    --hidden-import tkinter.scrolledtext ^
    main.py

if !errorlevel! neq 0 (
    echo.
    echo  [ERROR] Build failed.
    pause & exit /b 1
)

echo.
echo  ============================================
echo   [SUCCESS] Build complete!
echo   Output: dist\VideoCompressorPro.exe
echo  ============================================
echo.

if exist "dist" explorer dist
pause
endlocal
"""

def write_crlf(path: Path, content: str):
    with open(path, "w", newline="\r\n", encoding="utf-8") as f:
        f.write(content.lstrip("\n"))
    print(f"  OK: {path.name}  ({path.stat().st_size} bytes, CRLF, UTF-8)")

write_crlf(HERE / "setup.bat",     SETUP)
write_crlf(HERE / "build_exe.bat", BUILD)
print("\nBatch files updated to handle spaces correctly.")
