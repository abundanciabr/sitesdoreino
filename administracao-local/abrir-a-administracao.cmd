@echo off
cd /d "%~dp0.."
if errorlevel 1 exit /b 1
python ci\ligar_administracao.py
exit /b %errorlevel%
