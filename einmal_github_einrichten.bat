@echo off
setlocal
cd /d "%~dp0"
title Lauchmann Bauplan - GitHub Einrichtung

echo ============================================
echo   Lauchmann Bauplan - einmalige GitHub Einrichtung
echo ============================================
echo.
where git >nul 2>nul
if not %errorlevel%==0 (
  echo Git wurde auf diesem PC nicht gefunden.
  echo Installiere zuerst Git for Windows von https://git-scm.com/download/win
  echo und starte diese Datei danach erneut.
  echo.
  pause
  exit /b 1
)

if not exist ".git" (
  git init -b main
)

git config user.name "Lauchmannn"
git config user.email "Lauchmannn@users.noreply.github.com"

git remote get-url origin >nul 2>nul
if %errorlevel%==0 (
  git remote set-url origin https://github.com/Lauchmannn/LauchmannBauplan.git
) else (
  git remote add origin https://github.com/Lauchmannn/LauchmannBauplan.git
)

echo.
echo Fuege nur Programmdateien hinzu. Litematics und Projekte bleiben lokal.
git add .gitignore VERSION README.md litematic.py server.py updater.py start.bat einmal_github_einrichten.bat app

git diff --cached --quiet
if %errorlevel%==0 (
  echo Keine neuen Aenderungen zum Hochladen gefunden.
) else (
  git commit -m "Lauchmann Bauplan 0.2 - Litematic Viewer"
)

echo.
echo Lade nach GitHub hoch ...
echo Falls GitHub nach einer Anmeldung fragt, im Browser bestaetigen.
git push -u origin main
if not %errorlevel%==0 (
  echo.
  echo Upload fehlgeschlagen. Lies die Meldung oben.
  pause
  exit /b 1
)

echo.
echo Fertig. Ab jetzt kann start.bat Updates automatisch von GitHub laden.
echo.
pause
