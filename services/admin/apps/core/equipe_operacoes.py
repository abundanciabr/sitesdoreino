"""As operações do painel da equipe, as mesmas para a tela e para o robô.

O robô pessoal (`apps/agentes`) cria e altera tarefas pelas MESMAS funções
que os formulários do painel usam: uma regra só para validar, concluir,
bloquear, assumir compromisso e comentar. Uma regra copiada no robô seria uma
segunda regra, e duas regras discordam.

As funções recebem os dados no formato do formulário (identificadores como
texto, data como `AAAA-MM-DD`) e devolvem um código de resultado, o mesmo
que a tela transforma em frase por `equipe.RESULTADOS`.
"""

from __future__ import annotations

from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone

from .models import Comentario, Compromisso, MembroDaEquipe, Objetivo, Tarefa

Situacao = Tarefa.Situacao

# "Curto" é o pedido. O campo do formulário avisa no navegador; o servidor
# confere de novo, porque o navegador não é a porta.
TAMANHO_DO_COMENTARIO = 500

CAMPOS_DA_TAREFA = (
    "titulo",
    "descricao",
    "responsavel",
    "objetivo",
    "prazo",
    "situacao",
    "impedimento",
)


def hoje() -> date:
    return timezone.localdate()


def segunda(dia: date) -> date:
    """A segunda-feira da semana de `dia`: é ela que dá nome à semana."""
    return dia - timedelta(days=dia.weekday())


def cumprido(tarefa: Tarefa, domingo: date) -> bool:
    """O compromisso da semana que termina em `domingo` foi cumprido?

    Cumprido é a tarefa concluída até o domingo. Tarefa reaberta deixa de
    estar concluída, e por isso deixa de contar. UMA regra, lida pela aba
    "Esta semana", pela aba Placar e pelo panorama do robô."""
    return bool(
        tarefa.concluida_em and timezone.localdate(tarefa.concluida_em) <= domingo
    )


def membros_ativos() -> list[MembroDaEquipe]:
    return list(MembroDaEquipe.objects.filter(ativo=True))


def objetivos_para_escolher(atual: Objetivo | None = None) -> list[Objetivo]:
    """Os objetivos que a tarefa pode escolher: os ativos, e o que ela já tem
    mesmo desativado, para que salvar a ficha não largue o objetivo por baixo
    dos panos."""
    escolhiveis = list(Objetivo.objects.filter(ativo=True))
    if atual is not None and not atual.ativo:
        escolhiveis.append(atual)
    return escolhiveis


def ler_prazo(cru: str):
    """`(data ou None, erro ou None)` a partir do campo de data."""
    cru = (cru or "").strip()
    if not cru:
        return None, None
    try:
        return date.fromisoformat(cru), None
    except ValueError:
        return None, "O prazo precisa ser uma data válida."


def limpar_dados(cru: dict) -> dict:
    """Os dados de uma tarefa no formato do formulário, aparados."""
    return {
        "titulo": str(cru.get("titulo") or "").strip()[:200],
        "descricao": str(cru.get("descricao") or "").strip()[:5000],
        "responsavel": str(cru.get("responsavel") or "").strip(),
        "objetivo": str(cru.get("objetivo") or "").strip(),
        "prazo": str(cru.get("prazo") or "").strip(),
        "situacao": str(cru.get("situacao") or Situacao.A_FAZER).strip(),
        "impedimento": str(cru.get("impedimento") or "").strip()[:2000],
    }


def validar_tarefa(dados: dict, membros, objetivos) -> list[str]:
    """Os erros que impedem gravar a tarefa, em frases para quem pediu."""
    erros = []
    if not dados["titulo"]:
        erros.append("A tarefa precisa de um título.")
    if dados["responsavel"] and dados["responsavel"] not in {
        str(m.id) for m in membros
    }:
        erros.append("Não conheço essa pessoa. Escolha alguém da equipe.")
    if dados["objetivo"] and dados["objetivo"] not in {str(o.id) for o in objetivos}:
        erros.append("Não conheço esse objetivo. Escolha um dos objetivos ativos.")
    _, erro_prazo = ler_prazo(dados["prazo"])
    if erro_prazo:
        erros.append(erro_prazo)
    if dados["situacao"] not in Situacao.values:
        erros.append("Não conheço essa situação.")
    if dados["situacao"] == Situacao.BLOQUEADA and not dados["impedimento"]:
        erros.append("Para bloquear uma tarefa, escreva o impedimento.")
    return erros


def regra_da_situacao(tarefa: Tarefa, situacao: str, impedimento: str) -> None:
    """A regra da situação: concluir marca a hora; sair da conclusão limpa;
    só a bloqueada carrega impedimento."""
    tarefa.situacao = situacao
    if situacao == Situacao.CONCLUIDA:
        if tarefa.concluida_em is None:
            tarefa.concluida_em = timezone.now()
    else:
        tarefa.concluida_em = None
    tarefa.impedimento = impedimento if situacao == Situacao.BLOQUEADA else ""


def gravar_tarefa(tarefa: Tarefa, dados: dict, membros, objetivos, quem: str) -> Tarefa:
    """Grava os dados já validados na tarefa, e cuida de conclusão e impedimento."""
    tarefa.titulo = dados["titulo"]
    tarefa.descricao = dados["descricao"]
    tarefa.responsavel = {str(m.id): m for m in membros}.get(dados["responsavel"])
    tarefa.objetivo = {str(o.id): o for o in objetivos}.get(dados["objetivo"])
    tarefa.prazo, _ = ler_prazo(dados["prazo"])
    regra_da_situacao(tarefa, dados["situacao"], dados["impedimento"])
    tarefa.alterada_por = quem[:200]
    if not tarefa.pk and not tarefa.criada_por:
        tarefa.criada_por = quem[:200]
    tarefa.save()
    return tarefa


def dados_de(tarefa: Tarefa) -> dict:
    return {
        "titulo": tarefa.titulo,
        "descricao": tarefa.descricao,
        "responsavel": str(tarefa.responsavel_id or ""),
        "objetivo": str(tarefa.objetivo_id or ""),
        "prazo": tarefa.prazo.isoformat() if tarefa.prazo else "",
        "situacao": tarefa.situacao,
        "impedimento": tarefa.impedimento,
    }


def versao_de(tarefa: Tarefa) -> str:
    """O carimbo que diz "a tarefa como eu li". Quem altera com um carimbo
    antigo está escrevendo por cima de uma mudança que não viu."""
    return tarefa.alterada_em.isoformat() if tarefa.alterada_em else ""


class TarefaMudou(Exception):
    """A tarefa foi alterada por outra pessoa depois da leitura."""


def criar_tarefa(cru: dict, quem: str, *, executor: str = "") -> tuple[Tarefa | None, list[str]]:
    membros = membros_ativos()
    objetivos = objetivos_para_escolher()
    dados = limpar_dados(cru)
    erros = validar_tarefa(dados, membros, objetivos)
    if erros:
        return None, erros
    tarefa = Tarefa(criada_por=quem[:200])
    if executor:
        tarefa.executor = executor
    return gravar_tarefa(tarefa, dados, membros, objetivos, quem), []


def alterar_tarefa(
    tarefa_id: int, mudancas: dict, quem: str, *, versao: str = ""
) -> tuple[Tarefa | None, list[str]]:
    """Muda só os campos pedidos e mantém os outros como estão.

    Com `versao`, recusa quando a tarefa mudou desde a leitura: é a alteração
    concorrente que o robô não pode atropelar."""
    with transaction.atomic():
        tarefa = (
            Tarefa.objects.select_for_update(of=("self",)).select_related("objetivo").filter(pk=tarefa_id).first()
        )
        if tarefa is None:
            return None, ["Não achei essa tarefa."]
        if versao and versao != versao_de(tarefa):
            raise TarefaMudou(versao_de(tarefa))
        dados = dados_de(tarefa)
        for campo in CAMPOS_DA_TAREFA:
            if campo in mudancas and mudancas[campo] is not None:
                dados[campo] = mudancas[campo]
        dados = limpar_dados(dados)
        membros = membros_ativos()
        objetivos = objetivos_para_escolher(tarefa.objetivo)
        erros = validar_tarefa(dados, membros, objetivos)
        if erros:
            return None, erros
        return gravar_tarefa(tarefa, dados, membros, objetivos, quem), []


def mudar_situacao(tarefa: Tarefa, situacao: str, impedimento: str, quem: str) -> str:
    """Muda a situação pelo controle simples do cartão. Devolve o código."""
    impedimento = (impedimento or "").strip()[:2000]
    if situacao not in Situacao.values:
        return "situacao_desconhecida"
    if situacao == Situacao.BLOQUEADA and not impedimento:
        return "sem_impedimento"
    estava_concluida = tarefa.situacao == Situacao.CONCLUIDA
    regra_da_situacao(tarefa, situacao, impedimento)
    tarefa.alterada_por = quem[:200]
    tarefa.save()
    if situacao == Situacao.CONCLUIDA:
        return "concluida"
    if estava_concluida:
        return "reaberta"
    return "situacao"


def marcar_compromisso(tarefa: Tarefa, quem: str, *, tirar: bool = False) -> str:
    """Assumir a tarefa como compromisso da semana corrente, ou tirá-la.

    Só a semana CORRENTE se mexe: o que ficou numa semana que já passou é o
    registro dela, e tirar dali seria reescrever o resultado.
    """
    semana = segunda(hoje())
    if tirar:
        Compromisso.objects.filter(tarefa=tarefa, semana=semana).delete()
        return "compromisso_tirado"
    if tarefa.situacao == Situacao.CONCLUIDA:
        return "compromisso_concluida"
    if tarefa.responsavel_id is None:
        return "compromisso_sem_responsavel"
    Compromisso.objects.get_or_create(
        tarefa=tarefa, semana=semana, defaults={"marcado_por": quem[:200]}
    )
    return "compromisso_marcado"


def comentar(
    tarefa: Tarefa, texto: str, autor: str, autor_membro: MembroDaEquipe | None
) -> tuple[str, Comentario | None]:
    """Publica um comentário curto na ficha da tarefa."""
    # O navegador conta a quebra de linha como uma letra e a envia como duas;
    # contar do jeito dele é o que impede recusar o que ele deixou escrever.
    texto = (texto or "").replace("\r\n", "\n").strip()
    if not texto:
        return "comentario_vazio", None
    if len(texto) > TAMANHO_DO_COMENTARIO:
        return "comentario_longo", None
    comentario = Comentario.objects.create(
        tarefa=tarefa, texto=texto, autor=autor[:200], autor_membro=autor_membro
    )
    return "comentado", comentario
