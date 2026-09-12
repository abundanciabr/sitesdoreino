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


def test_declaracao_corretiva_precisa_estar_no_atestado_revisado():
    assert revisor.avaliar_atestado(SHA,[comentario()],correcoes=[10]).estado is Estado.FAIL
    assert revisor.avaliar_atestado(SHA,[comentario(corrige_publicacao=[10])],correcoes=[10]).estado is Estado.PASS
    assert revisor.avaliar_atestado(SHA,[comentario(corrige_publicacao=[11])],correcoes=[10]).estado is Estado.FAIL


def git(raiz, *argumentos):
    import subprocess
    return subprocess.run(["git", *argumentos], cwd=raiz, check=True,
                          capture_output=True, text=True, encoding="utf-8", timeout=20).stdout.strip()


@pytest.fixture
def revisao_git(tmp_path):
    origem = tmp_path / "origem.git"
    raiz = tmp_path / "bancada"
    raiz.mkdir()
    git(tmp_path, "init", "--bare", str(origem))
    git(raiz, "init", "-b", "main")
    git(raiz, "config", "user.name", "Teste")
    git(raiz, "config", "user.email", "teste@example.com")
    git(raiz, "config", "core.autocrlf", "false")
    (raiz / "comum.txt").write_text("inicial\n", encoding="utf-8")
    git(raiz, "add", ".")
    git(raiz, "commit", "-m", "base inicial")
    git(raiz, "remote", "add", "origin", str(origem))
    git(raiz, "switch", "-c", "entrega")
    (raiz / "comum.txt").write_text("entrega revisada\n", encoding="utf-8")
    git(raiz, "commit", "-am", "codigo revisado")
    revisado = git(raiz, "rev-parse", "HEAD")
    git(raiz, "push", "origin", "main", "entrega")
    return raiz, revisado


def atualizar_base(raiz, nome="base-nova.txt"):
    git(raiz, "switch", "main")
    (raiz / nome).write_text("base atualizada\n", encoding="utf-8")
    git(raiz, "add", ".")
    git(raiz, "commit", "-m", "atualizar base")
    principal = git(raiz, "rev-parse", "HEAD")
    git(raiz, "push", "origin", "main")
    git(raiz, "switch", "entrega")
    return principal


def conferir_git(monkeypatch, raiz, revisado, comentarios=None, *, publicar=True, head=None):
    if publicar:
        git(raiz, "push", "origin", "entrega")
    comentarios = comentarios if comentarios is not None else [comentario(sha=revisado)]
    monkeypatch.setattr(mergear, "_gh", lambda *args: json.dumps([comentarios]))
    return mergear.checar_revisao_independente(raiz, {
        "number": 99, "headRefOid": head or git(raiz, "rev-parse", "HEAD")
    })


def test_composicao_limpa_preserva_atestado_original_e_bancada(monkeypatch, revisao_git):
    # guarda: ci/revisor_de_pouso.py:82
    raiz, revisado = revisao_git
    anterior = git(raiz, "rev-parse", "origin/main")
    principal = atualizar_base(raiz)
    git(raiz, "merge", "--no-edit", "main")
    head = git(raiz, "rev-parse", "HEAD")
    git(raiz, "update-ref", "refs/remotes/origin/main", anterior)
    (raiz / "trabalho-local.txt").write_bytes(b"nao alterar\r\n")
    estado = git(raiz, "status", "--porcelain")
    atestado = comentario(sha=revisado)
    original = json.dumps(atestado)
    resultado = conferir_git(monkeypatch, raiz, revisado, [atestado])
    assert resultado.estado is Estado.PASS, resultado
    assert all(sha in resultado.resumo + resultado.detalhe for sha in (revisado, head, principal))
    assert json.dumps(atestado) == original
    assert git(raiz, "rev-parse", "HEAD") == head
    assert git(raiz, "status", "--porcelain") == estado
    assert (raiz / "trabalho-local.txt").read_bytes() == b"nao alterar\r\n"


def test_cadeia_de_atualizacoes_limpas_preserva_revisao(monkeypatch, revisao_git):
    # guarda: ci/revisor_de_pouso.py:82
    raiz, revisado = revisao_git
    for nome in ("base-um.txt", "base-dois.txt"):
        atualizar_base(raiz, nome)
        git(raiz, "merge", "--no-edit", "main")
    assert conferir_git(monkeypatch, raiz, revisado).estado is Estado.PASS


@pytest.mark.parametrize("merge_posterior", [False, True])
def test_commit_administrativo_extra_tambem_exige_revisao(monkeypatch, revisao_git, merge_posterior):
    # guarda: ci/revisor_de_pouso.py:130
    raiz, revisado = revisao_git
    atualizar_base(raiz)
    git(raiz, "merge", "--no-edit", "main")
    (raiz / "painel/registros").mkdir(parents=True)
    (raiz / "painel/registros/extra.js").write_text("registro novo", encoding="utf-8")
    git(raiz, "add", ".")
    git(raiz, "commit", "-m", "recibo posterior")
    if merge_posterior:
        atualizar_base(raiz, "base-posterior.txt")
        git(raiz, "merge", "--no-edit", "main")
    resultado = conferir_git(monkeypatch, raiz, revisado)
    assert resultado.estado is Estado.FAIL
    assert "dois pais" in resultado.resumo


def test_arvore_manual_divergente_do_merge_limpo_recusa(monkeypatch, revisao_git):
    # guarda: ci/revisor_de_pouso.py:141
    raiz, revisado = revisao_git
    atualizar_base(raiz)
    git(raiz, "merge", "--no-edit", "main")
    pais = git(raiz, "show", "-s", "--format=%P", "HEAD").split()
    (raiz / "comum.txt").write_text("codigo adulterado\n", encoding="utf-8")
    git(raiz, "add", ".")
    arvore = git(raiz, "write-tree")
    manual = git(raiz, "commit-tree", arvore, "-p", pais[0], "-p", pais[1], "-m", "merge manual")
    git(raiz, "update-ref", "refs/heads/entrega", manual)
    resultado = conferir_git(monkeypatch, raiz, revisado)
    assert resultado.estado is Estado.FAIL
    assert "árvore" in resultado.resumo


def test_conflito_resolvido_manualmente_exige_revisao(monkeypatch, revisao_git):
    # guarda: ci/revisor_de_pouso.py:136
    import subprocess
    raiz, revisado = revisao_git
    atualizar_base(raiz, "comum.txt")
    conflito = subprocess.run(["git", "merge", "--no-edit", "main"], cwd=raiz, capture_output=True)
    assert conflito.returncode == 1
    (raiz / "comum.txt").write_text("resolucao manual\n", encoding="utf-8")
    git(raiz, "add", ".")
    git(raiz, "commit", "-m", "resolver conflito")
    resultado = conferir_git(monkeypatch, raiz, revisado)
    assert resultado.estado is Estado.FAIL
    assert "conflito" in resultado.resumo


def test_segundo_pai_fora_da_main_nao_preserva_atestado(monkeypatch, revisao_git):
    # guarda: ci/revisor_de_pouso.py:133
    raiz, revisado = revisao_git
    git(raiz, "switch", "-c", "outra-base", "main")
    (raiz / "outra.txt").write_text("origem nao aprovada", encoding="utf-8")
    git(raiz, "add", ".")
    git(raiz, "commit", "-m", "outra base")
    git(raiz, "switch", "entrega")
    git(raiz, "merge", "--no-edit", "outra-base")
    resultado = conferir_git(monkeypatch, raiz, revisado)
    assert resultado.estado is Estado.FAIL
    assert "main" in resultado.resumo


@pytest.mark.parametrize("ultimo", [
    dict(comentario(veredito="REPROVADO"), id=2),
    dict(comentario(), id=2, body=MARCA + "\n{"),
])
def test_atestado_posterior_ruim_prevalece_sobre_composicao(monkeypatch, revisao_git, ultimo):
    # guarda: ci/revisor_de_pouso.py:73
    raiz, revisado = revisao_git
    atualizar_base(raiz)
    git(raiz, "merge", "--no-edit", "main")
    git(raiz, "remote", "set-url", "origin", str(raiz / "ausente.git"))
    resultado = conferir_git(monkeypatch, raiz, revisado, [comentario(sha=revisado), ultimo], publicar=False)
    assert resultado.estado is Estado.FAIL
    assert "reprovada" in resultado.resumo or "malformado" in resultado.resumo


def test_objeto_remoto_ausente_e_erro_de_instrumento(monkeypatch, revisao_git):
    # guarda: ci/revisor_de_pouso.py:150
    raiz, revisado = revisao_git
    resultado = conferir_git(monkeypatch, raiz, revisado, publicar=False, head="b" * 40)
    assert resultado.estado is Estado.ERROR


def test_timeout_do_git_nao_aprova_composicao(monkeypatch, revisao_git):
    # guarda: ci/revisor_de_pouso.py:150
    import subprocess
    raiz, revisado = revisao_git
    atualizar_base(raiz)
    git(raiz, "merge", "--no-edit", "main")
    git(raiz, "push", "origin", "entrega")
    executar_real = subprocess.run
    def executar(comando, **opcoes):
        if "fetch" in comando:
            raise subprocess.TimeoutExpired(comando, 40)
        return executar_real(comando, **opcoes)
    monkeypatch.setattr(subprocess, "run", executar)
    assert conferir_git(monkeypatch, raiz, revisado, publicar=False).estado is Estado.ERROR
