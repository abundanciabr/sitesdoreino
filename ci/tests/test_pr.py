"""Guardas do `make pr` (ci/pr.py) — do commit ao PR aberto, num comando só.

O que se prova aqui, na ordem do que custou caro:

1. O RITO INTEIRO acontece NA ORDEM, e o registro nasce com os 11 campos
   derivados batendo campo a campo (`armadilhas/185`: sem o número do PR
   dentro da evidência, a dívida do livro cai na próxima sessão).
2. O `detalhe` curto RECUSA antes de gravar qualquer coisa. A única frase que
   o mantenedor lê é escrita por quem fez o trabalho; máquina não inventa
   julgamento.
3. O `--continuar` relê o estado: PR já aberto não vira PR novo, e o que já
   está commitado não é commitado de novo.
4. No clone principal ele para na hora, sem tocar em git nenhum
   (`armadilhas/135`).
5. Qualquer passo que falhe PARA o rito, e a mensagem diz o que fazer.

Nenhum teste daqui fala com a rede: `git`, `gh`, `node` e o almoxarife passam
todos pela MESMA costura (`rodar`), substituída por dublê.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest

RAIZ_DO_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ_DO_REPO / "ci"))

import pr  # noqa: E402

COAUTOR = "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
URL_DO_PR = "https://github.com/abundanciabr/sitesdoreino/pull/1210"
HOJE = date(2026, 9, 6)


class Duble:
    """Substitui git, gh, node e o almoxarife. Guarda TODA chamada, em ordem."""

    def __init__(self, respostas: dict[str, str] | None = None) -> None:
        self.chamadas: list[list[str]] = []
        self.respostas = dict(respostas or {})
        self.explode_em: str | None = None
        self.recibo_preparado = False
        self.rascunho = False

    def __call__(self, comando: list[str], raiz: Path | None = None, **opcoes) -> str:
        self.chamadas.append(list(comando))
        linha = " ".join(comando)
        if comando[:3] == ["git", "status", "--porcelain=v1"]:
            return ""
        if self.explode_em and self.explode_em in linha:
            raise pr.ErroDeInstrumentacao(
                f"o comando falhou: {linha}", "exit 1\n(saída do dublê)"
            )
        if comando[:3] == ['git', 'add', '--'] and comando[3].startswith('painel/registros/'):
            self.recibo_preparado = True
            self.recibo = comando[3]
        if comando == ['git', 'diff', '--cached', '--name-only'] and self.recibo_preparado:
            return self.recibo
        if comando[:3] == ["gh", "pr", "create"]:
            self.rascunho = "--draft" in comando
        if comando[:3] == ["gh", "pr", "ready"]:
            self.rascunho = "--undo" in comando
        for chave, resposta in self.respostas.items():
            if chave in linha:
                if chave == "gh pr view" and resposta == RESPOSTAS_FELIZES["gh pr view"]:
                    return json.dumps({"headRefOid": "b" * 40, "state": "OPEN", "isDraft": self.rascunho})
                return resposta
        return ""

    @property
    def linhas(self) -> list[str]:
        return [" ".join(c) for c in self.chamadas]

    def pediu(self, pedaco: str) -> bool:
        return any(pedaco in linha for linha in self.linhas)

    def posicao(self, pedaco: str) -> int:
        for i, linha in enumerate(self.linhas):
            if pedaco in linha:
                return i
        raise AssertionError(f"o dublê nunca recebeu {pedaco!r}; recebeu: {self.linhas}")


RESPOSTAS_FELIZES = {
    "git show " + "b" * 40 + ":ci/pr.py": "def abrir(): pass\n",
    "write-tree": "a" * 40,
    "rev-parse HEAD^{tree}": "a" * 40,
    "rev-parse HEAD": "b" * 40,
        "gh pr view": json.dumps({"headRefOid": "b" * 40, "state": "OPEN", "isDraft": False}),
    "rev-parse --abbrev-ref": "agent/ci/make-pr\n",
    "status --porcelain": " M ci/pr.py\n?? ci/tests/test_pr.py\n",
    "diff --cached --name-only": "ci/pr.py\n",
    "gh pr create": f"{URL_DO_PR}\n",
    "gh pr list": "[]\n",
    "git remote get-url origin": "https://github.com/abundanciabr/sitesdoreino.git",
    "reservar.py numero registro": "20260906-077\n",
}


def bancada(tmp_path: Path, principal: bool = False) -> Path:
    """Uma raiz de mentira: worktree por padrão, clone principal se pedirem."""
    raiz = tmp_path / "wt-ci-make-pr"
    (raiz / "painel" / "registros").mkdir(parents=True)
    (raiz / "ci").mkdir()
    if principal:
        (raiz / ".git").mkdir()
    else:
        (raiz / ".git").write_text(f"gitdir: {tmp_path / 'git-privado'}\n", encoding="utf-8")
    (raiz / "mensagem.txt").write_text(
        f"ci: o comando que abre o PR\n\nMuda o mundo.\n\n{COAUTOR}\n", encoding="utf-8"
    )
    (raiz / "corpo.md").write_text("## O que muda\n\nUm comando só.\n", encoding="utf-8")
    (raiz / "validacao.json").write_text(json.dumps({"comandos": [["pytest", "ci/tests"]]}), encoding="utf-8")
    pr.telemetria.registrar_fase(
        "abertura", "concluido", tarefa="agent/ci/make-pr", tentativa="abertura-legada",
        branch="agent/ci/make-pr", commit="b" * 40, cwd=str(raiz),
    )
    return raiz


DETALHE = (
    "O rito de escriturar, abrir o PR e conferir virou um comando so. "
    "Antes eram dezessete idas e voltas ao modelo, todas deterministicas."
)


def pedido(raiz: Path, **trocas) -> pr.Pedido:
    base = dict(
        titulo="ci: do commit ao pouso armado, num comando so",
        mensagem_arquivo=raiz / "mensagem.txt",
        corpo_arquivo=raiz / "corpo.md",
        arquivos=["ci/pr.py", "ci/tests/test_pr.py"],
        detalhe=DETALHE,
        validacao_arquivo=raiz / "validacao.json",
    )
    base.update(trocas)
    return pr.Pedido(**base)


# ----------------------------------------------------------- (a) o rito inteiro --


def test_o_rito_inteiro_acontece_na_ordem(tmp_path, capsys):
    raiz = bancada(tmp_path)
    dub = Duble(RESPOSTAS_FELIZES)

    final = pr.abrir(raiz, pedido(raiz), rodar=dub, hoje=HOJE)

    ordem = [
        "git add",
        "git commit -F",
        "git push -u origin agent/ci/make-pr",
        "gh pr create",
        "reservar.py numero registro",
        "node painel/gerar_manifesto.js",
    ]
    posicoes = [dub.posicao(p) for p in ordem]
    assert posicoes == sorted(posicoes), f"fora de ordem: {dub.linhas}"
    # O commit do registro vem DEPOIS do gerador, nunca antes: registro
    # inválido não pode chegar a virar commit.
    assert dub.pediu("git add -- painel/registros/")
    assert dub.posicao("node painel/gerar_manifesto.js") < dub.posicao(
        "git add -- painel/registros/"
    )

    assert final.startswith("PR 1210 aberto com recibo")
    assert URL_DO_PR in final
    assert "python ci/esperar.py --checks 1210 --so-desfecho" in final
    assert "A sessão encerra aqui" not in final
    saida = capsys.readouterr().out
    assert saida.count("PASS") >= 4
    assert saida.strip().splitlines()[-1] == final


def test_o_registro_nasce_com_os_onze_campos_derivados(tmp_path):
    raiz = bancada(tmp_path)
    dub = Duble(RESPOSTAS_FELIZES)

    pr.abrir(raiz, pedido(raiz), rodar=dub, hoje=HOJE)

    escritos = list((raiz / "painel" / "registros").glob("*.js"))
    assert len(escritos) == 1
    nome = escritos[0].name
    assert nome == "20260906-077-ci-do-commit-ao-pouso-armado-num-comando-so.js"

    texto = escritos[0].read_text(encoding="utf-8")
    campos = pr.campos_lidos(texto)
    assert campos == {
        "arquivo": "20260906-077-ci-do-commit-ao-pouso-armado-num-comando-so",
        "tipo": "entrega",
        "quando": "2026-09-06",
        "titulo": "ci: do commit ao pouso armado, num comando so",
        "detalhe": DETALHE,
        "autoridade": "github",
        "evidencia": f"{URL_DO_PR}. Validação local: árvore {'a' * 40}; commit {'b' * 40}; 1 comando(s), exit 0. Revisão, integração e publicação não verificadas.",
        "verificado_em": "2026-09-06",
        "precisa_do_dono": False,
        "responde_a": None,
        "relacao": "comentario",
        "tarefa": None,
        "gravidade": "info",
        "frente": "fabrica",
        "area": "ci",
        "vence_em_dias": None,
        "se_eu_nao_decidir": None,
        "recomendacao": None,
        "reversivel": None,
    }


def test_a_evidencia_soma_o_texto_de_fora_ao_numero_do_pr(tmp_path):
    raiz = bancada(tmp_path)
    dub = Duble(RESPOSTAS_FELIZES)

    pr.abrir(
        raiz, pedido(raiz, evidencia="pytest ci/tests/test_pr.py: 9 passed"),
        rodar=dub, hoje=HOJE,
    )

    texto = next((raiz / "painel" / "registros").glob("*.js")).read_text(encoding="utf-8")
    evidencia = pr.campos_lidos(texto)["evidencia"]
    assert evidencia.startswith(URL_DO_PR)
    assert "9 passed" in evidencia
    assert "exit 0" in evidencia


def test_evidencia_da_flag_chega_ao_recibo_somada_a_url_do_pr(tmp_path):
    """`armadilhas/-`: `--evidencia` era lido e descartado em silêncio; o
    recibo saía só com a URL do PR e a prova real (run da VPS, por exemplo)
    se perdia."""
    raiz = bancada(tmp_path)
    url_da_prova = "https://github.com/abundanciabr/sitesdoreino/actions/runs/123"
    dub = Duble(RESPOSTAS_FELIZES)

    pr.abrir(raiz, pedido(raiz, evidencia=url_da_prova), rodar=dub, hoje=HOJE)

    texto = next((raiz / "painel" / "registros").glob("*.js")).read_text(encoding="utf-8")
    evidencia = pr.campos_lidos(texto)["evidencia"]
    assert url_da_prova in evidencia


def test_sem_a_flag_de_evidencia_nada_muda_no_recibo(tmp_path):
    raiz = bancada(tmp_path)
    dub = Duble(RESPOSTAS_FELIZES)

    pr.abrir(raiz, pedido(raiz), rodar=dub, hoje=HOJE)

    texto = next((raiz / "painel" / "registros").glob("*.js")).read_text(encoding="utf-8")
    evidencia = pr.campos_lidos(texto)["evidencia"]
    assert evidencia == (
        f"{URL_DO_PR}. Validação local: árvore {'a' * 40}; commit {'b' * 40}; "
        "1 comando(s), exit 0. Revisão, integração e publicação não verificadas."
    )


def test_evidencia_grande_demais_recusa_com_mensagem_que_ensina_a_flag(tmp_path):
    raiz = bancada(tmp_path)
    dub = Duble(RESPOSTAS_FELIZES)

    with pytest.raises(pr.ParouPorSeguranca, match="--evidencia") as excinfo:
        pr.abrir(raiz, pedido(raiz, evidencia="x" * 900), rodar=dub, hoje=HOJE)

    assert not list((raiz / "painel" / "registros").glob("*.js"))
    assert "Encurte o texto de --evidencia" in excinfo.value.o_que_fazer


def test_a_frente_sai_dos_caminhos_tocados_quando_ninguem_a_declara():
    assert pr.derivar_frente(["ci/pr.py", "Makefile"]) == "fabrica"
    assert pr.derivar_frente(["services/forum/apps/core/views.py"]) == "comunidade"
    assert pr.derivar_frente(["services/checkout/apps/core/models.py"]) == "vender"
    assert pr.derivar_frente(["services/cursos/apps/core/urls.py"]) == "curso"
    assert pr.derivar_frente(["services/quiz/templates/x.html"]) == "site"
    # Empate entre duas frentes não vira chute: fica nulo, e o campo é opcional.
    assert pr.derivar_frente(["ci/pr.py", "services/forum/x.py"]) is None
    assert pr.derivar_frente(["LEIAME.txt"]) is None


def test_o_assunto_do_recibo_corta_no_espaco_e_nunca_no_meio_da_palavra(tmp_path):
    # O caso real: o assunto do PR #1216 saiu "…com o recibo gera (PR #1216)".
    longo = "ci: do commit ao PR aberto num comando so, com o recibo gerado"
    assert pr._encurtar("curto", 60) == "curto"
    assert pr._encurtar(longo, 60) == "ci: do commit ao PR aberto num comando so, com o recibo"

    raiz = bancada(tmp_path)
    dub = Duble(RESPOSTAS_FELIZES)
    pr.abrir(raiz, pedido(raiz, titulo=longo), rodar=dub, hoje=HOJE)
    assunto = next(
        c[c.index("-m") + 1] for c in dub.chamadas if c[:2] == ["git", "commit"] and "-m" in c
    )
    assert assunto == "painel: ci: do commit ao PR aberto num comando so, com o recibo (PR #1210)"


def test_a_frente_declarada_vence_a_derivada(tmp_path):
    raiz = bancada(tmp_path)
    pr.abrir(raiz, pedido(raiz, frente="curso"), rodar=Duble(RESPOSTAS_FELIZES), hoje=HOJE)
    texto = next((raiz / "painel" / "registros").glob("*.js")).read_text(encoding="utf-8")
    assert pr.campos_lidos(texto)["frente"] == "curso"


# --------------------------------------------- (b) detalhe vazio para na porta --


@pytest.mark.parametrize("detalhe", ["", "   ", "Consertei o bug.", "x" * 79])
def test_detalhe_curto_recusa_antes_de_gravar_qualquer_coisa(tmp_path, detalhe):
    raiz = bancada(tmp_path)
    dub = Duble(RESPOSTAS_FELIZES)

    with pytest.raises(pr.ParouPorSeguranca) as caixa:
        pr.abrir(raiz, pedido(raiz, detalhe=detalhe), rodar=dub, hoje=HOJE)

    assert "detalhe" in str(caixa.value).lower()
    assert "--detalhe" in caixa.value.o_que_fazer
    assert dub.chamadas == [], f"tocou no mundo antes de recusar: {dub.linhas}"
    assert list((raiz / "painel" / "registros").glob("*.js")) == []


def test_mensagem_sem_coautor_recusa_antes_de_commitar(tmp_path):
    raiz = bancada(tmp_path)
    (raiz / "mensagem.txt").write_text("ci: sem coautor\n", encoding="utf-8")
    dub = Duble(RESPOSTAS_FELIZES)

    with pytest.raises(pr.ParouPorSeguranca) as caixa:
        pr.abrir(raiz, pedido(raiz), rodar=dub, hoje=HOJE)

    assert "Co-Authored-By" in str(caixa.value) or "Co-Authored-By" in caixa.value.o_que_fazer
    assert not dub.pediu("git commit")


def test_ramo_fora_do_padrao_agent_recusa(tmp_path):
    raiz = bancada(tmp_path)
    dub = Duble({**RESPOSTAS_FELIZES, "rev-parse --abbrev-ref": "main\n"})

    with pytest.raises(pr.ParouPorSeguranca) as caixa:
        pr.abrir(raiz, pedido(raiz), rodar=dub, hoje=HOJE)

    assert "agent/" in caixa.value.o_que_fazer
    assert not dub.pediu("git add")


def test_arvore_sem_mudancas_recusa(tmp_path):
    raiz = bancada(tmp_path)
    dub = Duble({**RESPOSTAS_FELIZES, "status --porcelain": "\n"})

    with pytest.raises(pr.ParouPorSeguranca) as caixa:
        pr.abrir(raiz, pedido(raiz), rodar=dub, hoje=HOJE)

    assert "--continuar" in caixa.value.o_que_fazer
    assert not dub.pediu("git add")


# O scratchpad é um só para a sessão e todos os subagentes: um despacho
# sobrescreveu o `corpo.md` do outro enquanto o rito validava, e #2122, #2164
# e #2220 saíram com o texto de outra tarefa.
@pytest.mark.parametrize("campo", ["mensagem_arquivo", "corpo_arquivo", "validacao_arquivo", "detalhe_arquivo"])
def test_arquivo_de_entrada_fora_da_bancada_recusa_antes_de_gravar(tmp_path, monkeypatch, campo):
    # guarda: ci/pr.py:749
    raiz = bancada(tmp_path)
    monkeypatch.setattr(pr, "base_de_scratch_padrao", lambda: tmp_path / "sessoes")
    copias = {"mensagem_arquivo": "mensagem.txt", "corpo_arquivo": "corpo.md", "validacao_arquivo": "validacao.json"}
    fora = tmp_path / "scratchpad-da-sessao" / "entrada"
    fora.parent.mkdir()
    fora.write_text((raiz / copias[campo]).read_text(encoding="utf-8") if campo in copias else DETALHE, encoding="utf-8")
    dub = Duble(RESPOSTAS_FELIZES)

    with pytest.raises(pr.ParouPorSeguranca) as caixa:
        pr.abrir(raiz, pedido(raiz, **{campo: fora}), rodar=dub, hoje=HOJE)

    assert str(fora) in str(caixa.value)
    assert str(tmp_path / "sessoes" / "ci-make-pr") in caixa.value.o_que_fazer
    assert not dub.pediu("git add")
    assert list((raiz / "painel" / "registros").glob("*.js")) == []


def test_arquivos_na_pasta_da_bancada_seguem_o_rito(tmp_path, monkeypatch):
    raiz = bancada(tmp_path)
    monkeypatch.setattr(pr, "base_de_scratch_padrao", lambda: tmp_path / "sessoes")
    pasta = tmp_path / "sessoes" / "ci-make-pr"
    pasta.mkdir(parents=True)
    for nome in ("mensagem.txt", "corpo.md", "validacao.json", "detalhe.txt"):
        (pasta / nome).write_text(DETALHE if nome == "detalhe.txt" else (raiz / nome).read_text(encoding="utf-8"), encoding="utf-8")
    dub = Duble(RESPOSTAS_FELIZES)

    final = pr.abrir(raiz, pedido(
        raiz, mensagem_arquivo=pasta / "mensagem.txt", corpo_arquivo=pasta / "corpo.md",
        validacao_arquivo=pasta / "validacao.json", detalhe_arquivo=pasta / "detalhe.txt",
    ), rodar=dub, hoje=HOJE)

    assert final.startswith("PR 1210 aberto com recibo")


# ------------------------------------------------------------- (c) --continuar --


def test_continuar_reusa_o_pr_ja_aberto_em_vez_de_abrir_outro(tmp_path):
    raiz = bancada(tmp_path)
    dub = Duble({
        **RESPOSTAS_FELIZES,
        "status --porcelain": "\n",
        "diff --cached --name-only": "",
        "gh pr list": json.dumps([{"number": 1210, "url": URL_DO_PR}]),
    })

    final = pr.abrir(raiz, pedido(raiz, continuar=True), rodar=dub, hoje=HOJE)

    assert not dub.pediu("gh pr create")
    assert not dub.pediu("git commit -F")
    assert "1210" in final
    # O registro ainda faltava: ele nasce, e é ele que vira o segundo commit.
    assert len(list((raiz / "painel" / "registros").glob("*.js"))) == 1


def test_continuar_com_o_registro_ja_embarcado_nao_pede_outro_numero(tmp_path):
    raiz = bancada(tmp_path)
    ja = raiz / "painel" / "registros" / "20260906-077-ci-do-commit.js"
    ja.write_text(pr.renderizar({"evidencia": f"{URL_DO_PR}. árvore {'a' * 40}"}), encoding="utf-8")
    dub = Duble({
        **RESPOSTAS_FELIZES,
        "status --porcelain": "\n",
        "diff --cached --name-only": "",
        "gh pr list": json.dumps([{"number": 1210, "url": URL_DO_PR}]),
    })

    pr.abrir(raiz, pedido(raiz, continuar=True), rodar=dub, hoje=HOJE)

    assert not dub.pediu("reservar.py numero registro")
    assert len(list((raiz / "painel" / "registros").glob("*.js"))) == 1


def test_push_falha_para_ate_retomada_explicita_com_continuar(tmp_path):
    raiz = bancada(tmp_path)
    primeira = Duble(RESPOSTAS_FELIZES)
    primeira.explode_em = 'git push -u origin'

    with pytest.raises(pr.ErroDeInstrumentacao):
        pr.abrir(raiz, pedido(raiz), rodar=primeira, hoje=HOJE)

    assert primeira.pediu('git commit -F')
    assert primeira.pediu('pytest ci/tests')
    assert primeira.pediu('git push -u origin')
    assert not primeira.pediu('gh pr create')
    assert not list((raiz / 'painel' / 'registros').glob('*.js'))

    segunda = Duble({
        **RESPOSTAS_FELIZES,
        'status --porcelain': '\n',
        'diff --cached --name-only': '',
        'gh pr list': '[]\n',
    })
    final = pr.abrir(raiz, pedido(raiz, continuar=True), rodar=segunda, hoje=HOJE)

    assert '1210' in final
    assert not segunda.pediu('git commit -F')
    assert segunda.pediu('git push -u origin')
    assert segunda.pediu('gh pr create')
    assert len(list((raiz / 'painel' / 'registros').glob('*.js'))) == 1


# ------------------------------------------------------- (d) o clone principal --


def test_no_clone_principal_para_na_hora_sem_tocar_em_git(tmp_path):
    raiz = bancada(tmp_path, principal=True)
    dub = Duble(RESPOSTAS_FELIZES)

    with pytest.raises(pr.ParouPorSeguranca) as caixa:
        pr.abrir(raiz, pedido(raiz), rodar=dub, hoje=HOJE)

    assert "worktree" in caixa.value.o_que_fazer
    assert dub.chamadas == [], f"mexeu no espelho: {dub.linhas}"


# ---------------------------------------------- (e) FAIL no meio para o rito --


@pytest.mark.parametrize(
    "onde, nao_deve_chegar",
    [
        ("git commit -F", "git push"),
        ("git push -u", "gh pr create"),
        ("gh pr create", "reservar.py"),
        ("reservar.py numero", "gerar_manifesto"),
        ("gerar_manifesto", "git add -- painel/registros/"),
    ],
)
def test_falha_em_qualquer_passo_para_o_rito(tmp_path, onde, nao_deve_chegar, capsys):
    raiz = bancada(tmp_path)
    dub = Duble(RESPOSTAS_FELIZES)
    dub.explode_em = onde

    with pytest.raises(pr.ErroDeInstrumentacao):
        pr.abrir(raiz, pedido(raiz), rodar=dub, hoje=HOJE)

    assert not dub.pediu(nao_deve_chegar), f"passou do FAIL: {dub.linhas}"


def test_a_cli_imprime_FAIL_e_o_que_fazer_e_sai_com_1(tmp_path, monkeypatch, capsys):
    raiz = bancada(tmp_path)
    monkeypatch.setattr(pr, "raiz_do_repo", lambda: raiz)

    codigo = pr.main([
        "--titulo", "ci: qualquer coisa",
        "--mensagem-arquivo", str(raiz / "mensagem.txt"),
        "--corpo-arquivo", str(raiz / "corpo.md"),
        "--arquivos", "ci/pr.py",
        "--detalhe", "curto demais",
        "--validacao-arquivo", str(raiz / "validacao.json"),
    ])

    saida = capsys.readouterr().out
    assert codigo == 1
    assert "FAIL" in saida
    assert "PAROU POR SEGURANÇA" in saida


def test_o_gerador_reprovando_impede_o_registro_de_virar_commit(tmp_path):
    """O livro inválido nunca chega ao commit — é o passo 8 antes do 9."""
    raiz = bancada(tmp_path)
    dub = Duble(RESPOSTAS_FELIZES)
    dub.explode_em = "gerar_manifesto"

    with pytest.raises(pr.ErroDeInstrumentacao):
        pr.abrir(raiz, pedido(raiz), rodar=dub, hoje=HOJE)

    assert not dub.pediu("git add -- painel/registros/")


# ------------------------------------------------------------------ o Makefile --


def test_o_makefile_tem_o_alvo_pr_e_ele_chama_ci_pr_py():
    texto = (RAIZ_DO_REPO / "Makefile").read_text(encoding="utf-8")
    assert "\npr:" in texto
    assert "ci/pr.py" in texto


def test_o_leia_me_manda_pelo_make_pr():
    texto = (RAIZ_DO_REPO / "painel" / "LEIA-ME.md").read_text(encoding="utf-8")
    assert "make pr" in texto


def test_o_exemplo_canonico_do_make_pr_ensina_a_tarefa_obrigatoria():
    import tomllib

    ficha_codex = tomllib.loads(
        (RAIZ_DO_REPO / ".codex/agents/despacho.toml").read_text(encoding="utf-8")
    )["developer_instructions"]
    textos = {
        ".claude/agents/despacho.md": (RAIZ_DO_REPO / ".claude/agents/despacho.md").read_text(encoding="utf-8"),
        ".codex/agents/despacho.toml": ficha_codex,
        "painel/LEIA-ME.md": (RAIZ_DO_REPO / "painel/LEIA-ME.md").read_text(encoding="utf-8"),
    }
    for nome, texto in textos.items():
        exemplo = texto.split("make pr TITULO=", 1)[1].split("```", 1)[0]
        assert "TAR=TAR-NNN" in exemplo, nome
        assert "quando aplicável" not in texto, nome
        assert "quando esta entrega" not in texto, nome

def test_evidencia_ausente_recusa_antes_de_publicar(tmp_path):
    raiz = bancada(tmp_path)
    dub = Duble(RESPOSTAS_FELIZES)
    with pytest.raises(pr.ParouPorSeguranca):
        pr.abrir(raiz, pedido(raiz, validacao_arquivo=None), rodar=dub, hoje=HOJE)
    assert not dub.pediu('git push')


def test_recibo_de_outro_pr_nao_e_reutilizado(tmp_path):
    raiz = bancada(tmp_path)
    arquivo = raiz / 'painel/registros/outro.js'
    arquivo.write_text(pr.renderizar({'evidencia': URL_DO_PR + '0'}), encoding='utf-8')
    assert pr._registro_que_cita(raiz, 1210) is None


def test_pr_existente_e_consultado_sem_continuar(tmp_path):
    dub = Duble({**RESPOSTAS_FELIZES, 'gh pr list': json.dumps([{'number': 1210, 'url': URL_DO_PR}])})
    assert pr._achar_ou_abrir_o_pr(lambda c: dub(c), pedido(bancada(tmp_path)), 'agent/ci/make-pr') == (1210, URL_DO_PR)
    assert not dub.pediu('gh pr create')


def test_pr_draft_vira_pronto_depois_da_validacao_final(tmp_path):
    raiz = bancada(tmp_path)
    class DraftDuble(Duble):
        def __init__(self):
            super().__init__(RESPOSTAS_FELIZES)
            self.views = 0

        def __call__(self, comando, raiz=None, **opcoes):
            if comando[:3] == ["gh", "pr", "view"]:
                self.views += 1
                self.chamadas.append(list(comando))
                return json.dumps({
                    "headRefOid": "b" * 40,
                    "state": "OPEN",
                    "isDraft": self.rascunho,
                })
            return super().__call__(comando, raiz, **opcoes)

    dub = DraftDuble()
    pr.abrir(raiz, pedido(raiz), rodar=dub, hoje=HOJE)
    assert dub.pediu("gh pr ready 1210")

@pytest.mark.parametrize('onde', ['pytest ci/tests', 'gh pr list', 'gh pr view'])
def test_falha_de_validacao_ou_rede_nunca_imprime_sucesso(tmp_path, capsys, onde):
    raiz = bancada(tmp_path)
    dub = Duble(RESPOSTAS_FELIZES)
    dub.explode_em = onde
    with pytest.raises(pr.ErroDeInstrumentacao):
        pr.abrir(raiz, pedido(raiz), rodar=dub, hoje=HOJE)
    assert 'aberto com recibo:' not in capsys.readouterr().out
    if onde == 'pytest ci/tests':
        assert not dub.pediu('git push')


def test_revisao_remota_antiga_recusa(tmp_path):
    raiz = bancada(tmp_path)
    dub = Duble({**RESPOSTAS_FELIZES, 'gh pr view': json.dumps({'headRefOid': 'c'*40, 'state': 'OPEN', 'isDraft': True})})
    with pytest.raises(pr.ParouPorSeguranca, match='revisão entregue'):
        pr.abrir(raiz, pedido(raiz), rodar=dub, hoje=HOJE)


def test_commit_alterado_por_hook_recusa_antes_do_push(tmp_path):
    raiz = bancada(tmp_path)
    dub = Duble({**RESPOSTAS_FELIZES, 'rev-parse HEAD^{tree}': 'c'*40})
    with pytest.raises(pr.ParouPorSeguranca, match='árvore validada'):
        pr.abrir(raiz, pedido(raiz), rodar=dub, hoje=HOJE)
    assert not dub.pediu('git push')


def test_codigo_alterado_apos_recibo_recusa(tmp_path):
    raiz = bancada(tmp_path)
    dub = Duble({**RESPOSTAS_FELIZES, 'diff --name-only ' + 'b'*40: 'ci/outro.py'})
    with pytest.raises(pr.ParouPorSeguranca, match='difere da validada'):
        pr.abrir(raiz, pedido(raiz), rodar=dub, hoje=HOJE)
    assert not dub.pediu('gh pr view')


def test_indice_alheio_e_preservado(tmp_path):
    raiz = bancada(tmp_path)
    dub = Duble({**RESPOSTAS_FELIZES, 'diff --cached --name-only': 'segredo.env'})
    with pytest.raises(pr.ParouPorSeguranca, match='não declarados'):
        pr.abrir(raiz, pedido(raiz), rodar=dub, hoje=HOJE)
    assert not dub.pediu('git add')


def test_segredo_nao_chega_no_recibo(tmp_path):
    raiz = bancada(tmp_path)
    dub = Duble(RESPOSTAS_FELIZES)
    with pytest.raises(pr.ParouPorSeguranca, match='segredo'):
        pr.abrir(raiz, pedido(raiz, detalhe=DETALHE + ' token=segredo12345'), rodar=dub, hoje=HOJE)
    assert not dub.chamadas


def test_interrupcao_apos_reserva_reusa_identidade(tmp_path):
    raiz = bancada(tmp_path)
    primeira = Duble(RESPOSTAS_FELIZES)
    primeira.explode_em = 'node painel/gerar_manifesto.js'
    with pytest.raises(pr.ErroDeInstrumentacao):
        pr.abrir(raiz, pedido(raiz), rodar=primeira, hoje=HOJE)
    segunda = Duble({**RESPOSTAS_FELIZES, 'gh pr list': json.dumps([{'number':1210,'url':URL_DO_PR}])})
    pr.abrir(raiz, pedido(raiz, continuar=True), rodar=segunda, hoje=HOJE)
    assert not segunda.pediu('reservar.py')
    assert not segunda.pediu('gh pr create')
    assert len(list((raiz/'painel/registros').glob('*.js'))) == 1


def test_retry_apos_recibo_commitado_nao_duplica_registro(tmp_path):
    raiz = bancada(tmp_path)
    pr.abrir(raiz, pedido(raiz), rodar=Duble(RESPOSTAS_FELIZES), hoje=HOJE)
    segunda = Duble({**RESPOSTAS_FELIZES, 'write-tree': 'c'*40, 'rev-parse HEAD^{tree}':'c'*40, 'diff --cached --name-only':'', 'gh pr list':json.dumps([{'number':1210,'url':URL_DO_PR}])})
    pr.abrir(raiz, pedido(raiz, continuar=True), rodar=segunda, hoje=HOJE)
    assert not segunda.pediu('reservar.py')
    assert not segunda.pediu('git commit -F')
    assert len(list((raiz/'painel/registros').glob('*.js'))) == 1


def test_pr_criado_com_resposta_perdida_e_reencontrado(tmp_path):
    raiz = bancada(tmp_path)
    primeira = Duble(RESPOSTAS_FELIZES)
    primeira.explode_em = 'gh pr create'
    with pytest.raises(pr.ErroDeInstrumentacao):
        pr.abrir(raiz, pedido(raiz), rodar=primeira, hoje=HOJE)
    segunda = Duble({**RESPOSTAS_FELIZES, 'gh pr list':json.dumps([{'number':1210,'url':URL_DO_PR}])})
    pr.abrir(raiz, pedido(raiz, continuar=True), rodar=segunda, hoje=HOJE)
    assert not segunda.pediu('gh pr create')


def test_recibo_antigo_nao_cobre_codigo_novo(tmp_path):
    raiz = bancada(tmp_path)
    pr.abrir(raiz, pedido(raiz), rodar=Duble(RESPOSTAS_FELIZES), hoje=HOJE)
    segunda = Duble({**RESPOSTAS_FELIZES, 'write-tree':'c'*40, 'rev-parse HEAD^{tree}':'c'*40, 'diff --name-only ' + 'b'*40:'ci/pr.py', 'reservar.py numero registro':'20260906-078'})
    with pytest.raises(pr.ParouPorSeguranca, match='difere da validada'):
        pr.abrir(raiz, pedido(raiz, continuar=True), rodar=segunda, hoje=HOJE)
    assert segunda.pediu('pytest ci/tests')
    assert segunda.pediu('reservar.py')
    assert len(list((raiz/'painel/registros').glob('*.js'))) == 2


def test_recibo_maior_que_1kb_recusa(tmp_path):
    raiz = bancada(tmp_path)
    with pytest.raises(pr.ParouPorSeguranca, match='1 KB'):
        pr.abrir(raiz, pedido(raiz, detalhe='x'*1100), rodar=Duble(RESPOSTAS_FELIZES), hoje=HOJE)


@pytest.mark.parametrize('tarefa_aberta', ['TAR-001','agent/ci/make-pr'])
def test_correlacao_usa_tentativa_da_abertura(tmp_path, monkeypatch, tarefa_aberta):
    import fila
    monkeypatch.setattr(fila, 'carregar_tarefas', lambda *a: {'TAR-001': {}})
    monkeypatch.setattr(fila, 'carregar_eventos', lambda *a: [])
    raiz = bancada(tmp_path)
    fases = []
    monkeypatch.setattr(pr, '_tentativa_da_abertura', lambda *a: ('tentativa-abertura', tarefa_aberta))
    monkeypatch.setattr(pr.telemetria, 'registrar_fase', lambda fase, resultado, **dados: fases.append((fase, resultado, dados)))
    declarada = tarefa_aberta if tarefa_aberta.startswith('TAR-') else None
    pr.abrir(raiz, pedido(raiz, tarefa=declarada), rodar=Duble(RESPOSTAS_FELIZES), hoje=HOJE)
    assert [(f,r) for f,r,d in fases] == [('fechamento','iniciado'), ('candidato','concluido'), ('validacao','iniciado'), ('validacao','concluido'), ('validacao','iniciado'), ('validacao','concluido'), ('fechamento','concluido')]
    validacoes = [d for f,r,d in fases if f == 'validacao']
    assert validacoes[0]['rodada'] == validacoes[1]['rodada']
    assert validacoes[2]['rodada'] == validacoes[3]['rodada']
    assert validacoes[0]['rodada'] != validacoes[2]['rodada']
    assert 'pr' not in validacoes[0] and 'pr' not in validacoes[1]
    assert validacoes[2]['pr'] == validacoes[3]['pr'] == 1210
    assert {d['tentativa'] for f,r,d in fases} == {'tentativa-abertura'}
    assert {d['tarefa'] for f,r,d in fases} == {tarefa_aberta}
    assert fases[-1][2]['pr'] == 1210
    assert fases[-1][2]['commit'] == 'b'*40


def test_validacao_muda_indice_e_expira_prova(tmp_path):
    raiz = bancada(tmp_path)
    dub = Duble(RESPOSTAS_FELIZES)
    chamadas = 0
    def rodar(comando, raiz, **opcoes):
        nonlocal chamadas
        if comando == ['git','write-tree']:
            chamadas += 1
            return ('a' if chamadas == 1 else 'c')*40
        return dub(comando,raiz)
    with pytest.raises(pr.ParouPorSeguranca, match='alterou a árvore'):
        pr.abrir(raiz, pedido(raiz), rodar=rodar, hoje=HOJE)
    assert not dub.pediu('git push')


def _fila_de_uma_tarefa(tmp_path, monkeypatch, eventos):
    """Bancada com a fila fingida: só os eventos que o caso quer medir."""
    import fila
    raiz = bancada(tmp_path)
    (raiz/'fila/eventos').mkdir(parents=True)
    monkeypatch.setattr(fila, 'carregar_tarefas', lambda *a: {'TAR-001':{}})
    monkeypatch.setattr(fila, 'carregar_eventos', lambda *a: eventos)
    return raiz


def _acoes_da_fila(dub):
    return [c[2] for c in dub.chamadas if len(c) > 2 and c[1] == 'ci/fila.py']


def test_entrega_submete_sem_fechar_a_tarefa_no_proprio_ramo(tmp_path, monkeypatch):
    """Submissão conserva a tarefa aberta até o aceite reconciliado."""
    # guarda: ci/pr.py:660
    raiz = _fila_de_uma_tarefa(tmp_path, monkeypatch, [])
    dub = Duble()
    pr._submeter_fila(raiz, lambda c:dub(c), 'TAR-001', 'agent/ci/tarefa', URL_DO_PR, 'a'*40, 'b'*40)
    assert _acoes_da_fila(dub) == ['submeter']
    assert not any('fechar-pela-entrega' in c for c in dub.chamadas)


def test_continuar_preserva_a_conclusao_sem_criar_evento_posterior(tmp_path, monkeypatch):
    """Uma revisão nova do mesmo PR não escreve depois do evento terminal."""
    # guarda: ci/pr.py:584
    evento = {'tarefa':'TAR-001','evento':'concluida','evidencia':URL_DO_PR}
    caminho_conclusao = 'fila/eventos/concluida.json'
    raiz = _fila_de_uma_tarefa(tmp_path, monkeypatch, [evento])
    (raiz/caminho_conclusao).write_text(json.dumps(evento),encoding='utf-8')
    dub = Duble()
    arquivos = pr._submeter_fila(raiz, lambda c:dub(c), 'TAR-001', 'agent/ci/tarefa', URL_DO_PR, 'a'*40, 'b'*40)
    assert arquivos == [caminho_conclusao]
    assert _acoes_da_fila(dub) == []


def test_entrega_recusa_tarefa_encerrada_por_outro_fato(tmp_path, monkeypatch):
    """Conclusão com outra evidência é encerramento alheio: não se sobrescreve."""
    evento = {'tarefa':'TAR-001','evento':'concluida','evidencia':URL_DO_PR+'0'}
    raiz = _fila_de_uma_tarefa(tmp_path, monkeypatch, [evento])
    dub = Duble()
    with pytest.raises(pr.ParouPorSeguranca, match='outro fato'):
        pr._submeter_fila(raiz, lambda c:dub(c), 'TAR-001', 'agent/ci/tarefa', URL_DO_PR, 'a'*40, 'b'*40)
    assert not dub.chamadas

@pytest.mark.parametrize('ignorado', [False, True])
@pytest.mark.parametrize('alvo', ['relativo','python_absoluto','pytest_absoluto'])
def test_validacao_real_nao_usa_modulo_fora_da_revisao(tmp_path, monkeypatch, ignorado, alvo):
    import subprocess
    monkeypatch.setattr(pr, "base_de_scratch_padrao", lambda: tmp_path / "sessoes")
    entradas = tmp_path / "sessoes" / "ci-prova"
    entradas.mkdir(parents=True)
    origem = tmp_path/'origem'
    subprocess.run(['git','init',str(origem)],check=True,capture_output=True)
    def git(*args, cwd=origem):
        return subprocess.run(['git',*args],cwd=cwd,check=True,capture_output=True,text=True).stdout.strip()
    git('config','user.name','Teste')
    git('config','user.email','teste@example.com')
    git('remote','add','origin','https://github.com/abundanciabr/sitesdoreino.git')
    (origem/'.gitignore').write_text('necessario.py\n' if ignorado else '',encoding='utf-8')
    (origem/'ci').mkdir()
    (origem/'ci/pr.py').write_text('def abrir(): pass\n',encoding='utf-8')
    git('add','.gitignore','ci/pr.py')
    git('commit','-m','base')
    raiz=tmp_path/'bancada'
    git('worktree','add','-b','agent/ci/prova',str(raiz))
    pr.telemetria.registrar_fase('abertura','concluido',tarefa='agent/ci/prova',tentativa='legada',branch='agent/ci/prova',commit=git('rev-parse','HEAD'),cwd=str(raiz))
    (raiz/'check.py').write_text('import necessario\ndef test_entregue():\n    assert necessario.valor == 42\n',encoding='utf-8')
    (raiz/'necessario.py').write_text('valor = 42\n',encoding='utf-8')
    (entradas/'mensagem.txt').write_text('ci: prova\n\n'+COAUTOR+'\n',encoding='utf-8')
    (entradas/'corpo.md').write_text('Teste isolado.',encoding='utf-8')
    comando = [sys.executable,'check.py'] if alvo == 'relativo' else [sys.executable,str(raiz/'check.py')]
    if alvo == 'pytest_absoluto':
        comando = [sys.executable,'-m','pytest',str(raiz/'check.py'),'-q']
    (entradas/'validacao.json').write_text(json.dumps({'comandos':[comando]}),encoding='utf-8')
    entrada=pr.Pedido(titulo='ci: prova',mensagem_arquivo=entradas/'mensagem.txt',corpo_arquivo=entradas/'corpo.md',validacao_arquivo=entradas/'validacao.json',arquivos=['check.py'],detalhe=DETALHE)
    def executar(comando, cwd, **opcoes):
        assert comando[:2] != ['git','push'], 'publicaria código dependente de arquivo não entregue'
        return pr.rodar(comando,cwd,**opcoes)
    with pytest.raises((pr.ErroDeInstrumentacao,pr.ParouPorSeguranca)) as erro:
        pr.abrir(raiz,entrada,rodar=executar)
    logs=list((origem/'.git'/pr.telemetria.PASTA/'validacoes-pr').rglob('*.log'))
    if alvo == 'relativo':
        assert 'log privado' in erro.value.detalhe
        assert len(logs)==1
        assert 'ModuleNotFoundError' in logs[0].read_text(encoding='utf-8')
    else:
        assert 'fora da revisão' in str(erro.value)
        assert not logs
    assert (raiz/'necessario.py').exists()
    assert len(git('worktree','list','--porcelain').split('worktree '))-1 == 2


def _repositorio_de_validacao(tmp_path):
    import subprocess

    origem = tmp_path / "origem-407"
    subprocess.run(["git", "init", str(origem)], check=True, capture_output=True)
    def git(*args):
        return subprocess.run(["git", *args], cwd=origem, check=True,
                              capture_output=True, text=True).stdout.strip()
    git("config", "user.name", "Teste")
    git("config", "user.email", "teste@example.com")
    (origem / "fonte.py").write_text("valor = 1\n", encoding="utf-8")
    (origem / "troca.py").write_text(
        "import subprocess, sys\n"
        "subprocess.run(['git', 'checkout', '--detach', sys.argv[1]], check=True)\n",
        encoding="utf-8",
    )
    git("add", ".")
    git("commit", "-m", "bom")
    correto = git("rev-parse", "HEAD")
    (origem / "fonte.py").write_text("valor = 2\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-m", "outra revisao")
    outro = git("rev-parse", "HEAD")
    raiz = tmp_path / "bancada-407"
    git("worktree", "add", "-b", "agent/ci/prova-407", str(raiz), correto)
    return origem, raiz, correto, outro


def test_validacao_407_aceita_revisao_correta_e_arquivos_temporarios(tmp_path):
    _, raiz, correto, _ = _repositorio_de_validacao(tmp_path)
    provas = pr._validar(
        raiz, correto, pr.rodar,
        [[sys.executable, "-c", "from pathlib import Path; p=Path('temp.txt'); p.write_text('ok'); assert p.read_text() == 'ok'"]],
        lambda *_: None,
    )

    assert len(provas) == 1


def test_validacao_407_recusa_troca_de_revisao_mesmo_com_exit_zero(tmp_path):
    _, raiz, correto, outro = _repositorio_de_validacao(tmp_path)

    with pytest.raises(pr.ParouPorSeguranca, match="trocou a revisão"):
        pr._validar(
            raiz, correto, pr.rodar,
            [[sys.executable, "troca.py", outro]],
            lambda *_: None,
        )


def test_validacao_407_recusa_alteracao_de_fonte_rastreada(tmp_path):
    _, raiz, correto, _ = _repositorio_de_validacao(tmp_path)

    with pytest.raises(pr.ParouPorSeguranca, match="alterou fontes rastreadas"):
        pr._validar(
            raiz, correto, pr.rodar,
            [[sys.executable, "-c", "from pathlib import Path; Path('fonte.py').write_text('quebrado')"]],
            lambda *_: None,
        )


def test_validacao_407_recusa_fonte_nao_rastreada_de_injecao(tmp_path):
    _, raiz, correto, _ = _repositorio_de_validacao(tmp_path)

    with pytest.raises(pr.ParouPorSeguranca, match="fontes não rastreadas"):
        pr._validar(
            raiz, correto, pr.rodar,
            [[sys.executable, "-c", "from pathlib import Path; Path('conftest.py').write_text('')"]],
            lambda *_: None,
        )


def test_retomada_407_nao_reutiliza_prova_invalidada(tmp_path):
    raiz = bancada(tmp_path)
    primeira = Duble(RESPOSTAS_FELIZES)
    mutou = False

    def executar_primeira(comando, cwd, **opcoes):
        nonlocal mutou
        if comando == ["pytest", "ci/tests"] and "log" in opcoes:
            mutou = True
            return "passo verde\n"
        if comando == ["git", "rev-parse", "HEAD"] and mutou and cwd != raiz:
            return "c" * 40
        return primeira(comando, cwd, **opcoes)

    with pytest.raises(pr.ParouPorSeguranca, match="trocou a revisão"):
        pr.abrir(raiz, pedido(raiz), rodar=executar_primeira, hoje=HOJE)

    segunda = Duble(RESPOSTAS_FELIZES)
    pr.abrir(raiz, pedido(raiz, continuar=True), rodar=segunda, hoje=HOJE)

    assert segunda.linhas.count("pytest ci/tests") == 2
    assert segunda.pediu("git worktree add")


def test_log_privado_preserva_stdout_stderr_e_redige_segredos(tmp_path):
    log=tmp_path/'prova.log'
    pr.rodar([sys.executable,'-c',"import sys;print('saida conferida');print('token=segredo12345',file=sys.stderr)"],tmp_path,log=log)
    texto=log.read_text(encoding='utf-8')
    assert 'saida conferida' in texto
    assert 'STDERR' in texto
    assert '<REDIGIDO>' in texto
    assert 'segredo12345' not in texto
    with pytest.raises(pr.ErroDeInstrumentacao):
        pr.rodar([sys.executable,'-c',"import sys;print('inicio conferido'+'x'*12000+'falha conferida',file=sys.stderr);sys.exit(1)"],tmp_path,log=log)
    assert 'falha conferida' in log.read_text(encoding='utf-8')
    assert 'inicio conferido' in log.read_text(encoding='utf-8')
    assert 'x'*12000 in log.read_text(encoding='utf-8')


def test_metadado_invalido_nao_bloqueia_e_tarefa_e_herdada(tmp_path,monkeypatch):
    raiz=bancada(tmp_path)
    ramo='agent/ci/prova'
    valido=dict(tarefa='TAR-123',tentativa='abertura123',branch=ramo,commit='a'*40,pr=None,fase='abertura',resultado='concluido',contexto_bytes=None)
    valido['id']=pr.telemetria.identidade_fase(valido)
    valido['quando']='2026-09-08T02:00:00+00:00'
    invalido={**valido,'quando':None}
    forjado={**valido,'tarefa':'TAR-999','quando':'2026-09-09T02:00:00+00:00'}
    monkeypatch.setattr(pr.telemetria,'ler_tudo',lambda *a:[invalido,valido,forjado])
    assert pr._tentativa_da_abertura(raiz,ramo)==('abertura123','TAR-123')

@pytest.mark.parametrize('prefixo', ['', '--arquivo='])
def test_argumento_absoluto_original_e_recusado(tmp_path, prefixo):
    raiz=bancada(tmp_path)
    comandos=[[sys.executable,prefixo+str(raiz/'check.py')]]
    with pytest.raises(pr.ParouPorSeguranca,match='fora da revisão'):
        pr._validar(raiz,'a'*40,Duble(RESPOSTAS_FELIZES),comandos,lambda *a:None)


@pytest.mark.parametrize('canal',['stdout','stderr'])
def test_json_com_credencial_nao_vaza_no_log(tmp_path,canal):
    log=tmp_path/'prova.log'
    comando=[sys.executable,'-c',f"import json,sys;print(json.dumps(dict(token='SEGREDO_DE_TESTE_123')),file=sys.{canal})"]
    pr.rodar(comando,tmp_path,log=log)
    assert 'SEGREDO_DE_TESTE_123' not in log.read_text(encoding='utf-8')
    assert '<REDIGIDO>' in log.read_text(encoding='utf-8')


def test_prova_final_avalia_o_sha_com_recibo_e_impede_sucesso(tmp_path):
    raiz=bancada(tmp_path)
    dub=Duble(RESPOSTAS_FELIZES)
    final=False
    revisoes=[]
    def executar(comando, cwd, **opcoes):
        nonlocal final
        if comando[:3]==['git','commit','-m']:
            final=True
        if comando==['git','rev-parse','HEAD'] and final:
            return 'c'*40
        if comando[:3]==['git','worktree','add']:
            revisoes.append(comando[-1])
        if comando==['pytest','ci/tests'] and final:
            raise pr.ErroDeInstrumentacao('recibo final inválido','o teste da revisão entregue reprovou')
        return dub(comando,cwd,**opcoes)
    with pytest.raises(pr.ErroDeInstrumentacao,match='não aprovada'):
        pr.abrir(raiz,pedido(raiz),rodar=executar,hoje=HOJE)
    assert revisoes==['b'*40,'c'*40]
    assert not dub.pediu('git push origin')
    assert not dub.pediu('gh pr view')


def test_authorization_bearer_nao_deixa_o_token_visivel():
    for texto in ['Authorization: Bearer SEGREDO_DE_TESTE_123', '{"Authorization":"Bearer SEGREDO_DE_TESTE_123"}']:
        assert 'SEGREDO_DE_TESTE_123' not in pr._sanitizar(texto)


def test_aspas_escapadas_normais_nao_sao_tratadas_como_segredo(tmp_path):
    raiz=bancada(tmp_path)
    texto=DETALHE+r' Exemplo de texto com \"nome\" preservado.'
    assert pr._sanitizar(texto)==texto
    pr._conferir_o_pedido(raiz,pedido(raiz,detalhe=texto))


@pytest.mark.parametrize('prazo', [1, 1800, 7200, None])
def test_prazo_do_json_chega_as_duas_provas(tmp_path, prazo):
    raiz = bancada(tmp_path)
    dados = {'comandos': [['pytest', 'ci/tests']]}
    if prazo is not None:
        dados['prazo_segundos'] = prazo
    (raiz/'validacao.json').write_text(json.dumps(dados), encoding='utf-8')
    recebidos = []
    dub = Duble(RESPOSTAS_FELIZES)
    def executar(comando, cwd, **opcoes):
        if 'log' in opcoes:
            recebidos.append(opcoes.get('prazo_segundos'))
        else:
            assert 'prazo_segundos' not in opcoes
        return dub(comando, cwd, **opcoes)
    pr.abrir(raiz, pedido(raiz), rodar=executar, hoje=HOJE)
    assert recebidos == [prazo or 900, prazo or 900]


@pytest.mark.parametrize('prazo', [None, True, False, 0, -1, 7201, 1.5, 900.0, '900', '', float('nan'), float('inf'), -float('inf'), [], {}])
def test_prazo_invalido_recusa_antes_de_efeitos(tmp_path, prazo):
    raiz = bancada(tmp_path)
    (raiz/'validacao.json').write_text(json.dumps({'comandos': [['pytest']], 'prazo_segundos': prazo}), encoding='utf-8')
    dub = Duble(RESPOSTAS_FELIZES)
    with pytest.raises(pr.ParouPorSeguranca, match='prazo_segundos'):
        pr.abrir(raiz, pedido(raiz), rodar=dub, hoje=HOJE)
    assert not dub.chamadas


def test_timeout_e_reprovacao_tem_resultados_distintos(tmp_path):
    log = tmp_path/'prova.log'
    with pytest.raises(pr.ValidacaoReprovada, match='exit 7'):
        pr.rodar([sys.executable, '-c', 'raise SystemExit(7)'], tmp_path, log=log, prazo_segundos=1)
    assert 'FAIL' in log.read_text(encoding='utf-8')
    assert 'TIMEOUT' not in log.read_text(encoding='utf-8')
    assert 'ok' in pr.rodar([sys.executable, '-c', "print('ok')"], tmp_path, log=log, prazo_segundos=1)
    assert 'PASS' in log.read_text(encoding='utf-8')


@pytest.mark.parametrize('prova_expirada', [1, 2])
def test_retomada_apos_timeout_exige_duas_novas_provas(tmp_path, prova_expirada):
    raiz = bancada(tmp_path)
    dub = Duble(RESPOSTAS_FELIZES)
    quantidade = 0
    def executar(comando, cwd, **opcoes):
        nonlocal quantidade
        if 'log' in opcoes:
            quantidade += 1
            if quantidade == prova_expirada:
                raise pr.PrazoDeValidacaoExcedido('TIMEOUT', 'Retome com nova validação.')
        return dub(comando, cwd, **opcoes)
    mensagens = []
    with pytest.raises(pr.PrazoDeValidacaoExcedido):
        pr.abrir(raiz, pedido(raiz), rodar=executar, hoje=HOJE, dizer=mensagens.append)
    assert not dub.pediu('git push origin')
    if prova_expirada == 1:
        assert not dub.pediu('gh pr create')
        assert not list((raiz/'painel/registros').glob('*.js'))
    segunda = Duble({**RESPOSTAS_FELIZES, 'gh pr list': json.dumps([{'number': 1210, 'url': URL_DO_PR}])})
    pr.abrir(raiz, pedido(raiz, continuar=True), rodar=segunda, hoje=HOJE)
    assert segunda.linhas.count('pytest ci/tests') == 2
    assert not segunda.pediu('gh pr create')
    assert len(list((raiz/'painel/registros').glob('*.js'))) == 1


@pytest.mark.parametrize('pai_encerra', [False, True])
@pytest.mark.parametrize('nova_sessao', [False, True])
@pytest.mark.parametrize('atraso_do_neto', [0, 3])
def test_timeout_encerra_filhos_e_netos_reais(
    tmp_path, pai_encerra, nova_sessao, atraso_do_neto, monkeypatch
):
    import os
    import signal
    import subprocess
    import time
    script = tmp_path/'processos.py'
    script.write_text('''import os, pathlib, subprocess, sys, time
profundidade = int(sys.argv[1])
if profundidade == 0:
    time.sleep(float(sys.argv[4]))
pathlib.Path(f"pid-{profundidade}").write_text(str(os.getpid()))
print(f"iniciado {profundidade}", flush=True)
print("saída íntegra " + "x"*12000, flush=True)
if profundidade:
    subprocess.Popen([sys.executable, __file__, str(profundidade-1), sys.argv[2], sys.argv[3], sys.argv[4]], start_new_session=sys.argv[3] == "nova")
if profundidade == 2 and sys.argv[2] == "sair":
    sys.exit(0)
print("token=SEGREDO_CONTROLADO", file=sys.stderr, flush=True)
time.sleep(60)
''', encoding='utf-8')
    comunicar = subprocess.Popen.communicate

    def comunicar_com_arvore_pronta(processo, input=None, timeout=None):
        if timeout == 2:
            limite_da_preparacao = time.monotonic() + 30
            while len(list(tmp_path.glob('pid-*'))) != 3:
                assert time.monotonic() < limite_da_preparacao, (
                    'preparação incompleta: pai, filho e neto não nasceram em 30s'
                )
                try:
                    comunicar(processo, input=input, timeout=.05)
                except subprocess.TimeoutExpired:
                    continue
                pytest.fail('a preparação encerrou sem pai, filho e neto')
        return comunicar(processo, input=input, timeout=timeout)

    monkeypatch.setattr(subprocess.Popen, 'communicate', comunicar_com_arvore_pronta)

    def vivo(pid):
        if os.name == 'nt':
            import ctypes
            from ctypes import wintypes
            api = ctypes.WinDLL('kernel32', use_last_error=True)
            api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            api.OpenProcess.restype = wintypes.HANDLE
            api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            api.CloseHandle.argtypes = [wintypes.HANDLE]
            handle = api.OpenProcess(0x100000, False, pid)
            if not handle:
                return False
            try:
                return api.WaitForSingleObject(handle, 0) == 258
            finally:
                api.CloseHandle(handle)
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        estado = Path(f'/proc/{pid}/stat')
        return not estado.exists() or estado.read_text().split(') ')[1][0] != 'Z'
    log = tmp_path/'timeout.log'
    try:
        with pytest.raises(pr.PrazoDeValidacaoExcedido, match='TIMEOUT'):
            pr.rodar([sys.executable, 'processos.py', '2', 'sair' if pai_encerra else 'ficar', 'nova' if nova_sessao else 'mesma', str(atraso_do_neto)], tmp_path, log=log, prazo_segundos=2)
        pids = [int(p.read_text()) for p in tmp_path.glob('pid-*')]
        assert len(pids) == 3, 'pai, filho e neto precisam ter executado'
        limite = time.monotonic() + 3
        while any(vivo(pid) for pid in pids) and time.monotonic() < limite:
            time.sleep(.05)
        assert not any(vivo(pid) for pid in pids), 'validação deixou processos órfãos'
        texto = log.read_text(encoding='utf-8')
        assert 'TIMEOUT' in texto and 'iniciado 0' in texto
        assert 'saída íntegra ' + 'x'*12000 in texto
        assert '<REDIGIDO>' in texto and 'SEGREDO_CONTROLADO' not in texto
        assert 'PASS' not in texto
    finally:
        for arquivo in tmp_path.glob('pid-*'):
            pid = int(arquivo.read_text())
            if vivo(pid):
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/F', '/T', '/PID', str(pid)], capture_output=True)
                else:
                    os.kill(pid, signal.SIGKILL)


def test_instrumento_inexistente_preserva_error(tmp_path):
    log = tmp_path/'error.log'
    with pytest.raises(pr.ErroDeInstrumentacao, match='não pôde executar'):
        pr.rodar(['executavel-inexistente-f1-03'], tmp_path, log=log, prazo_segundos=1)
    texto = log.read_text(encoding='utf-8')
    assert 'ERROR' in texto and 'PASS' not in texto




@pytest.mark.parametrize('erro,codigo,resultado', [
    (pr.ValidacaoReprovada, 1, 'FAIL'),
    (pr.PrazoDeValidacaoExcedido, 2, 'TIMEOUT'),
])
def test_cli_distingue_reprovacao_de_timeout(tmp_path, monkeypatch, capsys, erro, codigo, resultado):
    raiz = bancada(tmp_path)
    monkeypatch.setattr(pr, 'raiz_do_repo', lambda: raiz)
    def reprovar(*args, **kwargs):
        raise erro(resultado, 'Leia o log e retome com nova prova.')
    monkeypatch.setattr(pr, 'abrir', reprovar)
    retorno = pr.main([
        '--titulo', 'ci: prazo', '--mensagem-arquivo', str(raiz/'mensagem.txt'),
        '--corpo-arquivo', str(raiz/'corpo.md'), '--arquivos', 'ci/pr.py',
        '--detalhe', DETALHE, '--validacao-arquivo', str(raiz/'validacao.json'),
    ])
    assert retorno == codigo
    assert resultado in capsys.readouterr().out



def test_fechamento_submete_tar_declarada_e_recibo_a_identifica(tmp_path, monkeypatch):
    import fila
    raiz = bancada(tmp_path)
    monkeypatch.setattr(pr, "_tentativa_da_abertura", lambda *args: ("tentativa-1", "TAR-001"))
    monkeypatch.setattr(fila, "carregar_tarefas", lambda *args: {"TAR-001": {}})
    monkeypatch.setattr(fila, "carregar_eventos", lambda *args: [])
    dub = Duble(RESPOSTAS_FELIZES)
    pr.abrir(raiz, pedido(raiz, tarefa="TAR-001"), rodar=dub, hoje=HOJE)
    assert dub.pediu("ci/fila.py submeter TAR-001")
    assert not dub.pediu("ci/fila.py concluir")
    assert dub.pediu("--revisao " + "b" * 40)
    assert dub.pediu("--arvore " + "a" * 40)
    recibo = next((raiz / "painel/registros").glob("*.js"))
    assert pr.campos_lidos(recibo.read_text(encoding="utf-8"))["tarefa"] == "TAR-001"


def test_tar_inexistente_recusa_antes_de_git_add_ou_publicacao(tmp_path):
    raiz = bancada(tmp_path)
    dub = Duble(RESPOSTAS_FELIZES)
    with pytest.raises(pr.ParouPorSeguranca, match="tarefa"):
        pr.abrir(raiz, pedido(raiz, tarefa="TAR-999"), rodar=dub, hoje=HOJE)
    assert not dub.pediu("git add")
    assert not dub.pediu("git push")
    assert not dub.pediu("gh pr create")


@pytest.mark.parametrize("onde", ["titulo", "corpo", "detalhe"])
def test_tar_citada_no_texto_nao_escolhe_tarefa(tmp_path, monkeypatch, onde):
    """PRs #2189 e #2190: citar outra tarefa no texto a fechou de verdade."""
    # guarda: ci/pr.py:692
    import fila
    raiz = bancada(tmp_path)
    monkeypatch.setattr(fila, "carregar_tarefas", lambda *args: {"TAR-001": {}})
    monkeypatch.setattr(fila, "carregar_eventos", lambda *args: [])
    citacao = "Caso histórico TAR-001."
    texto = {"titulo": {"titulo": "fila: corrigir conclusão TAR-001"},
             "detalhe": {"detalhe": DETALHE + " " + citacao}}.get(onde, {})
    if onde == "corpo":
        (raiz / "corpo.md").write_text("## O que muda\n\n" + citacao + "\n", encoding="utf-8")
    dub = Duble({**RESPOSTAS_FELIZES, "git show " + "b" * 40 + ":ci/pr.py": Path(pr.__file__).read_text(encoding="utf-8")})
    with pytest.raises(pr.ParouPorSeguranca) as recusa:
        pr.abrir(raiz, pedido(raiz, **texto), rodar=dub, hoje=HOJE)
    assert "--tarefa" in recusa.value.o_que_fazer
    assert not dub.pediu("ci/fila.py")
    assert not dub.pediu("git add")
    assert not dub.pediu("gh pr create")


def test_sem_tarefa_a_recusa_ensina_a_tar_da_abertura(tmp_path, monkeypatch):
    # guarda: ci/pr.py:692
    raiz = bancada(tmp_path)
    monkeypatch.setattr(pr, "_tentativa_da_abertura", lambda *args: ("tentativa-1", "TAR-001"))
    dub = Duble({**RESPOSTAS_FELIZES, "git show " + "b" * 40 + ":ci/pr.py": Path(pr.__file__).read_text(encoding="utf-8")})
    with pytest.raises(pr.ParouPorSeguranca) as recusa:
        pr.abrir(raiz, pedido(raiz), rodar=dub, hoje=HOJE)
    assert "Repita com TAR=TAR-001 (make pr) ou --tarefa TAR-001 (python ci/pr.py)" in recusa.value.o_que_fazer
    assert not dub.pediu("ci/fila.py")
    assert not dub.pediu("git add")


def test_sessao_legada_aberta_com_tar_recusa_sem_tarefa(tmp_path, monkeypatch):
    """Na main antiga a TAR da abertura recebia eventos; sem --tarefa, calar a perde."""
    raiz = bancada(tmp_path)
    monkeypatch.setattr(pr, "_tentativa_da_abertura", lambda *args: ("tentativa-1", "TAR-001"))
    dub = Duble(RESPOSTAS_FELIZES)
    with pytest.raises(pr.ParouPorSeguranca) as recusa:
        pr.abrir(raiz, pedido(raiz), rodar=dub, hoje=HOJE)
    assert "TAR=TAR-001" in recusa.value.o_que_fazer
    assert not dub.pediu("ci/fila.py")
    assert not dub.pediu("git add")
    assert not dub.pediu("git push")


@pytest.mark.parametrize("fim_da_dependencia", [None, "cancelada"])
def test_tar_com_dependencia_nao_concluida_recusa_antes_de_publicar(tmp_path, monkeypatch, fim_da_dependencia):
    # guarda: ci/pr.py:714
    import fila
    raiz = bancada(tmp_path)
    monkeypatch.setattr(fila, "carregar_tarefas", lambda *args: {
        "TAR-001": {"depende_de": []}, "TAR-002": {"depende_de": ["TAR-001"]}})
    eventos = [{"tarefa": "TAR-001", "evento": fim_da_dependencia, "quem": "outra", "detalhe": "trocada",
                "quando": "2026-09-01T00:00:00+00:00"}] if fim_da_dependencia else []
    monkeypatch.setattr(fila, "carregar_eventos", lambda *args: eventos)
    dub = Duble(RESPOSTAS_FELIZES)
    with pytest.raises(pr.ParouPorSeguranca) as recusa:
        pr.abrir(raiz, pedido(raiz, tarefa="TAR-002"), rodar=dub, hoje=HOJE)
    estado = fila.CANCELADA if fim_da_dependencia else fila.NA_FILA
    assert f"dependência não concluída: TAR-001 ({estado})" in recusa.value.resumo
    assert "depende_de" in recusa.value.o_que_fazer
    assert "merge de origin/main" in recusa.value.o_que_fazer
    assert not dub.pediu("ci/fila.py")
    assert not dub.pediu("git add")
    assert not dub.pediu("gh pr create")


def test_tar_com_dependencia_concluida_segue_para_a_submissao(tmp_path, monkeypatch):
    import fila
    raiz = bancada(tmp_path)
    monkeypatch.setattr(fila, "carregar_tarefas", lambda *args: {
        "TAR-001": {"depende_de": []}, "TAR-002": {"depende_de": ["TAR-001"]}})
    monkeypatch.setattr(fila, "carregar_eventos", lambda *args: [
        {"tarefa": "TAR-001", "evento": "concluida", "quem": "outra", "evidencia": "PR #1",
         "quando": "2026-09-01T00:00:00+00:00"}])
    dub = Duble(RESPOSTAS_FELIZES)
    pr.abrir(raiz, pedido(raiz, tarefa="TAR-002"), rodar=dub, hoje=HOJE)
    assert dub.pediu("ci/fila.py submeter TAR-002")



def test_tar_explicita_nao_confunde_tarefa_citada_com_dependencia(tmp_path, monkeypatch):
    import fila
    raiz = bancada(tmp_path)
    (raiz / "corpo.md").write_text("Corrige TAR-001. Caso histórico TAR-077.", encoding="utf-8")
    monkeypatch.setattr(fila, "carregar_tarefas", lambda *args: {"TAR-001": {}, "TAR-077": {}})
    monkeypatch.setattr(fila, "carregar_eventos", lambda *args: [])
    dub = Duble(RESPOSTAS_FELIZES)
    pr.abrir(raiz, pedido(raiz, tarefa="TAR-001"), rodar=dub, hoje=HOJE)
    assert dub.pediu("ci/fila.py submeter TAR-001")
    assert not dub.pediu("ci/fila.py submeter TAR-077")



def test_abertura_nova_sem_tar_recusa_antes_de_publicar(tmp_path):
    raiz = bancada(tmp_path)
    dub = Duble({**RESPOSTAS_FELIZES, "git show " + "b" * 40 + ":ci/pr.py": Path(pr.__file__).read_text(encoding="utf-8")})
    with pytest.raises(pr.ParouPorSeguranca, match="tarefa"):
        pr.abrir(raiz, pedido(raiz), rodar=dub, hoje=HOJE)
    assert not dub.pediu("git add")
    assert not dub.pediu("git push")


def test_abertura_sem_proveniencia_nao_presume_sessao_legada(tmp_path, monkeypatch):
    raiz = bancada(tmp_path)
    monkeypatch.setattr(pr.telemetria, "ler_tudo", lambda *a: [])
    dub = Duble(RESPOSTAS_FELIZES)
    with pytest.raises(pr.ParouPorSeguranca, match="tarefa"):
        pr.abrir(raiz, pedido(raiz), rodar=dub, hoje=HOJE)
    assert not dub.pediu("git add")
    assert not dub.pediu("git push")


def test_abertura_com_revisao_ilegivel_nao_presume_sessao_legada(tmp_path):
    raiz = bancada(tmp_path)
    dub = Duble({**RESPOSTAS_FELIZES, "git show " + "b" * 40 + ":ci/pr.py": ""})
    with pytest.raises(pr.ParouPorSeguranca, match="tarefa"):
        pr.abrir(raiz, pedido(raiz), rodar=dub, hoje=HOJE)
    assert not dub.pediu("git add")


@pytest.mark.parametrize("ultimo_evento", ["concluida", "cancelada", "reivindicacao_expirada", "devolvida"])
def test_tar_explicita_ignora_posse_historica_encerrada(tmp_path, monkeypatch, ultimo_evento):
    import fila
    raiz = bancada(tmp_path)
    monkeypatch.setattr(fila, "carregar_tarefas", lambda *args: {"TAR-001": {}, "TAR-077": {}})
    eventos = [
        {"tarefa": "TAR-077", "evento": "reivindicada", "quem": "agent/ci/make-pr", "quando": "2026-09-01T00:00:00+00:00"},
        {"tarefa": "TAR-077", "evento": ultimo_evento, "quem": "agent/ci/make-pr", "quando": "2026-09-02T00:00:00+00:00"},
    ]
    monkeypatch.setattr(fila, "carregar_eventos", lambda *args: eventos)
    dub = Duble(RESPOSTAS_FELIZES)
    pr.abrir(raiz, pedido(raiz, tarefa="TAR-001"), rodar=dub, hoje=HOJE)
    assert dub.pediu("ci/fila.py submeter TAR-001")



def test_propagacao_do_sha_reconsulta_sem_repetir_recibo_ou_validacao(tmp_path, monkeypatch):
    import time
    monkeypatch.setattr(time, "sleep", lambda segundos: None)
    raiz = bancada(tmp_path)
    dub = Duble(RESPOSTAS_FELIZES)
    consultas = []
    def executar(comando, raiz, **opcoes):
        if comando[:3] == ["gh", "pr", "view"]:
            consultas.append(comando)
            return json.dumps({"headRefOid": ("c" if len(consultas) <= 2 else "b") * 40,
                               "state": "OPEN", "isDraft": dub.rascunho})
        return dub(comando, raiz, **opcoes)
    assert pr.abrir(raiz, pedido(raiz), rodar=executar, hoje=HOJE).startswith("PR 1210")
    assert len(consultas) == 4
    assert sum("reservar.py numero registro" in linha for linha in dub.linhas) == 1
    assert sum("worktree add --detach" in linha for linha in dub.linhas) == 2
    assert len(list((raiz / "painel/registros").glob("*.js"))) == 1


@pytest.mark.parametrize("remoto", [
    {"headRefOid": "c" * 40, "state": "OPEN", "isDraft": False},
    {"headRefOid": "b" * 40, "state": "CLOSED", "isDraft": False},
    {"headRefOid": "b" * 40, "state": "OPEN"},
])
def test_propagacao_esgota_consultas_sem_aprovar_revisao_ou_estado_errados(tmp_path, monkeypatch, remoto):
    import time
    monkeypatch.setattr(time, "sleep", lambda segundos: None)
    raiz = bancada(tmp_path)
    dub = Duble(RESPOSTAS_FELIZES)
    consultas = []
    def executar(comando, raiz, **opcoes):
        if comando[:3] == ["gh", "pr", "view"]:
            consultas.append(comando)
            if len(consultas) == 1:
                return json.dumps({"headRefOid": "b" * 40, "state": "OPEN", "isDraft": True})
            return json.dumps(remoto)
        return dub(comando, raiz, **opcoes)
    with pytest.raises(pr.ParouPorSeguranca, match="após 3 consultas"):
        pr.abrir(raiz, pedido(raiz), rodar=executar, hoje=HOJE)
    assert len(consultas) == 4
    assert not dub.pediu("gh pr ready")


def test_propagacao_de_ready_exige_estado_final_confirmado(tmp_path, monkeypatch):
    import time
    monkeypatch.setattr(time, "sleep", lambda segundos: None)
    raiz = bancada(tmp_path)
    dub = Duble(RESPOSTAS_FELIZES)
    consultas = []
    def executar(comando, raiz, **opcoes):
        if comando[:3] == ["gh", "pr", "view"]:
            consultas.append(comando)
            return json.dumps({"headRefOid": "b" * 40, "state": "OPEN", "isDraft": len(consultas) < 4})
        return dub(comando, raiz, **opcoes)
    assert pr.abrir(raiz, pedido(raiz), rodar=executar, hoje=HOJE).startswith("PR 1210")
    assert len(consultas) == 4
    assert sum("gh pr ready" in linha for linha in dub.linhas) == 1


def _bancada_com_painel_geravel(tmp_path):
    import shutil
    import subprocess

    _, raiz, _, _ = _repositorio_de_validacao(tmp_path)
    painel = raiz / "painel"
    (painel / "registros").mkdir(parents=True)
    for nome in ("gerar_manifesto.js", "logica.js", "areas.json", "painel.template.html"):
        shutil.copy2(RAIZ_DO_REPO / "painel" / nome, painel / nome)
    registro = {"arquivo": "20260912-001-prova", "tipo": "nota", "quando": "2026-09-12",
                "titulo": "Registro da prova", "detalhe": DETALHE, "autoridade": "sessao",
                "evidencia": None, "verificado_em": None, "precisa_do_dono": False,
                "responde_a": None, "gravidade": "info", "frente": "fabrica", "area": "ci",
                "vence_em_dias": None}
    (painel / "registros/20260912-001-prova.js").write_text(
        "(window.REGISTROS = window.REGISTROS || []).push(" + json.dumps(registro) + ");", encoding="utf-8")
    (raiz / ".gitignore").write_text("painel/painel.html\npainel/livro-*.js\nextra.py\nignorada/\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=raiz, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "painel canonico"], cwd=raiz, check=True, capture_output=True)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=raiz, text=True).strip()
    return raiz, commit


def test_validacao_aceita_geracao_canonica_deterministica(tmp_path):
    raiz, commit = _bancada_com_painel_geravel(tmp_path)
    provas = pr._validar(raiz, commit, pr.rodar, [
        ["node", "painel/gerar_manifesto.js"], ["node", "painel/gerar_manifesto.js", "--conferir"]
    ], lambda *_: None)
    assert len(provas) == 2
    assert not (raiz / "painel/livro-202609.js").exists()


@pytest.mark.parametrize("acao", [
    "Path('painel/livro-202609.js').write_text('process.exit(0)')",
    "Path('painel/livro-202609.js').unlink()",
    "Path('painel/painel.html').write_text('adulterado')",
])
def test_validacao_recusa_artefato_adulterado_mesmo_com_nome_legitimo(tmp_path, acao):
    # guarda: ci/pr.py:487
    raiz, commit = _bancada_com_painel_geravel(tmp_path)
    with pytest.raises(pr.ParouPorSeguranca, match="artefato"):
        pr._validar(raiz, commit, pr.rodar, [
            [sys.executable, "-c", "from pathlib import Path; " + acao]
        ], lambda *_: None)


@pytest.mark.parametrize("arquivo", ["extra.py", "ignorada/injecao.py", "painel/livro-202608.js"])
def test_validacao_recusa_fonte_ignorada_extra_apos_preparar_artefatos(tmp_path, arquivo):
    # guarda: ci/pr.py:505
    raiz, commit = _bancada_com_painel_geravel(tmp_path)
    with pytest.raises(pr.ParouPorSeguranca, match="fontes não rastreadas"):
        pr._validar(raiz, commit, pr.rodar, [[sys.executable, "-c",
            f"from pathlib import Path; p=Path({arquivo!r}); p.parent.mkdir(exist_ok=True); p.write_text('arbitrario')"
        ]], lambda *_: None)


@pytest.mark.parametrize("troca", [
    {"detalhe": "x" * 1100},
    {"detalhe": "á" * 300},
    {"evidencia": "prova " * 170},
])
def test_recibo_invalido_recusa_antes_de_validacao_e_efeitos(tmp_path, troca):
    raiz = bancada(tmp_path)
    dub = Duble(RESPOSTAS_FELIZES)
    with pytest.raises(pr.ParouPorSeguranca, match="1 KB"):
        pr.abrir(raiz, pedido(raiz, **troca), rodar=dub, hoje=HOJE)
    assert not dub.pediu("pytest")
    assert not dub.pediu("git add")
    assert not dub.pediu("git push")
    assert not dub.pediu("gh pr create")
    assert not dub.pediu("reservar.py")
    assert not list((raiz / "painel/registros").glob("*.js"))


def test_codex_preserva_area_e_provas_da_bancada(tmp_path, monkeypatch):
    raiz = bancada(tmp_path)
    monkeypatch.setattr(pr, "_tentativa_da_abertura", lambda *a: ("tentativa", "legada"))
    monkeypatch.setattr(pr, "_identificar_tarefa", lambda *a: None)
    dub = Duble({**RESPOSTAS_FELIZES, "rev-parse --abbrev-ref": "codex/ci/make-pr"})
    pr.abrir(raiz, pedido(raiz), rodar=dub, hoje=HOJE)
    recibo = next((raiz / "painel/registros").glob("*.js"))
    assert pr.campos_lidos(recibo.read_text(encoding="utf-8"))["area"] == "ci"
    assert dub.pediu("git push -u origin codex/ci/make-pr")
    assert dub.linhas.count("pytest ci/tests") == 2


@pytest.mark.parametrize("bytes_totais", [1023, 1024])
def test_limite_do_recibo_conta_bytes_e_preserva_campos(tmp_path, bytes_totais):
    raiz = bancada(tmp_path)
    entrada = pedido(raiz)
    args = (entrada, "20260906-077-teste", URL_DO_PR, HOJE, "ci", "a" * 40, "b" * 40, 1)
    texto = pr._texto_do_recibo(*args)
    entrada.detalhe += "x" * (bytes_totais - len(texto.encode("utf-8")))
    if bytes_totais == 1024:
        with pytest.raises(pr.ParouPorSeguranca, match="1 KB"):
            pr._texto_do_recibo(*args)
    else:
        texto = pr._texto_do_recibo(*args)
        assert len(texto.encode("utf-8")) == 1023
        assert pr.campos_lidos(texto)["detalhe"] == entrada.detalhe


@pytest.mark.parametrize("remoto", [
    "https://github.com/abundanciabr/sitesdoreino.git",
    "git@github.com:abundanciabr/sitesdoreino.git",
    "ssh://git@github.com/abundanciabr/sitesdoreino.git",
    "ssh://git@github.com:22/abundanciabr/sitesdoreino.git",
])
def test_orcamento_minimo_nao_cria_efeito_remoto(tmp_path, remoto):
    raiz = bancada(tmp_path)
    dub = Duble({"git remote get-url origin": remoto})
    pr._conferir_orcamento_do_recibo(raiz, pedido(raiz), dub, HOJE, "ci", "b" * 40, 1)
    assert dub.linhas == ["git remote get-url origin"]


def test_origin_invalido_recusa_antes_da_validacao(tmp_path):
    raiz = bancada(tmp_path)
    dub = Duble({**RESPOSTAS_FELIZES, "git remote get-url origin": "arquivo-local"})
    with pytest.raises(pr.ParouPorSeguranca, match="origin"):
        pr.abrir(raiz, pedido(raiz), rodar=dub, hoje=HOJE)
    assert not dub.pediu("git add")
    assert not dub.pediu("pytest")



def test_recibo_valido_de_1023_bytes_e_retomada_reutilizam_prova(tmp_path):
    raiz = bancada(tmp_path)
    entrada = pedido(raiz)
    nome = "20260906-077-" + pr.slug_do_titulo(entrada.titulo)
    texto = pr._texto_do_recibo(entrada, nome, URL_DO_PR, HOJE, "ci", "a" * 40, "b" * 40, 1)
    entrada.detalhe += "x" * (1023 - len(texto.encode("utf-8")))
    dub = Duble(RESPOSTAS_FELIZES)
    pr.abrir(raiz, entrada, rodar=dub, hoje=HOJE)
    recibo = next((raiz / "painel/registros").glob("*.js"))
    assert len(recibo.read_bytes()) == 1023
    retomada = Duble({**RESPOSTAS_FELIZES, "status --porcelain": "", "diff --cached --name-only": "",
                     "gh pr list": json.dumps([{"number": 1210, "url": URL_DO_PR, "state": "OPEN"}])})
    pr.abrir(raiz, pedido(raiz, detalhe="x" * 2000, continuar=True), rodar=retomada, hoje=HOJE)
    assert len(list((raiz / "painel/registros").glob("*.js"))) == 1
    assert len(recibo.read_bytes()) == 1023
    assert not retomada.pediu("reservar.py")
    assert retomada.linhas.count("pytest ci/tests") == 2



def test_scratch_codex_canonico_e_exclusivo(tmp_path, monkeypatch):
    raiz = bancada(tmp_path)
    scratch = tmp_path / "sessoes"
    monkeypatch.setattr(pr, "base_de_scratch_padrao", lambda: scratch)
    monkeypatch.setattr(pr, "_tentativa_da_abertura", lambda *a: ("tentativa", "legada"))
    monkeypatch.setattr(pr, "_identificar_tarefa", lambda *a: None)
    for nome_pasta in ("codex-ci-make-pr", "ci-make-pr"):
        pasta = scratch / nome_pasta
        pasta.mkdir(parents=True)
        for nome in ("mensagem.txt", "corpo.md", "validacao.json"):
            (pasta / nome).write_text((raiz / nome).read_text(encoding="utf-8"), encoding="utf-8")
        entrada = pedido(raiz, mensagem_arquivo=pasta / "mensagem.txt", corpo_arquivo=pasta / "corpo.md",
                         validacao_arquivo=pasta / "validacao.json")
        dub = Duble({**RESPOSTAS_FELIZES, "rev-parse --abbrev-ref": "codex/ci/make-pr"})
        if nome_pasta == "codex-ci-make-pr":
            pr.abrir(raiz, entrada, rodar=dub, hoje=HOJE)
        else:
            with pytest.raises(pr.ParouPorSeguranca, match="fora da bancada"):
                pr.abrir(raiz, entrada, rodar=dub, hoje=HOJE)
            assert not dub.pediu("git add")


@pytest.mark.parametrize("continuar", [False, True])
def test_candidata_existente_e_guardada_antes_de_qualquer_push(tmp_path, continuar):
    raiz = bancada(tmp_path)
    dub = Duble({**RESPOSTAS_FELIZES, "gh pr list": json.dumps([
        {"number": 1210, "url": URL_DO_PR, "state": "OPEN"}])})
    pr.abrir(raiz, pedido(raiz, continuar=continuar), rodar=dub, hoje=HOJE)
    assert dub.posicao("gh pr ready 1210 --undo") < dub.posicao("git push -u")


def test_novo_pr_nasce_rascunho_antes_do_recibo(tmp_path):
    raiz = bancada(tmp_path)
    dub = Duble(RESPOSTAS_FELIZES)
    dub.explode_em = "node painel/gerar_manifesto.js"
    with pytest.raises(pr.ErroDeInstrumentacao):
        pr.abrir(raiz, pedido(raiz), rodar=dub, hoje=HOJE)
    criar = next(c for c in dub.chamadas if c[:3] == ["gh", "pr", "create"])
    assert "--draft" in criar
    assert not dub.pediu("gh pr ready 1210")


@pytest.mark.parametrize("existente", [False, True])
@pytest.mark.parametrize("interrupcao", [False, True])
@pytest.mark.parametrize("ponto", ["recibo", "validacao_final", "push_final"])
def test_falha_ou_interrupcao_preserva_rascunho(tmp_path, existente, interrupcao, ponto):
    raiz = bancada(tmp_path)
    respostas = dict(RESPOSTAS_FELIZES)
    if existente:
        respostas["gh pr list"] = json.dumps([{"number": 1210, "url": URL_DO_PR, "state": "OPEN"}])
    dub = Duble(respostas)
    validacoes = 0
    erro = KeyboardInterrupt if interrupcao else pr.ErroDeInstrumentacao
    def executar(comando, raiz, **opcoes):
        nonlocal validacoes
        if comando == ["pytest", "ci/tests"]:
            validacoes += 1
        if ((ponto == "recibo" and comando[:2] == ["node", "painel/gerar_manifesto.js"])
                or (ponto == "validacao_final" and comando == ["pytest", "ci/tests"] and validacoes == 2)
                or (ponto == "push_final" and comando[:3] == ["git", "push", "origin"])):
            if interrupcao:
                raise KeyboardInterrupt()
            raise pr.ErroDeInstrumentacao("falha medida", "Retome esta candidata.")
        return dub(comando, raiz, **opcoes)
    with pytest.raises(erro):
        pr.abrir(raiz, pedido(raiz, continuar=existente), rodar=executar, hoje=HOJE)
    assert dub.rascunho is True
    assert not any(c[:3] == ["gh", "pr", "ready"] and "--undo" not in c for c in dub.chamadas)


@pytest.mark.parametrize("remoto", [
    {"headRefOid": "b" * 40, "state": "OPEN", "isDraft": False},
    {"headRefOid": "c" * 40, "state": "OPEN", "isDraft": True},
    {"headRefOid": "b" * 40, "state": "MERGED", "isDraft": True},
])
def test_guarda_nao_confirmada_recusa_antes_do_push(tmp_path, monkeypatch, remoto):
    monkeypatch.setattr(pr.time, "sleep", lambda segundos: None)
    raiz = bancada(tmp_path)
    dub = Duble({**RESPOSTAS_FELIZES, "gh pr list": json.dumps([
        {"number": 1210, "url": URL_DO_PR, "state": "OPEN"}])})
    views = 0
    def executar(comando, raiz, **opcoes):
        nonlocal views
        if comando[:3] == ["gh", "pr", "view"]:
            views += 1
            if views > 1:
                return json.dumps(remoto)
        return dub(comando, raiz, **opcoes)
    with pytest.raises(pr.ParouPorSeguranca):
        pr.abrir(raiz, pedido(raiz), rodar=executar, hoje=HOJE)
    assert not dub.pediu("git push")


def test_retoma_rascunho_apos_falha_e_libera_so_depois_da_prova_final(tmp_path):
    raiz = bancada(tmp_path)
    dub = Duble(RESPOSTAS_FELIZES)
    dub.explode_em = "node painel/gerar_manifesto.js"
    with pytest.raises(pr.ErroDeInstrumentacao):
        pr.abrir(raiz, pedido(raiz), rodar=dub, hoje=HOJE)
    dub.respostas["gh pr list"] = json.dumps([{"number": 1210, "url": URL_DO_PR, "state": "OPEN"}])
    dub.respostas["status --porcelain"] = ""
    dub.respostas["diff --cached --name-only"] = ""
    dub.explode_em = None
    dub.chamadas.clear()
    dub.recibo_preparado = False
    pr.abrir(raiz, pedido(raiz, continuar=True), rodar=dub, hoje=HOJE)
    assert not dub.pediu("gh pr create")
    assert not dub.pediu("gh pr ready 1210 --undo")
    validacoes = [i for i, c in enumerate(dub.chamadas) if c == ["pytest", "ci/tests"]]
    assert len(validacoes) == 2
    assert validacoes[-1] < dub.posicao("git push origin") < dub.posicao("gh pr ready 1210")
    assert dub.rascunho is False


@pytest.mark.parametrize("valor", [None, "pr", {}, {"number": True, "url": URL_DO_PR}, {"number": 1210, "url": "wrong"}])
def test_identidade_de_pr_invalida_nao_publica(tmp_path, valor):
    raiz = bancada(tmp_path)
    dub = Duble({**RESPOSTAS_FELIZES, "gh pr list": json.dumps([valor])})
    with pytest.raises(pr.ErroDeInstrumentacao):
        pr.abrir(raiz, pedido(raiz), rodar=dub, hoje=HOJE)
    assert not dub.pediu("git push")


def test_pr_liberado_durante_validacao_volta_a_rascunho_antes_do_push_final(tmp_path):
    raiz = bancada(tmp_path)
    dub = Duble(RESPOSTAS_FELIZES)
    validacoes = 0
    def executar(comando, raiz, **opcoes):
        nonlocal validacoes
        if comando == ["pytest", "ci/tests"]:
            validacoes += 1
            if validacoes == 2:
                dub.rascunho = False
        return dub(comando, raiz, **opcoes)
    pr.abrir(raiz, pedido(raiz), rodar=executar, hoje=HOJE)
    assert dub.posicao("gh pr ready 1210 --undo") < dub.posicao("git push origin")
    assert dub.rascunho is False
