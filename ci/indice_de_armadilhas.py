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
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _nucleo import (  # noqa: E402
    ErroDeInstrumentacao,
    configurar_saida,
    raiz_do_repo,
)

PASTA = "armadilhas"
NOME_DO_INDICE = "INDICE.md"
NOME_DAS_GUARDAS = "GUARDAS.json"
NOME_DOS_SINAIS = "SINAIS.json"

RE_TITULO = re.compile(r"^#\s+(.*\S)\s*$")
RE_ID_NO_TITULO = re.compile(r"^([0-9]+(?:\.[0-9]+)+)\s+(.*)$")
RE_SINTOMA = re.compile(r"^\*\*Sintoma[^*]*\*\*:?\s*(.*)$")
RE_NUMERO_DO_NOME = re.compile(r"^([0-9]+)-")

LIMITE_DA_CELULA = 220

CABECALHO = """<!-- GERADO por `python ci/indice_de_armadilhas.py`. NÃO EDITE À MÃO:
     a próxima regeneração apaga o que você escrever aqui. Para mudar uma linha,
     mude a entrada correspondente em armadilhas/ e regenere. -->

# ÍNDICE DAS ARMADILHAS — uma linha por entrada

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
> `ERROR` e diz para qual número renomear — dois arquivos com o mesmo número
> passam pelo `git rebase` sem conflito nenhum.
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
    "guarda", "sinal", "custo_por_queda",
}
CHAVES_DA_GUARDA = {"tipo", "detector", "dono", "motivo"}
SINAL_MINIMO = 8

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
    def __init__(self, caminho: Path) -> None:
        self.caminho = caminho
        self.nome = caminho.name
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
        if self.frontmatter is not None:
            validar_frontmatter(self.frontmatter, self.nome, self.numero)
            sinal = self.frontmatter.get("sinal")
            if isinstance(sinal, str):
                self.sinais = [sinal]
            elif isinstance(sinal, list):
                self.sinais = [s for s in sinal if s is not None]
            validar_sinais(self.sinais, self.nome)

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

    livre = max(por_numero) + 1
    detalhe = []
    for numero, nomes in colisoes:
        detalhe.append(f"  {numero:03d} — {len(nomes)} arquivos:")
        detalhe.extend(f"    - {PASTA}/{nome}" for nome in nomes)
    repetido = f"{colisoes[0][0]:03d}"
    # Qual dos dois arquivos renomear é uma decisão que este gerador NÃO tem
    # como tomar sozinho (ele não olha o git): renomear o que já está na main
    # quebraria as referências de quem já cita aquela entrada. Por isso a
    # mensagem entrega o comando com o slug em branco e o jeito de descobrir
    # qual é o seu — instrução errada em mensagem de erro custa mais que
    # instrução incompleta.
    detalhe.append(
        "\nDuas sessões escolheram o mesmo 'próximo número livre'. O `git rebase`\n"
        "junta os dois arquivos SEM conflito (nomes diferentes, hunks diferentes)\n"
        "e a pasta fica com dois NNN iguais — foi o que aconteceu em 24/08/2026.\n"
        "\n"
        "Conserte renomeando a SUA entrada — a que ainda NÃO está na main — para o\n"
        f"primeiro número acima de todos, hoje {livre:03d}, e regenere o índice:\n"
        "\n"
        f"  git log origin/main --oneline -- {PASTA}/{repetido}-<slug>.md"
        "   # vazio = essa é a sua\n"
        f"  git mv {PASTA}/{repetido}-<o-seu-slug>.md "
        f"{PASTA}/{livre:03d}-<o-seu-slug>.md\n"
        "  python ci/indice_de_armadilhas.py\n"
        "\n"
        "Não reaproveite um número vago no meio (042, 046…): eles estão\n"
        "aposentados e as referências antigas continuam apontando para eles."
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


def conferir_guardas_vivas(entradas: list[Entrada], raiz: Path) -> None:
    """Guarda que aponta arquivo inexistente é pior que guarda nenhuma.

    Ela faz o índice dizer 'esta lição é imposta por X' quando X não existe —
    e ler nunca dá erro, então ninguém percebe (armadilhas/148). Referência
    morta é ERROR, não FAIL: regenerar não conserta, alguém precisa decidir.
    """
    for entrada in entradas:
        dono = entrada.guarda.get("dono")
        if not dono:
            continue
        if not (raiz / str(dono)).exists():
            raise ErroDeInstrumentacao(
                f"{entrada.nome}: a guarda aponta '{dono}', que não existe",
                "Ou o caminho está errado, ou o mecanismo foi removido sem\n"
                "atualizar a entrada. Corrija o caminho, ou declare\n"
                "'guarda: {tipo: nenhum, motivo: ...}' e assuma o buraco.",
            )


def montar(entradas: list[Entrada]) -> str:
    linhas = [CABECALHO]
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


def rodar(raiz: Path, conferir: bool) -> int:
    entradas = coletar(raiz)
    artefatos = [
        (raiz / PASTA / NOME_DO_INDICE, montar(entradas)),
        (raiz / PASTA / NOME_DAS_GUARDAS, montar_guardas(entradas)),
        (raiz / PASTA / NOME_DOS_SINAIS, montar_sinais(entradas)),
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
    print(
        f"PASS indice-de-armadilhas: {', '.join(escritos)} regenerado(s) "
        f"({len(entradas)} entradas)"
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
            "(o worktree do agente), além da árvore deste arquivo"
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
        try:
            codigo = rodar(raiz, conferir=args.conferir)
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
