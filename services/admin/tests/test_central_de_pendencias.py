"""Teste-guarda: a Central de Pendências (`/admin/pendencias/`), degrau 1.

Plano: `documentos/pendencias-e-conferencia-por-pares.md`.

O QUE ESTE ARQUIVO EXISTE PARA IMPEDIR, e por que os testes óbvios não
impediriam:

1. **A tela dizendo "nada esperando você" quando a verdade é "não consegui
   perguntar".** É a falha mais cara possível aqui, e a única cujo custo se
   mede em pessoas: nove gente esperando aprovação viraria um zero, e o
   mantenedor fecharia a tela em paz. Um teste que só afirmasse `200` ficaria
   verde com a `alunos` fora do ar. Por isso os guardas de baixo derrubam cada
   fila de propósito e exigem que a tela MUDE de frase.

2. **O total virando uma conta fechada com uma fila muda.** Somar o que se sabe
   e apresentar como "20 coisas esperando você" é a mesma mentira do zero,
   disfarçada de precisão. A tela tem de dizer "pelo menos".

3. **A confissão sumindo.** Este degrau enxerga duas das cinco filas do site.
   Uma portaria que enxerga metade e não avisa ensina o mantenedor a confiar
   num "nada esperando" que ela não pode sustentar.

4. **O número do painel divergindo do painel.** A regra da caixa "Precisa de
   você" mora em `painel/logica.js::caixaDeEntrada`, e esta célula não roda
   JavaScript: ela lê o carimbo que o gerador deixa em `painel.html`. Um
   `test_...` que montasse uma página de mentira com o formato esperado
   provaria apenas que o teste concorda com o código. O guarda daqui lê a
   página REAL gerada pelo gerador REAL (o `conftest` a materializa), que é a
   única forma de a divergência de formato aparecer aqui e não em produção.

5. **A rota nascendo fora da porta.** `CAMINHOS_ISENTOS` é igualdade exata e
   já tem guarda próprio, mas ele prova que ninguém acrescentou isenção, não
   que ESTA rota responde a quem não é da casa. Aqui se mede de fora.

A rede é dublada com `respx`, como nos irmãos desta pasta: além de isolar, é
isso que prova que a tela não sai para a rede por conta própria, porque
`respx.mock` sem rota registrada estoura em qualquer chamada inesperada.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone as tz
import hashlib
import json
from pathlib import Path

import httpx
import pytest
import respx
from django.test import Client
from django.urls import get_script_prefix, reverse, set_script_prefix

from apps.core import moldura
from apps.core import admin_dados, painel
from apps.core import robos
from apps.core import pendencias as central
from apps.core.painel import diretorio_do_painel

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
ALUNOS = "http://alunos:8000/api/alunos"
FILA_DE_ENTRADA = f"{ALUNOS}/pre-matriculas"
LISTA_DE_ALUNOS = f"{ALUNOS}/matriculas"
CAIXA = "http://sugestoes:8000/interno"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"
DE_FORA = "estranho@exemplo.com"
TELA = "/pendencias/"


@respx.mock
@pytest.mark.parametrize("alternativa", ["livro", "fila"])
def test_central_identifica_as_duas_publicacoes_sem_trocar_a_selecao(
    tmp_path, monkeypatch, alternativa
):
    from tests.test_versao_dos_dados_admin import pacote

    livro = pacote(
        tmp_path / "livro",
        texto="pedidosDoDono: { quantidade: 0, maisAntigoQuando: null }",
    )
    fila = pacote(
        tmp_path / "fila",
        sha="b" * 40,
        run=11,
        tipo="fila",
        extras={"estados.json": {}},
    )
    monkeypatch.setattr(
        painel,
        "CANDIDATOS",
        (tmp_path / "ausente", livro) if alternativa == "livro" else (livro,),
    )
    monkeypatch.setattr(
        robos,
        "CANDIDATOS",
        (tmp_path / "ausente", fila) if alternativa == "fila" else (fila,),
    )
    outra_fila = pacote(
        tmp_path / "outra-fila",
        sha="c" * 40,
        run=12,
        tipo="fila",
        extras={"estados.json": {}},
    )
    ler_estados = robos.ler_estados

    def ler_e_trocar(pasta):
        estados = ler_estados(pasta)
        monkeypatch.setattr(robos, "CANDIDATOS", (outra_fila,))
        return estados

    monkeypatch.setattr(robos, "ler_estados", ler_e_trocar)
    _todos_respondem([])
    html = _texto(_dentro().get(TELA))
    assert "Dados do livro" in html
    assert "Dados da fila de trabalho" in html
    rotulo = "Dados do livro" if alternativa == "livro" else "Dados da fila de trabalho"
    assert f"<details open><summary>{rotulo}</summary>" in html
    assert "a" * 40 in html
    assert "b" * 40 in html
    assert "Execução 1000" in html
    assert "Execução 1100" in html
    assert "c" * 40 not in html
    assert "cópia alternativa" in html
    assert str(tmp_path) not in html


@respx.mock
def test_central_inclui_a_decisao_humana_da_fila_sem_trabalho_tecnico(
    tmp_path, monkeypatch
):
    carimbar_painel(
        tmp_path,
        monkeypatch,
        [{"arquivo": "a", "tarefa": None}, {"arquivo": "b", "tarefa": None}],
    )
    pasta = tmp_path / "fila"
    pasta.mkdir()
    (pasta / "estados.json").write_text(
        json.dumps(
            {
                "TAR-701": {
                    "estado": "bloqueada",
                    "espera": "mantenedor",
                    "titulo": "Escolher destino",
                    "motivo": "Falta sua decisão",
                },
                "TAR-702": {
                    "estado": "bloqueada",
                    "espera": "fila",
                    "titulo": "Esperar outra tarefa",
                },
                "TAR-703": {"estado": "em execução", "titulo": "Submetida sem aceite"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(robos, "CANDIDATOS", (pasta,))
    _todos_respondem([])
    html = _texto(_dentro().get(TELA))
    assert "1 · Tarefas esperando uma decisão sua" in html
    assert reverse("caixa_robos") in html
    assert "três fontes" in html


@respx.mock
@pytest.mark.parametrize(
    "conteudo",
    [
        None,
        "{",
        "[]",
        '{"TAR-001": null}',
        '{"TAR-001": {"estado": "estado-inventado"}}',
        '{"errada": {"estado": "na fila"}}',
    ],
)
def test_fila_de_trabalho_indisponivel_na_central_nao_e_zero(
    tmp_path, monkeypatch, conteudo
):
    if conteudo is not None:
        (tmp_path / "estados.json").write_text(conteudo, encoding="utf-8")
    monkeypatch.setattr(robos, "CANDIDATOS", (tmp_path,))
    _todos_respondem([])
    html = _texto(_dentro().get(TELA))
    assert "Não foi possível consultar a fila de trabalho agora." in html
    assert "0 · Tarefas" not in html
    assert "Você está em dia" not in html


def carimbar_painel(tmp_path, monkeypatch, vinculos):
    pasta = tmp_path / "painel"
    pasta.mkdir(exist_ok=True)
    (pasta / "painel.html").write_text(
        'pedidosDoDono: { quantidade: 2, maisAntigoQuando: "2026-09-01" },\n'
        + (
            "pedidosDoDonoVinculos: " + json.dumps(vinculos) + ",\n"
            if vinculos is not None
            else ""
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(central, "diretorio_do_painel", lambda: pasta)


def carimbar_vinculos_em_arquivo(
    tmp_path, monkeypatch, *, mudar_fonte=None, mudar_dados=None
):
    carimbo = "abcdef123456"
    dados = {
        "carimbo": carimbo,
        "quantidade": 2,
        "vinculos": [
            {"arquivo": "a", "tarefa": "TAR-701"},
            {"arquivo": "b", "tarefa": None},
        ],
    }
    dados.update(mudar_dados or {})
    conteudo = (json.dumps(dados, ensure_ascii=False) + "\n").encode("utf-8")
    fonte = {
        "arquivo": "paginas/pedidos-do-dono.json",
        "carimbo": carimbo,
        "quantidade": 2,
        "sha256": hashlib.sha256(conteudo).hexdigest(),
    }
    fonte.update(mudar_fonte or {})
    carimbar_painel(tmp_path, monkeypatch, [])
    pasta = tmp_path / "painel"
    (pasta / "paginas").mkdir()
    (pasta / "paginas/pedidos-do-dono.json").write_bytes(conteudo)
    pagina = pasta / "painel.html"
    pagina.write_text(
        'var PAINEL = {\n  carimbo: "'
        + carimbo
        + '",\n'
        + pagina.read_text(encoding="utf-8")
        + "pedidosDoDonoVinculosFonte: "
        + json.dumps(fonte)
        + ",\n};",
        encoding="utf-8",
    )
    return pasta


def test_vinculos_externos_completos_conferidos_retiram_so_tar_explicita(
    tmp_path, monkeypatch
):
    carimbar_vinculos_em_arquivo(tmp_path, monkeypatch)
    fila = central.decisoes_paradas_no_painel(datetime.now(tz.utc))
    assert fila.quantidade == 2
    assert fila.tarefas == frozenset({"TAR-701"})


def test_vinculos_permanecem_na_pasta_concreta_fixada_pela_resposta(
    tmp_path, monkeypatch
):
    primeira = tmp_path / "primeira"
    segunda = tmp_path / "segunda"
    primeira.mkdir()
    segunda.mkdir()
    pasta_a = carimbar_vinculos_em_arquivo(primeira, monkeypatch)
    pasta_b = carimbar_vinculos_em_arquivo(
        segunda,
        monkeypatch,
        mudar_dados={
            "vinculos": [
                {"arquivo": "a", "tarefa": "TAR-999"},
                {"arquivo": "b", "tarefa": None},
            ]
        },
    )
    monkeypatch.setattr(central, "diretorio_do_painel", diretorio_do_painel)
    monkeypatch.setattr(painel, "CANDIDATOS", (pasta_a,))
    with admin_dados.dados_da_resposta():
        assert diretorio_do_painel() == pasta_a.resolve()
        monkeypatch.setattr(painel, "CANDIDATOS", (pasta_b,))
        fila = central.decisoes_paradas_no_painel(datetime.now(tz.utc))
    assert fila.tarefas == frozenset({"TAR-701"})


@pytest.mark.parametrize("dentro", [False, True])
def test_vinculos_nao_seguem_diretorio_redirecionado(tmp_path, monkeypatch, dentro):
    from tests.test_versao_dos_dados_admin import apontar, retirar_ponteiro

    pasta = carimbar_vinculos_em_arquivo(tmp_path, monkeypatch)
    alvo = (pasta if dentro else tmp_path) / "outra-publicacao"
    (pasta / "paginas").rename(alvo)
    ponteiro = pasta / "paginas"
    apontar(alvo, ponteiro)
    try:
        fila = central.decisoes_paradas_no_painel(datetime.now(tz.utc))
        assert fila.quantidade == 2
        assert fila.tarefas is None
    finally:
        retirar_ponteiro(ponteiro)


def test_caminho_malicioso_e_recusado_antes_de_abrir_bytes(tmp_path, monkeypatch):
    pasta = carimbar_vinculos_em_arquivo(
        tmp_path, monkeypatch, mudar_fonte={"arquivo": "../roubado.json"}
    )
    (pasta.parent / "roubado.json").write_bytes(
        (pasta / "paginas/pedidos-do-dono.json").read_bytes()
    )

    def leitura_proibida(caminho):
        pytest.fail(f"Leu bytes depois de receber caminho proibido: {caminho}")

    monkeypatch.setattr(Path, "read_bytes", leitura_proibida)
    assert central.decisoes_paradas_no_painel(datetime.now(tz.utc)).tarefas is None


def test_nome_alternativo_mesmo_dentro_da_pasta_nao_e_o_artefato_contratado(
    tmp_path, monkeypatch
):
    pasta = carimbar_vinculos_em_arquivo(
        tmp_path, monkeypatch, mudar_fonte={"arquivo": "paginas/outro.json"}
    )
    (pasta / "paginas/outro.json").write_bytes(
        (pasta / "paginas/pedidos-do-dono.json").read_bytes()
    )
    assert central.decisoes_paradas_no_painel(datetime.now(tz.utc)).tarefas is None


@pytest.mark.parametrize("conteudo", [b"{", b"[]", b"null", b"\xff"])
def test_arquivo_ilegivel_mesmo_com_hash_coerente_preserva_contagem(
    tmp_path, monkeypatch, conteudo
):
    pasta = carimbar_vinculos_em_arquivo(tmp_path, monkeypatch)
    arquivo = pasta / "paginas/pedidos-do-dono.json"
    anterior = hashlib.sha256(arquivo.read_bytes()).hexdigest()
    arquivo.write_bytes(conteudo)
    html = pasta / "painel.html"
    html.write_text(
        html.read_text(encoding="utf-8").replace(
            anterior, hashlib.sha256(conteudo).hexdigest()
        ),
        encoding="utf-8",
    )
    fila = central.decisoes_paradas_no_painel(datetime.now(tz.utc))
    assert fila.quantidade == 2 and fila.tarefas is None


def test_descritor_nulo_conserva_leitura_inline_integral(tmp_path, monkeypatch):
    carimbar_painel(
        tmp_path,
        monkeypatch,
        [{"arquivo": "a", "tarefa": "TAR-701"}, {"arquivo": "b", "tarefa": None}],
    )
    html = tmp_path / "painel/painel.html"
    html.write_text(
        html.read_text(encoding="utf-8") + "pedidosDoDonoVinculosFonte: null,\n",
        encoding="utf-8",
    )
    assert central.decisoes_paradas_no_painel(
        datetime.now(tz.utc)
    ).tarefas == frozenset({"TAR-701"})


@pytest.mark.parametrize(
    "linha",
    [
        "pedidosDoDonoVinculosFonte: null\n",
        "pedidosDoDonoVinculosFonte: null,\npedidosDoDonoVinculosFonte: null,\n",
        "pedidosDoDonoVinculosFonte: quebrado,\n",
    ],
)
def test_descritor_malformado_nao_vira_inline_legado(tmp_path, monkeypatch, linha):
    carimbar_painel(
        tmp_path,
        monkeypatch,
        [{"arquivo": "a", "tarefa": "TAR-701"}, {"arquivo": "b", "tarefa": None}],
    )
    html = tmp_path / "painel/painel.html"
    html.write_text(html.read_text(encoding="utf-8") + linha, encoding="utf-8")
    fila = central.decisoes_paradas_no_painel(datetime.now(tz.utc))
    assert fila.quantidade == 2 and fila.tarefas is None


@pytest.mark.parametrize(
    "fonte",
    [
        {"arquivo": "../pedidos-do-dono.json"},
        {"arquivo": "/pedidos-do-dono.json"},
        {"arquivo": "C:\\fora.json"},
        {"arquivo": "paginas\\pedidos-do-dono.json"},
        {"arquivo": "paginas/../pedidos-do-dono.json"},
        {"arquivo": "https://exemplo.com/pedidos.json"},
        {"arquivo": None},
        {"carimbo": "000000000000"},
        {"carimbo": 123},
        {"quantidade": True},
        {"quantidade": 2.0},
        {"quantidade": "2"},
        {"quantidade": 1},
        {"sha256": "0" * 64},
        {"sha256": None},
        {"sha256": 123},
    ],
)
def test_descritor_invalido_nao_deduplica_nem_apaga_a_contagem(
    tmp_path, monkeypatch, fonte
):
    carimbar_vinculos_em_arquivo(tmp_path, monkeypatch, mudar_fonte=fonte)
    fila = central.decisoes_paradas_no_painel(datetime.now(tz.utc))
    assert fila.quantidade == 2
    assert fila.tarefas is None


@pytest.mark.parametrize(
    "dados",
    [
        {"carimbo": "000000000000"},
        {"quantidade": True},
        {"quantidade": 2.0},
        {"quantidade": 1},
        {"vinculos": [{"arquivo": "a", "tarefa": "TAR-701"}]},
        {
            "vinculos": [
                {"arquivo": "a", "tarefa": 701},
                {"arquivo": "b", "tarefa": None},
            ]
        },
    ],
)
def test_arquivo_incoerente_mesmo_com_hash_valido_nao_deduplica(
    tmp_path, monkeypatch, dados
):
    carimbar_vinculos_em_arquivo(tmp_path, monkeypatch, mudar_dados=dados)
    fila = central.decisoes_paradas_no_painel(datetime.now(tz.utc))
    assert fila.quantidade == 2
    assert fila.tarefas is None


@respx.mock
@pytest.mark.parametrize(
    "falha", ["ausente", "alterado", "html_outra_versao", "inline_parcial"]
)
def test_arquivo_de_vinculos_invalido_preserva_assuntos_sem_inventar_total(
    tmp_path, monkeypatch, falha
):
    pasta = carimbar_vinculos_em_arquivo(tmp_path, monkeypatch)
    arquivo = pasta / "paginas/pedidos-do-dono.json"
    html = pasta / "painel.html"
    if falha == "ausente":
        arquivo.unlink()
    elif falha == "alterado":
        arquivo.write_text("{}", encoding="utf-8")
    else:
        texto = html.read_text(encoding="utf-8")
        if falha == "html_outra_versao":
            texto = texto.replace('carimbo: "abcdef123456"', 'carimbo: "000000000000"')
        else:
            texto = texto.replace(
                "pedidosDoDonoVinculos: []",
                'pedidosDoDonoVinculos: [{"arquivo":"a","tarefa":"TAR-701"}]',
            )
        html.write_text(texto, encoding="utf-8")
    (tmp_path / "estados.json").write_text(
        json.dumps(
            {
                tid: {"estado": "bloqueada", "espera": "mantenedor"}
                for tid in ("TAR-701", "TAR-702")
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(robos, "CANDIDATOS", (tmp_path,))
    _todos_respondem([])
    texto = _texto(_dentro().get(TELA))
    assert "2 · Decisões suas paradas" in texto
    assert "2 · Tarefas esperando uma decisão sua" in texto
    assert "Total de assuntos desconhecido" in texto
    assert 'class="hero-numero"' not in texto


@respx.mock
def test_o_mesmo_assunto_no_livro_e_na_fila_conta_uma_vez(tmp_path, monkeypatch):
    carimbar_painel(
        tmp_path,
        monkeypatch,
        [
            {"arquivo": "20260909-001", "tarefa": "TAR-701"},
            {"arquivo": "20260909-002", "tarefa": None},
        ],
    )
    (tmp_path / "estados.json").write_text(
        json.dumps(
            {
                tid: {
                    "estado": "bloqueada",
                    "espera": "mantenedor",
                    "titulo": "Mesmo título",
                }
                for tid in ["TAR-701", "TAR-702"]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(robos, "CANDIDATOS", (tmp_path,))
    _todos_respondem([])
    html = _texto(_dentro().get(TELA))
    assert '<div class="hero-numero">3</div>' in html
    assert "1 · Tarefas esperando uma decisão sua" in html
    assert "2 · Decisões suas paradas" in html
    assert "Total parcial" in html
    assert "Registros sem vínculo de tarefa" in html


@respx.mock
@pytest.mark.parametrize(
    "vinculos",
    [None, [], [{"arquivo": "a", "tarefa": 123}, {"arquivo": "b", "tarefa": None}]],
)
def test_vinculos_ausentes_ou_invalidos_preservam_linhas_sem_inventar_total(
    tmp_path, monkeypatch, vinculos
):
    carimbar_painel(tmp_path, monkeypatch, vinculos)
    (tmp_path / "estados.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(robos, "CANDIDATOS", (tmp_path,))
    _todos_respondem([])
    html = _texto(_dentro().get(TELA))
    assert "2 · Decisões suas paradas" in html
    assert 'class="hero-numero"' not in html
    assert "Total de assuntos desconhecido" in html


@respx.mock
def test_parada_sem_responsavel_nao_inventa_decisao_humana(tmp_path, monkeypatch):
    carimbar_painel(
        tmp_path,
        monkeypatch,
        [{"arquivo": "a", "tarefa": None}, {"arquivo": "b", "tarefa": None}],
    )
    (tmp_path / "estados.json").write_text(
        json.dumps(
            {
                "TAR-701": {"estado": "bloqueada", "titulo": "Quem destrava?"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(robos, "CANDIDATOS", (tmp_path,))
    _todos_respondem([])
    html = _texto(_dentro().get(TELA))
    assert "1 · Tarefas esperando uma decisão sua" not in html
    assert "responsável ainda não informado" in html


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    monkeypatch.setenv("ALUNOS_API_URL", ALUNOS)
    monkeypatch.setenv("ALUNOS_API_TOKEN", "token-do-par-admin-alunos")
    monkeypatch.setenv("SUGESTOES_API_URL", CAIXA)
    monkeypatch.setenv("SUGESTOES_API_TOKEN", "token-do-par-admin-sugestoes")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


def _dentro(email: str = DONO) -> Client:
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "id-opaco-123",
                "nome_exibido": "Fulano",
                "papel": None,
                "email": email,
            },
        )
    )
    cliente = Client()
    cliente.defaults["HTTP_COOKIE"] = COOKIE
    return cliente


def _texto(resposta) -> str:
    return resposta.content.decode()


def _quem_espera(quantos: int, esperando_ha_dias: int = 3) -> list[dict]:
    """Gente na fila de entrada, na forma EXATA que o contrato promete."""
    return [
        {
            "id": str(i),
            "site_id": "escola-a",
            "email": f"pessoa{i}@exemplo.com",
            "nome_completo": f"Pessoa {i}",
            "whatsapp": "(96) 99999-0000",
            "status": "aguardando",
            "criada_em": "2026-09-04T10:00:00Z",
            "esperando_ha_dias": esperando_ha_dias if i == 0 else 1,
            "ja_foi_aluno": False,
            "passagens_anteriores": 0,
            "saiu_em": None,
        }
        for i in range(quantos)
    ]


def _todos_respondem(fila=None):
    """As duas fontes de pé. O painel vem do disco, materializado pelo conftest."""
    respx.get(FILA_DE_ENTRADA).mock(
        return_value=httpx.Response(200, json=_quem_espera(9) if fila is None else fila)
    )
    respx.get(LISTA_DE_ALUNOS).mock(return_value=httpx.Response(200, json=[]))


# ---------------------------------------------------------------------------
# 1. A porta vem antes da tela
# ---------------------------------------------------------------------------
@respx.mock
def test_sem_sessao_a_central_manda_para_o_login():
    resposta = Client().get(TELA)
    assert resposta.status_code == 302
    assert "/entrar/google" in resposta["Location"]


@respx.mock
def test_para_quem_nao_e_da_casa_a_central_nao_existe():
    """404, e não 403: para um estranho, o bastidor não existe."""
    _todos_respondem()
    assert _dentro(DE_FORA).get(TELA).status_code == 404


# ---------------------------------------------------------------------------
# 2. As duas filas na tela, com a idade de cada uma
# ---------------------------------------------------------------------------
@respx.mock
def test_as_duas_filas_aparecem_com_quantidade_e_idade():
    _todos_respondem()
    html = _texto(_dentro().get(TELA))

    assert "9 · Pessoas querendo entrar na escola" in html
    assert "A mais antiga espera há 3 dias." in html
    assert "Decisões suas paradas no painel do sistema" in html


@respx.mock
def test_a_fila_da_assinatura_nao_existe_mais_na_portaria():
    """Ela saiu em 06/09/2026, junto com a assinatura de obra da Caixa.

    Sem este guarda a linha volta de boa-fé na primeira sessão que ler o
    cabeçalho antigo deste arquivo — e voltaria como um 0 eterno, porque uma
    ideia em "Planejado" não espera mais por ninguém.
    """
    _todos_respondem()
    html = _texto(_dentro().get(TELA))

    # Medido pelo TÍTULO da fila e pelo LINK dela, que são as duas formas em
    # que a linha voltaria à tela. O nome "Caixa de Sugestões" sozinho não
    # serve de asserção aqui: ele vive também num comentário do CSS da
    # moldura, que é de outro assunto e viaja em toda tela do Admin.
    assert "Ideias esperando a sua assinatura" not in html
    assert reverse("caixa_esperando") not in html


@respx.mock
def test_cada_linha_leva_ao_lugar_onde_a_coisa_se_resolve():
    """A portaria não resolve nada por dentro: ela é uma porta, e a porta abre.

    Medido pelo DESTINO, e não pela presença do texto: uma tela que listasse as
    filas sem link nenhum passaria num teste de texto e seria inútil.
    """
    _todos_respondem()
    html = _texto(_dentro().get(TELA))

    for rotulo, rota in (
        ("Pessoas querendo entrar na escola", "escola_alunos"),
        ("Decisões suas paradas no painel do sistema", "painel"),
    ):
        ate = html.index(rotulo)
        inicio = html.rindex('href="', 0, ate) + len('href="')
        assert html[inicio : html.index('"', inicio)] == reverse(rota), rotulo


# ---------------------------------------------------------------------------
# 3. "Não consegui perguntar" NUNCA vira zero — o guarda que importa
# ---------------------------------------------------------------------------
@respx.mock
def test_com_a_alunos_muda_a_tela_diz_isso_e_NAO_mostra_zero():
    """O guarda mais caro deste arquivo.

    A `alunos` fora do ar não pode virar "ninguém está esperando aprovação". A
    asserção é dupla de propósito: a frase honesta tem de APARECER, e a frase
    tranquilizadora tem de SUMIR. Só a primeira metade deixaria passar uma tela
    que dissesse as duas coisas ao mesmo tempo.
    """
    respx.get(FILA_DE_ENTRADA).mock(return_value=httpx.Response(503))
    respx.get(LISTA_DE_ALUNOS).mock(return_value=httpx.Response(200, json=[]))
    html = _texto(_dentro().get(TELA))

    assert "Não foi possível consultar a lista de alunos agora." in html
    assert "0 · Pessoas querendo entrar" not in html
    assert "Nada esperando você em: a lista de alunos" not in html


@respx.mock
def test_sem_o_par_de_tokens_a_tela_tambem_abre(monkeypatch):
    """Enquanto o par não estiver no env da VPS, a área abre e a tela avisa."""
    monkeypatch.delenv("ALUNOS_API_URL", raising=False)

    resposta = _dentro().get(TELA)

    assert resposta.status_code == 200
    assert "Não foi possível consultar" in _texto(resposta)


@respx.mock
def test_com_uma_fila_muda_o_total_vira_um_PISO_e_nao_uma_conta_fechada(
    tmp_path, monkeypatch
):
    """Somar o que se sabe e chamar de total é a mentira do zero, com precisão.

    O guarda mede as duas frases porque elas são a mesma tela em dois estados,
    e trocar uma pela outra é a regressão provável.
    """
    carimbar_painel(
        tmp_path,
        monkeypatch,
        [{"arquivo": "a", "tarefa": None}, {"arquivo": "b", "tarefa": None}],
    )
    respx.get(FILA_DE_ENTRADA).mock(return_value=httpx.Response(503))
    respx.get(LISTA_DE_ALUNOS).mock(return_value=httpx.Response(200, json=[]))

    html = _texto(_dentro().get(TELA))

    assert "É <b>pelo menos</b> isso" in html
    assert "nas duas filas que esta tela já enxerga" not in html


@respx.mock
def test_com_tudo_respondendo_o_total_ainda_declara_as_fontes_nao_integradas(
    tmp_path, monkeypatch
):
    carimbar_painel(
        tmp_path,
        monkeypatch,
        [{"arquivo": "a", "tarefa": None}, {"arquivo": "b", "tarefa": None}],
    )
    (tmp_path / "estados.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(robos, "CANDIDATOS", (tmp_path,))
    _todos_respondem()
    html = _texto(_dentro().get(TELA))

    assert "nas três fontes consultadas" in html
    assert "Total parcial" in html
    assert "É <b>pelo menos</b> isso" not in html


@respx.mock
def test_zero_de_verdade_e_uma_frase_DIFERENTE_de_nao_sei():
    """As duas telas que se parecem de dentro do código, medidas separadas.

    Sem este guarda, um `{% if fila.quantidade %}` no template juntaria os dois
    casos e ninguém veria: zero é falso em template, exatamente como `None`.
    """
    respx.get(FILA_DE_ENTRADA).mock(return_value=httpx.Response(200, json=[]))
    respx.get(LISTA_DE_ALUNOS).mock(return_value=httpx.Response(200, json=[]))
    html = _texto(_dentro().get(TELA))

    assert "Nada esperando você em:" in html
    assert "a lista de alunos" in html
    assert "Não foi possível consultar a lista de alunos" not in html


# ---------------------------------------------------------------------------
# 4. A confissão: a tela diz o que ela ainda NÃO conta
# ---------------------------------------------------------------------------
@respx.mock
def test_a_tela_confessa_as_filas_que_ainda_nao_enxerga():
    """Portaria que enxerga metade e não avisa é pior que portaria nenhuma."""
    _todos_respondem()
    html = _texto(_dentro().get(TELA))

    assert "O que esta tela ainda não conta" in html
    for nome, endereco in central.FILAS_QUE_AINDA_NAO_VEJO:
        assert nome in html
        assert endereco in html


def test_a_confissao_lista_as_TRES_filas_do_degrau_3_e_nenhuma_outra():
    """Trava o conteúdo da lista, e não só a existência do bloco.

    Uma lista que ficasse vazia por engano deixaria o guarda de cima verde: o
    `for` não iteraria, e o bloco sumiria da tela sem nenhum vermelho.
    """
    assert [nome for nome, _ in central.FILAS_QUE_AINDA_NAO_VEJO] == [
        "Portfólios pedindo conferência",
        "Provas de marco enviadas pelos alunos",
        "Checkpoints de aula esperando laudo",
    ]


# ---------------------------------------------------------------------------
# 4.1 As quatro visões não escondem fonte que a Central ainda não lê
# ---------------------------------------------------------------------------
@respx.mock
def test_as_quatro_funcoes_encontram_hoje_aprovacoes_atrasos_e_resultados():
    """A Central oferece a mesma pergunta operacional às quatro pessoas.

    O cartão não inventa uma fila para Ensino só porque ela ainda não tem uma
    porta que a enumere. A resposta honesta continua sendo visível ao lado das
    outras três perguntas, em vez de um zero que pareceria trabalho concluído.
    """
    _todos_respondem()

    html = _texto(_dentro().get(TELA))

    for funcao, pessoa in (
        ("Estratégia e Conteúdo", "Arameu"),
        ("Operações e Tráfego", "Ryan"),
        ("Ensino e Comunidade", "Lívia"),
        ("Comercial e Relacionamento", "Maria"),
    ):
        assert funcao in html
        assert pessoa in html
    for pergunta in (
        "Fazer hoje",
        "Aprovar",
        "Resolver atrasos",
        "Acompanhar resultados",
    ):
        assert html.count(pergunta) == 4
    assert "A fonte ainda não oferece uma lista de portfólios para conferir." in html
    assert "A fonte de marcos ainda não tem contrato de leitura para a Central." in html
    assert "A fonte ainda não oferece uma lista de checkpoints esperando laudo." in html


@respx.mock
def test_acessos_indisponiveis_e_crm_sem_leitura_nao_parecem_fila_vazia():
    """Acesso e CRM declaram separadamente o que a Central consegue ler."""
    respx.get(FILA_DE_ENTRADA).mock(return_value=httpx.Response(503))
    respx.get(LISTA_DE_ALUNOS).mock(return_value=httpx.Response(200, json=[]))

    html = _texto(_dentro().get(TELA))

    assert "Comercial e Relacionamento" in html
    assert "A fonte Acessos à escola não respondeu agora." in html
    assert (
        "Integração indisponível: Ainda não há contrato de leitura nem consumidor."
        in html
    )
    assert "Acompanhe o CRM na fonte dona até a Central ganhar leitura." in html
    assert "A fonte de oportunidades e acessos não respondeu agora." not in html
    assert "0 pendência comercial" not in html


def test_fonte_sem_leitura_precisa_explicar_a_lacuna():
    """Fonte sem fila não pode gerar um trecho em branco na Central."""
    with pytest.raises(ValueError, match="precisa explicar"):
        central.FonteDeTrabalho(nome="CRM de oportunidades", fila=None)


@respx.mock
def test_queda_futura_do_crm_nomeia_a_fonte_e_nao_parece_fila_vazia(monkeypatch):
    """Quando o CRM ganhar leitura, a queda dele usa a mesma guarda explícita."""
    _todos_respondem()
    visao = central.VisaoDeResponsabilidade(
        nome="Comercial e Relacionamento",
        pessoa="Maria",
        fontes=(),
        aprovacoes=(),
        destino="/escola/alunos/",
        destino_texto="Abrir pessoas aguardando acesso e acompanhar o desfecho.",
        fontes_de_trabalho=(
            central.FonteDeTrabalho(
                nome="CRM de oportunidades",
                fila=central.Fila(
                    titulo="Oportunidades ativas",
                    quantidade=None,
                    espera_ha=None,
                    href="/crm/",
                    o_que_e="",
                    onde_mora="o CRM",
                ),
            ),
        ),
        lacunas=(),
    )
    monkeypatch.setattr(central, "visoes_de_responsabilidade", lambda _: (visao,))

    html = _texto(_dentro().get(TELA))

    assert "A fonte CRM de oportunidades não respondeu agora." in html
    assert "Nenhuma pessoa aguarda acesso nesta fonte agora." not in html


@respx.mock
def test_titular_vazio_permanece_no_cartao_com_ausencia_e_sem_substituto(monkeypatch):
    """A falta de pessoa não apaga a função nem permite inventar alguém."""
    _todos_respondem()
    cadastro = central._cadastro_de_responsabilidades()
    assert cadastro is not None
    cadastro["funcoes"]["comercial-relacionamento"]["pessoa"] = ""
    monkeypatch.setattr(central, "_cadastro_de_responsabilidades", lambda: cadastro)

    html = _texto(_dentro().get(TELA))

    inicio = html.index("Comercial e Relacionamento")
    fim = html.index("</section>", inicio)
    cartao = html[inicio:fim]
    assert "Titular ausente." in cartao
    assert "Não há substituto humano cadastrado." in cartao
    assert "Maria" not in cartao


@respx.mock
def test_integracao_indisponivel_e_acesso_negado_tem_estados_e_gestos_distintos(
    monkeypatch,
):
    """A Central não chama falta de integração de recusa de acesso."""
    _todos_respondem()
    visao = central.VisaoDeResponsabilidade(
        nome="Comercial e Relacionamento",
        pessoa="Maria",
        fontes=(),
        aprovacoes=(),
        destino="/escola/alunos/",
        destino_texto="Abrir pessoas aguardando acesso e acompanhar o desfecho.",
        fontes_de_trabalho=(
            central.FonteDeTrabalho(
                nome="CRM de oportunidades",
                fila=None,
                estado=central.INTEGRACAO_INDISPONIVEL,
                explicacao="Ainda não há contrato de leitura nem consumidor.",
                proximo_gesto="Acompanhe o CRM na fonte dona até a Central ganhar leitura.",
            ),
            central.FonteDeTrabalho(
                nome="Acessos à escola",
                fila=None,
                estado=central.ACESSO_NEGADO,
                explicacao="A fonte recusou a credencial de leitura da Central.",
                proximo_gesto="Peça ao titular de Operações que restaure a leitura autorizada.",
            ),
        ),
        lacunas=(),
    )
    monkeypatch.setattr(central, "visoes_de_responsabilidade", lambda _: (visao,))

    html = _texto(_dentro().get(TELA))

    assert (
        "Integração indisponível: Ainda não há contrato de leitura nem consumidor."
        in html
    )
    assert "Acompanhe o CRM na fonte dona até a Central ganhar leitura." in html
    assert "Acesso negado: A fonte recusou a credencial de leitura da Central." in html
    assert "Peça ao titular de Operações que restaure a leitura autorizada." in html


@respx.mock
def test_crm_vazio_e_com_demanda_nao_viram_pessoas_aguardando_acesso(monkeypatch):
    """O CRM conta oportunidades; acesso conta pessoas, são fontes independentes."""
    _todos_respondem()

    def central_com_crm(quantidade):
        return (
            central.VisaoDeResponsabilidade(
                nome="Comercial e Relacionamento",
                pessoa="Maria",
                fontes=(),
                aprovacoes=(),
                destino="/escola/alunos/",
                destino_texto="Abrir pessoas aguardando acesso e acompanhar o desfecho.",
                fontes_de_trabalho=(
                    central.FonteDeTrabalho(
                        nome="CRM de oportunidades",
                        fila=central.Fila(
                            titulo="Oportunidades ativas",
                            quantidade=quantidade,
                            espera_ha=2 if quantidade else None,
                            href="/crm/",
                            o_que_e="",
                            onde_mora="o CRM",
                        ),
                        singular="oportunidade ativa",
                        plural="oportunidades ativas",
                        vazio="Nenhuma oportunidade ativa nesta fonte agora.",
                    ),
                    central.FonteDeTrabalho(
                        nome="Acessos à escola",
                        fila=central.Fila(
                            titulo="Pessoas aguardando acesso",
                            quantidade=0,
                            espera_ha=None,
                            href="/escola/alunos/",
                            o_que_e="",
                            onde_mora="a lista de alunos",
                        ),
                        singular="pessoa aguardando acesso",
                        plural="pessoas aguardando acesso",
                        vazio="Nenhuma pessoa aguarda acesso nesta fonte agora.",
                    ),
                ),
                lacunas=(),
            ),
        )

    monkeypatch.setattr(
        central, "visoes_de_responsabilidade", lambda _: central_com_crm(0)
    )
    vazio = _texto(_dentro().get(TELA))
    monkeypatch.setattr(
        central, "visoes_de_responsabilidade", lambda _: central_com_crm(2)
    )
    com_demanda = _texto(_dentro().get(TELA))

    assert "Nenhuma oportunidade ativa nesta fonte agora." in vazio
    assert "2 oportunidades ativas" in com_demanda
    assert "2 pessoas aguardando acesso" not in com_demanda


@respx.mock
def test_aprovacoes_usam_link_interno_da_fonte_dona():
    """A aprovação abre a casa que a decide, sem URL vinda do cadastro."""
    _todos_respondem()
    html = _texto(_dentro().get(TELA))

    for funcao, rota in (
        ("Estratégia e Conteúdo", "placar"),
        ("Ensino e Comunidade", "escola"),
    ):
        inicio = html.index(funcao)
        aprovar = html.index("Aprovar", inicio)
        resolver_atrasos = html.index("Resolver atrasos", aprovar)
        assert f'<a href="{reverse(rota)}">' in html[aprovar:resolver_atrasos]


@respx.mock
def test_sem_cadastro_de_responsabilidades_a_central_nao_inventa_quatro_titulares(
    monkeypatch,
):
    """O cadastro publicado caiu: não há pessoa atribuível por adivinhação."""
    monkeypatch.setattr(central, "diretorio_do_painel", lambda: None)
    _todos_respondem()

    html = _texto(_dentro().get(TELA))

    assert "Não consegui ler o cadastro de responsabilidades." in html
    assert "Estratégia e Conteúdo" not in html


@respx.mock
def test_cadastro_de_responsabilidades_de_formato_errado_e_recusado(monkeypatch):
    """JSON válido ainda pode não ser o cadastro que a tela espera."""
    monkeypatch.setattr(central.json, "loads", lambda _: [])

    assert central._cadastro_de_responsabilidades() is None


# ---------------------------------------------------------------------------
# 5. O número do painel é o do PAINEL, lido da página que o gerador produz
# ---------------------------------------------------------------------------
def test_o_carimbo_da_fila_casa_com_a_pagina_REAL_do_gerador():
    """A ponte entre o gerador (JavaScript) e esta célula (Python), medida.

    Não é um teste de formato contra si mesmo: a página vem do gerador de
    verdade, materializado pelo `conftest`. No dia em que alguém mudar a forma
    do carimbo de um lado só, o vermelho aparece aqui, e não na tela dele.
    """
    pasta = diretorio_do_painel()
    assert pasta is not None, (
        "a pasta do painel não foi encontrada — sem ela este guarda não mede "
        "nada, e isso não é um OK ([INV-CI01])."
    )
    achado = central._CARIMBO_DA_FILA.search(
        (pasta / "painel.html").read_text(encoding="utf-8")
    )
    assert achado is not None, (
        "o gerador do painel não carimbou `pedidosDoDono` na página, ou mudou a "
        "forma do carimbo. A Central passaria a dizer 'não consegui perguntar' "
        "para sempre, em silêncio. Conserte `painel/gerar_manifesto.js` e o "
        "padrão em `apps/core/pendencias.py` juntos."
    )
    assert int(achado.group(1)) >= 0


@respx.mock
def test_sem_o_painel_na_imagem_a_linha_diz_que_nao_sabe(monkeypatch):
    """Painel ausente vira "não consegui perguntar", nunca "você está em dia".

    Um zero aqui afirmaria que ele respondeu todos os robôs, que é o contrário
    do que se sabe quando a pasta nem chegou na imagem.
    """
    monkeypatch.setattr(central, "diretorio_do_painel", lambda: None)
    _todos_respondem()

    html = _texto(_dentro().get(TELA))

    assert "Não foi possível consultar o painel do sistema agora." in html
    assert "0 · Decisões suas paradas" not in html


def test_o_carimbo_recusa_uma_pagina_de_outro_formato():
    """A contraprova do padrão: ele não casa com qualquer coisa parecida.

    Um padrão frouxo casaria a linha de outra geração e a Central mostraria um
    número que ninguém calculou.
    """
    assert central._CARIMBO_DA_FILA.search(
        'pedidosDoDono: { quantidade: 14, maisAntigoQuando: "2026-08-31" },'
    )
    assert central._CARIMBO_DA_FILA.search(
        "pedidosDoDono: { quantidade: 0, maisAntigoQuando: null },"
    )
    assert not central._CARIMBO_DA_FILA.search("pedidosDoDono: { quantidade: 14 }")
    assert not central._CARIMBO_DA_FILA.search('pedidosDoDono: "14"')


def test_a_data_do_pedido_mais_antigo_vira_dias_de_espera():
    """A conta que a tela mostra, feita sobre um relógio conhecido.

    Sem duble de rede: é aritmética de data, e a fonte é o carimbo.
    """
    agora = datetime(2026, 9, 7, 12, 0, tzinfo=tz.utc)
    assert central._mais_antiga(["2026-08-31"], agora) == 7
    assert central._mais_antiga([], agora) is None
    # Data no futuro acontece de verdade (relógio da máquina fora de hora), e
    # "espera há -355142 dias" não é um número esquisito: é uma frase sem
    # sentido numa tela feita para leigo.
    adiante = (agora + timedelta(days=30)).date().isoformat()
    assert central._mais_antiga([adiante], agora) == 0


# ---------------------------------------------------------------------------
# 6. A porta da capa e o item do menu, sob o prefixo de produção
# ---------------------------------------------------------------------------
@pytest.fixture
def sob_o_prefixo_publico():
    """O regime de produção: a área inteira mora sob `/admin`.

    Mexe no PREFIXO DE SCRIPT, e não em `settings.FORCE_SCRIPT_NAME`, porque é
    o prefixo de thread que `reverse()` lê (`armadilhas/081`). O `finally`
    restaura o anterior: o prefixo vaza entre testes.
    """
    anterior = get_script_prefix()
    set_script_prefix("/admin/")
    try:
        yield
    finally:
        set_script_prefix(anterior)


@respx.mock
def test_a_visao_geral_oferece_a_porta_da_central(sob_o_prefixo_publico):
    """Um botão que ninguém encontra é uma funcionalidade que não existe.

    E o endereço tem de levar o prefixo público: `href="/pendencias/"` abriria
    no PC de quem desenvolve e daria 404 só na tela dele (`armadilhas/081`).
    """
    respx.get(FILA_DE_ENTRADA).mock(return_value=httpx.Response(200, json=[]))
    respx.get(LISTA_DE_ALUNOS).mock(return_value=httpx.Response(200, json=[]))
    html = _texto(_dentro().get("/"))

    assert "Ver o que está esperando você" in html
    assert 'href="/admin/pendencias/"' in html


def test_a_central_esta_no_menu_de_toda_tela_da_area(sob_o_prefixo_publico):
    """O menu é o que faz a tela ser alcançável de qualquer lugar da área.

    Medido na MOLDURA, que é quem decide o menu de toda página
    (`apps/core/moldura.py`), e com o endereço já sob o prefixo de produção:
    entrar na lista com um `href` sem `/admin` seria um item de menu que dá 404
    só na tela dele (`armadilhas/081`).
    """
    itens = moldura.secoes_do_menu("/")
    nossa = [i for i in itens if i["rotulo"] == "Pendências"]

    assert len(nossa) == 1, "a Central precisa de exatamente um item no menu"
    assert nossa[0]["href"] == "/admin/pendencias/"


def test_a_central_acende_no_menu_quando_e_ela_que_esta_aberta(sob_o_prefixo_publico):
    """ "Você está aqui" tem de valer para a tela nova como vale para as outras.

    A contraprova está junto: aberta noutra tela, o item apaga. Sem ela, um
    item aceso para sempre passaria neste guarda.
    """
    aberta = {i["rotulo"]: i["aqui"] for i in moldura.secoes_do_menu("/pendencias/")}
    noutra = {i["rotulo"]: i["aqui"] for i in moldura.secoes_do_menu("/escola/")}

    assert aberta["Pendências"] is True
    assert noutra["Pendências"] is False
