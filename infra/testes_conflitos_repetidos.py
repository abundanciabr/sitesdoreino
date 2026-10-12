"""Regressões com Git real: repetição, entradas novas e retomada transitória."""
import datetime
import json
from types import SimpleNamespace

import entregas
from testes_entregas import amb, sh


def test_conflito_repetido_nao_executa_git_nem_regrava_entrega(amb, monkeypatch):
    id_ = amb.entregar("rob-conf", amb.conflito())["id"]
    entregas.cmd_integrar(SimpleNamespace())
    arquivo = entregas.caminho(id_)
    antes = arquivo.read_bytes()
    git = entregas.git
    def sem_combinar(*args, **kwargs):
        assert "merge-tree" not in args and "commit-tree" not in args
        return git(*args, **kwargs)
    monkeypatch.setattr(entregas, "git", sem_combinar)
    for _ in range(8):
        _, saida = entregas.cmd_integrar(SimpleNamespace())
        assert saida["combinacoes"]["conflito_reutilizado"] == 1
    assert arquivo.read_bytes() == antes
    medicao = json.loads((entregas.pasta()/"medicoes/combinacoes.json").read_text())
    assert medicao["totais"]["conflito_reutilizado"] == 8


def test_main_nova_recombina_e_entrega_corrigida_segue(amb):
    id_ = amb.entregar("rob-conf", amb.conflito())["id"]
    entregas.cmd_integrar(SimpleNamespace())
    chave = amb.consultar(id_)["combinacao"]["chave"]
    amb.avancar_main({"outro.txt": "outra entrega legitima\n"})
    _, resultado = entregas.cmd_integrar(SimpleNamespace())
    assert resultado["combinacoes"]["merge_tree"] > 0
    assert amb.consultar(id_)["combinacao"]["chave"] != chave
    base = amb.main()
    novo = amb.ramo("rob-corrigido", {"novo.txt": "correcao\n"}, de=base)
    corrigido = amb.entregar("rob-corrigido", novo, base=base)["id"]
    entregas.cmd_integrar(SimpleNamespace())
    assert amb.consultar(corrigido)["estado"] == "pronta"
    assert amb.promover(corrigido)[0] == 0


def test_falha_transitoria_retoma_sem_mudanca_no_codigo(amb, monkeypatch):
    id_ = amb.entregar("rob-a", amb.ramo("rob-a", {"a.txt": "A\n"}))["id"]
    combinar = entregas.combinar
    chamadas = []
    def falhar_uma(reg, main):
        chamadas.append(reg["id"])
        if len(chamadas) == 1:
            raise OSError("armazenamento temporariamente indisponivel")
        return combinar(reg, main)
    monkeypatch.setattr(entregas, "combinar", falhar_uma)
    entregas.cmd_integrar(SimpleNamespace())
    entregas.cmd_integrar(SimpleNamespace())
    assert len(chamadas) == 1
    reg = entregas.ler(id_)
    reg["falha_integracao"]["tentar_depois"] = "2000-01-01T00:00:00+00:00"
    entregas.gravar(reg)
    entregas.cmd_integrar(SimpleNamespace())
    assert len(chamadas) == 2
    assert entregas.ler(id_)["estado"] == "pronta"
    assert "falha_integracao" not in entregas.ler(id_)


def test_base_dependencia_e_combinador_invalidam_conflito(amb, monkeypatch):
    id_ = amb.entregar("rob-conf", amb.conflito())["id"]
    entregas.cmd_integrar(SimpleNamespace())
    reg = entregas.ler(id_)
    chave = reg["combinacao"]["chave"]
    reg["atualizada_em"] = "outro horario"
    reg["tentativas"] += 100
    assert entregas.chave_combinacao(reg, amb.main(), {}) == chave
    monkeypatch.setattr(entregas, "COMBINADOR_VERSAO", "outra implementacao")
    assert entregas.chave_combinacao(reg, amb.main(), {}) != chave
    entregas.cmd_integrar(SimpleNamespace())
    assert entregas.ler(id_)["combinacao"]["chave"] != chave
    reg["depende_de"] = ["abcdef012345"]
    a = entregas.chave_combinacao(reg, amb.main(), {})
    assert a != entregas.chave_combinacao(reg, amb.main(), {"abcdef012345": {"estado": entregas.NA_MAIN}})
    reg["base"] = amb.main()
    assert a != entregas.chave_combinacao(reg, amb.main(), {})
