# tests/test_inv_avaliacao_interna_fora_do_alcance.py  # [RECEITA:R5 v1]
"""INV-SUG03 — `AvaliacaoInterna` nunca é lida nem escrita por rota de aluno.

Spec §8, e a Definição de Pronto do MVP (§11): *"endpoint de avaliação de
produto retorna 403 para qualquer ator sem role de staff"*. Enquanto esse
endpoint não existe (EVO-13), o invariante tem uma forma mais forte e é ela que
está travada aqui: **nenhuma rota que o aluno alcança encosta na tabela**.

Por que este é o guarda mais importante do despacho: a `AvaliacaoInterna`
guarda a decisão de produto sobre a ideia de uma pessoa — o "não vamos fazer, e
por quê", escrito para a equipe ler. Vazar isso por descuido de campo num
template não é um bug de listagem; é a Caixa contando ao aluno o que a equipe
achou da ideia dele, com as palavras que ninguém escreveu para ele ler.

**Três degraus, do mais forte ao mais legível:**

1. **O SQL.** A jornada inteira do aluno roda com as consultas capturadas, e o
   nome da tabela não pode aparecer em nenhuma delas. É o degrau que pega o
   `select_related` distraído, o `{{ sugestao.avaliacao.notas }}` no template
   (que consulta na hora de renderizar) e qualquer caminho futuro que ninguém
   previu aqui.
2. **O corpo das respostas.** O texto da avaliação é semeado com uma marca
   inconfundível; se ela aparecer em qualquer página do aluno, o guarda cai.
3. **A ÁRVORE SINTÁTICA do módulo do aluno.** `apps/core/participacao.py` não
   pode sequer nomear o model nem o `related_name` — via AST, não via `grep`,
   para que citar o nome num comentário (como este arquivo faz) não conte.

A completude é mecânica: a lista de rotas percorridas é conferida contra o
urlconf. Rota de participação nova que ninguém acrescentar aqui deixa este
guarda VERMELHO — que é exatamente o lembrete que se quer.
"""

import ast
import inspect

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.core import participacao
from apps.sugestoes.models import AvaliacaoInterna

pytestmark = pytest.mark.django_db

MARCA = "DECISAO-INTERNA-QUE-O-ALUNO-NUNCA-PODE-VER"


@pytest.fixture
def avaliacao(sugestao, aluno):
    return AvaliacaoInterna.objects.create(
        sugestao=sugestao,
        impacto_educacional=5,
        impacto_comercial=4,
        esforco_tecnico=2,
        notas=MARCA,
        decisao_produto=MARCA,
        avaliado_por=aluno,
    )


def _rotas_de_participacao() -> set[str]:
    """As rotas que o ALUNO alcança: exigem sessão e NÃO exigem crachá.

    O recorte por `exige_staff` entrou no EVO-13, quando as rotas de moderação
    nasceram — e ele não afrouxa nada, porque as três varreduras do urlconf
    juntas continuam cobrindo o urlconf inteiro, sem sobra:

    * rota sem `exige_sessao` e fora da lista pública ⇒ cai em
      `test_inv_sem_sessao_nada.py::test_toda_rota_nao_publica_carrega_o_porteiro`;
    * rota com `exige_staff` ⇒ cai em `test_inv_so_staff_modera.py`, que a
      percorre com uma sessão de ALUNO e exige 403 em todas;
    * rota com `exige_sessao` e sem `exige_staff` ⇒ é o aluno, e é aqui.

    Sem o recorte, este guarda passaria a exigir que a jornada do aluno
    percorresse as páginas da equipe — que devolvem 403 exatamente porque ele
    não pode entrar nelas. Seria medir o contrário do invariante.
    """
    from config.urls import urlpatterns

    return {
        rota.name
        for rota in urlpatterns
        if getattr(rota.callback, "exige_sessao", False)
        and not getattr(rota.callback, "exige_staff", False)
    }


def _jornada_completa(cliente, sugestao, aviso) -> dict[str, list]:
    """Todo endereço que um aluno com sessão alcança, uma vez cada.

    As duas rotas do sininho (EVO-21) entraram aqui pelo mecanismo, não por
    lembrança: elas exigem sessão e não exigem crachá, então
    `_rotas_de_participacao()` passou a listá-las e
    `test_a_jornada_cobre_TODAS_as_rotas_de_participacao` ficou vermelho até
    serem percorridas. É exatamente o lembrete que este guarda existe para dar.
    """
    quadro = reverse("quadro")
    nova = reverse("nova_sugestao")
    base = {
        "titulo": "Um tema qualquer",
        "problema": "Doi assim.",
        "categoria": "curso",
    }
    return {
        # As TRÊS abas, e não só a padrão: "Em alta" (V1.2) monta um ranking
        # próprio, com uma subconsulta que as outras não têm — medir só o
        # caminho de sempre deixaria o SQL da aba nova fora do degrau 1. O
        # painel "Meu impacto", que estreou no mesmo despacho, vive dentro desta
        # mesma página e entra em cada linha desta lista de graça.
        "quadro": [
            cliente.get(quadro),
            cliente.get(f"{quadro}?categoria=curso"),
            cliente.get(f"{quadro}?ordem=em-alta"),
        ],
        "nova_sugestao": [
            cliente.get(nova),
            cliente.post(nova, {**base, "conferir": "1"}),
            cliente.post(nova, {**base, "publicar": "1"}),
        ],
        "sugestao": [cliente.get(reverse("sugestao", args=[sugestao.id]))],
        "votar": [cliente.post(reverse("votar", args=[sugestao.id]))],
        "desvotar": [cliente.post(reverse("desvotar", args=[sugestao.id]))],
        "comentar": [
            cliente.post(reverse("comentar", args=[sugestao.id]), {"texto": "isso!"})
        ],
        "avisos": [cliente.get(reverse("avisos"))],
        "marcar_aviso_lido": [
            cliente.post(reverse("marcar_aviso_lido", args=[aviso.id]))
        ],
    }


def test_nenhuma_consulta_do_aluno_toca_a_tabela_da_avaliacao(
    dentro, sugestao, avaliacao, aviso
):
    tabela = AvaliacaoInterna._meta.db_table

    with CaptureQueriesContext(connection) as consultas:
        respostas = _jornada_completa(dentro.client, sugestao, aviso)

    achatadas = [r for lista in respostas.values() for r in lista]
    assert all(r.status_code in (200, 302) for r in achatadas), [
        r.status_code for r in achatadas
    ]

    culpadas = [c["sql"] for c in consultas.captured_queries if tabela in c["sql"]]
    assert culpadas == [], (
        f"a jornada do aluno consultou {tabela}: {culpadas[:3]}. "
        "A avaliação interna é da equipe (spec §8)."
    )


def test_nenhuma_pagina_do_aluno_mostra_o_texto_da_avaliacao(
    dentro, sugestao, avaliacao, aviso
):
    respostas = _jornada_completa(dentro.client, sugestao, aviso)

    for nome, lista in respostas.items():
        for resposta in lista:
            if resposta.status_code != 200:
                continue
            assert (
                MARCA not in resposta.content.decode()
            ), f"a rota '{nome}' devolveu o texto da avaliação interna."


def test_a_jornada_cobre_TODAS_as_rotas_de_participacao(dentro, sugestao, aviso):
    """Sem isto, rota nova nasceria fora do guarda e ninguém perceberia."""
    percorridas = set(_jornada_completa(dentro.client, sugestao, aviso))

    assert percorridas == _rotas_de_participacao(), (
        "a jornada deste guarda não cobre as mesmas rotas do urlconf: "
        f"faltando {_rotas_de_participacao() - percorridas}, "
        f"sobrando {percorridas - _rotas_de_participacao()}"
    )


def test_a_jornada_do_aluno_nao_escreve_na_avaliacao(
    dentro, sugestao, avaliacao, aviso
):
    antes = (
        avaliacao.notas,
        avaliacao.decisao_produto,
        AvaliacaoInterna.objects.count(),
    )

    _jornada_completa(dentro.client, sugestao, aviso)

    avaliacao.refresh_from_db()
    assert (
        avaliacao.notas,
        avaliacao.decisao_produto,
        AvaliacaoInterna.objects.count(),
    ) == antes


def test_o_modulo_do_aluno_nem_nomeia_a_avaliacao_interna():
    """Via AST, não `grep`: comentário e docstring podem citar o nome à vontade.

    O que não pode é o CÓDIGO nomear — nem o model (`AvaliacaoInterna`), nem o
    `related_name` pelo qual se chega nele a partir de uma sugestão
    (`sugestao.avaliacao`).
    """
    arvore = ast.parse(inspect.getsource(participacao))
    nomes = {no.id for no in ast.walk(arvore) if isinstance(no, ast.Name)}
    atributos = {no.attr for no in ast.walk(arvore) if isinstance(no, ast.Attribute)}
    importados = {
        apelido.name
        for no in ast.walk(arvore)
        if isinstance(no, (ast.Import, ast.ImportFrom))
        for apelido in no.names
    }

    assert "AvaliacaoInterna" not in (nomes | atributos | importados)
    assert "avaliacao" not in atributos
