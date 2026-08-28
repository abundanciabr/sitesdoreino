"""Quem pode LER e quem pode ESCREVER em cada área — fail-CLOSED, e por DADO.

**As permissões moram no dado, não no código** (`DECISAO-forum-da-escola.md`
§5, recomendação do consultor 1 na rodada de 28/08). O mantenedor decidiu áreas
MISTAS: umas públicas e indexáveis pelo Google, outras trancadas por curso ou
turma. Escrever isso em `if` espalhado por views transformaria cada área nova
numa entrega de código; como dado, uma área nova é uma linha na tabela.

**Fail-closed é a regra, e ela aparece na forma das funções:** cada uma começa
supondo NÃO e só devolve `True` num caso explicitamente nomeado. Nada de
`if bloqueado: return False` no fim — essa forma libera tudo que alguém
esquecer de listar.
"""

from __future__ import annotations

from apps.forum.models import Area

from .sessao import Ator


def pode_ler(area: Area, ator: Ator) -> bool:
    """A área é visível para este Ator?

    - **Pública:** qualquer um, inclusive visitante e o robô do Google. É a
      aposta de crescimento da escola: dúvida respondida é porta de entrada
      gratuita e permanente.
    - **Alunos:** exige matrícula válida, conferida na `alunos`.
    - **Turma:** exige matrícula E o curso certo. Enquanto o fórum não souber
      perguntar "esta pessoa está NESTE curso?", **ninguém entra** — que é o
      lado seguro do erro, e está travado em teste.
    """
    if not area.ativa:
        return False

    if area.visibilidade == Area.Visibilidade.PUBLICA:
        return True

    # Daqui para baixo, tudo exige pelo menos ser aluno.
    if ator.eh_equipe:
        return True
    if not ator.eh_aluno:
        return False

    if area.visibilidade == Area.Visibilidade.ALUNOS:
        return True

    if area.visibilidade == Area.Visibilidade.TURMA:
        # AINDA NÃO IMPLEMENTADO, e fecha de propósito. Saber se alguém está
        # num curso específico é uma pergunta que o fórum ainda não faz à
        # `alunos`. Devolver `True` aqui "para não travar" seria abrir a área
        # mais restrita do sistema — o oposto do que o nome dela promete.
        return False

    # Visibilidade desconhecida (dado novo, código velho) ⇒ fechado.
    return False


def pode_escrever(area: Area, ator: Ator) -> bool:
    """Este Ator pode abrir tópico ou responder nesta área?

    Escrever exige, SEMPRE, poder ler — e mais um degrau, declarado no campo
    `quem_escreve` da área.
    """
    if not pode_ler(area, ator):
        return False

    if area.quem_escreve == Area.QuemEscreve.EQUIPE:
        return ator.eh_equipe

    if area.quem_escreve == Area.QuemEscreve.ALUNO:
        return ator.eh_aluno or ator.eh_equipe

    if area.quem_escreve == Area.QuemEscreve.CADASTRADO:
        # O único caso que aceita quem tem login sem ter comprado — e é o que
        # EXIGE defesa anti-spam de verdade antes de ser usado numa área
        # pública (`DECISAO-forum-da-escola.md` §6.3, pergunta em aberto).
        return ator.autenticado

    return False


def areas_visiveis(ator: Ator):
    """As áreas que este Ator enxerga, na ordem da tela.

    Filtra em Python de propósito, e não numa `QuerySet` com `Q(...)`: a regra
    de leitura vive numa função só (`pode_ler`), e duas expressões da mesma
    regra — uma em SQL, outra em Python — divergem no primeiro dia em que
    alguém mexer numa delas. O número de áreas de um fórum de escola é dezenas,
    não milhões; quando deixar de ser, a otimização vem com um teste que compare
    as duas.
    """
    return [a for a in Area.objects.filter(ativa=True) if pode_ler(a, ator)]
