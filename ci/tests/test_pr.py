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
    "write-tree": "a" * 40,
    "rev-parse HEAD^{tree}": "a" * 40,
    "rev-parse HEAD": "b" * 40,
    "gh pr view": json.dumps({"headRefOid": "b" * 40, "state": "OPEN"}),
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
    assert pr._concluir_fila(raiz, lambda c:dub(c), tarefa, 'agent/ci/tarefa', URL_DO_PR) == ['fila/eventos/concluida.json']
    assert not dub.chamadas
    evento['evidencia'] = URL_DO_PR+'0'
    with pytest.raises(pr.ParouPorSeguranca, match='outro fato'):
        pr._concluir_fila(raiz, lambda c:dub(c), tarefa, 'agent/ci/tarefa', URL_DO_PR)

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
    git('add','.gitignore')
    git('commit','-m','base')
    raiz=tmp_path/'bancada'
    git('worktree','add','-b','agent/ci/prova',str(raiz))
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
