@echo off
setlocal enabledelayedexpansion
REM build.bat -- Build vcode thanh Windows app
REM Dat o thu muc goc vcode\ va chay: .\build.bat

echo ============================================
echo   vcode - Windows Build Script
echo ============================================
echo.

where node >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js chua duoc cai: https://nodejs.org
    pause & exit /b 1
)

REM -- Tim venv --
set VENV_DIR=
if exist "venv\Scripts\python.exe"  set VENV_DIR=venv
if exist ".venv\Scripts\python.exe" set VENV_DIR=.venv
if "!VENV_DIR!"=="" (
    echo [ERROR] Khong tim thay venv. Hay tao venv truoc:
    echo         python -m venv venv
    echo         venv\Scripts\activate
    echo         pip install -r requirements.txt
    pause & exit /b 1
)
echo [INFO] Venv tim thay: !VENV_DIR!

REM =============================================
REM 1. Chuan bi python\ (source code de bundle)
REM =============================================
echo [1/4] Chuan bi source bundle...
if exist python rmdir /s /q python
mkdir python
mkdir python\src
mkdir python\data
mkdir python\output

xcopy /E /I /Y src python\src >nul
copy /Y app.py python\app.py >nul
if exist data\rules.json copy /Y data\rules.json python\data\rules.json >nul

REM Tao run.py -- script de chay streamlit tu bundled packages
(
echo # -*- coding: utf-8 -*-
echo import sys, os
echo # Them thu muc hien tai vao path de load src/
echo sys.path.insert^(0, os.path.dirname^(__file__^)^)
echo import streamlit.web.cli as stcli
echo if __name__ == "__main__":
echo     app_path = os.path.join^(os.path.dirname^(__file__^), "app.py"^)
echo     sys.argv = [
echo         "streamlit", "run", app_path,
echo         "--server.port", "8501",
echo         "--server.headless", "true",
echo         "--server.enableCORS", "false",
echo         "--server.enableXsrfProtection", "false",
echo         "--browser.gatherUsageStats", "false",
echo         "--theme.base", "dark",
echo     ]
echo     sys.exit^(stcli.main^(^)^)
) > python\run.py

echo      Source bundle: OK

REM =============================================
REM 2. Cai Electron dependencies
REM =============================================
echo [2/4] Cai Electron dependencies...
cd electron
call npm install --quiet
if %errorlevel% neq 0 (
    echo [ERROR] npm install that bai
    cd .. & pause & exit /b 1
)
echo      Electron: OK

REM =============================================
REM 3. Build .exe
REM =============================================
echo [3/4] Building .exe (co the mat 5-10 phut lan dau)...
set CSC_IDENTITY_AUTO_DISCOVERY=false
set WIN_CSC_LINK=
set CSC_LINK=
call npm run build
if %errorlevel% neq 0 (
    echo [ERROR] electron-builder that bai
    cd .. & pause & exit /b 1
)
cd ..

REM Kiem tra output
if not exist "dist\win-unpacked\vcode.exe" (
    echo [ERROR] Khong tim thay dist\win-unpacked\vcode.exe
    pause & exit /b 1
)
echo      Build: OK

REM =============================================
REM 4. Copy toan bo venv vao canh vcode.exe
REM    => Khong can cai Python tren may nguoi dung
REM =============================================
echo [4/4] Copy venv vao dist\win-unpacked\venv ...
echo      (co the mat 1-2 phut, venv thuong ~200-500MB)

xcopy /E /I /Y "!VENV_DIR!" "dist\win-unpacked\venv" >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Copy venv that bai
    pause & exit /b 1
)

REM Kiem tra python.exe da duoc copy
if not exist "dist\win-unpacked\venv\Scripts\python.exe" (
    echo [ERROR] Khong tim thay python.exe trong dist\win-unpacked\venv\Scripts\
    echo         Kiem tra lai ten thu muc venv: !VENV_DIR!
    pause & exit /b 1
)
echo      Venv: OK - python.exe da co tai dist\win-unpacked\venv\Scripts\

echo.
echo ============================================
echo   BUILD THANH CONG!
echo.
echo   Chay thu    : dist\win-unpacked\vcode.exe
echo   Phan phoi   : zip toan bo dist\win-unpacked\
echo                 giai nen va chay vcode.exe
echo ============================================
pause