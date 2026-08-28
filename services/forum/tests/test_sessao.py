"""Guardas do reconhecimento — o caminho de REDE, que é onde mora o fail-closed.

**Este arquivo nasceu de uma falha do próprio processo, em 28/08/2026.** A
suíte já tinha 39 testes verdes e nenhum deles chamava `quem_e()`: todos
montavam o `Ator` à mão. Uma sabotagem deliberada — *"não conseguir conferir a
matrícula vira 'é aluno'"* — **passou nos 39**. O guarda que importa não
existia; existia só a confiança de que existia.

Cada teste daqui exerce a cadeia inteira com a rede dublada, e a pergunta é
sempre a mesma: **quando algo dá errado, a pessoa recebe MENOS poder, nunca
mais?**
"""

import httpx
import pytest

from apps.core.sessao import CATEGORIA_ALUNO, quem_e
from apps.forum.models import Pessoa

pytestmark = pytest.mark.django_db

SESSAO_OK = {
    "autenticado": True,
    "id": "p_ana",
    "email": "ana@exemplo.com",
    "nome_exibido": "Ana",
}


class RequisicaoFalsa:
    """Só o que `quem_e` lê: o cabeçalho `Cookie` cru."""

    def __init__(self, cookie: str = "meshcraft_sessao=abc"):
        self.META = {"HTTP_COOKIE": cookie} if cookie else {}


@pytest.fixture
def env(monkeypatch):
    for nome, valor in [
        ("IDENTIDADE_API_URL", "http://identidade:8000/interno"),
        ("IDENTIDADE_API_TOKEN", "tok-id"),
        ("ALUNOS_API_URL", "http://alunos:8000/api/alunos"),
        ("ALUNOS_API_TOKEN", "tok-al"),
        ("FORUM_PROFESSORES", ""),
        ("ADMIN_EMAILS", ""),
    ]:
        monkeypatch.setenv(nome, valor)


def dublar(monkeypatch, *, identidade=None, alunos=None):
    """Troca `httpx.Client.get` por um dublê que responde por URL.

    Cada parâmetro é uma `httpx.Response` OU uma exceção a levantar. `None`
    significa "esta chamada não deveria acontecer" — e se acontecer, quebra.
    """

    def falso_get(self, url, **kwargs):
        alvo = identidade if "identidade" in str(url) else alunos
        if alvo is None:
            raise AssertionError(f"chamada inesperada a {url}")
        if isinstance(alvo, Exception):
            raise alvo
        return alvo

    monkeypatch.setattr(httpx.Client, "get", falso_get)


def resposta(corpo, status=200):
    return httpx.Response(status, json=corpo)


# ------------------------------------------------------------------ visitante
def test_sem_cookie_e_visitante_sem_tocar_a_rede(env, monkeypatch):
    dublar(monkeypatch)  # qualquer chamada quebraria o teste
    ator = quem_e(RequisicaoFalsa(cookie=""))
    assert ator.autenticado is False


def test_identidade_fora_do_ar_vira_visitante_e_nao_erro(env, monkeypatch):
    """Reconhecimento falha ABERTO — a área pública continua legível."""
    dublar(monkeypatch, identidade=httpx.ConnectError("caiu"))
    ator = quem_e(RequisicaoFalsa())
    assert ator.autenticado is False
    assert ator.eh_aluno is False


def test_identidade_respondendo_fora_do_contrato_vira_visitante(env, monkeypatch):
    """`200` com corpo que não é do contrato não pode virar sessão válida."""
    dublar(monkeypatch, identidade=resposta({"qualquer": "coisa"}))
    assert quem_e(RequisicaoFalsa()).autenticado is False


def test_sessao_autenticada_sem_email_vira_visitante(env, monkeypatch):
    """Sem e-mail não dá para perguntar à `alunos` — fecha em vez de adivinhar."""
    dublar(monkeypatch, identidade=resposta({"autenticado": True, "id": "x"}))
    assert quem_e(RequisicaoFalsa()).autenticado is False


# ------------------------------------------------------- o guarda que faltava
def test_alunos_fora_do_ar_NAO_vira_aluno(env, monkeypatch):
    """**O guarda que a sabotagem de 28/08 provou não existir.**

    Autorização falha FECHADO: não conseguir conferir a matrícula é diferente
    de conferir e dar positivo. Se este teste ficar verde com
    `eh_aluno = True`, o fórum passou a liberar área de aluno para qualquer
    pessoa logada sempre que a célula `alunos` piscar.
    """
    dublar(
        monkeypatch,
        identidade=resposta(SESSAO_OK),
        alunos=httpx.ConnectError("alunos caiu"),
    )
    ator = quem_e(RequisicaoFalsa())

    assert ator.autenticado is True, "a pessoa continua reconhecida"
    assert ator.eh_aluno is False, "mas NÃO é tratada como aluna"


def test_alunos_respondendo_500_tambem_nao_vira_aluno(env, monkeypatch):
    dublar(monkeypatch, identidade=resposta(SESSAO_OK), alunos=resposta({}, status=500))
    assert quem_e(RequisicaoFalsa()).eh_aluno is False


def test_alunos_respondendo_sem_categoria_nao_vira_aluno(env, monkeypatch):
    dublar(monkeypatch, identidade=resposta(SESSAO_OK), alunos=resposta({"x": 1}))
    assert quem_e(RequisicaoFalsa()).eh_aluno is False


def test_categoria_diferente_de_aluno_nao_vira_aluno(env, monkeypatch):
    """`na_fila` e `cadastrado` são reconhecidos, e não são aluno."""
    for categoria in ["cadastrado", "na_fila", "visitante"]:
        dublar(
            monkeypatch,
            identidade=resposta(SESSAO_OK),
            alunos=resposta({"categoria": categoria}),
        )
        assert quem_e(RequisicaoFalsa()).eh_aluno is False, categoria


def test_token_do_par_ausente_fecha_em_vez_de_derrubar(env, monkeypatch):
    """Env faltando é `ConfiguracaoAusente`, tratada — não 500 na página.

    `armadilhas/097`: cliente que lê env no import transforma variável ausente
    em erro em TODA página, com o deploy verde.
    """
    monkeypatch.delenv("IDENTIDADE_API_TOKEN")
    dublar(monkeypatch)
    assert quem_e(RequisicaoFalsa()).autenticado is False


# ------------------------------------------------------------- o caminho feliz
def test_aluno_reconhecido_e_espelhado_localmente(env, monkeypatch):
    dublar(
        monkeypatch,
        identidade=resposta(SESSAO_OK),
        alunos=resposta({"categoria": CATEGORIA_ALUNO}),
    )
    ator = quem_e(RequisicaoFalsa())

    assert ator.eh_aluno is True
    assert ator.pessoa.email == "ana@exemplo.com"
    assert ator.pessoa.nome_exibido == "Ana"
    # O espelho local existe para não pedir o nome pela rede a cada mensagem.
    assert Pessoa.objects.filter(id_da_plataforma="p_ana").exists()


def test_o_espelho_e_atualizado_e_nao_duplicado(env, monkeypatch):
    """Trocar o nome no site não pode criar uma segunda Pessoa."""
    dublar(
        monkeypatch,
        identidade=resposta(SESSAO_OK),
        alunos=resposta({"categoria": CATEGORIA_ALUNO}),
    )
    quem_e(RequisicaoFalsa())

    dublar(
        monkeypatch,
        identidade=resposta({**SESSAO_OK, "nome_exibido": "Ana Maria"}),
        alunos=resposta({"categoria": CATEGORIA_ALUNO}),
    )
    ator = quem_e(RequisicaoFalsa())

    assert Pessoa.objects.count() == 1
    assert ator.pessoa.nome_exibido == "Ana Maria"


def test_professor_e_admin_vem_das_listas_do_forum_nunca_da_identidade(
    env, monkeypatch
):
    """**Reconhecer não é autorizar.**

    O papel NÃO vem na resposta da `identidade` — vem das listas desta célula.
    Foi exatamente aqui que um consultor externo tropeçou na rodada de 28/08,
    ao propor papel assinado dentro do login.
    """
    monkeypatch.setenv("FORUM_PROFESSORES", "ana@exemplo.com, outro@x.com")
    monkeypatch.setenv("ADMIN_EMAILS", "chefe@x.com")
    dublar(
        monkeypatch,
        identidade=resposta({**SESSAO_OK, "papel": "aluno"}),
        alunos=resposta({"categoria": "cadastrado"}),
    )
    ator = quem_e(RequisicaoFalsa())

    assert ator.eh_professor is True, "a lista do fórum manda, não o `papel`"
    assert ator.eh_admin is False
    assert ator.eh_equipe is True


def test_lista_de_professores_vazia_nao_da_poder_a_ninguem(env, monkeypatch):
    """Fail-closed: variável ausente é *ninguém*, nunca *todo mundo*."""
    monkeypatch.delenv("FORUM_PROFESSORES", raising=False)
    dublar(
        monkeypatch,
        identidade=resposta(SESSAO_OK),
        alunos=resposta({"categoria": CATEGORIA_ALUNO}),
    )
    assert quem_e(RequisicaoFalsa()).eh_professor is False
