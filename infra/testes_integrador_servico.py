import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import entregas
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
    def __init__(self, falha_preparar=None, perda_publicar=False, falha_publicar_celula=None):
        self.chamadas = []
        self.falha_preparar = falha_preparar
        self.perda_publicar = perda_publicar
        self.falha_publicar_celula = falha_publicar_celula
        self.provas = set()
        self.preparadas = set()

    def espelhar(self, id_, candidata):
        self.chamadas.append(("espelhar", id_))

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


def test_entrega_historica_na_main_nao_dispara_publicacao(tmp_path):
    reg = entrega(I1, C1)
    reg.update(estado=entregas.NA_MAIN, promovida_candidata=C1)
    worker, _, ponte = servico(tmp_path, [reg])
    assert worker.rodada() == []
    assert ponte.chamadas == []


def _git(*args, cwd=None):
    return subprocess.run(["git", *map(str, args)], cwd=cwd, check=True,
                          capture_output=True, text=True).stdout.strip()


def test_espelho_importa_objeto_exato_e_recusa_registro_antigo(tmp_path):
    origem, destino = tmp_path / "integrador", tmp_path / "plataforma"
    (origem / "codigo").mkdir(parents=True)
    (destino / "codigo").mkdir(parents=True)
    repo1, repo2 = origem / "codigo/repo.git", destino / "codigo/repo.git"
    _git("init", "--bare", repo1)
    _git("init", "--bare", repo2)
    _git("--git-dir", repo2, "remote", "add", "integrador", repo1)
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
    reg.update(estado=entregas.NA_MAIN, promovida_candidata=cand,
               promocao={"estado": "remota", "candidata": cand, "remoto": "integrador"})
    (origem / "entregas" / (I1 + ".json")).write_text(json.dumps(reg), encoding="utf-8")
    autoridade.espelhar(I1, cand)
    reg["promocao"]["estado"] = "intencao"
    (origem / "entregas" / (I1 + ".json")).write_text(json.dumps(reg), encoding="utf-8")
    with pytest.raises(ErroPonte, match="antigo"):
        autoridade.espelhar(I1, cand)


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
