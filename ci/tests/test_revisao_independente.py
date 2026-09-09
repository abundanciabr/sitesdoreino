"""Prova do atestado independente e da ligação ao commit final."""
import json
import pytest
import revisor_de_pouso as revisor
import mergear
from _nucleo import Estado

SHA = "a" * 40
MARCA = "<!-- revisao-independente:v1 -->"

def comentario(**mudancas):
    dados = dict(sha=SHA, despacho="despacho-1", revisor="revisor-2",
                 maestro="maestro-3", veredito="APROVADO",
                 resumo="Diff e guardas conferidos sem achados pendentes.",
                 evidencia="Tarefa revisor-2, avaliação final conferida pela maestro.")
    dados.update(mudancas)
    return dict(id=1, author_association="OWNER", body=MARCA + "\n" + json.dumps(dados))

def avaliar(comentarios, sha=SHA):
    return revisor.avaliar_atestado(sha, comentarios)

def test_aprovacao_real_do_sha_passa():
    assert avaliar([comentario()]).estado is Estado.PASS

@pytest.mark.parametrize("comentarios,sha", [
    ([], SHA), ([comentario()], "b" * 40),
    ([comentario(veredito="REPROVADO")], SHA),
    ([comentario(revisor="despacho-1")], SHA),
    ([comentario(revisor="maestro-3")], SHA),
    ([comentario(evidencia="")], SHA),
    ([comentario(sha="abc")], "abc"),
    ([dict(comentario(), author_association="NONE")], SHA),
    ([dict(comentario(), body=MARCA + "\n{}")], SHA),
    ([dict(comentario(), body=MARCA + "\n{")], SHA),
])
def test_ausencia_novo_sha_e_evidencia_invalida_recusam(comentarios, sha):
    assert avaliar(comentarios, sha).estado is Estado.FAIL

def test_ultimo_atestado_confiavel_prevalece_inclusive_invalido():
    ultimo = dict(comentario(), id=2, body=MARCA + "\n{")
    assert avaliar([ultimo, comentario()]).estado is Estado.FAIL

def test_comentario_externo_nao_revoga_atestado_da_maestro():
    externo = dict(comentario(veredito="REPROVADO"), id=2, author_association="NONE")
    assert avaliar([comentario(), externo]).estado is Estado.PASS

def test_comando_merge_amarra_sha_conferido():
    comando = mergear.comando_de_merge(99, "merge", SHA)
    assert comando[comando.index("--match-head-commit") + 1] == SHA

def test_conferir_invoca_portao_de_revisao(monkeypatch, tmp_path):
    monkeypatch.setattr(mergear, "carregar_pr", lambda *a: {"number":99, "headRefOid":SHA})
    for nome in ("checar_estado", "checar_mergeabilidade", "checar_registro_embarcado", "checar_frescor_do_livro", "checar_divida_do_livro"):
        monkeypatch.setattr(mergear, nome, lambda *a: mergear.Resultado("outro", Estado.PASS, "verde"))
    for nome in ("checar_checks", "checar_labels", "checar_dependencias"):
        monkeypatch.setattr(mergear, nome, lambda *a: [])
    monkeypatch.setattr(mergear, "checar_publicacoes_anteriores", lambda *a: [])
    monkeypatch.setattr(mergear, "checar_revisao_independente", lambda *a: avaliar([]))
    relatorio, _ = mergear.conferir(99, tmp_path)
    assert relatorio.estado is Estado.FAIL
    assert "REVISAO-NECESSARIA" in mergear.motivos_da_recusa(relatorio)


def test_conferir_exige_publicacao_anterior_mesmo_com_revisao_aprovada(monkeypatch,tmp_path):
    monkeypatch.setattr(mergear, "carregar_pr", lambda *a: {"number":99,"headRefOid":SHA})
    for nome in ("checar_estado", "checar_mergeabilidade", "checar_registro_embarcado", "checar_frescor_do_livro", "checar_divida_do_livro"):
        monkeypatch.setattr(mergear,nome,lambda *a: mergear.Resultado("outro",Estado.PASS,"verde"))
    for nome in ("checar_checks","checar_labels","checar_dependencias"):
        monkeypatch.setattr(mergear,nome,lambda *a: [])
    monkeypatch.setattr(mergear,"checar_revisao_independente",lambda *a: avaliar([comentario()]))
    monkeypatch.setattr(mergear,"checar_publicacoes_anteriores",lambda *a: [mergear.Resultado("publicação anterior",Estado.FAIL,"run reprovado")])
    relatorio,_=mergear.conferir(99,tmp_path)
    assert relatorio.estado is Estado.FAIL
    assert any(r.resumo == "run reprovado" for r in relatorio.resultados)
