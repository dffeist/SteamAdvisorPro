@echo off
:: ============================================================
:: Build SteamAdvisorPro using PyInstaller (onedir / --dir mode)
:: UPX disabled — UPX-packed binaries are commonly flagged by AV
:: No terminal window (windowed mode)
:: ============================================================

cd /d "%~dp0"
setlocal

set "SCRIPT=SteamAdvisorPro.py"
set "APP_NAME=SteamAdvisorPro"
set "VERSION=1.0.0B2"
set "OUT_DIR=dist"
set "WORK_DIR=build"

echo [BUILD] Cleaning previous output...
if exist "%OUT_DIR%\%APP_NAME%-%VERSION%" rmdir /s /q "%OUT_DIR%\%APP_NAME%-%VERSION%"
if exist "%WORK_DIR%"                      rmdir /s /q "%WORK_DIR%"

echo [BUILD] Running PyInstaller...

pyinstaller ^
    --noconfirm ^
    --onedir ^
    --windowed ^
    --name "%APP_NAME%-%VERSION%" ^
    --distpath "%OUT_DIR%" ^
    --workpath "%WORK_DIR%" ^
    --exclude-module unittest ^
    --exclude-module xml ^
    --exclude-module pydoc ^
    --exclude-module doctest ^
    --noupx ^
    --clean ^
    "%SCRIPT%"

if %ERRORLEVEL% neq 0 (
    echo [ERROR] PyInstaller failed with exit code %ERRORLEVEL%.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo [BUILD] Done. Output: %OUT_DIR%\%APP_NAME%-%VERSION%\%APP_NAME%-%VERSION%.exe
endlocal
pause
