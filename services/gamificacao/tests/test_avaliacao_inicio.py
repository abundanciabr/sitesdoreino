"""Casos em que uma avaliação incorreta poderia liberar faixa sem exame."""

import importlib.util
import json
import hashlib
from pathlib import Path
import struct
from types import SimpleNamespace

import pytest


ARQUIVO = Path(__file__).parents[1] / "apps" / "gamificacao" / "avaliacao_inicio.py"
spec = importlib.util.spec_from_file_location("avaliacao_inicio_testada", ARQUIVO)
avaliacao = importlib.util.module_from_spec(spec)
spec.loader.exec_module(avaliacao)


def dados(ordem=3, **extras):
    return {"chave": "tentativa-1", "ordem": ordem, "caminho": "ugc",
            "item_nome": "Boné", "item_acao": "Mudei a cor da aba para azul.",
            "explicacao": "Quero usar o boné no avatar.", "parte": "aba", **extras}


def anexo(nome="bone.png", identidade="1"):
    return SimpleNamespace(pk=identidade, nome=nome, conteudo=b"imagem", sha256=f"hash-{identidade}",
                           pessoa_id=10, site_id="site")


def responder(resultado="reconhecida", observacoes=None):
    return json.dumps({"resultado": resultado,
        "feedback": "A aba do boné ficou azul na nova versão apresentada.",
        "observacoes": observacoes or [{"fonte": "relato", "observacao": "O aluno relatou ter mudado a cor da aba do boné."}]})


def test_relato_azul_sem_objeto_pode_ser_avaliado(monkeypatch):
    monkeypatch.setattr(avaliacao, "_modelo", lambda *args: responder())
    saida = avaliacao.avaliar(10, "site", 3, dados())
    assert saida["resultado"] == "reconhecida"
    assert saida["evidencia"]["anexos"] == []
    assert saida["evidencia"]["chave"] == "tentativa-1"


def test_resposta_malformada_falha_sem_recompensa(monkeypatch):
    monkeypatch.setattr(avaliacao, "_modelo", lambda *args: '{"resultado":"reconhecida"}')
    assert avaliacao.avaliar(10, "site", 3, dados())["resultado"] == "falha"


def test_vermelha_precisa_imagem_examinada(monkeypatch):
    assert avaliacao.avaliar(10, "site", 4, dados(4))["resultado"] == "incompleta"
    assert avaliacao.avaliar(10, "site", 4, dados(4), [anexo("bone.glb")])["resultado"] == "falha"
    monkeypatch.setattr(avaliacao, "_imagem", lambda _: (b"png", {"largura_px": 8, "altura_px": 8}))
    monkeypatch.setattr(avaliacao, "_modelo", lambda *args: responder())
    assert avaliacao.avaliar(10, "site", 4, dados(4), [anexo()])["resultado"] == "falha"


def test_vermelha_avalia_apresentacao_sem_exigir_versao_anterior(monkeypatch):
    chamada = {}
    monkeypatch.setattr(avaliacao, "_imagem", lambda _: (b"png", {"largura_px": 800, "altura_px": 600}))
    def modelo(instrucoes, conteudo):
        chamada["instrucoes"] = instrucoes
        chamada["pedido"] = json.loads(conteudo[0]["text"])
        return responder(observacoes=[{"fonte": "1", "observacao":
            "A imagem apresenta boné com aba azul e copa arredondada."}])
    monkeypatch.setattr(avaliacao, "_modelo", modelo)
    saida = avaliacao.avaliar(10, "site", 4, dados(4), [anexo()])
    assert saida["resultado"] == "reconhecida"
    assert len(chamada["pedido"]["imagens"]) == 1
    assert "não exija imagem anterior" in chamada["pedido"]["criterio"]
    assert "sem tratar a apresentação correspondente como incompleta" in chamada["pedido"]["criterio"]
    assert "Somente nas etapas de comparação (5, 6 e 7" in chamada["instrucoes"]
    assert "Compare duas versões" in avaliacao._criterio(5, "ugc")
    assert "Compare duas versões" in avaliacao._criterio(6, "ugc")


def test_glb_le_geometria_real_e_nao_afirma_aparencia(monkeypatch):
    vertices = struct.pack("<9f", 0, 0, 0, 1, 0, 0, 0, 1, 0)
    documento = {"asset": {"version": "2.0"}, "buffers": [{"byteLength": len(vertices)}],
        "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(vertices)}],
        "accessors": [{"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3"}],
        "meshes": [{"name": "Bone", "primitives": [{"attributes": {"POSITION": 0}}]}]}
    js = json.dumps(documento).encode()
    js += b" " * (-len(js) % 4)
    glb = (struct.pack("<4sII", b"glTF", 2, 12+8+len(js)+8+len(vertices)) +
           struct.pack("<I4s", len(js), b"JSON") + js +
           struct.pack("<I4s", len(vertices), b"BIN\x00") + vertices)
    arquivo = SimpleNamespace(pk="3", nome="modelo.glb", conteudo=glb,
        sha256=hashlib.sha256(glb).hexdigest(), pessoa_id=10, site_id="site")
    fatos = avaliacao._modelo_estrutural(arquivo)
    assert fatos["limites_xyz_amostrados"] == [[0.0, 1.0], [0.0, 1.0], [0.0, 0.0]]
    assert "sem renderização" in fatos["limite_do_exame"]
    monkeypatch.setattr(avaliacao, "_modelo", lambda *args: responder(observacoes=[
        {"fonte": "3", "observacao": "A malha possui três vértices e uma face triangular."}]))
    assert avaliacao.avaliar(10, "site", 4, dados(4), [arquivo])["resultado"] == "reconhecida"


def test_aprender_confere_registro_servidor_ou_duas_imagens(monkeypatch):
    fatos = [{"tipo": "cor", "parte": "aba", "antes": "vermelha",
              "depois": "azul", "fonte": "tentativa-42"}]
    d = {**dados(7), "caminho": "aprender", "registro_alteracoes": fatos}
    monkeypatch.setattr(avaliacao, "_modelo", lambda *args: responder(observacoes=[
        {"fonte": "registro:0", "observacao": "A prática registra a aba vermelha antes e azul depois."}]))
    saida = avaliacao.avaliar(10, "site", 7, d)
    assert saida["resultado"] == "reconhecida"
    assert saida["evidencia"]["registros_pratica"][0]["fonte"] == "tentativa-42"

    sem_registro = {**d, "registro_alteracoes": []}
    assert avaliacao.avaliar(10, "site", 7, sem_registro)["resultado"] == "incompleta"
    imagens = [anexo("antes.png", "1"), anexo("final.png", "2")]
    monkeypatch.setattr(avaliacao, "_imagem", lambda _: (b"png", {"largura_px": 8, "altura_px": 8}))
    sem_registro.update(anexo_anterior_id="1", anexo_final_id="2")
    monkeypatch.setattr(avaliacao, "_modelo", lambda *args: responder(observacoes=[
        {"fonte": "1", "observacao": "A aba era vermelha na imagem anterior."},
        {"fonte": "2", "observacao": "A aba é azul na imagem final."}]))
    assert avaliacao.avaliar(10, "site", 7, sem_registro, imagens)["resultado"] == "reconhecida"


def test_aprender_nao_reconhece_so_relato_quando_ha_registro(monkeypatch):
    d = {**dados(7), "caminho": "aprender", "registro_alteracoes": [
        {"tipo": "cor", "parte": "aba", "antes": "vermelha", "depois": "azul", "fonte": "tentativa-42"}]}
    monkeypatch.setattr(avaliacao, "_modelo", lambda *args: responder())
    assert avaliacao.avaliar(10, "site", 7, d)["resultado"] == "falha"


def test_aprender_preserva_zero_como_valor_anterior(monkeypatch):
    d = {**dados(7), "caminho": "aprender", "registro_alteracoes": [
        {"tipo": "proporcao", "parte": "aba", "antes": 0, "depois": 1, "fonte": "tentativa-43"}]}
    monkeypatch.setattr(avaliacao, "_modelo", lambda *args: responder(observacoes=[
        {"fonte": "registro:0", "observacao": "A prática registrou a proporção da aba de zero para um."}]))
    saida = avaliacao.avaliar(10, "site", 7, d)
    assert saida["resultado"] == "reconhecida"
    assert saida["evidencia"]["registros_pratica"][0]["antes"] == "0"


@pytest.mark.parametrize("nome,conteudo", [
    ("bone.obj", b"o bone\nv 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n"),
    ("bone.stl", b"solid bone\nfacet normal 0 0 1\nouter loop\nvertex 0 0 0\nvertex 1 0 0\nvertex 0 1 0\nendloop\nendfacet\nendsolid\n"),
])
def test_obj_e_stl_abrem_geometria_sem_inferir_cor(nome, conteudo):
    arquivo = SimpleNamespace(nome=nome, conteudo=conteudo,
        sha256=hashlib.sha256(conteudo).hexdigest())
    fatos = avaliacao._modelo_estrutural(arquivo)
    assert fatos["faces_estimadas"] == 1
    assert fatos["limites_xyz_amostrados"] == [[0.0, 1.0], [0.0, 1.0], [0.0, 0.0]]
    assert "cor" not in fatos


def test_modelo_falsamente_renomeado_falha():
    conteudo = b"nao e malha"
    arquivo = SimpleNamespace(pk="9", nome="bone.obj", conteudo=conteudo,
        sha256=hashlib.sha256(conteudo).hexdigest(), pessoa_id=10, site_id="site")
    assert avaliacao.avaliar(10, "site", 4, dados(4), [arquivo])["resultado"] == "falha"


def test_comparacao_exige_duas_fontes_e_diferenca(monkeypatch):
    monkeypatch.setattr(avaliacao, "_imagem", lambda _: (b"png", {"largura_px": 8, "altura_px": 8}))
    assert avaliacao.avaliar(10, "site", 5, dados(5), [anexo()])["resultado"] == "incompleta"
    imagens = [anexo("antes.png", "1"), anexo("depois.png", "2")]
    monkeypatch.setattr(avaliacao, "_modelo", lambda *args: responder(observacoes=[
        {"fonte": "1", "observacao": "A aba parecia vermelha na versão anterior."}]))
    assert avaliacao.avaliar(10, "site", 5, dados(5), imagens)["resultado"] == "falha"
    monkeypatch.setattr(avaliacao, "_modelo", lambda *args: responder(observacoes=[
        {"fonte": "1", "observacao": "A aba parecia vermelha na versão anterior."},
        {"fonte": "2", "observacao": "A aba aparece azul na versão atual."}]))
    assert avaliacao.avaliar(10, "site", 5, dados(5), imagens)["resultado"] == "reconhecida"


def test_proporcao_pede_aumento_e_rotula_versoes(monkeypatch):
    chamadas = []
    monkeypatch.setattr(avaliacao, "_imagem", lambda _: (b"png", {"largura_px": 8, "altura_px": 8}))
    def modelo(instrucoes, conteudo):
        chamadas.append((instrucoes, conteudo))
        return responder(observacoes=[
            {"fonte": "1", "observacao": "A aba ocupava menos da largura do boné antes."},
            {"fonte": "2", "observacao": "A aba ocupa mais da largura do boné depois."}])
    monkeypatch.setattr(avaliacao, "_modelo", modelo)
    saida = avaliacao.avaliar(10, "site", 6, dados(6), [anexo("antes.png", "1"), anexo("depois.png", "2")])
    assert saida["resultado"] == "reconhecida"
    assert "AUMENTO" in chamadas[0][1][0]["text"]
    assert "Imagem anterior 1" in chamadas[0][1][1]["text"]
    assert "Imagem final 2" in chamadas[0][1][3]["text"]


def test_anexo_de_outro_aluno_nao_vai_ao_modelo(monkeypatch):
    monkeypatch.setattr(avaliacao, "_modelo", lambda *args: pytest.fail("não deveria chamar IA"))
    outro = anexo()
    outro.pessoa_id = 11
    assert avaliacao.avaliar(10, "site", 4, dados(4), [outro])["resultado"] == "falha"


def test_snapshot_obrigatorio():
    with pytest.raises(ValueError, match="chave"):
        avaliacao.avaliar(10, "site", 3, {**dados(), "chave": ""})
