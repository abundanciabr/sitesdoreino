import json
from pathlib import Path
import shlex
import subprocess
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import entregas
import ponte_entregas
from integrador_servico import Estados, Servico
from ponte_entregas import Autoridade, ErroPonte

C1 = "a" * 40
C2 = "b" * 40
BASE = "c" * 40
I1 = "111111111111"
I2 = "222222222222"


class IntegradorFalso:
    def __init__(self, regs, perda_promocao=False, diff=None, fetch_falha=False):
        self.regs = {r["id"]: r for r in regs}
        self.diff = diff or "services/aplicacao/apps/core/views.py\n"
        self.fetch_falha = fetch_falha
        self.promocoes = []
        self.perda_promocao = perda_promocao

    def cmd_integrar(self, arg):
        return 0, {}

    def todos(self):
        return [self.regs[k].copy() for k in sorted(self.regs)]

    def ler(self, id_):
        return self.regs[id_].copy()

    def git(self, *args, **kwargs):
        if args[0] == "fetch":
            if self.fetch_falha:
                raise entregas.Recusa("main indisponivel")
            return SimpleNamespace(stdout="")
        return SimpleNamespace(stdout=(self.diff.get(args[3], "") if isinstance(self.diff, dict) else self.diff))

    def cmd_promover(self, arg):
        self.promocoes.append(arg.id)
        reg = self.regs[arg.id]
        if self.perda_promocao:
            self.perda_promocao = False
            reg["promocao"] = {"estado": "intencao", "candidata": reg["candidata"],
                              "main_esperada": BASE}
            raise entregas.Recusa("resposta remota perdida")
        reg["estado"] = entregas.NA_MAIN
        reg["promovida_candidata"] = reg["candidata"]
        reg["promocao"] = {"estado": "remota", "candidata": reg["candidata"]}
        return 0, reg


class PonteFalsa:
    def __init__(self, falha_preparar=None, perda_publicar=False, falha_publicar_celula=None,
                 conciliacao=None):
        self.chamadas = []
        self.falha_preparar = falha_preparar
        self.perda_publicar = perda_publicar
        self.falha_publicar_celula = falha_publicar_celula
        self.conciliacao = conciliacao or {}
        self.provas = set()
        self.preparadas = set()

    def espelhar(self, id_, candidata):
        self.chamadas.append(("espelhar", id_))

    def conferir_preservacao(self, id_, candidata, celula):
        self.chamadas.append(("conferir-preservacao", id_))
        return self.conciliacao.get((id_, celula), {"situacao": "publicavel"})

    def preparar(self, id_, candidata, celula):
        self.chamadas.append(("preparar", id_))
        if id_ == self.falha_preparar:
            raise ErroPonte("caso comercial falhou", "ensaio")
        self.preparadas.add((id_, celula))

    def registrar(self, id_, candidata, celula):
        self.chamadas.append(("registrar", id_))
        if (id_, celula) not in self.preparadas:
            raise ErroPonte("resultado ausente", "infra")
        self.provas.add((id_, celula))

    def verificar_prova(self, id_, candidata, celula):
        self.chamadas.append(("verificar", id_))
        if (id_, celula) not in self.provas:
            raise ErroPonte("prova ausente", "recusa")
        return {"identidade": "d" * 64, "pacote_id": "e" * 64}

    def publicar(self, id_, candidata, celula):
        self.chamadas.append(("publicar", id_))
        if self.perda_publicar or self.falha_publicar_celula == celula:
            self.perda_publicar = False
            self.falha_publicar_celula = None
            raise ErroPonte("resposta perdida")


def entrega(id_, cand, deps=None):
    return {"id": id_, "estado": "pronta", "candidata": cand,
            "base_da_candidata": BASE, "depende_de": deps or []}


def servico(tmp_path, regs, ponte=None, **kwargs):
    integ = IntegradorFalso(regs, **kwargs)
    ponte = ponte or PonteFalsa()
    return Servico(integ, ponte, Estados(tmp_path / "fases")), integ, ponte


def test_perda_da_resposta_da_promocao_retoma_sem_reensaiar(tmp_path):
    worker, integ, ponte = servico(tmp_path, [entrega(I1, C1)], perda_promocao=True)
    primeiro = worker.rodada()
    assert primeiro[0]["fase"] == "promoção pendente"
    assert worker.estados.ler(I1)["diagnostico"]["codigo"] == "resposta_perdida"
    assert integ.regs[I1]["promocao"]["estado"] == "intencao"
    segundo = worker.rodada()
    assert segundo[0]["fase"] == "ativa"
    assert [c for c in ponte.chamadas if c == ("preparar", I1)] == [("preparar", I1)]
    assert integ.promocoes == [I1, I1]


def test_resposta_perdida_da_publicacao_retoma_o_mesmo_id(tmp_path):
    worker, integ, ponte = servico(tmp_path, [entrega(I1, C1)],
                                   ponte=PonteFalsa(perda_publicar=True))
    assert worker.rodada()[0]["fase"] == "ativação pendente"
    assert worker.rodada()[0]["fase"] == "ativa"
    assert integ.promocoes == [I1]
    assert [c for c in ponte.chamadas if c == ("publicar", I1)] == [
        ("publicar", I1), ("publicar", I1)]


def test_causa_da_publicacao_persiste_e_retomada_confirma_progresso(tmp_path):
    worker, _, _ = servico(tmp_path, [entrega(I1, C1)],
                           ponte=PonteFalsa(perda_publicar=True))
    assert worker.rodada()[0]["fase"] == "ativação pendente"
    pendente = worker.estados.ler(I1)
    assert pendente["diagnostico"]["codigo"] == "resposta_perdida"
    assert pendente["ultima_falha"]["codigo"] == "resposta_perdida"
    assert pendente["em_andamento"] is False
    assert pendente["progresso_em"]
    assert pendente["tentativa_em"]
    assert pendente["tentativas"] == 3  # ensaio, promoção e ativação realmente iniciados
    assert worker.rodada()[0]["fase"] == "ativa"
    concluida = worker.estados.ler(I1)
    assert concluida["diagnostico"] is None
    assert concluida["ultima_falha"]["codigo"] == "resposta_perdida"
    assert concluida["tentativas"] == 4


def test_dependencia_pendente_guarda_ids_sem_iniciar_tentativas(tmp_path):
    worker, _, _ = servico(tmp_path, [entrega(I2, C2, [I1])])
    worker.rodada()
    estado = worker.estados.ler(I2)
    assert estado["fase"] == "aguardando dependência"
    assert estado["dependencias_pendentes"] == [I1]
    assert estado["diagnostico"]["codigo"] == "dependencia_pendente"
    assert estado["tentativas"] == 0
    assert estado["progresso_em"] is None


def test_indisponibilidade_do_ensaio_nao_gasta_tentativa_real(tmp_path):
    class PonteIndisponivel(PonteFalsa):
        def preparar(self, id_, candidata, celula):
            self.chamadas.append(("preparar", id_))
            raise ErroPonte("execução indisponível", "infra")

    ponte = PonteIndisponivel()
    worker, _, _ = servico(tmp_path, [entrega(I1, C1)], ponte=ponte)
    assert worker.rodada()[0]["fase"] == "ensaiando"
    estado = worker.estados.ler(I1)
    assert estado["diagnostico"]["codigo"] == "ensaio_indisponivel"
    assert estado["tentativas"] == 0
    assert estado.get("tentativas_celula", {}).get("aplicacao", 0) == 0
    assert estado["em_andamento"] is False
    worker.rodada()
    estado = worker.estados.ler(I1)
    assert estado["proxima_tentativa_em"]
    assert estado["tentativas"] == 0
    assert worker.rodada()[0]["fase"] == "ensaiando"
    assert ponte.chamadas.count(("preparar", I1)) == 2


def test_falha_do_canal_ao_verificar_ou_registrar_nao_inicia_ensaio(tmp_path):
    class PonteFalhaProva(PonteFalsa):
        def verificar_prova(self, id_, candidata, celula):
            raise ErroPonte("autoridade indisponivel", "infra")

    class PonteFalhaRegistro(PonteFalsa):
        def registrar(self, id_, candidata, celula):
            raise ErroPonte("autoridade indisponivel", "infra")

    for ponte in (PonteFalhaProva(), PonteFalhaRegistro()):
        worker, _, _ = servico(tmp_path / str(type(ponte).__name__), [entrega(I1, C1)], ponte=ponte)
        worker.rodada()
        estado = worker.estados.ler(I1)
        assert estado["diagnostico"]["codigo"] == "autoridade_indisponivel"
        assert estado["tentativas"] == 0
        assert ("preparar", I1) not in ponte.chamadas


def test_limite_tres_ensaios_reais_preserva_ultima_causa(tmp_path):
    class PonteSemResultado(PonteFalsa):
        def registrar(self, id_, candidata, celula):
            raise ErroPonte("resultado ausente", "infra")

    worker, _, ponte = servico(tmp_path, [entrega(I1, C1)], ponte=PonteSemResultado())
    for _ in range(3):
        worker.rodada()
        estado = worker.estados.ler(I1)
        assert estado["fase"] == "ensaiando"
        estado["proxima_tentativa_em"] = "2000-01-01T00:00:00+00:00"
        worker.estados.salvar(estado)
    worker.rodada()
    estado = worker.estados.ler(I1)
    assert estado["fase"] == "falha no ensaio"
    assert estado["diagnostico"]["codigo"] == "tentativas_esgotadas"
    assert estado["ultima_falha"]["codigo"] == "resultado_ensaio_ausente"
    assert estado["tentativas"] == 3
    assert estado["tentativas_celula"]["aplicacao"] == 3


def test_registro_ilegivel_fica_isolado_e_outra_entrega_ativa(tmp_path):
    worker, integrador, _ = servico(tmp_path, [entrega(I1, C1), entrega(I2, C2)])
    ler = integrador.ler

    def ler_com_falha(id_):
        if id_ == I1:
            raise entregas.Recusa("registro ilegível /privado/marcador")
        return ler(id_)

    integrador.ler = ler_com_falha
    resultados = {r["id"]: r for r in worker.rodada()}
    assert resultados[I1]["diagnostico"]["codigo"] == "registro_ilegivel"
    assert "/privado/" not in json.dumps(resultados)
    assert resultados[I2]["fase"] == "ativa"
    assert json.loads((worker.estados.pasta / "canal.json").read_text(encoding="utf-8"))["estado"] == "rodada concluída"


def test_fase_ilegivel_nao_e_sobrescrita_nem_derruba_a_fila(tmp_path):
    worker, _, _ = servico(tmp_path, [entrega(I1, C1), entrega(I2, C2)])
    arquivo = worker.estados.pasta / (I1 + ".json")
    arquivo.write_text("{", encoding="utf-8")
    resultados = {r["id"]: r for r in worker.rodada()}
    assert resultados[I1]["diagnostico"]["codigo"] == "registro_ilegivel"
    assert arquivo.read_text(encoding="utf-8") == "{"
    assert resultados[I2]["fase"] == "ativa"


def test_dependencia_com_fase_ilegivel_aguarda_e_retoma_apos_reparo(tmp_path):
    worker, _, ponte = servico(tmp_path, [entrega(I2, C2, [I1])])
    arquivo = worker.estados.pasta / (I1 + ".json")
    arquivo.write_text("{", encoding="utf-8")
    assert worker.rodada()[0]["fase"] == "aguardando dependência"
    estado = worker.estados.ler(I2)
    assert estado["diagnostico"]["codigo"] == "registro_ilegivel"
    assert estado["dependencias_pendentes"] == [I1]
    assert ("preparar", I2) not in ponte.chamadas
    worker.estados.salvar({"id": I1, "candidata": C1, "fase": "ativa"})
    assert worker.rodada()[0]["fase"] == "ativa"


def test_espera_invalida_nao_derruba_fila(tmp_path):
    worker, _, _ = servico(tmp_path, [entrega(I1, C1)])
    for valor in (None, "sem-data", "2026-10-10T10:00:00"):
        assert worker._espera_vigente({"proxima_tentativa_em": valor}) is False


def test_canal_registra_falha_da_main_e_recuperacao_na_rodada_seguinte(tmp_path):
    worker, integrador, _ = servico(tmp_path, [entrega(I1, C1)], fetch_falha=True)
    worker.rodada()
    canal = json.loads((worker.estados.pasta / "canal.json").read_text(encoding="utf-8"))
    assert canal["estado"] == "infraestrutura indisponível"
    assert canal["diagnostico"]["codigo"] == "main_indisponivel"
    integrador.fetch_falha = False
    assert worker.rodada()[0]["fase"] == "ativa"
    canal = json.loads((worker.estados.pasta / "canal.json").read_text(encoding="utf-8"))
    assert canal["estado"] == "rodada concluída"
    assert canal["diagnostico"] is None


def test_falha_de_uma_entrega_nao_para_independente_e_dependente_aguarda(tmp_path):
    worker, integ, ponte = servico(
        tmp_path, [entrega(I1, C1), entrega(I2, C2), entrega("333333333333", "3" * 40, [I1])],
        ponte=PonteFalsa(falha_preparar=I1))
    saida = {r["id"]: r for r in worker.rodada()}
    assert saida[I1]["fase"] == "falha no ensaio"
    assert saida[I2]["fase"] == "ativa"
    assert saida["333333333333"]["fase"] == "aguardando dependência"
    assert integ.promocoes == [I2]


def test_dependencia_sem_estado_local_aguarda_ativacao(tmp_path):
    worker, integ, ponte = servico(tmp_path, [entrega(I2, C2, [I1])])
    assert worker.rodada() == [{"id": I2, "fase": "aguardando dependência"}]
    assert integ.promocoes == []
    assert ponte.chamadas == []


def test_promocao_superada_preservada_libera_dependente_sem_publicar_antiga(tmp_path):
    antiga = entrega(I1, C1)
    antiga.update(estado=entregas.NA_MAIN, promovida_candidata=C1,
                  promocao={"estado": "remota", "candidata": C1, "remoto": "integrador"})
    prova = {"situacao": "preservada", "sha_aprovada": C2,
             "prova_identidade": "d" * 64, "arquivos_conferidos": 2}
    ponte = PonteFalsa(conciliacao={(I1, "aplicacao"): prova})
    worker, integ, _ = servico(tmp_path, [antiga, entrega(I2, C2, [I1])], ponte=ponte)
    worker.estados.salvar({"id": I1, "candidata": C1, "fase": "ativação pendente",
                           "tentativas": 0, "celulas": ["aplicacao"]})
    saida = {r["id"]: r for r in worker.rodada()}
    assert saida[I1]["fase"] == "preservada em versão posterior"
    assert saida[I1]["versoes_aprovadas"] == {"aplicacao": C2}
    assert worker.estados.ler(I1)["preservacao"]["aplicacao"] == {
        "sha_aprovada": C2, "prova_identidade": "d" * 64, "arquivos_conferidos": 2}
    assert saida[I2]["fase"] == "ativa"
    assert ("espelhar", I1) not in ponte.chamadas
    assert ("publicar", I1) not in ponte.chamadas


@pytest.mark.parametrize("situacao,fase", [("aguardando", "aguardando versão posterior"),
                                           ("conflito", "preservação não comprovada")])
def test_promocao_superada_sem_prova_nao_publica_nem_libera_dependente(tmp_path, situacao, fase):
    antiga = entrega(I1, C1)
    antiga.update(estado=entregas.NA_MAIN, promovida_candidata=C1,
                  promocao={"estado": "remota", "candidata": C1, "remoto": "integrador"})
    ponte = PonteFalsa(conciliacao={(I1, "aplicacao"): {"situacao": situacao,
                                                         "motivo": "conteudo ainda nao comprovado"}})
    worker, _, _ = servico(tmp_path, [antiga, entrega(I2, C2, [I1])], ponte=ponte)
    worker.estados.salvar({"id": I1, "candidata": C1, "fase": "ativação pendente",
                           "tentativas": 0, "celulas": ["aplicacao"]})
    saida = {r["id"]: r for r in worker.rodada()}
    assert saida[I1]["fase"] == fase
    assert saida[I2]["fase"] == "aguardando dependência"
    assert ("espelhar", I1) not in ponte.chamadas
    assert ("publicar", I1) not in ponte.chamadas


def test_dependencia_pendente_e_conferida_antes_de_id_lexicalmente_anterior(tmp_path):
    anterior = entrega(I2, C2)
    anterior.update(estado=entregas.NA_MAIN, promovida_candidata=C2,
                    promocao={"estado": "remota", "candidata": C2, "remoto": "integrador"})
    ponte = PonteFalsa(conciliacao={(I2, "aplicacao"): {"situacao": "conflito",
                                                         "motivo": "conteudo da entrega mudou"}})
    worker, _, _ = servico(tmp_path, [entrega(I1, C1, [I2]), anterior], ponte=ponte)
    worker.estados.salvar({"id": I2, "candidata": C2, "fase": "ativação pendente",
                           "tentativas": 0, "celulas": ["aplicacao"]})
    saida = {r["id"]: r for r in worker.rodada()}
    assert saida[I2]["fase"] == "preservação não comprovada"
    assert saida[I1]["fase"] == "aguardando dependência"
    assert ("publicar", I1) not in ponte.chamadas


@pytest.mark.parametrize("fase_final", ["ativa", "preservada em versão posterior"])
def test_correcao_posterior_nao_reabre_entrega_historicamente_concluida(tmp_path, fase_final):
    anterior = entrega(I1, C1)
    anterior.update(estado=entregas.NA_MAIN, promovida_candidata=C1,
                    promocao={"estado": "remota", "candidata": C1, "remoto": "integrador"})
    ponte = PonteFalsa(conciliacao={(I1, "aplicacao"): {"situacao": "conflito",
                                                         "motivo": "correcao posterior no mesmo arquivo"}})
    worker, _, _ = servico(tmp_path, [anterior, entrega(I2, C2, [I1])], ponte=ponte)
    estado = {"id": I1, "candidata": C1, "fase": fase_final, "tentativas": 0,
              "celulas": ["aplicacao"], "ativadas": ["aplicacao"]}
    if fase_final == "preservada em versão posterior":
        estado["preservacao"] = {"aplicacao": {"sha_aprovada": C2,
                                              "prova_identidade": "d" * 64,
                                              "arquivos_conferidos": 1}}
    worker.estados.salvar(estado)
    saida = {r["id"]: r for r in worker.rodada()}
    assert saida[I1]["fase"] == fase_final
    assert worker.estados.ler(I1)["fase"] == fase_final
    assert saida[I2]["fase"] == "ativa"
    assert ("conferir-preservacao", I1) not in ponte.chamadas
    assert ("espelhar", I1) not in ponte.chamadas
    assert ("publicar", I1) not in ponte.chamadas


def test_entrega_historica_na_main_nao_dispara_publicacao(tmp_path):
    reg = entrega(I1, C1)
    reg.update(estado=entregas.NA_MAIN, promovida_candidata=C1)
    worker, _, ponte = servico(tmp_path, [reg])
    assert worker.rodada() == []
    assert ponte.chamadas == []


def _git(*args, cwd=None):
    return subprocess.run(["git", *map(str, args)], cwd=cwd, check=True,
                          capture_output=True, text=True).stdout.strip()


def test_espelho_importa_objeto_exato_e_recusa_registro_antigo(tmp_path, monkeypatch):
    origem, destino = tmp_path / "integrador", tmp_path / "plataforma"
    (origem / "codigo").mkdir(parents=True)
    (destino / "codigo").mkdir(parents=True)
    repo1, repo2 = origem / "codigo/repo.git", destino / "codigo/repo.git"
    publico = tmp_path / "publico.git"
    _git("init", "--bare", repo1)
    _git("init", "--bare", repo2)
    _git("init", "--bare", publico)
    monkeypatch.setattr(ponte_entregas, "REPO_PUBLICO", str(publico))
    comandos = []
    executar = ponte_entregas.subprocess.run

    def registrar_comando(comando, *args, **kwargs):
        comandos.append(comando)
        return executar(comando, *args, **kwargs)

    monkeypatch.setattr(ponte_entregas.subprocess, "run", registrar_comando)
    trabalho = tmp_path / "trabalho"
    _git("init", trabalho)
    (trabalho / "pagina.txt").write_text("versao", encoding="utf-8")
    _git("-C", trabalho, "add", ".")
    _git("-C", trabalho, "-c", "user.name=Teste", "-c", "user.email=teste@localhost",
         "commit", "-m", "pagina")
    cand = _git("-C", trabalho, "rev-parse", "HEAD")
    _git("-C", trabalho, "push", repo1, "HEAD:refs/heads/main")
    (origem / "entregas").mkdir()
    reg = {"id": I1, "candidata": cand, "estado": "pronta"}
    (origem / "entregas" / (I1 + ".json")).write_text(json.dumps(reg), encoding="utf-8")
    autoridade = Autoridade(origem, destino, tmp_path / "ferramentas")
    assert autoridade.espelhar(I1, cand)["ok"]
    assert _git("--git-dir", repo2, "rev-parse", cand + "^{commit}") == cand
    fetch = next(c for c in comandos if "fetch" in c)
    assert any(a.startswith("--upload-pack=") and
               shlex.split(a.split("=", 1)[1]) ==
               ["git", "-c", f"safe.directory={repo1}", "upload-pack"] for a in fetch)
    reg.update(estado=entregas.NA_MAIN, promovida_candidata=cand,
               promocao={"estado": "remota", "candidata": cand, "remoto": "integrador"})
    (origem / "entregas" / (I1 + ".json")).write_text(json.dumps(reg), encoding="utf-8")
    _git("-C", trabalho, "push", publico, "HEAD:refs/heads/main")
    autoridade.espelhar(I1, cand)
    assert _git("--git-dir", repo2, "rev-parse", "refs/heads/main") == cand
    assert not _git("--git-dir", repo2, "remote")
    assert any(c[0] == "git" and "ls-remote" in c and str(publico) in c for c in comandos)
    reg["promocao"]["estado"] = "intencao"
    (origem / "entregas" / (I1 + ".json")).write_text(json.dumps(reg), encoding="utf-8")
    with pytest.raises(ErroPonte, match="antigo"):
        autoridade.espelhar(I1, cand)


def test_espelho_consulta_url_publica_sem_remoto_local_ou_credenciais(tmp_path, monkeypatch):
    origem, destino = tmp_path / "integrador", tmp_path / "plataforma"
    repo1, repo2 = origem / "codigo/repo.git", destino / "codigo/repo.git"
    repo1.mkdir(parents=True)
    repo2.mkdir(parents=True)
    (origem / "entregas").mkdir()
    reg = {"id": I1, "candidata": C1, "estado": entregas.NA_MAIN,
           "promovida_candidata": C1,
           "promocao": {"estado": "remota", "candidata": C1, "remoto": "integrador"}}
    (origem / "entregas" / (I1 + ".json")).write_text(json.dumps(reg), encoding="utf-8")
    chamadas = []

    def simular_git(comando, **kwargs):
        chamadas.append((comando, kwargs))
        if "ls-remote" in comando:
            return SimpleNamespace(returncode=0, stdout=f"{C1}\trefs/heads/main\n")
        if "rev-parse" in comando:
            return SimpleNamespace(returncode=0, stdout=C1 + "\n")
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr(ponte_entregas.subprocess, "run", simular_git)
    assert Autoridade(origem, destino, tmp_path / "ferramentas").espelhar(I1, C1)["ok"]
    fetch, remoto = (next((c, kw) for c, kw in chamadas if operacao in c)
                     for operacao in ("fetch", "ls-remote"))
    assert any(a.startswith("--upload-pack=") and
               shlex.split(a.split("=", 1)[1]) ==
               ["git", "-c", f"safe.directory={repo1}", "upload-pack"] for a in fetch[0])
    assert ponte_entregas.REPO_PUBLICO in remoto[0]
    assert "integrador" not in remoto[0]
    assert remoto[1]["env"]["GIT_CONFIG_NOSYSTEM"] == "1"
    assert remoto[1]["env"]["GIT_CONFIG_GLOBAL"] == ponte_entregas.os.devnull
    assert remoto[1]["env"]["GIT_TERMINAL_PROMPT"] == "0"


def test_conciliacao_historica_exige_conteudo_preservado_e_nao_move_main(tmp_path, monkeypatch):
    origem, destino = tmp_path / "integrador", tmp_path / "plataforma"
    repo1, repo2, publico = origem / "codigo/repo.git", destino / "codigo/repo.git", tmp_path / "publico.git"
    repo1.parent.mkdir(parents=True)
    repo2.parent.mkdir(parents=True)
    for repo in (repo1, repo2, publico):
        _git("init", "--bare", repo)
    trabalho = tmp_path / "trabalho"
    _git("init", trabalho)

    def gravar(nome, texto):
        (trabalho / nome).write_text(texto, encoding="utf-8")
        _git("-C", trabalho, "add", ".")
        _git("-C", trabalho, "-c", "user.name=Teste", "-c", "user.email=teste@localhost",
             "commit", "-m", nome)
        return _git("-C", trabalho, "rev-parse", "HEAD")

    gravar("site.txt", "antes")
    base = gravar("outro.txt", "antes")
    cand = gravar("site.txt", "entrega antiga")
    nova = gravar("outro.txt", "entrega posterior")
    for repo in (repo1, publico):
        _git("-C", trabalho, "push", repo, "HEAD:refs/heads/main")
    _git("--git-dir", repo2, "fetch", repo1, nova)
    _git("--git-dir", repo2, "update-ref", "refs/heads/main", nova)
    (origem / "entregas").mkdir()
    reg = {"id": I1, "candidata": cand, "promovida_candidata": cand,
           "estado": entregas.NA_MAIN, "base_da_candidata": base,
           "promocao": {"estado": "remota", "candidata": cand, "remoto": "integrador",
                        "prova_identidade": "d" * 64}}
    (origem / "entregas" / (I1 + ".json")).write_text(json.dumps(reg), encoding="utf-8")
    publicacoes = destino / "publicacoes"
    publicacoes.mkdir()
    (publicacoes / ".ativacao.lock").touch()
    pacote = {"id": "e" * 64}
    journal = {"atual": nova, "servicos": ["aplicacao"],
               "aprovada": {"sha": nova, "pacote": pacote}}
    arquivo = publicacoes / "aplicacao.json"
    arquivo.write_text(json.dumps(journal), encoding="utf-8")
    monkeypatch.setattr(ponte_entregas, "REPO_PUBLICO", str(publico))
    autoridade = Autoridade(origem, destino, tmp_path / "ferramentas")
    ensaio = SimpleNamespace(RecusaEnsaio=RuntimeError,
                             verificar_prova=lambda plataforma, sha, ferramentas, celula: {
                                 "identidade": "d" * 64, "candidata": sha, "celula": celula,
                                 "pacote_publicador": pacote})
    monkeypatch.setattr(autoridade, "_ensaio", lambda: ensaio)
    executar = ponte_entregas.subprocess.run
    chamadas = []

    def simular_container(comando, *args, **kwargs):
        chamadas.append(comando)
        if comando[-1] == "conferir-atual":
            return SimpleNamespace(returncode=0)
        if comando[:4] == ["docker", "compose", "ps", "-q"]:
            return SimpleNamespace(returncode=0, stdout="container-aprovado\n")
        if comando[:2] == ["docker", "inspect"]:
            return SimpleNamespace(returncode=0, stdout='{"Running":true,"Health":{"Status":"healthy"}}')
        return executar(comando, *args, **kwargs)

    monkeypatch.setattr(ponte_entregas.subprocess, "run", simular_container)
    resposta = autoridade.conferir_preservacao(I1, cand, "aplicacao")
    assert resposta["situacao"] == "preservada"
    assert resposta["sha_aprovada"] == nova
    assert resposta["arquivos_conferidos"] == 1
    assert not any("update-ref" in comando for comando in chamadas)
    assert _git("--git-dir", repo2, "rev-parse", "refs/heads/main") == nova

    posterior = gravar("site.txt", "entrega antiga alterada")
    for repo in (repo1, publico):
        _git("-C", trabalho, "push", repo, "HEAD:refs/heads/main")
    _git("--git-dir", repo2, "fetch", repo1, posterior)
    arquivo.write_text(json.dumps({"atual": posterior, "servicos": ["aplicacao"],
                                   "aprovada": {"sha": posterior, "pacote": pacote}}), encoding="utf-8")
    resposta = autoridade.conferir_preservacao(I1, cand, "aplicacao")
    assert resposta["situacao"] == "conflito"
    assert "alterou arquivos" in resposta["motivo"]
    assert _git("--git-dir", repo2, "rev-parse", "refs/heads/main") == nova


def test_ponte_recusa_caminho_e_acao_arbitraria(tmp_path):
    autoridade = Autoridade(tmp_path / "a", tmp_path / "b", tmp_path / "c")
    with pytest.raises(ErroPonte, match="formato"):
        autoridade.atender({"acao": "espelhar", "id": I1, "candidata": C1,
                            "celula": "aplicacao", "caminho": "/etc/shadow"})
    with pytest.raises(ErroPonte, match="acao"):
        autoridade.atender({"acao": "shell", "id": I1, "candidata": C1,
                            "celula": "aplicacao"})



def test_entrega_mista_prova_e_ativa_as_duas_celulas_em_ordem(tmp_path):
    diff = "services/aplicacao/apps/core/views.py\nservices/funil/apps/web/views.py\n"
    worker, integ, ponte = servico(tmp_path, [entrega(I1, C1)], diff=diff)
    assert worker.rodada()[0]["fase"] == "ativa"
    assert [c for c in ponte.chamadas if c[0] == "preparar"] == [
        ("preparar", I1), ("preparar", I1)]
    assert [c for c in ponte.chamadas if c[0] == "publicar"] == [
        ("publicar", I1), ("publicar", I1)]
    assert worker.estados.ler(I1)["ativadas"] == ["aplicacao", "funil"]


def test_main_remota_indisponivel_nao_integra_nem_promove(tmp_path):
    worker, integ, ponte = servico(tmp_path, [entrega(I1, C1)], fetch_falha=True)
    assert worker.rodada()[0]["fase"] == "infraestrutura indisponível"
    assert integ.promocoes == []
    assert ponte.chamadas == []


def test_prova_devolve_so_identificadores_sem_hash_privado(tmp_path, monkeypatch):
    autoridade = Autoridade(tmp_path / "a", tmp_path / "b", tmp_path / "c")
    monkeypatch.setattr(autoridade, "espelhar", lambda id_, cand: {"ok": True})
    prova = {"candidata": C1, "celula": "funil", "resultado": "aprovado",
             "identidade": "d" * 64, "pacote_publicador": {"id": "e" * 64},
             "configuracao": "SEGREDO-HASH", "artefato": {"codigo": "/privado"}}
    fake = SimpleNamespace(verificar_prova=lambda *args: prova, RecusaEnsaio=RuntimeError)
    monkeypatch.setattr(autoridade, "_ensaio", lambda: fake)
    arquivo = autoridade.plataforma / "entregas/provas" / (C1 + "-funil.json")
    arquivo.parent.mkdir(parents=True)
    arquivo.write_text(json.dumps(prova), encoding="utf-8")
    resposta = autoridade.verificar_prova(I1, C1, "funil")
    assert set(resposta) == {"ok", "identidade", "pacote_id"}
    assert "SEGREDO-HASH" not in json.dumps(resposta)


def test_mista_parcial_retoma_funil_sem_repetir_aplicacao(tmp_path):
    diff = "services/aplicacao/a.py\nservices/funil/b.py\n"
    ponte = PonteFalsa(falha_publicar_celula="funil")
    worker, integ, _ = servico(tmp_path, [entrega(I1, C1)], ponte=ponte, diff=diff)
    assert worker.rodada()[0]["fase"] == "ativação pendente"
    assert worker.estados.ler(I1)["ativadas"] == ["aplicacao"]
    reiniciado = Servico(integ, ponte, Estados(tmp_path / "fases"))
    assert reiniciado.rodada()[0]["fase"] == "ativa"
    assert [c for c in ponte.chamadas if c == ("publicar", I1)] == [
        ("publicar", I1), ("publicar", I1), ("publicar", I1)]


def test_erro_de_celula_em_uma_entrega_nao_para_outra(tmp_path):
    worker, integ, ponte = servico(
        tmp_path, [entrega(I1, C1), entrega(I2, C2)],
        diff={C1: "", C2: "services/aplicacao/a.py\n"})
    saida = {r["id"]: r for r in worker.rodada()}
    assert saida[I1]["fase"] == "precisa de correção"
    assert saida[I2]["fase"] == "ativa"
