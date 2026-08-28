"""A gestão de quem já é aluno — `docs/decisoes/DECISAO-gestao-de-alunos.md`.

O mantenedor abriu a tela de alunos e disse: *"os alunos aprovados não aparecem
em lugar nenhum do painel. Quero poder gerenciá-los."* Ele estava certo, e a
tela também: **não existia, em lugar nenhum, como listar quem é aluno** — a
célula só sabia responder sobre um e-mail por vez.

**Os três testes que carregam o arquivo**, e nenhum deles é "a porta responde":

1. `test_pausar_tira_o_acesso_de_verdade`. É a mudança de regra inteira, medida
   de ponta a ponta: `suspensa` saiu de `STATUS_QUE_VALEM`, e um botão "pausar"
   que deixasse a pessoa entrar do mesmo jeito seria decoração. O teste pausa
   pela porta nova e pergunta pela porta que a Caixa usa.

2. `test_a_lista_sem_site_id_traz_todas_as_escolas`. `.filter(site_id=None)`
   casa com `site_id IS NULL` e devolve **lista vazia** — *"nenhum aluno"* para
   quem tem alunos. O mesmo erro que a fila já recusou uma vez.

3. `test_a_fila_nao_se_administra_por_aqui`. Duas portas para o mesmo fato, com
   regras diferentes, é como uma decisão de fila passa sem conferir "já
   decidida" e sem gravar motivo. Linha da fila responde **409**.

E `test_o_email_nao_se_edita`: ele é a IDENTIDADE da linha. Trocá-lo moveria a
matrícula, em silêncio, para outra pessoa.
"""

import itertools
import json

import pytest

from apps.matriculas.models import Matricula

MATRICULAS = "/api/alunos/matriculas"
ALGUEM = "aluno@example.com"

# As chaves que o painel recebe, e NADA além delas. Escritas à mão: um
# inventário que perguntasse ao código concordaria com qualquer vazamento.
CHAVES = {
    "id",
    "site_id",
    "email",
    "nome_completo",
    "whatsapp",
    "turma",
    "comprou_em",
    "status",
    "origem",
    "criada_em",
}


@pytest.fixture
def token_valido(settings):
    settings.TOKENS_ACEITOS = {"token-de-teste"}
    return "token-de-teste"


@pytest.fixture
def auth(token_valido):
    return {"HTTP_AUTHORIZATION": f"Bearer {token_valido}"}


# Contador, e não relógio: `timezone.now().timestamp()` repete dentro do mesmo
# microssegundo e duas linhas seguidas colidem no `order_id`, que é único.
_sequencia = itertools.count(1)


def criar(**campos) -> Matricula:
    corpo = {
        "site_id": "escola-a",
        "order_id": f"pedido-{next(_sequencia)}",
        "email": ALGUEM,
        "name": "Fulano de Tal",
        "status": Matricula.STATUS_ATIVA,
    }
    corpo.update(campos)
    return Matricula.objects.create(**corpo)


def listar(client, auth, **query):
    url = MATRICULAS
    if query:
        url += "?" + "&".join(f"{k}={v}" for k, v in query.items())
    return client.get(url, **auth)


def mudar(client, auth, linha, **corpo):
    corpo.setdefault("decidido_por", "id-do-admin")
    return client.patch(
        f"{MATRICULAS}/{linha.pk}",
        data=json.dumps(corpo),
        content_type="application/json",
        **auth,
    )


# ------------------------------------------------------------------- a lista


@pytest.mark.django_db
def test_a_lista_traz_quem_ja_e_aluno_e_nao_quem_esta_na_fila(client, auth):
    criar(email="aluno@example.com")
    criar(
        email="espera@example.com",
        order_id="pre:1",
        status=Matricula.STATUS_AGUARDANDO,
    )
    corpo = listar(client, auth).json()
    assert [linha["email"] for linha in corpo] == ["aluno@example.com"]


@pytest.mark.django_db
def test_a_lista_sem_site_id_traz_todas_as_escolas(client, auth):
    """O erro clássico: `.filter(site_id=None)` devolveria vazio."""
    criar(site_id="escola-a", email="a@example.com")
    criar(site_id="escola-b", email="b@example.com")
    corpo = listar(client, auth).json()
    assert {linha["site_id"] for linha in corpo} == {"escola-a", "escola-b"}


@pytest.mark.django_db
def test_a_lista_filtra_por_escola_e_por_estado(client, auth):
    criar(site_id="escola-a", email="a@example.com")
    criar(site_id="escola-b", email="b@example.com")
    criar(
        site_id="escola-a",
        email="pausado@example.com",
        status=Matricula.STATUS_SUSPENSA,
    )

    so_a = listar(client, auth, site_id="escola-a").json()
    assert {linha["email"] for linha in so_a} == {
        "a@example.com",
        "pausado@example.com",
    }

    pausados = listar(client, auth, status="suspensa").json()
    assert [linha["email"] for linha in pausados] == ["pausado@example.com"]


@pytest.mark.django_db
def test_a_origem_e_derivada_do_pedido_e_nao_de_um_campo(client, auth):
    """`liberado` x `comprou` sai do prefixo sintético `pre:`.

    Um campo `origem` gravado seria um segundo lugar guardando o que o
    `order_id` já diz — e os dois discordariam no primeiro backfill.
    """
    criar(email="comprou@example.com", order_id="mp-123456")
    criar(email="liberado@example.com", order_id="pre:abc")
    por_email = {
        linha["email"]: linha["origem"] for linha in listar(client, auth).json()
    }
    assert por_email == {
        "comprou@example.com": "comprou",
        "liberado@example.com": "liberado",
    }


@pytest.mark.django_db
def test_a_lista_devolve_o_whatsapp_e_so_as_chaves_do_contrato(client, auth):
    """PII: é porta de PAINEL, e o WhatsApp sai por ela de propósito.

    A lei da fila §5 diz que o número sai "por uma porta só, a do painel
    administrativo" — `GET /pre-matriculas` e esta SÃO essa porta. Sem ele o
    mantenedor não consegue falar com a pessoa. O que o guarda trava é o
    conjunto EXATO: campo novo entra por decisão, não por descuido.
    """
    criar(whatsapp="(96) 99999-0000", turma="Turma A")
    linha = listar(client, auth).json()[0]
    assert set(linha) == CHAVES
    assert linha["whatsapp"] == "(96) 99999-0000"


# ---------------------------------------------------------------- o formulário


@pytest.mark.django_db
def test_mudar_o_estado_grava_quem_mudou_e_quando(client, auth):
    alvo = criar()
    resposta = mudar(client, auth, alvo, status="suspensa")

    assert resposta.status_code == 200, resposta.content
    assert resposta.json()["status"] == "suspensa"
    alvo.refresh_from_db()
    assert alvo.status == Matricula.STATUS_SUSPENSA
    assert alvo.decidido_por == "id-do-admin"
    assert alvo.decidido_em is not None


@pytest.mark.django_db
def test_corrigir_os_dados_que_a_pessoa_digitou(client, auth):
    """Nome, WhatsApp, turma e data: coisas que a própria pessoa preencheu e erra."""
    alvo = criar(name="Fluano", whatsapp="96999990000", turma="")
    resposta = mudar(
        client,
        auth,
        alvo,
        nome_completo="Fulano de Tal",
        whatsapp="(96) 99999-0000",
        turma="Turma de agosto",
        comprou_em="2026-08-01",
    )

    assert resposta.status_code == 200, resposta.content
    alvo.refresh_from_db()
    assert alvo.name == "Fulano de Tal"
    assert alvo.whatsapp == "(96) 99999-0000"
    assert alvo.turma == "Turma de agosto"
    assert alvo.comprou_em.isoformat() == "2026-08-01"


@pytest.mark.django_db
def test_o_email_nao_se_edita(client, auth):
    """É a IDENTIDADE da linha — trocá-lo moveria a matrícula para outra pessoa.

    Recusado por `additionalProperties: false` traduzido em código
    (`_payload_valido`), e não por um `if` esquecível: chave desconhecida é
    recusada em bloco, então o campo que alguém acrescentar amanhã também é.
    """
    alvo = criar()
    resposta = mudar(client, auth, alvo, email="outra@example.com")

    assert resposta.status_code == 422, resposta.content
    alvo.refresh_from_db()
    assert alvo.email == ALGUEM


@pytest.mark.django_db
@pytest.mark.parametrize("campo", ["site_id", "order_id", "product_id"])
def test_o_que_veio_do_fato_que_criou_a_linha_nao_se_reescreve(client, auth, campo):
    alvo = criar()
    assert mudar(client, auth, alvo, **{campo: "outro"}).status_code == 422


@pytest.mark.django_db
def test_a_fila_nao_se_administra_por_aqui(client, auth):
    """409, e a recusa é o desenho.

    A porta da fila confere "já decidida" e grava o motivo da recusa. Deixar
    esta mexer nas mesmas linhas daria dois caminhos para o mesmo fato, com
    regras diferentes — e o segundo não saberia nada sobre motivo.
    """
    alvo = criar(order_id="pre:9", status=Matricula.STATUS_AGUARDANDO)
    resposta = mudar(client, auth, alvo, status="ativa")

    assert resposta.status_code == 409, resposta.content
    alvo.refresh_from_db()
    assert alvo.status == Matricula.STATUS_AGUARDANDO


@pytest.mark.django_db
@pytest.mark.parametrize("status", ["aguardando", "recusada", "inventada", ""])
def test_estado_fora_do_vocabulario_de_gestao_nao_entra(client, auth, status):
    """Lista de PERMISSÃO: estado da fila e estado inventado ficam de fora."""
    alvo = criar()
    assert mudar(client, auth, alvo, status=status).status_code == 422
    alvo.refresh_from_db()
    assert alvo.status == Matricula.STATUS_ATIVA


@pytest.mark.django_db
def test_formulario_que_nao_muda_nada_e_422(client, auth):
    """Quase sempre é um formulário que não chegou como a pessoa achou."""
    alvo = criar(status=Matricula.STATUS_ATIVA)
    assert mudar(client, auth, alvo, status="ativa").status_code == 422


@pytest.mark.django_db
def test_nome_em_branco_e_recusado(client, auth):
    """Apagaria a única forma de o mantenedor reconhecer a pessoa na lista."""
    alvo = criar()
    assert mudar(client, auth, alvo, nome_completo="   ").status_code == 422


@pytest.mark.django_db
def test_id_que_nao_existe_e_404_e_nao_500(client, auth):
    alvo = criar()
    alvo.delete()
    assert mudar(client, auth, alvo, status="suspensa").status_code == 404


# ------------------------------------------- a regra nova, de ponta a ponta


@pytest.mark.django_db
def test_pausar_tira_o_acesso_de_verdade(client, auth):
    """A mudança de 28/08 inteira, medida pelas DUAS portas.

    Pausa pela porta do painel e pergunta pela porta que a Caixa usa. Sem isto,
    "pausar" seria uma etiqueta bonita sem efeito nenhum — que é exatamente o
    que `suspensa` era antes desta lei.
    """
    alvo = criar()
    porta_da_caixa = f"/api/alunos/alunos/{ALGUEM}/matriculas"
    assert client.get(porta_da_caixa, **auth).status_code == 200

    assert mudar(client, auth, alvo, status="suspensa").status_code == 200

    assert (
        client.get(porta_da_caixa, **auth).status_code == 404
    ), "pausado continuou entrando — o botão de pausar virou decoração"


@pytest.mark.django_db
def test_religar_devolve_o_acesso_na_hora(client, auth):
    """Reversível é metade do valor do botão."""
    alvo = criar(status=Matricula.STATUS_SUSPENSA)
    porta_da_caixa = f"/api/alunos/alunos/{ALGUEM}/matriculas"
    assert client.get(porta_da_caixa, **auth).status_code == 404

    assert mudar(client, auth, alvo, status="ativa").status_code == 200
    assert client.get(porta_da_caixa, **auth).status_code == 200


@pytest.mark.django_db
def test_encerrar_tira_o_acesso_e_a_linha_continua_existindo(client, auth):
    """ "Excluir" apaga o ACESSO, não a história (`DECISAO-gestao-de-alunos` §5).

    É a linha que permite desfazer e que dá sentido à auditoria do painel.
    """
    alvo = criar()
    assert mudar(client, auth, alvo, status="encerrada").status_code == 200

    assert (
        client.get(f"/api/alunos/alunos/{ALGUEM}/matriculas", **auth).status_code == 404
    )
    assert Matricula.objects.filter(pk=alvo.pk).exists()
    assert [l["status"] for l in listar(client, auth).json()] == ["encerrada"]


@pytest.mark.django_db
def test_reembolsada_continua_valendo_acesso(client, auth):
    """A decisão de 24/08 do mantenedor, intacta: quem já foi aluno mantém a voz.

    Ela foi tomada sobre REEMBOLSO, e a mudança de 28/08 (pausar bloqueia) não
    a toca. Este teste existe para que a próxima pessoa que "limpar" a lista de
    status que valem encontre a decisão em vez de a adivinhar.
    """
    criar(status=Matricula.STATUS_REEMBOLSADA)
    assert (
        client.get(f"/api/alunos/alunos/{ALGUEM}/matriculas", **auth).status_code == 200
    )


# ------------------------------------------------------- a borda da internet


@pytest.mark.django_db
def test_as_duas_portas_recusam_sem_bearer():
    """Esta API é alcançável pela internet (`armadilhas/103`), e devolve PII."""
    from django.test import Client

    anonimo = Client()
    assert anonimo.get(MATRICULAS).status_code == 401
    assert (
        anonimo.patch(
            f"{MATRICULAS}/1",
            data=json.dumps({"decidido_por": "x", "status": "suspensa"}),
            content_type="application/json",
        ).status_code
        == 401
    )


# ------------------------------------------------------------ apagar de vez
#
# `DECISAO-administradores-e-apagar` §4. O mantenedor escolheu construir agora,
# contra a recomendação do agente, com o preço apresentado antes.


def apagar(client, auth, linha):
    return client.delete(f"{MATRICULAS}/{linha.pk}", **auth)


@pytest.mark.django_db
def test_apagar_some_com_a_linha_e_nao_troca_o_estado(client, auth):
    """A diferença que separa esta porta do `PATCH status=encerrada`.

    Encerrar guarda a ficha para poder desfazer; apagar não guarda nada. Um
    teste que só olhasse "sumiu da lista" não distinguiria as duas.
    """
    alvo = criar()
    resposta = apagar(client, auth, alvo)

    assert resposta.status_code == 204
    assert resposta.content == b"", "204 não devolve corpo"
    assert not Matricula.objects.filter(pk=alvo.pk).exists()


@pytest.mark.django_db
def test_apagar_tira_o_acesso_junto(client, auth):
    alvo = criar()
    porta_da_caixa = f"/api/alunos/alunos/{ALGUEM}/matriculas"
    assert client.get(porta_da_caixa, **auth).status_code == 200

    apagar(client, auth, alvo)
    assert client.get(porta_da_caixa, **auth).status_code == 404


@pytest.mark.django_db
def test_apagar_quem_esta_na_fila_e_recusado(client, auth):
    """Mesma recusa do `PATCH`, e pelo mesmo motivo: a fila tem porta própria."""
    alvo = criar(order_id="pre:5", status=Matricula.STATUS_AGUARDANDO)
    assert apagar(client, auth, alvo).status_code == 409
    assert Matricula.objects.filter(pk=alvo.pk).exists()


@pytest.mark.django_db
def test_apagar_o_que_ja_nao_existe_e_404_e_nao_500(client, auth):
    alvo = criar()
    alvo.delete()
    assert apagar(client, auth, alvo).status_code == 404


@pytest.mark.django_db
def test_apagar_sem_bearer_e_recusado():
    """A porta mais destrutiva da célula, e a que mais precisa do guarda."""
    from django.test import Client

    assert Client().delete(f"{MATRICULAS}/1").status_code == 401
