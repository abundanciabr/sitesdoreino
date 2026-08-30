#!/usr/bin/env python3
"""O TRAVESSÃO NÃO ATRAVESSA — texto publicado sai sem travessão.

Decisão do mantenedor em 30/08/2026: **todo texto escrito para ser publicado
online sai sem travessão.** No lugar dele entram vírgula, parênteses,
dois-pontos ou aspas, conforme o papel que o travessão fazia na frase. A escolha
é de quem escreve; este portão não escolhe por ninguém — ele só recusa o
travessão e ensina as quatro trocas.

POR QUE ISTO É UM PORTÃO, E NÃO UM CONSELHO
-------------------------------------------
A doença-mãe deste projeto é regra escrita que ninguém impõe
(`ci/leis_sem_mecanismo.py`): ela não falha, não apita, e é obedecida enquanto
alguém lembrar. Uma regra de ESCRITA é o caso extremo dessa doença — quem
escreve o texto novo é uma sessão diferente a cada vez, e nenhuma delas leu o
que a anterior combinou. Só um portão atravessa sessões.

A SUPERFÍCIE PÚBLICA — o que ele olha, e por que assim
------------------------------------------------------
O mantenedor definiu a fronteira em 30/08/2026: **entra tudo que alguém que não
é ele lê.** A vitrine do site, o cadastro, o login, o checkout, o quiz, o
fórum, a área do aluno, a Caixa de Sugestões, os documentos publicados e as
traduções. Fica de fora o bastidor: o painel dele e as telas de administração,
que ninguém além dele abre.

A superfície é DERIVADA, não listada: toda pasta `templates/` de toda célula,
toda pasta `traducoes/`, e `documentos/`. Célula nova, ou tela nova numa célula
que já existe, entra sozinha — é fail-closed, e é de propósito. Um mapa de
caminhos mantido à mão envelheceria em silêncio, que é a Classe 8 do
`PLANO-MESTRE-ROBOS-SEM-COLISAO.md` e já cobrou caro aqui.

O bastidor sai por uma lista CURTA e declarada (`ci/texto-publico-bastidor.txt`),
uma linha por padrão, com o motivo escrito. A inversão importa: em dúvida, o
texto é público. Tirar algo da regra exige uma linha no diff que alguém vê.

O QUE CONTA COMO TRAVESSÃO
--------------------------
As três riscas longas (`—` travessão, `–` meia-risca, `―` barra horizontal) e
as formas escritas em HTML que viram risca na tela (`&mdash;`, `&ndash;`,
`&#8212;`, `&#x2014;`, ...). O HÍFEN (`-`) nunca entra: ele é letra de palavra
composta ("guarda-chuva"), não pontuação de frase. Um portão que caçasse hífen
seria um portão que recusa português correto, e viraria ruído até alguém o
desligar.

COMENTÁRIO NÃO É TEXTO PUBLICADO
--------------------------------
`{% comment %}`, `{# #}`, `<!-- -->` e `#` de YAML não chegam a leitor nenhum.
Eles são despidos antes da contagem — e sem essa poda a dívida medida aqui
seria quatro vezes maior e quase toda falsa, o que treinaria todo mundo a
ignorar o portão. Medir a coisa errada com precisão é como um portão morre.

O QUE ELE **NÃO** MEDE, dito na cara
------------------------------------
Texto publicado que more em `.py`. A superfície é de `templates/`,
`traducoes/` e `documentos/`, e só — e isto **é um buraco real**, não uma
categoria vazia. Ele tem pelo menos um morador conhecido: as descrições das
áreas do fórum nascem em
`services/forum/apps/forum/management/commands/semear_areas.py` e aparecem em
`meshcraft.top/forum`.

Varrer `.py` inteiro seria pior que o buraco: das 160 strings com travessão nas
células públicas, a esmagadora maioria é docstring, mensagem de log e texto de
validação que só um programador lê. O caminho certo é a superfície crescer para
a classe ESTREITA de arquivos que existem para criar conteúdo público (os
`semear_*`), lendo só as constantes de string que não são docstring.

Também fica de fora `painel/ia/`, servido em `/mapa-ia/` sem porta: é mapa
TÉCNICO, escrito para uma IA de fora auditar o sistema, e a régua do
mantenedor é a leitura de PESSOAS. São 314 travessões que nenhum aluno lê.

Se um dia a cópia do site passar a morar em `.py`, é aqui que a superfície
cresce. Enquanto não passar, este parágrafo é a diferença entre um limite
conhecido e um buraco.

A CATRACA DA DÍVIDA HERDADA
---------------------------
O texto que já estava publicado quando a regra nasceu está em
`ci/travessoes-herdados.txt`, arquivo por arquivo, com a contagem exata. O
número declarado é um COMPROMISSO, não um teto frouxo:

    contagem real > declarada  ->  FAIL (a dívida cresceu)
    contagem real < declarada  ->  FAIL, com a linha nova pronta para colar
    arquivo fora da lista com travessão  ->  FAIL (texto novo não nasce devendo)

Baixar o número é sempre permitido, e é o objetivo. Exigir que o diff MOSTRE a
queda é o que impede a lista de virar ficção — a mesma forma de
`ci/guardas-nao-declarados.txt` e `ci/leis-sem-mecanismo.txt`, que já provaram
funcionar aqui.

Uso:

    python ci/travessao.py             # o portão (o que a CI roda)
    python ci/travessao.py --listar    # o censo, para leitura humana
    python ci/travessao.py --herdados  # a lista pronta para colar no arquivo

Exit codes: 0 PASS · 1 travessão em texto público · 2 ERROR (não mediu).
"""

from __future__ import annotations

import argparse
import fnmatch
import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _nucleo import (  # noqa: E402
    ErroDeInstrumentacao,
    Estado,
    Relatorio,
    Resultado,
    configurar_saida,
    raiz_do_repo,
)

LISTA_DE_HERDADOS = "ci/travessoes-herdados.txt"
LISTA_DE_BASTIDOR = "ci/texto-publico-bastidor.txt"

# ---------------------------------------------------------------------------
# O que é travessão. Cada forma tem nome, porque a recusa cita o nome.
# ---------------------------------------------------------------------------
FORMAS = (
    ("—", "travessão (—)"),
    ("–", "meia-risca (–)"),
    ("―", "barra horizontal (―)"),
    ("&mdash;", "travessão escrito em HTML (&mdash;)"),
    ("&ndash;", "meia-risca escrita em HTML (&ndash;)"),
    ("&horbar;", "barra horizontal em HTML (&horbar;)"),
    ("&#8212;", "travessão em código HTML (&#8212;)"),
    ("&#8211;", "meia-risca em código HTML (&#8211;)"),
    ("&#x2014;", "travessão em código HTML (&#x2014;)"),
    ("&#x2013;", "meia-risca em código HTML (&#x2013;)"),
)

# Pastas que nunca são texto publicado, em qualquer profundidade.
PASTAS_IGNORADAS = {"__pycache__", ".venv", "node_modules", ".git", "tests", "testes"}

# A lição que a recusa entrega, palavra por palavra do mantenedor. Ela viaja
# junto do erro de propósito: quem topa com o portão precisa saber como sair
# dele na mesma tela, sem abrir documento nenhum (a linha de precisão das
# muralhas desta casa — "a recusa entrega uma alternativa EXECUTÁVEL na hora").
COMO_TROCAR = """\
COMO TROCAR — escolha pelo papel que o travessão fazia na frase:

  VÍRGULA (troca neutra) — explicação comum, no meio da frase. Mantém a
  leitura fluida e natural.
      antes:  O motorista — que estava muito cansado — parou no posto.
      depois: O motorista, que estava muito cansado, parou no posto.

  PARÊNTESES (troca de menor destaque) — dado acessório, que pode ser
  ignorado sem perda.
      antes:  A inflação — principal vilã do orçamento — voltou a subir.
      depois: A inflação (principal vilã do orçamento) voltou a subir.

  DOIS-PONTOS (troca de fechamento) — quando o trecho isolado fica no FIM da
  frase e serve de esclarecimento ou conclusão.
      antes:  Ele só queria uma coisa — paz.
      depois: Ele só queria uma coisa: paz.

  ASPAS (troca de diálogo) — quando o travessão marcava fala de personagem.
      antes:  — Não quero ir hoje — disse Pedro.
      depois: "Não quero ir hoje", disse Pedro.

O hífen (-) continua livre: ele é letra de palavra composta, não pontuação."""


@dataclass(frozen=True)
class Achado:
    """Um travessão vivo num texto que alguém vai ler."""

    caminho: str
    linha: int
    forma: str
    trecho: str


# ---------------------------------------------------------------------------
# Despir o texto: o que é comentário não chega a leitor nenhum.
#
# Toda poda troca o comentário por ESPAÇOS do mesmo tamanho, nunca por vazio.
# Assim o número da linha e a coluna continuam batendo com o arquivo real, e a
# recusa aponta para o lugar certo. Um portão que erra a linha manda o leitor
# procurar, e procurar é onde a paciência acaba.
# ---------------------------------------------------------------------------
def _apagar(texto: str, inicio: int, fim: int) -> str:
    miolo = texto[inicio:fim]
    return texto[:inicio] + "".join("\n" if c == "\n" else " " for c in miolo) + texto[fim:]


def _podar_par(texto: str, abre: str, fecha: str) -> str:
    """Apaga todo trecho entre `abre` e `fecha`, inclusive os delimitadores.

    Abertura sem fechamento apaga até o fim do arquivo: um comentário que
    ninguém fechou também não é publicado, e tratar o resto como texto vivo
    inventaria achados que não existem na tela.
    """
    saida = texto
    procura = 0
    while True:
        i = saida.find(abre, procura)
        if i < 0:
            return saida
        j = saida.find(fecha, i + len(abre))
        fim = len(saida) if j < 0 else j + len(fecha)
        saida = _apagar(saida, i, fim)
        procura = fim


RE_COMENTARIO_DJANGO = re.compile(r"\{%-?\s*comment\b.*?%\}", re.DOTALL)


def _podar_comentario_django(texto: str) -> str:
    """`{% comment %} … {% endcomment %}`, inclusive com rótulo e com `{%- -%}`."""
    saida = texto
    procura = 0
    while True:
        abre = RE_COMENTARIO_DJANGO.search(saida, procura)
        if abre is None:
            return saida
        fecha = saida.find("endcomment", abre.end())
        if fecha < 0:
            fim = len(saida)
        else:
            marca = saida.find("%}", fecha)
            fim = len(saida) if marca < 0 else marca + 2
        saida = _apagar(saida, abre.start(), fim)
        procura = fim


def _podar_comentario_de_linha(texto: str, marca: str, exigir_folga: bool) -> str:
    """`marca` até o fim da linha, mas só FORA de aspas.

    `titulo: "Promoção # 2"` publica a cerquilha; tratá-la como comentário
    cegaria o portão para o resto da linha, que é justamente onde o texto do
    site mora. Em JS a mesma regra vale para `//`, com o cuidado extra de não
    confundir com o `//` de uma URL (`https://…`).

    `exigir_folga` pede espaço antes da marca — é o que separa o `#` de
    comentário do `#` colado numa palavra.
    """
    saida = []
    for linha in texto.split("\n"):
        aspas: str | None = None
        corte = None
        pos = 0
        while pos < len(linha):
            c = linha[pos]
            if aspas:
                if c == aspas and linha[pos - 1] != "\\":
                    aspas = None
            elif c in "'\"`":
                aspas = c
            elif linha.startswith(marca, pos):
                anterior = linha[pos - 1] if pos else " "
                folga_ok = (not exigir_folga) or anterior in " \t" or pos == 0
                if folga_ok and anterior != ":":
                    corte = pos
                    break
            pos += 1
        saida.append(linha if corte is None else linha[:corte] + " " * (len(linha) - corte))
    return "\n".join(saida)


def _podar_comentario_de_yaml(texto: str) -> str:
    return _podar_comentario_de_linha(texto, "#", exigir_folga=True)


RE_BLOCO_DE_CODIGO = re.compile(r"<(script|style)\b[^>]*>(.*?)</\1\s*>", re.DOTALL | re.IGNORECASE)


def _podar_comentario_de_codigo(texto: str) -> str:
    """Comentário de JS e de CSS dentro de `<script>`/`<style>` também não é lido.

    Sem esta poda o portão reprovava a nota de um programador dentro de um
    `/* … */` — texto que nenhum visitante recebe. Reprovar comentário de código
    é a definição de portão chato, e portão chato é desligado por quem trabalha:
    a lição está na `docs/decisoes/RETROSPECTIVA-FASE-D.md`.

    A poda é DELIBERADAMENTE estreita. Só o miolo de `<script>` e `<style>`
    entra, para um `/*` solto no meio do HTML nunca comer texto de verdade; e o
    `//` só corta fora de aspas, porque `x_text="\\`${a} — ${b}\\`"` é rótulo na
    tela, não comentário.
    """
    saida = texto
    for casa in RE_BLOCO_DE_CODIGO.finditer(texto):
        inicio, fim = casa.span(2)
        miolo = saida[inicio:fim]
        limpo = _podar_par(miolo, "/*", "*/")
        limpo = _podar_comentario_de_linha(limpo, "//", exigir_folga=False)
        saida = saida[:inicio] + limpo + saida[fim:]
    return saida


def despir(texto: str, sufixo: str) -> str:
    """O texto como o leitor o recebe: sem os comentários de quem escreveu."""
    if sufixo in (".html", ".htm"):
        texto = _podar_comentario_django(texto)
        texto = _podar_par(texto, "{#", "#}")
        texto = _podar_par(texto, "<!--", "-->")
        return _podar_comentario_de_codigo(texto)
    if sufixo in (".yaml", ".yml"):
        return _podar_comentario_de_yaml(texto)
    if sufixo == ".md":
        return _podar_par(texto, "<!--", "-->")
    return texto


# ---------------------------------------------------------------------------
# A superfície pública, derivada do repositório (nunca listada à mão).
# ---------------------------------------------------------------------------
def _padroes_de_bastidor(raiz: Path) -> list[str]:
    arquivo = raiz / LISTA_DE_BASTIDOR
    if not arquivo.is_file():
        raise ErroDeInstrumentacao(
            "a lista do bastidor não existe",
            f"Esperada em:\n  {arquivo}\n\n"
            "Sem ela o portão não sabe o que é tela de administração e o que é\n"
            "texto público. Lista ausente não é lista vazia: medir a superfície\n"
            "errada é pior que não medir.",
        )
    padroes = []
    for bruta in arquivo.read_text(encoding="utf-8").splitlines():
        linha = bruta.strip()
        if not linha or linha.startswith("#"):
            continue
        padrao, _, motivo = linha.partition("::")
        if len(motivo.strip()) < 15:
            raise ErroDeInstrumentacao(
                "linha do bastidor sem motivo escrito",
                f"Em {LISTA_DE_BASTIDOR}:\n  {linha}\n\n"
                "Toda linha tira um texto da regra: `<padrão> :: <por que ninguém\n"
                "de fora lê isto>`. Carimbo de menos de 15 caracteres não é motivo.",
            )
        padroes.append(padrao.strip())
    return padroes


def _dentro_de_pasta_ignorada(relativo: Path) -> bool:
    return any(parte in PASTAS_IGNORADAS for parte in relativo.parts)


def superficie(raiz: Path) -> list[Path]:
    """Todo arquivo cujo texto alguém que não é o mantenedor pode ler."""
    achados: set[Path] = set()

    documentos = raiz / "documentos"
    if documentos.is_dir():
        achados |= {p for p in documentos.rglob("*.md") if p.is_file()}

    servicos = raiz / "services"
    if not servicos.is_dir():
        raise ErroDeInstrumentacao(
            "não encontrei services/ para derivar a superfície pública",
            f"Procurei em:\n  {servicos}\n\nSem as células não há o que medir.",
        )
    for celula in sorted(p for p in servicos.iterdir() if p.is_dir()):
        for pasta in celula.rglob("templates"):
            if not pasta.is_dir():
                continue
            for sufixo in (".html", ".htm", ".txt", ".md"):
                achados |= {p for p in pasta.rglob(f"*{sufixo}") if p.is_file()}
        for pasta in celula.rglob("traducoes"):
            if not pasta.is_dir():
                continue
            for sufixo in (".yaml", ".yml"):
                achados |= {p for p in pasta.rglob(f"*{sufixo}") if p.is_file()}

    bastidor = _padroes_de_bastidor(raiz)
    publicos = []
    for caminho in achados:
        relativo = caminho.relative_to(raiz)
        if _dentro_de_pasta_ignorada(relativo):
            continue
        texto = relativo.as_posix()
        if any(fnmatch.fnmatch(texto, padrao) for padrao in bastidor):
            continue
        publicos.append(caminho)
    return sorted(publicos)


# ---------------------------------------------------------------------------
# A contagem.
# ---------------------------------------------------------------------------
def achar(texto: str, sufixo: str, caminho: str) -> list[Achado]:
    """Os travessões vivos de um texto, já despido dos comentários."""
    limpo = despir(texto, sufixo)
    achados: list[Achado] = []
    for numero, linha in enumerate(limpo.split("\n"), start=1):
        for marca, nome in FORMAS:
            posicao = linha.find(marca)
            while posicao >= 0:
                achados.append(
                    Achado(caminho, numero, nome, _recorte(linha, posicao, len(marca)))
                )
                posicao = linha.find(marca, posicao + len(marca))
    return sorted(achados, key=lambda a: (a.linha, a.forma))


def _recorte(linha: str, posicao: int, tamanho: int, folga: int = 32) -> str:
    inicio = max(0, posicao - folga)
    fim = min(len(linha), posicao + tamanho + folga)
    trecho = linha[inicio:fim].strip()
    return ("…" if inicio > 0 else "") + trecho + ("…" if fim < len(linha) else "")


def censo(raiz: Path) -> dict[str, list[Achado]]:
    """Arquivo público -> travessões vivos nele. Só entra quem tem algum."""
    resultado: dict[str, list[Achado]] = {}
    for caminho in superficie(raiz):
        relativo = caminho.relative_to(raiz).as_posix()
        try:
            texto = caminho.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as erro:
            raise ErroDeInstrumentacao(
                f"não consegui ler {relativo}",
                f"{erro}\n\nUm arquivo público ilegível não é um arquivo limpo.",
            ) from erro
        achados = achar(texto, caminho.suffix.lower(), relativo)
        if achados:
            resultado[relativo] = achados
    return resultado


# ---------------------------------------------------------------------------
# A catraca da dívida herdada.
# ---------------------------------------------------------------------------
def herdados(raiz: Path) -> dict[str, int]:
    arquivo = raiz / LISTA_DE_HERDADOS
    if not arquivo.is_file():
        raise ErroDeInstrumentacao(
            "a lista da dívida herdada não existe",
            f"Esperada em:\n  {arquivo}\n\n"
            "Lista ausente faria todo texto antigo virar violação de uma vez.\n"
            "Isso não é rigor: é um portão que ninguém consegue atender, e um\n"
            "portão assim é desligado na primeira semana.",
        )
    declarados: dict[str, int] = {}
    for bruta in arquivo.read_text(encoding="utf-8").splitlines():
        linha = bruta.strip()
        if not linha or linha.startswith("#"):
            continue
        caminho, _, quantia = linha.partition("::")
        try:
            numero = int(quantia.strip())
        except ValueError:
            raise ErroDeInstrumentacao(
                "linha da dívida sem contagem",
                f"Em {LISTA_DE_HERDADOS}:\n  {linha}\n\n"
                "O molde é `<caminho> :: <quantos travessões ainda vivos>`.",
            ) from None
        declarados[caminho.strip()] = numero
    return declarados


def rodar(raiz: Path | None = None) -> Relatorio:
    relatorio = Relatorio("TRAVESSÃO EM TEXTO PÚBLICO")
    try:
        raiz = raiz or raiz_do_repo()
        vivos = censo(raiz)
        declarados = herdados(raiz)
    except ErroDeInstrumentacao as erro:
        relatorio.registrar(Resultado.de_erro("superficie", erro))
        return relatorio

    novos = {c: a for c, a in vivos.items() if c not in declarados}
    cresceu = {
        c: (len(a), declarados[c]) for c, a in vivos.items()
        if c in declarados and len(a) > declarados[c]
    }
    encolheu = {
        c: (len(vivos.get(c, [])), n) for c, n in declarados.items()
        if len(vivos.get(c, [])) < n
    }

    total_publicos = len(superficie(raiz))
    relatorio.registrar(
        Resultado(
            "superficie",
            Estado.PASS,
            f"{total_publicos} arquivos de texto público inspecionados",
        )
    )

    if novos:
        linhas = [
            "Travessão em texto que alguém vai ler, e que não está na dívida herdada.",
            "",
        ]
        for caminho, achados in sorted(novos.items()):
            linhas.append(f"  {caminho}  ({len(achados)})")
            for achado in achados[:6]:
                linhas.append(f"      linha {achado.linha}: {achado.trecho}")
            if len(achados) > 6:
                linhas.append(f"      … e mais {len(achados) - 6}")
        linhas += ["", COMO_TROCAR]
        relatorio.registrar(
            Resultado(
                "texto-novo",
                Estado.FAIL,
                f"{sum(len(a) for a in novos.values())} travessões em {len(novos)} arquivo(s)",
                "\n".join(linhas),
            )
        )
    else:
        relatorio.registrar(
            Resultado("texto-novo", Estado.PASS, "nenhum travessão fora da dívida herdada")
        )

    if cresceu:
        linhas = ["A dívida herdada CRESCEU. Ela só pode encolher.", ""]
        for caminho, (real, declarado) in sorted(cresceu.items()):
            linhas.append(f"  {caminho}: {declarado} declarados, {real} encontrados")
            for achado in vivos[caminho][:6]:
                linhas.append(f"      linha {achado.linha}: {achado.trecho}")
        linhas += ["", COMO_TROCAR]
        relatorio.registrar(
            Resultado("divida-cresceu", Estado.FAIL, f"{len(cresceu)} arquivo(s)", "\n".join(linhas))
        )
    elif encolheu:
        linhas = [
            "A dívida encolheu — é exatamente o objetivo. Falta baixar o número",
            f"em {LISTA_DE_HERDADOS}, no MESMO PR, para a queda aparecer no diff:",
            "",
        ]
        for caminho, (real, declarado) in sorted(encolheu.items()):
            linhas.append(
                f"  {caminho} :: {real}"
                + (f"      (era {declarado}; apague a linha se chegou a zero)")
            )
        relatorio.registrar(
            Resultado(
                "divida-encolheu",
                Estado.FAIL,
                f"{len(encolheu)} arquivo(s) já limpos e ainda declarados",
                "\n".join(linhas),
            )
        )
    else:
        restante = sum(declarados.values())
        relatorio.registrar(
            Resultado(
                "divida-herdada",
                Estado.PASS,
                f"{restante} travessões herdados em {len(declarados)} arquivo(s), estáveis",
            )
        )

    orfaos = [c for c in declarados if c not in {p.relative_to(raiz).as_posix() for p in superficie(raiz)}]
    if orfaos:
        relatorio.registrar(
            Resultado(
                "divida-orfa",
                Estado.FAIL,
                f"{len(orfaos)} linha(s) apontam para arquivo que saiu da superfície",
                "Estes caminhos estão na dívida mas não são mais texto público\n"
                "(sumiram, mudaram de nome, ou entraram no bastidor). Apague as\n"
                "linhas — dívida que aponta para o nada parece garantia e não é:\n\n"
                + "\n".join(f"  {c}" for c in sorted(orfaos)),
            )
        )

    return relatorio


def main(argv: list[str] | None = None) -> int:
    configurar_saida()
    parser = argparse.ArgumentParser(
        description="Nenhum texto publicado online sai com travessão.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=COMO_TROCAR,
    )
    parser.add_argument("--listar", action="store_true", help="o censo, para leitura humana")
    parser.add_argument(
        "--herdados",
        action="store_true",
        help=f"a lista pronta para colar em {LISTA_DE_HERDADOS}",
    )
    args = parser.parse_args(argv)

    if args.listar or args.herdados:
        try:
            vivos = censo(raiz_do_repo())
        except ErroDeInstrumentacao as erro:
            print(f"ERROR: {erro.resumo}\n{erro.detalhe}", file=sys.stderr)
            return 2
        if args.herdados:
            for caminho, achados in sorted(vivos.items()):
                print(f"{caminho} :: {len(achados)}")
            print(f"# TOTAL: {sum(len(a) for a in vivos.values())}")
            return 0
        for caminho, achados in sorted(vivos.items()):
            print(f"\n{caminho}  ({len(achados)})")
            for achado in achados:
                print(f"  linha {achado.linha}  {achado.forma}: {achado.trecho}")
        print(f"\nTOTAL: {sum(len(a) for a in vivos.values())} em {len(vivos)} arquivo(s)")
        return 0

    relatorio = rodar()
    print(relatorio.render())
    return relatorio.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
