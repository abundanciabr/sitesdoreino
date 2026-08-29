"""A tradução e-mail → id de plataforma (`findPersonByEmail`).

Ela existe por uma razão só, e vale escrevê-la aqui porque ela explica todas as
escolhas abaixo: **uma célula que conhece as pessoas por e-mail precisa
endereçar uma carta para a caixa de avisos, que entrega por id de plataforma.**
Ninguém, até 29/08/2026, sabia traduzir um no outro — e sem isso a promessa "você
é avisado quando a sua situação muda" não tinha como existir.

O mantenedor escolheu esta porta contra a alternativa de gravar o id na ficha do
aluno: a cópia resolveria só as fichas novas, e as antigas — e as que o painel
cria à mão — ficariam para sempre sem aviso.

**As quatro coisas que este arquivo trava:**

1. **O degrau a mais.** Bearer válido não basta: exige `TOKENS_COMPLETOS_*`, o
   mesmo de `/sessao/completa`. Aquele DEVOLVE um e-mail; este RECEBE um e diz
   se ele existe — e isso permite enumerar endereços.

2. **Entra e-mail, sai id.** A resposta nunca carrega e-mail nem nome. É a
   `DECISAO-EVO-01` §3 impressa na forma da porta.

3. **"Não conheço" é 200 com `id: null`, nunca 404.** Quem foi cadastrado à mão
   pelo painel e ainda não entrou com o Google não tem identidade nenhuma aqui —
   é resposta comum, não exceção. Um 404 obrigaria quem chama a traduzir
   exceção de rede em "não existe", e aí um erro de verdade passaria
   despercebido.

4. **A normalização mora aqui.** Quem é dono do dado é dono da forma canônica
   dele. Se cada célula repetisse a regra, a primeira que esquecesse receberia
   `null` para uma pessoa que existe — e o efeito seria um aviso que nunca
   chega, sem erro nenhum no caminho.
"""

import pytest

from apps.identidade.models import Identidade

TOKEN = "token-do-par-alunos-identidade"
CAMINHO = "/interno/pessoas/por-email"
EMAIL = "quem.procuro@exemplo.test"


@pytest.fixture
def par_completo(settings):
    """O par com o degrau a mais — como o env real o forneceria."""
    settings.TOKENS_ACEITOS = {TOKEN}
    settings.TOKENS_COMPLETOS = {TOKEN}
    return TOKEN


@pytest.fixture
def par_sem_degrau(settings):
    """Bearer válido, sem `TOKENS_COMPLETOS_*`."""
    settings.TOKENS_ACEITOS = {TOKEN}
    settings.TOKENS_COMPLETOS = set()
    return TOKEN


def _procurar(client, email, token: "str | None" = TOKEN):
    cabecalhos = {"authorization": f"Bearer {token}"} if token else {}
    return client.post(
        CAMINHO,
        data={"email": email},
        content_type="application/json",
        headers=cabecalhos,
    )


# --------------------------------------------------------- 1. quem pode chamar


def test_sem_token_do_par_e_401(client, db, par_completo):
    assert _procurar(client, EMAIL, token=None).status_code == 401


def test_token_errado_e_401(client, db, par_completo):
    assert _procurar(client, EMAIL, token="de-outro-alguem").status_code == 401


def test_bearer_valido_SEM_o_degrau_e_403(client, db, par_sem_degrau):
    """O guarda que carrega este arquivo.

    Quem manda um e-mail para esta porta descobre se ele existe — e um par sem
    o degrau poderia varrer endereços e mapear quem tem conta no site. É o mesmo
    raciocínio que fez `/sessao/completa` nascer com 403 próprio.
    """
    Identidade.objects.create(email=EMAIL)
    assert _procurar(client, EMAIL).status_code == 403


def test_sem_nenhum_token_completo_configurado_tudo_e_403(client, db, settings):
    """Conjunto vazio ⇒ ninguém passa. Fail-closed por construção."""
    settings.TOKENS_ACEITOS = {TOKEN}
    settings.TOKENS_COMPLETOS = set()
    assert _procurar(client, EMAIL).status_code == 403


# ------------------------------------------------------------ 2. a tradução


def test_acha_o_id_de_quem_existe(client, db, par_completo):
    pessoa = Identidade.objects.create(email=EMAIL, nome_exibido="Quem Procuro")

    resposta = _procurar(client, EMAIL)

    assert resposta.status_code == 200
    assert resposta.json() == {"id": pessoa.id}


def test_a_resposta_NAO_devolve_email_nem_nome(client, db, par_completo):
    """Entra e-mail, sai id. `DECISAO-EVO-01` §3 impressa na forma da porta.

    Medido no corpo cru, e não nas chaves: um campo novo acrescentado amanhã com
    outro nome ainda vazaria o dado, e é o VALOR que não pode sair daqui.
    """
    Identidade.objects.create(email=EMAIL, nome_exibido="Quem Procuro")

    corpo = _procurar(client, EMAIL).content.decode()

    assert EMAIL not in corpo
    assert "Quem Procuro" not in corpo


def test_maiusculas_e_espacos_acham_a_mesma_pessoa(client, db, par_completo):
    """A normalização mora AQUI, e não em quem chama.

    Se cada célula repetisse a regra, a primeira que esquecesse receberia `null`
    para uma pessoa que existe — e o efeito seria um aviso que nunca chega, sem
    erro nenhum no caminho.
    """
    pessoa = Identidade.objects.create(email=EMAIL)

    for escrito in (f"  {EMAIL}  ", EMAIL.upper(), f" {EMAIL.title()} "):
        resposta = _procurar(client, escrito)
        assert resposta.json() == {"id": pessoa.id}, escrito


# ------------------------------------------- 3. "não conheço" é uma RESPOSTA


def test_quem_nao_existe_volta_200_com_id_nulo(client, db, par_completo):
    """Nunca 404: quem foi cadastrado à mão pelo painel e ainda não entrou com o
    Google não tem identidade nenhuma aqui, e isso é comum — não é exceção."""
    resposta = _procurar(client, "ninguem@exemplo.test")

    assert resposta.status_code == 200
    assert resposta.json() == {"id": None}


def test_pedido_sem_email_e_422_e_nao_id_nulo(client, db, par_completo):
    """Responder "não conheço" a uma pergunta que não foi feita esconderia o
    defeito de quem escreveu o código."""
    assert _procurar(client, "").status_code == 422
    assert _procurar(client, "   ").status_code == 422


def test_corpo_sem_a_chave_email_e_recusado(client, db, par_completo):
    resposta = client.post(
        CAMINHO,
        data={"outro": "campo"},
        content_type="application/json",
        headers={"authorization": f"Bearer {TOKEN}"},
    )
    assert resposta.status_code == 422


# --------------------------------------------- 4. a porta continua não sabendo


def test_esta_porta_nao_cunha_ninguem(client, db, par_completo):
    """Procurar não cria.

    Uma porta de leitura que criasse a pessoa ao não achá-la encheria a tabela
    de identidades com quem nunca entrou no site — e o `id` devolvido não
    significaria "esta pessoa entrou", que é o que ele significa hoje.
    """
    _procurar(client, "ninguem@exemplo.test")
    assert not Identidade.objects.filter(email="ninguem@exemplo.test").exists()


def test_o_metodo_GET_nao_atende(client, db, par_completo):
    """POST e não GET com o e-mail no caminho, e a escolha é de privacidade:
    caminho de URL entra em log de servidor, em histórico de proxy e em rastro
    de erro. Corpo, não."""
    resposta = client.get(
        f"{CAMINHO}/{EMAIL}", headers={"authorization": f"Bearer {TOKEN}"}
    )
    assert resposta.status_code in (404, 405)
