"""Estado remoto exato, sem equiparar merge à publicação."""
from pathlib import Path
import pytest
import base64
import yaml
import estado_da_entrega as entrega

RAIZ = Path(__file__).resolve().parents[2]
SHA = "a" * 40
CELULA = ".github/workflows/deploy-celula.yml"
INFRA = ".github/workflows/deploy-infra.yml"

def run(path=CELULA, **mudancas):
    dados = dict(id=20 if path == INFRA else 10, path=path, head_sha=SHA, head_branch="main", event="push",
                 status="completed", conclusion="success", run_attempt=1,
                 run_started_at="2026-09-09T10:00:00Z",
                 html_url="https://example.invalid/run/10")
    dados.update(mudancas)
    return dados

def conteudo_workflow(caminho):
    arquivo = caminho.removeprefix("contents/").split("?",1)[0]
    return dict(encoding="base64",content=base64.b64encode((RAIZ/arquivo).read_bytes()).decode())

def medir(monkeypatch, runs, arquivos=None):
    def api(raiz, caminho, **kw):
        if caminho.startswith("contents/"):
            return conteudo_workflow(caminho)
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
    monkeypatch.setattr(entrega, "_api", lambda raiz,caminho: conteudo_workflow(caminho) if caminho.startswith("contents/") else {"workflow_runs":[]})
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
    from _nucleo import ErroDeInstrumentacao
    mapa = {n: Celula(n,("services/"+n,),deps) for n,deps in
            [("loja",("vendas",)),("vendas",()),("quiz",())]}
    monkeypatch.setattr(entrega.mapa_de_celulas,"carregar",lambda *a: mapa)
    monkeypatch.setattr(entrega,"caminhos_dos_deploys",lambda *a: {CELULA:["services/**"],INFRA:["infra/traefik/**"]})
    monkeypatch.setattr(entrega,"_api",lambda *a,**kw: dict(total_count=1,workflow_runs=[run()]))
    monkeypatch.setattr(entrega,"consultar_jobs",lambda *a: [
        dict(name="deploy (loja)",status="completed",conclusion="success"),
        dict(name="deploy (vendas)",status="completed",conclusion="success"),
    ])
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
    with pytest.raises(ErroDeInstrumentacao, match=r"não prova os jobs: deploy \(quiz\)"):
        entrega.publicacoes_anteriores(RAIZ,["services/quiz/app.py"])
    assert not any("services/vendas" in a for a in vistos)


def test_historia_sem_job_exigido_falha_fechado(monkeypatch):
    from types import SimpleNamespace
    from mapa_de_celulas import Celula
    from _nucleo import ErroDeInstrumentacao

    monkeypatch.setattr(entrega.mapa_de_celulas, "carregar", lambda *a: {
        "admin": Celula("admin", ("services/admin",), ()),
    })
    monkeypatch.setattr(entrega, "caminhos_dos_deploys", lambda *a: {
        CELULA: ["services/**"], INFRA: ["infra/**"],
    })
    monkeypatch.setattr(entrega, "executar", lambda args, **kw: SimpleNamespace(
        stdout="false" if args[1] == "rev-parse" and "--is-shallow-repository" in args
        else SHA if args[1] == "rev-parse" else ""
    ))
    monkeypatch.setattr(entrega, "_api", lambda *a, **kw: {"total_count": 0, "workflow_runs": []})

    with pytest.raises(ErroDeInstrumentacao, match=r"não prova os jobs: deploy \(admin\)"):
        entrega.publicacoes_anteriores(RAIZ, ["services/admin/app.py"])


def test_cli_consulta_uma_vez_sem_espera(monkeypatch, capsys):
    import esperar
    monkeypatch.setattr(entrega,"consultar_entrega",lambda *a: dict(estado="AGUARDANDO_PUBLICACAO",terminal=False,sha_integrado=SHA))
    monkeypatch.setattr(esperar,"vigiar",lambda *a,**kw: pytest.fail("consulta iniciou espera"))
    assert esperar.main(["--entrega","99"]) == 1
    assert "AGUARDANDO_PUBLICACAO" in capsys.readouterr().out


def test_resposta_truncada_nao_aprova(monkeypatch):
    from _nucleo import ErroDeInstrumentacao
    monkeypatch.setattr(entrega,"_api",lambda raiz,caminho: conteudo_workflow(caminho) if caminho.startswith("contents/") else dict(total_count=101,workflow_runs=[run()]))
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
    pendente=dict(estado="FALHA_PUBLICACAO",terminal=False,sha_integrado=SHA,celulas=["quiz"],workflows=[CELULA],runs=[dict(id=10,workflow=CELULA,sha=SHA,status="completed",conclusion="cancelled",jobs_exigidos=["detectar","portao-de-deploy","deploy (quiz)"],jobs=[])])
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
    pendente["workflows"].append(INFRA)
    assert entrega.comprovar_sucessores(RAIZ,pendente)["estado"] == "FALHA_PUBLICACAO"
    pendente["workflows"].remove(INFRA)
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
    pendente=dict(estado="FALHA_PUBLICACAO",terminal=False,sha_integrado=SHA,celulas=["quiz"],workflows=[CELULA],runs=[dict(id=10,workflow=CELULA,sha=SHA,status="completed",conclusion="cancelled",jobs_exigidos=["detectar","portao-de-deploy","deploy (quiz)"],jobs=[])])
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


def test_cli_erro_inesperado_preserva_contrato_json(monkeypatch, capsys):
    import json
    import esperar
    def falhar(*args):
        raise RuntimeError("resposta remota incompatível")
    monkeypatch.setattr(entrega,"consultar_entrega",falhar)
    assert esperar.main(["--entrega","99"]) == 2
    estado = json.loads(capsys.readouterr().out)
    assert estado["estado"] == "ERROR"
    assert estado["terminal"] is False
    assert "Corrija a consulta" in estado["acao"]


@pytest.mark.parametrize("fonte", ["job", "caminho"])
def test_dados_admin_verdes_nao_escondem_ultima_imagem_falha(monkeypatch, fonte):
    from types import SimpleNamespace
    from mapa_de_celulas import Celula
    imagem = "b" * 40
    mapa = {"admin": Celula("admin",("services/admin","painel"),())}
    monkeypatch.setattr(entrega.mapa_de_celulas,"carregar",lambda *a: mapa)
    monkeypatch.setattr(entrega,"caminhos_dos_deploys",lambda *a: {CELULA:["services/**","painel/**"],INFRA:["infra/traefik/**"]})
    def executar(args,**kw):
        if args[1] == "rev-parse":
            return SimpleNamespace(stdout="false" if "--is-shallow-repository" in args else SHA)
        if args[1] == "log":
            return SimpleNamespace(stdout=SHA if "painel" in args else imagem if fonte=="caminho" and "services/admin" in args else "")
        if args[1] == "diff":
            return SimpleNamespace(stdout="painel/registros/a.js" if args[-1]==SHA else "services/admin/app.py")
        return SimpleNamespace(stdout="")
    monkeypatch.setattr(entrega,"executar",executar)
    def api(raiz,caminho,**kw):
        runs = [run(id=11),run(head_sha=imagem,conclusion="failure")]
        if fonte == "caminho":
            runs = [run(head_sha=imagem,conclusion="failure")]
        return dict(total_count=len(runs),workflow_runs=runs)
    monkeypatch.setattr(entrega,"_api",api)
    monkeypatch.setattr(entrega,"consultar_jobs",lambda raiz,r: [dict(name="publicar-dados-admin" if r["id"]==11 else "deploy (admin)",status="completed",conclusion="success" if r["id"]==11 else "failure")])
    monkeypatch.setattr(entrega,"consultar_publicacao",lambda raiz,sha,arquivos: dict(terminal=sha==SHA,estado="PUBLICADO" if sha==SHA else "FALHA_PUBLICACAO",sha_integrado=sha))
    bloqueios=entrega.publicacoes_anteriores(RAIZ,["services/admin/app.py"])
    assert [b["sha_integrado"] for b in bloqueios] == [imagem]


def test_historico_anterior_a_job_de_dados_nao_fica_procurando_para_sempre(monkeypatch):
    from types import SimpleNamespace
    from mapa_de_celulas import Celula

    chamadas = []
    jobs_consultados = []
    publicacoes = []
    monkeypatch.setattr(entrega.mapa_de_celulas, "carregar", lambda *a: {
        "admin": Celula("admin", ("services/admin",), ()),
    })
    monkeypatch.setattr(entrega, "caminhos_dos_deploys", lambda *a: {
        CELULA: ["services/**"], INFRA: ["infra/**"],
    })
    def executar(args, **kw):
        if args[1] == "rev-parse":
            return SimpleNamespace(stdout="false" if "--is-shallow-repository" in args else SHA)
        if args[1] == "log":
            return SimpleNamespace(stdout=SHA if "services/admin" in args else "")
        if args[1] == "diff":
            return SimpleNamespace(stdout="services/admin/app.py")
        return SimpleNamespace(stdout="")

    def api(raiz, caminho, **kw):
        chamadas.append(caminho)
        return {"total_count": 30, "workflow_runs": [run(id=n) for n in range(1, 31)]}

    monkeypatch.setattr(entrega, "executar", executar)
    monkeypatch.setattr(entrega, "_api", api)
    def consultar_jobs(raiz, run):
        jobs_consultados.append(run["id"])
        return [
            {"name": "detectar", "status": "completed", "conclusion": "success"},
            {"name": "portao-de-deploy", "status": "completed", "conclusion": "success"},
            {"name": "deploy (admin)", "status": "completed", "conclusion": "success"},
        ]

    monkeypatch.setattr(entrega, "consultar_jobs", consultar_jobs)
    def consultar_publicacao(*a):
        publicacoes.append(a)
        return {"terminal": True, "estado": "PUBLICADO", "sha_integrado": SHA}

    monkeypatch.setattr(entrega, "consultar_publicacao", consultar_publicacao)

    assert entrega.publicacoes_anteriores(RAIZ, ["services/admin/app.py"]) == []
    assert jobs_consultados
    assert chamadas == ["actions/workflows/deploy-celula.yml/runs?branch=main&event=push&per_page=100&page=1"]
    assert len(publicacoes) == 1


def test_historico_paralelo_reduz_na_ordem_da_tentativa(monkeypatch):
    from threading import Event
    from types import SimpleNamespace
    from mapa_de_celulas import Celula

    antigo_terminou = Event()
    recente = "c" * 40
    antigo = "b" * 40
    consultados = []
    monkeypatch.setattr(entrega.mapa_de_celulas, "carregar", lambda *a: {
        "admin": Celula("admin", ("services/admin",), ()),
    })
    monkeypatch.setattr(entrega, "caminhos_dos_deploys", lambda *a: {
        CELULA: ["services/**"], INFRA: ["infra/**"],
    })
    monkeypatch.setattr(entrega, "executar", lambda args, **kw: SimpleNamespace(
        stdout="false" if args[1] == "rev-parse" and "--is-shallow-repository" in args
        else SHA if args[1] == "rev-parse" else "services/admin/app.py"
        if args[1] == "diff" else ""
    ))
    monkeypatch.setattr(entrega, "_api", lambda *a, **kw: {
        "total_count": 3,
        "workflow_runs": [
            run(id=30, run_started_at="2026-09-09T12:00:00Z"),
            run(id=20, head_sha=recente, run_started_at="2026-09-09T11:00:00Z"),
            run(id=10, head_sha=antigo, run_started_at="2026-09-09T10:00:00Z"),
        ],
    })

    def consultar_jobs(raiz, atual):
        consultados.append(atual["id"])
        if atual["id"] == 30:
            return [{"name": "detectar", "status": "completed", "conclusion": "success"}]
        if atual["id"] == 10:
            antigo_terminou.set()
        else:
            assert antigo_terminou.wait(1), "a consulta antiga não terminou durante a nova"
        return [{"name": "deploy (admin)", "status": "completed", "conclusion": "success"}]

    monkeypatch.setattr(entrega, "consultar_jobs", consultar_jobs)
    monkeypatch.setattr(entrega, "consultar_publicacao", lambda raiz, sha, arquivos: {
        "terminal": sha != recente,
        "estado": "FALHA_PUBLICACAO" if sha == recente else "PUBLICADO",
        "sha_integrado": sha,
    })

    bloqueios = entrega.publicacoes_anteriores(RAIZ, ["services/admin/app.py"])
    assert [bloqueio["sha_integrado"] for bloqueio in bloqueios] == [recente]
    assert set(consultados) == {10, 20, 30}


def test_reexecucao_recente_com_id_antigo_na_segunda_pagina_decide(monkeypatch):
    from types import SimpleNamespace
    from mapa_de_celulas import Celula

    antigo = "b" * 40
    recente = "c" * 40
    paginas = []
    jobs_consultados = []
    monkeypatch.setattr(entrega.mapa_de_celulas, "carregar", lambda *a: {
        "admin": Celula("admin", ("services/admin",), ()),
    })
    monkeypatch.setattr(entrega, "caminhos_dos_deploys", lambda *a: {
        CELULA: ["services/**"], INFRA: ["infra/**"],
    })
    monkeypatch.setattr(entrega, "executar", lambda args, **kw: SimpleNamespace(
        stdout="false" if args[1] == "rev-parse" and "--is-shallow-repository" in args
        else SHA if args[1] == "rev-parse" else "services/admin/app.py"
        if args[1] == "diff" else ""
    ))

    def api(raiz, caminho, **kw):
        pagina = int(caminho.rsplit("page=", 1)[1])
        paginas.append(pagina)
        runs = [run(id=n, head_sha=antigo) for n in range(20, 120)] if pagina == 1 else [
            run(id=10, run_attempt=2, head_sha=recente,
                run_started_at="2026-09-09T11:00:00Z"),
        ]
        return {"total_count": 101, "workflow_runs": runs}

    monkeypatch.setattr(entrega, "_api", api)

    def consultar_jobs(raiz, atual):
        jobs_consultados.append(atual["id"])
        return [{"name": "deploy (admin)", "status": "completed", "conclusion": "success"}]

    monkeypatch.setattr(entrega, "consultar_jobs", consultar_jobs)
    monkeypatch.setattr(entrega, "consultar_publicacao", lambda raiz, sha, arquivos: {
        "terminal": sha == antigo,
        "estado": "PUBLICADO" if sha == antigo else "FALHA_PUBLICACAO",
        "sha_integrado": sha,
    })

    bloqueios = entrega.publicacoes_anteriores(RAIZ, ["services/admin/app.py"])
    assert [bloqueio["sha_integrado"] for bloqueio in bloqueios] == [recente]
    assert paginas == [1, 2]
    assert jobs_consultados == [10]


@pytest.mark.parametrize("arquivo,esperado", [("painel/registros/a.js","PUBLICADO"),("painel/registros/a.js","FALHA_PUBLICACAO"),("docs/decisoes/plano.md","SEM_PUBLICACAO")])
def test_publicacao_usa_workflow_vigente_no_sha(monkeypatch, arquivo, esperado):
    consultas = []
    def api(raiz,caminho,**kw):
        consultas.append(caminho)
        if caminho.startswith("contents/"):
            atual = conteudo_workflow(caminho)
            dado = yaml.safe_load(base64.b64decode(atual["content"]))
            if CELULA in caminho:
                dado["jobs"].pop("publicar-dados-admin")
                dado[True]["push"]["paths"] = ["services/**","painel/**","fila/**"]
            return dict(encoding="base64",content=base64.b64encode(yaml.safe_dump(dado).encode()).decode())
        if "/jobs?" in caminho:
            return dict(jobs=[dict(name=n,status="completed",conclusion="success") for n in (["detectar","portao-de-deploy"] if esperado=="FALHA_PUBLICACAO" else ["detectar","portao-de-deploy","deploy (admin)"])])
        return dict(workflow_runs=[run()])
    monkeypatch.setattr(entrega,"_api",api)
    resultado = entrega.consultar_publicacao(RAIZ,SHA,[arquivo])
    assert resultado["estado"] == esperado
    assert len([c for c in consultas if c.startswith("contents/") and c.endswith("?ref="+SHA)]) == 2
    if esperado == "PUBLICADO":
        assert "publicar-dados-admin" not in resultado["runs"][0]["jobs_exigidos"]
        assert "deploy (admin)" in resultado["runs"][0]["jobs_exigidos"]


@pytest.mark.parametrize("arquivo", ["Dockerfile","requirements.txt"])
def test_recuperacao_aceita_insumos_reais_da_imagem(monkeypatch,arquivo):
    falha=dict(estado="FALHA_PUBLICACAO",celulas=["quiz"],runs=[dict(id=10,conclusion="failure",jobs=[dict(name="deploy (quiz)",conclusion="failure")])])
    pr=dict(body="Corrige-publicacao: 10",files=[{"path":"services/quiz/"+arquivo}])
    assert entrega.correcao_da_publicacao(RAIZ,pr,falha)
    assert not entrega.correcao_da_publicacao(RAIZ,dict(pr,body="Corrige-publicacao: 11"),falha)
    assert not entrega.correcao_da_publicacao(RAIZ,dict(pr,files=[{"path":"services/quiz/tests/"+arquivo}]),falha)
    assert not entrega.correcao_da_publicacao(RAIZ,dict(pr,files=[{"path":"services/quiz/exemplo/"+arquivo}]),falha)
    assert not entrega.correcao_da_publicacao(RAIZ,dict(pr,files=[{"path":"services/admin/"+arquivo}]),falha)


@pytest.mark.parametrize("defeito", ["encoding","sem_jobs","jobs_desconhecidos"])
def test_workflow_historico_invalido_e_erro_de_instrumento(monkeypatch, defeito):
    from _nucleo import ErroDeInstrumentacao
    def api(raiz,caminho,**kw):
        if not caminho.startswith("contents/"):
            return dict(workflow_runs=[run()])
        dado = conteudo_workflow(caminho)
        if defeito == "encoding": return dict(dado,encoding="none")
        conteudo = yaml.safe_load(base64.b64decode(dado["content"]))
        if defeito == "sem_jobs": conteudo.pop("jobs")
        else: conteudo["jobs"] = {}
        return dict(dado,content=base64.b64encode(yaml.safe_dump(conteudo).encode()).decode())
    monkeypatch.setattr(entrega,"_api",api)
    with pytest.raises(ErroDeInstrumentacao):
        if defeito == "jobs_desconhecidos":
            entrega.consultar_publicacao(RAIZ,SHA,["services/quiz/app.py"])
        else:
            entrega.workflows_dos_deploys(RAIZ,SHA)
