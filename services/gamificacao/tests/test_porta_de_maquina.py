"""Guardas da porta de MÁQUINA (`/api/gamificacao`) — e o que ela NUNCA devolve.

As invariantes desta porta são as três do cabeçalho de
`contracts/gamificacao.openapi.yaml`, e elas são curtas e duras:

1. **Nunca sai e-mail, nunca sai texto de pessoa.** O público desta escola é
   majoritariamente menor de idade.
2. **Nunca sai XP bruto de outra pessoa.** Placar de XP entre alunos não existe
   nesta plataforma, e é AQUI que isso fica mecânico.
3. **Slug, nunca frase pronta.** O site serve três idiomas.

Por que ela precisa de guarda próprio, e forte: a porta de máquina é a
superfície mais fácil de vazar do sistema, porque ninguém olha para ela. Não tem
tela, não tem link, não aparece no navegador de ninguém. Um campo a mais que
alguém acrescente num Schema não quebra página nenhuma — só passa a devolver,
para quem tiver o token, o e-mail e o XP dos alunos de uma escola de menores.

E nesta célula há um agravante que a `identidade` não tem: **a porta é
alcançável pela borda pública**. O `SCRIPT_NAME=/conquistas` é cortado pelo
Django, não pelo Traefik (`armadilhas/186`), então
`meshcraft.top/conquistas/api/gamificacao/perfis` chega aqui. O Bearer é o
único cadeado — por isso os testes de 401 cobrem as DUAS operações, o token
errado e o conjunto de tokens VAZIO.

Por isso o teste central **sabota de verdade**: monta uma pessoa com e-mail,
nome de exibição e um XP absurdo e inconfundível, e exige que NADA disso apareça
em `getPublicProfiles`. Um cenário sem esses dados passaria mesmo com o Schema
vazando — seria verde provando nada.
"""

from __future__ import annotations

import json
from datetime import timedelta

import httpx
import pytest
from django.test import Client
from django.utils import timezone

from apps.gamificacao.models import (
    MissaoDefinicao,
    NivelDefinicao,
    Pessoa,
    PerfilJogador,
    ProgressoDeMissao,
    Sequencia,
)

pytestmark = pytest.mark.django_db

TOKEN = "token-de-teste-do-par"
SITE = "site-da-escola"
BASE = "/api/gamificacao"

# A URL INTEIRA que esta célula tem direito de chamar, montada do `servers:` do
# contrato congelado da `identidade` mais o caminho da operação `getSession`.
# Escrita por extenso porque o dublê abaixo passa a EXIGI-LA: enquanto um dublê
# casa só `"identidade" in url`, um cliente que chame o caminho errado dá 404 em
# produção e verde na suíte — foi assim que um bug real atravessou 39 testes no
# fórum, em 29/08/2026.
URL_IDENTIDADE = "http://identidade:8000/interno/sessao"

# Os dados pessoais do cenário. Inconfundíveis de propósito: um `in` contra
# `"Ana"` acharia a substring em qualquer lugar, e o teste ficaria frouxo.
EMAIL = "ana-da-sabotagem@exemplo.com"
NOME = "Ana da Sabotagem"
ID_OPACO = "p_ana_opaco"
# Um XP que não aparece por acaso em contagem nenhuma.
XP_SECRETO = 987654


@pytest.fixture(autouse=True)
def par_autorizado(settings):
    settings.TOKENS_ACEITOS = {TOKEN}


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("SITE_ID", SITE)
    monkeypatch.setenv("IDENTIDADE_API_URL", "http://identidade:8000/interno")
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "tok-id")


@pytest.fixture(autouse=True)
def rede_proibida(monkeypatch):
    """Nenhum teste fala com a rede de verdade.

    Sem este dublê, um teste que esquecesse de dublar a `identidade` tentaria
    resolver `identidade:8000` e a suíte ficaria vermelha por motivo alheio —
    ou, pior, verde e lenta em quem tivesse um DNS que responde.
    """

    def proibido(self, url, **kwargs):
        raise AssertionError(f"chamada de rede não dublada: {url}")

    monkeypatch.setattr(httpx.Client, "get", proibido)


def dublar_identidade(monkeypatch, *, corpo=None, erro=None, status=200):
    """Troca `httpx.Client.get` por um dublê que EXIGE a URL inteira."""

    def falso(self, url, **kwargs):
        assert str(url) == URL_IDENTIDADE, f"URL fora do contrato: {url}"
        if erro is not None:
            raise erro
        return httpx.Response(
            status, json=corpo, request=httpx.Request("GET", str(url))
        )

    monkeypatch.setattr(httpx.Client, "get", falso)


def pedir(
    caminho: str,
    token: str | None = TOKEN,
    cookie: str | None = None,
    *,
    deixar_estourar: bool = True,
):
    """Uma chamada à porta.

    `deixar_estourar=False` faz o cliente devolver o 500 como RESPOSTA em vez de
    relançar a exceção. Só um teste usa: o que afirma que a porta responde 200
    mesmo com dado torto no banco. É `armadilhas/195` — sem isso, a sabotagem
    daquele guarda morreria na exceção e não na asserção, e o vermelho não
    provaria que a DECISÃO ("descartar, não estourar") mudou.
    """
    cabecalhos = {}
    if token:
        cabecalhos["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    if cookie:
        cabecalhos["HTTP_COOKIE"] = cookie
    cliente = Client(raise_request_exception=deixar_estourar)
    return cliente.get(f"{BASE}{caminho}", **cabecalhos)


def corpo(resposta):
    return json.loads(resposta.content)


def montar_o_cenario():
    """Uma pessoa COM dado pessoal e COM XP — o que existe para vazar.

    A pessoa precisa ter e-mail, nome e um XP alto de verdade: um cenário com
    os campos vazios passaria no teste de vazamento mesmo se o Schema
    devolvesse tudo. É a mesma armadilha do cenário fraco.
    """
    pessoa = Pessoa.objects.create(
        id_da_plataforma=ID_OPACO, email=EMAIL, nome_exibido=NOME
    )
    NivelDefinicao.objects.create(
        site_id=SITE, nivel=7, xp_necessario=900_000, titulo="Mestre de Ateliê"
    )
    NivelDefinicao.objects.create(
        site_id=SITE, nivel=8, xp_necessario=1_000_000, titulo="Mestre Maior"
    )
    perfil = PerfilJogador.objects.create(
        pessoa=pessoa,
        site_id=SITE,
        xp_total=XP_SECRETO,
        nivel=7,
        cristais_saldo=42,
    )
    return pessoa, perfil


# ---------------------------------------------------------------------------
# A INVARIANTE — a sabotagem
# ---------------------------------------------------------------------------
def test_perfis_publicos_NAO_vazam_dado_pessoal_nem_xp():
    """**O guarda que justifica este arquivo existir.**

    Se este teste ficar verde com e-mail ou XP na saída, a porta de máquina
    virou um placar de XP entre menores de idade — exatamente o que as
    invariantes 1 e 2 do contrato existem para impedir.
    """
    montar_o_cenario()

    saida = pedir(f"/perfis?ids={ID_OPACO}").content.decode()

    for proibido in [EMAIL, NOME, "ana-da-sabotagem", str(XP_SECRETO), "42"]:
        assert proibido not in saida, f"VAZOU dado que não é público: {proibido!r}"


def test_o_cenario_do_teste_tem_dente():
    """Prova que o cenário acima NÃO é fraco: há, sim, o que vazar."""
    pessoa, perfil = montar_o_cenario()
    assert pessoa.email == EMAIL and pessoa.nome_exibido == NOME
    assert perfil.xp_total == XP_SECRETO
    assert perfil.cristais_saldo == 42


def test_a_etiqueta_e_nivel_e_slug_e_nada_mais():
    montar_o_cenario()
    assert corpo(pedir(f"/perfis?ids={ID_OPACO}")) == {
        ID_OPACO: {"nivel": 7, "titulo_slug": "mestre-de-atelie"}
    }


def test_o_titulo_sai_como_SLUG_nunca_como_frase(monkeypatch):
    """Invariante 3: quem lê traduz o slug. Frase pronta congela o idioma.

    A asserção é dupla de propósito: o slug tem de estar lá E a frase com
    acento e maiúscula não pode estar. Só a primeira metade passaria se
    alguém devolvesse os dois campos.
    """
    montar_o_cenario()
    saida = pedir(f"/perfis?ids={ID_OPACO}").content.decode()
    assert "mestre-de-atelie" in saida
    assert "Mestre de Ateli" not in saida, "vazou a frase pronta do título"


# ---------------------------------------------------------------------------
# A falha desta porta é ABERTA, por contrato
# ---------------------------------------------------------------------------
def test_id_desconhecido_e_OMITIDO_nunca_erro_nem_linha_vazia():
    montar_o_cenario()
    resposta = pedir(f"/perfis?ids={ID_OPACO},p_nao_existe")
    assert resposta.status_code == 200
    dados = corpo(resposta)
    assert "p_nao_existe" not in dados, "id desconhecido virou linha no mapa"
    assert list(dados) == [ID_OPACO]


def test_ninguem_conhecido_responde_200_com_mapa_vazio():
    """404 obrigaria o consumidor a traduzir erro em "sem etiqueta"."""
    resposta = pedir("/perfis?ids=p_a,p_b")
    assert resposta.status_code == 200
    assert corpo(resposta) == {}


def test_perfil_de_OUTRO_site_nao_aparece():
    """Lei 9 — uma fábrica, N lojas. A etiqueta é do site desta instalação."""
    montar_o_cenario()
    outra = Pessoa.objects.create(
        id_da_plataforma="p_de_outra_loja", email="b@exemplo.com"
    )
    # NÍVEL 7 de propósito, o mesmo do cenário: se este perfil tivesse um nível
    # sem `NivelDefinicao` neste site, ele sumiria do mapa pelo filtro de
    # TÍTULO, e o teste ficaria verde mesmo com o filtro de SITE removido —
    # cenário fraco medindo a defesa errada.
    PerfilJogador.objects.create(pessoa=outra, site_id="outro-site", nivel=7)

    dados = corpo(pedir(f"/perfis?ids={ID_OPACO},p_de_outra_loja"))
    assert list(dados) == [ID_OPACO], "vazou perfil de outro site"


def test_nivel_sem_definicao_some_do_mapa_em_vez_de_devolver_titulo_vazio():
    """String vazia seria mentira: "existe título, é vazio"."""
    pessoa = Pessoa.objects.create(id_da_plataforma="p_orfa", email="o@exemplo.com")
    PerfilJogador.objects.create(pessoa=pessoa, site_id=SITE, nivel=99)
    assert corpo(pedir("/perfis?ids=p_orfa")) == {}


def test_mais_de_50_ids_e_CORTADO_no_teto_nunca_recusado():
    """Consumidor nenhum deve quebrar por pedir demais."""
    for n in range(60):
        pessoa = Pessoa.objects.create(
            id_da_plataforma=f"p{n:03d}", email=f"a{n}@exemplo.com"
        )
        PerfilJogador.objects.create(pessoa=pessoa, site_id=SITE, nivel=1)
    NivelDefinicao.objects.create(
        site_id=SITE, nivel=1, xp_necessario=0, titulo="Aprendiz"
    )

    ids = ",".join(f"p{n:03d}" for n in range(60))
    resposta = pedir(f"/perfis?ids={ids}")
    assert resposta.status_code == 200
    assert len(corpo(resposta)) == 50, "o teto de 50 do contrato não foi respeitado"


def test_ids_vazio_ou_so_virgulas_responde_200_com_mapa_vazio():
    montar_o_cenario()
    assert corpo(pedir("/perfis?ids=")) == {}
    assert corpo(pedir("/perfis?ids=,,,")) == {}


def test_sem_SITE_ID_no_env_a_porta_fica_sem_etiqueta_e_nao_quebra(monkeypatch):
    """Falha ABERTA: página sem selo, nunca página quebrada.

    E é justamente a falha que se esconde melhor — por isso ela também grita no
    log (`apps/core/sessao.py::site_atual`).
    """
    montar_o_cenario()
    monkeypatch.delenv("SITE_ID")
    resposta = pedir(f"/perfis?ids={ID_OPACO}")
    assert resposta.status_code == 200
    assert corpo(resposta) == {}


# ---------------------------------------------------------------------------
# `getMyStatus` — 200 SEMPRE, e o conteúdo é do dono da sessão
# ---------------------------------------------------------------------------
VISITANTE = {
    "autenticado": False,
    "xp": None,
    "nivel": None,
    "xp_para_proximo": None,
    "sequencia": None,
    "cristais": None,
    "missoes": [],
    "celebracoes_pendentes": [],
}


def test_visitante_recebe_200_com_autenticado_false_nunca_401():
    """Obrigar o consumidor a traduzir 401 em "ninguém logado" faria o widget
    da home mostrar tela de erro para quem só não entrou ainda."""
    resposta = pedir("/eu")
    assert resposta.status_code == 200
    assert corpo(resposta) == VISITANTE


def test_o_dono_da_sessao_ve_o_proprio_xp(monkeypatch):
    montar_o_cenario()
    dublar_identidade(monkeypatch, corpo={"autenticado": True, "id": ID_OPACO})

    dados = corpo(pedir("/eu", cookie="meshcraft_sessao=abc"))
    assert dados["autenticado"] is True
    assert dados["xp"] == XP_SECRETO
    assert dados["nivel"] == 7
    assert dados["cristais"] == 42
    # 1.000.000 do nível 8 menos os 987.654 que ela já tem.
    assert dados["xp_para_proximo"] == 12_346


def test_no_topo_da_escada_o_que_falta_e_null_e_nao_zero(monkeypatch):
    """`None` e `0` dizem coisas diferentes, e o contrato aceita os dois.

    `0` é "está a um passo"; `None` é "não há próximo degrau". Quem desenha a
    barra precisa distinguir para não mostrar barra cheia que nunca vira nada.
    """
    montar_o_cenario()
    NivelDefinicao.objects.filter(site_id=SITE, nivel=8).delete()
    dublar_identidade(monkeypatch, corpo={"autenticado": True, "id": ID_OPACO})
    assert corpo(pedir("/eu", cookie="meshcraft_sessao=abc"))["xp_para_proximo"] is None


def test_quem_entrou_mas_ainda_nao_jogou_e_autenticado_com_numeros_em_null(
    monkeypatch,
):
    """A linha de perfil é PREGUIÇOSA (Lei 7): nasce no primeiro XP."""
    dublar_identidade(monkeypatch, corpo={"autenticado": True, "id": "p_novata"})
    dados = corpo(pedir("/eu", cookie="meshcraft_sessao=abc"))
    assert dados == {**VISITANTE, "autenticado": True}


def test_a_sequencia_sao_os_quatro_numeros_do_contrato_e_mais_nada(monkeypatch):
    montar_o_cenario()
    Sequencia.objects.create(
        pessoa_id=ID_OPACO,
        site_id=SITE,
        semana_corrente=timezone.localdate(),
        meta_dias=5,
        dias_ativos_na_semana=3,
        semanas_atuais=11,
        recorde_semanas=11,
        escudos=1,
    )
    dublar_identidade(monkeypatch, corpo={"autenticado": True, "id": ID_OPACO})

    assert corpo(pedir("/eu", cookie="meshcraft_sessao=abc"))["sequencia"] == {
        "semanas": 11,
        "dias_da_semana": 3,
        "meta": 5,
        "escudos": 1,
    }


def test_as_missoes_sao_as_da_JANELA_CORRENTE(monkeypatch):
    """Diária de HOJE e semanal desta semana. A janela velha não volta."""
    montar_o_cenario()
    hoje = timezone.localdate()
    segunda = hoje - timedelta(days=hoje.weekday())
    diaria = MissaoDefinicao.objects.create(
        site_id=SITE,
        slug="a-diaria",
        nome="A diária",
        cadencia=MissaoDefinicao.Cadencia.DIARIA,
        categoria=MissaoDefinicao.Categoria.CRIAR,
        meta=3,
    )
    semanal = MissaoDefinicao.objects.create(
        site_id=SITE,
        slug="b-semanal",
        nome="A encomenda",
        cadencia=MissaoDefinicao.Cadencia.SEMANAL,
        categoria=MissaoDefinicao.Categoria.MOSTRAR,
        meta=1,
    )
    ProgressoDeMissao.objects.create(
        pessoa_id=ID_OPACO, site_id=SITE, missao=diaria, janela=hoje, progresso=2
    )
    ProgressoDeMissao.objects.create(
        pessoa_id=ID_OPACO,
        site_id=SITE,
        missao=semanal,
        janela=segunda,
        progresso=1,
        cumprida_em=timezone.now(),
    )
    # A janela velha: mesma missão, semana passada. NÃO pode aparecer.
    ProgressoDeMissao.objects.create(
        pessoa_id=ID_OPACO,
        site_id=SITE,
        missao=diaria,
        janela=hoje - timedelta(days=8),
        progresso=3,
    )
    dublar_identidade(monkeypatch, corpo={"autenticado": True, "id": ID_OPACO})

    assert corpo(pedir("/eu", cookie="meshcraft_sessao=abc"))["missoes"] == [
        {
            "slug": "a-diaria",
            "cadencia": "diaria",
            "categoria": "criar",
            "progresso": 2,
            "meta": 3,
            "cumprida": False,
        },
        {
            "slug": "b-semanal",
            "cadencia": "semanal",
            "categoria": "mostrar",
            "progresso": 1,
            "meta": 1,
            "cumprida": True,
        },
    ]


def test_celebracao_fora_de_forma_e_DESCARTADA_nunca_vira_500(monkeypatch):
    """O campo é `JSONField` livre e quem escreve nele ainda vai nascer.

    Deixar uma linha torta atravessar transformaria o dado errado de UMA pessoa
    em HTTP 500 para quem chama — numa porta cuja falha é aberta por contrato.
    """
    _, perfil = montar_o_cenario()
    perfil.celebracoes_pendentes = [
        {"tipo": "nivel-alcancado", "referencia": "7"},
        {"tipo": "invencao-do-motor", "referencia": "x"},
        {"tipo": "marco-validado"},
        "isto nem e um dicionario",
        {"tipo": "conquista-concedida", "referencia": "primeiro-ugc"},
    ]
    perfil.save(update_fields=["celebracoes_pendentes"])
    dublar_identidade(monkeypatch, corpo={"autenticado": True, "id": ID_OPACO})

    resposta = pedir("/eu", cookie="meshcraft_sessao=abc", deixar_estourar=False)
    assert resposta.status_code == 200, "dado torto de UMA pessoa virou 500 para todos"
    assert corpo(resposta)["celebracoes_pendentes"] == [
        {"tipo": "nivel-alcancado", "referencia": "7"},
        {"tipo": "conquista-concedida", "referencia": "primeiro-ugc"},
    ]


def test_o_email_nunca_sai_nem_no_proprio_painel(monkeypatch):
    """A invariante 1 vale nas DUAS operações, não só na pública."""
    montar_o_cenario()
    dublar_identidade(monkeypatch, corpo={"autenticado": True, "id": ID_OPACO})
    saida = pedir("/eu", cookie="meshcraft_sessao=abc").content.decode()
    assert EMAIL not in saida
    assert NOME not in saida


# ---------------------------------------------------------------------------
# Reconhecer não é autorizar: falhar devolve MENOS, nunca outra pessoa
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "avaria",
    [
        {"erro": httpx.ConnectError("recusou")},
        {"status": 503, "corpo": {}},
        {"corpo": {"autenticado": False}},
        {"corpo": {"autenticado": True}},  # autenticado sem id: fora de forma
    ],
    ids=["rede-caiu", "http-503", "visitante", "sem-id"],
)
def test_identidade_avariada_devolve_VISITANTE_nunca_o_painel_de_alguem(
    monkeypatch, avaria
):
    montar_o_cenario()
    dublar_identidade(
        monkeypatch,
        corpo=avaria.get("corpo"),
        erro=avaria.get("erro"),
        status=avaria.get("status", 200),
    )
    resposta = pedir("/eu", cookie="meshcraft_sessao=abc")
    assert resposta.status_code == 200
    assert corpo(resposta) == VISITANTE


def test_sem_env_da_identidade_a_porta_fecha_em_visitante_e_nao_derruba(monkeypatch):
    """`armadilhas/097`: env ausente não pode virar HTTP 500 em toda página."""
    montar_o_cenario()
    monkeypatch.delenv("IDENTIDADE_API_TOKEN")
    resposta = pedir("/eu", cookie="meshcraft_sessao=abc")
    assert resposta.status_code == 200
    assert corpo(resposta) == VISITANTE


# ---------------------------------------------------------------------------
# A porta é fechada por padrão — e o Bearer é o ÚNICO cadeado
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("caminho", ["/perfis?ids=p_a", "/eu"])
def test_sem_token_e_401_em_toda_operacao(caminho):
    assert pedir(caminho, token=None).status_code == 401


@pytest.mark.parametrize("caminho", ["/perfis?ids=p_a", "/eu"])
def test_token_errado_e_401_em_toda_operacao(caminho):
    assert pedir(caminho, token="token-de-outra-pessoa").status_code == 401


@pytest.mark.parametrize("caminho", ["/perfis?ids=p_a", "/eu"])
def test_conjunto_de_tokens_vazio_recusa_todo_mundo(settings, caminho):
    """Env ausente ⇒ conjunto vazio ⇒ ninguém entra. Fail-closed por construção.

    O modo de falha que isto mata: a célula sobe sem o token no env e a porta
    fica ABERTA porque "não havia nada com que comparar". Nesta célula ele é
    pior que nas vizinhas — sem token válido, `meshcraft.top/conquistas/api/…`
    seria uma porta aberta na internet (`armadilhas/186`).
    """
    settings.TOKENS_ACEITOS = set()
    assert pedir(caminho).status_code == 401


def test_a_porta_responde_no_endereco_do_CONTRATO_e_nao_no_da_genese():
    """O contrato congelou `/api/gamificacao`; a gênese previa `/interno`.

    O cabeçalho do contrato registra a divergência e a resolve a favor do
    contrato. Este guarda impede que alguém "conserte" o endereço para casar
    com o comentário antigo — o que quebraria todo consumidor calado.
    """
    montar_o_cenario()
    assert pedir(f"/perfis?ids={ID_OPACO}").status_code == 200
    cabecalhos = {"HTTP_AUTHORIZATION": f"Bearer {TOKEN}"}
    assert Client().get("/interno/perfis", **cabecalhos).status_code == 404
