"""O VERIFICADOR DO PAINEL — quem confere não é quem constrói.

O PROBLEMA QUE ISTO FECHA
-------------------------
`painel/gerar_manifesto.js` escreve os artefatos do painel E confere se estão em
dia (`--conferir`). Os dois lados da comparação saem do mesmo programa, lendo a
pasta do mesmo jeito. Isso pega arquivo editado à mão e arquivo desatualizado —
mas é **cego para o próprio gerador**.

Três consultorias independentes apontaram exatamente isto em 27/08/2026:

    "Se o mesmo programa produz os dois lados da comparação, quem verifica o
     programa? Um bug que ignore todos os arquivos terminados em -x.js gera
     manifesto = 87 e livro = 87. Painel: tudo certo. CI: tudo certo. Mas três
     ocorrências sumiram."  (GPT, §2.4 — *correlated failure*)

    "A referência de contagem precisa vir de onde o gerador não passou. A versão
     barata e honesta: comparar contra `git ls-files registros/` — o índice do
     Git é uma fonte de verdade independente da varredura do gerador. E compare
     CONJUNTOS DE NOMES, não comprimentos."  (Opus, §2d)

    "Cardinalidade não é integridade: manifesto A B C D, livro A B C C. Contagem
     4 == 4. Painel verde. Mas D desapareceu."  (GPT, §2.3)

O QUE FAZ DESTE VERIFICADOR INDEPENDENTE
----------------------------------------
1. **Outra linguagem.** O gerador é Node; este é Python. Um erro de raciocínio
   não se copia entre os dois por acidente.
2. **Outra fonte de verdade.** A lista de registros vem de `git ls-files`, não de
   um `readdir` da pasta. Arquivo não rastreado, arquivo esquecido no disco e
   arquivo apagado sem commit aparecem como divergência — e são divergência
   mesmo, já que é o índice que viaja no PR e entra na imagem do deploy.
3. **Nenhum código compartilhado com o gerador.** Não importa `logica.js` nem
   `gerar_manifesto.js`. O trecho de Node que lê os registros está escrito aqui
   dentro e não faz nada além de executar cada arquivo e despejar JSON.
4. **Compara CONJUNTOS, nunca contagens.** Faltando, sobrando e repetido são três
   achados diferentes, e cada um é nomeado.

Deliberadamente burro: quanto mais simples este arquivo, menos ele tem como
mentir junto com o gerador.

ONDE ELE MEDE
-------------
Na cópia do repositório onde ELE está — `raiz_do_repo()` resolve a partir da
localização deste arquivo, do mesmo jeito que `ci/mergear.py`. Chamar
`../outra-arvore/ci/verificar_painel.py` mede a outra árvore
(`armadilhas/147`). Rode `python ci/verificar_painel.py` de dentro do checkout
que você quer conferir.

Dialeto (RETROSPECTIVA-FASE-D §1): exit 0 PASS · 1 FAIL · 2 ERROR.
ERROR nunca vira PASS: "não consegui medir" é resultado, não silêncio.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _nucleo import (  # noqa: E402
    ErroDeInstrumentacao,
    configurar_saida,
    executar,
    raiz_do_repo,
)

# O nome de um registro É o identificador dele, e carrega o mês a que pertence.
NOME = re.compile(r"^(\d{4})(\d{2})\d{2}-\d{3}-[a-z0-9-]+$")

# Os artefatos que o desenho de 27/08/2026 aposentou. Se voltarem a existir, o
# painel voltou a carregar o livro inteiro ao abrir — e ninguém notaria, porque
# a página continuaria funcionando.
APOSENTADOS = ("manifesto.js", "livro.js")

# Lê cada registro executando-o, exatamente como o navegador faria, e despeja
# JSON. É o mínimo que dá para fazer sem reimplementar um parser de JavaScript —
# e não toca em nenhuma linha do gerador nem da lógica do painel. A pasta vem
# por variável de ambiente: com `node -e`, `process.argv` não carrega os
# argumentos do script no índice que se espera.
LEITOR_JS = """
var fs = require("fs"), path = require("path"), vm = require("vm");
var pasta = process.env.PASTA_DOS_REGISTROS, saida = {};
fs.readdirSync(pasta).filter(function (n) { return n.slice(-3) === ".js"; }).forEach(function (n) {
  var sandbox = { window: {} };
  try { vm.runInNewContext(fs.readFileSync(path.join(pasta, n), "utf8"), sandbox, { timeout: 2000 }); }
  catch (e) { saida[n] = { __erro: "nao executou: " + e.message }; return; }
  var lista = sandbox.window.REGISTROS || [];
  if (lista.length !== 1) { saida[n] = { __erro: "empurrou " + lista.length + " registros" }; return; }
  saida[n] = lista[0];
});
process.stdout.write(JSON.stringify(saida));
"""


class Painel:
    """Os caminhos, resolvidos uma vez a partir da raiz provada."""

    def __init__(self, raiz: Path) -> None:
        self.raiz = raiz
        self.pasta = raiz / "painel"
        self.registros = self.pasta / "registros"
        self.pagina = self.pasta / "painel.html"


# ------------------------------------------------------------------ as fontes


def ids_no_git(p: Painel) -> set[str]:
    """Os registros que o Git conhece — a fonte que o gerador não visitou."""
    exec_ = executar(
        ["git", "ls-files", "--", "painel/registros/*.js"],
        cwd=p.raiz,
        descricao="listar os registros pelo índice do Git",
        exigir_stdout=True,
    )
    if exec_.exit_code != 0:
        raise ErroDeInstrumentacao(
            "git ls-files não conseguiu listar os registros",
            f"exit {exec_.exit_code}\n{exec_.stderr.strip()}",
        )
    nomes = [ln.strip() for ln in exec_.stdout.splitlines() if ln.strip()]
    if not nomes:
        raise ErroDeInstrumentacao(
            "o índice do Git não tem nenhum registro em painel/registros/",
            "Isto NÃO é um livro vazio válido — é sinal de repositório errado, "
            "de pasta movida, ou de registros nunca adicionados ao Git.",
        )
    return {Path(n).stem for n in nomes}


def gerados_no_indice(p: Painel) -> list[str]:
    """Os artefatos GERADOS que voltaram ao índice do Git — devem ser zero.

    Desde 28/08/2026 (Onda 3 do PLANO-MESTRE-ROBOS-SEM-COLISAO.md) o painel tem
    **escritor único**: `painel/registros/` é a fonte multiescritor, e
    `painel.html` + `livro-AAAAMM.js` são MATERIALIZADOS pela integração — na
    muralha, a cada PR, e no deploy, antes de a imagem da célula `admin` ser
    construída. Eles não viajam mais no Git.

    O motivo é medido, não estético: enquanto viajavam, todo PR que registrasse
    qualquer coisa reescrevia os dois arquivos inteiros, e dois robôs no mesmo
    dia colidiam sem ter escrito uma linha em comum. Um PR de 4 arquivos levou
    OITO tentativas para entrar (`armadilhas/156`).

    Quem devolvesse um deles ao índice reabriria a colisão em silêncio — e
    silêncio é o que este arquivo inteiro existe para não permitir. O
    `.gitignore` já os mantém fora e `.githooks/pre-commit` avisa aqui na
    máquina; esta função é o degrau que vale para todo mundo, porque roda na
    muralha de todo PR.
    """
    exec_ = executar(
        ["git", "ls-files", "--", "painel/painel.html", "painel/livro-*.js"],
        cwd=p.raiz,
        descricao="conferir se algum artefato gerado voltou ao índice do Git",
    )
    if exec_.exit_code != 0:
        raise ErroDeInstrumentacao(
            "git ls-files não conseguiu inspecionar os artefatos gerados",
            f"exit {exec_.exit_code}" + chr(10) + exec_.stderr.strip(),
        )
    return [ln.strip() for ln in exec_.stdout.splitlines() if ln.strip()]


def registros_da_fonte(p: Painel) -> dict[str, dict]:
    """Cada registro, executado a partir do arquivo-fonte. Chave = id."""
    exec_ = executar(
        ["node", "-e", LEITOR_JS],
        cwd=p.raiz,
        descricao="ler os registros executando cada arquivo-fonte",
        exigir_stdout=True,
        env_extra={"PASTA_DOS_REGISTROS": str(p.registros)},
    )
    if exec_.exit_code != 0:
        raise ErroDeInstrumentacao(
            "o leitor de registros não terminou",
            f"exit {exec_.exit_code}\n{exec_.stderr.strip()[:600]}",
        )
    try:
        cru = json.loads(exec_.stdout)
    except ValueError as erro:
        raise ErroDeInstrumentacao(
            "o leitor de registros não devolveu JSON",
            f"{erro}\nSaída (início): {exec_.stdout[:300]}",
        ) from erro
    return {Path(nome).stem: obj for nome, obj in cru.items()}


# --------------------------------------------------------------- os artefatos


def _json_embutido(texto: str, padrao: str, onde: str) -> object:
    """Extrai um `JSON.parse("...")` do arquivo gerado, sem executar nada.

    O literal é uma string JS produzida por `JSON.stringify`, que por construção
    também é um literal JSON válido. Duas passadas de `json.loads` bastam: a
    primeira desfaz o literal, a segunda lê o conteúdo.
    """
    achado = re.search(padrao, texto, re.S)
    if not achado:
        raise ErroDeInstrumentacao(
            f"{onde} não traz o bloco esperado",
            "Ou o arquivo não foi gerado, ou foi editado à mão, ou o formato mudou "
            "sem este verificador saber. Rode: node painel/gerar_manifesto.js",
        )
    try:
        return json.loads(json.loads(achado.group(1)))
    except ValueError as erro:
        raise ErroDeInstrumentacao(f"{onde} não decodifica", str(erro)) from erro


def declaracao_da_pagina(p: Painel) -> tuple[int, list[dict]]:
    """O que `painel.html` PROMETE: o total do livro e os meses que serve.

    Lido por regex, de propósito: executar a página exigiria um navegador, e o
    que importa aqui é o que ela declara — não o que ela faz.
    """
    if not p.pagina.is_file():
        raise ErroDeInstrumentacao(
            "painel/painel.html não existe",
            "Rode: node painel/gerar_manifesto.js",
        )
    texto = p.pagina.read_text(encoding="utf-8")
    achado = re.search(
        r"livro:\s*\{\s*total:\s*(\d+),\s*meses:\s*(\[.*?\])\s*\}", texto, re.S
    )
    if not achado:
        raise ErroDeInstrumentacao(
            "painel.html não declara `livro: { total, meses }`",
            "Ou não foi gerado, ou o formato mudou sem este verificador saber.",
        )
    try:
        meses = json.loads(achado.group(2))
    except ValueError as erro:
        raise ErroDeInstrumentacao(
            "a declaração de meses em painel.html não é JSON", str(erro)
        ) from erro
    return int(achado.group(1)), meses


def registros_do_mes(caminho: Path) -> list[dict]:
    """Os registros dentro de um `livro-AAAAMM.js`, sem executar JavaScript."""
    lista = _json_embutido(
        caminho.read_text(encoding="utf-8"),
        r"registros:\s*JSON\.parse\((\".*\")\)",
        caminho.name,
    )
    if not isinstance(lista, list):
        raise ErroDeInstrumentacao(
            f"{caminho.name} não traz uma lista de registros", ""
        )
    return lista


def ids_do_resumo(p: Painel) -> set[str]:
    """Os ids que a página embute no resumo (o que a capa e o mapa desenham)."""
    resumo = _json_embutido(
        p.pagina.read_text(encoding="utf-8"),
        r"resumo:\s*JSON\.parse\((\".*?\")\)\s*\n\};",
        "o resumo de painel.html",
    )
    if not isinstance(resumo, dict):
        raise ErroDeInstrumentacao("o resumo de painel.html não é um objeto", "")
    return {
        r["arquivo"]
        for r in resumo.get("registros", [])
        if isinstance(r, dict) and r.get("arquivo")
    }


def carimbo_de(texto: str) -> str | None:
    """A impressão digital da geração que produziu o arquivo.

    A página e cada arquivo de mês carregam a mesma. É ela que permite ao painel
    distinguir, na tela do dono, "o arquivo não chegou" de "os arquivos são de
    gerações diferentes" — o caso do OneDrive sincronizando pela metade. Um
    carimbo divergente entre artefatos do MESMO build é bug do gerador, e a tela
    do dono não pode ser o primeiro lugar a descobrir.
    """
    achado = re.search(r'carimbo: "([a-f0-9]+)"', texto)
    return achado.group(1) if achado else None


def canonico(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


# -------------------------------------------------------------------- o exame


def conferir(p: Painel) -> list[str]:
    """Devolve a lista de problemas. Vazia = PASS."""
    problemas: list[str] = []

    no_git = ids_no_git(p)
    fonte = registros_da_fonte(p)

    # O ESCRITOR ÚNICO: gerado não mora no Git. Vem antes de tudo porque é a
    # única divergência que não se conserta regenerando — conserta-se tirando o
    # arquivo do índice.
    for caminho in gerados_no_indice(p):
        problemas.append(
            f"{caminho}: artefato GERADO de volta no índice do Git. Desde a Onda 3 "
            "quem materializa é a integração — commitá-lo devolve a colisão diária "
            "entre robôs. Tire com: git rm --cached " + caminho
        )

    # Registro que o Git conhece e que não executa é problema de CONTEÚDO, não de
    # instrumento: ele viajaria no PR e não existiria na tela.
    for ident in sorted(no_git):
        obj = fonte.get(ident)
        if obj is None:
            problemas.append(
                f"{ident}: está no índice do Git e não foi encontrado no disco"
            )
        elif "__erro" in obj:
            problemas.append(f"{ident}: {obj['__erro']}")

    total_declarado, meses_declarados = declaracao_da_pagina(p)

    for nome in APOSENTADOS:
        if (p.pasta / nome).exists():
            problemas.append(
                f"{nome} voltou a existir — este arquivo foi aposentado em 27/08/2026, "
                "e ele de volta significa o livro inteiro sendo carregado ao abrir"
            )

    # Meses declarados x meses em disco: nenhum prometido e ausente, nenhum
    # servido e não prometido (o fantasma que sobrevive a uma geração antiga).
    em_disco = {c.name for c in p.pasta.glob("livro-*.js")}
    prometidos = {m["arquivo"] for m in meses_declarados}
    for nome in sorted(prometidos - em_disco):
        problemas.append(
            f"{nome}: painel.html promete servir este mês e o arquivo não existe"
        )
    for nome in sorted(em_disco - prometidos):
        problemas.append(
            f"{nome}: está no disco e nenhum mês o reivindica (sobrou de uma geração antiga)"
        )

    carimbo_da_pagina = carimbo_de(p.pagina.read_text(encoding="utf-8"))
    if not carimbo_da_pagina:
        problemas.append(
            "painel.html não carrega carimbo de geração — sem ele a página não "
            "consegue distinguir arquivo faltando de arquivo de outra geração"
        )

    nos_meses: dict[str, int] = {}
    conteudo: dict[str, dict] = {}
    for mes in meses_declarados:
        caminho = p.pasta / mes["arquivo"]
        if not caminho.is_file():
            continue
        carimbo_do_mes = carimbo_de(caminho.read_text(encoding="utf-8"))
        if carimbo_do_mes != carimbo_da_pagina:
            problemas.append(
                f"{mes['arquivo']}: carimbo {carimbo_do_mes} contra {carimbo_da_pagina} "
                "em painel.html — os dois saíram do mesmo build e têm de bater"
            )
        lista = registros_do_mes(caminho)
        if len(lista) != mes["count"]:
            problemas.append(
                f"{mes['arquivo']}: painel.html declara {mes['count']} registros "
                f"e o arquivo traz {len(lista)}"
            )
        for obj in lista:
            ident = obj.get("arquivo") if isinstance(obj, dict) else None
            if not ident:
                problemas.append(f"{mes['arquivo']}: um registro sem campo 'arquivo'")
                continue
            nos_meses[ident] = nos_meses.get(ident, 0) + 1
            conteudo[ident] = obj
            # O mês de um registro é o do próprio nome dele. Trocar de gaveta
            # quebraria a promessa de que mês fechado nunca mais é reescrito.
            casa = NOME.match(ident)
            if casa and f"{casa.group(1)}-{casa.group(2)}" != mes["mes"]:
                problemas.append(
                    f"{ident}: está no arquivo de {mes['mes']}, mas o nome dele "
                    f"diz {casa.group(1)}-{casa.group(2)}"
                )

    # ---- A COMPARAÇÃO QUE QUEBRA A TAUTOLOGIA: conjuntos, nunca contagens ----
    nos_artefatos = set(nos_meses)
    for ident in sorted(no_git - nos_artefatos):
        problemas.append(
            f"{ident}: está no livro e NÃO está em nenhum arquivo de mês — sumiu da tela"
        )
    for ident in sorted(nos_artefatos - no_git):
        problemas.append(
            f"{ident}: está num arquivo de mês e o Git NÃO o conhece "
            "(registro nunca adicionado, ou apagado sem commit)"
        )
    for ident in sorted(i for i, n in nos_meses.items() if n > 1):
        problemas.append(
            f"{ident}: aparece {nos_meses[ident]} vezes nos arquivos de mês — "
            "id repetido passa despercebido por qualquer contagem"
        )

    if total_declarado != len(no_git):
        problemas.append(
            f"painel.html declara um livro de {total_declarado} registros "
            f"e o Git conhece {len(no_git)}"
        )

    # ---- Conteúdo: o id certo com o texto errado também é mentira ----
    for ident in sorted(no_git & nos_artefatos):
        original = fonte.get(ident)
        if not original or "__erro" in original:
            continue
        if canonico(original) != canonico(conteudo[ident]):
            problemas.append(
                f"{ident}: o conteúdo empacotado difere do arquivo-fonte "
                "(o id está certo e o registro foi alterado no caminho)"
            )

    # ---- O resumo não pode inventar ----
    for ident in sorted(ids_do_resumo(p) - no_git):
        problemas.append(
            f"{ident}: aparece no resumo da página e não existe em painel/registros/"
        )

    return problemas


def main() -> int:
    configurar_saida()
    try:
        raiz = raiz_do_repo(Path(__file__).resolve().parent)
        painel = Painel(raiz)
        print("VERIFICADOR DO PAINEL — conferindo de fora do gerador")
        print(f"  raiz medida: {raiz}")
        problemas = conferir(painel)
    except ErroDeInstrumentacao as erro:
        print(f"\n❌ ERROR verificar_painel: {erro.resumo}")
        if erro.detalhe:
            print("\n".join(f"   {ln}" for ln in erro.detalhe.splitlines()))
        print("   O painel NÃO foi inspecionado. Este resultado NÃO é um OK.")
        return 2

    if problemas:
        print(
            f"\n❌ FAIL — {len(problemas)} divergência(s) entre o livro e o painel gerado:"
        )
        for item in problemas[:40]:
            print(f"   - {item}")
        if len(problemas) > 40:
            print(f"   … e mais {len(problemas) - 40}.")
        print(
            "\n   Conserte a FONTE (painel/registros/) e rode: node painel/gerar_manifesto.js"
        )
        print("   Nunca edite um arquivo gerado à mão para calar este verificador.")
        print("")
        print(
            "   Acabou de escrever um registro novo? Ele precisa estar no ÍNDICE do Git"
        )
        print(
            "   para contar: git add painel/registros/ — registro que o Git não conhece"
        )
        print("   não viaja no PR e não entra na imagem do deploy. Logo, não existe.")
        return 1

    total, meses = declaracao_da_pagina(painel)
    print(
        f"\n✅ PASS — os {total} registros do índice do Git, em {len(meses)} mês(es), "
        "estão nos artefatos"
    )
    print(
        "   com o mesmo id e o mesmo conteúdo. Conferido sem reusar uma linha do gerador."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
