@echo off
chcp 65001 >nul
title Redes IA - instalar
cd /d "%~dp0"
echo.
echo   Instalando Redes IA... (solo la primera vez, tarda 1-2 minutos)
echo.
where py >nul 2>nul && (set PY=py -3) || (set PY=python)
%PY% --version >nul 2>nul || (
  echo   No encuentro Python. Instalalo desde https://www.python.org/downloads/
  echo   y marca la casilla "Add python.exe to PATH". Luego vuelve a abrir este archivo.
  pause
  exit /b 1
)
if not exist .venv (%PY% -m venv .venv)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt || (echo. & echo   Algo ha fallado instalando. Mira el mensaje de arriba. & pause & exit /b 1)
echo.
echo   Listo. Ahora abre "iniciar.bat".
echo.
pause
