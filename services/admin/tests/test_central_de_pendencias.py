"""Teste-guarda: a Central de Pendências (`/admin/pendencias/`), degrau 1.

Plano: `documentos/pendencias-e-conferencia-por-pares.md`.

O QUE ESTE ARQUIVO EXISTE PARA IMPEDIR, e por que os testes óbvios não
impediriam:

1. **A tela dizendo "nada esperando você" quando a verdade é "não consegui
   perguntar".** É a falha mais cara possível aqui, e a única cujo custo se
   mede em pessoas: nove pessoas esperando aprovação viraria um zero, e o
   mantenedor fecharia a tela em paz. Um teste que só afirmasse `200` ficaria
   verde com a `alunos` fora do ar. Por isso os guardas de baixo derrubam a
   fila de propósito e exigem que a tela MUDE de frase.

2. **A recusa da credencial virando um "não sei" qualquer.** Recarregar a
   página não conserta um 401/403, e quem lê o aviso precisa saber a quem
   pedir. A tela diz a causa e o caminho, e o guarda exige que a frase da
   queda SUMA.

3. **A confissão sumindo.** Este degrau enxerga uma das quatro filas do site.
   Uma portaria que enxerga parte e não avisa ensina o mantenedor a confiar
   num "nada esperando" que ela não pode sustentar.

4. **A rota nascendo fora da porta.** `CAMINHOS_ISENTOS` é igualdade exata e
   já tem guarda próprio, mas ele prova que ninguém acrescentou isenção, não
   que ESTA rota responde a quem não é da casa. Aqui se mede de fora.

A rede é dublada com `respx`, como nos irmãos desta pasta: além de isolar, é
isso que prova que a tela não sai para a rede por conta própria, porque
`respx.mock` sem rota registrada estoura em qualquer chamada inesperada.
"""

from __future__ import annotations

import httpx
import pytest
import respx
from django.test import Client
from django.urls import get_script_prefix, reverse, set_script_prefix

from apps.core import moldura
from apps.core import pendencias as central

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
ALUNOS = "http://alunos:8000/api/alunos"
FILA_DE_ENTRADA = f"{ALUNOS}/pre-matriculas"
PAGES = "http://pages:8000/interno"
GAMIFICACAO = "http://gamificacao:8000/api/gamificacao"
CURSOS = "http://cursos:8000/api/cursos"
RESUMOS = {
    "portfolio": f"{PAGES}/pendencias/escola-a",
    "marcos": f"{GAMIFICACAO}/pendencias/escola-a",
    "checkpoints": f"{CURSOS}/pendencias/escola-a",
}
CAIXA = "http://sugestoes:8000/interno"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"
DE_FORA = "estranho@exemplo.com"
TELA = "/pendencias/"


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    monkeypatch.setenv("ALUNOS_API_URL", ALUNOS)
    monkeypatch.setenv("ALUNOS_API_TOKEN", "token-do-par-admin-alunos")
    monkeypatch.setenv("SUGESTOES_API_URL", CAIXA)
    monkeypatch.setenv("SUGESTOES_API_TOKEN", "token-do-par-admin-sugestoes")
    monkeypatch.setenv("PAGES_API_URL", PAGES)
    monkeypatch.setenv("PAGES_API_TOKEN", "token-do-par-admin-pages")
    monkeypatch.setenv("GAMIFICACAO_API_URL", GAMIFICACAO)
    monkeypatch.setenv("TOKEN_GAMIFICACAO", "token-do-par-admin-gamificacao")
    monkeypatch.setenv("CURSOS_API_URL", CURSOS)
    monkeypatch.setenv("CURSOS_API_TOKEN", "token-do-par-admin-cursos")
    monkeypatch.setattr(central, "site_de", lambda request: "escola-a")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


def _dentro(email: str = DONO) -> Client:
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "id-opaco-123",
                "nome_exibido": "Fulano",
                "papel": None,
                "email": email,
            },
        )
    )
    cliente = Client()
    cliente.defaults["HTTP_COOKIE"] = COOKIE
    return cliente


def _texto(resposta) -> str:
    return resposta.content.decode()


def _quem_espera(quantos: int, esperando_ha_dias: int = 3) -> list[dict]:
    """Gente na fila de entrada, na forma EXATA que o contrato promete."""
    return [
        {
            "id": str(i),
            "site_id": "escola-a",
            "email": f"pessoa{i}@exemplo.com",
            "nome_completo": f"Pessoa {i}",
            "whatsapp": "(96) 99999-0000",
            "status": "aguardando",
            "criada_em": "2026-09-04T10:00:00Z",
            "esperando_ha_dias": esperando_ha_dias if i == 0 else 1,
            "ja_foi_aluno": False,
            "passagens_anteriores": 0,
            "saiu_em": None,
        }
        for i in range(quantos)
    ]


def _alunos_responde():
    """A `alunos` de pé, com nove pessoas na fila de entrada."""
    respx.get(FILA_DE_ENTRADA).mock(
        return_value=httpx.Response(200, json=_quem_espera(9))
    )
    _outras_respondem()


def _outras_respondem():
    for endereco in RESUMOS.values():
        respx.get(endereco).mock(
            return_value=httpx.Response(200, json={"quantidade": 0, "espera_ha_dias": None})
        )


# ---------------------------------------------------------------------------
# 1. A porta vem antes da tela
# ---------------------------------------------------------------------------
@respx.mock
def test_sem_sessao_a_central_manda_para_o_login():
    resposta = Client().get(TELA)
    assert resposta.status_code == 302
    assert "/entrar/google" in resposta["Location"]


@respx.mock
def test_para_quem_nao_e_da_casa_a_central_nao_existe():
    """404, e não 403: para um estranho, o bastidor não existe."""
    _alunos_responde()
    assert _dentro(DE_FORA).get(TELA).status_code == 404


# ---------------------------------------------------------------------------
# 2. A fila na tela, com a idade dela
# ---------------------------------------------------------------------------
@respx.mock
def test_a_fila_de_entrada_aparece_com_quantidade_e_idade():
    _alunos_responde()
    html = _texto(_dentro().get(TELA))

    assert "9 · Pessoas querendo entrar na escola" in html
    assert "A mais antiga espera há 3 dias." in html
    assert '<div class="hero-numero">9</div>' in html
    assert "ocorrências identificadas" in html


@respx.mock
def test_a_fila_da_assinatura_nao_existe_mais_na_portaria():
    """Ela saiu em 06/09/2026, junto com a assinatura de obra da Caixa.

    Sem este guarda a linha volta de boa-fé na primeira sessão que ler um plano
    antigo, e voltaria como um 0 eterno, porque uma ideia em "Planejado" não
    espera mais por ninguém.
    """
    _alunos_responde()
    html = _texto(_dentro().get(TELA))

    # Medido pelo TÍTULO da fila e pelo LINK dela, que são as duas formas em
    # que a linha voltaria à tela. O nome "Caixa de Sugestões" sozinho não
    # serve de asserção aqui: ele vive também num comentário do CSS da
    # moldura, que é de outro assunto e viaja em toda tela do Admin.
    assert "Ideias esperando a sua assinatura" not in html
    assert reverse("caixa_esperando") not in html


@respx.mock
def test_a_linha_leva_ao_lugar_onde_a_coisa_se_resolve():
    """A portaria não resolve nada por dentro: ela é uma porta, e a porta abre.

    Medido pelo DESTINO, e não pela presença do texto: uma tela que listasse a
    fila sem link nenhum passaria num teste de texto e seria inútil.
    """
    _alunos_responde()
    html = _texto(_dentro().get(TELA))

    ate = html.index("Pessoas querendo entrar na escola")
    inicio = html.rindex('href="', 0, ate) + len('href="')
    assert html[inicio : html.index('"', inicio)] == reverse("escola_alunos")


# ---------------------------------------------------------------------------
# 3. "Não consegui perguntar" NUNCA vira zero — o guarda que importa
# ---------------------------------------------------------------------------
@respx.mock
def test_com_a_alunos_muda_a_tela_diz_isso_e_NAO_mostra_zero():
    """O guarda mais caro deste arquivo.

    A `alunos` fora do ar não pode virar "ninguém está esperando aprovação". A
    asserção é dupla de propósito: a frase honesta tem de APARECER, e a frase
    tranquilizadora tem de SUMIR. Só a primeira metade deixaria passar uma tela
    que dissesse as duas coisas ao mesmo tempo.
    """
    respx.get(FILA_DE_ENTRADA).mock(return_value=httpx.Response(503))
    _outras_respondem()
    html = _texto(_dentro().get(TELA))

    assert "Não foi possível consultar a lista de alunos agora." in html
    assert "0 · Pessoas querendo entrar" not in html
    assert "Nada esperando você em: a lista de alunos" not in html
    assert 'class="hero-numero"' not in html


@respx.mock
@pytest.mark.parametrize("status", [401, 403])
def test_acesso_negado_pela_alunos_nao_e_queda_nem_fila_vazia(status):
    """Credencial recusada pede outro conserto que a queda, e a tela diz qual.

    Recarregar não resolve um 401/403, então a frase da queda tem de SUMIR e a
    que manda pedir a uma sessão que restaure a credencial tem de APARECER.
    """
    respx.get(FILA_DE_ENTRADA).mock(return_value=httpx.Response(status))
    _outras_respondem()
    html = _texto(_dentro().get(TELA))

    assert (
        "Acesso negado: a lista de alunos recusou a credencial de leitura da Central."
        in html
    )
    assert "Confira a credencial de leitura dessa fonte" in html
    assert "Não foi possível consultar" not in html
    assert "0 · Pessoas querendo entrar" not in html
    assert "Nada esperando você em: a lista de alunos" not in html
    assert 'class="hero-numero"' not in html


@respx.mock
def test_sem_o_par_de_tokens_a_tela_tambem_abre(monkeypatch):
    """Enquanto o par não estiver no env da VPS, a área abre e a tela avisa."""
    monkeypatch.delenv("ALUNOS_API_URL", raising=False)
    _outras_respondem()

    resposta = _dentro().get(TELA)

    assert resposta.status_code == 200
    assert "Não foi possível consultar" in _texto(resposta)


@respx.mock
def test_zero_de_verdade_e_uma_frase_DIFERENTE_de_nao_sei():
    """As duas telas que se parecem de dentro do código, medidas separadas.

    Sem este guarda, um `{% if fila.quantidade %}` no template juntaria os dois
    casos e ninguém veria: zero é falso em template, exatamente como `None`.
    """
    respx.get(FILA_DE_ENTRADA).mock(return_value=httpx.Response(200, json=[]))
    _outras_respondem()
    html = _texto(_dentro().get(TELA))

    assert "Nada esperando você em:" in html
    assert "a lista de alunos" in html
    assert "Não foi possível consultar a lista de alunos" not in html
    assert 'class="hero-numero"' not in html


# ---------------------------------------------------------------------------
# 4. A confissão: a tela diz o que ela ainda NÃO conta
# ---------------------------------------------------------------------------
@respx.mock
def test_as_quatro_filas_entram_na_conta():
    _alunos_responde()
    for chave, quantidade, idade in (("portfolio", 2, 4), ("marcos", 3, 1), ("checkpoints", 5, 0)):
        respx.get(RESUMOS[chave]).mock(return_value=httpx.Response(
            200, json={"quantidade": quantidade, "espera_ha_dias": idade}
        ))
    html = _texto(_dentro().get(TELA))
    assert '<div class="hero-numero">19</div>' in html
    for nome in ("Portfólios pedindo conferência", "Provas de marco enviadas pelos alunos", "Checkpoints de aula esperando laudo"):
        assert nome in html
    assert "A mais antiga chegou hoje." in html


@respx.mock
def test_fonte_caida_e_recusa_de_token_nao_viram_zero():
    _alunos_responde()
    respx.get(RESUMOS["portfolio"]).mock(return_value=httpx.Response(503))
    respx.get(RESUMOS["marcos"]).mock(return_value=httpx.Response(403))
    html = _texto(_dentro().get(TELA))
    assert "Não foi possível consultar a fila de portfólios agora" in html
    assert "Acesso negado: a fila de marcos" in html
    assert "Nada esperando você em: a fila de portfólios" not in html
    assert '<div class="hero-numero">9</div>' in html


# ---------------------------------------------------------------------------
# 5. A porta da capa e o item do menu, sob o prefixo de produção
# ---------------------------------------------------------------------------
@pytest.fixture
def sob_o_prefixo_publico():
    """O regime de produção: a área inteira mora sob `/admin`.

    Mexe no PREFIXO DE SCRIPT, e não em `settings.FORCE_SCRIPT_NAME`, porque é
    o prefixo de thread que `reverse()` lê. O `finally`
    restaura o anterior: o prefixo vaza entre testes.
    """
    anterior = get_script_prefix()
    set_script_prefix("/admin/")
    try:
        yield
    finally:
        set_script_prefix(anterior)


@respx.mock
def test_a_visao_geral_oferece_a_porta_da_central(sob_o_prefixo_publico):
    """Um botão que ninguém encontra é uma funcionalidade que não existe.

    E o endereço tem de levar o prefixo público: `href="/pendencias/"` abriria
    no PC de quem desenvolve e daria 404 só na tela dele.
    """
    html = _texto(_dentro().get("/"))

    assert "Ver o que está esperando você" in html
    assert 'href="/admin/pendencias/"' in html


def test_a_central_esta_no_menu_de_toda_tela_da_area(sob_o_prefixo_publico):
    """O menu é o que faz a tela ser alcançável de qualquer lugar da área.

    Medido na MOLDURA, que é quem decide o menu de toda página
    (`apps/core/moldura.py`), e com o endereço já sob o prefixo de produção:
    entrar na lista com um `href` sem `/admin` seria um item de menu que dá 404
    só na tela dele.
    """
    itens = moldura.secoes_do_menu("/")
    nossa = [i for i in itens if i["rotulo"] == "Pendências"]

    assert len(nossa) == 1, "a Central precisa de exatamente um item no menu"
    assert nossa[0]["href"] == "/admin/pendencias/"


def test_a_central_acende_no_menu_quando_e_ela_que_esta_aberta(sob_o_prefixo_publico):
    """ "Você está aqui" tem de valer para a tela nova como vale para as outras.

    A contraprova está junto: aberta noutra tela, o item apaga. Sem ela, um
    item aceso para sempre passaria neste guarda.
    """
    aberta = {i["rotulo"]: i["aqui"] for i in moldura.secoes_do_menu("/pendencias/")}
    noutra = {i["rotulo"]: i["aqui"] for i in moldura.secoes_do_menu("/escola/")}

    assert aberta["Pendências"] is True
    assert noutra["Pendências"] is False
