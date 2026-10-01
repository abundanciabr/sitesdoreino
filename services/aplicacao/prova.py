"""Ensaio isolado da troca: 17 bancos legados, registry único e HTTP.

Executado pelo publicador antes da ativação, com PostgreSQL e Redis descartáveis.
Nunca lê env nem banco de produção.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import httpx
import psycopg
from psycopg import sql

from preparar import MODULOS


RAIZ_SERVICOS = Path(os.environ.get("PROVA_ORIGEM_SERVICES", "/fonte/services"))
POSTGRES_URL = os.environ.get("PROVA_POSTGRES_URL", "")
if not POSTGRES_URL:
    raise SystemExit("PROVA_POSTGRES_URL ausente no Postgres isolado")
if not RAIZ_SERVICOS.is_dir():
    raise SystemExit(f"fontes legadas ausentes: {RAIZ_SERVICOS}")

PREFIXOS = {
    "admin": "/admin", "alunos": "/alunos", "checkout": "/checkout",
    "cursos": "/cursos", "encomendas": "/encomendas", "forum": "/forum",
    "gamificacao": "/conquistas", "pages": "/pages", "quiz": "/quiz",
    "sugestoes": "/forms/sugestoes",
}


def banco_url(nome: str) -> str:
    partes = urlsplit(POSTGRES_URL)
    return urlunsplit((partes.scheme, partes.netloc, "/" + nome,
                       partes.query, partes.fragment))


def criar_bancos() -> dict[str, str]:
    sufixo = uuid4().hex[:8]
    urls = {}
    with psycopg.connect(POSTGRES_URL, autocommit=True) as conexao:
        with conexao.cursor() as cursor:
            for servico in MODULOS:
                if servico == "funil":
                    continue
                nome = f"prova_{servico}_{sufixo}"
                cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(nome)))
                urls[servico] = banco_url(nome)
    return urls


def ambiente(servico: str, urls: dict[str, str]) -> dict[str, str]:
    valores = {
        "DJANGO_SECRET_KEY": "prova-local-sem-dado-real-" + servico,
        "DEBUG": "1",
        "SCRIPT_NAME": PREFIXOS.get(servico, ""),
        "REDIS_STREAMS_URL": os.environ.get("REDIS_STREAMS_URL", "redis://redis:6379/0"),
        "MP_ACCESS_TOKEN": "TEST-prova-isolada",
        "MP_WEBHOOK_SECRET": "prova-isolada",
    }
    if servico in urls:
        valores["DATABASE_URL"] = urls[servico]
    return valores


def _contagens(conexao) -> dict[str, int]:
    resultado = {}
    with conexao.cursor() as cursor:
        cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
        for (tabela,) in cursor.fetchall():
            cursor.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(tabela)))
            resultado[tabela] = cursor.fetchone()[0]
    return resultado


def migrar_legado(urls: dict[str, str], pasta_env: Path) -> dict[str, dict[str, int]]:
    contagens = {}
    for servico in MODULOS:
        valores = ambiente(servico, urls)
        (pasta_env / f"{servico}.env").write_text(
            "".join(f"{chave}={valor}\n" for chave, valor in valores.items()),
            encoding="utf-8",
        )
        if servico == "funil":
            continue
        origem = RAIZ_SERVICOS / servico
        subprocess.run(
            [sys.executable, "manage.py", "migrate", "--noinput"],
            cwd=origem, env={**os.environ, **valores}, check=True,
            stdout=subprocess.DEVNULL,
        )
        with psycopg.connect(urls[servico]) as conexao:
            contagens[servico] = _contagens(conexao)
    return contagens


def migrar_unificado(urls: dict[str, str], antes: dict[str, dict[str, int]]) -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    from django.core.management import call_command
    from config.migracoes import preparar_migracoes
    from config.runtime import install_contextual_settings, load_original_settings, serving

    django.setup()
    load_original_settings()
    install_contextual_settings()
    preparar_migracoes()
    for servico in MODULOS:
        if servico == "funil":
            continue
        with serving(servico):
            call_command("migrate", database=servico, interactive=False, verbosity=0)
        with psycopg.connect(urls[servico]) as conexao:
            depois = _contagens(conexao)
            if not set(antes[servico]) <= set(depois):
                raise AssertionError(f"tabelas antigas desapareceram em {servico}")
            for tabela, quantidade in antes[servico].items():
                if tabela in ("django_migrations", "django_content_type", "auth_permission"):
                    continue
                if depois[tabela] < quantidade:
                    raise AssertionError(f"linhas antigas desapareceram em {servico}.{tabela}")
            with conexao.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) FROM django_migrations WHERE app LIKE %s",
                    [servico + "_%"],
                )
                if cursor.fetchone()[0] == 0:
                    raise AssertionError(f"histórico não reconhecido em {servico}")

        # O código anterior continua apto a iniciar após adoção aditiva;
        # a reversão de imagem depende dessa compatibilidade.
        valores = ambiente(servico, urls)
        subprocess.run(
            [sys.executable, "manage.py", "check"],
            cwd=RAIZ_SERVICOS / servico, env={**os.environ, **valores},
            check=True, stdout=subprocess.DEVNULL,
        )


async def provar_http() -> None:
    import config.asgi
    for servico in MODULOS:
        cliente = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=config.asgi.app_do_servico(servico)),
            base_url="https://meshcraft.top",
        )
        async with cliente:
            resposta = await cliente.get("/healthz")
            if resposta.status_code != 200:
                raise AssertionError(f"{servico}/healthz: HTTP {resposta.status_code}")
    # O JS das páginas de entrada precisa sair da própria fonte após o bundle.
    for caminho in ("/static/funil/api.js", "/checkout/static/checkout/api.js"):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=config.asgi.application),
            base_url="https://meshcraft.top",
        ) as cliente:
            resposta = await cliente.get(caminho)
            if resposta.status_code != 200 or not resposta.content:
                raise AssertionError(f"estático {caminho}: HTTP {resposta.status_code}")


def main() -> None:
    urls = criar_bancos()
    with tempfile.TemporaryDirectory(prefix="prova-aplicacao-") as temporario:
        pasta_env = Path(temporario)
        antes = migrar_legado(urls, pasta_env)
        os.environ["APLICACAO_ENV_DIR"] = str(pasta_env)
        migrar_unificado(urls, antes)
        asyncio.run(provar_http())
    print(f"Aplicação única: {len(urls)} bancos legados preservados; "
          f"{len(MODULOS)} módulos HTTP saudáveis; estáticos servidos.")


if __name__ == "__main__":
    main()
