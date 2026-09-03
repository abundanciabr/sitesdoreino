"""A aba "Os robôs" (29/08/2026) — o quadro da fila, calculado, nunca digitado.

O que estes guardas protegem:

1. **A tela serve o que o build materializou** (`fila_embutida/estados.json`)
   — ela não recalcula estado nenhum: recalcular seria a segunda definição de
   "em que pé está", e as duas divergiriam.
2. **Fila ausente se DECLARA** (500 + explicação), nunca vira quadro vazio —
   "não há trabalho" seria mentira, a mesma lei do painel ausente.
3. **O CSP continua estrito**: a ilha de script entra por hash (nunca
   `'unsafe-inline'`), e `connect-src` abre SÓ para `api.github.com` — sem
   isso o bloco "ao vivo" morreria em silêncio no navegador.
4. **Nada daqui sai para a internet no servidor**: `respx.mock` estoura em
   qualquer chamada não registrada — quem pergunta ao GitHub é o NAVEGADOR
   do dono, nunca esta célula.
"""

import json
import re

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.core import robos

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


def _dentro() -> Client:
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "id-opaco-123",
                "nome_exibido": "Fulano",
                "papel": None,
                "email": DONO,
            },
        )
    )
    c = Client()
    c.defaults["HTTP_COOKIE"] = COOKIE
    return c


def fila_de_mentira(tmp_path, monkeypatch, com_esperas=True):
    """Uma fila embutida como o deploy a deixaria — estados JÁ materializados."""
    pasta = tmp_path / "fila_embutida"
    (pasta / "esperas").mkdir(parents=True)
    (pasta / "estados.json").write_text(
        json.dumps(
            {
                "TAR-001": {
                    "estado": "concluída",
                    "motivo": "https://github.com/x/y/pull/516",
                    "quem": "sessao-semeadura",
                    "titulo": "Semear a fila",
                    "toca": ["fila"],
                },
                "TAR-002": {
                    "estado": "reivindicada",
                    "motivo": "",
                    "quem": "sessao-aba",
                    "titulo": "Construir a aba",
                    "toca": ["admin"],
                },
                "TAR-003": {
                    "estado": "bloqueada",
                    "motivo": "aguardando despacho do mantenedor",
                    "quem": None,
                    "titulo": "Backup antes de migração",
                    "toca": ["infra"],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (pasta / "regua.json").write_text(
        json.dumps(
            {
                "medido_em": "2026-08-29",
                "esperas": {
                    "checks": {
                        "rotulo": "os testes de um PR",
                        "p50_s": 90,
                        "p90_s": 180,
                        "amostra": 62,
                    },
                    "pouso": {
                        "rotulo": "o pouso pela pista",
                        "p50_s": 420,
                        "p90_s": 900,
                        "amostra": 5,
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    if com_esperas:
        (pasta / "esperas" / "resumo-20260829-120000.json").write_text(
            json.dumps(
                {
                    "gerado_em": "2026-08-29T12:00:00+00:00",
                    "total": 10,
                    "verdes": 9,
                    "por_classe": {},
                    "estouros": [
                        {
                            "quando_utc": "2026-08-29T03:00:00+00:00",
                            "alvo": "sonda:docker",
                            "dizendo": "o Docker acordar",
                            "teto_s": 300,
                            "decorrido_s": 300,
                            "desfecho": "estourou",
                            "detalhe": "morreu no teto",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    monkeypatch.setattr(robos, "CANDIDATOS", (pasta,))
    return pasta


def texto(resposta) -> str:
    return resposta.content.decode()


# A folha de estilo desta aba mora DENTRO do corpo da resposta, então toda
# asserção de "isto NÃO está na tela" precisa podá-la antes de medir — senão um
# nome de classe ou um comentário de CSS vira falso vermelho num teste que não
# tem nada a ver com estilo (`armadilhas/247`).
RE_ESTILO = re.compile(r"<style\b[^>]*>.*?</style\s*>", re.DOTALL | re.IGNORECASE)


def texto_sem_estilo(resposta) -> str:
    return RE_ESTILO.sub("", resposta.content.decode())


@respx.mock
def test_o_quadro_mostra_o_que_o_build_materializou(tmp_path, monkeypatch):
    fila_de_mentira(tmp_path, monkeypatch)
    pagina = texto(_dentro().get(reverse("caixa_robos")))

    assert "TAR-002" in pagina and "Construir a aba" in pagina
    assert "sessao-aba" in pagina
    # A bloqueada carrega o MOTIVO — é a coluna que pede gente, não máquina.
    assert "aguardando despacho do mantenedor" in pagina
    # A concluída aparece com a prova por perto.
    assert "pull/516" in pagina


@respx.mock
def test_o_de_agora_vem_antes_do_retrato(tmp_path, monkeypatch):
    """A ordem da página é POR URGÊNCIA, e isso é o conserto de 03/09/2026.

    Até esta data a tela era um kanban de colunas lado a lado, e a coluna das
    concluídas (76 cartões em produção) empurrava o bloco ao vivo — a única
    coisa realmente de agora — para dezenas de rolares abaixo da dobra. O
    mantenedor abriu a tela e disse que não conseguia acompanhá-la.
    """
    fila_de_mentira(tmp_path, monkeypatch)
    pagina = texto_sem_estilo(_dentro().get(reverse("caixa_robos")))

    ao_vivo = pagina.find("Agora, neste minuto")
    parou = pagina.find("Pararam no meio do caminho")
    ja_terminaram = pagina.find("Já terminaram")

    assert ao_vivo != -1 and parou != -1 and ja_terminaram != -1
    assert ao_vivo < parou, "o que é de agora ficou abaixo do retrato do deploy"
    assert parou < ja_terminaram, "a história antiga passou na frente do que parou"


@respx.mock
def test_a_historia_nasce_fechada_e_o_que_pede_gente_nasce_aberto(
    tmp_path, monkeypatch
):
    """Concluídas e canceladas são história: elas entram num `details` FECHADO.

    Em produção são 76 cartões que não pedem nada de ninguém. Abertos, eles
    são a página inteira; fechados, são uma linha com um número do lado.
    """
    fila_de_mentira(tmp_path, monkeypatch)
    pagina = texto_sem_estilo(_dentro().get(reverse("caixa_robos")))

    depois_do_details = pagina.split("<details>")[-1]
    assert "Já terminaram" in depois_do_details, "a história voltou a nascer aberta"
    assert "<details open" not in pagina
    # O que parou esperando alguém NUNCA fica atrás de um clique.
    assert "Pararam no meio do caminho" not in depois_do_details


@respx.mock
def test_a_tela_fala_portugues_e_nao_o_vocabulario_da_fila(tmp_path, monkeypatch):
    """Os estados da fila são contrato; o mantenedor é leigo.

    "reivindicada", "em execução" e "toca" são o vocabulário de `ci/fila.py` e
    continuam intactos NO DADO. O que chega à tela é a tradução — a mesma lei
    do painel do dono, que não tem sigla.
    """
    fila_de_mentira(tmp_path, monkeypatch)
    pagina = texto_sem_estilo(_dentro().get(reverse("caixa_robos")))

    assert "Um robô pegou, e está com ela agora" in pagina
    assert "mexe em: infra" in pagina
    assert "reivindicada" not in pagina
    assert "toca:" not in pagina


@respx.mock
def test_o_endereco_da_prova_vira_link_clicavel(tmp_path, monkeypatch):
    """A prova de uma concluída é um endereço, e endereço em texto cru obriga o
    mantenedor a selecionar e copiar à mão."""
    fila_de_mentira(tmp_path, monkeypatch)
    pagina = texto(_dentro().get(reverse("caixa_robos")))

    assert 'href="https://github.com/x/y/pull/516"' in pagina


@respx.mock
def test_as_esperas_mostram_o_que_estourou_e_a_regua(tmp_path, monkeypatch):
    fila_de_mentira(tmp_path, monkeypatch)
    pagina = texto(_dentro().get(reverse("caixa_robos")))

    assert "o Docker acordar" in pagina
    assert "os testes de um PR" in pagina
    # Régua honesta: amostra pequena se declara na tela.
    assert "pouca amostra" in pagina


@respx.mock
def test_sem_resumo_de_esperas_a_pagina_diz_isso(tmp_path, monkeypatch):
    fila_de_mentira(tmp_path, monkeypatch, com_esperas=False)
    pagina = texto(_dentro().get(reverse("caixa_robos")))

    assert "ainda não foi exportado" in pagina


@respx.mock
def test_fila_ausente_se_declara_nunca_finge_vazio(tmp_path, monkeypatch):
    monkeypatch.setattr(robos, "CANDIDATOS", (tmp_path / "nao-existe",))
    resposta = _dentro().get(reverse("caixa_robos"))

    assert resposta.status_code == 500
    assert "não veio nesta imagem" in texto(resposta)


@respx.mock
def test_o_csp_tem_hash_da_ilha_e_connect_src_do_github(tmp_path, monkeypatch):
    fila_de_mentira(tmp_path, monkeypatch)
    resposta = _dentro().get(reverse("caixa_robos"))

    csp = resposta["Content-Security-Policy"]
    assert "connect-src 'self' https://api.github.com" in csp
    assert "'sha256-" in csp
    # A linha de script NUNCA afrouxa — mesma lei do painel.
    assert "script-src 'self' 'sha256-" in csp
    assert "unsafe-inline" not in csp.split("style-src")[0]
