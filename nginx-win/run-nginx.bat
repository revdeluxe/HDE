@echo off
REM === Navigate to the script directory ===
cd /d "%~dp0"

setlocal
set NGINX_DIR=nginx-win
set FRONTEND_TARGET=html
set FRONTEND_SOURCE=..\html

cd %NGINX_DIR%

REM === Check if symlink exists and is a directory before deleting ===
if exist %FRONTEND_TARGET%\NUL (
    echo Existing link found. Removing...
    rmdir %FRONTEND_TARGET%
)

REM === Recreate link ===
mklink /D %FRONTEND_TARGET% %FRONTEND_SOURCE%

REM === KILLING nginx if running ===
echo Checking for running nginx processes...
taskkill /F /IM nginx.exe
if errorlevel 1 (
    echo No running nginx process found or failed to kill.
) else (
    echo Nginx process killed successfully.
)

REM === Start nginx ===
echo Starting nginx...
REM === Test config ===
.\nginx.exe -t -c conf\nginx.conf
REM === Check if nginx config test passed ===
if errorlevel 1 (
    echo Nginx configuration test failed. Exiting...
    exit /b 1
)

REM === Start nginx in foreground ===
.\nginx.exe -c conf\nginx.conf -g "daemon off."


endlocal
pause
