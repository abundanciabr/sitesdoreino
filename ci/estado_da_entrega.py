"""Consulta revisão, integração e publicação; não agenda nem publica nada.

A pista usa o mesmo leitor para impedir que uma célula ou seu consumidor
avance antes da publicação anterior. Estado é derivado do Git e do GitHub,
nunca de um arquivo de status paralelo ao livro de ocorrências.
"""
from __future__ import annotations

import fnmatch
import base64
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import mapa_de_celulas
from _nucleo import ErroDeInstrumentacao, Estado, executar
from revisor_de_pouso import avaliar_atestado

DEPLOYS = (".github/workflows/deploy-celula.yml", ".github/workflows/deploy-infra.yml")
MAX_PAGINAS_DO_HISTORICO = 100


def _api(raiz: Path, caminho: str, *, paginas=False):
    args = ["gh", "api", "repos/{owner}/{repo}/" + caminho]
    if paginas:
        args += ["--paginate", "--slurp"]
    saida = executar(args, cwd=raiz, descricao="consultar " + caminho,
                     exigir_stdout=True).stdout
    try:
        dados = json.loads(saida)
        if paginas:
            if not isinstance(dados, list) or any(not isinstance(p, list) for p in dados):
                raise ValueError("resposta paginada incompleta")
            return [item for pagina in dados for item in pagina]
        return dados
    except (ValueError, TypeError) as exc:
        raise ErroDeInstrumentacao("GitHub devolveu uma medição inválida", str(exc)) from exc


def ler_pr(raiz: Path, numero: int) -> dict:
    dado = _api(raiz, f"pulls/{numero}")
    arquivos = _api(raiz, f"pulls/{numero}/files", paginas=True)
    if not isinstance(dado, dict) or not isinstance(arquivos, list):
        raise ErroDeInstrumentacao("PR ou arquivos ausentes na resposta do GitHub")
    return dict(number=numero, state="MERGED" if dado.get("merged") else str(dado.get("state", "")).upper(),
                headRefOid=(dado.get("head") or {}).get("sha"),
                mergeCommit={"oid": dado.get("merge_commit_sha")},
                labels=dado.get("labels") or [], isDraft=dado.get("draft"),
                body=dado.get("body"), url=dado.get("html_url"),
                files=[{"path": a["filename"]} for a in arquivos])


def workflows_dos_deploys(raiz: Path, sha: str | None = None) -> dict[str, dict]:
    import yaml
    resultado = {}
    for workflow in DEPLOYS:
        if sha is None:
            texto = (raiz / workflow).read_text(encoding="utf-8")
        else:
            dado = _api(raiz, f"contents/{workflow}?ref={sha}")
            if not isinstance(dado, dict) or dado.get("encoding") != "base64":
                raise ErroDeInstrumentacao("workflow histórico não foi medido", workflow)
            texto = base64.b64decode(dado["content"]).decode("utf-8")
        dado = yaml.safe_load(texto)
        if not isinstance(dado, dict) or not isinstance(dado.get("jobs"), dict):
            raise ErroDeInstrumentacao("workflow sem definição dos jobs", workflow)
        resultado[workflow] = dado
    return resultado


def caminhos_dos_deploys(raiz: Path, definicoes: dict | None = None) -> dict[str, list[str]]:
    resultado = {}
    for workflow, dado in (definicoes if definicoes is not None else workflows_dos_deploys(raiz)).items():
        gatilhos = dado.get("on") or dado.get(True)
        caminhos = gatilhos["push"]["paths"]
        if not isinstance(caminhos, list) or not caminhos or any(
            not isinstance(p, str) or p.startswith("!") for p in caminhos
        ):
            raise ErroDeInstrumentacao("gatilhos de publicação não reconhecidos", workflow)
        resultado[workflow] = caminhos
    return resultado


def jobs_exigidos(workflow: str, arquivos: list[str], celulas: list[str], definicao: dict) -> list[str]:
    jobs = definicao["jobs"]
    chaves = {"portao", "sincronizar"} if workflow == DEPLOYS[1] else {"detectar", "portao", "deploy"}
    if not chaves <= jobs.keys():
        raise ErroDeInstrumentacao("jobs históricos de publicação não reconhecidos", workflow)
    if workflow == DEPLOYS[1]:
        return [jobs[n].get("name", n) for n in ["portao", "sincronizar"]]
    nomes = [jobs[n].get("name", n) for n in ["detectar", "portao"]]
    dados_separados = "publicar-dados-admin" in jobs
    dados_admin = any(a.startswith(("painel/", "fila/")) for a in arquivos)
    if dados_admin and dados_separados:
        nomes.append(jobs["publicar-dados-admin"].get("name", "publicar-dados-admin"))
    somente_dados = dados_separados and bool(arquivos) and all(a.startswith(("painel/", "fila/")) for a in arquivos)
    if not somente_dados:
        nomes.extend(f"{jobs['deploy'].get('name', 'deploy')} ({c})" for c in celulas)
    return nomes


def consultar_jobs(raiz: Path, run: dict) -> list[dict]:
    dados = _api(raiz, f"actions/runs/{run['id']}/jobs?filter=latest&per_page=100")
    if not isinstance(dados, dict) or not isinstance(dados.get("jobs"), list):
        raise ErroDeInstrumentacao("GitHub não devolveu os jobs da publicação")
    if dados.get("total_count", len(dados["jobs"])) > len(dados["jobs"]):
        raise ErroDeInstrumentacao("jobs de publicação truncados; não há prova de cobertura")
    return [dict(id=j.get("id"), name=j.get("name"), status=j.get("status"),
                 conclusion=j.get("conclusion"), url=j.get("html_url")) for j in dados["jobs"]]


def consultar_publicacao(raiz: Path, sha: str, arquivos: list[str]) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40}", sha or ""):
        raise ErroDeInstrumentacao("SHA integrado ausente ou incompleto; confira o merge")
    definicoes = workflows_dos_deploys(raiz, sha)
    exigidos = [w for w, padroes in caminhos_dos_deploys(raiz, definicoes).items()
                if any(fnmatch.fnmatchcase(a, p) for a in arquivos for p in padroes)]
    celulas = mapa_de_celulas.celulas_do_diff(arquivos, mapa_de_celulas.carregar(raiz))
    base = dict(sha_integrado=sha, celulas=celulas, workflows=exigidos, runs=[])
    if not exigidos:
        return dict(base, estado="SEM_PUBLICACAO", terminal=True, acao="Integração concluída; este diff não dispara publicação.")
    runs_por_workflow = {}
    for workflow in exigidos:
        resposta = _api(raiz, f"actions/workflows/{Path(workflow).name}/runs?head_sha={sha}&per_page=100")
        if not isinstance(resposta, dict) or not isinstance(resposta.get("workflow_runs"), list):
            raise ErroDeInstrumentacao("GitHub não devolveu a lista de publicações")
        # Não aceitar uma página truncada: uma execução mais recente pode estar fora dela.
        if resposta.get("total_count", len(resposta["workflow_runs"])) > len(resposta["workflow_runs"]):
            raise ErroDeInstrumentacao("lista de publicações truncada; confira os runs do SHA")
        runs_por_workflow[workflow] = [
            r for r in resposta["workflow_runs"]
            if r.get("path") == workflow and r.get("head_sha") == sha
            and r.get("head_branch") == "main" and r.get("event") == "push"
        ]
    escolhidos = [max(runs_por_workflow[workflow],
                      key=lambda r: (r.get("id", 0), r.get("run_attempt", 1)), default=None)
                  for workflow in exigidos]
    base["runs"] = [dict(id=r["id"], workflow=r["path"], sha=sha,
                         status=r.get("status"), conclusion=r.get("conclusion"),
                         url=r.get("html_url")) for r in escolhidos if r]
    cobertura_incompleta = False
    for registro in base["runs"]:
        registro["jobs_exigidos"] = jobs_exigidos(registro["workflow"], arquivos, celulas, definicoes[registro["workflow"]])
        registro["jobs"] = consultar_jobs(raiz, registro)
        por_nome = {j["name"]: j for j in registro["jobs"]}
        registro["jobs_sem_prova"] = [n for n in registro["jobs_exigidos"]
                                     if por_nome.get(n, {}).get("conclusion") != "success"
                                     or por_nome.get(n, {}).get("status") != "completed"]
        if registro["status"] == "completed" and registro["jobs_sem_prova"]:
            cobertura_incompleta = True
    caidos = [r for r in escolhidos if r and r.get("status") == "completed"
              and r.get("conclusion") != "success"]
    if caidos or cobertura_incompleta:
        run = caidos[0] if caidos else next(r for r in base["runs"] if r["jobs_sem_prova"])
        return dict(base, estado="FALHA_PUBLICACAO", terminal=False,
                    acao=f"Maestro: leia gh run view {run['id']} --log-failed; corrija a causa "
                         f"ou reexecute gh run rerun {run['id']} --failed e confira este SHA novamente.")
    if any(r is None or r.get("status") != "completed" for r in escolhidos):
        return dict(base, estado="AGUARDANDO_PUBLICACAO", terminal=False,
                    acao="Maestro: acompanhe pelo heartbeat nativo até todos os workflows exigidos concluírem; ausência não é sucesso.")
    return dict(base, estado="PUBLICADO", terminal=True,
                acao="Publicação comprovada nos runs deste SHA; registre o veredito no livro.")


def consultar_entrega(raiz: Path, numero: int) -> dict:
    pr = ler_pr(raiz, numero)
    base = dict(pr=numero, sha_atual=pr.get("headRefOid"), terminal=False)
    if pr["state"] == "MERGED":
        publicacao = consultar_publicacao(raiz, (pr.get("mergeCommit") or {}).get("oid"),
                                        [a["path"] for a in pr["files"]])
        return dict(base, **comprovar_sucessores(raiz, publicacao))
    if pr["state"] == "CLOSED":
        return dict(base, estado="ENCERRADO_SEM_INTEGRAR", terminal=True,
                    acao="PR encerrado sem integração; a entrega não foi publicada.")
    comentarios = _api(raiz, f"issues/{numero}/comments", paginas=True)
    revisao = avaliar_atestado(pr.get("headRefOid") or "", comentarios, correcoes=correcoes_declaradas(pr))
    if revisao.estado is not Estado.PASS:
        return dict(base, estado="REVISAO_NECESSARIA", acao=revisao.resumo + ". " + revisao.detalhe)
    if pr.get("isDraft"):
        return dict(base, estado="RASCUNHO", acao="Despacho: conclua a validação e o recibo pelo rito do PR.")
    etiquetas = {l.get("name") for l in pr.get("labels", [])}
    if "pousar" in etiquetas:
        return dict(base, estado="AGUARDANDO_INTEGRACAO",
                    acao="Maestro: mantenha o acompanhamento nativo; etiqueta não prova integração nem publicação.")
    return dict(base, estado="POUSO_NAO_SOLICITADO_OU_RECUSADO",
                acao=f"Maestro: execute python ci/mergear.py {numero} --conferir e corrija o diagnóstico antes de pedir pouso.")


def celulas_requeridas(arquivos: list[str], mapa: dict) -> set[str]:
    requeridas = set(mapa_de_celulas.celulas_do_diff(arquivos, mapa))
    pendentes = list(requeridas)
    while pendentes:
        for provedor in mapa[pendentes.pop()].consome:
            if provedor not in requeridas:
                requeridas.add(provedor)
                pendentes.append(provedor)
    return requeridas


def publicacoes_anteriores(raiz: Path, arquivos: list[str]) -> list[dict]:
    mapa = mapa_de_celulas.carregar(raiz)
    requeridas = celulas_requeridas(arquivos, mapa)
    gatilhos = caminhos_dos_deploys(raiz)
    infra = gatilhos[DEPLOYS[1]]
    toca_infra = any(fnmatch.fnmatchcase(a, p) for a in arquivos for p in infra)
    if toca_infra:
        requeridas = set(mapa)
    if not requeridas and not toca_infra:
        return []
    executar(["git", "fetch", "origin", "main"], cwd=raiz,
             descricao="atualizar a referência publicada antes de conferir a fila")
    def git(*args):
        return executar(["git", *args], cwd=raiz, descricao="ler histórico de publicação").stdout.strip()
    if git("rev-parse", "--is-shallow-repository") != "false":
        raise ErroDeInstrumentacao("histórico raso não prova a última publicação; use fetch-depth: 0")
    referencia = git("rev-parse", "origin/main")
    grupos = [mapa[c].caminhos for c in sorted(requeridas)]
    grupos.extend(tuple(p for p in mapa[c].caminhos if p.rstrip("/") not in {"painel", "fila"})
                  for c in sorted(requeridas))
    grupos = [g for g in grupos if g]
    grupos.append(tuple(p.replace("/**", "") for p in infra))
    shas = set()
    for caminhos in grupos:
        sha = git("log", "--first-parent", "-1", "--format=%H", referencia, "--", *caminhos)
        if sha:
            shas.add(sha)
    # Dados recentes não apagam a última tentativa da imagem da mesma célula.
    faltam = {f"deploy ({c})" for c in requeridas}
    # O job de dados nasceu depois de vários deploys históricos. O workflow
    # do SHA encontrado decide se ele era exigido, em consultar_publicacao.
    # Procurá-lo aqui faria a pista atravessar todo o histórico antigo sem
    # nunca encontrar um job que ainda não existia.
    runs = []
    total = None
    for pagina in range(1, MAX_PAGINAS_DO_HISTORICO + 1):
        resposta = _api(
            raiz,
            f"actions/workflows/deploy-celula.yml/runs?per_page=100&page={pagina}",
        )
        if (not isinstance(resposta, dict)
                or not isinstance(resposta.get("workflow_runs"), list)
                or not isinstance(resposta.get("total_count"), int)):
            raise ErroDeInstrumentacao(
                "histórico de jobs ausente; imagem e dados não foram conferidos"
            )
        if total is None:
            total = resposta["total_count"]
            if total < 0 or total > MAX_PAGINAS_DO_HISTORICO * 100:
                raise ErroDeInstrumentacao(
                    "histórico excedeu o teto seguro da consulta; amplie o instrumento antes de julgar"
                )
        elif resposta["total_count"] != total:
            raise ErroDeInstrumentacao(
                "histórico mudou durante a consulta; confira novamente antes de julgar"
            )
        runs.extend(resposta["workflow_runs"])
        if len(runs) >= total:
            break
    if total is None or len(runs) != total or len({run.get("id") for run in runs}) != total:
        raise ErroDeInstrumentacao(
            "histórico de jobs ficou incompleto durante a consulta; confira novamente"
        )
    candidatos = []
    for run in runs:
        if (run.get("path") != DEPLOYS[0] or run.get("event") != "push"
                or run.get("head_branch") != "main"):
            continue
        try:
            inicio = datetime.fromisoformat(run["run_started_at"].replace("Z", "+00:00"))
        except (AttributeError, KeyError, TypeError, ValueError) as erro:
            raise ErroDeInstrumentacao(
                "histórico sem o instante da tentativa; não dá para ordenar as publicações",
                str(erro),
            ) from erro
        if inicio.tzinfo is None:
            raise ErroDeInstrumentacao(
                "histórico sem o fuso da tentativa; não dá para ordenar as publicações"
            )
        if not isinstance(run.get("id"), int) or not isinstance(run.get("run_attempt"), int):
            raise ErroDeInstrumentacao(
                "histórico sem identidade da tentativa; não dá para ordenar as publicações"
            )
        candidatos.append((inicio, run["run_attempt"], run["id"], run))
    candidatos = [item[-1] for item in sorted(
        candidatos, key=lambda item: item[:3], reverse=True
    )]

    def considerar(run, jobs):
        nonlocal faltam
        nomes = {j["name"] for j in jobs if j.get("conclusion") != "skipped"}
        encontrados = faltam & nomes
        if encontrados:
            shas.add(run["head_sha"])
            faltam -= encontrados

    if candidatos:
        considerar(candidatos[0], consultar_jobs(raiz, candidatos[0]))
    for inicio_do_lote in range(1, len(candidatos), 8):
        if not faltam:
            break
        lote = candidatos[inicio_do_lote:inicio_do_lote + 8]
        with ThreadPoolExecutor(max_workers=len(lote)) as executor:
            futuros = [(run, executor.submit(consultar_jobs, raiz, run)) for run in lote]
            for run, futuro in futuros:
                considerar(run, futuro.result())
                if not faltam:
                    for _, pendente in futuros:
                        pendente.cancel()
                    break
    if faltam:
        raise ErroDeInstrumentacao(
            "o histórico completo não prova os jobs: " + ", ".join(sorted(faltam))
        )
    resultados = []
    for sha in sorted(shas):
        alterados = git("diff", "--name-only", sha + "^", sha).splitlines()
        resultado = comprovar_sucessores(raiz, consultar_publicacao(raiz, sha, alterados))
        if not resultado["terminal"]:
            resultados.append(resultado)
    return resultados


def correcoes_declaradas(pr: dict) -> list[int]:
    linhas = re.findall(r"^\s*Corrige-publicacao:\s*([^\r\n]*)$", pr.get("body") or "", re.I | re.M)
    numeros = set()
    for linha in linhas:
        if not re.fullmatch(r"[1-9][0-9]*(?:\s*,\s*[1-9][0-9]*)*", linha.strip()):
            raise ErroDeInstrumentacao("Corrige-publicacao exige IDs de runs separados por vírgula")
        numeros.update(int(n.strip()) for n in linha.split(","))
    return sorted(numeros)


def correcao_da_publicacao(raiz: Path, pr: dict, publicacao: dict) -> bool:
    """Elegibilidade mecânica; o revisor independente julga a correção real."""
    from rerun_de_deploy import celula_do_job

    if publicacao["estado"] != "FALHA_PUBLICACAO":
        return False
    declaradas = set(correcoes_declaradas(pr))
    falhos = [r for r in publicacao.get("runs", []) if r.get("conclusion") == "failure"]
    if not falhos or any(r["id"] not in declaradas for r in falhos):
        return False
    celulas_falhas = set()
    for run in falhos:
        jobs_falhos = [j for j in run.get("jobs", []) if j.get("conclusion") == "failure"]
        if not jobs_falhos:
            return False
        for job in jobs_falhos:
            celula = celula_do_job(job.get("name") or "")
            if job.get("name") == "publicar-dados-admin":
                celula = "admin"
            if job.get("name") == "sincronizar" and run.get("workflow") == DEPLOYS[1]:
                celula = "infra"
            if not celula:
                return False
            celulas_falhas.add(celula)
    arquivos = [a["path"] for a in pr.get("files", [])]
    mapa = mapa_de_celulas.carregar(raiz)
    tocadas = set(mapa_de_celulas.celulas_do_diff(arquivos, mapa))
    if not set(publicacao.get("celulas", [])) <= tocadas:
        return False
    for celula in celulas_falhas:
        if celula == "infra":
            gatilhos = caminhos_dos_deploys(raiz)[DEPLOYS[1]]
            if not any(fnmatch.fnmatchcase(a, p) for a in arquivos for p in gatilhos):
                return False
            continue
        if celula not in mapa or not any(
            a.startswith(f"services/{celula}/") and "/tests/" not in a
            and not Path(a).name.startswith("test_")
            and (Path(a).suffix in {".py", ".html", ".js", ".css", ".sh"}
                 or a in {f"services/{celula}/Dockerfile", f"services/{celula}/requirements.txt"})
            for a in arquivos
        ):
            return False
    return True


def comprovar_sucessores(raiz: Path, publicacao: dict) -> dict:
    """Cobertura posterior é provada por job e ancestralidade, nunca só pelo SHA."""
    from rerun_de_deploy import RUNS_OLHADOS_ATRAS

    if publicacao.get("estado") != "FALHA_PUBLICACAO" or not publicacao.get("runs"):
        return publicacao
    if {r["workflow"] for r in publicacao["runs"]} != set(publicacao.get("workflows", [])):
        return publicacao
    provas = []
    comparacoes = {}
    for original in publicacao["runs"]:
        if original.get("status") != "completed":
            return publicacao
        exigidos = set(original.get("jobs_exigidos", [])) - {"detectar", "portao-de-deploy"}
        if not exigidos:
            return publicacao
        workflow = original["workflow"]
        resposta = _api(raiz, f"actions/workflows/{Path(workflow).name}/runs?branch=main&event=push&per_page={RUNS_OLHADOS_ATRAS}")
        if not isinstance(resposta, dict) or not isinstance(resposta.get("workflow_runs"), list):
            raise ErroDeInstrumentacao("GitHub não devolveu o histórico de cobertura por célula")
        candidatos = sorted((r for r in resposta["workflow_runs"]
                             if r.get("id", 0) > original["id"] and r.get("path") == workflow
                             and r.get("event") == "push" and r.get("head_branch") == "main"),
                            key=lambda r: r["id"], reverse=True)
        vistos = set()
        provados = set()
        for candidato in candidatos:
            sha = candidato.get("head_sha")
            if not re.fullmatch(r"[0-9a-f]{40}", sha or ""):
                continue
            if sha not in comparacoes:
                comparacoes[sha] = _api(raiz, f"compare/{publicacao['sha_integrado']}...{sha}").get("status")
            if comparacoes[sha] not in {"ahead", "identical"}:
                continue
            jobs = consultar_jobs(raiz, candidato)
            por_nome = {j["name"]: j for j in jobs}
            portoes = {"portao-de-deploy"} | ({"detectar"} if workflow == DEPLOYS[0] else set())
            for nome in exigidos - vistos:
                job = por_nome.get(nome)
                if not job:
                    continue
                vistos.add(nome)
                if (candidato.get("status") == "completed" and job.get("status") == "completed"
                        and job.get("conclusion") == "success"
                        and all(por_nome.get(n, {}).get("conclusion") == "success" for n in portoes)):
                    provados.add(nome)
                    provas.append(dict(workflow=workflow, job=nome, run=candidato["id"],
                                       sha=sha, url=candidato.get("html_url")))
            if vistos == exigidos:
                break
        por_nome = {j["name"]: j for j in original.get("jobs", [])}
        for nome in exigidos - vistos:
            job = por_nome.get(nome, {})
            portoes = {"portao-de-deploy"} | ({"detectar"} if workflow == DEPLOYS[0] else set())
            if (job.get("conclusion") == "success" and job.get("status") == "completed"
                    and all(por_nome.get(n, {}).get("conclusion") == "success" for n in portoes)):
                provados.add(nome)
                provas.append(dict(workflow=workflow, job=nome, run=original["id"],
                                   sha=original["sha"], url=original.get("url")))
        if provados != exigidos:
            return publicacao
    return dict(publicacao, estado="PUBLICADO", terminal=True, publicacoes=provas,
                acao="Cobertura técnica comprovada por jobs de commits que contêm a entrega. Registre os SHAs e runs; o aceite funcional continua separado.")
