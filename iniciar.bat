@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py -3) || (set PY=python)
%PY% --version >nul 2>nul || (
  echo O Python nao foi encontrado.
  echo Instale em https://www.python.org/downloads/ e marque a opcao "Add Python to PATH".
  pause
  exit /b 1
)
%PY% -m pip install --quiet pypdf
%PY% main.py
