"""A sessão é da `identidade`; a sala só REPASSA o cookie e pergunta.

Cada guarda daqui exerce a cadeia inteira (`quem_e` → cliente de verdade → rede
dublada pelo transporte), e a pergunta é sempre a mesma: **quando algo dá
errado, a pessoa recebe MENOS poder, nunca mais?** Reconhecimento falha
ABERTO (tropeço vira visitante, e a sala convida a entrar); a matrícula fica
para `test_acesso_pela_matricula.py`, onde a falha é FECHADA.

E o guarda de `armadilhas/143`, medido na RESPOSTA e não na intenção: nenhuma
resposta desta célula reescreve o cookie de sessão do site.
"""

from __future__ import annotations

import re
from pathlib import Path

import httpx
import pytest
from django.urls import reverse

from apps.core.sessao import quem_e
from apps.cursos.models import Pessoa

from tests.conftest import ANA, COOKIE, URL_DA_SESSAO, dublar_matricula, dublar_sessao

pytestmark = pytest.mark.django_db


class RequisicaoFalsa:
    """Só o que `quem_e` lê: o cabeçalho `Cookie` cru."""

    def __init__(self, cookie: str = COOKIE):
        self.META = {"HTTP_COOKIE": cookie} if cookie else {}


# ----------------------------------------------------- o cookie viaja opaco
def test_o_cookie_viaja_intacto_e_o_bearer_do_par_vai_junto(aluna, rede):
    """`getSessionFull`: o Bearer prova quem CHAMA; o cookie, repassado opaco,
    prova quem é a PESSOA. Os dois cabeçalhos, medidos na chamada real."""
    quem_e(RequisicaoFalsa())

    sessao = next(c.request for c in rede.calls if str(c.request.url) == URL_DA_SESSAO)
    assert sessao.headers["Cookie"] == COOKIE
    assert sessao.headers["Authorization"] == "Bearer token-cursos-para-identidade"


def test_a_pergunta_e_a_completa_porque_a_matricula_e_por_email(aluna, rede):
    """`/sessao/completa`, e não `/sessao`: é o e-mail que a `alunos` pede."""
    quem_e(RequisicaoFalsa())
    assert any(str(c.request.url) == URL_DA_SESSAO for c in rede.calls)


def test_sem_cookie_e_visitante_sem_tocar_a_rede(env_dos_pares, rede):
    ator = quem_e(RequisicaoFalsa(cookie=""))
    assert ator.autenticado is False
    assert rede.calls.call_count == 0


# ------------------------------------------------- reconhecimento falha aberto
def test_identidade_fora_do_ar_vira_visitante_e_nao_erro(env_dos_pares, rede):
    rede.get(URL_DA_SESSAO).mock(side_effect=httpx.ConnectError("caiu"))
    ator = quem_e(RequisicaoFalsa())
    assert ator.autenticado is False
    assert ator.eh_aluno is False


def test_identidade_fora_do_ar_a_sala_convida_a_entrar_e_nunca_500(
    env_dos_pares, rede, esqueleto, client
):
    rede.get(URL_DA_SESSAO).mock(side_effect=httpx.ConnectError("caiu"))
    resposta = client.get(reverse("curso", args=["profissional"]), HTTP_COOKIE=COOKIE)
    assert resposta.status_code == 200
    assert "Entre para ver o curso" in resposta.content.decode()


def test_identidade_respondendo_fora_do_contrato_vira_visitante(env_dos_pares, rede):
    dublar_sessao(rede, {"qualquer": "coisa"})
    assert quem_e(RequisicaoFalsa()).autenticado is False


def test_identidade_respondendo_200_sem_json_vira_visitante(env_dos_pares, rede):
    """2xx não é sucesso: um proxy devolvendo HTML com 200 não pode virar 500."""
    rede.get(URL_DA_SESSAO).mock(return_value=httpx.Response(200, text="<html>"))
    assert quem_e(RequisicaoFalsa()).autenticado is False


def test_identidade_respondendo_403_vira_visitante(env_dos_pares, rede):
    """403 é o degrau `TOKENS_COMPLETOS_CURSOS` ainda não instalado na
    identidade: a sala convida a entrar, e o log diz o motivo."""
    dublar_sessao(rede, status=403)
    assert quem_e(RequisicaoFalsa()).autenticado is False


def test_sessao_autenticada_sem_email_vira_visitante(env_dos_pares, rede):
    """Sem e-mail não dá para perguntar à `alunos`: fecha em vez de adivinhar."""
    dublar_sessao(rede, {"autenticado": True, "id": "x", "nome_exibido": "X"})
    assert quem_e(RequisicaoFalsa()).autenticado is False


@pytest.mark.parametrize("ausente", ["IDENTIDADE_API_URL", "IDENTIDADE_API_TOKEN"])
def test_env_do_par_ausente_vira_visitante_sem_custar_rede(
    env_dos_pares, rede, monkeypatch, ausente
):
    """`armadilhas/097`: env lido no ponto de uso, e desistir SEM tocar a rede."""
    monkeypatch.delenv(ausente)
    assert quem_e(RequisicaoFalsa()).autenticado is False
    assert rede.calls.call_count == 0


# ------------------------------------------------------------- o espelho
def test_a_pessoa_e_espelhada_pelo_id_opaco_e_nunca_pelo_email(aluna):
    ator = quem_e(RequisicaoFalsa())
    pessoa = Pessoa.objects.get()
    assert ator.pessoa == pessoa
    assert pessoa.id_da_plataforma == ANA["id"]
    assert pessoa.nome_exibido == "Ana"
    campos = {campo.name for campo in Pessoa._meta.get_fields()}
    assert "email" not in campos


def test_a_memoria_e_por_requisicao(aluna, rede):
    """Duas perguntas na MESMA requisição custam uma ida à identidade."""
    requisicao = RequisicaoFalsa()
    quem_e(requisicao)
    quem_e(requisicao)
    idas = [c for c in rede.calls if str(c.request.url) == URL_DA_SESSAO]
    assert len(idas) == 1


def test_o_papel_do_site_e_guardado_como_veio_e_nao_autoriza_nada(env_dos_pares, rede):
    """`papel: staff` não abre a sala: quem abre é a matrícula."""
    dublar_sessao(rede, {**ANA, "papel": "staff"})
    dublar_matricula(rede, ANA["email"], "cadastrado")
    ator = quem_e(RequisicaoFalsa())
    assert ator.papel_do_site == "staff"
    assert ator.eh_aluno is False


# -------------------------------------------- armadilhas/143, na RESPOSTA
def test_nenhuma_resposta_reescreve_o_cookie_de_sessao_do_site(
    aluna, aula_publicada, client
):
    """O guarda de `armadilhas/143`, medido na resposta e não na intenção."""
    for endereco in (
        reverse("curso", args=["profissional"]),
        reverse("aula-do-curso", args=["profissional", 1, "E00"]),
    ):
        resposta = client.get(endereco, HTTP_COOKIE=COOKIE)
        assert resposta.status_code == 200, endereco
        assert (
            "meshcraft_sessao" not in resposta.cookies
        ), f"{endereco} reescreveu o cookie de sessão do SITE"


def test_nenhum_arquivo_da_celula_toca_request_session():
    """Cinto e suspensório do [INV-P12]: além de não haver SessionMiddleware,
    nenhuma linha de código desta célula escreve ou lê `request.session`.

    A régua é um ACESSO (`request.session[…]`, `.get`, `=`), e não o nome:
    os comentários desta célula citam o nome justamente para dizer que ele é
    proibido."""
    raiz = Path(__file__).resolve().parents[1] / "apps"
    culpados = [
        str(arquivo.relative_to(raiz))
        for arquivo in raiz.rglob("*.py")
        if re.search(r"request\.session\s*[\[.=]", arquivo.read_text(encoding="utf-8"))
    ]
    assert culpados == [], culpados
