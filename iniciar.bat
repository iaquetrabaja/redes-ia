@echo off
chcp 65001 >nul
title Redes IA
cd /d "%~dp0"
if not exist .venv (call instalar.bat)
call .venv\Scripts\activate.bat
python -m redes_ia %*
pause
