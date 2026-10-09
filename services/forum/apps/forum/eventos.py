# apps/forum/eventos.py
"""Os quatro fatos que este fórum AFIRMA ao resto da escola.

Até 01/09/2026 ele era MUDO. Tinha gente conversando, dúvidas sendo resolvidas,
e nada disso virava ponto para ninguém: a medalha "Mão amiga" (cinco respostas
aceitas) não tinha como cair, porque ninguém contava. Este arquivo é a voz.

Os campos emitidos aqui são os que as células consumidoras leem.

AS QUATRO REGRAS QUE ESTE ARQUIVO CUMPRE
-----------------------------------------
1. **O evento nasce DENTRO da transação do fato.** Fora dela, um rollback
   deixaria a plataforma pagando ponto por uma mensagem que não existe.
   `emitir()` RECUSA a escrita fora de `atomic`.

2. **Nenhum texto escrito por gente viaja.** `mensagem-criada` leva o TAMANHO
   (`caracteres`), nunca o conteúdo — foi decisão da Sessão B, e a razão é dupla:
   o motor de XP precisa do tamanho para o teto anti-spam, e o texto de um aluno
   não tem por que atravessar fila de evento nem log de servidor.

3. **`resposta-aceita` carrega DOIS ids, e nenhum é redundante.** O `ator_id` do
   envelope é quem MARCOU; o `autor_da_resposta_id` do `data` é quem RECEBE o
   prêmio. O contrato diz, com todas as letras, para não remover nenhum dos dois
   por economia: sem eles as defesas antifraude ficam cegas, e desde a decisão D
   da Sessão B elas são a ÚNICA proteção do maior prêmio do sistema.

4. **Sem site conhecido, não se emite** — e o fórum continua funcionando. A
   falta de um evento nunca pode custar a fala de um aluno.

DE ONDE SAI O `site_id`, E POR QUE NÃO HÁ ENV NOVO
---------------------------------------------------
Do HOST, perguntando ao catálogo (`getSiteByHost`), com o mesmo cache que o menu
do topo já usa. O fórum não tinha e não ganhou uma variável de ambiente com o id
do site: uma variável dessas seria uma segunda verdade sobre "que site é este",
que envelhece calada e que custaria um passo de provisionamento na VPS.

A consequência honesta: com o catálogo fora do ar E o cache vazio, o evento não
sai. É o mesmo desenho que o menu já escolheu para si — o fórum abre sem menu, em
vez de não abrir.
"""

from __future__ import annotations

import uuid
from typing import Any

from django.db import transaction

from .models import Area, OutboxEvent, Topico

TOPICO_CRIADO = "forum.topico-criado"
MENSAGEM_CRIADA = "forum.mensagem-criada"
RESPOSTA_ACEITA = "forum.resposta-aceita"
MENSAGEM_REMOVIDA = "forum.mensagem-removida"
RESPOSTA_CRIADA = "forum.resposta-criada"


def _destinatario_pode_ler(area: Area, destinatario) -> bool:
    """Confere a permissão atual pela mesma função usada pela página."""
    from apps.core.permissoes import pode_ler
    from apps.core.sessao import Ator, email_da_equipe

    if area.visibilidade == Area.Visibilidade.PUBLICA:
        return bool(area.ativa)
    equipe = email_da_equipe(destinatario.email)
    aluno = False
    if not equipe:
        try:
            from apps.core.clients import AlunosClient

            aluno = AlunosClient().categoria_de(destinatario.email) == "aluno"
        except Exception:  # noqa: BLE001 - sem conferência, não emite aviso
            return False
    ator = Ator(pessoa=destinatario, eh_aluno=aluno, eh_professor=equipe)
    return pode_ler(area, ator)


class EventoForaDaTransacao(Exception):
    """`emitir()` chamado sem transação aberta — o evento não seria transacional.

    Levantar aqui é o princípio 'mecanismo, não documento' aplicado: em vez de confiar que todo ponto de emissão
    futuro se lembre do `atomic`, a própria função recusa a escrita. Um evento
    gravado em autocommit sobrevive ao rollback do fato que o justifica, e aí a
    plataforma inteira passa a acreditar em algo que não aconteceu.
    """


def emitir(
    event: str,
    data: dict[str, Any],
    *,
    ator_id: str | None,
    version: int = 1,
) -> OutboxEvent:
    """Grava o fato na outbox — SEMPRE dentro da transação do fato.

    Não publica nada: publicar é do relay (`tasks.py`), depois do commit. Essa
    separação É a outbox — escrever no Redis aqui dentro devolveria o problema
    que o padrão resolve (evento publicado, transação revertida).
    """
    if not transaction.get_connection().in_atomic_block:
        raise EventoForaDaTransacao(
            f"emitir({event!r}) foi chamado fora de transaction.atomic(). "
            "O evento tem de nascer na MESMA transação do fato que o justifica: "
            "sem isso, um rollback deixa a plataforma acreditando num fato que "
            "não aconteceu."
        )
    return OutboxEvent.objects.create(
        event=event,
        version=version,
        payload=data,
        envelope_extra={"ator_id": ator_id},
    )


def topico_criado(*, site_id: str, topico, ator_id: str) -> OutboxEvent | None:
    """Alguém abriu uma conversa nova."""
    if not site_id:
        return None
    return emitir(
        TOPICO_CRIADO,
        {
            "site_id": site_id,
            "topico_id": str(topico.pk),
            "area_id": str(topico.area_id),
        },
        ator_id=ator_id,
    )


def mensagem_criada(*, site_id: str, mensagem, ator_id: str,
                    host: str = "") -> OutboxEvent | None:
    """Alguém falou.

    `caracteres` é o TAMANHO, nunca o texto — e a diferença é o que permite ao
    motor de XP ter teto anti-spam sem que uma linha escrita por um aluno passe
    por fila de evento nenhuma.
    """
    if not site_id:
        return None
    evento = emitir(
        MENSAGEM_CRIADA,
        {
            "site_id": site_id,
            "mensagem_id": str(mensagem.pk),
            "topico_id": str(mensagem.topico_id),
            "area_id": str(mensagem.topico.area_id),
            "caracteres": len(mensagem.texto or ""),
        },
        ator_id=ator_id,
    )
    # Só uma resposta a tópico de outra pessoa tem destinatário. A primeira
    # mensagem do tópico e uma fala do próprio autor não avisam ninguém.
    topico = mensagem.topico
    destinatario = topico.autor
    # O host veio do mesmo request que o catálogo usou para obter site_id.
    # Confirmá-lo outra vez pelo cache impede que um chamador interno monte
    # link de outro domínio; sem par confirmado, não há link a enviar.
    host = (host or "").strip().lower()
    link = ""
    if host and all(c.isascii() and (c.isalnum() or c in ".-") for c in host):
        from apps.core.menu import site_id_do_host

        if site_id_do_host(host) == site_id:
            link = f"https://{host}/forum/t/{topico.pk}#m{mensagem.pk}"
    if (
        destinatario is not None
        and destinatario.id_da_plataforma != ator_id
        and topico.estado == Topico.Estado.PUBLICADO
        and topico.area.ativa
        and mensagem.removida_em is None
        and link
        and _destinatario_pode_ler(topico.area, destinatario)
    ):
        dados_da_resposta = {
            "site_id": site_id,
            "topico_id": str(topico.pk),
            "mensagem_id": str(mensagem.pk),
            "area_id": str(topico.area_id),
            "destinatario_id": destinatario.id_da_plataforma,
            "link": link,
        }
        if topico.area.curso_id:
            dados_da_resposta["curso_id"] = topico.area.curso_id
        emitir(
            RESPOSTA_CRIADA,
            dados_da_resposta,
            ator_id=ator_id,
        )
    return evento


def resposta_aceita(
    *, site_id: str, topico, mensagem, ator_id: str, marcada_por: str
) -> OutboxEvent | None:
    """Esta mensagem resolveu a dúvida. É o fato mais valioso do sistema.

    Quem ajudou de verdade recebe a maior recompensa do catálogo, porque
    validação humana vale cerca de dez vezes consumo (decisão 4 da Sessão A).

    **Os dois ids são diferentes de propósito:** `ator_id` é quem marcou,
    `autor_da_resposta_id` é quem escreveu e vai receber. Sem o segundo, o
    consumidor teria de perguntar ao fórum quem escreveu a mensagem — e a aresta
    "A premiou B", de que a detecção de anéis depende, não existiria.
    """
    if not site_id:
        return None
    return emitir(
        RESPOSTA_ACEITA,
        {
            "site_id": site_id,
            "topico_id": str(topico.pk),
            "mensagem_id": str(mensagem.pk),
            "autor_da_resposta_id": str(mensagem.autor_id),
            "marcada_por": marcada_por,
        },
        ator_id=ator_id,
    )


def mensagem_removida(*, site_id: str, mensagem, ator_id: str) -> OutboxEvent | None:
    """A moderação tirou uma fala do ar.

    É o evento do ESTORNO: sem ele, o ponto pago por uma mensagem que a escola
    depois removeu continuaria no placar de quem a escreveu — e a quarentena do
    motor de XP, que existe para exatamente esta janela, nunca teria o que
    desfazer.
    """
    if not site_id:
        return None
    return emitir(
        MENSAGEM_REMOVIDA,
        {
            "site_id": site_id,
            "mensagem_id": str(mensagem.pk),
            "topico_id": str(mensagem.topico_id),
        },
        ator_id=ator_id,
    )
