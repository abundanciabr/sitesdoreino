"""Publicar é criar versão NOVA. Este módulo é o único lugar que sabe como.

Lei: `docs/decisoes/PLANO-SEQUENCIAS-DE-MENSAGENS.md` §5 (a versão é imutável
por construção) e §8.3 (o mantenedor troca uma frase sozinho, sem PR).

POR QUE NÃO É UM `UPDATE`
-------------------------
Porque o banco não deixa, e não deixa de propósito. O gatilho
`jornadas_texto_publicado_e_pedra` (migração `0001`) recusa `UPDATE` e `DELETE`
em todo `TextoDoPasso` de uma versão publicada. Publicada é pedra.

E a pedra existe para segurar DUAS promessas que, sem ela, se contradizem: o
mantenedor edita a frase quando quiser, e ninguém que já está no meio da
sequência vê a frase mudar embaixo de si. A `Inscricao` aponta para a VERSÃO,
não para a jornada — quem entrou na v1 termina a v1, com o texto da v1.

O QUE ESTA FUNÇÃO FAZ, EM UMA FRASE
-----------------------------------
Copia a versão publicada corrente inteira para uma versão nova, aplica a frase
editada na cópia, e publica a cópia. Do lado de fora isso é "salvei o texto"; do
lado de dentro é uma versão a mais, e o número dela volta para a tela poder
dizer ao mantenedor, em português simples, o que acabou de acontecer.

A CÓPIA É PROFUNDA, E POR ISSO ELA É AQUI
-----------------------------------------
Passo e texto são linhas separadas, e um `Passo` que continuasse apontando para
a versão antiga faria a versão nova nascer vazia sem erro nenhum. É o tipo de
defeito que só aparece no dia em que alguém publica: a tela diz "salvo", a
sequência para de mandar mensagem, e nada fica vermelho.

O QUE NÃO MUDA AQUI, DE PROPÓSITO
---------------------------------
`Jornada.ativa` não é tocada. Editar uma frase nunca liga uma sequência
desligada, e publicar não é ligar. Ligar continua sendo gesto próprio do
mantenedor (`semear_boas_vindas --ligar` hoje, a tela do degrau 7 amanhã).
"""

from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from apps.jornadas.models import Jornada, JornadaVersao, Passo, TextoDoPasso


class SemVersaoPublicada(Exception):
    """A jornada existe, mas nunca teve versão publicada para servir de base."""


class PassoInexistente(Exception):
    """A versão base não tem passo naquela `ordem`."""


class VersaoBaseDesatualizada(Exception):
    """Alguém publicou entre a leitura da tela e este pedido.

    Sem esta recusa, a tela do mantenedor sobrescreveria em silêncio a edição de
    quem publicou primeiro: as duas partiriam da mesma base, e a segunda venceria
    por chegar depois. Publicar sem `versao_base` continua permitido e é o gesto
    de quem não estava editando uma versão específica.
    """


@dataclass(frozen=True)
class VersaoNascida:
    numero: int
    publicada_em: object
    passo_id: object
    passos: int


def versao_publicada_corrente(jornada: Jornada) -> JornadaVersao | None:
    """A versão que vale agora: a de MAIOR número entre as publicadas.

    Mesma regra que `apps/jornadas/motor.py::_versao_publicada` usa para
    inscrever. As duas precisam concordar, ou a tela mostraria uma versão e a
    sequência mandaria outra.
    """
    return (
        jornada.versoes.filter(publicada_em__isnull=False).order_by("-numero").first()
    )


@transaction.atomic
def publicar_texto(
    *,
    jornada: Jornada,
    ordem: int,
    idioma: str,
    assunto_visivel: str,
    corpo: str,
    versao_base: int | None = None,
) -> VersaoNascida:
    """Aplica uma frase nova e devolve a versão que nasceu dela.

    `versao_base` é o número que a tela estava editando. Quando vem e não bate
    com a publicada corrente, o pedido é RECUSADO em vez de bifurcar.
    """
    base = versao_publicada_corrente(jornada)
    if base is None:
        raise SemVersaoPublicada()
    if versao_base is not None and versao_base != base.numero:
        raise VersaoBaseDesatualizada()

    passos_da_base = list(base.passos.order_by("ordem"))
    if not any(p.ordem == ordem for p in passos_da_base):
        raise PassoInexistente()

    # `numero` sai do MÁXIMO de todas as versões da jornada, publicadas ou não —
    # nunca de `base.numero + 1`. Um rascunho com número maior deixaria a soma
    # ingênua colidir com ele, e a `UniqueConstraint` recusaria a publicação com
    # um IntegrityError que não explica nada a quem está numa tela.
    ultimo = jornada.versoes.order_by("-numero").first()
    nova = JornadaVersao.objects.create(jornada=jornada, numero=ultimo.numero + 1)

    passo_editado = None
    for antigo in passos_da_base:
        copia = Passo.objects.create(
            jornada_versao=nova,
            ordem=antigo.ordem,
            atraso=antigo.atraso,
            janela=antigo.janela,
            assunto=antigo.assunto,
            classe=antigo.classe,
            canais=list(antigo.canais),
            condicao_slug=antigo.condicao_slug,
        )
        if antigo.ordem == ordem:
            passo_editado = copia
        for texto in antigo.textos.all():
            if antigo.ordem == ordem and texto.idioma == idioma:
                continue  # a frase nova entra abaixo, no lugar desta
            TextoDoPasso.objects.create(
                passo=copia,
                idioma=texto.idioma,
                assunto_visivel=texto.assunto_visivel,
                corpo=texto.corpo,
            )

    # Idioma que ainda não existia entra como linha nova, e é assim que a tela
    # traduz um passo sem PR nenhum.
    TextoDoPasso.objects.create(
        passo=passo_editado,
        idioma=idioma,
        assunto_visivel=assunto_visivel,
        corpo=corpo,
    )

    # `queryset.update()` e não `save()`: o gatilho aceita este UPDATE porque
    # `OLD.publicada_em` ainda é nulo. É o último UPDATE que a linha aceita, e
    # daqui em diante ela é pedra.
    agora = timezone.now()
    JornadaVersao.objects.filter(pk=nova.pk).update(publicada_em=agora)

    return VersaoNascida(
        numero=nova.numero,
        publicada_em=agora,
        passo_id=passo_editado.id,
        passos=len(passos_da_base),
    )
