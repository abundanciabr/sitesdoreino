"""As regras da porta: que aula abre, quando, e por quem.

**O checkpoint abre a porta; o calendário, nunca** (a missão da célula). Este
arquivo é o único lugar onde uma porta muda de estado, e é por isso que os
três invariantes da porta (`PLANO-CELULA-CURSOS.md` §9) são impostos aqui:

- **[INV-CUR-P2]** a porta seguinte abre por UMA de duas regras, e a regra é
  dado do curso (`Curso.progressao`, escolhida pelo mantenedor no cadastro,
  `DECISAO-a-sala-serve-varios-cursos.md` §3): no curso por laudo (o padrão, e
  o do livro), `concluir` EXIGE um laudo com decisão `aberto` ou
  `aberto_com_ajuste`; no curso de progressão livre, `concluir_por_gesto`
  EXIGE que o curso seja livre e que as pausas estejam registradas. Cada
  função RECUSA o curso da outra. Em nenhuma das duas há parâmetro de data, de
  XP nem de pagamento, e as duas gravam `concluida` pelo mesmo miolo
  (`_concluir`), que é o único lugar que grava esse valor. Guarda:
  `tests/test_inv_p2_a_porta_so_abre_por_laudo.py`.
- **[INV-CUR-P3]** `pausas_registradas` é a pergunta que o formulário do
  checkpoint (degrau 2.1) faz antes de abrir: só é verdadeira com TODAS as
  pausas da aula registradas. Guarda:
  `tests/test_inv_p3_checkpoint_fechado_ate_as_pausas.py`.

A regra de vizinhança: a aula N sai de `trancada` quando a N-1 conclui, pela
`ordem`. A bônus (EB, ordem 33) fica disponível quando a E32 (ordem 32) conclui
e não tranca ninguém, porque nada vem depois dela; a E32 não depende dela,
porque a EB vem depois. É a mesma regra, sem caso especial.

Molde de forma: `services/gamificacao/apps/gamificacao/validacao.py` (as
regras fora da view, a recusa como exceção com frase para gente).
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from . import eventos
from .models import Aula, Curso, Pessoa, Progresso, RegistroDePausa

# As duas decisões de laudo que abrem a porta seguinte. Escritas aqui como
# dado desta célula, e não importadas de lugar nenhum: o vocabulário do laudo
# nasce no degrau 2.2, e travá-lo aqui é o que faz uma decisão nova
# ("reprovado", que a lei proíbe) aparecer como teste vermelho em vez de porta
# aberta.
DECISOES_QUE_ABREM = frozenset({"aberto", "aberto_com_ajuste"})

# As frases da recusa que a tela mostra no lugar do botão de concluir. Moram
# aqui, e não em `envio.py`, porque no curso livre não existe checkpoint: a
# frase do checkpoint ("fica fechado até...") falaria de uma seção que a tela
# desse curso não tem.
SO_COM_AS_PAUSAS = "Esta aula só conclui depois de todas as pausas dela terem registro."
SO_POR_LAUDO = (
    "Neste curso a porta seguinte só abre com o laudo da professora: entregue "
    "o checkpoint."
)
SO_NO_CURSO_LIVRE = (
    "Este curso não tem entrega de checkpoint: a aula conclui pelo botão "
    "Concluir esta aula."
)


class PortaRecusada(Exception):
    """A porta não muda. A mensagem é escrita para quem lê a tela."""


def progresso_de(pessoa: Pessoa, aula: Aula) -> Progresso | None:
    """A linha desta pessoa nesta aula, ou `None`: linha ausente é porta trancada."""
    return Progresso.objects.filter(pessoa=pessoa, aula=aula).first()


def nascer(pessoa: Pessoa, curso: Curso) -> Progresso | None:
    """A primeira porta (E00) nasce `disponivel` para quem tem matrícula ativa.

    Chamada na primeira visita à sala, e em toda visita depois dela: o
    `get_or_create` faz a segunda ser inerte. `None` só quando o curso não tem
    aula nenhuma, que é o estado de um site sem esqueleto semeado.
    """
    primeira = curso.aulas.order_by("ordem").first()
    if primeira is None:
        return None
    progresso, _ = Progresso.objects.get_or_create(
        pessoa=pessoa,
        aula=primeira,
        defaults={"estado": Progresso.Estado.DISPONIVEL},
    )
    return progresso


def abrir(progresso: Progresso) -> Progresso:
    """`disponivel` vira `em_producao` na primeira abertura da aula.

    Qualquer outro estado fica como está: abrir uma aula devolvida não a
    devolve de novo, e abrir uma concluída não a desfaz.
    """
    if progresso.estado == Progresso.Estado.DISPONIVEL:
        progresso.estado = Progresso.Estado.EM_PRODUCAO
        progresso.save(update_fields=["estado"])
    return progresso


def concluir(progresso: Progresso, *, laudo) -> Progresso:
    """No curso por laudo, a porta seguinte abre SÓ por um laudo aberto
    ([INV-CUR-P2], a regra do livro).

    `laudo` é o único caminho: qualquer objeto cuja `decisao` seja `aberto` ou
    `aberto_com_ajuste`. Não existe parâmetro de data, de XP nem de pagamento,
    e é a assinatura desta função, medida no guarda, que prova a ausência. O
    que acontece com a porta depois da validação é o miolo comum, `_concluir`.
    """
    if progresso.aula.curso.progressao != Curso.Progressao.POR_LAUDO:
        raise PortaRecusada(SO_NO_CURSO_LIVRE)
    decisao = getattr(laudo, "decisao", None)
    if decisao not in DECISOES_QUE_ABREM:
        raise PortaRecusada(
            "A porta seguinte só abre com um laudo que diga aberto ou aberto "
            "com ajuste. Sem laudo, ou com laudo devolvido, ela fica como está."
        )
    _concluir(progresso)
    return progresso


def concluir_por_gesto(progresso: Progresso) -> Progresso:
    """No curso de progressão LIVRE, o próprio aluno conclui a aula, e a
    seguinte abre ([INV-CUR-P2], a segunda regra).

    Exige, nesta ordem: o curso ser livre (no curso por laudo esta função
    recusa, e `concluir` é o único caminho), as pausas registradas
    ([INV-CUR-P3] vale igual nos dois cursos), e a porta não trancada. Uma
    concluída fica concluída, e o segundo gesto não emite evento nenhum.

    O evento `aula.concluida.v1` nasce AQUI, dentro da mesma transação da
    porta: no curso por laudo quem o emite é `laudo.emitir`, porque lá a
    conclusão é parte de uma transação maior (o laudo, o envio, os três
    eventos). É o mesmo `eventos.emitir_aula_concluida` nos dois casos.
    """
    if progresso.aula.curso.progressao != Curso.Progressao.LIVRE:
        raise PortaRecusada(SO_POR_LAUDO)
    if not pausas_registradas(progresso):
        raise PortaRecusada(SO_COM_AS_PAUSAS)
    with transaction.atomic():
        if _concluir(progresso):
            eventos.emitir_aula_concluida(progresso.aula, ator_id=progresso.pessoa_id)
    return progresso


def _concluir(progresso: Progresso) -> bool:
    """O miolo das duas regras: a porta vira `concluida`, carimba a hora, deixa
    a cerimônia pendente se a aula é boss, e abre a `ordem + 1`. Tudo numa
    transação. Devolve `True` quando concluiu AGORA, `False` na já concluída.

    Uma porta trancada não conclui (não há como ter feito o que não se abriu),
    e uma concluída fica concluída: um segundo laudo ou um segundo gesto sobre
    a mesma aula não reabre nem refaz nada.
    """
    if progresso.estado == Progresso.Estado.TRANCADA:
        raise PortaRecusada(
            "Esta porta ainda está trancada: conclua a aula anterior antes."
        )
    if progresso.estado == Progresso.Estado.CONCLUIDA:
        return False

    with transaction.atomic():
        progresso.estado = Progresso.Estado.CONCLUIDA
        progresso.concluida_em = timezone.now()
        progresso.cerimonia_pendente = progresso.aula.e_boss
        progresso.save(update_fields=["estado", "concluida_em", "cerimonia_pendente"])
        _abrir_a_seguinte(progresso)
    return True


def proxima_de(aula: Aula) -> Aula | None:
    """A aula de `ordem + 1` do mesmo curso, ou `None` na última. É a regra
    de vizinhança inteira, num lugar só: quem abre a seguinte e quem diz ao
    aluno "a próxima está aberta" perguntam aqui."""
    return Aula.objects.filter(curso=aula.curso, ordem=aula.ordem + 1).first()


def _abrir_a_seguinte(concluido: Progresso) -> None:
    """A aula de `ordem + 1` do mesmo curso sai de `trancada`, se existir."""
    seguinte = proxima_de(concluido.aula)
    if seguinte is None:
        return
    Progresso.objects.filter(
        pessoa=concluido.pessoa, aula=seguinte, estado=Progresso.Estado.TRANCADA
    ).update(estado=Progresso.Estado.DISPONIVEL)
    Progresso.objects.get_or_create(
        pessoa=concluido.pessoa,
        aula=seguinte,
        defaults={"estado": Progresso.Estado.DISPONIVEL},
    )


def pausas_registradas(progresso: Progresso) -> bool:
    """Todas as pausas da aula têm registro desta pessoa? ([INV-CUR-P3])

    É esta a pergunta que o formulário do checkpoint (degrau 2.1) faz antes de
    abrir. Aula sem pausa responde `True`: não há o que registrar.
    """
    pausas = set(progresso.aula.pausas.values_list("id", flat=True))
    registradas = set(
        RegistroDePausa.objects.filter(
            pessoa=progresso.pessoa, pausa_id__in=pausas
        ).values_list("pausa_id", flat=True)
    )
    return all(pausa in registradas for pausa in pausas)
