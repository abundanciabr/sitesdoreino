"""O simulador do mundo inteiro: as duas pistas rodam dias a fio e os 24 invariantes ficam de pé.

Lei: `docs/decisoes/DECISAO-fila-do-primeiro-dolar.md` §5 (os dez invariantes de
justiça) e §6 (os parâmetros). Emenda:
`docs/decisoes/PLANO-AREA-DE-NEGOCIACAO.md` §3 (o Mural), §4 (a Proposta e o
Acordo) e §8 (os treze invariantes novos, M1 a M5 e N1 a N8). Produto:
`PLANO-MESTRE-FILA-DO-PRIMEIRO-DOLAR.md` §6 (o livro de regras), §7.4 (o
algoritmo) e o Anexo B (os cenários de aceite).

Este é o degrau 2.13 da escada. No degrau 2.6 este arquivo rodava cem alunos
contra a FILA; agora ele roda o mundo inteiro: alunos com zero, uma e cinco
entregas aprovadas, projetos dos três níveis, as duas pistas ao mesmo tempo,
reservas do Mural que caducam, propostas aceitas, recusadas e vencidas, e rodadas
de negociação que se esgotam. Os vinte e quatro guardas de `tests/test_inv_*.py`
medem cada invariante isolado, num cenário de duas ou três pessoas montado à mão.
Este arquivo mede outra coisa, e é por isso que ele existe: **cem alunos e trinta
projetos se atropelando durante dias**, com gente aceitando, passando, sumindo,
pegando, propondo, cedendo, pausando e voltando ao mesmo tempo. É onde uma
injustiça que nenhum cenário de três pessoas produz teria de aparecer.

A ASSERÇÃO É POR PASSO, NUNCA POR RESULTADO FINAL
--------------------------------------------------
Os vinte e quatro são conferidos DUAS vezes por hora simulada: depois do tique
(quando o sistema já reagiu ao relógio) e depois dos gestos das pessoas. Um
simulador que só olhasse o estado final seria quase inútil: a fila pode passar
por um minuto com duas ofertas pendentes para o mesmo aluno e chegar limpa ao
fim, e é exatamente esse minuto que arruinaria a promessa do produto.

O ORÁCULO É A LEI, E NÃO O MOTOR
---------------------------------
Nenhuma conferência daqui chama `motor.por_que_nao` nem `motor.CHAVE_DA_ORDEM`,
e nenhuma chama `mural.vaga_de` nem `mural.tem_elegivel_disponivel`. A
elegibilidade das duas pistas, a ordem de prioridade e a memória do Mural estão
**reescritas neste arquivo**, do plano §6.1 e §6.2 e da emenda §3.1, com os
números lidos do banco. Não é duplicação por descuido: um teste que perguntasse
ao motor se o motor acertou mediria a si mesmo. O que prova alguma coisa é a
SEGUNDA medida, feita por outro caminho, chegando ao mesmo lugar.

A única exceção é `mural.listar`, e ela é o oposto de uma consulta ao juiz: o
[INV-ENC-M1] e o [INV-ENC-M4] falam sobre A LISTA QUE O ALUNO VÊ, então o guarda
CHAMA a lista de verdade e a compara, projeto por projeto e na ordem, com a lista
que o oráculo montou por fora.

O QUE O SIMULADOR ENCENA, E QUE AINDA NÃO EXISTE
-------------------------------------------------
A entrega, a revisão e a aprovação do cliente são Fase 3 e Fase 5, e nenhuma
delas tem código. Aqui elas são encenadas a partir de `em_producao`, porque sem
alguém ENTREGANDO a fila nunca mostra a promessa do produto acontecendo, que é o
novato passando na frente do veterano. Quem faz a transição é a máquina de estado
de verdade (`Encomenda.TRANSICOES`), então nada aqui inventa caminho que o banco
não aceite. Tudo o que vem antes disso (nascer na pista certa, pegar, propor,
contrapropor, aceitar, registrar o pagamento, começar a produzir) passa pelos
gestos de produção, sem um `update` sequer.

OS BURACOS DECLARADOS
---------------------
Duas propriedades deste arquivo têm exceções ESCRITAS, com nome, contagem e
tarefa de conserto. Elas existem porque a alternativa seria pior: afrouxar a
asserção até o vermelho sumir esconderia, junto com o buraco conhecido, todo
buraco novo que aparecesse depois. Cada exceção é medida separadamente, e o
guarda que reprova continua valendo zero. `BURACOS_DECLARADOS` é a lista, e cada
linha diz a tarefa que a tapa.

O PLACAR
--------
Sai em texto no fim, para ser lido por gente e conferido contra o piloto de papel
da Fase 1. Ele também é asserção: um simulador em que ninguém aceita, ninguém
pega, ninguém propõe e ninguém some passaria nos vinte e quatro invariantes sem
provar nada, e as asserções do fim do arquivo existem para que esse verde vazio
seja impossível.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from apps.encomendas import gestos, mural, negociacao, relogio, tique
from apps.encomendas.models import (
    ESTADOS_DO_MURAL_RESERVAVEL,
    Acordo,
    Encomenda,
    Oferta,
    Parametro,
    PerfilProfissional,
    Proposta,
    ReservaDoMural,
)

# O tamanho do passo e a duração da simulação. Não são parâmetros da lei §6 (o
# mantenedor não os edita numa tela): são a régua do experimento. Uma hora é o
# maior passo que ainda enxerga o relógio de três horas úteis da oferta e o da
# reserva do Mural nascerem, correrem e vencerem; oito dias são o menor prazo que
# ainda mostra as duas pistas girarem inteiras: um projeto pego no primeiro dia
# volta como entrega aprovada a tempo de mudar a ordem da lei §6.2 antes do fim.
PASSO = timedelta(hours=1)
DIAS_SIMULADOS = 8

# Quantos alunos abrem o Mural e olham cada cartão a cada hora simulada. Régua do
# experimento, e não regra: o Mural de verdade avisa todo elegível, e simular cem
# cliques por hora custaria cem consultas para provar o que três provam.
QUANTOS_OLHAM_CADA_CARTAO = 3

# QUEM ASSINA PELA ESCOLA. Enquanto a única origem for `escola` (§1, terceira
# resposta do mantenedor), quem abre o projeto, quem aceita a proposta e quem
# registra o pagamento é a mesma equipe, e o §7 diz em voz alta que o que torna
# isso auditável é o REGISTRO de quem decidiu. O banco exige o autor
# (`acordo_tem_quem_aceitou`, `confirmacao_de_pagamento_tem_autor_e_data`), e é
# por isso que este nome existe em vez de uma string vazia.
O_PLANTAO = "plantao-1"

# A trava de uma negociação viva por aluno é verificada por comportamento no
# simulador: nenhum aluno pode terminar um passo com dois projetos nas mãos, e
# nenhum gesto pode deixar escapar a IntegrityError desta regra.


def apesar_do_estouro(_placar, chamada):
    """Executa o gesto; a segunda negociação precisa ser recusada antes do banco."""
    return chamada()


# ---------------------------------------------------------------------------
# O ORÁCULO — o plano §6.1 e §6.2 e a emenda §3.1, reescritos aqui
# ---------------------------------------------------------------------------

# A hierarquia dos títulos (plano §6.1). Título vazio é o perfil que nunca passou
# pelo professor: ele fica abaixo de tudo.
TITULOS_EM_ORDEM = ("", "nivel_1", "nivel_2", "nivel_3")

# O título mínimo de cada nível de projeto, lido do plano §6.1 palavra por
# palavra: *"Iniciante: título Modelador Nível 1. Intermediário: título Nível 2 e
# pelo menos 1 entrega aprovada. Avançado: título Nível 3 e 5 entregas aprovadas
# e nenhum abandono nos últimos 90 dias."*
TITULO_MINIMO = {
    Encomenda.Nivel.INICIANTE: "nivel_1",
    Encomenda.Nivel.INTERMEDIARIO: "nivel_2",
    Encomenda.Nivel.AVANCADO: "nivel_3",
}

# A pista em que cada nível NASCE, da emenda §3.1, regras 2 e 3. É a régua do
# [INV-ENC-M2]: o Iniciante nasce na fila e só chega ao Mural pela chamada
# aberta, que não é prateleira reservável.
PISTA_QUE_A_EMENDA_MANDA = {
    Encomenda.Nivel.INICIANTE: Encomenda.Status.NA_FILA,
    Encomenda.Nivel.INTERMEDIARIO: Encomenda.Status.NO_MURAL,
    Encomenda.Nivel.AVANCADO: Encomenda.Status.NO_MURAL,
}

# O que o Mural mostra (emenda §3.1 e §3.3): a prateleira reservável e a chamada
# aberta. `reservada` não aparece porque já tem dono.
VISIVEIS_NO_MURAL = (Encomenda.Status.NO_MURAL, Encomenda.Status.ABERTA)

# A linha do começo da produção até a aprovação do cliente (plano §7.2). É a Fase
# 3 e a Fase 5 encenadas: o simulador só precisa que o aluno volte a ficar livre
# com uma entrega a mais. Começa em `entregue` porque tudo o que vem antes (o
# acordo, o caixa, o começo da produção) passou pelos gestos de verdade.
DA_PRODUCAO_ATE_CONCLUIDA = (
    Encomenda.Status.ENTREGUE,
    Encomenda.Status.EM_REVISAO,
    Encomenda.Status.AGUARDANDO_CLIENTE,
    Encomenda.Status.APROVADA,
    Encomenda.Status.CONCLUIDA,
)

# Os estados em que um projeto já passou do caixa e está a caminho da entrega. É
# a régua do [INV-ENC-N4]: nenhum deles existe sem Acordo E pagamento confirmado
# com autor.
DEPOIS_DO_CAIXA = (
    Encomenda.Status.EM_PRODUCAO,
    Encomenda.Status.ENTREGUE,
    Encomenda.Status.EM_REVISAO,
    Encomenda.Status.AGUARDANDO_CLIENTE,
    Encomenda.Status.EM_CORRECAO,
    Encomenda.Status.APROVADA,
    Encomenda.Status.CONCLUIDA,
)

ESPERANDO_UM_ALUNO = (Encomenda.Status.NA_FILA, Encomenda.Status.OFERECIDA)

# Onde um projeto ESPERA por gente: as duas prateleiras, as duas mãos e a mesa da
# negociação. É a lista que a propriedade 2 varre atrás de projeto preso.
ESPERAS = (
    Encomenda.Status.NA_FILA,
    Encomenda.Status.OFERECIDA,
    Encomenda.Status.NO_MURAL,
    Encomenda.Status.RESERVADA,
    Encomenda.Status.ABERTA,
    Encomenda.Status.EM_NEGOCIACAO,
)

# Os estados em que o projeto está NAS MÃOS de um aluno, e por isso ocupa a vez
# dele. É a régua do [INV-ENC-N6] como a emenda §4.2 o escreve: *"um aluno tem no
# máximo UMA negociação viva por vez, somando as duas pistas."*
NEGOCIACAO_VIVA = (Encomenda.Status.RESERVADA, Encomenda.Status.EM_NEGOCIACAO)

# Onde um projeto ainda ocupa as mãos de quem está com ele. Serve ao
# [INV-ENC-N5]: um aluno marcado como "trabalhando" e sem nenhum destes é um
# aluno preso fora da fila por uma negociação que já morreu.
NAS_MAOS_DO_ALUNO = (
    Encomenda.Status.RESERVADA,
    Encomenda.Status.EM_NEGOCIACAO,
    Encomenda.Status.ACORDADA,
    Encomenda.Status.AGUARDANDO_PAGAMENTO,
    Encomenda.Status.EM_PRODUCAO,
    Encomenda.Status.ENTREGUE,
    Encomenda.Status.EM_REVISAO,
    Encomenda.Status.AGUARDANDO_CLIENTE,
    Encomenda.Status.EM_CORRECAO,
)

# QUANTO TEMPO UM PROJETO PODE FICAR PARADO sem que nada aconteça com ele. Não é
# parâmetro da lei: é o teto da propriedade 2, e sai da soma das esperas
# LEGÍTIMAS mais longas do desenho. A maior delas é a validade da proposta, 24
# horas ÚTEIS, que numa janela de 14 horas por dia e começando de noite chega a
# cerca de dois dias corridos. Três dias dão folga de um dia inteiro sobre a
# maior espera desenhada, e qualquer coisa acima disso é projeto preso.
TETO_PARADO = timedelta(days=3)


@dataclass(frozen=True)
class Regua:
    """Os números da lei §6 e da emenda §9 que o oráculo consulta, lidos do banco.

    Lidos do BANCO e não escritos aqui: o oráculo precisa ser uma segunda medida
    da regra, não uma segunda cópia dos valores. Se o mantenedor mudar
    `entregas_para_nivel_avancado` numa tela, o motor e este arquivo mudam juntos.
    """

    entregas_minimas: dict
    janela_sem_abandono: timedelta
    relogio_da_oferta: timedelta
    prazo_da_fila: timedelta
    prazo_da_chamada_aberta: timedelta
    rodadas: int
    limite_da_justificativa: int
    dias_de_revisao: int

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
            prazo_da_chamada_aberta=horas("horas_para_escalar_chamada_aberta"),
            rodadas=numero("rodadas_de_negociacao"),
            limite_da_justificativa=numero("limite_da_justificativa"),
            dias_de_revisao=numero("dias_de_revisao_no_prazo_prometido"),
        )


def elegivel_pela_lei(
    perfil, nivel, ja_viram, com_oferta, regua, agora, *, com_negociacao=frozenset()
):
    """Este aluno pode receber um projeto deste nível, agora? (plano §6.1)

    Escrita de novo, longe do motor, e na ordem em que a lei está escrita. É a
    régua contra a qual o [INV-ENC-J3], o [INV-ENC-J5] e o [INV-ENC-M1] são
    medidos. `ja_viram` é a memória da pista: na fila são as ofertas
    ([INV-ENC-J6]), no Mural são as reservas ([INV-ENC-M3]), e na chamada aberta
    é o conjunto VAZIO, porque a chamada aberta é a exceção literal da lei §6.4.
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
    if perfil.id in com_negociacao:
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


def a_alocacao_que_a_lei_manda(
    perfis,
    na_fila,
    com_oferta,
    quem_ja_viu,
    regua,
    agora,
    *,
    com_negociacao=frozenset(),
):
    """A rodada inteira da FILA, calculada por fora do motor. O oráculo do [INV-ENC-J3].

    É o laço do plano §7.4 escrito de novo: *"para cada encomenda em `na_fila`,
    da mais antiga para a mais nova (...) escolhido = min(elegiveis, chave =
    (entregas_aprovadas, data_entrada_fila))"*. Quem recebe passa a ter oferta
    pendente para o resto da varredura, e é isso que impede uma pessoa só de levar
    a fila inteira numa passada.

    Conferir a ALOCAÇÃO INTEIRA, e não cada oferta isolada, é o que dá dente ao
    guarda. Olhando uma oferta de cada vez, uma troca entre dois projetos da
    mesma rodada (o primeiro indo para quem devia levar o segundo, e vice-versa)
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
                perfil,
                encomenda.nivel,
                ja_viram,
                ocupados,
                regua,
                agora,
                com_negociacao=com_negociacao,
            )
        ]
        if not aptos:
            # Ninguém elegível: o projeto FICA onde está, e quem o vira em
            # chamada aberta é o relógio das 24h, nunca esta varredura.
            continue
        vencedor = min(aptos, key=lugar_na_ordem)
        esperada[encomenda.pk] = vencedor.id
        ocupados.add(vencedor.id)
    return esperada


def quem_ve_no_mural(
    projeto, perfis, memoria, com_oferta, regua, agora, *, com_negociacao=frozenset()
):
    """Quem enxerga ESTE projeto na prateleira, pela emenda §3.1. O oráculo do M1.

    A memória do Mural são as RESERVAS, e não as ofertas, e a diferença é
    deliberada: um projeto Iniciante chega ao Mural em chamada aberta, e a chamada
    aberta é a exceção literal do [INV-ENC-J6] (plano §6.4). Ler as ofertas aqui
    reintroduziria, pela porta dos fundos, a proibição que a lei já excetuou, e o
    guarda ficaria verde contra uma regra que o produto não tem.
    """
    ja_pegaram = memoria.quem_ja_pegou.get(projeto.pk, set())
    return [
        perfil
        for perfil in perfis
        if elegivel_pela_lei(
            perfil,
            projeto.nivel,
            ja_pegaram,
            com_oferta,
            regua,
            agora,
            com_negociacao=com_negociacao,
        )
    ]


# ---------------------------------------------------------------------------
# OS BURACOS DECLARADOS — o que já se sabe que não tem saída, com nome e tarefa
# ---------------------------------------------------------------------------

# Cada linha é um jeito de um projeto ficar parado que o CÓDIGO DE HOJE não
# resolve. Elas não afrouxam a propriedade 2: elas a dividem em duas, e a metade
# que vale zero (os presos por motivo NOVO) continua sendo o guarda de verdade.
# Afrouxar o teto até o vermelho sumir esconderia, junto com o buraco conhecido,
# todo buraco novo que aparecesse depois dele.
PRESO_NA_PRATELEIRA_COM_ELEGIVEL = "no mural com elegivel que nao pega (por desenho)"

BURACOS_DECLARADOS = (PRESO_NA_PRATELEIRA_COM_ELEGIVEL,)


def por_que_esta_preso(projeto, tem_proposta_de_pe, tem_elegivel):
    """O nome do buraco em que este projeto caiu, ou `""` se ele é novidade.

    - **`em_negociacao` sem proposta**: quem aceita uma oferta da FILA (ou uma
      chamada aberta) cai em `em_negociacao` na hora, e o relógio da reserva, que
      é do Mural, não cobre esse caso. Se o aluno nunca preencher o primeiro
      formulário, não existe proposta para vencer, e nem o projeto nem o aluno
      saem de lá. Achado por este simulador em 07/09/2026.
    - **`no_mural` com elegível**: é espera, e não encalhe. A emenda §3.1 escreve
      as duas condições do [INV-ENC-M5] como E, e diz por quê: *"um projeto que
      passou o prazo COM elegíveis disponíveis fica onde está: ele ainda pode ser
      pego."* Retirá-lo da prateleira seria recolher o que a prateleira ainda
      pode vender.
    """
    if projeto.status == Encomenda.Status.NO_MURAL and tem_elegivel:
        return PRESO_NA_PRATELEIRA_COM_ELEGIVEL
    return ""


# ---------------------------------------------------------------------------
# O PLACAR — o que aconteceu, em português, para conferir contra o piloto
# ---------------------------------------------------------------------------


def _linha(rotulo, valor, *, recuo=2):
    """Rótulo, pontinhos até a mesma coluna, valor. Uma só, para tudo alinhar."""
    return f"{' ' * recuo}{rotulo} ".ljust(56, ".") + f" {valor}"


@dataclass
class Placar:
    # A FILA
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
    # O MURAL
    nasceram_no_mural: int = 0
    pegadas_no_mural: int = 0
    reservas_que_venceram: int = 0
    ao_plantao_sem_elegivel: int = 0
    # A NEGOCIAÇÃO
    propostas_do_aluno: int = 0
    contrapropostas_do_cliente: int = 0
    contrapropostas_do_aluno: int = 0
    acordos_pelo_cliente: int = 0
    acordos_pelo_aluno: int = 0
    cliente_calado: int = 0
    aluno_calado: int = 0
    rodadas_esgotadas: int = 0
    desistencias_do_aluno: int = 0
    desistencias_do_cliente: int = 0
    pagamentos_registrados: int = 0
    producoes_iniciadas: int = 0
    prazos_que_comecaram_depois_do_acordo: int = 0
    # AS DUAS PROPRIEDADES E O QUE ELAS ENCONTRARAM
    presos: dict = field(default_factory=dict)
    zerados_servidos: set = field(default_factory=set)

    @property
    def total_de_passes(self):
        return sum(self.passes.values())

    @property
    def acordos(self):
        return self.acordos_pelo_cliente + self.acordos_pelo_aluno

    def em_texto(self, povoado, *, quantos_zerados, contagem):
        """O placar em português, para o mantenedor ler sem tradutor.

        Cada linha é um mecanismo do livro de regras acontecendo tantas vezes.
        Ele existe para ser conferido contra o piloto de papel da Fase 1, onde o
        professor anota as mesmas coisas à mão numa planilha, e por isso os
        rótulos são os do plano, não os das colunas do banco.
        """
        linhas = [
            "",
            "PLACAR DO SIMULADOR DAS DUAS PISTAS",
            f"{len(povoado.perfis)} alunos, {len(povoado.projetos)} projetos, "
            f"{DIAS_SIMULADOS} dias simulados, passo de "
            f"{int(PASSO.total_seconds() // 3600)} hora",
            "",
            "  A FILA",
            _linha("Ofertas feitas", self.ofertas, recuo=4),
            _linha("Aceites na fila", self.aceites_na_fila, recuo=4),
            _linha("Passes (com motivo)", self.total_de_passes, recuo=4),
        ]
        for motivo, quantos in sorted(self.passes.items()):
            linhas.append(
                _linha(dict(Oferta.MotivoDoPasse.choices)[motivo], quantos, recuo=6)
            )
        linhas += [
            _linha("Silencios (ofertas que venceram)", self.silencios, recuo=4),
            _linha(
                "Pausas automaticas por tres silencios",
                self.pausas_por_silencio,
                recuo=4,
            ),
            _linha("Pausas pelo proprio aluno", self.pausas_pelo_aluno, recuo=4),
            _linha("Voltas a fila (o aluno religou)", self.voltas_a_fila, recuo=4),
            _linha("Viraram chamada aberta", self.viraram_chamada_aberta, recuo=4),
            _linha(
                "Aceites em chamada aberta", self.aceites_em_chamada_aberta, recuo=4
            ),
            _linha("Mandados para reclassificar", self.reclassificadas, recuo=4),
            "",
            "  O MURAL",
            _linha("Projetos que nasceram no Mural", self.nasceram_no_mural, recuo=4),
            _linha("Pegadas no Mural", self.pegadas_no_mural, recuo=4),
            _linha(
                "Reservas que venceram sem proposta",
                self.reservas_que_venceram,
                recuo=4,
            ),
            _linha(
                "Ao plantao por falta de elegivel",
                self.ao_plantao_sem_elegivel,
                recuo=4,
            ),
            "",
            "  A NEGOCIACAO",
            _linha("Primeiras propostas do aluno", self.propostas_do_aluno, recuo=4),
            _linha(
                "Contrapropostas do cliente", self.contrapropostas_do_cliente, recuo=4
            ),
            _linha("Contrapropostas do aluno", self.contrapropostas_do_aluno, recuo=4),
            _linha("Acordos fechados", self.acordos, recuo=4),
            _linha("deles, aceitos pelo cliente", self.acordos_pelo_cliente, recuo=6),
            _linha("deles, aceitos pelo aluno", self.acordos_pelo_aluno, recuo=6),
            _linha("Cliente calou (foi ao plantao)", self.cliente_calado, recuo=4),
            _linha("Aluno calou (voltou a pista)", self.aluno_calado, recuo=4),
            _linha("Rodadas esgotadas sem acordo", self.rodadas_esgotadas, recuo=4),
            _linha("Desistencias do aluno", self.desistencias_do_aluno, recuo=4),
            _linha("Desistencias do cliente", self.desistencias_do_cliente, recuo=4),
            _linha(
                "Pagamentos registrados pela escola",
                self.pagamentos_registrados,
                recuo=4,
            ),
            _linha("Producoes iniciadas", self.producoes_iniciadas, recuo=4),
            _linha(
                "Prazos que comecaram depois do acordo",
                self.prazos_que_comecaram_depois_do_acordo,
                recuo=4,
            ),
            _linha("Entregas aprovadas no periodo", self.entregas_aprovadas, recuo=4),
            "",
            "  AS DUAS PROPRIEDADES QUE SO O SIMULADOR PROVA",
            _linha(
                "Alunos que receberam oferta", len(self.alunos_que_receberam), recuo=4
            ),
            _linha(
                f"deles, de zero entregas (de {quantos_zerados})",
                len(self.zerados_servidos),
                recuo=6,
            ),
            _linha("Projetos presos por motivo NOVO", self.presos.get("", 0), recuo=4),
        ]
        for buraco in BURACOS_DECLARADOS:
            linhas.append(_linha(buraco, self.presos.get(buraco, 0), recuo=6))
        linhas += [
            "",
            "  No fim: "
            + ", ".join(f"{quantos} {estado}" for estado, quantos in contagem),
            "",
        ]
        return "\n".join(linhas)


# ---------------------------------------------------------------------------
# O INSTANTÂNEO — o mundo lido UMA vez por conferência
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Instantaneo:
    """Tudo o que os vinte e quatro guardas precisam ver, num retrato só.

    Existe por coerência antes de por custo: os vinte e quatro se medem duas vezes
    por hora simulada, e cada um lendo o banco por conta própria veria retratos
    ligeiramente diferentes do mesmo instante. Um retrato só é uma verdade só.
    """

    perfis: list
    por_id: dict
    projetos: list
    por_pk: dict
    ofertas_pendentes: list
    com_oferta: set
    propostas: list
    propostas_por_projeto: dict
    de_pe_por_projeto: dict
    reservas: list
    reservas_vivas_por_projeto: dict
    acordos: set

    @classmethod
    def do_banco(cls, site_id):
        perfis = list(PerfilProfissional.objects.filter(site_id=site_id))
        projetos = list(Encomenda.objects.filter(site_id=site_id))
        pendentes = list(
            Oferta.objects.filter(site_id=site_id, resultado=Oferta.Resultado.PENDENTE)
        )
        propostas = list(Proposta.objects.filter(site_id=site_id))
        reservas = list(ReservaDoMural.objects.filter(site_id=site_id))

        propostas_por_projeto: dict = {}
        de_pe: dict = {}
        for proposta in propostas:
            propostas_por_projeto.setdefault(proposta.encomenda_id, []).append(proposta)
            if proposta.resultado == Proposta.Resultado.PENDENTE:
                de_pe.setdefault(proposta.encomenda_id, []).append(proposta)

        vivas: dict = {}
        for reserva in reservas:
            if reserva.resultado in ReservaDoMural.VIVAS:
                vivas.setdefault(reserva.encomenda_id, []).append(reserva)

        return cls(
            perfis=perfis,
            por_id={p.id: p for p in perfis},
            projetos=projetos,
            por_pk={p.pk: p for p in projetos},
            ofertas_pendentes=pendentes,
            com_oferta={o.aluno_id for o in pendentes},
            propostas=propostas,
            propostas_por_projeto=propostas_por_projeto,
            de_pe_por_projeto=de_pe,
            reservas=reservas,
            reservas_vivas_por_projeto=vivas,
            acordos=set(
                Acordo.objects.filter(site_id=site_id).values_list(
                    "encomenda_id", flat=True
                )
            ),
        )


@dataclass
class Memoria:
    """O que o guarda precisa lembrar entre um instante e o seguinte.

    Nada aqui é lido do módulo medido: são as ANOTAÇÕES do simulador sobre o que
    ele viu acontecer, no relógio simulado. `entrada_na_fila` e `entrada_no_mural`
    são a segunda medida do marco das 24 horas ([INV-ENC-J9] e [INV-ENC-M5]) — o
    código de produção o tira de `MudancaDeStatus`, e um guarda que lesse a mesma
    tabela não estaria medindo nada.
    """

    quem_ja_viu: dict = field(default_factory=dict)
    quem_ja_pegou: dict = field(default_factory=dict)
    nascimento: dict = field(default_factory=dict)
    pares: set = field(default_factory=set)
    pares_do_mural: set = field(default_factory=set)
    status_anterior: dict = field(default_factory=dict)
    entrada_na_fila: dict = field(default_factory=dict)
    entrada_no_mural: dict = field(default_factory=dict)
    situacao: dict = field(default_factory=dict)
    parado_desde: dict = field(default_factory=dict)
    presos_ja_contados: set = field(default_factory=set)
    acordo_congelado: dict = field(default_factory=dict)
    nunca_ficou_indisponivel: set = field(default_factory=set)

    def anotar(self, retrato, agora):
        """Atualiza os marcos e o cronômetro do "nada aconteceu", a cada retrato.

        O marco da espera se move quando o projeto ENTRA no par de estados de uma
        pista vindo de fora dele. As idas e vindas internas (`na_fila` para
        `oferecida` e de volta; `no_mural` para `reservada` e de volta) não zeram
        nada, e essa é a mesma regra que o código de produção segue: um relógio
        que reiniciasse a cada oferta ou a cada reserva nunca chegaria às 24h, e
        os dois invariantes seriam letra morta exatamente onde mais importam.
        """
        for projeto in retrato.projetos:
            antes = self.status_anterior.get(projeto.pk)
            if projeto.status in ESPERANDO_UM_ALUNO and antes not in ESPERANDO_UM_ALUNO:
                self.entrada_na_fila[projeto.pk] = agora
            if (
                projeto.status in ESTADOS_DO_MURAL_RESERVAVEL
                and antes not in ESTADOS_DO_MURAL_RESERVAVEL
            ):
                self.entrada_no_mural[projeto.pk] = agora
            self.status_anterior[projeto.pk] = projeto.status

            # A SITUAÇÃO é o retrato mínimo do que pode mudar num projeto sem que
            # o status mude: uma proposta nova, uma reserva nova, um dono novo.
            # Ela é o que separa "está parado há três dias" de "está negociando
            # há três dias", e sem ela a propriedade 2 acusaria toda negociação
            # longa como projeto preso.
            situacao = (
                projeto.status,
                projeto.aluno_id,
                len(retrato.propostas_por_projeto.get(projeto.pk, ())),
                len(retrato.reservas_vivas_por_projeto.get(projeto.pk, ())),
                len(retrato.de_pe_por_projeto.get(projeto.pk, ())),
            )
            if self.situacao.get(projeto.pk) != situacao:
                self.situacao[projeto.pk] = situacao
                self.parado_desde[projeto.pk] = agora

        for perfil in retrato.perfis:
            if perfil.disponibilidade != PerfilProfissional.Disponibilidade.DISPONIVEL:
                self.nunca_ficou_indisponivel.discard(perfil.id)


# ---------------------------------------------------------------------------
# OS DEZ DA JUSTIÇA, CONFERIDOS NUM INSTANTE
# ---------------------------------------------------------------------------


def conferir_os_dez(
    povoado, retrato, agora, memoria, regua, janela, *, novas, depois_do_tique
):
    """Os dez invariantes de justiça, neste instante. Reprova no primeiro que cair.

    `novas` são as ofertas criadas AGORA: os invariantes que falam do momento da
    escolha ([INV-ENC-J3], [INV-ENC-J5], [INV-ENC-J6], [INV-ENC-J7]) se medem
    nelas, porque é isso que eles dizem. Uma oferta feita de manhã para quem era
    o primeiro da fila continua correta à tarde, mesmo que outra pessoa tenha
    chegado na frente no meio do dia.

    `depois_do_tique` liga o [INV-ENC-J9]. Quem vira o projeto em chamada aberta
    é o tique, então a promessa dele é *"nenhum projeto continua esperando depois
    do prazo QUANDO O RELÓGIO RODA"*. Entre um tique e o seguinte, um aluno pode
    passar uma encomenda que já passou das 24h de volta para a fila, e ela fica
    esperando o próximo minuto. Isso é o desenho, não uma violação.
    """
    perfis = retrato.perfis
    por_id = retrato.por_id
    pendentes = retrato.ofertas_pendentes
    com_negociacao = {
        projeto.aluno_id
        for projeto in retrato.projetos
        if projeto.aluno_id is not None and projeto.status in NEGOCIACAO_VIVA
    }

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

    # [INV-ENC-J4] Passar, expirar, pausar e NEGOCIAR nunca mexem no lugar na fila.
    for perfil in perfis:
        assert perfil.data_entrada_fila == povoado.lugar_na_fila[perfil.id], (
            f"[INV-ENC-J4] quebrado em {agora.isoformat()}: o perfil "
            f"{perfil.id} entrou na fila em {povoado.lugar_na_fila[perfil.id]} e "
            f"agora aparece com {perfil.data_entrada_fila}. Só o abandono move o "
            "lugar, e esta simulação não abandona nada."
        )

    for oferta in novas:
        encomenda = retrato.por_pk[oferta.encomenda_id]
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
    # `na_fila` antes é quem está `na_fila` agora mais os projetos recém
    # ofertados; e quem já tinha visto cada encomenda é a memória de agora menos o
    # escolhido desta rodada.
    recem = {oferta.encomenda_id: oferta.aluno_id for oferta in novas}
    if novas:
        na_fila_antes = sorted(
            [
                projeto
                for projeto in retrato.projetos
                if projeto.status == Encomenda.Status.NA_FILA or projeto.pk in recem
            ],
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
            com_negociacao=com_negociacao,
        )
        assert recem == esperada, (
            f"[INV-ENC-J3] quebrado em {agora.isoformat()}: o motor ofertou "
            f"{recem}, e a regra da lei §6.2, calculada por fora, manda "
            f"{esperada}."
        )

    if depois_do_tique:
        # [INV-ENC-J9] Nenhuma encomenda continua esperando um aluno da fila
        # depois do prazo, uma vez que o relógio rodou. O marco é o do simulador
        # (`entrada_na_fila`), e não `criada_em`: um projeto devolvido pela
        # negociação recomeça a espera, e cobrá-lo desde o nascimento seria
        # medir uma promessa que a lei não faz.
        for encomenda in retrato.projetos:
            if encomenda.status not in ESPERANDO_UM_ALUNO:
                continue
            esperou = agora - memoria.entrada_na_fila[encomenda.pk]
            assert esperou < regua.prazo_da_fila, (
                f"[INV-ENC-J9] quebrado em {agora.isoformat()}: a encomenda "
                f"{encomenda.pk} entrou na espera em "
                f"{memoria.entrada_na_fila[encomenda.pk].isoformat()}, esperou "
                f"{esperou} em {encomenda.status!r} e o prazo da fila e "
                f"{regua.prazo_da_fila}."
            )


# ---------------------------------------------------------------------------
# OS CINCO DO MURAL
# ---------------------------------------------------------------------------


def conferir_o_mural(
    povoado, retrato, agora, memoria, regua, *, passo, depois_do_tique
):
    """Os cinco invariantes do Mural (emenda §8), neste instante."""
    site = povoado.site_id

    for projeto in retrato.projetos:
        # [INV-ENC-M2] Projeto Iniciante só chega ao Mural pela chamada aberta.
        # Medido no ESTADO, e não só no nascimento: a prateleira reservável é
        # `no_mural` e `reservada`, e um Iniciante em qualquer um dos dois quer
        # dizer que alguém trancou por três horas o que a fila já não colocou em
        # vinte e quatro, e quem pagaria a conta é o cliente.
        if projeto.nivel == Encomenda.Nivel.INICIANTE:
            assert projeto.status not in ESTADOS_DO_MURAL_RESERVAVEL, (
                f"[INV-ENC-M2] quebrado em {agora.isoformat()}: o projeto "
                f"{projeto.pk}, de nivel Iniciante, esta em {projeto.status!r}. "
                "Ele nasce na fila e so chega ao Mural pela chamada aberta, que "
                "nao se reserva."
            )

        # [INV-ENC-M3] O Mural não é leilão: uma reserva viva e uma proposta de
        # pé por projeto.
        vivas = retrato.reservas_vivas_por_projeto.get(projeto.pk, ())
        assert len(vivas) <= 1, (
            f"[INV-ENC-M3] quebrado em {agora.isoformat()}: o projeto "
            f"{projeto.pk} tem {len(vivas)} reservas vivas ao mesmo tempo."
        )
        de_pe = retrato.de_pe_por_projeto.get(projeto.pk, ())
        assert len(de_pe) <= 1, (
            f"[INV-ENC-M3] quebrado em {agora.isoformat()}: o projeto "
            f"{projeto.pk} tem {len(de_pe)} propostas vivas ao mesmo tempo, e o "
            "Mural nao e leilao."
        )

    # [INV-ENC-M3], terceira metade: ninguém pega o mesmo projeto duas vezes. A
    # conta fecha pelo total, como a do [INV-ENC-J6]: cada reserva é um par
    # (projeto, aluno) inédito, então o número de pares tem de ser o número de
    # reservas.
    for reserva in retrato.reservas:
        memoria.pares_do_mural.add((reserva.encomenda_id, reserva.aluno_id))
        memoria.quem_ja_pegou.setdefault(reserva.encomenda_id, set()).add(
            reserva.aluno_id
        )
    assert len(memoria.pares_do_mural) == len(retrato.reservas), (
        f"[INV-ENC-M3] quebrado em {agora.isoformat()}: ha "
        f"{len(retrato.reservas)} reservas para {len(memoria.pares_do_mural)} "
        "pares (projeto, aluno) distintos. Alguem pegou o mesmo projeto duas "
        "vezes, e o projeto giraria sem sair do lugar."
    )

    # [INV-ENC-M1] e [INV-ENC-M4], na lista de verdade. Dois alunos por passo, e
    # não os cem: `mural.listar` faz uma peneira por projeto, e cem listas por
    # hora simulada custariam centenas de milhares de consultas para provar o que
    # duas provam. Os dois giram por saltos diferentes, e ao longo dos oito dias
    # a turma inteira passa pela conferência mais de uma vez.
    na_prateleira = sorted(
        (p for p in retrato.projetos if p.status in VISIVEIS_NO_MURAL),
        key=lambda projeto: povoado.chegada[projeto.pk],
    )
    com_negociacao = {
        projeto.aluno_id
        for projeto in retrato.projetos
        if projeto.aluno_id is not None and projeto.status in NEGOCIACAO_VIVA
    }
    for salto in (1, 37):
        perfil = retrato.perfis[(passo * salto) % len(retrato.perfis)]
        esperada = [
            projeto.pk
            for projeto in na_prateleira
            if quem_ve_no_mural(
                projeto,
                [perfil],
                memoria,
                retrato.com_oferta,
                regua,
                agora,
                com_negociacao=com_negociacao,
            )
        ]
        vista = [p.pk for p in mural.listar(perfil.id, agora, site_id=site)]
        assert vista == esperada, (
            f"[INV-ENC-M1] quebrado em {agora.isoformat()}: o Mural mostrou "
            f"{vista} ao perfil {perfil.id}, e a regra da emenda §3.1, calculada "
            f"por fora, manda {esperada}."
        )
        # [INV-ENC-M4] A ordem é só a antiguidade, e nenhuma outra chave ordena.
        # Medida na lista DEVOLVIDA e contra a chegada que o simulador anotou,
        # que é uma segunda fonte: um destaque, um peso ou uma relevância que
        # entrassem no `order_by` apareceriam aqui como uma inversão.
        idades = [povoado.chegada[pk] for pk in vista]
        assert idades == sorted(idades), (
            f"[INV-ENC-M4] quebrado em {agora.isoformat()}: o Mural devolveu ao "
            f"perfil {perfil.id} uma lista fora da ordem de chegada ({idades})."
        )

    if not depois_do_tique:
        return

    # [INV-ENC-M5] Nada encalha em silêncio: passado o prazo, ou existe alguém
    # que possa pegar, ou o projeto foi ao plantão. As duas condições são E, e é
    # o que separa espera de encalhe (emenda §3.1, quarta regra).
    for projeto in retrato.projetos:
        if projeto.status != Encomenda.Status.NO_MURAL:
            continue
        esperou = agora - memoria.entrada_no_mural[projeto.pk]
        if esperou < regua.prazo_da_fila:
            continue
        aptos = quem_ve_no_mural(
            projeto,
            retrato.perfis,
            memoria,
            retrato.com_oferta,
            regua,
            agora,
            com_negociacao={
                outro.aluno_id
                for outro in retrato.projetos
                if outro.aluno_id is not None and outro.status in NEGOCIACAO_VIVA
            },
        )
        assert aptos, (
            f"[INV-ENC-M5] quebrado em {agora.isoformat()}: o projeto "
            f"{projeto.pk} entrou no Mural em "
            f"{memoria.entrada_no_mural[projeto.pk].isoformat()}, esperou "
            f"{esperou} (o prazo e {regua.prazo_da_fila}) e nao ha um unico "
            "aluno elegivel e disponivel para pega-lo. Ele tinha de ter ido ao "
            "plantao, e do jeito que esta ninguem sabe que ele parou."
        )


# ---------------------------------------------------------------------------
# OS OITO DA NEGOCIAÇÃO
# ---------------------------------------------------------------------------


def conferir_a_negociacao(povoado, retrato, agora, memoria, regua, placar):
    """Os oito invariantes da negociação (emenda §8), neste instante."""
    permitidos = set(povoado.entregaveis)

    for proposta in retrato.propostas:
        # [INV-ENC-N1] Nenhum texto entre cliente e aluno fora dos campos
        # estruturados. Os entregáveis saem da lista FECHADA do briefing, e a
        # justificativa cabe no limite do parâmetro: propor um entregável que
        # ninguém pediu é o texto livre com outro nome.
        fora = set(proposta.entregaveis) - permitidos
        assert not fora, (
            f"[INV-ENC-N1] quebrado em {agora.isoformat()}: a proposta "
            f"{proposta.pk} entrega {sorted(fora)}, que nao esta no briefing."
        )
        assert len(proposta.justificativa) <= regua.limite_da_justificativa, (
            f"[INV-ENC-N1] quebrado em {agora.isoformat()}: a justificativa da "
            f"proposta {proposta.pk} tem {len(proposta.justificativa)} "
            f"caracteres, e o limite do parametro e "
            f"{regua.limite_da_justificativa}."
        )

    for projeto in retrato.projetos:
        propostas = retrato.propostas_por_projeto.get(projeto.pk, ())

        # [INV-ENC-N2] As rodadas são contadas, e o teto é o do parâmetro. Medido
        # por LADO, porque o parâmetro da emenda §4.2 é "3 por lado".
        for lado in (Proposta.DeQuem.ALUNO, Proposta.DeQuem.CLIENTE):
            do_lado = [p for p in propostas if p.de_quem == lado]
            assert len(do_lado) <= regua.rodadas, (
                f"[INV-ENC-N2] quebrado em {agora.isoformat()}: o projeto "
                f"{projeto.pk} tem {len(do_lado)} propostas do lado {lado!r}, e "
                f"o teto do parametro e {regua.rodadas}."
            )

        if projeto.acordado_em is None:
            continue

        # [INV-ENC-N3] O Acordo congela, e o congelado não muda mais. A primeira
        # metade compara o combinado com a proposta ACEITA; a segunda guarda o
        # retrato e o compara a cada passo seguinte, que é o que transforma
        # "congelou" em "continua congelado".
        aceita = [p for p in propostas if p.resultado == Proposta.Resultado.ACEITA]
        assert len(aceita) == 1, (
            f"[INV-ENC-N3] quebrado em {agora.isoformat()}: o projeto "
            f"{projeto.pk} esta acordado e tem {len(aceita)} propostas aceitas."
        )
        congelado = tuple(
            getattr(projeto, f"acordo_{campo}")
            for campo in Proposta.CAMPOS_QUE_O_ACORDO_CONGELA
        )
        da_proposta = tuple(
            getattr(aceita[0], campo) for campo in Proposta.CAMPOS_QUE_O_ACORDO_CONGELA
        )
        assert congelado == da_proposta, (
            f"[INV-ENC-N3] quebrado em {agora.isoformat()}: o projeto "
            f"{projeto.pk} congelou {congelado}, e a proposta aceita dizia "
            f"{da_proposta}."
        )
        anterior = memoria.acordo_congelado.setdefault(projeto.pk, congelado)
        assert anterior == congelado, (
            f"[INV-ENC-N3] quebrado em {agora.isoformat()}: o acordo do projeto "
            f"{projeto.pk} era {anterior} e agora e {congelado}. Depois de "
            "fechado, so a mediacao muda, com autor e motivo."
        )

    for projeto in retrato.projetos:
        if projeto.status not in DEPOIS_DO_CAIXA:
            continue
        # [INV-ENC-N4] Nenhuma produção começa sem Acordo E confirmação de
        # pagamento registrada COM AUTOR. As quatro perguntas são separadas
        # porque mandam o plantão para lugares diferentes.
        assert projeto.acordado_em is not None, (
            f"[INV-ENC-N4] quebrado em {agora.isoformat()}: o projeto "
            f"{projeto.pk} chegou a {projeto.status!r} sem acordo."
        )
        assert projeto.pk in retrato.acordos, (
            f"[INV-ENC-N4] quebrado em {agora.isoformat()}: o projeto "
            f"{projeto.pk} chegou a {projeto.status!r} sem linha de Acordo."
        )
        assert projeto.confirmacao_de_pagamento and projeto.pagamento_confirmado_em, (
            f"[INV-ENC-N4] quebrado em {agora.isoformat()}: o projeto "
            f"{projeto.pk} chegou a {projeto.status!r} sem pagamento confirmado."
        )
        assert projeto.pagamento_confirmado_por, (
            f"[INV-ENC-N4] quebrado em {agora.isoformat()}: o projeto "
            f"{projeto.pk} chegou a {projeto.status!r} com pagamento confirmado "
            "e sem autor, e e o autor que o §7 existe para registrar."
        )

        # [INV-ENC-N8] O prazo do Acordo começa na confirmação do pagamento,
        # nunca no Acordo. Recalculado por fora, a partir da confirmação, e
        # comparado com o que a célula gravou.
        esperado = projeto.pagamento_confirmado_em + timedelta(
            days=projeto.acordo_prazo_dias
        )
        assert projeto.prazo_producao_ate == esperado, (
            f"[INV-ENC-N8] quebrado em {agora.isoformat()}: o projeto "
            f"{projeto.pk} acordou {projeto.acordo_prazo_dias} dias, teve o "
            f"pagamento confirmado em "
            f"{projeto.pagamento_confirmado_em.isoformat()} e o prazo de "
            f"producao vai ate {projeto.prazo_producao_ate}, e nao ate "
            f"{esperado}."
        )
        assert projeto.prazo_prometido_ate == esperado + timedelta(
            days=regua.dias_de_revisao
        ), (
            f"[INV-ENC-N8] quebrado em {agora.isoformat()}: o prazo prometido do "
            f"projeto {projeto.pk} nao e o de producao mais o dia de revisao."
        )

    # [INV-ENC-N5] Negociar é grátis, nas duas metades. A primeira é o lugar na
    # fila, e ela vale para todo mundo (o [INV-ENC-J4] a mede antes). A segunda é
    # a que só a negociação pode quebrar: um aluno marcado como "trabalhando" e
    # sem projeto nenhum nas mãos foi cobrado por uma demora que não foi dele,
    # que é a injustiça que a emenda §4.2 descreve com todas as letras.
    com_projeto = {
        projeto.aluno_id
        for projeto in retrato.projetos
        if projeto.aluno_id is not None and projeto.status in NAS_MAOS_DO_ALUNO
    }
    for perfil in retrato.perfis:
        if perfil.disponibilidade != PerfilProfissional.Disponibilidade.TRABALHANDO:
            continue
        assert perfil.id in com_projeto, (
            f"[INV-ENC-N5] quebrado em {agora.isoformat()}: o perfil "
            f"{perfil.id} esta 'trabalhando' e nao tem projeto nenhum nas maos. "
            "A negociacao que morreu tinha de o ter soltado, e do jeito que esta "
            "ele ficou fora da fila por uma demora que nao foi dele."
        )

    # [INV-ENC-N6] Um aluno nunca tem duas negociações vivas, somando as duas
    # pistas (emenda §4.2). São DUAS medidas da mesma frase: a proposta de pé,
    # que o índice `uma_proposta_viva_por_aluno` faz valer, e a VEZ nas mãos, que
    # é a régua mais larga da emenda e inclui quem pegou no Mural e ainda não
    # propôs.
    de_pe_por_aluno: dict = {}
    for proposta in retrato.propostas:
        if proposta.resultado == Proposta.Resultado.PENDENTE:
            de_pe_por_aluno.setdefault(proposta.aluno_id, []).append(proposta.pk)
    for aluno_id, quais in de_pe_por_aluno.items():
        assert len(quais) == 1, (
            f"[INV-ENC-N6] quebrado em {agora.isoformat()}: o perfil {aluno_id} "
            f"tem {len(quais)} propostas de pe ao mesmo tempo ({quais})."
        )

    nas_maos: dict = {}
    for projeto in retrato.projetos:
        if projeto.status in NEGOCIACAO_VIVA and projeto.aluno_id is not None:
            nas_maos.setdefault(projeto.aluno_id, []).append(projeto)
    for aluno_id, quais in nas_maos.items():
        if len(quais) == 1:
            continue
        assert False, (
            f"[INV-ENC-N6] quebrado em {agora.isoformat()}: o perfil {aluno_id} "
            f"tem {len(quais)} negociacoes vivas "
            f"({[p.pk for p in quais]}). A segunda negociação deveria ter sido "
            "recusada antes de chegar ao simulador."
        )


# ---------------------------------------------------------------------------
# O QUE AS PESSOAS FAZEM — cada gesto é o gesto de produção, nunca um `update`
# ---------------------------------------------------------------------------


def _os_alunos_respondem_as_ofertas(povoado, agora, placar):
    """Aceitar, passar ou sumir, na ordem da chegada dos projetos.

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
            if apesar_do_estouro(
                placar,
                lambda: gestos.aceitar(
                    oferta.pk, oferta.aluno_id, agora, site_id=povoado.site_id
                ),
            ).feito:
                placar.aceites_na_fila += 1
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


def _os_alunos_pegam_no_mural(povoado, agora, placar):
    """Um aluno sorteado tenta pegar cada projeto da prateleira (emenda §3.2).

    Um por projeto por passo, e não a turma inteira: o Mural avisa todo elegível,
    mas simular cem cliques por hora custaria cem consultas para provar a mesma
    coisa que três provam. **Três, e não um**, porque a maioria da turma tem zero
    entregas e não enxerga o Mural: com um sorteado por passo, quase toda
    tentativa caía em quem não podia pegar, e a prateleira ficava parada por
    falta de gente olhando, e não por falta de gente elegível. Ao longo dos oito
    dias cada projeto recebe centenas de tentativas, e o gesto recusa sozinho
    quem não pode pegar.

    **O aluno não se contém, e a falta de contenção é o experimento.** Nada aqui
    pergunta se ele já tem outra vez na mão: é o Mural de verdade, com um botão
    "Pegar" por cartão, e quem tem de dizer não é a célula. É essa liberdade que
    faz o [INV-ENC-N6] ser medido em vez de ser poupado.
    """
    na_prateleira = list(
        Encomenda.objects.filter(
            site_id=povoado.site_id, status=Encomenda.Status.NO_MURAL
        ).order_by("criada_em")
    )
    for projeto in na_prateleira:
        for _ in range(QUANTOS_OLHAM_CADA_CARTAO):
            candidato = povoado.sorteio.choice(povoado.perfis)
            jeito = povoado.temperamentos[candidato.id]
            if povoado.sorteio.random() >= jeito.p_pega_no_mural:
                continue
            if mural.pegar(
                projeto.pk, candidato.id, agora, site_id=povoado.site_id
            ).feito:
                placar.pegadas_no_mural += 1
                break


def _o_formulario(povoado, projeto, rodada, *, de_quem, jeito):
    """Os seis campos da §4.1, preenchidos por um lado ou pelo outro.

    O valor anda em direção ao meio a cada rodada, e é isso que faz a negociação
    ter para onde ir: o aluno começa acima da referência e cede, o cliente começa
    abaixo e sobe. Sem esse movimento, três rodadas seriam a mesma proposta
    escrita três vezes, e o acordo só sairia por sorte.
    """
    referencia = povoado.referencia[projeto.nivel]
    if de_quem == Proposta.DeQuem.ALUNO:
        valor = int(referencia * (1.25 - 0.10 * rodada))
        prazo = jeito.prazo_pedido
        entregaveis = list(povoado.entregaveis[:2])
        correcoes = 1
        justificativa = "modelagem, uv e duas texturas, com uma correcao inclusa"
    else:
        valor = int(referencia * (0.70 + 0.10 * rodada))
        prazo = max(1, jeito.prazo_pedido - 2)
        entregaveis = list(povoado.entregaveis)
        correcoes = 2
        justificativa = "o orcamento da escola cobre este valor, com o fonte junto"
    return {
        "valor_cents": max(1, valor),
        "prazo_dias": prazo,
        "entregaveis": entregaveis,
        "correcoes_inclusas": correcoes,
        "justificativa": justificativa,
    }


def _formulario_da_rodada(povoado, projeto, de_quem, jeito):
    """A rodada DESTE lado, contada do banco, e o formulário que ela produz."""
    rodada = Proposta.objects.filter(encomenda=projeto, de_quem=de_quem).count() + 1
    return _o_formulario(povoado, projeto, rodada, de_quem=de_quem, jeito=jeito)


def _os_alunos_negociam(povoado, agora, placar):
    """O aluno da vez propõe, responde à contraproposta, desiste ou some.

    Os quatro caminhos da emenda §4.2 num laço só, porque o formulário é o mesmo
    nos dois sentidos: propor é preencher, contrapropor é preencher de novo, e
    aceitar é dizer que o que está de pé serve.
    """
    projetos = list(
        Encomenda.objects.filter(
            site_id=povoado.site_id,
            status__in=(Encomenda.Status.RESERVADA, Encomenda.Status.EM_NEGOCIACAO),
        ).order_by("criada_em")
    )
    for projeto in projetos:
        if projeto.aluno_id is None:
            continue
        jeito = povoado.temperamentos[projeto.aluno_id]
        de_pe = negociacao.proposta_de_pe(projeto)
        dado = povoado.sorteio.random()

        if de_pe is None:
            # A PRIMEIRA PROPOSTA. Quem propõe primeiro é o aluno (§4.2), e é ela
            # que para o relógio da reserva. Quem não propõe fica em silêncio, e
            # é do silêncio que nasce a reserva vencida.
            if dado >= jeito.p_propoe:
                continue
            desfecho = apesar_do_estouro(
                placar,
                lambda: negociacao.propor(
                    projeto.pk,
                    agora,
                    site_id=povoado.site_id,
                    de_quem=Proposta.DeQuem.ALUNO,
                    **_formulario_da_rodada(
                        povoado, projeto, Proposta.DeQuem.ALUNO, jeito
                    ),
                ),
            )
            if desfecho.feito:
                placar.propostas_do_aluno += 1
            elif desfecho.razao == negociacao.RODADAS_ESGOTADAS:
                placar.rodadas_esgotadas += 1
            continue

        if de_pe.de_quem == Proposta.DeQuem.ALUNO:
            # A bola está com o cliente. Ninguém responde à própria proposta.
            continue

        if dado < jeito.p_aceita_a_contraproposta:
            if negociacao.aceitar_a_proposta(
                projeto.pk,
                agora,
                site_id=povoado.site_id,
                de_quem=Proposta.DeQuem.ALUNO,
                quem=str(projeto.aluno_id),
            ).feito:
                placar.acordos_pelo_aluno += 1
        elif dado < jeito.p_aceita_a_contraproposta + jeito.p_contrapropoe:
            desfecho = apesar_do_estouro(
                placar,
                lambda: negociacao.propor(
                    projeto.pk,
                    agora,
                    site_id=povoado.site_id,
                    de_quem=Proposta.DeQuem.ALUNO,
                    **_formulario_da_rodada(
                        povoado, projeto, Proposta.DeQuem.ALUNO, jeito
                    ),
                ),
            )
            if desfecho.feito:
                placar.contrapropostas_do_aluno += 1
            elif desfecho.razao == negociacao.RODADAS_ESGOTADAS:
                placar.rodadas_esgotadas += 1
        elif (
            dado
            < jeito.p_aceita_a_contraproposta + jeito.p_contrapropoe + jeito.p_desiste
        ):
            if negociacao.desistir(
                projeto.pk,
                agora,
                site_id=povoado.site_id,
                de_quem=Proposta.DeQuem.ALUNO,
            ).feito:
                placar.desistencias_do_aluno += 1


def _o_cliente_responde(povoado, agora, placar):
    """O outro lado da mesa: aceita, contrapropõe, desiste ou some (emenda §4.2).

    O que some é o mais importante dos quatro, e é o único que este arquivo não
    escreve: ele é o caminho que sobra quando nenhuma das três chances sai. É
    dele que nasce o [INV-ENC-N7].
    """
    projetos = list(
        Encomenda.objects.filter(
            site_id=povoado.site_id, status=Encomenda.Status.EM_NEGOCIACAO
        ).order_by("criada_em")
    )
    for projeto in projetos:
        de_pe = negociacao.proposta_de_pe(projeto)
        if de_pe is None or de_pe.de_quem != Proposta.DeQuem.ALUNO:
            continue
        cliente = povoado.clientes[projeto.pk]
        jeito = povoado.temperamentos[projeto.aluno_id]
        dado = povoado.sorteio.random()

        if dado < cliente.p_aceita:
            if negociacao.aceitar_a_proposta(
                projeto.pk,
                agora,
                site_id=povoado.site_id,
                de_quem=Proposta.DeQuem.CLIENTE,
                quem=O_PLANTAO,
            ).feito:
                placar.acordos_pelo_cliente += 1
        elif dado < cliente.p_aceita + cliente.p_contrapropoe:
            desfecho = negociacao.propor(
                projeto.pk,
                agora,
                site_id=povoado.site_id,
                de_quem=Proposta.DeQuem.CLIENTE,
                **_formulario_da_rodada(
                    povoado, projeto, Proposta.DeQuem.CLIENTE, jeito
                ),
            )
            if desfecho.feito:
                placar.contrapropostas_do_cliente += 1
            elif desfecho.razao == negociacao.RODADAS_ESGOTADAS:
                placar.rodadas_esgotadas += 1
        elif dado < cliente.p_aceita + cliente.p_contrapropoe + cliente.p_desiste:
            if negociacao.desistir(
                projeto.pk,
                agora,
                site_id=povoado.site_id,
                de_quem=Proposta.DeQuem.CLIENTE,
            ).feito:
                placar.desistencias_do_cliente += 1


def _o_caixa_registra_o_pagamento(povoado, agora, placar):
    """O plantão declara "pago pela escola", com autor e data (emenda §5).

    Nenhuma linha de cobrança, nenhum Mercado Pago e nenhum webhook: a trava de
    22/08/2026 continua de pé, e o que o [INV-ENC-N4] mede é o registro humano.

    **Roda ANTES da negociação no laço do passo, e isso não é arrumação.** Um
    acordo fechado no passo `k` só é pago no passo `k+1`, e essa distância é o
    que faz o [INV-ENC-N8] medir alguma coisa: com o acordo e o pagamento no
    mesmo instante, "o prazo começa no pagamento" e "o prazo começa no acordo"
    dariam a mesma data, e o guarda ficaria verde com a regra apagada.
    """
    acordados = list(
        Encomenda.objects.filter(
            site_id=povoado.site_id, status=Encomenda.Status.ACORDADA
        ).order_by("criada_em")
    )
    for projeto in acordados:
        if negociacao.confirmar_pagamento_pela_escola(
            projeto.pk, agora, site_id=povoado.site_id, quem=O_PLANTAO
        ).feito:
            placar.pagamentos_registrados += 1
            if projeto.acordado_em is not None and projeto.acordado_em != agora:
                placar.prazos_que_comecaram_depois_do_acordo += 1


def _a_producao_comeca(povoado, agora, placar, entrega_prevista):
    """[INV-ENC-N4] e [INV-ENC-N8] pelo gesto de verdade, e o cronômetro do aluno.

    Roda antes do caixa pela mesma razão que o caixa roda antes da negociação: o
    projeto pago no passo `k` começa a produzir no `k+1`, e a distância entre o
    acordo e o começo é o que o [INV-ENC-N8] existe para proteger.
    """
    aguardando = list(
        Encomenda.objects.filter(
            site_id=povoado.site_id, status=Encomenda.Status.AGUARDANDO_PAGAMENTO
        ).order_by("criada_em")
    )
    for projeto in aguardando:
        if not negociacao.comecar_a_producao(
            projeto.pk, agora, site_id=povoado.site_id
        ).feito:
            continue
        placar.producoes_iniciadas += 1
        jeito = povoado.temperamentos[projeto.aluno_id]
        entrega_prevista[projeto.pk] = (
            agora + timedelta(hours=jeito.horas_de_trabalho),
            projeto.aluno_id,
        )


def _alguem_tenta_a_chamada_aberta(povoado, agora, placar):
    """Um aluno sorteado tenta levar cada chamada aberta (Anexo B, cenário 4).

    Um por projeto por passo, pela mesma economia do Mural. O gesto recusa
    sozinho quem não pode levar, e aqui a memória é vazia de propósito: a chamada
    aberta é a exceção literal do [INV-ENC-J6].
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
        if apesar_do_estouro(
            placar,
            lambda: gestos.aceitar_a_chamada_aberta(
                encomenda.pk, candidato.id, agora, site_id=povoado.site_id
            ),
        ).feito:
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
    """A Fase 3 e a Fase 5 encenadas: o projeto chega ao fim e o aluno fica livre.

    Nada disto existe em código ainda. O simulador encena porque as duas pistas
    só mostram a promessa do produto quando alguém ENTREGA: é a entrega aprovada
    que muda o primeiro termo da chave da lei §6.2, é ela que faz o novato de
    ontem virar o veterano de amanhã, e é ela que faz o Mural ganhar gente nova
    ao longo dos oito dias. As transições passam pela máquina de estado de
    verdade, então nenhum caminho inventado aqui seria aceito pelo banco.
    """
    for encomenda_id, (quando, aluno_id) in sorted(
        entrega_prevista.items(), key=lambda item: item[1][0]
    ):
        if agora < quando:
            continue
        encomenda = Encomenda.objects.get(pk=encomenda_id)
        for status in DA_PRODUCAO_ATE_CONCLUIDA:
            encomenda.mudar_status(status, motivo="o simulador encena a Fase 3 e a 5")
        perfil = PerfilProfissional.objects.get(pk=aluno_id)
        perfil.entregas_aprovadas += 1
        perfil.save(update_fields=["entregas_aprovadas", "atualizado_em"])
        # Só quem foi TRANCADO é solto. Quem ganhou o projeto no Mural nunca
        # ficou "trabalhando" (é o buraco que o [INV-ENC-N6] conta acima), e
        # mandá-lo de `disponivel` para `disponivel` seria uma transição que a
        # máquina de estado recusa.
        if perfil.disponibilidade == PerfilProfissional.Disponibilidade.TRABALHANDO:
            perfil.mudar_disponibilidade(PerfilProfissional.Disponibilidade.DISPONIVEL)
        placar.entregas_aprovadas += 1
        del entrega_prevista[encomenda_id]


# ---------------------------------------------------------------------------
# AS DUAS PROPRIEDADES QUE SÓ O SIMULADOR ALCANÇA
# ---------------------------------------------------------------------------


def conferir_que_nada_fica_preso(retrato, agora, memoria, placar, regua):
    """PROPRIEDADE 2: nenhum projeto dá voltas sem chegar a um aluno nem ao plantão.

    "Preso" não é "está esperando": é **nada aconteceu com ele**. O cronômetro
    zera a cada mudança de situação (status, dono, proposta nova, reserva nova),
    e por isso uma negociação de três rodadas ao longo de cinco dias não conta
    como preso, e um projeto largado numa prateleira por três dias conta.

    Cada projeto que estoura o teto é classificado, e a classificação é o que faz
    esta propriedade valer alguma coisa: os buracos já conhecidos são contados
    com nome, e o guarda que reprova é o dos presos por motivo NOVO, que vale
    zero.
    """
    for projeto in retrato.projetos:
        if projeto.status not in ESPERAS:
            continue
        parado_ha = agora - memoria.parado_desde[projeto.pk]
        if projeto.status == Encomenda.Status.ABERTA:
            assert parado_ha < regua.prazo_da_chamada_aberta, (
                f"[INV-ENC-J11] quebrado em {agora.isoformat()}: a chamada "
                f"aberta {projeto.pk} esta sem aceite ha {parado_ha}, e o "
                f"prazo historico e {regua.prazo_da_chamada_aberta}. O tique "
                "tinha de manda-la ao plantao."
            )
            continue
        if parado_ha <= TETO_PARADO:
            continue
        motivo = por_que_esta_preso(
            projeto,
            tem_proposta_de_pe=bool(retrato.de_pe_por_projeto.get(projeto.pk)),
            tem_elegivel=bool(
                quem_ve_no_mural(
                    projeto, retrato.perfis, memoria, retrato.com_oferta, regua, agora
                )
            ),
        )
        # Conta uma vez por projeto e por motivo: o cronômetro não zera enquanto
        # o projeto está preso, e sem esta guarda ele somaria uma linha no placar
        # a cada hora simulada.
        chave = (projeto.pk, motivo)
        if chave in memoria.presos_ja_contados:
            continue
        memoria.presos_ja_contados.add(chave)
        placar.presos[motivo] = placar.presos.get(motivo, 0) + 1
        assert motivo, (
            f"PROPRIEDADE 2 quebrada em {agora.isoformat()}: o projeto "
            f"{projeto.pk} esta em {projeto.status!r} desde "
            f"{memoria.parado_desde[projeto.pk].isoformat()} e nada aconteceu "
            f"com ele em {parado_ha}. Ele nao chegou a um aluno nem ao plantao, "
            "e o motivo NAO e nenhum dos buracos declarados "
            f"({', '.join(BURACOS_DECLARADOS)})."
        )


def os_de_zero_entregas(povoado):
    """Os alunos que começaram de mãos vazias, na ordem da lei §6.2.

    Todos têm zero entregas, então a chave da lei se reduz ao segundo termo, a
    data de entrada na fila, com o desempate do identificador. É a fila de quem
    espera o primeiro dólar, e é sobre ela que a propriedade 1 fala.
    """
    return sorted(
        (
            perfil
            for perfil in povoado.perfis
            if povoado.entregas_no_comeco[perfil.id] == 0 and perfil.titulo_banca
        ),
        key=lambda perfil: (povoado.lugar_na_fila[perfil.id], perfil.id),
    )


def conferir_a_promessa_do_primeiro_dolar(povoado, zerados, memoria, placar, texto):
    """PROPRIEDADE 1: o Mural não rouba da fila, e a ordem do zero é respeitada.

    A promessa do produto é que **a fila garante o primeiro trabalho de cada
    aluno**, e o Mural é para onde ele vai depois (emenda §1). Um simulador que
    só contasse quantos foram servidos não provaria isso: com trinta projetos e
    cem alunos, o que acaba é a oferta, não a justiça.

    O que se prova aqui é mais forte, e é o que importa: **entre os alunos de zero
    entregas que ficaram disponíveis o tempo todo, os servidos são um PREFIXO da
    ordem da lei §6.2.** Ninguém de trás recebeu enquanto alguém da frente, de
    mãos vazias e disponível, não recebeu nada. É o formato em que o Mural
    roubaria se roubasse: bastaria uma oferta da fila indo para quem já entregou,
    ou um projeto Iniciante escorregando para a prateleira, e alguém da frente
    ficaria sem a primeira vez para sempre.

    Quem pausou fica de fora, e a exclusão é a única honesta: um aluno que
    desligou o interruptor não recebe oferta por regra ([INV-ENC-J7]), e cobrar a
    fila por isso seria cobrá-la de cumprir uma promessa que o próprio aluno
    dispensou.
    """
    posicao = {perfil.id: numero for numero, perfil in enumerate(zerados)}
    servidos = [p for p in zerados if p.id in placar.alunos_que_receberam]
    famintos = [
        p
        for p in zerados
        if p.id not in placar.alunos_que_receberam
        and p.id in memoria.nunca_ficou_indisponivel
    ]

    assert servidos, (
        "PROPRIEDADE 1 quebrada: nenhum aluno de zero entregas recebeu oferta em "
        f"{DIAS_SIMULADOS} dias, e a fila existe para eles.\n{texto}"
    )
    if not famintos:
        return

    ultimo_servido = max(posicao[p.id] for p in servidos)
    primeiro_faminto = min(posicao[p.id] for p in famintos)
    assert primeiro_faminto > ultimo_servido, (
        f"PROPRIEDADE 1 quebrada: o aluno na posicao {primeiro_faminto} da ordem "
        "da lei §6.2 tem zero entregas, ficou disponivel a simulacao inteira e "
        "nao recebeu uma unica oferta, enquanto o da posicao "
        f"{ultimo_servido}, que vem DEPOIS dele, recebeu. A fila pulou a "
        f"frente.\n{texto}"
    )


def _contar_as_propostas_que_venceram(retrato, batida, placar):
    """Quem calou em cada proposta vencida, para o placar (emenda §4.2).

    Contado da BATIDA e não do estado: uma proposta vencida vira `expirou` e o
    projeto sai de `em_negociacao` na mesma passada, então perguntar depois
    "quantas venceram?" daria zero.
    """
    por_pk = {p.pk: p for p in retrato.propostas}
    for proposta_id in batida.propostas_expiradas:
        proposta = por_pk.get(proposta_id)
        if proposta is None:
            continue
        if proposta.de_quem == Proposta.DeQuem.ALUNO:
            placar.cliente_calado += 1
        else:
            placar.aluno_calado += 1


def _conferir_que_o_cliente_calado_foi_ao_plantao(retrato, batida, agora):
    """[INV-ENC-N7]: proposta vencida por silêncio do CLIENTE vai ao plantão.

    E nunca para o próximo aluno. Mandá-la ao próximo faria cada aluno da fila
    gastar a própria vez num cliente fantasma, um depois do outro, e nenhum deles
    saberia por quê (emenda §4.2). O espelho é medido junto: quando quem calou
    foi o ALUNO, o projeto volta à pista e o plantão não é chamado.
    """
    por_pk = {p.pk: p for p in retrato.propostas}
    for proposta_id in batida.propostas_expiradas:
        proposta = por_pk.get(proposta_id)
        if proposta is None:
            continue
        projeto = retrato.por_pk[proposta.encomenda_id]
        if proposta.de_quem == Proposta.DeQuem.ALUNO:
            assert projeto.status == Encomenda.Status.PARA_RECLASSIFICAR, (
                f"[INV-ENC-N7] quebrado em {agora.isoformat()}: a proposta do "
                f"aluno no projeto {projeto.pk} venceu sem resposta do cliente, "
                f"e o projeto foi para {projeto.status!r} em vez de ir ao "
                "plantao. Um cliente que sumiu nao vira fila de espera para "
                "decepcionar o proximo aluno."
            )
            assert projeto.aluno_id is None, (
                f"[INV-ENC-N7] quebrado em {agora.isoformat()}: o projeto "
                f"{projeto.pk} foi ao plantao ainda apontando para o aluno "
                f"{projeto.aluno_id}."
            )
        else:
            assert projeto.status != Encomenda.Status.PARA_RECLASSIFICAR, (
                f"[INV-ENC-N7] quebrado em {agora.isoformat()}: quem calou no "
                f"projeto {projeto.pk} foi o ALUNO, e o projeto tinha de ter "
                "voltado a pista dele, para o proximo, em vez de ir ao plantao."
            )


# ---------------------------------------------------------------------------
# A SIMULAÇÃO
# ---------------------------------------------------------------------------


def test_as_duas_pistas_rodam_e_nenhum_dos_vinte_e_quatro_invariantes_cai(
    povoado, capsys
):
    """O portão do degrau 2.13: dias de fila e de Mural cheios, e os 24 de pé.

    O laço é o do plano §7.4 mais o da emenda §4.2: a cada hora simulada o tique
    expira ofertas, reservas e propostas, abre o que esperou demais, manda ao
    plantão o que encalhou e oferece o que sobrou; depois a produção anda, o
    caixa registra, os alunos respondem, pegam, propõem e cedem, o cliente
    responde, alguém tenta a chamada aberta, o interruptor gira e quem terminou
    volta com uma entrega a mais. Entre uma coisa e outra, os vinte e quatro.
    """
    site = povoado.site_id
    regua = Regua.do_banco(povoado.t_zero, site_id=site)
    janela = relogio.Janela.do_banco(povoado.t_zero, site_id=site)
    memoria = Memoria()
    placar = Placar()
    entrega_prevista: dict = {}
    pausados_por_silencio: set = set()

    # Os marcos nascem da CHEGADA anotada pelo simulador, e não do primeiro
    # retrato: os projetos das ondas 2 e 3 já existem no banco no minuto zero, e
    # datá-los de agora faria o guarda cobrar deles uma espera que ainda não
    # começou.
    for projeto in povoado.projetos:
        memoria.entrada_na_fila[projeto.pk] = povoado.chegada[projeto.pk]
        memoria.entrada_no_mural[projeto.pk] = povoado.chegada[projeto.pk]
        memoria.parado_desde[projeto.pk] = povoado.chegada[projeto.pk]
        memoria.status_anterior[projeto.pk] = projeto.status
        if projeto.status == Encomenda.Status.NO_MURAL:
            placar.nasceram_no_mural += 1
        # [INV-ENC-M2] no NASCIMENTO: a pista é a que o nível manda, e ninguém a
        # escolhe. Medido aqui, e não no laço, porque é aqui que ela é dada.
        assert projeto.status == PISTA_QUE_A_EMENDA_MANDA[projeto.nivel], (
            f"[INV-ENC-M2] quebrado no nascimento: o projeto {projeto.pk}, de "
            f"nivel {projeto.nivel!r}, nasceu em {projeto.status!r} e a emenda "
            f"§3.1 manda {PISTA_QUE_A_EMENDA_MANDA[projeto.nivel]!r}."
        )
    memoria.nunca_ficou_indisponivel = {perfil.id for perfil in povoado.perfis}

    agora = povoado.t_zero
    fim = povoado.t_zero + timedelta(days=DIAS_SIMULADOS)
    passo = 0
    while agora <= fim:
        povoado.relogio.agora = agora
        batida = tique.rodar(agora, site_id=site)
        novas = list(Oferta.objects.filter(pk__in=batida.rodada.ofertas_criadas))
        for oferta in novas:
            memoria.nascimento[oferta.pk] = agora
            placar.alunos_que_receberam.add(oferta.aluno_id)
        placar.ofertas += len(novas)
        placar.silencios += len(batida.ofertas_expiradas)
        placar.viraram_chamada_aberta += len(batida.encomendas_abertas)
        placar.reservas_que_venceram += len(batida.reservas_expiradas)
        placar.ao_plantao_sem_elegivel += len(batida.projetos_ao_plantao)
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

        retrato = Instantaneo.do_banco(site)
        _contar_as_propostas_que_venceram(retrato, batida, placar)
        memoria.anotar(retrato, agora)
        conferir_os_dez(
            povoado,
            retrato,
            agora,
            memoria,
            regua,
            janela,
            novas=novas,
            depois_do_tique=True,
        )
        conferir_o_mural(
            povoado, retrato, agora, memoria, regua, passo=passo, depois_do_tique=True
        )
        conferir_a_negociacao(povoado, retrato, agora, memoria, regua, placar)
        _conferir_que_o_cliente_calado_foi_ao_plantao(retrato, batida, agora)
        conferir_que_nada_fica_preso(retrato, agora, memoria, placar, regua)

        # [INV-ENC-J10] Reexecutar sem mudança de estado não cria nada. Conferido
        # em TODO passo, e não uma vez no fim: a idempotência que só vale num
        # estado é a que quebra no dia do deploy com dois workers de pé. As cinco
        # varreduras do tique entram na conta, e não só a do motor: uma reserva
        # ou uma proposta expirada duas vezes seria um projeto devolvido duas
        # vezes à prateleira.
        de_novo = tique.rodar(agora, site_id=site)
        assert (
            de_novo.rodada.quantas_ofertas == 0
            and de_novo.ofertas_expiradas == ()
            and de_novo.reservas_expiradas == ()
            and de_novo.propostas_expiradas == ()
            and de_novo.encomendas_abertas == ()
            and de_novo.projetos_ao_plantao == ()
        ), (
            f"[INV-ENC-J10] quebrado em {agora.isoformat()}: a segunda passada "
            f"no mesmo instante criou {de_novo.rodada.quantas_ofertas} oferta(s), "
            f"expirou {len(de_novo.ofertas_expiradas)} oferta(s), "
            f"{len(de_novo.reservas_expiradas)} reserva(s) e "
            f"{len(de_novo.propostas_expiradas)} proposta(s), abriu "
            f"{len(de_novo.encomendas_abertas)} e mandou "
            f"{len(de_novo.projetos_ao_plantao)} ao plantao."
        )

        _a_producao_comeca(povoado, agora, placar, entrega_prevista)
        _o_caixa_registra_o_pagamento(povoado, agora, placar)
        _os_alunos_respondem_as_ofertas(povoado, agora, placar)
        _os_alunos_pegam_no_mural(povoado, agora, placar)
        _os_alunos_negociam(povoado, agora, placar)
        _o_cliente_responde(povoado, agora, placar)
        _alguem_tenta_a_chamada_aberta(povoado, agora, placar)
        _o_interruptor(povoado, agora, placar)
        _o_trabalho_terminou_e_o_cliente_aprovou(
            povoado, agora, placar, entrega_prevista
        )

        retrato = Instantaneo.do_banco(site)
        memoria.anotar(retrato, agora)
        conferir_os_dez(
            povoado,
            retrato,
            agora,
            memoria,
            regua,
            janela,
            novas=[],
            depois_do_tique=False,
        )
        conferir_o_mural(
            povoado, retrato, agora, memoria, regua, passo=passo, depois_do_tique=False
        )
        conferir_a_negociacao(povoado, retrato, agora, memoria, regua, placar)
        conferir_que_nada_fica_preso(retrato, agora, memoria, placar, regua)
        agora += PASSO
        passo += 1

    zerados = os_de_zero_entregas(povoado)
    placar.zerados_servidos = {
        p.id for p in zerados if p.id in placar.alunos_que_receberam
    }
    contagem = sorted(
        (estado, quantos)
        for estado, quantos in (
            (estado, Encomenda.objects.filter(site_id=site, status=estado).count())
            for estado in Encomenda.Status.values
        )
        if quantos
    )
    texto = placar.em_texto(povoado, quantos_zerados=len(zerados), contagem=contagem)
    with capsys.disabled():
        print(texto)

    conferir_a_promessa_do_primeiro_dolar(povoado, zerados, memoria, placar, texto)

    # O SIMULADOR PRECISA TER ACONTECIDO. Sem estas linhas, um mundo em que
    # ninguém recebe, ninguém pega, ninguém propõe e ninguém some passaria nos
    # vinte e quatro invariantes sem provar nada — o verde vazio que a
    # `armadilhas/132` descreve.
    # Os pisos são a METADE do que esta semente produz, e não o número exato: o
    # que eles guardam é "o mecanismo aconteceu", não "aconteceu tantas vezes".
    # Um piso igual ao valor medido viraria vermelho a cada ajuste legítimo do
    # motor, e o vermelho que chega sempre é o vermelho que ninguém lê.
    assert placar.ofertas > 30, texto
    assert placar.aceites_na_fila > 3, texto
    assert placar.total_de_passes > 5, texto
    assert placar.silencios > 15, texto
    assert placar.pausas_por_silencio > 0, texto
    assert placar.reclassificadas > 0, texto
    assert placar.entregas_aprovadas > 3, texto
    assert len(placar.alunos_que_receberam) > 15, texto
    # O MURAL ACONTECEU: a prateleira nasceu cheia, gente pegou, relógio venceu e
    # alguma coisa encalhou a ponto de o professor precisar olhar.
    assert placar.nasceram_no_mural == 20, texto
    assert placar.pegadas_no_mural > 10, texto
    assert placar.reservas_que_venceram > 3, texto
    assert placar.ao_plantao_sem_elegivel > 0, texto
    # A NEGOCIAÇÃO ACONTECEU, e os dois lados falaram. Sem contraproposta não há
    # rodada, e sem rodada o [INV-ENC-N2] mede uma contagem que nunca cresce.
    assert placar.propostas_do_aluno > 5, texto
    assert placar.contrapropostas_do_cliente > 2, texto
    assert placar.contrapropostas_do_aluno > 0, texto
    assert placar.acordos > 2, texto
    assert placar.cliente_calado > 0, texto
    assert placar.aluno_calado > 0, texto
    assert placar.rodadas_esgotadas > 0, texto
    assert placar.pagamentos_registrados > 2, texto
    assert placar.producoes_iniciadas > 2, texto
    # O [INV-ENC-N8] só mede alguma coisa quando o acordo e o pagamento caem em
    # instantes DIFERENTES. Sem esta linha, um mundo que pagasse no mesmo minuto
    # do acordo faria o guarda ficar verde com a regra apagada.
    assert placar.prazos_que_comecaram_depois_do_acordo > 2, texto
    # A conta que fecha o [INV-ENC-J6] pelo total: cada oferta é um par
    # (encomenda, aluno) inédito, então o número de pares tem de ser o número de
    # ofertas. Uma repetição em qualquer minuto dos oito dias derruba a igualdade.
    assert len(memoria.pares) == placar.ofertas, texto
    # PROPRIEDADE 2, a metade que reprova: nenhum projeto ficou preso por um
    # motivo que não esteja declarado.
    assert placar.presos.get("", 0) == 0, texto
