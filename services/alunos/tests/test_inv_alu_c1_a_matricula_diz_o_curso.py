"""[INV-ALU-C1] Nenhuma matrícula ativa sem curso.

Lei: `docs/decisoes/DECISAO-cursos-matriculas-e-alunos.md` (06/09/2026), nas
palavras do mantenedor: *"eu preciso que ele seja liberado somente após escolher
o curso no qual ele está matriculado"*. Ninguém é aluno do site: todo mundo é
aluno de UM curso, e a matrícula é o que diz qual.

AS QUATRO COISAS QUE ESTE ARQUIVO TRAVA
----------------------------------------
1. **Liberar sem curso é recusado NA PORTA, com frase em português, e sem efeito
   nenhum.** Não basta o 422: a linha tem de continuar `aguardando`. Um 422 que
   liberasse assim mesmo seria o pior desfecho possível, porque a tela mostraria
   erro e a pessoa entraria.
2. **Liberar com curso grava o curso na MESMA transação do status.** É a metade
   positiva, e sem ela a primeira asserção passaria por verdade vazia (recusar
   tudo também faz "nunca há ativa sem curso").
3. **Recusar não pede curso e não grava curso.** Quem foi recusado não é aluno
   de nada, e exigir a escolha de um curso para dizer "não" seria burocracia sem
   fato por trás.
4. **Esta célula não tem tabela de cursos** (lei §7). A lista de cursos é do
   `catalogo`; a matrícula guarda a REFERÊNCIA. O guarda é por igualdade exata
   do inventário de modelos da célula: uma tabela nova reprova aqui e obriga
   quem a criou a justificar, em vez de duas listas de cursos divergirem no
   primeiro curso novo.

O QUE ESTE ARQUIVO NÃO ALCANÇA, E ESTÁ DITO NA CARA
----------------------------------------------------
A matrícula que nasce do EVENTO de pagamento. `pagamento.aprovado.v1` não
carrega `product_id` (medido em `contracts/eventos/`), então `handlers.py` grava
`""` e a linha nasce `ativa` sem curso sem passar pela decisão da fila. Fechar
essa metade é Rito de Contrato no evento, e o evento é de outra célula. O
guarda existe assim mesmo porque a metade que ele cobre é a que o mantenedor
opera com a mão, todo dia, e é a que a lei nomeia.
"""

import io
import json

import pytest
from django.apps import apps
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.matriculas.handlers import ao_pagamento_aprovado
from apps.matriculas.models import Matricula
from apps.matriculas.services import decidir_na_fila, entrar_na_fila

PRE_MATRICULAS = "/api/alunos/pre-matriculas"

# O curso 1 da escola (lei §5, "Primeiros Dólares com Roblox") é uma linha do
# `catalogo`, e o id dela é dado de produção. Aqui vale qualquer texto opaco: o
# que se prova é que a matrícula guarda o que recebeu, não qual é o valor.
CURSO = "produto-do-curso-1"


@pytest.fixture
def auth(settings):
    settings.TOKENS_ACEITOS = {"token-de-teste"}
    return {"HTTP_AUTHORIZATION": "Bearer token-de-teste"}


def decidir(client, auth, linha, corpo):
    return client.post(
        f"{PRE_MATRICULAS}/{linha.pk}/decisao",
        data=json.dumps(corpo),
        content_type="application/json",
        **auth,
    )


def na_fila():
    linha, _ = entrar_na_fila(
        site_id="site-1",
        email="quem-espera@example.com",
        nome_completo="Quem Espera",
        whatsapp="(96) 99999-0000",
    )
    return linha


# ---------------------------------------------------------------------------
# 1. Liberar sem curso: 422, em português, e ZERO efeito
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_liberar_sem_curso_e_recusado_com_frase_em_portugues(client, auth):
    linha = na_fila()

    resposta = decidir(
        client, auth, linha, {"decisao": "liberar", "decidido_por": "idt-do-mantenedor"}
    )

    assert resposta.status_code == 422
    # A frase diz o que faltou E o que fazer: quem lê é o mantenedor, na tela de
    # liberar, e ele é leigo em código.
    detalhe = resposta.json()["detail"]
    assert "curso" in detalhe
    assert "product_id" in detalhe

    linha.refresh_from_db()
    assert linha.status == Matricula.STATUS_AGUARDANDO
    assert linha.product_id == ""


@pytest.mark.django_db
def test_liberar_com_curso_em_branco_e_a_mesma_recusa(client, auth):
    """Mandar a chave com texto vazio (ou só espaços) não é dizer o curso.

    É o caminho por onde um formulário com o campo em branco entraria: sem esta
    metade, `product_id=""` viraria uma matrícula ativa sem curso E com a chave
    presente, que passa por qualquer conferência de forma.
    """
    linha = na_fila()

    resposta = decidir(
        client,
        auth,
        linha,
        {
            "decisao": "liberar",
            "decidido_por": "idt-do-mantenedor",
            "product_id": "   ",
        },
    )

    assert resposta.status_code == 422
    linha.refresh_from_db()
    assert linha.status == Matricula.STATUS_AGUARDANDO


# ---------------------------------------------------------------------------
# 2. Liberar COM curso: a metade positiva, sem a qual a de cima é vazia
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_liberar_com_curso_grava_o_curso_na_matricula(client, auth):
    linha = na_fila()

    resposta = decidir(
        client,
        auth,
        linha,
        {
            "decisao": "liberar",
            "decidido_por": "idt-do-mantenedor",
            "product_id": CURSO,
        },
    )

    assert resposta.status_code == 200
    linha.refresh_from_db()
    assert linha.status == Matricula.STATUS_ATIVA
    assert linha.product_id == CURSO


@pytest.mark.django_db
def test_nenhuma_matricula_que_vale_fica_sem_curso_depois_de_liberar():
    """A varredura universal, e não um caso.

    Ela mede o invariante como ele está escrito ("nenhuma matrícula em status que
    dá acesso aponta para curso nenhum") em vez de medir a linha que o teste
    acabou de mexer. Uma liberação futura que grave o curso pela metade cai aqui
    mesmo que ninguém volte para escrever a asserção.
    """
    liberada = na_fila()
    decidir_na_fila(
        id_da_linha=str(liberada.pk),
        decisao="liberar",
        decidido_por="idt-do-mantenedor",
        product_id=CURSO,
    )
    recusada, _ = entrar_na_fila(
        site_id="site-1",
        email="outra@example.com",
        nome_completo="Outra Pessoa",
        whatsapp="(96) 99999-0001",
    )
    decidir_na_fila(
        id_da_linha=str(recusada.pk),
        decisao="recusar",
        decidido_por="idt-do-mantenedor",
        motivo="não é aluno",
    )

    sem_curso = Matricula.objects.filter(
        status__in=Matricula.STATUS_QUE_VALEM, product_id=""
    )
    assert list(sem_curso) == []
    # Verdade vazia é o modo de falha desta varredura: sem alguém `ativa` no
    # banco, "ninguém está ativa sem curso" passa sozinho (`armadilhas/266`).
    assert Matricula.objects.filter(status__in=Matricula.STATUS_QUE_VALEM).count() == 1


# ---------------------------------------------------------------------------
# 3. Recusar não pede curso, e não grava curso
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_recusar_nao_pede_curso(client, auth):
    linha = na_fila()

    resposta = decidir(
        client,
        auth,
        linha,
        {
            "decisao": "recusar",
            "decidido_por": "idt-do-mantenedor",
            "motivo": "não achei na lista",
        },
    )

    assert resposta.status_code == 200
    linha.refresh_from_db()
    assert linha.status == Matricula.STATUS_RECUSADA
    assert linha.product_id == ""


@pytest.mark.django_db
def test_curso_mandado_junto_de_uma_recusa_nao_e_gravado(client, auth):
    """Recusar com curso é aceito e o curso é ignorado, como `motivo` na liberação.

    Gravar o curso aqui marcaria como aluna de um curso uma pessoa que a escola
    acabou de dizer que não é aluna de nada.
    """
    linha = na_fila()

    resposta = decidir(
        client,
        auth,
        linha,
        {
            "decisao": "recusar",
            "decidido_por": "idt-do-mantenedor",
            "motivo": "não achei na lista",
            "product_id": CURSO,
        },
    )

    assert resposta.status_code == 200
    linha.refresh_from_db()
    assert linha.product_id == ""


# ---------------------------------------------------------------------------
# 4. Nenhuma tabela de cursos nesta célula (lei §7)
# ---------------------------------------------------------------------------


def test_esta_celula_nao_tem_tabela_de_cursos():
    """Inventário por IGUALDADE, nunca por lista de proibidos.

    Uma lista de nomes proibidos (`Curso`, `Produto`, ...) seria furada pelo
    primeiro nome que ninguém imaginou. Por igualdade, QUALQUER tabela nova
    reprova, e quem a criar precisa passar por aqui e dizer o que ela é.
    """
    daqui = {
        modelo.__name__
        for modelo in apps.get_models()
        if modelo._meta.app_config.name.startswith("apps.")
    }
    assert daqui == {"Matricula", "OutboxEvent", "EventoProcessado"}, (
        "tabela nova na célula `alunos`. Se for lista de cursos, ela não pode "
        "existir aqui: a lista é do `catalogo`, e a matrícula guarda a "
        "referência (`Matricula.product_id`), nunca a cópia. Lei: "
        "docs/decisoes/DECISAO-cursos-matriculas-e-alunos.md §7."
    )


# ---------------------------------------------------------------------------
# 5. O acerto das matrículas que já existiam quando a lei nasceu
# ---------------------------------------------------------------------------
#
# Os testes daqui para baixo FABRICAM O ESTADO DE PRODUÇÃO antes de medir: uma
# matrícula que dá acesso com `product_id=""`. É o estado real do banco em
# 06/09/2026, e ele não nasce mais pela porta da fila (a decisão passou a exigir
# o curso) — corrigir o código não muda a linha que já está gravada
# (`armadilhas/253`), e é por isso que o comando existe.


def ja_matriculada(email, *, site="site-1", status=Matricula.STATUS_ATIVA, curso=""):
    """Uma matrícula como as de antes da lei: dá acesso e não diz o curso."""
    return Matricula.objects.create(
        site_id=site,
        order_id=f"pedido-de-antes-{email}",
        product_id=curso,
        email=email,
        name="Aluna de Antes",
        status=status,
    )


def acertar(**opcoes):
    saida = io.StringIO()
    call_command("apontar_o_curso_das_matriculas", stdout=saida, **opcoes)
    return saida.getvalue()


@pytest.mark.django_db
def test_o_comando_grava_o_curso_nas_matriculas_que_ja_existiam():
    antiga = ja_matriculada("aluna-de-antes@example.com")
    assert antiga.product_id == ""

    saida = acertar(site="site-1", curso=CURSO, confirmar=True)

    antiga.refresh_from_db()
    assert antiga.product_id == CURSO
    assert "1 matrícula(s)" in saida


@pytest.mark.django_db
def test_a_matricula_que_o_pagamento_cria_hoje_tambem_e_alcancada():
    """O buraco que o guarda da porta não fecha, e o comando fecha para o passado.

    `pagamento.aprovado.v1` não carrega `product_id`, então o consumer grava `""`
    e a linha nasce `ativa` sem curso sem passar pela decisão da fila. Este teste
    usa o caminho REAL do pagamento para fabricar a linha, e não um `create()`
    conveniente: é a única forma de provar que o comando alcança o que o sistema
    de verdade produz.
    """
    ao_pagamento_aprovado(
        {
            "site_id": "site-1",
            "order_id": "pedido-que-veio-do-evento",
            "customer": {"email": "comprou@example.com", "name": "Comprou"},
        }
    )
    comprada = Matricula.objects.get(order_id="pedido-que-veio-do-evento")
    assert comprada.status == Matricula.STATUS_ATIVA
    assert comprada.product_id == ""

    acertar(site="site-1", curso=CURSO, confirmar=True)

    comprada.refresh_from_db()
    assert comprada.product_id == CURSO


@pytest.mark.django_db
def test_sem_confirmar_o_comando_conta_e_nao_escreve_nada():
    antiga = ja_matriculada("aluna-de-antes@example.com")

    saida = acertar(site="site-1", curso=CURSO)

    antiga.refresh_from_db()
    assert antiga.product_id == ""
    assert "NADA FOI ALTERADO" in saida
    assert "--confirmar" in saida


@pytest.mark.django_db
def test_o_comando_nunca_sobrescreve_um_curso_que_ja_esta_gravado():
    """Sobrescrever em massa apagaria a verdade de quem comprou outra coisa."""
    de_outro_curso = ja_matriculada(
        "outro-curso@example.com", curso="produto-do-curso-2"
    )

    acertar(site="site-1", curso=CURSO, confirmar=True)

    de_outro_curso.refresh_from_db()
    assert de_outro_curso.product_id == "produto-do-curso-2"


@pytest.mark.django_db
def test_o_comando_nao_atravessa_a_fronteira_de_site():
    """[INV-P11] A escola de quem roda não é a escola de todo mundo."""
    de_outra_escola = ja_matriculada("de-outra@example.com", site="site-2")

    acertar(site="site-1", curso=CURSO, confirmar=True)

    de_outra_escola.refresh_from_db()
    assert de_outra_escola.product_id == ""


@pytest.mark.django_db
def test_quem_ainda_espera_na_fila_nao_recebe_curso():
    """Quem está `aguardando` nunca foi aluno de nada: o curso dele é escolhido
    na hora de liberar, uma pessoa por vez, na tela do painel."""
    esperando = na_fila()

    acertar(site="site-1", curso=CURSO, confirmar=True)

    esperando.refresh_from_db()
    assert esperando.product_id == ""


@pytest.mark.django_db
def test_quem_teve_acesso_e_hoje_esta_pausado_tambem_recebe_o_curso():
    """O buraco que "só as ativas" deixaria aberto.

    O mantenedor pausa alguém, roda o acerto, e religa a pessoa depois: ela
    voltaria `ativa` sem curso, e o invariante estaria furado por um caminho que
    ninguém veria. "Esta pessoa comprou o curso 1" é fato histórico, e ele não
    muda quando o acesso é pausado.
    """
    pausada = ja_matriculada("pausada@example.com", status=Matricula.STATUS_SUSPENSA)
    ex_aluna = ja_matriculada("ex@example.com", status=Matricula.STATUS_ENCERRADA)

    acertar(site="site-1", curso=CURSO, confirmar=True)

    pausada.refresh_from_db()
    ex_aluna.refresh_from_db()
    assert pausada.product_id == CURSO
    assert ex_aluna.product_id == CURSO


@pytest.mark.django_db
def test_curso_em_branco_para_o_comando_antes_de_escrever():
    """Gravar curso vazio deixaria tudo como está e diria que acertou."""
    antiga = ja_matriculada("aluna-de-antes@example.com")

    with pytest.raises(CommandError, match="PAROU POR SEGURANÇA"):
        acertar(site="site-1", curso="   ", confirmar=True)

    antiga.refresh_from_db()
    assert antiga.product_id == ""


@pytest.mark.django_db
def test_rodar_de_novo_nao_muda_mais_nada():
    antiga = ja_matriculada("aluna-de-antes@example.com")
    acertar(site="site-1", curso=CURSO, confirmar=True)

    saida = acertar(site="site-1", curso=CURSO, confirmar=True)

    antiga.refresh_from_db()
    assert antiga.product_id == CURSO
    assert "Nenhuma matrícula precisa de acerto" in saida
