"""Guardas da porta de MÁQUINA (`/api/mensageria`) — o degrau 6c do plano.

Por que ela precisa de guarda próprio, e forte: uma porta de máquina é a
superfície mais fácil de estragar do sistema, porque ninguém olha para ela. Não
tem tela, não tem link, não aparece no navegador de ninguém. Um campo a mais num
Schema não quebra página nenhuma, e uma operação nova sem cadeado fica verde.

AS QUATRO COISAS QUE ESTE ARQUIVO PROVA
---------------------------------------
1. **Fechada por padrão.** Sem token, token errado ou env ausente é 401 em TODA
   operação, e a lista de operações é MEDIDA do schema vivo, nunca digitada.
2. **O grau a mais é de verdade.** Quem só lê leva 403 ao tentar publicar. Este
   é o guarda que justifica os dois conjuntos de token existirem.
3. **A fronteira de site fecha (Lei 9).** Jornada de outro site é 404, e
   inscrição de outro site é 404 mesmo com o UUID certo em mãos.
4. **Publicar é criar versão nova, e a antiga não se mexe.** É o que faz as duas
   promessas do plano conviverem, e o cenário abaixo tem uma inscrição parada na
   v1 justamente para provar que ela continua lá depois da publicação.

O CENÁRIO TEM DENTE, DE PROPÓSITO
---------------------------------
As entregas do cenário incluem uma BARRADA com motivo escrito. Um cenário só com
entregas bem-sucedidas passaria mesmo se `listDeliveries` filtrasse o que não
saiu — e seria verde provando nada, justamente na metade que faz a tela do
mantenedor valer ("por que o aluno X não recebeu?").
"""

from __future__ import annotations

import json
from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from apps.jornadas.models import (
    Entrega,
    Inscricao,
    Jornada,
    JornadaVersao,
    Passo,
    TextoDoPasso,
)

pytestmark = pytest.mark.django_db

BASE = "/api/mensageria"
TOKEN_LEITURA = "token-do-par-que-so-le"
TOKEN_PUBLICACAO = "token-do-par-que-publica"
SITE = "site-da-escola"
OUTRO_SITE = "site-de-outra-escola"
SLUG = "boas-vindas"


@pytest.fixture(autouse=True)
def pares_autorizados(settings):
    settings.TOKENS_SOMENTE_LEITURA = {TOKEN_LEITURA}
    settings.TOKENS_PUBLICACAO = {TOKEN_PUBLICACAO}


def pedir(caminho: str, token: str | None = TOKEN_LEITURA):
    cabecalhos = {}
    if token:
        cabecalhos["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return Client().get(f"{BASE}{caminho}", **cabecalhos)


def postar(caminho: str, corpo: dict, token: str | None = TOKEN_PUBLICACAO):
    cabecalhos = {}
    if token:
        cabecalhos["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return Client().post(
        f"{BASE}{caminho}",
        data=json.dumps(corpo),
        content_type="application/json",
        **cabecalhos,
    )


def corpo(resposta) -> dict:
    return json.loads(resposta.content)


def _publicar(versao: JornadaVersao) -> JornadaVersao:
    """Publica de fora do ORM, como o semeador faz.

    `queryset.update()` e não `save()`: o gatilho da migração `0001` aceita este
    UPDATE porque `OLD.publicada_em` ainda é nulo, e recusa todos os seguintes.
    """
    JornadaVersao.objects.filter(pk=versao.pk).update(publicada_em=timezone.now())
    versao.refresh_from_db()
    return versao


def montar_o_cenario(site: str = SITE, slug: str = SLUG) -> dict:
    """Uma jornada publicada de dois passos, com gente dentro e entregas."""
    jornada = Jornada.objects.create(
        site_id=site, slug=slug, gatilho="identidade.pessoa-cadastrada", ativa=False
    )
    versao = JornadaVersao.objects.create(jornada=jornada, numero=1)
    passo1 = Passo.objects.create(
        jornada_versao=versao,
        ordem=1,
        atraso=timedelta(0),
        classe="relacional",
        canais=["sino"],
        condicao_slug="",
    )
    passo2 = Passo.objects.create(
        jornada_versao=versao,
        ordem=2,
        atraso=timedelta(days=2),
        janela=timedelta(days=3),
        classe="engajamento",
        canais=["sino", "email"],
        condicao_slug="ainda-nao-entrou-em-aula",
    )
    for passo, assunto in ((passo1, "Bem-vindo"), (passo2, "A primeira aula")):
        TextoDoPasso.objects.create(
            passo=passo, idioma="pt-br", assunto_visivel=assunto, corpo=f"{assunto}."
        )
        TextoDoPasso.objects.create(
            passo=passo, idioma="en", assunto_visivel=assunto, corpo=f"{assunto} (en)."
        )
    _publicar(versao)

    inscricao = Inscricao.objects.create(
        jornada_versao=versao,
        jornada=jornada,
        destinatario_id="p_aluno_opaco",
        site_id=site,
        passo_atual=1,
        estado="andando",
    )
    agora = timezone.now()
    Entrega.objects.create(
        inscricao=inscricao,
        passo=passo1,
        canal="sino",
        previsto_para=agora,
        enviado_em=agora,
        resultado="enviada",
    )
    # A LINHA COM DENTE: o que NÃO saiu, e por quê.
    Entrega.objects.create(
        inscricao=inscricao,
        passo=passo2,
        canal="email",
        previsto_para=agora,
        reagendado_para=agora + timedelta(days=1),
        resultado="barrada_pela_regua",
        motivo="ja tinha recebido uma hoje",
    )
    return {
        "jornada": jornada,
        "versao": versao,
        "passo1": passo1,
        "passo2": passo2,
        "inscricao": inscricao,
    }


# ---------------------------------------------------------------------------
# AS QUATRO LEITURAS
# ---------------------------------------------------------------------------
def test_listar_jornadas_traz_a_versao_publicada_corrente():
    montar_o_cenario()
    dados = corpo(pedir(f"/jornadas?site_id={SITE}"))
    assert dados["site_id"] == SITE
    assert len(dados["jornadas"]) == 1
    jornada = dados["jornadas"][0]
    assert jornada["slug"] == SLUG
    assert jornada["gatilho"] == "identidade.pessoa-cadastrada"
    assert jornada["ativa"] is False
    assert jornada["versoes"] == 1
    assert jornada["versao_publicada"]["numero"] == 1


def test_jornada_so_com_rascunho_aparece_na_lista_sem_versao_publicada():
    """Rascunho não some da lista, e é justamente o que a tela precisa mostrar.

    Se a jornada sumisse, o mantenedor não teria por onde publicar a primeira
    versão dela, e o buraco seria invisível: uma lista curta parece resposta.
    """
    jornada = Jornada.objects.create(site_id=SITE, slug="rascunho", gatilho="x.y")
    JornadaVersao.objects.create(jornada=jornada, numero=1)
    dados = corpo(pedir(f"/jornadas?site_id={SITE}"))
    assert dados["jornadas"][0]["versao_publicada"] is None


def test_jornada_de_outro_site_nao_aparece_na_lista():
    montar_o_cenario(site=OUTRO_SITE)
    assert corpo(pedir(f"/jornadas?site_id={SITE}"))["jornadas"] == []


def test_ler_jornada_traz_passos_na_ordem_com_texto_por_idioma():
    montar_o_cenario()
    dados = corpo(pedir(f"/jornadas/{SLUG}?site_id={SITE}"))
    assert dados["versao"]["numero"] == 1
    assert dados["publicada"] is True
    assert [p["ordem"] for p in dados["passos"]] == [1, 2]
    segundo = dados["passos"][1]
    assert segundo["atraso_segundos"] == 2 * 24 * 3600
    assert segundo["janela_segundos"] == 3 * 24 * 3600
    assert segundo["classe"] == "engajamento"
    assert segundo["canais"] == ["sino", "email"]
    assert segundo["condicao_slug"] == "ainda-nao-entrou-em-aula"
    assert [t["idioma"] for t in segundo["textos"]] == ["en", "pt-br"]


def test_o_atraso_sai_em_SEGUNDOS_e_nao_como_duracao_ISO():
    """A tela precisa somar e comparar. "P2D" obriga quem consome a escrever um
    parser para responder "quantos dias depois?", e é o que o pydantic emitiria
    sozinho se o campo fosse um `timedelta`."""
    montar_o_cenario()
    dados = corpo(pedir(f"/jornadas/{SLUG}?site_id={SITE}"))
    assert isinstance(dados["passos"][1]["atraso_segundos"], int)


def test_passo_sem_janela_sai_com_janela_nula_e_nao_zero():
    """Nulo é "não expira"; zero seria "expira imediatamente"."""
    montar_o_cenario()
    dados = corpo(pedir(f"/jornadas/{SLUG}?site_id={SITE}"))
    assert dados["passos"][0]["janela_segundos"] is None


def test_ler_jornada_de_outro_site_e_404():
    montar_o_cenario(site=OUTRO_SITE)
    assert pedir(f"/jornadas/{SLUG}?site_id={SITE}").status_code == 404


def test_listar_inscricoes_traz_estado_passo_e_versao():
    cenario = montar_o_cenario()
    dados = corpo(pedir(f"/jornadas/{SLUG}/inscricoes?site_id={SITE}"))
    assert dados["total"] == 1
    linha = dados["inscricoes"][0]
    assert linha["inscricao_id"] == str(cenario["inscricao"].id)
    assert linha["destinatario_id"] == "p_aluno_opaco"
    assert linha["estado"] == "andando"
    assert linha["passo_atual"] == 1
    assert linha["versao_numero"] == 1


def test_filtrar_inscricoes_por_estado():
    cenario = montar_o_cenario()
    Inscricao.objects.filter(pk=cenario["inscricao"].pk).update(estado="concluida")
    assert (
        corpo(pedir(f"/jornadas/{SLUG}/inscricoes?site_id={SITE}&estado=andando"))[
            "total"
        ]
        == 0
    )
    assert (
        corpo(pedir(f"/jornadas/{SLUG}/inscricoes?site_id={SITE}&estado=concluida"))[
            "total"
        ]
        == 1
    )


def test_estado_desconhecido_e_422_e_nao_lista_vazia():
    """Uma tela que peça "andandu" por engano precisa ver o erro, e não uma
    escola aparentemente sem ninguém dentro da sequência."""
    montar_o_cenario()
    assert (
        pedir(f"/jornadas/{SLUG}/inscricoes?site_id={SITE}&estado=andandu").status_code
        == 422
    )


def test_limite_CORTA_a_pagina_mas_total_conta_o_filtro_inteiro():
    """Uma tela que mostrasse `len(inscricoes)` estaria mostrando o teto, e nao
    quantas pessoas estao dentro da sequencia."""
    cenario = montar_o_cenario()
    for n in range(2):
        Inscricao.objects.create(
            jornada_versao=cenario["versao"],
            jornada=cenario["jornada"],
            destinatario_id=f"p_outro_{n}",
            site_id=SITE,
            estado="andando",
        )
    dados = corpo(pedir(f"/jornadas/{SLUG}/inscricoes?site_id={SITE}&limite=2"))
    assert dados["total"] == 3
    assert len(dados["inscricoes"]) == 2


def test_limite_absurdo_e_CORTADO_no_teto_nunca_recusado():
    montar_o_cenario()
    assert (
        pedir(f"/jornadas/{SLUG}/inscricoes?site_id={SITE}&limite=99999").status_code
        == 200
    )


def test_listar_entregas_traz_O_QUE_NAO_SAIU_com_o_motivo():
    """A metade que faz a tela valer. Sem ela, "por que o aluno X não recebeu?"
    fica sem resposta e o mantenedor olha para o silêncio."""
    cenario = montar_o_cenario()
    dados = corpo(
        pedir(f"/inscricoes/{cenario['inscricao'].id}/entregas?site_id={SITE}")
    )
    resultados = [(e["ordem"], e["canal"], e["resultado"]) for e in dados["entregas"]]
    assert resultados == [(1, "sino", "enviada"), (2, "email", "barrada_pela_regua")]
    barrada = dados["entregas"][1]
    assert barrada["motivo"] == "ja tinha recebido uma hoje"
    assert barrada["reagendado_para"] is not None
    assert barrada["enviado_em"] is None


def test_entregas_de_inscricao_de_OUTRO_SITE_e_404_mesmo_com_o_uuid_certo():
    """Lei 9 com o id em mãos. Sem esta conferência, quem tivesse o UUID leria a
    inscrição de outra escola pela porta da sua."""
    cenario = montar_o_cenario(site=OUTRO_SITE)
    assert (
        pedir(
            f"/inscricoes/{cenario['inscricao'].id}/entregas?site_id={SITE}"
        ).status_code
        == 404
    )


@pytest.mark.parametrize(
    "caminho",
    [
        "/jornadas",
        f"/jornadas/{SLUG}",
        f"/jornadas/{SLUG}/inscricoes",
    ],
)
def test_sem_site_id_e_422_em_toda_leitura_de_jornada(caminho):
    """Fallback silencioso aqui misturaria as sequências de dois sites na mesma
    tela, e ninguém veria a mistura acontecer."""
    montar_o_cenario()
    assert pedir(caminho).status_code == 422


# ---------------------------------------------------------------------------
# A ESCRITA: publicar é criar versão NOVA
# ---------------------------------------------------------------------------
def test_publicar_texto_cria_versao_NOVA_e_devolve_o_numero_dela():
    montar_o_cenario()
    resposta = postar(
        f"/jornadas/{SLUG}/textos",
        {
            "site_id": SITE,
            "ordem": 1,
            "idioma": "pt-br",
            "assunto_visivel": "Bem-vindo de novo",
            "corpo": "Texto novo do primeiro passo.",
        },
    )
    assert resposta.status_code == 200
    dados = corpo(resposta)
    assert dados["versao"] == 2
    assert dados["passos"] == 2
    assert dados["publicada_em"] is not None

    lida = corpo(pedir(f"/jornadas/{SLUG}?site_id={SITE}"))
    assert lida["versao"]["numero"] == 2
    textos = {t["idioma"]: t for t in lida["passos"][0]["textos"]}
    assert textos["pt-br"]["corpo"] == "Texto novo do primeiro passo."
    # O que NÃO foi editado veio junto na cópia. Sem isto a versão nova nasceria
    # pela metade, sem erro nenhum, e a sequência pararia de mandar mensagem.
    assert textos["en"]["corpo"] == "Bem-vindo (en)."
    assert len(lida["passos"]) == 2
    assert lida["passos"][1]["condicao_slug"] == "ainda-nao-entrou-em-aula"
    assert lida["passos"][1]["canais"] == ["sino", "email"]


def test_quem_estava_na_v1_CONTINUA_na_v1_depois_da_publicacao():
    """As duas promessas do plano só convivem por causa disto: o mantenedor
    edita quando quiser, e o texto não muda embaixo de quem já entrou."""
    cenario = montar_o_cenario()
    postar(
        f"/jornadas/{SLUG}/textos",
        {
            "site_id": SITE,
            "ordem": 1,
            "idioma": "pt-br",
            "assunto_visivel": "Outro assunto",
            "corpo": "Outro corpo.",
        },
    )
    cenario["inscricao"].refresh_from_db()
    assert cenario["inscricao"].jornada_versao_id == cenario["versao"].id
    antiga = corpo(pedir(f"/jornadas/{SLUG}?site_id={SITE}&versao=1"))
    textos = {t["idioma"]: t for t in antiga["passos"][0]["textos"]}
    assert textos["pt-br"]["corpo"] == "Bem-vindo."


def test_idioma_novo_entra_como_linha_nova_sem_PR_nenhum():
    montar_o_cenario()
    postar(
        f"/jornadas/{SLUG}/textos",
        {
            "site_id": SITE,
            "ordem": 2,
            "idioma": "es",
            "assunto_visivel": "La primera clase",
            "corpo": "La primera clase es corta.",
        },
    )
    lida = corpo(pedir(f"/jornadas/{SLUG}?site_id={SITE}"))
    idiomas = [t["idioma"] for t in lida["passos"][1]["textos"]]
    assert idiomas == ["en", "es", "pt-br"]


def test_publicar_NUNCA_liga_uma_jornada_desligada():
    """Editar uma frase não é ligar uma sequência. Ligar continua sendo gesto
    próprio do mantenedor, e um efeito colateral aqui escreveria para todo mundo
    que se cadastrasse."""
    cenario = montar_o_cenario()
    postar(
        f"/jornadas/{SLUG}/textos",
        {
            "site_id": SITE,
            "ordem": 1,
            "idioma": "pt-br",
            "assunto_visivel": "a",
            "corpo": "b",
        },
    )
    cenario["jornada"].refresh_from_db()
    assert cenario["jornada"].ativa is False


def test_versao_base_desatualizada_e_409_e_nao_sobrescreve_em_silencio():
    """Duas telas partindo da mesma base: sem esta recusa, a segunda venceria só
    por chegar depois, e a primeira edição sumiria sem aviso."""
    montar_o_cenario()
    assert (
        postar(
            f"/jornadas/{SLUG}/textos",
            {
                "site_id": SITE,
                "ordem": 1,
                "idioma": "pt-br",
                "assunto_visivel": "a",
                "corpo": "b",
                "versao_base": 1,
            },
        ).status_code
        == 200
    )
    assert (
        postar(
            f"/jornadas/{SLUG}/textos",
            {
                "site_id": SITE,
                "ordem": 1,
                "idioma": "pt-br",
                "assunto_visivel": "c",
                "corpo": "d",
                "versao_base": 1,
            },
        ).status_code
        == 409
    )


def test_publicar_passo_que_nao_existe_e_404():
    montar_o_cenario()
    assert (
        postar(
            f"/jornadas/{SLUG}/textos",
            {
                "site_id": SITE,
                "ordem": 99,
                "idioma": "pt-br",
                "assunto_visivel": "a",
                "corpo": "b",
            },
        ).status_code
        == 404
    )


def test_publicar_em_jornada_sem_versao_publicada_e_409():
    Jornada.objects.create(site_id=SITE, slug="so-rascunho", gatilho="x.y")
    assert (
        postar(
            "/jornadas/so-rascunho/textos",
            {
                "site_id": SITE,
                "ordem": 1,
                "idioma": "pt-br",
                "assunto_visivel": "a",
                "corpo": "b",
            },
        ).status_code
        == 409
    )


@pytest.mark.parametrize(
    "campo", ["idioma", "corpo", "assunto_visivel"], ids=["idioma", "corpo", "assunto"]
)
def test_campo_vazio_e_422_e_nao_500_do_banco(campo):
    """As `CheckConstraint` do banco recusariam isto com 500 e uma mensagem que
    só um programador entende. A tela do mantenedor precisa dizer o que faltou."""
    montar_o_cenario()
    pedido = {
        "site_id": SITE,
        "ordem": 1,
        "idioma": "pt-br",
        "assunto_visivel": "a",
        "corpo": "b",
    }
    pedido[campo] = "   "
    assert postar(f"/jornadas/{SLUG}/textos", pedido).status_code == 422


def test_publicar_em_jornada_de_outro_site_e_404():
    montar_o_cenario(site=OUTRO_SITE)
    assert (
        postar(
            f"/jornadas/{SLUG}/textos",
            {
                "site_id": SITE,
                "ordem": 1,
                "idioma": "pt-br",
                "assunto_visivel": "a",
                "corpo": "b",
            },
        ).status_code
        == 404
    )


# ---------------------------------------------------------------------------
# A porta é fechada por padrão, e a lista de operações é MEDIDA
# ---------------------------------------------------------------------------
def _caminhos_de_leitura() -> list[str]:
    """Os caminhos de LEITURA que a porta expõe, medidos do schema vivo.

    Lista escrita à mão esquece: no dia em que uma operação nova entrasse na
    porta, este guarda continuaria verde cobrindo as antigas, e a operação nova
    nasceria sem cadeado provado. Foi o que quase aconteceu na `gamificacao` em
    01/09/2026.

    Aqui a medição é do schema VIVO porque o contrato congelado ainda não
    existe: ele nasce no degrau 6d, e a ordem porta-antes-de-contrato é
    obrigatória (`armadilhas/228`). Quando ele existir, esta função passa a ler
    o congelado, como a da `gamificacao` faz, porque é contra a PROMESSA que o
    cadeado precisa valer.
    """
    from config.api import api

    schema = api.get_openapi_schema(path_prefix="")
    caminhos = [
        rota.replace("{slug}", SLUG).replace(
            "{inscricao_id}", "00000000-0000-0000-0000-000000000000"
        )
        for rota, operacoes in schema["paths"].items()
        if "get" in operacoes
    ]
    assert caminhos, "a porta nao declarou operacao de leitura nenhuma"
    return caminhos


def _caminhos_de_escrita() -> list[str]:
    from config.api import api

    schema = api.get_openapi_schema(path_prefix="")
    caminhos = [
        rota.replace("{slug}", SLUG)
        for rota, operacoes in schema["paths"].items()
        if "post" in operacoes
    ]
    assert caminhos, "a porta nao declarou operacao de escrita nenhuma"
    return caminhos


@pytest.mark.parametrize("caminho", _caminhos_de_leitura())
def test_sem_token_e_401_em_toda_leitura(caminho):
    assert pedir(caminho, token=None).status_code == 401


@pytest.mark.parametrize("caminho", _caminhos_de_leitura())
def test_token_errado_e_401_em_toda_leitura(caminho):
    assert pedir(caminho, token="token-de-outra-pessoa").status_code == 401


@pytest.mark.parametrize("caminho", _caminhos_de_leitura())
def test_conjuntos_vazios_recusam_todo_mundo(settings, caminho):
    """Env ausente ⇒ conjuntos vazios ⇒ ninguém entra. Fail-closed por
    construção. O modo de falha que isto mata: a célula sobe sem token no env e
    a porta fica ABERTA porque "não havia nada com que comparar"."""
    settings.TOKENS_SOMENTE_LEITURA = set()
    settings.TOKENS_PUBLICACAO = set()
    assert pedir(caminho).status_code == 401


@pytest.mark.parametrize("caminho", _caminhos_de_escrita())
@pytest.mark.parametrize(
    "token", [None, "token-de-outra-pessoa"], ids=["sem-token", "token-errado"]
)
def test_publicar_sem_credencial_e_401(caminho, token):
    assert (
        postar(caminho, {"site_id": SITE, "ordem": 1}, token=token).status_code == 401
    )


@pytest.mark.parametrize("caminho", _caminhos_de_escrita())
def test_conjuntos_vazios_tambem_recusam_a_escrita(settings, caminho):
    settings.TOKENS_SOMENTE_LEITURA = set()
    settings.TOKENS_PUBLICACAO = set()
    assert postar(caminho, {"site_id": SITE, "ordem": 1}).status_code == 401


# ---------------------------------------------------------------------------
# O GRAU A MAIS: quem só lê, só lê
# ---------------------------------------------------------------------------
def test_quem_so_le_leva_403_ao_tentar_publicar():
    """O guarda que justifica os dois conjuntos existirem.

    Um `TOKENS_ACEITOS` plano daria a QUALQUER par consumidor o poder de
    publicar a versão de uma sequência que escreve para alunos de verdade. 403
    e não 401: o crachá é válido, o que falta é o grau.
    """
    montar_o_cenario()
    resposta = postar(
        f"/jornadas/{SLUG}/textos",
        {
            "site_id": SITE,
            "ordem": 1,
            "idioma": "pt-br",
            "assunto_visivel": "a",
            "corpo": "b",
        },
        token=TOKEN_LEITURA,
    )
    assert resposta.status_code == 403


def test_quem_publica_TAMBEM_le_sem_estar_no_outro_conjunto():
    """A diferença deliberada em relação à `identidade`, onde o par precisa
    estar nos dois envs. O modo de falha que isto mata é chato e silencioso: o
    token de publicação entra no env, a tela lê tudo certo, e a primeira
    tentativa de salvar devolve 403 sem nada estar errado no código."""
    montar_o_cenario()
    assert pedir(f"/jornadas?site_id={SITE}", token=TOKEN_PUBLICACAO).status_code == 200


def test_a_porta_de_publicacao_sozinha_nao_abre_a_leitura_para_qualquer_um(settings):
    settings.TOKENS_SOMENTE_LEITURA = set()
    montar_o_cenario()
    assert pedir(f"/jornadas?site_id={SITE}", token=TOKEN_LEITURA).status_code == 401
    assert pedir(f"/jornadas?site_id={SITE}", token=TOKEN_PUBLICACAO).status_code == 200


# ---------------------------------------------------------------------------
# NADA DE DADO PESSOAL, E O GUARDA É SOBRE O SCHEMA
# ---------------------------------------------------------------------------
def test_nenhum_componente_da_porta_declara_dado_pessoal():
    """Não há como sabotar o cenário com um e-mail: esta célula não guarda um.

    Por isso o guarda mede o SCHEMA, que é onde o vazamento nasceria: alguém
    acrescenta `email` ou `nome` a um Schema no dia em que a tela pedir, e nada
    quebra. O `destinatario_id` é o id OPACO da plataforma, e quem precisar do
    nome pergunta à `identidade`, que é onde esse dado mora numa linha só.
    """
    from config.api import api

    proibidos = {"email", "e_mail", "nome", "telefone", "whatsapp", "cpf", "senha"}
    schema = api.get_openapi_schema(path_prefix="")
    for nome, componente in schema["components"]["schemas"].items():
        campos = set(componente.get("properties", {}))
        assert not (
            campos & proibidos
        ), f"{nome} declara dado pessoal: {campos & proibidos}"


def test_a_porta_responde_no_endereco_escolhido_e_nao_no_de_interno():
    """As dez células com porta usam dois formatos, e esta escolheu
    `/api/<celula>/` porque não serve página nenhuma sob prefixo público. Este
    guarda impede que alguém "padronize" o endereço para `/interno/` sem passar
    pelo Rito de Contrato do degrau 6d."""
    montar_o_cenario()
    assert pedir(f"/jornadas?site_id={SITE}").status_code == 200
    cabecalhos = {"HTTP_AUTHORIZATION": f"Bearer {TOKEN_LEITURA}"}
    assert Client().get("/interno/jornadas", **cabecalhos).status_code == 404


def test_o_healthz_continua_aberto_e_sem_cracha():
    """A sonda do compose não passa por Bearer nenhum: é ela que faz o processo
    auxiliar esperar o `migrate` terminar (ARMADILHAS §3.13)."""
    assert Client().get("/healthz").status_code == 200
