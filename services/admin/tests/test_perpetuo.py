"""A área do lançamento perpétuo, `/admin/perpetuo/` (02/09/2026).

O que estes guardas protegem:

1. **Nenhuma porta escrita na máquina aponta para o vazio.** As seis peças
   nomeiam endereços do site, e quem descreve esses endereços é
   `painel/mapa-do-site.json`. Um endereço que mudar de forma lá e continuar
   escrito aqui vira link para 404, e o mantenedor conclui que o site quebrou.
   Este é o guarda principal do arquivo, e o motivo de ele existir.
2. **A tela não guarda cópia de nome nem de explicação.** O que ela mostra de
   cada porta sai do mapa. Uma segunda cópia aqui dentro seria a duplicação que
   o `CLAUDE.md` proíbe, e envelheceria em silêncio.
3. **Molde não vira link** (`/quiz/quiz/<slug:slug>/` não é um lugar).
4. **Mapa ausente se DECLARA**, e a página abre mesmo assim: as seis peças são
   conceito, e continuam verdadeiras sem o arquivo. O que não pode é a tela
   ficar calada sobre os links que faltam.
5. **A porta continua sendo a porta**: sem crachá, esta página não abre.
6. **A visão geral leva até aqui.** Botão que ninguém encontra é
   funcionalidade que não existe, e foi assim que o editor de documentos passou
   dois dias invisível.
"""

import json
import re
from pathlib import Path

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.core import perpetuo

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


def _mapa() -> dict:
    """O `painel/mapa-do-site.json` de verdade, indexado pelo endereço."""
    mapa = perpetuo._mapa_por_endereco()
    assert mapa is not None, (
        "o mapa do site não foi encontrado — em produção ele vem em "
        "`painel_embutido/`, num checkout em `painel/`. Se este assert falhou, "
        "a tela do perpétuo abriria sem link nenhum."
    )
    return mapa


def test_toda_porta_existe_no_mapa_do_site():
    """O guarda principal: endereço escrito numa peça que o mapa não conhece.

    Sem ele, o dia em que alguém renomear uma rota (e atualizar o mapa, porque
    lá a muralha obriga) esta tela continuaria oferecendo o endereço velho, e
    ninguém saberia até o mantenedor clicar e cair num 404.

    A mensagem de falha traz o endereço EXATO e o que fazer, porque quem vai
    lê-la é o robô que quebrou isto sem saber que esta tela existia.
    """
    mapa = _mapa()
    orfas = [
        (etapa["chave"], endereco)
        for etapa in perpetuo.ETAPAS
        for endereco in etapa["portas"]
        if endereco not in mapa
    ]
    assert not orfas, (
        f"endereços que a máquina do perpétuo cita e o mapa do site não tem: "
        f"{orfas}. Conserte a lista `ETAPAS` em apps/core/perpetuo.py com o "
        f"endereço novo (o certo está em painel/mapa-do-site.json), ou tire a "
        f"porta da peça se a tela deixou de existir."
    )


def test_nenhuma_peca_fica_sem_porta():
    """Peça sem porta nenhuma é um cartão que não ensina nada.

    Não é obrigação eterna do desenho: é a afirmação de que, HOJE, cada uma das
    seis etapas tem ao menos um lugar do site que a serve. No dia em que uma
    peça ficar vazia de verdade, o texto dela precisa dizer isso em voz alta,
    e não sumir por dentro.
    """
    vazias = [e["chave"] for e in perpetuo.ETAPAS if not e["portas"]]
    assert not vazias, f"peças sem porta nenhuma: {vazias}"


def test_o_codigo_nao_guarda_copia_do_nome_das_telas():
    """A lei anti-duplicação, medida: o nome de uma porta não mora aqui.

    Se um título do mapa aparecer escrito dentro de `perpetuo.py`, existem duas
    verdades sobre o nome daquela tela — e no dia em que divergirem, ninguém
    sabe qual está certa.
    """
    fonte = Path(perpetuo.__file__).read_text(encoding="utf-8")
    copiados = [
        entrada["titulo"]
        for entrada in _mapa().values()
        if entrada.get("titulo") and entrada["titulo"] in fonte
    ]
    assert not copiados, f"títulos de tela copiados para dentro do código: {copiados}"


@respx.mock
def test_a_pagina_abre_e_mostra_as_seis_pecas():
    resposta = _dentro().get(reverse("perpetuo"))
    assert resposta.status_code == 200
    html = resposta.content.decode()
    for etapa in perpetuo.ETAPAS:
        assert etapa["nome"] in html, f"a peça {etapa['chave']} sumiu da tela"
    assert len(perpetuo.ETAPAS) == 6


@respx.mock
def test_o_nome_de_cada_porta_vem_do_mapa_e_chega_a_tela():
    """O que a tela mostra de uma porta é o que o mapa diz dela, hoje."""
    html = _dentro().get(reverse("perpetuo")).content.decode()
    mapa = _mapa()
    sumidos = [
        mapa[endereco]["titulo"]
        for etapa in perpetuo.ETAPAS
        for endereco in etapa["portas"]
        if endereco in mapa and mapa[endereco]["titulo"] not in html
    ]
    assert not sumidos, f"portas que sumiram no caminho: {sumidos}"


@respx.mock
def test_molde_nao_vira_link():
    """`/quiz/quiz/<slug:slug>/` não é um lugar: é a forma de todos os quizzes.

    Oferecê-lo como link manda o mantenedor para um 404, e ele conclui que o
    site quebrou. A regra de quando um endereço vira link é a do mapa do site,
    reusada e não copiada.
    """
    html = _dentro().get(reverse("perpetuo")).content.decode()
    assert 'href="/quiz/quiz/' not in html
    assert "/quiz/quiz/" in html, "mas o endereço continua à vista, como texto"


@respx.mock
def test_endereco_fora_do_mapa_grita_em_vez_de_sumir(monkeypatch):
    """Sumir em silêncio é a pior forma de perder um fato.

    Aqui a peça cita um endereço que o mapa não conhece: a linha precisa
    aparecer, com o endereço legível, e não desaparecer da lista.
    """
    inventado = "/isto-nao-existe-em-lugar-nenhum"
    monkeypatch.setattr(
        perpetuo,
        "ETAPAS",
        (
            {
                "chave": "teste",
                "nome": "Peça de teste",
                "pergunta": "?",
                "resumo": "...",
                "portas": (inventado,),
            },
        ),
    )
    html = _dentro().get(reverse("perpetuo")).content.decode()
    assert inventado in html
    assert "fora do mapa do site" in html


@respx.mock
def test_sem_o_mapa_a_pagina_abre_e_diz_que_faltou(monkeypatch):
    """Diferente do `/admin/mapa/`, que devolve 500: lá o arquivo É a página.

    Aqui as seis peças continuam verdadeiras sem ele. O que não pode é a tela
    ficar calada: um cartão sem links, sem explicação, seria lido como "esta
    peça não existe".
    """
    monkeypatch.setattr(perpetuo, "arquivo_do_mapa", lambda: None)
    resposta = _dentro().get(reverse("perpetuo"))
    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert "Não consegui ler o mapa do site" in html
    assert perpetuo.ETAPAS[0]["nome"] in html


@respx.mock
def test_arquivo_torto_nao_vira_tela_pela_metade(monkeypatch, tmp_path):
    torto = tmp_path / "mapa-do-site.json"
    torto.write_text('{"enderecos": ', encoding="utf-8")
    monkeypatch.setattr(perpetuo, "arquivo_do_mapa", lambda: torto)
    html = _dentro().get(reverse("perpetuo")).content.decode()
    assert "Não consegui ler o mapa do site" in html


@respx.mock
def test_sem_cracha_a_pagina_nao_abre():
    respx.get(SESSAO).mock(
        return_value=httpx.Response(200, json={"autenticado": False})
    )
    assert Client().get(reverse("perpetuo")).status_code != 200


@respx.mock
def test_a_visao_geral_leva_ate_a_area():
    """Botão que ninguém encontra é funcionalidade que não existe."""
    html = _dentro().get(reverse("visao_geral")).content.decode()
    assert f'href="{reverse("perpetuo")}"' in html


def test_o_mapa_do_site_conhece_esta_tela():
    """A muralha do cartógrafo já exige isto no CI; aqui a suíte da célula
    reprova antes, com a mensagem que diz onde escrever.

    A pergunta é pela ROTA (`perpetuo/`, a string exata do `urls.py`), e NÃO
    por `reverse()`: nesta suíte não há `SCRIPT_NAME`, então `reverse` devolve
    `/perpetuo/` enquanto o endereço público é `/admin/perpetuo/`. Compor
    endereço de célula somando prefixo é a `armadilhas/197`, e a primeira
    versão deste teste caiu nela.
    """
    caminho = perpetuo.arquivo_do_mapa()
    assert caminho is not None
    entradas = json.loads(caminho.read_text(encoding="utf-8"))["enderecos"]
    assert any(
        e.get("celula") == "admin" and e.get("rota") == "perpetuo/" for e in entradas
    ), (
        "a rota nova precisa de uma entrada em painel/mapa-do-site.json — "
        "o formato está no `_doc` do próprio arquivo"
    )


def test_a_tela_nao_traz_estilo_na_marcacao():
    """O estilo mora em admin/base.html. Um `style=` aqui voltaria a espalhar
    desenho pela marcação, que é o que `test_estilo_nao_volta_para_a_marcacao`
    varre na célula inteira; esta é a mesma régua, apontada para esta tela."""
    caminho = Path(perpetuo.__file__).parent / "templates" / "admin" / "perpetuo.html"
    assert not re.search(r"\sstyle=", caminho.read_text(encoding="utf-8"))
