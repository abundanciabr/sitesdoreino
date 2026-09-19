"""O SINO ENTREGA A LIÇÃO, NÃO O ENDEREÇO (06/09/2026).

Por que estes guardas existem: na semana de 06/09/2026 o sino disparou 891
vezes dizendo "LEIA armadilhas/NNN", e cada disparo custava UMA CHAMADA INTEIRA
(contexto mediano de 206.460 tokens) para ler um arquivo de 996 bytes. Eram
4,3% da cota da semana pagando ida e volta em vez de conhecimento.

O que se prova aqui, nesta ordem:

  (a) casou  ................ o retorno traz a lição e as seções, dentro do teto;
  (b) segunda vez na sessão . volta a ser só o endereço, em uma linha;
  (c) sem as seções ......... sai a lição, ou só o endereço, sem quebrar;
  (d) arquivo ausente ....... exatamente o comportamento de antes.

E, pela lição 2 da armadilhas/176 (hook fail-open esconde o próprio defeito), o
sino é exercitado também COMO PROCESSO: só esse teste distingue "decidiu calar"
de "quebrou ao falar", porque o `except Exception: return 0` engole a segunda.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
CI = RAIZ / "ci"
SINO = CI / "sino_das_armadilhas.py"
sys.path.insert(0, str(CI))

import sino_das_armadilhas as sino  # noqa: E402


ENTRADA_COMPLETA = """---
schema_version: 2
armadilha: 900
---

# O caso que já custou uma rodada

**Sintoma:** o comando devolve `Erro Plantado 900` e o teste fica vermelho.
**Causa:** a rota nasce sem `response=` no decorador.
**Solução:** devolva `JsonResponse(dict, status=N)` direto.
**Origem:** PR inventado, para o teste.
"""

ENTRADA_EM_TITULOS = """# O mesmo caso, escrito com títulos

## Sintoma

O comando devolve `Erro Plantado 901`.

## Como se cura

Troque o decorador e rode de novo.

**Detalhe que mora dentro da cura:** e este parágrafo continua sendo cura.

## Origem

PR inventado.
"""

ENTRADA_SEM_SECOES = """# Uma entrada que não usa nenhuma das rubricas

Ela só narra o caso em prosa corrida, sem `Sintoma`, sem `Causa` e sem
`Solução`, porque o catálogo tem entradas assim.

**Origem:** PR inventado.
"""


def _sinal(numero: str, arquivo: str, regex: str) -> list[dict]:
    return [{"armadilha": numero, "arquivo": arquivo,
             "titulo": f"o caso {numero}", "regex": regex}]


def _entrada(saida: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": "python -m pytest -q"},
            "tool_response": {"stdout": "", "stderr": saida}}


def _casa(tmp_path: Path, nome: str, corpo: str, licao: str = "") -> Path:
    (tmp_path / "armadilhas").mkdir(exist_ok=True)
    (tmp_path / "armadilhas" / nome).write_text(corpo, encoding="utf-8")
    numero = nome.split("-")[0]
    gatilhos = {"gatilhos": ([{"armadilha": numero, "arquivo": f"armadilhas/{nome}",
                               "caminho": "x/*", "licao": licao}] if licao else [])}
    (tmp_path / "armadilhas" / "GATILHOS.json").write_text(
        json.dumps(gatilhos, ensure_ascii=False), encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# (a) casou ⇒ a lição e as seções vêm juntas, dentro do teto
# ---------------------------------------------------------------------------

def test_o_sino_entrega_as_secoes_da_armadilha(tmp_path: Path):
    _casa(tmp_path, "900-o-caso.md", ENTRADA_COMPLETA)
    aviso = sino.decidir(_entrada("Erro Plantado 900"),
                         _sinal("900", "armadilhas/900-o-caso.md", "Erro Plantado 900"),
                         tmp_path)
    assert aviso, "o sino não tocou no erro plantado"
    assert "Sintoma: o comando devolve" in aviso, "faltou o sintoma no retorno"
    assert "Causa: a rota nasce sem" in aviso, "faltou a causa no retorno"
    assert "Solução: devolva `JsonResponse" in aviso, "faltou a solução no retorno"
    assert "armadilhas/900-o-caso.md" in aviso, "o endereço tem de continuar na tela"


def test_a_licao_do_frontmatter_vem_antes_das_secoes(tmp_path: Path):
    _casa(tmp_path, "900-o-caso.md", ENTRADA_COMPLETA,
          licao="o número do registro se PEDE ao almoxarife, nunca se escolhe.")
    aviso = sino.decidir(_entrada("Erro Plantado 900"),
                         _sinal("900", "armadilhas/900-o-caso.md", "Erro Plantado 900"),
                         tmp_path)
    assert "Lição: o número do registro se PEDE" in aviso
    assert aviso.index("Lição:") < aviso.index("Sintoma:"), (
        "a lição é a frase que salva a rodada: ela vem primeiro")


def test_o_sino_le_secoes_escritas_como_titulo(tmp_path: Path):
    """Os nomes variam no catálogo: 327 entradas usam negrito, 20 usam `## `."""
    _casa(tmp_path, "901-titulos.md", ENTRADA_EM_TITULOS)
    aviso = sino.decidir(_entrada("Erro Plantado 901"),
                         _sinal("901", "armadilhas/901-titulos.md", "Erro Plantado 901"),
                         tmp_path)
    assert "Sintoma: O comando devolve" in aviso
    assert "Solução: Troque o decorador" in aviso, "`## Como se cura` é cura"
    assert "este parágrafo continua sendo cura" in aviso, (
        "sub-etiqueta em negrito não pode truncar a seção de título que a contém")


def test_negrito_no_meio_da_frase_nao_corta_a_secao(tmp_path: Path):
    """Achado ao ver o sino tocar de verdade na armadilhas/179, 06/09/2026.

    Ela escreve `**Sintoma.** … e ele volta com` e a linha seguinte começa em
    `**três** checks vermelhos`. Ler esse negrito como etiqueta entregava meia
    frase: etiqueta fecha com `:` ou `.`, ênfase não fecha com nada.
    """
    corpo = (
        "# o caso 905\n\n"
        "**Sintoma.** O PR fica verde na sua máquina e volta com\n"
        "**três** checks vermelhos, e o `Erro Plantado 905` está no log.\n\n"
        "**Solução.** Peça o número ao almoxarife.\n"
    )
    _casa(tmp_path, "905-negrito.md", corpo)
    aviso = sino.decidir(_entrada("Erro Plantado 905"),
                         _sinal("905", "armadilhas/905-negrito.md", "Erro Plantado 905"),
                         tmp_path)
    assert "checks vermelhos" in aviso, "o negrito de ênfase cortou o sintoma ao meio"
    assert "Solução: Peça o número" in aviso, "a etiqueta de verdade parou de abrir seção"


def test_o_resumo_respeita_o_teto_e_diz_onde_esta_o_resto(tmp_path: Path):
    longa = "---\narmadilha: 902\n---\n\n# longa\n\n**Sintoma:** " + (
        "uma frase que se repete para estourar o teto. " * 200)
    _casa(tmp_path, "902-longa.md", longa)
    aviso = sino.decidir(_entrada("Erro Plantado 902"),
                         _sinal("902", "armadilhas/902-longa.md", "Erro Plantado 902"),
                         tmp_path)
    resumo = aviso.split("Sintoma:", 1)[1]
    assert len(resumo) <= sino.TETO_DO_RESUMO, (
        f"o resumo passou do teto de {sino.TETO_DO_RESUMO}: {len(resumo)}")
    assert "… o resto em armadilhas/902-longa.md" in aviso, (
        "cortado sem dizer onde está o resto é pior que não cortar")
    assert aviso.rstrip().endswith("902-longa.md"), "o corte não fechou o parágrafo"


def test_nenhuma_entrada_do_catalogo_real_estoura_o_teto():
    """Prova de fora: o teto vale para as 306 assinaturas que existem hoje."""
    licoes = sino.licoes_por_armadilha()
    for assinatura in sino.carregar_sinais():
        resumo = sino.resumo_da_armadilha(
            sino.RAIZ / assinatura["arquivo"], assinatura["arquivo"],
            licoes.get(assinatura["armadilha"], ""))
        assert len(resumo) <= sino.TETO_DO_RESUMO, (
            f"{assinatura['arquivo']} entregou {len(resumo)} caracteres")


def test_o_catalogo_real_quase_todo_tem_o_que_ensinar():
    """Se a leitura de seções parar de casar os nomes reais, isto cai."""
    com_resumo = sum(
        1 for a in sino.carregar_sinais()
        if sino.resumo_da_armadilha(sino.RAIZ / a["arquivo"], a["arquivo"])
    )
    total = len(sino.carregar_sinais())
    assert com_resumo >= int(total * 0.9), (
        f"só {com_resumo} de {total} assinaturas rendem lição: as rubricas mudaram")


# ---------------------------------------------------------------------------
# (b) segunda vez na mesma sessão ⇒ só o endereço
# ---------------------------------------------------------------------------

def test_a_segunda_vez_na_sessao_volta_a_ser_so_o_endereco(tmp_path: Path):
    _casa(tmp_path, "900-o-caso.md", ENTRADA_COMPLETA)
    entrada = _entrada("Erro Plantado 900")
    sinais = _sinal("900", "armadilhas/900-o-caso.md", "Erro Plantado 900")

    primeiro, ensinadas = sino.avaliar(entrada, sinais, tmp_path, set())
    assert ensinadas == ["900"], "o sino não anotou o que ensinou"
    assert "Sintoma:" in primeiro

    segundo, de_novo = sino.avaliar(entrada, sinais, tmp_path, {"900"})
    assert de_novo == [], "ensinar duas vezes a mesma coisa é a conta cara de volta"
    assert "Sintoma:" not in segundo, "repetiu a lição inteira"
    assert "LEIA armadilhas/900-o-caso.md" in segundo, "sumiu o endereço"
    assert len(segundo.splitlines()) <= 3, "o segundo aviso tem de caber em poucas linhas"


def test_a_memoria_da_sessao_e_o_caderninho_da_licao_do_caminho():
    """Uma verdade só sobre o mesmo fato: o mesmo `ci/telemetria.py`."""
    import licao_do_caminho

    assert sino.telemetria is licao_do_caminho.telemetria, (
        "estado de sessão em dois lugares vira duas verdades")
    assert sino.EVENTO_ENSINOU != licao_do_caminho.EVENTO, (
        "os dois eventos moram no mesmo caderninho: nomes iguais se confundiriam")


# ---------------------------------------------------------------------------
# (c) entrada sem as seções ⇒ a lição, ou só o endereço, sem quebrar
# ---------------------------------------------------------------------------

def test_entrada_sem_secoes_e_sem_licao_volta_ao_endereco(tmp_path: Path):
    _casa(tmp_path, "903-sem-secoes.md", ENTRADA_SEM_SECOES)
    aviso, ensinadas = sino.avaliar(
        _entrada("Erro Plantado 903"),
        _sinal("903", "armadilhas/903-sem-secoes.md", "Erro Plantado 903"),
        tmp_path, set())
    assert aviso and "LEIA armadilhas/903-sem-secoes.md ANTES" in aviso
    assert ensinadas == [], "não havia lição: nada a anotar como ensinado"


def test_entrada_sem_secoes_mas_com_licao_entrega_a_licao(tmp_path: Path):
    _casa(tmp_path, "903-sem-secoes.md", ENTRADA_SEM_SECOES,
          licao="rode `python ci/reservar.py numero registro` antes de nomear.")
    aviso = sino.decidir(_entrada("Erro Plantado 903"),
                         _sinal("903", "armadilhas/903-sem-secoes.md", "Erro Plantado 903"),
                         tmp_path)
    assert "Lição: rode `python ci/reservar.py" in aviso
    assert "Sintoma:" not in aviso, "inventou seção que a entrada não tem"


# ---------------------------------------------------------------------------
# (d) arquivo ausente, catálogo quebrado ⇒ o comportamento de antes
# ---------------------------------------------------------------------------

def test_arquivo_da_armadilha_ausente_volta_ao_comportamento_de_antes(tmp_path: Path):
    (tmp_path / "armadilhas").mkdir()
    aviso = sino.decidir(_entrada("Erro Plantado 904"),
                         _sinal("904", "armadilhas/904-nao-existe.md", "Erro Plantado 904"),
                         tmp_path)
    assert aviso, "sumiu o aviso: fail-open é voltar ao endereço, nunca calar"
    assert "LEIA armadilhas/904-nao-existe.md ANTES" in aviso


def test_gatilhos_corrompido_nao_derruba_o_sino(tmp_path: Path):
    _casa(tmp_path, "900-o-caso.md", ENTRADA_COMPLETA)
    (tmp_path / "armadilhas" / "GATILHOS.json").write_text("{ isto não é json",
                                                           encoding="utf-8")
    aviso = sino.decidir(_entrada("Erro Plantado 900"),
                         _sinal("900", "armadilhas/900-o-caso.md", "Erro Plantado 900"),
                         tmp_path)
    assert aviso and "Sintoma: o comando devolve" in aviso, (
        "JSON quebrado tirou a lição junto: as seções não dependem dele")


@pytest.mark.parametrize("nome", ["", "Origem:", "Quem faz valer:", "Parente próximo"])
def test_rubrica_que_nao_e_sintoma_nem_cura_nao_vira_licao(nome: str):
    assert sino.familia_da_rubrica(nome) is None, f"{nome!r} não é sintoma nem cura"


@pytest.mark.parametrize("nome,rotulo", [
    ("Sintoma:", "Sintoma"),
    ("sintoma", "Sintoma"),
    ("4.2 Sintoma", "Sintoma"),
    ("O que estava acontecendo", "Sintoma"),
    ("Causa:", "Causa"),
    ("Solução.", "Solução"),
    ("Solução — três, e as três valem juntas:", "Solução"),
    ("Como se cura", "Solução"),
    ("O que fazer quando isto acontecer", "Solução"),
])
def test_os_nomes_reais_das_rubricas_sao_reconhecidos(nome: str, rotulo: str):
    assert sino.familia_da_rubrica(nome) == rotulo


# ---------------------------------------------------------------------------
# O sino COMO PROCESSO (armadilhas/176, lição 2): decidir calar e quebrar ao
# falar são indistinguíveis por dentro de um hook fail-open.
# ---------------------------------------------------------------------------

def _rodar(entrada: dict) -> dict | None:
    proc = subprocess.run(
        [sys.executable, str(SINO)], input=json.dumps(entrada, ensure_ascii=False),
        capture_output=True, text=True, timeout=120, encoding="utf-8", errors="replace",
    )
    assert proc.returncode == 0, f"o sino recusou: {proc.stderr}"
    return json.loads(proc.stdout) if proc.stdout.strip() else None


def test_o_processo_entrega_a_licao_e_nao_repete_na_mesma_sessao(tmp_path: Path):
    """Fim a fim, com o catálogo REAL e o caderninho REAL da sessão."""
    (tmp_path / ".git").mkdir()
    entrada = {
        "tool_name": "Bash", "cwd": str(tmp_path),
        "session_id": "teste-do-sino-que-ensina",
        "tool_input": {"command": "python -m pytest -q"},
        "tool_response": {"stderr":
                          "ConfigError: Schema for status 201 is not set in response"},
    }
    primeiro = _rodar(entrada)
    assert primeiro is not None, "stdout vazio: o sino quebrou ao falar (armadilhas/176)"
    texto = primeiro["hookSpecificOutput"]["additionalContext"]
    assert "Solução:" in texto, "o processo não entregou a cura, só o endereço"
    assert "armadilhas/021" in texto

    segundo = _rodar(entrada)
    repetido = segundo["hookSpecificOutput"]["additionalContext"]
    assert "Solução:" not in repetido, (
        "a mesma armadilha foi ensinada duas vezes na mesma sessão")
    assert "LEIA armadilhas/021" in repetido

    outra_sessao = _rodar({**entrada, "session_id": "outra-sessao-do-sino"})
    assert "Solução:" in outra_sessao["hookSpecificOutput"]["additionalContext"], (
        "a memória vazou entre sessões: cada sessão aprende de novo")
