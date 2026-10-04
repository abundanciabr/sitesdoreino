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

from . import conhecimento_comercial
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
            "impedimento": _texto_ou_nulo(
                "Descrição opcional do que está bloqueando, se houver."
            ),
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
            "impedimento": _texto_ou_nulo(
                "Descrição opcional do que está bloqueando, se houver."
            ),
        },
    ),
    _ferramenta(
        "comentar_tarefa",
        "Publica um comentário curto (até 500 letras) na ficha da tarefa.",
        {"tarefa_id": {"type": "integer"}, "texto": {"type": "string"}},
    ),
    _ferramenta(
        "marcar_compromisso",
        "Assume a tarefa como compromisso da semana atual, ou tira. Vale "
        "para qualquer tarefa aberta que tenha responsável.",
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
        "consultar_conhecimento",
        "Anda pelo mapa de conhecimento: as coisas (pessoas, tarefas, objetivos, "
        "medidas do placar, cursos, ofertas, sistemas, decisões...) e as ligações "
        "entre elas, juntando o painel e os documentos do site, cada ligação com "
        "o trecho e a fonte. Use para perguntas que cruzam informações: quem "
        "cuida de quê, o que depende de quê, por que algo existe, como uma coisa "
        "afeta outra, o que os documentos dizem de um assunto.",
        {
            "termos": {
                "type": "array",
                "items": {"type": "string"},
                "description": "1 a 5 nomes ou palavras-chave curtas do assunto.",
            },
            "profundidade": {
                "type": "integer",
                "enum": [1, 2, 3],
                "description": "Quantos passos andar a partir do que achar; 2 serve quase sempre.",
            },
        },
    ),
    conhecimento_comercial.DEFINICAO,
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


# ---------------------------------------------------------------- quizzes
#
# Só para quem administra o site: as telas de quiz ficam atrás da porta do
# administrador, e o robô não abre para a pessoa o que ela não abriria.

FORMATOS_DO_QUIZ = ["text", "video", "hybrid", "calc", "ai"]
SLUG_DO_QUIZ = _texto_ou_nulo(
    "O quiz (slug). Nulo: o quiz da página de onde a pessoa escreveu."
)


def _escolha_de_links(com_campanha: bool = True) -> dict:
    propriedades = {
        "slug": SLUG_DO_QUIZ,
        "versoes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Versões, como B2. Vazia: todas as ativas.",
        },
        "formatos": {
            "type": "array",
            "items": {"type": "string", "enum": FORMATOS_DO_QUIZ},
            "description": (
                "text = Texto; video = Vídeo no topo (VSL); hybrid = Vídeo curto + "
                "texto; calc = Calculadora; ai = Conversa com IA. Vazia: todos."
            ),
        },
        "publicos": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Públicos (seg), como frio, quente, escalando, iniciante; 'geral' "
                "é o link sem público. Vazia: todos."
            ),
        },
    }
    if com_campanha:
        propriedades.update(
            {
                "origem": _texto_ou_nulo(
                    "Onde o anúncio roda (src): meta, tiktok, google, youtube, "
                    "email, whatsapp ou organico."
                ),
                "meio": _texto_ou_nulo(
                    "Tipo (med): cpc = anúncio pago, retargeting, organic ou email."
                ),
                "campanha": _texto_ou_nulo(
                    "Nome humano escolhido para a campanha, com espaços e acentos. "
                    "O sistema prepara o código do link. Nulo: o sistema sugere."
                ),
                "anuncios": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Identificadores dos anúncios (ctv), como vsl_47s. Cada "
                        "anúncio multiplica os links."
                    ),
                },
                "utm_term": _texto_ou_nulo("Termo (utm_term), opcional."),
            }
        )
    return propriedades


PERIODO = {
    "inicio": _texto_ou_nulo("Primeiro dia AAAA-MM-DD; nulo para o começo."),
    "fim": _texto_ou_nulo("Último dia AAAA-MM-DD; nulo para hoje."),
}

DEFINICOES_DO_QUIZ = [
    _ferramenta(
        "perguntar_com_opcoes",
        "Mostra UMA pergunta na conversa com um formulário clicável. Encerra esta "
        "resposta e espera a escolha da pessoa. Use radio para uma escolha, "
        "checkbox para várias, select para uma lista ou texto para resposta livre. "
        "Para nomes de campanha, ofereça 2 ou 3 sugestões e aceite outro nome.",
        {
            "pergunta": {"type": "string"},
            "tipo": {"type": "string", "enum": ["radio", "checkbox", "select", "texto"]},
            "opcoes": {"type": "array", "items": {"type": "string"}},
            "ajuda": _texto_ou_nulo("Uma explicação curta, se precisar."),
            "aceita_outro": {"type": "boolean"},
            "outro_rotulo": _texto_ou_nulo("Ex.: Prefiro informar outro nome."),
        },
    ),
    _ferramenta(
        "consultar_rascunho_do_quiz",
        "Lê as perguntas, formatos, resultados e ofertas do estúdio. Use antes "
        "de criar uma nova versão ou oferecer as ofertas existentes. Os endereços "
        "de pagamento ficam no servidor; não invente nem peça chaves.",
        {"slug": SLUG_DO_QUIZ},
    ),
    _ferramenta(
        "criar_rascunho_do_quiz",
        "Cria de verdade o quiz no estúdio do site com as respostas coletadas. "
        "modo novo cria outro quiz; nova_versao acrescenta uma versão preservando "
        "as existentes e suas ofertas. O documento segue quiz-low-ticket/2, com "
        "quiz {slug,title}, 2 ofertas {id,nome,para_quem,entrega,checkout_url:null} "
        "e uma versoes [{key,default_format,formats,segments,perguntas,faixas}]. "
        "Perguntas {id,texto,opcoes:[{id,texto,pontos}]}. Faixas "
        "{key,title,description,min_score,max_score,oferta_id,botao_rotulo} sem "
        "sobreposição e cobrindo todas as somas possíveis. formats.text contém "
        "headline e subheadline. IDs minúsculos com hífens, versão A ou B3. "
        "Salva o rascunho e devolve o botão para ver, testar e publicar no estúdio.",
        {
            "slug": SLUG_DO_QUIZ,
            "modo": {"type": "string", "enum": ["novo", "nova_versao"]},
            "usar_ofertas_do_quiz_atual": {"type": "boolean"},
            "documento_json": {"type": "string", "description": "Documento inteiro em JSON válido, com uma única versão nova."},
        },
    ),
    _ferramenta(
        "consultar_quiz",
        "A estrutura de um quiz do site: versões ativas, perguntas, pontos "
        "possíveis, faixas de pontuação, a oferta e a saída de cada faixa, "
        "formatos e públicos. O quiz da página já vem nas instruções. Com slug "
        "nulo fora da página de um quiz, lista os quizzes do site.",
        {"slug": SLUG_DO_QUIZ},
    ),
    _ferramenta(
        "montar_links_do_quiz",
        "Monta os links dos anúncios pelo próprio quiz (nunca escreva um link "
        "à mão), salva um kit com todos como entrega e devolve o endereço da "
        "página de links já preenchida, onde cada link tem Copiar e Testar.",
        _escolha_de_links(),
    ),
    _ferramenta(
        "delegar_conferencia_dos_links",
        "Pede ao robô que CONFIRA NO SITE os links antes de anunciar: abre cada "
        "versão, formato e público como um visitante (aberturas marcadas como "
        "teste), confere versão, título e vídeo, calcula que oferta cada "
        "pontuação mostra e se a origem da campanha chega inteira ao checkout. "
        "Roda no servidor, sem IA e sem custo; não envia formulário nem compra. "
        "Entrega um relatório com veredito e, se achar problema, cria a tarefa "
        "de correção.",
        {**_escolha_de_links(), "observacao": _texto_ou_nulo("O que a pessoa pediu de especial.")},
    ),
    _ferramenta(
        "consultar_numeros_do_quiz",
        "Os números de um quiz num período: visitas de verdade (testes ficam "
        "fora), quem chegou ao resultado e quem foi para a oferta, por versão, "
        "etapa por etapa, por campanha e por dia, os gargalos e o que falta "
        "medir. Para perguntas rápidas; a leitura completa é delegar_leitura_do_quiz.",
        {"slug": SLUG_DO_QUIZ, **PERIODO},
    ),
    _ferramenta(
        "delegar_leitura_do_quiz",
        "Pede ao robô que EXECUTE no servidor a leitura completa dos números "
        "com o modelo forte: um documento com as tabelas, a leitura, até cinco "
        "ações com a evidência de cada uma e propostas de nova versão quando a "
        "amostra permitir (nenhuma versão existente muda). Cria a tarefa no "
        "painel e a conclui com a entrega.",
        {
            "slug": SLUG_DO_QUIZ,
            **PERIODO,
            "observacao": _texto_ou_nulo("O que a pessoa quer saber em especial."),
        },
    ),
    _ferramenta(
        "consultar_propostas_do_quiz",
        "As propostas de nova versão de um quiz, com o estado de cada uma "
        "(proposta, aceita, publicada, medida, descartada).",
        {"slug": SLUG_DO_QUIZ},
    ),
    _ferramenta(
        "registrar_proposta_de_versao",
        "Registra a ideia de uma versão nova a partir de uma versão publicada. "
        "Não muda o quiz: se a equipe aceitar, a versão nova é criada no "
        "estúdio. Use quando a pessoa pedir ou concordar com a ideia.",
        {
            "slug": SLUG_DO_QUIZ,
            "versao_base": {"type": "string", "description": "A versão publicada de partida, como B2."},
            "gargalo": {"type": "string", "description": "O problema que a versão nova ataca, em uma frase."},
            "hipotese": {"type": "string", "description": "Por que a mudança deve ajudar."},
            "mudanca": {"type": "string", "description": "O que muda, concretamente, na versão nova."},
            "prioridade": {"type": "string", "enum": ["alta", "media", "baixa"]},
        },
    ),
    _ferramenta(
        "decidir_proposta_de_versao",
        "Aceita, descarta, marca como publicada ou registra o resultado medido "
        "de uma proposta. Só quando a pessoa pedir essa decisão.",
        {
            "slug": SLUG_DO_QUIZ,
            "proposta_id": {"type": "integer"},
            "decisao": {
                "type": "string",
                "enum": ["aceitar", "descartar", "marcar_publicada", "registrar_resultado"],
            },
            "resultado": _texto_ou_nulo("O resultado observado, para registrar_resultado."),
        },
    ),
]
NOMES_DO_QUIZ = {d["name"] for d in DEFINICOES_DO_QUIZ}


def pode_usar_o_quiz(membro: MembroDaEquipe) -> bool:
    """Quem fala com o robô administra o site? Pelo e-mail conferido, contra a
    mesma lista da porta do painel."""
    from apps.core.porta import _emails_autorizados

    email = (membro.email or "").strip().lower()
    return bool(email) and not membro.email_a_conferir and email in _emails_autorizados()


def definicoes_para(membro: MembroDaEquipe) -> list[dict]:
    return DEFINICOES + DEFINICOES_DO_QUIZ if pode_usar_o_quiz(membro) else DEFINICOES


ESCREVEM = {
    "perguntar_com_opcoes",
    "criar_rascunho_do_quiz",
    "criar_tarefa",
    "alterar_tarefa",
    "mudar_situacao_da_tarefa",
    "comentar_tarefa",
    "marcar_compromisso",
    "delegar_panorama_semanal",
    "salvar_entrega",
    "montar_links_do_quiz",
    "delegar_conferencia_dos_links",
    "delegar_leitura_do_quiz",
    "registrar_proposta_de_versao",
    "decidir_proposta_de_versao",
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


def consultar_conhecimento(ctx: Contexto, args: dict) -> dict:
    from . import conhecimento

    termos = [str(t)[:80] for t in (args.get("termos") or [])][:5]
    if not termos:
        raise Recusa("Diga pelo menos um nome ou palavra do assunto.")
    resultado = conhecimento.consultar(
        termos,
        com_privados=pode_usar_o_quiz(ctx.membro),
        profundidade=int(args.get("profundidade") or 2),
    )
    if not resultado["achou"]:
        resultado["aviso"] = (
            "Nada no mapa casou esses termos. Tente outro nome ou diga que não achou."
        )
    return resultado


def consultar_conhecimento_comercial(ctx: Contexto, args: dict) -> dict:
    resultado = conhecimento_comercial.executar_ferramenta(args, com_privados=pode_usar_o_quiz(ctx.membro))
    if "erro" in resultado:
        raise Recusa(resultado["erro"])
    return resultado


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
                "resultado": e.resultado or None,
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
    "situacao_desconhecida": "Não conheço essa situação. Nada mudou.",
    "compromisso_marcado": "Tarefa assumida como compromisso desta semana.",
    "compromisso_tirado": "Tarefa tirada dos compromissos desta semana.",
    "compromisso_concluida": "Tarefa já concluída não vira compromisso. Nada mudou.",
    "compromisso_sem_responsavel": (
        "Compromisso é de alguém: a tarefa precisa de responsável. Nada mudou."
    ),
    "comentado": "Comentário publicado.",
    "comentario_vazio": "O comentário estava vazio. Nada foi publicado.",
    "comentario_longo": "O comentário passou de 500 letras. Nada foi publicado.",
}
CODIGOS_DE_RECUSA = {
    "situacao_desconhecida",
    "compromisso_concluida",
    "compromisso_sem_responsavel",
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
    codigo = operacoes.marcar_compromisso(tarefa, ctx.quem, tirar=bool(args.get("tirar")))
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


# ---------------------------------------------------------------- quizzes


def _pelo_quiz(funcao, *args, **kwargs):
    """Chama o quiz; a recusa dele e a falta de resposta voltam ao modelo
    como frase, para ele explicar à pessoa na mesma hora."""
    from .quiz import QuizIndisponivel, QuizRecusou

    try:
        return funcao(*args, **kwargs)
    except QuizRecusou as recusa:
        raise Recusa(str(recusa)) from None
    except QuizIndisponivel as falha:
        raise Recusa(falha.frase) from None


def _no_quiz(ctx: Contexto, args: dict, *, precisa_do_quiz: bool = True) -> tuple[str, str]:
    """O site e o quiz do pedido: o site vem de onde a pessoa escreveu; o
    quiz, do pedido ou da página do quiz."""
    from apps.core.conteudos import SLUG

    contexto = (ctx.execucao.estado or {}).get("contexto") or {}
    host = contexto.get("host") or ""
    if not host:
        raise Recusa(
            "Não sei de qual site é o pedido. Escreva de novo pela página do robô "
            "ou pela página de links e números do quiz."
        )
    slug = str(args.get("slug") or contexto.get("quiz") or "").strip().lower()
    if slug and not SLUG.fullmatch(slug):
        raise Recusa("Esse nome de quiz não existe.")
    if precisa_do_quiz and not slug:
        raise Recusa("Diga qual quiz. A lista sai em consultar_quiz com slug nulo.")
    return host, slug


def _quiz_existe(host: str, slug: str) -> None:
    from . import quiz

    quizzes = _pelo_quiz(quiz.lista_de_quizzes, host)["quizzes"]
    if slug not in {q["slug"] for q in quizzes}:
        nomes = ", ".join(q["slug"] for q in quizzes) or "nenhum"
        raise Recusa(f"Não há quiz {slug} neste site. Os que existem: {nomes}.")


def _periodo(args: dict) -> tuple[str, str]:
    datas = []
    for nome in ("inicio", "fim"):
        valor = str(args.get(nome) or "").strip()
        if valor:
            try:
                date.fromisoformat(valor)
            except ValueError:
                raise Recusa(f"A data {valor} não está em AAAA-MM-DD.") from None
        datas.append(valor)
    return datas[0], datas[1]


def consultar_quiz(ctx: Contexto, args: dict) -> dict:
    from . import quiz

    host, slug = _no_quiz(ctx, args, precisa_do_quiz=False)
    if not slug:
        return _pelo_quiz(quiz.lista_de_quizzes, host)
    return _pelo_quiz(quiz.retrato_do_quiz, host, slug, levantar=True)


def perguntar_com_opcoes(ctx: Contexto, args: dict) -> dict:
    from .quiz_guiado import montar_pergunta

    if (ctx.execucao.estado.get("contexto") or {}).get("pagina") != "campanhas":
        raise Recusa("As opções clicáveis estão na conversa da página de campanhas do quiz.")
    if ctx.execucao.estado.get("pergunta_guiada"):
        raise Recusa("Já há uma pergunta nesta resposta. Espere a pessoa escolher.")
    try:
        pergunta = montar_pergunta(args)
    except ValueError as erro:
        raise Recusa(str(erro)) from None
    ctx.execucao.estado["pergunta_guiada"] = pergunta
    Execucao.objects.filter(pk=ctx.execucao.pk).update(estado=ctx.execucao.estado)
    return {"pergunta_exibida": True, "pergunta": pergunta, "aguardando_resposta": True}


def consultar_rascunho_do_quiz(ctx: Contexto, args: dict) -> dict:
    from .quiz_guiado import consultar_rascunho

    host, slug = _no_quiz(ctx, args)
    return _pelo_quiz(consultar_rascunho, host, slug)


def criar_rascunho_do_quiz(ctx: Contexto, args: dict) -> dict:
    from .quiz_guiado import criar_rascunho

    host, slug = _no_quiz(ctx, args)
    return _pelo_quiz(criar_rascunho, ctx, host, slug, args)


def montar_links_do_quiz(ctx: Contexto, args: dict) -> dict:
    from . import quiz

    host, slug = _no_quiz(ctx, args)
    params = quiz.selecao_dos_argumentos(args, sugerir_campanha=True)
    kit = _pelo_quiz(quiz.kit_de_links, ctx.robo, ctx.execucao, host, slug, params)
    kit["titulo"] = (args.get("campanha") or kit.get("campanha") or "Minha campanha").replace("-", " ").replace("_", " ")
    ctx.execucao.estado.setdefault("kits_guiados", []).append(kit)
    Execucao.objects.filter(pk=ctx.execucao.pk).update(estado=ctx.execucao.estado)
    return kit


def delegar_conferencia_dos_links(ctx: Contexto, args: dict) -> dict:
    from . import quiz
    from .trabalhos import delegar_conferencia

    host, slug = _no_quiz(ctx, args)
    _quiz_existe(host, slug)
    params = quiz.selecao_dos_argumentos(args)
    execucao, nova = delegar_conferencia(
        ctx.robo,
        ctx.membro,
        pedido_por=ctx.membro.nome,
        origem="conversa",
        host=host,
        slug=slug,
        params=params,
        descricao=args.get("observacao") or "",
    )
    return {
        "delegado": True,
        "ja_existia": not nova,
        "trabalho_id": execucao.id,
        "situacao": execucao.get_situacao_display(),
        "conferindo": quiz.descrever_selecao(params),
        "acompanhar_em": quiz.endereco_da_pagina(host, slug, ancora="#robo"),
        "aviso": (
            "Roda no servidor, sem IA e sem custo. O relatório aparece na página "
            "de links e números do quiz e na página do robô."
        ),
    }


def consultar_numeros_do_quiz(ctx: Contexto, args: dict) -> dict:
    from . import quiz

    host, slug = _no_quiz(ctx, args)
    inicio, fim = _periodo(args)
    return _pelo_quiz(quiz.numeros_do_quiz, host, slug, inicio, fim)


def delegar_leitura_do_quiz(ctx: Contexto, args: dict) -> dict:
    from . import quiz
    from .trabalhos import delegar_leitura

    host, slug = _no_quiz(ctx, args)
    inicio, fim = _periodo(args)
    _quiz_existe(host, slug)
    execucao, nova = delegar_leitura(
        ctx.robo,
        ctx.membro,
        pedido_por=ctx.membro.nome,
        origem="conversa",
        host=host,
        slug=slug,
        inicio=inicio,
        fim=fim,
        observacao=args.get("observacao") or "",
    )
    return {
        "delegado": True,
        "ja_existia": not nova,
        "trabalho_id": execucao.id,
        "tarefa_id": execucao.tarefa_id,
        "situacao": execucao.get_situacao_display(),
        "acompanhar_em": quiz.endereco_da_pagina(host, slug, ancora="#robo"),
        "aviso": (
            "Roda no servidor com o modelo forte (centavos, dentro do teto do mês) "
            "e continua mesmo com o navegador fechado."
        ),
    }


def consultar_propostas_do_quiz(ctx: Contexto, args: dict) -> dict:
    from . import quiz

    host, slug = _no_quiz(ctx, args)
    return _pelo_quiz(quiz.propostas_do_quiz, host, slug)


def registrar_proposta_de_versao(ctx: Contexto, args: dict) -> dict:
    from . import quiz

    host, slug = _no_quiz(ctx, args)
    campos = {
        nome: str(args.get(nome) or "").strip()
        for nome in ("versao_base", "gargalo", "hipotese", "mudanca")
    }
    if not all(campos.values()):
        raise Recusa("A proposta precisa de versão base, problema, hipótese e mudança.")
    return _pelo_quiz(
        quiz.registrar_proposta,
        host,
        slug,
        prioridade=args.get("prioridade") or "media",
        **campos,
    )


def decidir_proposta_de_versao(ctx: Contexto, args: dict) -> dict:
    from . import quiz

    host, slug = _no_quiz(ctx, args)
    return _pelo_quiz(
        quiz.decidir_proposta,
        host,
        slug,
        int(args.get("proposta_id") or 0),
        str(args.get("decisao") or ""),
        str(args.get("resultado") or ""),
    )


ACOES = {
    "consultar_conhecimento": consultar_conhecimento,
    "consultar_conhecimento_comercial": consultar_conhecimento_comercial,
    "perguntar_com_opcoes": perguntar_com_opcoes,
    "consultar_rascunho_do_quiz": consultar_rascunho_do_quiz,
    "criar_rascunho_do_quiz": criar_rascunho_do_quiz,
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
    "consultar_quiz": consultar_quiz,
    "montar_links_do_quiz": montar_links_do_quiz,
    "delegar_conferencia_dos_links": delegar_conferencia_dos_links,
    "consultar_numeros_do_quiz": consultar_numeros_do_quiz,
    "delegar_leitura_do_quiz": delegar_leitura_do_quiz,
    "consultar_propostas_do_quiz": consultar_propostas_do_quiz,
    "registrar_proposta_de_versao": registrar_proposta_de_versao,
    "decidir_proposta_de_versao": decidir_proposta_de_versao,
}


# Como cada ação aparece para a pessoa no passo a passo e na página da execução.
ROTULOS = {
    "consultar_conhecimento": "consultar o mapa de conhecimento",
    "consultar_conhecimento_comercial": "consultar o conhecimento comercial do site",
    "perguntar_com_opcoes": "mostrar uma pergunta com opções",
    "consultar_rascunho_do_quiz": "ler as perguntas e ofertas do quiz",
    "criar_rascunho_do_quiz": "montar o quiz no site",
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
    "consultar_quiz": "consultar o quiz",
    "montar_links_do_quiz": "montar os links dos anúncios",
    "delegar_conferencia_dos_links": "pedir a conferência dos links no site",
    "consultar_numeros_do_quiz": "consultar os números do quiz",
    "delegar_leitura_do_quiz": "pedir a leitura dos números do quiz",
    "consultar_propostas_do_quiz": "consultar as propostas de versão",
    "registrar_proposta_de_versao": "registrar uma proposta de versão",
    "decidir_proposta_de_versao": "decidir uma proposta de versão",
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
    if nome in NOMES_DO_QUIZ and not pode_usar_o_quiz(ctx.membro):
        return _registrar(
            ctx,
            call_id,
            nome,
            argumentos,
            {"erro": "Os quizzes ficam com quem administra o site."},
            "recusada",
        )

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
