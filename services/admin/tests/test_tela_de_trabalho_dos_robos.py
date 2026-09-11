"""A tela de TRABALHO da aba "Os robôs" (06/09/2026).

Até 06/09/2026 `/admin/caixa/robos/` respondia "o que está parado" e não dava
jeito nenhum de fazer nada com aquilo. O mantenedor abriu a página, viu 22
tarefas na fila e disse que não entendia nenhuma: todo campo do cartão tinha
sido escrito por robô para robô. Ele pediu quatro coisas, e são elas que estes
guardas protegem.

1. **A explicação em português de gente**, com um exemplo. Ela vem da FILA
   (`o_que_e`, `o_que_muda`, `exemplo`, escritos pelo evento `explicada`), e
   esta tela nunca a inventa. Tarefa sem explicação DIZ isso, e nunca deixa um
   espaço em branco: um buraco calado seria lido como "esta aqui é simples".
2. **O ranking.** `importancia` (0 a 100) é declarada na fila; a POSIÇÃO é
   calculada aqui, a cada visita. Guardá-la seria a segunda definição que o
   cabeçalho de `robos.py` proíbe, e ela muda sozinha quando uma tarefa entra
   ou sai da fila.
3. **O prompt pronto**, calculado do id e do `toca`, com o mandato NOMINAL
   quando a tarefa toca caminho CODEOWNERS. Sem ele o robô que receber o pedido
   para na primeira linha, e o botão teria entregado um pedido morto.
4. **O botão de excluir**, que não apaga nada: ele abre um PR no GitHub com o
   evento `cancelada`, e quem mergeia é a pista. A tela nunca escreve na `main`.

E dois guardas que não vêm do pedido dele, e sim das leis da casa:

- **o `TAR-NNN` do formulário é DADO** (`armadilhas/047`): ele vira nome de ramo
  e nome de arquivo, e é conferido contra o formato ANTES de qualquer chamada;
- **sem `GITHUB_TOKEN_FILA` o botão nasce desligado**, dizendo o que fazer, e
  não fala com o GitHub. Botão escondido seria pior: ele nunca saberia do gesto.
"""

import json
import re
from html.parser import HTMLParser

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.auditoria.models import Registro
from apps.core import fila_no_github, robos

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"

REPO = f"https://api.github.com/repos/{fila_no_github.REPOSITORIO}"
SHA_DA_MAIN = "0123456789abcdef0123456789abcdef01234567"

RE_ESTILO = re.compile(r"<style\b[^>]*>.*?</style\s*>", re.DOTALL | re.IGNORECASE)


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    # O padrão de toda esta suíte é a imagem SEM a senha do GitHub, que é o
    # estado em que a célula está hoje em produção. Quem quer o botão ligado
    # chama `com_token`.
    monkeypatch.delenv(fila_no_github.VARIAVEL_DO_TOKEN, raising=False)
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


@pytest.fixture
def com_token(monkeypatch):
    monkeypatch.setenv(fila_no_github.VARIAVEL_DO_TOKEN, "ghp-de-mentira")


def _dentro(**extras) -> Client:
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "id-opaco-123",
                "nome_exibido": "Fulano",
                "papel": None,
                "email": DONO,
            },
        )
    )
    c = Client(**extras)
    c.defaults["HTTP_COOKIE"] = COOKIE
    return c


def fila_com_ranking(tmp_path, monkeypatch, estados=None):
    """Uma fila embutida como o deploy a deixaria, já com o vocabulário novo.

    O contrato é o de `estados.json`: a tela lê `o_que_e`, `o_que_muda`,
    `exemplo` e `importancia` do que a fila materializou, e não os calcula.
    """
    pasta = tmp_path / "fila_embutida"
    (pasta / "esperas").mkdir(parents=True, exist_ok=True)
    (pasta / "eventos").mkdir(exist_ok=True)
    (pasta / "regua.json").write_text("{}", encoding="utf-8")
    (pasta / "estados.json").write_text(
        json.dumps(
            (
                estados
                if estados is not None
                else {
                    # A do meio da fila, sem caminho protegido.
                    "TAR-100": {
                        "estado": "na fila",
                        "motivo": "ninguém pegou ainda",
                        "quem": None,
                        "titulo": "O dossiê em PDF do portfólio",
                        "toca": ["pages"],
                        "importancia": 55,
                        "o_que_e": "O aluno monta o portfólio no site e não consegue transformar isso num arquivo.",
                        "o_que_muda": "É a ponta do portfólio que vira dinheiro.",
                        "exemplo": "Ele aperta um botão e baixa um PDF para mandar a um estúdio.",
                    },
                    # A mais cara, e ela toca DOIS caminhos protegidos.
                    "TAR-101": {
                        "estado": "na fila",
                        "motivo": "ninguém pegou ainda",
                        "quem": None,
                        "titulo": "A esteira desiste antes do teste mais lento terminar",
                        "toca": ["ci", "services/checkout", "alunos"],
                        "importancia": 90,
                        "o_que_e": "A esteira espera um tempo fixo e desiste no meio.",
                        "o_que_muda": "Trabalho pronto fica parado sem chegar no site.",
                        "exemplo": "É a esteira do aeroporto parando antes da última mala sair.",
                    },
                    # A barata, sem explicação nenhuma.
                    "TAR-102": {
                        "estado": "na fila",
                        "motivo": "ninguém pegou ainda",
                        "quem": None,
                        "titulo": "Um conferidor de fim de linha entre o Windows e o servidor",
                        "toca": ["ci"],
                        "importancia": 20,
                    },
                    # A que ninguém classificou: vai para o fim, e diz isso.
                    "TAR-103": {
                        "estado": "na fila",
                        "motivo": "ninguém pegou ainda",
                        "quem": None,
                        "titulo": "Marcar como abandonado o trabalho que ficou para trás",
                        "toca": ["ci"],
                        "o_que_e": "Trabalhos que ninguém terminou ficam guardados para sempre.",
                        "o_que_muda": "Entulho e trabalho vivo aparecem iguais na lista.",
                        "exemplo": "É a gaveta com contas pagas e a pagar no mesmo maço.",
                    },
                    # Fora do grupo ranqueado: explica igual, sem posição nem botão.
                    "TAR-104": {
                        "estado": "reivindicada",
                        "motivo": "",
                        "quem": "sessao-x",
                        "titulo": "A tela de trabalho dos robôs",
                        "toca": ["admin"],
                        "importancia": 99,
                        "o_que_e": "A tela que você está lendo agora.",
                        "o_que_muda": "Você passa a entender o que está parado.",
                        "exemplo": "Este cartão mesmo.",
                    },
                    "TAR-105": {
                        "estado": "concluída",
                        "motivo": "https://github.com/x/y/pull/1",
                        "quem": "sessao-y",
                        "titulo": "Uma que já acabou",
                        "toca": ["admin"],
                        "importancia": 100,
                    },
                }
            ),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(robos, "CANDIDATOS", (pasta,))
    return pasta


def pagina_sem_estilo(resposta) -> str:
    return RE_ESTILO.sub("", resposta.content.decode())


def numa_linha(texto: str) -> str:
    """O HTML quebra as frases em várias linhas; quem lê a tela vê uma só."""
    return re.sub(r"\s+", " ", texto)


def github_responde_bem():
    from test_retomada_do_cancelamento import GitHubControlado

    remoto = GitHubControlado()
    respx.route(url__startswith=REPO).mock(side_effect=remoto.responder)
    return remoto


# ---------------------------------------------------------------------------
# 1. A EXPLICAÇÃO
# ---------------------------------------------------------------------------


@respx.mock
def test_o_cartao_explica_a_tarefa_com_os_tres_paragrafos(tmp_path, monkeypatch):
    fila_com_ranking(tmp_path, monkeypatch)
    pagina = pagina_sem_estilo(_dentro().get(reverse("caixa_robos")))

    assert "O que é." in pagina
    assert "O que muda para você." in pagina
    assert "A esteira espera um tempo fixo e desiste no meio." in pagina
    assert "Trabalho pronto fica parado sem chegar no site." in pagina
    assert "É a esteira do aeroporto parando antes da última mala sair." in pagina


@respx.mock
def test_tarefa_sem_explicacao_diz_isso_em_vez_de_deixar_branco(tmp_path, monkeypatch):
    """Buraco calado é lido como "esta é simples". A tela nunca deixa um."""
    fila_com_ranking(tmp_path, monkeypatch)
    pagina = pagina_sem_estilo(_dentro().get(reverse("caixa_robos")))

    assert "Ninguém explicou esta tarefa ainda" in pagina


@respx.mock
def test_a_historia_ja_fechada_nao_pede_explicacao(tmp_path, monkeypatch):
    """Medido na prévia com a fila de verdade: a linha saía 199 vezes.

    A maioria era história já encerrada (concluídas, canceladas, corrente da
    fila), que não pede explicação de ninguém. Aviso repetido duzentas vezes
    ensina o olho a pular a página, que é o defeito que esta tela veio curar.
    Nos grupos que ainda pedem trabalho ela continua obrigatória.
    """
    fila_com_ranking(tmp_path, monkeypatch)
    pagina = pagina_sem_estilo(_dentro().get(reverse("caixa_robos")))

    # Só a TAR-102, do grupo aberto. A TAR-105 (concluída, também sem
    # explicação) fica calada.
    assert pagina.count("Ninguém explicou esta tarefa ainda") == 1
    assert "Uma que já acabou" in pagina, "a concluída sumiu junto com o aviso"


@respx.mock
def test_a_explicacao_aparece_tambem_fora_do_grupo_ranqueado(tmp_path, monkeypatch):
    fila_com_ranking(tmp_path, monkeypatch)
    pagina = pagina_sem_estilo(_dentro().get(reverse("caixa_robos")))

    assert "A tela que você está lendo agora." in pagina


# ---------------------------------------------------------------------------
# 2. O RANKING
# ---------------------------------------------------------------------------


@respx.mock
def test_a_ordem_do_grupo_e_a_importancia_decrescente(tmp_path, monkeypatch):
    fila_com_ranking(tmp_path, monkeypatch)
    pagina = pagina_sem_estilo(_dentro().get(reverse("caixa_robos")))

    posicoes = [pagina.find(f"TAR-10{n}") for n in (1, 0, 2, 3)]
    assert -1 not in posicoes
    assert posicoes == sorted(posicoes), (
        "a fila não saiu da mais cara para a mais barata: "
        "90, 55, 20 e a que ninguém classificou, nessa ordem"
    )


@respx.mock
def test_a_posicao_e_calculada_a_cada_visita_e_nunca_guardada(tmp_path, monkeypatch):
    """A MESMA tarefa muda de posição quando a fila muda, sem nada ser reescrito.

    É a prova de que #1 é uma conta, e não um campo: guardá-lo seria a segunda
    definição de "o que é mais importante", e ela mentiria no dia seguinte.
    """
    fila_com_ranking(tmp_path, monkeypatch)
    primeira = pagina_sem_estilo(_dentro().get(reverse("caixa_robos")))
    assert re.search(r"#1</span>\s*<span class=\"selo alta\"", primeira)
    assert primeira.find("TAR-101") < primeira.find("TAR-100")

    # A mais cara sai da fila; a de baixo sobe sozinha para o #1.
    fila_com_ranking(
        tmp_path,
        monkeypatch,
        estados={
            "TAR-100": {
                "estado": "na fila",
                "motivo": "",
                "quem": None,
                "titulo": "O dossiê em PDF do portfólio",
                "toca": ["pages"],
                "importancia": 55,
            },
        },
    )
    segunda = pagina_sem_estilo(_dentro().get(reverse("caixa_robos")))
    assert "#1" in segunda and "TAR-100" in segunda
    assert "TAR-101" not in segunda


@respx.mock
def test_o_selo_sai_da_faixa_da_importancia(tmp_path, monkeypatch):
    fila_com_ranking(tmp_path, monkeypatch)
    pagina = pagina_sem_estilo(_dentro().get(reverse("caixa_robos")))

    assert "custa caro hoje" in pagina  # 90
    assert "importa" in pagina  # 55
    assert "pode esperar" in pagina  # 20
    assert "ninguém classificou esta ainda" in pagina  # sem nota


@pytest.mark.parametrize(
    "valor", [None, "alta", 101, -1, 3.5, True, False, [70]], ids=str
)
def test_importancia_que_nao_e_um_inteiro_de_0_a_100_vira_sem_nota(valor):
    """Falha ABERTO: o que a tela não reconhece ela mostra, nunca engole.

    `True` é `int` em Python e viraria importância 1 sem o corte à parte.
    """
    assert robos.importancia_declarada({"importancia": valor}) is None
    assert robos.importancia_declarada({}) is None


def test_as_tres_faixas_do_selo():
    assert robos.selo_da_importancia(70)["texto"] == "custa caro hoje"
    assert robos.selo_da_importancia(100)["texto"] == "custa caro hoje"
    assert robos.selo_da_importancia(69)["texto"] == "importa"
    assert robos.selo_da_importancia(40)["texto"] == "importa"
    assert robos.selo_da_importancia(39)["texto"] == "pode esperar"
    assert robos.selo_da_importancia(0)["texto"] == "pode esperar"
    assert robos.selo_da_importancia(None)["classe"] == "sem-nota"


@respx.mock
def test_o_grupo_do_meio_da_fila_nao_ganha_posicao_nem_botoes(tmp_path, monkeypatch):
    """Ranquear o que um robô já pegou seria uma ordem que não muda decisão."""
    fila_com_ranking(tmp_path, monkeypatch)
    pagina = pagina_sem_estilo(_dentro().get(reverse("caixa_robos")))

    # Quatro tarefas esperando um robô, e SÓ elas ganham posição e botões — as
    # outras duas (uma com um robô, uma concluída) ficam de fora das duas coisas.
    assert pagina.count('class="posicao"') == 4
    assert pagina.count('class="tocar"') == 4


# ---------------------------------------------------------------------------
# 3. O PROMPT
# ---------------------------------------------------------------------------


def test_o_prompt_cita_a_tarefa_e_manda_ler_o_despacho():
    texto = robos.prompt_para_tocar("TAR-100", ["pages"])
    assert texto.startswith("Toque a TAR-100 da fila de trabalho.")
    assert "fila/tarefas/" in texto
    assert "mandato" not in texto, "inventou mandato para caminho que não é protegido"


def test_o_prompt_preserva_a_tarefa_e_submete_sem_confundir_com_aceite():
    texto = robos.prompt_para_tocar("TAR-100", ["admin"])
    assert "--tar TAR-100" in texto
    assert "TAR=TAR-100" in texto
    assert "submeter TAR-100" in texto
    assert "--revisao" in texto and "--arvore" in texto
    assert "aceite" in texto
    assert "Conclua a tarefa no balcão com a URL do PR" not in texto


def test_o_prompt_da_mandato_nominal_em_caminho_codeowners():
    """Sem esta frase o robô PARA na primeira linha, e o botão entrega nada."""
    um = robos.prompt_para_tocar("TAR-102", ["ci"])
    assert "meu mandato para o caminho protegido: ci." in um

    dois = robos.prompt_para_tocar("TAR-101", ["ci", "services/checkout", "alunos"])
    assert "meu mandato para os caminhos protegidos: ci, checkout." in dois
    assert "alunos" not in dois.split("mandato")[1].split("\n")[0]
    for instrucao in (
        "bancada própria",
        "índice de armadilhas",
        "teste que nasce vermelho",
        "registro do painel",
        "Devolva o resultado a mim",
    ):
        assert instrucao in dois


def test_os_caminhos_protegidos_saem_normalizados_e_sem_repetir():
    assert robos.caminhos_protegidos(["services/checkout", "checkout"]) == ["checkout"]
    assert robos.caminhos_protegidos([".github", "ci"]) == [".github", "ci"]
    assert robos.caminhos_protegidos(["admin", "pages"]) == []
    assert robos.caminhos_protegidos(None) == []


@respx.mock
def test_o_prompt_esta_escrito_no_html_para_quem_nao_tem_area_de_transferencia(
    tmp_path, monkeypatch
):
    """Ele NÃO é montado pelo script: sem cópia, o texto continua na tela."""
    fila_com_ranking(tmp_path, monkeypatch)
    pagina = pagina_sem_estilo(_dentro().get(reverse("caixa_robos")))

    assert 'id="prompt-TAR-101"' in pagina
    assert "Toque a TAR-101 da fila de trabalho." in pagina
    assert "meu mandato para os caminhos protegidos: ci, checkout." in pagina


# ---------------------------------------------------------------------------
# 4. O BOTÃO DE EXCLUIR
# ---------------------------------------------------------------------------


@respx.mock
def test_sem_a_chave_do_github_o_botao_nasce_desligado_e_diz_como_o_dono_liga_sozinho(
    tmp_path, monkeypatch
):
    fila_com_ranking(tmp_path, monkeypatch)
    pagina = pagina_sem_estilo(_dentro().get(reverse("caixa_robos")))

    assert "Excluir (desligado)" in pagina
    assert "disabled" in pagina
    linha = numa_linha(pagina)
    assert "nada está quebrado por isso" in linha, "assustou o dono à toa"
    assert (
        "infra/por-a-chave-do-github.sh" in linha
    ), "não apontou o roteiro com o passo a passo"
    assert (
        "github.com/settings/personal-access-tokens/new" in linha
    ), "não disse onde o dono cria a chave"
    assert "ponha a" not in linha, "ainda manda o dono decorar jargão para um robô"
    assert "<dialog" not in pagina, "a caixa de confirmação nasceu sem serventia"


@respx.mock
def test_com_a_senha_o_botao_fica_clicavel_e_a_confirmacao_existe(
    tmp_path, monkeypatch, com_token
):
    fila_com_ranking(tmp_path, monkeypatch)
    pagina = pagina_sem_estilo(_dentro().get(reverse("caixa_robos")))

    assert 'class="excluir" data-tarefa="TAR-101"' in pagina
    assert "Excluir (desligado)" not in pagina
    assert "Pedir a exclusão desta tarefa?" in pagina
    assert 'name="motivo"' in pagina and "required" in pagina
    assert "csrfmiddlewaretoken" in pagina


@respx.mock
def test_excluir_abre_um_pr_com_o_evento_da_fila_e_nao_toca_na_main(
    tmp_path, monkeypatch, com_token
):
    fila_com_ranking(tmp_path, monkeypatch)
    remoto = github_responde_bem()
    resposta = _dentro().post(
        reverse("caixa_robos_excluir"),
        {"tarefa": "TAR-102", "motivo": "é a mesma coisa que a TAR-101."},
    )
    assert resposta.status_code == 200
    assert resposta.context["resultado"] == "revisao"
    assert resposta.context["pr"] == 1270
    assert len(remoto.arquivos) == len(remoto.prs) == 1
    evento = json.loads(next(iter(remoto.arquivos.values())))
    assert evento["tarefa"] == "TAR-102"
    assert evento["evento"] == "cancelada"
    assert evento["detalhe"] == "é a mesma coisa que a TAR-101."
    assert evento["arquivo"].endswith("-TAR-102-cancelada")
    assert set(evento) == {"arquivo", "tarefa", "evento", "quando", "quem", "detalhe"}
    refs = [
        json.loads(req.content)
        for (metodo, path), req in remoto.chamadas
        if metodo == "POST" and path == "/git/refs"
    ]
    assert refs[0]["ref"] == "refs/heads/agent/fila/cancelar-TAR-102"
    assert refs[0]["sha"] != SHA_DA_MAIN
    assert remoto.prs[0]["base"]["ref"] == "main"
    assert remoto.prs[0]["head"]["ref"] == "agent/fila/cancelar-TAR-102"


@respx.mock
def test_a_tela_confere_o_pedido_posterior_sem_inventar_publicacao(
    tmp_path, monkeypatch, com_token
):
    fila_com_ranking(tmp_path, monkeypatch)
    github_responde_bem()
    cliente = _dentro()
    cliente.post(
        reverse("caixa_robos_excluir"), {"tarefa": "TAR-102", "motivo": "repetida."}
    )

    pagina = pagina_sem_estilo(
        cliente.get(
            reverse("caixa_robos"),
            {"pedido": "TAR-102"},
        )
    )
    assert "Pedido recebido, em revisão." in pagina
    assert "nº 1270" in pagina
    assert "8 minutos" not in pagina
    assert "A integração e a aplicação ainda precisam ser conferidas." in pagina
    assert f"https://github.com/{fila_no_github.REPOSITORIO}/pull/1270" in pagina


@respx.mock
def test_um_numero_de_pr_que_nao_e_numero_nao_vira_link(tmp_path, monkeypatch):
    """O número veio de um servidor de fora: a página confere antes de linkar."""
    fila_com_ranking(tmp_path, monkeypatch)
    pagina = pagina_sem_estilo(
        _dentro().get(
            reverse("caixa_robos"),
            {"resultado": "pedido_aberto", "pr": "1270/../evil", "tarefa": "TAR-102"},
        )
    )
    assert "evil" not in pagina


@respx.mock
def test_sem_motivo_a_tela_recusa_e_nao_fala_com_o_github(
    tmp_path, monkeypatch, com_token
):
    """O `detalhe` é obrigatório no balcão, e a tela para antes de gastar rede."""
    fila_com_ranking(tmp_path, monkeypatch)
    resposta = _dentro().post(
        reverse("caixa_robos_excluir"), {"tarefa": "TAR-102", "motivo": "   "}
    )

    assert resposta.context["resultado"] == "sem_motivo"
    assert respx.calls.call_count == 1, "falou com o GitHub sem ter o motivo"


@respx.mock
def test_motivo_longo_demais_e_recusado(tmp_path, monkeypatch, com_token):
    fila_com_ranking(tmp_path, monkeypatch)
    resposta = _dentro().post(
        reverse("caixa_robos_excluir"),
        {"tarefa": "TAR-102", "motivo": "x" * (robos.MOTIVO_NO_MAXIMO + 1)},
    )
    assert resposta.context["resultado"] == "motivo_longo"


@respx.mock
@pytest.mark.parametrize(
    "id_torto",
    [
        "",
        "TAR-1",
        "tar-102",
        "../../etc/passwd",
        "TAR-102; rm -rf /",
        "main",
        # Longos DE PROPÓSITO: `alvo` tem 64 no banco, e um id enorme sem corte
        # derrubaria a própria linha de auditoria com erro do Postgres, virando
        # uma página 500 em vez de uma recusa explicada. O segundo passa no
        # formato e cai no gate seguinte, que é o que faz a auditoria ser
        # escrita com o valor comprido.
        "x" * 300,
        "TAR-" + "9" * 200,
    ],
    ids=str,
)
def test_id_fora_do_formato_nunca_chega_a_virar_ramo(
    tmp_path, monkeypatch, com_token, id_torto
):
    """`armadilhas/047`: valor de formulário é dado, e se confere antes de usar."""
    fila_com_ranking(tmp_path, monkeypatch)
    resposta = _dentro().post(
        reverse("caixa_robos_excluir"), {"tarefa": id_torto, "motivo": "não serve."}
    )

    assert resposta.context["resultado"] == "nao_existe"
    assert respx.calls.call_count == 1, "um id torto chegou ao GitHub"


@respx.mock
def test_id_torto_e_recusado_mesmo_estando_na_fila(tmp_path, monkeypatch, com_token):
    """A conferência de formato é a ÚNICA barreira quando o id existe no dado.

    Sem este caso a prova por mutação mentia: desligar a conferência continuava
    verde, porque um id torto era barrado logo depois, por não existir nos
    estados. Aqui ele EXISTE, e o que o segura é só o formato, que é o que a
    `armadilhas/047` manda conferir antes de o valor virar nome de ramo.
    """
    fila_com_ranking(
        tmp_path,
        monkeypatch,
        estados={
            "../../fila/eventos": {
                "estado": "na fila",
                "motivo": "",
                "quem": None,
                "titulo": "Uma chave torta que alguém conseguiu pôr no dado",
                "toca": ["ci"],
                "importancia": 50,
            }
        },
    )
    github_responde_bem()
    resposta = _dentro().post(
        reverse("caixa_robos_excluir"),
        {"tarefa": "../../fila/eventos", "motivo": "não deveria passar."},
    )

    assert resposta.context["resultado"] == "nao_existe"
    assert respx.calls.call_count == 1, "um id torto virou nome de ramo no GitHub"


@respx.mock
def test_tarefa_que_nao_esta_na_fila_e_recusada(tmp_path, monkeypatch, com_token):
    fila_com_ranking(tmp_path, monkeypatch)
    resposta = _dentro().post(
        reverse("caixa_robos_excluir"), {"tarefa": "TAR-999", "motivo": "sumiu."}
    )
    assert resposta.context["resultado"] == "nao_existe"
    assert respx.calls.call_count == 1


@respx.mock
def test_tarefa_que_ja_terminou_e_recusada(tmp_path, monkeypatch, com_token):
    """Depois do fim, silêncio: a fila reprova evento posterior a um terminal."""
    fila_com_ranking(tmp_path, monkeypatch)
    resposta = _dentro().post(
        reverse("caixa_robos_excluir"), {"tarefa": "TAR-105", "motivo": "tarde demais."}
    )
    assert resposta.context["resultado"] == "ja_terminou"
    assert respx.calls.call_count == 1


@respx.mock
def test_sem_a_senha_o_gesto_nao_fala_com_o_github_e_diz_o_que_fazer(
    tmp_path, monkeypatch
):
    fila_com_ranking(tmp_path, monkeypatch)
    resposta = _dentro().post(
        reverse("caixa_robos_excluir"), {"tarefa": "TAR-102", "motivo": "repetida."}
    )

    assert resposta.context["resultado"] == "sem_token"
    assert respx.calls.call_count == 1, "tentou falar com o GitHub sem senha"

    pagina = pagina_sem_estilo(resposta)
    linha = numa_linha(pagina)
    # Isolado do resto da página, porque o mesmo carregamento também mostra o
    # aviso PREVENTIVO do botão desligado (classe "desligado") — são dois
    # textos distintos, para dois momentos distintos, coexistindo na mesma
    # tela quando o token falta.
    desfecho = (
        re.search(r'<p class="desfecho nao-deu">(.*?)</p>', linha).group(1).strip()
    )
    assert desfecho.startswith(
        "O clique não abriu o pedido no GitHub"
    ), "o texto do desfecho tem de começar pelo que aconteceu, não pelo estado do botão"
    assert "tenha vencido" in desfecho, "não avisou que a chave pode ter vencido"
    assert "ponha (ou troque) a GITHUB_TOKEN_FILA no env da admin" in desfecho
    assert "infra/por-a-chave-do-github.sh" in desfecho, "não apontou o roteiro"
    assert (
        "está cinza porque falta uma chave" not in desfecho
    ), "repetiu a frase do aviso preventivo, que é de outro momento"


@respx.mock
def test_ramo_existente_sem_pr_nao_e_chamado_de_pedido_aberto(
    tmp_path, monkeypatch, com_token
):
    fila_com_ranking(tmp_path, monkeypatch)
    remoto = github_responde_bem()
    remoto.ramo = SHA_DA_MAIN
    remoto.falhar = ("POST", "/git/trees")
    resposta = _dentro().post(
        reverse("caixa_robos_excluir"), {"tarefa": "TAR-102", "motivo": "de novo."}
    )
    assert resposta.context["resultado"] == "incerto"
    assert not remoto.prs
    assert "já existe um pedido aberto" not in pagina_sem_estilo(resposta)
    assert resposta.context["rascunho"]["motivo"] == "de novo."


@respx.mock
def test_a_internet_caindo_no_meio_nao_vira_pagina_de_erro(
    tmp_path, monkeypatch, com_token
):
    fila_com_ranking(tmp_path, monkeypatch)
    respx.get(f"{REPO}/pulls").mock(side_effect=httpx.ConnectError("sem rota"))

    resposta = _dentro().post(
        reverse("caixa_robos_excluir"), {"tarefa": "TAR-102", "motivo": "tentativa."}
    )
    assert resposta.status_code == 200
    assert resposta.context["resultado"] == "incerto"


@respx.mock
def test_o_post_sem_carimbo_de_csrf_e_recusado(tmp_path, monkeypatch, com_token):
    fila_com_ranking(tmp_path, monkeypatch)
    resposta = _dentro(enforce_csrf_checks=True).post(
        reverse("caixa_robos_excluir"), {"tarefa": "TAR-102", "motivo": "sem carimbo."}
    )
    assert resposta.status_code == 403


@respx.mock
def test_a_rota_de_excluir_so_aceita_post(tmp_path, monkeypatch, com_token):
    fila_com_ranking(tmp_path, monkeypatch)
    assert _dentro().get(reverse("caixa_robos_excluir")).status_code == 405


@respx.mock
def test_cada_desfecho_deixa_uma_linha_de_auditoria(tmp_path, monkeypatch, com_token):
    """A auditoria distingue a confirmação do PR da recusa local do formulário."""
    fila_com_ranking(tmp_path, monkeypatch)
    github_responde_bem()
    cliente = _dentro()

    cliente.post(
        reverse("caixa_robos_excluir"), {"tarefa": "TAR-102", "motivo": "repetida."}
    )
    cliente.post(reverse("caixa_robos_excluir"), {"tarefa": "TAR-102", "motivo": ""})

    linhas = list(Registro.objects.filter(acao=Registro.CANCELAR_TAREFA).order_by("id"))
    assert len(linhas) == 2
    assert linhas[0].desfecho == Registro.OK
    assert linhas[0].alvo == "TAR-102"
    assert "1270" in linhas[0].detalhe
    assert linhas[0].quem_email == DONO
    assert linhas[1].desfecho == Registro.RECUSADO_PELA_CELULA


# ---------------------------------------------------------------------------
# O CSP, com as DUAS ilhas de script
# ---------------------------------------------------------------------------


@respx.mock
def test_as_duas_ilhas_entram_por_hash_e_unsafe_inline_nunca(
    tmp_path, monkeypatch, com_token
):
    fila_com_ranking(tmp_path, monkeypatch)
    csp = _dentro().get(reverse("caixa_robos"))["Content-Security-Policy"]

    script_src = csp.split("script-src")[1].split(";")[0]
    assert script_src.count("'sha256-") == 2, "uma das ilhas ficaria bloqueada"
    assert "unsafe-inline" not in script_src
    assert "connect-src 'self' https://api.github.com" in csp


@respx.mock
def test_parametros_de_resultado_na_url_nao_sao_prova(tmp_path, monkeypatch):
    fila_com_ranking(tmp_path, monkeypatch)
    resposta = _dentro().get(
        reverse("caixa_robos"),
        {"resultado": "pedido_aberto", "pr": "1270", "tarefa": "TAR-102"},
    )
    assert resposta.context["resultado"] == ""
    assert "Pedido recebido" not in pagina_sem_estilo(resposta)
    assert len(respx.calls) == 1


@respx.mock
def test_motivo_multilinha_sobrevive_ao_formulario_e_a_retomada(
    tmp_path, monkeypatch, com_token
):
    class FormularioDeCancelamento(HTMLParser):
        def __init__(self, resposta):
            super().__init__(convert_charrefs=True)
            self.dados = {}
            self.campo = None
            self.feed(
                resposta.content.decode().replace("\r\n", "\n").replace("\r", "\n")
            )

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            nome = attrs.get("name")
            if nome not in {"tarefa", "motivo"}:
                return
            if tag == "input":
                # O controle de linha única remove CR/LF antes de enviar.
                self.dados[nome] = (
                    attrs.get("value", "").replace("\r", "").replace("\n", "")
                )
            elif tag == "textarea":
                self.campo = nome
                self.dados[nome] = ""

        def handle_data(self, data):
            if self.campo:
                # A submissão HTML serializa quebras de linha como CRLF.
                self.dados[self.campo] += data.replace("\n", "\r\n")

        def handle_endtag(self, tag):
            if tag == "textarea":
                self.campo = None

    fila_com_ranking(tmp_path, monkeypatch)
    remoto = github_responde_bem()
    remoto.falhar = ("POST", "/pulls")
    remoto.resposta_perdida = True
    cliente = _dentro()
    motivo = (
        'Primeira linha: "duplicada" & conferida.\r\n\r\nSegunda linha: <preservar>.'
    )
    resposta = cliente.post(
        reverse("caixa_robos_excluir"), {"tarefa": "TAR-102", "motivo": motivo}
    )
    assert resposta.status_code == 200
    assert resposta.context["resultado"] == "recebido"
    originais = dict(remoto.arquivos)
    assert json.loads(next(iter(originais.values())))["detalhe"] == motivo
    assert len(remoto.prs) == len(originais) == 1
    chamadas = len(remoto.chamadas)

    for _ in range(2):
        formulario = FormularioDeCancelamento(resposta)
        resposta = cliente.post(reverse("caixa_robos_excluir"), formulario.dados)
        assert resposta.status_code == 200
        assert resposta.context["resultado"] == "revisao"
        assert resposta.context["rascunho"]["motivo"] == motivo
        assert resposta.context["pr"] == 1270
        resposta = cliente.get(reverse("caixa_robos"), {"pedido": "TAR-102"})
        assert resposta.context["resultado"] == "revisao"
        assert resposta.context["rascunho"]["motivo"] == motivo
        assert remoto.arquivos == originais
        assert len(remoto.prs) == len(remoto.arquivos) == 1

    assert all(chave[0] == "GET" for chave, _ in remoto.chamadas[chamadas:])


@respx.mock
def test_erro_preserva_motivo_no_html_sem_texto_livre_na_url(
    tmp_path, monkeypatch, com_token
):
    fila_com_ranking(tmp_path, monkeypatch)
    remoto = github_responde_bem()
    remoto.falhar = ("POST", "/pulls")
    motivo = '  repetida <script>alert("não executar")</script> & mais  '
    resposta = _dentro().post(
        reverse("caixa_robos_excluir"), {"tarefa": "TAR-102", "motivo": motivo}
    )
    assert resposta.status_code == 200 and "Location" not in resposta
    assert resposta.context["rascunho"]["motivo"] == motivo
    assert resposta.context["resultado"] == "recebido"
    assert "&lt;script&gt;" in pagina_sem_estilo(resposta)
    assert "<script>alert(" not in pagina_sem_estilo(resposta)
    registro = Registro.objects.get(acao=Registro.CANCELAR_TAREFA)
    assert "não foi possível confirmar" in registro.detalhe.lower()
    assert "nada foi salvo" not in registro.detalhe.lower()


@respx.mock
@pytest.mark.parametrize(
    "estado,arquivo,aplicada",
    [
        ("na fila", "ausente", False),
        ("cancelada", "ausente", False),
        ("cancelada", "adulterado", False),
        ("na fila", "exato", False),
        ("cancelada", "exato", True),
    ],
    ids=[
        "sem-provas",
        "sem-arquivo",
        "bytes-divergentes",
        "estado-divergente",
        "ambas-provas",
    ],
)
def test_integracao_so_vira_aplicacao_com_evento_exato_na_fila(
    tmp_path, monkeypatch, com_token, estado, arquivo, aplicada
):
    fila_com_ranking(tmp_path, monkeypatch)
    remoto = github_responde_bem()
    cliente = _dentro()
    cliente.post(
        reverse("caixa_robos_excluir"), {"tarefa": "TAR-102", "motivo": "repetida."}
    )
    remoto.prs[0].update(state="closed", merged=True)
    pasta = tmp_path / "fila_embutida"
    estados = json.loads((pasta / "estados.json").read_text(encoding="utf-8"))
    estados["TAR-102"]["estado"] = estado
    (pasta / "estados.json").write_text(json.dumps(estados), encoding="utf-8")
    if arquivo != "ausente":
        for path, conteudo in remoto.arquivos.items():
            if arquivo == "adulterado":
                evento = json.loads(conteudo)
                evento["detalhe"] = "Motivo diferente do pedido integrado."
                conteudo = json.dumps(evento).encode("utf-8")
            (pasta / path.removeprefix("fila/")).write_bytes(conteudo)
    resposta = cliente.get(reverse("caixa_robos"), {"pedido": "TAR-102"})
    assert resposta.context["resultado"] == "integrado"
    assert resposta.context["aplicacao_conferida"] is aplicada
    assert (
        "O cancelamento e o evento original estão presentes"
        in pagina_sem_estilo(resposta)
    ) is aplicada


def test_prompt_da_sessao_do_dono_nao_depende_de_maestro_inexistente():
    prompt = robos.prompt_para_tocar("TAR-102", ["admin"])
    assert "Devolva o resultado a mim" in prompt
    assert "maestro" not in prompt
    assert "aplicação" in prompt and "aceite" in prompt


@respx.mock
@pytest.mark.parametrize(
    "dados",
    [[], {"TAR-102": None}, {"TAR-102": {}}, {"TAR-102": {"estado": "inválido"}}],
)
def test_fila_invalida_recusa_cancelamento_e_preserva_motivo(
    tmp_path, monkeypatch, com_token, dados
):
    pasta = fila_com_ranking(tmp_path, monkeypatch)
    (pasta / "estados.json").write_text(json.dumps(dados), encoding="utf-8")
    resposta = _dentro().post(
        reverse("caixa_robos_excluir"),
        {"tarefa": "TAR-102", "motivo": "Conservar este motivo."},
    )
    assert resposta.status_code == 400
    assert resposta.context["resultado"] == "sem_fila"
    assert resposta.context["rascunho"]["motivo"] == "Conservar este motivo."
    assert "Conferir a fila e retomar o pedido público" in pagina_sem_estilo(resposta)
    assert len(respx.calls) == 1


@respx.mock
def test_consulta_integrada_sem_fila_nao_afirma_aplicacao(
    tmp_path, monkeypatch, com_token
):
    pasta = fila_com_ranking(tmp_path, monkeypatch)
    remoto = github_responde_bem()
    cliente = _dentro()
    cliente.post(
        reverse("caixa_robos_excluir"),
        {"tarefa": "TAR-102", "motivo": "Motivo persistente."},
    )
    remoto.prs[0].update(state="closed", merged=True)
    (pasta / "estados.json").unlink()
    resposta = cliente.get(reverse("caixa_robos"), {"pedido": "TAR-102"})
    assert resposta.context["resultado"] == "integrado"
    assert resposta.context["aplicacao_conferida"] is False
    assert resposta.context["rascunho"]["motivo"] == "Motivo persistente."
    assert "ainda não foi confirmada" in pagina_sem_estilo(resposta)
