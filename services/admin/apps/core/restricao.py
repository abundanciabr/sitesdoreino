"""A restrição desta semana: o único gargalo que, melhorado, move a meta.

Degrau 1 do `docs/decisoes/PLANO-PAINEL-DE-GESTAO.md` (§6.3), a peça nova
mais valiosa dos documentos do Scale OS (1 §8 a §10 e §33; 2 Parte VII; 3 §26
a §30; 4 Parte X): uma empresa tem muitos problemas e poucos gargalos, e
melhorar o que não é o gargalo é encher um cano furado.

## De que jornada este módulo fala, e de qual ele NÃO fala

Aqui se mede a jornada da **sala de espera**: **cadastrou → pediu entrada →
foi liberada → entrou pela primeira vez**. Os nomes das passagens são os que a
célula `alunos` dá às próprias peças (`pre-matriculas`), e trocá-los é Rito de
Contrato dela, não texto de painel.

O que este módulo **não** é, e até 05/09/2026 dizia ser: o caminho da venda
que leva à Meta 1. O mantenedor corrigiu a premissa naquele dia, com estas
palavras: *"ninguém pede entrada na escola, todos entram apenas e unicamente
pela matrícula mediante a compra do curso"*. Quem chega na fila **já comprou,
fora do site**, e o que ele espera é confirmação. A restrição medida aqui é,
portanto, o gargalo da CONFIRMAÇÃO de vendas feitas fora, e ela move a meta de
verdade (cada confirmação é +1), mas não é a torneira dela. O caminho da venda
tem cartões próprios (`visitas-na-pagina-de-venda-por-semana` e
`compras-pelo-checkout-por-semana`), apagados enquanto o checkout estiver
congelado pela decisão dele de 22/08/2026, e nasce medível no degrau 9 do
plano, quando a célula de medição existir.

A `admin` só enxerga ao vivo, pela célula `alunos`, a passagem do meio:
**pediu entrada → foi liberada** (a fila e a lista de alunos, com `criada_em`
e `virou_aluno_em`). As outras três não têm fonte nesta célula ainda
(cadastros moram na `identidade`, sem porta de contagem; "entrou pela primeira
vez" não é gravado em lugar nenhum), e este módulo DIZ isso em vez de fingir
que mediu: uma etapa sem dados nunca é escolhida como restrição, e a tela
nomeia as que faltam.

## A regra da suspeita (calculada) e a confirmação (dele)

O Scale OS 1.2 §51 é claro: a IA propõe "suspeita"; o humano promove a
"confirmada". Aqui a suspeita é regra explícita, sem peso escondido:

1. Se há gente esperando na sala há 2 dias ou mais, OU o tempo mediano de
   liberação nos últimos 28 dias passa de 2 dias, a restrição suspeita é **a
   confirmação**: cada pessoa parada ali já pagou, fora do site, e é +1 na
   meta ao ser confirmada. Confiança ALTA: é medido ao vivo.
2. Senão, se ninguém chegou à sala de espera nos últimos 28 dias, a suspeita
   é **a chegada**: nenhuma venda feita fora chegou para confirmação.
   Confiança MÉDIA: a admin vê quem chega na sala, mas não vê os cadastros
   que nunca compraram.
3. Senão, **não há restrição medível**: a liberação está em dia, e as etapas
   seguintes não têm dados. Isso é resposta, não vazio.

A confirmação mora no cartão (`confirmada`: etapa, data e o registro do
livro que a declara), gravada por PR quando o mantenedor decide. A régua no
cartão, o fato no livro, como o alvo da meta.
"""

from __future__ import annotations

import datetime as dt
from statistics import median

from .placar import STATUS_QUE_COMPRARAM, dia_em_sao_paulo

#: Quanto tempo esperando na sala já é gargalo. É a medida de direção
#: "liberações em até 48 horas" do plano (§4.1 da versão da manhã, §8 degrau 2
#: da atual): a parte da jornada que depende SÓ da casa, porque a pessoa já pagou.
DIAS_DE_ESPERA_QUE_VIRAM_GARGALO = 2

#: A janela da medição. 28 dias (quatro semanas cheias) e 7 (a semana), como
#: os documentos pedem: "ontem versus hoje" engana (Scale OS 1.1 §124).
JANELA_LONGA = 28
JANELA_CURTA = 7

#: As quatro passagens, na ordem em que uma pessoa as vive. Só a segunda tem
#: fonte nesta célula hoje; as outras dizem por quê.
ETAPAS = (
    {
        "chave": "entrada",
        "nome": "cadastrou → pediu entrada",
        "fonte": None,
        "sem_fonte_porque": "a admin não conta cadastros: a célula identidade ainda não tem porta de contagem (plano, degrau 7).",
    },
    {
        "chave": "liberacao",
        "nome": "pediu entrada → foi liberada",
        "fonte": "célula alunos, ao vivo: a fila (GET /pre-matriculas) e a lista (GET /matriculas, virou_aluno_em)",
        "sem_fonte_porque": None,
    },
    {
        "chave": "primeira-entrada",
        "nome": "foi liberada → entrou pela primeira vez",
        "fonte": None,
        "sem_fonte_porque": "a plataforma não guarda o último acesso de ninguém; nasce quando a célula de medição receber o evento de entrada (plano, degrau 7).",
    },
    {
        "chave": "forum",
        "nome": "entrou → escreveu no fórum",
        "fonte": None,
        "sem_fonte_porque": "a admin não lê o fórum; a célula de medição vai receber forum.topico-criado (plano, degrau 7).",
    },
)


def _dias_desde(texto: object, hoje: dt.date) -> int | None:
    dia = dia_em_sao_paulo(texto)
    return None if dia is None else (hoje - dia).days


def medir_liberacao(
    aguardando: list[dict] | None,
    recusados: list[dict] | None,
    alunos: list[dict] | None,
    hoje: dt.date,
) -> dict | None:
    """A passagem "chegou na sala → foi confirmada", nos últimos 28 e 7 dias.

    `None` quando não dá para medir (alguma lista não chegou): "não medi" se
    declara, não vira zero.
    """
    if aguardando is None or recusados is None or alunos is None:
        return None
    liberados = [
        a
        for a in alunos
        if a.get("origem") == "liberado" and a.get("status") in STATUS_QUE_COMPRARAM
    ]
    # Pedidos: quem ainda espera + quem foi recusado + quem foi liberado, todos
    # pela data em que PEDIRAM (`criada_em`, que na fila e na lista é o mesmo
    # carimbo: o instante do pedido).
    pedidos_28 = pedidos_7 = 0
    for linha in list(aguardando) + list(recusados) + liberados:
        dias = _dias_desde(linha.get("criada_em"), hoje)
        if dias is None:
            continue
        if 0 <= dias < JANELA_LONGA:
            pedidos_28 += 1
        if 0 <= dias < JANELA_CURTA:
            pedidos_7 += 1
    esperas = []
    liberados_28 = liberados_7 = 0
    for a in liberados:
        dias = _dias_desde(a.get("virou_aluno_em"), hoje)
        if dias is None or not 0 <= dias < JANELA_LONGA:
            continue
        liberados_28 += 1
        if dias < JANELA_CURTA:
            liberados_7 += 1
        pedido = dia_em_sao_paulo(a.get("criada_em"))
        liberacao = dia_em_sao_paulo(a.get("virou_aluno_em"))
        if pedido is not None and liberacao is not None and liberacao >= pedido:
            esperas.append((liberacao - pedido).days)
    esperando_ha_muito = sum(
        1
        for p in aguardando
        if isinstance(p.get("esperando_ha_dias"), int)
        and p["esperando_ha_dias"] >= DIAS_DE_ESPERA_QUE_VIRAM_GARGALO
    )
    return {
        "pedidos_28": pedidos_28,
        "pedidos_7": pedidos_7,
        "liberados_28": liberados_28,
        "liberados_7": liberados_7,
        "esperando": len(aguardando),
        "esperando_ha_muito": esperando_ha_muito,
        "mediana_dias": median(esperas) if esperas else None,
        "taxa_28": (round(liberados_28 / pedidos_28, 2) if pedidos_28 else None),
    }


def escolher_restricao(medida: dict | None, cartao: dict) -> dict:
    """A suspeita desta semana, pela regra explícita do cabeçalho.

    Devolve `etapa` (a chave de `ETAPAS`, ou `None`), `veredito` em uma
    destas palavras: `nao-consigo-medir` · `liberacao` · `entrada` ·
    `sem-restricao-medivel`; mais `confianca`, `impacto` (quantas pessoas a
    meta ganha se a etapa destravar), `gesto` e `confirmada` (do cartão).
    """
    confirmada = cartao.get("confirmada")
    base = {
        "etapa": None,
        "veredito": None,
        "confianca": None,
        "impacto": None,
        "gesto": None,
        "confirmada": confirmada,
        "medida": medida,
        "etapas": ETAPAS,
    }
    if medida is None:
        return {**base, "veredito": "nao-consigo-medir"}
    demora = medida["mediana_dias"] is not None and (
        medida["mediana_dias"] > DIAS_DE_ESPERA_QUE_VIRAM_GARGALO
    )
    if medida["esperando_ha_muito"] > 0 or demora:
        return {
            **base,
            "etapa": "liberacao",
            "veredito": "liberacao",
            "confianca": "alta",
            "impacto": medida["esperando"],
            "gesto": "Abra a fila em /admin/escola/ e confirme quem já pagou: cada pessoa parada ali comprou fora do site e é +1 na meta hoje.",
        }
    if medida["pedidos_28"] == 0:
        return {
            **base,
            "etapa": "entrada",
            "veredito": "entrada",
            "confianca": "media",
            "impacto": None,
            "gesto": "Ninguém chegou à sala de espera em 28 dias, ou seja, nenhuma venda feita fora do site chegou para confirmação. Hoje a compra acontece na sua divulgação (a home não convida, por decisão sua de 28/08), e o caminho da venda dentro do site ainda está apagado.",
        }
    return {**base, "veredito": "sem-restricao-medivel", "confianca": "alta"}
