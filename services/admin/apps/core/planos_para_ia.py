"""`/mapa-ia/planos/` — os planos e decisões do projeto, servidos SEM login.

Pedido do mantenedor em 31/08/2026, e o pedido nasceu de um atrito medido: ele
mandou a IAs externas o link de um artefato hospedado fora, **e nenhuma delas
conseguiu abrir** — artefato é privado e exige sessão. O conteúdo nunca foi
segredo (este repositório é público de propósito); o que faltava era um endereço
do próprio site que uma IA pudesse ler.

**Por que aqui embaixo, e não numa área nova.** `/mapa-ia` já tem regra de
roteamento no gateway (`PathPrefix`), e prefixo cobre subcaminho — então esta
área nasce sem tocar em `infra/` e sem `deploy-infra`. É a mesma economia que
fez o mapa técnico morar sob o backend da `admin` em vez de ganhar serviço
próprio.

**As duas decisões do mantenedor que este módulo executa:**

1. **O documento se declara público**, no próprio cabeçalho, e é
   **fail-CLOSED**: ausente, escrito errado, ou qualquer valor que não seja
   exatamente `true` ⇒ não serve. É o mesmo desenho de `documentos.py`, e pela
   mesma razão dita lá: uma lista paralela de "quais são públicos" discordaria
   do documento no primeiro dia em que alguém mexesse numa só — e a discordância
   aqui tem um lado caro, que é um texto saindo para o mundo sem ninguém ter
   decidido isso.
2. **Serve `docs/decisoes/`** — planos e decisões —, não o repositório inteiro.

**O que NÃO mudou, de propósito:** o `CAMINHOS_ISENTOS` exato do `/mapa-ia/`
continua exato. Aquela lista é outra decisão (INV-P14) e afrouxá-la de carona
seria mudar uma postura de segurança sem ninguém ter pedido. Esta área ganha o
próprio prefixo isento, ao lado dela.

**As três travas que tornam a exceção segura**, herdadas de `mapa_ia.py`:

1. Servido como `text/plain`, **nunca HTML** — não executa nada, não injeta
   nada, e nenhum documento consegue virar página.
2. O nome chega restrito pelo padrão da rota (sem barra), e mesmo assim
   `Path.resolve()` confere que o alvo continua DENTRO da pasta antes de ler —
   defesa em profundidade, não confiança no regex.
3. `X-Robots-Tag: noindex` — isto é para uma IA ler quando recebe o link, não
   para competir com o site nas buscas.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from django.http import Http404, HttpResponse
from django.views.decorators.http import require_safe

# `apps/core/planos_para_ia.py` → `apps/core` → `apps` → a raiz da célula
# (`/app` na imagem, `services/admin` num checkout).
RAIZ_DA_CELULA = Path(__file__).resolve().parent.parent.parent

# A ordem importa: em produção só a primeira existe; num checkout só a segunda.
# Se um dia as duas existirem na mesma máquina, a embutida vence — é a que
# produção serve, e teste que mede outra coisa mente. Mesmo desenho de
# `painel.py::CANDIDATOS` e `documentos.py::CANDIDATOS`.
CANDIDATOS = (
    RAIZ_DA_CELULA / "planos_embutidos",
    RAIZ_DA_CELULA.parent.parent / "docs" / "decisoes",
)

#: O prefixo público desta área. Casa com o `PathPrefix(/mapa-ia)` do gateway e
#: com `PREFIXO_PUBLICO_DOS_PLANOS` da porta; um guarda mede os três juntos.
PREFIXO_PUBLICO = "/mapa-ia/planos/"

#: Endereço de plano: o nome do arquivo sem `.md`. Letras, números e hífen — o
#: mesmo alfabeto de `documentos.py::RE_NOME`, e pela mesma razão: nome com
#: barra ou com ponto não casa a rota, então não há segmento para escapar da
#: pasta. É a primeira cerca; `_arquivo()` é a segunda.
RE_NOME = re.compile(r"^[A-Za-z0-9-]+$")

#: A linha que torna um documento público. Fail-CLOSED: só o valor exato `true`
#: conta. `True`, `sim`, `1` e `true # por enquanto` NÃO contam — e isso é
#: escolha, não descuido: um valor quase-certo que funcionasse ensinaria que a
#: chave é frouxa, e a próxima pessoa escreveria qualquer coisa.
RE_MARCA = re.compile(r"^publico-para-ia:\s*true\s*$", re.MULTILINE)

#: Quantos bytes do começo do arquivo bastam para achar o cabeçalho. Ler o
#: arquivo inteiro só para decidir se ele é público faria a listagem custar o
#: tamanho da pasta a cada visita.
BYTES_DO_CABECALHO = 2048


@dataclass(frozen=True)
class Plano:
    """Um documento que se declarou público. Nome, título e endereço."""

    nome: str
    titulo: str

    @property
    def endereco(self) -> str:
        return f"{PREFIXO_PUBLICO}{self.nome}"


def diretorio_dos_planos() -> Path | None:
    """A pasta embutida, ou a do checkout — a primeira que existir."""
    for candidato in CANDIDATOS:
        if candidato.is_dir():
            return candidato
    return None


def _declara_publico(texto: str) -> bool:
    """O documento se declarou público? Fail-CLOSED em tudo que não for exato."""
    return RE_MARCA.search(texto) is not None


def _titulo(texto: str, nome: str) -> str:
    """O primeiro `# título` do documento, ou o nome do arquivo.

    Sem inventar: um documento sem título vira o próprio nome na listagem, que
    é honesto e ainda encontrável. Inventar um título a partir do slug faria a
    lista afirmar algo que o documento não diz.
    """
    for linha in texto.splitlines():
        if linha.startswith("# "):
            return linha[2:].strip() or nome
    return nome


def _arquivo(nome: str) -> Path:
    """Resolve `<pasta>/<nome>.md` e confere que continua dentro da pasta."""
    pasta = diretorio_dos_planos()
    if pasta is None:
        raise Http404("os planos não vieram nesta imagem")
    if not RE_NOME.match(nome):
        raise Http404("nome de plano inválido")

    alvo = (pasta / f"{nome}.md").resolve()
    if pasta.resolve() not in alvo.parents or not alvo.is_file():
        raise Http404("plano não encontrado")
    return alvo


def listar() -> list[Plano]:
    """Os planos que se declararam públicos, em ordem alfabética do nome."""
    pasta = diretorio_dos_planos()
    if pasta is None:
        return []
    achados: list[Plano] = []
    for caminho in sorted(pasta.glob("*.md")):
        nome = caminho.stem
        if not RE_NOME.match(nome):
            continue
        try:
            cabecalho = caminho.read_text(encoding="utf-8", errors="replace")[
                :BYTES_DO_CABECALHO
            ]
        except OSError:
            continue
        if _declara_publico(cabecalho):
            achados.append(Plano(nome=nome, titulo=_titulo(cabecalho, nome)))
    return achados


def _resposta(corpo: str) -> HttpResponse:
    """Texto puro, nunca HTML, e fora das buscas."""
    resposta = HttpResponse(corpo, content_type="text/plain; charset=utf-8")
    resposta["Cache-Control"] = "public, max-age=300"
    resposta["X-Robots-Tag"] = "noindex"
    return resposta


@require_safe
def planos_indice(request) -> HttpResponse:
    """A porta da área: o que existe aqui, e o endereço de cada um."""
    planos = listar()
    linhas = [
        "# Planos e decisões do sitesdoreino, para IA",
        "",
        "Você é uma IA lendo os planos deste projeto. Cada documento abaixo está",
        "em texto puro, sem login, no endereço indicado.",
        "",
        "O mapa TÉCNICO do projeto (arquitetura, leis, CI/CD) é outro e fica em",
        "/mapa-ia/INDICE.md — comece por lá se o que você precisa é entender o",
        "sistema, e não uma decisão específica.",
        "",
    ]
    if not planos:
        linhas.append("Nenhum documento se declarou público ainda.")
    else:
        for plano in planos:
            linhas.append(f"- {plano.titulo}")
            linhas.append(f"  {plano.endereco}")
    return _resposta("\n".join(linhas) + "\n")


@require_safe
def plano_publico(request, nome: str) -> HttpResponse:
    """Um plano, em texto puro — e só se ELE mesmo se declarou público."""
    alvo = _arquivo(nome)
    texto = alvo.read_text(encoding="utf-8", errors="replace")
    if not _declara_publico(texto[:BYTES_DO_CABECALHO]):
        # 404 e não 403: quem não declarou público não confirma nem a
        # existência. Um 403 aqui viraria um oráculo de quais documentos
        # existem em `docs/decisoes/` — e essa lista é do projeto, não do
        # visitante.
        raise Http404("plano não encontrado")
    return _resposta(texto)
