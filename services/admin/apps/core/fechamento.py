"""`/admin/placar/fechamento/` — o fim das 12 semanas, e o que a escola para de fazer.

Degrau 13 do `docs/decisoes/PLANO-PAINEL-DE-GESTAO.md` (§5 e §8). O ciclo tem
começo e fim; sem um rito de fim, ele vira um número que corre para sempre e
ninguém nunca decide nada por causa dele.

## As cinco perguntas do fechamento, e de onde cada uma sai

1. **A meta bateu, e por quê?** Sai da MESMA régua do placar
   (`placar.calcular_placar` sobre `painel/cartoes/compras-no-ciclo.json`). A
   curva não é reescrita aqui: uma segunda régua discordaria da primeira no
   primeiro ajuste de meta, e as duas teriam ar de certeza.
2. **As medidas de direção previram a meta?** Compara o veredito das duas
   medidas da semana (`direcao.calcular_direcao`) com o veredito do ciclo.
3. **O que a escola PARA de fazer.** É a alma do degrau, e é o único campo
   sem o qual `montar_o_pedido` devolve `None`: o ciclo não fecha. Um
   fechamento que só acrescenta compromissos é uma lista que cresce para
   sempre, e uma casa que nunca recusa nada nunca escolhe nada.
4. **A meta seguinte**, que o robô grava no cartão e no livro.
5. **A fase da escola**, calculada dos portões (§6.5), nunca digitada.

## Os portões, e por que eles são um campo do livro

O plano exige que a fase seja calculada: "cada portão é um registro com
`evidencia` e `verificado_em`". Para isso um registro precisa poder DIZER qual
portão ele prova, e por isso nasceu o campo `portao` no cabeçalho do livro. O
vocabulário fechado dos oito é imposto na ESCRITA por `painel/logica.js` (o
gerador recusa portão inventado), pelo mesmo desenho de `veredito` no
laboratório: o livro é JavaScript, esta tela é Python, e um dos dois lados
impõe as palavras. Aqui a leitura é fail-open e ainda assim honesta: portão
declarado com nome que não existe aparece na tela pelo nome, nunca sumindo.

**Declarar não é provar.** Um registro com `portao` mas sem `evidencia` e sem
`verificado_em` NÃO conta, e aparece à parte. É a mesma lei do verde do livro
(`painel/LEIA-ME.md`): prova conferida, ou não é verde.

## Esta tela não escreve nada, e isso é desenho

Como a reunião de segunda (degrau 3): o que ela produz é o PEDIDO para o robô,
um bloco de texto para colar numa sessão. Registro entra por PR, e cartão
também. Recarregar a página apaga o que foi digitado, e a tela diz isso.

## O estado vazio é o estado principal, e vai ser por três meses

O ciclo corrente partiu em 03/09/2026 e fecha em 15/12/2026. A tela nasce sem
nenhum ciclo fechado. Por isso o ramo "correndo" não é o caminho triste: é o
caminho normal, e ele mostra a prévia com os números de hoje mais o que vai
ser perguntado no dia. O que ele NÃO faz é transformar ausência em conclusão
(`armadilhas/271`): com a curva ainda em zero, "as medidas previram a meta"
não é "sim", é "ainda não dá para saber", e a tela explica por quê.
"""

from __future__ import annotations

import datetime as dt

from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from . import analista as analista_
from .direcao import ler_registros
from .placar import montar_o_placar, site_de

#: Os oito portões antes de escalar (Scale OS 2 §60, plano §6.5): a chave que o
#: registro escreve em `portao`, o nome na tela, e o que prova aquele portão.
#: A ordem é a do documento, e ela é a ordem em que uma escola os atravessa.
PORTOES = (
    (
        "demanda",
        "Demanda",
        "gente querendo o que a escola vende, medida fora da cabeça de quem vende",
    ),
    (
        "conversao",
        "Conversão",
        "quem chega vira quem compra, com o número dos dois lados",
    ),
    ("economia", "Economia", "o que cada aluno traz paga o que custou trazê-lo"),
    (
        "entrega",
        "Entrega",
        "o aluno recebe o que comprou, no prazo, sem depender de herói",
    ),
    ("resultado", "Resultado", "o aluno consegue o que veio buscar, e dá para provar"),
    ("retencao", "Retenção", "o aluno continua depois do primeiro mês"),
    (
        "repeticao",
        "Repetição",
        "o mesmo caminho traz o próximo aluno sem ser refeito à mão",
    ),
    ("escala", "Escala", "dobrar a entrada não quebra a entrega nem a conta"),
)

#: As fases da escola (Scale OS 2 §4). "Compondo" é a quarta e fica fora deste
#: cálculo de propósito: ela é conversa anual do mantenedor, e não sai de portão.
#:
#: A régua do plano dá dois cortes ("nenhum provado é achando; todos é
#: escalando") e cita "até quatro é provando". A faixa de cinco a sete ficou
#: sem nome no plano, e aqui ela é CONSERVADORA: enquanto faltar um portão, a
#: escola está provando. Uma tela que promovesse a escola a "escalando" com
#: portão em aberto seria a tela decidindo o que só a prova decide.
FASE_SEM_NENHUM = "achando"
FASE_COM_ALGUNS = "provando"
FASE_COM_TODOS = "escalando"

#: O que o fechamento exige para existir. O primeiro é a lei do degrau (o ciclo
#: não fecha sem ele); os outros dois existem porque o robô grava a meta
#: seguinte no cartão, e um alvo em branco viraria a régua de todo o painel.
OBRIGATORIOS = (
    (
        "paramos_de_fazer",
        "o que a escola PARA de fazer",
        "O ciclo não fecha sem isto. Um fechamento que só acrescenta é uma "
        "lista que cresce para sempre, e uma casa que nunca recusa nada nunca "
        "escolhe nada.",
    ),
    (
        "proximo_alvo",
        "o alvo do próximo ciclo",
        "É o número que o robô grava no cartão da meta. Sem ele o painel "
        "inteiro fica sem régua no dia seguinte ao fechamento.",
    ),
    (
        "proxima_ate",
        "a data em que o próximo ciclo fecha",
        "É o outro lado da régua. Sem data, ganhando e perdendo não existem.",
    ),
)

#: O arquivo que o robô edita para virar o ciclo. Escrito por extenso porque é
#: ele que o pedido manda mexer, e um caminho errado ali custa uma rodada.
CARTAO_DA_META_NO_REPOSITORIO = "painel/cartoes/compras-no-ciclo.json"


def _data(texto: object) -> dt.date | None:
    try:
        return dt.date.fromisoformat(str(texto))
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------- os portões


def portoes(registros: list[dict] | None) -> dict:
    """Os oito portões, quais estão provados, e a fase que sai disso.

    `fase` é `None` quando o livro não chegou, e NUNCA "achando": livro ausente
    é "não consegui olhar", e dizer "achando" ali seria afirmar o estado da
    escola inteira a partir de uma leitura que não aconteceu.
    """
    conhecidos = {chave for chave, _, _ in PORTOES}
    provas: dict[str, dict] = {}
    sem_prova: list[dict] = []
    desconhecidos: list[dict] = []
    if registros is not None:
        for r in registros:
            nome = r.get("portao")
            if not nome:
                continue
            ficha = {
                "arquivo": r.get("arquivo"),
                "portao": nome,
                "titulo": r.get("titulo"),
            }
            if nome not in conhecidos:
                desconhecidos.append(ficha)
            elif r.get("evidencia") and r.get("verificado_em"):
                provas.setdefault(
                    nome, {**ficha, "verificado_em": r.get("verificado_em")}
                )
            else:
                sem_prova.append(ficha)

    lista = [
        {
            "chave": chave,
            "nome": nome,
            "prova": prova,
            "provado": chave in provas,
            "registro": provas.get(chave),
        }
        for chave, nome, prova in PORTOES
    ]
    total = len(PORTOES)
    provados = len(provas) if registros is not None else None
    if provados is None:
        fase = None
    elif provados == 0:
        fase = FASE_SEM_NENHUM
    elif provados < total:
        fase = FASE_COM_ALGUNS
    else:
        fase = FASE_COM_TODOS
    return {
        "livro": registros is not None,
        "portoes": lista,
        "provados": provados,
        "total": total,
        "fase": fase,
        "declarados_sem_prova": sem_prova,
        "desconhecidos": desconhecidos,
    }


# --------------------------------------------- as medidas previram a meta?


def medidas_previram(direcao_da_semana: dict | None, resultado: dict | None) -> dict:
    """As duas medidas de direção acertaram o resultado do ciclo?

    Devolve `veredito` em uma destas palavras: `previram` · `nao-previram` ·
    `ainda-nao-da-para-saber`, mais `porque`, a frase que a tela mostra.

    **A palavra do meio existe por causa de `armadilhas/271`.** Nas semanas de
    aprender, a meta da semana é ZERO: bater uma meta de zero e ver o ciclo
    "ganhando" não prova que uma coisa previu a outra, prova que ninguém foi
    cobrado ainda. Chamar isso de "previram" seria a tela parabenizando quem
    não fez nada.
    """
    if resultado is None or resultado.get("veredito") in (None, "nao-consigo-contar"):
        return {
            "veredito": "ainda-nao-da-para-saber",
            "porque": "não consegui contar as compras do ciclo, então não há "
            "resultado com que comparar as medidas.",
        }
    if direcao_da_semana is None:
        return {
            "veredito": "ainda-nao-da-para-saber",
            "porque": "não consegui ler as duas medidas de direção da semana.",
        }
    pedidos = direcao_da_semana.get("pedidos") or {}
    liberacoes = direcao_da_semana.get("liberacoes") or {}
    meta_semanal = pedidos.get("meta")
    if pedidos.get("veredito") in (None, "nao-consigo-medir", "sem-meta"):
        return {
            "veredito": "ainda-nao-da-para-saber",
            "porque": "a medida das chegadas à sala de espera ainda não tem "
            "meta para ser cobrada.",
        }
    if not meta_semanal:
        return {
            "veredito": "ainda-nao-da-para-saber",
            "porque": "a meta destas semanas ainda é zero (são as semanas de "
            "aprender a campanha), e bater uma meta de zero não prevê coisa "
            "nenhuma.",
        }
    if liberacoes.get("veredito") in (None, "nao-consigo-medir", "sem-liberacoes"):
        return {
            "veredito": "ainda-nao-da-para-saber",
            "porque": "a medida das confirmações em 48 horas não teve o que "
            "medir nesta semana.",
        }
    medidas_em_dia = (
        pedidos.get("veredito") == "cumprida"
        and liberacoes.get("veredito") == "cumprida"
    )
    meta_em_dia = resultado["veredito"] in ("cumprida", "ganhando")
    if medidas_em_dia == meta_em_dia:
        return {
            "veredito": "previram",
            "porque": (
                "as duas medidas estavam em dia e o resultado acompanhou."
                if medidas_em_dia
                else "as medidas estavam abaixo e o resultado ficou abaixo junto."
            ),
        }
    return {
        "veredito": "nao-previram",
        "porque": (
            "as duas medidas estavam em dia e o resultado não veio: elas medem "
            "a coisa errada, ou medem a coisa certa cedo demais."
            if medidas_em_dia
            else "o resultado veio com as medidas abaixo: alguma coisa fora "
            "destas duas trouxe as pessoas."
        ),
    }


def veredito_do_ciclo(resultado: dict | None, estado: str) -> str | None:
    """A palavra que ESTA tela mostra sobre a meta. `None` sem resultado.

    É a palavra do placar, com UMA recusa: enquanto a curva ainda espera zero e
    a escola fez zero, não existe ganhando nem perdendo, e a resposta é
    `ainda-nao-cobra`.

    Isto não reescreve a régua (a conta continua sendo `placar.calcular_placar`,
    e o placar continua dizendo o que diz). É a tela do FECHAMENTO se recusando
    a repetir um elogio vazio: "ganhando" com 0 de 1000, porque a curva ainda
    pedia 0, é a tela parabenizando quem ainda não foi cobrado de nada
    (`armadilhas/271`). Esperado zero com compra acontecida continua sendo
    "ganhando", e aí é ganho de verdade: alguém comprou antes de ser pedido.
    """
    if resultado is None or resultado.get("veredito") is None:
        return None
    if (
        estado == "correndo"
        and resultado.get("esperado_hoje") == 0
        and resultado.get("x") == 0
    ):
        return "ainda-nao-cobra"
    return resultado["veredito"]


# ------------------------------------------------------------- o fechamento


def montar(
    *,
    meta: dict | None,
    resultado: dict | None,
    direcao_da_semana: dict | None,
    registros: list[dict] | None,
    hoje: dt.date,
) -> dict:
    """Tudo que a tela do fechamento mostra, sem rede e sem relógio próprio.

    `estado` em uma destas palavras: `sem-cartao` (não há régua, e sem ela não
    há ciclo), `correndo` (o ciclo está em pé, e este é o estado de hoje e dos
    próximos três meses), `terminou` (passou do dia de fechar).
    """
    ate = _data((meta or {}).get("ate"))
    partida_em = _data((meta or {}).get("partida_em"))
    if meta is None or ate is None:
        estado, dias_restantes, semanas_restantes = "sem-cartao", None, None
    elif hoje > ate:
        estado, dias_restantes, semanas_restantes = "terminou", 0, 0
    else:
        estado = "correndo"
        dias_restantes = (ate - hoje).days
        semanas_restantes = -(-dias_restantes // 7)
    return {
        "estado": estado,
        "meta": meta,
        "ate": ate,
        "partida_em": partida_em,
        "dias_restantes": dias_restantes,
        "semanas_restantes": semanas_restantes,
        "resultado": resultado,
        "veredito": veredito_do_ciclo(resultado, estado),
        "previsao": medidas_previram(direcao_da_semana, resultado),
        "fase": portoes(registros),
    }


def montar_o_pedido(
    campos, dados: dict, hoje: dt.date
) -> tuple[str | None, list[dict]]:
    """`(pedido, faltando)`. O pedido é `None` enquanto faltar qualquer coisa.

    `faltando` traz uma ficha por campo, com `lei: True` no que é a lei do
    degrau, para a tela distinguir "o ciclo não fecha sem isto" de "preencha
    também isto".
    """
    valores = {chave: (campos.get(chave) or "").strip() for chave, _, _ in OBRIGATORIOS}
    faltando = [
        {
            "campo": chave,
            "rotulo": rotulo,
            "porque": porque,
            "lei": chave == OBRIGATORIOS[0][0],
        }
        for chave, rotulo, porque in OBRIGATORIOS
        if not valores[chave]
    ]
    alvo = None
    if valores["proximo_alvo"]:
        try:
            alvo = int(valores["proximo_alvo"])
        except ValueError:
            alvo = None
        if alvo is None or alvo <= 0:
            faltando.append(
                {
                    "campo": "proximo_alvo",
                    "rotulo": "o alvo do próximo ciclo",
                    "porque": "o alvo é um número de pessoas maior que zero, e "
                    f'"{valores["proximo_alvo"]}" não é.',
                    "lei": False,
                }
            )
            alvo = None
    proxima_ate = _data(valores["proxima_ate"]) if valores["proxima_ate"] else None
    if valores["proxima_ate"] and (proxima_ate is None or proxima_ate <= hoje):
        faltando.append(
            {
                "campo": "proxima_ate",
                "rotulo": "a data em que o próximo ciclo fecha",
                "porque": "a data se escreve como 2027-03-09 e tem de ser "
                f'depois de hoje; "{valores["proxima_ate"]}" não serve.',
                "lei": False,
            }
        )
    if faltando:
        return None, faltando

    resultado = dados.get("resultado") or {}
    fase = dados.get("fase") or {}
    linhas = [
        f"Fechamento do ciclo de 12 semanas do painel de gestão, {hoje.strftime('%d/%m/%Y')}.",
        "Lei: docs/decisoes/PLANO-PAINEL-DE-GESTAO.md, degrau 13.",
        "Registre no livro de ocorrências (painel/registros/), um registro por item,",
        "pelo rito de sempre (PR com o registro a bordo; molde em painel/LEIA-ME.md).",
        "",
    ]
    if dados.get("estado") != "terminou":
        linhas += [
            "ATENÇÃO, LEIA ANTES DE FAZER QUALQUER COISA: este ciclo AINDA NÃO",
            f"terminou (ele fecha em {dados['ate']}). Fechá-lo agora encerra o ciclo",
            "antes do prazo. Se isto aqui foi um ensaio, não escreva nada e avise",
            "o mantenedor.",
            "",
        ]
    linhas += [
        "- O QUE A ESCOLA PARA DE FAZER (tipo `decisao`, autoridade: mantenedor,",
        "  gravidade: info). É a peça obrigatória: sem ela o ciclo não fecha.",
        f"  {valores['paramos_de_fazer']}",
        "",
        "- O RESULTADO DO CICLO (tipo `medicao`, autoridade: sessao, evidencia: o",
        f"  link do PR, verificado_em: {hoje.isoformat()}).",
        f"  Meta: {resultado.get('alvo')} pessoas até {resultado.get('ate')}."
        f" Medido: {resultado.get('x')}. Veredito: {dados.get('veredito')}.",
        f"  As medidas de direção: {dados['previsao']['veredito']},"
        f" porque {dados['previsao']['porque']}",
    ]
    por_que = (campos.get("por_que") or "").strip()
    if por_que:
        linhas += [f"  Por quê, nas palavras do mantenedor: {por_que}"]
    linhas += [
        "",
        "- A META SEGUINTE (tipo `decisao`, autoridade: mantenedor), e a gravação",
        f"  dela em {CARTAO_DA_META_NO_REPOSITORIO}, no mesmo PR:",
        f"  alvo {alvo} pessoas, partida no total de hoje, ate: {valores['proxima_ate']}.",
        "  Remonte a curva de `semanas` junto: a soma dos alvos semanais tem de dar",
        "  exatamente `alvo` menos `partida`, e o validador do cartão reprova se não der.",
        "  Suba a `versao` do cartão e escreva o porquê da curva no campo `_por_que`.",
        "",
        f"- A FASE DA ESCOLA hoje é \"{fase.get('fase')}\","
        f" com {fase.get('provados')} de {fase.get('total')} portões provados.",
        "  Portão provado neste ciclo entra como registro com o campo `portao`",
        "  (um dos oito: " + ", ".join(chave for chave, _, _ in PORTOES) + "),",
        "  mais `evidencia` e `verificado_em`. Sem os dois, ele não conta.",
    ]
    return "\n".join(linhas), []


@require_http_methods(["GET", "POST"])
def fechamento(request):
    """A tela. Fail-OPEN na rede, como o placar: ela abre e diz o que não viu."""
    hoje = timezone.localdate()
    contexto = montar_o_placar(hoje, site_de(request))
    dados = montar(
        meta=contexto["meta"],
        resultado=contexto["placar"],
        direcao_da_semana=contexto["direcao"],
        registros=ler_registros(),
        hoje=hoje,
    )
    campos = request.POST if request.method == "POST" else {}
    pediram_o_analista = campos.get("acao") == analista_.ACAO
    fechar = request.method == "POST" and not pediram_o_analista
    pedido, faltando = montar_o_pedido(campos, dados, hoje) if fechar else (None, [])
    return render(
        request,
        "admin/fechamento.html",
        {
            "admin": request.admin,
            "recusas": contexto["recusas"],
            "fechamento": dados,
            "campos": campos,
            "montou": fechar,
            "pedido": pedido,
            "faltando": faltando,
            "hoje": hoje,
            "analista": analista_.para_a_tela(
                momento="fechamento",
                dossie=(
                    analista_.dossie_do_fechamento(dados, contexto, hoje)
                    if pediram_o_analista
                    else ""
                ),
                hoje=hoje,
                pediram=pediram_o_analista,
            ),
        },
    )
