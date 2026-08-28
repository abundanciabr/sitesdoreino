"""Teste-guarda [INV-P14]: `/mapa-ia/` é a única fresta pública além de
`/healthz` — e só ela, só os arquivos exatos, só texto puro.

Como `test_inv_porta_fail_closed.py::test_os_caminhos_isentos_sao_exatamente_estes_e_so_estes`
já prova o CONJUNTO de caminhos isentos por igualdade exata, este arquivo
prova o COMPORTAMENTO: que cada um deles responde de verdade sem cookie, que
o conteúdo é o mesmo do repositório (mesma lei anti-duplicação de
`test_painel_vivo.py`), e que nada além do que está nomeado escapa.
"""

from pathlib import Path

from django.http import Http404
from django.test import Client, RequestFactory

from apps.core.mapa_ia import mapa_ia_arquivo

# `services/admin/tests/` → `services/admin` → `services` → raiz do repo.
MAPA_IA_NO_REPO = Path(__file__).resolve().parents[3] / "painel" / "ia"

DOCUMENTOS = (
    "INDICE.md",
    "01-leis-ritos-e-invariantes.md",
    "02-armadilhas-e-padroes-recorrentes.md",
    "03-sistema-do-painel-e-livro.md",
    "04-arquitetura-de-celulas-e-contratos.md",
    "05-infraestrutura-ci-e-deploy.md",
    "06-produto-decisoes-e-roadmap.md",
    "07-oportunidades-e-fronteiras.md",
)


def test_a_lista_de_documentos_deste_teste_bate_com_o_disco():
    """Se `painel/ia/` ganhar ou perder um `.md`, este teste é o primeiro a notar.

    Sem isto, um documento novo em `painel/ia/` poderia ficar anos sem
    ninguém perceber que ele não está (ou está!) público — os outros testes
    deste arquivo só sabem iterar sobre `DOCUMENTOS`, nunca sobre o disco.
    """
    reais = {p.name for p in MAPA_IA_NO_REPO.glob("*.md")}
    assert reais == set(DOCUMENTOS)


def test_indice_responde_sem_cookie_nenhum():
    r = Client().get("/mapa-ia/")
    assert r.status_code == 200, r.content
    assert r.content == (MAPA_IA_NO_REPO / "INDICE.md").read_bytes()


def test_cada_documento_responde_sem_cookie_e_e_o_arquivo_do_repositorio():
    cliente = Client()
    for nome in DOCUMENTOS:
        r = cliente.get(f"/mapa-ia/{nome}")
        assert r.status_code == 200, f"{nome}: {r.status_code} {r.content!r}"
        assert r.content == (MAPA_IA_NO_REPO / nome).read_bytes(), nome
        assert r["Content-Type"] == "text/plain; charset=utf-8", nome


def test_documentos_pedem_para_nao_serem_indexados():
    """Isto é para IA ler, não para aparecer numa busca de humano."""
    assert Client().get("/mapa-ia/").get("X-Robots-Tag") == "noindex"


def test_caminho_nao_listado_fica_atras_da_porta_como_todo_o_resto():
    """A PRIMEIRA trava é `CAMINHOS_ISENTOS`, por igualdade EXATA.

    `/mapa-ia/naoexiste.md`, `/mapa-ia/logica.js` e `/mapa-ia/..` não estão
    na lista — então a porta (`apps/core/porta.py`) os barra ANTES da view
    rodar, com a mesma resposta que qualquer outro caminho desconhecido
    desta célula: redireciona para o login (sem sessão) ou 404 (com sessão
    de quem não está autorizado). Isto é MAIS forte que a view recusar
    sozinha — o request nem chega lá.
    """
    cliente = Client()
    for caminho in ("/mapa-ia/naoexiste.md", "/mapa-ia/logica.js", "/mapa-ia/.."):
        r = cliente.get(caminho)
        assert (
            r.status_code == 302
        ), f"{caminho}: esperava 302 (porta), veio {r.status_code}"
        assert r["Location"].startswith("/entrar/google"), caminho


def test_a_view_tambem_se_protege_sozinha_independente_da_porta():
    """A SEGUNDA trava: mesmo que `CAMINHOS_ISENTOS` um dia vire prefixo por
    engano (a coisa que o teste de `porta.py` existe para impedir), a view
    ainda recusaria — chamada aqui DIRETO, sem passar pelo middleware, para
    provar que a defesa não depende só da porta estar bem configurada.
    """
    request = RequestFactory().get("/mapa-ia/qualquer-coisa")

    try:
        mapa_ia_arquivo(request, "naoexiste.md")
        assert False, "deveria ter levantado Http404"
    except Http404:
        pass

    try:
        mapa_ia_arquivo(request, "logica.js")  # existe em painel/, não em painel/ia/
        assert False, "deveria ter levantado Http404 (não é .md)"
    except Http404:
        pass

    try:
        # Termina em `.md` de propósito — passa a PRIMEIRA checagem da view
        # (extensão) para provar que é a SEGUNDA (a pasta continua sendo
        # ancestral do arquivo resolvido) que pega isto, não a primeira por
        # acidente. `painel/LEIA-ME.md` existe de verdade: se a trava
        # falhasse, este teste veria o conteúdo dele, não um 404.
        mapa_ia_arquivo(request, "../LEIA-ME.md")
        assert False, "deveria ter levantado Http404 (escapou da pasta)"
    except Http404:
        pass


def test_um_caminho_atras_da_porta_continua_exigindo_sessao():
    """Regressão: a mudança não afrouxou nada além do que está nomeado."""
    r = Client().get("/")
    assert r.status_code == 302
    r = Client().get("/painel/")
    assert r.status_code == 302
