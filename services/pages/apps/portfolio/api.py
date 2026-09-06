"""A porta de MÁQUINA do portfólio: o que outra célula pode perguntar, e só isso.

POR QUE ELA EXISTE, E POR QUE TEM UMA OPERAÇÃO SÓ
--------------------------------------------------
A lei desta obra diz, com todas as letras, que a peça tem UMA casa: o portfólio
não guarda cópia de medalha, a gamificação não guarda cópia de peça, e **a tela
que precisa das duas pergunta por HTTP com falha ABERTA**
(`PLANO-PORTFOLIO-DO-ALUNO.md` §4). Sem esta porta, aquela frase é promessa sem
mecanismo: a primeira tela que precisasse do selo guardaria uma segunda cópia
dele, e no dia em que as duas discordassem ninguém saberia qual está certa.

A pergunta que essa tela faz é uma só: **onde este aluno está no roteiro, e a
escola já conferiu?** É ela que esta porta responde. Nada mais entra porque
nada mais tem consumidor declarado hoje, e o contrato desta casa é ADITIVO:
crescer é livre (um PR de Rito acrescenta campo), remover exige autorização
explícita. Nascer largo seria congelar operação que ninguém chama, e depois
precisar de Rito para tirá-la.

O QUE NÃO SAI DAQUI, E É DECISÃO
---------------------------------
- **Link, legenda e apelido.** São conteúdo do aluno, e só ids opacos viajam
  entre células (constituição da `pages`, seção "Emite"). Quem precisar mostrar
  a peça mostra a Prancheta ou a vitrine, que são desta casa.
- **E-mail, telefone e nome.** A célula não os guarda (critério AC-14), então
  não há o que vazar.
- **Nota, estrela ou ranking.** Proibidos por escrito (plano §7). Não existe
  campo aqui que possa virar um.
- **Escrita.** Nenhum verbo além de `GET`: quem muda o portfólio é o aluno, na
  tela desta casa, com sessão. Uma porta de máquina que escrevesse abriria um
  segundo caminho para a mesma regra, e regras em duas expressões divergem.

A LEITURA PASSA PELA PORTA ÚNICA
--------------------------------
`Portfolio.objects.do_aluno(...)` é o isolamento por aluno do critério AC-07, e
esta operação lê por ela como toda tela vai ler. Escrever um `filter()` próprio
aqui espalharia a regra numa segunda expressão, que é exatamente o que o degrau
02 recusou. Guarda: `tests/test_porta_de_maquina.py`, e o `do_aluno` já é
provado por mutação em `tests/test_isolamento_por_aluno.py`.
"""

from __future__ import annotations

from ninja import Router, Schema
from ninja.errors import HttpError

from apps.portfolio.models import PRIMEIRA_ETAPA, Portfolio

router = Router()


class PortfolioDoAluno(Schema):
    """O que sai. Campo novo aqui e mudanca de contrato (RITOS.md secao 3)."""

    portfolio_id: str
    etapa_atual: int
    conferido_em: str | None


@router.get(
    "/portfolios/{site_id}/{aluno_id}",
    response=PortfolioDoAluno,
    operation_id="getStudentPortfolio",
    summary="Onde o aluno esta no roteiro do portfolio, e se a escola conferiu",
    description=(
        "Responde a UNICA pergunta que outra celula faz sobre o portfolio:\n"
        "em que etapa das cinco o aluno esta, e se o selo 'conferido pela\n"
        "escola' ja saiu (`conferido_em`, ou `null` enquanto nao saiu).\n"
        "\n"
        "404 quando este aluno nao tem portfolio neste site, e o 404 e a\n"
        "resposta CERTA: 'ele nao comecou' e um fato, nao um erro, e devolver\n"
        "200 com campos vazios obrigaria todo consumidor a inventar a propria\n"
        "regra para distinguir os dois.\n"
        "\n"
        "O aluno que abriu o portfolio e nunca andou responde `etapa_atual: 1`\n"
        "e `conferido_em: null`. A primeira etapa e onde todo mundo comeca, e\n"
        "nao existe estado anterior a ela.\n"
        "\n"
        "So id opaco sai daqui. Nem link, nem legenda, nem apelido, nem\n"
        "e-mail, nem nome."
    ),
)
def get_student_portfolio(request, site_id: str, aluno_id: str):
    portfolio = (
        Portfolio.objects.do_aluno(site_id=site_id, aluno_id=aluno_id)
        .select_related("estado")
        .first()
    )
    if portfolio is None:
        raise HttpError(404, f"o aluno {aluno_id} não tem portfólio em {site_id}")

    # `EstadoDoAluno` nasce quando o aluno anda pela primeira vez (degrau 07),
    # então a ausência dele é o estado normal de quem acabou de abrir a
    # Prancheta, e não um erro. O padrão é o começo do roteiro, que é a mesma
    # verdade que a linha diria se existisse.
    estado = getattr(portfolio, "estado", None)
    return PortfolioDoAluno(
        portfolio_id=str(portfolio.pk),
        etapa_atual=estado.etapa_atual if estado else PRIMEIRA_ETAPA,
        conferido_em=(
            estado.selo_conferido_em.isoformat()
            if estado and estado.selo_conferido_em
            else None
        ),
    )
