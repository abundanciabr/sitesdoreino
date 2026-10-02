"""O tique como MÁQUINA: a ordem dos gestos, o batimento e o silêncio contado.

- **A ordem dos três gestos**: expirar, abrir, oferecer.
- **O batimento existe e é de um minuto**, pelo caminho canônico do Huey.
- **Uma oferta que vence é um silêncio a mais**, sem custar o lugar na fila.
"""

from datetime import datetime, timedelta, timezone as fuso

from apps.encomendas import motor, negociacao, tasks, tique
from apps.encomendas.models import (
    Encomenda,
    Oferta,
    PerfilProfissional,
    Proposta,
    ReservaDoMural,
)
from config.huey import huey

SITE = "escola-a"


# ---------------------------------------------------------------------------
# 1. A ORDEM DOS TRÊS GESTOS
# ---------------------------------------------------------------------------


def test_o_tique_expira_devolve_a_fila_e_oferece_ao_proximo(
    semeado, criar_perfil, criar_encomenda
):
    """Uma passada faz a fila andar inteira: o silêncio de um vira a vez do outro.

    É o cenário 2 do anexo B visto pelo lado do relógio. A oferta de Ana vence;
    a encomenda volta para `na_fila`; o motor, na MESMA passada, a oferece a
    Bia. Se os três gestos morassem em passadas diferentes, a encomenda ficaria
    um minuto parada a cada troca — e com uma fila de trinta alunos isso é meia
    hora de espera inventada.
    """
    encomenda = criar_encomenda()
    nasceu = encomenda.criada_em
    ana = criar_perfil("pes-ana", entrada=nasceu - timedelta(days=30))
    bia = criar_perfil("pes-bia", entrada=nasceu - timedelta(days=20))

    tique.rodar(nasceu, site_id=SITE)
    da_ana = Oferta.objects.get(encomenda=encomenda)
    assert da_ana.aluno_id == ana.id

    resultado = tique.rodar(da_ana.expira_em, site_id=SITE)

    da_ana.refresh_from_db()
    encomenda.refresh_from_db()
    assert da_ana.resultado == Oferta.Resultado.EXPIROU
    assert da_ana.respondida_em == da_ana.expira_em
    assert encomenda.status == Encomenda.Status.OFERECIDA
    assert resultado.rodada.desfechos == {encomenda.pk: motor.OFERECIDA}
    assert (
        Oferta.objects.get(
            encomenda=encomenda, resultado=Oferta.Resultado.PENDENTE
        ).aluno_id
        == bia.id
    )


def test_expirar_vem_antes_de_abrir_e_o_desfecho_diz_qual_foi(
    semeado, criar_perfil, criar_encomenda
):
    """No minuto em que os dois relógios vencem juntos, o do aluno vence primeiro.

    A ordem decide o que a auditoria de justiça vai ler daqui a seis meses:
    `expirou` significa "o prazo dele acabou", `cancelada` significa "a
    plataforma tirou a oferta dele". São coisas diferentes, e trocar a ordem dos
    gestos trocaria a resposta sem mudar uma linha de regra.
    """
    encomenda = criar_encomenda()
    nasceu = encomenda.criada_em
    criar_perfil("pes-1", entrada=nasceu - timedelta(days=30))
    tique.rodar(nasceu, site_id=SITE)
    oferta = Oferta.objects.get(encomenda=encomenda)

    # Um instante em que a oferta JÁ venceu e a encomenda JÁ passou do prazo da
    # fila: os dois relógios vencidos na mesma passada.
    resultado = tique.rodar(nasceu + timedelta(days=2), site_id=SITE)

    oferta.refresh_from_db()
    encomenda.refresh_from_db()
    assert resultado.ofertas_expiradas == (oferta.pk,)
    assert resultado.encomendas_abertas == (encomenda.pk,)
    assert oferta.resultado == Oferta.Resultado.EXPIROU
    assert encomenda.status == Encomenda.Status.ABERTA


def test_abrir_vem_antes_de_oferecer(semeado, criar_perfil, criar_encomenda):
    """A encomenda que já devia estar aberta não recebe oferta nova primeiro.

    Sem esta ordem, o [INV-ENC-J9] cairia por um minuto a cada volta: o motor
    daria três horas úteis novas a uma encomenda vencida, e ela só abriria no
    tique seguinte — que encontraria uma oferta viva e a cancelaria. O aluno
    receberia e perderia a oportunidade em sessenta segundos.
    """
    encomenda = criar_encomenda()
    nasceu = encomenda.criada_em
    criar_perfil("pes-1", entrada=nasceu - timedelta(days=30))

    resultado = tique.rodar(nasceu + timedelta(days=2), site_id=SITE)

    encomenda.refresh_from_db()
    assert resultado.encomendas_abertas == (encomenda.pk,)
    assert encomenda.status == Encomenda.Status.ABERTA
    assert Oferta.objects.count() == 0, "encomenda aberta não recebe oferta da fila"


def test_uma_encomenda_travada_nao_segura_as_de_tras(
    semeado, criar_perfil, criar_encomenda
):
    """A fila anda mesmo quando a primeira da fila não tem ninguém elegível.

    A encomenda intermediária não tem candidato (ninguém tem entrega aprovada) e
    é a mais antiga. Se a varredura parasse nela, a de nível iniciante logo atrás
    nunca sairia — é a doença da `armadilhas/283`, em que a varredura processava
    sempre as mesmas linhas e quem chegou depois nunca era atendido.
    """
    dificil = criar_encomenda(cliente="cli-1", nivel=Encomenda.Nivel.INTERMEDIARIO)
    facil = criar_encomenda(cliente="cli-2")
    criar_perfil("pes-1", entrada=dificil.criada_em - timedelta(days=5))

    resultado = tique.rodar(dificil.criada_em, site_id=SITE)

    assert resultado.rodada.desfechos[dificil.pk] == motor.SEM_ELEGIVEL
    assert resultado.rodada.desfechos[facil.pk] == motor.OFERECIDA


def test_reserva_em_negociacao_nao_expira_como_pendente(projeto_pego, formulario):
    """A primeira proposta passa o relógio da reserva para a negociação."""
    projeto, aluno = projeto_pego
    agora = datetime.now(tz=fuso.utc)
    assert negociacao.propor(
        projeto.pk,
        agora,
        site_id=SITE,
        de_quem=Proposta.DeQuem.ALUNO,
        **formulario(),
    ).feito

    reserva = ReservaDoMural.objects.get(encomenda=projeto)
    assert reserva.resultado == ReservaDoMural.Resultado.NEGOCIANDO
    assert (
        tique.expirar_reservas_vencidas(
            reserva.expira_em + timedelta(days=1), site_id=SITE
        )
        == ()
    )

    reserva.refresh_from_db()
    projeto.refresh_from_db()
    assert reserva.resultado == ReservaDoMural.Resultado.NEGOCIANDO
    assert projeto.status == Encomenda.Status.EM_NEGOCIACAO
    assert projeto.aluno_id == aluno.id


# ---------------------------------------------------------------------------
# 2. O BATIMENTO: um minuto, pelo caminho canônico
# ---------------------------------------------------------------------------


def test_a_task_periodica_esta_registrada_e_bate_a_cada_minuto():
    """O tique de um minuto do plano §8.6, provado no registro do Huey.

    Não basta o decorador estar escrito: o que faz uma task existir é ela estar
    no registro da instância, e o que a põe lá é o autodiscover de `tasks.py`
    que só o `manage.py run_huey` faz (`armadilhas/030`). Subir o
    `huey_consumer` direto dá um worker de pé com o registro VAZIO, que não roda
    nada e não reclama de nada.
    """
    periodicas = [t.name for t in huey._registry.periodic_tasks]
    assert periodicas == ["tique_periodico"]


def test_o_crontab_do_tique_aceita_qualquer_minuto():
    """`crontab(minute="*")` medido pelo comportamento, e não pelo texto.

    Um `crontab(minute="*/5")` também "está registrado" e também parece certo na
    leitura rápida — e faria uma oferta vencida esperar até cinco minutos para
    ser fechada. Aqui se pergunta ao próprio Huey se ele aceitaria cada um dos
    sessenta minutos da hora.
    """
    from datetime import datetime

    tarefa = tasks.tique_periodico.task_class()
    hora = datetime(2026, 1, 2, 9)

    assert all(tarefa.validate_datetime(hora.replace(minute=m)) for m in range(60))


def test_o_batimento_varre_cada_site_instalado(semeado, criar_perfil, criar_encomenda):
    """Multissítio (uma fábrica, N lojas) chegando ao tique.

    Duas escolas no mesmo banco: a que tem parâmetros é varrida, e o resultado
    vem por site. Um tique que varresse "a tabela toda" misturaria as filas de
    duas escolas na mesma ordem de prioridade, e ninguém veria.
    """
    encomenda = criar_encomenda()
    criar_perfil("pes-1", entrada=encomenda.criada_em - timedelta(days=5))

    resultados = tasks.bater_o_tique()

    assert list(resultados) == [SITE]
    assert resultados[SITE].rodada.quantas_ofertas == 1


def test_o_site_sem_parametros_nao_e_varrido(semeado, criar_encomenda):
    """Fail-closed um nível acima: escola sem régua não é escola parada, é escola ausente.

    Uma encomenda existe para a escola B, que nunca foi semeada. O tique não
    inventa régua para ela nem estoura `ParametroAusente` de minuto em minuto no
    log: ela simplesmente não está na lista, porque a lista sai da tabela de
    parâmetros.
    """
    criar_encomenda(site_id="escola-b")

    assert tique.sites_com_parametros() == (SITE,)
    assert list(tasks.bater_o_tique()) == [SITE]


def test_um_site_torto_nao_derruba_os_outros(semeado, criar_encomenda, monkeypatch):
    """A direção da falha, escrita: uma escola parada, nunca a plataforma parada.

    O tique roda em processo próprio e de minuto em minuto. Uma exceção que
    escapasse mataria a passada inteira — e com ela a fila de TODAS as escolas,
    por causa de um dado torto em uma.
    """
    criar_encomenda()
    original = tique.rodar

    def rodar_quebrando(agora, *, site_id):
        if site_id == "escola-z":
            raise RuntimeError("banco fora do ar nesta escola")
        return original(agora, site_id=site_id)

    monkeypatch.setattr(tique, "rodar", rodar_quebrando)
    monkeypatch.setattr(tique, "sites_com_parametros", lambda: ("escola-z", SITE))

    resultados = tasks.bater_o_tique()

    assert list(resultados) == [SITE]


# ---------------------------------------------------------------------------
# 3. O SILÊNCIO CONTADO
# ---------------------------------------------------------------------------


def test_o_tique_conta_o_silencio_pelo_dono_do_contador(
    semeado, criar_perfil, criar_encomenda
):
    """A fronteira do degrau 2.4, agora atravessada: o silêncio conta.

    Até a TAR-123 este arquivo media a AUSÊNCIA (`silencios_consecutivos == 0`
    depois de uma expiração), e o teste existia para o degrau 2.5 apagar. Ele foi
    apagado aqui, e o que sobra é a outra ponta da mesma medição: uma oferta que
    vence é um silêncio a mais, contado na mesma passada, sem custar o lugar.
    """
    encomenda = criar_encomenda()
    nasceu = encomenda.criada_em
    aluno = criar_perfil("pes-1", entrada=nasceu - timedelta(days=30))
    tique.rodar(nasceu, site_id=SITE)
    oferta = Oferta.objects.get(encomenda=encomenda)

    tique.rodar(oferta.expira_em, site_id=SITE)

    aluno.refresh_from_db()
    assert aluno.silencios_consecutivos == 1
    assert aluno.disponibilidade == PerfilProfissional.Disponibilidade.DISPONIVEL
    assert aluno.data_entrada_fila == nasceu - timedelta(days=30)
