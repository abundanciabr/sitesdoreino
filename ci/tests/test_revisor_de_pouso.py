"""GUARDA — o revisor de pouso acha o que diz que acha, e some quando não pode.

Um revisor que nunca apontou nada é indistinguível de um revisor desligado, e
um que aponta tudo é indistinguível de ruído. Por isso cada detector aqui tem
DOIS testes: o caso que ele precisa acusar (tirado da armadilha real que o
originou) e o caso vizinho que ele precisa deixar passar.

E há a terceira família, que é a mais importante deste arquivo: **o revisor não
pode segurar um pouso**. Ele roda dentro da máquina que faz TODO PR desta casa
entrar; um erro aqui não quebra uma tela, trava a esteira. Diff ilegível, diff
vazio, exceção não prevista — tudo desagua em `NAO-REVISADO` e exit 0.

Os corpora abaixo são falsos-verdes DE VERDADE, copiados das armadilhas que os
mediram em 01/09/2026. Se um dia um detector deixar de pegar o caso que o fez
nascer, este arquivo fica vermelho.
"""

# revisor-de-pouso: ignorar
#
# Esta é a única marca de dispensa do repositório, e ela está aqui pelo motivo
# exato para o qual foi criada: metade deste arquivo é falso-verde DE PROPÓSITO,
# e a outra metade afirma que o revisor não achou nada (`_codigos(X) == []`),
# que é a forma canônica de asserção de ausência. Sem a marca, medido: o
# primeiro caso real do revisor seriam SETE apontamentos errados sobre si
# mesmo — e revisor que erra sete vezes na estreia não é lido nunca mais.
#
# Não é escapatória para afrouxar guarda: ele OPINA, não reprova, então não há
# nada aqui para contornar. E as ausências deste arquivo têm causa única provada
# por mutação, não por promessa: 13 de 13 mutações reprovaram nomeando o teste
# que caiu (`armadilhas/268`).

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

CI = Path(__file__).resolve().parents[1]
if str(CI) not in sys.path:
    sys.path.insert(0, str(CI))

import revisor_de_pouso as rev  # noqa: E402

# ---------------------------------------------------------------------------
# Corpora. Cada um é um patch unificado mínimo, no formato que o `gh pr diff`
# devolve. Os `+` de dentro das aspas são o patch; os detectores só enxergam
# o lado NOVO.
# ---------------------------------------------------------------------------

# `armadilhas/266`: as duas asserções são de ausência, e o vazio tinha DUAS
# causas suficientes — a preguiça (que se queria provar) e a config ausente.
D1_ACUSA = """\
diff --git a/services/funil/tests/test_sino.py b/services/funil/tests/test_sino.py
--- /dev/null
+++ b/services/funil/tests/test_sino.py
@@ -0,0 +1,5 @@
+def test_a_property_nao_toca_a_rede_para_quem_nao_foi_reconhecido(rede):
+    ator = AtorDaRequisicao("", "site-qualquer")
+    assert ator.progresso is None
+    assert _chamadas_de_progresso(rede) == []
"""

# Os DOIS pares verdes, e são dois de propósito: o detector tem duas saídas, e
# um corpus que sai por uma delas não prova nada sobre a outra. É a régua da
# `armadilhas/267` aplicada ao próprio revisor — e ela cobrou: com um par verde
# só, as mutações M6 e M7 deste PR saíram VERDES.
#
# (a) sai pela PRESENÇA: o teste também afirma que algo aconteceu.
D1_LIMPO_POR_PRESENCA = """\
diff --git a/services/funil/tests/test_sino.py b/services/funil/tests/test_sino.py
--- /dev/null
+++ b/services/funil/tests/test_sino.py
@@ -0,0 +1,6 @@
+def test_a_property_desiste_cedo_mas_o_cenario_funciona(rede, ligado):
+    rede.get(EU).mock(return_value=httpx.Response(200, json=COM_NIVEL))
+    assert AtorDaRequisicao(COOKIE, "site").progresso.nivel == 7
+    assert AtorDaRequisicao("", "site").progresso is None
"""

# (b) sai pela PRESENÇA FORTE: só ausências, mas com a prova de que a chamada
# de verdade acontece. É o conserto que a `armadilhas/266` prescreve.
D1_LIMPO_POR_PRESENCA_FORTE = """\
diff --git a/services/funil/tests/test_sino.py b/services/funil/tests/test_sino.py
--- /dev/null
+++ b/services/funil/tests/test_sino.py
@@ -0,0 +1,7 @@
+def test_o_sino_nao_avisa_duas_vezes_pelo_mesmo_fato(rede, ligado):
+    rota = rede.post(AVISAR).mock(return_value=httpx.Response(200))
+    avisar(aluno)
+    avisar(aluno)
+    rota.assert_called_once()
+    assert avisos_repetidos() == []
+    assert erro_registrado() is None
"""

# `armadilhas/267`: o cenário só tinha quem SOBREVIVE ao filtro, então o grupo
# dos cortados dava zero — o ponto onde as duas implementações concordam.
D2_ACUSA = """\
diff --git a/services/alunos/tests/test_listar.py b/services/alunos/tests/test_listar.py
--- a/services/alunos/tests/test_listar.py
+++ b/services/alunos/tests/test_listar.py
@@ -8,4 +8,8 @@ def test_quem_tem_ativa_fica_na_lista_mesmo_com_uma_recusada():
     _pedido("ana@exemplo.test", RECUSADA)
     _pedido("ana@exemplo.test", ATIVA)

+    saida = _rodar(exceto="recusada")
+
+    assert "1 pessoa(s)." in saida
+    assert "ficaram de fora, porque so tem pedido recusada (0):" in saida
"""

# O conserto: o Dario entra em cena, e o grupo dos cortados é conferido por
# NÚMERO e por NOME. A implementação errada esvazia o grupo e o teste cai.
D2_LIMPO = """\
diff --git a/services/alunos/tests/test_listar.py b/services/alunos/tests/test_listar.py
--- a/services/alunos/tests/test_listar.py
+++ b/services/alunos/tests/test_listar.py
@@ -8,4 +8,9 @@ def test_quem_tem_ativa_fica_na_lista_mesmo_com_uma_recusada():
     _pedido("ana@exemplo.test", RECUSADA)
     _pedido("ana@exemplo.test", ATIVA)

+    _pedido("dario@exemplo.test", RECUSADA)
+    saida = _rodar(exceto="recusada")
+
+    assert "1 pessoa(s)." in saida
+    assert "ficaram de fora, porque so tem pedido recusada (1):" in saida
+    assert "dario@exemplo.test" in saida
"""

# O valor conferido é o mesmo que o autor mandou o dublê devolver.
D3_ACUSA = """\
diff --git a/services/loja/tests/test_preco.py b/services/loja/tests/test_preco.py
--- /dev/null
+++ b/services/loja/tests/test_preco.py
@@ -0,0 +1,4 @@
+def test_o_preco_vem_do_catalogo(monkeypatch):
+    monkeypatch.setattr(catalogo, "buscar", lambda _: "1499 reais")
+    assert descrever(SKU) == "1499 reais"
"""

# Vizinho legítimo: o dublê devolve um status HTTP, e a asserção confere o
# status. Apontar isso seria ruído puro — é o padrão de todo teste de cliente.
D3_LIMPO = """\
diff --git a/services/loja/tests/test_cliente.py b/services/loja/tests/test_cliente.py
--- /dev/null
+++ b/services/loja/tests/test_cliente.py
@@ -0,0 +1,4 @@
+def test_o_cliente_devolve_o_corpo(rede):
+    rede.get(URL).mock(return_value=httpx.Response(200, json={"nivel": 3}))
+    assert buscar().status_code == 200
"""

# Portão novo em `ci/`, e nenhuma linha nova de teste o vê RECUSANDO.
D4_ACUSA = """\
diff --git a/ci/muralha-do-nada.py b/ci/muralha-do-nada.py
--- /dev/null
+++ b/ci/muralha-do-nada.py
@@ -0,0 +1,3 @@
+def vale(x):
+    return x >= 0
diff --git a/ci/tests/test_muralha_do_nada.py b/ci/tests/test_muralha_do_nada.py
--- /dev/null
+++ b/ci/tests/test_muralha_do_nada.py
@@ -0,0 +1,3 @@
+def test_aceita_o_certo():
+    assert vale(3) is True
"""

# O mesmo portão, com o caso que o vê recusar — e dizendo o quê.
D4_LIMPO = """\
diff --git a/ci/muralha-do-nada.py b/ci/muralha-do-nada.py
--- /dev/null
+++ b/ci/muralha-do-nada.py
@@ -0,0 +1,3 @@
+def vale(x):
+    return x >= 0
diff --git a/ci/tests/test_muralha_do_nada.py b/ci/tests/test_muralha_do_nada.py
--- /dev/null
+++ b/ci/tests/test_muralha_do_nada.py
@@ -0,0 +1,6 @@
+def test_aceita_o_certo():
+    assert vale(3) is True
+
+
+def test_recusa_o_errado_e_diz_o_que():
+    with pytest.raises(ValueError, match="negativo"):
+        vale(-1)
"""

# Nada de teste, nada de portão: um diff que o revisor não tem o que apontar.
SEM_NADA_A_DIZER = """\
diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1,2 +1,3 @@
 # Projeto

+Uma linha nova de documentação.
"""


def _codigos(patch: str) -> list[str]:
    return [achado.detector for achado in rev.revisar(patch)]


# ---------------------------------------------------------------------------
# D1 — asserção de ausência com mais de uma causa suficiente (armadilhas/266)
# ---------------------------------------------------------------------------


def test_d1_acusa_o_teste_cujas_assercoes_sao_todas_de_ausencia():
    """O falso-verde medido: o guarda passava com a preguiça arrancada."""
    achados = rev.revisar(D1_ACUSA)
    assert [a.detector for a in achados] == ["D1"], achados
    assert achados[0].arquivo == "services/funil/tests/test_sino.py"
    # A linha apontada precisa ser uma das asserções, não o `def` nem o cenário.
    assert "assert" in achados[0].trecho
    assert "armadilhas/266" in achados[0].referencia


@pytest.mark.parametrize(
    "patch,saida",
    [
        pytest.param(D1_LIMPO_POR_PRESENCA, "presença", id="tambem-afirma-presenca"),
        pytest.param(
            D1_LIMPO_POR_PRESENCA_FORTE, "forte", id="prova-que-a-chamada-acontece"
        ),
    ],
)
def test_d1_nao_acusa_quando_o_teste_prova_que_a_coisa_acontece(patch, saida):
    """Os pares verdes, um por SAÍDA do detector.

    Um par verde só não bastava, e isto foi medido neste próprio PR: com um
    corpus único, duas mutações do D1 saíram VERDES, porque o corpus escapava
    por um terceiro caminho e nunca chegava à regra sob prova. É a
    `armadilhas/267` mordendo o revisor que existe para achá-la.
    """
    assert _codigos(patch) == [], saida


# ---------------------------------------------------------------------------
# D2 — filtro provado por um lado só (armadilhas/267)
# ---------------------------------------------------------------------------


def test_d2_acusa_o_filtro_cujo_grupo_cortado_esta_vazio():
    achados = rev.revisar(D2_ACUSA)
    assert [a.detector for a in achados] == ["D2"], achados
    assert "(0)" in achados[0].trecho
    assert "armadilhas/267" in achados[0].referencia


def test_d2_nao_acusa_quando_o_cortado_aparece_por_numero_e_por_nome():
    assert _codigos(D2_LIMPO) == []


# ---------------------------------------------------------------------------
# D3 — a asserção mede o dublê
# ---------------------------------------------------------------------------


def test_d3_acusa_a_assercao_que_confere_o_valor_decidido_pelo_duble():
    achados = rev.revisar(D3_ACUSA)
    assert [a.detector for a in achados] == ["D3"], achados
    # O recado tem de NOMEAR o valor repetido: apontar sem dizer qual manda o
    # leitor procurar sozinho, e revisor que dá trabalho não é lido.
    assert "1499 reais" in achados[0].pergunta


def test_d3_nao_acusa_status_http_devolvido_por_duble():
    """Conferir o status que o dublê devolveu é o padrão de todo teste de
    cliente. Apontar isso seria ruído puro, e ruído é como um revisor morre."""
    assert _codigos(D3_LIMPO) == []


# ---------------------------------------------------------------------------
# D4 — portão que ninguém viu reprovando (RETROSPECTIVA-FASE-D §1)
# ---------------------------------------------------------------------------


def test_d4_acusa_portao_novo_sem_nenhum_teste_que_o_veja_recusar():
    achados = rev.revisar(D4_ACUSA)
    assert [a.detector for a in achados] == ["D4"], achados
    assert "ci/muralha-do-nada.py" in achados[0].pergunta


def test_d4_nao_acusa_quando_o_teste_ve_o_portao_recusando():
    assert _codigos(D4_LIMPO) == []


def test_d4_enxerga_os_arquivos_do_patch_inteiro():
    """Guarda de um bug que existiu: `^` sem `re.M` casa só no início do PATCH.

    Com ele, `arquivos_do_diff` devolvia lista vazia e o D4 NUNCA disparava —
    em silêncio, que é o pior desfecho possível para um detector.
    """
    assert rev.arquivos_do_diff(D4_ACUSA) == [
        "ci/muralha-do-nada.py",
        "ci/tests/test_muralha_do_nada.py",
    ]


# ---------------------------------------------------------------------------
# O veredito — e por que "limpo" nunca pode parecer com "não rodei"
# ---------------------------------------------------------------------------


def test_diff_sem_teste_e_sem_portao_sai_limpo():
    assert _codigos(SEM_NADA_A_DIZER) == []


def test_o_recado_limpo_diz_o_que_foi_olhado():
    """Ausência de evidência não é evidência de sucesso ([INV-CI01]).

    Um "nada a apontar" que não diga o que foi procurado é indistinguível de um
    revisor que não rodou — e é assim que a casa inteira aprende a ignorá-lo.
    """
    texto = rev.comentario(1, [])
    assert "Nada a apontar" in texto
    for esperado in ("armadilhas/266", "armadilhas/267", "dublê", "recusar"):
        assert esperado in texto, f"o recado limpo não menciona {esperado!r}"


def test_o_recado_com_achado_cita_arquivo_linha_e_a_pergunta():
    texto = rev.comentario(1, rev.revisar(D1_ACUSA))
    assert "services/funil/tests/test_sino.py:" in texto
    assert "opinião, não reprovação" in texto
    assert "armadilhas/268" in texto  # o rodapé que ensina a provar direito


def test_o_recado_respeita_o_teto_de_achados():
    """Quarenta apontamentos não são quarenta informações: são zero leituras."""
    muitos = [
        rev.Achado("D1", f"caso {i}", "a.py", i, "assert x == []", "por quê?", "ref")
        for i in range(rev.TETO_DE_ACHADOS + 4)
    ]
    texto = rev.comentario(1, muitos)
    assert texto.count("### ") == rev.TETO_DE_ACHADOS
    assert "e mais 4" in texto


def test_a_dispensa_silencia_o_bloco_e_so_o_bloco():
    """A escapatória é deliberada, e não afrouxa nada: o revisor não reprova.

    Ela existe para os arquivos que falam SOBRE testes ruins — este aqui, por
    exemplo — não virarem uma fábrica de apontamentos sobre si mesmos.
    """
    dois_testes_ruins = """\
diff --git a/ci/tests/test_exemplos.py b/ci/tests/test_exemplos.py
--- /dev/null
+++ b/ci/tests/test_exemplos.py
@@ -0,0 +1,7 @@
+def test_um(rede):
+    assert _chamadas(rede) == []
+
+
+def test_dois(rede):
+    assert _outras(rede) == []
"""
    # Sem a marca, os DOIS blocos gritam. É a contraprova: sem ela, o teste de
    # baixo passaria com a dispensa apagada do código.
    assert _codigos(dois_testes_ruins) == ["D1", "D1"]

    # Com a marca em UM bloco, o arquivo inteiro se cala — é para isso que ela
    # serve: um arquivo que fala SOBRE testes ruins gritaria pelos vizinhos.
    com_dispensa = dois_testes_ruins.replace(
        "+def test_um", f"+# {rev.DISPENSA}\n+def test_um"
    )
    assert _codigos(com_dispensa) == []


# ---------------------------------------------------------------------------
# FAIL-OPEN — a família que importa mais que todas as outras juntas
# ---------------------------------------------------------------------------


def _rodar_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CI / "revisor_de_pouso.py"), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**__import__("os").environ, "PYTHONUTF8": "1"},
        timeout=120,
        check=False,
    )


def test_diff_ilegivel_vira_nao_revisado_e_sai_com_exit_zero(tmp_path):
    """O revisor roda dentro da pista. Ele NÃO pode segurar um pouso."""
    proc = _rodar_cli("0", "--diff-de", str(tmp_path / "nao-existe.patch"))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert f"{rev.MARCA} {rev.NAO_REVISADO}" in proc.stdout
    assert "O pouso segue normalmente" in proc.stdout


def test_diff_vazio_nao_vira_limpo(tmp_path):
    """"Não consegui medir" nunca pode chegar disfarçado de "está limpo"."""
    vazio = tmp_path / "vazio.patch"
    vazio.write_text("", encoding="utf-8")
    proc = _rodar_cli("0", "--diff-de", str(vazio))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert f"{rev.MARCA} {rev.LIMPO}" not in proc.stdout
    assert f"{rev.MARCA} {rev.NAO_REVISADO}" in proc.stdout


def test_patch_com_achado_sai_com_exit_zero_e_conta_os_achados(tmp_path):
    """Achar coisa não é reprovar: o exit continua 0, e a contagem vai na linha."""
    alvo = tmp_path / "com-achado.patch"
    alvo.write_text(D1_ACUSA, encoding="utf-8")
    proc = _rodar_cli("0", "--diff-de", str(alvo))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert f"{rev.MARCA} {rev.ACHADOS} 1" in proc.stdout


def test_excecao_dentro_do_proprio_revisor_vira_nao_revisado(capsys):
    """A blindagem: nem um bug NOSSO pode travar a esteira da casa inteira."""

    def explode():
        raise RuntimeError("o revisor quebrou de propósito")

    assert rev._blindar(explode)() == 0
    saida = capsys.readouterr().out
    assert f"{rev.MARCA} {rev.NAO_REVISADO}" in saida
    assert "o revisor quebrou de propósito" in saida


def test_a_linha_do_veredito_e_ascii():
    """Ela é contrato com quem lê o log — e acento atravessando YAML, shell e
    locale de executor já quebrou roteamento nesta casa (ci/mergear.py)."""
    for pedaco in (rev.MARCA, rev.LIMPO, rev.ACHADOS, rev.NAO_REVISADO):
        assert pedaco.isascii(), pedaco


def test_o_revisor_nao_executa_nada_do_pr():
    """A pista roda com poder de merge, e o repositório é público.

    Este guarda é de FORMA de propósito: o que ele protege é a ausência de uma
    capacidade. Nenhum `exec`, `eval`, `import` dinâmico ou checkout do ramo do
    PR pode aparecer aqui sem alguém decidir isso de olhos abertos.
    """
    fonte = (CI / "revisor_de_pouso.py").read_text(encoding="utf-8")
    corpo = fonte.split('"""', 2)[2]  # fora do docstring, que fala sobre isso
    for proibido in ("exec(", "eval(", "importlib", "checkout", "__import__"):
        assert proibido not in corpo, (
            f"{proibido!r} apareceu no revisor. Ele lê o texto do diff e mais "
            "nada: rodar código de um PR aqui entrega a PISTA_TOKEN a quem "
            "abrir o PR."
        )


@pytest.mark.parametrize(
    "linha,e_ausencia",
    [
        ("    assert chamadas == []", True),
        ("    assert ator.progresso is None", True),
        ("    assert not visto", True),
        ("    assert len(fila) == 0", True),
        ('    assert "ana" not in saida', True),
        ("    assert nivel == 7", False),
        ('    assert "dario" in saida', False),
        ("    assert resposta.status_code == 200", False),
    ],
)
def test_o_vocabulario_de_ausencia_distingue_os_dois_lados(linha, e_ausencia):
    assert rev._e_ausencia(linha) is e_ausencia
