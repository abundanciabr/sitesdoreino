"""O painel do dono, servido VIVO dentro da área administrativa.

O painel é `painel/painel.html` + `painel/registros/` — um site estático puro,
cuja fonte de verdade é o livro de ocorrências versionado no Git. Esta célula
**não recalcula nada**: preserva os bytes do livro e acrescenta a identificação
da versão selecionada, sem reimplementar suas contas.
Isso não é preguiça, é a lei anti-duplicação do `CLAUDE.md` aplicada: um painel
que reimplementasse a lógica de `painel/logica.js` seria um segundo lugar onde
os fatos do projeto moram, e o dia em que os dois discordassem ninguém saberia
qual está certo. A prova é `tests/test_painel_vivo.py::test_e_o_arquivo_do_repositorio`,
que compara byte a byte após retirar somente a identificação da publicação.

## De onde vem a pasta

| Onde                         | Caminho                    | Quem põe lá                    |
|------------------------------|----------------------------|--------------------------------|
| Produção                     | `/opt/plataforma/admin-dados/painel_ativo` | o publicador de dados valida e troca o ponteiro |
| Checkout do repositório      | `<repo>/painel/`           | já está lá (é a pasta viva)    |

O snapshot local é gitignorado de propósito (`services/admin/.gitignore`):
commitá-lo criaria no repositório duas pastas com os mesmos registros, a
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
from django.template.loader import render_to_string
from django.views.decorators.http import require_safe
from django.views.static import serve as serve_do_django

from .admin_dados import PASTA_DADOS_PAINEL_ATIVO, selecionar_dados

# `apps/core/painel.py` → `apps/core` → `apps` → a raiz da célula (`/app` na
# imagem, `services/admin` num checkout).
RAIZ_DA_CELULA = Path(__file__).resolve().parent.parent.parent

# A publicação vem primeiro. A cópia da imagem e o checkout são alternativas
# identificadas na resposta; escolher uma delas não afirma que está atualizada.
CANDIDATOS = (
    PASTA_DADOS_PAINEL_ATIVO,
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


def dados_do_painel():
    return selecionar_dados(
        CANDIDATOS, tipo="painel", arquivos_obrigatorios=("painel.html",)
    )


def diretorio_do_painel() -> Path | None:
    """A pasta concreta da mesma seleção validada que serve a página."""
    dados = dados_do_painel()
    return dados.pasta if dados else None


def _identificar_resposta(resposta, dados):
    resposta["X-Admin-Dados-Sha"] = dados.sha or "desconhecida"
    resposta["X-Admin-Dados-Run"] = dados.run_id or "desconhecida"
    resposta["X-Admin-Dados-Origem"] = dados.origem
    resposta["X-Admin-Dados-Condicao"] = dados.condicao
    resposta["Cache-Control"] = "no-store"
    return resposta


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
    a página busca os meses do histórico (`livro-AAAAMM.js`) por caminho
    RELATIVO. Sem a barra, o navegador resolveria `/admin/livro-202608.js` e a
    Memória abriria vazia. Quem redireciona `/admin/painel` para a forma com
    barra é o `CommonMiddleware` (APPEND_SLASH), que já está na cadeia.

    Desde 27/08/2026 ABRIR a página é um pedido só: o resumo e as regras vêm
    embutidos, escritos pelo gerador. O passado só é buscado se o mantenedor
    abrir a Memória.
    """
    dados = dados_do_painel()
    if dados is None:
        resposta = render(request, "admin/painel_ausente.html", status=500)
        resposta["X-Admin-Dados-Condicao"] = "indisponivel"
        resposta["Cache-Control"] = "no-store"
        return resposta

    html = (dados.pasta / "painel.html").read_bytes()
    identificacao = render_to_string(
        "admin/dados_do_painel.html", {"dados": dados}
    ).encode("utf-8")
    corpo = re.search(rb'<div class="wrap">', html) or re.search(
        rb"<body\b[^>]*>", html, re.IGNORECASE
    )
    posicao = corpo.end() if corpo else 0
    html = html[:posicao] + identificacao + html[posicao:]
    resposta = HttpResponse(html, content_type="text/html; charset=utf-8")
    resposta["Content-Security-Policy"] = _politica_de_seguranca(html)
    return _identificar_resposta(resposta, dados)


@require_safe
def painel_arquivo(request, path):
    """Os arquivos que a página pede DEPOIS de aberta: `livro-AAAAMM.js`.

    Serve do diretório-FONTE, nunca de `STATIC_ROOT` — `armadilhas/083`: o
    `collectstatic` do Dockerfile falha em todo build e o `|| true` engole, de
    modo que `STATIC_ROOT` está VAZIO na imagem de produção. Servir de lá daria
    404 só em produção, com a suíte inteira verde.

    A travessia de diretório já vem barrada pelo `safe_join` do Django, que
    devolve 400 (`SuspiciousFileOperation`, logado em `django.security`).
    """
    dados = dados_do_painel()
    if dados is None:
        raise Http404("nenhuma cópia do painel passou pela conferência")
    if Path(path).suffix.lower() not in EXTENSOES_SERVIDAS:
        raise Http404("o painel serve apenas .js, .css e .html")

    resposta = serve_do_django(request, path, document_root=dados.pasta)
    return _identificar_resposta(resposta, dados)
