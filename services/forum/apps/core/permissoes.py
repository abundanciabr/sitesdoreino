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


def pode_moderar(ator: Ator) -> bool:
    """Este Ator enxerga as ferramentas de moderação do fórum?

    **A ESCOLA: professor ou administrador.** O pedido de 30/08/2026 nasceu
    como *"as opções que devem aparecer apenas para o Admin"*, e a pergunta que
    ele deixou aberta (o professor herda isto?) foi levada ao mantenedor no
    mesmo dia. **Ele respondeu: professor também, com tudo** — os mesmos
    poderes, inclusive deixar área privada, arquivar e criar área nova. A
    resposta mora no livro (`painel/registros/`), que é a casa dela; aqui fica
    só o mecanismo.

    É a lei §5 sendo cumprida: *"o papel de professor nasce com o fórum, com
    autoridade real: resposta com selo, poder de marcar dúvida como resolvida,
    moderar sem ser dono do sistema"*. "Sem ser dono do sistema" é o que ele
    continua sendo: professor não abre a VPS, não mexe no painel do dono, não
    entra em `/admin`. Dentro do fórum, modera igual.

    **Fail-closed de ponta a ponta:** as duas listas (`FORUM_PROFESSORES` e
    `ADMIN_EMAILS`) saem do env, e env ausente ou vazio significa *ninguém*
    (`apps/core/sessao.py`). Fórum sem as listas é fórum sem moderador, nunca
    fórum de portas abertas. Hoje `FORUM_PROFESSORES` está vazio na VPS: pôr um
    e-mail lá é o gesto que dá as ferramentas a um professor, e é do mantenedor.
    """
    return ator.eh_equipe


def pode_ler(area: Area, ator: Ator) -> bool:
    """A área é visível para este Ator?

    - **Pública:** qualquer um, inclusive visitante e o robô do Google. É a
      aposta de crescimento da escola: dúvida respondida é porta de entrada
      gratuita e permanente.
    - **Alunos:** exige matrícula válida, conferida na `alunos`.
    - **Turma:** exige matrícula E o curso certo. Enquanto o fórum não souber
      perguntar "esta pessoa está NESTE curso?", **ninguém entra** — que é o
      lado seguro do erro, e está travado em teste.
    - **Arquivada:** some para todo mundo, menos para quem consegue desarquivar.
    """
    if not area.ativa:
        # ARQUIVAR PRECISA TER VOLTA. Arquivar é o "apagar" honesto desta casa
        # (nada sai do banco), e se a área arquivada sumisse também para quem
        # modera, o gesto viraria porta de mão única: reabrir exigiria
        # alguém com acesso ao banco. Para o resto do mundo, arquivada continua
        # indistinguível de inexistente — inclusive para o robô do Google.
        return pode_moderar(ator)

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


# As três recusas possíveis, ditas em português para quem está do outro lado da
# tela. Ficam AQUI, e não no template, porque a razão da recusa é a mesma regra
# que a produz — separá-las é o começo de duas verdades sobre a mesma coisa.
PRECISA_ENTRAR = "entrar"
PRECISA_SER_ALUNO = "matricula"
SO_A_ESCOLA_FALA = "equipe"
NAO_SE_APLICA = ""


def pode_escrever(area: Area, ator: Ator) -> bool:
    """Este Ator pode abrir tópico ou responder nesta área?

    Três degraus, nesta ordem, e todos precisam passar:

    1. **Poder ler.** Nunca se escreve onde não se enxerga.
    2. **Estar logado.** Escrita é SEMPRE atrás do login — mandato do
       mantenedor em 30/08/2026 (registro `20260830-021`). Visitante não
       escreve em lugar nenhum, nem numa área que aceite "qualquer cadastrado".
    3. **O degrau da área**, declarado em `quem_escreve` — com uma exceção que
       vem por cima de tudo: **em página PÚBLICA, só a escola fala.**

    O passo 3 tem cinto e suspensório: a combinação "área pública onde aluno
    escreve" também é recusada pelo BANCO (`Area.Meta.constraints`,
    `pagina_publica_so_a_escola_fala`). A conferência aqui não é redundância
    ociosa — é o que decide cada requisição, e o que continua valendo se um dia
    alguém dropar a restrição para "destravar" um incidente.
    """
    return por_que_nao_escreve(area, ator) == NAO_SE_APLICA


def por_que_nao_escreve(area: Area, ator: Ator) -> str:
    """A MESMA regra de `pode_escrever`, dizendo qual degrau reprovou.

    Devolve `NAO_SE_APLICA` (string vazia) quando a pessoa PODE escrever. A tela
    usa isto para dizer a verdade em vez de esconder o formulário em silêncio —
    "você precisa entrar" e "você precisa estar matriculado" são recusas
    diferentes, e quem lê merece saber qual das duas levou.

    **Uma função só, dois usos.** `pode_escrever` é esta função com os olhos
    fechados. Se a razão morasse num `if` paralelo, ela divergiria da regra no
    primeiro dia em que alguém mexesse numa das duas — e a tela passaria a
    convidar para entrar numa área onde entrar não resolve.
    """
    if not pode_ler(area, ator):
        # Quem não pode nem ler não chega a ver esta tela (a view responde 404
        # antes). Se chegasse, a recusa honesta é a mais fechada de todas.
        return PRECISA_SER_ALUNO

    # ESCREVER É SEMPRE ATRÁS DO LOGIN (mandato de 30/08/2026).
    if not ator.autenticado:
        return PRECISA_ENTRAR

    # EM PÁGINA PÚBLICA, SÓ A ESCOLA FALA. Vem antes de `quem_escreve` de
    # propósito: mesmo que o dado dissesse `aluno` — dado velho, restrição
    # dropada à mão, bug de migração —, a página que estranhos leem sem login
    # continua sendo só a voz da escola.
    if area.visibilidade == Area.Visibilidade.PUBLICA:
        return NAO_SE_APLICA if ator.eh_equipe else SO_A_ESCOLA_FALA

    if area.quem_escreve == Area.QuemEscreve.EQUIPE:
        return NAO_SE_APLICA if ator.eh_equipe else SO_A_ESCOLA_FALA

    if area.quem_escreve == Area.QuemEscreve.ALUNO:
        return NAO_SE_APLICA if (ator.eh_aluno or ator.eh_equipe) else PRECISA_SER_ALUNO

    if area.quem_escreve == Area.QuemEscreve.CADASTRADO:
        # Quem tem login sem ter comprado. O mantenedor decidiu em 30/08/2026
        # que **não** é assim que o fórum nasce (só aluno matriculado escreve),
        # e nenhuma área semeada usa este valor — ele fica no vocabulário para
        # o dia em que ele quiser abrir uma área trancada. Numa área pública
        # ele é impossível: a restrição do banco recusa.
        return NAO_SE_APLICA

    # Valor desconhecido (dado novo, código velho) ⇒ fechado.
    return SO_A_ESCOLA_FALA


def areas_visiveis(ator: Ator):
    """As áreas que este Ator enxerga, na ordem da tela.

    Filtra em Python de propósito, e não numa `QuerySet` com `Q(...)`: a regra
    de leitura vive numa função só (`pode_ler`), e duas expressões da mesma
    regra — uma em SQL, outra em Python — divergem no primeiro dia em que
    alguém mexer numa delas. O número de áreas de um fórum de escola é dezenas,
    não milhões; quando deixar de ser, a otimização vem com um teste que compare
    as duas.

    **E é por isso que a consulta não filtra `ativa=True`.** O filtro em SQL
    seria a segunda expressão da regra: quem decide se área arquivada aparece é
    `pode_ler` (e ela aparece para quem modera, senão arquivar não teria
    volta). Filtrar aqui teria escondido a área arquivada até dele, e o defeito
    seria invisível — a home simplesmente não a mostraria, sem erro nenhum.
    """
    return [a for a in Area.objects.all() if pode_ler(a, ator)]
