@echo off
setlocal
title Sentinel Edge - Installed App
cd /d "%~dp0"

if not exist "%~dp0Launch-Sentinel-Edge.ps1" (
  echo.
  echo Sentinel Edge could not find Launch-Sentinel-Edge.ps1.
  echo Please extract the full Sentinel Edge installer folder, or reinstall with SentinelEdge-Setup.
  echo Send this screenshot to Sentinel Edge support if the problem continues.
  pause
  exit /b 2
)

set "POWERSHELL=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%POWERSHELL%" (
  where powershell.exe >nul 2>nul
  if errorlevel 1 (
    echo.
    echo PowerShell was not found. Sentinel Edge needs Windows PowerShell to start and repair missing dependencies.
    echo Please send this screenshot to Sentinel Edge support.
    pause
    exit /b 9009
  )
  set "POWERSHELL=powershell.exe"
)

"%POWERSHELL%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0Launch-Sentinel-Edge.ps1" %*
set EXIT_CODE=%ERRORLEVEL%
if not "%EXIT_CODE%"=="0" (
  echo.
  echo Sentinel Edge launcher exited with code %EXIT_CODE%.
  pause
)
exit /b %EXIT_CODE%
