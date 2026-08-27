"""O painel do dono, servido VIVO dentro da área administrativa.

O painel é `painel/painel.html` + `painel/registros/` — um site estático puro,
cuja fonte de verdade é o livro de ocorrências versionado no Git. Esta célula
**não recalcula nada**: ela serve os MESMOS bytes que o mantenedor abre no PC.
Isso não é preguiça, é a lei anti-duplicação do `CLAUDE.md` aplicada: um painel
que reimplementasse a lógica de `painel/logica.js` seria um segundo lugar onde
os fatos do projeto moram, e o dia em que os dois discordassem ninguém saberia
qual está certo. A prova é `tests/test_painel_vivo.py::test_e_o_arquivo_do_repositorio`,
que compara byte a byte.

## De onde vem a pasta

| Onde                         | Caminho                    | Quem põe lá                    |
|------------------------------|----------------------------|--------------------------------|
| Imagem de produção           | `/app/painel_embutido/`    | o `deploy-celula` copia para o contexto do build |
| Checkout do repositório      | `<repo>/painel/`           | já está lá (é a pasta viva)    |

A cópia é gitignorada de propósito (`services/admin/.gitignore`): commitá-la
criaria no repositório duas pastas com os mesmos registros — exatamente a
duplicação que este arquivo evita servindo, e não copiando.

**Se a pasta não vier, a página DIZ isso** (`painel_ausente.html`, 500) em vez
de responder 404 ou uma tela em branco. Um painel vazio que parece vazio é a
pior falha possível aqui: ele se leria como "não há nada acontecendo no
projeto", que é uma mentira, e não como "o painel quebrou".

## Por que `no-store` em tudo

O atrito que originou este trabalho foi o mantenedor vendo painel velho. Estes
arquivos somam ~300 KB, mudam a cada tarefa e são lidos por uma pessoa só: não
há nada a ganhar com cache e há tudo a perder — um `registros/*.js` guardado
pelo navegador mostra o projeto no passado, sem nenhum erro na tela.

## Por que esta rota manda o próprio CSP

O `<script>` do painel é EMBUTIDO no HTML (uma ilha de ~350 linhas), e a porta
manda `script-src 'self'` em toda resposta da célula — sob essa regra o painel
carregaria e não renderizaria nada. A saída é o hash: o CSP desta resposta
declara o `sha256` do bloco embutido, calculado do arquivo servido, a cada
resposta. Ninguém precisa lembrar de atualizar hash nenhum quando o painel
mudar, e `'unsafe-inline'` — que abriria a porta para QUALQUER script — nunca
entra. Guarda: `test_csp_nao_afrouxa_para_unsafe_inline`.
"""

import base64
import hashlib
import re
from pathlib import Path

from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_safe
from django.views.static import serve as serve_do_django

# `apps/core/painel.py` → `apps/core` → `apps` → a raiz da célula (`/app` na
# imagem, `services/admin` num checkout).
RAIZ_DA_CELULA = Path(__file__).resolve().parent.parent.parent

# A ordem importa: em produção só a primeira existe; num checkout só a segunda.
# Se um dia as duas existirem na mesma máquina (alguém rodou a cópia local), a
# embutida vence — é a que produção serve, e teste que mede outra coisa mente.
CANDIDATOS = (
    RAIZ_DA_CELULA / "painel_embutido",
    RAIZ_DA_CELULA.parent.parent / "painel",
)

# O painel é feito de HTML, JS e CSS. Nada mais sai por esta rota — a pasta
# também contém `LEIA-ME.md`, `testes/` e o gerador, que não são para a web.
EXTENSOES_SERVIDAS = frozenset({".js", ".css", ".html"})

# `<script>` sem `src=` é ilha embutida; com `src=` é arquivo, e arquivo já é
# coberto por `'self'`.
_SCRIPT_EMBUTIDO = re.compile(
    rb"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.DOTALL | re.IGNORECASE
)


def diretorio_do_painel() -> Path | None:
    """A pasta do painel, ou `None` se ela não veio nesta imagem."""
    for candidato in CANDIDATOS:
        if (candidato / "painel.html").is_file():
            return candidato
    return None


def _politica_de_seguranca(html: bytes) -> str:
    """O CSP desta página: estrito, com o hash de cada ilha embutida.

    As fontes do Google entram porque o painel as pede desde a fundação e a
    paleta da casa depende delas; `style-src` aceita embutido porque o painel
    tem uma folha `<style>` e porque a ilha escreve estilo em elemento na mão.
    Estilo embutido não executa código — a linha que importa é a de `script`,
    e essa não afrouxa.
    """
    hashes = " ".join(
        "'sha256-"
        + base64.b64encode(hashlib.sha256(m.group(1)).digest()).decode()
        + "'"
        for m in _SCRIPT_EMBUTIDO.finditer(html)
    )
    return (
        "default-src 'self'; "
        f"script-src 'self' {hashes}; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; "
        "img-src 'self' data:; object-src 'none'; base-uri 'none'; "
        "form-action 'self'; frame-ancestors 'self'"
    )


@require_safe
def painel(request):
    """A página do painel, servida com os bytes do repositório.

    A rota TERMINA EM BARRA (`/admin/painel/`) e isso é estrutural, não estilo:
    o HTML pede `manifesto.js` e `registros/*.js` por caminho RELATIVO. Sem a
    barra, o navegador resolveria `/admin/manifesto.js` e a página carregaria
    vazia. Quem redireciona `/admin/painel` para a forma com barra é o
    `CommonMiddleware` (APPEND_SLASH), que já está na cadeia.
    """
    pasta = diretorio_do_painel()
    if pasta is None:
        return render(request, "admin/painel_ausente.html", status=500)

    html = (pasta / "painel.html").read_bytes()
    resposta = HttpResponse(html, content_type="text/html; charset=utf-8")
    resposta["Content-Security-Policy"] = _politica_de_seguranca(html)
    resposta["Cache-Control"] = "no-store"
    return resposta


@require_safe
def painel_arquivo(request, path):
    """Os arquivos que a página pede: `manifesto.js`, `logica.js`, `registros/*.js`.

    Serve do diretório-FONTE, nunca de `STATIC_ROOT` — `armadilhas/083`: o
    `collectstatic` do Dockerfile falha em todo build e o `|| true` engole, de
    modo que `STATIC_ROOT` está VAZIO na imagem de produção. Servir de lá daria
    404 só em produção, com a suíte inteira verde.

    A travessia de diretório já vem barrada pelo `safe_join` do Django, que
    devolve 400 (`SuspiciousFileOperation`, logado em `django.security`).
    """
    pasta = diretorio_do_painel()
    if pasta is None:
        raise Http404("o painel não veio nesta imagem")
    if Path(path).suffix.lower() not in EXTENSOES_SERVIDAS:
        raise Http404("o painel serve apenas .js, .css e .html")

    resposta = serve_do_django(request, path, document_root=pasta)
    resposta["Cache-Control"] = "no-store"
    return resposta
