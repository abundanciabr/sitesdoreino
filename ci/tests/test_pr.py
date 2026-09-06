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

    def __call__(self, comando: list[str], raiz: Path | None = None) -> str:
        self.chamadas.append(list(comando))
        linha = " ".join(comando)
        if self.explode_em and self.explode_em in linha:
            raise pr.ErroDeInstrumentacao(
                f"o comando falhou: {linha}", "exit 1\n(saída do dublê)"
            )
        for chave, resposta in self.respostas.items():
            if chave in linha:
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
    "rev-parse --abbrev-ref": "agent/ci/make-pr\n",
    "status --porcelain": " M ci/pr.py\n?? ci/tests/test_pr.py\n",
    "diff --cached --name-only": "ci/pr.py\n",
    "gh pr create": f"{URL_DO_PR}\n",
    "gh pr list": "[]\n",
    "reservar.py numero registro": "077\n",
}


def bancada(tmp_path: Path, principal: bool = False) -> Path:
    """Uma raiz de mentira: worktree por padrão, clone principal se pedirem."""
    raiz = tmp_path / "wt-ci-make-pr"
    (raiz / "painel" / "registros").mkdir(parents=True)
    (raiz / "ci").mkdir()
    if principal:
        (raiz / ".git").mkdir()
    else:
        (raiz / ".git").write_text("gitdir: /algum/lugar\n", encoding="utf-8")
    (raiz / "mensagem.txt").write_text(
        f"ci: o comando que abre o PR\n\nMuda o mundo.\n\n{COAUTOR}\n", encoding="utf-8"
    )
    (raiz / "corpo.md").write_text("## O que muda\n\nUm comando só.\n", encoding="utf-8")
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

    assert final.startswith("PR 1210 pronto para a espera")
    assert URL_DO_PR in final
    saida = capsys.readouterr().out
    assert saida.count("PASS") >= 8
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
        "evidencia": URL_DO_PR,
        "verificado_em": "2026-09-06",
        "precisa_do_dono": False,
        "responde_a": None,
        "gravidade": "verde",
        "frente": "fabrica",
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
    ja.write_text(f'// evidencia: "{URL_DO_PR}"\n', encoding="utf-8")
    dub = Duble({
        **RESPOSTAS_FELIZES,
        "status --porcelain": "\n",
        "diff --cached --name-only": "",
        "gh pr list": json.dumps([{"number": 1210, "url": URL_DO_PR}]),
    })

    pr.abrir(raiz, pedido(raiz, continuar=True), rodar=dub, hoje=HOJE)

    assert not dub.pediu("reservar.py numero registro")
    assert len(list((raiz / "painel" / "registros").glob("*.js"))) == 1


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
