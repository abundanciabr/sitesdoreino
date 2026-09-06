"""O laudo: a decisão da professora (ou, nas Fases 4/5, do par ou da Banca)
sobre um envio, as nove regras que o recusam antes de gravar nada, e os três
eventos que a decisão dispara.

Lei: `docs/decisoes/PLANO-CELULA-CURSOS.md` §4 (`Laudo`), §5 (os três
eventos), §6 (o plantão), §9 ([INV-CUR-L1], [INV-CUR-L2], [INV-CUR-L5],
[INV-CUR-L6], [INV-CUR-L7]). Degrau 2.2 (TAR-156). Molde de forma:
`apps/cursos/envio.py` (as regras fora da view, a recusa como exceção com
frase para gente, `criterios_de` reutilizada e não duplicada).

A ORDEM DAS NOVE VALIDAÇÕES NÃO É ARBITRÁRIA
---------------------------------------------
`emitir()` valida NESTA ordem, para que o 422 diga a causa MAIS ESPECÍFICA
primeiro: (1) a rubrica completa, uma nota+frase por critério; (2) exatamente
três forças, nenhuma genérica; (3) exatamente uma mudança, com aula que existe
no curso; (4) a decisão está no vocabulário fechado (não existe uma quarta
decisão negativa, [INV-CUR-L2]); (5) `aberto_com_ajuste` exige o ajuste feito; (6) `devolvido`
exige data de retorno de amanhã em diante ([INV-CUR-L1]); (7) a pergunta de
amanhã de manhã só aceita `true` ([INV-CUR-L7]). Só depois de as sete passarem
é que qualquer linha é gravada.

`mudanca` CHEGA COMO LISTA, NUNCA COMO UM DICIONÁRIO SOLTO
------------------------------------------------------------
O modelo grava UM objeto (`Laudo.mudanca`, `{texto, aula_id}`), mas o
parâmetro desta função recebe uma LISTA: é o que permite ao guarda provar, por
mutação, que zero ou duas mudanças são recusadas, e não só documentadas — um
parâmetro que já nasce como dicionário único não teria como testar "e se
vierem duas". O formulário do plantão (que só tem um campo de mudança) sempre
manda uma lista de um item.

O QUE ESTA FUNÇÃO NÃO DECIDE
------------------------------
Quem PODE chamar `emitir()` (quem está no plantão, fail-closed pela união de
`CURSOS_PROFESSORES` com `ADMIN_EMAILS`) é `apps/core/sessao.py` +
`apps/core/views.py`. Esta
função recebe o `avaliador` já resolvido e confia nele: não pergunta a
`identidade` nem a `alunos`.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from django.db import transaction
from django.utils import timezone

from . import eventos
from . import progresso as portas
from .envio import criterios_de
from .models import Aula, Envio, Laudo, Pessoa, Progresso, RascunhoDaIA

# As frases "força" que não dizem nada específico sobre o trabalho da pessoa.
# Comparação por igualdade, sem acento removido: são frases fixas, escritas
# para o campo de força, não um filtro de palavrão. Case-insensitive e sem
# espaço nas pontas, porque "Ficou bom!" e "ficou bom" são a mesma recusa.
FORCAS_GENERICAS = frozenset(
    {"bonito", "legal", "bom trabalho", "ficou bom", "parabéns"}
)


class LaudoRecusado(Exception):
    """O laudo não é gravado. A mensagem é escrita para quem lê a tela do
    plantão, e cita o invariante entre parênteses para quem lê o log."""


def _validar_rubrica(instrumento, notas: Any) -> dict:
    """[INV-CUR-L5] Uma nota (dentro da escala) e uma frase por critério, antes
    de qualquer campo livre. Sem critério nenhum (aula sem instrumento com
    escala), a rubrica é vazia por definição: não há o que exigir."""
    criterios = criterios_de(instrumento)
    dadas = notas if isinstance(notas, dict) else {}
    limpas: dict[str, dict[str, Any]] = {}
    for criterio in criterios:
        item = dadas.get(criterio.nome)
        item = item if isinstance(item, dict) else {}
        nota, frase = item.get("nota"), str(item.get("frase") or "").strip()
        if (
            isinstance(nota, bool)
            or not isinstance(nota, int)
            or not (criterio.minimo <= nota <= criterio.maximo)
        ):
            raise LaudoRecusado(
                f"A rubrica está incompleta: dê uma nota de {criterio.minimo} a "
                f"{criterio.maximo} em {criterio.nome} antes de qualquer campo "
                "livre (INV-CUR-L5)."
            )
        if not frase:
            raise LaudoRecusado(
                f"Escreva uma frase observável para a nota de {criterio.nome}: "
                "nota sem frase não diz nada (INV-CUR-L5)."
            )
        limpas[criterio.nome] = {"nota": nota, "frase": frase}
    return limpas


def validar_forcas(forcas: Any) -> list[str]:
    """[INV-CUR-L6] Exatamente três forças, nenhuma da lista de genéricos."""
    limpas = [str(f or "").strip() for f in (forcas or []) if str(f or "").strip()]
    if len(limpas) != 3:
        raise LaudoRecusado(
            "São exatamente três forças, nem mais nem menos: cada uma "
            "específica sobre o trabalho desta pessoa (INV-CUR-L6)."
        )
    genericas = [f for f in limpas if f.lower() in FORCAS_GENERICAS]
    if genericas:
        raise LaudoRecusado(
            f'"{genericas[0]}" é genérica demais para dizer o que ficou bom: '
            "escreva o que especificamente funcionou (INV-CUR-L6)."
        )
    return limpas


def _validar_mudanca(curso, mudanca: Any) -> dict:
    """[INV-CUR-L6] Exatamente uma mudança, com a aula onde se aprende, e essa
    aula existe neste curso."""
    itens = mudanca if isinstance(mudanca, list) else []
    if len(itens) != 1:
        raise LaudoRecusado(
            "É exatamente uma mudança: a mais específica para a próxima "
            "entrega, nunca uma lista (INV-CUR-L6)."
        )
    item = itens[0] if isinstance(itens[0], dict) else {}
    texto = str(item.get("texto") or "").strip()
    if not texto:
        raise LaudoRecusado("Escreva o texto da mudança pedida.")
    aula_id = item.get("aula_id")
    try:
        existe = Aula.objects.filter(pk=aula_id, curso=curso).exists()
    except (TypeError, ValueError):
        existe = False
    if not existe:
        raise LaudoRecusado(
            "A mudança precisa apontar para uma aula que existe neste curso "
            "(INV-CUR-L6)."
        )
    return {"texto": texto, "aula_id": str(aula_id)}


def _medir_a_ficha_de_serie(
    rascunho: RascunhoDaIA, forcas: list[str], mudanca: dict
) -> None:
    """A Ficha de Série do Assistente de laudo, medida DO DADO na emissão.

    Lei §7: "`RascunhoDaIA` × `Laudo`: forças mantidas sem edição, mudança
    mantida". As duas medidas saem da comparação entre o que a IA propôs e o
    que a professora assinou, aqui, no único instante em que os dois existem
    lado a lado. Nenhum robô anota isto à mão depois, e nenhuma tela guarda um
    número próprio: a Ficha se calcula do livro que estas duas colunas formam.

    **"Mantida" é IGUAL, letra por letra (sem espaço nas pontas), não parecida.**
    A pergunta que a Ficha responde é "a professora aproveitou a sugestão como
    ela veio?", e uma força que ela reescreveu inteira, mesmo que dizendo o
    mesmo, é trabalho dela, não do agente. Uma comparação frouxa faria a Ficha
    subir sozinha no dia em que alguém trocasse uma vírgula.

    Escreve só as duas colunas, e de propósito: o `conteudo` do rascunho é o que
    a IA disse, e reescrevê-lo aqui apagaria a prova contra a qual a medida foi
    feita.

    A contagem varre as forças ASSINADAS, nunca as sugeridas, e é o que mantém a
    medida dentro da restrição do banco (no máximo três): `validar_forcas` já
    garantiu que as assinadas são exatamente três, enquanto um `conteudo` com
    cinco forças escritas à mão faria a varredura da outra ponta contar cinco.
    """
    sugerido = rascunho.conteudo if isinstance(rascunho.conteudo, dict) else {}
    sugeridas = sugerido.get("forcas")
    sugeridas = {
        str(f).strip() for f in (sugeridas if isinstance(sugeridas, list) else [])
    }
    rascunho.forcas_mantidas = sum(1 for f in forcas if f.strip() in sugeridas)

    sugerida = sugerido.get("mudanca")
    sugerida = sugerida if isinstance(sugerida, dict) else {}
    rascunho.mudanca_mantida = (
        str(sugerida.get("texto") or "").strip() == mudanca["texto"]
    )
    rascunho.save(update_fields=["forcas_mantidas", "mudanca_mantida"])


def emitir(
    envio: Envio,
    *,
    avaliador: Pessoa,
    papel: str,
    notas: dict,
    forcas: list,
    mudanca: list,
    decisao: str,
    data_de_retorno: date | None = None,
    ajuste_feito: str | None = None,
    sabe_o_que_fazer_amanha: bool | None = None,
    rascunho: RascunhoDaIA | None = None,
) -> Laudo:
    """O laudo fecha (`aberto`/`aberto_com_ajuste`, e a porta seguinte abre) ou
    devolve (`devolvido`, e o envio volta para reenvio) o envio, sempre com os
    três eventos, na mesma transação. Levanta `LaudoRecusado` (a causa mais
    específica primeiro) antes de gravar qualquer coisa.

    `rascunho` é a sugestão do Assistente de laudo (degrau 2.3) quando o laudo
    nasceu de uma. Ele NÃO decide nada aqui: nem a decisão, nem a data, nem a
    pergunta de amanhã de manhã saem dele ([INV-CUR-L4]) — todos os três chegam
    pelos parâmetros acima, do formulário que a professora assinou. O que a
    presença dele muda é uma coisa só: a Ficha de Série do agente é medida na
    emissão (`_medir_a_ficha_de_serie`).
    """
    if papel not in Laudo.Papel.values:
        raise LaudoRecusado(
            f"papel de avaliador desconhecido: {papel!r}. É professor, par ou banca."
        )

    # (1) e (2) e (3): a rubrica, as forças, a mudança. Nenhuma delas toca o
    # banco: são puras, e por isso rodam ANTES de qualquer trava de linha.
    notas_limpas = _validar_rubrica(envio.aula.instrumento, notas)
    forcas_limpas = validar_forcas(forcas)
    mudanca_limpa = _validar_mudanca(envio.aula.curso, mudanca)

    # (4) a decisão está no vocabulário fechado. [INV-CUR-L2]: não existe uma
    # quarta decisão negativa — qualquer palavra fora das três de
    # `Laudo.Decisao.values` cai aqui, encerrar não é uma decisão que exista.
    if decisao not in Laudo.Decisao.values:
        raise LaudoRecusado(
            "A decisão é aberto, aberto com ajuste ou devolvido: não existe "
            "uma quarta decisão. Devolver é pedir mais uma volta com data "
            "marcada, nunca encerrar (INV-CUR-L2)."
        )

    # (5) aberto com ajuste exige o ajuste feito.
    ajuste_limpo = (ajuste_feito or "").strip()
    if decisao == Laudo.Decisao.ABERTO_COM_AJUSTE and not ajuste_limpo:
        raise LaudoRecusado(
            "Aberto com ajuste precisa dizer qual foi o ajuste feito: sem "
            "isso, a pessoa não sabe o que já foi resolvido por ela."
        )
    if decisao != Laudo.Decisao.ABERTO_COM_AJUSTE:
        ajuste_limpo = ""

    # (6) [INV-CUR-L1] devolvido exige data de retorno de amanhã em diante, no
    # dia de São Paulo (`TIME_ZONE`, `tests/test_fuso_horario.py`).
    data_final: date | None = None
    if decisao == Laudo.Decisao.DEVOLVIDO:
        amanha = timezone.localdate() + timedelta(days=1)
        if data_de_retorno is None or data_de_retorno < amanha:
            raise LaudoRecusado(
                "Devolvido exige uma data de retorno de amanhã em diante: a "
                "escola devolve com data marcada, nunca sem ela (INV-CUR-L1)."
            )
        data_final = data_de_retorno

    # (7) [INV-CUR-L7] a pergunta de amanhã de manhã: só `true` grava. `None`
    # (não respondida) e `False` (respondida negativamente) são a MESMA
    # recusa: não se registra recusa, se conversa antes de enviar o laudo.
    if sabe_o_que_fazer_amanha is not True:
        raise LaudoRecusado(
            "A pergunta de amanhã de manhã não se recusa: não se registra "
            "recusa. Sem certeza de que a pessoa sabe o que fazer amanhã, "
            "converse antes de enviar o laudo (INV-CUR-L7)."
        )

    with transaction.atomic():
        # A trava é no ENVIO (a unicidade que o `OneToOneField` de `Laudo`
        # impõe): dois cliques no mesmo segundo serializam aqui, e o segundo
        # encontra o laudo já gravado e é recusado com a frase certa, em vez
        # de um `IntegrityError` cru.
        envio_travado = Envio.objects.select_for_update().get(pk=envio.pk)
        if Laudo.objects.filter(envio=envio_travado).exists():
            raise LaudoRecusado("Este envio já recebeu um laudo: um envio, um laudo.")

        instrumento = envio_travado.aula.instrumento
        laudo = Laudo.objects.create(
            envio=envio_travado,
            avaliador=avaliador,
            papel=papel,
            instrumento_versao=instrumento.versao if instrumento else None,
            notas=notas_limpas,
            forcas=forcas_limpas,
            mudanca=mudanca_limpa,
            ajuste_feito=ajuste_limpo,
            decisao=decisao,
            data_de_retorno=data_final,
            sabe_o_que_fazer_amanha=True,
            rascunho=rascunho,
        )
        if rascunho is not None:
            # DENTRO da transação: uma Ficha de Série que sobrevivesse a um
            # laudo desfeito mediria um laudo que não existe.
            _medir_a_ficha_de_serie(rascunho, forcas_limpas, mudanca_limpa)
        envio_travado.estado = decisao
        envio_travado.save(update_fields=["estado"])
        eventos.emitir_laudo_emitido(laudo)

        progresso = Progresso.objects.select_for_update().get(
            pessoa_id=envio_travado.pessoa_id, aula_id=envio_travado.aula_id
        )
        if decisao in portas.DECISOES_QUE_ABREM:
            # `progresso.concluir` é o ÚNICO lugar que grava `concluida`
            # ([INV-CUR-P2]); esta função consome-o por nome, nunca reimplementa
            # a regra.
            portas.concluir(progresso, laudo=laudo)
            eventos.emitir_aula_concluida(
                envio_travado.aula, ator_id=envio_travado.pessoa_id
            )
        else:
            # `devolvido`: a porta NÃO conclui — `progresso.py` não tem (e não
            # precisa ter) uma função "devolver", porque devolver não é uma
            # NOVA regra de porta: é o mesmo campo que `Progresso` já reserva
            # para isto (`data_de_retorno`, "se devolvida") voltando a
            # `devolvida`, para que `envio.entregar` aceite o reenvio
            # (`ESTADOS_QUE_ENTREGAM`). `progresso.py` continua sendo o único
            # lugar que grava `concluida`; devolver não é concluir.
            progresso.estado = Progresso.Estado.DEVOLVIDA
            progresso.data_de_retorno = laudo.data_de_retorno
            progresso.save(update_fields=["estado", "data_de_retorno"])
            eventos.emitir_checkpoint_devolvido(laudo)

    return laudo
