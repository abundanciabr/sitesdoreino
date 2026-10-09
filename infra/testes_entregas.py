"""Testes do integrador de entregas (infra/entregas.py). Rodar: python -m pytest infra/testes_entregas.py -q"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent / "entregas.py"
ID = ["-c", "user.name=x", "-c", "user.email=x@x"]
LINHAS = "\n".join("linha %02d" % i for i in range(1, 21)) + "\n"


def sh(cwd, *args):
    r = subprocess.run(["git", *ID, *args], cwd=str(cwd), capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, "git %s: %s" % (args, r.stderr)
    return r.stdout.strip()


class Ambiente:
    def __init__(self, tmp, monkeypatch):
        self.plat = tmp / "plat"
        self.origin = self.plat / "codigo" / "repo.git"
        self.origin.parent.mkdir(parents=True)
        self.work = tmp / "work"
        monkeypatch.setenv("PLATAFORMA_DIR", str(self.plat))
        sh(tmp, "init", "-q", "--bare", "-b", "main", str(self.origin))
        sh(tmp, "clone", "-q", str(self.origin), str(self.work))
        sh(self.work, "checkout", "-q", "-B", "main")
        self.escrever("base.txt", "base\n")
        self.escrever("compartilhado.txt", LINHAS)
        self.escrever("admin.txt", "pagina\nTornar ADMIN\nfim\n")
        sh(self.work, "add", "-A")
        sh(self.work, "commit", "-q", "-m", "inicio")
        sh(self.work, "push", "-q", "origin", "main")
        self.base = sh(self.work, "rev-parse", "HEAD")

    def escrever(self, nome, texto):
        (self.work / nome).write_text(texto, encoding="utf-8", newline="\n")

    def ramo(self, nome, arquivos, de=None, remover=()):
        """Cria commit em ramo a partir de `de` (padrão: base inicial) e envia ao origin."""
        sh(self.work, "checkout", "-q", "-B", nome, de or self.base)
        for n, t in arquivos.items():
            self.escrever(n, t)
        for n in remover:
            (self.work / n).unlink()
        sh(self.work, "add", "-A")
        sh(self.work, "commit", "-q", "-m", "ramo " + nome)
        sh(self.work, "push", "-q", "-f", "origin", "%s:refs/heads/%s" % (nome, nome))
        return sh(self.work, "rev-parse", "HEAD")

    def avancar_main(self, arquivos):
        sh(self.work, "checkout", "-q", "main")
        sh(self.work, "pull", "-q", "--ff-only", "origin", "main")
        for n, t in arquivos.items():
            self.escrever(n, t)
        sh(self.work, "add", "-A")
        sh(self.work, "commit", "-q", "-m", "main avancou")
        sh(self.work, "push", "-q", "origin", "main")
        return sh(self.work, "rev-parse", "HEAD")

    def cli(self, *args):
        r = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True,
                           encoding="utf-8", env=None)
        linhas = r.stdout.strip().splitlines()
        assert len(linhas) == 1, "saida deve ser uma linha JSON: %r / %s" % (r.stdout, r.stderr)
        return r.returncode, json.loads(linhas[0])

    def entregar(self, ramo, sha, *extra, base=None):
        cod, reg = self.cli("entregar", "--ramo", ramo, "--commit", sha, "--base", base or self.base, *extra)
        assert cod == 0, reg
        return reg

    def integrar(self):
        cod, saida = self.cli("integrar")
        assert cod == 0, saida
        return {e["id"]: e for e in saida["entregas"]}

    def promover(self, id_, *extra):
        return self.cli("promover", id_, *extra)

    def consultar(self, id_):
        cod, reg = self.cli("consultar", id_)
        assert cod == 0
        return reg

    def main(self):
        return sh(self.origin, "rev-parse", "refs/heads/main")

    def arquivo_na_main(self, nome):
        return sh(self.origin, "show", "refs/heads/main:" + nome)

    def tem_ref(self, id_):
        r = subprocess.run(["git", "--git-dir", str(self.origin), "rev-parse", "--verify", "--quiet",
                            "refs/entregas/" + id_], capture_output=True, text=True)
        return r.returncode == 0

    def conflito(self):
        """Prepara main que alterou a linha 05 e devolve ramo que altera a mesma linha de outro jeito."""
        self.avancar_main({"compartilhado.txt": LINHAS.replace("linha 05", "linha 05 da main")})
        return self.ramo("rob-conf", {"compartilhado.txt": LINHAS.replace("linha 05", "linha 05 do robo")})


@pytest.fixture
def amb(tmp_path, monkeypatch):
    return Ambiente(tmp_path, monkeypatch)


def test_C01_dois_arquivos_diferentes_viram_prontas_e_entram_em_sequencia(amb):
    a = amb.entregar("rob-a", amb.ramo("rob-a", {"a.txt": "A\n"}))["id"]
    b = amb.entregar("rob-b", amb.ramo("rob-b", {"b.txt": "B\n"}))["id"]
    est = amb.integrar()
    assert est[a]["estado"] == "pronta" and est[b]["estado"] == "pronta"
    cod, _ = amb.promover(a)
    assert cod == 0
    est = amb.integrar()
    assert est[a]["estado"] == "integrada na main"
    assert est[b]["estado"] == "pronta"
    assert amb.consultar(b)["base_da_candidata"] == amb.main()
    cod, _ = amb.promover(b)
    assert cod == 0
    assert amb.arquivo_na_main("a.txt") == "A" and amb.arquivo_na_main("b.txt") == "B"
    assert amb.consultar(b)["estado"] == "integrada na main"


def test_C02_trechos_diferentes_do_mesmo_arquivo_preservam_os_dois(amb):
    topo = LINHAS.replace("linha 02", "linha 02 do A")
    fim = LINHAS.replace("linha 19", "linha 19 do B")
    a = amb.entregar("rob-a", amb.ramo("rob-a", {"compartilhado.txt": topo}))["id"]
    b = amb.entregar("rob-b", amb.ramo("rob-b", {"compartilhado.txt": fim}))["id"]
    amb.integrar()
    assert amb.promover(a)[0] == 0
    est = amb.integrar()
    assert est[b]["estado"] == "pronta"
    assert amb.promover(b)[0] == 0
    texto = amb.arquivo_na_main("compartilhado.txt")
    assert "linha 02 do A" in texto and "linha 19 do B" in texto


def test_C03_mesmo_trecho_incompativel_da_conflito_e_nao_mexe_na_main(amb):
    sha = amb.conflito()
    main_antes = amb.main()
    id_ = amb.entregar("rob-conf", sha)["id"]
    est = amb.integrar()
    assert est[id_]["estado"] == "conflito"
    reg = amb.consultar(id_)
    assert reg["conflitos"] == ["compartilhado.txt"]
    assert "compartilhado.txt" in reg["motivo"]
    assert amb.main() == main_antes
    assert not amb.tem_ref(id_)
    assert amb.promover(id_)[0] == 2


def test_C04_reenvio_nao_duplica_e_conteudo_ja_na_main_e_reconhecido(amb):
    sha = amb.ramo("rob-a", {"a.txt": "A\n"})
    r1 = amb.entregar("rob-a", sha)
    r2 = amb.entregar("rob-a", sha)
    assert r1["id"] == r2["id"]
    assert len(list((amb.plat / "entregas").glob("*.json"))) == 1
    cod, todos = amb.cli("consultar")
    assert cod == 0 and len(todos) == 1
    # cherry-pick previo na main: commit diferente, mesmo patch
    sh(amb.work, "checkout", "-q", "main")
    sh(amb.work, "cherry-pick", sha)
    sh(amb.work, "push", "-q", "origin", "main")
    sha2 = amb.ramo("rob-copia", {"c.txt": "C\n"})
    sh(amb.work, "checkout", "-q", "main")
    sh(amb.work, "cherry-pick", sha2)
    sh(amb.work, "push", "-q", "origin", "main")
    reg = amb.entregar("rob-copia", sha2)
    assert reg["estado"] == "integrada na main"
    assert reg["motivo"] == "conteúdo presente na main atual"


def test_C05_main_avanca_promover_recusa_e_integrar_recombina(amb):
    id_ = amb.entregar("rob-a", amb.ramo("rob-a", {"a.txt": "A\n"}))["id"]
    assert amb.integrar()[id_]["estado"] == "pronta"
    antiga = amb.consultar(id_)["candidata"]
    amb.avancar_main({"externo.txt": "fora\n"})
    main_nova = amb.main()
    cod, saida = amb.promover(id_)
    assert cod == 2 and "main mudou" in saida["motivo"]
    assert amb.main() == main_nova
    assert amb.integrar()[id_]["estado"] == "pronta"
    reg = amb.consultar(id_)
    assert reg["candidata"] != antiga and reg["base_da_candidata"] == main_nova
    assert amb.promover(id_)[0] == 0
    assert amb.arquivo_na_main("a.txt") == "A" and amb.arquivo_na_main("externo.txt") == "fora"


def test_C06_so_candidata_do_integrar_promove(amb):
    a = amb.entregar("rob-a", amb.ramo("rob-a", {"a.txt": "A\n"}))["id"]
    sha_isolado = amb.ramo("rob-x", {"x.txt": "X\n"})
    amb.integrar()
    assert amb.promover(a)[0] == 0
    main_antes = amb.main()
    cod, saida = amb.promover(sha_isolado)  # SHA solto
    assert cod == 2
    b = amb.entregar("rob-x", sha_isolado)["id"]
    cod, _ = amb.promover(b)  # registrada, mas ainda sem candidata
    assert cod == 2
    assert amb.main() == main_antes
    assert amb.arquivo_na_main("a.txt") == "A"
    assert sh(amb.origin, "cat-file", "-t", sha_isolado) == "commit"
    assert subprocess.run(["git", "--git-dir", str(amb.origin), "merge-base", "--is-ancestor", sha_isolado,
                           "refs/heads/main"]).returncode == 1


def test_C07_remocao_em_descendente_da_main_integra_e_fica_listada(amb):
    """Ancestralidade nao detecta remocao: o commit descende da main, integra sem conflito e
    o unico aviso e o arquivo listado em 'arquivos' (quem revisa decide)."""
    sha = amb.ramo("rob-rm", {"admin.txt": "pagina\nfim\n"})
    reg = amb.entregar("rob-rm", sha)
    assert "admin.txt" in reg["arquivos"]
    est = amb.integrar()
    assert est[reg["id"]]["estado"] == "pronta"
    assert amb.consultar(reg["id"])["conflitos"] == []
    assert amb.promover(reg["id"])[0] == 0
    assert "Tornar ADMIN" not in amb.arquivo_na_main("admin.txt")


def test_C09_conflito_de_uma_nao_trava_a_independente(amb):
    sha_conf = amb.conflito()
    a = amb.entregar("rob-conf", sha_conf)["id"]
    b = amb.entregar("rob-b", amb.ramo("rob-b", {"b.txt": "B\n"}))["id"]
    est = amb.integrar()
    assert est[a]["estado"] == "conflito" and est[b]["estado"] == "pronta"
    assert amb.promover(b)[0] == 0
    assert amb.arquivo_na_main("b.txt") == "B"
    assert amb.consultar(a)["estado"] == "conflito"


def test_C11_dependente_espera_a_entrega_em_conflito(amb):
    sha_conf = amb.conflito()
    a = amb.entregar("rob-conf", sha_conf)["id"]
    b = amb.entregar("rob-b", amb.ramo("rob-b", {"b.txt": "B\n"}), "--depende-de", a)["id"]
    est = amb.integrar()
    assert est[a]["estado"] == "conflito"
    assert est[b]["estado"] == "aguardando dependência"
    assert a in est[b]["motivo"]
    assert amb.promover(b)[0] == 2
    cod = subprocess.run(["git", "--git-dir", str(amb.origin), "cat-file", "-e", "refs/heads/main:b.txt"]).returncode
    assert cod != 0


def test_retomada_de_registro_integrando_nao_duplica_candidata(amb):
    id_ = amb.entregar("rob-a", amb.ramo("rob-a", {"a.txt": "A\n"}))["id"]
    # queda antes de gravar a candidata
    caminho = amb.plat / "entregas" / (id_ + ".json")
    reg = json.loads(caminho.read_text(encoding="utf-8"))
    reg["estado"] = "integrando"
    caminho.write_text(json.dumps(reg), encoding="utf-8")
    assert amb.integrar()[id_]["estado"] == "pronta"
    primeira = amb.consultar(id_)["candidata"]
    # queda depois do update-ref, antes de gravar o registro
    reg = amb.consultar(id_)
    reg.update(estado="integrando", candidata=None, base_da_candidata=None)
    caminho.write_text(json.dumps(reg), encoding="utf-8")
    assert amb.integrar()[id_]["estado"] == "pronta"
    assert amb.consultar(id_)["candidata"] == primeira
    refs = sh(amb.origin, "for-each-ref", "refs/entregas/")
    assert len(refs.splitlines()) == 1
    assert amb.promover(id_)[0] == 0


def test_commit_inexistente_ou_base_invalida_precisa_de_correcao(amb):
    reg = amb.entregar("rob-fantasma", "1" * 40)
    assert reg["estado"] == "precisa de correção" and "reenvie" in reg["motivo"]
    sha = amb.ramo("rob-a", {"a.txt": "A\n"})
    outro = amb.ramo("rob-o", {"o.txt": "O\n"})
    reg = amb.entregar("rob-a", sha, base=outro)  # base nao e ancestral
    assert reg["estado"] == "precisa de correção"


def test_ramo_movido_depois_nao_muda_a_entrega(amb):
    sha = amb.ramo("rob-a", {"a.txt": "A\n"})
    id_ = amb.entregar("rob-a", sha)["id"]
    amb.ramo("rob-a", {"a.txt": "OUTRO\n"})  # robo move o ramo
    amb.integrar()
    assert amb.consultar(id_)["commit"] == sha
    assert amb.promover(id_)[0] == 0
    assert amb.arquivo_na_main("a.txt") == "A"


def test_promover_com_remoto_empurra_e_atualiza_main_local(amb, tmp_path):
    # repo do integrador separado do remoto real (GitHub simulado)
    github = tmp_path / "github.git"
    sh(tmp_path, "clone", "-q", "--bare", str(amb.origin), str(github))
    sh(amb.origin, "remote", "add", "github", str(github))
    id_ = amb.entregar("rob-a", amb.ramo("rob-a", {"a.txt": "A\n"}))["id"]
    amb.integrar()
    cod, _ = amb.promover(id_, "--remoto", "github")
    assert cod == 0
    assert sh(github, "rev-parse", "refs/heads/main") == amb.main()
    assert sh(github, "show", "refs/heads/main:a.txt") == "A"



# ---------------------------------------------------------------- achados da revisão adversarial
import hashlib  # noqa: E402


def idde(ramo, sha):
    return hashlib.sha256((ramo + "\n" + sha).encode("utf-8")).hexdigest()[:12]


def refs(amb, padrao):
    return sh(amb.origin, "for-each-ref", "--format=%(refname)", padrao).splitlines()


def test_seguranca_ramo_e_remoto_hostis_sao_recusados_sem_executar_nada(amb, tmp_path):
    sha = amb.ramo("rob-a", {"a.txt": "A\n"})
    marca = tmp_path / "executou.txt"
    main_antes = amb.main()
    for ramo in ("--upload-pack=echo x > %s" % marca.as_posix(), "+refs/heads/evil:refs/heads/main",
                 "a:b", "a/../b", "-x", "a b", ""):
        cod, saida = amb.cli("entregar", "--ramo=" + ramo, "--commit", "1" * 40, "--base", amb.base)
        assert cod == 2 and saida["recusado"], ramo
    cod, saida = amb.cli("entregar", "--ramo", "rob-a", "--commit", sha, "--base", amb.base,
                         "--remoto=--upload-pack=echo x")
    assert cod == 2
    cod, saida = amb.cli("entregar", "--ramo", "rob-a", "--commit", "1" * 40, "--base", amb.base,
                         "--remoto=-oProxyCommand=x")
    assert cod == 2
    assert not marca.exists() and amb.main() == main_antes
    assert refs(amb, "refs/entregas*") == []


def test_seguranca_commit_e_base_precisam_ser_sha_completo(amb):
    sha = amb.ramo("rob-a", {"a.txt": "A\n"})
    for commit, base in (("rob-a", amb.base), (sha[:10], amb.base), (sha.upper(), amb.base),
                         (sha, "main"), (sha, amb.base[:8])):
        cod, saida = amb.cli("entregar", "--ramo", "rob-a", "--commit", commit, "--base", base)
        assert cod == 2 and "inválido" in saida["motivo"], (commit, base)
    assert list((amb.plat / "entregas").glob("*.json")) == []
    # mesmo commit com ramo de nome diferente e outro id; maiusculas no nome do ramo sao preservadas
    r1 = amb.entregar("rob-a", sha)
    r2 = amb.entregar("Rob-A", sha)
    assert r1["id"] != r2["id"] and r2["ramo"] == "Rob-A"
    assert r1["id"] == idde("rob-a", sha)


def test_seguranca_id_com_caminho_nao_le_arquivo_fora_de_entregas(amb):
    (amb.plat / "segredo.json").write_text('{"token": "XXXX"}', encoding="utf-8")
    for ruim in ("../segredo", "..\\segredo", "segredo", "A" * 12):
        cod, saida = amb.cli("consultar", ruim)
        assert cod == 2 and "XXXX" not in json.dumps(saida), ruim
        cod, saida = amb.promover(ruim)
        assert cod == 2
    cod, saida = amb.cli("entregar", "--ramo", "rob-a", "--commit", "1" * 40, "--base", amb.base,
                         "--depende-de", "../segredo")
    assert cod == 2


def test_registro_corrompido_nao_trava_as_outras_entregas(amb):
    a = amb.entregar("rob-a", amb.ramo("rob-a", {"a.txt": "A\n"}))["id"]
    (amb.plat / "entregas" / "zzzz.json").write_text("{quebrado", encoding="utf-8")
    cod, lista = amb.cli("estado")
    assert cod == 0 and any(r["estado"] == "registro ilegível" for r in lista)
    est = amb.integrar()
    assert est[a]["estado"] == "pronta"
    cod, saida = amb.cli("consultar", "abcdef012345")
    assert cod == 2
    (amb.plat / "entregas" / "abcdef012345.json").write_text("{quebrado", encoding="utf-8")
    cod, saida = amb.cli("consultar", "abcdef012345")
    assert cod == 2 and "ilegível" in saida["motivo"]
    assert amb.promover(a)[0] == 0


def test_C08_fetch_automatico_traz_o_commit_ausente_sem_mexer_em_refs_nomeadas(amb, tmp_path):
    externo = tmp_path / "externo.git"
    sh(tmp_path, "clone", "-q", "--bare", str(amb.origin), str(externo))
    sh(amb.origin, "remote", "add", "ext", str(externo))
    sh(amb.work, "remote", "add", "ext", str(externo))
    sh(amb.work, "checkout", "-q", "-B", "rob-ext", amb.base)
    amb.escrever("e.txt", "E\n")
    sh(amb.work, "add", "-A")
    sh(amb.work, "commit", "-q", "-m", "externo")
    sha = sh(amb.work, "rev-parse", "HEAD")
    sh(amb.work, "push", "-q", "ext", "rob-ext")
    main_antes = amb.main()
    assert subprocess.run(["git", "--git-dir", str(amb.origin), "cat-file", "-e", sha]).returncode != 0
    reg = amb.entregar("rob-ext", sha, "--remoto", "ext")
    assert reg["estado"] == "recebida" and reg["arquivos"] == ["e.txt"]
    assert amb.main() == main_antes
    assert refs(amb, "refs/heads/rob-ext") == [] and refs(amb, "refs/entregas/") == []
    assert amb.integrar()[reg["id"]]["estado"] == "pronta"


def test_entrega_sem_main_precisa_de_correcao(tmp_path, monkeypatch):
    plat = tmp_path / "plat"
    (plat / "codigo").mkdir(parents=True)
    monkeypatch.setenv("PLATAFORMA_DIR", str(plat))
    sh(tmp_path, "init", "-q", "--bare", "-b", "main", str(plat / "codigo" / "repo.git"))
    work = tmp_path / "w"
    sh(tmp_path, "clone", "-q", str(plat / "codigo" / "repo.git"), str(work))
    sh(work, "checkout", "-q", "-B", "r")
    (work / "x").write_text("x\n")
    sh(work, "add", "-A")
    sh(work, "commit", "-q", "-m", "x")
    sha = sh(work, "rev-parse", "HEAD")
    sh(work, "push", "-q", "origin", "r")
    amb = Ambiente.__new__(Ambiente)
    cod, reg = amb.cli("entregar", "--ramo", "r", "--commit", sha, "--base", sha)
    assert cod == 0 and reg["estado"] == "precisa de correção" and "main" in reg["motivo"]


def test_C07_remocao_real_fica_em_removidos(amb):
    sha = amb.ramo("rob-rm", {"b.txt": "B\n"}, remover=("admin.txt",))
    reg = amb.entregar("rob-rm", sha)
    assert reg["removidos"] == ["admin.txt"]
    assert sorted(reg["arquivos"]) == ["admin.txt", "b.txt"]
    # base antiga: 'arquivos' vale em relacao a main, nao a --base
    amb.avancar_main({"externo.txt": "fora\n"})
    sha2 = amb.ramo("rob-novo", {"n.txt": "N\n"}, de=amb.main())
    reg2 = amb.entregar("rob-novo", sha2, base=amb.base)
    assert reg2["arquivos"] == ["n.txt"] and reg2["removidos"] == []


def test_C10_conflito_com_nome_nao_ascii_e_reenvio_contam_tentativas(amb):
    amb.avancar_main({"ação é.txt": LINHAS.replace("linha 05", "linha 05 da main")})
    sha = amb.ramo("rob-conf", {"ação é.txt": LINHAS.replace("linha 05", "linha 05 do robo")})
    id_ = amb.entregar("rob-conf", sha)["id"]
    assert amb.integrar()[id_]["estado"] == "conflito"
    reg = amb.consultar(id_)
    assert reg["conflitos"] == ["ação é.txt"] and "ação é.txt" in reg["motivo"]
    # reenviar o mesmo commit em conflito: segue em conflito, sem duplicar
    assert amb.entregar("rob-conf", sha)["id"] == id_
    assert len(list((amb.plat / "entregas").glob("*.json"))) == 1


def test_C04_reenvio_em_correcao_conta_tentativa_e_cherry_pick_posterior_vira_na_main(amb):
    reg = amb.entregar("rob-a", "1" * 40)
    assert reg["estado"] == "precisa de correção" and reg["tentativas"] == 0
    reg = amb.entregar("rob-a", "1" * 40)
    assert reg["tentativas"] == 1
    sha = amb.ramo("rob-b", {"b.txt": "B\n"})
    id_ = amb.entregar("rob-b", sha)["id"]
    assert amb.consultar(id_)["estado"] == "recebida"
    sh(amb.work, "checkout", "-q", "main")
    sh(amb.work, "pull", "-q", "--ff-only", "origin", "main")
    sh(amb.work, "cherry-pick", sha)
    sh(amb.work, "push", "-q", "origin", "main")
    assert amb.integrar()[id_]["estado"] == "integrada na main"
    assert amb.tem_ref(id_) is False
    assert refs(amb, "refs/entregas-fixas/") == []


def test_C11_dependencia_inexistente_ciclo_correcao_cadeia_e_liberacao(amb):
    # inexistente
    fantasma = "0123456789ab"
    x = amb.entregar("rob-x", amb.ramo("rob-x", {"x.txt": "X\n"}), "--depende-de", fantasma)["id"]
    est = amb.integrar()
    assert est[x]["estado"] == "aguardando dependência" and fantasma in est[x]["motivo"]
    # ciclo A <-> B
    sa = amb.ramo("rob-a", {"a.txt": "A\n"})
    sb = amb.ramo("rob-b", {"b.txt": "B\n"})
    ia, ib = idde("rob-a", sa), idde("rob-b", sb)
    amb.entregar("rob-a", sa, "--depende-de", ib)
    amb.entregar("rob-b", sb, "--depende-de", ia)
    est = amb.integrar()
    circ = [e for e in (est[ia], est[ib]) if e["estado"] == "precisa de correção"]
    assert len(circ) == 1 and "dependência circular" in circ[0]["motivo"]
    assert ia in circ[0]["motivo"] and ib in circ[0]["motivo"]
    ia = circ[0]["id"]  # a que recebeu a correção
    # auto-dependencia
    sc = amb.ramo("rob-c", {"c.txt": "C\n"})
    ic = idde("rob-c", sc)
    amb.entregar("rob-c", sc, "--depende-de", ic)
    assert amb.integrar()[ic]["motivo"].startswith("dependência circular")
    # dependencia em 'precisa de correção'
    d = amb.entregar("rob-d", amb.ramo("rob-d", {"d.txt": "D\n"}), "--depende-de", ia)["id"]
    est = amb.integrar()
    assert est[d]["estado"] == "aguardando dependência" and "precisa de correção" in est[d]["motivo"]


def test_C11_cadeia_de_tres_elos_aponta_a_raiz_e_segue_depois_de_promover(amb):
    sha_conf = amb.conflito()
    c = amb.entregar("rob-conf", sha_conf)["id"]
    b = amb.entregar("rob-b", amb.ramo("rob-b", {"b.txt": "B\n"}), "--depende-de", c)["id"]
    a = amb.entregar("rob-a", amb.ramo("rob-a", {"a.txt": "A\n"}), "--depende-de", b)["id"]
    est = amb.integrar()
    assert est[a]["estado"] == "aguardando dependência" and c in est[a]["motivo"] and "conflito" in est[a]["motivo"]
    # cadeia saudável: dependente segue depois de a dependência ser promovida
    p = amb.entregar("rob-p", amb.ramo("rob-p", {"p.txt": "P\n"}))["id"]
    q = amb.entregar("rob-q", amb.ramo("rob-q", {"q.txt": "Q\n"}), "--depende-de", p)["id"]
    est = amb.integrar()
    assert est[p]["estado"] == "pronta" and est[q]["estado"] == "aguardando dependência"
    assert amb.promover(q)[0] == 2
    assert amb.promover(p)[0] == 0
    assert amb.integrar()[q]["estado"] == "pronta"
    assert amb.promover(q)[0] == 0


def test_C06_ref_da_candidata_sobrescrito_ou_registro_editado_nao_promove(amb):
    a = amb.entregar("rob-a", amb.ramo("rob-a", {"a.txt": "A\n"}))["id"]
    outro = amb.ramo("rob-o", {"o.txt": "O\n"}, de=amb.main())
    amb.integrar()
    cand = amb.consultar(a)["candidata"]
    sh(amb.origin, "update-ref", "refs/entregas/" + a, outro)
    main_antes = amb.main()
    cod, saida = amb.promover(a)
    assert cod == 2 and amb.main() == main_antes
    # integrar percebe a candidata obsoleta e recombina
    assert amb.integrar()[a]["estado"] == "pronta"
    nova = amb.consultar(a)["candidata"]
    assert nova not in (cand, outro) and sh(amb.origin, "rev-parse", "refs/entregas/" + a) == nova
    # registro e ref editados juntos para um commit arbitrario descendente da main
    sh(amb.origin, "update-ref", "refs/entregas/" + a, outro)
    caminho = amb.plat / "entregas" / (a + ".json")
    reg = json.loads(caminho.read_text(encoding="utf-8"))
    reg["candidata"] = outro
    caminho.write_text(json.dumps(reg), encoding="utf-8")
    cod, saida = amb.promover(a)
    assert cod == 2 and amb.main() == main_antes


def test_promover_limpa_refs_da_entrega(amb):
    id_ = amb.entregar("rob-a", amb.ramo("rob-a", {"a.txt": "A\n"}))["id"]
    amb.integrar()
    assert refs(amb, "refs/entregas/") and refs(amb, "refs/entregas-fixas/")
    assert amb.promover(id_)[0] == 0
    assert refs(amb, "refs/entregas/") == [] and refs(amb, "refs/entregas-fixas/") == []
    assert sh(amb.origin, "rev-parse", "refs/entregas-promovidas/" + id_) == amb.consultar(id_)["promovida_candidata"]


def test_C05_push_rejeitado_nao_mexe_na_main_local_nem_no_registro(amb, tmp_path):
    github = tmp_path / "github.git"
    sh(tmp_path, "clone", "-q", "--bare", str(amb.origin), str(github))
    sh(amb.origin, "remote", "add", "github", str(github))
    id_ = amb.entregar("rob-a", amb.ramo("rob-a", {"a.txt": "A\n"}))["id"]
    amb.integrar()
    # o GitHub avanca sem o espelho saber
    sh(amb.work, "checkout", "-q", "main")
    sh(amb.work, "pull", "-q", "--ff-only", "origin", "main")
    amb.escrever("g.txt", "G\n")
    sh(amb.work, "add", "-A")
    sh(amb.work, "commit", "-q", "-m", "github avancou")
    sh(amb.work, "push", "-q", str(github), "main")
    main_antes = amb.main()
    cod, saida = amb.promover(id_, "--remoto", "github")
    assert cod == 2 and "main mudou" in saida["motivo"]
    assert amb.main() == main_antes
    assert amb.consultar(id_)["estado"] == "pronta"


def test_promover_sem_remoto_desfeito_pelo_espelho_volta_a_ser_recebida(amb):
    id_ = amb.entregar("rob-a", amb.ramo("rob-a", {"a.txt": "A\n"}))["id"]
    amb.integrar()
    anterior = amb.main()
    assert amb.promover(id_)[0] == 0
    sh(amb.origin, "update-ref", "refs/heads/main", anterior)  # espelho recua a main
    est = amb.integrar()
    assert est[id_]["estado"] == "pronta"
    assert amb.promover(id_)[0] == 0
    assert amb.arquivo_na_main("a.txt") == "A"


def test_retomada_com_main_movida_e_ref_com_pais_errados(amb):
    ids = [amb.entregar("rob-%d" % i, amb.ramo("rob-%d" % i, {"f%d.txt" % i: "x\n"}))["id"] for i in range(3)]
    amb.integrar()
    # queda no meio: duas entregas ficam 'integrando', a main andou e uma ref aponta para commit errado
    amb.avancar_main({"externo.txt": "fora\n"})
    outro = amb.ramo("rob-o", {"o.txt": "O\n"})
    sh(amb.origin, "update-ref", "refs/entregas/" + ids[1], outro)
    for i in ids[:2]:
        caminho = amb.plat / "entregas" / (i + ".json")
        reg = json.loads(caminho.read_text(encoding="utf-8"))
        reg["estado"] = "integrando"
        caminho.write_text(json.dumps(reg), encoding="utf-8")
    est = amb.integrar()
    assert all(est[i]["estado"] == "pronta" for i in ids)
    main = amb.main()
    for i in ids:
        pais = sh(amb.origin, "rev-list", "--parents", "-n", "1", amb.consultar(i)["candidata"]).split()[1:]
        assert pais[0] == main and pais[1] == amb.consultar(i)["commit"]
    assert len(refs(amb, "refs/entregas/")) == 3


def test_conteudo_igual_a_main_por_cherry_pick_no_integrar_vira_na_main(amb):
    sha = amb.ramo("rob-a", {"a.txt": "A\n"})
    id_ = amb.entregar("rob-a", sha)["id"]
    sh(amb.work, "checkout", "-q", "main")
    sh(amb.work, "pull", "-q", "--ff-only", "origin", "main")
    amb.escrever("x.txt", "X\n")
    sh(amb.work, "add", "-A")
    sh(amb.work, "commit", "-q", "-m", "x")
    sh(amb.work, "cherry-pick", sha)
    sh(amb.work, "push", "-q", "origin", "main")
    assert amb.integrar()[id_]["estado"] == "integrada na main"


def test_dois_integrar_ao_mesmo_tempo_nao_corrompem_nem_duplicam(amb):
    for i in range(3):
        amb.entregar("rob-%d" % i, amb.ramo("rob-%d" % i, {"f%d.txt" % i: "x\n"}))
    procs = [subprocess.Popen([sys.executable, str(SCRIPT), "integrar"], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True, encoding="utf-8") for _ in range(3)]
    for p in procs:
        saida, _ = p.communicate(timeout=120)
        assert p.returncode == 0 and len(saida.strip().splitlines()) == 1
        json.loads(saida)
    est = amb.integrar()
    assert all(e["estado"] == "pronta" for e in est.values())
    assert len(refs(amb, "refs/entregas/")) == 3


def test_mensagens_ao_robo_nao_mostram_caminho_privado_nem_senha_de_url(amb):
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        import entregas
    finally:
        sys.path.pop(0)
    t = entregas.sanitizar("fatal: %s/codigo/repo.git e https://usuario:segredo@host/x.git" % amb.plat)
    assert str(amb.plat) not in t and "segredo" not in t and "<plataforma>" in t
    reg = amb.entregar("rob-fantasma", "1" * 40)
    assert str(amb.plat) not in reg["motivo"] and "origin" not in reg["motivo"]


def test_base_precisa_pertencer_ao_historico_da_main(amb):
    outra_base = amb.ramo("isolado", {"x.txt": "x\n"})
    commit = amb.ramo("derivado", {"y.txt": "y\n"}, de=outra_base)
    reg = amb.entregar("derivado", commit, base=outra_base)
    assert reg["estado"] == "precisa de correção"
    assert "histórico da main" in reg["motivo"]


def test_patch_antigo_revertido_na_main_nao_e_entrega_presente(amb):
    sha = amb.ramo("robo", {"a.txt": "A\n"})
    sh(amb.work, "checkout", "-q", "main")
    sh(amb.work, "pull", "-q", "--ff-only", "origin", "main")
    sh(amb.work, "cherry-pick", sha)
    sh(amb.work, "revert", "--no-edit", "HEAD")
    sh(amb.work, "push", "-q", "origin", "main")
    reg = amb.entregar("robo", sha)
    assert reg["estado"] == "recebida"
    assert amb.integrar()[reg["id"]]["estado"] == "pronta"
    assert amb.promover(reg["id"])[0] == 0
    assert amb.arquivo_na_main("a.txt") == "A"


def test_commit_ancestral_revertido_e_reaplicado_sem_perder_conteudo(amb):
    sha = amb.ramo("robo", {"a.txt": "A\n"})
    sh(amb.work, "checkout", "-q", "main")
    sh(amb.work, "pull", "-q", "--ff-only", "origin", "main")
    sh(amb.work, "merge", "-q", "--ff-only", sha)
    sh(amb.work, "revert", "--no-edit", "HEAD")
    sh(amb.work, "push", "-q", "origin", "main")
    assert subprocess.run(["git", "--git-dir", str(amb.origin), "merge-base", "--is-ancestor",
                           sha, amb.main()]).returncode == 0
    reg = amb.entregar("robo", sha)
    assert reg["estado"] == "recebida"
    assert amb.integrar()[reg["id"]]["estado"] == "pronta"
    assert amb.promover(reg["id"])[0] == 0
    assert amb.arquivo_na_main("a.txt") == "A"


def test_C08_renomeacao_e_binario_preservados(amb):
    amb.escrever("antigo.txt", "conteúdo\n")
    (amb.work / "imagem.bin").write_bytes(bytes(range(256)))
    sh(amb.work, "add", "-A")
    sh(amb.work, "commit", "-q", "-m", "arquivos")
    sh(amb.work, "push", "-q", "origin", "HEAD:main")
    base = amb.main()
    sh(amb.work, "checkout", "-q", "-B", "rename", base)
    (amb.work / "antigo.txt").rename(amb.work / "novo.txt")
    (amb.work / "imagem.bin").write_bytes(bytes(reversed(range(256))))
    sh(amb.work, "add", "-A")
    sh(amb.work, "commit", "-q", "-m", "rename binario")
    sha = sh(amb.work, "rev-parse", "HEAD")
    sh(amb.work, "push", "-q", "origin", "rename")
    reg = amb.entregar("rename", sha, base=base)
    assert sorted(reg["arquivos"]) == ["antigo.txt", "imagem.bin", "novo.txt"]
    assert reg["removidos"] == ["antigo.txt"]
    assert amb.integrar()[reg["id"]]["estado"] == "pronta"
    assert amb.promover(reg["id"])[0] == 0
    assert sh(amb.origin, "show", "main:novo.txt") == "conteúdo"
    assert subprocess.run(["git", "--git-dir", str(amb.origin), "show", "main:imagem.bin"],
                          capture_output=True).stdout == bytes(reversed(range(256)))


def test_C08_migracoes_concorrentes_ficam_pendentes_sem_executar_codigo(amb, tmp_path):
    mig = "app/apps/app/migrations"
    (amb.work / mig).mkdir(parents=True)
    amb.escrever(mig + "/0001_initial.py", "class Migration:\n    dependencies = []\n")
    sh(amb.work, "add", "-A")
    sh(amb.work, "commit", "-q", "-m", "mig base")
    sh(amb.work, "push", "-q", "origin", "HEAD:main")
    base = amb.main()
    a = amb.ramo("mig-a", {mig + "/0002_a.py": "class Migration:\n    dependencies = [('app', '0001_initial')]\n"}, de=base)
    b = amb.ramo("mig-b", {mig + "/0002_b.py": "class Migration:\n    dependencies = [('app', '0001_initial')]\n"}, de=base)
    ia = amb.entregar("mig-a", a, base=base)["id"]
    ib = amb.entregar("mig-b", b, base=base)["id"]
    assert amb.integrar()[ia]["estado"] == "pronta"
    assert amb.promover(ia)[0] == 0
    assert amb.integrar()[ib]["estado"] == "precisa de correção"
    assert "pontas concorrentes" in amb.consultar(ib)["motivo"]


def test_grafo_de_migracoes_e_lido_por_ast_sem_executar_candidata(amb, tmp_path):
    marca = tmp_path / "executada.txt"
    mig = "demo/apps/demo/migrations/0001_initial.py"
    (amb.work / "demo" / "apps" / "demo" / "migrations").mkdir(parents=True)
    codigo = ("from pathlib import Path\nPath(%r).write_text('inseguro')\n"
              "class Migration:\n    dependencies = []\n") % str(marca)
    sha = amb.ramo("mig-ast", {mig: codigo})
    id_ = amb.entregar("mig-ast", sha)["id"]
    assert amb.integrar()[id_]["estado"] == "pronta"
    assert not marca.exists()


def test_C12_resposta_perdida_apos_push_reconcilia_sem_duplicar(amb, tmp_path, monkeypatch):
    github = tmp_path / "github.git"
    sh(tmp_path, "clone", "-q", "--bare", str(amb.origin), str(github))
    sh(amb.origin, "remote", "add", "github", str(github))
    id_ = amb.entregar("robo", amb.ramo("robo", {"a.txt": "A\n"}))["id"]
    amb.integrar()
    main_antes = amb.main()
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        import entregas
        original = entregas.git
        def resposta_perdida(*args, **kwargs):
            if args and args[0] == "push":
                original(*args, **kwargs)
                raise subprocess.TimeoutExpired("git push", 60)
            return original(*args, **kwargs)
        monkeypatch.setattr(entregas, "git", resposta_perdida)
        with pytest.raises(subprocess.TimeoutExpired):
            entregas.cmd_promover(type("Args", (), {"id": id_, "remoto": "github"})())
    finally:
        sys.path.pop(0)
    assert amb.main() == main_antes
    assert amb.consultar(id_)["promocao"]["estado"] == "intencao"
    assert sh(github, "rev-parse", "main") == amb.consultar(id_)["candidata"]
    assert amb.promover(id_, "--remoto", "github")[0] == 0
    assert amb.promover(id_, "--remoto", "github")[0] == 0
    assert amb.main() == sh(github, "rev-parse", "main")


def test_promocao_em_modo_producao_exige_remoto_e_prova(amb, tmp_path, monkeypatch):
    github = tmp_path / "github.git"
    sh(tmp_path, "clone", "-q", "--bare", str(amb.origin), str(github))
    sh(amb.origin, "remote", "add", "github", str(github))
    id_ = amb.entregar("robo", amb.ramo("robo", {"a.txt": "A\n"}))["id"]
    amb.integrar()
    monkeypatch.setenv("ENTREGAS_EXIGIR_PROVA", "1")
    assert "remoto" in amb.promover(id_)[1]["motivo"]
    cod, resposta = amb.promover(id_, "--remoto", "github")
    assert cod == 2 and "prova" in resposta["motivo"]
    assert amb.main() == sh(github, "rev-parse", "main")
    assert not amb.consultar(id_).get("promocao")


def test_promocao_funil_sem_ensaio_especifico_e_recusada(amb, tmp_path, monkeypatch):
    github = tmp_path / "github.git"
    sh(tmp_path, "clone", "-q", "--bare", str(amb.origin), str(github))
    sh(amb.origin, "remote", "add", "github", str(github))
    (amb.work / "services" / "funil").mkdir(parents=True)
    sha = amb.ramo("funil", {"services/funil/novo.txt": "teste\n"})
    id_ = amb.entregar("funil", sha)["id"]
    amb.integrar()
    monkeypatch.setenv("ENTREGAS_EXIGIR_PROVA", "1")
    cod, resposta = amb.promover(id_, "--remoto", "github")
    assert cod == 2 and "prova" in resposta["motivo"]
    assert amb.main() == sh(github, "rev-parse", "main")


def test_promocao_mista_exige_identidades_das_duas_celulas(amb, tmp_path, monkeypatch):
    github = tmp_path / "github.git"
    sh(tmp_path, "clone", "-q", "--bare", str(amb.origin), str(github))
    sh(amb.origin, "remote", "add", "github", str(github))
    (amb.work / "services" / "funil").mkdir(parents=True)
    sha = amb.ramo("misto", {"a.txt": "A\n", "services/funil/novo.txt": "F\n"})
    id_ = amb.entregar("misto", sha)["id"]
    amb.integrar()
    monkeypatch.setenv("ENTREGAS_EXIGIR_PROVA", "1")
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        import entregas
        chamadas = []
        def comprovada(candidata, entrega, celula="aplicacao"):
            chamadas.append(celula)
            return {"identidade": ("a" if celula == "aplicacao" else "b") * 64}
        monkeypatch.setattr(entregas, "prova_aceita", comprovada)
        codigo, reg = entregas.cmd_promover(type("Args", (), {"id": id_, "remoto": "github"})())
    finally:
        sys.path.pop(0)
    assert codigo == 0 and chamadas == ["aplicacao", "funil"]
    assert reg["promocao"]["prova_identidade"] == "a" * 64
    assert reg["promocao"]["prova_funil_identidade"] == "b" * 64
