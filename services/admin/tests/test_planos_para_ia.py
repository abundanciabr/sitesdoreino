"""Guardas da área `/mapa-ia/planos/` — os planos servidos SEM login.

O que estes testes existem para impedir, e cada um já custou caro em algum
lugar deste projeto:

- um documento vazar por ESQUECIMENTO (o `publico-para-ia` é fail-closed, e é
  aqui que isso é medido contra o código, não contra a intenção);
- a área virar uma fresta pela porta dos fundos, com alguém pendurando uma rota
  de ESCRITA sob o prefixo isento;
- o documento virar HTML e passar a poder injetar script na página de quem lê;
- um nome de arquivo esperto escapar da pasta.
"""

from __future__ import annotations

import pytest
from django.test import Client
from django.urls import get_resolver

from apps.core import planos_para_ia
from apps.core.porta import CAMINHOS_ISENTOS, PREFIXO_PUBLICO_DOS_PLANOS


@pytest.fixture
def pasta_de_planos(tmp_path, monkeypatch):
    """Uma pasta de planos de mentira, com um público e um privado."""
    pasta = tmp_path / "planos"
    pasta.mkdir()
    (pasta / "plano-aberto.md").write_text(
        "---\npublico-para-ia: true\n---\n\n# O plano aberto\n\ncorpo do aberto\n",
        encoding="utf-8",
    )
    (pasta / "decisao-fechada.md").write_text(
        "# A decisao fechada\n\nsegredo interno\n", encoding="utf-8"
    )
    monkeypatch.setattr(planos_para_ia, "CANDIDATOS", (pasta,))
    return pasta


def test_documento_marcado_sai_em_texto_puro_e_sem_login(pasta_de_planos):
    """O caminho feliz — e ele é o motivo da área existir."""
    resposta = Client().get("/mapa-ia/planos/plano-aberto")
    assert resposta.status_code == 200
    assert resposta["Content-Type"] == "text/plain; charset=utf-8"
    assert b"corpo do aberto" in resposta.content


def test_documento_NAO_marcado_responde_404(pasta_de_planos):
    """Fail-closed: sem a linha no cabeçalho, o documento não existe para fora.

    E é 404, não 403: um 403 confirmaria a existência do arquivo e viraria um
    oráculo de que documentos há em `docs/decisoes/`.
    """
    resposta = Client().get("/mapa-ia/planos/decisao-fechada")
    assert resposta.status_code == 404
    assert b"segredo interno" not in resposta.content


@pytest.mark.parametrize(
    "marca",
    [
        "publico-para-ia: True",
        "publico-para-ia: sim",
        "publico-para-ia: 1",
        "publico-para-ia: false",
        "publico_para_ia: true",
        "publico: true",
    ],
)
def test_quase_certo_nao_conta(pasta_de_planos, marca):
    """Só o valor exato conta.

    Um valor quase-certo que funcionasse ensinaria que a chave é frouxa, e a
    próxima pessoa escreveria qualquer coisa. Nota: `publico: true` é a marca
    da OUTRA área (`/docs/`, para alunos) — que ela não sirva aqui é o que
    impede um documento de aluno de virar plano para IA por acidente.
    """
    (pasta_de_planos / "quase.md").write_text(
        f"---\n{marca}\n---\n\n# Quase\n\ncorpo\n", encoding="utf-8"
    )
    assert Client().get("/mapa-ia/planos/quase").status_code == 404


def test_o_indice_lista_so_os_marcados(pasta_de_planos):
    resposta = Client().get("/mapa-ia/planos/")
    assert resposta.status_code == 200
    corpo = resposta.content.decode()
    assert "O plano aberto" in corpo
    assert "/mapa-ia/planos/plano-aberto" in corpo
    assert "decisao-fechada" not in corpo
    assert "A decisao fechada" not in corpo


def test_o_indice_aponta_para_o_mapa_tecnico(pasta_de_planos):
    """Quem chega aqui procurando arquitetura precisa achar o caminho.

    As duas áreas moram sob o mesmo prefixo e respondem perguntas diferentes;
    sem esta linha, uma IA que caísse aqui concluiria que é tudo que existe.
    """
    corpo = Client().get("/mapa-ia/planos/").content.decode()
    assert "/mapa-ia/INDICE.md" in corpo


@pytest.mark.parametrize(
    "nome", ["..%2f..%2fsettings", "../../config/settings", "plano.aberto", "plano/sub"]
)
def test_nome_esperto_nao_escapa_da_pasta(pasta_de_planos, nome):
    """A rota é a primeira cerca; `Path.resolve()` é a segunda."""
    resposta = Client().get(f"/mapa-ia/planos/{nome}")
    assert resposta.status_code == 404


def test_html_dentro_do_documento_nao_vira_html_na_resposta(pasta_de_planos):
    """Servido como texto puro, um documento não consegue virar página.

    Não é confiança em quem escreve o documento: é o `Content-Type` tornando a
    injeção impossível por construção.
    """
    (pasta_de_planos / "com-html.md").write_text(
        "---\npublico-para-ia: true\n---\n\n# Com HTML\n\n<script>alert(1)</script>\n",
        encoding="utf-8",
    )
    resposta = Client().get("/mapa-ia/planos/com-html")
    assert resposta.status_code == 200
    assert resposta["Content-Type"] == "text/plain; charset=utf-8"


def test_a_area_pede_para_nao_ser_indexada(pasta_de_planos):
    for endereco in ("/mapa-ia/planos/", "/mapa-ia/planos/plano-aberto"):
        assert Client().get(endereco)["X-Robots-Tag"] == "noindex"


def test_o_prefixo_dos_planos_tem_so_as_duas_rotas():
    """Nenhuma rota de ESCRITA pode nascer sob o prefixo isento.

    É o guarda que torna o prefixo seguro: sem ele, alguém pendura uma rota
    nova aqui embaixo e ela fica pública em silêncio — que é exatamente o modo
    de falha que a lista exata do `/mapa-ia/` evita por outro caminho.
    """
    prefixo_sem_barras = PREFIXO_PUBLICO_DOS_PLANOS.strip("/")
    padroes = [
        str(p.pattern)
        for p in get_resolver().url_patterns
        if str(p.pattern).lstrip("^").startswith(prefixo_sem_barras)
    ]
    assert len(padroes) == 2, f"rota nova sob o prefixo público: {padroes}"


def test_a_lista_exata_do_mapa_ia_nao_foi_afrouxada():
    """A área nova NÃO herda nem amplia a isenção do mapa técnico.

    `/mapa-ia/` continua com a decisão arquivo por arquivo (INV-P14). Se um dia
    alguém puser um prefixo lá, este teste reprova e a conversa acontece antes.
    """
    assert all(caminho.endswith((".md", "/healthz", "/")) for caminho in CAMINHOS_ISENTOS)
    assert not any(
        caminho.startswith(PREFIXO_PUBLICO_DOS_PLANOS) for caminho in CAMINHOS_ISENTOS
    )


def test_sem_pasta_a_area_responde_404_e_nao_estoura(monkeypatch):
    """Imagem sem a pasta embutida: 404 honesto, nunca 500."""
    monkeypatch.setattr(planos_para_ia, "CANDIDATOS", ())
    assert Client().get("/mapa-ia/planos/plano-aberto").status_code == 404
    resposta = Client().get("/mapa-ia/planos/")
    assert resposta.status_code == 200
    assert b"Nenhum documento" in resposta.content
