"""Provas locais da escolha de recuperação, sem SSH nem registry reais."""
import copy
import json
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import reversao
from _nucleo import ErroDeInstrumentacao


def journal():
    aprovada = {"sha": "a" * 40, "dados": "schema-1", "configuracao": "config-1", "verificada_em": "2026-09-30T10:00:00+00:00"}
    return {"celula": "funil", "atual": "b" * 40, "candidata": "b" * 40, "publicada_em": "2026-09-30T11:00:00+00:00", "aprovada": aprovada, "anterior_aprovada": None, "compatibilidade": {"dados": "schema-1", "configuracao": "config-1"}, "recuperacao": None}


def test_candidata_nao_substitui_aprovada_antes_da_prova():
    estado = journal()
    antes = copy.deepcopy(estado)
    assert reversao.escolher_alvo(estado)["sha"] == "a" * 40
    assert estado == antes


def test_indisponivel_ja_aprovada_usa_anterior_distinta():
    estado = journal()
    estado["atual"] = estado["aprovada"]["sha"]
    estado["anterior_aprovada"] = dict(estado["aprovada"], sha="c" * 40)
    assert reversao.escolher_alvo(estado)["sha"] == "c" * 40


def test_ja_aprovada_sem_anterior_nao_disfarca_reinicio():
    estado = journal()
    estado["atual"] = estado["aprovada"]["sha"]
    with pytest.raises(ValueError, match="reiniciar"):
        reversao.escolher_alvo(estado)


@pytest.mark.parametrize("chave", ["dados", "configuracao"])
def test_incompatibilidade_interrompe_sem_restaurar_banco(chave):
    estado = journal()
    estado["compatibilidade"][chave] = "mudou"
    with pytest.raises(ValueError, match="banco não será restaurado"):
        reversao.escolher_alvo(estado)


def test_primeira_inicializacao_exige_prova():
    estado = journal()
    estado["aprovada"] = None
    with pytest.raises(ValueError, match="primeiro destino recuperável"):
        reversao.escolher_alvo(estado)


def test_aprovacao_sem_evidencia_nao_serve():
    estado = journal()
    estado["aprovada"]["verificada_em"] = ""
    with pytest.raises(ErroDeInstrumentacao, match="prova"):
        reversao.escolher_alvo(estado)


@pytest.mark.parametrize("status", ["tentando", "falhou", "concluida"])
def test_latch_impede_cascata_e_repeticao(status):
    estado = journal()
    estado["recuperacao"] = {"estado": status}
    with pytest.raises(ValueError, match="já tentada"):
        reversao.escolher_alvo(estado)


def test_vigia_seleciona_ultima_publicacao_com_horario():
    antiga = journal()
    antiga.update(celula="quiz", publicada_em="2026-09-30T10:00:00+00:00")
    assert reversao.selecionar_estado(json.dumps([antiga, journal()]))["celula"] == "funil"


def test_vigia_nao_adivinha_em_empate():
    outro = dict(journal(), celula="quiz")
    with pytest.raises(ErroDeInstrumentacao, match="incerto"):
        reversao.selecionar_estado(json.dumps([outro, journal()]))


@pytest.mark.parametrize("bruto", ["", "[]", "{}", '{"celula":"inventada"}'])
def test_journal_invalido_para_seguro(bruto):
    with pytest.raises(ErroDeInstrumentacao):
        reversao.selecionar_estado(bruto)


def test_imagem_existente_sem_aprovacao_nao_vira_plano(monkeypatch, tmp_path):
    estado = journal()
    estado["aprovada"] = None
    saida = tmp_path / "outputs"
    monkeypatch.setenv("REVERSAO_ESTADO_PUBLICACAO", json.dumps(estado))
    monkeypatch.setenv("REVERSAO_CELULA", "funil")
    monkeypatch.setenv("GITHUB_OUTPUT", str(saida))
    monkeypatch.setattr(reversao, "imagem_existe", lambda *a: pytest.fail("não consultar registry sem aprovação"))
    assert reversao.main() == 1
    assert "tag=" not in saida.read_text()


def test_registry_mudo_e_erro_nao_selecao_mais_velha(monkeypatch):
    monkeypatch.setenv("REVERSAO_ESTADO_PUBLICACAO", json.dumps(journal()))
    monkeypatch.setenv("REVERSAO_CELULA", "funil")
    def mudo(*args):
        raise ErroDeInstrumentacao("registry indisponível")
    monkeypatch.setattr(reversao, "imagem_existe", mudo)
    assert reversao.main() == 2


def test_plano_tem_atual_e_compatibilidade_para_revalidar_sob_trava(monkeypatch, tmp_path):
    saida = tmp_path / "outputs"
    monkeypatch.setenv("REVERSAO_ESTADO_PUBLICACAO", json.dumps(journal()))
    monkeypatch.setenv("REVERSAO_CELULA", "funil")
    monkeypatch.setenv("GITHUB_OUTPUT", str(saida))
    monkeypatch.setattr(reversao, "imagem_existe", lambda *a: True)
    assert reversao.main() == 0
    plano = dict(linha.split("=", 1) for linha in saida.read_text().splitlines())
    assert plano == {"celula": "funil", "tag": "a" * 40, "var_tag": "FUNIL_TAG", "atual": "b" * 40, "dados": "schema-1", "configuracao": "config-1"}


@pytest.mark.parametrize("sha", [None, 123, [], "curto"])
def test_sha_invalido_na_aprovacao_para_seguro(sha):
    estado = journal()
    estado["aprovada"]["sha"] = sha
    with pytest.raises(ValueError):
        reversao.escolher_alvo(estado)


@pytest.mark.parametrize("horario", [None, "inventado", "2026-09-30T10:00:00"])
def test_prova_sem_horario_real_com_fuso_para_seguro(horario):
    estado = journal()
    estado["aprovada"]["verificada_em"] = horario
    with pytest.raises(ErroDeInstrumentacao):
        reversao.escolher_alvo(estado)


def test_imagem_aprovada_removida_nao_emite_plano(monkeypatch, tmp_path):
    destino = tmp_path / "outputs"
    monkeypatch.setenv("REVERSAO_ESTADO_PUBLICACAO", json.dumps(journal()))
    monkeypatch.setenv("REVERSAO_CELULA", "funil")
    monkeypatch.setenv("GITHUB_OUTPUT", str(destino))
    monkeypatch.setattr(reversao, "imagem_existe", lambda *args: False)
    assert reversao.main() == 1
    assert "tag=" not in destino.read_text()


@pytest.mark.parametrize("falha", ["sem_aprovada", "incompativel", "imagem_ausente"])
def test_selecao_recusada_identifica_journal_para_latch_terminal(monkeypatch, tmp_path, falha):
    estado = journal()
    if falha == "sem_aprovada":
        estado["aprovada"] = None
    elif falha == "incompativel":
        estado["compatibilidade"]["dados"] = "mudou"
    destino = tmp_path / "outputs"
    monkeypatch.setenv("REVERSAO_ESTADO_PUBLICACAO", json.dumps(estado))
    monkeypatch.setenv("REVERSAO_CELULA", "funil")
    monkeypatch.setenv("GITHUB_OUTPUT", str(destino))
    monkeypatch.setattr(reversao, "imagem_existe", lambda *args: False)
    assert reversao.main() == 1
    assert dict(l.split("=", 1) for l in destino.read_text().splitlines()) == {"celula": "funil", "atual": "b" * 40}


@pytest.mark.parametrize("modo", ["ausente", "ambiguo"])
def test_recusa_indeterminada_persiste_terminal_global_e_segunda_chamada_bloqueia(monkeypatch, tmp_path, modo):
    import importlib.util
    spec = importlib.util.spec_from_file_location("terminal_publicacao", Path(__file__).resolve().parents[2] / "infra/publicacao-local.py")
    receptor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(receptor)
    receptor.RAIZ = tmp_path
    receptor.PASTA = tmp_path / "publicacoes"
    receptor.CELULA = ""
    monkeypatch.setattr(receptor, "comando", lambda *args: pytest.fail("não alterar runtime ao encerrar seleção"))
    estados = [] if modo == "ausente" else [journal(), dict(journal(), celula="quiz")]
    monkeypatch.setenv("REVERSAO_CELULA", "")
    monkeypatch.setenv("REVERSAO_ESTADO_PUBLICACAO", json.dumps({"publicacoes": estados, "recuperacao_global": False}))
    assert reversao.main() == 2
    receptor.executar("encerrar-recuperacao")
    terminal = receptor.PASTA / "recuperacao-terminal.json"
    gravado = terminal.read_text()
    # Simula novo tick do vigia: consulta real do arquivo de término e novos journals.
    monkeypatch.setenv("REVERSAO_ESTADO_PUBLICACAO", json.dumps({"publicacoes": estados, "recuperacao_global": terminal.exists()}))
    monkeypatch.setattr(reversao, "escolher_alvo", lambda *args: pytest.fail("não selecionar novamente após término"))
    assert reversao.main() == 2
    receptor.executar("encerrar-recuperacao")
    assert terminal.read_text() == gravado


@pytest.mark.parametrize("falha", ["sem_aprovada", "incompativel", "imagem_ausente"])
def test_recusa_conhecida_persiste_journal_e_segundo_disparo_bloqueia(monkeypatch, tmp_path, falha):
    import importlib.util
    spec = importlib.util.spec_from_file_location("terminal_publicacao_celula", Path(__file__).resolve().parents[2] / "infra/publicacao-local.py")
    receptor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(receptor)
    receptor.RAIZ = tmp_path
    receptor.PASTA = tmp_path / "publicacoes"
    receptor.PASTA.mkdir()
    receptor.CELULA = "funil"
    estado = journal()
    if falha == "sem_aprovada":
        estado["aprovada"] = None
    elif falha == "incompativel":
        estado["compatibilidade"]["dados"] = "mudou"
    caminho = receptor.PASTA / "funil.json"
    caminho.write_text(json.dumps(estado))
    monkeypatch.setenv("ATUAL_ESPERADA", estado["atual"])
    monkeypatch.setenv("REVERSAO_CELULA", "funil")
    monkeypatch.setenv("REVERSAO_ESTADO_PUBLICACAO", caminho.read_text())
    monkeypatch.setattr(reversao, "imagem_existe", lambda *args: False)
    assert reversao.main() == 1
    receptor.executar("encerrar-recuperacao")
    gravado = caminho.read_text()
    monkeypatch.setenv("REVERSAO_ESTADO_PUBLICACAO", gravado)
    monkeypatch.setattr(reversao, "imagem_existe", lambda *args: pytest.fail("sem nova consulta após término"))
    assert reversao.main() == 1
    assert "recuperacao" in json.loads(gravado)
    receptor.executar("encerrar-recuperacao")
    assert caminho.read_text() == gravado
