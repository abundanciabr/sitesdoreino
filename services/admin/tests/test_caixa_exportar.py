"""A aba que exporta a Caixa inteira em texto (02/09/2026).

Por que esta tela existe: o robô não consegue ler UMA linha do que os alunos
escreveram. Não é falta de permissão, é o desenho — o texto de uma ideia só
existe atrás do login, e a porta da administração é do mantenedor. O livro já
registrava a parede em 31/08 (`20260831-002`): *"eu enxergo a contagem, não o
conteúdo"*. Sem esta tela, "analise as sugestões da turma" custava a ele abrir
ideia por ideia e copiar cada uma à mão.

O que estes guardas protegem, em ordem de quanto dói perder:

1. **Nome de aluno não sai daqui.** É a decisão de privacidade da tela, e a
   única que ninguém percebe estar quebrada olhando a página: o texto parece
   igual com ou sem o nome, e quem descobre é a pessoa cujo nome viajou.
2. **O texto do aluno sai inteiro** — problema e solução proposta. Uma
   exportação que resume é uma exportação que decide por quem vai analisar.
3. **O que NÃO veio está dito no que sai.** Análise que não sabe o que falta
   inventa o que falta.
4. **A página não tem JavaScript.** A porta manda `script-src 'self'`; um botão
   de copiar custaria uma exceção na política, e o campo de texto faz o mesmo.
5. **Texto de aluno não vira marcação.** Quem escreve a ideia é de fora, e a
   tela renderiza o que ele escreveu.

A rede é dublada com `respx`, como nos irmãos desta pasta: além de isolar, é
prova mecânica de que nada aqui sai para a internet.
"""

import re

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
CAIXA = "http://sugestoes:8000/interno"
IDEIAS = f"{CAIXA}/gestao/ideias"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"

AUTOR = "Larissa Mendonca"


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    monkeypatch.setenv("SUGESTOES_API_URL", CAIXA)
    monkeypatch.setenv("SUGESTOES_API_TOKEN", "token-do-par-admin-sugestoes")
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


def ideia(**campos) -> dict:
    """Uma ideia na forma EXATA que o contrato promete."""
    base = {
        "id": 1,
        "titulo": "Aula de retopologia para quem trava no high poly",
        "problema": "Modelo bonito no Blender e o Roblox recusa por contagem de faces.",
        "solucao_proposta": "Uma aula curta so de reduzir malha sem perder o formato.",
        "categoria": "Blender e modelagem 3D",
        "status": "em_analise",
        "votos": 12,
        "comentarios": 3,
        "pessoas": 9,
        "autor": AUTOR,
        "criada_em": "2026-09-01T10:00:00+00:00",
        "parada_desde": "2026-09-01T10:00:00+00:00",
        "ja_ouviram": False,
        "tem_avaliacao": False,
        "tem_changespec": False,
        "motivo_da_saida": "",
        "avaliacao": None,
    }
    base.update(campos)
    return base


def a_caixa_responde(ideias, **topo):
    corpo = {
        "quadro": "Meshcraft",
        "pode_assinar": True,
        "pessoas_esperando": 0,
        "silencio_medio_em_dias": None,
        "pessoas_em_silencio_demais": 0,
        "ideias": ideias,
    }
    corpo.update(topo)
    respx.get(IDEIAS).mock(return_value=httpx.Response(200, json=corpo))


RE_ESTILO = re.compile("<style\\b[^>]*>.*?</style\\s*>", re.DOTALL | re.IGNORECASE)


def texto(resposta) -> str:
    """A página SEM a folha de estilo embutida (o irmão explica por quê)."""
    return RE_ESTILO.sub("", resposta.content.decode())


def _exportar(cliente):
    return cliente.get(reverse("caixa_exportar"))


# ---------------------------------------------------------------------------
# 1. O que sai, e o que NÃO sai
# ---------------------------------------------------------------------------


@respx.mock
def test_o_texto_traz_o_que_o_aluno_escreveu_por_inteiro():
    """Problema e solução proposta, sem resumo. Resumir é decidir por quem lê."""
    cliente = _dentro()
    a_caixa_responde([ideia()])

    pagina = texto(_exportar(cliente))

    assert "Modelo bonito no Blender e o Roblox recusa por contagem de faces." in pagina
    assert "Uma aula curta so de reduzir malha sem perder o formato." in pagina
    assert "Aula de retopologia para quem trava no high poly" in pagina


@respx.mock
def test_o_nome_de_quem_escreveu_nunca_sai_na_exportacao():
    """A decisão de privacidade da tela, e a única invisível a olho nu.

    O texto foi feito para SAIR da área administrativa: o próximo lugar onde ele
    vive é uma conversa com uma IA, um documento, um e-mail. A análise funciona
    sem o nome; então o nome não viaja. A Caixa MANDA o autor na resposta (o
    dublê acima prova isso) — quem o descarta é esta tela.
    """
    cliente = _dentro()
    a_caixa_responde([ideia()])

    assert AUTOR not in texto(_exportar(cliente))


@respx.mock
def test_o_cabecalho_diz_o_que_nao_veio_junto():
    """Quem receber este texto não tem como adivinhar o que falta nele."""
    cliente = _dentro()
    a_caixa_responde([ideia()])

    pagina = texto(_exportar(cliente))

    assert "O que não está neste texto" in pagina
    assert "Quem escreveu cada ideia" in pagina
    assert "texto dos comentários" in pagina
    assert "arquivadas" in pagina


@respx.mock
def test_a_contagem_de_comentarios_sai_mesmo_sem_o_texto_deles():
    """Saber que uma ideia tem 3 comentários é sinal, e é o que a Caixa promete."""
    cliente = _dentro()
    a_caixa_responde([ideia(comentarios=3)])

    assert "3 comentários" in texto(_exportar(cliente))


# ---------------------------------------------------------------------------
# 2. A ordem, as etapas e o vazio
# ---------------------------------------------------------------------------


@respx.mock
def test_a_ordem_e_a_mais_votada_primeiro_e_o_texto_diz_isso():
    """Ordem silenciosa em texto que vai para análise é opinião disfarçada de dado."""
    cliente = _dentro()
    a_caixa_responde(
        [
            ideia(id=1, titulo="Ideia pouco votada", votos=2, pessoas=2),
            ideia(id=2, titulo="Ideia muito votada", votos=40, pessoas=30),
        ]
    )

    pagina = texto(_exportar(cliente))

    assert pagina.index("Ideia muito votada") < pagina.index("Ideia pouco votada")
    assert "da mais votada para a menos votada" in pagina


@respx.mock
def test_a_etapa_sai_em_portugues_e_nunca_com_o_nome_do_campo():
    """Quem lê nunca viu a palavra em_analise em lugar nenhum."""
    cliente = _dentro()
    a_caixa_responde([ideia(status="em_analise", tem_avaliacao=False)])

    pagina = texto(_exportar(cliente))

    assert "Etapa: Chegando" in pagina
    assert "em_analise" not in pagina


@respx.mock
def test_a_recusada_sai_com_o_motivo_que_a_pessoa_recebeu():
    """Uma ideia recusada ensina tanto quanto uma aceita, mas só com o porquê."""
    cliente = _dentro()
    a_caixa_responde(
        [
            ideia(
                status="nao_planejado",
                motivo_da_saida="Ja existe na aula 4, com outro nome.",
            )
        ]
    )

    pagina = texto(_exportar(cliente))

    assert "Etapa: Recusada" in pagina
    assert "Ja existe na aula 4, com outro nome." in pagina


@respx.mock
def test_quadro_vazio_diz_em_letras_que_esta_vazio():
    """Texto mudo se leria como erro de cópia. O vazio precisa ser afirmado."""
    cliente = _dentro()
    a_caixa_responde([])

    pagina = texto(_exportar(cliente))

    assert "VAZIO" in pagina
    assert "nenhum aluno escreveu nada" in pagina.lower()


@respx.mock
def test_data_torta_nao_derruba_a_exportacao_inteira():
    """Uma data fora do formato não pode custar as outras 39 ideias."""
    cliente = _dentro()
    a_caixa_responde([ideia(criada_em="ontem de manha")])

    resposta = _exportar(cliente)

    assert resposta.status_code == 200
    assert "data desconhecida" in texto(resposta)


# ---------------------------------------------------------------------------
# 3. A avaliação da equipe
# ---------------------------------------------------------------------------


@respx.mock
def test_a_avaliacao_da_equipe_entra_quando_existe():
    cliente = _dentro()
    a_caixa_responde(
        [
            ideia(
                tem_avaliacao=True,
                avaliacao={
                    "impacto_educacional": 5,
                    "impacto_comercial": 2,
                    "esforco_tecnico": 3,
                    "decisao_produto": "Entra no lote de setembro.",
                },
            )
        ]
    )

    pagina = texto(_exportar(cliente))

    assert "ajuda o aluno a aprender: 5 de 5" in pagina
    assert "ajuda a escola a vender: 2 de 5" in pagina
    assert "trabalho que dá: 3 de 5" in pagina
    assert "Entra no lote de setembro." in pagina


@respx.mock
def test_sem_avaliacao_o_texto_afirma_que_ninguem_escreveu():
    """Silêncio no lugar da nota se leria como nota zero."""
    cliente = _dentro()
    a_caixa_responde([ideia(avaliacao=None)])

    assert "ninguém escreveu nada ainda" in texto(_exportar(cliente))


# ---------------------------------------------------------------------------
# 4. A tela: sem script, e sem confiar no texto de quem vem de fora
# ---------------------------------------------------------------------------


@respx.mock
def test_a_tela_nao_carrega_javascript_nenhum():
    """A porta manda script-src self e esta célula não serve estático.

    O guarda existe para a próxima pessoa que pensar em um botão de copiar: ela
    vai descobrir a política aqui, com um teste vermelho, e não em produção com
    um botão que não faz nada.
    """
    cliente = _dentro()
    a_caixa_responde([ideia()])

    assert "<script" not in texto(_exportar(cliente)).lower()


@respx.mock
def test_texto_de_aluno_nao_vira_marcacao_na_pagina():
    """Quem escreve a ideia é de fora, e o campo de texto tem um jeito de fechar."""
    cliente = _dentro()
    a_caixa_responde([ideia(titulo="fecha </textarea><script>alerta()</script>")])

    corpo = _exportar(cliente).content.decode()

    assert "</textarea><script>" not in corpo
    assert "&lt;/textarea&gt;" in corpo


@respx.mock
def test_a_aba_exportar_aparece_na_faixa_e_se_marca_na_propria_tela():
    cliente = _dentro()
    a_caixa_responde([ideia()])

    na_mesa = texto(cliente.get(reverse("caixa")))
    assert reverse("caixa_exportar") in na_mesa

    na_tela = texto(_exportar(cliente))
    assert 'aria-current="page"' in na_tela
