"""Os relógios da Fila do Primeiro Dólar: quanto tempo o aluno tem, e desde quando.

Lei: `docs/decisoes/DECISAO-fila-do-primeiro-dolar.md` (§5 os invariantes de
justiça, §6 os parâmetros). Produto: `PLANO-MESTRE-FILA-DO-PRIMEIRO-DOLAR.md`
§6.3 (a oferta), §6.4 (a chamada aberta), §7.4 (o algoritmo) e §8.6 (os
relógios).

Este é o degrau 2.4 da escada, e ele substitui a conta provisória que o degrau
2.3 deixou plugada de propósito (`motor.expiracao_provisoria`, que morreu neste
PR). A partir daqui existem TRÊS relógios nesta célula, e o mais importante a
saber sobre eles é que **eles medem coisas diferentes de propósito**:

| Relógio | Conta | Parâmetro | Unidade da lei §6 |
|---|---|---|---|
| o da OFERTA | horas ÚTEIS | `relogio_da_oferta` | "horas úteis" |
| o da FILA | horas de parede | `horas_para_virar_aberta` | "horas na fila" |
| a JANELA | o que faz a primeira coluna ser diferente da segunda | `janela_inicio`, `janela_fim` | "hora local" |

A tabela acima não é estilo: é a lei §6 lida palavra por palavra. Uma oferta
feita às 21h vence às 10h do dia seguinte (uma hora hoje, duas a partir das 8h),
porque seria injusto consumir o prazo de decisão de alguém enquanto ela dorme. A
encomenda que entrou na fila às 21h vira chamada aberta às 21h do dia seguinte,
porque quem espera é o CLIENTE, e o cliente não dorme junto com a janela.

"HORAS ÚTEIS" AQUI SÃO HORAS DA JANELA, E FIM DE SEMANA CONTA
--------------------------------------------------------------
Esta é a armadilha de leitura deste arquivo, e ela tem guarda próprio
(`tests/test_relogio_horas_uteis.py::test_sabado_e_domingo_contam_como_qualquer_dia`).
Em português comum, "hora útil" quer dizer "hora de dia útil", e dia útil exclui
sábado e domingo. **Aqui não.** A lei §6 tem duas chaves de janela e só duas:
`janela_inicio` e `janela_fim`. Não existe `dias_uteis`, não existe calendário
de feriado, e o vocabulário de chaves é FECHADO no banco
(`chave_de_parametro_no_vocabulario_fechado`) — inventar a regra de dia da
semana exigiria um número em código, que é o critério de morte 5 da lei §9.

E a regra de produto concorda com a régua: quem está na fila é um aluno da
escola, e a escola não tem expediente. Sábado à tarde é justamente quando ele
está no computador. Um relógio que congelasse de sexta às 22h até segunda às 8h
daria 62 horas de silêncio ao cliente para "proteger" alguém que estava
acordado o tempo todo.

O QUE ESTE ARQUIVO NÃO DECIDE
------------------------------
Nada. As três funções puras recebem a janela e devolvem um instante; quem lê o
banco são os três colaboradores do fim do arquivo, e eles são FAIL-CLOSED
(parâmetro ausente levanta, nunca assume um padrão). É o mesmo desenho do
`motor.py`: o miolo é função de (estado, `agora`), e por isso o simulador de cem
alunos (degrau 2.6) vai poder rodar cem dias de fila sem subir PostgreSQL nem
mexer no relógio da máquina.

O QUE AINDA NÃO É DESTE DEGRAU
-------------------------------
- **A pausa por três silêncios** e o contador `silencios_consecutivos` são o
  degrau 2.5 inteiro, em um gesto só (ver `tique.py`).
- **O que a chamada aberta FAZ** (avisar os elegíveis, o primeiro que aceitar
  leva) é o degrau 2.5. Aqui nasce só a virada de estado no prazo, que é o
  [INV-ENC-J9].
- **Os prazos de produção, a extensão, a aprovação tácita e o SLA do revisor**
  são as Fases 3 e 5. Eles vão usar estas mesmas funções puras, e é por isso que
  `somar_horas_uteis` recebe uma `duracao` em vez de ler `relogio_da_oferta` por
  dentro.

HORÁRIO DE VERÃO
----------------
`America/Sao_Paulo` não tem horário de verão desde 2019, e a aritmética abaixo é
de relógio de parede: somar "três horas úteis" anda três horas no relógio que a
pessoa lê. Se o horário de verão voltar, a hora repetida e a hora inexistente da
virada precisam de decisão — e o lugar de decidir é aqui, não num `try` no meio
do motor.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from django.conf import settings

from .models import ParametroAusente, Parametro


# ---------------------------------------------------------------------------
# A JANELA — o dado congelado que as funções puras recebem
# ---------------------------------------------------------------------------


class JanelaImpossivel(ValueError):
    """A janela lida do banco não deixa o relógio andar nunca.

    Acontece se alguém gravar `janela_inicio >= janela_fim` (por exemplo 22:00 e
    08:00, tentando dizer "a noite inteira"). Uma janela assim não tem hora
    nenhuma dentro dela, e a conta de horas úteis não terminaria — por isso o
    erro é aqui, na leitura, e não um laço infinito no meio de uma passada do
    motor.

    A virada de meia-noite (uma janela que atravessa o dia) NÃO é suportada de
    propósito: a lei §6 diz 8h–22h, e um relógio que atravessa a meia-noite
    muda a conta de "dia" de toda a célula. Se o mantenedor um dia quiser isso,
    é decisão, não configuração.
    """


@dataclass(frozen=True)
class Janela:
    """As horas do dia em que o relógio da oferta corre, no fuso da célula.

    `fuso` vem de `settings.TIME_ZONE` e não é parâmetro da lei §6 — a lei diz
    `America/Sao_Paulo` uma vez, no cabeçalho da tabela, e quem faz isso valer é
    `config/settings.py` com o guarda de `tests/test_fuso_horario.py`. Duas
    fontes para o mesmo fuso divergiriam no primeiro dia em que alguém mexesse
    numa delas.
    """

    inicio: time
    fim: time
    fuso: ZoneInfo

    CHAVES = ("janela_inicio", "janela_fim")

    def __post_init__(self) -> None:
        if self.inicio >= self.fim:
            raise JanelaImpossivel(
                f"janela {self.inicio}–{self.fim}: o fim tem de vir depois do "
                "início, no mesmo dia. Uma janela vazia (ou que atravessa a "
                "meia-noite) faria o relógio da oferta nunca andar."
            )

    @classmethod
    def do_banco(cls, agora: datetime, *, site_id: str) -> "Janela":
        """Lê `janela_inicio` e `janela_fim` do banco, ou levanta dizendo quais faltam.

        Mesma forma de `motor.Regras.do_banco`: valor vigente EM `agora`, nunca
        o mais recente (lei §3.8), e nenhum padrão embutido. Um padrão aqui
        seria pior do que a constante mágica comum: ele faria a célula oferecer
        com uma janela que ninguém escolheu, e o erro só apareceria como "o
        aluno perdeu a oferta dormindo".
        """
        valores: dict[str, str] = {}
        faltando: list[str] = []
        for chave in cls.CHAVES:
            linha = Parametro.vigente_em(chave, agora, site_id=site_id)
            if linha is None:
                faltando.append(chave)
            else:
                valores[chave] = linha.valor
        if faltando:
            raise ParametroAusente(
                f"site {site_id!r}: sem valor vigente em {agora.isoformat()} para "
                f"{', '.join(sorted(faltando))}. Sem a janela não há relógio de "
                "oferta ([INV-ENC-J8]), e o motor não oferece nada. Rode "
                f"`python manage.py semear_parametros --site {site_id}`."
            )
        return cls(
            inicio=time.fromisoformat(valores["janela_inicio"]),
            fim=time.fromisoformat(valores["janela_fim"]),
            fuso=ZoneInfo(settings.TIME_ZONE),
        )

    def abertura_de(self, dia: date) -> datetime:
        """O instante em que a janela abre neste dia local."""
        return datetime.combine(dia, self.inicio, tzinfo=self.fuso)

    def fechamento_de(self, dia: date) -> datetime:
        """O instante em que a janela fecha neste dia local."""
        return datetime.combine(dia, self.fim, tzinfo=self.fuso)


def _dia_seguinte(dia: date) -> date:
    """O dia civil seguinte, sem `timedelta`.

    `date.fromordinal(dia.toordinal() + 1)` em vez de `dia + timedelta(days=1)`
    não é preciosismo: o guarda de constante mágica desta célula
    (`tests/test_parametros_sao_dado.py`) reprova qualquer `timedelta` com
    número solto, e ele está certo em fazer isso — é assim que
    `timedelta(hours=3)` no lugar do parâmetro nunca entra. A conta de ordinal
    diz a mesma coisa sem número de duração nenhum.
    """
    return date.fromordinal(dia.toordinal() + 1)


# ---------------------------------------------------------------------------
# AS TRÊS FUNÇÕES PURAS — sem banco, sem relógio de máquina, sem efeito
# ---------------------------------------------------------------------------


def esta_na_janela(momento: datetime, janela: Janela) -> bool:
    """O relógio da oferta está correndo neste instante?

    A borda é fechada na abertura e ABERTA no fechamento: às 8h em ponto o
    relógio já anda; às 22h em ponto ele já parou. É a mesma convenção do
    `expira_em <= agora` do tique — sem ela, o instante exato do fechamento
    pertenceria aos dois lados, e um teste de borda passaria ou falharia
    conforme a ordem em que as comparações fossem escritas.
    """
    local = momento.astimezone(janela.fuso)
    return (
        janela.abertura_de(local.date()) <= local < janela.fechamento_de(local.date())
    )


def somar_horas_uteis(inicio: datetime, duracao: timedelta, janela: Janela) -> datetime:
    """`inicio` mais `duracao` de tempo DENTRO da janela. O [INV-ENC-J8] em uma função.

    É a função que o plano §7.4 chama de *"o cálculo de horas úteis é uma função
    única, pura e testada"*. Ela não sabe o que é uma oferta, não lê parâmetro e
    não olha o relógio da máquina: recebe um instante, uma duração e a janela, e
    devolve o instante em que a duração se esgota.

    Três comportamentos, e os três têm guarda:

    - **Começou fora da janela?** O relógio só começa a andar na próxima
      abertura. Uma oferta feita às 2h da manhã dá as três horas cheias a partir
      das 8h, e não um prazo que venceu enquanto a pessoa dormia.
    - **A duração não cabe no resto do dia?** O que sobra continua na abertura do
      dia seguinte, quantos dias forem precisos.
    - **Cabe exatamente?** O prazo vence no fechamento, e o instante do
      fechamento já conta como vencido (`expira_em <= agora` no tique).

    O resultado sai em UTC, que é como o banco guarda (`USE_TZ`). Converter aqui,
    e não em quem chama, é o que impede um `datetime` no fuso local vazar para
    uma coluna e virar comparação torta seis meses depois.
    """
    local = inicio.astimezone(janela.fuso)
    restante = duracao
    while True:
        abertura = janela.abertura_de(local.date())
        fechamento = janela.fechamento_de(local.date())
        if local < abertura:
            local = abertura
        if local >= fechamento:
            local = janela.abertura_de(_dia_seguinte(local.date()))
            continue
        disponivel = fechamento - local
        if restante <= disponivel:
            return (local + restante).astimezone(timezone.utc)
        restante -= disponivel
        # Vai para o fechamento e deixa a volta seguinte pular para o dia
        # seguinte. Saltar direto para a abertura de amanhã daria o mesmo
        # resultado com uma linha a menos e uma regra a mais escondida.
        local = fechamento


def horas_uteis_entre(inicio: datetime, fim: datetime, janela: Janela) -> timedelta:
    """Quanto tempo de JANELA existe entre dois instantes. A inversa da de cima.

    Ela existe por um motivo que vale escrever: é com ela que o guarda do
    [INV-ENC-J8] mede a promessa inteira numa asserção só — *"entre
    `oferecida_em` e `expira_em` há exatamente `relogio_da_oferta` horas de
    janela, não importa a que horas a oferta foi feita"*. Sem ela, o guarda
    teria de recalcular a expiração com a mesma função que ele está medindo, e
    um teste que reimplementa o código que mede não mede nada.

    E ela é a peça que a espera estimada do aluno (Fase 4) e o painel de plantão
    (Fase 7) vão pedir: "faltam quantas horas úteis?".
    """
    if fim <= inicio:
        return timedelta()
    local = inicio.astimezone(janela.fuso)
    alvo = fim.astimezone(janela.fuso)
    total = timedelta()
    while local < alvo:
        abertura = janela.abertura_de(local.date())
        fechamento = janela.fechamento_de(local.date())
        if local < abertura:
            local = abertura
        elif local >= fechamento:
            local = janela.abertura_de(_dia_seguinte(local.date()))
        else:
            ate = min(fechamento, alvo)
            total += ate - local
            local = ate
    return total


# ---------------------------------------------------------------------------
# OS COLABORADORES — leem o banco, montam a janela, chamam o miolo
# ---------------------------------------------------------------------------


def _horas_do_parametro(chave: str, agora: datetime, *, site_id: str) -> timedelta:
    """A duração de uma chave da lei §6 que se mede em horas, ou a recusa.

    Uma função só para as três leituras de hora desta célula, e não uma cópia por
    chave: o `relogio_da_oferta` e o `horas_para_virar_aberta` fazem exatamente a
    mesma coisa com o banco, e duas cópias divergiriam no dia em que uma delas
    ganhasse um cuidado a mais.

    O que ela acrescenta a `Parametro.inteiro_vigente` é só a UNIDADE: ler o
    número e recusar quando ele não existe é da tabela, e desde o degrau 2.5 há
    um terceiro leitor de inteiros nesta célula (`gestos.py`, que conta silêncios
    e passes). Transformar horas em `timedelta` continua sendo do relógio.
    """
    return timedelta(hours=Parametro.inteiro_vigente(chave, agora, site_id=site_id))


def _vence_em_horas_uteis(chave: str, agora: datetime, *, site_id: str) -> datetime:
    """Quando vence, em horas úteis, o prazo que a `chave` mede, contado de `agora`.

    Duas leituras do banco, as duas fail-closed e as duas no valor vigente em
    `agora`: quantas horas úteis (a `chave`) e quais são as horas úteis
    (`janela_inicio`, `janela_fim`).

    Uma definição só porque os dois relógios de vez desta célula fazem
    exatamente a mesma coisa e diferem só na chave: o da OFERTA, na fila, e o da
    RESERVA, no Mural. Duas cópias divergiriam no primeiro dia em que uma delas
    ganhasse um cuidado a mais, e a divergência apareceria como "o aluno perdeu
    a vez dormindo" numa das pistas e não na outra.
    """
    duracao = _horas_do_parametro(chave, agora, site_id=site_id)
    janela = Janela.do_banco(agora, site_id=site_id)
    return somar_horas_uteis(agora, duracao, janela)


def calcular_expiracao(agora: datetime, *, site_id: str) -> datetime:
    """Quando expira a oferta feita em `agora`. A costura que o motor recebe.

    Substitui a `expiracao_provisoria` do degrau 2.3, que contava horas de
    parede e cuja docstring já dizia que morreria aqui. A assinatura é a mesma
    de propósito: o motor a recebe como argumento
    (`rodar(..., calcular_expiracao=...)`), e é isso que fez a troca ser uma
    linha em vez de uma cirurgia no meio da varredura.
    """
    return _vence_em_horas_uteis("relogio_da_oferta", agora, site_id=site_id)


def calcular_expiracao_da_reserva(agora: datetime, *, site_id: str) -> datetime:
    """Quando vence a vez de quem pegou um projeto no Mural em `agora`.

    Produto: `PLANO-AREA-DE-NEGOCIACAO.md` §3.2 e §9
    (`relogio_da_reserva_no_mural`, três horas úteis).

    **É o MESMO relógio de horas úteis da oferta, e isso é decisão, e não
    preguiça.** As três horas da reserva existem pela mesma razão que as três da
    oferta: são o tempo de a pessoa olhar o briefing e responder. Se o relógio
    do Mural corresse de madrugada, o aluno que pegasse um projeto às 21h o
    perderia dormindo, e a pista nova teria uma justiça diferente da pista
    velha sem ninguém ter decidido isso.

    **E ele para na primeira proposta.** Este relógio mede só a primeira perna,
    do "Pegar" ao "Propor"; a partir da proposta quem manda são os relógios da
    negociação, de 24 horas úteis por rodada (§4.2). Sem essa passagem de
    bastão, a reserva venceria no meio da primeira rodada e o projeto voltaria
    ao Mural com uma proposta de pé. Quem passa o bastão é a TAR-134, fechando
    a reserva em `negociando`.
    """
    return _vence_em_horas_uteis("relogio_da_reserva_no_mural", agora, site_id=site_id)


def calcular_validade_da_proposta(agora: datetime, *, site_id: str) -> datetime:
    """Ate quando fica de pe a proposta feita em `agora`. O relogio da negociacao.

    Produto: `PLANO-AREA-DE-NEGOCIACAO.md` §4.2 e §9 (`validade_da_proposta`,
    24 horas uteis).

    **E o MESMO relogio de horas uteis da oferta e da reserva**, e o plano pede
    isso com todas as letras: *"no mesmo relogio de horas uteis que a lei ja
    definiu para a oferta"*. Um segundo relogio aqui daria a negociacao uma
    justica diferente da fila sem ninguem ter decidido isso, e a diferenca
    apareceria como "o aluno perdeu o projeto dormindo" em uma das pistas e nao
    na outra.

    Terceiro chamador de `_vence_em_horas_uteis`, e nenhuma linha de conta nova:
    o que muda entre os tres relogios de vez desta celula e so a CHAVE.
    """
    return _vence_em_horas_uteis("validade_da_proposta", agora, site_id=site_id)


def limite_para_pedir_extensao(
    prazo_final: datetime, prazo_dias: int, agora: datetime, *, site_id: str
) -> datetime:
    """Ate quando o aluno pode pedir a extensao de um prazo ACORDADO ([INV-ENC-N8]).

    Produto: `PLANO-AREA-DE-NEGOCIACAO.md` §4.3, ultimo paragrafo. A lei da
    metade de baixo (§6.6) da uma extensao pedida *"ate 24h antes do prazo"*, e
    ela nasceu de prazos de 3, 7 e 14 dias, que vinham da tabela. Com prazo
    NEGOCIADO, um aluno pode combinar 1 dia, e nesse caso a janela de 24 horas
    simplesmente nao existe: o pedido teria de ser feito antes de o prazo
    comecar.

    Entao a antecedencia e a MENOR das duas: metade do prazo combinado, ou o
    `extensao_pedida_ate_horas_antes` da lei. O que se compara e a
    ANTECEDENCIA, e nao o instante, e essa e a leitura que faz a segunda frase
    do plano ser verdade (*"prazo curto continua tendo janela, e prazo longo
    continua com a regra que a lei ja tinha"*): com 7 dias, o menor entre 3,5
    dias e 24 horas e 24 horas, e a regra antiga fica de pe; com 1 dia, o menor
    e 12 horas, e a janela existe.

    Horas de PAREDE, e nao uteis, porque o prazo do acordo tambem e de parede
    (dias corridos, como a lei ja define). Contar a antecedencia em horas uteis
    faria o limite andar para tras dentro de um prazo que nao anda.
    """
    da_lei = _horas_do_parametro(
        "extensao_pedida_ate_horas_antes", agora, site_id=site_id
    )
    metade_do_combinado = timedelta(days=prazo_dias) / 2
    return prazo_final - min(da_lei, metade_do_combinado)


def prazo_para_virar_aberta(agora: datetime, *, site_id: str) -> timedelta:
    """Quantas horas DE PAREDE uma encomenda espera na fila antes da chamada aberta.

    Horas de parede, e não úteis, e a diferença é uma decisão de produto lida
    direto da lei §6: a unidade de `relogio_da_oferta` está escrita como "horas
    úteis" e a de `horas_para_virar_aberta` como "horas na fila". Faz sentido:
    o relógio da oferta protege o SONO DO ALUNO, e a espera na fila é sentida
    pelo CLIENTE, que não dorme junto com a janela.

    Contar as 24h em horas úteis daria quase dois dias inteiros de espera para
    quem pagou, e o plano §6.4 fala em 24h como um prazo que o cliente
    reconhece.
    """
    return _horas_do_parametro("horas_para_virar_aberta", agora, site_id=site_id)


def prazo_para_escalar_chamada_aberta(agora: datetime, *, site_id: str) -> timedelta:
    """Quantas horas de parede uma chamada aberta espera sem aceite.

    A chamada aberta já avisou todos os elegíveis. Se ninguém aceitar, o
    próximo tique precisa entregá-la ao plantão, usando a chave histórica
    própria dessa segunda espera. Horas de parede mantêm a mesma
    unidade do prazo que levou a encomenda até a chamada aberta.
    """
    return _horas_do_parametro(
        "horas_para_escalar_chamada_aberta", agora, site_id=site_id
    )
