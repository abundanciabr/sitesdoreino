"""A ficha não se apaga, e o prontuário conta a história — `DECISAO-a-ficha-nao-se-apaga.md`.

O mantenedor, em 29/08/2026: *"Eu quero que o cadastro do aluno NUNCA SEJA
APAGADO, mas que ele mude para 'ex-aluno'. Onde quando ele tentar fazer um novo
cadastro que ele vá novamente para a lista onde ficam os cadastros aguardando a
aprovação/liberação, com a indicação na tela de que se trata de um ex-aluno, e
mostre o link para o prontuário do mesmo."*

**Os quatro testes que carregam o arquivo:**

1. `test_nao_existe_porta_que_apague_uma_ficha` — a capacidade saiu, não só o
   botão. Uma porta some com uma linha de decorador e volta com outra; sem
   guarda, a próxima sessão que precisar de um "limpar" a recria sem saber que
   está revertendo uma lei.

2. `test_a_ficha_encerrada_sobrevive_a_volta` — o coração da decisão: quem sai e
   volta ganha ficha NOVA, e a antiga fica intacta, com a data e o motivo da
   saída. Reaproveitar a linha apagaria a saída no instante da volta, e
   *"quando ele saiu, mesmo?"* deixaria de ter resposta.

3. `test_a_fila_diz_quem_ja_foi_aluno` — sem isso o mantenedor decide sobre um
   ex-aluno achando que é gente nova, que é exatamente o erro que a fila existe
   para não cometer.

4. `test_ja_foi_aluno_nao_e_ja_teve_ficha` — a distinção que um `.exists()`
   apressado apagaria: quem foi recusado três vezes tem três fichas e nunca
   entrou.
"""

import itertools
import json

import pytest
from django.test import Client
from django.utils import timezone

from apps.matriculas.models import Matricula
from apps.matriculas.services import prontuario_de

MATRICULAS = "/api/alunos/matriculas"
FILA = "/api/alunos/pre-matriculas"
ALGUEM = "quem.voltou@example.com"


@pytest.fixture
def token_valido(settings):
    settings.TOKENS_ACEITOS = {"token-de-teste"}
    return "token-de-teste"


@pytest.fixture
def auth(token_valido):
    return {"HTTP_AUTHORIZATION": f"Bearer {token_valido}"}


_sequencia = itertools.count(1)


def criar(**campos) -> Matricula:
    corpo = {
        "site_id": "escola-a",
        "order_id": f"pedido-{next(_sequencia)}",
        "email": ALGUEM,
        "name": "Quem Voltou",
        "status": Matricula.STATUS_ATIVA,
    }
    corpo.update(campos)
    return Matricula.objects.create(**corpo)


def na_fila(**campos) -> Matricula:
    """Uma linha nascida na FILA — prefixo `pre:`, como a porta a cria."""
    return criar(
        order_id=f"pre:{next(_sequencia)}",
        status=Matricula.STATUS_AGUARDANDO,
        **campos,
    )


def prontuario(client, auth, email=ALGUEM):
    return client.get(f"/api/alunos/alunos/{email}/prontuario", **auth)


# --------------------------------------------------- 1. a capacidade que saiu


@pytest.mark.django_db
def test_nao_existe_porta_que_apague_uma_ficha(client, auth):
    """A porta saiu do roteador, e não só do contrato.

    Um `DELETE` que respondesse 204 aqui significaria que o código continuou
    capaz de apagar e só o papel mudou — o oposto de "remoção de capacidade".
    405/404 é o roteador dizendo que este verbo não existe neste caminho.
    """
    alvo = criar()

    resposta = client.delete(f"{MATRICULAS}/{alvo.pk}", **auth)

    assert resposta.status_code in (404, 405), (
        "DELETE /matriculas/{id} respondeu "
        f"{resposta.status_code} — a porta que apagava voltou"
    )
    assert Matricula.objects.filter(pk=alvo.pk).exists()


def test_a_celula_nao_tem_mais_a_funcao_de_apagar():
    """O caminho de código, e não só a rota.

    Enquanto `apagar_matricula` existir, basta uma view nova para a capacidade
    voltar sem passar por lei nenhuma.
    """
    from apps.matriculas import services

    assert not hasattr(services, "apagar_matricula")


@pytest.mark.django_db
def test_encerrar_e_o_caminho_e_ele_guarda_a_ficha(client, auth):
    """O que existe NO LUGAR do apagar — e a prova de que tira o acesso mesmo.

    Sem esta metade, "não apagamos mais" poderia significar "não tiramos mais o
    acesso", que é o oposto do que o mantenedor pediu.
    """
    alvo = criar()
    porta_da_caixa = f"/api/alunos/alunos/{ALGUEM}/matriculas"
    assert client.get(porta_da_caixa, **auth).status_code == 200

    resposta = client.patch(
        f"{MATRICULAS}/{alvo.pk}",
        data=json.dumps(
            {"status": Matricula.STATUS_ENCERRADA, "decidido_por": "id-do-admin"}
        ),
        content_type="application/json",
        **auth,
    )

    assert resposta.status_code == 200
    assert client.get(porta_da_caixa, **auth).status_code == 404
    alvo.refresh_from_db()
    assert alvo.status == Matricula.STATUS_ENCERRADA
    assert alvo.name == "Quem Voltou", "a ficha continua inteira"


# ------------------------------------------- 2. a ficha antiga sobrevive à volta


@pytest.mark.django_db
def test_a_ficha_encerrada_sobrevive_a_volta(client, auth):
    """Duas passagens, duas fichas — e o prontuário conta as duas em ordem.

    A alternativa recusada pelo mantenedor era reaproveitar a linha antiga.
    Ela deixaria a lista mais limpa e apagaria a data da saída no instante da
    volta: informação que, uma vez perdida, não volta.
    """
    antiga = criar(status=Matricula.STATUS_ENCERRADA)
    antiga.decidido_em = timezone.now()
    antiga.decidido_por = "id-do-admin"
    antiga.save(update_fields=["decidido_em", "decidido_por"])
    nova = na_fila()

    corpo = prontuario(client, auth).json()

    assert [p["id"] for p in corpo["passagens"]] == [
        str(antiga.pk),
        str(nova.pk),
    ], "as passagens vêm da mais antiga para a mais nova — é uma história"
    encerrada = corpo["passagens"][0]
    assert encerrada["status"] == Matricula.STATUS_ENCERRADA
    assert encerrada["decidido_em"] is not None, "a data da saída sobreviveu"
    assert encerrada["decidido_por"] == "id-do-admin"
    # E a situação de AGORA é a da linha nova, não a da antiga.
    assert corpo["categoria"] == "na_fila"


@pytest.mark.django_db
def test_o_prontuario_de_quem_a_celula_nao_conhece_e_vazio_e_nao_erro(client, auth):
    """404 aqui obrigaria cada consumidor a traduzir "erro" em "pessoa nova".

    O primeiro que tratasse isso como falha de rede mostraria a tela errada.
    """
    resposta = prontuario(client, auth, email="ninguem@example.com")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["passagens"] == []
    assert corpo["categoria"] == "cadastrado"
    assert corpo["nome_completo"] == ""


@pytest.mark.django_db
def test_o_prontuario_mostra_os_dados_da_passagem_mais_recente(client, auth):
    """Quem volta anos depois pode ter mudado de nome e de telefone.

    O que o mantenedor precisa para falar com a pessoa é o dado de hoje — e o
    de ontem continua visível, dentro da passagem a que pertence.
    """
    criar(status=Matricula.STATUS_ENCERRADA, name="Nome Antigo", whatsapp="(96) 1111")
    na_fila(name="Nome de Hoje", whatsapp="(96) 2222")

    corpo = prontuario(client, auth).json()

    assert corpo["nome_completo"] == "Nome de Hoje"
    assert corpo["whatsapp"] == "(96) 2222"
    assert corpo["passagens"][0]["nome_completo"] == "Nome Antigo"


@pytest.mark.django_db
def test_o_prontuario_nao_ecoa_o_email_em_cada_passagem():
    """O e-mail é da PESSOA, e aparece uma vez, no topo.

    Repeti-lo em cada linha sugeriria que ele poderia ser diferente entre elas
    — e é justamente por ser a identidade que a porta de edição recusa mexer
    nele.
    """
    criar()

    corpo = prontuario_de(ALGUEM)

    assert corpo["email"] == ALGUEM
    assert "email" not in corpo["passagens"][0]


@pytest.mark.django_db
def test_o_prontuario_sem_bearer_e_recusado():
    """Porta de PAINEL: devolve WhatsApp, e por isso a mesma trava das vizinhas."""
    assert Client().get(f"/api/alunos/alunos/{ALGUEM}/prontuario").status_code == 401


# ------------------------------------------------- 3. a fila diz quem já foi aluno


@pytest.mark.django_db
def test_a_fila_diz_quem_ja_foi_aluno(client, auth):
    """A indicação que o mantenedor pediu, no corpo da porta que a tela lê."""
    antiga = criar(status=Matricula.STATUS_ENCERRADA)
    antiga.decidido_em = timezone.now()
    antiga.save(update_fields=["decidido_em"])
    na_fila()

    linha = client.get(f"{FILA}?status=aguardando", **auth).json()[0]

    assert linha["ja_foi_aluno"] is True
    assert linha["passagens_anteriores"] == 1
    assert linha["saiu_em"] is not None


@pytest.mark.django_db
def test_quem_nunca_esteve_aqui_nao_vira_ex_aluno_por_engano(client, auth):
    """O caso comum, e o que uma implementação apressada estragaria primeiro."""
    na_fila()

    linha = client.get(f"{FILA}?status=aguardando", **auth).json()[0]

    assert linha["ja_foi_aluno"] is False
    assert linha["passagens_anteriores"] == 0
    assert linha["saiu_em"] is None


@pytest.mark.django_db
def test_ja_foi_aluno_nao_e_ja_teve_ficha(client, auth):
    """A distinção que um `.exists()` apressado apagaria.

    Quem foi recusado e nunca liberado tem ficha e **nunca** foi aluno. Mostrar
    a tarja de ex-aluno para essa pessoa faria o mantenedor tratá-la como
    alguém que ele conhece.

    As recusas moram em OUTRAS escolas, e não é enfeite de teste: a constraint
    parcial `matricula_unica_na_fila_por_site_e_email` impede duas linhas em
    espera no mesmo site — quem é recusado e pede de novo reaproveita a própria
    linha (`entrar_na_fila`). Fichas de fila repetidas para a mesma pessoa só
    existem entre escolas diferentes, e a plataforma é multi-escola (Lei 9).
    """
    criar(site_id="escola-b", order_id="pre:r1", status=Matricula.STATUS_RECUSADA)
    criar(site_id="escola-c", order_id="pre:r2", status=Matricula.STATUS_RECUSADA)
    na_fila()

    linha = client.get(f"{FILA}?status=aguardando", **auth).json()[0]

    assert linha["ja_foi_aluno"] is False, "recusa não é passagem pela escola"
    assert linha["passagens_anteriores"] == 2, "mas as tentativas anteriores contam"


@pytest.mark.django_db
def test_a_fila_nao_pergunta_o_passado_uma_vez_por_linha(
    client, auth, django_assert_num_queries
):
    """O N+1 que só aparece quando a fila cresce — ou seja, quando ela importa.

    O número exato não é o ponto (ele muda com qualquer refatoração honesta); o
    ponto é que ele NÃO cresce com o tamanho da fila. Por isso o teste mede a
    mesma tela com três pessoas e com seis.
    """
    for i in range(3):
        na_fila(email=f"pessoa{i}@example.com")

    with django_assert_num_queries(2) as tres:
        client.get(f"{FILA}?status=aguardando", **auth)

    for i in range(3, 6):
        na_fila(email=f"pessoa{i}@example.com")

    with django_assert_num_queries(len(tres.captured_queries)):
        client.get(f"{FILA}?status=aguardando", **auth)
