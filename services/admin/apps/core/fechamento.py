"""Fechamento persistente dos ciclos do placar, com histórico no painel."""

from __future__ import annotations

import datetime as dt

from django.shortcuts import render
from django.db import transaction
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from . import analista as analista_
from .direcao import ler_registros
from .placar import montar_o_placar, site_de
from .models import CartaoDoPlacar, FechamentoDoCiclo, VersaoDoCartaoDoPlacar
from django.db.models import Max

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
    anterior = FechamentoDoCiclo.objects.filter(partida_em=dados.get("partida_em")).first() if dados.get("partida_em") else None
    campos = request.POST if request.method == "POST" else (anterior.dados if anterior else {})
    pediram_o_analista = campos.get("acao") == analista_.ACAO
    fechar = request.method == "POST" and not pediram_o_analista
    faltando = []
    encerrado = None
    if fechar and dados.get("estado") != "sem-cartao":
        partida = dados["partida_em"]
        proximo_alvo = (campos.get("proximo_alvo") or "").strip()
        proxima_ate = (campos.get("proxima_ate") or "").strip()
        alvo = None
        ate = None
        if proximo_alvo or proxima_ate:
            try:
                alvo = int(proximo_alvo)
            except ValueError:
                faltando.append({"rotulo": "alvo do próximo ciclo", "porque": "Digite um número inteiro.", "lei": False})
            ate = _data(proxima_ate)
            if alvo is not None and alvo <= 0:
                faltando.append({"rotulo": "alvo do próximo ciclo", "porque": "O alvo precisa ser positivo.", "lei": False})
            if ate is None or ate <= hoje:
                faltando.append({"rotulo": "data do próximo ciclo", "porque": "Escolha uma data futura.", "lei": False})
            if not proximo_alvo or not proxima_ate:
                faltando.append({"rotulo": "meta seguinte", "porque": "Preencha alvo e data juntos, ou deixe os dois vazios.", "lei": False})
            if (dados.get("resultado") or {}).get("x") is None:
                faltando.append({"rotulo": "valor de partida", "porque": "A contagem de compras precisa responder antes de iniciar uma nova meta.", "lei": False})
        if not faltando:
            foto = {
                "responsavel": (request.admin or {}).get("id") or (request.admin or {}).get("email"),
                "paramos_de_fazer": (campos.get("paramos_de_fazer") or "").strip(),
                "por_que": (campos.get("por_que") or "").strip(),
                "proximo_alvo": alvo,
                "proxima_ate": proxima_ate or None,
                "meta_anterior": contexto["meta"],
                "resultado": dados.get("resultado"),
                "veredito": dados.get("veredito"),
                "previsao": dados.get("previsao"),
                "fase": dados.get("fase", {}).get("fase"),
            }
            with transaction.atomic():
                encerrado, _ = FechamentoDoCiclo.objects.update_or_create(
                    partida_em=partida,
                    defaults={"encerrado_em": hoje, "dados": foto},
                )
                if alvo is not None and ate is not None:
                    linha = CartaoDoPlacar.objects.select_for_update().get(nome="compras-no-ciclo")
                    nova_meta = dict(linha.dados)
                    nova_meta.update({
                        "alvo": alvo, "ate": ate.isoformat(),
                        "partida": (dados.get("resultado") or {}).get("x"),
                        "partida_em": hoje.isoformat(),
                        "atualizado_por": (request.admin or {}).get("id") or (request.admin or {}).get("email"),
                        "versao": int(nova_meta.get("versao") or 0) + 1,
                        "desde": hoje.isoformat(),
                    })
                    nova_meta.pop("semanas", None)
                    linha.dados = nova_meta
                    linha.save(update_fields=["dados", "atualizado_em"])
                    revisao = (linha.versoes.aggregate(n=Max("revisao"))["n"] or 0) + 1
                    VersaoDoCartaoDoPlacar.objects.create(
                        cartao=linha, revisao=revisao, dados=nova_meta,
                        responsavel=(request.admin or {}).get("id") or (request.admin or {}).get("email") or "",
                    )
    historico = FechamentoDoCiclo.objects.order_by("-encerrado_em", "-id")
    return render(
        request,
        "admin/fechamento.html",
        {
            "admin": request.admin,
            "recusas": contexto["recusas"],
            "fechamento": dados,
            "campos": campos,
            "montou": fechar,
            "encerrado": encerrado,
            "historico": historico,
            "faltando": faltando,
            "hoje": hoje,
            "analista": analista_.para_a_tela(
                dossie=(
                    analista_.dossie_do_fechamento(dados, contexto, hoje)
                    if pediram_o_analista
                    else ""
                ),
                pediram=pediram_o_analista,
            ),
        },
    )



