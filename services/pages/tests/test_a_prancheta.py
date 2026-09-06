"""A PRANCHETA do degrau 07: as cinco etapas, as listas, e a marca que fica.

Os dois critérios que mandam aqui, e o modo de falha silencioso de cada um:

**AC-06 (o progresso persiste entre visitas E ENTRE APARELHOS).** O caminho
curto para lembrar de uma marcação é `request.session`, que funciona em dev,
passa em teste de unidade, reprova este critério (sessão não atravessa
aparelho) e desloga a plataforma inteira em produção (`armadilhas/143`,
[INV-P12]). Por isso a prova do segundo aparelho não reusa o cliente do
primeiro: ela monta um `Client()` novo, sem nada guardado, e manda só o cookie
de sessão. É a única forma de o teste medir o BANCO em vez de medir a memória
do próprio teste.

**AC-07 (o progresso de um aluno nunca aparece para outro).** O guarda de
consulta já mora em `test_isolamento_por_aluno.py`, provado por mutação. O que
este arquivo acrescenta é a mesma prova pela TELA: a Prancheta do Bruno pedida
com o cookie do Bruno, depois de a Ana ter marcado tudo.

**As listas são DADO.** O teste que prova isso corrige o texto de um item no
banco e exige a frase nova na tela. Um teste que só procurasse a frase da
escola ficaria verde com o texto cravado no template, que é exatamente o que o
despacho proíbe.

O que este arquivo NÃO mede, porque não é deste degrau: as peças por link
(degrau 08), o semáforo (10) e a vitrine (13).
"""

from __future__ import annotations

import pytest
from django.test import Client

from apps.portfolio.models import (
    EtapaDoRoteiro,
    ItemDeConferencia,
    ItemDoRoteiro,
    Portfolio,
)
from apps.portfolio.roteiro_da_escola import ROTEIRO

from tests.conftest import (
    ANA,
    COOKIE,
    SITE_DECLARADO,
    dublar_matricula,
    dublar_sessao,
)

# O cookie de OUTRO aluno. Opaco como o da Ana: quem o traduz é a `identidade`,
# e aqui o dublê responde por ele.
COOKIE_DO_BRUNO = "meshcraft_sessao=cookie-opaco-de-bruno"
BRUNO = {
    "autenticado": True,
    "id": "p_bruno",
    "email": "bruno@exemplo.com",
    "nome_exibido": "Bruno",
    "papel": "aluno",
}

# O primeiro item da primeira etapa, e a chave dele é a mesma desde o degrau 02.
CHAVE = "tres-tipos-escolhidos"

# COMO A TELA DIZ QUE ESTE ITEM ESTÁ MARCADO, e é a marcação de verdade: o
# `aria-pressed` do botão é o que um leitor de tela anuncia. Escrita por
# extenso, e não montada a partir do template: um teste que lesse a mesma fonte
# que o código passaria com a tela vazia.
MARCADO_NA_TELA = f'value="{CHAVE}" aria-pressed="true"'


def texto(resposta) -> str:
    return resposta.content.decode("utf-8")


def abrir(cookie: str = COOKIE):
    """A Prancheta, pedida de um aparelho NOVO a cada chamada.

    `Client()` por chamada não é desperdício: é o que faz "de outro aparelho"
    ser verdade no teste. Um cliente reaproveitado carregaria o que a
    requisição anterior tivesse deixado nele.
    """
    return Client().get("/", HTTP_COOKIE=cookie)


def marcar(chave: str = CHAVE, *, marcar: str = "1", cookie: str = COOKIE):
    return Client().post(
        "/marcar", {"chave": chave, "marcar": marcar}, HTTP_COOKIE=cookie
    )


@pytest.fixture
def aluno_ana(env_dos_pares, rede, site_declarado, db):
    """Ana, dentro da casa, numa instalação que sabe de que escola ela é."""
    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"], "aluno")
    return ANA


@pytest.fixture
def os_dois_alunos(env_dos_pares, rede, site_declarado, db):
    """Ana e Bruno, cada um com o seu cookie, na mesma escola.

    O dublê responde por COOKIE, e não por um valor só: sem isso os dois
    alunos seriam a mesma pessoa e o guarda do isolamento não mediria nada.
    """
    import httpx

    from tests.conftest import URL_DA_SESSAO

    def por_cookie(pedido):
        cookie = pedido.headers.get("cookie", "")
        corpo = BRUNO if "bruno" in cookie else ANA
        return httpx.Response(200, json=corpo)

    rede.get(URL_DA_SESSAO).mock(side_effect=por_cookie)
    dublar_matricula(rede, ANA["email"], "aluno")
    dublar_matricula(rede, BRUNO["email"], "aluno")


# ---------------------------------------------------------------------------
# 1. As cinco etapas, e elas vêm do banco
# ---------------------------------------------------------------------------
def test_o_aluno_ve_as_cinco_etapas(aluno_ana):
    saida = texto(abrir())
    for etapa in ROTEIRO:
        assert etapa["titulo"] in saida


def test_sao_exatamente_cinco_etapas_e_o_banco_recusa_a_sexta(db):
    """A lei fixa cinco (AC-06), e a faixa mora nas três tabelas que a usam."""
    assert EtapaDoRoteiro.objects.count() == 5

    from django.db.utils import IntegrityError

    with pytest.raises(IntegrityError):
        EtapaDoRoteiro.objects.create(numero=6, titulo="a sexta")


def test_a_lista_sai_do_banco_e_nao_do_template(aluno_ana):
    """Corrigir o texto no banco muda a tela, sem tocar em código.

    É este teste que separa "lista lida do banco" de "lista escrita no
    template": com a frase cravada no HTML ele fica vermelho.
    """
    ItemDoRoteiro.objects.filter(chave=CHAVE).update(
        texto="Pelo menos 4 tipos de modelo, porque a professora mudou de ideia."
    )

    saida = texto(abrir())

    assert "porque a professora mudou de ideia" in saida


def test_o_titulo_da_etapa_tambem_sai_do_banco(aluno_ana):
    EtapaDoRoteiro.objects.filter(numero=1).update(titulo="Comece escolhendo")

    assert "Comece escolhendo" in texto(abrir())


def test_a_prancheta_orienta_e_nunca_tranca(aluno_ana):
    """Plano §7: trancar conteúdo atrás da lista é proibido.

    Sem nenhuma marcação, o roteiro inteiro está na tela, da primeira etapa à
    última. Uma tela que revelasse a etapa seguinte só depois da anterior
    deixaria este teste vermelho na última etapa.
    """
    saida = texto(abrir())

    assert ItemDeConferencia.objects.count() == 0
    assert ROTEIRO[-1]["titulo"] in saida


# ---------------------------------------------------------------------------
# 2. Marcar, desmarcar, e a marca que atravessa o aparelho (AC-06)
# ---------------------------------------------------------------------------
def test_o_aluno_marca_um_item(aluno_ana):
    resposta = marcar()

    assert resposta.status_code == 302
    marcacao = ItemDeConferencia.objects.get(chave=CHAVE)
    assert marcacao.marcado is True
    assert marcacao.marcado_em is not None
    assert marcacao.etapa == 1
    assert marcacao.portfolio.aluno_id == ANA["id"]
    assert marcacao.portfolio.site_id == SITE_DECLARADO


def test_a_marcacao_aparece_na_visita_seguinte(aluno_ana):
    marcar()

    assert MARCADO_NA_TELA in texto(abrir())


def test_a_marcacao_atravessa_aparelhos(aluno_ana):
    """O celular marca, o computador encontra. É o coração do AC-06.

    Cada chamada monta um `Client()` novo: o segundo pedido não herda nada do
    primeiro além do cookie de sessão, que é o que um aparelho novo tem.
    Guardar a marca em `request.session` deixaria este teste vermelho.
    """
    marcar()

    do_computador = abrir()

    assert MARCADO_NA_TELA in texto(do_computador)


def test_desmarcar_apaga_a_marca_e_nao_a_linha(aluno_ana):
    marcar()

    marcar(marcar="0")

    marcacao = ItemDeConferencia.objects.get(chave=CHAVE)
    assert marcacao.marcado is False
    assert marcacao.marcado_em is None
    assert MARCADO_NA_TELA not in texto(abrir())


def test_marcar_duas_vezes_nao_cria_duas_linhas(aluno_ana):
    """O aluno clica duas vezes, ou a rede repete o POST. Uma linha só."""
    marcar()
    marcar()

    assert ItemDeConferencia.objects.filter(chave=CHAVE).count() == 1


def test_o_portfolio_nasce_na_primeira_marcacao_e_nao_na_visita(aluno_ana):
    """Abrir a Prancheta é leitura, e leitura não escreve no banco.

    Um `GET` que criasse o portfólio encheria a tabela com quem só passou pela
    porta, e ainda faria a página do aluno depender de uma escrita para
    responder.
    """
    abrir()
    assert Portfolio.objects.count() == 0

    marcar()
    assert Portfolio.objects.count() == 1


# ---------------------------------------------------------------------------
# 3. Isolamento entre alunos, pela tela (AC-07)
# ---------------------------------------------------------------------------
def test_a_marcacao_da_ana_nao_aparece_para_o_bruno(os_dois_alunos):
    marcar(cookie=COOKIE)

    do_bruno = texto(abrir(cookie=COOKIE_DO_BRUNO))

    assert MARCADO_NA_TELA not in do_bruno


def test_o_bruno_marca_no_portfolio_dele_e_nao_no_da_ana(os_dois_alunos):
    marcar(cookie=COOKIE)
    marcar(cookie=COOKIE_DO_BRUNO)

    donos = {m.portfolio.aluno_id for m in ItemDeConferencia.objects.all()}

    assert donos == {ANA["id"], BRUNO["id"]}
    assert Portfolio.objects.count() == 2


def test_desmarcar_do_bruno_nao_toca_na_marcacao_da_ana(os_dois_alunos):
    """O caso que uma consulta sem aluno estragaria em silêncio.

    Com um `filter(chave=...)` sem dono, o desmarcar do Bruno apagaria a marca
    da Ana, e nenhuma tela reclamaria.
    """
    marcar(cookie=COOKIE)

    marcar(marcar="0", cookie=COOKIE_DO_BRUNO)

    da_ana = ItemDeConferencia.objects.get(portfolio__aluno_id=ANA["id"])
    assert da_ana.marcado is True


# ---------------------------------------------------------------------------
# 4. Entrada inválida, e a instalação que ainda não declarou a escola
# ---------------------------------------------------------------------------
def test_item_que_nao_existe_no_roteiro_e_recusado(aluno_ana):
    """Chave de fora do catálogo nunca vira linha no banco.

    Sem esta recusa, qualquer POST escreveria marcação com a chave que
    quisesse, e a tela do aluno passaria a ter itens que a escola nunca
    escreveu.
    """
    resposta = marcar("chave-inventada")

    assert resposta.status_code == 404
    assert ItemDeConferencia.objects.count() == 0


def test_sem_site_id_o_roteiro_aparece_e_a_marcacao_explica_por_que_nao_abre(
    env_dos_pares, rede, sem_site_declarado, db
):
    """A instalação de hoje: `infra/provisionar-pages.sh` não escreve `SITE_ID`.

    Duas coisas se exigem juntas, e uma sem a outra seria pior do que nada: o
    aluno CONTINUA lendo o roteiro (a Prancheta orienta, plano §7), e a
    ausência da marcação é dita em português, com o que ele deve fazer.
    """
    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"], "aluno")

    saida = texto(abrir())

    assert ROTEIRO[0]["titulo"] in saida
    assert "ainda não terminou de ligar" in saida
    assert "<input" not in saida


def test_sem_site_id_a_marcacao_e_recusada_em_vez_de_gravar_no_escuro(
    env_dos_pares, rede, sem_site_declarado, db
):
    """Fail-closed: sem saber de que escola é, nada entra no banco.

    Gravar com o site em branco misturaria os alunos de duas escolas na mesma
    linha no dia em que a segunda chegasse, e nenhuma tela quebraria para
    avisar.
    """
    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"], "aluno")

    resposta = marcar()

    assert resposta.status_code == 503
    assert Portfolio.objects.count() == 0
    assert ItemDeConferencia.objects.count() == 0


# ---------------------------------------------------------------------------
# 5. [INV-P12]: nem marcar assina sessão
# ---------------------------------------------------------------------------
def test_marcar_nao_escreve_o_cookie_de_sessao_do_site(aluno_ana):
    """O POST é a tentação concreta do [INV-P12], e é aqui que ela se mede.

    Se esta célula gravasse qualquer coisa em `request.session`, o Django
    reserializaria `meshcraft_sessao` com o conteúdo DAQUI e o aluno seria
    deslogado da plataforma inteira, sem erro em lugar nenhum
    (`armadilhas/143`).
    """
    resposta = marcar()

    assert "meshcraft_sessao" not in resposta.cookies
