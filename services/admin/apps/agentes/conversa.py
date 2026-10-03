"""Responder uma mensagem da conversa: o modelo rápido (GPT-6 Luna) com as
ações do painel.

O histórico mora aqui, não na OpenAI: cada rodada reenvia os itens da
conversa e dos pedidos de ação já resolvidos. Os itens ficam guardados em
`Execucao.estado["itens"]` ANTES de qualquer ação rodar, para que a retomada
reveja os mesmos pedidos (mesmo `call_id`) e ache as ações já feitas em vez
de repeti-las.
"""

from __future__ import annotations

import json

from apps.core import equipe_operacoes as operacoes
from apps.core.models import MembroDaEquipe

from . import ferramentas, modelo
from .executor import batimento, guardar_estado, terminar
from .models import Execucao, Mensagem

MAX_RODADAS = 8
HISTORICO = 30
MAX_SAIDA = 2000
# Conversa de painel pede resposta rápida: o modelo pensa pouco antes de
# responder. O panorama (modelo forte) fica com o esforço padrão.
ESFORCO = "low"


def instrucoes(robo, membro, retrato: dict | None = None, quiz: dict | None = None) -> str:
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
        "- No fim destas instruções está o retrato do painel, tirado no instante "
        "desta mensagem: as pessoas, os objetivos ativos e as tarefas abertas da "
        "pessoa, com prazo, atraso, compromisso da semana e versão. Ele vale como "
        "uma consulta recém-feita. Para perguntas que ele responde, responda "
        "direto, sem chamar ferramenta de consulta. Consulte só o que ele não "
        "traz: tarefas de outra pessoa ou concluídas, comentários e detalhes de "
        "uma tarefa, outra semana, ou quando o total for maior que as listadas. "
        "Não invente números nem nomes. Para a pessoa, o retrato é só o "
        "painel: diga 'no painel', nunca 'no retrato'.\n"
        "- Para perguntas que cruzam coisas (quem cuida de quê, o que depende "
        "de quê, por que algo existe, o que os documentos dizem de um assunto), "
        "chame consultar_conhecimento com os nomes do assunto e responda pelas "
        "ligações que voltarem, citando a fonte (documento ou painel) em poucas "
        "palavras. Se o mapa não trouxer, diga que não achou, sem completar de cabeça.\n"
        "- Criar uma tarefa é diferente de executar um trabalho. 'Cria uma "
        "tarefa para...' é criar_tarefa. 'Faz o panorama da semana' é "
        "delegar_panorama_semanal, que roda no servidor.\n"
        "- Só diga que algo foi criado, alterado, comentado ou delegado depois "
        "que a ferramenta confirmar. Se ela recusar, diga o motivo dela.\n"
        "- Fora da criação guiada de quiz ou campanha, pergunte só quando um nome servir para mais de uma pessoa ou tarefa, "
        "ou quando faltar o título de uma tarefa. No resto, decida pelo óbvio "
        "e diga o que decidiu.\n"
        "- Ao alterar uma tarefa existente, passe a versão do retrato ou de "
        "consultar_tarefa. Se a ação recusar por versão, consulte e tente de novo.\n"
        "- Nas ferramentas, datas em AAAA-MM-DD; para a pessoa, DD/MM.\n"
        "- Ainda não existem: lembretes, automações por horário, avisos por "
        "e-mail ou celular, conversa com outros robôs. Se pedirem, diga que "
        "ainda não está disponível, sem fingir que fez."
    )
    if quiz is not None:
        partes.append(instrucoes_do_quiz(membro, quiz))
    if retrato:
        partes.append(
            "Retrato do painel quando a mensagem chegou (JSON):\n"
            + json.dumps(retrato, ensure_ascii=False, separators=(",", ":"))
        )
    return "\n\n".join(partes)


def instrucoes_do_quiz(membro, quiz: dict) -> str:
    """O que o robô sabe e pode nos quizzes do site. Só entra para quem
    administra o site (`ferramentas.pode_usar_o_quiz`)."""
    from .quiz import caminho, descrever_selecao, endereco_da_pagina

    partes = [
        f"Quizzes do site ({membro.nome} administra o site, então você também "
        "opera os quizzes):\n"
        "- Cada quiz leva quem responde a uma de duas ofertas, pela soma dos "
        "pontos. As versões (A, B1, B2...) convivem no mesmo endereço e não "
        "mudam depois de publicadas: mudança vira versão nova, por proposta. "
        "Formatos: text = Texto, video = Vídeo no topo (VSL), hybrid = Vídeo "
        "curto + texto, calc = Calculadora, ai = Conversa com IA. Públicos (seg) "
        "como frio e quente; 'geral' é o link sem público. Cada anúncio usa um "
        "link fixo de versão, formato e público.\n"
        "- Link de anúncio sai só de montar_links_do_quiz; nunca escreva um link "
        "à mão. Se forem mais de 8 links, mande o endereço da página que a "
        "ferramenta devolve e o número da entrega, sem colar todos.\n"
        "- Antes de a equipe subir anúncios, ofereça delegar_conferencia_dos_links: "
        "não custa nada, abre as páginas como visitante marcado como teste, não "
        "envia formulário e não compra.\n"
        "- Números: abaixo de 30 visitas é observação, não decisão. Campanha "
        "direcionada mostra o que aconteceu, não prova causa. Clique na oferta "
        "não é compra; ainda não há dados de compra. Para a leitura completa com "
        "ações e propostas, delegar_leitura_do_quiz (modelo forte, centavos).\n"
        "- Proposta de versão só registra a ideia: não publica nem muda versão "
        "existente. Aceitar, descartar ou marcar resultado só quando a pessoa "
        "pedir.\n"
        "- Você pode criar perguntas e resultados com criar_rascunho_do_quiz: "
        "o estúdio salva o quiz de verdade, sem alterar as versões publicadas. "
        "Não liga chaves, não compra anúncios e não mexe em verba. Para testar "
        "e publicar o quiz montado, devolva o endereço do estúdio."
    ]
    contexto = quiz.get("contexto") or {}
    host, slug = contexto.get("host"), contexto.get("quiz")
    if host and slug:
        partes.append(
            f"A pessoa escreveu da página de links e números do quiz {slug} "
            f"({endereco_da_pagina(host, slug)}). Na tela estava escolhido: "
            f"{descrever_selecao(contexto.get('selecao') or {})}. Quando ela disser "
            "'este quiz', 'estes links' ou 'esta página', é isso. Estúdio do quiz: "
            f"https://{host}{caminho('conteudo_editar', 'quiz', slug)}. Onde o quiz "
            f"perde gente: https://{host}{caminho('quiz_evolucao', slug)}."
        )
        if contexto.get("pagina") == "campanhas":
            partes.append(
                "Conversa guiada para uma pessoa leiga e iniciante:\n"
                "- Você conduz: uma pergunta de cada vez, curta, em pt-BR. "
                "Use perguntar_com_opcoes para mostrar controles reais na tela; "
                "não escreva uma lista de perguntas nem código HTML ou JSON na conversa. "
                "Ao chamar essa ferramenta, a tela exibe o formulário e espera a resposta.\n"
                "- Prefira radio para uma escolha, checkbox para várias escolhas, "
                "select para lista extensa e texto para algo pessoal. Sempre permita "
                "outra resposta quando fizer sentido, e ofereça 'Pode sugerir por mim' "
                "para quem não souber. Checkbox é para a nossa conversa de criação; "
                "as perguntas do quiz público usam uma resposta por pergunta.\n"
                "- Não peça identificadores, pontos, nomes técnicos de formatos ou parâmetros. "
                "Traduza escolhas em configuração e faça essas contas você. "
                "Aproveite informações já dadas; não pergunte de novo.\n"
                "- Ao criar quiz: comece perguntando o objetivo, com 2 a 4 opções "
                "simples, 'Pode sugerir por mim' e outra resposta. Pergunte quem "
                "vai responder na próxima pergunta, se ainda não souber. Depois "
                "identifique as duas ofertas ou resultados e suas diferenças; consulte "
                "consultar_rascunho_do_quiz para oferecer ofertas reais existentes. "
                "Pergunte preferências de tamanho (3, 5 ou 7 perguntas) e apresentação "
                "(texto, vídeo ou conversa), se ainda não estiverem claras. Sugira "
                "as perguntas, alternativas, títulos e resultados com base nas respostas. "
                "Quando já souber o suficiente, use criar_rascunho_do_quiz. Para criar "
                "novo quiz use modo novo e derive o slug do nome escolhido; para "
                "melhorar este quiz, consulte o rascunho e use nova_versao, preservando "
                "os IDs das duas ofertas existentes. Não diga que criou antes de salvar. "
                "Para text crie headline e subheadline; video/hybrid podem ter "
                "video_url:null quando ainda não houver vídeo; ai precisa de instructions. "
                "Não invente preço, curso, promessa ou endereço de pagamento. "
                "Se a pessoa pedir suas próprias ofertas, colete os nomes e para quem são; "
                "checkout_url fica null. Se escolher ofertas deste quiz, use os mesmos "
                "IDs e usar_ofertas_do_quiz_atual:true.\n"
                "- Ao criar campanha: descubra onde divulgar (uma ou várias origens), "
                "se é divulgação paga ou gratuita e para quem. Use a versão mais nova "
                "e Texto como padrão, salvo preferência diferente. Antes de montar "
                "os links, proponha 2 ou 3 nomes curtos e humanos usando radio, "
                "aceita_outro:true e outro_rotulo:'Prefiro informar outro nome'. "
                "Gere os nomes conforme objetivo, público e canal; não só códigos. "
                "Pode também sugerir nomes para os anúncios. Se houver vários canais, "
                "chame montar_links_do_quiz uma vez para cada origem.\n"
                "- Se a pessoa já explicou tudo ou pediu para você decidir, conclua "
                "direto com as ferramentas. Em uma entrega final, seja breve e "
                "mostre o próximo botão útil. Não mostre IDs de entrega, códigos de "
                "versão, parâmetros ou avisos sobre compras: diga o nome humano "
                "da campanha e que o link está pronto para copiar. Passe o nome "
                "escolhido com espaços e acentos em montar_links_do_quiz; o sistema "
                "prepara o código do link. O histórico é a memória da conversa."
            )
    if quiz.get("retrato"):
        partes.append(
            "Estrutura do quiz quando a mensagem chegou (JSON; vale como "
            "consultar_quiz recém-feito):\n"
            + json.dumps(quiz["retrato"], ensure_ascii=False, separators=(",", ":"))
        )
    return "\n\n".join(partes)


def _quiz_da_conversa(estado: dict, membro) -> dict | None:
    if not ferramentas.pode_usar_o_quiz(membro):
        return None
    return {"contexto": estado.get("contexto") or {}, "retrato": estado.get("retrato_quiz")}


def _historico(execucao: Execucao) -> list[dict]:
    gatilho = execucao.mensagens.filter(papel=Mensagem.Papel.MEMBRO).first()
    mensagens = Mensagem.objects.filter(conversa_id=execucao.conversa_id).exclude(
        papel=Mensagem.Papel.AVISO
    )
    contexto = (execucao.estado or {}).get("contexto") or {}
    if contexto.get("quiz"):
        mensagens = mensagens.filter(execucao__estado__contexto__quiz=contexto["quiz"])
    if contexto.get("inicio_fluxo"):
        mensagens = mensagens.filter(id__gte=contexto["inicio_fluxo"])
    if gatilho is not None:
        mensagens = mensagens.filter(id__lte=gatilho.id)
    recentes = list(mensagens.order_by("-id")[:HISTORICO])[::-1]
    itens = []
    for m in recentes:
        papel = "user" if m.papel == Mensagem.Papel.MEMBRO else "assistant"
        texto = m.texto
        if m.papel == Mensagem.Papel.ROBO and m.execucao_id:
            pergunta = (m.execucao.estado or {}).get("pergunta_guiada")
            if pergunta:
                texto += "\nOpções oferecidas: " + "; ".join(o["rotulo"] for o in pergunta["opcoes"])
        itens.append({"role": papel, "content": texto})
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
        # Guardado com os itens: a retomada e a segunda rodada veem o mesmo
        # retrato, e o começo do pedido fica igual para o cache da OpenAI.
        estado["retrato"] = ferramentas.retrato(membro)
        contexto = estado.get("contexto") or {}
        if contexto.get("host") and contexto.get("quiz") and ferramentas.pode_usar_o_quiz(membro):
            from .quiz import retrato_do_quiz

            estado["retrato_quiz"] = retrato_do_quiz(contexto["host"], contexto["quiz"])
        execucao.estado = estado
        guardar_estado(execucao)

    while True:
        itens = estado["itens"]
        pendentes = _pedidos_sem_resposta(itens)
        if estado.get("pergunta_guiada") and not pendentes:
            from .quiz_guiado import texto_da_pergunta

            _responder(execucao, texto_da_pergunta(estado["pergunta_guiada"]))
            return
        if pendentes:
            # Retomada depois de cair no meio das ações: termina as ações
            # da rodada guardada antes de chamar o modelo de novo.
            for chamada in pendentes:
                nome = chamada.get("name", "")
                batimento(execucao, f"Fazendo: {ferramentas.ROTULOS.get(nome, nome)}")
                saida = ferramentas.executar(
                    ctx, chamada["call_id"], chamada.get("name", ""), chamada.get("arguments", "")
                )
                itens.append(
                    {"type": "function_call_output", "call_id": chamada["call_id"], "output": saida}
                )
                guardar_estado(execucao)
            if estado.get("pergunta_guiada"):
                from .quiz_guiado import texto_da_pergunta

                _responder(execucao, texto_da_pergunta(estado["pergunta_guiada"]))
                return
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
            instrucoes=instrucoes(
                robo, membro, estado.get("retrato"), _quiz_da_conversa(estado, membro)
            ),
            itens=itens,
            ferramentas=ferramentas.definicoes_para(membro),
            max_saida=8000 if (estado.get("contexto") or {}).get("guiado") else MAX_SAIDA,
            esforco=ESFORCO,
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
    Mensagem.objects.get_or_create(
        execucao=execucao,
        papel=Mensagem.Papel.ROBO,
        defaults={
            "conversa_id": execucao.conversa_id,
            "texto": texto,
            "autor": execucao.robo.nome,
        },
    )
    acoes = execucao.chamadas.filter(situacao="feita").exclude(nome__startswith="consultar").count()
    resumo = f"Respondeu na conversa ({acoes} ação(ões) no painel)." if acoes else "Respondeu na conversa."
    terminar(execucao, Execucao.Situacao.CONCLUIDA, resultado=resumo)

