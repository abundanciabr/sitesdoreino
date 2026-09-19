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

**As duas travas que tornam a exceção segura**, herdadas de `mapa_ia.py`:

1. Servido como `text/plain`, **nunca HTML** — não executa nada, não injeta
   nada, e nenhum documento consegue virar página.
2. O nome chega restrito pelo padrão da rota (sem barra), e mesmo assim
   `Path.resolve()` confere que o alvo continua DENTRO da pasta antes de ler —
   defesa em profundidade, não confiança no regex.

**O `X-Robots-Tag: noindex` SAIU em 31/08/2026, e a razão é medição.** Ele
estava aqui copiado de `mapa_ia.py`, com a intenção de "não competir com o site
nas buscas" — e derrotava o único propósito da área. No dia em que ela subiu, o
mantenedor mandou o endereço para o Gemini e ouviu *"não consegui acessar o
conteúdo"*. A investigação descartou, uma a uma, as causas plausíveis: o
servidor responde **200 a todo User-Agent**, inclusive `GPTBot`, `GoogleOther` e
`Google-Extended`; não há `robots.txt` bloqueando (é 404, que significa liberado);
não há IPv6 quebrado (o domínio não tem AAAA); e a cadeia TLS verifica completa
(`Verify return code: 0`).

Sobrou UMA diferença entre este endereço e o `raw.githubusercontent.com` do mesmo
arquivo, que as IAs leem sem reclamar: o `noindex` — e a extensão. `noindex` é
uma instrução que diz *"não use este conteúdo"*, e pedir que uma IA leia uma
página marcada assim é pedir que ela desobedeça.

**A troca, dita por inteiro:** sem o `noindex`, estas páginas podem passar a
aparecer numa busca do Google por "Meshcraft". São documentos de projeto num
repositório que já é público — mas é visibilidade nova, e o mantenedor foi
avisado e pode mandar reverter.

**E o endereço passou a aceitar `.md` no fim**, opcional. Não é enfeite: é a
outra diferença medida contra o `raw` do GitHub, e custa uma linha na rota. Os
dois endereços servem o mesmo arquivo.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import markdown
from django.conf import settings
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import render
from django.template.loader import get_template
from django.urls import reverse
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


@dataclass(frozen=True)
class PlanoLocal:
    """Um `.md` local do plano mestre, servido atras da porta da admin."""

    nome: str
    arquivo: str
    titulo: str
    resumo: str
    grupo: str
    ordem: int
    endereco: str


GRUPOS_LOCAIS = (
    (0, 9, "Núcleo"),
    (10, 19, "Desenho"),
    (20, 29, "Operação"),
    (30, 39, "Acompanhamento"),
)

VARIAVEL_DA_PASTA_LOCAL = "ADMIN_PLANOS_DIR"


def estado_da_continuidade() -> dict:
    """O estado que o motor autonomo deixa para a tela do plano mestre."""
    pasta = diretorio_local_dos_planos()
    ligado = _vigilia_ligada()
    vazio = {
        "existe": False,
        "vigilia_ligada": ligado,
        "mensagem": (
            "Nenhuma sessão de continuidade rodou ainda. "
            "Para ligar, dê duplo clique em administracao-local\\ligar-a-vigilia.cmd."
        ),
    }
    if pasta is None or not pasta.is_dir():
        vazio["mensagem"] = "A pasta do plano mestre não está disponível."
        return vazio
    arquivo = pasta / "estado-da-continuidade.json"
    if not arquivo.is_file():
        return vazio
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "existe": True,
            "vigilia_ligada": ligado,
            "erro": (
                "O estado da continuidade não pôde ser lido. "
                "Corrija o JSON em estado-da-continuidade.json."
            ),
        }
    if not isinstance(dados, dict):
        return {
            "existe": True,
            "vigilia_ligada": ligado,
            "erro": (
                "O estado da continuidade não é um objeto JSON. "
                "Corrija estado-da-continuidade.json."
            ),
        }
    bloqueios = dados.get("bloqueios")
    if not isinstance(bloqueios, list):
        bloqueios = []
    return {
        "existe": True,
        "vigilia_ligada": ligado,
        "ultima_sessao": dados.get("ultima_sessao") or "",
        "sessoes_rodadas": int(dados.get("sessoes_rodadas") or 0),
        "tarefa_corrente": dados.get("tarefa_corrente") or "sem tarefa em curso",
        "bloqueios": len(bloqueios),
        "ultimo_handoff": dados.get("ultimo_handoff") or "",
    }


def _vigilia_ligada() -> bool:
    comando = os.environ.get("ADMIN_VIGILIA_LIGADA")
    if comando is not None:
        return comando.strip() == "1"
    try:
        resultado = subprocess.run(
            ["schtasks", "/Query", "/TN", "Triade - vigilia do painel local"],
            text=True,
            capture_output=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return resultado.returncode == 0


def diretorio_dos_planos() -> Path | None:
    """A pasta embutida, ou a do checkout — a primeira que existir."""
    for candidato in CANDIDATOS:
        if candidato.is_dir():
            return candidato
    return None


def diretorio_local_dos_planos() -> Path | None:
    """A pasta local do plano mestre, vinda do ambiente."""
    cru = (os.environ.get(VARIAVEL_DA_PASTA_LOCAL) or "").strip()
    return Path(cru) if cru else None


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


def _resumo(texto: str) -> str:
    """A primeira linha de texto que não seja título nem metadado."""
    for linha in texto.splitlines():
        limpa = linha.strip()
        if not limpa or limpa.startswith(("#", "---")) or ":" in limpa[:32]:
            continue
        return limpa.strip("*` ")
    return ""


def _grupo(numero: int) -> str:
    for inicio, fim, nome in GRUPOS_LOCAIS:
        if inicio <= numero <= fim:
            return nome
    return "Outros"


def _ordem_do_nome(nome: str) -> int:
    try:
        return int(nome.split("-", 1)[0])
    except ValueError:
        return 10_000


def _arquivo(nome: str) -> Path:
    """Resolve `<pasta>/<nome>.md` e confere que continua dentro da pasta."""
    pasta = diretorio_dos_planos()
    if pasta is None:
        raise Http404("os planos não vieram nesta imagem")
    # `.md` no fim e opcional: e a forma do `raw.githubusercontent.com`, que
    # as IAs leem sem reclamar, e igualar as duas custou esta linha.
    if nome.endswith(".md"):
        nome = nome[:-3]
    if not RE_NOME.match(nome):
        raise Http404("nome de plano inválido")

    alvo = (pasta / f"{nome}.md").resolve()
    if pasta.resolve() not in alvo.parents or not alvo.is_file():
        raise Http404("plano não encontrado")
    return alvo


def _arquivo_local(nome: str) -> Path:
    """Resolve `<pasta>/<nome>.md` para a leitura local do painel."""
    pasta = diretorio_local_dos_planos()
    if pasta is None or not pasta.is_dir():
        raise Http404("plano não encontrado")
    if nome.endswith(".md"):
        nome = nome[:-3]
    if not RE_NOME.match(nome):
        raise Http404("plano não encontrado")

    raiz = pasta.resolve()
    alvo = (raiz / f"{nome}.md").resolve()
    if raiz not in alvo.parents or not alvo.is_file():
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


def listar_locais() -> tuple[list[PlanoLocal], Path | None, str | None]:
    """Os `.md` locais do plano mestre, sem lista de nomes digitada."""
    pasta = diretorio_local_dos_planos()
    if pasta is None:
        return [], None, f"Defina {VARIAVEL_DA_PASTA_LOCAL} no lançador local."
    if not pasta.is_dir():
        return [], pasta, "Crie a pasta ou ajuste o caminho no lançador local."

    achados: list[PlanoLocal] = []
    for caminho in sorted(
        pasta.glob("*.md"), key=lambda p: (_ordem_do_nome(p.stem), p.name)
    ):
        if not RE_NOME.match(caminho.stem):
            continue
        try:
            texto = caminho.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        ordem = _ordem_do_nome(caminho.stem)
        achados.append(
            PlanoLocal(
                nome=caminho.stem,
                arquivo=caminho.name,
                titulo=_titulo(texto, caminho.stem),
                resumo=_resumo(texto),
                grupo=_grupo(ordem),
                ordem=ordem,
                endereco=reverse("plano_mestre_documento", args=[caminho.name]),
            )
        )
    if not achados:
        return [], pasta, "Coloque arquivos .md nessa pasta e atualize a página."
    return achados, pasta, None


def _html_do_markdown(texto: str) -> str:
    """Markdown local em HTML, com tabelas legíveis."""
    return markdown.markdown(
        texto,
        extensions=["tables", "fenced_code"],
        output_format="html",
    )


def mtime_local() -> int:
    """Carimbo dos documentos locais e do template do painel."""
    assinatura = hashlib.sha256()
    pasta = diretorio_local_dos_planos()
    if pasta is not None and pasta.is_dir():
        for caminho in sorted(pasta.glob("*.md")):
            if not caminho.is_file():
                continue
            estado = caminho.stat()
            assinatura.update(caminho.name.encode("utf-8"))
            assinatura.update(f"{estado.st_mtime_ns}:{estado.st_size}".encode())
    try:
        template = get_template("admin/plano_mestre.html")
        origem = getattr(template, "origin", None)
        nome = getattr(origem, "name", "")
        if nome:
            estado = Path(nome).stat()
            assinatura.update(nome.encode("utf-8"))
            assinatura.update(f"{estado.st_mtime_ns}:{estado.st_size}".encode())
    except OSError:
        pass
    return int.from_bytes(assinatura.digest()[:8], "big")


def _csp_com_script(corpo: bytes) -> str:
    scripts = re.findall(
        rb"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>",
        corpo,
        flags=re.DOTALL | re.IGNORECASE,
    )
    hashes = " ".join(
        "'sha256-" + base64.b64encode(hashlib.sha256(script).digest()).decode() + "'"
        for script in scripts
    )
    return (
        f"default-src 'self'; script-src 'self' {hashes}; "
        "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
        "object-src 'none'; base-uri 'none'; form-action 'self'; "
        "frame-ancestors 'self'; connect-src 'self'"
    )


def _resposta(corpo: str) -> HttpResponse:
    """Texto puro, nunca HTML.

    SEM `X-Robots-Tag: noindex`, de propósito e por medição — ver o cabeçalho
    deste arquivo. O guarda que impede o header de voltar sem conversa é
    `tests/test_planos_para_ia.py::test_a_area_nao_pede_para_ser_ignorada`.
    """
    resposta = HttpResponse(corpo, content_type="text/plain; charset=utf-8")
    resposta["Cache-Control"] = "public, max-age=300"
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


@require_safe
def plano_mestre(request) -> HttpResponse:
    """Painel local do plano mestre, alimentado pela pasta de `.md`."""
    planos, pasta, recado = listar_locais()
    por_grupo: dict[str, list[PlanoLocal]] = {}
    for plano in planos:
        por_grupo.setdefault(plano.grupo, []).append(plano)
    resposta = render(
        request,
        "admin/plano_mestre.html",
        {
            "admin": request.admin,
            "grupos": [
                {"nome": nome, "planos": itens} for nome, itens in por_grupo.items()
            ],
            "pasta": str(pasta) if pasta is not None else "",
            "recado": recado,
            "continuidade": estado_da_continuidade(),
            "mtime": mtime_local(),
            "acompanhar_mudancas": settings.DEBUG,
        },
    )
    resposta["Content-Security-Policy"] = _csp_com_script(resposta.content)
    return resposta


@require_safe
def plano_mestre_documento(request, nome: str) -> JsonResponse:
    """Um documento local do plano mestre, em HTML para o dialog."""
    alvo = _arquivo_local(nome)
    texto = alvo.read_text(encoding="utf-8", errors="replace")
    return JsonResponse(
        {
            "titulo": _titulo(texto, alvo.stem),
            "arquivo": alvo.name,
            "html": _html_do_markdown(texto),
        }
    )


@require_safe
def plano_mestre_mtime(request) -> JsonResponse:
    """Relógio de recarga local. Em produção, não existe."""
    if not settings.DEBUG:
        raise Http404("plano não encontrado")
    return JsonResponse({"mtime": mtime_local()})
