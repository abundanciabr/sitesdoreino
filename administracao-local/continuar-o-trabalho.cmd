@echo off
cd /d "%~dp0.."
if errorlevel 1 exit /b 1
python administracao-local\continuidade.py
exit /b %errorlevel%
