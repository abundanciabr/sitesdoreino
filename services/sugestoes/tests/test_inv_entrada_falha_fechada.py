"""[INVARIANTE] Peça fora do ar ⇒ a porta FECHA, com erro claro.

Desde a `DECISAO-celula-de-identidade` são DUAS as peças que a porta consulta:
a `identidade` (quem é) e a `alunos` (se pode). Falhar QUALQUER uma delas
nunca vira "deixa entrar" — a resposta daqui alimenta autorização, e
autorização falha fechada (é o oposto do reconhecimento de exibição do
`funil`, que falha aberto porque lá a resposta só decide um nome na tela).

E a tela diz que o problema é NOSSO: a pessoa não pode sair daqui achando que
perdeu a matrícula.
"""

import httpx
import pytest

from apps.sugestoes.models import Identidade
from tests.conftest import sessao_do_site

PESSOA = "joao.silva@exemplo.test"


def _porta_fechada_explicando(pessoa):
    resposta = pessoa.abrir()
    assert resposta.status_code == 503, resposta.content
    conteudo = resposta.content.decode()
    assert "Não conseguimos conferir" in conteudo
    assert "problema nosso" in conteudo
    return conteudo


def test_alunos_fora_do_ar_fecha_a_porta(rede, db):
    rede.alunos_fora_do_ar(PESSOA)
    pessoa = sessao_do_site(rede, email=PESSOA)

    _porta_fechada_explicando(pessoa)
    assert Identidade.objects.count() == 0, "recusa não cunha identidade local"


def test_alunos_demorando_demais_fecha_a_porta(rede, db):
    rede.alunos_demora_demais(PESSOA)
    pessoa = sessao_do_site(rede, email=PESSOA)

    _porta_fechada_explicando(pessoa)


@pytest.mark.parametrize("status", [500, 401, 403])
def test_alunos_com_erro_fecha_a_porta(rede, db, status):
    """5xx e 401/403 (token errado) são "não consegui perguntar" — nunca
    "não tem matrícula": as duas recusas têm telas diferentes."""
    rede.alunos_responde(PESSOA, httpx.Response(status))
    pessoa = sessao_do_site(rede, email=PESSOA)

    _porta_fechada_explicando(pessoa)


def test_identidade_fora_do_ar_fecha_a_porta(rede, db, client):
    """A peça NOVA da mesma regra: sem saber QUEM É, nada de participação.

    Note o detalhe: o visitante SEM cookie nenhum não é este caso — ele nem
    gera pergunta e vê a porta normal. O caso é quem TEM cookie e a identidade
    não responde: pode ser alguém logado, e mostrar "Entrar" mentiria.
    """
    rede.central_fora_do_ar()
    client.cookies["meshcraft_sessao"] = "algum-valor"
    from tests.conftest import Porta

    _porta_fechada_explicando(Porta(client, rede))


def test_identidade_respondendo_fora_do_contrato_fecha_a_porta(rede, db, client):
    rede.central_responde(httpx.Response(200, json={"isto": "não é o contrato"}))
    client.cookies["meshcraft_sessao"] = "algum-valor"
    from tests.conftest import Porta

    _porta_fechada_explicando(Porta(client, rede))


def test_resposta_autenticada_sem_email_fecha_a_porta(rede, db, client):
    """`autenticado: true` sem e-mail = o degrau TOKENS_COMPLETOS faltando do
    outro lado. Sem e-mail não há como conferir lista nenhuma — fecha, em vez
    de tratar a pessoa como visitante (que esconderia a má configuração)."""
    rede.central_responde(
        httpx.Response(200, json={"autenticado": True, "nome_exibido": "João"})
    )
    client.cookies["meshcraft_sessao"] = "algum-valor"
    from tests.conftest import Porta

    _porta_fechada_explicando(Porta(client, rede))


def test_participacao_tambem_fecha_quando_nao_da_para_conferir(rede, db, quadro):
    """A outra metade: não é só a porta — nenhuma rota de participação roda."""
    rede.alunos_fora_do_ar(PESSOA)
    pessoa = sessao_do_site(rede, email=PESSOA)

    from django.urls import reverse

    resposta = pessoa.client.get(reverse("quadro"))
    assert resposta.status_code == 302
    assert resposta["Location"] == reverse("entrar")


def test_resposta_200_que_nao_e_json_fecha_explicando(rede, db, client):
    """`json.JSONDecodeError` é `ValueError`, não `httpx.RequestError`.

    Cenário real: um proxy interposto devolve a própria página de erro com
    status 200, ou a resposta chega truncada. Fora do `try` isso subiria cru
    até a view e viraria **500** — em vez do 503 que diz "o problema é nosso".
    A porta continua fechando (autorização é fail-closed), mas fechando com
    explicação, que é a regra desta célula.
    """
    rede.central_responde(httpx.Response(200, text="<html>erro do proxy</html>"))
    client.cookies["meshcraft_sessao"] = "algum-valor"
    from tests.conftest import Porta

    _porta_fechada_explicando(Porta(client, rede))
