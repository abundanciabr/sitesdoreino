"""AS MÉTRICAS DA FÁBRICA — o instrumento que não pode mentir (Onda 6).

Um número sobre saúde é lido com confiança e raramente conferido — é para isso
que ele existe. Por isso o perigo aqui não é o portão reprovar errado (ele não
reprova nada): é ele **informar errado**, e alguém decidir com base nisso.

Os três jeitos de este arquivo mentir, e um teste para cada:

    somar a AMOSTRA como se fosse o total   (o erro de 28/08, que voltou aqui)
    inventar seção quando falta medida      (meia-verdade com cara de relatório)
    discordar do painel sobre a fila do dono (dois números para a mesma pergunta)

O terceiro é o mais importante do arquivo, e em 29/08/2026 ele COBROU: o
`pedidos_ao_dono` não lia o livro — procurava o texto `precisa_do_dono: true`
dentro do arquivo. Um registro gravado com as chaves entre aspas
(`"precisa_do_dono": true`, forma que o livro aceita sem reclamar) não casava
com nenhuma variação procurada, e o pedido não era contado: o Python disse 6
onde o painel dizia 7. O guarda pegou — e a cura foi tirar a segunda
implementação do mundo: hoje o Python CHAMA `painel/logica.js::caixaDeEntrada`,
a mesma função que desenha a caixa "Precisa de você" na tela.

Os testes abaixo cobrem as duas metades disso: o contador precisa contar o que
o livro aceita (não o que uma expressão de texto reconhece), e precisa se CALAR
quando não consegue medir, em vez de devolver um número menor.
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


# --------------------------------------------------------------------------
# O CONTADOR LÊ O LIVRO — os guardas que faltavam em 29/08/2026
# --------------------------------------------------------------------------


def _livro(tmp_path: Path, registros: list[str]) -> Path:
    """Um repositório de mentirinha com o painel de verdade dentro.

    `logica.js` é copiada, não reescrita: é ela que está sob teste junto.
    """
    raiz = tmp_path / "repo"
    (raiz / "painel" / "registros").mkdir(parents=True)
    (raiz / "painel" / "logica.js").write_text(
        (RAIZ / "painel" / "logica.js").read_text(encoding="utf-8"), encoding="utf-8"
    )
    for i, conteudo in enumerate(registros):
        (raiz / "painel" / "registros" / f"20260829-{i:03d}-r.js").write_text(
            conteudo, encoding="utf-8"
        )
    return raiz


def _registro(nome: str, precisa: bool, aspas: bool, responde_a: str | None = None):
    """Um registro do livro. `aspas=True` usa chaves entre aspas (JSON)."""
    campos = {
        "arquivo": f'"{nome}"',
        "tipo": '"nota"',
        "quando": '"2026-08-29"',
        "titulo": '"t"',
        "detalhe": '"d"',
        "autoridade": '"sessao"',
        "evidencia": "null",
        "verificado_em": "null",
        "precisa_do_dono": "true" if precisa else "false",
        "responde_a": f'"{responde_a}"' if responde_a else "null",
        "gravidade": '"info"',
        "frente": "null",
        "vence_em_dias": "null",
        "se_eu_nao_decidir": "null",
        "recomendacao": "null",
        "reversivel": "null",
        "impacto": "null",
    }
    corpo = ",\n  ".join(
        (f'"{k}": {v}' if aspas else f"{k}: {v}") for k, v in campos.items()
    )
    return (
        "(function(){ (window.REGISTROS = window.REGISTROS || []).push({\n  "
        + corpo
        + "\n});})();\n"
    )


def test_registro_com_chaves_entre_aspas_TAMBEM_conta(tmp_path: Path):
    """O bug de 29/08/2026, encenado.

    O livro aceita as duas pontuações; a busca por texto só reconhecia uma. Um
    pedido sumia da conta sem nada ficar vermelho nas telas.
    """
    raiz = _livro(
        tmp_path,
        [
            _registro("20260829-000-r", precisa=True, aspas=False),
            _registro("20260829-001-r", precisa=True, aspas=True),
        ],
    )
    assert metricas.pedidos_ao_dono(raiz) == 2, (
        "um dos dois pedidos não foi contado — é exatamente o defeito que fez "
        "o Python dizer 6 e o painel dizer 7"
    )


def test_pedido_respondido_sai_da_fila(tmp_path: Path):
    """A outra metade da regra: pedido com resposta não espera mais ninguém."""
    raiz = _livro(
        tmp_path,
        [
            _registro("20260829-000-r", precisa=True, aspas=False),
            _registro(
                "20260829-001-r",
                precisa=False,
                aspas=True,
                responde_a="20260829-000-r",
            ),
        ],
    )
    assert metricas.pedidos_ao_dono(raiz) == 0


def test_sem_a_regra_do_painel_e_ERROR_nunca_um_numero(tmp_path: Path):
    """Contador que chuta a fila do dono é pior que contador que se cala."""
    raiz = _livro(tmp_path, [_registro("20260829-000-r", precisa=True, aspas=False)])
    (raiz / "painel" / "logica.js").unlink()
    with pytest.raises(ErroDeInstrumentacao):
        metricas.pedidos_ao_dono(raiz)


def test_livro_ilegivel_e_ERROR_nunca_zero(tmp_path: Path):
    """Registro quebrado não pode virar 'ninguém está esperando por você'."""
    raiz = _livro(tmp_path, ["isto nao e javascript valido ((("])
    with pytest.raises(ErroDeInstrumentacao):
        metricas.pedidos_ao_dono(raiz)
