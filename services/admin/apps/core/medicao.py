"""A memória da escola, lida da célula de medição (degrau 7.6 do plano).

`docs/decisoes/PLANO-PAINEL-DE-GESTAO.md` §6.6 (a confiança). Todo o resto
desta tela conta AO VIVO, perguntando às células donas a cada abertura: isso
responde "quantas alunas há agora" e nunca "quantas havia na semana passada".
A `metricas` guarda o passado, e desde o degrau 7.4 responde por contrato.

O QUE ESTA LINHA RESPONDE, E POR QUE ELA VEM ANTES DOS NÚMEROS
--------------------------------------------------------------
Uma pergunta só: **dá para confiar no que esta tela vai mostrar?** O plano
(§2, régua 8) manda que tela vazia diga o que falta e que dado velho diga que
é velho. A memória é quem sabe as duas coisas: se os fatos pararam de chegar,
todo número histórico desta casa começa a envelhecer em silêncio, e o único
lugar onde isso aparece é aqui.

Ela NÃO é um bloco: a capa tem teto de nove e se recusa a crescer (§3). É a
"confiança dos dados desta tela" que o cabeçalho já devia dizer.

OS CINCO DESFECHOS, E POR QUE SÃO CINCO
---------------------------------------
Cada um leva a uma frase diferente na tela, porque cada um pede uma coisa
diferente de quem lê:

- `sem-site`      não soube de qual site perguntar (o catálogo não respondeu).
- `sem-configuracao`  o par admin→metricas não foi ligado na VPS.
- `nao-respondeu`  perguntei e a medição não respondeu a tempo.
- `vazia`         perguntei, respondeu, e ainda não guardou fato nenhum.
- `medindo`       está guardando; e aí a linha diz quanto, de quê e desde quando.

`vazia` e `nao-respondeu` seriam o mesmo `0` num desenho descuidado, e é
exatamente a confusão que esta célula existe para não cometer: zero é uma
afirmação sobre o mundo, ausência de resposta não é.

O NOME DE CADA ASSUNTO
----------------------
Os eventos têm nome de máquina (`identidade.pessoa-cadastrada`). Quem lê esta
tela não é máquina, então há um dicionário abaixo — e ele NÃO é uma lista que
precisa ser mantida em dia: assunto que não estiver nele aparece com o nome
cru, nunca escondido. Uma tradução que faltasse não pode virar um fato que
some, e é por isso que o `.get` cai no próprio nome.
"""

from __future__ import annotations

import datetime as dt

from .clients import MedicaoClient

#: Quantos dias sem um assunto chegar já é motivo de dizer que ele parou.
#: Sete porque é a janela de cobertura do §6.6, e porque abaixo disso um fim
#: de semana quieto viraria alarme.
DIAS_PARA_DIZER_QUE_PAROU = 7

#: Nome de máquina → nome de gente. Incompleto por natureza (ver o docstring).
ASSUNTOS = {
    "identidade.pessoa-cadastrada": "gente se cadastrando",
    "quiz.completado": "quiz respondido",
    "forum.topico-criado": "pergunta no fórum",
    "forum.mensagem-criada": "resposta no fórum",
    "forum.resposta-aceita": "resposta aceita no fórum",
    "forum.mensagem-removida": "mensagem tirada do fórum",
    "sugestao.criada": "ideia na Caixa",
    "sugestao.status-alterado": "ideia mudou de situação",
    "sugestao.voto-adicionado": "voto numa ideia",
    "sugestao.voto-removido": "voto tirado de uma ideia",
}


def nome_de_gente(tipo: str) -> str:
    return ASSUNTOS.get(tipo, tipo)


def ha_quanto_tempo(instante: dt.datetime, agora: dt.datetime) -> str:
    """ "há 2 minutos", "há 3 horas", "há 2 dias" — sem "há 0 minutos"."""
    segundos = (agora - instante).total_seconds()
    if segundos < 90:
        return "agora mesmo"
    minutos = int(segundos // 60)
    if minutos < 60:
        return f"há {minutos} minutos"
    horas = int(minutos // 60)
    if horas < 24:
        return f"há {horas} hora{'s' if horas > 1 else ''}"
    dias = int(horas // 24)
    return f"há {dias} dia{'s' if dias > 1 else ''}"


def _instante(texto: object) -> dt.datetime | None:
    if not isinstance(texto, str):
        return None
    try:
        quando = dt.datetime.fromisoformat(texto)
    except ValueError:
        return None
    return quando if quando.tzinfo is not None else None


def a_cobertura(
    site_id: str | None,
    agora: dt.datetime,
    cliente: MedicaoClient | None = None,
) -> dict:
    """O veredito da memória e, quando ela responde, UMA LINHA POR ASSUNTO.

    É a única função desta casa que decide qual dos cinco desfechos aconteceu.
    A linha do placar (`a_memoria`) e a tela da confiança
    (`/admin/placar/confianca/`) leem daqui, e é por isso que as duas nunca
    conseguem discordar sobre "não perguntei" e "perguntei e não há nada": uma
    segunda cópia dessa decisão seria a lei anti-duplicação quebrada no lugar
    exato onde ela mais dói.

    `assuntos` vem VAZIA em todo desfecho que não é `medindo`, e quem desenha
    a tela precisa olhar o veredito antes da lista. Lista vazia aqui não
    significa "não há assunto": significa que não houve resposta para listar.
    """
    if not site_id:
        return {"veredito": "sem-site", "assuntos": []}

    cliente = cliente or MedicaoClient()
    desfecho, tipos = cliente.cobertura(site_id)
    if desfecho != MedicaoClient.OK:
        return {"veredito": desfecho, "assuntos": []}
    if not tipos:
        return {"veredito": "vazia", "assuntos": []}

    fatos = 0
    ultimo: dt.datetime | None = None
    assuntos: list[dict] = []
    for linha in tipos:
        tipo = str(linha.get("tipo") or "")
        quantidade = linha.get("quantidade")
        if isinstance(quantidade, int):
            fatos += quantidade
        recebido = _instante(linha.get("ultimo_recebido_em"))
        if recebido is not None and (ultimo is None or recebido > ultimo):
            ultimo = recebido
        dias = linha.get("dias_desde_o_ultimo")
        assuntos.append(
            {
                "tipo": tipo,
                "nome": nome_de_gente(tipo),
                "quantidade": quantidade if isinstance(quantidade, int) else None,
                "dias": dias if isinstance(dias, int) else None,
                "parou": isinstance(dias, int) and dias >= DIAS_PARA_DIZER_QUE_PAROU,
                "ultimo": ha_quanto_tempo(recebido, agora) if recebido else None,
            }
        )

    # Os calados na frente: quem abre esta lista está procurando o que parou,
    # e o que parou não pode estar no fim de uma lista de vinte assuntos.
    assuntos.sort(key=lambda a: (not a["parou"], a["nome"]))
    return {
        "veredito": "medindo",
        "fatos": fatos,
        "assuntos": assuntos,
        # Os calados, já separados, porque as duas telas que leem daqui os
        # querem em destaque e nenhuma das duas tem como filtrar uma lista.
        "parados": [a for a in assuntos if a["parou"]],
        "ultimo": ha_quanto_tempo(ultimo, agora) if ultimo else None,
    }


def a_memoria(
    site_id: str | None,
    agora: dt.datetime,
    cliente: MedicaoClient | None = None,
) -> dict:
    """A linha de confiança do cabeçalho. Nunca levanta, nunca inventa zero."""
    cliente = cliente or MedicaoClient()
    coberta = a_cobertura(site_id, agora, cliente)
    if coberta["veredito"] != "medindo":
        return {"veredito": coberta["veredito"]}

    # A fila de mortos é uma SEGUNDA pergunta, e a resposta dela não pode
    # derrubar a primeira: se ela falhar sozinha, a linha continua dizendo o
    # que a cobertura contou, e o número de quebrados vem como `None` (a tela
    # simplesmente não fala deles). Silêncio aqui é honesto; um zero não seria.
    _desfecho_dos_mortos, quebrados = cliente.quebrados()

    return {
        "veredito": "medindo",
        "fatos": coberta["fatos"],
        "assuntos": len(coberta["assuntos"]),
        "ultimo": coberta["ultimo"],
        "parados": sorted(a["nome"] for a in coberta["parados"]),
        "quebrados": quebrados,
    }
