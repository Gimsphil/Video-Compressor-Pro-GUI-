@echo off
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
