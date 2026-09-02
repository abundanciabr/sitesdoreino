"""A tradução id de plataforma → para onde escrever (`findPersonById`).

A **inversa** de `findPersonByEmail`, e existe pelo motivo oposto: uma célula que
conhece as pessoas por ID precisa entregar uma carta **fora** do site, e correio
eletrônico se endereça por e-mail. Rito de Contrato de 02/09/2026, degrau 1 do
e-mail de verdade — até ele, a `mensageria` tinha o id e nenhum jeito de virá-lo
em endereço, e por isso o e-mail das sequências não podia existir.

**As cinco coisas que este arquivo trava:**

1. **O degrau alto, por um motivo mais forte que o da irmã.** Aquela RECEBE um
   e-mail e diz se existe; esta DEVOLVE o e-mail. Um par sem
   `TOKENS_COMPLETOS_*` poderia varrer ids e colher a caixa de entrada da escola
   inteira.

2. **Só o que uma carta precisa.** Para onde ir e em que língua ser escrita.
   Nunca o nome, nunca o papel — cada campo a mais é um campo a mais vazando por
   um par de tokens.

3. **"Não conheço" é 200 com `email: null`, nunca 404.** A `mensageria` guarda o
   id numa inscrição que pode sobreviver à pessoa. Um 404 obrigaria quem chama a
   traduzir exceção de rede em "não existe" — e aí um erro de verdade passaria
   despercebido.

4. **`idioma` vazio no banco vira `null` no fio.** `""` é um idioma que não
   existe, e quem lesse sem cuidado tentaria renderizar nele.

5. **A língua se anota na cunhagem, e só nela.** Voltar para trocar a senha não
   reescreve o idioma: a pessoa pode estar em qualquer página, e deixar isso
   mandar faria a preferência dela oscilar ao sabor de por onde entrou.
"""

import pytest

from apps.core import sessao as ses
from apps.identidade.models import Identidade

TOKEN = "token-do-par-mensageria-identidade"
CAMINHO = "/interno/pessoas/por-id"


@pytest.fixture
def par_completo(settings):
    settings.TOKENS_ACEITOS = {TOKEN}
    settings.TOKENS_COMPLETOS = {TOKEN}
    return TOKEN


@pytest.fixture
def par_sem_degrau(settings):
    settings.TOKENS_ACEITOS = {TOKEN}
    settings.TOKENS_COMPLETOS = set()
    return TOKEN


def _procurar(client, id_pessoa, token: "str | None" = TOKEN):
    cabecalhos = {"authorization": f"Bearer {token}"} if token else {}
    return client.post(
        CAMINHO,
        data={"id": id_pessoa},
        content_type="application/json",
        headers=cabecalhos,
    )


# --------------------------------------------------------- 1. quem pode chamar


def test_sem_token_do_par_e_401(client, db, par_completo):
    assert _procurar(client, "qualquer", token=None).status_code == 401


def test_bearer_valido_SEM_o_degrau_e_403(client, db, par_sem_degrau):
    """O guarda que carrega este arquivo.

    Esta porta DEVOLVE dado pessoal. Sem o degrau, um par com Bearer válido
    varreria ids e colheria os endereços de toda a escola.
    """
    pessoa = Identidade.objects.create(email="alguem@exemplo.test")
    assert _procurar(client, pessoa.id).status_code == 403


def test_sem_nenhum_token_completo_configurado_tudo_e_403(client, db, settings):
    """Conjunto vazio ⇒ ninguém passa. Fail-closed por construção."""
    settings.TOKENS_ACEITOS = {TOKEN}
    settings.TOKENS_COMPLETOS = set()
    assert _procurar(client, "qualquer").status_code == 403


# ------------------------------------------------------------- 2. a tradução


def test_devolve_para_onde_escrever_e_em_que_lingua(client, db, par_completo):
    pessoa = Identidade.objects.create(email="aluna@exemplo.test", idioma="es")
    resposta = _procurar(client, pessoa.id)
    assert resposta.status_code == 200
    assert resposta.json() == {"email": "aluna@exemplo.test", "idioma": "es"}


def test_id_que_nao_existe_e_200_com_email_nulo(client, db, par_completo):
    """Nunca 404: "não conheço este id" é resposta comum, não exceção."""
    resposta = _procurar(client, "id-que-nunca-existiu")
    assert resposta.status_code == 200
    assert resposta.json() == {"email": None, "idioma": None}


def test_quem_nunca_declarou_lingua_volta_com_idioma_nulo(client, db, par_completo):
    """No banco a ausência é `""`; no fio ela é `null`.

    Duas grafias para a mesma coisa fariam o primeiro código que comparasse com
    `== ""` errar metade das linhas em silêncio — e quem escreve a carta precisa
    de um sinal claro para aplicar o próprio padrão.
    """
    pessoa = Identidade.objects.create(email="sem.lingua@exemplo.test")
    assert _procurar(client, pessoa.id).json() == {
        "email": "sem.lingua@exemplo.test",
        "idioma": None,
    }


def test_a_porta_nunca_devolve_nome_nem_papel(client, db, par_completo):
    """O mínimo que uma carta precisa, e nada além.

    Guarda de superfície: o dia em que alguém acrescentar um campo "porque é
    útil", este teste reprova e obriga a conversa a acontecer no PR.
    """
    pessoa = Identidade.objects.create(
        email="aluno@exemplo.test", nome_exibido="Fulano de Tal"
    )
    corpo = _procurar(client, pessoa.id).json()
    assert set(corpo) == {"email", "idioma"}
    assert "Fulano" not in str(corpo)


def test_pedido_sem_id_e_422(client, db, par_completo):
    """Desacordo de quem chama com o contrato, não "não conheço".

    Responder `email: null` a uma pergunta que não foi feita esconderia o
    defeito de quem escreveu o código que chama.
    """
    assert _procurar(client, "  ").status_code == 422


# ------------------------------------------- 3. de onde a língua vem, e quando


def test_a_cunhagem_anota_o_idioma(client, db):
    """A única hora em que a plataforma tem essa informação de graça."""
    identidade, criada = ses.definir_senha(
        email="nova@exemplo.test", senha="uma-senha-qualquer", idioma="en"
    )
    assert criada
    assert identidade.idioma == "en"


def test_voltar_para_trocar_a_senha_NAO_reescreve_o_idioma(client, db):
    """O guarda do "só na cunhagem", e ele protege uma preferência da pessoa.

    Quem volta para trocar a senha pode estar em qualquer página do site. Se
    esta segunda visita mandasse, a língua da pessoa oscilaria ao sabor de por
    onde ela entrou — e ela nunca pediu isso.
    """
    ses.definir_senha(email="volta@exemplo.test", senha="primeira-senha", idioma="es")
    identidade, criada = ses.definir_senha(
        email="volta@exemplo.test", senha="segunda-senha", idioma="pt-br"
    )
    assert not criada
    assert identidade.idioma == "es"


def test_cunhagem_sem_idioma_deixa_a_pessoa_sem_lingua_declarada(client, db):
    """E isso é resposta legítima, não falta: quem escreve a carta decide."""
    identidade, _ = ses.definir_senha(
        email="muda@exemplo.test", senha="uma-senha-qualquer"
    )
    assert identidade.idioma == ""
