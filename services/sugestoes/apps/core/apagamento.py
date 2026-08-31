# apps/core/apagamento.py
"""O apagamento definitivo de uma ideia, num lugar só.

`DECISAO-apagar-ideia.md` (29/08/2026) decidiu O QUE acontece: a "lousa
apagada" — título, problema e solução viram vazio, votos e comentários somem
de verdade (de QUALQUER pessoa que participou, não só do autor), e a LINHA
continua no banco, porque `HistoricoStatus`, `ChangeSpecAprovado` e `Aviso`
apontam para ela com `PROTECT` e são append-only em três degraus. Apagar a
linha exigiria desmontar justamente a trava que esta casa construiu com
cuidado extra.

POR QUE ISTO SAIU DE DENTRO DO ENDPOINT
---------------------------------------
Até 31/08/2026 a regra morava no corpo de `api_gestao.apagar()`, e o único
caminho para apagar era o botão do Admin. Nesse dia o mantenedor pediu um
caminho pelo pipeline para esvaziar a Caixa sem abrir tela nenhuma
(`manage.py esvaziar_caixa`), e a alternativa preguiçosa era escrever a mesma
sequência de novo lá dentro.

Duas cópias da mesma regra é como um "apagar" que limpa o título num caminho e
esquece os comentários no outro: toda mudança futura precisa ser lembrada duas
vezes, e na primeira vez que alguém esquecer, o conteúdo que a decisão promete
destruir sobrevive em silêncio, sem erro nenhum na tela. Uma função só,
chamada pelos dois, faz o comando herdar o comportamento do botão por
construção — inclusive o que ele DELIBERADAMENTE não toca: o histórico da
equipe e a avaliação interna, que nunca guardaram o texto da pessoa.

`quem` é opcional porque o pipeline não é uma pessoa. `apagada_por` e
`arquivada_por` nasceram nuláveis (`models.py`), e gravar `NULL` ali é a
resposta honesta para "quem apagou?" quando a resposta é "um passo automático
que o mantenedor disparou", em vez de cunhar uma identidade de fachada para
preencher a coluna.
"""

from django.utils import timezone

from apps.sugestoes.models import Aviso, Comentario, Sugestao, Voto

CAMPOS_GRAVADOS = [
    "titulo",
    "problema",
    "solucao_proposta",
    "apagada_em",
    "apagada_por",
    "arquivada_em",
    "arquivada_por",
]


def apagar_definitivamente(sugestao: Sugestao, quem=None, agora=None) -> bool:
    """Destrói o conteúdo legível da ideia. Devolve `False` se já estava apagada.

    Idempotente de propósito: quem chama em lote (o comando que esvazia a
    Caixa) não precisa filtrar antes, e quem chama pela API traduz o `False`
    na recusa 422 que o contrato promete.
    """
    if sugestao.apagada_em is not None:
        return False

    agora = agora or timezone.now()
    Voto.objects.filter(sugestao=sugestao).delete()
    Comentario.objects.filter(sugestao=sugestao).delete()
    # O recado também vai. `Aviso` NÃO é append-only (só `HistoricoStatus` e
    # `ChangeSpecAprovado` são, com trigger no Postgres): apagar estas linhas
    # não encosta na trava que protege a auditoria da equipe.
    #
    # Esta é a cópia LOCAL do recado. A que a pessoa realmente lê hoje mora na
    # caixa central (`notificacoes`), e o contrato congelado dela só sabe
    # listar e marcar como lida — não retirar. Por isso o sumiço visível é
    # feito na leitura (`avisos.py::_sobre_ideia_apagada`), e esta linha é a
    # metade que ESTA célula consegue destruir de verdade. As duas juntas são
    # o mínimo para a promessa da `DECISAO-apagar-ideia.md` valer também para
    # quem recebeu o aviso; o que falta para ela valer inteira é uma operação
    # de retirada na caixa central, que é mudança de contrato (Rito §3).
    Aviso.objects.filter(sugestao=sugestao).delete()
    sugestao.titulo = ""
    sugestao.problema = ""
    sugestao.solucao_proposta = ""
    sugestao.apagada_em = agora
    sugestao.apagada_por = quem
    # Apagada é sempre arquivada: nenhuma superfície do aluno ou da gestão
    # precisa aprender um segundo carimbo para saber que isto sumiu — a única
    # NOVIDADE que `apagada` acrescenta é "não há mais nada para restaurar".
    sugestao.arquivada_em = sugestao.arquivada_em or agora
    sugestao.arquivada_por = sugestao.arquivada_por or quem
    sugestao.save(update_fields=CAMPOS_GRAVADOS)
    return True
