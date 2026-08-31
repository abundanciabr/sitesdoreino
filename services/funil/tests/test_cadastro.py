"""Fase 2 do PLANO-I18N — página de cadastro do meshcraft nos 3 idiomas.

Desde 31/08/2026 esta página deixou de ser captura de lead ("acompanhar as
novidades") e virou o pedido de entrada de quem não tem conta do Google: o
POST entra DIRETO na fila "Aguardando aprovação" da célula `alunos`
(`POST /pre-matriculas`, `createPreEnrollment`) — a mesma porta que o
cadastro à mão do admin e o pedido de entrada da Caixa já usam. Na mesma
submissão, a pessoa também escolhe a senha do segundo jeito de entrar
(`DECISAO-login-por-senha.md`), gravada via `IdentidadeClient.definir_senha`
— fail-CLOSED (decisão do mantenedor): se a senha não puder ser gravada, o
pedido inteiro vira 502, mesmo que o pedido de vaga já tenha ido.

Os 3 idiomas vêm do CATÁLOGO (fase 4: `conftest.SITE_MESH`, no formato do
contrato) — nada aqui monkeypatcha idioma. O catálogo (célula), a alunos e a
identidade entram só como contrato mockado (respx), com Host válido
(ARMADILHAS §4.6) e filtro por endpoint nas asserções de chamada (LICOES: o
CONV-SITE sempre bate no catálogo)."""

import json
from types import MappingProxyType

import httpx
import pytest
from django.template.loader import get_template
from django.test import RequestFactory
from django.utils.html import escape
from django.utils.translation import gettext, ngettext, override

from apps.core.views import FormularioDeCadastro
from apps.i18n import catalogo as cat
from apps.i18n.catalogo import t
from apps.i18n.validador import pseudo_do_catalogo, texto_hardcoded
from tests.conftest import ALUNOS, HOST_MESH, IDENTIDADE, SITE_MESH, caminho_mesh

IDIOMAS = ("en", "pt-br", "es")
TAGS = {"en": "en", "pt-br": "pt-BR", "es": "es"}

# Campos válidos de senha, para os testes que não são SOBRE a senha em si —
# evita repetir "8 caracteres, as duas iguais" em cada teste que só quer
# passar da validação.
SENHA_VALIDA = {"senha": "uma-senha-boa-123", "confirmar_senha": "uma-senha-boa-123"}


def _chamadas_a_pre_matriculas(rede):
    # LICOES: nunca "nenhuma chamada de rede" — o CONV-SITE sempre resolve o
    # site no catálogo; o que se afirma é sobre o ENDPOINT /pre-matriculas.
    return [c for c in rede.calls if "/pre-matriculas" in str(c.request.url)]


def _chamadas_a_definir_senha(rede):
    return [c for c in rede.calls if "/pessoas/definir-senha" in str(c.request.url)]


# ---------------------------------------------------------------------------
# Render nos 3 idiomas: title/meta/og e h1 no idioma certo, action prefixado.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("idioma", IDIOMAS)
def test_pagina_nos_3_idiomas_title_meta_e_action(client, rede, idioma):
    resp = client.get(caminho_mesh(idioma, "/cadastro"), HTTP_HOST=HOST_MESH)
    assert resp.status_code == 200
    conteudo = resp.content.decode()
    assert f'<html lang="{TAGS[idioma]}" dir="ltr">' in conteudo
    assert f"<title>{escape(t('cadastro.titulo', idioma))}</title>" in conteudo
    assert (
        f'<meta name="description" content="{escape(t("cadastro.meta_descricao", idioma))}">'
        in conteudo
    )
    assert (
        f'<meta property="og:title" content="{escape(t("cadastro.titulo", idioma))}">'
        in conteudo
    )
    assert f"<h1>{escape(t('cadastro.titulo_pagina', idioma))}</h1>" in conteudo
    # O form posta para a PRÓPRIA URL prefixada ({% url_i18n %}) — decisão da
    # maestro sobre a pendência 1 do PR #87.
    # O form posta para a PRÓPRIA URL pública da página — nua em inglês,
    # prefixada nos outros. É o {% url_i18n %} do template, e a asserção sai do
    # mesmo caminho_publico que ele usa.
    assert f'action="{caminho_mesh(idioma, "/cadastro")}"' in conteudo


# ---------------------------------------------------------------------------
# POST prefixado feliz: o pedido entra na fila "Aguardando aprovação".
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("idioma", IDIOMAS)
def test_post_feliz_entra_na_fila_aguardando_aprovacao(client, alunos_ligada, idioma):
    alunos_ligada.post(f"{ALUNOS}/pre-matriculas", name="pre_matricula").mock(
        return_value=httpx.Response(201, json={"id": "123", "status": "aguardando"})
    )
    resp = client.post(
        caminho_mesh(idioma, "/cadastro"),
        {
            "name": "Aluno Teste",
            "email": "aluno@exemplo.com",
            "whatsapp": "+5511900000000",
            **SENHA_VALIDA,
        },
        HTTP_HOST=HOST_MESH,
    )
    assert resp.status_code == 200
    assert escape(t("cadastro.sucesso", idioma)) in resp.content.decode()

    chamadas = _chamadas_a_pre_matriculas(alunos_ligada)
    assert len(chamadas) == 1
    enviado = json.loads(chamadas[0].request.content)
    assert enviado["site_id"] == SITE_MESH["id"]  # [INV-P11] do Host, não do payload
    assert enviado["email"] == "aluno@exemplo.com"
    assert enviado["nome_completo"] == "Aluno Teste"
    assert enviado["whatsapp"] == "+5511900000000"
    assert "source" not in enviado  # não é campo do contrato de pre-matriculas

    # A senha só é gravada DEPOIS do pedido de vaga dar certo.
    chamadas_senha = _chamadas_a_definir_senha(alunos_ligada)
    assert len(chamadas_senha) == 1
    enviado_senha = json.loads(chamadas_senha[0].request.content)
    assert enviado_senha["email"] == "aluno@exemplo.com"
    assert enviado_senha["senha"] == "uma-senha-boa-123"
    assert enviado_senha["site_id"] == SITE_MESH["id"]


# ---------------------------------------------------------------------------
# POST com erro de validação: mensagem do Django NO IDIOMA da página (o
# activate() da fase 1), e nenhum pedido sai.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("idioma", IDIOMAS)
def test_post_sem_email_erro_localizado_e_nenhuma_pre_matricula(
    client, alunos_ligada, idioma
):
    resp = client.post(
        caminho_mesh(idioma, "/cadastro"),
        {"name": "Sem E-mail", **SENHA_VALIDA},
        HTTP_HOST=HOST_MESH,
    )
    assert resp.status_code == 200
    with override(TAGS[idioma]):
        esperado = gettext("This field is required.")
    assert escape(esperado) in resp.content.decode()
    assert _chamadas_a_pre_matriculas(alunos_ligada) == []


def test_post_sem_whatsapp_erro_localizado_e_nenhuma_pre_matricula(
    client, alunos_ligada
):
    resp = client.post(
        "/pt-br/cadastro",
        {"name": "Aluno Teste", "email": "aluno@exemplo.com", **SENHA_VALIDA},
        HTTP_HOST=HOST_MESH,
    )
    assert resp.status_code == 200
    with override("pt-br"):
        esperado = gettext("This field is required.")
    assert escape(esperado) in resp.content.decode()
    assert _chamadas_a_pre_matriculas(alunos_ligada) == []


def test_post_email_invalido_erro_localizado_em_es(client, alunos_ligada):
    resp = client.post(
        "/es/cadastro",
        {
            "name": "Aluno",
            "email": "isto-nao-e-email",
            "whatsapp": "+34600000000",
            **SENHA_VALIDA,
        },
        HTTP_HOST=HOST_MESH,
    )
    assert resp.status_code == 200
    with override("es"):
        esperado = gettext("Enter a valid email address.")
    assert escape(esperado) in resp.content.decode()
    assert _chamadas_a_pre_matriculas(alunos_ligada) == []


# ---------------------------------------------------------------------------
# Senha (DECISAO-login-por-senha.md): obrigatória, mínimo 8, as duas batendo.
# ---------------------------------------------------------------------------
def test_post_sem_senha_erro_localizado_e_nenhuma_pre_matricula(client, alunos_ligada):
    resp = client.post(
        "/pt-br/cadastro",
        {
            "name": "Aluno Teste",
            "email": "aluno@exemplo.com",
            "whatsapp": "11900000000",
        },
        HTTP_HOST=HOST_MESH,
    )
    assert resp.status_code == 200
    with override("pt-br"):
        esperado = gettext("This field is required.")
    assert escape(esperado) in resp.content.decode()
    assert _chamadas_a_pre_matriculas(alunos_ligada) == []


def test_post_senha_curta_erro_localizado_e_nenhuma_pre_matricula(
    client, alunos_ligada
):
    resp = client.post(
        "/pt-br/cadastro",
        {
            "name": "Aluno Teste",
            "email": "aluno@exemplo.com",
            "whatsapp": "11900000000",
            "senha": "curta",
            "confirmar_senha": "curta",
        },
        HTTP_HOST=HOST_MESH,
    )
    assert resp.status_code == 200
    with override("pt-br"):
        # MinLengthValidator usa ngettext (singular/plural por limit_value) —
        # a mesma função que o próprio Django chama internamente, não uma
        # cópia da string à mão.
        esperado = ngettext(
            "Ensure this value has at least %(limit_value)d character (it has %(show_value)d).",
            "Ensure this value has at least %(limit_value)d characters (it has %(show_value)d).",
            8,
        ) % {"limit_value": 8, "show_value": 5}
    assert escape(esperado) in resp.content.decode()
    assert _chamadas_a_pre_matriculas(alunos_ligada) == []


def test_post_senhas_diferentes_mostra_erro_e_nenhuma_pre_matricula(
    client, alunos_ligada
):
    resp = client.post(
        "/pt-br/cadastro",
        {
            "name": "Aluno Teste",
            "email": "aluno@exemplo.com",
            "whatsapp": "11900000000",
            "senha": "uma-senha-boa-123",
            "confirmar_senha": "uma-senha-diferente-456",
        },
        HTTP_HOST=HOST_MESH,
    )
    assert resp.status_code == 200
    assert (
        escape(t("cadastro.erro_senhas_diferentes", "pt-br")) in resp.content.decode()
    )
    assert _chamadas_a_pre_matriculas(alunos_ligada) == []
    assert _chamadas_a_definir_senha(alunos_ligada) == []


# ---------------------------------------------------------------------------
# A senha não pôde ser gravada: fail-CLOSED (decisão do mantenedor) — o
# pedido inteiro vira 502, mesmo que o pedido de vaga já tenha ido.
# ---------------------------------------------------------------------------
def test_falha_ao_definir_senha_e_502_mesmo_com_vaga_registrada(client, alunos_ligada):
    alunos_ligada.post(f"{ALUNOS}/pre-matriculas", name="pre_matricula").mock(
        return_value=httpx.Response(201, json={"id": "123", "status": "aguardando"})
    )
    alunos_ligada.post(
        f"{IDENTIDADE}/pessoas/definir-senha", name="definir_senha"
    ).mock(return_value=httpx.Response(500))
    resp = client.post(
        "/pt-br/cadastro",
        {
            "name": "Aluno Teste",
            "email": "aluno@exemplo.com",
            "whatsapp": "11900000000",
            **SENHA_VALIDA,
        },
        HTTP_HOST=HOST_MESH,
    )
    assert resp.status_code == 502
    conteudo = resp.content.decode()
    assert escape(t("cadastro.erro_envio", "pt-br")) in conteudo
    assert 'value="aluno@exemplo.com"' in conteudo
    # O pedido de vaga TINHA ido — reenviar é seguro (entrar_na_fila é
    # idempotente por e-mail do lado da alunos), então o formulário não
    # some, só a senha não foi gravada.
    assert len(_chamadas_a_pre_matriculas(alunos_ligada)) == 1


# ---------------------------------------------------------------------------
# alunos fora do ar: 502 honesto (ARMADILHAS §4.9), mensagem localizada, e o
# que a pessoa digitou continua no formulário.
# ---------------------------------------------------------------------------
def test_alunos_fora_do_ar_e_502_localizado_preservando_o_form(client, alunos_ligada):
    alunos_ligada.post(f"{ALUNOS}/pre-matriculas", name="pre_matricula").mock(
        return_value=httpx.Response(500)
    )
    resp = client.post(
        "/pt-br/cadastro",
        {
            "name": "Aluno Teste",
            "email": "aluno@exemplo.com",
            "whatsapp": "11900000000",
            **SENHA_VALIDA,
        },
        HTTP_HOST=HOST_MESH,
    )
    assert resp.status_code == 502
    conteudo = resp.content.decode()
    assert escape(t("cadastro.erro_envio", "pt-br")) in conteudo
    assert 'value="aluno@exemplo.com"' in conteudo
    assert 'value="11900000000"' in conteudo
    # A senha nunca é gravada quando o pedido de vaga em si já falhou.
    assert _chamadas_a_definir_senha(alunos_ligada) == []


# ---------------------------------------------------------------------------
# Este e-mail já tem matrícula (409): nem sucesso, nem erro de envio — a
# tela explica em vez de fingir que recebeu um cadastro novo.
# ---------------------------------------------------------------------------
def test_post_ja_matriculado_mostra_aviso_sem_fingir_sucesso(client, alunos_ligada):
    alunos_ligada.post(f"{ALUNOS}/pre-matriculas", name="pre_matricula").mock(
        return_value=httpx.Response(409)
    )
    resp = client.post(
        "/pt-br/cadastro",
        {
            "name": "Aluno Teste",
            "email": "aluno@exemplo.com",
            "whatsapp": "11900000000",
            **SENHA_VALIDA,
        },
        HTTP_HOST=HOST_MESH,
    )
    assert resp.status_code == 200
    conteudo = resp.content.decode()
    assert escape(t("cadastro.erro_ja_matriculado", "pt-br")) in conteudo
    assert escape(t("cadastro.sucesso", "pt-br")) not in conteudo
    assert _chamadas_a_definir_senha(alunos_ligada) == []


# ---------------------------------------------------------------------------
# es noindex de fato (entrega 7): 200 + robots noindex + fora do hreflang.
# ---------------------------------------------------------------------------
def test_es_cadastro_serve_200_noindex_e_fora_do_hreflang(client, rede):
    conteudo = client.get("/es/cadastro", HTTP_HOST=HOST_MESH).content.decode()
    assert '<meta name="robots" content="noindex">' in conteudo
    # Fora do hreflang de ROBÔ (tag <link>); o seletor <a> continua listando
    # es — seletor é para gente, hreflang é para robô (fase 1).
    assert '<link rel="alternate" hreflang="es"' not in conteudo
    ptbr = client.get("/pt-br/cadastro", HTTP_HOST=HOST_MESH).content.decode()
    assert '<meta name="robots" content="noindex">' not in ptbr
    assert f'hreflang="pt-BR" href="https://{HOST_MESH}/pt-br/cadastro"' in ptbr


# ---------------------------------------------------------------------------
# Pseudo-locale (D8.4) nos DOIS templates novos: nenhum texto visível fora do
# catálogo. Dados de contexto (nome de produto, preço) entram como dígitos —
# são DADO, não copy; o detector deve enxergar só o template.
# ---------------------------------------------------------------------------
@pytest.fixture
def catalogo_pseudo(monkeypatch):
    chaves = pseudo_do_catalogo(dict(cat.catalogo_instalado()))
    monkeypatch.setattr(cat, "_CATALOGO", MappingProxyType(chaves))


def _request_pseudo(caminho):
    request = RequestFactory().get(caminho, HTTP_HOST=HOST_MESH)
    request.idioma = "qps"
    return request


def test_pseudo_locale_cadastro_sem_texto_hardcoded(catalogo_pseudo):
    html = get_template("funil/cadastro.html").render(
        {
            "form": FormularioDeCadastro(),
            "sucesso": True,
            "ja_matriculado": True,
            "erro_envio": True,
            "senhas_diferentes": True,
        },
        request=_request_pseudo("/qps/cadastro"),
    )
    assert texto_hardcoded(html) == []


@pytest.mark.parametrize(
    "erro", ["", "senha-invalida", "muitas-tentativas", "email-nao-verificado"]
)
def test_pseudo_locale_login_com_mini_form_de_senha_sem_texto_hardcoded(
    catalogo_pseudo, erro
):
    """login.html não tinha cobertura de pseudo-locale nenhuma antes do
    mini-formulário de senha (DECISAO-login-por-senha.md) — exercitado só
    por HTTP real (test_sessao_no_site.py), com os 3 idiomas de verdade,
    nunca com o catálogo trocado por dígitos. `token_de_senha` presente
    para o mini-formulário aparecer; uma amostra das chaves de recusa
    (as duas novas + uma antiga) para as duas gerações de erro_* conviverem
    no mesmo teste."""
    html = get_template("funil/login.html").render(
        {
            "url_de_entrada": "9",
            "url_de_entrada_por_senha": "9",
            "erro": erro,
            "destino": "9",
            "token_de_senha": "9",
        },
        request=_request_pseudo("/qps/login"),
    )
    assert texto_hardcoded(html) == []


class _AtorFalso:
    """Alguém entrou — o mínimo que a home e o cabeçalho de sessão leem.

    `nome` em dígitos pela mesma convenção do resto deste bloco: o detector
    procura LETRAS visíveis fora do catálogo, e nome de pessoa é DADO, não
    copy. `avisos_nao_lidos = None` é o "não sei" que apaga o sino — o sino
    tem os guardas dele em tests/test_sino.py.
    """

    nome = "123"
    avisos_nao_lidos = None


def test_pseudo_locale_home_de_visitante_sem_texto_hardcoded(catalogo_pseudo):
    html = get_template("funil/landing_i18n.html").render(
        {}, request=_request_pseudo("/qps/")
    )
    assert texto_hardcoded(html) == []


def test_pseudo_locale_home_de_quem_entrou_sem_texto_hardcoded(catalogo_pseudo):
    """O OUTRO ramo da home — o que a versão anterior deste teste não tinha.

    Enquanto a raiz era vitrine, ela mostrava a mesma página para todo mundo e
    um render só a cobria inteira. Desde 27/08/2026 ela tem dois ramos, e o de
    quem entrou é justamente o que ganhou texto novo (o aviso de novidade, o
    rótulo da Caixa). Um pseudo-locale que só varresse o ramo do visitante
    ficaria verde com uma string cravada no ramo de dentro.
    """
    pedido = _request_pseudo("/qps/")
    pedido.ator = _AtorFalso()
    pedido.url_da_caixa = "/forms/sugestoes/"

    html = get_template("funil/landing_i18n.html").render({}, request=pedido)

    assert texto_hardcoded(html) == []
