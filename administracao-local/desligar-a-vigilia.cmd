@echo off
schtasks /Delete /TN "Triade - vigilia do painel local" /F
if errorlevel 1 (
  echo A vigilia ja estava desligada ou o Agendador recusou o pedido.
) else (
  echo Vigilia desligada: o Windows nao chamara mais a continuidade do painel local.
)
pause
