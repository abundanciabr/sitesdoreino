"""O motor como MÁQUINA: a função pura, os desfechos nomeados e as bordas.

Os sete `test_inv_j*.py` medem a JUSTIÇA — quem recebe e por quê. Este arquivo
mede o que sobra, e o que sobra é o que mantém a justiça de pé em produção:

- **O miolo é puro.** Sem isso, o simulador de cem alunos (degrau 2.6) precisaria
  de PostgreSQL para cada cenário, e a justiça só seria verificável de dentro.
- **Todo desfecho tem nome.** O desfecho que ninguém nomeia vira "o que sobra", e
  é ele que entope a fila em silêncio (`armadilhas/283`, medida na mensageria: a
  varredura processava sempre as mesmas linhas e quem chegou depois nunca era
  atendido, sem uma linha de erro).
- **Parâmetro ausente é recusa, não padrão.** Fail-closed na borda
  (`RETROSPECTIVA-FASE-D` §2, padrão 4).
- **A costura do relógio existe e é usada.** Foi por ela que o degrau 2.4
  trocou a conta de horas corridas pela de horas úteis sem cirurgia no meio do
  motor — e é ela que prova, pelo caminho real, que a troca de fato aconteceu.
"""

from datetime import datetime, timedelta, timezone as fuso

import pytest

from apps.encomendas import motor, relogio
from apps.encomendas.models import Encomenda, Oferta

SITE = "escola-a"
AGORA = datetime.now(tz=fuso.utc)


# ---------------------------------------------------------------------------
# 1. O miolo é função de (estado, agora), e não toca banco
# ---------------------------------------------------------------------------


def test_o_miolo_decide_sem_banco_nenhum():
    """Sem a fixture `db`: qualquer consulta aqui estouraria o teste.

    É a asserção mais barata deste arquivo e a que mais protege o degrau 2.6: um
    `escolher()` que fosse ao banco tornaria o simulador de cem alunos e trinta
    encomendas lento demais para rodar em toda CI, e ele é o PORTÃO da Fase 2.
    """
    regras = motor.Regras(
        entregas_minimas_por_nivel={"iniciante": 0, "intermediario": 1, "avancado": 5},
        janela_sem_abandono_dias=90,
    )
    candidatos = [
        motor.Candidato(
            perfil_id=i,
            titulo_banca="nivel_1",
            disponibilidade="disponivel",
            entregas_aprovadas=i,
            data_entrada_fila=AGORA - timedelta(days=i),
            tem_oferta_pendente=False,
        )
        for i in (3, 1, 2)
    ]

    escolha = motor.escolher(
        motor.Vaga(encomenda_id="v", nivel="iniciante"), candidatos, regras, AGORA
    )

    assert escolha.desfecho == motor.OFERECIDA
    assert escolha.escolhido.perfil_id == 1


def test_a_mesma_entrada_da_sempre_a_mesma_saida():
    """Função é função: mil chamadas, uma resposta."""
    regras = motor.Regras(
        entregas_minimas_por_nivel={"iniciante": 0, "intermediario": 1, "avancado": 5},
        janela_sem_abandono_dias=90,
    )
    vaga = motor.Vaga(encomenda_id="v", nivel="iniciante")
    candidatos = [
        motor.Candidato(
            perfil_id=n,
            titulo_banca="nivel_1",
            disponibilidade="disponivel",
            entregas_aprovadas=0,
            data_entrada_fila=AGORA - timedelta(days=1),
            tem_oferta_pendente=False,
        )
        for n in (7, 7, 9)
    ]

    escolhas = {
        motor.escolher(vaga, candidatos, regras, AGORA).escolhido.perfil_id
        for _ in range(50)
    }

    assert escolhas == {7}


# ---------------------------------------------------------------------------
# 2. Os cinco desfechos têm nome, e a rodada os devolve
# ---------------------------------------------------------------------------


def test_os_desfechos_da_rodada_sao_cinco_e_estao_escritos():
    """Inventário por igualdade: desfecho novo passa por aqui antes de existir.

    Não é burocracia. O caso da `armadilhas/283` foi exatamente um desfecho que
    existia no mundo e não no código — e o efeito não foi um erro, foi uma fila
    que parou de atender gente nova sem ninguém perceber por dias.
    """
    assert {
        motor.OFERECIDA,
        motor.JA_TEM_OFERTA_PENDENTE,
        motor.SEM_ELEGIVEL,
        motor.CORRIDA_PERDIDA,
        motor.SAIU_DA_FILA,
    } == {
        "oferecida",
        "ja_tem_oferta_pendente",
        "sem_elegivel",
        "corrida_perdida",
        "saiu_da_fila",
    }


def test_toda_encomenda_varrida_sai_com_desfecho(
    semeado, criar_perfil, criar_encomenda
):
    """Nenhuma encomenda da fila termina a passada sem uma palavra sobre ela.

    "Não apareceu no relatório" e "não havia ninguém para ela" são coisas
    diferentes, e a tela do plantão precisa saber qual das duas foi.
    """
    criar_perfil("pes-1", entrada=AGORA - timedelta(days=5))
    tres = [criar_encomenda(cliente=f"cli-{i}") for i in range(3)]

    rodada = motor.rodar(AGORA, site_id=SITE)

    assert set(rodada.desfechos) == {e.pk for e in tres}
    assert all(v for v in rodada.desfechos.values())


def test_encomenda_sem_elegivel_nao_bloqueia_a_de_tras(
    semeado, criar_perfil, criar_encomenda
):
    """A lição da `armadilhas/283`, encenada nesta fila.

    A encomenda presa é sempre a mais antiga, e a varredura começa pela mais
    antiga. Se ela ocupasse a vaga, quem chegou depois nunca seria atendido —
    foi assim que uma fila de verdade parou de servir gente nova, em silêncio.
    Aqui a primeira encomenda é de nível avançado e não tem ninguém elegível; a
    segunda é iniciante e TEM.
    """
    criar_perfil("pes-1", entrada=AGORA - timedelta(days=5))
    presa = criar_encomenda(nivel=Encomenda.Nivel.AVANCADO, cliente="cli-presa")
    seguinte = criar_encomenda(nivel=Encomenda.Nivel.INICIANTE, cliente="cli-seguinte")

    rodada = motor.rodar(AGORA, site_id=SITE)

    assert rodada.desfechos[presa.pk] == motor.SEM_ELEGIVEL
    assert rodada.desfechos[seguinte.pk] == motor.OFERECIDA
    # E ela CONTINUA na fila, esperando o tique do degrau 2.4 abri-la em 24h.
    presa.refresh_from_db()
    assert presa.status == Encomenda.Status.NA_FILA


def test_a_varredura_e_da_mais_antiga_para_a_mais_nova(
    semeado, criar_perfil, criar_encomenda
):
    """Plano §7.4, literal. A ordem das encomendas é tão regra quanto a dos alunos.

    Duas encomendas, um aluno: a que entrou primeiro leva. Sem `order_by`, a
    resposta seria a ordem que o PostgreSQL devolvesse, que muda sem aviso.
    """
    criar_perfil("pes-1", entrada=AGORA - timedelta(days=5))
    primeira = criar_encomenda(cliente="cli-1")
    segunda = criar_encomenda(cliente="cli-2")

    rodada = motor.rodar(AGORA, site_id=SITE)

    assert rodada.desfechos[primeira.pk] == motor.OFERECIDA
    assert rodada.desfechos[segunda.pk] == motor.SEM_ELEGIVEL


# ---------------------------------------------------------------------------
# 3. Fail-closed: sem parâmetro, o motor não inventa
# ---------------------------------------------------------------------------


def test_sem_parametro_semeado_o_motor_recusa_a_rodada(
    db, criar_perfil, criar_encomenda
):
    """Banco sem semente: recusa com nome, não oferta com padrão embutido.

    Um valor padrão em código seria a constante mágica que a lei §3.8 proíbe
    (critério de morte 5) e esconderia uma instalação pela metade — a célula
    ofereceria encomendas com uma régua que ninguém escolheu.
    """
    criar_perfil("pes-1", entrada=AGORA - timedelta(days=5))
    criar_encomenda()

    with pytest.raises(motor.ParametroAusente) as erro:
        motor.rodar(AGORA, site_id=SITE)

    assert "entregas_para_nivel_intermediario" in str(erro.value)
    assert "semear_parametros" in str(erro.value)
    assert Oferta.objects.count() == 0


def test_a_recusa_acontece_antes_da_primeira_oferta(
    semeado, criar_perfil, criar_encomenda
):
    """A expiração é calculada UMA vez, antes de qualquer escrita.

    Se ela fosse calculada por oferta, um `relogio_da_oferta` ausente deixaria
    metade da fila oferecida e a outra metade não, com a rodada estourando no
    meio. Aqui o motor para antes de a primeira linha existir.
    """
    criar_perfil("pes-1", entrada=AGORA - timedelta(days=5))
    criar_perfil("pes-2", entrada=AGORA - timedelta(days=4))
    criar_encomenda(cliente="cli-1")
    criar_encomenda(cliente="cli-2")

    def sem_relogio(agora, *, site_id):
        raise motor.ParametroAusente("relogio_da_oferta")

    with pytest.raises(motor.ParametroAusente):
        motor.rodar(AGORA, site_id=SITE, calcular_expiracao=sem_relogio)

    assert Oferta.objects.count() == 0


# ---------------------------------------------------------------------------
# 4. A costura do relógio — o degrau 2.4 trocou a conta, e a troca se vê daqui
# ---------------------------------------------------------------------------


def test_a_conta_padrao_do_motor_e_a_de_horas_uteis(
    semeado, criar_perfil, criar_encomenda
):
    """A troca do degrau 2.4 aconteceu de verdade, e não só no arquivo novo.

    Até a TAR-121 o padrão de `rodar()` era `expiracao_provisoria`, que contava
    horas de PAREDE. A conta de horas úteis podia nascer inteira, com guarda e
    tudo, e o motor continuar chamando a antiga sem ninguém notar — o guarda do
    [INV-ENC-J8] mediria a função certa, e a fila usaria a outra. Esta asserção
    fecha esse buraco pelo caminho REAL: roda o motor sem passar colaborador
    nenhum e confere que o `expira_em` gravado é o que a janela devolve.
    """
    criar_perfil("pes-1", entrada=AGORA - timedelta(days=5))
    encomenda = criar_encomenda()

    motor.rodar(AGORA, site_id=SITE)

    assert Oferta.objects.get(
        encomenda=encomenda
    ).expira_em == relogio.calcular_expiracao(AGORA, site_id=SITE)


def test_a_conta_provisoria_de_horas_corridas_nao_existe_mais(semeado):
    """A contraprova da de cima: a conta antiga MORREU, não ficou de reserva.

    Duas contas de expiração convivendo é a lei anti-duplicação sendo violada no
    lugar mais caro possível — a próxima sessão escolheria uma das duas ao
    acaso, e metade das ofertas teria prazo de parede. E a diferença entre elas
    é visível: às 21h, a conta de parede vence à meia-noite; a da janela, às 10h
    do dia seguinte.
    """
    assert not hasattr(motor, "expiracao_provisoria")


def test_relogio_da_oferta_ausente_tem_mensagem_propria(db):
    """A conta nova continua fail-closed, e continua dizendo o que fazer.

    Este guarda existia desde o degrau 2.3, apontando para a conta provisória.
    Ele NÃO morreu com ela: mudou de alvo, porque a promessa que ele mede não
    mudou — sem `relogio_da_oferta` não há quando expirar, e uma oferta sem prazo
    é uma encomenda parada para sempre.

    O cenário é o banco SEM semente, e tem de ser: a tabela é append-only no
    PostgreSQL, então apagar a linha semeada para encenar a ausência é recusado
    por gatilho — que é o desenho da lei §3.8 funcionando.
    """
    with pytest.raises(motor.ParametroAusente) as erro:
        relogio.calcular_expiracao(AGORA, site_id=SITE)

    assert "relogio_da_oferta" in str(erro.value)
    assert "semear_parametros" in str(erro.value)


def test_o_parametro_de_outro_site_nao_serve_de_relogio(semeado):
    """A leitura é por site, e a ausência de um não se cobre com o valor do outro.

    A escola A está semeada; a B não. Se `vigente_em` esquecesse o `site_id`, a
    escola B começaria a oferecer com a régua da A, e ninguém veria diferença até
    os dois números divergirem. Mesmo guarda de antes, mesmo alvo novo.
    """
    with pytest.raises(motor.ParametroAusente):
        relogio.calcular_expiracao(AGORA, site_id="escola-b")


def test_o_motor_usa_a_conta_que_lhe_deram(semeado, criar_perfil, criar_encomenda):
    """A costura é de verdade: quem calcula a expiração é o colaborador.

    Sem esta asserção, o degrau 2.4 poderia escrever a conta de horas úteis
    inteira, plugá-la, e o motor continuar usando a provisória sem ninguém
    notar — o guarda do [INV-ENC-J8] mediria a função, e a fila usaria a outra.
    """
    criar_perfil("pes-1", entrada=AGORA - timedelta(days=5))
    encomenda = criar_encomenda()
    combinado = AGORA + timedelta(days=2)

    motor.rodar(
        AGORA, site_id=SITE, calcular_expiracao=lambda agora, *, site_id: combinado
    )

    assert Oferta.objects.get(encomenda=encomenda).expira_em == combinado


def test_as_ofertas_da_mesma_rodada_expiram_no_mesmo_instante(
    tres_na_fila, criar_encomenda
):
    """Consequência de o motor ser função de (estado, `agora`), e ela é visível.

    Três encomendas oferecidas na mesma passada dão a três pessoas exatamente o
    mesmo prazo. Calcular a expiração por oferta faria a terceira pessoa da
    varredura ganhar alguns milissegundos a mais — e, no dia em que a varredura
    demorar, alguns minutos.
    """
    for i in range(3):
        criar_encomenda(cliente=f"cli-{i}")

    motor.rodar(AGORA, site_id=SITE)

    assert len(set(Oferta.objects.values_list("expira_em", flat=True))) == 1


# ---------------------------------------------------------------------------
# 5. A fronteira de site, e a pista do Mural
# ---------------------------------------------------------------------------


def test_o_motor_de_um_site_nao_enxerga_o_outro(semeado, criar_perfil, criar_encomenda):
    """Lei 9 / [INV-P11]: nenhum dado de um site aparece em outro.

    A escola B tem o aluno mais antigo e com menos entregas do mundo. Ele não
    recebe a encomenda da escola A — e o banco recusaria a linha de qualquer
    jeito (`oferta_e_aluno_do_mesmo_site`), mas descobrir isso por
    `IntegrityError` seria a fila parando em produção.
    """
    da_casa = criar_perfil("pes-a", entrada=AGORA - timedelta(days=1))
    criar_perfil("pes-b", entrada=AGORA - timedelta(days=999), site_id="escola-b")

    encomenda = criar_encomenda()
    motor.rodar(AGORA, site_id=SITE)

    assert Oferta.objects.get(encomenda=encomenda).aluno_id == da_casa.id


def test_o_motor_da_fila_nao_toca_no_que_esta_no_mural(
    semeado, criar_perfil, criar_encomenda
):
    """A fila e o Mural são pistas separadas (`PLANO-AREA-DE-NEGOCIACAO.md` §3).

    `no_mural` é status próprio, e o motor varre `na_fila`. A fronteira não
    depende de ninguém lembrar dela — o que é o ponto, porque o Mural nasce em
    outro degrau (TAR-133) e em outra bancada.
    """
    criar_perfil(
        "pes-1", entrada=AGORA - timedelta(days=5), titulo="nivel_2", entregas=3
    )
    no_mural = criar_encomenda(
        nivel=Encomenda.Nivel.INTERMEDIARIO, status=Encomenda.Status.NO_MURAL
    )

    rodada = motor.rodar(AGORA, site_id=SITE)

    assert no_mural.pk not in rodada.desfechos
    assert Oferta.objects.count() == 0
