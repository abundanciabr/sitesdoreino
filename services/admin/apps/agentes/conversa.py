"""Responder uma mensagem da conversa: o modelo rápido (GPT-6 Luna) com as
ações do painel.

O histórico mora aqui, não na OpenAI: cada rodada reenvia os itens da
conversa e dos pedidos de ação já resolvidos. Os itens ficam guardados em
`Execucao.estado["itens"]` ANTES de qualquer ação rodar, para que a retomada
reveja os mesmos pedidos (mesmo `call_id`) e ache as ações já feitas em vez
de repeti-las.
"""

from __future__ import annotations

from apps.core import equipe_operacoes as operacoes
from apps.core.models import MembroDaEquipe

from . import ferramentas, modelo
from .executor import batimento, guardar_estado, terminar
from .models import Execucao, Mensagem

MAX_RODADAS = 8
HISTORICO = 30
MAX_SAIDA = 2000


def instrucoes(robo, membro) -> str:
    hoje = operacoes.hoje()
    segunda = operacoes.segunda(hoje)
    partes = [
        f"Você é {robo.nome}, o robô pessoal de {membro.nome}"
        + (f" ({membro.area})" if membro.area else "")
        + " na equipe da Meshcraft, uma escola de modelagem 3D.",
        f"Hoje é {hoje:%d/%m/%Y} ({hoje.isoformat()}); a semana começou em "
        f"{segunda:%d/%m} ({segunda.isoformat()}). Fuso: America/Sao_Paulo.",
    ]
    if robo.responsabilidades:
        partes.append("Suas responsabilidades: " + robo.responsabilidades)
    if robo.instrucoes:
        partes.append(f"Instruções de {membro.nome}: " + robo.instrucoes)
    partes.append(
        "Como trabalhar:\n"
        "- Responda em português do Brasil, curto e direto, como colega de equipe.\n"
        "- Para falar de tarefas, objetivos, pessoas e compromissos, consulte "
        "com as ferramentas. Não invente números nem nomes.\n"
        "- Criar uma tarefa é diferente de executar um trabalho. 'Cria uma "
        "tarefa para...' é criar_tarefa. 'Faz o panorama da semana' é "
        "delegar_panorama_semanal, que roda no servidor.\n"
        "- Só diga que algo foi criado, alterado, comentado ou delegado depois "
        "que a ferramenta confirmar. Se ela recusar, diga o motivo dela.\n"
        "- Pergunte só quando um nome servir para mais de uma pessoa ou tarefa, "
        "ou quando faltar o título de uma tarefa. No resto, decida pelo óbvio "
        "e diga o que decidiu.\n"
        "- Antes de alterar uma tarefa existente, consulte-a e passe a versão.\n"
        "- Nas ferramentas, datas em AAAA-MM-DD; para a pessoa, DD/MM.\n"
        "- Ainda não existem: lembretes, automações por horário, avisos por "
        "e-mail ou celular, conversa com outros robôs. Se pedirem, diga que "
        "ainda não está disponível, sem fingir que fez."
    )
    return "\n\n".join(partes)


def _historico(execucao: Execucao) -> list[dict]:
    gatilho = execucao.mensagens.filter(papel=Mensagem.Papel.MEMBRO).first()
    mensagens = Mensagem.objects.filter(conversa_id=execucao.conversa_id).exclude(
        papel=Mensagem.Papel.AVISO
    )
    if gatilho is not None:
        mensagens = mensagens.filter(id__lte=gatilho.id)
    recentes = list(mensagens.order_by("-id")[:HISTORICO])[::-1]
    itens = []
    for m in recentes:
        papel = "user" if m.papel == Mensagem.Papel.MEMBRO else "assistant"
        itens.append({"role": papel, "content": m.texto})
    return itens


def executar(execucao: Execucao) -> None:
    robo = execucao.robo
    membro = MembroDaEquipe.objects.get(pk=execucao.pedido_por_membro_id or robo.membro_id)
    conexao = modelo.conexao()
    execucao.modelo = conexao.modelo_rapido
    Execucao.objects.filter(pk=execucao.pk).update(modelo=execucao.modelo)
    ctx = ferramentas.Contexto(robo=robo, membro=membro, execucao=execucao)

    estado = execucao.estado or {}
    if "itens" not in estado:
        estado["itens"] = _historico(execucao)
        estado["rodadas"] = 0
        execucao.estado = estado
        guardar_estado(execucao)

    while True:
        itens = estado["itens"]
        pendentes = _pedidos_sem_resposta(itens)
        if pendentes:
            # Retomada depois de cair no meio das ações: termina as ações
            # da rodada guardada antes de chamar o modelo de novo.
            for chamada in pendentes:
                batimento(execucao, f"Fazendo: {chamada.get('name')}")
                saida = ferramentas.executar(
                    ctx, chamada["call_id"], chamada.get("name", ""), chamada.get("arguments", "")
                )
                itens.append(
                    {"type": "function_call_output", "call_id": chamada["call_id"], "output": saida}
                )
                guardar_estado(execucao)
            continue

        if estado.get("rodadas", 0) >= MAX_RODADAS:
            _responder(
                execucao,
                "Parei depois de muitas ações seguidas sem chegar a uma resposta. "
                "Me diga com mais detalhe o que precisa.",
            )
            return

        batimento(execucao, "Pensando na resposta", progresso=min(90, 10 + 10 * estado.get("rodadas", 0)))
        resposta = modelo.responder(
            modelo=execucao.modelo,
            instrucoes=instrucoes(robo, membro),
            itens=itens,
            ferramentas=ferramentas.DEFINICOES,
            max_saida=MAX_SAIDA,
            execucao=execucao,
            robo=robo,
        )
        estado["rodadas"] = estado.get("rodadas", 0) + 1
        itens.extend(resposta.itens)
        guardar_estado(execucao)

        if not resposta.chamadas:
            texto = resposta.texto or (
                "Não consegui formular uma resposta agora." if resposta.completa
                else "A resposta ficou longa demais e foi cortada. Peça em partes."
            )
            _responder(execucao, texto)
            return


def _pedidos_sem_resposta(itens: list) -> list[dict]:
    respondidos = {i.get("call_id") for i in itens if i.get("type") == "function_call_output"}
    return [
        i for i in itens
        if i.get("type") == "function_call" and i.get("call_id") not in respondidos
    ]


def _responder(execucao: Execucao, texto: str) -> None:
    Mensagem.objects.create(
        conversa_id=execucao.conversa_id,
        papel=Mensagem.Papel.ROBO,
        texto=texto,
        autor=execucao.robo.nome,
        execucao=execucao,
    )
    acoes = execucao.chamadas.filter(situacao="feita").exclude(nome__startswith="consultar").count()
    resumo = f"Respondeu na conversa ({acoes} ação(ões) no painel)." if acoes else "Respondeu na conversa."
    terminar(execucao, Execucao.Situacao.CONCLUIDA, resultado=resumo)

