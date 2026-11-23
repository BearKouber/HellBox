@echo off
setlocal
set "B=%~dp0bin\HellBox"
if not exist "%B%\HellBox.exe" (
  echo HellBox build not found:
  echo %B%
  pause
  exit /b 1
)
net session >nul 2>&1
if errorlevel 1 (
  echo Please right-click this file and choose Run as administrator.
  pause
  exit /b 1
)
echo Restoring Medium integrity on the HellBox build...
icacls "%B%" /setintegritylevel (OI)(CI)M /T >nul
if errorlevel 1 goto fail
echo Done. Starting HellBox...
start "" "%B%\HellBox.exe"
exit /b 0
:fail
echo Failed to change the integrity label.
pause
exit /b 1
