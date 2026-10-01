"""O panorama semanal: o primeiro trabalho que o robô executa sozinho.

Plano-mestre §18.1. Quatro etapas, cada uma guardada em `estado` antes da
próxima, para que a retomada continue de onde parou:

1. **coletar** as tarefas, os compromissos e os objetivos da pessoa, cada
   fonte por si: a que falhar vira pendência e as outras seguem;
2. **montar** o documento com os números e as listas (sem modelo: é conta);
3. **ler**: o modelo forte (GPT-6 Sol) escreve a leitura da semana a partir
   dos dados coletados;
4. **entregar**: salva a entrega ligada à tarefa, comenta na tarefa e, se
   nada ficou pendente, conclui a tarefa.

Sem chave, sem teto ou com a conta recusando, a entrega sai PARCIAL (os
dados e as listas, sem a leitura), a pendência fica escrita nela e na
tarefa, e a execução espera. Quando a dependência volta, a MESMA entrega
ganha versão nova com a leitura.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from django.utils import timezone

from apps.core import equipe_operacoes as operacoes
from apps.core.models import Compromisso, MembroDaEquipe, Objetivo, Tarefa

from . import modelo
from .executor import batimento, guardar_estado, terminar
from .models import Entrega, Execucao

Situacao = Tarefa.Situacao
MAX_SAIDA = 3000
DADOS_VALEM = timedelta(hours=1)


# ---------------------------------------------------------------- 1. coletar


def _tarefa_em_dados(t: Tarefa) -> dict:
    return {
        "id": t.id,
        "titulo": t.titulo,
        "situacao": t.situacao,
        "prazo": t.prazo.isoformat() if t.prazo else None,
        "impedimento": t.impedimento or None,
        "objetivo": t.objetivo.titulo if t.objetivo else None,
        "objetivo_id": t.objetivo_id,
        "concluida_em": (
            timezone.localdate(t.concluida_em).isoformat() if t.concluida_em else None
        ),
        "executor": t.executor,
    }


def coletar(membro: MembroDaEquipe, segunda: date, sem_tarefa: int | None) -> dict:
    domingo = segunda + timedelta(days=6)
    dados: dict = {"falhas": []}
    try:
        tarefas = Tarefa.objects.select_related("objetivo").filter(responsavel=membro)
        if sem_tarefa:
            tarefas = tarefas.exclude(pk=sem_tarefa)
        abertas = tarefas.exclude(situacao=Situacao.CONCLUIDA)
        concluidas = tarefas.filter(
            situacao=Situacao.CONCLUIDA,
            concluida_em__date__gte=segunda,
            concluida_em__date__lte=domingo,
        )
        dados["tarefas_abertas"] = [_tarefa_em_dados(t) for t in abertas[:200]]
        dados["concluidas_na_semana"] = [_tarefa_em_dados(t) for t in concluidas[:200]]
    except Exception as erro:  # noqa: BLE001 - a fonte falha, o panorama segue
        dados["falhas"].append(f"Tarefas: não deu para ler ({type(erro).__name__}).")
    try:
        compromissos = Compromisso.objects.filter(
            semana=segunda, tarefa__responsavel=membro
        ).select_related("tarefa")
        dados["compromissos"] = [
            {
                "tarefa_id": c.tarefa_id,
                "titulo": c.tarefa.titulo,
                "cumprido": operacoes.cumprido(c.tarefa, domingo),
            }
            for c in compromissos
        ]
    except Exception as erro:  # noqa: BLE001
        dados["falhas"].append(f"Compromissos: não deu para ler ({type(erro).__name__}).")
    try:
        ids = {
            t["objetivo_id"]
            for t in dados.get("tarefas_abertas", []) + dados.get("concluidas_na_semana", [])
            if t.get("objetivo_id")
        }
        objetivos = Objetivo.objects.filter(pk__in=ids)
        dados["objetivos"] = [
            {
                "id": o.id,
                "titulo": o.titulo,
                "prazo": o.prazo.isoformat() if o.prazo else None,
                "ativo": o.ativo,
                "move": o.get_move_display() if o.move else None,
                "suas_abertas": sum(
                    1 for t in dados.get("tarefas_abertas", []) if t["objetivo_id"] == o.id
                ),
            }
            for o in objetivos
        ]
    except Exception as erro:  # noqa: BLE001
        dados["falhas"].append(f"Objetivos: não deu para ler ({type(erro).__name__}).")
    return dados


# ---------------------------------------------------------------- 2. montar


def _dia(iso: str | None) -> str:
    return date.fromisoformat(iso).strftime("%d/%m") if iso else "sem prazo"


def _linha(t: dict, extra: str = "") -> str:
    partes = [f"- **{t['titulo']}** (nº {t['id']}) — prazo {_dia(t['prazo'])}"]
    if t.get("objetivo"):
        partes.append(f" — objetivo: {t['objetivo']}")
    if extra:
        partes.append(f" — {extra}")
    return "".join(partes)


def montar(dados: dict, membro: MembroDaEquipe, robo_nome: str, segunda: date) -> str:
    hoje = operacoes.hoje()
    domingo = segunda + timedelta(days=6)
    abertas = dados.get("tarefas_abertas", [])
    concluidas = dados.get("concluidas_na_semana", [])
    compromissos = dados.get("compromissos", [])

    def prazo(t):
        return date.fromisoformat(t["prazo"]) if t["prazo"] else None

    atrasadas = [t for t in abertas if prazo(t) and prazo(t) < hoje]
    bloqueadas = [t for t in abertas if t["situacao"] == Situacao.BLOQUEADA]
    vencem = [
        t for t in abertas
        if prazo(t) and hoje <= prazo(t) <= domingo and t["situacao"] != Situacao.BLOQUEADA
    ]
    em_andamento = [
        t for t in abertas
        if t["situacao"] == Situacao.EM_ANDAMENTO and t not in atrasadas and t not in vencem
    ]
    a_fazer = [
        t for t in abertas
        if t["situacao"] == Situacao.A_FAZER and t not in atrasadas and t not in vencem
    ]
    cumpridos = sum(1 for c in compromissos if c["cumprido"])

    linhas = [
        f"# Panorama da semana — {membro.nome}",
        "",
        f"Semana de {segunda:%d/%m} a {domingo:%d/%m/%Y}. Montado pelo {robo_nome} "
        f"em {timezone.localtime():%d/%m/%Y às %H:%M}, com os dados do painel da equipe.",
        "",
        "## Resumo",
        "",
        f"- Tarefas abertas: **{len(abertas)}** "
        f"({sum(1 for t in abertas if t['situacao'] == Situacao.A_FAZER)} a fazer, "
        f"{sum(1 for t in abertas if t['situacao'] == Situacao.EM_ANDAMENTO)} em andamento, "
        f"{len(bloqueadas)} bloqueadas)",
        f"- Atrasadas: **{len(atrasadas)}**",
        f"- Vencem até domingo: **{len(vencem)}**",
        f"- Concluídas nesta semana: **{len(concluidas)}**",
        f"- Compromissos da semana: **{cumpridos} cumpridos de {len(compromissos)}**",
        "",
    ]

    def secao(titulo, lista, vazio, extra=lambda t: ""):
        linhas.extend([f"## {titulo}", ""])
        if lista:
            linhas.extend(_linha(t, extra(t)) for t in lista)
        else:
            linhas.append(vazio)
        linhas.append("")

    secao("Atrasadas", atrasadas, "Nenhuma tarefa atrasada.")
    secao(
        "Bloqueadas",
        bloqueadas,
        "Nenhuma tarefa bloqueada.",
        lambda t: f"impedimento: {t['impedimento']}" if t.get("impedimento") else "",
    )
    secao("Vencem até domingo", vencem, "Nada vence até domingo.")
    secao("Em andamento", em_andamento, "Nada mais em andamento.")
    secao("A fazer", a_fazer, "Nada mais na fila.")
    secao(
        "Concluídas nesta semana",
        concluidas,
        "Nada concluído nesta semana ainda.",
        lambda t: f"concluída em {_dia(t['concluida_em'])}",
    )

    linhas.extend(["## Compromissos da semana", ""])
    if compromissos:
        for c in compromissos:
            marca = "cumprido" if c["cumprido"] else "em aberto"
            linhas.append(f"- **{c['titulo']}** (nº {c['tarefa_id']}) — {marca}")
    else:
        linhas.append("Nenhuma tarefa assumida como compromisso nesta semana.")
    linhas.append("")

    linhas.extend(["## Objetivos ligados às suas tarefas", ""])
    objetivos = dados.get("objetivos", [])
    if objetivos:
        for o in objetivos:
            move = f" — move: {o['move']}" if o.get("move") else ""
            linhas.append(
                f"- **{o['titulo']}** — prazo {_dia(o['prazo'])}{move} — "
                f"suas tarefas abertas: {o['suas_abertas']}"
            )
    else:
        linhas.append("Nenhuma das suas tarefas aponta para um objetivo.")
    linhas.append("")
    return "\n".join(linhas)


# ---------------------------------------------------------------- 3. ler


INSTRUCOES_DA_LEITURA = (
    "Você é o robô pessoal de uma pessoa da equipe da Meshcraft, uma escola de "
    "modelagem 3D. Recebe em JSON as tarefas, os compromissos e os objetivos "
    "dela nesta semana. Escreva, em português do Brasil, a seção 'Leitura do "
    "robô' do panorama semanal: no máximo 250 palavras, em Markdown simples "
    "(parágrafos curtos e listas com '- '), sem título. Diga o que mais pede "
    "atenção (atrasos, bloqueios, compromissos em risco), sugira até três "
    "prioridades para os próximos dias citando as tarefas pelo título e pelo "
    "número, e aponte tarefas sem objetivo ou sem prazo se isso atrapalhar. "
    "Use só os dados recebidos; não invente tarefas, datas nem números."
)


def ler(execucao: Execucao, dados: dict, membro: MembroDaEquipe, segunda: date) -> str:
    conexao = modelo.conexao()
    execucao.modelo = conexao.modelo_forte
    Execucao.objects.filter(pk=execucao.pk).update(modelo=execucao.modelo)
    pedido = {
        "pessoa": membro.nome,
        "area": membro.area,
        "hoje": operacoes.hoje().isoformat(),
        "semana": segunda.isoformat(),
        "observacao_da_pessoa": execucao.pedido or None,
        **{k: v for k, v in dados.items() if k != "falhas"},
    }
    resposta = modelo.responder(
        modelo=execucao.modelo,
        instrucoes=INSTRUCOES_DA_LEITURA,
        itens=[{"role": "user", "content": json.dumps(pedido, ensure_ascii=False)}],
        max_saida=MAX_SAIDA,
        execucao=execucao,
        robo=execucao.robo,
    )
    return resposta.texto.strip()


# ---------------------------------------------------------------- 4. entregar


def _conteudo(estado: dict) -> str:
    partes = [estado["documento"].rstrip(), "", "## Leitura do robô", ""]
    if estado.get("leitura"):
        partes.append(estado["leitura"])
    else:
        partes.append("Ainda não feita: veja as pendências abaixo.")
    pendencias = estado.get("pendencias") or []
    if pendencias:
        partes.extend(["", "## Pendências", ""])
        partes.extend(f"- {p}" for p in pendencias)
    return "\n".join(partes) + "\n"


def entregar(execucao: Execucao, membro: MembroDaEquipe) -> Entrega:
    estado = execucao.estado
    pendencias = estado.get("pendencias") or []
    segunda = date.fromisoformat(estado["semana"])
    titulo = f"Panorama da semana de {segunda:%d/%m} — {membro.nome}"[:200]
    entrega = Entrega.objects.filter(pk=estado.get("entrega_id")).first()
    if entrega is None:
        entrega = Entrega.objects.create(
            robo=execucao.robo,
            execucao=execucao,
            tarefa_id=execucao.tarefa_id,
            tipo="panorama_semanal",
            titulo=titulo,
            conteudo=_conteudo(estado),
            parcial=bool(pendencias),
            pendencias=pendencias,
        )
        estado["entrega_id"] = entrega.id
        guardar_estado(execucao)
    elif entrega.conteudo != _conteudo(estado) or entrega.parcial != bool(pendencias):
        entrega.conteudo = _conteudo(estado)
        entrega.parcial = bool(pendencias)
        entrega.pendencias = pendencias
        entrega.versao += 1
        entrega.save()
    return entrega


def _comentar_uma_vez(execucao: Execucao, membro, entrega: Entrega, texto: str) -> None:
    marca = f"{entrega.id}:{entrega.versao}:{entrega.parcial}"
    if execucao.estado.get("comentado") == marca or not execucao.tarefa_id:
        return
    tarefa = Tarefa.objects.filter(pk=execucao.tarefa_id).first()
    if tarefa is None:
        return
    quem = f"{execucao.robo.nome} (a pedido de {membro.nome})"
    operacoes.comentar(tarefa, texto[:500], quem, None)
    execucao.estado["comentado"] = marca
    guardar_estado(execucao)


def executar(execucao: Execucao) -> None:
    robo = execucao.robo
    membro = MembroDaEquipe.objects.get(pk=execucao.pedido_por_membro_id or robo.membro_id)
    if not membro.ativo:
        terminar(execucao, Execucao.Situacao.CANCELADA, "A pessoa não está mais ativa na equipe.")
        return
    estado = execucao.estado
    segunda = date.fromisoformat(estado.get("semana") or operacoes.segunda(operacoes.hoje()).isoformat())
    estado["semana"] = segunda.isoformat()

    coletado_em = estado.get("coletado_em")
    if coletado_em and timezone.now() - datetime.fromisoformat(coletado_em) > DADOS_VALEM:
        # Retomada muito depois (a chave chegou no dia seguinte): os dados
        # guardados envelheceram, e o panorama é da semana de AGORA.
        estado.pop("dados", None)
        estado.pop("documento", None)

    if "dados" not in estado:
        batimento(execucao, "Consultando tarefas, compromissos e objetivos", progresso=15)
        estado["dados"] = coletar(membro, segunda, execucao.tarefa_id)
        estado["coletado_em"] = timezone.now().isoformat()
        guardar_estado(execucao)

    if "documento" not in estado:
        batimento(execucao, "Montando o documento", progresso=35)
        estado["documento"] = montar(estado["dados"], membro, robo.nome, segunda)
        guardar_estado(execucao)

    pendencias = list(estado["dados"].get("falhas") or [])
    espera = None
    if not estado.get("leitura"):
        batimento(execucao, "Escrevendo a leitura da semana com o modelo", progresso=55)
        try:
            estado["leitura"] = ler(execucao, estado["dados"], membro, segunda)
        except modelo.Temporario:
            raise
        except modelo.ProblemaDoModelo as problema:
            espera = problema
            pendencias.append("Leitura do robô: " + problema.frase)
        guardar_estado(execucao)
    estado["pendencias"] = pendencias

    batimento(execucao, "Salvando a entrega", progresso=85)
    entrega = entregar(execucao, membro)

    if espera is not None:
        _comentar_uma_vez(
            execucao,
            membro,
            entrega,
            f"Entrega parcial salva: «{entrega.titulo}» (nº {entrega.id}). Falta a "
            f"leitura do robô: {espera.frase}",
        )
        terminar(execucao, espera.situacao, espera.frase, resultado=f"Entrega parcial nº {entrega.id}.")
        return

    _comentar_uma_vez(
        execucao,
        membro,
        entrega,
        f"Entrega pronta: «{entrega.titulo}» (nº {entrega.id}). Abra na seção Robô "
        "desta ficha ou na página do robô."
        + (" Ficaram pendências escritas na entrega." if pendencias else ""),
    )
    if execucao.tarefa_id and not pendencias:
        tarefa = Tarefa.objects.filter(pk=execucao.tarefa_id).first()
        if tarefa is not None and tarefa.situacao != Situacao.CONCLUIDA:
            operacoes.mudar_situacao(
                tarefa,
                Situacao.CONCLUIDA,
                "",
                f"{robo.nome} (a pedido de {membro.nome})",
            )
    terminar(
        execucao,
        Execucao.Situacao.CONCLUIDA,
        resultado=f"Entrega nº {entrega.id}" + (" com pendências." if pendencias else "."),
    )
