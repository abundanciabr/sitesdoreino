"""O mundo do ciclo comercial: as células de verdade juntas, só os provedores simulados.

Liga com `E2E_POSTGRES_URL` (qualquer banco do servidor, ex.:
`postgres://postgres:postgres@127.0.0.1:59010/postgres`) e `E2E_REDIS_URL`
(ex.: `redis://127.0.0.1:60010`). Sem as duas, estes testes são pulados.

Roda sozinho (`pytest tests/e2e`): as outras provas da aplicação sobem a
configuração com banco em memória no mesmo processo, e uma configuração só
vale por processo.

Materializa `modules/` sozinho (o mesmo que `preparar.py --origem .. --destino modules`),
sempre a partir dos fontes atuais.

Cria (apaga e recria) os bancos `e2e_<celula>` do servidor de teste e usa os
bancos 7, 8, 9 e 15 do Redis de teste (o 15 é do roteiro). Nada disto toca o
site no ar: só servidor local (127.0.0.1 ou localhost) é aceito, e os bancos
e os fluxos de teste são apagados no fim.

Os módulos (`modules/`) são gerados aqui mesmo a partir dos fontes, com o
mesmo `preparar.py` da imagem; não precisa rodá-lo antes.
"""

from __future__ import annotations

import os
import sys
import tempfile
import uuid
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

HOST = "ciclo.e2e.test"
HOST_OUTRO = "outro.e2e.test"  # um segundo site, para provar que um não enxerga o outro
SERVIDORES_LOCAIS = ("127.0.0.1", "localhost", "::1")
USADAS = ("catalogo", "quiz", "leads", "checkout", "pagamentos", "mensageria", "identidade")
SCRIPTS = {"checkout": "/checkout", "quiz": "/quiz"}

T = {
    "leads_admin": "tk-admin-para-leads",
    "leads_mensageria": "tk-mensageria-para-leads",
    "mensageria_admin": "tk-admin-para-mensageria",
    "checkout_admin": "tk-admin-para-checkout",
    "checkout_catalogo": "tk-checkout-para-catalogo",
    "checkout_pagamentos": "tk-checkout-para-pagamentos",
    "quiz_catalogo": "tk-quiz-para-catalogo",
    "pagina": "tk-publico-da-pagina",
    "gateway": "tk-gateway-whatsapp",
    "webhook": "tk-webhook-whatsapp",
    "mp_segredo": "segredo-do-mp-de-ensaio",
}


def _marca(texto: str, desde: float) -> float:
    import time

    agora = time.monotonic()
    print(f"[e2e] {texto}: {agora - desde:.1f}s", file=sys.stderr)
    return agora


def _banco(url: str, nome: str) -> str:
    partes = urlsplit(url)
    return urlunsplit(partes._replace(path=f"/{nome}"))


def _redis(url: str, numero: int) -> str:
    return urlunsplit(urlsplit(url)._replace(path=f"/{numero}"))


def _criar_bancos(url_postgres: str) -> None:
    import psycopg

    with psycopg.connect(_banco(url_postgres, "postgres"), autocommit=True) as conexao:
        for servico in USADAS:
            nome = f"e2e_{servico}"
            conexao.execute(f'DROP DATABASE IF EXISTS "{nome}" WITH (FORCE)')
            conexao.execute(f'CREATE DATABASE "{nome}"')


def _preparar_modulos() -> None:
    """Materializa `modules/` a partir dos fontes (o `preparar.py` da imagem) quando falta ou ficou velho.

    Sem isto o teste falharia por falta da pasta ou, pior, rodaria um `modules/` de outra
    versão do código. Com a pasta em dia ela não é refeita, para não apagá-la debaixo de
    outra rodada de testes que já a esteja usando.
    """
    import importlib

    from preparar import MODULOS, preparar

    destino, marca = RAIZ / "modules", RAIZ / "modules" / ".preparado"
    fontes = RAIZ.parent
    ultima_edicao = max((p.stat().st_mtime for m in MODULOS for p in (fontes / m).rglob("*.py")
                         if "tests" not in p.parts and ".venv" not in p.parts), default=0)
    if marca.is_file() and marca.stat().st_mtime >= ultima_edicao:
        return
    preparar(fontes, destino)
    marca.write_text("pronto\n", encoding="utf-8")
    importlib.invalidate_caches()


def _limpar(url_postgres: str, url_redis: str) -> None:
    """No fim, o servidor de teste fica como estava: sem os bancos e2e_* e sem os fluxos de teste."""
    import psycopg
    import redis as redis_lib

    try:
        for numero in (7, 8, 9, 15):
            redis_lib.from_url(_redis(url_redis, numero)).flushdb()
        with psycopg.connect(_banco(url_postgres, "postgres"), autocommit=True) as conexao:
            for servico in USADAS:
                conexao.execute(f'DROP DATABASE IF EXISTS "e2e_{servico}" WITH (FORCE)')
    except Exception as erro:  # noqa: BLE001 - a limpeza nunca derruba o resultado dos testes
        print(f"[e2e] limpeza do servidor de teste incompleta: {type(erro).__name__}", file=sys.stderr)


def _escrever_ambientes(pasta: Path, postgres: str, redis_url: str, gateway_url: str) -> None:
    from config.registry import SERVICES

    streams, huey, erros = _redis(redis_url, 9), _redis(redis_url, 8), _redis(redis_url, 7)
    extras = {
        "catalogo": [f"TOKENS_ACEITOS_CHECKOUT={T['checkout_catalogo']}",
                     f"TOKENS_ACEITOS_QUIZ={T['quiz_catalogo']}"],
        "quiz": ["CATALOGO_API_URL=http://catalogo:8000/api/catalogo",
                 f"TOKEN_CATALOGO={T['quiz_catalogo']}"],
        "leads": [f"TOKENS_ACEITOS_ADMIN={T['leads_admin']}",
                  f"TOKENS_ACEITOS_MENSAGERIA={T['leads_mensageria']}"],
        "checkout": ["CATALOGO_API_URL=http://catalogo:8000/api/catalogo",
                     f"TOKEN_CATALOGO={T['checkout_catalogo']}",
                     "PAGAMENTOS_API_URL=http://pagamentos:8000/api/pagamentos",
                     f"TOKEN_PAGAMENTOS={T['checkout_pagamentos']}",
                     f"TOKENS_ACEITOS_ADMIN={T['checkout_admin']}",
                     f"TOKENS_ACEITOS_PAGINAS={T['pagina']}",
                     "MP_PUBLIC_KEY=TEST-fake"],
        "pagamentos": [f"TOKENS_ACEITOS_CHECKOUT={T['checkout_pagamentos']}",
                       "MP_ACCESS_TOKEN=TEST-de-ensaio",
                       f"MP_WEBHOOK_SECRET={T['mp_segredo']}",
                       "PAGAMENTOS_PUBLIC_BASE_URL=https://meshcraft.top",
                       "PUBLIC_BASE_URL=https://meshcraft.top"],
        "mensageria": [f"TOKENS_PUBLICACAO_ADMIN={T['mensageria_admin']}",
                       f"WHATSAPP_GATEWAY_URL={gateway_url}",
                       f"WHATSAPP_GATEWAY_TOKEN={T['gateway']}",
                       f"WHATSAPP_WEBHOOK_TOKEN={T['webhook']}",
                       "LEADS_API_URL=http://leads:8000/api/leads",
                       f"LEADS_API_TOKEN={T['leads_mensageria']}"],
    }
    for servico in SERVICES:
        linhas = [f"DJANGO_SECRET_KEY=segredo-de-ensaio-{servico}", "DEBUG=0",
                  f"SCRIPT_NAME={SCRIPTS.get(servico, '')}"]
        if servico != "funil":
            banco = _banco(postgres, f"e2e_{servico}") if servico in USADAS else "sqlite:///:memory:"
            linhas.append(f"DATABASE_URL={banco}")
        linhas += [f"REDIS_STREAMS_URL={streams}", f"HUEY_REDIS_URL={huey}",
                   f"SITE_ERRORS_REDIS_URL={erros}"]
        linhas += extras.get(servico, [])
        (pasta / f"{servico}.env").write_text("\n".join(linhas) + "\n", encoding="utf-8")


def _subir_aplicacao() -> None:
    """O mesmo começo do entrypoint, sem servidor e sem trabalhadores."""
    import django
    from django.core.management import call_command

    from config.migracoes import preparar_migracoes
    from config.runtime import install_contextual_settings, load_original_settings, serving

    django.setup()
    load_original_settings()
    # A mesma exceção de fixtures usada pelos testes da célula leads. Este
    # processo só existe nos bancos de ensaio confirmados pela fixture mundo.
    from config.runtime import _service_settings
    _service_settings["leads"]["CRM_REJEITAR_TESTES"] = False
    install_contextual_settings()
    preparar_migracoes()
    import time

    t = time.monotonic()
    for servico in USADAS:
        with serving(servico):
            call_command("migrate", database=servico, interactive=False, verbosity=0)
        t = _marca(f"migrate {servico}", t)
    from internal import instalar

    instalar()
    import config.asgi  # noqa: F401  (constrói os handlers antes das threads)


def _semear(host: str = HOST, instancia: str = "instancia-do-ciclo", preco_cents: int = 19700) -> dict:
    """O catálogo, dois quizzes e a conexão do WhatsApp de um site de ensaio."""
    from config.runtime import serving
    from modules.catalogo.apps.ofertas.models import Offer
    from modules.catalogo.apps.produtos.models import Product
    from modules.catalogo.apps.sites.models import Site as SiteDoCatalogo
    from modules.mensageria.apps.whatsapp.models import ConfiguracaoWhatsApp
    from modules.quiz.apps.quiz.models import Option, Question, Quiz, QuizVersion, ResultBand
    from modules.quiz.apps.quiz.models import Site as SiteDoQuiz

    sufixo = uuid.uuid4().hex[:6]
    with serving("catalogo"):
        site = SiteDoCatalogo.objects.create(host=host, name="Loja do ciclo")
        produto = Product.objects.create(slug=f"curso-{sufixo}", name="Curso do ciclo", price_cents=preco_cents)
        oferta = Offer.objects.create(site=site, slug="curso-do-ciclo", product=produto, price_cents=preco_cents)
    site_id = str(site.id)
    with serving("quiz"):
        espelho = SiteDoQuiz.objects.create(id=site_id, host=host, name="Loja do ciclo")
        for slug in ("quiz-a", "quiz-b"):
            quiz = Quiz.objects.create(site=espelho, slug=slug, title=f"Quiz {slug}")
            versao = QuizVersion.objects.create(quiz=quiz, key="v1")
            for ordem in (1, 2):
                pergunta = Question.objects.create(version=versao, order=ordem, text=f"Pergunta {ordem} do {slug}?")
                Option.objects.create(question=pergunta, order=1, text="Ainda não", points=1)
                Option.objects.create(question=pergunta, order=2, text="Sim, quero vender", points=2)
            ResultBand.objects.create(version=versao, key="geral", title="Perfil geral",
                                      description="Resultado do ciclo", min_score=0, max_score=100)
    with serving("mensageria"):
        ConfiguracaoWhatsApp.objects.create(site_id=site_id, instancia=instancia, ativo=True)
    from modules.checkout.apps.pedidos.models import CondicaoDoAgente

    with serving("checkout"):  # o mantenedor libera o Pix da oferta ao agente
        CondicaoDoAgente.objects.create(site_id=site_id, oferta_slug=oferta.slug, condicao_id="pix")
    return {"site_id": site_id, "oferta": oferta.slug, "preco_cents": oferta.price_cents}


@pytest.fixture(scope="session")
def mundo():
    postgres, redis_url = os.environ.get("E2E_POSTGRES_URL"), os.environ.get("E2E_REDIS_URL")
    if not postgres or not redis_url:
        pytest.skip("defina E2E_POSTGRES_URL e E2E_REDIS_URL para rodar o ciclo ponta a ponta")
    if "config.settings" in sys.modules:
        pytest.skip("rode `pytest tests/e2e` sozinho: a configuração da aplicação já foi carregada por outra prova")
    # Esta fixture apaga bancos `e2e_*` e esvazia bancos do Redis: nunca num servidor que não seja local.
    for nome, url in (("E2E_POSTGRES_URL", postgres), ("E2E_REDIS_URL", redis_url)):
        servidor = urlsplit(url).hostname or ""
        if servidor not in SERVIDORES_LOCAIS:
            pytest.fail(f"{nome} aponta para '{servidor}': o ciclo ponta a ponta só roda em servidor local "
                        f"({', '.join(SERVIDORES_LOCAIS)}), porque apaga e recria bancos de teste", pytrace=False)
    _preparar_modulos()
    import redis as redis_lib

    for numero in (7, 8, 9):
        redis_lib.from_url(_redis(redis_url, numero)).flushdb()
    _criar_bancos(postgres)

    from ciclo_comercial import Ambiente, Cena, Ciclo, GatewayFalso, ProvedoresFalsos, Rotas, iniciar_consumidores

    gateway = GatewayFalso()
    pasta = tempfile.TemporaryDirectory(prefix="ciclo-env-")
    os.environ["APLICACAO_ENV_DIR"] = pasta.name
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
    from importlib import import_module

    # `config.registry` não precisa de configuração: ele só lista as células.
    _escrever_ambientes(Path(pasta.name), postgres, redis_url, gateway.url)
    _subir_aplicacao()
    provedores = ProvedoresFalsos().instalar()
    dados = _semear()
    outro = _semear(HOST_OUTRO, "instancia-do-outro-site", 29700)
    cena = Cena(host=HOST, site_id=dados["site_id"], quiz_a="quiz-a", quiz_b="quiz-b",
                oferta=dados["oferta"], preco_cents=dados["preco_cents"])
    rotas = Rotas.de(leads=T["leads_mensageria"], leads_admin=T["leads_admin"],
                     mensageria=T["mensageria_admin"], checkout=T["checkout_admin"], quiz="")
    ambiente = Ambiente(rotas=rotas, gateway=gateway, provedores=provedores, token_pagina=T["pagina"],
                        webhook_whatsapp=T["webhook"], mp_segredo=T["mp_segredo"],
                        instancia="instancia-do-ciclo")
    trabalhadores = iniciar_consumidores()
    import_module("time").sleep(1)
    ciclo = Ciclo(cena, ambiente)
    ciclo.outro_site = Ciclo(
        Cena(host=HOST_OUTRO, site_id=outro["site_id"], quiz_a="quiz-a", quiz_b="quiz-b",
             oferta=outro["oferta"], preco_cents=outro["preco_cents"]),
        replace(ambiente, instancia="instancia-do-outro-site"))
    yield ciclo
    trabalhadores.parar.set()
    provedores.remover()
    gateway.parar()
    pasta.cleanup()
    _limpar(postgres, redis_url)
