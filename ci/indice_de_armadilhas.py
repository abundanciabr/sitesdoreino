"""GERADOR DO `armadilhas/INDICE.md` — a chave de busca da memória de campo.

              ci/indice_de_armadilhas.py
                       ▲
                 ┌─────┼─────┐
                 │     │     │
             Makefile  CI   Agentes

`make indice` na raiz delega para cá. Se `make` não existir numa máquina, o
caminho oficial continua existindo:

    python ci/indice_de_armadilhas.py            # regenera o índice
    python ci/indice_de_armadilhas.py --conferir  # só confere (não escreve)

POR QUE ISTO EXISTE
-------------------
`ARMADILHAS.md` era um monólito append-only de 1.490 linhas — 48% da carga de
contexto de todo despacho, e a fonte nº 1 de conflito de merge em lote (duas
sessões escrevendo no mesmo hunk). Em 23/08/2026 virou uma entrada por arquivo
em `armadilhas/`, e o índice passou a ser **gerado**: o agente lê uma linha por
armadilha e abre só a que casa com a tarefa dele. Índice escrito à mão volta a
inchar e a divergir; gerado, não.

O CONTRATO DE UMA ENTRADA (o mínimo que este gerador precisa)
-------------------------------------------------------------
Um arquivo `armadilhas/NNN-slug.md` com:

    # <título>                 <- primeira linha começando com "# "; se começar
                                  por "N.N ", esse prefixo é lido como o §
                                  histórico (de onde a entrada veio no monólito)
    **Sintoma:** <o erro cru>  <- opcional, mas é o que faz o Ctrl+F funcionar

Nada além disso é obrigatório. A tabela é **plana, uma linha por arquivo, em
ordem de nome** — de propósito: agrupar por categoria exigiria uma declaração
que o próximo agente esquece, e declaração esquecida esconde a entrada do
grupo em silêncio. Uma tabela plana não consegue esconder ninguém.

O NNN É ÚNICO — E ISSO É PORTÃO, NÃO COMBINADO
----------------------------------------------
"NNN = próximo número livre" evita conflito de hunk, mas NÃO evita duas sessões
escolherem o mesmo número. Em 24/08/2026 (EVO-11) um ramo criou
`078-guarda-de-imutabilidade-...md` enquanto outra sessão mergeava
`078-script-injetado-...md` na main: o `git rebase origin/main` juntou os dois
arquivos **sem conflito** — nomes diferentes, hunks diferentes, nada para o git
reclamar — e a pasta ficou com dois `078-`. Este gerador rodava por cima e
produzia um índice com as duas linhas, exit 0. Só um `ls` na mão pegou.

Por isso `NNN` repetido aqui é **ERROR (2)**, não um índice bonito: enquanto o
número for ambíguo, toda citação `armadilhas/078` aponta para dois lugares, e
"o índice está em dia" deixa de significar alguma coisa.

SEMÂNTICA DE SAÍDA ([INV-CI01], igual ao resto da CI)
-----------------------------------------------------
    0  PASS   índice em dia (ou regenerado com sucesso)
    1  FAIL   `--conferir` e o índice no disco diverge das entradas
    2  ERROR  não foi possível medir (pasta ausente, entrada ilegível,
              dois arquivos com o mesmo NNN)

`ERROR` nunca é "quase passou".
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _nucleo import (  # noqa: E402
    ErroDeInstrumentacao,
    configurar_saida,
    raiz_do_repo,
)

# Quem sabe distinguir espelho de bancada é a muralha da pasta compartilhada
# (`.git` DIRETÓRIO = clone principal; `.git` ARQUIVO = worktree). Importar em
# vez de reescrever: duas leituras do mesmo fato divergiriam no primeiro dia.
from muralha_pasta_compartilhada import raiz_do_checkout  # noqa: E402

PASTA = "armadilhas"
NOME_DO_INDICE = "INDICE.md"
NOME_DAS_GUARDAS = "GUARDAS.json"
NOME_DOS_SINAIS = "SINAIS.json"
NOME_DOS_GATILHOS = "GATILHOS.json"

RE_TITULO = re.compile(r"^#\s+(.*\S)\s*$")
RE_ID_NO_TITULO = re.compile(r"^([0-9]+(?:\.[0-9]+)+)\s+(.*)$")
RE_SINTOMA = re.compile(r"^\*\*Sintoma[^*]*\*\*:?\s*(.*)$")
RE_NUMERO_DO_NOME = re.compile(r"^([0-9]+)-")

LIMITE_DA_CELULA = 220

CABECALHO = """<!-- GERADO por `python ci/indice_de_armadilhas.py`. NÃO EDITE À MÃO:
     a próxima regeneração apaga o que você escrever aqui. Para mudar uma linha,
     mude a entrada correspondente em armadilhas/ e regenere. -->

# ÍNDICE DAS ARMADILHAS — uma linha por entrada

> **Antes de tudo, o Padrão de Trabalho:** a PRIMEIRA seção do `CLAUDE.md` da
> raiz é a régua de toda tarefa desta casa — resolver o problema real por trás
> do pedido, discordar antes e executar depois, decidir em vez de servir
> cardápio, a Definição de "Pronto" da regra 6 e as frases proibidas da 10. Ela
> já chegou no seu contexto junto com o `CLAUDE.md`; este lembrete existe porque
> chegar no contexto e ser USADA são coisas diferentes.

> **Antes de codar, leia os 8 padrões:** `docs/decisoes/RETROSPECTIVA-FASE-D.md`.
> Este índice cura o **caso**; lá estão as **categorias** que os atravessam
> (falso-verde · garantia sem mecanismo · prova de fora · fail-closed na borda ·
> humano no caminho crítico · contexto é orçamento · sessões paralelas ·
> viabilidade sem ler a config). É curto, e existe porque conhecer os casos não
> impede repetir a classe — em 48h uma sessão repetiu duas falhas já catalogadas.

> **Como usar:** dê Ctrl+F pela **mensagem de erro crua** que você está vendo (ou
> pela tecnologia: `django-ninja`, `respx`, `middleware`, `mypy`, `traefik`,
> `stash`…). Achou a linha? Abra **só aquele arquivo**. Ler a pasta inteira
> desfaz o motivo de ela existir.
>
> **Entrada nova ao terminar o despacho:** peça o número —
> `python ci/reservar.py numero armadilha` — crie `armadilhas/NNN-slug.md` com
> ele, comece pelo **sintoma concreto** e rode
> `python ci/indice_de_armadilhas.py`. Nunca edite este arquivo à mão, e nunca
> acrescente ao fim de um arquivo alheio — arquivo novo por entrada é o que faz
> duas sessões paralelas pararem de colidir.
>
> **O número NÃO se escolhe** (desde 29/08/2026, e agora é portão):
> `ci/muralha-das-reservas.sh` reprova o PR cujo número de entrada nova não foi
> pedido ao almoxarife. "O primeiro livre" lido da pasta não tem trava nenhuma —
> duas sessões leem, veem o mesmo livre, e o `git merge` junta os dois arquivos
> sem ter o que reclamar. Vagos no meio seguem aposentados: o almoxarife nunca
> reusa número, porque entrada antiga continua sendo citada para sempre.
>
> Se o seu rebase trouxe um `NNN` que outra sessão já usou, o gerador para com
> `ERROR` — dois arquivos com o mesmo número passam pelo `git rebase` sem
> conflito nenhum. O conserto é o mesmo de sempre: **peça outro número ao
> almoxarife** (`python ci/reservar.py numero armadilha`) e renomeie o arquivo E
> o campo `armadilha:` com ele. O gerador não escolhe número por você — se
> escolhesse, a `muralha-das-reservas` reprovaria quem obedecesse.
>
> `§ antigo` é o número que a entrada tinha no `ARMADILHAS.md` monolítico, até
> 23/08/2026 — é por ele que as referências antigas (`ARMADILHAS §5.3`) ainda
> resolvem. Entrada nova não precisa de um.
>
> **`Guarda` diz QUEM faz a lição valer** (desde 29/08/2026). `— sem guarda` não
> é acusação: é o vermelho honesto do B10 — enquanto ninguém a impõe, ela só
> vale se você a tiver lido. `muralha` recusa o comando antes de ele rodar;
> `sino` reconhece a assinatura do erro na saída e aponta a entrada; `CI` é
> portão de PR; `vacina` é o procedimento automatizado que mata a armadilha na
> raiz; `nenhum` é uma escolha DECLARADA, com motivo. Quem mede se isso está
> funcionando é `python ci/termometro.py`.
>
> Resolvidas (histórico, fora da dieta do agente): `docs/historico/RESOLVIDAS.md`.
> O que é do humano (§1 precisa-de-você, como mergear, painéis, dívidas abertas):
> `ARMADILHAS-OPERACAO.md`.

| # | Sintoma / mensagem de erro (chave de busca) | Guarda | § antigo |
|---|---|---|---|
"""


ESTADOS = (
    "observada", "documentada", "recorrente", "candidata",
    "sombra", "guardada", "extinta", "aposentada",
)
CONFIANCAS = ("estrutural", "alta", "media", "baixa")
TIPOS_DE_GUARDA = ("muralha", "sino", "CI", "teste", "vacina", "nenhum")
CUSTOS = ("alto", "medio", "baixo")
CHAVES_DO_SCHEMA = {
    "schema_version", "armadilha", "estado", "degrau", "confianca",
    "guarda", "sinal", "custo_por_queda", "gatilho", "licao",
}
CHAVES_DA_GUARDA = {"tipo", "detector", "dono", "motivo"}
SINAL_MINIMO = 8

# O GATILHO — a mesma lição, indexada pela INTENÇÃO em vez do sintoma.
#
# `sinal` casa a mensagem de erro, então só pode falar DEPOIS da queda: antes
# dela não existe mensagem nenhuma. Medido em 06/09/2026: das 339 entradas do
# catálogo, 140 tinham assinatura de erro e ZERO tinham qualquer forma de dizer
# "isto vai te morder quando você mexer em tal lugar". No mesmo dia a
# armadilhas/179 mordeu uma sessão que a tinha no repositório desde 29/08. Ela
# não foi lida porque ninguém procura por "número repetido" enquanto escreve um
# registro; procura-se depois, quando o CI já reprovou.
#
# `gatilho` é o caminho que a pessoa está prestes a tocar; `licao` é a frase que
# ela precisa ler antes de tocar. Os dois andam juntos: gatilho sem lição manda
# procurar (e procurar é onde a paciência acaba), lição sem gatilho não chega a
# ninguém.
GATILHO_SEGMENTO_MINIMO = 3
LICAO_MINIMA = 25
LICAO_MAXIMA = 400

# Caminhos do dia a dia desta casa. Um gatilho que casa QUALQUER um deles
# interromperia trabalho normal — vira ERROR na geração, não atrito no terminal
# de quem trabalha. É o CORPUS_FELIZ dos sinais, para caminhos: sabote um
# gatilho com `*` e a suíte fica vermelha.
CAMINHOS_INOCENTES = (
    "CLAUDE.md",
    "README.md",
    "ci/travessao.py",
    "ci/tests/test_travessao.py",
    "painel/logica.js",
    "armadilhas/179-numero-do-registro-escolhido-cedo-colide.md",
    "services/admin/apps/core/views.py",
    "services/forum/templates/forum/area.html",
    "docs/decisoes/DECISAO-filosofia-de-escopo.md",
)

# Saídas benignas do dia a dia desta casa. Um sinal que casa QUALQUER uma delas
# tocaria o sino em trabalho normal — vira ERROR na geração, não ruído no
# terminal de quem trabalha. Sabote um sinal com `.*` e a suíte fica vermelha.
CORPUS_FELIZ = (
    "PASS indice-de-armadilhas: em dia (153 entradas)",
    "929 passed in 239.63s (0:03:59)",
    "On branch main\nnothing to commit, working tree clean",
    "Merge pull request #494 from abundanciabr/agent/painel/registro",
    '{"state":"MERGED","mergedBy":{"login":"abundanciabr"}}',
    "✅ os checks do PR 495: todos os 5 checks verdes · levou 1min02s.",
    "RESULTADO  PASS\n\nTudo verde. (--conferir: nada foi mergeado.)",
    "Everything up-to-date",
    "total 48\ndrwxr-xr-x 1 davia 197121 0 Aug 29 16:11 ci",
    "Successfully installed huey-2.5.1 redis-5.0.1",
    # A TABELA do `ci/mergear.py --conferir` num PR saudavel. O
    # "RESULTADO  PASS" acima ja estava no corpus, mas ele e so o RODAPE do
    # relatorio: as linhas de cima faltavam, e foi por esse buraco que o sino
    # tocou em dia feliz. O rotulo "divida do livro" era a assinatura da
    # armadilhas/185 e e dito IGUAL nos dois estados (30/08/2026, TAR-033 /
    # PR 626: duas badaladas em cima de um PASS, na mesma sessao). A tabela
    # entra INTEIRA de proposito: o rotulo de cada linha daqui aparece em todo
    # PR verde, e nenhum deles pode virar assinatura de falha. Assinatura de
    # falha ancora no que SO a falha diz.
    "MERGE GUARDADO — PR #640\n"
    "\n"
    "  estado do PR          PASS   aberto e pronto para revisão\n"
    "  conflitos             PASS   sem conflitos (MERGEABLE)\n"
    "  check/muralhas        PASS   verde\n"
    "  check/ci-celula-gate  PASS   verde\n"
    "  orçamento             PASS   4 arquivo(s)\n"
    "  dívida do livro       PASS   livro em dia\n"
    "\n"
    "RESULTADO  PASS",
    # As outras duas linhas felizes do mesmo relatorio: a isencao de quem so
    # escritura, e o unico pulo declarado como permitido.
    "  dívida do livro       PASS   isento: este PR é o registro",
    "  check/ci-celula (admin)  SKIP   o job da célula é pulado de "
    "propósito quando o PR não toca services/",
    # O balcao da fila em dia (`python ci/fila.py listar`), a outra saida de
    # rotina que todo agente le: ela nomeia tarefa, estado e PR.
    "A FILA DE TRABALHO — 38 tarefa(s) · só arquivos "
    "(use --ao-vivo para reservas e PRs)\n"
    "\n"
    "  TAR-013  [concluída · sessao-tar013-2026-08-30] — "
    "https://github.com/abundanciabr/sitesdoreino/pull/584\n"
    "         A vacina do deploy: medir a porta, repetir com pausa, parar "
    "na terceira  (toca: .github, ci)",
    # Os CABECALHOS CSP SAUDAVEIS da celula `admin`. Faltavam, e por esse
    # buraco a `armadilhas/199` declarava `style-src 'self'` — que e o PREFIXO
    # da politica CERTA, nao a assinatura da errada. O sino badalava em cima da
    # propria cura que a licao manda escrever (30/08/2026, TAR-043).
    #
    # As TRES formas saudaveis entram, porque cada uma refuta uma assinatura
    # tentadora diferente. A primeira e a mais importante: um 302/404 sem corpo
    # nao tem `<style>` para hashear, entao `porta.py::_hashes_de_estilo`
    # devolve vazio DE PROPOSITO e a politica sai com `style-src 'self';` nu.
    # Isso e SAUDE, nao doenca — e e o que `curl -I` no /admin/ devolve num dia
    # perfeitamente normal (medido no ar em 30/08/2026). Sem esta linha aqui, o
    # proximo agente "aperta" a assinatura para o `style-src` sem `sha256-` e
    # reintroduz o mesmo sino falso por outro caminho.
    "HTTP/1.1 302 Found\r\n"
    "Content-Security-Policy: default-src 'self'; script-src 'self'; "
    "style-src 'self'; img-src 'self' data:; object-src 'none'; "
    "base-uri 'none'; form-action 'self'; frame-ancestors 'self'",
    # A politica do painel (`painel.py::_politica_de_seguranca`): `style-src`
    # com `'unsafe-inline'` e as fontes do Google.
    "default-src 'self'; script-src 'self' 'sha256-gaaMFNHZyRta8zB2VHkWLMP4"
    "tMxJ+d8v3dTW7nw2r6M='; style-src 'self' 'unsafe-inline' "
    "https://fonts.googleapis.com; font-src https://fonts.gstatic.com; "
    "img-src 'self' data:; object-src 'none'; base-uri 'none'; "
    "form-action 'self'; frame-ancestors 'self'",
    # A politica da porta com CORPO: `style-src 'self'` MAIS o hash do estilo
    # embutido. Esta linha e literalmente a CURA que a `armadilhas/199` ensina
    # a escrever — nenhuma assinatura de falha pode casar com ela.
    "default-src 'self'; script-src 'self'; style-src 'self' "
    "'sha256-FcQqt3aNlV7AZnGV4zkQRVeCeJOxbMPnQSx258L803E='; "
    "img-src 'self' data:; object-src 'none'; base-uri 'none'; "
    "form-action 'self'; frame-ancestors 'self'",
)


class ErroDeFrontmatter(ErroDeInstrumentacao):
    pass


def ler_frontmatter(linhas: list[str], nome: str) -> dict | None:
    """O bloco `---` do topo, num parser MÍNIMO e estrito.

    Deliberadamente sem `import yaml`: este arquivo roda em portão de CI, e a
    ausência do pyyaml já derrubou um portão inteiro desta casa
    (armadilhas/096). O preço é um dialeto pequeno — `chave: valor`, um nível de
    aninhamento por indentação, e listas de itens `- \\`entre crases\\`` (crase
    para que um regex com `:` e aspas passe intacto). Chave fora do schema é
    ERROR: dialeto que aceita o que não entende cria campo que ninguém lê.
    """
    if not linhas or linhas[0].strip() != "---":
        return None
    try:
        fim = next(i for i, l in enumerate(linhas[1:], start=1) if l.strip() == "---")
    except StopIteration:
        raise ErroDeFrontmatter(
            f"frontmatter sem fechamento em {nome}",
            "O bloco começa com '---' e precisa de outro '---' para fechar.",
        ) from None

    dados: dict = {}
    atual: str | None = None
    for numero, linha in enumerate(linhas[1:fim], start=2):
        if not linha.strip() or linha.lstrip().startswith("#"):
            continue
        indentado = linha[:1].isspace()
        texto = linha.strip()
        if indentado and atual:
            if texto.startswith("- "):
                if dados.get(atual) is None:
                    dados[atual] = []
                if not isinstance(dados[atual], list):
                    raise ErroDeFrontmatter(
                        f"{nome}: '{atual}' mistura lista e chaves (linha {numero})", ""
                    )
                dados[atual].append(_valor(texto[2:].strip()))
                continue
            chave, sep, valor = texto.partition(":")
            if not sep:
                raise ErroDeFrontmatter(
                    f"{nome}: linha {numero} não é 'chave: valor' nem '- item'", ""
                )
            if dados.get(atual) is None:
                dados[atual] = {}
            if not isinstance(dados[atual], dict):
                raise ErroDeFrontmatter(
                    f"{nome}: '{atual}' mistura lista e chaves (linha {numero})", ""
                )
            dados[atual][chave.strip()] = _valor(valor.strip())
            continue
        chave, sep, valor = texto.partition(":")
        if not sep:
            raise ErroDeFrontmatter(
                f"{nome}: linha {numero} não é 'chave: valor'", ""
            )
        chave = chave.strip()
        atual = chave
        if valor.strip():
            dados[chave] = _valor(valor.strip())
        else:
            dados[chave] = None
    return dados


def _valor(cru: str):
    if cru.startswith("`") and cru.endswith("`") and len(cru) > 1:
        return cru[1:-1]  # regex vai entre crases: passa intacto, sem escapes
    if cru in ("null", "~", ""):
        return None
    if cru == "true":
        return True
    if cru == "false":
        return False
    if re.fullmatch(r"-?\d+", cru):
        return int(cru)
    return cru.strip("\"'")


def validar_frontmatter(dados: dict, nome: str, numero: str) -> None:
    sobrando = set(dados) - CHAVES_DO_SCHEMA
    if sobrando:
        raise ErroDeFrontmatter(
            f"{nome}: chave(s) fora do schema: {', '.join(sorted(sobrando))}",
            f"Chaves aceitas: {', '.join(sorted(CHAVES_DO_SCHEMA))}.\n"
            "Campo que ninguém lê é campo que mente — por isso isto é ERROR.",
        )
    if dados.get("schema_version") != 2:
        raise ErroDeFrontmatter(
            f"{nome}: schema_version deve ser 2 (veio {dados.get('schema_version')!r})",
            "Entrada com frontmatter declara schema_version: 2. Entrada SEM\n"
            "frontmatter é legado (schema 1) e continua válida.",
        )
    declarado = str(dados.get("armadilha") or "")
    if declarado.zfill(3) != numero.zfill(3):
        raise ErroDeFrontmatter(
            f"{nome}: frontmatter diz armadilha {declarado}, o arquivo é {numero}",
            "Número que discorda do nome faz o índice apontar para a entrada errada.",
        )
    if dados.get("estado") not in ESTADOS:
        raise ErroDeFrontmatter(
            f"{nome}: estado {dados.get('estado')!r} desconhecido",
            f"Aceitos: {', '.join(ESTADOS)}.",
        )
    if dados.get("confianca") not in CONFIANCAS:
        raise ErroDeFrontmatter(
            f"{nome}: confianca {dados.get('confianca')!r} desconhecida",
            f"Aceitas: {', '.join(CONFIANCAS)}.",
        )
    guarda = dados.get("guarda")
    if not isinstance(guarda, dict) or guarda.get("tipo") not in TIPOS_DE_GUARDA:
        raise ErroDeFrontmatter(
            f"{nome}: guarda.tipo ausente ou desconhecido",
            f"Aceitos: {', '.join(TIPOS_DE_GUARDA)}.\n"
            "'nenhum' é uma escolha legítima — com motivo declarado.",
        )
    sobrando = set(guarda) - CHAVES_DA_GUARDA
    if sobrando:
        raise ErroDeFrontmatter(
            f"{nome}: guarda tem chave(s) fora do schema: {', '.join(sorted(sobrando))}",
            f"Aceitas: {', '.join(sorted(CHAVES_DA_GUARDA))}.",
        )
    if guarda.get("tipo") == "nenhum" and not guarda.get("motivo"):
        raise ErroDeFrontmatter(
            f"{nome}: guarda 'nenhum' sem motivo",
            "Buraco assumido é gerenciável; buraco silencioso não\n"
            "(RETROSPECTIVA-FASE-D §2). Declare por que não dá para mecanizar.",
        )
    custo = dados.get("custo_por_queda")
    if custo is not None and custo not in CUSTOS:
        raise ErroDeFrontmatter(
            f"{nome}: custo_por_queda {custo!r} desconhecido",
            f"Aceitos: {', '.join(CUSTOS)}.",
        )


def validar_gatilhos(gatilhos: list, licao: str, nome: str) -> None:
    """O par gatilho/lição é indivisível, e nenhum gatilho pode ser guloso.

    A régua do padrão não é estética: um gatilho largo (`*`, `services/*`)
    interromperia trabalho legítimo em toda sessão, e um aviso que atrapalha é
    desligado por quem trabalha. Por isso ele precisa de pasta, de um segmento
    literal de verdade, e passa pelo CAMINHOS_INOCENTES.
    """
    if gatilhos and not licao:
        raise ErroDeFrontmatter(
            f"{nome}: gatilho sem licao",
            "O gatilho diz QUANDO avisar; a lição é o que a pessoa lê. Sem ela\n"
            "o aviso manda procurar, e procurar é onde a paciência acaba.",
        )
    if licao and not gatilhos:
        raise ErroDeFrontmatter(
            f"{nome}: licao sem gatilho",
            "Lição sem gatilho não chega a ninguém: nada a dispara. Declare em\n"
            "`gatilho:` o caminho que a pessoa toca antes de cair nesta.",
        )
    if licao and not (LICAO_MINIMA <= len(licao) <= LICAO_MAXIMA):
        raise ErroDeFrontmatter(
            f"{nome}: licao com {len(licao)} caracteres",
            f"Entre {LICAO_MINIMA} e {LICAO_MAXIMA}. Curta demais não ensina;\n"
            "longa demais não é lida na hora em que ela atrapalha.",
        )
    for cru in gatilhos:
        if not isinstance(cru, str) or not cru.strip():
            raise ErroDeFrontmatter(f"{nome}: gatilho não textual: {cru!r}", "")
        padrao = cru.strip()
        if "\\" in padrao:
            raise ErroDeFrontmatter(
                f"{nome}: gatilho com barra invertida: {padrao!r}",
                "Caminho se escreve com `/` aqui, em qualquer sistema: é assim\n"
                "que o gancho compara, e a barra invertida nunca casaria nada.",
            )
        if "/" not in padrao:
            raise ErroDeFrontmatter(
                f"{nome}: gatilho sem pasta: {padrao!r}",
                "Um gatilho é um CAMINHO (`painel/registros/*`), não um nome solto.",
            )
        literais = [
            parte
            for parte in re.split(r"[*?/\[\]]+", padrao)
            if len(parte) >= GATILHO_SEGMENTO_MINIMO
        ]
        if not literais:
            raise ErroDeFrontmatter(
                f"{nome}: gatilho genérico demais: {padrao!r}",
                f"Ele precisa de ao menos um pedaço literal de "
                f"{GATILHO_SEGMENTO_MINIMO} letras.\n"
                "Gatilho largo interrompe trabalho legítimo, e o aviso que\n"
                "atrapalha é o aviso que alguém desliga.",
            )
        for inocente in CAMINHOS_INOCENTES:
            if fnmatch.fnmatch(inocente, padrao):
                raise ErroDeFrontmatter(
                    f"{nome}: o gatilho {padrao!r} casa caminho INOCENTE",
                    f"Casou: {inocente}\n"
                    "Aperte o padrão até ele só reconhecer o gesto que morde.",
                )


def validar_sinais(sinais: list, nome: str) -> None:
    for cru in sinais:
        if not isinstance(cru, str):
            raise ErroDeFrontmatter(f"{nome}: sinal não textual: {cru!r}", "")
        if len(cru) < SINAL_MINIMO:
            raise ErroDeFrontmatter(
                f"{nome}: sinal curto demais ({len(cru)} caracteres): {cru!r}",
                f"Mínimo {SINAL_MINIMO}. Assinatura curta casa saída inocente,\n"
                "e sino que toca à toa é ruído que ninguém mais lê.",
            )
        try:
            compilado = re.compile(cru)
        except re.error as erro:
            raise ErroDeFrontmatter(
                f"{nome}: sinal não compila como regex: {cru!r}", str(erro)
            ) from erro
        if compilado.search(""):
            raise ErroDeFrontmatter(
                f"{nome}: o sinal {cru!r} casa a string vazia",
                "Sinal que casa vazio casa TUDO — o sino tocaria a cada comando.",
            )
        for benigno in CORPUS_FELIZ:
            if compilado.search(benigno):
                raise ErroDeFrontmatter(
                    f"{nome}: o sinal {cru!r} casa saída BENIGNA do dia a dia",
                    f"Casou: {benigno[:70]!r}\n"
                    "Aperte a assinatura até ela só reconhecer a falha de verdade.",
                )


class Entrada:
    def __init__(
        self, caminho: Path, linhas: list[str] | None = None, origem: str = "local"
    ) -> None:
        """`linhas` vem preenchido quando a entrada foi lida do git (a origem),
        e não do disco — o resto do parse é o MESMO, de propósito."""
        self.caminho = caminho
        self.nome = caminho.name
        self.origem = origem
        if linhas is None:
            try:
                linhas = caminho.read_text(encoding="utf-8").splitlines()
            except OSError as erro:  # pragma: no cover - I/O do sistema
                raise ErroDeInstrumentacao(
                    f"não foi possível ler a entrada {caminho.name}", str(erro)
                ) from erro

        titulo = ""
        for linha in linhas:
            achado = RE_TITULO.match(linha)
            if achado:
                titulo = achado.group(1)
                break
        if not titulo:
            raise ErroDeInstrumentacao(
                f"entrada sem título: {caminho.name}",
                "Toda entrada precisa de uma linha começando com '# '.\n"
                "Sem título não há o que indexar — e uma entrada fora do índice\n"
                "é uma entrada que ninguém vai achar.",
            )

        self.id_antigo = ""
        com_id = RE_ID_NO_TITULO.match(titulo)
        if com_id:
            self.id_antigo = com_id.group(1)
            titulo = com_id.group(2)
        self.titulo = titulo

        # O sintoma é um PARÁGRAFO, não uma linha: junta a continuação até a
        # linha em branco ou o próximo campo em negrito (**Causa:**, **Solução:**).
        # Cortar na primeira quebra deixaria a chave de busca partida no meio de
        # uma frase — e é justamente a frase que o Ctrl+F precisa encontrar.
        self.sintoma = ""
        for i, linha in enumerate(linhas):
            achado = RE_SINTOMA.match(linha)
            if not achado:
                continue
            partes = [achado.group(1).strip()]
            for seguinte in linhas[i + 1 :]:
                if not seguinte.strip() or seguinte.startswith(("**", "#", "```", "|")):
                    break
                partes.append(seguinte.strip())
            self.sintoma = " ".join(p for p in partes if p)
            break

        # Metadata CONTROLA, Markdown EXPLICA (29/08/2026). Entrada sem
        # frontmatter é legado (schema 1) e continua válida para sempre — o que
        # separa novo de antigo é a declaração, nunca um número mágico de
        # arquivo, que só vira arqueologia para quem vier depois.
        self.frontmatter = ler_frontmatter(linhas, self.nome)
        self.sinais: list[str] = []
        self.gatilhos: list[str] = []
        self.licao = ""
        if self.frontmatter is not None:
            validar_frontmatter(self.frontmatter, self.nome, self.numero)
            sinal = self.frontmatter.get("sinal")
            if isinstance(sinal, str):
                self.sinais = [sinal]
            elif isinstance(sinal, list):
                self.sinais = [s for s in sinal if s is not None]
            validar_sinais(self.sinais, self.nome)
            gatilho = self.frontmatter.get("gatilho")
            if isinstance(gatilho, str):
                self.gatilhos = [gatilho.strip()]
            elif isinstance(gatilho, list):
                self.gatilhos = [g.strip() for g in gatilho if isinstance(g, str)]
            self.licao = str(self.frontmatter.get("licao") or "").strip()
            validar_gatilhos(self.gatilhos, self.licao, self.nome)

    @property
    def guarda(self) -> dict:
        return (self.frontmatter or {}).get("guarda") or {}

    @property
    def guarda_curta(self) -> str:
        """A célula da coluna — curta de propósito: o índice é dieta de contexto."""
        if self.frontmatter is None:
            return "— sem guarda"
        tipo = self.guarda.get("tipo")
        partes = [tipo] if tipo and tipo != "nenhum" else []
        if self.sinais and "sino" not in partes:
            partes.append("sino")
        if not partes:
            return "nenhum (declarado)"
        return "+".join(partes)

    @property
    def chave(self) -> str:
        """O texto que o Ctrl+F vai varrer: título + sintoma, nessa ordem."""
        partes = [self.titulo]
        if self.sintoma and self.sintoma.lower() not in self.titulo.lower():
            partes.append(self.sintoma)
        texto = " — ".join(partes)
        if len(texto) > LIMITE_DA_CELULA:
            corte = texto[:LIMITE_DA_CELULA]
            espaco = corte.rfind(" ")
            if espaco > LIMITE_DA_CELULA // 2:
                corte = corte[:espaco]
            texto = corte.rstrip(" ,;:—-") + "…"
        return texto.replace("|", r"\|")

    @property
    def numero(self) -> str:
        return self.nome.split("-", 1)[0]

    @staticmethod
    def numero_de(nome: str) -> int | None:
        """O NNN do nome do arquivo como NÚMERO — `078` e `78` são a mesma gaveta.

        Comparar como texto deixaria passar a colisão escrita com outra
        quantidade de zeros, que na hora de citar é igualmente ambígua.
        Devolve `None` para nome sem prefixo numérico — não é entrada numerada,
        e quem chama decide o que fazer com isso.
        """
        achado = RE_NUMERO_DO_NOME.match(nome)
        return int(achado.group(1)) if achado else None

    @property
    def numero_canonico(self) -> int | None:
        return self.numero_de(self.nome)


def conferir_numeracao(entradas: list[Entrada]) -> None:
    """Dois arquivos com o mesmo NNN param o gerador — ERROR, nunca índice.

    Este é o portão que faltava enquanto a regra "NNN = próximo número livre"
    morava só na prosa do CLAUDE.md: a prosa evita o conflito de hunk, mas nada
    impedia duas sessões de escolherem 078 no mesmo dia. Aqui a informação já
    está toda na mão (a pasta inteira acabou de ser varrida), então a checagem
    custa zero e vale em todo caminho — regenerar, `--conferir` e a suíte do
    testador, que é por onde o CI de PR passa.
    """
    por_numero: dict[int, list[str]] = {}
    for entrada in entradas:
        numero = entrada.numero_canonico
        if numero is None:
            continue
        por_numero.setdefault(numero, []).append(entrada.nome)

    colisoes = sorted(
        (numero, sorted(nomes))
        for numero, nomes in por_numero.items()
        if len(nomes) > 1
    )
    if not colisoes:
        return

    detalhe = []
    for numero, nomes in colisoes:
        detalhe.append(f"  {numero:03d} — {len(nomes)} arquivos:")
        detalhe.extend(f"    - {PASTA}/{nome}" for nome in nomes)
    repetido = f"{colisoes[0][0]:03d}"
    # Qual dos dois arquivos renomear é uma decisão que este gerador NÃO tem
    # como tomar sozinho (ele não olha o git): renomear o que já está na main
    # quebraria as referências de quem já cita aquela entrada. Por isso a
    # mensagem entrega o jeito de descobrir qual é o seu — instrução errada em
    # mensagem de erro custa mais que instrução incompleta.
    #
    # E o NÚMERO NOVO NÃO SAI DAQUI. Até 30/08/2026 esta mensagem mandava
    # escolher "o primeiro número acima de todos, hoje NNN" e fazer um `git mv`
    # — e a `muralha-das-reservas` (ci/reservas_das_armadilhas.py) reprova
    # exatamente isso, com "número escolhido à mão". Dois guardas se
    # contradiziam sobre o mesmo número, e obedecer a este custou uma rodada de
    # CI a TRÊS robôs num só dia. Quem dá número é o almoxarife
    # (`ci/reservar.py`), que aloca por comparar-e-trocar no servidor do GitHub;
    # "o primeiro livre que eu vejo agora" é justamente a leitura que as duas
    # sessões fazem ao mesmo tempo. Guarda de erro que ensina o conserto errado
    # é pior que guarda mudo: TAR-036.
    detalhe.append(
        "\nDuas sessões escolheram o mesmo número. O `git rebase` junta os dois\n"
        "arquivos SEM conflito (nomes diferentes, hunks diferentes) e a pasta\n"
        "fica com dois NNN iguais — foi o que aconteceu em 24/08/2026.\n"
        "\n"
        "Conserte a SUA entrada — a que ainda NÃO está na main. Descubra qual é:\n"
        "\n"
        f"  git log origin/main --oneline -- {PASTA}/{repetido}-<slug>.md"
        "   # vazio = essa é a sua\n"
        "\n"
        "PEÇA o número novo ao almoxarife; não escolha um. Ele aloca no servidor\n"
        "do GitHub (comparar-e-trocar), então duas sessões nunca recebem o mesmo:\n"
        "\n"
        "  python ci/reservar.py numero armadilha\n"
        "\n"
        "Com o número que ele devolveu (chame-o de NNN), renomeie o arquivo E o\n"
        "campo `armadilha:` do frontmatter — os dois têm de bater —, ajuste as\n"
        "citações à entrada, e regenere:\n"
        "\n"
        f"  git mv {PASTA}/{repetido}-<o-seu-slug>.md {PASTA}/NNN-<o-seu-slug>.md\n"
        "  python ci/indice_de_armadilhas.py\n"
        "\n"
        "Escolher o número à mão é reprovado pela `muralha-das-reservas` em todo\n"
        "PR, com 'número escolhido à mão' — e não adianta pegar um número vago no\n"
        "meio (042, 046…): eles estão aposentados e as referências antigas\n"
        "continuam apontando para eles."
    )
    raise ErroDeInstrumentacao(
        f"número repetido em '{PASTA}/': "
        + ", ".join(f"{numero:03d}" for numero, _ in colisoes),
        "\n".join(detalhe),
    )


def coletar(raiz: Path) -> list[Entrada]:
    pasta = raiz / PASTA
    if not pasta.is_dir():
        raise ErroDeInstrumentacao(
            f"pasta '{PASTA}/' não encontrada",
            f"Esperada em:\n  {pasta}\n\n"
            "Sem as entradas não há índice — e índice vazio não é índice em dia.",
        )
    arquivos = sorted(p for p in pasta.glob("*.md") if p.name != NOME_DO_INDICE)
    if not arquivos:
        raise ErroDeInstrumentacao(
            f"nenhuma entrada em '{PASTA}/'",
            f"Procurado em:\n  {pasta}\n\n"
            "Zero entradas é indistinguível de 'não consegui listar a pasta';\n"
            "por isso isto é ERROR, não um índice vazio.",
        )
    entradas = [Entrada(p) for p in arquivos]
    conferir_numeracao(entradas)
    conferir_guardas_vivas(entradas, raiz)
    return entradas


# ---------------------------------------------------------------------------
# A ORIGEM COMO FONTE (TAR-050, 04/09/2026)
# ---------------------------------------------------------------------------
# Os hooks rodam de `${CLAUDE_PROJECT_DIR}`, o CLONE PRINCIPAL, que a
# `armadilhas/135` fez de espelho: ninguém trabalha lá, e ninguém o atualiza
# a cada merge. `SINAIS.json` é gerado no `SessionStart` a partir dos
# `armadilhas/*.md` DAQUELA pasta — então o sino de toda sessão desta casa
# enxergava as assinaturas do dia em que o espelho parou. Medido em 30/08/2026:
# 7 assinaturas em vez de 45, com a versão PRÉ-conserto da 185 tocando em cima
# de sucesso. Medido de novo em 04/09/2026: 195 commits atrás, 151 assinaturas
# em vez de 165, 10 entradas a menos. Consertos que já entraram na `main` não
# valiam em sessão nenhuma.
#
# A cura: quando a árvore a materializar é o PRINCIPAL, a fonte das entradas
# passa a ser a UNIÃO do que está em `origin/main` (lido do CACHE do git, sem
# rede: o que o último `git fetch` de alguém deixou) com o que está na pasta,
# e a pasta vence quando as duas têm o mesmo número (é o caso de quem está
# escrevendo uma entrada nova, que ainda não existe na origem). Numa bancada
# (worktree) nada muda: ela nasceu de `origin/main` e a entrada nova está nela.
#
# O que isto NÃO cura, dito com todas as letras: o CÓDIGO dos hooks (este
# gerador, o sino, as muralhas) também é o do espelho. Este conserto só passa a
# valer depois do PRÓXIMO refresh do espelho — e a partir dele os DADOS (as
# assinaturas, que mudam todo dia) ficam frescos para sempre, enquanto o código
# (que muda raramente) segue com a idade do espelho. Atualizar o espelho não é
# tarefa de robô (`armadilhas/135`, `/234`): a pasta é compartilhada.
REF_DA_VERDADE = "origin/main"


def _git(raiz: Path, *argumentos: str) -> subprocess.CompletedProcess | None:
    """Um git que só LÊ o cache local. None = não deu para rodar (sem git, sem
    repositório) — e None nunca vira 'lista vazia'."""
    try:
        return subprocess.run(
            ["git", "-C", str(raiz), *argumentos],
            capture_output=True, timeout=60, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def caminhos_da_origem(raiz: Path, ref: str = REF_DA_VERDADE) -> set[str] | None:
    """Todos os caminhos versionados em `ref`, para conferir `dono` de entrada
    que veio da origem contra a árvore DELA (o arquivo pode não existir aqui)."""
    proc = _git(raiz, "ls-tree", "-r", "--name-only", ref)
    if proc is None or proc.returncode != 0:
        return None
    return set(proc.stdout.decode("utf-8", errors="replace").split("\n")) - {""}


def coletar_da_origem(raiz: Path, ref: str = REF_DA_VERDADE) -> list[Entrada] | None:
    """As entradas como estão em `ref`, lidas do cache do git, sem rede.

    Devolve None quando não dá para medir (sem git, ref ausente num clone raso):
    "não consegui medir" nunca vira "a origem está vazia" ([INV-CI01]).
    Um `git cat-file --batch` só, para os ~300 arquivos: um processo, não 300.
    """
    listagem = _git(raiz, "ls-tree", "--name-only", ref, "--", f"{PASTA}/")
    if listagem is None or listagem.returncode != 0:
        return None
    nomes = sorted(
        Path(linha).name
        for linha in listagem.stdout.decode("utf-8", errors="replace").split("\n")
        if linha.endswith(".md") and Path(linha).name != NOME_DO_INDICE
    )
    if not nomes:
        return None
    pedido = "".join(f"{ref}:{PASTA}/{nome}\n" for nome in nomes).encode("utf-8")
    try:
        lote = subprocess.run(
            ["git", "-C", str(raiz), "cat-file", "--batch"],
            input=pedido, capture_output=True, timeout=120, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if lote.returncode != 0:
        return None
    entradas: list[Entrada] = []
    dados = lote.stdout
    pos = 0
    for nome in nomes:
        fim_do_cabecalho = dados.find(b"\n", pos)
        if fim_do_cabecalho < 0:
            return None
        cabecalho = dados[pos:fim_do_cabecalho].decode("utf-8", errors="replace").split()
        pos = fim_do_cabecalho + 1
        if len(cabecalho) != 3 or cabecalho[1] != "blob":
            return None  # "missing" ou forma inesperada: não medi
        tamanho = int(cabecalho[2])
        corpo = dados[pos:pos + tamanho].decode("utf-8", errors="replace")
        pos += tamanho + 1  # o `\n` que o --batch põe depois do conteúdo
        entradas.append(Entrada(raiz / PASTA / nome, corpo.splitlines(), origem=ref))
    return entradas


def unir(locais: list[Entrada], da_origem: list[Entrada]) -> tuple[list[Entrada], list[Entrada]]:
    """A união pelo NÚMERO, com a pasta local vencendo. Devolve (todas, só-na-origem)."""
    por_numero: dict[int | str, Entrada] = {}
    for e in da_origem:
        por_numero[e.numero_canonico if e.numero_canonico is not None else e.nome] = e
    numeros_locais = set()
    for e in locais:
        chave = e.numero_canonico if e.numero_canonico is not None else e.nome
        por_numero[chave] = e
        numeros_locais.add(chave)
    todas = sorted(por_numero.values(), key=lambda e: e.nome)
    so_na_origem = [e for e in todas if e.origem != "local"]
    return todas, so_na_origem


def conferir_guardas_vivas(
    entradas: list[Entrada], raiz: Path, na_origem: set[str] | None = None
) -> None:
    """Guarda que aponta arquivo inexistente é pior que guarda nenhuma.

    Ela faz o índice dizer 'esta lição é imposta por X' quando X não existe —
    e ler nunca dá erro, então ninguém percebe (armadilhas/148). Referência
    morta é ERROR, não FAIL: regenerar não conserta, alguém precisa decidir.

    Entrada que veio da ORIGEM é conferida contra a árvore da origem
    (`na_origem`): o dono dela pode ainda não existir nesta pasta.
    """
    for entrada in entradas:
        dono = entrada.guarda.get("dono")
        if not dono:
            continue
        existe_aqui = (raiz / str(dono)).exists()
        existe_na_origem = (
            entrada.origem != "local" and na_origem is not None and str(dono) in na_origem
        )
        if not (existe_aqui or existe_na_origem):
            raise ErroDeInstrumentacao(
                f"{entrada.nome}: a guarda aponta '{dono}', que não existe",
                "Ou o caminho está errado, ou o mecanismo foi removido sem\n"
                "atualizar a entrada. Corrija o caminho, ou declare\n"
                "'guarda: {tipo: nenhum, motivo: ...}' e assuma o buraco.",
            )


def nota_do_que_falta_aqui(so_na_origem: list[Entrada]) -> str:
    """Quando o índice foi gerado da união com a origem num espelho atrasado, ele
    lista entradas cujo ARQUIVO não existe nesta pasta. Dizer isso no topo evita
    o `cat` que falha sem explicação: a leitura certa é do `origin/main`."""
    if not so_na_origem:
        return ""
    nomes = ", ".join(f"`{e.nome}`" for e in so_na_origem[:12])
    if len(so_na_origem) > 12:
        nomes += f" e mais {len(so_na_origem) - 12}"
    return (
        f"> **⚠️ {len(so_na_origem)} entrada(s) deste índice ainda NÃO existem nesta "
        f"pasta** — este checkout está atrás de `{REF_DA_VERDADE}`, e o índice foi "
        "gerado da união com a origem para o sino não ficar surdo (TAR-050). "
        f"Abra-as assim: `git show {REF_DA_VERDADE}:{PASTA}/<arquivo>`. "
        f"São: {nomes}.\n\n"
    )


def montar(entradas: list[Entrada], so_na_origem: list[Entrada] | None = None) -> str:
    linhas = [CABECALHO, nota_do_que_falta_aqui(so_na_origem or [])]
    for e in entradas:
        antigo = f"§{e.id_antigo}" if e.id_antigo else "—"
        linhas.append(
            f"| [{e.numero}]({e.nome}) | {e.chave} | {e.guarda_curta} | {antigo} |\n"
        )
    sem_guarda = sum(1 for e in entradas if e.frontmatter is None)
    linhas.append(
        f"\n**{len(entradas)} entradas** — {len(entradas) - sem_guarda} com guarda "
        f"declarada, {sem_guarda} ainda sem.\n"
    )
    return "".join(linhas)


def montar_guardas(entradas: list[Entrada]) -> str:
    """O registro NEUTRO: dados, lidos por quem quiser, sem importar hook nenhum.

    O índice é para humano; este arquivo é para programa (o termômetro, um
    painel futuro). Nenhum dos dois importa `ci/muralha_das_armadilhas.py` — um
    gerador de relatório não pode depender de código de execução. A coerência
    entre esta declaração e a tabela real da muralha é provada por teste-guarda.
    """
    corpo = {
        "versao": 1,
        "gerado_por": "python ci/indice_de_armadilhas.py",
        "guardas": [
            {
                "armadilha": e.numero,
                "arquivo": f"{PASTA}/{e.nome}",
                "estado": (e.frontmatter or {}).get("estado"),
                "degrau": (e.frontmatter or {}).get("degrau"),
                "confianca": (e.frontmatter or {}).get("confianca"),
                "custo_por_queda": (e.frontmatter or {}).get("custo_por_queda"),
                "tipo": e.guarda.get("tipo"),
                "detector": e.guarda.get("detector"),
                "dono": e.guarda.get("dono"),
                "tem_sinal": bool(e.sinais),
            }
            for e in entradas
            if e.frontmatter is not None
        ],
    }
    return json.dumps(corpo, ensure_ascii=False, indent=2) + "\n"


def montar_sinais(entradas: list[Entrada]) -> str:
    """As assinaturas que o sino compara com a saída dos comandos."""
    corpo = {
        "versao": 1,
        "gerado_por": "python ci/indice_de_armadilhas.py",
        "sinais": [
            {
                "armadilha": e.numero,
                "arquivo": f"{PASTA}/{e.nome}",
                "titulo": e.titulo,
                "regex": regex,
            }
            for e in entradas
            for regex in e.sinais
        ],
    }
    return json.dumps(corpo, ensure_ascii=False, indent=2) + "\n"


def montar_gatilhos(entradas: list[Entrada]) -> str:
    """As lições que o gancho entrega ANTES de o robô tocar num caminho.

    Uma linha por par (armadilha, caminho): quem lê agrupa por caminho, porque
    o mesmo gesto pode ter mais de uma lição e quem trabalha merece receber as
    duas de uma vez, não uma interrupção para cada.
    """
    corpo = {
        "versao": 1,
        "gerado_por": "python ci/indice_de_armadilhas.py",
        "gatilhos": [
            {
                "armadilha": e.numero,
                "arquivo": f"{PASTA}/{e.nome}",
                "titulo": e.titulo,
                "caminho": padrao,
                "licao": e.licao,
            }
            for e in entradas
            for padrao in e.gatilhos
        ],
    }
    return json.dumps(corpo, ensure_ascii=False, indent=2) + "\n"


def rodar(raiz: Path, conferir: bool, com_a_origem: bool = False) -> int:
    entradas = coletar(raiz)
    so_na_origem: list[Entrada] = []
    if com_a_origem:
        da_origem = coletar_da_origem(raiz)
        if da_origem is None:
            # Não medi a origem. Falo, e sigo só com a pasta — nunca finjo que
            # a origem está vazia nem que está igual ([INV-CI01]).
            print(
                f"AVISO indice-de-armadilhas: não consegui ler `{REF_DA_VERDADE}` "
                f"em {raiz} (sem git, sem a ref, ou clone raso). Gerado só da "
                f"pasta local — pode estar atrasado (TAR-050).",
                file=sys.stderr,
            )
        else:
            entradas, so_na_origem = unir(entradas, da_origem)
            conferir_numeracao(entradas)
            conferir_guardas_vivas(entradas, raiz, caminhos_da_origem(raiz))
    artefatos = [
        (raiz / PASTA / NOME_DO_INDICE, montar(entradas, so_na_origem)),
        (raiz / PASTA / NOME_DAS_GUARDAS, montar_guardas(entradas)),
        (raiz / PASTA / NOME_DOS_SINAIS, montar_sinais(entradas)),
        (raiz / PASTA / NOME_DOS_GATILHOS, montar_gatilhos(entradas)),
    ]

    if conferir:
        divergentes = [
            destino for destino, esperado in artefatos
            if (destino.read_text(encoding="utf-8") if destino.is_file() else None)
            != esperado
        ]
        if not divergentes:
            print(f"PASS indice-de-armadilhas: em dia ({len(entradas)} entradas)")
            return 0
        for destino in divergentes:
            print(
                f"FAIL indice-de-armadilhas: {destino.relative_to(raiz)} "
                f"diverge das {len(entradas)} entradas de {PASTA}/.",
                file=sys.stderr,
            )
        print(
            "Regenere com:\n  python ci/indice_de_armadilhas.py\n"
            "(são gerados — editá-los à mão é o que faz eles divergirem)",
            file=sys.stderr,
        )
        return 1

    escritos = []
    for destino, esperado in artefatos:
        atual = destino.read_text(encoding="utf-8") if destino.is_file() else None
        if atual != esperado:
            destino.write_text(esperado, encoding="utf-8", newline="\n")
            escritos.append(destino.name)
    if not escritos:
        print(f"PASS indice-de-armadilhas: já estava em dia ({len(entradas)} entradas)")
        return 0
    de_fora = f", {len(so_na_origem)} só em {REF_DA_VERDADE}" if so_na_origem else ""
    print(
        f"PASS indice-de-armadilhas: {', '.join(escritos)} regenerado(s) "
        f"({len(entradas)} entradas{de_fora})"
    )
    return 0


def raizes_a_materializar(tambem_aqui: bool) -> list[Path]:
    """As árvores onde este comando deve materializar os gerados.

    Sempre a árvore DESTE arquivo (`raiz_do_repo()` resolve pelo `__file__`, do
    mesmo jeito que `ci/mergear.py` — `armadilhas/147`). Com `--tambem-aqui`,
    também a árvore de onde o comando foi chamado, quando ela é outra.

    Por que a segunda existe (30/08/2026, TAR-022): desde que os gerados saíram
    do Git, quem os materializa é a integração — e o `SessionStart` chama
    `python "${CLAUDE_PROJECT_DIR}/ci/indice_de_armadilhas.py"`, que aponta
    SEMPRE para o clone principal. É de lá que o sino lê (`ci/sino_das_armadilhas.py`
    resolve pelo `__file__` dele também), então o clone principal precisa mesmo
    ser materializado. Mas o agente trabalha num WORKTREE (RITOS §1), e é lá que
    ele vai abrir o `INDICE.md`. Sem esta flag, uma árvore ficaria sempre sem os
    arquivos — e a lei que manda ler o índice no começo de toda tarefa
    dependeria de alguém lembrar de rodar o gerador à mão.
    """
    raizes = [raiz_do_repo()]
    if not tambem_aqui:
        return raizes
    try:
        aqui = raiz_do_repo(Path.cwd())
    except ErroDeInstrumentacao:
        # Chamado de fora de qualquer checkout: a árvore do próprio arquivo já
        # foi materializada, e isso é tudo o que dá para prometer daqui.
        return raizes
    if aqui not in raizes:
        raizes.append(aqui)
    return raizes


def e_o_principal(raiz: Path) -> bool:
    """`.git` DIRETÓRIO = clone principal (o espelho, de onde os hooks rodam);
    `.git` ARQUIVO = worktree. Fora de git: não é principal (não há origem)."""
    achado = raiz_do_checkout(raiz)
    return bool(achado and achado[1] and achado[0] == raiz.resolve())


def main(argv: list[str] | None = None) -> int:
    # Console cp1252 do Windows não pode virar UnicodeEncodeError no meio de uma
    # mensagem de erro acentuada (armadilhas/003).
    configurar_saida()
    parser = argparse.ArgumentParser(
        description="Regenera (ou confere) o índice das armadilhas."
    )
    parser.add_argument(
        "--conferir",
        action="store_true",
        help="não escreve: reprova (exit 1) se o índice estiver desatualizado",
    )
    parser.add_argument(
        "--tambem-aqui",
        action="store_true",
        help=(
            "materializa também na árvore de onde o comando foi chamado "
            "(o worktree do agente), além da árvore deste arquivo; no CLONE "
            "PRINCIPAL, gera da união com origin/main (TAR-050)"
        ),
    )
    parser.add_argument(
        "--com-a-origem",
        action="store_true",
        help=(
            "gera da UNIÃO das entradas de origin/main (cache do git, sem rede) "
            "com as da pasta, a pasta vencendo — para um checkout atrasado não "
            "deixar o sino surdo. Com --tambem-aqui isto é automático no clone "
            "principal"
        ),
    )
    args = parser.parse_args(argv)
    try:
        raizes = raizes_a_materializar(args.tambem_aqui)
    except ErroDeInstrumentacao as erro:
        print(f"ERROR indice-de-armadilhas: {erro}", file=sys.stderr)
        detalhe = getattr(erro, "detalhe", "")
        if detalhe:
            print(detalhe, file=sys.stderr)
        return 2

    pior = 0
    for raiz in raizes:
        com_a_origem = args.com_a_origem or (args.tambem_aqui and e_o_principal(raiz))
        try:
            codigo = rodar(raiz, conferir=args.conferir, com_a_origem=com_a_origem)
        except ErroDeInstrumentacao as erro:
            print(f"ERROR indice-de-armadilhas: {erro}", file=sys.stderr)
            detalhe = getattr(erro, "detalhe", "")
            if detalhe:
                print(detalhe, file=sys.stderr)
            codigo = 2
        pior = max(pior, codigo)
    return pior


if __name__ == "__main__":
    raise SystemExit(main())
