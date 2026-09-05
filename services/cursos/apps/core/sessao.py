"""Quem é a pessoa desta requisição, e se ela pode entrar na sala.

**A regra que organiza este arquivo inteiro: reconhecer não é autorizar.**
A `identidade` diz quem é; a `alunos` diz em que categoria está. **Quem decide
se a pessoa vê a aula é esta célula**, aqui, fail-CLOSED: só a matrícula ativa
abre a sala, e não conseguir perguntar nunca vira "então pode entrar"
(`DECISAO-celula-de-identidade.md` §6.2; constituição da célula).

**Esta célula não assina sessão** ([INV-P12]). O cookie recebido é repassado
OPACO à `identidade`; não há `SessionMiddleware`, não há `request.session`, e
os dois estados que a tentação poria lá (a cerimônia do Boss e "já leu o
laudo?") moram no `Progresso` (`armadilhas/143`).

Molde: `services/forum/apps/core/sessao.py`, copiado e nunca importado.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from apps.cursos.models import Pessoa

from .clients import (
    AlunosClient,
    AlunosIndisponivel,
    ConfiguracaoAusente,
    IdentidadeClient,
    IdentidadeIndisponivel,
)

logger = logging.getLogger(__name__)

# A categoria que a `alunos` devolve para quem tem matrícula ativa
# (`DECISAO-categorias-de-usuario.md`). Escrita aqui como dado desta célula:
# um renomeamento silencioso do outro lado aparece como teste vermelho aqui.
CATEGORIA_ALUNO = "aluno"


@dataclass(frozen=True)
class Ator:
    """Quem está do outro lado, do ponto de vista da sala de aula.

    `pessoa` é `None` para visitante. `eh_aluno` é conclusão DESTA célula, e
    `matricula_conferida` separa "perguntei e não é" de "não consegui
    perguntar": as duas fecham a porta, e a tela diz frases diferentes.

    `papel_do_site` é o `papel` que a `identidade` devolve, guardado como VEIO.
    Existe para UMA coisa: a plateia `staff` do menu do topo. Usá-lo para
    liberar qualquer coisa é a violação que a lei da identidade proíbe.
    """

    pessoa: Pessoa | None
    eh_aluno: bool = False
    matricula_conferida: bool = False
    papel_do_site: str = ""

    @property
    def autenticado(self) -> bool:
        return self.pessoa is not None


VISITANTE = Ator(pessoa=None)


def site_atual() -> str | None:
    """O `site_id` desta instalação, ou `None` quando o env não o declara.

    Lido no ponto de uso, com default inofensivo: sem ele a sala diz que o
    curso ainda não está ligado nesta escola, e nunca mostra o curso de outra.
    """
    valor = (os.environ.get("SITE_ID") or "").strip()
    if not valor:
        logger.error("SITE_ID ausente no env: a sala de aula não sabe de que site é")
        return None
    return valor


def quem_e(request) -> Ator:
    """O Ator desta requisição. Nunca levanta: o pior caso é VISITANTE.

    A cadeia: cookie opaco → `identidade` (quem é) → espelho local → `alunos`
    (matrícula). **Falhar em qualquer degrau devolve menos poder, nunca mais.**

    UMA resolução por requisição, guardada na própria requisição: a view
    pergunta, e o processador de contexto do menu pergunta de novo, depois
    dela. A memória vive na requisição e não em módulo: ela morre com a
    resposta, e duas pessoas nunca compartilham a mesma.
    """
    guardado = getattr(request, "_ator_desta_requisicao", None)
    if guardado is not None:
        return guardado

    ator = _resolver(request)
    request._ator_desta_requisicao = ator
    return ator


def _resolver(request) -> Ator:
    """A cadeia de verdade. `quem_e` é a porta com memória; esta é a viagem."""
    cookie = request.META.get("HTTP_COOKIE", "")
    if not cookie:
        return VISITANTE

    try:
        corpo = IdentidadeClient().sessao_completa(cookie)
    except (IdentidadeIndisponivel, ConfiguracaoAusente) as erro:
        # Sem saber quem é, a sala convida a entrar: é o fail-OPEN do
        # reconhecimento, e ele só dá menos poder, nunca mais.
        logger.warning("não deu para reconhecer a sessão: %s", erro)
        return VISITANTE

    if not corpo.get("autenticado"):
        return VISITANTE

    id_da_plataforma = corpo.get("id")
    email = (corpo.get("email") or "").strip().lower()
    if not id_da_plataforma or not email:
        # Autenticado sem id ou sem e-mail é resposta fora de forma: não dá
        # para espelhar nem para perguntar à `alunos`. Fecha.
        logger.warning("sessão autenticada sem id ou e-mail; tratando como visitante")
        return VISITANTE

    pessoa, _ = Pessoa.objects.update_or_create(
        id_da_plataforma=id_da_plataforma,
        defaults={"nome_exibido": corpo.get("nome_exibido") or ""},
    )

    try:
        categoria = AlunosClient().categoria_de(email)
        conferida = True
    except (AlunosIndisponivel, ConfiguracaoAusente) as erro:
        # FECHA. Não conseguir conferir a matrícula nunca é "pode entrar".
        logger.warning("não deu para conferir a matrícula de %s: %s", pessoa.pk, erro)
        categoria, conferida = "", False

    return Ator(
        pessoa=pessoa,
        eh_aluno=(categoria == CATEGORIA_ALUNO),
        matricula_conferida=conferida,
        papel_do_site=(corpo.get("papel") or "").strip(),
    )
