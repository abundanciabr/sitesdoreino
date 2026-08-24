"""[INVARIANTE 5] `alunos` fora do ar ⇒ a porta FECHA, com erro claro.

O modo de falha que este guarda existe para tornar impossível tem nome e é
tentador de escrever:

    try:
        matriculas = AlunosClient().matriculas_de(email)
    except Exception:
        matriculas = [...]        # "deixa entrar, depois a gente confere"

"Não consegui perguntar" NÃO é sinônimo de "perguntei e pode". A `alunos` é a
fonte de verdade da matrícula (`DECISAO-EVO-01-identidade.md` §2); indisponível,
a resposta honesta é *não sei*, e não saber fecha a porta.

O guarda cobre as quatro formas de não saber que a rede oferece — conexão
recusada, timeout, 500 e 401 — porque cada uma chega por um caminho diferente do
`httpx` e é perfeitamente possível tratar uma e esquecer as outras três.

A outra metade do invariante é a mensagem: o texto tem de dizer que o problema é
NOSSO. Quem vê "não encontramos sua matrícula" quando o sistema é que caiu passa
a tarde achando que perdeu o acesso ao curso que comprou.
"""

import httpx
import pytest

from apps.sugestoes.models import Identidade

pytestmark = pytest.mark.django_db

PESSOA = "aluna@exemplo.test"


@pytest.mark.parametrize(
    "modo",
    ["alunos_fora_do_ar", "alunos_demora_demais"],
    ids=["conexão recusada", "timeout"],
)
def test_rede_que_nao_responde_nao_deixa_entrar(porta, perfil, rede, modo):
    getattr(rede, modo)(PESSOA)

    resposta = porta.bater(perfil(PESSOA))

    assert resposta.status_code == 503, resposta.content
    assert not porta.esta_dentro
    assert Identidade.objects.count() == 0


@pytest.mark.parametrize("http", [401, 403, 500, 502, 503])
def test_resposta_de_erro_da_alunos_nao_deixa_entrar(
    porta, perfil, rede, http, matricula
):
    """Inclusive 401: token errado é falha de configuração, não permissão.

    O 404 fica de fora de propósito — ele é uma RESPOSTA ("aluno inexistente"),
    e está coberto pelo guarda do invariante 2.
    """
    rede.alunos_responde(PESSOA, httpx.Response(http))

    resposta = porta.bater(perfil(PESSOA))

    assert resposta.status_code == 503, resposta.content
    assert not porta.esta_dentro
    assert Identidade.objects.count() == 0


def test_resposta_fora_do_contrato_nao_deixa_entrar(porta, perfil, rede):
    """200 com um corpo que não é lista: `if matriculas:` acharia isto verdadeiro.

    Um dicionário de erro (`{"detail": "..."}`) é truthy em Python. Sem a
    conferência de tipo no cliente, este seria o caminho mais silencioso de
    todos para alguém entrar sem matrícula.
    """
    rede.alunos_responde(
        PESSOA, httpx.Response(200, json={"detail": "algo deu errado"})
    )

    resposta = porta.bater(perfil(PESSOA))

    assert resposta.status_code == 503, resposta.content
    assert not porta.esta_dentro
    assert Identidade.objects.count() == 0


def test_a_tela_diz_que_o_problema_e_nosso(porta, perfil, rede):
    rede.alunos_fora_do_ar(PESSOA)

    corpo = porta.bater(perfil(PESSOA)).content.decode()

    assert "problema nosso" in corpo
    assert "não encontramos matrícula" not in corpo.lower()


def test_configuracao_ausente_tambem_fecha_a_porta(porta, perfil, monkeypatch):
    """Sem `ALUNOS_API_URL` no env, ninguém entra — e o log nomeia a variável.

    É a contrapartida de ler configuração no ponto de uso em vez de fail-hard no
    import: a célula sobe, o `/healthz` responde, e o caminho que precisa da
    variável falha fechado e alto. Sobe sem entrar em silêncio seria o pior dos
    dois mundos.
    """
    monkeypatch.delenv("ALUNOS_API_URL")

    resposta = porta.bater(perfil(PESSOA))

    assert resposta.status_code == 503, resposta.content
    assert "ALUNOS_API_URL" in resposta.content.decode()
    assert not porta.esta_dentro
    assert Identidade.objects.count() == 0


def test_o_google_fora_do_ar_tambem_fecha(porta, perfil, rede):
    """O mesmo princípio no outro salto: sem perfil, não há quem entrar."""
    rede.google_fora_do_ar()

    resposta = porta.bater()

    assert resposta.status_code == 503, resposta.content
    assert not porta.esta_dentro
    assert Identidade.objects.count() == 0
