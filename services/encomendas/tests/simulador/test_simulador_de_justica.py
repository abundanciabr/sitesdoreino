"""O simulador de cem alunos: a fila roda dias a fio e a justiça não quebra em nenhum minuto.

Lei: `docs/decisoes/DECISAO-fila-do-primeiro-dolar.md` §5 (os dez invariantes de
justiça) e §6 (os parâmetros). Produto:
`PLANO-MESTRE-FILA-DO-PRIMEIRO-DOLAR.md` §6 (o livro de regras), §7.4 (o
algoritmo), item 2.9 do backlog e o Anexo B (os cenários de aceite).

Este é o degrau 2.6 da escada e o **portão da Fase 2** (plano §11): *"invariantes
de justiça verdes; simulação reproduz o piloto de papel"*. Os dez guardas
`test_inv_j*.py` medem cada invariante isolado, num cenário de duas ou três
pessoas montado à mão. Este arquivo mede outra coisa, e é por isso que ele
existe: **cem alunos e trinta encomendas se atropelando durante dias**, com
gente aceitando, passando, sumindo, pausando e voltando ao mesmo tempo. É onde
uma injustiça que nenhum cenário de três pessoas produz teria de aparecer.

A ASSERÇÃO É POR PASSO, NUNCA POR RESULTADO FINAL
--------------------------------------------------
Os dez invariantes são conferidos DUAS vezes por hora simulada: depois do tique
(quando o sistema já reagiu ao relógio) e depois dos gestos dos alunos. Um
simulador que só olhasse o estado final seria quase inútil: a fila pode passar
por um minuto com duas ofertas pendentes para o mesmo aluno e chegar limpa ao
fim, e é exatamente esse minuto que arruinaria a promessa do produto.

O ORÁCULO É A LEI, E NÃO O MOTOR
---------------------------------
Nenhuma conferência daqui chama `motor.por_que_nao` nem `motor.CHAVE_DA_ORDEM`.
A elegibilidade e a ordem de prioridade estão **reescritas neste arquivo**, do
plano §6.1 e §6.2, com os números lidos do banco. Não é duplicação por descuido:
um teste que perguntasse ao motor se o motor acertou mediria a si mesmo. O que
prova alguma coisa é a SEGUNDA medida, feita por outro caminho, chegando ao
mesmo lugar.

O QUE O SIMULADOR ENCENA, E QUE AINDA NÃO EXISTE
-------------------------------------------------
`_o_trabalho_terminou_e_o_cliente_aprovou` empurra a encomenda aceita pela linha
principal da máquina de estado até `concluida` e soma uma entrega ao aluno. Isso
é Fase 3 e Fase 5, e não existe em código nenhum ainda. Está aqui porque **sem
entregas aprovadas a fila não gira**: a chave da lei §6.2 é
`(entregas_aprovadas, data_entrada_fila)`, e um mundo em que ninguém entrega
nunca mostra a promessa do produto acontecendo, que é o novato passando na frente
do veterano. Quem faz a transição é a máquina de estado de verdade
(`Encomenda.TRANSICOES`), então nada aqui inventa caminho que o banco não aceite.

O PLACAR
--------
Sai em texto no fim, para ser lido por gente e conferido contra o piloto de papel
da Fase 1. Ele também é asserção: um simulador em que ninguém aceita, ninguém
passa e ninguém some passaria nos dez invariantes sem provar nada, e as
asserções do fim do arquivo existem para que esse verde vazio seja impossível.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from apps.encomendas import gestos, relogio, tique
from apps.encomendas.models import (
    Encomenda,
    Oferta,
    Parametro,
    PerfilProfissional,
)

# O tamanho do passo e a duração da simulação. Não são parâmetros da lei §6 (o
# mantenedor não os edita numa tela): são a régua do experimento. Uma hora é o
# maior passo que ainda enxerga o relógio de três horas úteis da oferta nascer,
# correr e vencer; oito dias são o menor prazo que ainda mostra a fila
# girar inteira: uma encomenda aceita no primeiro dia volta como entrega
# aprovada a tempo de mudar a ordem da lei §6.2 antes do fim.
PASSO = timedelta(hours=1)
DIAS_SIMULADOS = 8

# ---------------------------------------------------------------------------
# O ORÁCULO — o plano §6.1 e §6.2 reescritos aqui, longe do motor
# ---------------------------------------------------------------------------

# A hierarquia dos títulos (plano §6.1). Título vazio é o perfil que nunca passou
# pelo professor: ele fica abaixo de tudo.
TITULOS_EM_ORDEM = ("", "nivel_1", "nivel_2", "nivel_3")

# O título mínimo de cada nível de encomenda, lido do plano §6.1 palavra por
# palavra: *"Iniciante: título Modelador Nível 1. Intermediário: título Nível 2 e
# pelo menos 1 entrega aprovada. Avançado: título Nível 3 e 5 entregas aprovadas
# e nenhum abandono nos últimos 90 dias."*
TITULO_MINIMO = {
    Encomenda.Nivel.INICIANTE: "nivel_1",
    Encomenda.Nivel.INTERMEDIARIO: "nivel_2",
    Encomenda.Nivel.AVANCADO: "nivel_3",
}

# A linha principal do plano §7.2, do aceite até a aprovação do cliente. É a Fase
# 3 e a Fase 5 encenadas: o simulador só precisa que o aluno volte a ficar livre
# com uma entrega a mais.
DO_ACEITE_ATE_CONCLUIDA = (
    Encomenda.Status.ACORDADA,
    Encomenda.Status.AGUARDANDO_PAGAMENTO,
    Encomenda.Status.EM_PRODUCAO,
    Encomenda.Status.ENTREGUE,
    Encomenda.Status.EM_REVISAO,
    Encomenda.Status.AGUARDANDO_CLIENTE,
    Encomenda.Status.APROVADA,
    Encomenda.Status.CONCLUIDA,
)

ESPERANDO_UM_ALUNO = (Encomenda.Status.NA_FILA, Encomenda.Status.OFERECIDA)


@dataclass(frozen=True)
class Regua:
    """Os números da lei §6 que o oráculo consulta, lidos do banco uma vez.

    Lidos do BANCO e não escritos aqui: o oráculo precisa ser uma segunda medida
    da regra, não uma segunda cópia dos valores. Se o mantenedor mudar
    `entregas_para_nivel_avancado` numa tela, o motor e este arquivo mudam juntos.
    """

    entregas_minimas: dict
    janela_sem_abandono: timedelta
    relogio_da_oferta: timedelta
    prazo_da_fila: timedelta

    @classmethod
    def do_banco(cls, agora, *, site_id):
        def horas(chave):
            return timedelta(
                hours=Parametro.inteiro_vigente(chave, agora, site_id=site_id)
            )

        def numero(chave):
            return Parametro.inteiro_vigente(chave, agora, site_id=site_id)

        return cls(
            entregas_minimas={
                # Iniciante não exige entrega nenhuma, e essa ausência é a razão
                # de a fila existir: ninguém contrata quem nunca entregou.
                Encomenda.Nivel.INICIANTE: 0,
                Encomenda.Nivel.INTERMEDIARIO: numero(
                    "entregas_para_nivel_intermediario"
                ),
                Encomenda.Nivel.AVANCADO: numero("entregas_para_nivel_avancado"),
            },
            janela_sem_abandono=timedelta(days=numero("janela_sem_abandono")),
            relogio_da_oferta=horas("relogio_da_oferta"),
            prazo_da_fila=horas("horas_para_virar_aberta"),
        )


def elegivel_pela_lei(perfil, nivel, ja_viram, com_oferta, regua, agora):
    """Este aluno pode receber uma encomenda deste nível, agora? (plano §6.1)

    Escrita de novo, longe do motor, e na ordem em que a lei está escrita. É a
    régua contra a qual o [INV-ENC-J3] e o [INV-ENC-J5] são medidos.
    """
    if perfil.data_entrada_fila is None:
        return False
    minimo = TITULO_MINIMO[nivel]
    if TITULOS_EM_ORDEM.index(perfil.titulo_banca) < TITULOS_EM_ORDEM.index(minimo):
        return False
    if perfil.entregas_aprovadas < regua.entregas_minimas[nivel]:
        return False
    if nivel == Encomenda.Nivel.AVANCADO and _abandonou_na_janela(perfil, regua, agora):
        return False
    if perfil.disponibilidade != PerfilProfissional.Disponibilidade.DISPONIVEL:
        return False
    if perfil.id in com_oferta:
        return False
    return perfil.id not in ja_viram


def _abandonou_na_janela(perfil, regua, agora):
    limite = agora - regua.janela_sem_abandono
    return any(
        datetime.fromisoformat(quando) >= limite for quando in (perfil.abandonos or [])
    )


def lugar_na_ordem(perfil):
    """A prioridade da lei §6.2: menos entregas primeiro, empate pela data.

    O terceiro termo é o desempate do banco, e está aqui pela mesma razão que
    está no motor: sem ele, dois perfis idênticos fariam a comparação depender da
    ordem em que as linhas voltaram.
    """
    return (perfil.entregas_aprovadas, perfil.data_entrada_fila, perfil.id)


def a_alocacao_que_a_lei_manda(perfis, na_fila, com_oferta, quem_ja_viu, regua, agora):
    """A rodada inteira, calculada por fora do motor. O oráculo do [INV-ENC-J3].

    É o laço do plano §7.4 escrito de novo: *"para cada encomenda em `na_fila`,
    da mais antiga para a mais nova (...) escolhido = min(elegiveis, chave =
    (entregas_aprovadas, data_entrada_fila))"*. Quem recebe passa a ter oferta
    pendente para o resto da varredura, e é isso que impede uma pessoa só de levar
    a fila inteira numa passada.

    Conferir a ALOCAÇÃO INTEIRA, e não cada oferta isolada, é o que dá dente ao
    guarda. Olhando uma oferta de cada vez, uma troca entre duas encomendas da
    mesma rodada (a primeira indo para quem devia levar a segunda, e vice-versa)
    passaria despercebida: os dois escolhidos estariam ocupados, e nenhum dos dois
    apareceria como "estava elegível e vinha antes".
    """
    ocupados = set(com_oferta)
    esperada = {}
    for encomenda in na_fila:
        ja_viram = quem_ja_viu.get(encomenda.pk, set())
        aptos = [
            perfil
            for perfil in perfis
            if elegivel_pela_lei(
                perfil, encomenda.nivel, ja_viram, ocupados, regua, agora
            )
        ]
        if not aptos:
            # Ninguém elegível: a encomenda FICA onde está, e quem a vira em
            # chamada aberta é o relógio das 24h, nunca esta varredura.
            continue
        vencedor = min(aptos, key=lugar_na_ordem)
        esperada[encomenda.pk] = vencedor.id
        ocupados.add(vencedor.id)
    return esperada


# ---------------------------------------------------------------------------
# O PLACAR — o que aconteceu, em português, para conferir contra o piloto
# ---------------------------------------------------------------------------


def _linha(rotulo, valor, *, recuo=2):
    """Rótulo, pontinhos até a mesma coluna, valor. Uma só, para tudo alinhar."""
    return f"{' ' * recuo}{rotulo} ".ljust(46, ".") + f" {valor}"


@dataclass
class Placar:
    ofertas: int = 0
    aceites_na_fila: int = 0
    passes: dict = field(default_factory=dict)
    silencios: int = 0
    pausas_por_silencio: int = 0
    pausas_pelo_aluno: int = 0
    voltas_a_fila: int = 0
    viraram_chamada_aberta: int = 0
    aceites_em_chamada_aberta: int = 0
    reclassificadas: int = 0
    entregas_aprovadas: int = 0
    alunos_que_receberam: set = field(default_factory=set)

    @property
    def total_de_passes(self):
        return sum(self.passes.values())

    def em_texto(self, povoado, *, esperando, abertas_sem_dono, concluidas):
        """O placar em português, para o mantenedor ler sem tradutor.

        Cada linha é um mecanismo do livro de regras acontecendo tantas vezes.
        Ele existe para ser conferido contra o piloto de papel da Fase 1, onde o
        professor anota as mesmas coisas à mão numa planilha, e por isso os
        rótulos são os do plano, não os das colunas do banco.
        """
        linhas = [
            "",
            "PLACAR DO SIMULADOR DA FILA DO PRIMEIRO DOLAR",
            f"{len(povoado.perfis)} alunos, {len(povoado.encomendas)} "
            f"encomendas, {DIAS_SIMULADOS} dias simulados, passo de "
            f"{int(PASSO.total_seconds() // 3600)} hora",
            "",
            _linha("Ofertas feitas", self.ofertas),
            _linha("Aceites na fila", self.aceites_na_fila),
            _linha("Passes (com motivo)", self.total_de_passes),
        ]
        for motivo, quantos in sorted(self.passes.items()):
            linhas.append(
                _linha(dict(Oferta.MotivoDoPasse.choices)[motivo], quantos, recuo=4)
            )
        linhas += [
            _linha("Silencios (ofertas que venceram)", self.silencios),
            _linha("Pausas automaticas por tres silencios", self.pausas_por_silencio),
            _linha("Pausas pelo proprio aluno", self.pausas_pelo_aluno),
            _linha("Voltas a fila (o aluno religou)", self.voltas_a_fila),
            _linha("Viraram chamada aberta", self.viraram_chamada_aberta),
            _linha("Aceites em chamada aberta", self.aceites_em_chamada_aberta),
            _linha("Mandadas para reclassificar", self.reclassificadas),
            _linha("Entregas aprovadas no periodo", self.entregas_aprovadas),
            _linha("Alunos que receberam oferta", len(self.alunos_que_receberam)),
            "",
            f"  No fim: {concluidas} concluidas, {esperando} ainda esperando na "
            f"fila, {abertas_sem_dono} em chamada aberta sem dono",
            "",
        ]
        return "\n".join(linhas)


# ---------------------------------------------------------------------------
# OS DEZ, CONFERIDOS NUM INSTANTE
# ---------------------------------------------------------------------------


@dataclass
class Memoria:
    """O que o guarda precisa lembrar entre um instante e o seguinte.

    `quem_ja_viu` é a memória do [INV-ENC-J6], `nascimento` é o instante SIMULADO
    de cada oferta (a coluna `oferecida_em` é `auto_now_add` e guarda o relógio da
    máquina, que não é o relógio desta simulação), e `pares` é o conjunto de
    (encomenda, aluno) já ofertados.
    """

    quem_ja_viu: dict = field(default_factory=dict)
    nascimento: dict = field(default_factory=dict)
    pares: set = field(default_factory=set)


def conferir_os_dez(povoado, agora, memoria, regua, janela, *, novas, depois_do_tique):
    """Os dez invariantes de justiça, neste instante. Reprova no primeiro que cair.

    `novas` são as ofertas criadas AGORA: os invariantes que falam do momento da
    escolha ([INV-ENC-J3], [INV-ENC-J5], [INV-ENC-J6], [INV-ENC-J7]) se medem
    nelas, porque é isso que eles dizem. Uma oferta feita de manhã para quem era
    o primeiro da fila continua correta à tarde, mesmo que outra pessoa tenha
    chegado na frente no meio do dia.

    `depois_do_tique` liga o [INV-ENC-J9]. Quem vira a encomenda em chamada
    aberta é o tique, então a promessa dele é *"nenhuma encomenda continua
    esperando depois do prazo QUANDO O RELÓGIO RODA"*. Entre um tique e o
    seguinte, um aluno pode passar uma encomenda que já passou das 24h de volta
    para a fila, e ela fica esperando o próximo minuto. Isso é o desenho, não uma
    violação.
    """
    site = povoado.site_id
    perfis = list(PerfilProfissional.objects.filter(site_id=site))
    por_id = {p.id: p for p in perfis}
    pendentes = list(
        Oferta.objects.filter(site_id=site, resultado=Oferta.Resultado.PENDENTE)
    )

    # [INV-ENC-J1] Uma encomenda nunca tem duas ofertas pendentes.
    encomendas_com_pendente = [o.encomenda_id for o in pendentes]
    assert len(set(encomendas_com_pendente)) == len(encomendas_com_pendente), (
        f"[INV-ENC-J1] quebrado em {agora.isoformat()}: encomenda com duas "
        f"ofertas pendentes ao mesmo tempo ({encomendas_com_pendente})."
    )

    # [INV-ENC-J2] Um aluno nunca tem duas ofertas pendentes.
    alunos_com_pendente = [o.aluno_id for o in pendentes]
    assert len(set(alunos_com_pendente)) == len(alunos_com_pendente), (
        f"[INV-ENC-J2] quebrado em {agora.isoformat()}: aluno com duas ofertas "
        f"pendentes ao mesmo tempo ({alunos_com_pendente})."
    )

    # [INV-ENC-J4] Passar, expirar e pausar nunca mexem no lugar na fila.
    for perfil in perfis:
        assert perfil.data_entrada_fila == povoado.lugar_na_fila[perfil.id], (
            f"[INV-ENC-J4] quebrado em {agora.isoformat()}: o perfil "
            f"{perfil.id} entrou na fila em {povoado.lugar_na_fila[perfil.id]} e "
            f"agora aparece com {perfil.data_entrada_fila}. Só o abandono move o "
            "lugar, e esta simulação não abandona nada."
        )

    for oferta in novas:
        encomenda = Encomenda.objects.get(pk=oferta.encomenda_id)
        escolhido = por_id[oferta.aluno_id]

        # [INV-ENC-J5] Ninguém recebe encomenda acima do próprio título.
        minimo = TITULO_MINIMO[encomenda.nivel]
        assert TITULOS_EM_ORDEM.index(escolhido.titulo_banca) >= TITULOS_EM_ORDEM.index(
            minimo
        ), (
            f"[INV-ENC-J5] quebrado em {agora.isoformat()}: encomenda "
            f"{encomenda.nivel} ofertada a quem tem titulo "
            f"{escolhido.titulo_banca!r} (o minimo e {minimo!r})."
        )

        # [INV-ENC-J6] Ninguém vê a mesma encomenda duas vezes.
        par = (encomenda.pk, escolhido.id)
        assert par not in memoria.pares, (
            f"[INV-ENC-J6] quebrado em {agora.isoformat()}: a encomenda "
            f"{encomenda.pk} foi ofertada duas vezes ao perfil {escolhido.id}."
        )
        memoria.pares.add(par)

        # [INV-ENC-J7] Quem não está disponível não RECEBE oferta. (Pausar
        # depois de receber é outra coisa, e é permitido: a pausa mantém o
        # lugar, e a oferta na mão simplesmente vence.)
        assert (
            escolhido.disponibilidade == PerfilProfissional.Disponibilidade.DISPONIVEL
        ), (
            f"[INV-ENC-J7] quebrado em {agora.isoformat()}: oferta criada para "
            f"o perfil {escolhido.id}, que estava {escolhido.disponibilidade!r}."
        )

        # [INV-ENC-J8] Entre a oferta e o vencimento há exatamente o relógio da
        # lei, contado só dentro da janela. Medido pela função INVERSA da que
        # calculou a expiração: recalcular com a mesma conta não mediria nada.
        nasceu = memoria.nascimento[oferta.pk]
        de_janela = relogio.horas_uteis_entre(nasceu, oferta.expira_em, janela)
        assert de_janela == regua.relogio_da_oferta, (
            f"[INV-ENC-J8] quebrado em {agora.isoformat()}: a oferta "
            f"{oferta.pk} nasceu em {nasceu.isoformat()} e vence em "
            f"{oferta.expira_em.isoformat()}, o que da {de_janela} de janela em "
            f"vez de {regua.relogio_da_oferta}."
        )

        memoria.quem_ja_viu.setdefault(encomenda.pk, set()).add(escolhido.id)

    # [INV-ENC-J3] A rodada INTEIRA foi a que a lei manda. Vem depois dos quatro
    # de cima de propósito: eles são específicos (título, memória, disponibilidade,
    # relógio) e este é global, e uma sabotagem em qualquer regra de elegibilidade
    # também muda a alocação. Com o global primeiro, o vermelho diria sempre
    # "[INV-ENC-J3]" e esconderia qual regra caiu.
    #
    # O estado de ANTES da varredura do motor se reconstrói do estado de agora: o
    # motor não mexe em perfil nenhum, então quem estava com oferta pendente antes
    # é quem está com ela agora menos os que acabaram de receber; quem estava
    # `na_fila` antes é quem está `na_fila` agora mais as encomendas recém
    # ofertadas; e quem já tinha visto cada encomenda é a memória de agora menos o
    # escolhido desta rodada.
    recem = {oferta.encomenda_id: oferta.aluno_id for oferta in novas}
    if novas:
        na_fila_antes = sorted(
            list(
                Encomenda.objects.filter(site_id=site, status=Encomenda.Status.NA_FILA)
            )
            + list(Encomenda.objects.filter(pk__in=recem)),
            key=lambda encomenda: encomenda.criada_em,
        )
        esperada = a_alocacao_que_a_lei_manda(
            perfis,
            na_fila_antes,
            set(alunos_com_pendente) - set(recem.values()),
            {
                encomenda_id: viram - {recem.get(encomenda_id)}
                for encomenda_id, viram in memoria.quem_ja_viu.items()
            },
            regua,
            agora,
        )
        assert recem == esperada, (
            f"[INV-ENC-J3] quebrado em {agora.isoformat()}: o motor ofertou "
            f"{recem}, e a regra da lei §6.2, calculada por fora, manda "
            f"{esperada}."
        )

    if depois_do_tique:
        # [INV-ENC-J9] Nenhuma encomenda continua esperando um aluno da fila
        # depois do prazo, uma vez que o relógio rodou.
        for encomenda in Encomenda.objects.filter(
            site_id=site, status__in=ESPERANDO_UM_ALUNO
        ):
            esperou = agora - povoado.chegada[encomenda.pk]
            assert esperou < regua.prazo_da_fila, (
                f"[INV-ENC-J9] quebrado em {agora.isoformat()}: a encomenda "
                f"{encomenda.pk} chegou em "
                f"{povoado.chegada[encomenda.pk].isoformat()}, esperou {esperou} "
                f"em {encomenda.status!r} e o prazo da fila e "
                f"{regua.prazo_da_fila}."
            )


# ---------------------------------------------------------------------------
# O QUE OS ALUNOS FAZEM — cada gesto é o gesto de produção, nunca um `update`
# ---------------------------------------------------------------------------


def _os_alunos_respondem_as_ofertas(povoado, agora, placar, entrega_prevista):
    """Aceitar, passar ou sumir, na ordem da chegada das encomendas.

    A ordem é `encomenda__criada_em` e não a chave primária: os identificadores
    são UUID sorteados, e uma varredura por eles faria o sorteio desta simulação
    depender de números que mudam a cada rodada. A semente fixa não vale nada se
    a ORDEM em que ela é consumida for aleatória.
    """
    pendentes = list(
        Oferta.objects.filter(
            site_id=povoado.site_id, resultado=Oferta.Resultado.PENDENTE
        ).order_by("encomenda__criada_em")
    )
    for oferta in pendentes:
        jeito = povoado.temperamentos[oferta.aluno_id]
        dado = povoado.sorteio.random()
        if dado < jeito.p_aceita:
            desfecho = gestos.aceitar(
                oferta.pk, oferta.aluno_id, agora, site_id=povoado.site_id
            )
            if desfecho.feito:
                placar.aceites_na_fila += 1
                entrega_prevista[oferta.encomenda_id] = (
                    agora + timedelta(hours=jeito.horas_de_trabalho),
                    oferta.aluno_id,
                )
        elif dado < jeito.p_aceita + jeito.p_passa:
            desfecho = gestos.passar(
                oferta.pk,
                oferta.aluno_id,
                jeito.motivo_preferido,
                agora,
                site_id=povoado.site_id,
            )
            if desfecho.feito:
                placar.passes[jeito.motivo_preferido] = (
                    placar.passes.get(jeito.motivo_preferido, 0) + 1
                )
                if desfecho.encomenda_em == Encomenda.Status.PARA_RECLASSIFICAR:
                    placar.reclassificadas += 1
        # O terceiro caminho é não fazer nada. É o silêncio do plano §6.3, e
        # quem o transforma em consequência é o relógio, não este arquivo.


def _alguem_tenta_a_chamada_aberta(povoado, agora, placar):
    """Um aluno sorteado tenta levar cada chamada aberta (Anexo B, cenário 4).

    Um por encomenda por passo, e não a turma inteira: a chamada aberta avisa
    todos os elegíveis, mas simular cem tentativas por minuto custaria cem
    consultas para provar a mesma coisa que uma prova. Ao longo dos dias
    simulados cada chamada aberta recebe dezenas de tentativas, e o gesto recusa
    sozinho quem não pode levar.
    """
    abertas = list(
        Encomenda.objects.filter(
            site_id=povoado.site_id, status=Encomenda.Status.ABERTA
        ).order_by("criada_em")
    )
    for encomenda in abertas:
        candidato = povoado.sorteio.choice(povoado.perfis)
        if povoado.sorteio.random() >= povoado.temperamentos[candidato.id].p_aceita:
            continue
        desfecho = gestos.aceitar_a_chamada_aberta(
            encomenda.pk, candidato.id, agora, site_id=povoado.site_id
        )
        if desfecho.feito:
            placar.aceites_em_chamada_aberta += 1


def _o_interruptor(povoado, agora, placar):
    """Quem some pausa; quem volta religa. Pelos gestos de verdade, sempre.

    Pausar e religar entram na simulação porque são o que o [INV-ENC-J4] promete:
    *"o aluno religa e volta ao MESMO lugar"*. Sem ninguém pausando, a promessa
    ficaria só escrita.
    """
    for perfil in PerfilProfissional.objects.filter(site_id=povoado.site_id).order_by(
        "id"
    ):
        jeito = povoado.temperamentos[perfil.id]
        dado = povoado.sorteio.random()
        if perfil.disponibilidade == PerfilProfissional.Disponibilidade.DISPONIVEL:
            if (
                dado < jeito.p_pausa
                and gestos.pausar(perfil.id, site_id=povoado.site_id).feito
            ):
                placar.pausas_pelo_aluno += 1
        elif perfil.disponibilidade == PerfilProfissional.Disponibilidade.PAUSADO:
            if (
                dado < jeito.p_religa
                and gestos.religar(perfil.id, agora, site_id=povoado.site_id).feito
            ):
                placar.voltas_a_fila += 1


def _o_trabalho_terminou_e_o_cliente_aprovou(povoado, agora, placar, entrega_prevista):
    """A Fase 3 e a Fase 5 encenadas: a encomenda chega ao fim e o aluno fica livre.

    Nada disto existe em código ainda. O simulador encena porque a fila só mostra
    a promessa do produto quando alguém ENTREGA: é a entrega aprovada que muda o
    primeiro termo da chave da lei §6.2, e é ela que faz o novato de ontem virar
    o veterano de amanhã. As transições passam pela máquina de estado de verdade,
    então nenhum caminho inventado aqui seria aceito pelo banco.
    """
    for encomenda_id, (quando, aluno_id) in sorted(
        entrega_prevista.items(), key=lambda item: item[1][0]
    ):
        if agora < quando:
            continue
        encomenda = Encomenda.objects.get(pk=encomenda_id)
        for status in DO_ACEITE_ATE_CONCLUIDA:
            encomenda.mudar_status(status, motivo="o simulador encena a Fase 3 e a 5")
        perfil = PerfilProfissional.objects.get(pk=aluno_id)
        perfil.entregas_aprovadas += 1
        perfil.save(update_fields=["entregas_aprovadas", "atualizado_em"])
        perfil.mudar_disponibilidade(PerfilProfissional.Disponibilidade.DISPONIVEL)
        placar.entregas_aprovadas += 1
        del entrega_prevista[encomenda_id]


# ---------------------------------------------------------------------------
# A SIMULAÇÃO
# ---------------------------------------------------------------------------


def test_cem_alunos_e_trinta_encomendas_nao_quebram_nenhum_invariante(povoado, capsys):
    """O portão da Fase 2: dias de fila cheia, e os dez de justiça de pé em todo instante.

    O laço é o do plano §7.4: a cada hora simulada o tique expira, abre e oferece;
    depois os alunos respondem, tentam as chamadas abertas e mexem no
    interruptor; depois quem terminou o trabalho volta para a fila com uma
    entrega a mais. Entre uma coisa e outra, os dez invariantes.
    """
    site = povoado.site_id
    regua = Regua.do_banco(povoado.t_zero, site_id=site)
    janela = relogio.Janela.do_banco(povoado.t_zero, site_id=site)
    memoria = Memoria()
    placar = Placar()
    entrega_prevista = {}
    pausados_por_silencio = set()

    agora = povoado.t_zero
    fim = povoado.t_zero + timedelta(days=DIAS_SIMULADOS)
    while agora <= fim:
        batida = tique.rodar(agora, site_id=site)
        novas = list(Oferta.objects.filter(pk__in=batida.rodada.ofertas_criadas))
        for oferta in novas:
            memoria.nascimento[oferta.pk] = agora
            placar.alunos_que_receberam.add(oferta.aluno_id)
        placar.ofertas += len(novas)
        placar.silencios += len(batida.ofertas_expiradas)
        placar.viraram_chamada_aberta += len(batida.encomendas_abertas)
        # A pausa por três silêncios se conta pela BORDA, e não pelo retrato:
        # `mudar_disponibilidade` limpa `modo_da_pausa` quando o aluno religa,
        # então perguntar "quantos estão pausados agora?" daria zero num mundo em
        # que a pausa aconteceu vinte vezes e foi desfeita vinte vezes.
        pausados_agora = set(
            PerfilProfissional.objects.filter(
                site_id=site,
                modo_da_pausa=PerfilProfissional.ModoDaPausa.POR_SILENCIO,
            ).values_list("id", flat=True)
        )
        placar.pausas_por_silencio += len(pausados_agora - pausados_por_silencio)
        pausados_por_silencio = pausados_agora

        conferir_os_dez(
            povoado, agora, memoria, regua, janela, novas=novas, depois_do_tique=True
        )

        # [INV-ENC-J10] Reexecutar sem mudança de estado não cria nada. Conferido
        # em TODO passo, e não uma vez no fim: a idempotência que só vale num
        # estado é a que quebra no dia do deploy com dois workers de pé.
        de_novo = tique.rodar(agora, site_id=site)
        assert (
            de_novo.rodada.quantas_ofertas == 0
            and de_novo.ofertas_expiradas == ()
            and de_novo.encomendas_abertas == ()
        ), (
            f"[INV-ENC-J10] quebrado em {agora.isoformat()}: a segunda passada "
            f"no mesmo instante criou {de_novo.rodada.quantas_ofertas} oferta(s), "
            f"expirou {len(de_novo.ofertas_expiradas)} e abriu "
            f"{len(de_novo.encomendas_abertas)}."
        )

        _os_alunos_respondem_as_ofertas(povoado, agora, placar, entrega_prevista)
        _alguem_tenta_a_chamada_aberta(povoado, agora, placar)
        _o_interruptor(povoado, agora, placar)
        _o_trabalho_terminou_e_o_cliente_aprovou(
            povoado, agora, placar, entrega_prevista
        )

        conferir_os_dez(
            povoado, agora, memoria, regua, janela, novas=[], depois_do_tique=False
        )
        agora += PASSO

    esperando = Encomenda.objects.filter(
        site_id=site, status__in=ESPERANDO_UM_ALUNO
    ).count()
    abertas_sem_dono = Encomenda.objects.filter(
        site_id=site, status=Encomenda.Status.ABERTA
    ).count()
    concluidas = Encomenda.objects.filter(
        site_id=site, status=Encomenda.Status.CONCLUIDA
    ).count()

    texto = placar.em_texto(
        povoado,
        esperando=esperando,
        abertas_sem_dono=abertas_sem_dono,
        concluidas=concluidas,
    )
    with capsys.disabled():
        print(texto)

    # O SIMULADOR PRECISA TER ACONTECIDO. Sem estas linhas, um mundo em que
    # ninguém recebe, ninguém aceita e ninguém some passaria nos dez invariantes
    # sem provar nada — o verde vazio que a `armadilhas/132` descreve.
    # Os pisos são a METADE do que esta semente produz, e não o número exato: o
    # que eles guardam é "o mecanismo aconteceu", não "aconteceu tantas vezes".
    # Um piso igual ao valor medido viraria vermelho a cada ajuste legítimo do
    # motor, e o vermelho que chega sempre é o vermelho que ninguém lê.
    assert placar.ofertas > 50, texto
    assert placar.aceites_na_fila > 10, texto
    assert placar.total_de_passes > 10, texto
    assert placar.silencios > 25, texto
    assert placar.pausas_por_silencio > 0, texto
    assert placar.viraram_chamada_aberta > 0, texto
    assert placar.aceites_em_chamada_aberta > 0, texto
    assert placar.reclassificadas > 0, texto
    assert placar.entregas_aprovadas > 10, texto
    assert len(placar.alunos_que_receberam) > 20, texto
    # A conta que fecha o [INV-ENC-J6] pelo total: cada oferta é um par
    # (encomenda, aluno) inédito, então o número de pares tem de ser o número de
    # ofertas. Uma repetição em qualquer minuto dos oito dias derruba a igualdade.
    assert len(memoria.pares) == placar.ofertas, texto
