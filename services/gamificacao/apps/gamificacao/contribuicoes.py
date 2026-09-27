"""O quadro de contribuições: a escola pede, o aluno assume, entrega, e a equipe aceita.

É o ciclo do dossiê da Comunidade (§6), e este arquivo é a ÚNICA porta de
escrita dele: **tarefa disponível, compromisso assumido, contribuição enviada,
avaliação, aceita ou devolvida para ajuste, reconhecimento.** Toda tela passa
por aqui, e é por isso que as travas moram aqui e não nas views.

AS TRAVAS, E POR QUE CADA UMA
------------------------------
1. **A exigência vem antes do compromisso.** A tarefa nasce com os cinco campos
   preenchidos, ou não nasce: quem assume sabe o que vai ser cobrado.
2. **Vaga é teto.** A contagem acontece com a linha da tarefa TRAVADA
   (`select_for_update`): dois alunos clicando juntos na última vaga não viram
   dois compromissos, porque o segundo espera o primeiro e conta de novo.
3. **Ninguém avalia a própria contribuição** (dossiê §12). A equipe também
   contribui, e o banco não sabe comparar `pessoa` com quem clicou.
4. **Aceitar conta uma vez.** Só se avalia o que está ENVIADO; o aceito não
   volta a ser enviado, e o fato (`ContribuicaoAceita`) é único por
   compromisso no banco.
5. **Devolver diz o motivo, da lista, e o que fazer**, por escrito.
6. **Reconhecimento, nunca pagamento.** O aceite registra o fato e chama o motor
   de critérios; a medalha vale o que a escola ligou, e nenhum crédito nasce
   aqui (dossiê §7 e §17: catálogo e benefício são decisão do mantenedor).
7. **Quem responde pela aceitação é sempre da equipe, conferido AQUI.** A view
   já perguntava isso, mas a porta é esta função: quem a chamasse por outro
   caminho gravava uma tarefa com qualquer pessoa como responsável. Fail-closed.
8. **A lista de critérios tem teto.** Sem limite, o campo vira formulário sem
   fim: no máximo 20 critérios, cada um com até 300 caracteres.
9. **Só quem tem matrícula ativa assume** (decisão do mantenedor de
   27/09/2026, a mesma regra do grupo e do desafio). A categoria é pergunta de
   rede, feita pela view (`apps/core/matricula.py`); a regra mora AQUI, e o
   argumento é obrigatório: nenhum caminho assume sem dizer a categoria.

O QUE ESTE ARQUIVO NÃO FAZ: não avisa ninguém. Só boa notícia vira carta, e a
carta da medalha já sai por `conceder()`. A devolução e o prazo moram na tela
do aluno (`/conquistas/contribuicoes`), como na trilha dos marcos.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import transaction
from django.utils import timezone

from apps.core.equipe import e_da_equipe

from .criterios import avaliar
from .models import (
    CompromissoDeContribuicao,
    Concessao,
    ConquistaDefinicao,
    ContribuicaoAceita,
    Pessoa,
    TarefaComunitaria,
)
from .validacao import conceder, prazo_em_dias_uteis

# O prazo da equipe para avaliar uma contribuição enviada: o mesmo dos marcos,
# porque os dois são "olhar com calma o trabalho de alguém", e não responder a
# uma dúvida.
DIAS_UTEIS_PARA_CONTRIBUICAO = 5

# A origem que a concessão guarda: "de onde veio este reconhecimento?" tem de
# ter resposta meses depois (dossiê §5), e é por ela que se volta do
# reconhecimento ao fato que o gerou.
ORIGEM = "contribuicao:{id}"

# O teto de vagas de uma tarefa. Não é regra de produto: é o limite do que a
# coluna guarda sem virar erro de banco, com folga para qualquer tarefa real.
VAGAS_NO_MAXIMO = 999

# O teto da lista de critérios. Também não é regra de produto: sem limite,
# `criterios` vira formulário sem fim. 20 itens de até 300 caracteres cobre
# qualquer tarefa real com folga, e cada item continua sendo uma frase, não
# um parágrafo.
MAXIMO_DE_CRITERIOS = 20
MAXIMO_DE_CARACTERES_POR_CRITERIO = 300

# A única categoria de `getStudentStanding` que assume tarefa no quadro.
CATEGORIA_QUE_ASSUME = "aluno"

Estado = CompromissoDeContribuicao.Estado

# Por que uma contribuição fora de `enviada` não se avalia, dito para a equipe.
# Uma trava só, com a frase certa para cada estado: é ela que impede o reaceite
# de contar duas vezes.
_POR_QUE_NAO_SE_AVALIA = {
    Estado.ASSUMIDA: "Esta contribuição ainda não foi enviada. Não há o que avaliar.",
    Estado.DEVOLVIDA: (
        "Esta contribuição voltou para ajuste. Ela reaparece aqui quando a pessoa "
        "mandar de novo."
    ),
    Estado.ACEITA: (
        "Esta contribuição já foi aceita. Aceitar de novo não conta outra vez, e o "
        "reconhecimento continua sendo um só."
    ),
    Estado.CANCELADA: "A pessoa desistiu desta tarefa. Não há o que avaliar.",
}


class ContribuicaoRecusada(Exception):
    """O gesto não pode acontecer. A mensagem é escrita para ser lida por gente."""


# ---------------------------------------------------------------------------
# A TAREFA, do lado da equipe
# ---------------------------------------------------------------------------
def publicar(
    *,
    site_id: str,
    autor_id: str,
    titulo: str,
    o_que_entregar: str,
    quem_pode: str,
    criterios: list[str],
    responsavel_id: str,
    responsavel_nome: str,
    vagas: int,
    medalha: ConquistaDefinicao | None = None,
) -> TarefaComunitaria:
    """A escola publica o que precisa. Sem os cinco campos, a tarefa não nasce.

    Quem PODE publicar (a view recusa quem não é da equipe antes de chegar
    aqui) é diferente de quem PODE ser o responsável pela aceitação: isso é
    conferido AQUI, contra a mesma porta da equipe (`apps/core/equipe.py`),
    porque esta é a única porta de escrita e não pode confiar que todo
    chamador lembrou de checar antes.
    """
    campos = {
        "o título": titulo,
        "o que entregar": o_que_entregar,
        "quem pode participar": quem_pode,
        "quem responde pela aceitação": responsavel_nome,
    }
    faltando = [nome for nome, valor in campos.items() if not (valor or "").strip()]
    criterios = [c.strip() for c in criterios if c and c.strip()]
    if not criterios:
        faltando.append("ao menos um critério de qualidade")
    if faltando:
        raise ContribuicaoRecusada(
            "A tarefa precisa dizer tudo antes de ir para o quadro. Falta: "
            + ", ".join(faltando)
            + ". Quem assume tem de saber o que vai ser cobrado."
        )
    if len(criterios) > MAXIMO_DE_CRITERIOS:
        raise ContribuicaoRecusada(
            f"A lista de critérios vai até {MAXIMO_DE_CRITERIOS} itens. Escolha "
            "os que realmente importam para quem avalia."
        )
    if any(len(c) > MAXIMO_DE_CARACTERES_POR_CRITERIO for c in criterios):
        raise ContribuicaoRecusada(
            f"Cada critério cabe em até {MAXIMO_DE_CARACTERES_POR_CRITERIO} "
            "caracteres: é uma frase, não um parágrafo."
        )
    if len(titulo.strip()) > 120 or len(responsavel_nome.strip()) > 120:
        raise ContribuicaoRecusada(
            "O título e o nome de quem responde cabem em até 120 caracteres cada."
        )
    if not e_da_equipe(responsavel_id):
        raise ContribuicaoRecusada(
            "Quem responde pela aceitação precisa ser alguém da equipe da escola."
        )
    if not isinstance(vagas, int) or not 1 <= vagas <= VAGAS_NO_MAXIMO:
        raise ContribuicaoRecusada(
            f"As vagas vão de 1 a {VAGAS_NO_MAXIMO}: quantas contribuições a "
            "escola consegue avaliar nesta tarefa."
        )
    if medalha is not None and not _medalha_da_equipe(medalha, site_id):
        raise ContribuicaoRecusada(
            f"A medalha {medalha.nome!r} não pode ser dada por tarefa. Só serve uma "
            "medalha ligada desta escola que seja concedida pela equipe: medalha de "
            "conta automática cai pela própria conta."
        )

    return TarefaComunitaria.objects.create(
        site_id=site_id,
        autor_id=autor_id,
        titulo=titulo.strip(),
        o_que_entregar=o_que_entregar.strip(),
        quem_pode=quem_pode.strip(),
        criterios=criterios,
        responsavel_id=responsavel_id,
        responsavel_nome=responsavel_nome.strip(),
        vagas=vagas,
        medalha=medalha,
    )


def _medalha_da_equipe(medalha: ConquistaDefinicao, site_id: str) -> bool:
    return (
        medalha.site_id == site_id
        and medalha.classe == ConquistaDefinicao.Classe.MEDALHA
        and medalha.ativa
        and (medalha.criterio or {}).get("tipo", "manual") == "manual"
    )


def medalhas_que_a_tarefa_pode_dar(site_id: str) -> list[ConquistaDefinicao]:
    """As medalhas que o formulário da equipe oferece: ligadas e de concessão manual."""
    return [
        medalha
        for medalha in ConquistaDefinicao.objects.filter(
            site_id=site_id, classe=ConquistaDefinicao.Classe.MEDALHA, ativa=True
        ).order_by("nome")
        if _medalha_da_equipe(medalha, site_id)
    ]


def encerrar(*, tarefa: TarefaComunitaria) -> TarefaComunitaria:
    """Fecha a tarefa para compromissos NOVOS. Quem já assumiu continua valendo."""
    tarefa.aberta = False
    tarefa.save(update_fields=["aberta"])
    return tarefa


def reabrir(*, tarefa: TarefaComunitaria) -> TarefaComunitaria:
    tarefa.aberta = True
    tarefa.save(update_fields=["aberta"])
    return tarefa


# ---------------------------------------------------------------------------
# O COMPROMISSO, do lado do aluno
# ---------------------------------------------------------------------------
def _ativos():
    return CompromissoDeContribuicao.objects.exclude(estado=Estado.CANCELADA)


def _meu(tarefa: TarefaComunitaria, pessoa: Pessoa) -> CompromissoDeContribuicao:
    """O compromisso ativo desta pessoa nesta tarefa, ou a recusa dita em português.

    O dono é sempre quem a sessão diz que é: nenhum gesto do aluno recebe o id de
    um compromisso, e o de outra pessoa simplesmente não existe para esta busca.
    """
    compromisso = (
        _ativos().select_for_update().filter(tarefa=tarefa, pessoa=pessoa).first()
    )
    if compromisso is None:
        raise ContribuicaoRecusada(
            "Você ainda não assumiu esta tarefa. Para enviar, primeiro é preciso "
            "assumir, e assumir ocupa uma vaga."
        )
    return compromisso


def assumir(
    *, tarefa: TarefaComunitaria, pessoa: Pessoa, categoria: str
) -> CompromissoDeContribuicao:
    """O aluno diz "eu faço". Com matrícula ativa, dentro das vagas, uma vez por tarefa."""
    if categoria != CATEGORIA_QUE_ASSUME:
        raise ContribuicaoRecusada(
            "Assumir tarefa do quadro é para quem tem matrícula ativa na escola, e "
            "a sua ainda não está ativa. Faça a sua matrícula e volte aqui para "
            "assumir. Ver as tarefas continua livre."
        )
    with transaction.atomic():
        tarefa = TarefaComunitaria.objects.select_for_update().get(pk=tarefa.pk)
        if not tarefa.aberta:
            raise ContribuicaoRecusada(
                "Esta tarefa foi encerrada pela escola e não aceita compromisso novo."
            )
        ocupadas = _ativos().filter(tarefa=tarefa)
        if ocupadas.filter(pessoa=pessoa).exists():
            raise ContribuicaoRecusada(
                "Você já assumiu esta tarefa. O que falta agora é mandar o link."
            )
        if ocupadas.count() >= tarefa.vagas:
            raise ContribuicaoRecusada(
                "As vagas desta tarefa já estão com outras pessoas. Se alguém "
                "desistir, a vaga volta para o quadro."
            )
        return CompromissoDeContribuicao.objects.create(
            tarefa=tarefa, pessoa=pessoa, site_id=tarefa.site_id
        )


def enviar(
    *, tarefa: TarefaComunitaria, pessoa: Pessoa, link: str
) -> CompromissoDeContribuicao:
    """Manda (ou manda de novo) o link da contribuição. O prazo da equipe começa.

    Vale também para tarefa encerrada: encerrar fecha a porta para quem chega,
    não para quem já estava trabalhando.
    """
    link = (link or "").strip()
    try:
        URLValidator(schemes=["http", "https"])(link)
    except ValidationError:
        raise ContribuicaoRecusada(
            "Mande o link da sua contribuição, começando com https://. É por ele "
            "que a escola abre o que você fez."
        ) from None
    if len(link) > 500:
        raise ContribuicaoRecusada(
            "Esse link passa de 500 caracteres. Mande um mais curto."
        )

    with transaction.atomic():
        compromisso = _meu(tarefa, pessoa)
        if compromisso.estado == Estado.ACEITA:
            raise ContribuicaoRecusada(
                "Esta contribuição já foi aceita e está no seu histórico. Mandar de "
                "novo não conta outra vez."
            )
        if compromisso.estado == Estado.ENVIADA:
            raise ContribuicaoRecusada(
                "Esta contribuição já está com a escola, em avaliação. Se ela "
                "voltar para ajuste, o botão de mandar de novo aparece aqui."
            )
        agora = timezone.now()
        compromisso.link = link
        compromisso.estado = Estado.ENVIADA
        compromisso.enviada_em = agora
        compromisso.prazo_ate = prazo_em_dias_uteis(DIAS_UTEIS_PARA_CONTRIBUICAO, agora)
        # O motivo e a orientação descreviam a versão anterior. Mantê-los faria a
        # fila mostrar "o link não abre" ao lado de um link novo.
        compromisso.motivo_da_devolucao = ""
        compromisso.orientacao = ""
        compromisso.save()
    return compromisso


def desistir(*, tarefa: TarefaComunitaria, pessoa: Pessoa) -> CompromissoDeContribuicao:
    """O aluno desiste, e a vaga volta para o quadro. Contribuição aceita não se desfaz."""
    with transaction.atomic():
        compromisso = _meu(tarefa, pessoa)
        if compromisso.estado == Estado.ACEITA:
            raise ContribuicaoRecusada(
                "Esta contribuição já foi aceita e faz parte do seu histórico. Não há "
                "de que desistir."
            )
        compromisso.estado = Estado.CANCELADA
        compromisso.cancelada_em = timezone.now()
        compromisso.save(update_fields=["estado", "cancelada_em"])
    return compromisso


# ---------------------------------------------------------------------------
# A AVALIAÇÃO, do lado da equipe
# ---------------------------------------------------------------------------
def _travar_para_decidir(
    compromisso: CompromissoDeContribuicao, validador_id: str
) -> CompromissoDeContribuicao:
    """Relê a linha travada e confere quem decide. Chamar dentro de transação.

    Travar é o que impede dois cliques da equipe, ao mesmo tempo, de aceitarem a
    mesma contribuição duas vezes: o segundo espera e encontra `aceita`.
    """
    compromisso = CompromissoDeContribuicao.objects.select_for_update().get(
        pk=compromisso.pk
    )
    if not validador_id:
        raise ContribuicaoRecusada(
            "Toda decisão tem nome. Sem o id de quem decidiu, ninguém saberia "
            "depois quem disse sim."
        )
    if validador_id == compromisso.pessoa_id:
        raise ContribuicaoRecusada(
            "Ninguém avalia a própria contribuição. Outra pessoa da equipe precisa "
            "olhar esta."
        )
    if compromisso.estado != Estado.ENVIADA:
        raise ContribuicaoRecusada(_POR_QUE_NAO_SE_AVALIA[compromisso.estado])
    return compromisso


def aceitar(
    *, compromisso: CompromissoDeContribuicao, validador_id: str
) -> CompromissoDeContribuicao:
    """A equipe olhou e disse sim. O fato nasce, e o reconhecimento vem com ele.

    Numa transação só: o estado, o fato e as medalhas. O motor de critérios roda
    ANTES da medalha da tarefa, com o nome de quem aceitou; na ordem inversa, o
    recálculo de dentro de `conceder()` concederia a "Primeira contribuição" como
    se fosse conta de máquina, sem ninguém por trás.
    """
    with transaction.atomic():
        compromisso = _travar_para_decidir(compromisso, validador_id)
        compromisso.estado = Estado.ACEITA
        compromisso.decidida_por = validador_id
        compromisso.decidida_em = timezone.now()
        compromisso.save(update_fields=["estado", "decidida_por", "decidida_em"])

        fato = ContribuicaoAceita.objects.create(
            pessoa=compromisso.pessoa,
            site_id=compromisso.site_id,
            compromisso=compromisso,
            aceita_por=validador_id,
        )
        origem = ORIGEM.format(id=fato.pk)
        quem = {
            "validador_id": validador_id,
            "validador_papel": Concessao.PapelDoValidador.PROFESSOR,
        }
        avaliar(
            compromisso.pessoa_id, compromisso.site_id, origem_event_id=origem, **quem
        )
        medalha = compromisso.tarefa.medalha
        if medalha is not None and medalha.ativa:
            conceder(
                pessoa=compromisso.pessoa,
                site_id=compromisso.site_id,
                conquista=medalha,
                origem_event_id=origem,
                **quem,
            )
    return compromisso


def devolver(
    *,
    compromisso: CompromissoDeContribuicao,
    validador_id: str,
    motivo: str,
    orientacao: str,
) -> CompromissoDeContribuicao:
    """Ainda não. Com o motivo da lista e o que fazer, escrito por quem avaliou."""
    orientacao = (orientacao or "").strip()
    with transaction.atomic():
        compromisso = _travar_para_decidir(compromisso, validador_id)
        if motivo not in CompromissoDeContribuicao.MotivoDaDevolucao.values:
            raise ContribuicaoRecusada(
                "Escolha um motivo da lista. Devolver sem motivo deixa a pessoa sem "
                "saber o que corrigir."
            )
        if not orientacao:
            raise ContribuicaoRecusada(
                "Escreva a orientação de ajuste: o que a pessoa precisa mudar para a "
                "contribuição ser aceita."
            )
        compromisso.estado = Estado.DEVOLVIDA
        compromisso.motivo_da_devolucao = motivo
        compromisso.orientacao = orientacao
        compromisso.decidida_por = validador_id
        compromisso.decidida_em = timezone.now()
        compromisso.save()
    return compromisso


# ---------------------------------------------------------------------------
# AS LEITURAS que as telas usam
# ---------------------------------------------------------------------------
def quadro_da_pessoa(pessoa: Pessoa, site_id: str) -> dict:
    """O que esta pessoa vê: as contribuições dela e as tarefas que ela pode assumir.

    **Nenhum número de outras pessoas.** A tarefa diz se há vaga, e não quantas
    pessoas a assumiram: "3 de 5" é o primeiro passo de um placar (lei §8).
    """
    minhas = list(
        _ativos()
        .filter(pessoa=pessoa, site_id=site_id)
        .select_related("tarefa", "tarefa__medalha")
        .order_by("-assumida_em")
    )
    ja_assumidas = {c.tarefa_id for c in minhas}
    abertas = []
    for tarefa in TarefaComunitaria.objects.filter(
        site_id=site_id, aberta=True
    ).select_related("medalha"):
        if tarefa.pk in ja_assumidas:
            continue
        abertas.append(
            {
                "tarefa": tarefa,
                "tem_vaga": _ativos().filter(tarefa=tarefa).count() < tarefa.vagas,
            }
        )
    return {"minhas": minhas, "abertas": abertas}


def para_avaliar(site_id: str):
    """A fila da equipe: as contribuições enviadas, a de prazo mais curto em cima."""
    return (
        CompromissoDeContribuicao.objects.filter(site_id=site_id, estado=Estado.ENVIADA)
        .select_related("tarefa")
        .order_by("prazo_ate", "enviada_em")
    )


def tarefas_da_escola(site_id: str) -> list[dict]:
    """Todas as tarefas publicadas, com as vagas ocupadas. Bastidor, nunca vitrine."""
    return [
        {"tarefa": tarefa, "ocupadas": _ativos().filter(tarefa=tarefa).count()}
        for tarefa in TarefaComunitaria.objects.filter(site_id=site_id)
    ]
