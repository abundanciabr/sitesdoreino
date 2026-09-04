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
    """
    linha = Parametro.vigente_em(chave, agora, site_id=site_id)
    if linha is None:
        raise ParametroAusente(
            f"site {site_id!r}: sem valor vigente em {agora.isoformat()} para "
            f"{chave}. Rode `python manage.py semear_parametros --site {site_id}` "
            "ou confira a data de `desde` das linhas."
        )
    return timedelta(hours=int(linha.valor))


def calcular_expiracao(agora: datetime, *, site_id: str) -> datetime:
    """Quando expira a oferta feita em `agora`. A costura que o motor recebe.

    Substitui a `expiracao_provisoria` do degrau 2.3, que contava horas de
    parede e cuja docstring já dizia que morreria aqui. A assinatura é a mesma
    de propósito: o motor a recebe como argumento
    (`rodar(..., calcular_expiracao=...)`), e é isso que fez a troca ser uma
    linha em vez de uma cirurgia no meio da varredura.

    Duas leituras do banco, as duas fail-closed e as duas no valor vigente em
    `agora`: quantas horas úteis (`relogio_da_oferta`) e quais são as horas
    úteis (`janela_inicio`, `janela_fim`).
    """
    duracao = _horas_do_parametro("relogio_da_oferta", agora, site_id=site_id)
    janela = Janela.do_banco(agora, site_id=site_id)
    return somar_horas_uteis(agora, duracao, janela)


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
