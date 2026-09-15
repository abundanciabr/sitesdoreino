@echo off
cd /d "%~dp0.."
if errorlevel 1 goto fim
schtasks /Create /TN "Triade - vigilia do painel local" /SC MINUTE /MO 20 /TR "\"%CD%\administracao-local\continuar-o-trabalho.cmd\"" /F
if errorlevel 1 (
  echo Nao consegui ligar a vigilia. Abra este arquivo como seu usuario do Windows e tente de novo.
) else (
  echo Vigilia ligada: a cada 20 minutos o Windows chama administracao-local\continuar-o-trabalho.cmd.
)
:fim
pause
