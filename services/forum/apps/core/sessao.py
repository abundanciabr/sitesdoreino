"""Quem é a pessoa desta requisição — e o que ela pode fazer aqui.

**A regra que organiza este arquivo inteiro: reconhecer não é autorizar.**
A `identidade` diz quem é; a `alunos` diz em que categoria está. **Quem decide
o que pode é o fórum**, aqui, fail-CLOSED, conferindo as listas dele
(`DECISAO-forum-da-escola.md` §3, e a lei da identidade §4).

Foi exatamente aqui que um consultor externo tropeçou na rodada de 28/08: ele
propôs carregar papel e matrícula dentro do próprio login, assinados. Isso é
proibido por escrito — transformaria a `identidade` em autoridade de permissão,
que é a doença de que este projeto já se vacinou.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from apps.forum.models import Pessoa

from .clients import (
    AlunosClient,
    AlunosIndisponivel,
    ConfiguracaoAusente,
    IdentidadeClient,
    IdentidadeIndisponivel,
)

logger = logging.getLogger(__name__)

# As categorias que a `alunos` devolve (`DECISAO-categorias-de-usuario.md`).
# Escritas aqui como dado do fórum, e não importadas de lugar nenhum: o
# vocabulário vem do contrato, e travá-lo em código local é o que faz um
# renomeamento silencioso do outro lado aparecer como teste vermelho aqui.
CATEGORIA_ALUNO = "aluno"


@dataclass(frozen=True)
class Ator:
    """Quem está do outro lado, do ponto de vista do fórum.

    `pessoa` é `None` para visitante. `eh_aluno` e `eh_equipe` são conclusões
    DESTA célula — nunca campos que vieram prontos de fora.
    """

    pessoa: Pessoa | None
    eh_aluno: bool = False
    eh_professor: bool = False
    eh_admin: bool = False

    @property
    def autenticado(self) -> bool:
        return self.pessoa is not None

    @property
    def eh_equipe(self) -> bool:
        """Quem fala com autoridade no fórum: professor ou administrador."""
        return self.eh_professor or self.eh_admin


VISITANTE = Ator(pessoa=None)


def _lista_de_emails(nome_da_variavel: str) -> set[str]:
    """Uma lista de e-mails do env, normalizada. Vazia ⇒ ninguém.

    Lida no PONTO DE USO e com default inofensivo (`armadilhas/097`): env
    ausente fecha o poder, mas não derruba o container — o `/healthz` continua
    respondendo e o deploy não entra em crashloop.

    **Fail-closed por construção:** variável ausente ou vazia significa
    *ninguém tem este poder*, nunca *todo mundo tem*.
    """
    cru = os.environ.get(nome_da_variavel, "") or ""
    return {parte.strip().lower() for parte in cru.split(",") if parte.strip()}


def quem_e(request) -> Ator:
    """O Ator desta requisição. Nunca levanta — o pior caso é VISITANTE.

    A cadeia é: cookie opaco → `identidade` (quem é) → espelho local → `alunos`
    (que categoria) → listas do env (professor, admin).

    **Falhar em qualquer degrau devolve menos poder, nunca mais.** É a diferença
    entre reconhecimento e autorização: não conseguir perguntar "é aluno?" não
    pode virar "então é aluno".
    """
    cookie = request.META.get("HTTP_COOKIE", "")
    if not cookie:
        return VISITANTE

    try:
        corpo = IdentidadeClient().sessao_completa(cookie)
    except (IdentidadeIndisponivel, ConfiguracaoAusente) as erro:
        # Sem saber quem é, o fórum trata como visitante: as áreas públicas
        # continuam legíveis (é conteúdo público), e tudo o mais fecha.
        logger.warning("não deu para reconhecer a sessão: %s", erro)
        return VISITANTE

    if not corpo.get("autenticado"):
        return VISITANTE

    id_da_plataforma = corpo.get("id")
    email = (corpo.get("email") or "").strip().lower()
    if not id_da_plataforma or not email:
        # Autenticado sem id ou sem e-mail é resposta fora de forma. Não dá
        # para espelhar nem para perguntar à `alunos` — fecha.
        logger.warning("sessão autenticada sem id ou e-mail; tratando como visitante")
        return VISITANTE

    pessoa, _ = Pessoa.objects.update_or_create(
        id_da_plataforma=id_da_plataforma,
        defaults={"email": email, "nome_exibido": corpo.get("nome_exibido") or ""},
    )

    try:
        categoria = AlunosClient().categoria_de(email)
    except (AlunosIndisponivel, ConfiguracaoAusente) as erro:
        # FECHA. Não conseguir conferir a matrícula nunca é "pode entrar".
        logger.warning("não deu para conferir a matrícula de %s: %s", pessoa.pk, erro)
        categoria = ""

    return Ator(
        pessoa=pessoa,
        eh_aluno=(categoria == CATEGORIA_ALUNO),
        eh_professor=email in _lista_de_emails("FORUM_PROFESSORES"),
        eh_admin=email in _lista_de_emails("ADMIN_EMAILS"),
    )
