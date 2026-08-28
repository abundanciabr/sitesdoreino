"""As cinco categorias de usuário — `docs/decisoes/DECISAO-categorias-de-usuario.md`.

Esta célula responde por TRÊS delas (`cadastrado`, `na_fila`, `aluno`), e a
ausência das outras duas é medida aqui: `visitante` não chega (não há e-mail), e
`administrador` mora na lista da célula `admin`. Uma porta que respondesse
"administrador" faria a autorização da área administrativa depender de uma
célula de produto — o inverso de *reconhecer não é autorizar*.

**Os dois testes que carregam o arquivo**, e nenhum dos dois é "a porta
responde":

1. `test_quem_a_celula_nao_conhece_e_cadastrado_com_200_e_nunca_404`. É a
   decisão mais importante do contrato. Um 404 aqui obrigaria cada consumidor a
   traduzir "erro" em "cadastrado" por conta própria — e o primeiro que
   tratasse 404 como falha de rede mostraria a tela errada, **fail-OPEN**, para
   todo visitante novo do site. O teste trava o 200.

2. `test_a_resposta_nao_carrega_nenhum_dado_pessoal`. A §5 da lei da fila
   promete que o WhatsApp sai por UMA porta só. Uma promessa dessas some no
   primeiro campo acrescentado por conveniência, então a asserção é de
   **conjunto EXATO de chaves**, e não "whatsapp não está aí": campo novo — com
   qualquer nome — fica vermelho até alguém decidir explicitamente.

E `test_aguardando_nao_e_aluno_nesta_porta_tambem` é a lei §3 reafirmada no
lugar novo: a consulta de acesso já a respeita, mas esta porta é uma SEGUNDA
oportunidade de o mesmo erro nascer, e ela é medida por si.
"""

import json

import pytest
from django.utils import timezone

from apps.matriculas.models import Matricula
from apps.matriculas.services import situacao_de

SITUACAO = "/api/alunos/alunos/{email}/situacao"
ALGUEM = "alguem@example.com"

# As chaves que a resposta pode ter, e NADA além delas. Escritas à mão aqui, e
# não derivadas do código: um inventário que perguntasse ao próprio handler
# quais chaves ele devolve concordaria com qualquer vazamento futuro.
CHAVES_DO_TOPO = {"categoria", "na_fila"}
CHAVES_DA_FILA = {"estado", "esperando_ha_dias", "motivo_recusa"}

# Tudo que NÃO pode aparecer, em nenhum nível. Redundante com o conjunto exato
# acima de propósito: se alguém um dia afrouxar aquela asserção, esta continua
# nomeando o dado que a lei protege.
PROIBIDAS = {"whatsapp", "nome_completo", "name", "email", "turma", "comprou_em"}


@pytest.fixture
def token_valido(settings):
    settings.TOKENS_ACEITOS = {"token-de-teste"}
    return "token-de-teste"


@pytest.fixture
def auth(token_valido):
    return {"HTTP_AUTHORIZATION": f"Bearer {token_valido}"}


def perguntar(client, auth, email=ALGUEM):
    return client.get(SITUACAO.format(email=email), **auth)


def linha(**campos):
    corpo = {
        "site_id": "site-1",
        "order_id": f"pedido-{campos.get('status', 'x')}-{timezone.now().timestamp()}",
        "email": ALGUEM,
        "name": "Quem Quer Que Seja",
        "status": Matricula.STATUS_ATIVA,
    }
    corpo.update(campos)
    return Matricula.objects.create(**corpo)


# ------------------------------------------------- a decisão do 200, não 404


@pytest.mark.django_db
def test_quem_a_celula_nao_conhece_e_cadastrado_com_200_e_nunca_404(client, auth):
    resposta = perguntar(client, auth)
    assert resposta.status_code == 200, resposta.content
    assert resposta.json() == {"categoria": "cadastrado", "na_fila": None}


@pytest.mark.django_db
def test_a_porta_vizinha_continua_dando_404_e_a_diferenca_e_deliberada(client, auth):
    """As duas portas discordam de propósito, e o teste registra isso.

    `GET /alunos/{email}/matriculas` responde 404 para desconhecido e está
    certa: lá a pergunta é "quais são as matrículas desta pessoa?", e não haver
    nenhuma é ausência de recurso. Aqui a pergunta é "em que categoria ela
    está?", e "nenhuma linha" É a resposta. Sem este teste, a próxima sessão
    olharia as duas e "uniformizaria" uma delas.
    """
    vizinha = client.get(f"/api/alunos/alunos/{ALGUEM}/matriculas", **auth)
    assert vizinha.status_code == 404
    assert perguntar(client, auth).status_code == 200


# ------------------------------------------------------------------ aluno


@pytest.mark.django_db
@pytest.mark.parametrize("status", list(Matricula.STATUS_QUE_VALEM))
def test_todo_status_que_vale_responde_aluno(client, auth, status):
    """Derivado da constante, e não de uma lista escrita à mão.

    Até 28/08/2026 esta lista era `[ativa, suspensa, reembolsada]`, escrita à
    mão — e quando `suspensa` deixou de dar acesso
    (`DECISAO-gestao-de-alunos` §2) o teste reprovou por estar REPETINDO a
    regra em vez de a consultar. Derivando, ele mede a regra verdadeira, seja
    qual for ela amanhã.

    `reembolsada` continuar valendo é decisão de 24/08/2026, não descuido:
    quem já foi aluno mantém a voz na Caixa.
    """
    linha(status=status)
    assert perguntar(client, auth).json() == {"categoria": "aluno", "na_fila": None}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "status", [Matricula.STATUS_SUSPENSA, Matricula.STATUS_ENCERRADA]
)
def test_pausado_e_encerrado_nao_sao_aluno(client, auth, status):
    """O outro lado da mudança de 28/08, e o que a torna real.

    Sem este teste, tirar `suspensa` de `STATUS_QUE_VALEM` teria como única
    prova um teste que *não a menciona mais* — e ausência de asserção não é
    asserção. Aqui está dito com todas as letras: pausado e encerrado NÃO são
    aluno, e é isso que faz o botão "pausar" valer alguma coisa.
    """
    linha(status=status, order_id=f"pedido-{status}")
    assert perguntar(client, auth).json()["categoria"] != "aluno"


@pytest.mark.django_db
def test_a_categoria_sai_da_mesma_lista_que_decide_acesso():
    """Uma segunda lista de status seriam duas verdades sobre quem é aluno.

    Medido pela consequência: qualquer status de `STATUS_QUE_VALEM` responde
    `aluno`, e nenhum de `STATUS_DA_FILA` responde. Se alguém acrescentar um
    status novo à lista de permissão sem pensar nesta porta, este teste
    continua correto — porque ele deriva das MESMAS constantes.
    """
    for status in Matricula.STATUS_QUE_VALEM:
        Matricula.objects.all().delete()
        linha(status=status)
        assert situacao_de(ALGUEM)["categoria"] == "aluno", status
    for status in Matricula.STATUS_DA_FILA:
        Matricula.objects.all().delete()
        linha(status=status, order_id=f"pre:{status}")
        assert situacao_de(ALGUEM)["categoria"] != "aluno", status


# ------------------------------------------------------------------ na fila


@pytest.mark.django_db
def test_quem_espera_e_na_fila_com_os_dias_contados(client, auth):
    m = linha(status=Matricula.STATUS_AGUARDANDO, order_id="pre:1")
    Matricula.objects.filter(pk=m.pk).update(
        enrolled_at=timezone.now() - timezone.timedelta(days=5)
    )
    corpo = perguntar(client, auth).json()
    assert corpo["categoria"] == "na_fila"
    assert corpo["na_fila"]["estado"] == "aguardando"
    assert corpo["na_fila"]["esperando_ha_dias"] == 5
    assert corpo["na_fila"]["motivo_recusa"] is None


@pytest.mark.django_db
def test_quem_foi_recusado_ve_o_motivo_e_para_de_contar_dias(client, auth):
    """`esperando_ha_dias` vira `null` depois de decidida.

    Um número que continuasse subindo seria lido como "meu pedido está parado
    há 40 dias" por quem, na verdade, já foi respondido — e a pessoa precisa do
    MOTIVO para poder pedir de novo (lei da fila §7).
    """
    linha(
        status=Matricula.STATUS_RECUSADA,
        order_id="pre:2",
        motivo_recusa="não achei sua compra",
    )
    corpo = perguntar(client, auth).json()
    assert corpo["categoria"] == "na_fila"
    assert corpo["na_fila"]["estado"] == "recusada"
    assert corpo["na_fila"]["esperando_ha_dias"] is None
    assert corpo["na_fila"]["motivo_recusa"] == "não achei sua compra"


@pytest.mark.django_db
def test_aguardando_nao_e_aluno_nesta_porta_tambem():
    """A lei §3, reafirmada no lugar novo.

    A consulta de acesso já exclui `aguardando` — mas esta porta é uma SEGUNDA
    chance de o mesmo erro nascer, escrita meses depois por outra pessoa. Um
    `aluno` aqui não abriria a Caixa (quem decide é a outra consulta), mas
    esconderia da home o pedido em análise e mostraria o botão de aluno para
    quem não é.
    """
    linha(status=Matricula.STATUS_AGUARDANDO, order_id="pre:3")
    assert situacao_de(ALGUEM)["categoria"] == "na_fila"


@pytest.mark.django_db
def test_ser_aluno_vence_uma_linha_antiga_de_espera():
    """A ordem de conferência é a decisão: matrícula que vale ganha da fila."""
    linha(status=Matricula.STATUS_AGUARDANDO, order_id="pre:4")
    linha(status=Matricula.STATUS_ATIVA, order_id="pedido-real-1")
    assert situacao_de(ALGUEM) == {"categoria": "aluno", "na_fila": None}


@pytest.mark.django_db
def test_a_linha_mais_recente_e_a_que_conta_entre_sites(client, auth):
    """Duas linhas de fila só existem em SITES diferentes — e vale a de agora.

    No mesmo site elas são impossíveis por MECANISMO: a `UniqueConstraint`
    parcial de `Matricula` cobre `STATUS_DA_FILA` inteiro, então quem foi
    recusado e pede de novo **atualiza a mesma linha** (`entrar_na_fila` é
    idempotente por `(site_id, email)`), não cria uma segunda — e isso já tem
    guarda em `test_fila_de_liberacao.py::test_duas_linhas_na_fila_para_o_mesmo_par_sao_impossiveis`,
    que não se repete aqui.

    Este teste exercita o único caso em que a ordenação decide alguma coisa, e
    é o que justifica o `order_by("-enrolled_at")` existir em vez de um
    `.first()` qualquer.
    """
    antiga = linha(
        site_id="outra-escola",
        status=Matricula.STATUS_RECUSADA,
        order_id="pre:5",
        motivo_recusa="faltou dado",
    )
    Matricula.objects.filter(pk=antiga.pk).update(
        enrolled_at=timezone.now() - timezone.timedelta(days=30)
    )
    linha(status=Matricula.STATUS_AGUARDANDO, order_id="pre:6")
    assert perguntar(client, auth).json()["na_fila"]["estado"] == "aguardando"


# --------------------------------------------------------------------- PII


@pytest.mark.django_db
@pytest.mark.parametrize(
    "status",
    [
        Matricula.STATUS_ATIVA,
        Matricula.STATUS_AGUARDANDO,
        Matricula.STATUS_RECUSADA,
        None,
    ],
)
def test_a_resposta_nao_carrega_nenhum_dado_pessoal(client, auth, status):
    """Conjunto EXATO de chaves, nos quatro estados possíveis da resposta."""
    if status is not None:
        linha(
            status=status,
            order_id=f"pre:{status}",
            whatsapp="(96) 99999-0000",
            turma="turma-1",
            motivo_recusa="qualquer",
        )
    corpo = perguntar(client, auth).json()
    assert set(corpo) == CHAVES_DO_TOPO, corpo
    if corpo["na_fila"] is not None:
        assert set(corpo["na_fila"]) == CHAVES_DA_FILA, corpo

    cru = json.dumps(corpo, ensure_ascii=False)
    for proibida in PROIBIDAS:
        assert proibida not in cru, f"{proibida} vazou: {cru}"
    assert "99999" not in cru
    assert ALGUEM not in cru


# ------------------------------------------------------- a borda da internet


@pytest.mark.django_db
def test_sem_bearer_a_porta_recusa_com_401():
    """Esta API é alcançável pela internet, e o token é a única defesa.

    O Traefik NÃO remove o prefixo das células sob `SCRIPT_NAME`
    (`armadilhas/103`): `/alunos/api/alunos/...` responde de fora. Medido em
    25/08/2026. Porta nova nasce com este guarda ou nasce aberta.
    """
    from django.test import Client

    assert Client().get(SITUACAO.format(email=ALGUEM)).status_code == 401


@pytest.mark.django_db
def test_email_malformado_e_422_e_nao_cadastrado(client, auth):
    """422, e explicitamente NÃO 200 `cadastrado`.

    Confundir "seu pedido está errado" com "esta pessoa não tem matrícula"
    faria o consumidor tratar o próprio bug como um fato sobre uma pessoa — e
    o sintoma seria uma tela plausível, nunca um erro.
    """
    resposta = perguntar(client, auth, email="isto-nao-e-email")
    assert resposta.status_code == 422, resposta.content
