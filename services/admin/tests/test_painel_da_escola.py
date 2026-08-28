"""Teste-guarda: os DOIS painéis da área, e a tela de alunos da escola.

Três coisas diferentes são travadas aqui, e nenhuma delas seria pega por um
teste que só perguntasse "a página abriu?":

1. **Os dois painéis têm nomes distintos, e o do sistema não se chama mais
   "painel da escola".** Foi um defeito de VERDADE, relatado pelo mantenedor em
   28/08/2026: o único link da visão geral levava ao livro de ocorrências da
   construção da plataforma, mas se anunciava como painel da escola. Ele
   clicava esperando alunos e via merges. Um teste de status nunca veria isso —
   a página abria perfeitamente, dizendo a coisa errada.

2. **As duas rotas novas nascem ATRÁS da porta.** `CAMINHOS_ISENTOS` é uma
   igualdade exata (`test_inv_porta_fail_closed.py`), mas ela prova que
   ninguém acrescentou isenção — não prova que a rota nova responde a alguém.
   Aqui a medição é de fora: sem sessão, 302; com sessão fora da lista, 404.

3. **"Não sei quantos" e "não há nenhum" são telas diferentes.** É o
   invariante desta página. Um `0` no lugar do traço diria ao mantenedor que
   ninguém está esperando aprovação, quando a verdade é que ninguém está
   contando — falso-verde clássico (`RETROSPECTIVA-FASE-D.md` §1). O guarda
   abaixo não se contenta em ver o traço: ele renderiza a MESMA página com
   `quantidade: 0` e exige que a tela mude.

A rede é dublada com `respx`, como nos irmãos desta pasta: além de isolar, é
isso que prova que as páginas novas não saem para a rede por conta própria —
`respx.mock` sem rota registrada estoura em qualquer chamada inesperada.
"""

import httpx
import pytest
import respx
from django.template.loader import render_to_string
from django.test import Client
from django.urls import get_script_prefix, reverse, set_script_prefix

from apps.core.views import TIPOS_DE_ALUNO, FonteAusente

BASE = "http://identidade:8000/interno"
SESSAO = f"{BASE}/sessao/completa"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"


@pytest.fixture(autouse=True)
def env_da_porta(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", BASE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


def _pessoa(email: str = DONO) -> dict:
    return {
        "autenticado": True,
        "id": "id-opaco-123",
        "nome_exibido": "Fulano",
        "papel": None,
        "email": email,
    }


def _dentro(email: str = DONO) -> Client:
    """Um cliente que a porta deixa passar."""
    respx.get(SESSAO).mock(return_value=httpx.Response(200, json=_pessoa(email)))
    c = Client()
    c.defaults["HTTP_COOKIE"] = COOKIE
    return c


def _texto(resposta) -> str:
    return resposta.content.decode()


# ------------------------------------------------------- 1. os dois painéis


@respx.mock
def test_a_visao_geral_oferece_os_dois_paineis_com_nomes_distintos():
    html = _texto(_dentro().get("/"))
    assert "Abrir o painel do sistema" in html
    assert "Abrir o painel da escola" in html


@respx.mock
def test_o_painel_do_sistema_nao_se_chama_mais_painel_da_escola():
    """O defeito relatado, travado pelo DESTINO e não pelo texto solto.

    Não basta que as duas frases existam na página: o que quebrou foi a
    ligação entre elas. Este teste confere que o link chamado "painel do
    sistema" aponta para `painel` e o chamado "painel da escola" aponta para
    `escola` — trocar os dois de lugar deixaria o teste acima verde.
    """
    html = _texto(_dentro().get("/"))
    sistema = html.index("Abrir o painel do sistema")
    escola = html.index("Abrir o painel da escola")
    # O href vem ANTES do rótulo dentro de cada cartão: o pedaço de HTML que
    # antecede cada rótulo é onde o endereço dele tem de estar.
    assert reverse("painel") in html[:sistema]
    assert reverse("escola") in html[sistema:escola]
    assert reverse("escola") not in html[:sistema]


@pytest.fixture
def sob_o_prefixo_publico():
    """O regime de produção: a área inteira mora sob `/admin`.

    Mexe no PREFIXO DE SCRIPT, e não em `settings.FORCE_SCRIPT_NAME` — é a
    `armadilhas/081` inteira, e ela mordeu de novo aqui: `reverse()` não lê a
    variável, lê um prefixo de THREAD que o SERVIDOR preenche
    (`ASGIHandler.__call__` chama `set_script_prefix()`); os handlers de teste
    do Django não chamam. Ajustar só `FORCE_SCRIPT_NAME` deixa este teste
    verde sem medir nada — foi exatamente o que a primeira versão dele fez.

    O `finally` também é da armadilha: o prefixo é de thread e vaza para os
    testes seguintes, fazendo o próximo vermelho aparecer num arquivo sem
    relação nenhuma. Aqui ele RESTAURA o anterior em vez de chamar
    `clear_script_prefix()` — mesmo efeito hoje (o padrão é `/`) e à prova de
    uma fixture futura que já tenha um prefixo de pé.
    """
    anterior = get_script_prefix()
    set_script_prefix("/admin/")
    try:
        yield
    finally:
        set_script_prefix(anterior)


@respx.mock
def test_os_enderecos_carregam_o_prefixo_publico(sob_o_prefixo_publico):
    """`{% url %}` e nunca caminho cravado à mão (`armadilhas/081`).

    Sem prefixo o defeito é invisível: `/escola/` funciona nos testes e dá 404
    em produção, onde a área inteira mora sob `/admin`. Um `href="/escola/"`
    escrito à mão passa em tudo o que este arquivo mede — menos aqui.
    """
    html = _texto(_dentro().get("/"))
    assert 'href="/admin/escola/"' in html
    assert 'href="/admin/painel/"' in html

    html_escola = _texto(_dentro().get("/escola/"))
    assert 'href="/admin/escola/alunos/"' in html_escola


# ------------------------------------------------------- 2. atrás da porta


@pytest.mark.parametrize("caminho", ["/escola/", "/escola/alunos/"])
def test_rota_nova_sem_sessao_vai_para_o_login(caminho):
    r = Client().get(caminho)
    assert r.status_code == 302
    assert r["Location"].startswith("/entrar/google?next=")


@respx.mock
@pytest.mark.parametrize("caminho", ["/escola/", "/escola/alunos/"])
def test_rota_nova_fora_da_lista_recebe_404(caminho):
    """Para quem não é da casa, a escola não existe — como o resto da área."""
    assert _dentro("estranho@exemplo.com").get(caminho).status_code == 404


# ------------------------------------------------------------- a navegação


@respx.mock
def test_a_escola_abre_e_leva_aos_alunos():
    r = _dentro().get("/escola/")
    assert r.status_code == 200, r.content
    html = _texto(r)
    assert "Painel da escola" in html
    assert reverse("escola_alunos") in html


@respx.mock
def test_os_alunos_abrem_e_voltam_para_a_escola():
    r = _dentro().get("/escola/alunos/")
    assert r.status_code == 200, r.content
    assert reverse("escola") in _texto(r)


@respx.mock
def test_a_pagina_de_alunos_mostra_todos_os_tipos():
    html = _texto(_dentro().get("/escola/alunos/"))
    for tipo in TIPOS_DE_ALUNO:
        assert tipo["nome"] in html, tipo["slug"]


def test_aguardando_aprovacao_e_o_primeiro_tipo():
    """A ordem é produto, não estética: foi o tipo que o mantenedor pediu.

    "os alunos que se cadastraram no site e que estão esperando serem
    aprovados" — pedido de 28/08/2026. Ele é o motivo de a tela existir, e
    quem reordenar a tupla precisa passar por aqui.
    """
    assert TIPOS_DE_ALUNO[0]["slug"] == "aguardando-aprovacao"


# ------------------------------------- 3. "não sei" nunca vira "não há nenhum"


def _renderiza(tipos) -> str:
    return render_to_string(
        "admin/escola_alunos.html",
        {
            "admin": {"nome": "Fulano", "email": DONO, "id": "x"},
            "tipos": tipos,
            "SEM_DADO": FonteAusente.SEM_DADO,
        },
    )


def _um_tipo(quantidade):
    return [
        {
            "slug": "teste",
            "nome": "Tipo de mentira",
            "quem": "Quem cai neste tipo.",
            "quantidade": quantidade,
            "fonte_ausente": FonteAusente.SEM_OPERACAO,
            "falta": "O motivo de faltar.",
        }
    ]


# A CASA do número na tela — o `<div>` que mostra o valor de um tipo. As
# asserções miram nela, e não na página inteira: o texto que explica ao
# mantenedor por que não há números CITA um "0" de propósito, e um `">0<" in
# html` estaria medindo a explicação em vez do valor.
CASA_DO_NUMERO = 'class="valor">'
CASA_VAZIA = 'class="valor vazio">&mdash;<'


def test_quantidade_desconhecida_vira_traco_e_nunca_zero():
    html = _renderiza(_um_tipo(None))
    assert CASA_VAZIA in html
    assert "Ainda não dá para contar." in html
    assert CASA_DO_NUMERO + "0<" not in html


def test_o_guarda_morde_zero_de_verdade_muda_a_tela():
    """A prova de que o teste acima mede alguma coisa.

    `{% if tipo.quantidade %}` — o jeito natural de escrever — trataria `0`
    como ausência, e ESTE teste ficaria vermelho: um zero legítimo apareceria
    como traço, e a tela mentiria para o outro lado. É por isso que o template
    usa `is None`.
    """
    html = _renderiza(_um_tipo(0))
    assert CASA_DO_NUMERO + "0<" in html
    assert CASA_VAZIA not in html
    assert "Ainda não dá para contar." not in html


def test_hoje_nenhum_tipo_tem_numero_e_isso_e_declarado():
    """Enquanto não houver de onde ler, `None` — nunca um número plantado."""
    quantidades = [t["quantidade"] for t in TIPOS_DE_ALUNO]
    assert quantidades == [None] * len(TIPOS_DE_ALUNO)


def test_todo_tipo_declara_por_que_o_numero_falta():
    """A lição do §4.6b do plano: seção não promete dado que não existe.

    Lá, uma seção nasceu prometendo "visitas" porque alguém supôs que o dado
    estava em algum lugar — e não estava. Aqui cada tipo diz qual dos dois
    casos ele é, e o valor tem de ser um dos DOIS conhecidos: um terceiro
    valor inventado deixaria a tela sem a frase correspondente, em silêncio.
    """
    validos = {FonteAusente.SEM_DADO, FonteAusente.SEM_OPERACAO}
    campos = {"slug", "nome", "quem", "quantidade", "fonte_ausente", "falta"}
    for tipo in TIPOS_DE_ALUNO:
        assert set(tipo) == campos, tipo["slug"]
        assert tipo["fonte_ausente"] in validos, tipo["slug"]
        assert tipo["falta"].strip(), tipo["slug"]


@respx.mock
def test_a_fila_de_aprovacao_diz_que_espera_por_uma_decisao_do_dono():
    """O único tipo SEM_DADO carrega o pedido — e a tela o mostra.

    Sem isto, a página diria "ainda não dá para contar" para os quatro tipos
    igualmente, e o mantenedor não teria como saber que três são trabalho de
    robô e um é decisão dele.
    """
    sem_dado = [
        t["slug"] for t in TIPOS_DE_ALUNO if t["fonte_ausente"] == FonteAusente.SEM_DADO
    ]
    assert sem_dado == ["aguardando-aprovacao"]
    html = _texto(_dentro().get("/escola/alunos/"))
    assert "Precisa de você" in html


# ------------------------------------------------------ higiene das telas novas


@respx.mock
@pytest.mark.parametrize("caminho", ["/", "/escola/", "/escola/alunos/"])
def test_nenhuma_marca_de_template_vaza_nas_telas(caminho):
    """Irmão de `test_nenhum_comentario_vaza_para_a_tela.py`, pelo resultado.

    Lá a varredura é do ARQUIVO, e cobre toda a célula; aqui é do que o
    navegador recebe nas três telas ligadas por esta mudança. `armadilhas/087`
    já pôs um bloco de comentário na cara do mantenedor uma vez.
    """
    html = _texto(_dentro().get(caminho))
    assert "{#" not in html
    assert "{%" not in html
