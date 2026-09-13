@echo off
setlocal

cd /d "%~dp0.."
if errorlevel 1 goto falha_raiz

for /f "delims=" %%K in ('python -c "import secrets; print(secrets.token_urlsafe(32))"') do set "DJANGO_SECRET_KEY=%%K"
set "DEBUG=1"
set "DATABASE_URL=sqlite:///teste-local.sqlite3"
set "ADMIN_PLANOS_DIR=%~dp0..\docs\decisoes"
for /f "delims=" %%K in ('python -c "import secrets; print(secrets.token_urlsafe(32))"') do set "ADMIN_LINK_TOKEN=%%K"
set "URL_DE_ENTRADA=/acesso-local/%ADMIN_LINK_TOKEN%/"

if not exist "services\admin\manage.py" goto falha_manage

cd /d "services\admin"
if errorlevel 1 goto falha_admin

python manage.py migrate
if errorlevel 1 goto falha_migrate

python manage.py shell -c "from django.db import connection; faltando={'core_documento','core_livro'}-set(connection.introspection.table_names()); raise SystemExit('faltam tabelas: '+', '.join(sorted(faltando)) if faltando else 0)"
if errorlevel 1 goto falha_tabelas

echo Administracao local pronta. Abra:
echo http://127.0.0.1:8000/admin/acesso-local/%ADMIN_LINK_TOKEN%/?next=/admin/plano-mestre/
python manage.py runserver 127.0.0.1:8000
goto fim

:falha_raiz
echo PAROU POR SEGURANCA: nao consegui entrar na raiz do repositorio. Abra este arquivo dentro de administracao-local.
goto fim

:falha_manage
echo PAROU POR SEGURANCA: nao encontrei services\admin\manage.py. Confira se este arquivo esta na raiz correta do repositorio.
goto fim

:falha_admin
echo PAROU POR SEGURANCA: nao consegui entrar em services\admin. Confira se a pasta existe neste checkout.
goto fim

:falha_migrate
echo PAROU POR SEGURANCA: o migrate falhou. Leia o erro acima, instale as dependencias de services\admin\requirements.txt e rode de novo.
goto fim

:falha_tabelas
echo PAROU POR SEGURANCA: o banco local nao ficou com as tabelas esperadas. Leia o erro acima e rode o lancador de novo depois de corrigir a migracao.
goto fim

:fim
echo.
pause
