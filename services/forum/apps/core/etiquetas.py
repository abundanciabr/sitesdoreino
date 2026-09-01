# apps/core/etiquetas.py — "Nv 7 · Modelador" ao lado de quem escreve
"""A etiqueta de nível do autor, buscada em LOTE na célula `gamificacao`.

Até aqui o progresso do aluno só existia para quem abrisse `/conquistas` de
propósito. O fórum é o lugar da escola com mais gente passando, e é aqui que o
nível encontra quem nunca foi procurá-lo.

**Cópia do PADRÃO de `apps/core/menu.py`, nunca do arquivo dele** (Lei 3): um
cliente que fala com outra célula, com cache por TTL curto, teto de tamanho, e
que falha sempre para o mesmo lado. Lá o lado seguro é "sem menu"; aqui é
**"sem etiqueta"**.

## Falha para o lado de "sem etiqueta", sempre

Gamificação fora do ar, par de tokens não provisionado, corpo fora do contrato,
id que a gamificação não conhece: a resposta é mapa vazio e a página do tópico
abre normal. **Uma etiqueta é enfeite; derrubar o fórum porque ela está torta
seria a troca errada.** O próprio contrato já desenha a porta assim
(`getPublicProfiles`: "a falha desta porta é ABERTA por contrato: página sem
selo, nunca página quebrada") — o que este arquivo faz é honrar isso do lado de
cá, onde ele pode ser desfeito.

## Em LOTE, e é o desenho, não uma otimização

`getPublicProfiles` aceita até 50 ids por chamada porque uma página de fórum
decora N autores. Uma chamada por autor faria a tela do fórum depender da
latência da `gamificacao` N vezes — com 20 mensagens numa conversa, vinte
saltos de rede para desenhar vinte selos. Existe um guarda de teste sobre isso
(`test_uma_pagina_com_varios_autores_faz_UMA_chamada_de_rede`), e ele está lá
porque este é o tipo de desenho que se desfaz de boa-fé: basta alguém achar
mais legível perguntar dentro do laço.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass

import httpx

from .clients import http

logger = logging.getLogger("forum.etiquetas")

# ---------------------------------------------------------------------------
# O MAPA DE RÓTULOS — leia isto inteiro antes de "consertar"
# ---------------------------------------------------------------------------
# `titulo_slug` é um SLUG, não um rótulo. Ele sai de `slugify(titulo)` lá na
# `gamificacao` (`apps/core/api.py::_titulos_por_nivel`), e slug **perde acento
# e junta as palavras com hífen**: "Aprendiz de Ateliê" chega aqui como
# `aprendiz-de-atelie`.
#
# **Desfazer o slug programaticamente produz lixo.** `"aprendiz-de-atelie"
# .replace("-", " ").title()` devolve "Aprendiz De Atelie" — preposição em
# maiúscula e "Ateliê" sem acento, na cara do aluno. Não existe volta
# automática: o acento foi jogado fora do outro lado da porta, e nenhuma regra
# de string o traz de volta sem adivinhar.
#
# Por isso o fórum guarda o mapa, com as frases escritas à mão em português.
#
# **A saída bonita seria acrescentar `titulo` ao contrato, e ela está PROIBIDA
# aqui.** Duas razões, e as duas valem para quem ler isto no futuro:
#
#   1. Mexer em `contracts/` é Rito de Contrato, com o mantenedor presente
#      (`RITOS.md` §3). Não se faz dentro de um lote de trabalho paralelo.
#   2. O contrato manda SLUG de propósito, e está escrito lá: o site serve três
#      idiomas, e transmitir "Modelador" congelaria o idioma de quem escreveu.
#      Quem lê é quem traduz — que é exatamente o que este mapa faz.
#
# ## O DIA EM QUE OS TÍTULOS MUDAREM
#
# Se o mantenedor renomear um degrau na `gamificacao` (ou acrescentar um), o
# slug novo simplesmente **não estará neste mapa**. O que acontece então:
# a etiqueta sai como "Nv 7", sem título, e ninguém vê erro nenhum. Isso é o
# fallback fail-open desta função, e é deliberado.
#
# O conserto é **acrescentar a linha aqui**, com o rótulo em português, no mesmo
# PR que mudou o título lá. Nunca é derivar do slug.
#
# Fonte dos dez degraus:
# `services/gamificacao/apps/gamificacao/management/commands/semear_economia.py`
# (a lista `NIVEIS`). O slug de cada um é `slugify` do título masculino, que é
# o campo que a porta usa.
ROTULO_POR_SLUG: dict[str, str] = {
    "aprendiz": "Aprendiz",
    "aprendiz-de-atelie": "Aprendiz de Ateliê",
    "modelador": "Modelador",
    "modelador-de-atelie": "Modelador de Ateliê",
    "oficial": "Oficial",
    "oficial-de-atelie": "Oficial de Ateliê",
    "artesao": "Artesão",
    "artesao-de-atelie": "Artesão de Ateliê",
    "mestre": "Mestre",
    "mestre-de-atelie": "Mestre de Ateliê",
}

# O teto do contrato (`getPublicProfiles`: "até 50 por chamada"). Página com
# mais autores distintos que isto vira mais de uma chamada, em vez de mandar
# uma lista que a porta cortaria em silêncio.
TETO_DE_IDS_POR_CHAMADA = 50

# O mesmo TTL do menu, e pelo mesmo motivo: nível muda devagar (quem sobe de
# degrau demora dias), e um minuto de atraso é barato perto de uma consulta de
# rede por página aberta.
TTL_SEGUNDOS = 60

# Teto de segurança, como o do menu: sem ele o dicionário cresceria sem fim
# dentro do processo, uma entrada por aluno que já apareceu em alguma página.
MAXIMO_DE_PESSOAS_EM_CACHE = 500

# `{pessoa_id: (expira_em, Etiqueta | None)}`. `None` guardado é "perguntei e
# não tem etiqueta" — ver `_buscar`.
_CACHE: dict[str, tuple[float, "Etiqueta | None"]] = {}


def limpar_cache() -> None:
    """Esvazia o cache de módulo. Chamada pelas fixtures da suíte.

    Cache de módulo sobrevive entre testes (`armadilhas/026`): sem esta função,
    uma etiqueta que um teste ensinou faria o teste seguinte passar por
    herança, e não por medição.
    """
    _CACHE.clear()


@dataclass(frozen=True)
class Etiqueta:
    """O que a tela estampa: um número e, quando dá, um título em português.

    `titulo` vazio é caso NORMAL, não erro: é o slug que ainda não está em
    `ROTULO_POR_SLUG`. A tela desenha só "Nv 7", que é verdade, em vez de um
    rótulo chutado.

    **A frase não é montada aqui, e isso é de propósito.** Quem escreve
    "Nv 7 · Modelador" é o template, porque é `templates/` que o portão do
    travessão vigia (lei de 30/08/2026). Frase montada em Python sairia de
    baixo dessa régua sem ninguém notar.
    """

    nivel: int
    titulo: str = ""


def _configuracao() -> tuple[str, str] | None:
    """(endereço, token) do par com a `gamificacao`, ou `None`.

    **Lido no PONTO DE USO, e com `.get()`** (`armadilhas/097`): variável de
    ambiente lida no `__init__` de um cliente vira `KeyError`, que não é
    `httpx.RequestError`, que portanto atravessa o `try` do fail-open e sai
    como **HTTP 500 em toda página do fórum** — com o deploy verde e o
    `/healthz` respondendo 200.

    `None` é o estado real enquanto o passo do mantenedor não roda
    (`infra/provisionar-par-do-forum-com-a-gamificacao.sh`), e ele não pode
    custar nem um erro nem uma tentativa de rede por página aberta.
    """
    base = (os.environ.get("GAMIFICACAO_API_URL") or "").strip().rstrip("/")
    token = (os.environ.get("GAMIFICACAO_API_TOKEN") or "").strip()
    return (base, token) if base and token else None


def _perguntar_a_gamificacao(ids: list[str]) -> dict:
    """O mapa cru desta porta para estes ids, ou `{}`. Nunca levanta.

    Quem chama desenha a página de qualquer jeito, então todo tropeço tem o
    mesmo desfecho: dicionário vazio.
    """
    configuracao = _configuracao()
    if configuracao is None:
        return {}
    base, token = configuracao
    try:
        resposta = http().get(
            f"{base}/perfis",
            params={"ids": ",".join(ids)},
            headers={"Authorization": f"Bearer {token}"},
        )
    except httpx.RequestError as erro:
        logger.warning("etiquetas: a gamificação não respondeu: %s", erro)
        return {}
    if resposta.status_code != 200:
        logger.warning(
            "etiquetas: a gamificação respondeu HTTP %s", resposta.status_code
        )
        return {}
    try:
        corpo = resposta.json()
    except ValueError as erro:
        # `200` com corpo que não é JSON: página de erro de um proxy
        # interposto, resposta truncada. `json.JSONDecodeError` é `ValueError`,
        # NÃO é `httpx.RequestError` — fora deste `try` ela subiria crua e
        # viraria 500 na página inteira. É a família do *2xx não é sucesso*
        # (`RETROSPECTIVA-FASE-D` §4).
        logger.warning("etiquetas: a gamificação respondeu fora do contrato: %s", erro)
        return {}
    if not isinstance(corpo, dict):
        return {}
    return corpo


def _etiqueta_do_corpo(linha) -> Etiqueta | None:
    """Uma linha do mapa vira `Etiqueta`, ou `None` se não couber no contrato.

    O contrato promete `{nivel: int, titulo_slug: str}`. Confiar sem conferir é
    como um `null` do outro lado vira `TypeError` no meio do template — e ali o
    erro já não tem como falhar aberto, porque a página está sendo renderizada.

    `bool` é excluído de propósito: em Python `isinstance(True, int)` é
    verdadeiro, e "Nv True" seria uma etiqueta possível sem esta linha.
    """
    if not isinstance(linha, dict):
        return None
    nivel = linha.get("nivel")
    if isinstance(nivel, bool) or not isinstance(nivel, int) or nivel < 1:
        return None
    slug = linha.get("titulo_slug")
    if not isinstance(slug, str):
        return None
    # Slug fora do mapa desenha SÓ o nível. Ver o bloco grande no topo: é
    # fail-open deliberado, nunca um rótulo derivado do slug.
    return Etiqueta(nivel=nivel, titulo=ROTULO_POR_SLUG.get(slug, ""))


def _fatias(ids: list[str], tamanho: int):
    for inicio in range(0, len(ids), tamanho):
        yield ids[inicio : inicio + tamanho]


def _buscar(faltantes: list[str]) -> None:
    """Pergunta pelos ids que não estão em cache e guarda o que voltou.

    **A ausência também é guardada**, e é a peça que faz o cache valer a pena:
    id que a `gamificacao` não conhece (aluno que nunca pontuou, e são a
    maioria no começo) voltaria a custar uma consulta de rede em toda página
    aberta se só o positivo fosse lembrado. É a mesma escolha do `menu.py` com
    o catálogo mudo.
    """
    agora = time.time()
    for lote in _fatias(faltantes, TETO_DE_IDS_POR_CHAMADA):
        corpo = _perguntar_a_gamificacao(lote)
        if len(_CACHE) + len(lote) > MAXIMO_DE_PESSOAS_EM_CACHE:
            _CACHE.clear()
        for pessoa_id in lote:
            _CACHE[pessoa_id] = (
                agora + TTL_SEGUNDOS,
                _etiqueta_do_corpo(corpo.get(pessoa_id)),
            )


def etiquetas_de(ids) -> dict[str, Etiqueta]:
    """`{pessoa_id: Etiqueta}` para os ids pedidos. Nunca levanta.

    Id sem etiqueta simplesmente **não aparece no resultado** — a mesma forma
    que o contrato usa do outro lado, e a que faz "sem etiqueta" ser
    indistinguível de "a gamificação está fora do ar" para quem desenha a tela.
    Isso é o certo: as duas situações têm a mesma página.
    """
    pedidos = []
    for pessoa_id in ids:
        if isinstance(pessoa_id, str) and pessoa_id and pessoa_id not in pedidos:
            pedidos.append(pessoa_id)
    if not pedidos:
        # Nem cache, nem rede: página só com falas da escola não pergunta nada.
        return {}

    agora = time.time()
    faltantes = [
        pessoa_id
        for pessoa_id in pedidos
        if not ((guardado := _CACHE.get(pessoa_id)) is not None and guardado[0] > agora)
    ]
    if faltantes:
        _buscar(faltantes)

    achadas: dict[str, Etiqueta] = {}
    for pessoa_id in pedidos:
        guardado = _CACHE.get(pessoa_id)
        if guardado is not None and guardado[1] is not None:
            achadas[pessoa_id] = guardado[1]
    return achadas


def decorar(mensagens: list) -> list:
    """Pendura `.etiqueta` em cada mensagem da página, com UMA ida à rede.

    Devolve a mesma lista, para quem preferir encadear.

    **O id que a `gamificacao` entende é o id OPACO da plataforma**, e nesta
    célula ele é a própria chave primária de `Pessoa` (`id_da_plataforma`).
    Então `mensagem.autor_id` **já é** esse id: nem o id local do fórum (não
    existe outro), nem o e-mail (que é dado pessoal e nunca sai daqui), e sem
    uma consulta a mais ao banco para descobri-lo.

    ## Fala da escola nunca recebe etiqueta

    Uma mensagem pode ser **da instituição** e não de uma pessoa
    (`publicado_pela_escola`, `apps/forum/models.py`). A Meshcraft Academy não
    tem nível, e estampar um nela seria fingir que a escola é uma aluna.
    Autor nulo (a assinatura vira "alguém") também não recebe.

    As DUAS condições são conferidas, embora hoje o banco garanta que elas
    andam juntas (`_fala_de_pessoa_ou_da_escola`). Uma regra de produto que
    depende de uma restrição de banco continuar existindo é uma regra que se
    perde no dia em que a restrição mudar de forma por outro motivo.
    """
    ids = [
        mensagem.autor_id
        for mensagem in mensagens
        if mensagem.autor_id and not mensagem.publicado_pela_escola
    ]
    mapa = etiquetas_de(ids)
    for mensagem in mensagens:
        mensagem.etiqueta = (
            mapa.get(mensagem.autor_id)
            if mensagem.autor_id and not mensagem.publicado_pela_escola
            else None
        )
    return mensagens
