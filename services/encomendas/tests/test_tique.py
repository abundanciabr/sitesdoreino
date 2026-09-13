"""O tique como MÁQUINA: a ordem dos gestos, o batimento, e a ausência de timer.

Os três `test_inv_j8/j9/j10*.py` medem as PROMESSAS que o tique guarda. Este
arquivo mede o que sobra, e o que sobra é o que mantém as promessas de pé em
produção:

- **A ordem dos três gestos é regra**, não arrumação: expirar, abrir, oferecer.
- **O batimento existe e é de um minuto**, pelo caminho canônico do Huey.
- **Não existe agendamento por oferta**, e isso é medido por FORMA — a única
  garantia que continua valendo para o código que o degrau 2.5 ainda vai
  escrever.
- **O contador de silêncios tem um dono só**, e isso é medido por FORMA: o
  tique NOTA o silêncio, e quem sabe o que fazer com ele é `gestos.py`.
"""

import ast
from datetime import datetime, timedelta, timezone as fuso
from pathlib import Path

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
CELULA = Path(__file__).resolve().parent.parent


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
    """Lei 9 (uma fábrica, N lojas) chegando ao tique.

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
# 3. NENHUM TIMER AGENDADO — a garantia de FORMA
# ---------------------------------------------------------------------------

# Os gestos do Huey que criam um agendamento por unidade de trabalho. É a
# peneira estreita de propósito: `revoke` e `restore` mexem numa execução
# específica, `schedule` e `reschedule` marcam hora para uma, e `eta`/`delay`
# são os argumentos que transformam uma chamada comum em agendamento.
AGENDAMENTOS = {"schedule", "reschedule", "revoke", "restore"}
ARGUMENTOS_DE_AGENDAMENTO = {"eta", "delay"}


class _Varredor(ast.NodeVisitor):
    def __init__(self):
        self.agendamentos: list[tuple[int, str]] = []
        self.crontabs: list[int] = []

    def visit_Call(self, no):
        nome = getattr(no.func, "attr", None) or getattr(no.func, "id", None)
        if nome in AGENDAMENTOS:
            self.agendamentos.append((no.lineno, nome))
        if nome == "crontab":
            self.crontabs.append(no.lineno)
        for chave in no.keywords:
            if chave.arg in ARGUMENTOS_DE_AGENDAMENTO:
                self.agendamentos.append((no.lineno, f"{nome}({chave.arg}=...)"))
        self.generic_visit(no)


def _varrer_a_celula():
    achados: list[str] = []
    crontabs: list[str] = []
    for caminho in sorted((CELULA / "apps").rglob("*.py")):
        if "migrations" in caminho.parts:
            continue
        varredor = _Varredor()
        varredor.visit(ast.parse(caminho.read_text(encoding="utf-8")))
        relativo = caminho.relative_to(CELULA)
        achados += [
            f"{relativo}:{linha} {nome}" for linha, nome in varredor.agendamentos
        ]
        crontabs += [f"{relativo}:{linha}" for linha in varredor.crontabs]
    return achados, crontabs


def test_nenhuma_oferta_tem_agendamento_proprio():
    """A lei §7.4 medida como forma: *"relógios não são timers agendados"*.

    Comportamento mede os gestos que existem hoje; o degrau 2.5 traz gestos
    novos (a pausa por três silêncios, a reclassificação) e as Fases 3 e 5 trazem
    seis prazos a mais. É exatamente ali que alguém, com toda a boa intenção,
    escreve `pausar.schedule(eta=perfil.pausa_ate)` para "não precisar varrer" —
    e nenhum teste de comportamento escrito hoje pegaria isso.

    O estrago é invisível: o agendamento vive fora do banco, some no primeiro
    deploy, e a pausa nunca termina. Sem erro, sem log, sem alarme.
    """
    agendamentos, _ = _varrer_a_celula()

    assert agendamentos == [], (
        "agendamento por unidade de trabalho no código desta célula: "
        + "; ".join(agendamentos)
        + ". Relógio desta célula é REAVALIAÇÃO PERIÓDICA (plano §7.4): a "
        "verdade mora numa coluna, e o tique de um minuto pergunta o que está "
        "vencido agora. Um `eta`/`delay`/`schedule` vive fora do banco e some "
        "no primeiro deploy, levando junto a única coisa que faria aquele "
        "prazo acontecer."
    )


def test_existe_um_batimento_so_na_celula_inteira():
    """Um `crontab`, e ele não conhece nenhuma oferta.

    É a outra metade da forma: sem esta asserção, alguém poderia acrescentar um
    `crontab` por tipo de prazo (um para ofertas, um para aprovação tácita, um
    para o SLA do revisor) e voltar ao mundo dos agendamentos por outro caminho
    — seis batimentos a sincronizar, seis lugares para esquecer um.
    """
    _, crontabs = _varrer_a_celula()

    assert len(crontabs) == 1, f"batimentos encontrados: {crontabs}"
    assert crontabs[0].startswith("apps/encomendas/tasks.py") or crontabs[0].startswith(
        "apps\\encomendas\\tasks.py"
    )


def test_o_varredor_enxerga_o_agendamento_que_ele_procura():
    """O guarda que não morde é indistinguível do guarda desligado.

    Sem esta prova, a varredura acima passaria igualmente bem se o `_Varredor`
    não achasse nada — e é exatamente assim que um portão morre em silêncio.
    """
    codigo = (
        "def agenda():\n"
        "    expirar_oferta.schedule(args=(oferta.id,), eta=oferta.expira_em)\n"
        "    tarefa.revoke()\n"
    )
    varredor = _Varredor()
    varredor.visit(ast.parse(codigo))

    assert sorted(nome for _, nome in varredor.agendamentos) == [
        "revoke",
        "schedule",
        "schedule(eta=...)",
    ]


# ---------------------------------------------------------------------------
# 4. O CONTADOR DE SILÊNCIOS TEM UM DONO SÓ
# ---------------------------------------------------------------------------

CONTADOR = "silencios_consecutivos"
# O único arquivo da célula onde a coluna pode ser escrita. `gestos.py` guarda as
# DUAS metades do contador — o que o enche (`contar_o_silencio`, chamado daqui) e
# o que o zera (`zerar_o_silencio`, chamado por aceitar, passar e religar).
QUEM_MEXE_NO_CONTADOR = {"gestos.py"}


class _VarredorDoContador(ast.NodeVisitor):
    """As mesmas três formas de gravar que o guarda do [INV-ENC-J4] enxerga."""

    def __init__(self):
        self.achados: list[int] = []

    def visit_Assign(self, no):
        for alvo in no.targets:
            if isinstance(alvo, ast.Attribute) and alvo.attr == CONTADOR:
                self.achados.append(no.lineno)
        self.generic_visit(no)

    def visit_AugAssign(self, no):
        alvo = no.target
        if isinstance(alvo, ast.Attribute) and alvo.attr == CONTADOR:
            self.achados.append(no.lineno)
        self.generic_visit(no)

    def visit_Call(self, no):
        nome = getattr(no.func, "attr", None) or getattr(no.func, "id", None)
        for chave in no.keywords:
            if chave.arg == CONTADOR and nome in {"create", "update", "bulk_update"}:
                self.achados.append(no.lineno)
            if chave.arg == "update_fields" and nome == "save":
                for item in getattr(chave.value, "elts", []):
                    if isinstance(item, ast.Constant) and item.value == CONTADOR:
                        self.achados.append(no.lineno)
        self.generic_visit(no)


def test_so_um_arquivo_da_celula_escreve_no_contador_de_silencios():
    """As duas metades do contador moram juntas, ou uma delas envelhece sozinha.

    O perigo tem forma conhecida: o gesto novo (o abandono, a mediação, o aceite
    de uma proposta) é escrito num arquivo novo, cresce ou zera o contador ali
    mesmo, e a regra passa a viver em dois lugares. Meses depois um deles esquece
    de zerar, e o aluno é pausado por "estar ocupado" no dia em que mais
    respondeu — sem erro, sem log, sem alarme.

    Vermelho aqui quer dizer: leve a escrita para `gestos.py`, ao lado da outra
    metade, e chame de onde o gesto acontece.
    """
    fora = []
    for caminho in sorted((CELULA / "apps").rglob("*.py")):
        if "migrations" in caminho.parts or caminho.name in QUEM_MEXE_NO_CONTADOR:
            continue
        varredor = _VarredorDoContador()
        varredor.visit(ast.parse(caminho.read_text(encoding="utf-8")))
        fora += [f"{caminho.relative_to(CELULA)}:{linha}" for linha in varredor.achados]

    assert fora == [], (
        f"escrita em `{CONTADOR}` fora de {sorted(QUEM_MEXE_NO_CONTADOR)}: "
        + "; ".join(fora)
        + ". O contador da pausa automática tem as duas metades no mesmo arquivo "
        "(plano §6.3): quem o enche e quem o zera. Chame "
        "`gestos.contar_o_silencio` ou `gestos.zerar_o_silencio` em vez de "
        "escrever na coluna."
    )


def test_o_varredor_do_contador_enxerga_as_quatro_formas_de_gravar():
    """O guarda que não morde é indistinguível do guarda desligado."""
    codigo = "\n".join(
        [
            "def mexe():",
            "    perfil.silencios_consecutivos = 0",
            "    perfil.silencios_consecutivos += 1",
            "    Perfil.objects.update(silencios_consecutivos=0)",
            "    perfil.save(update_fields=['silencios_consecutivos'])",
        ]
    )
    varredor = _VarredorDoContador()
    varredor.visit(ast.parse(codigo))

    assert len(varredor.achados) == 4


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
