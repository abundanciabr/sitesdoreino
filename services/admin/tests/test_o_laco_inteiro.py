"""O TESTE DO LAÇO INTEIRO — o guarda do degrau 13 do painel de gestão.

É o cenário que o quinto documento do Scale OS pede em §81
(`docs/consultorias/painel-de-gestao/SCALE-OS-5-growth-execution-engine.md`),
traduzido para as peças que esta casa realmente tem.

## Por que ele existe, e por que ele vale mais que os guardas que já existem

Cada estação do laço já é testada sozinha: `test_placar.py` mede a régua,
`test_direcao.py` as duas medidas da semana, `test_restricao.py` a suspeita,
`test_laboratorio.py` o experimento, `test_reuniao.py` a pauta, `test_doze.py`
o placar de doze. **O que ninguém testava é o LAÇO**: se o que sai de uma
estação entra na próxima sem ninguém traduzir à mão.

É a diferença entre doze peças que funcionam e uma máquina que gira. Uma peça
pode mudar de formato (um `None` que virou `0`, uma chave renomeada, um
veredito com palavra nova) sem nenhum teste próprio ficar vermelho, e o laço
para de fechar em silêncio. A partir daqui, para.

## As treze estações, na ordem em que a semana acontece

1. ciclo ativo (o cartão da meta é válido e declara a curva);
2. a meta (o veredito ganhando/perdendo sai da curva);
3. as medidas de direção (as duas que a casa move na semana);
4. a medição (as duas medidas saem das listas de gente de verdade);
5. a restrição detectada (a suspeita da semana sai da medição);
6. o experimento (a aposta escrita ANTES, no livro, aparece rodando);
7. a semana aberta (a pauta de segunda monta o pedido para o robô);
8. a tarefa gerada (o pedido carrega o compromisso, com prazo);
9. a tarefa executada (a resposta no livro fecha o compromisso, calculada);
10. a semana encerrada (o resultado no livro fecha o experimento);
11. o aprendizado registrado (o experimento fechado vira número);
12. o placar atualizado (o número do laboratório e o veredito do ciclo mudam);
13. o ciclo fechado (o degrau 13: e ele se RECUSA a fechar sem a decisão do
    que a escola para de fazer).

## Um relógio só, e uma fonte só

O laço inteiro roda com UMA data (`HOJE`) e UMA lista de gente. Duas datas
fariam duas estações discordarem por um dia e o teste passar assim mesmo, que
é exatamente o defeito que ele existe para pegar.
"""

from __future__ import annotations

import datetime as dt

from apps.core import direcao, doze, fechamento, laboratorio, placar, restricao, reuniao

#: Uma segunda-feira dentro do ciclo sintético abaixo.
HOJE = dt.date(2026, 10, 26)
PARTIDA = dt.date(2026, 9, 3)

#: O ciclo sintético: pequeno o bastante para a conta ser conferível de cabeça,
#: e LEGAL o bastante para `placar.validar` aceitá-lo (a primeira estação prova
#: isso). Um cartão de fantasia faria o laço girar sobre uma régua que a casa
#: recusaria na vida real.
CARTAO_DO_CICLO = {
    "nome": "compras-no-ciclo",
    "tipo": "resultado",
    "andar": 0,
    "pergunta": "Quantas pessoas viraram alunas desde o começo do ciclo?",
    "definicao": "Fichas de aluno com data de virada dentro do ciclo.",
    "formula": "contagem das fichas ativas, suspensas ou encerradas",
    "fonte": "célula alunos",
    "autoridade": "alunos",
    "dono": "mantenedor",
    "frequencia": "tempo real",
    "direcao": "subir",
    "acao": "Abra a fila em /admin/escola/ e confirme quem já pagou.",
    "par": "alunos-ativos-30d",
    "alvo": 30,
    "partida": 0,
    "partida_em": "2026-09-03",
    "ate": "2026-11-06",
    "semanas": [
        {"n": 1, "de": "2026-10-19", "ate": "2026-10-23", "alvo": 10},
        {"n": 2, "de": "2026-10-26", "ate": "2026-10-30", "alvo": 20},
    ],
    "versao": 1,
    "desde": "2026-09-03",
}

CARTAO_DOS_PEDIDOS = {
    "nome": "pedidos-de-entrada-por-semana",
    "tipo": "direcao",
    "andar": 1,
    "pergunta": "Quantas pessoas chegaram à sala de espera nesta semana?",
    "definicao": "Chegadas à sala de espera na semana.",
    "formula": "contagem por semana",
    "fonte": "célula alunos",
    "autoridade": "alunos",
    "dono": "mantenedor",
    "frequencia": "semanal",
    "par": "alunos-ativos-30d",
    "meta_semanal": 4,
    "versao": 1,
    "desde": "2026-09-05",
}

CARTAO_DAS_48H = {
    "nome": "liberacoes-em-48h",
    "tipo": "direcao",
    "andar": 1,
    "pergunta": "Quantas confirmações saíram em até 48 horas?",
    "definicao": "Confirmações da sala de espera dentro de dois dias.",
    "formula": "porcentagem",
    "fonte": "célula alunos",
    "autoridade": "alunos",
    "dono": "mantenedor",
    "frequencia": "semanal",
    "par": "alunos-ativos-30d",
    "versao": 1,
    "desde": "2026-09-05",
}

CARTAO_DA_RESTRICAO = {
    "nome": "restricao-da-semana",
    "tipo": "confianca",
    "andar": 1,
    "pergunta": "Qual etapa está segurando a meta esta semana?",
    "definicao": "A etapa com a maior perda medida.",
    "formula": "regra explícita sobre a medição da fila",
    "fonte": "célula alunos",
    "autoridade": "admin",
    "dono": "mantenedor",
    "frequencia": "semanal",
    "versao": 1,
    "desde": "2026-09-03",
}


def _pessoa(**campos) -> dict:
    base = {
        "status": "ativa",
        "origem": "liberado",
        "criada_em": "2026-10-20T09:00:00-03:00",
        "virou_aluno_em": "2026-10-21T09:00:00-03:00",
    }
    base.update(campos)
    return base


def _registro(arquivo: str, tipo: str, quando: str, **extra) -> dict:
    """Um cabeçalho de registro do livro, com os campos que os leitores usam."""
    base = {
        "arquivo": arquivo,
        "tipo": tipo,
        "quando": quando,
        "titulo": f"Registro {arquivo}",
        "responde_a": None,
        "vence_em_dias": None,
        "precisa_do_dono": False,
        "foto": None,
        "problema": None,
        "hipotese": None,
        "metrica": None,
        "guarda": None,
        "veredito": None,
        "portao": None,
        "evidencia": None,
        "verificado_em": None,
    }
    base.update(extra)
    return base


def test_o_laco_inteiro_gira_do_ciclo_ativo_ate_o_placar_atualizado():
    """As treze estações, em ordem, com um relógio só e uma fonte só."""

    # ---------------------------------------------- 1. ciclo ativo
    assert (
        placar.validar(CARTAO_DO_CICLO) == []
    ), "o ciclo do cenário não é um cartão legal"
    faixas = placar.semanas_do_ciclo(CARTAO_DO_CICLO)
    assert [f["n"] for f in faixas] == [1, 2], "o ciclo ativo perdeu a curva"
    assert faixas[-1]["acumulado"] == CARTAO_DO_CICLO["alvo"]

    # A gente da escola nesta semana: seis pedidos de entrada, quatro
    # confirmados dentro do ciclo, dois ainda esperando ha mais de dois dias.
    aguardando = [
        {"criada_em": "2026-10-20T09:00:00-03:00", "esperando_ha_dias": 6},
        {"criada_em": "2026-10-21T09:00:00-03:00", "esperando_ha_dias": 5},
    ]
    recusados: list[dict] = []
    alunos = [
        _pessoa(
            criada_em=f"2026-10-{dia}T09:00:00-03:00",
            virou_aluno_em=f"2026-10-{dia + 1}T09:00:00-03:00",
        )
        for dia in (20, 21, 22, 23)
    ]

    # ---------------------------------------------- 2. a meta
    contagem = placar.contar_compras(alunos, PARTIDA, HOJE)
    resultado = placar.calcular_placar(CARTAO_DO_CICLO, contagem["ciclo"], HOJE)
    assert contagem["ciclo"] == 4
    assert resultado["veredito"] == "perdendo", (
        "a semana 1 pedia 10 e a escola fez 4: a régua tem de dizer perdendo, "
        f"e disse {resultado['veredito']}"
    )
    assert resultado["esperado_hoje"] == 14, "o esperado de hoje saiu da curva errada"

    # ---------------------------------------------- 3 e 4. as medidas, medidas
    pedidos = direcao.medir_pedidos(aguardando, recusados, alunos, HOJE)
    liberacoes = direcao.medir_liberacoes_em_48h(aguardando, alunos, HOJE)
    assert pedidos is not None and liberacoes is not None
    assert pedidos[0] == 6, "as seis chegadas da semana não chegaram à medida"
    assert liberacoes["total"] == 4 and liberacoes["por_cento"] == 100

    a_direcao = direcao.calcular_direcao(
        CARTAO_DOS_PEDIDOS, CARTAO_DAS_48H, CARTAO_DO_CICLO, pedidos, liberacoes, HOJE
    )
    assert a_direcao["pedidos"]["veredito"] == "cumprida", "6 chegadas contra meta 4"
    assert (
        a_direcao["liberacoes"]["veredito"] == "abaixo"
    ), "duas pessoas esperam há mais de dois dias: a medida não pode dizer que está em dia"

    # ---------------------------------------------- 5. a restrição detectada
    medida = restricao.medir_liberacao(aguardando, recusados, alunos, HOJE)
    a_restricao = restricao.escolher_restricao(medida, CARTAO_DA_RESTRICAO)
    assert (
        a_restricao["veredito"] == "liberacao"
    ), "a espera de seis dias na sala tinha de virar a restrição da semana"
    assert a_restricao["impacto"] == 2, "a restrição perdeu o tamanho do impacto"

    # ---------------------------------------------- 6. o experimento
    experimento = _registro(
        "20261019-001-avisar-quem-espera",
        "medicao",
        "2026-10-19",
        vence_em_dias=14,
        problema="quem compra fora do site espera dias pela confirmação",
        hipotese="avisar por mensagem no mesmo dia corta a espera pela metade",
        metrica="liberacoes-em-48h",
        guarda="se alguém esperar mais de 5 dias, paramos",
    )
    livro = [experimento]
    lab = laboratorio.montar(livro, HOJE)
    assert [e["arquivo"] for e in lab["rodando"]] == [experimento["arquivo"]]
    assert lab["vencidos"] == [], "o experimento ainda está no prazo"

    # ---------------------------------------------- 7 e 8. semana aberta, tarefa gerada
    compromisso_texto = "confirmar toda a sala de espera até quarta"
    pedido_da_semana = reuniao.montar_o_pedido(
        {"compromisso1": compromisso_texto, "confirmar_restricao": "a liberação"},
        HOJE,
    )
    assert pedido_da_semana is not None, "a pauta de segunda não gerou tarefa nenhuma"
    assert compromisso_texto in pedido_da_semana
    assert (
        f"vence_em_dias: {reuniao.VENCE_EM_DIAS}" in pedido_da_semana
    ), "tarefa sem prazo nunca vence, e o que não vence nunca é cobrado"

    # ---------------------------------------------- 9. a tarefa executada
    compromisso = _registro(
        "20261026-002-confirmar-a-sala-de-espera",
        "compromisso",
        "2026-10-26",
        titulo=compromisso_texto,
        vence_em_dias=reuniao.VENCE_EM_DIAS,
    )
    livro = livro + [compromisso]
    em_aberto = direcao.compromissos(livro, HOJE)
    assert [c["veredito"] for c in em_aberto] == ["em-aberto"]

    livro = livro + [
        _registro(
            "20261028-003-a-sala-de-espera-esta-vazia",
            "resposta",
            "2026-10-28",
            responde_a=compromisso["arquivo"],
        )
    ]
    depois = direcao.compromissos(livro, dt.date(2026, 10, 28))
    assert [c["veredito"] for c in depois] == [
        "cumprido"
    ], "a resposta no livro tinha de fechar o compromisso sozinha, sem ninguém digitar"

    # ---------------------------------------------- 10 e 11. semana encerrada, aprendizado
    livro = livro + [
        _registro(
            "20261028-004-avisar-funcionou",
            "medicao",
            "2026-10-28",
            responde_a=experimento["arquivo"],
            veredito="venceu",
        )
    ]
    fim_da_semana = dt.date(2026, 10, 28)
    lab = laboratorio.montar(livro, fim_da_semana)
    assert lab["rodando"] == [] and len(lab["encerrados"]) == 1
    assert (
        laboratorio.aprendizados_validados(livro, PARTIDA) == 1
    ), "o experimento fechado tinha de virar aprendizado validado do ciclo"

    # ---------------------------------------------- 12. o placar atualizado
    # A aposta venceu: a sala de espera foi confirmada, e as duas pessoas que
    # esperavam viraram alunas. O MESMO placar, relido, muda de veredito.
    alunos_depois = alunos + [
        _pessoa(
            criada_em="2026-10-26T09:00:00-03:00",
            virou_aluno_em=f"2026-10-{27 + n % 2}T{9 + n // 2:02d}:00:00-03:00",
        )
        for n in range(18)
    ]
    contagem_depois = placar.contar_compras(alunos_depois, PARTIDA, fim_da_semana)
    resultado_depois = placar.calcular_placar(
        CARTAO_DO_CICLO, contagem_depois["ciclo"], fim_da_semana
    )
    assert contagem_depois["ciclo"] == 22
    assert resultado_depois["veredito"] == "ganhando", (
        "o laço fechou: o experimento venceu, a sala esvaziou, e o placar tinha "
        f"de virar; ele disse {resultado_depois['veredito']}"
    )

    os_doze = doze.medir_os_doze(
        barra=None,
        por_mes=doze.compras_por_mes(alunos_depois, PARTIDA),
        liberacao=restricao.medir_liberacao(
            [], recusados, alunos_depois, fim_da_semana
        ),
        registros=livro,
        partida_em=PARTIDA,
        hoje=fim_da_semana,
        pasta=placar.diretorio_dos_cartoes(),
    )
    aprendizados = [
        d for d in os_doze if d["nome"] == "aprendizados-validados-no-ciclo"
    ]
    assert aprendizados, "o placar de doze perdeu o número do laboratório"
    assert aprendizados[0]["valor"] == 1, (
        "o aprendizado do laboratório não chegou ao placar de doze: o laço "
        "quebrou entre a estação 11 e a 12"
    )

    # ---------------------------------------------- 13. o ciclo fechado
    dia_do_fechamento = dt.date(2026, 11, 7)  # o dia seguinte ao `ate` do cartão
    dados = fechamento.montar(
        meta=CARTAO_DO_CICLO,
        resultado=placar.calcular_placar(
            CARTAO_DO_CICLO, contagem_depois["ciclo"], dia_do_fechamento
        ),
        direcao_da_semana=a_direcao,
        registros=livro,
        hoje=dia_do_fechamento,
    )
    assert (
        dados["estado"] == "terminou"
    ), "passado o dia do `ate`, a tela tem de dizer que o ciclo terminou"
    assert (
        dados["resultado"]["veredito"] == "vencida"
    ), "22 de 30 com o prazo passado é meta não batida, e a tela diz isso"
    assert dados["resultado"]["distancia"] == 8, "faltaram oito pessoas"

    # A ALMA DO DEGRAU: o ciclo NÃO fecha sem a decisão do que a escola para de
    # fazer. Sem ela não existe pedido nenhum para o robô.
    campos_sem_a_recusa = {
        "paramos_de_fazer": "   ",
        "proximo_alvo": "60",
        "proxima_ate": "2027-02-05",
    }
    pedido, faltando = fechamento.montar_o_pedido(
        campos_sem_a_recusa, dados, dia_do_fechamento
    )
    assert (
        pedido is None
    ), "o ciclo fechou sem ninguém dizer o que a escola para de fazer"
    assert [f["campo"] for f in faltando] == ["paramos_de_fazer"]
    assert faltando[0]["lei"] is True

    campos = {**campos_sem_a_recusa, "paramos_de_fazer": "parar de vender por mensagem"}
    pedido, faltando = fechamento.montar_o_pedido(campos, dados, dia_do_fechamento)
    assert faltando == []
    assert pedido is not None
    assert "parar de vender por mensagem" in pedido
    assert (
        "compras-no-ciclo.json" in pedido
    ), "o pedido tinha de mandar o robô gravar a meta seguinte no cartão"
