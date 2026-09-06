"""Guardas da PORTA da casa e da tela mínima (degrau 06, critério AC-05).

Quatro coisas se provam aqui, e cada uma tem um modo de falha silencioso:

1. **A porta é fail-CLOSED.** Quem não tem sessão, ou não tem matrícula ativa,
   não vê nada do portfólio. Cada teste de recusa afirma DUAS coisas: o estado
   certo, e que o conteúdo da Prancheta não saiu na resposta. Um teste que só
   olhasse o estado ficaria verde numa porta que devolvesse 403 com a página
   inteira dentro.

2. **Não conseguir perguntar nunca é "então pode entrar".** A `identidade`
   fora do ar, a `alunos` fora do ar e o env do par ausente fecham a porta. O
   último não é hipótese: é o estado da VPS enquanto o passo do mantenedor não
   roda, e é o único caso em que a porta se defende sozinha sem ninguém ter
   configurado nada.

3. **A célula NÃO assina sessão** ([INV-P12], `armadilhas/143`). O cookie
   viaja OPACO para a `identidade`, com o valor intacto, e nenhuma resposta
   desta casa grava `meshcraft_sessao`. O guarda de configuração está em
   `test_inv_pages_nao_assina_sessao.py`; este aqui mede o comportamento.

4. **A vitrine pública não passa pela porta.** `/estudio/<apelido>` é o link
   que o aluno manda ao cliente pagante, e uma porta escrita sem essa distinção
   a fecharia. A única prova disso, sem este teste, seria o cliente do aluno
   vendo um pedido de login.

A sonda (`/healthz`) e a porta de máquina (`/interno`) têm guarda próprio, e os
dois já estavam plantados antes desta porta existir:
`test_healthz_script_name.py` e `test_porta_de_maquina.py`. Este arquivo prova
que a porta não os atropela, e não os repete.
"""

from __future__ import annotations

import pytest
from django.test import Client

from apps.core.porta import (
    CAMINHOS_ISENTOS,
    PREFIXO_DA_PORTA_DE_MAQUINA,
    PREFIXO_PUBLICO_DA_VITRINE,
)

from tests.conftest import ANA, COOKIE, dublar_matricula, dublar_sessao

# O que só quem entrou pode ler. Escrito por extenso, e não lido do template:
# um teste que lesse a mesma fonte que o código passaria com o template vazio.
FRASE_DA_PRANCHETA = "Esta é a sua Prancheta"


def bater(caminho: str = "/", *, cookie: str | None = None):
    """Uma batida na porta, com ou sem cookie de sessão."""
    cabecalhos = {"HTTP_COOKIE": cookie} if cookie else {}
    return Client().get(caminho, **cabecalhos)


def texto(resposta) -> str:
    return resposta.content.decode("utf-8")


# ---------------------------------------------------------------------------
# 1. Fail-closed: quem não entrou não vê nada do portfólio
# ---------------------------------------------------------------------------
def test_sem_cookie_nenhum_a_prancheta_nao_responde(env_dos_pares, rede):
    resposta = bater()
    assert FRASE_DA_PRANCHETA not in texto(resposta)
    assert "Entre para ver a sua Prancheta" in texto(resposta)
    # E a porta não gastou uma ida à rede para receber "visitante".
    assert not rede.calls


def test_sessao_de_visitante_recebe_o_convite(env_dos_pares, rede):
    dublar_sessao(rede, {"autenticado": False})
    resposta = bater(cookie=COOKIE)
    assert resposta.status_code == 200
    assert FRASE_DA_PRANCHETA not in texto(resposta)
    assert "Entre para ver a sua Prancheta" in texto(resposta)


def test_quem_entrou_sem_matricula_ativa_recebe_403_e_a_frase_diz_isso(
    env_dos_pares, rede
):
    """`cadastrado` é gente da casa que ainda não é aluno. A porta fecha."""
    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"], "cadastrado")
    resposta = bater(cookie=COOKIE)
    assert resposta.status_code == 403
    assert FRASE_DA_PRANCHETA not in texto(resposta)
    assert "matrícula ativa" in texto(resposta)


# ---------------------------------------------------------------------------
# 2. Não conseguir perguntar nunca é "então pode entrar"
# ---------------------------------------------------------------------------
def test_a_identidade_fora_do_ar_fecha_a_porta(env_dos_pares, rede):
    dublar_sessao(rede, status=500)
    resposta = bater(cookie=COOKIE)
    assert resposta.status_code == 503
    assert FRASE_DA_PRANCHETA not in texto(resposta)
    assert "conferir o seu acesso" in texto(resposta)


def test_a_alunos_fora_do_ar_fecha_a_porta(env_dos_pares, rede):
    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"], status=500)
    resposta = bater(cookie=COOKIE)
    assert resposta.status_code == 503
    assert FRASE_DA_PRANCHETA not in texto(resposta)


def test_sem_o_env_do_par_a_porta_fecha_em_vez_de_abrir(monkeypatch, rede):
    """O estado da VPS enquanto o passo do mantenedor não roda.

    Nenhuma variável do par existe, então nem a pergunta chega a ser feita. A
    porta se fecha sozinha, sem ninguém ter configurado nada, e é isso que
    torna a recusa uma propriedade da construção e não de uma lembrança.
    """
    for chave in (
        "IDENTIDADE_API_URL",
        "IDENTIDADE_API_TOKEN",
        "ALUNOS_API_URL",
        "ALUNOS_API_TOKEN",
    ):
        monkeypatch.delenv(chave, raising=False)
    resposta = bater(cookie=COOKIE)
    assert resposta.status_code == 503
    assert FRASE_DA_PRANCHETA not in texto(resposta)
    assert not rede.calls


def test_sessao_autenticada_sem_email_nao_abre_a_porta(env_dos_pares, rede):
    """Resposta fora de forma: não dá para perguntar a matrícula de ninguém."""
    dublar_sessao(rede, {"autenticado": True, "id": "p_x", "nome_exibido": "X"})
    resposta = bater(cookie=COOKIE)
    assert resposta.status_code == 503
    assert FRASE_DA_PRANCHETA not in texto(resposta)


def test_a_recusa_temporaria_nao_fica_guardada_no_navegador(env_dos_pares, rede):
    """503 sem estas duas linhas pode ser cacheado, e o aluno continuaria
    vendo a recusa depois de a plataforma voltar."""
    dublar_sessao(rede, status=500)
    resposta = bater(cookie=COOKIE)
    assert resposta["Retry-After"] == "30"
    assert resposta["Cache-Control"] == "no-store"


# ---------------------------------------------------------------------------
# 3. A tela mínima, para quem passou
# ---------------------------------------------------------------------------
def test_o_aluno_com_matricula_ativa_ve_a_prancheta_e_o_proprio_nome(aluna):
    resposta = bater(cookie=COOKIE)
    assert resposta.status_code == 200
    assert FRASE_DA_PRANCHETA in texto(resposta)
    assert aluna["nome_exibido"] in texto(resposta)


def test_a_tela_nao_mostra_o_email_de_ninguem(aluna):
    """O e-mail serve para perguntar a matrícula, e é descartado depois."""
    assert aluna["email"] not in texto(bater(cookie=COOKIE))


# ---------------------------------------------------------------------------
# 4. [INV-P12] a célula repassa o cookie, e nunca o assina
# ---------------------------------------------------------------------------
def test_o_cookie_viaja_opaco_e_intacto_para_a_identidade(aluna, rede):
    bater(cookie=COOKIE)
    pedido = rede.calls[0].request
    assert pedido.headers["Cookie"] == COOKIE
    assert pedido.headers["Authorization"].startswith("Bearer ")


@pytest.mark.parametrize(
    "cenario",
    ["sem-cookie", "visitante", "sem-matricula", "aluno"],
)
def test_nenhuma_resposta_desta_casa_grava_o_cookie_do_site(
    env_dos_pares, rede, db, cenario
):
    """Se um dia esta célula assinar sessão, o site inteiro passa a deslogar
    sozinho, sem erro, sem log e sem alarme (`armadilhas/143`).

    O `db` entrou no degrau 07: o cenário `aluno` atravessa a porta e desenha a
    Prancheta, que desde então lê o roteiro da escola do banco.
    """
    if cenario == "visitante":
        dublar_sessao(rede, {"autenticado": False})
    elif cenario != "sem-cookie":
        dublar_sessao(rede, ANA)
        dublar_matricula(
            rede, ANA["email"], "aluno" if cenario == "aluno" else "cadastrado"
        )
    resposta = bater(cookie=None if cenario == "sem-cookie" else COOKIE)
    assert "meshcraft_sessao" not in resposta.cookies
    assert (
        "Set-Cookie" not in resposta or "meshcraft_sessao" not in resposta["Set-Cookie"]
    )


# ---------------------------------------------------------------------------
# 5. A vitrine pública é a exceção, e a exceção não é uma fresta
# ---------------------------------------------------------------------------
def test_a_vitrine_publica_nao_passa_pela_porta(env_dos_pares, rede):
    """`/estudio/<apelido>` é para um cliente que nunca vai entrar na
    plataforma. A tela dele nasce no degrau 13; o que se prova aqui é que a
    porta o deixa chegar ao urlconf em vez de pedir login.
    """
    resposta = bater("/estudio/ana-3d")
    assert (
        resposta.status_code == 404
    ), "a vitrine chegou ao urlconf, e ele ainda não tem a tela dela (degrau 13)"
    assert "Entre para ver a sua Prancheta" not in texto(resposta)
    assert not rede.calls, "a porta nem perguntou quem é: a vitrine é aberta"


def test_um_caminho_parecido_com_a_vitrine_nao_herda_a_isencao(env_dos_pares, rede):
    """Sem a barra na comparação, `/estudiosecreto` entraria de graça."""
    resposta = bater("/estudiosecreto")
    assert "Entre para ver a sua Prancheta" in texto(resposta)


def test_as_isencoes_da_porta_sao_exatamente_estas():
    """Igualdade EXATA, e não `in`: rota nova não escapa em silêncio.

    Ou ela está declarada aqui de propósito, ou a porta a protege. Um teste
    escrito com `in` deixaria passar a isenção que alguém acrescentasse com
    pressa.
    """
    assert CAMINHOS_ISENTOS == frozenset({"/healthz"})
    assert PREFIXO_DA_PORTA_DE_MAQUINA == "/interno"
    assert PREFIXO_PUBLICO_DA_VITRINE == "/estudio"
