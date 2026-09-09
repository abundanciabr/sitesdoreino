"""O mandato cobre um destino e os arquivos realmente transmitidos."""
import json
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mandato_publicacao as mandato

SHA = "a" * 40
BLOB = "b" * 40
URL = "https://github.com/abundanciabr/sitesdoreino.git"

class Git:
    def __init__(self, *, urls=None, caminho="ci/portao.py", conteudo="print(1)", commits=None):
        self.urls = urls or [URL]
        self.caminho = caminho
        self.conteudo = conteudo
        self.commits = [SHA] if commits is None else commits
        self.chamadas = []
    def __call__(self, cmd, raiz):
        self.chamadas.append(cmd)
        if cmd[:3] == ["git", "remote", "get-url"]:
            return "\n".join(self.urls)
        if cmd[:2] == ["gh", "api"]:
            return json.dumps({"full_name": "abundanciabr/sitesdoreino", "private": False})
        if cmd[:2] == ["git", "rev-list"]:
            return "\n".join(self.commits)
        if cmd[:2] == ["git", "diff-tree"]:
            return self.caminho + "\0"
        if cmd[:2] == ["git", "ls-tree"]:
            return "100644 blob " + BLOB + "\t" + self.caminho + "\0"
        if cmd[:2] == ["git", "cat-file"]:
            return self.conteudo
        if cmd[:2] == ["git", "show"]:
            return "fix: concluir tarefa"
        raise AssertionError(cmd)

@pytest.mark.parametrize("url", [URL, "git@github.com:abundanciabr/sitesdoreino.git", "ssh://git@github.com/abundanciabr/sitesdoreino.git"])
def test_destino_autorizado_sem_nova_pergunta(tmp_path, url):
    git = Git(urls=[url])
    mandato.conferir_envio(tmp_path, [git.caminho], git)
    assert any(c[:2] == ["git", "cat-file"] for c in git.chamadas)

@pytest.mark.parametrize("url", ["https://github.com/terceiro/sitesdoreino.git", "https://github.com.evil.test/abundanciabr/sitesdoreino.git", "https://usuario:senha@github.com/abundanciabr/sitesdoreino.git", "file:///tmp/remote"])
def test_destino_diferente_para_antes_de_enviar(tmp_path, url):
    git = Git(urls=[url])
    with pytest.raises(mandato.PublicacaoRecusada, match="destino"):
        mandato.conferir_envio(tmp_path, [git.caminho], git)
    assert not any(c[:2] == ["gh", "api"] for c in git.chamadas)

def test_segundo_destino_de_push_nao_recebe_payload(tmp_path):
    git = Git(urls=[URL, "https://github.com/terceiro/copia.git"])
    with pytest.raises(mandato.PublicacaoRecusada):
        mandato.conferir_envio(tmp_path, [git.caminho], git)

def test_commit_intermediario_tambem_tem_de_estar_no_escopo(tmp_path):
    git = Git(caminho="documentos/particular.txt")
    with pytest.raises(mandato.PublicacaoRecusada, match="declarado"):
        mandato.conferir_envio(tmp_path, ["ci/portao.py"], git)

@pytest.mark.parametrize("caminho", [".env", "infra/env/producao.env", "backup/clientes.dump", "dados.sqlite3", ".codex/sessions/transcript.jsonl", "../fora.txt"])
def test_dados_privados_nao_sao_publicaveis_por_declarar_nome(tmp_path, caminho):
    git = Git(caminho=caminho)
    with pytest.raises(mandato.PublicacaoRecusada):
        mandato.conferir_envio(tmp_path, [caminho], git)

@pytest.mark.parametrize("conteudo", ["gh" + "p_" + "A" * 36, "-----BEGIN " + "PRIVATE KEY-----", "APP_" + "USR-1234567890abcdef"])
def test_segredo_recusa_sem_repetir_valor_no_erro(tmp_path, conteudo):
    git = Git(conteudo=conteudo)
    with pytest.raises(mandato.PublicacaoRecusada) as erro:
        mandato.conferir_envio(tmp_path, [git.caminho], git)
    assert conteudo not in str(erro.value)

def test_resposta_git_malformada_nao_quer_dizer_historico_vazio(tmp_path):
    git = Git(commits=["nao e um sha"])
    with pytest.raises(mandato.PublicacaoRecusada):
        mandato.conferir_envio(tmp_path, [git.caminho], git)

def test_anuncio_sem_codigo_ainda_confere_destino(tmp_path):
    git = Git(commits=[])
    mandato.conferir_envio(tmp_path, [], git)
    assert len([c for c in git.chamadas if c[:3] == ["git", "remote", "get-url"]]) == 2


def test_fechamento_recusa_destino_antes_do_primeiro_push(tmp_path):
    import test_pr
    import pr
    raiz = test_pr.bancada(tmp_path)
    git = test_pr.Duble({**test_pr.RESPOSTAS_FELIZES, "remote get-url": "https://github.com/terceiro/repo.git"})
    with pytest.raises(pr.ParouPorSeguranca, match="mandato"):
        pr.abrir(raiz, test_pr.pedido(raiz), rodar=git, hoje=test_pr.HOJE)
    assert not git.pediu("git push")
    assert not git.pediu("gh pr create")


def test_anuncio_recusa_destino_antes_de_publicar_intencao():
    import test_sessao
    import sessao
    class Mundo(test_sessao.MundoFalso):
        def _stdout(self, linha):
            if "remote get-url" in linha:
                return "https://github.com/terceiro/repo.git"
            return super()._stdout(linha)
    mundo = Mundo(test_sessao.plano_de_teste(sobe_ambiente=False))
    with pytest.raises(sessao.ErroDeSessao) as erro:
        mundo.sessao().rodar()
    assert "mandato" in erro.value.resumo
    assert not any("git push" in c or "gh pr create" in c for c in mundo.chamadas)


@pytest.mark.parametrize("permitir_nome", [False, True])
def test_git_real_inspeciona_arquivo_introduzido_e_removido(tmp_path, permitir_nome):
    import subprocess
    def git(*args):
        return subprocess.run(["git", *args], cwd=tmp_path, capture_output=True, text=True, encoding="utf-8", check=True).stdout
    git("init", "-b", "main")
    git("config", "user.name", "Teste")
    git("config", "user.email", "teste@example.invalid")
    (tmp_path / "publico.txt").write_text("publico", encoding="utf-8")
    git("add", "publico.txt"); git("commit", "-m", "base")
    git("update-ref", "refs/remotes/origin/main", "HEAD")
    (tmp_path / "acidente.txt").write_text("gh" + "p_" + "B" * 36, encoding="utf-8")
    git("add", "acidente.txt"); git("commit", "-m", "introduziu")
    git("rm", "acidente.txt"); git("commit", "-m", "removeu")
    def rodar(cmd, raiz):
        if cmd[:3] == ["git", "remote", "get-url"]:
            return URL
        if cmd[:2] == ["gh", "api"]:
            return json.dumps({"full_name": "abundanciabr/sitesdoreino", "private": False})
        return git(*cmd[1:])
    with pytest.raises(mandato.PublicacaoRecusada, match="credencial" if permitir_nome else "declarado"):
        mandato.conferir_envio(tmp_path, ["acidente.txt"] if permitir_nome else ["publico.txt"], rodar)


def test_destino_e_reconferido_no_push_do_recibo(tmp_path):
    import test_pr
    import pr
    class GitMutavel(test_pr.Duble):
        destinos = 0
        def __call__(self, cmd, raiz=None, **opcoes):
            if cmd[:3] == ["git", "remote", "get-url"]:
                self.destinos += 1
                if self.destinos > 2:
                    self.chamadas.append(cmd)
                    return "https://github.com/terceiro/copia.git"
            return super().__call__(cmd, raiz, **opcoes)
    raiz = test_pr.bancada(tmp_path)
    git = GitMutavel(test_pr.RESPOSTAS_FELIZES)
    with pytest.raises(pr.ParouPorSeguranca, match="mandato"):
        pr.abrir(raiz, test_pr.pedido(raiz), rodar=git, hoje=test_pr.HOJE)
    pushes = [c for c in git.chamadas if c[:2] == ["git", "push"]]
    assert len(pushes) == 1
    assert "--no-follow-tags" in pushes[0]


@pytest.mark.parametrize("existente", [False, True])
@pytest.mark.parametrize("campo", ["titulo", "corpo_arquivo", "detalhe", "mensagem_arquivo"])
@pytest.mark.parametrize("familia", ["github", "pagamento", "openai"])
def test_textos_fora_do_git_sao_conferidos_antes_de_publicar(tmp_path, existente, campo, familia):
    import test_pr
    import pr
    credencial = {"github": "gh" + "o_" + "X" * 36,
                  "pagamento": "APP_" + "USR-" + "X" * 32,
                  "openai": "s" + "k-" + "X" * 32}[familia]
    raiz = test_pr.bancada(tmp_path)
    entrada = test_pr.pedido(raiz)
    if campo.endswith("_arquivo"):
        arquivo = getattr(entrada, campo)
        arquivo.write_text(arquivo.read_text(encoding="utf-8") + "\n" + credencial, encoding="utf-8")
    else:
        setattr(entrada, campo, getattr(entrada, campo) + " " + credencial)
    respostas = dict(test_pr.RESPOSTAS_FELIZES)
    if existente:
        respostas["gh pr list"] = json.dumps([{"number": 1210, "url": test_pr.URL_DO_PR}])
    git = test_pr.Duble(respostas)
    with pytest.raises(pr.ParouPorSeguranca, match="mandato") as erro:
        pr.abrir(raiz, entrada, rodar=git, hoje=test_pr.HOJE)
    assert credencial not in str(erro.value)
    assert not git.pediu("git push")
    assert not git.pediu("gh pr create")
    assert not git.pediu("gh pr edit")
