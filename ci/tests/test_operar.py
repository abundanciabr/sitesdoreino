"""infra/operar.py: as 22 operações sem GitHub Actions, com fakes (sem rede, VPS nem Docker)."""

from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path

import pytest
from conftest import BASH

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("operar_sob_teste", ROOT / "infra" / "operar.py")
operar = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = operar
spec.loader.exec_module(operar)

OPERACOES = {
    "appmax-drill-rollback", "appmax-estorno-sandbox", "appmax-sandbox-tela",
    "backfill-mensagens-do-forum", "backfill-pontos-do-forum", "conferir-as-fichas",
    "esvaziar-caixa", "ligar-os-degraus", "limpar-avisos-orfaos", "operacoes-vps",
    "provisionar", "semear-areas-do-forum", "semear-boas-vindas", "semear-caixa",
    "semear-convite-para-a-comunidade", "semear-demo-caixa", "semear-duvidas-do-forum",
    "semear-economia", "semear-experimento", "semear-quiz", "sonda-pix-publica",
    "vigia-do-cadeado",
}


class Processos:
    """Fake de `ctx.processo`: guarda cada chamada e responde (código, saída)."""

    def __init__(self, resposta=None):
        self.chamadas = []
        self.resposta = resposta or (lambda comando, env: (0, "PRONTO: ok\n"))

    def __call__(self, comando, *, env, timeout, juntar=True, cwd=None):
        self.chamadas.append(
            {"comando": list(comando), "env": dict(env), "timeout": timeout, "juntar": juntar}
        )
        return self.resposta(list(comando), env)

    def rodadas(self):
        """As chamadas que não são `bash -n`."""
        return [c for c in self.chamadas if c["comando"][:2] != ["bash", "-n"]]


@pytest.fixture
def fazer_ctx(tmp_path):
    def fazer(processo=None, ambiente=None, raiz=ROOT, **resto):
        base = {
            "PATH": "/usr/bin", "PLATAFORMA_DIR": "/opt/plataforma",
            "OPERAR_ESTADO": str(tmp_path / "estado"),
        }
        base.update(ambiente or {})
        return operar.Contexto(
            raiz=raiz, ambiente=base, processo=processo or Processos(),
            dormir=lambda segundos: None, espera=0, **resto,
        )

    return fazer


# --------------------------------------------------------------------------- a lista


def test_a_lista_tem_as_22_operacoes_e_cada_uma_se_explica(capsys):
    assert set(operar.OPERACOES) == OPERACOES
    assert operar.main(["listar"]) == 0
    saida = capsys.readouterr().out
    for nome in OPERACOES:
        assert nome in saida
    assert "agenda: 0 11 * * *" in saida


def test_sem_argumento_e_operacao_desconhecida_sao_pedido_invalido(capsys):
    assert operar.main([]) == 2
    assert operar.main(["rm-rf"]) == 2
    assert "desconhecida" in capsys.readouterr().err


# --------------------------------------------------------------------------- scripts da VPS

CONTROLE_ZERO = {
    "CONFIRMAR", "LIGAR", "HOST_CAIXA", "HOST_QUIZ", "QUANTAS", "ACAO_DEMO",
    "ACAO_EXPERIMENTO", "CONSERTAR", "AVISAR",
}


@pytest.mark.parametrize(
    ("argv", "script", "esperado"),
    [
        (["semear-caixa"], "semear-caixa.sh", {"HOST_CAIXA": "meshcraft.top"}),
        (["semear-caixa", "--host", "basileiatoutheou.org"], "semear-caixa.sh",
         {"HOST_CAIXA": "basileiatoutheou.org"}),
        (["semear-quiz"], "semear-quiz.sh", {"HOST_QUIZ": "meshcraft.top"}),
        (["semear-demo-caixa", "--acao", "remover"], "semear-demo-caixa.sh",
         {"ACAO_DEMO": "remover", "HOST_CAIXA": "meshcraft.top"}),
        (["semear-boas-vindas"], "semear-boas-vindas.sh", {"LIGAR": "0"}),
        (["semear-boas-vindas", "--ligar"], "semear-boas-vindas.sh", {"LIGAR": "1"}),
        (["backfill-pontos-do-forum"], "backfill-pontos-do-forum.sh", {"CONFIRMAR": "nao"}),
        (["backfill-pontos-do-forum", "--confirmar"], "backfill-pontos-do-forum.sh", {"CONFIRMAR": "sim"}),
        (["backfill-mensagens-do-forum"], "backfill-mensagens-do-forum.sh", {"CONFIRMAR": "nao"}),
        (["backfill-mensagens-do-forum", "--confirmar"], "backfill-mensagens-do-forum.sh",
         {"CONFIRMAR": "sim"}),
        (["conferir-as-fichas"], "conferir-as-fichas.sh", {"CONSERTAR": "nao", "AVISAR": "nao"}),
        (["conferir-as-fichas", "--consertar", "sim", "--avisar", "sim"], "conferir-as-fichas.sh",
         {"CONSERTAR": "sim", "AVISAR": "sim"}),
        (["esvaziar-caixa", "--quantas", "2"], "esvaziar-caixa.sh",
         {"QUANTAS": "2", "HOST_CAIXA": "meshcraft.top"}),
        (["semear-experimento", "--acao", "medir"], "semear-experimento.sh", {"ACAO_EXPERIMENTO": "medir"}),
        (["ligar-os-degraus"], "ligar-os-degraus.sh", {}),
        (["limpar-avisos-orfaos"], "limpar-avisos-orfaos.sh", {}),
        (["semear-areas-do-forum"], "semear-areas-do-forum.sh", {}),
        (["semear-convite-para-a-comunidade"], "semear-convite-para-a-comunidade.sh", {}),
        (["semear-duvidas-do-forum"], "semear-duvidas-do-forum.sh", {}),
        (["semear-economia"], "semear-economia.sh", {}),
    ],
)
def test_script_roda_o_arquivo_certo_com_o_ambiente_certo_sem_shell(fazer_ctx, argv, script, esperado):
    processos = Processos()
    assert operar.main(argv, fazer_ctx(processos)) == 0
    sintaxe, execucao = processos.chamadas
    arquivo = str(ROOT / "infra" / script)
    assert sintaxe["comando"] == ["bash", "-n", arquivo]
    assert execucao["comando"] == ["bash", arquivo]  # lista, nunca texto de shell
    assert execucao["env"]["PLATAFORMA_DIR"] == "/opt/plataforma"
    for chave in CONTROLE_ZERO:
        assert execucao["env"].get(chave) == esperado.get(chave)


def test_o_prazo_de_cada_script_e_o_do_workflow(fazer_ctx):
    processos = Processos()
    operar.main(["semear-experimento", "--acao", "medir"], fazer_ctx(processos))
    operar.main(["semear-caixa"], fazer_ctx(processos))
    assert [c["timeout"] for c in processos.rodadas()] == [5 * 60, 10 * 60]


def test_variavel_de_controle_herdada_nunca_chega_ao_script(fazer_ctx):
    herdado = {"CONFIRMAR": "sim", "HOST_CAIXA": "outro.top", "QUANTAS": "99", "AVISAR": "sim"}
    processos = Processos()
    operar.main(["ligar-os-degraus"], fazer_ctx(processos, ambiente=herdado))
    assert not CONTROLE_ZERO & set(processos.rodadas()[0]["env"])
    processos = Processos()
    operar.main(["backfill-pontos-do-forum"], fazer_ctx(processos, ambiente=herdado))
    assert processos.rodadas()[0]["env"]["CONFIRMAR"] == "nao"


def test_as_chaves_do_gateway_entram_no_script_sem_aparecer_na_tela(fazer_ctx, tmp_path, capsys):
    plataforma = tmp_path / "plataforma"
    (plataforma / "env").mkdir(parents=True)
    (plataforma / "env" / "admin.env").write_text(
        "OUTRA=1\nALUNOS_API_TOKEN=segredo-alunos==\nTOKEN_CATALOGO=\nALUNOS_API_TOKEN=segunda-linha\n",
        encoding="utf-8",
    )
    processos = Processos()
    ctx = fazer_ctx(processos, ambiente={"PLATAFORMA_DIR": str(plataforma)})
    assert operar.main(["conferir-as-fichas"], ctx) == 0
    env = processos.rodadas()[0]["env"]
    assert env["ALUNOS_API_TOKEN"] == "segredo-alunos=="  # a primeira linha, como o `grep -m1`
    assert "TOKEN_CATALOGO" not in env  # vazia não vira chave
    assert "segredo-alunos" not in capsys.readouterr().out


def test_chave_do_gateway_ja_no_ambiente_nao_e_trocada_e_env_ausente_nao_derruba(fazer_ctx, tmp_path):
    plataforma = tmp_path / "plataforma"
    (plataforma / "env").mkdir(parents=True)
    (plataforma / "env" / "admin.env").write_text("ALUNOS_API_TOKEN=do-arquivo\n", encoding="utf-8")
    ctx = fazer_ctx(ambiente={"PLATAFORMA_DIR": str(plataforma), "ALUNOS_API_TOKEN": "de-fora"})
    assert operar.chaves_do_gateway(ctx) == {}
    assert operar.chaves_do_gateway(fazer_ctx(ambiente={"PLATAFORMA_DIR": str(tmp_path / "nao-existe")})) == {}


@pytest.mark.parametrize(
    "argv",
    [
        ["semear-caixa", "--host", "meshcraft.top; touch /tmp/x"],
        ["semear-caixa", "--host", "$(id)"],
        ["semear-caixa", "--host", "a\nb"],
        ["semear-caixa", "--host", "-rf"],
        ["semear-quiz", "--host", "`id`.top"],
        ["semear-demo-caixa", "--acao", "criar; id"],
        ["semear-experimento", "--acao", "medir && id"],
        ["esvaziar-caixa", "--quantas", "1; id"],
        ["esvaziar-caixa", "--quantas", ""],
        ["esvaziar-caixa"],
        ["conferir-as-fichas", "--consertar", "talvez"],
        ["provisionar", "--alvo", "../ligar-a-appmax"],
        ["provisionar", "--alvo", "a;b"],
        ["provisionar", "--alvo", "ENCOMENDAS"],
        ["provisionar"],
        ["operacoes-vps", "--operacao", "estado-servico; id", "--servico", "x"],
        ["operacoes-vps", "--operacao", "estado-servico", "--servico", "catalogo; id"],
        ["operacoes-vps", "--operacao", "appmax-pix-aviso", "--referencia", "123"],
        ["appmax-sandbox-tela", "--cartao", "4000000000000010"],
        ["appmax-sandbox-tela", "--perfil", "tablet"],
        ["semear-areas-do-forum", "--host", "x"],
    ],
)
def test_parametro_fora_do_combinado_e_recusado_antes_de_tocar_em_qualquer_coisa(fazer_ctx, argv):
    processos = Processos()
    assert operar.main(argv, fazer_ctx(processos)) == 2
    assert processos.chamadas == []


def test_script_que_sai_zero_mas_diz_parou_por_seguranca_conta_como_falha(fazer_ctx, capsys):
    processos = Processos(lambda cmd, env: (0, "== 1/3 ==\n\nPAROU POR SEGURANÇA: o serviço não está de pé.\n"))
    assert operar.main(["semear-experimento", "--acao", "iniciar-aa"], fazer_ctx(processos)) == 1
    assert "conta como falha" in capsys.readouterr().out


def test_codigo_de_saida_do_script_e_o_veredito(fazer_ctx):
    def responde(codigo, saida):
        return Processos(lambda cmd, env: (0, "") if cmd[:2] == ["bash", "-n"] else (codigo, saida))

    assert operar.main(["ligar-os-degraus"], fazer_ctx(responde(1, "PAROU POR SEGURANÇA: x"))) == 1
    assert operar.main(["ligar-os-degraus"], fazer_ctx(responde(124, ""))) == 124
    assert operar.main(["ligar-os-degraus"], fazer_ctx(responde(0, "PRONTO"))) == 0


def test_script_ausente_ou_com_sintaxe_quebrada_nao_roda(fazer_ctx, tmp_path, capsys):
    vazia = tmp_path / "copia"
    (vazia / "infra").mkdir(parents=True)
    processos = Processos()
    assert operar.main(["ligar-os-degraus"], fazer_ctx(processos, raiz=vazia)) == 1
    assert processos.chamadas == []
    assert "não existe nesta cópia" in capsys.readouterr().out

    (vazia / "infra" / "ligar-os-degraus.sh").write_text("echo 'aberto\n", encoding="utf-8")
    processos = Processos(lambda cmd, env: (2, "") if cmd[:2] == ["bash", "-n"] else (0, "PRONTO"))
    assert operar.main(["ligar-os-degraus"], fazer_ctx(processos, raiz=vazia)) == 1
    assert len(processos.chamadas) == 1  # só o `bash -n`; o script não rodou


# --------------------------------------------------------------------------- provisionar


def _com_uso(linha_de_uso: str, corpo: str) -> str:
    """Um roteiro como os de verdade: o topo diz, num comentário, como se chama."""
    return f"#!/usr/bin/env bash\n# COMO EXECUTAR NA VPS:\n#   {linha_de_uso}\n{corpo}\n"


@pytest.fixture
def copia_com_provisionadores(tmp_path):
    raiz = tmp_path / "copia"
    infra = raiz / "infra"
    infra.mkdir(parents=True)
    (infra / "provisionar-livre.sh").write_text("#!/usr/bin/env bash\necho PRONTO\n", encoding="utf-8")
    (infra / "provisionar-pede-valor.sh").write_text('LOGIN="${1:-}"\n', encoding="utf-8")
    (infra / "provisionar-pede-todos.sh").write_text('echo "$@"\n', encoding="utf-8")
    (infra / "provisionar-conta.sh").write_text('[ "$#" -eq 0 ]\n', encoding="utf-8")
    (infra / "provisionar-cursos.sh").write_text(
        _com_uso("curl -fsSL https://exemplo/c.sh -o /tmp/c.sh && bash /tmp/c.sh meshcraft.top", 'HOST="${1:-}"'),
        encoding="utf-8")
    (infra / "provisionar-email.sh").write_text(
        _com_uso("bash /tmp/p.sh SEU_LOGIN_SMTP", 'LOGIN="${1:-}"'), encoding="utf-8")
    (infra / "provisionar-sugestoes.sh").write_text(
        _com_uso('bash /tmp/p.sh "ID_DO_GOOGLE" "email@staff"', 'ID="${1:-}"; STAFF="${2:-}"'), encoding="utf-8")
    (infra / "provisionar-equipe-da-gamificacao.sh").write_text(
        _com_uso("bash /tmp/e.sh seu-email@exemplo.com", 'echo "$@"'), encoding="utf-8")
    return raiz


@pytest.fixture
def plataforma_da_aplicacao(tmp_path):
    raiz = tmp_path / "plataforma"
    (raiz / "env").mkdir(parents=True)
    (raiz / "publicacoes").mkdir()
    (raiz / "env" / "admin.env").write_text("TOKEN=anterior\n", encoding="utf-8")
    (raiz / "publicacoes" / "aplicacao.json").write_text("{}", encoding="utf-8")
    return raiz


def test_provisionar_roda_o_que_nao_pede_nada(fazer_ctx, copia_com_provisionadores, plataforma_da_aplicacao):
    processos = Processos()
    ctx = fazer_ctx(processos, raiz=copia_com_provisionadores,
                    ambiente={"PLATAFORMA_DIR": str(plataforma_da_aplicacao)})
    assert operar.main(["provisionar", "--alvo", "livre"], ctx) == 0
    assert processos.rodadas()[0]["comando"] == ["bash", str(copia_com_provisionadores / "infra" / "provisionar-livre.sh")]


def test_provisionar_funciona_no_retorno_legado(fazer_ctx, copia_com_provisionadores, plataforma_da_aplicacao):
    (plataforma_da_aplicacao / "publicacoes" / "aplicacao.json").unlink()
    processos = Processos()
    ctx = fazer_ctx(processos, raiz=copia_com_provisionadores,
                    ambiente={"PLATAFORMA_DIR": str(plataforma_da_aplicacao)})
    assert operar.main(["provisionar", "--alvo", "livre"], ctx) == 0
    assert processos.rodadas()[0]["comando"][0] == "bash"


@pytest.mark.parametrize("alvo", ["email", "sugestoes", "equipe-da-gamificacao"])
def test_provisionar_recusa_valor_realmente_ausente(fazer_ctx, copia_com_provisionadores, alvo, capsys):
    processos = Processos()
    assert operar.main(["provisionar", "--alvo", alvo], fazer_ctx(processos, raiz=copia_com_provisionadores)) == 1
    assert processos.chamadas == []
    assert "argumento(s) que ainda não foram informados" in capsys.readouterr().out


def test_provisionar_alvo_inexistente_lista_os_nomes(fazer_ctx, copia_com_provisionadores, capsys):
    assert operar.main(["provisionar", "--alvo", "nao-existe"], fazer_ctx(raiz=copia_com_provisionadores)) == 1
    saida = capsys.readouterr().out
    assert "livre" in saida and "pede-valor" in saida


def test_provisionar_host_conhecido_e_argumentos_em_lista(fazer_ctx, copia_com_provisionadores, plataforma_da_aplicacao):
    processos = Processos()
    ctx = fazer_ctx(processos, raiz=copia_com_provisionadores,
                    ambiente={"PLATAFORMA_DIR": str(plataforma_da_aplicacao)})
    assert operar.main(["provisionar", "--alvo", "cursos"], ctx) == 0
    assert processos.rodadas()[0]["comando"] == ["bash", str(copia_com_provisionadores / "infra" / "provisionar-cursos.sh"), "meshcraft.top"]
    processos = Processos()
    ctx.processo = processos
    assert operar.main(["provisionar", "--alvo", "pede-todos", "--argumento", "um", "--argumento", "dois"], ctx) == 0
    assert processos.rodadas()[0]["comando"][-2:] == ["um", "dois"]


def _roteiro_novo(copia, nome, linha_de_uso, corpo='echo "$@"'):
    (copia / "infra" / f"provisionar-{nome}.sh").write_text(_com_uso(linha_de_uso, corpo), encoding="utf-8")


def test_roteiro_novo_que_pede_endereco_funciona_sem_lista_nenhuma(
    fazer_ctx, copia_com_provisionadores, plataforma_da_aplicacao,
):
    _roteiro_novo(copia_com_provisionadores, "escola-nova",
                  "curl -fsSL https://exemplo/n.sh -o /tmp/n.sh && bash /tmp/n.sh outra-escola.exemplo.top")
    script = copia_com_provisionadores / "infra" / "provisionar-escola-nova.sh"
    ctx = fazer_ctx(raiz=copia_com_provisionadores, ambiente={"PLATAFORMA_DIR": str(plataforma_da_aplicacao)})

    ctx.processo = processos = Processos()  # sem --argumento: vai o host da própria linha de uso
    assert operar.main(["provisionar", "--alvo", "escola-nova"], ctx) == 0
    assert processos.rodadas()[0]["comando"] == ["bash", str(script), "outra-escola.exemplo.top"]

    ctx.processo = processos = Processos()  # com --argumento: vai o pedido, se for um host
    assert operar.main(["provisionar", "--alvo", "escola-nova", "--argumento", "meshcraft.top"], ctx) == 0
    assert processos.rodadas()[0]["comando"][-1] == "meshcraft.top"

    ctx.processo = processos = Processos()  # e só um host: nada de shell no meio
    assert operar.main(["provisionar", "--alvo", "escola-nova", "--argumento", "a.top; id"], ctx) == 1
    assert operar.main(["provisionar", "--alvo", "escola-nova", "--argumento", "a.top", "--argumento", "b.top"], ctx) == 1
    assert processos.chamadas == []


def test_roteiro_novo_que_pede_valor_obrigatorio_recusa_quando_falta(
    fazer_ctx, copia_com_provisionadores, plataforma_da_aplicacao, capsys,
):
    _roteiro_novo(copia_com_provisionadores, "pede-dois", 'bash /tmp/n.sh "LOGIN" outro_valor')
    ctx = fazer_ctx(raiz=copia_com_provisionadores, ambiente={"PLATAFORMA_DIR": str(plataforma_da_aplicacao)})

    ctx.processo = processos = Processos()
    for dados in ([], ["--argumento", "so-um"]):
        assert operar.main(["provisionar", "--alvo", "pede-dois", *dados], ctx) == 1
        assert "precisa de 2 argumento(s) que ainda não foram informados" in capsys.readouterr().out
    assert processos.chamadas == []

    assert operar.main(["provisionar", "--alvo", "pede-dois", "--argumento", "um", "--argumento", "dois"], ctx) == 0
    assert processos.rodadas()[0]["comando"][-2:] == ["um", "dois"]


def test_roteiro_novo_com_valor_opcional_roda_com_ou_sem_ele(
    fazer_ctx, copia_com_provisionadores, plataforma_da_aplicacao,
):
    _roteiro_novo(copia_com_provisionadores, "talvez", "bash /tmp/n.sh [quem@exemplo.com]")
    ctx = fazer_ctx(raiz=copia_com_provisionadores, ambiente={"PLATAFORMA_DIR": str(plataforma_da_aplicacao)})

    ctx.processo = processos = Processos()
    assert operar.main(["provisionar", "--alvo", "talvez"], ctx) == 0
    assert operar.main(["provisionar", "--alvo", "talvez", "--argumento", "quem@exemplo.com"], ctx) == 0
    assert [r["comando"][2:] for r in processos.rodadas()] == [[], ["quem@exemplo.com"]]


@pytest.mark.parametrize("texto, esperado", [
    ("#!/usr/bin/env bash\necho oi\n", operar.UsoDoRoteiro()),
    ("# derrubaria a sessão. Com `bash /tmp/p.sh` o exit morre no filho\n# e (`bash /tmp/p.sh\n# meshcraft.top`) é só texto.\n",
     operar.UsoDoRoteiro()),
    ("[ -f \"$X\" ] || X=1\n#   bash /tmp/p.sh meshcraft.top\n", operar.UsoDoRoteiro("meshcraft.top")),
    ("#   curl -fsSL https://e/p.sh -o /tmp/p.sh && bash /tmp/p.sh Login 'dois valores'\n",
     operar.UsoDoRoteiro(None, 2)),
    ("#   bash /tmp/p.sh [meshcraft.top] LOGIN # comentário solto\n#   bash /tmp/p.sh outro valor\n",
     operar.UsoDoRoteiro("meshcraft.top", 1)),
])
def test_uso_do_roteiro_e_lido_da_primeira_linha_de_uso(tmp_path, texto, esperado):
    arquivo = tmp_path / "provisionar-x.sh"
    arquivo.write_text(texto, encoding="utf-8")
    assert operar.uso_do_roteiro(arquivo) == esperado
    assert operar.uso_do_roteiro(tmp_path / "nao-existe.sh") == operar.UsoDoRoteiro()


def test_provisionar_rejeita_host_invalido_antes_do_backup(fazer_ctx, copia_com_provisionadores, plataforma_da_aplicacao):
    processos = Processos()
    ctx = fazer_ctx(processos, raiz=copia_com_provisionadores,
                    ambiente={"PLATAFORMA_DIR": str(plataforma_da_aplicacao)})
    assert operar.main(["provisionar", "--alvo", "cursos", "--argumento", "meshcraft.top; id"], ctx) == 1
    assert processos.chamadas == []
    assert list((plataforma_da_aplicacao / "publicacoes").iterdir()) == [plataforma_da_aplicacao / "publicacoes" / "aplicacao.json"]


def test_provisionar_valor_explicito_chega_sem_eco_no_operador(
    fazer_ctx, copia_com_provisionadores, plataforma_da_aplicacao, capsys,
):
    processos = Processos()
    ctx = fazer_ctx(processos, raiz=copia_com_provisionadores,
                    ambiente={"PLATAFORMA_DIR": str(plataforma_da_aplicacao)})
    valor = "id-publico-por-exemplo"
    assert operar.main(["provisionar", "--alvo", "email", "--argumento", valor], ctx) == 0
    assert processos.rodadas()[0]["comando"][-1] == valor
    assert valor not in capsys.readouterr().out


def test_executor_oculta_argumento_que_o_script_imprime(capsys):
    valor = "id-publico-por-exemplo"
    codigo, saida = operar.executar_processo(
        [sys.executable, "-c", "import sys; print(sys.argv[1])", valor],
        env={"PATH": "/usr/bin"}, timeout=10, redigir=(valor,),
    )
    assert codigo == 0
    assert valor not in saida
    assert valor not in capsys.readouterr().out


def test_provisionar_falhou_restaura_env_e_reprova_app(
    fazer_ctx, copia_com_provisionadores, plataforma_da_aplicacao, capsys,
):
    ambiente = plataforma_da_aplicacao / "env"
    chamadas = []

    def processo(comando, *, env, timeout, juntar=True, cwd=None):
        chamadas.append(comando)
        if comando[:2] == ["bash", "-n"]:
            return 0, ""
        if comando[0] == "bash":
            (ambiente / "admin.env").write_text("TOKEN=novo\n", encoding="utf-8")
            (ambiente / "novo.env").write_text("SEGREDO=preservado\n", encoding="utf-8")
            return 1, "falha do provisionador"
        assert comando[-2].endswith("recarregar-aplicacao.py")
        assert comando[-1] == "provisionar-livre.sh"
        assert (ambiente / "admin.env").read_text(encoding="utf-8") == "TOKEN=anterior\n"
        assert not (ambiente / "novo.env").exists()
        return 0, "APLICACAO-RECARREGADA-E-PROVADA"

    ctx = fazer_ctx(processo, raiz=copia_com_provisionadores,
                    ambiente={"PLATAFORMA_DIR": str(plataforma_da_aplicacao)})
    assert operar.op_provisionar(ctx, {"alvo": "livre"}) == 1
    assert len(chamadas) == 3
    assert list((plataforma_da_aplicacao / "publicacoes").glob("provisionar-livre-*/novo-novo.env"))
    assert "preservado" not in capsys.readouterr().out


def test_provisionar_nao_anuncia_retorno_se_prova_falhar(
    fazer_ctx, copia_com_provisionadores, plataforma_da_aplicacao, capsys,
):
    ambiente = plataforma_da_aplicacao / "env"

    def processo(comando, *, env, timeout, juntar=True, cwd=None):
        if comando[:2] == ["bash", "-n"]:
            return 0, ""
        if comando[0] == "bash":
            (ambiente / "admin.env").write_text("TOKEN=novo\n", encoding="utf-8")
            return 1, "falha"
        return 1, "site fora"

    ctx = fazer_ctx(processo, raiz=copia_com_provisionadores,
                    ambiente={"PLATAFORMA_DIR": str(plataforma_da_aplicacao)})
    assert operar.op_provisionar(ctx, {"alvo": "livre"}) == 1
    assert (ambiente / "admin.env").read_text(encoding="utf-8") == "TOKEN=anterior\n"
    assert "não passou na prova de retorno" in capsys.readouterr().out


# --------------------------------------------------------------------------- operacoes-vps


def carregar_com(**trocas):
    def carregar(raiz, relativo, nome):
        modulo = operar.carregar_modulo(raiz, relativo, nome)
        for chave, valor in trocas.items():
            setattr(modulo, chave, valor)
        return modulo

    return carregar


def docker_falso(inspecao):
    chamadas = []

    def comando(argumentos, prazo_segundos=30):
        chamadas.append(argumentos)
        if argumentos[:2] == ["docker", "ps"]:
            return inspecao["ps"]
        if argumentos[:2] == ["docker", "inspect"]:
            return inspecao["inspect"]
        raise AssertionError(f"comando inesperado: {argumentos}")

    comando.chamadas = chamadas
    return comando


ESTADO_OK = json.dumps(
    {"estado": "running", "saude": "healthy", "reinicios": 0, "imagem": "sha256:" + "b" * 64}
)


@pytest.mark.parametrize("aplicacao_ativa", [False, True])
def test_operacoes_vps_mede_confere_e_imprime_so_a_evidencia_validada(
    fazer_ctx, tmp_path, capsys, aplicacao_ativa,
):
    (tmp_path / "publicacoes").mkdir()
    if aplicacao_ativa:
        (tmp_path / "publicacoes" / "aplicacao.json").write_text("{}", encoding="utf-8")
    comando = docker_falso({"ps": "a" * 64 + "\n", "inspect": ESTADO_OK})
    ctx = fazer_ctx(carregar=carregar_com(comando=comando, RAIZ_INFRA=tmp_path))
    assert operar.main(["operacoes-vps", "--operacao", "estado-servico", "--servico", "catalogo"], ctx) == 0
    saida = capsys.readouterr().out
    linha = next(l for l in saida.splitlines() if l.startswith("{"))
    dados = json.loads(linha)
    assert dados["resultado"] == "PASS" and dados["operacao"] == "estado-servico"
    assert dados["servico"] == "catalogo" and dados["medicao"]["estado"] == "running"
    destino = "aplicacao" if aplicacao_ativa else "catalogo"
    assert any(f"label=com.docker.compose.service={destino}" in a for a in comando.chamadas[0])


def test_operacoes_vps_com_servico_fora_do_compose_nem_chega_a_medir(fazer_ctx, capsys):
    comando = docker_falso({"ps": "", "inspect": ""})
    ctx = fazer_ctx(carregar=carregar_com(comando=comando))
    assert operar.main(["operacoes-vps", "--operacao", "estado-servico", "--servico", "nao-existe"], ctx) == 2
    assert comando.chamadas == []
    assert "ERROR" in capsys.readouterr().out


def test_operacoes_vps_servico_padrao_por_operacao_mas_combinacao_errada_e_barrada(fazer_ctx):
    comando = docker_falso({"ps": "", "inspect": ""})
    ctx = fazer_ctx(carregar=carregar_com(comando=comando))
    # appmax-pix sem --servico vira pagamentos; com outro serviço, o validar do módulo barra.
    assert operar.main(["operacoes-vps", "--operacao", "appmax-pix", "--servico", "catalogo"], ctx) == 2
    assert comando.chamadas == []
    assert operar.SERVICOS_PADRAO["coordenacao-db"] == "postgres"


def test_operacoes_vps_medicao_ausente_mostra_o_erro_cru_e_falha(fazer_ctx, capsys):
    comando = docker_falso({"ps": "", "inspect": ""})
    ctx = fazer_ctx(carregar=carregar_com(comando=comando))
    assert operar.main(["operacoes-vps", "--operacao", "estado-servico", "--servico", "admin"], ctx) == 2
    saida = capsys.readouterr().out
    assert '"erro": "ausente"' in saida and "ERROR" in saida


def test_operacoes_vps_evidencia_fora_do_formato_nao_passa(fazer_ctx):
    ruim = json.dumps({"estado": "running", "saude": "healthy", "reinicios": 0, "imagem": "tag-solta"})
    comando = docker_falso({"ps": "a" * 64, "inspect": ruim})
    ctx = fazer_ctx(carregar=carregar_com(comando=comando))
    assert operar.main(["operacoes-vps", "--operacao", "estado-servico", "--servico", "admin"], ctx) == 2


def test_as_operacoes_do_workflow_sao_exatamente_as_do_modulo():
    modulo = operar.carregar_modulo(ROOT, "ci/operacoes_vps.py", "operacoes_vps_conferencia")
    assert set(operar.OPERACOES["operacoes-vps"].params[0].escolhas) == modulo.OPERACOES


def test_servicos_do_compose_com_e_sem_yaml_dao_a_mesma_lista(monkeypatch):
    compose = ROOT / "infra" / "docker-compose.yml"
    com_yaml = pytest.importorskip("yaml") and operar.servicos_do_compose(compose)
    monkeypatch.setitem(sys.modules, "yaml", None)  # `import yaml` passa a dar ImportError
    sem_yaml = operar.servicos_do_compose(compose)
    assert sem_yaml == com_yaml
    assert sem_yaml == ["aplicacao", "plataforma", "postgres", "redis", "traefik"]


# --------------------------------------------------------------------------- módulos Appmax

ESTORNO_PASS = {
    "resultado": "PASS", "ambiente": "sandbox", "solicitacao": "aceita",
    "valor_solicitado_centavos": 495, "pedido_confere": True,
}


def test_estorno_sandbox_passa_so_com_a_evidencia_exata(fazer_ctx, capsys):
    def executar():
        print(json.dumps(ESTORNO_PASS, sort_keys=True))
        return 0

    ctx = fazer_ctx(carregar=carregar_com(executar=executar))
    assert operar.main(["appmax-estorno-sandbox"], ctx) == 0
    assert '"solicitacao": "aceita"' in capsys.readouterr().out


def test_estorno_sandbox_com_erro_na_vps_mostra_a_saida_e_falha(fazer_ctx, capsys):
    def executar():
        print(json.dumps({"resultado": "ERROR", "motivo": "repetida", "acao": "Não repita o POST."}))
        return 2

    ctx = fazer_ctx(carregar=carregar_com(executar=executar))
    assert operar.main(["appmax-estorno-sandbox"], ctx) == 2
    saida = capsys.readouterr().out
    assert '"motivo": "repetida"' in saida and "sem repetir o POST" in saida


def drill_evidencia(resultado, **campos):
    modulo = operar.carregar_modulo(ROOT, "infra/drill-appmax-rollback-sandbox.py", "drill_para_o_teste")
    sonda = {"http": 200, "pix_oferecido": True, "pix_na_appmax": False, "cartao_ligado": True,
             "explicacao_ao_comprador": False}
    return json.dumps(modulo.evidencia(resultado, env_devolvido_identico=True, sondas={"antes": sonda}, **campos))


@pytest.mark.parametrize(
    ("resultado", "esperado"), [("PASS", 0), ("FAIL", 1), ("ERROR", 2)],
)
def test_drill_de_rollback_o_veredito_e_o_da_evidencia_nao_o_codigo_do_script(fazer_ctx, resultado, esperado, capsys):
    campos = {} if resultado == "PASS" else {"motivo": "o cartão não voltou"}
    processos = Processos(lambda cmd, env: (0, drill_evidencia(resultado, **campos) + "\n"))
    assert operar.main(["appmax-drill-rollback"], fazer_ctx(processos)) == esperado
    chamada = processos.chamadas[0]
    assert chamada["comando"][0] == sys.executable and chamada["comando"][-1] == "executar"
    assert chamada["comando"][1].endswith("drill-appmax-rollback-sandbox.py")
    assert chamada["timeout"] == 20 * 60 and chamada["juntar"] is False
    assert f"Resultado: {resultado}" in capsys.readouterr().out


def test_drill_de_rollback_sem_evidencia_e_error(fazer_ctx):
    processos = Processos(lambda cmd, env: (0, "Traceback (most recent call last)\n"))
    assert operar.main(["appmax-drill-rollback"], fazer_ctx(processos)) == 2


# --------------------------------------------------------------------------- navegador


def test_sonda_no_conteiner_oficial_com_uid_de_quem_chama_e_argumentos_como_argv(fazer_ctx):
    processos = Processos()
    ctx = fazer_ctx(processos, ambiente={"OPERAR_NODE": "docker"})
    assert operar.main(["sonda-pix-publica", "--so-auto-teste"], ctx) == 0
    comando = processos.chamadas[0]["comando"]
    assert comando[:3] == ["docker", "run", "--rm"]
    assert operar.IMAGEM_DO_NAVEGADOR in comando
    assert f"{ROOT / 'e2e'}:/repo/e2e:ro" in comando
    assert "--user" in comando
    assert comando[-2:] == ["sonda_pix_publica.js", "--so-auto-teste"]
    assert 'exec node "/repo/e2e/$0" "$@"' in comando[comando.index("-c") + 1]


def test_sonda_sem_o_flag_cria_o_pedido_e_nao_passa_argumento_nenhum(fazer_ctx):
    processos = Processos()
    operar.main(["sonda-pix-publica"], fazer_ctx(processos, ambiente={"OPERAR_NODE": "docker"}))
    assert processos.chamadas[0]["comando"][-1] == "sonda_pix_publica.js"


def test_sonda_usa_node_local_quando_ha_playwright(fazer_ctx, monkeypatch):
    monkeypatch.setattr(operar.shutil, "which", lambda nome: "/usr/bin/node")
    processos = Processos()
    assert operar.main(["sonda-pix-publica"], fazer_ctx(processos)) == 0
    assert processos.chamadas[0]["comando"][:3] == ["node", "-e", "require('playwright')"]
    assert processos.chamadas[1]["comando"] == ["node", str(ROOT / "e2e" / "sonda_pix_publica.js")]


def test_sandbox_tela_compra_espera_conta_so_lendo_e_julga(fazer_ctx, capsys):
    vistos = []

    def resposta(comando, env):
        vistos.append(comando)
        if comando[0] == "docker" and "--etapa=comprar" in comando:
            montagem = comando[comando.index("-v", comando.index("-v") + 1) + 1]
            Path(montagem.split(":/dados")[0], "contagem.sh").write_text("echo '{}'\n", encoding="utf-8")
            return 0, ""
        if comando[0] == "bash" and comando[1] != "-n":
            assert "SAIDA" not in env  # a evidência só entra no passo de julgar
            return 0, '{"resultado": "PASS", "pedidos": {}}\n'
        if comando[0] == "docker":
            assert env["SAIDA"].startswith('{"resultado": "PASS"')
        return 0, ""

    dormiu = []
    processos = Processos(resposta)
    ctx = fazer_ctx(processos, ambiente={"OPERAR_NODE": "docker"})
    ctx.dormir = dormiu.append
    assert operar.main(["appmax-sandbox-tela", "--cartao", "0010", "--perfil", "celular"], ctx) == 0
    assert dormiu == [90]
    comprar, sintaxe, contar, julgar = [c["comando"] for c in processos.chamadas]
    assert {"--etapa=comprar", "--cartao=0010", "--perfil=celular", "--dados=/dados/compras.json"} <= set(comprar)
    assert sintaxe[:2] == ["bash", "-n"] and contar[0] == "bash" and contar[1].endswith("contagem.sh")
    assert processos.chamadas[2]["juntar"] is False  # só o stdout é a evidência
    assert "--etapa=conferir" in julgar and "SAIDA" in julgar and "SAIDA=" not in " ".join(julgar)


def test_sandbox_tela_sem_script_de_contagem_para_antes_de_esperar(fazer_ctx, capsys):
    dormiu = []
    ctx = fazer_ctx(Processos(), ambiente={"OPERAR_NODE": "docker"})
    ctx.dormir = dormiu.append
    assert operar.main(["appmax-sandbox-tela"], ctx) == 1
    assert dormiu == [] and "não gerou o script de contagem" in capsys.readouterr().out


def test_sandbox_tela_sem_filtro_passa_os_argumentos_vazios_como_o_workflow(fazer_ctx):
    processos = Processos(lambda cmd, env: (3, ""))
    operar.main(["appmax-sandbox-tela"], fazer_ctx(processos, ambiente={"OPERAR_NODE": "docker"}))
    comprar = processos.chamadas[0]["comando"]
    assert "--cartao=" in comprar and "--perfil=" in comprar


# --------------------------------------------------------------------------- vigia do cadeado


class Alarmes:
    def __init__(self, falha=None):
        self.chamadas, self.falha = [], falha

    def __call__(self, texto, assunto=None, **kwargs):
        self.chamadas.append((texto, assunto, kwargs))
        if self.falha:
            raise self.falha
        return "enviado"


def test_cadeado_verde_nao_avisa_ninguem(fazer_ctx):
    alarmes = Alarmes()
    processos = Processos(lambda cmd, env: (0, "RESULTADO  PASS\n"))
    assert operar.main(["vigia-do-cadeado"], fazer_ctx(processos, avisar=alarmes)) == 0
    assert alarmes.chamadas == []
    assert processos.chamadas[0]["comando"] == [sys.executable, str(ROOT / "ci" / "vigia_do_cadeado.py")]


def test_cadeado_vermelho_avisa_com_a_medicao_sem_repetir_a_cada_dia(fazer_ctx, capsys):
    alarmes = Alarmes()
    medicao = "  meshcraft.top   FAIL vence em 3 dia(s)\nRESULTADO  FAIL\n"
    processos = Processos(lambda cmd, env: (1, medicao))
    assert operar.main(["vigia-do-cadeado"], fazer_ctx(processos, avisar=alarmes)) == 1
    (texto, assunto, kwargs), = alarmes.chamadas
    assert "vence em 3 dia(s)" in texto and "TRAEFIK DEFAULT CERT" in texto
    assert assunto.startswith("Cadeado vermelho")
    assert kwargs == {"chave": "cadeado-vermelho", "a_cada_horas": 72}


def test_cadeado_vermelho_com_alarme_quebrado_continua_falhando_e_diz_que_o_alarme_nao_saiu(fazer_ctx, capsys):
    alarmes = Alarmes(falha=RuntimeError("env/mensageria.env sem SMTP_HOST"))
    processos = Processos(lambda cmd, env: (1, "RESULTADO  FAIL\n"))
    assert operar.main(["vigia-do-cadeado"], fazer_ctx(processos, avisar=alarmes)) == 1
    assert "NÃO saiu" in capsys.readouterr().out


# --------------------------------------------------------------------------- execução de verdade


def test_executar_processo_junta_ou_separa_o_stderr_e_ecoa(capsys):
    codigo_python = "import sys; print('ola'); print('erro', file=sys.stderr); sys.exit(3)"
    codigo, saida = operar.executar_processo(
        [sys.executable, "-c", codigo_python], env={"PATH": ""}, timeout=30
    )
    assert codigo == 3 and "ola" in saida and "erro" in saida
    codigo, saida = operar.executar_processo(
        [sys.executable, "-c", codigo_python], env={"PATH": ""}, timeout=30, juntar=False
    )
    assert codigo == 3 and "ola" in saida and "erro" not in saida
    assert "ola" in capsys.readouterr().out


def test_executar_processo_estourado_o_prazo_e_encerrado():
    inicio = time.monotonic()
    codigo, _ = operar.executar_processo(
        [sys.executable, "-c", "import time; time.sleep(60)"], env={"PATH": ""}, timeout=1
    )
    assert codigo == 124 and time.monotonic() - inicio < 30


def test_executar_processo_comando_inexistente_e_falha_nao_excecao():
    codigo, _ = operar.executar_processo(["nao-existe-esse-comando"], env={"PATH": ""}, timeout=5)
    assert codigo == 127


@pytest.mark.skipif(BASH is None, reason="sem bash utilizável")
def test_de_ponta_a_ponta_com_bash_de_verdade_o_valor_chega_so_por_ambiente(tmp_path, fazer_ctx, capsys):
    raiz = tmp_path / "copia"
    (raiz / "infra").mkdir(parents=True)
    (raiz / "infra" / "semear-caixa.sh").write_text(
        '#!/usr/bin/env bash\nset -u\necho "host=[$HOST_CAIXA] raiz=[$PLATAFORMA_DIR]"\necho "PRONTO: ok"\n',
        encoding="utf-8", newline="\n",
    )

    def com_o_bash_sondado(comando, **kwargs):
        return operar.executar_processo([BASH, *comando[1:]], **kwargs)

    ctx = fazer_ctx(com_o_bash_sondado, raiz=raiz, ambiente={"PATH": str(Path(BASH).parent)})
    assert operar.main(["semear-caixa", "--host", "exemplo.top"], ctx) == 0
    assert "host=[exemplo.top] raiz=[/opt/plataforma]" in capsys.readouterr().out

    (raiz / "infra" / "semear-caixa.sh").write_text("echo 'PAROU POR SEGURANÇA: x'\n", encoding="utf-8", newline="\n")
    assert operar.main(["semear-caixa"], ctx) == 1
