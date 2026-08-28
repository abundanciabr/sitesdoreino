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

4. **A tela não pode declarar inexistente o que está no contrato congelado.**
   Acrescentado em 28/08/2026 depois de a primeira versão desta tela afirmar
   que a fila de espera "não existe em lugar nenhum do sistema" — e ela existia
   desde a véspera, com porta que o contrato da `alunos` chama de *"a porta do
   painel administrativo"*. A causa foi ler um clone da `main` 75 merges
   atrasado; os três guardas acima não podiam pegar isso, porque todos mediam
   o que a tela DIZ e nenhum media o que o contrato TEM. Os três testes do fim
   deste arquivo medem.

A rede é dublada com `respx`, como nos irmãos desta pasta: além de isolar, é
isso que prova que as páginas novas não saem para a rede por conta própria —
`respx.mock` sem rota registrada estoura em qualquer chamada inesperada.
"""

from pathlib import Path

import httpx
import pytest
import respx
from django.template.loader import render_to_string
from django.test import Client
from django.urls import get_script_prefix, reverse, set_script_prefix

from apps.core.views import TIPOS_DE_ALUNO, FonteAusente, tipos_com_contagem

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
            "esperando": None,
            "nao_consigo_perguntar": True,
            "mostrar_escola": False,
        },
    )


def _um_tipo(quantidade):
    """Um tipo já CONTADO — a forma que `tipos_com_contagem()` devolve.

    O catálogo do módulo não tem `quantidade`; ela é acrescentada por
    requisição. Este ajudante monta a forma que chega ao template.
    """
    return [
        {
            "slug": "teste",
            "nome": "Tipo de mentira",
            "quem": "Quem cai neste tipo.",
            "quantidade": quantidade,
            "fonte": None,
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


def test_o_catalogo_do_modulo_nao_guarda_contagem():
    """Contagem é de REQUISIÇÃO, e guardá-la no módulo seria vazamento entre pessoas.

    `TIPOS_DE_ALUNO` é um dicionário de módulo: escrever um número nele numa
    requisição faria esse número aparecer na tela da requisição seguinte, de
    outra pessoa. O teste trava a ausência do campo — que é o que impede
    alguém de "otimizar" a contagem para dentro do catálogo.
    """
    for tipo in TIPOS_DE_ALUNO:
        assert "quantidade" not in tipo, tipo["slug"]


def test_a_contagem_distingue_nao_sei_de_nenhum():
    """`None` e `[]` produzem números diferentes — é o invariante da tela.

    Medido na função, e não só na tela: `len([])` é zero, e zero é um FATO
    ("perguntei, não há ninguém"); `None` é "não consegui perguntar" e não
    pode virar número nenhum.
    """
    por_slug = {
        t["slug"]: t
        for t in tipos_com_contagem({"aguardando-aprovacao": 0, "recusados": None})
    }
    assert por_slug["aguardando-aprovacao"]["quantidade"] == 0
    assert por_slug["recusados"]["quantidade"] is None
    # Tipo que nem aparece no dicionário nasce sem número — honesto por
    # omissão, em vez de nascer mostrando zero.
    assert por_slug["ativos"]["quantidade"] is None


def test_a_contagem_vem_do_dicionario_que_a_view_monta():
    contagens = {"aguardando-aprovacao": 3, "recusados": 1, "ativos": 7}
    por_slug = {t["slug"]: t for t in tipos_com_contagem(contagens)}
    assert por_slug["aguardando-aprovacao"]["quantidade"] == 3
    assert por_slug["recusados"]["quantidade"] == 1
    assert por_slug["ativos"]["quantidade"] == 7


def test_todo_tipo_declara_por_que_o_numero_falta():
    """A lição do §4.6b do plano: seção não promete dado que não existe.

    Lá, uma seção nasceu prometendo "visitas" porque alguém supôs que o dado
    estava em algum lugar — e não estava. Aqui cada tipo diz qual dos dois
    casos ele é, e o valor tem de ser um dos DOIS conhecidos: um terceiro
    valor inventado deixaria a tela sem a frase correspondente, em silêncio.
    """
    validos = {FonteAusente.PORTA_PRONTA, FonteAusente.SEM_OPERACAO}
    campos = {"slug", "nome", "quem", "fonte", "fonte_ausente", "falta"}
    for tipo in TIPOS_DE_ALUNO:
        assert set(tipo) == campos, tipo["slug"]
        assert tipo["fonte_ausente"] in validos, tipo["slug"]
        assert tipo["falta"].strip(), tipo["slug"]


CONTRATO_DA_ALUNOS = (
    Path(__file__).resolve().parents[3] / "contracts" / "alunos.openapi.yaml"
)


def test_o_contrato_da_alunos_esta_onde_este_arquivo_pensa():
    """Sem isto, os dois testes abaixo passariam lendo string vazia.

    *Ausência de evidência nunca é evidência de sucesso* ([INV-CI01]): um
    guarda que mede um arquivo que não existe devolve verde por nada.
    """
    assert CONTRATO_DA_ALUNOS.is_file(), CONTRATO_DA_ALUNOS
    assert "openapi:" in CONTRATO_DA_ALUNOS.read_text(encoding="utf-8")


def test_toda_porta_declarada_existe_mesmo_no_contrato_congelado():
    """`fonte` não pode nomear operação que a `alunos` não tem.

    A conferência é por TEXTO, e não por `yaml.safe_load`, de propósito: ler
    YAML aqui custaria uma dependência nova à célula só para este guarda, e o
    que precisa ser verdade é grosseiro — o caminho e o status aparecem, ou
    não aparecem, no contrato congelado.
    """
    contrato = CONTRATO_DA_ALUNOS.read_text(encoding="utf-8")
    declaradas = [t for t in TIPOS_DE_ALUNO if t["fonte"]]
    assert declaradas, "nenhum tipo declara fonte — o guarda abaixo mediria nada"
    for tipo in declaradas:
        caminho = tipo["fonte"].split()[1].split("?")[0]
        assert caminho in contrato, f"{tipo['slug']}: {caminho} não está no contrato"
        if "status=" in tipo["fonte"]:
            status = tipo["fonte"].split("status=")[1]
            assert status in contrato, f"{tipo['slug']}: status {status} não existe"


def test_a_fila_que_o_contrato_tem_nao_pode_ficar_sem_dono_nesta_tela():
    """O guarda do erro REAL de 28/08/2026, na direção em que ele aconteceu.

    A primeira versão desta tela declarou que a fila de espera "não existe em
    lugar nenhum do sistema" — e ela existia desde 27/08, com porta que o
    próprio contrato chama de *"a porta do painel administrativo"*. O erro veio
    de ler um clone da `main` 75 merges atrasado, e nenhum teste desta suíte
    poderia tê-lo pego: todos mediam o que a tela DIZ, nenhum media o que o
    contrato TEM.

    Este mede. Se a `alunos` sabe listar um estado de aluno, algum tipo desta
    tela tem de apontar para essa porta — nem que seja para dizer que ainda
    não a abrimos. Declarar inexistente o que está no contrato congelado passa
    a ser vermelho.
    """
    contrato = CONTRATO_DA_ALUNOS.read_text(encoding="utf-8")
    if "/pre-matriculas" not in contrato:  # pragma: no cover - a fila saiu?
        pytest.skip("o contrato não tem mais a fila; este guarda perdeu o objeto")
    fontes = " ".join(t["fonte"] or "" for t in TIPOS_DE_ALUNO)
    assert "/pre-matriculas" in fontes, (
        "o contrato da `alunos` lista a fila de liberação, mas nenhum tipo "
        "desta tela aponta para ela. Foi exatamente o erro de 28/08/2026."
    )


@respx.mock
def test_a_tela_nao_diz_que_a_fila_nao_existe():
    """O texto errado, travado pela frase — porque foi a frase que enganou.

    O mantenedor leu esta tela e teria concluído que precisava decidir de novo
    algo que ele já decidiu em 27/08 (`DECISAO-fila-de-liberacao.md`). Custo de
    um texto errado numa área de operação: uma decisão retomada do zero.
    """
    html = _texto(_dentro().get("/escola/alunos/"))
    assert "não existe fila de espera" not in html
    # Sem o par de tokens (o estado desta suíte), a tela diz que não CONSEGUE
    # perguntar — nunca que a fila não existe. As duas frases se parecem para
    # quem lê rápido e são opostas para quem decide o que fazer.
    assert "Ainda não consigo perguntar" in html
    assert "A fila existe e está recebendo gente" in html


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


# ---------------------------------------------------- 5. a fila, com dado real
#
# Acrescentado em 28/08/2026, quando a tela deixou de listar o que falta e
# passou a PERGUNTAR (`DECISAO-categorias-de-usuario`, fase 2 da lei da fila).
#
# O par de tokens `admin→alunos` é ligado por
# `infra/provisionar-pares-de-categorias.sh`, na VPS. Enquanto ele não roda, as
# variáveis não existem — e é por isso que TODOS os testes acima continuam
# valendo sem tocar em rede nenhuma: `_configuracao()` devolve `None` e a
# célula nem tenta sair.

ALUNOS = "http://alunos:8000/api/alunos"
FILA = f"{ALUNOS}/pre-matriculas"


@pytest.fixture
def par_com_a_alunos(monkeypatch):
    monkeypatch.setenv("ALUNOS_API_URL", ALUNOS)
    monkeypatch.setenv("ALUNOS_API_TOKEN", "token-do-par-admin-alunos")


def _pessoa_na_fila(**campos) -> dict:
    corpo = {
        "id": "1",
        "site_id": "escola-a",
        "email": "quem-espera@exemplo.com",
        "nome_completo": "Quem Espera",
        "whatsapp": "(96) 99999-0000",
        "comprou_em": None,
        "turma": None,
        "status": "aguardando",
        "criada_em": "2026-08-21T10:00:00Z",
        "esperando_ha_dias": 7,
        "motivo_recusa": None,
    }
    corpo.update(campos)
    return corpo


ALUNOS_LISTA = f"{ALUNOS}/matriculas"


def _fila_responde(aguardando=None, recusada=None, alunos=None):
    """As TRÊS perguntas que a tela faz — a fila, os recusados e os alunos.

    Desde a gestão de alunos (28/08/2026) a página consulta as três, e
    `respx.mock` sem rota registrada estoura em qualquer chamada inesperada. É
    justamente o que se quer dele: nenhuma ida à rede desta célula passa sem
    alguém ter dito o que ela responde.
    """
    respx.get(FILA, params={"status": "aguardando"}).mock(
        return_value=httpx.Response(
            200, json=aguardando if aguardando is not None else []
        )
    )
    respx.get(FILA, params={"status": "recusada"}).mock(
        return_value=httpx.Response(200, json=recusada if recusada is not None else [])
    )
    respx.get(ALUNOS_LISTA).mock(
        return_value=httpx.Response(200, json=alunos if alunos is not None else [])
    )


@respx.mock
def test_a_fila_com_gente_mostra_nome_email_whatsapp_e_dias(par_com_a_alunos):
    _fila_responde(aguardando=[_pessoa_na_fila()])
    html = _texto(_dentro().get("/escola/alunos/"))
    assert "Quem Espera" in html
    assert "quem-espera@exemplo.com" in html
    assert "(96) 99999-0000" in html
    assert "Espera há 7 dias" in html


@respx.mock
def test_esta_e_a_unica_tela_que_mostra_o_whatsapp_e_ela_mostra(par_com_a_alunos):
    """A §5 da lei da fila tem duas metades, e esta é a que costuma faltar.

    A metade guardada por outros testes é "o telefone NÃO sai por mais
    nenhuma porta". Esta é a outra: ele TEM de sair por esta, senão o
    mantenedor não consegue conferir quem é a pessoa antes de liberar — e a
    lei inteira perde o objeto.
    """
    _fila_responde(aguardando=[_pessoa_na_fila(whatsapp="(11) 91234-5678")])
    assert "(11) 91234-5678" in _texto(_dentro().get("/escola/alunos/"))


@respx.mock
def test_fila_vazia_medida_mostra_zero_e_nao_traco(par_com_a_alunos):
    """O zero LEGÍTIMO nasce aqui — e agora ele existe de verdade.

    Até esta mudança nenhum tipo tinha número, e o `—` cobria tudo. Com a
    pergunta feita, "perguntei e não há ninguém" é um fato, e mostrá-lo como
    traço seria esconder uma resposta boa.
    """
    _fila_responde(aguardando=[], recusada=[], alunos=[])
    html = _texto(_dentro().get("/escola/alunos/"))
    assert "Ninguém está esperando agora" in html
    assert 'class="valor">0<' in html
    # E, desde a gestão de alunos (28/08/2026), NENHUM traço sobra quando as
    # três perguntas são respondidas: todo tipo desta tela passou a ter porta.
    # A tela deixou de ter um canto que ela não sabe medir — e é este teste que
    # impede alguém de acrescentar um tipo sem fonte sem perceber.
    assert 'class="valor vazio">&mdash;<' not in html


@respx.mock
@pytest.mark.parametrize(
    "resposta,motivo",
    [
        (httpx.Response(401), "o par não está em TOKENS_ACEITOS_ADMIN"),
        (httpx.Response(500), "a alunos quebrou"),
        (httpx.Response(200, text="<html>proxy</html>"), "corpo que não é JSON"),
        (httpx.Response(200, json={"detail": "oi"}), "corpo que não é lista"),
    ],
)
def test_a_alunos_respondendo_mal_nao_derruba_a_pagina(
    par_com_a_alunos, resposta, motivo
):
    """Fail-OPEN por tile: a página abre, o número some, e a tela DIZ por quê.

    É o inverso deliberado da porta desta mesma célula (`clients.py` explica):
    lá a dúvida fecha, porque decide acesso; aqui a dúvida não pode derrubar a
    ferramenta que o mantenedor abre justamente quando algo está errado.
    """
    respx.get(FILA).mock(return_value=resposta)
    respx.get(ALUNOS_LISTA).mock(return_value=resposta)
    r = _dentro().get("/escola/alunos/")
    assert r.status_code == 200, f"{motivo}: {r.content}"
    html = _texto(r)
    assert "Ainda não consigo perguntar" in html
    assert 'class="valor">0<' not in html, f"{motivo}: virou zero, que é mentira"


@respx.mock
def test_a_alunos_fora_do_ar_nao_derruba_a_pagina(par_com_a_alunos):
    respx.get(FILA).mock(side_effect=httpx.ConnectError("recusou"))
    respx.get(ALUNOS_LISTA).mock(side_effect=httpx.ConnectError("recusou"))
    r = _dentro().get("/escola/alunos/")
    assert r.status_code == 200, r.content
    assert "Ainda não consigo perguntar" in _texto(r)


@respx.mock
def test_com_uma_escola_so_o_codigo_interno_dela_nao_aparece(par_com_a_alunos):
    """Identificador opaco numa tela de leigo é ruído, e ruído esconde sinal."""
    _fila_responde(aguardando=[_pessoa_na_fila(site_id="escola-a")])
    assert "escola-a" not in _texto(_dentro().get("/escola/alunos/"))


@respx.mock
def test_com_duas_escolas_cada_linha_diz_de_qual_veio(par_com_a_alunos):
    _fila_responde(
        aguardando=[
            _pessoa_na_fila(id="1", site_id="escola-a", email="a@exemplo.com"),
            _pessoa_na_fila(id="2", site_id="escola-b", email="b@exemplo.com"),
        ]
    )
    html = _texto(_dentro().get("/escola/alunos/"))
    assert "escola-a" in html and "escola-b" in html


@respx.mock
def test_a_segunda_escola_aparece_mesmo_vindo_so_das_recusadas(par_com_a_alunos):
    """A conta das escolas olha TODAS as filas, não só a que está na tela.

    Sem isto, uma escola cuja única presença é uma recusa deixaria a coluna
    escondida — e a lista de espera diria "escola" nenhuma justamente no dia
    em que passou a haver duas.
    """
    _fila_responde(
        aguardando=[_pessoa_na_fila(site_id="escola-a")],
        recusada=[_pessoa_na_fila(id="9", site_id="escola-b", status="recusada")],
    )
    assert "escola-a" in _texto(_dentro().get("/escola/alunos/"))


def test_sem_o_par_de_tokens_a_celula_nem_tenta_sair_para_a_rede():
    """O estado de HOJE, e ele é o caminho normal — não uma falha.

    `respx.mock` sem rota registrada estoura em qualquer chamada inesperada;
    este teste roda SEM ele de propósito, e o que prova é o outro lado: com o
    env vazio, `_configuracao()` devolve `None` antes de qualquer rede.
    """
    from apps.core.clients import AlunosClient

    assert AlunosClient()._configuracao() is None
    assert AlunosClient().fila("aguardando") is None


def test_o_orcamento_de_tempo_da_fila_e_explicito():
    """Célula fora do ar e célula que PENDURA são falhas diferentes.

    Sem orçamento, a segunda vira a página do mantenedor travando — e ele não
    tem como saber que o problema é de outra peça.
    """
    from apps.core.clients import AlunosClient

    assert AlunosClient.TIMEOUT == 2.0
