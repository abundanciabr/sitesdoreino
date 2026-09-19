"""A chamada aberta: o primeiro elegível que aceitar leva, e só um leva.

Cenário 4 do anexo B: *"Nenhum aceite em 24h → `aberta`; dois alunos tentam
aceitar ao mesmo tempo → só um consegue."*

Plano §6.4: *"Encomenda há 24h na fila sem aceite (ou sem elegíveis disponíveis)
vira Aberta: todos os elegíveis são avisados; o primeiro que aceitar leva. O
nível mínimo continua valendo."*

**A metade que já existia e a metade que nasce aqui.** Virar `aberta` no prazo é
[INV-ENC-J9], do degrau 2.4, e este arquivo a usa pelo caminho real (o tique) em
vez de forçar o estado à mão — um cenário que começa com `status = aberta`
escrito na marra provaria o aceite e não provaria que alguma encomenda chega
lá. O que nasce agora é o que a chamada aberta FAZ: quem pode levar, e o que
acontece quando dois tentam no mesmo segundo.
"""

import threading
from datetime import datetime, timedelta, timezone as fuso

import pytest
from django.db import connection

from apps.encomendas import gestos, motor, tique
from apps.encomendas.models import Encomenda, Oferta, PerfilProfissional

SITE = "escola-a"
AGORA = datetime.now(tz=fuso.utc)
# Bem depois de `horas_para_virar_aberta` (24, lei §6), sem repetir o número: a
# régua é o parâmetro, e um teste que escrevesse 24 aqui passaria a mentir no dia
# em que o mantenedor mudasse a linha da tabela.
MUITO_DEPOIS = timedelta(days=3)


def _abrir(criar_encomenda, cliente="cli-1"):
    """Uma encomenda que esperou demais na fila e virou chamada aberta.

    Pelo caminho real: o tique de um minuto, com `agora` bem depois do prazo. É a
    mesma passada que expira a oferta pendente e cancela o que estiver vivo.
    """
    encomenda = criar_encomenda(cliente=cliente)
    depois = encomenda.criada_em + MUITO_DEPOIS
    tique.rodar(depois, site_id=SITE)
    encomenda.refresh_from_db()
    assert encomenda.status == Encomenda.Status.ABERTA
    return encomenda, depois


def _abrir_avancada(criar_encomenda):
    """A encomenda mais difícil da casa, esperando na fila até virar aberta."""
    encomenda = criar_encomenda(nivel=Encomenda.Nivel.AVANCADO, cliente="cli-dificil")
    depois = encomenda.criada_em + MUITO_DEPOIS
    tique.rodar(depois, site_id=SITE)
    encomenda.refresh_from_db()
    assert encomenda.status == Encomenda.Status.ABERTA
    return encomenda, depois


# ---------------------------------------------------------------------------
# 1. QUEM LEVA
# ---------------------------------------------------------------------------


def test_o_primeiro_elegivel_que_aceitar_leva(tres_na_fila, criar_encomenda):
    """A chamada aberta entrega a encomenda a quem chegar primeiro, não a quem é o primeiro da fila.

    É a única vez em que a ordem da fila não decide, e ela existe porque a fila já
    falhou: passaram 24h e ninguém aceitou. A partir daí quem espera é o cliente.
    """
    _, bia, _ = tres_na_fila
    encomenda, depois = _abrir(criar_encomenda)

    desfecho = gestos.aceitar_a_chamada_aberta(
        encomenda.pk, bia.id, depois, site_id=SITE
    )

    assert desfecho.feito
    assert desfecho.encomenda_em == Encomenda.Status.EM_NEGOCIACAO
    encomenda.refresh_from_db()
    bia.refresh_from_db()
    assert encomenda.aluno_id == bia.id
    assert bia.disponibilidade == PerfilProfissional.Disponibilidade.TRABALHANDO
    # Nenhuma `Oferta` nasce aqui: não houve oferta. Inventar uma já aceita
    # mentiria na auditoria de justiça (taxa de aceite, tempo de resposta).
    assert not Oferta.objects.filter(encomenda=encomenda, aluno=bia).exists()


def test_o_segundo_recebe_uma_recusa_com_nome(tres_na_fila, criar_encomenda):
    """Depois de levada, a chamada aberta não é mais de ninguém.

    A tela precisa dizer "alguém pegou antes de você", e não "erro": é a
    experiência mais comum de uma chamada aberta com fila grande.
    """
    ana, bia, _ = tres_na_fila
    encomenda, depois = _abrir(criar_encomenda)
    gestos.aceitar_a_chamada_aberta(encomenda.pk, bia.id, depois, site_id=SITE)

    desfecho = gestos.aceitar_a_chamada_aberta(
        encomenda.pk, ana.id, depois, site_id=SITE
    )

    assert not desfecho.feito
    assert desfecho.razao == gestos.JA_FOI_LEVADA
    encomenda.refresh_from_db()
    assert encomenda.aluno_id == bia.id


def test_encomenda_que_nao_esta_aberta_nao_se_pega(tres_na_fila, criar_encomenda):
    """A porta só abre no estado `aberta`, e a recusa distingue os dois casos.

    Sem esta conferência, qualquer aluno pegaria qualquer encomenda da fila por
    identificador, e a frase "a plataforma escolhe o aluno" morreria aí.
    """
    ana, _, _ = tres_na_fila
    encomenda = criar_encomenda()

    desfecho = gestos.aceitar_a_chamada_aberta(
        encomenda.pk, ana.id, AGORA, site_id=SITE
    )

    assert not desfecho.feito
    assert desfecho.razao == gestos.NAO_ESTA_ABERTA
    encomenda.refresh_from_db()
    assert encomenda.status == Encomenda.Status.NA_FILA


# ---------------------------------------------------------------------------
# 2. O NÍVEL MÍNIMO CONTINUA VALENDO — a mesma régua, nunca uma segunda
# ---------------------------------------------------------------------------


def test_a_chamada_aberta_respeita_o_nivel_minimo(
    semeado, criar_perfil, criar_encomenda
):
    """Cenário 6 do anexo B, do lado da chamada aberta: *"vira aberta só para elegíveis"*.

    Aberta não quer dizer "de qualquer um". Um Nível 1 que levasse um personagem
    entregaria uma peça que não sabe fazer, e a promessa de que nenhuma primeira
    entrega chega crua ao cliente começaria a ser paga na revisão.
    """
    iniciante = criar_perfil("pes-ana", entrada=AGORA - timedelta(days=30))
    encomenda, depois = _abrir_avancada(criar_encomenda)

    desfecho = gestos.aceitar_a_chamada_aberta(
        encomenda.pk, iniciante.id, depois, site_id=SITE
    )

    assert not desfecho.feito
    assert desfecho.razao == motor.TITULO_ABAIXO_DO_NIVEL


def test_quem_esta_pausado_nao_leva_a_chamada_aberta(
    semeado, criar_perfil, criar_encomenda
):
    """A elegibilidade é a MESMA do motor, e por isso a pausa vale aqui também.

    Se a chamada aberta tivesse régua própria, ela seria a primeira a divergir: o
    caminho mais curto para "todos os elegíveis" é `PerfilProfissional.objects.all()`.
    """
    ana = criar_perfil("pes-ana", entrada=AGORA - timedelta(days=30))
    encomenda, depois = _abrir(criar_encomenda)
    gestos.pausar(ana.id, site_id=SITE)

    desfecho = gestos.aceitar_a_chamada_aberta(
        encomenda.pk, ana.id, depois, site_id=SITE
    )

    assert not desfecho.feito
    assert desfecho.razao == motor.NAO_ESTA_DISPONIVEL


# ---------------------------------------------------------------------------
# 3. DOIS ACEITES NO MESMO SEGUNDO — quem resolve é a trava do banco
# ---------------------------------------------------------------------------

# As duas travas de TRUNCATE desta célula, pelo nome que a migração lhes deu. O
# desmonte de um teste transacional é um `flush`, e `flush` é `TRUNCATE` em toda
# tabela — que estas duas recusam, porque `Parametro` e `MudancaDeStatus` são
# append-only NO BANCO (lei §3.8; `armadilhas/361` mediu exatamente este erro na
# célula `admin`, e ele estoura no desmonte, apontando para o teste errado).
#
# Desligar as duas por um teste é o preço de encenar dois processos de verdade, e
# é MENOR do que a alternativa: sem processos de verdade não existe prova de
# trava nenhuma. Só o TRUNCATE sai; `UPDATE` e `DELETE` continuam recusados, e
# `test_parametros_sao_dado.py` continua medindo os dois.
TRAVAS_DE_TRUNCATE = (
    ("encomendas_parametro", "encomendas_parametro_sem_truncate"),
    ("encomendas_mudancadestatus", "encomendas_historico_sem_truncate"),
)


@pytest.fixture
def sem_a_trava_de_truncate(django_db_setup, django_db_blocker):
    """Desliga as duas travas de TRUNCATE, e as religa DEPOIS do desmonte.

    A ordem importa e é o motivo de este ajudante não pedir `transactional_db`:
    quem é montado primeiro é desmontado por último, e o `flush` que precisa das
    travas desligadas mora no desmonte do `transactional_db`. Por isso ele vem
    ANTES dele na assinatura do teste.

    A conferência de que o gatilho existe antes de desligar não é zelo: se uma
    migração futura o renomear, sem ela este ajudante passaria a não desligar
    nada, em silêncio, e o teste voltaria a quebrar no desmonte de um vizinho.
    """

    def mexer(acao):
        with django_db_blocker.unblock(), connection.cursor() as cursor:
            for tabela, gatilho in TRAVAS_DE_TRUNCATE:
                cursor.execute("SELECT 1 FROM pg_trigger WHERE tgname = %s", [gatilho])
                assert cursor.fetchone(), f"gatilho {gatilho} nao existe mais"
                cursor.execute(f"ALTER TABLE {tabela} {acao} TRIGGER {gatilho}")

    mexer("DISABLE")
    yield
    mexer("ENABLE")


def test_dois_aceites_simultaneos_e_so_um_leva(
    sem_a_trava_de_truncate,
    transactional_db,
    semeado,
    criar_perfil,
    criar_encomenda,
):
    """A segunda metade do cenário 4, encenada com dois processos de verdade.

    **Um teste sequencial não prova isto.** Chamando as duas aceitações uma
    depois da outra, a segunda encontra `em_negociacao` e recusa — e passaria
    igualmente bem se não houvesse trava nenhuma, porque em sequência não há
    corrida. As duas linhas de execução leem `aberta` ao mesmo tempo; quem as
    separa é o `select_for_update` na linha da encomenda, e mais nada.

    A barreira faz as duas chegarem juntas ao gesto; sem ela, a primeira
    terminaria antes de a segunda começar e o teste voltaria a ser sequencial.
    """
    ana = criar_perfil("pes-ana", entrada=AGORA - timedelta(days=30))
    bia = criar_perfil("pes-bia", entrada=AGORA - timedelta(days=20))
    encomenda, depois = _abrir(criar_encomenda)

    barreira = threading.Barrier(2)
    desfechos = []
    erros = []

    def tentar(perfil_id):
        try:
            barreira.wait(timeout=5)
            desfechos.append(
                gestos.aceitar_a_chamada_aberta(
                    encomenda.pk, perfil_id, depois, site_id=SITE
                )
            )
        except Exception as erro:  # pragma: no cover - não engolir falha da thread
            erros.append(erro)
        finally:
            connection.close()

    fios = [threading.Thread(target=tentar, args=(p,)) for p in (ana.id, bia.id)]
    for fio in fios:
        fio.start()
    for fio in fios:
        fio.join(timeout=30)

    assert not erros, erros
    assert [d.feito for d in desfechos].count(True) == 1
    assert [d.razao for d in desfechos if not d.feito] == [gestos.JA_FOI_LEVADA]

    encomenda.refresh_from_db()
    assert encomenda.status == Encomenda.Status.EM_NEGOCIACAO
    assert encomenda.aluno_id in {ana.id, bia.id}
    trabalhando = PerfilProfissional.objects.filter(
        disponibilidade=PerfilProfissional.Disponibilidade.TRABALHANDO
    )
    assert [p.id for p in trabalhando] == [encomenda.aluno_id]
