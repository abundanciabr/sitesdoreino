"""Como um trabalho nasce: o robô da pessoa, a mensagem e a delegação.

As telas e as ferramentas do robô criam execuções por aqui, nunca direto na
tabela: é aqui que mora a regra do pedido repetido (a mesma mensagem enviada
duas vezes vira UMA execução) e a do panorama em andamento (pedir de novo
enquanto um panorama não terminou devolve o que já está rodando).
"""

from __future__ import annotations

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core import equipe_operacoes as operacoes
from apps.core.models import MembroDaEquipe, Tarefa

from .models import Conversa, Execucao, Mensagem, RegistroDaExecucao, RoboPessoal

INSTRUCOES_INICIAIS = (
    "Ajudar no trabalho do dia a dia da equipe: consultar e organizar tarefas, "
    "objetivos e compromissos, e produzir o panorama semanal."
)


def robo_de(membro: MembroDaEquipe) -> RoboPessoal:
    """O robô da pessoa. Nasce no primeiro acesso e não renasce: trocar o
    modelo, as instruções ou o nome é alterar este mesmo robô."""
    robo = RoboPessoal.objects.filter(membro=membro).first()
    if robo is not None:
        return robo
    try:
        with transaction.atomic():
            return RoboPessoal.objects.create(
                membro=membro,
                nome=f"Robô de {membro.nome}"[:120],
                responsabilidades=INSTRUCOES_INICIAIS,
            )
    except IntegrityError:
        return RoboPessoal.objects.get(membro=membro)


def conversa_de(robo: RoboPessoal) -> Conversa:
    conversa = robo.conversas.order_by("criada_em").first()
    if conversa is None:
        conversa = Conversa.objects.create(robo=robo, titulo="Conversa")
    return conversa


def registrar(execucao: Execucao, texto: str, situacao: str = "") -> None:
    RegistroDaExecucao.objects.create(
        execucao=execucao, texto=texto[:2000], situacao=situacao or execucao.situacao
    )


def _acordar_o_executor() -> None:
    """Depois que a gravação valer, o executor deste processo busca na hora
    em vez de esperar a próxima volta."""
    from . import executor  # o executor importa daqui: import tardio

    transaction.on_commit(executor.acordar)


def pedir_resposta(
    robo: RoboPessoal,
    membro: MembroDaEquipe,
    texto: str,
    *,
    chave: str,
    autor: str,
    contexto: dict | None = None,
) -> tuple[Mensagem, Execucao]:
    """Guarda a mensagem da pessoa e põe na fila o trabalho de responder.

    `chave` vem do formulário: o mesmo envio repetido (duplo clique, botão
    voltar) acha a mensagem já guardada. `contexto` diz de onde a mensagem
    veio (o domínio do site e, na página de um quiz, qual quiz e o que estava
    escolhido): o robô responde sobre aquela página sem a pessoa repetir."""
    conversa = conversa_de(robo)
    chave = (chave or "")[:64]
    if chave:
        existente = Mensagem.objects.filter(conversa=conversa, chave_de_envio=chave).first()
        if existente is not None and existente.execucao_id:
            return existente, existente.execucao
    try:
        with transaction.atomic():
            mensagem = Mensagem.objects.create(
                conversa=conversa,
                papel=Mensagem.Papel.MEMBRO,
                texto=texto,
                autor=autor[:200],
                chave_de_envio=chave,
            )
            execucao = Execucao.objects.create(
                robo=robo,
                tipo=Execucao.Tipo.CONVERSA,
                origem="conversa",
                pedido_por_membro_id=membro.id,
                pedido_por=autor[:200],
                conversa=conversa,
                pedido=texto[:4000],
                chave_de_repeticao=f"mensagem-{mensagem.id}",
                etapa_atual="Na fila para responder",
                estado={"contexto": contexto} if contexto else {},
            )
            mensagem.execucao = execucao
            mensagem.save(update_fields=["execucao"])
            if contexto and contexto.get("novo_fluxo"):
                execucao.estado["contexto"]["inicio_fluxo"] = mensagem.pk
                execucao.save(update_fields=["estado"])
            registrar(execucao, "Mensagem recebida; resposta na fila do servidor.")
            _acordar_o_executor()
            return mensagem, execucao
    except IntegrityError:
        mensagem = Mensagem.objects.get(conversa=conversa, chave_de_envio=chave)
        return mensagem, mensagem.execucao


def delegar_panorama(
    robo: RoboPessoal,
    membro: MembroDaEquipe,
    *,
    pedido_por: str,
    origem: str,
    observacao: str = "",
    tarefa_id: int | None = None,
    chave: str = "",
) -> tuple[Execucao, bool]:
    """Põe na fila o panorama semanal, ligado a uma tarefa da pessoa.

    Sem tarefa indicada, cria a tarefa "Panorama da semana" no painel com a
    pessoa como responsável e o robô como executor: o trabalho aparece no
    painel desde o primeiro instante, não só quando termina."""
    if chave:
        existente = Execucao.objects.filter(chave_de_repeticao=f"painel-{chave}"[:120]).first()
        if existente is not None:
            return existente, False
    with transaction.atomic():
        # A linha do robô travada serializa dois pedidos ao mesmo tempo.
        RoboPessoal.objects.select_for_update().get(pk=robo.pk)
        aberta = robo.execucoes.filter(
            tipo=Execucao.Tipo.PANORAMA, situacao__in=Execucao.ABERTAS
        ).first()
        if aberta is not None:
            return aberta, False
        quem = f"{robo.nome} (a pedido de {membro.nome})"
        segunda = operacoes.segunda(operacoes.hoje())
        if tarefa_id:
            tarefa = Tarefa.objects.select_for_update().get(pk=tarefa_id)
            if tarefa.executor == Tarefa.Executor.PESSOA:
                tarefa.executor = Tarefa.Executor.ROBO
            if tarefa.situacao == Tarefa.Situacao.A_FAZER:
                operacoes.regra_da_situacao(tarefa, Tarefa.Situacao.EM_ANDAMENTO, "")
            tarefa.alterada_por = quem[:200]
            tarefa.save()
        else:
            tarefa, erros = operacoes.criar_tarefa(
                {
                    "titulo": f"Panorama da semana de {segunda:%d/%m} — {membro.nome}",
                    "descricao": (
                        "Trabalho delegado ao robô: juntar as tarefas, os objetivos "
                        "e os compromissos da semana e salvar o documento como "
                        "entrega desta tarefa."
                        + (f"\n\nPedido: {observacao}" if observacao else "")
                    ),
                    "responsavel": str(membro.id),
                    "situacao": Tarefa.Situacao.EM_ANDAMENTO,
                },
                quem,
                executor=Tarefa.Executor.ROBO,
            )
            if erros:  # pragma: no cover - os dados acima são sempre válidos
                raise ValueError(" ".join(erros))
        execucao = Execucao.objects.create(
            robo=robo,
            tipo=Execucao.Tipo.PANORAMA,
            origem=origem,
            pedido_por_membro_id=membro.id,
            pedido_por=pedido_por[:200],
            tarefa_id=tarefa.id,
            pedido=observacao[:4000],
            chave_de_repeticao=f"painel-{chave}"[:120] if chave else None,
            etapa_atual="Na fila do servidor",
            estado={"semana": segunda.isoformat()},
        )
        registrar(execucao, f"Panorama delegado ({origem}), ligado à tarefa nº {tarefa.id}.")
        _acordar_o_executor()
        return execucao, True


def _repetido(chave: str) -> tuple[str | None, Execucao | None]:
    marca = f"quiz-{chave}"[:120] if chave else None
    if marca is None:
        return None, None
    return marca, Execucao.objects.filter(chave_de_repeticao=marca).first()


def _aberta_do_quiz(robo: RoboPessoal, tipo: str, slug: str) -> Execucao | None:
    return robo.execucoes.filter(
        tipo=tipo, situacao__in=Execucao.ABERTAS, estado__quiz=slug
    ).first()


def delegar_conferencia(
    robo: RoboPessoal,
    membro: MembroDaEquipe,
    *,
    pedido_por: str,
    origem: str,
    host: str,
    slug: str,
    params: dict,
    descricao: str = "",
    chave: str = "",
) -> tuple[Execucao, bool]:
    """Põe na fila a conferência dos links de um quiz no site.

    Sem modelo e sem gasto (`quiz.executar_conferencia`). Pedir de novo
    enquanto a conferência do mesmo quiz não terminou devolve a que está
    rodando."""
    marca, existente = _repetido(chave)
    if existente is not None:
        return existente, False
    with transaction.atomic():
        RoboPessoal.objects.select_for_update().get(pk=robo.pk)
        aberta = _aberta_do_quiz(robo, Execucao.Tipo.CONFERENCIA_QUIZ, slug)
        if aberta is not None:
            return aberta, False
        execucao = Execucao.objects.create(
            robo=robo,
            tipo=Execucao.Tipo.CONFERENCIA_QUIZ,
            origem=origem,
            pedido_por_membro_id=membro.id,
            pedido_por=pedido_por[:200],
            pedido=descricao[:4000],
            chave_de_repeticao=marca,
            etapa_atual="Na fila do servidor",
            estado={"host": host, "quiz": slug, "params": params},
        )
        registrar(execucao, f"Conferência dos links do quiz {slug} pedida ({origem}).")
        _acordar_o_executor()
        return execucao, True


def delegar_leitura(
    robo: RoboPessoal,
    membro: MembroDaEquipe,
    *,
    pedido_por: str,
    origem: str,
    host: str,
    slug: str,
    inicio: str = "",
    fim: str = "",
    observacao: str = "",
    chave: str = "",
) -> tuple[Execucao, bool]:
    """Põe na fila a leitura dos números de um quiz, ligada a uma tarefa.

    Como o panorama: a tarefa "Leitura dos números do quiz" aparece no painel
    desde o primeiro instante, com a pessoa como responsável e o robô como
    executor, e é concluída com a entrega."""
    marca, existente = _repetido(chave)
    if existente is not None:
        return existente, False
    with transaction.atomic():
        RoboPessoal.objects.select_for_update().get(pk=robo.pk)
        aberta = _aberta_do_quiz(robo, Execucao.Tipo.LEITURA_QUIZ, slug)
        if aberta is not None:
            return aberta, False
        quem = f"{robo.nome} (a pedido de {membro.nome})"
        tarefa, erros = operacoes.criar_tarefa(
            {
                "titulo": f"Leitura dos números do quiz {slug} — {operacoes.hoje():%d/%m}",
                "descricao": (
                    "Trabalho delegado ao robô: ler visitas, respostas e cliques "
                    "para a oferta do quiz, apontar onde ele perde gente, sugerir "
                    "até cinco ações e registrar propostas de nova versão quando "
                    "a amostra permitir. A entrega fica ligada a esta tarefa."
                    + (f"\n\nPedido: {observacao}" if observacao else "")
                ),
                "responsavel": str(membro.id),
                "situacao": Tarefa.Situacao.EM_ANDAMENTO,
            },
            quem,
            executor=Tarefa.Executor.ROBO,
        )
        if erros:  # pragma: no cover - os dados acima são sempre válidos
            raise ValueError(" ".join(erros))
        execucao = Execucao.objects.create(
            robo=robo,
            tipo=Execucao.Tipo.LEITURA_QUIZ,
            origem=origem,
            pedido_por_membro_id=membro.id,
            pedido_por=pedido_por[:200],
            tarefa_id=tarefa.id,
            pedido=observacao[:4000],
            chave_de_repeticao=marca,
            etapa_atual="Na fila do servidor",
            estado={"host": host, "quiz": slug, "inicio": inicio, "fim": fim},
        )
        registrar(
            execucao,
            f"Leitura dos números do quiz {slug} pedida ({origem}), ligada à tarefa nº {tarefa.id}.",
        )
        _acordar_o_executor()
        return execucao, True


def pedir_cancelamento(execucao: Execucao, quem: str) -> None:
    """Interromper: o que ainda não começou para na hora; o que está rodando
    para no próximo passo (o executor confere o pedido a cada batimento)."""
    with transaction.atomic():
        execucao = Execucao.objects.select_for_update().get(pk=execucao.pk)
        if not execucao.aberta:
            return
        if execucao.situacao == Execucao.Situacao.EXECUTANDO:
            execucao.cancelar_pedido_em = timezone.now()
            execucao.save(update_fields=["cancelar_pedido_em", "atualizada_em"])
            registrar(execucao, f"Interrupção pedida por {quem}; para no próximo passo.")
            return
        execucao.situacao = Execucao.Situacao.CANCELADA
        execucao.motivo = f"Interrompida por {quem}."
        execucao.terminada_em = timezone.now()
        execucao.save()
        registrar(execucao, execucao.motivo)


def retomar(execucao: Execucao, quem: str, texto: str = "") -> bool:
    """Põe de volta na fila um trabalho que esperava ou que falhou."""
    with transaction.atomic():
        execucao = Execucao.objects.select_for_update().get(pk=execucao.pk)
        if execucao.situacao not in (*Execucao.ESPERANDO, Execucao.Situacao.FALHOU):
            return False
        execucao.situacao = Execucao.Situacao.NA_FILA
        execucao.tentativas = 0
        execucao.nao_antes_de = None
        execucao.terminada_em = None
        execucao.save()
        registrar(execucao, texto or f"Retomada pedida por {quem}.")
        _acordar_o_executor()
        return True


def retomar_os_que_esperam(situacoes, motivo: str) -> int:
    """Põe na fila os trabalhos que esperavam uma dependência que voltou."""
    n = 0
    for execucao in Execucao.objects.filter(situacao__in=situacoes):
        if retomar(execucao, "servidor", f"Retomada pelo servidor: {motivo}."):
            n += 1
    return n
