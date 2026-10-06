"""Primeira leitura do negócio: fatos das portas existentes e trabalho da equipe.

O contexto devolvido contém apenas agregados. Ausência, falha e zero são estados
distintos; dados de teste nunca entram em receita presumida.
"""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from django.utils import timezone

from .clients import AlunosClient, CursosClient, MedicaoClient, PagamentosClient
from .models import Objetivo, Tarefa


def _estado(valor, *, fonte: str, periodo: str, motivo: str = "") -> dict:
    if valor is None:
        return {"estado": "indisponivel", "valor": None, "fonte": fonte,
                "periodo": periodo, "motivo": motivo or "A consulta não respondeu."}
    return {"estado": "zero" if valor == 0 else "medido", "valor": valor,
            "fonte": fonte, "periodo": periodo, "motivo": motivo}


def _pagamentos(site_id: str | None, hoje: dt.date, cliente=None) -> dict:
    """Receita somente quando cada cobrança aprovada prova ambiente de produção.

    A porta atual não fornece esse campo; a resposta honesta será indisponível.
    Lê todas as páginas para que uma página parcial não vire total do mês.
    """
    periodo = f"{hoje.replace(day=1):%d/%m/%Y} a {hoje:%d/%m/%Y}"
    fonte = "Pagamentos do próprio site (API interna de compras)"
    if not site_id:
        return _estado(None, fonte=fonte, periodo=periodo, motivo="Site não identificado.")
    cliente = cliente or PagamentosClient()
    compras = []
    pagina = 1
    while True:
        dados = cliente.compras_pagina(site_id, pagina)
        if (not isinstance(dados, dict) or dados.get("pagina") != pagina
                or not isinstance(dados.get("compras"), list)
                or type(dados.get("paginas")) is not int
                or dados["paginas"] < pagina):
            return _estado(None, fonte=fonte, periodo=periodo,
                           motivo="Consulta de compras falhou ou paginação incompleta.")
        compras.extend(dados["compras"])
        if not dados.get("mais"):
            break
        pagina += 1
        if pagina > dados["paginas"]:
            return _estado(None, fonte=fonte, periodo=periodo,
                           motivo="Paginação de compras inconsistente.")
    if len(compras) != dados.get("total"):
        return _estado(None, fonte=fonte, periodo=periodo,
                       motivo="Total de compras não confere com as páginas.")
    centavos = 0
    for compra in compras:
        if not isinstance(compra, dict):
            return _estado(None, fonte=fonte, periodo=periodo, motivo="Compra fora do contrato.")
        if compra.get("estado") != "approved" or compra.get("estorno"):
            continue
        try:
            instante = dt.datetime.fromisoformat(compra["data"])
            if instante.tzinfo is None:
                raise ValueError("data sem fuso")
            dia = instante.astimezone(ZoneInfo("America/Sao_Paulo")).date()
        except (KeyError, TypeError, ValueError):
            return _estado(None, fonte=fonte, periodo=periodo,
                           motivo="Compra aprovada sem data verificável.")
        if not hoje.replace(day=1) <= dia <= hoje:
            continue
        ambiente = compra.get("ambiente")
        if ambiente not in ("producao", "sandbox"):
            return _estado(None, fonte=fonte, periodo=periodo,
                           motivo="A lista de pagamentos não informa o ambiente das cobranças; não é seguro separar testes de receita real.")
        if ambiente == "sandbox":
            continue
        valor = compra.get("valor_centavos")
        if type(valor) is not int or valor < 0:
            return _estado(None, fonte=fonte, periodo=periodo,
                           motivo="Compra aprovada sem valor verificável.")
        centavos += valor
    resultado = _estado(centavos, fonte=fonte, periodo=periodo)
    inteiro = f"{centavos // 100:,}".replace(",", ".")
    resultado["reais"] = f"R$ {inteiro},{centavos % 100:02d}"
    return resultado


def _funil(site_id: str | None, hoje: dt.date, dias: int, cliente=None) -> dict:
    periodo = f"{hoje - dt.timedelta(days=dias - 1):%d/%m/%Y} a {hoje:%d/%m/%Y}"
    fonte = "Medição do site, visitantes distintos por etapa"
    if not site_id:
        return _estado(None, fonte=fonte, periodo=periodo, motivo="Site não identificado.")
    cliente = cliente or MedicaoClient()
    desfecho, dados = cliente.funil(hoje - dt.timedelta(days=dias - 1), hoje, site_id)
    if desfecho != cliente.OK or not isinstance(dados, dict):
        return _estado(None, fonte=fonte, periodo=periodo, motivo="Medição não respondeu.")
    if not dados.get("coleta", {}).get("primeiro"):
        return {**_estado(None, fonte=fonte, periodo=periodo,
                          motivo="Ainda não chegaram eventos nesta janela."), "estado": "sem_dados"}
    passos = dados.get("passos", {})
    if not isinstance(passos, dict):
        return _estado(None, fonte=fonte, periodo=periodo, motivo="Resposta fora do contrato.")
    return {"estado": "medido", "passos": passos, "fonte": fonte, "periodo": periodo,
            "limite": "Eventos do funil; pedido pago é evento, não receita financeira confirmada."}


def _alunos(cliente=None, site_id: str | None = None) -> dict:
    fonte = "Matrículas da célula Alunos"
    alunos = (cliente or AlunosClient()).alunos()
    if alunos is None:
        return _estado(None, fonte=fonte, periodo="posição atual",
                       motivo="A consulta de matrículas falhou.")
    if not isinstance(alunos, list) or any(not isinstance(a, dict) for a in alunos):
        return _estado(None, fonte=fonte, periodo="posição atual",
                       motivo="Resposta de matrículas fora do contrato.")
    escopo_site = bool(site_id and not alunos)
    if site_id and alunos:
        com_site = ["site_id" in a for a in alunos]
        if any(com_site) and not all(com_site):
            return _estado(None, fonte=fonte, periodo="posição atual",
                           motivo="Parte das matrículas veio sem identificação do site.")
        if all(com_site):
            alunos = [a for a in alunos if a["site_id"] == site_id]
            fonte += " deste site"
            escopo_site = True
    ativos = sum(a.get("status") == "ativa" for a in alunos)
    return {**_estado(ativos, fonte=fonte, periodo="posição atual"),
            "escopo": "site" if escopo_site else "plataforma",
            "limite": ("Inclui entradas por fontes externas. Matrícula não prova receita deste site."
                       if escopo_site else
                       "Todas as escolas da plataforma; inclui fontes externas. Matrícula não prova receita deste site.")}


def _cursos(site_id: str | None, cliente=None) -> dict:
    fonte = "Catálogo de cursos deste site"
    if not site_id:
        return _estado(None, fonte=fonte, periodo="posição atual", motivo="Site não identificado.")
    cliente = cliente or CursosClient()
    desfecho, cursos = cliente.cursos(site_id)
    if desfecho != cliente.OK or not isinstance(cursos, list):
        return _estado(None, fonte=fonte, periodo="posição atual", motivo="Consulta de cursos falhou.")
    return _estado(len(cursos), fonte=fonte, periodo="posição atual")


def _trabalho(hoje: dt.date) -> list[dict]:
    objetivos = list(Objetivo.objects.filter(ativo=True))
    tarefas = list(Tarefa.objects.exclude(situacao=Tarefa.Situacao.CONCLUIDA)
                   .select_related("responsavel", "objetivo"))
    saida = []
    for objetivo in [*objetivos, None]:
        ligadas = [t for t in tarefas if t.objetivo_id == (objetivo.id if objetivo else None)]
        if objetivo is None and not ligadas:
            continue
        bloqueadas = sum(t.situacao == Tarefa.Situacao.BLOQUEADA for t in ligadas)
        atrasadas = sum(bool(t.prazo and t.prazo < hoje) for t in ligadas)
        saida.append({"id": objetivo.id if objetivo else None,
                      "titulo": objetivo.titulo if objetivo else "Tarefas sem objetivo",
                      "prazo": objetivo.prazo if objetivo else None,
                      "move": objetivo.o_que_move_curto if objetivo else "",
                      "abertas": len(ligadas), "bloqueadas": bloqueadas,
                      "atrasadas": atrasadas, "prioridade": "Atenção agora" if bloqueadas or atrasadas else "Em andamento",
                      "responsaveis": sorted({t.responsavel.nome if t.responsavel else "Sem responsável" for t in ligadas}),
                      "tarefas": [{"id": t.id, "titulo": t.titulo,
                                   "responsavel": t.responsavel.nome if t.responsavel else "Sem responsável",
                                   "prazo": t.prazo, "situacao": t.get_situacao_display()} for t in ligadas[:5]]})
    return sorted(saida, key=lambda o: (-o["bloqueadas"], -o["atrasadas"], o["prazo"] or dt.date.max))


def montar_painel_negocio(site_id: str | None, hoje: dt.date | None = None) -> dict:
    """Contexto para incluir `admin/_painel_negocio.html` no placar existente."""
    hoje = hoje or timezone.localdate()
    return {"negocio": {"financeiro": _pagamentos(site_id, hoje),
                        "funis": [_funil(site_id, hoje, 7), _funil(site_id, hoje, 30)],
                        "alunos": _alunos(site_id=site_id), "cursos": _cursos(site_id),
                        "objetivos": _trabalho(hoje)}}


_MOTIVOS = {
    "custo-por-aluna": "Faltam custos de aquisição atribuídos e conciliação de vendas do site e das plataformas externas.",
    "custo-do-proximo-aluna": "Faltam custos incrementais de aquisição por campanha e matrículas atribuídas.",
    "dias-para-recuperar-o-custo": "Faltam custo de aquisição e receita líquida por coorte, incluindo Hotmart e Herospark.",
    "margem-mensal": "Faltam receitas confirmadas, taxas, impostos, reembolsos e custos variáveis do site, Hotmart e Herospark.",
    "margem-por-real-de-aquisicao": "Faltam margem por coorte e gasto de aquisição atribuível.",
    "primeira-acao-em-7-dias": "Atividades do site podem ser medidas; falta ligar o evento da primeira ação à coorte de matrícula. Atividades em Hotmart/Herospark precisam integração.",
    "alunos-com-resultado-profissional": "Falta registrar resultados profissionais comprovados por aluno, incluindo estudantes das plataformas externas.",
    "vindos-por-indicacao": "Falta atribuição confiável da indicação na matrícula, seja no site, Hotmart ou Herospark.",
}


def atualizar_explicacoes(contexto: dict) -> dict:
    """Projeta explicações atuais em cópias, sem alterar cartões nem histórico.

    Recebe o contexto já montado por `montar_o_placar` e devolve o mesmo
    contexto com referências visuais atualizadas. A medição numérica permanece
    sob responsabilidade das funções existentes.
    """
    contexto = dict(contexto)
    doze = []
    for item in contexto.get("doze") or []:
        item = dict(item)
        cartao = item.get("cartao")
        if isinstance(cartao, dict) and item.get("veredito") == "sem-fonte":
            cartao = dict(cartao)
            cartao["sem_fonte_porque"] = _MOTIVOS.get(item.get("nome"), cartao.get("sem_fonte_porque"))
            item["cartao"] = cartao
        doze.append(item)
    if contexto.get("doze") is not None:
        contexto["doze"] = doze
        contexto["estrelas"] = [i for i in doze if i.get("nome") in
                                ("margem-mensal", "alunos-com-resultado-profissional")]
    caminho = []
    for cartao in contexto.get("caminho_da_venda") or []:
        cartao = dict(cartao)
        if cartao.get("nome") == "visitas-na-pagina-de-venda-por-semana":
            cartao["sem_fonte_porque"] = "O funil da Medição já registra páginas vistas nos últimos 7 e 30 dias. Falta identificar a página de venda no evento para medir somente suas visitas; veja os números gerais abaixo."
        elif cartao.get("nome") == "compras-pelo-checkout-por-semana":
            cartao["sem_fonte_porque"] = "O funil registra pedidos pagos, e Pagamentos lista cobranças do site. Falta conciliar o evento com a cobrança de produção e excluir testes e estornos antes de contar compras confirmadas."
        caminho.append(cartao)
    contexto["caminho_da_venda"] = caminho
    par = contexto.get("par")
    if isinstance(par, dict) and par.get("fonte") is None:
        par = dict(par)
        par["sem_fonte_porque"] = ("Há registros de acesso no site, mas falta ligar cada acesso à matrícula e recortar os alunos ativos nos últimos 30 dias. "
                                   "Atividade em Hotmart e Herospark depende de integração própria.")
        contexto["par"] = par
    restricao = contexto.get("restricao")
    if isinstance(restricao, dict) and isinstance(restricao.get("etapas"), list):
        restricao = dict(restricao)
        etapas = []
        for etapa in restricao["etapas"]:
            etapa = dict(etapa)
            if not etapa.get("fonte"):
                etapa["sem_fonte_porque"] = "Há dados de funil e matrículas no site; esta etapa exige recorte e conciliação específicos. Hotmart e Herospark precisam integração própria."
            etapas.append(etapa)
        restricao["etapas"] = etapas
        contexto["restricao"] = restricao
    return contexto
