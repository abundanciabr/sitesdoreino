"""Guardas da porta de MÁQUINA (`/interno`) — e o que ela NUNCA pode responder.

A invariante desta porta é curta e é dura: **ela só fala de área PÚBLICA.**

Por que ela precisa de guarda próprio, e forte: a porta interna é a superfície
mais fácil de vazar do sistema, porque ninguém olha para ela. Não tem tela, não
tem link, não aparece no navegador de ninguém. Um `filter()` que alguém tire
numa refatoração não quebra página nenhuma — só passa a devolver, para quem
tiver o token, o conteúdo das áreas trancadas de uma escola de menores de idade.

Por isso o teste central aqui **sabota de verdade**: monta uma área de alunos e
uma de turma, com tópico e mensagem dentro, e exige que NADA delas apareça em
NENHUMA das três operações — nem título, nem contagem, nem existência.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest
from django.db import OperationalError
from django.test import Client
from django.utils import timezone

from apps.core.galeria import AREA_DA_GALERIA
from apps.forum.models import Area, ConsentimentoDaGaleria, Mensagem, Pessoa, Topico

pytestmark = pytest.mark.django_db

TOKEN = "token-de-teste-do-par"
# O par da Galeria tem um degrau A MAIS que o token comum: ele está nos dois
# conjuntos. Um par da casa que só tenha o token comum recebe 403 na porta da
# Galeria, e é essa diferença que o teste do 403 mede.
TOKEN_DA_GALERIA = "token-de-teste-do-par-da-galeria"

SITE = "site-da-escola"
OUTRO_SITE = "site-de-outra-escola"
HOST = "escola.exemplo"
TRABALHO = "https://www.roblox.com/games/123/meu-mundo"


@pytest.fixture(autouse=True)
def par_autorizado(settings):
    settings.TOKENS_ACEITOS = {TOKEN, TOKEN_DA_GALERIA}
    settings.TOKENS_DA_GALERIA = {TOKEN_DA_GALERIA}


@pytest.fixture
def autor():
    return Pessoa.objects.create(
        id_da_plataforma="p_ana", email="ana@exemplo.com", nome_exibido="Ana"
    )


def pedir(caminho: str, token: str | None = TOKEN):
    cabecalhos = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
    return Client().get(f"/interno{caminho}", **cabecalhos)


def corpo(resposta):
    return json.loads(resposta.content)


def montar_o_cenario(autor):
    """Uma área pública COM conteúdo, e duas trancadas TAMBÉM com conteúdo.

    As trancadas precisam ter conteúdo de verdade: uma área trancada vazia
    passaria no teste mesmo se o filtro sumisse — o teste ficaria verde
    provando nada. É a mesma armadilha do cenário fraco.
    """
    publica = Area.objects.create(
        slug="aberta", nome="Dúvidas gerais", visibilidade=Area.Visibilidade.PUBLICA
    )
    de_aluno = Area.objects.create(
        slug="trancada", nome="Só alunos", visibilidade=Area.Visibilidade.ALUNOS
    )
    de_turma = Area.objects.create(
        slug="turma-1",
        nome="Turma de janeiro",
        visibilidade=Area.Visibilidade.TURMA,
        curso_id="curso_x",
    )
    for area, titulo in [
        (publica, "Como faço um cubo"),
        (de_aluno, "SEGREDO DE ALUNO"),
        (de_turma, "SEGREDO DE TURMA"),
    ]:
        topico = Topico.objects.create(area=area, autor=autor, titulo=titulo)
        Mensagem.objects.create(topico=topico, autor=autor, texto=f"corpo de {titulo}")
    return publica, de_aluno, de_turma


# ---------------------------------------------------------------------------
# A INVARIANTE — a sabotagem
# ---------------------------------------------------------------------------
def test_area_trancada_NAO_vaza_por_nenhuma_das_tres_operacoes(autor):
    """**O guarda que justifica este arquivo existir.**

    Se este teste ficar verde com o conteúdo trancado aparecendo, a porta
    interna virou um buraco em volta de `permissoes.py`.
    """
    montar_o_cenario(autor)

    tudo = " ".join(
        pedir(c).content.decode() for c in ["/areas", "/topicos/recentes", "/resumo"]
    )

    for proibido in [
        "trancada",
        "Só alunos",
        "SEGREDO DE ALUNO",
        "turma-1",
        "Turma de janeiro",
        "SEGREDO DE TURMA",
    ]:
        assert proibido not in tudo, f"VAZOU conteúdo de área trancada: {proibido!r}"


def test_as_contagens_do_resumo_contam_so_o_publico(autor):
    """Contagem de área trancada é informação sobre área trancada.

    Este é o vazamento silencioso: nenhum título aparece, mas o número diz
    quantas conversas existem atrás da porta.
    """
    montar_o_cenario(autor)
    dados = corpo(pedir("/resumo"))

    assert dados == {
        "areas_publicas": 1,
        "topicos_publicos": 1,
        "mensagens_publicas": 1,
    }, "o resumo contou algo que não é público"


def test_o_cenario_do_teste_tem_dente(autor):
    """Prova que o cenário acima NÃO é fraco.

    Se as áreas trancadas não tivessem conteúdo, a sabotagem passaria mesmo
    com o filtro removido. Aqui se afirma que há, sim, o que vazar.
    """
    montar_o_cenario(autor)
    assert Area.objects.count() == 3
    assert Topico.objects.count() == 3
    assert Mensagem.objects.count() == 3


# ---------------------------------------------------------------------------
# A porta é fechada por padrão
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("caminho", ["/areas", "/topicos/recentes", "/resumo"])
def test_sem_token_e_401_em_toda_operacao(caminho):
    assert pedir(caminho, token=None).status_code == 401


@pytest.mark.parametrize("caminho", ["/areas", "/topicos/recentes", "/resumo"])
def test_token_errado_e_401_em_toda_operacao(caminho):
    assert pedir(caminho, token="token-de-outra-pessoa").status_code == 401


def test_conjunto_de_tokens_vazio_recusa_todo_mundo(settings):
    """Env ausente ⇒ conjunto vazio ⇒ ninguém entra. Fail-closed por construção.

    O modo de falha que isto mata: a célula sobe sem o token no env e a porta
    fica ABERTA porque "não havia nada com que comparar".
    """
    settings.TOKENS_ACEITOS = set()
    assert pedir("/areas").status_code == 401


# ---------------------------------------------------------------------------
# Nada de dado pessoal
# ---------------------------------------------------------------------------
def test_o_email_do_autor_nunca_sai(autor):
    montar_o_cenario(autor)
    tudo = " ".join(
        pedir(c).content.decode() for c in ["/areas", "/topicos/recentes", "/resumo"]
    )
    assert "ana@exemplo.com" not in tudo, "vazou e-mail"
    assert "p_ana" not in tudo, "vazou o id da plataforma"
    # O nome de exibição PODE sair: é o que já aparece na página pública.
    assert "Ana" in tudo


# ---------------------------------------------------------------------------
# O caminho feliz, e as bordas
# ---------------------------------------------------------------------------
def test_area_publica_desativada_some_da_porta(autor):
    publica, _, _ = montar_o_cenario(autor)
    publica.ativa = False
    publica.save(update_fields=["ativa"])
    assert corpo(pedir("/areas")) == []
    assert corpo(pedir("/resumo"))["areas_publicas"] == 0


def test_topico_nao_publicado_nao_aparece(autor):
    publica, _, _ = montar_o_cenario(autor)
    Topico.objects.filter(area=publica).update(estado=Topico.Estado.REMOVIDO)
    assert corpo(pedir("/topicos/recentes")) == []


def test_mensagem_removida_nao_entra_na_contagem(autor):
    montar_o_cenario(autor)
    Mensagem.objects.update(removida_em=timezone.now())
    assert corpo(pedir("/resumo"))["mensagens_publicas"] == 0


def test_forum_vazio_responde_200_com_lista_vazia_nunca_404():
    """404 obrigaria o consumidor a traduzir erro em "fórum vazio"."""
    assert pedir("/areas").status_code == 200
    assert corpo(pedir("/areas")) == []
    assert corpo(pedir("/resumo")) == {
        "areas_publicas": 0,
        "topicos_publicos": 0,
        "mensagens_publicas": 0,
    }


def test_o_limite_de_recentes_e_cortado_em_vez_de_recusado(autor):
    """Consumidor nenhum deve quebrar por pedir demais."""
    montar_o_cenario(autor)
    assert pedir("/topicos/recentes?limite=9999").status_code == 200
    assert pedir("/topicos/recentes?limite=0").status_code == 200
    assert pedir("/topicos/recentes?limite=-5").status_code == 200


# ===========================================================================
# A PORTA DA GALERIA — a única exceção desta superfície, e ela é estreita
# ===========================================================================
# `GET /galeria/candidatas/{pessoa_id}?site_id=...` é a única operação desta
# porta que fala de área TRANCADA, e existe porque o aluno pediu: ele marcou o
# próprio trabalho para aparecer na Galeria. Tudo o que a estreita está aqui,
# com o cenário forte que o resto do arquivo já exige — cada recusa é montada
# com material de verdade para vazar, nunca com o banco vazio.


@pytest.fixture
def galeria_ligada(monkeypatch):
    """O fórum sabe em que escola está: é o que a marcação guarda no gesto."""
    monkeypatch.setattr("apps.core.galeria.site_id_do_host", lambda host: SITE)


def area_de_mostrar():
    """A área da vitrine. Trancada, como toda área onde aluno escreve."""
    return Area.objects.create(
        slug=AREA_DA_GALERIA,
        nome="Mostre seu trabalho",
        visibilidade=Area.Visibilidade.ALUNOS,
        quem_escreve=Area.QuemEscreve.ALUNO,
    )


def trabalho(autor, area=None, *, titulo="Meu primeiro mundo"):
    topico = Topico.objects.create(
        area=area if area is not None else area_de_mostrar(),
        autor=autor,
        titulo=titulo,
    )
    Mensagem.objects.create(topico=topico, autor=autor, texto=f"corpo de {titulo}")
    return topico


def consentir(topico, autor, *, site_id=SITE):
    return ConsentimentoDaGaleria.objects.create(
        topico=topico,
        site_id=site_id,
        host_publico=HOST,
        referencia_url=TRABALHO,
        concedido_por=autor,
        concedido_em=timezone.now(),
    )


def pedir_candidatas(pessoa_id="p_ana", site_id=SITE, token=TOKEN_DA_GALERIA):
    return pedir(f"/galeria/candidatas/{pessoa_id}?site_id={site_id}", token=token)


# ---------------------------------------------------------------------------
# SEM CONSENTIMENTO NÃO HÁ CANDIDATA — a invariante desta operação
# ---------------------------------------------------------------------------
def test_sem_consentimento_o_trabalho_do_aluno_nao_e_candidata(autor):
    """O cenário é forte de propósito: o trabalho existe, publicado e do autor
    certo, na área certa, no site certo. Só falta o gesto dele. Se o filtro de
    consentimento sumir numa refatoração, este teste fica vermelho."""
    topico = trabalho(autor)

    assert corpo(pedir_candidatas()) == []
    assert Topico.objects.filter(pk=topico.pk).exists(), "cenário fraco"


def test_a_candidata_consentida_sai_inteira_e_na_forma_do_contrato(autor):
    topico = trabalho(autor)
    consentir(topico, autor)

    dados = corpo(pedir_candidatas())

    assert dados == [
        {
            "site_id": SITE,
            "topico_id": str(topico.pk),
            "titulo": "Meu primeiro mundo",
            "referencia": {
                "origem": "lista_permitida",
                "tipo": "link",
                "url": TRABALHO,
            },
            "url_canonica": f"https://{HOST}/forum/t/{topico.pk}",
        }
    ]


def test_consentimento_retirado_deixa_de_ser_candidata(autor):
    topico = trabalho(autor)
    marca = consentir(topico, autor)

    marca.revogado_em = timezone.now()
    marca.save(update_fields=["revogado_em"])

    assert corpo(pedir_candidatas()) == []


def test_candidata_de_outra_pessoa_nunca_sai_no_pedido_desta(autor):
    """O Bearer prova o serviço, nunca a pessoa. Quem confere a autoria da
    candidata é o fórum, e é isto que ele confere."""
    outro = Pessoa.objects.create(
        id_da_plataforma="p_bia", email="bia@exemplo.com", nome_exibido="Bia"
    )
    area = area_de_mostrar()
    consentir(trabalho(outro, area, titulo="TRABALHO DA BIA"), outro)
    consentir(trabalho(autor, area), autor)

    tudo = pedir_candidatas("p_ana").content.decode()

    assert "TRABALHO DA BIA" not in tudo
    assert "Meu primeiro mundo" in tudo


# ---------------------------------------------------------------------------
# ÁREA PRIVADA NUNCA APARECE NEM CONTA — nem por esta porta
# ---------------------------------------------------------------------------
def test_consentimento_em_outra_area_privada_nao_abre_aquela_area(autor):
    """O gesto do aluno vale para a vitrine, e só para ela.

    Uma marcação gravada num tópico de área de alunos ou de turma NÃO
    transforma aquela conversa em candidata: a exceção do contrato é a área
    `mostre-seu-trabalho`, não "qualquer área onde alguém marcou"."""
    de_aluno = Area.objects.create(
        slug="trancada", nome="Só alunos", visibilidade=Area.Visibilidade.ALUNOS
    )
    de_turma = Area.objects.create(
        slug="turma-1",
        nome="Turma de janeiro",
        visibilidade=Area.Visibilidade.TURMA,
        curso_id="curso_x",
    )
    consentir(trabalho(autor, de_aluno, titulo="SEGREDO DE ALUNO"), autor)
    consentir(trabalho(autor, de_turma, titulo="SEGREDO DE TURMA"), autor)

    tudo = pedir_candidatas().content.decode()

    assert corpo(pedir_candidatas()) == []
    for proibido in ["SEGREDO DE ALUNO", "SEGREDO DE TURMA", "trancada", "turma-1"]:
        assert proibido not in tudo, f"VAZOU área trancada pela Galeria: {proibido!r}"


def test_a_galeria_nao_muda_as_tres_operacoes_publicas(autor):
    """Consentir não torna o tópico público, e não o faz contar em lugar nenhum."""
    consentir(trabalho(autor), autor)

    tudo = " ".join(
        pedir(c).content.decode() for c in ["/areas", "/topicos/recentes", "/resumo"]
    )

    assert "Meu primeiro mundo" not in tudo
    assert AREA_DA_GALERIA not in tudo
    assert corpo(pedir("/resumo")) == {
        "areas_publicas": 0,
        "topicos_publicos": 0,
        "mensagens_publicas": 0,
    }


def test_conversa_fora_do_ar_ou_esperando_moderacao_nao_e_candidata(autor):
    """ "Moderados" é o estado PUBLICADO, e nada além dele."""
    topico = trabalho(autor)
    consentir(topico, autor)

    for estado in [Topico.Estado.ESPERANDO, Topico.Estado.REMOVIDO]:
        Topico.objects.filter(pk=topico.pk).update(estado=estado)
        assert corpo(pedir_candidatas()) == [], f"vazou em {estado}"


def test_area_da_vitrine_arquivada_some_da_galeria(autor):
    area = area_de_mostrar()
    consentir(trabalho(autor, area), autor)

    Area.objects.filter(pk=area.pk).update(ativa=False)

    assert corpo(pedir_candidatas()) == []


# ---------------------------------------------------------------------------
# OUTRO SITE NÃO VAZA — e a resposta não conta que ele existe
# ---------------------------------------------------------------------------
def test_candidata_de_outro_site_e_omitida_sem_virar_erro(autor):
    consentir(trabalho(autor), autor, site_id=OUTRO_SITE)

    resposta = pedir_candidatas(site_id=SITE)

    assert resposta.status_code == 200, "revelou a existência da candidata alheia"
    assert corpo(resposta) == []
    assert OUTRO_SITE not in resposta.content.decode()


def test_cada_candidata_repete_o_site_pedido(autor):
    area = area_de_mostrar()
    consentir(trabalho(autor, area), autor)
    consentir(
        trabalho(autor, area, titulo="DE OUTRA ESCOLA"), autor, site_id=OUTRO_SITE
    )

    dados = corpo(pedir_candidatas(site_id=SITE))

    assert [c["site_id"] for c in dados] == [SITE]
    assert dados[0]["titulo"] == "Meu primeiro mundo"


def test_site_vazio_no_pedido_nao_traz_nada(autor):
    """Pedido sem escola é pedido que ninguém pode responder com honestidade."""
    consentir(trabalho(autor), autor)
    assert corpo(pedir_candidatas(site_id="")) == []


# ---------------------------------------------------------------------------
# 401, 403 E 503 — os três de verdade, pela rede
# ---------------------------------------------------------------------------
def test_sem_bearer_a_porta_da_galeria_responde_401(autor):
    consentir(trabalho(autor), autor)
    assert pedir_candidatas(token=None).status_code == 401


def test_par_da_casa_sem_direito_a_galeria_recebe_403(autor):
    """O token vale para as três operações públicas e NÃO vale para esta.

    O 401 diria "não sei quem é você", o que seria mentira: o par é da casa. O
    403 é a resposta de autorização, e ela não conta se existe candidata."""
    consentir(trabalho(autor), autor)

    resposta = pedir_candidatas(token=TOKEN)

    assert resposta.status_code == 403
    assert "Meu primeiro mundo" not in resposta.content.decode()


def test_sem_par_autorizado_nenhum_a_porta_da_galeria_fecha(settings, autor):
    """Env ausente ⇒ conjunto vazio ⇒ 403 para todo mundo. Fail-closed."""
    settings.TOKENS_DA_GALERIA = set()
    consentir(trabalho(autor), autor)
    assert pedir_candidatas().status_code == 403


def test_fonte_muda_e_503_e_nunca_lista_vazia(monkeypatch, autor):
    """O 503 é distinto da lista vazia, e esta é a diferença que importa.

    Sem esta distinção, a Galeria mostraria "você ainda não tem trabalhos" para
    um aluno que tem — e o aluno acreditaria."""
    consentir(trabalho(autor), autor)
    assert corpo(pedir_candidatas()) != [], "cenário fraco: não havia o que devolver"

    class BancoMudo:
        def filter(self, *args, **kwargs):
            raise OperationalError("o banco do fórum não respondeu")

    monkeypatch.setattr(
        "apps.core.galeria.ConsentimentoDaGaleria",
        SimpleNamespace(objects=BancoMudo()),
    )

    resposta = pedir_candidatas()

    assert resposta.status_code == 503
    assert "Meu primeiro mundo" not in resposta.content.decode()


def test_a_porta_da_galeria_nao_devolve_dado_pessoal(autor):
    consentir(trabalho(autor), autor)

    tudo = pedir_candidatas().content.decode()

    assert "autor@exemplo.com" not in tudo, "vazou e-mail"
    assert "corpo de" not in tudo, "vazou o texto integral da conversa"
    # `pessoa_id` viaja no PEDIDO porque nomeia a única autora permitida; a
    # resposta não o repete (contrato).
    assert "p_ana" not in tudo


def test_pessoa_sem_candidata_recebe_lista_vazia_e_nunca_404(autor):
    assert pedir_candidatas("p_ninguem").status_code == 200
    assert corpo(pedir_candidatas("p_ninguem")) == []


# ---------------------------------------------------------------------------
# O GESTO DO ALUNO — marcar e desmarcar, com quem e quando
# ---------------------------------------------------------------------------
# O consentimento não nasce de configuração nem de gesto da escola: nasce da
# mão do dono do trabalho, na página dele. Estes testes atravessam a tela pela
# REDE, como o navegador dele atravessa.

COOKIE = "meshcraft_sessao=um-cookie-opaco-qualquer"

SESSAO_DA_ANA = {
    "autenticado": True,
    "id": "p_ana",
    "email": "autor@exemplo.com",
    "nome_exibido": "Ana",
}


@pytest.fixture
def escola_no_ar(monkeypatch):
    """O env mínimo das duas células vizinhas. Sem ele, tudo fecha."""
    for nome, valor in [
        ("IDENTIDADE_API_URL", "http://identidade:8000/interno"),
        ("IDENTIDADE_API_TOKEN", "tok-id"),
        ("ALUNOS_API_URL", "http://alunos:8000/api/alunos"),
        ("ALUNOS_API_TOKEN", "tok-al"),
        ("FORUM_PROFESSORES", ""),
        ("ADMIN_EMAILS", ""),
    ]:
        monkeypatch.setenv(nome, valor)


def como_a_ana(monkeypatch):
    """A `identidade` e a `alunos` dubladas: aluna matriculada, e nada além."""

    def falso_get(self, url, **kwargs):
        if "identidade" in str(url):
            return httpx.Response(200, json=SESSAO_DA_ANA)
        return httpx.Response(200, json={"categoria": "aluno"})

    monkeypatch.setattr(httpx.Client, "get", falso_get)


def navegar(caminho: str):
    return Client().get(caminho, headers={"cookie": COOKIE}, HTTP_HOST=HOST)


def gesto(topico, **campos):
    return Client().post(
        f"/t/{topico.pk}/galeria",
        campos,
        headers={"cookie": COOKIE},
        HTTP_HOST=HOST,
    )


@pytest.mark.usefixtures("escola_no_ar", "galeria_ligada")
def test_o_aluno_marca_o_trabalho_e_fica_registrado_quem_e_quando(monkeypatch, autor):
    como_a_ana(monkeypatch)
    topico = trabalho(autor)
    antes = timezone.now()

    resposta = gesto(topico, acao="mostrar", referencia=TRABALHO)

    assert resposta.status_code == 302
    marca = ConsentimentoDaGaleria.objects.get(topico=topico)
    assert marca.concedido_por_id == "p_ana", "não guardou QUEM consentiu"
    assert marca.concedido_em >= antes, "não guardou QUANDO consentiu"
    assert marca.revogado_em is None
    assert marca.site_id == SITE
    assert marca.referencia_url == TRABALHO
    assert corpo(pedir_candidatas())[0]["titulo"] == "Meu primeiro mundo"


@pytest.mark.usefixtures("escola_no_ar", "galeria_ligada")
def test_o_aluno_desmarca_e_a_candidata_some_sem_apagar_o_historico(monkeypatch, autor):
    como_a_ana(monkeypatch)
    topico = trabalho(autor)
    consentir(topico, autor)

    resposta = gesto(topico, acao="tirar")

    assert resposta.status_code == 302
    marca = ConsentimentoDaGaleria.objects.get(topico=topico)
    assert marca.revogado_em is not None, "desmarcar tem de ficar registrado"
    assert marca.concedido_por_id == "p_ana", "apagou quem havia consentido"
    assert corpo(pedir_candidatas()) == []


@pytest.mark.usefixtures("escola_no_ar", "galeria_ligada")
def test_o_primeiro_uso_mostra_a_caixa_vazia_e_o_que_fazer(monkeypatch, autor):
    como_a_ana(monkeypatch)
    topico = trabalho(autor)

    pagina = navegar(f"/t/{topico.pk}").content.decode()

    assert "Mostrar na Galeria" in pagina
    assert "Tirar da Galeria" not in pagina


@pytest.mark.usefixtures("escola_no_ar", "galeria_ligada")
def test_marcado_a_pagina_diz_quem_marcou_e_quando(monkeypatch, autor):
    como_a_ana(monkeypatch)
    topico = trabalho(autor)
    marca = consentir(topico, autor)

    pagina = navegar(f"/t/{topico.pk}").content.decode()

    assert "Tirar da Galeria" in pagina
    assert timezone.localtime(marca.concedido_em).strftime("%d/%m/%Y") in pagina


@pytest.mark.usefixtures("escola_no_ar", "galeria_ligada")
def test_o_aluno_nao_marca_a_conversa_de_outra_pessoa(monkeypatch, autor):
    """404, e não 403: o 403 confirmaria que a porta existe para este tópico."""
    como_a_ana(monkeypatch)
    outra = Pessoa.objects.create(
        id_da_plataforma="p_bia", email="bia@exemplo.com", nome_exibido="Bia"
    )
    topico = trabalho(outra)

    resposta = gesto(topico, acao="mostrar", referencia=TRABALHO)

    assert resposta.status_code == 404
    assert not ConsentimentoDaGaleria.objects.exists()
    assert "Mostrar na Galeria" not in navegar(f"/t/{topico.pk}").content.decode()


@pytest.mark.usefixtures("escola_no_ar", "galeria_ligada")
def test_endereco_fora_da_lista_permitida_e_recusado_com_recado(monkeypatch, autor):
    como_a_ana(monkeypatch)
    topico = trabalho(autor)

    resposta = gesto(topico, acao="mostrar", referencia="https://sitequalquer.com/eu")

    assert resposta.status_code == 400
    assert not ConsentimentoDaGaleria.objects.exists()
    recado = resposta.content.decode()
    assert "roblox.com" in recado, "o recado não diz o que fazer"


@pytest.mark.usefixtures("escola_no_ar", "galeria_ligada")
def test_endereco_sem_https_e_recusado(monkeypatch, autor):
    como_a_ana(monkeypatch)
    topico = trabalho(autor)

    resposta = gesto(topico, acao="mostrar", referencia="http://www.roblox.com/x")

    assert resposta.status_code == 400
    assert not ConsentimentoDaGaleria.objects.exists()


@pytest.mark.usefixtures("escola_no_ar", "galeria_ligada")
def test_endereco_em_branco_e_recusado_com_recado(monkeypatch, autor):
    como_a_ana(monkeypatch)
    topico = trabalho(autor)

    resposta = gesto(topico, acao="mostrar", referencia="   ")

    assert resposta.status_code == 400
    assert not ConsentimentoDaGaleria.objects.exists()


@pytest.mark.usefixtures("escola_no_ar")
def test_sem_saber_a_escola_o_gesto_e_recusado_em_vez_de_gravar_orfao(
    monkeypatch, autor
):
    """Catálogo mudo ⇒ `site_id` vazio. Gravar assim criaria uma candidata de
    escola nenhuma, e o banco recusa a linha. Quem recusa antes é a tela, com
    um recado que diz o que aconteceu."""
    como_a_ana(monkeypatch)
    monkeypatch.setattr("apps.core.galeria.site_id_do_host", lambda host: "")
    topico = trabalho(autor)

    resposta = gesto(topico, acao="mostrar", referencia=TRABALHO)

    assert resposta.status_code == 400
    assert not ConsentimentoDaGaleria.objects.exists()


@pytest.mark.usefixtures("escola_no_ar", "galeria_ligada")
def test_a_caixa_nao_aparece_em_conversa_fora_da_vitrine(monkeypatch, autor):
    como_a_ana(monkeypatch)
    duvidas = Area.objects.create(
        slug="duvidas",
        nome="Dúvidas gerais",
        visibilidade=Area.Visibilidade.ALUNOS,
        quem_escreve=Area.QuemEscreve.ALUNO,
    )
    topico = trabalho(autor, duvidas)

    assert "Mostrar na Galeria" not in navegar(f"/t/{topico.pk}").content.decode()
    assert gesto(topico, acao="mostrar", referencia=TRABALHO).status_code == 404


@pytest.mark.usefixtures("escola_no_ar", "galeria_ligada")
def test_visitante_sem_login_nao_alcanca_o_gesto(monkeypatch, autor):
    def sem_sessao(self, url, **kwargs):
        return httpx.Response(200, json={"autenticado": False})

    monkeypatch.setattr(httpx.Client, "get", sem_sessao)
    topico = trabalho(autor)

    assert gesto(topico, acao="mostrar", referencia=TRABALHO).status_code == 404
    assert not ConsentimentoDaGaleria.objects.exists()


@pytest.mark.usefixtures("escola_no_ar", "galeria_ligada")
def test_o_gesto_nao_acontece_por_GET(monkeypatch, autor):
    """Escrita por GET é escrita que um `<img src>` de fora dispara."""
    como_a_ana(monkeypatch)
    topico = trabalho(autor)

    assert navegar(f"/t/{topico.pk}/galeria").status_code == 405
    assert not ConsentimentoDaGaleria.objects.exists()


@pytest.mark.usefixtures("escola_no_ar", "galeria_ligada")
def test_imagem_de_dominio_permitido_sai_como_imagem(monkeypatch, autor):
    como_a_ana(monkeypatch)
    topico = trabalho(autor)
    imagem = "https://tr.rbxcdn.com/abc/meu-mundo.png"

    assert gesto(topico, acao="mostrar", referencia=imagem).status_code == 302

    assert corpo(pedir_candidatas())[0]["referencia"] == {
        "origem": "lista_permitida",
        "tipo": "imagem",
        "url": imagem,
    }


@pytest.mark.usefixtures("escola_no_ar", "galeria_ligada")
def test_endereco_no_proprio_forum_sai_com_origem_forum(monkeypatch, autor):
    como_a_ana(monkeypatch)
    topico = trabalho(autor)
    dentro_de_casa = f"https://{HOST}/forum/t/{topico.pk}"

    assert gesto(topico, acao="mostrar", referencia=dentro_de_casa).status_code == 302

    assert corpo(pedir_candidatas())[0]["referencia"]["origem"] == "forum"
