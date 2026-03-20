@echo off
REM build.bat — Build vcode thanh Windows installer (.exe)
REM Dat file nay o thu muc goc vcode\ roi chay
REM Yeu cau: Node.js, npm, Python + venv da co san

echo ============================================
echo   vcode - Windows Build Script
echo ============================================
echo.

REM -- Kiem tra Node.js --
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js chua duoc cai. Tai tai: https://nodejs.org
    pause & exit /b 1
)

REM -- Kiem tra Python --
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python chua duoc cai. Tai tai: https://python.org
    pause & exit /b 1
)

REM -- Tim duong dan venv --
set VENV_PYTHON=
if exist "venv\Scripts\python.exe"  set VENV_PYTHON=venv\Scripts\python.exe
if exist ".venv\Scripts\python.exe" set VENV_PYTHON=.venv\Scripts\python.exe
if exist "env\Scripts\python.exe"   set VENV_PYTHON=env\Scripts\python.exe

if "%VENV_PYTHON%"=="" (
    echo [WARN] Khong tim thay venv, dung system Python
    set VENV_PYTHON=python
)
echo [INFO] Python: %VENV_PYTHON%

REM =============================================
REM 1. Chuan bi thu muc python\ de bundle vao app
REM =============================================
echo [1/4] Chuan bi Python bundle...

REM Xoa cu neu co
if exist python rmdir /s /q python
mkdir python
mkdir python\src
mkdir python\data
mkdir python\output

REM Copy source files
xcopy /E /I /Y src python\src >nul
copy /Y app.py python\app.py >nul
if exist data\rules.json copy /Y data\rules.json python\data\rules.json >nul

REM Cai streamlit va cac package vao python\Lib\site-packages
REM Su dung pip cua venv
echo [INFO] Cai Python packages vao bundle (co the mat 2-3 phut)...
%VENV_PYTHON% -m pip install streamlit pandas openpyxl google-generativeai openai ^
    --target python ^
    --quiet --no-warn-script-location
if %errorlevel% neq 0 (
    echo [ERROR] Cai pip packages that bai
    pause & exit /b 1
)

REM Tao file __main__.py de chay streamlit tu python -m
echo import streamlit.web.cli as stcli > python\run.py
echo import sys >> python\run.py
echo import os >> python\run.py
echo. >> python\run.py
echo if __name__ == "__main__": >> python\run.py
echo     app_path = os.path.join(os.path.dirname(__file__), "app.py") >> python\run.py
echo     sys.argv = ["streamlit", "run", app_path, >> python\run.py
echo         "--server.headless", "true", >> python\run.py
echo         "--server.enableCORS", "false", >> python\run.py
echo         "--server.enableXsrfProtection", "false", >> python\run.py
echo         "--browser.gatherUsageStats", "false", >> python\run.py
echo         "--theme.base", "dark"] >> python\run.py
echo     sys.exit(stcli.main()) >> python\run.py

echo      Done.

REM =============================================
REM 2. Cap nhat main.js de dung python bundle
REM =============================================
echo [2/4] Cap nhat Electron config...

REM Cai Electron dependencies
cd electron
call npm install --quiet
if %errorlevel% neq 0 (
    echo [ERROR] npm install that bai
    cd ..
    pause & exit /b 1
)
echo      Done.

REM =============================================
REM 3. Build .exe
REM =============================================
echo [3/4] Building .exe (co the mat 5-10 phut lan dau)...

REM Tat code signing de tranh loi symlink tren Windows
set CSC_IDENTITY_AUTO_DISCOVERY=false
set WIN_CSC_LINK=
set CSC_LINK=

call npm run build
if %errorlevel% neq 0 (
    echo [ERROR] Build that bai
    cd ..
    pause & exit /b 1
)
cd ..

echo [4/4] Xong!
echo.
echo ============================================
echo   BUILD THANH CONG!
echo   Output: dist\vcode Setup 1.0.0.exe
echo ============================================
echo.
pause