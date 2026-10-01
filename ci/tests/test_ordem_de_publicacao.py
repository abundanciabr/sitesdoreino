"""A ORDEM DE PUBLICAÇÃO — provedor antes de consumidor, medido no código real.

Por que a propriedade precisa de guarda: publicar fora de ordem **não quebra
nada visivelmente**. O consumidor sobe antes do provedor, fala alguns minutos
com uma versão que ainda não existe, o site responde errado, e o deploy fecha
verde. Não há erro para ninguém ler — só usuário atendido errado durante a
janela. É a família do falso-verde (RETROSPECTIVA-FASE-D, padrão 1).

Dois tipos de teste aqui, e eles medem coisas diferentes:

    contra o REPOSITÓRIO REAL   a convenção `<OUTRA>_API_URL` existe mesmo e o
                                grafo sai dela — um teste só com dados
                                inventados provaria o algoritmo e não a
                                realidade que ele lê;
    contra CENÁRIOS de mentira  ciclo, célula desconhecida, determinismo — os
                                estados que o repositório real não produz sob
                                encomenda.
"""

from __future__ import annotations

import json
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PUBLICADOR = RAIZ / "infra" / "publicar.py"

sys.path.insert(0, str(RAIZ / "ci"))

from ordem_de_publicacao import ordenar  # noqa: E402


def _roda(argumento: str, raiz: Path | None = None):
    import os

    env = dict(os.environ)
    if raiz is not None:
        env["ORDEM_RAIZ"] = str(raiz)
    return subprocess.run(
        [sys.executable, str(RAIZ / "ci" / "ordem_de_publicacao.py"), argumento],
        cwd=str(RAIZ),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        env=env,
        check=False,
    )


# --------------------------------------------------------------------------
# Contra o repositório real: a ordem sai do código, não de uma lista escrita
# --------------------------------------------------------------------------


def test_o_provedor_sobe_antes_do_consumidor_no_repositorio_real():
    """O mapa publicado reconhece uma única aplicação para código do produto."""
    proc = _roda('["aplicacao"]')
    assert proc.returncode == 0, proc.stderr
    ordem = json.loads(proc.stdout)
    assert ordem == ["aplicacao"]


def test_a_admin_sobe_por_ultimo_porque_consome_tres():
    """O algoritmo ainda respeita dependências em cenários isolados."""
    grafo = {"admin": {"identidade", "alunos", "sugestoes"},
             "identidade": set(), "alunos": set(), "sugestoes": set()}
    ordem, _ = ordenar(list(grafo), grafo)
    assert ordem[-1] == "admin", ordem
    assert ordem.index("sugestoes") < ordem.index("admin")


def test_a_explicacao_vai_para_o_stderr_e_o_dado_para_o_stdout():
    """O dado da publicação é JSON puro; a explicação fica no stderr."""
    proc = _roda('["aplicacao"]')
    assert proc.returncode == 0
    assert json.loads(proc.stdout) == ["aplicacao"]
    assert "provedor antes de consumidor" in proc.stderr


def test_celula_sozinha_continua_sendo_uma_lista_de_uma():
    proc = _roda('["aplicacao"]')
    assert proc.returncode == 0
    assert json.loads(proc.stdout) == ["aplicacao"]


# --------------------------------------------------------------------------
# Os estados que o repositório real não produz
# --------------------------------------------------------------------------


def test_ciclo_nao_bloqueia_a_entrega_mas_e_ANUNCIADO():
    """Duas células que se consomem em círculo não têm ordem perfeita.

    Recusar publicar transformaria uma questão de arquitetura em site parado;
    escolher calado seria mentir. O desenho é: escolhe, e diz que escolheu.
    """
    grafo = {"a": {"b"}, "b": {"a"}, "c": set()}
    ordem, avisos = ordenar(["a", "b", "c"], grafo)
    assert sorted(ordem) == ["a", "b", "c"], "ninguém pode ficar de fora"
    assert avisos and "CICLO" in avisos[0]
    assert "a" in avisos[0] and "b" in avisos[0], "o aviso precisa NOMEAR o círculo"


def test_a_ordem_e_deterministica():
    """Mesmo push, mesma ordem — sempre.

    Sem o desempate alfabético, dois runs do mesmo commit poderiam publicar em
    ordens diferentes, e a ordem deixaria de ser propriedade para virar sorte.
    """
    grafo = {"a": set(), "b": set(), "c": {"a"}}
    primeira, _ = ordenar(["c", "b", "a"], grafo)
    for _ in range(5):
        assert ordenar(["a", "b", "c"], grafo)[0] == primeira


def test_dependencia_que_nao_esta_sendo_publicada_nao_entra_na_ordem():
    """Quem não está subindo agora já está no ar — não há ordem a respeitar."""
    grafo = {"checkout": {"pagamentos"}, "pagamentos": set()}
    ordem, avisos = ordenar(["checkout"], grafo)
    assert ordem == ["checkout"]
    assert not avisos


@pytest.mark.parametrize(
    "entrada", ['["inventada"]', '["aplicacao", "nao-existe"]', '"aplicacao"', "isso não é json"]
)
def test_entrada_invalida_e_ERROR_e_nunca_uma_ordem_chutada(entrada: str):
    proc = _roda(entrada)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert proc.stdout.strip() == "", "nada pode ir para o stdout quando não se mediu"


# --------------------------------------------------------------------------
# A fiação do publicador atual
# --------------------------------------------------------------------------


def _publicador():
    spec = importlib.util.spec_from_file_location("publicador_ordem", PUBLICADOR)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_o_publicador_reconhece_a_aplicacao_como_uma_unica_onda():
    publicar = _publicador()
    assert publicar.ondas(["aplicacao"]) == [["aplicacao"]]


def test_ativacao_da_aplicacao_exclui_troca_concorrente(monkeypatch, tmp_path):
    publicar = _publicador()
    monkeypatch.setattr(publicar, "RAIZ", tmp_path)
    chamadas = []
    monkeypatch.setattr(publicar, "travar", lambda caminho, **opcoes: (
        chamadas.append((caminho.name, opcoes)) or len(chamadas)))
    publicar.travas_da_celula("aplicacao")
    assert chamadas[0] == (".publicacao.lock", {"exclusiva": True})
    assert chamadas[1][0] == ".publicacao-aplicacao.lock"


def test_celula_desconhecida_nao_vira_publicacao_vazia():
    proc = _roda('["servico-inventado"]')
    assert proc.returncode == 2
    assert not proc.stdout.strip()
