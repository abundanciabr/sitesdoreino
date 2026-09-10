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
    assert "9 passed" not in evidencia
    assert "exit 0" in evidencia


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
                    "isDraft": self.views == 1,
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
    dub = Duble({**RESPOSTAS_FELIZES, 'gh pr view': json.dumps({'headRefOid': 'c'*40, 'state': 'OPEN'})})
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
    pr.abrir(raiz, pedido(raiz), rodar=Duble(RESPOSTAS_FELIZES), hoje=HOJE)
    assert [(f,r) for f,r,d in fases] == [('fechamento','iniciado'), ('validacao','concluido'), ('validacao','concluido'), ('fechamento','concluido')]
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


def test_fila_retomada_preserva_evento_logico(tmp_path, monkeypatch):
    import fila
    raiz = bancada(tmp_path)
    (raiz/'fila/eventos').mkdir(parents=True)
    tarefa = 'TAR-001'
    evento = {'tarefa':tarefa, 'evento':'concluida','evidencia':URL_DO_PR}
    caminho = raiz/'fila/eventos/concluida.json'
    caminho.write_text(json.dumps(evento),encoding='utf-8')
    monkeypatch.setattr(fila, 'carregar_tarefas', lambda *a: {tarefa:{}})
    monkeypatch.setattr(fila, 'carregar_eventos', lambda *a: [evento])
    dub = Duble()
    assert pr._submeter_fila(raiz, lambda c:dub(c), tarefa, 'agent/ci/tarefa', URL_DO_PR, 'a'*40, 'b'*40) == ['fila/eventos/concluida.json']
    assert not dub.chamadas
    evento['evidencia'] = URL_DO_PR+'0'
    with pytest.raises(pr.ParouPorSeguranca, match='outro fato'):
        pr._submeter_fila(raiz, lambda c:dub(c), tarefa, 'agent/ci/tarefa', URL_DO_PR, 'a'*40, 'b'*40)

@pytest.mark.parametrize('ignorado', [False, True])
@pytest.mark.parametrize('alvo', ['relativo','python_absoluto','pytest_absoluto'])
def test_validacao_real_nao_usa_modulo_fora_da_revisao(tmp_path, ignorado, alvo):
    import subprocess
    origem = tmp_path/'origem'
    subprocess.run(['git','init',str(origem)],check=True,capture_output=True)
    def git(*args, cwd=origem):
        return subprocess.run(['git',*args],cwd=cwd,check=True,capture_output=True,text=True).stdout.strip()
    git('config','user.name','Teste')
    git('config','user.email','teste@example.com')
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
    (tmp_path/'mensagem.txt').write_text('ci: prova\n\n'+COAUTOR+'\n',encoding='utf-8')
    (tmp_path/'corpo.md').write_text('Teste isolado.',encoding='utf-8')
    comando = [sys.executable,'check.py'] if alvo == 'relativo' else [sys.executable,str(raiz/'check.py')]
    if alvo == 'pytest_absoluto':
        comando = [sys.executable,'-m','pytest',str(raiz/'check.py'),'-q']
    (tmp_path/'validacao.json').write_text(json.dumps({'comandos':[comando]}),encoding='utf-8')
    entrada=pr.Pedido(titulo='ci: prova',mensagem_arquivo=tmp_path/'mensagem.txt',corpo_arquivo=tmp_path/'corpo.md',validacao_arquivo=tmp_path/'validacao.json',arquivos=['check.py'],detalhe=DETALHE)
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
def test_timeout_encerra_filhos_e_netos_reais(tmp_path, pai_encerra, nova_sessao):
    import os
    import signal
    import subprocess
    import time
    script = tmp_path/'processos.py'
    script.write_text('''import os, pathlib, subprocess, sys, time
profundidade = int(sys.argv[1])
pathlib.Path(f"pid-{profundidade}").write_text(str(os.getpid()))
print(f"iniciado {profundidade}", flush=True)
print("saída íntegra " + "x"*12000, flush=True)
if profundidade:
    subprocess.Popen([sys.executable, __file__, str(profundidade-1), sys.argv[2], sys.argv[3]], start_new_session=sys.argv[3] == "nova")
if profundidade == 2 and sys.argv[2] == "sair":
    sys.exit(0)
print("token=SEGREDO_CONTROLADO", file=sys.stderr, flush=True)
time.sleep(60)
''', encoding='utf-8')
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
            pr.rodar([sys.executable, 'processos.py', '2', 'sair' if pai_encerra else 'ficar', 'nova' if nova_sessao else 'mesma'], tmp_path, log=log, prazo_segundos=2)
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



def test_fechamento_submete_tar_recuperada_e_recibo_a_identifica(tmp_path, monkeypatch):
    import fila
    raiz = bancada(tmp_path)
    monkeypatch.setattr(pr, "_tentativa_da_abertura", lambda *args: ("tentativa-1", "TAR-001"))
    monkeypatch.setattr(fila, "carregar_tarefas", lambda *args: {"TAR-001": {}})
    monkeypatch.setattr(fila, "carregar_eventos", lambda *args: [])
    dub = Duble(RESPOSTAS_FELIZES)
    pr.abrir(raiz, pedido(raiz), rodar=dub, hoje=HOJE)
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


@pytest.mark.parametrize("fonte", ["ramo", "titulo", "corpo", "posse"])
def test_pr_documental_sem_vinculo_recusa_tar_citada_sem_efeitos(tmp_path, monkeypatch, fonte):
    import fila
    raiz = bancada(tmp_path)
    ramo = "agent/ci/TAR-321" if fonte == "ramo" else "agent/ci/make-pr"
    titulo = "docs: plano da TAR-321" if fonte == "titulo" else "docs: plano de obra futura"
    if fonte == "corpo":
        (raiz / "corpo.md").write_text("Este plano descreve a obra futura TAR-321.", encoding="utf-8")
    monkeypatch.setattr(fila, "carregar_tarefas", lambda *args: {"TAR-321": {}})
    eventos = [{"tarefa": "TAR-321", "evento": "reivindicada", "quem": ramo,
                "quando": "2026-09-01T00:00:00+00:00"}] if fonte == "posse" else []
    monkeypatch.setattr(fila, "carregar_eventos", lambda *args: eventos)
    fases = []
    monkeypatch.setattr(pr.telemetria, "registrar_fase", lambda *args, **dados: fases.append(dados))
    dub = Duble({**RESPOSTAS_FELIZES, "rev-parse --abbrev-ref": ramo,
                 "git show " + "b" * 40 + ":ci/pr.py": "PROTOCOLO_SUBMISSAO = 1\n"})
    with pytest.raises(pr.ParouPorSeguranca, match="tarefa") as erro:
        pr.abrir(raiz, pedido(raiz, titulo=titulo), rodar=dub, hoje=HOJE)
    assert "--tarefa" in erro.value.o_que_fazer
    assert not fases
    assert not list((raiz / "painel/registros").glob("*.js"))
    assert all(c[:2] in (["git", "rev-parse"], ["git", "status"], ["git", "show"])
               for c in dub.chamadas)


def test_pr_documental_com_vinculo_submete_so_tar_explicita(tmp_path, monkeypatch):
    import fila
    raiz = bancada(tmp_path)
    (raiz / "corpo.md").write_text("Este documento planeja a obra futura TAR-321.", encoding="utf-8")
    monkeypatch.setattr(fila, "carregar_tarefas", lambda *args: {"TAR-320": {}, "TAR-321": {}})
    monkeypatch.setattr(fila, "carregar_eventos", lambda *args: [])
    dub = Duble({**RESPOSTAS_FELIZES, "rev-parse --abbrev-ref": "agent/ci/TAR-321"})
    pr.abrir(raiz, pedido(raiz, tarefa="TAR-320", titulo="docs: plano da TAR-321"), rodar=dub, hoje=HOJE)
    assert dub.pediu("ci/fila.py submeter TAR-320")
    assert not dub.pediu("ci/fila.py submeter TAR-321")
    recibo = next((raiz / "painel/registros").glob("*.js"))
    assert pr.campos_lidos(recibo.read_text(encoding="utf-8"))["tarefa"] == "TAR-320"


@pytest.mark.parametrize("fase,resultado", [("fechamento", "iniciado"), ("fechamento", "falhou"),
                                           ("fechamento", "concluido"), ("abertura", "iniciado"),
                                           ("abertura", "falhou")])
def test_fase_sem_abertura_concluida_nao_prova_vinculo(tmp_path, monkeypatch, fase, resultado):
    import fila
    raiz = bancada(tmp_path)
    evento = dict(tarefa="TAR-321", tentativa="tentativa-anterior", branch="agent/ci/make-pr",
                  commit="b" * 40, pr=None, fase=fase, resultado=resultado, contexto_bytes=None)
    evento.update(id=pr.telemetria.identidade_fase(evento), quando="2026-09-09T00:00:00+00:00")
    monkeypatch.setattr(pr.telemetria, "ler_tudo", lambda *args: [evento])
    monkeypatch.setattr(fila, "carregar_tarefas", lambda *args: {"TAR-321": {}})
    monkeypatch.setattr(fila, "carregar_eventos", lambda *args: [])
    dub = Duble(RESPOSTAS_FELIZES)
    with pytest.raises(pr.ParouPorSeguranca, match="tarefa"):
        pr.abrir(raiz, pedido(raiz, continuar=True), rodar=dub, hoje=HOJE)
    assert not dub.pediu("git add")


def test_abertura_atual_define_tar_sem_herdar_fechamento_anterior(tmp_path, monkeypatch):
    import fila
    raiz = bancada(tmp_path)
    fases = []
    for fase, tarefa, quando in [("abertura", "TAR-001", "2026-09-08"),
                                ("abertura", "TAR-320", "2026-09-09"),
                                ("fechamento", "TAR-321", "2026-09-10")]:
        evento = dict(tarefa=tarefa, tentativa="tentativa-" + tarefa, branch="agent/ci/make-pr",
                      commit="b" * 40, pr=None, fase=fase, resultado="concluido", contexto_bytes=None)
        evento.update(id=pr.telemetria.identidade_fase(evento), quando=quando + "T00:00:00+00:00")
        fases.append(evento)
    monkeypatch.setattr(pr.telemetria, "ler_tudo", lambda *args: fases)
    monkeypatch.setattr(fila, "carregar_tarefas", lambda *args: {"TAR-001": {}, "TAR-320": {}, "TAR-321": {}})
    monkeypatch.setattr(fila, "carregar_eventos", lambda *args: [])
    dub = Duble(RESPOSTAS_FELIZES)
    pr.abrir(raiz, pedido(raiz), rodar=dub, hoje=HOJE)
    assert pr._tentativa_da_abertura(raiz, "agent/ci/make-pr") == ("tentativa-TAR-320", "TAR-320")
    assert dub.pediu("ci/fila.py submeter TAR-320")
    assert not dub.pediu("ci/fila.py submeter TAR-321")


def test_tar_explicita_divergente_da_abertura_recusa_sem_publicar(tmp_path, monkeypatch):
    import fila
    raiz = bancada(tmp_path)
    monkeypatch.setattr(pr, "_tentativa_da_abertura", lambda *args: ("tentativa-atual", "TAR-320"))
    monkeypatch.setattr(fila, "carregar_tarefas", lambda *args: {"TAR-320": {}, "TAR-321": {}})
    monkeypatch.setattr(fila, "carregar_eventos", lambda *args: [])
    dub = Duble(RESPOSTAS_FELIZES)
    with pytest.raises(pr.ParouPorSeguranca, match="ambígua"):
        pr.abrir(raiz, pedido(raiz, tarefa="TAR-321"), rodar=dub, hoje=HOJE)
    assert not dub.pediu("git add")


def test_sessao_atual_nao_herda_excecao_da_abertura_legada(tmp_path, monkeypatch):
    raiz = bancada(tmp_path)
    fases = []
    for commit, quando in [("b" * 40, "2026-09-08"), ("c" * 40, "2026-09-09")]:
        evento = dict(tarefa="agent/ci/make-pr", tentativa="sessao-" + commit, branch="agent/ci/make-pr",
                      commit=commit, pr=None, fase="abertura", resultado="concluido", contexto_bytes=None)
        evento.update(id=pr.telemetria.identidade_fase(evento), quando=quando + "T00:00:00+00:00")
        fases.append(evento)
    monkeypatch.setattr(pr.telemetria, "ler_tudo", lambda *args: fases)
    dub = Duble({**RESPOSTAS_FELIZES, "git show " + "c" * 40 + ":ci/pr.py": "PROTOCOLO_SUBMISSAO = 1\n"})
    with pytest.raises(pr.ParouPorSeguranca, match="tarefa"):
        pr.abrir(raiz, pedido(raiz), rodar=dub, hoje=HOJE)
    assert not dub.pediu("git add")



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
            return json.dumps({"headRefOid": ("c" if len(consultas) == 1 else "b") * 40,
                               "state": "OPEN", "isDraft": False})
        return dub(comando, raiz, **opcoes)
    assert pr.abrir(raiz, pedido(raiz), rodar=executar, hoje=HOJE).startswith("PR 1210")
    assert len(consultas) == 2
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
            return json.dumps(remoto)
        return dub(comando, raiz, **opcoes)
    with pytest.raises(pr.ParouPorSeguranca, match="após 3 consultas"):
        pr.abrir(raiz, pedido(raiz), rodar=executar, hoje=HOJE)
    assert len(consultas) == 3
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
            return json.dumps({"headRefOid": "b" * 40, "state": "OPEN", "isDraft": len(consultas) < 3})
        return dub(comando, raiz, **opcoes)
    assert pr.abrir(raiz, pedido(raiz), rodar=executar, hoje=HOJE).startswith("PR 1210")
    assert len(consultas) == 3
    assert sum("gh pr ready" in linha for linha in dub.linhas) == 1
