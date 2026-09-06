"""Guardas do preço da conversa (ci/preco_da_conversa.py).

O gancho mede o preço da conversa em curso e fala UMA VEZ por patamar, pelo
PostToolUse. Contrato: exit 0 SEMPRE (é conselho, não muralha), e o texto sai em
`hookSpecificOutput.additionalContext` — aninhado, porque no topo do JSON o
harness ignora EM SILÊNCIO, que é o falso-verde perfeito.

Os três testes que importam de verdade:

  · o aninhamento do canal (sem ele o gancho parece funcionar e não fala com
    ninguém);
  · o fail-open em toda entrada estragada (um conselho que trava a sessão é
    pior que conselho nenhum);
  · a leitura incremental não perder nem contar duas vezes o que já leu — é
    ela que torna o gancho barato o bastante para rodar a cada comando.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ_DO_REPO = Path(__file__).resolve().parents[2]
GANCHO = RAIZ_DO_REPO / "ci" / "preco_da_conversa.py"
FIACAO = RAIZ_DO_REPO / ".claude" / "settings.json"

sys.path.insert(0, str(RAIZ_DO_REPO / "ci"))
import preco_da_conversa as modulo  # noqa: E402


def linha_de_uso(tokens: int) -> str:
    return json.dumps(
        {"message": {"role": "assistant", "usage": {"cache_read_input_tokens": tokens}}}
    )


def linha_de_ferramenta(nome: str = "Bash") -> str:
    return json.dumps(
        {"message": {"role": "assistant", "content": [{"type": "tool_use", "name": nome}]}}
    )


def rodar(transcript: Path):
    dados = {
        "hook_event_name": "PostToolUse",
        "transcript_path": str(transcript),
        "tool_name": "Bash",
    }
    return subprocess.run(
        [sys.executable, str(GANCHO)],
        input=json.dumps(dados), capture_output=True, text=True,
        encoding="utf-8", timeout=60,
    )


@pytest.fixture()
def transcript(tmp_path: Path):
    return tmp_path / "sessao.jsonl"


def falou(resultado) -> str | None:
    """O texto que chegou ao robô, ou None. Só conta se vier ANINHADO."""
    if not resultado.stdout.strip():
        return None
    dados = json.loads(resultado.stdout)
    assert "additionalContext" not in dados, (
        "additionalContext no TOPO do JSON é ignorado em silêncio pelo harness: "
        "o gancho pareceria funcionar e nunca falaria com ninguém."
    )
    return (dados.get("hookSpecificOutput") or {}).get("additionalContext")


# ---------- o canal ----------


def test_conversa_barata_nao_fala(transcript, tmp_path):
    transcript.write_text(linha_de_uso(80_000) + "\n", encoding="utf-8")
    r = rodar(transcript)
    assert r.returncode == 0
    assert falou(r) is None


def test_passou_de_300k_fala_pelo_canal_aninhado(transcript):
    transcript.write_text(linha_de_uso(320_000) + "\n", encoding="utf-8")
    r = rodar(transcript)
    assert r.returncode == 0
    texto = falou(r)
    assert texto and "320k" in texto
    assert "conversa nova" in texto


def test_o_aviso_manda_falar_com_o_mantenedor_e_nao_fechar_nada(transcript):
    transcript.write_text(linha_de_uso(340_000) + "\n", encoding="utf-8")
    texto = falou(rodar(transcript))
    assert "mantenedor" in texto
    assert "não feche nada por conta própria" in texto.lower()


def test_o_aviso_de_lote_nunca_manda_fazer_menos(transcript):
    """A lei 'feito completo' vale para este gancho também: ele manda repartir,
    nunca encolher. A palavra que sobrava aqui já custou caro a este projeto."""
    transcript.write_text(
        "".join(linha_de_ferramenta() + "\n" for _ in range(modulo.CHAMADAS_SEM_DESPACHAR)),
        encoding="utf-8",
    )
    texto = falou(rodar(transcript))
    assert texto and "NÃO é fazer menos" in texto
    assert "sub-agente" in texto


def test_quem_ja_despachou_nao_ouve_o_aviso_de_lote(transcript):
    linhas = [linha_de_ferramenta() for _ in range(modulo.CHAMADAS_SEM_DESPACHAR)]
    linhas.append(linha_de_ferramenta("Agent"))
    transcript.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    assert falou(rodar(transcript)) is None


# ---------- uma vez por patamar ----------


def test_fala_uma_vez_por_patamar(transcript):
    transcript.write_text(linha_de_uso(310_000) + "\n", encoding="utf-8")
    assert falou(rodar(transcript)) is not None
    assert falou(rodar(transcript)) is None, "repetiu o mesmo patamar"

    with open(transcript, "a", encoding="utf-8") as fh:
        fh.write(linha_de_uso(520_000) + "\n")
    texto = falou(rodar(transcript))
    assert texto is not None and "520k" in texto, "patamar novo tem de falar"


def test_conversa_que_ja_nasce_altissima_fala_uma_vez_so(transcript):
    """O defeito que a prova de fora pegou (06/09/2026): uma conversa retomada
    em 967k cruza os TRÊS patamares de uma vez. Marcando só o mais alto, a
    chamada seguinte encontrava o de baixo por dizer e avisava de novo — a cada
    comando, para sempre. Aviso repetido é aviso ignorado."""
    transcript.write_text(linha_de_uso(967_000) + "\n", encoding="utf-8")
    assert falou(rodar(transcript)) is not None
    assert falou(rodar(transcript)) is None, "repetiu num patamar mais baixo"
    assert falou(rodar(transcript)) is None


def test_conversas_diferentes_nao_se_calam_uma_a_outra(transcript, tmp_path):
    """O estado mora ao lado do transcript, então cada conversa tem o seu."""
    transcript.write_text(linha_de_uso(310_000) + "\n", encoding="utf-8")
    assert falou(rodar(transcript)) is not None
    outro = tmp_path / "outra.jsonl"
    outro.write_text(linha_de_uso(310_000) + "\n", encoding="utf-8")
    assert falou(rodar(outro)) is not None


# ---------- a leitura incremental ----------


def test_leitura_incremental_nao_conta_duas_vezes(transcript):
    """O gancho roda a cada ferramenta; reler o arquivo inteiro pagaria em I/O
    o que economiza em tokens. Ler duas vezes o mesmo pedaço faria o contador de
    chamadas disparar o aviso de lote cedo demais."""
    metade = modulo.CHAMADAS_SEM_DESPACHAR // 2
    transcript.write_text(
        "".join(linha_de_ferramenta() + "\n" for _ in range(metade)), encoding="utf-8"
    )
    assert falou(rodar(transcript)) is None
    assert falou(rodar(transcript)) is None, "recontou o que já tinha lido"

    with open(transcript, "a", encoding="utf-8") as fh:
        for _ in range(metade):
            fh.write(linha_de_ferramenta() + "\n")
    assert falou(rodar(transcript)) is not None


def test_transcript_que_encolheu_recomeca_do_zero(transcript, tmp_path):
    """Compactação ou sessão retomada deixam o transcript menor que o offset
    guardado. Sem este ramo o gancho ficaria mudo para sempre naquela sessão."""
    transcript.write_text(
        "".join(linha_de_ferramenta() + "\n" for _ in range(20)), encoding="utf-8"
    )
    rodar(transcript)
    transcript.write_text(linha_de_uso(360_000) + "\n", encoding="utf-8")
    assert falou(rodar(transcript)) is not None


# ---------- fail-open ----------


@pytest.mark.parametrize(
    "entrada",
    ["", "isto não é json", "[]", "null", json.dumps({"transcript_path": "/nao/existe"})],
)
def test_entrada_estragada_e_silencio_e_exit_zero(entrada):
    r = subprocess.run(
        [sys.executable, str(GANCHO)],
        input=entrada, capture_output=True, text=True, encoding="utf-8", timeout=60,
    )
    assert r.returncode == 0, "conselho que trava a sessão é pior que conselho nenhum"
    assert not r.stdout.strip()


def test_transcript_com_linha_quebrada_no_meio_nao_derruba(transcript):
    transcript.write_text(
        "{lixo que não fecha\n" + linha_de_uso(330_000) + "\n", encoding="utf-8"
    )
    r = rodar(transcript)
    assert r.returncode == 0
    assert falou(r) is not None, "uma linha podre não pode cegar o gancho"


# ---------- a fiação ----------


def test_o_gancho_esta_ligado_no_settings():
    """Gancho que ninguém chama é lei sem mecanismo com outro nome — que é
    exatamente a doença que este arquivo veio curar."""
    fiacao = json.loads(FIACAO.read_text(encoding="utf-8"))
    comandos = [
        h.get("command", "")
        for grupo in fiacao["hooks"].get("PostToolUse", [])
        for h in grupo.get("hooks", [])
    ]
    assert any("preco_da_conversa.py" in c for c in comandos), (
        "o gancho existe mas não está ligado no PostToolUse de .claude/settings.json"
    )
