"""Quem é do plantão desta escola, e por que a resposta mora aqui dentro.

**Reconhecer não é autorizar.** A `identidade` devolve um `papel` junto com o id
de quem está logado, e usá-lo para abrir esta tela seria confortável e errado:
aquele campo é de EXIBIÇÃO. O `papel` responde "esta pessoa é professora na
plataforma?"; a pergunta desta tela é "esta pessoa pode dar um título de Banca e
abrir encomenda paga pela escola?". No dia em que a plataforma tiver um segundo
produto com outros professores, a primeira resposta continuaria "sim" e a
segunda passaria a ser "não", e ninguém perceberia, porque nada quebraria
(`DECISAO-onde-mora-a-sessao.md` §4).

**A LISTA VAZIA E NINGUEM**, e é o mesmo desenho de `TOKENS_ACEITOS` ao lado:
env ausente não derruba o boot, não quebra tela nenhuma e fecha o plantão.
Fail-closed sem fail-hard.

**Por que id de plataforma e não e-mail:** e-mail muda de dono, e o id opaco é o
que `sessao.quem_e()` já devolve. Sem conversão, sem chamada de rede, sem cache
para envelhecer.

Quem escreve o env é o mantenedor, na VPS: um id de pessoa é dado de produção, e
nenhum agente o inventa.

O molde é `services/gamificacao/apps/core/equipe.py`.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

# O nome da variável, num lugar só: a mensagem de recusa cita a mesma palavra que
# o env escreve, e o teste compara as duas.
VARIAVEL = "IDS_DO_PLANTAO"

_ja_avisei_que_a_lista_esta_vazia = False


def ids_do_plantao() -> frozenset[str]:
    """Os ids de plataforma que podem dar título e abrir encomenda da escola.

    Lida **no ponto de uso**, nunca no import (`armadilhas/097`).

    Separador é vírgula, espaços são ignorados e valor vazio some. Formato
    frouxo na LEITURA e rígido na escrita: quem digita é um humano numa VPS, e um
    espaço a mais não pode trancar o professor para fora.
    """
    global _ja_avisei_que_a_lista_esta_vazia
    cru = os.environ.get(VARIAVEL, "")
    ids = frozenset(pedaco.strip() for pedaco in cru.split(",") if pedaco.strip())
    if not ids and not _ja_avisei_que_a_lista_esta_vazia:
        # UMA vez por processo. O log existe para o dia em que a tela estiver
        # "quebrada" para todo mundo: sem esta linha, a causa (env ausente) é
        # indistinguível de um defeito de código.
        logger.warning(
            "%s esta vazia ou ausente: o plantao esta fechado para todo mundo",
            VARIAVEL,
        )
        _ja_avisei_que_a_lista_esta_vazia = True
    return ids


def e_do_plantao(pessoa_id: str | None) -> bool:
    """Esta pessoa pode agir no plantão? Visitante nunca pode."""
    return bool(pessoa_id) and pessoa_id in ids_do_plantao()
