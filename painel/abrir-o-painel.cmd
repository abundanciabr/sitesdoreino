@echo off
REM ===========================================================================
REM ABRIR O PAINEL NESTA MAQUINA — dois cliques, sem terminal.
REM
REM Desde 28/08/2026 o painel.html nao mora mais no repositorio: ele e MONTADO
REM a partir de painel/registros/ (Onda 3 — escritor unico). Este arquivo faz a
REM montagem e abre a pagina, para quem quiser ver o painel offline.
REM
REM O painel de verdade, sempre no ar e sempre atual, e:
REM     https://meshcraft.top/admin/painel/
REM ===========================================================================
setlocal
cd /d "%~dp0.."

where node >nul 2>nul
if errorlevel 1 (
  echo.
  echo   PAROU POR SEGURANCA: o Node nao esta instalado nesta maquina.
  echo.
  echo   Sem ele nao da para montar o painel aqui. Use o painel do site,
  echo   que esta sempre no ar e sempre atualizado:
  echo.
  echo       https://meshcraft.top/admin/painel/
  echo.
  pause
  exit /b 2
)

echo Montando o painel a partir dos registros...
node painel\gerar_manifesto.js
if errorlevel 1 (
  echo.
  echo   PAROU POR SEGURANCA: o livro de ocorrencias tem algo invalido, e o
  echo   painel NAO foi montado. A mensagem acima diz qual registro e o que
  echo   ha de errado nele. Nada foi escrito — o painel antigo continua como
  echo   estava.
  echo.
  pause
  exit /b 1
)

echo Abrindo...
start "" "%~dp0painel.html"
endlocal
