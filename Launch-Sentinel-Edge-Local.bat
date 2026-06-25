@echo off
setlocal
title Sentinel Edge - Local Source
echo.
echo ========================================
echo   Sentinel Edge - Local Source
echo ========================================
echo.
cd /d "%~dp0"

if not exist "%~dp0Launch-Sentinel-Edge-Local.ps1" (
  echo.
  echo Sentinel Edge could not find Launch-Sentinel-Edge-Local.ps1.
  echo Please extract the full Sentinel Edge folder, or use the SentinelEdge-Setup installer.
  echo Send this screenshot to Sentinel Edge support if the problem continues.
  pause
  exit /b 2
)

set "POWERSHELL=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%POWERSHELL%" (
  where powershell.exe >nul 2>nul
  if errorlevel 1 (
    echo.
    echo PowerShell was not found. Sentinel Edge needs Windows PowerShell to start.
    echo Please send this screenshot to Sentinel Edge support.
    pause
    exit /b 9009
  )
  set "POWERSHELL=powershell.exe"
)

"%POWERSHELL%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0Launch-Sentinel-Edge-Local.ps1" %*
set EXITCODE=%ERRORLEVEL%
if not "%EXITCODE%"=="0" (
  echo.
  echo Sentinel Edge local launcher exited with code %EXITCODE%.
  pause
)
exit /b %EXITCODE%
