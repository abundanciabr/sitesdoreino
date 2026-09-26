@echo off
setlocal
set "PYTHONUTF8=1"
set "runtimeCodex=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%runtimeCodex%" goto executar
for %%P in (python.exe python3.exe) do (
    for /f "delims=" %%Q in ('where %%P 2^>nul') do (
        "%%Q" -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)" >nul 2>nul
        if not errorlevel 1 (
            set "runtimeCodex=%%Q"
            goto executar
        )
    )
)
>&2 echo PAROU POR SEGURANCA: Python 3.11+ indisponivel. O agente nao conseguiu executar a tarefa porque o runtime nao foi encontrado.
exit /b 2
:executar
"%runtimeCodex%" %*
exit /b %errorlevel%
