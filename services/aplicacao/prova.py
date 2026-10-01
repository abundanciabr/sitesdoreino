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
import time
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
        "CATALOGO_API_URL": "http://catalogo:8000/api/catalogo",
        "TOKEN_CATALOGO": "prova-token-catalogo",
        "TOKENS_ACEITOS_FUNIL": "prova-token-catalogo",
        "IDENTIDADE_API_URL": "http://identidade:8000/interno",
        "IDENTIDADE_API_TOKEN": "prova-token-identidade",
        "TOKENS_ACEITOS_PAGES": "prova-token-identidade",
        "TOKENS_COMPLETOS_PAGES": "prova-token-identidade",
        "ALUNOS_API_URL": "http://alunos:8000/api/alunos",
        "ALUNOS_API_TOKEN": "prova-token-alunos",
        "QUIZ_API_URL": "http://quiz:8000/interno",
        "QUIZ_API_TOKEN": "prova-editor-quiz",
        "TOKENS_ACEITOS_ADMIN": "prova-editor-quiz",
        "ADMIN_EMAILS": "equipe@prova.local",
        "HUEY_REDIS_URL": os.environ.get("REDIS_STREAMS_URL", "redis://redis:6379/0"),
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
        if servico == "catalogo":
            # A real legacy ORM row proves more than a comparison of empty
            # schemas after adopting the namespaced migration history.
            subprocess.run(
                [sys.executable, "manage.py", "shell", "-c",
                 "from apps.sites.models import Site; "
                 "Site.objects.create(host='meshcraft.top', name='Prova legada')"],
                cwd=origem, env={**os.environ, **valores}, check=True,
                stdout=subprocess.DEVNULL,
            )
        with psycopg.connect(urls[servico]) as conexao:
            contagens[servico] = _contagens(conexao)
    return contagens


def migrar_unificado(urls: dict[str, str], antes: dict[str, dict[str, int]]) -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    from django.apps import apps
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
            for modelo in apps.get_models():
                meta = modelo._meta
                if (meta.app_label.startswith(servico + "_") and meta.managed
                        and not meta.proxy and meta.db_table not in antes[servico]):
                    raise AssertionError(
                        f"modelo {meta.label} aponta a tabela não legada {meta.db_table}"
                    )
            if not set(antes[servico]) <= set(depois):
                raise AssertionError(f"tabelas antigas desapareceram em {servico}")
            for tabela, quantidade in antes[servico].items():
                if tabela in ("django_migrations", "django_content_type", "auth_permission"):
                    continue
                if depois[tabela] < quantidade:
                    raise AssertionError(f"linhas antigas desapareceram em {servico}.{tabela}")
            with conexao.cursor() as cursor:
                if servico == "catalogo":
                    cursor.execute(
                        "SELECT name FROM sites_site WHERE host = %s",
                        ["meshcraft.top"],
                    )
                    if cursor.fetchone() != ("Prova legada",):
                        raise AssertionError("registro legado de site não sobreviveu")
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
    from internal import instalar
    instalar()
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
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=config.asgi.application),
        base_url="https://meshcraft.top", follow_redirects=False,
    ) as cliente:
        for antigo, novo in (
            ("/pages/trabalhos?origem=antiga", "/portfolio/trabalhos?origem=antiga"),
            ("/estudio/pecas", "/portfolio/trabalhos"),
        ):
            resposta = await cliente.get(antigo)
            if (resposta.status_code != 308 or resposta.headers.get("location") != novo
                    or resposta.headers.get("content-length") != "0"):
                raise AssertionError(f"redirecionamento legado inválido: {antigo}")
        for caminho in ("/", "/portfolio/", "/forum/", "/quiz/", "/admin/"):
            resposta = await cliente.get(caminho)
            if resposta.status_code >= 500:
                raise AssertionError(f"rota pública {caminho}: HTTP {resposta.status_code}")


def provar_entrada_real() -> None:
    """Boot the production entrypoint, including its workers, on test services."""
    from config.runtime import serving

    with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as log:
        processo = subprocess.Popen(
            [sys.executable, "entrypoint.py"], cwd=Path(__file__).resolve().parent,
            env=os.environ.copy(), stdout=log, stderr=subprocess.STDOUT,
        )
        try:
            prazo = time.monotonic() + 90
            while time.monotonic() < prazo:
                if processo.poll() is not None:
                    break
                try:
                    resposta = httpx.get("http://127.0.0.1:8000/healthz", timeout=1)
                    if resposta.status_code == 200:
                        break
                except httpx.RequestError:
                    pass
                time.sleep(0.5)
            else:
                raise AssertionError("entrypoint não iniciou HTTP em 90 segundos")
            if processo.poll() is not None:
                raise AssertionError("entrypoint encerrou antes do HTTP")

            # A periodic task with an empty outbox is side-effect-free; its
            # result proves the real Huey worker restored forum context/DB.
            with serving("forum"):
                from modules.forum.apps.forum.tasks import relay_outbox_periodico
                from modules.forum.config.huey import huey as fila
                from modules.forum.apps.forum.models import OutboxEvent
                import redis
                evento = OutboxEvent.objects.create(
                    event="forum.prova-unificada", payload={"prova": True},
                )
                relay_outbox_periodico()
                print(f"Huey fórum: {fila.storage.queue_key}; pendentes={fila.pending_count()}",
                      flush=True)
                limite = time.monotonic() + 20
                while time.monotonic() < limite:
                    evento.refresh_from_db()
                    if evento.published_at:
                        break
                    time.sleep(0.3)
                else:
                    raise AssertionError("task Huey não publicou outbox no banco do fórum")
                canal = redis.Redis.from_url(os.environ["REDIS_STREAMS_URL"])
                cartas = canal.xrevrange("eventos.forum.prova-unificada", count=1)
                if not cartas or str(evento.event_id).encode() not in cartas[0][1][b"json"]:
                    raise AssertionError("task Huey não publicou no Redis isolado")
            time.sleep(2)
            log.seek(0)
            texto = log.read()
            if "Worker " in texto and " falhou" in texto:
                raise AssertionError(f"worker da aplicação falhou: {texto[-4000:]}")
        except Exception as erro:
            log.flush()
            log.seek(0)
            linhas = [linha for linha in log.read().splitlines()
                      if any(palavra in linha for palavra in
                             ("Worker", "huey", "Huey", "ERROR", "Traceback", "Connection"))]
            raise AssertionError(
                f"entrypoint/workers: {erro}; log: {' | '.join(linhas[-80:])}"
            ) from erro
        finally:
            processo.terminate()
            try:
                processo.wait(timeout=10)
            except subprocess.TimeoutExpired:
                processo.kill()
                processo.wait()


def main() -> None:
    urls = criar_bancos()
    with tempfile.TemporaryDirectory(prefix="prova-aplicacao-") as temporario:
        pasta_env = Path(temporario)
        antes = migrar_legado(urls, pasta_env)
        os.environ["APLICACAO_ENV_DIR"] = str(pasta_env)
        migrar_unificado(urls, antes)
        comando = subprocess.run(
            [sys.executable, "-m", "config.comando", "catalogo", "shell", "-c",
             "from apps.sites.models import Site; "
             "print(Site.objects.get(host='meshcraft.top').name)"],
            cwd=Path(__file__).resolve().parent, env=os.environ.copy(),
            check=True, capture_output=True, text=True,
        )
        if comando.stdout.strip() != "Prova legada":
            raise AssertionError("CLI unificada não leu registro legado")
        asyncio.run(provar_http())
        from prova_fluxos import provar as provar_fluxos
        provar_fluxos()
        provar_entrada_real()
    print(f"Aplicação única: {len(urls)} bancos legados preservados; "
          f"{len(MODULOS)} módulos HTTP saudáveis; estáticos servidos.")


if __name__ == "__main__":
    main()
