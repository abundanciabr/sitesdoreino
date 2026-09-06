"""Onde a sala de aula está: QUAL curso, e em QUE PARTE dele.

O endereço da sala carrega o curso e a parte por decisão do mantenedor, em
05/09/2026, com as palavras dele: *"quero que ao compartilhar uma aula o link
da mesma seja útil para o aluno entender exatamente em qual parte do curso ele
está"*. O motivo que decide tudo veio logo depois: *"precisamos ajustar o curso
ao livro porque o aluno terá o livro em mãos durante o curso"*. Os números do
endereço são os números do livro, e é por isso que eles precisam ser
confiáveis.

POR QUE ESTE MÓDULO EXISTE
--------------------------
Para que a conta seja feita UMA vez. Quem a usa são as duas portas desta
célula: a de máquina (`apps/core/api.py`, onde a regra nasceu na TAR-203) e a
sala do aluno (`apps/core/views.py`). Duplicar e divergir é o terceiro pecado
da Lei 3, e aqui ele teria a forma mais cara possível: um endereço que a porta
de máquina recusa e a sala aceita mostraria ao aluno a aula ERRADA com o
número CERTO na barra do navegador, sem erro em lugar nenhum.

O CURSO SE RESOLVE PELO PAR SITE+SLUG, NUNCA POR "O PRIMEIRO DO SITE"
----------------------------------------------------------------------
É a unicidade que o banco garante (`um_curso_por_slug_por_site`). "O primeiro
do site" era a resolução da sala do aluno até esta data
(`Curso.objects.filter(site_id=site).order_by("id").first()`): no dia em que
nascesse um segundo curso, o site inteiro continuaria servindo o primeiro, sem
erro, sem aviso e sem tela quebrada. Medido em 06/09/2026, com dois cursos
semeados no mesmo site: a sala servia o de `id=1` e o segundo era invisível
para todo mundo.

A PARTE É GUARDA, E NÃO FILTRO
-------------------------------
`parte_errada` devolve `None` quando o endereço está certo (inclusive quando a
parte não foi pedida) e a FRASE da recusa quando não está. Quem chama decide o
formato da recusa: a porta de máquina levanta 404 com essa frase no corpo, a
sala do aluno desenha uma tela com ela e com o link do endereço certo.
"""

from __future__ import annotations

from apps.cursos.models import Aula, Curso


def cursos_do_site(site_id: str) -> list[Curso]:
    """Os cursos deste site, em ordem de slug: a ordem que o aluno lê."""
    return list(Curso.objects.filter(site_id=site_id).order_by("slug"))


def curso_do_site(site_id: str, slug: str) -> Curso | None:
    """O curso pelo PAR site+slug, ou `None`. Nunca "o primeiro do site"."""
    return Curso.objects.filter(site_id=site_id, slug=slug).first()


def recado_de_curso_desconhecido(site_id: str, slug: str) -> str:
    """A frase da recusa, com os slugs que existem: quem errou o endereço
    precisa saber qual é o certo, e um 404 mudo manda a pessoa adivinhar."""
    conhecidos = ", ".join(curso.slug for curso in cursos_do_site(site_id))
    recado = (
        f"os cursos deste site são: {conhecidos}"
        if conhecidos
        else "este site ainda não tem curso"
    )
    return f"o curso '{slug}' não existe no site '{site_id}'; {recado}"


def parte_errada(curso: Curso, aula: Aula, parte: int | None) -> str | None:
    """`None` quando o endereço está certo; a frase da recusa quando não está.

    Um endereço que aponta certo para a aula ERRADA é pior do que um endereço
    quebrado: o aluno com o livro aberto confia no número. Por isso a parte
    que não casa recusa, e a frase diz em que parte a aula realmente está.
    """
    if parte is None or aula.bloco.parte == int(parte):
        return None
    return (
        f"a aula {aula.numero} não está na parte {int(parte)} do curso "
        f"'{curso.slug}': ela está na parte {aula.bloco.parte}. Troque a "
        f"parte do endereço para {aula.bloco.parte}."
    )
