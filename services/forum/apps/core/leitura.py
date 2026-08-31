"""TEM COISA NOVA? — a marca-d'água de leitura, do banco até a tela.

Escolha do mantenedor em 30/08/2026. A fundação existe desde o modelo de dados
(lei §4.3) e nenhuma tela usava: `MarcaDeLeitura` (UMA linha por pessoa por
ÁREA, o "li até aqui") mais `TopicoLido` (as poucas exceções lidas DEPOIS da
marca). É o desenho do Discourse, e o motivo dele é aritmético.

**A forma ingênua — uma linha por pessoa por mensagem lida — é o erro caro.**
Com 200 alunos e 20 mil mensagens ela fabrica milhões de linhas para responder
uma pergunta boba ("tem coisa nova?"), a lista de tópicos fica lenta, e o
conserto depois é migração na maior tabela do sistema. O guarda que impede essa
volta já existe em `tests/test_modelo_de_dados.py`, e é literal: 30 mensagens
lidas, UMA linha de leitura.

**A conta, em uma frase:** um tópico é novidade quando a última atividade dele é
mais recente que a marca-d'água da área E não existe uma exceção dizendo que a
pessoa o abriu depois dessa atividade.

**Quem nunca leu nada vê tudo como novo, e isso é desejado**, não um caso
esquecido: o aluno que entrar na segunda encontra as dúvidas já publicadas
convidando a entrar, em vez de um fórum que parece vazio.

**Visitante não tem novidade nenhuma.** Sem login não há de quem guardar marca,
e inventar uma por sessão seria guardar estado de gente que o fórum decidiu não
conhecer.
"""

from __future__ import annotations

from django.db.models import Count, Exists, F, OuterRef, Q, Subquery
from django.utils import timezone

from apps.forum.models import MarcaDeLeitura, Topico, TopicoLido


def _com_novidade(pessoa, areas):
    """Os tópicos que são novidade para esta pessoa, nestas áreas.

    Uma consulta só, em SQL, e não um laço em Python: a capa do fórum chama isto
    com todas as áreas de uma vez, e um laço faria uma ida ao banco por área.

    As duas metades da regra aparecem como estão escritas na lei:

    * `lido_ate` é a marca-d'água da área (NULO quando a pessoa nunca marcou
      nada como lido — e aí tudo é novo);
    * `ja_visto` é a exceção: a pessoa abriu ESTE tópico depois da última
      atividade dele.
    """
    marca = MarcaDeLeitura.objects.filter(
        pessoa=pessoa, area=OuterRef("area_id")
    ).values("lido_ate")[:1]
    ja_visto = TopicoLido.objects.filter(
        pessoa=pessoa,
        topico=OuterRef("pk"),
        lido_em__gte=OuterRef("ultima_atividade_em"),
    )
    return (
        Topico.objects.filter(area__in=areas, estado=Topico.Estado.PUBLICADO)
        .annotate(marca_da_area=Subquery(marca), ja_visto=Exists(ja_visto))
        .filter(
            Q(marca_da_area__isnull=True)
            | Q(ultima_atividade_em__gt=F("marca_da_area"))
        )
        .filter(ja_visto=False)
    )


def novidades_por_area(ator, areas) -> dict[int, int]:
    """Quantas conversas têm novidade em cada área. Vazio para visitante."""
    if not ator.autenticado or not areas:
        return {}
    contagem = (
        _com_novidade(ator.pessoa, areas)
        .values("area_id")
        .annotate(quantas=Count("pk"))
    )
    return {linha["area_id"]: linha["quantas"] for linha in contagem}


def topicos_com_novidade(ator, area) -> set[int]:
    """Quais conversas desta área são novidade. Vazio para visitante."""
    if not ator.autenticado:
        return set()
    return set(_com_novidade(ator.pessoa, [area]).values_list("pk", flat=True))


def registrar_leitura(ator, topico) -> None:
    """A pessoa abriu esta conversa: guarda a exceção.

    **Isto é uma escrita durante um GET, e é deliberado.** O resto da célula
    proíbe escrita por GET porque um `<img src>` de outro site a dispararia; aqui
    o que um ataque desses consegue é marcar como lida, para a própria vítima,
    uma conversa que ela poderia abrir de qualquer forma. Nenhum conteúdo muda,
    nada é destruído, e o efeito é o mesmo de ela ter clicado. O preço de evitar
    isso seria um formulário que se envia sozinho em toda página de conversa.

    `update_or_create` porque reler a mesma conversa é o caso comum: a exceção é
    UMA por pessoa por tópico (o banco garante), e ela só avança a data.
    """
    if not ator.autenticado:
        return
    TopicoLido.objects.update_or_create(
        pessoa=ator.pessoa, topico=topico, defaults={"lido_em": timezone.now()}
    )


def marcar_area_como_lida(ator, area) -> None:
    """ "Já vi tudo": a marca-d'água avança e as exceções são PODADAS.

    A poda é o que mantém `TopicoLido` pequena — ela existe só para viver entre
    a marca e o presente. Sem ela, a tabela das exceções cresceria para sempre e
    viraria, devagar, a forma ingênua que a lei §4.3 proíbe.
    """
    if not ator.autenticado:
        return
    agora = timezone.now()
    MarcaDeLeitura.objects.update_or_create(
        pessoa=ator.pessoa, area=area, defaults={"lido_ate": agora}
    )
    TopicoLido.objects.filter(
        pessoa=ator.pessoa, topico__area=area, lido_em__lte=agora
    ).delete()
