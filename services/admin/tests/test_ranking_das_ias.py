"""O ranking das IAs na TELA — o que ele mostra, e o que ele se recusa a inventar.

A conta mora em `ci/ranking_das_ias.py` e é medida lá
(`ci/tests/test_ranking_das_ias.py`). Aqui se guarda o outro lado: a tela lê o
retrato publicado, ORDENA, e nada mais.

As quatro coisas que este arquivo existe para impedir, todas já vividas em
alguma tela deste repositório:

1. **Retrato ausente virar ranking zerado.** "Ninguém entregou nada" e "ainda não
   foi medido" são frases diferentes, e a primeira é a que faria o mantenedor
   cortar o plano de alguém por engano.
2. **A tela refazer a conta do gerador.** Dois lugares somando o mesmo fato já
   custaram uma divergência medida nesta casa — o Python dizia 6 e o painel
   dizia 7 (`apps/core/pendencias.py`).
3. **Custo por página aparecer como zero para quem não publicou.** Zero linha
   por página se lê como "publicou de graça", que é o oposto do fato.
4. **A linha sem assinatura entrar no pódio.** Ela é trabalho de dono
   desconhecido; premiá-la ou escondê-la estraga o ranking dos dois jeitos.
"""

from __future__ import annotations

import json
from html import unescape
from pathlib import Path

import httpx
import pytest
import respx
from django.test import Client
from django.urls import get_script_prefix, set_script_prefix

from apps.core import ranking_das_ias as tela

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"
TELA = "/ranking-ias/"


@pytest.fixture
def sob_o_prefixo_publico():
    """Emula o prefixo de thread do servidor e restaura o anterior (081)."""
    anterior = get_script_prefix()
    set_script_prefix("/admin/")
    try:
        yield
    finally:
        set_script_prefix(anterior)


@pytest.fixture(autouse=True)
def porta_aberta(settings, monkeypatch):
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
    cliente = Client()
    cliente.defaults["HTTP_COOKIE"] = COOKIE
    return cliente


def _ia(chave: str, nome: str, papel: str, **medidas) -> dict:
    base = {
        "entregas": 0,
        "paginas": 0,
        "linhas": 0,
        "retrabalho": 0,
        "dias_ativos": 0,
        "ultima_entrega": None,
    }
    return {"chave": chave, "nome": nome, "papel": papel, **base, **medidas}


def publicar(tmp_path: Path, monkeypatch, retrato: "dict | None") -> Path:
    """Põe (ou não põe) o retrato na pasta que a tela lê."""
    pasta = tmp_path / "painel"
    pasta.mkdir(exist_ok=True)
    if retrato is not None:
        (pasta / "ranking-ias.json").write_text(
            json.dumps(retrato, ensure_ascii=False), encoding="utf-8"
        )
    monkeypatch.setattr(tela, "diretorio_do_painel", lambda: pasta)
    return pasta


def retrato_de_exemplo(**trocas) -> dict:
    base = {
        "versao": 1,
        "gerado_em": "2026-09-17T18:00:00+00:00",
        "base": "origin/main",
        "commit_da_base": "e7cd92e89c6f5b1276f9bee130aa0c9017b6aac9",
        "ias": [
            _ia(
                "claude-code",
                "Claude Code",
                "Maestro",
                paginas=112,
                entregas=2305,
                linhas=549919,
                retrabalho=84,
                dias_ativos=27,
                ultima_entrega="2026-09-17T14:40:08+00:00",
            ),
            _ia(
                "codex",
                "Codex",
                "Executor",
                paginas=10,
                entregas=633,
                linhas=56076,
                retrabalho=34,
                dias_ativos=10,
                ultima_entrega="2026-09-17T14:59:22+00:00",
            ),
            _ia("antigravity", "Antigravity", "Sentinela"),
        ],
        "sem_assinatura": {
            "entregas": 437,
            "paginas": 11,
            "linhas": 56679,
            "retrabalho": 68,
            "dias_ativos": 31,
            "ultima_entrega": "2026-09-17T15:41:41+00:00",
        },
    }
    base.update(trocas)
    return base


def _texto(resposta) -> str:
    return resposta.content.decode()


@respx.mock
def test_sem_retrato_a_tela_diz_o_que_falta_e_o_comando(tmp_path, monkeypatch):
    publicar(tmp_path, monkeypatch, None)

    pagina = _texto(_dentro().get(TELA))

    assert "ainda não foi medido" in pagina
    assert "python ci/ranking_das_ias.py" in pagina, "erro sem saída não é erro útil"
    assert (
        "0º" not in pagina and "Plano Premium" not in pagina
    ), "sem medição não existe pódio para mostrar"


@respx.mock
def test_retrato_de_versao_desconhecida_nao_e_lido_pela_metade(tmp_path, monkeypatch):
    publicar(tmp_path, monkeypatch, retrato_de_exemplo(versao=99))

    pagina = _texto(_dentro().get(TELA))
    assert "A versão do retrato não é compatível" in pagina
    assert "python ci/ranking_das_ias.py" in pagina
    assert "não está na publicação" not in pagina


@respx.mock
def test_o_podio_ordena_por_pagina_publicada(tmp_path, monkeypatch):
    publicar(tmp_path, monkeypatch, retrato_de_exemplo())

    pagina = _texto(_dentro().get(TELA))
    ordem = [pagina.index(nome) for nome in ("Claude Code", "Codex", "Antigravity")]

    assert ordem == sorted(ordem)
    assert pagina.index("Plano Premium") < pagina.index("Plano Médio")
    assert pagina.index("Plano Médio") < pagina.index("Zona de eliminação")


def test_empate_em_paginas_e_desempatado_pelo_custo():
    """Regra do mantenedor: entre duas que publicaram o mesmo, ganha a mais barata."""
    cara = tela.Participante(
        "Cara",
        "x",
        paginas=5,
        entregas=1,
        linhas=5000,
        retrabalho=0,
        dias_ativos=1,
        ultima_entrega=None,
    )
    barata = tela.Participante(
        "Barata",
        "x",
        paginas=5,
        entregas=1,
        linhas=500,
        retrabalho=0,
        dias_ativos=1,
        ultima_entrega=None,
    )

    podio = tela.classificar([cara, barata])

    assert [p.nome for p in podio] == ["Barata", "Cara"]
    assert podio[0].plano == "Plano Premium"


def test_quem_nao_publicou_pagina_fica_atras_de_quem_publicou_uma():
    """Commit não é entrega. Movimento sem publicação não sobe no tela."""
    ocupada = tela.Participante(
        "Ocupada",
        "x",
        paginas=0,
        entregas=900,
        linhas=90000,
        retrabalho=0,
        dias_ativos=30,
        ultima_entrega=None,
    )
    publicou = tela.Participante(
        "Publicou",
        "x",
        paginas=1,
        entregas=2,
        linhas=40,
        retrabalho=0,
        dias_ativos=1,
        ultima_entrega=None,
    )

    assert [p.nome for p in tela.classificar([ocupada, publicou])] == [
        "Publicou",
        "Ocupada",
    ]


def test_sem_pagina_o_custo_por_pagina_nao_existe_e_nao_e_zero():
    parada = tela.Participante(
        "Parada",
        "x",
        paginas=0,
        entregas=0,
        linhas=0,
        retrabalho=0,
        dias_ativos=0,
        ultima_entrega=None,
    )

    assert parada.custo_por_pagina is None
    assert parada.dias_por_pagina is None
    assert parada.retrabalho_por_cento is None, "0 de 0 entregas não é 0% de retrabalho"


@respx.mock
def test_sem_assinatura_aparece_fora_do_podio(tmp_path, monkeypatch):
    publicar(tmp_path, monkeypatch, retrato_de_exemplo())

    pagina = _texto(_dentro().get(TELA))

    assert "Sem autoria única" in pagina, "437 entregas não podem sumir da tela"
    assert "fora do pódio" in pagina
    assert pagina.index("Zona de eliminação") < pagina.index(
        "fora do pódio"
    ), "a linha sem dono vem depois das três, nunca no meio delas"


@respx.mock
def test_a_tela_declara_o_que_nao_enxerga(tmp_path, monkeypatch):
    publicar(tmp_path, monkeypatch, retrato_de_exemplo())

    pagina = _texto(_dentro().get(TELA))

    assert (
        "Tokens consumidos" in pagina
    ), "a coluna pedida não existe; a tela tem de dizer por quê"
    # Cada lacuna sai verbatim: casar por pedaço deixaria a tela perder metade
    # da frase sem o teste notar.
    for lacuna in tela.O_QUE_NAO_ENXERGO:
        assert lacuna in pagina


@respx.mock
def test_linha_incompleta_cai_sozinha_e_a_pagina_continua(tmp_path, monkeypatch):
    quebrado = retrato_de_exemplo()
    quebrado["ias"][1] = {"chave": "codex", "nome": "Codex", "papel": "Executor"}
    publicar(tmp_path, monkeypatch, quebrado)

    pagina = _texto(_dentro().get(TELA))

    assert "Claude Code" in pagina, "uma linha torta não derruba as outras duas"
    assert "Ranking parcial" in pagina, "e a falta é dita, nunca silenciosa"


@respx.mock
def test_de_fora_nao_ve_o_ranking(tmp_path, monkeypatch):
    publicar(tmp_path, monkeypatch, retrato_de_exemplo())
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "id-opaco-999",
                "nome_exibido": "Estranho",
                "papel": None,
                "email": "estranho@exemplo.com",
            },
        )
    )
    cliente = Client()
    cliente.defaults["HTTP_COOKIE"] = COOKIE

    resposta = cliente.get(TELA)

    assert resposta.status_code != 200
    assert "Claude Code" not in _texto(resposta)


@respx.mock
def test_a_visao_geral_oferece_a_porta_do_ranking_das_ias(sob_o_prefixo_publico):
    # guarda: services/admin/tests/test_ranking_das_ias.py:47
    pagina = unescape(_texto(_dentro().get("/")))

    assert "Ver o ranking das IAs →" in pagina
    assert 'href="/admin/ranking-ias/"' in pagina


@pytest.mark.parametrize("ias", [None, {}, "invalido", []])
@respx.mock
def test_retrato_sem_lista_de_ias_nao_inventa_podio(tmp_path, monkeypatch, ias):
    # guarda: services/admin/apps/core/ranking_das_ias.py:209
    publicar(tmp_path, monkeypatch, retrato_de_exemplo(ias=ias))
    resposta = _dentro().get(TELA)

    assert resposta.status_code == 200
    assert "O retrato está inválido" in _texto(resposta)
    assert "Plano Premium" not in _texto(resposta)


@respx.mock
def test_participante_ausente_e_anunciado(tmp_path, monkeypatch):
    dados = retrato_de_exemplo()
    dados["ias"].pop()
    publicar(tmp_path, monkeypatch, dados)

    assert "Ranking parcial" in _texto(_dentro().get(TELA))


@pytest.mark.parametrize("campo,valor", [("paginas", True), ("ultima_entrega", 123)])
@respx.mock
def test_linha_invalida_nao_quebra_a_pagina(tmp_path, monkeypatch, campo, valor):
    # guarda: services/admin/apps/core/ranking_das_ias.py:138
    dados = retrato_de_exemplo()
    dados["ias"][0][campo] = valor
    publicar(tmp_path, monkeypatch, dados)

    resposta = _dentro().get(TELA)
    assert resposta.status_code == 200
    assert "Ranking parcial" in _texto(resposta)


def test_custo_zero_ganha_de_custo_positivo():
    sem_custo = tela.Participante("Zero", "x", 1, 1, 0, 0, 0, None)
    com_custo = tela.Participante("Cara", "x", 1, 1, 5, 0, 1, None)

    assert tela.classificar([com_custo, sem_custo])[0].nome == "Zero"


@respx.mock
def test_json_malformado_pede_regeneracao_sem_dizer_que_arquivo_falta(
    tmp_path, monkeypatch
):
    pasta = publicar(tmp_path, monkeypatch, None)
    (pasta / "ranking-ias.json").write_text("{incompleto", encoding="utf-8")

    resposta = _dentro().get(TELA)
    pagina = _texto(resposta)
    assert resposta.status_code == 200
    assert "O retrato está inválido" in pagina
    assert "python ci/ranking_das_ias.py" in pagina
    assert "não está na publicação" not in pagina


@pytest.mark.parametrize("sem_assinatura", [None, {}, {"paginas": 1}])
@respx.mock
def test_bloco_sem_assinatura_invalido_e_anunciado(
    tmp_path, monkeypatch, sem_assinatura
):
    publicar(tmp_path, monkeypatch, retrato_de_exemplo(sem_assinatura=sem_assinatura))

    assert "Ranking parcial" in _texto(_dentro().get(TELA))


@pytest.mark.parametrize("chave", ["codex", "desconhecida", None])
@respx.mock
def test_identidade_duplicada_ou_desconhecida_nao_forma_podio(
    tmp_path, monkeypatch, chave
):
    # guarda: services/admin/apps/core/ranking_das_ias.py:219
    dados = retrato_de_exemplo()
    dados["ias"][0]["chave"] = chave
    publicar(tmp_path, monkeypatch, dados)

    pagina = _texto(_dentro().get(TELA))
    assert "O retrato está inválido" in pagina
    assert "Plano Premium" not in pagina


@respx.mock
def test_sem_a_lider_o_retrato_parcial_nao_atribui_planos(tmp_path, monkeypatch):
    dados = retrato_de_exemplo()
    dados["ias"].pop(0)
    publicar(tmp_path, monkeypatch, dados)

    pagina = _texto(_dentro().get(TELA))
    assert "Ranking parcial" in pagina
    assert "Codex" in pagina
    assert "Plano Premium" not in pagina
    assert "Plano Médio" not in pagina
    assert "Zona de eliminação" not in pagina
    assert "python ci/ranking_das_ias.py" in pagina


@pytest.mark.parametrize(
    "identidade",
    [{}, {"nome": None, "papel": None}, {"nome": "Codex", "papel": "Executor"}],
)
@respx.mock
def test_nome_e_papel_vem_da_identidade_canonica(tmp_path, monkeypatch, identidade):
    dados = retrato_de_exemplo()
    dados["ias"][0].pop("nome")
    dados["ias"][0].pop("papel")
    dados["ias"][0].update(identidade)
    publicar(tmp_path, monkeypatch, dados)

    pagina = _texto(_dentro().get(TELA))
    assert '<b>Claude Code</b><span class="papel">Maestro</span>' in pagina
