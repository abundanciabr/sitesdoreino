"""As ações do robô: consultar e operar o painel da equipe, delegar e entregar.

Toda ação que muda alguma coisa passa pelas MESMAS funções do painel
(`apps.core.equipe_operacoes`): o robô não tem regra própria de tarefa.

Cada ação roda com a identidade de quem é dono do robô: confere, na hora, que
a pessoa continua ativa e que o robô não está pausado. O rastro na tarefa diz
"Robô de Fulana (a pedido de Fulana)".

## Pedido repetido

Cada pedido do modelo tem um `call_id`. A ação e o registro dela
(`ChamadaDeFerramenta`) são gravados na MESMA transação: ou os dois ficaram,
ou nenhum. Numa retomada, o mesmo `call_id` acha o registro e devolve o
resultado guardado, sem fazer a ação duas vezes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from apps.core import equipe_operacoes as operacoes
from apps.core.models import Compromisso, MembroDaEquipe, Objetivo, Tarefa

from .models import ChamadaDeFerramenta, Entrega, Execucao, RoboPessoal

Situacao = Tarefa.Situacao


@dataclass
class Contexto:
    robo: RoboPessoal
    membro: MembroDaEquipe
    execucao: Execucao

    @property
    def quem(self) -> str:
        return f"{self.robo.nome} (a pedido de {self.membro.nome})"[:200]


class Recusa(Exception):
    """A ação não pode ser feita; a frase volta para o modelo explicar."""


def _texto_ou_nulo(descricao: str) -> dict:
    return {"type": ["string", "null"], "description": descricao}


def _inteiro_ou_nulo(descricao: str) -> dict:
    return {"type": ["integer", "null"], "description": descricao}


def _ferramenta(nome: str, descricao: str, propriedades: dict) -> dict:
    return {
        "type": "function",
        "name": nome,
        "description": descricao,
        "parameters": {
            "type": "object",
            "properties": propriedades,
            "required": list(propriedades),
            "additionalProperties": False,
        },
        "strict": True,
    }


SITUACOES = list(Situacao.values)

DEFINICOES = [
    _ferramenta(
        "consultar_membros",
        "Lista as pessoas ativas da equipe, com número, nome e área. Elas "
        "já vêm no retrato do painel: só chame se o retrato não estiver lá.",
        {},
    ),
    _ferramenta(
        "consultar_objetivos",
        "Lista os objetivos da equipe, com quantas tarefas abertas cada um tem. "
        "Os ativos já vêm no retrato do painel: chame para os inativos ou a descrição.",
        {"incluir_inativos": {"type": "boolean"}},
    ),
    _ferramenta(
        "consultar_tarefas",
        "Procura tarefas do painel da equipe. As tarefas abertas de quem fala "
        "com você já vêm no retrato do painel: não chame para elas. Chame para "
        "outra pessoa, toda a equipe, tarefas concluídas ou uma busca por texto.",
        {
            "responsavel_id": _inteiro_ou_nulo(
                "Número da pessoa responsável; nulo para a pessoa que fala com você."
            ),
            "toda_a_equipe": {
                "type": "boolean",
                "description": "Verdadeiro para não filtrar por pessoa.",
            },
            "situacao": {
                "type": ["string", "null"],
                "enum": SITUACOES + [None],
                "description": "Filtra pela situação; nulo traz as abertas.",
            },
            "objetivo_id": _inteiro_ou_nulo("Filtra pelo objetivo."),
            "texto": _texto_ou_nulo("Parte do título para procurar."),
        },
    ),
    _ferramenta(
        "consultar_tarefa",
        "Abre uma tarefa: descrição, comentários, compromisso e trabalhos do robô.",
        {"tarefa_id": {"type": "integer"}},
    ),
    _ferramenta(
        "consultar_compromissos",
        "Os compromissos de uma semana, por pessoa, cumpridos e não cumpridos.",
        {
            "semana": _texto_ou_nulo(
                "Uma data AAAA-MM-DD da semana; nulo para a semana atual."
            ),
            "responsavel_id": _inteiro_ou_nulo("Só os de uma pessoa."),
        },
    ),
    _ferramenta(
        "criar_tarefa",
        "Cria uma tarefa no painel da equipe, como o formulário do painel.",
        {
            "titulo": {"type": "string"},
            "descricao": _texto_ou_nulo("Descrição."),
            "responsavel_id": _inteiro_ou_nulo(
                "Quem responde; nulo para ninguém. Use o número de consultar_membros."
            ),
            "objetivo_id": _inteiro_ou_nulo("Objetivo; nulo para nenhum."),
            "prazo": _texto_ou_nulo("Data AAAA-MM-DD; nulo para sem prazo."),
            "situacao": {
                "type": ["string", "null"],
                "enum": SITUACOES + [None],
                "description": "Nulo para a_fazer.",
            },
            "impedimento": _texto_ou_nulo("Obrigatório se a situação for bloqueada."),
        },
    ),
    _ferramenta(
        "alterar_tarefa",
        "Altera só os campos informados de uma tarefa. Campos nulos ficam "
        "como estão. Passe a versão lida em consultar_tarefa para não "
        "escrever por cima de uma mudança de outra pessoa.",
        {
            "tarefa_id": {"type": "integer"},
            "versao": _texto_ou_nulo("A versão lida da tarefa."),
            "titulo": _texto_ou_nulo("Novo título."),
            "descricao": _texto_ou_nulo("Nova descrição."),
            "responsavel_id": _inteiro_ou_nulo("Novo responsável; 0 tira o responsável."),
            "objetivo_id": _inteiro_ou_nulo("Novo objetivo; 0 tira o objetivo."),
            "prazo": _texto_ou_nulo("Novo prazo AAAA-MM-DD; 'sem' tira o prazo."),
            "situacao": {
                "type": ["string", "null"],
                "enum": SITUACOES + [None],
            },
            "impedimento": _texto_ou_nulo("Impedimento, se bloquear."),
        },
    ),
    _ferramenta(
        "mudar_situacao_da_tarefa",
        "Muda a situação de uma tarefa, como o controle do cartão no painel.",
        {
            "tarefa_id": {"type": "integer"},
            "situacao": {"type": "string", "enum": SITUACOES},
            "impedimento": _texto_ou_nulo("Obrigatório para bloqueada."),
        },
    ),
    _ferramenta(
        "comentar_tarefa",
        "Publica um comentário curto (até 500 letras) na ficha da tarefa.",
        {"tarefa_id": {"type": "integer"}, "texto": {"type": "string"}},
    ),
    _ferramenta(
        "marcar_compromisso",
        "Assume a tarefa como compromisso da semana atual, ou tira. Só "
        "vale para tarefa de que a própria pessoa é responsável.",
        {"tarefa_id": {"type": "integer"}, "tirar": {"type": "boolean"}},
    ),
    _ferramenta(
        "delegar_panorama_semanal",
        "Pede ao robô que EXECUTE o panorama semanal no servidor: junta as "
        "tarefas, objetivos e compromissos da pessoa e salva um documento "
        "ligado a uma tarefa. Use só quando a pessoa pedir que o trabalho "
        "seja feito, não quando pedir para criar uma tarefa.",
        {"observacao": _texto_ou_nulo("O que a pessoa pediu de especial.")},
    ),
    _ferramenta(
        "consultar_trabalhos_do_robo",
        "Os trabalhos recentes deste robô: situação, etapa, motivo da espera e entregas.",
        {},
    ),
    _ferramenta(
        "salvar_entrega",
        "Salva no site um documento que você escreveu (texto em Markdown), "
        "opcionalmente ligado a uma tarefa. A pessoa abre pela página do robô.",
        {
            "titulo": {"type": "string"},
            "conteudo": {"type": "string"},
            "tarefa_id": _inteiro_ou_nulo("A tarefa a que a entrega pertence."),
        },
    ),
]

ESCREVEM = {
    "criar_tarefa",
    "alterar_tarefa",
    "mudar_situacao_da_tarefa",
    "comentar_tarefa",
    "marcar_compromisso",
    "delegar_panorama_semanal",
    "salvar_entrega",
}


# ---------------------------------------------------------------- leitura


def _resumo(tarefa: Tarefa, hoje: date, compromissos: set[int]) -> dict:
    aberta = tarefa.situacao != Situacao.CONCLUIDA
    return {
        "id": tarefa.id,
        "titulo": tarefa.titulo,
        "responsavel": tarefa.responsavel.nome if tarefa.responsavel else None,
        "responsavel_id": tarefa.responsavel_id,
        "objetivo": tarefa.objetivo.titulo if tarefa.objetivo else None,
        "objetivo_id": tarefa.objetivo_id,
        "prazo": tarefa.prazo.isoformat() if tarefa.prazo else None,
        "atrasada": bool(tarefa.prazo and aberta and tarefa.prazo < hoje),
        "situacao": tarefa.situacao,
        "impedimento": tarefa.impedimento or None,
        "executor": tarefa.executor,
        "compromisso_desta_semana": tarefa.id in compromissos,
        "versao": operacoes.versao_de(tarefa),
    }


def _compromissos_da_semana() -> set[int]:
    return set(
        Compromisso.objects.filter(semana=operacoes.segunda(operacoes.hoje())).values_list(
            "tarefa_id", flat=True
        )
    )


RETRATO_MAX_TAREFAS = 40


def retrato(membro: MembroDaEquipe) -> dict:
    """O painel como está quando a mensagem chega: as pessoas, os objetivos
    ativos e as tarefas abertas da pessoa. Vai junto com as instruções, e o
    robô responde as perguntas comuns sem gastar uma rodada só para consultar."""
    hoje = operacoes.hoje()
    compromissos = _compromissos_da_semana()
    abertas = (
        Tarefa.objects.select_related("responsavel", "objetivo")
        .filter(responsavel=membro)
        .exclude(situacao=Situacao.CONCLUIDA)
        .order_by(F("prazo").asc(nulls_last=True), "-criada_em")
    )
    tarefas = []
    for tarefa in abertas[:RETRATO_MAX_TAREFAS]:
        resumo = _resumo(tarefa, hoje, compromissos)
        # São todas da pessoa: o responsável não precisa vir em cada uma.
        del resumo["responsavel"], resumo["responsavel_id"]
        tarefas.append(resumo)
    return {
        "pessoas": [
            {"id": m.id, "nome": m.nome, "area": m.area, "e_voce": m.id == membro.id}
            for m in operacoes.membros_ativos()
        ],
        "objetivos_ativos": [
            {"id": o.id, "titulo": o.titulo, "prazo": o.prazo.isoformat() if o.prazo else None}
            for o in Objetivo.objects.filter(ativo=True)
        ],
        "suas_tarefas_abertas": {
            "total": abertas.count(),
            "atrasadas": abertas.filter(prazo__lt=hoje).count(),
            "listadas": len(tarefas),
            "tarefas": tarefas,
        },
    }


def consultar_membros(ctx: Contexto, args: dict) -> dict:
    return {
        "membros": [
            {"id": m.id, "nome": m.nome, "area": m.area, "e_voce": m.id == ctx.membro.id}
            for m in operacoes.membros_ativos()
        ]
    }


def consultar_objetivos(ctx: Contexto, args: dict) -> dict:
    objetivos = Objetivo.objects.all()
    if not args.get("incluir_inativos"):
        objetivos = objetivos.filter(ativo=True)
    saida = []
    for o in objetivos:
        saida.append(
            {
                "id": o.id,
                "titulo": o.titulo,
                "descricao": o.descricao[:500],
                "prazo": o.prazo.isoformat() if o.prazo else None,
                "ativo": o.ativo,
                "move": o.get_move_display() if o.move else None,
                "tarefas_abertas": o.tarefas.exclude(situacao=Situacao.CONCLUIDA).count(),
            }
        )
    return {"objetivos": saida}


def consultar_tarefas(ctx: Contexto, args: dict) -> dict:
    tarefas = Tarefa.objects.select_related("responsavel", "objetivo")
    if not args.get("toda_a_equipe"):
        tarefas = tarefas.filter(responsavel_id=args.get("responsavel_id") or ctx.membro.id)
    if args.get("situacao"):
        tarefas = tarefas.filter(situacao=args["situacao"])
    else:
        tarefas = tarefas.exclude(situacao=Situacao.CONCLUIDA)
    if args.get("objetivo_id"):
        tarefas = tarefas.filter(objetivo_id=args["objetivo_id"])
    if args.get("texto"):
        tarefas = tarefas.filter(titulo__icontains=args["texto"])
    hoje = operacoes.hoje()
    compromissos = _compromissos_da_semana()
    lista = [_resumo(t, hoje, compromissos) for t in tarefas[:80]]
    return {"total": len(lista), "tarefas": lista}


def consultar_tarefa(ctx: Contexto, args: dict) -> dict:
    tarefa = (
        Tarefa.objects.select_related("responsavel", "objetivo")
        .filter(pk=args.get("tarefa_id"))
        .first()
    )
    if tarefa is None:
        raise Recusa("Não achei essa tarefa.")
    dados = _resumo(tarefa, operacoes.hoje(), _compromissos_da_semana())
    dados["descricao"] = tarefa.descricao
    dados["criada_por"] = tarefa.criada_por
    dados["alterada_por"] = tarefa.alterada_por
    dados["comentarios"] = [
        {"autor": c.autor, "texto": c.texto, "em": c.criado_em.isoformat()}
        for c in tarefa.comentarios.order_by("-criado_em")[:10]
    ]
    dados["trabalhos_do_robo"] = [
        {"id": e.id, "tipo": e.get_tipo_display(), "situacao": e.get_situacao_display()}
        for e in Execucao.objects.filter(tarefa_id=tarefa.id)[:5]
    ]
    return {"tarefa": dados}


def consultar_compromissos(ctx: Contexto, args: dict) -> dict:
    pedida, erro = operacoes.ler_prazo(args.get("semana") or "")
    if erro:
        raise Recusa("A semana precisa ser uma data AAAA-MM-DD.")
    corrente = operacoes.segunda(operacoes.hoje())
    segunda = min(operacoes.segunda(pedida), corrente) if pedida else corrente
    domingo = segunda + timedelta(days=6)
    compromissos = Compromisso.objects.filter(semana=segunda).select_related(
        "tarefa", "tarefa__responsavel"
    )
    if args.get("responsavel_id"):
        compromissos = compromissos.filter(tarefa__responsavel_id=args["responsavel_id"])
    saida = [
        {
            "tarefa_id": c.tarefa_id,
            "titulo": c.tarefa.titulo,
            "responsavel": c.tarefa.responsavel.nome if c.tarefa.responsavel else None,
            "cumprido": operacoes.cumprido(c.tarefa, domingo),
            "situacao": c.tarefa.situacao,
        }
        for c in compromissos
    ]
    return {
        "semana": segunda.isoformat(),
        "domingo": domingo.isoformat(),
        "compromissos": saida,
    }


def consultar_trabalhos_do_robo(ctx: Contexto, args: dict) -> dict:
    saida = []
    for e in ctx.robo.execucoes.exclude(tipo=Execucao.Tipo.CONVERSA)[:10]:
        saida.append(
            {
                "id": e.id,
                "tipo": e.get_tipo_display(),
                "situacao": e.get_situacao_display(),
                "etapa": e.etapa_atual,
                "motivo": e.motivo or None,
                "tarefa_id": e.tarefa_id,
                "entregas": [
                    {"id": en.id, "titulo": en.titulo, "parcial": en.parcial}
                    for en in e.entregas.all()
                ],
            }
        )
    return {"trabalhos": saida}


# ---------------------------------------------------------------- escrita


def _id_ou_vazio(valor) -> str:
    return str(valor) if valor else ""


def criar_tarefa(ctx: Contexto, args: dict) -> dict:
    tarefa, erros = operacoes.criar_tarefa(
        {
            "titulo": args.get("titulo"),
            "descricao": args.get("descricao"),
            "responsavel": _id_ou_vazio(args.get("responsavel_id")),
            "objetivo": _id_ou_vazio(args.get("objetivo_id")),
            "prazo": args.get("prazo"),
            "situacao": args.get("situacao"),
            "impedimento": args.get("impedimento"),
        },
        ctx.quem,
    )
    if erros:
        raise Recusa(" ".join(erros))
    return {
        "criada": True,
        "tarefa": _resumo(tarefa, operacoes.hoje(), _compromissos_da_semana()),
    }


def alterar_tarefa(ctx: Contexto, args: dict) -> dict:
    mudancas = {}
    for campo in ("titulo", "descricao", "situacao", "impedimento"):
        if args.get(campo) is not None:
            mudancas[campo] = args[campo]
    if args.get("responsavel_id") is not None:
        mudancas["responsavel"] = _id_ou_vazio(args["responsavel_id"])
    if args.get("objetivo_id") is not None:
        mudancas["objetivo"] = _id_ou_vazio(args["objetivo_id"])
    if args.get("prazo") is not None:
        mudancas["prazo"] = "" if args["prazo"] == "sem" else args["prazo"]
    if not mudancas:
        raise Recusa("Nenhum campo para mudar.")
    try:
        tarefa, erros = operacoes.alterar_tarefa(
            int(args["tarefa_id"]), mudancas, ctx.quem, versao=args.get("versao") or ""
        )
    except operacoes.TarefaMudou:
        raise Recusa(
            "A tarefa mudou desde que você a leu (outra pessoa alterou). "
            "Consulte de novo antes de alterar."
        )
    if erros:
        raise Recusa(" ".join(erros))
    return {
        "alterada": True,
        "tarefa": _resumo(tarefa, operacoes.hoje(), _compromissos_da_semana()),
    }


def _tarefa(args: dict) -> Tarefa:
    tarefa = Tarefa.objects.filter(pk=args.get("tarefa_id")).first()
    if tarefa is None:
        raise Recusa("Não achei essa tarefa.")
    return tarefa


FRASES = {
    "situacao": "Situação atualizada.",
    "concluida": "Tarefa concluída.",
    "reaberta": "Tarefa reaberta: voltou para A fazer.",
    "sem_impedimento": "Para bloquear uma tarefa, escreva o impedimento. Nada mudou.",
    "situacao_desconhecida": "Não conheço essa situação. Nada mudou.",
    "compromisso_marcado": "Tarefa assumida como compromisso desta semana.",
    "compromisso_tirado": "Tarefa tirada dos compromissos desta semana.",
    "compromisso_concluida": "Tarefa já concluída não vira compromisso. Nada mudou.",
    "compromisso_sem_responsavel": (
        "Compromisso é de alguém: a tarefa precisa de responsável. Nada mudou."
    ),
    "compromisso_de_outra_pessoa": (
        "O compromisso da semana é de quem responde pela tarefa: só essa "
        "pessoa assume ou tira. Nada mudou."
    ),
    "comentado": "Comentário publicado.",
    "comentario_vazio": "O comentário estava vazio. Nada foi publicado.",
    "comentario_longo": "O comentário passou de 500 letras. Nada foi publicado.",
}
CODIGOS_DE_RECUSA = {
    "sem_impedimento",
    "situacao_desconhecida",
    "compromisso_concluida",
    "compromisso_sem_responsavel",
    "compromisso_de_outra_pessoa",
    "comentario_vazio",
    "comentario_longo",
}


def _resultado_do_painel(codigo: str, tarefa: Tarefa) -> dict:
    if codigo in CODIGOS_DE_RECUSA:
        raise Recusa(FRASES[codigo])
    tarefa.refresh_from_db()
    return {
        "feito": FRASES.get(codigo, codigo),
        "tarefa": _resumo(tarefa, operacoes.hoje(), _compromissos_da_semana()),
    }


def mudar_situacao_da_tarefa(ctx: Contexto, args: dict) -> dict:
    tarefa = _tarefa(args)
    codigo = operacoes.mudar_situacao(
        tarefa, args.get("situacao") or "", args.get("impedimento") or "", ctx.quem
    )
    return _resultado_do_painel(codigo, tarefa)


def comentar_tarefa(ctx: Contexto, args: dict) -> dict:
    tarefa = _tarefa(args)
    # Sem `autor_membro`: a ficha mostra o nome da pessoa quando ele existe, e
    # o comentário é do robô (o texto do autor já diz a pedido de quem).
    codigo, _ = operacoes.comentar(tarefa, args.get("texto") or "", ctx.quem, None)
    return _resultado_do_painel(codigo, tarefa)


def marcar_compromisso(ctx: Contexto, args: dict) -> dict:
    tarefa = _tarefa(args)
    codigo = operacoes.marcar_compromisso(
        tarefa, ctx.quem, membro=ctx.membro, tirar=bool(args.get("tirar"))
    )
    return _resultado_do_painel(codigo, tarefa)


def delegar_panorama_semanal(ctx: Contexto, args: dict) -> dict:
    from .trabalhos import delegar_panorama

    execucao, nova = delegar_panorama(
        ctx.robo,
        ctx.membro,
        pedido_por=ctx.membro.nome,
        origem="conversa",
        observacao=args.get("observacao") or "",
    )
    return {
        "delegado": True,
        "ja_existia": not nova,
        "trabalho_id": execucao.id,
        "situacao": execucao.get_situacao_display(),
        "aviso": (
            "O panorama roda no servidor e continua mesmo com o navegador "
            "fechado. O andamento aparece na página do robô."
        ),
    }


def salvar_entrega(ctx: Contexto, args: dict) -> dict:
    titulo = (args.get("titulo") or "").strip()[:200]
    conteudo = (args.get("conteudo") or "").strip()
    if not titulo or not conteudo:
        raise Recusa("A entrega precisa de título e conteúdo.")
    tarefa_id = args.get("tarefa_id")
    if tarefa_id and not Tarefa.objects.filter(pk=tarefa_id).exists():
        raise Recusa("Não achei essa tarefa.")
    entrega = Entrega.objects.create(
        robo=ctx.robo,
        execucao=ctx.execucao,
        tarefa_id=tarefa_id or None,
        tipo="documento",
        titulo=titulo,
        conteudo=conteudo[:100_000],
    )
    if tarefa_id:
        operacoes.comentar(
            Tarefa.objects.get(pk=tarefa_id),
            f"Entrega do robô salva: «{titulo}» (nº {entrega.id}). Abra na seção "
            "Robô desta ficha.",
            ctx.quem,
            None,
        )
    return {"salva": True, "entrega_id": entrega.id, "titulo": titulo}


ACOES = {
    "consultar_membros": consultar_membros,
    "consultar_objetivos": consultar_objetivos,
    "consultar_tarefas": consultar_tarefas,
    "consultar_tarefa": consultar_tarefa,
    "consultar_compromissos": consultar_compromissos,
    "consultar_trabalhos_do_robo": consultar_trabalhos_do_robo,
    "criar_tarefa": criar_tarefa,
    "alterar_tarefa": alterar_tarefa,
    "mudar_situacao_da_tarefa": mudar_situacao_da_tarefa,
    "comentar_tarefa": comentar_tarefa,
    "marcar_compromisso": marcar_compromisso,
    "delegar_panorama_semanal": delegar_panorama_semanal,
    "salvar_entrega": salvar_entrega,
}


# Como cada ação aparece para a pessoa no passo a passo e na página da execução.
ROTULOS = {
    "consultar_membros": "consultar as pessoas da equipe",
    "consultar_objetivos": "consultar os objetivos",
    "consultar_tarefas": "consultar as tarefas",
    "consultar_tarefa": "abrir uma tarefa",
    "consultar_compromissos": "consultar os compromissos",
    "consultar_trabalhos_do_robo": "consultar os próprios trabalhos",
    "criar_tarefa": "criar uma tarefa",
    "alterar_tarefa": "alterar uma tarefa",
    "mudar_situacao_da_tarefa": "mudar a situação de uma tarefa",
    "comentar_tarefa": "comentar numa tarefa",
    "marcar_compromisso": "marcar ou tirar um compromisso da semana",
    "delegar_panorama_semanal": "delegar o panorama semanal",
    "salvar_entrega": "salvar uma entrega",
}


def _pode_agir(ctx: Contexto) -> str | None:
    """A identidade confere AGORA, não só quando o pedido foi feito."""
    membro = MembroDaEquipe.objects.filter(pk=ctx.membro.pk).first()
    if membro is None or not membro.ativo:
        return "A pessoa dona deste robô não está mais ativa na equipe."
    robo = RoboPessoal.objects.filter(pk=ctx.robo.pk).first()
    if robo is None or robo.situacao != RoboPessoal.Situacao.ATIVO:
        return "Este robô está pausado."
    return None


def executar(ctx: Contexto, call_id: str, nome: str, argumentos_crus: str) -> str:
    """Executa um pedido do modelo e devolve o resultado em JSON (texto)."""
    feita = ChamadaDeFerramenta.objects.filter(execucao=ctx.execucao, call_id=call_id).first()
    if feita is not None:
        return json.dumps(feita.resultado, ensure_ascii=False, default=str)

    try:
        argumentos = json.loads(argumentos_crus or "{}")
        if not isinstance(argumentos, dict):
            raise ValueError
    except ValueError:
        argumentos = {}
        resultado, situacao = {"erro": "Os argumentos não vieram em JSON."}, "recusada"
        return _registrar(ctx, call_id, nome, argumentos, resultado, situacao)

    acao = ACOES.get(nome)
    impedimento = _pode_agir(ctx)
    if acao is None:
        return _registrar(ctx, call_id, nome, argumentos, {"erro": "Ação desconhecida."}, "recusada")
    if impedimento:
        return _registrar(ctx, call_id, nome, argumentos, {"erro": impedimento}, "recusada")

    try:
        with transaction.atomic():
            resultado = acao(ctx, argumentos)
            return _registrar(ctx, call_id, nome, argumentos, resultado, "feita")
    except Recusa as recusa:
        return _registrar(ctx, call_id, nome, argumentos, {"erro": str(recusa)}, "recusada")
    except IntegrityError:
        # Outro trabalhador gravou o mesmo pedido ao mesmo tempo: vale o dele.
        feita = ChamadaDeFerramenta.objects.get(execucao=ctx.execucao, call_id=call_id)
        return json.dumps(feita.resultado, ensure_ascii=False, default=str)


def _registrar(ctx, call_id, nome, argumentos, resultado, situacao) -> str:
    resultado = json.loads(json.dumps(resultado, ensure_ascii=False, default=str))
    ChamadaDeFerramenta.objects.create(
        execucao=ctx.execucao,
        call_id=call_id[:120],
        nome=nome[:80],
        argumentos=argumentos,
        resultado=resultado,
        situacao=situacao,
        terminada_em=timezone.now(),
    )
    return json.dumps(resultado, ensure_ascii=False)
