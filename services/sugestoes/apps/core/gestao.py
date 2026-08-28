# apps/core/gestao.py — o que sobrou da gestão depois que ela mudou de casa
"""As contas que a Caixa faz sobre as próprias ideias. Nenhuma tela.

**As três abas do painel viveram aqui entre 28/08/2026 e 28/08/2026** — o mesmo
dia. Elas nasceram nesta célula e mudaram para `/admin/caixa/` por decisão do
mantenedor (`docs/decisoes/DECISAO-a-gestao-da-caixa-mora-no-admin.md`): *"não
vamos espalhar painéis ou gestão por aí, tudo será em /admin"*. Os endereços
antigos agora redirecionam.

O que ficou aqui é o que só esta célula consegue calcular, porque depende de
dados que não atravessam a fronteira:

* **`plateia_de`** — quantas pessoas DISTINTAS estão atrás de cada ideia. É a
  mesma definição de `avisos.interessados_em()` ([INV-SUG13]), e o guarda que
  casa as duas continua de pé.
* **`silencio_por_pessoa`** e **`noticia_mais_recente`** — há quantos dias cada
  pessoa não ouve nada. Deduplicar quem está atrás de duas ideias exige as
  plateias como CONJUNTOS, e do outro lado da fronteira só existe a contagem por
  ideia.

O agrupamento — colunas, baldes, o que é pendência, a ordem — foi junto com as
telas, e está em `services/admin/apps/core/caixa.py`. A divisão é deliberada:
com o agrupamento aqui, cada ajuste de layout do Admin viraria mudança de
contrato, e mudança de contrato custa um Rito.
"""

from datetime import timedelta

from django.db.models import Exists, Max, OuterRef
from django.db.models.functions import Coalesce

from apps.sugestoes.models import (
    AvaliacaoInterna,
    ChangeSpecAprovado,
    Comentario,
    Sugestao,
    Voto,
)

# Quantos dias uma ideia pode ficar em "Em análise" sem ninguém da equipe
# escrever nada antes de ela contar como esquecida.
#
# Sete, e o número tem uma razão medível: é a mesma janela do freio de publicação
# do aluno (3 sugestões a cada 7 dias, spec §10). Uma pessoa que gastou uma das
# três vagas da semana dela e não ouviu nada até a semana seguinte fechar já
# esperou um ciclo inteiro do próprio limite.
#
# Ele vive nos DOIS lados hoje: aqui e no Admin, que é quem decide o que sobe
# para a mesa. Não é duplicação de FATO — é a mesma constante de produto num
# lugar que calcula e noutro que agrupa; passá-la pelo contrato a transformaria
# em promessa congelada, e mudá-la exigiria um Rito.
DIAS_ATE_A_ANALISE_ENVELHECER = 7

# A partir de quantos dias sem notícia o silêncio deixa de ser fila e vira
# alarme. Trinta: é o mês. Uma pessoa que passou um mês inteiro sem ouvir NADA
# aprendeu, na prática, que sugerir não adianta — que é exatamente o que a §5 da
# DECISAO-EVO-01 proíbe a Caixa de ensinar.
DIAS_DE_SILENCIO_DEMAIS = 30

# Os três estados em que a pessoa JÁ recebeu a resposta dela. "Recusada" conta
# como respondida de propósito: um não explicado é resposta, e tratá-lo como
# silêncio faria a conta cobrar para sempre uma dívida que já foi paga.
JA_RESPONDIDAS = (
    Sugestao.Status.IMPLEMENTADO,
    Sugestao.Status.NAO_PLANEJADO,
    Sugestao.Status.MESCLADO,
)


def plateia_de(sugestoes) -> dict[int, int]:
    """Quantas pessoas DISTINTAS estão atrás de cada ideia, em duas consultas.

    É a mesma definição de `avisos.interessados_em()` — autor, quem comentou e
    quem votou, cada pessoa contada uma vez —, e ela precisa continuar sendo a
    mesma: o número que esta tela mostra é a plateia que vai receber o aviso
    quando a ideia andar. Duas definições divergentes fariam a mesa prometer uma
    audiência e o sininho entregar outra.

    Por que não chamar `interessados_em()` num laço: ele custa duas consultas
    **por sugestão**, e esta tela mostra uma lista. Aqui são duas no total, para
    a lista inteira. Que as duas formas concordam não é confiança — é
    `test_inv_a_plateia_da_mesa_e_a_mesma_do_sininho`, que compara as duas na
    mesma sugestão e reprova se divergirem.

    Sobe para a memória uma lista de pares de ids opacos, nunca linhas de
    `Identidade` — que carregam e-mail (`DECISAO-EVO-01` §3).
    """
    ids = [sugestao.id for sugestao in sugestoes]
    gente: dict[int, set[str]] = {
        sugestao.id: {sugestao.autor_id} for sugestao in sugestoes
    }
    if not ids:
        return {}
    for sugestao_id, autor_id in Voto.objects.filter(sugestao_id__in=ids).values_list(
        "sugestao_id", "autor_id"
    ):
        gente[sugestao_id].add(autor_id)
    # `.order_by()` vazio antes do `.distinct()`: `Comentario` tem `ordering` no
    # `Meta`, e o Django acrescenta a coluna ordenada ao `SELECT DISTINCT` — o
    # distinto passaria a ser por PAR (autor, data) e não deduplicaria ninguém.
    # É a mesma pegadinha documentada em `avisos.interessados_em()`.
    for sugestao_id, autor_id in (
        Comentario.objects.filter(sugestao_id__in=ids)
        .order_by()
        .values_list("sugestao_id", "autor_id")
        .distinct()
    ):
        gente[sugestao_id].add(autor_id)
    return {sugestao_id: len(pessoas) for sugestao_id, pessoas in gente.items()}


def noticia_mais_recente(sugestoes, agora) -> dict[str, tuple[int, int]]:
    """Por PESSOA: há quantos dias foi a última notícia, e de qual ideia ela veio.

    Uma travessia só, e dela saem as duas contas que a aba 3 precisa — o silêncio
    (quantos dias) e o motivo (de qual ideia). Duas travessias separadas
    responderiam a mesma pergunta duas vezes e divergiriam no primeiro ajuste
    que só uma recebesse. Foi exatamente o que aconteceu em 28/08/2026: a versão
    anterior calculava o silêncio de cada balde isoladamente, e quem estava atrás
    de ideias em baldes diferentes era contado DUAS vezes — a soma dos motivos
    dava mais gente do que existe. Quem pegou foi o guarda da soma.

    O mínimo, e não o máximo: quem está atrás de três ideias não está em silêncio
    desde a mais parada — está em silêncio desde a última vez que ouviu qualquer
    coisa. E o desempate por id menor não é capricho: sem ele, duas ideias com o
    mesmo número de dias poriam a pessoa num balde ou noutro conforme a ordem em
    que o banco devolvesse as linhas.

    Usa a mesma definição de plateia de `plateia_de()`/`avisos.interessados_em()`
    — autor, quem comentou, quem votou —, e o guarda que casa as três é
    `test_inv_a_mesa_nao_inventa_espera.py`.
    """
    if not sugestoes:
        return {}
    dias = {sugestao.id: (agora - sugestao.parada_desde).days for sugestao in sugestoes}
    ids = list(dias)
    recente: dict[str, tuple[int, int]] = {}

    def anotar(identidade_id, sugestao_id):
        candidato = (dias[sugestao_id], sugestao_id)
        atual = recente.get(identidade_id)
        if atual is None or candidato < atual:
            recente[identidade_id] = candidato

    for sugestao in sugestoes:
        anotar(sugestao.autor_id, sugestao.id)
    for sugestao_id, autor_id in Voto.objects.filter(sugestao_id__in=ids).values_list(
        "sugestao_id", "autor_id"
    ):
        anotar(autor_id, sugestao_id)
    for sugestao_id, autor_id in (
        Comentario.objects.filter(sugestao_id__in=ids)
        .order_by()
        .values_list("sugestao_id", "autor_id")
        .distinct()
    ):
        anotar(autor_id, sugestao_id)
    return recente


def silencio_por_pessoa(sugestoes, agora) -> dict[str, int]:
    """Há quantos dias cada PESSOA não ouve nada. Derivado, nunca recalculado."""
    return {
        pessoa: dias
        for pessoa, (dias, _) in noticia_mais_recente(sugestoes, agora).items()
    }
