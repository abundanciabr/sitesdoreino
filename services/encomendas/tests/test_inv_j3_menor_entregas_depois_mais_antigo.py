"""[INV-ENC-J3] A oferta vai ao elegível de menor `(entregas_aprovadas, data_entrada_fila)`.

Lei: `docs/decisoes/DECISAO-fila-do-primeiro-dolar.md` §5 (justiça) e §9
(critério de morte 2). Produto: `PLANO-MESTRE-FILA-DO-PRIMEIRO-DOLAR.md` §6.2.

Este é o invariante do produto inteiro. A promessa da Fila do Primeiro Dólar não
é "há trabalho": é **"quem nunca entregou passa na frente"**. Tirar a primeira
metade da chave, ou pôr qualquer coisa antes dela, faz a fila virar exatamente o
marketplace que este produto existe para não ser — o lugar onde quem já tem
portfólio recebe mais trabalho e quem não tem nunca começa.

E é o invariante mais fácil de erodir sem má intenção. Uma segunda regra de
ordem (peso, prioridade paga, "destaque", afinidade de categoria, nota) parece
uma boa ideia numa tarde qualquer, e é o **critério de morte 2** da lei §9: pare
e reabra a decisão com o mantenedor.

Por isso o guarda tem duas naturezas. Ele mede o COMPORTAMENTO (quem recebeu, em
cinco cenários) e mede a FORMA (a chave de ordenação tem exatamente três termos,
os dois da lei e o desempate). Só o comportamento deixaria passar um quarto
termo que ainda não mudou nenhum resultado; só a forma não provaria que a ordem
dos dois primeiros é a certa.
"""

from datetime import datetime, timedelta, timezone as fuso

from apps.encomendas import motor
from apps.encomendas.models import Oferta

SITE = "escola-a"
AGORA = datetime.now(tz=fuso.utc)


def _candidato(perfil_id, *, entregas, dias_na_fila):
    return motor.Candidato(
        perfil_id=perfil_id,
        titulo_banca="nivel_1",
        disponibilidade="disponivel",
        entregas_aprovadas=entregas,
        data_entrada_fila=AGORA - timedelta(days=dias_na_fila),
        tem_oferta_pendente=False,
    )


REGRAS = motor.Regras(
    entregas_minimas_por_nivel={"iniciante": 0, "intermediario": 1, "avancado": 5},
    janela_sem_abandono_dias=90,
)
VAGA = motor.Vaga(encomenda_id="v", nivel="iniciante")


# ---------------------------------------------------------------------------
# 1. A regra, no miolo puro — sem banco, porque a justiça não depende de SQL
# ---------------------------------------------------------------------------


def test_menos_entregas_vence_quem_esperou_mais():
    """A PRIMEIRA metade da regra, e a que carrega a promessa do produto.

    O veterano está na fila há um ano; o novato entrou ontem. O novato leva,
    porque tem zero entregas. Inverter isto é inverter o produto.
    """
    veterano = _candidato(1, entregas=7, dias_na_fila=365)
    novato = _candidato(2, entregas=0, dias_na_fila=1)

    escolha = motor.escolher(VAGA, [veterano, novato], REGRAS, AGORA)

    assert escolha.escolhido.perfil_id == novato.perfil_id


def test_no_empate_de_entregas_vence_quem_entrou_antes():
    """A SEGUNDA metade: o desempate da lei, e não o do banco."""
    antigo = _candidato(1, entregas=2, dias_na_fila=100)
    recente = _candidato(2, entregas=2, dias_na_fila=3)

    escolha = motor.escolher(VAGA, [recente, antigo], REGRAS, AGORA)

    assert escolha.escolhido.perfil_id == antigo.perfil_id


def test_a_ordem_dos_dois_termos_e_essa_e_nao_a_inversa():
    """O cenário que separa a regra certa da regra plausível.

    Se a chave fosse `(data_entrada_fila, entregas_aprovadas)` — igualmente
    "justa" à primeira vista — o veterano de 365 dias levaria tudo, para sempre.
    Este teste é o único que fica vermelho com essa troca.
    """
    veterano = _candidato(1, entregas=9, dias_na_fila=365)
    meio = _candidato(2, entregas=3, dias_na_fila=200)
    novato = _candidato(3, entregas=0, dias_na_fila=1)

    ordem = motor.elegiveis(VAGA, [veterano, meio, novato], REGRAS, AGORA)

    assert [c.perfil_id for c in ordem] == [3, 2, 1]


def test_a_ordem_nao_depende_da_ordem_de_entrada():
    """O motor é FUNÇÃO do estado, e função não muda de resposta por embaralhar.

    A consulta ao banco não promete ordem sem `ORDER BY`; o dia em que ela
    mudar, a fila mudaria de resposta em silêncio, sem uma linha de diff.
    """
    tres = [
        _candidato(1, entregas=1, dias_na_fila=10),
        _candidato(2, entregas=0, dias_na_fila=5),
        _candidato(3, entregas=1, dias_na_fila=50),
    ]
    esperado = [c.perfil_id for c in motor.elegiveis(VAGA, tres, REGRAS, AGORA)]

    for embaralhado in ([tres[2], tres[0], tres[1]], list(reversed(tres))):
        atual = motor.elegiveis(VAGA, embaralhado, REGRAS, AGORA)
        assert [c.perfil_id for c in atual] == esperado


def test_empate_total_ainda_da_uma_resposta_so():
    """Dois perfis idênticos ao microssegundo: a escolha continua determinística.

    O terceiro termo da chave não é uma segunda regra de ordem — ele só é
    consultado quando os dois da lei empataram, e existe para a fila não passar
    a depender da ordem em que o PostgreSQL devolveu as linhas.
    """
    a = _candidato(41, entregas=0, dias_na_fila=7)
    b = _candidato(17, entregas=0, dias_na_fila=7)

    assert motor.escolher(VAGA, [a, b], REGRAS, AGORA).escolhido.perfil_id == 17
    assert motor.escolher(VAGA, [b, a], REGRAS, AGORA).escolhido.perfil_id == 17


# ---------------------------------------------------------------------------
# 2. A FORMA da chave — o dente contra o critério de morte 2
# ---------------------------------------------------------------------------


def test_a_chave_de_ordem_tem_os_dois_termos_da_lei_e_um_desempate():
    """Termo a mais é uma segunda regra de ordem, e isso é critério de morte.

    A régua é de FORMA e não de efeito, de propósito: um quarto termo pode
    passar meses sem mudar nenhum resultado (porque os três primeiros quase
    nunca empatam) e mesmo assim já ser a prioridade paga esperando o dia em que
    alguém a ligue. Quem acrescentar um termo aqui reprova antes de escrever a
    tela que o venderia.
    """
    candidato = _candidato(5, entregas=2, dias_na_fila=9)
    chave = motor.CHAVE_DA_ORDEM(candidato)

    assert len(chave) == 3
    assert chave[0] == candidato.entregas_aprovadas
    assert chave[1] == candidato.data_entrada_fila
    assert chave[2] == candidato.perfil_id


def test_o_candidato_nao_tem_onde_guardar_um_peso():
    """Garantia por AUSÊNCIA: o que não se pode nomear não se pode ordenar.

    A forma de `Candidato` é fechada. Nenhum campo de peso, prioridade,
    destaque, nota, patrocínio ou afinidade — e um motor que quisesse ordenar
    por isso teria de acrescentar o campo AQUI, onde a CI recusa. É a mesma
    técnica do [INV-GAM2]: o cosmético que não tem onde guardar um
    multiplicador não multiplica nada.
    """
    campos = set(motor.Candidato.__dataclass_fields__)
    vocabulario_da_vantagem = {
        "peso",
        "prioridade",
        "destaque",
        "nota",
        "score",
        "pontuacao",
        "ranking",
        "patrocinio",
        "afinidade",
        "boost",
        "nivel_de_prioridade",
    }

    assert campos & vocabulario_da_vantagem == set()


# ---------------------------------------------------------------------------
# 3. A mesma regra, atravessando o banco
# ---------------------------------------------------------------------------


def test_a_encomenda_real_vai_para_quem_tem_menos_entregas(
    semeado, criar_perfil, criar_encomenda
):
    """A prova de ponta a ponta: banco, motor, `Oferta` gravada."""
    criar_perfil("pes-veterano", entrada=AGORA - timedelta(days=300), entregas=4)
    novato = criar_perfil("pes-novato", entrada=AGORA - timedelta(days=1), entregas=0)

    encomenda = criar_encomenda()
    motor.rodar(AGORA, site_id=SITE)

    assert Oferta.objects.get(encomenda=encomenda).aluno_id == novato.id


def test_tres_encomendas_descem_a_fila_em_ordem(tres_na_fila, criar_encomenda):
    """Três encomendas numa passada servem os três primeiros da fila, em ordem.

    É o cenário 1 do anexo B do plano, e o que a tela do plantão vai mostrar num
    dia normal. Ana (30 dias), Bia (20), Caio (10): todos com zero entregas,
    então a data manda, e a ordem de recebimento é essa.
    """
    ana, bia, caio = tres_na_fila
    primeira = criar_encomenda(cliente="cli-1")
    segunda = criar_encomenda(cliente="cli-2")
    terceira = criar_encomenda(cliente="cli-3")

    motor.rodar(AGORA, site_id=SITE)

    assert Oferta.objects.get(encomenda=primeira).aluno_id == ana.id
    assert Oferta.objects.get(encomenda=segunda).aluno_id == bia.id
    assert Oferta.objects.get(encomenda=terceira).aluno_id == caio.id
