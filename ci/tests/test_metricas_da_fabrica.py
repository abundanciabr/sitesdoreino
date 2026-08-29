"""AS MÉTRICAS DA FÁBRICA — o instrumento que não pode mentir (Onda 6).

Um número sobre saúde é lido com confiança e raramente conferido — é para isso
que ele existe. Por isso o perigo aqui não é o portão reprovar errado (ele não
reprova nada): é ele **informar errado**, e alguém decidir com base nisso.

Os três jeitos de este arquivo mentir, e um teste para cada:

    somar a AMOSTRA como se fosse o total   (o erro de 28/08, que voltou aqui)
    inventar seção quando falta medida      (meia-verdade com cara de relatório)
    discordar do painel sobre a fila do dono (dois números para a mesma pergunta)

O terceiro é o mais importante do arquivo: `pedidos_ao_dono` reimplementa, em
Python, uma regra que o painel calcula em JavaScript. Duas implementações da
mesma pergunta divergem no primeiro dia em que alguém mexe numa delas — então
o teste compara as duas contra o livro REAL.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "ci"))

import metricas_da_fabrica as metricas  # noqa: E402
from _nucleo import ErroDeInstrumentacao  # noqa: E402

AGORA = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)


def _dados(**mudancas) -> dict:
    base = {
        "dias": 7,
        "pousos": 100,
        "amostra": 40,
        "minutos": [10.0, 20.0, 30.0],
        "commits": [1, 2, 5],
        "na_fila": 1,
        "abertos": 3,
        "pedidos_ao_dono": 2,
        "leis_sem_mecanismo": 3,
    }
    base.update(mudancas)
    return base


# --------------------------------------------------------------------------
# Amostra não é total — a lição de 28/08, que voltou a aparecer aqui
# --------------------------------------------------------------------------


def test_a_contagem_de_pousos_nao_sai_da_amostra():
    """377 entregas medidas no Git, 40 na amostra: o texto tem de dizer 377.

    A consulta que traz `commits` estoura o orçamento do GraphQL acima de ~40
    PRs. A saída fácil seria baixar o teto e chamar o teto de total — foi
    exatamente esse erro que custou o registro 20260828-077, no mesmo dia.
    """
    texto = metricas.montar(_dados(pousos=377, amostra=40))
    assert "377 entrega(s)" in texto
    assert "amostra de 40 PR(s)" in texto


def test_a_amostra_e_declarada_como_amostra():
    texto = metricas.montar(_dados())
    assert "amostra" in texto.lower()
    assert "contadas no Git" in texto


def test_sem_amostra_o_texto_diz_ausencia_de_dado_e_nao_saude():
    """Zero PRs na janela não é 'tudo bem' nem 'tudo mal' — é não medido."""
    texto = metricas.montar(_dados(amostra=0, minutos=[], commits=[]))
    assert "ausência de dado" in texto
    assert "min" not in texto.split("NA FILA")[0].replace("mín", "")


# --------------------------------------------------------------------------
# Meia-verdade não sai
# --------------------------------------------------------------------------


@pytest.mark.parametrize("campo", ["pousos", "minutos", "commits"])
def test_medida_incompleta_nao_vira_relatorio(campo: str):
    dados = _dados()
    del dados[campo]
    with pytest.raises(ErroDeInstrumentacao):
        metricas.montar(dados)


def test_o_arquivo_nao_julga():
    """Métrica que reprova vira meta, e meta vira gente otimizando o número.

    O contrato deste portão é ter só dois estados: mediu (0) ou não mediu (2).
    Um exit 1 aqui seria um juízo — e juízo sobre saúde de fábrica é humano.
    """
    fonte = (RAIZ / "ci" / "metricas_da_fabrica.py").read_text(encoding="utf-8")
    assert "return 1" not in fonte, "apareceu um veredito de reprovação"
    assert "Não existe exit 1" in fonte


def test_dias_invalido_e_ERROR():
    assert metricas.main(["--dias", "0"]) == 2


# --------------------------------------------------------------------------
# O número do dono: duas implementações, uma resposta
# --------------------------------------------------------------------------


def test_a_fila_do_dono_bate_com_a_do_painel():
    """A MESMA pergunta, medida em Python aqui e em JavaScript no painel.

    Se divergirem, o mantenedor tem dois números para "quantas coisas esperam
    por mim" — e é exatamente a doença que a reforma do painel curou no livro.
    """
    do_python = metricas.pedidos_ao_dono(RAIZ)
    script = (
        "var fs=require('fs'),path=require('path'),vm=require('vm');"
        "var dir='painel/registros';var regs=[];"
        "fs.readdirSync(dir).filter(function(n){return n.slice(-3)==='.js';})"
        ".sort().forEach(function(n){var s={window:{}};"
        "vm.runInNewContext(fs.readFileSync(path.join(dir,n),'utf8'),s,{timeout:2000});"
        "(s.window.REGISTROS||[]).forEach(function(r){regs.push(r);});});"
        "var p=regs.filter(function(r){return r.precisa_do_dono && !regs.some("
        "function(o){return o.responde_a===r.arquivo;});});"
        "console.log(p.length);"
    )
    proc = subprocess.run(
        ["node", "-e", script],
        cwd=str(RAIZ),
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if proc.returncode != 0:
        pytest.skip(f"node indisponível ou falhou: {proc.stderr[:200]}")
    do_painel = int(proc.stdout.strip())
    assert do_python == do_painel, (
        f"o Python diz {do_python} pedido(s) e a regra do painel diz "
        f"{do_painel} — duas respostas para a mesma pergunta"
    )


def test_leis_sem_mecanismo_le_a_divida_de_verdade():
    """O número vem da lista versionada, não de um total escrito à mão."""
    n = metricas.leis_sem_mecanismo(RAIZ)
    linhas = [
        linha
        for linha in (RAIZ / "ci" / "leis-sem-mecanismo.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if linha.strip() and not linha.strip().startswith("#")
    ]
    assert n == len(linhas)


def test_livro_ausente_e_ERROR(tmp_path: Path):
    with pytest.raises(ErroDeInstrumentacao):
        metricas.pedidos_ao_dono(tmp_path)


# --------------------------------------------------------------------------
# A coleta, sem rede
# --------------------------------------------------------------------------


def test_a_coleta_recusa_contagem_ilegivel(tmp_path: Path, monkeypatch):
    class Falsa:
        stdout = "não é número"

    monkeypatch.setattr(metricas, "executar", lambda *a, **k: Falsa())
    with pytest.raises(ErroDeInstrumentacao):
        metricas.coletar(RAIZ, 7, agora=AGORA)


def test_a_coleta_separa_contagem_de_amostra(tmp_path: Path, monkeypatch):
    """O Git diz 90; o GitHub devolve 2 PRs. O relatório precisa dizer 90."""

    class Falsa:
        stdout = "90"

    novo = (AGORA - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
    monkeypatch.setattr(metricas, "executar", lambda *a, **k: Falsa())
    monkeypatch.setattr(
        metricas,
        "_gh_json",
        lambda args, *a, **k: (
            []
            if "open" in args
            else [
                {
                    "number": 1,
                    "title": "x",
                    "createdAt": novo,
                    "mergedAt": novo,
                    "commits": [{}, {}],
                },
                {
                    "number": 2,
                    "title": "y",
                    "createdAt": novo,
                    "mergedAt": novo,
                    "commits": [{}],
                },
            ]
        ),
    )
    monkeypatch.setattr(metricas, "pedidos_ao_dono", lambda raiz: 0)
    monkeypatch.setattr(metricas, "leis_sem_mecanismo", lambda raiz: 0)
    dados = metricas.coletar(RAIZ, 7, agora=AGORA)
    assert dados["pousos"] == 90
    assert dados["amostra"] == 2
    assert "90 entrega(s)" in metricas.montar(dados)
