@echo off
setlocal
cd /d "%~dp0"
title Lauchmann Bauplan
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 server.py
  if errorlevel 1 pause
  goto :eof
)
where python >nul 2>nul
if %errorlevel%==0 (
  python server.py
  if errorlevel 1 pause
  goto :eof
)
echo.
echo Python 3 wurde nicht gefunden.
echo Installiere Python 3 von python.org und aktiviere "Add Python to PATH".
echo.
pause
