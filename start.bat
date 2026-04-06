@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo Haoce Auto Reader
echo ========================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] python was not found in PATH.
    echo Please install Python and add it to PATH.
    echo.
    pause
    exit /b 1
)

where adb >nul 2>nul
if errorlevel 1 (
    echo [ERROR] adb was not found in PATH.
    echo Please install ADB and add it to PATH.
    echo.
    pause
    exit /b 1
)

if not exist "config.json" (
    echo [ERROR] config.json was not found in the current folder.
    echo.
    pause
    exit /b 1
)

echo [1/4] Installing requirements...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to install requirements.
    echo Please check your network or pip environment.
    echo.
    pause
    exit /b 1
)

echo.
echo [2/4] Checking device and Haoce status...
python haoce_reader.py --config config.json doctor
if errorlevel 1 (
    echo.
    echo [ERROR] Doctor check failed.
    echo Make sure the phone is connected, ADB is authorized,
    echo and Haoce is installed.
    echo.
    pause
    exit /b 1
)

echo.
echo [3/4] Starting in 3 seconds...
timeout /t 3 /nobreak >nul

echo.
echo [4/4] Running. Press Ctrl+C to stop.
python haoce_reader.py --config config.json run
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if "%EXIT_CODE%"=="0" (
    echo [DONE] Script finished normally.
) else (
    echo [INFO] Script exited with code: %EXIT_CODE%
    echo If a page turn was not confirmed, check screenshots in debug.
)

echo.
pause
exit /b %EXIT_CODE%
