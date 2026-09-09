"""Estado remoto exato, sem equiparar merge à publicação."""
from pathlib import Path
import pytest
import estado_da_entrega as entrega

RAIZ = Path(__file__).resolve().parents[2]
SHA = "a" * 40
CELULA = ".github/workflows/deploy-celula.yml"
INFRA = ".github/workflows/deploy-infra.yml"

def run(path=CELULA, **mudancas):
    dados = dict(id=10, path=path, head_sha=SHA, head_branch="main", event="push",
                 status="completed", conclusion="success", html_url="https://example.invalid/run/10")
    dados.update(mudancas)
    return dados

def medir(monkeypatch, runs, arquivos=None):
    monkeypatch.setattr(entrega, "_api", lambda *a: {"workflow_runs":runs})
    return entrega.consultar_publicacao(RAIZ, SHA, arquivos or ["services/quiz/app.py"])

def test_publicado_exige_o_sha_exato(monkeypatch):
    assert medir(monkeypatch, [run()])["estado"] == "PUBLICADO"
    assert medir(monkeypatch, [run(head_sha="b"*40)])["estado"] == "AGUARDANDO_PUBLICACAO"

@pytest.mark.parametrize("mudancas", [dict(status="in_progress"), dict(event="pull_request"), dict(head_branch="outro")])
def test_pendente_e_outro_evento_nao_aprovam(monkeypatch, mudancas):
    assert medir(monkeypatch, [run(**mudancas)])["estado"] == "AGUARDANDO_PUBLICACAO"

@pytest.mark.parametrize("conclusao", ["failure", "cancelled", "skipped", None])
def test_vermelho_pulado_e_cancelado_recusam(monkeypatch, conclusao):
    assert medir(monkeypatch, [run(conclusion=conclusao)])["estado"] == "FALHA_PUBLICACAO"

def test_todos_workflows_exigidos_precisam_aparecer(monkeypatch):
    arquivos = ["services/quiz/app.py", "infra/docker-compose.yml"]
    assert medir(monkeypatch, [run()], arquivos)["estado"] == "AGUARDANDO_PUBLICACAO"
    assert medir(monkeypatch, [run(),run(INFRA)], arquivos)["estado"] == "PUBLICADO"

def test_reexecucao_mais_recente_decide_nos_dois_sentidos(monkeypatch):
    assert medir(monkeypatch, [run(conclusion="failure"),run(id=11)])["estado"] == "PUBLICADO"
    assert medir(monkeypatch, [run(),run(id=11, conclusion="failure")])["estado"] == "FALHA_PUBLICACAO"

def test_sem_gatilho_nao_inventa_deploy(monkeypatch):
    assert medir(monkeypatch, [], ["ci/algo.py"])["estado"] == "SEM_PUBLICACAO"

def test_merge_com_deploy_ausente_nao_e_terminal(monkeypatch):
    monkeypatch.setattr(entrega, "ler_pr", lambda *a: dict(number=99,state="MERGED",mergeCommit={"oid":SHA},headRefOid=SHA,files=[{"path":"services/quiz/app.py"}]))
    monkeypatch.setattr(entrega, "_api", lambda *a: {"workflow_runs":[]})
    estado = entrega.consultar_entrega(RAIZ,99)
    assert estado["estado"] == "AGUARDANDO_PUBLICACAO"
    assert estado["terminal"] is False
    assert estado["sha_integrado"] == SHA

def test_novo_sha_diagnostica_nova_revisao(monkeypatch):
    monkeypatch.setattr(entrega, "ler_pr", lambda *a: dict(number=99,state="OPEN",headRefOid=SHA,labels=[{"name":"pousar"}],files=[]))
    monkeypatch.setattr(entrega, "_api", lambda *a, **kw: [])
    estado = entrega.consultar_entrega(RAIZ,99)
    assert estado["estado"] == "REVISAO_NECESSARIA"
    assert estado["terminal"] is False
    assert "revisão" in estado["acao"].lower()

def test_dependencias_transitivas_e_celulas_independentes():
    from mapa_de_celulas import Celula
    mapa = {n: Celula(n,("services/"+n,),deps) for n,deps in
            [("loja",("vendas",)),("vendas",("alunos",)),("alunos",()),("quiz",())]}
    assert entrega.celulas_requeridas(["services/loja/app.py"],mapa) == {"loja","vendas","alunos"}
    assert entrega.celulas_requeridas(["services/quiz/app.py"],mapa) == {"quiz"}


def test_portao_bloqueia_falha_e_pendente_de_publicacao(monkeypatch):
    import mergear
    from _nucleo import Estado
    for estado, esperado in [("FALHA_PUBLICACAO", Estado.FAIL), ("AGUARDANDO_PUBLICACAO", Estado.ERROR)]:
        monkeypatch.setattr(entrega, "publicacoes_anteriores", lambda *a: [dict(estado=estado,sha_integrado=SHA,terminal=False,acao="Confira o run 10")])
        resultado = mergear.checar_publicacoes_anteriores(RAIZ,dict(files=[],body=""))
        assert resultado[0].estado is esperado
        assert "run 10" in resultado[0].detalhe


def test_dependencia_declarada_mergeada_com_deploy_vermelho_bloqueia(monkeypatch):
    import mergear
    from _nucleo import Estado
    monkeypatch.setattr(entrega, "publicacoes_anteriores", lambda *a: [])
    monkeypatch.setattr(entrega, "consultar_entrega", lambda *a: dict(estado="FALHA_PUBLICACAO",sha_integrado=SHA,terminal=False,acao="Conserte run 10"))
    resultados = mergear.checar_publicacoes_anteriores(RAIZ,dict(files=[],body="Depende-de: #88"))
    assert resultados[0].estado is Estado.FAIL


def test_historia_de_celula_e_provedor_e_medida_antes_de_liberar(monkeypatch):
    from types import SimpleNamespace
    from mapa_de_celulas import Celula
    mapa = {n: Celula(n,("services/"+n,),deps) for n,deps in
            [("loja",("vendas",)),("vendas",()),("quiz",())]}
    monkeypatch.setattr(entrega.mapa_de_celulas,"carregar",lambda *a: mapa)
    monkeypatch.setattr(entrega,"caminhos_dos_deploys",lambda *a: {CELULA:["services/**"],INFRA:["infra/traefik/**"]})
    vistos=[]
    def executar(args,**kw):
        vistos.append(args)
        if args[1] == "rev-parse":
            return SimpleNamespace(stdout="false" if "--is-shallow-repository" in args else "b"*40)
        if args[1] == "log":
            return SimpleNamespace(stdout=SHA if "services/vendas" in args else "")
        if args[1] == "diff":
            return SimpleNamespace(stdout="services/vendas/app.py")
        return SimpleNamespace(stdout="")
    monkeypatch.setattr(entrega,"executar",executar)
    monkeypatch.setattr(entrega,"consultar_publicacao",lambda *a: dict(terminal=False,estado="FALHA_PUBLICACAO",sha_integrado=SHA))
    assert entrega.publicacoes_anteriores(RAIZ,["services/loja/app.py"])[0]["estado"] == "FALHA_PUBLICACAO"
    assert any("services/vendas" in a for a in vistos)
    vistos.clear()
    assert entrega.publicacoes_anteriores(RAIZ,["services/quiz/app.py"]) == []
    assert not any("services/vendas" in a for a in vistos)


def test_cli_consulta_uma_vez_sem_espera(monkeypatch, capsys):
    import esperar
    monkeypatch.setattr(entrega,"consultar_entrega",lambda *a: dict(estado="AGUARDANDO_PUBLICACAO",terminal=False,sha_integrado=SHA))
    monkeypatch.setattr(esperar,"vigiar",lambda *a,**kw: pytest.fail("consulta iniciou espera"))
    assert esperar.main(["--entrega","99"]) == 1
    assert "AGUARDANDO_PUBLICACAO" in capsys.readouterr().out


def test_resposta_truncada_nao_aprova(monkeypatch):
    from _nucleo import ErroDeInstrumentacao
    monkeypatch.setattr(entrega,"_api",lambda *a: dict(total_count=101,workflow_runs=[run()]))
    with pytest.raises(ErroDeInstrumentacao,match="truncada"):
        entrega.consultar_publicacao(RAIZ,SHA,["services/quiz/app.py"])
