@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py -3) || (set PY=python)
%PY% -m pip install --quiet pyinstaller pypdf
%PY% -m PyInstaller --noconsole --onefile --name PegaPlagio main.py
echo.
echo Pronto. O programa ficou em: dist\PegaPlagio.exe
pause
