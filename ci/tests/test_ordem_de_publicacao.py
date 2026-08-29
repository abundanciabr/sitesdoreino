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
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[2]
DEPLOY = RAIZ / ".github" / "workflows" / "deploy-celula.yml"

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
    """`checkout` consome `pagamentos` e `catalogo` — e sobe depois dos dois.

    Se alguém trocar a convenção `<OUTRA>_API_URL` sem ensinar este script, ele
    devolveria a ordem alfabética e ninguém notaria. Este teste é o que faz essa
    troca ficar vermelha.
    """
    proc = _roda('["checkout", "pagamentos", "catalogo"]')
    assert proc.returncode == 0, proc.stderr
    ordem = json.loads(proc.stdout)
    assert ordem.index("pagamentos") < ordem.index("checkout")
    assert ordem.index("catalogo") < ordem.index("checkout")


def test_a_admin_sobe_por_ultimo_porque_consome_tres():
    proc = _roda('["admin", "identidade", "alunos", "sugestoes"]')
    assert proc.returncode == 0, proc.stderr
    ordem = json.loads(proc.stdout)
    assert ordem[-1] == "admin", ordem
    assert ordem.index("sugestoes") < ordem.index("admin")


def test_a_explicacao_vai_para_o_stderr_e_o_dado_para_o_stdout():
    """Quem consome isto é um `$(...)` dentro do YAML.

    Uma linha de explicação no stdout entraria na matriz do deploy como se
    fosse nome de célula — e o job tentaria publicar uma célula chamada
    "ORDEM DE PUBLICAÇÃO".
    """
    proc = _roda('["quiz", "catalogo"]')
    assert proc.returncode == 0
    assert json.loads(proc.stdout) == ["catalogo", "quiz"]
    assert "provedor antes de consumidor" in proc.stderr


def test_celula_sozinha_continua_sendo_uma_lista_de_uma():
    proc = _roda('["quiz"]')
    assert proc.returncode == 0
    assert json.loads(proc.stdout) == ["quiz"]


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
    "entrada", ['["inventada"]', '["quiz", "nao-existe"]', '"quiz"', "isso não é json"]
)
def test_entrada_invalida_e_ERROR_e_nunca_uma_ordem_chutada(entrada: str):
    proc = _roda(entrada)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert proc.stdout.strip() == "", "nada pode ir para o stdout quando não se mediu"


# --------------------------------------------------------------------------
# A fiação: o workflow de verdade usa isto
# --------------------------------------------------------------------------


def test_o_deploy_ordena_antes_de_montar_a_matriz():
    """Ordenar depois de publicar não ordena nada.

    A matriz sai de `celulas=` no GITHUB_OUTPUT; a ordenação precisa acontecer
    ANTES dessa linha, senão a saída ordenada não chega a lugar nenhum.
    """
    texto = DEPLOY.read_text(encoding="utf-8")
    assert "ci/ordem_de_publicacao.py" in texto, (
        "o deploy voltou a publicar na ordem em que a detecção devolveu — que é "
        "alfabética, isto é, arbitrária"
    )
    assert texto.index("ci/ordem_de_publicacao.py") < texto.index('echo "celulas=$JSON"')


def test_a_matriz_continua_publicando_uma_celula_por_vez():
    """Ordem sem serialização não é ordem: em paralelo, todas sobem juntas."""
    fluxo = yaml.safe_load(DEPLOY.read_text(encoding="utf-8"))
    estrategia = fluxo["jobs"]["deploy"]["strategy"]
    assert estrategia.get("max-parallel") == 1, (
        "a matriz voltou a publicar em paralelo — a ordem de dependência deixa "
        "de existir na prática"
    )


def test_a_falha_da_ordem_para_o_deploy_em_vez_de_seguir():
    """`|| true` aqui devolveria a lista vazia e publicaria NADA, em verde."""
    texto = DEPLOY.read_text(encoding="utf-8")
    linha = [ln for ln in texto.splitlines() if "ordem_de_publicacao.py" in ln]
    assert linha, "sumiu a chamada"
    for candidata in linha:
        assert "|| true" not in candidata and "2>/dev/null" not in candidata
