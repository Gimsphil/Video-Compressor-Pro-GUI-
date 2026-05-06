@echo off
setlocal enabledelayedexpansion
title Video Compressor Pro
cd /d "%~dp0"

echo.
echo  ============================================
echo   Video Compressor Pro  v1.0.0
echo  ============================================
echo.

:: Python 3.13 직접 경로 (사용자님 PC에 확인된 버전)
set "PYTHON313=%USERPROFILE%\AppData\Local\Programs\Python\Python313\python.exe"

if exist "!PYTHON313!" (
    echo  [OK] Python 3.13 발견
    echo  [실행 중] main.py 시작...
    echo.
    "!PYTHON313!" "%~dp0main.py"
    goto :done
)

:: Python 3.13이 없으면 다른 버전 탐색 (314 제외)
set "PYTHON="
for %%V in (313 312 311 310 39 38) do (
    if "!PYTHON!"=="" (
        if exist "%USERPROFILE%\AppData\Local\Programs\Python\Python%%V\python.exe" (
            set "PYTHON=%USERPROFILE%\AppData\Local\Programs\Python\Python%%V\python.exe"
        )
    )
)

if "!PYTHON!"=="" (
    echo  [ERROR] Python 3.13 이하 버전이 필요합니다.
    echo  Python 3.14는 지원되지 않습니다.
    echo  https://www.python.org/downloads/release/python-3130/
    echo.
    pause
    exit /b 1
)

echo  [OK] Python: !PYTHON!
echo.
"!PYTHON!" "%~dp0main.py"

:done
if errorlevel 1 (
    echo.
    echo  [ERROR] 프로그램 실행 중 오류가 발생했습니다.
    pause
)
endlocal
