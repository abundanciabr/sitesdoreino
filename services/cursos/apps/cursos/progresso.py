"""As regras da porta: que aula abre, quando, e por quem.

**O checkpoint abre a porta; o calendário, nunca** (a missão da célula). Este
arquivo é o único lugar onde uma porta muda de estado, e é por isso que os
três invariantes da porta (`PLANO-CELULA-CURSOS.md` §9) são impostos aqui:

- **[INV-CUR-P2]** `concluir` EXIGE um laudo com decisão `aberto` ou
  `aberto_com_ajuste`. Não há parâmetro de data, de XP nem de pagamento, e
  não há outra função que grave `concluida`. O `Laudo` como tabela nasce no
  degrau 2.2; aqui ele é qualquer objeto com `decisao`, e a função recusa
  todo o resto. Guarda: `tests/test_inv_p2_a_porta_so_abre_por_laudo.py`.
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

from .models import Aula, Curso, Pessoa, Progresso, RegistroDePausa

# As duas decisões de laudo que abrem a porta seguinte. Escritas aqui como
# dado desta célula, e não importadas de lugar nenhum: o vocabulário do laudo
# nasce no degrau 2.2, e travá-lo aqui é o que faz uma decisão nova
# ("reprovado", que a lei proíbe) aparecer como teste vermelho em vez de porta
# aberta.
DECISOES_QUE_ABREM = frozenset({"aberto", "aberto_com_ajuste"})


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
    """A porta seguinte abre, e SÓ por um laudo aberto ([INV-CUR-P2]).

    `laudo` é o único caminho: qualquer objeto cuja `decisao` seja `aberto` ou
    `aberto_com_ajuste`. Não existe parâmetro de data, de XP nem de pagamento,
    e é a assinatura desta função, medida no guarda, que prova a ausência.

    Uma porta trancada não conclui (não há envio possível de onde não se
    entrou), e uma concluída fica concluída: um segundo laudo sobre a mesma
    aula não reabre nem refaz nada.
    """
    decisao = getattr(laudo, "decisao", None)
    if decisao not in DECISOES_QUE_ABREM:
        raise PortaRecusada(
            "A porta seguinte só abre com um laudo que diga aberto ou aberto "
            "com ajuste. Sem laudo, ou com laudo devolvido, ela fica como está."
        )
    if progresso.estado == Progresso.Estado.TRANCADA:
        raise PortaRecusada(
            "Esta porta ainda está trancada: conclua a aula anterior antes."
        )
    if progresso.estado == Progresso.Estado.CONCLUIDA:
        return progresso

    with transaction.atomic():
        progresso.estado = Progresso.Estado.CONCLUIDA
        progresso.concluida_em = timezone.now()
        progresso.cerimonia_pendente = progresso.aula.e_boss
        progresso.save(update_fields=["estado", "concluida_em", "cerimonia_pendente"])
        _abrir_a_seguinte(progresso)
    return progresso


def _abrir_a_seguinte(concluido: Progresso) -> None:
    """A aula de `ordem + 1` do mesmo curso sai de `trancada`, se existir."""
    seguinte = Aula.objects.filter(
        curso=concluido.aula.curso, ordem=concluido.aula.ordem + 1
    ).first()
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
