@echo off
setlocal
title Sentinel Bot Suite
echo.
echo ========================================
echo   Sentinel Bot Suite
echo ========================================
echo.
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Launch-Sentinel-Bot-Suite.ps1" %*
set EXIT_CODE=%ERRORLEVEL%
if not "%EXIT_CODE%"=="0" (
  echo.
  echo Sentinel Bot Suite launcher exited with code %EXIT_CODE%.
  pause
)
exit /b %EXIT_CODE%
