"""`/mapa-ia/` — o mapa técnico do projeto, servido SEM login. Pedido do
mantenedor em 28/08/2026: um link único que ele manda a qualquer IA de fora
para ela conhecer o projeto inteiro, sem precisar dar acesso a nada.

A fonte é `painel/ia/` (mesma pasta descrita em `painel/ia/INDICE.md`), já
embutida na imagem desta célula pelo mesmo passo que embute o painel do dono
(`deploy-celula.yml`, "Embutir o painel do dono" — copia `painel/` inteira,
`ia/` vem junto de graça). Este arquivo NÃO reimplementa nada de
`painel/ia/`: serve os MESMOS bytes do repositório, mesma lei anti-duplicação
de `painel.py`.

**Isto é a ÚNICA fresta pública desta célula além de `/healthz`** — ver
[INV-P14] em `INVARIANTES.md` e `CAMINHOS_ISENTOS` em `porta.py`. Dois
cuidados que blindam essa exceção:

1. Servido como `text/plain`, nunca HTML — não executa nada, não injeta nada.
2. A lista de arquivos servíveis é a intersecção de dois lugares que têm de
   concordar: o disco (o que existe de fato em `painel/ia/*.md`) e
   `CAMINHOS_ISENTOS` (o que a porta decidiu deixar passar sem sessão). Um
   arquivo novo em `painel/ia/` não fica público sozinho — alguém tem de
   decidir isso também em `porta.py`, de propósito (é o mesmo espírito do
   comentário de `CAMINHOS_ISENTOS`: "rota nova não escapa em silêncio").
"""

from __future__ import annotations

from pathlib import Path

from django.http import Http404, HttpResponse
from django.views.decorators.http import require_safe

from .painel import diretorio_do_painel

NOME_DO_INDICE = "INDICE.md"


def diretorio_do_mapa_ia() -> Path | None:
    """`painel/ia/`, dentro da mesma pasta (embutida ou de checkout) do painel."""
    pasta_do_painel = diretorio_do_painel()
    if pasta_do_painel is None:
        return None
    candidato = pasta_do_painel / "ia"
    return candidato if candidato.is_dir() else None


def _servir(nome: str) -> HttpResponse:
    """Lê `painel/ia/<nome>` e devolve como texto puro, ou 404.

    `nome` já chega restrito pelo padrão da rota (só letras, números, `.`,
    `-`, `_` — sem `/`), então não há segmento de caminho para escapar da
    pasta. Mesmo assim resolve por `Path.resolve()` e confere que o
    resultado continua DENTRO da pasta do mapa antes de ler — defesa em
    profundidade, não confiança cega no padrão da URL.
    """
    pasta = diretorio_do_mapa_ia()
    if pasta is None:
        raise Http404("o mapa para IA não veio nesta imagem")
    if not nome.endswith(".md"):
        raise Http404("o mapa para IA só serve documentos .md")

    alvo = (pasta / nome).resolve()
    if pasta.resolve() not in alvo.parents or not alvo.is_file():
        raise Http404("documento não encontrado no mapa para IA")

    resposta = HttpResponse(alvo.read_bytes(), content_type="text/plain; charset=utf-8")
    resposta["Cache-Control"] = "public, max-age=300"
    # Isto é para IA ler, não para aparecer numa busca de humano.
    resposta["X-Robots-Tag"] = "noindex"
    return resposta


@require_safe
def mapa_ia_indice(request):
    """`/mapa-ia/` — a porta de entrada, o índice do mapa."""
    return _servir(NOME_DO_INDICE)


@require_safe
def mapa_ia_arquivo(request, nome):
    """`/mapa-ia/<nome>.md` — um documento do mapa, pelo nome exato."""
    return _servir(nome)
