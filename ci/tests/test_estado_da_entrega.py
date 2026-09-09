"""Estado remoto exato, sem equiparar merge à publicação."""
from pathlib import Path
import pytest
import estado_da_entrega as entrega

RAIZ = Path(__file__).resolve().parents[2]
SHA = "a" * 40
CELULA = ".github/workflows/deploy-celula.yml"
INFRA = ".github/workflows/deploy-infra.yml"

def run(path=CELULA, **mudancas):
    dados = dict(id=20 if path == INFRA else 10, path=path, head_sha=SHA, head_branch="main", event="push",
                 status="completed", conclusion="success", html_url="https://example.invalid/run/10")
    dados.update(mudancas)
    return dados

def medir(monkeypatch, runs, arquivos=None):
    def api(raiz, caminho, **kw):
        if "/jobs?" in caminho:
            numero = int(caminho.split("/")[2])
            atual = next(r for r in runs if r["id"] == numero)
            nomes = ["detectar", "portao-de-deploy", "publicar-dados-admin", "deploy (quiz)", "deploy (admin)", "sincronizar"]
            return {"jobs": atual.get("jobs",[dict(name=n,status="completed",conclusion="success") for n in nomes])}
        return {"workflow_runs":runs}
    monkeypatch.setattr(entrega, "_api", api)
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


def test_workflow_success_sem_job_da_celula_nao_publica(monkeypatch):
    jobs=[dict(name=n,status="completed",conclusion="success") for n in ["detectar","portao-de-deploy","deploy (admin)"]]
    estado=medir(monkeypatch,[run(jobs=jobs)])
    assert estado["estado"] == "FALHA_PUBLICACAO"
    assert "deploy (quiz)" in estado["runs"][0]["jobs_exigidos"]


def test_dados_admin_nao_exigem_imagem_mas_exigem_publicador(monkeypatch):
    jobs=[dict(name=n,status="completed",conclusion="success") for n in ["detectar","portao-de-deploy","publicar-dados-admin"]]
    assert medir(monkeypatch,[run(jobs=jobs)],["painel/registros/a.js"])["estado"] == "PUBLICADO"
    jobs.pop()
    assert medir(monkeypatch,[run(jobs=jobs)],["painel/registros/a.js"])["estado"] == "FALHA_PUBLICACAO"


def test_imagem_admin_nao_e_provada_por_publicador_de_dados(monkeypatch):
    jobs=[dict(name=n,status="completed",conclusion="success") for n in ["detectar","portao-de-deploy","publicar-dados-admin"]]
    assert medir(monkeypatch,[run(jobs=jobs)],["services/admin/app.py","painel/registros/a.js"])["estado"] == "FALHA_PUBLICACAO"


def test_recuperacao_exige_run_falho_e_codigo_de_todas_celulas(monkeypatch):
    falha=dict(estado="FALHA_PUBLICACAO",celulas=["cursos","admin"],runs=[dict(id=10,conclusion="failure",jobs=[dict(name="deploy (cursos)",conclusion="failure"),dict(name="deploy (admin)",conclusion="cancelled")])])
    pr=dict(body="Corrige-publicacao: 10",files=[{"path":"services/cursos/apps/cursos/management/commands/corrigir.py"},{"path":"painel/registros/a.js"}])
    assert entrega.correcao_da_publicacao(RAIZ,pr,falha)
    for arquivos,body in [([{"path":"painel/registros/a.js"}],"Corrige-publicacao: 10"),(pr["files"],"Corrige-publicacao: 11"),([{"path":"services/admin/app.py"}],"Corrige-publicacao: 10"),([{"path":"services/cursos/tests/test_a.py"},{"path":"painel/registros/a.js"}],"Corrige-publicacao: 10")]:
        assert not entrega.correcao_da_publicacao(RAIZ,dict(files=arquivos,body=body),falha)
    sem_admin = dict(pr,files=[pr["files"][0]])
    assert not entrega.correcao_da_publicacao(RAIZ,sem_admin,falha)
    fixture = dict(pr,files=[{"path":"services/cursos/tests/cenario.py"},{"path":"painel/registros/a.js"}])
    assert not entrega.correcao_da_publicacao(RAIZ,fixture,falha)
    falha["runs"].append(dict(id=11,conclusion="failure",jobs=[dict(name="deploy (quiz)",conclusion="failure")]))
    assert not entrega.correcao_da_publicacao(RAIZ,pr,falha)
    assert not entrega.correcao_da_publicacao(RAIZ,dict(pr,body="Corrige-publicacao: 10, 11"),falha)


def test_recuperacao_nao_dispensa_publicacao_pendente():
    assert not entrega.correcao_da_publicacao(RAIZ,dict(body="Corrige-publicacao: 10",files=[{"path":"services/quiz/app.py"}]),dict(estado="AGUARDANDO_PUBLICACAO",celulas=["quiz"],runs=[dict(id=10,conclusion="failure",jobs=[dict(name="deploy (quiz)",conclusion="failure")])]))


def test_sucessor_precisa_ancestralidade_e_job_real(monkeypatch):
    pendente=dict(estado="FALHA_PUBLICACAO",terminal=False,sha_integrado=SHA,celulas=["quiz"],runs=[dict(id=10,workflow=CELULA,sha=SHA,status="completed",conclusion="cancelled",jobs_exigidos=["detectar","portao-de-deploy","deploy (quiz)"],jobs=[])])
    sucessor=run(id=11,head_sha="b"*40)
    nome="deploy (quiz)"
    def api(raiz,caminho,**kw):
        if "compare/" in caminho:
            return dict(status="ahead")
        if "/jobs?" in caminho:
            return dict(jobs=[dict(name=n,status="completed",conclusion="success") for n in ["detectar","portao-de-deploy",nome]])
        return dict(workflow_runs=[sucessor])
    monkeypatch.setattr(entrega,"_api",api)
    resultado=entrega.comprovar_sucessores(RAIZ,pendente)
    assert resultado["estado"] == "PUBLICADO"
    assert resultado["sha_integrado"] == SHA
    assert resultado["publicacoes"][0]["sha"] == "b"*40
    nome="deploy (admin)"
    assert entrega.comprovar_sucessores(RAIZ,pendente)["estado"] == "FALHA_PUBLICACAO"
    nome="deploy (quiz)"
    def sem_ancestralidade(raiz,caminho,**kw):
        if "compare/" in caminho:
            return dict(status="diverged")
        return api(raiz,caminho,**kw)
    monkeypatch.setattr(entrega,"_api",sem_ancestralidade)
    assert entrega.comprovar_sucessores(RAIZ,pendente)["estado"] == "FALHA_PUBLICACAO"


def test_recuperacao_rejeita_id_extra_que_nao_e_falha_vigente(monkeypatch):
    import mergear
    from _nucleo import Estado
    falha=dict(estado="FALHA_PUBLICACAO",terminal=False,sha_integrado=SHA,acao="corrigir",celulas=["quiz"],runs=[dict(id=10,conclusion="failure",jobs=[dict(name="deploy (quiz)",conclusion="failure")])])
    monkeypatch.setattr(entrega,"publicacoes_anteriores",lambda *a:[falha])
    pr=dict(files=[{"path":"services/quiz/app.py"}],body="Corrige-publicacao: 10, 99")
    assert any(r.estado is Estado.FAIL for r in mergear.checar_publicacoes_anteriores(RAIZ,pr))


def test_sucessor_mais_recente_falho_nao_recua_para_verde_antigo(monkeypatch):
    pendente=dict(estado="FALHA_PUBLICACAO",terminal=False,sha_integrado=SHA,celulas=["quiz"],runs=[dict(id=10,workflow=CELULA,sha=SHA,status="completed",conclusion="cancelled",jobs_exigidos=["detectar","portao-de-deploy","deploy (quiz)"],jobs=[])])
    def api(raiz,caminho,**kw):
        if "compare/" in caminho: return dict(status="ahead")
        if "/jobs?" in caminho:
            ruim="/12/" in caminho
            return dict(jobs=[dict(name=n,status="completed",conclusion="failure" if ruim and n=="deploy (quiz)" else "success") for n in ["detectar","portao-de-deploy","deploy (quiz)"]])
        return dict(workflow_runs=[run(id=12,head_sha="c"*40,conclusion="failure"),run(id=11,head_sha="b"*40)])
    monkeypatch.setattr(entrega,"_api",api)
    assert entrega.comprovar_sucessores(RAIZ,pendente)["estado"] == "FALHA_PUBLICACAO"


def test_correcao_da_infra_exige_caminho_que_a_publica():
    falha=dict(estado="FALHA_PUBLICACAO",celulas=[],runs=[dict(id=20,workflow=INFRA,conclusion="failure",jobs=[dict(name="sincronizar",conclusion="failure")])])
    assert entrega.correcao_da_publicacao(RAIZ,dict(body="Corrige-publicacao: 20",files=[{"path":"infra/docker-compose.yml"}]),falha)
    assert not entrega.correcao_da_publicacao(RAIZ,dict(body="Corrige-publicacao: 20",files=[{"path":"painel/registros/a.js"}]),falha)
