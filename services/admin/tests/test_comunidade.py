"""O roadmap da Comunidade é calculado da fila e do livro embutidos, nunca digitado."""

import json
from pathlib import Path

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse, set_script_prefix

from apps.core import comunidade, direcao, robos


DONO = "dono@exemplo.com"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
SESSAO = "http://identidade:8000/interno/sessao/completa"
PR = "https://github.com/abundanciabr/sitesdoreino/pull/"


def _evento(pasta: Path, nome: str, dados: dict) -> None:
    (pasta / "eventos" / f"{nome}.json").write_text(
        json.dumps({"arquivo": nome, **dados}, ensure_ascii=False), encoding="utf-8"
    )


def _tarefa(pasta: Path, tid: str, titulo: str, **extra) -> None:
    documento = {"id": tid, "titulo": titulo, "origem": "teste", **extra}
    (pasta / "tarefas" / f"{tid[4:]}-teste.json").write_text(
        json.dumps(documento, ensure_ascii=False), encoding="utf-8"
    )


@pytest.fixture
def fila_comunidade(tmp_path, monkeypatch):
    pasta = tmp_path / "fila_embutida"
    (pasta / "tarefas").mkdir(parents=True)
    (pasta / "eventos").mkdir(parents=True)
    estados = {
        tid: {
            "estado": "concluída",
            "motivo": "",
            "quem": "agent/teste",
            "titulo": f"Título de {tid}",
        }
        for lote in comunidade.LOTES_DA_COMUNIDADE
        for tid in lote["tarefas"]
    }
    estados["TAR-824"] = {"estado": "em execução", "motivo": "", "quem": "agent/forum"}
    estados["TAR-926"] = {
        "estado": "bloqueada",
        "motivo": "Trava: decisão da participação espiritual.",
        "quem": "coordenacao",
        "espera": "mantenedor",
    }
    estados["TAR-828"] = {"estado": "na fila", "motivo": "", "quem": None}
    estados["TAR-929"] = {
        "estado": "bloqueada",
        "motivo": "esperando TAR-828",
        "quem": None,
        "espera": "fila",
    }
    estados["TAR-927"] = {
        "estado": "cancelada",
        "motivo": "substituída",
        "quem": "fila",
    }
    del estados["TAR-928"]
    estados["TAR-9999"] = {"estado": "na fila", "motivo": "", "quem": None}
    estados["TAR-9998"] = {"estado": "na fila", "motivo": "", "quem": None}

    _tarefa(pasta, "TAR-828", "A prova do percurso inteiro em produção")
    _tarefa(pasta, "TAR-929", "O piloto com pessoas de verdade", depende_de=["TAR-828"])
    _tarefa(pasta, "TAR-9999", "Um mural da COMUNIDADE inventado para o teste")
    _tarefa(pasta, "TAR-9998", "Uma tarefa de pagamentos sem relação")
    _evento(
        pasta,
        "20260927-051707-TAR-829-concluida",
        {
            "tarefa": "TAR-829",
            "evento": "concluida",
            "evidencia": f"{PR}2200",
        },
    )
    _evento(
        pasta,
        "20260927-044017-TAR-829-contrato_execucao",
        {
            "tarefa": "TAR-829",
            "evento": "contrato_execucao",
            "contrato": {
                "aceite": ["https://meshcraft.top/docs/comunidade responde 200"]
            },
        },
    )
    _evento(
        pasta,
        "20260927-100000-TAR-824-submetida",
        {
            "tarefa": "TAR-824",
            "evento": "submetida",
            "evidencia": f"{PR}2300",
        },
    )
    _evento(
        pasta,
        "20260927-225048-TAR-926-bloqueada",
        {
            "tarefa": "TAR-926",
            "evento": "bloqueada",
            "detalhe": "Trava: decisão da participação espiritual.",
            "espera": "mantenedor",
        },
    )
    (pasta / "estados.json").write_text(
        json.dumps(estados, ensure_ascii=False), encoding="utf-8"
    )
    monkeypatch.setattr(robos, "CANDIDATOS", (pasta,))
    return pasta


def _registro(pasta: Path, arquivo: str, **campos) -> None:
    linhas = [f'  arquivo: "{arquivo}",']
    for nome, valor in campos.items():
        linhas.append(f"  {nome}: {json.dumps(valor, ensure_ascii=False)},")
    (pasta / f"{arquivo}.js").write_text(
        "(function(){ (window.REGISTROS = window.REGISTROS || []).push({\n"
        + "\n".join(linhas)
        + '\n  detalhe: "várias\\nlinhas"\n}); })();',
        encoding="utf-8",
    )


@pytest.fixture
def livro_comunidade(tmp_path, monkeypatch):
    pasta = tmp_path / "registros"
    pasta.mkdir()
    pendencia = {
        "tipo": "pendencia",
        "frente": "comunidade",
        "precisa_do_dono": True,
        "quando": "2026-09-27",
    }
    _registro(
        pasta,
        "20260927-315-comunidade-beneficio",
        titulo="Decidir o benefício",
        proximo_passo="Responder a qualquer sessão",
        recomendacao="Não criar benefício agora",
        tarefa=None,
        **pendencia,
    )
    _registro(
        pasta,
        "20260927-316-comunidade-espiritual",
        titulo="Decidir a participação espiritual",
        proximo_passo="Responder",
        recomendacao="Convite",
        tarefa="TAR-926",
        **pendencia,
    )
    _registro(
        pasta,
        "20260928-400-resposta",
        tipo="nota",
        frente="comunidade",
        quando="2026-09-28",
        titulo="Resposta dele",
        responde_a="20260927-316-comunidade-espiritual",
    )
    _registro(
        pasta,
        "20260927-500-comunidade-nova",
        titulo="Decidir o nome dos grupos",
        proximo_passo="Escolher",
        recomendacao="Nomes curtos",
        tarefa="TAR-824",
        **pendencia,
    )
    _registro(
        pasta,
        "20260910-059-rumo-velho",
        tipo="rumo",
        frente="comunidade",
        quando="2026-09-10",
        titulo="Rumo velho da Comunidade",
    )
    _registro(
        pasta,
        "20260927-314-rumo-novo",
        tipo="rumo",
        frente="comunidade",
        quando="2026-09-27",
        titulo="Rumo novo da Comunidade",
    )
    _registro(
        pasta,
        "20260930-001-appmax",
        tipo="nota",
        frente="appmax",
        quando="2026-09-30",
        titulo="Registro de outra frente",
    )
    monkeypatch.setattr(direcao, "diretorio_dos_registros", lambda: pasta)
    return pasta


@pytest.fixture
def dentro(monkeypatch, settings):
    monkeypatch.setenv("IDENTIDADE_API_URL", "http://identidade:8000/interno")
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    settings.ADMIN_EMAILS = DONO
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200, json={"autenticado": True, "email": DONO, "nome_exibido": "Dono"}
        )
    )
    cliente = Client()
    cliente.defaults["HTTP_COOKIE"] = COOKIE
    return cliente


def _lote(resposta, codigo: str) -> dict:
    return next(lote for lote in resposta.context["lotes"] if lote["codigo"] == codigo)


def _ids(itens) -> list[str]:
    return [item["id"] for item in itens]


def test_cada_tarefa_pertence_a_exatamente_um_lote():
    todas = [tid for lote in comunidade.LOTES_DA_COMUNIDADE for tid in lote["tarefas"]]
    assert len(todas) == len(set(todas))
    assert (
        len(
            [
                l
                for l in comunidade.LOTES_DA_COMUNIDADE
                if l["codigo"].startswith("COM-")
            ]
        )
        == 10
    )


@respx.mock
def test_cada_estado_cai_na_coluna_certa(fila_comunidade, livro_comunidade, dentro):
    # guarda: services/admin/apps/core/comunidade.py:244
    resposta = dentro.get(reverse("comunidade"))
    html = resposta.content.decode()

    assert resposta.status_code == 200
    inventario = _lote(resposta, "COM-01")
    assert inventario["estado"] == "feito"
    assert _ids(inventario["feito"]) == ["TAR-829"]
    assert inventario["feito"][0]["prs"] == [{"url": f"{PR}2200", "rotulo": "PR #2200"}]
    assert inventario["feito"][0]["no_ar"] == "https://meshcraft.top/docs/comunidade"
    assert f'href="{PR}2200"' in html
    assert "no ar em" in html

    entrada = _lote(resposta, "COM-02")
    assert entrada["estado"] == "em voo"
    assert _ids(entrada["em_voo"]) == ["TAR-824"]
    assert entrada["em_voo"][0]["prs"][0]["rotulo"] == "PR #2300"

    saida = _lote(resposta, "COM-07")
    assert _ids(saida["a_fazer"]) == ["TAR-926"]
    assert (
        saida["a_fazer"][0]["linha"]
        == "espera você: Trava: decisão da participação espiritual."
    )
    assert saida["espera_voce"] is True

    lideranca = _lote(resposta, "COM-08")
    assert _ids(lideranca["canceladas"]) == ["TAR-927"]
    assert lideranca["a_fazer"] == [] and lideranca["feito"] == []
    assert "canceladas: TAR-927" in html


@respx.mock
def test_dependencia_nao_concluida_vai_para_a_fazer_com_a_tarefa_esperada(
    fila_comunidade, livro_comunidade, dentro
):
    # guarda: services/admin/apps/core/comunidade.py:221
    resposta = dentro.get(reverse("comunidade"))

    piloto = _lote(resposta, "COM-10")
    assert _ids(piloto["a_fazer"]) == ["TAR-929"]
    assert (
        piloto["a_fazer"][0]["linha"]
        == "espera TAR-828: A prova do percurso inteiro em produção"
    )
    assert _ids(piloto["em_voo"]) == ["TAR-828"]
    assert piloto["estado"] == "em voo"


@respx.mock
def test_tarefa_do_lote_ausente_da_fila_e_nao_medida(
    fila_comunidade, livro_comunidade, dentro
):
    # guarda: services/admin/apps/core/comunidade.py:228
    resposta = dentro.get(reverse("comunidade"))

    gamificacao = _lote(resposta, "COM-09")
    assert _ids(gamificacao["nao_medidas"]) == ["TAR-928"]
    assert gamificacao["estado"] == "a fazer"
    assert "não medida: TAR-928" in resposta.content.decode()


@respx.mock
def test_tarefa_fora_dos_lotes_com_comunidade_aparece_em_nao_classificadas(
    fila_comunidade, livro_comunidade, dentro
):
    # guarda: services/admin/apps/core/comunidade.py:308
    resposta = dentro.get(reverse("comunidade"))
    html = resposta.content.decode()

    assert _ids(resposta.context["nao_classificadas"]) == ["TAR-9999"]
    assert "Não classificadas" in html
    assert "Um mural da COMUNIDADE inventado para o teste" in html
    assert "TAR-9998" not in html


@respx.mock
def test_pendencia_respondida_some_e_a_aberta_aparece_com_o_lote(
    fila_comunidade, livro_comunidade, dentro
):
    # guarda: services/admin/apps/core/comunidade.py:329
    resposta = dentro.get(reverse("comunidade"))
    html = resposta.content.decode()

    pendencias = resposta.context["livro"]["pendencias"]
    assert [(p["titulo"], p["lote"]) for p in pendencias] == [
        ("Decidir o benefício", "COM-05 Reciprocidade"),
        ("Decidir o nome dos grupos", "COM-02 Entrada e acesso"),
    ]
    assert "Decidir a participação espiritual" not in html
    assert "Não criar benefício agora" in html
    assert "Responder a qualquer sessão" in html
    assert _lote(resposta, "COM-05")["espera_voce"] is True
    assert _ids(resposta.context["bloqueadas_por_voce"]) == ["TAR-926"]


@respx.mock
def test_rumo_mais_recente_e_data_do_ultimo_registro_da_frente(
    fila_comunidade, livro_comunidade, dentro
):
    # guarda: services/admin/apps/core/comunidade.py:323
    resposta = dentro.get(reverse("comunidade"))
    html = resposta.content.decode()

    assert resposta.context["livro"]["rumo"]["titulo"] == "Rumo novo da Comunidade"
    assert resposta.context["livro"]["ultimo_registro"] == "2026-09-28"
    assert "Rumo novo da Comunidade" in html
    assert "Rumo velho da Comunidade" not in html


@respx.mock
def test_fila_ausente_deixa_todo_lote_nao_medido_com_recarregar(
    tmp_path, monkeypatch, livro_comunidade, dentro
):
    # guarda: services/admin/apps/core/comunidade.py:264
    monkeypatch.setattr(robos, "CANDIDATOS", (tmp_path / "ausente",))

    resposta = dentro.get(reverse("comunidade"))
    html = resposta.content.decode()

    assert resposta.status_code == 200
    assert {lote["estado"] for lote in resposta.context["lotes"]} == {"não medido"}
    assert "não li a fila" in html
    assert f'href="{reverse("comunidade")}">Recarregar' in html
    assert "Rumo novo da Comunidade" in html


@respx.mock
def test_livro_ausente_diz_nao_li_e_continua_mostrando_a_fila(
    fila_comunidade, monkeypatch, dentro
):
    monkeypatch.setattr(direcao, "diretorio_dos_registros", lambda: None)

    resposta = dentro.get(reverse("comunidade"))
    html = resposta.content.decode()

    assert resposta.status_code == 200
    assert resposta.context["livro"] is None
    assert "não li o livro" in html
    assert _lote(resposta, "COM-01")["estado"] == "feito"
    assert _lote(resposta, "COM-05")["espera_voce"] is False


def test_registro_ilegivel_nao_vira_livro_pela_metade(tmp_path):
    (tmp_path / "20260927-001-torto.js").write_bytes(b'\xff\xfe arquivo: "x"')

    assert comunidade.ler_registros(tmp_path) is None


@respx.mock
def test_csp_e_titulo_da_aba(fila_comunidade, livro_comunidade, dentro):
    resposta = dentro.get(reverse("comunidade"))

    assert "default-src 'self'" in resposta["Content-Security-Policy"]
    assert "<title>Comunidade | Admin" in resposta.content.decode()


@respx.mock
@pytest.mark.parametrize("rota", ["appmax", "comunidade"])
def test_as_duas_abas_levam_o_prefixo_publico(
    fila_comunidade, livro_comunidade, dentro, rota
):
    set_script_prefix("/admin/")
    try:
        html = dentro.get(f"/{rota}/").content.decode()
    finally:
        set_script_prefix("/")

    assert 'href="/admin/comunidade/"' in html
    assert 'href="/admin/appmax/"' in html


@pytest.mark.django_db
def test_deslogado_recebe_302():
    assert Client().get(reverse("comunidade")).status_code == 302


def test_o_mapa_do_site_declara_a_tela():
    raiz = Path(__file__).resolve().parents[3]
    mapa = json.loads(
        (raiz / "painel" / "mapa-do-site.json").read_text(encoding="utf-8")
    )
    entradas = [
        e
        for e in mapa["enderecos"]
        if e.get("celula") == "admin" and e.get("rota") == "comunidade/"
    ]

    assert len(entradas) == 1
    assert entradas[0]["endereco"] == "/admin/comunidade/"
    assert entradas[0]["para_quem"] == "equipe"
