"""Teste-guarda: a Central de Pendências (`/admin/pendencias/`), degrau 1.

Plano: `documentos/pendencias-e-conferencia-por-pares.md`.

O QUE ESTE ARQUIVO EXISTE PARA IMPEDIR, e por que os testes óbvios não
impediriam:

1. **A tela dizendo "nada esperando você" quando a verdade é "não consegui
   perguntar".** É a falha mais cara possível aqui, e a única cujo custo se
   mede em pessoas: nove gente esperando aprovação viraria um zero, e o
   mantenedor fecharia a tela em paz. Um teste que só afirmasse `200` ficaria
   verde com a `alunos` fora do ar. Por isso os guardas de baixo derrubam cada
   fila de propósito e exigem que a tela MUDE de frase.

2. **O total virando uma conta fechada com uma fila muda.** Somar o que se sabe
   e apresentar como "20 coisas esperando você" é a mesma mentira do zero,
   disfarçada de precisão. A tela tem de dizer "pelo menos".

3. **A confissão sumindo.** Este degrau enxerga três das seis filas do site.
   Uma portaria que enxerga metade e não avisa ensina o mantenedor a confiar
   num "nada esperando" que ela não pode sustentar.

4. **O número do painel divergindo do painel.** A regra da caixa "Precisa de
   você" mora em `painel/logica.js::caixaDeEntrada`, e esta célula não roda
   JavaScript: ela lê o carimbo que o gerador deixa em `painel.html`. Um
   `test_...` que montasse uma página de mentira com o formato esperado
   provaria apenas que o teste concorda com o código. O guarda daqui lê a
   página REAL gerada pelo gerador REAL (o `conftest` a materializa), que é a
   única forma de a divergência de formato aparecer aqui e não em produção.

5. **A rota nascendo fora da porta.** `CAMINHOS_ISENTOS` é igualdade exata e
   já tem guarda próprio, mas ele prova que ninguém acrescentou isenção, não
   que ESTA rota responde a quem não é da casa. Aqui se mede de fora.

A rede é dublada com `respx`, como nos irmãos desta pasta: além de isolar, é
isso que prova que a tela não sai para a rede por conta própria, porque
`respx.mock` sem rota registrada estoura em qualquer chamada inesperada.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone as tz
from pathlib import Path

import httpx
import pytest
import respx
from django.test import Client
from django.urls import get_script_prefix, reverse, set_script_prefix

from apps.core import moldura
from apps.core import pendencias as central
from apps.core.painel import diretorio_do_painel

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
ALUNOS = "http://alunos:8000/api/alunos"
FILA_DE_ENTRADA = f"{ALUNOS}/pre-matriculas"
LISTA_DE_ALUNOS = f"{ALUNOS}/matriculas"
CAIXA = "http://sugestoes:8000/interno"
IDEIAS = f"{CAIXA}/gestao/ideias"
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


def _ideia(id_: int, **campos) -> dict:
    base = {
        "id": id_,
        "titulo": "Página pública com os meus projetos",
        "problema": "Meus projetos ficam parados no computador.",
        "solucao_proposta": "",
        "categoria": "Plataforma",
        "status": "planejado",
        "votos": 218,
        "comentarios": 31,
        "pessoas": 176,
        "autor": "Larissa M.",
        "criada_em": "2026-07-12T10:00:00+00:00",
        "parada_desde": "2026-07-12T10:00:00+00:00",
        "ja_ouviram": False,
        "tem_avaliacao": True,
        # `False` é o que põe a ideia na coluna "Esperando você assinar":
        # aprovada, sem documento de obra assinado (`caixa._coluna_de`).
        "tem_changespec": False,
        "motivo_da_saida": "",
        "avaliacao": None,
    }
    base.update(campos)
    return base


def _todos_respondem(fila=None, ideias=None):
    """As três fontes de pé. O painel vem do disco, materializado pelo conftest."""
    respx.get(FILA_DE_ENTRADA).mock(
        return_value=httpx.Response(200, json=_quem_espera(9) if fila is None else fila)
    )
    respx.get(LISTA_DE_ALUNOS).mock(return_value=httpx.Response(200, json=[]))
    respx.get(IDEIAS).mock(
        return_value=httpx.Response(
            200,
            json={
                "quadro": "Meshcraft",
                "pode_assinar": True,
                "pessoas_esperando": 0,
                "silencio_medio_em_dias": None,
                "pessoas_em_silencio_demais": 0,
                "ideias": [_ideia(1)] if ideias is None else ideias,
            },
        )
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
    _todos_respondem()
    assert _dentro(DE_FORA).get(TELA).status_code == 404


# ---------------------------------------------------------------------------
# 2. As três filas na tela, com a idade de cada uma
# ---------------------------------------------------------------------------
@respx.mock
def test_as_tres_filas_aparecem_com_quantidade_e_idade():
    _todos_respondem()
    html = _texto(_dentro().get(TELA))

    assert "9 · Pessoas querendo entrar na escola" in html
    assert "A mais antiga espera há 3 dias." in html
    assert "1 · Ideias esperando a sua assinatura" in html
    assert "Decisões suas paradas no painel do sistema" in html


@respx.mock
def test_cada_linha_leva_ao_lugar_onde_a_coisa_se_resolve():
    """A portaria não resolve nada por dentro: ela é uma porta, e a porta abre.

    Medido pelo DESTINO, e não pela presença do texto: uma tela que listasse as
    três filas sem link nenhum passaria num teste de texto e seria inútil.
    """
    _todos_respondem()
    html = _texto(_dentro().get(TELA))

    for rotulo, rota in (
        ("Pessoas querendo entrar na escola", "escola_alunos"),
        ("Ideias esperando a sua assinatura", "caixa_esperando"),
        ("Decisões suas paradas no painel do sistema", "painel"),
    ):
        ate = html.index(rotulo)
        inicio = html.rindex('href="', 0, ate) + len('href="')
        assert html[inicio : html.index('"', inicio)] == reverse(rota), rotulo


@respx.mock
def test_a_ideia_que_espera_um_ROBO_nao_entra_na_conta_dele():
    """Só a coluna "Esperando você assinar" é dele.

    Uma ideia já assinada espera um robô pegar, e listá-la aqui encheria a
    portaria de trabalho que não é do mantenedor. A diferença entre as duas é
    UM campo (`tem_changespec`), e é justamente por ser sutil que ela precisa
    de guarda.
    """
    _todos_respondem(ideias=[_ideia(1, tem_changespec=True)])
    html = _texto(_dentro().get(TELA))

    assert "Ideias esperando a sua assinatura" not in html
    assert "a Caixa de Sugestões" in html  # aparece como "nada esperando aqui"


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
    respx.get(LISTA_DE_ALUNOS).mock(return_value=httpx.Response(200, json=[]))
    respx.get(IDEIAS).mock(
        return_value=httpx.Response(
            200,
            json={
                "quadro": "Meshcraft",
                "pode_assinar": True,
                "pessoas_esperando": 0,
                "silencio_medio_em_dias": None,
                "pessoas_em_silencio_demais": 0,
                "ideias": [],
            },
        )
    )
    html = _texto(_dentro().get(TELA))

    assert "Não deu para perguntar a a lista de alunos agora." in html
    assert "0 · Pessoas querendo entrar" not in html
    assert "Nada esperando você em: a lista de alunos" not in html


@respx.mock
def test_com_a_caixa_muda_a_tela_diz_isso_e_a_pagina_abre_igual():
    """Fail-OPEN por LINHA: uma fila muda não derruba as outras duas."""
    respx.get(FILA_DE_ENTRADA).mock(
        return_value=httpx.Response(200, json=_quem_espera(9))
    )
    respx.get(LISTA_DE_ALUNOS).mock(return_value=httpx.Response(200, json=[]))
    respx.get(IDEIAS).mock(return_value=httpx.Response(503))

    resposta = _dentro().get(TELA)
    html = _texto(resposta)

    assert resposta.status_code == 200
    assert "Não deu para perguntar a a Caixa de Sugestões agora." in html
    assert "9 · Pessoas querendo entrar na escola" in html


@respx.mock
def test_sem_o_par_de_tokens_a_tela_tambem_abre(monkeypatch):
    """Enquanto o par não estiver no env da VPS, a área abre e a tela avisa."""
    monkeypatch.delenv("ALUNOS_API_URL", raising=False)
    monkeypatch.delenv("SUGESTOES_API_URL", raising=False)

    resposta = _dentro().get(TELA)

    assert resposta.status_code == 200
    assert "Não deu para perguntar" in _texto(resposta)


@respx.mock
def test_com_uma_fila_muda_o_total_vira_um_PISO_e_nao_uma_conta_fechada():
    """Somar o que se sabe e chamar de total é a mentira do zero, com precisão.

    O guarda mede as duas frases porque elas são a mesma tela em dois estados,
    e trocar uma pela outra é a regressão provável.
    """
    respx.get(FILA_DE_ENTRADA).mock(
        return_value=httpx.Response(200, json=_quem_espera(9))
    )
    respx.get(LISTA_DE_ALUNOS).mock(return_value=httpx.Response(200, json=[]))
    respx.get(IDEIAS).mock(return_value=httpx.Response(503))

    html = _texto(_dentro().get(TELA))

    assert "É <b>pelo menos</b> isso" in html
    assert "nas três filas que esta tela já enxerga" not in html


@respx.mock
def test_com_tudo_respondendo_o_total_e_a_soma_e_a_tela_diz_que_e_fechada():
    """A contraprova do guarda de cima: sem fila muda, nada de "pelo menos"."""
    _todos_respondem()
    html = _texto(_dentro().get(TELA))

    assert "nas três filas que esta tela já enxerga" in html
    assert "É <b>pelo menos</b> isso" not in html


@respx.mock
def test_zero_de_verdade_e_uma_frase_DIFERENTE_de_nao_sei():
    """As duas telas que se parecem de dentro do código, medidas separadas.

    Sem este guarda, um `{% if fila.quantidade %}` no template juntaria os dois
    casos e ninguém veria: zero é falso em template, exatamente como `None`.
    """
    respx.get(FILA_DE_ENTRADA).mock(return_value=httpx.Response(200, json=[]))
    respx.get(LISTA_DE_ALUNOS).mock(return_value=httpx.Response(200, json=[]))
    respx.get(IDEIAS).mock(
        return_value=httpx.Response(
            200,
            json={
                "quadro": "Meshcraft",
                "pode_assinar": True,
                "pessoas_esperando": 0,
                "silencio_medio_em_dias": None,
                "pessoas_em_silencio_demais": 0,
                "ideias": [],
            },
        )
    )
    html = _texto(_dentro().get(TELA))

    assert "Nada esperando você em:" in html
    assert "a lista de alunos" in html
    assert "Não deu para perguntar a a lista de alunos" not in html


# ---------------------------------------------------------------------------
# 4. A confissão: a tela diz o que ela ainda NÃO conta
# ---------------------------------------------------------------------------
@respx.mock
def test_a_tela_confessa_as_filas_que_ainda_nao_enxerga():
    """Portaria que enxerga metade e não avisa é pior que portaria nenhuma."""
    _todos_respondem()
    html = _texto(_dentro().get(TELA))

    assert "O que esta tela ainda não conta" in html
    for nome, endereco in central.FILAS_QUE_AINDA_NAO_VEJO:
        assert nome in html
        assert endereco in html


def test_a_confissao_lista_as_TRES_filas_do_degrau_3_e_nenhuma_outra():
    """Trava o conteúdo da lista, e não só a existência do bloco.

    Uma lista que ficasse vazia por engano deixaria o guarda de cima verde: o
    `for` não iteraria, e o bloco sumiria da tela sem nenhum vermelho.
    """
    assert [nome for nome, _ in central.FILAS_QUE_AINDA_NAO_VEJO] == [
        "Portfólios pedindo conferência",
        "Provas de marco enviadas pelos alunos",
        "Checkpoints de aula esperando laudo",
    ]


# ---------------------------------------------------------------------------
# 5. O número do painel é o do PAINEL, lido da página que o gerador produz
# ---------------------------------------------------------------------------
def test_o_carimbo_da_fila_casa_com_a_pagina_REAL_do_gerador():
    """A ponte entre o gerador (JavaScript) e esta célula (Python), medida.

    Não é um teste de formato contra si mesmo: a página vem do gerador de
    verdade, materializado pelo `conftest`. No dia em que alguém mudar a forma
    do carimbo de um lado só, o vermelho aparece aqui, e não na tela dele.
    """
    pasta = diretorio_do_painel()
    assert pasta is not None, (
        "a pasta do painel não foi encontrada — sem ela este guarda não mede "
        "nada, e isso não é um OK ([INV-CI01])."
    )
    achado = central._CARIMBO_DA_FILA.search(
        (pasta / "painel.html").read_text(encoding="utf-8")
    )
    assert achado is not None, (
        "o gerador do painel não carimbou `pedidosDoDono` na página, ou mudou a "
        "forma do carimbo. A Central passaria a dizer 'não consegui perguntar' "
        "para sempre, em silêncio. Conserte `painel/gerar_manifesto.js` e o "
        "padrão em `apps/core/pendencias.py` juntos."
    )
    assert int(achado.group(1)) >= 0


@respx.mock
def test_sem_o_painel_na_imagem_a_linha_diz_que_nao_sabe(monkeypatch):
    """Painel ausente vira "não consegui perguntar", nunca "você está em dia".

    Um zero aqui afirmaria que ele respondeu todos os robôs, que é o contrário
    do que se sabe quando a pasta nem chegou na imagem.
    """
    monkeypatch.setattr(central, "diretorio_do_painel", lambda: None)
    _todos_respondem()

    html = _texto(_dentro().get(TELA))

    assert "Não deu para perguntar a o painel do sistema agora." in html
    assert "0 · Decisões suas paradas" not in html


def test_o_carimbo_recusa_uma_pagina_de_outro_formato():
    """A contraprova do padrão: ele não casa com qualquer coisa parecida.

    Um padrão frouxo casaria a linha de outra geração e a Central mostraria um
    número que ninguém calculou.
    """
    assert central._CARIMBO_DA_FILA.search(
        'pedidosDoDono: { quantidade: 14, maisAntigoQuando: "2026-08-31" },'
    )
    assert central._CARIMBO_DA_FILA.search(
        "pedidosDoDono: { quantidade: 0, maisAntigoQuando: null },"
    )
    assert not central._CARIMBO_DA_FILA.search("pedidosDoDono: { quantidade: 14 }")
    assert not central._CARIMBO_DA_FILA.search('pedidosDoDono: "14"')


def test_a_data_do_pedido_mais_antigo_vira_dias_de_espera():
    """A conta que a tela mostra, feita sobre um relógio conhecido.

    Sem duble de rede: é aritmética de data, e a fonte é o carimbo.
    """
    agora = datetime(2026, 9, 7, 12, 0, tzinfo=tz.utc)
    assert central._mais_antiga(["2026-08-31"], agora) == 7
    assert central._mais_antiga([], agora) is None
    # Data no futuro acontece de verdade (relógio da máquina fora de hora), e
    # "espera há -355142 dias" não é um número esquisito: é uma frase sem
    # sentido numa tela feita para leigo.
    adiante = (agora + timedelta(days=30)).date().isoformat()
    assert central._mais_antiga([adiante], agora) == 0


# ---------------------------------------------------------------------------
# 6. A porta da capa e o item do menu, sob o prefixo de produção
# ---------------------------------------------------------------------------
@pytest.fixture
def sob_o_prefixo_publico():
    """O regime de produção: a área inteira mora sob `/admin`.

    Mexe no PREFIXO DE SCRIPT, e não em `settings.FORCE_SCRIPT_NAME`, porque é
    o prefixo de thread que `reverse()` lê (`armadilhas/081`). O `finally`
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
    no PC de quem desenvolve e daria 404 só na tela dele (`armadilhas/081`).
    """
    respx.get(FILA_DE_ENTRADA).mock(return_value=httpx.Response(200, json=[]))
    respx.get(LISTA_DE_ALUNOS).mock(return_value=httpx.Response(200, json=[]))
    html = _texto(_dentro().get("/"))

    assert "Ver o que está esperando você" in html
    assert 'href="/admin/pendencias/"' in html


def test_a_central_esta_no_menu_de_toda_tela_da_area(sob_o_prefixo_publico):
    """O menu é o que faz a tela ser alcançável de qualquer lugar da área.

    Medido na MOLDURA, que é quem decide o menu de toda página
    (`apps/core/moldura.py`), e com o endereço já sob o prefixo de produção:
    entrar na lista com um `href` sem `/admin` seria um item de menu que dá 404
    só na tela dele (`armadilhas/081`).
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
