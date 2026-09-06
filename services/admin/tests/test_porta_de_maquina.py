"""Guardas da porta de MÁQUINA (`/interno`) da área administrativa.

Quatro coisas se provam aqui, e cada uma tem um modo de falha silencioso.

1. **O Bearer é o único cadeado.** Esta célula roda sob `SCRIPT_NAME=/admin` e o
   corte do prefixo é do Django, não do Traefik: `/interno` é alcançável pela
   borda pública em `meshcraft.top/admin/interno/...` (`armadilhas/186`). Se o
   401 sumir, nada quebra, nenhuma tela muda, e a lista de quem manda na escola
   passa a responder para a internet inteira. Por isso o guarda cobre o
   sem-token, o token errado E o conjunto de tokens vazio, que é o estado de uma
   VPS onde ninguém colou o env ainda. E cobre TODAS as operações, varrendo o
   próprio documento OpenAPI: operação nova nasce coberta, ou este arquivo
   reprova.

2. **A porta de GENTE não pode interceptar a porta de máquina.** O middleware
   fail-closed desta célula manda para o login quem chega sem cookie, e máquina
   não tem cookie: sem a isenção de `/interno`, o contrato congelado (401)
   viraria um 302 silencioso, e o consumidor leria um HTML de login como se
   fosse resposta.

3. **A resposta vem da lista EFETIVA, que é a soma das duas fontes.** Env mais
   tabela, normalizados dos dois lados, exatamente como a porta de gente decide
   quem entra. Um segundo jeito de responder "esta pessoa é administradora?"
   seria uma segunda resposta livre para discordar da primeira.

4. **Só sim ou não sai, e nada mais entra.** A resposta é conferida campo a
   campo, e não por "contém"; o corpo recusa campo desconhecido; e nenhum verbo
   além de POST responde, porque esta porta não escreve.
"""

from __future__ import annotations

import json

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db

TOKEN = "token-de-teste-do-par"
CAMINHO = "/interno/administradores/consultar"


@pytest.fixture(autouse=True)
def par_autorizado(settings):
    settings.TOKENS_ACEITOS = {TOKEN}
    settings.ADMIN_EMAILS = ""


def perguntar(email: str, token: str | None = TOKEN):
    cabecalhos = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
    return Client().post(
        CAMINHO,
        data=json.dumps({"email": email}),
        content_type="application/json",
        **cabecalhos,
    )


def corpo(resposta):
    return json.loads(resposta.content)


def operacoes_da_porta() -> list[tuple[str, str]]:
    """Toda operação que o documento OpenAPI vivo declara, (verbo, caminho).

    Varre o documento em vez de listar à mão: é isto que faz o guarda de 401
    valer para a operação que alguém acrescentar depois, sem depender de essa
    pessoa lembrar de vir aqui.
    """
    from config.api import api

    schema = api.get_openapi_schema(path_prefix="")
    return [
        (verbo, caminho)
        for caminho, item in schema["paths"].items()
        for verbo in item
        if verbo in {"get", "post", "put", "patch", "delete"}
    ]


# ---------------------------------------------------------------------------
# 1. O cadeado
# ---------------------------------------------------------------------------
def test_a_porta_tem_a_operacao_que_o_contrato_congelou_e_so_ela():
    """Sem esta linha, o guarda de 401 abaixo passaria com ZERO operações.

    Guarda varrendo lista vazia é verde que não mede nada (`armadilhas/351`):
    apagar a rota deixaria os testes de cadeado passando por falta de caso.
    """
    assert operacoes_da_porta() == [("post", "/administradores/consultar")]


@pytest.mark.parametrize("verbo,caminho", operacoes_da_porta())
def test_toda_operacao_recusa_quem_chega_sem_token(verbo, caminho):
    resposta = getattr(Client(), verbo)(f"/interno{caminho}")
    assert resposta.status_code == 401


@pytest.mark.parametrize("verbo,caminho", operacoes_da_porta())
def test_toda_operacao_recusa_token_errado(verbo, caminho):
    resposta = getattr(Client(), verbo)(
        f"/interno{caminho}", HTTP_AUTHORIZATION="Bearer token-de-outra-pessoa"
    )
    assert resposta.status_code == 401


@pytest.mark.parametrize("verbo,caminho", operacoes_da_porta())
def test_conjunto_de_tokens_vazio_recusa_todo_mundo(settings, verbo, caminho):
    """O estado de uma VPS onde o env ainda não foi colado: ninguém entra.

    É o caso que o desenho promete (fail-closed sem derrubar o boot) e o único
    em que um erro de digitação no nome da variável passaria despercebido: com o
    conjunto vazio, `token in set()` é falso para qualquer token.
    """
    settings.TOKENS_ACEITOS = set()
    resposta = getattr(Client(), verbo)(
        f"/interno{caminho}", HTTP_AUTHORIZATION=f"Bearer {TOKEN}"
    )
    assert resposta.status_code == 401


# ---------------------------------------------------------------------------
# 2. A porta de gente não vale aqui
# ---------------------------------------------------------------------------
def test_maquina_sem_cookie_nenhum_e_atendida_e_nao_mandada_para_o_login(settings):
    """Sem a isenção de `/interno`, o 401 do contrato viraria um 302 invisível.

    O middleware desta célula manda para o login quem chega sem cookie, e é
    exatamente isso que uma célula chamando por HTTP faz: nenhuma máquina tem
    cookie de navegador. O que este teste fixa é que a resposta é a do contrato.
    """
    settings.ADMIN_EMAILS = "dono@exemplo.com"
    resposta = perguntar("dono@exemplo.com")
    assert resposta.status_code == 200
    assert corpo(resposta) == {"e_administrador": True}


def test_sem_token_a_porta_de_maquina_responde_401_e_nunca_302():
    """A recusa é a do Bearer, e não a da porta de gente: 401, nunca redirecionar."""
    resposta = perguntar("dono@exemplo.com", token=None)
    assert resposta.status_code == 401
    assert "Location" not in resposta


# ---------------------------------------------------------------------------
# 3. A resposta vem da lista EFETIVA (env + tabela)
# ---------------------------------------------------------------------------
def test_quem_esta_no_env_do_servidor_e_administrador(settings):
    settings.ADMIN_EMAILS = "dono@exemplo.com,socio@exemplo.com"
    assert corpo(perguntar("socio@exemplo.com"))["e_administrador"] is True


def test_quem_a_tela_promoveu_tambem_e_administrador(settings):
    """A metade que o env NÃO conhece. Sem ela, promover pela tela não valeria nada."""
    from apps.core.models import Administrador

    settings.ADMIN_EMAILS = "dono@exemplo.com"
    Administrador.objects.create(email="professora@exemplo.com", ativo=True)
    assert corpo(perguntar("professora@exemplo.com"))["e_administrador"] is True


def test_quem_a_tela_removeu_deixa_de_ser_administrador(settings):
    """Remover é desativar (`DECISAO-administradores-e-apagar` §3.1), e a porta obedece."""
    from apps.core.models import Administrador

    settings.ADMIN_EMAILS = "dono@exemplo.com"
    Administrador.objects.create(email="ex-monitor@exemplo.com", ativo=False)
    assert corpo(perguntar("ex-monitor@exemplo.com"))["e_administrador"] is False


def test_o_cenario_tem_as_duas_fontes_com_gente_dentro_e_fora(settings):
    """Sem cenário com dente, trocar a soma por uma fonte só passaria despercebido.

    Aqui existe um administrador que SÓ o env conhece, um que SÓ a tabela
    conhece, um desativado e um estranho: qualquer uma das quatro respostas
    muda se a soma virar uma parcela (`armadilhas/351`).
    """
    from apps.core.models import Administrador

    settings.ADMIN_EMAILS = "dono@exemplo.com"
    Administrador.objects.create(email="professora@exemplo.com", ativo=True)
    Administrador.objects.create(email="ex-monitor@exemplo.com", ativo=False)

    assert corpo(perguntar("dono@exemplo.com"))["e_administrador"] is True
    assert corpo(perguntar("professora@exemplo.com"))["e_administrador"] is True
    assert corpo(perguntar("ex-monitor@exemplo.com"))["e_administrador"] is False
    assert corpo(perguntar("aluno@exemplo.com"))["e_administrador"] is False


def test_a_lista_vazia_responde_nao_para_todo_mundo(settings):
    """Env vazio e tabela vazia: a porta de gente fecha, e esta responde `false`."""
    settings.ADMIN_EMAILS = ""
    assert corpo(perguntar("dono@exemplo.com"))["e_administrador"] is False


def test_a_comparacao_normaliza_caixa_e_espaco_dos_dois_lados(settings):
    """Um espaço a mais no env trancaria o mantenedor para fora da própria escola."""
    settings.ADMIN_EMAILS = "  Dono@Exemplo.COM  "
    assert corpo(perguntar("  DONO@exemplo.com "))["e_administrador"] is True


def test_email_desconhecido_e_200_com_nao_e_nunca_404(settings):
    """404 diria a quem perguntou que aquele e-mail não existe na plataforma.

    Esta porta não responde essa pergunta, e a resposta para quem não é da
    equipe é a MESMA para quem existe e para quem não existe.
    """
    settings.ADMIN_EMAILS = "dono@exemplo.com"
    resposta = perguntar("ninguem-nunca-visto@exemplo.com")
    assert resposta.status_code == 200
    assert corpo(resposta) == {"e_administrador": False}


# ---------------------------------------------------------------------------
# 4. O que sai, o que entra, e o que a porta não faz
# ---------------------------------------------------------------------------
def test_a_resposta_tem_exatamente_um_campo(settings):
    """Campo a campo, e não "contém": nome, papel e id não atravessam a porta."""
    settings.ADMIN_EMAILS = "dono@exemplo.com"
    assert set(corpo(perguntar("dono@exemplo.com"))) == {"e_administrador"}


def test_campo_desconhecido_no_pedido_e_recusado(settings):
    """`additionalProperties: false` é contrato congelado, não gosto.

    Um consumidor que mande `{"email": ..., "site_id": ...}` achando que a porta
    filtra por site precisa descobrir isso na primeira chamada, e não meses
    depois ao notar que o campo nunca foi lido.
    """
    settings.ADMIN_EMAILS = "dono@exemplo.com"
    resposta = Client().post(
        CAMINHO,
        data=json.dumps({"email": "dono@exemplo.com", "papel": "professor"}),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {TOKEN}",
    )
    assert resposta.status_code == 422


def test_pedido_sem_email_e_recusado():
    resposta = Client().post(
        CAMINHO,
        data=json.dumps({}),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {TOKEN}",
    )
    assert resposta.status_code == 422


def test_a_porta_nao_escreve():
    """Nenhum verbo além de POST: quem promove e remove é o mantenedor, com sessão."""
    cliente = Client()
    for verbo in ("get", "put", "delete"):
        resposta = getattr(cliente, verbo)(
            CAMINHO, HTTP_AUTHORIZATION=f"Bearer {TOKEN}"
        )
        assert resposta.status_code == 405, verbo
