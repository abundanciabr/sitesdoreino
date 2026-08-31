"""Quem está dentro, agora — resolvido pela sessão DO SITE, conferido AQUI.

Desde a `DECISAO-celula-de-identidade` (25/08/2026) esta célula **não tem mais
login próprio**: quem prova QUEM É é a célula `identidade` (o cookie
`meshcraft_sessao` é assinado e resolvido lá). O que continua sendo desta
célula — e não pode sair dela — é a AUTORIZAÇÃO: a Caixa é de quem tem
matrícula ou é da equipe (`DECISAO-EVO-01` §2/§4), e essas duas listas são
conferidas aqui, sobre o e-mail que a resposta completa do contrato entrega
(`getSessionFull` — o degrau `TOKENS_COMPLETOS_SUGESTOES` existe para isso).

O caminho de toda requisição de gente:

    cookie (opaco) → identidade responde quem é → staff? → tem matrícula?
                   → Ator(linha LOCAL, papel das listas LOCAIS)

**A linha local é snapshot, casado por e-mail** (Virtude da Lei 3: snapshots
são sagrados): `Identidade` desta célula continua existindo, com as mesmas 6
FKs de autoria apontando para ela — foi isso que fez a mudança de casa custar
ZERO migração de dado em produção. A mesma pessoa entrando pelo site recupera
a linha que já era dela.

**E desde a Fase 1 do `docs/notificacoes/PLANO-MESTRE.md` (25/08/2026) o
snapshot guarda também o `id` da resposta** — o identificador da pessoa na
célula `identidade`, o único que atravessa a plataforma. Ele já vinha em toda
resposta (`SessionFull.id`, contrato congelado) e era jogado fora nesta função;
sem ele, uma caixa central de notificações receberia o fato e um id que não
significa nada fora da Caixa (PLANO-MESTRE §2). **O casamento por e-mail
continua sendo a chave** — o id novo é dado a mais, não substituto.

**Fail-CLOSED, dos dois lados.** `identidade` fora do ar OU `alunos` fora do
ar ⇒ ninguém participa e a porta explica ("não conseguimos conferir"). É o
oposto do reconhecimento de exibição do `funil` (fail-open) — lá a resposta
decide um nome no canto da tela; aqui ela decide ACESSO.

**O papel continua derivado a cada requisição** da lista
`SUGESTOES_STAFF_EMAILS` — a promessa da EVO-01 §4, intocada. E a lista de
staff DESTA célula é desta célula: o `papel` que a `identidade` responde no
contrato é de EXIBIÇÃO e não autoriza nada aqui (invariante da
DECISAO-onde-mora-a-sessao §4).
"""

import logging
import os
import time
from dataclasses import dataclass

from django.db import IntegrityError, transaction

from apps.sugestoes.models import Identidade

from .clients import (
    AlunosClient,
    AlunosIndisponivel,
    ConfiguracaoAusente,
    IdentidadeClient,
    IdentidadeIndisponivel,
)

# Chave do dicionário da sessão LEGADA (o cookie que ESTA célula assinava, até
# 25/08/2026). Só o leitor legado da API interna a usa — ver
# `ator_da_sessao_legada` e o comentário no `apps/core/api.py`.
CHAVE_IDENTIDADE = "identidade"

logger = logging.getLogger(__name__)

PAPEL_ALUNO = "aluno"
PAPEL_STAFF = "staff"

# Os quatro estados que a porta precisa distinguir — cada um vira uma tela
# diferente em `apps/core/views.py`.
VISITANTE = "visitante"
DENTRO = "dentro"
SEM_MATRICULA = "sem-matricula"
INDISPONIVEL = "indisponivel"
# [EX-ALUNO] Dois jeitos de NÃO ter acesso que não são "nunca pediu nada"
# (`DECISAO-ex-aluno-e-a-porta-que-explica`). Até 28/08/2026 os dois caíam em
# `SEM_MATRICULA` e recebiam o formulário da fila — mandar quem saiu da escola
# preencher o pedido de entrada é dizer a ela que nunca pediu nada.
PAUSADO = "pausado"
EX_ALUNO = "ex-aluno"
# [RECIBO] 29/08/2026: "nunca pediu nada" e "está esperando decisão" deixaram de
# ser o mesmo estado aqui — e a fusão dos dois era um DEFEITO, não uma
# simplificação. A `alunos` sempre soube a diferença (`GET
# /alunos/{email}/situacao` devolve `na_fila` desde 28/08); esta porta jogava a
# resposta fora e reconstruía uma versão pior dela a partir de um cookie no
# navegador. O mantenedor encontrou o resultado com a própria conta: a tela
# dizia "seu pedido já está com a gente" enquanto a fila do painel estava
# vazia, medida. `DECISAO-o-recibo-e-conferido.md`.
NA_FILA = "na-fila"
# [REEMBOLSO] 31/08/2026: o mantenedor reverteu a decisao dele de 24/08 ("quem ja
# foi aluno mantem a voz") ao encontrar o texto antigo publicado no site.
# Reembolso passou a significar A COMPRA DESFEITA, e quem recebeu o dinheiro de
# volta nao entra. Estado PROPRIO, e nao um apelido de `EX_ALUNO`: os dois nao
# entram, mas o ex-aluno pode pedir para voltar e o reembolsado nao, e a tela de
# cada um diz uma coisa diferente. `DECISAO-reembolso-tira-o-acesso.md`.
REEMBOLSADO = "reembolsado"

#: O que a `alunos` responde ⇒ o estado desta porta. Mapa explícito, e não um
#: `if` por categoria: categoria nova que apareça amanhã cai no `else` de quem
#: chama, e o `else` é o formulário — o mesmo erro, com outro nome. Aqui ela
#: fica de fora do mapa e é tratada como desconhecida, de propósito visível.
ESTADO_POR_CATEGORIA = {
    "aluno": DENTRO,
    "pausado": PAUSADO,
    "ex_aluno": EX_ALUNO,
    "reembolsado": REEMBOLSADO,
    "cadastrado": SEM_MATRICULA,
    "na_fila": NA_FILA,
}

# ---------------------------------------------------------------------------
# Caches por processo (armadilhas/026: módulo vaza entre testes — o conftest
# limpa via `limpar_caches`). O desenho é o mesmo do `funil`: chave pelo
# cabeçalho `Cookie` INTEIRO e opaco (conhecer o nome do cookie alheio é o
# primeiro passo para tentar lê-lo), teto de tamanho para robô não estourar a
# memória, e SÓ RESPOSTAS entram — erro de rede nunca é cacheado.
# ---------------------------------------------------------------------------
TTL_DO_RECONHECIMENTO = 60
# A resposta "esta pessoa É aluna" pode envelhecer à vontade: o custo de um
# "sim" velho é alguém manter acesso por mais alguns minutos depois de perdê-lo
# — situação rara e nada urgente.
TTL_DA_MATRICULA = 600
# A resposta "NÃO é aluna" NÃO pode. Ela custa uma pessoa BARRADA depois de já
# ter sido liberada — e desde 27/08/2026 existe alguém do outro lado esperando
# na frente da tela, com a promessa escrita de que "quando estiver liberado,
# esta página leva você para o site".
#
# Medido em 28/08/2026, com o mantenedor: ele liberou a própria conta pelo
# painel, a pessoa saiu da fila na hora, e a Caixa continuou recusando. O TTL
# era o mesmo dos dois lados (10 min), escrito quando a única forma de virar
# aluno era COMPRAR — um caminho assíncrono, sem ninguém olhando. A fila mudou
# o cenário e o número não acompanhou.
#
# Cinco segundos, e não zero: o valor não é para o humano (ninguém percebe
# cinco segundos), é para não perder a proteção contra rajada — várias
# requisições da MESMA pessoa no mesmo instante continuam custando uma consulta
# só. E o tráfego que passa por aqui é pequeno por construção: desde as cinco
# categorias, a home só oferece a Caixa a quem JÁ é aluno, então quem cai no
# ramo negativo é quem está esperando na fila.
TTL_SEM_MATRICULA = 5
MAXIMO_EM_CACHE = 500
_CACHE_DE_RECONHECIMENTO: dict = {}
_CACHE_DE_MATRICULA: dict = {}


def limpar_caches() -> None:
    _CACHE_DE_RECONHECIMENTO.clear()
    _CACHE_DE_MATRICULA.clear()


def emails_da_staff() -> set[str]:
    """A lista de staff, lida NO PONTO DE USO (EVO-01 §4).

    Ausente ou vazia ⇒ conjunto vazio, e a célula sobe normalmente: ninguém é
    staff, e a porta continua funcionando para alunos.
    """
    crua = os.environ.get("SUGESTOES_STAFF_EMAILS", "")
    return {parte.strip().lower() for parte in crua.split(",") if parte.strip()}


def e_staff(email: str) -> bool:
    return email.strip().lower() in emails_da_staff()


def papel_de(email: str) -> str:
    return PAPEL_STAFF if e_staff(email) else PAPEL_ALUNO


def _id_da_plataforma(dados: dict) -> str | None:
    """O `SessionFull.id` da resposta, normalizado — ou `None`.

    O contrato declara o campo **opcional e nulável** (`anyOf: [string, null]`),
    então "veio", "veio nulo" e "não veio" chegam aqui como três formas do mesmo
    fato: não sei quem é do lado de lá. A coluna tem **uma** forma de não saber
    (`NULL`, imposta por `CheckConstraint`), e é aqui que as três viram uma.
    """
    valor = (dados.get("id") or "").strip()[:64]
    return valor or None


def cunhar_ou_recuperar(
    *, email: str, nome: str, id_da_plataforma: str | None = None
) -> Identidade:
    """A mesma pessoa tem UMA linha local (EVO-01 §3) — hoje como snapshot.

    A idempotência é do banco: `Identidade.email` é `unique`, e `get_or_create`
    transforma a corrida de duas requisições simultâneas numa recuperação. É o
    casamento por e-mail que preservou a autoria de tudo que já existia quando
    o login mudou de casa: quem entra pelo site recupera a linha antiga — e é
    por isso que **a busca continua sendo por e-mail** depois da Fase 1 do plano
    de notificações. O id da plataforma é dado a MAIS, nunca a chave.

    `nome_exibido` só é gravado na CUNHAGEM. Reentrar não sobrescreve: o campo
    é editável pela pessoa, e deixar o provedor reescrevê-lo a cada visita
    apagaria essa escolha sem aviso.

    **[INV-SUG11] O `id_da_plataforma` é gravado em duas frentes**, e a segunda
    é o que faz a Fase 1 valer para quem já existia:

    1. na **cunhagem**, junto com a linha;
    2. na **reentrada**, quando a linha está sem ele — o caminho de toda linha
       nascida antes desta migration, que não tinha de onde tirar o dado.

    Uma linha que JÁ tem id da plataforma **não é sobrescrita** por outro valor:
    seria a mesma pessoa mudando de identidade da plataforma, que é anomalia e
    não rotina. Fica no log e a porta segue — a Caixa não pode cair por causa
    disso, e escolher em silêncio qual dos dois ids é o certo seria pior.

    **Nada disto pode recusar ninguém.** O id da plataforma é dado que a Caixa
    passou a coletar hoje; transformar um problema com ele em porta fechada seria
    punir a pessoa por uma anomalia que ela não tem como resolver. As duas
    frentes engolem o `IntegrityError` da unicidade, cada uma na sua metade.
    """
    email = email.strip().lower()
    defaults = {"provedor": "google", "nome_exibido": nome.strip()[:120]}
    try:
        # O `atomic()` é o savepoint: sem ele, o `IntegrityError` do `unique`
        # envenenaria a transação da requisição inteira, e a página cairia em
        # 500 DEPOIS de a pessoa já ter sido autorizada.
        with transaction.atomic():
            identidade, criada = Identidade.objects.get_or_create(
                email=email,
                defaults={**defaults, "id_da_plataforma": id_da_plataforma},
            )
    except IntegrityError:
        # O id da plataforma já é de OUTRA linha local — acontece quando a
        # pessoa troca de e-mail do lado de lá e vira uma segunda linha aqui.
        # A linha nasce SEM o id (o casamento por e-mail, que é a chave, não
        # depende dele) e a porta segue. Na visita seguinte a frente 2 tenta de
        # novo; se ainda colidir, volta a recusar em silêncio de log.
        logger.warning(
            "nao deu para cunhar %s com o id da plataforma %s "
            "(provavelmente ja pertence a outra linha local); "
            "a identidade nasce sem ele (INV-SUG11)",
            email,
            id_da_plataforma,
        )
        identidade, _ = Identidade.objects.get_or_create(email=email, defaults=defaults)
        return identidade

    if not criada:
        _casar_com_a_plataforma(identidade, id_da_plataforma)
    return identidade


def _casar_com_a_plataforma(
    identidade: Identidade, id_da_plataforma: str | None
) -> None:
    """A frente 2: a linha antiga ganha o id na reentrada. Nunca derruba a porta.

    Três recusas, e cada uma existe por um motivo diferente:

    - **sem id na resposta** ⇒ nada a fazer (a Caixa não inventa o dado);
    - **linha já casada** ⇒ nunca sobrescreve. Igual é no-op; DIFERENTE é
      anomalia, e vai para o log com os dois valores;
    - **`IntegrityError`** ⇒ o id já pertence a OUTRA linha local. Acontece de
      verdade: alguém troca de e-mail lá e vira uma segunda linha aqui. O
      `atomic()` existe por isso — sem o savepoint, a exceção envenenaria a
      transação da requisição inteira e a página cairia em 500 depois de a
      pessoa já ter sido autorizada.
    """
    if id_da_plataforma is None:
        return
    if identidade.id_da_plataforma == id_da_plataforma:
        return
    if identidade.id_da_plataforma:
        logger.warning(
            "identidade local %s ja aponta para %s e a plataforma respondeu %s; "
            "mantido o primeiro (INV-SUG11)",
            identidade.id,
            identidade.id_da_plataforma,
            id_da_plataforma,
        )
        return

    identidade.id_da_plataforma = id_da_plataforma
    try:
        with transaction.atomic():
            identidade.save(update_fields=["id_da_plataforma"])
    except IntegrityError:
        identidade.refresh_from_db(fields=["id_da_plataforma"])
        logger.warning(
            "id da plataforma %s ja pertence a outra identidade local; "
            "a linha %s segue sem ele (INV-SUG11)",
            id_da_plataforma,
            identidade.id,
        )


@dataclass(frozen=True)
class Ator:
    """Quem está fazendo esta requisição. `None` = ninguém, e isso é um estado
    legítimo (a porta é pública; o que está atrás dela não é)."""

    identidade: Identidade
    papel: str

    @property
    def e_staff(self) -> bool:
        return self.papel == PAPEL_STAFF


@dataclass(frozen=True)
class Resolucao:
    """O que a porta precisa saber: o estado, quem é (se dentro) e o e-mail
    (para o recado — a única informação que torna uma recusa resolvível pela
    própria pessoa, EVO-01 §5)."""

    estado: str
    ator: "Ator | None" = None
    email: str = ""


def _sessao_central(cookie: str) -> dict:
    """A resposta da `identidade` para este cookie — com cache curto.

    Erro NÃO entra no cache (senão 60s de indisponibilidade virariam 120):
    só respostas de verdade, inclusive `autenticado: false` — visitante com
    cookie de outra coisa não pode custar um salto por página.
    """
    agora = time.time()
    hit = _CACHE_DE_RECONHECIMENTO.get(cookie)
    if hit and hit[0] > agora:
        return hit[1]
    dados = IdentidadeClient().sessao_completa(cookie)
    if len(_CACHE_DE_RECONHECIMENTO) >= MAXIMO_EM_CACHE:
        _CACHE_DE_RECONHECIMENTO.clear()
    _CACHE_DE_RECONHECIMENTO[cookie] = (agora + TTL_DO_RECONHECIMENTO, dados)
    return dados


def _situacao(email: str) -> str:
    """A CATEGORIA da pessoa, com cache — e com TTL ASSIMÉTRICO.

    Trocou `_tem_matricula` em 28/08/2026: aquela devolvia sim ou não, e com um
    "não" a porta mostrava sempre a mesma tela. Ver `ESTADO_POR_CATEGORIA`.

    Os dois TTLs são diferentes de propósito, e a assimetria é a correção de
    um defeito medido em 28/08/2026 (ver `TTL_SEM_MATRICULA` acima): um "sim"
    velho custa acesso a mais por alguns minutos; um "não" velho custa uma
    pessoa BARRADA depois de já ter sido liberada, olhando para uma tela que
    lhe promete o contrário.

    Quem entra é quem a `alunos` chama de `aluno`, e a lista de status por trás
    disso é dela — nunca reescrita aqui. Até 31/08/2026 `reembolsada` estava
    nessa lista (EVO-01 §4.1, *"quem já foi aluno mantém a voz"*); o mantenedor
    reverteu, e a mudança chegou aqui **sozinha**, sem uma linha nesta célula,
    porque a pergunta é uma só e a resposta mora lá
    (`DECISAO-reembolso-tira-o-acesso.md`).
    """
    chave = email.strip().lower()
    agora = time.time()
    hit = _CACHE_DE_MATRICULA.get(chave)
    if hit and hit[0] > agora:
        return hit[1]
    categoria = AlunosClient().situacao_de(chave)
    if len(_CACHE_DE_MATRICULA) >= MAXIMO_EM_CACHE:
        _CACHE_DE_MATRICULA.clear()
    # A assimetria continua valendo, e agora com a categoria no lugar do bool:
    # só "aluno" pode envelhecer. Todo o resto é um "ainda não" que pode virar
    # "sim" a qualquer clique do mantenedor.
    validade = TTL_DA_MATRICULA if categoria == "aluno" else TTL_SEM_MATRICULA
    _CACHE_DE_MATRICULA[chave] = (agora + validade, categoria)
    return categoria


def resolver(request) -> Resolucao:
    """O fluxo inteiro da porta, para QUALQUER requisição de gente.

    A ordem dos portões é herança direta da porta antiga, e continua não sendo
    arbitrária: **staff antes de matrícula** — quem modera não pode ficar de
    fora quando a `alunos` estiver fora do ar (a pergunta nem chega a ser
    feita; há guarda que estoura se alguém inverter isso um dia).
    """
    # UMA resolução por requisição, guardada na própria requisição. Desde
    # 31/08/2026 o menu do topo também precisa saber se a pessoa entrou (há
    # item que só aparece para quem entrou, e item que só aparece para quem
    # não entrou), e ele é montado por processador de contexto — ou seja,
    # DEPOIS da view que já perguntou. Sem esta memória, toda página de gente
    # logada custaria duas idas à `identidade` e duas à `alunos` em vez de uma.
    #
    # A memória vive na REQUISIÇÃO, e não em módulo: ela morre com a resposta,
    # e duas pessoas nunca compartilham a mesma. Cache de sessão em variável de
    # processo é exatamente como um guarda de "visitante" passa verde mostrando
    # o nome de outra pessoa (`armadilhas/026`).
    guardada = getattr(request, "_resolucao_desta_requisicao", None)
    if guardada is not None:
        return guardada

    resolucao = _resolver(request)
    request._resolucao_desta_requisicao = resolucao
    return resolucao


def _resolver(request) -> Resolucao:
    """A viagem em si. `resolver` é a porta com memória; esta é o caminho."""
    cookie = request.META.get("HTTP_COOKIE", "")
    if not cookie:
        # Sem cookie nenhum não há o que perguntar — e é o caminho de quase
        # toda primeira visita: zero salto de rede.
        return Resolucao(VISITANTE)

    try:
        dados = _sessao_central(cookie)
    except (IdentidadeIndisponivel, ConfiguracaoAusente):
        return Resolucao(INDISPONIVEL)

    if not dados.get("autenticado"):
        return Resolucao(VISITANTE)

    email = (dados.get("email") or "").strip().lower()
    if not email:
        # `autenticado: true` sem e-mail é resposta fora do contrato completo —
        # provavelmente o degrau TOKENS_COMPLETOS faltando do outro lado. Sem
        # e-mail não há como autorizar nada: fecha explicando.
        return Resolucao(INDISPONIVEL)

    nome = (dados.get("nome_exibido") or "").strip()
    # [INV-SUG11] O elo que atravessa a plataforma — e que a porta descartava
    # até 25/08/2026. Ausente ou nulo NÃO recusa ninguém: quem autoriza aqui
    # continua sendo e-mail + (staff | matrícula). Ver `_id_da_plataforma`.
    da_plataforma = _id_da_plataforma(dados)

    if e_staff(email):
        identidade = cunhar_ou_recuperar(
            email=email, nome=nome, id_da_plataforma=da_plataforma
        )
        return Resolucao(DENTRO, Ator(identidade, PAPEL_STAFF), email)

    try:
        categoria = _situacao(email)
    except (AlunosIndisponivel, ConfiguracaoAusente):
        # Falha FECHADA, com a tela dizendo que o problema é nosso — a pessoa
        # não pode sair daqui achando que perdeu a matrícula.
        return Resolucao(INDISPONIVEL, email=email)

    estado = ESTADO_POR_CATEGORIA.get(categoria)
    if estado is None:
        # Categoria que esta porta não conhece. FECHA dizendo que o problema é
        # nosso, em vez de cair no formulário: um vocabulário novo do outro
        # lado não pode fazer esta tela inventar uma história sobre a pessoa.
        return Resolucao(INDISPONIVEL, email=email)
    if estado != DENTRO:
        return Resolucao(estado, email=email)

    identidade = cunhar_ou_recuperar(
        email=email, nome=nome, id_da_plataforma=da_plataforma
    )
    return Resolucao(DENTRO, Ator(identidade, PAPEL_ALUNO), email)


def ator_atual(request):
    """O ator desta requisição, ou `None` — a interface que participação,
    moderação e avisos sempre usaram, agora servida pela resolução central.
    `None` cobre visitante, sem-matrícula e indisponível: para quem AUTORIZA,
    os três significam a mesma coisa (não roda); quem EXPLICA a diferença é a
    porta, via `resolver`."""
    return resolver(request).ator


def ator_da_sessao_legada(request):
    """O leitor do cookie que ESTA célula assinava até 25/08/2026 — e só dele.

    Existe por uma razão: a operação congelada `getSession` da API interna
    desta célula ficou DEPRECADA E INERTE (DECISAO-celula-de-identidade §5) —
    o contrato não muda sem Rito §3, então o endpoint continua respondendo,
    mas nenhum cookie novo é assinado por esta célula desde a virada. Este
    leitor responde pela sessão legada (Django `request.session`), que para
    todo cookie novo falha a assinatura e volta vazia: a resposta real é
    sempre "ninguém". NÃO use em página nenhuma — é peça de museu com contrato.
    """
    identificador = request.session.get(CHAVE_IDENTIDADE)
    if not identificador:
        return None
    identidade = Identidade.objects.filter(pk=identificador).first()
    if identidade is None:
        return None
    return Ator(identidade=identidade, papel=papel_de(identidade.email))


def encerrar_sessao(request) -> None:
    """O `flush()` da sessão Django apaga o cookie `meshcraft_sessao` do
    navegador — nome e Path=/ desta célula são os MESMOS que a `identidade`
    usa (herança da virada de 24/08), então sair da Caixa é sair do site.
    Não é coincidência mantida por sorte: há guarda de settings para o par
    (nome, path) em `tests/test_inv_caixa_nao_assina_sessao.py`."""
    request.session.flush()
